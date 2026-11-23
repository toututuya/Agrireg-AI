# Qwen3 规划数据与微调流程

AgriReg AI 的 SFT 样本由真实或合成问题和审核过的计划 JSON 组成。每道题标注任务类型、实体、工具和参数。需要追问时写明缺失字段并将 `steps` 设为空。涉及合规筛查的计划保留人工审批标记。Neo4j 和 Milvus 用于验证计划执行和取证，标注、校验及规划器 SFT 可独立完成。

## 准备训练集和留出集

第一版可以按 700 条训练、100 条验证、200 条留出测试准备 1,000 条 JSONL。以授权业务问题或可核查的公开记录为种子。把完整题、删掉一个必填字段的版本及同源改写放在同一个 `group_id` 中。同组只进入一个分割。对照题优先覆盖登记号、待比较对象和关系路径两端。人工抽查同一对象及模板的变体是否遵守分组。

每个种子先标预期动作和关键入参。参数齐全的题在固定图谱或文档快照上回放，并核对记录 ID。缺参题标明应追问的字段，在补入固定回复后复测工具和证据。需要核对语义的样例由人工复核。APIGen 的分层校验提供了格式、执行与语义三层参考。BFCL 的 Missing Parameters 场景用对话检验模型能否识别无法从上下文补齐的字段。[APIGen 论文](https://arxiv.org/abs/2406.18518) · [BFCL 数据说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/data/README.md#bfcl-v3)

JSONL 每行必填 `id`、`question` 和 `plan`。`kind` 可用于按场景汇总分数。`group_id` 用于标记同源的题，`source_ref` 可写登记记录编号或授权来源的稳定引用。`documents_enabled` 默认为 `true`。追问题可用 `clarification_terms` 指定评测必须问到的字段词。可参考 [训练样例](planner_samples/train.jsonl) 和 [留出样例](planner_samples/test.jsonl)。

在 Agent 目录执行 `check-data`。它指出不合规的行，并在训练、验证和留出集之间检查重复 ID、规范化问题和已标注的组 ID。加 `--base` 时只在 CPU 加载 Qwen3 分词器来检查样本长度。

~~~bash
python -m pip install -e ".[tokenizer]"
agrireg-planner-sft check-data --train evaluation/planner_samples/train.jsonl --test evaluation/planner_samples/test.jsonl
agrireg-planner-sft check-data --train labels/train.jsonl --dev labels/dev.jsonl --test labels/test.jsonl --base /path/to/Qwen3-1.7B
~~~

## 训练和评测

用同一基座、量化设置和提示词分别评测原始模型和训练后的 adapter。沿用单卡微批 1、梯度累积 4 的设置，700 条训练题大致用 175 个优化步覆盖一轮。先在验证集挑训练步数，再在冻结的留出集报告结果。训练、评测和校验输出记录数据指纹。合成数据流程可通过省略 `--dataset` 复现。

~~~bash
python -m pip install -e ".[training,training-4bit]"
agrireg-planner-sft train --base /path/to/Qwen3-1.7B --dataset labels/train.jsonl --output runs/domain-v1 --steps 175 --four-bit --seed 42
agrireg-planner-sft evaluate --base /path/to/Qwen3-1.7B --dataset labels/test.jsonl --adapter runs/domain-v1 --output runs/domain-v1-eval.json --four-bit --seed 42
~~~

报告继续保留 `exact_actions` 的全参数严格匹配。另外在 `decision_checks` 中记录两类题的分母和下面的命中数。

| 场景 | 计数 |
| --- | --- |
| 需要追问 | 原始 JSON 提出非空工具步骤 |
| 需要追问 | 命中标注字段词且原始 JSON 未提出工具步骤 |
| 参数齐全 | 通过校验后仍要求用户补充 |
| 参数齐全 | 匹配工具和关键参数，登记号归一化后对比 |

关键参数计数跳过文档检索自由文本 `query` 的逐字匹配。文档实际命中及两轮补参后的任务成功率需要通过固定后端和证据 ID 回放测量。业务词的可接受表述先在验证集上复核，再固定评分口径。

### 何时做 GRPO

完成 SFT 对照后，若缺参误调用或补参后二轮任务失败仍是主要问题，且回放环境可以程序化验分，可以从同一 SFT checkpoint 做两组 GRPO。第一组按最终任务成功给分，第二组加入问对缺失字段的奖励，并约束缺参时的误调用。固定样本、采样预算和留出集，观察缺参误调用、两轮成功率及参数齐全时的执行成功率。[ToolRL 代码与奖励配置](https://github.com/qiancheng0/ToolRL)

## 对接 GitHub 上的官方流程

Qwen 官方的 MS-SWIFT 流程用 `messages` JSONL 做 SFT，训练时加载基座并产出 LoRA adapter。AgriReg 的标注可以导出为相同的 `system`、`user`、`assistant` 结构。assistant 内容就是计划 JSON。使用外部训练器时，按其 Qwen3 模板配置无思考模式，并复用项目的留出集做对照。[Qwen3 官方训练示例](https://github.com/QwenLM/Qwen3/blob/main/docs/source/training/ms_swift.md) · [MS-SWIFT 数据格式](https://github.com/modelscope/ms-swift/blob/main/docs/source_en/Customization/Custom-dataset.md)

~~~bash
agrireg-planner-sft export-messages --dataset labels/train.jsonl --output exports/train.messages.jsonl
~~~
