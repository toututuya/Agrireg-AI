from agrireg_agent.config import Settings
from agrireg_agent.clients import DeepSeekClient
from agrireg_agent.planner import fallback_plan


def test_comparison_plan_uses_bounded_tools():
    plan = fallback_plan("比较 'Abamectin' 与 'Chlorantraniliprole' 的图谱关系")

    assert plan.task_type == "comparison"
    assert plan.entities == ["Abamectin", "Chlorantraniliprole"]
    assert [step.tool for step in plan.steps] == [
        "compare_entities",
        "external_substance_lookup",
        "external_substance_lookup",
        "grounded_answer",
    ]


def test_compliance_plan_requires_human_review():
    plan = fallback_plan("核验 'Abamectin' 是否允许用于该作物")
    assert plan.task_type == "compliance_screen"
    assert plan.requires_approval is True


def test_fallback_extracts_latin_substance_name():
    plan = fallback_plan("Chlorantraniliprole 与哪些病虫害有关？")
    assert plan.entities == ["Chlorantraniliprole"]
    assert plan.steps[0].arguments["keyword"] == "Chlorantraniliprole"

