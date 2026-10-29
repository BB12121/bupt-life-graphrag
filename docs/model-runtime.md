# 模型接入记录

2026-10-28：按项目委托要求使用阿里云百炼 `qwen3.8-27b`。
Base URL 为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
依据：[百炼 OpenAI 兼容文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)。文档说明原域名仍可使用，业务空间专属域名需填写真实 WorkspaceId。

已真实调用 chat/completions，HTTP 200，输入 `Return only the JSON array []`，输出 `[]`。
这仅证明认证和指定模型调用成功，不是正式评测，也不是本地量化小模型运行证明。
云端权重版本、量化规格和硬件由服务商管理，本项目无法固定其文件校验值。
原 T1 的 1.5B～3B GGUF 课程条件仍需课程负责人确认是否接受替代。

复制 `.env.example` 为 `.env`，配置 `BUPT_LLM_BASE_URL`、`BUPT_LLM_MODEL`、`BUPT_LLM_API_KEY`。
仓库根目录 `.env` 自动加载，已有环境变量优先。密钥仅用于后端请求，不导出到草稿、日志或前端。
本地 llama.cpp 仍可使用 HTTP 回环地址和其实际模型名，无需密钥。

模型只生成待审候选；请求超时或无效 JSON 记录为 error，已有图谱可继续离线查询。
批量请求不会自动重试错误，使用 `extract --model --retry-errors` 显式恢复。
源文件、标题、完整引文由程序绑定，模型不能替换来源。关系类型、方向、跨校区类型约束经过校验；否定、条件、适用阶段仍需逐条审核。

2026-10-28补充：全量39篇AI辅助覆盖记录、33条共享事实扩充、干净环境复现已完成，见 docs/knowledge-coverage.csv、docs/knowledge-review.json、docs/reproduction.md。团队人工签审与另一位成员复现仍待完成。

合并说明：主分支不跟踪 `.env`，运行时密钥通过本地环境变量或被 Git 忽略的 `.env` 配置。成员分支历史曾包含密钥，需要由密钥所有者在百炼撤销或轮换；从当前版本删除文件不会清除历史泄露。
