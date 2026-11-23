# 全量登记数据与 Qwen3 规划器

迁移包含原始和清洗后的 Neo4j dump。运行和评测使用清洗后的 `neo4j-cleaned.dump`，恢复后有 21,712 个节点、120,776 条关系和 16,216 个登记号。先前一期公开公告的数据覆盖 645 个登记号，其训练记录保存在 [一期公告评测](REGISTRY_PLANNER_CN.md)。

## 构建检索语料

在 Neo4j 4.4 恢复快照后，从 Agent 目录执行下列命令。`--neo4j-tx` 指向该快照的 HTTP 事务接口，`--citation-base` 指向用户浏览器能访问的同一快照的 Spring API。导出时保持快照只读，便于重新验证节点定位和数据指纹。

~~~bash
python -m pip install -e ".[documents,training,training-4bit]"
python evaluation/export_migration_registry.py \
  --neo4j-tx http://127.0.0.1:28747/db/neo4j/tx/commit \
  --citation-base http://127.0.0.1:18082 \
  --dump /path/to/neo4j-cleaned.dump \
  --expected-count 16216 --output /path/to/private-data/registry
~~~

导出器把登记属性、关联成分、作物和防治对象整理为 16,216 条登记记录。Milvus 从中写入 18,465 个可检索文本块。每个块携带快照哈希前缀和可点开的 Neo4j 节点引用。该迁移包的登记节点缺少原公告 URL，引用提供的是登记数据快照。有效期和状态按该快照呈现。

配置 `AGENT_MILVUS_URI` 和一个新 `AGENT_MILVUS_COLLECTION` 后写入索引。验收通过后，让 Agent 使用该 collection。原始 dump、登记数据导出、训练题和权重保存在授权环境。

~~~bash
agrireg-documents ingest /path/to/private-data/registry/documents.jsonl
agrireg-documents search "Dagda 登记资料" --registration-number 00A657-62 --mode reranked
~~~

## 构建训练集和留出集

脚本从真实登记号、产品、持有人和图谱边构造计划标签。问题由模板生成。每组绑定两个登记号，同一登记号只进入一个集合，主记录的持有人和产品组合也不跨集合。测试集包含未用于训练的问法，覆盖登记号精确检索、关键词检索、图谱实体和路径、对比、缺参追问、PubChem 核验、双来源检索与合规审批。按来源字段分层，700 条训练、100 条验证、200 条测试。

~~~bash
DATA=/path/to/private-data/planner
BASE=/path/to/Qwen3-1.7B
RUN=/path/to/runs/migration-sft-seed42

python evaluation/build_migration_planner_data.py /path/to/private-data/registry "$DATA"
agrireg-planner-sft check-data --train "$DATA/train.jsonl" --dev "$DATA/dev.jsonl" --test "$DATA/test.jsonl" --base "$BASE"
python evaluation/evaluate_registry_planner.py --data "$DATA"

agrireg-planner-sft train --base "$BASE" --dataset "$DATA/train.jsonl" --output "$RUN" \
  --steps 525 --save-steps 175 --four-bit --seed 42
python evaluation/evaluate_registry_planner.py --data "$DATA" --base "$BASE" \
  --run "$RUN" --output "${RUN}-eval" --four-bit --batch-size 8
~~~

三轮分别保存 adapter。先按验证集的关键动作和追问表现选 epoch，再对同一冻结测试集运行规则、原始模型和选中的 adapter。两轮任务按固定补参回复及真实记录快照中的证据 ID 评分。

检索评测由留出题生成两套相关性标注。精确组使用登记号过滤。关键词组按产品与持有人标注所有匹配登记记录，评估前五个文本块覆盖的记录和首次命中位置。

~~~bash
DOC_API=http://127.0.0.1:18082/api/agent/documents/search
python evaluation/evaluate_documents.py "$DATA/document_qrels_exact.jsonl" --api-url "$DOC_API" --limit 5
python evaluation/evaluate_documents.py "$DATA/document_qrels_keyword.jsonl" --api-url "$DOC_API" --limit 5
~~~

## 实测结果

Seed 42 在单张 RTX 3090 上完成 525 个优化步，用时 867.7 秒。第 1、2、3 轮的验证综合分分别为 50.8%、55.4% 和 52.5%。选择第 2 轮 `checkpoint-350` 对照同一个 Qwen3-1.7B 底座。

| 冻结测试指标 | Qwen3 底座 | 第 2 轮 QLoRA |
| --- | ---: | ---: |
| 参数齐全时关键动作正确 | 0/120 | 104/120 |
| 参数齐全时快照执行成功 | 0/120 | 103/120 |
| 缺参时原始计划拟调用 | 72/80 | 31/80 |
| 正确追问且原始计划无拟调用 | 0/80 | 38/80 |
| 首轮问对，补参后执行成功 | 0/80 | 37/80 |
| 给定补参后执行成功 | 0/80 | 78/80 |

分数衡量原始模型输出和冻结快照回放。主要错误集中在首轮缺参识别。服务执行仍会验证计划、处理显式追问和按号核对证据。

在全库索引上，Cross-Encoder 模式的证号组 40 条和关键词组 8 条均达到 Recall@5 1.0。证号组将登记号作为过滤条件。8 条关键词查询的热态检索接口 p95 在 CPU 上为 11.55 秒，在 GPU 上为 0.34 秒。

真实接口用 `00A657-62` 验证了精确引用、图谱路径、独立分项和补参后续跑。FastMCP 通过 Streamable HTTP 使用同一个 Milvus 索引和 Neo4j API，返回了登记片段和路径证据。[汇总指标](migration_result_seed42.json)
