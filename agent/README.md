# AgriReg Agent Service

独立 Python 服务，使用 LangGraph 编排任务规划、受控工具执行、补查、证据核验、人工确认和报告生成。图谱查询复用 Spring Boot 的有界查询接口。

## Local start

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env.local
.\.venv\Scripts\python -m uvicorn agrireg_agent.api:app --host 127.0.0.1 --port 8091
```

`DEEPSEEK_ENABLED=false` 时可使用确定性规划与报告。启用模型后，规划器优先生成结构化计划，服务端验证工具名与入参。报告模型选择编号证据，服务端按原文渲染引用。

## 计划、执行与上下文

- 比较或路径查询缺少对象时暂停追问，收到补充再规划。执行前校验工具白名单和参数，保证登记号及两实体参数来自当前请求。
- 工具返回空证据或失败时，可追加一轮补查，最多两步。路径或比较查不到时可以改查单个实体。启用文档索引时可补查登记原文。同一工具与入参只补查一次，整次运行受工具步数上限约束。
- 线程内最近三次已完成问题保留原文窗口，每条最多 300 字。前九次保留去重后的实体和任务类型摘要。历史只帮助解析“该产品”等指代，报告引用只使用本次运行的证据。
- 工具事件记录响应时间。新计划直接读取图谱证据，统一在收尾阶段生成报告。旧计划仍可恢复。

## API shape

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/agent/threads` | 创建任务线程 |
| `POST` | `/api/agent/threads/{threadId}/runs` | 启动一次分析 |
| `GET` | `/api/agent/threads/{threadId}/runs/{runId}` | 获取任务快照 |
| `GET` | `/api/agent/threads/{threadId}/runs/{runId}/events` | SSE 订阅可展示事件 |
| `POST` | `/api/agent/threads/{threadId}/runs/{runId}/resume` | 补充信息、批准或拒绝 |

事件只包含计划摘要、工具状态、证据、冲突和报告，不暴露模型隐藏推理。

## 登记文档检索

文档检索使用 Milvus 2.6 的 BM25 和 BGE-M3 的稠密编码。混合模式分别召回 32 条候选，通过 RRF 融合。默认再用 BGE Cross-Encoder 对融合后的前 32 条重排序，返回前 5 条。登记号过滤应用于两路召回，每条命中包含文档版本、页码或章节、原文片段和来源 URL。

从本目录安装可选依赖，按 `.env.example` 配置 `AGENT_MILVUS_URI`。`AGENT_RETRIEVAL_DEVICE` 可以填 `cpu` 或 `cuda:0`。模型在相应检索模式第一次运行时加载。
离线使用时，可在 `AGENT_EMBEDDING_MODEL` 和 `AGENT_RERANKER_MODEL` 中指定相应模型权重的本地目录。
本地开发可补装 `milvus-lite>=3.2.2,<4` 和 `jieba`，并把 `AGENT_MILVUS_URI` 指向新的 `.db` 文件。

~~~bash
python -m pip install -e ".[documents]"
agrireg-documents ingest /path/to/pages.jsonl
agrireg-documents search "登记状态" --registration-number SAMPLE-001 --mode reranked
~~~

每行提供一个文档页面或章节。下面是合成输入示例。

~~~json
{"document_id":"sample","version":"v1","title":"合成登记样例","source_url":"https://example.org/sample","page":1,"section":"登记状态","registration_number":"SAMPLE-001","text":"此条记录用于测试检索流程。"}
~~~

页码和章节至少填一项，同一文件内的定位必须唯一。同一版本重复导入以分块 ID 幂等写入。源文档更正时更新版本。为发布固定的语料快照，可用一个新的 `AGENT_MILVUS_COLLECTION` 完成入库和评测后切换。原始文档需要先提取为带页码或章节的文本，再按此格式导入。

`POST /api/agent/documents/search` 接受 `query`、`registration_number`（可省略）、`limit`（1–10）和 `mode`（`dense`、`bm25`、`hybrid`、`reranked`）。各模式的分数用于各自排序。可用下列命令在同一批标注查询上对照 Recall@k、MRR@k 和检索延迟。评测 JSONL 每行需要 `query` 与 `relevant_document_ids`，支持可选的 `registration_number`。

~~~bash
python evaluation/evaluate_documents.py /path/to/document-qrels.jsonl --limit 5
~~~

## MCP

FastMCP 暴露实体搜索、关系路径和文档检索三项工具，复用同一套检索逻辑。外部 MCP 客户端可通过 stdio 启动服务，也可以连接本机的 Streamable HTTP 端点。

~~~bash
python -m pip install -e ".[mcp]"
agrireg-mcp
agrireg-mcp --transport streamable-http --port 8092
~~~

HTTP 地址为 `http://127.0.0.1:8092/mcp`。配置图谱 API 或 Milvus 后，相应工具即可查询。文档工具的入参结构为 `{"request":{"query":"登记状态","limit":5}}`。

## Qwen3 规划器 LoRA

本地联调与实测指标见 [联调记录](evaluation/SMOKE_RESULTS_CN.md)。

自建标注、训练前校验及 GitHub 官方训练器的 `messages` 导出见 [规划数据流程](evaluation/PLANNER_DATA_CN.md)。

训练对象为 Qwen3-1.7B，关闭思考模式，用计划 JSON 监督工具选择、参数、缺参追问与审批标记。训练只对 assistant 输出计算损失，LoRA 更新注意力层的 Q、K、V、O 投影。合成数据按实体和问法模板留出，包含 336 条训练样本和 42 条测试样本。样本中的登记号只用于测试路由。

~~~bash
python -m pip install -e ".[training]"
agrireg-planner-sft data --output ./planner-data
CUDA_VISIBLE_DEVICES=0 agrireg-planner-sft train --output ./runs/qwen3-planner --steps 64
CUDA_VISIBLE_DEVICES=0 agrireg-planner-sft evaluate --adapter ./runs/qwen3-planner --output ./runs/planner-eval.json
~~~

两项实验命令都可用 `--base` 指向提前下载的 Qwen3 权重目录。显存紧张时加装 `.[training,training-4bit]`，训练和评测使用同一个 `--four-bit` 开关。评测在同一基础模型上分别关闭和启用 adapter，记录 JSON 格式通过数、有效计划数、意图和工具匹配数、精确动作数以及生成 p50/p95。精确动作要求参数匹配，追问题还要求指出缺失字段。

在 `.env.local` 设置 `AGENT_PLANNER_BACKEND=qwen3`、`AGENT_QWEN_BASE`、`AGENT_QWEN_ADAPTER` 和 `AGENT_QWEN_DEVICE`。部署量化版本时设置 `AGENT_QWEN_4BIT=true`。计划验证失败时使用确定性规划，证据检索及汇总继续走现有 LangGraph 流程。
