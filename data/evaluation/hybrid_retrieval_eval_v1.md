# Dense / BM25 / Hybrid 检索对比报告（P6-03）

- K：5
- Hybrid alpha：0.5（0=纯BM25，1=纯Dense）
- 题目数：51

## 中文分词方案

分词版本：`jieba-0.42.1-domain-v1`（应用侧 jieba + 领域词典，见 `src/evidence_desk/rag/tokenization.py`）

上一轮用 Weaviate 内置的 GSE_CH 分词器时，BM25 在中文上几乎完全失效（Recall@5=0.1176，「标签」「构件」「取消」等词确认存在于原文却返回 0 条）。根因是索引端和查询端切词不一致——BM25 靠 token 精确相等匹配，两端切法不同就永远匹配不上。排查过程见`/Users/tangxitao/学习/My-Notes/Agent开发/错误记录/Weaviate中文BM25分词失效排查.md`。

现在改为：索引和查询都调用同一个 `segment()` 切词，Weaviate 侧的`content_tokens`/`title_tokens` 字段只用 WHITESPACE 分词（按空格切，不做任何推断）。分词的确定性由应用代码保证，失配这类问题从结构上消除。

## 总体指标

| 方法 | Recall@K | Precision@K | MRR |
| --- | --- | --- | --- |
| Dense | 0.9314 | 0.2157 | 0.8693 |
| BM25 | 0.9118 | 0.2078 | 0.8170 |
| Hybrid | 0.9608 | 0.2196 | 0.9010 |

## 按标签细分的 Recall@K

| 标签 | Dense | BM25 | Hybrid |
| --- | --- | --- | --- |
| artifact | 1.0000 | 1.0000 | 1.0000 |
| cache | 1.0000 | 1.0000 | 1.0000 |
| concept | 1.0000 | 0.6667 | 1.0000 |
| debug | 1.0000 | 1.0000 | 1.0000 |
| exact_identifier | 0.9211 | 0.9737 | 0.9737 |
| multi_document | 0.8333 | 0.7222 | 0.7778 |
| rerun | 1.0000 | 1.0000 | 1.0000 |
| runner | 0.7500 | 0.8750 | 1.0000 |
| secret | 1.0000 | 1.0000 | 1.0000 |
| security | 1.0000 | 1.0000 | 1.0000 |
| semantic_paraphrase | 0.9118 | 0.8529 | 0.9412 |
