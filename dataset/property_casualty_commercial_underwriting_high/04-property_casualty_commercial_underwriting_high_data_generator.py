"""
Property & Casualty - Commercial Underwriting Fake Data Generator (high-complexity edition)

Business background
===================
This dataset simulates "DingAn Commercial Insurance Co., Ltd." (a fictional mid-sized
domestic commercial property/casualty insurer), supporting the build of InsightUnderwriter
- an AI Agent that assists underwriters with commercial-insurance renewal analysis.

The dataset covers 6 business domains across 24 tables, totaling about 115,000 rows:
  Domain 1 - Entities and Organization (7 tables): company, company_financial, company_location, subcontractor,
                                                   underwriter, broker, claim_adjuster
  Domain 2 - Policy and Underwriting (5 tables): policy, policy_coverage, policy_endorsement,
                                                 policy_premium_history, renewal_decision
  Domain 3 - Claims (4 tables): claim, claim_event, claim_communication, claim_reserve
  Domain 4 - Invoices and Payments (2 tables): invoice, payment
  Domain 5 - Risk Assessment (3 tables): risk_assessment, site_inspection, loss_run
  Domain 6 - External References (3 tables): industry_benchmark, regulatory_filing, third_party_report

Reference "today" date: 2026-06-21
History window: 2024-06-21 ~ 2026-06-21 (24 months)
"""

from __future__ import annotations

import random
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl
from faker import Faker
from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index,
    Integer, Numeric, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "property_casualty_commercial_underwriting_high.sqlite"

RANDOM_SEED = 42
TODAY = date(2026, 6, 21)
HISTORY_START = TODAY - timedelta(days=730)  # 24 months

fake = Faker("zh_CN")
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ---- Volume parameters ------------------------------------------------------
N_COMPANIES = 1000
N_UNDERWRITERS = 40   # includes 5 Senior/Manager
N_BROKERS = 60
N_ADJUSTERS = 25

# ---- Business enums (in Chinese) -------------------------------------------
INDUSTRIES = [
    "建筑施工", "制造业", "商业地产", "信息科技", "医疗健康",
    "零售批发", "物流运输", "餐饮酒店", "能源化工", "金融服务",
]

INDUSTRY_BASE_LOSS_RATIO = {  # industry baseline loss ratio (used for loss_run generation)
    "建筑施工": 0.78, "制造业": 0.65, "商业地产": 0.55, "信息科技": 0.42,
    "医疗健康": 0.72, "零售批发": 0.60, "物流运输": 0.70, "餐饮酒店": 0.68,
    "能源化工": 0.82, "金融服务": 0.48,
}

BUSINESS_TYPES = [
    "总承包商", "专业分包商", "商业开发商", "整车制造商", "零部件供应商",
    "批发商", "连锁零售商", "物流服务商", "酒店运营商", "餐饮连锁",
]

RISK_TIERS = ["低风险", "中风险", "高风险", "极高风险"]
RISK_TIER_WEIGHTS = [0.35, 0.40, 0.20, 0.05]

# Risk tier → claim probability (higher risk = more likely to have claims)
RISK_TIER_CLAIM_PROB = {"低风险": 0.42, "中风险": 0.55, "高风险": 0.72, "极高风险": 0.88}
# Risk tier → loss magnitude multiplier (applied to target loss ratio; higher risk = higher LR)
RISK_TIER_LOSS_MULT = {"低风险": 0.80, "中风险": 1.00, "高风险": 1.25, "极高风险": 1.55}
# Risk tier → baseline underwriting risk score (so risk_score correlates positively with risk_tier / loss ratio)
RISK_TIER_SCORE_BASE = {"低风险": 32, "中风险": 50, "高风险": 67, "极高风险": 82}
# Policy-level "earned premium → loss" calibration: inflation factor of reported loss vs. actual paid (paid ≈ reported × pay ratio)
# Used to calibrate the median of single-claim paid / premium to the healthy loss ratio band (about 0.5–0.9)
CLAIMED_LOSS_INFLATION = 1.6

POLICY_TYPES = [
    "商业财产险", "公众责任险", "雇主责任险", "产品责任险",
    "建筑工程一切险", "董事责任险", "营业中断险", "货物运输险",
]

COVERAGE_TYPES = [
    "财产损失", "人身伤害", "第三者责任", "专业责任", "设备故障",
    "营业中断", "环境污染", "网络安全", "诉讼费用", "雇员忠诚",
]

CHINA_CITIES = [
    ("北京", "北京"), ("上海", "上海"), ("广州", "广东"), ("深圳", "广东"),
    ("杭州", "浙江"), ("成都", "四川"), ("重庆", "重庆"), ("武汉", "湖北"),
    ("西安", "陕西"), ("南京", "江苏"), ("苏州", "江苏"), ("天津", "天津"),
    ("青岛", "山东"), ("宁波", "浙江"), ("长沙", "湖南"), ("郑州", "河南"),
    ("沈阳", "辽宁"), ("大连", "辽宁"), ("厦门", "福建"), ("无锡", "江苏"),
]

REGULATORY_AGENCIES = [
    ("应急管理部", "安全生产违规"),
    ("生态环境部", "环境保护违规"),
    ("国家市场监督管理总局", "产品质量违规"),
    ("国家消防救援局", "消防安全违规"),
    ("国家金融监督管理总局", "金融合规违规"),
    ("国家税务总局", "税务违规"),
    ("人力资源社会保障部", "劳动用工违规"),
]

CREDIT_RATING_AGENCIES = ["中诚信国际", "大公国际", "联合资信", "东方金诚"]
CREDIT_RATINGS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB", "BB", "B", "CCC"]
CREDIT_RATING_WEIGHTS = [0.05, 0.10, 0.15, 0.15, 0.15, 0.12, 0.10, 0.08, 0.05, 0.03, 0.02]

SUBCONTRACTOR_SPECIALTIES = [
    "电气安装", "管道", "暖通空调", "屋面工程", "混凝土",
    "钢结构", "拆除", "幕墙", "防水", "装饰装修",
]

UNDERWRITER_ROLES = ["核保经理", "高级核保员", "核保员", "初级核保员"]
UNDERWRITER_ROLE_QUOTAS = {"核保经理": 0, "高级核保员": 8, "核保员": 5, "初级核保员": 3}  # monthly quota (policies)

BROKER_FIRMS = [
    "怡安(中国)保险经纪", "韦莱韬悦保险经纪", "达信(中国)保险经纪",
    "明亚保险经纪", "华泰保险经纪", "江泰保险经纪", "联合保险经纪",
    "北京中怡保险经纪", "众和保险经纪", "永达理保险经纪",
]

# ============================================================================
# Claim communication template library (RAG data source)
# Each template format: (signal_tag, sub_tag, content)
# signal_tag is used for labeling to aid AI Agent RAG / classification training
# ============================================================================

CLAIM_COMM_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    # Normal-cooperative (about 45%)
    "normal_cooperative": [
        ("初次接洽顺利",
         "已与投保人电话初次接洽,对方配合度良好,主动提供了事故现场照片、监控录像及目击者联系方式。"
         "约定下周二上门核损,预计可在 15 个工作日内完成定损。"),
        ("文件齐备",
         "投保人按要求提交了全部理赔材料: 事故说明、损失清单、维修报价单、营业执照副本及发票。"
         "材料齐全规范,无需补充。建议进入定损环节。"),
        ("现场配合度高",
         "现场核查时,企业安全主管全程陪同,详细解答了事故经过。"
         "管理记录完整,事故应急处置规范。整体配合度评价: 优。"),
        ("定损达成共识",
         "与投保人就维修方案及金额初步达成一致。修复费用 28 万元(不含税),"
         "由原设备厂商负责更换损坏部件,预计停产时间 10 天,营业中断损失另行核算。"),
        ("及时通知赔付",
         "已电话通知投保人理算结果,对方表示理解和接受。"
         "无异议,可按调解方案在 5 个工作日内完成赔款支付。"),
        ("修复进度正常",
         "现场回访显示设备维修工作进展正常,预计本月底前可恢复生产。"
         "投保人未提出新增损失,各方对赔付方案无异议。"),
        ("结案归档",
         "本案已完成全部赔付手续,投保人签收赔款收据。"
         "案件证据完整、流程规范,无后续争议风险。已建议结案归档。"),
        ("理赔记录良好",
         "查阅历史记录,该企业过去 3 年共发生 2 起小额赔案,均按时和谐结案,无诉讼记录。"
         "本次事故性质与既往相符,无异常风险信号。"),
        ("配合调查到位",
         "投保人主动配合配合公估机构上门勘查,提供了完整的设备运行日志和维护记录。"
         "数据真实可信,事故起因清晰: 设备老化导致的非人为损失。"),
        ("快速理赔通过",
         "属于简易快赔范围(损失金额 < 5 万元,事实清楚)。"
         "材料审核通过,3 个工作日内可完成赔付,符合公司服务承诺。"),
    ],
    # Investigation notes (about 20%) - describing the investigation process
    "investigation_note": [
        ("现场勘查报告",
         "完成事故现场实地勘查,共拍摄照片 47 张,绘制现场示意图 2 份。"
         "现场已部分清理,但关键证据(损坏设备、起火点周边构件)保存完整。"),
        ("目击者询问",
         "走访目击者 5 名,询问笔录均已制作并签字确认。"
         "证词在事故发生时间、起因方面基本一致,在具体细节上存在合理差异。"),
        ("监控录像调取",
         "已从企业内部监控系统调取事发当日 24 小时录像。"
         "录像清晰显示事故发生经过,与投保人陈述完全吻合。已刻录光盘归档。"),
        ("第三方公估介入",
         "因损失金额较大(超过 50 万元),已委托上海方策公估公司联合调查。"
         "公估师下周到场,预计 30 个工作日内出具正式公估报告。"),
        ("消防部门定性",
         "已获取消防部门出具的《火灾事故认定书》,认定起火原因为电气线路短路,"
         "属于意外事故,投保人无重大过错。该认定支持本次赔付。"),
        ("医疗费用审核",
         "雇员伤情已委托医学顾问审核,治疗方案合理,费用清单与三甲医院收费标准一致。"
         "无过度治疗或费用虚高情形。"),
        ("损失清单复核",
         "对投保人提交的损失清单逐项复核,共核减项目 8 项,金额 12.3 万元。"
         "主要为重复计算和原值高估。已与投保人沟通确认,无异议。"),
        ("调查阶段性总结",
         "调查工作已完成 70%,核心事实已经查清,剩余工作主要是损失定量。"
         "预计未来 2 周内可完成全部定损,进入理算环节。"),
    ],
    # Fraud signal (about 10%) - high-value unstructured signal
    "fraud_signal": [
        ("陈述前后矛盾",
         "投保人在不同时间对事故经过的陈述存在多处矛盾: "
         "首次报案时称凌晨 2 点发现火情,但监控显示报警时间为凌晨 4:30。"
         "事故起因从最初的'电气故障'改为'外部纵火'。建议加强调查。"),
        ("理赔金额畸高",
         "申报损失金额 280 万元,而同类企业近 3 年平均赔案金额为 45 万元。"
         "维修报价单来自非投保人指定的关联公司,价格较市场均价高 60%。"
         "建议委托独立公估,审慎理算。"),
        ("历史可疑赔案",
         "经查询行业理赔信息平台,该企业法人代表名下另一家公司"
         "曾在 2023 年向其他承保人申报相似性质的火灾事故,获赔 180 万元。"
         "时间间隔较短,事故模式高度相似,存在道德风险信号。"),
        ("保单期初紧贴出险",
         "保单生效日 2025-09-01,事故发生日 2025-10-15,出险时间紧贴保单生效期(45 天)。"
         "投保前 6 个月内被保险标的曾被另一家保险公司拒保。"
         "建议详查投保前历史。"),
        ("供应商资质存疑",
         "维修发票开票方为一家成立不足 6 个月的小微公司,无固定经营场所,"
         "营业执照范围与所开发票内容(机电设备维修)不完全匹配。"
         "建议要求投保人补充提供供应商工程资质和实际维修记录。"),
        ("无报警无第三方记录",
         "重大事故(损失 > 100 万元)但投保人未及时报警,也未通知消防或应急部门,"
         "缺少独立第三方记录。仅靠投保人单方面陈述和内部监控,证据链脆弱。"
         "已转交反欺诈调查部门联合处理。"),
    ],
    # Dispute escalation (about 10%)
    "dispute_escalation": [
        ("责任认定争议",
         "投保人就事故责任认定提出异议,认为我司认定的'重大过错'不成立,"
         "要求按 100% 赔付而非按 70% 部分赔付。已上报理赔部主管复议。"),
        ("条款适用分歧",
         "争议焦点在于本次损失是否属于'间接损失'除外责任。"
         "投保人主张属于'连带的营业中断损失',要求全额赔付。"
         "已请法务部出具条款适用意见。"),
        ("定损金额拒不接受",
         "投保人对定损金额 35 万元拒不接受,坚持索赔 78 万元。"
         "双方差距过大,谈判陷入僵局。建议委托第三方独立公估出具仲裁意见。"),
        ("申诉至监管机构",
         "投保人已就本案向当地银保监分局投诉,称我司理赔流程拖延、"
         "定损不公。监管已下发问询函,需 10 日内书面回复。请合规部介入。"),
        ("拒赔决定拟出",
         "经调查确认本次事故属于保单除外责任(故意行为导致),"
         "拟出具《拒赔通知书》。投保人已表达强烈不满,扬言诉讼。"
         "请法务部审核拒赔依据。"),
    ],
    # Attorney involvement (about 5%) - the most serious disputes
    "attorney_involvement": [
        ("律师函送达",
         "投保人委托北京 XX 律师事务所发来正式《索赔律师函》,要求 15 日内全额赔付,"
         "否则将提起诉讼。函中引用了《保险法》第 30 条疑义利益解释原则。"
         "已转交我司法务部应对。"),
        ("诉讼立案通知",
         "收到法院《应诉通知书》: 投保人正式起诉我司,案由保险合同纠纷,"
         "诉讼标的额 156 万元。第一次开庭定于 2026-08-15。"
         "我司外聘律师已介入,正在准备答辩状和证据材料。"),
        ("调解程序启动",
         "经法院引导,双方同意进入诉前调解程序。"
         "调解员建议在 80 万元至 110 万元区间寻求和解。"
         "需经理赔委员会审批和解授权额度。"),
        ("仲裁裁决执行",
         "中国国际经济贸易仲裁委员会就本案作出裁决,"
         "裁定我司支付赔款 95 万元 + 利息 8 万元,共计 103 万元。"
         "我司在仲裁中败诉,已启动赔付流程。请财务部安排资金。"),
    ],
    # Settlement negotiation (about 10%)
    "settlement_negotiation": [
        ("初次和解报价",
         "向投保人提出和解方案: 一次性赔付 65 万元,投保人放弃后续追索权。"
         "对方表示需要内部研究,3 个工作日内答复。"),
        ("反报价",
         "投保人就上次和解报价提出反报价,要求一次性赔付 95 万元。"
         "差距 30 万元。我司可接受上限为 80 万元(已请示理赔总监授权)。"
         "下周三再次会谈。"),
        ("分期支付方案",
         "经多轮谈判,双方就 72 万元和解金额达成口头一致,"
         "改为分 3 期支付: 首期 40 万元(签约后 7 日)、二期 20 万元(60 日)、三期 12 万元(120 日)。"
         "起草和解协议中。"),
        ("和解协议签署",
         "双方正式签署《一次性了结协议书》,我司一次性赔付 68 万元,"
         "投保人撤回诉讼并出具完整《免责声明》,本案终结。"
         "请档案部归档保存,标记为'已和解结案'。"),
        ("和解失败转诉讼",
         "三轮谈判后仍无法达成和解,投保人决定继续诉讼。"
         "请法务部按既定诉讼策略推进,同时准备好和解的备选方案,以备法院调解阶段使用。"),
    ],
}

# Per-category probability distribution
COMM_CATEGORY_WEIGHTS = {
    "normal_cooperative": 0.45,
    "investigation_note": 0.20,
    "fraud_signal": 0.10,
    "dispute_escalation": 0.10,
    "attorney_involvement": 0.05,
    "settlement_negotiation": 0.10,
}


# ============================================================================
# SQLAlchemy ORM models (24 tables)
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


# ---------- Domain 1: Entities and Organization ----------
class Underwriter(Base):
    """Underwriter profile. manager_id is a self-referencing FK encoding team hierarchy."""
    __tablename__ = "underwriter"
    underwriter_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)       # Underwriting Manager / Senior Underwriter / Underwriter / Junior Underwriter
    specialty_industry: Mapped[str] = mapped_column(String(40), nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)     # North / East / South / West / Central China
    manager_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"))
    monthly_quota_policies: Mapped[int] = mapped_column(Integer, nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Broker(Base):
    """Insurance broker / intermediary. Most commercial insurance flows through brokers."""
    __tablename__ = "broker"
    broker_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_firm: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(40), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    license_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False)     # 0.05 ~ 0.20
    tier: Mapped[str] = mapped_column(String(20), nullable=False)              # Strategic Partner / Important Partner / General Partner
    onboarded_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClaimAdjuster(Base):
    """Claim adjuster / loss assessor profile"""
    __tablename__ = "claim_adjuster"
    adjuster_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    specialty_claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    case_load_capacity: Mapped[int] = mapped_column(Integer, nullable=False)   # max number of cases handled in parallel
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)


class Company(Base):
    """Insured company master"""
    __tablename__ = "company"
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unified_social_credit_code: Mapped[str] = mapped_column(String(18), nullable=False, unique=True)  # Unified Social Credit Code
    industry: Mapped[str] = mapped_column(String(40), nullable=False)
    founded_year: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    business_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # Reconciled fields
    total_active_premium_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    total_paid_claims_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CompanyFinancial(Base):
    """Company historical financials"""
    __tablename__ = "company_financial"
    financial_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_cny: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    total_assets_cny: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    total_liabilities_cny: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    debt_to_equity_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    net_profit_cny: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CompanyLocation(Base):
    """Company operating location (the subject of property insurance)"""
    __tablename__ = "company_location"
    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    location_name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False)
    province: Mapped[str] = mapped_column(String(40), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    property_value_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    location_risk_level: Mapped[str] = mapped_column(String(20), nullable=False)    # Low / Medium / High
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Subcontractor(Base):
    """Subcontractors used by a company (relevant for construction all-risk insurance)"""
    __tablename__ = "subcontractor"
    subcontractor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    subcontractor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialty: Mapped[str] = mapped_column(String(40), nullable=False)
    has_claims_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100


# ---------- Domain 2: Policy and Underwriting ----------
class Policy(Base):
    """Policy master"""
    __tablename__ = "policy"
    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    underwriter_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"), nullable=False)
    broker_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("broker.broker_id"))  # 15% direct (NULL)
    policy_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    policy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_annual_premium_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_annual_premium_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)  # reconciled: from the latest row of premium_history
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # In-force / Expired / Cancelled
    bound_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        Index("idx_policy_company", "company_id"),
        Index("idx_policy_underwriter", "underwriter_id"),
        Index("idx_policy_status", "status"),
    )


class PolicyCoverage(Base):
    """Policy coverage detail (one policy can have multiple coverages)"""
    __tablename__ = "policy_coverage"
    coverage_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    coverage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage_limit_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    deductible_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class PolicyEndorsement(Base):
    """Policy endorsement record (mid-term changes: add/cancel coverage, change of terms)"""
    __tablename__ = "policy_endorsement"
    endorsement_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    endorsement_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    premium_adjustment_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class PolicyPremiumHistory(Base):
    """Premium-rate change time-snapshot table

    Every premium adjustment (initial bind, endorsement) generates one row, recording the
    before/after premium and the reason.
    Supports "premium slippage" analysis to identify high-risk policies that are repriced frequently.
    """
    __tablename__ = "policy_premium_history"
    premium_history_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    change_event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # Initial Bind / Endorsement
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    previous_premium_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    new_premium_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    change_amount_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    __table_args__ = (
        Index("idx_premium_history_policy", "policy_id"),
        Index("idx_premium_history_changed", "changed_at"),
    )


class RenewalDecision(Base):
    """Historical renewal decision record"""
    __tablename__ = "renewal_decision"
    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    underwriter_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"), nullable=False)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)  # Renew / Conditional Renew / Decline
    premium_change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    underwriter_notes: Mapped[str | None] = mapped_column(Text)


# ---------- Domain 3: Claims ----------
class Claim(Base):
    """Claim master"""
    __tablename__ = "claim"
    claim_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    adjuster_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim_adjuster.adjuster_id"), nullable=False)
    claim_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    loss_amount_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    paid_amount_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # Filed / Investigating / Adjusting / Paid / Closed / Declined
    __table_args__ = (
        Index("idx_claim_policy", "policy_id"),
        Index("idx_claim_status", "status"),
        Index("idx_claim_incident_date", "incident_date"),
    )


class ClaimEvent(Base):
    """Claim event timeline (status changes such as reporting / acceptance / investigation / assessment / payment / close)"""
    __tablename__ = "claim_event"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim.claim_id"), nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_description: Mapped[str | None] = mapped_column(Text)


class ClaimCommunication(Base):
    """Unstructured communications during the claims process (emails / phone notes / investigation notes)

    This is the main data source for the InsightUnderwriter RAG:
    via the signal_tag field for category labels, used to train fraud-detection, dispute early-warning, and similar models.
    XOR constraint: author_underwriter_id and author_adjuster_id must have exactly one non-null.
    """
    __tablename__ = "claim_communication"
    comm_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim.claim_id"), nullable=False)
    author_underwriter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"))
    author_adjuster_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("claim_adjuster.adjuster_id"))
    comm_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    communication_type: Mapped[str] = mapped_column(String(30), nullable=False)  # Email / Phone / Investigation Notes / On-site Report
    signal_tag: Mapped[str] = mapped_column(String(40), nullable=False)            # category label
    sub_tag: Mapped[str] = mapped_column(String(60), nullable=False)               # sub-category label
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # XOR constraint: exactly one of author_underwriter_id and author_adjuster_id non-null (consistent with ER section 14 DDL)
    __table_args__ = (
        CheckConstraint(
            "(author_underwriter_id IS NULL) <> (author_adjuster_id IS NULL)",
            name="ck_claim_communication_author_xor",
        ),
        Index("idx_comm_claim", "claim_id"),
        Index("idx_comm_signal_tag", "signal_tag"),
    )


class ClaimReserve(Base):
    """Claim reserve set-up and adjustment history"""
    __tablename__ = "claim_reserve"
    reserve_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim.claim_id"), nullable=False)
    reserve_date: Mapped[date] = mapped_column(Date, nullable=False)
    reserve_amount_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    adjustment_reason: Mapped[str | None] = mapped_column(Text)


# ---------- Domain 4: Invoices and Payments ----------
class Invoice(Base):
    """Premium invoice"""
    __tablename__ = "invoice"
    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # Paid / Overdue / Pending
    __table_args__ = (Index("idx_invoice_policy", "policy_id"),)


class Payment(Base):
    """Actual payment record"""
    __tablename__ = "payment"
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoice.invoice_id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paid_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    days_late: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (Index("idx_payment_invoice", "invoice_id"),)


# ---------- Domain 5: Risk Assessment ----------
class RiskAssessment(Base):
    """Risk score (the underwriter's risk score for a policy)"""
    __tablename__ = "risk_assessment"
    assessment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    underwriter_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"), nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100, higher = more risky
    underwriter_notes: Mapped[str | None] = mapped_column(Text)


class SiteInspection(Base):
    """On-site inspection record"""
    __tablename__ = "site_inspection"
    inspection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("company_location.location_id"), nullable=False)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False)
    inspector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    hazards_identified: Mapped[str | None] = mapped_column(Text)
    remediation_status: Mapped[str] = mapped_column(String(20), nullable=False)  # Completed / In Progress / Not Started / No Remediation Needed


class LossRun(Base):
    """Loss-ratio statistics aggregated by company × year × line of business (loss run report)"""
    __tablename__ = "loss_run"
    loss_run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    total_premium_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    total_losses_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    loss_ratio: Mapped[float] = mapped_column(Float, nullable=False)  # reconciled: total_losses / total_premium
    claim_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (Index("idx_loss_run_company_year", "company_id", "year"),)


# ---------- Domain 6: External References ----------
class IndustryBenchmark(Base):
    """Industry benchmark data"""
    __tablename__ = "industry_benchmark"
    benchmark_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry: Mapped[str] = mapped_column(String(40), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_loss_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    avg_claim_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    avg_premium_range_low_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    avg_premium_range_high_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class RegulatoryFiling(Base):
    """Regulatory penalty record (from external regulator data)"""
    __tablename__ = "regulatory_filing"
    filing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    agency: Mapped[str] = mapped_column(String(40), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    fine_amount_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False)  # Closed / In Progress / Under Appeal


class ThirdPartyReport(Base):
    """Third-party credit-rating report"""
    __tablename__ = "third_party_report"
    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_rating: Mapped[str] = mapped_column(String(10), nullable=False)
    rating_change: Mapped[str] = mapped_column(String(20), nullable=False)   # Upgrade / Downgrade / Affirm
    report_source: Mapped[str] = mapped_column(String(40), nullable=False)


# ============================================================================
# Helper functions
# ============================================================================
def weighted_choice(options: list, weights: list[float]):
    return random.choices(options, weights=weights, k=1)[0]


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def random_datetime(start: date, end: date) -> datetime:
    d = random_date(start, end)
    return datetime.combine(d, datetime.min.time()) + timedelta(
        hours=random.randint(8, 19), minutes=random.randint(0, 59)
    )


def gen_uscc() -> str:
    """Generate an 18-character Unified Social Credit Code (illustrative; checksum digit not guaranteed valid)"""
    digits = "0123456789"
    letters = "ABCDEFGHJKLMNPQRTUWXY"
    return (
        "91"
        + "".join(random.choices(digits + letters, k=6))
        + "".join(random.choices(digits + letters, k=9))
        + random.choice(digits + letters)
    )


# ============================================================================
# Data generators
# ============================================================================

def gen_underwriters() -> pl.DataFrame:
    """Generate underwriters: 5 managers + 35 underwriters (40 total)"""
    regions = ["华北", "华东", "华南", "华西", "华中"]
    records = []
    # 5 managers - one per region
    for i in range(1, 6):
        records.append({
            "underwriter_id": i,
            "full_name": fake.name(),
            "email": f"manager{i}@dingan-insurance.com",
            "role": "核保经理",
            "specialty_industry": random.choice(INDUSTRIES),
            "years_of_experience": random.randint(12, 25),
            "region": regions[i - 1],
            "manager_id": None,
            "monthly_quota_policies": UNDERWRITER_ROLE_QUOTAS["核保经理"],
            "hire_date": random_date(date(2010, 1, 1), date(2018, 12, 31)),
            "is_active": True,
        })
    # 35 underwriters - assigned to managers, with 8 Senior / 20 regular / 7 Junior
    role_assignments = ["高级核保员"] * 8 + ["核保员"] * 20 + ["初级核保员"] * 7
    random.shuffle(role_assignments)
    for idx, role in enumerate(role_assignments):
        uid = idx + 6
        region = random.choice(regions)
        manager_id = next(i for i in range(1, 6) if regions[i - 1] == region)
        exp_map = {"高级核保员": (7, 15), "核保员": (3, 8), "初级核保员": (0, 3)}
        exp_low, exp_high = exp_map[role]
        records.append({
            "underwriter_id": uid,
            "full_name": fake.name(),
            "email": f"uw{uid:03d}@dingan-insurance.com",
            "role": role,
            "specialty_industry": random.choice(INDUSTRIES),
            "years_of_experience": random.randint(exp_low, exp_high),
            "region": region,
            "manager_id": manager_id,
            "monthly_quota_policies": UNDERWRITER_ROLE_QUOTAS[role],
            "hire_date": random_date(date(2015, 1, 1), date(2025, 12, 31)),
            "is_active": random.random() > 0.05,
        })
    return pl.DataFrame(records)


def gen_brokers() -> pl.DataFrame:
    records = []
    tier_pool = ["战略合作"] * 5 + ["重要合作"] * 20 + ["一般合作"] * 35
    random.shuffle(tier_pool)
    for i in range(1, N_BROKERS + 1):
        firm = random.choice(BROKER_FIRMS) + (f" {fake.city_suffix()}分公司" if random.random() < 0.4 else "")
        records.append({
            "broker_id": i,
            "broker_firm": firm,
            "contact_name": fake.name(),
            "contact_email": f"broker{i:03d}@{fake.domain_word()}.com.cn",
            "license_number": f"BJ{random.randint(100000, 999999)}",
            "commission_rate": round(random.uniform(0.05, 0.20), 3),
            "tier": tier_pool[i - 1],
            "onboarded_date": random_date(date(2015, 1, 1), date(2024, 12, 31)),
            "is_active": random.random() > 0.05,
        })
    return pl.DataFrame(records)


def gen_adjusters() -> pl.DataFrame:
    specialties = ["财产损失", "人身伤害", "营业中断", "工程损失", "复杂理赔"]
    regions = ["华北", "华东", "华南", "华西", "华中"]
    records = []
    for i in range(1, N_ADJUSTERS + 1):
        records.append({
            "adjuster_id": i,
            "full_name": fake.name(),
            "email": f"adj{i:03d}@dingan-insurance.com",
            "specialty_claim_type": random.choice(specialties),
            "years_of_experience": random.randint(2, 18),
            "region": random.choice(regions),
            "case_load_capacity": random.randint(15, 35),
            "hire_date": random_date(date(2014, 1, 1), date(2024, 12, 31)),
        })
    return pl.DataFrame(records)


def gen_companies() -> pl.DataFrame:
    records = []
    used_names = set()
    for i in range(1, N_COMPANIES + 1):
        # ensure company name uniqueness
        for _ in range(10):
            name = fake.company()
            if name not in used_names:
                used_names.add(name)
                break
        founded_year = random.randint(1985, 2022)
        # client onboarding cannot be earlier than the founding year, nor earlier than DingAn's system launch (2020)
        created_floor = date(max(founded_year, 2020), 1, 1)
        records.append({
            "company_id": i,
            "company_name": name,
            "unified_social_credit_code": gen_uscc(),
            "industry": random.choice(INDUSTRIES),
            "founded_year": founded_year,
            "employee_count": random.randint(20, 8000),
            "business_type": random.choice(BUSINESS_TYPES),
            "risk_tier": weighted_choice(RISK_TIERS, RISK_TIER_WEIGHTS),
            "total_active_premium_cny": 0.0,  # filled in later during reconciliation
            "total_paid_claims_cny": 0.0,      # filled in later during reconciliation
            "created_at": random_datetime(created_floor, TODAY),
        })
    return pl.DataFrame(records)


def gen_company_financials(company_ids: list[int]) -> pl.DataFrame:
    records = []
    fid = 1
    for cid in company_ids:
        # base_revenue = latest-year (2025) revenue; each company has a stable YoY growth rate "growth"
        base_revenue = random.uniform(5_000_000, 500_000_000)
        growth = random.uniform(-0.10, 0.25)
        for year_offset in range(random.randint(3, 5)):
            fiscal_year = 2025 - year_offset
            # larger year_offset = older year; older-year revenue = latest revenue / (1+growth)^offset
            # => when growth>0 revenue increases over time (newer = higher), when growth<0 it decreases - matches real trends
            revenue = base_revenue / ((1 + growth) ** year_offset)
            assets = revenue * random.uniform(1.2, 3.0)
            liab = assets * random.uniform(0.3, 0.8)
            equity = max(assets - liab, 1)
            net_profit = revenue * random.uniform(-0.05, 0.15)
            records.append({
                "financial_id": fid,
                "company_id": cid,
                "fiscal_year": fiscal_year,
                "revenue_cny": round(revenue, 2),
                "total_assets_cny": round(assets, 2),
                "total_liabilities_cny": round(liab, 2),
                "debt_to_equity_ratio": round(liab / equity, 3),
                "net_profit_cny": round(net_profit, 2),
                "reported_at": datetime(fiscal_year + 1, random.randint(3, 5), random.randint(1, 28)),
            })
            fid += 1
    return pl.DataFrame(records)


def gen_company_locations(company_ids: list[int]) -> pl.DataFrame:
    records = []
    lid = 1
    risk_levels = ["低", "中", "高"]
    location_kinds = ["办公楼", "厂房", "仓库", "门店", "研发中心"]
    for cid in company_ids:
        n_loc = random.randint(1, 4)
        for j in range(n_loc):
            city, province = random.choice(CHINA_CITIES)
            records.append({
                "location_id": lid,
                "company_id": cid,
                "location_name": f"{city}{random.choice(location_kinds)}",
                "address": fake.street_address(),
                "city": city,
                "province": province,
                "postal_code": fake.postcode(),
                "property_value_cny": round(random.uniform(1_000_000, 80_000_000), 2),
                "location_risk_level": weighted_choice(risk_levels, [0.5, 0.35, 0.15]),
                "is_primary": j == 0,
            })
            lid += 1
    return pl.DataFrame(records)


def gen_subcontractors(company_ids: list[int]) -> pl.DataFrame:
    records = []
    sid = 1
    for cid in company_ids:
        if random.random() < 0.30:  # 30% of companies have subcontractors
            for _ in range(random.randint(1, 5)):
                records.append({
                    "subcontractor_id": sid,
                    "company_id": cid,
                    "subcontractor_name": fake.company(),
                    "specialty": random.choice(SUBCONTRACTOR_SPECIALTIES),
                    "has_claims_history": random.random() < 0.30,
                    "safety_score": random.randint(40, 100),
                })
                sid += 1
    return pl.DataFrame(records)


def gen_policies(companies: pl.DataFrame, underwriter_ids: list[int]) -> pl.DataFrame:
    """Each company gets 1-5 policies (including historical). Total target ~2500 policies."""
    records = []
    pid = 1
    risk_premium_mult = {"低风险": 0.8, "中风险": 1.0, "高风险": 1.4, "极高风险": 1.9}
    for row in companies.iter_rows(named=True):
        cid = row["company_id"]
        n_policies = random.choices([1, 2, 3, 4, 5], weights=[0.10, 0.20, 0.30, 0.25, 0.15])[0]
        for _ in range(n_policies):
            eff_date = random_date(HISTORY_START, TODAY - timedelta(days=30))
            exp_date = eff_date + timedelta(days=365)
            base_premium = random.uniform(30_000, 800_000) * risk_premium_mult[row["risk_tier"]]
            # Status determined by whether the policy has already expired: expired → Expired (~85%) / Cancelled (~15%);
            # not expired → In-force (~95%) / Cancelled (~5%). Measured overall: about In-force 44% / Expired 45% / Cancelled 10%.
            if exp_date < TODAY:
                status = weighted_choice(["已到期", "已注销"], [0.85, 0.15])
            else:
                status = weighted_choice(["有效", "已注销"], [0.95, 0.05])
            records.append({
                "policy_id": pid,
                "company_id": cid,
                "underwriter_id": random.choice(underwriter_ids),
                "broker_id": random.choice(range(1, N_BROKERS + 1)) if random.random() > 0.15 else None,
                "policy_number": f"DA-{eff_date.year}-{pid:06d}",
                "policy_type": random.choice(POLICY_TYPES),
                "effective_date": eff_date,
                "expiration_date": exp_date,
                "initial_annual_premium_cny": round(base_premium, 2),
                "current_annual_premium_cny": round(base_premium, 2),  # reconciled later
                "status": status,
                "bound_at": datetime.combine(eff_date - timedelta(days=random.randint(7, 30)), datetime.min.time()),
            })
            pid += 1
    return pl.DataFrame(records)


def gen_policy_coverages(policy_ids: list[int]) -> pl.DataFrame:
    records = []
    cid = 1
    for pid in policy_ids:
        n_cov = random.randint(1, 4)
        chosen = random.sample(COVERAGE_TYPES, k=n_cov)
        for ct in chosen:
            records.append({
                "coverage_id": cid,
                "policy_id": pid,
                "coverage_type": ct,
                "coverage_limit_cny": round(random.uniform(500_000, 50_000_000), 2),
                "deductible_cny": round(random.uniform(5_000, 200_000), 2),
            })
            cid += 1
    return pl.DataFrame(records)


def gen_policy_endorsements(policy_ids: list[int]) -> pl.DataFrame:
    records = []
    eid = 1
    reasons = ["承保范围扩展", "保费调整", "标的地址变更", "增加除外责任", "免赔额调整", "受益人变更"]
    for pid in policy_ids:
        if random.random() < 0.55:
            for _ in range(random.randint(1, 3)):
                records.append({
                    "endorsement_id": eid,
                    "policy_id": pid,
                    "endorsement_date": random_date(HISTORY_START, TODAY),
                    "reason": random.choice(reasons),
                    "change_description": fake.sentence(nb_words=15),
                    "premium_adjustment_cny": round(random.uniform(-30_000, 80_000), 2),
                })
                eid += 1
    return pl.DataFrame(records)


def gen_policy_premium_history(
    policies: pl.DataFrame, endorsements: pl.DataFrame
) -> pl.DataFrame:
    """For each policy, generate a premium time-snapshot: initial bind (1 row) + one "endorsement" row per endorsement.

    Note: this dataset models "renewal = new policy" (see renewal_decision), so premium_history
    only contains the two event types Initial Bind / Endorsement, with no "Renewal" rows generated (consistent with the ER 9.12 enum).
    """
    records = []
    hid = 1
    endo_by_policy: dict[int, list[dict]] = {}
    for r in endorsements.iter_rows(named=True):
        endo_by_policy.setdefault(r["policy_id"], []).append(r)

    for p in policies.iter_rows(named=True):
        pid = p["policy_id"]
        # 1. Initial Bind event
        records.append({
            "premium_history_id": hid,
            "policy_id": pid,
            "change_event_type": "初承",
            "changed_at": p["bound_at"],
            "previous_premium_cny": 0.0,
            "new_premium_cny": p["initial_annual_premium_cny"],
            "change_amount_cny": p["initial_annual_premium_cny"],
            "change_pct": 0.0,
            "change_reason": "新保单初次承保",
        })
        hid += 1
        current_premium = p["initial_annual_premium_cny"]
        # 2. One adjustment per endorsement
        for e in sorted(endo_by_policy.get(pid, []), key=lambda x: x["endorsement_date"]):
            adj = float(e["premium_adjustment_cny"])
            new_p = max(current_premium + adj, 1000)
            pct = (new_p - current_premium) / current_premium * 100
            records.append({
                "premium_history_id": hid,
                "policy_id": pid,
                "change_event_type": "批改",
                "changed_at": datetime.combine(e["endorsement_date"], datetime.min.time()),
                "previous_premium_cny": round(current_premium, 2),
                "new_premium_cny": round(new_p, 2),
                "change_amount_cny": round(adj, 2),
                "change_pct": round(pct, 3),
                "change_reason": e["reason"],
            })
            hid += 1
            current_premium = new_p
    return pl.DataFrame(records)


def gen_renewal_decisions(
    policies: pl.DataFrame, underwriter_ids: list[int]
) -> pl.DataFrame:
    records = []
    did = 1
    decisions = ["续保", "有条件续保", "拒保"]
    decision_weights = [0.65, 0.25, 0.10]
    note_templates = [
        "赔付率改善,同意续保,保费上调 {pct}%",
        "存在多起未结理赔,要求增加安全条件后方可续保",
        "近期赔付率显著恶化,综合考虑后拒绝续保",
        "财务状况良好,保费维持现有水平续保",
        "因监管处罚记录,需提供整改证明方可续保",
        "经纪人积极沟通,在原条款基础上小幅上调续保",
    ]
    for p in policies.iter_rows(named=True):
        # Expired policies most likely have a renewal-decision record
        if p["expiration_date"] < TODAY and random.random() < 0.70:
            decision = weighted_choice(decisions, decision_weights)
            premium_change = random.uniform(-15.0, 35.0) if decision != "拒保" else 0.0
            note = random.choice(note_templates).format(pct=round(premium_change, 1))
            # Keep the same random-call order as the original implementation (underwriter_id first, then decision_date),
            # to avoid pointless RNG-stream shifts; this change really just caps the decision date at "today".
            underwriter_id = random.choice(underwriter_ids)
            # Cap the decision date at "today" (fix for Review-04: decision_date could be after TODAY)
            decision_date = min(
                p["expiration_date"] + timedelta(days=random.randint(-30, 30)), TODAY
            )
            records.append({
                "decision_id": did,
                "policy_id": p["policy_id"],
                "underwriter_id": underwriter_id,
                "decision_date": decision_date,
                "decision": decision,
                "premium_change_pct": round(premium_change, 2),
                "underwriter_notes": note if random.random() < 0.8 else None,
            })
            did += 1
    return pl.DataFrame(records)


def gen_claims(
    policies: pl.DataFrame,
    adjuster_ids: list[int],
    company_risk: dict[int, tuple[str, str]],
) -> pl.DataFrame:
    """Generate claims and apply "loss-ratio calibration" to the loss amount (fix for Review-01 P1).

    Calibration model:
      1. Claim probability = RISK_TIER_CLAIM_PROB[risk_tier] - higher risk = more likely to have a claim (no more fixed 0.55).
      2. Each policy with claims gets a target loss ratio
             target_lr = industry baseline loss ratio × risk-tier loss multiplier × lognormal(0, 0.32)
         truncated to [0.05, 3.0]. This ties losses to the trio of premium / risk / industry.
      3. Reported-loss budget loss_budget = annual premium × target_lr × CLAIMED_LOSS_INFLATION,
         randomly split across the policy's multiple claims.
      4. Actual paid: paid = reported × pay ratio (0.60-0.95); Declined / Open (Filed/Investigating/Adjusting) = 0.
    This brings the median of "paid claims / annual premium" back into a realistic, healthy band, and makes it move monotonically with risk_tier / industry.
    """
    records = []
    cid = 1
    claim_types = ["财产损失", "人身伤害", "设备故障", "营业中断", "第三者责任",
                   "产品责任", "运输损失", "环境污染", "网络安全"]
    LOSS_MIN, LOSS_MAX = 20_000.0, 5_000_000.0
    for p in policies.iter_rows(named=True):
        risk_tier, industry = company_risk[p["company_id"]]
        # 1. Claim probability tied to the company's risk tier
        if random.random() >= RISK_TIER_CLAIM_PROB[risk_tier]:
            continue
        eff = p["effective_date"]
        exp = min(p["expiration_date"], TODAY)
        if exp <= eff:
            continue
        n_claims = random.choices([1, 2, 3, 4], weights=[0.40, 0.32, 0.20, 0.08])[0]
        # 2. Target loss ratio for this policy (tied to industry baseline + risk tier)
        target_lr = (
            INDUSTRY_BASE_LOSS_RATIO[industry]
            * RISK_TIER_LOSS_MULT[risk_tier]
            * random.lognormvariate(0.0, 0.32)
        )
        target_lr = min(max(target_lr, 0.05), 3.0)
        premium = float(p["current_annual_premium_cny"])
        # 3. Reported-loss budget, split randomly across multiple claims
        loss_budget = premium * target_lr * CLAIMED_LOSS_INFLATION
        shares = [random.random() + 0.15 for _ in range(n_claims)]
        s_sum = sum(shares)
        for k in range(n_claims):
            loss_amt = loss_budget * shares[k] / s_sum
            loss_amt = round(min(max(loss_amt, LOSS_MIN), LOSS_MAX), 2)
            incident = random_date(eff, exp)
            # Report date no later than "today" (fix for Review-01: 80 rows of reported_date > TODAY)
            reported = min(incident + timedelta(days=random.randint(0, 14)), TODAY)
            status = weighted_choice(
                ["已立案", "调查中", "定损中", "已支付", "已结案", "已拒赔"],
                [0.05, 0.10, 0.10, 0.20, 0.45, 0.10]
            )
            # 4. Actual paid: only Paid/Closed have a payment; Declined (paid nothing) and open cases = 0
            if status in ("已支付", "已结案"):
                paid_amt = round(loss_amt * random.uniform(0.60, 0.95), 2)
            else:
                paid_amt = 0.0
            records.append({
                "claim_id": cid,
                "policy_id": p["policy_id"],
                "adjuster_id": random.choice(adjuster_ids),
                "claim_number": f"CL{incident.year}{cid:07d}",
                "incident_date": incident,
                "reported_date": reported,
                "claim_type": random.choice(claim_types),
                "loss_amount_cny": loss_amt,
                "paid_amount_cny": paid_amt,
                "status": status,
            })
            cid += 1
    return pl.DataFrame(records)


def gen_claim_events(claims: pl.DataFrame) -> pl.DataFrame:
    """Claim life-cycle events"""
    records = []
    eid = 1
    # Event sequence templates (in occurrence order)
    full_lifecycle = ["立案受理", "现场勘查", "调查取证", "定损评估", "理算复核", "审批通过", "赔款支付", "结案归档"]
    rejected_lifecycle = ["立案受理", "现场勘查", "调查取证", "争议讨论", "拒赔决定", "通知投保人"]
    in_progress_lifecycle = ["立案受理", "现场勘查", "调查取证", "定损评估"]

    for c in claims.iter_rows(named=True):
        status = c["status"]
        if status == "已结案":
            seq = full_lifecycle
        elif status == "已支付":
            seq = full_lifecycle[:7]
        elif status == "已拒赔":
            seq = rejected_lifecycle
        elif status == "定损中":
            seq = in_progress_lifecycle
        elif status == "调查中":
            seq = in_progress_lifecycle[:3]
        else:  # Filed
            seq = in_progress_lifecycle[:2]

        base_date = c["reported_date"]
        base_dt = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=9)
        n = len(seq)
        # 1. Cumulative step (days): event stream is strictly time-ascending (fix for Review-01: 76% of event_date out of order)
        steps = [0]
        for _ in range(1, n):
            steps.append(steps[-1] + random.randint(3, 14))
        total_span = steps[-1]
        # 2. If the full life cycle would cross "today", proportionally compress (preserves ordering and relative gaps, doesn't produce future dates)
        max_span = max((TODAY - base_date).days, 0)
        scale = (max_span / total_span) if (total_span > 0 and total_span > max_span) else 1.0
        for i, et in enumerate(seq):
            # +i minutes to guarantee strictly increasing even when compressed onto the same day
            event_dt = base_dt + timedelta(days=steps[i] * scale, minutes=i)
            records.append({
                "event_id": eid,
                "claim_id": c["claim_id"],
                "event_date": event_dt,
                "event_type": et,
                "event_description": fake.sentence(nb_words=12),
            })
            eid += 1
    return pl.DataFrame(records)


def gen_claim_communications(
    claims: pl.DataFrame, underwriter_ids: list[int], adjuster_ids: list[int]
) -> pl.DataFrame:
    """Generate rich-text claim communications, with signal_tag/sub_tag for RAG/classification training"""
    records = []
    cid = 1
    comm_types = ["邮件", "电话纪要", "调查笔记", "现场报告"]

    # Status-aware category distribution (Declined/Investigating biased toward more dispute signals)
    def status_aware_weights(status: str) -> dict[str, float]:
        if status in ("已拒赔", "调查中"):
            return {"normal_cooperative": 0.20, "investigation_note": 0.20, "fraud_signal": 0.20,
                    "dispute_escalation": 0.20, "attorney_involvement": 0.10, "settlement_negotiation": 0.10}
        return COMM_CATEGORY_WEIGHTS

    categories = list(COMM_CATEGORY_WEIGHTS.keys())

    end_cap = datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=23, minutes=59)
    for c in claims.iter_rows(named=True):
        n_comm = random.randint(3, 8)
        base_dt = datetime.combine(c["reported_date"], datetime.min.time())
        # Communication time advances cumulatively (comm_date ≥ reported_date), capped at "today" to avoid future dates
        cur_comm = base_dt + timedelta(hours=random.randint(8, 19))
        weights_map = status_aware_weights(c["status"])
        weights_list = [weights_map[k] for k in categories]
        for i in range(n_comm):
            if i > 0:
                cur_comm = cur_comm + timedelta(days=random.randint(2, 10),
                                                hours=random.randint(0, 8))
            comm_dt = min(cur_comm, end_cap)
            category = weighted_choice(categories, weights_list)
            sub_tag, content = random.choice(CLAIM_COMM_TEMPLATES[category])
            # author: investigation-type usually written by adjuster, dispute/decline reviewed by underwriter
            if category in ("attorney_involvement", "dispute_escalation"):
                use_uw = random.random() < 0.65
            else:
                use_uw = random.random() < 0.20
            author_uw = random.choice(underwriter_ids) if use_uw else None
            author_adj = None if use_uw else random.choice(adjuster_ids)
            records.append({
                "comm_id": cid,
                "claim_id": c["claim_id"],
                "author_underwriter_id": author_uw,
                "author_adjuster_id": author_adj,
                "comm_date": comm_dt,
                "communication_type": random.choice(comm_types),
                "signal_tag": category,
                "sub_tag": sub_tag,
                "content": content,
            })
            cid += 1
    return pl.DataFrame(records)


def gen_claim_reserves(claims: pl.DataFrame) -> pl.DataFrame:
    records = []
    rid = 1
    reasons = [
        "首次定损依据初步估算",
        "经现场核查后下调准备金",
        "新发现损失项目,上调准备金",
        "诉讼可能,审慎计提",
        "和解谈判达成共识,准备金对齐和解金额",
        "已部分赔付,余额准备金调整",
    ]
    for c in claims.iter_rows(named=True):
        loss = float(c["loss_amount_cny"])
        n_res = random.choices([1, 2, 3, 4], weights=[0.30, 0.35, 0.25, 0.10])[0]
        base = loss * random.uniform(0.8, 1.2)
        cur_date = c["reported_date"]
        for i in range(n_res):
            if i > 0:
                cur_date = cur_date + timedelta(days=random.randint(10, 40))
            multiplier = 1.0 + (i * random.uniform(-0.25, 0.35))
            amount = max(base * multiplier, 1000)
            records.append({
                "reserve_id": rid,
                "claim_id": c["claim_id"],
                # Reserve adjustment date advances cumulatively, capped at "today"
                "reserve_date": min(cur_date, TODAY),
                "reserve_amount_cny": round(amount, 2),
                "adjustment_reason": random.choice(reasons) if i > 0 else "首次定损依据初步估算",
            })
            rid += 1
    return pl.DataFrame(records)


def gen_invoices(policies: pl.DataFrame) -> pl.DataFrame:
    """Each policy generates 4 quarterly invoices"""
    records = []
    iid = 1
    for p in policies.iter_rows(named=True):
        # Quarterly invoices, 4 installments total
        quarterly = float(p["current_annual_premium_cny"]) / 4
        for q in range(4):
            inv_date = p["effective_date"] + timedelta(days=q * 91)
            if inv_date > TODAY:
                break
            due = inv_date + timedelta(days=30)
            if due < TODAY - timedelta(days=10):
                status = weighted_choice(["已支付", "逾期"], [0.92, 0.08])
            elif due < TODAY:
                status = weighted_choice(["已支付", "逾期", "待支付"], [0.65, 0.10, 0.25])
            else:
                status = "待支付"
            records.append({
                "invoice_id": iid,
                "policy_id": p["policy_id"],
                "invoice_number": f"INV-{inv_date.year}-{iid:07d}",
                "invoice_date": inv_date,
                "due_date": due,
                "amount_due_cny": round(quarterly, 2),
                "status": status,
            })
            iid += 1
    return pl.DataFrame(records)


def gen_payments(invoices: pl.DataFrame) -> pl.DataFrame:
    records = []
    pid = 1
    for inv in invoices.iter_rows(named=True):
        if inv["status"] == "已支付":
            # 86% on-time, 10% slightly late, 4% severely late
            r = random.random()
            if r < 0.50:
                days_late = random.randint(-7, 0)
            elif r < 0.86:
                days_late = random.randint(1, 15)
            elif r < 0.96:
                days_late = random.randint(16, 45)
            else:
                days_late = random.randint(46, 120)
            pay_date = inv["due_date"] + timedelta(days=days_late)
            records.append({
                "payment_id": pid,
                "invoice_id": inv["invoice_id"],
                "payment_date": pay_date,
                "amount_paid_cny": float(inv["amount_due_cny"]),
                "days_late": days_late,
            })
            pid += 1
        elif inv["status"] == "逾期":
            # Some overdue invoices have been partially paid
            if random.random() < 0.30:
                days_late = random.randint(45, 180)
                records.append({
                    "payment_id": pid,
                    "invoice_id": inv["invoice_id"],
                    "payment_date": inv["due_date"] + timedelta(days=days_late),
                    "amount_paid_cny": round(float(inv["amount_due_cny"]) * random.uniform(0.4, 0.95), 2),
                    "days_late": days_late,
                })
                pid += 1
    return pl.DataFrame(records)


def gen_risk_assessments(
    policies: pl.DataFrame,
    underwriter_ids: list[int],
    company_risk: dict[int, tuple[str, str]],
) -> pl.DataFrame:
    """Underwriting risk score.

    Fix for Review-01: previously risk_score was purely random in [20,95], with zero correlation
    to actual loss ratio, making B11 "risk score vs. loss ratio" useless. Now it's anchored to
    the company risk_tier's score baseline (RISK_TIER_SCORE_BASE) plus Gaussian noise; since
    target_lr also rises with risk_tier, risk_score now correlates positively with loss ratio.
    """
    records = []
    aid = 1
    notes_pool = [
        "标的位于沿海地区,台风风险偏高,建议增加防灾费率",
        "企业近 3 年安全记录良好,可享受费率优惠",
        "高赔付率行业,基准费率上浮 15%",
        "标的存储易燃化学品,建议增加除外责任条款",
        "信用评级稳定,主要风险来自宏观行业周期",
        "首次合作客户,采用保守费率,后续根据出险情况调整",
        "经纪人提供的风险评估资料完整,核保流程顺畅",
        "现场检查发现多处隐患,要求 60 天内整改后方可续保",
        "财务报表显示流动性紧张,关注付款延迟风险",
        "申报标的金额与第三方评估存在 20% 差异,需进一步核实",
    ]
    for p in policies.iter_rows(named=True):
        risk_tier, _ = company_risk[p["company_id"]]
        score_base = RISK_TIER_SCORE_BASE[risk_tier]
        n_asm = random.randint(1, 3)
        for _ in range(n_asm):
            # Anchored at the risk-tier baseline + Gaussian noise, truncated to 20-95
            risk_score = int(round(random.gauss(score_base, 9)))
            risk_score = min(max(risk_score, 20), 95)
            records.append({
                "assessment_id": aid,
                "policy_id": p["policy_id"],
                "underwriter_id": random.choice(underwriter_ids),
                "assessment_date": random_date(p["effective_date"],
                                                min(p["expiration_date"], TODAY)),
                "risk_score": risk_score,
                "underwriter_notes": random.choice(notes_pool) if random.random() < 0.75 else None,
            })
            aid += 1
    return pl.DataFrame(records)


def gen_site_inspections(location_ids: list[int]) -> pl.DataFrame:
    records = []
    iid = 1
    hazards_pool = [
        "电气配线老化,部分线路过载,建议升级",
        "消防通道堆放杂物,影响紧急疏散",
        "灭火器超过年检日期,需立即更换",
        "屋顶防水层局部破损,雨季可能渗漏",
        "高温作业区缺少防护设施,工人安全防护不足",
        "易燃易爆品存储不规范,与生产区距离不足",
        "监控盲区较多,夜间安保薄弱",
        "应急照明系统老化,部分设备失效",
        None,  # 25% no hazards
        None,
    ]
    statuses = ["已完成", "进行中", "未开始", "无需整改"]
    for lid in location_ids:
        if random.random() < 0.45:  # 45% of locations have been inspected at least once
            for _ in range(random.randint(1, 2)):
                hazards = random.choice(hazards_pool)
                status = "无需整改" if hazards is None else weighted_choice(
                    ["已完成", "进行中", "未开始"], [0.55, 0.30, 0.15]
                )
                records.append({
                    "inspection_id": iid,
                    "location_id": lid,
                    "inspection_date": random_date(HISTORY_START, TODAY),
                    "inspector_name": fake.name(),
                    "hazards_identified": hazards,
                    "remediation_status": status,
                })
                iid += 1
    return pl.DataFrame(records)


def gen_loss_runs(
    companies: pl.DataFrame, claims: pl.DataFrame, policies: pl.DataFrame
) -> pl.DataFrame:
    """Aggregate loss ratio by (company × underwriting year × line of business) under the policy-year / underwriting-year convention.

    Fix for Review-01:
      - Premium is attributed to the "underwriting year" (the year of effective_date), each policy
        counted only once, instead of range(eff.year, exp.year+1) double-counting premium across
        years (the original "cumulative premium inflated by about 2x").
      - Losses are uniformly "paid claims" SUM(paid_amount_cny): Declined / open claims naturally
        contribute 0; removed the original `paid or loss*0.5` phantom losses, consistent with
        company.total_paid_claims / D3 / 17.4.
      - No longer drops 2026: underwriting year covers 2024 / 2025 / 2026, so "last 3 years" actually means 3 years.
    """
    records = []
    lrid = 1

    # Build index: claims by policy_id
    claims_by_policy: dict[int, list[dict]] = {}
    for c in claims.iter_rows(named=True):
        claims_by_policy.setdefault(c["policy_id"], []).append(c)

    # Aggregate by (company, underwriting year, line of business): premium counted once + paid losses across all claims of that policy
    agg: dict[tuple[int, int, str], dict] = {}
    for p in policies.iter_rows(named=True):
        key = (p["company_id"], p["effective_date"].year, p["policy_type"])
        bucket = agg.setdefault(key, {"premium": 0.0, "losses": 0.0, "count": 0})
        bucket["premium"] += float(p["current_annual_premium_cny"])
        for c in claims_by_policy.get(p["policy_id"], []):
            bucket["losses"] += float(c["paid_amount_cny"])
            bucket["count"] += 1

    for (cid, year, ptype), b in agg.items():
        if b["premium"] <= 0:
            continue
        records.append({
            "loss_run_id": lrid,
            "company_id": cid,
            "year": year,
            "policy_type": ptype,
            "total_premium_cny": round(b["premium"], 2),
            "total_losses_cny": round(b["losses"], 2),
            "loss_ratio": round(b["losses"] / b["premium"], 4),
            "claim_frequency": b["count"],
        })
        lrid += 1
    return pl.DataFrame(records)


def gen_industry_benchmarks() -> pl.DataFrame:
    records = []
    bid = 1
    for ind in INDUSTRIES:
        base_ratio = INDUSTRY_BASE_LOSS_RATIO[ind]
        for year in range(2021, 2027):  # includes 2026, aligned with loss_run underwriting years
            records.append({
                "benchmark_id": bid,
                "industry": ind,
                "year": year,
                "avg_loss_ratio": round(base_ratio + random.uniform(-0.08, 0.08), 3),
                "avg_claim_frequency": round(random.uniform(2.0, 8.0), 2),
                "avg_premium_range_low_cny": round(random.uniform(50_000, 200_000), 2),
                "avg_premium_range_high_cny": round(random.uniform(500_000, 2_500_000), 2),
            })
            bid += 1
    return pl.DataFrame(records)


def gen_regulatory_filings(company_ids: list[int]) -> pl.DataFrame:
    records = []
    fid = 1
    resolutions = ["已结案", "进行中", "申诉中"]
    for cid in company_ids:
        # 35% of companies have at least one regulatory penalty
        if random.random() < 0.35:
            for _ in range(random.randint(1, 4)):
                agency, vtype_base = random.choice(REGULATORY_AGENCIES)
                violation_detail = vtype_base + " - " + random.choice([
                    "未按时整改", "存在重大隐患", "记录不规范",
                    "超标排放", "证件过期", "未按规定培训",
                ])
                records.append({
                    "filing_id": fid,
                    "company_id": cid,
                    "filing_date": random_date(date(2022, 1, 1), TODAY),
                    "agency": agency,
                    "violation_type": violation_detail,
                    "fine_amount_cny": round(random.uniform(5_000, 500_000), 2),
                    "resolution_status": weighted_choice(resolutions, [0.65, 0.25, 0.10]),
                })
                fid += 1
    return pl.DataFrame(records)


def gen_third_party_reports(company_ids: list[int]) -> pl.DataFrame:
    records = []
    rid = 1
    changes = ["上调", "下调", "维持"]
    for cid in company_ids:
        for _ in range(random.randint(2, 4)):
            records.append({
                "report_id": rid,
                "company_id": cid,
                "report_date": random_date(date(2023, 1, 1), TODAY),
                "credit_rating": weighted_choice(CREDIT_RATINGS, CREDIT_RATING_WEIGHTS),
                "rating_change": weighted_choice(changes, [0.20, 0.20, 0.60]),
                "report_source": random.choice(CREDIT_RATING_AGENCIES),
            })
            rid += 1
    return pl.DataFrame(records)


# ============================================================================
# Reconciliation logic
# ============================================================================
def reconcile_policy_premium(
    policies: pl.DataFrame, premium_history: pl.DataFrame
) -> pl.DataFrame:
    """Reconciliation: policy.current_annual_premium_cny = latest premium_history.new_premium_cny"""
    latest = (
        premium_history.sort("changed_at", descending=True)
        .group_by("policy_id")
        .agg(pl.col("new_premium_cny").first().alias("latest_premium"))
    )
    return (
        policies.join(latest, on="policy_id", how="left")
        .with_columns(
            pl.coalesce("latest_premium", "current_annual_premium_cny")
            .alias("current_annual_premium_cny")
        )
        .drop("latest_premium")
    )


def reconcile_company_aggregates(
    companies: pl.DataFrame,
    policies: pl.DataFrame,
    claims: pl.DataFrame,
) -> pl.DataFrame:
    """Reconciliation:
       company.total_active_premium_cny = SUM(policies WHERE status='In-force')
       company.total_paid_claims_cny = SUM(claims.paid_amount via policies)
    """
    active_premium = (
        policies.filter(pl.col("status") == "有效")
        .group_by("company_id")
        .agg(pl.col("current_annual_premium_cny").sum().alias("active_premium"))
    )
    paid_claims = (
        claims.join(
            policies.select("policy_id", "company_id"), on="policy_id", how="inner"
        )
        .group_by("company_id")
        .agg(pl.col("paid_amount_cny").sum().alias("paid_claims"))
    )
    return (
        companies.join(active_premium, on="company_id", how="left")
        .join(paid_claims, on="company_id", how="left")
        .with_columns(
            pl.coalesce("active_premium", pl.lit(0.0)).alias("total_active_premium_cny"),
            pl.coalesce("paid_claims", pl.lit(0.0)).alias("total_paid_claims_cny"),
        )
        .drop("active_premium", "paid_claims")
    )


# ============================================================================
# Main control function (idempotent)
# ============================================================================

def generate_all_tsv() -> None:
    """Generate all TSV files (idempotent: delete the old files first, then generate)"""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("生成 (按拓扑顺序)...")

    # ---- Domain 1: Organization ----
    df_underwriter = gen_underwriters()
    underwriter_ids = df_underwriter["underwriter_id"].to_list()
    df_underwriter.write_csv(DATA_DIR / "01_underwriter.tsv", separator="\t")
    print(f"  01_underwriter: {len(df_underwriter)}")

    df_broker = gen_brokers()
    df_broker.write_csv(DATA_DIR / "02_broker.tsv", separator="\t")
    print(f"  02_broker: {len(df_broker)}")

    df_adjuster = gen_adjusters()
    adjuster_ids = df_adjuster["adjuster_id"].to_list()
    df_adjuster.write_csv(DATA_DIR / "03_claim_adjuster.tsv", separator="\t")
    print(f"  03_claim_adjuster: {len(df_adjuster)}")

    df_benchmark = gen_industry_benchmarks()
    df_benchmark.write_csv(DATA_DIR / "04_industry_benchmark.tsv", separator="\t")
    print(f"  04_industry_benchmark: {len(df_benchmark)}")

    df_company = gen_companies()
    company_ids = df_company["company_id"].to_list()
    # company_id -> (risk_tier, industry): used by claim / risk_assessment for loss-ratio calibration
    company_risk: dict[int, tuple[str, str]] = {
        row["company_id"]: (row["risk_tier"], row["industry"])
        for row in df_company.iter_rows(named=True)
    }
    # Don't write out yet (need to reconcile first)
    print(f"  (gen) company: {len(df_company)}")

    df_company_fin = gen_company_financials(company_ids)
    df_company_fin.write_csv(DATA_DIR / "06_company_financial.tsv", separator="\t")
    print(f"  06_company_financial: {len(df_company_fin)}")

    df_company_loc = gen_company_locations(company_ids)
    location_ids = df_company_loc["location_id"].to_list()
    df_company_loc.write_csv(DATA_DIR / "07_company_location.tsv", separator="\t")
    print(f"  07_company_location: {len(df_company_loc)}")

    df_subcontractor = gen_subcontractors(company_ids)
    df_subcontractor.write_csv(DATA_DIR / "08_subcontractor.tsv", separator="\t")
    print(f"  08_subcontractor: {len(df_subcontractor)}")

    # ---- Domain 2: Policy ----
    df_policy = gen_policies(df_company, underwriter_ids)
    policy_ids = df_policy["policy_id"].to_list()
    print(f"  (gen) policy: {len(df_policy)}")

    df_coverage = gen_policy_coverages(policy_ids)
    df_coverage.write_csv(DATA_DIR / "10_policy_coverage.tsv", separator="\t")
    print(f"  10_policy_coverage: {len(df_coverage)}")

    df_endorsement = gen_policy_endorsements(policy_ids)
    df_endorsement.write_csv(DATA_DIR / "11_policy_endorsement.tsv", separator="\t")
    print(f"  11_policy_endorsement: {len(df_endorsement)}")

    df_premium_history = gen_policy_premium_history(df_policy, df_endorsement)
    df_premium_history.write_csv(DATA_DIR / "12_policy_premium_history.tsv", separator="\t")
    print(f"  12_policy_premium_history: {len(df_premium_history)}")

    # Reconcile policy.current_annual_premium_cny
    df_policy = reconcile_policy_premium(df_policy, df_premium_history)

    df_renewal = gen_renewal_decisions(df_policy, underwriter_ids)
    df_renewal.write_csv(DATA_DIR / "13_renewal_decision.tsv", separator="\t")
    print(f"  13_renewal_decision: {len(df_renewal)}")

    # ---- Domain 3: Claims ----
    df_claim = gen_claims(df_policy, adjuster_ids, company_risk)
    print(f"  (gen) claim: {len(df_claim)}")

    df_claim_event = gen_claim_events(df_claim)
    df_claim_event.write_csv(DATA_DIR / "15_claim_event.tsv", separator="\t")
    print(f"  15_claim_event: {len(df_claim_event)}")

    df_claim_comm = gen_claim_communications(df_claim, underwriter_ids, adjuster_ids)
    df_claim_comm.write_csv(DATA_DIR / "16_claim_communication.tsv", separator="\t")
    print(f"  16_claim_communication: {len(df_claim_comm)}")

    df_claim_reserve = gen_claim_reserves(df_claim)
    df_claim_reserve.write_csv(DATA_DIR / "17_claim_reserve.tsv", separator="\t")
    print(f"  17_claim_reserve: {len(df_claim_reserve)}")

    df_claim.write_csv(DATA_DIR / "14_claim.tsv", separator="\t")
    print(f"  14_claim: {len(df_claim)}")

    # ---- Domain 4: Invoices and Payments ----
    df_invoice = gen_invoices(df_policy)
    df_invoice.write_csv(DATA_DIR / "18_invoice.tsv", separator="\t")
    print(f"  18_invoice: {len(df_invoice)}")

    df_payment = gen_payments(df_invoice)
    df_payment.write_csv(DATA_DIR / "19_payment.tsv", separator="\t")
    print(f"  19_payment: {len(df_payment)}")

    # ---- Domain 5: Risk Assessment ----
    df_risk = gen_risk_assessments(df_policy, underwriter_ids, company_risk)
    df_risk.write_csv(DATA_DIR / "20_risk_assessment.tsv", separator="\t")
    print(f"  20_risk_assessment: {len(df_risk)}")

    df_inspection = gen_site_inspections(location_ids)
    df_inspection.write_csv(DATA_DIR / "21_site_inspection.tsv", separator="\t")
    print(f"  21_site_inspection: {len(df_inspection)}")

    df_loss_run = gen_loss_runs(df_company, df_claim, df_policy)
    df_loss_run.write_csv(DATA_DIR / "22_loss_run.tsv", separator="\t")
    print(f"  22_loss_run: {len(df_loss_run)}")

    # ---- Domain 6: External ----
    df_reg = gen_regulatory_filings(company_ids)
    df_reg.write_csv(DATA_DIR / "23_regulatory_filing.tsv", separator="\t")
    print(f"  23_regulatory_filing: {len(df_reg)}")

    df_tpr = gen_third_party_reports(company_ids)
    df_tpr.write_csv(DATA_DIR / "24_third_party_report.tsv", separator="\t")
    print(f"  24_third_party_report: {len(df_tpr)}")

    # ---- Reconcile company aggregates and finally write out ----
    df_company = reconcile_company_aggregates(df_company, df_policy, df_claim)
    df_company.write_csv(DATA_DIR / "05_company.tsv", separator="\t")
    print(f"  05_company (含对账): {len(df_company)}")

    # Re-write policy (with reconciled premium)
    df_policy.write_csv(DATA_DIR / "09_policy.tsv", separator="\t")
    print(f"  09_policy (含对账): {len(df_policy)}")

    # ---- Data-quality quick view (the generator's built-in prints verify the key fixes; no extra script needed) ----
    print("\n[数据质量速览]")
    # Policy status share
    status_share = (
        df_policy.group_by("status").len().sort("len", descending=True)
    )
    share_txt = ", ".join(
        f"{r['status']} {r['len'] / len(df_policy) * 100:.1f}%"
        for r in status_share.iter_rows(named=True)
    )
    print(f"  policy.status 占比: {share_txt}")
    # loss_run loss-ratio distribution (validates the truthfulness of the core KPI)
    lr = df_loss_run["loss_ratio"]
    n_lr = len(lr)
    comb = df_loss_run["total_losses_cny"].sum() / max(df_loss_run["total_premium_cny"].sum(), 1)
    years = sorted(set(df_loss_run["year"].to_list()))
    print(
        f"  loss_run.loss_ratio: 均值 {lr.mean():.3f} / 最大 {lr.max():.2f} / "
        f"=0 占 {(lr == 0).sum() / n_lr * 100:.1f}% / "
        f"[0.4,1.0] 占 {((lr >= 0.4) & (lr <= 1.0)).sum() / n_lr * 100:.1f}% / "
        f">1.0 占 {(lr > 1.0).sum() / n_lr * 100:.1f}%"
    )
    print(f"  loss_run 组合赔付率 SUM(losses)/SUM(premium) = {comb:.3f}; 承保年度 = {years}")
    # risk_tier → average paid claims (should be monotonically increasing)
    paid_by_tier = []
    for tier in RISK_TIERS:
        cids = [cid for cid, (rt, _ind) in company_risk.items() if rt == tier]
        tier_policy_ids = df_policy.filter(
            pl.col("company_id").is_in(cids)
        )["policy_id"].to_list()
        sub = df_claim.filter(pl.col("policy_id").is_in(tier_policy_ids))
        avg_paid = sub["paid_amount_cny"].mean() if len(sub) else 0.0
        paid_by_tier.append(f"{tier} {avg_paid or 0:,.0f}")
    print(f"  各风险等级平均已付赔款: {', '.join(paid_by_tier)}")
    # Future-date check (should all be 0)
    fut_reported = (df_claim["reported_date"] > TODAY).sum()
    fut_event = (df_claim_event["event_date"] > datetime.combine(TODAY, datetime.max.time())).sum()
    fut_decision = (df_renewal["decision_date"] > TODAY).sum()
    print(
        f"  晚于今天的 reported_date={fut_reported}, claim_event.event_date={fut_event}, "
        f"renewal_decision.decision_date={fut_decision} (应均为 0)"
    )
    # renewal_decision year distribution (B10 depends on: earliest decision year 2025)
    rd_years = (
        df_renewal.with_columns(pl.col("decision_date").dt.year().alias("y"))
        .group_by("y").len().sort("y")
    )
    print("  renewal_decision 决策年分布: "
          + ", ".join(f"{r['y']}:{r['len']}" for r in rd_years.iter_rows(named=True)))

    # Row-count summary
    total = sum(len(d) for d in [
        df_underwriter, df_broker, df_adjuster, df_benchmark, df_company,
        df_company_fin, df_company_loc, df_subcontractor, df_policy,
        df_coverage, df_endorsement, df_premium_history, df_renewal,
        df_claim, df_claim_event, df_claim_comm, df_claim_reserve,
        df_invoice, df_payment, df_risk, df_inspection, df_loss_run,
        df_reg, df_tpr,
    ])
    print(f"\n✓ 共生成 {total:,} 行 (24 张表)")


def create_sqlite_database() -> None:
    """Create SQLite from TSV (idempotent)"""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # Load order (topological)
    load_plan: list[tuple[str, type]] = [
        ("01_underwriter.tsv", Underwriter),
        ("02_broker.tsv", Broker),
        ("03_claim_adjuster.tsv", ClaimAdjuster),
        ("04_industry_benchmark.tsv", IndustryBenchmark),
        ("05_company.tsv", Company),
        ("06_company_financial.tsv", CompanyFinancial),
        ("07_company_location.tsv", CompanyLocation),
        ("08_subcontractor.tsv", Subcontractor),
        ("09_policy.tsv", Policy),
        ("10_policy_coverage.tsv", PolicyCoverage),
        ("11_policy_endorsement.tsv", PolicyEndorsement),
        ("12_policy_premium_history.tsv", PolicyPremiumHistory),
        ("13_renewal_decision.tsv", RenewalDecision),
        ("14_claim.tsv", Claim),
        ("15_claim_event.tsv", ClaimEvent),
        ("16_claim_communication.tsv", ClaimCommunication),
        ("17_claim_reserve.tsv", ClaimReserve),
        ("18_invoice.tsv", Invoice),
        ("19_payment.tsv", Payment),
        ("20_risk_assessment.tsv", RiskAssessment),
        ("21_site_inspection.tsv", SiteInspection),
        ("22_loss_run.tsv", LossRun),
        ("23_regulatory_filing.tsv", RegulatoryFiling),
        ("24_third_party_report.tsv", ThirdPartyReport),
    ]

    print("\n加载至 SQLite...")
    with Session(engine) as session:
        for filename, Model in load_plan:
            fp = DATA_DIR / filename
            if not fp.exists():
                print(f"  跳过缺失文件: {filename}")
                continue
            df = pl.read_csv(fp, separator="\t", try_parse_dates=True)
            if len(df) == 0:
                continue
            # Bulk insert
            session.bulk_insert_mappings(Model, df.to_dicts())
        session.commit()
    print(f"✓ SQLite 数据库已创建: {DATABASE_PATH}")


def main() -> None:
    print("=" * 80)
    print("InsightUnderwriter 商业承保数据生成器 - 高复杂度版本")
    print("=" * 80)
    generate_all_tsv()
    create_sqlite_database()
    print("=" * 80)
    print(f"  TSV 文件: {DATA_DIR}")
    print(f"  SQLite:   {DATABASE_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
