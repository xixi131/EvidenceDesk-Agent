"""构建 P6-04 的 33 篇对照语料（github-actions-multilingual-reference-v1）。

背景：阶段 1 建中文 Baseline 时，把 4 篇「英文为主」的参考文档排除在外了
（workflow-syntax 和 3 篇 REST API 文档，其中 workflow-syntax 的中文字符占比
只有 0.04%）。当时的理由写在 baseline_manifest 里：用中文 Embedding 模型，
先把语言这个变量控制住。那 4 条记录上还预留了
`future_experiment: github-actions-multilingual-reference-v1`——就是这个实验。

这个脚本生成一份**平行的**语料目录：同一批下载好的原始文档、同一个
dataset_version，但 33 篇全部纳入、一篇不排除。

为什么必须是独立目录而不是共用一个：
generate_cleaned_corpus() 会先 `rmtree(cleaned/)` 再重建。两个 Baseline 共用
一个 corpus_root 的话，跑哪个都会把另一个的 cleaned/ 和 reports/ 删掉——
阶段 1 冻结的那份就毁了。原始的 github_actions_zh_v1 目录全程只读，不碰。
"""

import json
import shutil
from pathlib import Path

from evidence_desk.rag.chunking.chunk_quality_pipeline import (
    generate_chunk_quality_report,
)
from evidence_desk.rag.corpus.cleaning_pipeline import generate_cleaned_corpus
from evidence_desk.rag.corpus.manifest import (
    MULTILINGUAL_BASELINE,
    MULTILINGUAL_BASELINE_VERSION,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "data/knowledge_base/github_actions_zh_v1"
TARGET_ROOT = PROJECT_ROOT / "data/knowledge_base/github_actions_multilingual_v1"

# 原样复制的文件/目录：原始文档和 Source Manifest 是同一份快照，不该有第二个版本。
COPIED_ENTRIES = (
    "documents",
    "manifest.json",
    "ATTRIBUTION.md",
    "LICENSE-CC-BY-4.0.txt",
)


def _build_multilingual_baseline_manifest() -> dict[str, object]:
    """基于中文 Baseline Manifest 生成"全部纳入"的版本。"""

    raw = json.loads(
        (SOURCE_ROOT / "baseline_manifest.json").read_text(encoding="utf-8")
    )

    documents = raw["documents"]
    for document in documents:
        # 把 4 篇原本排除的文档打开。exclusion_reason 清空，但不动
        # language_profile / risk_flags / metrics——那些是对文档本身的客观描述，
        # 跟"这一版纳不纳入它"是两回事，保留着才能在报告里解释结果。
        document["baseline_included"] = True
        document["exclusion_reason"] = None
        document["future_experiment"] = None

    raw["baseline_version"] = MULTILINGUAL_BASELINE_VERSION
    raw["included_document_count"] = len(documents)
    raw["excluded_document_count"] = 0
    raw["selection_policy"] = {
        **raw["selection_policy"],
        "description": (
            "P6-04 multilingual comparison: include all 33 source documents, "
            "including the four English-dominant reference documents that the "
            "first Chinese baseline excluded."
        ),
        "excluded_document_ids": [],
    }
    return dict(raw)


def main() -> None:
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)
    TARGET_ROOT.mkdir(parents=True)

    for entry in COPIED_ENTRIES:
        source = SOURCE_ROOT / entry
        target = TARGET_ROOT / entry
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

    manifest = _build_multilingual_baseline_manifest()
    (TARGET_ROOT / "baseline_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cleaning_report = generate_cleaned_corpus(
        TARGET_ROOT, spec=MULTILINGUAL_BASELINE
    )
    chunk_report = generate_chunk_quality_report(
        TARGET_ROOT, spec=MULTILINGUAL_BASELINE
    )

    print(f"语料目录：{TARGET_ROOT.relative_to(PROJECT_ROOT)}")
    print(f"清洗文档数：{len(cleaning_report.documents)}")
    print(f"Chunk 数：{chunk_report.chunk_count}")


if __name__ == "__main__":
    main()
