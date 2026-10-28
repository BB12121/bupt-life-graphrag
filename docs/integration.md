# 前后端整合与运行

Vue 3 和 FastAPI 已放在同一仓库。日常使用无需在线大模型 API Key；前端调用本机 `/api/v1`，后端使用本地 BGE 检索模型。

## 推荐：一个地址运行

在根目录完成 Python 安装与首次知识同步后：

```powershell
npm --prefix bupt-graphrag-frontend ci
npm --prefix bupt-graphrag-frontend run build
.venv/Scripts/python.exe -m uvicorn bupt_rag.api:app --host 127.0.0.1 --port 8000 --workers 1
```

访问 `http://127.0.0.1:8000`。FastAPI 提供构建文件和页面路由，刷新文档详情、知识库、检索对比均正常。`/docs`、`/openapi.json` 和 `/api/v1/*` 保持原用途。缺失 API 或静态资源返回 404，不会误返回首页。

`scripts/start.ps1` 自动安装依赖、构建前端并启动服务；已有构建可加 `-SkipBuild`。首次生成 dist 后要重启后端。未构建前端时后端仍可独立运行 API。请先停止旧后端再启动新实例，数据目录不支持多个进程同时占用。

## 开发与预览

在一个终端运行后端，在另一个终端执行：

```powershell
Set-Location bupt-graphrag-frontend
npm ci
npm run dev
```

开发地址 `http://127.0.0.1:5173` 支持热更新；`npm run preview` 或 `npm start` 使用 `http://127.0.0.1:4173`。开发和预览都将 `/api` 原样转发至 `http://127.0.0.1:8000`。

如后端换端口，在前端终端设置 `BUPT_BACKEND_URL`。`npm start` 从进程环境读取；Vite 也可读 `.env.local`。后端不可用时显示错误，不自动退回演示答案。

## 配置与同步

- `VITE_API_MODE` 默认 live，明确设置 demo 才使用有限演示数据并显示“演示版”。变更配置后需重启开发服务或重新构建。
- `VITE_API_BASE_URL` 默认 `/api/v1`，同源入口无需另配。
- 后端 `BUPT_ADMIN_KEY` 非空时，在知识库页面展开“同步管理密钥”后填写。只随本次同步发送 `X-Admin-Key`，完成后清空，不存入浏览器存储或构建文件。
- 问题最多 2000 字。客户端阻止问答和同步重复提交，后端仍通过锁保护跨客户端版本一致性。

页面使用后端实际文档/实体 ID。澄清后保留原问题、校区和 `entity_bindings` 重发完整请求。查看原文显式传证据的 `source_commit`；逆向路径保留规范事实方向。两种检索模式顺序执行并检查快照一致。

## 自动验证

```powershell
.venv/Scripts/python.exe -m pytest -q
Set-Location bupt-graphrag-frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

浏览器测试连接已启动的完整应用，默认 8000，可用 `BUPT_E2E_URL` 更改。Windows 已安装 Edge 时，设置 `$env:PLAYWRIGHT_CHANNEL='msedge'` 可省去 Chromium 下载。测试按当前完整 SHA 执行一次重复同步，不主动跟随 main 更新。

CI 设置 `BUPT_E2E_START_FIXTURE=1` 启动隔离测试后端，使用模型与资料替身；HTTP、图遍历、编排和前端仍是实际应用。真实模型性能继续使用独立评测，不从 CI 推断。
