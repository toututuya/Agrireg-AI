from agrireg_agent.graph import deduplicate_evidence, detect_conflicts


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

