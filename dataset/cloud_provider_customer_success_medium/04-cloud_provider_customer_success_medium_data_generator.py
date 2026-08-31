"""
Cloud Provider - Customer Success Management Fake Data Generator
Complexity: Medium (Review-01 fixed version)
Generation tool: Fake Data Generator Agent

Business context:
Simulates the customer success management scenario for an AWS/Azure/GCP-style cloud
provider. The CSM team needs to track customer health, usage trends, and renewal
risk, and to identify expansion opportunities.

Review-01 fix summary:
- Added `csm` employee table, with assignments specialized by tier (Enterprise / Mid-Market / SMB)
- subscription.monthly_committed_spend is bucketed by tier; start_date >= customer.created_at
- health_score sub-scores are sampled independently; overall = weighted average (causal direction corrected)
- support_tickets are inversely correlated with the customer health baseline (validates the Query 14 hypothesis)
- usage_metrics / interaction_log / csm_task timestamps are all constrained by customer.created_at
- Added UNIQUE constraints (usage_metrics, health_score)
- customer.is_active is derived from its subscription statuses for consistency
- Schema parity fixes (NULLABLE aligned with the ER document)
"""

from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import polars as pl
from faker import Faker
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "cloud_provider_customer_success_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# Date helpers
# ============================================================================
def first_of_month_n_ago(reference: date, n: int) -> date:
    """Return the first day of the month that is n months before reference (precise month arithmetic)."""
    new_month = reference.month - n
    new_year = reference.year + (new_month - 1) // 12 if new_month <= 0 else reference.year
    if new_month <= 0:
        new_month = ((new_month - 1) % 12) + 1
    return date(new_year, new_month, 1)


def add_months(d: date, months: int) -> date:
    """Precise month add/subtract, handling year crossover and end-of-month day overflow."""
    total = d.month - 1 + months
    new_year = d.year + total // 12
    new_month = total % 12 + 1
    last_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(d.day, last_day)
    return date(new_year, new_month, new_day)


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class AccountTier(Base):
    """Customer account tier."""
    __tablename__ = "account_tier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(200))
    monthly_min_spend: Mapped[float] = mapped_column(Float, nullable=False)
    support_level: Mapped[str] = mapped_column(String(50))


class HealthScoreReason(Base):
    """Reason types for health-score changes."""
    __tablename__ = "health_score_reason"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    impact_direction: Mapped[str] = mapped_column(String(20))
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class InteractionType(Base):
    """Customer interaction types."""
    __tablename__ = "interaction_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(200))
    is_proactive: Mapped[bool] = mapped_column(Boolean, default=True)


class Region(Base):
    """Cloud service regions."""
    __tablename__ = "region"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    continent: Mapped[str] = mapped_column(String(50))


class Csm(Base):
    """Customer Success Manager (CSM) employee master table (added in Review-01)."""
    __tablename__ = "csm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    territory_region_id: Mapped[int] = mapped_column(Integer, ForeignKey("region.id"), nullable=False)
    tier_specialization: Mapped[str] = mapped_column(String(20), nullable=False)  # Enterprise / Mid-Market / SMB
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base):
    """Customer company entity."""
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(100))
    employee_count: Mapped[int] = mapped_column(Integer)
    account_tier_id: Mapped[int] = mapped_column(Integer, ForeignKey("account_tier.id"), nullable=False)
    primary_region_id: Mapped[int] = mapped_column(Integer, ForeignKey("region.id"), nullable=False)
    csm_id: Mapped[int] = mapped_column(Integer, ForeignKey("csm.id"), nullable=False)
    account_owner_email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    """Customer subscription / contract information."""
    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    monthly_committed_spend: Mapped[float] = mapped_column(Float, nullable=False)
    discount_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")


class UsageMetrics(Base):
    """Customer monthly usage metrics."""
    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint("customer_id", "month_year", name="uq_usage_customer_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    month_year: Mapped[date] = mapped_column(Date, nullable=False)
    compute_spend: Mapped[float] = mapped_column(Float, default=0.0)
    storage_spend: Mapped[float] = mapped_column(Float, default=0.0)
    network_spend: Mapped[float] = mapped_column(Float, default=0.0)
    ai_ml_spend: Mapped[float] = mapped_column(Float, default=0.0)
    total_spend: Mapped[float] = mapped_column(Float, nullable=False)
    active_services_count: Mapped[int] = mapped_column(Integer, default=1)
    support_tickets_count: Mapped[int] = mapped_column(Integer, default=0)


class HealthScore(Base):
    """Customer health-score history (Review-01: sub-scores sampled independently; overall is derived as a weighted average)."""
    __tablename__ = "health_score"
    __table_args__ = (
        UniqueConstraint("customer_id", "score_date", name="uq_health_customer_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    score_date: Mapped[date] = mapped_column(Date, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_score: Mapped[int] = mapped_column(Integer, nullable=False)
    engagement_score: Mapped[int] = mapped_column(Integer, nullable=False)
    support_score: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_reason_id: Mapped[int] = mapped_column(Integer, ForeignKey("health_score_reason.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CsmTask(Base):
    """CSM tasks and follow-up items."""
    __tablename__ = "csm_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class InteractionLog(Base):
    """Customer interaction records."""
    __tablename__ = "interaction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    interaction_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("interaction_type.id"), nullable=False)
    interaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attendees_count: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False)


# ============================================================================
# Enum / lookup table generation
# ============================================================================
def gen_account_tiers() -> pl.DataFrame:
    records = [
        {"id": 1, "name": "Enterprise", "description": "Large enterprise customers with dedicated support and custom SLAs", "monthly_min_spend": 50000.0, "support_level": "Enterprise"},
        {"id": 2, "name": "Business", "description": "Growing businesses with business-level support", "monthly_min_spend": 10000.0, "support_level": "Business"},
        {"id": 3, "name": "Pro", "description": "Professional tier for SMBs", "monthly_min_spend": 1000.0, "support_level": "Developer"},
        {"id": 4, "name": "Basic", "description": "Basic tier for startups and small projects", "monthly_min_spend": 0.0, "support_level": "Basic"},
    ]
    return pl.DataFrame(records)


def gen_health_score_reasons() -> pl.DataFrame:
    records = [
        {"id": 1, "code": "USAGE_INCREASE", "name": "Usage increased significantly", "impact_direction": "positive", "weight": 1.5},
        {"id": 2, "code": "USAGE_DECREASE", "name": "Usage decreased significantly", "impact_direction": "negative", "weight": 2.0},
        {"id": 3, "code": "HIGH_ENGAGEMENT", "name": "High engagement with CSM team", "impact_direction": "positive", "weight": 1.2},
        {"id": 4, "code": "LOW_ENGAGEMENT", "name": "Low engagement with CSM team", "impact_direction": "negative", "weight": 1.5},
        {"id": 5, "code": "SUPPORT_ISSUES", "name": "Multiple support tickets unresolved", "impact_direction": "negative", "weight": 1.8},
        {"id": 6, "code": "NEW_SERVICES", "name": "Adopted new services", "impact_direction": "positive", "weight": 1.3},
        {"id": 7, "code": "CONTRACT_RISK", "name": "Contract renewal at risk", "impact_direction": "negative", "weight": 2.5},
        {"id": 8, "code": "EXPANSION_OPPORTUNITY", "name": "Expansion opportunity identified", "impact_direction": "positive", "weight": 1.0},
    ]
    return pl.DataFrame(records)


def gen_interaction_types() -> pl.DataFrame:
    records = [
        {"id": 1, "name": "QBR Meeting", "description": "Quarterly Business Review meeting", "is_proactive": True},
        {"id": 2, "name": "Technical Review", "description": "Technical architecture review session", "is_proactive": True},
        {"id": 3, "name": "Email", "description": "Email communication", "is_proactive": True},
        {"id": 4, "name": "Phone Call", "description": "Phone call with customer", "is_proactive": True},
        {"id": 5, "name": "Support Escalation", "description": "Escalated support issue discussion", "is_proactive": False},
        {"id": 6, "name": "Training Session", "description": "Product training or workshop", "is_proactive": True},
    ]
    return pl.DataFrame(records)


def gen_regions() -> pl.DataFrame:
    records = [
        {"id": 1, "code": "us-east-1", "name": "US East (N. Virginia)", "continent": "North America"},
        {"id": 2, "code": "us-west-2", "name": "US West (Oregon)", "continent": "North America"},
        {"id": 3, "code": "eu-west-1", "name": "Europe (Ireland)", "continent": "Europe"},
        {"id": 4, "code": "eu-central-1", "name": "Europe (Frankfurt)", "continent": "Europe"},
        {"id": 5, "code": "ap-northeast-1", "name": "Asia Pacific (Tokyo)", "continent": "Asia Pacific"},
        {"id": 6, "code": "ap-southeast-1", "name": "Asia Pacific (Singapore)", "continent": "Asia Pacific"},
        {"id": 7, "code": "ap-south-1", "name": "Asia Pacific (Mumbai)", "continent": "Asia Pacific"},
        {"id": 8, "code": "sa-east-1", "name": "South America (São Paulo)", "continent": "South America"},
        {"id": 9, "code": "ca-central-1", "name": "Canada (Central)", "continent": "North America"},
        {"id": 10, "code": "me-south-1", "name": "Middle East (Bahrain)", "continent": "Middle East"},
    ]
    return pl.DataFrame(records)


# ============================================================================
# Main table generation (Review-01 hardened version)
# ============================================================================
def gen_csms(region_ids: List[int]) -> pl.DataFrame:
    """
    Generate CSM employees. Group by tier specialization to ensure Enterprise/Mid-Market/SMB
    serve their corresponding customer cohorts.

    Review-02 fixes:
    - Keep the first.last separator dot in email (the Fix-01 version mistakenly stripped all dots)
    - Introduce 2 CSMs with is_active=False (simulating departures), so the WHERE csm.is_active=1 filter in Query 16 is meaningful
    """
    # Distribution: 4 Enterprise + 6 Mid-Market + 5 SMB = 15 people
    specs = [("Enterprise", 4), ("Mid-Market", 6), ("SMB", 5)]
    # 2 departed CSMs: pick non-Enterprise CSMs with relatively few customers to avoid disrupting the main test path
    # (the 6th in Mid-Market and the 5th in SMB; both are the last in their group. Customer assignment uses all CSMs, but some customers may still be attached to them.)
    inactive_csm_ids = {10, 15}
    records = []
    csm_id = 1
    for spec, count in specs:
        for _ in range(count):
            name = fake.name()
            # Strip punctuation (commas, apostrophes) and turn spaces into dots, so the email reads as first.last
            email_local = name.lower().replace(",", "").replace("'", "").replace(" ", ".")
            # Append csm_id suffix to guarantee email uniqueness
            email = f"{email_local}.{csm_id}@cloudprovider.com"
            hire_date = fake.date_between(start_date="-7y", end_date="-6m")
            records.append({
                "id": csm_id,
                "name": name,
                "email": email,
                "hire_date": hire_date,
                "territory_region_id": random.choice(region_ids),
                "tier_specialization": spec,
                "is_active": csm_id not in inactive_csm_ids,
            })
            csm_id += 1
    return pl.DataFrame(records)


def gen_customers(
    n: int,
    tier_ids: List[int],
    region_ids: List[int],
    csm_df: pl.DataFrame,
) -> tuple[pl.DataFrame, list[dict]]:
    """
    Generate customer companies. Returns (the persisted DataFrame, an internal record list that includes health_baseline).
    health_baseline is not persisted but is consumed by downstream functions to keep health_score and support_tickets consistent.
    """
    industries = [
        "Financial Services", "Healthcare", "Retail", "Technology", "Manufacturing",
        "Media & Entertainment", "Education", "Government", "Energy", "Transportation",
        "Real Estate", "Telecommunications", "Life Sciences", "Gaming", "Automotive",
    ]
    tier_weights = {1: 0.15, 2: 0.30, 3: 0.35, 4: 0.20}

    # Group csm_id by specialization (Review-02: use only is_active=True CSMs,
    # simulating inactive CSMs' customers being reassigned to active peers with the same specialization)
    csm_by_spec: dict[str, list[int]] = {}
    for row in csm_df.iter_rows(named=True):
        if not row["is_active"]:
            continue
        csm_by_spec.setdefault(row["tier_specialization"], []).append(row["id"])

    persistent: list[dict] = []
    internal: list[dict] = []

    for i in range(1, n + 1):
        tier_id = random.choices(tier_ids, weights=[tier_weights.get(t, 0.25) for t in tier_ids])[0]

        if tier_id == 1:  # Enterprise
            employee_count = random.randint(5000, 100000)
            eligible_csms = csm_by_spec["Enterprise"]
        elif tier_id == 2:  # Business
            employee_count = random.randint(500, 10000)
            eligible_csms = csm_by_spec["Mid-Market"]
        elif tier_id == 3:  # Pro
            employee_count = random.randint(50, 1000)
            eligible_csms = csm_by_spec["Mid-Market"] + csm_by_spec["SMB"]
        else:  # Basic
            employee_count = random.randint(5, 100)
            eligible_csms = csm_by_spec["SMB"]

        csm_id = random.choice(eligible_csms)
        # Loosen to -1m so that time-series constraints are meaningful
        created_at = fake.date_time_between(start_date="-3y", end_date="-1m")
        # Health baseline (internal use): drives the coupling between support_tickets and health_score
        health_baseline = random.randint(45, 95)

        rec = {
            "id": i,
            "company_name": fake.company(),
            "industry": random.choice(industries),
            "employee_count": employee_count,
            "account_tier_id": tier_id,
            "primary_region_id": random.choice(region_ids),
            "csm_id": csm_id,
            "account_owner_email": fake.company_email(),
            "created_at": created_at,
            # is_active is a placeholder for now; derived later from subscription status
            "is_active": True,
        }
        persistent.append(rec)
        internal.append({**rec, "health_baseline": health_baseline})

    return pl.DataFrame(persistent), internal


def gen_subscriptions(customer_records: list[dict]) -> pl.DataFrame:
    """
    Generate subscriptions. Review-01 fixes:
    - monthly_committed_spend is bucketed by tier instead of ignoring tier
    - discount_percentage skews higher for higher tiers
    - contract_start_date >= customer.created_at
    """
    records = []
    sub_id = 1
    today = date.today()

    # Committed-spend range by tier (aligned with or higher than account_tier.monthly_min_spend)
    tier_spend_range = {
        1: (50000, 500000),   # Enterprise
        2: (10000, 80000),    # Business
        3: (1000, 15000),     # Pro
        4: (100, 3000),       # Basic
    }
    tier_discount_range = {
        1: (10, 30),
        2: (5, 20),
        3: (0, 10),
        4: (0, 5),
    }

    for cust in customer_records:
        cid = cust["id"]
        tier_id = cust["account_tier_id"]
        created_dt = cust["created_at"]
        created_date = created_dt.date() if isinstance(created_dt, datetime) else created_dt

        # Most customers have 1 subscription, some have 2
        num_subs = random.choices([1, 2], weights=[0.85, 0.15])[0]
        spend_lo, spend_hi = tier_spend_range[tier_id]
        disc_lo, disc_hi = tier_discount_range[tier_id]

        for _ in range(num_subs):
            # contract_start >= created_at and <= today - 3m (contract signed at least 3 months ago)
            min_start = created_date
            max_start = today - timedelta(days=90)
            if min_start > max_start:
                contract_start = min_start
            else:
                contract_start = fake.date_between(start_date=min_start, end_date=max_start)

            contract_length_months = random.choice([12, 24, 36])
            contract_end = add_months(contract_start, contract_length_months)

            monthly_spend = round(random.uniform(spend_lo, spend_hi), 2)
            discount = round(random.uniform(disc_lo, disc_hi), 1)

            if contract_end < today - timedelta(days=30):
                status = random.choices(["expired", "churned"], weights=[0.7, 0.3])[0]
            elif contract_end < today + timedelta(days=90):
                status = "pending_renewal"
            else:
                status = "active"

            records.append({
                "id": sub_id,
                "customer_id": cid,
                "contract_start_date": contract_start,
                "contract_end_date": contract_end,
                "monthly_committed_spend": monthly_spend,
                "discount_percentage": discount,
                "auto_renewal": random.random() > 0.3,
                "status": status,
            })
            sub_id += 1

    return pl.DataFrame(records)


def derive_customer_is_active(df_customer: pl.DataFrame, df_sub: pl.DataFrame) -> pl.DataFrame:
    """
    Review-01 fix: customer.is_active is derived from subscription status for consistency.
    If all of the customer's subscription statuses are in {churned, expired} -> is_active = False; otherwise True.
    """
    statuses_by_cust = df_sub.group_by("customer_id").agg(
        pl.col("status").alias("statuses")
    )
    statuses_dict: dict[int, list[str]] = {
        row["customer_id"]: row["statuses"]
        for row in statuses_by_cust.iter_rows(named=True)
    }

    def is_active_for(cid: int) -> bool:
        statuses = statuses_dict.get(cid, [])
        if not statuses:
            return True
        return any(s not in ("churned", "expired") for s in statuses)

    return df_customer.with_columns(
        pl.col("id").map_elements(is_active_for, return_dtype=pl.Boolean).alias("is_active")
    )


def gen_usage_metrics(customer_records: list[dict], months: int = 6) -> pl.DataFrame:
    """
    Generate monthly usage. Review-01 fixes:
    - base_compute / base_storage / base_network / active_services scale by tier
    - support_tickets are inversely driven by health_baseline (validates the Query 14 hypothesis)
    - month_year >= the month after the month containing customer.created_at
    """
    records = []
    metric_id = 1
    today = date.today()
    current_month_first = date(today.year, today.month, 1)

    # Per-tier usage baselines and service-count ranges
    tier_usage_profile = {
        1: {  # Enterprise
            "compute": (20000, 150000),
            "storage": (5000, 30000),
            "network": (2000, 10000),
            "ai_ml_max": 50000,
            "services": (10, 30),
        },
        2: {  # Business
            "compute": (5000, 30000),
            "storage": (1500, 10000),
            "network": (500, 3000),
            "ai_ml_max": 15000,
            "services": (5, 18),
        },
        3: {  # Pro
            "compute": (500, 5000),
            "storage": (200, 2000),
            "network": (50, 500),
            "ai_ml_max": 3000,
            "services": (3, 10),
        },
        4: {  # Basic
            "compute": (50, 800),
            "storage": (20, 300),
            "network": (5, 100),
            "ai_ml_max": 500,
            "services": (1, 6),
        },
    }

    for cust in customer_records:
        cid = cust["id"]
        tier_id = cust["account_tier_id"]
        created_dt = cust["created_at"]
        created_date = created_dt.date() if isinstance(created_dt, datetime) else created_dt
        health_baseline = cust["health_baseline"]
        profile = tier_usage_profile[tier_id]

        base_compute = random.uniform(*profile["compute"])
        base_storage = random.uniform(*profile["storage"])
        base_network = random.uniform(*profile["network"])
        # 60% of customers use AI/ML
        use_ai_ml = random.random() > 0.4
        base_ai_ml = random.uniform(0, profile["ai_ml_max"]) if use_ai_ml else 0.0

        trend = random.choices(["growing", "stable", "declining"], weights=[0.4, 0.35, 0.25])[0]

        for m in range(months):
            month_first = first_of_month_n_ago(current_month_first, months - m)
            # Time-series constraint: skip months before customer creation
            if month_first < date(created_date.year, created_date.month, 1):
                continue

            if trend == "growing":
                factor = 1 + (m * 0.05) + random.uniform(-0.05, 0.10)
            elif trend == "declining":
                factor = 1 - (m * 0.03) + random.uniform(-0.05, 0.05)
            else:
                factor = 1 + random.uniform(-0.10, 0.10)
            factor = max(0.30, factor)

            compute = round(base_compute * factor, 2)
            storage = round(base_storage * factor * random.uniform(0.9, 1.1), 2)
            network = round(base_network * factor * random.uniform(0.8, 1.2), 2)
            ai_ml = round(base_ai_ml * factor * random.uniform(0.7, 1.5), 2) if base_ai_ml > 0 else 0.0
            total = round(compute + storage + network + ai_ml, 2)

            services_count = random.randint(*profile["services"])

            # Support tickets ~ inversely correlated with health_baseline
            # health_baseline is in [45, 95]; lower baseline means a higher expected ticket count
            health_factor = (100 - health_baseline) / 55  # ~0.09 ~ 1.0
            tickets_mean = 1 + health_factor * 7  # roughly 1.6 ~ 8
            tickets = max(0, int(round(random.gauss(tickets_mean, max(1.0, tickets_mean * 0.4)))))

            records.append({
                "id": metric_id,
                "customer_id": cid,
                "month_year": month_first,
                "compute_spend": compute,
                "storage_spend": storage,
                "network_spend": network,
                "ai_ml_spend": ai_ml,
                "total_spend": total,
                "active_services_count": services_count,
                "support_tickets_count": tickets,
            })
            metric_id += 1

    return pl.DataFrame(records)


def gen_health_scores(
    customer_records: list[dict],
    reason_ids: List[int],
    avg_tickets_by_customer: dict[int, float],
    months: int = 3,
) -> pl.DataFrame:
    """
    Generate health scores.

    Review-01 fixes:
    - Sub-scores (usage / engagement / support) are sampled independently; overall = weighted average (4/3/3)
    - support_score is inversely driven by the average ticket count over the full usage_metrics window (up to the last 6 months), consistent with the ER document
    - score_date is no earlier than customer.created_at

    Review-02 note: avg_tickets_by_customer is computed by generate_all_tsv() after usage_metrics is generated,
    using all usage_metrics rows via group_by(customer_id).agg(mean), so the window is the actual usage_metrics coverage months.
    """
    records = []
    score_id = 1
    today = date.today()

    for cust in customer_records:
        cid = cust["id"]
        created_dt = cust["created_at"]
        created_date = created_dt.date() if isinstance(created_dt, datetime) else created_dt
        baseline = cust["health_baseline"]
        avg_tickets = avg_tickets_by_customer.get(cid, 3.0)

        for m in range(months):
            score_date = today - timedelta(days=30 * (months - 1 - m))
            if score_date < created_date:
                continue

            usage_score = min(100, max(0, int(round(baseline + random.gauss(0, 8)))))
            engagement_score = min(100, max(0, int(round(baseline + random.gauss(0, 10)))))
            # More tickets -> lower support_score
            support_score = min(100, max(0, int(round(95 - avg_tickets * 6 + random.gauss(0, 6)))))

            # Weighted average: usage 40%, engagement 30%, support 30%
            overall = int(round(usage_score * 0.4 + engagement_score * 0.3 + support_score * 0.3))
            overall = min(100, max(0, overall))

            # Primary reason depends on the overall range
            if overall < 50:
                reason_id = random.choice([2, 4, 5, 7])
            elif overall > 80:
                reason_id = random.choice([1, 3, 6, 8])
            else:
                reason_id = random.choice(reason_ids)

            notes = None
            if overall < 60:
                notes = random.choice([
                    "Customer showing signs of disengagement",
                    "Usage dropped significantly this month",
                    "Multiple unresolved support tickets",
                    "Contract renewal at risk - needs immediate attention",
                    "Competitor mentioned in recent conversations",
                ])
            elif overall > 85:
                notes = random.choice([
                    "Strong engagement, potential expansion opportunity",
                    "Very satisfied with recent support experience",
                    "Interested in adopting new services",
                    "Excellent QBR feedback received",
                ])

            records.append({
                "id": score_id,
                "customer_id": cid,
                "score_date": score_date,
                "overall_score": overall,
                "usage_score": usage_score,
                "engagement_score": engagement_score,
                "support_score": support_score,
                "primary_reason_id": reason_id,
                "notes": notes,
            })
            score_id += 1

    return pl.DataFrame(records)


def gen_csm_tasks(
    customer_records: list[dict],
    customer_statuses: dict[int, set[str]],
    n: int = 300,
) -> pl.DataFrame:
    """
    Generate CSM tasks.

    Review-01 fix: created_at >= customer.created_at

    Review-02 fix (lightweight coupling between task_type and customer state):
    - Churned/expired-only customers no longer get new tasks (CSM no longer proactively serves them)
    - pending_renewal customers skew toward renewal_prep
    - active high-baseline (>=75) customers skew toward expansion_opportunity / training
    - active low-baseline (<60) customers skew toward risk_mitigation
    - active medium-baseline customers get a balanced distribution
    """
    # (type_code, title_base, desc_base)
    task_templates = {
        "renewal_prep": ("Prepare renewal proposal", "Review usage patterns and prepare renewal proposal"),
        "expansion_opportunity": ("Explore expansion opportunity", "Customer showing interest in additional services"),
        "risk_mitigation": ("Address churn risk", "Customer health score declining - need intervention"),
        "qbr_scheduling": ("Schedule QBR meeting", "Quarterly business review due"),
        "onboarding": ("Complete onboarding", "Help customer adopt new services"),
        "training": ("Schedule training session", "Customer requested product training"),
    }
    priorities = ["low", "medium", "high", "critical"]
    priority_weights = [0.15, 0.45, 0.30, 0.10]
    statuses = ["open", "in_progress", "completed", "cancelled"]
    status_weights = [0.30, 0.25, 0.40, 0.05]

    cust_by_id = {c["id"]: c for c in customer_records}

    # Only assign tasks to customers that still have active (or pending_renewal) subscriptions
    eligible_customer_ids: list[int] = []
    for cid in cust_by_id.keys():
        sub_statuses = customer_statuses.get(cid, set())
        if any(s in ("active", "pending_renewal") for s in sub_statuses):
            eligible_customer_ids.append(cid)

    def task_type_weights_for(cid: int) -> tuple[list[str], list[float]]:
        sub_statuses = customer_statuses.get(cid, set())
        baseline = cust_by_id[cid].get("health_baseline", 70)
        # pending_renewal takes priority (any active renewal customer needs a proposal)
        if "pending_renewal" in sub_statuses:
            return (
                ["renewal_prep", "qbr_scheduling", "training", "expansion_opportunity", "risk_mitigation", "onboarding"],
                [0.45, 0.20, 0.10, 0.10, 0.10, 0.05],
            )
        # Sub-segmentation for active-only customers
        if baseline >= 75:
            return (
                ["expansion_opportunity", "training", "qbr_scheduling", "onboarding", "renewal_prep", "risk_mitigation"],
                [0.35, 0.20, 0.20, 0.15, 0.05, 0.05],
            )
        if baseline < 60:
            return (
                ["risk_mitigation", "qbr_scheduling", "training", "onboarding", "expansion_opportunity", "renewal_prep"],
                [0.45, 0.20, 0.15, 0.10, 0.05, 0.05],
            )
        # Active customers with a medium baseline: relatively balanced
        return (
            ["qbr_scheduling", "training", "expansion_opportunity", "onboarding", "risk_mitigation", "renewal_prep"],
            [0.25, 0.20, 0.20, 0.15, 0.15, 0.05],
        )

    records = []
    now = datetime.now()

    for i in range(1, n + 1):
        cid = random.choice(eligible_customer_ids)
        types, weights = task_type_weights_for(cid)
        task_type = random.choices(types, weights=weights)[0]
        title_base, desc_base = task_templates[task_type]

        cust_created = cust_by_id[cid]["created_at"]
        if not isinstance(cust_created, datetime):
            cust_created = datetime.combine(cust_created, datetime.min.time())

        # Task created_at: after max(customer creation time, last 6 months)
        earliest = max(cust_created, now - timedelta(days=180))
        if earliest >= now:
            earliest = cust_created  # Edge case: customer just created
        created_at = fake.date_time_between(start_date=earliest, end_date=now)
        due_date = (created_at + timedelta(days=random.randint(7, 60))).date()

        status = random.choices(statuses, weights=status_weights)[0]
        completed_at = None
        if status == "completed":
            completed_at = created_at + timedelta(days=random.randint(1, 30))

        records.append({
            "id": i,
            "customer_id": cid,
            "task_type": task_type,
            "title": f"{title_base} for Customer #{cid}",
            "description": desc_base,
            "due_date": due_date,
            "priority": random.choices(priorities, weights=priority_weights)[0],
            "status": status,
            "created_at": created_at,
            "completed_at": completed_at,
        })

    return pl.DataFrame(records)


def gen_interaction_logs(
    customer_records: list[dict],
    interaction_type_ids: List[int],
    n: int = 400,
) -> pl.DataFrame:
    """Generate customer interaction records. Review-01 fix: interaction_date >= customer.created_at."""
    sentiments = ["positive", "neutral", "negative"]
    sentiment_weights = [0.45, 0.40, 0.15]

    cust_by_id = {c["id"]: c for c in customer_records}
    customer_ids = list(cust_by_id.keys())

    now = datetime.now()
    summaries = [
        "Discussed upcoming renewal and expansion opportunities",
        "Reviewed architecture and provided optimization recommendations",
        "Addressed support concerns and outlined resolution plan",
        "Presented new product features and gathered feedback",
        "Conducted training on best practices",
        "Followed up on action items from previous meeting",
        "Introduced new team members and reviewed account status",
    ]

    records = []
    for i in range(1, n + 1):
        cid = random.choice(customer_ids)
        cust_created = cust_by_id[cid]["created_at"]
        if not isinstance(cust_created, datetime):
            cust_created = datetime.combine(cust_created, datetime.min.time())

        earliest = max(cust_created, now - timedelta(days=180))
        if earliest >= now:
            earliest = cust_created
        interaction_date = fake.date_time_between(start_date=earliest, end_date=now)

        itype = random.choice(interaction_type_ids)
        if itype == 1:  # QBR
            duration, attendees = random.randint(45, 90), random.randint(3, 8)
        elif itype == 2:  # Technical Review
            duration, attendees = random.randint(30, 120), random.randint(2, 6)
        elif itype == 3:  # Email
            duration, attendees = None, 1
        elif itype == 4:  # Phone
            duration, attendees = random.randint(10, 45), random.randint(1, 3)
        elif itype == 5:  # Support Escalation
            duration, attendees = random.randint(20, 60), random.randint(2, 5)
        else:  # Training
            duration, attendees = random.randint(60, 180), random.randint(3, 15)

        records.append({
            "id": i,
            "customer_id": cid,
            "interaction_type_id": itype,
            "interaction_date": interaction_date,
            "duration_minutes": duration,
            "attendees_count": attendees,
            "summary": random.choice(summaries),
            "sentiment": random.choices(sentiments, weights=sentiment_weights)[0],
            "follow_up_required": random.random() > 0.6,
        })

    return pl.DataFrame(records)


# ============================================================================
# Core functions (idempotent)
# ============================================================================
def generate_all_tsv() -> None:
    """Generate all TSV files. Clears existing .tsv files before writing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("正在生成枚举/字典表...")
    df_tiers = gen_account_tiers()
    df_tiers.write_csv(DATA_DIR / "01_account_tier.tsv", separator="\t")
    print(f"  - account_tier: {len(df_tiers)} 行")

    df_reasons = gen_health_score_reasons()
    df_reasons.write_csv(DATA_DIR / "02_health_score_reason.tsv", separator="\t")
    print(f"  - health_score_reason: {len(df_reasons)} 行")

    df_interaction_types = gen_interaction_types()
    df_interaction_types.write_csv(DATA_DIR / "03_interaction_type.tsv", separator="\t")
    print(f"  - interaction_type: {len(df_interaction_types)} 行")

    df_regions = gen_regions()
    df_regions.write_csv(DATA_DIR / "04_region.tsv", separator="\t")
    print(f"  - region: {len(df_regions)} 行")

    region_ids = df_regions["id"].to_list()
    df_csm = gen_csms(region_ids=region_ids)
    df_csm.write_csv(DATA_DIR / "05_csm.tsv", separator="\t")
    print(f"  - csm: {len(df_csm)} 行")

    print("\n正在生成核心业务表...")
    tier_ids = df_tiers["id"].to_list()
    df_customers, customer_records = gen_customers(
        n=150, tier_ids=tier_ids, region_ids=region_ids, csm_df=df_csm
    )

    # Generate subscriptions first, then derive customer.is_active from them
    df_subscriptions = gen_subscriptions(customer_records=customer_records)
    df_customers = derive_customer_is_active(df_customers, df_subscriptions)
    # Sync the is_active field back into the internal records
    is_active_map = {row["id"]: row["is_active"] for row in df_customers.iter_rows(named=True)}
    for r in customer_records:
        r["is_active"] = is_active_map.get(r["id"], True)

    df_customers.write_csv(DATA_DIR / "06_customer.tsv", separator="\t")
    print(f"  - customer: {len(df_customers)} 行")

    df_subscriptions.write_csv(DATA_DIR / "07_subscription.tsv", separator="\t")
    print(f"  - subscription: {len(df_subscriptions)} 行")

    df_usage = gen_usage_metrics(customer_records=customer_records, months=6)
    df_usage.write_csv(DATA_DIR / "08_usage_metrics.tsv", separator="\t")
    print(f"  - usage_metrics: {len(df_usage)} 行")

    # Compute each customer's recent average ticket count, used by health_score
    tickets_summary = df_usage.group_by("customer_id").agg(
        pl.col("support_tickets_count").mean().alias("avg_tickets")
    )
    avg_tickets_by_customer = {
        row["customer_id"]: float(row["avg_tickets"])
        for row in tickets_summary.iter_rows(named=True)
    }

    reason_ids = df_reasons["id"].to_list()
    df_health = gen_health_scores(
        customer_records=customer_records,
        reason_ids=reason_ids,
        avg_tickets_by_customer=avg_tickets_by_customer,
        months=3,
    )
    df_health.write_csv(DATA_DIR / "09_health_score.tsv", separator="\t")
    print(f"  - health_score: {len(df_health)} 行")

    # Compute the set of subscription statuses per customer, used by gen_csm_tasks for the lightweight task_type vs. status coupling
    customer_statuses: dict[int, set[str]] = {}
    for row in df_subscriptions.iter_rows(named=True):
        customer_statuses.setdefault(row["customer_id"], set()).add(row["status"])

    df_tasks = gen_csm_tasks(
        customer_records=customer_records,
        customer_statuses=customer_statuses,
        n=300,
    )
    df_tasks.write_csv(DATA_DIR / "10_csm_task.tsv", separator="\t")
    print(f"  - csm_task: {len(df_tasks)} 行")

    interaction_type_ids = df_interaction_types["id"].to_list()
    df_interactions = gen_interaction_logs(
        customer_records=customer_records,
        interaction_type_ids=interaction_type_ids,
        n=400,
    )
    df_interactions.write_csv(DATA_DIR / "11_interaction_log.tsv", separator="\t")
    print(f"  - interaction_log: {len(df_interactions)} 行")

    print(f"\n已在 {DATA_DIR} 生成所有 TSV 文件")


def _parse_optional_datetime(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    return datetime.fromisoformat(value)


def _parse_optional_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _parse_optional_str(value) -> Optional[str]:
    if value is None or value == "":
        return None
    return value


def create_sqlite_database() -> None:
    """Create a SQLite database from the TSV files. Removes the old database first."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        print("\n正在加载数据到 SQLite...")

        df = pl.read_csv(DATA_DIR / "01_account_tier.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(AccountTier(**row))
        print(f"  - account_tier: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "02_health_score_reason.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(HealthScoreReason(**row))
        print(f"  - health_score_reason: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "03_interaction_type.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(InteractionType(**row))
        print(f"  - interaction_type: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "04_region.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Region(**row))
        print(f"  - region: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "05_csm.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["hire_date"] = date.fromisoformat(row["hire_date"])
            session.add(Csm(**row))
        print(f"  - csm: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "06_customer.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["created_at"] = datetime.fromisoformat(row["created_at"])
            session.add(Customer(**row))
        print(f"  - customer: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "07_subscription.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["contract_start_date"] = date.fromisoformat(row["contract_start_date"])
            row["contract_end_date"] = date.fromisoformat(row["contract_end_date"])
            session.add(Subscription(**row))
        print(f"  - subscription: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "08_usage_metrics.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["month_year"] = date.fromisoformat(row["month_year"])
            session.add(UsageMetrics(**row))
        print(f"  - usage_metrics: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "09_health_score.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["score_date"] = date.fromisoformat(row["score_date"])
            row["notes"] = _parse_optional_str(row.get("notes"))
            session.add(HealthScore(**row))
        print(f"  - health_score: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "10_csm_task.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["due_date"] = date.fromisoformat(row["due_date"])
            row["created_at"] = datetime.fromisoformat(row["created_at"])
            row["completed_at"] = _parse_optional_datetime(row.get("completed_at"))
            session.add(CsmTask(**row))
        print(f"  - csm_task: {len(df)} 行已加载")

        df = pl.read_csv(DATA_DIR / "11_interaction_log.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row["interaction_date"] = datetime.fromisoformat(row["interaction_date"])
            row["duration_minutes"] = _parse_optional_int(row.get("duration_minutes"))
            row["summary"] = _parse_optional_str(row.get("summary"))
            row["sentiment"] = _parse_optional_str(row.get("sentiment"))
            session.add(InteractionLog(**row))
        print(f"  - interaction_log: {len(df)} 行已加载")

        session.commit()

    print(f"\n已在 {DATABASE_PATH} 创建 SQLite 数据库")


def main() -> None:
    print("=" * 60)
    print("云服务商 - 客户成功管理 数据生成器 (Review-01 修复版)")
    print("=" * 60)
    print()
    generate_all_tsv()
    create_sqlite_database()
    print()
    print("=" * 60)
    print("全部完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
