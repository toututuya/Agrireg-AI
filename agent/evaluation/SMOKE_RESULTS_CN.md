# AgriReg AI 联调记录

## Qwen3-1.7B 规划器

在 Athena 的 RTX 3090 上用 NF4 QLoRA 训练，seed 为 42。336 条合成训练样本构成训练池，优化 64 步，训练用时 96.4 秒，CUDA 峰值分配 3,144 MiB。基线和微调版共享相同的 NF4 基座、提示词及贪心解码设置，在实体和问法均留出的 42 道合成题上评测。规划延迟在预热后按七类题各抽一条，逐条生成并计时。

| 指标 | 原始基座 | LoRA |
| --- | ---: | ---: |
| 可解析 JSON | 41 / 42 | 42 / 42 |
| 通过计划与输入参数校验 | 0 / 42 | 42 / 42 |
| 同时匹配意图、审批、工具和是否追问 | 0 / 42 | 38 / 42 |
| 精确匹配参数或问对缺失字段 | 0 / 42 | 21 / 42 |
| 单请求规划 p50 | 5.533 秒 | 3.678 秒 |
| 单请求规划 p95 | 12.073 秒 | 4.708 秒 |

有效计划和精确动作按本项目的计划协议统计。当前数据只覆盖合成场景。真实语料下的参数准确率、并发吞吐和整次 Agent 耗时需要在目标部署上测量。

检索登记文档与比较对象追问分别有 6 道题，精确动作均为 0 道。原始分组结果见 [Qwen3 评测 JSON](qwen3_nf4_seed42.json)。

## 登记文档检索

在 Athena CPU 上用真实 BGE-M3、Milvus Lite 3.2.2 和 bge-reranker-v2-m3 测试六份合成登记文本及六道标注查询。各模式先预热一次。表内包含 Milvus 查询和该模式启用的模型推理时间。

| 模式 | Recall@2 | MRR@2 | p50（ms） | p95（ms） |
| --- | ---: | ---: | ---: | ---: |
| BGE-M3 稠密召回 | 1.00 | 1.00 | 129 | 144 |
| 中文 BM25 | 1.00 | 1.00 | 1.34 | 1.95 |
| RRF 混合召回 | 1.00 | 1.00 | 142 | 149 |
| 混合召回与 Cross-Encoder 重排 | 1.00 | 1.00 | 817 | 887 |

这六道题用于验证每条检索路径和耗时口径。正式语料的检索质量需要独立标注集。合成数据位于 `evaluation/document_samples`。在 Agent 目录执行以下命令即可使用已配置的 Milvus 重现该评测。

~~~bash
agrireg-documents ingest evaluation/document_samples/pages.jsonl
python evaluation/evaluate_documents.py evaluation/document_samples/qrels.jsonl --limit 2
~~~

## 图谱和 MCP

- Neo4j 4.4.45 载入三条合成节点。Spring Boot 验证唯一别名、共享别名追问、有界路径，以及只渲染合法编号的图谱证据。
- LangGraph 通过 Spring Boot 查询并引用实际 Neo4j 返回的关系证据。
- 标准 MCP Streamable HTTP 客户端分别从实际 Neo4j 与 Milvus Lite 获取实体和文档片段。
- Windows 的 stdio 已验证工具发现、参数校验和实体查询。该环境的文档调用在 NumPy 冷加载阶段超时。
