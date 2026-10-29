# 模型接入记录

2026-10-28：按项目委托要求使用阿里云百炼 `qwen3.8-27b`。
Base URL 为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
依据：[百炼 OpenAI 兼容文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)。文档说明原域名仍可使用，业务空间专属域名需填写真实 WorkspaceId。

已真实调用 chat/completions，HTTP 200，输入 `Return only the JSON array []`，输出 `[]`。
这仅证明认证和指定模型调用成功，不是正式评测，也不是本地量化小模型运行证明。
云端权重版本、量化规格和硬件由服务商管理，本项目无法固定其文件校验值。
本地 1.5B GGUF 量化模型已于 2026-10-29 实际部署，见下文“本地量化小模型”。

复制 `.env.example` 为 `.env`，配置 `BUPT_LLM_BASE_URL`、`BUPT_LLM_MODEL`、`BUPT_LLM_API_KEY`。
仓库根目录 `.env` 自动加载，已有环境变量优先。密钥仅用于后端请求，不导出到草稿、日志或前端。
本地 llama.cpp 仍可使用 HTTP 回环地址和其实际模型名，无需密钥。

模型只生成待审候选；请求超时或无效 JSON 记录为 error，已有图谱可继续离线查询。
批量请求不会自动重试错误，使用 `extract --model --retry-errors` 显式恢复。
源文件、标题、完整引文由程序绑定，模型不能替换来源。关系类型、方向、跨校区类型约束经过校验；否定、条件、适用阶段仍需逐条审核。

2026-10-28补充：全量39篇AI辅助覆盖记录、33条共享事实扩充、干净环境复现已完成，见 docs/knowledge-coverage.csv、docs/knowledge-review.json、docs/reproduction.md。团队人工签审与另一位成员复现仍待完成。

合并说明：主分支不跟踪 `.env`，运行时密钥通过本地环境变量或被 Git 忽略的 `.env` 配置。成员分支历史曾包含密钥，需要由密钥所有者在百炼撤销或轮换；从当前版本删除文件不会清除历史泄露。

## 本地量化小模型（llama.cpp）

2026-10-29：已在本机实际部署并运行，满足课程 1.5B～3B GGUF 量化模型条件。

| 项 | 值 |
| --- | --- |
| 模型 | Qwen2.5-1.5B-Instruct，Q4_K_M（官方 `Qwen/Qwen2.5-1.5B-Instruct-GGUF`） |
| 文件 | `models/qwen2.5-1.5b-instruct-q4_k_m.gguf`，1,117,320,736 字节 |
| SHA256 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`（与 Hugging Face LFS 记录一致） |
| 推理引擎 | llama.cpp `b11977`，`llama-b11977-bin-win-vulkan-x64.zip`（Vulkan 后端，无需 CUDA 运行库） |
| 硬件 | Windows 11，NVIDIA RTX 4070 Laptop 8GB，全部层卸载到 GPU（`-ngl 99`） |
| 上下文 | `-c 8192`（4 个并发槽位共享） |
| 速度 | 约 1.3 秒/段（30 段 38 秒，含 few-shot 提示） |

`models/` 已加入 `.gitignore`，模型与可执行文件不入库。复现：

```powershell
# 下载上述两个文件到 models/ 与 models/llama-b11977/，先核对 SHA256
models/llama-b11977/llama-server.exe -m models/qwen2.5-1.5b-instruct-q4_k_m.gguf -c 8192 -ngl 99 --host 127.0.0.1 --port 8080 --alias qwen2.5-1.5b-instruct
$env:BUPT_LLM_BASE_URL='http://127.0.0.1:8080/v1'
$env:BUPT_LLM_MODEL='qwen2.5-1.5b-instruct'
$env:BUPT_LLM_API_KEY=''
.venv/Scripts/python.exe -m bupt_rag.cli sync   # 旧快照先迁移到当前格式（候选带 source_commit、campus）
.venv/Scripts/python.exe -m bupt_rag.cli extract --model --limit 20
```

`extract --model` 只对规则没有产出的段落调用模型。

针对小模型的处理（`bupt_rag/llm.py`）：

- 简短系统指令 + 3 组合成 few-shot（正例、否定句返回空、“或”条件整体保留），只发送标题、原文和校区。
- 回环地址的模型请求附带 `response_format: json_schema`，llama.cpp 据此生成语法约束，输出必为 `{"facts": [...]}`；远程服务不发送该参数。
- 兼容 ```json 代码块、裸数组和单个对象。超时、无法解析或结构错误记为 error，可用 `--retry-errors` 重试。
- 单个条目不合格时只丢弃该条：关系方向或类型不合法；两端名称都不在原文中（臆造）；主客体相同；名称以“位于/需要/通过”等提示词开头（整句照抄）；同一主体的第二个 LOCATED_IN（把一句话拆成多个“位置”）；类型为 Platform 却既不像平台名也未在原文中以「」标出。全部条目被丢弃时返回空结果而非 error——温度为 0，重试只会得到相同输出。
- 输出仍只是待审核草稿，不会自动入图。

### 实测结果（真实指南 30 段等距抽样，人工粗判）

| 版本 | 草稿 | 可用（约） | error | 典型错误 |
| --- | --- | --- | --- | --- |
| 仅格式与臆造校验 | 33 | 10 | 7 | 一句话拆出 6 条 LOCATED_IN；“门禁卡/电脑”当平台；自环；主体类型错导致整段 error |
| 加上述过滤 | 16 | 11 | 0 | 把“需参考具体文件”当条件；“考核项目为……”这类描述当条件 |

结论：1.5B 模型能补到规则漏掉的位置/提供关系（如“外卖柜→鸿雁路最西段路南”“北邮人团队→Overleaf 实例→北邮教育邮箱或校友邮箱”），但 REQUIRES 条件的精度仍低，必须人工审核。若课程允许，可换 Qwen2.5-3B-Instruct Q4_K_M（约 2GB）比较；代码无需修改。

## AI 回答模型

问答的“AI 总结”使用单独的 `BUPT_ANSWER_*` 配置，抽取仍可保持本地小模型。实现见 `bupt_rag/generation.py`：

- 只发送问题、校区、关系图已确认的结论和本次证据（编号 [1]…[n]），温度 0。
- 校验：每句（列表引导句除外）必须带 [n] 且编号有效；句中数字必须出现在该句引用的原文中；总长不超过 800 字。不通过则不返回 AI 总结，前端照常显示原文摘录。
- 远程请求跟随系统代理（`HTTPS_PROXY`）；本地 llama.cpp 直连。

2026-10-29 实测（百炼 `qwen3.8-27b`，开发集前 20 道可回答题）：19/20 通过校验（放宽列表引导句后为 20/20），模型耗时约 2.5 秒/题；人工通读未发现原文之外的内容。本地 1.5B 作为回答模型尚未系统测试。
