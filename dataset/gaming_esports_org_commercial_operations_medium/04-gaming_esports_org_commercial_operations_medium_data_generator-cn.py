"""
游戏/电竞 电竞俱乐部商业运营假数据生成器
复杂度: Medium

业务背景:
Vanguard Esports 是一家总部位于洛杉矶的虚构电竞俱乐部, 旗下 3 支分部战队
(Vanguard Fracture, Vanguard Aetherlane, Vanguard Academy)。本数据集覆盖
2024-07-01 到 REFERENCE_DATE = 2026-06-30 共两个赛季的商业与竞技运营数据,
支持以下 4 个业务陷阱的分析:

1. 赞助曝光计费缺口陷阱: 12 份赞助合同中有 3 份(TitanEnergy Global
   Partnership, GridForge Fracture Protocol Hardware Deal, StreakBet Gaming
   Partnership)的年化实测曝光小时数相对合同承诺值系统性缺口约 25%-35%,
   其余 9 份合同交付率保持在 93% 以上, 只看整体均值会被健康合同稀释.
2. 薪资与战绩脱节陷阱: 4 名选手(Zenithrax, Wraithcall, Thornquil,
   Hollowmere)近 6 个月表现评分相比其历史高点下降约 30%-35%, 但都在下滑
   前后完成了长期续约, 薪资未做任何下调; 其余选手的薪资与近期表现评分保持
   正相关.
3. 周边毛利与战绩挂钩陷阱: 战队近 60 天滚动胜率高时, 周边商品折扣力度低,
   毛利率维持在 48%-53%; 胜率跌入低谷时, 折扣力度大幅上升, 毛利率跌到
   32%-38%, 但销量因促销反而略有上升, 总营收降幅远小于毛利率降幅, 财务报表
   如果只看营收趋势会完全错过这个信号.
4. 奖金分成支付合规性陷阱: 约 15% 的选手奖金分成记录逾期(超过合同约定的
   30 天付款期限)或短付, 其中约 8 成集中在 Vanguard Academy 战队, 指向该
   战队奖金分成财务流程的系统性问题.

上述陷阱通过有意设计的相关分布注入. 对应的 SQL 查询位于
03-gaming_esports_org_commercial_operations_medium_sql_queries-cn.md, 用以
暴露这些陷阱.
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
# 配置常量
# ----------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "gaming_esports_org_commercial_operations_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期.
REFERENCE_DATE = date(2026, 6, 30)
# 数据窗口起点: 两个完整赛季, 共 24 个月.
SEASON_START = date(2024, 7, 1)
TOTAL_SEASON_DAYS = (REFERENCE_DATE - SEASON_START).days

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


def month_index(d: date) -> int:
    """把日期换算成距 SEASON_START 的月份序号(0-23), 用于查战队当月状态目标."""
    return (d.year - SEASON_START.year) * 12 + (d.month - SEASON_START.month)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def weighted_choice(pairs: list[tuple]) -> object:
    """从 (标签, 权重) 二元组列表里按权重抽一个标签. 权重无需和为 1."""
    labels = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return random.choices(labels, weights=weights, k=1)[0]


# ----------------------------------------------------------------------------
# 业务校准常量 (Business Calibration Constants)
# ----------------------------------------------------------------------------

# 3 支分部战队的基本设定. Vanguard Fracture 和 Vanguard Aetherlane 是一线队,
# Vanguard Academy 是 Fracture Protocol 的发展联赛(Ascendant Circuit 层级)战队, 预算明显更小.
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

# 每支战队的月度"状态目标胜率", 用于生成比赛结果. 陷阱3(周边毛利与战绩挂钩)
# 依赖这几段刻意设计的低谷期(月份序号见 month_index): Fracture Protocol 一线队开局低谷
# (0-2 月, 呼应"近三年最差开局"), 后半程走强并在最后半年打出队史最佳战绩
# (18-23 月, 呼应 Q2 董事会关注的"这个赛季打进季后赛"); Aetherlane 一线队在赛季
# 中段(9-11 月)遭遇低谷; Academy 战队常年状态起伏更大, 在 15-17 月遭遇低谷.
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


# 选手花名册. legacy_star=True 的 4 名选手是陷阱2(薪资与战绩脱节)的核心样本:
# 他们在近 6 个月的表现评分相比历史高点显著下滑, 但薪资合同已在下滑前后被
# 长期锁定. 其余选手薪资与近期表现保持正相关, 作为对照组.
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

# 薪资与奖金分成比例区间, 按 (战队级别, 是否主力) 分层.
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
# 非 legacy 选手的表现评分基线区间(围绕 1.00 浮动), 用于让薪资与表现产生
# 正相关(约 0.55-0.65 的相关系数): 基线越高的选手, 薪资在区间内的位置也越高.
RATING_BASELINE_BAND_BY_TIER = {
    ("main_roster", True): (0.98, 1.15),
    ("main_roster", False): (0.85, 1.00),
    ("academy_roster", True): (0.90, 1.08),
    ("academy_roster", False): (0.80, 0.95),
}

# --- 陷阱2: 薪资与战绩脱节 ---------------------------------------------------
# legacy_star 选手的历史高点表现评分区间(REFERENCE_DATE 前 12-18 个月),
# 以及近 6 个月的下滑幅度(28%-36%, 均值约 32%). 续约日期落在下滑开始前后,
# 合同期拉长到 24-30 个月, 保证 REFERENCE_DATE 时合同剩余 18 个月以上.
LEGACY_STAR_PROFILE = {
    "Zenithrax": {"peak_rating": 1.22, "decline_ratio": 0.33, "last_renegotiation_date": date(2025, 12, 15), "term_months": 30},
    "Wraithcall": {"peak_rating": 1.15, "decline_ratio": 0.30, "last_renegotiation_date": date(2025, 10, 1), "term_months": 30},
    "Thornquil": {"peak_rating": 1.20, "decline_ratio": 0.34, "last_renegotiation_date": date(2025, 11, 1), "term_months": 27},
    "Hollowmere": {"peak_rating": 1.12, "decline_ratio": 0.28, "last_renegotiation_date": date(2025, 9, 15), "term_months": 29},
}
PEAK_WINDOW_START_DAYS_BEFORE_REF = 540  # 参考日前 18 个月
PEAK_WINDOW_END_DAYS_BEFORE_REF = 360  # 参考日前 12 个月
RECENT_WINDOW_START_DAYS_BEFORE_REF = 180  # 参考日前 6 个月

# --- 陷阱1: 赞助曝光计费缺口 -------------------------------------------------
# 10 家赞助商, 12 份赞助合同(TitanEnergy 和 NorthPeak 各有 2 份不同范围的合同).
# target_ratio 是"年化实测曝光 / 承诺曝光"的目标交付率: 3 份 rigged 合同
# (见 RIGGED_DEAL_NAMES)控制在约 0.68-0.72(系统性缺口 28%-32%), 其余 9 份控制在
# 0.93-1.08(健康交付). 注意: 承诺年度曝光小时数(committed_annual_exposure_hours)
# 不再在此硬编码, 而是在 gen_sponsor_exposure_logs 里依据该合同"可触及的直播总
# 时长"反算得到(见那里的 docstring), 以保证单场实测曝光永远不超过直播本身时长.
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
EXPOSURE_LOG_SAMPLE_RATE = 0.60  # 只有约 60% 的合资格直播会被内容团队实际测量记录
# 单场直播里品牌 logo 的实测可见占比(占该场直播总时长的比例). 是把"承诺年度曝光
# 小时数"反算成每场实测曝光的关键系数, 也是保证 measured <= 直播时长的物理约束来源:
# stream_logo_overlay 是常驻角标, 可见占比高; jersey_patch_estimate 只在选手/球衣
# 出镜时可见, 占比低. 两者都远小于 1, 叠加噪声后单场实测仍恒 < 直播时长.
EXPOSURE_VISIBILITY_BY_METHOD = {"stream_logo_overlay": 0.60, "jersey_patch_estimate": 0.35}

# --- 陷阱3: 周边毛利与战绩挂钩 ------------------------------------------------
TRAILING_WINRATE_WINDOW_DAYS = 60
MERCH_UNIT_COST_RATIO_RANGE = (0.42, 0.48)  # 单件成本占官方标价的比例
MERCH_DISCOUNT_HOT = (10.0, 4.0, 0.0, 25.0)  # (均值, 标准差, 下限, 上限)
MERCH_DISCOUNT_MID = (18.0, 5.0, 5.0, 35.0)
MERCH_DISCOUNT_SLUMP = (30.0, 6.0, 15.0, 45.0)
MERCH_HOT_WINRATE_THRESHOLD = 0.55
MERCH_SLUMP_WINRATE_THRESHOLD = 0.35
MERCH_SLUMP_QUANTITY_BOOST = 1.15  # 低谷期靠加大折扣拉动的额外销量倍数
TOTAL_MERCH_SALES = 9000

# --- 陷阱4: 奖金分成支付合规性(集中在 Vanguard Academy) -----------------------
# 校准目标: 全体分成记录里约 15% 逾期或短付, 其中约八成集中在 Academy 战队.
PRIZE_LATE_PROB_BY_TIER = {"academy_roster": 0.38, "main_roster": 0.045}
PRIZE_UNDERPAY_PROB_GIVEN_LATE = {"academy_roster": 0.48, "main_roster": 0.10}
PRIZE_UNDERPAY_PROB_GIVEN_ON_TIME = {"academy_roster": 0.17, "main_roster": 0.045}
PRIZE_UNDERPAY_RATIO_RANGE = (0.88, 0.95)
PRIZE_STANDARD_PAYMENT_TERM_DAYS = 30

# 每场赛事的名次奖金占赛事总奖金池的比例(Vanguard 一支战队能拿到的份额估算).
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
# ORM 模型 (拓扑顺序)
# ----------------------------------------------------------------------------


class Sponsor(Base):
    """赞助品牌方维度: 与俱乐部签约的品牌公司."""

    __tablename__ = "sponsor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    industry_category: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship_start_date: Mapped[date] = mapped_column(Date, nullable=False)


class Team(Base):
    """俱乐部旗下分部战队维度."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    game_title: Mapped[str] = mapped_column(String(30), nullable=False)
    competitive_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    home_city: Mapped[str] = mapped_column(String(60), nullable=False)
    founded_date: Mapped[date] = mapped_column(Date, nullable=False)
    salary_cap_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class RosterPlayer(Base):
    """在册选手主档, 归属某支分部战队."""

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
    """选手当前生效合同: 年薪, 合同起止日期, 上次续约日期, 奖金分成比例."""

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
    """赞助合同: 品牌方, 赞助范围(俱乐部整体或特定战队), 承诺年度曝光小时数."""

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
    """赛事维度: Vanguard 某支战队参加过的联赛赛段, 季后赛或第三方邀请赛."""

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
    """比赛结果: Vanguard 某支战队在某场赛事里的一场对局."""

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
    """选手单场比赛个人数据, 含综合表现评分, 是薪资/战绩脱节分析的核心依据."""

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
    """直播场次: 比赛类直播或非比赛类内容直播, 是赞助曝光测量的基础."""

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
    """赞助曝光实测记录: 某场直播里某份赞助合同的品牌 Logo 实测曝光小时数."""

    __tablename__ = "sponsor_exposure_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsorship_deal_id: Mapped[int] = mapped_column(ForeignKey("sponsorship_deal.id"), nullable=False)
    broadcast_session_id: Mapped[int] = mapped_column(ForeignKey("broadcast_session.id"), nullable=False)
    measured_exposure_hours: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)


class MerchSku(Base):
    """周边商品目录: 战队专属或俱乐部整体品牌商品."""

    __tablename__ = "merch_sku"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_cost_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    list_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class MerchSale(Base):
    """周边商品销售流水: 是周边毛利与战绩挂钩分析的核心表."""

    __tablename__ = "merch_sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merch_sku_id: Mapped[int] = mapped_column(ForeignKey("merch_sku.id"), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    unit_price_paid_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)


class PrizePoolPayout(Base):
    """赛事奖金到账记录: 赛事主办方向俱乐部支付某战队的赛事奖金."""

    __tablename__ = "prize_pool_payout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournament.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False)
    placement: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_prize_awarded_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    organizer_payout_date: Mapped[date] = mapped_column(Date, nullable=False)
    org_received_date: Mapped[date] = mapped_column(Date, nullable=False)


class PlayerPrizeDistribution(Base):
    """选手个人奖金分成明细: 合同应得 vs 实付金额/日期, 是支付合规性分析的核心表."""

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
# 维度表生成函数
# ----------------------------------------------------------------------------


def gen_sponsors() -> pl.DataFrame:
    """赞助品牌方维度: 10 家虚构品牌, 覆盖能量饮料/硬件/金融科技/服装等行业."""
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
    """3 支分部战队维度."""
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
    """在册选手主档, 21 名选手, 4 名标记为 legacy_star(仅供生成器内部使用,
    不落地成表列, 分析师需从薪资与近期表现评分反推)."""
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
    """选手当前生效合同. legacy_star 选手的续约日期落在其表现下滑开始前后,
    合同期拉长到 24-30 个月, 薪资定在其历史高点对应的档位(陷阱2的核心)."""
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
            # 薪资定在历史高点对应的评分百分位, 而不是当前(已下滑)的评分.
            peak_percentile = clamp((profile["peak_rating"] - rating_lo) / (rating_hi - rating_lo), 0.0, 1.0)
            annual_salary = salary_lo + peak_percentile * (salary_hi - salary_lo)
            annual_salary = clamp(max(annual_salary, salary_hi * 0.90) * random.uniform(0.95, 1.03), salary_lo, salary_hi)
            base_rating_mean = None  # legacy_star 用专门的时间轴函数计算评分, 不用固定基线
        else:
            base_rating_mean = random.uniform(rating_lo, rating_hi)
            rating_percentile = (base_rating_mean - rating_lo) / (rating_hi - rating_lo)
            # 70% 权重给表现百分位, 30% 随机噪声, 制造约 0.55-0.65 的薪资/表现相关性.
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
    """12 份赞助合同. 合同期跨越整个 24 个月数据窗口(部分提前于窗口开始签订).

    注意: committed_annual_exposure_hours(承诺年度曝光小时数)不在这里硬编码,
    而是稍后在 gen_sponsor_exposure_logs 里, 依据该合同"可触及直播样本的实测
    曝光总量"年化后除以目标交付率反算出来并回填(见那里的 docstring)。这样做
    同时保证 (a) 单场实测曝光恒 < 直播本身时长, (b) Query 1/3 用同一年化口径
    算出的交付率精确落在设计的 target_ratio 上。此处 committed 先占位 None,
    反算完成后一定会被覆盖成正数(见 generate_all_tsv 里的落地顺序)。"""
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
            "committed_annual_exposure_hours": None,  # 占位, 由 gen_sponsor_exposure_logs 反算回填
            "exposure_measurement_method": d["method"],
            "_team_key": d["team_key"],
            "_target_ratio": d["target_ratio"],
        })
    return rows


# 每支战队 8 个赛事参赛位, 均匀分布在 24 个月的窗口里(约每 3 个月一次赛事窗口).
TOURNAMENT_SLOT_COUNT = 8
TOURNAMENT_TIER_BY_SLOT_MAIN = ["A", "S", "A", "S", "A", "S", "A", "S"]
TOURNAMENT_TIER_BY_SLOT_ACADEMY = ["B", "B", "A", "B", "B", "A", "B", "A"]
TIER_POOL_RANGE = {"S": (700_000.0, 1_000_000.0), "A": (150_000.0, 300_000.0), "B": (30_000.0, 70_000.0)}
TOURNAMENT_NAME_BY_SLOT = [
    "Kickoff", "Split 1 Playoffs", "Split 2 Regular Season", "Split 2 Playoffs",
    "Kickoff", "Split 1 Playoffs", "Split 2 Regular Season", "Split 2 Playoffs",
]


def gen_tournaments(team_id_by_key: dict) -> list[dict]:
    """24 场赛事, 每支战队 8 场, 均匀分布在两个赛季里."""
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
    """给单场赛事参赛位生成小组赛/季后赛/总决赛比赛记录. 战队当月状态目标
    (team_monthly_target)决定每场胜负概率, 从而让近 60 天胜率随时间起伏,
    是陷阱3(周边毛利与战绩挂钩)的数据基础."""
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
        # 小组赛战绩过差(未进入季后赛且胜率低于 25%), 现实中这类"小组赛出局"
        # 的参赛通常拿不到任何奖金. placement=99 不在 PLACEMENT_PRIZE_SHARE 里,
        # 下游会按 share=0 处理并跳过奖金到账记录, 而不是硬凑一笔零花钱.
        placement = 99
    else:
        placement = 5 + min(3, int((0.45 - group_win_rate) * 10))

    return matches, placement


def gen_match_results_and_payouts(tournaments: list[dict]) -> tuple[list[dict], list[dict]]:
    """比赛结果表 + 奖金到账记录表. 一次性生成是因为 placement(名次)由
    模拟出来的小组赛/季后赛战绩决定, 奖金到账记录依赖这个名次."""
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
            # 小组赛出局且颗粒无收: 赛事方没有任何奖金要付给俱乐部, 现实中
            # 不会产生一笔"零元奖金到账"的记录, 因此这次参赛直接不生成
            # prize_pool_payout 行(自然也不会有对应的选手分成记录)。
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
# 选手个人比赛数据与陷阱2(薪资与战绩脱节)
# ----------------------------------------------------------------------------


def legacy_star_rating_mean(gamertag: str, match_date: date) -> float:
    """legacy_star 选手在给定日期的表现评分期望值: 历史高点(参考日前 18-12
    个月)到近 6 个月低谷之间做线性过渡."""
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
    """选手个人比赛数据. legacy_star 选手的评分按时间轴从历史高点过渡到近期
    低谷(陷阱2); 其余选手评分围绕各自固定基线小幅波动, 与薪资保持正相关."""
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
# 直播场次与赞助曝光实测(陷阱1)
# ----------------------------------------------------------------------------

BASE_VIEWERS_BY_TEAM_KEY = {"fracture_main": 35_000, "aetherlane_main": 40_000, "fracture_academy": 6_000}
TIER_VIEWER_FACTOR = {"S": 1.3, "A": 1.0, "B": 0.6}
STAGE_VIEWER_FACTOR = {"group_stage": 0.8, "playoffs": 1.3, "grand_final": 1.8}
FORMAT_DURATION_HOURS = {"Bo1": 1.3, "Bo3": 2.5, "Bo5": 4.0}
CONTENT_BROADCAST_COUNT_PER_TEAM = 33


def gen_broadcast_sessions(match_rows: list[dict], tournament_by_id: dict, team_key_by_id: dict) -> list[dict]:
    """直播场次: 每场比赛一场直播, 外加每支战队约 33 场非比赛类内容直播."""
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
    """赞助曝光实测记录, 同时反算并回填每份合同的承诺年度曝光小时数.

    物理量(单场实测曝光): measured = 该场直播时长 × 该计费方式的可见占比
    (EXPOSURE_VISIBILITY_BY_METHOD) × 轻微噪声(0.85-1.15)。因可见占比 <= 0.60、
    噪声上界 1.15, 单场实测曝光恒 <= 0.69 × 直播时长 < 直播时长, 从根本上杜绝
    "logo 曝光比整场直播还长"这种物理不可能(修复旧版 measured > duration 越界)。

    计费量(承诺年度曝光小时数): 先在"实测样本(约 60% 合资格直播)"上把上面的
    单场实测加总, 得到该合同的实测曝光总量; 年化(除以合同在数据窗口内的有效年数)
    后再除以目标交付率 target_ratio, 反算出 committed_annual_exposure_hours 并回填
    到 deal dict。因为 committed 由同一批实测样本反推而来, Query 1/3 用完全相同的
    年化口径算出的交付率会精确落在 target_ratio 上(健康合同 ~0.93-1.08, 3 份 rigged
    合同 ~0.68-0.72), 稳定制造陷阱1(赞助曝光计费缺口)。"""
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

        # 反算承诺年度曝光小时数 = 年化实测曝光 / 目标交付率. 取整到整小时, 让承诺值
        # 更像谈判出来的合同条款(顺带给交付率一点自然抖动, 不至于精确到 0.0pp)。
        # 极端兜底: 若该合同没有任何可测样本(正常数据不会发生), 给一个合理默认值,
        # 避免 committed 落成 NULL 违反 NOT NULL 约束。
        annualized_measured = total_measured / years_active
        committed = annualized_measured / deal["_target_ratio"] if annualized_measured > 0 else 100.0
        deal["committed_annual_exposure_hours"] = float(max(round(committed), 1))
        rows.extend(deal_logs)
    return rows


# ----------------------------------------------------------------------------
# 周边商品与销售(陷阱3)
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
    """25 款周边商品: 3 支战队各 6 款专属商品 + 7 款俱乐部整体品牌商品."""
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
    """指定日期往前 window_days 天内的胜率. 没有比赛记录时返回 0.5(中性)."""
    window_start = as_of - timedelta(days=window_days)
    windowed = [m for m in matches if window_start <= m["match_date"] <= as_of]
    if not windowed:
        return 0.5
    wins = sum(1 for m in windowed if m["result"] == "win")
    return wins / len(windowed)


def gen_merch_sales(merch_skus: list[dict], matches_by_team: dict, team_id_by_key: dict) -> list[dict]:
    """周边商品销售流水. 折扣力度和销量随对应战队(或全俱乐部)近 60 天滚动
    胜率变化: 低谷期折扣力度大幅上升, 销量因促销略有上升, 毛利率被显著压缩
    (陷阱3)。"""
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
# 奖金分成明细(陷阱4)
# ----------------------------------------------------------------------------


def gen_player_prize_distributions(payout_rows: list[dict], players: list[dict], contracts_by_player: dict, team_by_id: dict) -> list[dict]:
    """选手个人奖金分成明细. 只有先发主力选手参与分成. Vanguard Academy
    战队的分成记录逾期/短付概率显著更高, 集中体现陷阱4."""
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
# TSV 生成与 SQLite 加载
# ----------------------------------------------------------------------------


def _strip_private_fields(rows: list[dict]) -> list[dict]:
    """去掉生成过程内部使用, 不落地成表列的 _ 前缀字段."""
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
    # 05_sponsorship_deal.tsv 延后到曝光日志生成之后再写: committed_annual_exposure_hours
    # 需要由 gen_sponsor_exposure_logs 依据可触及直播样本反算后回填到 deal dict。

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
    # 至此 deals 里每个 dict 的 committed_annual_exposure_hours 已被反算填好, 可以落地。
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
