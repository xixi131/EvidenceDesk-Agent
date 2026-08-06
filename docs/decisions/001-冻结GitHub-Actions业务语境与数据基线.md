# ADR-001｜冻结 GitHub Actions 业务语境与第一批数据基线

- 状态：Accepted；语料纳入范围由 ADR-002 进一步细化
- 日期：2026-08-05
- 决策人：项目所有者

## 背景

EvidenceDesk Agent 已完成通用企业技术支持 Agent 的工程设计，但原文档中的知识库、订单查询和取消订单示例没有落在同一个真实产品语境中，第一批公开数据也没有确定。没有固定业务领域和数据快照，Chunk、Embedding、Tool、Ground Truth 和评测均无法形成可信结论。

## 约束

- 业务约束：必须同时覆盖知识问答、实时只读 Tool、工单升级和高风险人工审核。
- 技术约束：第一版使用模块化单体、FastAPI、LangGraph、Weaviate、PostgreSQL。
- 时间约束：优先形成可运行、可评测的单一闭环，不扩展无关格式和基础设施。
- 数据约束：数据必须真实、公开、可署名、可固定版本，并适合中文 Embedding Baseline。

## 候选方案

### 方案 A：自建虚构 SaaS 文档和订单数据

优点：业务规则完全可控，容易设计 Tool 和审批。

缺点：数据真实性和简历说服力较弱，容易为了命中问题而反向编写文档。

### 方案 B：公开开源软件文档 + 无关订单 Tool

优点：知识文档真实且容易获得。

缺点：技术文档和订单业务割裂，完整流程缺少统一业务解释。

### 方案 C：GitHub Actions 官方中文文档 + GitHub Workflow REST Tool + 本地支持工单

优点：

- 文档真实、公开并有 CC BY 4.0 许可；
- GitHub Actions 具备工作流、Job、Runner、日志、缓存、权限和故障排查等丰富技术支持问题；
- GitHub REST API 同时支持查询、取消和重新运行，天然覆盖只读 Tool 与高风险写 Tool；
- 中文文档与 `bge-small-zh-v1.5` Baseline 匹配；
- 可以使用公开仓库验证读取，用专用演示仓库限制写操作风险。

缺点：

- GitHub Docs 页面和 API 可能更新，必须保存固定快照；
- 写操作需要 Token 和仓库权限；
- 超大工作流语法文档会提高分块难度；
- 本项目不能宣称是 GitHub 官方支持产品。

## 决策

选择方案 C。

第一版产品语境冻结为：

```text
GitHub Actions 技术支持与工作流运行协同
```

第一批 Source Dataset 冻结为 33 篇 GitHub Actions 官方页面快照，数据集版本：

```text
github-actions-zh-2026-08-05-v1
```

来源仓库提交：

```text
d19b6951e376efb7bd26fd1c0369158d1641d139
```

GitHub REST API 版本固定为 `2026-03-10`；公开只读 Smoke Target 使用 `github/docs` 的历史运行 `30964320373`。第一版只验收 Markdown Loader。RAG Baseline 冻结为结构优先 + 递归分块 600/80、`BAAI/bge-small-zh-v1.5`、Dense Retrieval、`top_k=5`、不开 Query Rewrite、不开 Reranker。

## 选择理由

该方案用同一个真实产品连接了：

```text
官方知识文档
→ 工作流运行查询
→ 支持工单
→ 取消/重跑审批
→ 固定评测
```

因此每个模块都有可解释的业务来源，不再为了展示框架而拼接无关场景。

## 代价和风险

- 必须保留来源 URL、署名、许可证和固定快照；
- 公开文档更新后不能静默替换同一个数据集版本；
- GitHub API 限流、权限和网络失败需要分类处理；
- 写操作只能在专用演示仓库验收；
- 中文翻译可能落后于英文页面，需要在失败分析中记录，而不是私自混入英文最新版。

## 验证方法

1. 校验 manifest 中 33 个文件全部存在且 SHA-256 一致；
2. 对 Markdown 标题、代码块、列表和超长章节生成 Chunk 统计；
3. 建立 12 条 Smoke Set 和 30 条人工审核 Dev Set；
4. 运行 Dense `top_k=5` Baseline 并保存逐题结果；
5. 对公开仓库真实调用 `get_workflow_run` 和 `list_workflow_jobs`；
6. 使用 Fake Gateway 验证取消/重跑必须 interrupt；
7. 最终只在专用演示仓库验证一次真实写操作。

## 重新评估条件

出现以下任一情况时重新评估：

- GitHub Docs 不再允许按当前许可使用；
- 中文文档质量不足以支持主要问题；
- GitHub API 无法稳定完成只读演示；
- 33 篇文档无法构建足够的多文档、无答案和版本问题；
- 项目目标从开发者技术支持改为其他行业场景。


## 后续细化

ADR-001 冻结的是统一业务语境、GitHub Docs Source Dataset 和初始 RAG 参数。后续数据画像发现 4 篇参考文档正文以英文为主，因此 ADR-002 将 33 篇 Source 进一步划分为 29 篇 Chinese Baseline 和 4 篇多语言实验文档。该细化不改变业务语境和 Source Dataset。
