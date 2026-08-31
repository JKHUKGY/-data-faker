"""
游戏 F2P 手游内购与巨鲸留存健康度假数据生成器
复杂度: Medium

业务背景:
Pinnacle Peak Games 是一家总部位于西雅图的虚构手游studio, 旗舰产品是 F2P 收集
养成 RPG 手游《Ember Realms Saga》. 本数据集抽样 5,000 名玩家过去约 18 个月的
经济行为(安装, 内购, 抽卡, 参与 Live-Ops 活动, 退款/拒付, 客服工单), 支持以下
5 个业务陷阱的分析:

1. 巨鲸依赖陷阱: 前 1% 玩家(50人)贡献约 65% 内购收入, dolphin(3%)约 28%,
   minnow(6%)约 6%, 收入高度集中在极少数玩家身上.
2. 概率池披露偏差陷阱: 5 个限定 (limited_rateup) 卡池中有 3 个的传说(legendary)
   实际掉率显著低于官方公示概率, 另外 2 个作为"诚实对照组"与公示一致; 常驻
   (standard) 卡池全部诚实. 只看"限定 vs 常驻"整体均值会被 2 个诚实限定池稀释,
   必须逐池比对才能揪出问题.
3. Live-Ops 活动假繁荣陷阱: 高频扎堆(stacked, 间隔小于7天)活动短期内拉高
   参与玩家的内购频次与客单价, 但这批玩家后续 30 天内活跃(留下任何行为记录)的
   比例显著低于正常节奏活动的参与者, 呈现"寅吃卯粮"的假繁荣.
4. 代充/优惠渠道套利陷阱: 未授权第三方代充商(third_party_agent, is_authorized=
   false)的交易实付价格系统性低于官方牌价, 且退款/拒付率远高于官方渠道基线;
   同时部分区域专属优惠码(discount_code.leaked_beyond_scope=true)被大量在
   非目标区域核销, 说明优惠码被泄露套利.
5. 退款欺诈团伙陷阱: 一批玩家共享同一个 device_fingerprint_hash(疑似同一台
   设备批量注册的马甲账号), 这批账号的退款/拒付发生率远高于普通玩家, 且发生
   模式高度集中(短时间内, 少数指纹), 与陷阱 4 的代充问题是两条独立但都指向
   欺诈风险的线索.

上述陷阱通过有意设计的相关分布注入. 对应的 SQL 查询位于
03-gaming_f2p_whale_monetization_medium_sql_queries-cn.md, 用以暴露这些陷阱.
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
# 配置常量
# ----------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "gaming_f2p_whale_monetization_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期.
REFERENCE_DATE = date(2026, 6, 30)
# 游戏全球上线日. 玩家 install_date 从这一天开始抽样.
LAUNCH_DATE = date(2025, 1, 6)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ----------------------------------------------------------------------------
# 业务校准常量 (Business Calibration Constants)
# ----------------------------------------------------------------------------

# 玩家规模与付费分层. 数字是这份分析样本的精确人数(而非概率), 保证"前1%"这样的
# 表述在样本里能精确对上. 90% 玩家从不付费(F2P 手游常态), 付费玩家里再按
# minnow/dolphin/whale 三级细分, whale 精确等于样本的前 1% (50人).
PLAYER_COUNT = 5000
SEGMENT_COUNTS = {
    "whale": 50,  # 前 1%. 陷阱1 的核心分组.
    "dolphin": 150,  # 前 4%(含whale为前4%).
    "minnow": 300,  # 前 10%(含以上).
    "non_payer": 4500,  # 后 90%, 内购收入贡献为 0.
}

# 各付费分层的内购笔数均值(高斯分布中心). 实际客单价不在这里直接设定, 而是由
# PRODUCT_WEIGHTS_BY_SEGMENT 选中的商品 base_price_usd × 地区 price_index 决定:
# whale 明显偏好大额礼包, minnow 偏好入门小额包. "笔数更多"叠加"客单价更高", 经校准后
# whale 贡献约 65% 收入, dolphin 约 28%, minnow 约 6% -- 呼应陷阱1的巨鲸依赖.
SEGMENT_TX_COUNT_MEAN = {
    "whale": 110,
    "dolphin": 50,
    "minnow": 14,
}

# 各付费分层的抽卡(gacha pull)次数均值. whale/dolphin/minnow 靠内购的水晶抽卡,
# non_payer 靠每日登录/活动赠送的免费水晶偶尔抽卡, 均值远低于付费玩家.
SEGMENT_GACHA_PULL_MEAN = {
    "whale": 250,
    "dolphin": 80,
    "minnow": 25,
    "non_payer": 1.5,
}

# 各付费分层的基础留存"寿命"(天), 即从安装到自然停止活跃的均值天数, 指数分布
# 抽样后再夹到 [7, 参考日窗口] 区间. 付费越深的玩家留存时间通常越长.
SEGMENT_TENURE_MEAN_DAYS = {
    "whale": 480,
    "dolphin": 300,
    "minnow": 150,
    "non_payer": 55,
}

# --- 陷阱2: 概率池披露偏差 ---------------------------------------------------
# 常驻(standard)卡池: 全部诚实, 实际掉率与公示一致(仅有极小随机噪声).
# 限定(limited_rateup)卡池: 5 个里有 3 个"被操纵", 实际传说掉率显著低于公示;
# 另外 2 个作为诚实对照组, 掉率与公示接近. 只看"限定卡池整体均值"会被 2 个诚实
# 对照组稀释掉信号, 必须逐个卡池比对才能揪出这 3 个真正有问题的卡池.
RIGGED_LIMITED_POOLS = {
    "Ember Queen Rate-Up Banner": {"disclosed": 3.0, "actual": 1.7},
    "Frostbound Knight Rate-Up Banner": {"disclosed": 3.0, "actual": 1.8},
    "Anniversary Celebration Banner": {"disclosed": 3.5, "actual": 2.0},
}
HONEST_LIMITED_POOLS = {
    "Shadowfang Assassin Rate-Up Banner": {"disclosed": 3.0, "actual": 2.9},
    "Golden Phoenix Rate-Up Banner": {"disclosed": 3.0, "actual": 3.1},
}

# --- 陷阱3: Live-Ops 活动假繁荣 ----------------------------------------------
# 扎堆活动定义: 与上一场活动结束日间隔 < 7 天. 玩家若参与 >= 2 场扎堆活动,
# 有 STACKED_FATIGUE_CHURN_PROB 的概率会在最后一场扎堆活动后 15-25 天内提前
# "熄火"(后续所有行为记录被截断), 模拟活动疲劳导致的次月留存塌方.
STACKED_EVENT_GAP_DAYS = 7
STACKED_FATIGUE_MIN_COUNT = 2
STACKED_FATIGUE_CHURN_PROB = 0.55
STACKED_FATIGUE_CUTOFF_MIN_DAYS = 15
STACKED_FATIGUE_CUTOFF_MAX_DAYS = 25
# 扎堆活动窗口内, 参与玩家的内购客单价/频次临时倍增, 制造短期 ARPPU 假象.
STACKED_EVENT_SPEND_MULTIPLIER = 1.8

# --- 陷阱4: 代充/优惠渠道套利 ------------------------------------------------
# 未授权代充商(is_authorized=false)交易的实付价格相对官方牌价的折扣系数,
# 以及这批交易的退款/拒付率(远高于官方渠道基线 2%).
UNAUTHORIZED_AGENT_PRICE_FACTOR = 0.68
UNAUTHORIZED_AGENT_CHARGEBACK_RATE = 0.20
OFFICIAL_CHANNEL_CHARGEBACK_RATE = 0.02
AUTHORIZED_AGENT_CHARGEBACK_RATE = 0.04

# 泄露优惠码在目标区域外核销的比例(正常优惠码目标区域外核销率应 < 10%).
LEAKED_CODE_OUT_OF_SCOPE_RATE = 0.75
NORMAL_CODE_OUT_OF_SCOPE_RATE = 0.06

# --- 陷阱5: 退款欺诈团伙(设备指纹马甲号) -------------------------------------
FRAUD_RING_COUNT = 10
FRAUD_RING_SIZE_MIN = 4
FRAUD_RING_SIZE_MAX = 5
FRAUD_RING_CHARGEBACK_RATE = 0.45  # 团伙账号自身的退款/拒付发生率


class Base(DeclarativeBase):
    pass


# ----------------------------------------------------------------------------
# ORM 模型 (拓扑顺序)
# ----------------------------------------------------------------------------


class ChannelPartner(Base):
    """内购支付渠道维度: 官方商店/官方网页直购/官方授权区域代收款伙伴/未授权第三方代充商."""

    __tablename__ = "channel_partner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    region_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    commission_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    onboarded_date: Mapped[date] = mapped_column(Date, nullable=False)


class RegionPriceTier(Base):
    """玩家计费所在国家/地区的官方定价系数维度, 用于识别区域套利."""

    __tablename__ = "region_price_tier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    country_name: Mapped[str] = mapped_column(String(60), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    price_index: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    is_arbitrage_source_region: Mapped[bool] = mapped_column(Boolean, nullable=False)


class IapProduct(Base):
    """内购商品目录: 各档位水晶包/礼包/月卡的官方美元牌价."""

    __tablename__ = "iap_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String(80), nullable=False)
    product_category: Mapped[str] = mapped_column(String(20), nullable=False)
    shard_amount: Mapped[int] = mapped_column(Integer, nullable=True)
    base_price_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class GachaPool(Base):
    """抽卡卡池维度: 常驻池全年开放, 限定池围绕角色上线做 2-3 周限时投放."""

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
    """优惠码维度: 官方生命周期营销码, 区域专属促销码, 达人合作码, 以及被泄露套利的区域码."""

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
    """Live-Ops 活动日历: 登录奖励/掉落翻倍/限时特惠/角色联动/周年庆等活动类型."""

    __tablename__ = "live_ops_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_stacked_event: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Player(Base):
    """玩家账号主档: 安装归因, 计费地区, 设备指纹, 付费分层与经济健康度快照(截至 REFERENCE_DATE)."""

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
    """内购交易流水: 每一笔水晶/礼包购买, 记录支付渠道, 计费地区, 牌价与实付价."""

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
    """抽卡记录: 每一次单抽/十连抽的结果稀有度, 用于比对公示概率与实际概率."""

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
    """玩家参与 Live-Ops 活动的记录, 用于衡量活动短期拉动与后续留存的关系."""

    __tablename__ = "event_participation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    live_ops_event_id: Mapped[int] = mapped_column(ForeignKey("live_ops_event.id"), nullable=False)
    participation_date: Mapped[date] = mapped_column(Date, nullable=False)
    shard_spent_during_event: Mapped[int] = mapped_column(Integer, nullable=True)
    completed_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RefundChargebackRiskEvent(Base):
    """退款/拒付/疑似代充团伙风险事件, 关联具体交易, 用于欺诈与渠道治理分析."""

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
    """客服工单: 概率池投诉, 账单纠纷, 封号申诉, 一般 bug 反馈等."""

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
# 维度表生成函数
# ----------------------------------------------------------------------------


def gen_channel_partners() -> pl.DataFrame:
    """支付渠道维度: 2 个官方商店 + 官方网页 + 2 个官方授权区域代收款伙伴 + 5 个未授权代充商."""
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
    """计费地区定价系数维度. TR/AR/PH/IN/ID/BR 是价格套利常见的来源地区(本币贬值或区域定价折扣大)."""
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
    """内购商品目录: 从 0.99 美元的入门水晶包到 199.99 美元的巨鲸档礼包."""
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


# 陷阱2: 3 个限定池被操纵(实际传说掉率显著低于公示), 2 个限定池诚实, 3 个常驻池全部诚实.
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
    """抽卡卡池维度. legendary_disclosed 是公示概率(写入 DDL 列), legendary_actual 只用于
    抽卡结果生成, 不落地成表列 -- 分析师必须从 gacha_pull_log 的真实结果反推实际概率."""
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
    """优惠码维度: 官方邮件营销码, 达人合作码, 区域专属促销码(其中 4 个被泄露套利, 陷阱4)."""
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
    # 区域专属促销码: 19 个, 目标区域集中在套利高发的 6 个地区; 其中 4 个被泄露(陷阱4).
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


# 30 场 Live-Ops 活动, 用显式的时长/间隔序列制造 8 场"扎堆"活动(陷阱3).
EVENT_DURATIONS = ([10, 6] * 15)
EVENT_GAP_SMALL_POSITIONS = {3, 4, 10, 11, 17, 18, 24, 25}
EVENT_TYPE_NAMES = {
    "login_bonus": ["Daily Login Bonanza", "Welcome Back Rewards", "Login Streak Festival"],
    "double_drop_rate": ["Double Drop Weekend", "Loot Surge", "Material Rush"],
    "flash_sale": ["Flash Shard Sale", "Weekend Value Bundle Sale", "Limited Time Discount Vault"],
    "rate_up_banner_tie_in": ["Rate-Up Banner Celebration", "New Hero Spotlight", "Banner Debut Festival"],
    # 展示名不绑定具体日历日期, 避免 i%5 轮转把"周年/founders"字样落到语义不符的月份.
    # (真正落在 2026-01-06 周年点的是 gacha 的 "Anniversary Celebration Banner", 与此无关.)
    "anniversary": ["Grand Realm Festival", "Ember Champions Gala", "Realm Legends Showcase"],
}
EVENT_TYPE_CYCLE = ["login_bonus", "double_drop_rate", "flash_sale", "rate_up_banner_tie_in", "anniversary"]


def gen_live_ops_events() -> pl.DataFrame:
    """Live-Ops 活动日历. 8 场活动与上一场活动间隔 < 7 天(扎堆), 其余间隔 12 天(正常节奏)."""
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
# 玩家主档与陷阱5(设备指纹欺诈团伙)
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

# 计费地区权重. 55% 落在美加英德等"发达"市场, 45% 落在套利高发的 6 个地区,
# 保证陷阱4(区域套利)有足够样本量可供分析.
REGION_WEIGHTS = {
    "US": 0.25, "CA": 0.12, "GB": 0.10, "DE": 0.08, "BR": 0.10,
    "TR": 0.08, "AR": 0.07, "PH": 0.08, "IN": 0.07, "ID": 0.05,
}


def weighted_choice(pairs: list[tuple]) -> object:
    """从 (标签, 权重) 二元组列表里按权重抽一个标签. 权重无需和为 1."""
    labels = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return random.choices(labels, weights=weights, k=1)[0]


def gen_players(region_rows: list[dict]) -> list[dict]:
    """玩家主档. whale/dolphin/minnow/non_payer 人数精确固定为样本的 1%/3%/6%/90%(陷阱1);
    48 名玩家分成 10 组(每组 4-5 人)共享同一个设备指纹, 模拟同一台设备批量注册的马甲号团伙(陷阱5)."""
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
# Live-Ops 活动参与与陷阱3(扎堆活动假繁荣)
# ----------------------------------------------------------------------------

EVENT_PARTICIPATION_BASE_PROB = {
    "whale": 0.90,
    "dolphin": 0.75,
    "minnow": 0.55,
    "non_payer": 0.30,
}


def gen_event_participation(players: list[dict], events: list[dict]) -> list[dict]:
    """玩家活动参与记录. 先按玩家 baseline 活跃窗口生成一版参与记录, 再据此判定
    参与过 >= 2 场扎堆活动的玩家里有约 55% 会提前熄火(陷阱3), 并用缩短后的窗口
    重新过滤参与记录, 让熄火玩家后续所有行为记录(不止活动参与)都随之收窄."""
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
# 内购交易与陷阱1(巨鲸依赖) / 陷阱3(短期加价) / 陷阱4(代充渠道折价)
# ----------------------------------------------------------------------------

# 各付费分层偏好的商品档位权重. whale 明显偏向大额礼包, minnow 偏向入门小额包.
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
    """支付渠道抽样. 官方商店/网页占约 96%, 未授权代充商约 2.8%, 官方授权区域伙伴约 1.2%."""
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
    """内购交易流水. 巨鲸档位商品集中在大额礼包(陷阱1的分层基础); 未授权代充渠道
    (unauthorized_agent)实付价系统性低于官方牌价(陷阱4); 每笔交易有约 12% 的概率
    被刻意锚定到扎堆活动窗口内并临时加价(实际约占全部交易的 8%-9%, 是陷阱3 的
    短期假繁荣信号)."""
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
    """事后给一部分交易挂上优惠码(就地修改 transactions). 4 个被标记 leaked_beyond_scope
    的区域专属促销码, 故意让约 75% 的核销落在目标区域之外; 其余 15 个正常区域码
    核销落在区域外的比例被控制在约 6%(陷阱4 的核心信号)."""
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
# 抽卡记录与陷阱2(概率池披露偏差)
# ----------------------------------------------------------------------------

STANDARD_POOL_WEIGHT = 1.0
LIMITED_POOL_WEIGHT_WHEN_ACTIVE = 22.0
RARITY_LEVELS = ["Common", "Rare", "Epic", "Legendary"]


def build_gacha_pool_runtime(gacha_pool_df: pl.DataFrame) -> list[dict]:
    """把 GACHA_POOL_DEFS 里只用于抽样, 不落地成表列的实际概率(legendary_actual 等)
    和已生成的 DB id 拼在一起, 供 gen_gacha_pull_logs 使用."""
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
    """按卡池的实际概率(而非公示概率)抽出结果稀有度. 二者之差正是陷阱2的核心."""
    weights = [pool["_actual_common"], pool["_actual_rare"], pool["_actual_epic"], pool["_actual_legendary"]]
    return random.choices(RARITY_LEVELS, weights=weights, k=1)[0]


def gen_gacha_pull_logs(players: list[dict], gacha_pools: list[dict]) -> list[dict]:
    """抽卡记录. 限定池活跃期间玩家会集中抽卡(权重更高); 3 个限定池的实际传说
    掉率显著低于公示概率, 另外 2 个限定池与常驻池一样诚实(陷阱2)."""
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
# 退款/拒付风险事件(陷阱4 代充渠道 + 陷阱5 设备指纹欺诈团伙)
# ----------------------------------------------------------------------------


def gen_refund_chargeback_events(transactions: list[dict], players_by_id: dict) -> list[dict]:
    """退款/拒付/疑似代充团伙风险事件. 设备指纹欺诈团伙账号(~45%)与未授权代充渠道
    (~20%)的发生率远高于官方渠道基线(~2%), 官方授权区域伙伴居中(~4%)(陷阱4/陷阱5)."""
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
        # event_date 落在交易日后 1-21 天, 但对基准日 REFERENCE_DATE 封顶: 分析快照口径是
        # "截至 2026-06-30", 不应出现晚于快照的风险事件(封顶只影响极少数临近快照日的交易).
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
# 客服工单
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
    """客服工单. 付费越深的玩家开工单概率越高, billing_dispute/refund_request_followup
    类别在有内购记录的玩家里才会关联具体交易."""
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
# 玩家快照字段回填
# ----------------------------------------------------------------------------


def finalize_players(
    players: list[dict],
    transactions: list[dict],
    gacha_pulls: list[dict],
    event_participations: list[dict],
    support_tickets: list[dict],
) -> None:
    """回填玩家快照字段(就地修改 players): 生涯消费, 最后活跃日, 流失风险分."""
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
# TSV 编排与 SQLite 构建
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
