from __future__ import annotations

import json
import re
from typing import Any

from .clients import DeepSeekClient
from .models import PlanStep, TaskPlan


PLANNER_SYSTEM = """You plan bounded pesticide knowledge tasks. Return one JSON object only.
Allowed task_type: fact_check, comparison, relation_path, compliance_screen.
Allowed tools: search_entity(keyword), compare_entities(left,right),
find_relation_path(source,target), grounded_answer(), external_substance_lookup(name).
Never propose arbitrary Cypher, shell, file, database or write operations.
Use at most 6 steps. If a comparison or path lacks two clear entities, set missing_information.
Set requires_approval for regulatory/compliance/risk conclusions.
Schema: {task_type, summary, entities, missing_information, requires_approval,
steps:[{id,title,tool,arguments}]}"""


def build_plan(question: str, require_approval: bool, llm: DeepSeekClient) -> TaskPlan:
    candidate = llm.json_completion(PLANNER_SYSTEM, question)
    if candidate:
        try:
            plan = TaskPlan.model_validate(candidate)
            plan.requires_approval = plan.requires_approval or require_approval
            if plan.steps:
                return plan
        except (ValueError, TypeError):
            pass
    return fallback_plan(question, require_approval)


def fallback_plan(question: str, require_approval: bool = False) -> TaskPlan:
    entities = extract_entities(question)
    compliance = bool(re.search(r"合规|风险|禁用|批准|登记|能否使用|是否允许", question, re.I))
    comparison = bool(re.search(r"对比|比较|区别|差异|\bvs\b|与.+相比", question, re.I))
    relation_path = bool(re.search(r"路径|怎么关联|什么关系|关联链|关系链", question, re.I))
    approval = require_approval or compliance

    if comparison:
        missing = "请补充需要比较的两个农药、有效成分或登记产品。" if len(entities) < 2 else ""
        steps = [] if missing else [
            PlanStep(id="compare", title="对比图谱实体与关联", tool="compare_entities", arguments={"left": entities[0], "right": entities[1]}),
            PlanStep(id="external-left", title=f"核验外部化学记录：{entities[0]}", tool="external_substance_lookup", arguments={"name": entities[0]}),
            PlanStep(id="external-right", title=f"核验外部化学记录：{entities[1]}", tool="external_substance_lookup", arguments={"name": entities[1]}),
            PlanStep(id="answer", title="生成图谱约束的对比结论", tool="grounded_answer", arguments={}),
        ]
        return TaskPlan(task_type="comparison", summary="比较两个对象的图谱关系与外部化学记录", entities=entities[:2], missing_information=missing, requires_approval=approval, steps=steps)

    if relation_path:
        missing = "请补充关系路径的起点和终点实体。" if len(entities) < 2 else ""
        steps = [] if missing else [
            PlanStep(id="path", title="检索受限最短关系路径", tool="find_relation_path", arguments={"source": entities[0], "target": entities[1]}),
            PlanStep(id="answer", title="解释关系路径与证据", tool="grounded_answer", arguments={}),
        ]
        return TaskPlan(task_type="relation_path", summary="查找并解释两个实体之间的关系路径", entities=entities[:2], missing_information=missing, requires_approval=approval, steps=steps)

    primary = entities[0] if entities else cleaned_subject(question)
    steps = [PlanStep(id="graph", title=f"检索图谱实体：{primary}", tool="search_entity", arguments={"keyword": primary})]
    if primary and len(primary) <= 80:
        steps.append(PlanStep(id="external", title=f"核验外部化学记录：{primary}", tool="external_substance_lookup", arguments={"name": primary}))
    steps.append(PlanStep(id="answer", title="生成图谱约束的初步结论", tool="grounded_answer", arguments={}))
    return TaskPlan(
        task_type="compliance_screen" if compliance else "fact_check",
        summary="图谱检索、外部来源核验与证据化报告" if compliance else "图谱与外部来源联合核验",
        entities=[primary] if primary else [],
        requires_approval=approval,
        steps=steps,
    )


def extract_entities(question: str) -> list[str]:
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
    return value[:80] or "Chlorantraniliprole"


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
    return json.loads(plan.model_dump_json())
