from __future__ import annotations

import argparse
import json
import logging
import math
import unicodedata
from collections import Counter
from collections.abc import Iterable
from functools import cached_property
from itertools import combinations
from pathlib import Path
from statistics import median
from threading import Lock
from time import perf_counter
from typing import Any

from .models import TaskPlan
from .planner import PLANNER_SYSTEM, parse_plan
from .planner_data import (
    dataset_fingerprint,
    default_clarification_terms,
    ensure_disjoint,
    make_dataset,
    read_dataset,
)


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
    answer = _plan_text(row) + tokenizer.eos_token
    target = tokenizer.encode(answer, add_special_tokens=False)
    if len(prefix) + len(target) > MAX_SEQUENCE:
        raise ValueError(f"Training row {row['id']} exceeds {MAX_SEQUENCE} tokens.")
    return {"input_ids": prefix + target, "labels": [-100] * len(prefix) + target}


def _plan_text(row: dict) -> str:
    return json.dumps(row["plan"], ensure_ascii=False, separators=(",", ":"))


def _write_jsonl(output: Path, rows: Iterable[dict]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _export_messages(dataset: Path, output: Path) -> None:
    if dataset.resolve() == output.resolve():
        raise ValueError("Use a different output path to preserve the labeled dataset.")
    rows = read_dataset(dataset)
    _write_jsonl(output, (
        {"messages": [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": row["input"]},
            {"role": "assistant", "content": _plan_text(row)},
        ]}
        for row in rows
    ))
    print(f"Exported {len(rows)} planning examples.")


def _load_model(base: str, device: str, adapter: str = "", four_bit: bool = False) -> tuple:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(base)
    dtype = torch.float32 if device == "cpu" else torch.bfloat16
    options = {"torch_dtype": dtype, "use_safetensors": True, "attn_implementation": "sdpa"}
    if four_bit:
        target = torch.device("cuda", torch.cuda.current_device()) if device == "cuda" else torch.device(device)
        options["device_map"] = {"": target}
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
    model = AutoModelForCausalLM.from_pretrained(base, **options)
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter)
    return tokenizer, model if four_bit else model.to(device)


def _generate_batch(tokenizer, model, system: str, users: list[str]) -> list[str]:
    import torch
    from transformers import GenerationConfig

    prompts = [_prompt(tokenizer, system, user) for user in users]
    width = max(map(len, prompts))
    inputs = torch.tensor([[tokenizer.pad_token_id] * (width - len(prompt)) + prompt for prompt in prompts],
                          device=model.device)
    mask = torch.tensor([[0] * (width - len(prompt)) + [1] * len(prompt) for prompt in prompts],
                        device=model.device)
    generation = GenerationConfig.from_model_config(model.config)
    generation.max_new_tokens = MAX_GENERATION
    generation.pad_token_id = tokenizer.pad_token_id
    with torch.inference_mode():
        output = model.generate(
            input_ids=inputs, attention_mask=mask, generation_config=generation,
            use_model_defaults=False, do_sample=False,
        )
    return [text.strip() for text in tokenizer.batch_decode(output[:, width:], skip_special_tokens=True)]


def _generate(tokenizer, model, system: str, user: str) -> str:
    return _generate_batch(tokenizer, model, system, [user])[0]


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


def train(
    base: str, output: Path, steps: int, seed: int, four_bit: bool = False, *, dataset: Path | None = None,
) -> None:
    rows = read_dataset(dataset) if dataset is not None else make_dataset("train", seed)
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
    training_rows = [training_sequence(tokenizer, row) for row in rows]

    def collate(examples):
        inputs = [torch.tensor(item["input_ids"]) for item in examples]
        labels = [torch.tensor(item["labels"]) for item in examples]
        return {
            "input_ids": pad_sequence(inputs, batch_first=True, padding_value=tokenizer.pad_token_id),
            "attention_mask": pad_sequence([torch.ones_like(item) for item in inputs], batch_first=True),
            "labels": pad_sequence(labels, batch_first=True, padding_value=-100),
        }

    trainer = Trainer(
        model=model, train_dataset=training_rows, data_collator=collate,
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
        "dataset_sha256": dataset_fingerprint(rows),
        "loss": result.training_loss, "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20),
        "seconds": result.metrics["train_runtime"],
    }
    (output / "training_metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def _actions(plan: TaskPlan, *, include_document_query: bool = True) -> list[tuple[str, dict]]:
    actions = []
    for step in plan.steps:
        arguments = {key: value.casefold() for key, value in step.arguments.items()}
        if step.tool == "search_documents" and not include_document_query:
            arguments.pop("query", None)
            registration = arguments.pop("registration_number", "")
            if registration:
                arguments["registration_number"] = unicodedata.normalize("NFKC", registration)
        actions.append((step.tool, arguments))
    return actions


def _measure(tokenizer, model, rows: list[dict]) -> dict:
    latencies = []
    first_per_kind = {}
    for row in rows:
        first_per_kind.setdefault(row["kind"], row["id"])
    latency_ids = set(first_per_kind.values())
    texts: dict[str, str] = {}
    _generate(tokenizer, model, PLANNER_SYSTEM, rows[0]["input"])
    for row in rows:
        if row["id"] not in latency_ids:
            continue
        started = perf_counter()
        texts[row["id"]] = _generate(tokenizer, model, PLANNER_SYSTEM, row["input"])
        latencies.append((perf_counter() - started) * 1000)
    remaining = [row for row in rows if row["id"] not in latency_ids]
    for start in range(0, len(remaining), 4):
        batch = remaining[start:start + 4]
        generations = _generate_batch(tokenizer, model, PLANNER_SYSTEM, [row["input"] for row in batch])
        texts.update((row["id"], text) for row, text in zip(batch, generations, strict=True))
    return _score_plans(rows, texts) | {
        "latency_cases": len(latencies),
        "p50_ms": round(median(latencies)), "p95_ms": round(sorted(latencies)[math.ceil(len(latencies) * 0.95) - 1]),
    }


def _score_plans(rows: list[dict], texts: dict[str, str]) -> dict:
    totals = Counter()
    by_kind: dict[str, Counter] = {}
    missing_params = {"cases": 0, "proposed_call": 0, "matched_clarification_without_call": 0}
    ready = {"cases": 0, "unnecessary_clarification": 0, "matched_critical_actions": 0}
    for row in rows:
        decoded = _decode_json(texts[row["id"]])
        expected = TaskPlan.model_validate(row["plan"])
        predicted = parse_plan(decoded, row["question"], documents_enabled=row.get("documents_enabled", True))
        needs_clarification = bool(expected.missing_information.strip())
        proposed_steps = (decoded or {}).get("steps")
        proposed_call = isinstance(proposed_steps, list) and bool(proposed_steps)
        if needs_clarification:
            missing_params["cases"] += 1
            missing_params["proposed_call"] += proposed_call
        else:
            ready["cases"] += 1
        scope = by_kind.setdefault(row["kind"], Counter())
        scope["cases"] += 1
        totals["json"] += decoded is not None
        if predicted is None:
            continue
        totals["valid"] += 1
        clarify = bool(predicted.missing_information.strip())
        scope["clarified"] += clarify
        ready["unnecessary_clarification"] += clarify and not needs_clarification
        decision = (
            predicted.task_type == expected.task_type
            and predicted.requires_approval == expected.requires_approval
            and clarify == needs_clarification
        )
        tools = [step.tool for step in predicted.steps] == [step.tool for step in expected.steps]
        if not (decision and tools):
            continue
        totals["intent_and_tool"] += 1
        terms = row.get("clarification_terms")
        if terms is None:
            terms = default_clarification_terms(expected.missing_information)
        matches_terms = all(term.casefold() in predicted.missing_information.casefold() for term in terms)
        if matches_terms and _actions(predicted) == _actions(expected):
            totals["exact_actions"] += 1
            scope["exact_actions"] += 1
        if needs_clarification:
            missing_params["matched_clarification_without_call"] += matches_terms and not proposed_call
        else:
            ready["matched_critical_actions"] += (
                _actions(predicted, include_document_query=False) == _actions(expected, include_document_query=False)
            )
    return {
        "cases": len(rows), "json": totals["json"], "valid": totals["valid"],
        "intent_and_tool": totals["intent_and_tool"], "exact_actions": totals["exact_actions"],
        "decision_checks": {"missing_parameters": missing_params, "ready": ready},
        "by_intent": {kind: dict(counts) for kind, counts in by_kind.items()},
    }


def evaluate(
    base: str, adapter: str, output: Path, seed: int, four_bit: bool = False, *, dataset: Path | None = None,
) -> None:
    rows = read_dataset(dataset) if dataset is not None else make_dataset("test", seed)
    if dataset is not None and dataset.resolve() == output.resolve():
        raise ValueError("Use a different output path to preserve the labeled dataset.")
    tokenizer, model = _load_model(base, "cuda", adapter, four_bit)
    model.eval()
    print(f"Evaluating base model on {len(rows)} held-out cases.", flush=True)
    with model.disable_adapter():
        baseline = _measure(tokenizer, model, rows)
    print(f"Evaluating LoRA adapter on the same {len(rows)} cases.", flush=True)
    tuned = _measure(tokenizer, model, rows)
    results = {
        "data": "labeled_jsonl" if dataset is not None else "synthetic_entity_and_template_holdout",
        "dataset_sha256": dataset_fingerprint(rows), "seed": seed, "four_bit": four_bit, "decoding": "greedy",
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
    preflight = commands.add_parser("check-data", help="Validate labels and check overlap across data splits")
    preflight.add_argument("--train", type=Path, required=True)
    preflight.add_argument("--dev", type=Path)
    preflight.add_argument("--test", type=Path, required=True)
    preflight.add_argument("--base", help="Optionally validate token lengths with an existing Qwen3 tokenizer")
    export = commands.add_parser("export-messages", help="Export labeled examples to messages JSONL")
    export.add_argument("--dataset", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    for command in (data, fit, check):
        command.add_argument("--seed", type=int, default=42)
    for command in (fit, check):
        command.add_argument("--four-bit", action="store_true")
        command.add_argument("--dataset", type=Path, help="Use a labeled JSONL file")
    args = parser.parse_args()
    try:
        if args.command == "data":
            for split in ("train", "test"):
                rows = make_dataset(split, args.seed)
                _write_jsonl(args.output / f"{split}.jsonl", rows)
                print(f"{split}: {len(rows)}")
        elif args.command == "check-data":
            _check_data(args.train, args.test, args.base, dev_path=args.dev)
        elif args.command == "export-messages":
            _export_messages(args.dataset, args.output)
        elif args.command == "train":
            if args.steps < 1:
                parser.error("--steps must be positive.")
            train(args.base, args.output, args.steps, args.seed, args.four_bit, dataset=args.dataset)
        else:
            evaluate(args.base, args.adapter, args.output, args.seed, args.four_bit, dataset=args.dataset)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


def _check_data(train_path: Path, test_path: Path, base: str | None, *, dev_path: Path | None = None) -> None:
    splits = {"train": read_dataset(train_path), "test": read_dataset(test_path)}
    if dev_path is not None:
        splits["dev"] = read_dataset(dev_path)
    for (left_name, left), (right_name, right) in combinations(splits.items(), 2):
        try:
            ensure_disjoint(left, right)
        except ValueError as exc:
            raise ValueError(f"{left_name}/{right_name}: {exc}") from exc
    if base:
        try:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(base)
            for rows in splits.values():
                for row in rows:
                    training_sequence(tokenizer, row)
        except ImportError as exc:
            raise ValueError('Install the tokenizer extra with pip install -e ".[tokenizer]".') from exc
    print(json.dumps({
        **{name: len(rows) for name, rows in splits.items()},
        "tokenizer_checked": bool(base),
        **{f"{name}_sha256": dataset_fingerprint(rows) for name, rows in splits.items()},
    }, indent=2))


if __name__ == "__main__":
    main()
