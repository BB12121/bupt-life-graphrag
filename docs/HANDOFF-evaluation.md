# 测评交接（T6 正式评测 / T7 资源测试）

更新日期：2026-10-29。本文件给接手测评的成员：后端现在做到了什么、怎么在自己机器上跑起来、测评时要注意什么。任务验收标准仍以 [NEXT_STEPS.md](NEXT_STEPS.md) 的 T6、T7 为准。

## 1. 后端现状（交接时）

| 模块 | 状态 | 说明 |
|---|---|---|
| 检索 | 完成 | BGE-small-zh-v1.5 向量 + jieba BM25，RRF 融合；`vector` 模式只用向量 |
| 图查询（T4） | 完成 | 12 个查询模板（`bupt_rag/qa.py` 的 `TEMPLATES`），支持一/二/三跳、逆向、双分支交集 |
| 增量更新（T5） | 完成 | 只重做受影响文档；规则变化只重抽对应文档；索引按文档增量维护，测试保证与全量重建一致 |
| 本地小模型（T1） | 完成 | Qwen2.5-1.5B-Instruct Q4_K_M + llama.cpp，已在 RTX 4070 实测，见 [model-runtime.md](model-runtime.md) |
| 候选抽取（T2） | 能产出草稿 | 规则逐句抽取 + 小模型补充；**草稿尚未人工审核入图**，图谱规模暂未因此扩大 |
| 工程测试 | 通过 | 后端 103 项 `pytest` 通过；前端 Playwright 端到端测试本轮未重跑 |

回归核对：重构后用真实 BGE 跑 72 道开发集（hybrid、vector 两种模式），逐题状态、原因码和答案文本与 [reference-run.json](../evaluation/reference-run.json) 完全一致。这只说明重构没有改变行为，**不是准确率评测**。

唯一可见变化：图遍历现按（关系、目标实体）排序，同一问题有多条路径时返回顺序可能与旧结果不同，路径集合不变。

## 2. 准备环境

按 [README](../README.md) 的“快速启动”安装依赖、同步、构建前端。测评相关的额外要点：

1. **数据目录锁**：API、CLI、评测脚本不能同时使用同一个数据目录。要么先停 API，要么复制一份数据目录给评测用：
   ```powershell
   Copy-Item -Recurse data D:\eval-data
   $env:BUPT_DATA_DIR='D:\eval-data'
   ```
2. **固定资料快照**：CLI `sync` 默认同步固定提交 `417fc690834fbc4406f48e503f5ef1f832d495db`，题库也基于这个提交。不要用 `ref=main` 的数据做正式评测。
3. **旧快照迁移**：用旧版本代码生成的数据目录，第一次需要执行一次 `sync`，会全量重新解析 39 篇（约 30 秒），之后的同步才是增量的。
4. **离线运行**：BGE 下载完成后设置 `$env:HF_HUB_OFFLINE='1'`，避免评测期间访问 Hugging Face。

## 3. 跑开发集评测

```powershell
.venv/Scripts/python.exe -m bupt_rag.cli sync
.venv/Scripts/python.exe scripts/evaluate.py --output evaluation/results.json
```

- 输出包含两种模式的逐题响应、状态、证据、图路径、延迟、内存采样；`evaluation/results*.json` 被 git 忽略。
- 指标口径见 [evaluation/README.md](../evaluation/README.md)。关键词检查只是代理指标；`human_answer_accuracy` 仍为 null，需要测评同学人工判分。
- 72 题是**开发/回归集**，开发时用来调过逻辑；正式验收请另备独立题目（NEXT_STEPS T6 第一条）。

## 4. 本地小模型（T7 资源测试需要）

模型和可执行文件不入库（`models/` 被 git 忽略），需自行下载并核对校验值：

| 文件 | 来源 | 校验 |
|---|---|---|
| `models/qwen2.5-1.5b-instruct-q4_k_m.gguf` | Hugging Face `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | SHA256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| `models/llama-b11977/`（解压） | GitHub `ggml-org/llama.cpp` release `b11977`，`llama-b11977-bin-win-vulkan-x64.zip` | 记录版本号即可 |

```powershell
models/llama-b11977/llama-server.exe -m models/qwen2.5-1.5b-instruct-q4_k_m.gguf -c 8192 -ngl 99 --host 127.0.0.1 --port 8080 --alias qwen2.5-1.5b-instruct
$env:BUPT_LLM_BASE_URL='http://127.0.0.1:8080/v1'
$env:BUPT_LLM_MODEL='qwen2.5-1.5b-instruct'
.venv/Scripts/python.exe -m bupt_rag.cli extract --model --limit 20
```

- 没有独立显卡时去掉 `-ngl 99`，改用 CPU；速度会明显变慢，属于 T7 要记录的内容。
- 已有实测（RTX 4070 Laptop 8GB，Vulkan）：约 1.3 秒/段；30 段抽样中过滤后草稿约 2/3 可用。内存、冷启动、首次入库等指标**尚未测量**，是 T7 的工作。
- **问答不调用小模型**：小模型只用于离线抽取候选草稿。测问答延迟时不需要启动 llama-server；测“包含小模型的完整流程”时才需要。

可选远程模型（百炼 `qwen3.8-27b`）的配置见 [model-runtime.md](model-runtime.md)。它不是课程要求的本地量化模型，只能作补充或对照，例如给小模型抽取结果做参考答案。

## 5. 测评时请注意

- **图谱覆盖有限**：图查询只基于已审核事实（约 61 条关系，16 篇来源）。图题失败可能是知识没入图，而不是查询逻辑问题，判分时请区分。
- **拒答是设计行为**：实时信息（如“今天开门吗”）、图片内容、超出模板的复杂多跳会拒答或要求澄清，计入拒答率而非错误。
- **冲突题**：固定指南中没有确认的真实矛盾；冲突处理只在合成测试 `tests/test_integrity.py` 中验证，报告中需注明。
- **两种模式对比**：两种模式的回答策略相同（原文摘录式），只改变检索方式。

## 6. 尚未完成（不属于本次后端范围）

- T2/T3：草稿的人工审核与入图（`cli drafts` → 审核 → `cli review` / `approve`，见 [review.md](review.md)、[demo.md](demo.md)）。
- T6：独立验收题、人工判分、评测报告（建议 `docs/evaluation-report.md`）。
- T7：目标硬件资源测试（建议 `docs/resource-report.md`）。
- T8：另一位成员从干净克隆复现。

有问题请在仓库提 issue，或在 PR 中 @ 后端负责人。
