# EvidenceDesk Agent

> 可评测的企业技术支持与工单协同 Agent

当前状态：**Git、uv、代码质量和测试入口已完成；下一任务是P0A-04建立最小FastAPI应用和Swagger。**

## 在新 Codex 对话中接手

建议直接用 Codex 打开本目录：

```text
/Users/tangxitao/code/Project/Agent-Engineering/EvidenceDesk-Agent
```

然后发送：

```text
请先阅读根目录 AGENTS.md、CODEX_HANDOFF_PROMPT.md、README.md 和 docs 下的设计文档，并严格按照 AGENTS.md 的“新对话首次响应”流程接手。第一轮只做只读理解与决策审计，不要直接初始化或生成全部项目代码。
```

完整交接内容见：[CODEX_HANDOFF_PROMPT.md](CODEX_HANDOFF_PROMPT.md)。

这不是一份为了快速堆出 Demo 的项目，而是一项工程化练习。核心目标不是“用了多少 AI 框架”，而是训练以下能力：

```text
理解真实问题
→ 划分业务边界
→ 选择技术并说明理由
→ 设计模块与数据流
→ 建立 Baseline
→ 用评测发现问题
→ 根据失败案例调优
→ 加入测试、日志、数据库和部署
→ 对结果负责
```

## 项目要解决什么

企业技术支持通常同时面对三类请求：

1. **知识问题**：Workflow Syntax、调试日志、缓存、权限、Secret 和 Runner 排查；
2. **业务操作**：查询 GitHub Actions Workflow Run/Job 状态、创建支持工单；
3. **高风险或证据不足问题**：取消工作流、重新运行失败 Job、知识库没有答案。

EvidenceDesk Agent 会根据问题类型进入不同流程：

```text
知识问题 → RAG 检索 → 证据判断 → 带引用回答
实时工作流问题 → 调用 GitHub REST Tool → 根据真实结果回答
信息不足 → 询问用户补充信息
取消/重跑操作 → 暂停并等待人工确认
无法解决 → 创建工单并转人工
```

## 为什么要做这个项目

它可以同时练习：

- FastAPI 工程分层与 API 设计；
- LangGraph State、Node、Edge、循环与持久化；
- LangChain 模型、Embedding、Tool 和 Retriever 组件；
- 文档解析、分块、Embedding、向量库和混合检索；
- PostgreSQL、SQLAlchemy、Alembic；
- Recall、Precision、MRR、Faithfulness 等评测；
- top_k、Chunk、Query Rewrite、Embedding、Hybrid、Reranker 调优；
- 日志、异常、测试、Docker Compose 和 CI；
- 在 AI 辅助下仍然保留自己的设计判断和问题定位能力。

## 文档阅读顺序

| 顺序 | 文档 | 解决的问题 |
|---:|---|---|
| 1 | [PROJECT_NAME.md](PROJECT_NAME.md) | 项目叫什么，为什么这样命名 |
| 2 | [docs/00-项目说明与业务边界.md](docs/00-项目说明与业务边界.md) | 项目到底做什么，不做什么 |
| 3 | [docs/01-技术选型与决策理由.md](docs/01-技术选型与决策理由.md) | 为什么选这些技术，而不是其他方案 |
| 4 | [docs/02-系统架构与模块边界.md](docs/02-系统架构与模块边界.md) | 系统怎么分层，模块如何协作 |
| 5 | [docs/03-RAG数据处理与分块策略.md](docs/03-RAG数据处理与分块策略.md) | 文档怎么导入、怎么切、为什么这样切 |
| 6 | [docs/04-Agent工作流与状态设计.md](docs/04-Agent工作流与状态设计.md) | Agent State、Node、路由、Tool 怎么设计 |
| 7 | [docs/05-接口与数据模型设计.md](docs/05-接口与数据模型设计.md) | API、数据库表和向量结构怎么设计 |
| 8 | [docs/06-评测与调优闭环.md](docs/06-评测与调优闭环.md) | 如何知道系统好不好，如何优化 |
| 9 | [docs/07-分阶段开发计划.md](docs/07-分阶段开发计划.md) | 项目主执行路线图：当前检查点、Task ID、依赖、文件范围、验证和阶段门禁 |
| 10 | [docs/08-工程规范与问题排查.md](docs/08-工程规范与问题排查.md) | 测试、日志、配置、部署和排错怎么做 |
| 11 | [docs/09-AI与用户分工及双模式协作规则.md](docs/09-AI与用户分工及双模式协作规则.md) | AI 与用户如何分工、两种开发模式、关键学习内容和教学验收 |
| 12 | [docs/10-官方资料与术语.md](docs/10-官方资料与术语.md) | 官方文档入口和中英文术语 |
| 13 | [docs/11-第一版冻结范围与数据集.md](docs/11-第一版冻结范围与数据集.md) | 已冻结的 GitHub Actions 业务语境、数据集、Tool 和 Baseline |
| 14 | [docs/12-语料审阅与清洗规则.md](docs/12-语料审阅与清洗规则.md) | 33 篇 Source、29 篇中文 Baseline、风险画像和 Cleaner 边界 |

## 已冻结的第一版业务语境

```text
GitHub Actions 技术支持与工作流运行协同
```

- Source Dataset：33 篇 GitHub Actions 官方页面快照；
- 中文 Baseline：29 篇，4 篇英文参考文档留作多语言实验；
- 数据集版本：`github-actions-zh-2026-08-05-v1`；
- 只读 Tool：查询 Workflow Run 和 Job；
- 本地 Tool：创建支持工单；
- 高风险 Tool：取消工作流、重新运行失败 Job，必须人工审批；
- 数据与许可：见 `data/knowledge_base/github_actions_zh_v1/`；
- 完整冻结说明：见 `docs/11-第一版冻结范围与数据集.md`、`docs/12-语料审阅与清洗规则.md`、ADR-001 和 ADR-002。

## 已冻结的第一版原则

1. 后端项目，不开发正式前端；
2. 采用模块化单体，不拆微服务；
3. FastAPI 是对外服务入口，LangGraph 是内部编排引擎；
4. 先做可预测的 RAG Baseline，再加入 Agent 路由；
5. 先实现自己的 Recall/Precision 评测，再接入平台；
6. 第一版只做一条完整闭环，不做多 Agent；
7. 所有优化必须通过固定评测集证明；
8. 所有技术决策都要回答“解决了什么问题、付出了什么代价”。

## 项目完成的最低标准

- 能导入真实且允许公开的技术文档；
- 能通过 RAG 返回带来源的回答；
- 没有证据时不会编造；
- 能调用至少一个只读 Tool 和一个工单 Tool；
- 高风险操作能进入人工审核；
- 有固定评测集和 Baseline；
- 至少完成三组可复现调优实验；
- 有 PostgreSQL 持久化和数据库迁移；
- 有单元测试、集成测试和评测回归；
- Docker Compose 可一键启动；
- README 中展示真实指标、失败案例和限制；
- 自己能够解释关键设计与代码。
