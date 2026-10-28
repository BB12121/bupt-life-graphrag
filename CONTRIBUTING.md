# 小组合作

推荐每个成员使用自己的分支，经 Pull Request 合并到 `main`。后端 API 类型变更需要同时更新 OpenAPI 并告知前端成员；已有字段不可无说明删除或改名。

建议分工：知识整理成员维护 `resources/`、别名与原文映射；后端成员维护同步、检索、QA 和接口；测试成员维护题库、审核正确性与故障回归；前端成员依据 `docs/frontend.md` 独立开发页面。

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
