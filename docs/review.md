# 人工审核事实

审核文件是 JSON 数组，每个对象形如：

```json
{
  "source_path": "src/content/docs/学习生活/常用网站.md",
  "heading": "实际完整标题路径",
  "quote": "从 pending 原样复制的完整段落",
  "subject": {
    "name": "具体服务名称",
    "type": "Service",
    "campus": "shared",
    "aliases": [],
    "url": null
  },
  "relation": "USES_PLATFORM",
  "object": {
    "name": "具体平台名称",
    "type": "Platform",
    "campus": "shared",
    "aliases": [],
    "url": null
  }
}
```

这是格式示意，不是可直接导入的事实。复制 `pending` 中的实际路径、标题和完整引文；不能只摘取会丢失否定、例外或阶段的一小段。程序校验类型与当前原文精确匹配，**关系语义正确性仍由审核人负责**。小模型 `suggest` 输出也必须逐条核对。

允许的关系：Place → Place/Campus 的 LOCATED_IN，Place → Service 的 PROVIDES，Service → Platform 的 USES_PLATFORM，Service/Platform → Condition 的 REQUIRES。服务名称须区分校区及办理地点；平台 URL 只填写原文给出的真实地址。`unknown` 实体不会参与正常答案。

“身份证或身份证号”应保留为一个可选条件，不拆成两个都必须满足的条件。“至少两人打卡”是使用研讨间时的条件，不能改写成预约前需要两人。文中提到另一校区的地方不能直接继承当前目录的校区。

同一范围内互相矛盾的审核记录，设置相同 `conflict_key`、不同 `decision`。例如：两条记录分别标记 `conflict_key="shahe:某服务:预约阶段:网络"`，`decision="required"` 和 `decision="not-required"`。当前系统发现同组多种决策时隔离相关证据并返回 `partial/conflicting_evidence`。不得把不同校区、不同阶段、或互补条件误标为冲突。

`approve` 将审核记录写入本地 `data/reviewed_facts.json`；随后 `sync` 发布新版本。更新或撤销人工记录可停服后编辑该文件并同步。同一规则重复导入会去重。小组共享审核结果时，在核对后将资源整理进 `bupt_rag/resources/facts.json` 并提交 PR，不提交本地数据库。
