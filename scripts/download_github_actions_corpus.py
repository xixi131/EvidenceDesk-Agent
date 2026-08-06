#!/usr/bin/env python3
"""下载冻结的 GitHub Actions 中文文档语料。

本脚本只使用 Python 标准库。运行后会刷新本地快照，因此除非明确创建
新的数据集版本，否则不要在实验期间运行。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"
DOCUMENT_DIR = OUTPUT_DIR / "documents"
DATASET_VERSION = "github-actions-zh-2026-08-05-v1"
USER_AGENT = "EvidenceDesk-Agent-corpus-downloader/1.0"

PATHS = [
    "/actions/how-tos/troubleshoot-workflows",
    "/actions/how-tos/monitor-workflows/use-workflow-run-logs",
    "/actions/how-tos/monitor-workflows/enable-debug-logging",
    "/actions/how-tos/monitor-workflows/use-the-visualization-graph",
    "/actions/how-tos/monitor-workflows/view-job-condition-logs",
    "/actions/how-tos/monitor-workflows/view-workflow-run-history",
    "/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs",
    "/actions/how-tos/manage-workflow-runs/cancel-a-workflow-run",
    "/actions/how-tos/manage-workflow-runs/delete-a-workflow-run",
    "/actions/how-tos/manage-workflow-runs/download-workflow-artifacts",
    "/actions/how-tos/manage-workflow-runs/manage-caches",
    "/actions/how-tos/manage-workflow-runs/approve-runs-from-forks",
    "/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows",
    "/actions/how-tos/manage-workflow-runs/manually-run-a-workflow",
    "/actions/concepts/workflows-and-actions/workflows",
    "/actions/concepts/workflows-and-actions/workflow-artifacts",
    "/actions/concepts/workflows-and-actions/dependency-caching",
    "/actions/concepts/workflows-and-actions/contexts",
    "/actions/concepts/workflows-and-actions/expressions",
    "/actions/concepts/workflows-and-actions/variables",
    "/actions/concepts/security/github_token",
    "/actions/concepts/security/secrets",
    "/actions/concepts/security/script-injections",
    "/actions/concepts/security/compromised-runners",
    "/actions/concepts/runners/self-hosted-runners",
    "/actions/how-tos/manage-runners/self-hosted-runners/monitor-and-troubleshoot",
    "/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow",
    "/actions/how-tos/manage-runners/self-hosted-runners/apply-labels",
    "/actions/reference/workflows-and-actions/workflow-syntax",
    "/actions/reference/workflows-and-actions/workflow-cancellation",
    "/rest/actions/workflow-runs",
    "/rest/actions/workflow-jobs",
    "/rest/actions/workflows",
]


def fetch(url: str, *, accept: str, attempts: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": accept},
            )
            with urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as exc:  # 不同平台产生的网络异常类型可能不同
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 1.5)
    raise RuntimeError(f"failed to download {url}: {last_error}") from last_error


def first_heading(markdown: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else "未命名"


def relative_document_path(pathname: str) -> Path:
    return Path(pathname.lstrip("/")).with_suffix(".md")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="覆盖冻结目录；仅在明确创建新数据集版本时使用",
    )
    args = parser.parse_args()

    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists() and not args.allow_overwrite:
        raise SystemExit(
            f"Frozen corpus already exists at {OUTPUT_DIR}. "
            "Run scripts/verify_github_actions_corpus.py instead. "
            "To refresh sources, first choose a new dataset version and output directory."
        )

    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()

    commit_data = json.loads(
        fetch(
            "https://api.github.com/repos/github/docs/commits/main",
            accept="application/vnd.github+json",
        )
    )
    source_commit = commit_data["sha"]
    source_commit_date = commit_data["commit"]["committer"]["date"]

    records: list[dict[str, object]] = []
    for index, pathname in enumerate(PATHS, start=1):
        localized_pathname = f"/zh{pathname}"
        download_url = "https://docs.github.com/api/article/body?pathname=" + quote(
            localized_pathname, safe="/"
        )
        public_url = f"https://docs.github.com{localized_pathname}"
        content = fetch(download_url, accept="text/markdown")
        markdown = content.decode("utf-8")

        relative_path = relative_document_path(pathname)
        output_path = DOCUMENT_DIR / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

        document_id = "github_actions_zh_" + pathname.strip("/").replace("/", "__")
        records.append(
            {
                "document_id": document_id,
                "title": first_heading(markdown),
                "locale": "zh",
                "pathname": pathname,
                "public_url": public_url,
                "download_url": download_url,
                "relative_path": str(Path("documents") / relative_path),
                "sha256": hashlib.sha256(content).hexdigest(),
                "byte_size": len(content),
                "status": "active",
            }
        )
        print(f"[{index:02d}/{len(PATHS)}] {relative_path} ({len(content)} bytes)")

    license_content = fetch(
        f"https://raw.githubusercontent.com/github/docs/{source_commit}/LICENSE",
        accept="text/plain",
    )
    (OUTPUT_DIR / "LICENSE-CC-BY-4.0.txt").write_bytes(license_content)

    manifest = {
        "dataset_version": DATASET_VERSION,
        "status": "frozen",
        "product_context": "GitHub Actions technical support and workflow operations",
        "source_name": "GitHub Docs - GitHub Actions",
        "source_repository": "https://github.com/github/docs",
        "source_repository_commit": source_commit,
        "source_repository_commit_date": source_commit_date,
        "retrieved_at": retrieved_at,
        "locale": "zh",
        "license": "CC-BY-4.0",
        "license_file": "LICENSE-CC-BY-4.0.txt",
        "document_count": len(records),
        "documents": records,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    attribution = f"""# 数据来源与署名\n\n- 数据集版本：`{DATASET_VERSION}`\n- 产品语境：GitHub Actions 技术支持与工作流运行协同\n- 来源：GitHub Docs 的 GitHub Actions 中文文档\n- 来源仓库：https://github.com/github/docs\n- 固定提交：`{source_commit}`\n- 提交时间：`{source_commit_date}`\n- 抓取时间：`{retrieved_at}`\n- 许可：Creative Commons Attribution 4.0 International（CC BY 4.0）\n\n本目录保留原始文档内容用于 EvidenceDesk Agent 的检索、引用和评测练习。\n引用回答时应保留 manifest 中的原始页面 URL。GitHub 和 GitHub Actions 是 GitHub, Inc. 的商标；本项目不是 GitHub 官方产品。\n"""
    (OUTPUT_DIR / "ATTRIBUTION.md").write_text(attribution, encoding="utf-8")

    print(f"\nDownloaded {len(records)} documents to {DOCUMENT_DIR}")
    print(f"Dataset version: {DATASET_VERSION}")
    print(f"Source commit: {source_commit}")


if __name__ == "__main__":
    main()
