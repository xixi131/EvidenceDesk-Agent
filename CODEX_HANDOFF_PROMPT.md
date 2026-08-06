# EvidenceDesk Agent 新对话交接提示词

请把本地项目文件和学习状态文件作为真实来源，不要只依赖聊天历史。

项目根目录：

```text
/Users/tangxitao/code/Project/Agent-Engineering/EvidenceDesk-Agent
```

学习状态目录：

```text
/Users/tangxitao/学习/Agent开发/持续学习
```

## 一、项目身份

```text
EvidenceDesk Agent
可评测的企业技术支持与工单协同 Agent
```

第一版统一产品语境已经冻结为：

```text
GitHub Actions 技术支持与工作流运行协同
```

本项目不是 GitHub 官方产品。

## 二、当前真实状态

已完成：

- 工程设计文档；
- 第一版业务语境、Tool、数据源和 RAG Baseline 冻结；
- ADR-001；
- 33 篇 GitHub Actions 官方页面本地快照；
- 29 篇中文 Baseline 与 4 篇英文参考文档隔离选择；
- 数据画像、Baseline Manifest、清洗规则和 ADR-002；
- 数据 manifest、许可和下载脚本。

尚未完成：

- Git 初始化；
- uv/pyproject；
- `src/`、`tests/`；
- FastAPI、数据库、RAG、Agent 和部署代码。

当前第一未完成步骤是 `docs/07-分阶段开发计划.md` 中的 `P0A-04｜建立最小 FastAPI 应用`，不再回到原来的跨领域示例或重新选择数据源，除非出现明确证据并新增 ADR。

## 三、必须先读

1. `AGENTS.md`
2. `PROJECT_NAME.md`
3. `README.md`
4. `docs/00-项目说明与业务边界.md`
5. `docs/01-技术选型与决策理由.md`
6. `docs/02-系统架构与模块边界.md`
7. `docs/03-RAG数据处理与分块策略.md`
8. `docs/04-Agent工作流与状态设计.md`
9. `docs/05-接口与数据模型设计.md`
10. `docs/06-评测与调优闭环.md`
11. `docs/07-分阶段开发计划.md`
12. `docs/08-工程规范与问题排查.md`
13. `docs/09-AI与用户分工及双模式协作规则.md`
14. `docs/10-官方资料与术语.md`
15. `docs/11-第一版冻结范围与数据集.md`
16. `docs/12-语料审阅与清洗规则.md`
17. `docs/decisions/001-冻结GitHub-Actions业务语境与数据基线.md`
18. `docs/decisions/002-冻结中文Baseline语料范围与清洗边界.md`
19. `data/knowledge_base/github_actions_zh_v1/manifest.json`
20. `data/knowledge_base/github_actions_zh_v1/baseline_manifest.json`

学习状态按需读取：

```text
/Users/tangxitao/学习/Agent开发/持续学习/学习进度.md
/Users/tangxitao/学习/Agent开发/持续学习/当前任务.md
```

## 四、已冻结内容

### 数据

```text
dataset_version=github-actions-zh-2026-08-05-v1
source_document_count=33
baseline_included=29
baseline_excluded=4
format=rendered Markdown
language_profiles=chinese_dominant/mixed_technical/english_dominant
license=CC-BY-4.0
source_commit=d19b6951e376efb7bd26fd1c0369158d1641d139
```

本地目录：

```text
data/knowledge_base/github_actions_zh_v1
```

### RAG Baseline

```text
structure-aware + recursive splitting
chunk_size=600 characters
chunk_overlap=80 characters
BAAI/bge-small-zh-v1.5
Dense Retrieval
top_k=5
query_rewrite=false
reranker=null
```

首次检索必须使用 original_query；只有证据不足且未超过上限时才允许一次 Query Rewrite。

### Tool

```text
只读：get_workflow_run、list_workflow_jobs
API：api.github.com，X-GitHub-Api-Version=2026-03-10
只读 Smoke：github/docs run_id=30964320373
本地写：create_support_ticket
高风险外部写：cancel_workflow_run、rerun_failed_jobs
```

高风险 Tool 必须 interrupt、冻结参数、人工审批、幂等、审计，并且只在专用演示仓库真实验收。

### 评测单位

```text
Retriever 返回 Chunk
Ground Truth 使用 Parent Document
Top-K 返回 Chunk；命中按唯一 relevant Parent Document 计数，Precision@K 分母仍为 K
Citation 保留 Chunk + Parent Document + source_url
```

## 五、学习与协作边界

协作和学习的唯一详细规则见：

```text
docs/09-AI与用户分工及双模式协作规则.md
```

每个任务必须明确使用“指导实战模式”或“实现教学模式”。无论谁写代码，关键 Agent/RAG 能力都必须完成设计解释、真实验证、教学复盘和用户小练习。不要把 AI 写好的代码或文档登记成用户已经掌握。

## 六、当前下一步

阶段 0 按 `docs/07-分阶段开发计划.md` 的 Task ID 顺序执行。当前只完成 `P0A-04`：

```text
添加FastAPI和Uvicorn
→ 建立evidence_desk.main应用入口
→ 实现/health和/api/v1/version
→ 验证Swagger /docs
→ 添加API测试
```

不要在同一个任务中同时实现 RAG、LangGraph、数据库和部署。
