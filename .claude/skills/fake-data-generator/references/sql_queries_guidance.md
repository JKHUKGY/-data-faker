# SQL Queries Guide

This guide describes the SQL queries document. The skill produces the Chinese variant `03-{dataset_name}_sql_queries-cn.md` during the authoring pass. The English variant `03-{dataset_name}_sql_queries.md` comes later from the `translate-to-en` skill.

The `03-` prefix marks this file as the third artifact in the dataset bundle, behind the business context (`01-`) and the ER document (`02-`), and ahead of the Python generator (`04-`).

The SQL queries document is the most teaching-oriented artifact in the dataset. It demonstrates that the schema and data actually support the business problems stated in the business context file, and it teaches a reader how a real analyst approaches each question.

The default market is North America.

---

## 1. Purpose and audience

The audience is a smart intern who has already read the business context file and the ER document. The intern's manager just handed them this document and said "work through these queries this week."

Every query should read like a project handoff:

> Here's the question. Here's why it matters. Here's how I would approach it. Here's the SQL. Here's what the answer should look like. Here's what we do with it.

The old style answered "which SQL technique does this query demonstrate." The new style answers "which business decision does this query inform, and how does a junior analyst learn to write it." The difference matters.

A query that just shows working SQL is not enough. The intern needs to understand why this join is a LEFT JOIN rather than an INNER JOIN, why the aggregation is grouped on this column, why a CTE earns its keep here, and what the resulting numbers tell the company.

---

## 2. Query count

The default is 20 queries. The acceptable range is 16 to 24. Go under the default if the dataset is small and 20 would force padding. Go over the default if the dataset has a natural set of distinct business questions that does not fit in 20. Avoid 30 and up; that becomes a slog.

---

## 3. Document-level intro

The opening of the file does three things in order.

First, it states which dataset this document covers and references the business context file by name, so the reader knows where to go for context.

Second, it explains the `REFERENCE_DATE` convention. The dataset is anchored to a fixed date that appears as a literal in every query, instead of `DATE('now')`, so results stay reproducible.

Third, it includes a 如何使用本文档 (how to use this document) section. This section is the teaching frame. It tells the intern:

- Who the queries are written for (the intern reading this document).
- The five content beats every query has and what each beat is for.
- That every query maps back to a problem stated in the business context file.
- That the SQL is meant to be read and learned from, not just executed.

A reader who finishes the intro section understands what to expect for the next twenty queries.

---

## 4. The query index

A flat table listing every query with the columns below. Use specific role titles ("首席风险官", "Collections Manager", "VP of Underwriting") when the business context names them, not generic ones ("Executive", "Manager").

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|

---

## 5. Per-query content beats

Each query has five content beats. The headings are flexible, but every beat must appear.

### Beat 1. Business context

Two to four paragraphs. Cover all four of:

- Who is asking and which role they sit in. Tie back to the org structure in the business context file.
- What prompted the question. A meeting, a quarter-end, a regulatory deadline, a customer complaint, a board prep.
- What decision the answer informs. A pricing change, a hiring move, a segment shutdown, a model retraining, a budget reallocation.
- Why now. What changed that makes this question urgent right now.

Generic context fails the bar. "Run this query to see the average loss per grade" reads identically in every industry and conveys no information. Specific context names the role, the meeting, the decision, and the urgency.

A specific business context paragraph looks like this:

> 首席风险官需要为季度风险评审准备材料. 她注意到 Grade C 占组合 28%, 但内部讨论中有人提出 Grade C 的实际违约率可能高于定价模型假设. 如果属实, 公司可能正在按"被低估的风险"放贷, 本季度的拨备需要上调. 她需要看到每个等级的"模型假设违约率 vs 实际违约率", 以决定是否在下季度调整 Grade C 利率. 这道题对应业务问题 Q1.

### Beat 2. Tags

Category, difficulty, and business role. Three short labels. Match what the SQL actually does. A query tagged "Aggregation + Join" should actually involve both. A query tagged "Advanced" should actually be advanced.

### Beat 3. 解题思路 (Approach)

Three to six sentences (sometimes longer for advanced queries) walking the intern through the approach before they see the SQL. This is the most teaching-heavy section and the one most often missing from old-style datasets. It is also the section that turns the document from a SQL reference into a learning artifact.

Cover the elements below. Use plain prose, not a bulleted recipe.

- Which tables the query needs to touch and why.
- The join structure and any traps to avoid. Fan-out from one-to-many joins, double counting, wrong cardinality.
- The grain of the aggregation. What does one output row mean.
- Why a CTE or window function or subquery is the right tool here (or why a simpler shape works).
- Any SQLite-specific gotcha that matters (NULL semantics, date function quirks).

A good 解题思路 paragraph looks like this:

> 这题要把 implied 违约率 (`risk_grade` 表) 与实际违约率 (从 `loan` 和 `default_event` 计算) 对齐到等级粒度. 先用 `LEFT JOIN default_event ON loan.id = de.loan_id` 把违约标在每笔贷款上, 然后按等级聚合 `COUNT(default_event.id) / COUNT(loan.id)`. 注意 LEFT JOIN 不能换成 INNER JOIN, 否则没有违约的贷款会被剔除, 实际违约率会被严重高估. 窗口函数和 CTE 都不需要, 一次 GROUP BY 即可完成.

Notice that the paragraph walks the intern through the logic before they see the SQL. By the time they reach the code block they already understand the shape.

### Beat 4. SQL code

The query itself, in a fenced `sql` block. Rules:

- Every query must run against the SQLite database produced by the generator. Verify before publishing.
- Inline comments only when a clause is non-obvious (a deliberate LEFT JOIN, a workaround for NULL semantics, a window function trick).
- Use a literal date string for the reference date (such as `'2026-06-03'`). Never `DATE('now')`.
- Quote reserved-word column names (`order`, `user`, `group`, `transaction`).
- Format for readability: place each top-level keyword (SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY) on its own line.

### Beat 5. Expected result and business conclusion

Two parts.

First, describe the shape of the result set. Number of rows, columns, what each column means. Cite the magnitudes that tie to the embedded business traps. "Grade C 应展示约 minus 4pp 的 pricing gap; A, B, E 落在 plus or minus 1pp 内; D 约 minus 2pp."

Second, name the next action the analyst takes. The teaching point is that running the query is the start, not the end, of the analysis. "如果 Grade C 缺口超过 minus 3pp, 起草一份调价提案提交到 Q3 风险委员会."

The action line is what makes the query a teaching artifact instead of a SQL exercise.

---

## 6. Coverage targets

Aim for diverse coverage so the dataset exercises a range of SQL skills and a range of business roles. The numbers below are guidelines, not hard rules. If the business problems naturally cluster differently, follow the business.

**SQL techniques:**

- Aggregation: 4 to 5
- Joins (including LEFT and RIGHT considerations): 4 to 5
- Window functions (RANK, LAG, moving averages): 2 to 3
- Date and time analysis (cohort, vintage, trend): 2 to 3
- Subqueries and CTEs: 2 to 3
- Pattern and text matching: 1 to 2

**Business roles (use the specific titles from the business context file):**

- C-level (CEO, CFO, CRO, CMO): 2 to 3
- VP or Director: 4 to 5
- Manager: 4 to 5
- Analyst or IC: 5 to 6
- Operations or specialist (collections, support, ops): 2 to 3

**Difficulty:**

- Basic: 6 to 8
- Intermediate: 8 to 10
- Advanced: 2 to 4

---

## 7. Tying queries to business problems

Every query must trace back to at least one business problem stated in the business context file. When the business problems list has three to five entries, the 20 queries should distribute roughly as follows.

A handful of queries support the marquee business problem (the one the project was named after). A few queries support each secondary problem. A few operational queries (daily volume, throughput, SLA adherence) round out the document, even when no business problem mentions them by name.

A document-level footer may include a mapping table:

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 风险定价对齐 | Query 1, Query 16 |
| Q2 组合集中度 | Query 2, Query 19 |

If a query does not trace back to any business need, ask whether it belongs in the document at all.

---

## 8. The Chinese narrative voice

The Chinese variant uses Chinese narration for the business context, the 解题思路, and the expected-result discussion. SQL keyword conventions stay English (SELECT, JOIN, GROUP BY). Column names and table names stay English snake_case. Business jargon stays in its English form (ARR, DPD, FICO, RMA, AOV) with explanations in the business context file's glossary.

---

## 9. The English version

The English variant comes from the `translate-to-en` skill after the Chinese version is finalized. The SQL itself stays identical. Only the narrative beats (business context, 解题思路, expected result) are re-voiced for an English-reading audience.

Do not author the English file by hand during the authoring pass.

---

## 10. Anti-patterns to avoid

- Generic business context that reads the same in any industry.
- Generic role tags ("Executive") when the business context names a specific VP or C-level title.
- A 解题思路 section that paraphrases the SQL instead of explaining the choice of joins, aggregations, or CTEs.
- Expected-result magnitudes that the generator does not produce.
- Queries with no traceable link to the business problems.
- `DATE('now')` anywhere.
- SQL syntax that crashes on SQLite (PostgreSQL-only window function syntax, MySQL-only date functions, and so on).
- A document with twenty queries that all read "show me the top ten." Vary the questions, not just the technique tag.
