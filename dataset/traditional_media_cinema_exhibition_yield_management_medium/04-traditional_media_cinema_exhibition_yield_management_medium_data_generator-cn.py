"""
传统媒体 — 院线场次与卖品盈利分析 假数据生成器
复杂度: Medium
生成者: Fake Data Generator Agent

业务背景:
Lakeshore Cinemas 是一家总部位于芝加哥的区域性院线连锁, 运营 18 家影院、92 块银幕,
覆盖伊利诺伊、威斯康星、印第安纳、俄亥俄、密歇根五个中西部州. 本数据集模拟其
2026 年第二季度 (2026-04-01 至 2026-06-30) 的场次、卖品和会员活动, 支撑以下分析:
1. 卖品真实现金毛利 (Concession Cash Margin) —— 会员积分兑换是否被误记为正常收入,
   稀释了账面上看起来健康的毛利率.
2. 高端银幕单银幕贡献 (Premium Screen Contribution) —— 二线市场的 IMAX 银幕是否
   持续亏损, 被 Primary 市场的强势 IMAX 银幕掩盖.
3. 深夜场保底票充场 (Late-Night Minimum-Guarantee Buyback) —— 附带最低开场人数
   条款的事件型大片, 深夜场是否靠影院自己买回的票凑够人数.

上述三个"业务陷阱"通过有意设计的相关分布注入 (会员兑换按全价确认收入但零现金,
二线市场 IMAX 的低客流 vs 高固定成本, tentpole 影片深夜场的低自然客流 vs 保底条款).
对应的 SQL 查询位于 03-traditional_media_cinema_exhibition_yield_management_medium_sql_queries-cn.md,
用以暴露这些陷阱.
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
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "traditional_media_cinema_exhibition_yield_management_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 数据窗口是 2026 年第二季度. 所有"今天/当前快照"的语义都锚定在这里,
# 保证多次运行结果一致, 也保证 SQL 查询里的日期字面量与生成器一致.
REFERENCE_DATE = date(2026, 6, 30)
WINDOW_START = date(2026, 4, 1)
WINDOW_END = REFERENCE_DATE

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# 业务校准常量
# ============================================================================

# 18 家影院的固定画像: (影院编码, 影院名, 城市, 州, 市场分层, Standard 银幕数,
# Premium 银幕数, IMAX 银幕数). 这个表是手工排布的, 不是随机生成 —— 因为
# Q2 陷阱 (二线市场 IMAX 银幕持续亏损) 需要精确控制"哪些影院有 IMAX、分布在
# 哪个市场分层", 随机分布无法保证陷阱的清晰程度.
# 汇总: 18 家影院 (12 Primary / 6 Secondary), 92 块银幕 (65 Standard / 17 Premium /
# 10 IMAX), 其中 10 块 IMAX 银幕分布在 7 家 Primary 影院和 3 家 Secondary 影院.
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
MPAA_WEIGHTS = [5, 15, 45, 35]  # 主流院线片单偏 PG-13/R, 符合北美票房分布常识
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

# 排片合约: tentpole 影片全院线首轮铺开 (发行商要求宽发行), 常规影片只在部分
# 影院上映. tentpole 上映周期更长 (行业惯例, 大片留在银幕上更久换取票房).
TENTPOLE_RUN_DAYS_RANGE = (28, 56)
REGULAR_RUN_DAYS_RANGE = (14, 35)
REGULAR_THEATER_COUNT_RANGE = (2, 9)
# 只有 85% 的 tentpole 排片合约真的带最低开场人数条款 —— 并非每一份合约都谈到这一条,
# 有些影院议价掉了这条要求.
TENTPOLE_MINIMUM_GUARANTEE_PROB = 0.85
MINIMUM_ATTENDANCE_PER_SHOWTIME = 20

# 票价: 工作日基准价, 周五/周六再乘 WEEKEND_PRICE_MULTIPLIER. IMAX 相对 Standard
# 溢价 $6.00, Premium 溢价 $2.50 —— 这两个溢价数字直接决定 Q2 银幕贡献计算.
BASE_TICKET_PRICE = {"Standard": 12.50, "Premium": 15.00, "IMAX": 18.50}
WEEKEND_PRICE_MULTIPLIER = 1.15

# 每天场次数: IMAX 场次更稀疏 (大画幅排片惯例), Standard/Premium 更密集.
STANDARD_DAYPART_SEQUENCE = ["matinee", "matinee", "prime", "prime", "late_night"]
IMAX_DAYPART_SEQUENCE = ["matinee", "prime", "late_night"]

# 各 daypart 相对 prime 时段的自然客流倍数. late_night 只有 0.35x, 是 Q3 陷阱的
# 客流基线 —— 深夜场本来就冷清, 这才需要"保底票"来凑数.
MATINEE_ATTENDANCE_MULTIPLIER = 0.55
LATE_NIGHT_ATTENDANCE_MULTIPLIER = 0.35
WEEKEND_ATTENDANCE_MULTIPLIER = 1.25

# prime 时段付费观众均值, 按 (银幕类型, 市场分层) 校准. 这是 Q2 陷阱的核心输入:
# IMAX/Secondary 的均值 (15) 远低于 IMAX/Primary (85) —— 同样的 $6 票价溢价,
# 在 Secondary 市场覆盖不了 IMAX 的高额固定成本 (见 SCREEN_MONTHLY_COST).
PRIME_ATTENDANCE_MEAN = {
    "Standard": {"Primary": 45, "Secondary": 26},
    "Premium": {"Primary": 62, "Secondary": 34},
    "IMAX": {"Primary": 85, "Secondary": 15},
}
ATTENDANCE_STD_RATIO = 0.30  # 场次层面的自然波动幅度 (占均值比例)

# tentpole 影片深夜场的自然客流均值, 覆盖上面按类型/分层算出的 late_night 均值.
# 8 人的自然客流远低于 20 人的最低开场人数, 这个缺口正是"影院自己买票充场"的动机来源.
TENTPOLE_LATE_NIGHT_ORGANIC_MEAN = 8

# 正常场次的赠票/买回票基线, 代表促销赠票和员工福利票, 与最低开场人数条款无关.
BASELINE_COMP_RATE = 0.02
# 场次连续放映同一部影片的概率 (day-to-day). 值越高, 银幕越像现实中"一部片连放
# 一到三周"而不是每天换片.
BOOKING_PERSISTENCE_PROB = 0.88

# 卖品 SKU 主数据: (item_name, category, unit_price, unit_cost).
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
# 按品类分配"当天当时段有没有卖"这个抽样的权重. Popcorn/Beverage 是高频复购品类,
# Candy/Combo 相对小众, 这个权重决定 concession_sale 里各品类出现的频率.
CONCESSION_CATEGORY_SALE_WEIGHT = {"Popcorn": 35, "Beverage": 35, "Candy": 15, "Combo": 15}
# 搭售率: 每个 (影院, 日期, daypart) 桶里卖出的卖品件数, 近似为该桶内买票观众数
# (paid_attendance 之和) 乘以这个系数. 0.40 件/人对应人均卖品消费约 $2.7, 卖品收入
# 约为票房的 19% —— 符合北美中端区域院线的真实量级 (大量观众结伴合买一份、部分观众
# 完全不买, 故人均件数远低于 1). 会员兑换 (loyalty_redemption) 在此之上叠加, 约占
# 卖品总件数 5%-6%, 使 Q1 的账面 vs 现金毛利缺口落在真实可信的区间: 缺口本身不大
# (约 1.5pp), 但它发生在 70%+ 高毛利的卖品线上, 且逐季累积, 正是 CFO 该盯的隐性侵蚀.
CONCESSION_ATTACH_RATE = 0.40

# 会员: Standard/Silver/Gold 三档, Gold 会员的季度兑换次数约为 Standard 的 3-4 倍
# (更高频到访, 积分攒得更快). 这是 Q1 陷阱的会员侧输入. 均值取季度活跃会员的
# 真实量级 —— Gold (最活跃的头部会员) 约每季 9 次, Standard 约 2-3 次.
LOYALTY_MEMBER_COUNT = 7500
LOYALTY_TIER_WEIGHTS = {"Standard": 60, "Silver": 30, "Gold": 10}
REDEMPTION_MEAN_BY_TIER = {"Standard": 2.5, "Silver": 4.6, "Gold": 9.2}
LOYALTY_ITEM_CATEGORY_WEIGHT = {"Popcorn": 40, "Beverage": 35, "Candy": 15, "Combo": 10}
CROSS_THEATER_REDEMPTION_PROB = 0.15  # 会员偶尔在非主场影院兑换 (出差/跨市观影)
POINTS_PER_DOLLAR = 100  # 兑换消耗的积分数近似等于商品全价 x 该系数

# 银幕月度固定成本 (能耗 + 维保). IMAX 的维保开支含设备授权费和激光光源保养合同,
# 数量级远高于 Standard/Premium —— 这是 Q2 陷阱的成本侧输入.
SCREEN_MONTHLY_COST = {
    "Standard": {"energy": 900.0, "maintenance": 600.0},
    "Premium": {"energy": 1600.0, "maintenance": 1000.0},
    "IMAX": {"energy": 3500.0, "maintenance": 7000.0},
}
COST_MONTHS = [date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1)]


def daypart_hour(daypart: str) -> int:
    """按 daypart 抽取一个具体的开场小时, 落在 ER 文档定义的时段区间内."""
    if daypart == "matinee":
        return random.randint(10, 15)
    if daypart == "prime":
        return random.randint(16, 22)
    return 23


def random_title() -> str:
    """拼出一个听起来像电影片名、但不撞任何真实电影的标题."""
    adj = random.choice(TITLE_ADJECTIVES)
    noun = random.choice(TITLE_NOUNS)
    prefix = "The " if random.random() < 0.35 else ""
    return f"{prefix}{adj} {noun}"


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""

    pass


class Theater(Base):
    """Lakeshore Cinemas 旗下的实体影院."""

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
    """一块具体的银幕(影厅)."""

    __tablename__ = "screen"
    __table_args__ = (Index("idx_screen_theater", "theater_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    screen_number: Mapped[int] = mapped_column(Integer, nullable=False)
    screen_type: Mapped[str] = mapped_column(String(20), nullable=False)
    seat_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    install_date: Mapped[date] = mapped_column(Date, nullable=False)


class FilmTitle(Base):
    """本季度上映或仍在放映的影片."""

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
    """某影院在某时间窗口放映某部影片的排片合约."""

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
    """一块银幕在某个具体时间点放映的一场电影."""

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
    """卖品 SKU 主数据."""

    __tablename__ = "concession_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_name: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)


class ConcessionSale(Base):
    """卖品的正常付费销售汇总(粒度: 影院 x 日期 x 时段 x SKU)."""

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
    """Lakeshore Rewards 会员."""

    __tablename__ = "loyalty_member"
    __table_args__ = (Index("idx_loyalty_member_theater", "home_theater_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    home_theater_id: Mapped[int] = mapped_column(ForeignKey("theater.id", ondelete="CASCADE"), nullable=False)
    join_date: Mapped[date] = mapped_column(Date, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    lifetime_points_balance: Mapped[int] = mapped_column(Integer, nullable=False)


class LoyaltyRedemption(Base):
    """会员用积分兑换卖品的记录 —— Q1 陷阱的直接载体."""

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
    """每块银幕每月的能耗与维保开支 —— Q2 陷阱的成本侧输入."""

    __tablename__ = "screen_monthly_cost"
    __table_args__ = (Index("idx_screen_monthly_cost_screen", "screen_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen_id: Mapped[int] = mapped_column(ForeignKey("screen.id", ondelete="CASCADE"), nullable=False)
    cost_month: Mapped[date] = mapped_column(Date, nullable=False)
    energy_cost: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    maintenance_cost: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


# ============================================================================
# 数据生成器
# ============================================================================

def gen_theaters() -> pl.DataFrame:
    """生成 18 家影院记录, 画像取自 THEATER_DEFINITIONS 固定表."""
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
    """按 THEATER_DEFINITIONS 里的银幕类型配比, 为每家影院生成具体银幕."""
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
    """生成 70 部影片, 其中 8 部为 tentpole (事件型大片)."""
    used_titles: set[str] = set()
    records = []
    for i in range(1, FILM_COUNT + 1):
        is_tentpole = i <= TENTPOLE_COUNT
        title = random_title()
        while title in used_titles:
            title = random_title()
        used_titles.add(title)

        genre = random.choice(TENTPOLE_GENRES) if is_tentpole else random.choice(GENRES)
        # tentpole 影片首映日集中在前半段, 确保有足够长的窗口内运营周期.
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
    """生成排片合约: tentpole 影片全院线铺开, 常规影片只在部分影院上映."""
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
    """生成场次事实表. 每块银幕逐日选择一个有效排片合约, 按 daypart 展开若干场次.

    这是三个陷阱里两个 (Q2 银幕贡献, Q3 深夜场保底票) 的直接生成位置:
    - paid_attendance 均值按 (screen_type, market_tier) 查表, IMAX/Secondary 远低于
      IMAX/Primary.
    - comp_attendance 在 daypart='late_night' 且合约带最低开场人数条款时, 会被推高到
      接近 MINIMUM_ATTENDANCE_PER_SHOWTIME, 而不是维持 2% 的正常基线.
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
    """生成 24 个卖品 SKU."""
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
    """按 (影院, 日期, 时段) 汇总付费观众数, 生成对应的卖品销售明细.

    每个桶的卖品总件数近似为 该桶付费观众数之和 x CONCESSION_ATTACH_RATE, 再按品类
    权重拆分给若干随机挑选的 SKU. 这样卖品销量天然随场次客流波动, 支撑 Q5 的
    daypart 卖品匹配分析.
    """
    screen_to_theater = dict(zip(screens["id"].to_list(), screens["theater_id"].to_list()))
    showtimes_with_theater = showtimes.with_columns(
        pl.col("screen_id").replace_strict(screen_to_theater, default=None).alias("theater_id"),
        pl.col("showtime_datetime").dt.date().alias("sale_date"),
    )
    # group_by 本身不保证跨进程/跨线程的行序稳定; 后面的循环按行序消耗全局随机流,
    # 必须先显式排序, 否则同一个 RANDOM_SEED 在不同运行之间可能产生不同的输出.
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
        chosen_indices = list(dict.fromkeys(chosen_indices))  # 去重同时保持抽样顺序

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
    """生成活跃会员. home_theater 按影院银幕数加权 (银幕越多的影院客流越大, 会员越多)."""
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
    """生成会员积分兑换记录 —— Q1 陷阱 (账面收入 vs 现金收入) 的直接载体.

    每个会员在本季度的兑换次数按其 tier 对应的泊松均值抽样 (Gold ~3.7x Standard),
    每次兑换记录当时的商品全价与成本快照 —— 这两个数字是 Q1 SQL 查询要拆解的对象.
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
    """为每块银幕生成三个月 (2026-04/05/06) 的能耗与维保开支."""
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
# 核心函数 (幂等)
# ============================================================================

def generate_all_tsv() -> None:
    """生成所有 TSV 文件. 幂等: 先删除已有文件."""
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
    """从 TSV 文件创建 SQLite 数据库. 幂等: 先删除已有数据库."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 拓扑加载顺序. 第一个元素是不带扩展名的 TSV 文件名; 第二个元素是
    # SQLAlchemy Core Table 对象.
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
    """主入口."""
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
