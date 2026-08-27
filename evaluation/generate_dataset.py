#!/usr/bin/env python3
"""Build deterministic GraphRAG evaluation cases from the local Neo4j graph.

Generated cases contain local graph identifiers and sampled source data, so they
are intentionally written under evaluation/generated/, which is git-ignored.
"""

import argparse
import base64
import json
import os
import random
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


LABEL_QUOTAS = {
    "RegisterNumber": 324,
    "Crop": 56,
    "Disease": 43,
    "ActiveSubstance": 5,
    "ChemicalClasses": 5,
    "PesticideCategory": 5,
    "TargetSite": 5,
    "ModeOfAction": 5,
}

PATH_QUOTAS = {
    "registration_crop_direct": 18,
    "registration_disease_direct": 12,
    "active_registration_crop": 11,
    "active_registration_disease": 11,
}

ENTITY_QUERY = """
MATCH (node)
WITH node, labels(node)[0] AS label,
     coalesce(toString(node.name), toString(node.`Trade name`),
              toString(node.`Pesticide name`), toString(node.`Active Ingredient`)) AS name
WHERE label IN $labels
  AND name IS NOT NULL
  AND size(trim(name)) >= 1 AND size(trim(name)) <= 80
  AND NOT toLower(trim(name)) IN ['', '-', '--', 'n/a', 'na', 'null', 'none', 'unknown']
  AND coalesce(node.data_quality_status, '') <> 'orphan'
OPTIONAL MATCH (node)-[relation]-()
WITH node, label, trim(name) AS name, count(relation) AS degree,
     collect(DISTINCT type(relation)) AS relationTypes
WHERE degree > 0
RETURN id(node) AS nodeId, label, name,
       CASE WHEN node.`CAS registry number` IS NULL
            THEN NULL ELSE trim(toString(node.`CAS registry number`)) END AS cas,
       degree, relationTypes
ORDER BY label, nodeId
"""

PATH_QUERIES = {
    "registration_crop_direct": """
        MATCH (registration:RegisterNumber)-[:APPLIED_TO]-(crop:Crop)
        WHERE size(trim(registration.name)) >= 1 AND size(trim(registration.name)) <= 80
          AND size(trim(crop.name)) >= 1 AND size(trim(crop.name)) <= 80
        RETURN DISTINCT id(registration) AS sourceId, registration.name AS sourceName,
               'RegisterNumber' AS sourceLabel, id(crop) AS targetId, crop.name AS targetName,
               'Crop' AS targetLabel, 1 AS pathLength, ['APPLIED_TO'] AS relationTypes
    """,
    "registration_disease_direct": """
        MATCH (registration:RegisterNumber)-[:TREATS]-(disease:Disease)
        WHERE size(trim(registration.name)) >= 1 AND size(trim(registration.name)) <= 80
          AND size(trim(disease.name)) >= 1 AND size(trim(disease.name)) <= 80
        RETURN DISTINCT id(registration) AS sourceId, registration.name AS sourceName,
               'RegisterNumber' AS sourceLabel, id(disease) AS targetId, disease.name AS targetName,
               'Disease' AS targetLabel, 1 AS pathLength, ['TREATS'] AS relationTypes
    """,
    "active_registration_crop": """
        MATCH (active:ActiveSubstance)-[:INCLUDES]-(registration:RegisterNumber)-[:APPLIED_TO]-(crop:Crop)
        WHERE size(trim(active.name)) >= 1 AND size(trim(active.name)) <= 80
          AND size(trim(crop.name)) >= 1 AND size(trim(crop.name)) <= 80
        RETURN DISTINCT id(active) AS sourceId, active.name AS sourceName,
               'ActiveSubstance' AS sourceLabel, id(crop) AS targetId, crop.name AS targetName,
               'Crop' AS targetLabel, 2 AS pathLength, ['INCLUDES', 'APPLIED_TO'] AS relationTypes,
               id(registration) AS viaId, registration.name AS viaName
    """,
    "active_registration_disease": """
        MATCH (active:ActiveSubstance)-[:INCLUDES]-(registration:RegisterNumber)-[:TREATS]-(disease:Disease)
        WHERE size(trim(active.name)) >= 1 AND size(trim(active.name)) <= 80
          AND size(trim(disease.name)) >= 1 AND size(trim(disease.name)) <= 80
        RETURN DISTINCT id(active) AS sourceId, active.name AS sourceName,
               'ActiveSubstance' AS sourceLabel, id(disease) AS targetId, disease.name AS targetName,
               'Disease' AS targetLabel, 2 AS pathLength, ['INCLUDES', 'TREATS'] AS relationTypes,
               id(registration) AS viaId, registration.name AS viaName
    """,
}


class Neo4jHttp:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        username = os.getenv("NEO4J_HTTP_USERNAME", "")
        password = os.getenv("NEO4J_HTTP_PASSWORD", "")
        self.authorization = None
        if username:
            token = base64.b64encode((username + ":" + password).encode("utf-8")).decode("ascii")
            self.authorization = "Basic " + token

    def query(self, statement, parameters=None):
        payload = {
            "statements": [{
                "statement": statement,
                "parameters": parameters or {},
                "resultDataContents": ["row"],
            }]
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        if self.authorization:
            request.add_header("Authorization", self.authorization)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode("utf-8", errors="replace")) from error
        if body.get("errors"):
            raise RuntimeError(json.dumps(body["errors"], ensure_ascii=False))
        result = body["results"][0]
        columns = result["columns"]
        return [dict(zip(columns, item["row"])) for item in result["data"]]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def query_variant(entity, index):
    name = entity["name"]
    if entity["label"] == "ActiveSubstance" and entity.get("cas") and index % 5 == 4:
        return entity["cas"], "cas_exact"
    variant = index % 3
    if variant == 1 and any(character.isalpha() for character in name):
        return name.lower(), "lowercase"
    if variant == 2:
        return "  " + name + "  ", "surrounding_whitespace"
    return name, "exact_name"


def choose_entity_cases(rows, rng):
    by_label = defaultdict(list)
    for row in rows:
        by_label[row["label"]].append(row)

    cases = []
    for label, quota in LABEL_QUOTAS.items():
        candidates = by_label[label]
        if len(candidates) < quota:
            raise RuntimeError("{} only has {} eligible nodes; {} required".format(label, len(candidates), quota))
        selected = rng.sample(candidates, quota)
        selected.sort(key=lambda item: item["nodeId"])
        for offset, entity in enumerate(selected):
            keyword, variant = query_variant(entity, offset)
            cases.append({
                "id": "entity-{:04d}".format(len(cases) + 1),
                "kind": "entity_lookup",
                "keyword": keyword,
                "variant": variant,
                "expected": {
                    "nodeId": entity["nodeId"],
                    "label": entity["label"],
                    "name": entity["name"],
                    "degree": entity["degree"],
                    "relationTypes": sorted(entity["relationTypes"] or []),
                },
            })
    return cases


def choose_path_cases(db, rng):
    cases = []
    selected_by_category = {}
    all_by_category = {}
    for category, quota in PATH_QUOTAS.items():
        candidates = db.query(PATH_QUERIES[category])
        all_by_category[category] = candidates
        if len(candidates) < quota:
            raise RuntimeError("{} only has {} eligible paths; {} required".format(category, len(candidates), quota))
        selected = rng.sample(candidates, quota)
        selected.sort(key=lambda item: (item["sourceId"], item["targetId"]))
        selected_by_category[category] = selected
        for path in selected:
            cases.append({
                "id": "path-{:03d}".format(len(cases) + 1),
                "kind": "shortest_path",
                "category": category,
                "source": path["sourceName"],
                "target": path["targetName"],
                "expected": {
                    "sourceId": path["sourceId"],
                    "sourceLabel": path["sourceLabel"],
                    "targetId": path["targetId"],
                    "targetLabel": path["targetLabel"],
                    "pathLength": path["pathLength"],
                    "relationTypes": path["relationTypes"],
                    "viaId": path.get("viaId"),
                    "viaName": path.get("viaName"),
                },
            })
    return cases, selected_by_category, all_by_category


def cycle_take(rows, count, start=0, predicate=None):
    filtered = [row for row in rows if predicate is None or predicate(row)]
    if len(filtered) < count:
        raise RuntimeError("not enough cases for semantic category: {} available, {} required".format(len(filtered), count))
    return filtered[start:start + count]


def semantic_case(case_id, category, question, primary, expected):
    return {
        "id": case_id,
        "kind": "graph_qa",
        "category": category,
        "question": question,
        "primaryEntity": primary,
        "expected": expected,
    }


def clean_semantic_name(value):
    if not value or len(value) > 80:
        return False
    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", value)]
    if not tokens or len(tokens) > 8:
        return False
    if any(token in {"hygiene", "unknown", "unnamed"} for token in tokens):
        return False
    return len(tokens) == len(set(tokens))


def clean_paths(selected, all_candidates, count):
    combined = selected + all_candidates
    clean = []
    seen = set()
    for path in combined:
        key = (path["sourceId"], path["targetId"], path.get("viaId"))
        if key in seen:
            continue
        seen.add(key)
        if clean_semantic_name(path["sourceName"]) and clean_semantic_name(path["targetName"]):
            clean.append(path)
        if len(clean) >= count:
            return clean
    raise RuntimeError("not enough clean path candidates: {} available, {} required".format(len(clean), count))


def build_semantic_cases(entity_cases, selected_paths, all_paths):
    by_label = defaultdict(list)
    for case in entity_cases:
        by_label[case["expected"]["label"]].append(case)

    semantic = []

    registrations = cycle_take(
        by_label["RegisterNumber"], 10,
        predicate=lambda item: bool(set(item["expected"]["relationTypes"]) & {"APPLIED_TO", "TREATS"}),
    )
    for item in registrations:
        entity = item["expected"]
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "registration_usage",
            "登记号 {} 关联了哪些作物或病虫害？请依据图谱关系回答。".format(entity["name"]),
            {"nodeId": entity["nodeId"], "name": entity["name"], "label": entity["label"]},
            {"grounded": True, "requiredRelationAny": ["APPLIED_TO", "TREATS"],
             "requiredRelationAll": [], "requiredEndpointIdsAll": [entity["nodeId"]]},
        ))

    clean_crop_paths = clean_paths(
        selected_paths["active_registration_crop"], all_paths["active_registration_crop"], 16
    )
    clean_disease_paths = clean_paths(
        selected_paths["active_registration_disease"], all_paths["active_registration_disease"], 12
    )
    active_paths = clean_crop_paths + clean_disease_paths
    active_unique = []
    seen_active = set()
    for path in active_paths:
        if path["sourceId"] not in seen_active:
            active_unique.append(path)
            seen_active.add(path["sourceId"])
    if len(active_unique) < 10:
        # Reusing an entity is acceptable here because endpoint and relation constraints still differ.
        active_unique = active_paths
    for path in active_unique[:10]:
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "active_registration",
            "有效成分 {} 出现在哪些农药登记中？".format(path["sourceName"]),
            {"nodeId": path["sourceId"], "name": path["sourceName"], "label": "ActiveSubstance"},
            {"grounded": True, "requiredRelationAny": [], "requiredRelationAll": ["INCLUDES"],
             "requiredEndpointIdsAll": [path["sourceId"]]},
        ))

    for path in clean_crop_paths[:7] + clean_disease_paths[:3]:
        terminal_relation = path["relationTypes"][1]
        terminal_type = "作物" if path["targetLabel"] == "Crop" else "病虫害"
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "active_two_hop",
            "{} 与{} {} 通过什么登记记录产生关联？".format(
                path["sourceName"], terminal_type, path["targetName"]
            ),
            {"nodeId": path["sourceId"], "name": path["sourceName"], "label": "ActiveSubstance"},
            {"grounded": True, "requiredRelationAny": [],
             "requiredRelationAll": ["INCLUDES", terminal_relation],
             "requiredEndpointIdsAll": [path["sourceId"], path["targetId"]]},
        ))

    for item in cycle_take(by_label["Crop"], 5, predicate=lambda row: "APPLIED_TO" in row["expected"]["relationTypes"]):
        entity = item["expected"]
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "crop_relations",
            "作物 {} 有哪些相关农药登记？".format(entity["name"]),
            {"nodeId": entity["nodeId"], "name": entity["name"], "label": entity["label"]},
            {"grounded": True, "requiredRelationAny": ["APPLIED_TO"], "requiredRelationAll": [],
             "requiredEndpointIdsAll": [entity["nodeId"]]},
        ))

    for item in cycle_take(by_label["Disease"], 5, predicate=lambda row: bool(set(row["expected"]["relationTypes"]) & {"TREATS", "INFECTS"})):
        entity = item["expected"]
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "disease_relations",
            "病虫害 {} 与哪些作物或登记药剂有关？".format(entity["name"]),
            {"nodeId": entity["nodeId"], "name": entity["name"], "label": entity["label"]},
            {"grounded": True, "requiredRelationAny": ["TREATS", "INFECTS"], "requiredRelationAll": [],
             "requiredEndpointIdsAll": [entity["nodeId"]]},
        ))

    path_semantic = clean_crop_paths[:3] + clean_disease_paths[:2]
    for path in path_semantic:
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "path_explanation",
            "解释 {} 与 {} 的图谱关联路径，并指出中间登记号。".format(
                path["sourceName"], path["targetName"]
            ),
            {"nodeId": path["sourceId"], "name": path["sourceName"], "label": path["sourceLabel"]},
            {"grounded": True, "requiredRelationAny": [],
             "requiredRelationAll": path["relationTypes"],
             "requiredEndpointIdsAll": [path["sourceId"], path["targetId"]]},
        ))

    negatives = [
        "不存在的农药登记 EVAL-NOT-FOUND-001 有哪些适用作物？",
        "有效成分 GraphRAG-Fake-Substance-002 关联哪些病虫害？",
        "作物 EvalCrop-NotInGraph-003 有哪些登记药剂？",
        "病害 EvalDisease-NotInGraph-004 与哪些作物有关？",
        "请查询登记号 EVAL-NOT-FOUND-005 的详细关系。",
    ]
    for question in negatives:
        semantic.append(semantic_case(
            "qa-{:03d}".format(len(semantic) + 1), "negative_entity", question, None,
            {"grounded": False, "requiredRelationAny": [], "requiredRelationAll": [],
             "requiredEndpointIdsAll": []},
        ))

    if len(semantic) != 50:
        raise RuntimeError("semantic suite should contain 50 cases, got {}".format(len(semantic)))
    return semantic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--neo4j-http",
        default="http://127.0.0.1:7475/db/neo4j/tx/commit",
        help="Neo4j transactional HTTP endpoint",
    )
    parser.add_argument("--output-dir", default="evaluation/generated")
    parser.add_argument("--seed", type=int, default=20260827)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    db = Neo4jHttp(args.neo4j_http)
    entity_rows = db.query(ENTITY_QUERY, {"labels": list(LABEL_QUOTAS)})
    entity_cases = choose_entity_cases(entity_rows, rng)
    path_cases, selected_paths, all_paths = choose_path_cases(db, rng)
    structural = entity_cases + path_cases
    semantic = build_semantic_cases(entity_cases, selected_paths, all_paths)

    stats = db.query(
        "MATCH (n) WITH count(n) AS nodeCount MATCH ()-[r]->() "
        "RETURN nodeCount, count(r) AS relationshipCount"
    )[0]
    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "structural_eval.jsonl", structural)
    write_jsonl(output_dir / "semantic_eval.jsonl", semantic)

    manifest = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "graph": stats,
        "structural": {
            "total": len(structural),
            "entityLookup": len(entity_cases),
            "shortestPath": len(path_cases),
            "entityCoverageOfNodes": round(len(entity_cases) / stats["nodeCount"], 6),
            "labelQuotas": LABEL_QUOTAS,
            "pathQuotas": PATH_QUOTAS,
        },
        "semantic": {
            "total": len(semantic),
            "categories": dict(sorted(Counter(case["category"] for case in semantic).items())),
            "goldScope": "graph-consistency-v0.2; not external agronomic truth",
            "nameScreening": "reject placeholder, repeated-token and suspicious machine-translation names",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
