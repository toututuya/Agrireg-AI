#!/usr/bin/env python3
"""Compare pretrained DeepSeek answers with the local GraphRAG pipeline."""

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


CITATION_PATTERN = re.compile(r"\[(\d+)]")
REFUSAL_TERMS = ("无法确定", "无法回答", "不知道", "不确定", "没有足够", "未找到", "cannot determine", "do not know")


def load_env(path):
    values = {}
    env_path = Path(path)
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def post_json(url, payload, headers=None, timeout=70):
    request_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=request_headers, method="POST"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response), (time.perf_counter() - started) * 1000, None
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw[:500]}
        return error.code, body, (time.perf_counter() - started) * 1000, "HTTP {}".format(error.code)
    except Exception as error:
        return curl_post_json(url, payload, request_headers, timeout, started, error)


def curl_post_json(url, payload, headers, timeout, started, first_error):
    curl = "curl.exe" if os.name == "nt" else "curl"
    try:
        with tempfile.TemporaryDirectory(prefix="agrireg-eval-") as temp_dir:
            body_path = Path(temp_dir) / "body.json"
            config_path = Path(temp_dir) / "curl.conf"
            body_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            config_lines = [
                "silent", "show-error", "request = \"POST\"",
                "max-time = \"{}\"".format(timeout),
                "url = \"{}\"".format(url.replace('"', '\\"')),
                "data-binary = \"@{}\"".format(body_path.as_posix()),
                "write-out = \"\\n%{{http_code}}\"",
            ]
            for key, value in headers.items():
                config_lines.append("header = \"{}: {}\"".format(key, str(value).replace('"', '\\"')))
            config_path.write_text("\n".join(config_lines) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [curl, "--config", str(config_path)], capture_output=True, text=True, encoding="utf-8",
                timeout=timeout + 5,
            )
        elapsed = (time.perf_counter() - started) * 1000
        if completed.returncode != 0:
            return None, {}, elapsed, "{}; curl: {}".format(first_error, completed.stderr.strip())
        raw, status_text = completed.stdout.rsplit("\n", 1)
        status = int(status_text.strip())
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw[:500]}
        error = None if 200 <= status < 300 else "HTTP {}".format(status)
        return status, body, elapsed, error
    except Exception as curl_error:
        return None, {}, (time.perf_counter() - started) * 1000, "{}; curl fallback: {}".format(first_error, curl_error)


def normalize(value):
    value = unicodedata.normalize("NFKC", str(value)).lower()
    return "".join(character for character in value if character.isalnum())


def answer_matches(answer, expected):
    normalized_answer = normalize(answer)
    groups = expected.get("requiredConceptGroups", [])
    return bool(groups) and all(any(normalize(term) in normalized_answer for term in group) for group in groups)


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100.0
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    return round(ordered[lower] * (upper - position) + ordered[upper] * (position - lower), 2)


def latency(values):
    return {
        "count": len(values), "p50Ms": percentile(values, 50), "p95Ms": percentile(values, 95),
        "meanMs": round(statistics.mean(values), 2) if values else None,
    }


def ratio(count, total):
    return round(count / total, 4) if total else None


def direct_answer(question, config):
    messages = [
        {
            "role": "system",
            "content": "你是农药与化学信息问答助手。仅使用模型已有知识简洁回答，不访问知识图谱或外部检索；不确定时明确说明，不要伪造来源。",
        },
        {"role": "user", "content": question},
    ]
    payload = {
        "model": config["model"], "messages": messages, "stream": False,
        "max_tokens": 300, "temperature": 0.1, "thinking": {"type": "disabled"},
    }
    status, body, elapsed, error = post_json(
        config["baseUrl"].rstrip("/") + "/chat/completions", payload,
        {"Authorization": "Bearer " + config["apiKey"]}, timeout=70,
    )
    answer = body.get("choices", [{}])[0].get("message", {}).get("content", "") if status == 200 else ""
    return status, answer.strip(), elapsed, error, body.get("usage", {})


def graphrag_answer(question, base_url):
    status, body, elapsed, error = post_json(
        base_url.rstrip("/") + "/api/assistant/ask",
        {"question": question, "visitorId": "external-ablation-eval", "persist": False},
        timeout=70,
    )
    return status, body.get("answer", ""), elapsed, error, body


def score_system(answer, expected):
    normalized_answer = answer.lower()
    return {
        "correct": answer_matches(answer, expected),
        "refused": any(term in normalized_answer for term in REFUSAL_TERMS),
    }


def system_summary(details, prefix):
    total = len(details)
    successes = sum(item[prefix + "Status"] == 200 for item in details)
    correct = sum(item[prefix + "Correct"] for item in details)
    refused = sum(item[prefix + "Refused"] for item in details)
    return {
        "httpSuccessRate": ratio(successes, total),
        "externalFactAccuracy": ratio(correct, total),
        "refusalRate": ratio(refused, total),
        "latency": latency([item[prefix + "LatencyMs"] for item in details]),
        "categoryAccuracy": {
            category: ratio(
                sum(item[prefix + "Correct"] for item in details if item["category"] == category),
                sum(item["category"] == category for item in details),
            )
            for category in sorted({item["category"] for item in details})
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evaluation/external_gold/external_source_candidates_v0.1.jsonl")
    parser.add_argument("--env-file", default="api/.env.local")
    parser.add_argument("--base-url", default="http://127.0.0.1:4399")
    parser.add_argument("--output-dir", default="evaluation/results")
    parser.add_argument("--tag", default="external-ablation")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    env = load_env(args.env_file)
    config = {
        "apiKey": os.getenv("DEEPSEEK_API_KEY", env.get("DEEPSEEK_API_KEY", "")),
        "baseUrl": os.getenv("DEEPSEEK_BASE_URL", env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")),
        "model": os.getenv("DEEPSEEK_MODEL", env.get("DEEPSEEK_MODEL", "deepseek-v4-flash")),
    }
    if not config["apiKey"]:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    cases = read_jsonl(args.cases)
    if args.limit:
        cases = cases[:args.limit]
    details = []
    direct_usage = Counter()
    for index, case in enumerate(cases, 1):
        direct_status, direct_text, direct_ms, direct_error, usage = direct_answer(case["question"], config)
        graph_status, graph_text, graph_ms, graph_error, graph_body = graphrag_answer(case["question"], args.base_url)
        direct_score = score_system(direct_text, case["expected"])
        graph_score = score_system(graph_text, case["expected"])
        for key, value in usage.items():
            if isinstance(value, int):
                direct_usage[key] += value
        citations = [int(value) for value in CITATION_PATTERN.findall(graph_text)]
        evidence_indices = {fact.get("index") for fact in graph_body.get("evidence", [])}
        citation_valid = bool(citations) and all(value in evidence_indices for value in citations)
        details.append({
            "id": case["id"], "category": case["category"], "question": case["question"],
            "expectedValue": case["expected"]["value"], "sourceUrl": case["source"]["url"],
            "expertReviewStatus": case["expertReview"]["status"],
            "directStatus": direct_status, "directAnswer": direct_text,
            "directLatencyMs": round(direct_ms, 2), "directError": direct_error,
            "directCorrect": direct_score["correct"], "directRefused": direct_score["refused"],
            "graphragStatus": graph_status, "graphragAnswer": graph_text,
            "graphragLatencyMs": round(graph_ms, 2), "graphragError": graph_error,
            "graphragCorrect": graph_score["correct"], "graphragRefused": graph_score["refused"],
            "graphragGrounded": graph_body.get("grounded"),
            "graphragEvidenceCount": len(graph_body.get("evidence", [])),
            "graphragCitationPresent": bool(citations), "graphragCitationIndexValid": citation_valid,
        })
        print("external ablation {}/{}".format(index, len(cases)), flush=True)

    pairwise = Counter()
    for item in details:
        if item["directCorrect"] and item["graphragCorrect"]:
            pairwise["both_correct"] += 1
        elif item["graphragCorrect"]:
            pairwise["graphrag_only"] += 1
        elif item["directCorrect"]:
            pairwise["direct_only"] += 1
        else:
            pairwise["neither"] += 1

    summary = {
        "schemaVersion": "1.0",
        "tag": args.tag,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "provisional_external_source_benchmark_pending_domain_expert_review",
        "caseCount": len(details),
        "model": config["model"],
        "direct": system_summary(details, "direct"),
        "graphrag": system_summary(details, "graphrag"),
        "graphragTraceability": {
            "groundedRate": ratio(sum(item["graphragGrounded"] is True for item in details), len(details)),
            "citationPresentRate": ratio(sum(item["graphragCitationPresent"] for item in details), len(details)),
            "citationIndexValidityRate": ratio(sum(item["graphragCitationIndexValid"] for item in details), len(details)),
        },
        "pairwise": dict(pairwise),
        "directUsage": dict(direct_usage),
        "scoring": "deterministic normalized concept matching; no LLM judge",
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / (args.tag + "_summary.json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_jsonl(output_dir / (args.tag + "_details.jsonl"), details)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
