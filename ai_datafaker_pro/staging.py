# -*- coding: utf-8 -*-

"""
Staging logic for copying dataset artifacts into ``tmp/stage/`` in two
complementary layouts:

1. Per-dataset bundle:

       tmp/stage/dataset/<name>/
         01-<name>_business_context-cn.md   /  01-<name>_business_context.md
         02-<name>_er_document-cn.md        /  02-<name>_er_document.md
         03-<name>_sql_queries-cn.md        /  03-<name>_sql_queries.md
         04-<name>_data_generator-cn.py     /  04-<name>_data_generator.py

2. Per-category roll-up:

       tmp/stage/business-context/      *_business_context.md     (all datasets)
       tmp/stage/business-context-cn/   *_business_context-cn.md
       tmp/stage/er-document/           *_er_document.md
       tmp/stage/er-document-cn/        *_er_document-cn.md
       tmp/stage/sql-queries/           *_sql_queries.md
       tmp/stage/sql-queries-cn/        *_sql_queries-cn.md
       tmp/stage/data-generator/        *_data_generator.py
       tmp/stage/data-generator-cn/     *_data_generator-cn.py

   File names are kept as-is; the ``NN-<dataset_name>_`` prefix already
   makes them unique within a folder. Datasets that pre-date the ``NN-``
   prefix (e.g. one legacy 0.1.1 leftover) land alongside the prefixed
   ones without collision because the dataset name itself differs.

   Everything lands under ``tmp/stage/`` rather than directly under
   ``tmp/`` so this one-shot staging output does not mix with other
   ephemeral files that also live under ``tmp/``.

Sqlite databases and TSV files are not copied; only the 8 canonical
artifacts are. ``tmp/stage/`` is fully owned by this module, nothing
else writes there, so every run calls ``clear_stage()`` first to wipe
the whole tree before repopulating it. That is what keeps stale
per-dataset and per-category folders from renamed or removed datasets
from lingering, rather than any per-folder wipe logic in the
functions below.

This module holds the pure staging logic (no printing, no CLI). See
``stage_datasets_to_tmp.py`` at the project root for the thin CLI wrapper
that drives it.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .dataset import Dataset
from .paths import path_enum

STAGE_BASE = path_enum.dir_tmp / "stage"
DST_PER_DATASET_BASE = STAGE_BASE / "dataset"
DST_CATEGORY_BASE = STAGE_BASE

BULLET_RE = re.compile(r"^\s*-\s*\[([^\]]+)\]\(([^)]+)\)")

EXPECTED_ARTIFACT_COUNT = 8

# (category, language) pairs used to materialise the per-category roll-up
# folders. The folder name is "<category>" for English and
# "<category>-cn" for Chinese, matching the ``tmp/stage/`` convention.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("business-context", "cn"),
    ("business-context", "en"),
    ("er-document", "cn"),
    ("er-document", "en"),
    ("sql-queries", "cn"),
    ("sql-queries", "en"),
    ("data-generator", "cn"),
    ("data-generator", "en"),
)


def category_dir(category: str, language: str) -> Path:
    """Return the per-category destination folder for ``(category, language)``."""
    suffix = "-cn" if language == "cn" else ""
    return DST_CATEGORY_BASE / f"{category}{suffix}"


def clear_stage() -> None:
    """Wipe ``tmp/stage/`` entirely, if it exists.

    ``tmp/stage/`` holds nothing but this module's output, so a full
    wipe up front is safe and is the single place staleness is dealt
    with. Call this once at the start of a run, before
    ``stage_dataset()`` or ``stage_categories()``.
    """
    if STAGE_BASE.exists():
        shutil.rmtree(STAGE_BASE)


def parse_dataset_names(index_path: Path) -> list[str]:
    """Pull dataset names out of the INDEX bullet markers (``- [name](name): …``)."""
    names: list[str] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        m = BULLET_RE.match(line)
        if m:
            names.append(m.group(2).strip())
    return names


def stage_dataset(dataset: Dataset) -> tuple[int, list[str]]:
    """Copy one dataset's canonical artifacts into ``tmp/stage/dataset/<name>/``.

    Assumes ``clear_stage()`` already ran this cycle, so the destination
    folder does not exist yet; this only creates and populates it.

    Returns ``(copied_count, missing_categories)`` where ``missing_categories``
    is a list of ``"<category>-<language>"`` strings for artifacts that
    are absent from the source folder.
    """
    dst_dir = DST_PER_DATASET_BASE / dataset.name
    dst_dir.mkdir(parents=True, exist_ok=True)

    present = {(c, lang) for c, lang, _ in dataset.iter_canonical_artifacts()}
    missing = [
        f"{c}-{lang}" for c, lang in CATEGORIES if (c, lang) not in present
    ]

    copied = 0
    for _, _, src in dataset.iter_canonical_artifacts():
        shutil.copy2(src, dst_dir / src.name)
        copied += 1
    return copied, missing


def stage_categories(datasets: list[Dataset]) -> dict[tuple[str, str], int]:
    """Roll every dataset's artifacts up into shared ``tmp/stage/<category>/`` folders.

    Assumes ``clear_stage()`` already ran this cycle, so each category
    folder does not exist yet; this only creates and populates them.
    Returns a mapping from ``(category, language)`` to the count of
    files copied into that folder.
    """
    for category, language in CATEGORIES:
        folder = category_dir(category, language)
        folder.mkdir(parents=True, exist_ok=True)

    counts: dict[tuple[str, str], int] = {key: 0 for key in CATEGORIES}
    for dataset in datasets:
        for category, language, src in dataset.iter_canonical_artifacts():
            folder = category_dir(category, language)
            shutil.copy2(src, folder / src.name)
            counts[(category, language)] += 1
    return counts
