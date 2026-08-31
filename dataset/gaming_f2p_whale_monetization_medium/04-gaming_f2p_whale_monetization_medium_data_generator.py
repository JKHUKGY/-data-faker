"""
Gaming F2P Mobile IAP & Whale Retention Health Fake Data Generator
Complexity: Medium

Business Context:
Pinnacle Peak Games is a fictional mobile game studio headquartered in Seattle,
whose flagship product is the F2P collection/progression RPG mobile game
*Ember Realms Saga*. This dataset samples the economic behavior of 5,000
players over roughly the past 18 months (installs, in-app purchases, gacha
pulls, Live-Ops event participation, refunds/chargebacks, support tickets),
supporting analysis of the following 5 business traps:

1. Whale-dependency trap: the top 1% of players (50 people) contribute about
   65% of IAP revenue, dolphins (3%) about 28%, and minnows (6%) about 6% --
   revenue is highly concentrated among a tiny group of players.
2. Probability-pool disclosure gap trap: among the 5 limited (limited_rateup)
   gacha pools, 3 have actual legendary drop rates significantly lower than
   the officially disclosed probability, while the other 2 serve as an
   "honest control group" matching the disclosed rate; all standard pools
   are honest. Looking only at the overall mean of "limited vs. standard"
   would be diluted by the 2 honest limited pools -- you must compare pool
   by pool to catch the problem.
3. Live-Ops event false-prosperity trap: high-frequency stacked events
   (interval < 7 days) temporarily boost participating players' IAP
   frequency and average spend in the short term, but this cohort's
   activity rate (any behavioral record left) over the following 30 days is
   significantly lower than for participants of normally paced events --
   a "borrowing from tomorrow" false prosperity pattern.
4. Top-up-reseller / discount-channel arbitrage trap: transactions from
   unauthorized third-party resellers (third_party_agent, is_authorized=
   false) systematically pay a lower actual price than the official list
   price, and their refund/chargeback rate is far above the official
   channel baseline; meanwhile some region-exclusive discount codes
   (discount_code.leaked_beyond_scope=true) are redeemed in large numbers
   outside their target region, indicating the discount code has leaked and
   is being arbitraged.
5. Refund fraud ring trap: a group of players shares the same
   device_fingerprint_hash (suspected sock-puppet accounts bulk-registered
   from the same device); this cohort's refund/chargeback incidence rate is
   far higher than ordinary players, and the pattern is highly concentrated
   (a short time window, a small number of fingerprints) -- an independent
   clue from trap 4's reseller issue, but both point toward fraud risk.

The traps above are injected through deliberately designed correlated
distributions. The corresponding SQL queries live in
03-gaming_f2p_whale_monetization_medium_sql_queries-cn.md, used to surface
these traps.
"""

from __future__ import annotations

import hashlib
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
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ----------------------------------------------------------------------------
# Configuration constants
# ----------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "gaming_f2p_whale_monetization_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date, so results are reproducible across runs and don't
# depend on the system's current time.
# Anywhere the SQL queries need "today", they use the same literal date.
REFERENCE_DATE = date(2026, 6, 30)
# The game's worldwide launch date. Player install_date is sampled starting
# from this day.
LAUNCH_DATE = date(2025, 1, 6)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ----------------------------------------------------------------------------
# Business Calibration Constants
# ----------------------------------------------------------------------------

# Player population size and payer segmentation. The numbers are the exact
# headcounts for this analysis sample (not probabilities), so that phrases
# like "top 1%" line up precisely in the sample. 90% of players never pay
# (typical for F2P mobile games); payers are further broken into
# minnow/dolphin/whale tiers, with whale exactly equal to the top 1% of the
# sample (50 people).
PLAYER_COUNT = 5000
SEGMENT_COUNTS = {
    "whale": 50,  # Top 1%. Core group for trap 1.
    "dolphin": 150,  # Top 4% (including whale, cumulative to 4%).
    "minnow": 300,  # Top 10% (cumulative, including the above).
    "non_payer": 4500,  # Bottom 90%, contributes 0 IAP revenue.
}

# Mean transaction count per payer segment (center of a Gaussian
# distribution). The actual average spend per transaction isn't set here
# directly -- it's determined by the product's base_price_usd (chosen via
# PRODUCT_WEIGHTS_BY_SEGMENT) times the region's price_index: whales
# clearly prefer large bundles, minnows prefer small starter packs. "More
# transactions" stacked with "higher average spend", once calibrated, makes
# whales contribute about 65% of revenue, dolphins about 28%, and minnows
# about 6% -- echoing the whale-dependency trap 1.
SEGMENT_TX_COUNT_MEAN = {
    "whale": 110,
    "dolphin": 50,
    "minnow": 14,
}

# Mean number of gacha pulls per payer segment. whale/dolphin/minnow pull
# using IAP-purchased shards, while non_payer pulls occasionally using free
# shards from daily login/event rewards, with a mean far lower than paying
# players.
SEGMENT_GACHA_PULL_MEAN = {
    "whale": 250,
    "dolphin": 80,
    "minnow": 25,
    "non_payer": 1.5,
}

# Base retention "lifespan" (days) per payer segment, i.e. the mean number
# of days from install to naturally stopping activity; sampled from an
# exponential distribution and then clamped to [7, reference-date window].
# The deeper a player pays, the longer their retention tends to last.
SEGMENT_TENURE_MEAN_DAYS = {
    "whale": 480,
    "dolphin": 300,
    "minnow": 150,
    "non_payer": 55,
}

# --- Trap 2: probability-pool disclosure gap ------------------------------
# Standard pools: all honest, actual drop rates match the disclosed rate
# (only tiny random noise).
# Limited (limited_rateup) pools: 3 of the 5 are "rigged", with actual
# legendary drop rates significantly below the disclosed rate; the other 2
# serve as an honest control group, close to the disclosed rate. Looking
# only at the "overall mean across limited pools" would dilute the signal
# with the 2 honest control pools -- you must compare pool by pool to catch
# the 3 truly problematic pools.
RIGGED_LIMITED_POOLS = {
    "Ember Queen Rate-Up Banner": {"disclosed": 3.0, "actual": 1.7},
    "Frostbound Knight Rate-Up Banner": {"disclosed": 3.0, "actual": 1.8},
    "Anniversary Celebration Banner": {"disclosed": 3.5, "actual": 2.0},
}
HONEST_LIMITED_POOLS = {
    "Shadowfang Assassin Rate-Up Banner": {"disclosed": 3.0, "actual": 2.9},
    "Golden Phoenix Rate-Up Banner": {"disclosed": 3.0, "actual": 3.1},
}

# --- Trap 3: Live-Ops event false prosperity -------------------------------
# Stacked event definition: gap from the previous event's end date < 7
# days. If a player participates in >= 2 stacked events, there is a
# STACKED_FATIGUE_CHURN_PROB chance they will prematurely "burn out" 15-25
# days after the last stacked event (all subsequent behavioral records get
# truncated), simulating the next-month retention collapse caused by event
# fatigue.
STACKED_EVENT_GAP_DAYS = 7
STACKED_FATIGUE_MIN_COUNT = 2
STACKED_FATIGUE_CHURN_PROB = 0.55
STACKED_FATIGUE_CUTOFF_MIN_DAYS = 15
STACKED_FATIGUE_CUTOFF_MAX_DAYS = 25
# Within a stacked event window, participating players' average IAP spend
# per transaction / frequency is temporarily multiplied, creating a
# short-term illusion of higher ARPPU.
STACKED_EVENT_SPEND_MULTIPLIER = 1.8

# --- Trap 4: top-up-reseller / discount-channel arbitrage ------------------
# The discount factor of unauthorized resellers' (is_authorized=false)
# actual paid price relative to the official list price, plus this
# cohort's refund/chargeback rate (far above the official channel baseline
# of 2%).
UNAUTHORIZED_AGENT_PRICE_FACTOR = 0.68
UNAUTHORIZED_AGENT_CHARGEBACK_RATE = 0.20
OFFICIAL_CHANNEL_CHARGEBACK_RATE = 0.02
AUTHORIZED_AGENT_CHARGEBACK_RATE = 0.04

# Rate at which a leaked discount code is redeemed outside its target
# region (a normal discount code's out-of-scope redemption rate should be
# < 10%).
LEAKED_CODE_OUT_OF_SCOPE_RATE = 0.75
NORMAL_CODE_OUT_OF_SCOPE_RATE = 0.06

# --- Trap 5: refund fraud ring (device fingerprint sock puppets) ----------
FRAUD_RING_COUNT = 10
FRAUD_RING_SIZE_MIN = 4
FRAUD_RING_SIZE_MAX = 5
FRAUD_RING_CHARGEBACK_RATE = 0.45  # Refund/chargeback incidence rate for the fraud ring's own accounts


class Base(DeclarativeBase):
    pass


# ----------------------------------------------------------------------------
# ORM models (topological order)
# ----------------------------------------------------------------------------


class ChannelPartner(Base):
    """IAP payment channel dimension: official store / official web direct purchase / official
    authorized regional billing partner / unauthorized third-party reseller."""

    __tablename__ = "channel_partner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    region_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    commission_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    onboarded_date: Mapped[date] = mapped_column(Date, nullable=False)


class RegionPriceTier(Base):
    """Dimension for the official pricing coefficient of a player's billing country/region,
    used to identify regional arbitrage."""

    __tablename__ = "region_price_tier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    country_name: Mapped[str] = mapped_column(String(60), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    price_index: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    is_arbitrage_source_region: Mapped[bool] = mapped_column(Boolean, nullable=False)


class IapProduct(Base):
    """IAP product catalog: official USD list prices for shard packs / bundles / monthly
    passes at each tier."""

    __tablename__ = "iap_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String(80), nullable=False)
    product_category: Mapped[str] = mapped_column(String(20), nullable=False)
    shard_amount: Mapped[int] = mapped_column(Integer, nullable=True)
    base_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class GachaPool(Base):
    """Gacha pool dimension: standard pools are open year-round; limited pools run for
    2-3 week limited windows tied to a character launch."""

    __tablename__ = "gacha_pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    pool_type: Mapped[str] = mapped_column(String(20), nullable=False)
    disclosed_common_prob_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    disclosed_rare_prob_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    disclosed_epic_prob_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    disclosed_legendary_prob_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    active_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    active_end_date: Mapped[date] = mapped_column(Date, nullable=True)


class DiscountCode(Base):
    """Discount code dimension: official lifecycle marketing codes, region-exclusive promo
    codes, influencer partnership codes, and region codes that leaked and got arbitraged."""

    __tablename__ = "discount_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code_string: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    source_channel: Mapped[str] = mapped_column(String(30), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    intended_region_scope: Mapped[str] = mapped_column(String(40), nullable=True)
    leaked_beyond_scope: Mapped[bool] = mapped_column(Boolean, nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    max_redemptions: Mapped[int] = mapped_column(Integer, nullable=False)


class LiveOpsEvent(Base):
    """Live-Ops event calendar: login rewards, double drop rate, flash sale, character
    tie-in, anniversary, and other event types."""

    __tablename__ = "live_ops_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_stacked_event: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Player(Base):
    """Player account master record: install attribution, billing region, device
    fingerprint, payer segment, and economic health snapshot (as of REFERENCE_DATE)."""

    __tablename__ = "player"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    install_date: Mapped[date] = mapped_column(Date, nullable=False)
    acquisition_channel: Mapped[str] = mapped_column(String(40), nullable=False)
    region_price_tier_id: Mapped[int] = mapped_column(ForeignKey("region_price_tier.id"), nullable=False)
    device_fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    player_segment: Mapped[str] = mapped_column(String(20), nullable=False)
    lifetime_spend_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    last_active_date: Mapped[date] = mapped_column(Date, nullable=False)
    churn_risk_score: Mapped[int] = mapped_column(Integer, nullable=False)


class IapTransaction(Base):
    """IAP transaction ledger: each shard/bundle purchase, recording payment channel,
    billing region, list price, and paid price."""

    __tablename__ = "iap_transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    iap_product_id: Mapped[int] = mapped_column(ForeignKey("iap_product.id"), nullable=False)
    channel_partner_id: Mapped[int] = mapped_column(ForeignKey("channel_partner.id"), nullable=False)
    discount_code_id: Mapped[int] = mapped_column(ForeignKey("discount_code.id"), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    list_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    paid_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    shard_credited: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)


class GachaPullLog(Base):
    """Gacha pull records: the resulting rarity of each single/ten-pull, used to compare
    disclosed probability against actual probability."""

    __tablename__ = "gacha_pull_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    gacha_pool_id: Mapped[int] = mapped_column(ForeignKey("gacha_pool.id"), nullable=False)
    pull_date: Mapped[date] = mapped_column(Date, nullable=False)
    pull_source: Mapped[str] = mapped_column(String(10), nullable=False)
    shard_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    result_rarity: Mapped[str] = mapped_column(String(20), nullable=False)
    result_character_name: Mapped[str] = mapped_column(String(60), nullable=False)


class EventParticipation(Base):
    """Records of players participating in Live-Ops events, used to measure the
    relationship between an event's short-term lift and subsequent retention."""

    __tablename__ = "event_participation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    live_ops_event_id: Mapped[int] = mapped_column(ForeignKey("live_ops_event.id"), nullable=False)
    participation_date: Mapped[date] = mapped_column(Date, nullable=False)
    shard_spent_during_event: Mapped[int] = mapped_column(Integer, nullable=True)
    completed_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RefundChargebackRiskEvent(Base):
    """Refund / chargeback / suspected reseller ring risk event, linked to a specific
    transaction, used for fraud and channel governance analysis."""

    __tablename__ = "refund_chargeback_risk_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    iap_transaction_id: Mapped[int] = mapped_column(ForeignKey("iap_transaction.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_note: Mapped[str] = mapped_column(String(40), nullable=False)


class SupportTicket(Base):
    """Support tickets: probability pool complaints, billing disputes, ban appeals,
    general bug reports, etc."""

    __tablename__ = "support_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    related_iap_transaction_id: Mapped[int] = mapped_column(ForeignKey("iap_transaction.id"), nullable=True)
    ticket_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    resolution_time_hours: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    csat_score: Mapped[int] = mapped_column(Integer, nullable=True)


# ----------------------------------------------------------------------------
# Dimension table generator functions
# ----------------------------------------------------------------------------


def gen_channel_partners() -> pl.DataFrame:
    """Payment channel dimension: 2 official stores + official web + 2 official
    authorized regional billing partners + 5 unauthorized resellers."""
    rows = [
        {"channel_name": "Apple App Store (IAP)", "channel_type": "official_app_store", "is_authorized": True, "region_scope": "Global", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE},
        {"channel_name": "Google Play (IAP)", "channel_type": "official_app_store", "is_authorized": True, "region_scope": "Global", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE},
        {"channel_name": "Official Web Store (Direct)", "channel_type": "official_web", "is_authorized": True, "region_scope": "Global", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE + timedelta(days=60)},
        {"channel_name": "SEA Regional Billing Partner", "channel_type": "third_party_agent", "is_authorized": True, "region_scope": "Southeast Asia", "commission_rate_pct": 15.0, "onboarded_date": LAUNCH_DATE + timedelta(days=90)},
        {"channel_name": "LatAm Regional Billing Partner", "channel_type": "third_party_agent", "is_authorized": True, "region_scope": "Latin America", "commission_rate_pct": 15.0, "onboarded_date": LAUNCH_DATE + timedelta(days=120)},
        {"channel_name": "Agent - SEA TopUp Hub", "channel_type": "third_party_agent", "is_authorized": False, "region_scope": "Southeast Asia", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE + timedelta(days=150)},
        {"channel_name": "Agent - LatAm Recharge Co", "channel_type": "third_party_agent", "is_authorized": False, "region_scope": "Latin America", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE + timedelta(days=160)},
        {"channel_name": "Agent - EasyGem Reseller", "channel_type": "third_party_agent", "is_authorized": False, "region_scope": "Global", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE + timedelta(days=180)},
        {"channel_name": "Agent - GlobalShard Traders", "channel_type": "third_party_agent", "is_authorized": False, "region_scope": "Global", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE + timedelta(days=200)},
        {"channel_name": "Agent - DiscountVault Group", "channel_type": "third_party_agent", "is_authorized": False, "region_scope": "Europe", "commission_rate_pct": None, "onboarded_date": LAUNCH_DATE + timedelta(days=220)},
    ]
    return pl.DataFrame(rows).with_row_index("id", offset=1)


def gen_region_price_tiers() -> pl.DataFrame:
    """Billing region pricing coefficient dimension. TR/AR/PH/IN/ID/BR are the common
    source regions for price arbitrage (weak local currency or large regional price discount)."""
    rows = [
        {"country_code": "US", "country_name": "United States", "currency_code": "USD", "price_index": 1.00, "is_arbitrage_source_region": False},
        {"country_code": "CA", "country_name": "Canada", "currency_code": "CAD", "price_index": 1.00, "is_arbitrage_source_region": False},
        {"country_code": "GB", "country_name": "United Kingdom", "currency_code": "GBP", "price_index": 0.95, "is_arbitrage_source_region": False},
        {"country_code": "DE", "country_name": "Germany", "currency_code": "EUR", "price_index": 0.95, "is_arbitrage_source_region": False},
        {"country_code": "BR", "country_name": "Brazil", "currency_code": "BRL", "price_index": 0.80, "is_arbitrage_source_region": True},
        {"country_code": "TR", "country_name": "Turkey", "currency_code": "TRY", "price_index": 0.55, "is_arbitrage_source_region": True},
        {"country_code": "AR", "country_name": "Argentina", "currency_code": "ARS", "price_index": 0.50, "is_arbitrage_source_region": True},
        {"country_code": "PH", "country_name": "Philippines", "currency_code": "PHP", "price_index": 0.75, "is_arbitrage_source_region": True},
        {"country_code": "IN", "country_name": "India", "currency_code": "INR", "price_index": 0.70, "is_arbitrage_source_region": True},
        {"country_code": "ID", "country_name": "Indonesia", "currency_code": "IDR", "price_index": 0.72, "is_arbitrage_source_region": True},
    ]
    return pl.DataFrame(rows).with_row_index("id", offset=1)


def gen_iap_products() -> pl.DataFrame:
    """IAP product catalog: from a $0.99 starter shard pack up to a $199.99 whale-tier bundle."""
    rows = [
        {"sku_code": "SHARD_100", "product_name": "Starter Shard Pack (100)", "product_category": "currency_pack", "shard_amount": 100, "base_price_usd": 0.99},
        {"sku_code": "SHARD_550", "product_name": "Small Shard Pack (550)", "product_category": "currency_pack", "shard_amount": 550, "base_price_usd": 4.99},
        {"sku_code": "SHARD_1200", "product_name": "Medium Shard Pack (1,200)", "product_category": "currency_pack", "shard_amount": 1200, "base_price_usd": 9.99},
        {"sku_code": "SHARD_2500", "product_name": "Large Shard Pack (2,500)", "product_category": "currency_pack", "shard_amount": 2500, "base_price_usd": 19.99},
        {"sku_code": "SHARD_6500", "product_name": "Mega Shard Pack (6,500)", "product_category": "currency_pack", "shard_amount": 6500, "base_price_usd": 49.99},
        {"sku_code": "SHARD_14000", "product_name": "Whale Shard Pack (14,000)", "product_category": "currency_pack", "shard_amount": 14000, "base_price_usd": 99.99},
        {"sku_code": "SHARD_30000", "product_name": "Ultimate Shard Vault (30,000)", "product_category": "currency_pack", "shard_amount": 30000, "base_price_usd": 199.99},
        {"sku_code": "BUNDLE_NEWBIE", "product_name": "Newbie Bundle", "product_category": "bundle", "shard_amount": 800, "base_price_usd": 4.99},
        {"sku_code": "PASS_VIP_MONTH", "product_name": "Monthly VIP Pass", "product_category": "subscription", "shard_amount": 300, "base_price_usd": 9.99},
        {"sku_code": "PASS_BATTLE_PREMIUM", "product_name": "Battle Pass Premium", "product_category": "subscription", "shard_amount": 0, "base_price_usd": 14.99},
        {"sku_code": "BUNDLE_EMBER_QUEEN", "product_name": "Ember Queen Banner Bundle", "product_category": "bundle", "shard_amount": 1600, "base_price_usd": 29.99},
        {"sku_code": "BUNDLE_ANNIVERSARY", "product_name": "Anniversary Celebration Bundle", "product_category": "bundle", "shard_amount": 2200, "base_price_usd": 39.99},
    ]
    return pl.DataFrame(rows).with_row_index("id", offset=1)


# Trap 2: 3 limited pools are rigged (actual legendary drop rate significantly below
# disclosed), 2 limited pools are honest, and all 3 standard pools are honest.
GACHA_POOL_DEFS = [
    {"pool_name": "Standard Summon Pool", "pool_type": "standard", "common": 58.0, "rare": 32.0, "epic": 8.0, "legendary_disclosed": 2.0, "legendary_actual": 2.0, "start": LAUNCH_DATE, "end": None},
    {"pool_name": "Starter Newbie Pool", "pool_type": "standard", "common": 50.0, "rare": 35.0, "epic": 12.0, "legendary_disclosed": 3.0, "legendary_actual": 3.0, "start": LAUNCH_DATE, "end": None},
    {"pool_name": "Veteran Loyalty Pool", "pool_type": "standard", "common": 55.0, "rare": 30.0, "epic": 10.0, "legendary_disclosed": 5.0, "legendary_actual": 5.0, "start": LAUNCH_DATE + timedelta(days=180), "end": None},
    {"pool_name": "Ember Queen Rate-Up Banner", "pool_type": "limited_rateup", "common": 55.0, "rare": 30.0, "epic": 12.0, "legendary_disclosed": 3.0, "legendary_actual": 1.2, "start": date(2025, 4, 1), "end": date(2025, 4, 14)},
    {"pool_name": "Frostbound Knight Rate-Up Banner", "pool_type": "limited_rateup", "common": 55.0, "rare": 30.0, "epic": 12.0, "legendary_disclosed": 3.0, "legendary_actual": 1.3, "start": date(2025, 7, 1), "end": date(2025, 7, 14)},
    {"pool_name": "Shadowfang Assassin Rate-Up Banner", "pool_type": "limited_rateup", "common": 55.0, "rare": 30.0, "epic": 12.0, "legendary_disclosed": 3.0, "legendary_actual": 3.0, "start": date(2025, 9, 15), "end": date(2025, 9, 28)},
    {"pool_name": "Anniversary Celebration Banner", "pool_type": "limited_rateup", "common": 50.0, "rare": 30.0, "epic": 16.5, "legendary_disclosed": 3.5, "legendary_actual": 1.5, "start": date(2026, 1, 6), "end": date(2026, 1, 20)},
    {"pool_name": "Golden Phoenix Rate-Up Banner", "pool_type": "limited_rateup", "common": 55.0, "rare": 30.0, "epic": 12.0, "legendary_disclosed": 3.0, "legendary_actual": 3.2, "start": date(2026, 4, 1), "end": date(2026, 4, 14)},
]


def gen_gacha_pools() -> pl.DataFrame:
    """Gacha pool dimension. legendary_disclosed is the disclosed probability (written to a
    DDL column); legendary_actual is only used for pull-result generation and is not
    persisted as a table column -- analysts must infer the actual probability from the
    real results in gacha_pull_log."""
    rows = []
    for pool in GACHA_POOL_DEFS:
        rows.append({
            "pool_name": pool["pool_name"],
            "pool_type": pool["pool_type"],
            "disclosed_common_prob_pct": pool["common"],
            "disclosed_rare_prob_pct": pool["rare"],
            "disclosed_epic_prob_pct": pool["epic"],
            "disclosed_legendary_prob_pct": pool["legendary_disclosed"],
            "active_start_date": pool["start"],
            "active_end_date": pool["end"],
        })
    return pl.DataFrame(rows).with_row_index("id", offset=1)


def gen_discount_codes() -> pl.DataFrame:
    """Discount code dimension: official email marketing codes, influencer partnership
    codes, region-exclusive promo codes (4 of which are leaked and arbitraged, trap 4)."""
    rows = []
    code_id = 1
    for _ in range(20):
        rows.append({
            "code_string": f"MAIL{code_id:04d}",
            "source_channel": "official_lifecycle_email",
            "discount_pct": round(random.uniform(10.0, 20.0), 1),
            "intended_region_scope": None,
            "leaked_beyond_scope": False,
            "issued_date": LAUNCH_DATE + timedelta(days=random.randint(0, 480)),
            "max_redemptions": random.choice([500, 1000, 2000]),
        })
        code_id += 1
    for _ in range(6):
        rows.append({
            "code_string": f"INFL{code_id:04d}",
            "source_channel": "influencer_partnership",
            "discount_pct": round(random.uniform(15.0, 25.0), 1),
            "intended_region_scope": None,
            "leaked_beyond_scope": False,
            "issued_date": LAUNCH_DATE + timedelta(days=random.randint(0, 480)),
            "max_redemptions": random.choice([300, 500, 800]),
        })
        code_id += 1
    # Region-exclusive promo codes: 19 of them, targeting the 6 regions where arbitrage is
    # common; 4 of these are leaked (trap 4).
    arbitrage_regions = ["Turkey", "Argentina", "Philippines", "Indonesia", "India", "Brazil"]
    leaked_flags = [True, True, True, True] + [False] * 15
    random.shuffle(leaked_flags)
    for i in range(19):
        region = arbitrage_regions[i % len(arbitrage_regions)]
        rows.append({
            "code_string": f"REGION{code_id:04d}",
            "source_channel": "regional_promo",
            "discount_pct": round(random.uniform(20.0, 40.0), 1),
            "intended_region_scope": region,
            "leaked_beyond_scope": leaked_flags[i],
            "issued_date": LAUNCH_DATE + timedelta(days=random.randint(0, 480)),
            "max_redemptions": random.choice([200, 400, 600]),
        })
        code_id += 1
    return pl.DataFrame(rows).with_row_index("id", offset=1)


# 30 Live-Ops events, using an explicit duration/gap sequence to produce 8 "stacked"
# events (trap 3).
EVENT_DURATIONS = ([10, 6] * 15)
EVENT_GAP_SMALL_POSITIONS = {3, 4, 10, 11, 17, 18, 24, 25}
EVENT_TYPE_NAMES = {
    "login_bonus": ["Daily Login Bonanza", "Welcome Back Rewards", "Login Streak Festival"],
    "double_drop_rate": ["Double Drop Weekend", "Loot Surge", "Material Rush"],
    "flash_sale": ["Flash Shard Sale", "Weekend Value Bundle Sale", "Limited Time Discount Vault"],
    "rate_up_banner_tie_in": ["Rate-Up Banner Celebration", "New Hero Spotlight", "Banner Debut Festival"],
    # Display names are not tied to specific calendar dates, to avoid the i%5 rotation
    # landing "anniversary/founders" wording on a semantically mismatched month.
    # (The one actually landing on the 2026-01-06 anniversary date is the gacha pool
    # "Anniversary Celebration Banner", which is unrelated to this.)
    "anniversary": ["Grand Realm Festival", "Ember Champions Gala", "Realm Legends Showcase"],
}
EVENT_TYPE_CYCLE = ["login_bonus", "double_drop_rate", "flash_sale", "rate_up_banner_tie_in", "anniversary"]


def gen_live_ops_events() -> pl.DataFrame:
    """Live-Ops event calendar. 8 events have a gap < 7 days from the previous event
    (stacked), the rest have a 12-day gap (normal pacing)."""
    rows = []
    current_start = LAUNCH_DATE
    prev_end = None
    for i in range(30):
        duration = EVENT_DURATIONS[i]
        start = current_start
        end = start + timedelta(days=duration)
        is_stacked = prev_end is not None and (start - prev_end).days < STACKED_EVENT_GAP_DAYS
        event_type = EVENT_TYPE_CYCLE[i % len(EVENT_TYPE_CYCLE)]
        name = f"{random.choice(EVENT_TYPE_NAMES[event_type])} {i + 1}"
        rows.append({
            "event_name": name,
            "event_type": event_type,
            "start_date": start,
            "end_date": end,
            "is_stacked_event": is_stacked,
        })
        prev_end = end
        gap = 4 if i in EVENT_GAP_SMALL_POSITIONS else 12
        current_start = end + timedelta(days=gap)
    return pl.DataFrame(rows).with_row_index("id", offset=1)


# ----------------------------------------------------------------------------
# Player master records and trap 5 (device fingerprint fraud ring)
# ----------------------------------------------------------------------------

ACQUISITION_CHANNELS = [
    ("Organic - App Store Search", 0.35),
    ("Organic - Word of Mouth", 0.10),
    ("Meta Ads UA", 0.20),
    ("TikTok Ads UA", 0.15),
    ("Google UAC", 0.12),
    ("AppLovin Network", 0.06),
    ("Influencer Partnership", 0.02),
]

# Billing region weights. 55% land in "developed" markets like the US, Canada, UK,
# Germany, and 45% land in the 6 regions where arbitrage is common, ensuring trap 4
# (regional arbitrage) has enough sample size to analyze.
REGION_WEIGHTS = {
    "US": 0.25, "CA": 0.12, "GB": 0.10, "DE": 0.08, "BR": 0.10,
    "TR": 0.08, "AR": 0.07, "PH": 0.08, "IN": 0.07, "ID": 0.05,
}


def weighted_choice(pairs: list[tuple]) -> object:
    """Pick one label at random from a list of (label, weight) pairs, weighted. The
    weights don't need to sum to 1."""
    labels = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return random.choices(labels, weights=weights, k=1)[0]


def gen_players(region_rows: list[dict]) -> list[dict]:
    """Player master records. whale/dolphin/minnow/non_payer headcounts are fixed
    precisely at 1%/3%/6%/90% of the sample (trap 1); 48 players are split into 10 groups
    (4-5 people each) sharing the same device fingerprint, simulating a sock-puppet
    fraud ring bulk-registered from the same device (trap 5)."""
    region_by_code = {r["country_code"]: r["id"] for r in region_rows}
    segment_pool = (
        ["whale"] * SEGMENT_COUNTS["whale"]
        + ["dolphin"] * SEGMENT_COUNTS["dolphin"]
        + ["minnow"] * SEGMENT_COUNTS["minnow"]
        + ["non_payer"] * SEGMENT_COUNTS["non_payer"]
    )
    random.shuffle(segment_pool)

    non_whale_indices = [i for i, seg in enumerate(segment_pool) if seg != "whale"]
    random.shuffle(non_whale_indices)
    fraud_ring_member_index: dict[int, str] = {}
    cursor = 0
    for ring_id in range(FRAUD_RING_COUNT):
        size = random.randint(FRAUD_RING_SIZE_MIN, FRAUD_RING_SIZE_MAX)
        members = non_whale_indices[cursor:cursor + size]
        cursor += size
        shared_hash = hashlib.sha256(f"fraud-ring-{ring_id}-{RANDOM_SEED}".encode()).hexdigest()
        for m in members:
            fraud_ring_member_index[m] = shared_hash

    players = []
    total_days = (REFERENCE_DATE - LAUNCH_DATE).days
    for i in range(PLAYER_COUNT):
        segment = segment_pool[i]
        install_offset = random.randint(0, max(1, total_days - 10))
        install_date = LAUNCH_DATE + timedelta(days=install_offset)
        acquisition_channel = weighted_choice(ACQUISITION_CHANNELS)
        country_code = weighted_choice(list(REGION_WEIGHTS.items()))
        if i in fraud_ring_member_index:
            device_hash = fraud_ring_member_index[i]
        else:
            device_hash = hashlib.sha256(f"device-{i}-{RANDOM_SEED}".encode()).hexdigest()
        tenure_mean = SEGMENT_TENURE_MEAN_DAYS[segment]
        max_possible = max((REFERENCE_DATE - install_date).days, 7)
        tenure_days = int(min(max(random.expovariate(1 / tenure_mean), 7), max_possible))
        baseline_cutoff = min(install_date + timedelta(days=tenure_days), REFERENCE_DATE)
        players.append({
            "id": i + 1,
            "install_date": install_date,
            "acquisition_channel": acquisition_channel,
            "region_price_tier_id": region_by_code[country_code],
            "device_fingerprint_hash": device_hash,
            "player_segment": segment,
            "is_fraud_ring_member": i in fraud_ring_member_index,
            "baseline_activity_end_date": baseline_cutoff,
            "final_activity_end_date": baseline_cutoff,
        })
    return players


# ----------------------------------------------------------------------------
# Live-Ops event participation and trap 3 (stacked-event false prosperity)
# ----------------------------------------------------------------------------

EVENT_PARTICIPATION_BASE_PROB = {
    "whale": 0.90,
    "dolphin": 0.75,
    "minnow": 0.55,
    "non_payer": 0.30,
}


def gen_event_participation(players: list[dict], events: list[dict]) -> list[dict]:
    """Player event participation records. First generate a version of the participation
    records based on each player's baseline activity window, then use it to determine
    that about 55% of players who participated in >= 2 stacked events will burn out
    early (trap 3), and re-filter the participation records with the shortened window so
    that all of a burned-out player's subsequent behavioral records (not just event
    participation) shrink accordingly."""
    rows = []
    row_id = 1
    for p in players:
        prob = EVENT_PARTICIPATION_BASE_PROB[p["player_segment"]]
        for ev in events:
            window_start = max(ev["start_date"], p["install_date"])
            window_end = min(ev["end_date"], p["baseline_activity_end_date"])
            if window_start > window_end:
                continue
            if random.random() > prob:
                continue
            span = (window_end - window_start).days
            participation_date = window_start + timedelta(days=random.randint(0, span) if span > 0 else 0)
            completed = random.random() < (0.7 if p["player_segment"] != "non_payer" else 0.45)
            shard_spent = None
            if p["player_segment"] != "non_payer" and random.random() < 0.6:
                shard_spent = random.randint(200, 3000)
            rows.append({
                "id": row_id,
                "player_id": p["id"],
                "live_ops_event_id": ev["id"],
                "participation_date": participation_date,
                "shard_spent_during_event": shard_spent,
                "completed_flag": completed,
                "_is_stacked": ev["is_stacked_event"],
                "_event_end_date": ev["end_date"],
            })
            row_id += 1

    stacked_rows_by_player: dict[int, list[dict]] = {}
    for r in rows:
        if r["_is_stacked"]:
            stacked_rows_by_player.setdefault(r["player_id"], []).append(r)

    player_by_id = {p["id"]: p for p in players}
    for player_id, stacked_list in stacked_rows_by_player.items():
        if len(stacked_list) >= STACKED_FATIGUE_MIN_COUNT and random.random() < STACKED_FATIGUE_CHURN_PROB:
            last_stacked_end = max(r["_event_end_date"] for r in stacked_list)
            cutoff_days = random.randint(STACKED_FATIGUE_CUTOFF_MIN_DAYS, STACKED_FATIGUE_CUTOFF_MAX_DAYS)
            new_cutoff = last_stacked_end + timedelta(days=cutoff_days)
            p = player_by_id[player_id]
            if new_cutoff < p["final_activity_end_date"]:
                p["final_activity_end_date"] = new_cutoff

    final_rows = []
    for r in rows:
        p = player_by_id[r["player_id"]]
        if r["participation_date"] <= p["final_activity_end_date"]:
            del r["_is_stacked"]
            del r["_event_end_date"]
            final_rows.append(r)
    for idx, r in enumerate(final_rows):
        r["id"] = idx + 1
    return final_rows


# ----------------------------------------------------------------------------
# IAP transactions and trap 1 (whale dependency) / trap 3 (short-term price hike) /
# trap 4 (reseller channel discounting)
# ----------------------------------------------------------------------------

# Product tier weights preferred by each payer segment. whale clearly favors large
# bundles, minnow favors small starter packs.
PRODUCT_WEIGHTS_BY_SEGMENT = {
    "whale": [
        ("SHARD_100", 0.02), ("SHARD_550", 0.05), ("SHARD_1200", 0.08), ("SHARD_2500", 0.12),
        ("SHARD_6500", 0.20), ("SHARD_14000", 0.25), ("SHARD_30000", 0.18),
        ("BUNDLE_EMBER_QUEEN", 0.04), ("BUNDLE_ANNIVERSARY", 0.04),
        ("PASS_VIP_MONTH", 0.01), ("PASS_BATTLE_PREMIUM", 0.01),
    ],
    "dolphin": [
        ("SHARD_100", 0.05), ("SHARD_550", 0.15), ("SHARD_1200", 0.20), ("SHARD_2500", 0.20),
        ("SHARD_6500", 0.15), ("SHARD_14000", 0.05), ("SHARD_30000", 0.01),
        ("BUNDLE_EMBER_QUEEN", 0.05), ("BUNDLE_ANNIVERSARY", 0.04),
        ("PASS_VIP_MONTH", 0.06), ("PASS_BATTLE_PREMIUM", 0.04),
    ],
    "minnow": [
        ("SHARD_100", 0.20), ("SHARD_550", 0.25), ("SHARD_1200", 0.20), ("SHARD_2500", 0.10),
        ("SHARD_6500", 0.03), ("BUNDLE_NEWBIE", 0.10),
        ("PASS_VIP_MONTH", 0.07), ("PASS_BATTLE_PREMIUM", 0.05),
    ],
}


def pick_channel_partner(country_code: str, channel_ids: dict) -> tuple[int, str]:
    """Sample a payment channel. Official store/web accounts for about 96%, unauthorized
    resellers about 2.8%, official authorized regional partners about 1.2%."""
    r = random.random()
    if r < 0.45:
        return channel_ids["apple"], "apple"
    if r < 0.87:
        return channel_ids["google"], "google"
    if r < 0.96:
        return channel_ids["official_web"], "official_web"
    if r < 0.988:
        return random.choice(channel_ids["unauthorized"]), "unauthorized_agent"
    if country_code in ("PH", "ID"):
        return channel_ids["sea_partner"], "authorized_agent"
    if country_code in ("BR", "AR"):
        return channel_ids["latam_partner"], "authorized_agent"
    return random.choice([channel_ids["sea_partner"], channel_ids["latam_partner"]]), "authorized_agent"


def gen_iap_transactions(
    players: list[dict],
    iap_products: list[dict],
    channel_ids: dict,
    country_code_by_region_id: dict,
    region_index_by_id: dict,
    stacked_events: list[dict],
) -> list[dict]:
    """IAP transaction ledger. Whale-tier products cluster in large bundles (the
    segmentation basis for trap 1); unauthorized reseller channel (unauthorized_agent)
    transactions systematically pay less than the official list price (trap 4); each
    transaction has about a 12% probability of being deliberately anchored into a
    stacked event window and temporarily marked up (effectively about 8%-9% of all
    transactions, the short-term false-prosperity signal for trap 3)."""
    product_by_sku = {p["sku_code"]: p for p in iap_products}
    rows = []
    row_id = 1
    for p in players:
        segment = p["player_segment"]
        if segment == "non_payer":
            continue
        mean_count = SEGMENT_TX_COUNT_MEAN[segment]
        tx_count = max(1, int(round(random.gauss(mean_count, mean_count * 0.35))))
        country_code = country_code_by_region_id[p["region_price_tier_id"]]
        region_index = region_index_by_id[p["region_price_tier_id"]]
        window_days = max((p["final_activity_end_date"] - p["install_date"]).days, 1)
        overlapping_stacked = [
            ev for ev in stacked_events
            if ev["start_date"] <= p["final_activity_end_date"] and ev["end_date"] >= p["install_date"]
        ]
        product_choices = PRODUCT_WEIGHTS_BY_SEGMENT[segment]
        product_labels = [c[0] for c in product_choices]
        product_weight_values = [c[1] for c in product_choices]
        for _ in range(tx_count):
            anchor_stacked = bool(overlapping_stacked) and random.random() < 0.12
            if anchor_stacked:
                ev = random.choice(overlapping_stacked)
                lo = max(ev["start_date"], p["install_date"])
                hi = min(ev["end_date"], p["final_activity_end_date"])
                span = max((hi - lo).days, 0)
                tx_date = lo + timedelta(days=random.randint(0, span))
            else:
                tx_date = p["install_date"] + timedelta(days=random.randint(0, window_days))
            sku = random.choices(product_labels, weights=product_weight_values, k=1)[0]
            product = product_by_sku[sku]
            list_price = round(product["base_price_usd"] * region_index, 2)
            channel_id, channel_kind = pick_channel_partner(country_code, channel_ids)
            if channel_kind == "unauthorized_agent":
                paid_price = round(list_price * UNAUTHORIZED_AGENT_PRICE_FACTOR * random.uniform(0.95, 1.05), 2)
                payment_method = "agent_transfer"
            elif channel_kind == "authorized_agent":
                paid_price = round(list_price * random.uniform(0.97, 1.03), 2)
                payment_method = "agent_transfer"
            elif channel_kind == "official_web":
                paid_price = round(list_price * random.uniform(0.97, 1.03), 2)
                payment_method = random.choices(["credit_card", "gift_card"], weights=[0.8, 0.2], k=1)[0]
            elif channel_kind == "apple":
                paid_price = round(list_price * random.uniform(0.97, 1.03), 2)
                payment_method = "apple_pay"
            else:
                paid_price = round(list_price * random.uniform(0.97, 1.03), 2)
                payment_method = "google_pay"
            if anchor_stacked:
                paid_price = round(paid_price * STACKED_EVENT_SPEND_MULTIPLIER, 2)
            rows.append({
                "id": row_id,
                "player_id": p["id"],
                "iap_product_id": product["id"],
                "channel_partner_id": channel_id,
                "discount_code_id": None,
                "transaction_date": tx_date,
                "list_price_usd": list_price,
                "paid_price_usd": paid_price,
                "shard_credited": product["shard_amount"] or 0,
                "payment_method": payment_method,
                "_channel_kind": channel_kind,
            })
            row_id += 1
    return rows


REGION_COUNTRY_BY_NAME = {
    "Turkey": "TR", "Argentina": "AR", "Philippines": "PH",
    "Indonesia": "ID", "India": "IN", "Brazil": "BR",
}
OUT_OF_SCOPE_CANDIDATE_COUNTRIES = ["US", "CA", "GB", "DE"]


def apply_discount_codes(
    transactions: list[dict],
    players_by_id: dict,
    discount_codes: list[dict],
    country_code_by_region_id: dict,
) -> None:
    """Attach discount codes to a subset of transactions after the fact (mutates
    transactions in place). For the 4 region-exclusive promo codes flagged
    leaked_beyond_scope, deliberately place about 75% of redemptions outside the target
    region; for the other 15 normal region codes, keep the out-of-scope redemption rate
    at about 6% (the core signal for trap 4)."""
    leaked_codes = [c for c in discount_codes if c["leaked_beyond_scope"]]
    normal_regional_codes = [c for c in discount_codes if c["source_channel"] == "regional_promo" and not c["leaked_beyond_scope"]]
    global_codes = [c for c in discount_codes if c["intended_region_scope"] is None]

    tx_indices_by_country: dict[str, list[int]] = {}
    for idx, t in enumerate(transactions):
        country = country_code_by_region_id[players_by_id[t["player_id"]]["region_price_tier_id"]]
        tx_indices_by_country.setdefault(country, []).append(idx)

    used_indices: set[int] = set()

    def redeem(code_row: dict, target_country: str) -> bool:
        candidates = [i for i in tx_indices_by_country.get(target_country, []) if i not in used_indices]
        if not candidates:
            return False
        idx = random.choice(candidates)
        used_indices.add(idx)
        t = transactions[idx]
        t["discount_code_id"] = code_row["id"]
        t["paid_price_usd"] = round(t["paid_price_usd"] * (1 - code_row["discount_pct"] / 100), 2)
        return True

    for code in leaked_codes:
        target_country = REGION_COUNTRY_BY_NAME[code["intended_region_scope"]]
        for _ in range(60):
            if random.random() < LEAKED_CODE_OUT_OF_SCOPE_RATE:
                country = random.choice(OUT_OF_SCOPE_CANDIDATE_COUNTRIES)
            else:
                country = target_country
            redeem(code, country)

    for code in normal_regional_codes:
        target_country = REGION_COUNTRY_BY_NAME[code["intended_region_scope"]]
        for _ in range(20):
            if random.random() < NORMAL_CODE_OUT_OF_SCOPE_RATE:
                country = random.choice(OUT_OF_SCOPE_CANDIDATE_COUNTRIES)
            else:
                country = target_country
            redeem(code, country)

    all_countries = list(tx_indices_by_country.keys())
    for code in global_codes:
        for _ in range(15):
            country = random.choice(all_countries)
            redeem(code, country)


# ----------------------------------------------------------------------------
# Gacha pull records and trap 2 (probability-pool disclosure gap)
# ----------------------------------------------------------------------------

STANDARD_POOL_WEIGHT = 1.0
LIMITED_POOL_WEIGHT_WHEN_ACTIVE = 22.0
RARITY_LEVELS = ["Common", "Rare", "Epic", "Legendary"]


def build_gacha_pool_runtime(gacha_pool_df: pl.DataFrame) -> list[dict]:
    """Combine the actual probabilities from GACHA_POOL_DEFS (legendary_actual, etc.),
    which are only used for sampling and are not persisted as table columns, with the
    already-generated DB ids, for use by gen_gacha_pull_logs."""
    df_rows = gacha_pool_df.to_dicts()
    runtime = []
    for defn, row in zip(GACHA_POOL_DEFS, df_rows):
        runtime.append({
            "id": row["id"],
            "pool_type": defn["pool_type"],
            "active_start_date": defn["start"],
            "active_end_date": defn["end"],
            "_actual_common": defn["common"],
            "_actual_rare": defn["rare"],
            "_actual_epic": defn["epic"],
            "_actual_legendary": defn["legendary_actual"],
        })
    return runtime


def roll_rarity(pool: dict) -> str:
    """Roll the result rarity using the pool's actual probability (not the disclosed
    probability). The gap between the two is exactly the core of trap 2."""
    weights = [pool["_actual_common"], pool["_actual_rare"], pool["_actual_epic"], pool["_actual_legendary"]]
    return random.choices(RARITY_LEVELS, weights=weights, k=1)[0]


def gen_gacha_pull_logs(players: list[dict], gacha_pools: list[dict]) -> list[dict]:
    """Gacha pull records. Players pull more heavily (higher weight) while a limited pool
    is active; 3 limited pools have an actual legendary drop rate significantly below
    the disclosed probability, while the other 2 limited pools are as honest as the
    standard pools (trap 2)."""
    standard_pools = [g for g in gacha_pools if g["pool_type"] == "standard"]
    limited_pools = [g for g in gacha_pools if g["pool_type"] == "limited_rateup"]
    rows = []
    row_id = 1
    for p in players:
        segment = p["player_segment"]
        mean_pulls = SEGMENT_GACHA_PULL_MEAN[segment]
        pull_count = max(0, int(round(random.gauss(mean_pulls, mean_pulls * 0.5))))
        window_days = max((p["final_activity_end_date"] - p["install_date"]).days, 1)
        for _ in range(pull_count):
            pull_date = p["install_date"] + timedelta(days=random.randint(0, window_days))
            eligible_standard = [g for g in standard_pools if g["active_start_date"] <= pull_date]
            active_limited = [
                g for g in limited_pools
                if g["active_start_date"] <= pull_date <= g["active_end_date"]
            ]
            candidates = eligible_standard + active_limited
            if not candidates:
                continue
            weights = [
                LIMITED_POOL_WEIGHT_WHEN_ACTIVE if g["pool_type"] == "limited_rateup" else STANDARD_POOL_WEIGHT
                for g in candidates
            ]
            pool = random.choices(candidates, weights=weights, k=1)[0]
            pull_source = random.choices(["single", "ten_pull"], weights=[0.65, 0.35], k=1)[0]
            shard_cost = 150 if pull_source == "single" else 1350
            rarity = roll_rarity(pool)
            character_name = f"{fake.first_name()} the {rarity}"
            rows.append({
                "id": row_id,
                "player_id": p["id"],
                "gacha_pool_id": pool["id"],
                "pull_date": pull_date,
                "pull_source": pull_source,
                "shard_cost": shard_cost,
                "result_rarity": rarity,
                "result_character_name": character_name,
            })
            row_id += 1
    return rows


# ----------------------------------------------------------------------------
# Refund/chargeback risk events (trap 4 reseller channel + trap 5 device
# fingerprint fraud ring)
# ----------------------------------------------------------------------------


def gen_refund_chargeback_events(transactions: list[dict], players_by_id: dict) -> list[dict]:
    """Refund / chargeback / suspected reseller ring risk events. Device fingerprint
    fraud ring accounts (~45%) and unauthorized reseller channels (~20%) have an
    incidence rate far above the official channel baseline (~2%), with official
    authorized regional partners in between (~4%) (trap 4/trap 5)."""
    rows = []
    row_id = 1
    for t in transactions:
        player = players_by_id[t["player_id"]]
        channel_kind = t["_channel_kind"]
        if player["is_fraud_ring_member"]:
            base_rate = FRAUD_RING_CHARGEBACK_RATE
            note = "multi_account_cluster"
        elif channel_kind == "unauthorized_agent":
            base_rate = UNAUTHORIZED_AGENT_CHARGEBACK_RATE
            note = "agent_sourced_dispute"
        elif channel_kind == "authorized_agent":
            base_rate = AUTHORIZED_AGENT_CHARGEBACK_RATE
            note = "billing_error"
        else:
            base_rate = OFFICIAL_CHANNEL_CHARGEBACK_RATE
            note = "genuine_dissatisfaction"
        if random.random() >= base_rate:
            continue
        if note == "multi_account_cluster":
            event_type = random.choices(
                ["refund_requested", "chargeback_filed", "account_flagged_reseller_activity"],
                weights=[0.3, 0.3, 0.4], k=1,
            )[0]
        else:
            event_type = random.choice(["refund_requested", "chargeback_filed"])
        # event_date falls 1-21 days after the transaction date, but is capped at the
        # REFERENCE_DATE baseline: the analysis snapshot cutoff is "as of 2026-06-30",
        # so no risk event should appear later than the snapshot (the cap only affects a
        # tiny number of transactions close to the snapshot date).
        event_date = min(t["transaction_date"] + timedelta(days=random.randint(1, 21)), REFERENCE_DATE)
        resolution = random.choices(["approved", "denied", "pending"], weights=[0.55, 0.30, 0.15], k=1)[0]
        rows.append({
            "id": row_id,
            "player_id": t["player_id"],
            "iap_transaction_id": t["id"],
            "event_type": event_type,
            "event_date": event_date,
            "amount_usd": t["paid_price_usd"],
            "resolution_status": resolution,
            "risk_note": note,
        })
        row_id += 1
    return rows


# ----------------------------------------------------------------------------
# Support tickets
# ----------------------------------------------------------------------------

TICKET_CATEGORY_WEIGHTS = {
    "whale": [
        ("billing_dispute", 0.35), ("account_banned_appeal", 0.15), ("gacha_odds_complaint", 0.20),
        ("general_bug", 0.25), ("refund_request_followup", 0.05),
    ],
    "dolphin": [
        ("billing_dispute", 0.30), ("gacha_odds_complaint", 0.25), ("general_bug", 0.35),
        ("account_banned_appeal", 0.05), ("refund_request_followup", 0.05),
    ],
    "minnow": [
        ("gacha_odds_complaint", 0.30), ("general_bug", 0.45), ("billing_dispute", 0.15),
        ("account_banned_appeal", 0.05), ("refund_request_followup", 0.05),
    ],
    "non_payer": [
        ("general_bug", 0.70), ("gacha_odds_complaint", 0.25), ("account_banned_appeal", 0.05),
    ],
}
TICKET_PROB_BY_SEGMENT = {"whale": 0.9, "dolphin": 0.7, "minnow": 0.4, "non_payer": 0.08}


def gen_support_tickets(players: list[dict], transactions_by_player: dict) -> list[dict]:
    """Support tickets. Deeper-paying players have a higher probability of opening a
    ticket; billing_dispute/refund_request_followup categories are only linked to a
    specific transaction for players who have IAP records."""
    rows = []
    row_id = 1
    for p in players:
        prob = TICKET_PROB_BY_SEGMENT[p["player_segment"]]
        n_tickets = 0
        while random.random() < prob and n_tickets < 4:
            n_tickets += 1
            prob *= 0.4
        choices = TICKET_CATEGORY_WEIGHTS[p["player_segment"]]
        labels = [c[0] for c in choices]
        weights = [c[1] for c in choices]
        window_days = max((p["final_activity_end_date"] - p["install_date"]).days, 1)
        player_txs = transactions_by_player.get(p["id"], [])
        for _ in range(n_tickets):
            category = random.choices(labels, weights=weights, k=1)[0]
            ticket_date = p["install_date"] + timedelta(days=random.randint(0, window_days))
            related_tx = None
            if player_txs and category in ("billing_dispute", "refund_request_followup") and random.random() < 0.7:
                related_tx = random.choice(player_txs)["id"]
            priority = random.choices(["low", "medium", "high"], weights=[0.4, 0.4, 0.2], k=1)[0]
            resolution_hours = round(random.uniform(1, 72), 1)
            csat = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.1, 0.2, 0.3, 0.3], k=1)[0] if random.random() < 0.7 else None
            rows.append({
                "id": row_id,
                "player_id": p["id"],
                "related_iap_transaction_id": related_tx,
                "ticket_date": ticket_date,
                "category": category,
                "priority": priority,
                "resolution_time_hours": resolution_hours,
                "csat_score": csat,
            })
            row_id += 1
    return rows


# ----------------------------------------------------------------------------
# Backfilling player snapshot fields
# ----------------------------------------------------------------------------


def finalize_players(
    players: list[dict],
    transactions: list[dict],
    gacha_pulls: list[dict],
    event_participations: list[dict],
    support_tickets: list[dict],
) -> None:
    """Backfill player snapshot fields (mutates players in place): lifetime spend, last
    active date, churn risk score."""
    spend_by_player: dict[int, float] = {}
    for t in transactions:
        spend_by_player[t["player_id"]] = spend_by_player.get(t["player_id"], 0.0) + t["paid_price_usd"]

    last_active_by_player: dict[int, date] = {}

    def bump(player_id: int, d: date) -> None:
        if player_id not in last_active_by_player or d > last_active_by_player[player_id]:
            last_active_by_player[player_id] = d

    for t in transactions:
        bump(t["player_id"], t["transaction_date"])
    for g in gacha_pulls:
        bump(g["player_id"], g["pull_date"])
    for e in event_participations:
        bump(e["player_id"], e["participation_date"])
    for s in support_tickets:
        bump(s["player_id"], s["ticket_date"])

    for p in players:
        p["lifetime_spend_usd"] = round(spend_by_player.get(p["id"], 0.0), 2)
        last_active = last_active_by_player.get(p["id"], p["install_date"])
        p["last_active_date"] = last_active
        inactive_days = (REFERENCE_DATE - last_active).days
        tenure_norm = max(SEGMENT_TENURE_MEAN_DAYS[p["player_segment"]] / 3, 20)
        risk = min(100, max(0, round(100 * inactive_days / tenure_norm)))
        p["churn_risk_score"] = int(risk)


# ----------------------------------------------------------------------------
# TSV orchestration and SQLite build
# ----------------------------------------------------------------------------

PLAYER_COLUMNS = [
    "id", "install_date", "acquisition_channel", "region_price_tier_id",
    "device_fingerprint_hash", "player_segment", "lifetime_spend_usd",
    "last_active_date", "churn_risk_score",
]
TRANSACTION_COLUMNS = [
    "id", "player_id", "iap_product_id", "channel_partner_id", "discount_code_id",
    "transaction_date", "list_price_usd", "paid_price_usd", "shard_credited", "payment_method",
]
GACHA_PULL_COLUMNS = [
    "id", "player_id", "gacha_pool_id", "pull_date", "pull_source",
    "shard_cost", "result_rarity", "result_character_name",
]
EVENT_PARTICIPATION_COLUMNS = [
    "id", "player_id", "live_ops_event_id", "participation_date",
    "shard_spent_during_event", "completed_flag",
]


def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_channel_partner = gen_channel_partners()
    df_channel_partner.write_csv(DATA_DIR / "01_channel_partner.tsv", separator="\t")

    df_region_price_tier = gen_region_price_tiers()
    df_region_price_tier.write_csv(DATA_DIR / "02_region_price_tier.tsv", separator="\t")

    df_iap_product = gen_iap_products()
    df_iap_product.write_csv(DATA_DIR / "03_iap_product.tsv", separator="\t")

    df_gacha_pool = gen_gacha_pools()
    df_gacha_pool.write_csv(DATA_DIR / "04_gacha_pool.tsv", separator="\t")

    df_discount_code = gen_discount_codes()
    df_discount_code.write_csv(DATA_DIR / "05_discount_code.tsv", separator="\t")

    df_live_ops_event = gen_live_ops_events()
    df_live_ops_event.write_csv(DATA_DIR / "06_live_ops_event.tsv", separator="\t")

    region_rows = df_region_price_tier.to_dicts()
    country_code_by_region_id = {r["id"]: r["country_code"] for r in region_rows}
    region_index_by_id = {r["id"]: r["price_index"] for r in region_rows}

    players = gen_players(region_rows)
    players_by_id = {p["id"]: p for p in players}

    events = df_live_ops_event.to_dicts()
    stacked_events = [e for e in events if e["is_stacked_event"]]

    event_participations = gen_event_participation(players, events)

    channel_rows = df_channel_partner.to_dicts()
    channel_ids = {
        "apple": next(r["id"] for r in channel_rows if r["channel_name"] == "Apple App Store (IAP)"),
        "google": next(r["id"] for r in channel_rows if r["channel_name"] == "Google Play (IAP)"),
        "official_web": next(r["id"] for r in channel_rows if r["channel_name"] == "Official Web Store (Direct)"),
        "sea_partner": next(r["id"] for r in channel_rows if r["channel_name"] == "SEA Regional Billing Partner"),
        "latam_partner": next(r["id"] for r in channel_rows if r["channel_name"] == "LatAm Regional Billing Partner"),
        "unauthorized": [r["id"] for r in channel_rows if r["channel_type"] == "third_party_agent" and not r["is_authorized"]],
    }

    iap_products = df_iap_product.to_dicts()
    transactions = gen_iap_transactions(
        players, iap_products, channel_ids, country_code_by_region_id, region_index_by_id, stacked_events,
    )

    discount_codes = df_discount_code.to_dicts()
    apply_discount_codes(transactions, players_by_id, discount_codes, country_code_by_region_id)

    gacha_pools_runtime = build_gacha_pool_runtime(df_gacha_pool)
    gacha_pulls = gen_gacha_pull_logs(players, gacha_pools_runtime)

    refund_events = gen_refund_chargeback_events(transactions, players_by_id)

    transactions_by_player: dict[int, list[dict]] = {}
    for t in transactions:
        transactions_by_player.setdefault(t["player_id"], []).append(t)
    support_tickets = gen_support_tickets(players, transactions_by_player)

    finalize_players(players, transactions, gacha_pulls, event_participations, support_tickets)

    df_player = pl.DataFrame([{k: p[k] for k in PLAYER_COLUMNS} for p in players])
    df_player.write_csv(DATA_DIR / "07_player.tsv", separator="\t")

    df_transaction = pl.DataFrame([{k: t[k] for k in TRANSACTION_COLUMNS} for t in transactions])
    df_transaction.write_csv(DATA_DIR / "08_iap_transaction.tsv", separator="\t")

    df_gacha_pull = pl.DataFrame([{k: g[k] for k in GACHA_PULL_COLUMNS} for g in gacha_pulls])
    df_gacha_pull.write_csv(DATA_DIR / "09_gacha_pull_log.tsv", separator="\t")

    df_event_participation = pl.DataFrame([{k: e[k] for k in EVENT_PARTICIPATION_COLUMNS} for e in event_participations])
    df_event_participation.write_csv(DATA_DIR / "10_event_participation.tsv", separator="\t")

    df_refund = pl.DataFrame(refund_events)
    df_refund.write_csv(DATA_DIR / "11_refund_chargeback_risk_event.tsv", separator="\t")

    df_support = pl.DataFrame(support_tickets)
    df_support.write_csv(DATA_DIR / "12_support_ticket.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order: list[tuple[str, Table]] = [
        ("01_channel_partner", ChannelPartner.__table__),
        ("02_region_price_tier", RegionPriceTier.__table__),
        ("03_iap_product", IapProduct.__table__),
        ("04_gacha_pool", GachaPool.__table__),
        ("05_discount_code", DiscountCode.__table__),
        ("06_live_ops_event", LiveOpsEvent.__table__),
        ("07_player", Player.__table__),
        ("08_iap_transaction", IapTransaction.__table__),
        ("09_gacha_pull_log", GachaPullLog.__table__),
        ("10_event_participation", EventParticipation.__table__),
        ("11_refund_chargeback_risk_event", RefundChargebackRiskEvent.__table__),
        ("12_support_ticket", SupportTicket.__table__),
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


def main() -> None:
    print("Starting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("All done!")


if __name__ == "__main__":
    main()
