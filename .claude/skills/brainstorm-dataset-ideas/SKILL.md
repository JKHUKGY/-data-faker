---
name: brainstorm-dataset-ideas
description: >
  Brainstorm fresh ideas for new fake datasets. Reads dataset/INDEX-cn.md to learn
  which industries and use cases are already covered, then proposes new dataset concepts —
  either by filling gaps in the current distribution, or by working backwards from a
  Job Description (its Industry, Company, Role) to the data and use case that would support
  that role's daily projects. Ideas only: it writes the proposals (in Chinese) to tmp/idea.md
  and stops. Use when the user wants ideas for the next dataset, asks "what should we build next",
  or hands over a job description to reverse-engineer a dataset from.
argument-hint: "[optional: job description / industry / company / role details]"
allowed-tools: Read, Write, Bash, Glob, Grep, WebSearch, AskUserQuestion
---

# Brainstorm Dataset Ideas

You help the user invent ideas for the **next** fake dataset in this project. You do not
build the dataset. Your entire job is to think up strong, business-meaningful, non-duplicate
ideas and write them, in Chinese, to `tmp/idea.md`. Then you stop.

Every dataset in this project tells the data story of one fictional **North American** company
(United States and Canada) solving concrete business problems. It ships with a business context
document, an ER document, SQL queries, a Python generator, and deliberately embedded business
traps for analysts to discover. Your ideas must be shaped so that such a dataset could plausibly
be authored from them by the `fake-data-generator` skill.

## Step 0: Read what already exists

Always start by reading the coverage index so you do not propose duplicates and can reason about gaps:

- Read `dataset/INDEX-cn.md` (the authoritative list of existing datasets and their coverage).

From it, build a mental coverage map along two axes:

- **行业 (Industry / vertical)** — e.g. fintech lending, health insurance, telecom manufacturing,
  ecommerce, adtech / advertising, govtech, real estate, cybersecurity, medical devices, media.
- **Use Case pattern** — e.g. AI/ML prediction & quality systems, fraud & AML risk, compliance &
  audit, marketing growth & attribution, customer success & churn, operations & scheduling,
  underwriting & pricing, credit approval, service-request / ticket intelligence.

Note the naming convention: dataset folder names are `{industry_or_domain}_{specific_use_case}_{size}`
where `size ∈ {medium, high, large}` (e.g. `telecom_equipment_fiber_splicing_quality_high`).
Follow it when you propose a suggested dataset name.

## Step 1: Decide which mode you are in

Look at the arguments the user passed (`$ARGUMENTS`).

- **Mode A — Distribution-driven brainstorming** (arguments are empty or just say "想点子" / "give me ideas"):
  Analyze the existing distribution, find under-served industries, missing use-case patterns, or
  fresh novel combinations, and propose new dataset ideas that expand coverage.

- **Mode B — Job-Description-driven brainstorming** (arguments describe a Job Description, or an
  Industry / Company / Role): Work backwards. The point of the JD is: *for the projects this person
  does every day on this job, what dataset and use case would let someone practice, demo, or support
  that work?* Reverse-engineer the data and use case from the daily reality of the role.

If the arguments are ambiguous (some text but you cannot tell whether it is a JD or a loose topic),
and it materially changes your output, use `AskUserQuestion` once to clarify. Otherwise pick the most
reasonable interpretation and proceed — do not stall.

If a JD is thin on detail, you may use `WebSearch` to understand what the role/industry actually does
day to day before reverse-engineering the dataset. Keep it light; the goal is good ideas, not research.

## Step 2 (Mode A): Find the gaps and generate ideas

1. From the coverage map, explicitly identify:
   - **Industries not yet covered** (e.g. hospitality, airlines/logistics, agriculture, energy/utilities,
     education/edtech, gaming, biotech/pharma trials, insurance sub-lines, construction, HR/payroll).
   - **Use-case patterns thin or absent** across the existing industries.
   - **Novel combinations** — an existing industry paired with a use case it has not been shown with.
2. Propose **5–8** ideas that maximize *diversity* and *business realism*. Favor ideas that fill a clear
   gap over ideas that sit next to something already covered. Each must be distinct enough that it would
   not read as a near-duplicate of an existing dataset.

## Step 2 (Mode B): Reverse-engineer from the job

1. Restate, briefly, what this role actually does day to day (the recurring projects, decisions, and
   deliverables). Ground it in the given Industry / Company / Role.
2. For those daily projects, ask: *what data would this person be looking at, querying, or feeding into
   a model?* That data need is the dataset. The recurring decision is the use case.
3. Propose **1–3** focused ideas tailored to the role. Prefer one strong, faithful idea over three loose
   ones. For each, spell out the **岗位映射 (job mapping)**: which daily task each part of the dataset
   supports.
4. Check the existing datasets: if something already covers this role well, say so honestly and pivot the
   idea toward the uncovered angle instead of duplicating.

## Step 3: Write each idea using this template

Every idea, in **Chinese**, follows this exact template (Mode B adds the 岗位映射 line):

```
## 点子 N: <一句话标题>

- **建议数据集名**: `{industry}_{use_case}_{size}`
- **行业**: <vertical>
- **虚构公司**: <公司名 + 一句话画像, 明确是北美 (美国/加拿大) 公司>
- **目标角色 / Persona**: <谁会用这份数据 — analyst / role>
- **核心 Use Case / 业务问题**: <2-4 个具体、可用 SQL 或 ML 回答的业务问题>
- **数据故事**: <这家公司在解决什么, 数据在讲什么故事>
- **核心实体 / 表构想**: <粗列 8-20 张主要表 / 核心实体, 体现事件级 + 维度表>
- **建议规模**: <medium / high / large> + <粗略行数量级>
- **内嵌业务陷阱构想**: <1-3 个 analyst 需要主动发现的"坑" — 如归因漂移、定价倒挂、SLA 虚假达成、幸存者偏差等>
- **与现有数据集的差异**: <为什么不重复, 填补了什么行业或 use case 空白>
（Mode B 额外增加）
- **岗位映射**: <这份数据的哪些部分对应岗位上的哪些日常项目/决策>
```

Aim for ideas that are *specific* — real numbers, named entities, concrete decisions — not abstract data
models. Business realism is load-bearing: a schema that reads like an abstract ER diagram misses the point.

## Step 4: Assemble and write `tmp/idea.md`

1. Ensure the `tmp/` directory exists (create it if needed) at the repo root
   `/Users/sanhehu/Documents/GitHub/ai_datafaker_pro-project/tmp/`.
2. Write **all** output to `tmp/idea.md`, overwriting any previous contents, in Chinese, with this structure:

```
# 新数据集点子

> 生成模式: <A: 按现有分布补空白 / B: 由岗位描述反推>
> 生成时间: <today's date>

## 现有覆盖速览
<3-6 行, 概括现有数据集覆盖的行业与 use case, 以及你识别到的空白 (Mode A) 或岗位画像 (Mode B)>

## 点子清单
<每个点子用 Step 3 的模板>
```

3. Keep everything in Chinese narration (English technical terms stay in English). Since you are producing
   a Chinese-narrated Markdown file, follow the project's `chinese-english-punctuation` and `markdown-style`
   conventions: use ASCII punctuation around English terms, and keep headings/tone consistent.

## Step 5: Report back briefly

In your reply to the user (not in the file), give a 3–6 line summary: which mode you ran, how many ideas
you wrote, the one-line title of each, and the path `tmp/idea.md`. Do not paste the full file back.

## Constraints

- **Ideas only.** Never create anything under `dataset/`, never write a generator, never build the dataset.
  Your only file output is `tmp/idea.md`.
- Never duplicate an existing dataset. Cross-check every idea against `dataset/INDEX-cn.md`.
- Every fictional company is North American; currency is USD; regulatory references are US/Canadian.
- Do not fabricate that a dataset already exists or does not exist without having read `INDEX-cn.md`.
