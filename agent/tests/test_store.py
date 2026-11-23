from agrireg_agent.store import RunStore


def test_thread_run_and_event_persist(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    thread = store.create_thread("新分析任务")
    run = store.create_run(thread["id"], "比较两个有效成分", True)
    store.append_event(run["id"], "tool_completed", "图谱检索", "完成", {"count": 2})

    restored = store.get_run(run["id"], thread["id"])
    assert restored["requireApproval"] is True
    assert restored["events"][-1]["payload"] == {"count": 2}
    assert store.get_thread(thread["id"])["title"] == "比较两个有效成分"

def test_planning_context_keeps_recent_raw_and_older_entities(tmp_path):
    from agrireg_agent.planner import fallback_plan

    store = RunStore(tmp_path / "context.sqlite3")
    thread_id = store.create_thread("测试上下文")["id"]
    other_id = store.create_thread("另一线程")["id"]
    other = store.create_run(other_id, "另一线程的独立问题", False)
    store.update_run(other["id"], "completed")
    for term in ("EntityA", "EntityB", "EntityC", "EntityD", "EntityE"):
        question = f"查询 '{term}' 的图谱关系"
        run = store.create_run(thread_id, question, False)
        store.append_event(run["id"], "plan_ready", "计划", "", {"plan": fallback_plan(question).model_dump()})
        store.append_event(run["id"], "evidence_verified", "证据", "", {"evidence": [{"title": term}]})
        store.update_run(run["id"], "completed")
    followup = store.create_run(thread_id, "它的登记证呢？", False)

    context = store.planning_context(followup["id"], thread_id)

    assert context["summary"]["entities"] == ["EntityB", "EntityA"]
    assert [turn["entities"] for turn in context["recent"]] == [["EntityC"], ["EntityD"], ["EntityE"]]
    assert "EntityA" not in str(context["recent"])
    assert "另一线程的独立问题" not in str(context)
