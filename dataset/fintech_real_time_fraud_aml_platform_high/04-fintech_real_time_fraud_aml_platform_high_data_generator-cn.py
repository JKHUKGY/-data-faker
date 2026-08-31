"""
FinTech - 实时欺诈与 AML 平台 假数据生成器
复杂度: High
生成者: Fake Data Generator Agent

业务背景:
NovaRisk AI 是一个虚构的 AI 原生实时欺诈与反洗钱 (AML)
SaaS 平台 (参照 DataVisor / Feedzai / Featurespace 等公司建模)。
银行、信用合作社、fintech、BNPL 服务商和支付处理商会将
NovaRisk 的实时评分 API 集成到自己的交易流程中。每一笔支付、登录
或开户事件都会在 < 100 ms 内被评分。高风险事件会生成告警 (alert),
告警会被汇总成调查案件 (case),确认的洗钱案件
则会作为可疑活动报告 (SAR) 上报给 FinCEN。

本数据集模拟了横跨 12 家客户机构的整整一个季度的活动,
并完整记录了从原始交易事件到监管申报的全部数据血缘,
外加欺诈分析师用自然语言询问系统时所产生的
对话式 AI agent (Vera 风格) 审计日志。
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
from faker import Faker
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "fintech_real_time_fraud_aml_platform_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# 基准模拟窗口: 一个季度, 截止到今天
NOW = datetime(2026, 6, 5, 0, 0, 0)
WINDOW_START = NOW - timedelta(days=90)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


# ----- 参考表 / Enum 表 -----------------------------------------------
class IndustryVertical(Base):
    """NovaRisk B2B 客户所属的垂直行业 (银行、fintech 等)。"""
    __tablename__ = "industry_vertical"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255))


class FraudTypeDim(Base):
    """欺诈 / 洗钱手法 (typology) 目录。"""
    __tablename__ = "fraud_type_dim"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255))
    severity_weight: Mapped[float] = mapped_column(Float, nullable=False)


class RiskDecisionDim(Base):
    """评分引擎针对每个事件可以给出的输出决策。"""
    __tablename__ = "risk_decision_dim"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255))


class AlertStatusDim(Base):
    """告警 (alert) 的生命周期状态。"""
    __tablename__ = "alert_status_dim"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255))


class CaseStatusDim(Base):
    """调查案件 (case) 的生命周期状态。"""
    __tablename__ = "case_status_dim"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255))


# ----- 核心实体 ----------------------------------------------------------
class ClientInstitution(Base):
    """购买 NovaRisk 平台的银行 / fintech (即 NovaRisk 的客户)。"""
    __tablename__ = "client_institution"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(120), nullable=False)
    industry_vertical_id: Mapped[int] = mapped_column(ForeignKey("industry_vertical.id"), nullable=False)
    headquarters_country: Mapped[str] = mapped_column(String(60))
    headquarters_state: Mapped[str] = mapped_column(String(60))
    contract_start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    annual_contract_value_usd: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SanctionsWatchlist(Base):
    """用于 AML 筛查的 OFAC / PEP / 内部 watchlist 条目。"""
    __tablename__ = "sanctions_watchlist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_source: Mapped[str] = mapped_column(String(40), nullable=False)
    listed_name: Mapped[str] = mapped_column(String(160), nullable=False)
    listed_country: Mapped[str] = mapped_column(String(60))
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    added_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Device(Base):
    """根据浏览器/移动端信号计算出的唯一设备指纹。"""
    __tablename__ = "device"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)
    os_family: Mapped[str] = mapped_column(String(20), nullable=False)
    browser_family: Mapped[str] = mapped_column(String(30))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_emulator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MlModel(Base):
    """为某个客户部署的评分模型版本。"""
    __tablename__ = "ml_model"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_institution_id: Mapped[int] = mapped_column(ForeignKey("client_institution.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_family: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_champion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DetectionRule(Base):
    """决策引擎按客户使用的手工编写规则。"""
    __tablename__ = "detection_rule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_institution_id: Mapped[int] = mapped_column(ForeignKey("client_institution.id"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_description: Mapped[str] = mapped_column(String(255), nullable=False)
    threshold_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Analyst(Base):
    """受雇于某客户机构的欺诈 / AML 分析师。"""
    __tablename__ = "analyst"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_institution_id: Mapped[int] = mapped_column(ForeignKey("client_institution.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    seniority: Mapped[str] = mapped_column(String(20), nullable=False)
    hired_on: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EndUser(Base):
    """在某客户机构开立了账户的消费者 / 企业。"""
    __tablename__ = "end_user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_institution_id: Mapped[int] = mapped_column(ForeignKey("client_institution.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    onboarded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    kyc_status: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_risk_rating: Mapped[str] = mapped_column(String(20), nullable=False)
    is_pep_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Account(Base):
    """某客户机构中的金融账户 (支票、储蓄、卡、钱包)。"""
    __tablename__ = "account"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    end_user_id: Mapped[int] = mapped_column(ForeignKey("end_user.id"), nullable=False)
    client_institution_id: Mapped[int] = mapped_column(ForeignKey("client_institution.id"), nullable=False)
    account_number_masked: Mapped[str] = mapped_column(String(40), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_limit_usd: Mapped[float] = mapped_column(Float, nullable=False)


class DeviceSession(Base):
    """将设备与终端用户关联起来的登录 / app 会话。"""
    __tablename__ = "device_session"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), nullable=False)
    end_user_id: Mapped[int] = mapped_column(ForeignKey("end_user.id"), nullable=False)
    session_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    session_ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    geo_country: Mapped[str] = mapped_column(String(60))
    geo_city: Mapped[str] = mapped_column(String(80))
    is_vpn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Transaction(Base):
    """流经客户系统的支付 / 转账事件。"""
    __tablename__ = "transaction"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    destination_account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True)
    device_session_id: Mapped[int] = mapped_column(ForeignKey("device_session.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    counterparty_country: Mapped[str] = mapped_column(String(60))
    initiated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_high_risk_corridor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RiskScoreEvent(Base):
    """实时评分 API 针对单笔交易的输出。"""
    __tablename__ = "risk_score_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id"), nullable=False, unique=True)
    ml_model_id: Mapped[int] = mapped_column(ForeignKey("ml_model.id"), nullable=False)
    decision_id: Mapped[int] = mapped_column(ForeignKey("risk_decision_dim.id"), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    top_feature: Mapped[str] = mapped_column(String(80), nullable=False)


class Alert(Base):
    """当某笔交易触发规则或评分过高时产生的告警。"""
    __tablename__ = "alert"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction.id"), nullable=False)
    detection_rule_id: Mapped[int | None] = mapped_column(ForeignKey("detection_rule.id"), nullable=True)
    fraud_type_id: Mapped[int] = mapped_column(ForeignKey("fraud_type_dim.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(ForeignKey("alert_status_dim.id"), nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("investigation_case.id"), nullable=True)
    watchlist_match_id: Mapped[int | None] = mapped_column(ForeignKey("sanctions_watchlist.id"), nullable=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_true_positive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class InvestigationCase(Base):
    """将相关告警汇总到某位分析师名下进行调查的案件。"""
    __tablename__ = "investigation_case"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_institution_id: Mapped[int] = mapped_column(ForeignKey("client_institution.id"), nullable=False)
    assigned_analyst_id: Mapped[int] = mapped_column(ForeignKey("analyst.id"), nullable=False)
    case_status_id: Mapped[int] = mapped_column(ForeignKey("case_status_dim.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_exposure_usd: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)


class SarReport(Base):
    """针对某案件上报给 FinCEN 的 SAR (可疑活动报告)。"""
    __tablename__ = "sar_report"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("investigation_case.id"), nullable=False, unique=True)
    watchlist_match_id: Mapped[int | None] = mapped_column(ForeignKey("sanctions_watchlist.id"), nullable=True)
    filing_reference: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    filed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    narrative_summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_reported_amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    ai_drafted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AgentInteractionLog(Base):
    """对话式 AI agent (Vera 风格) 与分析师之间的交互。"""
    __tablename__ = "agent_interaction_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analyst_id: Mapped[int] = mapped_column(ForeignKey("analyst.id"), nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("investigation_case.id"), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(40), nullable=False)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    tool_called: Mapped[str] = mapped_column(String(60), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    human_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ============================================================================
# 参考表 / Enum 数据
# ============================================================================
INDUSTRY_VERTICALS = [
    ("commercial_bank", "Commercial bank serving SMB and enterprise clients"),
    ("credit_union", "Member-owned credit union"),
    ("digital_fintech", "Cloud-native challenger fintech"),
    ("bnpl_lender", "Buy-Now-Pay-Later consumer lender"),
    ("payment_processor", "Card / ACH payment processor"),
]

FRAUD_TYPES = [
    ("account_takeover", "Legitimate account is hijacked by an attacker", 1.0),
    ("new_account_fraud", "Synthetic or stolen identity used to open an account", 0.95),
    ("ach_fraud", "Unauthorized ACH debit / push payment", 0.85),
    ("card_not_present", "Stolen card credentials used in an online purchase", 0.80),
    ("wire_fraud", "Unauthorized international wire", 1.10),
    ("mule_account", "Account knowingly or unknowingly used to launder funds", 1.05),
    ("bust_out", "Long-grown credit account drained then abandoned", 0.90),
    ("promo_abuse", "Coordinated abuse of signup / referral promotions", 0.55),
    ("deepfake_onboarding", "AI-generated identity used at KYC step", 1.15),
]

RISK_DECISIONS = [
    ("APPROVE", "Allow the transaction to proceed"),
    ("REVIEW", "Hold the transaction for analyst review"),
    ("DECLINE", "Block the transaction outright"),
    ("STEP_UP", "Require additional authentication before proceeding"),
]

ALERT_STATUSES = [
    ("OPEN", "Newly raised, not yet triaged"),
    ("IN_REVIEW", "Currently assigned to an analyst"),
    ("ESCALATED", "Promoted to a formal investigation case"),
    ("CLOSED_FALSE_POSITIVE", "Closed: legitimate activity"),
    ("CLOSED_CONFIRMED_FRAUD", "Closed: fraud confirmed"),
]

CASE_STATUSES = [
    ("OPEN", "Newly opened case"),
    ("INVESTIGATING", "Analyst gathering evidence"),
    ("PENDING_SAR", "Decision made to file SAR, drafting underway"),
    ("SAR_FILED", "SAR filed with FinCEN"),
    ("CLOSED_NO_ACTION", "Investigation closed without filing"),
]

CLIENT_INSTITUTIONS = [
    ("Pioneer Federal Credit Union", "credit_union", "USA", "Virginia", 320000.0),
    ("Crescent Community Bank", "commercial_bank", "USA", "Texas", 410000.0),
    ("Northwind Pay", "digital_fintech", "USA", "California", 880000.0),
    ("Skyline National Bank", "commercial_bank", "USA", "New York", 1200000.0),
    ("Halcyon Trust", "commercial_bank", "USA", "Illinois", 540000.0),
    ("BluePeak Credit Union", "credit_union", "USA", "Washington", 280000.0),
    ("OneTap BNPL", "bnpl_lender", "USA", "California", 760000.0),
    ("EquatorPay", "payment_processor", "Singapore", "Central", 950000.0),
    ("Aurora Digital Bank", "digital_fintech", "USA", "Massachusetts", 690000.0),
    ("Meridian Card Services", "payment_processor", "USA", "Georgia", 1050000.0),
    ("Trailhead Mutual", "credit_union", "USA", "Colorado", 240000.0),
    ("RiverGate Bank", "commercial_bank", "Canada", "Ontario", 470000.0),
]

WATCHLIST_SOURCES = ["OFAC_SDN", "EU_SANCTIONS", "UK_HMT", "INTERNAL_PEP", "INTERPOL"]
RISK_TIERS = ["HIGH", "MEDIUM", "LOW"]

ML_FAMILIES = ["unsupervised_clustering", "supervised_gbdt", "graph_anomaly", "deep_sequence"]
RULE_TEMPLATES = [
    ("HIGH_AMOUNT_INTL_WIRE", "Wire > $10K to high-risk corridor", 750),
    ("VELOCITY_5_IN_1H", "More than 5 transactions in 1 hour from same device", 680),
    ("NEW_DEVICE_LARGE_TRANSFER", "First-seen device initiating > $5K transfer", 720),
    ("VPN_PLUS_GEO_MISMATCH", "Session uses VPN and geo differs from account state", 640),
    ("STRUCTURING_PATTERN", "10+ deposits just under $10K reporting threshold", 820),
    ("KNOWN_MULE_DEVICE", "Device fingerprint flagged in Data Consortium", 880),
    ("DORMANT_ACCOUNT_REACTIVATION", "Inactive 180d, then large outflow", 700),
    ("CARD_TESTING_BURST", "20+ low-value card auths within 10 min", 760),
    ("CROSS_BORDER_ROUND_AMOUNT", "Even-round amount to high-risk country", 660),
    ("PEP_RELATED_TRANSFER", "Counterparty matches PEP watchlist", 850),
]

CHANNELS = ["mobile_app", "web", "branch", "api", "atm"]
TRANSACTION_TYPES = ["wire", "ach_push", "ach_pull", "card_purchase", "p2p_transfer", "atm_withdrawal", "wallet_topup"]
CURRENCIES = ["USD", "EUR", "GBP", "AED", "RUB", "CNY", "CAD", "JPY"]
# USD 占主导, 因为 amount_usd 是归一化后的值 (NovaRisk 只存储 USD 等值金额)。
# 我们保留少量其它货币的长尾, 用于演示多货币处理。
CURRENCY_WEIGHTS = [0.85, 0.05, 0.03, 0.02, 0.01, 0.01, 0.02, 0.01]
HIGH_RISK_COUNTRIES = ["Iran", "North Korea", "Syria", "Belarus", "Russia", "Myanmar"]
NORMAL_COUNTRIES = ["USA", "Canada", "United Kingdom", "Germany", "Australia", "Japan", "France", "Spain"]
# 贴近现实的国家权重 —— 95% 为正常国家, 5% 为高风险通道 (corridor) 合计。
# 在正常国家中: USA 占主导, 因为大多数客户都位于美国。
NORMAL_COUNTRY_WEIGHTS = [0.40, 0.10, 0.13, 0.08, 0.08, 0.06, 0.05, 0.05]   # 合计为 0.95
HIGH_RISK_COUNTRY_WEIGHTS = [0.005, 0.003, 0.005, 0.012, 0.020, 0.005]      # 合计为 0.05

DEVICE_TYPES = ["mobile", "desktop", "tablet"]
OS_FAMILIES = {"mobile": ["iOS", "Android"], "desktop": ["Windows", "macOS", "Linux"], "tablet": ["iPadOS", "Android"]}
BROWSER_FAMILIES = ["Chrome", "Safari", "Firefox", "Edge", "Mobile App"]

VERA_AGENTS = ["Detection", "Optimization", "Investigation", "Reporting"]
TOOLS_PER_AGENT = {
    "Detection": ["query_transactions_by_pattern", "compute_velocity_features", "rule_simulate"],
    "Optimization": ["score_threshold_simulate", "false_positive_review", "rule_ab_test"],
    "Investigation": ["fetch_case_context", "graph_link_explore", "device_history_query", "summarize_alerts"],
    "Reporting": ["draft_sar_narrative", "compose_regulator_pdf", "extract_counterparty_facts"],
}

SAR_NARRATIVE_TEMPLATES = [
    "Subject made {n} cash-equivalent deposits totaling ${amt:,.0f} into account {acct} between {d1} and {d2}, "
    "each below the $10K reporting threshold, consistent with structuring activity.",
    "Subject initiated {n} wire transfers totaling ${amt:,.0f} from account {acct} to counterparties located in "
    "high-risk jurisdictions including {ctry}, with no apparent economic purpose.",
    "Account {acct} received {n} inbound transfers totaling ${amt:,.0f} from unrelated third parties and then "
    "immediately disbursed funds to external wallets, consistent with mule activity.",
    "Subject's device fingerprint was previously associated with confirmed fraud at another institution via the "
    "Data Consortium. {n} subsequent transactions totaling ${amt:,.0f} from account {acct} were blocked or reversed.",
]

VERA_QUERY_TEMPLATES = [
    "Show me all transactions from device {dev} in the last 24 hours over $1000",
    "What are the top 5 false positives from rule {rule} this week?",
    "Summarize case {case} for me — who is the subject, what is the exposure?",
    "Find accounts that share a device fingerprint with case {case} subject",
    "Draft a SAR narrative for case {case} including the structuring pattern",
    "Simulate raising rule {rule} threshold from 680 to 720, what is the FP drop?",
    "Which counterparty countries had the highest decline rate yesterday?",
    "Pull the 30-day transaction history for the source account of alert {alert}",
    "Generate the customer due diligence summary for end user {user}",
    "Show me the alert volume trend for fraud type {ft} over the last week",
]


# ============================================================================
# 辅助函数
# ============================================================================
def _between(start: datetime, end: datetime) -> datetime:
    """在 start 和 end 之间均匀取一个随机 datetime。"""
    if end <= start:
        return start
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def _hash_email() -> str:
    return hashlib.sha256(fake.unique.email().encode()).hexdigest()[:32]


def _device_fingerprint() -> str:
    raw = f"{random.random()}{fake.user_agent()}{fake.ipv4()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


# ============================================================================
# 数据生成器
# ============================================================================
def gen_industry_vertical() -> pl.DataFrame:
    return pl.DataFrame(
        [{"id": i + 1, "code": code, "description": desc} for i, (code, desc) in enumerate(INDUSTRY_VERTICALS)]
    )


def gen_fraud_type_dim() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"id": i + 1, "code": code, "description": desc, "severity_weight": w}
            for i, (code, desc, w) in enumerate(FRAUD_TYPES)
        ]
    )


def gen_risk_decision_dim() -> pl.DataFrame:
    return pl.DataFrame(
        [{"id": i + 1, "code": code, "description": desc} for i, (code, desc) in enumerate(RISK_DECISIONS)]
    )


def gen_alert_status_dim() -> pl.DataFrame:
    return pl.DataFrame(
        [{"id": i + 1, "code": code, "description": desc} for i, (code, desc) in enumerate(ALERT_STATUSES)]
    )


def gen_case_status_dim() -> pl.DataFrame:
    return pl.DataFrame(
        [{"id": i + 1, "code": code, "description": desc} for i, (code, desc) in enumerate(CASE_STATUSES)]
    )


def gen_client_institution(vertical_lookup: dict[str, int]) -> pl.DataFrame:
    records = []
    for i, (name, vert_code, country, state, acv) in enumerate(CLIENT_INSTITUTIONS, start=1):
        start = fake.date_time_between(start_date="-3y", end_date="-9M")
        records.append(
            {
                "id": i,
                "legal_name": name,
                "industry_vertical_id": vertical_lookup[vert_code],
                "headquarters_country": country,
                "headquarters_state": state,
                "contract_start_date": start,
                "annual_contract_value_usd": acv,
                "is_active": True,
            }
        )
    return pl.DataFrame(records)


def gen_sanctions_watchlist(n: int = 50) -> pl.DataFrame:
    records = []
    for i in range(1, n + 1):
        listed_country = random.choice(HIGH_RISK_COUNTRIES + NORMAL_COUNTRIES)
        records.append(
            {
                "id": i,
                "list_source": random.choice(WATCHLIST_SOURCES),
                "listed_name": fake.name() if random.random() < 0.7 else fake.company(),
                "listed_country": listed_country,
                "risk_tier": random.choices(RISK_TIERS, weights=[0.5, 0.3, 0.2])[0],
                "added_on": fake.date_time_between(start_date="-5y", end_date="-30d"),
            }
        )
    return pl.DataFrame(records)


def gen_device(n: int = 400) -> pl.DataFrame:
    records = []
    for i in range(1, n + 1):
        dtype = random.choices(DEVICE_TYPES, weights=[0.6, 0.35, 0.05])[0]
        os = random.choice(OS_FAMILIES[dtype])
        records.append(
            {
                "id": i,
                "fingerprint_hash": _device_fingerprint(),
                "device_type": dtype,
                "os_family": os,
                "browser_family": random.choice(BROWSER_FAMILIES),
                "first_seen_at": fake.date_time_between(start_date="-18M", end_date="-1d"),
                "is_emulator": random.random() < 0.04,
            }
        )
    return pl.DataFrame(records)


def gen_ml_model(client_ids: list[int]) -> pl.DataFrame:
    """每个客户两个模型: 一个 champion, 一个 challenger。"""
    records = []
    model_id = 1
    for cid in client_ids:
        for slot in range(2):
            family = random.choice(ML_FAMILIES)
            version = f"{random.randint(1, 4)}.{random.randint(0, 9)}.{random.randint(0, 20)}"
            records.append(
                {
                    "id": model_id,
                    "client_institution_id": cid,
                    "model_name": f"{family}_v{version}",
                    "model_family": family,
                    "version": version,
                    "deployed_at": fake.date_time_between(start_date="-12M", end_date="-7d"),
                    "is_champion": slot == 0,
                }
            )
            model_id += 1
    return pl.DataFrame(records)


def gen_detection_rule(client_ids: list[int]) -> pl.DataFrame:
    """每个客户五条规则, 从规则模板中挑选。"""
    records = []
    rule_id = 1
    for cid in client_ids:
        chosen = random.sample(RULE_TEMPLATES, k=5)
        for code, desc, thresh in chosen:
            records.append(
                {
                    "id": rule_id,
                    "client_institution_id": cid,
                    "rule_code": code,
                    "rule_description": desc,
                    "threshold_score": thresh + random.randint(-20, 20),
                    "is_enabled": random.random() < 0.92,
                }
            )
            rule_id += 1
    return pl.DataFrame(records)


def gen_analyst(client_ids: list[int]) -> pl.DataFrame:
    """每个客户大约 3-4 名分析师。"""
    records = []
    aid = 1
    for cid in client_ids:
        for _ in range(random.randint(3, 4)):
            records.append(
                {
                    "id": aid,
                    "client_institution_id": cid,
                    "full_name": fake.name(),
                    "email": fake.unique.email(),
                    "seniority": random.choices(["junior", "senior", "lead"], weights=[0.45, 0.4, 0.15])[0],
                    "hired_on": fake.date_time_between(start_date="-5y", end_date="-30d"),
                }
            )
            aid += 1
    fake.unique.clear()
    return pl.DataFrame(records)


def gen_end_user(client_ids: list[int], n: int = 600) -> pl.DataFrame:
    records = []
    all_countries = NORMAL_COUNTRIES + HIGH_RISK_COUNTRIES
    all_country_weights = NORMAL_COUNTRY_WEIGHTS + HIGH_RISK_COUNTRY_WEIGHTS
    for i in range(1, n + 1):
        cid = random.choice(client_ids)
        country = random.choices(all_countries, weights=all_country_weights)[0]
        risk_rating = random.choices(["LOW", "MEDIUM", "HIGH"], weights=[0.7, 0.22, 0.08])[0]
        records.append(
            {
                "id": i,
                "client_institution_id": cid,
                "full_name": fake.name(),
                "email_hash": _hash_email(),
                "country": country,
                "state": fake.state() if country == "USA" else None,
                "onboarded_at": fake.date_time_between(start_date="-2y", end_date="-7d"),
                "kyc_status": random.choices(["VERIFIED", "PENDING", "REJECTED"], weights=[0.88, 0.08, 0.04])[0],
                "customer_risk_rating": risk_rating,
                "is_pep_match": random.random() < 0.02,
            }
        )
    fake.unique.clear()
    return pl.DataFrame(records)


def gen_account(end_users: pl.DataFrame, n: int = 800) -> pl.DataFrame:
    records = []
    user_rows = end_users.to_dicts()
    for i in range(1, n + 1):
        u = random.choice(user_rows)
        opened = _between(u["onboarded_at"], NOW - timedelta(days=1))
        atype = random.choices(
            ["checking", "savings", "credit_card", "debit_card", "wallet"],
            weights=[0.35, 0.20, 0.20, 0.15, 0.10],
        )[0]
        limit = {
            "checking": 25000,
            "savings": 50000,
            "credit_card": 15000,
            "debit_card": 5000,
            "wallet": 3000,
        }[atype]
        records.append(
            {
                "id": i,
                "end_user_id": u["id"],
                "client_institution_id": u["client_institution_id"],
                "account_number_masked": f"****{random.randint(1000, 9999)}",
                "account_type": atype,
                "opened_at": opened,
                "is_closed": random.random() < 0.05,
                "daily_limit_usd": float(limit),
            }
        )
    return pl.DataFrame(records)


def gen_device_session(
    devices: pl.DataFrame,
    end_users: pl.DataFrame,
    accounts: pl.DataFrame,
    n: int = 600,
) -> pl.DataFrame:
    """会话把设备和用户关联起来。约 8% 的设备被刻意在多个用户间共享
    (这是检测协同攻击团伙 (ring) 的基础)。"""
    records = []
    device_rows = devices.to_dicts()
    user_rows = end_users.to_dicts()
    shared_devices = random.sample(device_rows, k=max(1, int(len(device_rows) * 0.08)))
    # 预先计算每个用户最早的 account.opened_at —— 会话必须发生在用户至少拥有
    # 一个账户之后, 否则源自该会话的交易就没有可作为来源的账户。
    user_first_account_open: dict[int, datetime] = {}
    for a in accounts.to_dicts():
        prev = user_first_account_open.get(a["end_user_id"])
        if prev is None or a["opened_at"] < prev:
            user_first_account_open[a["end_user_id"]] = a["opened_at"]
    all_countries = NORMAL_COUNTRIES + HIGH_RISK_COUNTRIES
    all_country_weights = NORMAL_COUNTRY_WEIGHTS + HIGH_RISK_COUNTRY_WEIGHTS
    for i in range(1, n + 1):
        # 修复: 使用 random.choice(shared_devices) 而非 next(...) —— 旧的 next() 在每个
        # 共享设备槽位上总是返回同一个"巨型"设备。
        if random.random() < 0.15:
            dev = random.choice(shared_devices)
        else:
            dev = random.choice(device_rows)
        user = random.choice(user_rows)
        first_account = user_first_account_open.get(user["id"])
        # 下界: 设备首次出现、用户开户, 且用户至少有一个账户已开立。
        floors = [dev["first_seen_at"], user["onboarded_at"]]
        if first_account is not None:
            floors.append(first_account)
        start_floor = max(floors)
        # 对称的上界: 如果起始下界已经太接近 NOW, 则跳过。
        # 否则 `_between(..., NOW - 1h)` 会塌缩成 start = start_floor, 而
        # `end = start + 最多 90 分钟` 可能会越过 NOW。
        upper = NOW - timedelta(hours=1)
        if start_floor >= upper:
            continue
        start = _between(max(start_floor, WINDOW_START - timedelta(days=10)), upper)
        end = start + timedelta(minutes=random.randint(2, 90))
        # 地理国家: 90% 与用户的归属国相同 (贴近现实的情况), 10% 为出行/VPN 漂移。
        if random.random() < 0.90:
            country = user["country"]
        else:
            country = random.choices(all_countries, weights=all_country_weights)[0]
        records.append(
            {
                "id": i,
                "device_id": dev["id"],
                "end_user_id": user["id"],
                "session_started_at": start,
                "session_ended_at": end,
                "ip_address": fake.ipv4_public(),
                "geo_country": country,
                "geo_city": fake.city(),
                "is_vpn": random.random() < 0.18,
            }
        )
    return pl.DataFrame(records)


def _pick_channel_for_type(ttype: str) -> str:
    """channel ↔ transaction_type 的一致性: ATM 取款只在 ATM 渠道发生,
    wire/wallet_topup 不在 ATM 发生, branch 只用于高信任类型, 等等。"""
    if ttype == "atm_withdrawal":
        return "atm"
    if ttype == "wire":
        return random.choices(["branch", "web", "mobile_app", "api"], weights=[0.30, 0.30, 0.25, 0.15])[0]
    if ttype == "wallet_topup":
        return random.choices(["mobile_app", "web"], weights=[0.70, 0.30])[0]
    if ttype == "card_purchase":
        return random.choices(["api", "web", "mobile_app"], weights=[0.55, 0.25, 0.20])[0]
    if ttype.startswith("ach"):
        return random.choices(["web", "api", "mobile_app", "branch"], weights=[0.35, 0.25, 0.30, 0.10])[0]
    if ttype == "p2p_transfer":
        return random.choices(["mobile_app", "web"], weights=[0.80, 0.20])[0]
    return random.choice(CHANNELS)


def gen_transaction(accounts: pl.DataFrame, sessions: pl.DataFrame, n: int = 800) -> pl.DataFrame:
    """每笔交易都有一个源账户; 约 70% 还有一个目标账户。
    交易必须发生在其会话窗口之内。
    注意: destination_account_id 允许属于与源账户不同的 client_institution
    —— 这是为了模拟真实的跨行 wire / ACH 转账。"""
    records = []
    account_rows = accounts.to_dicts()
    session_rows = sessions.to_dicts()
    # 建立 user -> accounts 的映射, 以便把会话所属用户关联到其账户
    user_to_accounts: dict[int, list[dict]] = {}
    for a in account_rows:
        user_to_accounts.setdefault(a["end_user_id"], []).append(a)
    all_countries = NORMAL_COUNTRIES + HIGH_RISK_COUNTRIES
    all_country_weights = NORMAL_COUNTRY_WEIGHTS + HIGH_RISK_COUNTRY_WEIGHTS
    txid = 1
    attempts = 0
    while txid <= n and attempts < n * 4:
        attempts += 1
        sess = random.choice(session_rows)
        user_accounts = user_to_accounts.get(sess["end_user_id"], [])
        if not user_accounts:
            continue
        src = random.choice(user_accounts)
        if src["is_closed"]:
            continue
        dst = None
        if random.random() < 0.70:
            dst_candidate = random.choice(account_rows)
            if dst_candidate["id"] != src["id"]:
                dst = dst_candidate
        ttype = random.choice(TRANSACTION_TYPES)
        channel = _pick_channel_for_type(ttype)
        amount = round(
            random.choices(
                [random.uniform(5, 200), random.uniform(200, 2000), random.uniform(2000, 15000)],
                weights=[0.45, 0.40, 0.15],
            )[0],
            2,
        )
        cp_country = random.choices(all_countries, weights=all_country_weights)[0]
        is_high_risk = cp_country in HIGH_RISK_COUNTRIES
        initiated = _between(sess["session_started_at"], sess["session_ended_at"])
        settled = initiated + timedelta(minutes=random.randint(0, 60)) if random.random() < 0.85 else None
        records.append(
            {
                "id": txid,
                "source_account_id": src["id"],
                "destination_account_id": dst["id"] if dst else None,
                "device_session_id": sess["id"],
                "transaction_type": ttype,
                "channel": channel,
                "amount_usd": amount,
                "currency": random.choices(CURRENCIES, weights=CURRENCY_WEIGHTS)[0],
                "counterparty_country": cp_country,
                "initiated_at": initiated,
                "settled_at": settled,
                "is_high_risk_corridor": is_high_risk,
            }
        )
        txid += 1
    return pl.DataFrame(records)


def _decide(score: int) -> str:
    if score >= 800:
        return "DECLINE"
    if score >= 600:
        return "REVIEW"
    if score >= 400:
        return "STEP_UP"
    return "APPROVE"


def gen_risk_score_event(
    transactions: pl.DataFrame,
    models: pl.DataFrame,
    accounts: pl.DataFrame,
    decision_lookup: dict[str, int],
) -> pl.DataFrame:
    """每笔交易产生一个评分事件。所使用的模型必须与该交易源账户属于同一个
    client_institution (现实中路由是按租户 (per-tenant) 进行的)。
    约 15% 的事件由客户的 CHALLENGER 模型而非 champion 评分 (A/B 测试)。"""
    records = []
    # 建立 client -> champion 与 challenger 的映射
    champion_by_client: dict[int, dict] = {}
    challenger_by_client: dict[int, dict] = {}
    for m in models.to_dicts():
        if m["is_champion"]:
            champion_by_client[m["client_institution_id"]] = m
        else:
            challenger_by_client[m["client_institution_id"]] = m
    # account_id -> client_institution_id 的映射, 便于快速查找
    acct_to_client = {a["id"]: a["client_institution_id"] for a in accounts.to_dicts()}
    feature_names = [
        "device_velocity_1h",
        "amount_zscore_30d",
        "geo_mismatch_flag",
        "graph_cluster_density",
        "session_age_seconds",
        "counterparty_risk_score",
        "structuring_likelihood",
        "behavioral_drift_score",
    ]
    for i, tx in enumerate(transactions.to_dicts(), start=1):
        # 基础分, 整体偏向低分
        base = random.choices([random.randint(50, 350), random.randint(350, 650), random.randint(650, 999)],
                              weights=[0.65, 0.25, 0.10])[0]
        # 对高风险通道 / 大额交易加分
        if tx["is_high_risk_corridor"]:
            base = min(999, base + random.randint(80, 180))
        if tx["amount_usd"] > 10000:
            base = min(999, base + random.randint(40, 120))
        decision = _decide(base)
        # 为该交易所属的客户挑选模型。85% 的情况用 champion,
        # 15% 用 challenger (A/B 流量分配)。
        client_id = acct_to_client[tx["source_account_id"]]
        if random.random() < 0.15 and client_id in challenger_by_client:
            model = challenger_by_client[client_id]
        else:
            model = champion_by_client[client_id]
        scored = tx["initiated_at"] + timedelta(milliseconds=random.randint(10, 200))
        records.append(
            {
                "id": i,
                "transaction_id": tx["id"],
                "ml_model_id": model["id"],
                "decision_id": decision_lookup[decision],
                "risk_score": base,
                "scored_at": scored,
                "latency_ms": random.randint(15, 180),
                "top_feature": random.choice(feature_names),
            }
        )
    return pl.DataFrame(records)


def gen_alert(
    score_events: pl.DataFrame,
    transactions: pl.DataFrame,
    rules: pl.DataFrame,
    accounts: pl.DataFrame,
    watchlist: pl.DataFrame,
    fraud_lookup: dict[str, int],
    status_lookup: dict[str, int],
    max_alerts: int | None = None,
) -> pl.DataFrame:
    """告警产生于 risk_score_event 中评分 >= 600 的事件。此处 case_id 为空; 由调查步骤负责挂接。
    is_true_positive ↔ status 的不变式:
      CLOSED_FALSE_POSITIVE → False
      CLOSED_CONFIRMED_FRAUD → True
      OPEN / IN_REVIEW / ESCALATED → NULL (尚未裁定)
    一小部分告警 (那些经过 AML 制裁名单筛查并命中的)
    会带有 watchlist_match_id。

    `max_alerts` 是一个可选的硬上限, 用于测试; 默认 None 表示每一个
    risk_score >= 600 的 score_event 都会产生一个告警。之前默认值 200 存在风险:
    一旦调用方放大了交易量, 就会悄无声息地少产出告警。"""
    high = [se for se in score_events.to_dicts() if se["risk_score"] >= 600]
    if max_alerts is not None and len(high) > max_alerts:
        high = random.sample(high, k=max_alerts)
    tx_by_id = {t["id"]: t for t in transactions.to_dicts()}
    acct_by_id = {a["id"]: a for a in accounts.to_dicts()}
    rules_by_client: dict[int, list[dict]] = {}
    for r in rules.to_dicts():
        rules_by_client.setdefault(r["client_institution_id"], []).append(r)
    watchlist_ids = watchlist["id"].to_list()

    records = []
    for i, se in enumerate(high, start=1):
        tx = tx_by_id[se["transaction_id"]]
        src = acct_by_id[tx["source_account_id"]]
        client_id = src["client_institution_id"]
        candidate_rules = rules_by_client.get(client_id, [])
        rule_id = None
        if candidate_rules and random.random() < 0.8:
            applicable = [r for r in candidate_rules if r["is_enabled"] and r["threshold_score"] <= se["risk_score"]]
            if applicable:
                rule_id = random.choice(applicable)["id"]
        # 按交易类型加权的欺诈类型
        if tx["transaction_type"] == "wire":
            ft_code = random.choices(["wire_fraud", "mule_account", "ach_fraud"], weights=[0.5, 0.3, 0.2])[0]
        elif tx["transaction_type"].startswith("ach"):
            ft_code = random.choices(["ach_fraud", "mule_account", "account_takeover"], weights=[0.5, 0.3, 0.2])[0]
        elif tx["transaction_type"] == "card_purchase":
            ft_code = random.choices(["card_not_present", "bust_out", "account_takeover"], weights=[0.6, 0.2, 0.2])[0]
        else:
            ft_code = random.choice(["account_takeover", "promo_abuse", "new_account_fraud", "deepfake_onboarding"])
        # 状态分布 (10/15/25/30/20)
        status_code = random.choices(
            ["OPEN", "IN_REVIEW", "ESCALATED", "CLOSED_FALSE_POSITIVE", "CLOSED_CONFIRMED_FRAUD"],
            weights=[0.10, 0.15, 0.25, 0.30, 0.20],
        )[0]
        # is_true_positive ↔ status 不变式
        if status_code == "CLOSED_FALSE_POSITIVE":
            tp = False
        elif status_code == "CLOSED_CONFIRMED_FRAUD":
            tp = True
        else:
            tp = None
        # watchlist 筛查: 每个告警都会被筛查。整体命中概率较小, 但对
        # 高风险通道 / wire 交易明显更高 (AML 模式)。
        is_corridor = bool(tx["is_high_risk_corridor"])
        hit_prob = 0.18 if (is_corridor or tx["transaction_type"] == "wire") else 0.04
        watch_match = random.choice(watchlist_ids) if (watchlist_ids and random.random() < hit_prob) else None
        raised = se["scored_at"] + timedelta(seconds=random.randint(1, 60))
        records.append(
            {
                "id": i,
                "transaction_id": tx["id"],
                "detection_rule_id": rule_id,
                "fraud_type_id": fraud_lookup[ft_code],
                "status_id": status_lookup[status_code],
                "case_id": None,
                "watchlist_match_id": watch_match,
                "raised_at": raised,
                "is_true_positive": tp,
            }
        )
    return pl.DataFrame(records)


def gen_investigation_case(
    alerts: pl.DataFrame,
    transactions: pl.DataFrame,
    accounts: pl.DataFrame,
    analysts: pl.DataFrame,
    alert_status_lookup: dict[str, int],
    case_status_lookup: dict[str, int],
    n: int = 80,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """将告警汇总成案件。只有状态为 ESCALATED 或 CLOSED_CONFIRMED_FRAUD 的告警
    才符合条件 (OPEN/IN_REVIEW 仍在分流处理; CLOSED_FALSE_POSITIVE 已被否决)。
    每个案件汇总 1-4 个符合条件且全部属于同一个 client_institution 的告警,
    指派的分析师从该客户的分析师池中抽取。
    case.opened_at >= MAX(所汇总告警的 raised_at) —— 分析师只能汇总
    那些已经产生的告警。"""
    tx_by_id = {t["id"]: t for t in transactions.to_dicts()}
    acct_by_id = {a["id"]: a for a in accounts.to_dicts()}
    analyst_by_client: dict[int, list[dict]] = {}
    for a in analysts.to_dicts():
        analyst_by_client.setdefault(a["client_institution_id"], []).append(a)

    escalated_id = alert_status_lookup["ESCALATED"]
    confirmed_id = alert_status_lookup["CLOSED_CONFIRMED_FRAUD"]
    alert_rows = alerts.to_dicts()
    eligible = [a for a in alert_rows if a["status_id"] in (escalated_id, confirmed_id)]
    # 按所属 client_institution (由源账户推导) 对符合条件的告警分组
    grouped: dict[int, list[dict]] = {}
    for a in eligible:
        tx = tx_by_id[a["transaction_id"]]
        src = acct_by_id[tx["source_account_id"]]
        cid = src["client_institution_id"]
        grouped.setdefault(cid, []).append(a)

    cases = []
    alert_updates: dict[int, int] = {}  # alert_id -> case_id 的映射
    case_id = 1
    client_ids = [c for c in grouped if analyst_by_client.get(c)]
    random.shuffle(client_ids)
    while case_id <= n:
        if not client_ids:
            break
        cid = random.choice(client_ids)
        bucket = grouped[cid]
        if not bucket:
            client_ids.remove(cid)
            continue
        k = min(len(bucket), random.randint(1, 4))
        chosen = random.sample(bucket, k=k)
        for a in chosen:
            bucket.remove(a)
        if not bucket:
            client_ids.remove(cid)
        assignee = random.choice(analyst_by_client[cid])
        # case.opened_at 必须在最后一个告警产生之后 —— 分析师只能
        # 汇总已经存在的告警。
        latest_alert_time = max(a["raised_at"] for a in chosen)
        opened = latest_alert_time + timedelta(minutes=random.randint(5, 240))
        status_code = random.choices(
            ["OPEN", "INVESTIGATING", "PENDING_SAR", "SAR_FILED", "CLOSED_NO_ACTION"],
            weights=[0.10, 0.30, 0.15, 0.30, 0.15],
        )[0]
        closed = None
        if status_code in ("SAR_FILED", "CLOSED_NO_ACTION"):
            closed = opened + timedelta(days=random.randint(2, 21))
        # 双向噪声: 约为所汇总交易金额之和的 ±5%。
        bundled_sum = sum(tx_by_id[a["transaction_id"]]["amount_usd"] for a in chosen)
        total_exposure = round(bundled_sum + random.uniform(-0.05, 0.05) * bundled_sum, 2)
        cases.append(
            {
                "id": case_id,
                "client_institution_id": cid,
                "assigned_analyst_id": assignee["id"],
                "case_status_id": case_status_lookup[status_code],
                "opened_at": opened,
                "closed_at": closed,
                "total_exposure_usd": total_exposure,
                "priority": random.choices(["LOW", "MEDIUM", "HIGH", "CRITICAL"], weights=[0.2, 0.4, 0.3, 0.1])[0],
            }
        )
        for a in chosen:
            alert_updates[a["id"]] = case_id
        case_id += 1

    # 把 case_id 回填到告警上 (仅针对那些实际被汇总的告警)
    updated = []
    for a in alert_rows:
        a2 = dict(a)
        if a["id"] in alert_updates:
            a2["case_id"] = alert_updates[a["id"]]
        updated.append(a2)
    return pl.DataFrame(cases), pl.DataFrame(updated)


def gen_sar_report(
    cases: pl.DataFrame,
    transactions: pl.DataFrame,
    accounts: pl.DataFrame,
    alerts: pl.DataFrame,
    watchlist: pl.DataFrame,
    case_status_lookup_inv: dict[int, str],
) -> pl.DataFrame:
    """每个处于 SAR_FILED 状态的案件对应一份 SAR。
    时间不变式: case.opened_at < sar.filed_at < case.closed_at
    (先提交 SAR, 几天后再对案件做行政性关闭)。
    如果某个被汇总的告警已带有 watchlist_match_id, SAR 会继承它 (上游信号保持一致);
    否则, 对于带 AML 性质的案件, 我们有时会分配一个。"""
    tx_by_id = {t["id"]: t for t in transactions.to_dicts()}
    acct_by_id = {a["id"]: a for a in accounts.to_dicts()}
    alerts_by_case: dict[int, list[dict]] = {}
    for a in alerts.to_dicts():
        if a["case_id"]:
            alerts_by_case.setdefault(a["case_id"], []).append(a)
    watchlist_ids = watchlist["id"].to_list()
    records = []
    sid = 1
    for c in cases.to_dicts():
        status_code = case_status_lookup_inv[c["case_status_id"]]
        if status_code != "SAR_FILED":
            continue
        case_alerts = alerts_by_case.get(c["id"], [])
        if not case_alerts:
            continue
        tx0 = tx_by_id[case_alerts[0]["transaction_id"]]
        acct = acct_by_id[tx0["source_account_id"]]
        narrative_tpl = random.choice(SAR_NARRATIVE_TEMPLATES)
        n_alerts = len(case_alerts)
        narrative = narrative_tpl.format(
            n=n_alerts,
            amt=c["total_exposure_usd"],
            acct=acct["account_number_masked"],
            d1=c["opened_at"].strftime("%Y-%m-%d"),
            d2=(c["closed_at"] or c["opened_at"]).strftime("%Y-%m-%d"),
            ctry=tx0["counterparty_country"],
        )
        # 优先继承已有的告警级 watchlist 命中, 以保持血缘一致。
        # 随机兜底比例保持较低 (10%), 这样 SAR 级别的总命中率会维持在 30-40% 左右,
        # 而不会因为"继承 + 随机"两条路径叠加而被抬高。
        upstream_hits = [a["watchlist_match_id"] for a in case_alerts if a.get("watchlist_match_id")]
        if upstream_hits:
            watch_match = random.choice(upstream_hits)
        elif watchlist_ids and random.random() < 0.10:
            watch_match = random.choice(watchlist_ids)
        else:
            watch_match = None
        # filed_at 严格落在 opened_at 与 closed_at 之间。SAR_FILED 案件的 closed_at
        # 总是已被填充 (见 gen_investigation_case), 因此无需兜底分支。
        span_days = max(1, (c["closed_at"] - c["opened_at"]).days)
        # 在案件窗口的前 80% 内提交, 末尾留给行政性关闭。
        file_offset_days = random.randint(1, max(1, int(span_days * 0.8)))
        filed_at = c["opened_at"] + timedelta(days=file_offset_days)
        records.append(
            {
                "id": sid,
                "case_id": c["id"],
                "watchlist_match_id": watch_match,
                "filing_reference": f"FINCEN-{filed_at.strftime('%Y%m%d')}-{sid:05d}",
                "filed_at": filed_at,
                "narrative_summary": narrative,
                "total_reported_amount_usd": c["total_exposure_usd"],
                "ai_drafted": random.random() < 0.80,
            }
        )
        sid += 1
    return pl.DataFrame(records)


def gen_agent_interaction_log(
    cases: pl.DataFrame,
    analysts: pl.DataFrame,
    alerts: pl.DataFrame,
    devices: pl.DataFrame,
    rules: pl.DataFrame,
    end_users: pl.DataFrame,
    fraud_types: pl.DataFrame,
    n: int = 120,
) -> pl.DataFrame:
    """Vera agent 日志。不变式: 只要设置了 case_id, 就有
    analyst.client_institution_id == case.client_institution_id。当 case_id 为空时,
    分析师仍从单一客户的池中抽取 (现实中一名分析师恰好只隶属于一家银行)。

    各 agent 的 token / 延迟分布反映了真实的 LLM 成本形态:
      Reporting   —— 最大 (起草冗长的 SAR narrative)
      Investigation —— 中偏大 (多跳图谱 + RAG)
      Optimization  —— 中等 (规则模拟)
      Detection     —— 最小 (简短的模式查询)
    """
    case_rows = cases.to_dicts()
    analyst_by_client: dict[int, list[dict]] = {}
    for a in analysts.to_dicts():
        analyst_by_client.setdefault(a["client_institution_id"], []).append(a)
    analyst_rows = analysts.to_dicts()
    alert_ids = alerts["id"].to_list()
    device_hashes = devices["fingerprint_hash"].to_list()
    rule_codes = rules["rule_code"].to_list()
    user_ids = end_users["id"].to_list()
    fraud_codes = fraud_types["code"].to_list()

    # 每个 agent 的 tokens_used (min, max) 与 latency_ms (min, max)
    agent_cost_profile = {
        "Reporting":     ((3000, 12000), (3000, 12000)),
        "Investigation": ((1200, 5500),  (800, 6000)),
        "Optimization": ((800, 3500),   (600, 4500)),
        "Detection":    ((300, 2000),   (400, 3000)),
    }

    records = []
    for i in range(1, n + 1):
        case = random.choice(case_rows) if random.random() < 0.85 and case_rows else None
        if case:
            analyst = random.choice(analyst_by_client[case["client_institution_id"]])
            case_id = case["id"]
            occurred = case["opened_at"] + timedelta(minutes=random.randint(1, 60 * 24))
        else:
            # 未挂接案件。此处全局随机挑选没有问题, 因为每一行分析师记录本身就已经
            # 带有它自己的 client_institution_id —— 单一客户的归属关系已经
            # 内嵌在所选记录中, 不需要这里再加一层分支来强制保证。
            analyst = random.choice(analyst_rows)
            case_id = None
            occurred = fake.date_time_between(start_date=WINDOW_START, end_date=NOW)
        agent = random.choices(VERA_AGENTS, weights=[0.25, 0.20, 0.35, 0.20])[0]
        tool = random.choice(TOOLS_PER_AGENT[agent])
        tpl = random.choice(VERA_QUERY_TEMPLATES)
        query = tpl.format(
            dev=random.choice(device_hashes)[:12],
            rule=random.choice(rule_codes),
            case=case_id if case_id else random.randint(1, 80),
            alert=random.choice(alert_ids) if alert_ids else 1,
            user=random.choice(user_ids),
            ft=random.choice(fraud_codes),
        )
        (tok_lo, tok_hi), (lat_lo, lat_hi) = agent_cost_profile[agent]
        records.append(
            {
                "id": i,
                "analyst_id": analyst["id"],
                "case_id": case_id,
                "agent_name": agent,
                "user_query": query,
                "tool_called": tool,
                "tokens_used": random.randint(tok_lo, tok_hi),
                "latency_ms": random.randint(lat_lo, lat_hi),
                "human_approved": random.random() < 0.92,
                "occurred_at": occurred,
            }
        )
    return pl.DataFrame(records)


# ============================================================================
# 核心函数 (幂等)
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有 TSV 文件。幂等: 先删除已存在的文件。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    # Level 0: enum 表
    df_industry = gen_industry_vertical()
    df_industry.write_csv(DATA_DIR / "01_industry_vertical.tsv", separator="\t")
    df_fraud = gen_fraud_type_dim()
    df_fraud.write_csv(DATA_DIR / "02_fraud_type_dim.tsv", separator="\t")
    df_decision = gen_risk_decision_dim()
    df_decision.write_csv(DATA_DIR / "03_risk_decision_dim.tsv", separator="\t")
    df_alert_status = gen_alert_status_dim()
    df_alert_status.write_csv(DATA_DIR / "04_alert_status_dim.tsv", separator="\t")
    df_case_status = gen_case_status_dim()
    df_case_status.write_csv(DATA_DIR / "05_case_status_dim.tsv", separator="\t")

    # Level 1
    vert_lookup = {row["code"]: row["id"] for row in df_industry.to_dicts()}
    df_client = gen_client_institution(vert_lookup)
    df_client.write_csv(DATA_DIR / "06_client_institution.tsv", separator="\t")
    df_watchlist = gen_sanctions_watchlist(n=50)
    df_watchlist.write_csv(DATA_DIR / "07_sanctions_watchlist.tsv", separator="\t")
    df_device = gen_device(n=400)
    df_device.write_csv(DATA_DIR / "08_device.tsv", separator="\t")

    # Level 2
    client_ids = df_client["id"].to_list()
    df_model = gen_ml_model(client_ids)
    df_model.write_csv(DATA_DIR / "09_ml_model.tsv", separator="\t")
    df_rule = gen_detection_rule(client_ids)
    df_rule.write_csv(DATA_DIR / "10_detection_rule.tsv", separator="\t")
    df_analyst = gen_analyst(client_ids)
    df_analyst.write_csv(DATA_DIR / "11_analyst.tsv", separator="\t")
    df_user = gen_end_user(client_ids, n=600)
    df_user.write_csv(DATA_DIR / "12_end_user.tsv", separator="\t")

    # Level 3 —— 先生成 account, 这样 device_session 才能用 account.opened_at 作为下界
    df_account = gen_account(df_user, n=800)
    df_account.write_csv(DATA_DIR / "13_account.tsv", separator="\t")
    df_session = gen_device_session(df_device, df_user, df_account, n=600)
    df_session.write_csv(DATA_DIR / "14_device_session.tsv", separator="\t")

    # Level 4
    df_tx = gen_transaction(df_account, df_session, n=800)
    df_tx.write_csv(DATA_DIR / "15_transaction.tsv", separator="\t")

    # Level 5 —— 评分事件使用各客户专属的 champion (或 15% 概率用 challenger)
    decision_lookup = {row["code"]: row["id"] for row in df_decision.to_dicts()}
    df_score = gen_risk_score_event(df_tx, df_model, df_account, decision_lookup)
    df_score.write_csv(DATA_DIR / "16_risk_score_event.tsv", separator="\t")

    # Level 6
    fraud_lookup = {row["code"]: row["id"] for row in df_fraud.to_dicts()}
    alert_status_lookup = {row["code"]: row["id"] for row in df_alert_status.to_dicts()}
    df_alert = gen_alert(df_score, df_tx, df_rule, df_account, df_watchlist, fraud_lookup, alert_status_lookup)

    # Level 7 —— 调查案件 (同时也会更新 alerts.case_id)
    case_status_lookup = {row["code"]: row["id"] for row in df_case_status.to_dicts()}
    df_case, df_alert = gen_investigation_case(
        df_alert, df_tx, df_account, df_analyst, alert_status_lookup, case_status_lookup, n=80
    )
    df_alert.write_csv(DATA_DIR / "17_alert.tsv", separator="\t")
    df_case.write_csv(DATA_DIR / "18_investigation_case.tsv", separator="\t")

    # Level 8 —— sar + agent 日志
    case_status_lookup_inv = {v: k for k, v in case_status_lookup.items()}
    df_sar = gen_sar_report(df_case, df_tx, df_account, df_alert, df_watchlist, case_status_lookup_inv)
    df_sar.write_csv(DATA_DIR / "19_sar_report.tsv", separator="\t")
    df_agent = gen_agent_interaction_log(df_case, df_analyst, df_alert, df_device, df_rule, df_user, df_fraud, n=120)
    df_agent.write_csv(DATA_DIR / "20_agent_interaction_log.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")


# 加载器规格, 使加载顺序与上面的文件顺序保持一致。
LOAD_SPEC = [
    # (文件名, ORM 模型, datetime 列, boolean 列)
    # boolean 列清单会作为显式的 schema_overrides 传给 polars, 这样我们就不必
    # 依赖 infer_schema_length 去猜对 dtype —— 一旦数据集规模扩大到几千行以上,
    # 那种猜测就会变得不可靠。
    ("01_industry_vertical.tsv", IndustryVertical, [], []),
    ("02_fraud_type_dim.tsv", FraudTypeDim, [], []),
    ("03_risk_decision_dim.tsv", RiskDecisionDim, [], []),
    ("04_alert_status_dim.tsv", AlertStatusDim, [], []),
    ("05_case_status_dim.tsv", CaseStatusDim, [], []),
    ("06_client_institution.tsv", ClientInstitution, ["contract_start_date"], ["is_active"]),
    ("07_sanctions_watchlist.tsv", SanctionsWatchlist, ["added_on"], []),
    ("08_device.tsv", Device, ["first_seen_at"], ["is_emulator"]),
    ("09_ml_model.tsv", MlModel, ["deployed_at"], ["is_champion"]),
    ("10_detection_rule.tsv", DetectionRule, [], ["is_enabled"]),
    ("11_analyst.tsv", Analyst, ["hired_on"], []),
    ("12_end_user.tsv", EndUser, ["onboarded_at"], ["is_pep_match"]),
    ("13_account.tsv", Account, ["opened_at"], ["is_closed"]),
    ("14_device_session.tsv", DeviceSession, ["session_started_at", "session_ended_at"], ["is_vpn"]),
    ("15_transaction.tsv", Transaction, ["initiated_at", "settled_at"], ["is_high_risk_corridor"]),
    ("16_risk_score_event.tsv", RiskScoreEvent, ["scored_at"], []),
    ("17_alert.tsv", Alert, ["raised_at"], ["is_true_positive"]),
    ("18_investigation_case.tsv", InvestigationCase, ["opened_at", "closed_at"], []),
    ("19_sar_report.tsv", SarReport, ["filed_at"], ["ai_drafted"]),
    ("20_agent_interaction_log.tsv", AgentInteractionLog, ["occurred_at"], ["human_approved"]),
]


def _parse_datetime(s):
    if s is None or s == "" or (isinstance(s, float) and s != s):  # NaN (非数值)
        return None
    if isinstance(s, datetime):
        return s
    # Polars 以 ISO 格式写出 datetime
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            continue
    return None


def create_sqlite_database() -> None:
    """从 TSV 文件创建 SQLite 数据库。幂等。"""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        for filename, model, dt_cols, bool_cols in LOAD_SPEC:
            # 强制将 boolean 列设为 pl.Boolean, 这样放大行数时就不会破坏
            # polars 的类型推断 (这种情况罕见但有可能, 比如开头若干行全为 False 等)。
            schema_overrides = {col: pl.Boolean for col in bool_cols}
            df = pl.read_csv(
                DATA_DIR / filename,
                separator="\t",
                infer_schema_length=10000,
                schema_overrides=schema_overrides if schema_overrides else None,
            )
            for row in df.iter_rows(named=True):
                row_clean = {}
                for k, v in row.items():
                    if k in dt_cols:
                        row_clean[k] = _parse_datetime(v)
                    elif v == "" or v is None:
                        row_clean[k] = None
                    else:
                        row_clean[k] = v
                session.add(model(**row_clean))
            session.flush()
        session.commit()

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("Starting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("All done!")


if __name__ == "__main__":
    main()
