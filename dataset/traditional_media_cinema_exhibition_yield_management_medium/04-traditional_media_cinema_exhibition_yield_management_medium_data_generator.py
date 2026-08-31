"""
Traditional Media -- Cinema Showtime and Concession Profitability Fake Data Generator
Complexity: Medium
Generator: Fake Data Generator Agent

Business Context:
Lakeshore Cinemas is a regional cinema exhibition chain headquartered in Chicago, operating
18 theaters and 92 screens across five Midwestern states: Illinois, Wisconsin, Indiana, Ohio,
and Michigan. This dataset simulates its Q2 2026 (2026-04-01 through 2026-06-30) showtime,
concession, and loyalty activity, supporting the following analyses:
1. Concession Cash Margin -- whether loyalty point redemptions are mistakenly booked as
   normal revenue, diluting a gross margin that looks healthy on paper.
2. Premium Screen Contribution -- whether Secondary-market IMAX screens are running a
   persistent loss, masked by strong-performing IMAX screens in Primary markets.
3. Late-Night Minimum-Guarantee Buyback -- whether tentpole event films with a minimum
   attendance clause attached rely on the theater buying back its own tickets to pad
   late-night showtime headcounts.

The three "business traps" above are injected via deliberately designed correlated
distributions (loyalty redemptions booked at full price with zero cash, low foot traffic
vs. high fixed costs for Secondary-market IMAX, and low organic late-night attendance vs.
minimum-guarantee clauses for tentpole films). The corresponding SQL queries live in
03-traditional_media_cinema_exhibition_yield_management_medium_sql_queries-cn.md and are
used to surface these traps.
"""

from __future__ import annotations

import random
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "traditional_media_cinema_exhibition_yield_management_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Fixed reference date; the data window is Q2 2026. All "today / current snapshot"
# semantics are anchored here, ensuring reproducible results across runs and keeping
# the date literals in the SQL queries consistent with the generator.
REFERENCE_DATE = date(2026, 6, 30)
WINDOW_START = date(2026, 4, 1)
WINDOW_END = REFERENCE_DATE

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# Business calibration constants
# ============================================================================

# Fixed profile of the 18 theaters: (theater_code, theater_name, city, state,
# market_tier, Standard screen count, Premium screen count, IMAX screen count).
# This table is hand-laid-out, not randomly generated -- because the Q2 trap
# (persistent losses on Secondary-market IMAX screens) requires precise control
# over "which theaters have IMAX, and which market tier they fall into"; a
# random distribution could not guarantee the clarity of the trap.
# Summary: 18 theaters (12 Primary / 6 Secondary), 92 screens (65 Standard /
# 17 Premium / 10 IMAX), of which the 10 IMAX screens are spread across
# 7 Primary theaters and 3 Secondary theaters.
THEATER_DEFINITIONS = [
    ("LC-CHI-01", "Lakeshore Cinemas Lincoln Square", "Chicago", "IL", "Primary", 5, 2, 1),
    ("LC-CHI-02", "Lakeshore Cinemas South Loop", "Chicago", "IL", "Primary", 4, 2, 1),
    ("LC-NAP-01", "Lakeshore Cinemas Naperville Crossing", "Naperville", "IL", "Primary", 4, 1, 1),
    ("LC-SCH-01", "Lakeshore Cinemas Schaumburg Commons", "Schaumburg", "IL", "Primary", 4, 1, 0),
    ("LC-EVA-01", "Lakeshore Cinemas Evanston Circle", "Evanston", "IL", "Primary", 4, 1, 0),
    ("LC-MIL-01", "Lakeshore Cinemas Milwaukee Riverwalk", "Milwaukee", "WI", "Primary", 4, 2, 1),
    ("LC-MAD-01", "Lakeshore Cinemas Madison Junction", "Madison", "WI", "Primary", 4, 1, 0),
    ("LC-IND-01", "Lakeshore Cinemas Indianapolis Meridian", "Indianapolis", "IN", "Primary", 3, 2, 1),
    ("LC-CAR-01", "Lakeshore Cinemas Carmel Arts District", "Carmel", "IN", "Primary", 4, 1, 0),
    ("LC-COL-01", "Lakeshore Cinemas Columbus Short North", "Columbus", "OH", "Primary", 3, 2, 1),
    ("LC-CIN-01", "Lakeshore Cinemas Cincinnati Riverfront", "Cincinnati", "OH", "Primary", 4, 1, 0),
    ("LC-GRA-01", "Lakeshore Cinemas Grand Rapids Uptown", "Grand Rapids", "MI", "Primary", 3, 1, 1),
    ("LC-PEO-01", "Lakeshore Cinemas Peoria Landmark", "Peoria", "IL", "Secondary", 3, 0, 1),
    ("LC-ROC-01", "Lakeshore Cinemas Rockford Riverfront", "Rockford", "IL", "Secondary", 4, 0, 0),
    ("LC-FTW-01", "Lakeshore Cinemas Fort Wayne Anthony", "Fort Wayne", "IN", "Secondary", 3, 0, 1),
    ("LC-DAY-01", "Lakeshore Cinemas Dayton Oakwood", "Dayton", "OH", "Secondary", 3, 0, 0),
    ("LC-GRB-01", "Lakeshore Cinemas Green Bay Fox River", "Green Bay", "WI", "Secondary", 3, 0, 1),
    ("LC-KAL-01", "Lakeshore Cinemas Kalamazoo Crossroads", "Kalamazoo", "MI", "Secondary", 3, 0, 0),
]

SEAT_CAPACITY_RANGE = {
    "Standard": (120, 160),
    "Premium": (90, 120),
    "IMAX": (250, 350),
}

GENRES = ["Action", "Comedy", "Drama", "Animation", "Horror", "Sci-Fi", "Thriller", "Family", "Romance", "Documentary"]
TENTPOLE_GENRES = ["Action", "Sci-Fi", "Animation"]
MPAA_RATINGS = ["G", "PG", "PG-13", "R"]
MPAA_WEIGHTS = [5, 15, 45, 35]  # Mainstream exhibitor slates skew PG-13/R, matching typical North American box-office distribution
DISTRIBUTORS = [
    "Redline Entertainment",
    "Union Star Films",
    "Harborview Pictures",
    "Northgate Media",
    "Prairie Peak Studios",
    "Brightwell Films",
]
TITLE_ADJECTIVES = [
    "Midnight", "Crimson", "Silver", "Iron", "Broken", "Hidden", "Last", "Silent",
    "Golden", "Wild", "Distant", "Frozen", "Scarlet", "Northern", "Final", "Endless",
    "Shattered", "Velvet", "Restless", "Sacred",
]
TITLE_NOUNS = [
    "Horizon", "Harbor", "Static", "Ember", "Echo", "Legacy", "Signal", "Current",
    "Reckoning", "Passage", "Season", "Verdict", "Frontier", "Hollow", "Voyage",
    "Requiem", "Covenant", "Drift", "Ledger", "Chorus",
]

FILM_COUNT = 70
TENTPOLE_COUNT = 8

# Booking contracts: tentpole films open wide across the entire chain on release
# (distributors require wide release), while regular films play in only a subset
# of theaters. Tentpole runs last longer (industry convention -- blockbusters stay
# on screen longer to maximize box office).
TENTPOLE_RUN_DAYS_RANGE = (28, 56)
REGULAR_RUN_DAYS_RANGE = (14, 35)
REGULAR_THEATER_COUNT_RANGE = (2, 9)
# Only 85% of tentpole booking contracts actually carry a minimum attendance
# clause -- not every contract includes this term; some theaters negotiate it away.
TENTPOLE_MINIMUM_GUARANTEE_PROB = 0.85
MINIMUM_ATTENDANCE_PER_SHOWTIME = 20

# Ticket pricing: weekday base price, multiplied by WEEKEND_PRICE_MULTIPLIER on
# Friday/Saturday. IMAX carries a $6.00 premium over Standard, Premium carries a
# $2.50 premium -- these two premium figures directly drive the Q2 screen
# contribution calculation.
BASE_TICKET_PRICE = {"Standard": 12.50, "Premium": 15.00, "IMAX": 18.50}
WEEKEND_PRICE_MULTIPLIER = 1.15

# Number of showtimes per day: IMAX showtimes are sparser (large-format scheduling
# convention), while Standard/Premium are denser.
STANDARD_DAYPART_SEQUENCE = ["matinee", "matinee", "prime", "prime", "late_night"]
IMAX_DAYPART_SEQUENCE = ["matinee", "prime", "late_night"]

# Organic attendance multiplier for each daypart relative to prime. late_night is
# only 0.35x, which is the attendance baseline for the Q3 trap -- late-night
# showtimes are naturally sparse, which is exactly why "buyback tickets" are
# needed to pad the count.
MATINEE_ATTENDANCE_MULTIPLIER = 0.55
LATE_NIGHT_ATTENDANCE_MULTIPLIER = 0.35
WEEKEND_ATTENDANCE_MULTIPLIER = 1.25

# Mean paid attendance for prime showtimes, calibrated by (screen_type,
# market_tier). This is the core input for the Q2 trap: the IMAX/Secondary mean
# (15) is far below IMAX/Primary (85) -- the same $6 ticket premium cannot cover
# IMAX's high fixed costs in a Secondary market (see SCREEN_MONTHLY_COST).
PRIME_ATTENDANCE_MEAN = {
    "Standard": {"Primary": 45, "Secondary": 26},
    "Premium": {"Primary": 62, "Secondary": 34},
    "IMAX": {"Primary": 85, "Secondary": 15},
}
ATTENDANCE_STD_RATIO = 0.30  # Natural showtime-level variance (as a ratio of the mean)

# Organic mean late-night attendance for tentpole films, overriding the
# type/tier-based late_night mean computed above. The organic mean of 8 is far
# below the minimum attendance requirement of 20, and this gap is exactly what
# motivates theaters to buy back their own tickets to pad the count.
TENTPOLE_LATE_NIGHT_ORGANIC_MEAN = 8

# Baseline comp/buyback ticket rate for normal showtimes, representing
# promotional comp tickets and employee benefit tickets, unrelated to minimum
# attendance clauses.
BASELINE_COMP_RATE = 0.02
# Probability that a screen continues showing the same film day-to-day. The
# higher the value, the more a screen behaves like real life -- a film staying
# on screen for one to three weeks rather than changing daily.
BOOKING_PERSISTENCE_PROB = 0.88

# Concession SKU master data: (item_name, category, unit_price, unit_cost).
CONCESSION_ITEMS = [
    ("Small Popcorn", "Popcorn", 5.50, 1.75),
    ("Medium Popcorn", "Popcorn", 7.50, 2.25),
    ("Large Popcorn", "Popcorn", 9.50, 2.75),
    ("Caramel Popcorn", "Popcorn", 8.50, 3.00),
    ("Small Fountain Drink", "Beverage", 5.00, 0.80),
    ("Medium Fountain Drink", "Beverage", 6.00, 0.95),
    ("Large Fountain Drink", "Beverage", 7.00, 1.10),
    ("Bottled Water", "Beverage", 4.50, 0.90),
    ("ICEE Frozen Drink", "Beverage", 6.50, 1.60),
    ("Iced Coffee", "Beverage", 5.50, 1.00),
    ("Lemonade", "Beverage", 5.00, 0.85),
    ("M&Ms", "Candy", 5.50, 2.00),
    ("Reese's Pieces", "Candy", 5.50, 2.00),
    ("Milk Duds", "Candy", 5.00, 1.80),
    ("Twizzlers", "Candy", 5.00, 1.80),
    ("Sour Patch Kids", "Candy", 5.50, 2.00),
    ("Junior Mints", "Candy", 5.00, 1.80),
    ("Popcorn + Drink Combo (Medium)", "Combo", 12.50, 3.20),
    ("Popcorn + Drink Combo (Large)", "Combo", 14.50, 3.85),
    ("Nachos", "Combo", 8.00, 2.60),
    ("Pretzel Bites", "Combo", 7.50, 2.40),
    ("Hot Dog", "Combo", 6.50, 2.10),
    ("Chicken Tenders", "Combo", 9.50, 3.60),
    ("Kids Combo (Popcorn + Juice + Candy)", "Combo", 10.00, 3.50),
]
# Weights for sampling "whether this category sold anything in this bucket for
# this day/daypart." Popcorn/Beverage are high-frequency repeat-purchase
# categories, Candy/Combo are relatively niche; these weights govern how often
# each category appears in concession_sale.
CONCESSION_CATEGORY_SALE_WEIGHT = {"Popcorn": 35, "Beverage": 35, "Candy": 15, "Combo": 15}
# Attach rate: the number of concession units sold in each (theater, date,
# daypart) bucket is approximated as the paid attendance total for that bucket
# (sum of paid_attendance) multiplied by this coefficient. 0.40 units/person
# corresponds to roughly $2.7 of per-capita concession spend, with concession
# revenue at about 19% of box office -- consistent with the real-world scale of
# a mid-tier North American regional exhibitor (many moviegoers split a single
# item, and some buy nothing at all, so per-capita units are well below 1).
# Loyalty redemptions (loyalty_redemption) are layered on top of this, accounting
# for roughly 5%-6% of total concession units, putting the Q1 booked-vs-cash
# margin gap at a realistic and believable magnitude: the gap itself is small
# (about 1.5pp), but it occurs on a 70%+ gross-margin concession line and
# accumulates quarter over quarter -- exactly the kind of hidden erosion a CFO
# should be watching.
CONCESSION_ATTACH_RATE = 0.40

# Loyalty: three tiers -- Standard/Silver/Gold. Gold members' quarterly redemption
# count is roughly 3-4x that of Standard (higher visit frequency, faster point
# accrual). This is the loyalty-side input for the Q1 trap. The means are set to
# realistic quarterly-active-member magnitudes -- Gold (the most engaged top-tier
# members) redeems about 9 times per quarter, Standard about 2-3 times.
LOYALTY_MEMBER_COUNT = 7500
LOYALTY_TIER_WEIGHTS = {"Standard": 60, "Silver": 30, "Gold": 10}
REDEMPTION_MEAN_BY_TIER = {"Standard": 2.5, "Silver": 4.6, "Gold": 9.2}
LOYALTY_ITEM_CATEGORY_WEIGHT = {"Popcorn": 40, "Beverage": 35, "Candy": 15, "Combo": 10}
CROSS_THEATER_REDEMPTION_PROB = 0.15  # Members occasionally redeem at a non-home theater (business travel/moviegoing in another market)
POINTS_PER_DOLLAR = 100  # Points consumed by a redemption approximately equal the item's full price times this coefficient

# Monthly fixed screen costs (energy + maintenance). IMAX maintenance spend
# includes equipment licensing fees and laser light-source service contracts,
# an order of magnitude higher than Standard/Premium -- this is the cost-side
# input for the Q2 trap.
SCREEN_MONTHLY_COST = {
    "Standard": {"energy": 900.0, "maintenance": 600.0},
    "Premium": {"energy": 1600.0, "maintenance": 1000.0},
    "IMAX": {"energy": 3500.0, "maintenance": 7000.0},
}
COST_MONTHS = [date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1)]


def daypart_hour(daypart: str) -> int:
    """Sample a specific start hour for a given daypart, within the time-window ranges defined in the ER document."""
    if daypart == "matinee":
        return random.randint(10, 15)
    if daypart == "prime":
        return random.randint(16, 22)
    return 23


def random_title() -> str:
    """Assemble a title that sounds like a movie but doesn't collide with any real film."""
    adj = random.choice(TITLE_ADJECTIVES)
    noun = random.choice(TITLE_NOUNS)
    prefix = "The " if random.random() < 0.35 else ""
    return f"{prefix}{adj} {noun}"


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Theater(Base):
    """A physical theater location owned by Lakeshore Cinemas."""

    __tablename__ = "theater"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theater_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    theater_name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    market_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    open_date: Mapped[date] = mapped_column(Date, nullable=False)
    screen_count: Mapped[int] = mapped_column(Integer, nullable=False)


class Screen(Base):
    """A specific screen (auditorium)."""

    __tablename__ = "screen"
    __table_args__ = (Index("idx_screen_theater", "theater_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    screen_number: Mapped[int] = mapped_column(Integer, nullable=False)
    screen_type: Mapped[str] = mapped_column(String(20), nullable=False)
    seat_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    install_date: Mapped[date] = mapped_column(Date, nullable=False)


class FilmTitle(Base):
    """A film released or still playing this quarter."""

    __tablename__ = "film_title"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    genre: Mapped[str] = mapped_column(String(40), nullable=False)
    mpaa_rating: Mapped[str] = mapped_column(String(10), nullable=False)
    runtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    distributor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_tentpole: Mapped[bool] = mapped_column(Boolean, default=False)


class FilmBooking(Base):
    """A booking contract for a theater to play a given film over a time window."""

    __tablename__ = "film_booking"
    __table_args__ = (
        Index("idx_film_booking_theater", "theater_id"),
        Index("idx_film_booking_film", "film_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    film_id: Mapped[int] = mapped_column(ForeignKey("film_title.id", ondelete="CASCADE"), nullable=False)
    booking_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    has_minimum_guarantee: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_attendance_per_showtime: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Showtime(Base):
    """A single screening of a film on a specific screen at a specific time."""

    __tablename__ = "showtime"
    __table_args__ = (
        Index("idx_showtime_screen", "screen_id"),
        Index("idx_showtime_booking", "film_booking_id"),
        Index("idx_showtime_datetime", "showtime_datetime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen_id: Mapped[int] = mapped_column(ForeignKey("screen.id", ondelete="CASCADE"), nullable=False)
    film_booking_id: Mapped[int] = mapped_column(ForeignKey("film_booking.id", ondelete="CASCADE"), nullable=False)
    showtime_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    daypart: Mapped[str] = mapped_column(String(20), nullable=False)
    ticket_price: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    paid_attendance: Mapped[int] = mapped_column(Integer, nullable=False)
    comp_attendance: Mapped[int] = mapped_column(Integer, default=0)
    ticket_revenue: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class ConcessionItem(Base):
    """Concession SKU master data."""

    __tablename__ = "concession_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)


class ConcessionSale(Base):
    """Normal paid concession sales aggregate (grain: theater x date x daypart x SKU)."""

    __tablename__ = "concession_sale"
    __table_args__ = (
        Index("idx_concession_sale_theater", "theater_id"),
        Index("idx_concession_sale_item", "item_id"),
        Index("idx_concession_sale_date", "sale_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("concession_item.id", ondelete="CASCADE"), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    daypart: Mapped[str] = mapped_column(String(20), nullable=False)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    gross_revenue: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    cogs_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class LoyaltyMember(Base):
    """A Lakeshore Rewards member."""

    __tablename__ = "loyalty_member"
    __table_args__ = (Index("idx_loyalty_member_theater", "home_theater_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    home_theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    join_date: Mapped[date] = mapped_column(Date, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    lifetime_points_balance: Mapped[int] = mapped_column(Integer, nullable=False)


class LoyaltyRedemption(Base):
    """A record of a member redeeming loyalty points for a concession item -- the direct vehicle for the Q1 trap."""

    __tablename__ = "loyalty_redemption"
    __table_args__ = (
        Index("idx_loyalty_redemption_member", "member_id"),
        Index("idx_loyalty_redemption_theater", "theater_id"),
        Index("idx_loyalty_redemption_date", "redemption_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("loyalty_member.id", ondelete="CASCADE"), nullable=False)
    theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("concession_item.id", ondelete="CASCADE"), nullable=False)
    redemption_date: Mapped[date] = mapped_column(Date, nullable=False)
    points_used: Mapped[int] = mapped_column(Integer, nullable=False)
    item_full_price: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    item_unit_cost: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)


class ScreenMonthlyCost(Base):
    """Monthly energy and maintenance costs per screen -- the cost-side input for the Q2 trap."""

    __tablename__ = "screen_monthly_cost"
    __table_args__ = (Index("idx_screen_monthly_cost_screen", "screen_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen_id: Mapped[int] = mapped_column(ForeignKey("screen.id", ondelete="CASCADE"), nullable=False)
    cost_month: Mapped[date] = mapped_column(Date, nullable=False)
    energy_cost: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    maintenance_cost: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


# ============================================================================
# Data generators
# ============================================================================

def gen_theaters() -> pl.DataFrame:
    """Generate 18 theater records, with profiles taken from the fixed THEATER_DEFINITIONS table."""
    records = []
    for idx, (code, name, city, state, tier, n_std, n_prem, n_imax) in enumerate(THEATER_DEFINITIONS, start=1):
        open_date = fake.date_between(start_date=date(2006, 1, 1), end_date=date(2019, 12, 31))
        records.append({
            "id": idx,
            "theater_code": code,
            "theater_name": name,
            "city": city,
            "state": state,
            "market_tier": tier,
            "open_date": open_date,
            "screen_count": n_std + n_prem + n_imax,
        })
    return pl.DataFrame(records)


def gen_screens(theaters: pl.DataFrame) -> pl.DataFrame:
    """Generate specific screens for each theater, following the screen-type mix defined in THEATER_DEFINITIONS."""
    open_date_lookup = dict(zip(theaters["id"].to_list(), theaters["open_date"].to_list()))

    records = []
    screen_id = 1
    for idx, (_code, _name, _city, _state, _tier, n_std, n_prem, n_imax) in enumerate(THEATER_DEFINITIONS, start=1):
        theater_id = idx
        theater_open_date = open_date_lookup[theater_id]
        screen_number = 1
        type_counts = [("Standard", n_std), ("Premium", n_prem), ("IMAX", n_imax)]
        for screen_type, count in type_counts:
            lo, hi = SEAT_CAPACITY_RANGE[screen_type]
            for _ in range(count):
                install_date = fake.date_between(
                    start_date=max(theater_open_date, date(2020, 1, 1)),
                    end_date=WINDOW_START - timedelta(days=30),
                )
                records.append({
                    "id": screen_id,
                    "theater_id": theater_id,
                    "screen_number": screen_number,
                    "screen_type": screen_type,
                    "seat_capacity": random.randint(lo, hi),
                    "install_date": install_date,
                })
                screen_id += 1
                screen_number += 1
    return pl.DataFrame(records)


def gen_film_titles() -> pl.DataFrame:
    """Generate 70 films, 8 of which are tentpoles (event-driven blockbusters)."""
    used_titles: set[str] = set()
    records = []
    for i in range(1, FILM_COUNT + 1):
        is_tentpole = i <= TENTPOLE_COUNT
        title = random_title()
        while title in used_titles:
            title = random_title()
        used_titles.add(title)

        genre = random.choice(TENTPOLE_GENRES) if is_tentpole else random.choice(GENRES)
        # Tentpole release dates cluster in the first half, ensuring a long enough operating window in the season.
        release_start = date(2026, 1, 5)
        release_end = date(2026, 5, 15) if is_tentpole else date(2026, 6, 10)
        release_date = fake.date_between(start_date=release_start, end_date=release_end)

        records.append({
            "id": i,
            "title": title,
            "genre": genre,
            "mpaa_rating": random.choices(MPAA_RATINGS, weights=MPAA_WEIGHTS, k=1)[0],
            "runtime_minutes": random.randint(85, 165),
            "release_date": release_date,
            "distributor_name": random.choice(DISTRIBUTORS),
            "is_tentpole": is_tentpole,
        })
    return pl.DataFrame(records)


def gen_film_bookings(theaters: pl.DataFrame, films: pl.DataFrame) -> pl.DataFrame:
    """Generate booking contracts: tentpole films open wide across the chain, regular films play in only a subset of theaters."""
    theater_ids = theaters["id"].to_list()

    records = []
    booking_id = 1
    for film in films.iter_rows(named=True):
        is_tentpole = film["is_tentpole"]
        booked_theaters = theater_ids if is_tentpole else random.sample(
            theater_ids, random.randint(*REGULAR_THEATER_COUNT_RANGE)
        )
        run_range = TENTPOLE_RUN_DAYS_RANGE if is_tentpole else REGULAR_RUN_DAYS_RANGE

        for theater_id in booked_theaters:
            booking_start = max(film["release_date"], WINDOW_START)
            if booking_start > WINDOW_END:
                continue
            run_days = random.randint(*run_range)
            booking_end = min(booking_start + timedelta(days=run_days), WINDOW_END)
            if booking_end <= booking_start:
                continue

            has_minimum_guarantee = is_tentpole and random.random() < TENTPOLE_MINIMUM_GUARANTEE_PROB
            records.append({
                "id": booking_id,
                "theater_id": theater_id,
                "film_id": film["id"],
                "booking_start_date": booking_start,
                "booking_end_date": booking_end,
                "has_minimum_guarantee": has_minimum_guarantee,
                "minimum_attendance_per_showtime": MINIMUM_ATTENDANCE_PER_SHOWTIME if has_minimum_guarantee else None,
            })
            booking_id += 1
    return pl.DataFrame(records)


def gen_showtimes(theaters: pl.DataFrame, screens: pl.DataFrame, films: pl.DataFrame, bookings: pl.DataFrame) -> pl.DataFrame:
    """Generate the showtime fact table. Each screen picks a valid booking contract day by day and expands it into several showtimes per daypart.

    This is where two of the three traps (Q2 screen contribution, Q3 late-night
    minimum-guarantee buyback) are directly generated:
    - paid_attendance means are looked up by (screen_type, market_tier), with
      IMAX/Secondary far below IMAX/Primary.
    - comp_attendance is pushed up close to MINIMUM_ATTENDANCE_PER_SHOWTIME
      whenever daypart='late_night' and the contract carries a minimum
      attendance clause, rather than staying at the normal 2% baseline.
    """
    market_tier_lookup = dict(zip(theaters["id"].to_list(), theaters["market_tier"].to_list()))
    films_by_id = {f["id"]: f for f in films.iter_rows(named=True)}

    bookings_by_theater: dict[int, list[dict]] = {}
    for b in bookings.iter_rows(named=True):
        bookings_by_theater.setdefault(b["theater_id"], []).append(b)

    all_days = [WINDOW_START + timedelta(days=i) for i in range((WINDOW_END - WINDOW_START).days + 1)]

    records = []
    showtime_id = 1

    for screen in screens.iter_rows(named=True):
        theater_id = screen["theater_id"]
        screen_type = screen["screen_type"]
        seat_capacity = screen["seat_capacity"]
        market_tier = market_tier_lookup[theater_id]
        theater_bookings = bookings_by_theater.get(theater_id, [])
        daypart_sequence = IMAX_DAYPART_SEQUENCE if screen_type == "IMAX" else STANDARD_DAYPART_SEQUENCE
        attendance_mean_prime = PRIME_ATTENDANCE_MEAN[screen_type][market_tier]
        base_price = BASE_TICKET_PRICE[screen_type]

        current_booking: dict | None = None
        for day in all_days:
            valid_bookings = [
                b for b in theater_bookings
                if b["booking_start_date"] <= day <= b["booking_end_date"]
            ]
            if not valid_bookings:
                current_booking = None
                continue

            if screen_type == "IMAX":
                tentpole_valid = [b for b in valid_bookings if films_by_id[b["film_id"]]["is_tentpole"]]
                pool = tentpole_valid if tentpole_valid else valid_bookings
            else:
                pool = valid_bookings

            if current_booking is None or current_booking not in pool or random.random() > BOOKING_PERSISTENCE_PROB:
                current_booking = random.choice(pool)

            film = films_by_id[current_booking["film_id"]]
            is_weekend = day.weekday() in (4, 5)
            ticket_price = round(base_price * (WEEKEND_PRICE_MULTIPLIER if is_weekend else 1.0), 2)

            for daypart in daypart_sequence:
                hour = daypart_hour(daypart)
                minute = random.choice([0, 15, 30, 45])
                showtime_dt = datetime.combine(day, time(hour=hour, minute=minute))

                is_flagged_late_night = (
                    daypart == "late_night"
                    and current_booking["has_minimum_guarantee"]
                    and film["is_tentpole"]
                )

                if is_flagged_late_night:
                    mean = TENTPOLE_LATE_NIGHT_ORGANIC_MEAN
                elif daypart == "matinee":
                    mean = attendance_mean_prime * MATINEE_ATTENDANCE_MULTIPLIER
                elif daypart == "late_night":
                    mean = attendance_mean_prime * LATE_NIGHT_ATTENDANCE_MULTIPLIER
                else:
                    mean = attendance_mean_prime

                if is_weekend:
                    mean *= WEEKEND_ATTENDANCE_MULTIPLIER

                paid_attendance = int(max(0, min(seat_capacity, round(random.gauss(mean, mean * ATTENDANCE_STD_RATIO)))))

                if is_flagged_late_night:
                    shortfall = current_booking["minimum_attendance_per_showtime"] - paid_attendance
                    baseline_comp = round(paid_attendance * BASELINE_COMP_RATE)
                    comp_attendance = max(baseline_comp, shortfall + random.randint(0, 3)) if shortfall > 0 else baseline_comp
                else:
                    comp_attendance = round(paid_attendance * BASELINE_COMP_RATE)
                comp_attendance = max(0, min(comp_attendance, seat_capacity - paid_attendance))

                ticket_revenue = round(paid_attendance * ticket_price, 2)

                records.append({
                    "id": showtime_id,
                    "screen_id": screen["id"],
                    "film_booking_id": current_booking["id"],
                    "showtime_datetime": showtime_dt,
                    "daypart": daypart,
                    "ticket_price": ticket_price,
                    "paid_attendance": paid_attendance,
                    "comp_attendance": comp_attendance,
                    "ticket_revenue": ticket_revenue,
                })
                showtime_id += 1

    return pl.DataFrame(records)


def gen_concession_items() -> pl.DataFrame:
    """Generate 24 concession SKUs."""
    records = []
    for i, (name, category, price, cost) in enumerate(CONCESSION_ITEMS, start=1):
        records.append({
            "id": i,
            "item_name": name,
            "category": category,
            "unit_price": price,
            "unit_cost": cost,
        })
    return pl.DataFrame(records)


def gen_concession_sales(theaters: pl.DataFrame, showtimes: pl.DataFrame, screens: pl.DataFrame, items: pl.DataFrame) -> pl.DataFrame:
    """Aggregate paid attendance by (theater, date, daypart) and generate the corresponding concession sale detail records.

    Total concession units for each bucket are approximated as that bucket's
    total paid attendance x CONCESSION_ATTACH_RATE, then split across a handful
    of randomly chosen SKUs by category weight. This way, concession volume
    naturally fluctuates with showtime attendance, supporting the Q5
    daypart-vs-concession matching analysis.
    """
    screen_to_theater = dict(zip(screens["id"].to_list(), screens["theater_id"].to_list()))
    showtimes_with_theater = showtimes.with_columns(
        pl.col("screen_id").replace_strict(screen_to_theater, default=None).alias("theater_id"),
        pl.col("showtime_datetime").dt.date().alias("sale_date"),
    )
    # group_by does not by itself guarantee stable row order across processes/threads;
    # the loop below consumes the global random stream in row order, so we must sort
    # explicitly first, otherwise the same RANDOM_SEED could produce different output
    # across different runs.
    attendance_buckets = (
        showtimes_with_theater
        .group_by(["theater_id", "sale_date", "daypart"])
        .agg(pl.col("paid_attendance").sum().alias("total_attendance"))
        .sort(["theater_id", "sale_date", "daypart"])
    )

    item_rows = list(items.iter_rows(named=True))
    item_weights = [CONCESSION_CATEGORY_SALE_WEIGHT[row["category"]] for row in item_rows]

    records = []
    sale_id = 1
    for bucket in attendance_buckets.iter_rows(named=True):
        total_attendance = bucket["total_attendance"]
        if total_attendance <= 0:
            continue

        total_units = round(total_attendance * CONCESSION_ATTACH_RATE * random.uniform(0.85, 1.15))
        if total_units <= 0:
            continue

        k = random.randint(3, 7)
        chosen_indices = random.choices(range(len(item_rows)), weights=item_weights, k=k)
        chosen_indices = list(dict.fromkeys(chosen_indices))  # Deduplicate while preserving sample order

        shares = [random.uniform(0.5, 1.5) for _ in chosen_indices]
        share_sum = sum(shares)

        for idx, share in zip(chosen_indices, shares):
            item = item_rows[idx]
            units_sold = round(total_units * share / share_sum)
            if units_sold <= 0:
                continue
            gross_revenue = round(units_sold * item["unit_price"], 2)
            cogs_amount = round(units_sold * item["unit_cost"], 2)
            records.append({
                "id": sale_id,
                "theater_id": bucket["theater_id"],
                "item_id": item["id"],
                "sale_date": bucket["sale_date"],
                "daypart": bucket["daypart"],
                "units_sold": units_sold,
                "unit_price": item["unit_price"],
                "gross_revenue": gross_revenue,
                "cogs_amount": cogs_amount,
            })
            sale_id += 1

    return pl.DataFrame(records)


def gen_loyalty_members(theaters: pl.DataFrame) -> pl.DataFrame:
    """Generate active loyalty members. home_theater is weighted by theater screen count (theaters with more screens have more foot traffic and thus more members)."""
    theater_ids = theaters["id"].to_list()
    screen_counts = theaters["screen_count"].to_list()

    tier_keys = list(LOYALTY_TIER_WEIGHTS.keys())
    tier_weights = list(LOYALTY_TIER_WEIGHTS.values())

    records = []
    for i in range(1, LOYALTY_MEMBER_COUNT + 1):
        tier = random.choices(tier_keys, weights=tier_weights, k=1)[0]
        join_date = fake.date_between(start_date=date(2015, 1, 1), end_date=WINDOW_START - timedelta(days=30))
        points_multiplier = {"Standard": 1.0, "Silver": 1.8, "Gold": 3.2}[tier]
        lifetime_points_balance = int(random.uniform(150, 1500) * points_multiplier)

        records.append({
            "id": i,
            "member_code": f"LR-{i:06d}",
            "home_theater_id": random.choices(theater_ids, weights=screen_counts, k=1)[0],
            "join_date": join_date,
            "tier": tier,
            "lifetime_points_balance": lifetime_points_balance,
        })
    return pl.DataFrame(records)


def gen_loyalty_redemptions(members: pl.DataFrame, theaters: pl.DataFrame, items: pl.DataFrame) -> pl.DataFrame:
    """Generate loyalty point redemption records -- the direct vehicle for the Q1 trap (recognized revenue vs. cash revenue).

    Each member's redemption count for the quarter is sampled from a
    Poisson-like mean tied to their tier (Gold ~3.7x Standard); each redemption
    records a snapshot of the item's full price and cost at that time -- these
    two figures are exactly what the Q1 SQL query breaks apart.
    """
    theater_ids = theaters["id"].to_list()
    item_rows = list(items.iter_rows(named=True))
    item_weights = [LOYALTY_ITEM_CATEGORY_WEIGHT[row["category"]] for row in item_rows]

    records = []
    redemption_id = 1
    for member in members.iter_rows(named=True):
        mean_redemptions = REDEMPTION_MEAN_BY_TIER[member["tier"]]
        n_redemptions = min(30, max(0, round(random.gauss(mean_redemptions, mean_redemptions * 0.5))))

        for _ in range(n_redemptions):
            redemption_date = fake.date_between(start_date=WINDOW_START, end_date=WINDOW_END)
            if random.random() < CROSS_THEATER_REDEMPTION_PROB:
                theater_id = random.choice(theater_ids)
            else:
                theater_id = member["home_theater_id"]

            item = random.choices(item_rows, weights=item_weights, k=1)[0]
            points_used = int(item["unit_price"] * POINTS_PER_DOLLAR)

            records.append({
                "id": redemption_id,
                "member_id": member["id"],
                "theater_id": theater_id,
                "item_id": item["id"],
                "redemption_date": redemption_date,
                "points_used": points_used,
                "item_full_price": item["unit_price"],
                "item_unit_cost": item["unit_cost"],
            })
            redemption_id += 1

    return pl.DataFrame(records)


def gen_screen_monthly_costs(screens: pl.DataFrame) -> pl.DataFrame:
    """Generate three months (2026-04/05/06) of energy and maintenance costs for each screen."""
    records = []
    cost_id = 1
    for screen in screens.iter_rows(named=True):
        base = SCREEN_MONTHLY_COST[screen["screen_type"]]
        for cost_month in COST_MONTHS:
            energy_cost = round(base["energy"] * random.uniform(0.95, 1.05), 2)
            maintenance_cost = round(base["maintenance"] * random.uniform(0.95, 1.05), 2)
            records.append({
                "id": cost_id,
                "screen_id": screen["id"],
                "cost_month": cost_month,
                "energy_cost": energy_cost,
                "maintenance_cost": maintenance_cost,
                "total_cost": round(energy_cost + maintenance_cost, 2),
            })
            cost_id += 1
    return pl.DataFrame(records)


# ============================================================================
# Core functions (idempotent)
# ============================================================================

def generate_all_tsv() -> None:
    """Generate all TSV files. Idempotent: deletes existing files first."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating theaters...")
    df_theaters = gen_theaters()
    df_theaters.write_csv(DATA_DIR / "01_theater.tsv", separator="\t")

    print("Generating screens...")
    df_screens = gen_screens(df_theaters)
    df_screens.write_csv(DATA_DIR / "02_screen.tsv", separator="\t")

    print("Generating film titles...")
    df_films = gen_film_titles()
    df_films.write_csv(DATA_DIR / "03_film_title.tsv", separator="\t")

    print("Generating film bookings...")
    df_bookings = gen_film_bookings(df_theaters, df_films)
    df_bookings.write_csv(DATA_DIR / "04_film_booking.tsv", separator="\t")

    print("Generating showtimes...")
    df_showtimes = gen_showtimes(df_theaters, df_screens, df_films, df_bookings)
    df_showtimes.write_csv(DATA_DIR / "05_showtime.tsv", separator="\t")

    print("Generating concession items...")
    df_items = gen_concession_items()
    df_items.write_csv(DATA_DIR / "06_concession_item.tsv", separator="\t")

    print("Generating concession sales...")
    df_concession_sales = gen_concession_sales(df_theaters, df_showtimes, df_screens, df_items)
    df_concession_sales.write_csv(DATA_DIR / "07_concession_sale.tsv", separator="\t")

    print("Generating loyalty members...")
    df_members = gen_loyalty_members(df_theaters)
    df_members.write_csv(DATA_DIR / "08_loyalty_member.tsv", separator="\t")

    print("Generating loyalty redemptions...")
    df_redemptions = gen_loyalty_redemptions(df_members, df_theaters, df_items)
    df_redemptions.write_csv(DATA_DIR / "09_loyalty_redemption.tsv", separator="\t")

    print("Generating screen monthly costs...")
    df_costs = gen_screen_monthly_costs(df_screens)
    df_costs.write_csv(DATA_DIR / "10_screen_monthly_cost.tsv", separator="\t")

    total = (
        len(df_theaters) + len(df_screens) + len(df_films) + len(df_bookings)
        + len(df_showtimes) + len(df_items) + len(df_concession_sales)
        + len(df_members) + len(df_redemptions) + len(df_costs)
    )
    print(f"\nGenerated all TSV files in {DATA_DIR}")
    print(f"Total rows: {total}")


def create_sqlite_database() -> None:
    """Create the SQLite database from TSV files. Idempotent: deletes the existing database first."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # Topological load order. The first element is the TSV file name without
    # extension; the second element is the SQLAlchemy Core Table object.
    load_order: list[tuple[str, Table]] = [
        ("01_theater", Theater.__table__),
        ("02_screen", Screen.__table__),
        ("03_film_title", FilmTitle.__table__),
        ("04_film_booking", FilmBooking.__table__),
        ("05_showtime", Showtime.__table__),
        ("06_concession_item", ConcessionItem.__table__),
        ("07_concession_sale", ConcessionSale.__table__),
        ("08_loyalty_member", LoyaltyMember.__table__),
        ("09_loyalty_redemption", LoyaltyRedemption.__table__),
        ("10_screen_monthly_cost", ScreenMonthlyCost.__table__),
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
    print("Lakeshore Cinemas - Exhibition Yield Management Data Generator")
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
