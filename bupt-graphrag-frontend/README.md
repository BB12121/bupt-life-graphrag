# 北邮生活指南前端

Vue 3 + TypeScript + Pinia + Vite，已与本仓库的 FastAPI 后端整合。默认连接真实接口。

## 运行

Node.js >=22.12。先按[根目录说明](../README.md)启动后端，再在本目录运行：

```text
npm ci
npm run dev
```

访问 http://127.0.0.1:5173，/api 自动代理到 http://127.0.0.1:8000，无需额外在线模型 API Key。

运行 `npm run build` 后重启 FastAPI，即可在 http://127.0.0.1:8000 使用完整应用；也可用 `npm start` 或 `npm run preview` 在 4173 预览，预览服务同样代理 API。Git 不包含 dist，首次必须构建。

## 验证

```text
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

浏览器测试需要已启动的完整应用。Windows 可设置 `PLAYWRIGHT_CHANNEL=msedge` 使用已安装的 Edge。CI 会启动隔离测试后端，不下载模型。

## 配置

`VITE_API_MODE` 默认 live，仅显式设置 demo 才加载交接的有限演示样例。`VITE_API_BASE_URL` 默认 /api/v1；`BUPT_BACKEND_URL` 控制开发与预览代理目标。参见 [.env.example](.env.example) 和[整合说明](../docs/integration.md)。

同步管理密钥在知识库页面按需输入，只保留在内存，请求完成后清空。不要将后端密钥写入 VITE_* 构建变量。

`docs/HANDOFF.md`、`docs/DEMO.md`、截图和独立 `展示.html` 保留为原始交接记录，记录的是整合前的演示版本；当前使用方式以本文件为准。指南内容及演示快照的许可见 [ATTRIBUTION](docs/ATTRIBUTION.md)。
