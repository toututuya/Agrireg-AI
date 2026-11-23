import json
from collections import Counter
from time import monotonic, sleep

import httpx
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from agrireg_agent import api
from agrireg_agent.clients import ControlledTools, DeepSeekClient
from agrireg_agent.config import Settings
from agrireg_agent.graph import build_agent_graph
from agrireg_agent.planner import REGISTRATION
from agrireg_agent.runtime import AgentRuntime
from agrireg_agent.task_queue import split_subtasks


def lookup_payload(registration):
    return {"nodes": [{
        "id": registration, "name": registration, "label": "Registration",
        "properties": {"registrationNumber": registration},
    }], "edges": []}


def run_graph(tmp_path, question, handler, **options):
    settings = Settings(AGENT_DATA_DIR=tmp_path, DEEPSEEK_ENABLED=False)
    graph = build_agent_graph(
        ControlledTools(settings, transport=httpx.MockTransport(handler)),
        DeepSeekClient(settings), InMemorySaver(), **options,
    )
    return graph.invoke(
        {"question": question},
        {"configurable": {"thread_id": "resilience"}, "recursion_limit": 250},
    )


def test_twelve_step_run_retries_only_the_timed_out_step(tmp_path, monkeypatch):
    calls = Counter()
    waits = []
    monkeypatch.setattr("agrireg_agent.graph.sleep", waits.append)
    registrations = [f"PD209901{index:02d}" for index in range(1, 13)]

    def handler(request):
        registration = request.url.params["keyword"]
        calls[registration] += 1
        if registration == registrations[5] and calls[registration] < 3:
            raise httpx.ReadTimeout("injected timeout", request=request)
        return httpx.Response(200, json=lookup_payload(registration))

    question = "\n".join(f"{index}. 查图谱登记记录 {number}" for index, number in enumerate(registrations, 1))
    result = run_graph(tmp_path, question, handler)

    assert result["status"] == "completed"
    assert len(result["tool_results"]) == 12 and result["tool_attempts"] == 14
    assert len({item["step"]["id"] for item in result["tool_results"]}) == 12
    assert [calls[number] for number in registrations] == [1] * 5 + [3] + [1] * 6
    assert waits == [0.25, 0.5]
    assert [task["status"] for task in result["subtasks"]] == ["completed"] * 12
    assert "12/12 项" in result["report"]


def test_permanent_failure_blocks_dependents_and_keeps_independent_results(tmp_path):
    calls = []

    def handler(request):
        registration = request.url.params["keyword"]
        calls.append(registration)
        if registration == "PD20990201":
            return httpx.Response(403, json={"message": "injected permanent failure"})
        return httpx.Response(200, json=lookup_payload(registration))

    result = run_graph(tmp_path, (
        "1. 查图谱登记记录 PD20990201\n"
        "2. 根据第1项结果查图谱登记记录 PD20990202\n"
        "3. 查图谱登记记录 PD20990203"
    ), handler)

    assert calls == ["PD20990201", "PD20990203"]
    assert [task["status"] for task in result["subtasks"]] == ["failed", "blocked", "completed"]
    assert "依赖的第 1 项缺少完整结果" in result["report"]
    assert all(item["attempts"] == 1 for item in result["tool_results"])


def test_result_with_wrong_registration_is_dropped_and_replanned(tmp_path):
    class DocumentPlanner:
        def json_completion(self, system, user):
            question = json.loads(user)["question"]
            registration = REGISTRATION.search(question).group()
            return {
                "task_type": "fact_check", "summary": "查询登记材料", "entities": [registration],
                "steps": [{"id": "doc", "title": "查登记材料", "tool": "search_documents",
                           "arguments": {"query": registration, "registration_number": registration}}],
            }

    class DocumentsWithWrongHit(ControlledTools):
        def search_documents(self, query, registration_number=""):
            wrong = registration_number == "PD20990301"
            return {
                "tool": "search_documents", "summary": "找到文档",
                "evidence": [{
                    "id": "wrong-hit" if wrong else registration_number, "kind": "document_excerpt",
                    "title": "登记文档", "summary": "登记原文",
                    "properties": {"registrationNumber": "PD20990399" if wrong else registration_number},
                }],
            }

    settings = Settings(AGENT_DATA_DIR=tmp_path, DEEPSEEK_ENABLED=False)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=lookup_payload(req.url.params["keyword"])))
    graph = build_agent_graph(
        DocumentsWithWrongHit(settings, transport=transport), DeepSeekClient(settings), InMemorySaver(),
        planner=DocumentPlanner(), documents_enabled=True,
    )
    result = graph.invoke(
        {"question": "1. 查 PD20990301 登记原文\n2. 查 PD20990302 登记原文"},
        {"configurable": {"thread_id": "wrong-hit"}, "recursion_limit": 250},
    )

    assert [item["outcome"] for item in result["tool_results"]] == ["unexpected", "ok", "ok"]
    assert [item["step"]["tool"] for item in result["tool_results"]] == [
        "search_documents", "search_entity", "search_documents",
    ]
    assert [task["status"] for task in result["subtasks"]] == ["partial", "completed"]
    assert "返回文档与目标登记号不一致" in result["report"]
    assert "wrong-hit" not in {item["id"] for item in result["evidence"]}


def test_global_budget_stops_new_work_and_preserves_finished_tasks(tmp_path):
    calls = []

    def handler(request):
        registration = request.url.params["keyword"]
        calls.append(registration)
        return httpx.Response(200, json=lookup_payload(registration))

    result = run_graph(tmp_path, (
        "查图谱登记记录 PD20990401；查图谱登记记录 PD20990402；查图谱登记记录 PD20990403"
    ), handler, max_tool_attempts=2)

    assert calls == ["PD20990401", "PD20990402"]
    assert [task["status"] for task in result["subtasks"]] == ["completed", "completed", "blocked"]
    assert "工具调用额度已用完" in result["report"]


def test_split_requires_explicit_task_boundaries_and_prior_dependencies():
    assert split_subtasks("比较“甲”和“乙”的图谱关系") == []
    tasks = split_subtasks("1. 用第2项的结果查附件\n2. 查图谱\n3. 基于第2项的结果查该产品")
    assert [task["depends_on"] for task in tasks] == [[2], [], [2]]
    assert [task["status"] for task in tasks] == ["blocked", "pending", "pending"]
    queries = split_subtasks("请帮我做两件事，查 PD20990101；再查 PD20990102")
    assert [task["question"] for task in queries] == ["查 PD20990101", "再查 PD20990102"]


def test_same_registration_reference_stays_in_the_original_task():
    assert split_subtasks("我只想在登记资料里核对一下 00A657-62。请定位这个编号对应的文档。") == []
    tasks = split_subtasks("1. 查 00A657-62。\n2. 根据第1项查这个编号的登记资料。")
    assert len(tasks) == 2 and tasks[1]["depends_on"] == [1]


def test_dependent_task_uses_verified_registration_from_the_prior_result(tmp_path):
    registrations = []

    def handler(request):
        registration = request.url.params["keyword"]
        registrations.append(registration)
        return httpx.Response(200, json=lookup_payload(registration))

    result = run_graph(tmp_path, (
        "1. 查图谱登记记录 PD20990601\n"
        "2. 根据第1项结果，查该产品的图谱登记记录"
    ), handler)

    assert registrations == ["PD20990601", "PD20990601"]
    assert [task["status"] for task in result["subtasks"]] == ["completed", "completed"]


def test_event_stream_drains_all_pages_before_terminal_snapshot(tmp_path, monkeypatch):
    runtime = AgentRuntime(Settings(AGENT_DATA_DIR=tmp_path, DEEPSEEK_ENABLED=False))
    monkeypatch.setattr(api, "runtime", runtime)
    thread = runtime.store.create_thread("事件分页")
    run = runtime.store.create_run(thread["id"], "测试长流程", False)
    for number in range(105):
        runtime.store.append_event(run["id"], "step", str(number), "", {})
    runtime.store.update_run(run["id"], "completed")
    path = f"/api/agent/threads/{thread['id']}/runs/{run['id']}/events"
    try:
        with TestClient(api.app) as client:
            response = client.get(path)
        assert response.text.count("event: agent_event") == 106
        assert response.text.rfind("event: agent_event") < response.text.index("event: run_snapshot")
        snapshot = json.loads(response.text.split("event: run_snapshot\ndata: ", 1)[1])
        assert snapshot["events"][-1]["title"] == "104"
    finally:
        runtime._checkpoint_connection.close()


def test_restart_after_checkpoint_continues_with_next_subtask(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        registration = request.url.params["keyword"]
        calls.append(registration)
        return httpx.Response(200, json=lookup_payload(registration))

    settings = Settings(AGENT_DATA_DIR=tmp_path, DEEPSEEK_ENABLED=False)
    tools = ControlledTools(settings, transport=httpx.MockTransport(handler))
    original = AgentRuntime(settings, tools=tools)
    thread = original.store.create_thread("检查点恢复")
    run = original.store.create_run(thread["id"], "查登记记录 PD20990701；再查登记记录 PD20990702", False)
    config = {"configurable": {"thread_id": f"run:{run['id']}"}}
    list(original.graph.stream(
        original._initial_payload(run["id"]), config, interrupt_after=["execute"], durability="sync",
    ))
    assert calls == ["PD20990701"]
    original._checkpoint_connection.close()

    restarted = AgentRuntime(settings, tools=tools)
    monkeypatch.setattr(api, "runtime", restarted)
    try:
        path = f"/api/agent/threads/{thread['id']}/runs/{run['id']}"
        with TestClient(api.app) as client:
            assert client.get(path).json()["status"] == "paused"
            assert client.post(path + "/resume", json={"value": None}).status_code == 202
            assert "2/2 项" in wait_for_status(client, path, "completed")["report"]
        assert calls == ["PD20990701", "PD20990702"]
    finally:
        restarted._checkpoint_connection.close()


def wait_for_status(client, path, status):
    deadline = monotonic() + 6
    while monotonic() < deadline:
        run = client.get(path).json()
        if run["status"] == status:
            return run
        assert run["status"] != "failed", run
        sleep(0.02)
    raise AssertionError(f"Run did not reach {status}: {run}")


def test_missing_registration_other_task_finishes_then_reload_and_resume(tmp_path, monkeypatch):
    calls = []

    class LocalTools(ControlledTools):
        def execute(self, name, arguments, question):
            calls.append((name, arguments))
            registration = arguments.get("registration_number") or arguments.get("keyword")
            return {
                "tool": name, "summary": "找到样例", "evidence": [{
                    "id": f"{name}:{registration}", "title": registration, "summary": "登记记录",
                    "kind": "document_excerpt" if name == "search_documents" else "Registration",
                    "properties": {"registrationNumber": registration},
                }],
            }

    settings = Settings(
        AGENT_DATA_DIR=tmp_path, AGENT_MILVUS_URI="fixture.db", DEEPSEEK_ENABLED=False,
    )
    original = AgentRuntime(settings, tools=LocalTools(settings))
    monkeypatch.setattr(api, "runtime", original)
    with TestClient(api.app) as client:
        thread = client.post("/api/agent/threads", json={"title": "多任务"}).json()
        path = f"/api/agent/threads/{thread['id']}/runs"
        started = client.post(path, json={"question": (
            "1. 按登记证号查登记文件，目标登记号还没填，PD20990599 是举例\n"
            "2. 查图谱登记记录 PD20990502"
        )})
        assert started.status_code == 202
        path += "/" + started.json()["id"]
        waiting = wait_for_status(client, path, "waiting_clarification")
        assert waiting["interrupt"]["taskId"] == 1
        assert "登记证号" in waiting["interrupt"]["message"]
        calls_before_resume = list(calls)
        assert [args.get("registration_number") or args["keyword"] for _, args in calls] == ["PD20990502"] * 2

    original._checkpoint_connection.close()
    restarted = AgentRuntime(settings, tools=LocalTools(settings))
    monkeypatch.setattr(api, "runtime", restarted)
    try:
        with TestClient(api.app) as client:
            example = client.post(path + "/resume", json={"value": "这个还是示例 PD20990599"})
            assert example.status_code == 202
            waiting = wait_for_status(client, path, "waiting_clarification")
            assert waiting["interrupt"]["taskId"] == 1
            assert calls == calls_before_resume
            response = client.post(path + "/resume", json={"value": "目标登记号为 PD20990501"})
            assert response.status_code == 202
            completed = wait_for_status(client, path, "completed")
            assert completed["report"].startswith("# 多任务证据报告")
            assert "2/2 项" in completed["report"]
            assert calls == calls_before_resume + [("search_documents", {
                "query": "PD20990501", "registration_number": "PD20990501",
            })]
            assert client.post(path + "/resume", json={"value": "重复提交"}).status_code == 409
    finally:
        restarted._checkpoint_connection.close()
