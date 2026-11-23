from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal


RECENT_TURNS = 3
SUMMARY_TURNS = 48
PROMPT_MEMORY_CHARS = 1200
LOCAL_TIME = timezone(timedelta(hours=8))
SLOTS = {"登记号": "登记号", "登记证号": "登记号", "作物": "作物", "病害": "病害", "实体": "实体"}
SLOT_NAMES = "|".join(SLOTS)
DAY = r"\d{4}-\d{2}-\d{2}"
REMEMBER = re.compile(
    rf"(?:请\s*)?(?:记住|更正|更新)\s*[:：]?\s*(?:(?:本会话|本线程)(?:的)?\s*)?"
    rf"(?:当前|目标)?(?P<slot>{SLOT_NAMES})\s*(?:改为|为|是|[:：=])?\s*(?P<value>.*?)"
    rf"(?:\s*[，,]?\s*(?:自|从)\s*(?P<valid>{DAY})\s*起(?:生效)?)?"
)
RECALL_SLOT = re.compile(
    rf"(?:按\s*(?P<known>{DAY})\s*当时已知\s*[，,]?\s*)?(?:截至\s*(?P<valid>{DAY})\s*[，,]?\s*)?"
    rf"(?:查看|查询)?\s*(?:(?:本会话|本线程)(?:里|的)?\s*)?(?:当前)?(?:记住的|记忆中的)"
    rf"(?P<slot>{SLOT_NAMES})(?:是啥|是什么|是多少)?"
)
RECALL_TURN = re.compile(r"(?:请\s*)?(?:回顾|查看)\s*(?:第\s*(?P<turn>[1-9]\d{0,5})\s*轮|上一轮)")
RECALL_TOPIC = re.compile(r"(?:请\s*)?(?:回顾|查找本会话中提到的)\s*[「“](?P<value>[^」”\n]{1,80})[」”]")
MEMORY_REFERENCE = re.compile(rf"(?:本会话(?:里|的)?\s*)?(?:记住的|记忆中的)(?P<slot>{SLOT_NAMES})")


@dataclass(frozen=True)
class MemoryCommand:
    kind: Literal["remember", "slot", "turn", "topic", "overview"]
    slot: str = ""
    value: str = ""
    valid_at: str | None = None
    known_at: str | None = None
    turn: int | None = None
    error: str = ""


def utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def day_boundary(value: str | None, *, end: bool) -> str | None:
    if value is None:
        return None
    moment = datetime.combine(date.fromisoformat(value), time.max if end else time.min, LOCAL_TIME)
    return utc_timestamp(moment)


def display_time(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(LOCAL_TIME).isoformat(sep=" ", timespec="seconds")


def clean_subject(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip(" \t\"'「」“”‘’")
    if not 1 <= len(text) <= 80 or re.search(r"[\x00-\x1f；;。？！?!，,:：\"“”「」]", text):
        return ""
    return text


def parse_memory_command(question: str) -> MemoryCommand | None:
    question = question.strip().rstrip("。？！?!").strip()
    if question in {"总结本会话", "回顾本会话"}:
        return MemoryCommand("overview")
    match = RECALL_SLOT.fullmatch(question)
    if match:
        slot = SLOTS[match["slot"]]
        try:
            return MemoryCommand(
                "slot", slot, valid_at=day_boundary(match["valid"], end=True),
                known_at=day_boundary(match["known"], end=True),
            )
        except ValueError:
            return MemoryCommand("slot", slot, error="请提供有效的日期，格式为 YYYY-MM-DD。")
    match = REMEMBER.fullmatch(question)
    if match:
        slot = SLOTS[match["slot"]]
        value = clean_subject(match["value"])
        if slot == "登记号":
            value = value.upper()
            if not re.fullmatch(r"[A-Z0-9-]{2,48}", value) or not re.search(r"[0-9]", value):
                value = ""
        if not value:
            return MemoryCommand("remember", slot, error=f"请提供一个明确的{slot}。")
        try:
            return MemoryCommand("remember", slot, value, valid_at=day_boundary(match["valid"], end=False))
        except ValueError:
            return MemoryCommand("remember", slot, error="请提供有效的生效日期，格式为 YYYY-MM-DD。")
    match = RECALL_TURN.fullmatch(question)
    if match:
        return MemoryCommand("turn", turn=int(match["turn"]) if match["turn"] else None)
    match = RECALL_TOPIC.fullmatch(question)
    if match:
        value = match["value"].strip()
        return MemoryCommand("topic", value=value, error="" if value else "请提供要回顾的主题。")
    return None


def unique_names(values: list[Any], limit: int = 6) -> list[str]:
    names: dict[str, str] = {}
    for value in values:
        name = clean_subject(value) if isinstance(value, str) else ""
        if name:
            names.setdefault(name.casefold(), name)
        if len(names) >= limit:
            break
    return list(names.values())


def recovery_key(tool: str, outcome: str, next_tool: str) -> str:
    return f"{tool}/{outcome}/{next_tool}"


def procedure_results(results: list[dict[str, Any]]) -> dict[str, bool]:
    groups = defaultdict(list)
    for result in results:
        groups[result.get("task_id")].append(result)
    procedures: dict[str, bool] = {}
    for items in groups.values():
        primary, recovery = [], []
        for item in items:
            (recovery if item["step"]["id"].split(":")[-1].startswith("replan-") else primary).append(item)
        failures = [item for item in primary if item["outcome"] != "ok"]
        if len(failures) != 1:
            continue
        failed = failures[0]
        for item in recovery:
            key = recovery_key(failed["step"]["tool"], failed["outcome"], item["step"]["tool"])
            procedures[key] = procedures.get(key, False) or item["outcome"] == "ok"
    return procedures


def capture_episode(state: dict[str, Any]) -> dict[str, Any]:
    plan = state.get("plan") or {}
    task_type = plan.get("task_type")
    if task_type not in {"fact_check", "comparison", "relation_path", "compliance_screen"}:
        task_type = ""
    evidence = state.get("verified_evidence") or []
    names = unique_names([
        value for item in evidence
        for value in (item.get("title"), (item.get("properties") or {}).get("registrationNumber"))
    ], limit=96)
    verified = {name.casefold() for name in names}
    tasks = state.get("subtasks") or []
    if tasks:
        focus = unique_names([name for task in tasks if task["status"] == "completed" for name in task["entities"]])
        can_reference = all(task["status"] == "completed" and task["entities"] for task in tasks)
    else:
        planned = unique_names(plan.get("entities") or [])
        focus = [name for name in planned if name.casefold() in verified]
        if not focus and task_type == "fact_check" and len(planned) == 1:
            focus = unique_names([item.get("title") for item in evidence if item.get("is_center")])
        can_reference = not plan.get("missing_information") and len(planned) == 1 and task_type == "fact_check"
    reference = focus[0] if can_reference and len(focus) == 1 else ""
    reference_kind = next((
        item["kind"] for item in evidence
        if reference and str(item.get("title")).casefold() == reference.casefold()
        and item.get("kind") not in {None, "entity_definition"}
    ), "")
    return {
        "type": "multi_task" if tasks else task_type,
        "entities": focus,
        "reference": reference,
        "reference_kind": reference_kind,
        "evidence_count": len(evidence),
        "procedures": procedure_results(state.get("tool_results") or []),
    }


def prompt_context(turns: list[dict[str, Any]]) -> dict[str, Any]:
    if not turns:
        return {}
    recent = [
        {"question": turn["question"][:160], "type": turn["type"], "entities": turn["entities"]}
        for turn in reversed(turns[:RECENT_TURNS])
    ]
    older = turns[RECENT_TURNS:]
    summary = {
        "entities": unique_names([name for turn in older for name in turn["entities"]]),
        "types": list(dict.fromkeys(turn["type"] for turn in older if turn["type"])),
    }
    context = {"summary": summary, "recent": recent}
    while len(json.dumps(context, ensure_ascii=False, separators=(",", ":"))) > PROMPT_MEMORY_CHARS:
        if summary["entities"]:
            summary["entities"].pop()
        elif len(recent) > 1:
            recent.pop(0)
        else:
            recent[0]["question"] = ""
            recent[0]["entities"] = []
    return context
