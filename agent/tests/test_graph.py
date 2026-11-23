from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agrireg_agent.clients import DeepSeekClient
from agrireg_agent.config import Settings
from agrireg_agent.graph import build_agent_graph


class FakeTools:
    def execute(self, name, arguments, question):
        label = arguments.get("keyword") or arguments.get("name") or arguments.get("left") or "GraphRAG"
        return {
            "tool": name,
            "summary": f"{name} completed",
            "data": {},
            "evidence": [
                {
                    "id": f"{name}:{label}",
                    "source": "test-source",
                    "title": str(label),
                    "kind": "test",
                    "summary": f"verified {label}",
                    "url": "https://example.test/evidence",
                    "properties": {},
                }
            ],
        }


def make_graph(tmp_path: Path, tools=None, **options):
    settings = Settings(
        AGENT_DATA_DIR=tmp_path,
        DEEPSEEK_ENABLED=False,
        DEEPSEEK_API_KEY="",
    )
    return build_agent_graph(tools or FakeTools(), DeepSeekClient(settings), InMemorySaver(), **options)


def test_fact_task_completes_with_numbered_evidence(tmp_path):
    graph = make_graph(tmp_path)
    config = {"configurable": {"thread_id": "fact-run"}}
    result = graph.invoke(
        {
            "question": "Chlorantraniliprole 与哪些病虫害有关？",
            "require_approval": False,
            "tool_results": [],
            "evidence": [],
            "events": [],
        },
        config,
    )

    assert result["status"] == "completed"
    assert result["verified_evidence"]
    assert "[1]" in result["report"]
    assert [item["step"]["tool"] for item in result["tool_results"]] == [
        "search_entity", "external_substance_lookup",
    ]


def test_compliance_task_interrupts_and_resumes(tmp_path):
    graph = make_graph(tmp_path)
    config = {"configurable": {"thread_id": "approval-run"}}
    first = graph.invoke(
        {
            "question": "核验 'Abamectin' 是否合规",
            "require_approval": False,
            "tool_results": [],
            "evidence": [],
            "events": [],
        },
        config,
    )

    assert first["__interrupt__"][0].value["kind"] == "approval"

    resumed = graph.invoke(Command(resume={"decision": "approve"}), config)
    assert resumed["status"] == "completed"
    assert resumed["approval_decision"] == "approve"


def test_missing_comparison_entity_requests_clarification(tmp_path):
    graph = make_graph(tmp_path)
    config = {"configurable": {"thread_id": "clarification-run"}}
    first = graph.invoke(
        {
            "question": "比较 'Abamectin'",
            "require_approval": False,
            "tool_results": [],
            "evidence": [],
            "events": [],
        },
        config,
    )
    assert first["__interrupt__"][0].value["kind"] == "clarification"

    resumed = graph.invoke(Command(resume="Chlorantraniliprole"), config)
    assert resumed["status"] == "completed"


def test_empty_path_replans_once_within_total_step_budget(tmp_path):
    class EmptyPathTools(FakeTools):
        def execute(self, name, arguments, question):
            if name == "find_relation_path":
                return {"tool": name, "evidence": []}
            return super().execute(name, arguments, question)

    graph = make_graph(tmp_path, tools=EmptyPathTools(), documents_enabled=True, max_tool_steps=2)
    result = graph.invoke(
        {"question": "查找 'Abamectin' 到 'Botrytis cinerea' 的关系路径"},
        {"configurable": {"thread_id": "adaptive-path"}},
    )

    assert result["status"] == "completed"
    assert [tool["step"]["tool"] for tool in result["tool_results"]] == [
        "find_relation_path", "search_entity",
    ]
    assert sum(item["kind"] == "plan_updated" for item in result["events"]) == 1


def test_no_close_of_missing_fields_without_user_response(tmp_path):
    graph = make_graph(tmp_path)
    config = {"configurable": {"thread_id": "missing-fields"}}

    graph.invoke({"question": "比较 'Abamectin'"}, config)
    graph.invoke(Command(resume={"value": None}), config)
    result = graph.invoke(Command(resume=""), config)

    assert result["status"] == "completed"
    assert result["report"].startswith("# 信息待补")
    assert not result["tool_results"]

