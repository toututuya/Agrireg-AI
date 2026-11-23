# Qwen3 规划数据与微调流程

AgriReg AI 的 SFT 样本由真实或合成问题和审核过的计划 JSON 组成。每道题标注任务类型、实体、工具和参数。需要追问时写明缺失字段并将 `steps` 设为空。涉及合规筛查的计划保留人工审批标记。Neo4j 和 Milvus 用于验证计划执行和取证，标注、校验及规划器 SFT 可独立完成。

## 准备训练集和留出集

先从有权使用的典型查询收集问题，覆盖完整参数、只给一个比较对象、路径缺起点或终点、明确登记号等情况。每条标注都核对工具和参数是否能从问题中获得。将同一实体、登记记录和改写模板成组处理，再分到训练或测试侧，便于评测新实体和问法。

JSONL 每行一条，必填 `id`、`question` 和 `plan`。`kind` 可用于按场景汇总分数。`documents_enabled` 默认为 `true`。追问题可以用 `clarification_terms` 指定评测必须问到的字段，例如 `["登记号"]`。可直接参考 [训练样例](planner_samples/train.jsonl) 和 [留出样例](planner_samples/test.jsonl) 的结构。

在 Agent 目录执行以下命令。校验会指出问题行，并查找两份文件重复的 ID 和规范化问题。按实体、登记记录和模板分组由标注者在划分时完成。加 `--base` 时只在 CPU 加载 Qwen3 分词器来检查样本长度。

~~~bash
python -m pip install -e ".[tokenizer]"
agrireg-planner-sft check-data --train evaluation/planner_samples/train.jsonl --test evaluation/planner_samples/test.jsonl
agrireg-planner-sft check-data --train labels/train.jsonl --test labels/test.jsonl --base /path/to/Qwen3-1.7B
~~~

## 训练和评测

用同一基座分别评测原始模型和训练后的 adapter。训练、评测和校验输出记录数据指纹。原合成数据流程可继续通过省略 `--dataset` 复现。

~~~bash
python -m pip install -e ".[training,training-4bit]"
agrireg-planner-sft train --base /path/to/Qwen3-1.7B --dataset labels/train.jsonl --output runs/domain-v1 --steps 64 --four-bit --seed 42
agrireg-planner-sft evaluate --base /path/to/Qwen3-1.7B --dataset labels/test.jsonl --adapter runs/domain-v1 --output runs/domain-v1-eval.json --four-bit --seed 42
~~~

阅读结果时分别看有效计划、意图和工具、精确参数和缺失字段。规划器通过后，再接有授权的 Neo4j 和文档库验证工具返回与证据引用。

## 对接 GitHub 上的官方流程

Qwen 官方的 MS-SWIFT 流程用 `messages` JSONL 做 SFT，训练时加载基座并产出 LoRA adapter。AgriReg 的标注可以导出为相同的 `system`、`user`、`assistant` 结构。assistant 内容就是计划 JSON。使用外部训练器时，按其 Qwen3 模板配置无思考模式，并复用项目的留出集做对照。[Qwen3 官方训练示例](https://github.com/QwenLM/Qwen3/blob/main/docs/source/training/ms_swift.md) · [MS-SWIFT 数据格式](https://github.com/modelscope/ms-swift/blob/main/docs/source_en/Customization/Custom-dataset.md)

~~~bash
agrireg-planner-sft export-messages --dataset labels/train.jsonl --output exports/train.messages.jsonl
~~~
