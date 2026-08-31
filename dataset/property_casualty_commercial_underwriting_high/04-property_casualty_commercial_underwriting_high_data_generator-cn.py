"""
财产 & 责任险 - 商业承保 假数据生成器 (高复杂度版)

业务背景
========
本数据集模拟 "鼎安商业保险股份有限公司" (DingAn Commercial Insurance, 虚构的国内中型商业财产/责任险公司),
支持构建 InsightUnderwriter —— 一个辅助核保员 (Underwriter) 进行商业保险续保分析的 AI Agent。

数据集覆盖 6 个业务域 共 24 张表 约 115,000 行:
  域 1 - 主体与组织 (7 表): company, company_financial, company_location, subcontractor,
                              underwriter, broker, claim_adjuster
  域 2 - 保单与承保 (5 表): policy, policy_coverage, policy_endorsement,
                              policy_premium_history, renewal_decision
  域 3 - 理赔 (4 表): claim, claim_event, claim_communication, claim_reserve
  域 4 - 账单与付款 (2 表): invoice, payment
  域 5 - 风险评估 (3 表): risk_assessment, site_inspection, loss_run
  域 6 - 外部参考 (3 表): industry_benchmark, regulatory_filing, third_party_report

参考"今天"日期: 2026-06-21
历史窗口: 2024-06-21 ~ 2026-06-21 (24 个月)
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
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "property_casualty_commercial_underwriting_high.sqlite"

RANDOM_SEED = 42
TODAY = date(2026, 6, 21)
HISTORY_START = TODAY - timedelta(days=730)  # 24 个月

fake = Faker("zh_CN")
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ---- 数据量参数 -------------------------------------------------------------
N_COMPANIES = 1000
N_UNDERWRITERS = 40   # 含 5 个 Senior/Manager
N_BROKERS = 60
N_ADJUSTERS = 25

# ---- 业务枚举 (中文化) ------------------------------------------------------
INDUSTRIES = [
    "建筑施工", "制造业", "商业地产", "信息科技", "医疗健康",
    "零售批发", "物流运输", "餐饮酒店", "能源化工", "金融服务",
]

INDUSTRY_BASE_LOSS_RATIO = {  # 行业基准赔付率 (用于 loss_run 生成)
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

# 风险等级 → 出险概率 (风险越高越容易出险)
RISK_TIER_CLAIM_PROB = {"低风险": 0.42, "中风险": 0.55, "高风险": 0.72, "极高风险": 0.88}
# 风险等级 → 损失幅度乘数 (作用于目标赔付率, 风险越高赔付率越高)
RISK_TIER_LOSS_MULT = {"低风险": 0.80, "中风险": 1.00, "高风险": 1.25, "极高风险": 1.55}
# 风险等级 → 核保风险评分基准 (使 risk_score 与 risk_tier / 赔付率正相关)
RISK_TIER_SCORE_BASE = {"低风险": 32, "中风险": 50, "高风险": 67, "极高风险": 82}
# 保单层面 "已赚保费→损失" 标定: 申报损失相对实赔的放大系数 (实赔 ≈ 申报 × 赔付比例)
# 用于把单笔已付赔款 / 保费的中位数标定到健康赔付率区间 (约 0.5–0.9)
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
UNDERWRITER_ROLE_QUOTAS = {"核保经理": 0, "高级核保员": 8, "核保员": 5, "初级核保员": 3}  # 月配额(保单数)

BROKER_FIRMS = [
    "怡安(中国)保险经纪", "韦莱韬悦保险经纪", "达信(中国)保险经纪",
    "明亚保险经纪", "华泰保险经纪", "江泰保险经纪", "联合保险经纪",
    "北京中怡保险经纪", "众和保险经纪", "永达理保险经纪",
]

# ============================================================================
# 理赔通讯模板库 (RAG 数据源)
# 每个模板格式: (signal_tag, sub_tag, content)
# signal_tag 用于打标签辅助 AI Agent 训练 RAG / 分类
# ============================================================================

CLAIM_COMM_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    # 正常合作型 (约 45%)
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
    # 调查笔记 (约 20%) - 描述事故调查过程
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
    # 欺诈信号 (约 10%) - 高价值的非结构化信号
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
    # 争议升级 (约 10%)
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
    # 律师介入 (约 5%) - 最严重的争议
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
    # 和解谈判 (约 10%)
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

# 各类别概率分布
COMM_CATEGORY_WEIGHTS = {
    "normal_cooperative": 0.45,
    "investigation_note": 0.20,
    "fraud_signal": 0.10,
    "dispute_escalation": 0.10,
    "attorney_involvement": 0.05,
    "settlement_negotiation": 0.10,
}


# ============================================================================
# SQLAlchemy ORM 模型 (24 张表)
# ============================================================================
class Base(DeclarativeBase):
    """全部 ORM 模型的基类"""
    pass


# ---------- 域 1: 主体与组织 ----------
class Underwriter(Base):
    """核保员档案。manager_id 自引用 FK 编码团队层级。"""
    __tablename__ = "underwriter"
    underwriter_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)       # 核保经理/高级核保员/核保员/初级核保员
    specialty_industry: Mapped[str] = mapped_column(String(40), nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)     # 华北/华东/华南/华西/华中
    manager_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"))
    monthly_quota_policies: Mapped[int] = mapped_column(Integer, nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Broker(Base):
    """保险经纪人 / 中介。商业保险大多通过 broker 渠道达成。"""
    __tablename__ = "broker"
    broker_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_firm: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(40), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    license_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False)     # 0.05 ~ 0.20
    tier: Mapped[str] = mapped_column(String(20), nullable=False)              # 战略合作/重要合作/一般合作
    onboarded_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClaimAdjuster(Base):
    """理赔员 / 公估师档案"""
    __tablename__ = "claim_adjuster"
    adjuster_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    specialty_claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    case_load_capacity: Mapped[int] = mapped_column(Integer, nullable=False)   # 同时处理案件数上限
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)


class Company(Base):
    """投保企业主档"""
    __tablename__ = "company"
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unified_social_credit_code: Mapped[str] = mapped_column(String(18), nullable=False, unique=True)  # 统一社会信用代码
    industry: Mapped[str] = mapped_column(String(40), nullable=False)
    founded_year: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    business_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # 对账字段
    total_active_premium_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    total_paid_claims_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CompanyFinancial(Base):
    """企业历年财务"""
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
    """企业经营场所 (财产险标的)"""
    __tablename__ = "company_location"
    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    location_name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False)
    province: Mapped[str] = mapped_column(String(40), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(10), nullable=False)
    property_value_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    location_risk_level: Mapped[str] = mapped_column(String(20), nullable=False)    # 低/中/高
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Subcontractor(Base):
    """企业使用的分包商 (建筑工程险相关)"""
    __tablename__ = "subcontractor"
    subcontractor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    subcontractor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialty: Mapped[str] = mapped_column(String(40), nullable=False)
    has_claims_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100


# ---------- 域 2: 保单与承保 ----------
class Policy(Base):
    """保单主档"""
    __tablename__ = "policy"
    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    underwriter_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"), nullable=False)
    broker_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("broker.broker_id"))  # 15% 直销 (NULL)
    policy_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    policy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_annual_premium_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_annual_premium_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)  # 对账: 来自 premium_history 最新行
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 有效/已到期/已注销
    bound_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        Index("idx_policy_company", "company_id"),
        Index("idx_policy_underwriter", "underwriter_id"),
        Index("idx_policy_status", "status"),
    )


class PolicyCoverage(Base):
    """保单承保项目明细 (一张保单可包含多项承保范围)"""
    __tablename__ = "policy_coverage"
    coverage_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    coverage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage_limit_cny: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    deductible_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class PolicyEndorsement(Base):
    """保单批改记录 (中途修改: 加保/退保/责任变更)"""
    __tablename__ = "policy_endorsement"
    endorsement_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    endorsement_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    premium_adjustment_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class PolicyPremiumHistory(Base):
    """保费费率变化时间快照表
    每次保费调整(初承、批改)生成一行,记录调整前后的保费和原因。
    支持"保费滑动"分析,识别频繁调价的高风险保单。
    """
    __tablename__ = "policy_premium_history"
    premium_history_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    change_event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # 初承/批改
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
    """历史续保决策记录"""
    __tablename__ = "renewal_decision"
    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    underwriter_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"), nullable=False)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)  # 续保/有条件续保/拒保
    premium_change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    underwriter_notes: Mapped[str | None] = mapped_column(Text)


# ---------- 域 3: 理赔 ----------
class Claim(Base):
    """理赔主档"""
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
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 已立案/调查中/定损中/已支付/已结案/已拒赔
    __table_args__ = (
        Index("idx_claim_policy", "policy_id"),
        Index("idx_claim_status", "status"),
        Index("idx_claim_incident_date", "incident_date"),
    )


class ClaimEvent(Base):
    """理赔事件时间线 (报案/受理/调查/定损/赔付/结案 等状态变更)"""
    __tablename__ = "claim_event"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim.claim_id"), nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_description: Mapped[str | None] = mapped_column(Text)


class ClaimCommunication(Base):
    """理赔过程的非结构化通讯 (邮件/电话纪要/调查笔记)
    这是 InsightUnderwriter RAG 的主要数据源:
    通过 signal_tag 字段进行类别标注,便于训练欺诈检测、争议预警等模型。
    XOR 约束: author_underwriter_id 与 author_adjuster_id 二者必恰好一个非空。
    """
    __tablename__ = "claim_communication"
    comm_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim.claim_id"), nullable=False)
    author_underwriter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"))
    author_adjuster_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("claim_adjuster.adjuster_id"))
    comm_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    communication_type: Mapped[str] = mapped_column(String(30), nullable=False)  # 邮件/电话/调查笔记/现场报告
    signal_tag: Mapped[str] = mapped_column(String(40), nullable=False)            # 类别标签
    sub_tag: Mapped[str] = mapped_column(String(60), nullable=False)               # 子类别标签
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # XOR 约束: author_underwriter_id 与 author_adjuster_id 恰好一个非空 (与 ER 14 节 DDL 一致)
    __table_args__ = (
        CheckConstraint(
            "(author_underwriter_id IS NULL) <> (author_adjuster_id IS NULL)",
            name="ck_claim_communication_author_xor",
        ),
        Index("idx_comm_claim", "claim_id"),
        Index("idx_comm_signal_tag", "signal_tag"),
    )


class ClaimReserve(Base):
    """理赔准备金 (reserve) 设定与调整历史"""
    __tablename__ = "claim_reserve"
    reserve_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("claim.claim_id"), nullable=False)
    reserve_date: Mapped[date] = mapped_column(Date, nullable=False)
    reserve_amount_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    adjustment_reason: Mapped[str | None] = mapped_column(Text)


# ---------- 域 4: 账单与付款 ----------
class Invoice(Base):
    """保费账单"""
    __tablename__ = "invoice"
    invoice_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 已支付/逾期/待支付
    __table_args__ = (Index("idx_invoice_policy", "policy_id"),)


class Payment(Base):
    """实际付款记录"""
    __tablename__ = "payment"
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoice.invoice_id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paid_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    days_late: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (Index("idx_payment_invoice", "invoice_id"),)


# ---------- 域 5: 风险评估 ----------
class RiskAssessment(Base):
    """风险评分 (核保员对保单的风险打分)"""
    __tablename__ = "risk_assessment"
    assessment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=False)
    underwriter_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriter.underwriter_id"), nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100, 越高越危险
    underwriter_notes: Mapped[str | None] = mapped_column(Text)


class SiteInspection(Base):
    """现场检查记录"""
    __tablename__ = "site_inspection"
    inspection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("company_location.location_id"), nullable=False)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False)
    inspector_name: Mapped[str] = mapped_column(String(50), nullable=False)
    hazards_identified: Mapped[str | None] = mapped_column(Text)
    remediation_status: Mapped[str] = mapped_column(String(20), nullable=False)  # 已完成/进行中/未开始/无需整改


class LossRun(Base):
    """按公司 × 年度 × 险种汇总的赔付率统计 (loss run report)"""
    __tablename__ = "loss_run"
    loss_run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    total_premium_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    total_losses_cny: Mapped[float] = mapped_column(Numeric(13, 2), nullable=False)
    loss_ratio: Mapped[float] = mapped_column(Float, nullable=False)  # 对账: total_losses / total_premium
    claim_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (Index("idx_loss_run_company_year", "company_id", "year"),)


# ---------- 域 6: 外部参考 ----------
class IndustryBenchmark(Base):
    """行业基准数据"""
    __tablename__ = "industry_benchmark"
    benchmark_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry: Mapped[str] = mapped_column(String(40), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_loss_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    avg_claim_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    avg_premium_range_low_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    avg_premium_range_high_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class RegulatoryFiling(Base):
    """监管处罚记录 (来自外部监管部门数据)"""
    __tablename__ = "regulatory_filing"
    filing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    agency: Mapped[str] = mapped_column(String(40), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    fine_amount_cny: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False)  # 已结案/进行中/申诉中


class ThirdPartyReport(Base):
    """第三方信用评级报告"""
    __tablename__ = "third_party_report"
    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.company_id"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_rating: Mapped[str] = mapped_column(String(10), nullable=False)
    rating_change: Mapped[str] = mapped_column(String(20), nullable=False)   # 上调/下调/维持
    report_source: Mapped[str] = mapped_column(String(40), nullable=False)


# ============================================================================
# 辅助函数
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
    """生成 18 位统一社会信用代码 (示意,不保证校验位正确)"""
    digits = "0123456789"
    letters = "ABCDEFGHJKLMNPQRTUWXY"
    return (
        "91"
        + "".join(random.choices(digits + letters, k=6))
        + "".join(random.choices(digits + letters, k=9))
        + random.choice(digits + letters)
    )


# ============================================================================
# 数据生成器
# ============================================================================

def gen_underwriters() -> pl.DataFrame:
    """生成核保员: 5 个经理 + 35 个核保员 (总 40)"""
    regions = ["华北", "华东", "华南", "华西", "华中"]
    records = []
    # 5 个经理 - 每个区域一个
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
    # 35 个核保员 - 分配给经理, 含 8 高级/20 普通/7 初级
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
        # 保证公司名唯一
        for _ in range(10):
            name = fake.company()
            if name not in used_names:
                used_names.add(name)
                break
        founded_year = random.randint(1985, 2022)
        # 客户建档不早于公司成立, 也不早于鼎安系统上线 (2020)
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
            "total_active_premium_cny": 0.0,  # 后续对账填充
            "total_paid_claims_cny": 0.0,      # 后续对账填充
            "created_at": random_datetime(created_floor, TODAY),
        })
    return pl.DataFrame(records)


def gen_company_financials(company_ids: list[int]) -> pl.DataFrame:
    records = []
    fid = 1
    for cid in company_ids:
        # base_revenue = 最新年度 (2025) 营收; 每家公司有一个稳定的同比增长率 growth
        base_revenue = random.uniform(5_000_000, 500_000_000)
        growth = random.uniform(-0.10, 0.25)
        for year_offset in range(random.randint(3, 5)):
            fiscal_year = 2025 - year_offset
            # year_offset 越大 = 年份越旧; 旧年营收 = 最新营收 / (1+growth)^offset
            # => growth>0 时营收随时间递增 (新年更高), growth<0 时递减, 符合真实趋势
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
        if random.random() < 0.30:  # 30% 公司有分包商
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
    """每个公司生成 1-5 张保单 (含历史)。总目标 ~2500 张。"""
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
            # 状态由保单是否已过期决定: 已过期 → 已到期(~85%)/已注销(~15%);
            # 未过期 → 有效(~95%)/已注销(~5%)。整体实测约 有效44% / 已到期45% / 已注销10%。
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
                "current_annual_premium_cny": round(base_premium, 2),  # 后续对账
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
    """为每张保单生成保费时间快照: 初承 (1 行) + 每个 endorsement 对应一行"批改"。

    说明: 本数据集以"续保=新建保单"建模 (见 renewal_decision), 故 premium_history
    只含 初承 / 批改 两类事件, 不生成"续保"行 (与 ER 9.12 枚举一致)。
    """
    records = []
    hid = 1
    endo_by_policy: dict[int, list[dict]] = {}
    for r in endorsements.iter_rows(named=True):
        endo_by_policy.setdefault(r["policy_id"], []).append(r)

    for p in policies.iter_rows(named=True):
        pid = p["policy_id"]
        # 1. 初承事件
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
        # 2. 每个 endorsement 一次调整
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
        # 已到期保单大概率有续保决策记录
        if p["expiration_date"] < TODAY and random.random() < 0.70:
            decision = weighted_choice(decisions, decision_weights)
            premium_change = random.uniform(-15.0, 35.0) if decision != "拒保" else 0.0
            note = random.choice(note_templates).format(pct=round(premium_change, 1))
            # 保持与原实现一致的随机调用顺序 (先 underwriter_id, 再 decision_date),
            # 避免无谓的 RNG 流移位; 本次改动实质只是把决策日封顶在"今天"。
            underwriter_id = random.choice(underwriter_ids)
            # 决策日封顶在"今天" (修复 Review-04: decision_date 可晚于 TODAY)
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
    """生成理赔, 并对损失金额做 "赔付率标定" (修复 Review-01 P1)。

    标定模型:
      1. 出险概率 = RISK_TIER_CLAIM_PROB[risk_tier] —— 风险越高越易出险 (告别固定 0.55)。
      2. 每张出险保单设一个目标赔付率
             target_lr = 行业基准赔付率 × 风险等级损失乘数 × lognormal(0, 0.32)
         截断到 [0.05, 3.0]。它把损失和保费/风险/行业三者绑定。
      3. 申报损失预算 loss_budget = 年保费 × target_lr × CLAIMED_LOSS_INFLATION,
         在该保单的多笔 claim 间随机切分。
      4. 实赔 paid = 申报 × 赔付比例(0.60–0.95);已拒赔 / 在办(已立案/调查中/定损中)为 0。
    这样 "已付赔款 / 年保费" 的中位数回落到真实健康区间, 且随 risk_tier / 行业单调变化。
    """
    records = []
    cid = 1
    claim_types = ["财产损失", "人身伤害", "设备故障", "营业中断", "第三者责任",
                   "产品责任", "运输损失", "环境污染", "网络安全"]
    LOSS_MIN, LOSS_MAX = 20_000.0, 5_000_000.0
    for p in policies.iter_rows(named=True):
        risk_tier, industry = company_risk[p["company_id"]]
        # 1. 出险概率与公司风险等级挂钩
        if random.random() >= RISK_TIER_CLAIM_PROB[risk_tier]:
            continue
        eff = p["effective_date"]
        exp = min(p["expiration_date"], TODAY)
        if exp <= eff:
            continue
        n_claims = random.choices([1, 2, 3, 4], weights=[0.40, 0.32, 0.20, 0.08])[0]
        # 2. 该保单目标赔付率 (与行业基准 + 风险等级绑定)
        target_lr = (
            INDUSTRY_BASE_LOSS_RATIO[industry]
            * RISK_TIER_LOSS_MULT[risk_tier]
            * random.lognormvariate(0.0, 0.32)
        )
        target_lr = min(max(target_lr, 0.05), 3.0)
        premium = float(p["current_annual_premium_cny"])
        # 3. 申报损失预算, 在多笔 claim 间随机切分
        loss_budget = premium * target_lr * CLAIMED_LOSS_INFLATION
        shares = [random.random() + 0.15 for _ in range(n_claims)]
        s_sum = sum(shares)
        for k in range(n_claims):
            loss_amt = loss_budget * shares[k] / s_sum
            loss_amt = round(min(max(loss_amt, LOSS_MIN), LOSS_MAX), 2)
            incident = random_date(eff, exp)
            # 报案不晚于"今天" (修复 Review-01: 80 条 reported_date > TODAY)
            reported = min(incident + timedelta(days=random.randint(0, 14)), TODAY)
            status = weighted_choice(
                ["已立案", "调查中", "定损中", "已支付", "已结案", "已拒赔"],
                [0.05, 0.10, 0.10, 0.20, 0.45, 0.10]
            )
            # 4. 实赔: 仅已支付/已结案有赔款; 已拒赔(没赔一分钱)与在办均为 0
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
    """理赔生命周期事件"""
    records = []
    eid = 1
    # 事件序列模板 (按发生顺序)
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
        else:  # 已立案
            seq = in_progress_lifecycle[:2]

        base_date = c["reported_date"]
        base_dt = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=9)
        n = len(seq)
        # 1. 累计步长(天): 事件流严格按时间递增 (修复 Review-01: 76% event_date 逆序)
        steps = [0]
        for _ in range(1, n):
            steps.append(steps[-1] + random.randint(3, 14))
        total_span = steps[-1]
        # 2. 若整条生命周期会越过"今天", 整体等比压缩 (保持顺序与相对间隔, 不产生未来日期)
        max_span = max((TODAY - base_date).days, 0)
        scale = (max_span / total_span) if (total_span > 0 and total_span > max_span) else 1.0
        for i, et in enumerate(seq):
            # +i 分钟保证即使压缩到同日也严格递增
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
    """生成富文本理赔通讯, 带 signal_tag/sub_tag 用于 RAG/分类训练"""
    records = []
    cid = 1
    comm_types = ["邮件", "电话纪要", "调查笔记", "现场报告"]

    # 状态相关的类别分布调整 (拒赔/进行中更多争议信号)
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
        # 通讯时间累计推进 (comm_date ≥ reported_date), 并封顶在"今天"避免未来日期
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
            # author: 调查类多由 adjuster 写, 争议/拒赔由 underwriter 复核
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
                # 准备金调整日期累计推进, 封顶在"今天"
                "reserve_date": min(cur_date, TODAY),
                "reserve_amount_cny": round(amount, 2),
                "adjustment_reason": random.choice(reasons) if i > 0 else "首次定损依据初步估算",
            })
            rid += 1
    return pl.DataFrame(records)


def gen_invoices(policies: pl.DataFrame) -> pl.DataFrame:
    """每张保单生成 4 期 (季度) 账单"""
    records = []
    iid = 1
    for p in policies.iter_rows(named=True):
        # 季度账单, 共 4 期
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
            # 86% 准时, 10% 略晚, 4% 严重逾期
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
            # 部分逾期款项已部分支付
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
    """核保风险评分。

    修复 Review-01: 原 risk_score 在 [20,95] 纯随机, 与实际赔付率零相关, 使 B11
    "风险评分 vs 赔付率"失效。现以公司 risk_tier 对应的分数基准 (RISK_TIER_SCORE_BASE)
    为锚, 叠加高斯噪声; 由于 target_lr 也随 risk_tier 升高, risk_score 与赔付率正相关。
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
            # 以风险等级基准为锚 + 高斯噪声, 截断到 20-95
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
        None,  # 25% 无隐患
        None,
    ]
    statuses = ["已完成", "进行中", "未开始", "无需整改"]
    for lid in location_ids:
        if random.random() < 0.45:  # 45% 场所至少检查过一次
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
    """按 (公司 × 承保年度 × 险种) 汇总赔付率 (policy-year / 承保年度口径)。

    修复 Review-01:
      - 保费按"承保年度"(effective_date 所在年) 归属, 每张保单只计一次,
        不再 range(eff.year, exp.year+1) 跨年重复累加保费 (原"累计保费虚高约 2x")。
      - 损失统一为"已付赔款" SUM(paid_amount_cny): 已拒赔 / 在办自然为 0,
        删除原 `paid or loss*0.5` 的幽灵损失, 与 company.total_paid_claims / D3 / 17.4 同口径。
      - 不再丢弃 2026: 承保年度覆盖 2024 / 2025 / 2026, "近 3 年"名副其实。
    """
    records = []
    lrid = 1

    # 准备索引: claims by policy_id
    claims_by_policy: dict[int, list[dict]] = {}
    for c in claims.iter_rows(named=True):
        claims_by_policy.setdefault(c["policy_id"], []).append(c)

    # 按 (company, 承保年度, 险种) 聚合: 保费单计 + 该保单全部理赔的已付赔款
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
        for year in range(2021, 2027):  # 含 2026, 与 loss_run 承保年度对齐
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
        # 35% 公司至少有一次监管处罚
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
# 对账逻辑
# ============================================================================
def reconcile_policy_premium(
    policies: pl.DataFrame, premium_history: pl.DataFrame
) -> pl.DataFrame:
    """对账: policy.current_annual_premium_cny = 最新一条 premium_history.new_premium_cny"""
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
    """对账:
       company.total_active_premium_cny = SUM(policies WHERE status='有效')
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
# 主控函数 (幂等)
# ============================================================================

def generate_all_tsv() -> None:
    """生成全部 TSV 文件 (幂等: 先删除旧文件, 再生成)"""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("生成 (按拓扑顺序)...")

    # ---- 域 1: 组织 ----
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
    # company_id -> (risk_tier, industry): 供 claim / risk_assessment 做赔付率标定
    company_risk: dict[int, tuple[str, str]] = {
        row["company_id"]: (row["risk_tier"], row["industry"])
        for row in df_company.iter_rows(named=True)
    }
    # 暂不写出 (要先对账)
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

    # ---- 域 2: 保单 ----
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

    # 对账 policy.current_annual_premium_cny
    df_policy = reconcile_policy_premium(df_policy, df_premium_history)

    df_renewal = gen_renewal_decisions(df_policy, underwriter_ids)
    df_renewal.write_csv(DATA_DIR / "13_renewal_decision.tsv", separator="\t")
    print(f"  13_renewal_decision: {len(df_renewal)}")

    # ---- 域 3: 理赔 ----
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

    # ---- 域 4: 账单付款 ----
    df_invoice = gen_invoices(df_policy)
    df_invoice.write_csv(DATA_DIR / "18_invoice.tsv", separator="\t")
    print(f"  18_invoice: {len(df_invoice)}")

    df_payment = gen_payments(df_invoice)
    df_payment.write_csv(DATA_DIR / "19_payment.tsv", separator="\t")
    print(f"  19_payment: {len(df_payment)}")

    # ---- 域 5: 风险评估 ----
    df_risk = gen_risk_assessments(df_policy, underwriter_ids, company_risk)
    df_risk.write_csv(DATA_DIR / "20_risk_assessment.tsv", separator="\t")
    print(f"  20_risk_assessment: {len(df_risk)}")

    df_inspection = gen_site_inspections(location_ids)
    df_inspection.write_csv(DATA_DIR / "21_site_inspection.tsv", separator="\t")
    print(f"  21_site_inspection: {len(df_inspection)}")

    df_loss_run = gen_loss_runs(df_company, df_claim, df_policy)
    df_loss_run.write_csv(DATA_DIR / "22_loss_run.tsv", separator="\t")
    print(f"  22_loss_run: {len(df_loss_run)}")

    # ---- 域 6: 外部 ----
    df_reg = gen_regulatory_filings(company_ids)
    df_reg.write_csv(DATA_DIR / "23_regulatory_filing.tsv", separator="\t")
    print(f"  23_regulatory_filing: {len(df_reg)}")

    df_tpr = gen_third_party_reports(company_ids)
    df_tpr.write_csv(DATA_DIR / "24_third_party_report.tsv", separator="\t")
    print(f"  24_third_party_report: {len(df_tpr)}")

    # ---- 对账 company 聚合并最终写出 ----
    df_company = reconcile_company_aggregates(df_company, df_policy, df_claim)
    df_company.write_csv(DATA_DIR / "05_company.tsv", separator="\t")
    print(f"  05_company (含对账): {len(df_company)}")

    # 重新写 policy (保费已对账)
    df_policy.write_csv(DATA_DIR / "09_policy.tsv", separator="\t")
    print(f"  09_policy (含对账): {len(df_policy)}")

    # ---- 数据质量速览 (用生成器自带 print 即可验证关键修复, 无需额外脚本) ----
    print("\n[数据质量速览]")
    # 保单状态占比
    status_share = (
        df_policy.group_by("status").len().sort("len", descending=True)
    )
    share_txt = ", ".join(
        f"{r['status']} {r['len'] / len(df_policy) * 100:.1f}%"
        for r in status_share.iter_rows(named=True)
    )
    print(f"  policy.status 占比: {share_txt}")
    # loss_run 赔付率分布 (核心 KPI 真实性)
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
    # risk_tier → 平均已付赔款 (应单调递增)
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
    # 未来日期检查 (应全为 0)
    fut_reported = (df_claim["reported_date"] > TODAY).sum()
    fut_event = (df_claim_event["event_date"] > datetime.combine(TODAY, datetime.max.time())).sum()
    fut_decision = (df_renewal["decision_date"] > TODAY).sum()
    print(
        f"  晚于今天的 reported_date={fut_reported}, claim_event.event_date={fut_event}, "
        f"renewal_decision.decision_date={fut_decision} (应均为 0)"
    )
    # renewal_decision 年份分布 (B10 依赖: 决策年最早 2025)
    rd_years = (
        df_renewal.with_columns(pl.col("decision_date").dt.year().alias("y"))
        .group_by("y").len().sort("y")
    )
    print("  renewal_decision 决策年分布: "
          + ", ".join(f"{r['y']}:{r['len']}" for r in rd_years.iter_rows(named=True)))

    # 行数统计
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
    """从 TSV 创建 SQLite (幂等)"""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 加载顺序 (拓扑序)
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
            # 批量插入
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
