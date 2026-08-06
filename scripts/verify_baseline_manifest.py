#!/usr/bin/env python3
"""验证派生的 GitHub Actions 中文 Baseline 选择结果。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from build_github_actions_baseline_manifest import (
    BASELINE_MANIFEST_PATH,
    CORPUS_DIR,
    CORPUS_PROFILE_PATH,
    EXCLUDED_DOCUMENT_IDS,
    SOURCE_MANIFEST_PATH,
    build_outputs,
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    errors: list[str] = []
    source_manifest = read_json(SOURCE_MANIFEST_PATH)
    baseline_manifest = read_json(BASELINE_MANIFEST_PATH)
    corpus_profile = read_json(CORPUS_PROFILE_PATH)
    expected_profile, expected_baseline = build_outputs()

    if baseline_manifest != expected_baseline:
        errors.append(
            "baseline_manifest.json does not match the deterministic generator output"
        )
    if corpus_profile != expected_profile:
        errors.append(
            "reports/corpus_profile.json does not match the deterministic generator output"
        )

    source_documents = source_manifest["documents"]
    baseline_documents = baseline_manifest["documents"]
    source_ids = [document["document_id"] for document in source_documents]
    baseline_ids = [document["document_id"] for document in baseline_documents]

    if len(source_ids) != len(set(source_ids)):
        errors.append("source manifest contains duplicate document_id values")
    if len(baseline_ids) != len(set(baseline_ids)):
        errors.append("baseline manifest contains duplicate document_id values")
    if set(source_ids) != set(baseline_ids):
        errors.append("baseline manifest has missing or unexpected document_id values")

    included_ids = {
        document["document_id"]
        for document in baseline_documents
        if document["baseline_included"]
    }
    excluded_ids = {
        document["document_id"]
        for document in baseline_documents
        if not document["baseline_included"]
    }

    if included_ids & excluded_ids:
        errors.append("included and excluded document sets overlap")
    if included_ids | excluded_ids != set(source_ids):
        errors.append("included and excluded sets do not cover all source documents")
    if excluded_ids != EXCLUDED_DOCUMENT_IDS:
        errors.append("excluded document set does not match ADR-002")
    if len(included_ids) != 29:
        errors.append(f"expected 29 included documents, found {len(included_ids)}")
    if len(excluded_ids) != 4:
        errors.append(f"expected 4 excluded documents, found {len(excluded_ids)}")

    source_by_id = {document["document_id"]: document for document in source_documents}
    for document in baseline_documents:
        source = source_by_id[document["document_id"]]
        raw_path = CORPUS_DIR / source["relative_path"]
        if not raw_path.is_file():
            errors.append(f"missing raw document: {raw_path}")
            continue
        raw_content = raw_path.read_bytes()
        raw_sha256 = hashlib.sha256(raw_content).hexdigest()
        if raw_sha256 != source["sha256"]:
            errors.append(f"raw sha256 mismatch: {raw_path}")
        if document["source_sha256"] != source["sha256"]:
            errors.append(f"baseline source_sha256 mismatch: {document['document_id']}")
        if document["source_relative_path"] != source["relative_path"]:
            errors.append(f"baseline source path mismatch: {document['document_id']}")

        if not document["baseline_included"]:
            if document["language_profile"] != "english_dominant":
                errors.append(
                    f"excluded document is not english_dominant: {document['document_id']}"
                )
            if not document["exclusion_reason"]:
                errors.append(
                    f"excluded document has no reason: {document['document_id']}"
                )
            if not document["future_experiment"]:
                errors.append(
                    f"excluded document has no future experiment: {document['document_id']}"
                )

    if baseline_manifest["document_count"] != len(baseline_documents):
        errors.append("baseline document_count does not match documents list")
    if baseline_manifest["included_document_count"] != len(included_ids):
        errors.append("included_document_count is incorrect")
    if baseline_manifest["excluded_document_count"] != len(excluded_ids):
        errors.append("excluded_document_count is incorrect")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"source_dataset={source_manifest['dataset_version']}")
    print(f"baseline_version={baseline_manifest['baseline_version']}")
    print(f"source_documents={len(source_ids)}")
    print(f"baseline_included={len(included_ids)}")
    print(f"baseline_excluded={len(excluded_ids)}")
    print("duplicate_document_ids=0")
    print("missing_document_ids=0")
    print("raw_hash_changes=0")
    print("generated_metadata_drift=0")
    print("status=valid")


if __name__ == "__main__":
    main()
