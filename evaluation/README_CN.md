# GraphRAG 评测体系

这套评测把“检索是否正确”和“回答是否受图谱约束”分开验证，避免只看页面能否运行或挑少量演示问题。

## 为什么不是简单生成 2% 的问答

当前服务图谱有 21,712 个节点，但节点类型高度不均衡：登记号占大多数，作用靶点和作用方式很少。若直接随机抽取 2% 问题，结果会被登记号问题主导，也无法稳定覆盖最短路径、负例和两跳证据。

因此采用三层评测：

| 层级 | 数量 | 用途 |
| --- | ---: | --- |
| 结构化检索集 | 500 | 自动核对实体 ID、标签、路径长度和关系类型，并统计 API 延迟 |
| 语义 GraphRAG 集 | 50 | 核对实体证据、关系约束、负例拒答和引用编号完整性 |
| 外部来源候选集 | 30 | 用 PubChem、IRAC、FRAC、HRAC 原子事实比较 Direct DeepSeek 与 GraphRAG |

结构集包含 448 个实体检索，占当前节点数的 2.0634%，另含 52 条最短路径。实体按标签分层抽样：

| 标签 | 数量 |
| --- | ---: |
| RegisterNumber | 324 |
| Crop | 56 |
| Disease | 43 |
| ActiveSubstance | 5 |
| ChemicalClasses | 5 |
| PesticideCategory | 5 |
| TargetSite | 5 |
| ModeOfAction | 5 |

52 条路径覆盖登记号到作物、登记号到病虫害，以及“有效成分—登记号—作物 / 病虫害”两跳链路。50 条语义问题覆盖登记用途、成分登记、两跳关联、作物、病虫害、路径解释和不存在实体 7 类场景。

## 生成评测集

先启动本地 Neo4j，再在项目根目录执行：

```powershell
python evaluation/generate_dataset.py
```

默认读取 `http://127.0.0.1:7475/db/neo4j/tx/commit`。如 Neo4j HTTP 开启了认证，可通过环境变量提供用户名和密码：

```powershell
$env:NEO4J_HTTP_USERNAME='neo4j'
$env:NEO4J_HTTP_PASSWORD='your-password'
python evaluation/generate_dataset.py --neo4j-http http://127.0.0.1:7474/db/neo4j/tx/commit
```

生成文件位于 `evaluation/generated/`：

- `structural_eval.jsonl`：500 条结构化用例；
- `semantic_eval.jsonl`：50 条图谱一致性问题；
- `manifest.json`：图谱规模、配额、随机种子和版本。

这些文件可能包含本地图谱名称和内部节点 ID，因此不会提交到 GitHub。生成脚本和指标定义会提交，其他人在获得合法数据后可复现同一评测流程。

## 执行评测

启动 API 后运行：

```powershell
# 结构正确性与查询延迟
python evaluation/run_eval.py --suite structural --tag current

# DeepSeek GraphRAG 语义评测；请求不会写入用户对话历史
python evaluation/run_eval.py --suite semantic --tag semantic-current

# 两部分一起执行
python evaluation/run_eval.py --suite all --tag full-current
```

明细与汇总写入 `evaluation/results/`，同样不会提交到 GitHub。

## 指标定义

### 结构检索

- `entityHitRate`：返回中心节点 ID 与金标准一致的比例；
- `labelHitRate`：中心节点类型一致的比例；
- `lengthAccuracy`：最短路径长度一致的比例；
- `relationRecallPassRate`：期望关系类型全部出现在路径中的比例；
- `P50/P95`：单请求端到端延迟的中位数与 95 分位数。

### GraphRAG

- `groundedMatchRate`：正例能取到证据、负例不产生图谱证据的比例；
- `evidenceConstraintPassRate`：期望关系和端点全部出现在返回证据中的比例；
- `citationPresentRatePositive`：正例答案包含 `[n]` 引用的比例；
- `citationIndexValidityPositive`：答案引用编号都存在于本次证据列表中的比例；
- `faithfulnessProxyRate`：证据约束通过且引用编号完整的规则代理指标。

`citationIndexValidityPositive` 只能证明编号存在，不能证明该证据在语义上足以支持句子。`faithfulnessProxyRate` 也不是人工忠实度。要测外部事实正确率，仍需登记或农学专家依据原始来源逐条标注“问题—结论—来源证据”。

## 语义集质量控制

初次自动抽样发现了 `hygiene hygiene hygiene` 和 `poplar tree apple tree` 之类疑似重复翻译或字段粘连名称。正式 v0.2 语义集会排除占位符、重复词和明显异常机器翻译名称；这些异常仍保留在结构集与数据质量审计中，不能通过删掉失败用例来掩盖。

当前 50 条属于“图谱一致性金标准”，验证应用是否忠于当前 Neo4j 图谱，不代表图谱内容已经通过外部法规或农学来源核验。

## 外部来源与对照实验

外部候选集和专家复核流程见 [external_gold/README_CN.md](external_gold/README_CN.md)。它包含 20 条 PubChem 化学身份事实和 10 条 IRAC/FRAC/HRAC 作用机制事实。

运行对照实验：

```powershell
python evaluation/compare_direct_vs_graphrag.py --tag external-ablation-v0.1-corrected
```

脚本对相同问题分别调用：

1. `Direct DeepSeek`：只使用模型已有知识，不提供图谱或外部来源；
2. `GraphRAG`：通过现有 API 检索 Neo4j 属性与关系，再让模型依据编号证据回答。

评分使用规范化后的确定性概念匹配，不使用 DeepSeek 自己充当裁判。报告包括外部原子事实命中率、拒答率、P50/P95、GraphRAG 引用完整性，以及 `both_correct / graphrag_only / direct_only / neither` 成对结果。

2026-08-27 完成的 30 条全量实验中，Direct DeepSeek 命中 26/30（86.67%），GraphRAG 命中 30/30（100%）；GraphRAG P50/P95 为 1,952.06/2,919.13 ms，Direct 为 988.15/1,808.83 ms。完整结果、差异样本和统计边界见 [对照实验报告](../docs/EXTERNAL_ABLATION_REPORT_CN.md)。

脚本会把候选问题和相应本地图谱证据发送至配置的 DeepSeek API，重新运行前应确认数据出境范围。候选集尚未经过两位领域专家确认时，结果必须标记为 provisional，不能写成“专家金标准准确率”。
