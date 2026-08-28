from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .clients import ControlledTools, DeepSeekClient
from .config import Settings
from .graph import build_agent_graph
from .store import RunStore


class AgentRuntime:
    def __init__(
        self,
        settings: Settings,
        tools: ControlledTools | None = None,
        llm: DeepSeekClient | None = None,
    ):
        self.settings = settings.prepare()
        self.store = RunStore(self.settings.data_dir / "agent_runs.sqlite3")
        self._checkpoint_connection = sqlite3.connect(
            self.settings.data_dir / "agent_checkpoints.sqlite3", check_same_thread=False
        )
        self.checkpointer = SqliteSaver(self._checkpoint_connection)
        self.checkpointer.setup()
        self.tools = tools or ControlledTools(settings)
        self.llm = llm or DeepSeekClient(settings)
        self.graph = build_agent_graph(self.tools, self.llm, self.checkpointer)
        self._tasks: set[asyncio.Task[Any]] = set()

    def start_run(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        payload = {
            "question": run["question"],
            "require_approval": run["requireApproval"],
            "tool_results": [],
            "evidence": [],
            "events": [],
        }
        self._spawn(self._drive_async(run_id, payload))

    def resume_run(self, run_id: str, value: Any) -> None:
        run = self.store.get_run(run_id)
        if run["status"] not in {"waiting_clarification", "waiting_approval", "paused"}:
            raise ValueError("run_not_resumable")
        self.store.update_run(run_id, "running", interrupt_json=None, error=None)
        self.store.append_event(run_id, "run_resumed", "继续分析任务", "任务已从保存的状态继续。", {})
        payload: Any = None if run["status"] == "paused" and value is None else Command(resume=value)
        self._spawn(self._drive_async(run_id, payload))

    def _spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _drive_async(self, run_id: str, payload: Any) -> None:
        await asyncio.to_thread(self._drive, run_id, payload)

    def _drive(self, run_id: str, payload: Any) -> None:
        config = {"configurable": {"thread_id": f"run:{run_id}"}}
        try:
            interrupt_payload = None
            for chunk in self.graph.stream(payload, config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = self._interrupt_value(chunk["__interrupt__"])
                    break
                for output in chunk.values():
                    if not isinstance(output, dict):
                        continue
                    for item in output.get("events") or []:
                        self.store.append_event(
                            run_id,
                            item.get("kind", "progress"),
                            item.get("title", "任务进度"),
                            item.get("detail", ""),
                            item.get("payload") or {},
                        )

            if interrupt_payload:
                kind = interrupt_payload.get("kind")
                status = "waiting_approval" if kind == "approval" else "waiting_clarification"
                self.store.update_run(
                    run_id,
                    status,
                    interrupt_json=json.dumps(interrupt_payload, ensure_ascii=False),
                )
                self.store.append_event(
                    run_id,
                    "input_required",
                    interrupt_payload.get("title", "需要你的确认"),
                    interrupt_payload.get("message", "请补充信息后继续。"),
                    interrupt_payload,
                )
                return

            snapshot = self.graph.get_state(config)
            values = snapshot.values if snapshot else {}
            report = values.get("report", "") if isinstance(values, dict) else ""
            final_status = "rejected" if values.get("approval_decision") == "reject" else "completed"
            self.store.update_run(run_id, final_status, report=report, interrupt_json=None, error=None)
        except Exception as exc:
            self.store.update_run(run_id, "failed", error=str(exc))
            self.store.append_event(
                run_id,
                "run_failed",
                "分析任务未完成",
                "任务状态已经保存，可以检查依赖服务后重新运行。",
                {},
            )

    @staticmethod
    def _interrupt_value(raw: Any) -> dict[str, Any]:
        first = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
        value = getattr(first, "value", first)
        if isinstance(value, dict):
            return value
        return {"kind": "clarification", "title": "需要补充信息", "message": str(value)}

