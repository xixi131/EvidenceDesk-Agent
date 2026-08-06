#!/usr/bin/env python3
"""根据 Manifest 验证冻结的 GitHub Actions 语料。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = manifest["documents"]
    errors: list[str] = []

    if manifest["document_count"] != len(documents):
        errors.append("manifest document_count does not match documents list")

    for document in documents:
        path = CORPUS_DIR / document["relative_path"]
        if not path.is_file():
            errors.append(f"missing: {path}")
            continue
        content = path.read_bytes()
        if len(content) != document["byte_size"]:
            errors.append(f"byte_size mismatch: {path}")
        if hashlib.sha256(content).hexdigest() != document["sha256"]:
            errors.append(f"sha256 mismatch: {path}")
        if not content.decode("utf-8").startswith("# "):
            errors.append(f"missing H1 heading: {path}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"dataset_version={manifest['dataset_version']}")
    print(f"source_commit={manifest['source_repository_commit']}")
    print(f"document_count={len(documents)}")
    print(f"total_bytes={sum(item['byte_size'] for item in documents)}")
    print("status=valid")


if __name__ == "__main__":
    main()
