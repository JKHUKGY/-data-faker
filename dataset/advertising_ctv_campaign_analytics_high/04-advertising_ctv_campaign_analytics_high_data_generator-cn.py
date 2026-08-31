"""
广告技术 - CTV 广告投放分析 假数据生成器 (Vantage Media: Booking Copilot)
复杂度: High
生成工具: Fake Data Generator Agent

业务背景:
本数据集模拟虚构 AdTech SaaS 公司 Vantage Media 的核心业务。Vantage Media 为
DTC 品牌提供 CTV (Connected TV) 媒体采购 SaaS 平台，核心产品 "Booking Copilot"
基于 AutoML 在媒体买手向客户确认报价前，对每个候选广告位预测两个数：

  1. Clearance Probability (二分类) — 这条广告位实际播出的概率
  2. ROAS (回归) — 该广告位预期的广告投资回报率

平台为每个广告主 (advertiser) 训练定制化 ML 模型 (LightGBM / TabPFN / H2O
风格 AutoML pipeline)，通过 shadow scoring 同时挂载多版本进行回溯评估。

数据集覆盖 6 个月 (2025-05-01 → 2025-10-31)、~50,000 个 placement、~120 个
广告主、~400 个 campaign、15 个网络 (有线 + 广播 + 流媒体)。规模足以支撑：
  - AutoML 模型训练 (足够样本 × 特征组合)
  - 模型版本对比 (shadow scoring)
  - 时间序列特征工程 (network_clearance_history 预先在 ad_placement 时间窗外)
  - 业务 BI 与运营监控 (媒体采购、数据质量、归因对比)
"""

from __future__ import annotations
import os
import shutil
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Callable, Any
import random
import json

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, Text, Date, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "advertising_ctv_campaign_analytics_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# 业务配置
START_DATE = datetime(2025, 5, 1)  # 数据开始日期
END_DATE = datetime(2025, 10, 31)  # 数据结束日期（6个月）
TOTAL_DAYS = (END_DATE - START_DATE).days


def lead_clearance_adjustment(lead_days: int) -> float:
    """预订提前期 → 清除率分级加成 (Review-01 Q9 修复)。

    旧版本只对 lead<=7 加 +0.05、其余档持平且无 >60 天 lead，导致 Q9
    "清除率随提前期单调下降" 与 ">60天 75-80%" 预期无法兑现。
    现改为单调递减的分级调整，并在 lead 取值集合里引入 75/90 天，
    使 Q9 的 5 个分桶都非空且清除率单调下降。

    gen_ad_placements 与 gen_prediction_results 共用此函数，保证
    "实际清除" 与 "模型预测" 用同一套 lead 逻辑（Q2/Q14 准确率一致）。

    分桶调整经过居中：按 BOOKING_LEAD_WEIGHTS 的加权平均 ≈ +0.021，
    与旧版 (仅 ≤7 +0.05、加权 +0.021) 持平，保证整体清除率维持 ~85%，
    不破坏 Q2/Q14/Q18 依赖的"cleared ~85% / baseline ~85%"叙事；同时
    提供 13.5pp 的单调梯度，使 Q9 的 5 个分桶清除率单调下降。
    """
    if lead_days <= 7:
        return 0.075
    elif lead_days <= 14:
        return 0.035
    elif lead_days <= 30:
        return 0.005
    elif lead_days <= 60:
        return -0.03
    else:
        return -0.06


# 预订提前期取值与权重 (Review-01 Q9 修复: 引入 75/90 天填充 >60 天分桶)
# 加权平均调整 ≈ -0.003，对整体清除率近乎中性，不破坏 ~85% 清除率基线
BOOKING_LEAD_CHOICES = [3, 7, 14, 21, 30, 45, 60, 75, 90]
BOOKING_LEAD_WEIGHTS = [0.16, 0.18, 0.16, 0.13, 0.11, 0.09, 0.07, 0.06, 0.04]

# 归因方法 → ROAS 系数 (Review-01 Q8 修复)
# pixel_match 精确、轻微高估; ip_match 中性; panel_extrapolation 统计外推、系统性低估。
# 4 个 partner 中 pixel 占 2 个(50%)、panel/ip 各 1 个(25%)，加权平均系数 = 1.00，
# 因此各 network_type 的平均 ROAS 不被整体抬高/压低，仅在 partner 维度产生梯度。
ATTRIBUTION_METHOD_ROAS_MULTIPLIER = {
    "pixel_match": 1.10,
    "ip_match": 1.00,
    "panel_extrapolation": 0.80,
}


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


class AdvertiserCategory(Base):
    """广告主类别枚举表"""
    __tablename__ = "advertiser_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Daypart(Base):
    """时段枚举表"""
    __tablename__ = "daypart"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daypart_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    daypart_name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)


class AdFormat(Base):
    """广告格式枚举表"""
    __tablename__ = "ad_format"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    format_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    format_name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)


class AttributionPartner(Base):
    """归因合作伙伴表"""
    __tablename__ = "attribution_partner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partner_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    partner_name: Mapped[str] = mapped_column(String(100), nullable=False)
    attribution_method: Mapped[str] = mapped_column(String(50), nullable=False)
    typical_delay_hours: Mapped[int] = mapped_column(Integer, nullable=False)


class SeasonalEvent(Base):
    """季节性事件日历表"""
    __tablename__ = "seasonal_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    impact_level: Mapped[str] = mapped_column(String(20), nullable=False)


class ModelVersion(Base):
    """ML 模型版本表"""
    __tablename__ = "model_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    auc_roc: Mapped[float | None] = mapped_column(Float)
    mape: Mapped[float | None] = mapped_column(Float)


class Network(Base):
    """电视/流媒体网络表"""
    __tablename__ = "network"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    network_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    network_name: Mapped[str] = mapped_column(String(100), nullable=False)
    network_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_demo: Mapped[str] = mapped_column(String(50), nullable=False)
    live_programming_pct: Mapped[float] = mapped_column(Float, nullable=False)
    avg_clearance_rate_q1: Mapped[float] = mapped_column(Float, nullable=False)
    avg_clearance_rate_q2: Mapped[float] = mapped_column(Float, nullable=False)
    avg_clearance_rate_q3: Mapped[float] = mapped_column(Float, nullable=False)
    avg_clearance_rate_q4: Mapped[float] = mapped_column(Float, nullable=False)
    clearance_rate_stddev: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cpm_primetime: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Advertiser(Base):
    """广告主表"""
    __tablename__ = "advertiser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advertiser_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    advertiser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser_category.id"), nullable=False)
    total_budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    onboarded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DataQualityRule(Base):
    """数据质量规则表"""
    __tablename__ = "data_quality_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    target_column: Mapped[str | None] = mapped_column(String(100))
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    check_condition: Mapped[str] = mapped_column(Text, nullable=False)
    failure_threshold_pct: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    """广告活动表"""
    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NetworkClearanceHistory(Base):
    """网络历史清除率表"""
    __tablename__ = "network_clearance_history"
    __table_args__ = (
        UniqueConstraint("network_id", "month", name="uq_network_clearance_history_network_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    network_id: Mapped[int] = mapped_column(Integer, ForeignKey("network.id"), nullable=False)
    month: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_booked: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cleared: Mapped[int] = mapped_column(Integer, nullable=False)
    clearance_rate: Mapped[float] = mapped_column(Float, nullable=False)


class DataSourceSLA(Base):
    """数据源 SLA 跟踪表"""
    __tablename__ = "data_source_sla"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expected_delivery_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    sla_threshold_hours: Mapped[int] = mapped_column(Integer, nullable=False)


class IngestionMetadata(Base):
    """数据采集元数据表"""
    __tablename__ = "ingestion_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ingestion_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size_kb: Mapped[int] = mapped_column(Integer, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=True)


class AdPlacement(Base):
    """广告位预订表（核心事实表）"""
    __tablename__ = "ad_placement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    placement_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaign.id"), nullable=False)
    advertiser_id: Mapped[int] = mapped_column(Integer, ForeignKey("advertiser.id"), nullable=False)
    network_id: Mapped[int] = mapped_column(Integer, ForeignKey("network.id"), nullable=False)
    daypart_id: Mapped[int] = mapped_column(Integer, ForeignKey("daypart.id"), nullable=False)
    ad_format_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_format.id"), nullable=False)
    scheduled_air_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    scheduled_air_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    booked_cpm: Mapped[float] = mapped_column(Float, nullable=False)
    booked_impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_lead_days: Mapped[int] = mapped_column(Integer, nullable=False)
    break_position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    actual_air_time: Mapped[datetime | None] = mapped_column(DateTime)
    data_source: Mapped[str | None] = mapped_column(String(50))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DataQualityLog(Base):
    """数据质量日志表"""
    __tablename__ = "data_quality_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_quality_rule.id"), nullable=False)
    run_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rows_checked: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_rate: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_fired: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_failures: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String(50))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class PerformanceActual(Base):
    """实际效果数据表"""
    __tablename__ = "performance_actual"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actual_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    placement_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_placement.id"), nullable=False)
    impressions_delivered: Mapped[int] = mapped_column(Integer, nullable=False)
    spend_usd: Mapped[float] = mapped_column(Float, nullable=False)
    attributed_conversions: Mapped[int] = mapped_column(Integer, nullable=False)
    attributed_revenue_usd: Mapped[float] = mapped_column(Float, nullable=False)
    roas: Mapped[float] = mapped_column(Float, nullable=False)
    attribution_partner_id: Mapped[int] = mapped_column(Integer, ForeignKey("attribution_partner.id"), nullable=False)
    attribution_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PredictionResult(Base):
    """ML 预测结果表"""
    __tablename__ = "prediction_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    placement_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_placement.id"), nullable=False)
    predicted_clearance_prob: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_roas: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(20), nullable=False)
    top_features: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 字符串
    model_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("model_version.id"), nullable=False)
    # Review-01 修复: 双任务来源。clearance 预测挂 classifier(id 1/2/3)，
    # ROAS 预测挂配对的 regressor(id 4/5/6)，消除 roas_regressor 孤儿行。
    roas_model_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("model_version.id"), nullable=False)
    prediction_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(50), nullable=False)


class BookingHistory(Base):
    """预订历史变更表"""
    __tablename__ = "booking_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    placement_id: Mapped[int] = mapped_column(Integer, ForeignKey("ad_placement.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(50), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)


class UserAction(Base):
    """用户操作审计表"""
    __tablename__ = "user_action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String(50), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    placement_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ad_placement.id"))
    action_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)


class AlertNotification(Base):
    """告警通知表"""
    __tablename__ = "alert_notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quality_log_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_quality_log.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient: Mapped[str] = mapped_column(String(100), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False)


# ============================================================================
# 数据生成器
# ============================================================================

def gen_advertiser_categories() -> pl.DataFrame:
    """生成广告主类别枚举数据"""
    categories = [
        ("HEALTH", "Health & Wellness", "补充剂、保健品、健身器材"),
        ("FINANCE", "Financial Services", "银行、保险、投资理财"),
        ("APPAREL", "Apparel & Fashion", "服装、鞋履、配饰"),
        ("FOOD_BEV", "Food & Beverage", "食品、饮料、酒类"),
        ("TECH", "Technology & Electronics", "消费电子、软件、App"),
        ("HOME", "Home & Garden", "家居、家具、园艺"),
        ("AUTO", "Automotive", "汽车、汽车配件、保险"),
        ("TRAVEL", "Travel & Hospitality", "旅游、酒店、航空"),
    ]
    records = []
    for i, (code, name, desc) in enumerate(categories, 1):
        records.append({
            "id": i,
            "category_code": code,
            "category_name": name,
            "description": desc,
        })
    return pl.DataFrame(records)


def gen_dayparts() -> pl.DataFrame:
    """生成时段枚举数据"""
    dayparts = [
        ("EARLY_MORNING", "Early Morning", 5, 9),
        ("DAYTIME", "Daytime", 9, 16),
        ("EARLY_FRINGE", "Early Fringe", 16, 20),
        ("PRIMETIME", "Primetime", 20, 23),
        ("LATE_NIGHT", "Late Night", 23, 2),
        ("WEEKEND", "Weekend Daytime", 9, 20),
    ]
    records = []
    for i, (code, name, start, end) in enumerate(dayparts, 1):
        records.append({
            "id": i,
            "daypart_code": code,
            "daypart_name": name,
            "start_hour": start,
            "end_hour": end,
        })
    return pl.DataFrame(records)


def gen_ad_formats() -> pl.DataFrame:
    """生成广告格式枚举数据"""
    formats = [
        ("SPOT_15", "15-Second Spot", 15),
        ("SPOT_30", "30-Second Spot", 30),
        ("SPOT_60", "60-Second Spot", 60),
        ("SPOT_120", "2-Minute Infomercial", 120),
    ]
    records = []
    for i, (code, name, duration) in enumerate(formats, 1):
        records.append({
            "id": i,
            "format_code": code,
            "format_name": name,
            "duration_sec": duration,
        })
    return pl.DataFrame(records)


def gen_attribution_partners() -> pl.DataFrame:
    """生成归因合作伙伴数据"""
    partners = [
        ("ATTR_PRO", "AttributionPro", "pixel_match", 12),
        ("NIELSEN_DIG", "Nielsen Digital", "panel_extrapolation", 48),
        ("IMPACT_TRACK", "ImpactTracker", "ip_match", 24),
        ("CONV_PIXEL", "ConversionPixel", "pixel_match", 6),
    ]
    records = []
    for i, (code, name, method, delay) in enumerate(partners, 1):
        records.append({
            "id": i,
            "partner_code": code,
            "partner_name": name,
            "attribution_method": method,
            "typical_delay_hours": delay,
        })
    return pl.DataFrame(records)


def gen_seasonal_events() -> pl.DataFrame:
    """生成季节性事件数据"""
    events = [
        ("NFL Preseason", "sports", datetime(2025, 8, 1), datetime(2025, 8, 31), "medium"),
        ("NFL Regular Season", "sports", datetime(2025, 9, 5), datetime(2025, 10, 31), "high"),
        ("Back to School", "retail", datetime(2025, 8, 15), datetime(2025, 9, 10), "medium"),
        ("Labor Day Weekend", "holiday", datetime(2025, 8, 30), datetime(2025, 9, 2), "medium"),
        ("Prime Day (simulated)", "retail", datetime(2025, 7, 15), datetime(2025, 7, 17), "high"),
    ]
    records = []
    for i, (name, event_type, start, end, impact) in enumerate(events, 1):
        records.append({
            "id": i,
            "event_name": name,
            "event_type": event_type,
            "start_date": start.date(),
            "end_date": end.date(),
            "impact_level": impact,
        })
    return pl.DataFrame(records)


def gen_model_versions() -> pl.DataFrame:
    """生成 ML 模型版本数据"""
    versions = [
        ("v2.1.5", "clearance_classifier", datetime(2025, 4, 1), 0.768, 28.1),
        ("v2.2.0", "clearance_classifier", datetime(2025, 5, 15), 0.791, 24.5),
        ("v2.3.1", "clearance_classifier", datetime(2025, 7, 1), 0.824, 18.2),
        ("v2.1.5-roas", "roas_regressor", datetime(2025, 4, 1), None, 31.5),
        ("v2.2.0-roas", "roas_regressor", datetime(2025, 5, 15), None, 26.8),
        ("v2.3.1-roas", "roas_regressor", datetime(2025, 7, 1), None, 19.4),
    ]
    records = []
    for i, (code, model_type, deployed, auc, mape) in enumerate(versions, 1):
        records.append({
            "id": i,
            "version_code": code,
            "model_type": model_type,
            "deployed_at": deployed,
            "auc_roc": auc,
            "mape": mape,
        })
    return pl.DataFrame(records)


def gen_networks() -> pl.DataFrame:
    """生成网络数据（基于 Vantage Media 文档）"""
    networks = [
        # 列顺序: network_code, name, type, tier, demo, live%, q1, q2, q3, q4, stddev, cpm
        ("ESPN", "ESPN", "linear_cable", "premium", "Adults 18-49", 0.62, 0.81, 0.85, 0.79, 0.58, 0.11, 34.50),
        ("ESPN2", "ESPN2", "linear_cable", "standard", "Adults 18-49", 0.55, 0.78, 0.82, 0.76, 0.54, 0.13, 28.20),
        ("HGTV", "HGTV", "linear_cable", "standard", "Women 25-54", 0.04, 0.91, 0.93, 0.92, 0.90, 0.03, 18.20),
        ("NBC", "NBC", "linear_broadcast", "premium", "Adults 25-54", 0.38, 0.88, 0.90, 0.87, 0.72, 0.08, 42.00),
        ("CBS", "CBS", "linear_broadcast", "premium", "Adults 25-54", 0.35, 0.87, 0.89, 0.86, 0.70, 0.09, 40.50),
        ("ABC", "ABC", "linear_broadcast", "premium", "Adults 18-49", 0.32, 0.89, 0.91, 0.88, 0.74, 0.07, 41.20),
        ("FOX", "FOX", "linear_broadcast", "premium", "Adults 18-49", 0.45, 0.84, 0.87, 0.83, 0.62, 0.10, 38.75),
        ("HULU", "Hulu Live", "streaming_avod", "premium", "Adults 18-49", 0.15, 0.95, 0.96, 0.95, 0.94, 0.02, 28.75),
        ("PEACOCK", "Peacock", "streaming_avod", "standard", "Adults 25-54", 0.12, 0.94, 0.95, 0.94, 0.93, 0.02, 24.50),
        ("PLUTO", "Pluto TV", "streaming_avod", "standard", "Adults 18-49", 0.08, 0.96, 0.97, 0.96, 0.95, 0.01, 16.80),
        ("OWN", "OWN", "linear_cable", "niche", "Women 35-64", 0.01, 0.94, 0.95, 0.94, 0.93, 0.02, 12.40),
        ("FOOD_NET", "Food Network", "linear_cable", "standard", "Women 25-54", 0.03, 0.92, 0.93, 0.92, 0.91, 0.03, 17.50),
        ("TBS", "TBS", "linear_cable", "standard", "Adults 18-49", 0.28, 0.85, 0.87, 0.84, 0.68, 0.09, 26.30),
        ("TNT", "TNT", "linear_cable", "standard", "Adults 25-54", 0.30, 0.83, 0.86, 0.82, 0.66, 0.10, 27.80),
        ("CNN", "CNN", "linear_cable", "premium", "Adults 35-64", 0.52, 0.80, 0.83, 0.79, 0.61, 0.11, 32.40),
    ]
    records = []
    for i, data in enumerate(networks, 1):
        code, name, net_type, tier, demo, live_pct, q1, q2, q3, q4, std, cpm = data
        records.append({
            "id": i,
            "network_code": code,
            "network_name": name,
            "network_type": net_type,
            "tier": tier,
            "primary_demo": demo,
            "live_programming_pct": live_pct,
            "avg_clearance_rate_q1": q1,
            "avg_clearance_rate_q2": q2,
            "avg_clearance_rate_q3": q3,
            "avg_clearance_rate_q4": q4,
            "clearance_rate_stddev": std,
            "avg_cpm_primetime": cpm,
            "updated_at": datetime(2025, 5, 1),
        })
    return pl.DataFrame(records)


def gen_advertisers(n: int = 80) -> pl.DataFrame:
    """生成广告主数据"""
    records = []
    category_weights = [0.20, 0.15, 0.12, 0.10, 0.10, 0.12, 0.11, 0.10]  # 对应 8 个类别
    categories = random.choices(range(1, 9), weights=category_weights, k=n)

    for i in range(1, n + 1):
        budget = random.choice([
            random.uniform(200_000, 500_000),  # 小客户
            random.uniform(500_000, 1_500_000),  # 中客户
            random.uniform(1_500_000, 5_000_000),  # 大客户
        ])
        onboarded = fake.date_time_between(start_date="-2y", end_date=START_DATE)

        records.append({
            "id": i,
            "advertiser_code": f"ADV-{i:04d}",
            "advertiser_name": fake.company(),
            "category_id": categories[i-1],
            "total_budget_usd": round(budget, 2),
            "onboarded_at": onboarded,
        })
    return pl.DataFrame(records)


def gen_data_quality_rules() -> pl.DataFrame:
    """生成数据质量规则数据"""
    rules = [
        ("DQR-001", "Placement ID Not Null", "completeness", "ad_placement", "placement_code", "null_check", "P0", "placement_code IS NULL", 0.00),
        ("DQR-002", "Impressions In Range", "accuracy", "performance_actual", "impressions_delivered", "range_check", "P1", "impressions_delivered < 0 OR impressions_delivered > 50000000", 0.01),
        ("DQR-003", "Delivery Log Freshness", "timeliness", "ad_placement", "ingested_at", "freshness_check", "P1", "MAX(ingested_at) < DATETIME('now', '-28 hours')", 0.00),
        ("DQR-004", "ROAS Anomaly Detection", "accuracy", "performance_actual", "roas", "zscore_anomaly", "P1", "ABS(z_score) > 3.0", 0.05),
        ("DQR-005", "Impression Cross-Source", "consistency", "performance_actual", "impressions_delivered", "cross_source_check", "P1", "ABS(network_reported - vendor_verified) / network_reported > 0.15", 0.00),
        ("DQR-006", "Negative ROAS Check", "accuracy", "performance_actual", "roas", "range_check", "P0", "roas < 0", 0.00),
        ("DQR-007", "Future Air Date Check", "accuracy", "ad_placement", "scheduled_air_date", "logic_check", "P2", "scheduled_air_date > DATE('now', '+1 year')", 0.00),
        ("DQR-008", "CPM Range Check", "accuracy", "ad_placement", "booked_cpm", "range_check", "P1", "booked_cpm < 5 OR booked_cpm > 200", 0.02),
        ("DQR-009", "Campaign Budget Overrun", "consistency", "campaign", "budget_usd", "aggregate_check", "P2", "SUM(placement_spend) > campaign.budget_usd * 1.1", 0.00),
        ("DQR-010", "Attribution Delay SLA", "timeliness", "performance_actual", "finalized_at", "sla_check", "P1", "finalized_at - scheduled_air_date > typical_delay + 24h", 0.03),
    ]
    records = []
    for i, (code, name, dim, table, col, rule_type, sev, cond, thresh) in enumerate(rules, 1):
        records.append({
            "id": i,
            "rule_code": code,
            "rule_name": name,
            "dimension": dim,
            "target_table": table,
            "target_column": col,
            "rule_type": rule_type,
            "severity": sev,
            "check_condition": cond,
            "failure_threshold_pct": thresh,
            "is_active": True,
            "created_at": datetime(2025, 4, 15),
        })
    return pl.DataFrame(records)


def gen_campaigns(advertiser_ids: list[int], n: int = 150) -> pl.DataFrame:
    """生成广告活动数据"""
    records = []
    for i in range(1, n + 1):
        advertiser_id = random.choice(advertiser_ids)
        start = fake.date_between(start_date=START_DATE.date(), end_date=END_DATE.date())
        duration_days = random.choice([30, 60, 90, 120])
        end = start + timedelta(days=duration_days)
        budget = random.uniform(50_000, 500_000)
        status = random.choices(
            ["active", "completed", "paused"],
            weights=[0.4, 0.5, 0.1]
        )[0]

        records.append({
            "id": i,
            "campaign_code": f"CMP-{i:04d}",
            "campaign_name": f"{fake.catch_phrase()} Campaign",
            "advertiser_id": advertiser_id,
            "budget_usd": round(budget, 2),
            "start_date": start,
            "end_date": end,
            "status": status,
            "created_at": start - timedelta(days=random.randint(7, 30)),
        })
    return pl.DataFrame(records)


def gen_network_clearance_history(network_ids: list[int]) -> pl.DataFrame:
    """生成网络历史清除率数据

    Fix vs review: 使用真实月份运算（不再用 30 天近似），保证 UNIQUE(network_id, month)。
    历史窗口刻意早于 ad_placement（2024-11 → 2025-04 vs 2025-05 → 2025-10），
    作为 ML 特征 lookup，避免训练-评估时间泄漏。
    """
    records = []
    rec_id = 1

    # 生成 START_DATE 之前 6 个完整自然月：2024-11 → 2025-04
    base_year, base_month = START_DATE.year, START_DATE.month
    months: list[date] = []
    for offset in range(6, 0, -1):
        y = base_year
        m = base_month - offset
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))

    for network_id in network_ids:
        for month_date in months:
            total_booked = random.randint(100, 500)
            # 根据网络特性决定清除率
            if network_id in [1, 2]:  # ESPN 类体育网络
                base_clearance = 0.60
            elif network_id in [8, 9, 10]:  # 流媒体
                base_clearance = 0.95
            else:
                base_clearance = 0.88

            clearance_rate = max(0.5, min(0.99, base_clearance + random.uniform(-0.05, 0.05)))
            total_cleared = int(total_booked * clearance_rate)

            records.append({
                "id": rec_id,
                "network_id": network_id,
                "month": month_date,
                "total_booked": total_booked,
                "total_cleared": total_cleared,
                "clearance_rate": round(clearance_rate, 4),
            })
            rec_id += 1

    return pl.DataFrame(records)


def gen_data_source_sla() -> pl.DataFrame:
    """生成数据源 SLA 配置数据"""
    sources = [
        ("ESPN Delivery Log", "network_log", 6, 2),
        ("NBC Delivery Log", "network_log", 6, 2),
        ("Hulu Impression Feed", "streaming_log", 4, 1),
        ("AttributionPro API", "attribution", 12, 4),
        ("Nielsen Panel Data", "attribution", 48, 12),
    ]
    records = []
    for i, (name, src_type, expected_hour, sla_thresh) in enumerate(sources, 1):
        records.append({
            "id": i,
            "source_name": name,
            "source_type": src_type,
            "expected_delivery_hour": expected_hour,
            "sla_threshold_hours": sla_thresh,
        })
    return pl.DataFrame(records)


def gen_ingestion_metadata(n: int = 180) -> pl.DataFrame:
    """生成数据采集元数据（每天多个数据源）

    Fix vs review:
    - 偶发性大延迟（~10% 几率延迟 6-24 小时）使 SLA 违约可被观测
    """
    records = []
    sources = ["ESPN Delivery Log", "NBC Delivery Log", "Hulu Impression Feed", "AttributionPro API", "Nielsen Panel Data"]

    for day_offset in range(n):
        day = START_DATE + timedelta(days=day_offset)
        for source in random.sample(sources, k=random.randint(3, 5)):
            expected_hour = 6 if "Log" in source else 12

            # 10% 的概率发生显著延迟（6-24 小时，跨日处理）
            if random.random() < 0.10:
                delay_hours = random.randint(6, 24)
            else:
                delay_hours = random.randint(-1, 3)
            ingested_at = day.replace(hour=expected_hour, minute=random.randint(0, 59)) + timedelta(hours=delay_hours)

            records.append({
                "id": len(records) + 1,
                "source_name": source,
                "ingestion_date": day.date(),
                "file_name": f"{source.replace(' ', '_')}_{day.strftime('%Y%m%d')}.csv",
                "row_count": random.randint(50, 300),
                "file_size_kb": random.randint(500, 5000),
                "ingested_at": ingested_at,
                "is_complete": random.random() > 0.02,  # 2% 概率不完整
            })

    return pl.DataFrame(records)


def gen_ad_placements(
    campaign_meta: dict[int, tuple[int, date, date]],
    campaign_weight: dict[int, float],
    network_data: pl.DataFrame,
    daypart_ids: list[int],
    format_ids: list[int],
    n: int = 12000
) -> pl.DataFrame:
    """生成广告位预订数据（核心事实表）

    Fixes vs review:
    - advertiser_id 派生自 campaign，避免与 campaign.advertiser_id 不一致
    - 清除率/波动性从 network 表读取（不再硬编码，Pluto 和 11-15 都按 Q4 实际值）
    - NFL Season 惩罚扩到 Sep-Oct 且覆盖 FOX，范围 0.15-0.20
    - Q4 (10 月) 预订量比基线 +40%（通过偏向 Q4 的日期权重实现）
    - status 引入 ~2% pending（未到归因截止的尾部 placement）
    - volatility 通过 random.gauss 注入 per-placement 噪声

    Review-01 修复:
    - placement.scheduled_air_date 限制在所属 campaign 的 [start,end] ∩ 数据窗内
      抽样（旧版 air_date 全局抽样、campaign 独立随机 → 68% placement 越窗）。
      Q4(10 月)+40% 权重在每个 campaign 窗口内保留。
    - booking_lead_days 引入 75/90 天 + 分级清除率加成（见 lead_clearance_adjustment）。
    - preempted 也写入 data_source（网络日志确认被抢占）；仅 pending 的 data_source 为 NULL，
      让 preempted vs pending 的区分维度真实落地（见 ER §14 业务逻辑）。

    Review-02 修复 (campaign 预算 ↔ advertiser 年度预算量级一致):
    - booked_impressions 量级 10万-100万 → 1万-10万，使 6 个月总媒体花费 (~$82M)
      回落到 120 个 advertiser 年度预算之和 (~$174M) 的合理比例 (~6 个月 ≈ 年度 40%)，
      不再比客户分档预算 (§1.2 SMB/Mid/Enterprise) 大一个数量级。
    - campaign 选择按 campaign_weight (∝ advertiser 年度预算 / 该 advertiser 的 campaign 数)
      加权 → 每个 advertiser 的 placement 花费 ∝ 其年度预算，让花费落在自身分档内，
      从根本上消除"单 campaign 预算 > 客户整年预算"的矛盾 (Review-02 P1)。
    """
    records = []

    network_ids = network_data["id"].to_list()

    # 从 network 表读取参数（替换原 hardcoded dict，修复 Pluto 与 11-15）
    network_clearance_params: dict[int, tuple[float, float, float]] = {}
    for row in network_data.iter_rows(named=True):
        net_id = row["id"]
        # 用 Q4 作为基线（数据覆盖 5-10 月，Q4 月份会被特别处理；其他用 Q3 接近真实）
        network_clearance_params[net_id] = (
            row["avg_clearance_rate_q3"],
            row["avg_clearance_rate_q4"],
            row["clearance_rate_stddev"],
        )

    # 构建 "某天有哪些 campaign 处于活跃窗口" 的索引 (campaign[start,end] ∩ 数据窗)。
    # Review-01 修复策略: 先按全局月度权重 (Q4 10 月 1.4) 抽 air_date —— 保持原始月度
    # 分布 (5-9 月均衡 + 10 月 +40%)，再从"当日活跃 campaign"里选 campaign。
    # 这样既保证 placement 落在 campaign 窗口内 (0 越窗)，又不把月度量压成后移的斜坡。
    data_start = START_DATE.date()
    data_end = END_DATE.date()
    active_by_date: dict[date, list[int]] = {}
    active_wt_by_date: dict[date, list[float]] = {}
    for cid, (_adv_id, c_start, c_end) in campaign_meta.items():
        win_start = max(c_start, data_start)
        win_end = min(c_end, data_end)
        if win_end < win_start:
            win_end = win_start
        w = campaign_weight.get(cid, 1.0)
        d = win_start
        while d <= win_end:
            active_by_date.setdefault(d, []).append(cid)
            active_wt_by_date.setdefault(d, []).append(w)
            d += timedelta(days=1)

    # 仅在"有活跃 campaign"的日期上抽样 (几乎覆盖全部数据窗日)，权重 Q4(10 月)=1.4
    bucket_dates = sorted(active_by_date.keys())
    bucket_weights = [1.4 if d.month == 10 else 1.0 for d in bucket_dates]

    # ~pending placements 在数据快照末期（10/29-10/31）保持 pending
    pending_window_start = (END_DATE - timedelta(days=2)).date()

    for i in range(1, n + 1):
        # 先抽日期（全局月度权重），再从当日活跃 campaign 中按预算权重选取
        # → placement 必在窗口内，且花费 ∝ advertiser 年度预算 (Review-02 P1)
        air_date = random.choices(bucket_dates, weights=bucket_weights, k=1)[0]
        campaign_id = random.choices(
            active_by_date[air_date], weights=active_wt_by_date[air_date], k=1
        )[0]
        advertiser_id = campaign_meta[campaign_id][0]
        network_id = random.choice(network_ids)
        daypart_id = random.choice(daypart_ids)
        format_id = random.choice(format_ids)
        # 短 lead time 在真实业务中更常见；引入 75/90 天填充 >60 天分桶
        booking_lead_days = random.choices(
            BOOKING_LEAD_CHOICES,
            weights=BOOKING_LEAD_WEIGHTS,
            k=1
        )[0]

        # 根据时段确定播出时间
        if daypart_id == 4:  # 黄金时段
            air_hour = random.randint(20, 22)
        elif daypart_id == 2:  # 白天时段
            air_hour = random.randint(9, 15)
        else:
            air_hour = random.randint(6, 23)

        scheduled_air_time = datetime.combine(air_date, datetime.min.time()).replace(
            hour=air_hour, minute=random.randint(0, 59)
        )

        # CPM 基于网络和时段
        base_cpm = 25.0
        if network_id in [4, 5, 6, 7]:  # 广播网
            base_cpm = 40.0
        if daypart_id == 4:  # 黄金时段
            base_cpm *= 1.3
        elif daypart_id == 2:  # 白天时段
            base_cpm *= 0.7

        booked_cpm = round(base_cpm * random.uniform(0.85, 1.15), 2)
        # Review-02: 量级下调 (10万-100万 → 1万-10万)，使总媒体花费回落到客户分档预算量级
        booked_impressions = random.randint(10_000, 100_000)

        # 决定是否清除（基于网络特性和季度）
        quarter = (air_date.month - 1) // 3 + 1
        q3_clear, q4_clear, volatility = network_clearance_params.get(
            network_id, (0.88, 0.85, 0.05)
        )
        base_clear_rate = q4_clear if quarter == 4 else q3_clear

        # NFL Regular Season (2025-09-05 → 2025-10-31): ESPN/ESPN2/FOX 清除率下降 15-20%
        nfl_start = date(2025, 9, 5)
        nfl_end = date(2025, 10, 31)
        if network_id in [1, 2, 7] and nfl_start <= air_date <= nfl_end:
            base_clear_rate -= random.uniform(0.15, 0.20)

        # Lead time 越短，清除率越高（分级单调调整，见 lead_clearance_adjustment）
        base_clear_rate += lead_clearance_adjustment(booking_lead_days)

        # 注入 per-placement 噪声（volatility 现已使用）
        base_clear_rate = max(0.05, min(0.99, base_clear_rate + random.gauss(0, volatility)))

        # 数据快照末期保留 ~pending 状态（尚未确认是否播出）
        if air_date >= pending_window_start and random.random() < 0.25:
            status = "pending"
            actual_air_time = None
            data_source = None  # pending: 结果尚未回传，data_source 为 NULL
        else:
            cleared = random.random() < base_clear_rate
            status = "cleared" if cleared else "preempted"
            actual_air_time = scheduled_air_time if cleared else None
            # cleared/preempted 均已结案、有网络日志来源；仅 pending 为 NULL，
            # 使 preempted 与 pending 的区分维度真实可查 (data_source)。
            data_source = f"Network-{network_id}"

        # 数据到达时间（播出后 1-2 天）
        ingested_at = scheduled_air_time + timedelta(hours=random.randint(20, 48))

        records.append({
            "id": i,
            "placement_code": f"PL-2025-{i:06d}",
            "campaign_id": campaign_id,
            "advertiser_id": advertiser_id,
            "network_id": network_id,
            "daypart_id": daypart_id,
            "ad_format_id": format_id,
            "scheduled_air_date": air_date,
            "scheduled_air_time": scheduled_air_time,
            "booked_cpm": booked_cpm,
            "booked_impressions": booked_impressions,
            "booking_lead_days": booking_lead_days,
            "break_position": random.randint(1, 5),
            "status": status,
            "actual_air_time": actual_air_time,
            "data_source": data_source,
            "ingested_at": ingested_at,
            "updated_at": ingested_at,
        })

    return pl.DataFrame(records)


def gen_data_quality_logs(rule_ids: list[int], n_days: int = 180) -> pl.DataFrame:
    """生成数据质量日志（每天运行所有规则）"""
    records = []
    log_id = 1

    for day_offset in range(n_days):
        run_date = START_DATE + timedelta(days=day_offset)
        run_time = run_date.replace(hour=6, minute=30)

        for rule_id in rule_ids:
            rows_checked = random.randint(100, 2000)

            # 大部分规则通过，少数失败
            failure_prob = 0.03 if rule_id <= 5 else 0.01
            if random.random() < failure_prob:
                rows_failed = random.randint(1, int(rows_checked * 0.1))
                failure_rate = rows_failed / rows_checked
                status = "failed" if failure_rate > 0.05 else "warning"
                alert_fired = status == "failed"

                resolved_at = run_time + timedelta(hours=random.randint(1, 8)) if random.random() > 0.2 else None
                resolved_by = random.choice(["eng_maria", "eng_tom", "eng_sarah"]) if resolved_at else None
                resolution_note = "Issue resolved after vendor re-delivery" if resolved_at else None
            else:
                rows_failed = 0
                failure_rate = 0.0
                status = "passed"
                alert_fired = False
                resolved_at = None
                resolved_by = None
                resolution_note = None

            records.append({
                "id": log_id,
                "log_code": f"DQL-{run_date.strftime('%Y%m%d')}-{rule_id:03d}",
                "rule_id": rule_id,
                "run_timestamp": run_time,
                "rows_checked": rows_checked,
                "rows_failed": rows_failed,
                "failure_rate": round(failure_rate, 4),
                "status": status,
                "alert_fired": alert_fired,
                "sample_failures": json.dumps({"sample": "data"}) if rows_failed > 0 else None,
                "resolved_at": resolved_at,
                "resolved_by": resolved_by,
                "resolution_note": resolution_note,
            })
            log_id += 1

    # 使用显式 schema 避免类型推断问题
    schema = {
        "id": pl.Int64,
        "log_code": pl.Utf8,
        "rule_id": pl.Int64,
        "run_timestamp": pl.Datetime,
        "rows_checked": pl.Int64,
        "rows_failed": pl.Int64,
        "failure_rate": pl.Float64,
        "status": pl.Utf8,
        "alert_fired": pl.Boolean,
        "sample_failures": pl.Utf8,
        "resolved_at": pl.Datetime,
        "resolved_by": pl.Utf8,
        "resolution_note": pl.Utf8,
    }
    return pl.DataFrame(records, schema=schema, strict=False)


def gen_performance_actuals(
    placement_data: pl.DataFrame,
    partner_data: pl.DataFrame,
    advertiser_category_map: dict,
    network_data: pl.DataFrame,
) -> pl.DataFrame:
    """生成实际效果数据（只为已清除的广告位生成）

    Fixes vs review:
    - network_type 直接从 network 表读取（消除 unreachable elif 与 broadcast/cable 错位）
    - partner_delay 从 attribution_partner.typical_delay_hours 读取（不再 12/24 二选一）
    - roas_expectations 覆盖全部 8 个类别
    - AOV 按类别区分（避免恒定 $80 的退化分布）
    """
    records = []

    # 只选择已清除的广告位
    cleared_placements = placement_data.filter(pl.col("status") == "cleared")

    # ROAS 期望值矩阵：覆盖全部 8 个类别
    roas_expectations = {
        1: {"linear_cable": 1.4, "linear_broadcast": 1.1, "streaming_avod": 1.6},  # HEALTH
        2: {"linear_cable": 1.2, "linear_broadcast": 1.3, "streaming_avod": 1.5},  # FINANCE
        3: {"linear_cable": 1.1, "linear_broadcast": 0.9, "streaming_avod": 1.8},  # APPAREL
        4: {"linear_cable": 1.3, "linear_broadcast": 1.2, "streaming_avod": 1.4},  # FOOD_BEV
        5: {"linear_cable": 1.0, "linear_broadcast": 1.1, "streaming_avod": 1.7},  # TECH
        6: {"linear_cable": 1.5, "linear_broadcast": 1.2, "streaming_avod": 1.3},  # HOME
        7: {"linear_cable": 1.6, "linear_broadcast": 1.4, "streaming_avod": 1.2},  # AUTO
        8: {"linear_cable": 0.9, "linear_broadcast": 1.0, "streaming_avod": 1.5},  # TRAVEL
    }

    # 类别 AOV（$）：避免转化数恒为 revenue/80 的退化关系
    aov_by_category = {
        1: 65,   # HEALTH (补充剂订单偏小)
        2: 250,  # FINANCE (开户/保单)
        3: 95,   # APPAREL
        4: 35,   # FOOD_BEV
        5: 180,  # TECH (电子产品/订阅)
        6: 220,  # HOME (家具/电器)
        7: 750,  # AUTO (车险/试驾意向到成交)
        8: 380,  # TRAVEL (机酒打包)
    }

    # 从 network 表读取 network_type
    network_type_map = dict(zip(network_data["id"].to_list(), network_data["network_type"].to_list()))

    # 从 partner 表读取典型延迟
    partner_delay_map = dict(zip(partner_data["id"].to_list(), partner_data["typical_delay_hours"].to_list()))
    attribution_partner_ids = partner_data["id"].to_list()
    # Review-01 Q8 修复: 归因方法 → ROAS 系数 (pixel>ip>panel)
    partner_method_map = dict(zip(partner_data["id"].to_list(), partner_data["attribution_method"].to_list()))

    actual_id = 1
    for row in cleared_placements.iter_rows(named=True):
        placement_id = row["id"]
        advertiser_id = row["advertiser_id"]
        network_id = row["network_id"]
        booked_impressions = row["booked_impressions"]
        booked_cpm = row["booked_cpm"]
        scheduled_air_time = row["scheduled_air_time"]

        # 实际曝光数（通常接近预订数，±5%）
        impressions_delivered = int(booked_impressions * random.uniform(0.95, 1.05))
        spend_usd = round((impressions_delivered / 1000) * booked_cpm, 2)

        # 归因合作伙伴
        partner_id = random.choice(attribution_partner_ids)
        attribution_window = random.choice([7, 14, 30])

        # 获取广告主类别
        category_id = advertiser_category_map.get(advertiser_id, 1)

        # 根据网络类型和类别确定 ROAS 期望（直接读 network 表，不再硬编码 ID 段）
        network_type = network_type_map.get(network_id, "linear_cable")
        expected_roas = roas_expectations.get(category_id, {}).get(network_type, 1.2)

        # 体育网络对非体育/汽车类别 ROAS 较低（保留原业务规则）
        if network_id in [1, 2, 7] and category_id not in [7]:  # ESPN/ESPN2/FOX
            expected_roas *= 0.6

        # 归因方法对所测 ROAS 的系统性影响 (Q8): pixel 略高估、panel 系统性低估
        attr_method = partner_method_map.get(partner_id, "ip_match")
        expected_roas *= ATTRIBUTION_METHOD_ROAS_MULTIPLIER.get(attr_method, 1.0)

        # 生成 ROAS（带噪声）
        actual_roas = max(0.1, expected_roas * random.uniform(0.7, 1.3))

        # 根据 ROAS 计算转化和收入（AOV 按类别变化）
        attributed_revenue_usd = round(spend_usd * actual_roas, 2)
        avg_order_value = aov_by_category.get(category_id, 80)
        attributed_conversions = int(attributed_revenue_usd / avg_order_value)

        # 归因完成时间（播出后 + 归因窗口 + 合作伙伴延迟，从 partner 表读取）
        partner_delay = partner_delay_map.get(partner_id, 24)
        finalized_at = scheduled_air_time + timedelta(days=attribution_window) + timedelta(hours=partner_delay)
        ingested_at = finalized_at + timedelta(hours=random.randint(1, 6))

        records.append({
            "id": actual_id,
            "actual_code": f"ACT-{actual_id:06d}",
            "placement_id": placement_id,
            "impressions_delivered": impressions_delivered,
            "spend_usd": spend_usd,
            "attributed_conversions": attributed_conversions,
            "attributed_revenue_usd": attributed_revenue_usd,
            "roas": round(actual_roas, 2),
            "attribution_partner_id": partner_id,
            "attribution_window_days": attribution_window,
            "finalized_at": finalized_at,
            "ingested_at": ingested_at,
        })
        actual_id += 1

    return pl.DataFrame(records)


def gen_prediction_results(
    placement_data: pl.DataFrame,
    actual_data: pl.DataFrame,
    network_data: pl.DataFrame,
) -> pl.DataFrame:
    """生成 ML 预测结果（在预订前生成）

    设计要点:
    - **Model version 随机分配** (不再按时间切片): 三代版本对同分布数据做 "shadow scoring",
      让 Q14 的版本对比基于同样的数据难度。叙事: "三版本同时挂载,
      v2.3.1 是主用版本, 老版本继续 score 用于回溯评估"。
    - **prediction base_clear_rate 公式与 gen_ad_placements 完全对齐**:
      Q3/Q4 切换、NFL 罚分用 actual 同样的均值 0.175、分级 lead 加成
      (共用 lead_clearance_adjustment)。模型噪声 (model_noise) 是版本间唯一差异。
      但因类别极度不均衡, clearance 二分类准确率三代持平 ~86% (见 Q2/Q14)。
    - **predicted_roas 同样匹配 actual roas 公式 + model_noise**: 按 roas_model_version_id
      (配对 regressor) 分组的 ROAS MAPE 单调下降 (12→8→5)。
    """
    records = []

    buyers = ["buyer_sarah", "buyer_james", "buyer_emily", "buyer_michael"]
    # 从 network 表读出 q3/q4 清除率 (与 gen_ad_placements 一致)
    network_q_map = {
        row["id"]: (row["avg_clearance_rate_q3"], row["avg_clearance_rate_q4"])
        for row in network_data.iter_rows(named=True)
    }

    # 构造 placement_id → actual roas 映射
    actual_roas_map = dict(
        zip(actual_data["placement_id"].to_list(), actual_data["roas"].to_list())
    )

    nfl_start = date(2025, 9, 5)
    nfl_end = date(2025, 10, 31)
    # NFL 罚分的中位数（与 gen_ad_placements 的 uniform(0.15, 0.20) 同一期望值）
    nfl_penalty_mean = 0.175
    # 三个 clearance classifier 版本 ID（v2.1.5, v2.2.0, v2.3.1）+ 对应噪声幅度
    model_noise_by_version = {1: 0.12, 2: 0.08, 3: 0.05}
    model_version_ids = list(model_noise_by_version.keys())
    # Review-01 修复: clearance classifier(1/2/3) 配对同代 roas regressor(4/5/6)。
    # 一条预测同时挂分类器(clearance)与回归器(roas)，消除 roas_regressor 孤儿行，
    # 并让 "按 roas regressor 版本看 MAPE" 得到 12→8→5 的单调梯度。
    roas_version_for_classifier = {1: 4, 2: 5, 3: 6}

    # 为每个广告位生成预测
    for i, row in enumerate(placement_data.iter_rows(named=True), 1):
        placement_id = row["id"]
        network_id = row["network_id"]
        scheduled_air_date = row["scheduled_air_date"]
        booking_lead_days = row["booking_lead_days"]

        # 预测时间 = 预订日期（播出日期 - lead days）
        booking_date = datetime.combine(scheduled_air_date, datetime.min.time()) - timedelta(days=booking_lead_days)
        prediction_timestamp = booking_date.replace(hour=random.randint(9, 17), minute=random.randint(0, 59))

        # 随机分配模型版本（三版本同时挂载，回溯评估）
        model_version_id = random.choice(model_version_ids)
        model_noise = model_noise_by_version[model_version_id]
        roas_model_version_id = roas_version_for_classifier[model_version_id]

        # === base_clear_rate 计算: 与 gen_ad_placements 同一公式 ===
        quarter = (scheduled_air_date.month - 1) // 3 + 1
        q3_clear, q4_clear = network_q_map.get(network_id, (0.88, 0.85))
        base_clearance = q4_clear if quarter == 4 else q3_clear

        # NFL Regular Season (2025-09-05 → 2025-10-31): ESPN/ESPN2/FOX 清除率下降
        # 用均值 0.175 (actual uses uniform(0.15, 0.20) per-placement)
        if network_id in [1, 2, 7] and nfl_start <= scheduled_air_date <= nfl_end:
            base_clearance -= nfl_penalty_mean

        # Lead time → 清除率分级调整（与 gen_ad_placements 共用同一函数）
        base_clearance += lead_clearance_adjustment(booking_lead_days)

        # 模型预测 = base + 版本相关的均匀噪声
        predicted_clearance = max(0.05, min(0.99, base_clearance + random.uniform(-model_noise, model_noise)))

        # 预测 ROAS：以 actual 为锚 + 版本噪声；没有 actual 的 placement 用网络基线
        actual_roas = actual_roas_map.get(placement_id)
        if actual_roas is not None:
            relative_noise = random.uniform(-model_noise * 2, model_noise * 2)
            predicted_roas = actual_roas * (1 + relative_noise)
        else:
            if network_id in [1, 2, 7]:
                baseline_roas = 0.75
            elif network_id in [8, 9, 10]:
                baseline_roas = 1.55
            else:
                baseline_roas = 1.25
            predicted_roas = baseline_roas * (1 + random.uniform(-model_noise * 2, model_noise * 2))
        predicted_roas = max(0.1, predicted_roas)

        # 置信度
        if booking_lead_days >= 30:
            confidence = "low"
        elif booking_lead_days >= 14:
            confidence = "medium"
        else:
            confidence = "high"

        quarter = (scheduled_air_date.month - 1) // 3 + 1
        # Top 特征 (JSON)
        features = {
            "q4_sports_risk": "+" if quarter == 4 and network_id in [1, 2, 7] else "-",
            "lead_time": "+" if booking_lead_days < 14 else "-",
            "network_stability": "-" if network_id in [8, 9, 10] else "+",
        }

        records.append({
            "id": i,
            "prediction_code": f"PRED-{prediction_timestamp.strftime('%Y%m%d')}-{i:05d}",
            "placement_id": placement_id,
            "predicted_clearance_prob": round(predicted_clearance, 2),
            "predicted_roas": round(predicted_roas, 2),
            "confidence_level": confidence,
            "top_features": json.dumps(features),
            "model_version_id": model_version_id,
            "roas_model_version_id": roas_model_version_id,
            "prediction_timestamp": prediction_timestamp,
            "requested_by": random.choice(buyers),
        })

    return pl.DataFrame(records)


def gen_booking_history(placement_data: pl.DataFrame, n: int = 800) -> pl.DataFrame:
    """生成预订历史变更数据（部分广告位有变更）

    Fixes vs review:
    - changed_at 必须落在 [booking_date, scheduled_air_time] 区间内
      （cancellation 例外可发生在 scheduled_air_time 之前）
    """
    records = []
    change_types = ["status_change", "cpm_adjustment", "time_reschedule", "cancellation"]
    users = ["buyer_sarah", "buyer_james", "system_auto"]

    # 抽样 placements 并保留时间信息
    sampled = placement_data.sample(n=min(n, len(placement_data)), seed=RANDOM_SEED)

    for i, row in enumerate(sampled.iter_rows(named=True), 1):
        placement_id = row["id"]
        scheduled_air_time = row["scheduled_air_time"]
        booking_lead_days = row["booking_lead_days"]
        booking_dt = scheduled_air_time - timedelta(days=booking_lead_days)

        change_type = random.choice(change_types)

        # changed_at 落在 [booking_dt, scheduled_air_time] 区间
        window_seconds = int((scheduled_air_time - booking_dt).total_seconds())
        if window_seconds <= 0:
            changed_at = booking_dt
        else:
            changed_at = booking_dt + timedelta(seconds=random.randint(0, window_seconds))

        if change_type == "cpm_adjustment":
            old_value = "35.20"
            new_value = "38.50"
        elif change_type == "status_change":
            old_value = "pending"
            new_value = "cleared"
        else:
            old_value = "original_value"
            new_value = "new_value"

        records.append({
            "id": i,
            "placement_id": placement_id,
            "changed_at": changed_at,
            "changed_by": random.choice(users),
            "change_type": change_type,
            "old_value": old_value,
            "new_value": new_value,
        })

    return pl.DataFrame(records)


def gen_user_actions(placement_ids: list[int], n: int = 5000) -> pl.DataFrame:
    """生成用户操作审计数据"""
    records = []
    users = ["sarah_chen", "james_wilson", "emily_davis", "michael_brown", "system"]
    actions = ["view_placement", "create_prediction", "book_placement", "modify_booking", "cancel_booking", "view_analytics"]

    for i in range(1, n + 1):
        action_time = fake.date_time_between(start_date=START_DATE, end_date=END_DATE)
        action_type = random.choice(actions)
        placement_id = random.choice(placement_ids) if action_type != "view_analytics" else None

        records.append({
            "id": i,
            "user_name": random.choice(users),
            "action_type": action_type,
            "placement_id": placement_id,
            "action_timestamp": action_time,
            "ip_address": fake.ipv4(),
            "user_agent": fake.user_agent() if random.random() > 0.1 else None,
        })

    return pl.DataFrame(records)


def gen_alert_notifications(quality_log_data: pl.DataFrame) -> pl.DataFrame:
    """生成告警通知数据（只为触发告警的日志生成）"""
    records = []

    # 筛选触发告警的日志
    alert_logs = quality_log_data.filter(pl.col("alert_fired") == True)

    channels = ["slack", "email"]
    recipients = ["#data-quality", "eng-team@vantagemedia.com", "oncall@vantagemedia.com"]

    notification_id = 1
    for row in alert_logs.iter_rows(named=True):
        log_id = row["id"]
        run_timestamp = row["run_timestamp"]

        # 每个告警可能发送到多个渠道
        for channel in random.sample(channels, k=random.randint(1, 2)):
            sent_at = run_timestamp + timedelta(seconds=random.randint(1, 60))
            delivery_status = random.choices(["delivered", "failed"], weights=[0.95, 0.05])[0]

            records.append({
                "id": notification_id,
                "quality_log_id": log_id,
                "channel": channel,
                "recipient": random.choice(recipients),
                "sent_at": sent_at,
                "delivery_status": delivery_status,
            })
            notification_id += 1

    return pl.DataFrame(records)


# ============================================================================
# 辅助函数
# ============================================================================
def parse_date(value: Any) -> date | None:
    """解析日期字符串为 Python date 对象"""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        # 尝试解析常见的日期格式
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%d").date()
    return None


def parse_datetime(value: Any) -> datetime | None:
    """解析日期时间字符串为 Python datetime 对象"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # 尝试解析 ISO 格式的日期时间
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # 尝试其他常见格式
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
    return None


def convert_row_types(row: dict[str, Any], model_class: type) -> dict[str, Any]:
    """根据 ORM 模型定义转换行数据类型"""
    converted = {}
    for key, value in row.items():
        # 获取模型列的类型
        if hasattr(model_class, key):
            column = getattr(model_class, key)
            if hasattr(column, 'type'):
                col_type = column.type
                # Date 类型需要转换为 Python date 对象
                if isinstance(col_type, Date):
                    converted[key] = parse_date(value)
                # DateTime 类型需要转换为 Python datetime 对象
                elif isinstance(col_type, DateTime):
                    converted[key] = parse_datetime(value)
                else:
                    converted[key] = value
            else:
                converted[key] = value
        else:
            converted[key] = value
    return converted


# ============================================================================
# Review-01 修复辅助: 预算反推 + 校验摘要
# ============================================================================
def adjust_campaign_budgets(
    df_campaigns: pl.DataFrame,
    df_placements: pl.DataFrame,
    campaign_weight: dict[int, float],
) -> pl.DataFrame:
    """按每个 campaign 的 placement 计划花费 (booked) 反推 budget_usd。

    budget = 计划花费(所有 placement 的 booked_cpm×booked_impressions/1000 之和) × 系数。
    系数 uniform(0.9, 1.4): 由于实际花费(performance_actual, 仅 cleared) ≈ 计划花费×清除率(~0.85),
    多数 campaign 的 "预算剩余率" 落在合理正区间(~5%-40%)，少数(清除率偏高者)轻微超支，
    对应 ER DQR-009 "偶发预算超支告警"。

    Review-03 修复: 0-placement campaign 的兜底预算改为按其 advertiser 的"每 campaign 预算份额"
    (campaign_weight = advertiser 年度预算 / 该 advertiser 的 campaign 数) 的一个小比例,
    而非旧的固定常量 uniform(500K, 2M)(那是 impressions ÷9 之前的量级,会让 0-placement
    campaign 拿到 $1.3-1.86M、远超其 SMB 客户年预算)。新兜底 = 份额 × uniform(0.3, 0.8),
    天然 ≤ 客户年预算,且与客户分档成比例。
    """
    planned = (
        df_placements
        .with_columns(
            (pl.col("booked_impressions") / 1000.0 * pl.col("booked_cpm")).alias("planned_spend")
        )
        .group_by("campaign_id")
        .agg(pl.col("planned_spend").sum().alias("planned_spend"))
    )
    planned_map = dict(zip(planned["campaign_id"].to_list(), planned["planned_spend"].to_list()))

    new_budgets: list[float] = []
    for cid in df_campaigns["id"].to_list():
        ps = planned_map.get(cid)
        if ps is None or ps <= 0:
            # 0-placement campaign: 按其 advertiser 的每-campaign 预算份额给一个小兜底，
            # 保证 ≤ 客户年度预算且符合客户分档 (Review-03 P2)
            share = campaign_weight.get(cid, 0.0)
            if share > 0:
                new_budgets.append(round(share * random.uniform(0.3, 0.8), 2))
            else:
                new_budgets.append(round(random.uniform(20_000, 120_000), 2))
        else:
            new_budgets.append(round(ps * random.uniform(0.9, 1.4), 2))

    return df_campaigns.with_columns(pl.Series("budget_usd", new_budgets))


def print_validation_summary(
    df_placements: pl.DataFrame,
    df_actuals: pl.DataFrame,
    df_predictions: pl.DataFrame,
    df_campaigns: pl.DataFrame,
    df_networks: pl.DataFrame,
    df_partners: pl.DataFrame,
    df_models: pl.DataFrame,
    df_advertisers: pl.DataFrame,
) -> None:
    """打印 Review 关注的关键分布，便于核对 ER/SQL 文档数字（不写任何临时文件）。"""
    print("\n" + "=" * 70)
    print("📋 Review-01 修复验证摘要")
    print("=" * 70)

    total = len(df_placements)
    # --- 1. 状态分布 ---
    status_count: dict[str, int] = {}
    nt_map = dict(zip(df_networks["id"].to_list(), df_networks["network_type"].to_list()))
    # 预扫描 placements
    cid_window = {
        row["id"]: (row["start_date"], row["end_date"])
        for row in df_campaigns.iter_rows(named=True)
    }
    data_start, data_end = START_DATE.date(), END_DATE.date()

    month_count: dict[str, int] = {}
    month_gross: dict[str, float] = {}
    month_preempt_count: dict[str, int] = {}
    month_preempt_cost: dict[str, float] = {}
    lead_bucket_total: dict[str, int] = {}
    lead_bucket_cleared: dict[str, int] = {}
    nt_total: dict[str, int] = {}
    nt_cleared: dict[str, int] = {}
    out_of_window = 0

    def lead_bucket(d: int) -> str:
        if d <= 7: return "≤7天"
        if d <= 14: return "8-14天"
        if d <= 30: return "15-30天"
        if d <= 60: return "31-60天"
        return ">60天"

    for row in df_placements.iter_rows(named=True):
        st = row["status"]
        status_count[st] = status_count.get(st, 0) + 1
        ad = row["scheduled_air_date"]
        mkey = f"{ad.year}-{ad.month:02d}"
        month_count[mkey] = month_count.get(mkey, 0) + 1
        month_gross[mkey] = month_gross.get(mkey, 0.0) + row["booked_cpm"] * row["booked_impressions"] / 1000.0
        # 窗口检查
        ws, we = cid_window[row["campaign_id"]]
        eff_s, eff_e = max(ws, data_start), min(we, data_end)
        if ad < eff_s or ad > eff_e:
            out_of_window += 1
        # 仅对已结案(cleared/preempted)统计清除率相关
        if st in ("cleared", "preempted"):
            lb = lead_bucket(row["booking_lead_days"])
            lead_bucket_total[lb] = lead_bucket_total.get(lb, 0) + 1
            nt = nt_map.get(row["network_id"], "?")
            nt_total[nt] = nt_total.get(nt, 0) + 1
            if st == "cleared":
                lead_bucket_cleared[lb] = lead_bucket_cleared.get(lb, 0) + 1
                nt_cleared[nt] = nt_cleared.get(nt, 0) + 1
            if st == "preempted":
                month_preempt_count[mkey] = month_preempt_count.get(mkey, 0) + 1
                cost = row["booked_cpm"] * row["booked_impressions"] / 1000.0
                month_preempt_cost[mkey] = month_preempt_cost.get(mkey, 0.0) + cost

    print("\n[1] Placement 状态分布:")
    for st in ("cleared", "preempted", "pending"):
        c = status_count.get(st, 0)
        print(f"    {st:10s}: {c:6d} ({c / total * 100:.2f}%)")

    print("\n[2] 每月预订量 / 媒体购买金额(gross):")
    for mkey in sorted(month_count):
        print(f"    {mkey}: {month_count[mkey]:6d} 条, gross ${month_gross.get(mkey,0)/1e6:.2f}M")

    print("\n[3] 每月被抢占机会成本:")
    for mkey in sorted(month_preempt_count):
        print(f"    {mkey}: 被抢占 {month_preempt_count[mkey]:5d} 条, "
              f"机会成本 ${month_preempt_cost[mkey]/1e6:.2f}M, "
              f"平均 ${month_preempt_cost[mkey]/max(1,month_preempt_count[mkey])/1000:.1f}K")

    print("\n[4] 预订提前期 vs 清除率 (Q9):")
    for lb in ("≤7天", "8-14天", "15-30天", "31-60天", ">60天"):
        t = lead_bucket_total.get(lb, 0)
        c = lead_bucket_cleared.get(lb, 0)
        rate = c / t if t else 0.0
        print(f"    {lb:8s}: 总 {t:6d}, 清除率 {rate:.4f}")

    # --- 5. 网络类型清除率 + ROAS ---
    print("\n[5] 各网络类型 清除率 / 平均 ROAS:")
    # placement_id -> network_type
    pid_nt = {row["id"]: nt_map.get(row["network_id"], "?") for row in df_placements.iter_rows(named=True)}
    nt_roas_sum: dict[str, float] = {}
    nt_roas_n: dict[str, int] = {}
    for row in df_actuals.iter_rows(named=True):
        nt = pid_nt.get(row["placement_id"], "?")
        nt_roas_sum[nt] = nt_roas_sum.get(nt, 0.0) + row["roas"]
        nt_roas_n[nt] = nt_roas_n.get(nt, 0) + 1
    for nt in sorted(nt_total):
        cr = nt_cleared.get(nt, 0) / nt_total.get(nt, 1)
        avg_roas = nt_roas_sum.get(nt, 0.0) / max(1, nt_roas_n.get(nt, 0))
        print(f"    {nt:18s}: 已结案 {nt_total.get(nt,0):6d}, 清除率 {cr:.3f}, 平均 ROAS {avg_roas:.3f}")

    # --- 6. 归因方法 / partner 平均 ROAS (Q8) ---
    print("\n[6] 归因 partner 平均 ROAS (Q8):")
    partner_name = dict(zip(df_partners["id"].to_list(), df_partners["partner_name"].to_list()))
    partner_method = dict(zip(df_partners["id"].to_list(), df_partners["attribution_method"].to_list()))
    p_sum: dict[int, float] = {}
    p_n: dict[int, int] = {}
    for row in df_actuals.iter_rows(named=True):
        pid = row["attribution_partner_id"]
        p_sum[pid] = p_sum.get(pid, 0.0) + row["roas"]
        p_n[pid] = p_n.get(pid, 0) + 1
    for pid in sorted(p_sum, key=lambda k: -(p_sum[k] / max(1, p_n[k]))):
        print(f"    {partner_name.get(pid,'?'):18s} ({partner_method.get(pid,'?'):20s}): "
              f"平均 ROAS {p_sum[pid]/max(1,p_n[pid]):.3f} (n={p_n[pid]})")

    # --- 7. campaign 预算 vs 花费 (Q15) ---
    print("\n[7] Campaign 预算 vs 实际花费 (Q15):")
    pid_campaign = {row["id"]: row["campaign_id"] for row in df_placements.iter_rows(named=True)}
    camp_spend: dict[int, float] = {}
    for row in df_actuals.iter_rows(named=True):
        cid = pid_campaign.get(row["placement_id"])
        if cid is not None:
            camp_spend[cid] = camp_spend.get(cid, 0.0) + row["spend_usd"]
    budget_map = dict(zip(df_campaigns["id"].to_list(), df_campaigns["budget_usd"].to_list()))
    rem_rates = []
    overrun = 0
    n_camp = 0
    for cid, bud in budget_map.items():
        sp = camp_spend.get(cid, 0.0)
        if sp <= 0 or bud <= 0:
            continue
        n_camp += 1
        rem = (bud - sp) / bud
        rem_rates.append(rem)
        if rem < 0:
            overrun += 1
    if rem_rates:
        rem_rates_sorted = sorted(rem_rates)
        avg_bud = sum(budget_map.values()) / len(budget_map)
        avg_sp = sum(camp_spend.values()) / max(1, len(camp_spend))
        print(f"    平均预算 ${avg_bud/1e6:.2f}M, 平均实际花费 ${avg_sp/1e6:.2f}M")
        print(f"    预算剩余率: 最低 {rem_rates_sorted[0]*100:.1f}%, "
              f"中位 {rem_rates_sorted[len(rem_rates_sorted)//2]*100:.1f}%, "
              f"最高 {rem_rates_sorted[-1]*100:.1f}%")
        print(f"    超支 campaign 数 (剩余率<0): {overrun}/{n_camp} ({overrun/n_camp*100:.1f}%)")

    # --- 7b. campaign 预算 vs advertiser 年度预算一致性 (Review-02 P1) ---
    print("\n[7b] Campaign 预算 vs Advertiser 年度预算 (Review-02 P1):")
    adv_budget = dict(zip(df_advertisers["id"].to_list(), df_advertisers["total_budget_usd"].to_list()))
    camp_adv = dict(zip(df_campaigns["id"].to_list(), df_campaigns["advertiser_id"].to_list()))
    # 每个 advertiser 的 campaign 预算之和 + 6 个月实际花费
    adv_camp_budget_sum: dict[int, float] = {}
    adv_spend_sum: dict[int, float] = {}
    for cid, bud in budget_map.items():
        aid = camp_adv.get(cid)
        if aid is None:
            continue
        adv_camp_budget_sum[aid] = adv_camp_budget_sum.get(aid, 0.0) + bud
        adv_spend_sum[aid] = adv_spend_sum.get(aid, 0.0) + camp_spend.get(cid, 0.0)
    # 单 campaign 预算 > 其 advertiser 年度预算 的数量
    camp_over_adv = sum(
        1 for cid, bud in budget_map.items()
        if camp_adv.get(cid) is not None and bud > adv_budget.get(camp_adv[cid], 0.0)
    )
    ratios = [
        adv_camp_budget_sum[aid] / adv_budget[aid]
        for aid in adv_camp_budget_sum if adv_budget.get(aid, 0) > 0
    ]
    spend_ratios = [
        adv_spend_sum[aid] / adv_budget[aid]
        for aid in adv_spend_sum if adv_budget.get(aid, 0) > 0
    ]
    avg_adv_budget = sum(adv_budget.values()) / max(1, len(adv_budget))
    avg_camp_budget_sum = sum(adv_camp_budget_sum.values()) / max(1, len(adv_camp_budget_sum))
    print(f"    平均 advertiser 年度预算 ${avg_adv_budget/1e6:.2f}M, "
          f"平均(旗下 campaign 预算之和) ${avg_camp_budget_sum/1e6:.2f}M")
    if ratios:
        ratios_sorted = sorted(ratios)
        print(f"    (campaign预算和 / 年度预算) 比值: 中位 {ratios_sorted[len(ratios_sorted)//2]:.2f}×, "
              f"最高 {ratios_sorted[-1]:.2f}×")
    if spend_ratios:
        sr = sorted(spend_ratios)
        print(f"    (6个月实际花费 / 年度预算) 比值: 中位 {sr[len(sr)//2]:.2f}×, 最高 {sr[-1]:.2f}×")
    print(f"    单 campaign 预算 > 其 advertiser 年度预算 的数量: {camp_over_adv}/{len(budget_map)}")
    print(f"    campaign 预算范围: ${min(budget_map.values())/1e3:.0f}K ~ ${max(budget_map.values())/1e6:.2f}M; "
          f"advertiser 年度预算范围: ${min(adv_budget.values())/1e3:.0f}K ~ ${max(adv_budget.values())/1e6:.2f}M")
    # 0-placement campaign 兜底预算诊断 (Review-03 P2)
    camp_placement_cnt: dict[int, int] = {}
    for _cid in pid_campaign.values():
        camp_placement_cnt[_cid] = camp_placement_cnt.get(_cid, 0) + 1
    zero_pl = [cid for cid in budget_map if camp_placement_cnt.get(cid, 0) == 0]
    if zero_pl:
        zmax = max(budget_map[cid] for cid in zero_pl)
        zover = sum(
            1 for cid in zero_pl
            if camp_adv.get(cid) is not None and budget_map[cid] > adv_budget.get(camp_adv[cid], 0.0)
        )
        print(f"    0-placement campaign: {len(zero_pl)} 个, 兜底预算最高 ${zmax/1e3:.0f}K, "
              f"其中超客户年预算 {zover} 个")

    # --- 8. model_version 使用分布 ---
    print("\n[8] prediction model_version 使用分布:")
    mv_name = dict(zip(df_models["id"].to_list(), df_models["version_code"].to_list()))
    clf_count: dict[int, int] = {}
    reg_count: dict[int, int] = {}
    for row in df_predictions.iter_rows(named=True):
        clf_count[row["model_version_id"]] = clf_count.get(row["model_version_id"], 0) + 1
        reg_count[row["roas_model_version_id"]] = reg_count.get(row["roas_model_version_id"], 0) + 1
    print("    classifier (model_version_id):")
    for mid in sorted(clf_count):
        print(f"      id={mid} {mv_name.get(mid,'?'):14s}: {clf_count[mid]}")
    print("    roas regressor (roas_model_version_id):")
    for mid in sorted(reg_count):
        print(f"      id={mid} {mv_name.get(mid,'?'):14s}: {reg_count[mid]}")

    # --- 9. ROAS MAPE by classifier / regressor 版本 (Q4/Q14) ---
    pid_actual_roas = {row["placement_id"]: row["roas"] for row in df_actuals.iter_rows(named=True)}
    clf_mape_sum: dict[int, float] = {}
    clf_mape_n: dict[int, int] = {}
    reg_mape_sum: dict[int, float] = {}
    reg_mape_n: dict[int, int] = {}
    for row in df_predictions.iter_rows(named=True):
        ar = pid_actual_roas.get(row["placement_id"])
        if ar is None or ar <= 0:
            continue
        ape = abs(row["predicted_roas"] - ar) / ar
        cid_v = row["model_version_id"]
        rid_v = row["roas_model_version_id"]
        clf_mape_sum[cid_v] = clf_mape_sum.get(cid_v, 0.0) + ape
        clf_mape_n[cid_v] = clf_mape_n.get(cid_v, 0) + 1
        reg_mape_sum[rid_v] = reg_mape_sum.get(rid_v, 0.0) + ape
        reg_mape_n[rid_v] = reg_mape_n.get(rid_v, 0) + 1
    print("\n[9] ROAS MAPE (按 roas regressor 版本, Q14 footer):")
    for mid in sorted(reg_mape_sum):
        print(f"      id={mid} {mv_name.get(mid,'?'):14s}: MAPE {reg_mape_sum[mid]/max(1,reg_mape_n[mid])*100:.2f}%")

    # --- 10. 窗口一致性 + 预测准确率 ---
    print("\n[10] 跨表一致性:")
    print(f"    placement 越出 campaign 窗口数: {out_of_window}/{total} ({out_of_window/total*100:.2f}%)")
    # 二分类准确率 by classifier 版本
    pid_status = {row["id"]: row["status"] for row in df_placements.iter_rows(named=True)}
    acc_correct: dict[int, int] = {}
    acc_total: dict[int, int] = {}
    for row in df_predictions.iter_rows(named=True):
        st = pid_status.get(row["placement_id"])
        if st not in ("cleared", "preempted"):
            continue
        mid = row["model_version_id"]
        acc_total[mid] = acc_total.get(mid, 0) + 1
        pred_clear = row["predicted_clearance_prob"] >= 0.5
        if (pred_clear and st == "cleared") or (not pred_clear and st == "preempted"):
            acc_correct[mid] = acc_correct.get(mid, 0) + 1
    print("    clearance 二分类准确率 by classifier 版本:")
    for mid in sorted(acc_total):
        print(f"      id={mid} {mv_name.get(mid,'?'):14s}: 准确率 {acc_correct.get(mid,0)/max(1,acc_total[mid])*100:.2f}%")

    # --- 11. Q18 预测清除概率分桶 (仅 cleared+preempted) ---
    print("\n[11] 预测清除概率分桶 (Q18, 仅 cleared+preempted):")
    q18_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    q18_count = {lab: 0 for lab in q18_labels}
    q18_n = 0
    for row in df_predictions.iter_rows(named=True):
        st = pid_status.get(row["placement_id"])
        if st not in ("cleared", "preempted"):
            continue
        p = row["predicted_clearance_prob"]
        if p < 0.2:
            lab = "0.0-0.2"
        elif p < 0.4:
            lab = "0.2-0.4"
        elif p < 0.6:
            lab = "0.4-0.6"
        elif p < 0.8:
            lab = "0.6-0.8"
        else:
            lab = "0.8-1.0"
        q18_count[lab] += 1
        q18_n += 1
    for lab in q18_labels:
        c = q18_count[lab]
        print(f"      {lab}: {c:6d} ({c/max(1,q18_n)*100:.1f}%)")
    print(f"      (合计 n = {q18_n})")
    print("=" * 70)


# ============================================================================
# 核心函数（幂等操作）
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有 TSV 文件。幂等操作：先删除已存在的文件"""
    # 确保数据目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 删除已存在的 TSV 文件
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("开始生成数据...")

    # 第一层：枚举表（无外键依赖）
    print("生成枚举和配置表...")
    df_categories = gen_advertiser_categories()
    df_categories.write_csv(DATA_DIR / "01_advertiser_category.tsv", separator="\t")

    df_dayparts = gen_dayparts()
    df_dayparts.write_csv(DATA_DIR / "02_daypart.tsv", separator="\t")

    df_formats = gen_ad_formats()
    df_formats.write_csv(DATA_DIR / "03_ad_format.tsv", separator="\t")

    df_partners = gen_attribution_partners()
    df_partners.write_csv(DATA_DIR / "04_attribution_partner.tsv", separator="\t")

    df_events = gen_seasonal_events()
    df_events.write_csv(DATA_DIR / "05_seasonal_event.tsv", separator="\t")

    df_models = gen_model_versions()
    df_models.write_csv(DATA_DIR / "06_model_version.tsv", separator="\t")

    # 第二层：维度表
    print("生成维度表...")
    df_networks = gen_networks()
    df_networks.write_csv(DATA_DIR / "07_network.tsv", separator="\t")

    df_advertisers = gen_advertisers(n=120)
    df_advertisers.write_csv(DATA_DIR / "08_advertiser.tsv", separator="\t")

    df_rules = gen_data_quality_rules()
    df_rules.write_csv(DATA_DIR / "09_data_quality_rule.tsv", separator="\t")

    # 第三层：依赖第二层的表
    print("生成活动和支撑表...")
    df_campaigns = gen_campaigns(advertiser_ids=df_advertisers["id"].to_list(), n=400)
    # 注意: campaign 的 TSV 延后写出 —— budget_usd 需按 placement 计划花费反推 (Review-01 Q15 修复)

    df_clearance_hist = gen_network_clearance_history(network_ids=df_networks["id"].to_list())
    df_clearance_hist.write_csv(DATA_DIR / "11_network_clearance_history.tsv", separator="\t")

    df_sla = gen_data_source_sla()
    df_sla.write_csv(DATA_DIR / "12_data_source_sla.tsv", separator="\t")

    df_ingestion = gen_ingestion_metadata(n=180)
    df_ingestion.write_csv(DATA_DIR / "13_ingestion_metadata.tsv", separator="\t")

    # 第四层：核心事实表
    print("生成广告位预订数据（核心事实表）...")
    # 构造 campaign_meta: campaign_id → (advertiser_id, start_date, end_date)
    # - advertiser_id 保证 ad_placement 与 campaign 反规范化一致
    # - start/end 让 placement 的 air_date 落在 campaign 时间窗内 (Review-01 修复)
    campaign_meta = {
        row["id"]: (row["advertiser_id"], row["start_date"], row["end_date"])
        for row in df_campaigns.iter_rows(named=True)
    }
    # campaign 选择权重 ∝ advertiser 年度预算 / 该 advertiser 的 campaign 数 (Review-02 P1)
    # → placement 花费 ∝ advertiser 预算，让各客户花费落在 §1.2 分档内
    advertiser_budget_map = dict(
        zip(df_advertisers["id"].to_list(), df_advertisers["total_budget_usd"].to_list())
    )
    adv_campaign_count: dict[int, int] = {}
    for _adv_id, _s, _e in campaign_meta.values():
        adv_campaign_count[_adv_id] = adv_campaign_count.get(_adv_id, 0) + 1
    campaign_weight = {
        cid: advertiser_budget_map.get(adv_id, 1.0) / max(1, adv_campaign_count.get(adv_id, 1))
        for cid, (adv_id, _s, _e) in campaign_meta.items()
    }
    df_placements = gen_ad_placements(
        campaign_meta=campaign_meta,
        campaign_weight=campaign_weight,
        network_data=df_networks,
        daypart_ids=df_dayparts["id"].to_list(),
        format_ids=df_formats["id"].to_list(),
        n=50000
    )
    df_placements.write_csv(DATA_DIR / "14_ad_placement.tsv", separator="\t")

    # 按每个 campaign 的 placement 计划花费 (booked) 反推 budget_usd (Review-01 Q15 修复)
    # 旧版 budget 独立 random.uniform(50K,500K)，被 ~$1.7M 实际花费碾压 8.4×，
    # 导致 Q15 "预算剩余率" 恒为 -290%~-1900%。现在 budget = 计划花费 × 系数。
    # 0-placement campaign 用按客户预算份额的小兜底 (Review-03 P2)，传入 campaign_weight。
    df_campaigns = adjust_campaign_budgets(df_campaigns, df_placements, campaign_weight)
    df_campaigns.write_csv(DATA_DIR / "10_campaign.tsv", separator="\t")

    df_quality_logs = gen_data_quality_logs(rule_ids=df_rules["id"].to_list(), n_days=180)
    df_quality_logs.write_csv(DATA_DIR / "15_data_quality_log.tsv", separator="\t")

    # 第五层：依赖广告位的表
    print("生成效果数据和预测结果...")

    # 创建广告主类别映射
    advertiser_category_map = dict(zip(df_advertisers["id"].to_list(), df_advertisers["category_id"].to_list()))

    df_actuals = gen_performance_actuals(
        placement_data=df_placements,
        partner_data=df_partners,
        advertiser_category_map=advertiser_category_map,
        network_data=df_networks,
    )
    df_actuals.write_csv(DATA_DIR / "16_performance_actual.tsv", separator="\t")

    df_predictions = gen_prediction_results(
        placement_data=df_placements,
        actual_data=df_actuals,
        network_data=df_networks,
    )
    df_predictions.write_csv(DATA_DIR / "17_prediction_result.tsv", separator="\t")

    df_booking_hist = gen_booking_history(placement_data=df_placements, n=3000)
    df_booking_hist.write_csv(DATA_DIR / "18_booking_history.tsv", separator="\t")

    df_user_actions = gen_user_actions(placement_ids=df_placements["id"].to_list(), n=15000)
    df_user_actions.write_csv(DATA_DIR / "19_user_action.tsv", separator="\t")

    df_alerts = gen_alert_notifications(quality_log_data=df_quality_logs)
    df_alerts.write_csv(DATA_DIR / "20_alert_notification.tsv", separator="\t")

    print(f"✅ 已在 {DATA_DIR} 生成所有 TSV 文件")
    print(f"📊 数据统计:")
    print(f"   - 广告主: {len(df_advertisers)} 个")
    print(f"   - 广告活动: {len(df_campaigns)} 个")
    print(f"   - 广告位预订: {len(df_placements)} 条")
    print(f"   - 已清除广告位: {len(df_placements.filter(pl.col('status') == 'cleared'))} 条")
    print(f"   - 实际效果数据: {len(df_actuals)} 条")
    print(f"   - ML 预测记录: {len(df_predictions)} 条")
    print(f"   - 数据质量日志: {len(df_quality_logs)} 条")

    # Review 修复验证: 打印关键分布，供核对文档数字 (无需额外脚本)
    print_validation_summary(
        df_placements, df_actuals, df_predictions, df_campaigns,
        df_networks, df_partners, df_models, df_advertisers,
    )


def create_sqlite_database() -> None:
    """从 TSV 文件创建 SQLite 数据库。幂等操作：先删除已存在的数据库"""
    # 删除已存在的数据库
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    print("创建 SQLite 数据库...")
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # 按拓扑顺序加载 TSV 文件
        print("加载数据到数据库...")

        # 第一层
        df = pl.read_csv(DATA_DIR / "01_advertiser_category.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(AdvertiserCategory(**convert_row_types(row, AdvertiserCategory)))

        df = pl.read_csv(DATA_DIR / "02_daypart.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Daypart(**convert_row_types(row, Daypart)))

        df = pl.read_csv(DATA_DIR / "03_ad_format.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(AdFormat(**convert_row_types(row, AdFormat)))

        df = pl.read_csv(DATA_DIR / "04_attribution_partner.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(AttributionPartner(**convert_row_types(row, AttributionPartner)))

        df = pl.read_csv(DATA_DIR / "05_seasonal_event.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(SeasonalEvent(**convert_row_types(row, SeasonalEvent)))

        df = pl.read_csv(DATA_DIR / "06_model_version.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(ModelVersion(**convert_row_types(row, ModelVersion)))

        # 第二层
        df = pl.read_csv(DATA_DIR / "07_network.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Network(**convert_row_types(row, Network)))

        df = pl.read_csv(DATA_DIR / "08_advertiser.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Advertiser(**convert_row_types(row, Advertiser)))

        df = pl.read_csv(DATA_DIR / "09_data_quality_rule.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(DataQualityRule(**convert_row_types(row, DataQualityRule)))

        # 第三层
        df = pl.read_csv(DATA_DIR / "10_campaign.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Campaign(**convert_row_types(row, Campaign)))

        df = pl.read_csv(DATA_DIR / "11_network_clearance_history.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(NetworkClearanceHistory(**convert_row_types(row, NetworkClearanceHistory)))

        df = pl.read_csv(DATA_DIR / "12_data_source_sla.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(DataSourceSLA(**convert_row_types(row, DataSourceSLA)))

        df = pl.read_csv(DATA_DIR / "13_ingestion_metadata.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(IngestionMetadata(**convert_row_types(row, IngestionMetadata)))

        # 第四层
        df = pl.read_csv(DATA_DIR / "14_ad_placement.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(AdPlacement(**convert_row_types(row, AdPlacement)))

        df = pl.read_csv(DATA_DIR / "15_data_quality_log.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(DataQualityLog(**convert_row_types(row, DataQualityLog)))

        # 第五层
        df = pl.read_csv(DATA_DIR / "16_performance_actual.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(PerformanceActual(**convert_row_types(row, PerformanceActual)))

        df = pl.read_csv(DATA_DIR / "17_prediction_result.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(PredictionResult(**convert_row_types(row, PredictionResult)))

        df = pl.read_csv(DATA_DIR / "18_booking_history.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(BookingHistory(**convert_row_types(row, BookingHistory)))

        df = pl.read_csv(DATA_DIR / "19_user_action.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(UserAction(**convert_row_types(row, UserAction)))

        df = pl.read_csv(DATA_DIR / "20_alert_notification.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(AlertNotification(**convert_row_types(row, AlertNotification)))

        session.commit()

    print(f"✅ 已在 {DATABASE_PATH} 创建 SQLite 数据库")


def main() -> None:
    """主入口函数"""
    print("=" * 80)
    print("广告技术 - CTV 广告投放分析数据集生成器 (Vantage Media Booking Copilot)")
    print("复杂度: High | 表数量: 20 | 预计总行数: ~150,000+")
    print("=" * 80)
    print()

    generate_all_tsv()
    print()
    create_sqlite_database()
    print()
    print("=" * 80)
    print("✅ 全部完成！")
    print(f"📁 数据文件: {DATA_DIR}")
    print(f"🗄️  数据库: {DATABASE_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
