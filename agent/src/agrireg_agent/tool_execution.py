from __future__ import annotations

from typing import Any, Literal

import httpx

from .documents import _normalize_registration
from .models import PlanStep


MAX_STEP_ATTEMPTS = 3
READ_ONLY_TOOLS = frozenset({
    "search_entity", "compare_entities", "find_relation_path", "external_substance_lookup", "search_documents",
})
ToolOutcome = Literal["ok", "empty", "partial", "unexpected", "failed"]


def retry_delay(step: PlanStep, error: Exception, attempt: int) -> float | None:
    if step.tool not in READ_ONLY_TOOLS or attempt >= MAX_STEP_ATTEMPTS:
        return None
    delay = 0.25 * (2 ** (attempt - 1))
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code not in {408, 429, 500, 502, 503, 504}:
            return None
        retry_after = error.response.headers.get("Retry-After")
        if retry_after:
            if not retry_after.isdecimal() or int(retry_after) > 2:
                return None
            delay = max(delay, int(retry_after))
        return delay
    if isinstance(error, (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError,
                          httpx.RemoteProtocolError)):
        return delay
    return None


def assess_result(step: PlanStep, result: Any) -> tuple[ToolOutcome, list[dict[str, Any]], str]:
    if not isinstance(result, dict) or result.get("tool") != step.tool or not isinstance(result.get("evidence"), list):
        return "unexpected", [], "工具返回的结构不符合约定。"
    raw = result["evidence"]
    if not raw:
        return "empty", [], "未检索到证据。"
    evidence = [
        item for item in raw
        if isinstance(item, dict) and isinstance(item.get("summary"), str) and item["summary"].strip()
        and isinstance(item.get("properties", {}), dict)
    ]
    if not evidence:
        return "unexpected", [], "工具返回了无法核验的证据。"
    registration = step.arguments.get("registration_number")
    if step.tool == "search_documents" and registration:
        expected = _normalize_registration(registration)
        matching = [
            item for item in evidence
            if _normalize_registration(item.get("properties", {}).get("registrationNumber")) == expected
        ]
        if not matching:
            return "unexpected", [], "返回文档与目标登记号不一致。"
        evidence = matching
    if step.tool == "find_relation_path" and not any(item.get("kind") == "graph_relation" for item in evidence):
        return "partial", evidence, "仅查到端点，缺少能证明完整路径的关系。"
    if step.tool == "compare_entities":
        data = result.get("data")
        sides = [data.get(key) for key in ("left", "right")] if isinstance(data, dict) else []
        if len(sides) != 2 or any(not isinstance(side, dict) or not side.get("nodes") for side in sides):
            return "partial", evidence, "比较缺少至少一侧的图谱证据。"
    return "ok", evidence, str(result.get("summary") or "已返回有效证据。")
