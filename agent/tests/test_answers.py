from types import SimpleNamespace

import httpx
from langgraph.checkpoint.memory import InMemorySaver

from agrireg_agent.answering import answer_without_graph
from agrireg_agent.clients import ControlledTools, DeepSeekClient
from agrireg_agent.config import Settings
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
    edges = [{"source": 1, "target": 3, "type": "APPLIED_TO"}, {"source": 1, "target": 2, "type": "TREATS"}]
    path = {
        "found": True, "centerId": 2, "targetId": 3, "pathLength": 2,
        "nodes": [
            {"id": 1, "name": "00A657-62", "label": "RegisterNumber"},
            {"id": 2, "name": "网斑病", "label": "Disease", "center": True},
            {"id": 3, "name": "春大麦", "label": "Crop"},
        ],
    }

    def handler(request):
        if request.url.path == "/api/graph/path":
            return httpx.Response(200, json=path | {"edges": edges})
        return httpx.Response(200, json={"nodes": [], "edges": []})

    tools = ControlledTools(settings, transport=httpx.MockTransport(handler))
    graph = build_agent_graph(tools, DeepSeekClient(settings), InMemorySaver())
    question = {"question": "查找“网斑病”到“春大麦”的关系路径"}
    good = graph.invoke(question, {"configurable": {"thread_id": "good"}})
    assert "网斑病 → 00A657-62 → 春大麦" in good["report"]
    assert "「00A657-62」登记防治对象为「网斑病」" in good["report"]
    assert "「00A657-62」登记作物为「春大麦」" in good["report"]
    assert "[1]" in good["report"] and "[2]" in good["report"]
    assert "APPLIED_TO" not in good["report"]
    edges.pop()
    broken = graph.invoke(question, {"configurable": {"thread_id": "broken"}})
    assert "完整路径" in broken["report"] and "网斑病 →" not in broken["report"]
    assert broken["tool_results"][0]["outcome"] == "partial"
