"""
Fintech — SMB Lending Pipeline Fake Data Generator
Complexity: Medium
Author: Fake Data Generator Agent

Business background:
Pacific Bridge Lending is a mid-sized fintech company headquartered in California, focused on
small and medium-sized business (SMB) lending. This dataset simulates its full lending pipeline:
from application intake through repayment / default, supporting the following analyses:
1. Risk pricing alignment (is each risk grade priced correctly?)
2. Portfolio concentration (industry exposure management)
3. Approval leakage (good customers wrongly rejected)
4. Early warning signals (behavioral indicators before default)
5. Customer lifetime value (repeat vs. new customers)

The dataset contains roughly 3,000 loan applications spanning about 2 years. The five "business
traps" above are injected via deliberately correlated distributions (grade-driven default rates,
weighted industries, credit-score-driven approvals, pre-default repayment deterioration, better
performance from repeat customers). The corresponding SQL queries live in
{dataset}_sql_queries-cn.md and are designed to expose these traps.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
import random

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, Boolean, Date, Numeric, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "fintech_smb_lending_pipeline_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date to guarantee deterministic generation. All "today / current snapshot"
# calculations are anchored here, so multiple runs yield reproducible results regardless of the
# system clock, and payment dates always fall within a bounded window.
REFERENCE_DATE = date(2026, 6, 3)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# Business calibration constants
# ============================================================================

# Per-grade default probabilities for **first-time borrowers**. Repeat customers
# (is_repeat_customer=True, roughly 12% of the base) default at half these rates
# (see REPEAT_DEFAULT_MULTIPLIER), and another ~5% of would-be defaults are suppressed
# by feasibility clipping (loan too new to default yet). So the pool-level observed
# default rate ends up a few points below the first-time rate.
# Grade C is the core pricing mismatch: first-time 12% combined with the portfolio's
# grade mix yields a pool-level observed ~10% — about 4pp above the pricing model's
# 6.0% assumption. Grades A and B land within implied ±1pp; D and E are mildly underpriced (~1-2pp).
GRADE_FIRSTTIME_DEFAULT_RATE = {
    1: 0.035,  # A - Prime           (implied 3.0%; pool-level ~4%, mildly over)
    2: 0.065,  # B - Near Prime      (implied 6.0%; pool-level ~6%, near priced)
    3: 0.120,  # C - Standard        (implied 6.0%; pool-level ~10% — about 4pp underpriced)
    4: 0.150,  # D - Subprime        (implied 13.0%; pool-level ~15%, ~2pp under)
    5: 0.220,  # E - Deep Subprime   (implied 18.0%; pool-level ~19%, mildly under)
}

# Repeat customers default at half the first-time rate (the Q5 lifetime-value thesis).
REPEAT_DEFAULT_MULTIPLIER = 0.5

# Industry weights tilt the portfolio toward Restaurant / Tech / Construction,
# so Q2's concentration analysis has real concentration to find.
INDUSTRY_WEIGHTS = {
    1: 18,   # Restaurant
    2: 8,    # Retail
    3: 12,   # Technology Services
    4: 10,   # Construction
    5: 5,    # Healthcare Services
    6: 5,    # Professional Services
    7: 5,    # Manufacturing
    8: 5,    # Wholesale Trade
    9: 5,    # Transportation
    10: 5,   # Real Estate
    11: 9,   # Hospitality
    12: 3,   # Education
    13: 3,   # Automotive Services
    14: 3,   # Beauty & Personal Care
    15: 5,   # Other Services
}

# Target grade distribution for non-repeat customers — used to decide which credit scores
# to draw for them. Skewed lower because the approval gate (below) filters originations upward,
# so to get a balanced post-approval grade mix the customer pool itself needs to be riskier.
NONREPEAT_GRADE_WEIGHTS = {
    1: 12,  # A
    2: 22,  # B
    3: 28,  # C
    4: 25,  # D
    5: 13,  # E
}

# Repeat customers skew toward better grades, but not entirely prime.
REPEAT_GRADE_WEIGHTS = {
    1: 35,
    2: 30,
    3: 20,
    4: 10,
    5: 5,
}

# Share of customers flagged as repeat. They take more applications than non-repeat customers,
# so the flag stays consistent with the underlying behavior.
REPEAT_CUSTOMER_SHARE = 0.15

# Share of defaults that exhibit observable warning signals (lateness / partial payments)
# in the final installments — the premise behind Q4.
WARNING_RATE = 0.72

# Probability that a non-defaulted active loan pays off early. Tuned so the overall
# PAID_OFF rate lands near the ER document's ~20% target.
EARLY_PAYOFF_PROB = 0.18

# Recovery-rate range at default per grade. Higher-grade borrowers tend to recover better
# (more cooperative, better collateral, cleaner documentation); deep-subprime defaults
# recover the least. Q10 reads these numbers.
GRADE_RECOVERY_RANGE = {
    1: (0.45, 0.65),  # A: mean ~55%
    2: (0.40, 0.55),  # B: mean ~47%
    3: (0.30, 0.45),  # C: mean ~37%
    4: (0.25, 0.40),  # D: mean ~32%
    5: (0.15, 0.30),  # E: mean ~22%
}


def approval_probability(credit_score: int) -> float:
    """Return approval probability bucketed by credit score.

    Higher scores see more approvals; very low scores rarely get approved. The bands
    are deliberately loose at the top and tight at the bottom, so Q3 can find rejected
    applicants whose profiles look like already-approved borrowers
    (about 20-25% leakage in the rejected pool).
    """
    if credit_score >= 720:
        return 0.95
    if credit_score >= 680:
        return 0.88
    if credit_score >= 640:
        return 0.78
    if credit_score >= 600:
        return 0.55
    return 0.35


def pick_credit_score(is_repeat: bool) -> int:
    """Draw a credit score whose target grade matches the expected distribution."""
    weights = REPEAT_GRADE_WEIGHTS if is_repeat else NONREPEAT_GRADE_WEIGHTS
    grade_id = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]
    # Grade bands match the risk_grade table below.
    bands = {
        1: (720, 820),
        2: (680, 719),
        3: (640, 679),
        4: (600, 639),
        5: (550, 599),
    }
    lo, hi = bands[grade_id]
    return random.randint(lo, hi)


def amortization_remaining(principal: float, monthly_rate: float, monthly_payment: float, k: int) -> float:
    """Remaining principal after k installments paid under standard amortization."""
    if k <= 0:
        return principal
    if monthly_rate == 0:
        return max(0.0, principal - monthly_payment * k)
    factor = (1 + monthly_rate) ** k
    return max(0.0, principal * factor - monthly_payment * (factor - 1) / monthly_rate)


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Industry(Base):
    """Industry classification for borrowing businesses."""
    __tablename__ = "industry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    industry_name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_rate_baseline: Mapped[float] = mapped_column(Float, nullable=False)


class RiskGrade(Base):
    """Risk grade tier with pricing parameters."""
    __tablename__ = "risk_grade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grade_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    grade_name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    implied_default_rate: Mapped[float] = mapped_column(Float, nullable=False)


class LoanStatus(Base):
    """Loan application and lifecycle status."""
    __tablename__ = "loan_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status_category: Mapped[str] = mapped_column(String(20), nullable=False)


class LoanOfficer(Base):
    """Loan officer who processes applications."""
    __tablename__ = "loan_officer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    hire_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)


class Customer(Base):
    """Business borrower."""
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    industry_id: Mapped[int] = mapped_column(Integer, ForeignKey("industry.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    founded_year: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_revenue: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_score: Mapped[int] = mapped_column(Integer, nullable=False)  # FICO-style score of the principal / guarantor (300-850)
    first_contact_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    is_repeat_customer: Mapped[bool] = mapped_column(Boolean, default=False)


class Application(Base):
    """Loan application."""
    __tablename__ = "application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    loan_officer_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_officer.id"), nullable=False)
    requested_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    requested_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    application_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    decision_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_status.id"), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Loan(Base):
    """Approved and disbursed loan."""
    __tablename__ = "loan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("application.id"), nullable=False, unique=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    risk_grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_grade.id"), nullable=False)
    approved_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_payment: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    disbursement_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    current_status_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_status.id"), nullable=False)
    outstanding_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class RepaymentSchedule(Base):
    """Expected monthly repayment schedule for each loan."""
    __tablename__ = "repayment_schedule"
    __table_args__ = (
        UniqueConstraint("loan_id", "installment_number", name="uq_repayment_schedule_loan_installment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan.id", ondelete="CASCADE"), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    scheduled_payment: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    principal_portion: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    interest_portion: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    remaining_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class Payment(Base):
    """Actual payment received from a borrower."""
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan.id", ondelete="CASCADE"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    payment_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    days_late: Mapped[int] = mapped_column(Integer, default=0)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)


class DefaultEvent(Base):
    """Default event with early-warning indicators."""
    __tablename__ = "default_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan.id"), nullable=False, unique=True)
    default_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    installments_missed: Mapped[int] = mapped_column(Integer, nullable=False)
    outstanding_at_default: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recovery_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    loss_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    had_early_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_signals: Mapped[str | None] = mapped_column(String(500), nullable=True)


# ============================================================================
# Data generators
# ============================================================================

def gen_industries() -> pl.DataFrame:
    """Generate industry classification records."""
    industries = [
        (1, "REST", "Restaurant", 9.5),
        (2, "RETAIL", "Retail", 8.2),
        (3, "TECH", "Technology Services", 4.1),
        (4, "CONST", "Construction", 11.3),
        (5, "HEALTH", "Healthcare Services", 5.8),
        (6, "PROF", "Professional Services", 6.2),
        (7, "MANUF", "Manufacturing", 7.4),
        (8, "WHOLE", "Wholesale Trade", 6.9),
        (9, "TRANSP", "Transportation", 10.1),
        (10, "REALES", "Real Estate", 8.8),
        (11, "HOSPIT", "Hospitality", 12.4),
        (12, "EDUC", "Education", 4.6),
        (13, "AUTO", "Automotive Services", 7.8),
        (14, "BEAUTY", "Beauty & Personal Care", 9.2),
        (15, "OTHER", "Other Services", 8.5),
    ]
    return pl.DataFrame(
        industries,
        schema=["id", "industry_code", "industry_name", "default_rate_baseline"],
        orient="row",
    )


def gen_risk_grades() -> pl.DataFrame:
    """Generate risk grade tiers."""
    grades = [
        (1, "A", "Prime", 720, 850, 5.5, 3.0),
        (2, "B", "Near Prime", 680, 719, 7.5, 6.0),
        (3, "C", "Standard", 640, 679, 9.5, 6.0),  # pricing mismatch — pool-level observed ~10% (about 4pp above implied 6%)
        (4, "D", "Subprime", 600, 639, 12.5, 13.0),
        (5, "E", "Deep Subprime", 300, 599, 16.0, 18.0),
    ]
    return pl.DataFrame(
        grades,
        schema=["id", "grade_code", "grade_name", "min_credit_score", "max_credit_score", "interest_rate", "implied_default_rate"],
        orient="row",
    )


def gen_loan_statuses() -> pl.DataFrame:
    """Generate loan status codes."""
    statuses = [
        (1, "PENDING", "Pending Review", "Application"),
        (2, "UNDER_REVIEW", "Under Review", "Application"),
        (3, "APPROVED", "Approved", "Application"),
        (4, "REJECTED", "Rejected", "Application"),
        (5, "DISBURSED", "Disbursed", "Active"),
        (6, "CURRENT", "Current", "Active"),
        (7, "DEFAULTED", "Defaulted", "Closed"),
        (8, "PAID_OFF", "Paid Off", "Closed"),
    ]
    return pl.DataFrame(
        statuses,
        schema=["id", "status_code", "status_name", "status_category"],
        orient="row",
    )


def gen_loan_officers() -> pl.DataFrame:
    """Generate loan officer records."""
    regions = ["Northern CA", "Southern CA", "Bay Area", "Central Valley"]
    records = []
    for i in range(1, 21):
        records.append({
            "id": i,
            "employee_id": f"LO{str(i).zfill(4)}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": f"lo{str(i).zfill(4)}@pacificbridge.com",
            "hire_date": fake.date_between(start_date="-5y", end_date="-6m"),
            "region": random.choice(regions),
        })
    return pl.DataFrame(records)


def gen_customers(n: int = 800) -> pl.DataFrame:
    """Generate business customer records.

    Repeat-customer status is pre-assigned (~15%), and credit scores are drawn so the
    final grade distribution matches NONREPEAT_/REPEAT_GRADE_WEIGHTS. first_contact_date
    is anchored far enough before any reasonable application_date to keep the temporal
    ordering valid.
    """
    industry_ids = list(INDUSTRY_WEIGHTS.keys())
    industry_weights = list(INDUSTRY_WEIGHTS.values())

    ca_cities = ["Los Angeles", "San Francisco", "San Diego", "Sacramento", "San Jose",
                 "Fresno", "Oakland", "Bakersfield", "Anaheim", "Riverside"]

    # First-contact date is well before the earliest possible application date
    contact_start = REFERENCE_DATE - timedelta(days=int(3 * 365))
    contact_end = REFERENCE_DATE - timedelta(days=int(2 * 365 + 60))

    records = []
    for i in range(1, n + 1):
        is_repeat = random.random() < REPEAT_CUSTOMER_SHARE
        credit_score = pick_credit_score(is_repeat)

        # Revenue / employee size roughly follows credit quality — higher-credit borrowers
        # tend to be larger / more mature. Not a strict rule.
        size_multiplier = 1.0 + (credit_score - 600) / 600.0
        revenue = int(random.randint(200_000, 4_500_000) * max(0.5, min(2.0, size_multiplier)))
        employees = random.randint(5, 150)
        founded_year = random.randint(1990, 2020)

        records.append({
            "id": i,
            "business_name": fake.company(),
            "tax_id": fake.unique.bothify(text="##-#######"),
            "industry_id": random.choices(industry_ids, weights=industry_weights, k=1)[0],
            "state": "CA",
            "city": random.choice(ca_cities),
            "founded_year": founded_year,
            "annual_revenue": revenue,
            "employee_count": employees,
            "credit_score": credit_score,
            "first_contact_date": fake.date_between(start_date=contact_start, end_date=contact_end),
            "is_repeat_customer": is_repeat,
        })

    fake.unique.clear()
    return pl.DataFrame(records)


def gen_applications(customers: pl.DataFrame, officer_ids: list[int], n: int = 3000) -> pl.DataFrame:
    """Generate loan application records.

    Repeat customers get disproportionately more applications so the is_repeat_customer
    flag roughly matches each customer's actual loan count. Approval is gated by
    credit_score (with deliberate top-of-funnel leakage retained).
    """
    rejection_reasons_by_band = {
        "low_credit": ["Insufficient credit history", "Credit score below threshold", "Recent bankruptcy"],
        "mid_credit": ["DTI ratio too high", "Unstable revenue", "Industry risk concentration"],
        "high_credit": ["Collateral insufficient", "Documentation incomplete", "Industry risk concentration"],
    }
    approved_status_id = 3
    rejected_status_id = 4

    # Lightly weight repeat customers (2x) so they get slightly more applications than non-repeat,
    # while keeping their share of total loans moderate (~20-25%). is_repeat_customer is best
    # thought of as a customer tier flag set at onboarding (loyalty / premium) rather than a count
    # derived from loan history — but this bias keeps the two loosely correlated.
    is_repeat_lookup = dict(zip(customers["id"].to_list(), customers["is_repeat_customer"].to_list()))
    credit_lookup = dict(zip(customers["id"].to_list(), customers["credit_score"].to_list()))

    customer_pool = customers["id"].to_list()
    customer_weights = [2 if is_repeat_lookup[cid] else 1 for cid in customer_pool]

    # Application date window: from REFERENCE_DATE, -22 months to -3 months. Slightly tighter
    # than before so loans have time to mature, and so payment generation never crosses
    # REFERENCE_DATE.
    app_start = REFERENCE_DATE - timedelta(days=int(22 * 30))
    app_end = REFERENCE_DATE - timedelta(days=int(3 * 30))

    records = []
    for i in range(1, n + 1):
        customer_id = random.choices(customer_pool, weights=customer_weights, k=1)[0]
        app_date = fake.date_between(start_date=app_start, end_date=app_end)
        decision_date = app_date + timedelta(days=random.randint(3, 21))

        credit_score = credit_lookup[customer_id]
        is_approved = random.random() < approval_probability(credit_score)
        status_id = approved_status_id if is_approved else rejected_status_id

        if is_approved:
            rejection_reason = None
        elif credit_score >= 680:
            rejection_reason = random.choice(rejection_reasons_by_band["high_credit"])
        elif credit_score >= 600:
            rejection_reason = random.choice(rejection_reasons_by_band["mid_credit"])
        else:
            rejection_reason = random.choice(rejection_reasons_by_band["low_credit"])

        records.append({
            "id": i,
            "application_number": f"APP-{str(i).zfill(6)}",
            "customer_id": customer_id,
            "loan_officer_id": random.choice(officer_ids),
            "requested_amount": random.randint(50, 500) * 1000,
            "requested_term_months": random.choice([12, 24, 36, 48, 60]),
            "application_date": app_date,
            "decision_date": decision_date,
            "status_id": status_id,
            "rejection_reason": rejection_reason,
        })

    return pl.DataFrame(records)


def gen_loans(applications: pl.DataFrame, customers: pl.DataFrame, risk_grades: pl.DataFrame) -> pl.DataFrame:
    """Generate loan records for approved applications.

    Status is determined jointly by "grade + repeat-driven default probability" and
    "feasibility of elapsed time since disbursement," so payment dates always land on
    or before REFERENCE_DATE. outstanding_balance is computed directly from the amortization
    formula at the point of the most recent paid installment.

    Temporarily adds a private column ``_payments_made`` for use by gen_payments, dropped
    before the TSV is exported.
    """
    is_repeat_lookup = dict(zip(customers["id"].to_list(), customers["is_repeat_customer"].to_list()))
    credit_lookup = dict(zip(customers["id"].to_list(), customers["credit_score"].to_list()))

    grade_rows = list(risk_grades.iter_rows(named=True))

    def grade_for_score(score: int) -> dict:
        for g in grade_rows:
            if g["min_credit_score"] <= score <= g["max_credit_score"]:
                return g
        return grade_rows[-1]

    records = []
    loan_counter = 1
    approved_apps = applications.filter(pl.col("status_id") == 3)

    for row in approved_apps.iter_rows(named=True):
        app_id = row["id"]
        customer_id = row["customer_id"]
        requested_amount = row["requested_amount"]
        requested_term = row["requested_term_months"]
        decision_date = row["decision_date"]

        credit_score = credit_lookup[customer_id]
        is_repeat = is_repeat_lookup[customer_id]

        # Roughly 15% of loans are booked at a grade noticeably lower than the customer's
        # current credit score (credit score improved after funding — common in SMB lending:
        # annual credit refreshes capture the score lift from on-time payments). These loans
        # surface as repricing candidates in Q16, because customer.credit_score is the latest
        # value while loan.risk_grade_id is frozen at booking time.
        score_drift = random.randint(40, 80) if random.random() < 0.15 else 0
        score_at_origination = max(550, credit_score - score_drift)

        grade = grade_for_score(score_at_origination)
        risk_grade_id = grade["id"]
        interest_rate = grade["interest_rate"]

        approved_amount = round(requested_amount * random.uniform(0.9, 1.0), 2)
        term_months = requested_term

        monthly_rate = interest_rate / 100 / 12
        if monthly_rate == 0:
            monthly_payment = approved_amount / term_months
        else:
            monthly_payment = approved_amount * (monthly_rate * (1 + monthly_rate) ** term_months) / \
                              ((1 + monthly_rate) ** term_months - 1)
        monthly_payment = round(monthly_payment, 2)

        disbursement_date = decision_date + timedelta(days=random.randint(3, 10))
        maturity_date = disbursement_date + timedelta(days=term_months * 30)
        months_since_disbursement = max(1, (REFERENCE_DATE - disbursement_date).days // 30)

        # Default probability is driven by grade x repeat status.
        base_default = GRADE_FIRSTTIME_DEFAULT_RATE[risk_grade_id]
        default_prob = base_default * (REPEAT_DEFAULT_MULTIPLIER if is_repeat else 1.0)

        will_default = random.random() < default_prob

        if will_default and months_since_disbursement >= 4:
            # Default has occurred. The borrower made some payments before stopping.
            current_status_id = 7  # DEFAULTED
            max_payments = min(months_since_disbursement - 1, term_months - 1, 15)
            payments_made = random.randint(3, max(3, max_payments))
        elif months_since_disbursement >= term_months:
            # Loan reached maturity without defaulting.
            current_status_id = 8  # PAID_OFF
            payments_made = term_months
        elif not will_default and months_since_disbursement >= 6 and random.random() < EARLY_PAYOFF_PROB:
            # Early payoff — borrower paid the loan off ahead of schedule.
            current_status_id = 8  # PAID_OFF
            payments_made = months_since_disbursement
        else:
            # Still active (either genuinely performing, or will eventually default but hasn't yet).
            current_status_id = 6  # CURRENT
            payments_made = months_since_disbursement

        if current_status_id == 8:
            outstanding_balance = 0.0
        else:
            outstanding_balance = amortization_remaining(
                approved_amount, monthly_rate, monthly_payment, payments_made
            )

        # Pre-decide whether this default will exhibit observable warning signals. gen_payments
        # uses it to degrade the final 3 installments; gen_default_events uses it to set
        # had_early_warning. Carrying the decision on the loan row lets gen_payments and
        # gen_default_events stay independent of shared module state.
        has_warning = current_status_id == 7 and random.random() < WARNING_RATE

        records.append({
            "id": loan_counter,
            "loan_number": f"LN-{str(loan_counter).zfill(6)}",
            "application_id": app_id,
            "customer_id": customer_id,
            "risk_grade_id": risk_grade_id,
            "approved_amount": approved_amount,
            "interest_rate": interest_rate,
            "term_months": term_months,
            "monthly_payment": monthly_payment,
            "disbursement_date": disbursement_date,
            "maturity_date": maturity_date,
            "current_status_id": current_status_id,
            "outstanding_balance": round(outstanding_balance, 2),
            "_payments_made": payments_made,
            "_has_warning": has_warning,
        })
        loan_counter += 1

    return pl.DataFrame(records)


def gen_repayment_schedules(loans: pl.DataFrame) -> pl.DataFrame:
    """Generate the full scheduled monthly repayment table for each loan."""
    records = []
    schedule_id = 1

    for loan_row in loans.iter_rows(named=True):
        loan_id = loan_row["id"]
        approved_amount = loan_row["approved_amount"]
        term_months = loan_row["term_months"]
        monthly_payment = loan_row["monthly_payment"]
        interest_rate = loan_row["interest_rate"]
        disbursement_date = loan_row["disbursement_date"]

        monthly_rate = interest_rate / 100 / 12
        remaining_balance = approved_amount

        for i in range(1, term_months + 1):
            due_date = disbursement_date + timedelta(days=i * 30)
            interest_portion = remaining_balance * monthly_rate
            principal_portion = monthly_payment - interest_portion
            remaining_balance = max(0, remaining_balance - principal_portion)

            records.append({
                "id": schedule_id,
                "loan_id": loan_id,
                "installment_number": i,
                "due_date": due_date,
                "scheduled_payment": round(monthly_payment, 2),
                "principal_portion": round(principal_portion, 2),
                "interest_portion": round(interest_portion, 2),
                "remaining_balance": round(remaining_balance, 2),
            })
            schedule_id += 1

    return pl.DataFrame(records)


def gen_payments(loans: pl.DataFrame, schedules: pl.DataFrame) -> pl.DataFrame:
    """Generate actual payment records.

    For DEFAULTED loans flagged with warning signals (the ``_has_warning`` column on the loan row,
    pre-decided in gen_loans), the last 3 installments before default are degraded (more lateness,
    more partial payments) — so Q4's analysis can actually detect the pattern.
    """
    records = []
    payment_id = 1
    payment_methods = ["ACH", "Wire Transfer", "Check", "Credit Card"]

    # Index schedules by loan_id for O(1) lookup, avoiding repeated filter calls.
    schedules_by_loan: dict[int, list[dict]] = {}
    for s in schedules.iter_rows(named=True):
        schedules_by_loan.setdefault(s["loan_id"], []).append(s)

    for loan_row in loans.iter_rows(named=True):
        loan_id = loan_row["id"]
        monthly_payment = loan_row["monthly_payment"]
        payments_made = loan_row["_payments_made"]
        has_warning = loan_row["_has_warning"]

        loan_schedules = sorted(schedules_by_loan.get(loan_id, []), key=lambda s: s["installment_number"])

        # "Last 3 installments" deterioration. When payments_made=N and start=N-2,
        # i is in {N-2, N-1, N} — exactly 3 installments.
        deterioration_start = payments_made - 2 if has_warning else payments_made + 1

        for i in range(1, payments_made + 1):
            schedule_row = loan_schedules[i - 1]
            due_date = schedule_row["due_date"]

            in_deterioration_window = i >= deterioration_start

            # Timing of payment.
            if in_deterioration_window:
                # Mostly late, often quite late.
                late_roll = random.random()
                if late_roll < 0.20:
                    days_late = 0
                elif late_roll < 0.60:
                    days_late = random.randint(8, 20)
                else:
                    days_late = random.randint(20, 30)
            else:
                # Baseline: 70% on time / 20% mildly late / 10% seriously late.
                late_roll = random.random()
                if late_roll < 0.70:
                    days_late = 0
                elif late_roll < 0.90:
                    days_late = random.randint(1, 15)
                else:
                    days_late = random.randint(16, 30)
            payment_date = due_date + timedelta(days=days_late)

            # Payment amount.
            if in_deterioration_window:
                # Partial payments are common within the deterioration window.
                if random.random() < 0.45:
                    payment_amount = monthly_payment * random.uniform(0.50, 0.85)
                else:
                    payment_amount = monthly_payment
            else:
                if random.random() < 0.95:
                    payment_amount = monthly_payment
                else:
                    payment_amount = monthly_payment * random.uniform(0.5, 0.9)

            records.append({
                "id": payment_id,
                "loan_id": loan_id,
                "payment_date": payment_date,
                "payment_amount": round(payment_amount, 2),
                "installment_number": i,
                "days_late": days_late,
                "payment_method": random.choice(payment_methods),
            })
            payment_id += 1

    return pl.DataFrame(records)


def gen_default_events(loans: pl.DataFrame, payments: pl.DataFrame, schedules: pl.DataFrame) -> pl.DataFrame:
    """Generate default event records.

    had_early_warning and warning_signals are derived from the loan's actual last 3 payments —
    so the flag can never contradict the data, and Q4 can correlate behavior with default.

    outstanding_at_default is taken from the amortization table at the most recent paid installment,
    not pulled out of thin air.
    """
    records = []
    event_id = 1

    defaulted_loans = loans.filter(pl.col("current_status_id") == 7)

    # Index payments by loan for fast lookup.
    payments_by_loan: dict[int, list[dict]] = {}
    for p in payments.iter_rows(named=True):
        payments_by_loan.setdefault(p["loan_id"], []).append(p)

    schedules_by_loan: dict[int, list[dict]] = {}
    for s in schedules.iter_rows(named=True):
        schedules_by_loan.setdefault(s["loan_id"], []).append(s)

    for loan_row in defaulted_loans.iter_rows(named=True):
        loan_id = loan_row["id"]
        monthly_payment = loan_row["monthly_payment"]
        outstanding_balance = loan_row["outstanding_balance"]
        term_months = loan_row["term_months"]

        loan_payments = sorted(payments_by_loan.get(loan_id, []), key=lambda p: p["installment_number"])
        if not loan_payments:
            continue

        last_payment = loan_payments[-1]
        last_payment_date = last_payment["payment_date"]
        payments_made = len(loan_payments)

        # Industry-standard 90 DPD default declaration: 90 days after the last missed due date
        # (the first scheduled due date the borrower didn't pay).
        loan_schedules = sorted(schedules_by_loan.get(loan_id, []), key=lambda s: s["installment_number"])
        if payments_made < len(loan_schedules):
            first_missed_due = loan_schedules[payments_made]["due_date"]
        else:
            first_missed_due = last_payment_date
        default_date = min(first_missed_due + timedelta(days=90), REFERENCE_DATE)

        # installments_missed = scheduled installments that came due since the last payment but
        # were never paid (capped at the remaining term).
        months_since_last = max(1, (REFERENCE_DATE - last_payment_date).days // 30)
        installments_missed = min(term_months - payments_made, months_since_last)

        # had_early_warning is the flag pre-decided in gen_loans (carried on the loan row's
        # _has_warning column) — it determines which 72% of defaults will show deterioration
        # in their final 3 installments. warning_signals is then derived from the actual data;
        # if the deterioration window happens to look clean (due to random variance), we fall
        # back to a generic description so the flag and the signal text never contradict.
        had_early_warning = loan_row["_has_warning"]
        if had_early_warning:
            recent = loan_payments[-3:]
            late_count = sum(1 for p in recent if p["days_late"] > 10)
            partial_count = sum(1 for p in recent if p["payment_amount"] < monthly_payment * 0.90)
            signals = []
            if late_count > 0:
                signals.append(f"{late_count} late payments in last 3 months")
            if partial_count > 0:
                signals.append(f"{partial_count} partial payments")
            if not signals:
                signals.append("Account-review notes flagged deteriorating cash flow")
            warning_signals = "; ".join(signals)
        else:
            warning_signals = None

        # Recovery rate is grade-driven (better borrowers -> better recovery).
        lo, hi = GRADE_RECOVERY_RANGE[loan_row["risk_grade_id"]]
        recovery_rate = random.uniform(lo, hi)
        recovery_amount = outstanding_balance * recovery_rate
        loss_amount = outstanding_balance - recovery_amount

        records.append({
            "id": event_id,
            "loan_id": loan_id,
            "default_date": default_date,
            "installments_missed": installments_missed,
            "outstanding_at_default": round(outstanding_balance, 2),
            "recovery_amount": round(recovery_amount, 2),
            "loss_amount": round(loss_amount, 2),
            "had_early_warning": had_early_warning,
            "warning_signals": warning_signals,
        })
        event_id += 1

    return pl.DataFrame(records)


# ============================================================================
# Core functions (idempotent)
# ============================================================================
def generate_all_tsv() -> None:
    """Generate all TSV files. Idempotent: existing files are removed first."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating industry classifications...")
    df_industries = gen_industries()
    df_industries.write_csv(DATA_DIR / "01_industry.tsv", separator="\t")

    print("Generating risk grades...")
    df_risk_grades = gen_risk_grades()
    df_risk_grades.write_csv(DATA_DIR / "02_risk_grade.tsv", separator="\t")

    print("Generating loan statuses...")
    df_statuses = gen_loan_statuses()
    df_statuses.write_csv(DATA_DIR / "03_loan_status.tsv", separator="\t")

    print("Generating loan officers...")
    df_officers = gen_loan_officers()
    df_officers.write_csv(DATA_DIR / "04_loan_officer.tsv", separator="\t")

    print("Generating customers...")
    df_customers = gen_customers(n=800)
    df_customers.write_csv(DATA_DIR / "05_customer.tsv", separator="\t")

    print("Generating applications...")
    df_applications = gen_applications(
        customers=df_customers,
        officer_ids=df_officers["id"].to_list(),
        n=3000,
    )
    df_applications.write_csv(DATA_DIR / "06_application.tsv", separator="\t")

    print("Generating loans...")
    df_loans = gen_loans(df_applications, df_customers, df_risk_grades)

    print("Generating repayment schedules...")
    df_schedules = gen_repayment_schedules(df_loans)
    df_schedules.write_csv(DATA_DIR / "08_repayment_schedule.tsv", separator="\t")

    print("Generating payments...")
    df_payments = gen_payments(df_loans, df_schedules)
    df_payments.write_csv(DATA_DIR / "09_payment.tsv", separator="\t")

    print("Generating default events...")
    df_defaults = gen_default_events(df_loans, df_payments, df_schedules)
    df_defaults.write_csv(DATA_DIR / "10_default_event.tsv", separator="\t")

    # Drop the generator-only private columns before persisting the loan table.
    df_loans_out = df_loans.drop(["_payments_made", "_has_warning"])
    df_loans_out.write_csv(DATA_DIR / "07_loan.tsv", separator="\t")

    total = (
        len(df_industries) + len(df_risk_grades) + len(df_statuses) + len(df_officers)
        + len(df_customers) + len(df_applications) + len(df_loans_out)
        + len(df_schedules) + len(df_payments) + len(df_defaults)
    )
    print(f"\nGenerated all TSV files in {DATA_DIR}")
    print(f"Total rows: {total}")


def create_sqlite_database() -> None:
    """Create SQLite database from TSV files. Idempotent: existing database is removed first."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    print("\nLoading data into SQLite database...")

    load_order = [
        ("01_industry.tsv", "industry"),
        ("02_risk_grade.tsv", "risk_grade"),
        ("03_loan_status.tsv", "loan_status"),
        ("04_loan_officer.tsv", "loan_officer"),
        ("05_customer.tsv", "customer"),
        ("06_application.tsv", "application"),
        ("07_loan.tsv", "loan"),
        ("08_repayment_schedule.tsv", "repayment_schedule"),
        ("09_payment.tsv", "payment"),
        ("10_default_event.tsv", "default_event"),
    ]
    for filename, table in load_order:
        df = pl.read_csv(DATA_DIR / filename, separator="\t")
        df.to_pandas().to_sql(table, engine, if_exists="append", index=False)
        print(f"Loaded {len(df)} rows into {table}")

    print(f"\nCreated SQLite database at {DATABASE_PATH}")


def main() -> None:
    """Main entry point."""
    print("=" * 80)
    print("Pacific Bridge Lending - SMB Lending Pipeline Data Generator")
    print(f"Reference date (anchor for 'today'): {REFERENCE_DATE}")
    print("=" * 80)
    print("\nStarting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("\n" + "=" * 80)
    print("All done! Dataset ready for analysis.")
    print("=" * 80)


if __name__ == "__main__":
    main()
