from __future__ import annotations

import logging
import re
from collections.abc import Callable
from html import unescape
from typing import Any

import httpx

from .clients import ControlledTools
from .documents import CHUNK_LENGTH, CHUNK_OVERLAP
from .models import PlanStep
from .planner import (
    COMPLIANCE_TERMS, DOCUMENT_CONTENT, HYPHENATED_REGISTRATION, REGISTRATION, REGISTRATION_FIELD,
    requested_document_registration,
)
from .tool_execution import assess_result


logger = logging.getLogger(__name__)
SOURCE_REQUIRED = re.compile(
    rf"{REGISTRATION_FIELD}|登记(?:状态|效期|作物|企业|有效|有效期|范围|信息|资料)|"
    r"禁[限用]|可以.{0,12}(?:用|喷|施)|(?:能不能|可否|可不可以|可用|适用|能用|能否用|该用)"
    r".{0,12}(?:药|喷|施|用|作物)|用[量法药]|剂量|稀释|配比|浓度|施[药用]|喷[洒药施]|"
    r"混配|桶混|一起(?:打|用|喷|施)|用什么药|什么药有效|推荐.{0,8}(?:药|杀菌剂)|"
    r"防治(?:建议|用药|方案)|安全间隔|休药期|风险|毒性|"
    r"是否.{0,4}(?:合规|允许|登记|合法|适用)|哪(?:些|种|款).{0,8}(?:农药|药剂|杀菌剂)|"
    r"\b(?:dosage|dilute|dilution|approved|application rate|legal|registered|toxicity|restricted|mixing|"
    r"pesticide recommendation|pesticide label)\b",
    re.I,
)
APPLIED_INSTRUCTIONS = re.compile(
    r"(?:\d\s*(?:倍液|毫升|升|克|公斤|g/|ml/|mL/|kg/|%))|"
    r"(?:推荐|建议|可以|允许|采用|使用).{0,12}(?:剂量|用量|稀释液|施用农药|喷洒|混配|登记作物)|"
    r"(?:目前|已经).{0,8}(?:获准|禁用|已登记)|\[\d+\]|https?://",
    re.I,
)
GENERAL_SYSTEM = (
    "用一两句中文直接解释用户问到的通用概念，约120字。必要时给一个简短例子。"
    "避免引用、虚构文献、当前登记或政策判断、农药使用建议、剂量和专有查询结果。"
    "若无法可靠解释，只输出「无法可靠回答」。"
)
SNAPSHOT_FIELDS = {
    "图谱关联作物": "适用作物|登记作物|什么作物|哪些作物|作物是",
    "图谱关联防治对象": "防治对象|哪些病虫害|哪些病害",
    "有效成分": "有效成分|什么成分|哪些成分",
    "持有人": "持有人|登记企业",
    "登记辖区": "登记国家|登记地区|登记辖区",
    "有效期（快照）": "有效期|到期",
    "登记状态（快照）": "登记状态|现在有效|是否有效",
}
AnswerModel = Callable[[str, str], str | None]


def explain_general(question: str, complete: AnswerModel | None) -> str | None:
    if complete is None or needs_registry_source(question):
        return None
    text = complete(GENERAL_SYSTEM, question)
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if not text or text.strip("「」。") == "无法可靠回答" or "<think" in text or APPLIED_INSTRUCTIONS.search(text):
        return None
    return f"通用知识说明（Qwen3）\n\n{text}"


def answer_without_graph(question: str, tools: ControlledTools, complete: AnswerModel | None) -> dict[str, Any]:
    registration = requested_document_registration(question)
    if registration:
        step = PlanStep(
            id="documents", title="检索登记原文", tool="search_documents",
            arguments={"query": question[:512], "registration_number": registration},
        )
        evidence = []
        if tools.settings.milvus_uri:
            try:
                result = tools.search_documents(**step.arguments)
                _, evidence, _ = assess_result(step, result)
            except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
                logger.warning("Answer document search unavailable: %s", type(exc).__name__)
                return answer_payload("登记文档暂时无法读取。请稍后重试。", "unavailable")
        if evidence:
            return document_answer(question, registration, evidence)
        return answer_payload(f"暂时没有查到登记号 {registration} 的可引用资料。具体登记事项仍待核实。", "unsupported")
    if needs_registry_source(question):
        followup = "请提供目标登记号或产品标签，以便核对原文。" if DOCUMENT_CONTENT.search(question) else (
            "请补充具体产品和登记号，以便找到可以核对的依据。"
        )
        return answer_payload(f"这项问题需要核对登记或标签依据。{followup}", "unsupported")
    answer = explain_general(question, complete)
    if answer:
        return answer_payload(answer, "general", "qwen3-base")
    return answer_payload("目前没有足够证据回答这个问题。可以补充对象名称或登记号。", "unavailable")


def needs_registry_source(question: str) -> bool:
    return any(pattern.search(question) for pattern in (
        SOURCE_REQUIRED, COMPLIANCE_TERMS, REGISTRATION, HYPHENATED_REGISTRATION,
    ))


def answer_payload(answer: str, mode: str, model: str = "") -> dict[str, Any]:
    return {"answer": answer, "mode": mode, "model": model, "grounded": False, "evidence": [], "followUps": []}


def join_snapshot_chunks(hit: dict[str, Any], hits: list[dict[str, Any]]) -> tuple[str, bool]:
    metadata = hit.get("properties", {})
    parts = {
        candidate["summary"] for candidate in hits if all(
            candidate.get("properties", {}).get(key) == metadata.get(key)
            for key in ("documentId", "version", "section", "page")
        )
    }
    tail = content = hit["summary"]
    parts.discard(tail)
    while len(tail) >= CHUNK_OVERLAP:
        overlap = tail[-CHUNK_OVERLAP:]
        continuations = [part for part in parts if part.startswith(overlap) and len(part) > CHUNK_OVERLAP]
        if len(continuations) != 1:
            break
        tail = continuations[0]
        content += tail[CHUNK_OVERLAP:]
        parts.remove(tail)
    return content, len(tail) >= CHUNK_LENGTH


def document_answer(question: str, registration: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    selected = hits[:2]
    snapshots = [
        str(item.get("properties", {}).get("documentId", "")).startswith("neo4j-register-") for item in selected
    ]
    if all(snapshots):
        lines = [f"查到登记号 {registration} 的登记数据快照。原始文件和现行标签仍待核对。"]
    else:
        lines = [f"查到登记号 {registration} 的相关登记资料。"]
    fields = {field for field, trigger in SNAPSHOT_FIELDS.items() if re.search(trigger, question)}
    shown_fields: set[str] = set()
    for index, (hit, snapshot) in enumerate(zip(selected, snapshots), 1):
        raw, truncated = join_snapshot_chunks(hit, hits) if snapshot and fields else (hit["summary"], False)
        source_lines = unescape(raw).splitlines()
        focused = []
        for line_number, line in enumerate(source_lines):
            field = line.partition("：")[0]
            if not snapshot or field not in fields or field in shown_fields:
                continue
            shown_fields.add(field)
            if truncated and line_number == len(source_lines) - 1:
                line = (line.rpartition("、")[0] or line) + "…"
            focused.append(line)
        excerpt = "。".join(focused) if focused else " ".join(unescape(hit["summary"]).split())
        text = excerpt[:420].rstrip() + ("…" if len(excerpt) > 420 else "")
        title = hit.get("title") or "登记资料"
        if focused or not snapshot or not fields:
            lines.append(f"《{title}》\n{text} [{index}]")
        evidence.append({
            "index": index, "factType": "document", "sourceName": title,
            "sourceTitle": title, "sourceUrl": hit.get("url", ""),
            "relation": "登记快照" if snapshot else "文档摘录", "targetName": text,
        })
    if fields and all(snapshots) and not shown_fields:
        lines.append("检索到的快照缺少所问的字段。")
    return answer_payload("\n\n".join(lines), "document", "registry-retrieval") | {
        "grounded": True, "evidence": evidence,
    }
