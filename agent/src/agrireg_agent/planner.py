from __future__ import annotations

import json
import re
from typing import Any, Protocol

from .models import PlanStep, TaskPlan
from .task_queue import CLARIFICATION_SEPARATOR


PLANNER_SYSTEM = """You plan bounded pesticide knowledge tasks. Return one JSON object only.
Allowed task_type: fact_check, comparison, relation_path, compliance_screen.
Allowed tools: search_entity(keyword), compare_entities(left,right),
find_relation_path(source,target), external_substance_lookup(name), and
search_documents(query,registration_number optional) when document_search is enabled.
Never propose arbitrary Cypher, shell, file, database or write operations.
Use at most 6 steps. Copy entity names and registration numbers from the request.
If a comparison or path lacks either entity, ask for that field in missing_information and return no steps.
Use prior thread context only to interpret references, never as evidence.
Set requires_approval for regulatory/compliance/risk conclusions.
Schema: {task_type, summary, entities, missing_information, requires_approval,
steps:[{id,title,tool,arguments}]}"""

TOOL_ARGUMENTS = {
    "search_entity": ({"keyword"}, set()),
    "compare_entities": ({"left", "right"}, set()),
    "find_relation_path": ({"source", "target"}, set()),
    "external_substance_lookup": ({"name"}, set()),
    "search_documents": ({"query"}, {"registration_number"}),
}
REGISTRATION = re.compile(r"(?<![A-Z0-9])(?:PD|WP|LS|WL|EX)\d{5,12}(?![A-Z0-9])", re.I)
DOCUMENT_TERMS = re.compile(r"登记(证|号|文档|内容|材料|资料|有效|状态)|说明书|标签|文件|附件")
COMPLIANCE_TERMS = re.compile(r"合规|风险|禁用|批准|能否使用|是否允许")
FOLLOWUP = re.compile(r"^(?:那[么，, ]*)?(?:它|该产品|这个产品|该成分|该对象|上一个)")
REGISTRATION_FIELD = r"(?:登记(?:证)?(?:编)?号|证号)"
MIGRATION_REGISTRATION = r"(?:\d{2}[A-Z0-9]\d{3}-\d{2}|\d{4}(?:-\d{1,3})?)"
NAMED_MIGRATION_REGISTRATION = re.compile(
    rf"{REGISTRATION_FIELD}\s*(?:为|是|[：:])?\s*[“\"']?({MIGRATION_REGISTRATION})(?![A-Z0-9-])", re.I,
)
HYPHENATED_REGISTRATION = re.compile(r"(?<![A-Z0-9-])(?:\d{2}[A-Z0-9]\d{3}-\d{2}|\d{4}-\d{3})(?![A-Z0-9-])", re.I)
DOCUMENT_CONTENT = re.compile(r"原文|文件|文档|附件|材料|资料|标签|说明书")
EXACT_REGISTRATION_REQUEST = re.compile(
    rf"精[确准]|按(?:实际|目标|具体)?{REGISTRATION_FIELD}|(?:实际|目标|具体)(?:的)?{REGISTRATION_FIELD}|一张(?:登记)?证"
)
MISSING_REGISTRATION_FIELD = re.compile(
    rf"{REGISTRATION_FIELD}\s*(?:我\s*)?(?:还(?:没|未)(?:[填发给贴]|提[供交])|"
    r"尚未(?:填|发|给|提供|指定)|未(?:填|发|给|提供|指定)|没(?:填|发|给|提供)|稍后(?:补|发|提供)|空着|待补)"
    rf"|(?:等我|待我)补(?:上|发|充)?(?:实际|目标|具体)?(?:的)?{REGISTRATION_FIELD}"
)
OPTIONAL_REGISTRATION_FIELD = re.compile(rf"(?:不[用按限]|无需|无须)(?:按|使用|限定)?{REGISTRATION_FIELD}")
ILLUSTRATIVE_REGISTRATION = re.compile(r"示例|举例|例如|比如|仅供参考|例子|演示格式")
EXCLUDED_REGISTRATION = re.compile(r"(?:排除|忽略|跳过|不查|除去|剔除)\s*(?:(?:登记(?:证)?号|证号)\s*)?[“\"']?[A-Z0-9]", re.I)


class PlannerModel(Protocol):
    def json_completion(self, system: str, user: str) -> dict[str, Any] | None: ...


def planning_input(question: str, documents_enabled: bool, context: dict[str, Any] | None = None) -> str:
    return json.dumps({
        "question": question,
        "document_search": documents_enabled,
        "thread_context": context or {},
    }, ensure_ascii=False, separators=(",", ":"))


def needs_human_approval(question: str, plan: TaskPlan) -> bool:
    return plan.task_type == "compliance_screen" or bool(COMPLIANCE_TERMS.search(question))


def parse_plan(candidate: Any, question: str, documents_enabled: bool) -> TaskPlan | None:
    try:
        plan = TaskPlan.model_validate(candidate)
    except (ValueError, TypeError):
        return None
    if plan.missing_information.strip():
        return plan.model_copy(update={"steps": []})
    if not plan.steps or not plan.summary.strip() or len({step.id for step in plan.steps}) != len(plan.steps):
        return None
    entities = {entity.strip().casefold() for entity in plan.entities}
    if plan.task_type in {"comparison", "relation_path"}:
        if len(entities) != 2 or not all(entity and entity in question.casefold() for entity in entities):
            return None
    for step in plan.steps:
        contract = TOOL_ARGUMENTS.get(step.tool)
        if contract is None or (step.tool == "search_documents" and not documents_enabled):
            return None
        required, optional = contract
        keys = step.arguments.keys()
        if not required <= keys <= required | optional:
            return None
        for key, value in step.arguments.items():
            max_length = {"query": 512, "registration_number": 64}.get(key, 80)
            if not isinstance(value, str) or len(value.strip()) > max_length or (key in required and not value.strip()):
                return None
            if key in {"left", "right", "source", "target"} and value.strip().casefold() not in entities:
                return None
            if key == "registration_number" and value.strip() and value.strip().casefold() not in question.casefold():
                return None
            step.arguments[key] = value.strip()
        if step.tool in {"compare_entities", "find_relation_path"} and len(set(step.arguments.values())) != 2:
            return None
    return plan


def build_plan(
    question: str, require_approval: bool, llm: PlannerModel,
    documents_enabled: bool = False, context: dict[str, Any] | None = None,
) -> TaskPlan:
    recent = (context or {}).get("recent") or []
    if FOLLOWUP.match(question) and recent:
        entities = recent[-1]["entities"]
        if len(entities) == 1:
            question = FOLLOWUP.sub(entities[0], question, count=1)
    exact = plan_explicit_missing_registration(question, require_approval) if documents_enabled else None
    if exact is not None:
        return exact
    candidate = llm.json_completion(PLANNER_SYSTEM, planning_input(question, documents_enabled, context))
    plan = parse_plan(candidate, question, documents_enabled)
    if plan is None:
        return fallback_plan(question, require_approval, documents_enabled)
    registration = requested_document_registration(question) if documents_enabled else ""
    if registration:
        for step in plan.steps:
            if step.tool == "search_documents":
                step.arguments["registration_number"] = registration
    plan.requires_approval = plan.requires_approval or require_approval or needs_human_approval(question, plan)
    return plan


def plan_explicit_missing_registration(question: str, require_approval: bool) -> TaskPlan | None:
    original, *supplements = question.split(CLARIFICATION_SEPARATOR)
    if (
        not DOCUMENT_CONTENT.search(original) or not EXACT_REGISTRATION_REQUEST.search(original)
        or not MISSING_REGISTRATION_FIELD.search(original) or OPTIONAL_REGISTRATION_FIELD.search(original)
    ):
        return None
    compliance = bool(COMPLIANCE_TERMS.search(question))
    task_type = "compliance_screen" if compliance else "fact_check"
    approval = require_approval or compliance
    if supplements:
        latest = supplements[-1]
        supplied = _unique([match.group().upper() for match in REGISTRATION.finditer(latest)])
        supplied = _unique(supplied + NAMED_MIGRATION_REGISTRATION.findall(latest.upper()))
        bare = latest.strip(" 。？！.!?‘’“”\"'").upper()
        if not supplied and re.fullmatch(MIGRATION_REGISTRATION, bare):
            supplied = [bare]
        if len(supplied) == 1 and not (ILLUSTRATIVE_REGISTRATION.search(latest) or MISSING_REGISTRATION_FIELD.search(latest)):
            registration = supplied[0]
            return TaskPlan(
                task_type=task_type, summary="按补充的目标登记证号检索登记资料", entities=[registration],
                requires_approval=approval, steps=[PlanStep(
                    id="documents", title="检索登记资料", tool="search_documents",
                    arguments={"query": registration, "registration_number": registration},
                )],
            )
    return TaskPlan(
        task_type=task_type, summary="确认要查询的登记证号", requires_approval=approval,
        missing_information="请补充要查询的目标登记证号。",
    )


def fallback_plan(question: str, require_approval: bool = False, documents_enabled: bool = False) -> TaskPlan:
    entities = extract_entities(question)
    compliance = bool(COMPLIANCE_TERMS.search(question))
    comparison = bool(re.search(r"对比|比较|区别|差异|\bvs\b|与.+相比", question, re.I))
    relation_path = bool(re.search(r"路径|怎么关联|什么关系|关联链|关系链", question, re.I))
    approval = require_approval or compliance

    if comparison:
        missing = "请补充另一个比较对象。" if len(entities) == 1 else "请提供两个比较对象。" if not entities else ""
        steps = [] if missing else [
            PlanStep(id="compare", title="对比图谱实体与关联", tool="compare_entities", arguments={"left": entities[0], "right": entities[1]}),
            PlanStep(id="external-left", title=f"核验外部化学记录：{entities[0]}", tool="external_substance_lookup", arguments={"name": entities[0]}),
            PlanStep(id="external-right", title=f"核验外部化学记录：{entities[1]}", tool="external_substance_lookup", arguments={"name": entities[1]}),
        ]
        return TaskPlan(task_type="comparison", summary="比较两个对象的图谱关系与外部化学记录", entities=entities[:2], missing_information=missing, requires_approval=approval, steps=steps)

    if relation_path:
        missing = "请补充路径的另一个实体。" if len(entities) == 1 else "请提供路径的起点和终点。" if not entities else ""
        steps = [] if missing else [
            PlanStep(id="path", title="检索受限最短关系路径", tool="find_relation_path", arguments={"source": entities[0], "target": entities[1]}),
        ]
        return TaskPlan(task_type="relation_path", summary="查找并解释两个实体之间的关系路径", entities=entities[:2], missing_information=missing, requires_approval=approval, steps=steps)

    registration = registration_value(question)
    primary = registration if registration else entities[0] if entities else cleaned_subject(question)
    if not primary or FOLLOWUP.match(question):
        return TaskPlan(
            task_type="compliance_screen" if compliance else "fact_check", summary="确认需要查询的对象",
            missing_information="请提供要查询的农药、有效成分或登记号。", requires_approval=approval,
        )
    steps = [PlanStep(id="graph", title=f"检索图谱实体：{primary}", tool="search_entity", arguments={"keyword": primary})]
    if documents_enabled and (registration or compliance or DOCUMENT_TERMS.search(question)):
        steps.insert(0, document_step(question))
    if not registration and not DOCUMENT_TERMS.search(question):
        steps.append(PlanStep(id="external", title=f"核验外部化学记录：{primary}", tool="external_substance_lookup", arguments={"name": primary}))
    return TaskPlan(
        task_type="compliance_screen" if compliance else "fact_check",
        summary="图谱检索、外部来源核验与证据化报告" if compliance else "图谱与外部来源联合核验",
        entities=[primary] if primary else [],
        requires_approval=approval,
        steps=steps,
    )


def extract_entities(question: str) -> list[str]:
    segments = question.split(CLARIFICATION_SEPARATOR)
    if len(segments) > 1:
        return _unique([entity for segment in segments for entity in extract_entities(segment)])[:4]
    quoted = re.findall(r"[‘’'\"“”]([^‘’'\"“”]{2,80})[‘’'\"“”]", question)
    if quoted:
        return _unique(quoted)[:4]

    latin = re.findall(r"\b[A-Za-z][A-Za-z0-9-]{2,}(?:\s+[A-Za-z][A-Za-z0-9-]{2,}){0,2}\b", question)
    if latin:
        return _unique(latin)[:4]

    separators = re.split(r"\s+(?:vs\.?|VS\.?)\s+|与|和|、|→|->|到", question)
    cleaned = []
    for part in separators:
        value = re.sub(
            r"^(请|帮我|分析|检查|查询|比较|对比|看看|核验)+|"
            r"(之间|的关系路径|有什么关系|什么关系|有何区别|的区别|是否合规|能否使用).*$",
            "",
            part.strip(" ，。！？?"),
            flags=re.I,
        ).strip()
        if 2 <= len(value) <= 80:
            cleaned.append(value)
    return _unique(cleaned)[:4]


def cleaned_subject(question: str) -> str:
    value = re.sub(r"^(请|帮我|分析|查询|核验|介绍|看看)+", "", question.strip(), flags=re.I)
    value = re.split(r"与哪些|有哪些|关联|可以|用于|是否|能否|的作用|的风险", value, maxsplit=1)[0]
    value = re.sub(r"[？?。！!].*$", "", value).strip()
    return value[:80]


def registration_value(question: str) -> str:
    chinese = REGISTRATION.search(question)
    if chinese:
        return chinese.group().upper()
    named = NAMED_MIGRATION_REGISTRATION.search(question)
    return named.group(1).upper() if named else ""


def requested_document_registration(question: str) -> str:
    if (
        OPTIONAL_REGISTRATION_FIELD.search(question) or ILLUSTRATIVE_REGISTRATION.search(question)
        or EXCLUDED_REGISTRATION.search(question)
    ):
        return ""
    text = question.upper()
    matches = _unique(REGISTRATION.findall(text) + HYPHENATED_REGISTRATION.findall(text)
                      + NAMED_MIGRATION_REGISTRATION.findall(text))
    return matches[0] if len(matches) == 1 else ""


def document_step(question: str) -> PlanStep:
    arguments = {"query": question[:512]}
    registration = requested_document_registration(question)
    if registration:
        arguments["registration_number"] = registration
    return PlanStep(id="documents", title="检索登记资料", tool="search_documents", arguments=arguments)


def followup_steps(
    question: str, tool_results: list[dict[str, Any]], documents_enabled: bool, remaining: int,
) -> list[PlanStep]:
    if remaining < 1:
        return []
    def signature(step: PlanStep) -> tuple:
        return step.tool, tuple(sorted((name, str(value).strip().casefold()) for name, value in step.arguments.items()))

    attempted = {signature(PlanStep.model_validate(item["step"])) for item in tool_results}
    candidates: list[PlanStep] = []
    for item in tool_results:
        evidence_count = item.get("evidence_count", len(item.get("result", {}).get("evidence") or []))
        if item.get("outcome", "ok" if evidence_count else "empty") == "ok":
            continue
        step = PlanStep.model_validate(item["step"])
        args = step.arguments
        if step.tool in {"find_relation_path", "compare_entities"}:
            for entity in args.values():
                candidates.append(PlanStep(
                    id="followup", title=f"补查单个图谱实体：{entity}", tool="search_entity",
                    arguments={"keyword": entity},
                ))
        if step.tool in {"search_entity", "find_relation_path", "compare_entities"} and documents_enabled:
            candidates.append(document_step(question))
        if step.tool == "search_documents" and args.get("registration_number"):
            candidates.append(PlanStep(
                id="followup", title="按登记号补查图谱", tool="search_entity",
                arguments={"keyword": args["registration_number"]},
            ))
    result = []
    for step in candidates:
        key = signature(step)
        if key not in attempted:
            attempted.add(key)
            result.append(step.model_copy(update={"id": f"replan-{len(result) + 1}"}))
        if len(result) == min(remaining, 2):
            break
    return result


def _unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def compact_plan(plan: TaskPlan) -> dict[str, Any]:
    return plan.model_dump(mode="json")
