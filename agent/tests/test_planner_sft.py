import json

from agrireg_agent import planner_sft
from agrireg_agent.models import TaskPlan
from agrireg_agent.planner import parse_plan
from agrireg_agent.planner_data import make_dataset
from agrireg_agent.planner_sft import LocalQwenPlanner, training_sequence


def test_sft_data_has_entity_holdout_and_valid_targets():
    train, heldout = make_dataset("train"), make_dataset("test")
    assert len(train) == 336
    assert len(heldout) == 42
    assert set(row["question"] for row in train).isdisjoint(row["question"] for row in heldout)
    assert {entity for row in train for entity in row["plan"]["entities"]}.isdisjoint(
        entity for row in heldout for entity in row["plan"]["entities"]
    )
    for row in train + heldout:
        plan = parse_plan(row["plan"], row["question"], documents_enabled=True)
        assert isinstance(plan, TaskPlan)
        if row["kind"].startswith("missing_"):
            assert plan.missing_information and not plan.steps


def test_sft_loss_masks_prompt_and_keeps_assistant_eos():
    class StubTokenizer:
        eos_token = "<END>"

        def apply_chat_template(self, messages, **options):
            assert messages[0]["role"] == "system"
            assert options["add_generation_prompt"] and not options["enable_thinking"]
            return [1, 2]

        def encode(self, answer, **options):
            assert answer.endswith(self.eos_token) and not options["add_special_tokens"]
            return [3, 4, 5]

    result = training_sequence(StubTokenizer(), make_dataset("train")[0])
    assert result == {"input_ids": [1, 2, 3, 4, 5], "labels": [-100, -100, 3, 4, 5]}


def test_qwen_without_adapter_defers_to_fallback():
    planner = LocalQwenPlanner("base", "", "cpu")
    assert planner.json_completion("system", "request") is None


def test_heldout_metrics_use_latency_sample_count(monkeypatch):
    rows = make_dataset("test")
    answers = {row["input"]: json.dumps(row["plan"], ensure_ascii=False) for row in rows}
    monkeypatch.setattr(planner_sft, "_generate", lambda tokenizer, model, system, user: answers[user])
    monkeypatch.setattr(
        planner_sft, "_generate_batch", lambda tokenizer, model, system, users: [answers[user] for user in users],
    )

    result = planner_sft._measure(None, None, rows)

    assert result["exact_actions"] == result["cases"] == 42
    assert result["latency_cases"] == 7
    assert 0 <= result["p50_ms"] <= result["p95_ms"]
