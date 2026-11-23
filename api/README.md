# AgriReg AI API

Spring Boot API 提供健康检查、Neo4j 图谱检索、最短路径、DeepSeek GraphRAG 和有状态对话。

## 配置

从 `.env.example` 创建本地配置，再通过启动脚本加载：

```powershell
Copy-Item .env.example .env.local
# 编辑 .env.local 后启动
.\start-local.ps1
```

DeepSeek 默认关闭，问答接口直接引用 Neo4j 中的释义和关系。设置 `AGENT_ANSWER_URL` 后，缺少合适图谱证据时可通过 Agent 按登记号查登记资料，或让 Qwen3 基础模型解释通用概念。对于已挂载的登记快照，回答会标明快照来源。需要 DeepSeek 综合图谱证据时，可设置 `DEEPSEEK_ENABLED=true` 和 `DEEPSEEK_API_KEY`。

对话历史默认保存在 H2 文件数据库 `data/agrireg-chat*`。使用 DeepSeek 解析指代时可读取最近两轮。完整问题、回答、识别实体和证据可从历史接口恢复。`data/` 已被 Git 忽略。

## 查询约束

- 实体搜索覆盖 `name`、商品名、农药名、有效成分和 CAS 号；
- 排序优先级为主名称精确命中、其他属性精确命中、前缀命中、包含命中；
- 邻域最多返回 48 条关系；
- 最短路径最多搜索 6 跳；
- 大模型仅接收有界图谱证据，密钥不会返回前端。

## 对话接口

- `GET /api/conversations?visitorId=...`：最近对话；
- `GET /api/conversations/{id}?visitorId=...`：恢复完整消息和证据；
- `DELETE /api/conversations/{id}?visitorId=...`：删除对话；
- `POST /api/assistant/ask`：请求体可携带 `visitorId` 与 `conversationId`，继续多轮追问。

## 构建

```powershell
mvn -DskipTests package
```
