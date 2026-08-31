AI Datafaker Pro
==============================================================================
Realistic, business-meaningful synthetic datasets for demos, Text-to-SQL training, BI prototyping, and SQL teaching.

Good project work needs good data, and business data is the hardest kind to fake well. A schema that merely looks plausible is easy to produce. A dataset that is internally airtight, where every number, every distribution, and every relationship holds up under a domain expert's scrutiny and never contradicts itself, is much harder. This repository exists to solve that problem for a chosen project, business background, and use case, producing dummy data and a business narrative that fit together without gaps.

Each dataset ships with a Python generator, an ER document, and a library of production-grade SQL queries.


1. Datasets
------------------------------------------------------------------------------
Each subdirectory under ``dataset/`` is one self-contained dataset holding only documents and the Python generator script. The SQLite database and TSV files are produced by running the generator, not checked in. See ``dataset/INDEX.md`` (or ``INDEX-cn.md``) for the catalog.


2. Two core agent skills
------------------------------------------------------------------------------
``fake-data-generator`` writes a new dataset (or modifies an existing one) per the 0.2.1 spec. ``review-fake-data-generator`` audits a dataset and emits a structured punch list. Both live under ``.claude/skills/`` with their own SKILL.md plus supporting guidance.


3. Authoring workflow
------------------------------------------------------------------------------
Use ``fake-data-generator`` to draft a first version: agree on the project goal, the fictional company, the business problems, and the data shape, then write the four Chinese artifacts (business context, ER document, SQL queries, Python generator). Edit ``DATASET_NAMES`` in ``review_and_fix_loop.py`` and run it to drive rounds of review-then-fix against that draft. The loop is built on the Claude Agent SDK; ``multi-session-workflow-guide.md`` documents the underlying two-persistent-session pattern.


4. Index maintenance
------------------------------------------------------------------------------
The ``update-dataset-index`` skill keeps ``dataset/INDEX.md`` and ``dataset/INDEX-cn.md`` in sync with the dataset folders. Run it after adding or upgrading a dataset.


5. Snapshot for sharing
------------------------------------------------------------------------------
``copy_datasets_to_tmp.py`` copies each catalogued dataset's eight canonical artifacts into ``tmp/dataset/``, skipping generated outputs (``.sqlite``, ``data/``) and audit notes (``review-NN.md``, ``fix-NN.md``, ``upgrade.md``).
