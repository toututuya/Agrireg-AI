# AgriReg AI Web

Vue 2 图谱工作台，只保留“知识图谱”和“AI 问答”两条主路由。

## 交互

- `/graph`：原生 SVG 环形 / 路径布局，支持节点拖拽、画布平移、滚轮缩放、筛选、适配画布、重新布局和全屏；
- 图谱可按实体类型筛选，两侧面板可收起；单击查看属性、登记证据与直接关联，双击或使用详情按钮进行局部增量展开；
- 业务视角提供有效成分全景、作物—病虫害—登记产品和登记产品穿透入口；产品对比可逐项展示两个登记产品的属性与关系差异；
- AI 回答正文引用和依据卡片可定位回图谱，高亮对应的两个实体与关系边；图谱和产品对比结果均可导出为 JSON；
- “关系穿透”调用后端最短路径接口，并把中间登记、成分、作物或病虫害整理为可读的关系解释；
- `/ask`：展示 GraphRAG 回答、识别实体、证据关系和追问建议；左侧提供最近对话，新建或恢复对话后，历史回答中的引用仍能重新定位图谱证据。

## 启动

```powershell
pnpm install
pnpm serve
```

默认 Web 端口为 8082，API 地址为 `http://127.0.0.1:4399`。如需修改：

```powershell
Copy-Item .env.example .env.local
```

## 构建

```powershell
pnpm build
python tools/spa_server.py --directory dist --port 8082
```

`spa_server.py` 会把 `/graph`、`/ask` 等 history 路由回退到 `index.html`。
