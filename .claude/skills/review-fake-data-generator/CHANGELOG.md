# Changelog

All notable changes to the `review-fake-data-generator` skill are documented here.

## [0.2.1] - 2026-06-22

### Added
- Stage 1 added as a dedicated review of the new `01-{dataset_name}_business_context-cn.md` artifact. Review protocol expanded from three stages to four.
- Cardinal review principle: polish, do not redesign. Flag P0 only on serious contradictions with industry common sense, queries the data cannot answer, distribution claims the generator does not produce, or schema gaps the queries assume.
- Live SQLite verification in Stage 4. Reviewer runs `sqlite3` queries against the generated database to confirm documented business traps actually exist, with acceptance thresholds (plus or minus 1.5pp for percentage claims, plus or minus 10 percent for absolute claims).
- Mermaid ER diagram presence check as P0 in Stage 2.
- North American market sanity check as P0 (flag RMB amounts, Chinese cities, Chinese regulators in sample data).
- Hard code rules check in Stage 4a: single-import-per-line, Core API loader pattern, `REFERENCE_DATE` constant, Business Calibration Constants with WHY comments.
- Legacy format detection. Datasets in the old 3-file format are recognized and the reviewer offers best-effort review or stop.
- `Bash(sqlite3 *)`, `Bash(python *)`, `Bash(uv *)` added to allowed-tools for live verification.

### Changed
- Source of truth narrowed to the four Chinese files (`01-{dataset_name}_business_context-cn.md`, `02-{dataset_name}_er_document-cn.md`, `03-{dataset_name}_sql_queries-cn.md`, `04-{dataset_name}_data_generator-cn.py`). The English variants are out of scope. The reviewer does not read them and does not propose fixes against them; any issue in the Chinese files will propagate at the next `translate-to-en` pass.
- Artifact filenames now carry numeric prefixes `01-` through `04-` matching the new fake-data-generator spec. The pre-flight check, stage headers, and report templates have been updated accordingly.
- Stage 3 SQL review now checks teaching frame quality: how-to-use intro, 解题思路 section per query, business conclusion in expected result, mapping back to business problems.

## [0.1.1] - 2026-06-02

Initial release.

For reference, the 0.1.1 spec ran a three-stage read-only review (Stage 1 ER document, Stage 2 SQL queries, Stage 3 Python generator) over three artifact files. The reviewer auto-injected the `fake-data-generator` SKILL.md as the "supposed to look like" reference but did not execute the generated SQLite database. Allowed tools were `Read` plus basic Bash read commands (`ls`, `wc`, `head`, `tail`, `cat`, `find`). The final output was a prioritized fix list with an overall verdict. No CN to EN parity check, no live data verification, and no cardinal "polish do not redesign" principle were defined.
