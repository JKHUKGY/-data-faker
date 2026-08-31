# -*- coding: utf-8 -*-

"""
CLI: regenerate ``dataset/INDEX-cn.md`` and ``dataset/INDEX.md`` from every
dataset's one-line summary artifact.

Thin wrapper around ``ai_datafaker_pro.update_dataset_index``, which holds the
actual logic. Every run is a full scan of ``dataset/`` plus a full regenerate —
there are no arguments and nothing to update selectively, because reading the
summaries is deterministic. A dataset with no summary yet is skipped with a
warning, not an error.

Usage:

    uv run python update_dataset_index.py
"""

from __future__ import annotations

from ai_datafaker_pro.paths import path_enum
from ai_datafaker_pro.update_dataset_index import INDEX_CN
from ai_datafaker_pro.update_dataset_index import INDEX_EN
from ai_datafaker_pro.update_dataset_index import build_index

ROOT = path_enum.dir_project_root


def main() -> None:
    result = build_index()
    print(f"INDEX-cn.md: {result.cn_count} entries -> {INDEX_CN.relative_to(ROOT)}")
    print(f"INDEX.md:    {result.en_count} entries -> {INDEX_EN.relative_to(ROOT)}")
    for warning in result.warnings:
        print(f"  [warning] {warning}")


if __name__ == "__main__":
    main()
