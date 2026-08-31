"""
Search Ads 360 智能分析 Agent - 假数据生成器
复杂度: Large (21 张表, ~1,000,000 行)
生成方: Fake Data Generator Agent

业务背景:
本数据集模拟 Lumenly Ads —— 一个虚构的跨引擎搜索广告聚合管理平台
(对标 Google Search Ads 360 / Meta Ads Manager),为 data analyst / BI analyst
提供训练环境;数据集的下游应用是 LLM Agent 自动化执行人类产出的优化规则。

详细业务背景请见:
    01-search_ads_360_agent_large_business_context-cn.md
详细 schema 文档 (表结构 / 约束 / 生成规则 / DDL) 请见:
    02-search_ads_360_agent_large_er_document-cn.md

参考"今天" = 2026-06-01
"""

from __future__ import annotations
import os
import shutil
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Callable, List, Optional, Dict, Tuple
import random

import polars as pl
from faker import Faker
from sqlalchemy import (
    create_engine, ForeignKey, String, Integer, Float, DateTime,
    Boolean, Text, Date,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "search_ads_360_agent_large.sqlite"

FAKER_LOCALE = "zh_CN"
RANDOM_SEED = 42

# 时间参考
TODAY = date(2026, 6, 1)
HISTORY_START = TODAY - timedelta(days=540)        # 回溯 18 个月
DAILY_STATS_DAYS = 120                              # daily_stats 覆盖天数
SEARCH_TERM_DAYS = 30                               # search_term_report 覆盖天数
CONVERSION_LOOKBACK_DAYS = 90                       # conversion 时间窗

# 规模配置
N_AGENCY = 25
N_ADVERTISER = 150
N_CONVERSION = 25_000
MAX_SEARCH_TERM_ROWS = 200_000                      # 硬上限

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


def _dt(d: date, h: int = 0, m: int = 0) -> datetime:
    """辅助函数: 把 date 转换为指定时 / 分的 datetime。"""
    return datetime(d.year, d.month, d.day, h, m, 0)


def random_date_between(start: date, end: date) -> date:
    """在 [start, end] 闭区间内均匀随机取一个 date。"""
    if start > end:
        start, end = end, start
    days = (end - start).days
    return start + timedelta(days=random.randint(0, days))


def random_datetime_between(start: datetime, end: datetime) -> datetime:
    """在 [start, end] 区间内均匀随机取一个 datetime。"""
    if start > end:
        start, end = end, start
    delta_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(delta_seconds, 1)))


def weighted_sample_no_replace(items: List, weights: List[float], k: int) -> List:
    """按权重做不放回抽样 (用于 engine_type 的 35/40/15/10 分布)。"""
    items = list(items)
    weights = list(weights)
    chosen: List = []
    for _ in range(min(k, len(items))):
        idx = random.choices(range(len(items)), weights=weights)[0]
        chosen.append(items.pop(idx))
        weights.pop(idx)
    return chosen


# ============================================================================
# 业务常量
# ============================================================================
INDUSTRIES = ["电商零售", "教育培训", "金融服务", "旅游出行", "本地生活",
              "游戏娱乐", "医疗健康", "房产家居", "汽车交通", "B2B企业服务"]
COMPANY_SIZES = ["SMB", "Mid-Market", "Enterprise"]
MONTHLY_SPEND_TIERS = ["<10K", "10K-50K", "50K-200K", ">200K"]
PRIMARY_GOALS = ["品牌曝光", "获客引流", "销售转化", "App下载"]
REGIONS = ["华东", "华北", "华南", "华中", "西南", "西北", "东北"]
AGENCY_TIERS = ["Gold", "Silver", "Bronze", "Standard"]

CAMPAIGN_TYPES = ["Search", "Shopping", "Display", "Video", "App"]
CAMPAIGN_SUBTYPES = ["Standard", "Smart", "Performance Max"]
BID_STRATEGY_TYPES = [
    "Manual CPC",
    "Enhanced CPC",
    "Target CPA",
    "Target ROAS",
    "Maximize Conversions",
    "Maximize Conversion Value",
    "Maximize Clicks",
    "Target Impression Share",
]

MATCH_TYPES = ["EXACT", "PHRASE", "BROAD"]
DEVICES = ["Mobile", "Desktop", "Tablet"]
CHANNELS = ["Paid Search", "Display", "Social", "Email", "Direct", "Organic Search"]
INTERACTION_TYPES = ["Click", "Impression", "View"]
CONVERSION_TYPES = ["Purchase", "Lead", "Signup", "PageView", "AddToCart", "AppInstall"]

# 搜索词长尾构造词库: 真实搜索词报告是海量长尾、大量唯一词。
# 用 地名 + 多样修饰词 与种子关键词自由拼接, 把 search_term 空间从 ~1,540 撑到百万级,
# 使绝大多数 search_term 低频甚至唯一 → "高花费零转化否定词候选"等查询能真正命中。
SEARCH_TERM_GEO = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆",
    "苏州", "天津", "郑州", "长沙", "青岛", "东莞", "宁波", "佛山", "合肥", "昆明",
    "沈阳", "济南", "无锡", "厦门", "福州", "华东", "华南", "华北", "本地", "附近",
]
SEARCH_TERM_QUALIFIERS = [
    "价格", "多少钱", "哪家好", "怎么样", "推荐", "排名", "官网", "电话", "地址", "附近",
    "哪个好", "排行榜", "免费", "官方", "报价", "评价", "优惠", "最新", "教程", "对比",
    "哪里有", "靠谱吗", "费用", "套餐", "活动", "2025", "2026", "上门", "正规", "十大",
    "口碑", "预约", "咨询", "加盟", "攻略", "专业", "品牌", "旗舰店", "怎么选", "注意事项",
]

# 中文公司名组件
COMPANY_PREFIXES = ["华", "中", "新", "国", "东", "西", "南", "北",
                    "金", "银", "盛", "恒", "宏", "大", "万", "亿"]
COMPANY_MIDDLES = ["联", "通", "达", "创", "智", "信", "源", "辉",
                   "鑫", "泰", "安", "康", "美", "优", "佳", "利"]
COMPANY_SUFFIXES = ["科技", "网络", "电商", "商贸", "教育", "金融",
                    "传媒", "信息", "服务", "集团"]

# 中文关键词词库 (按行业)
KEYWORDS_BY_INDUSTRY: Dict[str, List[str]] = {
    "电商零售": [
        "网上购物", "优惠券", "折扣促销", "限时特价", "包邮", "正品保证",
        "双十一", "618大促", "品牌直营", "海淘代购", "母婴用品", "数码家电",
        "服装鞋帽", "美妆护肤", "家居生活", "生鲜水果",
    ],
    "教育培训": [
        "英语培训", "雅思托福", "考研辅导", "公务员培训", "职业技能",
        "在线课程", "K12教育", "少儿编程", "艺术培训", "留学申请",
        "MBA课程", "成人教育", "会计培训", "IT培训", "资格认证",
    ],
    "金融服务": [
        "贷款申请", "信用卡办理", "投资理财", "保险产品", "基金定投",
        "股票开户", "外汇交易", "P2P理财", "消费分期", "企业贷款",
        "房贷计算", "车贷利率", "信用评估", "财务规划",
    ],
    "旅游出行": [
        "机票预订", "酒店预订", "旅游攻略", "自由行", "跟团游",
        "签证办理", "租车服务", "景点门票", "度假村", "民宿推荐",
        "出境游", "国内游", "邮轮旅行", "亲子游", "蜜月旅行",
    ],
    "本地生活": [
        "外卖配送", "餐厅预订", "美食团购", "家政服务", "搬家公司",
        "装修设计", "婚庆策划", "宠物服务", "健身房", "美容美发",
        "洗衣服务", "维修服务", "月嫂保姆", "上门按摩",
    ],
    "游戏娱乐": [
        "手游下载", "游戏充值", "游戏攻略", "电竞比赛", "游戏代练",
        "VR游戏", "主机游戏", "网页游戏", "棋牌游戏", "休闲游戏",
        "游戏直播", "游戏周边", "游戏账号",
    ],
    "医疗健康": [
        "在线问诊", "预约挂号", "体检套餐", "药品购买", "医美整形",
        "口腔护理", "眼科医院", "中医养生", "心理咨询", "健康管理",
        "医疗器械", "保健品", "减肥产品",
    ],
    "房产家居": [
        "新房楼盘", "二手房源", "租房信息", "房价走势", "装修公司",
        "家具定制", "建材市场", "智能家居", "房产中介", "商铺出租",
        "写字楼", "公寓出售", "别墅豪宅",
    ],
    "汽车交通": [
        "新车报价", "二手车交易", "汽车保养", "驾校培训", "代驾服务",
        "汽车保险", "车贷计算", "汽车配件", "汽车改装", "网约车",
        "共享汽车", "电动汽车", "汽车维修",
    ],
    "B2B企业服务": [
        "企业软件", "云服务器", "办公系统", "CRM系统", "ERP软件",
        "企业培训", "法律顾问", "财务代理", "商标注册", "知识产权",
        "人力资源", "招聘服务", "会议系统", "数据中心",
    ],
}


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    pass


# ============= 维度表 =============

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


# ============= 组织 =============

class Agency(Base):
    __tablename__ = "agency"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    agency_name: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[int] = mapped_column(Integer, ForeignKey("region.id"), nullable=False)
    tier_level: Mapped[str] = mapped_column(String(20), nullable=False)
    account_manager: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Advertiser(Base):
    __tablename__ = "advertiser"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry_id: Mapped[int] = mapped_column(Integer, ForeignKey("industry.id"), nullable=False)
    sub_industry: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_size: Mapped[str] = mapped_column(String(20), nullable=False)
    monthly_spend_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_goal: Mapped[str] = mapped_column(String(50), nullable=False)
    website_url: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    account_status: Mapped[str] = mapped_column(String(20), nullable=False)
    lifetime_cost_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lifetime_conversion_value_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class AgencyClient(Base):
    __tablename__ = "agency_client"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_id: Mapped[int] = mapped_column(Integer, ForeignKey("agency.id"), nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    contract_start: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fee_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ============= 账户结构 =============

class EngineAccount(Base):
    __tablename__ = "engine_account"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
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
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("bid_strategy_type.id"), nullable=False)
    target_cpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_roas: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_cpc_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_impr_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impr_share_location: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Campaign(Base):
    __tablename__ = "campaign"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    engine_account_id: Mapped[int] = mapped_column(Integer, ForeignKey("engine_account.id"), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(30), nullable=False)
    campaign_subtype: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    bid_strategy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bid_strategy.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    targeting_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    targeting_language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    targeting_device: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lifetime_cost_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lifetime_conversions: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class CampaignBudget(Base):
    """历史化预算: 每 campaign 1-3 条带 effective_date_start / end。"""
    __tablename__ = "campaign_budget"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaign.id"), nullable=False)
    daily_budget: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_delivery: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_date_start: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AdGroup(Base):
    __tablename__ = "ad_group"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_group_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaign.id"), nullable=False)
    ad_group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Keyword(Base):
    __tablename__ = "keyword"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    ad_group_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_group.id"), nullable=False)
    keyword_text: Mapped[str] = mapped_column(String(300), nullable=False)
    match_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("match_type.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    max_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expected_ctr: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ad_relevance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    landing_page_exp: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    first_page_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top_of_page_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TextAd(Base):
    __tablename__ = "text_ad"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    ad_group_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_group.id"), nullable=False)
    headline_1: Mapped[str] = mapped_column(String(100), nullable=False)
    headline_2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    headline_3: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description_1: Mapped[str] = mapped_column(String(200), nullable=False)
    description_2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    final_url: Mapped[str] = mapped_column(String(500), nullable=False)
    display_url: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ============= 转化与归因 =============

class FloodlightTag(Base):
    __tablename__ = "floodlight_tag"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    conversion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    counting_method: Mapped[str] = mapped_column(String(30), nullable=False)
    attribution_model: Mapped[str] = mapped_column(String(30), nullable=False)
    lookback_window: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DailyStats(Base):
    __tablename__ = "daily_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    device_id: Mapped[int] = mapped_column(Integer, ForeignKey("device.id"), nullable=False)

    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    conversions: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False)

    ctr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roas: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    impression_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    search_impr_share: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_is_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_is_rank: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    search_abs_top_is: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    search_top_is: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Conversion(Base):
    __tablename__ = "conversion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversion_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    floodlight_tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("floodlight_tag.id"), nullable=False)
    conversion_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class AttributionPath(Base):
    __tablename__ = "attribution_path"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversion_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversion.id"), nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    touchpoint_order: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel.id"), nullable=False)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("campaign.id"), nullable=True)
    ad_group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("ad_group.id"), nullable=True)
    keyword_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("keyword.id"), nullable=True)
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
    """搜索词报告 — 新增 device_id"""
    __tablename__ = "search_term_report"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaign.id"), nullable=False)
    ad_group_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_group.id"), nullable=False)
    keyword_id: Mapped[int] = mapped_column(Integer, ForeignKey("keyword.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(Integer, ForeignKey("device.id"), nullable=False)
    search_term: Mapped[str] = mapped_column(String(500), nullable=False)
    match_type_used: Mapped[str] = mapped_column(String(20), nullable=False)

    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    conversions: Mapped[float] = mapped_column(Float, nullable=False)
    conversion_value: Mapped[float] = mapped_column(Float, nullable=False)

    added_excluded: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


# ============================================================================
# 数据生成函数
# ============================================================================

def generate_chinese_company_name() -> str:
    prefix = random.choice(COMPANY_PREFIXES)
    middle = random.choice(COMPANY_MIDDLES)
    suffix = random.choice(COMPANY_SUFFIXES)
    return f"{prefix}{middle}{suffix}"


def gen_industry() -> pl.DataFrame:
    records = []
    for i, name in enumerate(INDUSTRIES, 1):
        records.append({
            "id": i,
            "code": f"IND_{str(i).zfill(2)}",
            "name": name,
            "description": f"{name}行业的广告主",
        })
    return pl.DataFrame(records)


def gen_region() -> pl.DataFrame:
    records = []
    for i, region in enumerate(REGIONS, 1):
        records.append({
            "id": i,
            "code": f"REG_{str(i).zfill(2)}",
            "name": region,
        })
    return pl.DataFrame(records)


def gen_bid_strategy_type() -> pl.DataFrame:
    descriptions = {
        "Manual CPC": "手动设置每次点击的最高出价",
        "Enhanced CPC": "在手动出价基础上,根据转化可能性自动调整",
        "Target CPA": "自动出价以达到目标每次转化费用",
        "Target ROAS": "自动出价以达到目标广告支出回报率",
        "Maximize Conversions": "在预算范围内尽可能提高转化次数",
        "Maximize Conversion Value": "在预算范围内尽可能提高转化价值",
        "Maximize Clicks": "在预算范围内尽可能争取更多点击",
        "Target Impression Share": "自动出价以达到目标展示份额",
    }
    is_automated_map = {
        "Manual CPC": False,
        "Enhanced CPC": True,
        "Target CPA": True,
        "Target ROAS": True,
        "Maximize Conversions": True,
        "Maximize Conversion Value": True,
        "Maximize Clicks": True,
        "Target Impression Share": True,
    }
    records = []
    for i, name in enumerate(BID_STRATEGY_TYPES, 1):
        records.append({
            "id": i,
            "code": name.upper().replace(" ", "_"),
            "name": name,
            "description": descriptions.get(name, ""),
            "is_automated": is_automated_map.get(name, False),
        })
    return pl.DataFrame(records)


def gen_match_type() -> pl.DataFrame:
    return pl.DataFrame([
        {"id": 1, "code": "EXACT", "name": "完全匹配"},
        {"id": 2, "code": "PHRASE", "name": "短语匹配"},
        {"id": 3, "code": "BROAD", "name": "广泛匹配"},
    ])


def gen_device() -> pl.DataFrame:
    return pl.DataFrame([
        {"id": 1, "code": "MOBILE", "name": "移动设备"},
        {"id": 2, "code": "DESKTOP", "name": "桌面设备"},
        {"id": 3, "code": "TABLET", "name": "平板设备"},
    ])


def gen_channel() -> pl.DataFrame:
    channel_names = {
        "Paid Search": "付费搜索",
        "Display": "展示广告",
        "Social": "社交媒体",
        "Email": "电子邮件",
        "Direct": "直接访问",
        "Organic Search": "自然搜索",
    }
    records = []
    for i, channel in enumerate(CHANNELS, 1):
        records.append({
            "id": i,
            "code": channel.upper().replace(" ", "_"),
            "name": channel_names.get(channel, channel),
        })
    return pl.DataFrame(records)


def gen_agency(region_ids: List[int], n: int = N_AGENCY) -> pl.DataFrame:
    records = []
    for i in range(1, n + 1):
        created = random_datetime_between(_dt(HISTORY_START - timedelta(days=360)),
                                          _dt(HISTORY_START))
        records.append({
            "id": i,
            "agency_code": f"AGY_{str(i).zfill(3)}",
            "agency_name": f"{generate_chinese_company_name()}广告",
            "region_id": random.choice(region_ids),
            "tier_level": random.choices(AGENCY_TIERS, weights=[10, 30, 40, 20])[0],
            "account_manager": fake.name(),
            "contact_email": fake.email(),
            "contact_phone": fake.phone_number(),
            "created_at": created.isoformat(),
        })
    return pl.DataFrame(records)


def gen_advertiser(industry_ids: List[int], n: int = N_ADVERTISER) -> pl.DataFrame:
    records = []
    for i in range(1, n + 1):
        company_size = random.choices(COMPANY_SIZES, weights=[50, 35, 15])[0]

        if company_size == "Enterprise":
            spend_tier = random.choices(MONTHLY_SPEND_TIERS, weights=[5, 15, 40, 40])[0]
        elif company_size == "Mid-Market":
            spend_tier = random.choices(MONTHLY_SPEND_TIERS, weights=[10, 40, 40, 10])[0]
        else:
            spend_tier = random.choices(MONTHLY_SPEND_TIERS, weights=[40, 40, 15, 5])[0]

        created = random_datetime_between(
            _dt(TODAY - timedelta(days=720)),
            _dt(TODAY - timedelta(days=180)),
        )

        records.append({
            "id": i,
            "advertiser_code": f"ADV_{str(i).zfill(3)}",
            "company_name": generate_chinese_company_name(),
            "industry_id": random.choice(industry_ids),
            "sub_industry": None,
            "company_size": company_size,
            "monthly_spend_tier": spend_tier,
            "primary_goal": random.choice(PRIMARY_GOALS),
            "website_url": f"https://www.{fake.domain_name()}",
            "created_at": created.isoformat(),
            "account_status": random.choices(["Active", "Paused", "Suspended"], weights=[85, 12, 3])[0],
            "lifetime_cost_cny": 0.0,                         # 后续对账填充
            "lifetime_conversion_value_cny": 0.0,             # 后续对账填充
        })
    return pl.DataFrame(records)


def gen_agency_client(agency_ids: List[int], advertiser_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1
    # 80% 广告主由代理商管理
    managed = random.sample(advertiser_ids, k=int(len(advertiser_ids) * 0.8))
    for adv_id in managed:
        # 合同起始晚于所有 agency.created_at (最晚 ~TODAY-540), 满足 §7.1.1 时序
        contract_start = random_date_between(
            TODAY - timedelta(days=500),
            TODAY - timedelta(days=90),
        )
        # 50% 仍在续约 (end=NULL), 20% 已到期流失 (end 在过去), 30% 未来到期
        r = random.random()
        if r < 0.5:
            contract_end = None
        elif r < 0.7:
            contract_end = random_date_between(
                max(contract_start + timedelta(days=30), TODAY - timedelta(days=150)),
                TODAY - timedelta(days=5),
            )
        else:
            contract_end = random_date_between(
                TODAY + timedelta(days=30),
                TODAY + timedelta(days=365),
            )
        records.append({
            "id": record_id,
            "agency_id": random.choice(agency_ids),
            "advertiser_id": adv_id,
            "contract_start": contract_start.isoformat(),
            "contract_end": contract_end.isoformat() if contract_end else None,
            "fee_percentage": round(random.uniform(8, 20), 1),
            "is_active": contract_end is None or contract_end > TODAY,
        })
        record_id += 1
    return pl.DataFrame(records)


def gen_engine_account(advertiser_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1
    engine_types = ["Google", "Baidu", "Bing", "360"]
    engine_weights = [35, 40, 15, 10]                  # §4.10 / §7.2 目标分布

    for adv_id in advertiser_ids:
        # 每个广告主 1-3 个引擎账户; 按 35/40/15/10 加权不放回抽样
        num_accounts = random.randint(1, 3)
        engines = weighted_sample_no_replace(engine_types, engine_weights,
                                             k=min(num_accounts, len(engine_types)))
        created_base = random_datetime_between(
            _dt(TODAY - timedelta(days=720)),
            _dt(TODAY - timedelta(days=90)),
        )
        for engine in engines:
            records.append({
                "id": record_id,
                "account_code": f"ENG_{str(record_id).zfill(4)}",
                "advertiser_id": adv_id,
                "engine_type": engine,
                "account_name": f"{engine}广告账户_{adv_id}",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
                "status": random.choices(["Active", "Paused"], weights=[90, 10])[0],
                "created_at": created_base.isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_bid_strategy(advertiser_ids: List[int], strategy_type_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1
    for adv_id in advertiser_ids:
        num_strategies = random.randint(2, 5)
        for j in range(num_strategies):
            strategy_type_id = random.choice(strategy_type_ids)

            target_cpa = None
            target_roas = None
            max_cpc_limit = None
            target_impr_share = None
            impr_share_location = None

            if strategy_type_id == 3:                          # Target CPA
                target_cpa = round(random.uniform(20, 200), 2)
            elif strategy_type_id == 4:                        # Target ROAS
                target_roas = round(random.uniform(2.0, 8.0), 2)
            elif strategy_type_id in [1, 2]:                   # Manual / Enhanced CPC
                max_cpc_limit = round(random.uniform(1, 20), 2)
            elif strategy_type_id == 8:                        # Target Impression Share
                target_impr_share = round(random.uniform(50, 95), 0)
                impr_share_location = random.choice(["Anywhere", "Top of page", "Absolute top"])

            created = random_datetime_between(
                _dt(TODAY - timedelta(days=540)),
                _dt(TODAY - timedelta(days=30)),
            )
            last_modified = created + timedelta(days=random.randint(1, 60))

            records.append({
                "id": record_id,
                "strategy_code": f"BID_{str(record_id).zfill(4)}",
                "advertiser_id": adv_id,
                "strategy_name": f"策略_{record_id}_{BID_STRATEGY_TYPES[strategy_type_id - 1]}",
                "strategy_type_id": strategy_type_id,
                "target_cpa": target_cpa,
                "target_roas": target_roas,
                "max_cpc_limit": max_cpc_limit,
                "target_impr_share": target_impr_share,
                "impr_share_location": impr_share_location,
                "status": random.choices(["Active", "Paused"], weights=[80, 20])[0],
                "created_at": created.isoformat(),
                "last_modified": last_modified.isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_campaign(advertiser_ids: List[int], engine_account_df: pl.DataFrame,
                 bid_strategy_df: pl.DataFrame, industry_df: pl.DataFrame,
                 advertiser_df: pl.DataFrame) -> pl.DataFrame:
    records = []
    record_id = 1

    adv_to_engines: Dict[int, List[int]] = {}
    for row in engine_account_df.iter_rows(named=True):
        adv_to_engines.setdefault(row["advertiser_id"], []).append(row["id"])

    adv_to_strategies: Dict[int, List[int]] = {}
    for row in bid_strategy_df.iter_rows(named=True):
        adv_to_strategies.setdefault(row["advertiser_id"], []).append(row["id"])

    adv_to_industry = {row["id"]: row["industry_id"] for row in advertiser_df.iter_rows(named=True)}
    industry_names = {row["id"]: row["name"] for row in industry_df.iter_rows(named=True)}

    for adv_id in advertiser_ids:
        num_campaigns = random.randint(5, 15)
        engine_accounts = adv_to_engines.get(adv_id, [])
        strategies = adv_to_strategies.get(adv_id, [])
        industry_id = adv_to_industry.get(adv_id, 1)
        industry_name = industry_names.get(industry_id, "电商零售")

        for j in range(num_campaigns):
            campaign_type = random.choices(CAMPAIGN_TYPES, weights=[50, 20, 15, 10, 5])[0]
            start_date = random_date_between(
                TODAY - timedelta(days=540),
                TODAY - timedelta(days=30),
            )

            theme = random.choice([
                "品牌词_PC端", "竞品词_移动端", "通用词_全设备",
                "产品词_高意向", "活动词_限时促销", "地域词_本地推广",
                "长尾词_精准获客", "再营销_老客户",
            ])

            records.append({
                "id": record_id,
                "campaign_code": f"CMP_{str(record_id).zfill(5)}",
                "advertiser_id": adv_id,
                "engine_account_id": random.choice(engine_accounts) if engine_accounts else 1,
                "campaign_name": f"{industry_name}_{theme}_{record_id}",
                "campaign_type": campaign_type,
                "campaign_subtype": random.choice(CAMPAIGN_SUBTYPES) if campaign_type == "Search" else None,
                "bid_strategy_id": random.choice(strategies) if strategies else None,
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[70, 25, 5])[0],
                "start_date": start_date.isoformat(),
                "end_date": None if random.random() < 0.7
                            else (start_date + timedelta(days=random.randint(30, 180))).isoformat(),
                "targeting_location": random.choice(["全国", "华东地区", "华北地区", "一线城市", "二线城市"]),
                "targeting_language": "中文",
                "targeting_device": random.choice(["All", "Mobile", "Desktop"]),
                "created_at": _dt(start_date).isoformat(),
                "lifetime_cost_cny": 0.0,                      # 后续对账填充
                "lifetime_conversions": 0.0,                   # 后续对账填充
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_campaign_budget(campaign_df: pl.DataFrame, daily_stats_df: pl.DataFrame,
                        constrained_ids: Optional[set] = None) -> pl.DataFrame:
    """历史化预算: 每 campaign 1-3 条带 effective_date_start/end (相邻无缝衔接)。

    关键: daily_budget **锚定到该 campaign 的实际日均花费**, 使预算使用率
    (avg_daily_spend / daily_budget) 落在合理区间:
      - 普通 campaign: 花费 < 预算 → 使用率 ~55–95%
      - 预算受限 campaign (constrained_ids): 花费 ≥ 预算 → 使用率 >100%, 与其偏高的
        lost_is_budget 叙事一致
    """
    records = []
    record_id = 1
    constrained_ids = constrained_ids or set()

    # 每 campaign 的日均花费 (3 设备合计 / 活跃天数)
    spend_agg = (
        daily_stats_df
        .filter(pl.col("entity_type") == "Campaign")
        .group_by("entity_id")
        .agg([
            pl.col("cost").sum().alias("total_cost"),
            pl.col("report_date").n_unique().alias("n_days"),
        ])
    )
    cmp_avg_daily: Dict[int, float] = {}
    for r in spend_agg.iter_rows(named=True):
        nd = r["n_days"] or 0
        cmp_avg_daily[r["entity_id"]] = (r["total_cost"] / nd) if nd > 0 else 0.0

    for row in campaign_df.iter_rows(named=True):
        cmp_id = row["id"]
        cmp_start = date.fromisoformat(row["start_date"])
        cmp_end_iso = row["end_date"]
        cmp_end = date.fromisoformat(cmp_end_iso) if cmp_end_iso else None

        avg_daily = cmp_avg_daily.get(cmp_id, 0.0)
        # 把"当前生效预算"锚到日均花费 / 目标使用率
        if avg_daily <= 0:
            base_budget = round(random.uniform(100, 10000), 2)   # 无花费数据(已结束/窗外)回退
        elif cmp_id in constrained_ids:
            base_budget = round(avg_daily / random.uniform(1.0, 1.45), 2)   # 花费 ≥ 预算
        else:
            base_budget = round(avg_daily / random.uniform(0.55, 0.95), 2)  # 花费 < 预算
        base_budget = max(50.0, min(base_budget, 200_000.0))

        num_budgets = random.randint(1, 3)
        current_start = cmp_start

        for j in range(num_budgets):
            is_last = (j == num_budgets - 1)
            # 每段在 base 附近小幅波动 (展示"预算变更"但量级稳定, 不破坏使用率口径)
            seg_budget = round(max(50.0, base_budget * random.uniform(0.9, 1.12)), 2)

            if is_last:
                # 最后一条: 仍在投放 → end=NULL; 已结束 (cmp_end 已知) → end=cmp_end
                effective_end = cmp_end
            else:
                # 中间条目结束日期: 在 current_start 之后随机 30-180 天
                days_offset = random.randint(30, 180)
                effective_end = current_start + timedelta(days=days_offset)
                # 不超过 campaign 结束日 → 提前收尾为最后一条
                if cmp_end and effective_end >= cmp_end:
                    effective_end = cmp_end
                    is_last = True
                # 若已到/越过 TODAY, 说明 campaign 仍在投放 → 本条即最后一条, end=NULL
                if effective_end is not None and effective_end >= TODAY:
                    effective_end = None
                    is_last = True

            records.append({
                "id": record_id,
                "campaign_id": cmp_id,
                "daily_budget": seg_budget,
                "monthly_budget": round(seg_budget * 30, 2),
                "budget_delivery": random.choices(["Standard", "Accelerated"], weights=[80, 20])[0],
                "effective_date_start": current_start.isoformat(),
                "effective_date_end": effective_end.isoformat() if effective_end else None,
                "created_at": _dt(current_start).isoformat(),
            })
            record_id += 1

            if is_last or effective_end is None:
                break

            # 下一条从 effective_end 开始
            current_start = effective_end
            if current_start >= TODAY:
                break

    return pl.DataFrame(records)


def gen_ad_group(campaign_df: pl.DataFrame, advertiser_df: pl.DataFrame,
                 industry_df: pl.DataFrame) -> pl.DataFrame:
    records = []
    record_id = 1

    campaign_to_adv = {row["id"]: row["advertiser_id"] for row in campaign_df.iter_rows(named=True)}
    adv_to_industry = {row["id"]: row["industry_id"] for row in advertiser_df.iter_rows(named=True)}
    industry_names = {row["id"]: row["name"] for row in industry_df.iter_rows(named=True)}

    for row in campaign_df.iter_rows(named=True):
        cmp_id = row["id"]
        adv_id = campaign_to_adv.get(cmp_id, 1)
        industry_id = adv_to_industry.get(adv_id, 1)
        industry_name = industry_names.get(industry_id, "电商零售")

        num_groups = random.randint(3, 8)
        keywords_for_industry = KEYWORDS_BY_INDUSTRY.get(industry_name, KEYWORDS_BY_INDUSTRY["电商零售"])

        for j in range(num_groups):
            theme = random.choice(keywords_for_industry)
            records.append({
                "id": record_id,
                "ad_group_code": f"AGP_{str(record_id).zfill(5)}",
                "campaign_id": cmp_id,
                "ad_group_name": f"{theme}_广告组",
                "default_cpc": round(random.uniform(0.5, 15), 2),
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[75, 20, 5])[0],
                "created_at": row["created_at"],
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_keyword(ad_group_df: pl.DataFrame, campaign_df: pl.DataFrame,
                advertiser_df: pl.DataFrame, industry_df: pl.DataFrame,
                match_type_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1

    adgroup_to_campaign = {row["id"]: row["campaign_id"] for row in ad_group_df.iter_rows(named=True)}
    campaign_to_adv = {row["id"]: row["advertiser_id"] for row in campaign_df.iter_rows(named=True)}
    adv_to_industry = {row["id"]: row["industry_id"] for row in advertiser_df.iter_rows(named=True)}
    industry_names = {row["id"]: row["name"] for row in industry_df.iter_rows(named=True)}

    quality_levels = ["Below Average", "Average", "Above Average"]

    for row in ad_group_df.iter_rows(named=True):
        agp_id = row["id"]
        cmp_id = adgroup_to_campaign.get(agp_id, 1)
        adv_id = campaign_to_adv.get(cmp_id, 1)
        industry_id = adv_to_industry.get(adv_id, 1)
        industry_name = industry_names.get(industry_id, "电商零售")

        keywords_for_industry = KEYWORDS_BY_INDUSTRY.get(industry_name, KEYWORDS_BY_INDUSTRY["电商零售"])

        # 5-15 个关键词/广告组 (§4.15)
        num_keywords = random.randint(5, 15)
        # 允许重复以达到 8 万行总量
        selected_keywords = [random.choice(keywords_for_industry) for _ in range(num_keywords)]

        for kw_text in selected_keywords:
            quality_score = random.randint(3, 10)
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
                "expected_ctr": random.choice(quality_levels),
                "ad_relevance": random.choice(quality_levels),
                "landing_page_exp": random.choice(quality_levels),
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

    adgroup_to_campaign = {row["id"]: row["campaign_id"] for row in ad_group_df.iter_rows(named=True)}
    campaign_to_adv = {row["id"]: row["advertiser_id"] for row in campaign_df.iter_rows(named=True)}
    adv_to_industry = {row["id"]: row["industry_id"] for row in advertiser_df.iter_rows(named=True)}
    industry_names = {row["id"]: row["name"] for row in industry_df.iter_rows(named=True)}

    headline_templates = [
        "{industry}优惠来袭",
        "限时特惠{industry}",
        "{industry}专业服务",
        "品质{industry}首选",
        "{industry}一站式服务",
        "专注{industry}多年",
    ]
    description_templates = [
        "专业团队,品质保证。立即咨询获取优惠方案!",
        "超值优惠,限时抢购。点击了解详情,立享折扣!",
        "行业领先,服务至上。点击获取免费报价!",
        "品质生活,从这里开始。立即预约体验!",
    ]

    for row in ad_group_df.iter_rows(named=True):
        agp_id = row["id"]
        cmp_id = adgroup_to_campaign.get(agp_id, 1)
        adv_id = campaign_to_adv.get(cmp_id, 1)
        industry_id = adv_to_industry.get(adv_id, 1)
        industry_name = industry_names.get(industry_id, "电商零售")

        num_ads = random.randint(2, 4)
        for j in range(num_ads):
            records.append({
                "id": record_id,
                "ad_code": f"AD_{str(record_id).zfill(6)}",
                "ad_group_id": agp_id,
                "headline_1": random.choice(headline_templates).format(industry=industry_name[:4]),
                "headline_2": "官方认证-值得信赖",
                "headline_3": "立即咨询" if random.random() < 0.7 else None,
                "description_1": random.choice(description_templates),
                "description_2": "7*24小时在线服务,随时为您解答!" if random.random() < 0.6 else None,
                "final_url": f"https://www.example{adv_id}.com/landing",
                "display_url": f"www.example{adv_id}.com",
                "status": random.choices(["Enabled", "Paused", "Removed"], weights=[75, 20, 5])[0],
                "quality_score": random.randint(4, 10),
                "created_at": row["created_at"],
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_floodlight_tag(advertiser_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1
    attribution_models = ["Last Click", "First Click", "Linear", "Time Decay",
                          "Position Based", "Data Driven"]

    for adv_id in advertiser_ids:
        num_tags = random.randint(2, 5)
        conv_types = random.sample(CONVERSION_TYPES, k=min(num_tags, len(CONVERSION_TYPES)))
        for conv_type in conv_types:
            records.append({
                "id": record_id,
                "tag_code": f"FL_{str(record_id).zfill(4)}",
                "advertiser_id": adv_id,
                "tag_name": f"{conv_type}_转化跟踪",
                "conversion_type": conv_type,
                "counting_method": random.choice(["Standard", "Unique"]),
                "attribution_model": random.choice(attribution_models),
                "lookback_window": random.choice([7, 14, 30, 60, 90]),
                "status": "Active",
                "created_at": random_datetime_between(
                    _dt(TODAY - timedelta(days=540)),
                    _dt(TODAY - timedelta(days=180)),
                ).isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_daily_stats(campaign_df: pl.DataFrame, device_ids: List[int],
                    constrained_ids: Optional[set] = None,
                    days: int = DAILY_STATS_DAYS) -> pl.DataFrame:
    """生成 Campaign × Date × Device 的每日效果数据。"""
    records = []
    record_id = 1
    constrained_ids = constrained_ids or set()

    window_start = TODAY - timedelta(days=days)
    window_end = TODAY

    for row in campaign_df.iter_rows(named=True):
        cmp_id = row["id"]
        cmp_start = date.fromisoformat(row["start_date"])
        cmp_end = date.fromisoformat(row["end_date"]) if row["end_date"] else window_end

        # §7.1.4 时序: report_date ≥ campaign.start_date 且 ≤ min(end_date, TODAY)
        ds_start = max(window_start, cmp_start)
        ds_end = min(window_end, cmp_end)

        # 引入 campaign 级的"基础质量",让数据在 campaign 间有差异
        cmp_quality = random.uniform(0.7, 1.4)
        # 预算受限 campaign (由主流程统一指定): lost_is_budget 系统性偏高,
        # 且其 daily_budget 会被锚到"花费 ≥ 预算" → 预算使用率 >100% (与 lost_is_budget 叙事一致)
        budget_constrained = cmp_id in constrained_ids

        current_date = ds_start
        while current_date <= ds_end:
            for device_id in device_ids:
                # Mobile 占 55% 流量, Desktop 35%, Tablet 10%
                device_multiplier = {1: 1.1, 2: 0.7, 3: 0.2}.get(device_id, 1.0)

                impressions = max(1, int(random.randint(100, 50000) * device_multiplier))
                # CTR 目标 ~3.5% (§2.3): base uniform × campaign quality
                ctr = random.uniform(0.012, 0.055) * cmp_quality
                ctr = min(0.30, max(0.002, ctr))
                clicks = max(0, int(impressions * ctr))

                # 平均 CPC 目标 ~¥4.5 (§2.3)
                avg_cpc = round(random.uniform(0.5, 8.5), 2)
                cost = round(clicks * avg_cpc, 2)

                # 转化率 ~2.6% → CPA = cpc/conv_rate ≈ ¥180 (§2.3)
                conv_rate = random.uniform(0.005, 0.045) * cmp_quality
                conv_rate = min(0.20, max(0.0, conv_rate))
                conversions = round(clicks * conv_rate, 2)

                # 转化价值 → ROAS = conv_value/cost ≈ 3.2x (§2.3)
                avg_conv_value = round(random.uniform(100, 1000), 2)
                conversion_value = round(conversions * avg_conv_value, 2)

                cpa = round(cost / conversions, 2) if conversions > 0 else None
                roas = round(conversion_value / cost, 2) if cost > 0 else None
                actual_ctr = round(clicks / impressions, 4) if impressions > 0 else None
                actual_cpc = round(cost / clicks, 2) if clicks > 0 else None

                # 展示份额三件套: impression_share + lost_is_budget + lost_is_rank = 100
                impr_share = round(random.uniform(20, 95), 1)
                remaining = 100 - impr_share
                if budget_constrained:
                    lost_budget = round(random.uniform(0.40, 0.85) * remaining, 1)
                else:
                    lost_budget = round(random.uniform(0.0, 0.30) * remaining, 1)
                lost_rank = round(remaining - lost_budget, 1)

                # 页首份额有序: abs_top ≤ top ≤ impression_share
                search_top_is = round(random.uniform(0.5, 1.0) * impr_share, 1)
                search_abs_top_is = round(random.uniform(0.4, 1.0) * search_top_is, 1)

                records.append({
                    "id": record_id,
                    "entity_type": "Campaign",
                    "entity_id": cmp_id,
                    "report_date": current_date.isoformat(),
                    "device_id": device_id,
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": cost,
                    "conversions": conversions,
                    "conversion_value": conversion_value,
                    "ctr": actual_ctr,
                    "avg_cpc": actual_cpc,
                    "cpa": cpa,
                    "roas": roas,
                    "impression_share": impr_share,
                    "search_impr_share": impr_share,
                    "lost_is_budget": lost_budget,
                    "lost_is_rank": lost_rank,
                    "search_abs_top_is": search_abs_top_is,
                    "search_top_is": search_top_is,
                })
                record_id += 1
            current_date += timedelta(days=1)

    return pl.DataFrame(records)


def gen_conversion(advertiser_ids: List[int], floodlight_df: pl.DataFrame,
                   n: int = N_CONVERSION) -> pl.DataFrame:
    records = []
    adv_to_tags: Dict[int, List[int]] = {}
    for row in floodlight_df.iter_rows(named=True):
        adv_to_tags.setdefault(row["advertiser_id"], []).append(row["id"])

    # tag → conversion_type, 用于按类型给转化价值分档 (§4.19)
    tag_to_type = {row["id"]: row["conversion_type"] for row in floodlight_df.iter_rows(named=True)}
    # 购买类: 50–2000 CNY; 留资类: 1–50 CNY
    HIGH_VALUE_TYPES = {"Purchase", "AddToCart", "AppInstall"}

    for i in range(1, n + 1):
        adv_id = random.choice(advertiser_ids)
        tags = adv_to_tags.get(adv_id, [])
        if not tags:
            continue
        tag_id = random.choice(tags)
        conv_type = tag_to_type.get(tag_id, "Purchase")
        if conv_type in HIGH_VALUE_TYPES:
            conv_value = round(random.uniform(50, 2000), 2)
        else:                                                  # Lead / Signup / PageView
            conv_value = round(random.uniform(1, 50), 2)
        conv_time = random_datetime_between(
            _dt(TODAY - timedelta(days=CONVERSION_LOOKBACK_DAYS)),
            _dt(TODAY),
        )
        records.append({
            "id": i,
            "conversion_code": f"CONV_{str(i).zfill(6)}",
            "advertiser_id": adv_id,
            "floodlight_tag_id": tag_id,
            "conversion_time": conv_time.isoformat(),
            "conversion_value": conv_value,
            "currency": "CNY",
            "quantity": random.randint(1, 5),
        })
    return pl.DataFrame(records)


def gen_attribution_path(conversion_df: pl.DataFrame, campaign_df: pl.DataFrame,
                         ad_group_df: pl.DataFrame, keyword_df: pl.DataFrame,
                         channel_ids: List[int]) -> pl.DataFrame:
    records = []
    record_id = 1

    # 构建层级映射: 广告主 → campaign → ad_group → keyword
    adv_to_campaigns: Dict[int, List[int]] = {}
    for r in campaign_df.iter_rows(named=True):
        adv_to_campaigns.setdefault(r["advertiser_id"], []).append(r["id"])

    campaign_to_adgroups: Dict[int, List[int]] = {}
    for r in ad_group_df.iter_rows(named=True):
        campaign_to_adgroups.setdefault(r["campaign_id"], []).append(r["id"])

    adgroup_to_keywords: Dict[int, List[int]] = {}
    for r in keyword_df.iter_rows(named=True):
        adgroup_to_keywords.setdefault(r["ad_group_id"], []).append(r["id"])

    for row in conversion_df.iter_rows(named=True):
        conv_id = row["id"]
        adv_id = row["advertiser_id"]
        conv_time = datetime.fromisoformat(row["conversion_time"])
        adv_campaigns = adv_to_campaigns.get(adv_id, [])

        num_touchpoints = random.randint(2, 6)

        # 计算 6 种模型的权重
        last_click_credits = [0.0] * num_touchpoints
        last_click_credits[-1] = 1.0

        first_click_credits = [0.0] * num_touchpoints
        first_click_credits[0] = 1.0

        linear_credits = [1.0 / num_touchpoints] * num_touchpoints

        decay_sum = sum([2 ** i for i in range(num_touchpoints)])
        time_decay_credits = [2 ** i / decay_sum for i in range(num_touchpoints)]

        # Position 模型: N=1 → 100%; N=2 → 50/50 (Google 真实口径);
        # N≥3 → 首末各 40%, 中间均分 20%。各情形 credit 之和恒 = 1.0 (不变式 #6)
        if num_touchpoints == 1:
            position_credits = [1.0]
        elif num_touchpoints == 2:
            position_credits = [0.5, 0.5]
        else:
            position_credits = []
            for i in range(num_touchpoints):
                if i == 0 or i == num_touchpoints - 1:
                    position_credits.append(0.4)
                else:
                    position_credits.append(0.2 / (num_touchpoints - 2))

        data_driven_raw = [random.uniform(0.1, 0.4) for _ in range(num_touchpoints)]
        dd_sum = sum(data_driven_raw)
        data_driven_credits = [c / dd_sum for c in data_driven_raw]

        for tp_order in range(1, num_touchpoints + 1):
            hours_before = random.randint(1, 720)
            days_before = hours_before // 24
            interaction_time = conv_time - timedelta(hours=hours_before)

            channel_id = random.choice(channel_ids)
            # 触点的 campaign/ad_group/keyword 必须同属转化所属广告主, 且构成父子链
            campaign_id = None
            ad_group_id = None
            keyword_id = None
            if adv_campaigns and random.random() < 0.8:
                campaign_id = random.choice(adv_campaigns)
                cmp_adgroups = campaign_to_adgroups.get(campaign_id, [])
                if cmp_adgroups and random.random() < 0.7:
                    ad_group_id = random.choice(cmp_adgroups)
                    agp_keywords = adgroup_to_keywords.get(ad_group_id, [])
                    if agp_keywords and random.random() < 0.6:
                        keyword_id = random.choice(agp_keywords)

            records.append({
                "id": record_id,
                "conversion_id": conv_id,
                "advertiser_id": adv_id,
                "touchpoint_order": tp_order,
                "channel_id": channel_id,
                "campaign_id": campaign_id,
                "ad_group_id": ad_group_id,
                "keyword_id": keyword_id,
                "interaction_type": random.choices(INTERACTION_TYPES, weights=[70, 25, 5])[0],
                "interaction_time": interaction_time.isoformat(),
                "days_before_conv": days_before,
                "hours_before_conv": hours_before,
                "last_click_credit": round(last_click_credits[tp_order - 1], 4),
                "first_click_credit": round(first_click_credits[tp_order - 1], 4),
                "linear_credit": round(linear_credits[tp_order - 1], 4),
                "time_decay_credit": round(time_decay_credits[tp_order - 1], 4),
                "position_credit": round(position_credits[tp_order - 1], 4),
                "data_driven_credit": round(data_driven_credits[tp_order - 1], 4),
            })
            record_id += 1

    return pl.DataFrame(records)


def gen_search_term_report(keyword_df: pl.DataFrame, ad_group_df: pl.DataFrame,
                           campaign_df: pl.DataFrame, device_ids: List[int],
                           days: int = SEARCH_TERM_DAYS,
                           max_rows: int = MAX_SEARCH_TERM_ROWS) -> pl.DataFrame:
    """搜索词报告 — 包含 device_id;按 max_rows 硬上限。"""
    records = []
    record_id = 1

    end_date = TODAY
    start_date = end_date - timedelta(days=days)

    adgroup_to_campaign = {row["id"]: row["campaign_id"] for row in ad_group_df.iter_rows(named=True)}

    window_days = (end_date - start_date).days

    # 只对 Enabled 的关键词生成搜索词数据
    enabled_keywords = keyword_df.filter(pl.col("status") == "Enabled")
    n_enabled = max(1, len(enabled_keywords))

    # 动态配额: 把 ~90% 上限的行数均摊到每个启用关键词,
    # 保证全部关键词都有搜索词数据 (不再按 keyword id 截断), 总量逼近上限。
    base_terms = max(1.0, (max_rows * 0.9) / n_enabled)

    for row in enabled_keywords.iter_rows(named=True):
        if record_id > max_rows:
            break

        kw_id = row["id"]
        agp_id = row["ad_group_id"]
        kw_text = row["keyword_text"]
        cmp_id = adgroup_to_campaign.get(agp_id, 1)

        # 该关键词在 30 天窗口内的搜索词条数 (期望 ≈ base_terms, 至少 1 条)
        n_terms = max(1, int(round(random.uniform(0.5, 1.5) * base_terms)))

        for _ in range(n_terms):
            if record_id > max_rows:
                break

            report_date = start_date + timedelta(days=random.randint(0, window_days))

            # 构造长尾搜索词: 30% 用种子词本身 (高频头部词),
            # 70% 拼接 (可选地名) + 1-3 个修饰词 → 海量低频/唯一长尾词
            if random.random() < 0.30:
                search_term = kw_text
            else:
                parts = [kw_text]
                if random.random() < 0.45:
                    parts.insert(0, random.choice(SEARCH_TERM_GEO))
                k = random.choices([1, 2, 3], weights=[45, 35, 20])[0]
                parts += random.sample(SEARCH_TERM_QUALIFIERS, k)
                search_term = "".join(parts)

            # Mobile 55% / Desktop 35% / Tablet 10% 流量分布
            device_id = random.choices(device_ids, weights=[55, 35, 10])[0]

            impressions = random.randint(1, 500)
            clicks = max(0, int(impressions * random.uniform(0.01, 0.15)))
            cost = round(clicks * random.uniform(0.5, 10), 2)

            # 真实搜索词大多"有点击但不转化": 仅 ~30% 的有点击搜索词产生转化,
            # 其余 conversions=0 → "高花费零转化否定词候选"查询能命中长尾词
            if clicks > 0 and random.random() < 0.30:
                conversions = round(min(float(clicks), clicks * random.uniform(0.05, 0.30)), 2)
            else:
                conversions = 0.0
            conversion_value = round(conversions * random.uniform(50, 300), 2) if conversions > 0 else 0.0

            # 业务保证: conversions <= clicks
            if conversions > clicks:
                conversions = float(clicks)

            records.append({
                "id": record_id,
                "report_date": report_date.isoformat(),
                "campaign_id": cmp_id,
                "ad_group_id": agp_id,
                "keyword_id": kw_id,
                "device_id": device_id,
                "search_term": search_term,
                "match_type_used": random.choice(MATCH_TYPES),
                "impressions": impressions,
                "clicks": clicks,
                "cost": cost,
                "conversions": conversions,
                "conversion_value": conversion_value,
                # 'None' = 未处理 (字面量字符串, 与文档 §4.21/§14.6 查询口径一致)
                "added_excluded": random.choices(
                    ["None", "Added", "Excluded"], weights=[80, 15, 5]
                )[0],
            })
            record_id += 1

    return pl.DataFrame(records)


# ============================================================================
# 对账 (Reconciliation): 把子表聚合回父表的字段
# ============================================================================

def reconcile_lifetime_fields(advertiser_df: pl.DataFrame, campaign_df: pl.DataFrame,
                              daily_stats_df: pl.DataFrame) -> Tuple[pl.DataFrame, pl.DataFrame]:
    """
    把 daily_stats 的 cost / conversion_value / conversions 聚合回:
    - campaign.lifetime_cost_cny, lifetime_conversions
    - advertiser.lifetime_cost_cny, lifetime_conversion_value_cny
    """
    print("  Reconciling lifetime fields on campaign & advertiser ...")

    # 步骤 1: 按 campaign 聚合
    cmp_agg = (
        daily_stats_df
        .filter(pl.col("entity_type") == "Campaign")
        .group_by("entity_id")
        .agg([
            pl.col("cost").sum().alias("_lifetime_cost_cny"),
            pl.col("conversions").sum().alias("_lifetime_conversions"),
            pl.col("conversion_value").sum().alias("_lifetime_conv_value"),
        ])
        .rename({"entity_id": "id"})
    )

    campaign_df = (
        campaign_df
        .drop(["lifetime_cost_cny", "lifetime_conversions"])
        .join(cmp_agg, on="id", how="left")
        .with_columns([
            pl.col("_lifetime_cost_cny").fill_null(0.0).round(2).alias("lifetime_cost_cny"),
            pl.col("_lifetime_conversions").fill_null(0.0).round(2).alias("lifetime_conversions"),
        ])
    )

    # 步骤 2: 按 advertiser 聚合 (通过 campaign 关联)
    adv_agg = (
        campaign_df
        .join(cmp_agg, on="id", how="left")
        .group_by("advertiser_id")
        .agg([
            pl.col("_lifetime_cost_cny").sum().alias("__lifetime_cost"),
            pl.col("_lifetime_conv_value").sum().alias("__lifetime_value"),
        ])
        .rename({"advertiser_id": "id"})
    )

    advertiser_df = (
        advertiser_df
        .drop(["lifetime_cost_cny", "lifetime_conversion_value_cny"])
        .join(adv_agg, on="id", how="left")
        .with_columns([
            pl.col("__lifetime_cost").fill_null(0.0).round(2).alias("lifetime_cost_cny"),
            pl.col("__lifetime_value").fill_null(0.0).round(2).alias("lifetime_conversion_value_cny"),
        ])
    )

    # 清理中间列
    campaign_df = campaign_df.drop([c for c in campaign_df.columns if c.startswith("_lifetime")])
    advertiser_df = advertiser_df.drop([c for c in advertiser_df.columns if c.startswith("__lifetime")])

    return advertiser_df, campaign_df


# ============================================================================
# 主流程
# ============================================================================

def generate_all_tsv() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating dimension tables...")
    df_industry = gen_industry()
    df_region = gen_region()
    df_bid_strategy_type = gen_bid_strategy_type()
    df_match_type = gen_match_type()
    df_device = gen_device()
    df_channel = gen_channel()

    print(f"Generating {N_AGENCY} agencies & {N_ADVERTISER} advertisers ...")
    df_agency = gen_agency(df_region["id"].to_list(), n=N_AGENCY)
    df_advertiser = gen_advertiser(df_industry["id"].to_list(), n=N_ADVERTISER)
    advertiser_ids = df_advertiser["id"].to_list()

    print("Generating agency-client contracts ...")
    df_agency_client = gen_agency_client(df_agency["id"].to_list(), advertiser_ids)

    print("Generating engine accounts ...")
    df_engine_account = gen_engine_account(advertiser_ids)

    print("Generating bid strategies ...")
    df_bid_strategy = gen_bid_strategy(advertiser_ids, df_bid_strategy_type["id"].to_list())

    print(f"Generating campaigns ...")
    df_campaign = gen_campaign(advertiser_ids, df_engine_account, df_bid_strategy,
                               df_industry, df_advertiser)
    print(f"  → {len(df_campaign)} campaigns")
    campaign_ids = df_campaign["id"].to_list()

    # ~15% campaign 为"预算受限": daily_stats 里其 lost_is_budget 偏高,
    # 且 campaign_budget 把预算锚到"花费 ≥ 预算" → 预算使用率 >100% (二者叙事一致)。
    # 在主流程统一抽取并同时传给 gen_daily_stats 与 gen_campaign_budget。
    constrained_ids = set(random.sample(campaign_ids, k=max(1, int(len(campaign_ids) * 0.15))))
    print(f"  → {len(constrained_ids)} budget-constrained campaigns")

    print("Generating ad groups ...")
    df_ad_group = gen_ad_group(df_campaign, df_advertiser, df_industry)
    print(f"  → {len(df_ad_group)} ad groups")

    print("Generating keywords ...")
    df_keyword = gen_keyword(df_ad_group, df_campaign, df_advertiser, df_industry,
                             df_match_type["id"].to_list())
    print(f"  → {len(df_keyword)} keywords")

    print("Generating text ads ...")
    df_text_ad = gen_text_ad(df_ad_group, df_campaign, df_advertiser, df_industry)
    print(f"  → {len(df_text_ad)} text ads")

    print("Generating floodlight tags ...")
    df_floodlight = gen_floodlight_tag(advertiser_ids)
    print(f"  → {len(df_floodlight)} floodlight tags")

    print(f"Generating daily stats ({DAILY_STATS_DAYS} days × {len(df_campaign)} campaigns × 3 devices) ...")
    df_daily_stats = gen_daily_stats(df_campaign, df_device["id"].to_list(),
                                     constrained_ids=constrained_ids, days=DAILY_STATS_DAYS)
    print(f"  → {len(df_daily_stats)} daily_stats rows")

    # 预算锚定到实际日均花费 → 必须在 daily_stats 之后生成
    print("Generating campaign budget history (slowly changing dim, anchored to actual spend) ...")
    df_campaign_budget = gen_campaign_budget(df_campaign, df_daily_stats, constrained_ids=constrained_ids)
    print(f"  → {len(df_campaign_budget)} budget records")

    print(f"Generating {N_CONVERSION} conversions ...")
    df_conversion = gen_conversion(advertiser_ids, df_floodlight, n=N_CONVERSION)

    print("Generating attribution paths ...")
    df_attribution = gen_attribution_path(df_conversion, df_campaign, df_ad_group,
                                          df_keyword, df_channel["id"].to_list())
    print(f"  → {len(df_attribution)} attribution_path rows")

    print(f"Generating search term reports (cap {MAX_SEARCH_TERM_ROWS:,}) ...")
    df_search_term = gen_search_term_report(df_keyword, df_ad_group, df_campaign,
                                            df_device["id"].to_list(),
                                            days=SEARCH_TERM_DAYS,
                                            max_rows=MAX_SEARCH_TERM_ROWS)
    print(f"  → {len(df_search_term)} search_term_report rows")

    # 对账步骤: 把 daily_stats 聚合回 campaign / advertiser
    df_advertiser, df_campaign = reconcile_lifetime_fields(df_advertiser, df_campaign, df_daily_stats)

    # 写所有 TSV
    print("\nWriting TSV files ...")
    df_industry.write_csv(DATA_DIR / "01_industry.tsv", separator="\t")
    df_region.write_csv(DATA_DIR / "02_region.tsv", separator="\t")
    df_bid_strategy_type.write_csv(DATA_DIR / "03_bid_strategy_type.tsv", separator="\t")
    df_match_type.write_csv(DATA_DIR / "04_match_type.tsv", separator="\t")
    df_device.write_csv(DATA_DIR / "05_device.tsv", separator="\t")
    df_channel.write_csv(DATA_DIR / "06_channel.tsv", separator="\t")
    df_agency.write_csv(DATA_DIR / "07_agency.tsv", separator="\t")
    df_advertiser.write_csv(DATA_DIR / "08_advertiser.tsv", separator="\t")
    df_agency_client.write_csv(DATA_DIR / "09_agency_client.tsv", separator="\t")
    df_engine_account.write_csv(DATA_DIR / "10_engine_account.tsv", separator="\t")
    df_bid_strategy.write_csv(DATA_DIR / "11_bid_strategy.tsv", separator="\t")
    df_campaign.write_csv(DATA_DIR / "12_campaign.tsv", separator="\t")
    df_campaign_budget.write_csv(DATA_DIR / "13_campaign_budget.tsv", separator="\t")
    df_ad_group.write_csv(DATA_DIR / "14_ad_group.tsv", separator="\t")
    df_keyword.write_csv(DATA_DIR / "15_keyword.tsv", separator="\t")
    df_text_ad.write_csv(DATA_DIR / "16_text_ad.tsv", separator="\t")
    df_floodlight.write_csv(DATA_DIR / "17_floodlight_tag.tsv", separator="\t")
    df_daily_stats.write_csv(DATA_DIR / "18_daily_stats.tsv", separator="\t")
    df_conversion.write_csv(DATA_DIR / "19_conversion.tsv", separator="\t")
    df_attribution.write_csv(DATA_DIR / "20_attribution_path.tsv", separator="\t")
    df_search_term.write_csv(DATA_DIR / "21_search_term_report.tsv", separator="\t")

    print(f"\nAll TSV files written to {DATA_DIR}")

    return {
        "n_advertiser": len(df_advertiser),
        "n_campaign": len(df_campaign),
        "n_daily_stats": len(df_daily_stats),
        "n_keyword": len(df_keyword),
        "n_search_term": len(df_search_term),
        "n_attribution": len(df_attribution),
    }


def parse_datetime_fields(row: dict, datetime_fields: list, date_fields: list) -> dict:
    result = {}
    for k, v in row.items():
        if v is None or v == "":
            result[k] = None
            continue
        if k in datetime_fields and isinstance(v, str):
            try:
                result[k] = datetime.fromisoformat(v)
            except ValueError:
                result[k] = v
        elif k in date_fields and isinstance(v, str):
            try:
                result[k] = date.fromisoformat(v)
            except ValueError:
                result[k] = v
        else:
            result[k] = v
    return result


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    datetime_cols = ["created_at", "last_modified", "conversion_time", "interaction_time"]
    date_cols = ["report_date", "start_date", "end_date", "contract_start", "contract_end",
                 "effective_date_start", "effective_date_end"]

    with Session(engine) as session:
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

        for tsv_file, model in table_model_map:
            print(f"Loading {tsv_file} ...")
            # 注意: 不把字面量 "None" 当 NULL —— search_term_report.added_excluded
            # 用 'None' 表示"未处理"状态 (空值仍由 "" 表示)
            df = pl.read_csv(DATA_DIR / tsv_file, separator="\t", null_values=["", "null"])
            batch = []
            for row in df.iter_rows(named=True):
                clean_row = parse_datetime_fields(row, datetime_cols, date_cols)
                batch.append(model(**clean_row))
                if len(batch) >= 10_000:
                    session.bulk_save_objects(batch)
                    session.flush()
                    batch = []
            if batch:
                session.bulk_save_objects(batch)
                session.flush()
        session.commit()

    print(f"\nCreated SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("=" * 60)
    print("Search Ads 360 Agent — Data Generator (Lumenly Ads)")
    print("=" * 60)
    print(f"Reference date TODAY = {TODAY}")
    print()
    summary = generate_all_tsv()
    create_sqlite_database()
    print("\n" + "=" * 60)
    print("Generation Summary")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:20s} = {v:>10,}")
    print("\nAll done!")


if __name__ == "__main__":
    main()
