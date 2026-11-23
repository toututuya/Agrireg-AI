from __future__ import annotations

import argparse
import json
import logging
import math
from collections import Counter
from functools import cached_property
from pathlib import Path
from statistics import median
from threading import Lock
from time import perf_counter
from typing import Any

from .models import TaskPlan
from .planner import PLANNER_SYSTEM, parse_plan
from .planner_data import make_dataset


BASE_MODEL = "Qwen/Qwen3-1.7B"
MAX_SEQUENCE = 768
MAX_GENERATION = 320
logger = logging.getLogger(__name__)


def _prompt(tokenizer, system: str, user: str) -> list[int]:
    return tokenizer.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        tokenize=True, add_generation_prompt=True, enable_thinking=False,
    )


def training_sequence(tokenizer, row: dict) -> dict[str, list[int]]:
    prefix = _prompt(tokenizer, PLANNER_SYSTEM, row["input"])
    answer = json.dumps(row["plan"], ensure_ascii=False, separators=(",", ":")) + tokenizer.eos_token
    target = tokenizer.encode(answer, add_special_tokens=False)
    if len(prefix) + len(target) > MAX_SEQUENCE:
        raise ValueError(f"Training row {row['id']} exceeds {MAX_SEQUENCE} tokens.")
    return {"input_ids": prefix + target, "labels": [-100] * len(prefix) + target}


def _load_model(base: str, device: str, adapter: str = "", four_bit: bool = False) -> tuple:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(base)
    dtype = torch.float32 if device == "cpu" else torch.bfloat16
    options = {"torch_dtype": dtype, "use_safetensors": True, "attn_implementation": "sdpa"}
    if four_bit:
        options["device_map"] = {"": device}
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
    model = AutoModelForCausalLM.from_pretrained(base, **options)
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter)
    return tokenizer, model if four_bit else model.to(device)


def _generate(tokenizer, model, system: str, user: str) -> str:
    import torch
    from transformers import GenerationConfig

    prompt = _prompt(tokenizer, system, user)
    inputs = torch.tensor([prompt], device=model.device)
    generation = GenerationConfig.from_model_config(model.config)
    generation.do_sample = False
    generation.max_new_tokens = MAX_GENERATION
    generation.pad_token_id = tokenizer.pad_token_id
    with torch.inference_mode():
        output = model.generate(
            input_ids=inputs, attention_mask=torch.ones_like(inputs), generation_config=generation,
        )
    return tokenizer.decode(output[0, len(prompt):], skip_special_tokens=True).strip()


def _decode_json(text: str) -> dict[str, Any] | None:
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


class LocalQwenPlanner:
    """Lazy Qwen3 inference with a local LoRA adapter."""

    def __init__(self, base: str, adapter: str, device: str, four_bit: bool = False):
        self.base = base
        self.adapter = adapter
        self.device = device
        self.four_bit = four_bit
        self._lock = Lock()

    @cached_property
    def model(self):
        tokenizer, model = _load_model(self.base, self.device, self.adapter, self.four_bit)
        return tokenizer, model.eval()

    @property
    def enabled(self) -> bool:
        return bool(self.adapter)

    def json_completion(self, system: str, user: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            with self._lock:
                return _decode_json(_generate(*self.model, system, user))
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            logger.warning("Local Qwen3 planner unavailable: %s", type(exc).__name__)
            return None


def train(base: str, output: Path, steps: int, seed: int, four_bit: bool = False) -> None:
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from torch.nn.utils.rnn import pad_sequence
    from transformers import Trainer, TrainingArguments, set_seed

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("LoRA training requires a CUDA GPU with bfloat16 support.")
    if output.is_dir() and any(output.iterdir()):
        raise ValueError(f"Choose an empty training directory: {output}")
    set_seed(seed)
    tokenizer, model = _load_model(base, "cuda", four_bit=four_bit)
    if four_bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    ))
    rows = make_dataset("train", seed)
    dataset = [training_sequence(tokenizer, row) for row in rows]

    def collate(examples):
        inputs = [torch.tensor(item["input_ids"]) for item in examples]
        labels = [torch.tensor(item["labels"]) for item in examples]
        return {
            "input_ids": pad_sequence(inputs, batch_first=True, padding_value=tokenizer.pad_token_id),
            "attention_mask": pad_sequence([torch.ones_like(item) for item in inputs], batch_first=True),
            "labels": pad_sequence(labels, batch_first=True, padding_value=-100),
        }

    trainer = Trainer(
        model=model, train_dataset=dataset, data_collator=collate,
        args=TrainingArguments(
            output_dir=str(output), max_steps=steps, learning_rate=2e-4, seed=seed,
            per_device_train_batch_size=1, gradient_accumulation_steps=4, bf16=True,
            gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
            save_strategy="no", logging_steps=5, disable_tqdm=True, report_to="none",
        ),
    )
    result = trainer.train()
    model.save_pretrained(output, safe_serialization=True)
    summary = {
        "base": base, "seed": seed, "four_bit": four_bit, "rows": len(rows), "optimizer_steps": result.global_step,
        "loss": result.training_loss, "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20),
        "seconds": result.metrics["train_runtime"],
    }
    (output / "training_metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def _actions(plan: TaskPlan) -> list[tuple[str, dict]]:
    return [(step.tool, {key: value.casefold() for key, value in step.arguments.items()}) for step in plan.steps]


def _measure(tokenizer, model, rows: list[dict]) -> dict:
    totals = Counter()
    latencies = []
    by_kind: dict[str, Counter] = {}
    _generate(tokenizer, model, PLANNER_SYSTEM, rows[0]["input"])
    for row in rows:
        started = perf_counter()
        text = _generate(tokenizer, model, PLANNER_SYSTEM, row["input"])
        latencies.append((perf_counter() - started) * 1000)
        decoded = _decode_json(text)
        expected = TaskPlan.model_validate(row["plan"])
        predicted = parse_plan(decoded, row["question"], documents_enabled=True)
        scope = by_kind.setdefault(row["kind"], Counter())
        scope["cases"] += 1
        totals["json"] += decoded is not None
        if predicted is None:
            continue
        totals["valid"] += 1
        clarify = bool(predicted.missing_information.strip())
        scope["clarified"] += clarify
        decision = (
            predicted.task_type == expected.task_type
            and predicted.requires_approval == expected.requires_approval
            and clarify == bool(expected.missing_information)
        )
        tools = [step.tool for step in predicted.steps] == [step.tool for step in expected.steps]
        if decision and tools:
            totals["intent_and_tool"] += 1
        if decision and tools and _actions(predicted) == _actions(expected):
            missing = expected.missing_information
            field = "比较对象" if "比较" in missing else "起点" if "起点" in missing else "终点"
            if not missing or field in predicted.missing_information:
                totals["exact_actions"] += 1
                scope["exact_actions"] += 1
    return {
        "cases": len(rows), "json": totals["json"], "valid": totals["valid"],
        "intent_and_tool": totals["intent_and_tool"], "exact_actions": totals["exact_actions"],
        "p50_ms": round(median(latencies)), "p95_ms": round(sorted(latencies)[math.ceil(len(rows) * 0.95) - 1]),
        "by_intent": {kind: dict(counts) for kind, counts in by_kind.items()},
    }


def evaluate(base: str, adapter: str, output: Path, seed: int, four_bit: bool = False) -> None:
    tokenizer, model = _load_model(base, "cuda", adapter, four_bit)
    model.eval()
    rows = make_dataset("test", seed)
    with model.disable_adapter():
        baseline = _measure(tokenizer, model, rows)
    tuned = _measure(tokenizer, model, rows)
    results = {
        "data": "synthetic_entity_and_template_holdout", "seed": seed, "four_bit": four_bit,
        "baseline": baseline, "lora": tuned,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate the Qwen3 AgriReg planner")
    commands = parser.add_subparsers(dest="command", required=True)
    data = commands.add_parser("data")
    data.add_argument("--output", type=Path, required=True)
    fit = commands.add_parser("train")
    fit.add_argument("--base", default=BASE_MODEL)
    fit.add_argument("--output", type=Path, required=True)
    fit.add_argument("--steps", type=int, default=64)
    check = commands.add_parser("evaluate")
    check.add_argument("--base", default=BASE_MODEL)
    check.add_argument("--adapter", required=True)
    check.add_argument("--output", type=Path, required=True)
    for command in (data, fit, check):
        command.add_argument("--seed", type=int, default=42)
    for command in (fit, check):
        command.add_argument("--four-bit", action="store_true")
    args = parser.parse_args()
    if args.command == "data":
        args.output.mkdir(parents=True, exist_ok=True)
        for split in ("train", "test"):
            rows = make_dataset(split, args.seed)
            with (args.output / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{split}: {len(rows)}")
    elif args.command == "train":
        if args.steps < 1:
            parser.error("--steps must be positive.")
        train(args.base, args.output, args.steps, args.seed, args.four_bit)
    else:
        evaluate(args.base, args.adapter, args.output, args.seed, args.four_bit)


if __name__ == "__main__":
    main()
