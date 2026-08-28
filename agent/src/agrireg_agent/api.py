from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import get_settings
from .models import CreateThreadRequest, ResumeRunRequest, StartRunRequest
from .runtime import AgentRuntime
from .store import TERMINAL_STATUSES


settings = get_settings()
runtime = AgentRuntime(settings)

app = FastAPI(
    title="AgriReg Agent API",
    version="0.1.0",
    description="Stateful evidence verification agent over controlled GDP-KG tools.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Last-Event-ID"],
)


@app.get("/api/agent/health")
def health() -> dict[str, object]:
    return {"status": "ok", "modelPlanning": runtime.llm.enabled, "persistence": "sqlite"}


@app.get("/api/agent/threads")
def list_threads() -> list[dict[str, object]]:
    return runtime.store.list_threads()


@app.post("/api/agent/threads", status_code=status.HTTP_201_CREATED)
def create_thread(payload: CreateThreadRequest) -> dict[str, object]:
    return runtime.store.create_thread(payload.title)


@app.get("/api/agent/threads/{thread_id}")
def get_thread(thread_id: str) -> dict[str, object]:
    try:
        return runtime.store.get_thread(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在。") from exc


@app.post("/api/agent/threads/{thread_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(thread_id: str, payload: StartRunRequest) -> dict[str, object]:
    try:
        run = runtime.store.create_run(thread_id, payload.question, payload.require_approval)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在。") from exc
    runtime.start_run(run["id"])
    return run


@app.get("/api/agent/threads/{thread_id}/runs/{run_id}")
def get_run(thread_id: str, run_id: str) -> dict[str, object]:
    try:
        return runtime.store.get_run(run_id, thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="分析记录不存在。") from exc


@app.post("/api/agent/threads/{thread_id}/runs/{run_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_run(thread_id: str, run_id: str, payload: ResumeRunRequest) -> dict[str, object]:
    try:
        runtime.store.get_run(run_id, thread_id)
        runtime.resume_run(run_id, payload.value)
        return runtime.store.get_run(run_id, thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="分析记录不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="当前任务不需要补充信息或确认。") from exc


@app.get("/api/agent/threads/{thread_id}/runs/{run_id}/events")
async def stream_events(
    thread_id: str,
    run_id: str,
    request: Request,
    after: int = 0,
) -> StreamingResponse:
    try:
        runtime.store.get_run(run_id, thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="分析记录不存在。") from exc

    last_event_id = request.headers.get("last-event-id")
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else max(after, 0)

    async def generate() -> AsyncIterator[str]:
        nonlocal cursor
        idle_cycles = 0
        while not await request.is_disconnected():
            events = runtime.store.events_after(run_id, cursor)
            if events:
                idle_cycles = 0
                for item in events:
                    cursor = int(item["seq"])
                    yield f"id: {cursor}\nevent: agent_event\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
            else:
                idle_cycles += 1

            run = runtime.store.get_run(run_id, thread_id)
            if run["status"] in TERMINAL_STATUSES or run["status"].startswith("waiting_"):
                payload = json.dumps(run, ensure_ascii=False)
                yield f"event: run_snapshot\ndata: {payload}\n\n"
                break
            if idle_cycles >= 20:
                idle_cycles = 0
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.35)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def run() -> None:
    uvicorn.run("agrireg_agent.api:app", host=settings.host, port=settings.port, reload=False)
