"""
Media - Podcast Advertising Economics 模拟数据生成器
复杂度: High
生成方: Fake Data Generator Agent

业务背景:
StreamCast Media 是一家美国的播客广告平台 (类似 Spotify 的 Megaphone 或 Acast),
为 150 多档播客运营动态广告插入 (DAI) 技术。本数据集模拟了该平台跨越 60 天运营的
完整广告生态系统,支持以下分析:

1. 营收优化: 按受众 segment 划分的 CPM 定价、各时段的 fill rate
2. 广告主 ROI: campaign 表现、CTR / completion rate、单次获客成本
3. 库存管理: 广告位利用率、高峰 / 低谷时段的定价机会
4. 听众体验: 广告疲劳 (ad fatigue) 检测、skip rate、最优广告频次
5. 播客变现: 按内容类目划分的 RPM (revenue per thousand plays, 每千次播放营收)
6. 竞价动态: 出价竞争模式、win rate、budget pacing

数据集包含约 250 集播客、约 15,000 次播放会话、约 45,000 次广告 impression,
以及展示各广告主 segment 实时竞价动态的详细 auction 日志。
"""

from __future__ import annotations
import os
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
import random

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, Text, Date, Numeric, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "media_podcast_ad_economics_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# 参考 "今天" 被固定写死 (而非 datetime.now()),从而保证 60 天数据窗口可复现,
# 并与 SQL 查询中硬编码的 DATE('2026-06-21') 保持一致。
REFERENCE_DATE = datetime(2026, 6, 21)
WINDOW_START = REFERENCE_DATE - timedelta(days=60)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


class Podcast(Base):
    """播客节目元数据。"""
    __tablename__ = "podcast"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    podcast_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # Tech、Business、Health 等
    host_name: Mapped[str] = mapped_column(String(100), nullable=False)
    launch_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    avg_episode_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_completion_rate: Mapped[float] = mapped_column(Float, nullable=False)  # 听完整集的听众占比 (%)
    target_audience_age: Mapped[str] = mapped_column(String(20), nullable=False)  # 18-24、25-34 等
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PodcastEpisode(Base):
    """单集播客。"""
    __tablename__ = "podcast_episode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    podcast_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast.id"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    publish_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    total_plays_to_date: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AdSlotTemplate(Base):
    """标准广告位类型 (Pre-roll、Mid-roll、Post-roll)。"""
    __tablename__ = "ad_slot_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_type: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # pre_roll、mid_roll、post_roll
    slot_name: Mapped[str] = mapped_column(String(50), nullable=False)
    typical_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)  # 15、30、60 秒
    base_cpm_rate: Mapped[float] = mapped_column(Float, nullable=False)  # 每 1000 次 impression 的基础价格
    avg_completion_rate: Mapped[float] = mapped_column(Float, nullable=False)  # 未跳过广告的听众占比 (%)


class EpisodeAdSlot(Base):
    """每集内部的具体广告位。"""
    __tablename__ = "episode_ad_slot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast_episode.id"), nullable=False)
    slot_template_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_slot_template.id"), nullable=False)
    position_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # 该广告在本集中出现的位置
    max_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)


class Advertiser(Base):
    """购买广告库存的公司。"""
    __tablename__ = "advertiser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    industry_vertical: Mapped[str] = mapped_column(String(50), nullable=False)  # E-commerce、FinTech、SaaS、CPG 等
    account_manager_email: Mapped[str] = mapped_column(String(100), nullable=False)
    onboarding_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    avg_cpa_target: Mapped[float] = mapped_column(Float, nullable=True)  # 单次获客成本 (CPA) 目标
    competitor_exclusion_list: Mapped[str] = mapped_column(Text, nullable=True)  # 逗号分隔的 advertiser ID 列表


class AdCampaign(Base):
    """广告主投放的广告 campaign。"""
    __tablename__ = "ad_campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(150), nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # 生命周期 / 对外宣称的总预算
    window_budget_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)  # 投放于本 60 天窗口的预算 (按实际投放量定标 -> 让 pacing / burn 类查询有意义)
    daily_budget_cap_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    target_impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    max_bid_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # 最高 CPM 出价
    target_segment_age: Mapped[str] = mapped_column(String(50), nullable=True)  # 例如 "25-34,35-44"
    target_segment_geo: Mapped[str] = mapped_column(String(100), nullable=True)  # 例如 "US-CA,US-NY"
    target_podcast_category: Mapped[str] = mapped_column(String(100), nullable=True)  # 例如 "Tech,Business"


class AdCreative(Base):
    """广告创意素材 (音频文件、脚本)。"""
    __tablename__ = "ad_creative"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_campaign.id"), nullable=False)
    creative_name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)  # 15、30 或 60 秒
    audio_file_url: Mapped[str] = mapped_column(String(300), nullable=False)
    script_text: Mapped[str] = mapped_column(Text, nullable=True)
    has_call_to_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(Date, nullable=True)


class Listener(Base):
    """播客听众 (已匿名化)。"""
    __tablename__ = "listener"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listener_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    age_group: Mapped[str] = mapped_column(String(20), nullable=False)  # 18-24、25-34、35-44 等
    gender: Mapped[str] = mapped_column(String(10), nullable=True)
    location_state: Mapped[str] = mapped_column(String(2), nullable=False)  # 美国州代码
    location_metro: Mapped[str] = mapped_column(String(50), nullable=True)  # 都会区
    first_listen_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_listening_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_ad_skip_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 跳过广告的占比 (%)
    is_premium_subscriber: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ListenerSegment(Base):
    """用于定向投放的兴趣 / 行为 segment。"""
    __tablename__ = "listener_segment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listener_id: Mapped[int] = mapped_column(Integer, ForeignKey("listener.id"), nullable=False)
    segment_name: Mapped[str] = mapped_column(String(50), nullable=False)  # Tech_Enthusiast、Fitness_Oriented 等
    segment_score: Mapped[float] = mapped_column(Float, nullable=False)  # 置信度评分 0-1
    assigned_date: Mapped[datetime] = mapped_column(Date, nullable=False)


class PlaySession(Base):
    """单次收听会话。"""
    __tablename__ = "play_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listener_id: Mapped[int] = mapped_column(Integer, ForeignKey("listener.id"), nullable=False)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast_episode.id"), nullable=False)
    session_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    session_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    total_play_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)  # 实际收听时长
    completion_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)  # mobile、desktop、smart_speaker
    playback_speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # 1x、1.5x、2x


class AdImpression(Base):
    """广告投放记录 (每播放一条广告对应一行)。"""
    __tablename__ = "ad_impression"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    play_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("play_session.id"), nullable=False)
    ad_slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("episode_ad_slot.id"), nullable=False)
    creative_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_creative.id"), nullable=False)
    impression_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    winning_bid_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # auction 胜出价格
    actual_charge_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # second-price auction 结果
    ad_duration_played_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    was_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    skip_after_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    was_completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    was_clicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 听众点击了广告链接
    converted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 点击后转化


class AdAuctionLog(Base):
    """实时竞价 (RTB) auction 日志 (每个 impression 记录所有出价)。"""
    __tablename__ = "ad_auction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    impression_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_impression.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_campaign.id"), nullable=False)
    bid_cpm: Mapped[float] = mapped_column(Float, nullable=False)
    bid_rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=胜出者, 2=第二名, 以此类推
    won_auction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bid_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    audience_match_score: Mapped[float] = mapped_column(Float, nullable=True)  # 听众与定向条件的匹配程度


class RevenueSettlement(Base):
    """每日营收结算与分成。"""
    __tablename__ = "revenue_settlement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    settlement_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    podcast_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast.id"), nullable=False)
    total_impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    total_revenue_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # StreamCast 抽取的 30%
    podcast_payout_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # 创作者获得的 70% 分成
    rpm: Mapped[float] = mapped_column(Float, nullable=False)  # 每 1000 次播放的营收
    avg_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # 当日平均 CPM
    fill_rate: Mapped[float] = mapped_column(Float, nullable=False)  # 已填充广告位的占比 (%)


# ============================================================================
# 数据生成函数
# ============================================================================

def generate_podcasts(n: int = 50) -> list[dict]:
    """生成播客节目。"""
    categories = [
        "Technology", "Business", "Health & Wellness", "True Crime", "Comedy",
        "News & Politics", "Education", "Sports", "Science", "Arts", "Finance"
    ]
    age_groups = ["18-24", "25-34", "35-44", "45-54", "55+"]

    # 精选的知名节目,使得按精确 podcast_name 过滤的 SQL 示例
    # (例如 Query 14/15 -> 'Tech Explained') 真正能返回行。它们永远不是 premium,
    # 且时长足够 (>20 分钟) 以容纳一个 mid-roll 广告位。
    curated = [
        {"podcast_name": "Tech Explained", "category": "Technology", "avg_episode_duration_min": 45},
        {"podcast_name": "Business Breakdown", "category": "Business", "avg_episode_duration_min": 45},
    ]

    podcasts = []
    for i in range(1, n + 1):
        if i <= len(curated):
            c = curated[i - 1]
            category = c["category"]
            podcast_name = c["podcast_name"]
            duration_min = c["avg_episode_duration_min"]
            is_premium = False
        else:
            category = random.choice(categories)
            podcast_name = f"{fake.catch_phrase()} Podcast"
            duration_min = random.choice([20, 30, 45, 60, 90])
            is_premium = random.random() < 0.15  # 15% 为 premium 播客
        # 锚定到 REFERENCE_DATE (而非真实的系统时钟),以实现完全可复现。
        launch_date = fake.date_between_dates(
            date_start=REFERENCE_DATE.date() - timedelta(days=365 * 3),
            date_end=REFERENCE_DATE.date() - timedelta(days=182),
        )

        podcasts.append({
            "id": i,
            "podcast_name": podcast_name,
            "category": category,
            "host_name": fake.name(),
            "launch_date": launch_date,
            "avg_episode_duration_min": duration_min,
            "subscriber_count": random.randint(1000, 500000),
            "avg_completion_rate": round(random.uniform(0.55, 0.92), 2),
            "target_audience_age": random.choice(age_groups),
            "is_premium": is_premium
        })

    return podcasts


def generate_episodes(podcasts: list[dict], episodes_per_podcast: int = 5) -> list[dict]:
    """生成播客单集。"""
    episodes = []
    episode_id = 1
    start_date = WINDOW_START

    for podcast in podcasts:
        num_episodes = random.randint(3, episodes_per_podcast)
        for ep_num in range(1, num_episodes + 1):
            publish_date = start_date + timedelta(days=random.randint(0, 60))
            duration = podcast["avg_episode_duration_min"] * 60 + random.randint(-300, 300)

            episodes.append({
                "id": episode_id,
                "podcast_id": podcast["id"],
                "episode_number": ep_num,
                "title": f"Episode {ep_num}: {fake.catch_phrase()}",
                "publish_date": publish_date,
                "duration_seconds": max(600, duration),
                "description": fake.text(200),
                "total_plays_to_date": random.randint(100, 50000)
            })
            episode_id += 1

    return episodes


def generate_ad_slot_templates() -> list[dict]:
    """生成标准广告位类型。"""
    return [
        {
            "id": 1,
            "slot_type": "pre_roll",
            "slot_name": "Pre-Roll Ad",
            "typical_duration_sec": 30,
            "base_cpm_rate": 15.0,
            "avg_completion_rate": 0.88
        },
        {
            "id": 2,
            "slot_type": "mid_roll",
            "slot_name": "Mid-Roll Ad",
            "typical_duration_sec": 60,
            "base_cpm_rate": 25.0,
            "avg_completion_rate": 0.95
        },
        {
            "id": 3,
            "slot_type": "post_roll",
            "slot_name": "Post-Roll Ad",
            "typical_duration_sec": 30,
            "base_cpm_rate": 8.0,
            "avg_completion_rate": 0.42
        }
    ]


def generate_episode_ad_slots(episodes: list[dict]) -> list[dict]:
    """为每集生成广告位。"""
    slots = []
    slot_id = 1

    for episode in episodes:
        duration = episode["duration_seconds"]

        # Pre-roll (始终在开头)
        slots.append({
            "id": slot_id,
            "episode_id": episode["id"],
            "slot_template_id": 1,  # pre_roll
            "position_seconds": 0,
            "max_duration_sec": 30
        })
        slot_id += 1

        # Mid-roll (对于时长 > 20 分钟的单集,放在中点附近)
        if duration > 1200:
            slots.append({
                "id": slot_id,
                "episode_id": episode["id"],
                "slot_template_id": 2,  # mid_roll
                "position_seconds": duration // 2,
                "max_duration_sec": 60
            })
            slot_id += 1

        # Post-roll (在结尾)
        slots.append({
            "id": slot_id,
            "episode_id": episode["id"],
            "slot_template_id": 3,  # post_roll
            "position_seconds": duration - 30,
            "max_duration_sec": 30
        })
        slot_id += 1

    return slots


def generate_advertisers(n: int = 40) -> list[dict]:
    """生成广告主。"""
    industries = [
        "E-commerce", "FinTech", "SaaS", "CPG", "Automotive",
        "Healthcare", "Education", "Entertainment", "Travel", "Real Estate"
    ]

    # 精选的真实品牌,使得按精确公司 / campaign 名称过滤的 SQL 示例
    # (Query 7/8/11/12/24) 能返回行而非空集。CPG 集群还
    # 携带 competitor_exclusion_list (Coca-Cola <-> Pepsi <-> Dr Pepper)。
    curated = [
        {"company_name": "Nike", "industry_vertical": "E-commerce"},
        {"company_name": "SquareSpace", "industry_vertical": "SaaS"},
        {"company_name": "HelloFresh", "industry_vertical": "E-commerce"},
        {"company_name": "Adobe", "industry_vertical": "SaaS"},
        {"company_name": "Robinhood", "industry_vertical": "FinTech"},
        {"company_name": "Coca-Cola", "industry_vertical": "CPG", "competitors": ["Pepsi", "Dr Pepper"]},
        {"company_name": "Pepsi", "industry_vertical": "CPG", "competitors": ["Coca-Cola", "Dr Pepper"]},
        {"company_name": "Dr Pepper", "industry_vertical": "CPG", "competitors": ["Coca-Cola", "Pepsi"]},
        {"company_name": "Olipop", "industry_vertical": "CPG"},
        {"company_name": "Geico", "industry_vertical": "FinTech"},
        {"company_name": "Ford", "industry_vertical": "Automotive"},
    ]
    name_to_id = {c["company_name"]: idx + 1 for idx, c in enumerate(curated)}

    advertisers = []
    for i in range(1, n + 1):
        onboarding_date = fake.date_between_dates(
            date_start=REFERENCE_DATE.date() - timedelta(days=365 * 2),
            date_end=REFERENCE_DATE.date() - timedelta(days=30),
        )

        if i <= len(curated):
            c = curated[i - 1]
            company_name = c["company_name"]
            vertical = c["industry_vertical"]
            competitors = c.get("competitors")
            exclusion = (
                ",".join(str(name_to_id[x]) for x in competitors if x in name_to_id)
                if competitors else None
            )
        else:
            company_name = fake.company()
            vertical = random.choice(industries)
            exclusion = None

        advertisers.append({
            "id": i,
            "company_name": company_name,
            "industry_vertical": vertical,
            "account_manager_email": fake.company_email(),
            "onboarding_date": onboarding_date,
            "total_budget_usd": round(random.uniform(10000, 500000), 2),
            "avg_cpa_target": round(random.uniform(5, 50), 2) if random.random() > 0.3 else None,
            "competitor_exclusion_list": exclusion
        })

    return advertisers


def generate_campaigns(advertisers: list[dict]) -> list[dict]:
    """生成广告 campaign。"""
    campaigns = []
    campaign_id = 1
    start_date = WINDOW_START

    age_targets = ["18-24", "25-34", "35-44", "45-54", "25-34,35-44"]
    geo_targets = ["US-CA", "US-NY", "US-TX", "US-CA,US-NY", None]
    geo_targets_nonnull = [g for g in geo_targets if g]
    category_targets = ["Technology", "Business", "Health & Wellness", "Technology,Business", None]
    category_targets_nonnull = [c for c in category_targets if c]

    # 特定 SQL 示例 (Query 7 / Query 8) 据以过滤的精确 campaign 名称。
    forced_campaign_names = {
        "Nike": ["Nike - Running Shoes Spring Launch"],
        "SquareSpace": ["SquareSpace - Website Builder Promotion"],
    }
    curated_names = {
        "Nike", "SquareSpace", "HelloFresh", "Adobe", "Robinhood",
        "Coca-Cola", "Pepsi", "Dr Pepper", "Olipop", "Geico", "Ford",
    }

    for advertiser in advertisers:
        is_curated = advertiser["company_name"] in curated_names
        forced = forced_campaign_names.get(advertiser["company_name"], [])
        # 精选品牌始终投放 3 个 campaign,覆盖窗口的大部分时段并设置有竞争力的
        # max bid,从而让示例查询有足够的数据量。
        num_campaigns = 3 if is_curated else random.randint(1, 3)

        for idx in range(num_campaigns):
            if is_curated:
                campaign_start = start_date + timedelta(days=random.randint(0, 10))
                campaign_end = campaign_start + timedelta(days=random.randint(45, 60))
                max_bid = round(random.uniform(20, 40), 2)
                # 非空的定向条件,使得定向有效性查询 (Query 9) 有信号。
                target_age = random.choice(age_targets)
                target_geo = random.choice(geo_targets_nonnull)
                target_cat = random.choice(category_targets_nonnull)
            else:
                campaign_start = start_date + timedelta(days=random.randint(0, 30))
                campaign_end = campaign_start + timedelta(days=random.randint(14, 60))
                max_bid = round(random.uniform(8, 40), 2)
                target_age = random.choice(age_targets)
                target_geo = random.choice(geo_targets)
                target_cat = random.choice(category_targets)

            campaign_budget = advertiser["total_budget_usd"] / num_campaigns
            campaign_name = forced[idx] if idx < len(forced) else f"{advertiser['company_name']} - {fake.bs().title()}"

            campaigns.append({
                "id": campaign_id,
                "advertiser_id": advertiser["id"],
                "campaign_name": campaign_name,
                "start_date": campaign_start.date(),
                "end_date": campaign_end.date(),
                "total_budget_usd": round(campaign_budget, 2),
                "window_budget_usd": None,  # 在 impression 生成后回填 (按真实投放量定标)
                "daily_budget_cap_usd": round(campaign_budget / ((campaign_end - campaign_start).days + 1), 2),
                "target_impressions": random.randint(10000, 500000),
                "max_bid_cpm": max_bid,
                "target_segment_age": target_age,
                "target_segment_geo": target_geo,
                "target_podcast_category": target_cat
            })
            campaign_id += 1

    return campaigns


def generate_ad_creatives(campaigns: list[dict]) -> list[dict]:
    """生成广告创意素材。"""
    creatives = []
    creative_id = 1

    for campaign in campaigns:
        num_creatives = random.randint(2, 3)  # 每个 campaign 2-3 个创意用于 A/B 测试 (依据 ER 文档)
        for i in range(num_creatives):
            duration = random.choice([15, 30, 60])
            created = datetime.strptime(str(campaign["start_date"]), "%Y-%m-%d") - timedelta(days=random.randint(7, 30))

            creatives.append({
                "id": creative_id,
                "campaign_id": campaign["id"],
                "creative_name": f"Creative {i+1} - {duration}s",
                "duration_sec": duration,
                "audio_file_url": f"https://cdn.streamcast.media/ads/{creative_id}.mp3",
                "script_text": fake.text(100),
                "has_call_to_action": random.random() > 0.2,
                "created_date": created.date(),
                "expiry_date": campaign["end_date"]
            })
            creative_id += 1

    return creatives


def generate_listeners(n: int = 5000) -> list[dict]:
    """生成听众。"""
    age_groups = ["18-24", "25-34", "35-44", "45-54", "55+"]
    genders = ["M", "F", "Other", None]
    us_states = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
    metros = ["Los Angeles", "New York", "Chicago", "Houston", "Phoenix", "San Francisco", "Seattle"]

    listeners = []
    for i in range(1, n + 1):
        first_listen = fake.date_between_dates(
            date_start=REFERENCE_DATE.date() - timedelta(days=365),
            date_end=REFERENCE_DATE.date() - timedelta(days=7),
        )

        listeners.append({
            "id": i,
            "listener_uuid": fake.uuid4(),
            "age_group": random.choice(age_groups),
            "gender": random.choice(genders),
            "location_state": random.choice(us_states),
            "location_metro": random.choice(metros) if random.random() > 0.3 else None,
            "first_listen_date": first_listen,
            "total_listening_hours": round(random.uniform(5, 500), 1),
            "avg_ad_skip_rate": round(random.uniform(0.1, 0.7), 2),
            "is_premium_subscriber": random.random() < 0.1
        })

    return listeners


def generate_listener_segments(listeners: list[dict]) -> list[dict]:
    """为听众生成行为 segment。"""
    segments_pool = [
        "Tech_Enthusiast", "Fitness_Oriented", "Finance_Savvy", "Early_Adopter",
        "Frequent_Traveler", "Foodie", "DIY_Home", "Car_Enthusiast", "Pet_Owner",
        "Parent", "Gamer", "Fashion_Forward", "Health_Conscious"
    ]

    listener_segments = []
    segment_id = 1

    for listener in listeners:
        # 每个听众分配 1-3 个 segment
        num_segments = random.randint(1, 3)
        assigned_segments = random.sample(segments_pool, num_segments)

        for seg_name in assigned_segments:
            listener_segments.append({
                "id": segment_id,
                "listener_id": listener["id"],
                "segment_name": seg_name,
                "segment_score": round(random.uniform(0.5, 1.0), 2),
                "assigned_date": listener["first_listen_date"]
            })
            segment_id += 1

    return listener_segments


def generate_play_sessions(listeners: list[dict], episodes: list[dict], n: int = 15000) -> list[dict]:
    """生成收听会话。"""
    device_types = ["mobile", "desktop", "smart_speaker"]
    playback_speeds = [1.0, 1.0, 1.0, 1.0, 1.5, 1.5, 2.0]  # 权重偏向 1x

    sessions = []
    window_start = WINDOW_START
    reference = REFERENCE_DATE

    i = 1
    attempts = 0
    max_attempts = n * 4  # 安全上限; 对被跳过的行进行重试,从而仍能达到约 n 个会话
    while len(sessions) < n and attempts < max_attempts:
        attempts += 1
        listener = random.choice(listeners)
        episode = random.choice(episodes)

        # 对于非常热门的单集,对非 premium 听众进行部分限流
        if episode["total_plays_to_date"] > 100000 and not listener["is_premium_subscriber"]:
            if random.random() < 0.5:  # 50% 的概率跳过 (随后重新随机抽取再试)
                continue

        # 会话的开始时间不可能早于单集发布时间、早于数据
        # 窗口,或早于该听众的 first-listen 日期。
        publish = episode["publish_date"]
        first_listen_dt = datetime.combine(listener["first_listen_date"], datetime.min.time())
        earliest = max(publish, window_start, first_listen_dt)
        if earliest >= reference:
            continue
        span_seconds = int((reference - earliest).total_seconds())
        session_start = earliest + timedelta(seconds=random.randint(0, span_seconds))

        # 模拟真实的收听行为
        completion_pct = random.uniform(0.15, 1.0)
        if random.random() < 0.25:  # 25% 为高度投入的听众
            completion_pct = random.uniform(0.85, 1.0)

        play_duration = int(episode["duration_seconds"] * completion_pct)
        session_end = session_start + timedelta(seconds=play_duration)

        sessions.append({
            "id": i,
            "listener_id": listener["id"],
            "episode_id": episode["id"],
            "session_start_time": session_start,
            "session_end_time": session_end,
            "total_play_duration_sec": play_duration,
            "completion_percentage": round(completion_pct * 100, 1),
            "device_type": random.choice(device_types),
            "playback_speed": random.choice(playback_speeds)
        })
        i += 1

    return sessions


def generate_ad_impressions_and_auctions(
    sessions: list[dict],
    ad_slots: list[dict],
    creatives: list[dict],
    campaigns: list[dict],
    listeners: list[dict],
    episodes: list[dict],
    podcasts: list[dict],
    listener_segments: list[dict],
    advertisers: list[dict]
) -> tuple[list[dict], list[dict]]:
    """生成广告 impression 与 auction 日志,并带有真实的竞价过程。

    此处遵守的业务不变量:
    - premium 订阅者以及 premium (无广告) 播客均不产生任何 impression。
    - 每次出价都遵守广告位底价 (bid >= slot base_cpm) 与 campaign
      上限 (bid <= max_bid_cpm); 无法达到底价的 campaign 不具备参与资格。
    - 实际成交 CPM 遵循 mid_roll > pre_roll > post_roll 的定价梯度,因为
      出价锚定于广告位的 base CPM,而不仅仅是 campaign 的 max bid。
    - 定向 (age / geo / category / interest-segment) 会抬高付费意愿,因此
      高价值受众 (例如 Tech_Enthusiast) 与匹配的 campaign 以更高的 CPM 成交。
    """
    impressions = []
    auction_logs = []
    impression_id = 1
    auction_log_id = 1

    # 创建查找字典
    episode_slots_map = {}
    for slot in ad_slots:
        episode_slots_map.setdefault(slot["episode_id"], []).append(slot)

    campaign_creatives_map = {}
    for creative in creatives:
        campaign_creatives_map.setdefault(creative["campaign_id"], []).append(creative)

    listener_map = {l["id"]: l for l in listeners}
    episode_map = {e["id"]: e for e in episodes}
    podcast_map = {p["id"]: p for p in podcasts}
    advertiser_map = {a["id"]: a for a in advertisers}

    # listener_id -> interest-segment 名称集合
    listener_seg_map = {}
    for seg in listener_segments:
        listener_seg_map.setdefault(seg["listener_id"], set()).add(seg["segment_name"])

    # Slot template -> (base CPM 底价, 额外需求乘数)。Mid-roll 是最
    # 有价值的库存,因此它同时拥有最高的底价和需求溢价。
    slot_base_cpm = {1: 15.0, 2: 25.0, 3: 8.0}
    slot_demand_mult = {1: 1.0, 2: 1.15, 3: 0.9}
    # 各广告位每次 auction 的竞价者数量: mid-roll 竞争最激烈 (需求最高),pre-roll
    # 拥有最广的竞价池,post-roll 最薄 -> 保持 "mid-roll 争夺最激烈"
    # 与 ER 叙述一致 (下限保持 >=2,因此不会出现退化的单竞价者 auction)。
    slot_bidder_range = {1: (2, 6), 2: (4, 8), 3: (2, 4)}

    # 广告主 vertical -> 标志着高意向受众的 interest segment。
    vertical_pref_segments = {
        "SaaS": {"Tech_Enthusiast", "Early_Adopter"},
        "FinTech": {"Finance_Savvy", "Early_Adopter"},
        "E-commerce": {"Foodie", "Fashion_Forward", "Pet_Owner"},
        "CPG": {"Foodie", "Health_Conscious"},
        "Healthcare": {"Health_Conscious", "Fitness_Oriented"},
        "Automotive": {"Car_Enthusiast"},
        "Travel": {"Frequent_Traveler"},
        "Entertainment": {"Gamer"},
        "Education": {"Tech_Enthusiast"},
        "Real Estate": set(),
    }

    # 高价值受众吸引更密集的需求,因此其 auction 中的每一次出价都以更高的价格
    # 成交 -> 为 Query 3 (segment CPM 排名) 提供真实、单调的信号。
    high_value_segments = {
        "Tech_Enthusiast": 1.30,
        "Finance_Savvy": 1.30,
        "Early_Adopter": 1.15,
        "Health_Conscious": 1.12,
        "Fitness_Oriented": 1.10,
        "Frequent_Traveler": 1.08,
    }

    for session in sessions:
        listener = listener_map[session["listener_id"]]
        episode = episode_map[session["episode_id"]]
        podcast = podcast_map[episode["podcast_id"]]

        # 不向 premium 订阅者投放广告,premium 播客上也完全不投放广告。
        if listener["is_premium_subscriber"]:
            continue
        if podcast["is_premium"]:
            continue

        slots = episode_slots_map.get(session["episode_id"], [])
        session_date = session["session_start_time"].date()
        listener_segs = listener_seg_map.get(listener["id"], set())
        # 由该听众最具价值的 segment 驱动的、覆盖整个 auction 的需求溢价。
        listener_value_mult = max(
            (high_value_segments.get(s, 1.0) for s in listener_segs), default=1.0
        )

        for slot in slots:
            # 检查听众是否到达了该广告位置
            if session["total_play_duration_sec"] < slot["position_seconds"]:
                continue  # 听众在此广告之前就停止了收听

            base_cpm = slot_base_cpm.get(slot["slot_template_id"], 10.0)
            demand_mult = slot_demand_mult.get(slot["slot_template_id"], 1.0)

            # 具备资格 = 当日处于投放期 且 能够达到广告位底价。
            eligible_campaigns = [
                c for c in campaigns
                if c["start_date"] <= session_date <= c["end_date"]
                and c["max_bid_cpm"] >= base_cpm
            ]
            if not eligible_campaigns:
                continue  # 未填充 (未售出的库存)

            # 模拟 auction: 竞价者数量取决于广告位需求 (mid-roll 竞争最激烈)
            lo, hi = slot_bidder_range.get(slot["slot_template_id"], (2, 6))
            num_bidders = min(len(eligible_campaigns), random.randint(lo, hi))
            bidders = random.sample(eligible_campaigns, num_bidders)

            bids = []
            for campaign in bidders:
                vertical = advertiser_map[campaign["advertiser_id"]]["industry_vertical"]

                # 定向匹配: age / geo / category / interest-segment 亲和度。
                match_hits = 0
                match_dims = 0
                if campaign["target_segment_age"]:
                    match_dims += 1
                    if listener["age_group"] in campaign["target_segment_age"].split(","):
                        match_hits += 1
                if campaign["target_segment_geo"]:
                    match_dims += 1
                    geos = [g.replace("US-", "") for g in campaign["target_segment_geo"].split(",")]
                    if listener["location_state"] in geos:
                        match_hits += 1
                if campaign["target_podcast_category"]:
                    match_dims += 1
                    if podcast["category"] in campaign["target_podcast_category"].split(","):
                        match_hits += 1
                # interest-segment 亲和度始终算作一个维度。
                match_dims += 1
                pref = vertical_pref_segments.get(vertical, set())
                if pref and (listener_segs & pref):
                    match_hits += 1

                match_score = match_hits / match_dims if match_dims else 0.0

                # 定向最多可抬高付费意愿 +60%; 出价锚定于广告位底价;
                # 听众的 segment 价值会抬高整个 auction 的成交价格。
                targeting_premium = 0.6 * match_score
                desired = (
                    base_cpm * demand_mult * (1.0 + targeting_premium)
                    * listener_value_mult * random.uniform(0.92, 1.12)
                )
                bid_cpm = min(campaign["max_bid_cpm"], desired)
                bid_cpm = max(bid_cpm, base_cpm)  # 强制不低于底价

                bids.append({
                    "campaign": campaign,
                    "bid_cpm": round(bid_cpm, 2),
                    "match_score": round(match_score, 2)
                })

            # 按 CPM 排序出价 (从高到低)
            bids.sort(key=lambda x: x["bid_cpm"], reverse=True)

            # 胜出者支付第二高价 + $0.01 (second-price auction); 永不低于广告位
            # 底价,也永不高于胜出者自己的出价 (因此即使排名前二的出价四舍五入
            # 到相同值,winning_bid - actual >= 0 仍然成立)。
            winner = bids[0]
            second_price = bids[1]["bid_cpm"] if len(bids) > 1 else winner["bid_cpm"] * 0.9
            actual_charge = round(max(base_cpm, second_price + 0.01), 2)
            actual_charge = min(actual_charge, winner["bid_cpm"])

            # 从胜出的 campaign 中选择一个创意
            available_creatives = campaign_creatives_map.get(winner["campaign"]["id"], [])
            if not available_creatives:
                continue

            winning_creative = random.choice(available_creatives)

            # 判定广告是否被跳过 / 听完。
            # 基础 skip rate 是听众的容忍度,但匹配度更高 (更相关) 的
            # 广告被跳过得更少 -> 匹配的 impression 更常被听完。
            skip_probability = listener["avg_ad_skip_rate"] * (1.0 - 0.35 * winner["match_score"])
            was_skipped = random.random() < skip_probability

            if was_skipped:
                skip_after = random.randint(3, max(4, winning_creative["duration_sec"] - 5))
                ad_played = skip_after
                was_completed = False
            else:
                skip_after = None
                ad_played = winning_creative["duration_sec"]
                was_completed = True

            # 点击 / 转化信号 (仅在广告被完整听完时才有意义)。
            # 播客 CTR 较低 (约 0.5-1.5%),并随定向契合度 + CTA 而上升。
            was_clicked = False
            converted = False
            if was_completed:
                ctr = 0.005 + 0.012 * winner["match_score"]
                if winning_creative["has_call_to_action"]:
                    ctr += 0.004
                was_clicked = random.random() < ctr
                if was_clicked:
                    converted = random.random() < 0.15  # 约 15% 的点击会转化

            # 创建 impression
            impression_time = session["session_start_time"] + timedelta(seconds=slot["position_seconds"])

            impressions.append({
                "id": impression_id,
                "play_session_id": session["id"],
                "ad_slot_id": slot["id"],
                "creative_id": winning_creative["id"],
                "impression_time": impression_time,
                "winning_bid_cpm": winner["bid_cpm"],
                "actual_charge_cpm": actual_charge,
                "ad_duration_played_sec": ad_played,
                "was_skipped": was_skipped,
                "skip_after_seconds": skip_after,
                "was_completed": was_completed,
                "was_clicked": was_clicked,
                "converted": converted
            })

            # 为所有竞价者创建 auction 日志
            for rank, bid in enumerate(bids, start=1):
                auction_logs.append({
                    "id": auction_log_id,
                    "impression_id": impression_id,
                    "campaign_id": bid["campaign"]["id"],
                    "bid_cpm": bid["bid_cpm"],
                    "bid_rank": rank,
                    "won_auction": (rank == 1),
                    "bid_time": impression_time,
                    "audience_match_score": bid["match_score"]
                })
                auction_log_id += 1

            impression_id += 1

    return impressions, auction_logs


def generate_revenue_settlements(
    impressions: list[dict],
    sessions: list[dict],
    ad_slots: list[dict],
    episodes: list[dict],
    podcasts: list[dict],
    listeners: list[dict]
) -> list[dict]:
    """将真实的 ad_impression 行聚合为按 播客 x 天 维度的结算记录。

    这是对 impression 表的如实汇总 (而非随机数字):
    - total_impressions / total_revenue 直接来自当日的 impression。
    - platform_fee = 30%, podcast_payout = 70% (平台 / 创作者分成)。
    - rpm = (创作者分成 / 当日播放次数) * 1000  -> 创作者分成口径的 RPM。
    - avg_cpm = total_revenue / total_impressions * 1000      -> 加权 eCPM。
    - fill_rate = 该 播客 x 天 的 已填充广告位 / 可触达广告位。
    Premium 播客不投放广告,因此它们根本不会出现在这里。
    """
    episode_map = {e["id"]: e for e in episodes}
    podcast_map = {p["id"]: p for p in podcasts}
    session_map = {s["id"]: s for s in sessions}
    listener_map = {l["id"]: l for l in listeners}

    episode_slots_map = {}
    for slot in ad_slots:
        episode_slots_map.setdefault(slot["episode_id"], []).append(slot)

    filled = defaultdict(int)        # (podcast_id, date) -> 已填充的广告位数
    revenue = defaultdict(float)     # (podcast_id, date) -> 营收 (USD)
    plays = defaultdict(int)         # (podcast_id, date) -> 播放会话数
    available = defaultdict(int)     # (podcast_id, date) -> 可触达的广告位数

    # 播放数 (所有会话) 与可触达广告库存 (仅限可投放广告的会话)。
    for s in sessions:
        episode = episode_map[s["episode_id"]]
        podcast = podcast_map[episode["podcast_id"]]
        day = s["session_start_time"].date()
        key = (podcast["id"], day)
        plays[key] += 1

        listener = listener_map[s["listener_id"]]
        if listener["is_premium_subscriber"] or podcast["is_premium"]:
            continue
        reachable = sum(
            1 for slot in episode_slots_map.get(episode["id"], [])
            if s["total_play_duration_sec"] >= slot["position_seconds"]
        )
        available[key] += reachable

    # 来自真实 impression 的已填充广告位 + 营收。以 会话 的开始日期作为键
    # (与 plays/available 使用相同的键),从而使跨越午夜的 mid/post-roll 不会落入
    # 与其会话不同的某一天 -> 避免出现 available=0/fill_rate=0 的结算行。
    for imp in impressions:
        s = session_map[imp["play_session_id"]]
        episode = episode_map[s["episode_id"]]
        day = s["session_start_time"].date()
        key = (episode["podcast_id"], day)
        filled[key] += 1
        revenue[key] += imp["actual_charge_cpm"] / 1000.0

    settlements = []
    settlement_id = 1
    for key in sorted(filled.keys()):
        podcast_id, day = key
        total_impressions = filled[key]
        total_revenue = revenue[key]
        platform_fee = total_revenue * 0.30
        podcast_payout = total_revenue * 0.70

        day_plays = plays.get(key, total_impressions)
        rpm = (podcast_payout / day_plays) * 1000 if day_plays > 0 else 0.0
        avg_cpm = (total_revenue / total_impressions) * 1000 if total_impressions > 0 else 0.0

        avail = available.get(key, 0)
        fill_rate = (total_impressions / avail) if avail > 0 else 0.0
        fill_rate = min(fill_rate, 1.0)

        settlements.append({
            "id": settlement_id,
            "settlement_date": day,
            "podcast_id": podcast_id,
            "total_impressions": total_impressions,
            "total_revenue_usd": round(total_revenue, 2),
            "platform_fee_usd": round(platform_fee, 2),
            "podcast_payout_usd": round(podcast_payout, 2),
            "rpm": round(rpm, 2),
            "avg_cpm": round(avg_cpm, 2),
            "fill_rate": round(fill_rate, 3)
        })
        settlement_id += 1

    return settlements


def assign_window_budgets(campaigns: list[dict], creatives: list[dict], impressions: list[dict]) -> None:
    """根据每个 campaign 在窗口内的实际投放量回填其 `window_budget_usd`。

    `total_budget_usd` 是生命周期 / 广告主量级的对外宣称数字,因此在 60 天的
    样本上几乎未被消耗 (花费只有几美元到几十美元),导致 budget-pacing
    查询退化 (Q5 不返回任何结果,Q23 把一切都标记为 "too slow")。

    而 `window_budget_usd` = 花费 / utilization,其中 utilization 取自一个
    真实的混合分布 (部分 campaign 接近耗尽,多数健康,部分缓慢)。这使得
    Q5 (burn-down 告警)、Q23 (pacing 方差) 与 Q7 (预算 utilization) 能产生
    有意义且多样化的结果,同时保留宏大的对外宣称预算以服务叙述。
    就地修改 campaign 字典。
    """
    creative_to_campaign = {cr["id"]: cr["campaign_id"] for cr in creatives}
    spend = defaultdict(float)
    for imp in impressions:
        cid = creative_to_campaign.get(imp["creative_id"])
        if cid is not None:
            spend[cid] += imp["actual_charge_cpm"] / 1000.0

    for c in campaigns:
        spent = spend.get(c["id"], 0.0)
        r = random.random()
        if r < 0.25:
            utilization = random.uniform(0.90, 0.99)   # 接近耗尽 -> 触发 Q5 告警
        elif r < 0.75:
            utilization = random.uniform(0.45, 0.85)   # 健康的 pacing
        else:
            utilization = random.uniform(0.15, 0.45)   # 缓慢消耗 -> Q23 "too slow"

        if spent > 0:
            window_budget = spent / utilization
        else:
            # 本窗口无投放: 一个较小的名义投放预算会被读作 "slow"。
            window_budget = random.uniform(20, 120)
        # 投放预算永远不能低于已花费的金额。
        c["window_budget_usd"] = round(max(window_budget, spent), 2)
        # 让 (虽未使用但已记录的) daily cap 与 window budget 保持一致:
        # 一个均匀 pacing 的每日上限,且永不超过整个窗口的投放预算。
        days = (c["end_date"] - c["start_date"]).days + 1
        c["daily_budget_cap_usd"] = round(c["window_budget_usd"] / days, 2) if days > 0 else c["window_budget_usd"]


# ============================================================================
# 主生成逻辑
# ============================================================================

def write_tsv(data: list[dict], filepath: Path):
    """使用 Polars 将数据写入 TSV 文件。"""
    if not data:
        print(f"Warning: No data to write for {filepath}")
        return
    df = pl.DataFrame(data)
    df.write_csv(filepath, separator="\t")
    print(f"✓ Generated {filepath.name}: {len(data)} rows")


def main():
    """主数据生成编排流程。"""
    print("=" * 80)
    print("Media - Podcast Advertising Economics Data Generator")
    print("=" * 80)

    # 清理旧数据
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True)

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    print("\n[1/14] Generating podcasts...")
    podcasts = generate_podcasts(50)
    write_tsv(podcasts, DATA_DIR / "01_podcast.tsv")

    print("[2/14] Generating podcast episodes...")
    episodes = generate_episodes(podcasts, episodes_per_podcast=5)
    write_tsv(episodes, DATA_DIR / "02_podcast_episode.tsv")

    print("[3/14] Generating ad slot templates...")
    ad_slot_templates = generate_ad_slot_templates()
    write_tsv(ad_slot_templates, DATA_DIR / "03_ad_slot_template.tsv")

    print("[4/14] Generating episode ad slots...")
    ad_slots = generate_episode_ad_slots(episodes)
    write_tsv(ad_slots, DATA_DIR / "04_episode_ad_slot.tsv")

    print("[5/14] Generating advertisers...")
    advertisers = generate_advertisers(40)
    write_tsv(advertisers, DATA_DIR / "05_advertiser.tsv")

    print("[6/14] Generating ad campaigns...")
    campaigns = generate_campaigns(advertisers)
    # 注意: window_budget_usd 在 impression 生成后才回填,因此 campaign 的 TSV
    # 会在稍后写入 (见 step 11 之后),届时每个 campaign 的真实投放量已知。

    print("[7/14] Generating ad creatives...")
    creatives = generate_ad_creatives(campaigns)
    write_tsv(creatives, DATA_DIR / "07_ad_creative.tsv")

    print("[8/14] Generating listeners...")
    listeners = generate_listeners(5000)
    write_tsv(listeners, DATA_DIR / "08_listener.tsv")

    print("[9/14] Generating listener segments...")
    listener_segments = generate_listener_segments(listeners)
    write_tsv(listener_segments, DATA_DIR / "09_listener_segment.tsv")

    print("[10/14] Generating play sessions...")
    sessions = generate_play_sessions(listeners, episodes, 15000)
    write_tsv(sessions, DATA_DIR / "10_play_session.tsv")

    print("[11/14] Generating ad impressions and auction logs (this may take a moment)...")
    impressions, auction_logs = generate_ad_impressions_and_auctions(
        sessions, ad_slots, creatives, campaigns, listeners, episodes,
        podcasts, listener_segments, advertisers
    )
    # 将每个 campaign 的投放 window budget 按其实际投放量定标,然后写入
    # (此前延后的) campaign 表,使 budget-pacing 查询 Q5/Q23/Q7 具有意义。
    assign_window_budgets(campaigns, creatives, impressions)
    write_tsv(campaigns, DATA_DIR / "06_ad_campaign.tsv")
    write_tsv(impressions, DATA_DIR / "11_ad_impression.tsv")
    write_tsv(auction_logs, DATA_DIR / "12_ad_auction_log.tsv")

    print("[13/14] Generating revenue settlements...")
    settlements = generate_revenue_settlements(
        impressions, sessions, ad_slots, episodes, podcasts, listeners
    )
    write_tsv(settlements, DATA_DIR / "13_revenue_settlement.tsv")

    # ========================================================================
    # 创建 SQLite 数据库
    # ========================================================================
    print("\n[14/14] Creating SQLite database...")
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 将 TSV 文件加载进数据库
    table_files = [
        ("podcast", "01_podcast.tsv"),
        ("podcast_episode", "02_podcast_episode.tsv"),
        ("ad_slot_template", "03_ad_slot_template.tsv"),
        ("episode_ad_slot", "04_episode_ad_slot.tsv"),
        ("advertiser", "05_advertiser.tsv"),
        ("ad_campaign", "06_ad_campaign.tsv"),
        ("ad_creative", "07_ad_creative.tsv"),
        ("listener", "08_listener.tsv"),
        ("listener_segment", "09_listener_segment.tsv"),
        ("play_session", "10_play_session.tsv"),
        ("ad_impression", "11_ad_impression.tsv"),
        ("ad_auction_log", "12_ad_auction_log.tsv"),
        ("revenue_settlement", "13_revenue_settlement.tsv"),
    ]

    with Session(engine) as session:
        for table_name, filename in table_files:
            df = pl.read_csv(DATA_DIR / filename, separator="\t")
            df.write_database(table_name, connection=engine, if_table_exists="append")
            print(f"  ✓ Loaded {filename} into {table_name} table")

    print("\n" + "=" * 80)
    print("✓ Data generation complete!")
    print("=" * 80)
    print(f"\nGenerated files:")
    print(f"  - {len(table_files)} TSV files in {DATA_DIR}")
    print(f"  - SQLite database: {DATABASE_PATH}")
    print(f"\nDataset summary:")
    print(f"  - Podcasts: {len(podcasts)}")
    print(f"  - Episodes: {len(episodes)}")
    print(f"  - Advertisers: {len(advertisers)}")
    print(f"  - Campaigns: {len(campaigns)}")
    print(f"  - Listeners: {len(listeners)}")
    print(f"  - Play Sessions: {len(sessions)}")
    print(f"  - Ad Impressions: {len(impressions)}")
    print(f"  - Auction Logs: {len(auction_logs)}")
    print(f"  - Total Records: ~{len(podcasts) + len(episodes) + len(advertisers) + len(campaigns) + len(creatives) + len(listeners) + len(listener_segments) + len(sessions) + len(impressions) + len(auction_logs) + len(settlements):,}")


if __name__ == "__main__":
    main()
