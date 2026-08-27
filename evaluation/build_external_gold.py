#!/usr/bin/env python3
"""Build an authoritative-source candidate set for later expert adjudication."""

import argparse
import csv
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PUBCHEM_COMPOUNDS = [
    ("Chlorantraniliprole", 11271640, "500008-45-7"),
    ("Prothioconazole", 6451142, "178928-70-6"),
    ("Tebuconazole", 86102, "107534-96-3"),
    ("Glyphosate", 3496, "1071-83-6"),
    ("Cypermethrin", 2912, "52315-07-8"),
    ("Azadirachtin", 5281303, "11141-17-6"),
    ("Abamectin", 9920327, "71751-41-2"),
    ("Metaldehyde", 61021, "108-62-3"),
    ("Fenitrothion", 31200, "122-14-5"),
    ("Ethylene", 6325, "74-85-1"),
]

IRAC_SOURCE = "https://irac-online.org/content/uploads/IRAC-MoA_brochure_Ed7.2_13June22.pdf"
FRAC_SOURCE = "https://www.frac.info/docs/default-source/publications/frac-code-list/frac-code-list-2024.pdf"
HRAC_SOURCE = "https://hracglobal.com/files/Global-HRAC-MOA-Classification-Working-Group-Report_June-2020.pdf"

CLASSIFICATION_FACTS = [
    ("Chlorantraniliprole", "IRAC", "28", "p.12 and alphabetical table", IRAC_SOURCE),
    ("Cypermethrin", "IRAC", "3A", "p.7 and alphabetical table", IRAC_SOURCE),
    ("Abamectin", "IRAC", "6", "alphabetical table", IRAC_SOURCE),
    ("Fenitrothion", "IRAC", "1B", "p.7 and alphabetical table", IRAC_SOURCE),
    ("Azadirachtin", "IRAC", "UN", "p.13 and alphabetical table", IRAC_SOURCE),
    ("Prothioconazole", "FRAC", "3", "DMI fungicides, FRAC group 3", FRAC_SOURCE),
    ("Tebuconazole", "FRAC", "3", "DMI fungicides, FRAC group 3", FRAC_SOURCE),
    ("Glyphosate", "HRAC/WSSA", "9", "classification transition table", HRAC_SOURCE),
]

MODE_FACTS = [
    (
        "Chlorantraniliprole", "Ryanodine receptor modulator",
        [["ryanodine receptor", "鱼尼丁受体"]], "IRAC group 28, p.12", IRAC_SOURCE,
    ),
    (
        "Abamectin", "Glutamate-gated chloride channel allosteric modulator",
        [["glutamate", "谷氨酸"], ["chloride channel", "氯离子通道", "氯通道"]],
        "IRAC group 6", IRAC_SOURCE,
    ),
]


def fetch_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AgriReg-Eval/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)
    except Exception as first_error:
        curl = "curl.exe" if os.name == "nt" else "curl"
        completed = subprocess.run(
            [curl, "-fsS", "--retry", "5", "--retry-all-errors", "--retry-delay", "2",
             "--max-time", "60", url], capture_output=True, text=True, encoding="utf-8"
        )
        if completed.returncode != 0:
            raise RuntimeError("PubChem request failed: {} / {}".format(first_error, completed.stderr.strip()))
        return json.loads(completed.stdout)


def case(case_id, category, question, expected, source, accessed_at, verification_status="source_located"):
    return {
        "id": case_id,
        "version": "0.1",
        "category": category,
        "question": question,
        "expected": expected,
        "source": source,
        "sourceVerification": {"status": verification_status, "accessedAt": accessed_at},
        "expertReview": {
            "status": "pending_two_reviewers",
            "reviewer1": None,
            "reviewer2": None,
            "adjudicator": None,
            "reviewedAt": None,
            "notes": None,
        },
    }


def build_cases(delay):
    accessed_at = datetime.now(timezone.utc).isoformat()
    rows = []
    compound_records = []
    cid_list = ",".join(str(item[1]) for item in PUBCHEM_COMPOUNDS)
    property_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/"
        "property/Title,MolecularFormula/JSON".format(cid_list)
    )
    synonyms_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/synonyms/JSON".format(cid_list)
    properties = {
        item["CID"]: item for item in fetch_json(property_url)["PropertyTable"]["Properties"]
    }
    time.sleep(delay)
    synonyms_by_cid = {
        item["CID"]: item.get("Synonym", [])
        for item in fetch_json(synonyms_url)["InformationList"]["Information"]
    }
    for name, cid, expected_cas in PUBCHEM_COMPOUNDS:
        record = properties[cid]
        synonyms = synonyms_by_cid[cid]
        if expected_cas not in synonyms:
            raise RuntimeError("PubChem record for {} does not contain expected CAS {}".format(name, expected_cas))
        compound_records.append({
            "name": name,
            "cid": cid,
            "cas": expected_cas,
            "formula": record["MolecularFormula"],
            "propertyUrl": property_url,
            "synonymsUrl": synonyms_url,
        })

    for record in compound_records:
        rows.append(case(
            "ext-{:03d}".format(len(rows) + 1),
            "chemical_identity_cas",
            "{} 的 CAS 登记号是什么？".format(record["name"]),
            {
                "value": record["cas"],
                "requiredConceptGroups": [[record["cas"]]],
            },
            {
                "authority": "NCBI PubChem",
                "recordId": "CID {}".format(record["cid"]),
                "url": record["synonymsUrl"],
                "humanReadableUrl": "https://pubchem.ncbi.nlm.nih.gov/compound/{}".format(record["cid"]),
                "locator": "Names and Identifiers / CAS",
            },
            accessed_at, "api_record_verified",
        ))
    for record in compound_records:
        rows.append(case(
            "ext-{:03d}".format(len(rows) + 1),
            "chemical_identity_formula",
            "{} 的分子式是什么？".format(record["name"]),
            {
                "value": record["formula"],
                "requiredConceptGroups": [[record["formula"]]],
            },
            {
                "authority": "NCBI PubChem",
                "recordId": "CID {}".format(record["cid"]),
                "url": record["propertyUrl"],
                "humanReadableUrl": "https://pubchem.ncbi.nlm.nih.gov/compound/{}".format(record["cid"]),
                "locator": "Molecular Formula",
            },
            accessed_at, "api_record_verified",
        ))
    for substance, authority, group, locator, url in CLASSIFICATION_FACTS:
        rows.append(case(
            "ext-{:03d}".format(len(rows) + 1),
            "resistance_group",
            "{} 在 {} 作用机制分类中属于哪一组？".format(substance, authority),
            {
                "value": group,
                "requiredConceptGroups": [[authority, authority.split("/")[0]], [group, "Group " + group, group + "组"]],
            },
            {"authority": authority, "recordId": None, "url": url, "locator": locator},
            accessed_at,
        ))
    for substance, value, concept_groups, locator, url in MODE_FACTS:
        rows.append(case(
            "ext-{:03d}".format(len(rows) + 1),
            "mode_of_action",
            "{} 的主要作用机制是什么？".format(substance),
            {"value": value, "requiredConceptGroups": concept_groups},
            {"authority": "IRAC", "recordId": None, "url": url, "locator": locator},
            accessed_at,
        ))
    return rows, compound_records, accessed_at


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_review_csv(path, rows):
    fields = [
        "caseId", "question", "expectedValue", "sourceUrl", "sourceLocator",
        "reviewer1", "reviewer1Decision", "reviewer1Notes",
        "reviewer2", "reviewer2Decision", "reviewer2Notes",
        "adjudicator", "adjudicatedDecision", "adjudicationNotes", "reviewedAt",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "caseId": row["id"], "question": row["question"],
                "expectedValue": row["expected"]["value"], "sourceUrl": row["source"]["url"],
                "sourceLocator": row["source"]["locator"],
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="evaluation/external_gold")
    parser.add_argument("--request-delay", type=float, default=0.22)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, records, accessed_at = build_cases(args.request_delay)
    write_jsonl(output_dir / "external_source_candidates_v0.1.jsonl", rows)
    write_review_csv(output_dir / "expert_review_template_v0.1.csv", rows)
    manifest = {
        "version": "0.1",
        "createdAt": accessed_at,
        "caseCount": len(rows),
        "status": "candidate_external_source_set_pending_expert_review",
        "categories": {
            category: sum(row["category"] == category for row in rows)
            for category in sorted({row["category"] for row in rows})
        },
        "pubchemRecords": [{"name": item["name"], "cid": item["cid"]} for item in records],
        "reviewPolicy": "two independent domain reviewers; disagreements require adjudication",
    }
    (output_dir / "manifest_v0.1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
