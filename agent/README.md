# AgriReg Agent Service

独立 Python 服务，使用 LangGraph 编排“任务规划 → 受控图谱工具 → 外部来源核验 → 冲突检测 → 人工确认 → 报告生成”。Agent 不直接连接 Neo4j，也不能生成或执行任意 Cypher；所有图谱访问都通过现有 Spring Boot API。

## Local start

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env.local
.\.venv\Scripts\python -m uvicorn agrireg_agent.api:app --host 127.0.0.1 --port 8091
```

`DEEPSEEK_ENABLED=false` 时仍可完整演示状态图、工具路由、暂停恢复与确定性报告；启用模型后，规划器会优先生成结构化任务计划，并基于编号证据撰写报告。API Key 只放在本地环境变量中。

## API shape

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/agent/threads` | 创建任务线程 |
| `POST` | `/api/agent/threads/{threadId}/runs` | 启动一次分析 |
| `GET` | `/api/agent/threads/{threadId}/runs/{runId}` | 获取任务快照 |
| `GET` | `/api/agent/threads/{threadId}/runs/{runId}/events` | SSE 订阅可展示事件 |
| `POST` | `/api/agent/threads/{threadId}/runs/{runId}/resume` | 补充信息、批准或拒绝 |

事件只包含计划摘要、工具状态、证据、冲突和报告，不暴露模型隐藏推理。

