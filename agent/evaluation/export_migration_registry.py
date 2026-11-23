"""Export RAG input and planner source records from a restored Neo4j snapshot."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import file_digest
import json
from pathlib import Path
from urllib.request import Request, urlopen

from pydantic import HttpUrl

from agrireg_agent.documents import SourcePage, chunk_page
from agrireg_agent.planner_sft import _write_jsonl


REGISTRATIONS = """
MATCH (r:RegisterNumber) WHERE id(r) > $after
WITH r ORDER BY id(r) LIMIT $limit
OPTIONAL MATCH (r)-[:INCLUDES|APPLIED_TO|TREATS]-(n)
WITH r, collect(DISTINCT {name: n.name, labels: labels(n)}) AS neighbors
RETURN id(r), {
    registration: r.name, canonical_id: r.canonical_id,
    jurisdiction: r.jurisdiction, origin: r.`Member State of origin`,
    trade_name: r.`Trade name`, product_name: r.`Pesticide name`,
    authorization_holder: r.`Authorization holder`, certificate_holder: r.`holder of registration certificate`,
    active_ingredient: r.`Active Ingredient`, english_ingredient: r.`English name of active ingredient`,
    status: r.Status, valid_until: r.valid_until,
    category: r.`Pesticide category`, formulation: r.Formulation,
    recognized_from: r.`Approval number/Member State of origin`
}, neighbors ORDER BY id(r)
"""


def _query(url: str, cypher: str, **parameters):
    payload = json.dumps({"statements": [{"statement": cypher, "parameters": parameters}]}).encode()
    request = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=45) as response:
        result = json.load(response)
    if result["errors"]:
        error = result["errors"][0]
        raise RuntimeError(f"Neo4j export failed ({error['code']}).")
    return [row["row"] for row in result["results"][0]["data"]]


def _text(value: object) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _neighbors(neighbors: list[dict], label: str) -> list[str]:
    return sorted({_text(node["name"]) for node in neighbors if node["name"] and label in node["labels"]})


def _registration(raw: dict, neighbors: list[dict], node_id: int, citation_base: str, version: str):
    registration = _text(raw["registration"]).upper()
    if not registration or not raw["canonical_id"]:
        raise ValueError(f"Registration node {node_id} lacks a stable identifier.")
    product = _text(raw["product_name"]) or _text(raw["trade_name"])
    holder = _text(raw["certificate_holder"]) or _text(raw["authorization_holder"])
    origin = _text(raw["origin"])
    source_group = "other"
    if origin == "China":
        source_group = "china"
    elif raw["status"] is not None:
        source_group = "germany"
    elif raw["recognized_from"] is not None:
        source_group = "eu_mutual_recognition"
    actives = _neighbors(neighbors, "ActiveSubstance")
    crops = _neighbors(neighbors, "Crop")
    diseases = _neighbors(neighbors, "Disease")
    fields = (
        ("登记号", registration), ("产品名", product), ("持有人", holder), ("来源字段", origin),
        ("登记辖区", _text(raw["jurisdiction"])), ("类别", _text(raw["category"])), ("剂型", _text(raw["formulation"])),
        ("登记状态（快照）", _text(raw["status"])), ("有效期（快照）", _text(raw["valid_until"])),
        ("有效成分", _text(raw["active_ingredient"])), ("成分英文名", _text(raw["english_ingredient"])),
        ("图谱关联成分", "、".join(actives)), ("图谱关联作物", "、".join(crops)),
        ("图谱关联防治对象", "、".join(diseases)),
    )
    page = SourcePage(
        document_id=f"neo4j-register-{node_id}", version=version, title=f"{registration} 登记记录",
        section=f"登记数据快照 / Neo4j 节点 {node_id}",
        source_url=f"{citation_base}/api/graph/node/{node_id}", registration_number=registration,
        text="\n".join(f"{label}：{value}" for label, value in fields if value),
    )
    record = {
        "registration": page.registration_number, "holder": holder, "product": product,
        "source_group": source_group, "source_ref": str(page.source_url),
        "canonical_id": raw["canonical_id"], "path_targets": sorted(set(actives + crops)),
        "active_names": sorted(set(actives + [_text(raw["english_ingredient"]), _text(raw["active_ingredient"])]) - {""}),
    }
    return page, record


def export(url: str, citation_base: str, dump: Path, expected_count: int, output: Path) -> None:
    if expected_count < 1 or output.exists():
        raise ValueError("Supply a positive expected count and a new output directory.")
    citation = HttpUrl(citation_base)
    if citation.path != "/" or citation.query or citation.fragment or citation.username or citation.password:
        raise ValueError("The citation base must be the origin of the graph API.")
    with dump.open("rb") as handle:
        digest = file_digest(handle, "sha256").hexdigest()
    version = f"neo4j-{digest[:16]}"
    [[count]] = _query(url, "MATCH (r:RegisterNumber) RETURN count(r)")
    if count != expected_count:
        raise ValueError(f"Expected {expected_count} registration nodes, found {count}.")
    pages, records = [], []
    after = -1
    while batch := _query(url, REGISTRATIONS, after=after, limit=500):
        for node_id, props, neighbors in batch:
            page, record = _registration(props, neighbors, node_id, str(citation).rstrip("/"), version)
            pages.append(page)
            records.append(record)
        after = batch[-1][0]
    if len(pages) != count or len({page.registration_number for page in pages}) != count:
        raise ValueError("Exported registration identifiers are missing or duplicated.")

    output.mkdir(parents=True)
    _write_jsonl(output / "documents.jsonl", (page.model_dump(mode="json") for page in pages))
    _write_jsonl(output / "planner_records.jsonl", records)
    receipt = {
        "dump_sha256": digest, "version": version, "registrations": count,
        "chunks": sum(1 for page in pages for _ in chunk_page(page)),
        "source_groups": dict(Counter(record["source_group"] for record in records)),
        "citation_type": "neo4j_node_snapshot",
    }
    (output / "manifest.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neo4j-tx", required=True, help="HTTP transaction endpoint of the restored read-only snapshot")
    parser.add_argument("--citation-base", required=True, help="Browser-accessible graph API origin")
    parser.add_argument("--dump", type=Path, required=True, help="The dump restored for this export")
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.neo4j_tx, args.citation_base, args.dump, args.expected_count, args.output)
