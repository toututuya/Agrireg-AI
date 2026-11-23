# AgriReg AI 登记 Agent 规划器 SFT

## 数据

快照来自农业农村部《农药登记信息 2026 年第 11 期》附件 1，保留 645 个登记证号、持有人、产品名和 Excel 行号。每个场景分配两条公告登记记录，同组题留在同一个集合。训练、验证和测试分别有 140／20／40 组，对应 700／100／200 道中文题。三个集合使用各自的问句模板。产品名和企业可以重现，登记证号按组隔离。

每组有 3 道信息齐全题和 2 道缺参题。其中两题考察精确文档检索和登记号追问，另两题考察对比或关系路径。最后一题从图谱查询、PubChem 核验、登记材料关键词检索、文档和图谱联合查询、需人工确认的合规复核中选取。部分训练题使用 Agent 收到补充信息后的输入格式。题目和计划标签由脚本生成。

公告页面及附件下载位于[农业农村部](https://zzys.moa.gov.cn/gzjl/202607/t20260729_6486303.htm)。`registry_planner_v1/manifest.json` 固定各集合、来源快照和测试补参场景的指纹。每条样本的 `source_ref` 指向附件并附有对应 Excel 行号，PubChem 引用和同组的其它登记记录可在快照中核查。

## 训练与选型

使用 Qwen3-1.7B、NF4 QLoRA、rank 8、学习率 2e-4、有效批量 4、seed 42。训练一条 3 epoch 的线性学习率轨迹，在 175、350、525 个优化步保存适配器。每份权重都在同一验证集上用贪心解码评估。

验证分数取两项的算术平均。

- 信息齐全时，任务类别、审批要求、工具顺序和关键参数正确的比例。
- 信息缺失时，问到对应字段且原始输出没有拟调用任何工具的比例。

得分相同时，优先选择较少在缺参时拟调用工具的权重，其次优先较早的 epoch。选型后再用冻结测试集比较现有规则、同一量化底座和所选适配器。对比包含以下指标。

| 指标 | 口径 |
| --- | --- |
| 缺参拟调用率 | 80 道缺参题里，模型原始 JSON 的 `steps` 非空的比例。运行时保留自己的校验。 |
| 有效追问率 | 80 道缺参题里，任务类别正确、追问命中标注字段且没有拟调用的比例。 |
| 齐全题关键动作正确率 | 120 道齐全题中，任务类别、审批要求、工具顺序及关键参数正确的比例。文档搜索的自然语言 query 另由快照命中检查覆盖。 |
| 齐全题快照执行成功率 | 关键动作正确，且每次工具调用返回快照证据并覆盖标注证据的比例。 |
| 两轮成功率 | 首轮正确追问且零拟调用，追加固定补充信息后能执行正确动作并命中快照证据，占 80 道缺参题的比例。 |

快照回放使用公告登记号、持有人和产品名匹配，以及冻结的 PubChem CID。它测的是规划和参数如何驱动查询，实验覆盖的语料是这一期公告和上述任务模板。线上检索质量、会话分布和人工判断需要单独评估。

## Seed 42 实测

单张 RTX 3090 完成 525 个优化步，用时 867.9 秒。PyTorch 峰值分配显存为 3,239 MiB。表中三个 checkpoint 来自同一次训练。

| Epoch | 验证综合分 | 齐全题关键动作正确 | 有效追问 | 缺参拟调用 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 53.3% | 49/60 | 10/40 | 25/40 |
| 2 | 67.9% | 53/60 | 19/40 | 16/40 |
| **3** | **70.0%** | **54/60** | **20/40** | **16/40** |

第 3 轮用于冻结测试。相对第 2 轮，验证集中多答对 1 道齐全题和 1 道追问题。

| 冻结测试指标 | 现有规则 | Qwen3 底座 | 第 3 轮 QLoRA |
| --- | ---: | ---: | ---: |
| 运行时可解析计划 | 200/200 | 0/200 | 182/200 |
| 缺参拟调用 | 40/80 | 77/80 | 13/80 |
| 有效追问 | 0/80 | 0/80 | 58/80 |
| 齐全题关键动作正确 | 24/120 | 0/120 | 103/120 |
| 齐全题快照执行成功 | 24/120 | 0/120 | 102/120 |
| 两轮成功 | 0/80 | 0/80 | 58/80 |
| 提供固定补参后执行成功 | 20/80 | 0/80 | 79/80 |

同一提示和解码设置下，底座在 200 道首轮题中输出 184 个 JSON 对象，均使用数字型首步 ID 和非字符串型 `missing_information`。表中「现有规则」独立运行，衡量部署中的规则规划路径。

第 3 轮的 13 次缺参拟调用全部发生在登记号缺失题，原始步骤均不满足工具契约。另有 9 道路径题追问「终点实体名称」，严格指标要求命中「持有人」。8 道合规复核题的原始审批标记均为 false。Agent 运行时另有强制审批判断。

本轮评估覆盖五个工具，选用第 3 轮权重。复验优先检查登记号追问、合规审批和文档图谱联合检索。实验使用 seed 42 和这一期公告派生的问句。训练、验证、测试和权重指纹见 [运行记录](registry_planner_v1/results/seed42/)。

## 复现

以下命令在 `agent` 目录执行。先安装项目的 `training` 和 `training-4bit` 可选依赖。仓库包含冻结数据，重新解析原始附件时另装 `xlrd==2.0.2`。

```bash
python evaluation/build_registry_planner_data.py /path/to/original-attachment.xls evaluation/registry_planner_v1
agrireg-planner-sft check-data --train evaluation/registry_planner_v1/train.jsonl \
  --dev evaluation/registry_planner_v1/dev.jsonl --test evaluation/registry_planner_v1/test.jsonl \
  --base /path/to/Qwen3-1.7B
python evaluation/evaluate_registry_planner.py --data evaluation/registry_planner_v1
agrireg-planner-sft train --base /path/to/Qwen3-1.7B \
  --dataset evaluation/registry_planner_v1/train.jsonl --output runs/registry-planner-v1-s42 \
  --steps 525 --save-steps 175 --four-bit --seed 42
python evaluation/evaluate_registry_planner.py --data evaluation/registry_planner_v1 \
  --base /path/to/Qwen3-1.7B --run runs/registry-planner-v1-s42 --four-bit
```

## 第 4、5 轮续训

续训以第 3 轮的 `checkpoint-525` 初始化，沿用 700 条训练样本、有效批量 4 和 seed 42。原 checkpoint 只保存了模型权重，因此续训重新初始化优化器，学习率从 5e-5 线性降至 0。每 175 个优化步保存一次，用同一个验证集、评分和解码设置比较三个权重。此设置验证低学习率续训的收益。

```bash
agrireg-planner-sft train --base /path/to/Qwen3-1.7B \
  --dataset evaluation/registry_planner_v1/train.jsonl --output runs/registry-planner-v1-s42-extension \
  --init-adapter runs/registry-planner-v1-s42/checkpoint-525 --learning-rate 5e-5 \
  --steps 350 --save-steps 175 --four-bit --seed 42
python evaluation/evaluate_registry_planner.py --data evaluation/registry_planner_v1 \
  --base /path/to/Qwen3-1.7B --four-bit --output runs/registry-planner-v1-s42-extension/dev-check \
  --dev-checkpoint 3 runs/registry-planner-v1-s42/checkpoint-525 \
  --dev-checkpoint 4 runs/registry-planner-v1-s42-extension/checkpoint-175 \
  --dev-checkpoint 5 runs/registry-planner-v1-s42-extension/checkpoint-350
```

| Epoch | 验证综合分 | 齐全题关键动作正确 | 有效追问 | 缺参拟调用 |
| --- | ---: | ---: | ---: | ---: |
| 3 | 70.0% | 54/60 | 20/40 | 16/40 |
| 4 | 71.7% | 53/60 | 22/40 | 16/40 |
| **5** | **74.2%** | **53/60** | **24/40** | **15/40** |

两轮续训实际增加 350 个优化步，用时 573.8 秒。第 3 轮复评复现原验证计数。第 5 轮综合分高 4.2 个百分点，有效追问多 4 道，齐全题正确动作少 1 道。第 5 轮是这个验证集上的续训候选。完整冻结测试结果见前文的第 3 轮报告。

一次续训尝试因非有限梯度中止。切回首轮实验所用的 RTX 3090 后，四步诊断和正式续训均通过，三个适配器的权重均为有限值。验证与权重指纹见 [续训记录](registry_planner_v1/results/seed42/epoch_extension.json)。
