---
name: update-dataset-index
description: >
  Regenerate dataset/INDEX-cn.md and dataset/INDEX.md from every dataset's one-line summary files
  (00-<name>_summary-cn.md and 00-<name>_summary.md). A thin wrapper over the deterministic script
  update_dataset_index.py — no AI, no arguments: every run is a full scan of dataset/ plus a full
  regenerate from the frozen summaries. Use when the user wants to refresh the dataset index after
  datasets have been summarized and translated.
allowed-tools: Bash
---

# Update Dataset Index

Regenerate `dataset/INDEX-cn.md` and `dataset/INDEX.md` from the per-dataset one-line summary
artifacts. The actual work is a pure Python script; this skill is just the conversational entry
point that runs it and relays the result.

## What this skill does

Reading a summary file is deterministic, so there is nothing to merge or update selectively —
every run is a **full scan of `dataset/` plus a full regenerate**. The summary text is authored
once per dataset by the `run-summarize-and-translate` skill and frozen on disk as two one-line
files:

- `dataset/<name>/00-<name>_summary-cn.md` → a bullet in `dataset/INDEX-cn.md`
- `dataset/<name>/00-<name>_summary.md` → a bullet in `dataset/INDEX.md`

The script globs those files for every dataset and rebuilds both INDEX files from a string
template. It reads no ER documents, no SQL queries, no large artifacts, and asks no AI to write
anything. If a summary looks wrong, fix it by re-running `run-summarize-and-translate` for that
dataset, not here.

## How to run it

Run the script from the repo root — it takes no arguments:

```
uv run python update_dataset_index.py
```

Because it always regenerates from scratch, the resulting index is an exact mirror of which
summary files exist on disk right now. A dataset that has no summary yet (still mid-draft, or not
translated) is skipped with a warning and simply doesn't appear in the index — so run this
**after** the summarize-and-translate step, not before, or the regenerated index will drop the
datasets that lack a summary.

## Reading the result

The script prints how many entries went into each index, then one `[warning]` line per dataset it
skipped:

- `[warning] <name>: no cn/en summary file found, skipped` — the dataset hasn't been
  summarized/translated yet. Expected while some datasets are unfinished.
- `[warning] <name>: <lang> summary ... is empty or not one line, skipped` — the summary file is
  malformed. The fix is to re-summarize that dataset so its `00-<name>_summary*.md` is a single
  clean line.

Missing or malformed summaries are warnings, not errors — a defensive fallback, not a failure.

## Step: report

Relay the script's outcome to the user in their language, under ~10 lines: how many entries went
into each index, any warnings verbatim, and the two paths `dataset/INDEX-cn.md` and
`dataset/INDEX.md`. Do not restate the summary content.

## Constraints

- Never hand-edit `INDEX-cn.md` / `INDEX.md` — always go through `update_dataset_index.py`.
- Never fabricate a summary. If a dataset has no summary file, it is simply not indexed yet.
- Never modify files other than the two index files (the script only writes those two).
