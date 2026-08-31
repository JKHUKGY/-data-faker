# -*- coding: utf-8 -*-

"""
CLI: stage every dataset listed in ``dataset/INDEX-cn.md`` into ``tmp/stage/``.

Thin wrapper around ``ai_datafaker_pro.staging``, which holds the actual
copy logic. See that module's docstring for the two output layouts
(per-dataset bundle and per-category roll-up).

Usage:

    uv run python stage_datasets_to_tmp.py
"""

from __future__ import annotations

from ai_datafaker_pro.dataset import Dataset
from ai_datafaker_pro.paths import path_enum
from ai_datafaker_pro.staging import DST_CATEGORY_BASE
from ai_datafaker_pro.staging import DST_PER_DATASET_BASE
from ai_datafaker_pro.staging import EXPECTED_ARTIFACT_COUNT
from ai_datafaker_pro.staging import category_dir
from ai_datafaker_pro.staging import clear_stage
from ai_datafaker_pro.staging import parse_dataset_names
from ai_datafaker_pro.staging import stage_categories
from ai_datafaker_pro.staging import stage_dataset

ROOT = path_enum.dir_project_root
INDEX_FILE = ROOT / "dataset" / "INDEX-cn.md"


def main() -> None:
    clear_stage()
    names = parse_dataset_names(INDEX_FILE)
    print(f"Found {len(names)} datasets in {INDEX_FILE.relative_to(ROOT)}")
    DST_PER_DATASET_BASE.mkdir(parents=True, exist_ok=True)

    datasets: list[Dataset] = []
    total_copied = 0
    for name in names:
        print(f"- {name}")
        try:
            dataset = Dataset.from_name(name)
        except FileNotFoundError as e:
            print(f"  [skip] {e}")
            continue
        datasets.append(dataset)
        copied, missing = stage_dataset(dataset)
        print(f"    copied {copied}/{EXPECTED_ARTIFACT_COUNT} files")
        for key in missing:
            print(f"    [missing] {key}")
        total_copied += copied

    print(
        f"\nPer-dataset done. {total_copied} files copied into "
        f"{DST_PER_DATASET_BASE.relative_to(ROOT)}/"
    )

    print(f"\nRolling up into per-category folders under {DST_CATEGORY_BASE.relative_to(ROOT)}/")
    counts = stage_categories(datasets)
    for (category, language), n in counts.items():
        folder = category_dir(category, language).relative_to(ROOT)
        print(f"  {folder}/  ({n} files)")


if __name__ == "__main__":
    main()
