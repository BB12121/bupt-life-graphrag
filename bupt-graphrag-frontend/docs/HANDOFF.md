> 整合更新：本文保留原始前端交接记录。当前默认真实接口，预览服务已支持 API 代理，使用方式与验证结论请看 [当前 README](../README.md) 和 [全栈运行说明](../../docs/integration.md)。

# 前端交接文档

交付日期：2026-10-28。

## 1. 接手结论

交付物是 Vue 3 + TypeScript 前端源码、锁文件、生产构建 dist、本机静态展示服务、人工核对演示数据、测试与截图。

默认可独立运行 demo；切换 live 后按原设计调用 FastAPI。没有真实后端进程、OpenAPI 文件和模型运行环境，因此没有声称完成真实模型端到端联调。

## 2. 工程地图

    src/main.ts                    Vue/Pinia/Router 启动与路由
    src/App.vue                    顶部导航、移动菜单、搜索、关于、来源抽屉
    src/styles.css                 视觉 tokens、组件样式、响应式与阅读样式
    src/api/types.ts               根据 PDF 手工对齐的 DTO
    src/api/client.ts              demo/live 适配、超时、错误、六个接口
    src/stores/workspace.ts        状态、互斥任务、问题记录、通知
    src/lib/presentation.ts        标签、方向、引用校验、安全 URL、导出
    src/lib/markdown.ts            安全 Markdown、标题锚点、固定版本内部链接
    src/components/AnswerPanel.vue  四状态、澄清、答案/路径/证据联动
    src/components/PathDiagram.vue  事实方向和文字等价路径
    src/components/SourceDrawer.vue 历史 commit 原文与准确行号
    src/components/ModalShell.vue   原生 dialog 与焦点恢复
    src/views/AskView.vue           提问与示例
    src/views/DocumentsView.vue     当前清单与目录导航
    src/views/DocumentView.vue      阅读/原文行号
    src/views/KnowledgeView.vue     状态与同步
    src/views/LabView.vue           两模式顺序对比
    src/data/guide.json            固定版本 39 篇真实原文
    src/data/demo.ts               有限人工核对样例与模拟回执
    tests/protocol.test.ts         原文、路径、状态与安全显示
    tests/api.test.ts              live 适配的 HTTP Mock 验证
    scripts/preview.mjs            无第三方依赖的静态展示服务

types.ts 当前不是 OpenAPI 自动生成文件；待后端提供 /openapi.json 后，可生成并评审替换类型。不要在没有 schema 的情况下宣称已完成 SDK 自动同步。

## 3. 环境与命令

Node.js >=22.12，交付环境实测 Node 26.0.0 / npm 11.12.1。依赖以 package-lock.json 为准。

    npm ci
    npm run dev
    npm test
    npm run build
    npm start

dev 使用 5173，npm start 使用 4173，均只监听 127.0.0.1。PORT 环境变量可修改独立展示端口。生产构建在 dist；分享时不要携带 node_modules。

## 4. 环境变量与部署

VITE_API_MODE：demo/live，默认 demo。
VITE_API_BASE_URL：默认 /api/v1；可以指定已正确配置 CORS 的后端地址。

Vite 开发代理把 /api 原样转发到 http://127.0.0.1:8000。后端端口不同请修改 vite.config.ts。访问前端和后端的本机地址不是同一个进程。

VITE_* 都会进入浏览器构建，禁止写服务端密钥。切换环境后重启开发服务/重新构建。

生产部署需要：

1. VITE_API_MODE=live 时重新构建。
2. 静态目录指向 dist。
3. /api/* 代理到后端并保留 /api/v1 前缀。
4. 其他前端路由使用 index.html 回退，避免刷新 /documents/:id 时 404。
5. 后端超时与代理超时要配合本机模型等待时间。

独立 scripts/preview.mjs 不做 API 代理。/api 返回明确的 503 JSON；不存在的静态资源返回 404，避免 JS 请求被错误返回 HTML。它是本机展示服务，不是多用户生产后端。

## 5. 已对齐的六个接口

统一前缀 /api/v1；ID 和文本为字符串、数组无值为 []。

| 方法 | 路径 | 发送 / 读取 |
| --- | --- | --- |
| POST | /qa | 完整 QARequest，读取 QAResponse |
| GET | /knowledge/status | repository、commit、revision、count、time |
| POST | /knowledge/sync | {ref}，阻塞等待 SyncResult |
| GET | /documents | {items: Document[]} |
| GET | /documents/{doc_id} | 可选 source_commit；读取 document/text |
| GET | /entities | 可选 q/campus；实体适配已实现，未提供独立全量图页 |

QARequest：

    {
      "question": "学活是什么？",
      "campus": null,
      "mode": "hybrid",
      "entity_bindings": { "学活": "所选实体ID" }
    }

前端校区只发送 shahe、haidian 或 null。mode 仅 hybrid/vector。shared/unknown 仅作为实体范围，不能发送为 QA 校区。

实体澄清使用原样 mention 作键，重发完整请求。没有 messages/conversation_id；记录并不构成多轮上下文。输入修改后不会复用上次问题的实体绑定。

## 6. 四类业务状态与错误

所有四类状态都可为 HTTP 200：answered、partial、abstained、needs_clarification。前端不能只看 HTTP 成功。

- answered：展示返回结论与全部支持材料。
- partial：截断/冲突保持提醒，允许 answers 为空。
- abstained：按 no_evidence、unknown_entity、unsupported_query、realtime_unavailable 解释；未找到不等于不存在。
- needs_clarification：按 options 选择 campus 或 entity_bindings，再完整重发。

错误体预期 {error:{code,message}}。422/404/503/500 和网络错误均有可读提示。POST 不自动重试；180 秒等待超时可在 client.ts 调整，超时不声称取消服务端任务。

建议后端统一 FastAPI 自动 422 的默认体；未统一时前端只显示一般 HTTP 错误，不解析未约定的 detail 结构。

## 7. 图与证据不可破坏的约束

1. Path.nodes 是遍历顺序，Edge 保存事实方向。两者不同，逆向遍历也不反转事实。
2. 分支交集按 branch_id 展示，结论支持必须保留两个分支；前端不重新计算业务交集。
3. Edge 没独立 ID，视图 key 使用 path.id + edge 序号；不按 subject/object 把并行关系吞掉。
4. 图只展示后端返回路径，不从相同校区、共现或超链接补边。
5. 结论的 path_ids/evidence_ids 以及路径边的 evidence_ids 必须可解析，否则显示材料不完整。
6. QAResponse 没顶层 entities。文本题 entity_ids 未必能解析为实体详情，不因此拒绝合法回答。
7. 没有 query_type，前端不根据问句自行判定必须存在图路径。
8. 不生成置信度百分比、检索分数、真实阶段进度或未返回的冲突分组。
9. REQUIRES 不重写条件：“身份证或身份证号”和适用阶段必须保留。
10. 关联路径证据不受文本 Top10 限制。所有 evidence 可以查看，不裁成十条。

路径使用 Vue/HTML 和 Lucide 箭头，当前无图数据库或 Cytoscape 依赖；这使有限三跳更容易阅读。文字路径与手机竖向视图均可使用。

## 8. 固定版本与来源

来源：byrdocs/bupt-survival-guide。
完整提交：417fc690834fbc4406f48e503f5ef1f832d495db。

源库共 42 篇 Markdown/MDX，排除 index.mdx、contributing.md、acknowledgments.md，39 篇进入演示资料库。demo doc_id 是前端打包用路径哈希，不要求后端采用同一算法；live 切换后以后端 ID 为准。

Evidence 的 quote 直接取原文 line_start–line_end，1-based 且两端包含。测试逐字校验，未先清洗 Markdown。查看上下文明确传 evidence.source_commit；本地版本不存在时保留引文和固定提交链接，不自动替换最新版。

历史记录只在内存中保留最近 15 条。旧回答永远保存原始 response 版本。同步后如果 revision 改变，仅提示可重新查询，不重写旧回答。

Document 没 campus/category 字段。资料库的分组仅为 source_path 导航，不将目录名解释为所有事实的校区范围。

## 9. 同步与任务互斥

当前同步等待完成后返回。问答、对比实验与同步在本客户端互斥；后端仍必须实施跨客户端串行队列。

sync 不提供 job_id、阶段或进度。界面仅显示不确定 loading 和已等待秒数。没有百分比、伪阶段、自动 POST 重试或服务端取消承诺。

status 不含 pending_count，界面不从状态接口推断待审核数量。仅在本次同步回执中显示该值。changed=false 仅表示未发布新版本。

网络失败后状态页重新读取已发布快照，保留旧问答。现有协议无法恢复正在执行的任务；超时后应核对服务端状态，不能自动重发任务。

演示 sync 仅模拟检查内置快照，固定 changed=false；不联网拉取 main。页面明确标注“最近演示检查”，不虚构后端同步记录。

## 10. Markdown 与交互安全

阅读视图剥离 frontmatter 和 HTML 注释，但原文始终保留不变。禁用 HTML，不编译 MDX，不加载图片、不执行原文指令。图片显示来源占位提示。

链接只放行 http/https 和文内锚点；固定仓库内部文档链接转换为同一 commit 的 GitHub 路径。新窗口使用 noopener/noreferrer。原文/quote 用 Vue 文本输出；只有受控 Markdown 渲染结果使用 v-html。

原生 dialog 提供焦点限制、Esc 和关闭后恢复。跳转主内容、按钮说明、中文输入法处理、减少动画与无横向溢出的手机布局均已实现。没有宣称完整的无障碍认证。

## 11. 演示数据与真实能力

demo.ts 是有限的人工核对规则样例，650ms 人为等待仅用于观察 loading。不能用来评估 Dense、BM25、图检索或 Qwen。未知问题返回 unsupported_query 并提示连接真实后端。

部分/冲突样例只测试状态显示。冲突样例不编造矛盾事实，明确声明不表示真实指南已出现冲突。对比实验固定使用沙河参数，顺序请求 hybrid/vector；仅校验 commit/revision，一致模型和上下文预算需要后端保证。

## 12. 后端接手检查表

- 提供 OpenAPI 和四状态完整实例，尤其是逆向、交集、跨两文档路径。
- 统一 422 错误体，确认 question 长度和等待超时。
- 核对实体绑定校验、校区冲突、unknown/shared 范围。
- 保证答案、路径、每跳证据的引用完整。
- GET documents 兼容历史 source_commit 和准确源行号。
- 校验更新事务、失败保留旧版本、跨客户端串行。
- 用真实后端验证 60–80 道题；正确率和完整证据链基于人工标注。
- 阶段耗时、内存峰值、模型名、预算若需要展示，应新增明确的评测字段。

## 13. 后续迭代

可以继续做实体浏览、本地持久收藏、更多图视图。以下需要后端新协议，不是当前承诺：SSE、可恢复同步任务、全量子图、冲突分组、Web 审核、Rerank 开关、三路消融、Agent 会话、用户与权限系统。

不要只加按钮就宣称这些能力完成。新增接口先约定 capability/schema，再实现控件。

## 14. 本次界面调整

按用户反馈，视觉调整为简约、现代、直观。首页只保留标题、输入、三个常见问题和指南入口。移除侧栏、英文装饰标签、宣传口号、流程插画、首页统计和重复提示。

- 导航固定为问答、指南、知识库、检索对比；手机通过菜单展开。
- 背景白色，正文 #1D1D1F，次级文字 #6E6E73，交互蓝色 #0071E3。
- 采用本机系统字体；卡片用于分组，不在每段正文外增加容器。
- 来源版本、业务警告、校区澄清、原文行号继续保留；高级版本输入默认收起。
- 全局样式集中在 src/styles.css；760px 切换手机导航和结果页签，420px 调整窄屏间距。1000px 以下关系链纵向排列。
- 页面文案使用直接的功能名称，例如“关系路径”“请补充信息”“检查更新”，避免口号和无业务意义的双语标签。

接口、演示数据、来源引用规则没有改变。原始指南文本未修改。
