from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings


class DeepSeekClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    @property
    def enabled(self) -> bool:
        return self.settings.deepseek_enabled and bool(self.settings.deepseek_api_key)

    def json_completion(self, system: str, user: str) -> dict[str, Any] | None:
        text = self._completion(system, user, json_mode=True)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None

    def report_completion(self, system: str, user: str) -> str:
        return self._completion(system, user, json_mode=False) or ""

    def _completion(self, system: str, user: str, json_mode: bool) -> str:
        if not self.enabled:
            return ""
        payload: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(
                base_url=self.settings.deepseek_base_url.rstrip("/"),
                timeout=self.settings.request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                return str(response.json()["choices"][0]["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return ""


class ControlledTools:
    """Bounded adapters around the existing Graph API and PubChem PUG REST."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def execute(self, name: str, arguments: dict[str, Any], question: str) -> dict[str, Any]:
        handlers = {
            "search_entity": self.search_entity,
            "compare_entities": self.compare_entities,
            "find_relation_path": self.find_relation_path,
            "grounded_answer": lambda **_: self.grounded_answer(question),
            "external_substance_lookup": self.external_substance_lookup,
        }
        handler = handlers.get(name)
        if handler is None:
            raise ValueError(f"Unsupported controlled tool: {name}")
        return handler(**arguments)

    def search_entity(self, keyword: str) -> dict[str, Any]:
        payload = self._graph_get("/api/graph/search", {"keyword": keyword})
        return self._graph_result("search_entity", payload, [keyword])

    def compare_entities(self, left: str, right: str) -> dict[str, Any]:
        left_payload = self._graph_get("/api/graph/search", {"keyword": left})
        right_payload = self._graph_get("/api/graph/search", {"keyword": right})
        left_result = self._graph_result("search_entity", left_payload, [left])
        right_result = self._graph_result("search_entity", right_payload, [right])
        return {
            "tool": "compare_entities",
            "summary": f"已分别检索 {left} 与 {right} 的有界邻域。",
            "data": {"left": left_payload, "right": right_payload},
            "evidence": left_result["evidence"] + right_result["evidence"],
        }

    def find_relation_path(self, source: str, target: str) -> dict[str, Any]:
        payload = self._graph_get(
            "/api/graph/path", {"source": source, "target": target}
        )
        return self._graph_result("find_relation_path", payload, [source, target])

    def grounded_answer(self, question: str) -> dict[str, Any]:
        payload = self._graph_post("/api/assistant/ask", {"question": question})
        evidence = []
        for index, item in enumerate(payload.get("evidence") or [], start=1):
            evidence.append(
                {
                    "id": f"graphrag:{item.get('index', index)}:{item.get('sourceName', '')}",
                    "source": "GDP-KG GraphRAG",
                    "title": item.get("sourceName") or "图谱关系",
                    "kind": item.get("factType") or "graph_fact",
                    "summary": self._fact_summary(item),
                    "url": "",
                    "properties": item,
                }
            )
        return {
            "tool": "grounded_answer",
            "summary": "已生成图谱约束的初步回答。",
            "data": {"answer": payload.get("answer", "")},
            "evidence": evidence,
        }

    def external_substance_lookup(self, name: str) -> dict[str, Any]:
        endpoint = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            f"{quote(name, safe='')}/property/Title,MolecularFormula,IsomericSMILES/JSON"
        )
        try:
            with httpx.Client(timeout=self.settings.request_timeout_seconds, transport=self.transport) as client:
                response = client.get(endpoint)
                response.raise_for_status()
                rows = response.json().get("PropertyTable", {}).get("Properties", [])[:3]
        except (httpx.HTTPError, ValueError, TypeError):
            rows = []
        evidence = []
        for row in rows:
            cid = row.get("CID")
            evidence.append(
                {
                    "id": f"pubchem:{cid or name}",
                    "source": "PubChem",
                    "title": row.get("Title") or name,
                    "kind": "external_chemical_record",
                    "summary": f"MolecularFormula={row.get('MolecularFormula', '未提供')}",
                    "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else endpoint,
                    "properties": row,
                }
            )
        return {
            "tool": "external_substance_lookup",
            "summary": f"已查询 PubChem：{name}" if rows else f"PubChem 未返回 {name} 的记录。",
            "data": {"name": name, "records": rows},
            "evidence": evidence,
        }

    def _graph_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(
            base_url=self.settings.graph_api_base_url.rstrip("/"),
            timeout=self.settings.request_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    def _graph_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(
            base_url=self.settings.graph_api_base_url.rstrip("/"),
            timeout=max(self.settings.request_timeout_seconds, 45),
            transport=self.transport,
        ) as client:
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

    def _graph_result(self, tool: str, payload: dict[str, Any], terms: list[str]) -> dict[str, Any]:
        evidence: list[dict[str, Any]] = []
        nodes = payload.get("nodes") or []
        names = {str(node.get("id")): node.get("name") or "未知实体" for node in nodes}
        for node in nodes[:16]:
            metadata = node.get("evidence") or {}
            properties = node.get("properties") or {}
            evidence.append(
                {
                    "id": f"graph-node:{node.get('id')}",
                    "source": metadata.get("dataset") or "GDP-KG",
                    "title": node.get("name") or "图谱实体",
                    "kind": node.get("label") or "Entity",
                    "summary": self._properties_summary(properties),
                    "url": metadata.get("sourceUrl") or "",
                    "jurisdiction": metadata.get("jurisdiction") or "",
                    "properties": properties,
                }
            )
        for edge in (payload.get("edges") or [])[:24]:
            source = names.get(str(edge.get("source")), str(edge.get("source")))
            target = names.get(str(edge.get("target")), str(edge.get("target")))
            relation = edge.get("type") or "RELATED_TO"
            evidence.append(
                {
                    "id": f"graph-edge:{edge.get('source')}:{edge.get('target')}:{relation}",
                    "source": "GDP-KG",
                    "title": f"{source} → {target}",
                    "kind": "graph_relation",
                    "summary": f"{source} -[{relation}]-> {target}",
                    "url": "",
                    "properties": edge,
                }
            )
        return {
            "tool": tool,
            "summary": f"图谱检索完成：{' / '.join(terms)}，返回 {len(nodes)} 个实体。",
            "data": payload,
            "evidence": evidence,
        }

    @staticmethod
    def _properties_summary(properties: dict[str, Any]) -> str:
        if not properties:
            return "图谱实体记录"
        return "；".join(f"{key}={value}" for key, value in list(properties.items())[:5])

    @staticmethod
    def _fact_summary(item: dict[str, Any]) -> str:
        if item.get("factType") == "attribute":
            return f"{item.get('sourceName')}：{item.get('property')}={item.get('value')}"
        return (
            f"{item.get('sourceName')} -[{item.get('relation', 'RELATED_TO')}]-> "
            f"{item.get('targetName')}"
        )

