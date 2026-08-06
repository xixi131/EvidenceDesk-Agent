# EvidenceDesk Agent Workspace Instructions

This repository is a learning-driven engineering project. The user is building the project with AI assistance, but the primary goal is to develop the user's own engineering judgment and problem-solving ability—not to have an AI generate the entire system at once.

## 1. Project identity

Project name:

```text
EvidenceDesk Agent
可评测的企业技术支持与工单协同 Agent
```

Current repository state:

```text
The first-version business context, corpus, tools, and RAG baseline are frozen.
The 33-document GitHub Actions source snapshot is downloaded and profiled locally.
The first Chinese embedding baseline includes 29 documents; 4 English-dominant reference documents are reserved for a later multilingual experiment.
Git, the uv packaged project, and the pytest/Ruff/mypy quality gate are initialized and verified.
FastAPI and application features have not started yet.
The next task is P0A-04 in docs/07: build the minimal FastAPI app, health/version endpoints, and Swagger.
```

## 2. Required reading order

At the beginning of a new project-related task, read these files before proposing code:

1. `PROJECT_NAME.md`
2. `README.md`
3. `docs/00-项目说明与业务边界.md`
4. `docs/01-技术选型与决策理由.md`
5. `docs/02-系统架构与模块边界.md`
6. `docs/03-RAG数据处理与分块策略.md`
7. `docs/04-Agent工作流与状态设计.md`
8. `docs/05-接口与数据模型设计.md`
9. `docs/06-评测与调优闭环.md`
10. `docs/07-分阶段开发计划.md`
11. `docs/08-工程规范与问题排查.md`
12. `docs/09-AI与用户分工及双模式协作规则.md`
13. `docs/10-官方资料与术语.md`
14. `docs/11-第一版冻结范围与数据集.md`
15. `docs/12-语料审阅与清洗规则.md`
16. `docs/decisions/001-冻结GitHub-Actions业务语境与数据基线.md`
17. `docs/decisions/002-冻结中文Baseline语料范围与清洗边界.md`

For the user's durable learning status, also read when relevant:

```text
/Users/tangxitao/学习/Agent开发/持续学习/学习进度.md
/Users/tangxitao/学习/Agent开发/持续学习/当前任务.md
```

Do not rely only on prior chat history to decide what the user has learned.

## 3. Frozen first-version decisions

The accepted first-version product context is:

```text
GitHub Actions technical support and workflow-run collaboration
```

The frozen corpus is:

```text
data/knowledge_base/github_actions_zh_v1
dataset_version=github-actions-zh-2026-08-05-v1
33 rendered Markdown source documents
29 documents included in github-actions-zh-baseline-v1
4 English-dominant reference documents reserved for multilingual evaluation
source=GitHub Docs
license=CC-BY-4.0
```

The frozen initial RAG baseline is:

```text
structure-aware + recursive splitting
chunk_size=600 characters
chunk_overlap=80 characters
BAAI/bge-small-zh-v1.5
Dense Retrieval
top_k=5
no query rewrite
no reranker
```

The frozen tools are:

```text
read: get_workflow_run, list_workflow_jobs
local write: create_support_ticket
high-risk external write: cancel_workflow_run, rerun_failed_jobs
```

High-risk tools require interrupt, frozen parameters, approval, idempotency, audit, and a dedicated disposable demo repository. Do not re-open these decisions without concrete evidence and an ADR.

## 4. Collaboration and learning contract

Before starting any development task, read and follow:

```text
docs/09-AI与用户分工及双模式协作规则.md
```

That document is the single source of truth for:

- Guidance Practice Mode, where the user writes the code after design and explanation;
- Implementation Teaching Mode, where AI writes a scoped implementation and then completes detailed teaching;
- which Agent/RAG capabilities the user must learn;
- what AI may implement directly;
- required task output, teaching closure, exercises, and learning evidence.

Default language is Chinese. Project-owned code comments, docstrings, Swagger/CI display text, and Git commit messages must use Chinese by default; identifiers, protocol fields, stable error codes, and third-party names may remain in English. If the user does not specify a mode, follow the mode-selection rules in that document. Do not duplicate or redefine the collaboration contract in this file.


For concept-teaching tasks, use the `plain-language-teaching` skill when available. Before introducing terminology, first state the direct relationship between the user's existing artifact or knowledge and the code being implemented, for example: `manifest.json documents entry -> SourceDocument(BaseModel)`. Reuse the user's own explanation, correct only inaccuracies, distinguish completed preparation from current implementation, and use real project data before abstractions. If the user says they still do not understand, stop implementation and explain one abstraction level lower before continuing.

## 5. Development task output

All development-task explanations, validation reports, teaching reviews, and user exercises must follow sections 7–9 of:

```text
docs/09-AI与用户分工及双模式协作规则.md
```

Do not provide code without explaining why it is structured that way.

## 6. Engineering principles

- Use a modular monolith for the first version.
- FastAPI is the external service boundary.
- LangGraph is the internal stateful workflow engine.
- LangChain is used as a component/integration library, not as a black-box replacement for workflow design.
- PostgreSQL stores business facts.
- Weaviate stores searchable chunks and vectors.
- LangGraph Checkpointer stores graph state and execution position.
- These three storage responsibilities must remain separate.
- API Router must not directly create PostgreSQL, Weaviate, GitHub, or model clients.
- Application modules orchestrate use cases; Infrastructure modules implement external I/O; `main.py` is the composition root that wires them together.
- Keep the modular monolith shallow: default directory depth is at most one subpackage below a top-level capability, and create Ports only when a Fake or second implementation is actually needed.
- All loops and retries must have explicit upper bounds.
- Side-effecting tools require idempotency and human approval where appropriate.
- Every answer based on RAG must carry traceable citations.
- Insufficient evidence must lead to clarification, refusal, or ticket escalation—not hallucination.

## 7. RAG decision rules

Do not treat chunking as a fixed-size string operation.

For every chunking change, explain:

- document type and structure;
- why the boundary preserves meaning;
- expected effect on Recall/Precision;
- index size and latency cost;
- how the change will be evaluated.

Optimization work must follow:

```text
fixed dataset
→ fixed baseline
→ change one main variable
→ run evaluation
→ inspect failure cases
→ record decision
```

The main experiment order is:

```text
chunk strategy
→ top_k
→ query rewrite
→ BM25/Dense/Hybrid
→ embedding model
→ reranker
```

Do not change all variables at once.

## 8. Evaluation requirements

First implement and understand deterministic metrics:

- Recall@K
- Precision@K
- MRR
- Route Accuracy
- Tool Selection Accuracy
- Tool Argument Valid Rate

Then add answer-level evaluation and LangSmith experiments.

`relevant_doc_ids` must be treated as human-reviewed ground truth. Do not invent positive evaluation results or resume metrics.

For every experiment, record:

```text
experiment_id
dataset_version
git_commit
prompt_version
chunk config
embedding model
retrieval mode
top_k
reranker
per-case results
summary metrics
latency/token/cost
```

## 9. AI assistance and learning boundaries

Follow sections 4–6 and 8–10 of:

```text
docs/09-AI与用户分工及双模式协作规则.md
```

Never generate the full project in one step unless the user explicitly changes the project rule. AI implementation is not evidence that the user has mastered the implemented capability.

## 10. Scope exclusions for the first version

Do not introduce without explicit approval:

- frontend application;
- multi-agent architecture;
- microservices;
- Kubernetes;
- Kafka;
- Redis/Celery;
- full authentication/authorization system;
- complex multi-tenant permissions;
- embedding fine-tuning;
- custom model training;
- large-scale long-term memory.

## 11. Documentation and ADR rules

When a major design decision changes, update the relevant document and create an ADR under:

```text
docs/decisions/
```

Use `docs/decisions/000-ADR模板.md`.

A decision is incomplete unless it records:

- context;
- alternatives;
- chosen option;
- reason;
- cost/risk;
- validation method;
- conditions for reconsideration.

## 12. Evidence and learning status

Use the learning-evidence levels and acceptance rules defined in section 9 of:

```text
docs/09-AI与用户分工及双模式协作规则.md
```

Do not mark the user as having mastered a concept solely because AI prepared code, documents, tests, or an explanation.

## 13. First response in a fresh conversation

When this repository is opened in a fresh Codex conversation, the first response should not immediately generate code.

First:

1. Read the required documents.
2. Summarize the project in your own words.
3. List frozen decisions and unresolved decisions separately.
4. Identify the current first unfinished step.
5. Recommend one small next action with acceptance criteria.
6. Wait for user confirmation before initializing the codebase unless the user explicitly asks to start implementation immediately.
