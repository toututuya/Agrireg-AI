# AgriReg Agent 工程验收报告

验收日期：2026-08-28。

## 自动化结果

| 项目 | 结果 | 内容 |
| --- | ---: | --- |
| Pytest | 11 / 11 | 规划、受控工具、证据去重、字段冲突、interrupt / resume、SQLite Run Store 和异步启动接口 |
| 路由契约 | 12 / 12 | 事实查询、对比、关系路径、缺失信息、自动审批与显式审批 |
| Vue production build | 通过 | `/graph`、`/ask`、`/agent` 路由拆包并生成生产资产 |
| 响应式浏览器检查 | 通过 | 1440×900 与 375×812；移动端无页面横向滚动，任务历史与证据可展开 |

运行命令：

```powershell
cd agent
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python evaluation\run_eval.py
```

## 本机真实链路

依赖：本机 Neo4j 4.4 图谱（22,328 节点 / 145,579 关系）、Spring Boot API、DeepSeek、PubChem PUG REST 和 FastAPI Agent。

| 任务 | 工具结果 | 证据 / 差异 | 状态语义 |
| --- | --- | --- | --- |
| `Chlorantraniliprole 与哪些病虫害有关？` | 3 次成功、0 次失败 | 48 条去重证据，覆盖 GDP-KG、GraphRAG、登记字段集和 PubChem | 直接完成并生成报告 |
| `核验 Abamectin 的登记与使用风险` | 3 次成功、0 次失败 | 48 条去重证据，检测到 1 组分子式口径差异 | `waiting_approval` → approve → 从检查点恢复 → 完成报告 |

浏览器中再次从 `/agent` 发起普通任务，SSE 收到 7 条用户可见事件，页面最终显示 12 条折叠证据卡和完整报告，控制台无错误。

## 指标边界

这些结果证明任务编排、受控工具、真实图谱、外部核验、人工确认、状态恢复和 UI 流式更新能够协同运行。它们不证明 48 条证据都与最终问题同等相关，也不代表领域答案准确率、生产并发能力或法律 / 登记合规结论。后续需要针对工具选择准确率、证据精确率 / 召回率、冲突召回、报告忠实度、P50 / P95 延迟和人工采纳率建立独立评测集。

