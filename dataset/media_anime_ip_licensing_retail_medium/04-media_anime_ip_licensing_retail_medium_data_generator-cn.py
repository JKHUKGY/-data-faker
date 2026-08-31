"""
媒体娱乐 — 动画 IP 衍生品授权与零售动销分析 假数据生成器
复杂度: Medium

业务背景:
Ember & Ash Licensing Group 是一家总部位于加州 El Segundo 的虚构北美娱乐 IP 授权代理
公司, 代理多部动画 IP 在北美的衍生品授权业务 (玩具、服饰、收藏卡牌、家居用品等), 对接
零售商, 按被授权商 (licensee) 的批发净销售额抽取版税 (royalty). 本数据集模拟从"签约
授权"到"零售动销"再到"版税结算稽核"的完整链路, 支撑以下分析:
1. 内容动销与续约优先级 (哪些 IP x 品类组合的零售 sell-through 最高, 值得续签)
2. 版税稽核与低报风险 (被授权商自报版税是否与 POS 推算的实际销售额相符)
3. 热度-动销滞后 (流媒体热度峰值与零售销售峰值之间的供应链滞后周数)
4. 越权铺货合规 (是否有被授权商在授权范围外的渠道铺货)
5. 保底金额 (minimum guarantee) 达成追踪 (哪些合同的版税进度落后于保底进度, 续约前需要重新谈判)

上述陷阱通过有意设计的相关分布注入: 动画 IP 的 popularity_tier 直接驱动 pos_sell_through
单行平均销量的梯度差异 (陷阱 1); licensee.compliance_score 把被授权商分成 "clean"
和 "risk" 两个群体, risk 群体同时驱动版税低报 (陷阱 2) 和越权铺货 (陷阱 4); popularity_tier
同时驱动 streaming_popularity_index 里的"新季首播"热度峰值, 该峰值会在
6-10 周后拉动对应 SKU 的零售销量 (陷阱 3); IP 热度层级与品类基础动销速度共同驱动版税
累计进度, 使部分合同的保底达成率天然偏低 (陷阱 5)。对应的 SQL 查询位于
media_anime_ip_licensing_retail_medium_sql_queries-cn.md, 用以暴露这些陷阱。
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
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "media_anime_ip_licensing_retail_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期.
REFERENCE_DATE = date(2026, 6, 30)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# 业务校准常量
# ============================================================================

# 流媒体热度追踪的时间跨度 (2 年), 早于授权/动销数据的窗口, 因为 Ember & Ash 会在一部
# 动画走红之前就开始跟踪它的热度, 才能判断值不值得投资授权.
POPULARITY_HORIZON_WEEKS = 104
POPULARITY_HORIZON_START = REFERENCE_DATE - timedelta(weeks=POPULARITY_HORIZON_WEEKS)

# 授权合同签约日期窗口. 上限留出至少约 5 个月的运行时间, 使 SKU 上市、POS 动销、
# 至少一期版税结算都有机会发生.
AGREEMENT_SIGN_START = REFERENCE_DATE - timedelta(days=680)
AGREEMENT_SIGN_END = REFERENCE_DATE - timedelta(days=150)

# 每个 IP 热度层级签出的授权合同数量区间. Breakout 级 IP (全网爆款) 吸引更多品类和
# 被授权商竞相拿授权; niche 级 IP 只有少数忠实品类愿意投入.
AGREEMENT_COUNT_RANGE_BY_TIER = {
    "breakout": (6, 9),
    "mainstream": (4, 6),
    "niche": (1, 3),
}

# IP 热度层级分布. 大多数在管 IP 是"稳定但不算爆款"的 mainstream, 少数几部是
# 全网出圈的 breakout, 还有一批长尾 niche 老番仍在小范围授权.
POPULARITY_TIER_WEIGHTS = {"breakout": 5, "mainstream": 13, "niche": 6}

# 每个热度层级的"新季首播"次数. 只有 breakout / mainstream 级 IP 在追踪窗口内有
# 明确的首播热度峰值; niche 级 IP 没有首播事件, 因此陷阱 3 (热度-动销滞后) 的信号
# 只在 breakout / mainstream 级 IP 上可靠观测到 —— 这一点在 SQL 查询文档里会明确提示。
PREMIERE_COUNT_BY_TIER = {"breakout": 2, "mainstream": 1, "niche": 0}

# 热度评分基线区间 (0-100 量表, 类比搜索热度 / 观看时长指数). Breakout 级 IP 连非首播
# 周也维持较高基线; niche 级 IP 长期在低位徘徊.
POPULARITY_BASELINE_RANGE_BY_TIER = {
    "breakout": (45, 65),
    "mainstream": (30, 52),
    "niche": (10, 28),
}

# 首播周热度峰值区间, 以及峰值衰减到基线所需的周数形状 (第 1/2/3 周分别保留
# 峰值的 70% / 45% / 25%).
PREMIERE_SPIKE_RANGE = (85, 100)
PREMIERE_DECAY_FACTORS = [1.0, 0.70, 0.45, 0.25]

# 陷阱 3 核心参数: 首播热度峰值到零售动销峰值之间的供应链滞后周数. 零售商看到
# 一部新季走红后, 需要走"追加订货 -> 补货到店"的流程, 通常滞后 6-10 周才会体现
# 在 POS 销量上, 而不是当周同步反应.
POPULARITY_TO_SALES_LAG_WEEKS = (6, 10)
LAG_BUMP_DURATION_WEEKS = 3
LAG_BUMP_MULTIPLIER_RANGE = (1.4, 1.9)

# 被授权商 compliance_score 的两个群体. "risk" 群体 (~25%) 历史上就有版税低报和
# 越权铺货的合规记录, 用同一个分数驱动陷阱 2 和陷阱 4, 呼应真实业务中"合规差的
# 被授权商往往在多个维度上都有问题"这一相关性.
LICENSEE_RISK_SHARE = 0.25
LICENSEE_COMPLIANCE_RANGE = {
    "clean": (70, 98),
    "risk": (35, 65),
}

# 陷阱 2 核心参数: risk 群体系统性把自报净销售额压低 8%-18% (均值约 13%); clean 群体
# 只有 ±2% 的正常申报噪音, 均值约 0%. royalty_audit_finding 用 POS 推算值反推真实
# 版税, 与自报版税对比, 差异会清楚地把两个群体分开.
UNDERREPORT_RATE_RANGE = {
    "risk": (0.08, 0.18),
    "clean": (-0.02, 0.02),
}

# 版税稽核状态判定阈值 (按 variance_pct = (POS 推算版税 - 自报版税) / POS 推算版税).
AUDIT_CONFIRMED_THRESHOLD_PCT = 12.0
AUDIT_FLAGGED_THRESHOLD_PCT = 5.0

# 陷阱 4 核心参数: risk 群体的 SKU 有 ~15% 概率额外在未授权渠道 (优先 ecommerce_marketplace,
# 因为电商平台最容易被灰色转售渗透; 若该渠道已授权则退化为 direct_to_consumer_online)
# 产生销量. clean 群体只有 ~1% 的噪音, 不构成系统性违规.
UNAUTHORIZED_CHANNEL_LEAK_PROB = {"risk": 0.15, "clean": 0.01}

# 品类基础表, 覆盖典型北美动画衍生品品类. benchmark_royalty_rate_pct 是行业惯例的
# 批发净销售额版税率参考值 (消费品娱乐授权通常 7%-12%).
PRODUCT_CATEGORIES = [
    (1, "toys_action_figures", "Toys & Action Figures", 10.0),
    (2, "apparel", "Apparel", 8.0),
    (3, "collectible_trading_cards", "Collectible Trading Cards", 12.0),
    (4, "home_goods_decor", "Home Goods & Decor", 9.0),
    (5, "stationery_office", "Stationery & Office", 7.0),
    (6, "accessories_bags", "Accessories & Bags", 10.0),
]

# 每张合同下的 SKU 数量区间, 按品类差异化 —— 收藏卡牌品类天然 SKU 密度最高
# (不同角色/系列各出一款), 家居用品最低.
SKU_COUNT_RANGE_BY_CATEGORY = {
    "toys_action_figures": (5, 10),
    "apparel": (4, 8),
    "collectible_trading_cards": (6, 13),
    "home_goods_decor": (3, 6),
    "stationery_office": (4, 7),
    "accessories_bags": (3, 6),
}

# MSRP 区间 (美元), 按品类. wholesale_price_usd 按行业惯例的 "keystone" 批发-零售
# 加价法则 = MSRP 的 50%, 见 gen_product_skus.
MSRP_RANGE_BY_CATEGORY = {
    "toys_action_figures": (12, 35),
    "apparel": (18, 45),
    "collectible_trading_cards": (5, 25),
    "home_goods_decor": (15, 60),
    "stationery_office": (6, 20),
    "accessories_bags": (20, 70),
}

# 每周每 SKU 每渠道的基础动销件数均值, 按品类差异化 (卡牌复购频次最高, 家居最低),
# 随后再乘以 IP 热度层级乘数.
CATEGORY_BASE_WEEKLY_UNITS = {
    "toys_action_figures": 40,
    "apparel": 30,
    "collectible_trading_cards": 60,
    "home_goods_decor": 18,
    "stationery_office": 22,
    "accessories_bags": 25,
}

# IP 热度层级对动销速度的乘数. 这也是陷阱 5 (保底达成率) 的底层驱动力之一 ——
# niche 级 IP 天然动销慢, 版税累计进度容易落后于保底金额的分摊进度.
POPULARITY_TIER_SELLTHROUGH_MULTIPLIER = {"breakout": 1.8, "mainstream": 1.0, "niche": 0.45}

# 产品生命周期形状: 上市后 8 周内爬坡到满速; 第 30 周起每周衰减 1.8%, 衰减下限 35%.
LIFECYCLE_RAMP_WEEKS = 8
LIFECYCLE_DECAY_START_WEEK = 30
LIFECYCLE_DECAY_PER_WEEK = 0.018
LIFECYCLE_DECAY_FLOOR = 0.35

# SKU 提前下架的概率, 以及下架发生在上市后的天数区间.
SKU_DISCONTINUE_PROB = 0.15
SKU_DISCONTINUE_DAYS_RANGE = (150, 400)

# 授权渠道数量权重 (每份合同授权 1-3 个零售渠道), 以及每个渠道被选中的相对权重.
CHANNEL_COUNT_WEIGHTS = {1: 30, 2: 45, 3: 25}
CHANNEL_SELECTION_WEIGHTS = {
    "big_box_retail": 35,
    "specialty_retail": 30,
    "ecommerce_marketplace": 25,
    "direct_to_consumer_online": 7,
    "convention_pop_up": 3,
}

# 保底金额 (minimum guarantee) 按品类的基础金额, 再乘以 IP 热度层级和地域范围乘数,
# 最后加 ±30% 的谈判噪音. 保底通常低于"预期"版税, 不是惩罚性条款.
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

# 合同期限选项 (月) 及权重; 提前终止概率 (与合规无关的独立小概率, 保持简单).
CONTRACT_TERM_MONTHS_WEIGHTS = {12: 15, 18: 25, 24: 35, 36: 25}
CONTRACT_EARLY_TERMINATION_PROB = 0.04


def week_floor(d: date) -> date:
    """把任意日期归到该周的周一 (ISO 周起点)."""
    return d - timedelta(days=d.weekday())


def risk_tier_for_score(score: float) -> str:
    """按 compliance_score 阈值把被授权商归入 clean / risk 群体."""
    return "risk" if score < 66 else "clean"


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""

    pass


class ProductCategory(Base):
    """衍生品品类查找表, 含品类基准版税率."""

    __tablename__ = "product_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    benchmark_royalty_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class RetailChannel(Base):
    """零售渠道查找表 (大盒子连锁 / 专卖店 / 电商 / 官网直营 / 展会快闪)."""

    __tablename__ = "retail_channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)


class AnimeIp(Base):
    """被授权动画 IP. 每个 IP 关联一个流媒体首播平台和热度层级."""

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
    """被授权商 (北美衍生品制造/分销企业)."""

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
    """Ember & Ash 内部的授权经理, 负责被授权商关系与合同组合."""

    __tablename__ = "account_manager"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    region_focus: Mapped[str] = mapped_column(String(50), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)


class LicenseAgreement(Base):
    """一份授权合同: 一个 IP x 一个被授权商 x 一个品类的授权条款."""

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
    """合同授权渠道桥接表 (M:N): 一份合同可以授权 1-3 个零售渠道."""

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
    """衍生品 SKU, 隶属于某一份授权合同."""

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
    """动画 IP 在流媒体端的周度热度指数 (外部参考数据)."""

    __tablename__ = "streaming_popularity_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_ip_id: Mapped[int] = mapped_column(ForeignKey("anime_ip.id"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    popularity_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_season_premiere_week: Mapped[bool] = mapped_column(Boolean, default=False)


class PosSellThrough(Base):
    """零售终端周度动销事实表 (POS: point of sale)."""

    __tablename__ = "pos_sell_through"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_sku_id: Mapped[int] = mapped_column(ForeignKey("product_sku.id", ondelete="CASCADE"), nullable=False)
    retail_channel_id: Mapped[int] = mapped_column(ForeignKey("retail_channel.id"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    net_wholesale_revenue_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    ending_inventory_units: Mapped[int] = mapped_column(Integer, nullable=False)


class RoyaltyReport(Base):
    """被授权商按合同期分期自报的版税流水."""

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
    """版税稽核结果: 自报版税与 POS 推算版税的对比."""

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
# 生成器函数 (按拓扑顺序)
# ============================================================================

def gen_product_categories() -> pl.DataFrame:
    """生成衍生品品类查找表."""
    return pl.DataFrame(
        PRODUCT_CATEGORIES,
        schema=["id", "category_code", "category_name", "benchmark_royalty_rate_pct"],
        orient="row",
    )


def gen_retail_channels() -> pl.DataFrame:
    """生成零售渠道查找表."""
    channels = [
        (1, "big_box_retail", "Big Box Retail Chains", "offline"),
        (2, "specialty_retail", "Specialty Retail Stores", "offline"),
        (3, "ecommerce_marketplace", "E-commerce Marketplace", "online"),
        (4, "direct_to_consumer_online", "Direct-to-Consumer Online Store", "online"),
        (5, "convention_pop_up", "Convention & Pop-up Retail", "offline"),
    ]
    return pl.DataFrame(channels, schema=["id", "channel_code", "channel_name", "channel_type"], orient="row")


def gen_anime_ips() -> pl.DataFrame:
    """生成被授权动画 IP 维度表.

    popularity_tier 按 POPULARITY_TIER_WEIGHTS 的目标计数直接分配 (而非概率抽样), 保证
    每次运行的层级构成完全确定, 便于文档里引用精确数量.
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
    # 虚构流媒体平台. Vantage Anime Networks 与另一虚构北美动画数据集共享同一个宇宙设定.
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
    """生成被授权商维度表.

    compliance_score 按 LICENSEE_RISK_SHARE 的目标比例分配到 clean / risk 两个群体
    (确定性分配, 而非概率抽样), 这个 risk_tier 标签是陷阱 2 (版税低报) 与陷阱 4
    (越权铺货) 共同的驱动信号.
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
    """生成 Ember & Ash 内部授权经理团队."""
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
    """生成授权合同.

    每个 IP 按热度层级抽取一组 (licensee, category) 组合, 避免同一 IP 下出现完全
    重复的 (licensee, category) 组合. minimum_guarantee_usd 按品类基础金额 x IP
    热度层级 x 地域范围三重加权 —— 是陷阱 5 (保底达成率) 的对照基准.
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
    """生成合同授权渠道桥接表 (每份合同授权 1-3 个渠道)."""
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
        # 按固定的 channel_codes 顺序落表, 而非直接迭代 set —— set[str] 的迭代顺序受 Python
        # 哈希随机化 (PYTHONHASHSEED, 本环境默认未固定) 影响, 会使同一份合同的授权渠道每次运行
        # 被写成不同的 id 顺序, 破坏本生成器承诺的"多次运行结果一致"。此处的 random.choices 抽样
        # 逻辑完全不变 (RNG 流不受影响), 仅把落表顺序钉成确定性: 用固定顺序过滤 chosen_codes。
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
    """生成衍生品 SKU. 上市日期跟随合同起始日, 加上产品开发周期滞后."""
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
            # 批发-零售"keystone"加价惯例: 批发价约为建议零售价的 50%, 上下浮动 5%.
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
    """生成流媒体热度周度指数, 并返回每个 IP 的"动销拉动窗口" (陷阱 3 用).

    对每个首播事件, 生成一个从"首播周 + 6-10 周随机滞后"开始、持续 3 周的
    拉动窗口, gen_pos_sell_through 会在这些窗口内提升对应 IP 的 SKU 销量.
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

        # 首播周必须留出足够的后续窗口 (滞后 + 拉动持续时间) 才能落在追踪期内.
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

        # 逐周生成热度分数; 首播周及其后 3 周按 PREMIERE_DECAY_FACTORS 叠加基线.
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
    """生成零售终端周度动销事实表.

    这是数据集中最大的事实表, 也是陷阱 3 (热度-动销滞后) 和陷阱 4 (越权铺货) 的
    直接来源: 授权渠道内的常规动销叠加"热度拉动窗口"乘数; risk 群体的被授权商
    另有小概率在未授权渠道 (通常是 ecommerce_marketplace) 额外产生销量。
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
    """生成被授权商季度自报版税, 以及配套的稽核结果.

    版税结算周期跟随每份合同自己的"合同季度" (从 contract_start_date 起每 91 天一期),
    而非日历季度 —— 这是消费品授权合同的常见做法。POS 推算净销售额是同一份合同、
    同一时间窗口内 pos_sell_through 的真实总和 (跨所有渠道); reported_net_sales_usd
    按 risk_tier 对应的 UNDERREPORT_RATE_RANGE 压低, 制造陷阱 2 的可稽核偏差。
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

    # 按 (sku_id) 分组预排序周列表, 加速区间求和.
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
# 主流程 (幂等)
# ============================================================================

def generate_all_tsv() -> None:
    """生成所有 TSV 文件. 幂等: 先删除 data/ 下已有的 TSV 文件."""
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
    """从 TSV 文件构建 SQLite 数据库. 幂等: 先删除已有数据库文件.

    使用 Core API 批量加载模式: 一份按拓扑顺序排列的 (TSV 文件名, Table) 列表,
    一个 for 循环, 一个 engine.begin() 事务.
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
    """主入口."""
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
