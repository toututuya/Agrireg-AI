# 图谱数据清洗

该目录保存可复现的 Neo4j 清洗和验收脚本。清洗脚本只应在由原始 dump 恢复出的独立数据库上执行，不应直接作用于唯一的原始库。

## 清洗范围

- 统一实体名称中的首尾空白、换行和连续空格；
- 合并 `Crop`、`Disease`、`ActiveSubstance`、`PesticideCategory` 中仅大小写或空白不同的实体；
- 删除空字符串、`--`、`N/A` 等占位字段；
- 统一登记有效期和管辖地区的应用字段；
- 隔离孤立节点、无效名称和已确认的跨实体污染字段；
- 为 8 类实体规范名称、有效成分 CAS 和登记标识建立索引。

原始导入值由数据库 dump 保留；实体名称另保留在 `raw_name`，合并实体保留 `aliases` 与 `merged_legacy_ids`。

## 执行

```powershell
$cypherShell = 'D:\path\to\neo4j\bin\cypher-shell.bat'

& $cypherShell -a bolt://127.0.0.1:7688 -f .\ops\data-cleaning\01_clean_graph.cypher
& $cypherShell -a bolt://127.0.0.1:7688 -f .\ops\data-cleaning\02_audit_graph.cypher
```

验收脚本应确认受控实体类型没有规范名重复组、没有重复关系，并列出日期覆盖、隔离记录、疑似重复翻译名称和索引状态。疑似复合名称只进入人工复核清单，不由脚本自动拆分。
