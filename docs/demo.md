# 非测评功能演示

安装依赖、同步和构建步骤见 README。管理命令应停服运行。

```powershell
python -m bupt_rag.cli sync
python -m bupt_rag.cli extract
python -m bupt_rag.cli extract --model --limit 10
python -m bupt_rag.cli drafts --output data/drafts.json
```

从 drafts 选取真实记录 ID，逐条核对完整证据、校区、关系方向、否定、或条件与适用阶段。

```powershell
python -m bupt_rag.cli review RECORD_ID approved --reviewer YOUR_NAME --reason '原文明确支持关系，已核对校区和阶段'
# 如需修正，附加 --corrections data/corrected.json（FactRule 数组）
# 无合适关系用 text_only，错误草稿用 rejected，并填写具体依据。
python -m bupt_rag.cli sync
```

批准只保存审核记录，下次 sync 才发布。修改原文后，完整引文匹配失效的关系自动撤回。
重新运行同版本、同模型配置的抽取会复用已保存结果；模型或提示词版本变化会产生新的抽取配置。
费用、时间、否定与复杂条件保留在完整证据中；不能仅凭两个名称共现就批准关系。

页面演示：

1. 普通文本问题：“沙河宿舍电费是多少？”核对原文。
2. 跨文档多跳：“雁南一站式多功能厅的预约平台还能办理哪些手续？”逐边查看证据。
3. 澄清：“学活在哪里？”选择校区。
4. 实时拒答：“今天图书馆开放吗？”
5. 新事实全流程：运行 `python -m pytest tests/test_extraction.py -q`。该演示使用独立合成资料和向量替身，验证抽取、审核、发布、问答及撤回，不作为真实模型性能结论。

共享成果时导出草稿历史供审阅，将最终确认事实整理入 `resources/facts.json`；不要提交本地数据库。
