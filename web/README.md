# AgriReg AI Web

Vue 2 农药登记知识工作台。

- `/` 可以按登记号、实体名称或有效成分检索，并进入对应图谱。
- `/graph` 支持实体探索、关系穿透、产品对比、登记证据和 JSON 导出。
- `/ask` 提供带图谱引用的问答，可恢复最近对话。
- `/agent` 跟踪多步骤任务，支持缺参补充、审批、证据和报告回看。

## 启动

在 `web` 目录执行：

```powershell
pnpm install --frozen-lockfile
pnpm serve
```

前端默认使用 `http://127.0.0.1:8082`。图谱和问答调用 `http://127.0.0.1:4399`，任务分析调用 `http://127.0.0.1:8091`。服务配置详见 [项目启动说明](../README.md#技术栈)。如需修改接口地址，复制 `.env.example` 为 `.env.local` 并编辑其中的值。

图谱画布支持拖动和滚轮。键盘用户可按 Tab 选中节点、Enter 打开详情、方向键平移、加减号缩放、0 适配画布。使用方向键在详情页签之间切换。

## 构建

```powershell
pnpm build
python tools/spa_server.py --directory dist --port 8082
```

`spa_server.py` 会把 `/graph`、`/ask` 和 `/agent` 等前端路由回退到 `index.html`。
