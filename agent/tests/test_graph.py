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


def make_graph(tmp_path: Path):
    settings = Settings(
        AGENT_DATA_DIR=tmp_path,
        DEEPSEEK_ENABLED=False,
        DEEPSEEK_API_KEY="",
    )
    return build_agent_graph(FakeTools(), DeepSeekClient(settings), InMemorySaver())


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
    assert all(item["step"]["tool"] in {
        "search_entity", "external_substance_lookup", "grounded_answer"
    } for item in result["tool_results"])


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

    resumed = graph.invoke(Command(resume="'Chlorantraniliprole'"), config)
    assert resumed["status"] == "completed"

