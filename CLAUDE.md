## 1. Project Overview

This project generates realistic, business-meaningful fake datasets for any vertical industry, each one telling the data story of a fictional North American company. Every dataset ships with a business context document, an ER document, SQL queries, a Python generator, and deliberately embedded business traps for analysts to discover.

---

## 2. Development Setup

**Package Manager:** uv (via mise)

**Core Configuration Files:**
- `mise.toml` - Project tasks and tool versions (Python 3.12, uv)
- `pyproject.toml` - Dependencies and project metadata
- `.venv/` - Virtual environment directory

**Available Tasks:**
- `mise run venv-create` - Create Python virtual environment
- `mise run venv-remove` - Remove virtual environment
- `mise run inst` - Install Python dependencies
- `mise run test` - Run tests with pytest

---

## 3. Documentation Language

Chinese language documents for this project live under `docs-md`.

---

## 4. Core Agent Skills

`fake-data-generator` and `review-fake-data-generator` are the two core Agent Skills for this project. The first authors a new dataset from scratch, and the second performs an external, read-only review pass over an existing one.

---

## 5. Review and Fix Loop

`review_and_fix_loop.py` runs a scripted review and fix loop that simulates two terminals working against each other, one reviewing and one fixing, without human interruption for the full run.

---

## 6. Dataset Workflow

A human describes the target dataset in plain language, and the `fake-data-generator` skill drafts the initial version under `dataset/`, following its own authoring conventions. Once every file is in place, the human runs three to five light polishing rounds to settle the data and business tone, which completes the draft. From there, add the dataset name to `DATASET_NAMES` in `review_and_fix_loop.py` and run the script to let the automated review and fix loop refine it further. The final step is running the `update-dataset-index` skill to refresh `dataset/INDEX-cn.md` and `dataset/INDEX.md`.

---

## 7. Model Selection

Run this project on Opus when Plan quota allows it. Otherwise default to Sonnet.
