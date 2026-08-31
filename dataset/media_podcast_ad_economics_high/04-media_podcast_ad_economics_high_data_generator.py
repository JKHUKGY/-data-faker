"""
Media - Podcast Advertising Economics simulation data generator
Complexity: High
Producer: Fake Data Generator Agent

Business background:
StreamCast Media is a US podcast ad platform (comparable to Spotify's Megaphone
or Acast) that runs dynamic ad insertion (DAI) for 150+ podcasts. This dataset
simulates the platform's complete ad ecosystem over a 60-day operating window,
supporting the following analyses:

1. Revenue optimization: CPM pricing by audience segment, fill rate by daypart
2. Advertiser ROI: campaign performance, CTR / completion rate, cost per acquisition
3. Inventory management: ad slot utilization, peak / off-peak pricing opportunities
4. Listener experience: ad fatigue detection, skip rate, optimal ad frequency
5. Podcast monetization: RPM (revenue per thousand plays) by content category
6. Auction dynamics: bid competition patterns, win rate, budget pacing

The dataset includes ~250 podcast episodes, ~15,000 play sessions, and
~45,000 ad impressions, along with detailed auction logs that capture real-time
bidding dynamics across advertiser segments.
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
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "media_podcast_ad_economics_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# The reference "today" is hard-coded (rather than datetime.now()) so the 60-day
# data window is reproducible and aligns with the hard-coded DATE('2026-06-21')
# in the SQL queries.
REFERENCE_DATE = datetime(2026, 6, 21)
WINDOW_START = REFERENCE_DATE - timedelta(days=60)


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Podcast(Base):
    """Podcast show metadata."""
    __tablename__ = "podcast"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    podcast_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # Tech, Business, Health, etc.
    host_name: Mapped[str] = mapped_column(String(100), nullable=False)
    launch_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    avg_episode_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_completion_rate: Mapped[float] = mapped_column(Float, nullable=False)  # % of listeners who finish a full episode
    target_audience_age: Mapped[str] = mapped_column(String(20), nullable=False)  # 18-24, 25-34, etc.
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PodcastEpisode(Base):
    """A single podcast episode."""
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
    """Standard ad slot types (Pre-roll, Mid-roll, Post-roll)."""
    __tablename__ = "ad_slot_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_type: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # pre_roll, mid_roll, post_roll
    slot_name: Mapped[str] = mapped_column(String(50), nullable=False)
    typical_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)  # 15, 30, 60 seconds
    base_cpm_rate: Mapped[float] = mapped_column(Float, nullable=False)  # base price per 1000 impressions
    avg_completion_rate: Mapped[float] = mapped_column(Float, nullable=False)  # % of listeners who do not skip the ad


class EpisodeAdSlot(Base):
    """A specific ad slot within a single episode."""
    __tablename__ = "episode_ad_slot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast_episode.id"), nullable=False)
    slot_template_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_slot_template.id"), nullable=False)
    position_seconds: Mapped[int] = mapped_column(Integer, nullable=False)  # where in the episode the ad appears
    max_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)


class Advertiser(Base):
    """A company purchasing ad inventory."""
    __tablename__ = "advertiser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    industry_vertical: Mapped[str] = mapped_column(String(50), nullable=False)  # E-commerce, FinTech, SaaS, CPG, etc.
    account_manager_email: Mapped[str] = mapped_column(String(100), nullable=False)
    onboarding_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    avg_cpa_target: Mapped[float] = mapped_column(Float, nullable=True)  # cost-per-acquisition (CPA) target
    competitor_exclusion_list: Mapped[str] = mapped_column(Text, nullable=True)  # comma-separated advertiser IDs


class AdCampaign(Base):
    """An advertising campaign run by an advertiser."""
    __tablename__ = "ad_campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(150), nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # lifetime / publicly stated total budget
    window_budget_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)  # budget deployed in this 60-day window (calibrated to actual delivery -> makes pacing / burn queries meaningful)
    daily_budget_cap_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    target_impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    max_bid_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # max CPM bid
    target_segment_age: Mapped[str] = mapped_column(String(50), nullable=True)  # e.g., "25-34,35-44"
    target_segment_geo: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g., "US-CA,US-NY"
    target_podcast_category: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g., "Tech,Business"


class AdCreative(Base):
    """Ad creative asset (audio file, script)."""
    __tablename__ = "ad_creative"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_campaign.id"), nullable=False)
    creative_name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)  # 15, 30, or 60 seconds
    audio_file_url: Mapped[str] = mapped_column(String(300), nullable=False)
    script_text: Mapped[str] = mapped_column(Text, nullable=True)
    has_call_to_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(Date, nullable=True)


class Listener(Base):
    """A podcast listener (anonymized)."""
    __tablename__ = "listener"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listener_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    age_group: Mapped[str] = mapped_column(String(20), nullable=False)  # 18-24, 25-34, 35-44, etc.
    gender: Mapped[str] = mapped_column(String(10), nullable=True)
    location_state: Mapped[str] = mapped_column(String(2), nullable=False)  # US state code
    location_metro: Mapped[str] = mapped_column(String(50), nullable=True)  # metro area
    first_listen_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_listening_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_ad_skip_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # share of ads skipped (%)
    is_premium_subscriber: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ListenerSegment(Base):
    """Interest / behavior segment used for targeted delivery."""
    __tablename__ = "listener_segment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listener_id: Mapped[int] = mapped_column(Integer, ForeignKey("listener.id"), nullable=False)
    segment_name: Mapped[str] = mapped_column(String(50), nullable=False)  # Tech_Enthusiast, Fitness_Oriented, etc.
    segment_score: Mapped[float] = mapped_column(Float, nullable=False)  # confidence score 0-1
    assigned_date: Mapped[datetime] = mapped_column(Date, nullable=False)


class PlaySession(Base):
    """A single listening session."""
    __tablename__ = "play_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listener_id: Mapped[int] = mapped_column(Integer, ForeignKey("listener.id"), nullable=False)
    episode_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast_episode.id"), nullable=False)
    session_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    session_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    total_play_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)  # actual listening duration
    completion_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)  # mobile, desktop, smart_speaker
    playback_speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # 1x, 1.5x, 2x


class AdImpression(Base):
    """Ad delivery record (one row per ad played)."""
    __tablename__ = "ad_impression"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    play_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("play_session.id"), nullable=False)
    ad_slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("episode_ad_slot.id"), nullable=False)
    creative_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_creative.id"), nullable=False)
    impression_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    winning_bid_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # auction winning price
    actual_charge_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # second-price auction outcome
    ad_duration_played_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    was_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    skip_after_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    was_completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    was_clicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # listener clicked the ad link
    converted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # conversion after click


class AdAuctionLog(Base):
    """Real-time bidding (RTB) auction log (every bid for every impression)."""
    __tablename__ = "ad_auction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    impression_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_impression.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_campaign.id"), nullable=False)
    bid_cpm: Mapped[float] = mapped_column(Float, nullable=False)
    bid_rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=winner, 2=runner-up, etc.
    won_auction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bid_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    audience_match_score: Mapped[float] = mapped_column(Float, nullable=True)  # how well the listener matches targeting


class RevenueSettlement(Base):
    """Daily revenue settlement and revenue share."""
    __tablename__ = "revenue_settlement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    settlement_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    podcast_id: Mapped[int] = mapped_column(Integer, ForeignKey("podcast.id"), nullable=False)
    total_impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    total_revenue_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # StreamCast's 30% take
    podcast_payout_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # creator's 70% share
    rpm: Mapped[float] = mapped_column(Float, nullable=False)  # revenue per 1000 plays
    avg_cpm: Mapped[float] = mapped_column(Float, nullable=False)  # daily average CPM
    fill_rate: Mapped[float] = mapped_column(Float, nullable=False)  # share of ad slots filled (%)


# ============================================================================
# Data generation functions
# ============================================================================

def generate_podcasts(n: int = 50) -> list[dict]:
    """Generate podcast shows."""
    categories = [
        "Technology", "Business", "Health & Wellness", "True Crime", "Comedy",
        "News & Politics", "Education", "Sports", "Science", "Arts", "Finance"
    ]
    age_groups = ["18-24", "25-34", "35-44", "45-54", "55+"]

    # Curated well-known shows so that SQL examples filtering by exact podcast_name
    # (e.g., Query 14/15 -> 'Tech Explained') actually return rows. They are never
    # premium and are long enough (>20 min) to accommodate a mid-roll ad slot.
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
            is_premium = random.random() < 0.15  # 15% are premium podcasts
        # Anchor to REFERENCE_DATE (not the real system clock) for full reproducibility.
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
    """Generate podcast episodes."""
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
    """Generate the standard ad slot types."""
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
    """Generate ad slots for each episode."""
    slots = []
    slot_id = 1

    for episode in episodes:
        duration = episode["duration_seconds"]

        # Pre-roll (always at the start)
        slots.append({
            "id": slot_id,
            "episode_id": episode["id"],
            "slot_template_id": 1,  # pre_roll
            "position_seconds": 0,
            "max_duration_sec": 30
        })
        slot_id += 1

        # Mid-roll (placed near the midpoint for episodes > 20 minutes)
        if duration > 1200:
            slots.append({
                "id": slot_id,
                "episode_id": episode["id"],
                "slot_template_id": 2,  # mid_roll
                "position_seconds": duration // 2,
                "max_duration_sec": 60
            })
            slot_id += 1

        # Post-roll (at the end)
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
    """Generate advertisers."""
    industries = [
        "E-commerce", "FinTech", "SaaS", "CPG", "Automotive",
        "Healthcare", "Education", "Entertainment", "Travel", "Real Estate"
    ]

    # Curated real brands so that SQL examples filtering by exact company / campaign
    # name (Query 7/8/11/12/24) return rows instead of empty results. The CPG cluster
    # also carries a competitor_exclusion_list (Coca-Cola <-> Pepsi <-> Dr Pepper).
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
    """Generate ad campaigns."""
    campaigns = []
    campaign_id = 1
    start_date = WINDOW_START

    age_targets = ["18-24", "25-34", "35-44", "45-54", "25-34,35-44"]
    geo_targets = ["US-CA", "US-NY", "US-TX", "US-CA,US-NY", None]
    geo_targets_nonnull = [g for g in geo_targets if g]
    category_targets = ["Technology", "Business", "Health & Wellness", "Technology,Business", None]
    category_targets_nonnull = [c for c in category_targets if c]

    # Exact campaign names that specific SQL examples (Query 7 / Query 8) filter on.
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
        # Curated brands always run 3 campaigns, covering most of the window with
        # competitive max bids, so the example queries have enough data to chew on.
        num_campaigns = 3 if is_curated else random.randint(1, 3)

        for idx in range(num_campaigns):
            if is_curated:
                campaign_start = start_date + timedelta(days=random.randint(0, 10))
                campaign_end = campaign_start + timedelta(days=random.randint(45, 60))
                max_bid = round(random.uniform(20, 40), 2)
                # Non-null targeting so the targeting-effectiveness query (Query 9) has signal.
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
                "window_budget_usd": None,  # backfilled after impressions are generated (calibrated to real delivery)
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
    """Generate ad creative assets."""
    creatives = []
    creative_id = 1

    for campaign in campaigns:
        num_creatives = random.randint(2, 3)  # 2-3 creatives per campaign for A/B testing (per the ER document)
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
    """Generate listeners."""
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
    """Generate behavior segments for listeners."""
    segments_pool = [
        "Tech_Enthusiast", "Fitness_Oriented", "Finance_Savvy", "Early_Adopter",
        "Frequent_Traveler", "Foodie", "DIY_Home", "Car_Enthusiast", "Pet_Owner",
        "Parent", "Gamer", "Fashion_Forward", "Health_Conscious"
    ]

    listener_segments = []
    segment_id = 1

    for listener in listeners:
        # Assign 1-3 segments to each listener
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
    """Generate listening sessions."""
    device_types = ["mobile", "desktop", "smart_speaker"]
    playback_speeds = [1.0, 1.0, 1.0, 1.0, 1.5, 1.5, 2.0]  # weights skewed toward 1x

    sessions = []
    window_start = WINDOW_START
    reference = REFERENCE_DATE

    i = 1
    attempts = 0
    max_attempts = n * 4  # safety cap; retry skipped rows so we still reach ~n sessions
    while len(sessions) < n and attempts < max_attempts:
        attempts += 1
        listener = random.choice(listeners)
        episode = random.choice(episodes)

        # For very popular episodes, partially throttle non-premium listeners
        if episode["total_plays_to_date"] > 100000 and not listener["is_premium_subscriber"]:
            if random.random() < 0.5:  # 50% chance to skip (then re-randomize and retry)
                continue

        # A session's start time cannot precede the episode's publish time, the data
        # window, or the listener's first-listen date.
        publish = episode["publish_date"]
        first_listen_dt = datetime.combine(listener["first_listen_date"], datetime.min.time())
        earliest = max(publish, window_start, first_listen_dt)
        if earliest >= reference:
            continue
        span_seconds = int((reference - earliest).total_seconds())
        session_start = earliest + timedelta(seconds=random.randint(0, span_seconds))

        # Simulate realistic listening behavior
        completion_pct = random.uniform(0.15, 1.0)
        if random.random() < 0.25:  # 25% are highly engaged listeners
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
    """Generate ad impressions and auction logs with a realistic bidding process.

    Business invariants enforced here:
    - Premium subscribers and premium (ad-free) podcasts produce no impressions.
    - Every bid honors the slot floor (bid >= slot base_cpm) and the campaign cap
      (bid <= max_bid_cpm); campaigns that can't meet the floor are ineligible.
    - The realized CPM follows the mid_roll > pre_roll > post_roll pricing
      gradient, because bids are anchored to the slot's base CPM, not just to
      the campaign's max bid.
    - Targeting (age / geo / category / interest-segment) lifts willingness to pay,
      so high-value audiences (e.g., Tech_Enthusiast) and matching campaigns
      clear at higher CPM.
    """
    impressions = []
    auction_logs = []
    impression_id = 1
    auction_log_id = 1

    # Build lookup dicts
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

    # listener_id -> set of interest-segment names
    listener_seg_map = {}
    for seg in listener_segments:
        listener_seg_map.setdefault(seg["listener_id"], set()).add(seg["segment_name"])

    # Slot template -> (base CPM floor, additional demand multiplier). Mid-roll is the
    # most valuable inventory, so it has both the highest floor and a demand premium.
    slot_base_cpm = {1: 15.0, 2: 25.0, 3: 8.0}
    slot_demand_mult = {1: 1.0, 2: 1.15, 3: 0.9}
    # Bidders per auction by slot: mid-roll is the most contested (highest demand),
    # pre-roll has the broadest pool of bidders, post-roll the thinnest -> keeps
    # "mid-roll is most contested" aligned with the ER narrative (lower bound stays
    # >=2 so we don't get degenerate single-bidder auctions).
    slot_bidder_range = {1: (2, 6), 2: (4, 8), 3: (2, 4)}

    # Advertiser vertical -> interest segments that mark high-intent audiences.
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

    # High-value audiences attract denser demand, so every bid in their auctions
    # clears at a higher price -> gives Query 3 (segment CPM ranking) a real,
    # monotonic signal.
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

        # No ads served to premium subscribers, and no ads at all on premium podcasts.
        if listener["is_premium_subscriber"]:
            continue
        if podcast["is_premium"]:
            continue

        slots = episode_slots_map.get(session["episode_id"], [])
        session_date = session["session_start_time"].date()
        listener_segs = listener_seg_map.get(listener["id"], set())
        # Demand premium driven by the listener's most-valuable segment, applied across the whole auction.
        listener_value_mult = max(
            (high_value_segments.get(s, 1.0) for s in listener_segs), default=1.0
        )

        for slot in slots:
            # Check whether the listener reached this ad position
            if session["total_play_duration_sec"] < slot["position_seconds"]:
                continue  # listener stopped listening before this ad

            base_cpm = slot_base_cpm.get(slot["slot_template_id"], 10.0)
            demand_mult = slot_demand_mult.get(slot["slot_template_id"], 1.0)

            # Eligible = active on this day AND able to meet the slot floor.
            eligible_campaigns = [
                c for c in campaigns
                if c["start_date"] <= session_date <= c["end_date"]
                and c["max_bid_cpm"] >= base_cpm
            ]
            if not eligible_campaigns:
                continue  # unfilled (unsold inventory)

            # Simulate auction: bidder count depends on slot demand (mid-roll most contested)
            lo, hi = slot_bidder_range.get(slot["slot_template_id"], (2, 6))
            num_bidders = min(len(eligible_campaigns), random.randint(lo, hi))
            bidders = random.sample(eligible_campaigns, num_bidders)

            bids = []
            for campaign in bidders:
                vertical = advertiser_map[campaign["advertiser_id"]]["industry_vertical"]

                # Targeting match: age / geo / category / interest-segment affinity.
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
                # Interest-segment affinity always counts as one dimension.
                match_dims += 1
                pref = vertical_pref_segments.get(vertical, set())
                if pref and (listener_segs & pref):
                    match_hits += 1

                match_score = match_hits / match_dims if match_dims else 0.0

                # Targeting can lift willingness-to-pay up to +60%; bids are anchored
                # to the slot floor; the listener's segment value lifts the entire
                # auction's clearing price.
                targeting_premium = 0.6 * match_score
                desired = (
                    base_cpm * demand_mult * (1.0 + targeting_premium)
                    * listener_value_mult * random.uniform(0.92, 1.12)
                )
                bid_cpm = min(campaign["max_bid_cpm"], desired)
                bid_cpm = max(bid_cpm, base_cpm)  # enforce floor

                bids.append({
                    "campaign": campaign,
                    "bid_cpm": round(bid_cpm, 2),
                    "match_score": round(match_score, 2)
                })

            # Sort bids by CPM (high to low)
            bids.sort(key=lambda x: x["bid_cpm"], reverse=True)

            # Winner pays second-highest bid + $0.01 (second-price auction); never below
            # the slot floor and never above the winner's own bid (so even if the top
            # two bids round to the same value, winning_bid - actual >= 0 still holds).
            winner = bids[0]
            second_price = bids[1]["bid_cpm"] if len(bids) > 1 else winner["bid_cpm"] * 0.9
            actual_charge = round(max(base_cpm, second_price + 0.01), 2)
            actual_charge = min(actual_charge, winner["bid_cpm"])

            # Pick a creative from the winning campaign
            available_creatives = campaign_creatives_map.get(winner["campaign"]["id"], [])
            if not available_creatives:
                continue

            winning_creative = random.choice(available_creatives)

            # Decide whether the ad was skipped / fully listened to.
            # Base skip rate is the listener's tolerance, but higher-match (more
            # relevant) ads are skipped less often -> matched impressions complete more often.
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

            # Click / conversion signals (only meaningful when the ad was completed).
            # Podcast CTR is low (~0.5-1.5%) and rises with targeting fit + CTA.
            was_clicked = False
            converted = False
            if was_completed:
                ctr = 0.005 + 0.012 * winner["match_score"]
                if winning_creative["has_call_to_action"]:
                    ctr += 0.004
                was_clicked = random.random() < ctr
                if was_clicked:
                    converted = random.random() < 0.15  # ~15% of clicks convert

            # Create impression
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

            # Create auction log entries for every bidder
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
    """Aggregate the actual ad_impression rows into podcast x day settlement records.

    This is a faithful rollup of the impression table (not random numbers):
    - total_impressions / total_revenue come directly from that day's impressions.
    - platform_fee = 30%, podcast_payout = 70% (platform / creator share).
    - rpm = (creator share / day's plays) * 1000  -> creator-share RPM.
    - avg_cpm = total_revenue / total_impressions * 1000      -> weighted eCPM.
    - fill_rate = filled slots / reachable slots for that podcast x day.
    Premium podcasts don't serve ads, so they never appear here.
    """
    episode_map = {e["id"]: e for e in episodes}
    podcast_map = {p["id"]: p for p in podcasts}
    session_map = {s["id"]: s for s in sessions}
    listener_map = {l["id"]: l for l in listeners}

    episode_slots_map = {}
    for slot in ad_slots:
        episode_slots_map.setdefault(slot["episode_id"], []).append(slot)

    filled = defaultdict(int)        # (podcast_id, date) -> filled slot count
    revenue = defaultdict(float)     # (podcast_id, date) -> revenue (USD)
    plays = defaultdict(int)         # (podcast_id, date) -> play session count
    available = defaultdict(int)     # (podcast_id, date) -> reachable slot count

    # Play counts (all sessions) and reachable ad inventory (only sessions that can serve ads).
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

    # Filled slots + revenue come from actual impressions. Key on the session's start
    # date (same key as plays/available) so a mid/post-roll that crosses midnight doesn't
    # land on a different day than its session -> avoids settlement rows with available=0/fill_rate=0.
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
    """Backfill each campaign's `window_budget_usd` based on its actual delivery in the window.

    `total_budget_usd` is a lifetime / advertiser-level publicly-stated number, so on a
    60-day sample it goes almost entirely unspent (spend is just a few to a few dozen
    dollars), causing budget-pacing queries to degenerate (Q5 returns nothing, Q23
    flags everything as "too slow").

    `window_budget_usd`, in contrast, = spend / utilization, where utilization is drawn
    from a realistic mixed distribution (some campaigns nearly exhausted, most healthy,
    some slow). This makes Q5 (burn-down alerts), Q23 (pacing variance), and Q7
    (budget utilization) produce meaningful, varied results while preserving the
    grand headline budget for narrative purposes.
    Mutates campaign dicts in place.
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
            utilization = random.uniform(0.90, 0.99)   # near exhaustion -> triggers Q5 alerts
        elif r < 0.75:
            utilization = random.uniform(0.45, 0.85)   # healthy pacing
        else:
            utilization = random.uniform(0.15, 0.45)   # slow burn -> Q23 "too slow"

        if spent > 0:
            window_budget = spent / utilization
        else:
            # No delivery in this window: a small nominal deploy budget reads as "slow".
            window_budget = random.uniform(20, 120)
        # Deploy budget can never go below actual spend.
        c["window_budget_usd"] = round(max(window_budget, spent), 2)
        # Keep the (recorded but unused) daily cap consistent with window budget:
        # a uniformly-paced daily cap that never exceeds the whole window's deploy budget.
        days = (c["end_date"] - c["start_date"]).days + 1
        c["daily_budget_cap_usd"] = round(c["window_budget_usd"] / days, 2) if days > 0 else c["window_budget_usd"]


# ============================================================================
# Main generation logic
# ============================================================================

def write_tsv(data: list[dict], filepath: Path):
    """Write data to a TSV file using Polars."""
    if not data:
        print(f"Warning: No data to write for {filepath}")
        return
    df = pl.DataFrame(data)
    df.write_csv(filepath, separator="\t")
    print(f"✓ Generated {filepath.name}: {len(data)} rows")


def main():
    """Main data generation orchestration."""
    print("=" * 80)
    print("Media - Podcast Advertising Economics Data Generator")
    print("=" * 80)

    # Clean up old data
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
    # Note: window_budget_usd is backfilled only after impressions are generated, so the
    # campaign TSV is written later (after step 11), once each campaign's real delivery is known.

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
    # Calibrate each campaign's deploy window budget to its actual delivery, then write
    # the (previously deferred) campaign table, so the budget-pacing queries Q5/Q23/Q7 are meaningful.
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
    # Create SQLite database
    # ========================================================================
    print("\n[14/14] Creating SQLite database...")
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # Load TSV files into the database
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
