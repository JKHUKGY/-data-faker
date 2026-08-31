"""
Media & Entertainment — Anime IP Merchandise Licensing & Retail Sell-Through Analytics fake data generator
Complexity: Medium

Business context:
Ember & Ash Licensing Group is a fictional North American entertainment IP licensing agency
headquartered in El Segundo, California, representing multiple anime IPs for merchandise licensing
across North America (toys, apparel, collectible trading cards, home goods, etc). It works with
retailers and collects royalties on the net wholesale sales of its licensees. This dataset simulates
the full chain from "licensing agreement signing" to "retail sell-through" to "royalty settlement
audit," supporting the following analyses:
1. Content sell-through and renewal prioritization (which IP x category combinations have the
   highest retail sell-through and are worth renewing)
2. Royalty audit and underreporting risk (whether a licensee's self-reported royalty matches the
   actual sales derived from POS)
3. Popularity-to-sell-through lag (the supply-chain lag in weeks between a streaming popularity
   peak and the corresponding retail sales peak)
4. Unauthorized channel compliance (whether a licensee is distributing through channels outside
   its authorized scope)
5. Minimum guarantee (MG) attainment tracking (which contracts are lagging behind their MG pacing
   and need renegotiation before renewal)

The traps above are injected through deliberately designed correlated distributions: an anime IP's
popularity_tier directly drives the gradient in per-row average sales volume in pos_sell_through
(trap 1); licensee.compliance_score splits licensees into "clean" and "risk" cohorts, with the
"risk" cohort simultaneously driving royalty underreporting (trap 2) and unauthorized channel
leakage (trap 4); popularity_tier also drives the "season premiere" popularity spikes in
streaming_popularity_index, and each spike pulls up retail sales for the corresponding SKUs
6-10 weeks later (trap 3); IP popularity tier combined with category baseline sell-through speed
jointly drive cumulative royalty progress, causing some contracts to naturally lag behind their MG
attainment rate (trap 5). The corresponding SQL queries live in
media_anime_ip_licensing_retail_medium_sql_queries-cn.md, and are used to surface these traps.
"""

from __future__ import annotations

import random
from datetime import date
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "media_anime_ip_licensing_retail_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date, to keep results consistent across runs and independent of the system clock.
# Wherever the SQL queries need "today," they use this same literal date.
REFERENCE_DATE = date(2026, 6, 30)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# Business calibration constants
# ============================================================================

# Time span tracked for streaming popularity (2 years), earlier than the licensing/sell-through
# data window, because Ember & Ash starts tracking an anime's popularity before it breaks out, in
# order to judge whether it's worth investing in a license.
POPULARITY_HORIZON_WEEKS = 104
POPULARITY_HORIZON_START = REFERENCE_DATE - timedelta(weeks=POPULARITY_HORIZON_WEEKS)

# Window for licensing agreement signing dates. The upper bound leaves at least ~5 months of
# runway so SKU launch, POS sell-through, and at least one royalty settlement cycle all have a
# chance to occur.
AGREEMENT_SIGN_START = REFERENCE_DATE - timedelta(days=680)
AGREEMENT_SIGN_END = REFERENCE_DATE - timedelta(days=150)

# Range of licensing agreements signed per IP popularity tier. Breakout-tier IPs (viral hits)
# attract more categories and licensees competing for a license; niche-tier IPs only get a
# handful of dedicated categories willing to invest.
AGREEMENT_COUNT_RANGE_BY_TIER = {
    "breakout": (6, 9),
    "mainstream": (4, 6),
    "niche": (1, 3),
}

# IP popularity tier distribution. Most licensed IPs are "steady but not a hit" mainstream,
# a few are full-blown breakout viral hits, and a long tail of niche legacy titles are still
# licensed on a small scale.
POPULARITY_TIER_WEIGHTS = {"breakout": 5, "mainstream": 13, "niche": 6}

# Number of "season premiere" events per popularity tier. Only breakout / mainstream IPs have a
# clear premiere popularity spike within the tracking window; niche IPs have no premiere event,
# so the signal for trap 3 (popularity-to-sell-through lag) is only reliably observable on
# breakout / mainstream IPs — this is called out explicitly in the SQL query docs.
PREMIERE_COUNT_BY_TIER = {"breakout": 2, "mainstream": 1, "niche": 0}

# Baseline popularity score range (0-100 scale, analogous to a search-trend / watch-time index).
# Breakout-tier IPs maintain a high baseline even in non-premiere weeks; niche-tier IPs linger
# at low levels long-term.
POPULARITY_BASELINE_RANGE_BY_TIER = {
    "breakout": (45, 65),
    "mainstream": (30, 52),
    "niche": (10, 28),
}

# Premiere-week popularity spike range, and the decay shape (in weeks) back down to baseline
# (weeks 1/2/3 retain 70% / 45% / 25% of the peak respectively).
PREMIERE_SPIKE_RANGE = (85, 100)
PREMIERE_DECAY_FACTORS = [1.0, 0.70, 0.45, 0.25]

# Core parameter for trap 3: the supply-chain lag in weeks between a premiere popularity spike
# and the corresponding retail sell-through peak. After a new season goes viral, retailers must
# go through a "reorder -> restock the shelf" process, typically lagging 6-10 weeks before it
# shows up in POS sales, rather than reacting in the same week.
POPULARITY_TO_SALES_LAG_WEEKS = (6, 10)
LAG_BUMP_DURATION_WEEKS = 3
LAG_BUMP_MULTIPLIER_RANGE = (1.4, 1.9)

# The two licensee compliance_score cohorts. The "risk" cohort (~25%) has a historical track
# record of royalty underreporting and unauthorized channel leakage, driven by the same score for
# both trap 2 and trap 4, echoing the real-world correlation that "licensees with poor compliance
# tend to have issues across multiple dimensions."
LICENSEE_RISK_SHARE = 0.25
LICENSEE_COMPLIANCE_RANGE = {
    "clean": (70, 98),
    "risk": (35, 65),
}

# Core parameter for trap 2: the "risk" cohort systematically understates self-reported net sales
# by 8%-18% (mean ~13%); the "clean" cohort only has ±2% normal reporting noise, with a mean of
# ~0%. royalty_audit_finding backs out the true royalty from POS-derived figures and compares it
# against the self-reported royalty, clearly separating the two cohorts by the resulting variance.
UNDERREPORT_RATE_RANGE = {
    "risk": (0.08, 0.18),
    "clean": (-0.02, 0.02),
}

# Royalty audit status thresholds (based on variance_pct = (POS-derived royalty - self-reported
# royalty) / POS-derived royalty).
AUDIT_CONFIRMED_THRESHOLD_PCT = 12.0
AUDIT_FLAGGED_THRESHOLD_PCT = 5.0

# Core parameter for trap 4: SKUs belonging to the "risk" cohort have a ~15% chance of generating
# additional sales in an unauthorized channel (preferring ecommerce_marketplace, since e-commerce
# platforms are the easiest to penetrate via gray-market resale; if that channel is already
# authorized, it falls back to direct_to_consumer_online). The "clean" cohort only has ~1% noise,
# which does not constitute systemic violation.
UNAUTHORIZED_CHANNEL_LEAK_PROB = {"risk": 0.15, "clean": 0.01}

# Product category lookup table, covering typical North American anime merchandise categories.
# benchmark_royalty_rate_pct is the industry-standard reference royalty rate on net wholesale
# sales (consumer product entertainment licensing typically runs 7%-12%).
PRODUCT_CATEGORIES = [
    (1, "toys_action_figures", "Toys & Action Figures", 10.0),
    (2, "apparel", "Apparel", 8.0),
    (3, "collectible_trading_cards", "Collectible Trading Cards", 12.0),
    (4, "home_goods_decor", "Home Goods & Decor", 9.0),
    (5, "stationery_office", "Stationery & Office", 7.0),
    (6, "accessories_bags", "Accessories & Bags", 10.0),
]

# Range for the number of SKUs per contract, differentiated by category — collectible trading
# cards naturally have the highest SKU density (one SKU per character/series), home goods the
# lowest.
SKU_COUNT_RANGE_BY_CATEGORY = {
    "toys_action_figures": (5, 10),
    "apparel": (4, 8),
    "collectible_trading_cards": (6, 13),
    "home_goods_decor": (3, 6),
    "stationery_office": (4, 7),
    "accessories_bags": (3, 6),
}

# MSRP range (USD) by category. wholesale_price_usd follows the industry-standard "keystone"
# wholesale-to-retail markup convention = 50% of MSRP, see gen_product_skus.
MSRP_RANGE_BY_CATEGORY = {
    "toys_action_figures": (12, 35),
    "apparel": (18, 45),
    "collectible_trading_cards": (5, 25),
    "home_goods_decor": (15, 60),
    "stationery_office": (6, 20),
    "accessories_bags": (20, 70),
}

# Base mean weekly units sold per SKU per channel, differentiated by category (cards have the
# highest repurchase frequency, home goods the lowest), later multiplied by the IP popularity
# tier multiplier.
CATEGORY_BASE_WEEKLY_UNITS = {
    "toys_action_figures": 40,
    "apparel": 30,
    "collectible_trading_cards": 60,
    "home_goods_decor": 18,
    "stationery_office": 22,
    "accessories_bags": 25,
}

# IP popularity tier multiplier on sell-through velocity. This is also one of the underlying
# drivers of trap 5 (MG attainment) — niche-tier IPs naturally sell through slowly, so cumulative
# royalty progress tends to fall behind the MG pacing schedule.
POPULARITY_TIER_SELLTHROUGH_MULTIPLIER = {"breakout": 1.8, "mainstream": 1.0, "niche": 0.45}

# Product lifecycle shape: ramps up to full speed within 8 weeks of launch; from week 30 onward
# decays 1.8% per week, with a decay floor of 35%.
LIFECYCLE_RAMP_WEEKS = 8
LIFECYCLE_DECAY_START_WEEK = 30
LIFECYCLE_DECAY_PER_WEEK = 0.018
LIFECYCLE_DECAY_FLOOR = 0.35

# Probability of a SKU being discontinued early, and the range (in days after launch) in which
# discontinuation occurs.
SKU_DISCONTINUE_PROB = 0.15
SKU_DISCONTINUE_DAYS_RANGE = (150, 400)

# Weights for the number of authorized channels per contract (each contract authorizes 1-3
# retail channels), and the relative weight of each channel being selected.
CHANNEL_COUNT_WEIGHTS = {1: 30, 2: 45, 3: 25}
CHANNEL_SELECTION_WEIGHTS = {
    "big_box_retail": 35,
    "specialty_retail": 30,
    "ecommerce_marketplace": 25,
    "direct_to_consumer_online": 7,
    "convention_pop_up": 3,
}

# Minimum guarantee (MG) base amount by category, multiplied by the IP popularity tier and
# territory scope multipliers, then adding ±30% negotiation noise. The MG is typically lower than
# the "expected" royalty and is not a punitive clause.
MG_BASE_BY_CATEGORY = {
    "toys_action_figures": 25_000,
    "apparel": 16_000,
    "collectible_trading_cards": 30_000,
    "home_goods_decor": 10_000,
    "stationery_office": 6_500,
    "accessories_bags": 15_000,
}
MG_TIER_MULTIPLIER = {"breakout": 1.6, "mainstream": 1.0, "niche": 0.5}
MG_TERRITORY_MULTIPLIER = {"US": 0.65, "CANADA": 0.25, "US_CANADA": 1.0}

# Contract term options (in months) and their weights; early termination probability (a small,
# independent probability unrelated to compliance, kept simple).
CONTRACT_TERM_MONTHS_WEIGHTS = {12: 15, 18: 25, 24: 35, 36: 25}
CONTRACT_EARLY_TERMINATION_PROB = 0.04


def week_floor(d: date) -> date:
    """Round any date down to the Monday of its ISO week."""
    return d - timedelta(days=d.weekday())


def risk_tier_for_score(score: float) -> str:
    """Classify a licensee into the clean / risk cohort based on a compliance_score threshold."""
    return "risk" if score < 66 else "clean"


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class ProductCategory(Base):
    """Merchandise category lookup table, including the category benchmark royalty rate."""

    __tablename__ = "product_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    benchmark_royalty_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class RetailChannel(Base):
    """Retail channel lookup table (big box chains / specialty retail / e-commerce / DTC online / convention pop-up)."""

    __tablename__ = "retail_channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)


class AnimeIp(Base):
    """Licensed anime IP. Each IP is linked to a streaming premiere platform and a popularity tier."""

    __tablename__ = "anime_ip"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    genre: Mapped[str] = mapped_column(String(30), nullable=False)
    target_demographic: Mapped[str] = mapped_column(String(20), nullable=False)
    home_streaming_platform: Mapped[str] = mapped_column(String(100), nullable=False)
    season_count: Mapped[int] = mapped_column(Integer, nullable=False)
    debut_year: Mapped[int] = mapped_column(Integer, nullable=False)
    popularity_tier: Mapped[str] = mapped_column(String(20), nullable=False)


class Licensee(Base):
    """Licensee (North American merchandise manufacturer/distributor)."""

    __tablename__ = "licensee"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    hq_city: Mapped[str] = mapped_column(String(100), nullable=False)
    hq_state: Mapped[str] = mapped_column(String(2), nullable=False)
    founded_year: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_category_id: Mapped[int] = mapped_column(ForeignKey("product_category.id"), nullable=False)
    compliance_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(10), nullable=False)


class AccountManager(Base):
    """Ember & Ash internal licensing manager, responsible for licensee relationships and contract portfolio."""

    __tablename__ = "account_manager"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    region_focus: Mapped[str] = mapped_column(String(50), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)


class LicenseAgreement(Base):
    """A licensing agreement: the licensing terms for one IP x one licensee x one category."""

    __tablename__ = "license_agreement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agreement_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    anime_ip_id: Mapped[int] = mapped_column(ForeignKey("anime_ip.id"), nullable=False)
    licensee_id: Mapped[int] = mapped_column(ForeignKey("licensee.id"), nullable=False)
    product_category_id: Mapped[int] = mapped_column(ForeignKey("product_category.id"), nullable=False)
    account_manager_id: Mapped[int] = mapped_column(ForeignKey("account_manager.id"), nullable=False)
    territory: Mapped[str] = mapped_column(String(12), nullable=False)
    royalty_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    minimum_guarantee_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    signed_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_status: Mapped[str] = mapped_column(String(20), nullable=False)


class LicenseAgreementChannel(Base):
    """Contract-authorized-channel bridge table (M:N): a contract can authorize 1-3 retail channels."""

    __tablename__ = "license_agreement_channel"
    __table_args__ = (
        UniqueConstraint("license_agreement_id", "retail_channel_id", name="uq_agreement_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_agreement_id: Mapped[int] = mapped_column(
        ForeignKey("license_agreement.id", ondelete="CASCADE"), nullable=False
    )
    retail_channel_id: Mapped[int] = mapped_column(ForeignKey("retail_channel.id"), nullable=False)


class ProductSku(Base):
    """Merchandise SKU, belonging to a single licensing agreement."""

    __tablename__ = "product_sku"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    license_agreement_id: Mapped[int] = mapped_column(
        ForeignKey("license_agreement.id", ondelete="CASCADE"), nullable=False
    )
    sku_name: Mapped[str] = mapped_column(String(200), nullable=False)
    msrp_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    wholesale_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    launch_date: Mapped[date] = mapped_column(Date, nullable=False)
    discontinued_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class StreamingPopularityIndex(Base):
    """Weekly streaming popularity index for an anime IP (external reference data)."""

    __tablename__ = "streaming_popularity_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_ip_id: Mapped[int] = mapped_column(ForeignKey("anime_ip.id"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    popularity_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_season_premiere_week: Mapped[bool] = mapped_column(Boolean, default=False)


class PosSellThrough(Base):
    """Weekly retail-shelf sell-through fact table (POS: point of sale)."""

    __tablename__ = "pos_sell_through"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_sku_id: Mapped[int] = mapped_column(ForeignKey("product_sku.id", ondelete="CASCADE"), nullable=False)
    retail_channel_id: Mapped[int] = mapped_column(ForeignKey("retail_channel.id"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    net_wholesale_revenue_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    ending_inventory_units: Mapped[int] = mapped_column(Integer, nullable=False)


class RoyaltyReport(Base):
    """Royalty transactions self-reported by the licensee, in installments over the contract period."""

    __tablename__ = "royalty_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_agreement_id: Mapped[int] = mapped_column(
        ForeignKey("license_agreement.id", ondelete="CASCADE"), nullable=False
    )
    report_period_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reported_net_sales_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reported_royalty_due_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    report_submitted_date: Mapped[date] = mapped_column(Date, nullable=False)


class RoyaltyAuditFinding(Base):
    """Royalty audit result: comparison of self-reported royalty against the POS-derived royalty."""

    __tablename__ = "royalty_audit_finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    royalty_report_id: Mapped[int] = mapped_column(
        ForeignKey("royalty_report.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pos_derived_net_sales_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pos_derived_royalty_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    variance_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    variance_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    audit_status: Mapped[str] = mapped_column(String(30), nullable=False)


# ============================================================================
# Generator functions (in topological order)
# ============================================================================

def gen_product_categories() -> pl.DataFrame:
    """Generate the merchandise category lookup table."""
    return pl.DataFrame(
        PRODUCT_CATEGORIES,
        schema=["id", "category_code", "category_name", "benchmark_royalty_rate_pct"],
        orient="row",
    )


def gen_retail_channels() -> pl.DataFrame:
    """Generate the retail channel lookup table."""
    channels = [
        (1, "big_box_retail", "Big Box Retail Chains", "offline"),
        (2, "specialty_retail", "Specialty Retail Stores", "offline"),
        (3, "ecommerce_marketplace", "E-commerce Marketplace", "online"),
        (4, "direct_to_consumer_online", "Direct-to-Consumer Online Store", "online"),
        (5, "convention_pop_up", "Convention & Pop-up Retail", "offline"),
    ]
    return pl.DataFrame(channels, schema=["id", "channel_code", "channel_name", "channel_type"], orient="row")


def gen_anime_ips() -> pl.DataFrame:
    """Generate the licensed anime IP dimension table.

    popularity_tier is assigned directly from the target counts in POPULARITY_TIER_WEIGHTS
    (rather than by probabilistic sampling), guaranteeing the tier composition is exactly
    deterministic across runs, so precise counts can be referenced in the documentation.
    """
    titles = [
        "Starlit Ronin", "Ashfall Academy", "Nebula Drift", "Crimson Tide Guardians",
        "Moonlit Alchemist", "Iron Bloom", "Voidwalker Chronicles", "Sakura Static",
        "Ember Knights: Genesis", "Paper Lantern Detectives", "Skybound Mariners", "Glasswing",
        "Thunder Idol Rangers", "The Last Cartographer", "Wildfire Dorm", "Neon Shrine",
        "Frostbyte Legion", "Whispering Gears", "Solstice High", "Rustlight",
        "Hollow Meridian", "Petalfall", "Ironclad Melodies", "Driftwood Samurai",
    ]
    genres = [
        "shonen_action", "isekai_fantasy", "mecha", "sports",
        "slice_of_life", "romance_comedy", "horror_thriller", "comedy",
    ]
    demographics = ["kids", "teen", "young_adult", "mature"]
    # Fictional streaming platforms. Vantage Anime Networks shares a shared-universe setting with
    # another fictional North American anime dataset.
    platforms = ["Vantage Anime Networks", "Kaikan Stream", "Northlight Anime+", "Torii Play"]

    tier_pool: list[str] = []
    for tier, count in POPULARITY_TIER_WEIGHTS.items():
        tier_pool.extend([tier] * count)
    random.shuffle(tier_pool)

    records = []
    for i, title in enumerate(titles, start=1):
        tier = tier_pool[i - 1]
        season_count = random.randint(4, 6) if tier == "breakout" else random.randint(1, 4)
        debut_year = random.randint(2017, 2025)
        records.append({
            "id": i,
            "title": title,
            "genre": random.choice(genres),
            "target_demographic": random.choice(demographics),
            "home_streaming_platform": random.choice(platforms),
            "season_count": season_count,
            "debut_year": debut_year,
            "popularity_tier": tier,
        })
    return pl.DataFrame(records)


def gen_licensees(category_ids: list[int]) -> pl.DataFrame:
    """Generate the licensee dimension table.

    compliance_score is assigned to the clean / risk cohorts according to the target proportion
    in LICENSEE_RISK_SHARE (deterministic assignment, rather than probabilistic sampling); this
    risk_tier label is the shared driving signal for trap 2 (royalty underreporting) and trap 4
    (unauthorized channel leakage).
    """
    suffixes = ["Toys", "Collectibles", "Apparel Co.", "Home Goods", "Merch Studio", "Brands"]
    hq_cities = [
        ("Los Angeles", "CA"), ("New York", "NY"), ("Chicago", "IL"), ("Toronto", "ON"),
        ("Vancouver", "BC"), ("Dallas", "TX"), ("Atlanta", "GA"), ("Seattle", "WA"),
        ("Montreal", "QC"), ("Denver", "CO"), ("Portland", "OR"), ("Minneapolis", "MN"),
    ]

    n = 32
    n_risk = round(n * LICENSEE_RISK_SHARE)
    risk_flags = [True] * n_risk + [False] * (n - n_risk)
    random.shuffle(risk_flags)

    records = []
    for i in range(1, n + 1):
        is_risk = risk_flags[i - 1]
        risk_tier = "risk" if is_risk else "clean"
        lo, hi = LICENSEE_COMPLIANCE_RANGE[risk_tier]
        compliance_score = round(random.uniform(lo, hi), 2)
        city, state = random.choice(hq_cities)
        records.append({
            "id": i,
            "company_name": f"{fake.unique.company()} {random.choice(suffixes)}",
            "hq_city": city,
            "hq_state": state,
            "founded_year": random.randint(1985, 2019),
            "primary_category_id": random.choice(category_ids),
            "compliance_score": compliance_score,
            "risk_tier": risk_tier_for_score(compliance_score),
        })
    fake.unique.clear()
    return pl.DataFrame(records)


def gen_account_managers() -> pl.DataFrame:
    """Generate the Ember & Ash internal licensing manager team."""
    titles = ["Licensing Manager"] * 5 + ["Senior Licensing Manager"] * 2 + ["Director of Licensing"] * 1
    regions = ["West Coast", "East Coast", "Central", "Canada", "National"]

    records = []
    for i in range(1, 9):
        records.append({
            "id": i,
            "employee_id": f"AM{str(i).zfill(3)}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "title": titles[i - 1],
            "region_focus": random.choice(regions),
            "hire_date": fake.date_between(start_date="-8y", end_date="-6m"),
        })
    return pl.DataFrame(records)


def gen_license_agreements(
    anime_ips: pl.DataFrame,
    licensees: pl.DataFrame,
    categories: pl.DataFrame,
    manager_ids: list[int],
) -> pl.DataFrame:
    """Generate licensing agreements.

    For each IP, a set of (licensee, category) combinations is drawn according to its popularity
    tier, avoiding fully duplicate (licensee, category) combinations under the same IP.
    minimum_guarantee_usd is weighted by category base amount x IP popularity tier x territory
    scope — this is the benchmark against which trap 5 (MG attainment) is compared.
    """
    licensee_ids = licensees["id"].to_list()
    category_code_by_id = dict(zip(categories["id"].to_list(), categories["category_code"].to_list()))
    benchmark_rate_by_category = dict(
        zip(categories["id"].to_list(), categories["benchmark_royalty_rate_pct"].to_list())
    )

    territory_weights = {"US": 30, "CANADA": 10, "US_CANADA": 60}

    records = []
    agreement_id = 1
    for ip_row in anime_ips.iter_rows(named=True):
        tier = ip_row["popularity_tier"]
        lo, hi = AGREEMENT_COUNT_RANGE_BY_TIER[tier]
        n_agreements = random.randint(lo, hi)

        used_combos: set[tuple[int, int]] = set()
        attempts = 0
        combos_made = 0
        while combos_made < n_agreements and attempts < n_agreements * 10:
            attempts += 1
            licensee_id = random.choice(licensee_ids)
            category_id = random.choice(categories["id"].to_list())
            combo = (licensee_id, category_id)
            if combo in used_combos:
                continue
            used_combos.add(combo)
            combos_made += 1

            category_code = category_code_by_id[category_id]
            benchmark_rate = float(benchmark_rate_by_category[category_id])

            signed_date = fake.date_between(start_date=AGREEMENT_SIGN_START, end_date=AGREEMENT_SIGN_END)
            contract_start_date = signed_date + timedelta(days=random.randint(30, 75))
            term_months = random.choices(
                list(CONTRACT_TERM_MONTHS_WEIGHTS.keys()),
                weights=list(CONTRACT_TERM_MONTHS_WEIGHTS.values()),
                k=1,
            )[0]
            contract_end_date = contract_start_date + timedelta(days=term_months * 30)
            if random.random() < CONTRACT_EARLY_TERMINATION_PROB:
                contract_end_date = contract_start_date + timedelta(days=random.randint(90, term_months * 20))

            if contract_end_date <= REFERENCE_DATE:
                contract_status = "terminated" if contract_end_date < contract_start_date + timedelta(
                    days=term_months * 30
                ) else "expired"
            else:
                contract_status = "active"

            territory = random.choices(
                list(territory_weights.keys()), weights=list(territory_weights.values()), k=1
            )[0]

            royalty_rate_pct = round(max(4.0, benchmark_rate + random.uniform(-1.5, 1.5)), 2)

            mg_base = MG_BASE_BY_CATEGORY[category_code]
            mg = (
                mg_base
                * MG_TIER_MULTIPLIER[tier]
                * MG_TERRITORY_MULTIPLIER[territory]
                * random.uniform(0.7, 1.3)
            )

            records.append({
                "id": agreement_id,
                "agreement_number": f"LA-{str(agreement_id).zfill(5)}",
                "anime_ip_id": ip_row["id"],
                "licensee_id": licensee_id,
                "product_category_id": category_id,
                "account_manager_id": random.choice(manager_ids),
                "territory": territory,
                "royalty_rate_pct": royalty_rate_pct,
                "minimum_guarantee_usd": round(mg, 2),
                "signed_date": signed_date,
                "contract_start_date": contract_start_date,
                "contract_end_date": contract_end_date,
                "contract_status": contract_status,
            })
            agreement_id += 1

    return pl.DataFrame(records)


def gen_license_agreement_channels(agreements: pl.DataFrame, channels: pl.DataFrame) -> pl.DataFrame:
    """Generate the contract-authorized-channel bridge table (each contract authorizes 1-3 channels)."""
    channel_ids_by_code = dict(zip(channels["channel_code"].to_list(), channels["id"].to_list()))
    channel_codes = list(CHANNEL_SELECTION_WEIGHTS.keys())
    channel_weights = list(CHANNEL_SELECTION_WEIGHTS.values())

    records = []
    row_id = 1
    for agreement_id in agreements["id"].to_list():
        n_channels = random.choices(
            list(CHANNEL_COUNT_WEIGHTS.keys()), weights=list(CHANNEL_COUNT_WEIGHTS.values()), k=1
        )[0]
        chosen_codes: set[str] = set()
        attempts = 0
        while len(chosen_codes) < n_channels and attempts < n_channels * 10:
            attempts += 1
            chosen_codes.add(random.choices(channel_codes, weights=channel_weights, k=1)[0])
        # Write rows in the fixed channel_codes order, rather than iterating the set directly —
        # the iteration order of a set[str] is affected by Python's hash randomization
        # (PYTHONHASHSEED, not pinned by default in this environment), which would cause the
        # authorized channels of the same contract to be written in a different id order on each
        # run, breaking this generator's promise of "consistent results across runs." The
        # random.choices sampling logic here is completely unchanged (the RNG stream is
        # unaffected); only the row-write order is pinned to be deterministic, by filtering
        # chosen_codes in the fixed order.
        for code in channel_codes:
            if code not in chosen_codes:
                continue
            records.append({
                "id": row_id,
                "license_agreement_id": agreement_id,
                "retail_channel_id": channel_ids_by_code[code],
            })
            row_id += 1

    return pl.DataFrame(records)


def gen_product_skus(agreements: pl.DataFrame, categories: pl.DataFrame) -> pl.DataFrame:
    """Generate merchandise SKUs. Launch date follows the contract start date, plus a product-development lag."""
    category_code_by_id = dict(zip(categories["id"].to_list(), categories["category_code"].to_list()))
    sku_name_nouns = {
        "toys_action_figures": ["Action Figure", "Figure Set", "Deluxe Figure", "Poseable Figure"],
        "apparel": ["Graphic Tee", "Hoodie", "Bomber Jacket", "Cap"],
        "collectible_trading_cards": ["Booster Pack", "Starter Deck", "Foil Card Set", "Collector Box"],
        "home_goods_decor": ["Throw Blanket", "Mug", "Wall Scroll", "Desk Lamp"],
        "stationery_office": ["Notebook", "Pencil Case", "Sticker Sheet", "Planner"],
        "accessories_bags": ["Backpack", "Keychain", "Tote Bag", "Wallet"],
    }

    records = []
    sku_id = 1
    for agreement_row in agreements.iter_rows(named=True):
        category_code = category_code_by_id[agreement_row["product_category_id"]]
        n_lo, n_hi = SKU_COUNT_RANGE_BY_CATEGORY[category_code]
        msrp_lo, msrp_hi = MSRP_RANGE_BY_CATEGORY[category_code]
        n_skus = random.randint(n_lo, n_hi)

        contract_start = agreement_row["contract_start_date"]

        for _ in range(n_skus):
            launch_date = contract_start + timedelta(days=random.randint(60, 120))
            msrp = round(random.uniform(msrp_lo, msrp_hi), 2)
            # Wholesale-to-retail "keystone" markup convention: wholesale price is roughly 50% of
            # MSRP, with a ±5% swing.
            wholesale_price = round(msrp * random.uniform(0.45, 0.55), 2)

            discontinued_date = None
            if random.random() < SKU_DISCONTINUE_PROB:
                d_lo, d_hi = SKU_DISCONTINUE_DAYS_RANGE
                discontinued_date = launch_date + timedelta(days=random.randint(d_lo, d_hi))

            noun = random.choice(sku_name_nouns[category_code])
            records.append({
                "id": sku_id,
                "sku_code": f"SKU-{str(sku_id).zfill(6)}",
                "license_agreement_id": agreement_row["id"],
                "sku_name": f"{noun} Series {random.randint(1, 5)}",
                "msrp_usd": msrp,
                "wholesale_price_usd": wholesale_price,
                "launch_date": launch_date,
                "discontinued_date": discontinued_date,
            })
            sku_id += 1

    return pl.DataFrame(records)


def gen_streaming_popularity_index(anime_ips: pl.DataFrame) -> tuple[pl.DataFrame, dict[int, list[tuple[date, date]]]]:
    """Generate the weekly streaming popularity index, and return each IP's "sell-through bump window" (used by trap 3).

    For each premiere event, generate a bump window that starts "premiere week + a random 6-10
    week lag" and lasts 3 weeks; gen_pos_sell_through boosts sales for the corresponding IP's SKUs
    within these windows.
    """
    records = []
    row_id = 1
    bump_windows: dict[int, list[tuple[date, date]]] = {}

    n_weeks = POPULARITY_HORIZON_WEEKS + 1
    all_weeks = [POPULARITY_HORIZON_START + timedelta(weeks=w) for w in range(n_weeks)]

    for ip_row in anime_ips.iter_rows(named=True):
        ip_id = ip_row["id"]
        tier = ip_row["popularity_tier"]
        baseline_lo, baseline_hi = POPULARITY_BASELINE_RANGE_BY_TIER[tier]
        n_premieres = PREMIERE_COUNT_BY_TIER[tier]

        # A premiere week must leave enough follow-on window (lag + bump duration) to fall
        # within the tracking period.
        latest_premiere_week_idx = n_weeks - 1 - (POPULARITY_TO_SALES_LAG_WEEKS[1] + LAG_BUMP_DURATION_WEEKS + 2)
        earliest_premiere_week_idx = 8

        premiere_indices: list[int] = []
        tries = 0
        while len(premiere_indices) < n_premieres and tries < 50:
            tries += 1
            idx = random.randint(earliest_premiere_week_idx, max(earliest_premiere_week_idx, latest_premiere_week_idx))
            if all(abs(idx - existing) >= 20 for existing in premiere_indices):
                premiere_indices.append(idx)

        premiere_index_set = set(premiere_indices)
        bump_windows[ip_id] = []

        # Generate a popularity score week by week; the premiere week and the following 3 weeks
        # layer on top of the baseline according to PREMIERE_DECAY_FACTORS.
        decay_remaining: dict[int, int] = {}
        for week_idx, week_start in enumerate(all_weeks):
            baseline = random.uniform(baseline_lo, baseline_hi)
            is_premiere = week_idx in premiere_index_set

            spike_component = 0.0
            for start_idx in list(decay_remaining.keys()):
                steps_since = week_idx - start_idx
                if 0 <= steps_since < len(PREMIERE_DECAY_FACTORS):
                    spike_lo, spike_hi = PREMIERE_SPIKE_RANGE
                    spike_component = max(
                        spike_component,
                        random.uniform(spike_lo, spike_hi) * PREMIERE_DECAY_FACTORS[steps_since],
                    )
                else:
                    decay_remaining.pop(start_idx, None)

            if is_premiere:
                decay_remaining[week_idx] = 1
                spike_lo, spike_hi = PREMIERE_SPIKE_RANGE
                spike_component = max(spike_component, random.uniform(spike_lo, spike_hi))

            score = max(5.0, min(100.0, max(baseline, spike_component)))

            records.append({
                "id": row_id,
                "anime_ip_id": ip_id,
                "week_start_date": week_start,
                "popularity_score": round(score, 2),
                "is_season_premiere_week": is_premiere,
            })
            row_id += 1

            if is_premiere:
                lag_weeks = random.randint(*POPULARITY_TO_SALES_LAG_WEEKS)
                bump_start = week_start + timedelta(weeks=lag_weeks)
                bump_end = bump_start + timedelta(weeks=LAG_BUMP_DURATION_WEEKS)
                bump_windows[ip_id].append((bump_start, bump_end))

    return pl.DataFrame(records), bump_windows


def gen_pos_sell_through(
    skus: pl.DataFrame,
    agreements: pl.DataFrame,
    agreement_channels: pl.DataFrame,
    licensees: pl.DataFrame,
    categories: pl.DataFrame,
    anime_ips: pl.DataFrame,
    bump_windows: dict[int, list[tuple[date, date]]],
) -> pl.DataFrame:
    """Generate the weekly retail-shelf sell-through fact table.

    This is the largest fact table in the dataset, and also the direct source of trap 3
    (popularity-to-sell-through lag) and trap 4 (unauthorized channel leakage): regular
    sell-through within authorized channels is layered with a "popularity bump window"
    multiplier; licensees in the "risk" cohort also have a small probability of generating
    additional sales in an unauthorized channel (usually ecommerce_marketplace).
    """
    agreement_by_id = {row["id"]: row for row in agreements.iter_rows(named=True)}
    category_code_by_id = dict(zip(categories["id"].to_list(), categories["category_code"].to_list()))
    tier_by_ip_id = dict(zip(anime_ips["id"].to_list(), anime_ips["popularity_tier"].to_list()))
    risk_tier_by_licensee_id = dict(zip(licensees["id"].to_list(), licensees["risk_tier"].to_list()))

    authorized_channels_by_agreement: dict[int, list[int]] = {}
    for row in agreement_channels.iter_rows(named=True):
        authorized_channels_by_agreement.setdefault(row["license_agreement_id"], []).append(row["retail_channel_id"])

    ecommerce_channel_id = 3
    dtc_channel_id = 4

    records = []
    row_id = 1

    for sku_row in skus.iter_rows(named=True):
        agreement = agreement_by_id[sku_row["license_agreement_id"]]
        category_code = category_code_by_id[agreement["product_category_id"]]
        ip_id = agreement["anime_ip_id"]
        tier = tier_by_ip_id[ip_id]
        risk_tier = risk_tier_by_licensee_id[agreement["licensee_id"]]

        base_units = CATEGORY_BASE_WEEKLY_UNITS[category_code]
        tier_multiplier = POPULARITY_TIER_SELLTHROUGH_MULTIPLIER[tier]

        launch_date = sku_row["launch_date"]
        end_date = sku_row["discontinued_date"] or agreement["contract_end_date"]
        end_date = min(end_date, REFERENCE_DATE)
        if launch_date > end_date:
            continue

        first_week = week_floor(launch_date)
        last_week = week_floor(end_date)
        n_weeks = max(0, (last_week - first_week).days // 7 + 1)
        if n_weeks <= 0:
            continue

        authorized = authorized_channels_by_agreement.get(agreement["id"], [])
        if not authorized:
            continue

        leak_prob = UNAUTHORIZED_CHANNEL_LEAK_PROB[risk_tier]
        leak_channel_id = ecommerce_channel_id if ecommerce_channel_id not in authorized else dtc_channel_id

        this_ip_bumps = bump_windows.get(ip_id, [])

        ending_inventory = random.randint(200, 800)

        for w in range(n_weeks):
            week_start = first_week + timedelta(weeks=w)
            weeks_since_launch = w

            ramp = min(1.0, weeks_since_launch / LIFECYCLE_RAMP_WEEKS) if weeks_since_launch < LIFECYCLE_RAMP_WEEKS else 1.0
            if weeks_since_launch <= LIFECYCLE_DECAY_START_WEEK:
                decay = 1.0
            else:
                decay = max(
                    LIFECYCLE_DECAY_FLOOR,
                    1.0 - (weeks_since_launch - LIFECYCLE_DECAY_START_WEEK) * LIFECYCLE_DECAY_PER_WEEK,
                )

            bump_multiplier = 1.0
            for bump_start, bump_end in this_ip_bumps:
                if bump_start <= week_start < bump_end:
                    bump_multiplier = random.uniform(*LAG_BUMP_MULTIPLIER_RANGE)
                    break

            mean_units_per_channel = base_units * tier_multiplier * ramp * decay * bump_multiplier

            active_channels = list(authorized)
            if random.random() < leak_prob:
                if leak_channel_id not in active_channels:
                    active_channels.append(leak_channel_id)

            for channel_id in active_channels:
                units = max(0, round(random.gauss(mean_units_per_channel, mean_units_per_channel * 0.35)))
                revenue = round(units * float(sku_row["wholesale_price_usd"]), 2)
                ending_inventory = max(0, ending_inventory - units + random.randint(0, 15))

                records.append({
                    "id": row_id,
                    "product_sku_id": sku_row["id"],
                    "retail_channel_id": channel_id,
                    "week_start_date": week_start,
                    "units_sold": units,
                    "net_wholesale_revenue_usd": revenue,
                    "ending_inventory_units": ending_inventory,
                })
                row_id += 1

    return pl.DataFrame(records)


def gen_royalty_reports(
    agreements: pl.DataFrame,
    skus: pl.DataFrame,
    pos: pl.DataFrame,
    licensees: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Generate the licensee's quarterly self-reported royalties, along with the corresponding audit results.

    The royalty settlement cycle follows each contract's own "contract quarter" (a 91-day period
    starting from contract_start_date), rather than the calendar quarter — this is a common
    convention in consumer product licensing agreements. The POS-derived net sales figure is the
    true sum of pos_sell_through for the same contract over the same time window (across all
    channels); reported_net_sales_usd is understated according to the UNDERREPORT_RATE_RANGE for
    the corresponding risk_tier, producing the auditable bias in trap 2.
    """
    risk_tier_by_licensee_id = dict(zip(licensees["id"].to_list(), licensees["risk_tier"].to_list()))
    sku_ids_by_agreement: dict[int, list[int]] = {}
    for row in skus.iter_rows(named=True):
        sku_ids_by_agreement.setdefault(row["license_agreement_id"], []).append(row["id"])

    pos_pd = pos.select(["product_sku_id", "week_start_date", "net_wholesale_revenue_usd"])
    revenue_by_sku_week: dict[tuple[int, date], float] = {}
    for row in pos_pd.iter_rows(named=True):
        key = (row["product_sku_id"], row["week_start_date"])
        revenue_by_sku_week[key] = revenue_by_sku_week.get(key, 0.0) + row["net_wholesale_revenue_usd"]

    # Pre-sort the list of weeks grouped by (sku_id), to speed up range summation.
    weeks_by_sku: dict[int, list[date]] = {}
    for (sku_id, wk) in revenue_by_sku_week.keys():
        weeks_by_sku.setdefault(sku_id, []).append(wk)
    for sku_id in weeks_by_sku:
        weeks_by_sku[sku_id].sort()

    report_records = []
    audit_records = []
    report_id = 1
    audit_id = 1

    for agreement in agreements.iter_rows(named=True):
        agreement_id = agreement["id"]
        licensee_id = agreement["licensee_id"]
        risk_tier = risk_tier_by_licensee_id[licensee_id]
        royalty_rate = float(agreement["royalty_rate_pct"]) / 100.0
        contract_start = agreement["contract_start_date"]
        sku_ids = sku_ids_by_agreement.get(agreement_id, [])

        period_start = contract_start
        while True:
            period_end = period_start + timedelta(days=91)
            report_submitted = period_end + timedelta(days=random.randint(15, 45))
            if report_submitted > REFERENCE_DATE:
                break

            pos_derived_net_sales = 0.0
            for sku_id in sku_ids:
                for wk in weeks_by_sku.get(sku_id, []):
                    if period_start <= wk < period_end:
                        pos_derived_net_sales += revenue_by_sku_week[(sku_id, wk)]

            if pos_derived_net_sales <= 0:
                period_start = period_end
                continue

            lo, hi = UNDERREPORT_RATE_RANGE[risk_tier]
            underreport_rate = random.uniform(lo, hi)
            reported_net_sales = round(pos_derived_net_sales * (1 - underreport_rate), 2)
            reported_royalty_due = round(reported_net_sales * royalty_rate, 2)

            report_records.append({
                "id": report_id,
                "license_agreement_id": agreement_id,
                "report_period_start_date": period_start,
                "report_period_end_date": period_end,
                "reported_net_sales_usd": reported_net_sales,
                "reported_royalty_due_usd": reported_royalty_due,
                "report_submitted_date": report_submitted,
            })

            pos_derived_royalty = round(pos_derived_net_sales * royalty_rate, 2)
            variance_usd = round(pos_derived_royalty - reported_royalty_due, 2)
            variance_pct = round((variance_usd / pos_derived_royalty) * 100, 2) if pos_derived_royalty else 0.0

            if variance_pct >= AUDIT_CONFIRMED_THRESHOLD_PCT:
                audit_status = "confirmed_underreport"
            elif variance_pct >= AUDIT_FLAGGED_THRESHOLD_PCT:
                audit_status = "flagged_for_review"
            else:
                audit_status = "within_tolerance"

            audit_records.append({
                "id": audit_id,
                "royalty_report_id": report_id,
                "pos_derived_net_sales_usd": round(pos_derived_net_sales, 2),
                "pos_derived_royalty_usd": pos_derived_royalty,
                "variance_usd": variance_usd,
                "variance_pct": variance_pct,
                "audit_status": audit_status,
            })

            report_id += 1
            audit_id += 1
            period_start = period_end

    return pl.DataFrame(report_records), pl.DataFrame(audit_records)


# ============================================================================
# Main pipeline (idempotent)
# ============================================================================

def generate_all_tsv() -> None:
    """Generate all TSV files. Idempotent: first deletes any existing TSV files under data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating product categories...")
    df_categories = gen_product_categories()
    df_categories.write_csv(DATA_DIR / "01_product_category.tsv", separator="\t")

    print("Generating retail channels...")
    df_channels = gen_retail_channels()
    df_channels.write_csv(DATA_DIR / "02_retail_channel.tsv", separator="\t")

    print("Generating anime IPs...")
    df_anime_ips = gen_anime_ips()
    df_anime_ips.write_csv(DATA_DIR / "03_anime_ip.tsv", separator="\t")

    print("Generating licensees...")
    df_licensees = gen_licensees(category_ids=df_categories["id"].to_list())
    df_licensees.write_csv(DATA_DIR / "04_licensee.tsv", separator="\t")

    print("Generating account managers...")
    df_managers = gen_account_managers()
    df_managers.write_csv(DATA_DIR / "05_account_manager.tsv", separator="\t")

    print("Generating license agreements...")
    df_agreements = gen_license_agreements(
        anime_ips=df_anime_ips,
        licensees=df_licensees,
        categories=df_categories,
        manager_ids=df_managers["id"].to_list(),
    )
    df_agreements.write_csv(DATA_DIR / "06_license_agreement.tsv", separator="\t")

    print("Generating license agreement channel authorizations...")
    df_agreement_channels = gen_license_agreement_channels(df_agreements, df_channels)
    df_agreement_channels.write_csv(DATA_DIR / "07_license_agreement_channel.tsv", separator="\t")

    print("Generating product SKUs...")
    df_skus = gen_product_skus(df_agreements, df_categories)
    df_skus.write_csv(DATA_DIR / "08_product_sku.tsv", separator="\t")

    print("Generating streaming popularity index...")
    df_popularity, bump_windows = gen_streaming_popularity_index(df_anime_ips)
    df_popularity.write_csv(DATA_DIR / "09_streaming_popularity_index.tsv", separator="\t")

    print("Generating POS sell-through (largest table, may take a moment)...")
    df_pos = gen_pos_sell_through(
        skus=df_skus,
        agreements=df_agreements,
        agreement_channels=df_agreement_channels,
        licensees=df_licensees,
        categories=df_categories,
        anime_ips=df_anime_ips,
        bump_windows=bump_windows,
    )
    df_pos.write_csv(DATA_DIR / "10_pos_sell_through.tsv", separator="\t")

    print("Generating royalty reports and audit findings...")
    df_reports, df_audits = gen_royalty_reports(df_agreements, df_skus, df_pos, df_licensees)
    df_reports.write_csv(DATA_DIR / "11_royalty_report.tsv", separator="\t")
    df_audits.write_csv(DATA_DIR / "12_royalty_audit_finding.tsv", separator="\t")

    total = (
        len(df_categories) + len(df_channels) + len(df_anime_ips) + len(df_licensees)
        + len(df_managers) + len(df_agreements) + len(df_agreement_channels) + len(df_skus)
        + len(df_popularity) + len(df_pos) + len(df_reports) + len(df_audits)
    )
    print(f"\nGenerated all TSV files in {DATA_DIR}")
    print(f"Total rows: {total}")


def create_sqlite_database() -> None:
    """Build the SQLite database from the TSV files. Idempotent: first deletes any existing database file.

    Uses the Core API bulk-load pattern: a topologically ordered list of (TSV file name, Table)
    pairs, a single for loop, and a single engine.begin() transaction.
    """
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order: list[tuple[str, Table]] = [
        ("01_product_category", ProductCategory.__table__),
        ("02_retail_channel", RetailChannel.__table__),
        ("03_anime_ip", AnimeIp.__table__),
        ("04_licensee", Licensee.__table__),
        ("05_account_manager", AccountManager.__table__),
        ("06_license_agreement", LicenseAgreement.__table__),
        ("07_license_agreement_channel", LicenseAgreementChannel.__table__),
        ("08_product_sku", ProductSku.__table__),
        ("09_streaming_popularity_index", StreamingPopularityIndex.__table__),
        ("10_pos_sell_through", PosSellThrough.__table__),
        ("11_royalty_report", RoyaltyReport.__table__),
        ("12_royalty_audit_finding", RoyaltyAuditFinding.__table__),
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
            print(f"Loaded {len(rows)} rows into {table.name}")

    print(f"\nCreated SQLite database at {DATABASE_PATH}")


def main() -> None:
    """Main entry point."""
    print("=" * 80)
    print("Ember & Ash Licensing Group - Anime IP Licensing & Retail Sell-Through Generator")
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
