"""
金融科技 — 中小企业贷款流水线 假数据生成器
复杂度: Medium
生成者: Fake Data Generator Agent

业务背景:
Pacific Bridge Lending 是一家总部位于加州的中型金融科技公司, 专注于中小企业 (SMB)
贷款. 本数据集模拟其完整的贷款流水线: 从申请受理, 到还款 / 违约, 用于支撑以下分析:
1. 风险定价对齐 (各风险等级定价是否准确?)
2. 组合集中度 (行业敞口管理)
3. 审批漏失 (优质客户被错误拒绝)
4. 早期预警信号 (违约前的行为指标)
5. 客户全生命周期价值 (复购 vs 新客户)

数据集包含约 3,000 份贷款申请, 跨越约 2 年, 上述五个"业务陷阱"通过有意设计的相关
分布注入 (等级驱动的违约率, 加权行业, 信用分驱动的审批, 违约前的还款恶化,
复购客户的更优表现). 对应的 SQL 查询位于 {dataset}_sql_queries-cn.md, 用以暴露这些陷阱.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
import random

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, Boolean, Date, Numeric, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "fintech_smb_lending_pipeline_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证生成结果确定性. 所有"今天 / 当前快照"的计算都锚定到这里, 因此
# 无论系统当前时间如何, 多次运行结果都可复现; 也使 payment 日期始终落在有界窗口内.
REFERENCE_DATE = date(2026, 6, 3)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# 业务校准常量
# ============================================================================

# **首次借款人**的各等级违约概率. 复购客户 (is_repeat_customer=True 的约 12%) 的违约率
# 是这里数值的一半 (见 REPEAT_DEFAULT_MULTIPLIER), 另有约 5% 本应违约的贷款因可行性
# 裁剪 (贷款太新, 还来不及违约) 被抑制. 因此池级实测违约率会比首借率低几个点.
# Grade C 是核心定价错配: 首借 12% 配上组合中的等级分布, 池级实测约 10% —— 比定价模型
# 假设的 6.0% 高出约 4pp. Grade A 和 B 落在 implied ±1pp 内; D 和 E 轻微定价不足 (~1-2pp).
GRADE_FIRSTTIME_DEFAULT_RATE = {
    1: 0.035,  # A - Prime           (implied 3.0%; 池级 ~4%, 轻微高估)
    2: 0.065,  # B - Near Prime      (implied 6.0%; 池级 ~6%, 接近定价)
    3: 0.120,  # C - Standard        (implied 6.0%; 池级 ~10% —— 定价不足约 4pp)
    4: 0.150,  # D - Subprime        (implied 13.0%; 池级 ~15%, 约 2pp 不足)
    5: 0.220,  # E - Deep Subprime   (implied 18.0%; 池级 ~19%, 轻微不足)
}

# 复购客户的违约率是首借率的一半 (Q5 全生命周期论点).
REPEAT_DEFAULT_MULTIPLIER = 0.5

# 行业权重把组合偏向 Restaurant / Tech / Construction,
# 让 Q2 的集中度分析有真实的集中度可挖.
INDUSTRY_WEIGHTS = {
    1: 18,   # Restaurant
    2: 8,    # Retail
    3: 12,   # Technology Services
    4: 10,   # Construction
    5: 5,    # Healthcare Services
    6: 5,    # Professional Services
    7: 5,    # Manufacturing
    8: 5,    # Wholesale Trade
    9: 5,    # Transportation
    10: 5,   # Real Estate
    11: 9,   # Hospitality
    12: 3,   # Education
    13: 3,   # Automotive Services
    14: 3,   # Beauty & Personal Care
    15: 5,   # Other Services
}

# 非复购客户的目标等级分布 —— 用来决定给他们抽取的信用分. 整体偏低, 因为审批闸门 (下方)
# 会把放款向上筛选, 所以要得到一个均衡的审批后等级分布, 客户池本身需要更偏风险.
NONREPEAT_GRADE_WEIGHTS = {
    1: 12,  # A
    2: 22,  # B
    3: 28,  # C
    4: 25,  # D
    5: 13,  # E
}

# 复购客户偏向更优等级, 但并非全是 prime.
REPEAT_GRADE_WEIGHTS = {
    1: 35,
    2: 30,
    3: 20,
    4: 10,
    5: 5,
}

# 被标记为复购的客户占比. 他们比非复购客户拿到更多申请,
# 所以这个标记与底层事实保持一致.
REPEAT_CUSTOMER_SHARE = 0.15

# 违约中在最后几期表现出可观测预警信号 (逾期 / 部分付款) 的占比 —— Q4 的前提.
WARNING_RATE = 0.72

# 非违约的在贷贷款提前结清的概率. 经调校使整体 PAID_OFF 率
# 接近 ER 文档的 ~20% 目标.
EARLY_PAYOFF_PROB = 0.18

# 贷款违约时的回收率区间. 等级更高的借款人往往回收更好 (更配合, 抵押更足,
# 文档更干净); deep-subprime 违约回收最少. Q10 读取这些数值.
GRADE_RECOVERY_RANGE = {
    1: (0.45, 0.65),  # A: 均值 ~55%
    2: (0.40, 0.55),  # B: 均值 ~47%
    3: (0.30, 0.45),  # C: 均值 ~37%
    4: (0.25, 0.40),  # D: 均值 ~32%
    5: (0.15, 0.30),  # E: 均值 ~22%
}


def approval_probability(credit_score: int) -> float:
    """按信用分区间给出审批概率.

    分数越高审批越多; 分数越低很少批. 区间在顶部刻意宽松, 在底部刻意严苛,
    使得 Q3 能在被拒池里找到画像看起来像已批借款人的申请人
    (被拒池中约 20-25% 的漏失).
    """
    if credit_score >= 720:
        return 0.95
    if credit_score >= 680:
        return 0.88
    if credit_score >= 640:
        return 0.78
    if credit_score >= 600:
        return 0.55
    return 0.35


def pick_credit_score(is_repeat: bool) -> int:
    """抽取一个信用分, 使其目标等级符合期望分布."""
    weights = REPEAT_GRADE_WEIGHTS if is_repeat else NONREPEAT_GRADE_WEIGHTS
    grade_id = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]
    # 等级区间与下方的 risk_grade 表一致.
    bands = {
        1: (720, 820),
        2: (680, 719),
        3: (640, 679),
        4: (600, 639),
        5: (550, 599),
    }
    lo, hi = bands[grade_id]
    return random.randint(lo, hi)


def amortization_remaining(principal: float, monthly_rate: float, monthly_payment: float, k: int) -> float:
    """规则摊销下, 已付 k 期后的剩余本金."""
    if k <= 0:
        return principal
    if monthly_rate == 0:
        return max(0.0, principal - monthly_payment * k)
    factor = (1 + monthly_rate) ** k
    return max(0.0, principal * factor - monthly_payment * (factor - 1) / monthly_rate)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""
    pass


class Industry(Base):
    """借款企业的行业分类."""
    __tablename__ = "industry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    industry_name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_rate_baseline: Mapped[float] = mapped_column(Float, nullable=False)


class RiskGrade(Base):
    """带定价参数的风险等级层级."""
    __tablename__ = "risk_grade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grade_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    grade_name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    implied_default_rate: Mapped[float] = mapped_column(Float, nullable=False)


class LoanStatus(Base):
    """贷款申请与生命周期状态."""
    __tablename__ = "loan_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status_category: Mapped[str] = mapped_column(String(20), nullable=False)


class LoanOfficer(Base):
    """处理申请的信贷员."""
    __tablename__ = "loan_officer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    hire_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)


class Customer(Base):
    """企业借款人."""
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    industry_id: Mapped[int] = mapped_column(Integer, ForeignKey("industry.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    founded_year: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_revenue: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 法人 / 担保人的 FICO 风格信用分 (300-850)
    first_contact_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    is_repeat_customer: Mapped[bool] = mapped_column(Boolean, default=False)


class Application(Base):
    """贷款申请."""
    __tablename__ = "application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    loan_officer_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_officer.id"), nullable=False)
    requested_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    requested_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    application_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    decision_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_status.id"), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Loan(Base):
    """已批准并放款的贷款."""
    __tablename__ = "loan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("application.id"), nullable=False, unique=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=False)
    risk_grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_grade.id"), nullable=False)
    approved_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_payment: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    disbursement_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    current_status_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_status.id"), nullable=False)
    outstanding_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class RepaymentSchedule(Base):
    """每笔贷款的预期月度还款计划."""
    __tablename__ = "repayment_schedule"
    __table_args__ = (
        UniqueConstraint("loan_id", "installment_number", name="uq_repayment_schedule_loan_installment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan.id", ondelete="CASCADE"), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    scheduled_payment: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    principal_portion: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    interest_portion: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    remaining_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class Payment(Base):
    """实际收到的借款人还款."""
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan.id", ondelete="CASCADE"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    payment_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    days_late: Mapped[int] = mapped_column(Integer, default=0)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)


class DefaultEvent(Base):
    """违约事件, 含早期预警指标."""
    __tablename__ = "default_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan.id"), nullable=False, unique=True)
    default_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    installments_missed: Mapped[int] = mapped_column(Integer, nullable=False)
    outstanding_at_default: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recovery_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    loss_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    had_early_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_signals: Mapped[str | None] = mapped_column(String(500), nullable=True)


# ============================================================================
# 数据生成器
# ============================================================================

def gen_industries() -> pl.DataFrame:
    """生成行业分类记录."""
    industries = [
        (1, "REST", "Restaurant", 9.5),
        (2, "RETAIL", "Retail", 8.2),
        (3, "TECH", "Technology Services", 4.1),
        (4, "CONST", "Construction", 11.3),
        (5, "HEALTH", "Healthcare Services", 5.8),
        (6, "PROF", "Professional Services", 6.2),
        (7, "MANUF", "Manufacturing", 7.4),
        (8, "WHOLE", "Wholesale Trade", 6.9),
        (9, "TRANSP", "Transportation", 10.1),
        (10, "REALES", "Real Estate", 8.8),
        (11, "HOSPIT", "Hospitality", 12.4),
        (12, "EDUC", "Education", 4.6),
        (13, "AUTO", "Automotive Services", 7.8),
        (14, "BEAUTY", "Beauty & Personal Care", 9.2),
        (15, "OTHER", "Other Services", 8.5),
    ]
    return pl.DataFrame(
        industries,
        schema=["id", "industry_code", "industry_name", "default_rate_baseline"],
        orient="row",
    )


def gen_risk_grades() -> pl.DataFrame:
    """生成风险等级层级."""
    grades = [
        (1, "A", "Prime", 720, 850, 5.5, 3.0),
        (2, "B", "Near Prime", 680, 719, 7.5, 6.0),
        (3, "C", "Standard", 640, 679, 9.5, 6.0),  # 定价错配 —— 池级实测 ~10% (比 implied 6% 高出约 4pp)
        (4, "D", "Subprime", 600, 639, 12.5, 13.0),
        (5, "E", "Deep Subprime", 300, 599, 16.0, 18.0),
    ]
    return pl.DataFrame(
        grades,
        schema=["id", "grade_code", "grade_name", "min_credit_score", "max_credit_score", "interest_rate", "implied_default_rate"],
        orient="row",
    )


def gen_loan_statuses() -> pl.DataFrame:
    """生成贷款状态码."""
    statuses = [
        (1, "PENDING", "Pending Review", "Application"),
        (2, "UNDER_REVIEW", "Under Review", "Application"),
        (3, "APPROVED", "Approved", "Application"),
        (4, "REJECTED", "Rejected", "Application"),
        (5, "DISBURSED", "Disbursed", "Active"),
        (6, "CURRENT", "Current", "Active"),
        (7, "DEFAULTED", "Defaulted", "Closed"),
        (8, "PAID_OFF", "Paid Off", "Closed"),
    ]
    return pl.DataFrame(
        statuses,
        schema=["id", "status_code", "status_name", "status_category"],
        orient="row",
    )


def gen_loan_officers() -> pl.DataFrame:
    """生成信贷员记录."""
    regions = ["Northern CA", "Southern CA", "Bay Area", "Central Valley"]
    records = []
    for i in range(1, 21):
        records.append({
            "id": i,
            "employee_id": f"LO{str(i).zfill(4)}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": f"lo{str(i).zfill(4)}@pacificbridge.com",
            "hire_date": fake.date_between(start_date="-5y", end_date="-6m"),
            "region": random.choice(regions),
        })
    return pl.DataFrame(records)


def gen_customers(n: int = 800) -> pl.DataFrame:
    """生成企业客户记录.

    复购客户状态预先分配 (~15%), 信用分按抽样使最终的等级分布符合
    NONREPEAT_/REPEAT_GRADE_WEIGHTS. first_contact_date 锚定在任何合理的
    application_date 之前足够早处, 以保证时序顺序成立.
    """
    industry_ids = list(INDUSTRY_WEIGHTS.keys())
    industry_weights = list(INDUSTRY_WEIGHTS.values())

    ca_cities = ["Los Angeles", "San Francisco", "San Diego", "Sacramento", "San Jose",
                 "Fresno", "Oakland", "Bakersfield", "Anaheim", "Riverside"]

    # 首次接触日远早于最早可能的申请日
    contact_start = REFERENCE_DATE - timedelta(days=int(3 * 365))
    contact_end = REFERENCE_DATE - timedelta(days=int(2 * 365 + 60))

    records = []
    for i in range(1, n + 1):
        is_repeat = random.random() < REPEAT_CUSTOMER_SHARE
        credit_score = pick_credit_score(is_repeat)

        # 营收 / 员工规模大体跟随信用水平 —— 信用更高的借款人往往更大 / 更成熟.
        # 并非严格规则.
        size_multiplier = 1.0 + (credit_score - 600) / 600.0
        revenue = int(random.randint(200_000, 4_500_000) * max(0.5, min(2.0, size_multiplier)))
        employees = random.randint(5, 150)
        founded_year = random.randint(1990, 2020)

        records.append({
            "id": i,
            "business_name": fake.company(),
            "tax_id": fake.unique.bothify(text="##-#######"),
            "industry_id": random.choices(industry_ids, weights=industry_weights, k=1)[0],
            "state": "CA",
            "city": random.choice(ca_cities),
            "founded_year": founded_year,
            "annual_revenue": revenue,
            "employee_count": employees,
            "credit_score": credit_score,
            "first_contact_date": fake.date_between(start_date=contact_start, end_date=contact_end),
            "is_repeat_customer": is_repeat,
        })

    fake.unique.clear()
    return pl.DataFrame(records)


def gen_applications(customers: pl.DataFrame, officer_ids: list[int], n: int = 3000) -> pl.DataFrame:
    """生成贷款申请记录.

    复购客户会拿到不成比例更多的申请, 使 is_repeat_customer 标记与客户的实际
    贷款数大体匹配. 审批取决于 credit_score (并在顶部刻意保留漏失).
    """
    rejection_reasons_by_band = {
        "low_credit": ["Insufficient credit history", "Credit score below threshold", "Recent bankruptcy"],
        "mid_credit": ["DTI ratio too high", "Unstable revenue", "Industry risk concentration"],
        "high_credit": ["Collateral insufficient", "Documentation incomplete", "Industry risk concentration"],
    }
    approved_status_id = 3
    rejected_status_id = 4

    # 对复购客户做轻度加权 (2x), 使他们的申请数比非复购略多, 同时把他们在总贷款中的
    # 占比保持适度 (~20-25%). is_repeat_customer 最好理解为入职时设置的客户层级标记
    # (忠诚度 / 高级), 而不是从贷款历史派生的计数 —— 但这点偏置让它与之松散相关.
    is_repeat_lookup = dict(zip(customers["id"].to_list(), customers["is_repeat_customer"].to_list()))
    credit_lookup = dict(zip(customers["id"].to_list(), customers["credit_score"].to_list()))

    customer_pool = customers["id"].to_list()
    customer_weights = [2 if is_repeat_lookup[cid] else 1 for cid in customer_pool]

    # 申请日窗口: 从 REFERENCE_DATE 起 -22 个月到 -3 个月. 比之前稍紧, 使贷款有时间成熟,
    # 也使还款生成永不越过 REFERENCE_DATE.
    app_start = REFERENCE_DATE - timedelta(days=int(22 * 30))
    app_end = REFERENCE_DATE - timedelta(days=int(3 * 30))

    records = []
    for i in range(1, n + 1):
        customer_id = random.choices(customer_pool, weights=customer_weights, k=1)[0]
        app_date = fake.date_between(start_date=app_start, end_date=app_end)
        decision_date = app_date + timedelta(days=random.randint(3, 21))

        credit_score = credit_lookup[customer_id]
        is_approved = random.random() < approval_probability(credit_score)
        status_id = approved_status_id if is_approved else rejected_status_id

        if is_approved:
            rejection_reason = None
        elif credit_score >= 680:
            rejection_reason = random.choice(rejection_reasons_by_band["high_credit"])
        elif credit_score >= 600:
            rejection_reason = random.choice(rejection_reasons_by_band["mid_credit"])
        else:
            rejection_reason = random.choice(rejection_reasons_by_band["low_credit"])

        records.append({
            "id": i,
            "application_number": f"APP-{str(i).zfill(6)}",
            "customer_id": customer_id,
            "loan_officer_id": random.choice(officer_ids),
            "requested_amount": random.randint(50, 500) * 1000,
            "requested_term_months": random.choice([12, 24, 36, 48, 60]),
            "application_date": app_date,
            "decision_date": decision_date,
            "status_id": status_id,
            "rejection_reason": rejection_reason,
        })

    return pl.DataFrame(records)


def gen_loans(applications: pl.DataFrame, customers: pl.DataFrame, risk_grades: pl.DataFrame) -> pl.DataFrame:
    """为已批准的申请生成贷款记录.

    状态由"等级 + 复购驱动的违约概率"与"自放款以来经过时间的可行性"共同决定,
    使还款日期始终落在 REFERENCE_DATE 当天或之前. outstanding_balance 直接用最后一期
    已付时点的摊销公式计算.

    会临时加一个私有列 ``_payments_made`` 供 gen_payments 使用, 在导出 TSV 前丢弃.
    """
    is_repeat_lookup = dict(zip(customers["id"].to_list(), customers["is_repeat_customer"].to_list()))
    credit_lookup = dict(zip(customers["id"].to_list(), customers["credit_score"].to_list()))

    grade_rows = list(risk_grades.iter_rows(named=True))

    def grade_for_score(score: int) -> dict:
        for g in grade_rows:
            if g["min_credit_score"] <= score <= g["max_credit_score"]:
                return g
        return grade_rows[-1]

    records = []
    loan_counter = 1
    approved_apps = applications.filter(pl.col("status_id") == 3)

    for row in approved_apps.iter_rows(named=True):
        app_id = row["id"]
        customer_id = row["customer_id"]
        requested_amount = row["requested_amount"]
        requested_term = row["requested_term_months"]
        decision_date = row["decision_date"]

        credit_score = credit_lookup[customer_id]
        is_repeat = is_repeat_lookup[customer_id]

        # 约 15% 的贷款以一个明显低于客户当前信用分的等级入账 (放款后信用分有改善 ——
        # 在 SMB 贷款中常见: 年度重新拉取信用显示按时还款带来的分数提升). 这些贷款在 Q16
        # 中作为再定价候选浮现, 因为 customer.credit_score 是最新值,
        # 而 loan.risk_grade_id 冻结在入账时点.
        score_drift = random.randint(40, 80) if random.random() < 0.15 else 0
        score_at_origination = max(550, credit_score - score_drift)

        grade = grade_for_score(score_at_origination)
        risk_grade_id = grade["id"]
        interest_rate = grade["interest_rate"]

        approved_amount = round(requested_amount * random.uniform(0.9, 1.0), 2)
        term_months = requested_term

        monthly_rate = interest_rate / 100 / 12
        if monthly_rate == 0:
            monthly_payment = approved_amount / term_months
        else:
            monthly_payment = approved_amount * (monthly_rate * (1 + monthly_rate) ** term_months) / \
                              ((1 + monthly_rate) ** term_months - 1)
        monthly_payment = round(monthly_payment, 2)

        disbursement_date = decision_date + timedelta(days=random.randint(3, 10))
        maturity_date = disbursement_date + timedelta(days=term_months * 30)
        months_since_disbursement = max(1, (REFERENCE_DATE - disbursement_date).days // 30)

        # 违约概率由 等级 × 复购状态 驱动.
        base_default = GRADE_FIRSTTIME_DEFAULT_RATE[risk_grade_id]
        default_prob = base_default * (REPEAT_DEFAULT_MULTIPLIER if is_repeat else 1.0)

        will_default = random.random() < default_prob

        if will_default and months_since_disbursement >= 4:
            # 违约已发生. 借款人在停付前还了若干期.
            current_status_id = 7  # DEFAULTED
            max_payments = min(months_since_disbursement - 1, term_months - 1, 15)
            payments_made = random.randint(3, max(3, max_payments))
        elif months_since_disbursement >= term_months:
            # 贷款到期且未违约.
            current_status_id = 8  # PAID_OFF
            payments_made = term_months
        elif not will_default and months_since_disbursement >= 6 and random.random() < EARLY_PAYOFF_PROB:
            # 提前结清 —— 借款人提前还清了贷款.
            current_status_id = 8  # PAID_OFF
            payments_made = months_since_disbursement
        else:
            # 仍在贷 (要么确实正常, 要么最终会违约但尚未发生).
            current_status_id = 6  # CURRENT
            payments_made = months_since_disbursement

        if current_status_id == 8:
            outstanding_balance = 0.0
        else:
            outstanding_balance = amortization_remaining(
                approved_amount, monthly_rate, monthly_payment, payments_made
            )

        # 预先决定这笔违约是否会表现出可观测的预警信号. gen_payments 用它来恶化最后 3 期
        # 还款; gen_default_events 用它来设置 had_early_warning. 把这个决定带在贷款行上,
        # 可以让 gen_payments 和 gen_default_events 不依赖共享的模块状态.
        has_warning = current_status_id == 7 and random.random() < WARNING_RATE

        records.append({
            "id": loan_counter,
            "loan_number": f"LN-{str(loan_counter).zfill(6)}",
            "application_id": app_id,
            "customer_id": customer_id,
            "risk_grade_id": risk_grade_id,
            "approved_amount": approved_amount,
            "interest_rate": interest_rate,
            "term_months": term_months,
            "monthly_payment": monthly_payment,
            "disbursement_date": disbursement_date,
            "maturity_date": maturity_date,
            "current_status_id": current_status_id,
            "outstanding_balance": round(outstanding_balance, 2),
            "_payments_made": payments_made,
            "_has_warning": has_warning,
        })
        loan_counter += 1

    return pl.DataFrame(records)


def gen_repayment_schedules(loans: pl.DataFrame) -> pl.DataFrame:
    """为每笔贷款生成完整的计划月度还款表."""
    records = []
    schedule_id = 1

    for loan_row in loans.iter_rows(named=True):
        loan_id = loan_row["id"]
        approved_amount = loan_row["approved_amount"]
        term_months = loan_row["term_months"]
        monthly_payment = loan_row["monthly_payment"]
        interest_rate = loan_row["interest_rate"]
        disbursement_date = loan_row["disbursement_date"]

        monthly_rate = interest_rate / 100 / 12
        remaining_balance = approved_amount

        for i in range(1, term_months + 1):
            due_date = disbursement_date + timedelta(days=i * 30)
            interest_portion = remaining_balance * monthly_rate
            principal_portion = monthly_payment - interest_portion
            remaining_balance = max(0, remaining_balance - principal_portion)

            records.append({
                "id": schedule_id,
                "loan_id": loan_id,
                "installment_number": i,
                "due_date": due_date,
                "scheduled_payment": round(monthly_payment, 2),
                "principal_portion": round(principal_portion, 2),
                "interest_portion": round(interest_portion, 2),
                "remaining_balance": round(remaining_balance, 2),
            })
            schedule_id += 1

    return pl.DataFrame(records)


def gen_payments(loans: pl.DataFrame, schedules: pl.DataFrame) -> pl.DataFrame:
    """生成实际还款记录.

    对于被标记有预警信号的 DEFAULTED 贷款 (贷款行的 ``_has_warning`` 列, 在 gen_loans
    中预先决定), 违约前最后 3 期还款会恶化 (更多逾期, 更多部分付款) —— 这样 Q4 的
    分析才能真的检测到这一模式.
    """
    records = []
    payment_id = 1
    payment_methods = ["ACH", "Wire Transfer", "Check", "Credit Card"]

    # 按 loan_id 给 schedules 建索引, 实现 O(1) 查找, 避免反复 filter.
    schedules_by_loan: dict[int, list[dict]] = {}
    for s in schedules.iter_rows(named=True):
        schedules_by_loan.setdefault(s["loan_id"], []).append(s)

    for loan_row in loans.iter_rows(named=True):
        loan_id = loan_row["id"]
        monthly_payment = loan_row["monthly_payment"]
        payments_made = loan_row["_payments_made"]
        has_warning = loan_row["_has_warning"]

        loan_schedules = sorted(schedules_by_loan.get(loan_id, []), key=lambda s: s["installment_number"])

        # "最后 3 期"恶化. 当 payments_made=N 且 start=N-2 时,
        # i ∈ {N-2, N-1, N} —— 恰好 3 期.
        deterioration_start = payments_made - 2 if has_warning else payments_made + 1

        for i in range(1, payments_made + 1):
            schedule_row = loan_schedules[i - 1]
            due_date = schedule_row["due_date"]

            in_deterioration_window = i >= deterioration_start

            # 还款时点.
            if in_deterioration_window:
                # 多数逾期, 常常严重逾期.
                late_roll = random.random()
                if late_roll < 0.20:
                    days_late = 0
                elif late_roll < 0.60:
                    days_late = random.randint(8, 20)
                else:
                    days_late = random.randint(20, 30)
            else:
                # 基线: 70% 准时 / 20% 轻微逾期 / 10% 严重逾期.
                late_roll = random.random()
                if late_roll < 0.70:
                    days_late = 0
                elif late_roll < 0.90:
                    days_late = random.randint(1, 15)
                else:
                    days_late = random.randint(16, 30)
            payment_date = due_date + timedelta(days=days_late)

            # 还款金额.
            if in_deterioration_window:
                # 恶化窗口内部分付款很常见.
                if random.random() < 0.45:
                    payment_amount = monthly_payment * random.uniform(0.50, 0.85)
                else:
                    payment_amount = monthly_payment
            else:
                if random.random() < 0.95:
                    payment_amount = monthly_payment
                else:
                    payment_amount = monthly_payment * random.uniform(0.5, 0.9)

            records.append({
                "id": payment_id,
                "loan_id": loan_id,
                "payment_date": payment_date,
                "payment_amount": round(payment_amount, 2),
                "installment_number": i,
                "days_late": days_late,
                "payment_method": random.choice(payment_methods),
            })
            payment_id += 1

    return pl.DataFrame(records)


def gen_default_events(loans: pl.DataFrame, payments: pl.DataFrame, schedules: pl.DataFrame) -> pl.DataFrame:
    """生成违约事件记录.

    had_early_warning 与 warning_signals 由该贷款实际的最后 3 期还款派生 —— 因此标记
    永远不会与数据矛盾, Q4 也能把行为与违约关联起来.

    outstanding_at_default 取自摊销表中最后一期已付时点, 不是凭空写的数字.
    """
    records = []
    event_id = 1

    defaulted_loans = loans.filter(pl.col("current_status_id") == 7)

    # 按贷款给 payments 建索引以便快速查找.
    payments_by_loan: dict[int, list[dict]] = {}
    for p in payments.iter_rows(named=True):
        payments_by_loan.setdefault(p["loan_id"], []).append(p)

    schedules_by_loan: dict[int, list[dict]] = {}
    for s in schedules.iter_rows(named=True):
        schedules_by_loan.setdefault(s["loan_id"], []).append(s)

    for loan_row in defaulted_loans.iter_rows(named=True):
        loan_id = loan_row["id"]
        monthly_payment = loan_row["monthly_payment"]
        outstanding_balance = loan_row["outstanding_balance"]
        term_months = loan_row["term_months"]

        loan_payments = sorted(payments_by_loan.get(loan_id, []), key=lambda p: p["installment_number"])
        if not loan_payments:
            continue

        last_payment = loan_payments[-1]
        last_payment_date = last_payment["payment_date"]
        payments_made = len(loan_payments)

        # 行业标准的 90 DPD 违约宣告: 最后一次漏付的应还日 (即借款人未付的第一个计划应还日)
        # 之后 90 天.
        loan_schedules = sorted(schedules_by_loan.get(loan_id, []), key=lambda s: s["installment_number"])
        if payments_made < len(loan_schedules):
            first_missed_due = loan_schedules[payments_made]["due_date"]
        else:
            first_missed_due = last_payment_date
        default_date = min(first_missed_due + timedelta(days=90), REFERENCE_DATE)

        # installments_missed = 自最后一次还款以来已到期但从未支付的计划期数 (上限为期限).
        months_since_last = max(1, (REFERENCE_DATE - last_payment_date).days // 30)
        installments_missed = min(term_months - payments_made, months_since_last)

        # had_early_warning 是 gen_loans 中预先决定的标记 (带在贷款行的 _has_warning 列上) ——
        # 它决定了哪 72% 的违约会在最后 3 期表现出恶化. warning_signals 随后由实际数据派生;
        # 如果恶化窗口恰好看起来很干净 (随机方差所致), 就退回一个通用描述,
        # 使标记与信号文本永不矛盾.
        had_early_warning = loan_row["_has_warning"]
        if had_early_warning:
            recent = loan_payments[-3:]
            late_count = sum(1 for p in recent if p["days_late"] > 10)
            partial_count = sum(1 for p in recent if p["payment_amount"] < monthly_payment * 0.90)
            signals = []
            if late_count > 0:
                signals.append(f"{late_count} late payments in last 3 months")
            if partial_count > 0:
                signals.append(f"{partial_count} partial payments")
            if not signals:
                signals.append("Account-review notes flagged deteriorating cash flow")
            warning_signals = "; ".join(signals)
        else:
            warning_signals = None

        # 回收率由等级驱动 (更优的借款人 → 更好的回收).
        lo, hi = GRADE_RECOVERY_RANGE[loan_row["risk_grade_id"]]
        recovery_rate = random.uniform(lo, hi)
        recovery_amount = outstanding_balance * recovery_rate
        loss_amount = outstanding_balance - recovery_amount

        records.append({
            "id": event_id,
            "loan_id": loan_id,
            "default_date": default_date,
            "installments_missed": installments_missed,
            "outstanding_at_default": round(outstanding_balance, 2),
            "recovery_amount": round(recovery_amount, 2),
            "loss_amount": round(loss_amount, 2),
            "had_early_warning": had_early_warning,
            "warning_signals": warning_signals,
        })
        event_id += 1

    return pl.DataFrame(records)


# ============================================================================
# 核心函数 (幂等)
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有 TSV 文件. 幂等: 先删除已有文件."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating industry classifications...")
    df_industries = gen_industries()
    df_industries.write_csv(DATA_DIR / "01_industry.tsv", separator="\t")

    print("Generating risk grades...")
    df_risk_grades = gen_risk_grades()
    df_risk_grades.write_csv(DATA_DIR / "02_risk_grade.tsv", separator="\t")

    print("Generating loan statuses...")
    df_statuses = gen_loan_statuses()
    df_statuses.write_csv(DATA_DIR / "03_loan_status.tsv", separator="\t")

    print("Generating loan officers...")
    df_officers = gen_loan_officers()
    df_officers.write_csv(DATA_DIR / "04_loan_officer.tsv", separator="\t")

    print("Generating customers...")
    df_customers = gen_customers(n=800)
    df_customers.write_csv(DATA_DIR / "05_customer.tsv", separator="\t")

    print("Generating applications...")
    df_applications = gen_applications(
        customers=df_customers,
        officer_ids=df_officers["id"].to_list(),
        n=3000,
    )
    df_applications.write_csv(DATA_DIR / "06_application.tsv", separator="\t")

    print("Generating loans...")
    df_loans = gen_loans(df_applications, df_customers, df_risk_grades)

    print("Generating repayment schedules...")
    df_schedules = gen_repayment_schedules(df_loans)
    df_schedules.write_csv(DATA_DIR / "08_repayment_schedule.tsv", separator="\t")

    print("Generating payments...")
    df_payments = gen_payments(df_loans, df_schedules)
    df_payments.write_csv(DATA_DIR / "09_payment.tsv", separator="\t")

    print("Generating default events...")
    df_defaults = gen_default_events(df_loans, df_payments, df_schedules)
    df_defaults.write_csv(DATA_DIR / "10_default_event.tsv", separator="\t")

    # 在持久化 loan 表前, 丢弃仅供生成器使用的私有列.
    df_loans_out = df_loans.drop(["_payments_made", "_has_warning"])
    df_loans_out.write_csv(DATA_DIR / "07_loan.tsv", separator="\t")

    total = (
        len(df_industries) + len(df_risk_grades) + len(df_statuses) + len(df_officers)
        + len(df_customers) + len(df_applications) + len(df_loans_out)
        + len(df_schedules) + len(df_payments) + len(df_defaults)
    )
    print(f"\nGenerated all TSV files in {DATA_DIR}")
    print(f"Total rows: {total}")


def create_sqlite_database() -> None:
    """从 TSV 文件创建 SQLite 数据库. 幂等: 先删除已有数据库."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    print("\nLoading data into SQLite database...")

    load_order = [
        ("01_industry.tsv", "industry"),
        ("02_risk_grade.tsv", "risk_grade"),
        ("03_loan_status.tsv", "loan_status"),
        ("04_loan_officer.tsv", "loan_officer"),
        ("05_customer.tsv", "customer"),
        ("06_application.tsv", "application"),
        ("07_loan.tsv", "loan"),
        ("08_repayment_schedule.tsv", "repayment_schedule"),
        ("09_payment.tsv", "payment"),
        ("10_default_event.tsv", "default_event"),
    ]
    for filename, table in load_order:
        df = pl.read_csv(DATA_DIR / filename, separator="\t")
        df.to_pandas().to_sql(table, engine, if_exists="append", index=False)
        print(f"Loaded {len(df)} rows into {table}")

    print(f"\nCreated SQLite database at {DATABASE_PATH}")


def main() -> None:
    """主入口."""
    print("=" * 80)
    print("Pacific Bridge Lending - SMB Lending Pipeline Data Generator")
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
