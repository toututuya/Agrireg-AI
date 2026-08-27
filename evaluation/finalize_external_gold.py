#!/usr/bin/env python3
"""Finalize candidate cases only after two-reviewer agreement or adjudication."""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def normalized(value):
    return str(value or "").strip().lower()


def accepted_review(review):
    first = normalized(review.get("reviewer1Decision"))
    second = normalized(review.get("reviewer2Decision"))
    first_name = str(review.get("reviewer1") or "").strip()
    second_name = str(review.get("reviewer2") or "").strip()
    if first == second == "accept" and first_name and second_name:
        return True, "two_reviewer_agreement"
    adjudicated = normalized(review.get("adjudicatedDecision"))
    adjudicator = str(review.get("adjudicator") or "").strip()
    if adjudicated == "accept" and adjudicator:
        return True, "adjudicated_acceptance"
    return False, "unresolved_or_rejected"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="evaluation/external_gold/external_source_candidates_v0.1.jsonl")
    parser.add_argument("--reviews", default="evaluation/external_gold/expert_review_template_v0.1.csv")
    parser.add_argument("--output", default="evaluation/external_gold/external_gold_v0.1.jsonl")
    args = parser.parse_args()

    candidates = {item["id"]: item for item in read_jsonl(args.candidates)}
    with Path(args.reviews).open("r", encoding="utf-8-sig", newline="") as handle:
        reviews = {row["caseId"]: row for row in csv.DictReader(handle)}

    accepted = []
    unresolved = []
    finalized_at = datetime.now(timezone.utc).isoformat()
    for case_id, item in candidates.items():
        review = reviews.get(case_id, {})
        is_accepted, method = accepted_review(review)
        if not is_accepted:
            unresolved.append(case_id)
            continue
        item["expertReview"] = {
            "status": "accepted",
            "method": method,
            "reviewer1": review.get("reviewer1"),
            "reviewer2": review.get("reviewer2"),
            "adjudicator": review.get("adjudicator") or None,
            "reviewedAt": review.get("reviewedAt") or finalized_at,
            "notes": review.get("adjudicationNotes") or None,
        }
        accepted.append(item)

    if unresolved:
        raise RuntimeError(
            "Gold set not finalized: {} cases still unresolved ({})".format(
                len(unresolved), ", ".join(unresolved[:8])
            )
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output, accepted)
    manifest = {
        "status": "expert_reviewed_external_gold",
        "finalizedAt": finalized_at,
        "caseCount": len(accepted),
        "sourceCandidates": str(Path(args.candidates).as_posix()),
        "reviewFile": str(Path(args.reviews).as_posix()),
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
