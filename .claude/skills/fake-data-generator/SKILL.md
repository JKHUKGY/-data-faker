---
name: fake-data-generator
description: >
  Generate realistic, business-meaningful fake data for any vertical industry.
  Use when the user needs mock datasets for demos, testing, teaching, or prototyping.
  Produces TSV files, SQLite database, Python generator scripts, ER documentation, and SQL queries reference.
argument-hint: "[dataset_name]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion, Skill
---

# Fake Data Generator Agent

You help users create realistic, business-meaningful mock datasets for any vertical industry. Each generation task produces one dataset that tells the data story of one fictional company solving real business problems.

The default market is North America, meaning the United States and Canada. The fictional company is based there, the currency is USD, the customer geographies are North American, and the regulatory references are American or Canadian. The Chinese narrative files use Chinese only as the language of narration. The business they describe is still North American.

Treat the business-first framing as load-bearing. The schema, the data, and the queries all exist to serve the chosen fictional company's stated business problems. A dataset that reads like an abstract data model misses the point.

Before authoring any Markdown file in a dataset, invoke the `markdown-style` skill so all produced documents follow the project's writing conventions.

---

## 1. What gets produced

Each generation task produces one dataset. A dataset has a name following the convention `{industry}_{use_case}_{complexity}` in snake_case, lives in `dataset/{dataset_name}/`, and contains the artifacts described below.

### Naming convention

| Component | Source | Example |
|-----------|--------|---------|
| `{industry}` | Level 2 or Level 3 name from `industry_catelog.md` | `fintech`, `medical_devices`, `b2b_saas` |
| `{use_case}` | Specific business scenario in snake_case | `smb_lending_pipeline`, `orthopedic_implant_tracking` |
| `{complexity}` | Complexity tier | `low`, `medium`, `high`, `large` |

### File outputs

Each dataset folder ends up with eight documentation files (four Chinese authored plus four English translations), two Python generator files (Chinese and English comment variants), and the generated SQLite database plus TSV data files.

This skill writes only the Chinese files during the main authoring pass. The English files come from a later translation pass that uses the `translate-to-en` skill.

Each of the four artifact files carries a numeric prefix from `01-` to `04-` so the files sort in the logical order a reader will follow: business context first, then ER document, then SQL queries, then the Python generator.

Files written by this skill during the authoring pass:

- `01-{dataset_name}_business_context-cn.md`
- `02-{dataset_name}_er_document-cn.md`
- `03-{dataset_name}_sql_queries-cn.md`
- `04-{dataset_name}_data_generator-cn.py`

Files produced later by the `translate-to-en` skill:

- `01-{dataset_name}_business_context.md`
- `02-{dataset_name}_er_document.md`
- `03-{dataset_name}_sql_queries.md`
- `04-{dataset_name}_data_generator.py`

Files produced when the Python generator runs:

- `{dataset_name}.sqlite`
- `data/{NN}_{table_name}.tsv` files in topological order

The `NN_` prefix inside `data/` (such as `01_industry.tsv`) is a separate convention for TSV file ordering inside the database and uses an underscore separator. The artifact prefix at the top level uses a hyphen separator and applies only to the four documentation and generator files.

The two Python files share identical executable code. They differ only in the language used for comments and docstrings. The Chinese variant is what this skill produces. Variable names, function names, table names, SQL strings, and Faker calls remain in English in both files.

---

## 2. Reference files

Each guidance file describes the required content for one of the produced artifacts. The guidance is not a fill-in template. Sections, headings, and depth stay flexible as long as every required content beat is present.

| Reference | Purpose |
|-----------|---------|
| `references/industry_catelog.md` | Three-level industry classification, the catalog users browse for ideas |
| `references/industry_catelog_cn.md` | Chinese variant of the catalog |
| `references/industry_catelog_en.md` | English variant of the catalog |
| `references/business_context_guidance.md` | What goes in the business context file |
| `references/er_document_guidance.md` | What goes in the ER document |
| `references/sql_queries_guidance.md` | What goes in the SQL queries document |
| `references/data_generator_guidance.md` | Hard rules and patterns for the Python generator |

Open a guidance file when you start drafting the corresponding artifact, not before.

---

## 3. Workflow

The workflow runs seven phases. The first three are interactive and require user confirmation. Phase 3 designs the schema. Phase 4 writes the four Chinese files. Phase 5 executes and validates. Phase 6 hands off translation to the `translate-to-en` skill.

The phase numbers below are kept as is for continuity with prior conventions.

### Phase 0. Industry classification

Industry confirmation determines the `{industry}` prefix and anchors everything that follows.

Read `references/industry_catelog_cn.md` or `references/industry_catelog_en.md` based on the user's language preference. From the user's input, infer two to four candidate Level 2 or Level 3 entries with their snake_case prefixes and present them. Pause for the user to confirm via `AskUserQuestion`. Record the confirmed prefix.

### Phase 1. Fictional company and project framing

This is where the dataset earns its story. Brainstorm two or three distinct fictional company scenarios for the confirmed industry. Each scenario sketches:

- A fictional company name. Never reuse a real public company name.
- A North American city or region (United States or Canada).
- What they sell and how they make money in one sentence.
- Scale numbers (employees, revenue, customer count, all order of magnitude).
- The use case the dataset supports as a one-line name that becomes `{use_case}`.
- Three to five concrete business problems the data should help answer.
- The role the user plays inside this company (intern, full-time analyst, BI engineer, consultant, founding data hire, and so on).

Present the scenarios via `AskUserQuestion`. After the user picks one (or describes their own), expand the chosen scenario into a draft business context outline. Confirm any remaining ambiguity before moving on. Record `{use_case}` as snake_case.

### Phase 2. Complexity selection

Present the four complexity tiers and wait for the user to pick via `AskUserQuestion`.

| Tier | Tables | Total rows | Notes |
|------|--------|------------|-------|
| Low | 4 to 6 | a few thousand | Core entities only, mostly 1:N relationships |
| Medium | 8 to 12 | tens of thousands | Enum tables, some M:N, lifecycle states |
| High | 13 to 18 | around 200k | Computed rollups, time-series fan-out |
| Large | 18 and up | a million plus | Production scale, multiple domain clusters |

Finalize the dataset name as `{industry}_{use_case}_{complexity}`. Create `dataset/{dataset_name}/` and `dataset/{dataset_name}/data/`.

### Phase 3. Schema design with embedded business traps

Design the schema around the stated business problems. For each business problem:

1. Identify which entities and columns are needed to answer it.
2. Identify the business trap, meaning the deliberate distribution skew or correlation that a SQL query can surface to demonstrate the problem. A canonical example is Grade C loans priced as if they default at 6 percent but actually defaulting at 10 percent.
3. Write down the trap's expected magnitude. The Python generator must produce this magnitude. The SQL query must surface it. The ER document and business context file must document it.

Then design all tables (columns, types, constraints, foreign keys), topologically order them with FK dependencies first, and identify all business logic constraints. The constraints cover temporal ordering, computed fields, referential scoping that the DDL cannot enforce, and distribution targets.

### Phase 4. Chinese authoring pass

Write the four Chinese-narrative files together. They reference each other and should be iterated as a single coherent unit. The English versions are not written in this phase. They come from the translation pass in Phase 6.

Files to author in this phase:

1. `01-{dataset_name}_business_context-cn.md` following `references/business_context_guidance.md`.
2. `02-{dataset_name}_er_document-cn.md` following `references/er_document_guidance.md`. It must include a Mermaid ER diagram.
3. `03-{dataset_name}_sql_queries-cn.md` following `references/sql_queries_guidance.md`.
4. `04-{dataset_name}_data_generator-cn.py` following `references/data_generator_guidance.md`. Code is English. Comments and docstrings are Chinese.

The Chinese files use a Chinese narrative voice. Business terminology stays in its English jargon form (such as ARR, MRR, DSO, FICO, DRG, CPL). The fictional company, customers, geographies, and regulatory references are North American.

Treat the per-table descriptions in the ER document and the per-query descriptions in the SQL queries document as teaching content. Assume the reader is a smart layperson, not a domain expert. Explain what each table does in the business and what each query helps the analyst conclude. The business context file carries the heaviest jargon-to-layman explanations, but the ER and SQL documents still need to be readable to someone who only just read the business context.

Iterate across the four files until they tell one coherent story. The business context names a problem, the ER document embeds the corresponding trap, the generator produces it, and the SQL query surfaces it.

### Phase 5. Execution and validation

Install dependencies if missing with `uv pip install faker polars sqlalchemy`. Run the generator with `python dataset/{dataset_name}/04-{dataset_name}_data_generator-cn.py`. Confirm all expected TSV files exist with the expected row counts and that the SQLite database has all tables.

Then verify the embedded business traps are actually present in the generated data. Use `sqlite3` to spot-check two or three of the most important traps. If the documented Grade C default rate is around 10 percent and the actual data shows 6 percent, the generator is wrong. Fix it and re-run. Accept a tolerance of one to two absolute percentage points for percentage traps and roughly ten percent relative for count or amount traps.

When everything validates, present the dataset folder to the user and confirm they are satisfied with the Chinese files before moving to translation.

### Phase 6. Translation handoff

Run this phase only when the user explicitly signs off on the Chinese files.

Invoke the `translate-to-en` skill on each of the four Chinese files in turn. The translation skill produces:

- `01-{dataset_name}_business_context.md` from `01-{dataset_name}_business_context-cn.md`.
- `02-{dataset_name}_er_document.md` from `02-{dataset_name}_er_document-cn.md`.
- `03-{dataset_name}_sql_queries.md` from `03-{dataset_name}_sql_queries-cn.md`.
- `04-{dataset_name}_data_generator.py` from `04-{dataset_name}_data_generator-cn.py`.

The three Markdown files get a full prose translation. The fake-data-generator skill should be loaded during this step so the translator understands the structure of the documents (business context beats, ER document beats, SQL query five-part shape).

The Python file is a partial translation. Only the comments and docstrings get rewritten in English. Everything else (imports, variable names, function names, table names, SQL string literals, Faker calls, ORM model class names) stays byte-identical to the Chinese variant. After translation, running `diff` on the two `.py` files should show changes only inside `"""..."""` blocks and `#` comment lines.

When this phase finishes, the dataset has eight Markdown files plus two Python files plus the SQLite and TSV outputs.

If the user has not signed off on the Chinese files, skip this phase entirely.

---

## 4. Hard code standards

These rules apply to both Python files. The full detail and a Core API loader template live in `references/data_generator_guidance.md`.

- SQLAlchemy 2.0 ORM style using `DeclarativeBase`, `Mapped`, and `mapped_column`.
- One import per line. Multi-import statements such as `from datetime import date, datetime` are forbidden. Split into one line per name.
- Default `FAKER_LOCALE = "en_US"`.
- Seeded RNG with `RANDOM_SEED = 42` applied to `random.seed` and `Faker.seed`.
- A `REFERENCE_DATE` constant for any "today" or "current snapshot" semantics. Never call `datetime.now()` or `date.today()` in generator logic.
- A module docstring that lists every embedded business trap by name.
- A Business Calibration Constants section above the ORM models, with a WHY comment on every weight, probability, and threshold.
- The `create_sqlite_database` function uses the Core API batch loader pattern: one ordered list of `(tsv_basename, Table)` pairs, one for-loop, one `engine.begin()` transaction.
- Idempotent operation. The TSV generator deletes prior TSV files first. The database builder deletes the prior SQLite file first.
- Performance target: the full generator (TSV plus SQLite build) should finish in under one minute even for the Large complexity tier. Use polars vectorized operations where natural and rely on the Core API batch loader for inserts. No need for aggressive optimization; the goal is a single-digit-minute build at worst, well under one minute on Large in most cases.

---

## 5. SQL queries requirements

The SQL queries document defaults to 20 queries. The acceptable range is 16 to 24 if the business logic naturally clusters differently.

Each query carries five content beats: a business context paragraph, tags for category, difficulty, and role, a 解题思路 (approach) section, the SQL code itself, and an expected result with a business conclusion. Every query references the `REFERENCE_DATE` as a literal date string rather than `DATE('now')`. Every query maps back to a business problem stated in the business context file.

Treat the SQL queries document as a teaching artifact. The audience is an intern who has read the business context file and the ER document and is about to be assigned the queries by a manager. The 解题思路 section walks the intern through the approach before they see the SQL. The expected result section explains both the result columns and what the analyst should do with the numbers.

Full content guidance lives in `references/sql_queries_guidance.md`.

---

## 6. Constraints

- Never skip Phase 0, 1, or 2 interactive confirmations. The dataset name and business framing must be agreed up front.
- Row counts follow the complexity tier table in Phase 2. There is no hard per-table cap; entity tables can naturally exceed thousands of rows when the chosen tier and business call for it.
- Never reuse a real public company name for the fictional company.
- Always default to a North American market unless the user explicitly asks for a different region.
- Always invoke the `markdown-style` skill before authoring any Markdown file.
- Always follow the naming convention `{industry}_{use_case}_{complexity}`.
- Always write the four Chinese files (three Markdown plus one Python) before any English translation.
- Always include a Mermaid ER diagram in `02-{dataset_name}_er_document-cn.md`.
- Always validate FK integrity, row counts, and embedded traps before declaring done.
- Always apply the hard code standards to the Python file.
- Always hand off English translation to the `translate-to-en` skill. Do not author English files directly.
