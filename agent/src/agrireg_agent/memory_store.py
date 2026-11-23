from __future__ import annotations

import json
import sqlite3
from typing import Any

from .memory import (
    SLOTS, SUMMARY_TURNS, MemoryCommand, capture_episode, display_time, prompt_context,
)


def setup_memory(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS agent_memory_episodes (
            run_id TEXT PRIMARY KEY REFERENCES agent_runs(id),
            thread_id TEXT NOT NULL REFERENCES agent_threads(id),
            occurred_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            projection TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_episodes_thread
            ON agent_memory_episodes(thread_id, occurred_at DESC, run_id DESC);
        CREATE TABLE IF NOT EXISTS agent_memory_slots (
            run_id TEXT PRIMARY KEY REFERENCES agent_runs(id),
            thread_id TEXT NOT NULL REFERENCES agent_threads(id),
            slot TEXT NOT NULL,
            value TEXT NOT NULL,
            valid_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_slots_thread
            ON agent_memory_slots(thread_id, slot, valid_at DESC, recorded_at DESC);
    """)


def backfill_memory(connection: sqlite3.Connection) -> None:
    rows = connection.execute("""
        SELECT r.* FROM agent_runs r
        WHERE r.status IN ('completed', 'failed', 'rejected')
          AND NOT EXISTS (SELECT 1 FROM agent_memory_episodes e WHERE e.run_id = r.id)
          AND NOT EXISTS (SELECT 1 FROM agent_events e WHERE e.run_id = r.id AND e.kind = 'memory_answered')
    """)
    for row in rows:
        record_episode(connection, row, row["updated_at"])


def record_episode(
    connection: sqlite3.Connection, row: sqlite3.Row, now: str, episode: dict[str, Any] | None = None,
) -> None:
    if row["status"] != "completed":
        episode = {}
    elif episode is None:
        payloads = {}
        for kind in ("plan_ready", "evidence_verified", "subtasks_ready"):
            event = connection.execute(
                "SELECT payload_json FROM agent_events WHERE run_id = ? AND kind = ? ORDER BY seq DESC LIMIT 1",
                (row["id"], kind),
            ).fetchone()
            payloads[kind] = json.loads(event["payload_json"]) if event else {}
        plan = payloads["plan_ready"]
        episode = capture_episode({
            "plan": plan.get("plan") if not (payloads["subtasks_ready"] or plan.get("taskId")) else None,
            "verified_evidence": payloads["evidence_verified"].get("evidence"),
        })
    projection = {
        "type": "", "entities": [], "reference": "", "reference_kind": "", "evidence_count": 0, "procedures": {},
    } | episode
    connection.execute("""
        INSERT OR IGNORE INTO agent_memory_episodes(run_id, thread_id, occurred_at, recorded_at, projection)
        VALUES (?, ?, ?, ?, ?)
    """, (row["id"], row["thread_id"], row["created_at"], now, json.dumps(projection, ensure_ascii=False)))


# A run reads the conversation as it was at the time the user asked. A previous, slow run that
# finishes later stays out of the snapshot, even when the current run is resumed from a checkpoint.
VISIBLE_EPISODES = """
    FROM agent_memory_episodes e JOIN agent_runs r ON r.id = e.run_id
    WHERE e.thread_id = ? AND e.run_id != ? AND e.occurred_at <= ? AND e.recorded_at <= ?
"""


def episode_scope(run: sqlite3.Row) -> tuple[str, str, str, str]:
    return run["thread_id"], run["id"], run["created_at"], run["created_at"]


def read_slots(connection: sqlite3.Connection, thread_id: str, valid_at: str, known_at: str) -> dict[str, sqlite3.Row]:
    slots = {}
    for slot in set(SLOTS.values()):
        row = connection.execute("""
            SELECT value, valid_at, recorded_at FROM agent_memory_slots
            WHERE thread_id = ? AND slot = ? AND valid_at <= ? AND recorded_at <= ?
            ORDER BY valid_at DESC, recorded_at DESC, rowid DESC LIMIT 1
        """, (thread_id, slot, valid_at, known_at)).fetchone()
        if row is not None:
            slots[slot] = row
    return slots


def read_context(connection: sqlite3.Connection, run: sqlite3.Row) -> dict[str, Any]:
    rows = connection.execute("""
        SELECT substr(r.question, 1, 160) AS question, e.projection
    """ + VISIBLE_EPISODES + """
        ORDER BY e.occurred_at DESC, e.run_id DESC LIMIT ?
    """, (*episode_scope(run), SUMMARY_TURNS))
    turns = [json.loads(row["projection"]) | {"question": row["question"]} for row in rows]
    context = prompt_context(turns)
    procedures: dict[str, bool] = {}
    for turn in reversed(turns):
        procedures.update(turn["procedures"])
    slots = read_slots(connection, run["thread_id"], run["created_at"], run["created_at"])
    if turns:
        context["reference"] = turns[0]["reference"]
        context["reference_kind"] = turns[0].get("reference_kind", "")
        context["procedures"] = procedures
    if slots:
        context["slots"] = {name: row["value"] for name, row in slots.items()}
    return context


def memory_reply(
    connection: sqlite3.Connection, run: sqlite3.Row, command: MemoryCommand, recorded_at: str,
) -> str:
    if command.error:
        return command.error
    if command.kind == "remember":
        valid_at = command.valid_at or run["created_at"]
        connection.execute("""
            INSERT INTO agent_memory_slots(run_id, thread_id, slot, value, valid_at, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run["id"], run["thread_id"], command.slot, command.value, valid_at, recorded_at))
        return (
            f"已在本会话记住{command.slot} **{command.value}**。\n\n"
            f"生效时间 {display_time(valid_at)}，记录时间 {display_time(recorded_at)}。"
        )
    if command.kind == "slot":
        now = run["created_at"]
        slots = read_slots(connection, run["thread_id"], command.valid_at or now, min(command.known_at or now, now))
        row = slots.get(command.slot)
        if row is None:
            return f"在指定时间点，本会话没有已生效且已记录的{command.slot}记忆。"
        return (
            f"本会话记住的{command.slot}是 **{row['value']}**。\n\n"
            f"生效时间 {display_time(row['valid_at'])}，记录时间 {display_time(row['recorded_at'])}。"
        )
    if command.kind == "overview":
        context = read_context(connection, run)
        if not context.get("recent"):
            return "本会话还没有可回顾的分析。"
        recent = [f"- {turn['question']}" for turn in context["recent"]]
        entities = context["summary"]["entities"]
        older = [f"更早核对过的对象有{'、'.join(entities)}。"] if entities else []
        return "\n".join(["**最近的分析**", "", *recent, "", *older]).strip()

    scope = episode_scope(run)
    if command.kind == "topic":
        row = connection.execute("""
            SELECT r.question, r.status, r.report, e.occurred_at, e.recorded_at
        """ + VISIBLE_EPISODES + """
            AND (instr(lower(r.question), lower(?)) > 0 OR EXISTS (
                SELECT 1 FROM json_each(e.projection, '$.entities') WHERE lower(value) = lower(?)
            ))
            ORDER BY e.occurred_at DESC, e.run_id DESC LIMIT 1
        """, (*scope, command.value, command.value)).fetchone()
    else:
        ascending = command.turn is not None
        order = "ASC" if ascending else "DESC"
        row = connection.execute("""
            SELECT r.question, r.status, r.report, e.occurred_at, e.recorded_at
        """ + VISIBLE_EPISODES + f"""
            ORDER BY e.occurred_at {order}, e.run_id {order} LIMIT 1 OFFSET ?
        """, (*scope, (command.turn or 1) - 1)).fetchone()
    if row is None:
        return "本会话没有找到这条分析记录。"
    question = " ".join(row["question"].split())[:300]
    status = {"completed": "已结束", "failed": "执行失败", "rejected": "未通过确认"}[row["status"]]
    historical = row["report"] or f"这次分析{status}，没有保存结论。"
    return (
        f"**历史记录 · {status}**\n\n{question}\n\n"
        f"提问时间 {display_time(row['occurred_at'])}，完成记录时间 {display_time(row['recorded_at'])}。"
        f"\n\n{historical}"
    )
