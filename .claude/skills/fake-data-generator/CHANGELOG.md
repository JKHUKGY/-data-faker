# Changelog

All notable changes to the `fake-data-generator` skill are documented here.

## [0.2.1] - 2026-06-22

### Added
- Business context split into its own `01-{dataset_name}_business_context-cn.md` artifact. ER document is now pure data documentation.
- Dual Python generator files (`04-{dataset_name}_data_generator-cn.py` and `04-{dataset_name}_data_generator.py`); executable code identical, only comments and docstrings differ.
- Phase 6 translation handoff. Skill writes only the four Chinese files; English variants come from the `translate-to-en` skill.
- North American market as the explicit default (US or Canadian fictional company, USD, North American regulators).
- Phase 1 now asks the user to pick from two or three fictional company scenarios with 3 to 5 concrete business problems.
- Embedded business traps requirement in Phase 3 (deliberate distribution skews each tied to a specific SQL query).
- Mermaid ER diagram is a hard requirement (P0 violation if missing).
- Hard code rules: one import per line; SQLite load uses Core API batch loader (one ordered list, one for-loop, one transaction).
- Four content-guidance documents under `references/`: `business_context_guidance.md`, `er_document_guidance.md`, `sql_queries_guidance.md`, `data_generator_guidance.md`.
- `markdown-style` skill must be loaded before authoring any Markdown file.
- SQL queries document requires five content beats per query (business context, tags, 解题思路, SQL, expected result with business conclusion).

### Changed
- Workflow expanded to seven phases (0 through 6). Phase 4 writes only the four Chinese files.
- Per-table and per-query content must be layperson-friendly, not assume domain expertise.
- Output file count went from 3 files to 8 Markdown plus 2 Python files.
- Phase 6 translation is asymmetric. The three Markdown files get a full prose translation (with the `fake-data-generator` skill loaded so the translator understands document structure). The Python file gets a partial translation: comments and docstrings only. Imports, names, table names, SQL strings, and Faker calls remain byte-identical between the Chinese and English variants.
- The hard 1,000-row cap on top-level entity tables was removed. Row counts now follow the complexity tier picked in Phase 2, with no hard per-table cap.
- New performance target on the Python generator: complete the full TSV plus SQLite build in under one minute even for the Large tier.
- The four artifact files now carry a numeric prefix from `01-` to `04-`: `01-{dataset_name}_business_context-cn.md`, `02-{dataset_name}_er_document-cn.md`, `03-{dataset_name}_sql_queries-cn.md`, `04-{dataset_name}_data_generator-cn.py`. The same prefix applies to the English variants. The dataset folder now sorts in the order a reader follows. The `NN_` prefix inside `data/` (TSV ordering) is a separate convention and uses an underscore.

### Removed
- Old fill-in templates (`data_generator_template*.py`, `er_document_template*.md`, `sql_queries_template*.md`). Replaced by content-guidance documents.

## [0.1.1] - 2026-04-13

Initial release.

For reference, the 0.1.1 spec produced three files per dataset (`_data_generator.py`, `_er_document.md`, `_sql_queries.md`) in a single language chosen at run time. Authoring used fill-in templates with Chinese and English variants. The workflow had six phases (Phase 0 through 5) and Markdown files were written first, then the Python file. Business context lived as one section inside the ER document. Distributions were described but not framed as deliberately embedded analytical traps. No market default was set, no Mermaid diagram was strictly required, and no `translate-to-en` handoff existed.
