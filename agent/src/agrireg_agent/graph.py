from __future__ import annotations

import json
from typing import Any, Callable, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .clients import ControlledTools, DeepSeekClient
from .models import AgentState, TaskPlan
from .planner import build_plan, compact_plan


REPORT_SYSTEM = """You write concise pesticide knowledge screening reports in Chinese.
Use only the numbered evidence supplied by the user. Cite factual claims as [n].
Separate confirmed findings, conflicting evidence, and unresolved limitations.
Never claim legal approval or replace product labels, regulations, or domain experts.
Do not expose hidden reasoning or chain-of-thought."""


def build_agent_graph(
    tools: ControlledTools,
    llm: DeepSeekClient,
    checkpointer: Any,
):
    def plan_node(state: AgentState) -> dict[str, Any]:
        plan = build_plan(state["question"], bool(state.get("require_approval")), llm)
        return {
            "plan": compact_plan(plan),
            "step_index": 0,
            "status": "planned",
            "events": [event("plan_ready", "已生成分析计划", plan.summary, {"plan": compact_plan(plan)})],
        }

    def plan_route(state: AgentState) -> Literal["clarify", "execute"]:
        plan = TaskPlan.model_validate(state["plan"])
        return "clarify" if plan.missing_information else "execute"

    def clarify_node(state: AgentState) -> dict[str, Any]:
        plan = TaskPlan.model_validate(state["plan"])
        response = interrupt(
            {
                "kind": "clarification",
                "title": "需要补充任务信息",
                "message": plan.missing_information,
            }
        )
        text = response.get("value", "") if isinstance(response, dict) else str(response)
        return {
            "question": f"{state['question']}；补充信息：{text.strip()}",
            "status": "resumed",
            "events": [event("clarification_received", "已收到补充信息", text.strip())],
        }

    def execute_node(state: AgentState) -> dict[str, Any]:
        plan = TaskPlan.model_validate(state["plan"])
        index = int(state.get("step_index", 0))
        step = plan.steps[index]
        try:
            result = tools.execute(step.tool, step.arguments, state["question"])
            tool_event = event(
                "tool_completed",
                step.title,
                result.get("summary", "工具调用完成"),
                {"tool": step.tool, "stepId": step.id},
            )
            return {
                "step_index": index + 1,
                "tool_results": [{"step": step.model_dump(), "result": result}],
                "evidence": result.get("evidence") or [],
                "events": [tool_event],
                "status": "running",
            }
        except Exception as exc:
            return {
                "step_index": index + 1,
                "tool_results": [{"step": step.model_dump(), "error": str(exc)}],
                "events": [event("tool_failed", step.title, friendly_tool_error(step.tool))],
                "status": "running",
            }

    def execute_route(state: AgentState) -> Literal["execute", "verify"]:
        plan = TaskPlan.model_validate(state["plan"])
        return "execute" if int(state.get("step_index", 0)) < len(plan.steps) else "verify"

    def verify_node(state: AgentState) -> dict[str, Any]:
        evidence = deduplicate_evidence(state.get("evidence") or [])
        conflicts = detect_conflicts(evidence)
        coverage = "充分" if len(evidence) >= 4 else "有限" if evidence else "不足"
        detail = f"汇总 {len(evidence)} 条不重复证据，证据覆盖{coverage}。"
        if conflicts:
            detail += f"发现 {len(conflicts)} 组待核对差异。"
        return {
            "verified_evidence": evidence,
            "conflicts": conflicts,
            "coverage": coverage,
            "status": "verified",
            "events": [event("evidence_verified", "证据汇总与冲突检查", detail, {
                "evidenceCount": len(evidence),
                "conflictCount": len(conflicts),
                "coverage": coverage,
                "evidence": [public_evidence(item) for item in evidence],
                "conflicts": conflicts,
            })],
        }

    def verify_route(state: AgentState) -> Literal["approval", "report"]:
        plan = TaskPlan.model_validate(state["plan"])
        return "approval" if plan.requires_approval else "report"

    def approval_node(state: AgentState) -> dict[str, Any]:
        response = interrupt(
            {
                "kind": "approval",
                "title": "确认生成最终筛查报告",
                "message": "证据已汇总。请确认是否基于当前证据生成最终报告。",
                "summary": {
                    "evidenceCount": len(state.get("evidence") or []),
                    "conflictCount": len(state.get("conflicts") or []),
                    "coverage": state.get("coverage", "不足"),
                },
                "allowedDecisions": ["approve", "reject"],
            }
        )
        decision = response.get("decision", response.get("value", "approve")) if isinstance(response, dict) else str(response)
        normalized = "reject" if str(decision).lower() == "reject" else "approve"
        return {
            "approval_decision": normalized,
            "status": "approved" if normalized == "approve" else "rejected",
            "events": [event("approval_received", "人工确认已完成", "已批准生成报告。" if normalized == "approve" else "已拒绝生成结论性报告。", {"decision": normalized})],
        }

    def report_node(state: AgentState) -> dict[str, Any]:
        report = build_report(state, llm)
        return {
            "report": report,
            "status": "completed",
            "events": [event("report_ready", "分析报告已生成", "报告包含结论、编号证据、差异与适用边界。")],
        }

    builder = StateGraph(AgentState)
    builder.add_node("plan", plan_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("execute", execute_node)
    builder.add_node("verify", verify_node)
    builder.add_node("approval", approval_node)
    builder.add_node("report", report_node)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", plan_route)
    builder.add_edge("clarify", "plan")
    builder.add_conditional_edges("execute", execute_route)
    builder.add_conditional_edges("verify", verify_route)
    builder.add_edge("approval", "report")
    builder.add_edge("report", END)
    return builder.compile(checkpointer=checkpointer)


def event(kind: str, title: str, detail: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"kind": kind, "title": title, "detail": detail, "payload": payload or {}}


def deduplicate_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in items:
        key = item.get("id") or (item.get("source"), item.get("title"), item.get("summary"))
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(item)
        normalized["index"] = len(result) + 1
        result.append(normalized)
    return result[:48]


def detect_conflicts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = {
        "molecular_formula": ["MolecularFormula", "Molecular or Experimental Formulas Formul", "Molecular Formula"],
        "cas": ["CAS registry number", "CAS", "CASNumber"],
    }
    conflicts = []
    for field, keys in aliases.items():
        values: dict[str, list[int]] = {}
        for item in evidence:
            properties = item.get("properties") or {}
            for key in keys:
                value = properties.get(key)
                if value not in (None, ""):
                    values.setdefault(str(value).strip(), []).append(int(item.get("index", 0)))
                    break
        if len(values) > 1:
            conflicts.append(
                {
                    "field": field,
                    "values": [{"value": value, "evidence": indexes} for value, indexes in values.items()],
                    "message": f"{field} 在不同来源中存在不一致，需要回到原始登记或权威数据库核对。",
                }
            )
    return conflicts


def public_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": item.get("index"),
        "source": item.get("source", ""),
        "title": item.get("title", ""),
        "kind": item.get("kind", ""),
        "summary": item.get("summary", ""),
        "url": item.get("url", ""),
        "jurisdiction": item.get("jurisdiction", ""),
    }


def build_report(state: AgentState, llm: DeepSeekClient) -> str:
    plan = TaskPlan.model_validate(state["plan"])
    evidence = state.get("verified_evidence") or state.get("evidence") or []
    conflicts = state.get("conflicts") or []
    decision = state.get("approval_decision", "not_required")
    if decision == "reject":
        return "# 分析已停止\n\n你已拒绝生成结论性报告。已检索的证据和执行记录仍保留在任务中，后续可以重新核验。"

    evidence_text = "\n".join(
        f"[{item['index']}] {item.get('source')} | {item.get('title')} | {item.get('summary')} | {item.get('url', '')}"
        for item in evidence
    ) or "没有检索到可用证据。"
    conflict_text = json.dumps(conflicts, ensure_ascii=False)
    model_report = llm.report_completion(
        REPORT_SYSTEM,
        f"任务：{state['question']}\n计划：{plan.summary}\n证据覆盖：{state.get('coverage')}\n"
        f"证据：\n{evidence_text}\n冲突：{conflict_text}",
    )
    if model_report:
        return model_report

    findings = []
    for item in evidence[:8]:
        findings.append(f"- {item.get('summary')} [{item['index']}]")
    conflict_lines = [f"- {item['message']}" for item in conflicts] or ["- 当前自动检查未发现同字段的直接冲突；这不等于来源已完成专家复核。"]
    return (
        f"# {plan.summary}\n\n"
        f"## 任务\n\n{state['question']}\n\n"
        f"## 结论摘要\n\n已完成 {len(plan.steps)} 个受控步骤，汇总 {len(evidence)} 条不重复证据，证据覆盖为“{state.get('coverage', '不足')}”。"
        "以下内容用于知识检索与初步筛查，不构成登记或合规终审。\n\n"
        f"## 主要发现\n\n{chr(10).join(findings) if findings else '- 当前没有足够证据支持具体结论。'}\n\n"
        f"## 差异与待核对项\n\n{chr(10).join(conflict_lines)}\n\n"
        "## 下一步\n\n回到产品标签、登记主管部门原文或权威化学数据库核对关键字段；涉及实际使用或合规判断时由领域人员确认。"
    )


def friendly_tool_error(tool: str) -> str:
    labels = {
        "search_entity": "图谱实体暂时未能读取。",
        "compare_entities": "两个对象的图谱对比暂时未完成。",
        "find_relation_path": "关系路径暂时未能找到。",
        "grounded_answer": "图谱约束问答暂时未能生成。",
        "external_substance_lookup": "外部化学记录暂时未能核验。",
    }
    return labels.get(tool, "这一步暂时未完成。")
