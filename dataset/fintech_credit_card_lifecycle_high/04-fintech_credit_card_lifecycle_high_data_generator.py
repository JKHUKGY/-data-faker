"""
Fintech — Consumer Credit Card Full Lifecycle fake data generator
Complexity: High

Business background:
Keystone Card Company is a data-driven consumer credit card issuer headquartered in
Irvine, CA. It issues its own cards, underwrites its own risk, absorbs its own losses,
and makes money on "interest + interchange + fees - rewards - charge-off".
This dataset simulates about 24 months (2024-07 to 2026-06) of the full card lifecycle:
marketing (campaign / prescreen) -> application -> underwriting ->
account opening -> monthly statement -> transaction -> rewards ->
credit_line_change -> delinquency/charge_off -> attrition.

The dataset deliberately injects the following 8 business traps (each maps to a
group of queries in the 03 SQL document):

1. Underwriting model miscalibration (ROC / confusion matrix on underwriting_score):
   underwriting_score (0-999, higher = safer) predicts charge-off reasonably well
   overall (AUC ~0.70), but within credit_band = D (Subprime), the score is almost
   unrelated to actual charge-off (AUC ~0.50).
   => Computing AUC by DS segment reveals the model breaks down in the D segment.

2. Marketing channel adverse selection:
   The affiliate_partner channel has a high approval rate and low contact cost
   (2.00) vs digital channels (3.2-4.5), but the accounts it brings in have a
   charge-off rate of about 12.6%, roughly 3.2x that of prescreen_mail (~3.9%)
   and also higher than the overall portfolio (~6.9%). "Cheap acquisition cost
   != good customer quality."

3. Rewards-card transactors are unprofitable (transactor unprofitability):
   On premium cards (Travel / Venture Premium, rewards 2.0%-2.5%), transactors
   (who pay their statement in full every month) generate interchange (~1.8%)
   that is eaten up by rewards, leaving net per-account contribution negative;
   this is subsidized by revolver interest income.

4. 0% APR / balance-transfer promo cliff (promo APR cliff):
   BT-promo accounts (is_promo_apr=True, 12 months at 0% APR) have low DPD30+
   during the promo period (~2-5%); once the promo expires (around cycle_month
   12-14) and the rate reverts to base_apr, DPD30+ jumps to ~13%
   (over the same period, non-promo accounts' DPD30+ actually drops to ~1%).

5. Credit Line Increase (CLI) adverse selection:
   Accounts that received a CLI while already a "high-utilization revolver"
   (pre-CLI utilization > 70%) have a charge-off rate of ~10%, roughly 3x that
   of accounts with pre-CLI utilization <= 70% (~3.4%). The bank thinks it is
   rewarding good customers, but is actually piling on risk.

6. Signup-bonus hunters / negative LTV (bonus churner):
   In challenger campaigns with a large signup bonus, about 15% of accounts are
   bonus churners: they hit the min-spend requirement to earn the bonus, then
   close the card within 6-9 months; lifetime per-account contribution is
   negative (bonus > revenue).

7. Vintage loss-curve deterioration (vintage deterioration):
   Underwriting loosens over time (approval rate rises from ~55% to ~60%, booked
   FICO slides from ~722 to ~694); the charge-off rate at month_on_book<=6 for
   recent origination vintages rises from ~1.2% in 2024Q3 to ~3.5% in 2025Q4.

8. Per-account P&L across the product ladder (product ladder profitability):
   The six products (Secured -> Student -> Cashback -> Cashback Plus -> Travel ->
   Venture Premium) have very different unit economics: near-prime cashback
   revolvers are the profit engine, while premium travel-card transactor
   segments are near break-even or even loss-making. Full P&L = interest +
   interchange + fees - rewards - loss.

The above traps are injected via deliberately designed correlated distributions.
The corresponding SQL queries live in
03-fintech_credit_card_lifecycle_high_sql_queries-cn.md, used to surface these traps.
For a plain-language walkthrough of the terminology and business motivation, see
05-fintech_credit_card_lifecycle_high_analytics_primer-cn.md.
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
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ---------------------------------------------------------------------------
# Section 3. Configuration constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "fintech_credit_card_lifecycle_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date: end of quarter. All semantics for "today / current snapshot /
# months_on_book" are anchored to this date, independent of the system's current time.
# Anywhere the SQL queries need "today", they use the same literal '2026-06-30'.
REFERENCE_DATE = date(2026, 6, 30)

# Earliest account open date in the observation window. The oldest accounts are
# about 24 months old as of REFERENCE_DATE.
EARLIEST_OPEN_DATE = date(2024, 7, 1)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Section 4. Business Calibration Constants
# Every weight / probability / threshold is documented with why it has this
# value, and which trap it serves.
# ---------------------------------------------------------------------------

# Target scale (order of magnitude). Tune these few numbers to scale the whole dataset.
N_PRESCREEN_OFFERS = 20000   # prescreen mail volume; response ~5% -> ~1000 converted to applications
N_APPLICATIONS = 18000       # total applications (prescreen response + organic + branch)
TARGET_ACCOUNTS = 9000       # approved and activated accounts on the books (statement is the main row source)

# Pool of California cities (the company only operates in California, avoiding cross-state noise).
CA_CITIES = [
    "Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno",
    "Sacramento", "Long Beach", "Oakland", "Irvine", "Anaheim",
    "Bakersfield", "Riverside", "Santa Ana", "Chula Vista", "Fremont",
    "San Bernardino", "Modesto", "Fontana", "Oxnard", "Huntington Beach",
]

# --- credit_band: FICO segments -> pricing assumptions & baseline charge-off ---
# implied_loss is the "annualized loss rate assumed by the pricing model" (the cost
# assumption used at underwriting/pricing time);
# base_chargeoff is the "baseline observed-window charge-off probability" actually
# injected by the generator (before applying channel/vintage/CLI multipliers etc.).
# Except for band D, the two are broadly aligned (band-level pricing is roughly correct);
# the real trap (trap 1) is that within band D, the score cannot rank-order risk.
CREDIT_BANDS = [
    # code, name,            fico_min, fico_max, implied_loss, assigned_apr, base_chargeoff
    # base_chargeoff is the "underwriting-period charge-off probability baseline before
    # applying channel/vintage/CLI multipliers"; the observed window truncates by account
    # age, so the actually booked pool charge-off rate is roughly half of the baseline
    # (recent vintages haven't yet run through their full charge-off window).
    ("A", "Superprime",      780, 850, 0.015, 14.99, 0.022),
    ("B", "Prime",           720, 779, 0.030, 18.99, 0.048),
    ("C", "Near-Prime",      660, 719, 0.060, 22.99, 0.095),
    ("D", "Subprime",        600, 659, 0.100, 26.99, 0.160),
    ("E", "Deep-Subprime",   300, 599, 0.150, 29.99, 0.225),
]

# --- Channels: acquisition cost & adverse-selection multiplier (trap 2) ---
# chargeoff_mult is multiplied onto the account's pd. affiliate_partner is cheap and has
# high response, but its bad-debt rate is 2x -> adverse selection.
MARKETING_CHANNELS = [
    # name,              type,       cost_per_contact, chargeoff_mult, approval_lift
    ("direct_mail",      "outbound", 0.85,  0.80, 0.00),
    ("prescreen_mail",   "outbound", 1.10,  0.68, 0.05),   # pre-vetted, best quality, lowest bad debt
    ("digital_display",  "digital",  4.50,  1.15, 0.00),
    ("affiliate_partner","partner",  2.00,  2.30, 0.10),   # trap 2: cheap + high approval, highest bad debt ~2x+
    ("social",           "digital",  3.20,  1.45, 0.05),
    ("branch_referral",  "branch",   6.00,  0.72, 0.02),   # branch referral, best quality but most expensive to acquire
]

# --- Product ladder (traps 3 & 8): higher rewards + better-tier customers -> more transactors -> interchange eaten by rewards ---
CARD_PRODUCTS = [
    # name,                    tier,        annual_fee, base_apr, rewards_rate, rewards_type, target_band, transactor_rate
    ("Keystone Secured",       "secured",     0.0,  26.99, 0.000, "none",     "E", 0.10),
    ("Keystone Student",       "student",     0.0,  23.99, 0.010, "cashback", "C", 0.35),
    ("Keystone Cashback",      "cashback",    0.0,  22.99, 0.015, "cashback", "C", 0.40),
    ("Keystone Cashback Plus", "cashback",   95.0,  21.99, 0.020, "cashback", "B", 0.55),
    ("Keystone Travel",        "travel",     95.0,  20.99, 0.020, "miles",    "B", 0.70),
    ("Keystone Venture Premium","premium",  395.0,  19.99, 0.025, "miles",    "A", 0.82),  # main battleground for trap 3
]

# transactor (pays in full every month): interchange income - rewards cost is often
# negative, only the annual fee is pure profit;
# revolver (carries a balance): profits from APR interest, the actual profit engine.
# This is the economic root cause of traps 3/8.
INTERCHANGE_RATE = 0.018   # average interchange rate (as % of spend), varies around this by MCC.

# --- Charge-off timing distribution: concentrated at month_on_book 4-15, peak ~7. Supports early-warning & vintage curve analysis (trap 7) ---
CHARGEOFF_MOB_MIN = 4
CHARGEOFF_MOB_PEAK = 7
CHARGEOFF_MOB_MAX = 16

# --- Vintage deterioration (trap 7): pd multiplier by open-quarter, looser underwriting recently -> larger multiplier ---
VINTAGE_PD_MULT = {
    "2024Q3": 0.70, "2024Q4": 0.78,
    "2025Q1": 0.90, "2025Q2": 1.00,
    "2025Q3": 1.22, "2025Q4": 1.45,
    "2026Q1": 1.55, "2026Q2": 1.65,
}
# Underwriting threshold drifts downward over time (approval loosening): the FICO
# cutoff is high early on and low recently -> booked FICO trends down.
def approval_fico_cutoff(app_dt: date) -> int:
    """Return the FICO approval floor for a given application date. ~640 in H2 2024, linearly declining to ~605 by mid-2026 (underwriting loosening)."""
    months_from_start = (app_dt.year - 2024) * 12 + (app_dt.month - 7)
    cutoff = 640 - int(months_from_start * 1.5)   # drifts down ~1.5 points per month
    return max(600, cutoff)

# --- CLI adverse selection (trap 5) ---
CLI_ELIGIBLE_RATE = 0.40         # about 40% of accounts get a CLI at some point in their lifecycle
CLI_HIGH_UTIL_THRESHOLD = 0.70   # definition of "high utilization": pre-CLI utilization > 70%
CLI_HIGH_UTIL_PD_MULT = 2.4      # pd multiplier for high-utilization CLI accounts -> ~2.5x charge-off

# --- bonus churner (trap 6) ---
BONUS_CHURN_RATE_HIGH_BONUS = 0.15   # about 15% of accounts in large-bonus campaigns are bonus hunters
BONUS_CHURN_CLOSE_MOB = (6, 9)       # close the card 6-9 months after earning the bonus

# --- Relationship between underwriting_score and charge-off (trap 1) ---
# Non-D bands: pd = base * (SCORE_PD_HI - SCORE_PD_SLOPE * score/999), higher score -> lower pd (rank-orderable).
# D band:      pd = base (constant), score is independently random -> segment AUC ~0.5, model breaks down.
SCORE_PD_HI = 1.70
SCORE_PD_SLOPE = 1.40

# Account activation rate (approved -> actually opened and used).
ACTIVATION_RATE = 0.86
# Base annualized probability of voluntary attrition (not charge-off, not bonus churn).
VOLUNTARY_ATTRITION_BASE = 0.10

# MCC merchant categories (interchange rates vary).
MCC_CATEGORIES = [
    # mcc_code, name,               interchange_rate, spend_weight
    ("5411", "Grocery Stores",       0.0155, 0.16),
    ("5541", "Gas Stations",         0.0150, 0.10),
    ("5812", "Restaurants",          0.0195, 0.15),
    ("5814", "Fast Food",            0.0185, 0.08),
    ("5732", "Electronics",          0.0205, 0.05),
    ("5311", "Department Stores",    0.0190, 0.07),
    ("4511", "Airlines",             0.0210, 0.05),
    ("7011", "Hotels & Lodging",     0.0210, 0.04),
    ("5999", "Online Retail",        0.0200, 0.14),
    ("5912", "Drug Stores",          0.0160, 0.05),
    ("4900", "Utilities",            0.0130, 0.05),
    ("7999", "Entertainment",        0.0195, 0.06),
]

DECLINE_REASONS = [
    "Low FICO score",
    "High debt-to-income ratio",
    "Insufficient income",
    "Thin credit file",
    "Recent delinquency on bureau",
    "Failed identity verification",
]

ATTRITION_REASONS = {
    "VOLUNTARY": ["bonus_churn", "rate_shopping", "inactivity", "dissatisfaction", "product_upgrade"],
    "INVOLUNTARY": ["charge_off"],
}


# ---------------------------------------------------------------------------
# Section 5. ORM models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class CreditBand(Base):
    """FICO risk segment (A-E). The base dimension for underwriting pricing, and also the grouping key for the trap-1 segmented AUC."""

    __tablename__ = "credit_band"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    band_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    band_name: Mapped[str] = mapped_column(String(40), nullable=False)
    fico_min: Mapped[int] = mapped_column(Integer, nullable=False)
    fico_max: Mapped[int] = mapped_column(Integer, nullable=False)
    implied_annual_loss_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    assigned_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class CardProduct(Base):
    """Credit card product ladder. From the entry-level secured card up to Venture Premium, rewards / annual fee / APR all differ (traps 3/8)."""

    __tablename__ = "card_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    product_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_fee_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    base_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rewards_rate_pct: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    rewards_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_band_code: Mapped[str] = mapped_column(String(2), nullable=False)


class MarketingChannel(Base):
    """Acquisition channel. cost_per_contact is the denominator for acquisition cost, and also the star of the trap-2 adverse selection (affiliate)."""

    __tablename__ = "marketing_channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_per_contact_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class MccCategory(Base):
    """Merchant category (MCC). Determines the interchange rate and spend-mix analysis."""

    __tablename__ = "mcc_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mcc_code: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    category_name: Mapped[str] = mapped_column(String(40), nullable=False)
    interchange_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)


class Campaign(Base):
    """A single concrete marketing push. Champion/challenger pairs, some carrying a large signup bonus or a 0% BT promo (traps 4/6)."""

    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_name: Mapped[str] = mapped_column(String(80), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("marketing_channel.id"), nullable=False)
    card_product_id: Mapped[int] = mapped_column(ForeignKey("card_product.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_champion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    offer_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    promo_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    promo_duration_months: Mapped[int] = mapped_column(Integer, nullable=True)
    signup_bonus_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    min_spend_for_bonus_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    budget_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class Applicant(Base):
    """Applicant (a natural person). Includes the financial profile needed for underwriting. All are California residents."""

    __tablename__ = "applicant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False)
    last_name: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    employment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_income_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class PrescreenOffer(Base):
    """Prescreen mailed offer. Each row = one mailed pre-approval letter, with a response-model score and the actual response (the DS response-model confusion matrix)."""

    __tablename__ = "prescreen_offer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False)
    last_name: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    fico_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    response_model_score: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_response_prob: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    mailed_date: Mapped[date] = mapped_column(Date, nullable=False)
    responded: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Application(Base):
    """Credit card application. The underwriting decision (approve/decline), risk score underwriting_score, and assigned APR & limit are all here."""

    __tablename__ = "application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicant.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=True)
    card_product_id: Mapped[int] = mapped_column(ForeignKey("card_product.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("marketing_channel.id"), nullable=False)
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    fico_at_application: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    credit_band_id: Mapped[int] = mapped_column(ForeignKey("credit_band.id"), nullable=False)
    underwriting_score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    decline_reason: Mapped[str] = mapped_column(String(60), nullable=True)
    approved_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    approved_credit_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)


class Account(Base):
    """On-book credit card account. Becomes an account once approved and activated; the parent table for statement / transaction / all event types."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"), nullable=False)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicant.id"), nullable=False)
    card_product_id: Mapped[int] = mapped_column(ForeignKey("card_product.id"), nullable=False)
    credit_band_id: Mapped[int] = mapped_column(ForeignKey("credit_band.id"), nullable=False)
    acquisition_channel_id: Mapped[int] = mapped_column(ForeignKey("marketing_channel.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=True)
    open_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    purchase_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_promo_apr: Mapped[bool] = mapped_column(Boolean, nullable=False)
    promo_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    promo_end_date: Mapped[date] = mapped_column(Date, nullable=True)
    behavior_segment: Mapped[str] = mapped_column(String(12), nullable=False)
    underwriting_score: Mapped[int] = mapped_column(Integer, nullable=False)
    signup_bonus_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    account_status: Mapped[str] = mapped_column(String(14), nullable=False)
    open_vintage: Mapped[str] = mapped_column(String(6), nullable=False)
    closed_date: Mapped[date] = mapped_column(Date, nullable=True)
    months_on_book: Mapped[int] = mapped_column(Integer, nullable=False)


class Statement(Base):
    """Monthly statement. Each row = the complete economic picture of one account for one billing cycle (balance/spend/payment/interest/fees/interchange/rewards/DPD)."""

    __tablename__ = "statement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_balance_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_volume_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_amount_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_charged_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fees_charged_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    interchange_revenue_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    rewards_earned_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    minimum_due_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    credit_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    utilization_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    days_past_due: Mapped[int] = mapped_column(Integer, nullable=False)
    dpd_bucket: Mapped[str] = mapped_column(String(12), nullable=False)
    is_promo_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Transaction(Base):
    """Sampled card-swipe transaction. Not every real purchase is stored; only a sample is kept for MCC / interchange / fraud structure analysis."""

    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    mcc_category_id: Mapped[int] = mapped_column(ForeignKey("mcc_category.id"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    interchange_revenue_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    is_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RewardsLedger(Base):
    """Rewards ledger (discrete events). Only records one-off actions such as signup bonus / redemption / clawback; the monthly accrued rewards live in statement."""

    __tablename__ = "rewards_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(12), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(80), nullable=False)


class CreditLineChange(Base):
    """Credit line adjustment event (CLI increase / CLD decrease). pre_change_utilization is the key field for the trap-5 adverse selection."""

    __tablename__ = "credit_line_change"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    change_type: Mapped[str] = mapped_column(String(4), nullable=False)
    old_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    new_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    pre_change_utilization_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    initiated_by: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(60), nullable=False)


class ChargeOff(Base):
    """Charge-off record. An account becomes charged off after rolling delinquent to 180 days; records the charged-off balance, recovery amount, and account age."""

    __tablename__ = "charge_off"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    charge_off_date: Mapped[date] = mapped_column(Date, nullable=False)
    charged_off_balance_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recovery_amount_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recovery_date: Mapped[date] = mapped_column(Date, nullable=True)
    months_on_book_at_chargeoff: Mapped[int] = mapped_column(Integer, nullable=False)


class AttritionEvent(Base):
    """Card closure record. VOLUNTARY (customer-initiated) or INVOLUNTARY (company-closed); close_reason includes bonus_churn (trap 6)."""

    __tablename__ = "attrition_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    close_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_type: Mapped[str] = mapped_column(String(12), nullable=False)
    close_reason: Mapped[str] = mapped_column(String(20), nullable=False)
    months_on_book_at_close: Mapped[int] = mapped_column(Integer, nullable=False)


class FraudCase(Base):
    """Fraud case (lightweight). Disposition record for transaction fraud; this dataset does not go deep on fraud (there is a dedicated fraud/AML dataset for that)."""

    __tablename__ = "fraud_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    fraud_type: Mapped[str] = mapped_column(String(30), nullable=False)
    gross_loss_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    net_loss_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    resolution: Mapped[str] = mapped_column(String(20), nullable=False)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def vintage_of(d: date) -> str:
    """Map a date to a 'YYYYQn' vintage label."""
    q = (d.month - 1) // 3 + 1
    return f"{d.year}Q{q}"


def add_months(d: date, n: int) -> date:
    """Add n months to a date (day is clamped to a valid value within that month)."""
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def band_from_fico(fico: int) -> int:
    """FICO score -> credit_band id (1-based, matching the CREDIT_BANDS order)."""
    for idx, (_code, _name, lo, hi, *_rest) in enumerate(CREDIT_BANDS, start=1):
        if lo <= fico <= hi:
            return idx
    return len(CREDIT_BANDS)  # fallback: drop into the lowest band


def chargeoff_mob() -> int:
    """The month_on_book at which charge-off occurs, triangular distribution, peak ~7."""
    return int(round(random.triangular(CHARGEOFF_MOB_MIN, CHARGEOFF_MOB_MAX, CHARGEOFF_MOB_PEAK)))


# ---------------------------------------------------------------------------
# Section 6. Generator functions (topological order)
# ---------------------------------------------------------------------------

def gen_credit_bands() -> pl.DataFrame:
    rows = []
    for idx, (code, name, lo, hi, implied, apr, _base) in enumerate(CREDIT_BANDS, start=1):
        rows.append({
            "id": idx, "band_code": code, "band_name": name,
            "fico_min": lo, "fico_max": hi,
            "implied_annual_loss_rate_pct": round(implied * 100, 2),
            "assigned_apr_pct": apr,
        })
    return pl.DataFrame(rows)


def gen_card_products() -> pl.DataFrame:
    rows = []
    for idx, (name, tier, fee, apr, rr, rtype, tband, _tx) in enumerate(CARD_PRODUCTS, start=1):
        rows.append({
            "id": idx, "product_name": name, "product_tier": tier,
            "annual_fee_usd": fee, "base_apr_pct": apr,
            "rewards_rate_pct": round(rr, 3), "rewards_type": rtype,
            "target_band_code": tband,
        })
    return pl.DataFrame(rows)


def gen_marketing_channels() -> pl.DataFrame:
    rows = []
    for idx, (name, ctype, cpc, _m, _a) in enumerate(MARKETING_CHANNELS, start=1):
        rows.append({
            "id": idx, "channel_name": name, "channel_type": ctype,
            "cost_per_contact_usd": cpc,
        })
    return pl.DataFrame(rows)


def gen_mcc_categories() -> pl.DataFrame:
    rows = []
    for idx, (code, name, ic, _w) in enumerate(MCC_CATEGORIES, start=1):
        rows.append({
            "id": idx, "mcc_code": code, "category_name": name,
            "interchange_rate_pct": round(ic, 4),
        })
    return pl.DataFrame(rows)


def gen_campaigns() -> pl.DataFrame:
    """About 24 campaigns. Champion/challenger pairs; some challengers carry a large bonus (trap 6) or a 0% BT promo (trap 4)."""
    rows = []
    cid = 1
    channel_names = [c[0] for c in MARKETING_CHANNELS]
    quarters = ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    quarter_start = {
        "2024Q3": date(2024, 7, 1), "2024Q4": date(2024, 10, 1),
        "2025Q1": date(2025, 1, 1), "2025Q2": date(2025, 4, 1),
        "2025Q3": date(2025, 7, 1), "2025Q4": date(2025, 10, 1),
        "2026Q1": date(2026, 1, 1), "2026Q2": date(2026, 4, 1),
    }
    slot_counter = 0
    for q_idx, q in enumerate(quarters):
        start = quarter_start[q]
        end = add_months(start, 3) - timedelta(days=1)
        # 3 campaigns per quarter: 1 champion (steady state), 2 challengers (testing new offers).
        for slot in range(3):
            is_champion = slot == 0
            # Channels/products are round-robined so every channel spans all quarters
            # (avoids confounding channel with vintage).
            channel_id = (slot_counter % len(MARKETING_CHANNELS)) + 1
            product_id = ((slot_counter * 5) % len(CARD_PRODUCTS)) + 1
            slot_counter += 1
            product = CARD_PRODUCTS[product_id - 1]
            base_apr = product[3]
            # Among challengers, some run a large bonus, some run a 0% balance-transfer promo.
            is_bonus_offer = (not is_champion) and slot == 1
            is_bt_offer = (not is_champion) and slot == 2
            if is_bonus_offer:
                signup_bonus = random.choice([200.0, 250.0, 300.0])
                min_spend = random.choice([1500.0, 3000.0])
                promo_apr = None
                promo_months = None
                label = "BonusBoost"
            elif is_bt_offer:
                signup_bonus = 0.0
                min_spend = 0.0
                promo_apr = 0.0
                promo_months = 12   # 0% APR for 12 months, reverts to base_apr at expiry -> trap 4
                label = "0pct-BalanceTransfer"
            else:
                signup_bonus = random.choice([0.0, 100.0, 150.0])
                min_spend = 500.0 if signup_bonus > 0 else 0.0
                promo_apr = None
                promo_months = None
                label = "Champion" if is_champion else "Standard"
            rows.append({
                "id": cid,
                "campaign_name": f"{q}-{product[0].split()[-1]}-{label}",
                "channel_id": channel_id,
                "card_product_id": product_id,
                "start_date": start,
                "end_date": end,
                "is_champion": is_champion,
                "offer_apr_pct": base_apr,
                "promo_apr_pct": promo_apr,
                "promo_duration_months": promo_months,
                "signup_bonus_usd": signup_bonus,
                "min_spend_for_bonus_usd": min_spend,
                "budget_usd": float(random.randint(40, 200) * 1000),
            })
            cid += 1
    return pl.DataFrame(rows)


def gen_prescreen_offers(campaigns: pl.DataFrame) -> pl.DataFrame:
    """Prescreen mailing. Only campaigns on an outbound (direct_mail / prescreen_mail) channel send pre-approval letters."""
    outbound_channel_ids = {1, 2}  # direct_mail, prescreen_mail
    elig = campaigns.filter(pl.col("channel_id").is_in(list(outbound_channel_ids)))
    if elig.height == 0:
        elig = campaigns
    camp_ids = elig["id"].to_list()
    camp_start = dict(zip(campaigns["id"].to_list(), campaigns["start_date"].to_list()))
    rows = []
    for i in range(1, N_PRESCREEN_OFFERS + 1):
        cid = random.choice(camp_ids)
        fico = int(min(830, max(560, random.gauss(700, 55))))  # prescreen population skews better quality
        # Response model score (0-999): correlated with actual response but imperfect (AUC ~0.65).
        latent = random.random()
        response_score = int(min(999, max(1, latent * 999 + random.gauss(0, 80))))
        pred_prob = round(0.02 + 0.10 * (response_score / 999), 4)
        # Actual response: probability rises monotonically with the score, plus noise.
        responded = random.random() < (0.015 + 0.075 * (response_score / 999))
        start = camp_start[cid]
        mailed = start + timedelta(days=random.randint(0, 60))
        rows.append({
            "id": i, "campaign_id": cid,
            "first_name": fake.first_name(), "last_name": fake.last_name(),
            "city": random.choice(CA_CITIES), "state": "CA",
            "fico_estimate": fico,
            "response_model_score": response_score,
            "predicted_response_prob": pred_prob,
            "mailed_date": mailed,
            "responded": responded,
        })
    return pl.DataFrame(rows)


def gen_applicants_and_applications(campaigns: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Generate applicants and applications. Underwriting decisions follow a vintage-drifting FICO cutoff (trap 7); underwriting_score encodes risk (trap 1)."""
    applicants = []
    applications = []
    channel_names = [c[0] for c in MARKETING_CHANNELS]
    channel_approval_lift = {i + 1: MARKETING_CHANNELS[i][4] for i in range(len(MARKETING_CHANNELS))}
    camp_rows = campaigns.to_dicts()
    camp_by_id = {c["id"]: c for c in camp_rows}
    camp_ids = list(camp_by_id.keys())

    for i in range(1, N_APPLICATIONS + 1):
        # Application date: uniformly distributed within the observation window (leaving
        # at least 2 weeks for the decision).
        span_days = (REFERENCE_DATE - timedelta(days=14) - EARLIEST_OPEN_DATE).days
        app_dt = EARLIEST_OPEN_DATE + timedelta(days=random.randint(0, span_days))

        # About 70% of applications are attributed to a campaign live at the time; the
        # rest count as organic/branch traffic.
        active_camps = [c for c in camp_ids
                        if camp_by_id[c]["start_date"] <= app_dt <= camp_by_id[c]["end_date"]]
        if active_camps and random.random() < 0.70:
            cid = random.choice(active_camps)
            camp = camp_by_id[cid]
            channel_id = camp["channel_id"]
            product_id = camp["card_product_id"]
        else:
            cid = None
            channel_id = random.randint(1, len(MARKETING_CHANNELS))
            product_id = random.randint(1, len(CARD_PRODUCTS))

        # FICO: drifts slightly down with vintage (underwriting loosening, trap 7).
        # Recent means are lower.
        months_from_start = (app_dt.year - 2024) * 12 + (app_dt.month - 7)
        fico_mean = 700 - months_from_start * 1.2
        fico = int(min(840, max(520, random.gauss(fico_mean, 60))))
        band_id = band_from_fico(fico)

        # Income and age
        age = random.randint(21, 70)
        income = round(max(18000, random.gauss(72000, 32000)), 2)
        requested = float(random.choice([1000, 2000, 3000, 5000, 7500, 10000, 15000]))

        # underwriting_score (0-999, higher = safer) -- the vehicle for trap 1.
        band_code = CREDIT_BANDS[band_id - 1][0]
        if band_code == "D":
            # Band D: score is decoupled from risk (independently random) -> segment AUC ~0.5, model breaks down.
            uw_score = random.randint(1, 999)
        else:
            # Non-D bands: score encodes a latent safety level, inversely correlated
            # with later charge-off -> rank-orderable.
            safety = random.random()
            uw_score = int(min(999, max(1, safety * 999 + random.gauss(0, 55))))

        # Underwriting decision: FICO >= the cutoff that drifts down over time, plus
        # channel lift and randomness.
        cutoff = approval_fico_cutoff(app_dt)
        approve_prob = 0.32 + 0.45 * (fico - cutoff) / 120.0 + channel_approval_lift[channel_id]
        approve_prob = min(0.95, max(0.03, approve_prob))
        approved = random.random() < approve_prob
        decision_dt = app_dt + timedelta(days=random.randint(1, 12))

        applicants.append({
            "id": i,
            "first_name": fake.first_name(), "last_name": fake.last_name(),
            "email": fake.email(), "city": random.choice(CA_CITIES), "state": "CA",
            "zip_code": fake.zipcode_in_state("CA") if hasattr(fake, "zipcode_in_state") else fake.postcode(),
            "age": age, "employment_status": random.choice(
                ["employed", "self_employed", "employed", "employed", "retired", "student"]),
            "annual_income_usd": income,
        })

        if approved:
            apr = CREDIT_BANDS[band_id - 1][5]
            # Credit limit: correlated with income and band.
            band_limit_factor = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.32, "E": 0.18}[band_code]
            limit = round(min(requested * random.uniform(0.7, 1.3),
                              max(500, income * 0.28 * band_limit_factor)), -1)
            limit = float(max(500, min(35000, limit)))
            decision = "APPROVED"
            decline_reason = None
        else:
            apr = None
            limit = None
            decision = "DECLINED"
            decline_reason = random.choice(DECLINE_REASONS)

        applications.append({
            "id": i, "applicant_id": i, "campaign_id": cid, "card_product_id": product_id,
            "channel_id": channel_id, "application_date": app_dt,
            "fico_at_application": fico, "requested_limit_usd": requested,
            "credit_band_id": band_id, "underwriting_score": uw_score,
            "decision": decision, "decline_reason": decline_reason,
            "approved_apr_pct": apr, "approved_credit_limit_usd": limit,
            "decision_date": decision_dt,
        })

    return pl.DataFrame(applicants), pl.DataFrame(applications)


def gen_accounts_and_lifecycle(
    applications: pl.DataFrame,
    campaigns: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """Core simulation: approved -> activated into an account, generating monthly statements plus charge_off / attrition / CLI / rewards / transaction / fraud."""

    camp_by_id = {c["id"]: c for c in campaigns.to_dicts()}
    approved = applications.filter(pl.col("decision") == "APPROVED").to_dicts()
    random.shuffle(approved)

    # Activation: only a subset of approved applications become on-book accounts, keeping
    # the total near TARGET_ACCOUNTS.
    accounts = []
    statements = []
    transactions = []
    rewards = []
    cli_changes = []
    chargeoffs = []
    attritions = []
    frauds = []

    acct_id = 0
    stmt_id = 0
    txn_id = 0
    rl_id = 0
    cli_id = 0
    co_id = 0
    at_id = 0
    fr_id = 0

    mcc_ids = list(range(1, len(MCC_CATEGORIES) + 1))
    mcc_weights = [m[3] for m in MCC_CATEGORIES]
    mcc_ic = {i + 1: MCC_CATEGORIES[i][2] for i in range(len(MCC_CATEGORIES))}

    for app in approved:
        if acct_id >= TARGET_ACCOUNTS:
            break
        if random.random() > ACTIVATION_RATE:
            continue

        # open_date fix (the old logic hard-pinned the open_date of accounts near the
        # end of the window to a single day, violating decision_date >= open_date, which
        # breaks ER §5.1's invariant, and produced a fake spike in Q20).
        # Between the decision date and REFERENCE_DATE there must be room for the minimum
        # 3-day "approval -> card opening" gap; otherwise this application is not
        # activated (skipped). When satisfied, open_gap is drawn from [3, min(20, days
        # remaining)], guaranteeing decision_date < open_date <= REFERENCE_DATE - 1 day
        # for every account, without piling up on a single day.
        max_open_gap = (REFERENCE_DATE - app["decision_date"]).days - 1
        if max_open_gap < 3:
            continue
        open_gap = random.randint(3, min(20, max_open_gap))

        acct_id += 1
        product = CARD_PRODUCTS[app["card_product_id"] - 1]
        band_code = CREDIT_BANDS[app["credit_band_id"] - 1][0]
        base_co = CREDIT_BANDS[app["credit_band_id"] - 1][6]
        channel_id = app["channel_id"]
        channel_mult = MARKETING_CHANNELS[channel_id - 1][3]
        camp = camp_by_id.get(app["campaign_id"]) if app["campaign_id"] else None

        open_dt = app["decision_date"] + timedelta(days=open_gap)
        vintage = vintage_of(open_dt)
        limit = float(app["approved_credit_limit_usd"])
        base_apr = float(app["approved_apr_pct"])
        uw_score = app["underwriting_score"]

        # Promo: if the campaign is a 0% BT promo, the account carries the promo (trap 4).
        is_promo = bool(camp and camp["promo_apr_pct"] is not None)
        promo_apr = 0.0 if is_promo else None
        promo_end = add_months(open_dt, camp["promo_duration_months"]) if is_promo else None

        # Behavioral segmentation: transactor (pays in full) vs revolver (carries a
        # balance). Higher-end products skew more transactor (trap 3).
        tx_rate = product[7]
        # Superprime skews more transactor, subprime skews more revolver.
        band_tx_adj = {"A": 0.15, "B": 0.05, "C": -0.05, "D": -0.15, "E": -0.20}[band_code]
        is_transactor = random.random() < min(0.95, max(0.05, tx_rate + band_tx_adj))
        behavior = "TRANSACTOR" if is_transactor else "REVOLVER"

        # signup bonus: campaign has a bonus and the account "hits the min-spend"
        # (most accounts qualify).
        signup_bonus = 0.0
        if camp and camp["signup_bonus_usd"] and camp["signup_bonus_usd"] > 0:
            if random.random() < 0.80:
                signup_bonus = float(camp["signup_bonus_usd"])

        # bonus churner (trap 6): in large-bonus campaigns, some accounts take the money and run.
        # Their profile: hit min-spend to get the bonus (transactor, generates no interest),
        # then spend drops to zero afterward, and the first-year fee is also waived/refunded
        # before closure, so lifetime contribution ≈ a little interchange - signup bonus < 0 (negative LTV).
        is_bonus_churner = False
        if signup_bonus >= 200 and random.random() < BONUS_CHURN_RATE_HIGH_BONUS:
            is_bonus_churner = True
            behavior = "TRANSACTOR"

        # --- Determine the outcome: charge-off / bonus_churn close / voluntary close / survives ---
        # Combined pd (charge-off probability within the observed window).
        if band_code == "D":
            pd = base_co                      # band D: score-independent (trap 1)
        else:
            pd = base_co * (SCORE_PD_HI - SCORE_PD_SLOPE * (uw_score / 999.0))
        pd *= channel_mult                    # channel adverse selection (trap 2)
        pd *= VINTAGE_PD_MULT.get(vintage, 1.0)  # vintage deterioration (trap 7)

        # CLI adverse selection (trap 5): decide whether a CLI happens, and whether
        # pre-CLI utilization was high.
        got_cli = (not is_bonus_churner) and random.random() < CLI_ELIGIBLE_RATE
        cli_high_util = got_cli and (behavior == "REVOLVER") and random.random() < 0.45
        if cli_high_util:
            pd *= CLI_HIGH_UTIL_PD_MULT

        pd = min(0.62, max(0.004, pd))

        # Max account age (up to REFERENCE_DATE).
        max_mob = (REFERENCE_DATE.year - open_dt.year) * 12 + (REFERENCE_DATE.month - open_dt.month)
        max_mob = max(1, min(24, max_mob))

        fate = "ACTIVE"
        end_mob = max_mob
        co_at_mob = None
        close_at_mob = None
        close_reason = None
        close_type = None

        if is_bonus_churner:
            cm = random.randint(*BONUS_CHURN_CLOSE_MOB)
            if cm <= max_mob:
                fate = "CLOSED"
                close_at_mob = cm
                close_reason = "bonus_churn"
                close_type = "VOLUNTARY"
                end_mob = cm
        else:
            will_co = random.random() < pd
            if will_co:
                cm = chargeoff_mob()
                if cm <= max_mob:
                    fate = "CHARGED_OFF"
                    co_at_mob = cm
                    end_mob = cm
            if fate == "ACTIVE" and max_mob >= 4:
                # Voluntary attrition (rate_shopping / inactivity / upgrade). Probability accrues with account age.
                vol_prob = VOLUNTARY_ATTRITION_BASE * (max_mob / 12.0)
                if random.random() < vol_prob:
                    cm = random.randint(3, max_mob)
                    fate = "CLOSED"
                    close_at_mob = cm
                    close_reason = random.choice(["rate_shopping", "inactivity", "dissatisfaction", "product_upgrade"])
                    close_type = "VOLUNTARY"
                    end_mob = cm

        # --- Generate statements month by month ---
        # Baseline monthly spend: correlated with limit and behavior (transactors spend
        # more, revolvers spend less).
        spend_base = limit * (random.uniform(0.35, 0.75) if behavior == "TRANSACTOR"
                              else random.uniform(0.15, 0.45))
        prev_balance = 0.0
        cli_done = False
        # The mob at which the CLI occurs (if got_cli).
        cli_mob = random.randint(4, max(4, max_mob - 1)) if got_cli else None
        current_limit = limit
        anniversary_fee = product[2]

        for m in range(1, end_mob + 1):
            stmt_dt = add_months(open_dt, m)
            if stmt_dt > REFERENCE_DATE:
                break

            # CLI takes effect
            if got_cli and cli_mob is not None and m == cli_mob and not cli_done:
                pre_util = round(min(1.5, prev_balance / current_limit) if current_limit else 0, 2)
                new_limit = round(current_limit * random.uniform(1.2, 1.6), -1)
                cli_id += 1
                cli_changes.append({
                    "id": cli_id, "account_id": acct_id, "change_date": stmt_dt,
                    "change_type": "CLI",
                    "old_limit_usd": current_limit, "new_limit_usd": float(new_limit),
                    "pre_change_utilization_pct": round(pre_util * 100, 2),
                    "initiated_by": "bank" if random.random() < 0.7 else "customer",
                    "reason": "high_utilization_review" if cli_high_util else "good_standing_review",
                })
                current_limit = float(new_limit)
                cli_done = True

            promo_active = bool(is_promo and promo_end and stmt_dt < promo_end)
            eff_apr = 0.0 if promo_active else base_apr

            # Purchase amount
            purchase = max(0.0, random.gauss(spend_base, spend_base * 0.35))
            purchase = min(purchase, current_limit * 0.95)
            # bonus churner: hits min-spend in the first 2 months, then spend drops
            # essentially to zero afterward (goes dormant once the bonus is earned).
            if is_bonus_churner and m > 2:
                purchase *= 0.08

            # DPD logic
            dpd = 0
            if fate == "CHARGED_OFF" and co_at_mob is not None:
                # Gradual deterioration leading up to charge-off (early warning): DPD
                # escalates in the final 4 months.
                months_to_co = co_at_mob - m
                if months_to_co == 3:
                    dpd = 30
                elif months_to_co == 2:
                    dpd = 60
                elif months_to_co == 1:
                    dpd = 90
                elif months_to_co == 0:
                    dpd = 150
            # promo cliff (trap 4): DPD spikes in the 1-3 months after promo expiry.
            if is_promo and promo_end is not None:
                months_since_promo = (stmt_dt.year - promo_end.year) * 12 + (stmt_dt.month - promo_end.month)
                if 0 <= months_since_promo <= 2 and random.random() < 0.11 and fate != "CHARGED_OFF":
                    dpd = max(dpd, 30 * random.randint(1, 2))

            # Balance and payment
            if behavior == "TRANSACTOR" and dpd == 0:
                balance = purchase
                payment = prev_balance    # last statement paid in full
                interest = 0.0
            else:
                # revolver: carries a balance, pays only part of the minimum.
                carry = prev_balance
                interest = round(carry * (eff_apr / 100.0 / 12.0), 2)
                balance = round(carry + purchase + interest, 2)
                balance = min(balance, current_limit * 1.02)
                if dpd == 0:
                    pay_ratio = random.uniform(0.05, 0.35)
                else:
                    pay_ratio = random.uniform(0.0, 0.03)   # pays almost nothing while delinquent
                payment = round(carry * pay_ratio, 2)

            # Fees: annual fee (anniversary month) + late fee (delinquent). For bonus
            # churners, the first-year fee is treated as waived/refunded and not charged.
            fees = 0.0
            if anniversary_fee > 0 and not is_bonus_churner:
                if m == 1:
                    fees += anniversary_fee   # first-year annual fee charged at account opening
                elif m % 12 == 1 and m > 1:
                    fees += anniversary_fee   # renewal-year annual fee
            if dpd >= 30:
                fees += 35.0   # late fee

            interchange = round(purchase * INTERCHANGE_RATE, 2)
            rewards_earned = round(purchase * product[4], 2)  # product[4] = rewards_rate_pct
            min_due = round(max(25.0, balance * 0.02 + interest + fees), 2) if balance > 0 else 0.0
            util = round(min(1.5, balance / current_limit) * 100, 2) if current_limit else 0.0

            if dpd == 0:
                bucket = "CURRENT"
            elif dpd < 60:
                bucket = "DPD30"
            elif dpd < 90:
                bucket = "DPD60"
            elif dpd < 120:
                bucket = "DPD90"
            elif dpd < 180:
                bucket = "DPD120PLUS"
            else:
                bucket = "CHARGEOFF"

            stmt_id += 1
            statements.append({
                "id": stmt_id, "account_id": acct_id, "statement_date": stmt_dt,
                "cycle_month": m,
                "statement_balance_usd": round(balance, 2),
                "purchase_volume_usd": round(purchase, 2),
                "payment_amount_usd": round(payment, 2),
                "interest_charged_usd": round(interest, 2),
                "fees_charged_usd": round(fees, 2),
                "interchange_revenue_usd": interchange,
                "rewards_earned_usd": rewards_earned,
                "minimum_due_usd": min_due,
                "credit_limit_usd": current_limit,
                "utilization_pct": util,
                "days_past_due": dpd,
                "dpd_bucket": bucket,
                "is_promo_active": promo_active,
            })
            prev_balance = balance if behavior != "TRANSACTOR" or dpd > 0 else 0.0

            # Sampled transaction (~1 out of every 3 statement months), for MCC analysis.
            if purchase > 0 and random.random() < 0.35:
                txn_id += 1
                mcc = random.choices(mcc_ids, weights=mcc_weights, k=1)[0]
                amt = round(min(purchase, max(8.0, random.gauss(purchase / 4, purchase / 6))), 2)
                is_fraud_txn = random.random() < 0.004
                transactions.append({
                    "id": txn_id, "account_id": acct_id, "mcc_category_id": mcc,
                    "transaction_date": stmt_dt - timedelta(days=random.randint(1, 25)),
                    "amount_usd": amt,
                    "interchange_revenue_usd": round(amt * mcc_ic[mcc], 2),
                    "is_fraud": is_fraud_txn,
                })
                if is_fraud_txn:
                    fr_id += 1
                    gross = round(amt * random.uniform(1, 4), 2)
                    recovered = random.random() < 0.6
                    frauds.append({
                        "id": fr_id, "account_id": acct_id,
                        "reported_date": stmt_dt + timedelta(days=random.randint(1, 20)),
                        "fraud_type": random.choice(
                            ["card_not_present", "lost_stolen", "account_takeover", "counterfeit"]),
                        "gross_loss_usd": gross,
                        "net_loss_usd": 0.0 if recovered else gross,
                        "resolution": "recovered" if recovered else "written_off",
                    })

        # signup bonus ledger entry (posted once mob 2-3 qualification is met).
        if signup_bonus > 0:
            rl_id += 1
            bonus_dt = add_months(open_dt, min(3, max_mob))
            rewards.append({
                "id": rl_id, "account_id": acct_id, "entry_date": bonus_dt,
                "entry_type": "BONUS", "amount_usd": signup_bonus,
                "description": f"Signup bonus after ${camp['min_spend_for_bonus_usd']:.0f} min spend",
            })
        # Redemption event (occasional redemption on rewards cards).
        if product[4] > 0 and random.random() < 0.4 and end_mob >= 6:
            rl_id += 1
            redeem_dt = add_months(open_dt, random.randint(4, max(4, end_mob)))
            rewards.append({
                "id": rl_id, "account_id": acct_id, "entry_date": redeem_dt,
                "entry_type": "REDEEMED", "amount_usd": round(random.uniform(20, 250), 2),
                "description": "Cashback/miles redemption",
            })

        # charge-off record
        status = "ACTIVE"
        closed_dt = None
        final_mob = end_mob
        if fate == "CHARGED_OFF" and co_at_mob is not None:
            co_dt = add_months(open_dt, co_at_mob)
            co_balance = round(max(200.0, prev_balance if prev_balance > 0 else current_limit * random.uniform(0.5, 0.95)), 2)
            recovered = round(co_balance * random.uniform(0.05, 0.35), 2)
            has_recovery = random.random() < 0.7
            co_id += 1
            chargeoffs.append({
                "id": co_id, "account_id": acct_id, "charge_off_date": co_dt,
                "charged_off_balance_usd": co_balance,
                "recovery_amount_usd": recovered if has_recovery else 0.0,
                "recovery_date": add_months(co_dt, random.randint(2, 8)) if has_recovery else None,
                "months_on_book_at_chargeoff": co_at_mob,
            })
            status = "CHARGED_OFF"
            closed_dt = co_dt
            final_mob = co_at_mob
            # Also record as an INVOLUNTARY attrition
            at_id += 1
            attritions.append({
                "id": at_id, "account_id": acct_id, "close_date": co_dt,
                "close_type": "INVOLUNTARY", "close_reason": "charge_off",
                "months_on_book_at_close": co_at_mob,
            })
        elif fate == "CLOSED" and close_at_mob is not None:
            cl_dt = add_months(open_dt, close_at_mob)
            status = "CLOSED"
            closed_dt = cl_dt
            final_mob = close_at_mob
            at_id += 1
            attritions.append({
                "id": at_id, "account_id": acct_id, "close_date": cl_dt,
                "close_type": close_type, "close_reason": close_reason,
                "months_on_book_at_close": close_at_mob,
            })

        accounts.append({
            "id": acct_id, "application_id": app["id"], "applicant_id": app["applicant_id"],
            "card_product_id": app["card_product_id"], "credit_band_id": app["credit_band_id"],
            "acquisition_channel_id": channel_id, "campaign_id": app["campaign_id"],
            "open_date": open_dt, "credit_limit_usd": limit,
            "purchase_apr_pct": base_apr, "is_promo_apr": is_promo,
            "promo_apr_pct": promo_apr, "promo_end_date": promo_end,
            "behavior_segment": behavior, "underwriting_score": uw_score,
            "signup_bonus_usd": signup_bonus, "account_status": status,
            "open_vintage": vintage, "closed_date": closed_dt,
            "months_on_book": final_mob,
        })

    return {
        "account": pl.DataFrame(accounts),
        "statement": pl.DataFrame(statements),
        "transaction": pl.DataFrame(transactions),
        "rewards_ledger": pl.DataFrame(rewards),
        "credit_line_change": pl.DataFrame(cli_changes),
        "charge_off": pl.DataFrame(chargeoffs),
        "attrition_event": pl.DataFrame(attritions),
        "fraud_case": pl.DataFrame(frauds),
    }


# ---------------------------------------------------------------------------
# Section 7. generate_all_tsv
# ---------------------------------------------------------------------------

def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_band = gen_credit_bands()
    df_band.write_csv(DATA_DIR / "01_credit_band.tsv", separator="\t")

    df_product = gen_card_products()
    df_product.write_csv(DATA_DIR / "02_card_product.tsv", separator="\t")

    df_channel = gen_marketing_channels()
    df_channel.write_csv(DATA_DIR / "03_marketing_channel.tsv", separator="\t")

    df_mcc = gen_mcc_categories()
    df_mcc.write_csv(DATA_DIR / "04_mcc_category.tsv", separator="\t")

    df_campaign = gen_campaigns()
    df_campaign.write_csv(DATA_DIR / "05_campaign.tsv", separator="\t")

    df_prescreen = gen_prescreen_offers(df_campaign)
    df_prescreen.write_csv(DATA_DIR / "06_prescreen_offer.tsv", separator="\t")

    df_applicant, df_application = gen_applicants_and_applications(df_campaign)
    df_applicant.write_csv(DATA_DIR / "07_applicant.tsv", separator="\t")
    df_application.write_csv(DATA_DIR / "08_application.tsv", separator="\t")

    life = gen_accounts_and_lifecycle(df_application, df_campaign)
    life["account"].write_csv(DATA_DIR / "09_account.tsv", separator="\t")
    life["statement"].write_csv(DATA_DIR / "10_statement.tsv", separator="\t")
    life["transaction"].write_csv(DATA_DIR / "11_transaction.tsv", separator="\t")
    life["rewards_ledger"].write_csv(DATA_DIR / "12_rewards_ledger.tsv", separator="\t")
    life["credit_line_change"].write_csv(DATA_DIR / "13_credit_line_change.tsv", separator="\t")
    life["charge_off"].write_csv(DATA_DIR / "14_charge_off.tsv", separator="\t")
    life["attrition_event"].write_csv(DATA_DIR / "15_attrition_event.tsv", separator="\t")
    life["fraud_case"].write_csv(DATA_DIR / "16_fraud_case.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")
    print(f"  accounts={life['account'].height}, statements={life['statement'].height}, "
          f"transactions={life['transaction'].height}, charge_offs={life['charge_off'].height}")


# ---------------------------------------------------------------------------
# Section 8. create_sqlite_database (Core API batch loader)
# ---------------------------------------------------------------------------

def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order = [
        ("01_credit_band", CreditBand.__table__),
        ("02_card_product", CardProduct.__table__),
        ("03_marketing_channel", MarketingChannel.__table__),
        ("04_mcc_category", MccCategory.__table__),
        ("05_campaign", Campaign.__table__),
        ("06_prescreen_offer", PrescreenOffer.__table__),
        ("07_applicant", Applicant.__table__),
        ("08_application", Application.__table__),
        ("09_account", Account.__table__),
        ("10_statement", Statement.__table__),
        ("11_transaction", Transaction.__table__),
        ("12_rewards_ledger", RewardsLedger.__table__),
        ("13_credit_line_change", CreditLineChange.__table__),
        ("14_charge_off", ChargeOff.__table__),
        ("15_attrition_event", AttritionEvent.__table__),
        ("16_fraud_case", FraudCase.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv",
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=10000,
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
