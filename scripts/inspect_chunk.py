#!/usr/bin/env python3
"""按 Chunk ID 查看一次切块结果。"""

import argparse
from pathlib import Path

from evidence_desk.rag.chunking.chunk_inspector import (
    find_chunk,
    format_chunk_for_review,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_ROOT = PROJECT_ROOT / "data" / "knowledge_base" / "github_actions_zh_v1"


def main() -> None:
    """读取参数并打印 Chunk 追溯信息和正文。"""

    parser = argparse.ArgumentParser(description="按 Chunk ID 查看切块正文")
    parser.add_argument("chunk_id", help="要查看的 Chunk ID")
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_CORPUS_ROOT,
        help="语料根目录",
    )
    args = parser.parse_args()

    chunk, source_relative_path = find_chunk(args.corpus_root, args.chunk_id)
    print(format_chunk_for_review(chunk, source_relative_path))


if __name__ == "__main__":
    main()
