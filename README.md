# 北邮生活指南 GraphRAG

本次更新：支持 `extract [--model]` 批量抽取、`drafts` 导出、`review` 审核与断点恢复，见 [演示流程](docs/demo.md)。默认模型为百炼 `qwen3.8-27b`，接入记录见 [模型配置](docs/model-runtime.md)。仓库根目录 `.env` 自动加载（环境变量优先）；`.env` 不纳入版本控制，密钥只放在本地。本地 llama.cpp 小模型接入见同一文档。

面向小组合作的 Vue 3 + FastAPI 应用。以 [byrdocs/bupt-survival-guide](https://github.com/byrdocs/bupt-survival-guide) 为唯一资料源，将 BGE 向量检索、中文 BM25、NetworkX 图查询与原文证据结合。

前端位于 `bupt-graphrag-frontend/`，默认调用真实后端，包含问答、路径、原文、知识库与检索对比页面。构建后由 FastAPI 直接提供页面，浏览器只需访问一个地址。完整接口见 [OpenAPI](docs/openapi.json)，联调方式见 [全栈运行说明](docs/integration.md)。

**成员接手请先看 [下一步任务与交接清单](docs/NEXT_STEPS.md)。当前为可运行初版，课程验收尚未全部完成；知识抽取覆盖、量化小模型实际运行和正式人工评测是下一阶段重点。**

## 原始项目资料

- [课程要求](课程要求.md)：课程任务、技术约束与验收要求。
- [参考建议](参考建议.md)：前期收到的技术建议，供方案讨论参考。
- [总体设计与接口约定](北邮生活指南_GraphRAG_总体设计与接口约定.md)：小组原始设计、技术方案和接口约定。

以上资料保留原文；设计目标不代表已全部实现。当前实现与剩余工作见 [下一步任务与交接清单](docs/NEXT_STEPS.md)，实际接口定义见 [OpenAPI](docs/openapi.json)。

## 已实现

- 六组 `/api/v1` 接口，统一错误体、参数校验、CORS、可选同步管理密钥。
- 固定 commit 同步 39 篇 Markdown/MDX，保留原文件、标题、行号及历史版本。
- `bge-small-zh-v1.5` CPU 编码、余弦检索；中文分词 BM25；双路 Top10、RRF `1/(60+rank)`。
- 五类实体、四类关系；28 条经过原文核对的初始事实规则与校园俗称词表。
- 正向、逆向、两跳、三跳、双分支交集；每条边必须有证据；50 路径/1000 边展开上限。
- `answered / partial / abstained / needs_clarification` 四类业务状态。
- 校区与实体澄清、实时信息拒答、已审核冲突隔离、原文摘录式回答。
- SQLite 原子发布与持久化、文档内容哈希、片段向量复用、失败回滚、旧事实撤回、重启恢复。
- CLI 人工审核，以及可选 llama.cpp 小模型候选抽取。模型候选不会自动入图。
- 72 道带固定版本原文标注的题库、两种检索模式的评测脚本、自动化工程测试、GitHub Actions。

## 快速启动（Windows / PowerShell）

推荐 Python 3.11；最低 3.11。前端需要 Node.js >=22.12。以下命令在仓库根目录运行。

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"

# 首次需下载 BGE 模型和指南；默认同步设计指定的固定提交。
.venv/Scripts/python.exe -m bupt_rag.cli sync

# 构建真实接口模式的前端，无需在线大模型 API Key。
npm --prefix bupt-graphrag-frontend ci
npm --prefix bupt-graphrag-frontend run build

# 只启动一个 worker；前台终端按 Ctrl+C 停止。
.venv/Scripts/python.exe -m uvicorn bupt_rag.api:app --host 127.0.0.1 --port 8000 --workers 1
```

没有 uv 时可使用 `python -m venv .venv`，随后 `.venv/Scripts/python.exe -m pip install -e ".[dev]"`。Linux/macOS 对应解释器路径为 `.venv/bin/python`。

打开 [完整应用](http://127.0.0.1:8000)，接口文档在 [Swagger UI](http://127.0.0.1:8000/docs)。Windows 也可运行 `powershell -ExecutionPolicy Bypass -File scripts/start.ps1`，自动安装并构建前端后启动服务；已有构建可加 `-SkipBuild`。首次知识导入需先执行同步命令，或在页面“知识库”中检查更新。

如果网络需要代理，在当前终端设置自己的 `HTTP_PROXY/HTTPS_PROXY`；不要提交代理凭据。模型下载完毕可设置 `$env:HF_HUB_OFFLINE='1'`，避免离线问答期间访问 Hugging Face。上游指南同步仍需要网络。

本地缓存完整时优先离线加载模型。Windows 遇到 Hugging Face 符号链接权限错误，可以用 `scripts/download_model.py` 下载到普通目录，再通过 `BUPT_EMBEDDING_MODEL` 指向该目录；更换模型路径后需要重新同步索引。

## 提问与同步

```powershell
$body = @{
  question = '雁南一站式多功能厅的预约平台还能办理哪些手续？'
  campus = 'shahe'
  mode = 'hybrid'
  entity_bindings = @{}
} | ConvertTo-Json

Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/qa' -Method Post `
  -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

这道题可以返回“多功能厅 → 预约服务 → 网上服务大厅 ← 学生证补办申请”的三跳路径，证据来自两篇文档。它不表示去多功能厅补办学生证。

HTTP 同步默认 `main`，CLI 同步默认复现固定提交 `417fc690834fbc4406f48e503f5ef1f832d495db`：

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/knowledge/sync' -Method Post `
  -ContentType 'application/json' -Body '{"ref":"main"}'
```

同一提交与配置重复同步不会增加版本。同步失败时旧知识仍可用于问答。同步时所有业务请求按锁串行等待，因此首次导入期间前端应显示“处理中”，不要设置过短超时。

## 配置与部署

配置通过环境变量读取，[.env.example](.env.example) 只是示例，自动加载仓库根目录 .env（环境变量优先）。

| 变量 | 默认值 / 用途 |
|---|---|
| `BUPT_DATA_DIR` | `data`，SQLite、审核记录和进程锁 |
| `BUPT_FRONTEND_DIST` | 默认仓库内 `bupt-graphrag-frontend/dist`，可指定其他构建目录 |
| `BUPT_EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5`，也支持本地模型目录 |
| `BUPT_EMBEDDING_REVISION` | 已固定的 Hugging Face commit |
| `BUPT_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `BUPT_ADMIN_KEY` | 非空时同步接口要求 `X-Admin-Key` |
| `BUPT_LLM_BASE_URL` | 可选本地 llama.cpp 地址，例如 `http://127.0.0.1:8080/v1` |
| `BUPT_LLM_MODEL` | `qwen3.8-27b` |

默认绑定回环地址。小组局域网联调时可改为 `--host 0.0.0.0`，同时设置管理密钥和允许的前端来源。本项目是本地课程后端，尚无用户系统、配额或公网部署网关。

API、CLI、评测不能同时占用同一数据目录：进程文件锁会拒绝第二个实例。请停服后执行本地管理命令，或通过正在运行的 HTTP 接口操作。不要使用多个 worker。

## 事实维护与本地小模型

自动同步会提取可能含关系的段落作为待审核候选；只把匹配“已核对完整段落 + 标题”的事实发布到图。新增或修改段落不会因为包含两个实体就自动产生关系。

```powershell
# 停服后导出候选
.venv/Scripts/python.exe -m bupt_rag.cli pending --output data/pending.json

# 可选：本机启动 Qwen2.5-1.5B-Instruct Q4_K_M 的 llama.cpp 服务后
$env:BUPT_LLM_BASE_URL='http://127.0.0.1:8080/v1'
.venv/Scripts/python.exe -m bupt_rag.cli suggest CANDIDATE_ID --output data/draft.json

# 人工核对并编辑 FactRule JSON 数组，然后导入
.venv/Scripts/python.exe -m bupt_rag.cli approve data/reviewed.json
.venv/Scripts/python.exe -m bupt_rag.cli sync
```

审核格式、冲突标记和安全边界见 [事实审核](docs/review.md)。LLM 仅帮助生成候选；稳定回答采用可验证的模板与原文摘录，不依赖生成模型润色。未运行本地 Qwen 的性能测试。

## 测试、评测与协作

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check bupt_rag tests scripts
.venv/Scripts/python.exe scripts/export_openapi.py
npm --prefix bupt-graphrag-frontend test
npm --prefix bupt-graphrag-frontend run build

# 停服，且知识库使用题库指定快照
.venv/Scripts/python.exe scripts/evaluate.py --output evaluation/results.json
```

[题库](evaluation/questions.json) 包含 18 道图查询、34 道文本题、8 道澄清题、6 道实时拒答题和 6 道其他不可回答题。人工答案正确性默认空白；关键词自动检查只是代理指标。完整必要证据覆盖率对两种模式使用同一口径，图路径完整性另外记录。真实矛盾没有被编造成指南题，冲突处理通过独立回归测试验证。

参考 [评测说明](evaluation/README.md)、[架构说明](docs/architecture.md)、[合作约定](CONTRIBUTING.md) 和 [验证记录](docs/validation.md)。依赖的本机已测精确版本保存在 `requirements-tested.txt`；跨平台安装优先使用 `pyproject.toml`。

## 当前边界

图查询仅覆盖预设关系模板和已核对/人工审核的事实，不能把全部 39 篇文章自动转成可靠图谱。初次同步产生的待审核候选可由负责知识整理的同学继续处理。更复杂的自由形式多跳问题会拒答。

文本题提供原文摘录；相关度、答案字段检查与范围过滤是保守启发式，仍需人工评估。跨校区对比、实时查询、图片识别、外链正文和自动语义冲突发现未实现；已人工标记的冲突不会进入确定答案。实体消歧使用规范名称、别名、校区及用户绑定。

SQLite 会保留历史正文和版本，长期运行后需要另行设计清理策略。Embedding 已固定具体版本；本地目录模型内容改变时也应修改 `BUPT_EMBEDDING_REVISION` 以重建缓存。

## 来源与许可

代码与指南内容分开授权：应用代码使用 [MIT](LICENSE)，来源引文、事实资源、题库和前端演示快照中的指南衍生部分遵循 **CC BY-NC-SA 4.0**，署名归 byrdocs/bupt-survival-guide 贡献者。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与上游许可证副本。模型权重、数据库及交接压缩包不随代码提交；原始项目资料已收录，见上方入口。前端的固定版本演示快照保留在源码中，仅显式启用 demo 时使用。

?????????? [?????](docs/knowledge-coverage.csv)?[??????](docs/knowledge-review.json) ? [??????](docs/reproduction.md)?

2026-10-28补充：全量39篇AI辅助覆盖记录、33条共享事实扩充、干净环境复现已完成，见 docs/knowledge-coverage.csv、docs/knowledge-review.json、docs/reproduction.md。团队人工签审与另一位成员复现仍待完成；限额演示API密钥按所有者明确授权纳入 .env。
