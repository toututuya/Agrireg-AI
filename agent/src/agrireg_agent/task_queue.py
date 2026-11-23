from __future__ import annotations

import re
from typing import Literal, TypedDict


MAX_SUBTASKS = 16
CLARIFICATION_SEPARATOR = "；补充信息："
TASK_MARKER = re.compile(r"(?:^|[\s;；：:])([1-9]\d?)\s*[.．、)）]\s*(?=[^\d\s])")
ACTION = re.compile(
    r"^(?:(?:请|帮我|再|接着|然后|另外|同时|也|分别|先|最后|并|且|再请|再帮我)\s*)*"
    r"(?:查|找|搜|对比|比较|核验|核对|检查|检索|定位|根据|基于|依据|参照|结合)"
)
DEPENDENCY = re.compile(r"(?:根据|基于|依据|用|使用|参照|结合)\s*第\s*(\d{1,2})\s*(?:项|个任务|步)")
PREVIOUS = re.compile(r"(?:根据|基于|依据|用|使用|参照|结合)\s*(?:前一|上一)项")
REFERENCE = re.compile(r"该产品|这个产品|该成分|该对象|(?<![其另])它(?=的|是|和|[，。！？]|$)")
INTRO = re.compile(
    r"^(?:(?:请|帮我|麻烦)\s*)*(?:完成|处理|执行|分析|做)?\s*(?:以下|下列|下面|这些|这几项)?"
    r"\s*(?:(?:\d+|[一二三四五六七八九十几两]+)[件项])?\s*(?:事|任务|事项|查询)?\s*[:：]?$"
)

TaskStatus = Literal["pending", "running", "needs_input", "completed", "partial", "failed", "blocked"]
TASK_STATUS_LABELS = {
    "pending": "待执行", "running": "执行中", "needs_input": "待补充",
    "completed": "已完成", "partial": "部分完成", "failed": "缺少有效证据", "blocked": "未执行",
}


class Subtask(TypedDict):
    id: int
    question: str
    depends_on: list[int]
    status: TaskStatus
    message: str
    clarifications: list[str]
    entities: list[str]
    requires_approval: bool


def split_subtasks(question: str) -> list[Subtask]:
    numbered = list(TASK_MARKER.finditer(question))
    if len(numbered) >= 2:
        introduction = question[:numbered[0].start()].strip(" \t\r\n：:")
        parts = [
            (int(marker.group(1)), question[marker.end():end].strip(" \t\r\n；;"))
            for marker, end in zip(numbered, [item.start() for item in numbered[1:]] + [len(question)], strict=True)
        ]
        if len({number for number, _ in parts}) != len(parts):
            raise ValueError("分项编号需要唯一。")
        if any(not text for _, text in parts):
            raise ValueError("请为每个分项填写任务。")
        if introduction and not INTRO.fullmatch(introduction):
            parts = [(number, f"{text}；共同要求：{introduction}") for number, text in parts]
    else:
        pieces = re.split(r"([；;\n，。！？?])", question)
        first = pieces[0].strip()
        clauses = [first] if first and not INTRO.fullmatch(first) else []
        for separator, text in zip(pieces[1::2], pieces[2::2], strict=True):
            text = text.strip()
            if text and (not clauses or ACTION.match(text)):
                clauses.append(text)
            elif clauses:
                clauses[-1] += separator + text
        parts = list(enumerate(clauses, start=1))
    if len(parts) < 2:
        return []
    if len(parts) > MAX_SUBTASKS:
        raise ValueError(f"单次最多执行 {MAX_SUBTASKS} 个分项。请分批提交。")

    tasks = []
    earlier: list[int] = []
    for number, text in parts:
        dependencies = list(dict.fromkeys(int(match.group(1)) for match in DEPENDENCY.finditer(text)))
        if PREVIOUS.search(text):
            dependencies = list(dict.fromkeys([*dependencies, earlier[-1] if earlier else 0]))
        invalid = [item for item in dependencies if item not in earlier]
        tasks.append(Subtask(
            id=number, question=text, depends_on=dependencies, status="blocked" if invalid else "pending",
            message="依赖项必须是当前任务中列在前面的分项。" if invalid else "",
            clarifications=[], entities=[], requires_approval=False,
        ))
        earlier.append(number)
    return tasks


def public_subtask(task: Subtask) -> dict:
    return {
        "id": task["id"], "question": task["question"], "dependsOn": task["depends_on"],
        "status": task["status"], "message": task["message"],
    }


def task_question(task: Subtask, tasks: list[Subtask]) -> tuple[str, str]:
    question = task["question"] + "".join(
        f"{CLARIFICATION_SEPARATOR}{text}" for text in task["clarifications"] if text
    )
    dependencies = set(task["depends_on"])
    if not dependencies or not REFERENCE.search(task["question"]):
        return question, ""
    if any(text.strip() for text in task["clarifications"]):
        return question, ""
    entities = list(dict.fromkeys(entity for other in tasks if other["id"] in dependencies for entity in other["entities"]))
    if len(entities) == 1:
        return REFERENCE.sub(lambda _: entities[0], question), ""
    return question, "请指定本项要使用的登记号或实体名称。"
