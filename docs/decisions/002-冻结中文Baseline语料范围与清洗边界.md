# ADR-002｜冻结中文 Baseline 语料范围与清洗边界

- 状态：Accepted
- 日期：2026-08-05
- 决策人：项目所有者

## 背景

Source Dataset `github-actions-zh-2026-08-05-v1` 已下载并通过文件哈希验证。进一步画像发现，33 篇文档长度和语言分布非常不均匀：4 篇参考文档正文以英文为主，且占整个语料字符量约 70%；原文还包含 SVG、HTML、相对链接和转义 Callout。若直接对全部文档分块、Embedding 和入库，将同时改变语言、数据量、文档结构和模型适配难度，无法可靠分析第一次检索失败的原因。

## 约束

- 业务约束：第一轮优先验证中文 GitHub Actions 技术支持问题。
- 技术约束：Embedding Baseline 为 `BAAI/bge-small-zh-v1.5`。
- 实验约束：一次只改变一个主要变量。
- 数据约束：Raw 原始文件和 Source Manifest 必须保持不变。
- 学习约束：用户需要理解 Source、Baseline、Cleaned 和 Chunk 的区别。

## 候选方案

### 方案 A：33 篇全部进入第一次 Baseline

优点：数据最完整，不需要选择规则。

缺点：4 篇英文参考文档占主要数据量；语言、文档长度和代码密度同时变化；中文 Embedding 检索失败时难以定位原因。

### 方案 B：29 篇进入中文 Baseline，4 篇英文参考文档暂时隔离

优点：控制语言变量；减少超大参考文档对首次分块实验的干扰；保留 4 篇文档用于后续多语言实验；与中文轻量 Embedding 的定位一致。

缺点：第一次 Baseline 不覆盖完整 Workflow Syntax 和 REST API 参考知识；需要维护 Baseline Manifest。

### 方案 C：33 篇全部纳入，并立即改用 `bge-m3`

优点：多语言能力更匹配完整数据；知识覆盖最全。

缺点：同时改变数据范围和 Embedding；跳过轻量中文 Baseline；索引、内存和延迟成本更高；无法形成清晰对照实验。

## 决策

选择方案 B。

```text
Source Dataset：33 篇全部保留
Chinese Baseline：29 篇
暂时隔离：4 篇英文占主导的参考文档
Baseline Version：github-actions-zh-baseline-v1
Cleaning Rules Version：github-actions-cleaning-v1
Future Experiment：github-actions-multilingual-reference-v1
```

暂时隔离：

```text
GitHub Actions 的工作流语法
工作流运行的 REST API 终结点
工作流作业的 REST API 终结点
工作流的 REST API 终结点
```

Source Manifest 继续记录官方原始快照；Baseline Manifest 单独记录实验选择和风险，不修改 Raw 文件。

## 选择理由

该方案将第一次实验的问题缩小为：

```text
29 篇中文为主的支持文档
+ 固定清洗规则
+ structure-aware recursive 600/80
+ bge-small-zh-v1.5
+ Dense top_k=5
```

如果检索失败，可以优先检查清洗、结构、Chunk、Query 和中文 Embedding，而不是同时怀疑大规模英文参考文档。

## 清洗边界

Cleaner 只做确定性格式规范：

- 去除正文展示用 SVG，保留可读标签；
- 删除普通 HTML 标签但保留可见文本；
- 将 GitHub Docs 相对链接转换为绝对链接；
- 规范化 NOTE/WARNING 等 Callout；
- 统一换行和多余空白；
- 保留标题、代码块、YAML、命令、参数和精确标识符。

Cleaner 不允许：

- 使用 LLM 改写；
- 自动总结；
- 自动翻译；
- 删除代码示例；
- 覆盖 Raw 文件。

## 代价和风险

- 第一次 Baseline 无法回答完整 Workflow Syntax 和 REST API 参考问题；
- 简单字符比例不是完美的语言识别方法；
- 29 篇中仍有代码和英文标识符，需要在失败分析中按标签查看；
- 清洗 SVG/HTML 时可能误删可见信息，必须在代码围栏外处理并人工抽查。

## 验证方法

1. Source Manifest 仍有 33 个唯一文档；
2. Baseline Manifest 中 29 篇纳入、4 篇排除；
3. 纳入和排除集合无重复、无遗漏；
4. 4 篇排除文档与 ADR 列表完全一致；
5. 每篇 `source_sha256` 与 Source Manifest 和 Raw 文件一致；
6. 生成数据画像和风险统计；
7. Cleaner 完成后再验证 Cleaned 文档与 Cleaning Report。

## 重新评估条件

出现以下任一情况时重新评估：

- 中文 Baseline 无法覆盖关键 Workflow Syntax 问题；
- 29 篇语料不足以构建 30 条 Dev Set；
- `bge-m3` 多语言实验显著提升质量且成本可接受；
- 用户业务问题明确需要 REST API 和完整语法参考；
- GitHub Docs 中文内容更新并补齐当前英文参考页。
