# Direct DeepSeek 与 GraphRAG 外部对照实验

状态：30 条全量实验已完成；结果仍属于 **provisional external-source benchmark**，等待两位领域专家复核后才能称为专家金标准结果。

## 实验设计

该实验回答两个问题：

1. 与外部权威来源中的原子事实相比，Direct DeepSeek 和 GraphRAG 谁的命中率更高？
2. GraphRAG 是否能在回答之外提供可回到本地图谱的编号证据？

两边使用相同的 `deepseek-v4-flash`、`temperature=0.1` 和非思考模式。Direct DeepSeek 只收到原始问题；GraphRAG 先从 Neo4j 检索有界属性与关系证据，再让同一模型依据证据回答。GraphRAG 请求设置 `persist=false`，不会进入用户对话历史。

自动评分采用规范化后的确定性概念匹配，不使用 DeepSeek 给自己的答案打分。

## 外部候选集

| 类别 | 数量 | 来源 |
| --- | ---: | --- |
| CAS | 10 | NCBI PubChem |
| 分子式 | 10 | NCBI PubChem |
| 抗性/作用机制分组 | 8 | IRAC、FRAC、HRAC/WSSA |
| 作用机制 | 2 | IRAC |

每条记录包含问题、期望原子事实、可接受概念、来源 URL、记录号或页码定位，以及双人复核与仲裁状态。

## 全量结果

运行标识：`external-ablation-v0.1-corrected`，样本数 30。

| 指标 | Direct DeepSeek | GraphRAG | 差异 |
| --- | ---: | ---: | ---: |
| HTTP 成功率 | 100% | 100% | 0 pp |
| 外部事实命中率 | 86.67%（26/30） | 100%（30/30） | +13.33 pp |
| 拒答率 | 0% | 0% | 0 pp |
| P50 端到端延迟 | 988.15 ms | 1,952.06 ms | +963.91 ms |
| P95 端到端延迟 | 1,808.83 ms | 2,919.13 ms | +1,110.30 ms |
| 平均延迟 | 1,094.65 ms | 2,054.52 ms | +959.87 ms |

GraphRAG 的中位延迟约增加 97.5%，换来了本次候选集上 13.33 个百分点的命中率提升。不能只汇报准确率而忽略这一延迟成本。

### 分类别命中率

| 类别 | Direct DeepSeek | GraphRAG |
| --- | ---: | ---: |
| CAS | 90% | 100% |
| 分子式 | 90% | 100% |
| 作用机制 | 100% | 100% |
| 抗性/作用机制分组 | 75% | 100% |

### 成对结果

| 结果 | 数量 |
| --- | ---: |
| 两边都正确 | 26 |
| 仅 GraphRAG 正确 | 4 |
| 仅 Direct 正确 | 0 |
| 两边都错误 | 0 |

GraphRAG 的 `groundedRate`、引用出现率和引用编号有效率均为 100%。这些指标只证明回答带有可定位的图谱证据，不等价于专家已经确认“证据在语义上充分支持全部结论”。

## 4 个差异样本

1. `Prothioconazole` CAS：Direct 返回 `120983-64-4`，外部候选记录与图谱均为 `178928-70-6`。
2. `Abamectin` 分子式：候选记录使用 PubChem compound record 的 `C95H142O28`；Direct 返回主要组分 B1a/B1b 的分子式。该问题存在“混合物记录还是组分”的表述歧义，是专家复核的最高优先级样本，不能简单包装为模型常识错误。
3. `Cypermethrin` IRAC 分类：Direct 只回答 Group 3，候选记录要求更具体的 `3A`；GraphRAG 同时给出 Group 3 和 3A。
4. `Tebuconazole` FRAC 分类：Direct 回答靶标分组 `G1`，没有给出 FRAC code `3`；GraphRAG 同时给出 `FRAC 3, G1`。正式金标准应把问题改成“FRAC code 是什么”，减少层级歧义。

## 统计边界

- Direct 26/30 的 Wilson 95% 区间约为 70.3%–94.7%；GraphRAG 30/30 约为 88.6%–100%。
- 成对差异只有 4 个样本，双侧精确 McNemar 检验 `p=0.125`，尚不足以在 0.05 水平声称统计显著。
- 当前集合以原子事实为主，不能代表开放式法规判断、复杂登记比较或多跳因果解释。
- 候选集来自权威外部记录，但尚未完成双人领域复核，因此简历中只能写“外部来源候选基准”，不能写“专家金标准准确率 100%”。

## 自动指标

- `externalFactAccuracy`：答案是否包含候选记录要求的全部概念；
- `refusalRate`：答案是否明确表示无法确认；
- P50/P95：端到端响应时间；
- `citationPresentRate`：GraphRAG 是否给出 `[n]`；
- `citationIndexValidityRate`：引用编号是否存在于本次图谱证据；
- 成对结果：两边都对、仅 GraphRAG 正确、仅 Direct 正确、两边都错。

自动评分适用于当前单一原子事实问题。开放式登记合规结论仍需要专家逐句判断来源是否足以支持答案。

## 专家复核门禁

当前文件为外部来源候选集，而非“专家已核验金标准”。最终金标准要求两位领域专家独立接受；意见不一致时需要第三人仲裁。`evaluation/finalize_external_gold.py` 会阻止任何未完成复核的候选被导出为正式 gold 文件。

## 复现

```powershell
python evaluation/build_external_gold.py
python evaluation/compare_direct_vs_graphrag.py --tag external-ablation-v0.1-corrected
# 两位专家填写 CSV 后：
python evaluation/finalize_external_gold.py
```

原始明细与汇总写入被 Git 忽略的 `evaluation/results/`，候选集和复核表见 [evaluation/external_gold](../evaluation/external_gold/README_CN.md)。
