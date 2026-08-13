# ADR-003｜Chunk 策略代码与运行产物版本边界

- 状态：Accepted
- 日期：2026-08-08
- 决策人：项目负责人 / AI 协作

## 背景

P1B-02 已经开始产生 Chunk 正文。当前 RAG 根目录同时放置 Manifest、Loader、Cleaner、Section 提取和 Splitter，随着 Chunk Metadata、质量报告、Embedding 和索引继续加入，职责会混在同一层。

同时，切块实验不能只保留“当前向量库里的结果”。如果 600/80 被 800/100 覆盖，后续无法解释某次检索结果使用了什么 Chunk，也无法复现实验。

## 约束

- 第一版保持模块化单体和浅层目录；
- Raw 文档不可覆盖；
- Cleaned 文档是可重生成的派生数据；
- Chunk 策略会进行受控实验，不承诺第一版 Baseline 是最终最优；
- 同一输入和配置重复运行必须幂等；
- 不为每个 Chunk 创建独立文件，避免产生大量难以管理的小文件；
- 代码历史由 Git 保留，运行结果由 Chunk Run 产物保留。

## 候选方案

### 方案 A：所有代码继续放在 `rag/` 根目录，结果只写入当前索引

优点：文件少，初期实现快。

缺点：职责混合；旧 Chunk 结果被覆盖后无法复现；向量库不适合作为唯一实验档案。

### 方案 B：为每个策略复制一套代码文件，并为每个 Chunk 创建一个文件

优点：旧代码和旧结果看起来直观。

缺点：代码重复；修复通用 Bug 需要同步多份实现；大量小文件不便于批量导入和审查。

### 方案 C：按职责分层，策略通过 Protocol 注入，运行结果按 Chunk Run 保存

优点：调用方不依赖具体算法；Git 保留代码历史；JSONL 保留每个 Chunk；Manifest 绑定输入、配置和 Git Commit；相同运行可幂等复用，不同实验可以并存。

缺点：需要维护 Run Manifest、Chunk ID 和幂等规则；初期文件和测试略多。

## 决策

选择方案 C。

代码目录调整为：

```text
src/evidence_desk/rag/
├── models/
├── corpus/
│   ├── manifest.py
│   ├── markdown_loader.py
│   ├── cleaner.py
│   └── cleaning_pipeline.py
└── chunking/
    ├── contracts.py
    ├── section_extractor.py
    ├── strategies.py
    └── splitter.py
```

Chunk Run 结果保存为：

```text
data/knowledge_base/github_actions_zh_v1/chunk_runs/<chunk_run_id>/
├── chunk_run_manifest.json
├── chunks.jsonl
└── chunk_report.json
```

一次 Chunk Run 的身份至少由以下内容决定：

```text
dataset_version
cleaning_rules_version
chunk_strategy_name
chunk_strategy_version
chunk_size
chunk_overlap
git_commit
```

代码通过 `ChunkingStrategy` Protocol 与具体实现解耦。第一版实现为 `StructureThenRecursiveChunkingStrategy`。后续策略实现可以替换注入，但不能把不同策略的结果混写到同一个 Run 中。

## 选择理由

- 目录反映变化原因：语料处理和 Chunk 处理不会混在一起；
- Chunk 是检索和 Embedding 的真实输入，必须能被人工查看和复现；
- “每个 Chunk 一个文件”不是必要的可追溯性，`chunks.jsonl` 已经做到一行一条记录，同时避免大量小文件；
- Chunk 算法版本应由 Git 管理，运行目录只保存运行快照和派生结果；
- Protocol 只有在出现可替换实现时引入，本次已经存在明确的策略替换需求，因此满足项目的接口边界条件。

## 代价和风险

- 需要额外维护 Chunk Run Manifest 和幂等导入；
- 不同实验会占用更多磁盘和 Embedding/索引资源；
- 仅保存 Git Commit 不能保证未来依赖环境完全一致，后续还需记录 uv.lock 和模型版本；
- 当前 P1B-02 仍未完成代码块不可截断、Chunk Metadata 和质量报告，这些由 P1B-03 至 P1B-05 完成。

## 验证方法

- 目录导入检查：所有当前模块只从新的职责目录导入；
- Protocol Fake 测试：Splitter 可以接收不依赖真实递归算法的 Fake 策略；
- 相同配置重复运行生成相同 Chunk ID 和内容哈希；
- 不同配置生成不同 Chunk Run；
- `chunks.jsonl` 的 Chunk 数量与报告、后续 Weaviate 对象数量一致。

## 重新评估条件

- Chunk Run 产物数量或磁盘成本明显影响开发流程；
- 需要将 Chunk 结果直接查询、筛选或版本回滚时，评估是否把 Chunk Run 元数据登记 PostgreSQL；
- 出现第二种稳定的切块策略并且 Protocol 无法表达共同能力时，重新设计策略接口；
- Embedding/Weaviate 导入需要更细粒度的增量更新时，补充 artifact cache 和索引生命周期设计。
