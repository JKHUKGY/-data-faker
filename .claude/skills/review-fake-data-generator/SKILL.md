---
name: review-fake-data-generator
description: External code-review pass over a dataset produced by the fake-data-generator skill. Auto-loads the fake-data-generator skill context, then walks the business context, ER document, SQL queries, and Python generator in strict order. The final stage actively queries the generated SQLite database with sqlite3 or python to verify embedded business traps. Use when the user asks to review, audit, critique, sanity-check, or look at a generated dataset under dataset/.
argument-hint: <dataset-name-or-path>
allowed-tools: Read, Bash(ls *), Bash(wc *), Bash(head *), Bash(tail *), Bash(cat *), Bash(find *), Bash(sqlite3 *), Bash(python *), Bash(uv *)
---

# Review of Fake Data Generator Output

You are acting as an external code-review expert for a dataset produced by the `fake-data-generator` skill. The dataset can target any vertical industry (finance, healthcare, education, logistics, hospitality, manufacturing, media, public sector) and the review checklist applies uniformly. The default market is North America.

You are read-only on the dataset files. Never modify the dataset, the generator, or any other file. You may execute the generated SQLite database via `sqlite3` and run short Python scripts via `python` to inspect the data, since both are non-destructive read paths.

Your output is a structured review report.

---

## 1. Cardinal review principle

Polish the dataset. Do not redesign it.

The author chose the fictional company, the project framing, and the business problems. Treat that foundation as fixed. Surface every issue you find, but flag P0 only for serious self-contradictions with industry common sense, queries the data cannot answer, distribution claims the generator does not produce, or schema gaps the queries assume. Style preferences, alternative org structures, "I would have picked a different industry" comments are out of scope.

The user iterates by polishing. They want sharper details, more realistic distributions, fewer self-contradictions. They do not want a reviewer who proposes "have you considered making this a SaaS company instead." Bring your domain knowledge to bear on the current dataset, not a hypothetical alternative.

---

## 2. Generator framework context (auto-injected)

The block below is the live contents of the `fake-data-generator` SKILL.md. Use it as the source of truth for what the dataset is supposed to look like.

```!
cat ${CLAUDE_SKILL_DIR}/../fake-data-generator/SKILL.md
```

Content-guidance files live under `${CLAUDE_SKILL_DIR}/../fake-data-generator/references/`. Do not load them up front. Open one only when a specific review claim depends on what the guidance prescribes:

- `business_context_guidance.md`
- `er_document_guidance.md`
- `sql_queries_guidance.md`
- `data_generator_guidance.md`
- `industry_catelog.md`, `industry_catelog_cn.md`, `industry_catelog_en.md`

---

## 3. Resolving the target dataset

The user passed `$ARGUMENTS` as the dataset identifier. Resolve it as follows.

1. If `$ARGUMENTS` is empty, run `ls dataset/` and ask the user which dataset to review. Do not guess.
2. If `$ARGUMENTS` matches a dataset name format `{industry}_{use_case}_{complexity}`, the dataset directory is `dataset/$ARGUMENTS/`.
3. If `$ARGUMENTS` is an absolute or relative path to a directory, use it directly.

The four Chinese files below are the source of truth for this review. Each carries a numeric prefix from `01-` to `04-`. They are the only artifacts the review reads, and the only artifacts whose fix suggestions belong in the final punch list.

- `01-{dataset_name}_business_context-cn.md`
- `02-{dataset_name}_er_document-cn.md`
- `03-{dataset_name}_sql_queries-cn.md`
- `04-{dataset_name}_data_generator-cn.py`

The English variants (`01-{dataset_name}_business_context.md`, `02-{dataset_name}_er_document.md`, `03-{dataset_name}_sql_queries.md`, `04-{dataset_name}_data_generator.py`) are produced later by a one-shot `translate-to-en` pass once the Chinese files are signed off. The review never reads the English files and never proposes fixes against them. Any issue found in the Chinese files will propagate to the English files at the next translation pass.

The Python generator's outputs are also needed for the live verification step in Stage 4:

- `{dataset_name}.sqlite`
- `data/{NN}_{table_name}.tsv` (multiple)

---

## 4. Pre-flight check

Confirm the four Chinese files and the SQLite database exist. That is the whole pre-flight.

- If any of the four Chinese files is missing, stop and tell the user which one. The review cannot proceed without all four.
- If the SQLite database is missing but `04-{dataset_name}_data_generator-cn.py` is present, offer to run the generator (`uv run python dataset/{dataset_name}/04-{dataset_name}_data_generator-cn.py`) to build the database. Stage 4 needs it.
- If the dataset is in a legacy format (the three-file shape, or the unprefixed four-file shape from earlier 0.2.x drafts), tell the user the dataset predates the current spec. Offer to review against the old structure as a best effort, or to stop. Do not pretend a legacy format meets the current spec.

---

## 5. Domain calibration

Before Stage 1, identify the dataset's industry and use case from the dataset name and from the Chinese business context file. Briefly recall what a real North American company in that space looks like (nouns, verbs, money flow, regulatory shape, typical jargon). The review judges the artifacts against that mental model.

The default market is North America. If sample data contains RMB amounts, Chinese cities, Chinese regulators, or other clear non-North-American markers, flag this as a P0 issue.

---

## 6. Review protocol

Conduct the review in four sequential stages. Finish and emit the Stage N report before reading the artifact for Stage N+1. The phased order catches design-level issues before drowning in implementation detail.

The four stages map onto the four Chinese source-of-truth files:

- Stage 1: `01-{dataset_name}_business_context-cn.md`.
- Stage 2: `02-{dataset_name}_er_document-cn.md`, including the Mermaid diagram.
- Stage 3: `03-{dataset_name}_sql_queries-cn.md`.
- Stage 4: `04-{dataset_name}_data_generator-cn.py` plus live SQLite verification against the generated database.

The English variants are out of scope. Do not read them, do not compare against them, and do not include them in fix recommendations.

---

## 7. Stage 1. Business context review

Read `01-{dataset_name}_business_context-cn.md` first. This file frames everything else. Apply the cardinal principle: polish, do not redesign.

Evaluate as a domain expert for the dataset's industry would.

1. **North American context.** Is the fictional company actually based in the United States or Canada? Are the currency, cities, regulators, holidays, and units North American? Flag anything that is not.
2. **Company plausibility.** Is the company plausible for this industry? Right scale, right model, right geography? Flag serious self-contradictions (such as "a 10-person seed-stage startup with 500 enterprise customers"). Style nits are not issues unless they cause downstream incoherence.
3. **Revenue model concreteness.** Does the "how they make money" section actually tell a layperson something specific? Or is it LinkedIn boilerplate? Flag generic descriptions.
4. **Project framing.** Is the user's role named (intern, analyst, consultant)? Is the deliverable named? Is there a stakeholder or timeline?
5. **Business problems.** Three to five concrete questions, each tied to a real industry concern. Each should be specific enough to imagine a SQL query answering it. Flag generic problems ("improve sales performance"), missing problems (the use case implies one but the list does not), or problems the data cannot plausibly answer.
6. **Industry primer.** Does the industry overview give an outsider enough context for the use case to make sense? Flag missing key pieces (lending without DPD, SaaS without ARR vs MRR, med devices without UDI).
7. **Glossary.** Pick three to five jargon terms used in the ER document or SQL queries. Check each has a glossary entry written in plain language.
8. **Metrics with formulas.** Are computed metrics (ARR, NRR, DSO) given formulas with inputs and conventions? Are there any metrics referenced in queries but never defined here?

Stage 1 report format:

```
## Stage 1. Business context review

### Strengths
...

### Issues
- 🔴 P0 — <title>: <evidence with line refs from 01-{dataset_name}_business_context-cn.md>
- 🟠 P1 — <title>: <evidence>
- 🟡 P2 — <title>: <evidence>

### Claims to verify in later stages
- Business problem N (...) must show up as a SQL query in Stage 3 and a producible trap magnitude in Stage 4.
```

Pause and emit before reading the ER document.

---

## 8. Stage 2. ER document review

Read `02-{dataset_name}_er_document-cn.md`. Apply the cardinal principle.

1. **Pointer to business context.** Does the ER doc point readers to the business context file? Not blocking, but flag if missing.
2. **Mermaid ER diagram exists.** This is a hard requirement. If no Mermaid diagram is present, flag as P0.
3. **Entity completeness for the stated problems.** For each business problem from Stage 1, are the entities needed to answer it present? Typical gap patterns:
   - A money-handling business with no settlement, invoice, or payment-method entity.
   - A physical-goods business with no inventory, shipment, or returns entity.
   - A service business with no provider, appointment, or session entity.
   - An event-driven business with no link between event and downstream effect.
   - A regulated business with no audit-log or consent entity.
4. **Relationship correctness.** FK cardinalities (1:1, 1:N, M:N) realistic? Junction tables used when M:N is implied? Self-referential or hierarchical relationships modeled correctly? Nullable FKs justified?
5. **Field-level realism.** Sensible types and ranges? Plausible enums? Coherent temporal columns? Currencies (USD), units, and identifiers consistent across tables and consistent with a North American market?
6. **Per-table business purpose.** Each table should have a two-to-four sentence statement explaining what entity it represents in the business, who in the company cares about it, and what business question it helps answer. Flag generic statements ("This table stores X data") or missing statements.
7. **Computed-field claims.** Catalog every "computed from" or "derived from" claim. Stage 4 will verify the generator actually produces these.
8. **Business traps documented.** The format requires explicit "business traps embedded" callouts with expected magnitude (such as "Grade C around 4pp pricing gap"). For each business problem from Stage 1, find the corresponding trap callout. Flag any business problem without a documented trap.
9. **Mermaid ER diagram vs table definitions.** Relationships drawn in the diagram match FKs declared in the table definitions.
10. **Naming consistency.** Snake_case throughout? Reserved words (`order`, `user`, `group`, `transaction`) flagged for quoting?

Stage 2 report format:

```
## Stage 2. ER document review

### Strengths
...

### Issues
- 🔴 P0 — <title>: <evidence with line refs>
- 🟠 P1 — <title>: <evidence>
- 🟡 P2 — <title>: <evidence>

### Mermaid diagram presence
- ✅ present / 🔴 missing

### Documented traps catalogued for Stage 4
- "trap name" (line N): expected magnitude "X". Stage 4 will verify generator produces it.
```

Pause and emit before reading the SQL queries.

---

## 9. Stage 3. SQL queries review

Read `03-{dataset_name}_sql_queries-cn.md`. Three passes.

**Pass 3a. Teaching quality.** Is there a 如何使用本文档 intro that sets the teaching frame? Does each query include all five required beats (business context, tags, 解题思路, SQL, expected result with conclusion)? Are roles named specifically (using the org structure from Stage 1) rather than generic? Is the 解题思路 actually helpful (explains why the chosen join, aggregation, CTE)? Or does it paraphrase the SQL after the fact? Does the expected result name the analyst's next action?

**Pass 3b. Business logic per query.** Does the business context describe a question a real North American practitioner would ask in this industry? Or generic filler? Does each query map back to a business problem from Stage 1? Flag any query with no link. Do the stated category, difficulty, and role match what the SQL actually does? Does the expected result match what the SQL would return given the Stage 2 schema? Is the question answerable with the available columns?

**Pass 3c. SQL correctness.** Does the SQL parse against the schema from Stage 2? All referenced tables and columns present? Row duplication via joins: does a one-to-many or many-to-many join inflate the numerator while the denominator stays distinct? Fan-out across a junction table: a parent metric joined through a junction is multiplied by the child count. Check for DISTINCT, subquery aggregation, or explicit division. Aggregations grouped on the right columns? Window functions, CTEs, and date functions valid in SQLite? NULL semantics handled (NULLIF for div-by-zero, COALESCE for sums)? LEFT JOIN vs INNER JOIN choices match the metric semantics? Reserved words quoted? `REFERENCE_DATE` used as a literal, not `DATE('now')`?

**Pass 3d. Cross-query consistency.** Do two queries silently disagree on the definition of the same metric? Flag every mismatch.

Stage 3 report format:

```
## Stage 3. SQL queries review

### Teaching quality
...

### Business-logic issues
- Query <#> <title>: <issue>

### SQL correctness issues
- 🔴 P0 — Query <#>: <issue> — <one-line evidence>
- 🟠 P1 — Query <#>: <issue>

### Cross-query consistency
- "metric name": Query <a> defines as X, Query <b> defines as Y

### Mapping queries to business problems
- Problem 1 (...): covered by Q<#>, Q<#>
- Problem 2 (...): covered by Q<#>
- ⚠️ Queries with no business-problem link: Q<#>
```

Pause and emit before opening the Python file.

---

## 10. Stage 4. Data generator review with live verification

Two-part stage: static review of the Chinese Python file, then live verification via `sqlite3` queries.

### Part 4a. Static review of `04-{dataset_name}_data_generator-cn.py`

Read the file. It is usually 1000 to 2000 lines; read in slices if needed.

1. **Hard rules compliance** (from the data generator guide):
   - SQLAlchemy 2.0 ORM style.
   - Single import per line. Flag every `from x import a, b` collapse.
   - Comments and docstrings in Chinese (this is the `-cn.py` variant).
   - `FAKER_LOCALE = "en_US"` or a documented other-locale.
   - Seeded RNG.
   - `REFERENCE_DATE` constant present and used. Never `datetime.now()` or `date.today()`.
   - Module docstring lists embedded business traps.
   - Business Calibration Constants section with WHY comments on every weight, probability, threshold.
   - `create_sqlite_database` uses the Core API batch loader pattern (one ordered list, one for-loop, one transaction).
   - Idempotent (deletes prior outputs).
2. **Schema parity with ER document.** SQLAlchemy models match the ER tables, columns, types, nullability, uniqueness, FKs.
3. **Cross-table data integrity** (highest-value category):
   - `<parent>.<total_field>` equals `SUM(<child>.<amount_field>)` per parent.
   - `<parent>.<count_field>` equals `COUNT(<child>)` per parent.
   - Denormalized status, latest-date, aggregate columns on parents.
   - FK integrity: every FK value points at a parent row that was actually generated upstream.
   - Temporal ordering: child event time greater than or equal to parent event time; lifecycle end-dates after start-dates.
   - Attribution or "linked-to" fields actually derived, not randomly assigned.
4. **Distribution realism.** Weighted categorical choices reasonable for the industry? Numeric distributions within real-world bands? Per-entity counts scale with parent's tenure or lifecycle or size?
5. **Silent under-delivery.** `continue` or `break` paths that cause row counts to fall short of documented targets? Per-parent allowances truncated by an outer cap?

### Part 4b. Live SQLite verification

Run queries against the generated `{dataset_name}.sqlite` to verify documented business traps. For each trap catalogued in Stage 2, design a SQL query that measures the actual magnitude in the database. Run it with `sqlite3`. Compare to the documented magnitude.

Example:

> Stage 2 catalogued "Grade C pricing gap around 4pp (actual default about 10 percent vs implied 6.0 percent)."
>
> ```bash
> sqlite3 dataset/fintech_smb_lending_pipeline_medium/fintech_smb_lending_pipeline_medium.sqlite "
>   SELECT
>     rg.grade_code,
>     rg.implied_default_rate,
>     ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS actual_default_pct
>   FROM risk_grade rg
>   JOIN loan l ON rg.id = l.risk_grade_id
>   LEFT JOIN default_event de ON l.id = de.loan_id
>   GROUP BY rg.grade_code;"
> ```
>
> Then compare results to the documented Grade C around 4pp gap claim.

Acceptance threshold:

- For percentage claims: documented vs actual within plus or minus 1.5 absolute percentage points.
- For absolute count or amount claims: within plus or minus 10 percent relative.

Larger gaps are issues.

Also verify:

- **FK integrity at scale.** Pick two or three FKs and run `SELECT COUNT(*) FROM child WHERE fk_col NOT IN (SELECT pk FROM parent);`. Must be zero.
- **Temporal invariants.** For any "A must precede B" claim from Stage 2, count violations.
- **Computed-field invariants.** For any "X = formula(Y, Z)" claim, sample five to ten rows and verify the formula holds. For precise formulas (amortization), recompute and compare.
- **Row counts vs file manifest.** `sqlite3 ... ".tables"` and per-table `COUNT(*)` should match the manifest in the ER document.

For richer statistical checks (KS test on a distribution, correlation between columns), write a short one-off Python script and run it with `python`. This is allowed.

### Stage 4 report format

```
## Stage 4. Data generator review

### Hard rules compliance
- ✅ / 🔴 <rule>: <observation with line refs>

### Schema parity with ER document
...

### Cross-table integrity bugs
- 🔴 P0 — <issue> at <file:line> — <evidence>

### Distribution realism (static review)
- 🟠 P1 — <issue> at <file:line>

### Live data verification (sqlite3 queries)
- Trap "name": documented "X" — measured "Y" — ✅ / ⚠️ / 🔴 <verdict>
- FK integrity <child>.<fk_col>: orphans = N
- Temporal invariant "A < B": violations = N
- Computed-field "X = formula": ✅ / ⚠️ / 🔴 (sample N rows checked)
- Row count parity: ✅ / ⚠️

### Silent under-delivery
...
```

---

## 11. Final prioritized punch list

After all four stages, emit a single prioritized table covering issues from every stage.

```
## Prioritized fix list

| Priority | Stage | Issue | Suggested fix scope |
|----------|-------|-------|---------------------|
| P0 | <1/2/3/4> | <one-line description> | <low/medium/high> |
| P1 | <stage> | <one-line description> | <scope> |
```

Close with one short overall verdict paragraph. Is the dataset usable as-is for demos, teaching, or SQL exercises? If not, are the blockers concentrated or scattered? What is the single most important fix?

---

## 12. Review tone and rules

Be specific. Cite file path and line number for every claim. A claim without a line ref is a guess.

Distinguish bug (incorrect) from stylistic (could be better) from acceptable-for-demo-data (real world is more nuanced but the simplification is fine here).

Honor the cardinal principle. Polish, do not redesign. Do not propose "have you considered making this a different industry." Review the current dataset.

Call out things subtly wrong that might survive casual inspection.

Do not propose fixes inside the per-stage reports. Save fix suggestions for the final punch list at the scope level (low, medium, high), not actual code.

Do not edit, write, or delete any dataset files. Running the generator or querying the SQLite is fine. Modifying source is not.

If the dataset is internally consistent and well-modeled, say so plainly in the final verdict. Do not invent issues to fill the report.

Never assume the domain is e-commerce, SaaS, or any other particular vertical. Calibrate from the actual business context file every time.
