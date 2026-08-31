# Data Generator Guide

This guide describes the required shape of the Python generator file. Read it before drafting the `.py`.

The default market for every dataset is North America (the United States and Canada). The fictional company, customers, geographies, and regulatory references all live there.

---

## 1. What this guide is about

The Python generator file does two jobs at once. It is a working script that builds the dataset (TSV files plus a SQLite database). It is also a business-logic document that records why every weight, probability, and threshold takes the value it does.

Reading the generator should tell a future engineer what business the dataset models, which embedded business traps the file deliberately injects, and how each numeric constant was calibrated. If the file reads as anonymous Faker glue, it does not meet the bar.

---

## 2. The two Python files

Each dataset ends up with two Python files that contain identical executable code. They differ only in the language of their comments and docstrings.

| File | Comments and docstrings | Produced by |
|------|--------------------------|-------------|
| `04-{dataset_name}_data_generator-cn.py` | Chinese | This skill during the Chinese authoring pass |
| `04-{dataset_name}_data_generator.py` | English | The `translate-to-en` skill later |

The `04-` prefix marks this file as the fourth artifact in the dataset bundle. The three Markdown files use `01-`, `02-`, `03-` for business context, ER document, and SQL queries respectively, so the bundle sorts in the order a reader follows.

The Chinese variant is the one this skill produces during Phase 4. The English variant is produced later by the translation skill, which only rewrites the comments and docstrings. Variable names, function names, table names, SQL strings, and Faker calls remain in English in both files. The two files run interchangeably.

---

## 3. Hard rules

These rules are non-negotiable and apply to both Python files.

1. Use SQLAlchemy 2.0 ORM style. The base class derives from `DeclarativeBase`. Columns use `Mapped[type]` type hints and `mapped_column(...)` declarations.
2. Write one import per line. Multi-import statements such as `from datetime import date, datetime, timedelta` are forbidden. Split into three lines. This applies to every `from ... import ...` line in the file.
3. Set `FAKER_LOCALE = "en_US"` by default. Override only when the dataset is explicitly localized to a different market.
4. Seed every randomness source. `random.seed(RANDOM_SEED)` and `Faker.seed(RANDOM_SEED)` must both fire at module load. Reruns must produce identical output.
5. Declare a `REFERENCE_DATE` constant. Anchor every "today" or "current snapshot" semantic to that constant. Never call `datetime.now()` or `date.today()` inside generator logic.
6. Make the file idempotent. `generate_all_tsv` deletes any existing TSV files in `data/` before writing. `create_sqlite_database` deletes the prior `.sqlite` file before building.
7. Row counts follow the complexity tier picked in Phase 2. There is no hard per-table cap. Entity tables can naturally exceed thousands of rows when the tier and business call for it.
8. Output TSV files to `data/{NN}_{table_name}.tsv` with a zero-padded topological order index. The SQLite file lives next to the script as `{dataset_name}.sqlite`.
9. Performance target: the full generator (TSV plus SQLite build) should finish in under one minute even for the Large tier. Use polars vectorized operations where natural and the Core API batch loader for inserts. No aggressive optimization needed.

---

## 4. File structure top to bottom

The file follows a fixed top-to-bottom order. Each numbered section below maps to one block of the file.

### Section 1. Module docstring

The docstring is the first thing in the file. It summarizes the business context and lists every embedded trap. Example shape (Chinese variant):

```python
"""
{行业} {用例} 假数据生成器
复杂度: {Low/Medium/High/Large}

业务背景:
{公司名} 是一家 {一句话定位的公司}. 本数据集模拟 {数据覆盖范围},
支持以下分析:
1. {业务问题/陷阱 1}
2. {业务问题/陷阱 2}
...

上述陷阱通过有意设计的相关分布注入. 对应的 SQL 查询
位于 {dataset}_sql_queries-cn.md, 用以暴露这些陷阱.
"""
```

The trap list is a contract. Every SQL query relies on these traps existing; the generator must produce them.

### Section 2. Imports

Imports come immediately after the docstring. Group them in the order shown, with a blank line between groups. Note the single-import-per-line rule.

```python
from __future__ import annotations

import random
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Numeric
from sqlalchemy import Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
```

### Section 3. Configuration constants

Define paths, locale, seed, and reference date in one block.

```python
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "{dataset_name}.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期.
REFERENCE_DATE = date(YYYY, M, D)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)
```

### Section 4. Business calibration constants

This is the heart of the new-style generator. Every weight, probability, and threshold that drives a business trap or distribution shape lives here, named, with a comment explaining why that value was chosen. The comment must tie back to either a documented trap or a real-world industry convention.

Example:

```python
# 各风险等级的"首次借款人"违约率. 复购客户 (~12%) 违约率为表中数值的一半.
# Grade C 是核心定价错配: 首借 12% 配上组合中等级分布, 池级实际 ~10%, 
# 比定价模型假设的 6.0% 高出约 4pp. 这条偏置对应 SQL 查询 Q1.
GRADE_FIRSTTIME_DEFAULT_RATE = {
    1: 0.035,  # A - Prime          (implied 3.0%, pool ~4%, 略微高估)
    2: 0.065,  # B - Near Prime     (implied 6.0%, pool ~6%, 接近)
    3: 0.120,  # C - Standard       (implied 6.0%, pool ~10%, 定价不足 4pp)
    4: 0.150,  # D - Subprime       (implied 13.0%, pool ~15%, 略偏低)
    5: 0.220,  # E - Deep Subprime  (implied 18.0%, pool ~19%, 略偏低)
}
```

Rules of thumb:

- Every business trap mentioned in the docstring must have at least one named constant in this section.
- Prefer dict-of-floats over magic numbers scattered inside `gen_*` functions.
- If a constant exists because a regulator or industry convention dictates it (90 DPD for default, 30 days for ACH return, and so on), state that.

### Section 5. ORM models

Standard SQLAlchemy 2.0 style. Each model class has a one-line docstring naming the business entity, not just the table.

```python
class Base(DeclarativeBase):
    pass


class Customer(Base):
    """企业借款人. 美加州中小企业, 含财务画像, 用于信用承保."""

    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industry.id"), nullable=False)
    # ... 其他列 ...
```

The column types and constraints must match the ER document exactly. If they disagree, one of the two artifacts is wrong.

### Section 6. Generator functions

Define one `gen_*` function per table, in topological order (tables with no FK dependencies first).

Each function has a docstring naming what it produces and any non-obvious business constraint. The function embeds business logic into the sampling (weighted choices, correlated draws, conditional means), not just `fake.word()`.

Patterns to use:

- Weighted categorical choices anchored to a constant in section 4.
- Correlated draws. If credit score correlates with revenue, draw revenue conditional on the score, not independently.
- Conditional means. If defaulting loans show worse payment behavior in the last three installments, build that pattern into the payment generator.
- Hard invariants. `loan.outstanding_balance` is the closed-form amortization at the reference date, never `random.uniform(0, principal)`.

Anti-patterns to avoid:

- Drawing every field independently. Real data has correlation; uncorrelated mock data feels artificial.
- Picking categories with uniform `random.choice` when the business has a skewed distribution.
- Setting a rollup field on a parent (such as `customer.total_loans`) before its children are generated.

### Section 7. The `generate_all_tsv` function

This function orchestrates all `gen_*` calls and writes each result to a TSV file. It is idempotent.

```python
def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_industry = gen_industries()
    df_industry.write_csv(DATA_DIR / "01_industry.tsv", separator="\t")

    df_risk_grade = gen_risk_grades()
    df_risk_grade.write_csv(DATA_DIR / "02_risk_grade.tsv", separator="\t")

    df_customer = gen_customers(industry_ids=df_industry["id"].to_list())
    df_customer.write_csv(DATA_DIR / "03_customer.tsv", separator="\t")

    # ... 按拓扑顺序继续 ...

    print(f"Generated all TSV files in {DATA_DIR}")
```

### Section 8. The `create_sqlite_database` function

This must use the simplified Core API batch loader pattern: one ordered list of `(tsv_basename, Table)` pairs, one for-loop, one `engine.begin()` transaction. The pattern is fast and easy to extend.

```python
def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 拓扑加载顺序. 第一个元素是不带扩展名的 TSV 文件名;
    # 第二个元素是 SQLAlchemy Core Table 对象 (ORM 类用 `.__table__`,
    # 关联表用 metadata.tables["assoc_xxx"]).
    load_order: list[tuple[str, "Table"]] = [
        ("01_industry", Industry.__table__),
        ("02_risk_grade", RiskGrade.__table__),
        ("03_loan_status", LoanStatus.__table__),
        ("04_loan_officer", LoanOfficer.__table__),
        ("05_customer", Customer.__table__),
        ("06_application", Application.__table__),
        ("07_loan", Loan.__table__),
        ("08_repayment_schedule", RepaymentSchedule.__table__),
        ("09_payment", Payment.__table__),
        ("10_default_event", DefaultEvent.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv",
                separator="\t",
                try_parse_dates=True,
            )
            rows = df.to_dicts()
            if rows:
                conn.execute(table.insert(), rows)

    print(f"Created SQLite database at {DATABASE_PATH}")
```

Why this shape works well:

- One ordered list is one source of truth for topological order. Adding a table is one new line.
- `engine.begin()` opens a single transaction. Fast and atomic.
- `table.insert(), rows` is Core API executemany. Far faster than per-row `session.add` calls.
- Association tables for M:N relationships fit the same loop. The second element of the tuple can be any `Table` object, including `metadata.tables["assoc_xxx"]`.

Type coercion notes:

- `polars.read_csv(..., try_parse_dates=True)` parses dates and datetimes written by polars.
- Boolean columns written as `true` / `false` strings may need explicit handling. Writing `1` and `0` from inside `gen_*` simplifies the load.
- `NUMERIC(p, s)` columns: polars writes them as floats, which SQLite stores fine.

### Section 9. The main function and entry point

```python
def main() -> None:
    print("Starting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("All done!")


if __name__ == "__main__":
    main()
```

---

## 5. Optional reconciliation pass

For datasets with rollup or invariant fields (such as `account.lifetime_revenue = SUM(orders.amount)`), add a `reconcile` function that runs after `generate_all_tsv` and either fixes derived fields or asserts the invariants. The SQL queries document may reference these invariants. The reviewer skill will check them.

---

## 6. Style notes

Function-level docstrings are one or two lines naming the business entity and any non-obvious constraint. Skip the "Returns: DataFrame" boilerplate unless the return shape is non-obvious. Inline comments should explain why a number was chosen, not what a line of code does. The code already says what; the comment exists for context the code cannot carry.

Do not leave `# TODO` comments in the final file. Pass a basic `ruff` or `flake8` clean-up. Mapped attributes use type hints; local variables do not need them.

---

## 7. Anti-pattern checklist

A quick checklist to run before declaring the Python file done. Any item below means the file is not ready.

- A multi-import line such as `from datetime import datetime, timedelta` slipped in somewhere.
- `datetime.now()` or `date.today()` appears anywhere in generator logic.
- A categorical column uses `random.choice(list)` with no weights, even though the business has a real skew.
- A computed field gets a random value instead of being computed from its inputs.
- A FK column gets written before the referenced parent IDs exist.
- A numeric constant has no business rationale comment.
- The loader uses `session.add` in a loop where Core executemany would do.
- Multiple `session.commit()` calls inside the loader instead of one outer transaction.
- The Chinese variant has English-only comments left over (or vice versa for the English variant).
