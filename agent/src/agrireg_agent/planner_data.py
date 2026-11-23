from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationError

from .models import TaskPlan
from .planner import needs_human_approval, parse_plan, planning_input


NonemptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PlannerExample(BaseModel):
    id: NonemptyText
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    plan: TaskPlan
    kind: NonemptyText | None = None
    group_id: NonemptyText | None = None
    source: NonemptyText = "labeled"
    source_ref: NonemptyText | None = None
    documents_enabled: bool = True
    clarification_terms: list[NonemptyText] = Field(default_factory=list)


def default_clarification_terms(text: str) -> list[str]:
    text = text.strip().rstrip("。！？.!?").strip()
    if not text:
        return []
    terms = [term for term in ("比较对象", "起点", "终点", "登记号") if term in text]
    return terms or [text]


def read_dataset(path: Path) -> list[dict]:
    """Load human-reviewed plans and rebuild the input with the deployed planner format."""
    rows = []
    ids = set()
    with path.open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                example = PlannerExample.model_validate_json(line)
            except ValidationError as exc:
                issue = exc.errors(include_input=False, include_url=False)[0]
                location = ".".join(map(str, issue["loc"])) or "record"
                raise ValueError(f"{path}:{number}: {location}: {issue['msg']}") from exc
            if example.id in ids:
                raise ValueError(f"{path}:{number}: duplicate example id {example.id!r}.")
            try:
                row = _training_row(example)
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
            ids.add(example.id)
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: dataset contains no examples.")
    return rows


def _training_row(example: PlannerExample) -> dict:
    gold = example.plan
    missing = gold.missing_information.strip()
    if missing and gold.steps:
        raise ValueError("A clarification label must have an empty steps list.")
    if gold.requires_approval is False and needs_human_approval(example.question, gold):
        raise ValueError("This question requires requires_approval=true.")
    plan = parse_plan(gold, example.question, documents_enabled=example.documents_enabled)
    if plan is None:
        raise ValueError("The plan does not conform to the runtime tool and argument contract.")
    terms = example.clarification_terms or default_clarification_terms(missing)
    if missing and not terms:
        raise ValueError("A clarification label must identify the missing information.")
    if any(term.casefold() not in missing.casefold() for term in terms):
        raise ValueError("clarification_terms must occur in the labeled missing_information.")
    plan.missing_information = missing
    row = {
        "id": example.id, "kind": example.kind or plan.task_type, "source": example.source,
        "question": example.question, "documents_enabled": example.documents_enabled,
        "input": planning_input(example.question, example.documents_enabled),
        "plan": plan.model_dump(mode="json"), "clarification_terms": terms,
    }
    if example.group_id is not None:
        row["group_id"] = example.group_id
    if example.source_ref is not None:
        row["source_ref"] = example.source_ref
    return row


def ensure_disjoint(left: list[dict], right: list[dict]) -> None:
    def question_keys(rows: list[dict]) -> set[str]:
        return {"".join(unicodedata.normalize("NFKC", row["question"]).casefold().split()) for row in rows}

    def group_keys(rows: list[dict]) -> set[str]:
        return {row["group_id"] for row in rows if row.get("group_id")}

    shared_ids = {row["id"] for row in left} & {row["id"] for row in right}
    shared_questions = question_keys(left) & question_keys(right)
    shared_groups = group_keys(left) & group_keys(right)
    if shared_ids or shared_questions or shared_groups:
        raise ValueError(
            f"Datasets overlap on {len(shared_ids)} IDs, {len(shared_questions)} normalized questions, "
            f"and {len(shared_groups)} case groups."
        )


def dataset_fingerprint(rows: list[dict]) -> str:
    content = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
