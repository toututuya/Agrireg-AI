from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field


ToolName = Literal[
    "search_entity",
    "compare_entities",
    "find_relation_path",
    "grounded_answer",
    "external_substance_lookup",
]


class PlanStep(BaseModel):
    id: str
    title: str
    tool: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


class TaskPlan(BaseModel):
    task_type: Literal["fact_check", "comparison", "relation_path", "compliance_screen"]
    summary: str
    entities: list[str] = Field(default_factory=list, max_length=4)
    missing_information: str = ""
    requires_approval: bool = False
    steps: list[PlanStep] = Field(default_factory=list, max_length=6)


class AgentState(TypedDict, total=False):
    question: str
    require_approval: bool
    plan: dict[str, Any]
    step_index: int
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    evidence: Annotated[list[dict[str, Any]], operator.add]
    verified_evidence: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    events: Annotated[list[dict[str, Any]], operator.add]
    coverage: str
    approval_decision: str
    report: str
    status: str


class CreateThreadRequest(BaseModel):
    title: str = Field("新分析任务", min_length=1, max_length=80)


class StartRunRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    require_approval: bool = False


class ResumeRunRequest(BaseModel):
    value: str | dict[str, Any] | None = None
