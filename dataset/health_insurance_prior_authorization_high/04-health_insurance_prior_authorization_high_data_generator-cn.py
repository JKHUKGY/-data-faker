"""
健康保险 — 事前授权运营 假数据生成器。

业务背景
========
Meridian Health Plan 是一家虚构的区域性健康保险支付方,总部位于德州
奥斯汀,服务约 25 万名 ACA 个险交易所会员,产品覆盖 Bronze、Silver、
Gold、Platinum 四个金属层级和 HMO、PPO、EPO 三条产品线。本数据集是从
该生产业务簿里刻意抽小的一份分析样本(仅 400 名会员),覆盖截至 TODAY
(生成时的 `date.today()`)往前 12 个月的事前授权(PA)运营历史。

已应用的第二轮评审修复
======================
* 层级感知的成本分担:claims.member_responsibility_usd 由会员所在金属
  层级推导(Bronze 自付约 30%、Platinum 约 12%),而非一刀切的均匀抽样。
* 层级感知的批准率:pa_requests.status 权重按层级缩放,使 Bronze 的决定
  偏向拒绝、Platinum 偏向批准。
* pending 状态的时间闸门:一条请求只有在按其紧急度足够新近提交时才会
  停留在 `pending` / `in_review`(routine 14 天、urgent 3 天、emergent
  4 小时)。更老的开放请求被强制推进到终态。
* decided_at 钳制:决定时间戳永不超过 TODAY。
* 药品类政策:gen_payer_policies 在匹配类别时同时考虑 CPT 与 HCPCS 码,
  所以药品类(HCPCS J 码)政策得以存在。
* 专科与操作的相关性:Orthopedics 的 provider 多提交骨科 CPT;Oncology
  的 provider 多提交肿瘤科 CPT;以此类推。
* provider 名称与类型对齐:Hospital / Clinic / Surgical Center 一律用
  机构式名称;Physician / Specialist 一律用 Dr. {name}。
* 幂律请求分布:会员和 provider 的请求量服从类 Zipf 幂律,所以会存在
  少数"高频"会员和"高量"provider(Q19 / Q26 终于有信号)。
* 拒绝码 Pareto 权重:N-130 与 CO-50 占主导;其余是长尾 —— Q30 的
  pareto_class 列因此变得有意义。
* 新增派生列:pa_decisions.tat_hours 与 pa_decisions.sla_breached 把
  SLA 计算物化下来;payer_policies.category 取代了脆弱的 policy_id LIKE
  模式;appeals 在可读的 appeal_level 文本之外新增 level_number 与
  is_external_review。

关键不变量(强制保证)
======================
* members.plan_end_date > members.plan_start_date。
* pa_requests.submitted_at 落在 [plan_start_date, min(plan_end_date, TODAY)) 内。
* clinical_notes.note_date <= DATE(submitted_at)。
* pa_decisions.decided_at 落在 (submitted_at, TODAY] 内。
* claims.service_date 落在 [decided_at, TODAY) 内。
* appeals.submitted_at >= pa_decisions.decided_at。
* pa_decisions.request_id 唯一(与 pa_requests 为 1:1)。
* status 与 decision 的对照(见 _draw_decision_for_status)。
* appeals 只挂在 denied 上;claims 只挂在 approved/partial_approved 上。
* 对每条请求,pa_decisions.applied_policy_id(填充时)引用一条在
  decided_at 当天生效、其操作码与请求的 CPT/HCPCS 条目有交集、且层级
  限定与会员匹配的政策。

SQLite 存储约定
===============
SQLite 没有原生 ARRAY / JSONB / UUID。数组以 JSON TEXT 存储(用
json_each 展开)。UUID 用 VARCHAR(36)。布尔值用 INTEGER 0/1。
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

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
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "health_insurance_prior_authorization_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# TODAY 在生成时解析,这样滚动窗口查询
# (`DATE('now', '-30 days')` 之类) 总能相对运行查询的系统时钟拿到新鲜数据。
# 同一日历日内由 RANDOM_SEED 保证可复现;跨天则各行内容平移,
# 但行数和分布保持稳定。
TODAY = date.today()
TODAY_DT = datetime.combine(TODAY, time(0, 0))
HISTORY_START = TODAY - timedelta(days=365)

# 目标行数。N_PLAN = 12 是因为我们正好覆盖 4 个层级 × 3 条产品线各一次。
N_PLAN     = 12
N_PROVIDER = 150
N_REVIEWER = 30
N_SERVICE  = 100
N_POLICY   = 50
N_MEMBER   = 400
N_REQUEST  = 700

# ------- 层级感知的状态权重 (每个层级合计为 100) -------
# Bronze 计划拒得更多,Platinum 批得更多。每个层级仍允许同一组状态,
# 只是权重不同。
TIER_STATUS_WEIGHTS = {
    "Bronze":   {"approved": 35, "partial_approved_status": 5, "denied": 30, "pended": 10,
                 "appealed": 6, "in_review": 5, "pending": 5, "withdrawn": 4},
    "Silver":   {"approved": 45, "partial_approved_status": 5, "denied": 22, "pended": 8,
                 "appealed": 6, "in_review": 5, "pending": 5, "withdrawn": 4},
    "Gold":     {"approved": 55, "partial_approved_status": 5, "denied": 15, "pended": 7,
                 "appealed": 5, "in_review": 5, "pending": 5, "withdrawn": 3},
    "Platinum": {"approved": 62, "partial_approved_status": 6, "denied": 10, "pended": 5,
                 "appealed": 4, "in_review": 5, "pending": 5, "withdrawn": 3},
}
# 按紧急度划分的 pending / in_review 窗口 (小时)。这是活跃池提交时间的
# 上界 (见下方 ACTIVE_QUOTA)。
PENDING_WINDOW_HOURS = {"routine": 14 * 24, "urgent": 3 * 24, "emergent": 4}

# 预留的活跃请求池。没有它的话,365 天历史上 5% 的 pending 权重到窗口
# 末尾几乎产出不了 `pending` / `in_review` 行,会让 Q18 (开放队列) 和
# Q29 (滞留) 没有数据可展示。先填满活跃池,其余请求走常规的层级感知
# 状态抽样,且强制关闭 pending / in_review。
ACTIVE_QUOTA = {"routine": 50, "urgent": 15, "emergent": 5}
ACTIVE_STATUS_WEIGHTS = {"pending": 0.6, "in_review": 0.4}
# 一小部分 (10%) 活跃池提交会滑出紧急度窗口,为 Q29 播下"超 SLA 滞留"
# 的案例种子。
ACTIVE_STALLED_RATE = 0.10

# 按层级的会员成本分担 (占 allowed 金额的百分比)。Bronze 会员自付最多,
# Platinum 最少。
TIER_MEMBER_PCT = {
    "Bronze":   (0.28, 0.32),
    "Silver":   (0.22, 0.26),
    "Gold":     (0.15, 0.20),
    "Platinum": (0.10, 0.15),
}

APPROVED_DECISION_WEIGHTS = {"approved": 0.90, "partial_approved": 0.10}
PENDED_DECISION_WEIGHTS   = {"pended": 0.75, "escalated": 0.25}

URGENCY_WEIGHTS = {"routine": 0.70, "urgent": 0.25, "emergent": 0.05}
SOURCE_CHANNEL_WEIGHTS = {"portal": 0.45, "ehr_api": 0.30, "fax": 0.20, "phone": 0.05}

SLA_HOURS = {"routine": 336, "urgent": 72, "emergent": 2}

METAL_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
PRODUCT_LINES = ["HMO", "PPO", "EPO"]
NETWORK_TYPES = {"HMO": "Closed", "PPO": "Open", "EPO": "Restricted"}

SPECIALTIES = [
    "Orthopedics", "Oncology", "Cardiology", "Neurology",
    "Gastroenterology", "Dermatology", "Psychiatry", "General Surgery",
    "Radiology", "Pain Management",
]
PROVIDER_TYPES_ORG = ["Hospital", "Clinic", "Surgical Center"]
PROVIDER_TYPES_IND = ["Physician", "Specialist"]
PROVIDER_TYPE_WEIGHTS = {
    "Physician": 0.45, "Specialist": 0.20, "Hospital": 0.15,
    "Clinic": 0.15, "Surgical Center": 0.05,
}

# 把 provider 专科映射到该专科现实中会提交 PA 请求的 service_catalog
# 类别。gen_request_clinical_items 用它,让 Q13 (按专科的拒绝率) 有真实
# 信号。
SPECIALTY_TO_CATEGORIES = {
    "Orthopedics":      ["orthopedic", "pain_management"],
    "Oncology":         ["oncology", "pharmacy"],
    "Cardiology":       ["cardiac"],
    "Neurology":        ["imaging", "behavioral_health"],
    "Gastroenterology": ["gastroenterology"],
    "Dermatology":      ["general_surgery"],
    "Psychiatry":       ["behavioral_health", "pharmacy"],
    "General Surgery":  ["general_surgery", "orthopedic"],
    "Radiology":        ["imaging"],
    "Pain Management":  ["pain_management", "orthopedic"],
}

REVIEWER_ROLES = [
    ("auto_rule",          0.40),
    ("clinical_reviewer",  0.35),
    ("medical_director",   0.15),
    ("external_reviewer",  0.10),
]

SERVICE_CATEGORIES = [
    "orthopedic", "oncology", "cardiac", "behavioral_health",
    "imaging", "pharmacy", "general_surgery", "gastroenterology",
    "pain_management",
]

SERVICE_CATALOG_SEED = [
    # CPT 骨科
    ("27447", "CPT",   "Total knee arthroplasty",                       "orthopedic"),
    ("27130", "CPT",   "Total hip arthroplasty",                        "orthopedic"),
    ("23472", "CPT",   "Total shoulder arthroplasty",                   "orthopedic"),
    ("29881", "CPT",   "Knee arthroscopy with meniscectomy",            "orthopedic"),
    ("63030", "CPT",   "Lumbar laminotomy",                             "orthopedic"),
    ("22612", "CPT",   "Lumbar arthrodesis (spinal fusion)",            "orthopedic"),
    # CPT 心脏
    ("33533", "CPT",   "Coronary artery bypass, single graft",          "cardiac"),
    ("33208", "CPT",   "Insertion of dual chamber pacemaker",           "cardiac"),
    ("93458", "CPT",   "Cardiac catheterization, left heart",           "cardiac"),
    ("92928", "CPT",   "Percutaneous transluminal coronary stent",      "cardiac"),
    # CPT 肿瘤
    ("96413", "CPT",   "Chemotherapy IV infusion, 1 hour",              "oncology"),
    ("77301", "CPT",   "Intensity modulated radiation therapy plan",    "oncology"),
    ("19301", "CPT",   "Partial mastectomy",                            "oncology"),
    ("38525", "CPT",   "Biopsy of deep axillary lymph node",            "oncology"),
    # CPT 消化
    ("43239", "CPT",   "Upper GI endoscopy with biopsy",                "gastroenterology"),
    ("45378", "CPT",   "Diagnostic colonoscopy",                        "gastroenterology"),
    ("47562", "CPT",   "Laparoscopic cholecystectomy",                  "gastroenterology"),
    # CPT 影像
    ("70551", "CPT",   "MRI brain without contrast",                    "imaging"),
    ("72148", "CPT",   "MRI lumbar spine without contrast",             "imaging"),
    ("73721", "CPT",   "MRI lower extremity joint without contrast",    "imaging"),
    ("78815", "CPT",   "PET/CT skull base to mid-thigh",                "imaging"),
    # CPT 行为健康
    ("90837", "CPT",   "Psychotherapy, 60 minutes",                     "behavioral_health"),
    ("90867", "CPT",   "Transcranial magnetic stimulation, initial",    "behavioral_health"),
    # CPT 普外科
    ("44970", "CPT",   "Laparoscopic appendectomy",                     "general_surgery"),
    ("49585", "CPT",   "Umbilical hernia repair",                       "general_surgery"),
    # CPT 药品静脉输注 (给药编码)
    ("96365", "CPT",   "IV infusion, initial up to 1 hour",             "pharmacy"),
    ("96367", "CPT",   "IV infusion additional sequential drug",        "pharmacy"),
    # HCPCS 药品 (特药)
    ("J0129", "HCPCS", "Abatacept injection, 10 mg",                    "pharmacy"),
    ("J1745", "HCPCS", "Infliximab injection, 10 mg",                   "pharmacy"),
    ("J9035", "HCPCS", "Bevacizumab injection, 10 mg",                  "pharmacy"),
    ("J2350", "HCPCS", "Ocrelizumab injection, 1 mg",                   "pharmacy"),
    ("Q5103", "HCPCS", "Infliximab-dyyb biosimilar, 10 mg",             "pharmacy"),
    # HCPCS 影像造影剂
    ("Q9967", "HCPCS", "Low osmolar contrast, 350 mg/ml",               "imaging"),
    # ICD-10 骨科
    ("M17.11", "ICD10", "Unilateral primary osteoarthritis, right knee", "orthopedic"),
    ("M17.12", "ICD10", "Unilateral primary osteoarthritis, left knee",  "orthopedic"),
    ("M16.11", "ICD10", "Unilateral primary osteoarthritis, right hip",  "orthopedic"),
    ("M54.5",  "ICD10", "Low back pain",                                 "orthopedic"),
    # ICD-10 心脏
    ("I25.10", "ICD10", "Atherosclerotic heart disease without angina",  "cardiac"),
    ("I25.110", "ICD10", "Atherosclerotic heart disease with unstable angina", "cardiac"),
    ("I50.22", "ICD10", "Chronic systolic heart failure",                "cardiac"),
    ("I48.91", "ICD10", "Unspecified atrial fibrillation",               "cardiac"),
    # ICD-10 肿瘤
    ("C50.911", "ICD10", "Malignant neoplasm of unspecified site, right breast", "oncology"),
    ("C61",     "ICD10", "Malignant neoplasm of prostate",               "oncology"),
    ("C34.91",  "ICD10", "Malignant neoplasm of right lung",             "oncology"),
    ("C18.9",   "ICD10", "Malignant neoplasm of colon, unspecified",     "oncology"),
    # ICD-10 行为健康
    ("F33.1",  "ICD10", "Major depressive disorder, recurrent, moderate", "behavioral_health"),
    ("F41.1",  "ICD10", "Generalized anxiety disorder",                  "behavioral_health"),
    ("F31.10", "ICD10", "Bipolar disorder, current episode manic",       "behavioral_health"),
    # ICD-10 消化
    ("K21.9",  "ICD10", "GERD without esophagitis",                      "gastroenterology"),
    ("K80.20", "ICD10", "Calculus of gallbladder without cholecystitis", "gastroenterology"),
    ("K57.30", "ICD10", "Diverticulosis of large intestine",             "gastroenterology"),
    # ICD-10 影像驱动的检查
    ("R51.9",   "ICD10", "Headache, unspecified",                         "imaging"),
    ("G43.909", "ICD10", "Migraine, unspecified, not intractable",        "imaging"),
    # ICD-10 其他
    ("E11.9",  "ICD10", "Type 2 diabetes mellitus without complications", "general_surgery"),
    ("E11.65", "ICD10", "Type 2 diabetes mellitus with hyperglycemia",    "general_surgery"),
    ("J45.909", "ICD10", "Asthma, unspecified",                          "behavioral_health"),
    ("N40.1",  "ICD10", "Benign prostatic hyperplasia with LUTS",        "general_surgery"),
    # 更多 CPT / 耗材
    ("20610", "CPT",   "Major joint injection",                          "orthopedic"),
    ("29826", "CPT",   "Shoulder arthroscopy with decompression",        "orthopedic"),
    ("64483", "CPT",   "Transforaminal epidural injection, lumbar",      "pain_management"),
    ("64493", "CPT",   "Facet joint injection, lumbar, single level",    "pain_management"),
    ("74183", "CPT",   "MRI abdomen with and without contrast",          "imaging"),
    ("71260", "CPT",   "CT thorax with contrast",                        "imaging"),
    ("76700", "CPT",   "Abdominal ultrasound complete",                  "imaging"),
    ("90834", "CPT",   "Psychotherapy, 45 minutes",                      "behavioral_health"),
    ("90791", "CPT",   "Psychiatric diagnostic evaluation",              "behavioral_health"),
    ("93306", "CPT",   "Transthoracic echocardiogram, complete",         "cardiac"),
    ("93000", "CPT",   "Electrocardiogram, complete",                    "cardiac"),
    ("77386", "CPT",   "IMRT treatment delivery, complex",               "oncology"),
    ("E0143", "HCPCS", "Walker, folding, wheeled, without seat",         "orthopedic"),
    ("E0260", "HCPCS", "Hospital bed, semi-electric",                    "general_surgery"),
    ("L1845", "HCPCS", "Knee orthosis, double upright",                  "orthopedic"),
    ("K0001", "HCPCS", "Standard wheelchair",                            "orthopedic"),
    ("44140", "CPT",   "Partial colectomy with anastomosis",             "gastroenterology"),
    ("43775", "CPT",   "Laparoscopic sleeve gastrectomy",                "general_surgery"),
    ("47563", "CPT",   "Laparoscopic cholecystectomy with cholangiography", "general_surgery"),
    ("19120", "CPT",   "Excision of breast lesion",                      "oncology"),
    ("M79.604", "ICD10", "Pain in right leg",                            "pain_management"),
    ("M25.561", "ICD10", "Pain in right knee",                           "orthopedic"),
    ("Z01.419", "ICD10", "Routine gynecological exam without abnormal findings", "general_surgery"),
    ("R10.9",   "ICD10", "Unspecified abdominal pain",                   "gastroenterology"),
    ("R07.9",   "ICD10", "Chest pain, unspecified",                      "cardiac"),
    ("R55",     "ICD10", "Syncope and collapse",                         "cardiac"),
    ("R42",     "ICD10", "Dizziness and giddiness",                      "imaging"),
    ("R53.83",  "ICD10", "Other fatigue",                                "general_surgery"),
    ("M48.06",  "ICD10", "Spinal stenosis, lumbar region",               "orthopedic"),
    ("M51.36",  "ICD10", "Lumbar disc degeneration",                     "orthopedic"),
    ("S83.511A", "ICD10", "ACL sprain, right knee, initial encounter",   "orthopedic"),
    ("M75.101", "ICD10", "Unspecified rotator cuff tear, right shoulder", "orthopedic"),
    ("N18.3",   "ICD10", "Chronic kidney disease, stage 3",              "general_surgery"),
    ("E66.01",  "ICD10", "Morbid obesity",                               "general_surgery"),
    ("F32.9",   "ICD10", "Major depressive disorder, single episode",    "behavioral_health"),
    ("F90.0",   "ICD10", "ADHD, predominantly inattentive type",         "behavioral_health"),
    ("F43.10",  "ICD10", "Post-traumatic stress disorder, unspecified",  "behavioral_health"),
    ("C25.9",   "ICD10", "Malignant neoplasm of pancreas, unspecified",  "oncology"),
    ("C71.9",   "ICD10", "Malignant neoplasm of brain, unspecified",     "oncology"),
    ("Z51.11",  "ICD10", "Encounter for antineoplastic chemotherapy",    "oncology"),
    ("D63.0",   "ICD10", "Anemia in neoplastic disease",                 "oncology"),
    ("K58.9",   "ICD10", "Irritable bowel syndrome without diarrhea",    "gastroenterology"),
    ("K92.2",   "ICD10", "Gastrointestinal hemorrhage, unspecified",     "gastroenterology"),
    ("E03.9",   "ICD10", "Hypothyroidism, unspecified",                  "general_surgery"),
]
SERVICE_CATALOG_SEED = SERVICE_CATALOG_SEED[:N_SERVICE]

# 拒绝码带 Pareto 式权重,好让 Q30 的 vital_few / trivial_many 划分能呈现
# 清晰的形状。
DENIAL_CODES = [
    ("N-130",  "Consult plan benefit documents for services",       42),
    ("CO-50",  "Service is not medically necessary",                34),
    ("CO-97",  "Procedure benefit not separately payable",          18),
    ("N-657",  "Service not covered - step therapy required",       14),
    ("CO-167", "Diagnosis not covered",                              9),
    ("CO-204", "Service not covered under current benefit plan",     6),
    ("CO-22",  "Care may be covered by another payer",               4),
    ("N-115",  "Determination based on local coverage policy",       3),
    ("CO-16",  "Claim lacks information needed for adjudication",    2),
]
DENIAL_CODE_KEYS    = [c for c, _, _ in DENIAL_CODES]
DENIAL_CODE_WEIGHTS = [w for _, _, w in DENIAL_CODES]
DENIAL_CODE_REASON  = {c: t for c, t, _ in DENIAL_CODES}

CRITERIA_KEYS = [
    "conservative_treatment_3mo",
    "imaging_grade_iv_evidence",
    "bmi_under_40",
    "no_contraindications",
    "step_therapy_complete",
    "medical_necessity_documented",
    "primary_diagnosis_confirmed",
    "in_plan_benefit",
]


# ============================================================================
# 辅助函数
# ============================================================================
def weighted_choice(weights: dict) -> str:
    keys = list(weights.keys())
    vals = [weights[k] for k in keys]
    return random.choices(keys, weights=vals, k=1)[0]


def rand_dt_between(start: datetime, end: datetime) -> datetime:
    if end <= start:
        return start
    delta = end - start
    secs = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=secs)


def to_json(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str)


def bucketed_pareto_weights(n: int,
                             top_pct: float = 0.10, top_weight: float = 4.0,
                             mid_pct: float = 0.40, mid_weight: float = 2.0,
                             tail_weight: float = 1.0) -> list[float]:
    """三桶 Pareto 式权重。用默认值时,顶部 10% 的实体大约拿到 25-30% 的
    抽样,中间 40% 再拿 45-50%,底部 50% 拿余下部分。这是一个可信的业务簿
    形态,又不至于像原始 Zipf 分布那样集中失控。"""
    n_top = max(1, int(n * top_pct))
    n_mid = max(1, int(n * mid_pct))
    n_tail = n - n_top - n_mid
    return ([top_weight] * n_top) + ([mid_weight] * n_mid) + ([tail_weight] * n_tail)


# 历史池不再把老请求漏回 pending / in_review 状态 —— 活跃池
# (ACTIVE_QUOTA 加 ACTIVE_STALLED_RATE) 承担全部滞留案例预算。把它设为 0
# 可避免早先评审指出的那些约 320 天的历史残留。
STALLED_TAIL_RATE = 0.0


def clamp_to_today(dt: datetime) -> datetime:
    """把生成的时间戳封顶到 TODAY。上界在今天的工作时段内随机化,这样少数
    被钳制的行不会都挤在 00:00:00 这一个瞬间 (那样在排序后的演示界面上会
    一眼看出是合成的)。"""
    upper = datetime.combine(
        TODAY,
        time(random.randint(9, 17), random.randint(0, 59), random.randint(0, 59)),
    )
    return min(dt, upper)


# ============================================================================
# ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    pass


class Plan(Base):
    __tablename__ = "plans"

    plan_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metal_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    product_line: Mapped[str] = mapped_column(String(10), nullable=False)
    network_type: Mapped[str] = mapped_column(String(20), nullable=False)
    deductible_usd: Mapped[int] = mapped_column(Integer, nullable=False)
    out_of_pocket_max_usd: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_premium_usd: Mapped[int] = mapped_column(Integer, nullable=False)


class Member(Base):
    __tablename__ = "members"

    member_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(1))
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(20), ForeignKey("plans.plan_id"))
    plan_start_date: Mapped[date] = mapped_column(Date)
    plan_end_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Provider(Base):
    __tablename__ = "providers"

    npi: Mapped[str] = mapped_column(String(10), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50))
    specialty: Mapped[str] = mapped_column(String(50))
    tax_id: Mapped[str | None] = mapped_column(String(20))
    in_network: Mapped[bool] = mapped_column(Boolean)


class Reviewer(Base):
    __tablename__ = "reviewers"

    reviewer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    reviewer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    department: Mapped[str] = mapped_column(String(60))
    hired_date: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean)


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    service_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    code_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    avg_billed_amount_usd: Mapped[int] = mapped_column(Integer)


class SlaConfig(Base):
    __tablename__ = "sla_config"

    urgency: Mapped[str] = mapped_column(String(20), primary_key=True)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    regulatory_basis: Mapped[str] = mapped_column(String(120))


class PayerPolicy(Base):
    __tablename__ = "payer_policies"

    policy_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    policy_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    cpt_codes_json: Mapped[str] = mapped_column(Text)
    icd10_codes_json: Mapped[str] = mapped_column(Text)
    applies_to_metal_tier: Mapped[str | None] = mapped_column(String(20))
    effective_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    document_s3_key: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class PARequest(Base):
    __tablename__ = "pa_requests"

    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.member_id"))
    provider_npi: Mapped[str] = mapped_column(String(10), ForeignKey("providers.npi"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_request_text: Mapped[str | None] = mapped_column(Text)
    source_channel: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class RequestClinicalItem(Base):
    __tablename__ = "request_clinical_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("pa_requests.request_id"))
    service_code: Mapped[str] = mapped_column(String(20))
    code_type: Mapped[str] = mapped_column(String(10))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sequence_num: Mapped[int] = mapped_column(Integer)


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    note_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("pa_requests.request_id"))
    note_type: Mapped[str] = mapped_column(String(50))
    note_content: Mapped[str] = mapped_column(Text, nullable=False)
    note_date: Mapped[date] = mapped_column(Date)
    authored_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ExtractedClinicalFact(Base):
    __tablename__ = "extracted_clinical_facts"

    fact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("pa_requests.request_id"))
    fact_category: Mapped[str] = mapped_column(String(50), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(200), nullable=False)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_source: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    extracted_at: Mapped[datetime] = mapped_column(DateTime)


class PADecision(Base):
    __tablename__ = "pa_decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("pa_requests.request_id"), unique=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_reason_code: Mapped[str | None] = mapped_column(String(50))
    decision_reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    criteria_met_json: Mapped[str] = mapped_column(Text)
    denial_codes_json: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float)
    reviewer_id: Mapped[str] = mapped_column(String(20), ForeignKey("reviewers.reviewer_id"))
    applied_policy_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("payer_policies.policy_id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tat_hours: Mapped[float] = mapped_column(Float, nullable=False)
    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Appeal(Base):
    __tablename__ = "appeals"

    appeal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("pa_decisions.decision_id"))
    appeal_level: Mapped[str] = mapped_column(String(20), nullable=False)
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_external_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    overturned: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_by: Mapped[str] = mapped_column(String(30))


class AppealLetter(Base):
    __tablename__ = "appeal_letters"

    letter_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    appeal_id: Mapped[str] = mapped_column(String(36), ForeignKey("appeals.appeal_id"))
    letter_content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    review_status: Mapped[str] = mapped_column(String(20))
    reviewed_by: Mapped[str | None] = mapped_column(String(200))


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("pa_decisions.decision_id"))
    member_id: Mapped[str] = mapped_column(String(20), ForeignKey("members.member_id"))
    service_date: Mapped[date] = mapped_column(Date)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    billed_amount_usd: Mapped[float] = mapped_column(Float)
    allowed_amount_usd: Mapped[float] = mapped_column(Float)
    paid_amount_usd: Mapped[float] = mapped_column(Float)
    member_responsibility_usd: Mapped[float] = mapped_column(Float)
    claim_status: Mapped[str] = mapped_column(String(20))


# ============================================================================
# 参考维度表
# ============================================================================
def gen_plans() -> pl.DataFrame:
    """4 个金属层级 × 3 条产品线 = 12 个不同的计划。"""
    tier_economics = {
        "Bronze":   (7_500, 9_450, 320),
        "Silver":   (5_000, 8_500, 480),
        "Gold":     (1_500, 6_500, 640),
        "Platinum": (300,   3_500, 820),
    }
    rows = []
    counter = 1
    for tier, product in [(t, p) for t in METAL_TIERS for p in PRODUCT_LINES]:
        deductible, oop, premium = tier_economics[tier]
        rows.append({
            "plan_id": f"PLAN-{tier[:3].upper()}-{product}-{counter:03d}",
            "plan_name": f"Meridian {tier} {product} 2026",
            "metal_tier": tier,
            "product_line": product,
            "network_type": NETWORK_TYPES[product],
            "deductible_usd": deductible + random.randint(-200, 200),
            "out_of_pocket_max_usd": oop + random.randint(-500, 500),
            "monthly_premium_usd": premium + random.randint(-40, 60),
        })
        counter += 1
    return pl.DataFrame(rows)


def gen_providers() -> pl.DataFrame:
    """provider 名称现在与 provider_type 一致:
    Hospital / Clinic / Surgical Center -> fake.company()。
    Physician / Specialist             -> 'Dr. {fake.name()}'。
    """
    rows = []
    for i in range(1, N_PROVIDER + 1):
        ptype = weighted_choice(PROVIDER_TYPE_WEIGHTS)
        if ptype in PROVIDER_TYPES_ORG:
            suffix = {"Hospital": "Hospital", "Clinic": "Clinic", "Surgical Center": "Surgical Center"}[ptype]
            name = f"{fake.last_name()} {suffix}"
            if random.random() < 0.4:
                name = fake.company()
        else:
            name = f"Dr. {fake.name()}"
        rows.append({
            "npi": f"{1000000000 + i}",
            "provider_name": name,
            "provider_type": ptype,
            "specialty": random.choice(SPECIALTIES),
            "tax_id": f"{random.randint(10, 99)}-{random.randint(1000000, 9999999)}",
            "in_network": random.random() < 0.85,
        })
    return pl.DataFrame(rows)


def gen_reviewers() -> pl.DataFrame:
    rows = []
    role_weights = {r: w for r, w in REVIEWER_ROLES}
    departments = ["Medical Review", "Pharmacy Review", "Behavioral Health Review",
                   "Specialty Review", "Appeals Review"]
    for i in range(1, N_REVIEWER + 1):
        role = weighted_choice(role_weights)
        if role == "auto_rule":
            name = f"AUTO_RULE_ENGINE_v{random.randint(1, 4)}.{random.randint(0, 12)}"
            dept = "Automation"
            hired = TODAY - timedelta(days=random.randint(180, 1500))
        else:
            name = f"Dr. {fake.last_name()}" if role in ("medical_director", "external_reviewer") \
                   else f"{fake.first_name()} {fake.last_name()}, RN"
            dept = random.choice(departments)
            hired = TODAY - timedelta(days=random.randint(90, 3600))
        rows.append({
            "reviewer_id": f"REV-{i:04d}",
            "reviewer_name": name,
            "role": role,
            "department": dept,
            "hired_date": hired,
            "active": random.random() < 0.92,
        })
    return pl.DataFrame(rows)


def gen_service_catalog() -> pl.DataFrame:
    bill_bands = {"CPT": (800, 35_000), "HCPCS": (200, 18_000), "ICD10": (0, 0)}
    rows = []
    for code, code_type, desc, category in SERVICE_CATALOG_SEED:
        low, high = bill_bands[code_type]
        avg_bill = random.randint(low, high) if high > 0 else 0
        rows.append({
            "service_code": code,
            "code_type": code_type,
            "description": desc,
            "category": category,
            "avg_billed_amount_usd": avg_bill,
        })
    return pl.DataFrame(rows)


def gen_sla_config() -> pl.DataFrame:
    return pl.DataFrame([
        {"urgency": "routine",  "sla_hours": SLA_HOURS["routine"],
         "regulatory_basis": "CMS standard PA - 14 calendar days"},
        {"urgency": "urgent",   "sla_hours": SLA_HOURS["urgent"],
         "regulatory_basis": "CMS expedited PA - 72 hours"},
        {"urgency": "emergent", "sla_hours": SLA_HOURS["emergent"],
         "regulatory_basis": "Internal emergent SLA - 2 hours"},
    ])


def gen_payer_policies(service_df: pl.DataFrame) -> pl.DataFrame:
    """政策的 cpt_codes_json 现在同时包含该类别的 CPT 和 HCPCS 操作码
    (这样使用 HCPCS J 码的药品类政策才会存在)。新增一个显式的 `category`
    列,让 Q21 不必再解析 policy_id。"""
    proc_by_cat: dict[str, list[str]] = {}  # 该类别的 CPT 加 HCPCS
    icd_by_cat:  dict[str, list[str]] = {}
    for row in service_df.iter_rows(named=True):
        if row["code_type"] in ("CPT", "HCPCS"):
            proc_by_cat.setdefault(row["category"], []).append(row["service_code"])
        elif row["code_type"] == "ICD10":
            icd_by_cat.setdefault(row["category"], []).append(row["service_code"])
    categories = [c for c, codes in proc_by_cat.items() if codes]

    # 按类别计数,让政策 ID 保持确定且可读。
    counters: dict[str, int] = {c: 0 for c in categories}
    rows = []
    for i in range(N_POLICY):
        category = random.choice(categories)
        counters[category] += 1
        idx = counters[category]
        proc_pool = proc_by_cat[category]
        icd_pool  = icd_by_cat.get(category, [])
        proc_sample = random.sample(proc_pool, k=min(len(proc_pool), random.randint(1, 3)))
        icd_sample  = random.sample(icd_pool,  k=min(len(icd_pool),  random.randint(1, 4))) if icd_pool else []
        tier_scope = random.choice([None, None, None, "Bronze", "Silver", "Gold", "Platinum"])
        eff = TODAY - timedelta(days=random.randint(180, 900))
        exp = eff + timedelta(days=random.randint(540, 1100))
        rows.append({
            "policy_id": f"POL-{category[:3].upper()}-{idx:04d}",
            "policy_name": f"{category.replace('_', ' ').title()} Coverage Policy",
            "category": category,
            "cpt_codes_json": to_json(proc_sample),
            "icd10_codes_json": to_json(icd_sample),
            "applies_to_metal_tier": tier_scope,
            "effective_date": eff,
            "expiry_date": exp,
            "document_s3_key": f"s3://meridian-policies/{category}/{uuid.uuid4().hex[:12]}.pdf",
            "version": random.randint(1, 5),
        })
    return pl.DataFrame(rows)


# ============================================================================
# 会员
# ============================================================================
# Meridian Health Plan 会员的居住州分布。德州占主导 (总部在奥斯汀的区域
# 性支付方),其余 30% 分散在它销售的四个邻州。
MEMBER_STATE_WEIGHTS = {"TX": 0.70, "OK": 0.08, "LA": 0.08, "AR": 0.07, "NM": 0.07}


def gen_members(plan_ids: list[str]) -> pl.DataFrame:
    rows = []
    for i in range(1, N_MEMBER + 1):
        is_active = random.random() < 0.95
        start = TODAY - timedelta(days=random.randint(30, 365 * 3))
        if is_active:
            end = TODAY + timedelta(days=random.randint(30, 365))
        else:
            end = TODAY - timedelta(days=random.randint(30, 365))
            if end <= start:
                end = start + timedelta(days=365)
        gender = random.choices(["M", "F", "U"], weights=[0.49, 0.49, 0.02], k=1)[0]
        dob = fake.date_of_birth(minimum_age=18, maximum_age=85)
        rows.append({
            "member_id": f"MEM{i:06d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "date_of_birth": dob,
            "gender": gender,
            "state": weighted_choice(MEMBER_STATE_WEIGHTS),
            "plan_id": random.choice(plan_ids),
            "plan_start_date": start,
            "plan_end_date": end,
            "created_at": datetime.combine(start, time(0, 0)),
        })
    return pl.DataFrame(rows)


# ============================================================================
# PA 请求
# ============================================================================
def _draw_historical_status(tier: str, urgency: str, age_hours: float) -> str:
    """*历史* 池的状态抽样 (活跃池单独处理)。pending / in_review 从权重池
    里移除,只留一个很小的 STALLED_TAIL_RATE 来播下被遗忘的案例。

    Bronze 会员拒得更多,Platinum 会员批得更多。
    """
    weights = dict(TIER_STATUS_WEIGHTS[tier])
    window = PENDING_WINDOW_HOURS[urgency]
    if age_hours > window and random.random() > STALLED_TAIL_RATE:
        weights["pending"] = 0
        weights["in_review"] = 0
    raw = weighted_choice(weights)
    return "approved" if raw == "partial_approved_status" else raw


def _draw_decision_for_status(status: str, tier: str) -> str | None:
    if status in ("pending", "in_review", "withdrawn"):
        return None
    if status == "denied":
        return "denied"
    if status == "appealed":
        return "denied"
    if status == "pended":
        return weighted_choice(PENDED_DECISION_WEIGHTS)
    if status == "approved":
        # 部分批准率也按层级倾斜:Bronze 部分批准更多。
        partial_rate = {"Bronze": 0.15, "Silver": 0.10, "Gold": 0.08, "Platinum": 0.05}[tier]
        return "partial_approved" if random.random() < partial_rate else "approved"
    raise ValueError(f"Unhandled status: {status}")


def gen_pa_requests(member_df: pl.DataFrame,
                    provider_df: pl.DataFrame,
                    plan_df: pl.DataFrame) -> pl.DataFrame:
    """两阶段生成:

    阶段 1 — 活跃池 (~70 条请求):
        预留的 pending / in_review 请求队列,规模由 ACTIVE_QUOTA 决定。
        提交时间落在紧急度窗口内 (所以多数在 SLA 之内),另有
        ACTIVE_STALLED_RATE 比例落到窗口之外 (为 Q29 播种)。会员从截至
        TODAY 仍处于有效保障的人里抽取。

    阶段 2 — 历史池 (其余):
        原有的层级感知、幂律逻辑,但抑制 `pending` / `in_review`
        (这两种已由阶段 1 提供)。

    幂律的会员 / provider 抽样对两个阶段都适用。
    """
    member_cov = {}
    member_plan = {}
    for row in member_df.iter_rows(named=True):
        member_cov[row["member_id"]] = (row["plan_start_date"], row["plan_end_date"])
        member_plan[row["member_id"]] = row["plan_id"]
    plan_tier = {p["plan_id"]: p["metal_tier"] for p in plan_df.iter_rows(named=True)}

    member_ids = list(member_cov.keys())
    random.shuffle(member_ids)
    member_weights = bucketed_pareto_weights(len(member_ids),
                                              top_weight=4.0, mid_weight=2.0)

    provider_npis = provider_df["npi"].to_list()
    random.shuffle(provider_npis)
    provider_weights = bucketed_pareto_weights(len(provider_npis),
                                                top_weight=3.0, mid_weight=1.5)

    # 截至 TODAY 仍有有效保障的会员 (有资格进入活跃池)。
    active_member_ids = [m for m in member_ids if member_cov[m][1] > TODAY]
    active_member_weights = bucketed_pareto_weights(len(active_member_ids),
                                                     top_weight=4.0, mid_weight=2.0)

    def _build_request(member_id: str, urgency: str, submitted: datetime,
                       status: str) -> dict:
        return {
            "request_id": str(uuid.uuid4()),
            "member_id": member_id,
            "provider_npi": random.choices(provider_npis, weights=provider_weights, k=1)[0],
            "submitted_at": submitted,
            "urgency": urgency,
            "status": status,
            "raw_request_text": fake.paragraph(nb_sentences=3),
            "source_channel": weighted_choice(SOURCE_CHANNEL_WEIGHTS),
            "updated_at": submitted + timedelta(hours=random.randint(1, 72)),
        }

    rows: list[dict] = []

    # ---- 阶段 1:活跃池 ----
    for urgency, quota in ACTIVE_QUOTA.items():
        window = PENDING_WINDOW_HOURS[urgency]
        for _ in range(quota):
            member_id = random.choices(active_member_ids,
                                       weights=active_member_weights, k=1)[0]
            # 90% 落在窗口内 (on-track / at-risk);10% 超出窗口
            # (超 SLA 滞留)。
            if random.random() < ACTIVE_STALLED_RATE:
                age_hours = random.uniform(window * 1.05, window * 2.5)
            else:
                age_hours = random.uniform(0.5, window * 0.95)
            submitted = TODAY_DT - timedelta(hours=age_hours)
            # 不要早于会员的 plan_start_date。
            plan_start = member_cov[member_id][0]
            min_dt = datetime.combine(plan_start, time(0, 0))
            if submitted < min_dt:
                submitted = min_dt + timedelta(hours=random.uniform(0, 24))
            status = weighted_choice(ACTIVE_STATUS_WEIGHTS)
            rows.append(_build_request(member_id, urgency, submitted, status))

    # ---- 阶段 2:历史池 ----
    attempts = 0
    while len(rows) < N_REQUEST and attempts < N_REQUEST * 5:
        attempts += 1
        member_id = random.choices(member_ids, weights=member_weights, k=1)[0]
        plan_start, plan_end = member_cov[member_id]
        window_start = datetime.combine(max(plan_start, HISTORY_START), time(0, 0))
        window_end = datetime.combine(min(plan_end, TODAY) - timedelta(days=1), time(23, 59))
        if window_end <= window_start:
            continue
        submitted = rand_dt_between(window_start, window_end)
        urgency = weighted_choice(URGENCY_WEIGHTS)
        tier = plan_tier.get(member_plan[member_id], "Silver")
        age_hours = (TODAY_DT - submitted).total_seconds() / 3600.0
        status = _draw_historical_status(tier, urgency, age_hours)
        rows.append(_build_request(member_id, urgency, submitted, status))

    return pl.DataFrame(rows)


# ============================================================================
# 临床条目 / 笔记 / 事实
# ============================================================================
def gen_request_clinical_items(request_df: pl.DataFrame,
                               provider_df: pl.DataFrame,
                               service_df: pl.DataFrame) -> pl.DataFrame:
    """每条请求 1 到 3 个 ICD-10 码、1 到 2 个 CPT/HCPCS 码。75% 的码从
    与 provider 专科匹配的类别里抽,另有 25% 的跨专科长尾 (现实中存在
    交叉转诊)。"""
    icd_by_cat: dict[str, list[dict]] = {}
    proc_by_cat: dict[str, list[dict]] = {}
    all_icd: list[dict] = []
    all_proc: list[dict] = []
    for r in service_df.iter_rows(named=True):
        if r["code_type"] == "ICD10":
            icd_by_cat.setdefault(r["category"], []).append(r)
            all_icd.append(r)
        elif r["code_type"] in ("CPT", "HCPCS"):
            proc_by_cat.setdefault(r["category"], []).append(r)
            all_proc.append(r)

    spec_by_npi = {p["npi"]: p["specialty"] for p in provider_df.iter_rows(named=True)}

    rows = []
    for req in request_df.iter_rows(named=True):
        specialty = spec_by_npi.get(req["provider_npi"], "General Surgery")
        cats = SPECIALTY_TO_CATEGORIES.get(specialty, ["general_surgery"])

        def pick(pool_by_cat: dict, all_pool: list, k: int) -> list[dict]:
            picks: list[dict] = []
            for _ in range(k):
                # 75% 本专科,25% 跨专科
                if random.random() < 0.75:
                    cat = random.choice(cats)
                    pool = pool_by_cat.get(cat) or all_pool
                else:
                    pool = all_pool
                choice = random.choice(pool)
                if choice not in picks:
                    picks.append(choice)
            return picks

        selected_icd = pick(icd_by_cat, all_icd, random.randint(1, 3))
        selected_proc = pick(proc_by_cat, all_proc, random.randint(1, 2))

        seq = 1
        for code in selected_icd:
            rows.append({
                "item_id": str(uuid.uuid4()),
                "request_id": req["request_id"],
                "service_code": code["service_code"],
                "code_type": code["code_type"],
                "is_primary": seq == 1,
                "sequence_num": seq,
            })
            seq += 1
        proc_primary_seq = seq
        for code in selected_proc:
            rows.append({
                "item_id": str(uuid.uuid4()),
                "request_id": req["request_id"],
                "service_code": code["service_code"],
                "code_type": code["code_type"],
                "is_primary": seq == proc_primary_seq,
                "sequence_num": seq,
            })
            seq += 1
    return pl.DataFrame(rows)


_NOTE_TEMPLATES = {
    "physician_letter": (
        "Patient is a {age}-year-old {gender} presenting with {condition}. "
        "Conservative management including {treatment} for {duration} has failed to "
        "provide adequate relief. {imaging} findings dated {idate} demonstrate "
        "{severity}. Functional status: {functional}. BMI {bmi:.1f}. "
        "{contraindications}. Recommend {procedure}."
    ),
    "lab_results": (
        "CBC and BMP within normal limits. {test_name}: {value}. "
        "Pre-operative clearance obtained from PCP on {idate}."
    ),
    "imaging_report": (
        "{imaging} performed {idate} demonstrates {grade} {condition} "
        "with {detail}. {additional}"
    ),
    "treatment_history": (
        "Patient has undergone {treatment} for {duration} with {outcome}. "
        "Current medications: {medications}."
    ),
    "referral": (
        "Referral from {referrer} dated {idate} for evaluation of {condition}. "
        "Patient seen on {idate2} with diagnosis confirmed."
    ),
}


def gen_clinical_notes(request_df: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for req in request_df.iter_rows(named=True):
        n_notes = random.randint(1, 3)
        submitted = req["submitted_at"]
        earliest = submitted.date() - timedelta(days=180)
        for _ in range(n_notes):
            note_type = random.choice(list(_NOTE_TEMPLATES.keys()))
            tpl = _NOTE_TEMPLATES[note_type]
            note_date = fake.date_between_dates(date_start=earliest, date_end=submitted.date())
            content = tpl.format(
                age=random.randint(25, 80),
                gender=random.choice(["male", "female"]),
                condition=random.choice([
                    "severe right knee pain", "chronic low back pain",
                    "exertional chest pain", "persistent migraine",
                    "uncontrolled depression",
                ]),
                treatment=random.choice([
                    "physical therapy", "NSAIDs", "corticosteroid injections",
                    "SSRI medication", "lifestyle modification",
                ]),
                duration=random.choice(["3 months", "6 weeks", "8 weeks", "12 weeks", "6 months"]),
                imaging=random.choice(["X-ray", "MRI", "CT scan", "PET/CT"]),
                idate=note_date.isoformat(),
                idate2=(note_date + timedelta(days=random.randint(1, 14))).isoformat(),
                severity=random.choice([
                    "Grade IV osteoarthritis", "moderate spinal stenosis",
                    "single-vessel disease", "no acute findings",
                ]),
                functional=random.choice([
                    "significantly impaired", "moderately limited",
                    "severely restricted",
                ]),
                bmi=random.uniform(22.0, 38.0),
                contraindications=random.choice([
                    "No contraindications identified",
                    "Patient cleared for surgery",
                    "Anticoagulation paused per protocol",
                ]),
                procedure=random.choice([
                    "total knee arthroplasty", "cardiac catheterization",
                    "surgical intervention", "specialty pharmacy initiation",
                ]),
                test_name=random.choice(["PT/INR", "HbA1c", "Lipid panel", "TSH"]),
                value=random.choice(["1.1", "6.5%", "Normal", "0.8"]),
                grade=random.choice(["Grade III", "Grade IV", "moderate to severe"]),
                detail=random.choice([
                    "joint space narrowing", "bone spurs present",
                    "cartilage loss", "no acute fracture",
                ]),
                additional=fake.sentence(),
                outcome=random.choice([
                    "minimal improvement", "no significant relief",
                    "inadequate response",
                ]),
                medications=fake.sentence(),
                referrer=f"Dr. {fake.last_name()}",
            )
            rows.append({
                "note_id": str(uuid.uuid4()),
                "request_id": req["request_id"],
                "note_type": note_type,
                "note_content": content,
                "note_date": note_date,
                "authored_by": f"Dr. {fake.last_name()}",
                "created_at": datetime.combine(note_date, time(random.randint(8, 18), 0)),
            })
    return pl.DataFrame(rows)


def gen_extracted_clinical_facts(request_df: pl.DataFrame) -> pl.DataFrame:
    """只有有决定的请求才会被抽取事实。抽取作为接收分诊的一部分,在提交后
    几小时内完成。"""
    fact_templates = [
        ("prior_treatment",        "conservative_treatment_duration", "{months} months {treatment}"),
        ("diagnosis_confirmed",    "imaging_evidence_grade",          "Grade {grade} per {imaging}"),
        ("functional_status",      "ambulation_status",               "{status}"),
        ("lab_result",             "bmi",                             "{value}"),
        ("contraindication",       "contraindications_present",       "{present}"),
        ("duration_of_condition",  "symptom_duration_months",         "{months}"),
        ("medication_history",     "tried_first_line_therapy",        "{yesno}"),
    ]
    rows = []
    for req in request_df.iter_rows(named=True):
        if req["status"] in ("pending", "in_review", "withdrawn"):
            continue
        n_facts = random.randint(2, 4)
        submitted = req["submitted_at"]
        for _ in range(n_facts):
            category, key, tpl = random.choice(fact_templates)
            val = tpl.format(
                treatment=random.choice(["of physical therapy", "of NSAIDs", "of injections"]),
                months=random.randint(3, 24),
                grade=random.choice(["III", "IV"]),
                imaging=random.choice(["X-ray", "MRI"]),
                status=random.choice(["requires cane", "wheelchair bound", "limited mobility"]),
                value=round(random.uniform(22.0, 38.0), 1),
                present=random.choice(["false", "true"]),
                yesno=random.choice(["Yes", "No"]),
            )
            rows.append({
                "fact_id": str(uuid.uuid4()),
                "request_id": req["request_id"],
                "fact_category": category,
                "fact_key": key,
                "fact_value": val,
                "evidence_source": fake.sentence()[:120],
                "confidence": round(random.uniform(0.70, 0.99), 2),
                "extracted_at": clamp_to_today(
                    submitted + timedelta(minutes=random.randint(5, 240))
                ),
            })
    return pl.DataFrame(rows)


# ============================================================================
# 决定 / 申诉 / 理赔
# ============================================================================
def _gen_criteria_met(decision: str) -> str:
    n_keys = random.randint(3, 6)
    keys = random.sample(CRITERIA_KEYS, n_keys)
    if decision == "approved":
        return to_json({k: True for k in keys})
    if decision == "partial_approved":
        idx = random.randint(0, n_keys - 1)
        return to_json({k: (i != idx) for i, k in enumerate(keys)})
    n_false = random.randint(1, min(3, n_keys))
    false_idxs = set(random.sample(range(n_keys), n_false))
    return to_json({k: (i not in false_idxs) for i, k in enumerate(keys)})


def _sla_decided_at(submitted: datetime, urgency: str) -> datetime:
    """抽样 decided_at,90% 命中 SLA,另有 10% 的违约长尾。始终钳制到
    TODAY,使没有决定落在未来。"""
    sla = SLA_HOURS[urgency]
    if random.random() < 0.9:
        hours = random.uniform(0.1, sla * 0.95)
    else:
        hours = random.uniform(sla * 1.05, sla * 2.5)
    return clamp_to_today(submitted + timedelta(hours=hours))


def _pick_applied_policy(req_proc_codes: list[str],
                         policy_df: pl.DataFrame,
                         decided_at: datetime,
                         member_tier: str) -> str | None:
    decided_date = decided_at.date()
    candidates = []
    for pol in policy_df.iter_rows(named=True):
        if pol["effective_date"] > decided_date:
            continue
        if pol["expiry_date"] is not None and pol["expiry_date"] < decided_date:
            continue
        if pol["applies_to_metal_tier"] and pol["applies_to_metal_tier"] != member_tier:
            continue
        pol_codes = set(json.loads(pol["cpt_codes_json"]))
        if pol_codes & set(req_proc_codes):
            candidates.append(pol["policy_id"])
    if not candidates:
        return None
    return random.choice(candidates)


def gen_pa_decisions(request_df: pl.DataFrame,
                     reviewer_df: pl.DataFrame,
                     policy_df: pl.DataFrame,
                     items_df: pl.DataFrame,
                     member_df: pl.DataFrame,
                     plan_df: pl.DataFrame) -> pl.DataFrame:
    req_proc: dict[str, list[str]] = {}
    for it in items_df.iter_rows(named=True):
        if it["code_type"] in ("CPT", "HCPCS"):
            req_proc.setdefault(it["request_id"], []).append(it["service_code"])

    plan_tier = {p["plan_id"]: p["metal_tier"] for p in plan_df.iter_rows(named=True)}
    mem_tier = {m["member_id"]: plan_tier.get(m["plan_id"], "Silver")
                for m in member_df.iter_rows(named=True)}

    active_reviewers = reviewer_df.filter(pl.col("active") == True)
    rev_by_role: dict[str, list[str]] = {}
    for r in active_reviewers.iter_rows(named=True):
        rev_by_role.setdefault(r["role"], []).append(r["reviewer_id"])

    rows = []
    for req in request_df.iter_rows(named=True):
        tier = mem_tier.get(req["member_id"], "Silver")
        decision = _draw_decision_for_status(req["status"], tier)
        if decision is None:
            continue
        decided_at = _sla_decided_at(req["submitted_at"], req["urgency"])
        tat_hours = round((decided_at - req["submitted_at"]).total_seconds() / 3600.0, 2)
        sla_breached = tat_hours > SLA_HOURS[req["urgency"]]

        if decision == "approved" and random.random() < 0.55:
            role = "auto_rule"
        elif decision == "escalated":
            role = "medical_director" if random.random() < 0.7 else "external_reviewer"
        elif decision == "denied" and random.random() < 0.2:
            role = "medical_director"
        else:
            role = "clinical_reviewer"
        reviewer_id = random.choice(rev_by_role.get(role, rev_by_role["clinical_reviewer"]))

        if decision == "denied":
            n_codes = random.randint(1, 2)
            denial_codes = random.choices(DENIAL_CODE_KEYS, weights=DENIAL_CODE_WEIGHTS, k=n_codes)
            # 去重,同时保持顺序
            denial_codes = list(dict.fromkeys(denial_codes))
            denial_codes_json = to_json(denial_codes)
            reason_code = denial_codes[0]
            reason_text = DENIAL_CODE_REASON[reason_code]
        elif decision == "partial_approved":
            code = random.choices(DENIAL_CODE_KEYS, weights=DENIAL_CODE_WEIGHTS, k=1)[0]
            denial_codes_json = to_json([code])
            reason_code = "PARTIAL"
            reason_text = "Partial approval - some service lines denied."
        else:
            denial_codes_json = None
            reason_code = None
            if decision == "approved":
                reason_text = "All medical necessity criteria met per policy."
            elif decision == "pended":
                reason_text = "Additional clinical documentation required."
            elif decision == "escalated":
                reason_text = "Case escalated to medical director for review."
            else:
                reason_text = ""

        if role == "auto_rule":
            conf = random.uniform(0.85, 0.99)
        elif decision in ("pended", "escalated"):
            conf = random.uniform(0.55, 0.80)
        else:
            conf = random.uniform(0.75, 0.95)

        applied_policy = _pick_applied_policy(
            req_proc.get(req["request_id"], []),
            policy_df, decided_at, tier,
        )

        rows.append({
            "decision_id": str(uuid.uuid4()),
            "request_id": req["request_id"],
            "decision": decision,
            "decision_reason_code": reason_code,
            "decision_reason_text": reason_text,
            "criteria_met_json": _gen_criteria_met(decision),
            "denial_codes_json": denial_codes_json,
            "confidence_score": round(conf, 3),
            "reviewer_id": reviewer_id,
            "applied_policy_id": applied_policy,
            "decided_at": decided_at,
            "tat_hours": tat_hours,
            "sla_breached": sla_breached,
        })
    return pl.DataFrame(rows)


def gen_appeals(decision_df: pl.DataFrame, request_df: pl.DataFrame) -> pl.DataFrame:
    """level_number 取 1 / 2 / 3 (3 = 外部)。is_external_review 是便捷
    布尔列。appeal_level 文本保留供人阅读。"""
    status_by_req = {r["request_id"]: r["status"] for r in request_df.iter_rows(named=True)}
    denied_decisions = [d for d in decision_df.iter_rows(named=True) if d["decision"] == "denied"]

    rows = []
    for dec in denied_decisions:
        req_status = status_by_req.get(dec["request_id"])
        force_appeal = (req_status == "appealed")
        # 首次申诉率从 30% 提到 50%,这样在链路的推翻 / 待定短路之后,
        # 漏斗仍能以可观的体量抵达外部审查。
        if not force_appeal and random.random() > 0.50:
            continue

        levels_to_do = [(1, "1", False)]
        # L1 -> L2 升级 50%,L2 -> 外部 50% (原为 30 / 25)。约 75 件 L1
        # 申诉下,这会产出约 37 件 L2 和约 18 件外部案件,足够让 Q11 里的
        # 外部审查行干净地展示它更低的推翻率。
        if random.random() < 0.50:
            levels_to_do.append((2, "2", False))
            if random.random() < 0.50:
                levels_to_do.append((3, "external", True))

        prev_resolved = dec["decided_at"]
        for level_num, level_label, is_external in levels_to_do:
            submitted = prev_resolved + timedelta(days=random.randint(3, 30))
            if submitted > TODAY_DT:
                break
            sla_days = {1: 30, 2: 30, 3: 60}[level_num]
            resolved = submitted + timedelta(days=random.randint(5, sla_days))
            if resolved > TODAY_DT:
                resolved_out = None
                outcome = "pending"
                overturned = False
            else:
                # 第 3 级 (外部 IRO) 推翻率从 0.18 略升到 0.25 —— CMS
                # 数据里真实的 IRO 推翻率在 20-30% 区间,取较高值能确保
                # 这个很小的外部样本在 Q11 里稳定地显示非零推翻。
                p_overturn = {1: 0.35, 2: 0.25, 3: 0.25}[level_num]
                overturned = random.random() < p_overturn
                outcome = "overturned" if overturned else "upheld"
                resolved_out = resolved

            rows.append({
                "appeal_id": str(uuid.uuid4()),
                "decision_id": dec["decision_id"],
                "appeal_level": level_label,
                "level_number": level_num,
                "is_external_review": is_external,
                "submitted_at": submitted,
                "resolved_at": resolved_out,
                "outcome": outcome,
                "overturned": overturned,
                "requested_by": random.choices(
                    ["member", "provider"], weights=[0.3, 0.7], k=1)[0],
            })
            if resolved_out is None or overturned:
                break
            prev_resolved = resolved_out
    return pl.DataFrame(rows)


def gen_appeal_letters(appeal_df: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for ap in appeal_df.iter_rows(named=True):
        content = (
            f"Dear Appeals Review Board,\n\n"
            f"I am writing to appeal the denial of prior authorization "
            f"(level {ap['level_number']} review). The denial cited "
            f"{random.choice(['insufficient conservative treatment duration', 'lack of medical necessity', 'criteria not met', 'step therapy incomplete'])}. "
            f"{fake.paragraph(nb_sentences=4)}\n\n"
            f"I respectfully request reconsideration.\n\n"
            f"Sincerely,\nDr. {fake.last_name()}"
        )
        rs = random.choices(["sent", "accepted", "rejected"], weights=[0.30, 0.30, 0.40], k=1)[0]
        if ap["outcome"] == "pending":
            rs = random.choices(["draft", "sent"], weights=[0.4, 0.6], k=1)[0]
        rows.append({
            "letter_id": str(uuid.uuid4()),
            "appeal_id": ap["appeal_id"],
            "letter_content": content,
            "generated_at": clamp_to_today(
                ap["submitted_at"] + timedelta(hours=random.randint(1, 48))
            ),
            "review_status": rs,
            "reviewed_by": f"Dr. {fake.last_name()}" if random.random() < 0.6 else None,
        })
    return pl.DataFrame(rows)


# provider 类型的计费乘子,让 Q26 (付款最高的 provider) 偏向医院和手术
# 中心,这更贴近现实。
PROVIDER_TYPE_BILL_MULT = {
    "Hospital":        1.5,
    "Surgical Center": 1.8,
    "Clinic":          0.7,
    "Physician":       1.0,
    "Specialist":      1.1,
}


def gen_claims(decision_df: pl.DataFrame,
               request_df: pl.DataFrame,
               provider_df: pl.DataFrame,
               items_df: pl.DataFrame,
               service_df: pl.DataFrame,
               member_df: pl.DataFrame,
               plan_df: pl.DataFrame) -> pl.DataFrame:
    """层级感知的成本分担:member_responsibility_usd 按金属层级的
    TIER_MEMBER_PCT 区间计算,而非一刀切的均匀抽样。provider 类型也会
    影响计费金额。"""
    bill_map = {
        (s["service_code"], s["code_type"]): s["avg_billed_amount_usd"]
        for s in service_df.iter_rows(named=True)
    }
    req_proc: dict[str, list[tuple[str, str]]] = {}
    for it in items_df.iter_rows(named=True):
        if it["code_type"] in ("CPT", "HCPCS"):
            req_proc.setdefault(it["request_id"], []).append((it["service_code"], it["code_type"]))

    member_by_req = {r["request_id"]: r["member_id"] for r in request_df.iter_rows(named=True)}
    provider_by_req = {r["request_id"]: r["provider_npi"] for r in request_df.iter_rows(named=True)}
    ptype_by_npi = {p["npi"]: p["provider_type"] for p in provider_df.iter_rows(named=True)}

    plan_tier = {p["plan_id"]: p["metal_tier"] for p in plan_df.iter_rows(named=True)}
    mem_tier  = {m["member_id"]: plan_tier.get(m["plan_id"], "Silver")
                 for m in member_df.iter_rows(named=True)}

    rows = []
    for dec in decision_df.iter_rows(named=True):
        if dec["decision"] not in ("approved", "partial_approved"):
            continue
        if random.random() > 0.60:
            continue
        codes = req_proc.get(dec["request_id"], [])
        if not codes:
            continue
        billed_base = sum(bill_map.get(k, 1500) for k in codes)
        if billed_base <= 0:
            billed_base = random.randint(500, 5000)
        ptype = ptype_by_npi.get(provider_by_req.get(dec["request_id"]), "Physician")
        billed = billed_base * random.uniform(0.85, 1.15) * PROVIDER_TYPE_BILL_MULT.get(ptype, 1.0)

        allow_pct = random.uniform(0.55, 0.80) if dec["decision"] == "partial_approved" \
                    else random.uniform(0.70, 0.92)
        allowed = billed * allow_pct

        tier = mem_tier.get(member_by_req.get(dec["request_id"]), "Silver")
        lo, hi = TIER_MEMBER_PCT[tier]
        member_pct = random.uniform(lo, hi)
        member_resp = allowed * member_pct
        paid = allowed - member_resp

        max_service_day = (TODAY - timedelta(days=1))
        decided_day = dec["decided_at"].date()
        if decided_day >= max_service_day:
            service_date = decided_day
        else:
            service_date = fake.date_between_dates(date_start=decided_day, date_end=max_service_day)
        submitted_dt = clamp_to_today(
            datetime.combine(service_date + timedelta(days=random.randint(0, 14)), time(10, 0))
        )

        claim_status = random.choices(
            ["paid", "pending", "denied"], weights=[0.85, 0.10, 0.05], k=1)[0]
        rows.append({
            "claim_id": str(uuid.uuid4()),
            "decision_id": dec["decision_id"],
            "member_id": member_by_req.get(dec["request_id"]),
            "service_date": service_date,
            "submitted_at": submitted_dt,
            "billed_amount_usd": round(billed, 2),
            "allowed_amount_usd": round(allowed, 2),
            "paid_amount_usd": round(paid, 2),
            "member_responsibility_usd": round(member_resp, 2),
            "claim_status": claim_status,
        })
    return pl.DataFrame(rows)


# ============================================================================
# 流水线
# ============================================================================
def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating data in topological order...")

    plans = gen_plans();                                                 plans.write_csv(DATA_DIR / "01_plans.tsv", separator="\t")
    providers = gen_providers();                                         providers.write_csv(DATA_DIR / "02_providers.tsv", separator="\t")
    reviewers = gen_reviewers();                                         reviewers.write_csv(DATA_DIR / "03_reviewers.tsv", separator="\t")
    service_catalog = gen_service_catalog();                             service_catalog.write_csv(DATA_DIR / "04_service_catalog.tsv", separator="\t")
    sla_config = gen_sla_config();                                       sla_config.write_csv(DATA_DIR / "05_sla_config.tsv", separator="\t")
    policies = gen_payer_policies(service_catalog);                      policies.write_csv(DATA_DIR / "06_payer_policies.tsv", separator="\t")

    members = gen_members(plans["plan_id"].to_list());                   members.write_csv(DATA_DIR / "07_members.tsv", separator="\t")
    requests = gen_pa_requests(members, providers, plans);               requests.write_csv(DATA_DIR / "08_pa_requests.tsv", separator="\t")

    items = gen_request_clinical_items(requests, providers, service_catalog); items.write_csv(DATA_DIR / "09_request_clinical_items.tsv", separator="\t")
    notes = gen_clinical_notes(requests);                                notes.write_csv(DATA_DIR / "10_clinical_notes.tsv", separator="\t")
    facts = gen_extracted_clinical_facts(requests);                      facts.write_csv(DATA_DIR / "11_extracted_clinical_facts.tsv", separator="\t")
    decisions = gen_pa_decisions(requests, reviewers, policies, items,
                                  members, plans);                       decisions.write_csv(DATA_DIR / "12_pa_decisions.tsv", separator="\t")

    appeals = gen_appeals(decisions, requests);                          appeals.write_csv(DATA_DIR / "13_appeals.tsv", separator="\t")
    appeal_letters = gen_appeal_letters(appeals);                        appeal_letters.write_csv(DATA_DIR / "14_appeal_letters.tsv", separator="\t")
    claims = gen_claims(decisions, requests, providers, items,
                        service_catalog, members, plans);                claims.write_csv(DATA_DIR / "15_claims.tsv", separator="\t")

    print(f"  plans={plans.height}  providers={providers.height}  reviewers={reviewers.height}")
    print(f"  service_catalog={service_catalog.height}  sla_config={sla_config.height}  payer_policies={policies.height}")
    print(f"  members={members.height}  pa_requests={requests.height}")
    print(f"  request_clinical_items={items.height}  clinical_notes={notes.height}")
    print(f"  extracted_clinical_facts={facts.height}  pa_decisions={decisions.height}")
    print(f"  appeals={appeals.height}  appeal_letters={appeal_letters.height}  claims={claims.height}")
    total = sum([plans.height, providers.height, reviewers.height, service_catalog.height,
                 sla_config.height, policies.height, members.height, requests.height,
                 items.height, notes.height, facts.height, decisions.height,
                 appeals.height, appeal_letters.height, claims.height])
    print(f"  TOTAL = {total} rows")
    print(f"OK Generated all TSV files in {DATA_DIR}")


LOADER_SPEC = [
    ("01_plans.tsv",                     Plan,                   [], []),
    ("02_providers.tsv",                 Provider,               [], ["in_network"]),
    ("03_reviewers.tsv",                 Reviewer,               ["hired_date"], ["active"]),
    ("04_service_catalog.tsv",           ServiceCatalog,         [], []),
    ("05_sla_config.tsv",                SlaConfig,              [], []),
    ("06_payer_policies.tsv",            PayerPolicy,            ["effective_date", "expiry_date"], []),
    ("07_members.tsv",                   Member,                 ["date_of_birth", "plan_start_date", "plan_end_date", "created_at"], []),
    ("08_pa_requests.tsv",               PARequest,              ["submitted_at", "updated_at"], []),
    ("09_request_clinical_items.tsv",    RequestClinicalItem,    [], ["is_primary"]),
    ("10_clinical_notes.tsv",            ClinicalNote,           ["note_date", "created_at"], []),
    ("11_extracted_clinical_facts.tsv",  ExtractedClinicalFact,  ["extracted_at"], []),
    ("12_pa_decisions.tsv",              PADecision,             ["decided_at"], ["sla_breached"]),
    ("13_appeals.tsv",                   Appeal,                 ["submitted_at", "resolved_at"], ["overturned", "is_external_review"]),
    ("14_appeal_letters.tsv",            AppealLetter,           ["generated_at"], []),
    ("15_claims.tsv",                    Claim,                  ["service_date", "submitted_at"], []),
]


def _coerce_temporal(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    for col in cols:
        if col not in df.columns:
            continue
        dtype = df.schema[col]
        if dtype == pl.Utf8:
            df = df.with_columns(pl.col(col).str.to_datetime(strict=False).alias(col))
        elif dtype == pl.Date:
            df = df.with_columns(pl.col(col).cast(pl.Datetime).alias(col))
    return df


def _coerce_bool(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    for col in cols:
        if col not in df.columns:
            continue
        dtype = df.schema[col]
        if dtype == pl.Utf8:
            df = df.with_columns(
                pl.col(col).str.to_lowercase().is_in(["true", "1", "t", "yes"]).alias(col)
            )
    return df


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    print("Loading data into SQLite...")
    with Session(engine) as session:
        for filename, model, dt_cols, bool_cols in LOADER_SPEC:
            df = pl.read_csv(DATA_DIR / filename, separator="\t",
                             try_parse_dates=False, infer_schema_length=10_000)
            df = _coerce_temporal(df, dt_cols)
            df = _coerce_bool(df, bool_cols)
            for row in df.iter_rows(named=True):
                clean = {k: (None if (v is None or (isinstance(v, float) and v != v)) else v)
                         for k, v in row.items()}
                session.add(model(**clean))
        session.commit()

    print(f"OK Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("=" * 70)
    print("Meridian Health Plan - Prior Authorization Data Generator")
    print("=" * 70)
    generate_all_tsv()
    create_sqlite_database()
    print("\n" + "=" * 70)
    print("OK All done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
