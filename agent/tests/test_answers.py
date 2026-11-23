from types import SimpleNamespace

import httpx
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agrireg_agent.answering import answer_without_graph, document_answer
from agrireg_agent.clients import ControlledTools, DeepSeekClient
from agrireg_agent.config import Settings
from agrireg_agent.documents import CHUNK_LENGTH, CHUNK_OVERLAP
from agrireg_agent.graph import build_agent_graph


def test_general_answer_is_labeled_and_registry_judgment_requires_sources():
    tools = SimpleNamespace(settings=SimpleNamespace(milvus_uri=""))
    response = answer_without_graph("什么是轮作？", tools, lambda *_: "轮作是同一块田按季节交替种不同作物。")
    assert response["mode"] == "general" and response["model"] == "qwen3-base"
    assert "通用知识说明" in response["answer"] and not response["evidence"]

    def unexpected_model(*_):
        raise AssertionError("Registration-specific dosing must never reach the base model.")

    assert answer_without_graph("这个药该用多少剂量？", tools, unexpected_model)["mode"] == "unsupported"
    assert answer_without_graph("查资料 00A657-62 与 4387-901", tools, unexpected_model)["mode"] == "unsupported"
    assert answer_without_graph("解释轮作", tools, lambda *_: "建议使用300倍液。")["mode"] == "unavailable"


def test_document_fallback_verifies_the_exact_registration():
    def documents(query, registration_number):
        assert registration_number == "00A657-62"
        return {"tool": "search_documents", "evidence": [
            {
                "title": "错误登记", "summary": "其他登记原文", "properties": {"registrationNumber": "4387-901"},
            },
            {
                "title": "目标登记", "summary": "有效成分：Prothioconazole\n目标登记内容",
                "properties": {"registrationNumber": registration_number, "documentId": "neo4j-register-21268"},
                "url": "https://example.org/source",
            },
        ]}

    tools = SimpleNamespace(settings=SimpleNamespace(milvus_uri="index"), search_documents=documents)
    result = answer_without_graph("登记号 00A657-62 的登记资料", tools, None)
    assert result["mode"] == "document" and result["grounded"] is True
    assert "目标登记内容 [1]" in result["answer"] and "其他登记原文" not in result["answer"]
    assert "登记数据快照" in result["answer"] and "原文摘录" not in result["answer"]
    assert result["evidence"][0]["sourceUrl"] == "https://example.org/source"
    focused = answer_without_graph("登记号 00A657-62 的有效成分是什么", tools, None)
    assert "有效成分：Prothioconazole [1]" in focused["answer"] and "目标登记内容" not in focused["answer"]


def test_relationship_report_reconstructs_order_and_checks_each_link(tmp_path):
    settings = Settings(AGENT_DATA_DIR=tmp_path, DEEPSEEK_ENABLED=False)
    edges = [{"source": 1, "target": 3, "type": "APPLIED_TO"}, {"source": 2, "target": 1, "type": "INCLUDES"}]
    path = {
        "found": True, "centerId": 2, "targetId": 3, "pathLength": 2,
        "nodes": [
            {"id": 1, "name": "00A657-62", "label": "RegisterNumber"},
            {"id": 2, "name": "Chlorantraniliprole", "label": "ActiveSubstance", "center": True},
            {"id": 3, "name": "春大麦", "label": "Crop"},
        ],
    }

    def handler(request):
        if request.url.path == "/api/graph/path":
            return httpx.Response(200, json=path | {"edges": edges})
        return httpx.Response(200, json={"nodes": [], "edges": []})

    tools = ControlledTools(settings, transport=httpx.MockTransport(handler))
    graph = build_agent_graph(tools, DeepSeekClient(settings), InMemorySaver())
    question = {"question": "查找“Chlorantraniliprole”到“春大麦”的关系路径"}
    good = graph.invoke(question, {"configurable": {"thread_id": "good"}})
    assert "Chlorantraniliprole → 00A657-62 → 春大麦" in good["report"]
    assert "「00A657-62」的有效成分包括「Chlorantraniliprole」" in good["report"]
    assert "「00A657-62」的登记作物包括「春大麦」" in good["report"]
    assert "[1]" in good["report"] and "[2]" in good["report"]
    assert "APPLIED_TO" not in good["report"]
    report_event = next(item for item in good["events"] if item["kind"] == "report_ready")
    diagram, = report_event["payload"]["relationPaths"]
    assert [node["id"] for node in diagram["nodes"]] == ["2", "1", "3"]
    assert [link["label"] for link in diagram["links"]] == ["有效成分", "登记作物"]
    verified = {item["index"]: item["summary"] for item in good["verified_evidence"]}
    assert "的有效成分包括「Chlorantraniliprole」" in verified[diagram["links"][0]["evidenceIndex"]]
    assert "的登记作物包括「春大麦」" in verified[diagram["links"][1]["evidenceIndex"]]
    approval_config = {"configurable": {"thread_id": "review"}}
    waiting = graph.invoke(question | {"require_approval": True}, approval_config)
    assert waiting["__interrupt__"][0].value["kind"] == "approval"
    denied = graph.invoke(Command(resume={"decision": "reject"}), approval_config)
    assert all("relationPaths" not in item["payload"] for item in denied["events"])
    edges.pop()
    broken = graph.invoke(question, {"configurable": {"thread_id": "broken"}})
    assert "完整路径" in broken["report"] and "Chlorantraniliprole →" not in broken["report"]
    assert broken["tool_results"][0]["outcome"] == "partial"
    assert all("relationPaths" not in item["payload"] for item in broken["events"])


def test_focused_registry_answer_restores_words_split_between_snapshot_chunks():
    prefix = "图谱关联作物：Spring barley、Winter wheat、" + "Some variety、" * 5
    text = "其他资料" * ((CHUNK_LENGTH - len(prefix) - 2) // 4)
    text += "\n" + prefix
    text = text.ljust(CHUNK_LENGTH - 1, " ") + "W"
    first = {
        "title": "登记记录", "summary": text,
        "properties": {"documentId": "neo4j-register-1", "version": "v1", "section": "快照"},
    }
    continuation = first | {"summary": text[-CHUNK_OVERLAP:] + "inter oats\n其他字段：其他资料"}
    joined = document_answer("登记作物是什么", "00A657-62", [first, continuation])
    assert "Winter oats" in joined["answer"] and " W [1]" not in joined["answer"]
    trimmed = document_answer("登记作物是什么", "00A657-62", [first])
    assert "Some variety… [1]" in trimmed["answer"] and " W [1]" not in trimmed["answer"]
