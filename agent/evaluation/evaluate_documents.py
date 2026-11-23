from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter

from agrireg_agent.documents import DocumentSearchRequest, get_document_search


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare document retrieval modes on shared qrels")
    parser.add_argument("qrels", type=Path)
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 11))
    args = parser.parse_args()
    with args.qrels.open(encoding="utf-8-sig") as source:
        rows = [json.loads(line) for line in source if line.strip()]
    if not rows or any(not row.get("relevant_document_ids") for row in rows):
        parser.error("Each row must contain a query and nonempty relevant_document_ids.")
    documents = get_document_search()
    if documents is None:
        parser.error("Configure AGENT_MILVUS_URI for the evaluation.")

    results = {}
    for mode in ("dense", "bm25", "hybrid", "reranked"):
        requests = [
            DocumentSearchRequest(
                query=row["query"], registration_number=row.get("registration_number", ""),
                limit=args.limit, mode=mode,
            )
            for row in rows
        ]
        documents.search(requests[0])
        latency_ms, recall, reciprocal_rank = [], [], []
        for request, row in zip(requests, rows, strict=True):
            started = perf_counter()
            hits = documents.search(request)
            latency_ms.append((perf_counter() - started) * 1000)
            relevant = set(row["relevant_document_ids"])
            returned = [hit.document_id for hit in hits]
            recall.append(len(relevant.intersection(returned)) / len(relevant))
            rank = next((i for i, doc_id in enumerate(returned, 1) if doc_id in relevant), None)
            reciprocal_rank.append(1 / rank if rank else 0.0)
        results[mode] = {
            "recall": sum(recall) / len(rows),
            "mrr": sum(reciprocal_rank) / len(rows),
            "p50_ms": median(latency_ms),
            "p95_ms": sorted(latency_ms)[math.ceil(len(rows) * 0.95) - 1],
        }
    print(json.dumps({"queries": len(rows), "k": args.limit, "modes": results}, indent=2))


if __name__ == "__main__":
    main()
