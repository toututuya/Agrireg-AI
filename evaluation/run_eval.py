#!/usr/bin/env python3
"""Evaluate graph retrieval accuracy, evidence constraints and API latency."""

import argparse
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CITATION_PATTERN = re.compile(r"\[(\d+)]")


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def request_json(method, url, payload=None, timeout=70):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
            status = response.status
        error = None
    except urllib.error.HTTPError as exception:
        status = exception.code
        raw = exception.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw[:500]}
        error = "HTTP {}".format(status)
    except Exception as exception:
        status = None
        body = {}
        error = "{}: {}".format(type(exception).__name__, exception)
    latency_ms = (time.perf_counter() - started) * 1000
    return status, body, latency_ms, error


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    weighted = ordered[lower] * (upper - position) + ordered[upper] * (position - lower)
    return round(weighted, 2)


def latency_summary(values):
    if not values:
        return {"count": 0, "p50Ms": None, "p95Ms": None, "meanMs": None}
    return {
        "count": len(values),
        "p50Ms": percentile(values, 50),
        "p95Ms": percentile(values, 95),
        "meanMs": round(statistics.mean(values), 2),
    }


def ratio(numerator, denominator):
    return None if denominator == 0 else round(numerator / denominator, 4)


def structural_eval(cases, base_url):
    details = []
    search_latencies = []
    path_latencies = []

    for index, case in enumerate(cases, 1):
        expected = case["expected"]
        if case["kind"] == "entity_lookup":
            query = urllib.parse.urlencode({"keyword": case["keyword"]})
            status, response, latency, error = request_json(
                "GET", base_url + "/api/graph/search?" + query, timeout=30
            )
            search_latencies.append(latency)
            center_nodes = [node for node in response.get("nodes", []) if node.get("center")]
            actual_label = center_nodes[0].get("label") if center_nodes else None
            detail = {
                "id": case["id"], "kind": case["kind"], "status": status,
                "latencyMs": round(latency, 2), "error": error,
                "found": response.get("found") is True,
                "entityHit": response.get("centerId") == expected["nodeId"],
                "labelHit": actual_label == expected["label"],
                "expectedNodeId": expected["nodeId"], "actualNodeId": response.get("centerId"),
                "expectedLabel": expected["label"], "actualLabel": actual_label,
                "variant": case.get("variant"),
            }
        else:
            query = urllib.parse.urlencode({"source": case["source"], "target": case["target"]})
            status, response, latency, error = request_json(
                "GET", base_url + "/api/graph/path?" + query, timeout=45
            )
            path_latencies.append(latency)
            observed_relations = {edge.get("type") for edge in response.get("edges", [])}
            expected_relations = set(expected["relationTypes"])
            detail = {
                "id": case["id"], "kind": case["kind"], "category": case.get("category"),
                "status": status, "latencyMs": round(latency, 2), "error": error,
                "found": response.get("found") is True,
                "endpointHit": response.get("centerId") == expected["sourceId"] and
                               response.get("targetId") == expected["targetId"],
                "lengthHit": response.get("pathLength") == expected["pathLength"],
                "relationHit": expected_relations.issubset(observed_relations),
                "expectedPathLength": expected["pathLength"],
                "actualPathLength": response.get("pathLength"),
                "expectedRelations": sorted(expected_relations),
                "actualRelations": sorted(item for item in observed_relations if item),
            }
        details.append(detail)
        if index % 50 == 0 or index == len(cases):
            print("structural {}/{}".format(index, len(cases)), flush=True)

    searches = [item for item in details if item["kind"] == "entity_lookup"]
    paths = [item for item in details if item["kind"] == "shortest_path"]
    summary = {
        "caseCount": len(details),
        "entityLookup": {
            "count": len(searches),
            "foundRate": ratio(sum(item["found"] for item in searches), len(searches)),
            "entityHitRate": ratio(sum(item["entityHit"] for item in searches), len(searches)),
            "labelHitRate": ratio(sum(item["labelHit"] for item in searches), len(searches)),
            "httpSuccessRate": ratio(sum(item["status"] == 200 for item in searches), len(searches)),
            "latency": latency_summary(search_latencies),
            "variantAccuracy": {
                variant: ratio(
                    sum(item["entityHit"] for item in searches if item["variant"] == variant),
                    sum(item["variant"] == variant for item in searches),
                )
                for variant in sorted({item["variant"] for item in searches})
            },
        },
        "shortestPath": {
            "count": len(paths),
            "foundRate": ratio(sum(item["found"] for item in paths), len(paths)),
            "endpointHitRate": ratio(sum(item["endpointHit"] for item in paths), len(paths)),
            "lengthAccuracy": ratio(sum(item["lengthHit"] for item in paths), len(paths)),
            "relationRecallPassRate": ratio(sum(item["relationHit"] for item in paths), len(paths)),
            "httpSuccessRate": ratio(sum(item["status"] == 200 for item in paths), len(paths)),
            "latency": latency_summary(path_latencies),
        },
    }
    return summary, details


def evidence_node_ids(evidence):
    result = set()
    for fact in evidence:
        for key in ("sourceId", "targetId"):
            value = fact.get(key)
            if value is not None:
                result.add(value)
    return result


def semantic_eval(cases, base_url):
    details = []
    latencies = []
    for index, case in enumerate(cases, 1):
        status, response, latency, error = request_json(
            "POST",
            base_url + "/api/assistant/ask",
            {"question": case["question"], "visitorId": "graphrag-eval", "persist": False},
            timeout=70,
        )
        latencies.append(latency)
        expected = case["expected"]
        evidence = response.get("evidence", []) if isinstance(response.get("evidence"), list) else []
        relations = {fact.get("relation") for fact in evidence}
        node_ids = evidence_node_ids(evidence)
        answer = response.get("answer", "") if isinstance(response.get("answer"), str) else ""
        citations = [int(value) for value in CITATION_PATTERN.findall(answer)]
        evidence_indices = {fact.get("index") for fact in evidence}
        positive = expected["grounded"]
        relation_any = set(expected.get("requiredRelationAny", []))
        relation_all = set(expected.get("requiredRelationAll", []))
        endpoints_all = set(expected.get("requiredEndpointIdsAll", []))
        relation_any_pass = not relation_any or bool(relations & relation_any)
        relation_all_pass = relation_all.issubset(relations)
        endpoint_pass = endpoints_all.issubset(node_ids)
        grounded_match = response.get("grounded") is expected["grounded"]
        citation_present = bool(citations)
        citation_indices_valid = bool(citations) and all(value in evidence_indices for value in citations)
        if positive:
            constraint_pass = grounded_match and relation_any_pass and relation_all_pass and endpoint_pass
            faithfulness_proxy = constraint_pass and citation_present and citation_indices_valid
        else:
            constraint_pass = grounded_match and not evidence
            faithfulness_proxy = constraint_pass

        details.append({
            "id": case["id"], "category": case["category"], "status": status,
            "latencyMs": round(latency, 2), "error": error,
            "expectedGrounded": expected["grounded"], "actualGrounded": response.get("grounded"),
            "groundedMatch": grounded_match, "relationAnyPass": relation_any_pass,
            "relationAllPass": relation_all_pass, "endpointPass": endpoint_pass,
            "evidenceConstraintPass": constraint_pass, "citationPresent": citation_present,
            "citationIndicesValid": citation_indices_valid, "faithfulnessProxy": faithfulness_proxy,
            "evidenceCount": len(evidence), "citationCount": len(citations),
            "observedRelations": sorted(item for item in relations if item),
            "answer": answer, "focusEntities": response.get("focusEntities", []),
        })
        print("semantic {}/{}".format(index, len(cases)), flush=True)

    positive_rows = [item for item in details if item["expectedGrounded"]]
    summary = {
        "caseCount": len(details),
        "httpSuccessRate": ratio(sum(item["status"] == 200 for item in details), len(details)),
        "groundedMatchRate": ratio(sum(item["groundedMatch"] for item in details), len(details)),
        "evidenceConstraintPassRate": ratio(sum(item["evidenceConstraintPass"] for item in details), len(details)),
        "citationPresentRatePositive": ratio(sum(item["citationPresent"] for item in positive_rows), len(positive_rows)),
        "citationIndexValidityPositive": ratio(sum(item["citationIndicesValid"] for item in positive_rows), len(positive_rows)),
        "faithfulnessProxyRate": ratio(sum(item["faithfulnessProxy"] for item in details), len(details)),
        "latency": latency_summary(latencies),
        "categoryPassRate": {
            category: ratio(
                sum(item["evidenceConstraintPass"] for item in details if item["category"] == category),
                sum(item["category"] == category for item in details),
            )
            for category in sorted({item["category"] for item in details})
        },
        "failureCounts": dict(Counter(
            failure
            for item in details
            for failure, passed in (
                ("http", item["status"] == 200),
                ("grounded", item["groundedMatch"]),
                ("relation_any", item["relationAnyPass"]),
                ("relation_all", item["relationAllPass"]),
                ("endpoint", item["endpointPass"]),
                ("citation", (not item["expectedGrounded"]) or
                              (item["citationPresent"] and item["citationIndicesValid"])),
            )
            if not passed
        )),
    }
    return summary, details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("structural", "semantic", "all"), default="structural")
    parser.add_argument("--base-url", default="http://127.0.0.1:4399")
    parser.add_argument("--structural-file", default="evaluation/generated/structural_eval.jsonl")
    parser.add_argument("--semantic-file", default="evaluation/generated/semantic_eval.jsonl")
    parser.add_argument("--output-dir", default="evaluation/results")
    parser.add_argument("--tag", default="current")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run = {
        "schemaVersion": "1.0",
        "tag": args.tag,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": base_url,
        "suite": args.suite,
    }
    all_details = []
    if args.suite in ("structural", "all"):
        summary, details = structural_eval(read_jsonl(args.structural_file), base_url)
        run["structural"] = summary
        all_details.extend(details)
    if args.suite in ("semantic", "all"):
        summary, details = semantic_eval(read_jsonl(args.semantic_file), base_url)
        run["semantic"] = summary
        all_details.extend(details)
    run["finishedAt"] = datetime.now(timezone.utc).isoformat()

    summary_path = output_dir / (args.tag + "_summary.json")
    details_path = output_dir / (args.tag + "_details.jsonl")
    summary_path.write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(details_path, all_details)
    print(json.dumps(run, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
