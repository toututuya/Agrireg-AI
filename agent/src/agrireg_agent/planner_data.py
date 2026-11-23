from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from random import Random
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationError

from .models import PlanStep, TaskPlan
from .planner import needs_human_approval, parse_plan, planning_input


TRAIN_ENTITIES = (
    "阿维菌素", "吡虫啉", "吡唑醚菌酯", "氟啶虫胺腈", "吡蚜酮", "噻虫嗪",
    "噻虫胺", "烯酰吗啉", "啶虫脒", "苯醚甲环唑", "草甘膦", "啶酰菌胺",
    "Abamectin", "Fluopyram", "Imidacloprid", "Azoxystrobin",
)
TEST_ENTITIES = ("氯虫苯甲酰胺", "丙硫菌唑", "咯菌腈", "Flonicamid", "Pydiflumetofen", "Tebuconazole")
TRAIN_CROPS = ("水稻", "苹果", "辣椒", "玉米", "梨", "茄子")
TEST_CROPS = ("西葫芦", "大豆", "油菜", "Sorghum", "春大麦", "桃")

KINDS = ("graph", "comparison", "path", "document", "missing_comparison", "missing_path", "compliance")
TRAIN_PHRASES = (
    (
        "查“{left}”的图谱条目", "对比“{left}”和“{right}”", "查“{left}”到“{crop}”的关系路径",
        "找登记证 {reg} 的原文", "把“{left}”做个比较", "查询从“{left}”出发的路径",
        "核验“{left}”的登记是否合规",
    ),
    (
        "图谱里有“{left}”吗？", "“{left}”与“{right}”的关联有何不同？", "“{left}”和“{crop}”怎样在图谱中关联？",
        "{reg} 对应的登记材料在哪里？", "“{left}”有什么差异？", "“{left}”的关系链能查一下吗？",
        "请复核“{left}”是否符合登记要求",
    ),
    (
        "查询“{left}”的实体信息", "麻烦比较“{left}”和“{right}”的图谱信息", "连接“{left}”和“{crop}”的最短路径是什么？",
        "查一下 {reg} 的标签文档", "请比较“{left}”", "检索到“{left}”的最短路径",
        "帮我评估“{left}”的登记合规风险",
    ),
)
TEST_PHRASES = (
    "我想看图谱中关于“{left}”的记录", "把“{left}”跟“{right}”放在一起看区别",
    "给出从“{left}”通往“{crop}”的图谱链路", "我只知道号码 {reg}，请定位登记文件",
    "我想把“{left}”和另一个成分比较", "能从“{left}”追踪一条图谱链吗？",
    "请根据登记材料判断“{left}”的合规性",
)


NonemptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PlannerExample(BaseModel):
    id: NonemptyText
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    plan: TaskPlan
    kind: NonemptyText | None = None
    source: NonemptyText = "labeled"
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
    return {
        "id": example.id, "kind": example.kind or plan.task_type, "source": example.source,
        "question": example.question, "documents_enabled": example.documents_enabled,
        "input": planning_input(example.question, example.documents_enabled),
        "plan": plan.model_dump(mode="json"), "clarification_terms": terms,
    }


def ensure_disjoint(train: list[dict], test: list[dict]) -> None:
    def question_keys(rows: list[dict]) -> set[str]:
        return {"".join(unicodedata.normalize("NFKC", row["question"]).casefold().split()) for row in rows}

    shared_ids = {row["id"] for row in train} & {row["id"] for row in test}
    shared_questions = question_keys(train) & question_keys(test)
    if shared_ids or shared_questions:
        raise ValueError(
            f"Train and test overlap on {len(shared_ids)} IDs and {len(shared_questions)} normalized questions."
        )


def dataset_fingerprint(rows: list[dict]) -> str:
    content = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _label(kind: str, question: str, left: str, right: str, crop: str, reg: str) -> TaskPlan:
    if kind == "missing_comparison":
        return TaskPlan(
            task_type="comparison", summary="确认比较对象", entities=[left],
            missing_information="请提供另一个比较对象。",
        )
    if kind == "missing_path":
        missing = "起点" if "到“" in question else "终点"
        return TaskPlan(
            task_type="relation_path", summary="确认路径两端", entities=[left],
            missing_information=f"请提供路径{missing}实体。",
        )
    if kind == "comparison":
        return TaskPlan(
            task_type="comparison", summary="比较两个有效成分", entities=[left, right],
            steps=[PlanStep(id="compare", title="比较图谱实体", tool="compare_entities", arguments={"left": left, "right": right})],
        )
    if kind == "path":
        return TaskPlan(
            task_type="relation_path", summary="查询图谱关系路径", entities=[left, crop],
            steps=[PlanStep(id="path", title="查询关系路径", tool="find_relation_path", arguments={"source": left, "target": crop})],
        )
    if kind in {"document", "compliance"}:
        args = {"query": question}
        if kind == "document":
            args["registration_number"] = reg
        return TaskPlan(
            task_type="compliance_screen" if kind == "compliance" else "fact_check",
            summary="检索登记文档原文", entities=[reg if kind == "document" else left],
            requires_approval=kind == "compliance",
            steps=[PlanStep(id="doc", title="查找登记文档", tool="search_documents", arguments=args)],
        )
    return TaskPlan(
        task_type="fact_check", summary="检索图谱实体", entities=[left],
        steps=[PlanStep(id="graph", title="检索实体", tool="search_entity", arguments={"keyword": left})],
    )


def make_dataset(split: str, seed: int = 42) -> list[dict]:
    if split not in {"train", "test"}:
        raise ValueError(f"Unknown split {split!r}")
    entities, crops, phrases, first_reg = (
        (TRAIN_ENTITIES, TRAIN_CROPS, TRAIN_PHRASES, 1)
        if split == "train" else (TEST_ENTITIES, TEST_CROPS, (TEST_PHRASES,), 1001)
    )
    rows = []
    for i, left in enumerate(entities):
        reg = f"PD2099{first_reg + i:04d}"
        crop = crops[i % len(crops)]
        for j, variants in enumerate(phrases):
            right = entities[(i + j + 1) % len(entities)]
            for kind, phrase in zip(KINDS, variants, strict=True):
                question = phrase.format(left=left, right=right, crop=crop, reg=reg)
                plan = _label(kind, question, left, right, crop, reg)
                rows.append({
                    "id": f"{split}-{i}-{j}-{kind}", "kind": kind, "source": "synthetic",
                    "question": question, "input": planning_input(question, documents_enabled=True),
                    "plan": plan.model_dump(mode="json"),
                })
    Random(seed).shuffle(rows)
    return rows
