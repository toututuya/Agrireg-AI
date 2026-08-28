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

