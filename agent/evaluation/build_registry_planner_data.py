"""Build a versioned planner dataset from the Ministry's public registration bulletin."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from agrireg_agent.planner import REGISTRATION
from agrireg_agent.planner_data import dataset_fingerprint, ensure_disjoint, read_dataset
from agrireg_agent.planner_sft import _write_jsonl


ANNOUNCEMENT = "https://zzys.moa.gov.cn/gzjl/202607/t20260729_6486303.htm"
WORKBOOK_URL = "https://zzys.moa.gov.cn/gzjl/202607/P020260729578096144904.xls"
WORKBOOK_SHA256 = "8a550114a1e68bd3d9b8076a0b8b8e24cd2f5872651586e67528a1cf4563b31e"
SEED = 42
GROUPS = {"train": 140, "dev": 20, "test": 40}
PUBCHEM = {
    "呋虫胺": ("Dinotefuran", 197701),
    "氯虫苯甲酰胺": ("Chlorantraniliprole", 11271640),
    "吡唑醚菌酯": ("Pyraclostrobin", 6422843),
    "氟吡菌酰胺": ("Fluopyram", 11158353),
    "噻虫嗪": ("Thiamethoxam", 5821911),
    "溴氰虫酰胺": ("Cyantraniliprole", 11578610),
    "阿维菌素": ("Abamectin", 9920327),
}

# Each scenario has two train, two dev and two test prompt templates.
QUESTIONS = {
    "document": (
        "根据证号 {reg} 给我定位这份登记附件原文。",
        "请直接按登记证号 {reg} 筛登记文档。",
        "只保留登记号为 {reg} 的原始登记材料。",
        "登记文档按证号精确过滤，目标是 {reg}。",
        "能从登记材料中找出编号 {reg} 对应的那份原文吗？",
        "我核对的是 {reg} 这一张证，请返回它对应的登记附件。",
    ),
    "missing_registration": (
        "要找“{holder}”的“{product}”登记材料，必须按证号筛，但我还没贴证号。",
        "我想精确定位“{holder}”的某份登记文件。{other} 是别人的示例，目标证号我还没给。",
        "帮忙按证号锁定“{holder}”的“{product}”登记证。具体登记号我稍后发。",
        "要查“{holder}”的登记原文，系统要求指定证号；{other} 是用来演示格式的另一条。",
        "请等我补上实际的证号，再精准检索“{product}”的登记附件。{other} 只是前一份记录。",
        "“{holder}”的“{product}”登记材料里我只需要其中一张证的原文，目标登记号没填。",
    ),
    "comparison": (
        "仅用图谱先查登记证 {reg}，再和 {other} 做对比。",
        "比较“{reg}”与“{other}”的图谱邻域，仅查平台图谱。",
        "把图谱里 {reg} 和 {other} 两条登记记录并列比较。",
        "图谱对照检查：左边 {reg}，右边 {other}。",
        "只看图谱，把登记号 {reg} 放左边、{other} 放右边，看看两条有哪些差异。",
        "不查外网。请把 {reg} 和 {other} 这两张登记证的图谱条目放在一起比对。",
    ),
    "missing_comparison": (
        "要做图谱登记证对比，第一张证是 {reg}，另一张的登记证号还没给。",
        "用图谱对照“{reg}”和另一张登记证，我只填了左侧的编号。",
        "想并排看两张登记证的图谱差异，已知基准条目为 {reg}。",
        "图谱对比的一边锁定 {reg}，另一张证等我提供编号。",
        "打算把 {reg} 和另一份指定的登记证放在图谱里比较，对方编号还空着。",
        "能帮我对比两条登记记录吗？目前我只知道其中一条的登记号 {reg}。",
    ),
    "path": (
        "走图谱，找从登记证 {reg} 到持有人“{holder}”的关系路径。",
        "查询“{reg}”和“{holder}”之间的图谱关系链，从证号出发。",
        "以登记证 {reg} 为起点，以“{holder}”为终点，查关系路径。",
        "图谱路径查询，从 {reg} 出发连到登记持有人“{holder}”。",
        "给我图谱里从证号 {reg} 连向持有人“{holder}”的那条链路。",
        "在图谱中，从“{reg}”沿关系怎样走到“{holder}”？",
    ),
    "missing_path": (
        "查从登记证 {reg} 出发的图谱关系路径，终点持有人还没告诉你。",
        "想沿图谱从“{reg}”连到一家持有人公司，我没有填公司名称。",
        "我知道图谱关系链的起点是 {reg}，终点是持有人但还未指定名称。",
        "从登记 {reg} 查一条到持有人的图谱路径。我接下来再给具体持有人。",
        "准备从 {reg} 走图谱查路径，终点要用持有人全称，这个我稍后发。",
        "请帮我查图谱关联链，起点已定为“{reg}”，另一端的持有人名称空着。",
    ),
    "external": (
        "登记号 {reg} 只是背景。单查 PubChem 中“{compound}”的记录。",
        "看 {reg} 的登记时遇到“{compound}”，请只用 PubChem 核验化学条目。",
        "这次用外部来源，在 PubChem 搜“{compound}”，{reg} 仅供背景参考。",
        "我手边证号是 {reg}，这次只打开 PubChem 查化学品“{compound}”。",
        "麻烦到 PubChem 看“{compound}”的化学条目；我不需要查 {reg} 这张登记证。",
        "登记文件编号 {reg} 先放一边。我想要“{compound}”在 PubChem 的记录。",
    ),
    "graph": (
        "现在文档库不可用，直接在图谱里查登记实体 {reg}。",
        "只用图谱检索“{reg}”这个登记证节点。",
        "有证号 {reg}，帮我翻一下平台图谱中的条目。",
        "关闭文档检索时，请走图谱找登记实体 {reg}。",
        "请把图谱中编号为 {reg} 的实体记录给我看。",
        "今天文档入口关着，帮我从图谱中找“{reg}”。",
    ),
    "compliance": (
        "请为 {reg} 的登记合规复核准备附件和图谱条目，最终交人工确认。",
        "需要检查 {reg} 的登记合规性，先调出登记文件和图谱证据，之后由人工确认。",
        "预审登记 {reg} 的合规材料，同时查登记附件和图谱，结果交人工复核。",
        "按 {reg} 做一份合规复核准备，请把文档和图谱证据汇集起来，等人工确认。",
        "我要复核登记号 {reg} 的合规性，先收集对应文档和图谱记录供人工复核。",
        "请先找 {reg} 的登记文件和图谱证据，合规结论留给审核人确认。",
    ),
    "keyword_document": (
        "没有固定证号。按“{holder}”和产品“{product}”关键词搜登记附件。",
        "对“{holder}”的“{product}”做登记文档关键词检索，不限定证号。",
        "用产品“{product}”加持有人“{holder}”搜原始登记材料即可。",
        "去文档库搜“{product}”，加上“{holder}”一起匹配，无需限定到一张证。",
        "我只知道持有人“{holder}”和产品“{product}”，烦请用这两个词找公开登记文件。",
        "不用按号过滤，帮我在登记附件里找“{holder}”的“{product}”。",
    ),
    "joint_lookup": (
        "先找 {reg} 的登记原文，随后查图谱里同号的实体。",
        "两步都做：按 {reg} 查登记附件，然后去图谱找这张证。",
        "先拿到证号 {reg} 的附件，再补一条图谱证据。",
        "请先走文档库精确查 {reg}，再走图谱核对该登记记录。",
        "请把 {reg} 的登记原文和图谱记录都调出来，按原文、图谱的顺序进行。",
        "从 {reg} 的登记文件查起，再查同一个登记号的图谱节点。",
    ),
}

MIGRATION_QUESTIONS = {
    "document": (
        "用证号 {reg} 找到对应的登记资料。",
        "请按登记证号 {reg} 精确筛选登记材料。",
        "只保留登记号为 {reg} 的登记文档。",
        "登记文档按证号筛选，目标是 {reg}。",
        "能从登记材料里定位证号 {reg} 吗？",
        "我核对的是 {reg} 这张证，请返回它的登记资料。",
    ),
    "missing_registration": (
        "请按登记证号精确查找“{product_description}”的登记材料，目标证号还没填。",
        "精确定位“{product_description}”的登记材料。{other} 是格式示例，目标证号还没给。",
        "帮我按登记证号筛“{product_description}”的登记文档，证号稍后补。",
        "我要按实际登记证号查“{product_description}”的登记资料。{other} 仅供参考，目标证号尚未提供。",
        "等我补上实际证号，再精确检索“{product_description}”的登记材料。{other} 是示例。",
        "想精确定位“{product_description}”的一张登记证，登记证号还没提供。",
    ),
    "path": (
        "在图谱里找从登记证 {reg} 到“{target}”的关系路径。",
        "查询“{reg}”连到“{target}”的图谱关系链。",
        "以 {reg} 为起点，“{target}”为终点，帮我查路径。",
        "用证号 {reg} 和图谱实体“{target}”作为两端，检索最短路径。",
        "给我图谱里证号 {reg} 通往“{target}”的链路。",
        "在图谱中，从“{reg}”沿什么关系可以到“{target}”？",
    ),
    "missing_path": (
        "查从登记证 {reg} 出发的图谱关系路径，我还没指定终点。",
        "从“{reg}”沿图谱查路径，终点实体名称我稍后发。",
        "已知图谱关系链起点是 {reg}，终点实体待补。",
        "从登记 {reg} 查一条图谱路径，另一端的名字我接下来再给。",
        "准备从 {reg} 走图谱查路径，终点实体的全称还没填。",
        "请查登记“{reg}”的关联链，具体要连向哪个实体我稍后告诉你。",
    ),
}


def load_registry(workbook: Path) -> dict:
    import xlrd

    data = workbook.read_bytes()
    if sha256(data).hexdigest() != WORKBOOK_SHA256:
        raise ValueError("Workbook does not match the frozen bulletin attachment.")
    sheet = xlrd.open_workbook(file_contents=data).sheet_by_name("农药登记信息")
    records = {}
    for index in range(sheet.nrows):
        registration, holder, product = (str(value).strip() for value in sheet.row_values(index)[1:4])
        if not REGISTRATION.fullmatch(registration):
            continue
        record = records.setdefault(registration, {"holder": holder, "product": product, "xls_rows": []})
        if not holder or not product or (holder, product) != (record["holder"], record["product"]):
            raise ValueError(f"Inconsistent identifying fields for {registration} in Excel row {index + 1}.")
        record["xls_rows"].append(index + 1)
    if len(records) != 645:
        raise ValueError(f"Expected 645 registrations from the bulletin, found {len(records)}.")
    return {
        "announcement": ANNOUNCEMENT,
        "attachment": WORKBOOK_URL,
        "attachment_sha256": WORKBOOK_SHA256,
        "records": records,
        "pubchem": {
            name: {"cid": cid, "product": product, "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"}
            for product, (name, cid) in PUBCHEM.items()
        },
    }


def step(tool: str, title: str, **arguments: str) -> dict:
    return {"id": tool, "title": title, "tool": tool, "arguments": arguments}


def label(task_type: str, summary: str, entities: list[str], *steps: dict, missing: str = "") -> dict:
    return {
        "task_type": task_type, "summary": summary, "entities": entities, "missing_information": missing,
        "requires_approval": task_type == "compliance_screen", "steps": list(steps),
    }


def group_examples(reg: str, other: str, record: dict, ordinal: int, phrase: int) -> tuple[list[dict], list[dict]]:
    holder, product = record["holder"], record["product"]
    migration = "path_targets" in record
    compound, cid = record.get("pubchem_reference", ("", 0)) if migration else PUBCHEM.get(product, ("", 0))
    targets = record.get("path_targets") or [holder]
    target = targets[ordinal % len(targets)]
    values = {
        "reg": reg, "other": other, "holder": holder, "product": product, "compound": compound, "target": target,
        "product_description": f"{holder} 的 {product}" if holder else product,
    }
    if migration:
        group, provenance, source_ref = f"migration-{reg}", "neo4j_registry_derived", record["source_ref"]
    else:
        group, provenance = f"moa-2026-11-{reg}", "public_registry_generated"
        source_ref = f"{WORKBOOK_URL}#xls-row={record['xls_rows'][0]}"
    rows, replays = [], []

    def add(kind: str, plan: dict, evidence: list[str], *, terms=(), enabled=True, followup=None) -> None:
        templates = MIGRATION_QUESTIONS.get(kind, QUESTIONS[kind]) if migration else QUESTIONS[kind]
        template = templates[phrase]
        if migration:
            for original in ("原始登记材料", "原始登记文件", "登记原文", "登记附件", "登记文件", "附件", "原文"):
                template = template.replace(original, "登记资料")
        question = template.format(**values)
        example = {
            "id": f"{group}-{kind}", "group_id": group, "kind": kind, "question": question,
            "source": provenance, "source_ref": source_ref,
            "documents_enabled": enabled, "plan": plan, "clarification_terms": list(terms),
        }
        rows.append(example)
        if followup is not None:
            reply, recovered_plan = followup
            replays.append({
                "id": example["id"], "reply": reply, "recovered_plan": recovered_plan, "evidence": evidence,
            })
        else:
            replays.append({"id": example["id"], "evidence": evidence})

    docs = step("search_documents", "按登记号检索登记资料" if migration else "按登记号检索原文", query=reg, registration_number=reg)
    graph = step("search_entity", "查找图谱登记实体", keyword=reg)
    document_plan = label("fact_check", "定位登记资料" if migration else "定位登记附件", [reg], docs)
    add("document", document_plan, [reg])
    add("missing_registration", label("fact_check", "确认要查的登记证号", [], missing="请补充目标登记证号。"),
        [reg], terms=("登记", "号"), followup=(f"目标登记证号是 {reg}。", document_plan))

    if ordinal % 2 == 0:
        compare = step("compare_entities", "比较图谱登记实体", left=reg, right=other)
        plan = label("comparison", "对比两张登记证的图谱记录", [reg, other], compare)
        add("comparison", plan, [reg, other])
        add("missing_comparison", label("comparison", "确认另一张登记证", [reg], missing="请补充另一张用于比较的登记证号。"),
            [reg, other], terms=("号",), followup=(f"另一张登记证号是 {other}。", plan))
    else:
        target_type = "关联实体" if migration else "持有人"
        path = step("find_relation_path", f"查找登记证到{target_type}的路径", source=reg, target=target)
        plan = label("relation_path", f"查找登记证与{target_type}的图谱路径", [reg, target], path)
        add("path", plan, [reg])
        add("missing_path", label("relation_path", "确认路径终点", [reg], missing=f"请补充终点{target_type}名称。"),
            [reg], terms=("终点" if migration else "持有人",), followup=(f"终点{target_type}是“{target}”。", plan))

    kind = ordinal % 5
    if kind == 0:
        external = step("external_substance_lookup", "核验 PubChem 条目", name=compound)
        add("external", label("fact_check", "查找 PubChem 化学条目", [compound], external), [f"pubchem:{cid}"])
    elif kind == 1:
        add("graph", label("fact_check", "定位图谱登记记录", [reg], graph), [reg], enabled=False)
    elif kind == 2:
        add("compliance", label("compliance_screen", "收集登记证据并等待人工确认", [reg], docs, graph), [reg])
    elif kind == 3:
        keyword = step("search_documents", "按名称和持有人查找文档", query=f"{product} {holder}")
        add("keyword_document", label("fact_check", "按关键词检索登记材料", [product, holder], keyword), [reg])
    else:
        add("joint_lookup", label("fact_check", "查文档并核对图谱登记实体", [reg], docs, graph), [reg])
    return rows, replays


def build(workbook: Path, output: Path) -> None:
    source = load_registry(workbook)
    records = source["records"]
    rng = Random(SEED)
    registrations = sorted(records)
    rng.shuffle(registrations)
    external_count = sum(count // 5 for count in GROUPS.values())
    external_registrations = [reg for reg in registrations if records[reg]["product"] in PUBCHEM][:external_count]
    if len(external_registrations) != external_count:
        raise ValueError("The bulletin lacks enough product names with verified PubChem references.")
    external = iter(external_registrations)
    reserved = set(external_registrations)
    remaining = iter(reg for reg in registrations if reg not in reserved)
    pairs = {
        split: [(next(external if ordinal % 5 == 0 else remaining), next(remaining)) for ordinal in range(count)]
        for split, count in GROUPS.items()
    }
    write_dataset(source, output, pairs, {"seed": SEED, "split_policy": "two_unique_registration_ids_per_group"})


def write_dataset(source: dict, output: Path, splits: dict[str, list[tuple[str, str]]], metadata: dict) -> None:
    records = source["records"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "registry_snapshot.json").write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = metadata | {"splits": {}}
    all_replay = []
    used = set()
    for split_number, (split, pairs) in enumerate(splits.items()):
        rows, split_registrations = [], set()
        for ordinal, (reg, other) in enumerate(pairs):
            split_registrations.update((reg, other))
            phrase = 2 * split_number + (ordinal // 10) % 2
            examples, replays = group_examples(reg, other, records[reg], ordinal, phrase)
            # Include the shape of a resumed turn in training. Dev/test replay prompts stay untrained.
            if split == "train" and ordinal % 3 == 0:
                for ready_index in (0, 2):
                    pending = examples[ready_index + 1]["question"]
                    reply = replays[ready_index + 1]["reply"]
                    examples[ready_index]["question"] = f"{pending}；补充信息：{reply}"
            rows.extend(examples)
            if split == "test":
                all_replay.extend(replays)
        if split_registrations & used or len(split_registrations) != 2 * len(pairs):
            raise ValueError(f"Registration coverage overlaps or is incomplete in {split}.")
        used.update(split_registrations)
        if len({row["question"] for row in rows}) != len(rows):
            raise ValueError(f"Duplicate questions in {split}.")
        _write_jsonl(output / f"{split}.jsonl", rows)
        parsed = read_dataset(output / f"{split}.jsonl")
        manifest["splits"][split] = {
            "groups": len(pairs), "rows": len(parsed), "registrations": len(split_registrations),
            **({"primary_source_groups": dict(Counter(records[reg]["source_group"] for reg, _ in pairs))}
               if "dump_sha256" in source else {}),
            "sha256": dataset_fingerprint(parsed), "kinds": dict(Counter(row["kind"] for row in parsed)),
        }
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        ensure_disjoint(read_dataset(output / f"{left}.jsonl"), read_dataset(output / f"{right}.jsonl"))
    _write_jsonl(output / "test_replay.jsonl", all_replay)
    manifest["fixtures"] = {
        "registry_snapshot_sha256": dataset_fingerprint([source]),
        "test_replay_sha256": dataset_fingerprint(all_replay),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Original public MOA .xls attachment (requires xlrd==2.0.2)")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.workbook, args.output)
