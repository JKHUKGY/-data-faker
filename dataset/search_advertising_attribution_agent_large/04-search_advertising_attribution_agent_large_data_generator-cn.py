# -*- coding: utf-8 -*-

"""
Search Advertising Attribution Agent (Large) - 数据生成器

面向 Text-to-SQL / Agent 训练的北美 Search Ads 360 数据集。
Locale: en_US, USD, America/Los_Angeles。
引擎: Google Ads（约占 75% 的花费）和 Microsoft Advertising（约 25%）。

Schema 与完整性
- ``daily_stats`` 以 Campaign 为粒度，带有直接的 ``campaign_id`` 外键。
- ``attribution_path`` 的 touchpoint 严格保持在该 conversion 所属
  advertiser 的子树内（遵循 campaign → ad_group → keyword 的父子关系）。
- ``engine_account.advertiser_id`` / ``bid_strategy.advertiser_id`` /
  ``floodlight_tag.advertiser_id`` 与其父 ``campaign`` /
  ``conversion`` 行的 advertiser 保持一致。
- ``daily_stats.search_impr_share`` / ``search_top_is`` / ``search_abs_top_is``
  在非 Search campaign（Display / Video / Performance Max /
  Shopping）上为 NULL —— 真实的 SA360 不会对非搜索库存暴露这些指标。
- ``agency_client(agency_id, advertiser_id)`` 是 UNIQUE。
- ``campaign_budget(campaign_id, effective_date)`` 是 UNIQUE，同一
  campaign 的相邻 ``effective_date`` 值至少间隔 20 天
  （采用累积偏移量）。

时间与排序不变量
- Touchpoint 的 ``hours_before_conv`` 经过排序，使 ``touchpoint_order=1`` 是
  时间上最早的触点，``=N`` 是紧贴 conversion 之前的触点。
- ``hours_before_conv`` 受该 conversion 的 Floodlight tag 的
  ``lookback_window`` 限制。
- ``daily_stats`` 行只在每个 campaign 的有效窗口内生成
  ``[max(start_date, today-90), min(end_date or today, today)]``。

分布锚点
- 引擎占比: 按 campaign 和花费计约 75% Google / 25% Microsoft。
- 设备占比: Mobile 约占 60% impressions，Desktop 的 CPA 最优，Tablet 约 10%
  （``DEVICE_IMPRESSION_SCALE`` / ``DEVICE_CONV_RATE_SCALE``）。
- 引擎差异: Microsoft 的 CPC 比 Google 低约 20%，conversion rate 低约 12%
  （``ENGINE_CPC_SCALE`` /
  ``ENGINE_CONV_RATE_SCALE``）。
- 行业 conversion value: 通过 ``INDUSTRY_CONV_VALUE_RANGE`` 设定各垂直行业的
  取值范围 —— Real Estate / Financial Services /
  Insurance / Auto 偏高；Restaurants / Retail 偏低。
- 行业 Quality Score: ``_qs_weights_for_industry`` 对竞争激烈的垂直行业
  （Insurance、Financial Services、Real Estate）把 QS 分布左移，
  对低竞争的细分领域（B2B SaaS、Education、Restaurants）右移。
- 路径长度分布为截断几何分布（N ∈ {2,3,4,5,6} 对应权重 [40,30,15,10,5]）。
- Position-Based credit 在 N=2 时返回 (0.5, 0.5)；N≥3 时按
  40 / 40 / 20% 分摊。
- 渠道占比按 touchpoint 位置进行偏置: Display / Paid Social
  偏向 first-touch；Paid Search / Direct 偏向 last-touch。
- Quality-Score 的子分项（``expected_ctr``、``ad_relevance``、
  ``landing_page_exp``）按 keyword 的整体 QS 加权。
- ``daily_budget`` 从一个跟随其父 advertiser 的 ``monthly_spend_tier`` 的
  范围中采样（``DAILY_BUDGET_RANGE_BY_TIER``）。
- Agency tier ↔ advertiser company_size 相关: Platinum agency
  偏向 Enterprise / Mid-Market；Standard agency 只服务 SMB。
- ``floodlight_tag.attribution_model`` 偏向 Last Click（约 45%），
  与 SA360 生产环境的默认值一致。
- ``daily_stats.lost_is_rank`` 经采样保证非负。
- ``daily_stats.lost_is_budget`` 在单日 cost 超过该 campaign 当时
  ``daily_budget`` 约 80% 时向上偏置。

运行机制
- ``search_term_report`` 采用按 keyword 分层的采样，无全局上限。
- TSV 的布尔列以整数 ``0``/``1`` 写入（规避 polars 的
  ``true``/``false`` 与 SQL ``= 1`` 之间的不匹配）。
- loader 末尾会创建一个 SQL 视图 ``v_reference_date``，让所有
  query 模板可以使用 ``(SELECT reference_date FROM v_reference_date)``
  而不是 ``DATE('now', ...)``。
"""

from __future__ import annotations

import random
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import polars as pl
from faker import Faker
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "search_advertising_attribution_agent_large.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# 业务常量（北美 Search Ads 360）
# ============================================================================
INDUSTRIES: List[Dict[str, str]] = [
    {"code": "RETAIL", "name": "Retail & E-commerce",
     "description": "Online and brick-and-mortar consumer goods"},
    {"code": "TRAVEL", "name": "Travel & Hospitality",
     "description": "Airlines, hotels, OTAs, vacation rentals"},
    {"code": "FINSVC", "name": "Financial Services",
     "description": "Banking, cards, lending, wealth management"},
    {"code": "HEALTH", "name": "Healthcare",
     "description": "Telehealth, clinics, pharmacy, wellness"},
    {"code": "AUTO", "name": "Automotive",
     "description": "OEM, dealers, parts, aftermarket"},
    {"code": "INSURE", "name": "Insurance",
     "description": "Auto, home, life, renters, pet"},
    {"code": "B2BSAAS", "name": "B2B SaaS",
     "description": "CRM, HR, project management, dev tools"},
    {"code": "EDU", "name": "Education",
     "description": "Higher ed, bootcamps, online courses"},
    {"code": "REALEST", "name": "Real Estate",
     "description": "Brokerages, rentals, mortgages, property tech"},
    {"code": "RESTRNT", "name": "Restaurants & Food Delivery",
     "description": "QSR, casual dining, delivery aggregators"},
]

REGIONS: List[Dict[str, str]] = [
    {"code": "NE", "name": "Northeast"},
    {"code": "MW", "name": "Midwest"},
    {"code": "SO", "name": "South"},
    {"code": "SE", "name": "Southeast"},
    {"code": "WE", "name": "West"},
    {"code": "PAC", "name": "Pacific"},
    {"code": "MT", "name": "Mountain"},
]

BID_STRATEGIES: List[Dict[str, object]] = [
    {"code": "MANUAL_CPC", "name": "Manual CPC",
     "description": "Advertiser sets max CPC per keyword", "is_automated": 0},
    {"code": "ENHANCED_CPC", "name": "Enhanced CPC",
     "description": "Manual bids adjusted by predicted conversion likelihood", "is_automated": 0},
    {"code": "TARGET_CPA", "name": "Target CPA",
     "description": "Smart bidding to hit a cost-per-acquisition target", "is_automated": 1},
    {"code": "TARGET_ROAS", "name": "Target ROAS",
     "description": "Smart bidding to hit a return-on-ad-spend target", "is_automated": 1},
    {"code": "MAX_CONV", "name": "Maximize Conversions",
     "description": "Spend full budget for the most conversions", "is_automated": 1},
    {"code": "MAX_CONV_VAL", "name": "Maximize Conversion Value",
     "description": "Spend full budget for the most conversion value", "is_automated": 1},
    {"code": "MAX_CLICKS", "name": "Maximize Clicks",
     "description": "Spend full budget for the most clicks", "is_automated": 1},
    {"code": "TARGET_IS", "name": "Target Impression Share",
     "description": "Bid to hit an impression-share goal at a chosen position", "is_automated": 1},
]

MATCH_TYPES: List[Dict[str, str]] = [
    {"code": "EXACT", "name": "Exact Match"},
    {"code": "PHRASE", "name": "Phrase Match"},
    {"code": "BROAD", "name": "Broad Match"},
]

DEVICES: List[Dict[str, str]] = [
    {"code": "MOBILE", "name": "Mobile"},
    {"code": "DESKTOP", "name": "Desktop"},
    {"code": "TABLET", "name": "Tablet"},
]

CHANNELS: List[Dict[str, str]] = [
    {"code": "PAID_SEARCH", "name": "Paid Search"},
    {"code": "DISPLAY", "name": "Display"},
    {"code": "SOCIAL", "name": "Paid Social"},
    {"code": "EMAIL", "name": "Email"},
    {"code": "DIRECT", "name": "Direct"},
    {"code": "ORGANIC", "name": "Organic Search"},
]

AGENCY_TIERS = ["Platinum", "Gold", "Silver", "Standard"]
COMPANY_SIZES = ["SMB", "Mid-Market", "Enterprise"]
MONTHLY_SPEND_TIERS = ["<10K", "10K-50K", "50K-200K", ">200K"]
PRIMARY_GOALS = ["Brand Awareness", "Lead Generation", "Sales Conversion", "App Installs"]

# 北美 Search Ads 360 的双引擎组合。已移除 Yahoo Japan（它是日本的
# Yahoo! JAPAN Ads 合作伙伴，不服务美国 advertiser）。
# Google Ads 是主引擎；Microsoft Advertising 是次引擎。
ENGINE_TYPES = ["Google Ads", "Microsoft Advertising"]
ENGINE_WEIGHTS = [75, 25]

CAMPAIGN_TYPES = ["Search", "Shopping", "Display", "Video", "Performance Max"]
CAMPAIGN_TYPE_WEIGHTS = [55, 18, 12, 8, 7]
CAMPAIGN_SUBTYPES = ["Standard", "Smart", "Dynamic"]

CONVERSION_TYPES = ["Purchase", "Lead", "Signup", "PageView", "AddToCart", "AppInstall"]
INTERACTION_TYPES = ["Click", "Impression", "View"]
INTERACTION_TYPE_WEIGHTS = [15, 80, 5]  # P1-10: impressions 在路径中占主导

ATTRIBUTION_MODELS = [
    "Last Click", "First Click", "Linear",
    "Time Decay", "Position Based", "Data Driven",
]

US_GEO_TARGETS = [
    "United States", "California", "Texas", "New York", "Florida",
    "Illinois", "Pennsylvania", "Ohio", "Georgia", "Washington",
    "New York City Metro", "Los Angeles Metro", "Chicago Metro",
    "Dallas-Fort Worth", "Houston Metro", "Phoenix Metro", "Atlanta Metro",
    "Seattle Metro", "Miami Metro", "Boston Metro",
]

TARGETING_LANGUAGES = ["English", "Spanish", "English; Spanish"]
TARGETING_DEVICES = ["All", "Mobile only", "Desktop + Tablet", "Mobile + Tablet"]

# 各行业的 keyword —— SA360 advertiser 在美国实际会投放的
# 短头部词 + 中长尾词。
KEYWORDS_BY_INDUSTRY: Dict[str, List[str]] = {
    "Retail & E-commerce": [
        "best running shoes", "wireless earbuds", "kitchen knife set",
        "iphone 15 case", "standing desk", "espresso machine",
        "memory foam pillow", "cordless vacuum", "smart tv 55 inch",
        "winter jacket men", "yoga mat", "air fryer", "robot vacuum",
        "noise cancelling headphones", "gaming chair", "ergonomic mouse",
    ],
    "Travel & Hospitality": [
        "cheap flights to maui", "all inclusive cancun", "vegas hotel deals",
        "rental car phoenix", "disney world packages", "hawaii vacation",
        "european river cruise", "cabo san lucas resorts", "iceland tours",
        "national park lodges", "boutique hotels nyc", "airbnb san diego",
        "alaska cruise 2026", "cheap flights to europe", "all inclusive jamaica",
    ],
    "Financial Services": [
        "best credit cards 2026", "auto loan rates", "checking account no fees",
        "investing for beginners", "high yield savings", "balance transfer card",
        "personal loan rates", "business credit card", "401k rollover",
        "wealth advisor near me", "small business banking", "wire transfer fees",
        "online brokerage account", "robo advisor comparison", "open ira",
    ],
    "Healthcare": [
        "telehealth doctor", "weight loss program", "dental implants near me",
        "online therapy", "lasik eye surgery", "primary care doctor accepting patients",
        "covid testing near me", "physical therapy near me", "dermatologist online",
        "fertility clinic", "pediatrician near me", "mental health counseling",
        "ozempic prescription", "varicose vein treatment",
    ],
    "Automotive": [
        "2026 toyota camry price", "used trucks for sale", "ford f150 lease deals",
        "tesla model y price", "honda civic dealer", "car insurance quotes",
        "auto loan calculator", "best electric vehicles 2026", "jeep wrangler price",
        "tire rotation near me", "oil change near me", "extended car warranty",
        "ev charging stations", "trade in value", "rav4 hybrid availability",
    ],
    "Insurance": [
        "term life insurance quote", "renters insurance", "auto insurance comparison",
        "homeowners insurance quote", "pet insurance", "umbrella policy",
        "small business liability insurance", "disability insurance",
        "medicare supplement plans", "dental insurance plans", "travel insurance",
        "earthquake insurance california", "boat insurance quote", "rv insurance",
    ],
    "B2B SaaS": [
        "crm software pricing", "project management tool", "hr software small business",
        "applicant tracking system", "marketing automation platform", "help desk software",
        "video conferencing for business", "expense management software", "payroll software smb",
        "e signature software", "knowledge base software", "endpoint security software",
        "observability platform", "data warehouse pricing",
    ],
    "Education": [
        "online mba programs", "coding bootcamp", "sat prep course",
        "data science certificate", "online masters in computer science",
        "online nursing programs", "executive education", "language learning app",
        "cybersecurity certification", "online accounting degree",
        "k12 tutoring online", "test prep gmat", "phd in education online",
        "online psychology degree",
    ],
    "Real Estate": [
        "homes for sale austin", "apartments for rent nyc", "real estate agent dallas",
        "mortgage rates today", "first time home buyer programs", "home value estimator",
        "luxury condos miami", "rent vs buy calculator", "fsbo listings",
        "open houses near me", "commercial real estate listings", "home inspection cost",
        "refinance calculator", "investment property loans",
    ],
    "Restaurants & Food Delivery": [
        "best pizza near me", "italian restaurants chicago", "sushi delivery",
        "thai food delivery", "best burgers nyc", "happy hour near me",
        "brunch reservations", "wedding catering", "gluten free restaurants",
        "vegan restaurants la", "late night food delivery", "michelin star restaurants",
        "rooftop bar nyc", "tacos near me", "ramen near me",
    ],
}


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    pass


# ---- 维度表 --------------------------------------------------------------
class Industry(Base):
    __tablename__ = "industry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Region(Base):
    __tablename__ = "region"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class BidStrategyType(Base):
    __tablename__ = "bid_strategy_type"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_automated: Mapped[bool] = mapped_column(Boolean, default=False)


class MatchType(Base):
    __tablename__ = "match_type"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class Device(Base):
    __tablename__ = "device"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class Channel(Base):
    __tablename__ = "channel"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


# ---- 组织 ----------------------------------------------------------------
class Agency(Base):
    __tablename__ = "agency"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    agency_name: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), nullable=False)
    tier_level: Mapped[str] = mapped_column(String(20), nullable=False)
    account_manager: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Advertiser(Base):
    __tablename__ = "advertiser"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industry.id"), nullable=False)
    sub_industry: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_size: Mapped[str] = mapped_column(String(20), nullable=False)
    monthly_spend_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_goal: Mapped[str] = mapped_column(String(50), nullable=False)
    website_url: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    account_status: Mapped[str] = mapped_column(String(20), nullable=False)


class AgencyClient(Base):
    __tablename__ = "agency_client"
    __table_args__ = (
        UniqueConstraint("agency_id", "advertiser_id", name="uq_agency_client_pair"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agency.id"), nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    contract_start: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fee_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


# ---- 账户结构 ------------------------------------------------------------
class EngineAccount(Base):
    __tablename__ = "engine_account"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    engine_type: Mapped[str] = mapped_column(String(30), nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class BidStrategy(Base):
    __tablename__ = "bid_strategy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type_id: Mapped[int] = mapped_column(ForeignKey("bid_strategy_type.id"), nullable=False)
    target_cpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_roas: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_cpc_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_impr_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impr_share_location: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_modified: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Campaign(Base):
    __tablename__ = "campaign"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    engine_account_id: Mapped[int] = mapped_column(ForeignKey("engine_account.id"), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(30), nullable=False)
    campaign_subtype: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    bid_strategy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bid_strategy.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    targeting_location: Mapped[str] = mapped_column(String(100), nullable=False)
    targeting_language: Mapped[str] = mapped_column(String(50), nullable=False)
    targeting_device: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CampaignBudget(Base):
    __tablename__ = "campaign_budget"
    __table_args__ = (
        UniqueConstraint("campaign_id", "effective_date", name="uq_campaign_budget_effective"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=False)
    daily_budget: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_budget: Mapped[float] = mapped_column(Float, nullable=False)
    budget_delivery: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AdGroup(Base):
    __tablename__ = "ad_group"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_group_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=False)
    ad_group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_cpc: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Keyword(Base):
    __tablename__ = "keyword"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    ad_group_id: Mapped[int] = mapped_column(ForeignKey("ad_group.id"), nullable=False)
    keyword_text: Mapped[str] = mapped_column(String(300), nullable=False)
    match_type_id: Mapped[int] = mapped_column(ForeignKey("match_type.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    max_cpc: Mapped[float] = mapped_column(Float, nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_ctr: Mapped[str] = mapped_column(String(20), nullable=False)
    ad_relevance: Mapped[str] = mapped_column(String(20), nullable=False)
    landing_page_exp: Mapped[str] = mapped_column(String(20), nullable=False)
    first_page_cpc: Mapped[float] = mapped_column(Float, nullable=False)
    top_of_page_cpc: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TextAd(Base):
    __tablename__ = "text_ad"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    ad_group_id: Mapped[int] = mapped_column(ForeignKey("ad_group.id"), nullable=False)
    headline_1: Mapped[str] = mapped_column(String(100), nullable=False)
    headline_2: Mapped[str] = mapped_column(String(100), nullable=False)
    headline_3: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description_1: Mapped[str] = mapped_column(String(200), nullable=False)
    description_2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    final_url: Mapped[str] = mapped_column(String(500), nullable=False)
    display_url: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FloodlightTag(Base):
    __tablename__ = "floodlight_tag"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    conversion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    counting_method: Mapped[str] = mapped_column(String(30), nullable=False)
    attribution_model: Mapped[str] = mapped_column(String(30), nullable=False)
    lookback_window: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ---- 事实表 --------------------------------------------------------------
class DailyStats(Base):
    """每日的 campaign 级表现。粒度 = (campaign_id, report_date, device_id)。

    已弃用的 SA360 数据集中的多态 entity_type/entity_id 列已被移除
    （见 design_decisions.md §3, P1-1, Option A）。所有行都以
    Campaign 为粒度，带有直接的 ``campaign_id`` 外键。
    """
    __tablename__ = "daily_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    conversions: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cpc: Mapped[float] = mapped_column(Float, nullable=False)
    cpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roas: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impression_share: Mapped[float] = mapped_column(Float, nullable=False)
    # `search_*_is` 列只对 Search campaign 可上报 ——
    # 在 Display / Video / Performance Max 行上为 NULL（真实的 SA360
    # 不会对非搜索库存暴露这些指标）。
    search_impr_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_is_budget: Mapped[float] = mapped_column(Float, nullable=False)
    lost_is_rank: Mapped[float] = mapped_column(Float, nullable=False)
    search_abs_top_is: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    search_top_is: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Conversion(Base):
    __tablename__ = "conversion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversion_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    floodlight_tag_id: Mapped[int] = mapped_column(ForeignKey("floodlight_tag.id"), nullable=False)
    conversion_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class AttributionPath(Base):
    __tablename__ = "attribution_path"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversion_id: Mapped[int] = mapped_column(ForeignKey("conversion.id"), nullable=False)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertiser.id"), nullable=False)
    touchpoint_order: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.id"), nullable=False)
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaign.id"), nullable=True)
    ad_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ad_group.id"), nullable=True)
    keyword_id: Mapped[Optional[int]] = mapped_column(ForeignKey("keyword.id"), nullable=True)
    interaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    interaction_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    days_before_conv: Mapped[int] = mapped_column(Integer, nullable=False)
    hours_before_conv: Mapped[int] = mapped_column(Integer, nullable=False)
    last_click_credit: Mapped[float] = mapped_column(Float, nullable=False)
    first_click_credit: Mapped[float] = mapped_column(Float, nullable=False)
    linear_credit: Mapped[float] = mapped_column(Float, nullable=False)
    time_decay_credit: Mapped[float] = mapped_column(Float, nullable=False)
    position_credit: Mapped[float] = mapped_column(Float, nullable=False)
    data_driven_credit: Mapped[float] = mapped_column(Float, nullable=False)


class SearchTermReport(Base):
    """Search-term 表现。``keyword_id`` 可为空: broad-match
    溢出的 query 无法映射回某个已存储的 keyword（P1-3 from review）。"""
    __tablename__ = "search_term_report"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=False)
    ad_group_id: Mapped[int] = mapped_column(ForeignKey("ad_group.id"), nullable=False)
    keyword_id: Mapped[Optional[int]] = mapped_column(ForeignKey("keyword.id"), nullable=True)
    search_term: Mapped[str] = mapped_column(String(500), nullable=False)
    match_type_used: Mapped[str] = mapped_column(String(20), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    conversions: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False)
    added_excluded: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


# ============================================================================
# 生成函数 —— 维度
# ============================================================================
def gen_industry() -> pl.DataFrame:
    rows = [{"id": i + 1, **d} for i, d in enumerate(INDUSTRIES)]
    return pl.DataFrame(rows)


def gen_region() -> pl.DataFrame:
    rows = [{"id": i + 1, **d} for i, d in enumerate(REGIONS)]
    return pl.DataFrame(rows)


def gen_bid_strategy_type() -> pl.DataFrame:
    rows = [{"id": i + 1, **d} for i, d in enumerate(BID_STRATEGIES)]
    return pl.DataFrame(rows)


def gen_match_type() -> pl.DataFrame:
    rows = [{"id": i + 1, **d} for i, d in enumerate(MATCH_TYPES)]
    return pl.DataFrame(rows)


def gen_device() -> pl.DataFrame:
    rows = [{"id": i + 1, **d} for i, d in enumerate(DEVICES)]
    return pl.DataFrame(rows)


def gen_channel() -> pl.DataFrame:
    rows = [{"id": i + 1, **d} for i, d in enumerate(CHANNELS)]
    return pl.DataFrame(rows)


# ============================================================================
# 生成函数 —— 组织
# ============================================================================
def gen_agency(region_ids: List[int], n: int = 15) -> pl.DataFrame:
    """分层的 tier 拆分: 只有 15 个 agency 时，用权重采样 Standard
    会产生很大的方差（该 tier 经常出现 0 个 agency）。改用一个
    确定性的拆分，始终保证 Standard tier 非空。"""
    target_counts = {"Platinum": 2, "Gold": 5, "Silver": 5, "Standard": 3}
    assert sum(target_counts.values()) == n, "tier split must total n agencies"
    tiers: List[str] = []
    for tier, count in target_counts.items():
        tiers.extend([tier] * count)
    random.shuffle(tiers)

    records = []
    for i in range(1, n + 1):
        records.append({
            "id": i,
            "agency_code": f"AGY_{str(i).zfill(3)}",
            "agency_name": fake.company() + " Media",
            "region_id": random.choice(region_ids),
            "tier_level": tiers[i - 1],
            "account_manager": fake.name(),
            "contact_email": fake.company_email(),
            "contact_phone": fake.phone_number(),
            "created_at": fake.date_time_between(start_date="-3y", end_date="-1y").isoformat(),
        })
    return pl.DataFrame(records)


# 以天为单位的偏移量 —— Faker 的 date_between 把小写 "m" 当作分钟而非
# 月份，所以所有以月为尺度的偏移量都用天来表示。
DAYS_2Y = 730
DAYS_18M = 540
DAYS_6M = 180
DAYS_3M = 90
DAYS_1M = 30


# ----- gen_daily_stats 内部使用的差异化乘数 --------------------------------
# 设备在 impression / click / conversion 总量中所占的份额。
# Mobile 在量上占主导；Desktop 的转化率更高；Tablet 占比很小。
DEVICE_IMPRESSION_SCALE = {
    "Mobile":  1.5,
    "Desktop": 0.7,
    "Tablet":  0.25,
}
DEVICE_CONV_RATE_SCALE = {
    "Mobile":  0.75,
    "Desktop": 1.50,
    "Tablet":  0.95,
}

# 引擎层面的差异化。Microsoft 历史上以更低的 CPC 成交（竞争更少），
# 但 conversion rate 也更低。
ENGINE_CPC_SCALE = {
    "Google Ads":            1.00,
    "Microsoft Advertising": 0.80,
}
ENGINE_CONV_RATE_SCALE = {
    "Google Ads":            1.00,
    "Microsoft Advertising": 0.88,
}

# 行业层面的 conversion value（LTV / 客单价）。高客单价的垂直行业
# （Financial Services、Insurance、Real Estate）的单次 conversion 价值
# 远高于餐饮或零售。
INDUSTRY_CONV_VALUE_RANGE = {
    "Retail & E-commerce":         (50, 350),
    "Travel & Hospitality":        (150, 900),
    "Financial Services":          (200, 1500),
    "Healthcare":                  (100, 800),
    "Automotive":                  (300, 1500),
    "Insurance":                   (200, 1200),
    "B2B SaaS":                    (250, 1000),
    "Education":                   (100, 700),
    "Real Estate":                 (400, 2000),
    "Restaurants & Food Delivery": (15, 90),
}


def gen_advertiser(industry_ids: List[int], n: int = 80) -> pl.DataFrame:
    records = []
    for i in range(1, n + 1):
        company_size = random.choices(COMPANY_SIZES, weights=[50, 35, 15])[0]
        if company_size == "Enterprise":
            spend_tier = random.choices(MONTHLY_SPEND_TIERS, weights=[5, 15, 40, 40])[0]
        elif company_size == "Mid-Market":
            spend_tier = random.choices(MONTHLY_SPEND_TIERS, weights=[10, 40, 40, 10])[0]
        else:
            spend_tier = random.choices(MONTHLY_SPEND_TIERS, weights=[40, 40, 15, 5])[0]
        records.append({
            "id": i,
            "advertiser_code": f"ADV_{str(i).zfill(3)}",
            "company_name": fake.company(),
            "industry_id": random.choice(industry_ids),
            "sub_industry": None,
            "company_size": company_size,
            "monthly_spend_tier": spend_tier,
            "primary_goal": random.choice(PRIMARY_GOALS),
            "website_url": f"https://www.{fake.domain_name()}",
            "created_at": fake.date_time_between(start_date=f"-{DAYS_2Y}d", end_date=f"-{DAYS_6M}d").isoformat(),
            "account_status": random.choices(["Active", "Paused", "Suspended"], weights=[85, 12, 3])[0],
        })
    return pl.DataFrame(records)


# 为 advertiser 挑选 agency 时，按 agency 的 tier 与 advertiser 的
# company_size 加权。Platinum/Gold agency 服务更大的账户；Standard agency
# 服务 SMB。正是这一点让 tier-by-ROAS 查询（#17）呈现出有意义的差异，
# 而不是让 tier 与花费在统计上相互独立。
TIER_PROBABILITY_BY_SIZE: Dict[str, Dict[str, float]] = {
    "Enterprise": {"Platinum": 40, "Gold": 40, "Silver": 15, "Standard": 5},
    "Mid-Market": {"Platinum": 15, "Gold": 40, "Silver": 35, "Standard": 10},
    "SMB":        {"Platinum": 5,  "Gold": 20, "Silver": 35, "Standard": 40},
}


def gen_agency_client(agency_df: pl.DataFrame,
                      advertiser_df: pl.DataFrame) -> pl.DataFrame:
    """约 80% 的 advertiser 由 agency 托管；其余为直客。约
    30% 的合同已结束（`is_active=0`），这样下游查询里的 active
    过滤条件才会真正起作用。"""
    records = []
    record_id = 1
    today = date.today()
    advertisers = list(advertiser_df.iter_rows(named=True))
    agencies = list(agency_df.iter_rows(named=True))
    agencies_by_tier: Dict[str, List[int]] = {}
    for row in agencies:
        agencies_by_tier.setdefault(row["tier_level"], []).append(row["id"])

    managed = random.sample(advertisers, k=int(len(advertisers) * 0.8))
    for adv in managed:
        # 根据 advertiser 的 company_size 偏置挑选一个 tier，再从该 tier 中
        # 随机选一个 agency（若该 tier 下没有 agency 则回退，这在只有
        # 15 个 agency 时可能发生）。
        size = adv["company_size"]
        tier_weights = TIER_PROBABILITY_BY_SIZE[size]
        for _ in range(5):
            chosen_tier = random.choices(
                list(tier_weights.keys()),
                weights=list(tier_weights.values()),
            )[0]
            if agencies_by_tier.get(chosen_tier):
                agency_id = random.choice(agencies_by_tier[chosen_tier])
                break
        else:
            agency_id = random.choice([row["id"] for row in agencies])

        contract_start = fake.date_between(start_date=f"-{DAYS_2Y}d", end_date=f"-{DAYS_3M}d")
        # 60% 无限期（NULL），20% 已结束（is_active=0），
        # 20% 在未来结束（仍然 active）。
        end_mode = random.choices(["open", "past", "future"], weights=[60, 20, 20])[0]
        if end_mode == "open":
            contract_end = None
        elif end_mode == "past":
            contract_end = fake.date_between(start_date=contract_start, end_date=f"-{DAYS_1M}d")
        else:
            contract_end = fake.date_between(start_date=f"+{DAYS_1M}d", end_date="+1y")
        is_active = contract_end is None or contract_end > today

        records.append({
            "id": record_id,
            "agency_id": agency_id,
            "advertiser_id": adv["id"],
            "contract_start": contract_start.isoformat(),
            "contract_end": contract_end.isoformat() if contract_end else None,
            "fee_percentage": round(random.uniform(8, 20), 1),
            "is_active": 1 if is_active else 0,
        })
        record_id += 1
    return pl.DataFrame(records)


# ============================================================================
# 生成函数 —— 账户结构
# ============================================================================
def gen_engine_account(advertiser_ids: List[int]) -> pl.DataFrame:
    """每个 advertiser 都有 Google Ads；约 50% 额外拥有 Microsoft。
    再加上 campaign 在该 advertiser 可用引擎间的随机分配，
    便能在组合层面得到接近预期的 75% Google / 25% Microsoft
    的 campaign 占比。"""
    records = []
    record_id = 1
    for adv_id in advertiser_ids:
        # 所有 advertiser 都投放 Google Ads（北美 SA360 的主引擎）。
        engines = ["Google Ads"]
        if random.random() < 0.50:
            engines.append("Microsoft Advertising")
        for engine in engines:
            records.append({
                "id": record_id,
                "account_code": f"ENG_{str(record_id).zfill(4)}",
                "advertiser_id": adv_id,
                "engine_type": engine,
                "account_name": f"{engine} - Advertiser {adv_id}",
                "currency": "USD",
                "timezone": "America/Los_Angeles",
                "status": random.choices(["Active", "Paused"], weights=[90, 10])[0],
                "created_at": fake.date_time_between(start_date=f"-{DAYS_2Y}d", end_date=f"-{DAYS_3M}d").isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_bid_strategy(advertiser_ids: List[int], strategy_type_df: pl.DataFrame) -> pl.DataFrame:
    """对所选的 (advertiser, strategy_type) 子集，每个组合生成一行 strategy。"""
    records = []
    record_id = 1
    strategy_codes = strategy_type_df["code"].to_list()
    strategy_names = strategy_type_df["name"].to_list()
    code_to_id = {c: i + 1 for i, c in enumerate(strategy_codes)}

    for adv_id in advertiser_ids:
        num_strategies = random.randint(2, 5)
        chosen_codes = random.sample(strategy_codes, k=min(num_strategies, len(strategy_codes)))
        for code in chosen_codes:
            target_cpa = None
            target_roas = None
            max_cpc_limit = None
            target_impr_share = None
            impr_share_location = None

            if code == "TARGET_CPA":
                target_cpa = round(random.uniform(20, 200), 2)
            elif code == "TARGET_ROAS":
                target_roas = round(random.uniform(2.0, 8.0), 2)
            elif code in ("MANUAL_CPC", "ENHANCED_CPC"):
                max_cpc_limit = round(random.uniform(1, 20), 2)
            elif code == "TARGET_IS":
                target_impr_share = round(random.uniform(50, 95), 0)
                impr_share_location = random.choice(["Anywhere", "Top of page", "Absolute top"])

            created_at = fake.date_time_between(start_date=f"-{DAYS_18M}d", end_date=f"-{DAYS_1M}d")
            name = strategy_names[strategy_codes.index(code)]
            records.append({
                "id": record_id,
                "strategy_code": f"BID_{str(record_id).zfill(4)}",
                "advertiser_id": adv_id,
                "strategy_name": f"{name} - Adv {adv_id}",
                "strategy_type_id": code_to_id[code],
                "target_cpa": target_cpa,
                "target_roas": target_roas,
                "max_cpc_limit": max_cpc_limit,
                "target_impr_share": target_impr_share,
                "impr_share_location": impr_share_location,
                "status": random.choices(["Active", "Paused"], weights=[80, 20])[0],
                "created_at": created_at.isoformat(),
                "last_modified": (created_at + timedelta(days=random.randint(1, 60))).isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def _campaign_name(advertiser_id: int, industry_name: str, campaign_type: str,
                   campaign_id: int) -> str:
    """Google Ads 风格的命名: {Brand}_{Product}_{MatchType}_{Geo}_{Device}。"""
    brand = f"Adv{advertiser_id}"
    product_pool = {
        "Retail & E-commerce": ["Footwear", "Electronics", "HomeGoods", "Apparel"],
        "Travel & Hospitality": ["Flights", "Hotels", "Cruises", "CarRental"],
        "Financial Services": ["CreditCards", "Loans", "Savings", "Wealth"],
        "Healthcare": ["Telehealth", "DentalCare", "EyeCare", "Pharmacy"],
        "Automotive": ["SUVs", "Trucks", "Sedans", "EVs"],
        "Insurance": ["AutoInsurance", "HomeInsurance", "LifeInsurance", "RentersInsurance"],
        "B2B SaaS": ["CRM", "ProjectMgmt", "HRTech", "DevTools"],
        "Education": ["MBAPrograms", "Bootcamps", "TestPrep", "OnlineDegree"],
        "Real Estate": ["HomesForSale", "Apartments", "Mortgages", "Commercial"],
        "Restaurants & Food Delivery": ["Pizza", "Sushi", "Burgers", "Delivery"],
    }
    product = random.choice(product_pool.get(industry_name, ["Generic"]))
    match = random.choice(["Brand", "Generic", "Competitor", "LongTail"])
    geo = random.choice(["US", "CA", "TX", "NY", "FL", "WestCoast", "Northeast"])
    device = random.choice(["AllDevice", "Mobile", "Desktop"])
    return f"{brand}_{product}_{match}_{geo}_{device}_C{campaign_id}"


def gen_campaign(advertiser_ids: List[int], engine_account_df: pl.DataFrame,
                 bid_strategy_df: pl.DataFrame, advertiser_df: pl.DataFrame,
                 industry_df: pl.DataFrame) -> pl.DataFrame:
    records = []
    record_id = 1
    adv_to_engines: Dict[int, List[int]] = {}
    for row in engine_account_df.iter_rows(named=True):
        adv_to_engines.setdefault(row["advertiser_id"], []).append(row["id"])
    adv_to_strategies: Dict[int, List[int]] = {}
    for row in bid_strategy_df.iter_rows(named=True):
        adv_to_strategies.setdefault(row["advertiser_id"], []).append(row["id"])
    adv_to_industry = {r["id"]: r["industry_id"] for r in advertiser_df.iter_rows(named=True)}
    industry_names = {r["id"]: r["name"] for r in industry_df.iter_rows(named=True)}

    for adv_id in advertiser_ids:
        num_campaigns = random.randint(5, 15)
        engines = adv_to_engines.get(adv_id, [])
        strategies = adv_to_strategies.get(adv_id, [])
        industry_name = industry_names[adv_to_industry[adv_id]]
        if not engines:
            continue
        for _ in range(num_campaigns):
            campaign_type = random.choices(CAMPAIGN_TYPES, weights=CAMPAIGN_TYPE_WEIGHTS)[0]
            start_date = fake.date_between(start_date=f"-{DAYS_18M}d", end_date=f"-{DAYS_1M}d")
            has_end_date = random.random() < 0.3
            end_date = (start_date + timedelta(days=random.randint(60, 360))) if has_end_date else None
            records.append({
                "id": record_id,
                "campaign_code": f"CMP_{str(record_id).zfill(5)}",
                "advertiser_id": adv_id,
                "engine_account_id": random.choice(engines),
                "campaign_name": _campaign_name(adv_id, industry_name, campaign_type, record_id),
                "campaign_type": campaign_type,
                "campaign_subtype": random.choice(CAMPAIGN_SUBTYPES) if campaign_type == "Search" else None,
                "bid_strategy_id": random.choice(strategies) if strategies else None,
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[70, 25, 5])[0],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat() if end_date else None,
                "targeting_location": random.choice(US_GEO_TARGETS),
                "targeting_language": random.choices(TARGETING_LANGUAGES, weights=[80, 5, 15])[0],
                "targeting_device": random.choices(TARGETING_DEVICES, weights=[70, 15, 10, 5])[0],
                "created_at": datetime.combine(start_date, datetime.min.time()).isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


# daily_budget 的取值范围随 advertiser 的 monthly_spend_tier 缩放。
# 这些范围是刻意重叠的（SMB 偶尔可能飙升，Enterprise 也可能跑小额的
# 实验性预算），但其中心值会跟随 tier。
DAILY_BUDGET_RANGE_BY_TIER: Dict[str, tuple] = {
    "<10K":      (50,   500),
    "10K-50K":   (200,  2_000),
    "50K-200K":  (1_000, 8_000),
    ">200K":     (3_000, 30_000),
}


def gen_campaign_budget(campaign_df: pl.DataFrame,
                        advertiser_df: pl.DataFrame) -> pl.DataFrame:
    """每个 campaign 有 1-3 行 budget，effective_date 单调递增。
    `daily_budget` 从一个取决于 advertiser 的 `monthly_spend_tier` 的范围中
    采样，因此 SMB advertiser 不会出现 Enterprise 级别的每日预算。

    调用方将“日期 D 当天生效的 budget”解析为
    ``MAX(effective_date) WHERE effective_date <= D``（见 SQL queries 文档）。
    (campaign_id, effective_date) 组合在构造上是唯一的 ——
    同一 campaign 的相邻行 `effective_date` 至少向前推进 20 天。
    """
    records = []
    record_id = 1
    adv_to_tier = {r["id"]: r["monthly_spend_tier"]
                   for r in advertiser_df.iter_rows(named=True)}
    for row in campaign_df.iter_rows(named=True):
        cmp_id = row["id"]
        campaign_start = date.fromisoformat(row["start_date"])
        adv_tier = adv_to_tier[row["advertiser_id"]]
        lo, hi = DAILY_BUDGET_RANGE_BY_TIER[adv_tier]
        num_budgets = random.choices([1, 2, 3], weights=[35, 45, 20])[0]
        # 累积偏移量，使相邻的 effective_date 值每次至少严格递增
        # 20 天。之前的 ``i * random.randint(20, 45)`` 写法在每次迭代中
        # 重新采样，可能在 i=2 时产生比 i=1 更小的偏移量。
        cumulative_offset = 0
        for i in range(num_budgets):
            daily_budget = round(random.uniform(lo, hi), 2)
            if i > 0:
                cumulative_offset += random.randint(20, 45)
            effective_date = campaign_start + timedelta(days=cumulative_offset)
            records.append({
                "id": record_id,
                "campaign_id": cmp_id,
                "daily_budget": daily_budget,
                "monthly_budget": round(daily_budget * 30, 2),
                "budget_delivery": random.choices(["Standard", "Accelerated"], weights=[80, 20])[0],
                "effective_date": effective_date.isoformat(),
                "created_at": datetime.combine(effective_date, datetime.min.time()).isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_ad_group(campaign_df: pl.DataFrame, advertiser_df: pl.DataFrame,
                 industry_df: pl.DataFrame) -> pl.DataFrame:
    records = []
    record_id = 1
    campaign_to_adv = {r["id"]: r["advertiser_id"] for r in campaign_df.iter_rows(named=True)}
    adv_to_industry = {r["id"]: r["industry_id"] for r in advertiser_df.iter_rows(named=True)}
    industry_names = {r["id"]: r["name"] for r in industry_df.iter_rows(named=True)}

    for row in campaign_df.iter_rows(named=True):
        cmp_id = row["id"]
        adv_id = campaign_to_adv[cmp_id]
        industry_name = industry_names[adv_to_industry[adv_id]]
        num_groups = random.randint(3, 8)
        keyword_pool = KEYWORDS_BY_INDUSTRY[industry_name]
        themes = random.sample(keyword_pool, k=min(num_groups, len(keyword_pool)))
        for theme in themes:
            records.append({
                "id": record_id,
                "ad_group_code": f"AGP_{str(record_id).zfill(5)}",
                "campaign_id": cmp_id,
                "ad_group_name": f"{theme} - AdGroup",
                "default_cpc": round(random.uniform(0.5, 15), 2),
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[75, 20, 5])[0],
                "created_at": row["created_at"],
            })
            record_id += 1
    return pl.DataFrame(records)


QUALITY_LEVELS = ["Below Average", "Average", "Above Average"]

# 各垂直行业的拍卖竞争激烈程度。竞争激烈的行业
# （insurance、financial services、real estate）会让大多数 advertiser 的
# Quality Score 偏低；低竞争的细分领域（B2B SaaS、education、
# restaurants）则把 QS 分布往上推。
HIGH_COMPETITION_INDUSTRIES = {"Insurance", "Financial Services", "Real Estate"}
LOW_COMPETITION_INDUSTRIES = {"B2B SaaS", "Education", "Restaurants & Food Delivery"}

# QS 取值 [3, 4, 5, 6, 7, 8, 9, 10] 对应的 Quality Score 权重。
QS_WEIGHTS_DEFAULT       = [3,  5, 10, 20, 25, 20, 12, 5]
QS_WEIGHTS_HIGH_COMPETE  = [6, 10, 20, 25, 20, 12,  5, 2]   # 左移
QS_WEIGHTS_LOW_COMPETE   = [1,  3,  7, 15, 22, 25, 17, 10]  # 右移


def _qs_weights_for_industry(industry: str) -> List[int]:
    if industry in HIGH_COMPETITION_INDUSTRIES:
        return QS_WEIGHTS_HIGH_COMPETE
    if industry in LOW_COMPETITION_INDUSTRIES:
        return QS_WEIGHTS_LOW_COMPETE
    return QS_WEIGHTS_DEFAULT


def _qs_subcomponent_for(quality_score: int) -> str:
    """从 {Below Average, Average, Above Average} 中采样一个，权重与
    keyword 的整体 quality_score 相关。高 QS 的 keyword 偏向
    Above Average；低 QS 的 keyword 偏向 Below Average。"""
    if quality_score >= 8:
        weights = [5, 25, 70]
    elif quality_score >= 6:
        weights = [15, 50, 35]
    else:
        weights = [55, 35, 10]
    return random.choices(QUALITY_LEVELS, weights=weights)[0]


def gen_keyword(ad_group_df: pl.DataFrame, campaign_df: pl.DataFrame,
                advertiser_df: pl.DataFrame, industry_df: pl.DataFrame,
                match_type_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1
    adgroup_to_campaign = {r["id"]: r["campaign_id"] for r in ad_group_df.iter_rows(named=True)}
    campaign_to_adv = {r["id"]: r["advertiser_id"] for r in campaign_df.iter_rows(named=True)}
    adv_to_industry = {r["id"]: r["industry_id"] for r in advertiser_df.iter_rows(named=True)}
    industry_names = {r["id"]: r["name"] for r in industry_df.iter_rows(named=True)}

    for row in ad_group_df.iter_rows(named=True):
        agp_id = row["id"]
        cmp_id = adgroup_to_campaign[agp_id]
        adv_id = campaign_to_adv[cmp_id]
        industry_name = industry_names[adv_to_industry[adv_id]]
        keyword_pool = KEYWORDS_BY_INDUSTRY[industry_name]
        num_keywords = random.randint(5, 15)
        chosen = random.sample(keyword_pool, k=min(num_keywords, len(keyword_pool)))
        qs_weights = _qs_weights_for_industry(industry_name)
        for kw_text in chosen:
            # Quality score 偏向 6-8（钟形分布）。对竞争激烈的垂直行业
            # （insurance、finance、real estate）权重左移，对低竞争的
            # 细分领域右移。
            quality_score = random.choices(
                [3, 4, 5, 6, 7, 8, 9, 10],
                weights=qs_weights,
            )[0]
            max_cpc = round(random.uniform(0.5, 20), 2)
            records.append({
                "id": record_id,
                "keyword_code": f"KW_{str(record_id).zfill(6)}",
                "ad_group_id": agp_id,
                "keyword_text": kw_text,
                "match_type_id": random.choice(match_type_ids),
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[80, 15, 5])[0],
                "max_cpc": max_cpc,
                "quality_score": quality_score,
                # 三个 QS 子分项与整体 QS 相关。
                "expected_ctr":     _qs_subcomponent_for(quality_score),
                "ad_relevance":     _qs_subcomponent_for(quality_score),
                "landing_page_exp": _qs_subcomponent_for(quality_score),
                "first_page_cpc": round(max_cpc * 0.6, 2),
                "top_of_page_cpc": round(max_cpc * 1.2, 2),
                "created_at": row["created_at"],
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_text_ad(ad_group_df: pl.DataFrame, campaign_df: pl.DataFrame,
                advertiser_df: pl.DataFrame, industry_df: pl.DataFrame) -> pl.DataFrame:
    records = []
    record_id = 1
    adgroup_to_campaign = {r["id"]: r["campaign_id"] for r in ad_group_df.iter_rows(named=True)}
    campaign_to_adv = {r["id"]: r["advertiser_id"] for r in campaign_df.iter_rows(named=True)}
    adv_to_industry = {r["id"]: r["industry_id"] for r in advertiser_df.iter_rows(named=True)}
    industry_names = {r["id"]: r["name"] for r in industry_df.iter_rows(named=True)}

    headline_1_templates = [
        "Top-Rated {industry}",
        "Save Big on {industry}",
        "{industry} - Free Shipping",
        "Trusted {industry} Brand",
        "Compare {industry} Deals",
        "{industry} You Can Trust",
        "Best-in-Class {industry}",
        "Discover {industry} Today",
    ]
    headline_2_templates = [
        "Trusted Brand. Verified Reviews.",
        "Award-Winning Customer Service",
        "Backed by 100% Money-Back Guarantee",
        "Fast Delivery. Easy Returns.",
        "5-Star Rated. 50K+ Happy Customers.",
        "Free Trial. No Credit Card Needed.",
        "Industry-Leading Quality Since 1998",
    ]
    headline_3_templates = [
        "Get Started Today",
        "Compare Plans Now",
        "Claim Your Discount",
        "Get an Instant Quote",
        "Book Your Free Consultation",
        "Try Risk-Free for 30 Days",
        None,
    ]
    description_1_templates = [
        "Trusted by 1M+ customers. Shop our deals today and save up to 40%.",
        "Free returns. Fast shipping. Backed by our 100-day guarantee.",
        "Award-winning service. Compare options and find your perfect fit.",
        "Get an instant quote. No credit card required. Cancel anytime.",
        "Top-rated nationwide. Expert support 7 days a week.",
        "Save 25% when you sign up today. Limited-time offer.",
    ]
    description_2_templates = [
        "Free 30-day trial. No hidden fees.",
        "Talk to a specialist now — no commitment.",
        "Bundle and save up to 35% on multiple plans.",
        "Same-day approval available for qualifying customers.",
        "Backed by our best-price guarantee.",
        None,
    ]

    for row in ad_group_df.iter_rows(named=True):
        agp_id = row["id"]
        adv_id = campaign_to_adv[adgroup_to_campaign[agp_id]]
        industry_name = industry_names[adv_to_industry[adv_id]]
        industry_short = industry_name.split(" &")[0].split(" ")[0]
        num_ads = random.randint(2, 4)
        for _ in range(num_ads):
            records.append({
                "id": record_id,
                "ad_code": f"AD_{str(record_id).zfill(6)}",
                "ad_group_id": agp_id,
                "headline_1": random.choice(headline_1_templates).format(industry=industry_short),
                "headline_2": random.choice(headline_2_templates),
                "headline_3": random.choice(headline_3_templates),
                "description_1": random.choice(description_1_templates),
                "description_2": random.choice(description_2_templates),
                "final_url": f"https://www.advertiser{adv_id}.com/landing",
                "display_url": f"www.advertiser{adv_id}.com",
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[75, 20, 5])[0],
                "quality_score": random.choices(
                    [4, 5, 6, 7, 8, 9, 10],
                    weights=[5, 10, 20, 30, 20, 10, 5],
                )[0],
                "created_at": row["created_at"],
            })
            record_id += 1
    return pl.DataFrame(records)


# 在真实的 Floodlight 默认设置中 Last Click 占主导；Data Driven 的采用率
# 在增长但仍是少数。这些数字是为教学目的而设的示意值。
ATTRIBUTION_MODEL_WEIGHTS = [45, 10, 10, 10, 10, 15]  # 对应 ATTRIBUTION_MODELS


def gen_floodlight_tag(advertiser_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1
    for adv_id in advertiser_ids:
        num_tags = random.randint(2, 5)
        conv_types = random.sample(CONVERSION_TYPES, k=min(num_tags, len(CONVERSION_TYPES)))
        for conv_type in conv_types:
            records.append({
                "id": record_id,
                "tag_code": f"FL_{str(record_id).zfill(4)}",
                "advertiser_id": adv_id,
                "tag_name": f"{conv_type} Tracking - Adv {adv_id}",
                "conversion_type": conv_type,
                "counting_method": random.choices(["Standard", "Unique"], weights=[80, 20])[0],
                "attribution_model": random.choices(
                    ATTRIBUTION_MODELS, weights=ATTRIBUTION_MODEL_WEIGHTS
                )[0],
                "lookback_window": random.choices(
                    [7, 14, 30, 60, 90], weights=[15, 25, 35, 15, 10]
                )[0],
                "status": random.choices(["Active", "Paused"], weights=[95, 5])[0],
                "created_at": fake.date_time_between(start_date=f"-{DAYS_18M}d", end_date=f"-{DAYS_6M}d").isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


# ============================================================================
# 生成函数 —— 事实表
# ============================================================================
def _budget_lookup(campaign_budget_df: pl.DataFrame) -> Dict[int, List[tuple]]:
    """将 campaign_id 映射到按序排列的 (effective_date, daily_budget) 元组列表。"""
    out: Dict[int, List[tuple]] = {}
    for row in campaign_budget_df.iter_rows(named=True):
        out.setdefault(row["campaign_id"], []).append(
            (date.fromisoformat(row["effective_date"]), row["daily_budget"])
        )
    for cmp_id in out:
        out[cmp_id].sort(key=lambda x: x[0])
    return out


def _budget_on_date(budgets: List[tuple], d: date) -> Optional[float]:
    """返回日期 d 当天生效的 daily_budget（满足 effective_date <= d 的最新一条）。"""
    chosen = None
    for eff_date, budget in budgets:
        if eff_date <= d:
            chosen = budget
        else:
            break
    return chosen


def gen_daily_stats(campaign_df: pl.DataFrame, campaign_budget_df: pl.DataFrame,
                    device_df: pl.DataFrame, engine_account_df: pl.DataFrame,
                    advertiser_df: pl.DataFrame, industry_df: pl.DataFrame,
                    window_days: int = 90) -> pl.DataFrame:
    """在 [today - window_days, today] 与该 campaign 的有效窗口
    [start_date, end_date or today] 的交集内，为每个
    (campaign, report_date, device) 组合生成一行。

    在基础的 impression / CTR / conversion-rate 采样之上叠加的分布锚点:

    * 设备 —— Mobile 承载最多的 impressions；Desktop 的转化率
      更高；Tablet 远远落后排第三（`DEVICE_*_SCALE` 常量）。
    * 引擎 —— Microsoft Advertising 的 CPC 更低、conversion rate 也比
      Google Ads 略低（`ENGINE_*_SCALE` 常量）。
    * 行业 —— 平均 conversion value 从各行业的范围
      （`INDUSTRY_CONV_VALUE_RANGE`）中采样: Financial Services / Insurance /
      Real Estate 偏高，restaurants 偏低。

    当 cost 接近当时生效的 budget 时，``lost_is_budget`` 会向上偏置。
    ``search_*_is`` 列在非 Search campaign 上为 NULL
    （真实的 SA360 不会暴露它们）。"""
    records = []
    record_id = 1
    today = date.today()
    window_start = today - timedelta(days=window_days)
    budgets_by_campaign = _budget_lookup(campaign_budget_df)

    # 用于差异化的查找表。
    device_id_to_name = {r["id"]: r["name"] for r in device_df.iter_rows(named=True)}
    engine_id_to_type = {r["id"]: r["engine_type"] for r in engine_account_df.iter_rows(named=True)}
    advertiser_to_industry = {r["id"]: r["industry_id"] for r in advertiser_df.iter_rows(named=True)}
    industry_id_to_name = {r["id"]: r["name"] for r in industry_df.iter_rows(named=True)}

    device_ids = device_df["id"].to_list()

    for row in campaign_df.iter_rows(named=True):
        cmp_id = row["id"]
        cmp_type = row["campaign_type"]
        is_search = cmp_type == "Search"
        cmp_start = date.fromisoformat(row["start_date"])
        cmp_end = date.fromisoformat(row["end_date"]) if row["end_date"] else today
        first_day = max(cmp_start, window_start)
        last_day = min(cmp_end, today)
        if first_day > last_day:
            continue

        engine_type = engine_id_to_type[row["engine_account_id"]]
        industry_name = industry_id_to_name[advertiser_to_industry[row["advertiser_id"]]]
        engine_cpc_mult = ENGINE_CPC_SCALE[engine_type]
        engine_conv_rate_mult = ENGINE_CONV_RATE_SCALE[engine_type]
        conv_value_lo, conv_value_hi = INDUSTRY_CONV_VALUE_RANGE[industry_name]

        budgets = budgets_by_campaign.get(cmp_id, [])

        current = first_day
        while current <= last_day:
            daily_budget = _budget_on_date(budgets, current) or 1000.0
            for device_id in device_ids:
                device_name = device_id_to_name[device_id]
                impression_mult = DEVICE_IMPRESSION_SCALE[device_name]
                conv_rate_mult_device = DEVICE_CONV_RATE_SCALE[device_name]
                # 在基础采样之上应用设备 impression 乘数，使 Mobile 平均
                # 约为 Tablet 的 6 倍。
                base_impressions = random.randint(100, 50000)
                impressions = max(1, int(base_impressions * impression_mult))
                # 贴近真实的 Search CTR: 通常 1-6%，brand 词偶尔更高
                ctr = random.choices(
                    [random.uniform(0.005, 0.02), random.uniform(0.02, 0.06),
                     random.uniform(0.06, 0.12)],
                    weights=[55, 35, 10],
                )[0]
                clicks = int(impressions * ctr)
                # CPC 乘以引擎的缩放系数（Microsoft 的成交价比 Google 便宜）。
                avg_cpc = round(random.uniform(0.5, 12) * engine_cpc_mult, 2)
                cost = round(clicks * avg_cpc, 2)

                # Conversion rate = 基础转化率 × 设备缩放 × 引擎缩放:
                # Desktop 的转化约为 Mobile 的 2 倍，在其他条件相同的行上
                # Google 的转化比 Microsoft 高约 13%。
                conv_rate = (
                    random.uniform(0.005, 0.08)
                    * conv_rate_mult_device
                    * engine_conv_rate_mult
                )
                conversions = round(clicks * conv_rate, 2)
                avg_conv_value = round(random.uniform(conv_value_lo, conv_value_hi), 2)
                conversion_value = round(conversions * avg_conv_value, 2)

                cpa = round(cost / conversions, 2) if conversions > 0 else None
                roas = round(conversion_value / cost, 2) if cost > 0 else None

                # impression-share 的分解，满足 abs_top <= top <= search
                impr_share = round(random.uniform(25, 95), 1)
                # P1-7: cost 与 budget 的压力会让 lost_is_budget 向上偏置
                budget_pressure = cost / daily_budget if daily_budget > 0 else 0
                if budget_pressure > 0.8:
                    base = random.uniform(8, 28)
                    lost_budget_max = max(2.0, 100 - impr_share)
                    lost_budget = round(min(base * 1.7, lost_budget_max), 1)
                else:
                    lost_budget = round(
                        random.uniform(0, max(2.0, min(20.0, 100 - impr_share))), 1
                    )
                lost_rank = round(max(0.0, 100 - impr_share - lost_budget), 1)

                if is_search:
                    search_top_is = round(impr_share * random.uniform(0.55, 0.95), 1)
                    search_abs_top_is = round(search_top_is * random.uniform(0.4, 0.85), 1)
                    search_impr_share = impr_share
                else:
                    search_top_is = None
                    search_abs_top_is = None
                    search_impr_share = None

                records.append({
                    "id": record_id,
                    "campaign_id": cmp_id,
                    "report_date": current.isoformat(),
                    "device_id": device_id,
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": cost,
                    "conversions": conversions,
                    "conversion_value": conversion_value,
                    "ctr": round(ctr, 4),
                    "avg_cpc": avg_cpc,
                    "cpa": cpa,
                    "roas": roas,
                    "impression_share": impr_share,
                    "search_impr_share": search_impr_share,
                    "lost_is_budget": lost_budget,
                    "lost_is_rank": lost_rank,
                    "search_abs_top_is": search_abs_top_is,
                    "search_top_is": search_top_is,
                })
                record_id += 1
            current += timedelta(days=1)

    return pl.DataFrame(records)


def gen_conversion(advertiser_ids: List[int], floodlight_df: pl.DataFrame,
                   n: int = 5000) -> pl.DataFrame:
    records = []
    adv_to_tags: Dict[int, List[int]] = {}
    for row in floodlight_df.iter_rows(named=True):
        adv_to_tags.setdefault(row["advertiser_id"], []).append(row["id"])

    for i in range(1, n + 1):
        adv_id = random.choice(advertiser_ids)
        tags = adv_to_tags.get(adv_id, [])
        if not tags:
            continue
        records.append({
            "id": i,
            "conversion_code": f"CONV_{str(i).zfill(6)}",
            "advertiser_id": adv_id,
            "floodlight_tag_id": random.choice(tags),
            "conversion_time": fake.date_time_between(start_date="-90d", end_date="now").isoformat(),
            "conversion_value": round(random.uniform(50, 2000), 2),
            "currency": "USD",
            "quantity": random.randint(1, 5),
        })
    return pl.DataFrame(records)


def _build_advertiser_hierarchy(campaign_df: pl.DataFrame, ad_group_df: pl.DataFrame,
                                keyword_df: pl.DataFrame) -> Dict[int, Dict[int, Dict[int, List[int]]]]:
    """返回 {advertiser_id: {campaign_id: {ad_group_id: [keyword_id, ...]}}}。

    这是 ``gen_attribution_path`` 使用的主索引，确保 touchpoint
    只引用属于该 conversion 自身 advertiser 的实体
    （P0-1 from review）。
    """
    campaign_to_adv = {r["id"]: r["advertiser_id"] for r in campaign_df.iter_rows(named=True)}
    adgroup_to_campaign = {r["id"]: r["campaign_id"] for r in ad_group_df.iter_rows(named=True)}

    hierarchy: Dict[int, Dict[int, Dict[int, List[int]]]] = {}
    for row in ad_group_df.iter_rows(named=True):
        adgroup_id = row["id"]
        campaign_id = row["campaign_id"]
        adv_id = campaign_to_adv[campaign_id]
        hierarchy.setdefault(adv_id, {}).setdefault(campaign_id, {})[adgroup_id] = []

    for row in keyword_df.iter_rows(named=True):
        kw_id = row["id"]
        adgroup_id = row["ad_group_id"]
        campaign_id = adgroup_to_campaign[adgroup_id]
        adv_id = campaign_to_adv[campaign_id]
        hierarchy[adv_id][campaign_id][adgroup_id].append(kw_id)
    return hierarchy


# 路径长度分布偏向短路径（截断几何分布）。
PATH_LENGTHS    = [2, 3, 4, 5, 6]
PATH_LENGTH_WEIGHTS = [40, 30, 15, 10, 5]

# 按 touchpoint 位置划分的渠道权重。Display / Paid Social 偏向 first
# touch（上漏斗）；Paid Search / Direct 偏向 last touch（下漏斗）。
# 顺序与 CHANNELS 常量一致: [Paid Search, Display, Paid Social,
# Email, Direct, Organic Search]。
CHANNEL_WEIGHTS_FIRST = [10, 30, 25, 10,  5, 20]
CHANNEL_WEIGHTS_MID   = [20, 20, 20, 10, 10, 20]
CHANNEL_WEIGHTS_LAST  = [35,  5,  5, 10, 30, 15]


def _position_credits(num_touchpoints: int) -> List[float]:
    """Position-Based 归因: first 占 40%，last 占 40%，剩余 20% 分摊给
    中间的 touchpoint。N=2 时没有中间触点，因此按 Google Ads 的惯例把
    credit 在 first 和 last 之间平均分配（50/50）—— 这是相对于此前
    (0.4, 0.4) bug（导致 credit 之和只有 0.8）的 P0 修复。"""
    if num_touchpoints == 2:
        return [0.5, 0.5]
    credits = []
    middle_per_touch = 0.2 / (num_touchpoints - 2)
    for i in range(num_touchpoints):
        if i == 0 or i == num_touchpoints - 1:
            credits.append(0.4)
        else:
            credits.append(middle_per_touch)
    return credits


def gen_attribution_path(conversion_df: pl.DataFrame, floodlight_df: pl.DataFrame,
                         campaign_df: pl.DataFrame, ad_group_df: pl.DataFrame,
                         keyword_df: pl.DataFrame, channel_ids: List[int]) -> pl.DataFrame:
    """生成满足 review 要求的不变量的 touchpoint:

    * Touchpoint 保持在该 conversion 所属 advertiser 的子树内（P0-1）。
    * ``touchpoint_order=1`` 是时间上最早的触点（P0-2）: 采样 N 个
      ``hours_before_conv`` 值，降序排序，再分配 order。
    * ``hours_before_conv <= floodlight_tag.lookback_window * 24``（P1-5）。
    * 对每个 N（包括 N=2），position credit 之和都为 1.0（Review 2 P0）。
    * 渠道占比按位置偏置: first touch 偏向 Display /
      Social，last touch 偏向 Paid Search / Direct（Review 2 P1）。
    """
    records = []
    record_id = 1
    hierarchy = _build_advertiser_hierarchy(campaign_df, ad_group_df, keyword_df)
    tag_to_lookback = {r["id"]: r["lookback_window"]
                       for r in floodlight_df.iter_rows(named=True)}

    for row in conversion_df.iter_rows(named=True):
        conv_id = row["id"]
        adv_id = row["advertiser_id"]
        conv_time = datetime.fromisoformat(row["conversion_time"])
        lookback_days = tag_to_lookback[row["floodlight_tag_id"]]
        max_hours = lookback_days * 24

        subtree = hierarchy.get(adv_id, {})
        adv_campaign_ids = list(subtree.keys())
        if not adv_campaign_ids:
            continue

        num_touchpoints = random.choices(
            PATH_LENGTHS, weights=PATH_LENGTH_WEIGHTS
        )[0]

        # 时间顺序排列: 选取 N 个 hours_before 值并降序排序，使
        # hours_before 最大（时间上最早）的那一行成为
        # touchpoint_order = 1。
        hours_before_list = sorted(
            [random.randint(1, max_hours) for _ in range(num_touchpoints)],
            reverse=True,
        )

        # 归因 credit --------------------------------------------------------
        last_click = [0.0] * num_touchpoints
        last_click[-1] = 1.0
        first_click = [0.0] * num_touchpoints
        first_click[0] = 1.0
        linear = [1.0 / num_touchpoints] * num_touchpoints
        decay_sum = sum(2 ** i for i in range(num_touchpoints))
        time_decay = [2 ** i / decay_sum for i in range(num_touchpoints)]
        position = _position_credits(num_touchpoints)
        dd = [random.uniform(0.1, 0.4) for _ in range(num_touchpoints)]
        dd_sum = sum(dd)
        data_driven = [c / dd_sum for c in dd]

        for tp_order in range(1, num_touchpoints + 1):
            hours_before = hours_before_list[tp_order - 1]
            days_before = hours_before // 24
            interaction_time = conv_time - timedelta(hours=hours_before)

            # 渠道占比取决于该 touchpoint 在路径中的位置。
            if tp_order == 1:
                channel_weights = CHANNEL_WEIGHTS_FIRST
            elif tp_order == num_touchpoints:
                channel_weights = CHANNEL_WEIGHTS_LAST
            else:
                channel_weights = CHANNEL_WEIGHTS_MID
            channel_id = random.choices(channel_ids, weights=channel_weights)[0]

            # 严格在该 advertiser 的子树内挑选 campaign/ad_group/keyword。
            # 每一层都可能为 None（仅 impression / display 类的触点）。
            campaign_id = random.choice(adv_campaign_ids) if random.random() < 0.85 else None
            ad_group_id = None
            keyword_id = None
            if campaign_id is not None:
                groups = list(subtree[campaign_id].keys())
                if groups and random.random() < 0.75:
                    ad_group_id = random.choice(groups)
                    keywords = subtree[campaign_id][ad_group_id]
                    if keywords and random.random() < 0.65:
                        keyword_id = random.choice(keywords)

            records.append({
                "id": record_id,
                "conversion_id": conv_id,
                "advertiser_id": adv_id,
                "touchpoint_order": tp_order,
                "channel_id": channel_id,
                "campaign_id": campaign_id,
                "ad_group_id": ad_group_id,
                "keyword_id": keyword_id,
                "interaction_type": random.choices(INTERACTION_TYPES, weights=INTERACTION_TYPE_WEIGHTS)[0],
                "interaction_time": interaction_time.isoformat(),
                "days_before_conv": days_before,
                "hours_before_conv": hours_before,
                "last_click_credit": round(last_click[tp_order - 1], 4),
                "first_click_credit": round(first_click[tp_order - 1], 4),
                "linear_credit": round(linear[tp_order - 1], 4),
                "time_decay_credit": round(time_decay[tp_order - 1], 4),
                "position_credit": round(position[tp_order - 1], 4),
                "data_driven_credit": round(data_driven[tp_order - 1], 4),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_search_term_report(keyword_df: pl.DataFrame, ad_group_df: pl.DataFrame,
                           campaign_df: pl.DataFrame, window_days: int = 30) -> pl.DataFrame:
    """按 keyword 分层的采样: 每个 keyword 在窗口内约 5 个随机日期上，
    每天获得约 1-2 个 search term。无全局上限；各 keyword 的覆盖是均匀的
    （P1-8 from review）。

    约 15% 的行 keyword_id 为 NULL（broad-match 溢出: 没有直接匹配到
    某个已存储 keyword 的 search-term impression）。campaign/
    ad_group 列仍会解析到产生该 impression 的源 ad_group。
    """
    records = []
    record_id = 1
    today = date.today()
    window_start = today - timedelta(days=window_days)

    suffixes = [
        " near me", " online", " best", " cheap", " reviews",
        " 2026", " price", " comparison", " coupons", " deals",
    ]

    adgroup_to_campaign = {r["id"]: r["campaign_id"] for r in ad_group_df.iter_rows(named=True)}

    keyword_rows = list(keyword_df.iter_rows(named=True))
    days_per_keyword = 5
    terms_per_day = (1, 2)

    for row in keyword_rows:
        kw_id = row["id"]
        kw_text = row["keyword_text"]
        agp_id = row["ad_group_id"]
        cmp_id = adgroup_to_campaign[agp_id]

        # 从窗口中随机选取一小部分日期，使覆盖是分层的，同时避免对
        # 约 4 万个 keyword 撑爆磁盘。
        sampled_days = random.sample(
            range(window_days + 1),
            k=min(days_per_keyword, window_days + 1),
        )
        for day_offset in sampled_days:
            current = window_start + timedelta(days=day_offset)
            num_terms = random.randint(*terms_per_day)
            for _ in range(num_terms):
                # 50% 与 keyword 文本完全匹配，50% 带一个长尾后缀
                if random.random() < 0.5:
                    search_term = kw_text
                else:
                    search_term = kw_text + random.choice(suffixes)
                # 约 15% 的 keyword_id 为 NULL（broad-match 溢出）
                emit_keyword_id = kw_id if random.random() < 0.85 else None

                impressions = random.randint(1, 500)
                clicks = int(impressions * random.uniform(0.005, 0.10))
                cost = round(clicks * random.uniform(0.5, 8), 2)
                conversions = round(clicks * random.uniform(0, 0.08), 2)
                conversion_value = round(conversions * random.uniform(40, 300), 2)
                records.append({
                    "id": record_id,
                    "report_date": current.isoformat(),
                    "campaign_id": cmp_id,
                    "ad_group_id": agp_id,
                    "keyword_id": emit_keyword_id,
                    "search_term": search_term,
                    "match_type_used": random.choices(
                        [m["name"] for m in MATCH_TYPES], weights=[40, 35, 25],
                    )[0],
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": cost,
                    "conversions": conversions,
                    "conversion_value": conversion_value,
                    "added_excluded": random.choices(
                        [None, "Added", "Excluded"], weights=[80, 15, 5],
                    )[0],
                })
                record_id += 1
    return pl.DataFrame(records)


# ============================================================================
# 编排
# ============================================================================
def generate_all_tsv() -> Dict[str, List[int]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating dimension tables...")
    df_industry = gen_industry()
    df_industry.write_csv(DATA_DIR / "01_industry.tsv", separator="\t")

    df_region = gen_region()
    df_region.write_csv(DATA_DIR / "02_region.tsv", separator="\t")

    df_bid_strategy_type = gen_bid_strategy_type()
    df_bid_strategy_type.write_csv(DATA_DIR / "03_bid_strategy_type.tsv", separator="\t")

    df_match_type = gen_match_type()
    df_match_type.write_csv(DATA_DIR / "04_match_type.tsv", separator="\t")

    df_device = gen_device()
    df_device.write_csv(DATA_DIR / "05_device.tsv", separator="\t")

    df_channel = gen_channel()
    df_channel.write_csv(DATA_DIR / "06_channel.tsv", separator="\t")

    print("Generating agencies and advertisers...")
    df_agency = gen_agency(df_region["id"].to_list(), n=15)
    df_agency.write_csv(DATA_DIR / "07_agency.tsv", separator="\t")

    df_advertiser = gen_advertiser(df_industry["id"].to_list(), n=80)
    df_advertiser.write_csv(DATA_DIR / "08_advertiser.tsv", separator="\t")
    advertiser_ids = df_advertiser["id"].to_list()

    df_agency_client = gen_agency_client(df_agency, df_advertiser)
    df_agency_client.write_csv(DATA_DIR / "09_agency_client.tsv", separator="\t")

    print("Generating account structure...")
    df_engine_account = gen_engine_account(advertiser_ids)
    df_engine_account.write_csv(DATA_DIR / "10_engine_account.tsv", separator="\t")

    df_bid_strategy = gen_bid_strategy(advertiser_ids, df_bid_strategy_type)
    df_bid_strategy.write_csv(DATA_DIR / "11_bid_strategy.tsv", separator="\t")

    df_campaign = gen_campaign(advertiser_ids, df_engine_account, df_bid_strategy,
                               df_advertiser, df_industry)
    df_campaign.write_csv(DATA_DIR / "12_campaign.tsv", separator="\t")
    campaign_ids = df_campaign["id"].to_list()

    df_campaign_budget = gen_campaign_budget(df_campaign, df_advertiser)
    df_campaign_budget.write_csv(DATA_DIR / "13_campaign_budget.tsv", separator="\t")

    df_ad_group = gen_ad_group(df_campaign, df_advertiser, df_industry)
    df_ad_group.write_csv(DATA_DIR / "14_ad_group.tsv", separator="\t")

    df_keyword = gen_keyword(df_ad_group, df_campaign, df_advertiser, df_industry,
                             df_match_type["id"].to_list())
    df_keyword.write_csv(DATA_DIR / "15_keyword.tsv", separator="\t")

    df_text_ad = gen_text_ad(df_ad_group, df_campaign, df_advertiser, df_industry)
    df_text_ad.write_csv(DATA_DIR / "16_text_ad.tsv", separator="\t")

    df_floodlight = gen_floodlight_tag(advertiser_ids)
    df_floodlight.write_csv(DATA_DIR / "17_floodlight_tag.tsv", separator="\t")

    print("Generating daily stats (largest table, may take a minute)...")
    df_daily_stats = gen_daily_stats(
        df_campaign, df_campaign_budget,
        df_device, df_engine_account, df_advertiser, df_industry,
        window_days=90,
    )
    df_daily_stats.write_csv(DATA_DIR / "18_daily_stats.tsv", separator="\t")

    print("Generating conversions and attribution paths...")
    df_conversion = gen_conversion(advertiser_ids, df_floodlight, n=5000)
    df_conversion.write_csv(DATA_DIR / "19_conversion.tsv", separator="\t")

    df_attribution = gen_attribution_path(df_conversion, df_floodlight, df_campaign,
                                          df_ad_group, df_keyword,
                                          df_channel["id"].to_list())
    df_attribution.write_csv(DATA_DIR / "20_attribution_path.tsv", separator="\t")

    print("Generating search-term report...")
    df_search_term = gen_search_term_report(df_keyword, df_ad_group, df_campaign,
                                            window_days=30)
    df_search_term.write_csv(DATA_DIR / "21_search_term_report.tsv", separator="\t")

    print(f"All TSVs written to {DATA_DIR}")
    return {"advertiser_ids": advertiser_ids, "campaign_ids": campaign_ids}


# ============================================================================
# SQLite 加载器
# ============================================================================
BOOLEAN_COLUMNS = {
    "is_active": True,
    "is_automated": True,
}

DATETIME_COLUMNS = {"created_at", "last_modified", "conversion_time", "interaction_time"}
DATE_COLUMNS = {"report_date", "start_date", "end_date",
                "contract_start", "contract_end", "effective_date"}


def coerce_row(row: dict) -> dict:
    """解析 date/datetime 字符串，并把整数 0/1 转换为 Python bool。"""
    out = {}
    for k, v in row.items():
        if v is None:
            continue
        if k in BOOLEAN_COLUMNS:
            if isinstance(v, bool):
                out[k] = v
            elif isinstance(v, (int, float)):
                out[k] = bool(int(v))
            elif isinstance(v, str):
                out[k] = v.strip().lower() in ("1", "true", "t", "yes")
            else:
                out[k] = bool(v)
            continue
        if k in DATETIME_COLUMNS and isinstance(v, str):
            try:
                out[k] = datetime.fromisoformat(v)
                continue
            except ValueError:
                pass
        if k in DATE_COLUMNS and isinstance(v, str):
            try:
                out[k] = date.fromisoformat(v)
                continue
            except ValueError:
                pass
        out[k] = v
    return out


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    table_model_map = [
        ("01_industry.tsv", Industry),
        ("02_region.tsv", Region),
        ("03_bid_strategy_type.tsv", BidStrategyType),
        ("04_match_type.tsv", MatchType),
        ("05_device.tsv", Device),
        ("06_channel.tsv", Channel),
        ("07_agency.tsv", Agency),
        ("08_advertiser.tsv", Advertiser),
        ("09_agency_client.tsv", AgencyClient),
        ("10_engine_account.tsv", EngineAccount),
        ("11_bid_strategy.tsv", BidStrategy),
        ("12_campaign.tsv", Campaign),
        ("13_campaign_budget.tsv", CampaignBudget),
        ("14_ad_group.tsv", AdGroup),
        ("15_keyword.tsv", Keyword),
        ("16_text_ad.tsv", TextAd),
        ("17_floodlight_tag.tsv", FloodlightTag),
        ("18_daily_stats.tsv", DailyStats),
        ("19_conversion.tsv", Conversion),
        ("20_attribution_path.tsv", AttributionPath),
        ("21_search_term_report.tsv", SearchTermReport),
    ]

    with Session(engine) as session:
        for tsv_file, model in table_model_map:
            print(f"Loading {tsv_file}...")
            df = pl.read_csv(DATA_DIR / tsv_file, separator="\t",
                             null_values=["", "null"], infer_schema_length=10000)
            for row in df.iter_rows(named=True):
                session.add(model(**coerce_row(row)))
            session.flush()
        session.commit()

    # 参考日期视图: 所有按时间窗口查询的锚点（P0-4）。
    with engine.connect() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_reference_date"))
        conn.execute(text(
            "CREATE VIEW v_reference_date AS "
            "SELECT MAX(report_date) AS reference_date FROM daily_stats"
        ))
        conn.commit()
    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("=" * 60)
    print("Search Advertising Attribution Agent — Data Generator")
    print("=" * 60)
    generate_all_tsv()
    create_sqlite_database()
    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
