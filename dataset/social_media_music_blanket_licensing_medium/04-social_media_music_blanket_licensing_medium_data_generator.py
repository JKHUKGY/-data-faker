"""
Social Media - Short-Video Platform Music Blanket Licensing and Compliance Audit Fake Data Generator
Complexity: Medium

Business Background:
ReelWave, Inc. is a fictional short-video social media company headquartered in San
Francisco. This dataset simulates the blanket license contracts that its internal
"Sounds" music team signs with 20 record labels/aggregator distributors, the
platform's monthly catalog usage data, weekly Creator Fund payouts, UGC remix
rights-conflict audit records, and daily fine-grained usage data for 120 trending
candidate sounds, supporting the following analyses:

1. Catalog usage share drift: a label's actual catalog usage share has
   systematically diverged from the assumption made at contract signing, but the
   annual fee was never adjusted to match.
2. UGC unauthorized sampling compliance audit: a batch of rights-conflict flags
   has remained unresolved for a long time, exceeding the internal 30-day SLA,
   with real advertising revenue risk exposure behind it.
3. Creator Fund viral-window snapshot misalignment: sounds whose viral window
   happens to straddle two calendar-week settlement boundaries systematically
   receive a lower payout per thousand views than sounds whose viral window
   falls entirely within a single week.
4. MFN (Most Favored Nation) clause compliance audit: the effective rate for
   Titan Sound Group, a label with MFN protection, is lower than that of
   Northline Aggregator, a label without MFN protection that signed later,
   constituting a violation of Titan's own contract terms.

The traps above are injected through deliberately designed correlated
distributions, not independent randomness. The corresponding SQL queries live in
03-social_media_music_blanket_licensing_medium_sql_queries-cn.md, used to expose
these traps.
"""

from __future__ import annotations

import random
from datetime import date
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import Numeric
from sqlalchemy import Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "social_media_music_blanket_licensing_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date, ensuring consistent results across multiple runs,
# independent of the system's current time.
# Wherever the SQL queries need "today", the same literal date is used.
REFERENCE_DATE = date(2026, 6, 30)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================
# Section 4: Business Calibration Constants
# ============================================================

# --- Label tier composition ---
# 3 major labels + 7 mid-size labels + 10 indie aggregator distributors = 20,
# consistent with the ER document.
LABEL_TIER_COUNTS = {
    "major": 3,
    "mid_size": 7,
    "indie_aggregator": 10,
}

# Fixed naming so that Titan Sound Group (trap 4's victim) and Northline
# Aggregator (trap 4's trigger) always appear in the same position across
# generations, making it easier for audit scripts to verify.
MAJOR_LABEL_NAMES = [
    "Titan Sound Group",
    "Meridian Recorded Music",
    "Cascade Harmonic Group",
]
MID_SIZE_LABEL_NAMES = [
    "Bluecrest Music Group",
    "Foundry Sound Partners",
    "Amberlight Recordings",
    "Ironwood Music Co.",
    "Solstice Recorded Arts",
    "Harborline Music Group",
    "Redwood Sound Partners",
]
INDIE_AGGREGATOR_NAMES = [
    "Northline Aggregator",
    "Coastal Wave Distribution",
    "Fernway Music Collective",
    "Basecamp Sound Aggregation",
    "Driftwood Indie Alliance",
    "Signal Path Music",
    "Lowlight Aggregator Group",
    "Tenfold Music Distribution",
    "Greenroom Indie Network",
    "Anchor Point Aggregation",
]

# --- Catalog usage share assumptions (at contract signing) ---
# Major labels have strong bargaining power, so their share assumptions are
# typically higher; indie aggregator distributors are just starting out, so
# their share assumptions are very low.
USAGE_SHARE_ASSUMPTION_RANGE_BY_TIER = {
    "major": (16.0, 26.0),
    "mid_size": (5.0, 12.0),
    "indie_aggregator": (1.0, 5.0),
}
NORTHLINE_USAGE_SHARE_ASSUMPTION_PCT = 3.0  # Northline's share seed before normalization; after the field-wide normalization to a total of 100%, it comes out to about 1.74 (the final value stored in the database). What trap 4 actually relies on is its effective rate (NORTHLINE_EFFECTIVE_RATE_USD = 800k); the annual fee is derived backward as "share x rate", so this rate is unaffected by normalization

# --- Contract term and effective dates ---
CONTRACT_TERM_MONTHS_BY_TIER = {
    "major": 36,
    "mid_size": 36,
    "indie_aggregator": 24,
}
CONTRACT_START_RANGE_BY_TIER = {
    # (lower bound, upper bound of start date) -- major labels signed earliest,
    # indie aggregator distributors generally sign later, echoing the industry
    # backstory of "emerging aggregator distributors grabbing catalog with
    # aggressive offers." Every interval guarantees
    # start + contract term > REFERENCE_DATE, i.e. a "currently active contract"
    # genuinely has not expired yet as of the reference date (otherwise
    # is_current=TRUE but contract_end_date has already passed, which would be
    # self-contradictory).
    "major": (date(2023, 8, 1), date(2024, 7, 1)),
    "mid_size": (date(2023, 8, 1), date(2024, 10, 1)),
    "indie_aggregator": (date(2024, 8, 1), date(2025, 8, 1)),
}
NORTHLINE_CONTRACT_START_DATE = date(2026, 1, 15)  # Signed most recently, the key setup for trap 4

# --- MFN (Most Favored Nation) clause coverage ---
# All 3 major labels have MFN protection (strongest bargaining power); 2
# randomly chosen mid-size labels have MFN; indie aggregator distributors have
# no MFN protection at all (just starting out, no bargaining leverage).
MFN_HOLDER_COUNT_MID_SIZE = 2

# --- Effective rate (annual fee per 1 percentage point of catalog usage
# share, in USD) ---
# This group of constants is the core of trap 4 (MFN compliance): carefully
# constructed so that there is exactly one, and only one, MFN violation case.
EFFECTIVE_RATE_RANGE_NON_MFN_INDIE = (280_000.0, 480_000.0)
EFFECTIVE_RATE_RANGE_NON_MFN_MID = (430_000.0, 620_000.0)
# Northline's effective rate is deliberately set to the highest among all
# non-MFN labels, and noticeably higher than Titan's.
NORTHLINE_EFFECTIVE_RATE_USD = 800_000.0
# Titan's effective rate is deliberately set lower than Northline's,
# constituting a violation of Titan's own MFN clause.
TITAN_EFFECTIVE_RATE_RANGE = (680_000.0, 750_000.0)
# The remaining MFN-protected labels have their effective rate set safely
# above max(non-MFN rate), so they do not constitute a violation.
OTHER_MFN_RATE_MULTIPLIER_RANGE = (1.05, 1.20)

# --- Catalog size ---
NUM_OFFICIAL_TRACKS_BY_TIER = {
    "major": 50,  # 3 x 50 = 150
    "mid_size": 20,  # 7 x 20 = 140
    "indie_aggregator": 11,  # 10 x 11 = 110
}  # Total official tracks about 400, consistent with the ER document
NUM_SAMPLING_REMIXES = 130  # UGC remixes that sample official tracks
NUM_ORIGINAL_REMIXES = 70  # UGC remixes that are fully original and sample no official tracks
NUM_MONITORED_REMIXES = 120  # "Trending candidate sounds" selected by popularity score, the only ones with daily fine-grained data

GENRE_WEIGHTS = {
    "Pop": 0.30,
    "Hip-Hop": 0.22,
    "Electronic": 0.16,
    "R&B": 0.12,
    "Country": 0.10,
    "Indie Rock": 0.06,
    "Latin": 0.04,
}

# --- Song title vocabulary ---
# Official track and original remix titles are assembled from "adjective +
# noun / noun phrase / verb + noun" combinations to read like real song
# titles, rather than fake.catch_phrase()-style corporate slogans (e.g.
# "Multi-tiered local intranet"), so that a music rights dataset reads as
# credible. Sampling-type remixes instead use "noun stem + remix suffix" (e.g.
# "midnight sped up"), building on the realism of sound.title.
SONG_TITLE_ADJECTIVES = [
    "Golden", "Midnight", "Neon", "Velvet", "Electric", "Silent", "Crimson",
    "Faded", "Wild", "Lonely", "Endless", "Broken", "Sacred", "Frozen",
    "Restless", "Hollow", "Gilded", "Distant", "Reckless", "Fading",
    "Scarlet", "Amber", "Cosmic", "Paper", "Weightless", "Feral",
]
SONG_TITLE_NOUNS = [
    "Hearts", "Nights", "Dreams", "Echoes", "Skyline", "Horizon", "Fire",
    "Rain", "Waves", "Shadows", "Lights", "Roads", "Summer", "Ghosts",
    "Static", "Neon", "Fever", "Bloom", "Static", "Currents", "Embers",
    "Mirage", "Gravity", "Silhouette", "Riptide", "Afterglow", "Lullaby",
]
SONG_TITLE_VERBS = [
    "Chasing", "Losing", "Breaking", "Falling", "Burning", "Dancing",
    "Drowning", "Running", "Fading", "Holding",
]
REMIX_TITLE_SUFFIXES = ["remix", "sped up", "slowed + reverb", "freestyle over it"]

# --- Creator composition ---
NUM_CREATORS = 150
CREATOR_TIER_WEIGHTS = {"top": 0.10, "mid": 0.30, "long_tail": 0.60}
# Creator Fund payout tier multiplier: top creators generally produce higher
# content/production quality, giving them a slight bonus.
CREATOR_TIER_QUALITY_MULTIPLIER = {"top": 1.15, "mid": 1.00, "long_tail": 0.90}

# --- Catalog usage share drift (trap 1) ---
# Among the 20 labels, 5 are "growth" type with rising share, 4 are "decline"
# type with falling share, and 11 are "stable" with essentially unchanged
# share (only absorbing a small residual adjustment); the 3 major labels are
# always classified as stable (see `_pick_drift_targets` for why). Both
# growth/decline use "multiply by the signing assumption" rather than
# adding/subtracting a fixed percentage point, to avoid small-share labels
# being pushed negative; the multiplier ranges are calibrated so the two
# groups' total movement is roughly comparable.
USAGE_SHARE_DRIFT_GROWTH_COUNT = 5
USAGE_SHARE_DRIFT_DECLINE_COUNT = 4
USAGE_SHARE_DRIFT_GROWTH_MULTIPLIER_RANGE = (1.4, 1.8)  # Target share is 1.4-1.8x the signing assumption
USAGE_SHARE_DRIFT_DECLINE_MULTIPLIER_RANGE = (0.25, 0.45)  # Target share shrinks to 25%-45% of the signing assumption
# Hard cap/floor on a single label's pp-level drift: growth/decline slots are
# preferentially assigned to mid_size labels with a larger share base (see
# `_pick_drift_targets`); if a large-share label draws an extreme multiplier,
# pure multiplication could produce a drift of over +5pp, exceeding the
# documented "+1~+4.5pp / -2~-4.8pp" range. The absolute drift is capped here
# so the signal stays significant while reliably landing within the documented
# range (not binding for small-share labels, since their multiplier naturally
# never produces such a large pp).
USAGE_SHARE_DRIFT_MAX_GROWTH_PP = 4.1
USAGE_SHARE_DRIFT_MAX_DECLINE_PP = 4.4

# --- Monthly catalog usage pool ---
USAGE_MONTHS_COUNT = 18  # 2025-01 through 2026-06
LABELED_POOL_BASE_VIDEOS = 520_000  # Total videos attributable to some label in 2025-01
LABELED_POOL_MONTHLY_GROWTH = 1.018  # Month-over-month growth
ORIGINAL_POOL_BASE_VIDEOS = 55_000  # Total videos for fully original remixes in 2025-01
ORIGINAL_POOL_MONTHLY_GROWTH = 1.025

# --- Rights conflict flags (trap 2) ---
RIGHTS_CONFLICT_FLAG_RATE = 0.45  # About 45% of the 130 sampling remixes get flagged
CONFLICT_TYPE_WEIGHTS = {
    "unauthorized_sample": 0.55,
    "mismatched_metadata": 0.25,
    "duplicate_claim": 0.20,
}
RESOLUTION_STATUS_WEIGHTS = {
    "cleared": 0.28,
    "licensed_retroactively": 0.14,
    "takedown": 0.10,
    "under_review": 0.26,
    "open": 0.22,
}
SLA_DAYS_TARGET = 30
# About half of resolved records actually take longer than the SLA to
# process, creating a genuine "slow processing" problem; calibrated to 0.52 so
# that the overall overdue share across all flags reliably lands in the
# documented 60%-65% range.
RESOLVED_LATE_PROBABILITY = 0.52
RESOLVED_ON_TIME_DAYS_RANGE = (5, 29)
RESOLVED_LATE_DAYS_RANGE = (31, 70)

# --- Creator Fund payouts (trap 3) ---
CREATOR_FUND_BASE_RATE_PER_1000_VIEWS = 1.20  # USD, matches the base rate for the aligned case
# Sounds whose viral window straddles calendar weeks have their effective rate
# discounted by 30% -- this is the quantitative definition of trap 3 (payout
# per thousand views is about 28%-30% lower than for aligned sounds,
# calibrated to 0.70 so the aggregate metric reliably lands in the documented
# range).
SPLIT_WEEK_ALIGNMENT_PENALTY_MULTIPLIER = 0.70
ACTIVE_WEEKS_LOOKBACK = 52  # Creator Fund weekly payouts cover the most recent 52 weeks
SPIKE_VIEW_MULTIPLIER_RANGE = (12.0, 30.0)  # Multiplier for viral-week views relative to baseline

# --- Daily viral window (only for the 120 monitored sounds) ---
DAILY_WINDOW_DAYS_BEFORE_SPIKE = 20
DAILY_WINDOW_DAYS_AFTER_SPIKE = 24  # 45-day window in total
DAILY_SPIKE_CORE_MULTIPLIER_RANGE = (15.0, 40.0)
DAILY_SHOULDER_MULTIPLIER_RANGE = (3.0, 8.0)  # Transition multiplier for the 1-2 days before/after the viral core days


def add_months(start: date, n: int) -> date:
    """Given the first day of the month containing `start`, advance n months
    forward, returning the first day of the target month."""
    month_index = start.month - 1 + n
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def most_recent_monday(d: date) -> date:
    """Return the most recent Monday on or before d."""
    return d - timedelta(days=d.weekday())


def compute_spike_anchor_date(sound: dict) -> date:
    """Compute the anchor date for a trending candidate sound's viral core.
    Both `creator_fund_weekly_payout` (which decides which week or two weeks
    get the spike multiplier) and `sound_daily_viral_window` (which decides
    where the 45-day fine-grained window is centered) call this function,
    ensuring the same sound has an identical viral timing point across both
    tables, so the "viral week" in the weekly payout table and the "viral day"
    in the daily curve never disagree. An independent random source is derived
    from sound_id (rather than the shared global random state), so results are
    identical regardless of which table's generator function is called first.
    """
    local_rng = random.Random(RANDOM_SEED * 1_000_003 + sound["id"])
    release = sound["release_date"]
    if sound["spike_week_alignment"] == "aligned":
        candidate_weekdays = (1, 2)  # Tuesday/Wednesday, ensuring the 3-4 day core window doesn't cross a calendar week boundary
    else:
        candidate_weekdays = (5,)  # Saturday, letting the core window spill into next Monday/Tuesday
    # The viral core date must ensure the 45-day window [core-20, core+24]
    # falls entirely within [release_date, REFERENCE_DATE]; otherwise
    # sound_daily_viral_window would generate future dates past the reference
    # date, breaking the semantics of "all data anchored to a fixed snapshot
    # date."
    #   Lower bound: prefer release+60 (a more realistic build-up period); if a
    #   very late release makes the 60-day window go out of bounds, fall back
    #   to release+20 (so the window's leading edge is not earlier than
    #   release_date).
    #   Upper bound: min(release+320, REFERENCE_DATE-25), the latter ensuring
    #   the window's tail (+24 days) does not go past the reference date,
    #   leaving 1 day of margin.
    latest_valid = REFERENCE_DATE - timedelta(days=25)
    lower = release + timedelta(days=60)
    if lower > latest_valid:
        lower = release + timedelta(days=20)
    upper = min(release + timedelta(days=320), latest_valid)
    if lower > upper:
        # Extremely late release, not even the minimum window fits: clamp
        # directly to the latest valid anchor.
        return latest_valid
    candidates = [
        offset
        for offset in range((lower - release).days, (upper - release).days + 1)
        if (release + timedelta(days=offset)).weekday() in candidate_weekdays
    ]
    if candidates:
        return release + timedelta(days=local_rng.choice(candidates))
    # No matching weekday found within the valid range (an extremely narrow
    # window): clamp to the latest valid anchor to guarantee no out-of-bounds.
    return latest_valid


def weighted_choice(weights: dict[str, float]) -> str:
    """Perform a single weighted draw from the weights given in the dict,
    returning the chosen key."""
    keys = list(weights.keys())
    values = list(weights.values())
    return random.choices(keys, weights=values, k=1)[0]


def make_song_title() -> str:
    """Assemble a short "song-like" title from the vocabulary lists, used for
    official tracks and original remixes. Randomly switches among a few
    common song title patterns (adjective+noun / noun in the noun /
    single noun / verb+noun) to create enough variety while retaining a
    musical feel."""
    noun = random.choice(SONG_TITLE_NOUNS)
    roll = random.random()
    if roll < 0.40:
        return f"{random.choice(SONG_TITLE_ADJECTIVES)} {noun}"
    if roll < 0.68:
        other = random.choice(SONG_TITLE_NOUNS)
        while other == noun:
            other = random.choice(SONG_TITLE_NOUNS)
        return f"{noun} in the {other}"
    if roll < 0.85:
        return noun
    return f"{random.choice(SONG_TITLE_VERBS)} {noun}"


USAGE_MONTHS = [add_months(date(2025, 1, 1), i) for i in range(USAGE_MONTHS_COUNT)]
LATEST_MONDAY = most_recent_monday(REFERENCE_DATE)
ALL_WEEK_STARTS = [
    LATEST_MONDAY - timedelta(weeks=i) for i in range(ACTIVE_WEEKS_LOOKBACK)
][::-1]  # Arranged from earliest to most recent


# ============================================================
# Section 5: ORM Models
# ============================================================


class Base(DeclarativeBase):
    pass


class Label(Base):
    """A record label or aggregator distributor that has signed a blanket license contract."""

    __tablename__ = "label"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    label_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    hq_country: Mapped[str] = mapped_column(String(20), nullable=False)
    onboarded_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Creator(Base):
    """A creator who posts UGC remixes on ReelWave and is eligible for Creator Fund payouts."""

    __tablename__ = "creator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    handle: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(20), nullable=False)
    join_date: Mapped[date] = mapped_column(Date, nullable=False)
    creator_tier: Mapped[str] = mapped_column(String(20), nullable=False)


class LabelBlanketLicense(Base):
    """The currently active blanket license contract terms for a label: share assumption, annual fee, MFN protection."""

    __tablename__ = "label_blanket_license"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label_id: Mapped[int] = mapped_column(ForeignKey("label.id"), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    usage_share_assumption_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    annual_license_fee_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    has_mfn_clause: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Sound(Base):
    """A piece of music tracked on the platform: either an official track or a user-created remix."""

    __tablename__ = "sound"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sound_type: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_label_id: Mapped[int | None] = mapped_column(ForeignKey("label.id"))
    source_sound_id: Mapped[int | None] = mapped_column(ForeignKey("sound.id"))
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("creator.id"))
    genre: Mapped[str] = mapped_column(String(30), nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_trending_monitored: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spike_week_alignment: Mapped[str | None] = mapped_column(String(20))
    popularity_score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)


class LicenseFeePayment(Base):
    """A quarterly actual payment record for a blanket license contract."""

    __tablename__ = "license_fee_payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    license_id: Mapped[int] = mapped_column(ForeignKey("label_blanket_license.id"), nullable=False)
    payment_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    payment_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paid_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)


class SoundMonthlyUsage(Base):
    """Monthly video count and view count aggregate for each sound, the raw fact data behind catalog usage share calculations."""

    __tablename__ = "sound_monthly_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    usage_month: Mapped[date] = mapped_column(Date, nullable=False)
    video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False)


class RightsConflictFlag(Base):
    """A UGC remix rights-conflict record flagged for suspected unauthorized sampling or similar reasons."""

    __tablename__ = "rights_conflict_flag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    remix_sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(30), nullable=False)
    flagged_date: Mapped[date] = mapped_column(Date, nullable=False)
    sla_days_target: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(30), nullable=False)
    resolved_date: Mapped[date | None] = mapped_column(Date)
    revenue_at_risk_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class CreatorFundWeeklyPayout(Base):
    """A Creator Fund payout record computed per calendar week for a UGC remix and its creator."""

    __tablename__ = "creator_fund_weekly_payout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    remix_sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.id"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekly_video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_view_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    payout_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class SoundDailyViralWindow(Base):
    """Daily view count detail for the 120 trending candidate sounds within the roughly 45-day window around their viral spike."""

    __tablename__ = "sound_daily_viral_window"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_view_count: Mapped[int] = mapped_column(Integer, nullable=False)


# ============================================================
# Section 6: Generator Functions (topological order)
# ============================================================


def gen_labels() -> pl.DataFrame:
    """Generate 20 labels, with fixed naming to carry trap 4's Titan / Northline case."""
    rows = []
    label_id = 1
    tier_name_pools = {
        "major": MAJOR_LABEL_NAMES,
        "mid_size": MID_SIZE_LABEL_NAMES,
        "indie_aggregator": INDIE_AGGREGATOR_NAMES,
    }
    for tier, names in tier_name_pools.items():
        for name in names:
            if name == "Northline Aggregator":
                onboarded = date(2025, 8, 1)
            elif tier == "major":
                onboarded = fake.date_between(date(2019, 6, 1), date(2020, 12, 1))
            elif tier == "mid_size":
                onboarded = fake.date_between(date(2020, 6, 1), date(2022, 6, 1))
            else:
                onboarded = fake.date_between(date(2021, 6, 1), date(2024, 6, 1))
            rows.append(
                {
                    "id": label_id,
                    "label_name": name,
                    "label_tier": tier,
                    "hq_country": "US" if random.random() < 0.85 else "Canada",
                    "onboarded_date": onboarded,
                    "is_active": True,
                }
            )
            label_id += 1
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_creators() -> pl.DataFrame:
    """Generate 150 creators eligible for the Creator Fund."""
    rows = []
    for creator_id in range(1, NUM_CREATORS + 1):
        tier = weighted_choice(CREATOR_TIER_WEIGHTS)
        rows.append(
            {
                "id": creator_id,
                "handle": f"@{fake.user_name()}.{creator_id}",
                "country": "US" if random.random() < 0.82 else "Canada",
                "join_date": fake.date_between(date(2022, 1, 1), date(2026, 3, 1)),
                "creator_tier": tier,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_label_blanket_licenses(labels_df: pl.DataFrame) -> pl.DataFrame:
    """Generate each label's currently active blanket license contract. Carefully constructs trap 4's single MFN violation case."""
    labels = labels_df.to_dicts()
    by_name = {row["label_name"]: row for row in labels}

    # Step 1: decide who has MFN protection.
    mid_size_labels = [row for row in labels if row["label_tier"] == "mid_size"]
    mfn_mid_size_names = {
        row["label_name"]
        for row in random.sample(mid_size_labels, MFN_HOLDER_COUNT_MID_SIZE)
    }
    has_mfn_by_name = {}
    for row in labels:
        if row["label_tier"] == "major":
            has_mfn_by_name[row["label_name"]] = True
        elif row["label_name"] in mfn_mid_size_names:
            has_mfn_by_name[row["label_name"]] = True
        else:
            has_mfn_by_name[row["label_name"]] = False

    # Step 2: decide the share assumptions. The 20 contracts were negotiated
    # independently, but since together they cover the entire view count of
    # the "attributable catalog," a reasonable approach is to have their share
    # assumptions sum to roughly 100% -- otherwise a systematic scaling bias
    # unrelated to trap 1 would appear between each label's "assumption" and
    # "actual," masking the deliberately designed growth/decline/stable
    # signal.
    raw_usage_share_by_name = {}
    for row in labels:
        if row["label_name"] == "Northline Aggregator":
            raw_usage_share_by_name[row["label_name"]] = NORTHLINE_USAGE_SHARE_ASSUMPTION_PCT
        else:
            low, high = USAGE_SHARE_ASSUMPTION_RANGE_BY_TIER[row["label_tier"]]
            raw_usage_share_by_name[row["label_name"]] = random.uniform(low, high)
    raw_total = sum(raw_usage_share_by_name.values())
    rescale_factor = 100.0 / raw_total
    usage_share_by_name = {
        name: round(value * rescale_factor, 2) for name, value in raw_usage_share_by_name.items()
    }

    # Step 3: first compute the effective rate for all labels "without MFN
    # protection," and find the maximum among them.
    effective_rate_by_name = {}
    for row in labels:
        name = row["label_name"]
        if has_mfn_by_name[name]:
            continue
        if name == "Northline Aggregator":
            effective_rate_by_name[name] = NORTHLINE_EFFECTIVE_RATE_USD
        elif row["label_tier"] == "indie_aggregator":
            effective_rate_by_name[name] = random.uniform(*EFFECTIVE_RATE_RANGE_NON_MFN_INDIE)
        else:
            effective_rate_by_name[name] = random.uniform(*EFFECTIVE_RATE_RANGE_NON_MFN_MID)
    max_non_mfn_rate = max(effective_rate_by_name.values())

    # Step 4: labels with MFN protection. Titan is deliberately set below
    # max_non_mfn_rate (violating MFN); all other MFN labels are set safely
    # above this value (compliant).
    for row in labels:
        name = row["label_name"]
        if not has_mfn_by_name[name]:
            continue
        if name == "Titan Sound Group":
            effective_rate_by_name[name] = random.uniform(*TITAN_EFFECTIVE_RATE_RANGE)
        else:
            effective_rate_by_name[name] = max_non_mfn_rate * random.uniform(
                *OTHER_MFN_RATE_MULTIPLIER_RANGE
            )

    rows = []
    license_id = 1
    for row in labels:
        name = row["label_name"]
        tier = row["label_tier"]
        if name == "Northline Aggregator":
            start = NORTHLINE_CONTRACT_START_DATE
        else:
            low, high = CONTRACT_START_RANGE_BY_TIER[tier]
            start = fake.date_between(low, high)
        term_months = CONTRACT_TERM_MONTHS_BY_TIER[tier]
        end = add_months(start, term_months) - timedelta(days=1)
        usage_share = usage_share_by_name[name]
        effective_rate = effective_rate_by_name[name]
        annual_fee = round(effective_rate * usage_share, 2)
        rows.append(
            {
                "id": license_id,
                "label_id": by_name[name]["id"],
                "contract_start_date": start,
                "contract_end_date": end,
                "usage_share_assumption_pct": usage_share,
                "annual_license_fee_usd": annual_fee,
                "has_mfn_clause": has_mfn_by_name[name],
                "is_current": True,
            }
        )
        license_id += 1
    return pl.DataFrame(rows, infer_schema_length=None)


def _pick_drift_targets(labels: list[dict]) -> dict[int, str]:
    """Split the 20 labels into growth / decline / stable categories, with
    Northline fixed as growth, Titan fixed as stable, and the rest assigned
    randomly, matching the 5/4/11 distribution specified by the ER document.

    All 3 major labels are always classified as stable: a major label's
    catalog is spread across hundreds or thousands of songs, so its monthly
    share is already unlikely to swing wildly from one or two songs; also, if
    major labels with a share base of 15%+ also participated in large
    growth/decline drift, the zero-sum constraint would require moving so
    much share that it would drag the stable group along with it -- see the
    explanation in gen_sound_monthly_usage.
    """
    eligible = [
        row
        for row in labels
        if row["label_tier"] != "major" and row["label_name"] != "Northline Aggregator"
    ]
    random.shuffle(eligible)
    # Preferentially assign growth/decline slots to mid_size labels: their
    # normalized share base (roughly 3-8pp) is noticeably larger than indie
    # aggregator distributors (roughly 1-2.5pp), so multiplying by the drift
    # multiplier produces a more significant pp-level drift, reliably landing
    # within the documented +1~+4.5pp / -2~-4.8pp range; if the slots were
    # randomly assigned to tiny-share indie distributors, the drift signal
    # would be flattened to within ±1pp and lose its teaching impact.
    # sorted is a stable sort, so the mid_size subgroup still retains the
    # random order produced by the shuffle above.
    remaining = sorted(eligible, key=lambda r: 0 if r["label_tier"] == "mid_size" else 1)
    drift_type_by_id = {}
    for row in labels:
        if row["label_name"] == "Northline Aggregator":
            drift_type_by_id[row["id"]] = "growth"
        elif row["label_tier"] == "major":
            drift_type_by_id[row["id"]] = "stable"
    remaining_growth = USAGE_SHARE_DRIFT_GROWTH_COUNT - 1  # Northline already occupies one growth slot
    remaining_decline = USAGE_SHARE_DRIFT_DECLINE_COUNT
    idx = 0
    for _ in range(remaining_growth):
        drift_type_by_id[remaining[idx]["id"]] = "growth"
        idx += 1
    for _ in range(remaining_decline):
        drift_type_by_id[remaining[idx]["id"]] = "decline"
        idx += 1
    while idx < len(remaining):
        drift_type_by_id[remaining[idx]["id"]] = "stable"
        idx += 1
    return drift_type_by_id


def gen_sounds(labels_df: pl.DataFrame, creators_df: pl.DataFrame) -> pl.DataFrame:
    """Generate 600 sounds: 400 official tracks + 200 UGC remixes (including self-referencing sampling relationships)."""
    labels = labels_df.to_dicts()
    creator_ids = creators_df["id"].to_list()

    rows = []
    sound_id = 1
    official_track_ids_by_label: dict[int, list[int]] = {row["id"]: [] for row in labels}
    all_official_track_ids: list[int] = []
    official_popularity: dict[int, float] = {}
    official_release_by_id: dict[int, date] = {}

    # Official tracks: all released before the start of the catalog usage
    # window (2025-01-01), ensuring a complete catalog exists from the start
    # of the contract term.
    for row in labels:
        n_tracks = NUM_OFFICIAL_TRACKS_BY_TIER[row["label_tier"]]
        for _ in range(n_tracks):
            popularity = min(8.0, random.paretovariate(2.3))
            release = fake.date_between(date(2021, 1, 1), date(2024, 12, 1))
            rows.append(
                {
                    "id": sound_id,
                    "title": make_song_title(),
                    "sound_type": "official_track",
                    "primary_label_id": row["id"],
                    "source_sound_id": None,
                    "creator_id": None,
                    "genre": weighted_choice(GENRE_WEIGHTS),
                    "release_date": release,
                    "is_trending_monitored": False,
                    "spike_week_alignment": None,
                    "popularity_score": round(popularity, 4),
                }
            )
            official_track_ids_by_label[row["id"]].append(sound_id)
            all_official_track_ids.append(sound_id)
            official_popularity[sound_id] = popularity
            official_release_by_id[sound_id] = release
            sound_id += 1

    # The source official track for sampling remixes is drawn with weights
    # proportional to popularity, so more popular official tracks are more
    # likely to be sampled; the actual candidates are further filtered below
    # by "release date earlier than the remix" before weighting (see the
    # is_sampling branch).

    # First give every creator a guaranteed baseline of one remix, ensuring
    # all 150 creators have at least one work; the remaining remix slots are
    # then drawn with weights by creator tier, creating a realistic
    # distribution where "some creators have multiple remixes."
    creator_tier_by_id = dict(zip(creators_df["id"].to_list(), creators_df["creator_tier"].to_list()))
    tier_weight_for_extra = {"top": 3.0, "mid": 1.5, "long_tail": 1.0}
    total_remixes = NUM_SAMPLING_REMIXES + NUM_ORIGINAL_REMIXES
    remix_creator_ids = list(creator_ids)  # The first 150 remixes are the guaranteed baseline allocation
    extra_count = total_remixes - len(creator_ids)
    extra_weights = [tier_weight_for_extra[creator_tier_by_id[cid]] for cid in creator_ids]
    remix_creator_ids += random.choices(creator_ids, weights=extra_weights, k=extra_count)
    random.shuffle(remix_creator_ids)

    remix_popularity: dict[int, float] = {}
    remix_release_dates: dict[int, date] = {}
    remix_ids: list[int] = []
    remix_creator_map: dict[int, int] = {}
    remix_source_map: dict[int, int | None] = {}

    creator_cursor = 0
    for i in range(total_remixes):
        is_sampling = i < NUM_SAMPLING_REMIXES
        popularity = min(6.0, random.paretovariate(2.1))
        release = fake.date_between(date(2024, 6, 1), date(2026, 5, 15))
        creator_id = remix_creator_ids[creator_cursor]
        creator_cursor += 1
        if is_sampling:
            # The sampled source must be released earlier than the remix
            # itself (ER timing rule: sampled official track's release_date <
            # remix.release_date). All official tracks predate 2025-01-01, and
            # the earliest remix is 2024-06, so eligible candidates are always
            # non-empty; still drawn with weighting by popularity.
            eligible_source_ids = [
                sid for sid in all_official_track_ids if official_release_by_id[sid] < release
            ]
            eligible_weights = [official_popularity[sid] for sid in eligible_source_ids]
            source_id = random.choices(eligible_source_ids, weights=eligible_weights, k=1)[0]
            title_suffix = random.choice(REMIX_TITLE_SUFFIXES)
            title = f"{random.choice(SONG_TITLE_NOUNS).lower()} {title_suffix}"
        else:
            source_id = None
            title = make_song_title()
        rows.append(
            {
                "id": sound_id,
                "title": title,
                "sound_type": "ugc_remix",
                "primary_label_id": None,
                "source_sound_id": source_id,
                "creator_id": creator_id,
                "genre": weighted_choice(GENRE_WEIGHTS),
                "release_date": release,
                "is_trending_monitored": False,  # Backfilled below once sorted by popularity
                "spike_week_alignment": None,
                "popularity_score": round(popularity, 4),
            }
        )
        remix_popularity[sound_id] = popularity
        remix_release_dates[sound_id] = release
        remix_ids.append(sound_id)
        remix_creator_map[sound_id] = creator_id
        remix_source_map[sound_id] = source_id
        sound_id += 1

    # Select the top 120 by popularity score as "trending candidate sounds,"
    # half aligned and half split_across_weeks.
    monitored_ids = sorted(remix_ids, key=lambda sid: remix_popularity[sid], reverse=True)[
        :NUM_MONITORED_REMIXES
    ]
    monitored_set = set(monitored_ids)
    alignment_pool = ["aligned"] * (NUM_MONITORED_REMIXES // 2) + ["split_across_weeks"] * (
        NUM_MONITORED_REMIXES - NUM_MONITORED_REMIXES // 2
    )
    random.shuffle(alignment_pool)
    alignment_by_id = dict(zip(monitored_ids, alignment_pool))

    for r in rows:
        if r["id"] in monitored_set:
            r["is_trending_monitored"] = True
            r["spike_week_alignment"] = alignment_by_id[r["id"]]

    return pl.DataFrame(rows, infer_schema_length=None)


def gen_license_fee_payments(licenses_df: pl.DataFrame) -> pl.DataFrame:
    """Generate all actual quarterly payment records from each contract's signing date through the reference date (no lookback-period cap).

    Query 14 uses "proportion of contract elapsed time x annual fee" as the
    "expected payment based on time progress," so the actual payments must
    completely cover the period from the signing date to the reference date
    for the cumulative actual to align with the expected basis. If, as in an
    earlier version, only the most recent 2 years (8 periods) were kept, a
    major label's 3-year-old contract would have an "expected" computed over
    2.5-2.9 years while the actual only covers 2 years, producing a
    million-dollar-scale systematic shortfall out of nowhere, directly
    conflicting with Query 14's teaching expectation of "only a natural lag
    from quarterly payment in arrears." Now the only remaining difference is
    the lag from "the current period not yet settled" (quarterly payment in
    arrears), capped at one quarter's worth of annual fee.
    """
    rows = []
    payment_id = 1
    for lic in licenses_df.to_dicts():
        quarterly_amount = round(lic["annual_license_fee_usd"] / 4.0, 2)
        period_start = lic["contract_start_date"]
        while period_start <= REFERENCE_DATE:
            period_end = add_months(period_start, 3) - timedelta(days=1)
            if period_end > REFERENCE_DATE:
                break
            amount = round(quarterly_amount * random.uniform(0.99, 1.01), 2)
            payment_date = period_end + timedelta(days=random.randint(10, 20))
            rows.append(
                {
                    "id": payment_id,
                    "license_id": lic["id"],
                    "payment_period_start": period_start,
                    "payment_period_end": period_end,
                    "amount_paid_usd": amount,
                    "payment_date": payment_date,
                }
            )
            payment_id += 1
            period_start = add_months(period_start, 3)
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_sound_monthly_usage(sounds_df: pl.DataFrame, labels_df: pl.DataFrame, licenses_df: pl.DataFrame) -> pl.DataFrame:
    """Generate 18 months of monthly usage data, carefully constructing trap 1 (catalog usage share drift)."""
    labels = labels_df.to_dicts()
    licenses = licenses_df.to_dicts()
    usage_share_assumption_by_label_id = {lic["label_id"]: lic["usage_share_assumption_pct"] for lic in licenses}
    drift_type_by_label_id = _pick_drift_targets(labels)

    # Catalog usage share is zero-sum (the shares of the 20 labels always sum
    # to 100%): whatever share any one label gains must come from another
    # label's loss. growth uses "multiply by a multiplier" rather than adding
    # a fixed percentage point, so no matter which label is drawn, the target
    # can never be negative, and no extra lower-bound protection is needed.
    # The growth and decline multiplier ranges are calibrated so that the two
    # groups' total "share movement" is roughly comparable (the growth group
    # gains on average about 60% of its own share, the decline group loses on
    # average about 65% of its own share; both groups are drawn only from the
    # 9 labels outside the major tier, see `_pick_drift_targets`), let the two
    # groups approximately self-balance internally. The remaining small
    # imbalance is distributed proportionally by label size across the 11
    # stable labels (including all 3 major labels); the residual is usually
    # small, so the adjustment each label receives is negligible.
    stable_ids = [lid for lid, t in drift_type_by_label_id.items() if t == "stable"]
    growth_ids = [lid for lid, t in drift_type_by_label_id.items() if t == "growth"]
    decline_ids = [lid for lid, t in drift_type_by_label_id.items() if t == "decline"]

    final_target_share_by_label_id = {}
    for lid in growth_ids:
        assumption = usage_share_assumption_by_label_id[lid]
        target = assumption * random.uniform(*USAGE_SHARE_DRIFT_GROWTH_MULTIPLIER_RANGE)
        # pp-level hard cap: when a large-share label draws a high multiplier, the absolute drift does not exceed about +4.5pp.
        final_target_share_by_label_id[lid] = min(target, assumption + USAGE_SHARE_DRIFT_MAX_GROWTH_PP)
    for lid in decline_ids:
        assumption = usage_share_assumption_by_label_id[lid]
        target = assumption * random.uniform(*USAGE_SHARE_DRIFT_DECLINE_MULTIPLIER_RANGE)
        # pp-level hard floor: absolute drift does not go below about -4.8pp.
        final_target_share_by_label_id[lid] = max(target, assumption - USAGE_SHARE_DRIFT_MAX_DECLINE_PP)
    for lid in stable_ids:
        final_target_share_by_label_id[lid] = usage_share_assumption_by_label_id[lid]

    residual = 100.0 - sum(final_target_share_by_label_id.values())
    stable_total_assumption = sum(usage_share_assumption_by_label_id[lid] for lid in stable_ids)
    for lid in stable_ids:
        weight = usage_share_assumption_by_label_id[lid] / stable_total_assumption
        final_target_share_by_label_id[lid] += residual * weight

    sounds = sounds_df.to_dicts()
    official_tracks_by_label: dict[int, list[dict]] = {row["id"]: [] for row in labels}
    official_track_by_id: dict[int, dict] = {}
    for s in sounds:
        if s["sound_type"] == "official_track":
            official_tracks_by_label[s["primary_label_id"]].append(s)
            official_track_by_id[s["id"]] = s

    sampling_remixes_by_label: dict[int, list[dict]] = {row["id"]: [] for row in labels}
    original_remixes: list[dict] = []
    for s in sounds:
        if s["sound_type"] != "ugc_remix":
            continue
        if s["source_sound_id"] is not None:
            source_label_id = official_track_by_id[s["source_sound_id"]]["primary_label_id"]
            sampling_remixes_by_label[source_label_id].append(s)
        else:
            original_remixes.append(s)

    rows = []
    usage_id = 1

    for month_index, month in enumerate(USAGE_MONTHS):
        # Each month's per-label share: linearly interpolate from the signing
        # assumption to that label's final target share, add noise, then
        # normalize.
        raw_shares = {}
        for row in labels:
            assumption = usage_share_assumption_by_label_id[row["id"]]
            target = final_target_share_by_label_id[row["id"]]
            progress = month_index / (USAGE_MONTHS_COUNT - 1)
            share = assumption + (target - assumption) * progress + random.uniform(-0.4, 0.4)
            raw_shares[row["id"]] = max(0.5, min(35.0, share))
        share_sum = sum(raw_shares.values())
        normalized_shares = {lid: value / share_sum * 100.0 for lid, value in raw_shares.items()}

        pool = LABELED_POOL_BASE_VIDEOS * (LABELED_POOL_MONTHLY_GROWTH**month_index)

        for row in labels:
            label_id = row["id"]
            label_videos = pool * normalized_shares[label_id] / 100.0
            eligible = list(official_tracks_by_label[label_id])
            for remix in sampling_remixes_by_label[label_id]:
                if remix["release_date"] <= month:
                    eligible.append(remix)
            weight_sum = sum(s["popularity_score"] for s in eligible)
            if weight_sum <= 0:
                continue
            for s in eligible:
                video_count = max(1, round(label_videos * s["popularity_score"] / weight_sum))
                avg_views_per_video = 300.0 * (1.0 + s["popularity_score"]) * random.uniform(0.85, 1.15)
                view_count = max(video_count, round(video_count * avg_views_per_video))
                rows.append(
                    {
                        "id": usage_id,
                        "sound_id": s["id"],
                        "usage_month": month,
                        "video_count": video_count,
                        "view_count": view_count,
                    }
                )
                usage_id += 1

        # Fully original remix usage comes from an independent, smaller pool, unrelated to any label.
        original_pool = ORIGINAL_POOL_BASE_VIDEOS * (ORIGINAL_POOL_MONTHLY_GROWTH**month_index)
        eligible_original = [s for s in original_remixes if s["release_date"] <= month]
        weight_sum = sum(s["popularity_score"] for s in eligible_original)
        if weight_sum > 0:
            for s in eligible_original:
                video_count = max(1, round(original_pool * s["popularity_score"] / weight_sum))
                avg_views_per_video = 280.0 * (1.0 + s["popularity_score"]) * random.uniform(0.85, 1.15)
                view_count = max(video_count, round(video_count * avg_views_per_video))
                rows.append(
                    {
                        "id": usage_id,
                        "sound_id": s["id"],
                        "usage_month": month,
                        "video_count": video_count,
                        "view_count": view_count,
                    }
                )
                usage_id += 1

    return pl.DataFrame(rows, infer_schema_length=None)


def gen_rights_conflict_flags(sounds_df: pl.DataFrame) -> pl.DataFrame:
    """Generate rights-conflict flags, carefully constructing trap 2 (about 45%-55% of the records constitute SLA overdue)."""
    sampling_remixes = sounds_df.filter(
        (pl.col("sound_type") == "ugc_remix") & (pl.col("source_sound_id").is_not_null())
    ).to_dicts()
    n_flagged = round(len(sampling_remixes) * RIGHTS_CONFLICT_FLAG_RATE)
    flagged_remixes = random.sample(sampling_remixes, n_flagged)

    rows = []
    flag_id = 1
    for remix in flagged_remixes:
        release = remix["release_date"]
        latest_possible = REFERENCE_DATE - timedelta(days=5)
        earliest_possible = release + timedelta(days=7)
        if earliest_possible >= latest_possible:
            continue
        flagged_date = fake.date_between(earliest_possible, latest_possible)
        resolution_status = weighted_choice(RESOLUTION_STATUS_WEIGHTS)

        resolved_date = None
        if resolution_status in ("cleared", "licensed_retroactively", "takedown"):
            if random.random() < RESOLVED_LATE_PROBABILITY:
                days = random.randint(*RESOLVED_LATE_DAYS_RANGE)
            else:
                days = random.randint(*RESOLVED_ON_TIME_DAYS_RANGE)
            candidate = flagged_date + timedelta(days=days)
            resolved_date = min(candidate, REFERENCE_DATE)

        revenue_at_risk = round(
            400.0 + remix["popularity_score"] * 2500.0 + random.uniform(-200.0, 800.0), 2
        )
        revenue_at_risk = max(300.0, revenue_at_risk)

        rows.append(
            {
                "id": flag_id,
                "remix_sound_id": remix["id"],
                "conflict_type": weighted_choice(CONFLICT_TYPE_WEIGHTS),
                "flagged_date": flagged_date,
                "sla_days_target": SLA_DAYS_TARGET,
                "resolution_status": resolution_status,
                "resolved_date": resolved_date,
                "revenue_at_risk_usd": revenue_at_risk,
            }
        )
        flag_id += 1
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_creator_fund_weekly_payouts(sounds_df: pl.DataFrame, creators_df: pl.DataFrame) -> pl.DataFrame:
    """Generate Creator Fund weekly payout records, carefully constructing trap 3 (cross-week sounds have an effective rate about 28% lower)."""
    creator_tier_by_id = dict(zip(creators_df["id"].to_list(), creators_df["creator_tier"].to_list()))
    remixes = sounds_df.filter(pl.col("sound_type") == "ugc_remix").to_dicts()

    rows = []
    payout_id = 1
    week_view_accumulator: dict[date, list[dict]] = {w: [] for w in ALL_WEEK_STARTS}

    for remix in remixes:
        remix_monday = most_recent_monday(remix["release_date"])
        active_weeks = [w for w in ALL_WEEK_STARTS if w >= remix_monday]
        if not active_weeks:
            continue

        # For trending candidate sounds, select the viral week (one week or
        # two adjacent weeks) that determines when the spike multiplier
        # applies. The viral anchor date shares the same computation function
        # with sound_daily_viral_window, ensuring both tables use a fully
        # consistent viral timing point for the same sound.
        active_weeks_set = set(active_weeks)
        spike_weeks: set[date] = set()
        if remix["is_trending_monitored"]:
            spike_anchor = compute_spike_anchor_date(remix)
            spike_monday = most_recent_monday(spike_anchor)
            if remix["spike_week_alignment"] == "aligned":
                candidate_weeks = {spike_monday}
            else:
                candidate_weeks = {spike_monday, spike_monday + timedelta(weeks=1)}
            spike_weeks = candidate_weeks & active_weeks_set

        tier = creator_tier_by_id[remix["creator_id"]]
        quality_multiplier = CREATOR_TIER_QUALITY_MULTIPLIER[tier]
        alignment_multiplier = 1.0
        if remix["spike_week_alignment"] == "split_across_weeks":
            alignment_multiplier = SPLIT_WEEK_ALIGNMENT_PENALTY_MULTIPLIER

        baseline_weekly_views = 150.0 + remix["popularity_score"] * 3500.0

        for week in active_weeks:
            noise = random.uniform(0.7, 1.3)
            weekly_view_count = baseline_weekly_views * noise
            if week in spike_weeks:
                weekly_view_count *= random.uniform(*SPIKE_VIEW_MULTIPLIER_RANGE)
            weekly_view_count = max(50, round(weekly_view_count))
            weekly_video_count = max(1, round(weekly_view_count / (400.0 + remix["popularity_score"] * 100.0)))
            payout_usd = round(
                weekly_view_count / 1000.0
                * CREATOR_FUND_BASE_RATE_PER_1000_VIEWS
                * quality_multiplier
                * alignment_multiplier,
                2,
            )
            row = {
                "id": payout_id,
                "remix_sound_id": remix["id"],
                "creator_id": remix["creator_id"],
                "week_start_date": week,
                "weekly_video_count": weekly_video_count,
                "weekly_view_count": weekly_view_count,
                "snapshot_rank": 0,  # Backfilled below after ranking is computed per week
                "payout_usd": payout_usd,
            }
            rows.append(row)
            week_view_accumulator[week].append(row)
            payout_id += 1

    for week, week_rows in week_view_accumulator.items():
        ranked = sorted(week_rows, key=lambda r: r["weekly_view_count"], reverse=True)
        for rank, row in enumerate(ranked, start=1):
            row["snapshot_rank"] = rank

    return pl.DataFrame(rows, infer_schema_length=None)


def gen_sound_daily_viral_window(sounds_df: pl.DataFrame) -> pl.DataFrame:
    """Generate daily view detail for the 120 trending candidate sounds, so that
    the aligned/split_across_weeks sounds have their viral peak land,
    respectively, within a single calendar week or spanning two calendar
    weeks. The viral anchor date comes from `compute_spike_anchor_date`, and
    corresponds exactly to the calendar week in which the same sound's spike
    multiplier is applied in creator_fund_weekly_payout, making it easy for
    case analyses to cross-check the day-by-day curve against the weekly
    payout."""
    monitored = sounds_df.filter(pl.col("is_trending_monitored")).to_dicts()

    rows = []
    row_id = 1
    for s in monitored:
        spike_core_start = compute_spike_anchor_date(s)
        core_duration = random.randint(3, 4)
        window_start = spike_core_start - timedelta(days=DAILY_WINDOW_DAYS_BEFORE_SPIKE)
        window_end = spike_core_start + timedelta(days=DAILY_WINDOW_DAYS_AFTER_SPIKE)

        baseline_daily_views = 60.0 + s["popularity_score"] * 200.0
        current = window_start
        while current <= window_end:
            days_from_core = (current - spike_core_start).days
            if 0 <= days_from_core < core_duration:
                multiplier = random.uniform(*DAILY_SPIKE_CORE_MULTIPLIER_RANGE)
            elif days_from_core in (-1, core_duration) or days_from_core in (-2, core_duration + 1):
                multiplier = random.uniform(*DAILY_SHOULDER_MULTIPLIER_RANGE)
            else:
                multiplier = random.uniform(0.7, 1.3)
            daily_view_count = max(20, round(baseline_daily_views * multiplier))
            daily_video_count = max(1, round(daily_view_count / (350.0 + s["popularity_score"] * 80.0)))
            rows.append(
                {
                    "id": row_id,
                    "sound_id": s["id"],
                    "usage_date": current,
                    "daily_video_count": daily_video_count,
                    "daily_view_count": daily_view_count,
                }
            )
            row_id += 1
            current += timedelta(days=1)

    return pl.DataFrame(rows, infer_schema_length=None)


# ============================================================
# Section 7: TSV Generation Orchestration
# ============================================================


def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_label = gen_labels()
    df_label.write_csv(DATA_DIR / "01_label.tsv", separator="\t")

    df_creator = gen_creators()
    df_creator.write_csv(DATA_DIR / "02_creator.tsv", separator="\t")

    df_license = gen_label_blanket_licenses(df_label)
    df_license.write_csv(DATA_DIR / "03_label_blanket_license.tsv", separator="\t")

    df_sound = gen_sounds(df_label, df_creator)
    df_sound.write_csv(DATA_DIR / "04_sound.tsv", separator="\t")

    df_payment = gen_license_fee_payments(df_license)
    df_payment.write_csv(DATA_DIR / "05_license_fee_payment.tsv", separator="\t")

    df_monthly_usage = gen_sound_monthly_usage(df_sound, df_label, df_license)
    df_monthly_usage.write_csv(DATA_DIR / "06_sound_monthly_usage.tsv", separator="\t")

    df_conflict = gen_rights_conflict_flags(df_sound)
    df_conflict.write_csv(DATA_DIR / "07_rights_conflict_flag.tsv", separator="\t")

    df_payout = gen_creator_fund_weekly_payouts(df_sound, df_creator)
    df_payout.write_csv(DATA_DIR / "08_creator_fund_weekly_payout.tsv", separator="\t")

    df_daily = gen_sound_daily_viral_window(df_sound)
    df_daily.write_csv(DATA_DIR / "09_sound_daily_viral_window.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")


# ============================================================
# Section 8: SQLite Database Build
# ============================================================


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # Topological load order. The first element is the TSV file name without
    # extension; the second element is the SQLAlchemy Core Table object.
    load_order: list[tuple[str, "Table"]] = [
        ("01_label", Label.__table__),
        ("02_creator", Creator.__table__),
        ("03_label_blanket_license", LabelBlanketLicense.__table__),
        ("04_sound", Sound.__table__),
        ("05_license_fee_payment", LicenseFeePayment.__table__),
        ("06_sound_monthly_usage", SoundMonthlyUsage.__table__),
        ("07_rights_conflict_flag", RightsConflictFlag.__table__),
        ("08_creator_fund_weekly_payout", CreatorFundWeeklyPayout.__table__),
        ("09_sound_daily_viral_window", SoundDailyViralWindow.__table__),
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
