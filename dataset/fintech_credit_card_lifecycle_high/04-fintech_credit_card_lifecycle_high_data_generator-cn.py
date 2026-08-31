"""
金融科技 — 消费信用卡全生命周期 假数据生成器
复杂度: High

业务背景:
Keystone Card Company 是一家总部位于加州尔湾 (Irvine, CA) 的数据驱动型消费信用卡发行商.
它自己发卡, 自己承保, 自己扛坏账, 靠"利息 + interchange + 费用 - rewards - charge-off"赚钱.
本数据集模拟约 24 个月 (2024-07 至 2026-06) 一整条 card lifecycle 的数据轨迹:
营销 (campaign / prescreen) -> 申请 (application) -> 承保 (underwriting) ->
开卡 (account) -> 月度账单 (statement) -> 交易 (transaction) -> 奖励 (rewards) ->
提额 (credit_line_change) -> 逾期/核销 (charge_off) -> 流失 (attrition).

数据集刻意注入以下 8 个业务陷阱 (每个都对应 03 SQL 文档里的一组查询):

1. 承保模型误校准 (underwriting_score 的 ROC / 混淆矩阵):
   underwriting_score (0-999, 越高越安全) 整体上能预测 charge-off (AUC ~0.70),
   但在 credit_band = D (Subprime) 这个分段里, 分数与实际 charge-off 几乎无关 (AUC ~0.50).
   => DS 分段算 AUC 会发现 D 段模型失效.

2. 营销渠道逆向选择 (channel adverse selection):
   affiliate_partner 渠道批准率高, 触达成本 (2.00) 低于数字渠道 (3.2-4.5),
   但它带来的账户 charge-off 率约 12.6%, 是 prescreen_mail (~3.9%) 的约 3.2 倍,
   也高于组合整体 (~6.9%). "获客成本便宜 != 客户质量好".

3. 奖励卡 transactor 不赚钱 (transactor unprofitability):
   高端卡 (Travel / Venture Premium, rewards 2.0%-2.5%) 上的 transactor (每月全额还款)
   贡献 interchange (~1.8%) 却被 rewards 吃穿, 单账户净贡献为负; 靠 revolver 的利息补.

4. 0% APR / balance-transfer 促销悬崖 (promo APR cliff):
   BT 促销账户 (is_promo_apr=True, 12 个月 0% APR) 促销期内 DPD30+ 低 (~2-5%),
   促销一到期 (第 12-14 个 cycle_month) 利率跳回 base_apr 后 DPD30+ 跳升到 ~13%
   (同期非促销账户 DPD30+ 反而降到 ~1%).

5. 提额 (CLI) 逆向选择:
   给"高利用率 revolver" (提额前 utilization > 70%) 提额的账户, charge-off 率 ~10%,
   约为提额前利用率 <=70% 账户 (~3.4%) 的约 3 倍. 银行以为在奖励好客户, 其实在加码风险.

6. 开卡奖金猎人 / 负 LTV (bonus churner):
   大额 signup bonus 的 challenger campaign 里, 约 15% 账户是 bonus churner:
   刷够 min-spend 拿到 bonus 后 6-9 个月内销卡, 单账户 lifetime 贡献为负 (bonus > 收入).

7. Vintage 损失曲线恶化 (vintage deterioration):
   承保随时间放松 (approval 率从 ~55% 升到 ~60%, booked FICO 从 ~722 滑到 ~694), 近期
   origination vintage 在 month_on_book<=6 处的 charge-off 率从 2024Q3 的 ~1.2% 升到
   2025Q4 的 ~3.5%.

8. 产品阶梯单账户 P&L (product ladder profitability):
   6 款产品 (Secured -> Student -> Cashback -> Cashback Plus -> Travel -> Venture Premium)
   的单位经济学差异巨大: near-prime cashback 的 revolver 是利润引擎, 高端 travel 的
   transactor 段接近盈亏平衡甚至亏损. 完整 P&L = 利息+interchange+费用 - rewards - loss.

上述陷阱通过有意设计的相关分布注入. 对应的 SQL 查询位于
03-fintech_credit_card_lifecycle_high_sql_queries-cn.md, 用以暴露这些陷阱.
名词与业务动机的通俗讲解见 05-fintech_credit_card_lifecycle_high_analytics_primer-cn.md.
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
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ---------------------------------------------------------------------------
# Section 3. 配置常量
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "fintech_credit_card_lifecycle_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日: 季度末. 所有"今天 / 当前快照 / months_on_book"的语义都锚定到这一天,
# 不依赖系统当前时间. SQL 查询里凡是需要"今天"的地方也用同一个字面量 '2026-06-30'.
REFERENCE_DATE = date(2026, 6, 30)

# 数据观测窗口的最早开卡日. 最老的账户到 REFERENCE_DATE 约 24 个月账龄.
EARLIEST_OPEN_DATE = date(2024, 7, 1)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Section 4. 业务校准常量 (Business Calibration Constants)
# 每个权重 / 概率 / 阈值都写清楚"为什么是这个值", 并点名它服务哪个陷阱.
# ---------------------------------------------------------------------------

# 目标规模 (数量级). 调这几个数就能整体缩放数据集.
N_PRESCREEN_OFFERS = 20000   # 预筛邮寄量; response ~5% -> ~1000 转成申请
N_APPLICATIONS = 18000       # 申请总量 (预筛响应 + 自然 + 网点)
TARGET_ACCOUNTS = 9000       # 批准并激活后的在册账户 (statement 是主要行数来源)

# 加州城市池 (公司只在加州展业, 避免跨州噪声).
CA_CITIES = [
    "Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno",
    "Sacramento", "Long Beach", "Oakland", "Irvine", "Anaheim",
    "Bakersfield", "Riverside", "Santa Ana", "Chula Vista", "Fremont",
    "San Bernardino", "Modesto", "Fontana", "Oxnard", "Huntington Beach",
]

# --- credit_band: FICO 分段 -> 定价假设 & 基准 charge-off ---
# implied_loss 是"定价模型假设的年化损失率"(承保定价时的成本假设);
# base_chargeoff 是生成器实际注入的"观测窗口内 charge-off 概率基线"(未叠加渠道/vintage 等乘子前).
# 除 D 段外, 二者大体对齐 (band 级定价基本准); 真正的坑在陷阱 1: D 段内部分数无法排序风险.
CREDIT_BANDS = [
    # code, name,            fico_min, fico_max, implied_loss, assigned_apr, base_chargeoff
    # base_chargeoff 是"承保当期若不叠加渠道/vintage/CLI 乘子的核销概率基线"; 观测窗口有账龄截断,
    # 实际落库的 pool 核销率约为基线的一半左右 (近期 vintage 尚未走完核销窗口).
    ("A", "Superprime",      780, 850, 0.015, 14.99, 0.022),
    ("B", "Prime",           720, 779, 0.030, 18.99, 0.048),
    ("C", "Near-Prime",      660, 719, 0.060, 22.99, 0.095),
    ("D", "Subprime",        600, 659, 0.100, 26.99, 0.160),
    ("E", "Deep-Subprime",   300, 599, 0.150, 29.99, 0.225),
]

# --- 渠道: 获客成本 & 逆向选择乘子 (陷阱 2) ---
# chargeoff_mult 乘到账户 pd 上. affiliate_partner 便宜且响应高, 但坏账 2x -> 逆向选择.
MARKETING_CHANNELS = [
    # name,              type,       cost_per_contact, chargeoff_mult, approval_lift
    ("direct_mail",      "outbound", 0.85,  0.80, 0.00),
    ("prescreen_mail",   "outbound", 1.10,  0.68, 0.05),   # 预筛过, 质量最好, 坏账最低
    ("digital_display",  "digital",  4.50,  1.15, 0.00),
    ("affiliate_partner","partner",  2.00,  2.30, 0.10),   # 陷阱 2: 便宜+高批准, 坏账最高 ~2x+
    ("social",           "digital",  3.20,  1.45, 0.05),
    ("branch_referral",  "branch",   6.00,  0.72, 0.02),   # 网点转介, 质量最好但获客最贵
]

# --- 产品阶梯 (陷阱 3 & 8): rewards 越高 + 客群越优 -> transactor 越多 -> interchange 被 rewards 吃 ---
CARD_PRODUCTS = [
    # name,                    tier,        annual_fee, base_apr, rewards_rate, rewards_type, target_band, transactor_rate
    ("Keystone Secured",       "secured",     0.0,  26.99, 0.000, "none",     "E", 0.10),
    ("Keystone Student",       "student",     0.0,  23.99, 0.010, "cashback", "C", 0.35),
    ("Keystone Cashback",      "cashback",    0.0,  22.99, 0.015, "cashback", "C", 0.40),
    ("Keystone Cashback Plus", "cashback",   95.0,  21.99, 0.020, "cashback", "B", 0.55),
    ("Keystone Travel",        "travel",     95.0,  20.99, 0.020, "miles",    "B", 0.70),
    ("Keystone Venture Premium","premium",  395.0,  19.99, 0.025, "miles",    "A", 0.82),  # 陷阱 3 主战场
]

# transactor (每月全额还款): interchange 收入 - rewards 成本 常为负, 只赚年费;
# revolver (滚动余额): 靠 APR 利息, 是利润引擎. 这是陷阱 3/8 的经济学根源.
INTERCHANGE_RATE = 0.018   # 平均 interchange 费率 (占刷卡额), 各 MCC 在此上下浮动.

# --- charge-off 时间分布: 集中在 month_on_book 4-15, 峰值 ~7. 支撑早期预警 & vintage 曲线 (陷阱 7) ---
CHARGEOFF_MOB_MIN = 4
CHARGEOFF_MOB_PEAK = 7
CHARGEOFF_MOB_MAX = 16

# --- vintage 恶化 (陷阱 7): 按开卡季度给 pd 乘子, 近期越松 -> 乘子越大 ---
VINTAGE_PD_MULT = {
    "2024Q3": 0.70, "2024Q4": 0.78,
    "2025Q1": 0.90, "2025Q2": 1.00,
    "2025Q3": 1.22, "2025Q4": 1.45,
    "2026Q1": 1.55, "2026Q2": 1.65,
}
# 承保门槛随时间下移 (approval 放松): 早期 FICO cutoff 高, 近期低 -> booked FICO 下滑.
def approval_fico_cutoff(app_dt: date) -> int:
    """按申请日返回 FICO 审批下限. 2024 下半年 ~640, 线性降到 2026 中 ~605 (承保放松)."""
    months_from_start = (app_dt.year - 2024) * 12 + (app_dt.month - 7)
    cutoff = 640 - int(months_from_start * 1.5)   # 每月下移 ~1.5 分
    return max(600, cutoff)

# --- CLI 逆向选择 (陷阱 5) ---
CLI_ELIGIBLE_RATE = 0.40         # 约 40% 账户在生命周期里发生一次提额
CLI_HIGH_UTIL_THRESHOLD = 0.70   # "高利用率"定义: 提额前 utilization > 70%
CLI_HIGH_UTIL_PD_MULT = 2.4      # 高利用率提额账户 pd 乘子 -> ~2.5x charge-off

# --- bonus churner (陷阱 6) ---
BONUS_CHURN_RATE_HIGH_BONUS = 0.15   # 大额 bonus campaign 里约 15% 是奖金猎人
BONUS_CHURN_CLOSE_MOB = (6, 9)       # 拿到奖金后 6-9 个月内销卡

# --- underwriting_score 与 charge-off 的关系 (陷阱 1) ---
# 非 D 段: pd = base * (SCORE_PD_HI - SCORE_PD_SLOPE * score/999), 分数越高 pd 越低 (可排序).
# D 段:   pd = base (常数), score 独立随机 -> 分段 AUC ~0.5, 模型失效.
SCORE_PD_HI = 1.70
SCORE_PD_SLOPE = 1.40

# 账户激活率 (approved -> 真正开卡用起来).
ACTIVATION_RATE = 0.86
# 自愿流失 (非 charge-off, 非 bonus churn) 的基础年化概率.
VOLUNTARY_ATTRITION_BASE = 0.10

# MCC 商户类别 (interchange 费率各异).
MCC_CATEGORIES = [
    # mcc_code, name,               interchange_rate, spend_weight
    ("5411", "Grocery Stores",       0.0155, 0.16),
    ("5541", "Gas Stations",         0.0150, 0.10),
    ("5812", "Restaurants",          0.0195, 0.15),
    ("5814", "Fast Food",            0.0185, 0.08),
    ("5732", "Electronics",          0.0205, 0.05),
    ("5311", "Department Stores",    0.0190, 0.07),
    ("4511", "Airlines",             0.0210, 0.05),
    ("7011", "Hotels & Lodging",     0.0210, 0.04),
    ("5999", "Online Retail",        0.0200, 0.14),
    ("5912", "Drug Stores",          0.0160, 0.05),
    ("4900", "Utilities",            0.0130, 0.05),
    ("7999", "Entertainment",        0.0195, 0.06),
]

DECLINE_REASONS = [
    "Low FICO score",
    "High debt-to-income ratio",
    "Insufficient income",
    "Thin credit file",
    "Recent delinquency on bureau",
    "Failed identity verification",
]

ATTRITION_REASONS = {
    "VOLUNTARY": ["bonus_churn", "rate_shopping", "inactivity", "dissatisfaction", "product_upgrade"],
    "INVOLUNTARY": ["charge_off"],
}


# ---------------------------------------------------------------------------
# Section 5. ORM 模型
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class CreditBand(Base):
    """FICO 风险分段 (A-E). 承保定价的基础维度, 也是陷阱 1 分段算 AUC 的分组键."""

    __tablename__ = "credit_band"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    band_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    band_name: Mapped[str] = mapped_column(String(40), nullable=False)
    fico_min: Mapped[int] = mapped_column(Integer, nullable=False)
    fico_max: Mapped[int] = mapped_column(Integer, nullable=False)
    implied_annual_loss_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    assigned_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class CardProduct(Base):
    """信用卡产品阶梯. 从 secured 起步卡到 Venture Premium, rewards / 年费 / APR 各异 (陷阱 3/8)."""

    __tablename__ = "card_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    product_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_fee_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    base_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rewards_rate_pct: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    rewards_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_band_code: Mapped[str] = mapped_column(String(2), nullable=False)


class MarketingChannel(Base):
    """获客渠道. cost_per_contact 是获客成本分母, 也是陷阱 2 逆向选择的主角 (affiliate)."""

    __tablename__ = "marketing_channel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_per_contact_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class MccCategory(Base):
    """商户类别 (MCC). 决定 interchange 费率与消费结构分析."""

    __tablename__ = "mcc_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mcc_code: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    category_name: Mapped[str] = mapped_column(String(40), nullable=False)
    interchange_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)


class Campaign(Base):
    """一次具体的营销投放. champion/challenger 成对, 部分带大额 signup bonus 或 0% BT 促销 (陷阱 4/6)."""

    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_name: Mapped[str] = mapped_column(String(80), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("marketing_channel.id"), nullable=False)
    card_product_id: Mapped[int] = mapped_column(ForeignKey("card_product.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_champion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    offer_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    promo_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    promo_duration_months: Mapped[int] = mapped_column(Integer, nullable=True)
    signup_bonus_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    min_spend_for_bonus_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    budget_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class Applicant(Base):
    """申请人 (一个自然人). 含承保需要的财务画像. 全部为加州居民."""

    __tablename__ = "applicant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False)
    last_name: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    employment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_income_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class PrescreenOffer(Base):
    """预筛邮寄 offer. 每行=一封寄出的预批信, 含 response 模型分数与实际是否响应 (DS 的响应模型混淆矩阵)."""

    __tablename__ = "prescreen_offer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(40), nullable=False)
    last_name: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    fico_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    response_model_score: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_response_prob: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    mailed_date: Mapped[date] = mapped_column(Date, nullable=False)
    responded: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Application(Base):
    """信用卡申请. 承保决策 (approve/decline)、风险分 underwriting_score、分配的 APR 与额度都在这里."""

    __tablename__ = "application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicant.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=True)
    card_product_id: Mapped[int] = mapped_column(ForeignKey("card_product.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("marketing_channel.id"), nullable=False)
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    fico_at_application: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    credit_band_id: Mapped[int] = mapped_column(ForeignKey("credit_band.id"), nullable=False)
    underwriting_score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    decline_reason: Mapped[str] = mapped_column(String(60), nullable=True)
    approved_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    approved_credit_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)


class Account(Base):
    """在册信用卡账户. approved 且激活后成为 account, 是 statement / transaction / 各类事件的父表."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"), nullable=False)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicant.id"), nullable=False)
    card_product_id: Mapped[int] = mapped_column(ForeignKey("card_product.id"), nullable=False)
    credit_band_id: Mapped[int] = mapped_column(ForeignKey("credit_band.id"), nullable=False)
    acquisition_channel_id: Mapped[int] = mapped_column(ForeignKey("marketing_channel.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaign.id"), nullable=True)
    open_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    purchase_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_promo_apr: Mapped[bool] = mapped_column(Boolean, nullable=False)
    promo_apr_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    promo_end_date: Mapped[date] = mapped_column(Date, nullable=True)
    behavior_segment: Mapped[str] = mapped_column(String(12), nullable=False)
    underwriting_score: Mapped[int] = mapped_column(Integer, nullable=False)
    signup_bonus_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    account_status: Mapped[str] = mapped_column(String(14), nullable=False)
    open_vintage: Mapped[str] = mapped_column(String(6), nullable=False)
    closed_date: Mapped[date] = mapped_column(Date, nullable=True)
    months_on_book: Mapped[int] = mapped_column(Integer, nullable=False)


class Statement(Base):
    """月度账单. 每行=一个账户一个账单周期的完整经济画面 (余额/消费/还款/利息/费用/interchange/rewards/DPD)."""

    __tablename__ = "statement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_balance_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_volume_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_amount_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_charged_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fees_charged_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    interchange_revenue_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    rewards_earned_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    minimum_due_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    credit_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    utilization_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    days_past_due: Mapped[int] = mapped_column(Integer, nullable=False)
    dpd_bucket: Mapped[str] = mapped_column(String(12), nullable=False)
    is_promo_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Transaction(Base):
    """抽样刷卡交易. 不是每一笔真实消费都落库, 只抽样保留用于 MCC / interchange / 欺诈结构分析."""

    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    mcc_category_id: Mapped[int] = mapped_column(ForeignKey("mcc_category.id"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    interchange_revenue_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    is_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RewardsLedger(Base):
    """奖励台账 (离散事件). 只记 signup bonus / 兑换 / 清回 等一次性动作; 按月 accrue 的 rewards 在 statement 里."""

    __tablename__ = "rewards_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(12), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(80), nullable=False)


class CreditLineChange(Base):
    """额度调整事件 (CLI 提额 / CLD 降额). pre_change_utilization 是陷阱 5 逆向选择的关键字段."""

    __tablename__ = "credit_line_change"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    change_type: Mapped[str] = mapped_column(String(4), nullable=False)
    old_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    new_limit_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    pre_change_utilization_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    initiated_by: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(60), nullable=False)


class ChargeOff(Base):
    """核销记录. 账户连续逾期到 180 天被 charge-off; 记录核销余额、回收金额与账龄."""

    __tablename__ = "charge_off"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    charge_off_date: Mapped[date] = mapped_column(Date, nullable=False)
    charged_off_balance_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recovery_amount_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recovery_date: Mapped[date] = mapped_column(Date, nullable=True)
    months_on_book_at_chargeoff: Mapped[int] = mapped_column(Integer, nullable=False)


class AttritionEvent(Base):
    """销卡记录. VOLUNTARY (客户主动) 或 INVOLUNTARY (公司关闭); close_reason 含 bonus_churn (陷阱 6)."""

    __tablename__ = "attrition_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    close_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_type: Mapped[str] = mapped_column(String(12), nullable=False)
    close_reason: Mapped[str] = mapped_column(String(20), nullable=False)
    months_on_book_at_close: Mapped[int] = mapped_column(Integer, nullable=False)


class FraudCase(Base):
    """欺诈案件 (轻量). 交易欺诈的处置记录; 本数据集不深挖欺诈 (另有专门的 fraud/AML 数据集)."""

    __tablename__ = "fraud_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    fraud_type: Mapped[str] = mapped_column(String(30), nullable=False)
    gross_loss_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    net_loss_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    resolution: Mapped[str] = mapped_column(String(20), nullable=False)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def vintage_of(d: date) -> str:
    """把日期映射到 'YYYYQn' vintage 标签."""
    q = (d.month - 1) // 3 + 1
    return f"{d.year}Q{q}"


def add_months(d: date, n: int) -> date:
    """日期加 n 个月 (日取该月内的合法值)."""
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def band_from_fico(fico: int) -> int:
    """FICO 分数 -> credit_band id (1-based, 对应 CREDIT_BANDS 顺序)."""
    for idx, (_code, _name, lo, hi, *_rest) in enumerate(CREDIT_BANDS, start=1):
        if lo <= fico <= hi:
            return idx
    return len(CREDIT_BANDS)  # 兜底: 落到最低段


def chargeoff_mob() -> int:
    """核销发生的 month_on_book, 三角分布, 峰值 ~7."""
    return int(round(random.triangular(CHARGEOFF_MOB_MIN, CHARGEOFF_MOB_MAX, CHARGEOFF_MOB_PEAK)))


# ---------------------------------------------------------------------------
# Section 6. 生成器函数 (拓扑序)
# ---------------------------------------------------------------------------

def gen_credit_bands() -> pl.DataFrame:
    rows = []
    for idx, (code, name, lo, hi, implied, apr, _base) in enumerate(CREDIT_BANDS, start=1):
        rows.append({
            "id": idx, "band_code": code, "band_name": name,
            "fico_min": lo, "fico_max": hi,
            "implied_annual_loss_rate_pct": round(implied * 100, 2),
            "assigned_apr_pct": apr,
        })
    return pl.DataFrame(rows)


def gen_card_products() -> pl.DataFrame:
    rows = []
    for idx, (name, tier, fee, apr, rr, rtype, tband, _tx) in enumerate(CARD_PRODUCTS, start=1):
        rows.append({
            "id": idx, "product_name": name, "product_tier": tier,
            "annual_fee_usd": fee, "base_apr_pct": apr,
            "rewards_rate_pct": round(rr, 3), "rewards_type": rtype,
            "target_band_code": tband,
        })
    return pl.DataFrame(rows)


def gen_marketing_channels() -> pl.DataFrame:
    rows = []
    for idx, (name, ctype, cpc, _m, _a) in enumerate(MARKETING_CHANNELS, start=1):
        rows.append({
            "id": idx, "channel_name": name, "channel_type": ctype,
            "cost_per_contact_usd": cpc,
        })
    return pl.DataFrame(rows)


def gen_mcc_categories() -> pl.DataFrame:
    rows = []
    for idx, (code, name, ic, _w) in enumerate(MCC_CATEGORIES, start=1):
        rows.append({
            "id": idx, "mcc_code": code, "category_name": name,
            "interchange_rate_pct": round(ic, 4),
        })
    return pl.DataFrame(rows)


def gen_campaigns() -> pl.DataFrame:
    """约 24 个 campaign. champion/challenger 成对; 部分 challenger 带大额 bonus (陷阱 6) 或 0% BT 促销 (陷阱 4)."""
    rows = []
    cid = 1
    channel_names = [c[0] for c in MARKETING_CHANNELS]
    quarters = ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]
    quarter_start = {
        "2024Q3": date(2024, 7, 1), "2024Q4": date(2024, 10, 1),
        "2025Q1": date(2025, 1, 1), "2025Q2": date(2025, 4, 1),
        "2025Q3": date(2025, 7, 1), "2025Q4": date(2025, 10, 1),
        "2026Q1": date(2026, 1, 1), "2026Q2": date(2026, 4, 1),
    }
    slot_counter = 0
    for q_idx, q in enumerate(quarters):
        start = quarter_start[q]
        end = add_months(start, 3) - timedelta(days=1)
        # 每季度 3 个 campaign: 1 个 champion (稳态), 2 个 challenger (试新 offer).
        for slot in range(3):
            is_champion = slot == 0
            # 渠道/产品用 round-robin 铺开, 保证每个渠道横跨所有季度 (避免渠道与 vintage 混淆).
            channel_id = (slot_counter % len(MARKETING_CHANNELS)) + 1
            product_id = ((slot_counter * 5) % len(CARD_PRODUCTS)) + 1
            slot_counter += 1
            product = CARD_PRODUCTS[product_id - 1]
            base_apr = product[3]
            # challenger 里一部分打大额 bonus, 一部分打 0% balance-transfer 促销.
            is_bonus_offer = (not is_champion) and slot == 1
            is_bt_offer = (not is_champion) and slot == 2
            if is_bonus_offer:
                signup_bonus = random.choice([200.0, 250.0, 300.0])
                min_spend = random.choice([1500.0, 3000.0])
                promo_apr = None
                promo_months = None
                label = "BonusBoost"
            elif is_bt_offer:
                signup_bonus = 0.0
                min_spend = 0.0
                promo_apr = 0.0
                promo_months = 12   # 0% APR 12 个月, 到期跳回 base_apr -> 陷阱 4
                label = "0pct-BalanceTransfer"
            else:
                signup_bonus = random.choice([0.0, 100.0, 150.0])
                min_spend = 500.0 if signup_bonus > 0 else 0.0
                promo_apr = None
                promo_months = None
                label = "Champion" if is_champion else "Standard"
            rows.append({
                "id": cid,
                "campaign_name": f"{q}-{product[0].split()[-1]}-{label}",
                "channel_id": channel_id,
                "card_product_id": product_id,
                "start_date": start,
                "end_date": end,
                "is_champion": is_champion,
                "offer_apr_pct": base_apr,
                "promo_apr_pct": promo_apr,
                "promo_duration_months": promo_months,
                "signup_bonus_usd": signup_bonus,
                "min_spend_for_bonus_usd": min_spend,
                "budget_usd": float(random.randint(40, 200) * 1000),
            })
            cid += 1
    return pl.DataFrame(rows)


def gen_prescreen_offers(campaigns: pl.DataFrame) -> pl.DataFrame:
    """预筛邮寄. 只有 outbound (direct_mail / prescreen_mail) 渠道的 campaign 会寄预批信."""
    outbound_channel_ids = {1, 2}  # direct_mail, prescreen_mail
    elig = campaigns.filter(pl.col("channel_id").is_in(list(outbound_channel_ids)))
    if elig.height == 0:
        elig = campaigns
    camp_ids = elig["id"].to_list()
    camp_start = dict(zip(campaigns["id"].to_list(), campaigns["start_date"].to_list()))
    rows = []
    for i in range(1, N_PRESCREEN_OFFERS + 1):
        cid = random.choice(camp_ids)
        fico = int(min(830, max(560, random.gauss(700, 55))))  # 预筛人群偏优
        # response 模型分数 (0-999): 与真实响应相关但不完美 (AUC ~0.65).
        latent = random.random()
        response_score = int(min(999, max(1, latent * 999 + random.gauss(0, 80))))
        pred_prob = round(0.02 + 0.10 * (response_score / 999), 4)
        # 实际响应: 概率随分数单调上升, 叠加噪声.
        responded = random.random() < (0.015 + 0.075 * (response_score / 999))
        start = camp_start[cid]
        mailed = start + timedelta(days=random.randint(0, 60))
        rows.append({
            "id": i, "campaign_id": cid,
            "first_name": fake.first_name(), "last_name": fake.last_name(),
            "city": random.choice(CA_CITIES), "state": "CA",
            "fico_estimate": fico,
            "response_model_score": response_score,
            "predicted_response_prob": pred_prob,
            "mailed_date": mailed,
            "responded": responded,
        })
    return pl.DataFrame(rows)


def gen_applicants_and_applications(campaigns: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """生成申请人与申请. 承保决策按 vintage 漂移的 FICO cutoff (陷阱 7), underwriting_score 编码风险 (陷阱 1)."""
    applicants = []
    applications = []
    channel_names = [c[0] for c in MARKETING_CHANNELS]
    channel_approval_lift = {i + 1: MARKETING_CHANNELS[i][4] for i in range(len(MARKETING_CHANNELS))}
    camp_rows = campaigns.to_dicts()
    camp_by_id = {c["id"]: c for c in camp_rows}
    camp_ids = list(camp_by_id.keys())

    for i in range(1, N_APPLICATIONS + 1):
        # 申请日: 在观测窗口内均匀分布 (留出至少 2 周做决策).
        span_days = (REFERENCE_DATE - timedelta(days=14) - EARLIEST_OPEN_DATE).days
        app_dt = EARLIEST_OPEN_DATE + timedelta(days=random.randint(0, span_days))

        # 约 70% 申请归因到某个当时在投的 campaign; 其余算自然/网点流量.
        active_camps = [c for c in camp_ids
                        if camp_by_id[c]["start_date"] <= app_dt <= camp_by_id[c]["end_date"]]
        if active_camps and random.random() < 0.70:
            cid = random.choice(active_camps)
            camp = camp_by_id[cid]
            channel_id = camp["channel_id"]
            product_id = camp["card_product_id"]
        else:
            cid = None
            channel_id = random.randint(1, len(MARKETING_CHANNELS))
            product_id = random.randint(1, len(CARD_PRODUCTS))

        # FICO: 随 vintage 略降 (承保放松, 陷阱 7). 近期均值更低.
        months_from_start = (app_dt.year - 2024) * 12 + (app_dt.month - 7)
        fico_mean = 700 - months_from_start * 1.2
        fico = int(min(840, max(520, random.gauss(fico_mean, 60))))
        band_id = band_from_fico(fico)

        # 收入与年龄
        age = random.randint(21, 70)
        income = round(max(18000, random.gauss(72000, 32000)), 2)
        requested = float(random.choice([1000, 2000, 3000, 5000, 7500, 10000, 15000]))

        # underwriting_score (0-999, 越高越安全) —— 陷阱 1 的载体.
        band_code = CREDIT_BANDS[band_id - 1][0]
        if band_code == "D":
            # D 段: 分数与风险脱钩 (独立随机) -> 分段 AUC ~0.5, 模型失效.
            uw_score = random.randint(1, 999)
        else:
            # 非 D 段: 分数编码 latent 安全度, 与后续 charge-off 反相关 -> 可排序.
            safety = random.random()
            uw_score = int(min(999, max(1, safety * 999 + random.gauss(0, 55))))

        # 承保决策: FICO >= 随时间下移的 cutoff, 叠加渠道 lift 与随机性.
        cutoff = approval_fico_cutoff(app_dt)
        approve_prob = 0.32 + 0.45 * (fico - cutoff) / 120.0 + channel_approval_lift[channel_id]
        approve_prob = min(0.95, max(0.03, approve_prob))
        approved = random.random() < approve_prob
        decision_dt = app_dt + timedelta(days=random.randint(1, 12))

        applicants.append({
            "id": i,
            "first_name": fake.first_name(), "last_name": fake.last_name(),
            "email": fake.email(), "city": random.choice(CA_CITIES), "state": "CA",
            "zip_code": fake.zipcode_in_state("CA") if hasattr(fake, "zipcode_in_state") else fake.postcode(),
            "age": age, "employment_status": random.choice(
                ["employed", "self_employed", "employed", "employed", "retired", "student"]),
            "annual_income_usd": income,
        })

        if approved:
            apr = CREDIT_BANDS[band_id - 1][5]
            # 授信额度: 与收入、band 相关.
            band_limit_factor = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.32, "E": 0.18}[band_code]
            limit = round(min(requested * random.uniform(0.7, 1.3),
                              max(500, income * 0.28 * band_limit_factor)), -1)
            limit = float(max(500, min(35000, limit)))
            decision = "APPROVED"
            decline_reason = None
        else:
            apr = None
            limit = None
            decision = "DECLINED"
            decline_reason = random.choice(DECLINE_REASONS)

        applications.append({
            "id": i, "applicant_id": i, "campaign_id": cid, "card_product_id": product_id,
            "channel_id": channel_id, "application_date": app_dt,
            "fico_at_application": fico, "requested_limit_usd": requested,
            "credit_band_id": band_id, "underwriting_score": uw_score,
            "decision": decision, "decline_reason": decline_reason,
            "approved_apr_pct": apr, "approved_credit_limit_usd": limit,
            "decision_date": decision_dt,
        })

    return pl.DataFrame(applicants), pl.DataFrame(applications)


def gen_accounts_and_lifecycle(
    applications: pl.DataFrame,
    campaigns: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """核心模拟: approved -> 激活为 account, 逐月生成 statement 及 charge_off / attrition / CLI / rewards / transaction / fraud."""

    camp_by_id = {c["id"]: c for c in campaigns.to_dicts()}
    approved = applications.filter(pl.col("decision") == "APPROVED").to_dicts()
    random.shuffle(approved)

    # 激活: 只保留一部分 approved 成为在册账户, 并控制总量在 TARGET_ACCOUNTS 附近.
    accounts = []
    statements = []
    transactions = []
    rewards = []
    cli_changes = []
    chargeoffs = []
    attritions = []
    frauds = []

    acct_id = 0
    stmt_id = 0
    txn_id = 0
    rl_id = 0
    cli_id = 0
    co_id = 0
    at_id = 0
    fr_id = 0

    mcc_ids = list(range(1, len(MCC_CATEGORIES) + 1))
    mcc_weights = [m[3] for m in MCC_CATEGORIES]
    mcc_ic = {i + 1: MCC_CATEGORIES[i][2] for i in range(len(MCC_CATEGORIES))}

    for app in approved:
        if acct_id >= TARGET_ACCOUNTS:
            break
        if random.random() > ACTIVATION_RATE:
            continue

        # open_date 修复 (旧逻辑把窗口末端账户的 open_date 硬拍到单日, 造成
        # decision_date >= open_date 违反 ER §5.1 不变式, 并在 Q20 制造假尖峰).
        # 决策日到 REFERENCE_DATE 之间必须放得下"审批->开卡"的最小 3 天间隔, 否则这张
        # 申请不予激活 (跳过). 满足时 open_gap 取 [3, min(20, 剩余天数)], 保证
        # decision_date < open_date <= REFERENCE_DATE - 1 天, 对所有账户都成立, 且不堆单日.
        max_open_gap = (REFERENCE_DATE - app["decision_date"]).days - 1
        if max_open_gap < 3:
            continue
        open_gap = random.randint(3, min(20, max_open_gap))

        acct_id += 1
        product = CARD_PRODUCTS[app["card_product_id"] - 1]
        band_code = CREDIT_BANDS[app["credit_band_id"] - 1][0]
        base_co = CREDIT_BANDS[app["credit_band_id"] - 1][6]
        channel_id = app["channel_id"]
        channel_mult = MARKETING_CHANNELS[channel_id - 1][3]
        camp = camp_by_id.get(app["campaign_id"]) if app["campaign_id"] else None

        open_dt = app["decision_date"] + timedelta(days=open_gap)
        vintage = vintage_of(open_dt)
        limit = float(app["approved_credit_limit_usd"])
        base_apr = float(app["approved_apr_pct"])
        uw_score = app["underwriting_score"]

        # 促销: 若 campaign 是 0% BT 促销, 账户带 promo (陷阱 4).
        is_promo = bool(camp and camp["promo_apr_pct"] is not None)
        promo_apr = 0.0 if is_promo else None
        promo_end = add_months(open_dt, camp["promo_duration_months"]) if is_promo else None

        # 行为分层: transactor (全额还款) vs revolver (滚动余额). 产品越高端 transactor 越多 (陷阱 3).
        tx_rate = product[7]
        # superprime 更偏 transactor, subprime 更偏 revolver.
        band_tx_adj = {"A": 0.15, "B": 0.05, "C": -0.05, "D": -0.15, "E": -0.20}[band_code]
        is_transactor = random.random() < min(0.95, max(0.05, tx_rate + band_tx_adj))
        behavior = "TRANSACTOR" if is_transactor else "REVOLVER"

        # signup bonus: campaign 有 bonus 且账户"刷够 min-spend"(大多数能达标).
        signup_bonus = 0.0
        if camp and camp["signup_bonus_usd"] and camp["signup_bonus_usd"] > 0:
            if random.random() < 0.80:
                signup_bonus = float(camp["signup_bonus_usd"])

        # bonus churner (陷阱 6): 大额 bonus campaign 里一部分账户拿钱就跑.
        # 他们的画像: 刷够 min-spend 拿 bonus (transactor, 不产生利息), 之后消费归零, 首年年费也在销卡前被豁免/退掉,
        # 所以一生贡献 ≈ 一点点 interchange - signup bonus < 0 (负 LTV).
        is_bonus_churner = False
        if signup_bonus >= 200 and random.random() < BONUS_CHURN_RATE_HIGH_BONUS:
            is_bonus_churner = True
            behavior = "TRANSACTOR"

        # --- 决定命运: charge-off / bonus_churn close / voluntary close / 存活 ---
        # 组合 pd (观测窗口内 charge-off 概率).
        if band_code == "D":
            pd = base_co                      # D 段: 分数无关 (陷阱 1)
        else:
            pd = base_co * (SCORE_PD_HI - SCORE_PD_SLOPE * (uw_score / 999.0))
        pd *= channel_mult                    # 渠道逆向选择 (陷阱 2)
        pd *= VINTAGE_PD_MULT.get(vintage, 1.0)  # vintage 恶化 (陷阱 7)

        # CLI 逆向选择 (陷阱 5): 决定是否提额, 以及提额前是否高利用率.
        got_cli = (not is_bonus_churner) and random.random() < CLI_ELIGIBLE_RATE
        cli_high_util = got_cli and (behavior == "REVOLVER") and random.random() < 0.45
        if cli_high_util:
            pd *= CLI_HIGH_UTIL_PD_MULT

        pd = min(0.62, max(0.004, pd))

        # 账龄上限 (到 REFERENCE_DATE).
        max_mob = (REFERENCE_DATE.year - open_dt.year) * 12 + (REFERENCE_DATE.month - open_dt.month)
        max_mob = max(1, min(24, max_mob))

        fate = "ACTIVE"
        end_mob = max_mob
        co_at_mob = None
        close_at_mob = None
        close_reason = None
        close_type = None

        if is_bonus_churner:
            cm = random.randint(*BONUS_CHURN_CLOSE_MOB)
            if cm <= max_mob:
                fate = "CLOSED"
                close_at_mob = cm
                close_reason = "bonus_churn"
                close_type = "VOLUNTARY"
                end_mob = cm
        else:
            will_co = random.random() < pd
            if will_co:
                cm = chargeoff_mob()
                if cm <= max_mob:
                    fate = "CHARGED_OFF"
                    co_at_mob = cm
                    end_mob = cm
            if fate == "ACTIVE" and max_mob >= 4:
                # 自愿流失 (rate_shopping / inactivity / upgrade). 概率随账龄累积.
                vol_prob = VOLUNTARY_ATTRITION_BASE * (max_mob / 12.0)
                if random.random() < vol_prob:
                    cm = random.randint(3, max_mob)
                    fate = "CLOSED"
                    close_at_mob = cm
                    close_reason = random.choice(["rate_shopping", "inactivity", "dissatisfaction", "product_upgrade"])
                    close_type = "VOLUNTARY"
                    end_mob = cm

        # --- 逐月生成 statement ---
        # 每月消费基准: 与额度、行为相关 (transactor 刷得多, revolver 刷得少).
        spend_base = limit * (random.uniform(0.35, 0.75) if behavior == "TRANSACTOR"
                              else random.uniform(0.15, 0.45))
        prev_balance = 0.0
        cli_done = False
        # 提额发生的 mob (若 got_cli).
        cli_mob = random.randint(4, max(4, max_mob - 1)) if got_cli else None
        current_limit = limit
        anniversary_fee = product[2]

        for m in range(1, end_mob + 1):
            stmt_dt = add_months(open_dt, m)
            if stmt_dt > REFERENCE_DATE:
                break

            # 提额落地
            if got_cli and cli_mob is not None and m == cli_mob and not cli_done:
                pre_util = round(min(1.5, prev_balance / current_limit) if current_limit else 0, 2)
                new_limit = round(current_limit * random.uniform(1.2, 1.6), -1)
                cli_id += 1
                cli_changes.append({
                    "id": cli_id, "account_id": acct_id, "change_date": stmt_dt,
                    "change_type": "CLI",
                    "old_limit_usd": current_limit, "new_limit_usd": float(new_limit),
                    "pre_change_utilization_pct": round(pre_util * 100, 2),
                    "initiated_by": "bank" if random.random() < 0.7 else "customer",
                    "reason": "high_utilization_review" if cli_high_util else "good_standing_review",
                })
                current_limit = float(new_limit)
                cli_done = True

            promo_active = bool(is_promo and promo_end and stmt_dt < promo_end)
            eff_apr = 0.0 if promo_active else base_apr

            # 消费额
            purchase = max(0.0, random.gauss(spend_base, spend_base * 0.35))
            purchase = min(purchase, current_limit * 0.95)
            # bonus churner: 前 2 个月刷够 min-spend, 之后消费基本归零 (拿到奖金就休眠).
            if is_bonus_churner and m > 2:
                purchase *= 0.08

            # DPD 逻辑
            dpd = 0
            if fate == "CHARGED_OFF" and co_at_mob is not None:
                # charge-off 前的逐步恶化 (早期预警): 最后 4 个月 DPD 阶梯上升.
                months_to_co = co_at_mob - m
                if months_to_co == 3:
                    dpd = 30
                elif months_to_co == 2:
                    dpd = 60
                elif months_to_co == 1:
                    dpd = 90
                elif months_to_co == 0:
                    dpd = 150
            # promo 悬崖 (陷阱 4): 促销到期后的 1-3 个月 DPD 跳升.
            if is_promo and promo_end is not None:
                months_since_promo = (stmt_dt.year - promo_end.year) * 12 + (stmt_dt.month - promo_end.month)
                if 0 <= months_since_promo <= 2 and random.random() < 0.11 and fate != "CHARGED_OFF":
                    dpd = max(dpd, 30 * random.randint(1, 2))

            # 余额与还款
            if behavior == "TRANSACTOR" and dpd == 0:
                balance = purchase
                payment = prev_balance    # 上期账单全额还清
                interest = 0.0
            else:
                # revolver: 携带余额, 还最低到部分.
                carry = prev_balance
                interest = round(carry * (eff_apr / 100.0 / 12.0), 2)
                balance = round(carry + purchase + interest, 2)
                balance = min(balance, current_limit * 1.02)
                if dpd == 0:
                    pay_ratio = random.uniform(0.05, 0.35)
                else:
                    pay_ratio = random.uniform(0.0, 0.03)   # 逾期时几乎不还
                payment = round(carry * pay_ratio, 2)

            # 费用: 年费 (周年月) + 滞纳金 (逾期). bonus churner 首年年费视为豁免/退回, 不计.
            fees = 0.0
            if anniversary_fee > 0 and not is_bonus_churner:
                if m == 1:
                    fees += anniversary_fee   # 开卡即收首年年费
                elif m % 12 == 1 and m > 1:
                    fees += anniversary_fee   # 续年年费
            if dpd >= 30:
                fees += 35.0   # late fee

            interchange = round(purchase * INTERCHANGE_RATE, 2)
            rewards_earned = round(purchase * product[4], 2)  # product[4] = rewards_rate_pct
            min_due = round(max(25.0, balance * 0.02 + interest + fees), 2) if balance > 0 else 0.0
            util = round(min(1.5, balance / current_limit) * 100, 2) if current_limit else 0.0

            if dpd == 0:
                bucket = "CURRENT"
            elif dpd < 60:
                bucket = "DPD30"
            elif dpd < 90:
                bucket = "DPD60"
            elif dpd < 120:
                bucket = "DPD90"
            elif dpd < 180:
                bucket = "DPD120PLUS"
            else:
                bucket = "CHARGEOFF"

            stmt_id += 1
            statements.append({
                "id": stmt_id, "account_id": acct_id, "statement_date": stmt_dt,
                "cycle_month": m,
                "statement_balance_usd": round(balance, 2),
                "purchase_volume_usd": round(purchase, 2),
                "payment_amount_usd": round(payment, 2),
                "interest_charged_usd": round(interest, 2),
                "fees_charged_usd": round(fees, 2),
                "interchange_revenue_usd": interchange,
                "rewards_earned_usd": rewards_earned,
                "minimum_due_usd": min_due,
                "credit_limit_usd": current_limit,
                "utilization_pct": util,
                "days_past_due": dpd,
                "dpd_bucket": bucket,
                "is_promo_active": promo_active,
            })
            prev_balance = balance if behavior != "TRANSACTOR" or dpd > 0 else 0.0

            # 抽样交易 (~每 3 个账单月抽 1 笔), 供 MCC 分析.
            if purchase > 0 and random.random() < 0.35:
                txn_id += 1
                mcc = random.choices(mcc_ids, weights=mcc_weights, k=1)[0]
                amt = round(min(purchase, max(8.0, random.gauss(purchase / 4, purchase / 6))), 2)
                is_fraud_txn = random.random() < 0.004
                transactions.append({
                    "id": txn_id, "account_id": acct_id, "mcc_category_id": mcc,
                    "transaction_date": stmt_dt - timedelta(days=random.randint(1, 25)),
                    "amount_usd": amt,
                    "interchange_revenue_usd": round(amt * mcc_ic[mcc], 2),
                    "is_fraud": is_fraud_txn,
                })
                if is_fraud_txn:
                    fr_id += 1
                    gross = round(amt * random.uniform(1, 4), 2)
                    recovered = random.random() < 0.6
                    frauds.append({
                        "id": fr_id, "account_id": acct_id,
                        "reported_date": stmt_dt + timedelta(days=random.randint(1, 20)),
                        "fraud_type": random.choice(
                            ["card_not_present", "lost_stolen", "account_takeover", "counterfeit"]),
                        "gross_loss_usd": gross,
                        "net_loss_usd": 0.0 if recovered else gross,
                        "resolution": "recovered" if recovered else "written_off",
                    })

        # signup bonus 台账 (mob 2-3 达标后入账).
        if signup_bonus > 0:
            rl_id += 1
            bonus_dt = add_months(open_dt, min(3, max_mob))
            rewards.append({
                "id": rl_id, "account_id": acct_id, "entry_date": bonus_dt,
                "entry_type": "BONUS", "amount_usd": signup_bonus,
                "description": f"Signup bonus after ${camp['min_spend_for_bonus_usd']:.0f} min spend",
            })
        # 兑换事件 (奖励卡偶发兑换).
        if product[4] > 0 and random.random() < 0.4 and end_mob >= 6:
            rl_id += 1
            redeem_dt = add_months(open_dt, random.randint(4, max(4, end_mob)))
            rewards.append({
                "id": rl_id, "account_id": acct_id, "entry_date": redeem_dt,
                "entry_type": "REDEEMED", "amount_usd": round(random.uniform(20, 250), 2),
                "description": "Cashback/miles redemption",
            })

        # charge-off 记录
        status = "ACTIVE"
        closed_dt = None
        final_mob = end_mob
        if fate == "CHARGED_OFF" and co_at_mob is not None:
            co_dt = add_months(open_dt, co_at_mob)
            co_balance = round(max(200.0, prev_balance if prev_balance > 0 else current_limit * random.uniform(0.5, 0.95)), 2)
            recovered = round(co_balance * random.uniform(0.05, 0.35), 2)
            has_recovery = random.random() < 0.7
            co_id += 1
            chargeoffs.append({
                "id": co_id, "account_id": acct_id, "charge_off_date": co_dt,
                "charged_off_balance_usd": co_balance,
                "recovery_amount_usd": recovered if has_recovery else 0.0,
                "recovery_date": add_months(co_dt, random.randint(2, 8)) if has_recovery else None,
                "months_on_book_at_chargeoff": co_at_mob,
            })
            status = "CHARGED_OFF"
            closed_dt = co_dt
            final_mob = co_at_mob
            # 同时登记为 INVOLUNTARY 流失
            at_id += 1
            attritions.append({
                "id": at_id, "account_id": acct_id, "close_date": co_dt,
                "close_type": "INVOLUNTARY", "close_reason": "charge_off",
                "months_on_book_at_close": co_at_mob,
            })
        elif fate == "CLOSED" and close_at_mob is not None:
            cl_dt = add_months(open_dt, close_at_mob)
            status = "CLOSED"
            closed_dt = cl_dt
            final_mob = close_at_mob
            at_id += 1
            attritions.append({
                "id": at_id, "account_id": acct_id, "close_date": cl_dt,
                "close_type": close_type, "close_reason": close_reason,
                "months_on_book_at_close": close_at_mob,
            })

        accounts.append({
            "id": acct_id, "application_id": app["id"], "applicant_id": app["applicant_id"],
            "card_product_id": app["card_product_id"], "credit_band_id": app["credit_band_id"],
            "acquisition_channel_id": channel_id, "campaign_id": app["campaign_id"],
            "open_date": open_dt, "credit_limit_usd": limit,
            "purchase_apr_pct": base_apr, "is_promo_apr": is_promo,
            "promo_apr_pct": promo_apr, "promo_end_date": promo_end,
            "behavior_segment": behavior, "underwriting_score": uw_score,
            "signup_bonus_usd": signup_bonus, "account_status": status,
            "open_vintage": vintage, "closed_date": closed_dt,
            "months_on_book": final_mob,
        })

    return {
        "account": pl.DataFrame(accounts),
        "statement": pl.DataFrame(statements),
        "transaction": pl.DataFrame(transactions),
        "rewards_ledger": pl.DataFrame(rewards),
        "credit_line_change": pl.DataFrame(cli_changes),
        "charge_off": pl.DataFrame(chargeoffs),
        "attrition_event": pl.DataFrame(attritions),
        "fraud_case": pl.DataFrame(frauds),
    }


# ---------------------------------------------------------------------------
# Section 7. generate_all_tsv
# ---------------------------------------------------------------------------

def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_band = gen_credit_bands()
    df_band.write_csv(DATA_DIR / "01_credit_band.tsv", separator="\t")

    df_product = gen_card_products()
    df_product.write_csv(DATA_DIR / "02_card_product.tsv", separator="\t")

    df_channel = gen_marketing_channels()
    df_channel.write_csv(DATA_DIR / "03_marketing_channel.tsv", separator="\t")

    df_mcc = gen_mcc_categories()
    df_mcc.write_csv(DATA_DIR / "04_mcc_category.tsv", separator="\t")

    df_campaign = gen_campaigns()
    df_campaign.write_csv(DATA_DIR / "05_campaign.tsv", separator="\t")

    df_prescreen = gen_prescreen_offers(df_campaign)
    df_prescreen.write_csv(DATA_DIR / "06_prescreen_offer.tsv", separator="\t")

    df_applicant, df_application = gen_applicants_and_applications(df_campaign)
    df_applicant.write_csv(DATA_DIR / "07_applicant.tsv", separator="\t")
    df_application.write_csv(DATA_DIR / "08_application.tsv", separator="\t")

    life = gen_accounts_and_lifecycle(df_application, df_campaign)
    life["account"].write_csv(DATA_DIR / "09_account.tsv", separator="\t")
    life["statement"].write_csv(DATA_DIR / "10_statement.tsv", separator="\t")
    life["transaction"].write_csv(DATA_DIR / "11_transaction.tsv", separator="\t")
    life["rewards_ledger"].write_csv(DATA_DIR / "12_rewards_ledger.tsv", separator="\t")
    life["credit_line_change"].write_csv(DATA_DIR / "13_credit_line_change.tsv", separator="\t")
    life["charge_off"].write_csv(DATA_DIR / "14_charge_off.tsv", separator="\t")
    life["attrition_event"].write_csv(DATA_DIR / "15_attrition_event.tsv", separator="\t")
    life["fraud_case"].write_csv(DATA_DIR / "16_fraud_case.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")
    print(f"  accounts={life['account'].height}, statements={life['statement'].height}, "
          f"transactions={life['transaction'].height}, charge_offs={life['charge_off'].height}")


# ---------------------------------------------------------------------------
# Section 8. create_sqlite_database (Core API batch loader)
# ---------------------------------------------------------------------------

def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order = [
        ("01_credit_band", CreditBand.__table__),
        ("02_card_product", CardProduct.__table__),
        ("03_marketing_channel", MarketingChannel.__table__),
        ("04_mcc_category", MccCategory.__table__),
        ("05_campaign", Campaign.__table__),
        ("06_prescreen_offer", PrescreenOffer.__table__),
        ("07_applicant", Applicant.__table__),
        ("08_application", Application.__table__),
        ("09_account", Account.__table__),
        ("10_statement", Statement.__table__),
        ("11_transaction", Transaction.__table__),
        ("12_rewards_ledger", RewardsLedger.__table__),
        ("13_credit_line_change", CreditLineChange.__table__),
        ("14_charge_off", ChargeOff.__table__),
        ("15_attrition_event", AttritionEvent.__table__),
        ("16_fraud_case", FraudCase.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv",
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=10000,
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
