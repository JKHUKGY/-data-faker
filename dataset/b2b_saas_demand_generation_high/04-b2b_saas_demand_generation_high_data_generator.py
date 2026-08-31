"""
B2B SaaS - Demand Generation and Marketing Operations Fake Data Generator
Complexity: High (16 tables, ~100,000 rows)
Produced by the Fake Data Generator Agent

Business Context
================
Stratosend is a fictional North American B2B SaaS company that sells an API
observability platform (think Datadog / New Relic / Honeycomb, but focused on
API performance, errors, latency, and dependency mapping). Revenue is ARR-based
and splits across three customer tiers (SMB / Mid-Market / Enterprise), with
deal sizes from $5K to over $500K. The motion is sales-assisted: nearly every
deal requires a demo plus an evaluation, and Enterprise-level deals routinely
involve 5-7 stakeholders, multi-month POCs, and a procurement approval flow.

The dataset covers 18 months of historical demand-generation and sales activity,
plus in-flight campaigns and open opportunities across every stage. The 16-table
schema supports:

  * Full-funnel analytics: Lead -> MQL -> SQL -> Opp -> Won
  * Multi-touch attribution across campaigns and content (W-shaped)
  * Sales-pipeline analytics: stage velocity, win/loss, forecasting
  * Sales productivity: SDR SLAs, sequence performance, AE quota attainment
  * ABM (account-based marketing) engagement depth on target accounts
  * Content-asset influence and lead-scoring effectiveness

KEY INVARIANTS (enforced by the reconciliation passes)
==================================================
  * lead.lead_score = SUM(lead_scoring_event.points_awarded) per lead
  * lead.mql_date = MIN(occurred_at WHERE cumulative_score >= 100)
  * opportunity.current_stage_id = latest stage_transition.to_stage_id
  * opportunity.actual_close_date = time of transition into Closed-Won/Closed-Lost
  * account.lifetime_arr_won_usd = SUM(opportunity.amount_usd WHERE Won)
  * account.is_target_account = (id IN target_account_list)
  * content_asset.total_downloads = COUNT(content_engagement WHERE download)
  * campaign_member.attribution_credit_pct computed via W-shaped attribution
  * XOR constraint: campaign_member / content_engagement / sales_email each
    have lead_id XOR contact_id (exactly one non-NULL)
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import polars as pl
from faker import Faker
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "b2b_saas_demand_generation_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Reference "today" - deterministic generation
TODAY = date(2026, 6, 1)
HISTORY_START = TODAY - timedelta(days=540)   # 18 months back
FUTURE_END = TODAY + timedelta(days=30)       # 30 days of forward-looking plan

# Target row counts (~100k total)
N_SALES_REP = 40
N_ACCOUNT = 2_000
N_LEAD = 8_000
N_CONTACT = 3_000
N_CAMPAIGN = 80
N_CONTENT_ASSET = 150
N_OPPORTUNITY = 2_500   # Soft cap. gen_opportunity targets 75% from
                        # converted_to_contact leads + 25% direct outbound,
                        # but the converted pool is bounded by the natural
                        # funnel (~13% of N_LEAD ≈ 1,000 leads).
                        # Actual count typically lands between 1,600 and 1,700.
N_TARGET_ACCOUNT_LIST = 300
# Event-level (derived from the values above)
AVG_TRANSITIONS_PER_OPP = 4.5     # ~12,000 transition rows
AVG_CAMPAIGN_MEMBERS = 12_000
AVG_CONTENT_ENGAGEMENTS = 18_000
AVG_SALES_EMAILS = 30_000
AVG_SCORING_EVENTS = 45_000   # Soft target; actual count driven by per-lead distribution

# MQL threshold
MQL_SCORE_THRESHOLD = 100


# ============================================================================
# Static lookup-table data
# ============================================================================
LEAD_SOURCES = [
    # (code, name, category, typical_cpl_usd)
    ("INBOUND_DEMO_REQUEST",  "Inbound - Demo Request",       "Inbound",  0.0),
    ("INBOUND_FREE_TRIAL",    "Inbound - Free Trial",         "Inbound",  0.0),
    ("INBOUND_CONTENT_DOWNLOAD","Inbound - Content Download", "Inbound",  0.0),
    ("PAID_SEARCH_GOOGLE",    "Paid Search - Google",         "Inbound",  80.0),
    ("PAID_SOCIAL_LINKEDIN",  "Paid Social - LinkedIn",       "Inbound",  120.0),
    ("WEBINAR",               "Webinar Registration",         "Inbound",  50.0),
    ("CONFERENCE_EVENT",      "Conference / Industry Event",  "Event",    200.0),
    ("OUTBOUND_SDR",          "Outbound - SDR Sourced",       "Outbound", 0.0),
    ("PARTNER_REFERRAL",      "Partner Referral",             "Partner",  0.0),
    ("CONTENT_SYNDICATION",   "3rd-Party Content Syndication","Inbound",  35.0),
]

INDUSTRIES = [
    # (name, naics, typical_arr_band)
    ("Fintech",                  "522110", "Mid"),
    ("SaaS / Software",          "511210", "Mid"),
    ("Ecommerce",                "454110", "SMB"),
    ("Media & Entertainment",    "515210", "Mid"),
    ("Gaming",                   "713210", "SMB"),
    ("Healthcare Tech",          "621399", "Enterprise"),
    ("Manufacturing",            "333242", "Enterprise"),
    ("Education Tech",           "611310", "SMB"),
    ("Government / Public",      "921110", "Enterprise"),
    ("Telecom",                  "517311", "Enterprise"),
    ("Retail / CPG",             "452210", "Mid"),
    ("Logistics",                "488510", "Mid"),
]

OPPORTUNITY_STAGES = [
    # (name, order, is_closed, is_won, typical_win_prob_pct)
    ("Discovery",       1, False, False, 10.0),
    ("Demo",            2, False, False, 25.0),
    ("Evaluation/POC",  3, False, False, 40.0),
    ("Proposal",        4, False, False, 60.0),
    ("Negotiation",     5, False, False, 80.0),
    ("Closed-Won",      6, True,  True,  100.0),
    ("Closed-Lost",     7, True,  False, 0.0),
]

REGIONS = ["NA-East", "NA-West", "EMEA", "APAC"]
REGION_WEIGHTS = [0.40, 0.35, 0.15, 0.10]

EMPLOYEE_BANDS = ["1-50", "51-200", "201-1000", "1001-5000", "5000+"]
REVENUE_BANDS = ["<$10M", "$10M-$50M", "$50M-$250M", "$250M-$1B", "$1B+"]
ACCOUNT_TIERS = ["SMB", "Mid", "Enterprise"]
# 60/30/10 distribution
TIER_BY_EMP_BAND = {
    "1-50":     "SMB",
    "51-200":   "SMB",
    "201-1000": "Mid",
    "1001-5000":"Enterprise",
    "5000+":    "Enterprise",
}
EMP_BAND_WEIGHTS = [0.35, 0.25, 0.30, 0.07, 0.03]   # 60% SMB / 30% Mid / 10% Ent (Enterprise)

COUNTRY_WEIGHTS = [
    ("United States", 0.72),
    ("Canada",        0.10),
    ("United Kingdom",0.08),
    ("Germany",       0.05),
    ("Australia",     0.03),
    ("France",        0.02),
]

US_STATES = [
    "California", "New York", "Texas", "Massachusetts", "Washington",
    "Illinois", "Colorado", "Georgia", "Florida", "Virginia",
    "North Carolina", "Oregon", "Pennsylvania", "Ohio", "Michigan",
]

PERSONAS = ["Champion", "Economic Buyer", "Decision Maker", "Influencer", "Blocker"]
PERSONA_WEIGHTS = [0.30, 0.20, 0.15, 0.30, 0.05]

SENIORITIES = ["IC", "Manager", "Director", "VP", "CXO"]
SENIORITY_WEIGHTS = [0.40, 0.30, 0.18, 0.10, 0.02]

PERSONA_TO_TITLES = {
    "Champion":       ["Senior Software Engineer", "Staff Engineer", "Tech Lead",
                       "Senior SRE", "Principal Engineer", "Senior DevOps Engineer"],
    "Economic Buyer": ["Engineering Manager", "Director of Engineering",
                       "Director of Platform", "Director of DevOps"],
    "Decision Maker": ["VP Engineering", "VP Platform", "CTO", "Chief Architect",
                       "Head of Engineering"],
    "Influencer":     ["DevOps Engineer", "SRE", "Backend Engineer", "Platform Engineer"],
    "Blocker":        ["Security Architect", "CISO", "Procurement Manager",
                       "VP Legal", "InfoSec Lead"],
}

SENIORITY_BY_PERSONA = {
    "Champion":       "Manager",
    "Economic Buyer": "Director",
    "Decision Maker": "VP",
    "Influencer":     "IC",
    "Blocker":        "Director",
}

SDR_REP_ROLES = {
    "Manager":         4,
    "SDR":             12,
    "AE_SMB":          8,
    "AE_Mid":          8,
    "AE_Enterprise":   8,
}  # total = 40

CAMPAIGN_TYPES = [
    ("Webinar",                "MQLs Generated",      0.18),
    ("Email_Blast",            "Pipeline Influenced", 0.10),
    ("Paid_Search",            "MQLs Generated",      0.14),
    ("Paid_Social",            "MQLs Generated",      0.10),
    ("Content_Syndication",    "MQLs Generated",      0.08),
    ("Conference_Event",       "Pipeline Influenced", 0.12),
    ("ABM_Sequence",           "Pipeline Influenced", 0.13),
    ("SDR_Outbound_Sequence",  "SQLs",                0.15),
]

CAMPAIGN_STATUS_WEIGHTS = [
    ("COMPLETED", 0.60),
    ("ACTIVE",    0.30),
    ("PLANNED",   0.10),
]

ASSET_TYPES = [
    ("ebook",             0.18),
    ("whitepaper",        0.18),
    ("case_study",        0.18),
    ("webinar_recording", 0.18),
    ("blog_post",         0.18),
    ("analyst_report",    0.05),
    ("template",          0.05),
]

CONTENT_TOPICS = [
    "API Observability", "Distributed Tracing", "Kubernetes Monitoring",
    "OpenTelemetry", "Service Mesh", "SLO/SLI Practices",
    "Incident Response", "Microservices Debugging", "Cost Optimization",
    "API Security Monitoring", "Database Observability",
    "Frontend Performance", "Logging Best Practices",
]

LEAD_STATUSES = ["new", "working", "mql", "sql", "disqualified", "converted_to_contact"]

LEAD_DISQUAL_REASONS = [
    "Not ICP",
    "No budget",
    "Wrong contact",
    "Already a customer",
    "Competitor incumbent",
    "Company too small",
    "Region not supported",
    "Timeline too long",
]

WIN_LOSS_REASONS_WON = [
    "Product Fit - Best in Class",
    "Champion Mobilized",
    "Pricing Advantage",
    "Strong POC Results",
    "Replaced Competitor (Datadog)",
    "Executive Sponsorship",
]
WIN_LOSS_REASONS_LOST = [
    "Competitor (Datadog)",
    "Competitor (New Relic)",
    "Competitor (Honeycomb)",
    "Budget Cut",
    "Champion Left",
    "Project Postponed",
    "No Decision",
    "Insufficient ROI",
]

CONTENT_ENGAGEMENT_TYPES = ["download", "view", "share", "replay"]
CONTENT_ENGAGEMENT_WEIGHTS = [0.45, 0.40, 0.05, 0.10]

SCORING_RULES = [
    # (event_type, scoring_rule_name, points, weight)
    ("page_visit_pricing",       "Pricing Page Visit +20",        20,  0.10),
    ("content_download",         "Content Download +15",          15,  0.20),
    ("webinar_attend",           "Webinar Attended +30",          30,  0.10),
    ("email_click",              "Email Click +5",                 5,  0.20),
    ("demo_request",             "Demo Requested +50",            50,  0.05),
    ("multiple_visits_7d",       "Multi-Visit (3+/week) +25",     25,  0.08),
    ("free_trial_started",       "Free Trial Started +40",        40,  0.05),
    ("video_watched_50pct",      "Video Watched 50% +10",         10,  0.10),
    ("pricing_calc_used",        "Pricing Calculator Used +15",   15,  0.05),
    ("competitor_compare_view",  "Competitor Comparison Visited +10",10,0.05),
    ("unsubscribed",             "Unsubscribed -50",             -50,  0.02),
]

SDR_SEQUENCE_NAMES = [
    "Outbound Cold - Engineering Manager",
    "Outbound Cold - VP Engineering",
    "Outbound Cold - Director DevOps",
    "Outbound Warm - Webinar Attendee",
    "Webinar No-Show Follow-up",
    "Content Download Follow-up",
    "Free Trial Activation Nudge",
    "Re-engage Dormant - 90 day silence",
    "Fintech Vertical Outbound",
    "Conference Follow-up - KubeCon",
]

ABM_LIST_TEMPLATES = [
    "FY26 Enterprise NA-East Tier 1",
    "FY26 Enterprise NA-West Tier 1",
    "FY26 Enterprise EMEA Tier 1",
    "Fintech Expansion Wave Q2",
    "Healthcare Tech Tier 1",
    "Strategic Logos - Top 50",
    "Manufacturing Mid-Market Push",
    "Telecom Vertical Tier 2",
]


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    pass


class LeadSource(Base):
    """Marketing lead-source taxonomy (Inbound / Outbound / Partner / Event)."""
    __tablename__ = "lead_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source_category: Mapped[str] = mapped_column(String(20), nullable=False)
    typical_cost_per_lead_usd: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Industry(Base):
    """Target-industry taxonomy."""
    __tablename__ = "industry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry_name: Mapped[str] = mapped_column(String(60), nullable=False)
    naics_code: Mapped[str] = mapped_column(String(10), nullable=False)
    typical_arr_band: Mapped[str] = mapped_column(String(20), nullable=False)


class OpportunityStage(Base):
    """Standard B2B sales opportunity stages, in order."""
    __tablename__ = "opportunity_stage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    typical_win_probability_pct: Mapped[float] = mapped_column(Float, nullable=False)


class SalesRep(Base):
    """SDR / AE / Manager. The self-referencing FK on manager_id models the team hierarchy."""
    __tablename__ = "sales_rep"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    quota_usd: Mapped[float] = mapped_column(Float, nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Account(Base):
    """B2B customer / prospect company."""
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    industry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("industry.id"), nullable=False
    )
    employee_count_band: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_revenue_band: Mapped[str] = mapped_column(String(20), nullable=False)
    account_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(30), nullable=False)
    state_or_province: Mapped[str] = mapped_column(String(40), nullable=False)
    website: Mapped[str] = mapped_column(String(150), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    owner_ae_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=True
    )
    is_target_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lifetime_arr_won_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class Lead(Base):
    """Prospective buyer (from untouched to qualified)."""
    __tablename__ = "lead"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    seniority: Mapped[str] = mapped_column(String(20), nullable=False)
    persona: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead_source.id"), nullable=False
    )
    source_campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=True
    )
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    mql_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sql_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    converted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disqualified_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    assigned_sdr_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Contact(Base):
    """A contact engaged by sales (converted from a lead, or sourced via direct outbound)."""
    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lead.id"), nullable=True
    )
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    seniority: Mapped[str] = mapped_column(String(20), nullable=False)
    persona: Mapped[str] = mapped_column(String(30), nullable=False)
    role_in_deal: Mapped[str] = mapped_column(String(30), nullable=False)
    do_not_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Campaign(Base):
    """Marketing campaign (webinar, in-person event, paid media, ABM, SDR sequence)."""
    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    campaign_name: Mapped[str] = mapped_column(String(150), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    spend_to_date_usd: Mapped[float] = mapped_column(Float, nullable=False)
    target_persona: Mapped[str] = mapped_column(String(30), nullable=False)
    target_industry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("industry.id"), nullable=True
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=False
    )
    primary_kpi: Mapped[str] = mapped_column(String(40), nullable=False)
    # Plan-vs-actual targets (new fields)
    target_mql_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_pipeline_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ContentAsset(Base):
    """Marketing content asset (ebook, whitepaper, case study, webinar, etc.)."""
    __tablename__ = "content_asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    topic_tag: Mapped[str] = mapped_column(String(60), nullable=False)
    target_persona: Mapped[str] = mapped_column(String(30), nullable=False)
    is_gated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    asset_url: Mapped[str] = mapped_column(String(200), nullable=False)
    total_downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Opportunity(Base):
    """Sales opportunity (the core revenue entity)."""
    __tablename__ = "opportunity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=False
    )
    primary_contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id"), nullable=False
    )
    current_stage_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunity_stage.id"), nullable=False
    )
    owner_ae_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=False
    )
    sourced_by_sdr_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=True
    )
    source_lead_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lead.id"), nullable=True
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead_source.id"), nullable=False
    )
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    expected_close_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    won_lost_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)


class StageTransition(Base):
    """Event log of opportunity stage transitions. The new column snapshots the expected close date at each transition."""
    __tablename__ = "stage_transition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunity.id"), nullable=False
    )
    from_stage_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("opportunity_stage.id"), nullable=True
    )
    to_stage_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("opportunity_stage.id"), nullable=False
    )
    transitioned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    transitioned_by_rep_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=False
    )
    days_in_previous_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Snapshot of opportunity.expected_close_date at the moment of this transition
    # (used to identify "slipped" opportunities whose expected close date keeps moving out)
    expected_close_date_at_transition: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CampaignMember(Base):
    """M:N junction: a lead or contact engaged with a campaign. lead_id XOR contact_id."""
    __tablename__ = "campaign_member"
    __table_args__ = (
        CheckConstraint(
            "(lead_id IS NULL) <> (contact_id IS NULL)",
            name="ck_campaign_member_lead_xor_contact",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=False
    )
    lead_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lead.id"), nullable=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contact.id"), nullable=True
    )
    member_role: Mapped[str] = mapped_column(String(20), nullable=False)
    engaged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attribution_credit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ContentEngagement(Base):
    """Event log: a lead/contact engaging with a content_asset. lead_id XOR contact_id."""
    __tablename__ = "content_engagement"
    __table_args__ = (
        CheckConstraint(
            "(lead_id IS NULL) <> (contact_id IS NULL)",
            name="ck_content_engagement_lead_xor_contact",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_asset.id"), nullable=False
    )
    lead_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lead.id"), nullable=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contact.id"), nullable=True
    )
    engagement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    engaged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=True
    )
    time_on_page_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SalesEmail(Base):
    """SDR / AE outbound one-to-one email (part of a sequence). lead_id XOR contact_id."""
    __tablename__ = "sales_email"
    __table_args__ = (
        CheckConstraint(
            "(recipient_lead_id IS NULL) <> (recipient_contact_id IS NULL)",
            name="ck_sales_email_lead_xor_contact",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_rep_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=False
    )
    recipient_lead_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lead.id"), nullable=True
    )
    recipient_contact_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contact.id"), nullable=True
    )
    sequence_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    opened: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    replied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reply_sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bounced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LeadScoringEvent(Base):
    """Event log: every scoring action applied to a lead. Summed up into lead.lead_score."""
    __tablename__ = "lead_scoring_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lead.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_object_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TargetAccountList(Base):
    """Membership in an ABM target-account list."""
    __tablename__ = "target_account_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_name: Mapped[str] = mapped_column(String(80), nullable=False)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_rep_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_rep.id"), nullable=False
    )
    added_date: Mapped[date] = mapped_column(Date, nullable=False)
    engagement_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# ============================================================================
# Helper functions
# ============================================================================
def weighted_choice(weighted: list[tuple]) -> object:
    """Pick one element from a list of (item, weight) tuples."""
    items, weights = zip(*weighted)
    return random.choices(items, weights=weights, k=1)[0]


def weighted_choice_list(items: list, weights: list):
    """Pick one element from items using weights."""
    return random.choices(items, weights=weights, k=1)[0]


def random_date_between(start: date, end: date) -> date:
    """Uniform random date in [start, end]."""
    if end <= start:
        return start
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_datetime_between(start: date, end: date) -> datetime:
    """Uniform random datetime in [start 00:00, end 23:59]."""
    d = random_date_between(start, end)
    return datetime.combine(d, time(
        hour=random.randint(0, 23),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
    ))


def slugify(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


# ============================================================================
# Generators - Lookup tables
# ============================================================================
def gen_lead_source() -> pl.DataFrame:
    """10 fixed rows of lead-source taxonomy data."""
    rows = []
    for i, (code, name, cat, cpl) in enumerate(LEAD_SOURCES, start=1):
        rows.append({
            "id": i,
            "source_code": code,
            "source_name": name,
            "source_category": cat,
            "typical_cost_per_lead_usd": cpl,
            "is_active": True,
        })
    return pl.DataFrame(rows)


def gen_industry() -> pl.DataFrame:
    """12 rows of industry data."""
    rows = []
    for i, (name, naics, arr_band) in enumerate(INDUSTRIES, start=1):
        rows.append({
            "id": i,
            "industry_name": name,
            "naics_code": naics,
            "typical_arr_band": arr_band,
        })
    return pl.DataFrame(rows)


def gen_opportunity_stage() -> pl.DataFrame:
    """7 stages: Discovery, Demo, Eval/POC, Proposal, Negotiation, Won, Lost."""
    rows = []
    for i, (name, order, closed, won, prob) in enumerate(OPPORTUNITY_STAGES, start=1):
        rows.append({
            "id": i,
            "stage_name": name,
            "stage_order": order,
            "is_closed": closed,
            "is_won": won,
            "typical_win_probability_pct": prob,
        })
    return pl.DataFrame(rows)


# ============================================================================
# Generators - Core entities
# ============================================================================
def gen_sales_rep() -> pl.DataFrame:
    """40 sales reps: 4 Managers + 12 SDRs + 8 AE_SMB + 8 AE_Mid + 8 AE_Enterprise.

    Self-referencing manager_id FK: managers have NULL; everyone else reports to a manager.
    Region is weighted; quota varies by role.
    """
    rows = []
    used_emails = set()

    def _uniq_email(first, last):
        base = f"{first.lower()}.{last.lower()}".replace(" ", "")
        candidate = f"{base}@stratosend.com"
        n = 1
        while candidate in used_emails:
            candidate = f"{base}{n}@stratosend.com"
            n += 1
        used_emails.add(candidate)
        return candidate

    rep_id = 1
    manager_ids_by_region = {}

    # 4 managers, one per region (NA may end up with an extra one)
    manager_regions = ["NA-East", "NA-West", "EMEA", "APAC"]
    for region in manager_regions:
        fn, ln = fake.first_name(), fake.last_name()
        rows.append({
            "id": rep_id,
            "first_name": fn,
            "last_name": ln,
            "email": _uniq_email(fn, ln),
            "role": "Manager",
            "region": region,
            "quota_usd": 0.0,
            "hire_date": random_date_between(
                TODAY - timedelta(days=365 * 8),
                TODAY - timedelta(days=365 * 2),
            ),
            "manager_id": None,
            "is_active": True,
        })
        manager_ids_by_region[region] = rep_id
        rep_id += 1

    role_counts = {
        "SDR": 12,
        "AE_SMB": 8,
        "AE_Mid": 8,
        "AE_Enterprise": 8,
    }
    quota_by_role = {
        "SDR": 0.0,
        "AE_SMB": 600_000.0,
        "AE_Mid": 1_200_000.0,
        "AE_Enterprise": 2_000_000.0,
    }
    for role, n in role_counts.items():
        for _ in range(n):
            fn, ln = fake.first_name(), fake.last_name()
            region = random.choices(REGIONS, weights=REGION_WEIGHTS, k=1)[0]
            # Hire date skews more recent
            tenure_days = random.choices(
                [180, 365, 730, 1095, 1825],
                weights=[0.25, 0.25, 0.25, 0.15, 0.10],
                k=1,
            )[0]
            hire_date = TODAY - timedelta(days=random.randint(60, tenure_days))
            rows.append({
                "id": rep_id,
                "first_name": fn,
                "last_name": ln,
                "email": _uniq_email(fn, ln),
                "role": role,
                "region": region,
                "quota_usd": quota_by_role[role],
                "hire_date": hire_date,
                "manager_id": manager_ids_by_region[region],
                "is_active": random.random() > 0.05,  # 5% inactive
            })
            rep_id += 1

    return pl.DataFrame(rows)


def gen_account(industry_ids: list[int], ae_ids: list[int]) -> pl.DataFrame:
    """2,000 B2B accounts. Tier derived from employee-count band. Assign an owning AE."""
    rows = []
    used_names = set()
    for i in range(1, N_ACCOUNT + 1):
        # Unique company name
        company = fake.unique.company()
        while company in used_names:
            company = fake.company() + " " + random.choice(
                ["Inc", "LLC", "Corp", "Holdings", "Labs", "Group"]
            )
        used_names.add(company)

        emp_band = random.choices(EMPLOYEE_BANDS, weights=EMP_BAND_WEIGHTS, k=1)[0]
        tier = TIER_BY_EMP_BAND[emp_band]
        # Revenue band loosely correlates with employee band
        rev_band_idx = {
            "1-50": 0, "51-200": 1, "201-1000": 2, "1001-5000": 3, "5000+": 4
        }[emp_band]
        # Add a small jitter
        rev_band_idx = max(0, min(4, rev_band_idx + random.choice([-1, 0, 0, 0, 1])))
        rev_band = REVENUE_BANDS[rev_band_idx]

        country = random.choices(
            [c for c, _ in COUNTRY_WEIGHTS],
            weights=[w for _, w in COUNTRY_WEIGHTS],
            k=1,
        )[0]
        if country == "United States":
            state = random.choice(US_STATES)
        else:
            state = fake.city()

        website = f"https://{slugify(company)[:30]}.com"
        created = random_date_between(HISTORY_START, TODAY - timedelta(days=14))

        # Owner: SMB->AE_SMB, Mid->AE_Mid, Enterprise->AE_Enterprise (not every account has one)
        owner_id = random.choice(ae_ids) if random.random() < 0.85 else None

        rows.append({
            "id": i,
            "company_name": company,
            "industry_id": random.choice(industry_ids),
            "employee_count_band": emp_band,
            "annual_revenue_band": rev_band,
            "account_tier": tier,
            "country": country,
            "state_or_province": state,
            "website": website,
            "created_date": created,
            "owner_ae_id": owner_id,
            "is_target_account": False,   # reconciled later
            "lifetime_arr_won_usd": 0.0,  # reconciled later
        })
    fake.unique.clear()
    return pl.DataFrame(rows)


def gen_campaign(industry_ids: list[int], manager_ids: list[int]) -> pl.DataFrame:
    """80 campaigns with a mix of types, statuses, and dates."""
    rows = []
    used_codes = set()
    today_dt = datetime.combine(TODAY, time(0, 0))
    for i in range(1, N_CAMPAIGN + 1):
        ctype_name = weighted_choice([(t[0], t[2]) for t in CAMPAIGN_TYPES])
        primary_kpi = next(t[1] for t in CAMPAIGN_TYPES if t[0] == ctype_name)
        status = weighted_choice(CAMPAIGN_STATUS_WEIGHTS)

        # Date range determined by status
        if status == "COMPLETED":
            end_date = random_date_between(
                TODAY - timedelta(days=500), TODAY - timedelta(days=14)
            )
            start_date = end_date - timedelta(days=random.randint(7, 60))
        elif status == "ACTIVE":
            start_date = random_date_between(
                TODAY - timedelta(days=45), TODAY - timedelta(days=1)
            )
            end_date = TODAY + timedelta(days=random.randint(7, 45))
        else:  # PLANNED
            start_date = random_date_between(
                TODAY + timedelta(days=2), TODAY + timedelta(days=20)
            )
            end_date = start_date + timedelta(days=random.randint(14, 60))

        budget = round(random.uniform(500.0, 50_000.0), 2)
        if ctype_name in ("Conference_Event", "ABM_Sequence"):
            budget = round(random.uniform(15_000.0, 80_000.0), 2)

        # Spend
        if status == "COMPLETED":
            spend = round(budget * random.uniform(0.80, 1.05), 2)
        elif status == "ACTIVE":
            spend = round(budget * random.uniform(0.20, 0.70), 2)
        else:
            spend = 0.0

        # Plan targets
        if "MQL" in primary_kpi:
            target_mql = random.randint(20, 250)
            target_pipeline = round(target_mql * random.uniform(8_000, 25_000), 2)
        elif "Pipeline" in primary_kpi:
            target_mql = random.randint(10, 100)
            target_pipeline = round(random.uniform(200_000, 2_000_000), 2)
        else:  # SQLs
            target_mql = random.randint(30, 150)
            target_pipeline = round(random.uniform(100_000, 800_000), 2)

        prefix = {
            "Webinar": "WBR",
            "Email_Blast": "EML",
            "Paid_Search": "SEM",
            "Paid_Social": "SOC",
            "Content_Syndication": "SYN",
            "Conference_Event": "EVT",
            "ABM_Sequence": "ABM",
            "SDR_Outbound_Sequence": "SDR",
        }[ctype_name]
        code = f"{prefix}-{start_date.strftime('%Y%m')}-{i:03d}"
        while code in used_codes:
            code = f"{prefix}-{start_date.strftime('%Y%m')}-{i:03d}X"
        used_codes.add(code)

        # Templated name
        topics_subset = random.sample(CONTENT_TOPICS, k=1)
        if ctype_name == "Webinar":
            name = f"Webinar: {topics_subset[0]}"
        elif ctype_name == "Email_Blast":
            name = f"Email Nurture: {topics_subset[0]}"
        elif ctype_name == "Paid_Search":
            name = f"Google Search: '{topics_subset[0]}'"
        elif ctype_name == "Paid_Social":
            name = f"LinkedIn Sponsored: {topics_subset[0]}"
        elif ctype_name == "Content_Syndication":
            name = f"Syndication: {topics_subset[0]}"
        elif ctype_name == "Conference_Event":
            name = random.choice([
                "KubeCon Booth Sponsorship",
                "AWS re:Invent Field Marketing",
                "QCon SF Speaker Slot",
                "Gartner IT Symposium",
                "DevOps Enterprise Summit",
            ]) + f" {start_date.year}"
        elif ctype_name == "ABM_Sequence":
            name = random.choice([
                "ABM Fintech Wave",
                "ABM Healthcare Tier-1",
                "ABM Enterprise Logos NA",
                "ABM Manufacturing Push",
            ]) + f" {start_date.year}-Q{(start_date.month - 1) // 3 + 1}"
        else:
            name = f"SDR Outbound: {topics_subset[0]} Persona-Targeted"

        target_persona = weighted_choice_list(PERSONAS, PERSONA_WEIGHTS)
        target_industry = random.choice(industry_ids) if random.random() < 0.45 else None

        rows.append({
            "id": i,
            "campaign_code": code,
            "campaign_name": name[:150],
            "campaign_type": ctype_name,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "total_budget_usd": budget,
            "spend_to_date_usd": spend,
            "target_persona": target_persona,
            "target_industry_id": target_industry,
            "owner_id": random.choice(manager_ids),
            "primary_kpi": primary_kpi,
            "target_mql_count": target_mql,
            "target_pipeline_usd": target_pipeline,
            "created_at": datetime.combine(
                start_date - timedelta(days=random.randint(7, 30)),
                time(random.randint(9, 17), random.randint(0, 59), 0),
            ),
        })
    return pl.DataFrame(rows)


def gen_content_asset() -> pl.DataFrame:
    """150 content assets across types and topics."""
    rows = []
    used_names = set()
    for i in range(1, N_CONTENT_ASSET + 1):
        asset_type = weighted_choice(ASSET_TYPES)
        topic = random.choice(CONTENT_TOPICS)
        # Templated name
        if asset_type == "ebook":
            name = f"The Complete Guide to {topic}"
        elif asset_type == "whitepaper":
            name = f"Whitepaper: {topic} at Scale"
        elif asset_type == "case_study":
            name = f"How {fake.company()} Reduced MTTR with {topic}"
        elif asset_type == "webinar_recording":
            name = f"Webinar Recording: {topic} Deep Dive"
        elif asset_type == "blog_post":
            adjective = random.choice(["5 Lessons", "What We Learned", "Why",
                                       "Hidden Costs of", "Best Practices for"])
            name = f"{adjective} {topic}"
        elif asset_type == "analyst_report":
            name = f"Analyst Report: {topic} Vendor Landscape"
        else:
            name = f"Template: {topic} Runbook"

        while name in used_names:
            name = name + f" v{random.randint(2,9)}"
        used_names.add(name)

        # Gating probability: gated content is mostly ebooks/whitepapers
        gated_prob = 0.85 if asset_type in ("ebook", "whitepaper", "analyst_report") else 0.55
        is_gated = random.random() < gated_prob

        created = random_date_between(HISTORY_START, TODAY - timedelta(days=7))
        url = f"https://stratosend.com/resources/{slugify(name)[:60]}"

        rows.append({
            "id": i,
            "asset_name": name[:200],
            "asset_type": asset_type,
            "topic_tag": topic,
            "target_persona": weighted_choice_list(PERSONAS, PERSONA_WEIGHTS),
            "is_gated": is_gated,
            "created_date": created,
            "asset_url": url[:200],
            "total_downloads": 0,  # reconciled later
        })
    return pl.DataFrame(rows)


def gen_lead(
    source_ids: list[int],
    account_ids: list[int],
    sdr_ids: list[int],
    campaign_ids: list[int],
    campaigns_df: pl.DataFrame,
) -> pl.DataFrame:
    """8,000 leads. Status starts as 'new' and is reconciled later.

    ~70% have an account_id. ~50% have a source_campaign_id (mostly inbound).
    """
    rows = []
    used_emails = set()
    completed_active_campaign_ids = campaigns_df.filter(
        pl.col("status").is_in(["COMPLETED", "ACTIVE"])
    )["id"].to_list()

    for i in range(1, N_LEAD + 1):
        persona = weighted_choice_list(PERSONAS, PERSONA_WEIGHTS)
        # Seniority correlates with persona, with some noise
        base_seniority = SENIORITY_BY_PERSONA[persona]
        if random.random() < 0.30:
            seniority = weighted_choice_list(SENIORITIES, SENIORITY_WEIGHTS)
        else:
            seniority = base_seniority
        title = random.choice(PERSONA_TO_TITLES[persona])

        first = fake.first_name()
        last = fake.last_name()
        base_email = f"{first.lower()}.{last.lower()}{random.randint(1,9999)}@{fake.domain_name()}"
        while base_email in used_emails:
            base_email = f"{first.lower()}.{last.lower()}{random.randint(1,99999)}@{fake.domain_name()}"
        used_emails.add(base_email)

        account_id = random.choice(account_ids) if random.random() < 0.70 else None

        # Weighted source: inbound + paid search dominate enterprise-grade events
        source_id = random.choices(
            source_ids,
            weights=[0.05, 0.05, 0.12, 0.20, 0.13, 0.10, 0.05, 0.18, 0.04, 0.08],
            k=1,
        )[0]

        # source_campaign_id: paid / webinar / event sources are more likely to have one
        if random.random() < 0.55 and completed_active_campaign_ids:
            source_campaign_id = random.choice(completed_active_campaign_ids)
        else:
            source_campaign_id = None

        # Creation date: leads distributed over the past 18 months
        created_date = random_date_between(HISTORY_START, TODAY - timedelta(days=1))
        created_at = datetime.combine(
            created_date,
            time(random.randint(7, 22), random.randint(0, 59), random.randint(0, 59)),
        )

        # SDR assignment: ~80% of leads eventually get assigned to an SDR
        assigned_sdr = random.choice(sdr_ids) if random.random() < 0.80 else None

        rows.append({
            "id": i,
            "first_name": first,
            "last_name": last,
            "email": base_email,
            "title": title,
            "seniority": seniority,
            "persona": persona,
            "account_id": account_id,
            "source_id": source_id,
            "source_campaign_id": source_campaign_id,
            "lead_score": 0,         # reconcile
            "status": "new",         # reconcile
            "mql_date": None,        # reconcile
            "sql_date": None,        # reconcile
            "converted_date": None,  # reconcile
            "disqualified_reason": None,
            "assigned_sdr_id": assigned_sdr,
            "created_at": created_at,
        })
    return pl.DataFrame(rows)


def gen_contact(
    leads_df: pl.DataFrame,
    accounts_df: pl.DataFrame,
) -> pl.DataFrame:
    """3,000 contacts. 20% are converted from leads (lead_id set, part 1),
    80% are direct outbound (lead_id NULL, part 2).

    The 20/80 split is tuned to match the natural lead-conversion rate
    (~7% of N_LEAD) so that reconcile_lead_funnel does not have to force
    a large batch of leads into 'converted_to_contact' to satisfy the
    contact -> lead invariant.
    See line 1189 (`n_from_leads`) for the rationale.

    Every contact must have an account_id.
    """
    rows = []
    used_emails = set()

    # Convertible leads: anything with an account_id (so we have somewhere to map them)
    convertible_lead_rows = leads_df.filter(pl.col("account_id").is_not_null()).to_dicts()
    random.shuffle(convertible_lead_rows)

    account_ids = accounts_df["id"].to_list()
    # Contacts skew toward Mid/Enterprise accounts (more stakeholders per account)
    account_tier_map = dict(zip(accounts_df["id"].to_list(),
                                accounts_df["account_tier"].to_list()))

    # Use 20% not 60%: only ~7% of leads naturally complete the MQL -> SQL ->
    # converted_to_contact path (35% × 25% × 80% ≈ 560 of 8,000). An earlier
    # version pre-assigned 60% of N_CONTACT (1,800) to leads, after which
    # reconcile_lead_funnel had to force ~1,300 leads to
    # status='converted_to_contact', breaking funnel realism
    # (conversion rate shot up to 27% vs the spec target of 6%). At 20%,
    # the part-1 quota (600) matches natural conversion volume, so the
    # downstream invariant pass only catches a small remainder.
    n_from_leads = int(N_CONTACT * 0.20)
    n_direct = N_CONTACT - n_from_leads

    contact_id = 1

    # Part 1: contacts converted from leads
    for lead in convertible_lead_rows[:n_from_leads]:
        persona = lead["persona"]
        role_in_deal_map = {
            "Champion":       "Champion",
            "Economic Buyer": "Decision Maker",
            "Decision Maker": "Decision Maker",
            "Influencer":     "User",
            "Blocker":        "Blocker",
        }
        role_in_deal = role_in_deal_map.get(persona, "User")

        email = lead["email"]
        # Email may have already been used; nudge it
        while email in used_emails:
            email = f"alt-{contact_id}-{lead['email']}"
        used_emails.add(email)

        created_at = lead["created_at"] + timedelta(days=random.randint(7, 60))
        if created_at.date() > TODAY:
            created_at = datetime.combine(TODAY, time(12, 0))

        rows.append({
            "id": contact_id,
            "lead_id": lead["id"],
            "account_id": lead["account_id"],
            "first_name": lead["first_name"],
            "last_name": lead["last_name"],
            "email": email,
            "title": lead["title"],
            "seniority": lead["seniority"],
            "persona": persona,
            "role_in_deal": role_in_deal,
            "do_not_email": random.random() < 0.05,
            "created_at": created_at,
        })
        contact_id += 1

    # Part 2: Direct outbound contacts (lead_id is NULL)
    # Skewed toward non-SMB accounts
    weighted_accounts = []
    for aid in account_ids:
        tier = account_tier_map[aid]
        weight = 1 if tier == "SMB" else 3 if tier == "Mid" else 5
        weighted_accounts.extend([aid] * weight)

    for _ in range(n_direct):
        persona = weighted_choice_list(PERSONAS, PERSONA_WEIGHTS)
        seniority = (
            SENIORITY_BY_PERSONA[persona]
            if random.random() < 0.70
            else weighted_choice_list(SENIORITIES, SENIORITY_WEIGHTS)
        )
        title = random.choice(PERSONA_TO_TITLES[persona])
        first, last = fake.first_name(), fake.last_name()
        email = f"{first.lower()}.{last.lower()}{random.randint(1,9999)}@{fake.domain_name()}"
        while email in used_emails:
            email = f"{first.lower()}.{last.lower()}{random.randint(1,99999)}@{fake.domain_name()}"
        used_emails.add(email)
        role_in_deal_map = {
            "Champion": "Champion", "Economic Buyer": "Decision Maker",
            "Decision Maker": "Decision Maker", "Influencer": "User", "Blocker": "Blocker",
        }
        created_at = random_datetime_between(HISTORY_START, TODAY - timedelta(days=1))
        rows.append({
            "id": contact_id,
            "lead_id": None,
            "account_id": random.choice(weighted_accounts),
            "first_name": first,
            "last_name": last,
            "email": email,
            "title": title,
            "seniority": seniority,
            "persona": persona,
            "role_in_deal": role_in_deal_map.get(persona, "User"),
            "do_not_email": random.random() < 0.05,
            "created_at": created_at,
        })
        contact_id += 1

    return pl.DataFrame(rows)


# ============================================================================
# Generators - Marketing event tables
# ============================================================================
def gen_campaign_member(
    campaigns_df: pl.DataFrame,
    leads_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
) -> pl.DataFrame:
    """~12,000 campaign membership rows. XOR: lead_id or contact_id (exactly one).

    Member roles: registered / attended / no_show / influenced / converted
    """
    rows = []
    member_id = 1
    member_role_weights = [
        ("registered", 0.40),
        ("attended",   0.25),
        ("no_show",    0.15),
        ("influenced", 0.15),
        ("converted",  0.05),
    ]

    # Only completed + active campaigns get members
    active_campaigns = campaigns_df.filter(
        pl.col("status").is_in(["COMPLETED", "ACTIVE"])
    ).to_dicts()

    lead_ids = leads_df["id"].to_list()
    lead_created_lookup = dict(zip(
        leads_df["id"].to_list(),
        [d.date() if isinstance(d, datetime) else d for d in leads_df["created_at"].to_list()],
    ))
    contact_ids = contacts_df["id"].to_list()
    contact_created_lookup = dict(zip(
        contacts_df["id"].to_list(),
        [d.date() if isinstance(d, datetime) else d for d in contacts_df["created_at"].to_list()],
    ))

    # Target: ~12,000 members across ~80 campaigns -> avg 150/campaign
    # but skew so some campaigns are huge (paid_search, webinars)
    for camp in active_campaigns:
        ctype = camp["campaign_type"]
        if ctype in ("Paid_Search", "Paid_Social", "Email_Blast"):
            n_members = random.randint(150, 350)
        elif ctype == "Webinar":
            n_members = random.randint(80, 250)
        elif ctype == "Conference_Event":
            n_members = random.randint(50, 200)
        elif ctype == "Content_Syndication":
            n_members = random.randint(50, 150)
        elif ctype == "ABM_Sequence":
            n_members = random.randint(20, 80)
        else:  # SDR_Outbound_Sequence
            n_members = random.randint(40, 150)

        camp_start = camp["start_date"]
        camp_end = camp["end_date"]
        # Engagement window: from campaign start to min(end, today)
        engage_end = min(camp_end, TODAY)
        if engage_end < camp_start:
            engage_end = camp_start

        for _ in range(n_members):
            # 75% are leads, 25% are contacts
            if random.random() < 0.75 and lead_ids:
                lead_id = random.choice(lead_ids)
                contact_id = None
                # Skip if the lead was created AFTER engagement window
                lead_created = lead_created_lookup[lead_id]
                if lead_created > engage_end:
                    continue
                engage_start_candidate = max(camp_start, lead_created)
            else:
                contact_id = random.choice(contact_ids)
                lead_id = None
                contact_created = contact_created_lookup[contact_id]
                if contact_created > engage_end:
                    continue
                engage_start_candidate = max(camp_start, contact_created)

            if engage_end < engage_start_candidate:
                continue

            engaged_at = random_datetime_between(engage_start_candidate, engage_end)
            role = weighted_choice(member_role_weights)

            rows.append({
                "id": member_id,
                "campaign_id": camp["id"],
                "lead_id": lead_id,
                "contact_id": contact_id,
                "member_role": role,
                "engaged_at": engaged_at,
                "attribution_credit_pct": 0.0,  # reconciled later
            })
            member_id += 1

    return pl.DataFrame(rows)


def gen_content_engagement(
    assets_df: pl.DataFrame,
    leads_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
    campaigns_df: pl.DataFrame,
) -> pl.DataFrame:
    """~18,000 content engagements. XOR lead/contact. Some traced back to a campaign."""
    rows = []
    eng_id = 1

    asset_rows = assets_df.to_dicts()
    lead_ids = leads_df["id"].to_list()
    contact_ids = contacts_df["id"].to_list()
    lead_created_lookup = dict(zip(
        leads_df["id"].to_list(),
        [d.date() if isinstance(d, datetime) else d for d in leads_df["created_at"].to_list()],
    ))
    contact_created_lookup = dict(zip(
        contacts_df["id"].to_list(),
        [d.date() if isinstance(d, datetime) else d for d in contacts_df["created_at"].to_list()],
    ))
    completed_active_camp_ids = campaigns_df.filter(
        pl.col("status").is_in(["COMPLETED", "ACTIVE"])
    )["id"].to_list()

    n_target = AVG_CONTENT_ENGAGEMENTS

    while eng_id <= n_target:
        asset = random.choice(asset_rows)
        # Asset must exist before the engagement
        asset_created = asset["created_date"]
        if asset_created >= TODAY:
            continue
        engagement_type = weighted_choice_list(
            CONTENT_ENGAGEMENT_TYPES, CONTENT_ENGAGEMENT_WEIGHTS
        )

        # 70% lead, 30% contact
        if random.random() < 0.70:
            lead_id = random.choice(lead_ids)
            contact_id = None
            person_created = lead_created_lookup[lead_id]
        else:
            contact_id = random.choice(contact_ids)
            lead_id = None
            person_created = contact_created_lookup[contact_id]

        eng_start = max(asset_created, person_created)
        if eng_start >= TODAY:
            continue
        engaged_at = random_datetime_between(eng_start, TODAY - timedelta(days=1))

        # Campaign source: 40% have one
        if random.random() < 0.40 and completed_active_camp_ids:
            source_camp = random.choice(completed_active_camp_ids)
        else:
            source_camp = None

        # Time on page only meaningful for view/replay; downloads and shares
        # are instantaneous (per ER doc 8.1 content_engagement rules).
        if engagement_type == "view":
            time_on_page = random.randint(20, 600)
        elif engagement_type == "replay":
            time_on_page = random.randint(60, 1200)
        else:
            time_on_page = 0

        rows.append({
            "id": eng_id,
            "content_asset_id": asset["id"],
            "lead_id": lead_id,
            "contact_id": contact_id,
            "engagement_type": engagement_type,
            "engaged_at": engaged_at,
            "source_campaign_id": source_camp,
            "time_on_page_seconds": time_on_page,
        })
        eng_id += 1

    return pl.DataFrame(rows)


def gen_sales_email(
    sdr_ae_rows: list[dict],
    leads_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
) -> pl.DataFrame:
    """~30,000 SDR outbound emails. XOR recipient lead/contact.

    Open ~35%, click ~8% (subset of opens), reply ~3%, bounce ~4%.
    Sequences span 3-7 steps with diminishing reply rates.
    """
    rows = []
    email_id = 1

    sdr_rep_ids = [r["id"] for r in sdr_ae_rows if r["role"] == "SDR"]
    ae_rep_ids = [r["id"] for r in sdr_ae_rows if r["role"].startswith("AE")]
    lead_rows = leads_df.to_dicts()
    contact_rows = contacts_df.to_dicts()

    # Group leads by SDR for stable sequences
    # SDR -> leads
    leads_by_sdr = defaultdict(list)
    for ld in lead_rows:
        if ld["assigned_sdr_id"] is not None:
            leads_by_sdr[ld["assigned_sdr_id"]].append(ld)

    n_target = AVG_SALES_EMAILS

    while email_id <= n_target:
        # 60% leads, 40% contacts
        if random.random() < 0.60 and sdr_rep_ids:
            sender = random.choice(sdr_rep_ids)
            candidate_leads = leads_by_sdr.get(sender, []) or lead_rows
            recipient_lead = random.choice(candidate_leads)
            recipient_lead_id = recipient_lead["id"]
            recipient_contact_id = None
            lead_created = recipient_lead["created_at"]
            if isinstance(lead_created, datetime):
                lead_created_date = lead_created.date()
            else:
                lead_created_date = lead_created
            seq_start_min = max(HISTORY_START, lead_created_date)
        else:
            sender = random.choice(sdr_rep_ids + ae_rep_ids)
            recipient_contact = random.choice(contact_rows)
            recipient_contact_id = recipient_contact["id"]
            recipient_lead_id = None
            contact_created = recipient_contact["created_at"]
            if isinstance(contact_created, datetime):
                contact_created_date = contact_created.date()
            else:
                contact_created_date = contact_created
            seq_start_min = max(HISTORY_START, contact_created_date)

        if seq_start_min >= TODAY:
            continue

        # Pick a sequence
        sequence_name = random.choice(SDR_SEQUENCE_NAMES)
        # Sequence has 3-7 steps; we emit a batch of steps for this recipient
        n_steps = random.randint(3, 7)
        step_start = random_datetime_between(
            seq_start_min, TODAY - timedelta(days=2)
        )

        for step_idx in range(1, n_steps + 1):
            if email_id > n_target:
                break

            # Bounce kills the rest of the sequence
            bounced = (step_idx == 1) and (random.random() < 0.04)

            # Open / click / reply rates decay by step
            open_rate = max(0.10, 0.40 - 0.04 * (step_idx - 1))
            click_rate_given_open = 0.22
            reply_rate_given_click = 0.30

            opened = (not bounced) and (random.random() < open_rate)
            clicked = opened and (random.random() < click_rate_given_open)
            replied = clicked and (random.random() < reply_rate_given_click)
            sentiment = None
            if replied:
                sentiment = random.choices(
                    ["positive", "neutral", "negative", "not_interested", "auto_reply"],
                    weights=[0.20, 0.20, 0.10, 0.40, 0.10],
                    k=1,
                )[0]

            subject_pool = [
                f"Quick question about {fake.company()}",
                f"Reducing MTTR at {fake.company()} (API observability)",
                "Worth a 15-min look?",
                f"Following up on {sequence_name}",
                "Re: API latency tracing benchmarks",
                "Thought you'd find this useful",
                "Stratosend vs Datadog - quick comparison",
            ]
            subject = random.choice(subject_pool)

            sent_at = step_start + timedelta(
                days=(step_idx - 1) * random.randint(3, 7),
                hours=random.randint(-2, 2),
            )
            if sent_at.date() > TODAY:
                break

            rows.append({
                "id": email_id,
                "sender_rep_id": sender,
                "recipient_lead_id": recipient_lead_id,
                "recipient_contact_id": recipient_contact_id,
                "sequence_name": sequence_name,
                "sequence_step": step_idx,
                "subject": subject[:200],
                "sent_at": sent_at,
                "opened": opened,
                "clicked": clicked,
                "replied": replied,
                "reply_sentiment": sentiment,
                "bounced": bounced,
            })
            email_id += 1

            if bounced:
                break
            # Stop if got a positive reply
            if sentiment == "positive":
                break

    return pl.DataFrame(rows)


def gen_lead_scoring_event(
    leads_df: pl.DataFrame,
    content_engagements_df: pl.DataFrame,
    campaign_members_df: pl.DataFrame,
    sales_emails_df: pl.DataFrame,
) -> pl.DataFrame:
    """~15,000 scoring events. Most leads get 1-4 events. Some derived from real events."""
    rows = []
    event_id = 1

    lead_rows = leads_df.to_dicts()

    # Pre-index source events per lead
    eng_by_lead = defaultdict(list)
    for eng in content_engagements_df.iter_rows(named=True):
        if eng["lead_id"]:
            eng_by_lead[eng["lead_id"]].append(eng)

    cm_by_lead = defaultdict(list)
    for cm in campaign_members_df.iter_rows(named=True):
        if cm["lead_id"]:
            cm_by_lead[cm["lead_id"]].append(cm)

    em_by_lead = defaultdict(list)
    for em in sales_emails_df.iter_rows(named=True):
        if em["recipient_lead_id"]:
            em_by_lead[em["recipient_lead_id"]].append(em)

    # Soft cap, intentionally generous so every lead gets its allotment.
    # The earlier version used AVG_SCORING_EVENTS as a hard cap, then
    # random.shuffle'd lead_rows — so the tail (~10% of leads) silently
    # received 0 events and ended up with mql_date = NULL.
    n_cap = AVG_SCORING_EVENTS * 2

    # Sort by created_at ascending so earlier leads get their events first.
    # We do not cap until we have walked every lead, so funnel-tail leads
    # are no longer starved.
    lead_rows.sort(key=lambda ld: ld["created_at"])

    for lead in lead_rows:
        if event_id > n_cap:
            break

        # Number of events for this lead: bias higher for inbound sources
        lead_created = lead["created_at"]
        if isinstance(lead_created, datetime):
            lead_created_date = lead_created.date()
        else:
            lead_created_date = lead_created
        days_alive = max(1, (TODAY - lead_created_date).days)

        # Heavy right tail so ~30% of leads cross MQL threshold (100 pts).
        # avg ~5.7 events/lead × ~17 pts/event ~= 97 base; upper quartile easily clears.
        n_events = random.choices(
            [0, 1, 2, 4, 6, 10, 16, 24],
            weights=[0.08, 0.15, 0.18, 0.18, 0.16, 0.13, 0.08, 0.04],
            k=1,
        )[0]

        for _ in range(n_events):
            if event_id > n_cap:
                break

            # Pick scoring rule
            rule = weighted_choice([(r, r[3]) for r in SCORING_RULES])
            event_type, rule_name, points, _ = rule

            # Derive source_object from real events when possible
            source_object_type = None
            source_object_id = None
            occurred_at_candidate = None

            if event_type == "content_download" and eng_by_lead.get(lead["id"]):
                src = random.choice(eng_by_lead[lead["id"]])
                source_object_type = "content_engagement"
                source_object_id = src["id"]
                occurred_at_candidate = src["engaged_at"]
            elif event_type == "webinar_attend" and cm_by_lead.get(lead["id"]):
                webinar_members = [
                    m for m in cm_by_lead[lead["id"]]
                    if m.get("member_role") in ("attended", "registered")
                ]
                if webinar_members:
                    src = random.choice(webinar_members)
                    source_object_type = "campaign_member"
                    source_object_id = src["id"]
                    occurred_at_candidate = src["engaged_at"]
            elif event_type == "email_click" and em_by_lead.get(lead["id"]):
                clicked = [e for e in em_by_lead[lead["id"]] if e.get("clicked")]
                if clicked:
                    src = random.choice(clicked)
                    source_object_type = "sales_email"
                    source_object_id = src["id"]
                    occurred_at_candidate = src["sent_at"]

            if occurred_at_candidate is None:
                source_object_type = "website"
                occurred_at_candidate = random_datetime_between(
                    lead_created_date,
                    min(TODAY - timedelta(days=1),
                        lead_created_date + timedelta(days=days_alive)),
                )

            rows.append({
                "id": event_id,
                "lead_id": lead["id"],
                "event_type": event_type,
                "points_awarded": points,
                "scoring_rule_name": rule_name,
                "occurred_at": occurred_at_candidate,
                "source_object_type": source_object_type,
                "source_object_id": source_object_id,
            })
            event_id += 1

    return pl.DataFrame(rows)


# ============================================================================
# Reconcile - Lead funnel (status, mql_date, sql_date, lead_score)
# ============================================================================
def reconcile_lead_funnel(
    leads_df: pl.DataFrame,
    scoring_events_df: pl.DataFrame,
    sales_emails_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
) -> pl.DataFrame:
    """Reconcile lead.lead_score, lead.mql_date, lead.status, etc.

    Rules:
      * lead_score = SUM(scoring_event.points)
      * mql_date = MIN(occurred_at WHERE cumulative_score >= MQL_THRESHOLD)
      * status transitions:
        - score < 50 and no SDR touch -> 'new'
        - score < 100 with SDR email   -> 'working'
        - score >= 100                 -> 'mql' (and possibly further)
        - Of MQLs: ~70% pursued by SDR -> 25% become 'sql', 75% stay 'mql'
                   ~30% disqualified
        - Of SQLs: ~80% 'converted_to_contact', 20% dropped (stay 'sql')

      * Semantic invariant (enforced after the random rolls):
        Any lead that ALREADY has a contact row pointing at it (created by
        gen_contact part 1) MUST end up with status='converted_to_contact'.
        Also back-fill lead.account_id from the contact when missing, so the
        lead-sourced funnel join (lead.account_id ↔ contact.account_id) is
        consistent end-to-end.
    """
    # Build lead_id -> (contact_account_id, contact_created_at) for leads
    # that already have a contact pointing at them.
    leads_with_contact: dict[int, tuple[int, datetime]] = {}
    if contacts_df.height > 0:
        for c in contacts_df.filter(
            pl.col("lead_id").is_not_null()
        ).iter_rows(named=True):
            leads_with_contact[c["lead_id"]] = (c["account_id"], c["created_at"])
    # Sum scoring events per lead
    score_sum = (
        scoring_events_df
        .group_by("lead_id")
        .agg(pl.col("points_awarded").sum().alias("lead_score"))
    )
    # Earliest event when cumulative score >= MQL_THRESHOLD
    sorted_events = scoring_events_df.sort(["lead_id", "occurred_at"])
    mql_dates = []
    for lead_id, grp in sorted_events.group_by("lead_id"):
        cumsum = 0
        mql_date = None
        for row in grp.iter_rows(named=True):
            cumsum += row["points_awarded"]
            if cumsum >= MQL_SCORE_THRESHOLD:
                occ = row["occurred_at"]
                mql_date = occ.date() if isinstance(occ, datetime) else occ
                break
        mql_dates.append({"lead_id": lead_id[0] if isinstance(lead_id, tuple) else lead_id,
                          "mql_date": mql_date})
    mql_df = pl.DataFrame(mql_dates, schema={"lead_id": pl.Int64, "mql_date": pl.Date})

    # Did the lead get any email?
    leads_with_email = sales_emails_df.filter(
        pl.col("recipient_lead_id").is_not_null()
    )["recipient_lead_id"].unique().to_list()
    lead_has_email = set(leads_with_email)

    # Build merged
    leads_df = leads_df.join(score_sum, left_on="id", right_on="lead_id", how="left") \
        .with_columns(pl.col("lead_score_right").fill_null(0).alias("lead_score_new"))
    if "lead_score" in leads_df.columns:
        leads_df = leads_df.drop("lead_score")
    leads_df = leads_df.rename({"lead_score_new": "lead_score"})
    if "lead_score_right" in leads_df.columns:
        leads_df = leads_df.drop("lead_score_right")

    leads_df = leads_df.join(mql_df, left_on="id", right_on="lead_id", how="left")
    if "mql_date_right" in leads_df.columns:
        leads_df = leads_df.drop("mql_date").rename({"mql_date_right": "mql_date"})

    # Now compute status / sql_date / converted_date / disqual reason
    updated = []
    for row in leads_df.iter_rows(named=True):
        score = row.get("lead_score") or 0
        mql_date = row.get("mql_date")
        has_email = row["id"] in lead_has_email

        status = "new"
        sql_date = None
        converted_date = None
        disqual = None
        account_id_override = None

        if mql_date is not None:
            # MQL achieved
            status = "mql"
            roll = random.random()
            if roll < 0.25:
                # 25% of MQLs -> SQL (matches spec target)
                sql_offset = random.randint(2, 21)
                sql_d = mql_date + timedelta(days=sql_offset)
                if sql_d <= TODAY:
                    status = "sql"
                    sql_date = sql_d
                    # 80% of SQLs convert to contact
                    if random.random() < 0.80:
                        conv_offset = random.randint(1, 10)
                        conv_d = sql_d + timedelta(days=conv_offset)
                        if conv_d <= TODAY:
                            status = "converted_to_contact"
                            converted_date = conv_d
            elif roll < 0.50:
                # 25% disqualified
                status = "disqualified"
                disqual = random.choice(LEAD_DISQUAL_REASONS)
            # else: remaining 50% stay 'mql' (still being worked)
        elif has_email or score >= 30:
            status = "working"

        # Invariant enforcement: if a contact already points at this lead,
        # force status='converted_to_contact' and back-fill missing dates +
        # account_id. This keeps the lead -> contact relationship truthful
        # regardless of the random rolls above.
        contact_link = leads_with_contact.get(row["id"])
        if contact_link is not None:
            c_account_id, c_created_at = contact_link
            status = "converted_to_contact"
            disqual = None  # cannot be disqualified if a contact exists
            # Best-effort sql_date / converted_date so downstream queries work
            c_created_date = c_created_at.date() if isinstance(c_created_at, datetime) else c_created_at
            if mql_date is None:
                # Synthesize an mql_date 1-21 days before contact creation
                synth_mql = c_created_date - timedelta(days=random.randint(7, 21))
                if synth_mql > TODAY:
                    synth_mql = TODAY - timedelta(days=1)
                mql_date = synth_mql
            if sql_date is None:
                sql_date = min(c_created_date - timedelta(days=1), TODAY - timedelta(days=1))
                if sql_date < mql_date:
                    sql_date = mql_date
            converted_date = c_created_date
            # Back-fill lead.account_id from contact so lead-vs-contact joins line up
            if row.get("account_id") is None:
                account_id_override = c_account_id

        updated.append({
            "id": row["id"],
            "status": status,
            "sql_date": sql_date,
            "converted_date": converted_date,
            "disqualified_reason": disqual,
            "mql_date_override": mql_date,
            "account_id_override": account_id_override,
        })

    updates_df = pl.DataFrame(updated, schema={
        "id": pl.Int64,
        "status": pl.Utf8,
        "sql_date": pl.Date,
        "converted_date": pl.Date,
        "disqualified_reason": pl.Utf8,
        "mql_date_override": pl.Date,
        "account_id_override": pl.Int64,
    })

    leads_df = leads_df.drop(["status", "sql_date", "converted_date", "disqualified_reason"]) \
        .join(updates_df, on="id", how="left")

    # Apply contact-driven overrides for mql_date and account_id.
    leads_df = leads_df.with_columns(
        pl.coalesce([pl.col("mql_date_override"), pl.col("mql_date")]).alias("mql_date"),
        pl.coalesce([pl.col("account_id_override"), pl.col("account_id")]).alias("account_id"),
    ).drop(["mql_date_override", "account_id_override"])

    return leads_df


# ============================================================================
# Post-funnel pass: ensure every converted_to_contact lead has a contact
# ============================================================================
def ensure_contacts_for_converted_leads(
    leads_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
    accounts_df: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """For every lead with status='converted_to_contact' that has no existing
    contact row, create one. This guarantees the lead → contact → opportunity
    chain is intact for the lead-sourced sales funnel.

    Returns (contacts_df, leads_df). leads_df may have lead.account_id
    back-filled when we had to pick an account from the pool for a
    contact whose source lead had no account_id.
    """
    existing_lead_ids = set(
        c for c in
        contacts_df.filter(pl.col("lead_id").is_not_null())["lead_id"].to_list()
    )
    converted_lead_rows = leads_df.filter(
        pl.col("status") == "converted_to_contact"
    ).to_dicts()

    existing_emails = set(contacts_df["email"].to_list())
    next_id = int(contacts_df["id"].max() or 0) + 1
    new_rows = []
    # lead_id -> chosen account_id, so we can back-fill lead.account_id at the end
    lead_account_backfill: dict[int, int] = {}

    role_in_deal_map = {
        "Champion": "Champion", "Economic Buyer": "Decision Maker",
        "Decision Maker": "Decision Maker", "Influencer": "User",
        "Blocker": "Blocker",
    }

    account_ids_pool = accounts_df["id"].to_list()

    for lead in converted_lead_rows:
        if lead["id"] in existing_lead_ids:
            continue
        account_id = lead["account_id"]
        if account_id is None:
            account_id = random.choice(account_ids_pool)
            # Record so we can back-fill lead.account_id below — otherwise
            # contact.account_id is set but lead.account_id stays NULL, and
            # joins on lead.account_id ↔ contact.account_id silently miss.
            lead_account_backfill[lead["id"]] = account_id

        # Derive contact email distinct from lead's
        local, domain = lead["email"].split("@", 1) if "@" in lead["email"] else ("user", "example.com")
        candidate = f"c{next_id}.{local}@{domain}"
        n = 1
        while candidate in existing_emails:
            candidate = f"c{next_id}-{n}.{local}@{domain}"
            n += 1
        existing_emails.add(candidate)

        conv_date = lead.get("converted_date")
        if conv_date is None:
            created_at = lead["created_at"]
        else:
            base = conv_date if isinstance(conv_date, date) else conv_date
            created_at = datetime.combine(base, time(random.randint(9, 17), random.randint(0, 59)))

        if isinstance(created_at, date) and not isinstance(created_at, datetime):
            created_at = datetime.combine(created_at, time(12, 0))

        new_rows.append({
            "id": next_id,
            "lead_id": lead["id"],
            "account_id": account_id,
            "first_name": lead["first_name"],
            "last_name": lead["last_name"],
            "email": candidate,
            "title": lead["title"],
            "seniority": lead["seniority"],
            "persona": lead["persona"],
            "role_in_deal": role_in_deal_map.get(lead["persona"], "User"),
            "do_not_email": False,
            "created_at": created_at,
        })
        next_id += 1

    # Back-fill lead.account_id for the leads where we synthesized one.
    if lead_account_backfill:
        backfill_df = pl.DataFrame(
            [{"id": lid, "backfill_account_id": aid}
             for lid, aid in lead_account_backfill.items()],
            schema={"id": pl.Int64, "backfill_account_id": pl.Int64},
        )
        leads_df = leads_df.join(backfill_df, on="id", how="left").with_columns(
            pl.coalesce([pl.col("account_id"), pl.col("backfill_account_id")]).alias("account_id")
        ).drop("backfill_account_id")

    if not new_rows:
        return contacts_df, leads_df

    new_df = pl.DataFrame(new_rows, schema=contacts_df.schema)
    return pl.concat([contacts_df, new_df]), leads_df


# ============================================================================
# Generators - Opportunity & stage transition
# ============================================================================
def gen_opportunity(
    leads_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
    accounts_df: pl.DataFrame,
    sales_rep_df: pl.DataFrame,
    stages_df: pl.DataFrame,
) -> pl.DataFrame:
    """Generate 2,500 opportunities.

    Sources:
      * ~75% from leads that converted_to_contact (find the contact via lead_id)
      * ~25% from direct outbound contacts (no source_lead_id)
    """
    rows = []
    opp_id = 1

    contact_rows = contacts_df.to_dicts()
    contact_by_lead = {c["lead_id"]: c for c in contact_rows if c["lead_id"] is not None}
    contacts_by_account = defaultdict(list)
    for c in contact_rows:
        contacts_by_account[c["account_id"]].append(c)

    # Map lead_id -> lead row
    lead_by_id = {r["id"]: r for r in leads_df.to_dicts()}
    account_by_id = {r["id"]: r for r in accounts_df.to_dicts()}

    ae_smb = [r["id"] for r in sales_rep_df.iter_rows(named=True) if r["role"] == "AE_SMB"]
    ae_mid = [r["id"] for r in sales_rep_df.iter_rows(named=True) if r["role"] == "AE_Mid"]
    ae_ent = [r["id"] for r in sales_rep_df.iter_rows(named=True) if r["role"] == "AE_Enterprise"]
    sdr_ids = [r["id"] for r in sales_rep_df.iter_rows(named=True) if r["role"] == "SDR"]

    ae_by_tier = {"SMB": ae_smb, "Mid": ae_mid, "Enterprise": ae_ent}

    # Identify converted leads (status='converted_to_contact')
    converted_leads = leads_df.filter(pl.col("status") == "converted_to_contact").to_dicts()
    random.shuffle(converted_leads)

    n_from_lead = int(N_OPPORTUNITY * 0.75)
    n_direct = N_OPPORTUNITY - n_from_lead

    # Stage 1 (Discovery) - we'll start all opps in Discovery in stage_transition,
    # then advance them in gen_stage_transition. For now record initial pos.
    stage_id_by_name = dict(zip(stages_df["stage_name"].to_list(), stages_df["id"].to_list()))

    # Part 1: opps from converted leads
    count = 0
    for lead in converted_leads:
        if count >= n_from_lead:
            break
        # Find contact derived from this lead
        contact = contact_by_lead.get(lead["id"])
        if contact is None:
            continue
        account_id = contact["account_id"]
        account = account_by_id.get(account_id)
        if account is None:
            continue
        tier = account["account_tier"]

        # Amount by tier
        if tier == "SMB":
            amount = round(random.triangular(5_000, 25_000, 12_000), 2)
        elif tier == "Mid":
            amount = round(random.triangular(25_000, 100_000, 50_000), 2)
        else:
            amount = round(random.triangular(100_000, 500_000, 180_000), 2)

        # Created date: shortly after lead.converted_date
        conv_date = lead.get("converted_date")
        if conv_date is None:
            created_dt = random_datetime_between(
                HISTORY_START + timedelta(days=30), TODAY - timedelta(days=14)
            )
        else:
            created_dt = datetime.combine(
                conv_date + timedelta(days=random.randint(0, 5)),
                time(random.randint(9, 17), random.randint(0, 59)),
            )

        # Expected close: depends on tier (sales cycle length)
        if tier == "SMB":
            cycle_days = random.randint(20, 60)
        elif tier == "Mid":
            cycle_days = random.randint(60, 150)
        else:
            cycle_days = random.randint(120, 300)
        expected_close = created_dt.date() + timedelta(days=cycle_days)

        opportunity_name = f"{account['company_name']} - Stratosend Platform"
        ae_id = random.choice(ae_by_tier[tier]) if ae_by_tier[tier] else None
        if ae_id is None:
            continue
        sourced_by_sdr = lead.get("assigned_sdr_id")

        rows.append({
            "id": opp_id,
            "opportunity_name": opportunity_name[:200],
            "account_id": account_id,
            "primary_contact_id": contact["id"],
            "current_stage_id": stage_id_by_name["Discovery"],  # placeholder, reconciled
            "owner_ae_id": ae_id,
            "sourced_by_sdr_id": sourced_by_sdr,
            "source_lead_id": lead["id"],
            "source_id": lead["source_id"],
            "amount_usd": amount,
            "expected_close_date": expected_close,
            "actual_close_date": None,         # reconciled
            "created_at": created_dt,
            "won_lost_reason": None,           # filled if closed
        })
        opp_id += 1
        count += 1

    # Part 2: direct outbound opportunities (contacts with no lead origin)
    direct_contacts = [c for c in contact_rows if c["lead_id"] is None]
    random.shuffle(direct_contacts)
    count = 0
    for contact in direct_contacts:
        if count >= n_direct:
            break
        account_id = contact["account_id"]
        account = account_by_id.get(account_id)
        if account is None:
            continue
        tier = account["account_tier"]
        if tier == "SMB":
            amount = round(random.triangular(5_000, 25_000, 12_000), 2)
        elif tier == "Mid":
            amount = round(random.triangular(25_000, 100_000, 50_000), 2)
        else:
            amount = round(random.triangular(100_000, 500_000, 180_000), 2)
        created_dt = random_datetime_between(
            HISTORY_START + timedelta(days=60), TODAY - timedelta(days=14)
        )
        if tier == "SMB":
            cycle_days = random.randint(20, 60)
        elif tier == "Mid":
            cycle_days = random.randint(60, 150)
        else:
            cycle_days = random.randint(120, 300)
        expected_close = created_dt.date() + timedelta(days=cycle_days)
        ae_id = random.choice(ae_by_tier[tier]) if ae_by_tier[tier] else None
        if ae_id is None:
            continue

        rows.append({
            "id": opp_id,
            "opportunity_name": f"{account['company_name']} - Stratosend Platform"[:200],
            "account_id": account_id,
            "primary_contact_id": contact["id"],
            "current_stage_id": stage_id_by_name["Discovery"],
            "owner_ae_id": ae_id,
            "sourced_by_sdr_id": random.choice(sdr_ids) if random.random() < 0.6 else None,
            "source_lead_id": None,
            "source_id": random.choice([7, 8, 9]),  # OUTBOUND_SDR / CONFERENCE / PARTNER
            "amount_usd": amount,
            "expected_close_date": expected_close,
            "actual_close_date": None,
            "created_at": created_dt,
            "won_lost_reason": None,
        })
        opp_id += 1
        count += 1

    return pl.DataFrame(rows)


def gen_stage_transition(
    opps_df: pl.DataFrame,
    stages_df: pl.DataFrame,
    sales_rep_df: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build stage_transition history for each opp.

    Returns (transitions_df, updated_opps_df) where opps_df has updated
    current_stage_id, actual_close_date, won_lost_reason.

    Each opp goes through Discovery -> ... -> {Won/Lost/Open}.
    Per-stage advancement probabilities (match `advance_prob` below and
    ER doc section 8 row "Transition logic"):
      * Discovery -> Demo:        0.90 advance, otherwise close-Lost
      * Demo -> Eval:             0.82
      * Eval -> Proposal:         0.72
      * Proposal -> Negotiation:  0.78
      * Negotiation -> Won:       0.72
    Final mix target: ~25% Won, ~50% Lost, ~25% Open.
    """
    transitions = []
    tran_id = 1
    stage_id_by_order = dict(zip(stages_df["stage_order"].to_list(),
                                 stages_df["id"].to_list()))
    stage_name_by_id = dict(zip(stages_df["id"].to_list(),
                                stages_df["stage_name"].to_list()))
    stage_id_by_name = dict(zip(stages_df["stage_name"].to_list(),
                                stages_df["id"].to_list()))
    rep_ids = sales_rep_df["id"].to_list()

    # Per-stage advance probabilities. Tuned so ~25% of opps reach Closed-Won,
    # ~50% Closed-Lost, ~25% remain open at TODAY.
    advance_prob = {1: 0.90, 2: 0.82, 3: 0.72, 4: 0.78, 5: 0.72}

    # Mutate opps in place by collecting updates
    opp_updates = []

    for opp in opps_df.iter_rows(named=True):
        cur_stage_order = 1   # Discovery
        cur_stage_id = stage_id_by_order[1]
        cur_dt = opp["created_at"]
        if isinstance(cur_dt, date) and not isinstance(cur_dt, datetime):
            cur_dt = datetime.combine(cur_dt, time(9, 0))
        owner_ae = opp["owner_ae_id"]
        sdr = opp["sourced_by_sdr_id"]

        # Initial transition: NULL -> Discovery
        initial_close = opp["expected_close_date"]
        transitions.append({
            "id": tran_id,
            "opportunity_id": opp["id"],
            "from_stage_id": None,
            "to_stage_id": cur_stage_id,
            "transitioned_at": cur_dt,
            "transitioned_by_rep_id": sdr if sdr else owner_ae,
            "days_in_previous_stage": 0,
            "expected_close_date_at_transition": initial_close,
            "notes": "Opportunity created.",
        })
        tran_id += 1

        last_transition_dt = cur_dt
        current_expected_close = initial_close
        won_lost_reason = None
        closed = False

        # Advance through stages
        while cur_stage_order < 5 and not closed:
            # Decide if opp advances or dies here
            p_advance = advance_prob[cur_stage_order]
            roll = random.random()

            # Days in current stage
            tier_mult = 1.0
            # Tier multiplier (inferred from amount)
            if opp["amount_usd"] >= 100_000:
                tier_mult = 2.5
            elif opp["amount_usd"] >= 25_000:
                tier_mult = 1.5
            base_days = {1: 10, 2: 15, 3: 25, 4: 20, 5: 15}[cur_stage_order]
            days_in_stage = int(random.uniform(base_days * 0.5, base_days * 1.8) * tier_mult)

            next_dt = last_transition_dt + timedelta(
                days=days_in_stage, hours=random.randint(-3, 3)
            )

            # If next_dt > TODAY, opp stays "open" at current stage
            if next_dt.date() > TODAY:
                # Don't transition - opp remains here
                break

            if roll < p_advance:
                # Advance to next stage — but ~4% of advancements regress by
                # one stage first (deal slips back to the previous stage for
                # a re-discovery / re-eval cycle, then advances again). This
                # creates the small-but-nonzero stage-regression population
                # that query B19 looks for.
                regression_chance = 0.04 if cur_stage_order >= 2 else 0.0
                if random.random() < regression_chance:
                    prev_stage_order = cur_stage_order - 1
                    prev_stage_id = stage_id_by_order[prev_stage_order]
                    regress_dt = next_dt
                    transitions.append({
                        "id": tran_id,
                        "opportunity_id": opp["id"],
                        "from_stage_id": cur_stage_id,
                        "to_stage_id": prev_stage_id,
                        "transitioned_at": regress_dt,
                        "transitioned_by_rep_id": owner_ae,
                        "days_in_previous_stage": days_in_stage,
                        "expected_close_date_at_transition": current_expected_close,
                        "notes": f"Regressed to {stage_name_by_id[prev_stage_id]} "
                                 f"(re-{'discovery' if prev_stage_order==1 else 'evaluation'}).",
                    })
                    tran_id += 1
                    cur_stage_id = prev_stage_id
                    cur_stage_order = prev_stage_order
                    last_transition_dt = regress_dt
                    # Spend a small amount of time before re-advancing
                    re_advance_days = random.randint(7, 21)
                    next_dt = regress_dt + timedelta(days=re_advance_days)
                    if next_dt.date() > TODAY:
                        break
                    days_in_stage = re_advance_days

                next_stage_order = cur_stage_order + 1
                next_stage_id = stage_id_by_order[next_stage_order]
                # Sometimes the close date slips (10-25% chance, especially in later stages)
                slip_chance = 0.15 + (cur_stage_order * 0.04)
                if random.random() < slip_chance:
                    current_expected_close = current_expected_close + timedelta(
                        days=random.randint(7, 30)
                    )
                transitions.append({
                    "id": tran_id,
                    "opportunity_id": opp["id"],
                    "from_stage_id": cur_stage_id,
                    "to_stage_id": next_stage_id,
                    "transitioned_at": next_dt,
                    "transitioned_by_rep_id": owner_ae,
                    "days_in_previous_stage": days_in_stage,
                    "expected_close_date_at_transition": current_expected_close,
                    "notes": f"Advanced to {stage_name_by_id[next_stage_id]}.",
                })
                tran_id += 1
                cur_stage_order = next_stage_order
                cur_stage_id = next_stage_id
                last_transition_dt = next_dt
            else:
                # Lost at current stage
                lost_stage_id = stage_id_by_name["Closed-Lost"]
                transitions.append({
                    "id": tran_id,
                    "opportunity_id": opp["id"],
                    "from_stage_id": cur_stage_id,
                    "to_stage_id": lost_stage_id,
                    "transitioned_at": next_dt,
                    "transitioned_by_rep_id": owner_ae,
                    "days_in_previous_stage": days_in_stage,
                    "expected_close_date_at_transition": current_expected_close,
                    "notes": "Closed-Lost (stalled at current stage).",
                })
                tran_id += 1
                cur_stage_id = lost_stage_id
                last_transition_dt = next_dt
                won_lost_reason = random.choice(WIN_LOSS_REASONS_LOST)
                closed = True

        # If we made it to Negotiation alive, decide Won vs Lost
        if cur_stage_order == 5 and not closed:
            roll = random.random()
            base_days = 18
            tier_mult = 1.0
            if opp["amount_usd"] >= 100_000:
                tier_mult = 2.5
            elif opp["amount_usd"] >= 25_000:
                tier_mult = 1.5
            days_in_stage = int(random.uniform(base_days * 0.5, base_days * 1.8) * tier_mult)
            next_dt = last_transition_dt + timedelta(
                days=days_in_stage, hours=random.randint(-3, 3)
            )
            if next_dt.date() <= TODAY:
                if roll < 0.72:
                    won_id = stage_id_by_name["Closed-Won"]
                    transitions.append({
                        "id": tran_id,
                        "opportunity_id": opp["id"],
                        "from_stage_id": cur_stage_id,
                        "to_stage_id": won_id,
                        "transitioned_at": next_dt,
                        "transitioned_by_rep_id": owner_ae,
                        "days_in_previous_stage": days_in_stage,
                        "expected_close_date_at_transition": current_expected_close,
                        "notes": "Closed-Won.",
                    })
                    tran_id += 1
                    cur_stage_id = won_id
                    won_lost_reason = random.choice(WIN_LOSS_REASONS_WON)
                    closed = True
                else:
                    lost_id = stage_id_by_name["Closed-Lost"]
                    transitions.append({
                        "id": tran_id,
                        "opportunity_id": opp["id"],
                        "from_stage_id": cur_stage_id,
                        "to_stage_id": lost_id,
                        "transitioned_at": next_dt,
                        "transitioned_by_rep_id": owner_ae,
                        "days_in_previous_stage": days_in_stage,
                        "expected_close_date_at_transition": current_expected_close,
                        "notes": "Closed-Lost at Negotiation.",
                    })
                    tran_id += 1
                    cur_stage_id = lost_id
                    won_lost_reason = random.choice(WIN_LOSS_REASONS_LOST)
                    closed = True
                last_transition_dt = next_dt

        # Record final state for opp update
        opp_updates.append({
            "id": opp["id"],
            "current_stage_id_new": cur_stage_id,
            "actual_close_date_new": (
                last_transition_dt.date() if closed else None
            ),
            "won_lost_reason_new": won_lost_reason,
            "expected_close_date_new": current_expected_close,
        })

    transitions_df = pl.DataFrame(transitions)
    updates_df = pl.DataFrame(opp_updates)

    # Apply updates back to opps_df
    opps_df = opps_df.join(updates_df, on="id", how="left")
    opps_df = opps_df.with_columns(
        pl.col("current_stage_id_new").alias("current_stage_id"),
        pl.col("actual_close_date_new").alias("actual_close_date"),
        pl.col("won_lost_reason_new").alias("won_lost_reason"),
        pl.col("expected_close_date_new").alias("expected_close_date"),
    ).drop(["current_stage_id_new", "actual_close_date_new",
            "won_lost_reason_new", "expected_close_date_new"])

    # Reorder columns to original order
    original_cols = [
        "id", "opportunity_name", "account_id", "primary_contact_id",
        "current_stage_id", "owner_ae_id", "sourced_by_sdr_id", "source_lead_id",
        "source_id", "amount_usd", "expected_close_date", "actual_close_date",
        "created_at", "won_lost_reason",
    ]
    opps_df = opps_df.select(original_cols)

    return transitions_df, opps_df


def gen_target_account_list(
    accounts_df: pl.DataFrame,
    sales_rep_df: pl.DataFrame,
) -> pl.DataFrame:
    """300 ABM target_account_list rows across several lists. Bias to Mid/Enterprise."""
    rows = []
    tier_weight = {"SMB": 0.10, "Mid": 0.45, "Enterprise": 0.45}
    account_rows = accounts_df.to_dicts()
    weighted_accounts = []
    for a in account_rows:
        w = tier_weight[a["account_tier"]]
        weighted_accounts.extend([a] * int(w * 100))

    enterprise_aes = [r["id"] for r in sales_rep_df.iter_rows(named=True)
                      if r["role"] == "AE_Enterprise"]
    if not enterprise_aes:
        enterprise_aes = [r["id"] for r in sales_rep_df.iter_rows(named=True)
                          if r["role"].startswith("AE")]

    tab_id = 1
    used = set()
    while tab_id <= N_TARGET_ACCOUNT_LIST:
        list_name = random.choice(ABM_LIST_TEMPLATES)
        acct = random.choice(weighted_accounts)
        key = (list_name, acct["id"])
        if key in used:
            continue
        used.add(key)

        tier = random.choices(["Tier 1", "Tier 2", "Tier 3"], weights=[0.30, 0.45, 0.25], k=1)[0]
        added = random_date_between(HISTORY_START + timedelta(days=30),
                                    TODAY - timedelta(days=30))
        engagement_score = random.randint(0, 350)
        notes = random.choice([
            "Strategic logo - executive sponsorship in place",
            "Champion identified in DevOps team",
            "Long-standing competitor incumbent (Datadog)",
            "Procurement contact established",
            "Multi-stakeholder evaluation underway",
            "Awaiting renewal window",
            None,
            None,
        ])
        rows.append({
            "id": tab_id,
            "list_name": list_name,
            "account_id": acct["id"],
            "tier": tier,
            "owner_rep_id": random.choice(enterprise_aes),
            "added_date": added,
            "engagement_score": engagement_score,
            "notes": notes,
        })
        tab_id += 1

    return pl.DataFrame(rows)


# ============================================================================
# Final reconcile passes
# ============================================================================
def reconcile_account_lifetime_arr(
    accounts_df: pl.DataFrame,
    opps_df: pl.DataFrame,
    stages_df: pl.DataFrame,
) -> pl.DataFrame:
    """account.lifetime_arr_won_usd = SUM(opp.amount WHERE Won)."""
    won_stage_id = stages_df.filter(pl.col("stage_name") == "Closed-Won")["id"][0]
    won_opps = opps_df.filter(pl.col("current_stage_id") == won_stage_id)
    arr_per_acct = (
        won_opps
        .group_by("account_id")
        .agg(pl.col("amount_usd").sum().alias("arr_won_sum"))
    )
    accounts_df = accounts_df.join(
        arr_per_acct, left_on="id", right_on="account_id", how="left"
    )
    accounts_df = accounts_df.with_columns(
        pl.col("arr_won_sum").fill_null(0.0).alias("lifetime_arr_won_usd")
    ).drop(["lifetime_arr_won_usd_right" if "lifetime_arr_won_usd_right" in accounts_df.columns
            else "arr_won_sum"])
    if "arr_won_sum" in accounts_df.columns:
        accounts_df = accounts_df.drop("arr_won_sum")
    return accounts_df


def reconcile_account_is_target(
    accounts_df: pl.DataFrame,
    target_list_df: pl.DataFrame,
) -> pl.DataFrame:
    """account.is_target_account = (id IN target_account_list)."""
    target_ids = set(target_list_df["account_id"].unique().to_list())
    is_target = accounts_df["id"].is_in(list(target_ids)).rename("is_target_account_new")
    accounts_df = accounts_df.with_columns(is_target).drop("is_target_account") \
        .rename({"is_target_account_new": "is_target_account"})
    return accounts_df


def reconcile_content_asset_downloads(
    assets_df: pl.DataFrame,
    engagements_df: pl.DataFrame,
) -> pl.DataFrame:
    """content_asset.total_downloads = COUNT(content_engagement WHERE download)."""
    dl_counts = (
        engagements_df.filter(pl.col("engagement_type") == "download")
        .group_by("content_asset_id")
        .agg(pl.len().alias("dl_count"))
    )
    assets_df = assets_df.join(
        dl_counts, left_on="id", right_on="content_asset_id", how="left"
    )
    assets_df = assets_df.with_columns(
        pl.col("dl_count").fill_null(0).cast(pl.Int64).alias("total_downloads_new")
    ).drop("total_downloads").rename({"total_downloads_new": "total_downloads"})
    if "dl_count" in assets_df.columns:
        assets_df = assets_df.drop("dl_count")
    return assets_df


def reconcile_campaign_member_attribution(
    members_df: pl.DataFrame,
    opps_df: pl.DataFrame,
    contacts_df: pl.DataFrame,
    leads_df: pl.DataFrame,
    stages_df: pl.DataFrame,
) -> pl.DataFrame:
    """W-shaped attribution. For each Won opportunity:
    Assign 30% credit to first-touch member, 30% to MQL-creation touch,
    30% to opp-creation touch, 10% spread across other influencer touches.

    For non-Won opps, leave attribution at 0%.

    Returns members_df with attribution_credit_pct populated.
    """
    won_stage_id = stages_df.filter(pl.col("stage_name") == "Closed-Won")["id"][0]
    won_opps = opps_df.filter(pl.col("current_stage_id") == won_stage_id).to_dicts()

    # Build lookup: account -> opp(s)
    contact_to_account = dict(zip(contacts_df["id"].to_list(),
                                  contacts_df["account_id"].to_list()))
    lead_to_mql_date = dict(zip(leads_df["id"].to_list(),
                                leads_df["mql_date"].to_list()))

    # Pre-index members by account: for each member, what account does it touch?
    # lead -> account_id (via leads_df) or contact -> account_id
    lead_to_account = dict(zip(leads_df["id"].to_list(),
                               leads_df["account_id"].to_list()))

    member_rows = members_df.to_dicts()
    credit_map = {}  # member_id -> credit_pct

    for opp in won_opps:
        account_id = opp["account_id"]
        opp_created = opp["created_at"]
        if isinstance(opp_created, date) and not isinstance(opp_created, datetime):
            opp_created = datetime.combine(opp_created, time(0, 0))
        # MQL date from source lead
        mql_dt = None
        if opp["source_lead_id"]:
            md = lead_to_mql_date.get(opp["source_lead_id"])
            if md:
                mql_dt = datetime.combine(md, time(0, 0))

        # Path: members where lead.account == this account OR contact.account == this account
        path_members = []
        for m in member_rows:
            owner_account = None
            if m["lead_id"]:
                owner_account = lead_to_account.get(m["lead_id"])
            elif m["contact_id"]:
                owner_account = contact_to_account.get(m["contact_id"])
            if owner_account == account_id:
                eng = m["engaged_at"]
                if isinstance(eng, date) and not isinstance(eng, datetime):
                    eng = datetime.combine(eng, time(0, 0))
                if eng <= opp_created:
                    path_members.append((m["id"], eng))
        if not path_members:
            continue

        path_members.sort(key=lambda x: x[1])
        first_touch_id = path_members[0][0]
        # opp-creation touch: last member before opp_created
        opp_touch_id = path_members[-1][0]
        # MQL touch: prefer the closest touch AT OR BEFORE mql_dt; fall back to
        # the closest touch AFTER mql_dt only if no pre-MQL touch exists.
        # (The earlier version used abs() distance, which could pick a touch
        # well after MQL — semantically wrong for a "MQL-creation touch".)
        mql_touch_id = None
        if mql_dt:
            pre_mql = [pm for pm in path_members if pm[1] <= mql_dt]
            if pre_mql:
                closest = max(pre_mql, key=lambda x: x[1])  # latest pre-MQL touch
            else:
                closest = min(path_members, key=lambda x: x[1] - mql_dt)
            mql_touch_id = closest[0]

        weights = defaultdict(float)
        weights[first_touch_id] += 30.0
        weights[opp_touch_id] += 30.0
        if mql_touch_id is not None:
            weights[mql_touch_id] += 30.0
            anchors = {first_touch_id, opp_touch_id, mql_touch_id}
        else:
            # No MQL touch (lead didn't reach MQL) -> redistribute that 30% to first+opp
            weights[first_touch_id] += 15.0
            weights[opp_touch_id] += 15.0
            anchors = {first_touch_id, opp_touch_id}

        # Other influencers share the remaining 10%
        others = [pid for pid, _ in path_members if pid not in anchors]
        if others:
            share = 10.0 / len(others)
            for pid in others:
                weights[pid] += share
        else:
            # Spread extra 10% across anchors
            extra = 10.0 / len(anchors)
            for pid in anchors:
                weights[pid] += extra

        for pid, w in weights.items():
            credit_map[pid] = credit_map.get(pid, 0.0) + w

    # Cap accumulated credit at 100% per campaign_member: the field
    # is interpreted as "this member's share of attribution", and a single
    # campaign_member row by definition cannot carry more than the whole
    # path credit. (Without this cap, a person on the path of multiple Won
    # opps could accumulate >100%, which we observed in earlier runs.)
    for pid in list(credit_map.keys()):
        if credit_map[pid] > 100.0:
            credit_map[pid] = 100.0

    # Apply credits to members_df
    credits = []
    for m in member_rows:
        credits.append({"id": m["id"],
                        "attribution_credit_pct_new": credit_map.get(m["id"], 0.0)})
    credits_df = pl.DataFrame(credits)
    members_df = members_df.join(credits_df, on="id", how="left")
    members_df = members_df.with_columns(
        pl.col("attribution_credit_pct_new").fill_null(0.0).alias("attribution_credit_pct")
    ).drop("attribution_credit_pct_new")
    if "attribution_credit_pct_right" in members_df.columns:
        members_df = members_df.drop("attribution_credit_pct_right")
    return members_df


# ============================================================================
# Orchestration: generate_all_tsv
# ============================================================================
def generate_all_tsv() -> None:
    """Generate all 16 TSV files. Idempotent: deletes existing first.

    Phases (per spec section 11):
      1. Lookups
      2. Core entities (sales_rep, account, campaign, content_asset)
      3. Leads & contacts
      4. Marketing event tables (campaign_member, content_engagement, sales_email,
         lead_scoring_event)
      5. Reconcile lead funnel (lead.score / mql_date / status / sql_date / converted_date)
      6. Sales pipeline (opportunity + stage_transition)
      7. ABM + back-reconcile
      8. Write TSVs
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Phase 1 - Lookups ...")
    df_lead_source = gen_lead_source()
    df_industry = gen_industry()
    df_stage = gen_opportunity_stage()

    print("Phase 2 - Core entities ...")
    df_sales_rep = gen_sales_rep()
    sales_rep_rows = df_sales_rep.to_dicts()
    manager_ids = [r["id"] for r in sales_rep_rows if r["role"] == "Manager"]
    ae_ids = [r["id"] for r in sales_rep_rows if r["role"].startswith("AE")]
    sdr_ids = [r["id"] for r in sales_rep_rows if r["role"] == "SDR"]

    df_account = gen_account(df_industry["id"].to_list(), ae_ids)
    df_campaign = gen_campaign(df_industry["id"].to_list(), manager_ids)
    df_content_asset = gen_content_asset()

    print("Phase 3 - Leads & Contacts ...")
    df_lead = gen_lead(
        source_ids=df_lead_source["id"].to_list(),
        account_ids=df_account["id"].to_list(),
        sdr_ids=sdr_ids,
        campaign_ids=df_campaign["id"].to_list(),
        campaigns_df=df_campaign,
    )
    df_contact = gen_contact(df_lead, df_account)

    print("Phase 4 - Marketing event tables ...")
    df_campaign_member = gen_campaign_member(df_campaign, df_lead, df_contact)
    df_content_engagement = gen_content_engagement(
        df_content_asset, df_lead, df_contact, df_campaign
    )
    df_sales_email = gen_sales_email(sales_rep_rows, df_lead, df_contact)
    df_scoring_event = gen_lead_scoring_event(
        df_lead, df_content_engagement, df_campaign_member, df_sales_email
    )

    print("Phase 5 - Reconcile lead funnel ...")
    df_lead = reconcile_lead_funnel(
        df_lead, df_scoring_event, df_sales_email, df_contact
    )

    # Ensure every converted_to_contact lead has a contact (so the lead-sourced
    # sales funnel is end-to-end traceable).
    df_contact, df_lead = ensure_contacts_for_converted_leads(
        df_lead, df_contact, df_account
    )

    print("Phase 6 - Opportunity + stage transitions ...")
    df_opportunity = gen_opportunity(
        df_lead, df_contact, df_account, df_sales_rep, df_stage
    )
    df_stage_transition, df_opportunity = gen_stage_transition(
        df_opportunity, df_stage, df_sales_rep
    )

    print("Phase 7 - ABM + back-reconcile ...")
    df_target_list = gen_target_account_list(df_account, df_sales_rep)
    df_account = reconcile_account_is_target(df_account, df_target_list)
    df_account = reconcile_account_lifetime_arr(df_account, df_opportunity, df_stage)
    df_content_asset = reconcile_content_asset_downloads(
        df_content_asset, df_content_engagement
    )
    df_campaign_member = reconcile_campaign_member_attribution(
        df_campaign_member, df_opportunity, df_contact, df_lead, df_stage
    )

    print("Phase 8 - Write TSVs ...")
    # Topological order
    df_lead_source.write_csv(DATA_DIR / "01_lead_source.tsv", separator="\t")
    df_industry.write_csv(DATA_DIR / "02_industry.tsv", separator="\t")
    df_stage.write_csv(DATA_DIR / "03_opportunity_stage.tsv", separator="\t")
    df_sales_rep.write_csv(DATA_DIR / "04_sales_rep.tsv", separator="\t")
    df_account.write_csv(DATA_DIR / "05_account.tsv", separator="\t")
    df_campaign.write_csv(DATA_DIR / "06_campaign.tsv", separator="\t")
    df_content_asset.write_csv(DATA_DIR / "07_content_asset.tsv", separator="\t")
    df_lead.write_csv(DATA_DIR / "08_lead.tsv", separator="\t")
    df_contact.write_csv(DATA_DIR / "09_contact.tsv", separator="\t")
    df_opportunity.write_csv(DATA_DIR / "10_opportunity.tsv", separator="\t")
    df_stage_transition.write_csv(DATA_DIR / "11_stage_transition.tsv", separator="\t")
    df_campaign_member.write_csv(DATA_DIR / "12_campaign_member.tsv", separator="\t")
    df_content_engagement.write_csv(DATA_DIR / "13_content_engagement.tsv", separator="\t")
    df_sales_email.write_csv(DATA_DIR / "14_sales_email.tsv", separator="\t")
    df_scoring_event.write_csv(DATA_DIR / "15_lead_scoring_event.tsv", separator="\t")
    df_target_list.write_csv(DATA_DIR / "16_target_account_list.tsv", separator="\t")
    print(f"  TSVs written to {DATA_DIR}")

    # Print row counts
    rows_summary = {
        "lead_source": df_lead_source.height,
        "industry": df_industry.height,
        "opportunity_stage": df_stage.height,
        "sales_rep": df_sales_rep.height,
        "account": df_account.height,
        "campaign": df_campaign.height,
        "content_asset": df_content_asset.height,
        "lead": df_lead.height,
        "contact": df_contact.height,
        "opportunity": df_opportunity.height,
        "stage_transition": df_stage_transition.height,
        "campaign_member": df_campaign_member.height,
        "content_engagement": df_content_engagement.height,
        "sales_email": df_sales_email.height,
        "lead_scoring_event": df_scoring_event.height,
        "target_account_list": df_target_list.height,
    }
    print("Row counts:")
    for name, n in rows_summary.items():
        print(f"  {name:30s}: {n:>7,}")
    print(f"  TOTAL: {sum(rows_summary.values()):>7,}")


# ============================================================================
# SQLite load order + DB build
# ============================================================================
LOAD_ORDER: list[tuple[str, type]] = [
    ("01_lead_source.tsv",        LeadSource),
    ("02_industry.tsv",           Industry),
    ("03_opportunity_stage.tsv",  OpportunityStage),
    ("04_sales_rep.tsv",          SalesRep),
    ("05_account.tsv",            Account),
    ("06_campaign.tsv",           Campaign),
    ("07_content_asset.tsv",      ContentAsset),
    ("08_lead.tsv",               Lead),
    ("09_contact.tsv",            Contact),
    ("10_opportunity.tsv",        Opportunity),
    ("11_stage_transition.tsv",   StageTransition),
    ("12_campaign_member.tsv",    CampaignMember),
    ("13_content_engagement.tsv", ContentEngagement),
    ("14_sales_email.tsv",        SalesEmail),
    ("15_lead_scoring_event.tsv", LeadScoringEvent),
    ("16_target_account_list.tsv",TargetAccountList),
]


def _coerce_value(col_type, value):
    if value is None:
        return None
    type_name = str(col_type).lower()
    if "date" in type_name and "time" not in type_name:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return datetime.fromisoformat(value).date()
        if isinstance(value, datetime):
            return value.date()
        return value
    if "datetime" in type_name:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    if "bool" in type_name:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "t", "yes")
    if "integer" in type_name:
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip() == "":
            return None
        return value
    return value


def create_sqlite_database() -> None:
    """Create the SQLite database from TSV files. Idempotent."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        for filename, model in LOAD_ORDER:
            path = DATA_DIR / filename
            df = pl.read_csv(
                path,
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=2000,
                null_values=["", "null", "NULL"],
            )
            mapper_cols = {c.key: c.type for c in model.__table__.columns}
            objs = []
            for row in df.iter_rows(named=True):
                obj_kwargs = {}
                for k, v in row.items():
                    if k in mapper_cols:
                        obj_kwargs[k] = _coerce_value(mapper_cols[k], v)
                objs.append(model(**obj_kwargs))
            session.bulk_save_objects(objs)
            session.flush()
            print(f"Loaded {filename} -> {model.__tablename__} ({df.height} rows)")
        session.commit()

    print(f"SQLite database created at {DATABASE_PATH}")


def main() -> None:
    print("=" * 70)
    print("Stratosend B2B SaaS - Demand Generation Dataset Generator")
    print("=" * 70)
    generate_all_tsv()
    create_sqlite_database()
    print("Done.")


if __name__ == "__main__":
    main()
