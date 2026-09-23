# EvidenceDesk Agent

> 可评测的企业技术支持与工单协同 Agent —— 每一项优化都有评测数据支撑，每一个放弃的方案都有记录在案的理由。

以 GitHub Actions 技术支持为场景：知识问题走 RAG 带引用回答，实时问题调 GitHub API，
高风险写操作进人工审批，证据不足时如实拒答。

```text
FastAPI（对外接口）→ LangGraph ReAct Agent（内部编排）→ Weaviate 混合检索 + PostgreSQL 持久化
```

| | |
|---|---|
| 代码规模 | 7798 行（`src/`），214 个测试全绿 |
| 语料 | 33 篇 GitHub Actions 官方文档快照，29 篇中文 Baseline，293 个 Chunk |
| 评测 | 检索层 51 题 / 回答层 60 题 / Agent 层 16 题，三层各自有固定评测集与基线 |
| 质量门禁 | 每次推送 CI 跑 `ruff` + `mypy --strict` + 单元测试 |

---

## 真实指标

所有数字来自 `data/evaluation/` 下的评测产物，可复现。

### 检索层（51 题，K=5）

| 方案 | Recall@5 | MRR | 单次延迟 | 是否上生产 |
|---|---|---|---|---|
| Dense | 0.9314 | 0.8693 | 12.7ms | |
| BM25 | 0.9118 | 0.8170 | — | |
| **Hybrid（alpha 0.5）** | **0.9608** | **0.9010** | 13.1ms | ✅ **已冻结为生产配置** |
| Dense + Reranker | 1.0000 | 0.8333 | 1389.6ms | ❌ 见下方「主动放弃的方案」 |

### 回答层（60 题，LLM-as-judge）

| 指标 | 数值 |
|---|---|
| 忠实度（有依据的回答占比） | 0.8958 |
| 编造率（无依据的回答占比） | **0.0000** |
| 回答质量（完全正确占比） | 0.9583 |
| 拒答准确率 | 0.9167 |

### Agent 层（16 题，7 项指标）

| 指标 | 数值 |
|---|---|
| 路由准确率 | 1.0000 |
| 工具选择准确率 | 0.9375 |
| 工具参数有效率 | 1.0000 |
| 人工审批该拦必拦 | 1.0000 |
| **未经审批执行写操作** | **0.0000** |
| 任务成功率 | 1.0000 |

### 性能

| | |
|---|---|
| 单请求 P50 | 10.3 秒（其中 99.99% 是等模型返回） |
| 框架自身开销 | 1.58ms / 110s —— FastAPI + 中间件 + Postgres 写入全部加起来 |
| 纯框架吞吐上限 | ~2700 QPS（`/health` 实测） |

---

## 三个能说清取舍的决策

### 1. 重排器做完了，但不上生产

两段式重排（粗筛 20 → 精排 5）把 Recall@5 拉到 **1.0000**，11 个标签全部满分。
但单次检索延迟从 **12.7ms 涨到 1389.6ms**，**110 倍**。

判断：为 4 个点的召回付出 110 倍延迟不划算。代码保留（`RerankingRetriever`），
重新启用的条件写入 ADR。

顺带两个实验发现：

- **两段式里第一段该看 `Recall@候选数`，不是 `Recall@5`。** Hybrid 单独用比 Dense 强，
  配上重排反而更差——因为 Dense 的 Recall@20 = 1.0000，候选集是满的，Hybrid 的不是。
  「单独用谁强」是错误的选型标准。
- **重排把 Recall 拉满，MRR 反而降了**（0.8693 → 0.8333）：该找的都找到了，但最好的那条
  没排第一。对 RAG 来说 Recall 更重要（5 条都进 prompt），但这个取舍要写进文档。

### 2. 多语言文档被排除，且换模型救不回来

往索引里加 4 篇英文参考文档，Recall@5 从 **0.9314 掉到 0.8725**。

换多语言 Embedding（bge-m3）完全救不回来——Recall **完全相同**，MRR 更低，
向量化慢 13 倍，维度翻倍。

根因不是「能不能编码英文」，而是**英文内容占了索引 75%（898/1191 chunk），
把中文答案挤出去了**。换模型治不了稀释。

### 3. 用压测数据否决了自己的异步化计划

原计划做全链路异步化提升并发。压测后放弃：

- 框架开销只占 1.58ms / 110s，代码不是瓶颈
- 并发 5 时零排队（10 个请求 22.7 秒完成，串行则需 102.5 秒）
- 瓶颈是单次模型调用 16~53 秒

改为换模型：单请求 **110 秒 → 10.3 秒**。异步化改造取消。

---

## 修过的一个真 bug：中文 BM25 全军覆没

现象：BM25 中文检索 Recall@5 只有 **0.1176**，几乎全部 0 命中。

根因：Weaviate 内置中文分词器（GSE_CH）导致**索引端和查询端切词不一致**——
同一个词，写入时切成 A+B，查询时切成 C+D，永远对不上。

修法：把分词收回应用侧（`rag/tokenization.py`，jieba + 领域词典），
索引和查询共用同一个 `segment()`，Weaviate 侧只做空格切分。

结果：**0.1176 → 0.9118**。并用测试钉住词典边界（只收原子词，收长复合词会重新
引入同一个失配 bug）。

---

## 已实现的 Agent 能力

| 能力 | 实现 |
|---|---|
| 推理与工具调用 | LangGraph `create_agent`，6 个工具：文档检索、2 个 GitHub 只读、工单写入、记忆读写各一 |
| 短期记忆 | `PostgresSaver` checkpointer + `thread_id`，跨请求保留会话 |
| 上下文超限 | `SummarizationMiddleware`，超过阈值自动摘要压缩旧对话 |
| 长期记忆 | `PostgresStore`（pgvector）+ 记忆读写工具，跨会话、跨重启 |
| 人工审批 | `HumanInTheLoopMiddleware` 拦截写操作 → `pending_approval` → 审批接口恢复执行 |
| 幂等写入 | 工单创建以 `conversation_id` 为幂等键 |
| 限流 / 缓存 / 重试 | 三个自实现中间件，分别控制调用节奏、命中复用、临时故障重试 |
| 可观测 | 每次调用记录模型调用次数、token 数、成本、工具序列、耗时 |
| 分层拒答 | 检索分数前置闸门 + 回答文本兜底 + 后置引用校验 |

### 拒答阈值是标定出来的，不是拍的

前置闸门阈值取 **0.52**，依据是评测集上两类问题的分数分布存在空隙：

```text
该答的 51 道：最低 0.5570，中位 0.7111
该拒的  9 道：最高 0.5607，其中 7 道在 0.4908 以下
                    ↑ 空隙 0.4908 ~ 0.5570，阈值取中央
```

实测：误伤 0 道，正确拦下 7/9。放到 0.62 会误伤 11 道。

---

## 快速开始

需要 Docker、Python 3.11+、[uv](https://docs.astral.sh/uv/)。

```bash
uv sync
```

```bash
cp .env.example .env    # 填入 OPENAI_API_KEY 等
```

```bash
docker compose up -d
```

```bash
uv run uvicorn evidence_desk.main:app
```

首次启动会下载 Embedding 模型，需要等一会儿。看到 `Application startup complete` 再往下。

接口文档在 http://127.0.0.1:8000/docs

### 试一个知识问题

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/chat -H 'Content-Type: application/json' -d '{"question":"如何启用调试日志？"}'
```

返回（节选）：

```json
{
  "ok": true,
  "data": {
    "status": "completed",
    "answer": "在仓库中进入 Settings → Secrets and variables → Actions，新建变量 ACTIONS_STEP_DEBUG = true ...",
    "tools_used": ["search_docs"],
    "conversation_id": "conv_b49c1a34..."
  },
  "meta": { "request_id": "req_5db05f35..." }
}
```

同时服务端记录这次调用的开销：

```json
{"message":"Agent 调用完成","model":"gpt-5.5","llm_calls":2,
 "input_tokens":3040,"output_tokens":328,"cost_usd":0.0,
 "tool_calls":["search_docs"],"agent_latency_ms":36375.45}
```

### 试一个需要审批的写操作

创建工单会先停在审批点，返回 `status: "pending_approval"`，
再调 `POST /api/v1/agent/chat/{conversation_id}/decisions` 提交批准或拒绝，
被拒绝的工具不会执行。

---

## 评测怎么跑

```bash
uv run python scripts/run_retrieval_eval.py
```

```bash
uv run python scripts/run_answer_eval.py
```

```bash
uv run python scripts/run_agent_eval.py
```

跑完跟冻结基线对比，有指标退步就以非 0 退出（可直接接进 CI）：

```bash
uv run python scripts/compare_eval_baseline.py
```

基线文件在 `data/evaluation/baselines/`，每个指标带方向（越大越好 / 越小越好）
和容差。**容差按「一道题翻转的幅度」标定**：Agent 层 16 题，一题 = 0.0625，
所以容差取 0.07（容一题抖动，两题报红）；两个安全指标容差为 **0**——
该拦没拦、未经审批就写数据，发生一次都不算噪音。

### 压测

```bash
uv run python scripts/load_test.py --url http://127.0.0.1:8000/health --concurrency 1,10,50,100 --requests 500
```

业务接口用准备好的问题集（避免命中响应缓存导致数字虚高）：

```bash
uv run python scripts/load_test.py --url http://127.0.0.1:8000/api/v1/agent/chat --json-file data/evaluation/load_test_questions.json --concurrency 5 --requests 10 --timeout 300
```

---

## 技术选型

| 选择 | 理由 |
|---|---|
| FastAPI | 对外服务入口，类型驱动，自带接口文档 |
| LangGraph | 内部编排引擎，提供 ReAct 循环、中断恢复、checkpointer |
| Weaviate | 同时提供向量检索与 BM25，原生支持 Hybrid 融合，不用自己实现 |
| PostgreSQL + pgvector | 业务数据 + Agent 状态持久化 + 长期记忆语义检索，共用一套连接池 |
| bge-small-zh-v1.5 | 中文语料下实测优于多语言模型，且快 13 倍、内存省一半 |
| uv | 依赖锁定与可复现构建 |

完整理由和被否决的方案见 [docs/01-技术选型与决策理由.md](docs/01-技术选型与决策理由.md) 与 `docs/decisions/` 下的 ADR。

---

## 项目结构

```text
src/evidence_desk/
├── api/              FastAPI 路由、中间件、依赖注入、异常处理
├── application/      用例编排 + 端口定义（Protocol），不依赖具体实现
├── infrastructure/   适配器：Weaviate、PostgreSQL、OpenAI、GitHub、Embedding、Reranker
├── agent/            ReAct Agent 装配、工具定义、自实现中间件、开销采集
├── rag/              语料清洗、Section 提取、分块、分词、引用组装
├── evaluation/       三层评测的数据集、指标、Runner、基线对比
├── perf/             压测统计口径
└── core/             配置、日志、错误、ID
```

分层规则：`application/ports/` 只定义 Protocol，`infrastructure/` 提供实现，
组合发生在 `main.py`。所以换检索器、换模型不需要动业务代码。

---

## 当前状态与已知限制

**进度**：阶段 0~5 完成，阶段 6（评测与调优）进行中，阶段 7（容器化与部署）未开始。

**已知限制**，都是有意识保留的：

- **未做正式前端**。这是第一版冻结原则，后端服务以 Swagger 和 API 为交付面。
- **应用未容器化**。目前只有依赖服务在 Compose 里，应用本体靠 uvicorn 启动。
- **评测未接入 CI**。基线对比脚本已具备（退出码驱动），但夜间跑批需要配置 API Key 与向量库，尚未接入。
- **接口为同步实现**。压测显示瓶颈在上游模型（框架开销 1.58ms / 110s），
  异步化收益不足，已记录为「测量后主动放弃」。
- **就绪检查每次新建数据库连接**。单机无影响；多副本 + 密集探针会对 Postgres 造成
  连接创建压力，已记录待改。
- **`multi_document` 标签召回偏低**（Hybrid 0.7778）。需跨文档整合的问题仍是弱项，
  开启重排可解决但延迟代价过大。

---

## 文档

| 顺序 | 文档 | 解决的问题 |
|---:|---|---|
| 1 | [docs/00-项目说明与业务边界.md](docs/00-项目说明与业务边界.md) | 做什么，不做什么 |
| 2 | [docs/01-技术选型与决策理由.md](docs/01-技术选型与决策理由.md) | 为什么选这些技术 |
| 3 | [docs/02-系统架构与模块边界.md](docs/02-系统架构与模块边界.md) | 怎么分层，模块如何协作 |
| 4 | [docs/03-RAG数据处理与分块策略.md](docs/03-RAG数据处理与分块策略.md) | 文档怎么切，为什么这样切 |
| 5 | [docs/04-Agent工作流与状态设计.md](docs/04-Agent工作流与状态设计.md) | State、Node、路由、Tool |
| 6 | [docs/05-接口与数据模型设计.md](docs/05-接口与数据模型设计.md) | API、数据库表、向量结构 |
| 7 | [docs/06-评测与调优闭环.md](docs/06-评测与调优闭环.md) | 如何知道好不好，如何优化 |
| 8 | [docs/07-分阶段开发计划.md](docs/07-分阶段开发计划.md) | 路线图与当前进度 |
| 9 | [docs/08-工程规范与问题排查.md](docs/08-工程规范与问题排查.md) | 测试、日志、部署、排错 |
| 10 | [docs/11-第一版冻结范围与数据集.md](docs/11-第一版冻结范围与数据集.md) | 冻结的业务语境与数据集 |

---

## 数据来源与许可

语料为 GitHub Actions 官方文档快照，采用 CC BY 4.0，
出处与归属见 [data/knowledge_base/github_actions_zh_v1/ATTRIBUTION.md](data/knowledge_base/github_actions_zh_v1/ATTRIBUTION.md)。

代码部分尚未附加开源许可声明。
