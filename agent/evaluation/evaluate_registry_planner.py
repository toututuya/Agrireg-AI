"""Select a registry planner on development data and compare it on frozen test fixtures."""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from fractions import Fraction
import json
from pathlib import Path
from time import perf_counter

from agrireg_agent.models import TaskPlan
from agrireg_agent.planner import PLANNER_SYSTEM, fallback_plan, parse_plan, planning_input
from agrireg_agent.planner_data import dataset_fingerprint, read_dataset
from agrireg_agent.planner_sft import BASE_MODEL, _decode_json, _generate_batch, _load_model, _score_plans, _write_jsonl


STEPS_BY_EPOCH = {1: 175, 2: 350, 3: 525}
SELECTION = "max_mean_of_ready_critical_action_and_correct_non_call_clarification_rates; fewer_missing_calls; earlier_epoch"
Predict = Callable[[list[dict]], dict[str, str]]


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def frozen_split(data: Path, split: str) -> tuple[list[dict], str]:
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    rows = read_dataset(data / f"{split}.jsonl")
    digest = dataset_fingerprint(rows)
    if digest != manifest["splits"][split]["sha256"]:
        raise ValueError(f"{split} does not match the frozen data manifest.")
    return rows, digest


def generations(tokenizer, model, rows: list[dict], batch_size: int) -> dict[str, str]:
    texts = {}
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        replies = _generate_batch(tokenizer, model, PLANNER_SYSTEM, [row["input"] for row in batch])
        texts.update((row["id"], text) for row, text in zip(batch, replies, strict=True))
    return texts


def balance(scores: dict) -> Fraction:
    decisions = scores["decision_checks"]
    ready, missing = decisions["ready"], decisions["missing_parameters"]
    return (Fraction(ready["matched_critical_actions"], ready["cases"])
            + Fraction(missing["matched_clarification_without_call"], missing["cases"])) / 2


def choose_epoch(results: dict[int, dict]) -> int:
    return max(results, key=lambda epoch: (
        balance(results[epoch]), -results[epoch]["decision_checks"]["missing_parameters"]["proposed_call"], -epoch,
    ))


def score_development(base: str, checkpoints: dict[int, Path], dev: list[dict], four_bit: bool, batch_size: int):
    if batch_size < 1:
        raise ValueError("Batch size must be positive.")
    first_epoch = min(checkpoints)
    tokenizer, model = _load_model(base, "cuda", str(checkpoints[first_epoch]), four_bit)
    adapter_names = {first_epoch: "default"}
    results = {}
    for epoch, path in sorted(checkpoints.items()):
        if epoch != first_epoch:
            adapter_names[epoch] = f"epoch_{epoch}"
            model.load_adapter(str(path), adapter_names[epoch], is_trainable=False)
        model.set_adapter(adapter_names[epoch])
        model.eval()
        print(f"Dev epoch {epoch}: {len(dev)} examples", flush=True)
        metrics = _score_plans(dev, generations(tokenizer, model, dev, batch_size))
        results[epoch] = metrics | {"balanced_score": float(balance(metrics))}
    return tokenizer, model, adapter_names, results


def compare_development(
    data: Path, output: Path, base: str, checkpoints: dict[int, Path], four_bit: bool, batch_size: int,
) -> None:
    dev, digest = frozen_split(data, "dev")
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    _, _, _, results = score_development(base, checkpoints, dev, four_bit, batch_size)
    selected = choose_epoch(results)
    write_json(output / "development.json", {
        "dataset_sha256": digest, "selected_epoch": selected, "epochs": results, "selection": SELECTION,
        "four_bit": four_bit, "decoding": "greedy", "batch_size": batch_size,
        "wall_seconds": round(perf_counter() - started, 3),
    })
    print(f"Selected epoch {selected} on dev. Results saved under {output}", flush=True)


def step_evidence(tool: str, args: dict[str, str], snapshot: dict) -> set[str]:
    records = snapshot["records"]
    if tool == "search_entity":
        key = args["keyword"].upper()
        return {key} if key in records else set()
    if tool == "compare_entities":
        pair = {args["left"].upper(), args["right"].upper()}
        return pair if pair <= records.keys() else set()
    if tool == "find_relation_path":
        source = args["source"].upper()
        match = records.get(source)
        return {source} if match and match["holder"].casefold() == args["target"].casefold() else set()
    if tool == "search_documents":
        key = args.get("registration_number", "").upper()
        if key:
            return {key} if key in records else set()
        query = args["query"].casefold()
        return {
            registration for registration, record in records.items()
            if record["product"].casefold() in query and record["holder"].casefold() in query
        }
    if tool == "external_substance_lookup":
        return {
            f"pubchem:{record['cid']}" for name, record in snapshot["pubchem"].items()
            if name.casefold() == args["name"].casefold()
        }
    return set()


def snapshot_match(row: dict, text: str, expected: list[str], snapshot: dict) -> bool:
    plan = parse_plan(_decode_json(text), row["question"], row["documents_enabled"])
    if plan is None or not plan.steps:
        return False
    evidence = [step_evidence(step.tool, step.arguments, snapshot) for step in plan.steps]
    return all(evidence) and set(expected) <= set.union(*evidence)


def load_fixtures(data: Path, test: list[dict]) -> tuple[dict, dict, list[dict], dict]:
    snapshot = json.loads((data / "registry_snapshot.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (data / "test_replay.jsonl").read_text(encoding="utf-8").splitlines()]
    digests = {
        "registry_snapshot_sha256": dataset_fingerprint([snapshot]),
        "test_replay_sha256": dataset_fingerprint(rows),
    }
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    if digests != manifest["fixtures"]:
        raise ValueError("Registry or replay fixtures do not match the frozen manifest.")
    replay = {row["id"]: row for row in rows}
    if len(rows) != len(replay) or replay.keys() != {row["id"] for row in test}:
        raise ValueError("Frozen replay fixtures and test IDs must match one-to-one.")
    recovered = []
    for row in test:
        missing = bool(row["plan"]["missing_information"])
        fixture = replay[row["id"]]
        if fixture.keys() != ({"id", "evidence", "reply", "recovered_plan"} if missing else {"id", "evidence"}):
            raise ValueError(f"Unexpected fixture fields for {row['id']}.")
        executable = row
        if missing:
            reply = fixture["reply"].strip()[:200]
            question = f"{row['question']}；补充信息：{reply}"
            plan = TaskPlan.model_validate(fixture["recovered_plan"])
            if not reply or plan.missing_information or not plan.steps:
                raise ValueError(f"Fixture does not resolve {row['id']}.")
            executable = row | {
                "question": question, "input": planning_input(question, row["documents_enabled"]),
                "plan": plan.model_dump(mode="json"), "clarification_terms": [],
            }
            recovered.append(executable)
        if not fixture["evidence"] or not snapshot_match(
            executable, json.dumps(executable["plan"]), fixture["evidence"], snapshot,
        ):
            raise ValueError(f"Gold plan cannot retrieve the frozen evidence for {row['id']}.")
    return snapshot, replay, recovered, digests


def rule_predictions(rows: list[dict]) -> dict[str, str]:
    return {
        row["id"]: fallback_plan(row["question"], documents_enabled=row["documents_enabled"]).model_dump_json()
        for row in rows
    }


def score_test(
    test: list[dict], recovered: list[dict], replay: dict, snapshot: dict, predict: Predict,
) -> tuple[dict, list[dict]]:
    started = perf_counter()
    first = predict(test)
    second = predict(recovered)
    by_kind: dict[str, Counter] = {}
    cases = []
    ready_hits = two_turn_hits = resolved_hits = 0
    second_rows = {row["id"]: row for row in recovered}
    for row in test:
        key = row["id"]
        kind = by_kind.setdefault(row["kind"], Counter())
        decisions = _score_plans([row], first)["decision_checks"]
        expected = replay[key]["evidence"]
        case = {"id": key, "kind": row["kind"], "prediction": first[key]}
        kind["cases"] += 1
        if key in second_rows:
            first_ok = bool(decisions["missing_parameters"]["matched_clarification_without_call"])
            proposed = bool(decisions["missing_parameters"]["proposed_call"])
            replay_row = second_rows[key]
            actions = _score_plans([replay_row], second)["decision_checks"]["ready"]["matched_critical_actions"]
            resolved = bool(actions) and snapshot_match(replay_row, second[key], expected, snapshot)
            two_turn = first_ok and resolved
            kind["matched_clarification_without_call"] += first_ok
            kind["proposed_call"] += proposed
            kind["after_expected_reply"] += resolved
            kind["two_turn_success"] += two_turn
            resolved_hits += resolved
            two_turn_hits += two_turn
            case.update(clarify=first_ok, proposed_call=proposed, resumed_prediction=second[key],
                        resolved=resolved, two_turn=two_turn)
        else:
            actions = bool(decisions["ready"]["matched_critical_actions"])
            success = actions and snapshot_match(row, first[key], expected, snapshot)
            kind["matched_critical_actions"] += actions
            kind["snapshot_success"] += success
            ready_hits += success
            case.update(critical_actions=actions, snapshot_success=success)
        cases.append(case)
    metrics = _score_plans(test, first) | {
        "snapshot_ready": {"success": ready_hits, "cases": len(test) - len(recovered)},
        "two_turn": {"success": two_turn_hits, "after_expected_reply": resolved_hits, "cases": len(recovered)},
        "snapshot_by_kind": {key: dict(counts) for key, counts in by_kind.items()},
        "wall_seconds": round(perf_counter() - started, 3),
    }
    return metrics, cases


def evaluate(data: Path, run: Path, output: Path, base: str, four_bit: bool, batch_size: int) -> None:
    train_metrics = json.loads((run / "training_metrics.json").read_text(encoding="utf-8"))
    train_rows, train_digest = frozen_split(data, "train")
    if (
        len(train_rows) != 4 * STEPS_BY_EPOCH[1] or train_metrics["dataset_sha256"] != train_digest
        or train_metrics["optimizer_steps"] != STEPS_BY_EPOCH[3] or train_metrics["four_bit"] != four_bit
    ):
        raise ValueError("Training metrics must match the frozen 3-epoch run and its quantization.")
    dev, dev_digest = frozen_split(data, "dev")
    output.mkdir(parents=True, exist_ok=False)
    checkpoints = {epoch: run / f"checkpoint-{step}" for epoch, step in STEPS_BY_EPOCH.items()}
    tokenizer, model, adapter_names, results = score_development(base, checkpoints, dev, four_bit, batch_size)
    for epoch, metrics in results.items():
        metrics["optimizer_steps"] = STEPS_BY_EPOCH[epoch]

    def predict(rows: list[dict]) -> dict[str, str]:
        return generations(tokenizer, model, rows, batch_size)

    selected = choose_epoch(results)
    development = {
        "dataset_sha256": dev_digest, "selected_epoch": selected, "epochs": results,
        "selection": SELECTION,
    }
    write_json(output / "development.json", development)
    print(f"Selected epoch {selected} on dev; opening the test split.", flush=True)

    test, test_digest = frozen_split(data, "test")
    snapshot, replay, recovered, digests = load_fixtures(data, test)
    print(f"Test rule fallback: {len(test)} initial and {len(recovered)} resumed turns", flush=True)
    rules, rule_cases = score_test(test, recovered, replay, snapshot, rule_predictions)
    _write_jsonl(output / "test_rule_predictions.jsonl", rule_cases)
    model.set_adapter(adapter_names[selected])
    print(f"Test Qwen3 base: {len(test)} initial and {len(recovered)} resumed turns", flush=True)
    with model.disable_adapter():
        baseline, baseline_cases = score_test(test, recovered, replay, snapshot, predict)
    _write_jsonl(output / "test_base_predictions.jsonl", baseline_cases)
    print(f"Test Qwen3 LoRA epoch {selected}: {len(test)} initial and {len(recovered)} resumed turns", flush=True)
    tuned, tuned_cases = score_test(test, recovered, replay, snapshot, predict)
    _write_jsonl(output / "test_lora_predictions.jsonl", tuned_cases)
    write_json(output / "test.json", {
        "dataset_sha256": test_digest, "train_sha256": train_digest, "dev_sha256": dev_digest, **digests,
        "selected_epoch": selected, "checkpoint": f"checkpoint-{STEPS_BY_EPOCH[selected]}",
        "seed": train_metrics["seed"], "base": base, "four_bit": four_bit, "decoding": "greedy",
        "batch_size": batch_size, "rule_fallback": rules, "qwen3_base": baseline, "qwen3_lora": tuned,
    })
    print(f"Results saved under {output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", type=Path)
    mode.add_argument("--dev-checkpoint", action="append", nargs=2, metavar=("EPOCH", "ADAPTER"),
                      help="Compare this epoch and local adapter on dev only. Pass at least twice.")
    parser.add_argument("--output", type=Path, help="New evaluation directory. Defaults to RUN/evaluation with --run.")
    parser.add_argument("--base", default=BASE_MODEL)
    parser.add_argument("--four-bit", action="store_true")
    parser.add_argument("--batch-size", type=int, default=12)
    args = parser.parse_args()
    if args.run is not None:
        evaluate(args.data, args.run, args.output or args.run / "evaluation", args.base, args.four_bit, args.batch_size)
    elif args.dev_checkpoint:
        try:
            checkpoints = {int(epoch): Path(path) for epoch, path in args.dev_checkpoint}
        except ValueError:
            parser.error("Each checkpoint epoch must be an integer.")
        if len(checkpoints) < 2 or len(checkpoints) != len(args.dev_checkpoint) or min(checkpoints) < 1:
            parser.error("Provide at least two distinct positive checkpoint epochs.")
        if args.output is None:
            parser.error("--dev-checkpoint requires --output.")
        if any(not (path / "adapter_config.json").is_file() for path in checkpoints.values()):
            parser.error("Each checkpoint must point to a local adapter directory.")
        compare_development(args.data, args.output, args.base, checkpoints, args.four_bit, args.batch_size)
    else:
        test, _ = frozen_split(args.data, "test")
        snapshot, replay, recovered, digests = load_fixtures(args.data, test)
        print(json.dumps({"test": len(test), "recovered": len(recovered), **digests}, indent=2))
