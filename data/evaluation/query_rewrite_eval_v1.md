# Query Rewrite 对比报告（P6-02）

- 检索方式：Dense（不开重排，一次只动一个变量）
- Top-K：5
- 改写模型：`gpt-5.5`
- 改写提示词版本：`query-rewrite-v1`
- 失败阈值（Top-1 score）：0.62
- 题目数：51

## 总体指标

| 方法 | Recall@K | Precision@K | MRR | 改写率 | 每题耗时(ms) |
| --- | --- | --- | --- | --- | --- |
| Original | 0.9314 | 0.2157 | 0.8693 | 0.00% | 9.8 |
| RewriteAlways | 0.9412 | 0.2196 | 0.9036 | 96.08% | 2675.4 |
| RewriteOnFailure | 0.9412 | 0.2196 | 0.8807 | 21.57% | 679.2 |

## 延迟拆解（ms/题）

| 方法 | 失败探测 | LLM 改写 | 检索 | 合计 |
| --- | --- | --- | --- | --- |
| Original | 0.0 | 0.0 | 9.8 | 9.8 |
| RewriteAlways | 0.0 | 2666.7 | 8.8 | 2675.4 |
| RewriteOnFailure | 20.5 | 657.0 | 7.8 | 679.2 |

## 精确标识符保留情况

只统计**真的被改写过**的题。保留率的分母是原问题里的标识符总数；大小写变化不算丢失（索引和查询都会归一化），标识符整个消失或被翻译成中文才算。

| 方法 | 含标识符题数 | 标识符总数 | 丢失个数 | 保留率 | 丢失题数 | 新增标识符题数 |
| --- | --- | --- | --- | --- | --- | --- |
| RewriteAlways | 8 | 8 | 0 | 1.0000 | 0 | 0 |
| RewriteOnFailure | 1 | 1 | 0 | 1.0000 | 0 | 0 |

## 按标签细分的 Recall@K

| 标签 | Original | RewriteAlways | RewriteOnFailure |
| --- | --- | --- | --- |
| artifact | 1.0000 | 1.0000 | 1.0000 |
| cache | 1.0000 | 1.0000 | 1.0000 |
| concept | 1.0000 | 1.0000 | 1.0000 |
| debug | 1.0000 | 1.0000 | 1.0000 |
| exact_identifier | 0.9211 | 0.8684 | 0.8684 |
| multi_document | 0.8333 | 0.8889 | 0.8889 |
| rerun | 1.0000 | 1.0000 | 1.0000 |
| runner | 0.7500 | 1.0000 | 1.0000 |
| secret | 1.0000 | 1.0000 | 1.0000 |
| security | 1.0000 | 1.0000 | 1.0000 |
| semantic_paraphrase | 0.9118 | 1.0000 | 1.0000 |

## 退化案例（相对 Original 掉分的题）

### RewriteAlways

- **dev-058**（exact_identifier）Recall 1.00 → 0.00
  - 原问题：工件（artifact）的默认保留时间是多久？
  - 改写后：GitHub Actions 工件（artifact）的默认保留时间是多久？

### RewriteOnFailure

- **dev-058**（exact_identifier）Recall 1.00 → 0.00
  - 原问题：工件（artifact）的默认保留时间是多久？
  - 改写后：GitHub Actions 中工件（artifact）的默认保留时间是多久？

## 标识符异常明细（人工抽查用）

`lost` 是真问题；`introduced` 只是**可疑**——模型把「手动触发」归一化成 `workflow_dispatch` 反而可能帮到检索，必须逐条看原文判断，不能自动判错。

无。

## Top-1 分数分布（用于校准失败阈值）

RewriteOnFailure 用「Top-1 score 低于阈值」当失败信号。阈值定得对不对，要看这份真实分布——阈值太低则永远不触发（等于 Original），太高则每题都触发（等于 RewriteAlways）。

- 最小值：0.5570
- 25 分位：0.6398
- 中位数：0.7111
- 75 分位：0.7567
- 最大值：0.8368
- 当前阈值 0.62 下触发改写：11 题

