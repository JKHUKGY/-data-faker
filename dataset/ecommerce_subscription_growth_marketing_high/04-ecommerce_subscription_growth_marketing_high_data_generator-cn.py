"""
电商零售 - 订阅增长营销虚拟数据生成器
复杂度：高（16 张表）
生成者：Fake Data Generator Agent

业务背景：
VerdantBox 是一家北美直面消费者（DTC）的订阅平台，专注于有机、
植物基和功能性健康食品。客户订阅 VerdantBox+ 会员，以获得免运费、
会员专属定价以及独家精选盒子。营销团队围绕三大目标持续运营一个
增长 campaign 组合：ACQUISITION（付费社媒、搜索、推荐）、
MEMBERSHIP_CONVERSION（试用转付费推动）以及 REACTIVATION
（唤回沉睡客户）。

本数据集涵盖：
  * 历史基线（约 18 个月的客户、订单、已完成的 campaign）
  * 当前进行中的 campaign（最近 30 天，持续的 touchpoint 与订单）
  * 计划中的 campaign（未来 30 天，已设定目标 segment 但尚无表现数据）

这套 16 张表的 schema 支持 cohort 分析、漏斗视图、RFM 分群、
会员与非会员 LTV 分析、multi-touch attribution、渠道 ROAS、
campaign 组合复盘以及 promo 兑换跟踪。

关键不变量（KEY INVARIANTS，在生成结束时通过一轮 reconciliation 强制保证）：
  * order.subtotal_usd = 每个 order 的 SUM(order_item.line_total_usd)
  * order.item_count   = 每个 order 的 COUNT(order_item)
  * order.total_usd    = subtotal + shipping + tax − discount
  * order.is_first_order = 当且仅当该 order 是该客户的 MIN(order_date) 时为 True
  * order.attributed_campaign_id 通过真实 last-touch 计算（即订单前 60 天内
    最近一次 click/convert 的 touchpoint_response），当不存在 touchpoint 链路
    时回退为按日期窗口分配
  * campaign_channel.spend_to_date_usd = SUM(marketing_touchpoint.cost_usd)
  * promo_code.redemption_count        = COUNT(promo_redemption)
  * creative_asset.is_winner：每个 (campaign, asset_type) 至多一个 winner
"""

from __future__ import annotations
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import polars as pl
from faker import Faker
from sqlalchemy import (
    create_engine,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "ecommerce_subscription_growth_marketing_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# 参考“今天” — 保证生成过程具有确定性
TODAY = date(2026, 6, 1)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    pass


class ChannelType(Base):
    """营销渠道分类体系（paid/owned/earned）。"""
    __tablename__ = "channel_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    channel_name: Mapped[str] = mapped_column(String(80), nullable=False)
    channel_category: Mapped[str] = mapped_column(String(20), nullable=False)
    typical_cpm_usd: Mapped[float] = mapped_column(Float, nullable=False)
    typical_ctr_pct: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductCategory(Base):
    """层级化的商品类目（通过自引用 FK 实现 2 级）。"""
    __tablename__ = "product_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_name: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("product_category.id"), nullable=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class AudienceSegment(Base):
    """基于规则的受众 segment，用于 campaign 投放定向。"""
    __tablename__ = "audience_segment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_name: Mapped[str] = mapped_column(String(120), nullable=False)
    segment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_definition: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Campaign(Base):
    """营销 campaign 定义（acquisition / conversion / reactivation）。"""
    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    campaign_name: Mapped[str] = mapped_column(String(150), nullable=False)
    objective: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    target_segment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audience_segment.id"), nullable=False
    )
    owner_name: Mapped[str] = mapped_column(String(80), nullable=False)
    primary_kpi: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Customer(Base):
    """终端客户（DTC）。对于自然流量，acquisition channel 与 campaign 可为空。"""
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(20), nullable=False)
    state_or_province: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    signup_date: Mapped[date] = mapped_column(Date, nullable=False)
    lifecycle_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    acquisition_channel_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("channel_type.id"), nullable=True
    )
    acquisition_campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=True
    )
    email_subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sms_subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    push_subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Product(Base):
    """健康食品 SKU。"""
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_category.id"), nullable=False
    )
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    list_price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    member_price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    is_organic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_subscription_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    launch_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class CreativeAsset(Base):
    """挂在某个 campaign 下的创意素材（email body / push copy / banner）。"""
    __tablename__ = "creative_asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=False
    )
    asset_name: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    headline: Mapped[str] = mapped_column(String(200), nullable=False)
    body_copy: Mapped[str] = mapped_column(Text, nullable=False)
    cta_text: Mapped[str] = mapped_column(String(40), nullable=False)
    target_emotion: Mapped[str] = mapped_column(String(40), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False)


class CampaignChannel(Base):
    """campaign x channel 预算分配（M:N）。"""
    __tablename__ = "campaign_channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channel_type.id"), nullable=False
    )
    channel_budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    spend_to_date_usd: Mapped[float] = mapped_column(Float, nullable=False)
    target_impressions: Mapped[int] = mapped_column(Integer, nullable=False)


class CustomerSegmentMembership(Base):
    """customer x audience_segment（M:N）。"""
    __tablename__ = "customer_segment_membership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer.id"), nullable=False
    )
    segment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audience_segment.id"), nullable=False
    )
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)


class MembershipSubscription(Base):
    """每个客户的 VerdantBox+ 会员订阅（1:1）。"""
    __tablename__ = "membership_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer.id"), nullable=False
    )
    plan_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    monthly_fee_usd: Mapped[float] = mapped_column(Float, nullable=False)
    trial_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    activation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PromoCode(Base):
    """挂在某个 campaign 下的 promo code。"""
    __tablename__ = "promo_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=False
    )
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[float] = mapped_column(Float, nullable=False)
    min_order_value_usd: Mapped[float] = mapped_column(Float, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    max_redemptions: Mapped[int] = mapped_column(Integer, nullable=False)
    redemption_count: Mapped[int] = mapped_column(Integer, nullable=False)


class MarketingTouchpoint(Base):
    """单次营销发送尝试（事件级）。delivery_status 记录该次发送是
    delivered、bounced 还是 failed。"""
    __tablename__ = "marketing_touchpoint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer.id"), nullable=False
    )
    campaign_channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_channel.id"), nullable=False
    )
    creative_asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("creative_asset.id"), nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)


class TouchpointResponse(Base):
    """用户对某个 touchpoint 的响应。response_type 是该 touchpoint 的终态
    （互斥：open / click / dismiss / convert）。
    'click' 意味着用户先 open 过；'convert' 意味着先 click 过。"""
    __tablename__ = "touchpoint_response"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    touchpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("marketing_touchpoint.id"), nullable=False
    )
    response_type: Mapped[str] = mapped_column(String(20), nullable=False)
    response_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)
    landed_on_page: Mapped[str] = mapped_column(String(100), nullable=False)


class Order(Base):
    """客户订单（表头）。注意：'order' 是 SQL 保留字 —— 在裸 SQL 中
    始终要加引号（"order"）。"""
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer.id"), nullable=False
    )
    order_status: Mapped[str] = mapped_column(String(20), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    subtotal_usd: Mapped[float] = mapped_column(Float, nullable=False)
    shipping_usd: Mapped[float] = mapped_column(Float, nullable=False)
    tax_usd: Mapped[float] = mapped_column(Float, nullable=False)
    discount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    total_usd: Mapped[float] = mapped_column(Float, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_member_at_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_first_order: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attributed_campaign_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campaign.id"), nullable=True
    )


class OrderItem(Base):
    """订单上的行项目。"""
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    line_total_usd: Mapped[float] = mapped_column(Float, nullable=False)


class PromoRedemption(Base):
    """在某个订单上兑换的 promo code。"""
    __tablename__ = "promo_redemption"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_code_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("promo_code.id"), nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order.id"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer.id"), nullable=False
    )
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discount_applied_usd: Mapped[float] = mapped_column(Float, nullable=False)


# ============================================================================
# 参考数据（常量）
# ============================================================================
CHANNELS: list[tuple[str, str, str, float, float]] = [
    # 字段：(code, name, category, typical_cpm_usd, typical_ctr_pct)
    ("EMAIL", "Email Newsletter", "Owned", 0.50, 3.5),
    ("PUSH", "Mobile Push Notification", "Owned", 0.10, 2.0),
    ("SMS", "SMS / Text Message", "Owned", 5.00, 8.0),
    ("IN_APP", "In-App Message", "Owned", 0.05, 4.0),
    ("PAID_SOCIAL_META", "Paid Social - Meta (FB/IG)", "Paid", 9.50, 1.2),
    ("PAID_SOCIAL_TIKTOK", "Paid Social - TikTok", "Paid", 7.00, 1.6),
    ("GOOGLE_ADS", "Google Search Ads", "Paid", 14.00, 3.0),
    ("YOUTUBE_ADS", "YouTube Video Ads", "Paid", 12.00, 0.8),
    ("REFERRAL", "Referral Program", "Earned", 0.00, 12.0),
    ("AFFILIATE", "Affiliate Network", "Paid", 6.00, 2.5),
]

CATEGORY_TREE: list[tuple[str, str | None, str]] = [
    ("Pantry & Staples", None, "Shelf-stable everyday essentials"),
    ("Snacks & Bars", None, "Healthy snacks for on-the-go"),
    ("Beverages", None, "Functional drinks, teas, and tonics"),
    ("Breakfast", None, "Cereals, granolas, oats, mixes"),
    ("Supplements", None, "Vitamins, minerals, herbal blends"),
    ("Plant-Based Protein", None, "Vegan/vegetarian protein products"),
    ("Refrigerated & Fresh", None, "Cold-chain products"),
    ("Frozen Meals", None, "Heat-and-eat clean meals"),
    ("Organic Pasta & Grains", "Pantry & Staples", "Whole grains, quinoa, pasta"),
    ("Nut Butters & Spreads", "Pantry & Staples", "Almond, peanut, cashew butters"),
    ("Oils & Condiments", "Pantry & Staples", "EVOO, vinegars, sauces"),
    ("Protein Bars", "Snacks & Bars", "High-protein clean-label bars"),
    ("Nut & Seed Mixes", "Snacks & Bars", "Trail mixes, roasted nuts"),
    ("Crackers & Chips", "Snacks & Bars", "Gluten-free crackers, baked chips"),
    ("Kombucha", "Beverages", "Probiotic fermented teas"),
    ("Cold-Pressed Juice", "Beverages", "HPP juices and shots"),
    ("Functional Coffee & Tea", "Beverages", "Adaptogen blends, matcha, herbal"),
    ("Granola & Cereal", "Breakfast", "Low-sugar granolas and cereals"),
    ("Oatmeal & Pancake Mixes", "Breakfast", "Steel-cut oats, GF mixes"),
    ("Multivitamins", "Supplements", "Daily multivitamins"),
    ("Probiotics", "Supplements", "Gut-health capsules and powders"),
    ("Adaptogens & Mushrooms", "Supplements", "Ashwagandha, lion's mane, reishi"),
    ("Plant Protein Powder", "Plant-Based Protein", "Pea, hemp, rice protein"),
    ("Meat Alternatives", "Plant-Based Protein", "Tempeh, seitan, plant burgers"),
    ("Plant Milks", "Refrigerated & Fresh", "Oat, almond, soy milks"),
    ("Yogurts & Kefir", "Refrigerated & Fresh", "Plant and dairy yogurts"),
    ("Fresh Salads & Bowls", "Refrigerated & Fresh", "Pre-made grab-and-go bowls"),
    ("Frozen Entrées", "Frozen Meals", "Single-serve frozen meals"),
    ("Frozen Smoothie Kits", "Frozen Meals", "Pre-portioned smoothie cubes"),
    ("Frozen Plant Pizzas", "Frozen Meals", "Cauliflower-crust pizzas"),
    ("Energy Bites & Truffles", "Snacks & Bars", "No-bake energy snacks"),
    ("Sparkling Functional Water", "Beverages", "Adaptogen sparkling waters"),
    ("Protein Granola", "Breakfast", "High-protein granolas"),
    ("Collagen & Beauty Supps", "Supplements", "Skin, hair, nails support"),
    ("Sports Nutrition", "Supplements", "Pre-workout, BCAAs"),
    ("Vegan Cheese", "Refrigerated & Fresh", "Plant-based cheeses"),
    ("Frozen Breakfast", "Frozen Meals", "Breakfast burritos, waffles"),
    ("Specialty Sweeteners", "Pantry & Staples", "Monk fruit, allulose, stevia"),
    ("Flours & Baking", "Pantry & Staples", "Almond flour, coconut flour"),
    ("Hydration & Electrolytes", "Beverages", "Mineral hydration mixes"),
]

ACQUISITION_CHANNEL_DISTRIBUTION = [
    ("PAID_SOCIAL_META", 0.22),
    ("PAID_SOCIAL_TIKTOK", 0.18),
    ("GOOGLE_ADS", 0.14),
    ("REFERRAL", 0.12),
    ("AFFILIATE", 0.08),
    ("YOUTUBE_ADS", 0.05),
    ("EMAIL", 0.04),
    (None, 0.17),
]

US_STATES = [
    "CA", "NY", "TX", "FL", "WA", "MA", "IL", "PA", "GA", "CO", "OR",
    "NJ", "MN", "VA", "MI", "AZ", "OH", "NC",
]
CA_PROVINCES = ["ON", "BC", "QC", "AB"]

# 地区税率查找表（state/province → 税率）。用于 order.tax_usd。
TAX_RATES: dict[str, float] = {
    # 美国各州（近似的州级销售税）
    "CA": 0.0925, "NY": 0.08, "TX": 0.0625, "FL": 0.06, "WA": 0.0650,
    "MA": 0.0625, "IL": 0.0625, "PA": 0.06, "GA": 0.04, "CO": 0.029,
    "OR": 0.0, "NJ": 0.0663, "MN": 0.0688, "VA": 0.053, "MI": 0.06,
    "AZ": 0.056, "OH": 0.0575, "NC": 0.0475,
    # 加拿大各省（HST/GST 混合税率）
    "ON": 0.13, "BC": 0.12, "QC": 0.14975, "AB": 0.05,
}

OBJECTIVES = ["ACQUISITION", "MEMBERSHIP_CONVERSION", "REACTIVATION"]

OBJECTIVE_KPI = {
    "ACQUISITION": "First Order Conversion Rate",
    "MEMBERSHIP_CONVERSION": "Trial-to-Paid Conversion Rate",
    "REACTIVATION": "Reactivation Rate",
}

CAMPAIGN_NAME_THEMES = {
    "ACQUISITION": [
        "First Box Free Spring Drive",
        "Refer-a-Friend Boost",
        "TikTok Healthy Habits Wave",
        "Meta Plant-Based Discovery",
        "Search Intent Capture - Organic",
        "Influencer Wellness Sprint",
        "YouTube Wellness Storytellers",
        "Black Friday Acquisition Surge",
        "New Year Resolutions Push",
        "Affiliate Partnership - Wellness Bloggers",
    ],
    "MEMBERSHIP_CONVERSION": [
        "VerdantBox+ Trial Upgrade",
        "Free Trial Day 5 Nudge",
        "Member Exclusive Preview",
        "Annual Plan Upsell",
        "Win-Back Trial Cohort",
        "First-Order to Member Bridge",
        "Member-Only Drop Tease",
        "Premium Tier Cross-Sell",
        "Pay-Annually Save 20%",
        "VerdantBox+ Black Friday Tier",
    ],
    "REACTIVATION": [
        "Welcome Back 60-Day Dormant",
        "We Miss You - 90 Day Bundle",
        "Personalized Comeback Box",
        "Reactivation Token Drop",
        "Lapsed Member Re-Engagement",
        "Seasonal Comeback - Spring",
        "Seasonal Comeback - Fall",
        "Holiday Reactivation Sprint",
        "$15 Off Your Next Box",
        "180-Day Win-Back Final Call",
    ],
}

LIFECYCLE_STAGES = ["new", "active", "at_risk", "dormant", "churned"]


# ============================================================================
# 辅助工具
# ============================================================================
def weighted_choice(weighted: list[tuple]) -> object:
    """从 (value, weight) 列表中按权重挑选一个 value。"""
    values = [v for v, _ in weighted]
    weights = [w for _, w in weighted]
    return random.choices(values, weights=weights, k=1)[0]


def random_date_between(start: date, end: date) -> date:
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def random_datetime_between(start: date, end: date) -> datetime:
    d = random_date_between(start, end)
    return datetime.combine(d, time(
        random.randint(0, 23),
        random.randint(0, 59),
        random.randint(0, 59),
    ))


# ============================================================================
# 生成器
# ============================================================================
def gen_channel_type() -> pl.DataFrame:
    rows = []
    for i, (code, name, cat, cpm, ctr) in enumerate(CHANNELS, start=1):
        rows.append({
            "id": i,
            "channel_code": code,
            "channel_name": name,
            "channel_category": cat,
            "typical_cpm_usd": cpm,
            "typical_ctr_pct": ctr,
            "is_active": True,
        })
    return pl.DataFrame(rows)


def gen_product_category() -> pl.DataFrame:
    name_to_id: dict[str, int] = {}
    rows = []
    next_id = 1
    for name, parent, desc in CATEGORY_TREE:
        if parent is None:
            name_to_id[name] = next_id
            rows.append({
                "id": next_id,
                "category_name": name,
                "parent_category_id": None,
                "level": 1,
                "description": desc,
            })
            next_id += 1
    for name, parent, desc in CATEGORY_TREE:
        if parent is not None:
            name_to_id[name] = next_id
            rows.append({
                "id": next_id,
                "category_name": name,
                "parent_category_id": name_to_id[parent],
                "level": 2,
                "description": desc,
            })
            next_id += 1
    return pl.DataFrame(rows)


def gen_audience_segment(n: int = 60) -> pl.DataFrame:
    segment_templates = [
        ("High-Value Active Members", "behavioral", "lifecycle=active AND member=True AND L90D_spend>200"),
        ("Lapsed Premium Customers", "behavioral", "lifecycle=dormant AND L365D_spend>500"),
        ("First-Order 14-Day Window", "behavioral", "first_order_age_days<=14"),
        ("Trial Members Day 5+", "behavioral", "membership_status=trial AND trial_age>=5"),
        ("Frequent Snackers", "category_affinity", "L180D_category=Snacks orders>=3"),
        ("Plant-Based Loyalists", "category_affinity", "L180D_category='Plant-Based Protein' orders>=2"),
        ("Coastal Wellness Coast - West", "geo", "state IN (CA, WA, OR)"),
        ("Northeast Urban Professionals", "geo", "state IN (NY, NJ, MA) AND age 25-45"),
        ("Canadian Members", "geo", "country=CA"),
        ("Gen-Z Health Curious", "demographic", "age 18-26"),
        ("Millennial Parents", "demographic", "age 28-42 AND has_kids=True"),
        ("60-Day Dormant All", "behavioral", "lifecycle=dormant AND days_since_last_order BETWEEN 60 AND 89"),
        ("90-Day Dormant All", "behavioral", "lifecycle=dormant AND days_since_last_order BETWEEN 90 AND 179"),
        ("180+ Day Churn Risk", "behavioral", "lifecycle=churned AND days_since_last_order>=180"),
        ("Single-Order Browse-Only", "behavioral", "total_orders=1 AND visits_L30D>5"),
        ("Email Engaged Non-Members", "behavioral", "L60D_email_opens>=4 AND member=False"),
        ("Push Opted-In Customers", "channel_pref", "push_subscribed=True"),
        ("SMS Opted-In Customers", "channel_pref", "sms_subscribed=True"),
        ("High AOV Buyers", "behavioral", "avg_order_value>=80"),
        ("Low AOV Frequent Buyers", "behavioral", "avg_order_value<40 AND order_frequency>=2/month"),
        ("Supplements Enthusiasts", "category_affinity", "L180D_category=Supplements orders>=2"),
        ("Beverage Heavy Buyers", "category_affinity", "L180D_category=Beverages orders>=3"),
        ("Frozen Meals Adopters", "category_affinity", "L180D_category='Frozen Meals' orders>=1"),
        ("Subscription-Eligible Browsers", "behavioral", "cart_subscription_skus>=2 AND no_subscription"),
        ("Holiday Buyers Only", "behavioral", "orders_in_holiday_months>=2 AND orders_other_months=0"),
        ("Referrers (Brought 2+ Friends)", "advocacy", "referrals_made>=2"),
        ("Promo-Sensitive Buyers", "behavioral", "promo_redemption_rate>0.7"),
        ("Full-Price Loyalists", "behavioral", "promo_redemption_rate<0.1 AND total_orders>=3"),
        ("Annual Plan Members", "subscription", "membership_status=active AND billing_cycle=annual"),
        ("Monthly Plan Members", "subscription", "membership_status=active AND billing_cycle=monthly"),
    ]
    rows = []
    for i in range(1, n + 1):
        name, stype, rule = segment_templates[(i - 1) % len(segment_templates)]
        suffix = "" if i <= len(segment_templates) else f" v{(i - 1) // len(segment_templates) + 1}"
        created = random_date_between(
            TODAY - timedelta(days=540), TODAY - timedelta(days=30)
        )
        rows.append({
            "id": i,
            "segment_name": name + suffix,
            "segment_type": stype,
            "rule_definition": rule,
            "estimated_size": random.randint(800, 25000),
            "created_date": created,
            "is_active": random.random() > 0.1,
        })
    return pl.DataFrame(rows)


def gen_campaign(n: int = 50, segment_ids: list[int] | None = None) -> pl.DataFrame:
    assert segment_ids is not None
    objective_plan = (
        ["ACQUISITION"] * 18 +
        ["MEMBERSHIP_CONVERSION"] * 17 +
        ["REACTIVATION"] * 15
    )
    random.shuffle(objective_plan)

    rows = []
    for i in range(1, n + 1):
        objective = objective_plan[i - 1]
        roll = random.random()
        if roll < 0.70:
            status = "COMPLETED"
            end_d = random_date_between(
                TODAY - timedelta(days=540), TODAY - timedelta(days=15)
            )
            duration = random.randint(14, 60)
            start_d = end_d - timedelta(days=duration)
        elif roll < 0.90:
            status = "ACTIVE"
            start_d = random_date_between(
                TODAY - timedelta(days=30), TODAY - timedelta(days=3)
            )
            end_d = start_d + timedelta(days=random.randint(21, 60))
        else:
            status = "PLANNED"
            start_d = random_date_between(
                TODAY + timedelta(days=3), TODAY + timedelta(days=30)
            )
            end_d = start_d + timedelta(days=random.randint(21, 60))

        theme = random.choice(CAMPAIGN_NAME_THEMES[objective])
        base_code = f"{objective[:3]}-{start_d.strftime('%Y%m')}-{i:03d}"

        # 给样本数据集设定一个贴近现实的每 campaign 预算，使其能与实际花费
        # 大致对得上（即约 1000 个 touchpoint 的样本窗口内的
        # Σ touchpoint.cost_usd）
        budget = round(random.uniform(300, 3000), 2)
        rows.append({
            "id": i,
            "campaign_code": base_code,
            "campaign_name": f"{theme} ({start_d.strftime('%b %Y')})",
            "objective": objective,
            "status": status,
            "start_date": start_d,
            "end_date": end_d,
            "total_budget_usd": budget,
            "target_segment_id": random.choice(segment_ids),
            "owner_name": fake.name(),
            "primary_kpi": OBJECTIVE_KPI[objective],
            "created_at": datetime.combine(
                start_d - timedelta(days=random.randint(7, 30)),
                time(random.randint(8, 18), random.randint(0, 59)),
            ),
        })
    return pl.DataFrame(rows)


def gen_customer(
    n: int,
    channel_id_by_code: dict[str, int],
    campaigns_df: pl.DataFrame,
) -> pl.DataFrame:
    rows = []
    acq_campaigns = campaigns_df.filter(
        pl.col("objective") == "ACQUISITION"
    ).select(["id", "start_date", "end_date"]).to_dicts()

    for i in range(1, n + 1):
        signup_d = random_date_between(
            TODAY - timedelta(days=540), TODAY - timedelta(days=1)
        )
        days_since_signup = (TODAY - signup_d).days

        if days_since_signup <= 30:
            lifecycle = "new"
        else:
            lifecycle = weighted_choice([
                ("active", 0.42),
                ("at_risk", 0.18),
                ("dormant", 0.22),
                ("churned", 0.18),
            ])

        ch_code = weighted_choice(ACQUISITION_CHANNEL_DISTRIBUTION)
        acq_channel_id = channel_id_by_code.get(ch_code) if ch_code else None

        acq_campaign_id = None
        if ch_code and random.random() < 0.55:
            eligible = [
                c for c in acq_campaigns
                if c["start_date"] <= signup_d <= c["end_date"]
            ]
            if eligible:
                acq_campaign_id = random.choice(eligible)["id"]

        if random.random() < 0.88:
            country = "USA"
            state = random.choice(US_STATES)
            city = fake.city()
            postal = fake.zipcode()
        else:
            country = "Canada"
            state = random.choice(CA_PROVINCES)
            city = random.choice([
                "Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa",
                "Edmonton", "Burnaby", "Mississauga",
            ])
            postal = f"{random.choice('MKLVH')}{random.randint(1,9)}{random.choice('ABCEGH')} {random.randint(1,9)}{random.choice('ABCEGH')}{random.randint(1,9)}"

        first = fake.first_name()
        last = fake.last_name()
        email = f"{first.lower()}.{last.lower()}{i}@{fake.free_email_domain()}"

        rows.append({
            "id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": fake.numerify("###-###-####"),
            "birth_date": fake.date_of_birth(minimum_age=18, maximum_age=72),
            "gender": random.choice(["F", "M", "NB", "U"]),
            "country": country,
            "state_or_province": state,
            "city": city,
            "postal_code": postal,
            "signup_date": signup_d,
            "lifecycle_stage": lifecycle,
            "acquisition_channel_id": acq_channel_id,
            "acquisition_campaign_id": acq_campaign_id,
            "email_subscribed": random.random() < 0.82,
            "sms_subscribed": random.random() < 0.41,
            "push_subscribed": random.random() < 0.55,
        })
    return pl.DataFrame(rows)


def gen_product(n: int, category_ids: list[int]) -> pl.DataFrame:
    brand_pool = [
        "VerdantHouse", "PurelyNorth", "Wildgrove", "SproutLane", "TerraBloom",
        "RootCellar", "GreenCanyon", "Sunhaven Organics", "Northwoods Pantry",
        "Solbright", "Honeycrest", "Maple & Moss", "Cedarpeak", "WhitePine Foods",
        "Verdant Roots", "Glacier Spring", "True North Wellness",
    ]
    adjectives = [
        "Organic", "Sprouted", "Cold-Pressed", "Stone-Ground", "Single-Origin",
        "Whole-Grain", "Fermented", "Raw", "Heirloom", "Grass-Fed", "Wildcrafted",
    ]
    nouns_by_cat = {
        "Snacks": ["Bites", "Crunch", "Bars", "Clusters", "Mix"],
        "Beverages": ["Brew", "Tonic", "Sparkler", "Infusion", "Latte Mix"],
        "Pantry": ["Pasta", "Quinoa", "Granola", "Spread", "Sauce"],
        "Supplements": ["Capsules", "Powder", "Blend", "Drops", "Gummies"],
        "Frozen": ["Bowl", "Pizza", "Burrito", "Smoothie Kit", "Entrée"],
        "Plant": ["Protein Powder", "Burger", "Tempeh", "Patties", "Crumbles"],
        "Refrigerated": ["Yogurt", "Kefir", "Milk", "Cheese Wheel", "Salad Kit"],
        "Breakfast": ["Oatmeal", "Granola", "Pancake Mix", "Muesli", "Porridge"],
    }
    rows = []
    for i in range(1, n + 1):
        cat_id = random.choice(category_ids)
        noun_key = random.choice(list(nouns_by_cat.keys()))
        adj = random.choice(adjectives)
        noun = random.choice(nouns_by_cat[noun_key])
        flavor = random.choice([
            "Vanilla Bean", "Cacao", "Wild Berry", "Lemon Ginger", "Turmeric",
            "Matcha", "Maple Pecan", "Sea Salt", "Pumpkin Spice", "Apple Cinnamon",
            "Chai", "Spirulina", "Cold Brew", "Sourdough Style", "Mediterranean",
            "Sriracha", "Garlic Herb", "Original",
        ])
        name = f"{adj} {flavor} {noun}"

        list_price = round(random.uniform(4.99, 49.99), 2)
        member_price = round(list_price * random.uniform(0.78, 0.90), 2)
        cost = round(list_price * random.uniform(0.35, 0.55), 2)
        launch = random_date_between(
            TODAY - timedelta(days=900), TODAY - timedelta(days=30)
        )

        rows.append({
            "id": i,
            "sku": f"VB-{i:05d}",
            "product_name": name,
            "category_id": cat_id,
            "brand": random.choice(brand_pool),
            "list_price_usd": list_price,
            "member_price_usd": member_price,
            "cost_usd": cost,
            "is_organic": random.random() < 0.78,
            "is_subscription_eligible": random.random() < 0.65,
            "launch_date": launch,
            "is_active": random.random() < 0.94,
        })
    return pl.DataFrame(rows)


def gen_creative_asset(n: int, campaign_ids: list[int]) -> pl.DataFrame:
    """每个含 ≥2 个素材的 campaign x asset_type 分组得到唯一一个 winner。"""
    asset_types = ["email_html", "push_copy", "sms_copy", "banner_image", "video_15s", "video_30s", "landing_page"]
    emotions = ["aspirational", "relatable", "educational", "urgent", "trust-building", "playful"]
    cta_options = [
        "Shop Now", "Get Started", "Claim My Box", "Try Free", "See What's Inside",
        "Continue My Trial", "Reactivate Now", "Save 20%", "Learn More", "Refer a Friend",
    ]
    headlines = [
        "Real food. Real fuel. Real fast.",
        "Your plant-based pantry, delivered.",
        "Stock your shelves, save your weeknights.",
        "We picked. You unbox. You thrive.",
        "Welcome back — your favorites are waiting.",
        "Try VerdantBox+ free for 30 days.",
        "Your gut will thank you.",
        "Healthy snacking just got easier.",
        "Curated by nutritionists. Loved by families.",
        "One box. Endless wellness wins.",
    ]
    rows = []
    for i in range(1, n + 1):
        cid = random.choice(campaign_ids)
        rows.append({
            "id": i,
            "campaign_id": cid,
            "asset_name": f"Creative {i:04d}",
            "asset_type": random.choice(asset_types),
            "headline": random.choice(headlines),
            "body_copy": fake.paragraph(nb_sentences=3),
            "cta_text": random.choice(cta_options),
            "target_emotion": random.choice(emotions),
            "created_date": random_date_between(
                TODAY - timedelta(days=540), TODAY
            ),
            "is_winner": False,
        })

    # Winner reconciliation：对每个含 ≥2 个素材的 (campaign_id, asset_type)
    # 分组，恰好选出一个 winner。只含 1 个素材的分组没有 A/B test，
    # 保持 is_winner=False。
    by_group: dict[tuple[int, str], list[dict]] = {}
    for r in rows:
        key = (r["campaign_id"], r["asset_type"])
        by_group.setdefault(key, []).append(r)
    for key, asset_list in by_group.items():
        if len(asset_list) >= 2:
            winner = random.choice(asset_list)
            winner["is_winner"] = True

    return pl.DataFrame(rows)


def gen_campaign_channel(
    campaigns_df: pl.DataFrame,
    channel_ids: list[int],
) -> pl.DataFrame:
    """每个 campaign 分到 2-5 个 channel，预算拆分之和等于
    total_budget_usd。spend_to_date_usd 初始为 0，之后通过
    SUM(marketing_touchpoint.cost_usd) 进行 reconcile。"""
    rows = []
    next_id = 1
    for c in campaigns_df.to_dicts():
        n_channels = random.randint(2, 5)
        chosen = random.sample(channel_ids, k=min(n_channels, len(channel_ids)))
        # 分配总和为 1.0 的预算份额
        shares = [random.uniform(0.1, 1.0) for _ in chosen]
        total_share = sum(shares)
        shares = [s / total_share for s in shares]
        for ch_id, share in zip(chosen, shares):
            ch_budget = round(c["total_budget_usd"] * share, 2)
            target_imp = int(ch_budget * 1000 / random.uniform(5, 15))
            rows.append({
                "id": next_id,
                "campaign_id": c["id"],
                "channel_id": ch_id,
                "channel_budget_usd": ch_budget,
                "spend_to_date_usd": 0.0,  # placeholder；后续 reconcile
                "target_impressions": target_imp,
            })
            next_id += 1
    return pl.DataFrame(rows)


def gen_customer_segment_membership(
    n: int,
    customer_ids: list[int],
    segment_ids: list[int],
) -> pl.DataFrame:
    rows = []
    pairs = set()
    next_id = 1
    while next_id <= n:
        cust = random.choice(customer_ids)
        seg = random.choice(segment_ids)
        if (cust, seg) in pairs:
            continue
        pairs.add((cust, seg))
        rows.append({
            "id": next_id,
            "customer_id": cust,
            "segment_id": seg,
            "assigned_date": random_date_between(
                TODAY - timedelta(days=365), TODAY
            ),
            "score": round(random.uniform(0.30, 0.99), 3),
        })
        next_id += 1
    return pl.DataFrame(rows)


def gen_membership_subscription(n: int, customer_ids: list[int]) -> pl.DataFrame:
    """1:1 —— 每个客户至多一条订阅记录。"""
    chosen = random.sample(customer_ids, k=min(n, len(customer_ids)))
    rows = []
    for i, cid in enumerate(chosen, start=1):
        billing = weighted_choice([("monthly", 0.60), ("annual", 0.40)])
        tier = weighted_choice([("Plus", 0.78), ("Plus Premium", 0.22)])
        if billing == "monthly":
            fee = 14.99 if tier == "Plus" else 24.99
        else:
            fee = 9.99 if tier == "Plus" else 17.99

        trial_start = random_date_between(
            TODAY - timedelta(days=540), TODAY - timedelta(days=1)
        )
        trial_age = (TODAY - trial_start).days

        if trial_age < 30:
            status = "trial"
            activation = None
            cancellation = None
        else:
            convert = random.random() < 0.62
            if convert:
                activation = trial_start + timedelta(days=random.randint(28, 31))
                if random.random() < 0.28:
                    cancellation = activation + timedelta(days=random.randint(30, 360))
                    if cancellation <= TODAY:
                        status = "cancelled"
                    else:
                        cancellation = None
                        status = "active"
                else:
                    cancellation = None
                    status = "active"
            else:
                activation = None
                cancellation = trial_start + timedelta(days=random.randint(15, 30))
                status = "trial_ended"

        rows.append({
            "id": i,
            "customer_id": cid,
            "plan_tier": tier,
            "billing_cycle": billing,
            "monthly_fee_usd": fee,
            "trial_start_date": trial_start,
            "activation_date": activation,
            "cancellation_date": cancellation,
            "status": status,
            "auto_renew": status == "active",
        })
    return pl.DataFrame(rows)


def gen_promo_code(n: int, campaigns_df: pl.DataFrame) -> pl.DataFrame:
    """redemption_count 初始为 0，之后通过
    COUNT(promo_redemption) 进行 reconcile。"""
    campaign_records = campaigns_df.select(
        ["id", "start_date", "end_date", "objective"]
    ).to_dicts()
    rows = []
    used = set()
    for i in range(1, n + 1):
        c = random.choice(campaign_records)
        prefix = {
            "ACQUISITION": "WELCOME",
            "MEMBERSHIP_CONVERSION": "MEMBER",
            "REACTIVATION": "COMEBACK",
        }[c["objective"]]
        code = f"{prefix}{random.randint(100, 999)}{random.choice('ABCDEFGHJKMN')}{i}"
        if code in used:
            code += "X"
        used.add(code)

        discount_type = weighted_choice([("PERCENT", 0.55), ("FIXED", 0.35), ("FREE_SHIPPING", 0.10)])
        if discount_type == "PERCENT":
            discount_value = random.choice([10, 15, 20, 25, 30])
        elif discount_type == "FIXED":
            discount_value = random.choice([5, 10, 15, 20, 25])
        else:
            discount_value = 0

        max_red = random.choice([200, 500, 1000, 2500, 5000])
        rows.append({
            "id": i,
            "code": code,
            "campaign_id": c["id"],
            "discount_type": discount_type,
            "discount_value": float(discount_value),
            "min_order_value_usd": float(random.choice([0, 25, 35, 50, 75])),
            "valid_from": c["start_date"],
            "valid_to": c["end_date"],
            "max_redemptions": max_red,
            "redemption_count": 0,  # placeholder；后续 reconcile
        })
    return pl.DataFrame(rows)


def gen_marketing_touchpoint(
    n: int,
    customers_df: pl.DataFrame,
    campaign_channel_df: pl.DataFrame,
    creative_df: pl.DataFrame,
    campaigns_df: pl.DataFrame,
    channels_df: pl.DataFrame,
) -> pl.DataFrame:
    """每个 touchpoint 的成本依照 channel 的 CPM 经济学校准
    （cost = CPM × U(0.3, 1.0)）。每个 touchpoint 代表一次 batch-send
    事件；每个 campaign_channel 的总花费 = SUM(cost_usd)，之后会写入
    campaign_channel.spend_to_date_usd。"""
    campaign_by_id = {c["id"]: c for c in campaigns_df.to_dicts()}
    channel_by_id = {ch["id"]: ch for ch in channels_df.to_dicts()}
    cc_records = campaign_channel_df.to_dicts()
    valid_cc = [
        cc for cc in cc_records
        if campaign_by_id[cc["campaign_id"]]["status"] in ("COMPLETED", "ACTIVE")
    ]
    if not valid_cc:
        valid_cc = cc_records

    creative_by_campaign: dict[int, list[int]] = {}
    for cr in creative_df.to_dicts():
        creative_by_campaign.setdefault(cr["campaign_id"], []).append(cr["id"])

    customer_ids = customers_df["id"].to_list()
    customer_signup = dict(zip(
        customers_df["id"].to_list(),
        customers_df["signup_date"].to_list(),
    ))

    rows = []
    next_id = 1
    attempts = 0
    max_attempts = n * 10  # 安全上限，避免退化数据集导致死循环
    while next_id <= n and attempts < max_attempts:
        attempts += 1
        cc = random.choice(valid_cc)
        campaign = campaign_by_id[cc["campaign_id"]]
        channel = channel_by_id[cc["channel_id"]]

        candidate_creatives = creative_by_campaign.get(campaign["id"])
        if not candidate_creatives:
            candidate_creatives = creative_df["id"].to_list()
        creative_id = random.choice(candidate_creatives)

        cust_id = random.choice(customer_ids)
        sent_lower = max(campaign["start_date"], customer_signup[cust_id])
        sent_upper = min(campaign["end_date"], TODAY)
        if sent_lower > sent_upper:
            eligible_customers = [
                c for c in customer_ids
                if customer_signup[c] <= campaign["end_date"]
            ]
            if not eligible_customers:
                continue
            cust_id = random.choice(eligible_customers)
            sent_lower = max(campaign["start_date"], customer_signup[cust_id])
            sent_upper = min(campaign["end_date"], TODAY)
            if sent_lower > sent_upper:
                continue

        sent_at = random_datetime_between(sent_lower, sent_upper)
        delivery_status = weighted_choice([
            ("delivered", 0.94),
            ("bounced", 0.03),
            ("failed", 0.03),
        ])
        # CPM × U(2.0, 5.0)。每个 touchpoint = 一次 batch-send 事件，其
        # 成本随每批触达量缩放。经过校准，使得在该样本规模下，每个 campaign
        # 的 SUM(touchpoint cost) 相对 attributed revenue 落在一个真实的
        # ROAS 区间内。
        cost = round(channel["typical_cpm_usd"] * random.uniform(2.0, 5.0), 4)

        rows.append({
            "id": next_id,
            "customer_id": cust_id,
            "campaign_channel_id": cc["id"],
            "creative_asset_id": creative_id,
            "sent_at": sent_at,
            "delivery_status": delivery_status,
            "cost_usd": cost,
        })
        next_id += 1
    return pl.DataFrame(rows)


def gen_touchpoint_response(n: int, touchpoints_df: pl.DataFrame) -> pl.DataFrame:
    """只有 delivered 的 touchpoint 才能产生响应。response_type 是终态
    —— open / click / dismiss / convert，互斥。"""
    delivered = touchpoints_df.filter(
        pl.col("delivery_status") == "delivered"
    ).select(["id", "sent_at"]).to_dicts()
    if not delivered:
        return pl.DataFrame(schema={
            "id": pl.Int64, "touchpoint_id": pl.Int64, "response_type": pl.String,
            "response_at": pl.Datetime, "device_type": pl.String, "landed_on_page": pl.String,
        })

    response_types_weighted = [
        ("open", 0.50),
        ("click", 0.30),
        ("dismiss", 0.12),
        ("convert", 0.08),
    ]
    devices = ["iOS", "Android", "Desktop", "Tablet"]
    pages = [
        "/home", "/shop/snacks", "/shop/beverages", "/membership", "/account/orders",
        "/cart", "/promo/welcome", "/category/supplements", "/category/breakfast",
        "/landing/spring", "/landing/comeback",
    ]
    n_responses = min(n, int(len(delivered) * 0.85))
    sampled = random.sample(delivered, k=n_responses)
    rows = []
    for i, tp in enumerate(sampled, start=1):
        rtype = weighted_choice(response_types_weighted)
        sent_dt: datetime = tp["sent_at"]
        delta_minutes = random.randint(1, 60 * 72)
        response_at = sent_dt + timedelta(minutes=delta_minutes)
        rows.append({
            "id": i,
            "touchpoint_id": tp["id"],
            "response_type": rtype,
            "response_at": response_at,
            "device_type": random.choice(devices),
            "landed_on_page": random.choice(pages) if rtype in ("click", "convert") else "n/a",
        })
    return pl.DataFrame(rows)


def gen_order(
    n: int,
    customers_df: pl.DataFrame,
    memberships_df: pl.DataFrame,
) -> pl.DataFrame:
    """生成订单骨架。财务字段和 is_first_order 都是 placeholder —— 之后
    会通过 order_item 以及每个客户的排序进行 reconcile。
    attributed_campaign_id 同样是 placeholder —— 通过真实的 touchpoint
    last-touch 进行 reconcile。"""
    memb_active_window: dict[int, tuple[date, date]] = {}
    for m in memberships_df.to_dicts():
        start = m["activation_date"] or m["trial_start_date"]
        end = m["cancellation_date"] or TODAY
        memb_active_window[m["customer_id"]] = (start, end)

    customer_records = customers_df.to_dicts()
    cust_signup = {c["id"]: c["signup_date"] for c in customer_records}

    lifecycle_to_orders = {
        "new": (1, 2),
        "active": (2, 5),  # 设上限，使订单总数控制在约 1000 以内
        "at_risk": (1, 3),
        "dormant": (1, 2),
        "churned": (1, 2),
    }

    plan: list[int] = []
    for c in customer_records:
        lo, hi = lifecycle_to_orders[c["lifecycle_stage"]]
        cnt = random.randint(lo, hi)
        for _ in range(cnt):
            plan.append(c["id"])

    random.shuffle(plan)
    plan = plan[:n]

    rows = []
    for i, cust_id in enumerate(plan, start=1):
        signup = cust_signup[cust_id]
        order_date_d = random_date_between(signup, TODAY)
        order_dt = datetime.combine(
            order_date_d,
            time(random.randint(7, 23), random.randint(0, 59)),
        )

        is_member = False
        if cust_id in memb_active_window:
            start, end = memb_active_window[cust_id]
            if start <= order_date_d <= end:
                is_member = True

        days_old = (TODAY - order_date_d).days
        if days_old >= 7:
            status = weighted_choice([
                ("delivered", 0.93),
                ("returned", 0.05),
                ("cancelled", 0.02),
            ])
        elif days_old >= 2:
            status = weighted_choice([
                ("delivered", 0.55),
                ("shipped", 0.35),
                ("processing", 0.07),
                ("cancelled", 0.03),
            ])
        else:
            status = weighted_choice([
                ("processing", 0.45),
                ("shipped", 0.40),
                ("delivered", 0.10),
                ("cancelled", 0.05),
            ])

        # item_count 的提示值 —— 会员每单买更大的购物篮，这正是在会员折扣
        # 单价之下仍能形成 “Member AOV > Non-Member AOV” 的底层机制
        if is_member:
            target_item_count = random.randint(3, 6)
        else:
            target_item_count = random.randint(1, 3)

        rows.append({
            "id": i,
            "order_number": f"VB-{order_date_d.strftime('%Y%m%d')}-{i:06d}",
            "customer_id": cust_id,
            "order_status": status,
            "order_date": order_dt,
            "subtotal_usd": 0.0,         # placeholder；后续 reconcile
            "shipping_usd": 0.0,         # placeholder；后续 reconcile
            "tax_usd": 0.0,              # placeholder；后续 reconcile
            "discount_usd": 0.0,         # placeholder；后续 reconcile
            "total_usd": 0.0,            # placeholder；后续 reconcile
            "item_count": target_item_count,  # target —— 会被 reconcile 覆盖
            "is_member_at_purchase": is_member,
            "is_first_order": False,     # placeholder；后续 reconcile
            "attributed_campaign_id": None,  # placeholder；后续 reconcile
        })
    return pl.DataFrame(rows)


def gen_order_item(orders_df: pl.DataFrame, products_df: pl.DataFrame) -> pl.DataFrame:
    """为每个订单生成 `target_item_count` 个不同的商品。每个行项目按
    member_price_usd 或 list_price_usd 计价，取决于该订单的会员状态。
    line_total_usd = unit_price × quantity。"""
    products = products_df.to_dicts()
    rows = []
    next_id = 1
    for o in orders_df.to_dicts():
        target = max(1, int(o["item_count"]))
        target = min(target, len(products))
        chosen = random.sample(products, k=target)
        for p in chosen:
            qty = random.randint(1, 3)
            price = p["member_price_usd"] if o["is_member_at_purchase"] else p["list_price_usd"]
            rows.append({
                "id": next_id,
                "order_id": o["id"],
                "product_id": p["id"],
                "quantity": qty,
                "unit_price_usd": round(price, 2),
                "line_total_usd": round(price * qty, 2),
            })
            next_id += 1
    return pl.DataFrame(rows)


def gen_promo_redemption(
    n: int,
    promo_df: pl.DataFrame,
    orders_df: pl.DataFrame,
) -> pl.DataFrame:
    """在订单 discount reconciliation 之后创建：仅限那些 discount_usd > 0、
    其 attributed_campaign_id 有对应 promo code、且 order_date 落在 promo
    有效期窗口内的订单。"""
    promos = promo_df.to_dicts()
    promo_by_campaign: dict[int, list[dict]] = {}
    for p in promos:
        promo_by_campaign.setdefault(p["campaign_id"], []).append(p)

    discounted_orders = [
        o for o in orders_df.to_dicts()
        if o["discount_usd"] > 0 and o["attributed_campaign_id"] in promo_by_campaign
    ]
    random.shuffle(discounted_orders)
    rows = []
    for o in discounted_orders[:n]:
        promo = random.choice(promo_by_campaign[o["attributed_campaign_id"]])
        order_d = o["order_date"].date() if isinstance(o["order_date"], datetime) else o["order_date"]
        if not (promo["valid_from"] <= order_d <= promo["valid_to"]):
            continue
        rows.append({
            "id": len(rows) + 1,
            "promo_code_id": promo["id"],
            "order_id": o["id"],
            "customer_id": o["customer_id"],
            "redeemed_at": o["order_date"],
            "discount_applied_usd": o["discount_usd"],
        })
    return pl.DataFrame(rows)


# ============================================================================
# Reconcile pass（对账校准阶段）
# ============================================================================
def reconcile_order_financials(
    df_order: pl.DataFrame,
    df_item: pl.DataFrame,
    df_customer: pl.DataFrame,
) -> pl.DataFrame:
    """根据真实的 order_item 行项目计算 subtotal/tax/shipping/discount/
    total/item_count，将所有财务字段都锚定到行项目合计上。"""
    item_agg = (
        df_item.group_by("order_id")
        .agg(
            pl.col("line_total_usd").sum().alias("subtotal"),
            pl.len().alias("item_count"),
        )
    )
    agg_lookup = {r["order_id"]: r for r in item_agg.to_dicts()}
    cust_state = dict(zip(
        df_customer["id"].to_list(),
        df_customer["state_or_province"].to_list(),
    ))

    rows = []
    for o in df_order.to_dicts():
        agg = agg_lookup.get(o["id"])
        subtotal = round(float(agg["subtotal"]), 2) if agg else 0.0
        item_count = int(agg["item_count"]) if agg else 0

        shipping = (
            0.0 if o["is_member_at_purchase"]
            else round(random.choice([0.0, 5.99, 7.99, 9.99]), 2)
        )
        state = cust_state.get(o["customer_id"], "")
        tax_rate = TAX_RATES.get(state, 0.08)
        tax = round(subtotal * tax_rate, 2)
        discount = (
            round(subtotal * random.uniform(0.05, 0.20), 2)
            if random.random() < 0.42 else 0.0
        )
        total = round(subtotal + shipping + tax - discount, 2)

        o["subtotal_usd"] = subtotal
        o["shipping_usd"] = shipping
        o["tax_usd"] = tax
        o["discount_usd"] = discount
        o["total_usd"] = total
        o["item_count"] = item_count
        rows.append(o)
    return pl.DataFrame(rows)


def reconcile_first_order(df_order: pl.DataFrame) -> pl.DataFrame:
    """对每个客户，将 MIN(order_date) 的那笔订单标记为 is_first_order=True。"""
    rows = df_order.to_dicts()
    by_customer: dict[int, list[dict]] = {}
    for r in rows:
        by_customer.setdefault(r["customer_id"], []).append(r)
    for cust_id, order_list in by_customer.items():
        order_list.sort(key=lambda x: x["order_date"])
        for idx, r in enumerate(order_list):
            r["is_first_order"] = (idx == 0)
    rows.sort(key=lambda x: x["id"])
    return pl.DataFrame(rows)


def reconcile_attribution(
    df_order: pl.DataFrame,
    df_tp: pl.DataFrame,
    df_resp: pl.DataFrame,
    df_cc: pl.DataFrame,
    df_campaign: pl.DataFrame,
) -> pl.DataFrame:
    """真实的 last-touch attribution：对每个订单，查找该客户在订单前 60 天内
    最近一次 click/convert 的 touchpoint_response。当该客户不存在符合条件的
    touchpoint 时，回退为按日期窗口的随机分配。"""
    cc_to_campaign = dict(zip(
        df_cc["id"].to_list(),
        df_cc["campaign_id"].to_list(),
    ))
    tp_records = df_tp.select(
        ["id", "customer_id", "campaign_channel_id"]
    ).to_dicts()
    tp_to_customer_campaign: dict[int, tuple[int, int | None]] = {}
    for tp in tp_records:
        cid = cc_to_campaign.get(tp["campaign_channel_id"])
        tp_to_customer_campaign[tp["id"]] = (tp["customer_id"], cid)

    # 每个客户的 (response_at, campaign_id) 列表，仅保留 click/convert
    customer_clicks: dict[int, list[tuple[datetime, int]]] = {}
    for r in df_resp.filter(
        pl.col("response_type").is_in(["click", "convert"])
    ).select(["touchpoint_id", "response_at"]).to_dicts():
        cust_id, campaign_id = tp_to_customer_campaign.get(
            r["touchpoint_id"], (None, None)
        )
        if cust_id is None or campaign_id is None:
            continue
        customer_clicks.setdefault(cust_id, []).append(
            (r["response_at"], campaign_id)
        )
    # 将每个客户的点击按 response_at 降序排序
    for cust_id in customer_clicks:
        customer_clicks[cust_id].sort(key=lambda x: x[0], reverse=True)

    # 回退候选池：时间窗口包含订单日期的 campaign
    attr_campaigns = df_campaign.filter(
        pl.col("status").is_in(["COMPLETED", "ACTIVE"])
    ).select(["id", "start_date", "end_date", "objective"]).to_dicts()

    real_count = 0
    fallback_count = 0
    rows = []
    for o in df_order.to_dicts():
        order_dt: datetime = o["order_date"]
        cust_id = o["customer_id"]
        attributed_id = None

        # 先尝试订单前 60 天内的真实 last-touch
        for resp_at, campaign_id in customer_clicks.get(cust_id, []):
            if resp_at <= order_dt and (order_dt - resp_at).days <= 60:
                attributed_id = campaign_id
                real_count += 1
                break

        # 回退到按日期窗口的随机分配（剩余订单的约 70%）
        if attributed_id is None and random.random() < 0.70:
            order_d = order_dt.date() if isinstance(order_dt, datetime) else order_dt
            eligible = [
                c for c in attr_campaigns
                if c["start_date"] <= order_d <= c["end_date"]
            ]
            if eligible:
                if o["is_first_order"]:
                    pref = [c for c in eligible if c["objective"] == "ACQUISITION"]
                    if pref:
                        eligible = pref
                else:
                    pref = [c for c in eligible if c["objective"] != "ACQUISITION"]
                    if pref:
                        eligible = pref
                attributed_id = random.choice(eligible)["id"]
                fallback_count += 1

        o["attributed_campaign_id"] = attributed_id
        rows.append(o)

    print(f"  attribution: {real_count} real last-touch, {fallback_count} date-window fallback")
    return pl.DataFrame(rows)


def reconcile_cc_spend(df_cc: pl.DataFrame, df_tp: pl.DataFrame) -> pl.DataFrame:
    """spend_to_date_usd = 每个 campaign_channel 的
    SUM(marketing_touchpoint.cost_usd)。"""
    spend_per_cc = (
        df_tp.group_by("campaign_channel_id")
        .agg(pl.col("cost_usd").sum().alias("_spend"))
    )
    spend_lookup = dict(zip(
        spend_per_cc["campaign_channel_id"].to_list(),
        spend_per_cc["_spend"].to_list(),
    ))
    rows = df_cc.to_dicts()
    for r in rows:
        r["spend_to_date_usd"] = round(float(spend_lookup.get(r["id"], 0.0)), 2)
    return pl.DataFrame(rows)


def reconcile_promo_redemption_count(
    df_promo: pl.DataFrame,
    df_red: pl.DataFrame,
) -> pl.DataFrame:
    """redemption_count = 每个 promo_code 的 COUNT(promo_redemption)。"""
    if df_red.is_empty():
        rows = df_promo.to_dicts()
        for r in rows:
            r["redemption_count"] = 0
        return pl.DataFrame(rows)

    counts = df_red.group_by("promo_code_id").agg(pl.len().alias("_count"))
    count_lookup = dict(zip(
        counts["promo_code_id"].to_list(),
        counts["_count"].to_list(),
    ))
    rows = df_promo.to_dicts()
    for r in rows:
        r["redemption_count"] = int(count_lookup.get(r["id"], 0))
    return pl.DataFrame(rows)


# ============================================================================
# 核心编排（幂等 Idempotent）
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有 TSV 文件。幂等：先删除已有文件。
    顺序：
      Phase 1 —— 独立表 + 核心实体
      Phase 2 —— 营销层（touchpoints/responses）
      Phase 3 —— order + items（骨架）
      Phase 4 —— reconcile 财务、first_order、attribution
      Phase 5 —— promo_redemption（依赖已 reconcile 的 discount）
      Phase 6 —— 反向 reconcile cc.spend 和 promo.redemption_count
      Phase 7 —— 按拓扑顺序写出所有 TSV
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Phase 1: independent + core entities ...")
    df_channel = gen_channel_type()
    df_category = gen_product_category()
    df_segment = gen_audience_segment(n=60)
    df_campaign = gen_campaign(n=50, segment_ids=df_segment["id"].to_list())
    channel_id_by_code = dict(zip(
        df_channel["channel_code"].to_list(),
        df_channel["id"].to_list(),
    ))
    df_customer = gen_customer(
        n=1000,
        channel_id_by_code=channel_id_by_code,
        campaigns_df=df_campaign,
    )
    df_product = gen_product(n=500, category_ids=df_category["id"].to_list())

    print("Phase 2: marketing layer ...")
    df_creative = gen_creative_asset(
        n=200, campaign_ids=df_campaign["id"].to_list()
    )
    df_cc = gen_campaign_channel(
        campaigns_df=df_campaign,
        channel_ids=df_channel["id"].to_list(),
    )
    df_csm = gen_customer_segment_membership(
        n=1000,
        customer_ids=df_customer["id"].to_list(),
        segment_ids=df_segment["id"].to_list(),
    )
    df_memb = gen_membership_subscription(
        n=500, customer_ids=df_customer["id"].to_list()
    )
    df_promo = gen_promo_code(n=80, campaigns_df=df_campaign)
    df_tp = gen_marketing_touchpoint(
        n=1000,
        customers_df=df_customer,
        campaign_channel_df=df_cc,
        creative_df=df_creative,
        campaigns_df=df_campaign,
        channels_df=df_channel,
    )
    df_resp = gen_touchpoint_response(n=800, touchpoints_df=df_tp)

    print("Phase 3: order + items (skeletons) ...")
    df_order = gen_order(
        n=1000, customers_df=df_customer, memberships_df=df_memb
    )
    df_item = gen_order_item(orders_df=df_order, products_df=df_product)

    print("Phase 4: reconciling order financials / first_order / attribution ...")
    df_order = reconcile_order_financials(df_order, df_item, df_customer)
    df_order = reconcile_first_order(df_order)
    df_order = reconcile_attribution(
        df_order, df_tp, df_resp, df_cc, df_campaign
    )

    print("Phase 5: promo_redemption (uses reconciled discounts) ...")
    df_red = gen_promo_redemption(n=500, promo_df=df_promo, orders_df=df_order)

    print("Phase 6: back-reconcile cc.spend and promo.redemption_count ...")
    df_cc = reconcile_cc_spend(df_cc, df_tp)
    df_promo = reconcile_promo_redemption_count(df_promo, df_red)

    print("Phase 7: writing TSVs ...")
    df_channel.write_csv(DATA_DIR / "01_channel_type.tsv", separator="\t")
    df_category.write_csv(DATA_DIR / "02_product_category.tsv", separator="\t")
    df_segment.write_csv(DATA_DIR / "03_audience_segment.tsv", separator="\t")
    df_campaign.write_csv(DATA_DIR / "04_campaign.tsv", separator="\t")
    df_customer.write_csv(DATA_DIR / "05_customer.tsv", separator="\t")
    df_product.write_csv(DATA_DIR / "06_product.tsv", separator="\t")
    df_creative.write_csv(DATA_DIR / "07_creative_asset.tsv", separator="\t")
    df_cc.write_csv(DATA_DIR / "08_campaign_channel.tsv", separator="\t")
    df_csm.write_csv(DATA_DIR / "09_customer_segment_membership.tsv", separator="\t")
    df_memb.write_csv(DATA_DIR / "10_membership_subscription.tsv", separator="\t")
    df_promo.write_csv(DATA_DIR / "11_promo_code.tsv", separator="\t")
    df_tp.write_csv(DATA_DIR / "12_marketing_touchpoint.tsv", separator="\t")
    df_resp.write_csv(DATA_DIR / "13_touchpoint_response.tsv", separator="\t")
    df_order.write_csv(DATA_DIR / "14_order.tsv", separator="\t")
    df_item.write_csv(DATA_DIR / "15_order_item.tsv", separator="\t")
    df_red.write_csv(DATA_DIR / "16_promo_redemption.tsv", separator="\t")
    print(f"  TSVs written to {DATA_DIR}")


LOAD_ORDER: list[tuple[str, type]] = [
    ("01_channel_type.tsv", ChannelType),
    ("02_product_category.tsv", ProductCategory),
    ("03_audience_segment.tsv", AudienceSegment),
    ("04_campaign.tsv", Campaign),
    ("05_customer.tsv", Customer),
    ("06_product.tsv", Product),
    ("07_creative_asset.tsv", CreativeAsset),
    ("08_campaign_channel.tsv", CampaignChannel),
    ("09_customer_segment_membership.tsv", CustomerSegmentMembership),
    ("10_membership_subscription.tsv", MembershipSubscription),
    ("11_promo_code.tsv", PromoCode),
    ("12_marketing_touchpoint.tsv", MarketingTouchpoint),
    ("13_touchpoint_response.tsv", TouchpointResponse),
    ("14_order.tsv", Order),
    ("15_order_item.tsv", OrderItem),
    ("16_promo_redemption.tsv", PromoRedemption),
]


def _coerce_value(col_type, value):
    if value is None:
        return None
    type_name = str(col_type).lower()
    if "date" in type_name and "time" not in type_name:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return datetime.fromisoformat(value).date()
        if isinstance(value, datetime):
            return value.date()
        return value
    if "datetime" in type_name:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    if "bool" in type_name:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "t", "yes")
    return value


def create_sqlite_database() -> None:
    """从 TSV 文件创建 SQLite 数据库。幂等：先删除已有数据库。"""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        for filename, model in LOAD_ORDER:
            path = DATA_DIR / filename
            df = pl.read_csv(
                path,
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=2000,
                null_values=["", "null", "NULL"],
            )
            mapper_cols = {c.key: c.type for c in model.__table__.columns}
            for row in df.iter_rows(named=True):
                obj_kwargs = {}
                for k, v in row.items():
                    if k in mapper_cols:
                        obj_kwargs[k] = _coerce_value(mapper_cols[k], v)
                session.add(model(**obj_kwargs))
            session.flush()
            print(f"Loaded {filename} -> {model.__tablename__} ({df.height} rows)")
        session.commit()

    print(f"SQLite database created at {DATABASE_PATH}")


def main() -> None:
    print("=" * 70)
    print("VerdantBox Subscription Growth Marketing Dataset Generator")
    print("=" * 70)
    generate_all_tsv()
    create_sqlite_database()
    print("Done.")


if __name__ == "__main__":
    main()
