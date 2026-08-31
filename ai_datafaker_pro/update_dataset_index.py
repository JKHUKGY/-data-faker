# -*- coding: utf-8 -*-

"""
Dataset index generation.

Scan every dataset under ``dataset/`` and regenerate ``dataset/INDEX-cn.md``
and ``dataset/INDEX.md`` from scratch, purely from each dataset's one-line
summary files written by the ``run-summarize-and-translate`` skill:

    dataset/<name>/00-<name>_summary-cn.md   ->  dataset/INDEX-cn.md
    dataset/<name>/00-<name>_summary.md      ->  dataset/INDEX.md

Reading a summary is a deterministic act, so there is nothing to "update" or
merge: every run is a full scan plus a full regenerate. Each INDEX file is
rebuilt from a string template — a header followed by one
``- [<name>](<name>): <summary>`` bullet per dataset, sorted by name.

The only defensive move is around a missing summary: a dataset whose summary
file can't be located (still mid-draft, or not translated yet) is skipped with
a warning rather than an error, and simply doesn't appear in the regenerated
index. A full regenerate therefore always mirrors exactly which summary files
exist on disk right now — no stale bullets can survive.

Pure logic, no printing. See ``update_dataset_index.py`` at the project root
for the thin CLI wrapper that drives it and prints its result, the same way
``stage_datasets_to_tmp.py`` drives ``staging.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from .paths import path_enum

DATASET_DIR = path_enum.dir_project_root / "dataset"
INDEX_CN = DATASET_DIR / "INDEX-cn.md"
INDEX_EN = DATASET_DIR / "INDEX.md"
HEADER = "# Dataset Index"

BULLET_TEMPLATE = "- [{name}]({name}): {summary}"


@dataclass
class IndexResult:
    """Outcome of one :func:`build_index` run, for the caller to report."""

    cn_count: int = 0
    en_count: int = 0
    warnings: list[str] = field(default_factory=list)


def find_summary(dataset_dir: Path, *, cn: bool) -> Path | None:
    """Locate a dataset's Chinese or English summary file via glob, or None.

    ``cn=True`` matches ``*_summary-cn.md``; ``cn=False`` matches
    ``*_summary.md`` while excluding the ``-cn`` variant. Returns the first
    match, or None when the dataset has no such summary yet.
    """
    if cn:
        matches = sorted(dataset_dir.glob("*_summary-cn.md"))
    else:
        matches = [
            p for p in sorted(dataset_dir.glob("*_summary.md"))
            if not p.name.endswith("-cn.md")
        ]
    return matches[0] if matches else None


def read_summary_line(path: Path) -> str | None:
    """Read a summary file as one stripped line, or None if empty / multi-line."""
    text = path.read_text(encoding="utf-8").strip()
    if not text or "\n" in text:
        return None
    return text


def render_index(bullets: dict[str, str]) -> str:
    """Render the whole INDEX file from a string template: header + sorted bullets."""
    lines = [HEADER, ""]
    lines.extend(bullets[name] for name in sorted(bullets))
    return "\n".join(lines) + "\n"


def iter_dataset_names() -> list[str]:
    """Every direct subdirectory of ``dataset/``, sorted."""
    return sorted(
        p.name
        for p in DATASET_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def build_index() -> IndexResult:
    """Full scan of ``dataset/``, regenerate both INDEX files from summaries.

    Every dataset that has a valid one-line summary contributes a bullet; a
    dataset missing (or with a malformed) summary is skipped with a warning.
    Both INDEX files are then written fresh from the string template. Returns an
    :class:`IndexResult` for the caller to print.
    """
    result = IndexResult()
    cn_bullets: dict[str, str] = {}
    en_bullets: dict[str, str] = {}

    for name in iter_dataset_names():
        dataset_dir = DATASET_DIR / name
        for cn, bullets, lang in (
            (True, cn_bullets, "cn"),
            (False, en_bullets, "en"),
        ):
            path = find_summary(dataset_dir, cn=cn)
            if path is None:
                result.warnings.append(f"{name}: no {lang} summary file found, skipped")
                continue
            summary = read_summary_line(path)
            if summary is None:
                result.warnings.append(
                    f"{name}: {lang} summary {path.name} is empty or not one line, skipped"
                )
                continue
            bullets[name] = BULLET_TEMPLATE.format(name=name, summary=summary)

    INDEX_CN.write_text(render_index(cn_bullets), encoding="utf-8")
    INDEX_EN.write_text(render_index(en_bullets), encoding="utf-8")
    result.cn_count = len(cn_bullets)
    result.en_count = len(en_bullets)
    return result
