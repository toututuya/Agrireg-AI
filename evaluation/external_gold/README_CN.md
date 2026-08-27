# 外部来源金标准与专家复核

本目录目前保存的是 **30 条外部来源候选集**，还不是已经由专家确认的最终金标准。

## 数据来源

- 化学身份：NCBI PubChem PUG REST，包含 10 个有效成分的 CAS 与分子式；
- 杀虫剂作用机制：IRAC Mode of Action Classification；
- 杀菌剂作用机制：FRAC Code List；
- 除草剂作用机制：HRAC/WSSA Classification。

候选集不复制来源正文，只保存原子事实、原始链接、记录号和页码或表格定位信息。

## 文件

- `external_source_candidates_v0.1.jsonl`：30 条候选问题、期望原子事实和来源；
- `expert_review_template_v0.1.csv`：双人独立复核与仲裁表；
- `manifest_v0.1.json`：数据集版本和构成；
- `external_gold_v0.1.jsonl`：只有完成专家复核后才会生成。

## 复核规则

每条记录需要两位登记或农学领域复核者独立判断：

- `accept`：问题、答案和来源定位一致；
- `reject`：来源不能支持答案，或问题存在歧义；
- `needs_correction`：事实或表述需要修订后重新复核。

两人都填写姓名且均为 `accept` 时可以进入金标准。意见不一致时，必须由第三位仲裁者填写 `adjudicatedDecision=accept` 或 `reject`。不能用模型评分代替专家签字。

首轮复核应优先检查两个存在分类层级或对象边界歧义的样本：

- `ext-017`：Abamectin 应回答 PubChem mixture record 的分子式，还是 B1a/B1b 组分分子式；
- `ext-027`：问题中的“FRAC 哪一组”应明确指 FRAC code `3`，避免与靶标分组 `G1` 混淆。

完成 CSV 后运行：

```powershell
python evaluation/finalize_external_gold.py
```

只要仍有未复核、被拒绝或存在分歧的记录，脚本就不会生成“专家已核验”文件，防止把候选集误包装成正式金标准。

## 更新外部来源

PubChem 数据可以重新拉取：

```powershell
python evaluation/build_external_gold.py
```

IRAC、FRAC 和 HRAC 分类版本发生更新时，需要先修改来源 URL、定位信息和期望分类，再重新走双人复核。
