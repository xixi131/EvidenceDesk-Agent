#!/usr/bin/env python3
"""生成确定性的语料画像和中文 RAG Baseline Manifest。

Source Manifest 和 Raw 文档是只读输入；本脚本只在同一语料目录下
写入派生元数据。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"
SOURCE_MANIFEST_PATH = CORPUS_DIR / "manifest.json"
BASELINE_MANIFEST_PATH = CORPUS_DIR / "baseline_manifest.json"
REPORTS_DIR = CORPUS_DIR / "reports"
CORPUS_PROFILE_PATH = REPORTS_DIR / "corpus_profile.json"

PROFILE_VERSION = "github-actions-corpus-profile-v1"
BASELINE_VERSION = "github-actions-zh-baseline-v1"
CLEANING_RULES_VERSION = "github-actions-cleaning-v1"
DECISION_DATE = "2026-08-05"
MULTILINGUAL_EXPERIMENT = "github-actions-multilingual-reference-v1"

ENGLISH_DOMINANT_THRESHOLD = 0.10
MIXED_TECHNICAL_THRESHOLD = 0.40
LARGE_DOCUMENT_THRESHOLD = 10_000
OVERSIZED_DOCUMENT_THRESHOLD = 50_000
MANY_CODE_BLOCKS_THRESHOLD = 20

EXCLUDED_DOCUMENT_IDS = {
    "github_actions_zh_actions__reference__workflows-and-actions__workflow-syntax",
    "github_actions_zh_rest__actions__workflow-runs",
    "github_actions_zh_rest__actions__workflow-jobs",
    "github_actions_zh_rest__actions__workflows",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def nearest_rank(values: list[int], percentile: float) -> int:
    """为非空列表计算确定性的最近秩百分位数。"""
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def classify_category(relative_path: str) -> str:
    if "/rest/actions/" in f"/{relative_path}":
        return "rest_api"
    if "/security/" in relative_path:
        return "security_and_permissions"
    if "/self-hosted-runners/" in relative_path or "/runners/" in relative_path:
        return "runner"
    if "/monitor-workflows/" in relative_path or relative_path.endswith(
        "troubleshoot-workflows.md"
    ):
        return "monitoring_and_troubleshooting"
    if "/manage-workflow-runs/" in relative_path:
        return "workflow_run_management"
    if "/workflows-and-actions/" in relative_path:
        return "concepts_and_syntax"
    return "other"


def classify_language(cjk_ratio: float) -> str:
    # 技术标识符、URL 和代码会提高中文文档中的拉丁字符比例，
    # 因此只有在中文字符占比非常低时，才判定为英文占主导。
    if cjk_ratio < ENGLISH_DOMINANT_THRESHOLD:
        return "english_dominant"
    if cjk_ratio < MIXED_TECHNICAL_THRESHOLD:
        return "mixed_technical"
    return "chinese_dominant"


def analyze_document(document: dict[str, Any]) -> dict[str, Any]:
    raw_path = CORPUS_DIR / document["relative_path"]
    text = raw_path.read_text(encoding="utf-8")

    headings = re.findall(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    language_denominator = cjk_count + latin_count
    cjk_ratio = cjk_count / language_denominator if language_denominator else 0.0

    metrics = {
        "character_count": len(text),
        "line_count": text.count("\n") + 1,
        "heading_count": len(headings),
        "h2_count": sum(1 for level, _ in headings if len(level) == 2),
        "code_block_count": text.count("```") // 2,
        "cjk_character_count": cjk_count,
        "latin_character_count": latin_count,
        "cjk_ratio": round(cjk_ratio, 6),
        "svg_count": len(re.findall(r"<svg\b", text)),
        "html_tag_count": len(re.findall(r"<[A-Za-z][^>]*>", text)),
        "relative_link_count": len(re.findall(r"\]\(/(?:zh|en)/", text)),
        "english_relative_link_count": len(re.findall(r"\]\(/en/", text)),
        "escaped_callout_count": len(re.findall(r"\\\[![A-Z]+\]", text)),
    }

    language_profile = classify_language(metrics["cjk_ratio"])
    risk_flags: list[str] = []
    if language_profile == "english_dominant":
        risk_flags.append("english_dominant")
    elif language_profile == "mixed_technical":
        risk_flags.append("mixed_language_or_code_heavy")
    if metrics["character_count"] >= OVERSIZED_DOCUMENT_THRESHOLD:
        risk_flags.append("oversized_document")
    elif metrics["character_count"] >= LARGE_DOCUMENT_THRESHOLD:
        risk_flags.append("large_document")
    if metrics["code_block_count"] >= MANY_CODE_BLOCKS_THRESHOLD:
        risk_flags.append("many_code_blocks")
    if metrics["svg_count"]:
        risk_flags.append("inline_svg")
    if metrics["html_tag_count"]:
        risk_flags.append("inline_html")
    if metrics["relative_link_count"]:
        risk_flags.append("relative_links")
    if metrics["english_relative_link_count"]:
        risk_flags.append("english_relative_links")
    if metrics["escaped_callout_count"]:
        risk_flags.append("escaped_callouts")

    baseline_included = document["document_id"] not in EXCLUDED_DOCUMENT_IDS
    exclusion_reason = None
    future_experiment = None
    if not baseline_included:
        exclusion_reason = (
            "English-dominant reference document; excluded from the first "
            "Chinese embedding baseline to keep the language variable controlled."
        )
        future_experiment = MULTILINGUAL_EXPERIMENT

    return {
        "document_id": document["document_id"],
        "title": document["title"],
        "category": classify_category(document["relative_path"]),
        "source_relative_path": document["relative_path"],
        "source_url": document["public_url"],
        "source_sha256": document["sha256"],
        "language_profile": language_profile,
        "baseline_included": baseline_included,
        "exclusion_reason": exclusion_reason,
        "future_experiment": future_experiment,
        "cleaning_status": "pending",
        "risk_flags": risk_flags,
        "metrics": metrics,
    }


def build_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    source_manifest = read_json(SOURCE_MANIFEST_PATH)
    analyzed_documents = [
        analyze_document(document) for document in source_manifest["documents"]
    ]

    included_documents = [
        document for document in analyzed_documents if document["baseline_included"]
    ]
    excluded_documents = [
        document for document in analyzed_documents if not document["baseline_included"]
    ]

    sizes = [document["metrics"]["character_count"] for document in analyzed_documents]
    category_counts = Counter(document["category"] for document in analyzed_documents)
    language_counts = Counter(
        document["language_profile"] for document in analyzed_documents
    )
    risk_counts = Counter(
        risk for document in analyzed_documents for risk in document["risk_flags"]
    )

    corpus_profile = {
        "profile_version": PROFILE_VERSION,
        "generated_on": DECISION_DATE,
        "source_dataset_version": source_manifest["dataset_version"],
        "source_repository_commit": source_manifest["source_repository_commit"],
        "document_count": len(analyzed_documents),
        "total_character_count": sum(sizes),
        "size_statistics": {
            "minimum": min(sizes),
            "median": nearest_rank(sizes, 0.50),
            "p75": nearest_rank(sizes, 0.75),
            "p90": nearest_rank(sizes, 0.90),
            "p95": nearest_rank(sizes, 0.95),
            "maximum": max(sizes),
        },
        "total_heading_count": sum(
            document["metrics"]["heading_count"] for document in analyzed_documents
        ),
        "total_code_block_count": sum(
            document["metrics"]["code_block_count"] for document in analyzed_documents
        ),
        "category_counts": dict(sorted(category_counts.items())),
        "language_profile_counts": dict(sorted(language_counts.items())),
        "risk_flag_counts": dict(sorted(risk_counts.items())),
        "baseline_summary": {
            "included_document_count": len(included_documents),
            "excluded_document_count": len(excluded_documents),
            "included_character_count": sum(
                document["metrics"]["character_count"]
                for document in included_documents
            ),
            "excluded_character_count": sum(
                document["metrics"]["character_count"]
                for document in excluded_documents
            ),
        },
        "largest_documents": [
            {
                "document_id": document["document_id"],
                "title": document["title"],
                "character_count": document["metrics"]["character_count"],
                "language_profile": document["language_profile"],
                "baseline_included": document["baseline_included"],
            }
            for document in sorted(
                analyzed_documents,
                key=lambda item: item["metrics"]["character_count"],
                reverse=True,
            )[:10]
        ],
    }

    baseline_manifest = {
        "baseline_version": BASELINE_VERSION,
        "status": "frozen",
        "decision_date": DECISION_DATE,
        "source_dataset_version": source_manifest["dataset_version"],
        "source_manifest": "manifest.json",
        "source_repository_commit": source_manifest["source_repository_commit"],
        "cleaning_rules_version": CLEANING_RULES_VERSION,
        "cleaned_output_directory": "cleaned/",
        "embedding_baseline": {
            "model": "BAAI/bge-small-zh-v1.5",
            "retrieval_mode": "dense",
            "top_k": 5,
            "query_rewrite": False,
            "reranker": None,
        },
        "selection_policy": {
            "description": (
                "Keep all raw source documents, but exclude the four "
                "English-dominant reference documents from the first Chinese "
                "embedding baseline."
            ),
            "english_dominant_threshold": ENGLISH_DOMINANT_THRESHOLD,
            "excluded_document_ids": sorted(EXCLUDED_DOCUMENT_IDS),
            "future_experiment": MULTILINGUAL_EXPERIMENT,
        },
        "document_count": len(analyzed_documents),
        "included_document_count": len(included_documents),
        "excluded_document_count": len(excluded_documents),
        "documents": analyzed_documents,
    }

    return corpus_profile, baseline_manifest


def main() -> None:
    corpus_profile, baseline_manifest = build_outputs()
    write_json(CORPUS_PROFILE_PATH, corpus_profile)
    write_json(BASELINE_MANIFEST_PATH, baseline_manifest)

    print(f"source_documents={baseline_manifest['document_count']}")
    print(f"baseline_included={baseline_manifest['included_document_count']}")
    print(f"baseline_excluded={baseline_manifest['excluded_document_count']}")
    print(f"profile={CORPUS_PROFILE_PATH.relative_to(ROOT)}")
    print(f"baseline_manifest={BASELINE_MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
