from agrireg_agent.planner import fallback_plan, parse_plan


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

