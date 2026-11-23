from __future__ import annotations

from random import Random

from .models import PlanStep, TaskPlan
from .planner import planning_input


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
