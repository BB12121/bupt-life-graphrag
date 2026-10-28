# 前端联调

Vue 前端已整合到 `bupt-graphrag-frontend/`，默认真实接口模式。构建后访问 `http://127.0.0.1:8000`；Vite 开发使用 5173，预览使用 4173，两者均代理 `/api` 到后端。当前操作以 [整合说明](integration.md) 为准。本文的 TypeScript 文件是原始最小示例，实际客户端位于前端 `src/api/client.ts`。

后端：`http://127.0.0.1:8000`；前缀：`/api/v1`。交互式文档 `/docs`，机器可读文档 `/openapi.json`。可复制 [TypeScript 请求示例](frontend-client.ts)。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/knowledge/status` | 当前源提交、知识版本、文档数、同步时间 |
| POST | `/knowledge/sync` | JSON `{ "ref": "main" }`，等待完成；指定 SHA 可复现 |
| GET | `/documents` | 当前正文列表 |
| GET | `/documents/{doc_id}?source_commit=完整SHA` | 原始 Markdown，旧版本可回溯 |
| GET | `/entities?q=名称&campus=shahe` | 名称/别名匹配，包含所选校区及 shared |
| POST | `/qa` | 完整问答请求 |

## 交互约定

页面常驻展示“依据指南快照”。将 `source_commit` 的短版本作为标签，点击可查看证据固定链接；不要展示为“实时官方信息”。

`answered` 显示答案和引用；`partial` 显示有证据的部分及限制；`abstained` 不显示虚构答案；`needs_clarification` 根据 `clarifications` 渲染选择控件。四种业务状态的 HTTP 状态均为 200，不能仅靠 `response.ok` 判断有答案。

澄清校区时保存选中的 `shahe/haidian` 到 `campus`。澄清实体时，将选项 `value` 保存到 `entity_bindings[mention]`，保留问题并重新提交整个请求。不要用选项 label 代替 ID。

证据通过 `answers[].evidence_ids` 与 `evidence` 连接；图通过 `answers[].path_ids` 与 `paths` 连接。路径节点是遍历顺序，边始终保存事实方向。例：`Platform ← Service` 的边仍是 `Service USES_PLATFORM Platform`，画箭头时用 `subject_id/object_id`。交集答案需要同时呈现 `branch_id=0/1`。

所有文本、原始 Markdown 和引文均按不可信资料处理；Vue 插值可直接展示，禁止未净化的 `v-html`。图片和链接不代表后端读取了它们的内容。

`GET /knowledge/status` 未初始化时版本为 0，提交与同步时间为 null。文档列表、实体列表为空数组；`POST /qa` 返回 503，提示先同步。同步期间后端排队处理其他业务请求；健康检查仍独立可用。同步按钮应防重复点击，客户端取消请求不保证取消后台同步。

错误统一为 `{ "error": { "code": "invalid_request", "message": "..." } }`。422 表示字段不合法，404 表示不存在的文档/历史版本，503 表示资料或模型不可用。启用管理密钥后同步缺少或错误密钥返回 401。其他服务器异常为 500。

## 常见演示

| 问题 | campus | 预期 |
|---|---|---|
| 雁南一站式多功能厅通过什么平台预约？ | shahe | 两跳回答 |
| 雁南一站式多功能厅的预约平台还能办理哪些手续？ | shahe | 跨文档三跳 |
| 雁南一站式多功能厅和雁北一站式多功能厅有什么共同平台？ | shahe | 双分支交集 |
| 补办学生卡在哪里？ | haidian | 逆向图查询 |
| 学活在哪里？ | null | 校区澄清 |
| 校园卡是什么？ | null | 实体澄清 |
| 今天图书馆开放吗？ | shahe | 实时拒答 |

`partial` 的真实源快照不一定有可触发的冲突或超限，前端可使用 `docs/examples/partial.json` 的明确标注测试夹具联调。其余示例来自真实快照运行。
