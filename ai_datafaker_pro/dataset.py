# -*- coding: utf-8 -*-

"""
Dataset domain model.

A `Dataset` represents one folder under `dataset/` produced by the
`fake-data-generator` skill. It is layout-agnostic: legacy (0.1.1) and
current (0.2.1) layouts share the same folder name convention
``{industry}_{use_case}_{complexity}`` but use different file naming
conventions inside.

`Dataset.from_name(name)` resolves the directory and globs the four
canonical artifacts up front, storing every found path (or ``None``)
as a plain attribute on the frozen dataclass. No lazy work: by the
time the caller has a `Dataset` instance, every path is known.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import path_enum


def _glob_one(directory: Path, pattern: str) -> Path | None:
    """Return the single absolute path matching ``pattern`` under ``directory``.

    Returns None when zero files match. Raises RuntimeError when more
    than one matches (callers expect at most one of each canonical
    artifact per dataset directory).
    """
    matches = sorted(directory.glob(pattern))
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"expected at most 1 file matching {pattern!r} in {directory}, "
            f"found {len(matches)}: {[p.name for p in matches]}"
        )
    return matches[0].resolve()


def _glob_legacy_generator(directory: Path) -> Path | None:
    """Find the legacy single-language Python generator, if present.

    Looks for ``*_data_generator.py`` while excluding the
    ``*_data_generator-cn.py`` variant that belongs to the current spec.
    """
    matches = [
        p for p in sorted(directory.glob("*_data_generator.py"))
        if not p.name.endswith("-cn.py")
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"expected at most 1 legacy '*_data_generator.py' in {directory}, "
            f"found {len(matches)}: {[p.name for p in matches]}"
        )
    return matches[0].resolve()


@dataclass(frozen=True)
class Dataset:
    """A dataset folder, fully resolved at construction time.

    Construct via `Dataset.from_name(name)`. Every attribute is set
    once and never recomputed. Optional artifacts (e.g. a legacy
    generator that only exists in 0.1.1 layouts) are typed as
    ``Path | None``; callers can branch on ``is_legacy_layout`` or on
    the presence of a specific path.

    Attributes:
        name: Folder name under ``dataset/``, e.g.
            ``"b2b_saas_demand_generation_high"``.
        dataset_dir: Absolute path to the dataset directory.
        data_dir: Absolute path to the ``data/`` subdirectory.
        sqlite_path: Absolute path to ``{name}.sqlite`` (may or may not
            exist on disk yet; this is the conventional location).
        business_context_cn: Absolute path to ``*business_context-cn.md``,
            or None if the file is not present (typical for legacy layouts).
        er_document_cn: Absolute path to ``*er_document-cn.md``, or None.
        sql_queries_cn: Absolute path to ``*sql_queries-cn.md``, or None.
        data_generator_cn: Absolute path to ``*_data_generator-cn.py``,
            or None if the current-spec generator is not present.
        business_context_en: Absolute path to ``*business_context.md``
            (English / no ``-cn`` suffix), or None.
        er_document_en: Absolute path to ``*er_document.md``, or None.
        sql_queries_en: Absolute path to ``*sql_queries.md``, or None.
        data_generator_en: Absolute path to ``*_data_generator.py``
            (English / no ``-cn`` suffix), or None. For 0.1.1 layouts this
            is the single legacy generator; for 0.2.1 it is the English
            counterpart of ``data_generator_cn``.
        data_generator_legacy: Alias of ``data_generator_en`` kept for
            backward compatibility.
        is_legacy_layout: True when the folder looks like 0.1.1 (no
            business context file and a legacy generator is present).
    """

    name: str
    dataset_dir: Path
    data_dir: Path
    sqlite_path: Path
    business_context_cn: Path | None
    er_document_cn: Path | None
    sql_queries_cn: Path | None
    data_generator_cn: Path | None
    business_context_en: Path | None
    er_document_en: Path | None
    sql_queries_en: Path | None
    data_generator_en: Path | None
    data_generator_legacy: Path | None
    is_legacy_layout: bool

    def iter_canonical_artifacts(
        self,
    ) -> list[tuple[str, str, Path]]:
        """List present canonical artifacts as ``(category, language, path)``.

        ``category`` is one of ``"business-context"``, ``"er-document"``,
        ``"sql-queries"``, ``"data-generator"``. ``language`` is ``"cn"``
        or ``"en"``. Missing artifacts are simply omitted. Order matches
        the ``NN-`` ordering of the 0.2.1 layout, with the ``-cn``
        variant emitted before the English variant of the same category.
        """
        items = [
            ("business-context", "cn", self.business_context_cn),
            ("business-context", "en", self.business_context_en),
            ("er-document", "cn", self.er_document_cn),
            ("er-document", "en", self.er_document_en),
            ("sql-queries", "cn", self.sql_queries_cn),
            ("sql-queries", "en", self.sql_queries_en),
            ("data-generator", "cn", self.data_generator_cn),
            ("data-generator", "en", self.data_generator_en),
        ]
        return [(c, lang, p) for c, lang, p in items if p is not None]

    @classmethod
    def from_name(cls, name: str) -> "Dataset":
        """Resolve a dataset by its folder name under ``dataset/``.

        All file globs run here so the returned instance is fully
        populated. The directory itself is required to exist; missing
        artifacts inside it are captured as ``None`` fields.

        Args:
            name: Folder name under ``dataset/``.

        Raises:
            FileNotFoundError: When the dataset directory does not exist.
            RuntimeError: When a canonical glob matches more than one
                file (the directory layout is then ambiguous).
        """
        dataset_dir = (path_enum.dir_project_root / "dataset" / name).resolve()
        if not dataset_dir.exists() or not dataset_dir.is_dir():
            raise FileNotFoundError(
                f"dataset directory does not exist: {dataset_dir}"
            )

        bc = _glob_one(dataset_dir, "*business_context-cn.md")
        er = _glob_one(dataset_dir, "*er_document-cn.md")
        sql = _glob_one(dataset_dir, "*sql_queries-cn.md")
        gen_cn = _glob_one(dataset_dir, "*_data_generator-cn.py")
        bc_en = _glob_one(dataset_dir, "*business_context.md")
        er_en = _glob_one(dataset_dir, "*er_document.md")
        sql_en = _glob_one(dataset_dir, "*sql_queries.md")
        gen_legacy = _glob_legacy_generator(dataset_dir)

        return cls(
            name=name,
            dataset_dir=dataset_dir,
            data_dir=dataset_dir / "data",
            sqlite_path=dataset_dir / f"{name}.sqlite",
            business_context_cn=bc,
            er_document_cn=er,
            sql_queries_cn=sql,
            data_generator_cn=gen_cn,
            business_context_en=bc_en,
            er_document_en=er_en,
            sql_queries_en=sql_en,
            data_generator_en=gen_legacy,
            data_generator_legacy=gen_legacy,
            is_legacy_layout=(bc is None and gen_legacy is not None),
        )
