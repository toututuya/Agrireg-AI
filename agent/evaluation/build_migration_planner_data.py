"""Build 1,000 planner cases from the registry export of a real Neo4j snapshot."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from random import Random

from agrireg_agent.documents import read_pages
from agrireg_agent.planner import COMPLIANCE_TERMS
from agrireg_agent.planner_data import read_dataset
from agrireg_agent.planner_sft import _write_jsonl

from build_registry_planner_data import GROUPS, PUBCHEM, SEED, write_dataset


def read_registry(directory: Path) -> tuple[dict, dict]:
    receipt = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    rows = {}
    by_name = {name.casefold(): pair for name, pair in PUBCHEM.items()}
    by_name.update({name.casefold(): (name, cid) for name, cid in PUBCHEM.values()})
    with (directory / "planner_records.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            registration = record.pop("registration")
            if registration in rows:
                raise ValueError(f"Repeated registration in the snapshot export: {registration}.")
            record["path_targets"] = [
                target for target in record["path_targets"]
                if 2 <= len(target) <= 80 and target.casefold() != registration.casefold()
                and not COMPLIANCE_TERMS.search(target)
            ]
            for name in record.pop("active_names"):
                if name.casefold() in by_name:
                    record["pubchem_reference"] = by_name[name.casefold()]
                    break
            rows[registration] = record
    if len(rows) != receipt["registrations"]:
        raise ValueError("Planner record count differs from the registry export manifest.")
    return rows, receipt


def primary_source(ordinal: int) -> str:
    if ordinal % 20 == 11:
        return "other"
    if ordinal % 10 == 1:
        return "germany"
    if ordinal % 10 == 6:
        return "eu_mutual_recognition"
    return "china"


def write_retrieval_qrels(source_directory: Path, output: Path, records: dict) -> None:
    document_ids = {page.registration_number: page.document_id for page in read_pages(source_directory / "documents.jsonl")}
    if document_ids.keys() != records.keys():
        raise ValueError("The RAG corpus and planner source must cover the same registrations.")
    by_description = defaultdict(list)
    for reg, record in records.items():
        key = (record["holder"].casefold(), record["product"].casefold())
        by_description[key].append(document_ids[reg])

    exact, keyword = [], []
    for row in read_dataset(output / "test.jsonl"):
        if row["kind"] == "document":
            reg = row["plan"]["steps"][0]["arguments"]["registration_number"]
            exact.append({"query": row["question"], "registration_number": reg, "relevant_document_ids": [document_ids[reg]]})
        elif row["kind"] == "keyword_document":
            product, holder = row["plan"]["entities"]
            query = row["plan"]["steps"][0]["arguments"]["query"]
            keyword.append({"query": query, "relevant_document_ids": sorted(by_description[(holder.casefold(), product.casefold())])})
    _write_jsonl(output / "document_qrels_exact.jsonl", exact)
    _write_jsonl(output / "document_qrels_keyword.jsonl", keyword)


def build(source_directory: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("Choose a new planner dataset directory.")
    records, receipt = read_registry(source_directory)
    ordering = sorted(records)
    Random(SEED).shuffle(ordering)
    candidates = {group: [] for group in receipt["source_groups"]}
    for registration in ordering:
        record = records[registration]
        terms = (record["holder"], record["product"])
        if record["path_targets"] and record["product"] and not any(
            len(value) > 80 or COMPLIANCE_TERMS.search(value) for value in terms
        ):
            candidates[record["source_group"]].append(registration)

    used = set()
    descriptions = set()
    primaries = {split: [] for split in GROUPS}
    for split, count in GROUPS.items():
        for ordinal in range(count):
            group = primary_source(ordinal)
            for registration in candidates[group]:
                record = records[registration]
                description = (record["holder"].casefold(), record["product"].casefold())
                if registration in used or description in descriptions:
                    continue
                if ordinal % 5 == 0 and "pubchem_reference" not in record:
                    continue
                if ordinal % 5 == 3 and not record["holder"]:
                    continue
                primaries[split].append(registration)
                used.add(registration)
                descriptions.add(description)
                break
            else:
                raise ValueError(f"Insufficient matching registry records in {group} for {split} case {ordinal}.")

    remaining = iter(reg for reg in ordering if reg not in used)
    pairs = {split: [(reg, next(remaining)) for reg in registrations] for split, registrations in primaries.items()}
    selected = {reg: records[reg] for part in pairs.values() for pair in part for reg in pair}
    chemicals = {
        name: {"cid": cid, "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"}
        for name, cid in PUBCHEM.values()
    }
    source = {"dump_sha256": receipt["dump_sha256"], "records": selected, "pubchem": chemicals}
    write_dataset(source, output, pairs, {
        "seed": SEED, "dump_sha256": receipt["dump_sha256"], "corpus_registrations": receipt["registrations"],
        "split_policy": "two_unique_registration_ids_per_group_and_disjoint_primary_holder_product_pairs",
    })
    write_retrieval_qrels(source_directory, output, records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_export", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.registry_export, args.output)
