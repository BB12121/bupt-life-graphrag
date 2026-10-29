# 干净环境复现记录（2026-10-28）

执行者：Codex。使用新克隆目录 `repository` 和新建 `.venv`，未继承上一目录的 Python 环境或 node_modules。这是自动化独立环境复现，不冒充另一位团队成员签字。

已执行并成功：

```powershell
uv --cache-dir .cache/uv venv .venv
uv --cache-dir .cache/uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
npm.cmd --prefix bupt-graphrag-frontend ci
npm.cmd --prefix bupt-graphrag-frontend test
npm.cmd --prefix bupt-graphrag-frontend run build
.venv/Scripts/python.exe -m bupt_rag.cli sync
.venv/Scripts/python.exe scripts/expand_knowledge.py
.venv/Scripts/python.exe -m bupt_rag.cli sync
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp .cache/final-tests
.venv/Scripts/python.exe scripts/verify_delivery.py
```

Windows / Python 3.12.14；安装全部项目依赖成功，前端 30 项测试、后端 49 项测试通过，Vue 类型检查和生产构建成功。
真实 BGE 从固定版本加载，首次从上游同步 39 篇正文；新增事实发布到知识版本2。
两条新主题跨文档两跳路径（劳动教育学时查询、体育运动达标成绩查询→本科教务管理系统→校园网环境）验证成功，原始响应保存于 `live-smoke.json`。
FastAPI TestClient 完成应用生命周期启动，`/healthz`、构建首页和知识状态接口均返回200；这不是浏览器端到端测试或长期运行服务证明。
PowerShell 默认策略拦截 npm.ps1，因此使用 npm.cmd，无需修改系统执行策略。

复现未做答案质量评测和资源测评。服务商模型为远程 qwen3.8-27b，不能据此声明本地1.5B～3B量化模型要求已满足。
