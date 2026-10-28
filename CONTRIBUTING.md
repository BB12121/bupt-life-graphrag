# 小组合作

当前任务、优先级、建议分工和验收标准统一维护在 [下一步任务与交接清单](docs/NEXT_STEPS.md)。成员认领后填写负责人，PR 注明任务 ID；完成时附验证记录并更新清单。

推荐每个成员使用自己的分支，经 Pull Request 合并到 `main`。后端 API 类型变更需要同时更新 OpenAPI 并告知前端成员；已有字段不可无说明删除或改名。

建议分工：知识整理成员维护 `resources/`、别名与原文映射；后端成员维护抽取、同步、检索、QA 和接口；测试成员维护题库、人工评分与故障回归；前端成员维护已联通页面及新能力的显示。

本地安装：`uv venv --python 3.11`，`uv pip install -e ".[dev]"`。修改后运行：

```text
python -m ruff check bupt_rag tests scripts
python -m ruff format --check bupt_rag tests scripts
python -m pytest -q
python scripts/export_openapi.py
```

工程测试使用明确标注的模型替身，不需要下载权重。它们验证接口和正确性约束，不能作为真实检索能力的性能结论。真实评测使用 `scripts/evaluate.py` 和固定指南提交。

只提交源代码、文档与已审核数据；不提交 `.env`、访问令牌、模型、SQLite、本机日志或个人资料。新引用要注明原来源及许可。修改实验口径时保留记录，不为得到更高分而删除失败题。

当前 GitHub 仓库由创建者管理。邀请其他成员需要其 GitHub 用户名，由仓库管理员在 Settings → Collaborators 中添加。

## 前端与全栈验证

前端源码在 `bupt-graphrag-frontend/`，执行 `npm ci`、`npm test`、`npm run build`。默认连接真实后端；仅演示时设置 `VITE_API_MODE=demo`。不要把服务端密钥写入 `VITE_*` 变量。

启动完整应用后，在前端目录执行 `npm run test:e2e`。本机浏览器测试走真实后端与模型；GitHub Actions 构建前端后使用隔离后端与明确标注的模型/资料测试替身执行同样的流程，不依赖模型下载，其耗时不是模型性能。

修改接口时同步更新前端类型和协议测试。原交接包中的截图、独立展示说明保留为历史记录；当前操作以仓库 README 和 `docs/integration.md` 为准。
