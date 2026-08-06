# 03｜RAG 数据处理与分块策略

> 分块不是把字符串每 500 个字符切一刀。分块的目标是：让每个 Chunk 能独立表达一个可检索、可引用、可理解的知识单元。

## 1. 为什么分块决定 RAG 上限

Embedding 和 Retriever 检索的是 Chunk，不是原始整份文档。

如果切坏了：

- 正确答案可能横跨两个 Chunk；
- 标题和正文可能分离；
- 条件和结论可能分离；
- 表格表头和数据可能分离；
- 一个 Chunk 混入多个主题；
- 相同 overlap 产生大量重复结果。

后续换 Embedding 或调 top_k，无法完全补救已经丢失的语义结构。

## 2. 已冻结的数据集

```text
dataset_version: github-actions-zh-2026-08-05-v1
source: GitHub Docs - GitHub Actions 中文文档
document_count: 33
format: rendered Markdown
license: CC BY 4.0
local_path: data/knowledge_base/github_actions_zh_v1
```

第一版只实现和验收 Markdown Loader。源仓库的模板语法已通过官方页面渲染结果展开，实验直接使用本地冻结快照，不在运行时在线抓取。

## 3. 数据处理流水线

```mermaid
graph LR
    A[原始文档] --> B[解析 Loader]
    B --> C[清洗 Cleaner]
    C --> D[结构提取]
    D --> E[分块 Splitter]
    E --> F[Chunk 质量检查]
    F --> G[Embedding]
    G --> H[写入 Weaviate]
    H --> I[检索评测]
```

每一步都必须可观察，不能直接执行 `load_and_split()` 后不知道发生了什么。

## 4. 原始文档模型

PostgreSQL 文档登记至少保存：

```text
document_id
source_uri
file_name
content_type
title
version
status
checksum
effective_at
created_at
updated_at
```

`checksum` 用于判断内容是否变化，避免重复索引。

## 5. Chunk 必须保存的字段

```json
{
  "chunk_id": "github_actions_enable_debug_logging_chunk_01",
  "parent_doc_id": "github_actions_enable_debug_logging",
  "title": "启用调试日志记录",
  "section_path": ["监视工作流", "启用调试日志记录", "启用步骤调试日志"],
  "content": "若要启用步骤调试日志记录……",
  "chunk_index": 1,
  "content_hash": "...",
  "metadata": {
    "category": "workflow_debugging",
    "product": "github_actions",
    "dataset_version": "github-actions-zh-2026-08-05-v1",
    "status": "active",
    "effective_at": "2026-08-01"
  }
}
```

`section_path` 很重要，因为只保存正文会丢失标题语义。

最终用于 Embedding 的文本建议是：

```text
标题：启用调试日志记录
章节：监视工作流 > 启用调试日志记录 > 启用步骤调试日志
正文：若要启用步骤调试日志记录……
```

## 6. 第一版分块 Baseline

第一版采用：

```yaml
strategy: structure_then_recursive
chunk_size: 600
chunk_overlap: 80
length_unit: character
keep_title: true
keep_section_path: true
```

这里的 600 是字符，不是 Token。因为 LangChain 的 RecursiveCharacterTextSplitter 默认可以按字符长度计算；后续也可以换成模型 Tokenizer。

### 为什么从 600/80 开始

- 中文技术文档一个完整规则或排查步骤通常能放入该范围；
- 比 300 字更不容易把条件和结论切开；
- 比 1000 字更不容易混入多个主题；
- 80 字 overlap 可以保留段落边界附近上下文，又不会产生过多重复。

它只是 Baseline，不代表最终最佳值。

官方资料：[RecursiveCharacterTextSplitter](https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter)

## 7. 中文递归分隔符

建议优先级：

```python
separators = [
    "\n\n",     # 段落
    "\n",       # 行
    "。",        # 中文句号
    "！",
    "？",
    "；",
    "，",
    " ",
    "",
]
```

递归切分的思想：

1. 先尝试在大结构边界切；
2. 如果仍然太长，再使用更小边界；
3. 最后才退化到字符级。

不能把逗号放在段落之前，否则会过早产生碎片。

## 8. 不同文档结构如何分

### Markdown

优先按标题结构：

```text
# GitHub Actions
## 监视工作流
### 启用调试日志记录
```

先按 Heading 形成 Section，再对过长 Section 递归切分。

为什么：标题本身就是高质量语义标签。

### FAQ

一组问答作为一个知识单元：

```text
Q: 如何查看失败的工作流日志？
A: 打开 Workflow Run，选择失败 Job 和 Step……
```

不要把 Q 和 A 分开。

### 业务规则

必须保证条件与结论在同一 Chunk：

```text
条件：Workflow 使用 fork pull request 且需要写权限
结论：必须按文档要求审批运行或调整最小权限
```

### 故障排查

按“现象—原因—步骤—升级条件”组织：

```text
失败现象
Workflow/Runner 范围
排查步骤
仍失败怎么办
```

### GitHub Docs 大型参考页

`workflow-syntax.md` 和 REST API 页面明显长于普通文章，必须先按 Heading 建立 Section，再对超长 Section 递归切分。不能整篇作为一个 Chunk，也不能只按固定字符切断 YAML Key、参数说明和代码块。

### 表格

不要把表头和数据行分开。可将一行字段说明转换为包含字段名、类型、权限和描述的文本单元。

### 代码块和 YAML

保持一个完整 YAML 示例或 Shell 命令块。代码块超过 600 字符时，优先以相邻标题和解释作为 Parent Section，记录截断风险，不能在普通字符位置静默切断。

### 暂不支持 PDF/TXT

第一版真实数据源是结构化 Markdown。PDF/TXT Loader 不属于第一版验收，只有引入真实对应来源并补充解析评测时才加入。

## 9. Overlap 为什么不能太大

Overlap 的作用是保留边界信息。

太小：

- 句子和解释可能分开；
- 条件在前一块、结果在后一块。

太大：

- 多个结果高度重复；
- Top-K 被同一段内容占满；
- Precision 降低；
- 存储和 Embedding 成本增加。

需要监控：

```text
平均 Chunk 长度
Chunk 数量
重复率
同一 parent_doc_id 占 Top-K 的比例
```

## 10. Chunk 质量检查

索引前执行规则检查：

- Chunk 不为空；
- 长度在合理范围；
- title 存在；
- parent_doc_id 存在；
- content_hash 唯一；
- 不包含重复页眉页脚；
- 不是只有目录或导航；
- 表格有表头；
- 代码块没有被截断。

并生成报告：

```text
文档数
Chunk 总数
平均长度
P50/P95 长度
过短 Chunk 数
过长 Chunk 数
重复 Chunk 数
```

## 11. 第一组分块实验

固定：

- 同一批文档；
- 同一 Embedding；
- Dense Retrieval；
- top_k=5；
- 不开 Query Rewrite；
- 不开 Reranker。

只比较：

| 实验 | chunk_size | overlap |
|---|---:|---:|
| small | 300 | 50 |
| baseline | 600 | 80 |
| large | 900 | 120 |

记录：

- Recall@5；
- Precision@5；
- MRR；
- Chunk 总数；
- 索引时间；
- 平均检索延迟；
- 多文档问题表现；
- 失败案例。

## 12. 如何根据失败案例调整

### 正确内容被切成两块

动作：增大 Chunk、增加 overlap，或按结构合并。

### 检索结果包含很多不同主题

动作：减小 Chunk，改善标题和 metadata。

### Top-K 都是同一文档的重复段落

动作：减小 overlap、去重、按 parent_doc_id 限制，或使用 MMR。

### `GITHUB_TOKEN`、环境变量或 YAML Key 检索失败

动作：不是先改 Chunk，而是检查文本规范化、BM25 和 Hybrid。

### 多文档问题只找到一份资料

动作：增大候选 top_n、使用 Hybrid、加入 Reranker；不要直接把最终上下文 top_k 无限增大。

## 13. 进阶策略什么时候加入

### Parent-Child Retrieval

小 Chunk 用于检索，大 Parent 用于给模型上下文。

适用：小块容易命中，但答案需要更完整段落。

### Semantic Chunking

通过语义变化决定边界。

适用：段落结构差、主题切换明显的长文本。

代价：速度慢、成本高、结果更难复现。第一版不使用。

### Contextual Retrieval

为 Chunk 补充文档上下文描述。

适用：Chunk 脱离原文后语义不足。

代价：需要额外 LLM 调用和索引成本。先通过标题与 section_path 解决。

## 14. 分块决策完成标准

不是“代码能切”，而是：

1. 能解释 Baseline 参数为什么这样定；
2. 能展示三种 Chunk 样例；
3. 有 Chunk 统计报告；
4. 有 12 条 Smoke Set 和人工审核的文档级 Ground Truth；
5. 有三组切片实验；
6. 能根据失败案例说明最终选择。
