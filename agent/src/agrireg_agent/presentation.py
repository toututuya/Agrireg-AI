from __future__ import annotations

from collections import defaultdict, deque
from html import unescape
from typing import Any


RELATION_LABELS = {
    ("INCLUDES", "RegisterNumber", "ActiveSubstance"): ("有效成分", "的有效成分包括"),
    ("INCLUDES", "ChemicalClasses", "ActiveSubstance"): ("类别成分", "这一化学类别包括有效成分"),
    ("INCLUDES", "PesticideCategory", "ChemicalClasses"): ("化学类别", "这一农药类别包括化学类别"),
    ("APPLIED_TO", "RegisterNumber", "Crop"): ("登记作物", "的登记作物包括"),
    ("TREATS", "RegisterNumber", "Disease"): ("防治对象", "的登记防治对象包括"),
    ("INFECTS", "Disease", "Crop"): ("侵染关联", "的侵染关联作物包括"),
    ("DETERMINES", "ChemicalClasses", "TargetSite"): ("作用靶点", "在图谱中关联作用靶点"),
    ("DETERMINES", "TargetSite", "ModeOfAction"): ("作用方式", "在图谱中关联作用方式"),
}


def relation_terms(relation: str, left: str | None, right: str | None) -> tuple[str, str, bool]:
    direct = RELATION_LABELS.get((relation, left, right))
    if direct:
        return (*direct, False)
    reverse = RELATION_LABELS.get((relation, right, left))
    if reverse:
        return (*reverse, True)
    return "图谱关联", "在图谱中关联", False


def relation_sentence(source: dict[str, Any], relation: str, target: dict[str, Any]) -> str:
    _, predicate, reverse = relation_terms(relation, source.get("label"), target.get("label"))
    if reverse:
        source, target = target, source
    return f"「{source['name']}」{predicate}「{target['name']}」"


def verified_chain(
    data: object, evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    if not isinstance(data, dict) or data.get("found") is not True:
        return None
    source, target = data.get("centerId"), data.get("targetId")
    length = data.get("pathLength")
    if source is None or target is None or source == target or type(length) is not int or not 1 <= length <= 6:
        return None
    by_node_id = {
        str(item["id"]): {"id": str(item["id"]), "name": item["name"], "label": item.get("label") or ""}
        for item in data.get("nodes") or []
        if isinstance(item, dict) and item.get("id") is not None and item.get("name")
    }
    source, target = str(source), str(target)
    adjacent = defaultdict(list)
    for item in evidence:
        if item.get("kind") != "graph_relation" or not item.get("id"):
            continue
        edge = item.get("properties") or {}
        left, right = str(edge.get("source")), str(edge.get("target"))
        if left in by_node_id and right in by_node_id:
            adjacent[left].append((right, item))
            adjacent[right].append((left, item))

    pending = deque([([source], [])])
    visited = {source}
    while pending:
        nodes, edges = pending.popleft()
        if nodes[-1] == target:
            return ([by_node_id[node] for node in nodes], edges) if len(edges) == length else None
        for next_node, edge in adjacent[nodes[-1]]:
            if next_node not in visited:
                pending.append(([*nodes, next_node], [*edges, edge]))
                visited.add(next_node)
    return None


def tool_finding(tool: str, data: Any, evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    if tool == "find_relation_path":
        chain = verified_chain(data, evidence)
        if chain is not None:
            nodes, edges = chain
            return {"path": [node["name"] for node in nodes], "nodes": nodes, "edges": [edge["id"] for edge in edges]}
    if tool == "compare_entities" and isinstance(data, dict):
        centers = [
            str(side["centerId"])
            for key in ("left", "right")
            if isinstance(side := data.get(key), dict) and side.get("centerId") is not None
        ]
        if len(centers) == 2:
            anchors = [next((item for item in evidence if item.get("id") == f"graph-node:{node}"), None)
                       for node in centers]
            if all(anchors):
                details = []
                for center, anchor in zip(centers, anchors):
                    related = [
                        item["id"] for item in evidence if item.get("kind") == "graph_relation"
                        and item.get("id") and any(
                            str(item.get("properties", {}).get(end)) == center for end in ("source", "target")
                        )
                    ]
                    details.append({"anchor": anchor["id"], "related": list(dict.fromkeys(related))[:2]})
                return {"comparison": details}
    return None


def important_evidence(finding: dict[str, Any]) -> list[str]:
    return finding.get("edges", []) + [
        identity for side in finding.get("comparison", []) for identity in [side["anchor"], *side["related"]]
    ]


def report_relation_paths(results: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in evidence if item.get("id")}
    paths = []
    for result in results:
        finding = result.get("finding") or {}
        nodes, edges = finding.get("nodes"), finding.get("edges")
        if not nodes or not edges or len(nodes) != len(edges) + 1 or not all(edge in by_id for edge in edges):
            continue
        links = []
        for left, right, edge in zip(nodes, nodes[1:], edges):
            item = by_id[edge]
            relation = item.get("properties", {}).get("type") or "RELATED_TO"
            label, _, _ = relation_terms(relation, left["label"], right["label"])
            links.append({"label": label, "evidenceIndex": item["index"]})
        arguments = result["step"]["arguments"]
        paths.append({
            "taskId": result.get("task_id"), "source": arguments["source"], "target": arguments["target"],
            "nodes": nodes, "links": links,
        })
    return paths


def evidence_line(item: dict[str, Any], max_chars: int = 250) -> str:
    excerpt = " ".join(unescape(str(item.get("summary", ""))).split())
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars].rstrip() + "…"
    kind = item.get("kind")
    if kind == "document_excerpt":
        excerpt = f"《{item['title']}》摘录：{excerpt}"
    elif item.get("is_center") or str(item.get("id", "")).startswith("graph-node:"):
        label = {"Crop": "作物", "Disease": "病害", "PesticideRegistration": "登记记录",
                 "Registration": "登记记录", "RegisterNumber": "登记记录", "Pesticide": "农药",
                 "ActiveIngredient": "有效成分", "ActiveSubstance": "有效成分"}.get(kind, "图谱条目")
        if kind != "entity_definition":
            excerpt = f"「{item['title']}」（{label}）" + (f"。{excerpt}" if excerpt != "图谱实体记录" else "")
    return f"{excerpt} [{item['index']}]"


def render_finding(finding: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[str]:
    if "path" in finding:
        edges = finding["edges"]
        if not all(edge in by_id for edge in edges):
            return []
        hop = len(edges)
        chain = " → ".join(finding["path"])
        return [
            f"在图谱中找到一条 {hop} 段关系路径。",
            chain,
            *(f"- {evidence_line(by_id[edge])}。" for edge in edges),
        ]
    if "comparison" in finding:
        sides = finding["comparison"]
        if not all(side["anchor"] in by_id for side in sides):
            return []
        if sides[0]["anchor"] == sides[1]["anchor"]:
            item = by_id[sides[0]["anchor"]]
            return [f"这两个查询名称在图谱中指向同一条记录「{item['title']}」[{item['index']}]。"]
        lines = ["两边各查到一个图谱对象，主要区别见各自的属性和关联。"]
        for side in sides:
            lines.append(f"- {evidence_line(by_id[side['anchor']])}")
            lines.extend(f"- {evidence_line(by_id[key])}" for key in side["related"] if key in by_id)
        return lines
    return []
