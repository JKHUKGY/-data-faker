"""
Healthcare - 妇产科病房调度 (Obstetrics Ward Scheduling) 假数据生成器
复杂度: 中等 (Medium)
生成方: Fake Data Generator Agent

业务背景:
MaterniFlow 是一个面向美国医院妇产科病房的 AI 辅助调度系统 (POC)。本数据集支持
5 个 demo 场景: 交班简报 (shift handover)、床位余量 (bed availability)、产程进展
跟踪 (labor progress)、高危产妇预警 (high-risk alert)、医嘱排程 (order scheduling)。
所有数据都刻意贴近北美医院真实的临床规律。

刻意埋入的"剧情点" (供 SQL 查询暴露, 详见 02 ER 文档的业务陷阱声明):
1. 高危血压趋势: 2 例 admission 的收缩压沿 125 -> 131 -> 137 -> 143 上升越过 140
   警戒线 (各触发 1 条未确认 high_bp 告警) —— 对应 Q6 / Q7 / Q16。
2. 双胎早产: 1 例 34.2 周双胎高危, 触发 1 条已确认 preterm_risk 告警 —— 对应 Q18。
3. 明日剖宫产: 1 台明天 09:00 的 scheduled c_section (delivery 房) —— 对应 Q4 / Q14。
4. 床位四态: 故意保留 2 张 cleaning + 1 张 maintenance (含 1 张 labor 房 cleaning),
   不能简单按"占/空"二分 —— 对应 Q2 / Q10。
5. LOS 口径: predicted_los_hours 是产后时长 (顺产 24-48h, 剖宫产 72-96h) —— 对应 Q9 / Q17。

业务背景、术语表、指标公式见 01-..._business_context-cn.md;
表结构与字段定义见 02-..._er_document-cn.md;
暴露这些埋点的 SQL 查询见 03-..._sql_queries-cn.md。
"""

from __future__ import annotations
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional
import random
import json

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, Text, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "healthcare_obstetrics_ward_scheduling_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Demo 的参考日 (模拟世界里的"当前时间"); 固定值保证多次运行结果一致
REFERENCE_DATE = datetime(2026, 2, 13, 8, 0, 0)  # Demo 从早上 8 点开始


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


class Patient(Base):
    """patient 实体 —— 产妇的基本身份信息 (只放人口学/联系方式, 不放临床信息)。"""
    __tablename__ = "patient"

    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(200))
    insurance_type: Mapped[Optional[str]] = mapped_column(String(20))  # Medicaid/commercial/self_pay


class OBProfile(Base):
    """ob_profile 实体 —— 产妇的孕产临床档案 (风险判断/分娩方式/LOS 预测的源头), 与 patient 严格 1:1。"""
    __tablename__ = "ob_profile"

    ob_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patient.patient_id"), unique=True, nullable=False)
    gravida: Mapped[int] = mapped_column(Integer, nullable=False)  # 妊娠总次数 (G), 含本次
    para: Mapped[int] = mapped_column(Integer, nullable=False)  # 既往分娩次数 (P)
    gestational_weeks: Mapped[float] = mapped_column(Float, nullable=False)
    edd: Mapped[date] = mapped_column(Date, nullable=False)  # 预产期 (Estimated Due Date)
    fetus_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prior_delivery_method: Mapped[Optional[str]] = mapped_column(String(20))  # none/vaginal/c_section
    planned_delivery_method: Mapped[str] = mapped_column(String(20), nullable=False)  # vaginal/c_section/vbac
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)  # low/medium/high
    complications: Mapped[Optional[str]] = mapped_column(Text)  # JSON 数组
    gbs_status: Mapped[Optional[str]] = mapped_column(String(10))  # positive/negative/unknown
    notes: Mapped[Optional[str]] = mapped_column(Text)


class Room(Base):
    """room 实体 —— 病房的物理房间 (5 种功能区: labor/delivery/postpartum/nicu/triage)。"""
    __tablename__ = "room"

    room_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    room_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    room_type: Mapped[str] = mapped_column(String(20), nullable=False)  # labor/delivery/postpartum/nicu/triage
    floor: Mapped[int] = mapped_column(Integer, nullable=False)


class Bed(Base):
    """bed 实体 —— 床位 (比 room 粒度更细); status 四态是房间余量查询的核心。"""
    __tablename__ = "bed"

    bed_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("room.room_id"), nullable=False)
    bed_label: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")  # available/occupied/cleaning/maintenance
    current_admission_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("admission.admission_id"))


class Provider(Base):
    """provider 实体 —— 病房的医护人员 (主治/住院医/护士/助产士/麻醉师)。"""
    __tablename__ = "provider"

    provider_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # attending/resident/nurse/midwife/anesthesiologist
    department: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Shift(Base):
    """shift 实体 —— 医护排班 (24/7 分 day/night 两班)。"""
    __tablename__ = "shift"

    shift_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("provider.provider_id"), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_type: Mapped[str] = mapped_column(String(10), nullable=False)  # day/night
    assigned_room_ids: Mapped[Optional[str]] = mapped_column(Text)  # JSON 数组


class Admission(Base):
    """admission 实体 —— 一次完整住院的生命周期记录, 整个 POC 的核心事实表。"""
    __tablename__ = "admission"

    admission_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patient.patient_id"), nullable=False)
    ob_id: Mapped[str] = mapped_column(String(36), ForeignKey("ob_profile.ob_id"), nullable=False)
    admit_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # admitted/in_labor/delivered/postpartum/ready_for_discharge/discharged
    delivery_method_actual: Mapped[Optional[str]] = mapped_column(String(20))
    delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    predicted_los_hours: Mapped[Optional[int]] = mapped_column(Integer)
    predicted_discharge_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_discharge_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    current_bed_id: Mapped[Optional[str]] = mapped_column(String(36))  # 指向 bed 的逻辑引用 (非约束 FK)
    attending_provider_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("provider.provider_id"))
    primary_nurse_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("provider.provider_id"))


class LaborProgress(Base):
    """labor_progress 实体 —— 产程进展记录 (时序事件表, 内诊每 1-4h 一次)。"""
    __tablename__ = "labor_progress"

    progress_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admission.admission_id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cervical_dilation_cm: Mapped[float] = mapped_column(Float, nullable=False)  # 宫口开大 0-10 cm
    effacement_pct: Mapped[Optional[int]] = mapped_column(Integer)  # 宫颈消失度 0-100%
    station: Mapped[Optional[int]] = mapped_column(Integer)  # 胎头下降 -3 至 +3
    contraction_freq: Mapped[Optional[int]] = mapped_column(Integer)  # 每 10 分钟宫缩次数
    membrane_status: Mapped[str] = mapped_column(String(20), nullable=False)  # intact/ruptured
    notes: Mapped[Optional[str]] = mapped_column(Text)


class VitalSign(Base):
    """vital_sign 实体 —— 生命体征监测 (时序事件表, 高危预警的直接数据源)。"""
    __tablename__ = "vital_sign"

    vital_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admission.admission_id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bp_systolic: Mapped[int] = mapped_column(Integer, nullable=False)
    bp_diastolic: Mapped[int] = mapped_column(Integer, nullable=False)
    heart_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    fetal_heart_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    oxygen_saturation: Mapped[float] = mapped_column(Float, nullable=False)


class Order(Base):
    """medical_order 实体 —— 医嘱与计划操作 (含明日待执行手术, 场景 5 的核心)。"""
    __tablename__ = "medical_order"

    order_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admission.admission_id"), nullable=False)
    order_type: Mapped[str] = mapped_column(String(30), nullable=False)  # c_section/induction/epidural/lab_test/medication/consult
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # scheduled/in_progress/completed/cancelled
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    assigned_provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("provider.provider_id"), nullable=False)
    assigned_room_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("room.room_id"))
    priority: Mapped[str] = mapped_column(String(15), nullable=False, default="routine")  # routine/urgent/emergency
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)


class Alert(Base):
    """alert 实体 —— AI 自动生成的临床告警 (POC 的输出之一)。"""
    __tablename__ = "alert"

    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admission_id: Mapped[str] = mapped_column(String(36), ForeignKey("admission.admission_id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)  # high_bp/abnormal_fhr/fever/preterm_risk
    severity: Mapped[str] = mapped_column(String(15), nullable=False)  # warning/critical
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("provider.provider_id"))


# ============================================================================
# 美式姓名与临床数据
# ============================================================================
AMERICAN_FEMALE_NAMES = [
    "Emily Johnson", "Sarah Williams", "Jessica Brown", "Ashley Davis", "Amanda Miller",
    "Stephanie Wilson", "Jennifer Moore", "Nicole Taylor", "Melissa Anderson", "Christina Thomas",
    "Elizabeth Jackson", "Lauren White", "Rachel Harris", "Samantha Martin", "Rebecca Thompson",
    "Heather Garcia", "Katherine Martinez", "Brittany Robinson", "Megan Clark", "Kimberly Rodriguez",
    "Danielle Lewis", "Michelle Lee", "Tiffany Walker", "Amber Hall", "Lindsay Allen",
    "Courtney Young", "Natalie Hernandez", "Vanessa King", "Chelsea Wright", "Morgan Lopez",
    "Brooke Hill", "Kelsey Scott", "Allison Green", "Erin Adams", "Crystal Baker",
    "Casey Nelson", "Jamie Carter", "Kristen Mitchell", "Holly Perez", "Diana Roberts",
    "Laura Turner", "Amy Phillips", "Angela Campbell", "Julie Parker", "Cynthia Evans",
    "Lisa Edwards", "Kelly Collins", "Sharon Stewart", "Teresa Sanchez", "Maria Morris"
]

PROVIDER_NAMES = {
    "attending": [
        ("Dr. Michael Chen", "attending"),
        ("Dr. Sarah Williams", "attending"),
        ("Dr. James Rodriguez", "attending"),
        ("Dr. Emily Foster", "attending"),
    ],
    "resident": [
        ("Dr. Kevin Park", "resident"),
        ("Dr. Lisa Nguyen", "resident"),
    ],
    "nurse": [
        ("RN Jessica Martinez", "nurse"),
        ("RN Amanda Thompson", "nurse"),
        ("RN David Kim", "nurse"),
        ("RN Rachel Green", "nurse"),
        ("RN Michelle Davis", "nurse"),
    ],
    "midwife": [
        ("CNM Rebecca Johnson", "midwife"),
        ("CNM Karen White", "midwife"),
    ],
    "anesthesiologist": [
        ("Dr. Robert Lee", "anesthesiologist"),
        ("Dr. Jennifer Smith", "anesthesiologist"),
    ],
}

COMPLICATIONS_LIST = [
    "Gestational diabetes",
    "Gestational hypertension",
    "Preeclampsia",
    "Placenta previa",
    "Oligohydramnios",
    "Polyhydramnios",
    "Intrauterine growth restriction",
    "Previous cesarean section",
    "Advanced maternal age",
    "Anemia",
]


# ============================================================================
# 数据生成函数
# ============================================================================
def gen_uuid() -> str:
    """生成一个 UUID 字符串。"""
    return str(uuid.uuid4())


def gen_patients(n: int = 50) -> pl.DataFrame:
    """生成产妇记录 (美式姓名 + 人口学; 年龄与保险按目标权重抽样)。"""
    records = []
    names_used = random.sample(AMERICAN_FEMALE_NAMES, min(n, len(AMERICAN_FEMALE_NAMES)))

    for i in range(n):
        name = names_used[i] if i < len(names_used) else f"Patient {fake.first_name_female()} {fake.last_name()}"
        age = random.choices(
            [random.randint(18, 24), random.randint(25, 34), random.randint(35, 42)],
            weights=[0.2, 0.6, 0.2]
        )[0]

        insurance = random.choices(
            ["commercial", "Medicaid", "self_pay"],
            weights=[0.55, 0.35, 0.10]
        )[0]

        records.append({
            "patient_id": gen_uuid(),
            "name": name,
            "age": age,
            "phone": fake.phone_number(),
            "emergency_contact": f"{fake.name()}, {fake.phone_number()}",
            "insurance_type": insurance,
        })

    return pl.DataFrame(records)


def gen_ob_profiles(patients_df: pl.DataFrame) -> pl.DataFrame:
    """为所有产妇生成孕产临床档案 (风险等级由年龄/多胎/早产/VBAC/并发症派生)。"""
    records = []
    patient_ids = patients_df["patient_id"].to_list()
    patient_ages = dict(zip(patients_df["patient_id"].to_list(), patients_df["age"].to_list()))

    for pid in patient_ids:
        age = patient_ages[pid]

        # 妊娠次数 G/P 与年龄相关 (年龄越大, 中位数越高)
        if age < 25:
            gravida = random.choices([1, 2], weights=[0.7, 0.3])[0]
        elif age < 35:
            gravida = random.choices([1, 2, 3, 4], weights=[0.3, 0.35, 0.25, 0.1])[0]
        else:
            gravida = random.choices([1, 2, 3, 4, 5], weights=[0.15, 0.3, 0.3, 0.15, 0.1])[0]

        para = min(gravida - 1, random.randint(0, gravida - 1))

        # 胎数 (先抽, 这样孕周/分娩计划可以依赖它)
        fetus_count = random.choices([1, 2, 3], weights=[0.96, 0.035, 0.005])[0]

        # 孕周 —— 与胎数相关 (多胎分娩更早)。
        # 单胎: 多在 37-41 周; 双胎: 典型 34-38 周; 三胎: 30-34 周。
        if fetus_count == 1:
            gest_weeks = random.choices(
                [random.uniform(32, 36.9), random.uniform(37, 38.9), random.uniform(39, 40.9), random.uniform(41, 42)],
                weights=[0.1, 0.35, 0.45, 0.1]
            )[0]
        elif fetus_count == 2:
            gest_weeks = random.choices(
                [random.uniform(32, 34.9), random.uniform(35, 36.9), random.uniform(37, 38)],
                weights=[0.25, 0.5, 0.25]
            )[0]
        else:  # 三胎
            gest_weeks = random.uniform(30, 34)
        gest_weeks = round(gest_weeks, 1)

        # 计算预产期 (EDD)
        days_to_edd = int((40 - gest_weeks) * 7)
        edd = (REFERENCE_DATE + timedelta(days=days_to_edd)).date()

        # 上一胎分娩方式
        if para == 0:
            prior_method = "none"
        else:
            prior_method = random.choices(["vaginal", "c_section"], weights=[0.7, 0.3])[0]

        # 本次计划分娩方式 —— 多胎以剖宫产为主。
        if fetus_count >= 3:
            planned_method = "c_section"
        elif fetus_count == 2:
            planned_method = random.choices(["c_section", "vaginal"], weights=[0.8, 0.2])[0]
        elif prior_method == "c_section":
            planned_method = random.choices(["c_section", "vbac"], weights=[0.7, 0.3])[0]
        else:
            planned_method = random.choices(["vaginal", "c_section"], weights=[0.85, 0.15])[0]

        # 计算风险等级 (risk_factors 累加)
        risk_factors = 0
        if age >= 35:
            risk_factors += 1
        if fetus_count > 1:
            risk_factors += 2
        if gest_weeks < 37:
            risk_factors += 1
        if prior_method == "c_section" and planned_method == "vbac":
            risk_factors += 1

        # 随机添加并发症
        complications = []
        if random.random() < 0.25:
            num_complications = random.randint(1, 3)
            complications = random.sample(COMPLICATIONS_LIST, num_complications)
            risk_factors += len(complications)

        if risk_factors == 0:
            risk_level = "low"
        elif risk_factors <= 2:
            risk_level = "medium"
        else:
            risk_level = "high"

        # GBS (B 族链球菌) 状态
        gbs_status = random.choices(
            ["positive", "negative", "unknown"],
            weights=[0.25, 0.65, 0.10]
        )[0]

        records.append({
            "ob_id": gen_uuid(),
            "patient_id": pid,
            "gravida": gravida,
            "para": para,
            "gestational_weeks": gest_weeks,
            "edd": edd,
            "fetus_count": fetus_count,
            "prior_delivery_method": prior_method,
            "planned_delivery_method": planned_method,
            "risk_level": risk_level,
            "complications": json.dumps(complications) if complications else None,
            "gbs_status": gbs_status,
            "notes": None,
        })

    return pl.DataFrame(records)


def gen_rooms(n: int = 20) -> pl.DataFrame:
    """生成妇产科病房的房间记录 (房间号首字母对应类型, 百位对应楼层)。"""
    records = []

    room_configs = [
        # 待产室 (labor, 单床)
        ("L-201", "labor", 2), ("L-202", "labor", 2), ("L-203", "labor", 2),
        ("L-204", "labor", 2), ("L-205", "labor", 2),
        # 分娩间 / OR (delivery, 手术室)
        ("D-301", "delivery", 3), ("D-302", "delivery", 3), ("D-303", "delivery", 3),
        # 产后恢复室 (postpartum, 可多床)
        ("P-401", "postpartum", 4), ("P-402", "postpartum", 4), ("P-403", "postpartum", 4),
        ("P-404", "postpartum", 4), ("P-405", "postpartum", 4), ("P-406", "postpartum", 4),
        # 新生儿重症室 (NICU)
        ("NICU-501", "nicu", 5), ("NICU-502", "nicu", 5),
        # 预检分诊 (triage)
        ("T-101", "triage", 1), ("T-102", "triage", 1),
        # 额外的待产室
        ("L-206", "labor", 2), ("L-207", "labor", 2),
    ]

    for room_num, room_type, floor in room_configs:
        records.append({
            "room_id": gen_uuid(),
            "room_number": room_num,
            "room_type": room_type,
            "floor": floor,
        })

    return pl.DataFrame(records)


def gen_beds(rooms_df: pl.DataFrame) -> pl.DataFrame:
    """按房型配置生成床位 (labor/delivery/triage 单床, postpartum 双床, nicu 四床)。"""
    records = []

    room_type_beds = {
        "labor": 1,  # 单床
        "delivery": 1,  # 单床
        "postpartum": 2,  # 双床
        "nicu": 4,  # 多床
        "triage": 1,  # 单床
    }

    for row in rooms_df.iter_rows(named=True):
        num_beds = room_type_beds.get(row["room_type"], 1)
        labels = ["A", "B", "C", "D"][:num_beds]

        for label in labels:
            records.append({
                "bed_id": gen_uuid(),
                "room_id": row["room_id"],
                "bed_label": label,
                "status": "available",
                "current_admission_id": None,
            })

    return pl.DataFrame(records)


def gen_providers(n: int = 15) -> pl.DataFrame:
    """生成医护人员记录 (麻醉师 department 标 Anesthesiology, 其余 OB/GYN)。"""
    records = []

    all_providers = []
    for role, providers in PROVIDER_NAMES.items():
        for name, role_type in providers:
            all_providers.append((name, role_type))

    for name, role in all_providers:
        records.append({
            "provider_id": gen_uuid(),
            "name": name,
            "role": role,
            "department": "Obstetrics & Gynecology" if role != "anesthesiologist" else "Anesthesiology",
            "is_active": True,
        })

    return pl.DataFrame(records)


def gen_shifts(providers_df: pl.DataFrame, num_days: int = 3) -> pl.DataFrame:
    """生成医护排班 (覆盖 demo 当天 + 前 2 天共 3 天, 每天 day/night 两班)。"""
    records = []

    provider_by_role = {}
    for row in providers_df.iter_rows(named=True):
        role = row["role"]
        if role not in provider_by_role:
            provider_by_role[role] = []
        provider_by_role[role].append(row["provider_id"])

    base_date = REFERENCE_DATE.date()

    for day_offset in range(num_days):
        shift_date = base_date + timedelta(days=day_offset)

        for shift_type in ["day", "night"]:
            # 排主治医师 (每班 1 人)
            for attending_id in random.sample(provider_by_role.get("attending", []), min(1, len(provider_by_role.get("attending", [])))):
                records.append({
                    "shift_id": gen_uuid(),
                    "provider_id": attending_id,
                    "shift_date": shift_date,
                    "shift_type": shift_type,
                    "assigned_room_ids": json.dumps(["L-201", "L-202", "L-203", "L-204", "L-205"]),
                })

            # 排住院医师
            for resident_id in random.sample(provider_by_role.get("resident", []), min(1, len(provider_by_role.get("resident", [])))):
                records.append({
                    "shift_id": gen_uuid(),
                    "provider_id": resident_id,
                    "shift_date": shift_date,
                    "shift_type": shift_type,
                    "assigned_room_ids": json.dumps(["L-206", "L-207"]),
                })

            # 排护士 (每班 2-3 人)
            nurse_count = 2 if shift_type == "night" else 3
            for nurse_id in random.sample(provider_by_role.get("nurse", []), min(nurse_count, len(provider_by_role.get("nurse", [])))):
                records.append({
                    "shift_id": gen_uuid(),
                    "provider_id": nurse_id,
                    "shift_date": shift_date,
                    "shift_type": shift_type,
                    "assigned_room_ids": None,
                })

            # 排助产士
            for midwife_id in random.sample(provider_by_role.get("midwife", []), min(1, len(provider_by_role.get("midwife", [])))):
                records.append({
                    "shift_id": gen_uuid(),
                    "provider_id": midwife_id,
                    "shift_date": shift_date,
                    "shift_type": shift_type,
                    "assigned_room_ids": None,
                })

            # 排麻醉师
            for anesth_id in random.sample(provider_by_role.get("anesthesiologist", []), min(1, len(provider_by_role.get("anesthesiologist", [])))):
                records.append({
                    "shift_id": gen_uuid(),
                    "provider_id": anesth_id,
                    "shift_date": shift_date,
                    "shift_type": shift_type,
                    "assigned_room_ids": None,
                })

    return pl.DataFrame(records)


def gen_admissions(
    patients_df: pl.DataFrame,
    ob_profiles_df: pl.DataFrame,
    rooms_df: pl.DataFrame,
    beds_df: pl.DataFrame,
    providers_df: pl.DataFrame,
    num_current: int = 16
) -> tuple[pl.DataFrame, Optional[pl.DataFrame], pl.DataFrame, dict]:
    """生成场景驱动的住院记录。

    - 按状态分配临床上正确房型的床位 (in_labor -> labor, postpartum -> postpartum 等)。
    - 覆盖选定产妇的 OB 档案以落实 demo 埋点 (高危血压上升、双胎/早产、再次剖宫产)。
    - 返回 (admissions_df, bed_updates_df, ob_profiles_df_updated, demo_hooks),
      其中 demo_hooks 携带每条住院的 scenario_map, 以及 gen_orders / gen_alerts
      要用到的 admission_id。

    16 条 admission = 15 active (覆盖全部 5 个在院阶段) + 1 discharged
    (作 LOS 基线并覆盖第 6 个状态)。
    """
    records = []
    bed_updates = []
    scenario_map = {}
    demo_hooks = {}

    ob_by_pid = {row["patient_id"]: dict(row) for row in ob_profiles_df.iter_rows(named=True)}

    attendings = [row["provider_id"] for row in providers_df.iter_rows(named=True) if row["role"] == "attending"]
    nurses = [row["provider_id"] for row in providers_df.iter_rows(named=True) if row["role"] == "nurse"]

    # 按房型分组床位 (稳定顺序), 以便临床上正确地分床
    room_type_by_id = {r["room_id"]: r["room_type"] for r in rooms_df.iter_rows(named=True)}
    beds_by_type: dict = {}
    for b in beds_df.iter_rows(named=True):
        beds_by_type.setdefault(room_type_by_id.get(b["room_id"]), []).append(b)
    bed_ptr = {rt: 0 for rt in beds_by_type}

    def take_bed(room_type: Optional[str]) -> Optional[str]:
        """弹出给定房型的下一张空床 (用尽则返回 None)。"""
        beds = beds_by_type.get(room_type, [])
        idx = bed_ptr.get(room_type, 0)
        if idx < len(beds):
            bed_ptr[room_type] = idx + 1
            return beds[idx]["bed_id"]
        return None

    admission_scenarios = [
        # 活跃产程主角 (Q5 排第一): 宫口 8 cm, 最接近分娩
        {"status": "in_labor", "room_type": "labor", "hours_ago": 9, "max_dilation": 8.0},
        {"status": "in_labor", "room_type": "labor", "hours_ago": 7, "max_dilation": 6.0},
        # 高危血压上升 #1 -> 未确认 high_bp 告警
        {"status": "in_labor", "room_type": "labor", "hours_ago": 16, "max_dilation": 5.5,
         "force_high_risk": True, "rising_bp": True},
        # 高危血压上升 #2 -> 未确认 high_bp 告警
        {"status": "admitted", "room_type": "labor", "hours_ago": 14, "max_dilation": 3.0,
         "force_high_risk": True, "rising_bp": True},
        # 双胎 / 早产高危 -> 已确认 preterm_risk 告警
        {"status": "in_labor", "room_type": "labor", "hours_ago": 11, "max_dilation": 4.0,
         "force_high_risk": True, "twin_preterm": True},
        # 刚分娩 (<=2h), 在 delivery 房
        {"status": "delivered", "room_type": "delivery", "hours_ago": 4, "delivered_hours_ago": 1.5},
        {"status": "delivered", "room_type": "delivery", "hours_ago": 6, "delivered_hours_ago": 2.0},
        # 产后 / 待出院, 在 postpartum 房
        {"status": "postpartum", "room_type": "postpartum", "hours_ago": 36, "delivered_hours_ago": 30},
        {"status": "postpartum", "room_type": "postpartum", "hours_ago": 50, "delivered_hours_ago": 44},
        {"status": "ready_for_discharge", "room_type": "postpartum", "hours_ago": 74, "delivered_hours_ago": 66},
        {"status": "ready_for_discharge", "room_type": "postpartum", "hours_ago": 84, "delivered_hours_ago": 76},
        # triage 新入院 (早期产程); idx 11 -> 明日引产埋点
        {"status": "admitted", "room_type": "triage", "hours_ago": 4, "max_dilation": 2.0,
         "scheduled_induction": True},
        {"status": "admitted", "room_type": "triage", "hours_ago": 2, "max_dilation": 1.0},
        # 明日剖宫产 (术前, 在 labor 楼层)
        {"status": "admitted", "room_type": "labor", "hours_ago": 1, "max_dilation": 0.5,
         "scheduled_csection": True},
        {"status": "postpartum", "room_type": "postpartum", "hours_ago": 60, "delivered_hours_ago": 54},
        # 4 小时前出院 (LOS 基线 + 覆盖第 6 个状态)
        {"status": "discharged", "room_type": None, "hours_ago": 96, "delivered_hours_ago": 88,
         "discharge_hours_ago": 4},
    ]

    all_patient_ids = patients_df["patient_id"].to_list()
    n = min(num_current, len(all_patient_ids), len(admission_scenarios))
    selected_patients = all_patient_ids[:n]

    for i, patient_id in enumerate(selected_patients):
        scenario = admission_scenarios[i]
        status = scenario["status"]
        admission_id = gen_uuid()

        # ---- 覆盖 OB 档案, 让 demo 埋点彼此自洽 ----
        ob = ob_by_pid[patient_id]
        if scenario.get("force_high_risk"):
            ob["risk_level"] = "high"
            if i == 2:
                ob["complications"] = json.dumps(["Gestational hypertension", "Preeclampsia", "Anemia"])
            else:
                ob["complications"] = json.dumps(["Gestational hypertension", "Intrauterine growth restriction", "Anemia"])
        if scenario.get("twin_preterm"):
            ob["fetus_count"] = 2
            ob["gestational_weeks"] = 34.2
            ob["edd"] = (REFERENCE_DATE + timedelta(days=int((40 - 34.2) * 7))).date()
            ob["gravida"] = 1
            ob["para"] = 0
            ob["prior_delivery_method"] = "none"
            ob["planned_delivery_method"] = "c_section"
            ob["risk_level"] = "high"
            demo_hooks["preterm_admission_id"] = admission_id
        if scenario.get("scheduled_csection"):
            ob["planned_delivery_method"] = "c_section"
            ob["prior_delivery_method"] = "c_section"
            demo_hooks["csection_admission_id"] = admission_id
        if scenario.get("scheduled_induction"):
            demo_hooks["induction_admission_id"] = admission_id
        if status == "discharged":
            ob["planned_delivery_method"] = "c_section"

        # 保持 active 队列临床合理: 正在 (顺产) 产程中、早期入院、或计划再次剖宫产的
        # 产妇应是足月或接近足月的单胎 —— 而不是随机出现一个 41 周三胎却开到 8 cm。
        # 有意埋的双胎/早产案例 (idx4) 例外。
        if status in ("in_labor", "admitted") and not scenario.get("twin_preterm"):
            ob["fetus_count"] = 1
            if ob["gestational_weeks"] < 37.0:
                ob["gestational_weeks"] = round(random.uniform(37.0, 41.0), 1)
                ob["edd"] = (REFERENCE_DATE + timedelta(days=int((40 - ob["gestational_weeks"]) * 7))).date()
            # 正在顺产产程中的产妇不会是计划剖宫产
            if status == "in_labor" and ob["planned_delivery_method"] == "c_section":
                ob["planned_delivery_method"] = "vbac" if ob["prior_delivery_method"] == "c_section" else "vaginal"

        admit_time = REFERENCE_DATE - timedelta(hours=scenario["hours_ago"])

        delivery_method_actual = None
        delivery_time = None
        actual_discharge_time = None

        if status in ("delivered", "postpartum", "ready_for_discharge", "discharged"):
            delivered_hours_ago = scenario.get("delivered_hours_ago", scenario["hours_ago"] - 6)
            delivery_time = REFERENCE_DATE - timedelta(hours=delivered_hours_ago)
            delivery_method_actual = ob["planned_delivery_method"]
            if delivery_method_actual == "vbac":
                delivery_method_actual = random.choice(["vaginal", "c_section"])

        if status == "discharged":
            actual_discharge_time = REFERENCE_DATE - timedelta(hours=scenario.get("discharge_hours_ago", 4))

        # predicted_los_hours = 产后住院时长 (从 delivery_time 起算)
        predicted_los = None
        predicted_discharge = None
        if delivery_method_actual == "c_section":
            predicted_los = random.randint(72, 96)
        elif delivery_method_actual == "vaginal":
            predicted_los = random.randint(24, 48)
        if predicted_los and delivery_time:
            predicted_discharge = delivery_time + timedelta(hours=predicted_los)

        # 分配一张临床上正确房型的床位
        bed_id = take_bed(scenario.get("room_type"))
        if bed_id is not None:
            bed_updates.append({
                "bed_id": bed_id,
                "status": "occupied",
                "current_admission_id": admission_id,
            })

        records.append({
            "admission_id": admission_id,
            "patient_id": patient_id,
            "ob_id": ob["ob_id"],
            "admit_time": admit_time,
            "status": status,
            "delivery_method_actual": delivery_method_actual,
            "delivery_time": delivery_time,
            "predicted_los_hours": predicted_los,
            "predicted_discharge_time": predicted_discharge,
            "actual_discharge_time": actual_discharge_time,
            "current_bed_id": bed_id,
            "attending_provider_id": random.choice(attendings) if attendings else None,
            "primary_nurse_id": random.choice(nurses) if nurses else None,
        })

        scenario_map[admission_id] = {
            "max_dilation": scenario.get("max_dilation"),
            "rising_bp": bool(scenario.get("rising_bp", False)),
        }

    demo_hooks["scenario_map"] = scenario_map

    # 用 (含覆盖的) OB 档案重建 DataFrame, 保持原始行序
    ob_rows = [ob_by_pid[row["patient_id"]] for row in ob_profiles_df.iter_rows(named=True)]
    ob_profiles_df_updated = pl.DataFrame(ob_rows)

    bed_updates_df = pl.DataFrame(bed_updates) if bed_updates else None
    return pl.DataFrame(records), bed_updates_df, ob_profiles_df_updated, demo_hooks


def gen_labor_progress(admissions_df: pl.DataFrame, scenario_map: dict) -> pl.DataFrame:
    """生成产程进展记录, 时间界定在 [admit_time, delivery_time]。

    对 delivered/postpartum/ready/discharged 的住院, 上界是 delivery_time
    (分娩后不再有宫颈内诊)。对 admitted/in_labor, 上界是 REFERENCE_DATE, 且最新
    一条记录恰好达到该场景的目标宫口, 使 Q5 ("最接近分娩") 的排序是确定性的。
    """
    records = []

    labor_statuses = ("admitted", "in_labor", "delivered", "postpartum",
                      "ready_for_discharge", "discharged")

    for row in admissions_df.iter_rows(named=True):
        status = row["status"]
        if status not in labor_statuses:
            continue

        admit_time = row["admit_time"]
        delivery_time = row["delivery_time"]
        sc = scenario_map.get(row["admission_id"], {})

        # 上界: 已分娩取 delivery_time, 否则取当前时间
        end_time = delivery_time if delivery_time is not None else REFERENCE_DATE
        span = (end_time - admit_time).total_seconds() / 3600  # 小时
        if span <= 0:
            span = 1.0

        if status in ("delivered", "postpartum", "ready_for_discharge", "discharged"):
            max_dilation = 10.0
            num_records = max(3, min(10, int(span / 2) + 1))
        elif status == "in_labor":
            max_dilation = sc.get("max_dilation") or 6.0
            num_records = max(2, min(8, int(span / 2) + 1))
        else:  # admitted (早期产程)
            max_dilation = sc.get("max_dilation")
            if max_dilation is None:
                max_dilation = 3.0
            num_records = max(1, min(3, int(span / 3) + 1))

        interval = span / num_records
        membrane_ruptured = False

        for i in range(num_records):
            recorded_at = admit_time + timedelta(hours=i * interval)
            if recorded_at > end_time:
                recorded_at = end_time

            # 宫口单调递增; 最后一条记录恰好达到 max_dilation
            frac = (i + 1) / num_records
            dilation = round(max_dilation * frac, 1)
            dilation = max(0.0, min(10.0, dilation))

            if not membrane_ruptured and (dilation >= 4 or (i > 0 and random.random() < 0.1)):
                membrane_ruptured = True

            station = int(-3 + (dilation / 10) * 6)
            station = max(-3, min(3, station))
            effacement = int(min(100, 30 + dilation * 7))
            contraction_freq = 2 + int(dilation / 2)

            records.append({
                "progress_id": gen_uuid(),
                "admission_id": row["admission_id"],
                "recorded_at": recorded_at,
                "cervical_dilation_cm": dilation,
                "effacement_pct": effacement,
                "station": station,
                "contraction_freq": contraction_freq,
                "membrane_status": "ruptured" if membrane_ruptured else "intact",
                "notes": None,
            })

    return pl.DataFrame(records)


def gen_vital_signs(admissions_df: pl.DataFrame, scenario_map: dict) -> pl.DataFrame:
    """生成生命体征记录, 时间界定在 [admit_time, delivery_time 或当前时间]。

    对已分娩的住院只生成到 delivery_time, 因此 fetal_heart_rate 始终是宫内
    (in-utero) 胎儿读数 (分娩后不再有胎心)。标记 rising_bp 的住院会产生确定性上升的
    收缩压趋势, 越过 140 mmHg 警戒线 (这正是 gen_alerts 里两条未确认 high_bp 告警的来源)。
    """
    records = []

    for row in admissions_df.iter_rows(named=True):
        admit_time = row["admit_time"]
        delivery_time = row["delivery_time"]
        sc = scenario_map.get(row["admission_id"], {})
        rising = sc.get("rising_bp", False)

        end_time = delivery_time if delivery_time is not None else REFERENCE_DATE
        span = (end_time - admit_time).total_seconds() / 3600  # 小时
        if span <= 0:
            span = 1.0

        num_records = max(1, min(12, int(span / 3) + 1))
        interval = span / num_records

        for i in range(num_records):
            recorded_at = admit_time + timedelta(hours=i * interval)
            if recorded_at > end_time:
                recorded_at = end_time

            if rising:
                # 确定性爬升: 125 -> 131 -> 137 -> 143 -> 149 ...
                bp_systolic = 125 + i * 6
                bp_diastolic = 78 + i * 3
            else:
                bp_systolic = 114 + random.randint(-4, 5)
                bp_diastolic = 72 + random.randint(-3, 4)

            bp_systolic = max(90, min(180, bp_systolic))
            bp_diastolic = max(55, min(110, bp_diastolic))

            heart_rate = random.randint(70, 95)
            temperature = round(random.uniform(97.6, 99.4), 1)
            fetal_heart_rate = random.randint(125, 155)
            oxygen_saturation = round(random.uniform(96, 100), 1)

            records.append({
                "vital_id": gen_uuid(),
                "admission_id": row["admission_id"],
                "recorded_at": recorded_at,
                "bp_systolic": bp_systolic,
                "bp_diastolic": bp_diastolic,
                "heart_rate": heart_rate,
                "temperature": temperature,
                "fetal_heart_rate": fetal_heart_rate,
                "oxygen_saturation": oxygen_saturation,
            })

    return pl.DataFrame(records)


def gen_orders(
    admissions_df: pl.DataFrame,
    providers_df: pl.DataFrame,
    rooms_df: pl.DataFrame,
    demo_hooks: dict
) -> pl.DataFrame:
    """生成医嘱, 包含 demo 用的明日剖宫产 / 引产。

    明日 09:00 的剖宫产 (delivery 房) 与明日 14:00 的引产, 通过 demo_hooks 挂到
    gen_admissions 指定的特定 admission 上, 而不是随便挂在"第一个 admitted"产妇上。
    """
    records = []

    attendings = [row for row in providers_df.iter_rows(named=True) if row["role"] == "attending"]
    anesthesiologists = [row for row in providers_df.iter_rows(named=True) if row["role"] == "anesthesiologist"]
    delivery_rooms = [row for row in rooms_df.iter_rows(named=True) if row["room_type"] == "delivery"]

    for row in admissions_df.iter_rows(named=True):
        status = row["status"]
        admission_id = row["admission_id"]
        admit_time = row["admit_time"]

        # 给活跃产程中的产妇下硬膜外麻醉 (epidural) 医嘱
        if status == "in_labor" and random.random() < 0.7:
            records.append({
                "order_id": gen_uuid(),
                "admission_id": admission_id,
                "order_type": "epidural",
                "status": random.choice(["completed", "in_progress"]),
                "scheduled_time": admit_time + timedelta(hours=random.randint(2, 6)),
                "assigned_provider_id": random.choice(anesthesiologists)["provider_id"] if anesthesiologists else attendings[0]["provider_id"],
                "assigned_room_id": None,
                "priority": "routine",
                "notes": "Patient requested epidural",
                "created_by": random.choice(["RN Jessica Martinez", "RN Amanda Thompson"]),
            })

        # 常规化验
        if random.random() < 0.6:
            records.append({
                "order_id": gen_uuid(),
                "admission_id": admission_id,
                "order_type": "lab_test",
                "status": "completed",
                "scheduled_time": admit_time + timedelta(hours=1),
                "assigned_provider_id": random.choice(attendings)["provider_id"],
                "assigned_room_id": None,
                "priority": "routine",
                "notes": "CBC, Type & Screen",
                "created_by": random.choice(attendings)["name"],
            })

    # Demo 场景 5: 明日 09:00 在 delivery 房的 scheduled 剖宫产
    tomorrow_9am = REFERENCE_DATE.replace(hour=9, minute=0, second=0) + timedelta(days=1)
    csection_aid = demo_hooks.get("csection_admission_id")
    if csection_aid:
        records.append({
            "order_id": gen_uuid(),
            "admission_id": csection_aid,
            "order_type": "c_section",
            "status": "scheduled",
            "scheduled_time": tomorrow_9am,
            "assigned_provider_id": attendings[0]["provider_id"] if attendings else None,
            "assigned_room_id": delivery_rooms[0]["room_id"] if delivery_rooms else None,
            "priority": "routine",
            "notes": "Scheduled cesarean section - repeat C-section",
            "created_by": "Dr. Michael Chen",
        })

    # 第二台计划操作 (引产), 明日 14:00
    tomorrow_2pm = REFERENCE_DATE.replace(hour=14, minute=0, second=0) + timedelta(days=1)
    induction_aid = demo_hooks.get("induction_admission_id")
    if induction_aid:
        records.append({
            "order_id": gen_uuid(),
            "admission_id": induction_aid,
            "order_type": "induction",
            "status": "scheduled",
            "scheduled_time": tomorrow_2pm,
            "assigned_provider_id": attendings[1]["provider_id"] if len(attendings) > 1 else attendings[0]["provider_id"],
            "assigned_room_id": None,
            "priority": "routine",
            "notes": "Induction of labor - post-dates",
            "created_by": "Dr. Sarah Williams",
        })

    return pl.DataFrame(records)


def gen_alerts(
    admissions_df: pl.DataFrame,
    vital_signs_df: pl.DataFrame,
    providers_df: pl.DataFrame,
    demo_hooks: dict
) -> pl.DataFrame:
    """生成临床告警: 2 条未确认 high_bp + 1 条已确认 preterm_risk。

    high_bp 告警来自两条血压上升、vital 越过警戒线的住院; preterm_risk 告警挂在
    指定的双胎/早产住院上, 使告警内容与底层数据一致。
    """
    records = []

    nurses = [row for row in providers_df.iter_rows(named=True) if row["role"] == "nurse"]

    # vital 越过 BP 警戒线的住院
    high_bp_set = set()
    for v in vital_signs_df.iter_rows(named=True):
        if v["bp_systolic"] >= 140 or v["bp_diastolic"] >= 90:
            high_bp_set.add(v["admission_id"])

    # 最多发出 2 条未确认 high_bp 告警 (按确定性的 admission 顺序)
    count = 0
    for row in admissions_df.iter_rows(named=True):
        if count >= 2:
            break
        if row["admission_id"] in high_bp_set:
            records.append({
                "alert_id": gen_uuid(),
                "admission_id": row["admission_id"],
                "alert_type": "high_bp",
                "severity": "warning",
                "message": "Blood pressure trending upward: 125 -> 131 -> 137 -> 143 mmHg systolic. Recommend increased monitoring frequency and OB notification.",
                "triggered_at": REFERENCE_DATE - timedelta(hours=2),
                "acknowledged": False,
                "acknowledged_by": None,
            })
            count += 1

    # 在双胎/早产住院上发 1 条已确认的 preterm_risk 告警
    preterm_aid = demo_hooks.get("preterm_admission_id")
    if preterm_aid:
        records.append({
            "alert_id": gen_uuid(),
            "admission_id": preterm_aid,
            "alert_type": "preterm_risk",
            "severity": "warning",
            "message": "Twin pregnancy at 34 weeks - preterm delivery risk. NICU notified and on standby (beds available).",
            "triggered_at": REFERENCE_DATE - timedelta(hours=6),
            "acknowledged": True,
            "acknowledged_by": nurses[0]["provider_id"] if nurses else None,
        })

    return pl.DataFrame(records)


def update_beds_with_admissions(
    beds_df: pl.DataFrame,
    bed_updates_df: Optional[pl.DataFrame],
    rooms_df: pl.DataFrame
) -> pl.DataFrame:
    """先应用 occupied 床位分配, 再按房型放置 cleaning/maintenance 床位。

    保证 2 张 cleaning + 1 张 maintenance, 其中 1 张 cleaning 在 labor 房
    (这样 "labor 房 ~30 分钟后腾出" 的 demo 有数据支撑), 另 1 张 cleaning 与那张
    maintenance 在 postpartum 房。
    """
    room_type_by_id = {r["room_id"]: r["room_type"] for r in rooms_df.iter_rows(named=True)}

    if bed_updates_df is not None and not bed_updates_df.is_empty():
        updates = {row["bed_id"]: row for row in bed_updates_df.iter_rows(named=True)}
    else:
        updates = {}

    recs = []
    for row in beds_df.iter_rows(named=True):
        rec = dict(row)
        if rec["bed_id"] in updates:
            rec["status"] = "occupied"
            rec["current_admission_id"] = updates[rec["bed_id"]]["current_admission_id"]
        recs.append(rec)

    # 在剩余空床中按房型放置特殊状态 (cleaning/maintenance)
    quotas = {
        ("labor", "cleaning"): 1,
        ("postpartum", "cleaning"): 1,
        ("postpartum", "maintenance"): 1,
    }
    for rec in recs:
        if rec["status"] != "available":
            continue
        rt = room_type_by_id.get(rec["room_id"])
        if rt == "labor" and quotas[("labor", "cleaning")] > 0:
            rec["status"] = "cleaning"
            quotas[("labor", "cleaning")] -= 1
        elif rt == "postpartum" and quotas[("postpartum", "cleaning")] > 0:
            rec["status"] = "cleaning"
            quotas[("postpartum", "cleaning")] -= 1
        elif rt == "postpartum" and quotas[("postpartum", "maintenance")] > 0:
            rec["status"] = "maintenance"
            quotas[("postpartum", "maintenance")] -= 1

    return pl.DataFrame(recs)


# ============================================================================
# 核心函数 (幂等)
# ============================================================================
def generate_all_tsv() -> dict:
    """生成全部 TSV 文件。幂等: 先删除已有文件再写。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 删除已有的 TSV 文件
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating patients...")
    df_patients = gen_patients(n=50)
    df_patients.write_csv(DATA_DIR / "01_patient.tsv", separator="\t")

    print("Generating OB profiles...")
    df_ob_profiles = gen_ob_profiles(df_patients)
    # 注意: 02_ob_profile.tsv 在稍后写出, 即 gen_admissions 应用了它那些
    # demo 驱动的临床覆盖 (高危、双胎/早产、再次剖宫产) 之后。

    print("Generating rooms...")
    df_rooms = gen_rooms()
    df_rooms.write_csv(DATA_DIR / "03_room.tsv", separator="\t")

    print("Generating providers...")
    df_providers = gen_providers()
    df_providers.write_csv(DATA_DIR / "04_provider.tsv", separator="\t")

    print("Generating shifts...")
    df_shifts = gen_shifts(df_providers)
    df_shifts.write_csv(DATA_DIR / "05_shift.tsv", separator="\t")

    print("Generating beds...")
    df_beds = gen_beds(df_rooms)

    print("Generating admissions...")
    df_admissions, bed_updates, df_ob_profiles, demo_hooks = gen_admissions(
        df_patients, df_ob_profiles, df_rooms, df_beds, df_providers
    )
    # 此刻持久化 (含覆盖的) OB 档案与 admissions
    df_ob_profiles.write_csv(DATA_DIR / "02_ob_profile.tsv", separator="\t")
    df_admissions.write_csv(DATA_DIR / "06_admission.tsv", separator="\t")
    scenario_map = demo_hooks["scenario_map"]

    print("Updating beds with admission assignments...")
    df_beds = update_beds_with_admissions(df_beds, bed_updates, df_rooms)
    df_beds.write_csv(DATA_DIR / "07_bed.tsv", separator="\t")

    print("Generating labor progress...")
    df_labor_progress = gen_labor_progress(df_admissions, scenario_map)
    df_labor_progress.write_csv(DATA_DIR / "08_labor_progress.tsv", separator="\t")

    print("Generating vital signs...")
    df_vital_signs = gen_vital_signs(df_admissions, scenario_map)
    df_vital_signs.write_csv(DATA_DIR / "09_vital_sign.tsv", separator="\t")

    print("Generating orders...")
    df_orders = gen_orders(df_admissions, df_providers, df_rooms, demo_hooks)
    df_orders.write_csv(DATA_DIR / "10_medical_order.tsv", separator="\t")

    print("Generating alerts...")
    df_alerts = gen_alerts(df_admissions, df_vital_signs, df_providers, demo_hooks)
    df_alerts.write_csv(DATA_DIR / "11_alert.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")

    return {
        "patients": df_patients,
        "ob_profiles": df_ob_profiles,
        "rooms": df_rooms,
        "beds": df_beds,
        "providers": df_providers,
        "shifts": df_shifts,
        "admissions": df_admissions,
        "labor_progress": df_labor_progress,
        "vital_signs": df_vital_signs,
        "orders": df_orders,
        "alerts": df_alerts,
    }


def parse_datetime(val):
    """解析 datetime 字符串, 无法解析则返回 None。"""
    if val is None or val == "" or val == "null":
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def parse_date(val):
    """解析 date 字符串, 无法解析则返回 None。"""
    if val is None or val == "" or val == "null":
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def create_sqlite_database() -> None:
    """从 TSV 文件构建 SQLite 数据库。幂等: 先删除已有 DB 再建。"""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # 按拓扑顺序加载

        # 1. Patient (无外键)
        df = pl.read_csv(DATA_DIR / "01_patient.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Patient(**row))

        # 2. OB Profile (外键: patient)
        df = pl.read_csv(DATA_DIR / "02_ob_profile.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            row_dict["edd"] = parse_date(row_dict.get("edd"))
            if row_dict.get("complications") == "":
                row_dict["complications"] = None
            if row_dict.get("notes") == "":
                row_dict["notes"] = None
            session.add(OBProfile(**row_dict))

        # 3. Room (无外键)
        df = pl.read_csv(DATA_DIR / "03_room.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Room(**row))

        # 4. Provider (无外键)
        df = pl.read_csv(DATA_DIR / "04_provider.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            session.add(Provider(**row))

        # 5. Shift (外键: provider)
        df = pl.read_csv(DATA_DIR / "05_shift.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            row_dict["shift_date"] = parse_date(row_dict.get("shift_date"))
            if row_dict.get("assigned_room_ids") == "":
                row_dict["assigned_room_ids"] = None
            session.add(Shift(**row_dict))

        # 6. Admission (外键: patient, ob_profile, provider)
        df = pl.read_csv(DATA_DIR / "06_admission.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            # 处理 datetime 字段
            row_dict["admit_time"] = parse_datetime(row_dict.get("admit_time"))
            row_dict["delivery_time"] = parse_datetime(row_dict.get("delivery_time"))
            row_dict["predicted_discharge_time"] = parse_datetime(row_dict.get("predicted_discharge_time"))
            row_dict["actual_discharge_time"] = parse_datetime(row_dict.get("actual_discharge_time"))
            # 处理可空字段
            for key in ["delivery_method_actual", "predicted_los_hours",
                       "current_bed_id", "attending_provider_id", "primary_nurse_id"]:
                if key in row_dict and row_dict[key] == "":
                    row_dict[key] = None
            session.add(Admission(**row_dict))

        # 7. Bed (外键: room, admission)
        df = pl.read_csv(DATA_DIR / "07_bed.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            if row_dict.get("current_admission_id") == "":
                row_dict["current_admission_id"] = None
            session.add(Bed(**row_dict))

        # 8. Labor Progress (外键: admission)
        df = pl.read_csv(DATA_DIR / "08_labor_progress.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            row_dict["recorded_at"] = parse_datetime(row_dict.get("recorded_at"))
            for key in ["effacement_pct", "station", "contraction_freq", "notes"]:
                if key in row_dict and row_dict[key] == "":
                    row_dict[key] = None
            session.add(LaborProgress(**row_dict))

        # 9. Vital Sign (外键: admission)
        df = pl.read_csv(DATA_DIR / "09_vital_sign.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            row_dict["recorded_at"] = parse_datetime(row_dict.get("recorded_at"))
            session.add(VitalSign(**row_dict))

        # 10. Order (外键: admission, provider, room)
        df = pl.read_csv(DATA_DIR / "10_medical_order.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            row_dict["scheduled_time"] = parse_datetime(row_dict.get("scheduled_time"))
            if row_dict.get("assigned_room_id") == "":
                row_dict["assigned_room_id"] = None
            if row_dict.get("notes") == "":
                row_dict["notes"] = None
            session.add(Order(**row_dict))

        # 11. Alert (外键: admission, provider)
        df = pl.read_csv(DATA_DIR / "11_alert.tsv", separator="\t")
        for row in df.iter_rows(named=True):
            row_dict = dict(row)
            row_dict["triggered_at"] = parse_datetime(row_dict.get("triggered_at"))
            if row_dict.get("acknowledged_by") == "":
                row_dict["acknowledged_by"] = None
            session.add(Alert(**row_dict))

        session.commit()

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    """主入口。"""
    print("=" * 60)
    print("MaterniFlow Fake Data Generator")
    print("=" * 60)
    print(f"Reference date: {REFERENCE_DATE}")
    print()

    print("Starting data generation...")
    data = generate_all_tsv()

    print()
    print("Creating SQLite database...")
    create_sqlite_database()

    print()
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    for name, df in data.items():
        print(f"  {name}: {len(df)} records")

    print()
    print("All done!")


if __name__ == "__main__":
    main()
