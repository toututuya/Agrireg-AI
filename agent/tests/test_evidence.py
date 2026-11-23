from agrireg_agent.graph import build_report, deduplicate_evidence, detect_conflicts
from agrireg_agent.planner import fallback_plan


def test_evidence_is_deduplicated_and_numbered():
    items = [
        {"id": "same", "source": "graph", "title": "A", "summary": "first"},
        {"id": "same", "source": "graph", "title": "A", "summary": "duplicate"},
        {"id": "other", "source": "external", "title": "A", "summary": "second"},
    ]
    result = deduplicate_evidence(items)
    assert [item["index"] for item in result] == [1, 2]
    assert [item["id"] for item in result] == ["same", "other"]


def test_formula_conflict_keeps_evidence_indexes():
    evidence = [
        {"index": 1, "properties": {"MolecularFormula": "C10H20"}},
        {"index": 2, "properties": {"Molecular Formula": "C10H18"}},
    ]
    conflicts = detect_conflicts(evidence)
    assert conflicts[0]["field"] == "molecular_formula"
    assert conflicts[0]["values"] == [
        {"value": "C10H20", "evidence": [1]},
        {"value": "C10H18", "evidence": [2]},
    ]


def test_distinct_entities_are_not_formula_conflicts():
    evidence = [
        {"index": 1, "title": "A", "properties": {"MolecularFormula": "C10H20"}},
        {"index": 2, "title": "B", "properties": {"MolecularFormula": "C10H18"}},
    ]

    assert detect_conflicts(evidence) == []


def test_report_uses_only_existing_evidence_text():
    class OffTopicModel:
        def json_completion(self, _system, _user):
            return {"evidence_ids": [99, 2, 2], "answer": "虚构的事实"}

    question = "查询 '吡虫啉'"
    report = build_report(
        {
            "question": question,
            "plan": fallback_plan(question).model_dump(),
            "verified_evidence": [
                {"index": 1, "title": "条目一", "summary": "图谱事实一"},
                {"index": 2, "title": "条目二", "summary": "图谱事实二"},
            ],
        },
        OffTopicModel(),
    )

    assert report.count("图谱事实二 [2]") == 1
    assert "虚构的事实" not in report
    assert "[99]" not in report

