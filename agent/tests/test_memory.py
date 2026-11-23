from datetime import datetime, timedelta, timezone

import pytest

from agrireg_agent.memory import PROMPT_MEMORY_CHARS, parse_memory_command, procedure_results, utc_timestamp
from agrireg_agent.planner import build_plan, followup_steps, resolve_context
from agrireg_agent.store import RunStore
from agrireg_agent.task_queue import CLARIFICATION_SEPARATOR


def ask_memory(store, thread, question):
    run = store.create_run(thread, question, False)
    command = parse_memory_command(question)
    assert command is not None
    store.answer_memory(run["id"], command)
    store.answer_memory(run["id"], command)
    result = store.get_run(run["id"])
    assert result["status"] == "completed"
    assert sum(event["kind"] == "memory_answered" for event in result["events"]) == 1
    return result["report"]


def test_slot_recall_uses_valid_time_and_record_time_independently(tmp_path, monkeypatch):
    clock = datetime(2026, 6, 1, 7, tzinfo=timezone.utc)
    monkeypatch.setattr("agrireg_agent.store.utc_now", lambda: utc_timestamp(clock))
    store = RunStore(tmp_path / "memory.sqlite3")
    thread = store.create_thread("登记号更正")["id"]
    other = store.create_thread("其他会话")["id"]
    assert "00A657-62" in ask_memory(store, thread, "记住登记号 00A657-62 从 2026-05-01 起")
    clock += timedelta(days=2)
    assert "4387-901" in ask_memory(store, thread, "更正登记号为 4387-901 从 2026-05-16 起")
    assert "4387-901" in ask_memory(store, thread, "记住的登记号是什么？")
    assert "00A657-62" in ask_memory(store, thread, "截至 2026-05-15 记住的登记号是什么")
    historical = ask_memory(store, thread, "按 2026-06-02 当时已知，截至 2026-05-30 记住的登记号是什么")
    assert "00A657-62" in historical and "4387-901" not in historical
    assert "没有已生效" in ask_memory(store, other, "记住的登记号是什么")
    assert "有效的生效日期" in ask_memory(store, thread, "记住登记号 4387-901 从 2026-02-30 起")


def test_late_episode_cannot_change_concurrent_run_context(tmp_path, monkeypatch):
    clock = datetime(2026, 6, 1, tzinfo=timezone.utc)
    monkeypatch.setattr("agrireg_agent.store.utc_now", lambda: utc_timestamp(clock))
    store = RunStore(tmp_path / "memory.sqlite3")
    thread = store.create_thread("并行任务")["id"]
    earlier = store.create_run(thread, "叶锈病是什么", False)
    clock += timedelta(seconds=1)
    current = store.create_run(thread, "它是什么", False)
    clock += timedelta(seconds=1)
    store.update_run(earlier["id"], "completed", episode={"reference": "leaf rust", "entities": ["leaf rust"]})
    assert store.planning_context(current["id"], thread) == {}
    clock += timedelta(seconds=1)
    later = store.create_run(thread, "它是什么", False)
    assert store.planning_context(later["id"], thread)["reference"] == "leaf rust"
    other = store.create_thread("独立会话")["id"]
    with pytest.raises(KeyError):
        store.planning_context(later["id"], other)


def test_history_older_than_window_is_available_without_model(tmp_path, monkeypatch):
    import json

    clock = datetime(2026, 6, 1, tzinfo=timezone.utc)
    monkeypatch.setattr("agrireg_agent.store.utc_now", lambda: utc_timestamp(clock))
    store = RunStore(tmp_path / "memory.sqlite3")
    thread = store.create_thread("长会话")["id"]
    for index in range(52):
        clock += timedelta(seconds=1)
        entity = f"实体{index:02d}"
        question = "查询苹果登记资料" if index == 0 else f"查询{entity}" + "较长的原始问题" * 60
        run = store.create_run(thread, question, False)
        store.update_run(run["id"], "completed", report=f"结论{index}", episode={
            "reference": entity, "entities": [entity], "type": "fact_check",
        })
    clock += timedelta(seconds=1)
    run = store.create_run(thread, "还是查这个", False)
    context = store.planning_context(run["id"], thread)
    window = {key: context[key] for key in ("recent", "summary")}
    assert len(context["recent"]) == 3
    assert len(json.dumps(window, ensure_ascii=False, separators=(",", ":"))) <= PROMPT_MEMORY_CHARS
    assert "苹果" not in str(window)
    old = ask_memory(store, thread, "回顾第1轮")
    assert "历史记录" in old and "查询苹果登记资料" in old and "结论0" in old
    assert "结论0" in ask_memory(store, thread, "回顾「苹果」")
    assert "结论51" in ask_memory(store, thread, "回顾上一轮")


def test_current_target_overrules_thread_history_and_real_ambiguity_asks():
    class RecordingModel:
        def __init__(self):
            self.questions = []

        def json_completion(self, _system, user):
            self.questions.append(user)
            return None

    model = RecordingModel()
    old = {"slots": {"登记号": "00A657-62"}, "recent": [{"question": "改查苹果"}], "reference": "leaf rust"}
    explicit = build_plan("不用记住的登记号，改查登记号 4387-901 的资料", False, model, True, old)
    assert explicit.steps[0].arguments["registration_number"] == "4387-901"
    assert "改查苹果" not in model.questions[-1] and "00A657-62" not in model.questions[-1]
    ambiguous = "查记住的登记号和登记号 4387-901 的资料"
    blocked = build_plan(ambiguous, False, model, True, old)
    assert blocked.missing_information and not blocked.steps and len(model.questions) == 1
    clarified = ambiguous + CLARIFICATION_SEPARATOR + "我指的是 00A657-62"
    assert build_plan(clarified, False, model, True, old).steps[0].arguments["registration_number"] == "00A657-62"
    recall = build_plan("用记住的登记号查登记资料", False, model, True, old)
    assert recall.steps[0].arguments["registration_number"] == "00A657-62"
    new_thread = build_plan("它是什么", False, model, True, {})
    assert new_thread.missing_information and not new_thread.steps
    assert resolve_context("它是什么", old) == ("leaf rust是什么", "")
    assert resolve_context("该产品的登记资料", old | {"reference_kind": "Disease"})[1]


def test_procedural_memory_only_prioritizes_allowed_recovery_tools():
    primary = {
        "step": {"id": "path", "title": "查路径", "tool": "find_relation_path", "arguments": {"source": "A", "target": "B"}},
        "outcome": "empty", "task_id": 1,
    }
    recovery = {
        "step": {"id": "task-1-followup:replan-1", "tool": "search_documents"}, "outcome": "ok", "task_id": 1,
    }
    learned = procedure_results([primary, recovery])
    assert learned == {"find_relation_path/empty/search_documents": True}
    assert followup_steps("查路径", [primary], True, 1, learned)[0].tool == "search_documents"
    assert followup_steps("查路径", [primary], False, 1, learned)[0].tool == "search_entity"
    assert procedure_results([primary, recovery | {"outcome": "empty"}]) == {
        "find_relation_path/empty/search_documents": False,
    }
