# AgriReg AI API

Spring Boot API 提供健康检查、Neo4j 图谱检索、最短路径、DeepSeek GraphRAG 和有状态对话。

## 配置

从 `.env.example` 创建本地配置，再通过启动脚本加载：

```powershell
Copy-Item .env.example .env.local
# 编辑 .env.local 后启动
.\start-local.ps1
```

DeepSeek 默认关闭。需要问答时在 `.env.local` 设置 `DEEPSEEK_ENABLED=true` 和 `DEEPSEEK_API_KEY`。默认使用成本较低的 `deepseek-v4-flash`，请求显式关闭思考模式。

对话历史默认保存在 H2 文件数据库 `data/agrireg-chat*`。API 每次只取最近两轮消息作为指代解析上下文，完整问题、回答、识别实体和图谱证据仍可从历史接口恢复。`data/` 已被 Git 忽略。

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
