import json
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

from agrireg_agent import planner_sft
from agrireg_agent.planner import PLANNER_SYSTEM
from agrireg_agent.planner_data import dataset_fingerprint, ensure_disjoint, make_dataset, read_dataset


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def example(kind: str) -> dict:
    return next(row for row in make_dataset("train") if row["kind"] == kind)


def test_read_dataset_rebuilds_input_and_checks_runtime_tools(tmp_path):
    row = example("graph")
    row.update(input="incorrect preformatted input", documents_enabled=False)
    path = write_jsonl(tmp_path / "train.jsonl", [row])
    loaded = read_dataset(path)[0]

    assert json.loads(loaded["input"]) == {
        "question": row["question"], "document_search": False, "thread_context": {},
    }
    assert loaded["plan"]["steps"][0]["tool"] == "search_entity"
    doc = example("document")
    doc["documents_enabled"] = False
    with pytest.raises(ValueError, match=r"train\.jsonl:2: .*tool and argument"):
        read_dataset(write_jsonl(path, [row, doc]))


def test_rejects_tool_calls_on_clarification_and_missing_approval(tmp_path):
    example_path = tmp_path / "example.jsonl"
    row = example("graph")
    row["plan"]["missing_information"] = "请补充登记号。"
    with pytest.raises(ValueError, match="empty steps"):
        read_dataset(write_jsonl(example_path, [row]))
    compliance = example("compliance")
    compliance["plan"]["requires_approval"] = False
    with pytest.raises(ValueError, match="requires_approval=true"):
        read_dataset(write_jsonl(example_path, [compliance]))


def test_train_test_rejects_duplicate_normalized_questions(tmp_path):
    train = {"id": "train-entry", "question": "查   Ａ 条目"}
    test = {"id": "test-entry", "question": "查a条目"}
    with pytest.raises(ValueError, match="1 normalized questions"):
        ensure_disjoint([train], [test])
    row = example("graph")
    with pytest.raises(ValueError, match=r"repeat\.jsonl:2: duplicate example id"):
        read_dataset(write_jsonl(tmp_path / "repeat.jsonl", [row, row]))


def test_export_cli_preserves_validated_assistant_plan(tmp_path, monkeypatch):
    path = write_jsonl(tmp_path / "labels.jsonl", [example("missing_path")])
    output = tmp_path / "export" / "messages.jsonl"
    monkeypatch.setattr(sys, "argv", ["planner-sft", "export-messages", "--dataset", str(path), "--output", str(output)])

    planner_sft.main()

    messages = json.loads(output.read_text(encoding="utf-8"))["messages"]
    assert messages[0] == {"role": "system", "content": PLANNER_SYSTEM}
    assert [message["role"] for message in messages] == ["system", "user", "assistant"]
    assert json.loads(messages[2]["content"]) == read_dataset(path)[0]["plan"]


def test_evaluate_cli_passes_labeled_test_file(tmp_path, monkeypatch):
    path = write_jsonl(tmp_path / "holdout.jsonl", [example("graph")])
    output = tmp_path / "scores.json"

    class Model:
        def eval(self):
            pass

        def disable_adapter(self):
            return nullcontext()

    def measure(_tokenizer, _model, rows):
        assert rows == read_dataset(path)
        return {"cases": len(rows)}

    monkeypatch.setattr(planner_sft, "_load_model", lambda *_: (None, Model()))
    monkeypatch.setattr(planner_sft, "_measure", measure)
    monkeypatch.setattr(sys, "argv", [
        "planner-sft", "evaluate", "--adapter", "adapter", "--output", str(output), "--dataset", str(path),
    ])
    planner_sft.main()

    results = json.loads(output.read_text(encoding="utf-8"))
    assert results["data"] == "labeled_jsonl"
    assert results["dataset_sha256"] == dataset_fingerprint(read_dataset(path))
    assert results["baseline"] == results["lora"] == {"cases": 1}
