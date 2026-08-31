---
name: run-summarize-and-translate
description: >
  Finalize a signed-off dataset: first write a one-line Chinese summary of it, then translate every
  Chinese-authored artifact (files ending in `-cn.md` or `-cn.py` under `dataset/<dataset-name>/`,
  including the just-written summary) into their English counterparts. Orchestration only — the work
  is done by three custom subagents: `dataset-digest` reads the dataset once, writes
  `00-<name>_summary-cn.md`, and returns a consistency brief; then `dataset-md-translator` and
  `dataset-py-translator` run one per file in parallel using that brief. Output filenames drop the
  `-cn` suffix. Use when a dataset's Chinese files are signed off and ready to be summarized and
  translated to English.
argument-hint: "[dataset-name]"
allowed-tools: Read, Glob, Bash, Agent
---

# Run Summarize and Translate

This skill is **orchestration only**. It coordinates three custom subagents to finalize one
signed-off dataset in two ordered jobs:

1. **Summarize** — the `dataset-digest` subagent reads the dataset's Chinese business-context, ER,
   and SQL-queries files once, writes the one-line summary
   `dataset/<dataset-name>/00-<dataset-name>_summary-cn.md`, and returns a consistency brief.
2. **Translate** — one translation subagent per `-cn` file, run in parallel, rewrites every source
   file **including the summary** into English. `dataset-md-translator` handles `.md` files (full
   rewrite); `dataset-py-translator` handles the `.py` generator (comments/docstrings only, code
   byte-identical).

The order is load-bearing: the summary must exist **before** the translation fan-out, so the same
fan-out produces its English version (`00-<dataset-name>_summary.md`) for free. Do not translate
first.

The translation rules, filename conventions, and per-file constraints live in the three subagent
definitions under `.claude/agents/` (`dataset-digest.md`, `dataset-md-translator.md`,
`dataset-py-translator.md`) — including their pinned `model` and the preloaded
`doc-writing-styles:translate-to-en` skill. This skill does not restate those rules; it only
discovers files, sequences the two jobs, passes each subagent its file paths and the shared brief,
and verifies the result.

Do not hardcode an expected file count or specific filenames — `fake-data-generator` may add or
rename artifacts over time. Discover the source files fresh each run via Glob. Each run processes
exactly one dataset.

## Step 1: Confirm the target dataset and discover its Chinese source files

Resolve `<dataset-name>` from `$ARGUMENTS`. If empty, run `ls dataset/` and ask the user which
dataset to finalize in plain conversation — do not guess.

Confirm `dataset/<dataset-name>/` exists, then use Glob to find every source file:

- `dataset/<dataset-name>/*-cn.md`
- `dataset/<dataset-name>/*-cn.py`

If the directory doesn't exist, or the glob finds no `-cn` files, stop and tell the user — this
dataset hasn't been authored yet or is still mid-draft. Do not invent files.

## Step 2: Summarize — delegate to the `dataset-digest` subagent

Launch **one** `dataset-digest` subagent (Agent tool, `subagent_type: dataset-digest`) and wait for
it to finish before Step 3. From the `-cn.md` files discovered in Step 1, pick out the
business-context, ER-document, and SQL-queries files and pass their **exact paths** to the digest
in its task prompt (the digest does not search for them itself). It writes
`00-<dataset-name>_summary-cn.md` and returns the consistency brief as its final message.

Keep the returned consistency brief text — every Step 3 subagent needs it. After this step the
translate set is every `-cn.md`/`-cn.py` from Step 1 **plus** `00-<dataset-name>_summary-cn.md`.

## Step 3: Translate — fan out one subagent per file, in a single message

Launch all translation subagents in the **same response** so they run in parallel:

- For every `-cn.md` file (including `00-<dataset-name>_summary-cn.md`), launch a
  `dataset-md-translator` subagent (`subagent_type: dataset-md-translator`).
- For every `-cn.py` file, launch a `dataset-py-translator` subagent
  (`subagent_type: dataset-py-translator`).

Each subagent's task prompt is short — it already carries the rules in its definition. Give it only:

- the **source path** (the `-cn` file),
- the **output path** (drop `-cn`, keep the extension — e.g.
  `02-<name>_er_document-cn.md` → `02-<name>_er_document.md`;
  `00-<name>_summary-cn.md` → `00-<name>_summary.md`), and
- the **consistency brief** from Step 2.

If an output file already exists, this run overwrites it.

## Step 4: Verify

- Confirm `00-<dataset-name>_summary-cn.md` exists and is exactly one line, and that its English
  counterpart `00-<dataset-name>_summary.md` also exists and is exactly one line (read them; check
  there's one paragraph and no `#` header).
- Confirm every discovered `-cn` file has a matching English output (same name, `-cn` dropped).
- For every `.py` pair, run a diff and confirm every changed line falls inside a `"""..."""` block
  or starts with `#`:

  ```
  diff -u dataset/<dataset-name>/<name>-cn.py dataset/<dataset-name>/<name>.py
  ```

  If the diff touches an executable line, the `dataset-py-translator` violated its constraints —
  re-run it with the offending lines quoted, or fix the file directly, before reporting done.
- Spot-check one Markdown file: cross-file links point to English filenames, SQL blocks and
  `REFERENCE_DATE` literals are untouched, jargon abbreviations weren't reworded.
- Confirm every `-cn` source file is untouched — this run only adds/overwrites English files and the
  two summary files.

## Step 5: Report

Report in the user's language: the dataset name, that the summary was written (both languages), the
list of translation output paths, and the result of each Python diff check. Keep it under ~10 lines.
Do not restate the content.

## Constraints

- Summarize before translating — the summary must exist before the fan-out so its English version is
  produced by the same fan-out.
- This skill delegates; it does not translate or summarize inline. If a rule needs changing, edit the
  subagent definition under `.claude/agents/`, not this skill.
- Never hardcode a file count or filename — always discover source files fresh via Glob.
- Always launch the Step 3 translation subagents in a single message so they run in parallel.
