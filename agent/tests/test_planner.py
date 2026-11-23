from agrireg_agent.planner import build_plan, fallback_plan, parse_plan, plan_explicit_missing_registration
from agrireg_agent.task_queue import CLARIFICATION_SEPARATOR


def test_comparison_plan_uses_bounded_tools():
    plan = fallback_plan("比较 'Abamectin' 与 'Chlorantraniliprole' 的图谱关系")

    assert plan.task_type == "comparison"
    assert plan.entities == ["Abamectin", "Chlorantraniliprole"]
    assert [step.tool for step in plan.steps] == [
        "compare_entities",
        "external_substance_lookup",
        "external_substance_lookup",
    ]


def test_compliance_plan_requires_human_review():
    plan = fallback_plan("核验 'Abamectin' 是否允许用于该作物")
    assert plan.task_type == "compliance_screen"
    assert plan.requires_approval is True


def test_fallback_extracts_latin_substance_name():
    plan = fallback_plan("Chlorantraniliprole 与哪些病虫害有关？")
    assert plan.entities == ["Chlorantraniliprole"]
    assert plan.steps[0].arguments["keyword"] == "Chlorantraniliprole"


def test_guessed_comparison_target_is_rejected():
    plan = fallback_plan("比较 'Abamectin' 与 'Chlorantraniliprole'")

    assert parse_plan(plan.model_dump(), "比较 'Abamectin'", False) is None


def test_registration_uses_filtered_document_lookup():
    plan = fallback_plan("PD20230017 的登记证有效期", documents_enabled=True)

    assert plan.steps[0].tool == "search_documents"
    assert plan.steps[0].arguments["registration_number"] == "PD20230017"
    assert all(step.tool != "external_substance_lookup" for step in plan.steps)


def test_missing_registration_accepts_real_migration_number_and_ignores_examples():
    question = "请按登记证号精确查找 Dagda 的登记资料，目标证号还没填。"
    initial = plan_explicit_missing_registration(question, False)
    assert initial and initial.missing_information and not initial.steps
    for reply in ("00a657-62", "目标登记证号是 00A657-62。"):
        resumed = plan_explicit_missing_registration(f"{question}{CLARIFICATION_SEPARATOR}{reply}", False)
        assert resumed and not resumed.missing_information
        assert resumed.steps[0].arguments["registration_number"] == "00A657-62"
    example = plan_explicit_missing_registration(f"{question}{CLARIFICATION_SEPARATOR}证号 4387-901 是示例。", False)
    assert example and example.missing_information and not example.steps


def test_planner_binds_a_single_requested_document_number():
    class OmitsFilter:
        def json_completion(self, _system, _user):
            return {
                "task_type": "fact_check", "summary": "查登记资料",
                "steps": [{"id": "docs", "tool": "search_documents", "title": "登记资料",
                           "arguments": {"query": "Dagda 登记资料"}}],
            }

    exact = build_plan("在登记资料里核对一下 00A657-62，定位这个编号的文档。", False, OmitsFilter(), True)
    assert exact.steps[0].arguments["registration_number"] == "00A657-62"
    optional = build_plan("关键词检索 Dagda 的登记资料，无需按证号 00A657-62 筛。", False, OmitsFilter(), True)
    assert "registration_number" not in optional.steps[0].arguments
    pair = build_plan("查登记资料里 00A657-62 和 4387-901 的两条记录。", False, OmitsFilter(), True)
    assert "registration_number" not in pair.steps[0].arguments

