"""
Gaming/Esports Esports Club Commercial Operations Fake Data Generator
Complexity: Medium

Business Background:
Vanguard Esports is a fictional esports club headquartered in Los Angeles, with 3
sub-teams (Vanguard Fracture, Vanguard Aetherlane, Vanguard Academy). This dataset
covers commercial and competitive operations data across two full seasons, from
2024-07-01 to REFERENCE_DATE = 2026-06-30, supporting analysis of the following
4 business traps:

1. Sponsorship exposure billing gap trap: among the 12 sponsorship contracts, 3
   (TitanEnergy Global Partnership, GridForge Fracture Protocol Hardware Deal,
   StreakBet Gaming Partnership) have annualized measured exposure hours that
   systematically fall about 25%-35% short of the contractually committed
   values, while the remaining 9 contracts maintain a delivery rate above 93%;
   looking only at the overall average would dilute the signal with the healthy
   contracts.
2. Salary-performance disconnect trap: 4 players (Zenithrax, Wraithcall,
   Thornquil, Hollowmere) have seen their performance ratings over the trailing
   6 months drop roughly 30%-35% from their historical peaks, yet all of them
   completed long-term contract renewals around the time of the decline, with
   salaries never adjusted downward; the remaining players' salaries stay
   positively correlated with their recent performance ratings.
3. Merch gross margin tied to team form trap: when the team's trailing 60-day
   rolling win rate is high, merch discounting is light and gross margin holds
   at 48%-53%; when the win rate falls into a slump, discounting rises sharply
   and gross margin drops to 32%-38%, but unit volume actually ticks up slightly
   thanks to the promotions, so total revenue declines far less than gross
   margin does -- a financial report that only looks at revenue trends would
   completely miss this signal.
4. Prize split payment compliance trap: about 15% of player prize distribution
   records are either late (beyond the contractually agreed 30-day payment
   term) or underpaid, and roughly 80% of those are concentrated in the
   Vanguard Academy team, pointing to a systemic issue in that team's prize
   split payment process.

The traps above are injected via deliberately designed correlated distributions.
The corresponding SQL queries live in
03-gaming_esports_org_commercial_operations_medium_sql_queries-cn.md and are
used to surface these traps.
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
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ----------------------------------------------------------------------------
# Configuration constants
# ----------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "gaming_esports_org_commercial_operations_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date, so results stay consistent across runs and do not
# depend on the current system time.
# Anywhere the SQL queries need "today", they use this same literal date.
REFERENCE_DATE = date(2026, 6, 30)
# Start of the data window: two full seasons, 24 months total.
SEASON_START = date(2024, 7, 1)
TOTAL_SEASON_DAYS = (REFERENCE_DATE - SEASON_START).days

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


def month_index(d: date) -> int:
    """Convert a date into a month index (0-23) relative to SEASON_START, used to look up a team's monthly target state."""
    return (d.year - SEASON_START.year) * 12 + (d.month - SEASON_START.month)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def weighted_choice(pairs: list[tuple]) -> object:
    """Draw one label from a list of (label, weight) tuples, weighted by the given weights. Weights do not need to sum to 1."""
    labels = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return random.choices(labels, weights=weights, k=1)[0]


# ----------------------------------------------------------------------------
# Business Calibration Constants
# ----------------------------------------------------------------------------

# Basic setup for the 3 sub-teams. Vanguard Fracture and Vanguard Aetherlane are
# the main-roster teams; Vanguard Academy is the Fracture Protocol development
# league team (Ascendant Circuit tier), with a markedly smaller budget.
TEAM_DEFS = [
    {
        "key": "fracture_main",
        "team_name": "Vanguard Fracture",
        "game_title": "Fracture Protocol",
        "competitive_tier": "main_roster",
        "home_city": "Los Angeles, CA",
        "founded_date": date(2018, 3, 1),
        "salary_cap_usd": 3_200_000.00,
    },
    {
        "key": "aetherlane_main",
        "team_name": "Vanguard Aetherlane",
        "game_title": "Aetherlane",
        "competitive_tier": "main_roster",
        "home_city": "Los Angeles, CA",
        "founded_date": date(2019, 1, 15),
        "salary_cap_usd": 3_600_000.00,
    },
    {
        "key": "fracture_academy",
        "team_name": "Vanguard Academy",
        "game_title": "Fracture Protocol",
        "competitive_tier": "academy_roster",
        "home_city": "Los Angeles, CA",
        "founded_date": date(2021, 6, 1),
        "salary_cap_usd": 600_000.00,
    },
]

# Monthly "target win rate" state for each team, used to generate match
# results. Trap 3 (merch gross margin tied to team form) relies on a few
# deliberately designed slump windows (month indices per month_index):
# Fracture Protocol main roster opens with a slump (months 0-2, echoing "worst
# start in three years"), then strengthens in the back half and posts its
# best-ever run in the final six months (months 18-23, echoing the Q2 board's
# focus on "making the playoffs this season"); Aetherlane main roster hits a
# slump mid-season (months 9-11); the Academy team swings more year-round,
# hitting a slump in months 15-17.
def team_monthly_target(team_key: str, m_idx: int) -> float:
    if team_key == "fracture_main":
        if m_idx <= 2:
            return 0.30
        if m_idx >= 18:
            return 0.68
        return 0.52
    if team_key == "aetherlane_main":
        if 9 <= m_idx <= 11:
            return 0.28
        return 0.55
    # fracture_academy
    if 15 <= m_idx <= 17:
        return 0.25
    return 0.45


# Player roster. The 4 players with legacy_star=True are the core sample for
# trap 2 (salary-performance disconnect): their performance ratings over the
# trailing 6 months have declined significantly from their historical peaks,
# yet their salary contracts were locked in for the long term around the same
# time as the decline. The remaining players' salaries stay positively
# correlated with recent performance, serving as the control group.
ROSTER_DEFS = [
    # --- Vanguard Fracture (fracture_main) ---
    {"gamertag": "Zenithrax", "team_key": "fracture_main", "role_position": "Duelist", "is_starter": True, "legacy_star": True},
    {"gamertag": "Wraithcall", "team_key": "fracture_main", "role_position": "IGL", "is_starter": True, "legacy_star": True},
    {"gamertag": "Glimmerhex", "team_key": "fracture_main", "role_position": "Controller", "is_starter": True, "legacy_star": False},
    {"gamertag": "Duskrunner", "team_key": "fracture_main", "role_position": "Initiator", "is_starter": True, "legacy_star": False},
    {"gamertag": "Ironvale", "team_key": "fracture_main", "role_position": "Sentinel", "is_starter": True, "legacy_star": False},
    {"gamertag": "Emberclip", "team_key": "fracture_main", "role_position": "Duelist", "is_starter": False, "legacy_star": False},
    {"gamertag": "Frostbyte", "team_key": "fracture_main", "role_position": "Initiator", "is_starter": False, "legacy_star": False},
    # --- Vanguard Aetherlane (aetherlane_main) ---
    {"gamertag": "Novaspark", "team_key": "aetherlane_main", "role_position": "Top", "is_starter": True, "legacy_star": False},
    {"gamertag": "Thornquil", "team_key": "aetherlane_main", "role_position": "Jungle", "is_starter": True, "legacy_star": True},
    {"gamertag": "Skyhaven", "team_key": "aetherlane_main", "role_position": "Mid", "is_starter": True, "legacy_star": False},
    {"gamertag": "Vexstrike", "team_key": "aetherlane_main", "role_position": "ADC", "is_starter": True, "legacy_star": False},
    {"gamertag": "Ashbourne", "team_key": "aetherlane_main", "role_position": "Support", "is_starter": True, "legacy_star": False},
    {"gamertag": "Calderis", "team_key": "aetherlane_main", "role_position": "Top", "is_starter": False, "legacy_star": False},
    {"gamertag": "Rimeclad", "team_key": "aetherlane_main", "role_position": "Jungle", "is_starter": False, "legacy_star": False},
    {"gamertag": "Solvane", "team_key": "aetherlane_main", "role_position": "Mid", "is_starter": False, "legacy_star": False},
    # --- Vanguard Academy (fracture_academy) ---
    {"gamertag": "Emberquill", "team_key": "fracture_academy", "role_position": "Duelist", "is_starter": True, "legacy_star": False},
    {"gamertag": "Hollowmere", "team_key": "fracture_academy", "role_position": "Controller", "is_starter": True, "legacy_star": True},
    {"gamertag": "Brackenfall", "team_key": "fracture_academy", "role_position": "Initiator", "is_starter": True, "legacy_star": False},
    {"gamertag": "Graniteshade", "team_key": "fracture_academy", "role_position": "Sentinel", "is_starter": True, "legacy_star": False},
    {"gamertag": "Pyrelash", "team_key": "fracture_academy", "role_position": "IGL", "is_starter": True, "legacy_star": False},
    {"gamertag": "Wrenfield", "team_key": "fracture_academy", "role_position": "Duelist", "is_starter": False, "legacy_star": False},
]

NATIONALITIES = [
    "United States", "Canada", "South Korea", "Sweden", "Denmark",
    "Brazil", "France", "United Kingdom", "Germany", "Poland",
]

# Salary and prize-split percentage ranges, stratified by (team tier, is starter).
SALARY_BAND_BY_TIER = {
    ("main_roster", True): (220_000.0, 650_000.0),
    ("main_roster", False): (75_000.0, 150_000.0),
    ("academy_roster", True): (45_000.0, 110_000.0),
    ("academy_roster", False): (30_000.0, 70_000.0),
}
PRIZE_SPLIT_BAND_BY_TIER = {
    ("main_roster", True): (8.0, 14.0),
    ("main_roster", False): (3.0, 6.0),
    ("academy_roster", True): (6.0, 10.0),
    ("academy_roster", False): (2.0, 4.0),
}
# Baseline performance rating range for non-legacy players (fluctuating around
# 1.00), used to give salary and performance a positive correlation (a
# correlation coefficient of roughly 0.55-0.65): the higher a player's
# baseline, the higher their salary position within the range.
RATING_BASELINE_BAND_BY_TIER = {
    ("main_roster", True): (0.98, 1.15),
    ("main_roster", False): (0.85, 1.00),
    ("academy_roster", True): (0.90, 1.08),
    ("academy_roster", False): (0.80, 0.95),
}

# --- Trap 2: Salary-performance disconnect ----------------------------------
# Historical peak performance rating range for legacy_star players (12-18
# months before REFERENCE_DATE), and the magnitude of their trailing-6-month
# decline (28%-36%, averaging around 32%). Renegotiation dates fall around the
# start of the decline, with contract terms extended to 24-30 months, ensuring
# more than 18 months remain on the contract as of REFERENCE_DATE.
LEGACY_STAR_PROFILE = {
    "Zenithrax": {"peak_rating": 1.22, "decline_ratio": 0.33, "last_renegotiation_date": date(2025, 12, 15), "term_months": 30},
    "Wraithcall": {"peak_rating": 1.15, "decline_ratio": 0.30, "last_renegotiation_date": date(2025, 10, 1), "term_months": 30},
    "Thornquil": {"peak_rating": 1.20, "decline_ratio": 0.34, "last_renegotiation_date": date(2025, 11, 1), "term_months": 27},
    "Hollowmere": {"peak_rating": 1.12, "decline_ratio": 0.28, "last_renegotiation_date": date(2025, 9, 15), "term_months": 29},
}
PEAK_WINDOW_START_DAYS_BEFORE_REF = 540  # 18 months before the reference date
PEAK_WINDOW_END_DAYS_BEFORE_REF = 360  # 12 months before the reference date
RECENT_WINDOW_START_DAYS_BEFORE_REF = 180  # 6 months before the reference date

# --- Trap 1: Sponsorship exposure billing gap --------------------------------
# 10 sponsors, 12 sponsorship contracts (TitanEnergy and NorthPeak each have 2
# contracts with different scopes). target_ratio is the target delivery rate
# ("annualized measured exposure / committed exposure"): the 3 rigged contracts
# (see RIGGED_DEAL_NAMES) are held around 0.68-0.72 (a systematic gap of
# 28%-32%), while the remaining 9 are held at 0.93-1.08 (healthy delivery).
# Note: committed annual exposure hours (committed_annual_exposure_hours) are
# NOT hardcoded here -- instead they are back-calculated in
# gen_sponsor_exposure_logs from that contract's "total reachable broadcast
# duration" (see the docstring there), which guarantees that the measured
# exposure for any single broadcast never exceeds the broadcast's own duration.
SPONSOR_DEAL_DEFS = [
    {"sponsor": "TitanEnergy Drink", "industry": "energy_drink", "deal_name": "TitanEnergy Global Partnership", "team_key": None, "annual_value": 900_000.0, "target_ratio": 0.70, "method": "stream_logo_overlay"},
    {"sponsor": "TitanEnergy Drink", "industry": "energy_drink", "deal_name": "TitanEnergy Fracture Protocol Jersey Patch", "team_key": "fracture_main", "annual_value": 220_000.0, "target_ratio": 1.02, "method": "jersey_patch_estimate"},
    {"sponsor": "GridForge PC Hardware", "industry": "pc_hardware", "deal_name": "GridForge Fracture Protocol Hardware Deal", "team_key": "fracture_main", "annual_value": 300_000.0, "target_ratio": 0.69, "method": "stream_logo_overlay"},
    {"sponsor": "StreakBet Gaming", "industry": "fintech_betting", "deal_name": "StreakBet Gaming Partnership", "team_key": "aetherlane_main", "annual_value": 260_000.0, "target_ratio": 0.69, "method": "stream_logo_overlay"},
    {"sponsor": "NorthPeak Gaming Chairs", "industry": "furniture", "deal_name": "NorthPeak Fracture Protocol Seating Partner", "team_key": "fracture_main", "annual_value": 180_000.0, "target_ratio": 0.96, "method": "stream_logo_overlay"},
    {"sponsor": "NorthPeak Gaming Chairs", "industry": "furniture", "deal_name": "NorthPeak Aetherlane Seating Renewal", "team_key": "aetherlane_main", "annual_value": 190_000.0, "target_ratio": 1.04, "method": "stream_logo_overlay"},
    {"sponsor": "VoltLine Mobility", "industry": "mobility", "deal_name": "VoltLine Global Partnership", "team_key": None, "annual_value": 350_000.0, "target_ratio": 0.98, "method": "stream_logo_overlay"},
    {"sponsor": "CrestBank Financial", "industry": "fintech", "deal_name": "CrestBank Global Partnership", "team_key": None, "annual_value": 400_000.0, "target_ratio": 1.05, "method": "stream_logo_overlay"},
    {"sponsor": "Apexware Peripherals", "industry": "pc_hardware", "deal_name": "Apexware Aetherlane Peripherals Deal", "team_key": "aetherlane_main", "annual_value": 150_000.0, "target_ratio": 0.95, "method": "stream_logo_overlay"},
    {"sponsor": "Highlander Apparel", "industry": "apparel", "deal_name": "Highlander Global Apparel Partnership", "team_key": None, "annual_value": 240_000.0, "target_ratio": 1.06, "method": "jersey_patch_estimate"},
    {"sponsor": "Pulsecom Telecom", "industry": "telecom", "deal_name": "Pulsecom Academy Development Partner", "team_key": "fracture_academy", "annual_value": 60_000.0, "target_ratio": 1.00, "method": "stream_logo_overlay"},
    {"sponsor": "Ridgeline Insurance", "industry": "insurance", "deal_name": "Ridgeline Global Partnership", "team_key": None, "annual_value": 210_000.0, "target_ratio": 0.97, "method": "stream_logo_overlay"},
]
RIGGED_DEAL_NAMES = {"TitanEnergy Global Partnership", "GridForge Fracture Protocol Hardware Deal", "StreakBet Gaming Partnership"}
EXPOSURE_LOG_SAMPLE_RATE = 0.60  # Only about 60% of eligible broadcasts get actually measured and logged by the content team
# Measured visible share of the brand logo within a single broadcast (as a
# fraction of that broadcast's total duration). This is the key coefficient
# used to back-calculate "committed annual exposure hours" into a per-broadcast
# measured value, and it's also what guarantees measured <= broadcast duration
# as a physical constraint: stream_logo_overlay is a persistent corner badge
# with a high visible share; jersey_patch_estimate is only visible when a
# player/jersey is on camera, so its share is lower. Both are far below 1, so
# even with added noise a single broadcast's measured exposure always stays
# below the broadcast's duration.
EXPOSURE_VISIBILITY_BY_METHOD = {"stream_logo_overlay": 0.60, "jersey_patch_estimate": 0.35}

# --- Trap 3: Merch gross margin tied to team form ----------------------------
TRAILING_WINRATE_WINDOW_DAYS = 60
MERCH_UNIT_COST_RATIO_RANGE = (0.42, 0.48)  # Unit cost as a share of the official list price
MERCH_DISCOUNT_HOT = (10.0, 4.0, 0.0, 25.0)  # (mean, std dev, lower bound, upper bound)
MERCH_DISCOUNT_MID = (18.0, 5.0, 5.0, 35.0)
MERCH_DISCOUNT_SLUMP = (30.0, 6.0, 15.0, 45.0)
MERCH_HOT_WINRATE_THRESHOLD = 0.55
MERCH_SLUMP_WINRATE_THRESHOLD = 0.35
MERCH_SLUMP_QUANTITY_BOOST = 1.15  # Extra sales-volume multiplier driven by the heavier slump-period discounting
TOTAL_MERCH_SALES = 9000

# --- Trap 4: Prize split payment compliance (concentrated in Vanguard Academy) ---
# Calibration target: about 15% of all distribution records are late or
# underpaid, with roughly 80% of those concentrated in the Academy team.
PRIZE_LATE_PROB_BY_TIER = {"academy_roster": 0.38, "main_roster": 0.045}
PRIZE_UNDERPAY_PROB_GIVEN_LATE = {"academy_roster": 0.48, "main_roster": 0.10}
PRIZE_UNDERPAY_PROB_GIVEN_ON_TIME = {"academy_roster": 0.17, "main_roster": 0.045}
PRIZE_UNDERPAY_RATIO_RANGE = (0.88, 0.95)
PRIZE_STANDARD_PAYMENT_TERM_DAYS = 30

# Share of a tournament's total prize pool that goes to the placement prize
# for each rank (an estimate of what one Vanguard team can win).
PLACEMENT_PRIZE_SHARE = {1: 0.40, 2: 0.20, 3: 0.12, 4: 0.08, 5: 0.05, 6: 0.03, 7: 0.015, 8: 0.01}

OPPONENT_NAME_ADJECTIVES = [
    "Ironclad", "Obsidian", "Crimson", "Silverline", "Ashen", "Radiant",
    "Nightfall", "Golden", "Storm", "Rogue", "Frozen", "Scarlet",
]
OPPONENT_NAME_NOUNS = [
    "Syndicate", "Vanguard Rivals", "Talons", "Wolves", "Sentinels",
    "Dominion", "Uprising", "Coalition", "Legion", "Rift", "Phalanx",
]


class Base(DeclarativeBase):
    pass


# ----------------------------------------------------------------------------
# ORM models (topological order)
# ----------------------------------------------------------------------------


class Sponsor(Base):
    """Sponsor brand dimension: the brand companies under contract with the club."""

    __tablename__ = "sponsor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    industry_category: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship_start_date: Mapped[date] = mapped_column(Date, nullable=False)


class Team(Base):
    """Dimension of the club's sub-teams."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    game_title: Mapped[str] = mapped_column(String(30), nullable=False)
    competitive_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    home_city: Mapped[str] = mapped_column(String(60), nullable=False)
    founded_date: Mapped[date] = mapped_column(Date, nullable=False)
    salary_cap_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class RosterPlayer(Base):
    """Roster player master record, belonging to a given sub-team."""

    __tablename__ = "roster_player"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    gamertag: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    real_name: Mapped[str] = mapped_column(String(80), nullable=False)
    nationality: Mapped[str] = mapped_column(String(56), nullable=False)
    role_position: Mapped[str] = mapped_column(String(30), nullable=False)
    join_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PlayerContract(Base):
    """Player's currently active contract: annual salary, contract start/end dates, last renegotiation date, prize split percentage."""

    __tablename__ = "player_contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roster_player_id: Mapped[int] = mapped_column(ForeignKey("roster_player.id"), nullable=False, unique=True)
    annual_salary_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    signing_bonus_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_renegotiation_date: Mapped[date] = mapped_column(Date, nullable=False)
    prize_split_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class SponsorshipDeal(Base):
    """Sponsorship contract: brand, sponsorship scope (whole club or a specific team), committed annual exposure hours."""

    __tablename__ = "sponsorship_deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsor.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=True)
    deal_name: Mapped[str] = mapped_column(String(100), nullable=False)
    annual_value_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    committed_annual_exposure_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    exposure_measurement_method: Mapped[str] = mapped_column(String(40), nullable=False)


class Tournament(Base):
    """Tournament dimension: a league split, playoff, or third-party invitational that one of Vanguard's teams participated in."""

    __tablename__ = "tournament"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    game_title: Mapped[str] = mapped_column(String(30), nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    region: Mapped[str] = mapped_column(String(40), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_prize_pool_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class MatchResult(Base):
    """Match result: a single game played by one of Vanguard's teams at a given tournament."""

    __tablename__ = "match_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournament.id"), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    opponent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    team_score: Mapped[int] = mapped_column(Integer, nullable=False)
    opponent_score: Mapped[int] = mapped_column(Integer, nullable=False)


class PlayerMatchStat(Base):
    """Per-player, per-match statistics, including the composite performance rating; the core basis for salary/performance disconnect analysis."""

    __tablename__ = "player_match_stat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_result_id: Mapped[int] = mapped_column(ForeignKey("match_result.id"), nullable=False)
    roster_player_id: Mapped[int] = mapped_column(ForeignKey("roster_player.id"), nullable=False)
    kills: Mapped[int] = mapped_column(Integer, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_rating: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    was_mvp: Mapped[bool] = mapped_column(Boolean, nullable=False)


class BroadcastSession(Base):
    """Broadcast session: a match broadcast or non-match content stream; the foundation for sponsorship exposure measurement."""

    __tablename__ = "broadcast_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_result_id: Mapped[int] = mapped_column(ForeignKey("match_result.id"), nullable=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    broadcast_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_duration_hours: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    average_viewers: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_viewers: Mapped[int] = mapped_column(Integer, nullable=False)


class SponsorExposureLog(Base):
    """Measured sponsorship exposure record: measured exposure hours for a given sponsorship contract's brand logo within a given broadcast."""

    __tablename__ = "sponsor_exposure_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsorship_deal_id: Mapped[int] = mapped_column(ForeignKey("sponsorship_deal.id"), nullable=False)
    broadcast_session_id: Mapped[int] = mapped_column(ForeignKey("broadcast_session.id"), nullable=False)
    measured_exposure_hours: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)


class MerchSku(Base):
    """Merch catalog: team-specific or club-wide branded products."""

    __tablename__ = "merch_sku"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_cost_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    list_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class MerchSale(Base):
    """Merch sales transactions: the core table for the merch-gross-margin-tied-to-team-form analysis."""

    __tablename__ = "merch_sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merch_sku_id: Mapped[int] = mapped_column(ForeignKey("merch_sku.id"), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    unit_price_paid_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)


class PrizePoolPayout(Base):
    """Tournament prize payout record: the prize money the tournament organizer pays the club for a given team."""

    __tablename__ = "prize_pool_payout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournament.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    placement: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_prize_awarded_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    organizer_payout_date: Mapped[date] = mapped_column(Date, nullable=False)
    org_received_date: Mapped[date] = mapped_column(Date, nullable=False)


class PlayerPrizeDistribution(Base):
    """Player prize distribution detail: contracted vs actual paid amount/date; the core table for payment compliance analysis."""

    __tablename__ = "player_prize_distribution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prize_pool_payout_id: Mapped[int] = mapped_column(ForeignKey("prize_pool_payout.id"), nullable=False)
    roster_player_id: Mapped[int] = mapped_column(ForeignKey("roster_player.id"), nullable=False)
    contracted_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    contracted_amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    actual_paid_amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False)


# ----------------------------------------------------------------------------
# Dimension table generator functions
# ----------------------------------------------------------------------------


def gen_sponsors() -> pl.DataFrame:
    """Sponsor brand dimension: 10 fictional brands, spanning energy drinks/hardware/fintech/apparel and other industries."""
    seen = {}
    rows = []
    for d in SPONSOR_DEAL_DEFS:
        if d["sponsor"] in seen:
            continue
        seen[d["sponsor"]] = True
        rows.append({
            "sponsor_name": d["sponsor"],
            "industry_category": d["industry"],
            "relationship_start_date": SEASON_START - timedelta(days=random.randint(30, 720)),
        })
    return pl.DataFrame(rows).with_row_index("id", offset=1)


def gen_teams() -> pl.DataFrame:
    """Dimension of the 3 sub-teams."""
    rows = [
        {
            "team_name": t["team_name"],
            "game_title": t["game_title"],
            "competitive_tier": t["competitive_tier"],
            "home_city": t["home_city"],
            "founded_date": t["founded_date"],
            "salary_cap_usd": t["salary_cap_usd"],
        }
        for t in TEAM_DEFS
    ]
    return pl.DataFrame(rows).with_row_index("id", offset=1)


def gen_roster_players(team_id_by_key: dict) -> list[dict]:
    """Roster player master data, 21 players, with 4 flagged legacy_star (for internal generator use
    only, not persisted as a table column -- analysts need to infer it from salary vs. recent performance rating)."""
    rows = []
    for i, p in enumerate(ROSTER_DEFS):
        team_id = team_id_by_key[p["team_key"]]
        join_offset = random.randint(60, 900)
        join_date = max(SEASON_START - timedelta(days=join_offset), date(2019, 1, 1))
        rows.append({
            "id": i + 1,
            "team_id": team_id,
            "gamertag": p["gamertag"],
            "real_name": fake.name(),
            "nationality": random.choice(NATIONALITIES),
            "role_position": p["role_position"],
            "join_date": join_date,
            "is_starter": p["is_starter"],
            "is_active": True,
            "_team_key": p["team_key"],
            "_legacy_star": p["legacy_star"],
        })
    return rows


def gen_player_contracts(players: list[dict], team_by_id: dict) -> list[dict]:
    """Players' currently active contracts. legacy_star players' renegotiation dates fall around the
    start of their performance decline, with contract terms extended to 24-30 months, and salaries set
    at the tier corresponding to their historical peak (the core of trap 2)."""
    rows = []
    for idx, p in enumerate(players):
        team = team_by_id[p["team_id"]]
        tier = team["competitive_tier"]
        is_starter = p["is_starter"]
        salary_lo, salary_hi = SALARY_BAND_BY_TIER[(tier, is_starter)]
        split_lo, split_hi = PRIZE_SPLIT_BAND_BY_TIER[(tier, is_starter)]
        rating_lo, rating_hi = RATING_BASELINE_BAND_BY_TIER[(tier, is_starter)]

        if p["_legacy_star"]:
            profile = LEGACY_STAR_PROFILE[p["gamertag"]]
            last_renegotiation_date = profile["last_renegotiation_date"]
            contract_start_date = last_renegotiation_date
            contract_end_date = contract_start_date + timedelta(days=30 * profile["term_months"])
            # Salary is set at the rating percentile corresponding to the historical peak, not the current (already declined) rating.
            peak_percentile = clamp((profile["peak_rating"] - rating_lo) / (rating_hi - rating_lo), 0.0, 1.0)
            annual_salary = salary_lo + peak_percentile * (salary_hi - salary_lo)
            annual_salary = clamp(max(annual_salary, salary_hi * 0.90) * random.uniform(0.95, 1.03), salary_lo, salary_hi)
            base_rating_mean = None  # legacy_star ratings are computed with a dedicated timeline function, not a fixed baseline
        else:
            base_rating_mean = random.uniform(rating_lo, rating_hi)
            rating_percentile = (base_rating_mean - rating_lo) / (rating_hi - rating_lo)
            # 70% weight on the performance percentile, 30% random noise, producing a salary/performance correlation of roughly 0.55-0.65.
            annual_salary = (
                salary_lo
                + rating_percentile * (salary_hi - salary_lo) * 0.7
                + random.uniform(0.0, 0.3) * (salary_hi - salary_lo)
            )
            contract_start_date = SEASON_START - timedelta(days=random.randint(0, 300))
            contract_start_date = max(contract_start_date, p["join_date"])
            last_renegotiation_date = contract_start_date
            contract_end_date = contract_start_date + timedelta(days=30 * random.randint(12, 30))

        rows.append({
            "id": idx + 1,
            "roster_player_id": p["id"],
            "annual_salary_usd": round(annual_salary, 2),
            "signing_bonus_usd": round(annual_salary * random.uniform(0.0, 0.15), 2) if random.random() < 0.5 else None,
            "contract_start_date": contract_start_date,
            "contract_end_date": contract_end_date,
            "last_renegotiation_date": last_renegotiation_date,
            "prize_split_pct": round(random.uniform(split_lo, split_hi), 2),
            "_base_rating_mean": base_rating_mean,
        })
    return rows


def gen_sponsorship_deals(sponsor_id_by_name: dict, team_id_by_key: dict) -> list[dict]:
    """12 sponsorship contracts. Contract terms span the entire 24-month data window (some were signed before the window starts).

    Note: committed_annual_exposure_hours (committed annual exposure hours) is not hardcoded here;
    it is later back-calculated in gen_sponsor_exposure_logs from that contract's "total measured
    exposure across its reachable broadcast sample", annualized and then divided by the target delivery
    rate (see the docstring there). This simultaneously guarantees (a) a single broadcast's measured
    exposure always stays < the broadcast's own duration, and (b) Query 1/3, using the same annualized
    basis, computes a delivery rate that lands exactly on the designed target_ratio. Here committed is
    a placeholder None; once the back-calculation runs it is always overwritten with a positive number
    (see the write order in generate_all_tsv)."""
    rows = []
    for idx, d in enumerate(SPONSOR_DEAL_DEFS):
        contract_start_date = SEASON_START - timedelta(days=random.randint(0, 200))
        contract_end_date = REFERENCE_DATE + timedelta(days=random.randint(30, 200))
        rows.append({
            "id": idx + 1,
            "sponsor_id": sponsor_id_by_name[d["sponsor"]],
            "team_id": team_id_by_key[d["team_key"]] if d["team_key"] else None,
            "deal_name": d["deal_name"],
            "annual_value_usd": d["annual_value"],
            "contract_start_date": contract_start_date,
            "contract_end_date": contract_end_date,
            "committed_annual_exposure_hours": None,  # placeholder, back-filled by gen_sponsor_exposure_logs
            "exposure_measurement_method": d["method"],
            "_team_key": d["team_key"],
            "_target_ratio": d["target_ratio"],
        })
    return rows


# 8 tournament slots per team, evenly distributed across the 24-month window (roughly one tournament window every 3 months).
TOURNAMENT_SLOT_COUNT = 8
TOURNAMENT_TIER_BY_SLOT_MAIN = ["A", "S", "A", "S", "A", "S", "A", "S"]
TOURNAMENT_TIER_BY_SLOT_ACADEMY = ["B", "B", "A", "B", "B", "A", "B", "A"]
TIER_POOL_RANGE = {"S": (700_000.0, 1_000_000.0), "A": (150_000.0, 300_000.0), "B": (30_000.0, 70_000.0)}
TOURNAMENT_NAME_BY_SLOT = [
    "Kickoff", "Split 1 Playoffs", "Split 2 Regular Season", "Split 2 Playoffs",
    "Kickoff", "Split 1 Playoffs", "Split 2 Regular Season", "Split 2 Playoffs",
]


def gen_tournaments(team_id_by_key: dict) -> list[dict]:
    """24 tournaments, 8 per team, evenly distributed across the two seasons."""
    rows = []
    row_id = 1
    slot_span_days = TOTAL_SEASON_DAYS // TOURNAMENT_SLOT_COUNT
    for t in TEAM_DEFS:
        tier_pattern = TOURNAMENT_TIER_BY_SLOT_ACADEMY if t["competitive_tier"] == "academy_roster" else TOURNAMENT_TIER_BY_SLOT_MAIN
        for slot in range(TOURNAMENT_SLOT_COUNT):
            tier = tier_pattern[slot]
            pool_lo, pool_hi = TIER_POOL_RANGE[tier]
            slot_anchor = SEASON_START + timedelta(days=slot_span_days * slot + random.randint(10, slot_span_days - 20))
            start_date = slot_anchor
            end_date = start_date + timedelta(days=random.randint(10, 16))
            year_label = 2024 + (slot_anchor.year - SEASON_START.year) + (1 if slot_anchor.month < SEASON_START.month else 0)
            name = f"{t['team_name']} {TOURNAMENT_NAME_BY_SLOT[slot]} {slot_anchor.year}"
            rows.append({
                "id": row_id,
                "tournament_name": name,
                "game_title": t["game_title"],
                "tier": tier,
                "region": "North America",
                "start_date": start_date,
                "end_date": end_date,
                "total_prize_pool_usd": round(random.uniform(pool_lo, pool_hi), 2),
                "_team_key": t["key"],
                "_team_id": team_id_by_key[t["key"]],
            })
            row_id += 1
    return rows


def gen_opponent_name() -> str:
    return f"{random.choice(OPPONENT_NAME_ADJECTIVES)} {random.choice(OPPONENT_NAME_NOUNS)}"


def simulate_stage_matches(team_key: str, tournament: dict) -> list[dict]:
    """Generate group-stage/playoff/grand-final match records for a single tournament slot. The team's
    monthly target state (team_monthly_target) determines the win probability of each match, causing the
    trailing 60-day win rate to fluctuate over time -- this is the data foundation for trap 3 (merch
    gross margin tied to team form)."""
    matches = []
    span = (tournament["end_date"] - tournament["start_date"]).days

    def draw_date(offset_lo: int, offset_hi: int) -> date:
        offset = random.randint(offset_lo, min(offset_hi, max(span, offset_lo)))
        return tournament["start_date"] + timedelta(days=offset)

    def win_prob_at(d: date) -> float:
        return team_monthly_target(team_key, month_index(d))

    group_count = random.randint(14, 20)
    group_wins = 0
    for i in range(group_count):
        d = draw_date(0, max(span - 2, 1))
        p_win = win_prob_at(d)
        is_win = random.random() < p_win
        group_wins += int(is_win)
        team_score = 1 if is_win else 0
        opp_score = 0 if is_win else 1
        matches.append({"match_date": d, "opponent_name": gen_opponent_name(), "format": "Bo1", "stage": "group_stage", "result": "win" if is_win else "loss", "team_score": team_score, "opponent_score": opp_score})

    group_win_rate = group_wins / group_count
    reached_playoffs = group_win_rate >= 0.45
    playoffs_win_rate = 0.0
    playoffs_wins = 0
    playoffs_count = 0
    if reached_playoffs:
        playoffs_count = random.randint(3, 6)
        for i in range(playoffs_count):
            d = draw_date(max(span - 6, 0), span)
            p_win = win_prob_at(d)
            is_win = random.random() < p_win
            playoffs_wins += int(is_win)
            if random.random() < 0.7:
                team_score, opp_score = (2, random.choice([0, 1])) if is_win else (random.choice([0, 1]), 2)
            else:
                team_score, opp_score = (3, random.choice([0, 1, 2])) if is_win else (random.choice([0, 1, 2]), 3)
            matches.append({"match_date": d, "opponent_name": gen_opponent_name(), "format": "Bo3" if team_score + opp_score <= 3 else "Bo5", "stage": "playoffs", "result": "win" if is_win else "loss", "team_score": team_score, "opponent_score": opp_score})
        playoffs_win_rate = playoffs_wins / playoffs_count if playoffs_count else 0.0

    reached_final = reached_playoffs and playoffs_win_rate >= 0.60 and random.random() < 0.65
    won_final = False
    if reached_final:
        d = tournament["end_date"]
        p_win = win_prob_at(d)
        is_win = random.random() < clamp(p_win + 0.05, 0.0, 0.95)
        won_final = is_win
        team_score, opp_score = (3, random.choice([1, 2])) if is_win else (random.choice([1, 2]), 3)
        matches.append({"match_date": d, "opponent_name": gen_opponent_name(), "format": "Bo5", "stage": "grand_final", "result": "win" if is_win else "loss", "team_score": team_score, "opponent_score": opp_score})

    if won_final:
        placement = 1
    elif reached_final:
        placement = 2
    elif reached_playoffs:
        placement = 3 if playoffs_win_rate >= 0.35 else 4
    elif group_win_rate < 0.25:
        # Group-stage performance was too poor (didn't reach playoffs and win rate is below 25%); in
        # reality this kind of "group-stage elimination" typically wins no prize money at all.
        # placement=99 is not in PLACEMENT_PRIZE_SHARE, so downstream logic treats it as share=0 and
        # skips generating a prize payout record, rather than manufacturing a token payout.
        placement = 99
    else:
        placement = 5 + min(3, int((0.45 - group_win_rate) * 10))

    return matches, placement


def gen_match_results_and_payouts(tournaments: list[dict]) -> tuple[list[dict], list[dict]]:
    """Match results table + prize payout records table. Generated together in one pass because
    placement (rank) is determined by the simulated group-stage/playoff results, and the prize
    payout records depend on that placement."""
    match_rows = []
    payout_rows = []
    match_id = 1
    payout_id = 1
    for t in tournaments:
        stage_matches, placement = simulate_stage_matches(t["_team_key"], t)
        for m in stage_matches:
            match_rows.append({
                "id": match_id,
                "team_id": t["_team_id"],
                "tournament_id": t["id"],
                "match_date": m["match_date"],
                "opponent_name": m["opponent_name"],
                "format": m["format"],
                "stage": m["stage"],
                "result": m["result"],
                "team_score": m["team_score"],
                "opponent_score": m["opponent_score"],
            })
            match_id += 1

        share = PLACEMENT_PRIZE_SHARE.get(placement, 0.0)
        if share <= 0.0:
            # Eliminated in group stage with nothing to show for it: the organizer owes the club no
            # prize money at all, and in reality this would never produce a "zero-dollar payout"
            # record, so this appearance simply generates no prize_pool_payout row (and consequently
            # no corresponding player distribution records either).
            continue
        gross_prize = round(t["total_prize_pool_usd"] * share * random.uniform(0.9, 1.1), 2)
        organizer_payout_date = t["end_date"] + timedelta(days=random.randint(3, 10))
        org_received_date = organizer_payout_date + timedelta(days=random.randint(2, 12))
        payout_rows.append({
            "id": payout_id,
            "tournament_id": t["id"],
            "team_id": t["_team_id"],
            "placement": placement,
            "gross_prize_awarded_usd": gross_prize,
            "organizer_payout_date": organizer_payout_date,
            "org_received_date": org_received_date,
        })
        payout_id += 1
    return match_rows, payout_rows


# ----------------------------------------------------------------------------
# Player match statistics and trap 2 (salary-performance disconnect)
# ----------------------------------------------------------------------------


def legacy_star_rating_mean(gamertag: str, match_date: date) -> float:
    """Expected performance rating for a legacy_star player at a given date: a linear transition from
    the historical peak (18-12 months before the reference date) down to the trailing-6-month slump."""
    profile = LEGACY_STAR_PROFILE[gamertag]
    peak_mean = profile["peak_rating"]
    decline_mean = peak_mean * (1 - profile["decline_ratio"])
    peak_end = REFERENCE_DATE - timedelta(days=PEAK_WINDOW_END_DAYS_BEFORE_REF)
    recent_start = REFERENCE_DATE - timedelta(days=RECENT_WINDOW_START_DAYS_BEFORE_REF)
    if match_date <= peak_end:
        return peak_mean
    if match_date >= recent_start:
        return decline_mean
    frac = (match_date - peak_end).days / (recent_start - peak_end).days
    return peak_mean + frac * (decline_mean - peak_mean)


def gen_player_match_stats(match_rows: list[dict], players: list[dict], contracts_by_player: dict) -> list[dict]:
    """Per-player match statistics. legacy_star players' ratings follow the timeline transition from
    historical peak down to the recent slump (trap 2); other players' ratings fluctuate slightly around
    their own fixed baselines, staying positively correlated with salary."""
    starters_by_team: dict[int, list[dict]] = {}
    for p in players:
        starters_by_team.setdefault(p["team_id"], []).append(p)

    rows = []
    row_id = 1
    for m in match_rows:
        roster = [p for p in starters_by_team[m["team_id"]] if p["is_starter"]]
        match_ratings = []
        for p in roster:
            if p["_legacy_star"]:
                rating_mean = legacy_star_rating_mean(p["gamertag"], m["match_date"])
            else:
                rating_mean = contracts_by_player[p["id"]]["_base_rating_mean"]
            rating = clamp(round(random.gauss(rating_mean, 0.14), 2), 0.40, 1.90)
            deaths = random.randint(8, 17)
            kills = max(0, round(deaths * rating * random.uniform(0.9, 1.1)))
            assists = random.randint(2, 14)
            match_ratings.append({
                "id": None,
                "match_result_id": m["id"],
                "roster_player_id": p["id"],
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "performance_rating": rating,
                "was_mvp": False,
            })
        if match_ratings:
            best = max(match_ratings, key=lambda r: r["performance_rating"])
            best["was_mvp"] = True
        for r in match_ratings:
            r["id"] = row_id
            rows.append(r)
            row_id += 1
    return rows


# ----------------------------------------------------------------------------
# Broadcast sessions and measured sponsorship exposure (trap 1)
# ----------------------------------------------------------------------------

BASE_VIEWERS_BY_TEAM_KEY = {"fracture_main": 35_000, "aetherlane_main": 40_000, "fracture_academy": 6_000}
TIER_VIEWER_FACTOR = {"S": 1.3, "A": 1.0, "B": 0.6}
STAGE_VIEWER_FACTOR = {"group_stage": 0.8, "playoffs": 1.3, "grand_final": 1.8}
FORMAT_DURATION_HOURS = {"Bo1": 1.3, "Bo3": 2.5, "Bo5": 4.0}
CONTENT_BROADCAST_COUNT_PER_TEAM = 33


def gen_broadcast_sessions(match_rows: list[dict], tournament_by_id: dict, team_key_by_id: dict) -> list[dict]:
    """Broadcast sessions: one broadcast per match, plus about 33 non-match content broadcasts per team."""
    rows = []
    row_id = 1
    for m in match_rows:
        tournament = tournament_by_id[m["tournament_id"]]
        team_key = team_key_by_id[m["team_id"]]
        base_viewers = BASE_VIEWERS_BY_TEAM_KEY[team_key]
        tier_factor = TIER_VIEWER_FACTOR[tournament["tier"]]
        stage_factor = STAGE_VIEWER_FACTOR[m["stage"]]
        avg_viewers = int(base_viewers * tier_factor * stage_factor * random.uniform(0.8, 1.2))
        rows.append({
            "id": row_id,
            "match_result_id": m["id"],
            "team_id": m["team_id"],
            "platform": weighted_choice([("Twitch", 0.8), ("YouTube", 0.2)]),
            "broadcast_date": m["match_date"],
            "actual_duration_hours": round(FORMAT_DURATION_HOURS[m["format"]] * random.uniform(0.85, 1.15), 2),
            "average_viewers": avg_viewers,
            "peak_viewers": int(avg_viewers * random.uniform(1.15, 1.4)),
        })
        row_id += 1

    for t in TEAM_DEFS:
        base_viewers = BASE_VIEWERS_BY_TEAM_KEY[t["key"]]
        team_id = [k for k, v in team_key_by_id.items() if v == t["key"]][0]
        for _ in range(CONTENT_BROADCAST_COUNT_PER_TEAM):
            broadcast_date = SEASON_START + timedelta(days=random.randint(0, TOTAL_SEASON_DAYS))
            avg_viewers = int(base_viewers * 0.15 * random.uniform(0.7, 1.3))
            rows.append({
                "id": row_id,
                "match_result_id": None,
                "team_id": team_id,
                "platform": weighted_choice([("Twitch", 0.85), ("YouTube", 0.15)]),
                "broadcast_date": broadcast_date,
                "actual_duration_hours": round(random.uniform(0.5, 2.0), 2),
                "average_viewers": avg_viewers,
                "peak_viewers": int(avg_viewers * random.uniform(1.1, 1.3)),
            })
            row_id += 1
    return rows


def gen_sponsor_exposure_logs(deals: list[dict], broadcasts: list[dict]) -> list[dict]:
    """Measured sponsorship exposure records, and simultaneously back-calculates and fills in each
    contract's committed annual exposure hours.

    Physical quantity (measured exposure for a single broadcast): measured = that broadcast's duration
    x the visible share for that billing method (EXPOSURE_VISIBILITY_BY_METHOD) x a slight noise factor
    (0.85-1.15). Since the visible share is <= 0.60 and the noise upper bound is 1.15, a single
    broadcast's measured exposure is always <= 0.69 x the broadcast's duration, i.e. strictly less than
    the broadcast's duration -- fundamentally ruling out the physically impossible situation of "logo
    exposure lasting longer than the entire broadcast" (fixing the old version's measured > duration
    overflow bug).

    Billing quantity (committed annual exposure hours): first sum up the per-broadcast measured values
    above over the "measured sample (about 60% of eligible broadcasts)" to get that contract's total
    measured exposure; annualize it (divide by the contract's effective years within the data window),
    then divide by the target delivery rate target_ratio to back-calculate committed_annual_exposure_hours,
    which is filled back into the deal dict. Because committed is derived from the same measured sample,
    Query 1/3, using the exact same annualized basis, will compute a delivery rate that lands precisely on
    target_ratio (healthy contracts ~0.93-1.08, the 3 rigged contracts ~0.68-0.72), reliably producing
    trap 1 (sponsorship exposure billing gap)."""
    rows = []
    row_id = 1
    for deal in deals:
        visibility = EXPOSURE_VISIBILITY_BY_METHOD[deal["exposure_measurement_method"]]
        eligible = [
            b for b in broadcasts
            if (deal["_team_key"] is None or b["team_id"] == deal["team_id"])
            and deal["contract_start_date"] <= b["broadcast_date"] <= deal["contract_end_date"]
        ]
        sampled = [b for b in eligible if random.random() < EXPOSURE_LOG_SAMPLE_RATE]
        years_active = max((min(deal["contract_end_date"], REFERENCE_DATE) - deal["contract_start_date"]).days / 365.25, 0.5)

        deal_logs = []
        total_measured = 0.0
        for b in sampled:
            measured = max(round(b["actual_duration_hours"] * visibility * random.uniform(0.85, 1.15), 3), 0.001)
            total_measured += measured
            deal_logs.append({
                "id": row_id,
                "sponsorship_deal_id": deal["id"],
                "broadcast_session_id": b["id"],
                "measured_exposure_hours": measured,
                "log_date": b["broadcast_date"],
            })
            row_id += 1

        # Back-calculate committed annual exposure hours = annualized measured exposure / target
        # delivery rate. Round to whole hours, so the committed value reads more like a negotiated
        # contract term (which also gives the delivery rate a bit of natural jitter, rather than
        # hitting exactly 0.0pp).
        # Extreme fallback: if this contract has no measurable samples at all (shouldn't happen with
        # normal data), fall back to a reasonable default so committed doesn't end up NULL and violate
        # the NOT NULL constraint.
        annualized_measured = total_measured / years_active
        committed = annualized_measured / deal["_target_ratio"] if annualized_measured > 0 else 100.0
        deal["committed_annual_exposure_hours"] = float(max(round(committed), 1))
        rows.extend(deal_logs)
    return rows


# ----------------------------------------------------------------------------
# Merch products and sales (trap 3)
# ----------------------------------------------------------------------------

MERCH_PRODUCT_TEMPLATES = [
    ("Home Jersey", "jersey", 74.99, 89.99),
    ("Away Jersey", "jersey", 74.99, 89.99),
    ("Logo Hoodie", "hoodie", 54.99, 64.99),
    ("Team Cap", "headwear", 24.99, 32.99),
    ("Mousepad", "accessory", 14.99, 19.99),
    ("Keychain", "accessory", 9.99, 14.99),
]
GENERAL_MERCH_TEMPLATES = [
    ("Vanguard Esports Logo Hoodie", "hoodie", 54.99, 64.99),
    ("Vanguard Esports Snapback Cap", "headwear", 24.99, 29.99),
    ("Vanguard Esports Mousepad XL", "accessory", 19.99, 24.99),
    ("Vanguard Esports Keychain Set", "accessory", 9.99, 12.99),
    ("Vanguard Esports Tote Bag", "accessory", 14.99, 18.99),
    ("Vanguard Esports Pin Collector Set", "accessory", 12.99, 16.99),
    ("Vanguard Esports Poster Print", "accessory", 9.99, 12.99),
]


def gen_merch_skus(team_id_by_key: dict) -> list[dict]:
    """25 merch products: 6 team-specific products for each of the 3 teams + 7 club-wide branded products."""
    rows = []
    row_id = 1
    for t in TEAM_DEFS:
        for product_suffix, category, price_lo, price_hi in MERCH_PRODUCT_TEMPLATES:
            list_price = round(random.uniform(price_lo, price_hi), 2)
            cost_ratio = random.uniform(*MERCH_UNIT_COST_RATIO_RANGE)
            rows.append({
                "id": row_id,
                "team_id": team_id_by_key[t["key"]],
                "product_name": f"{t['team_name']} {product_suffix}",
                "category": category,
                "unit_cost_usd": round(list_price * cost_ratio, 2),
                "list_price_usd": list_price,
                "_team_key": t["key"],
            })
            row_id += 1
    for product_name, category, price_lo, price_hi in GENERAL_MERCH_TEMPLATES:
        list_price = round(random.uniform(price_lo, price_hi), 2)
        cost_ratio = random.uniform(*MERCH_UNIT_COST_RATIO_RANGE)
        rows.append({
            "id": row_id,
            "team_id": None,
            "product_name": product_name,
            "category": category,
            "unit_cost_usd": round(list_price * cost_ratio, 2),
            "list_price_usd": list_price,
            "_team_key": None,
        })
        row_id += 1
    return rows


def build_matches_by_team(match_rows: list[dict]) -> dict[int, list[dict]]:
    by_team: dict[int, list[dict]] = {}
    for m in match_rows:
        by_team.setdefault(m["team_id"], []).append(m)
    for team_id in by_team:
        by_team[team_id].sort(key=lambda m: m["match_date"])
    return by_team


def trailing_winrate(matches: list[dict], as_of: date, window_days: int = TRAILING_WINRATE_WINDOW_DAYS) -> float:
    """Win rate over the window_days days preceding the given date. Returns 0.5 (neutral) when there are no match records."""
    window_start = as_of - timedelta(days=window_days)
    windowed = [m for m in matches if window_start <= m["match_date"] <= as_of]
    if not windowed:
        return 0.5
    wins = sum(1 for m in windowed if m["result"] == "win")
    return wins / len(windowed)


def gen_merch_sales(merch_skus: list[dict], matches_by_team: dict, team_id_by_key: dict) -> list[dict]:
    """Merch sales transactions. Discount level and sales volume vary with the corresponding team's (or
    the whole club's) trailing 60-day rolling win rate: during a slump, discounting rises sharply, unit
    volume ticks up slightly thanks to the promotions, and gross margin is significantly compressed
    (trap 3)."""
    all_team_ids = list(team_id_by_key.values())
    rows = []
    sku_weights = [(s["id"], 3.0 if s["category"] == "jersey" else (2.0 if s["category"] == "hoodie" else 1.0)) for s in merch_skus]
    sku_by_id = {s["id"]: s for s in merch_skus}
    for row_id in range(1, TOTAL_MERCH_SALES + 1):
        sku_id = weighted_choice(sku_weights)
        sku = sku_by_id[sku_id]
        sale_date = SEASON_START + timedelta(days=random.randint(0, TOTAL_SEASON_DAYS))
        if sku["team_id"] is not None:
            wr = trailing_winrate(matches_by_team.get(sku["team_id"], []), sale_date)
        else:
            wr = sum(trailing_winrate(matches_by_team.get(tid, []), sale_date) for tid in all_team_ids) / len(all_team_ids)

        if wr >= MERCH_HOT_WINRATE_THRESHOLD:
            mean, std, lo, hi = MERCH_DISCOUNT_HOT
            qty_boost = 1.0
        elif wr < MERCH_SLUMP_WINRATE_THRESHOLD:
            mean, std, lo, hi = MERCH_DISCOUNT_SLUMP
            qty_boost = MERCH_SLUMP_QUANTITY_BOOST
        else:
            mean, std, lo, hi = MERCH_DISCOUNT_MID
            qty_boost = 1.05

        discount_pct = round(clamp(random.gauss(mean, std), lo, hi), 2)
        quantity = max(1, round(random.gauss(3.0 * qty_boost, 1.2)))
        unit_price_paid = round(sku["list_price_usd"] * (1 - discount_pct / 100), 2)
        rows.append({
            "id": row_id,
            "merch_sku_id": sku_id,
            "sale_date": sale_date,
            "quantity": quantity,
            "discount_pct": discount_pct,
            "unit_price_paid_usd": unit_price_paid,
            "channel": weighted_choice([("online_store", 0.75), ("event_pop_up", 0.25)]),
        })
    return rows


# ----------------------------------------------------------------------------
# Prize split distribution details (trap 4)
# ----------------------------------------------------------------------------


def gen_player_prize_distributions(payout_rows: list[dict], players: list[dict], contracts_by_player: dict, team_by_id: dict) -> list[dict]:
    """Player prize distribution detail. Only starting players receive a prize split. The Vanguard
    Academy team's distribution records have a markedly higher probability of being late/underpaid,
    concentrating trap 4."""
    starters_by_team: dict[int, list[dict]] = {}
    for p in players:
        if p["is_starter"]:
            starters_by_team.setdefault(p["team_id"], []).append(p)

    rows = []
    row_id = 1
    for payout in payout_rows:
        team = team_by_id[payout["team_id"]]
        tier = team["competitive_tier"]
        due_date = payout["org_received_date"] + timedelta(days=PRIZE_STANDARD_PAYMENT_TERM_DAYS)
        for p in starters_by_team.get(payout["team_id"], []):
            contract = contracts_by_player[p["id"]]
            contracted_pct = contract["prize_split_pct"]
            contracted_amount = round(payout["gross_prize_awarded_usd"] * contracted_pct / 100, 2)

            is_late = random.random() < PRIZE_LATE_PROB_BY_TIER[tier]
            underpay_prob = PRIZE_UNDERPAY_PROB_GIVEN_LATE[tier] if is_late else PRIZE_UNDERPAY_PROB_GIVEN_ON_TIME[tier]
            is_underpaid = random.random() < underpay_prob

            if is_underpaid:
                actual_amount = round(contracted_amount * random.uniform(*PRIZE_UNDERPAY_RATIO_RANGE), 2)
            else:
                actual_amount = contracted_amount

            if is_late:
                paid_date = due_date + timedelta(days=random.randint(15, 60))
            else:
                paid_date = due_date - timedelta(days=random.randint(0, 25))
                paid_date = max(paid_date, payout["org_received_date"])

            if is_late and is_underpaid:
                status = "late_and_underpaid"
            elif is_late:
                status = "late"
            elif is_underpaid:
                status = "underpaid"
            else:
                status = "on_time"

            rows.append({
                "id": row_id,
                "prize_pool_payout_id": payout["id"],
                "roster_player_id": p["id"],
                "contracted_pct": contracted_pct,
                "contracted_amount_usd": contracted_amount,
                "actual_paid_amount_usd": actual_amount,
                "due_date": due_date,
                "paid_date": paid_date,
                "payment_status": status,
            })
            row_id += 1
    return rows


# ----------------------------------------------------------------------------
# TSV generation and SQLite loading
# ----------------------------------------------------------------------------


def _strip_private_fields(rows: list[dict]) -> list[dict]:
    """Strip the underscore-prefixed fields used only internally during generation, not persisted as table columns."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_sponsor = gen_sponsors()
    df_sponsor.write_csv(DATA_DIR / "01_sponsor.tsv", separator="\t")
    sponsor_id_by_name = {r["sponsor_name"]: r["id"] for r in df_sponsor.to_dicts()}

    df_team = gen_teams()
    df_team.write_csv(DATA_DIR / "02_team.tsv", separator="\t")
    team_rows = df_team.to_dicts()
    team_id_by_key = {t["key"]: team_rows[i]["id"] for i, t in enumerate(TEAM_DEFS)}
    team_key_by_id = {v: k for k, v in team_id_by_key.items()}
    team_by_id = {r["id"]: r for r in team_rows}

    players = gen_roster_players(team_id_by_key)
    df_roster = pl.DataFrame(_strip_private_fields(players))
    df_roster.write_csv(DATA_DIR / "03_roster_player.tsv", separator="\t")

    contracts = gen_player_contracts(players, team_by_id)
    contracts_by_player = {c["roster_player_id"]: c for c in contracts}
    df_contract = pl.DataFrame(_strip_private_fields(contracts))
    df_contract.write_csv(DATA_DIR / "04_player_contract.tsv", separator="\t")

    deals = gen_sponsorship_deals(sponsor_id_by_name, team_id_by_key)
    # 05_sponsorship_deal.tsv is written later, after the exposure logs are generated:
    # committed_annual_exposure_hours needs to be back-calculated by gen_sponsor_exposure_logs
    # from the reachable broadcast sample and filled back into the deal dict first.

    tournaments = gen_tournaments(team_id_by_key)
    df_tournament = pl.DataFrame(_strip_private_fields(tournaments))
    df_tournament.write_csv(DATA_DIR / "06_tournament.tsv", separator="\t")
    tournament_by_id = {t["id"]: t for t in tournaments}

    match_rows, payout_rows = gen_match_results_and_payouts(tournaments)
    df_match = pl.DataFrame(match_rows)
    df_match.write_csv(DATA_DIR / "07_match_result.tsv", separator="\t")

    stat_rows = gen_player_match_stats(match_rows, players, contracts_by_player)
    df_stat = pl.DataFrame(stat_rows)
    df_stat.write_csv(DATA_DIR / "08_player_match_stat.tsv", separator="\t")

    broadcast_rows = gen_broadcast_sessions(match_rows, tournament_by_id, team_key_by_id)
    df_broadcast = pl.DataFrame(broadcast_rows)
    df_broadcast.write_csv(DATA_DIR / "09_broadcast_session.tsv", separator="\t")

    exposure_rows = gen_sponsor_exposure_logs(deals, broadcast_rows)
    # At this point every deal dict's committed_annual_exposure_hours has already been back-calculated and filled in, so it can be written out.
    df_deal = pl.DataFrame(_strip_private_fields(deals))
    df_deal.write_csv(DATA_DIR / "05_sponsorship_deal.tsv", separator="\t")
    df_exposure = pl.DataFrame(exposure_rows)
    df_exposure.write_csv(DATA_DIR / "10_sponsor_exposure_log.tsv", separator="\t")

    merch_skus = gen_merch_skus(team_id_by_key)
    df_merch_sku = pl.DataFrame(_strip_private_fields(merch_skus))
    df_merch_sku.write_csv(DATA_DIR / "11_merch_sku.tsv", separator="\t")

    matches_by_team = build_matches_by_team(match_rows)
    merch_sale_rows = gen_merch_sales(merch_skus, matches_by_team, team_id_by_key)
    df_merch_sale = pl.DataFrame(merch_sale_rows)
    df_merch_sale.write_csv(DATA_DIR / "12_merch_sale.tsv", separator="\t")

    df_payout = pl.DataFrame(payout_rows)
    df_payout.write_csv(DATA_DIR / "13_prize_pool_payout.tsv", separator="\t")

    distribution_rows = gen_player_prize_distributions(payout_rows, players, contracts_by_player, team_by_id)
    df_distribution = pl.DataFrame(distribution_rows)
    df_distribution.write_csv(DATA_DIR / "14_player_prize_distribution.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order: list[tuple[str, "Table"]] = [
        ("01_sponsor", Sponsor.__table__),
        ("02_team", Team.__table__),
        ("03_roster_player", RosterPlayer.__table__),
        ("04_player_contract", PlayerContract.__table__),
        ("05_sponsorship_deal", SponsorshipDeal.__table__),
        ("06_tournament", Tournament.__table__),
        ("07_match_result", MatchResult.__table__),
        ("08_player_match_stat", PlayerMatchStat.__table__),
        ("09_broadcast_session", BroadcastSession.__table__),
        ("10_sponsor_exposure_log", SponsorExposureLog.__table__),
        ("11_merch_sku", MerchSku.__table__),
        ("12_merch_sale", MerchSale.__table__),
        ("13_prize_pool_payout", PrizePoolPayout.__table__),
        ("14_player_prize_distribution", PlayerPrizeDistribution.__table__),
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
