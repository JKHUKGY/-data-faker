"""
医疗器械 - 骨科植入物追踪 合成数据生成器
复杂度: High (企业级分析数据集市)
所属系统: 由 MidAtlantic Orthopedic Health Network (MAOHN, 米德大西洋骨科医疗网络,
一家虚构的 12 家医院集团) 运营的骨科植入物中央登记系统.

本生成器产出一个医院侧的植入物登记库, 数据汇总自五个上游 feed (Epic EHR, ERP,
手术信息系统 SIS, GUDID feed, FDA enforcement RSS). 原始事件表 (inventory_movement,
quality_test_event, pricing_history, patient_followup_visit, audit_log) 是唯一可信源;
inventory 上的 silver 层 "当前态" 列是在生成过程中从原始事件派生出来的, 因此两层永远不会漂移.

业务背景, 数据归属, 数据流, 以及完整的生成不变式清单, 请见 ER 文档.
"""

from __future__ import annotations

import json
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
DATABASE_PATH = OUTPUT_DIR / "medical_devices_orthopedic_implant_tracking_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# "Now" 锚点: 所有日期生成都相对于它, 这样重复运行结果保持稳定.
NOW = datetime(2026, 6, 1, 12, 0, 0)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    pass


class ImplantCategory(Base):
    __tablename__ = "implant_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text)


class Manufacturer(Base):
    __tablename__ = "manufacturer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100))
    contact_email: Mapped[str] = mapped_column(String(255))
    contact_phone: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ImplantProduct(Base):
    __tablename__ = "implant_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_category.id"))
    manufacturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("manufacturer.id"))
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_number: Mapped[str] = mapped_column(String(100))
    udi_di: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    material: Mapped[str] = mapped_column(String(100))
    size_specification: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Hospital(Base):
    __tablename__ = "hospital"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str] = mapped_column(String(20))
    trauma_level: Mapped[str | None] = mapped_column(String(20))


class Surgeon(Base):
    __tablename__ = "surgeon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    npi_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    specialty: Mapped[str] = mapped_column(String(100))
    license_number: Mapped[str] = mapped_column(String(50))
    license_state: Mapped[str] = mapped_column(String(2))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    years_experience: Mapped[int | None] = mapped_column(Integer)


class Patient(Base):
    __tablename__ = "patient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mrn: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[datetime] = mapped_column(DateTime)
    gender: Mapped[str] = mapped_column(String(10))
    blood_type: Mapped[str | None] = mapped_column(String(10))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    allergies: Mapped[str | None] = mapped_column(Text)
    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_policy_number: Mapped[str | None] = mapped_column(String(50))


class RegulatorySubmission(Base):
    __tablename__ = "regulatory_submission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_product.id"))
    submission_type: Mapped[str] = mapped_column(String(20))
    submission_number: Mapped[str] = mapped_column(String(50), unique=True)
    submission_date: Mapped[datetime] = mapped_column(DateTime)
    approval_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))
    regulatory_body: Mapped[str] = mapped_column(String(50))
    submission_path: Mapped[str | None] = mapped_column(String(255))


class PricingHistory(Base):
    __tablename__ = "pricing_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_product.id"))
    manufacturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("manufacturer.id"))
    effective_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    list_price_usd: Mapped[float] = mapped_column(Float)
    contracted_price_usd: Mapped[float] = mapped_column(Float)
    contract_type: Mapped[str] = mapped_column(String(30))


class ImplantLot(Base):
    __tablename__ = "implant_lot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_product.id"))
    lot_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    expiration_date: Mapped[datetime] = mapped_column(DateTime)
    manufacture_date: Mapped[datetime] = mapped_column(DateTime)
    quantity_manufactured: Mapped[int] = mapped_column(Integer)
    sterilization_method: Mapped[str | None] = mapped_column(String(100))


class QualityTestEvent(Base):
    __tablename__ = "quality_test_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_lot.id"))
    test_date: Mapped[datetime] = mapped_column(DateTime)
    test_type: Mapped[str] = mapped_column(String(50))
    result: Mapped[str] = mapped_column(String(20))
    tester: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class PurchaseOrder(Base):
    __tablename__ = "purchase_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospital.id"))
    manufacturer_id: Mapped[int] = mapped_column(Integer, ForeignKey("manufacturer.id"))
    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime)
    expected_delivery_date: Mapped[datetime] = mapped_column(DateTime)
    actual_delivery_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))
    is_consignment: Mapped[bool] = mapped_column(Boolean)
    total_amount_usd: Mapped[float] = mapped_column(Float)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospital.id"))
    lot_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_lot.id"))
    purchase_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_order.id"))
    serial_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    udi_pi: Mapped[str] = mapped_column(String(100), nullable=False)
    received_date: Mapped[datetime] = mapped_column(DateTime)
    is_consignment: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(100))
    last_updated: Mapped[datetime] = mapped_column(DateTime)


class InventoryMovement(Base):
    __tablename__ = "inventory_movement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory.id"))
    sequence_no: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[str] = mapped_column(String(20))
    movement_date: Mapped[datetime] = mapped_column(DateTime)
    from_location: Mapped[str | None] = mapped_column(String(100))
    to_location: Mapped[str | None] = mapped_column(String(100))
    performed_by: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class Surgery(Base):
    __tablename__ = "surgery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"))
    surgeon_id: Mapped[int] = mapped_column(Integer, ForeignKey("surgeon.id"))
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospital.id"))
    revision_of_surgery_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("surgery.id"))
    surgery_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    procedure_code: Mapped[str] = mapped_column(String(20))
    procedure_name: Mapped[str] = mapped_column(String(200))
    diagnosis_code: Mapped[str] = mapped_column(String(20))
    diagnosis_description: Mapped[str] = mapped_column(Text)
    surgery_type: Mapped[str] = mapped_column(String(20))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    anesthesia_type: Mapped[str | None] = mapped_column(String(50))
    asa_score: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class SurgeryImplant(Base):
    __tablename__ = "surgery_implant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    surgery_id: Mapped[int] = mapped_column(Integer, ForeignKey("surgery.id"))
    inventory_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory.id"), unique=True)
    implant_site: Mapped[str | None] = mapped_column(String(100))
    implantation_timestamp: Mapped[datetime] = mapped_column(DateTime)
    implanted_by_surgeon_id: Mapped[int] = mapped_column(Integer, ForeignKey("surgeon.id"))


class AdverseEvent(Base):
    __tablename__ = "adverse_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    surgery_implant_id: Mapped[int] = mapped_column(Integer, ForeignKey("surgery_implant.id"))
    event_date: Mapped[datetime] = mapped_column(DateTime)
    event_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    reported_by: Mapped[str] = mapped_column(String(200))
    reported_date: Mapped[datetime] = mapped_column(DateTime)
    fda_mdr_number: Mapped[str | None] = mapped_column(String(50))
    patient_outcome: Mapped[str | None] = mapped_column(String(100))
    corrective_action: Mapped[str | None] = mapped_column(Text)


class PatientFollowupVisit(Base):
    __tablename__ = "patient_followup_visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patient.id"))
    surgery_implant_id: Mapped[int] = mapped_column(Integer, ForeignKey("surgery_implant.id"))
    visit_date: Mapped[datetime] = mapped_column(DateTime)
    visit_type: Mapped[str] = mapped_column(String(30))
    functional_score: Mapped[str | None] = mapped_column(String(20))
    revision_indicated: Mapped[bool] = mapped_column(Boolean, default=False)
    clinician_notes: Mapped[str | None] = mapped_column(Text)
    clinician_name: Mapped[str] = mapped_column(String(200))


class Recall(Base):
    __tablename__ = "recall"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("implant_product.id"))
    lot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("implant_lot.id"))
    recall_number: Mapped[str] = mapped_column(String(50), unique=True)
    recall_date: Mapped[datetime] = mapped_column(DateTime)
    recall_reason: Mapped[str] = mapped_column(Text)
    recall_class: Mapped[str] = mapped_column(String(20))
    fda_enforcement_report: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    completion_date: Mapped[datetime | None] = mapped_column(DateTime)


class RecallNotification(Base):
    __tablename__ = "recall_notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recall_id: Mapped[int] = mapped_column(Integer, ForeignKey("recall.id"))
    surgery_implant_id: Mapped[int] = mapped_column(Integer, ForeignKey("surgery_implant.id"))
    notification_date: Mapped[datetime] = mapped_column(DateTime)
    notification_method: Mapped[str] = mapped_column(String(30))
    notified_party: Mapped[str] = mapped_column(String(50))
    acknowledgment_date: Mapped[datetime | None] = mapped_column(DateTime)
    action_taken: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(50))
    record_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(10))
    changed_by: Mapped[str] = mapped_column(String(200))
    change_timestamp: Mapped[datetime] = mapped_column(DateTime)
    old_values: Mapped[str | None] = mapped_column(Text)
    new_values: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)


# ============================================================================
# 辅助函数
# ============================================================================
def dt_between(start: datetime, end: datetime) -> datetime:
    """在 [start, end) 内采样一个 datetime. 区间为空时回退到 start."""
    if end <= start:
        return start
    delta_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(1, delta_seconds - 1)))


def weighted_choice(values: list, weights: list[float]):
    return random.choices(values, weights=weights, k=1)[0]


# ============================================================================
# 生成器 - 参考数据
# ============================================================================
def gen_implant_categories() -> pl.DataFrame:
    """骨科植入物品类的静态目录."""
    categories = [
        {"id": 1, "name": "Bone Plate", "description": "Metal plates for fracture fixation"},
        {"id": 2, "name": "Bone Screw", "description": "Screws for securing plates or fragments"},
        {"id": 3, "name": "Intramedullary Nail", "description": "Rods inserted into bone marrow cavity"},
        {"id": 4, "name": "Hip Replacement", "description": "Total or partial hip prosthesis"},
        {"id": 5, "name": "Knee Replacement", "description": "Total or partial knee prosthesis"},
        {"id": 6, "name": "Spinal Implant", "description": "Devices for spinal fusion or stabilization"},
        {"id": 7, "name": "Shoulder Implant", "description": "Shoulder joint replacement components"},
        {"id": 8, "name": "External Fixator", "description": "External frame for bone stabilization"},
    ]
    return pl.DataFrame(categories)


def gen_manufacturers(n: int = 15) -> pl.DataFrame:
    """制造商维度. 参考数据, 来源于 GUDID feed."""
    records = []
    names = [
        "Stryker Corporation", "Zimmer Biomet", "DePuy Synthes (J&J)", "Smith & Nephew",
        "Medtronic Spine", "NuVasive", "Globus Medical", "Arthrex", "Wright Medical",
        "Integra LifeSciences", "Acumed LLC", "Orthofix Medical", "MicroPort Orthopedics",
        "Exactech", "ConMed Corporation",
    ]
    for i in range(1, n + 1):
        records.append({
            "id": i,
            "name": names[i - 1] if i <= len(names) else fake.company(),
            "country": weighted_choice(
                ["USA", "Switzerland", "Germany", "Ireland"], [0.7, 0.1, 0.1, 0.1]
            ),
            "contact_email": fake.company_email(),
            "contact_phone": fake.phone_number(),
            "is_active": weighted_choice([True, False], [0.85, 0.15]),
        })
    return pl.DataFrame(records)


def gen_implant_products(
    category_ids: list[int], manufacturer_ids: list[int], n: int = 200
) -> pl.DataFrame:
    """产品维度. 参考数据, 来源于 GUDID feed."""
    records = []
    materials = [
        "Titanium Alloy", "Stainless Steel 316L", "Cobalt-Chromium",
        "Ceramic (Alumina)", "PEEK Polymer",
    ]
    for i in range(1, n + 1):
        records.append({
            "id": i,
            "category_id": random.choice(category_ids),
            "manufacturer_id": random.choice(manufacturer_ids),
            "product_name": (
                f"{fake.word().title()} "
                f"{random.choice(['Pro', 'Elite', 'Advanced', 'Classic', 'Apex'])} System"
            ),
            "model_number": f"MDL-{random.randint(1000, 9999)}",
            # GS1 AI 01 = 14 位 GTIN
            "udi_di": fake.unique.numerify("00382000######"),
            "material": random.choice(materials),
            "size_specification": (
                f"{random.choice(['Small', 'Medium', 'Large', 'XL'])}"
                f"-{random.randint(80, 180)}mm"
                if random.random() > 0.3 else None
            ),
            "is_active": weighted_choice([True, False], [0.85, 0.15]),
        })
    return pl.DataFrame(records)


def gen_hospitals(n: int = 12) -> pl.DataFrame:
    """MAOHN 旗下的医院网络."""
    records = []
    trauma_levels = ["Level I", "Level II", "Level III", None]
    trauma_weights = [0.15, 0.25, 0.30, 0.30]
    for i in range(1, n + 1):
        records.append({
            "id": i,
            "name": (
                f"{fake.city()} "
                f"{random.choice(['General', 'Medical Center', 'Regional', 'Memorial', 'University'])} "
                f"Hospital"
            ),
            "address": fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip_code": fake.zipcode(),
            "phone": fake.phone_number(),
            "trauma_level": weighted_choice(trauma_levels, trauma_weights),
        })
    return pl.DataFrame(records)


def gen_surgeons(n: int = 100) -> pl.DataFrame:
    """持有资质的骨科医生. NPI 全局唯一."""
    records = []
    specialties = [
        "Orthopedic Surgery - Trauma",
        "Orthopedic Surgery - Joint Replacement",
        "Orthopedic Surgery - Spine",
        "Orthopedic Surgery - Sports Medicine",
        "Orthopedic Surgery - Hand & Wrist",
        "Orthopedic Surgery - Foot & Ankle",
    ]
    for i in range(1, n + 1):
        records.append({
            "id": i,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "npi_number": str(fake.unique.random_int(min=1000000000, max=9999999999)),
            "specialty": random.choice(specialties),
            "license_number": f"MD{random.randint(10000, 99999)}",
            "license_state": fake.state_abbr(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "years_experience": random.randint(5, 35) if random.random() > 0.1 else None,
        })
    return pl.DataFrame(records)


def gen_patients(n: int = 500) -> pl.DataFrame:
    """患者维度, 来源于 Epic EHR."""
    records = []
    blood_types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    for i in range(1, n + 1):
        dob = fake.date_of_birth(minimum_age=18, maximum_age=95)
        records.append({
            "id": i,
            "mrn": f"MRN{fake.unique.random_int(min=1000000, max=9999999)}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "date_of_birth": datetime.combine(dob, datetime.min.time()),
            "gender": weighted_choice(["Male", "Female", "Other"], [0.49, 0.49, 0.02]),
            "blood_type": random.choice(blood_types) if random.random() > 0.2 else None,
            "weight_kg": round(random.uniform(45, 120), 1) if random.random() > 0.1 else None,
            "height_cm": round(random.uniform(150, 200), 1) if random.random() > 0.1 else None,
            "allergies": random.choice(
                [None, "Penicillin", "Latex", "Nickel", "Penicillin, Latex"]
            ),
            "insurance_provider": weighted_choice(
                ["Medicare", "Medicare Advantage", "Blue Cross Blue Shield",
                 "United Healthcare", "Aetna", "Cigna", "Medicaid", "Self-pay"],
                [0.30, 0.25, 0.12, 0.10, 0.08, 0.07, 0.05, 0.03],
            ),
            "insurance_policy_number": f"POL-{random.randint(100000, 9999999)}",
        })
    return pl.DataFrame(records)


# ============================================================================
# 生成器 - 监管与价格参考 (raw + silver)
# ============================================================================
def gen_regulatory_submissions(product_ids: list[int], n: int = 250) -> pl.DataFrame:
    """监管申报记录. FDA 批准日期的唯一可信源.
    status 与 approval_date 保持自洽: Approved/Denied 有日期, Pending/Withdrawn 没有."""
    records = []
    submission_types = ["510(k)", "PMA", "De Novo", "HDE"]
    submission_weights = [0.75, 0.15, 0.07, 0.03]
    statuses = ["Approved", "Pending", "Denied", "Withdrawn"]
    status_weights = [0.70, 0.15, 0.10, 0.05]
    regulatory_bodies = ["FDA", "EMA", "Health Canada"]
    body_weights = [0.85, 0.10, 0.05]

    for i in range(1, n + 1):
        sub_type = weighted_choice(submission_types, submission_weights)
        status = weighted_choice(statuses, status_weights)
        submission_date = dt_between(NOW - timedelta(days=15 * 365), NOW - timedelta(days=180))

        if status in ("Approved", "Denied"):
            # Approved/Denied 一定有一个严格晚于申报日的决定日期
            min_review = 90 if sub_type == "510(k)" else 180
            max_review = 365 if sub_type == "510(k)" else 540
            decision_date = submission_date + timedelta(
                days=random.randint(min_review, max_review)
            )
            decision_date = min(decision_date, NOW)
            approval_date = decision_date
        else:
            approval_date = None

        records.append({
            "id": i,
            "product_id": random.choice(product_ids),
            "submission_type": sub_type,
            "submission_number": (
                f"{sub_type.replace('(', '').replace(')', '')}-"
                f"{fake.unique.random_int(min=100000, max=9999999)}"
            ),
            "submission_date": submission_date,
            "approval_date": approval_date,
            "status": status,
            "regulatory_body": weighted_choice(regulatory_bodies, body_weights),
            "submission_path": (
                f"/documents/regulatory/{sub_type.lower()}/{random.randint(1000, 9999)}.pdf"
            ),
        })
    return pl.DataFrame(records)


def gen_pricing_history(
    product_ids: list[int], product_manufacturer_map: dict[int, int], n: int = 500
) -> pl.DataFrame:
    """SCD2 价格历史. 每个产品至少有一个区间, 这样按 point-in-time 价格做 LEFT JOIN
    永远不会出 NULL. 最新一个区间的 end_date=NULL (当前生效).
    合同折扣: GPO/Direct 为 10-30%, Consignment 为 0%."""
    records = []
    contract_types = ["GPO", "Direct", "Consignment"]
    contract_weights = [0.55, 0.25, 0.20]
    rec_id = 1

    from collections import defaultdict
    # 保证每个产品都至少有一个区间.
    per_product: dict[int, int] = defaultdict(lambda: 1)
    for pid in product_ids:
        _ = per_product[pid]  # 触碰一下, 以默认值 1 插入

    # 再把剩余配额随机撒到各产品上 (这样有些产品会拿到 2 或 3 个区间).
    extra_budget = max(0, n - len(product_ids))
    for _ in range(extra_budget):
        per_product[random.choice(product_ids)] += 1

    # 本数据集里最早可能的 received_date 受最早的 lot.manufacture_date 约束
    # (NOW - 5 年; 见 gen_implant_lots). 价格至少要覆盖到那个下界,
    # 否则 point-in-time 价格查询会出 NULL.
    # 这里把最早区间的起点钉在 NOW - 6 年, 留出 1 年安全余量.
    PRICING_EARLIEST_FLOOR = NOW - timedelta(days=6 * 365)

    for product_id, count in per_product.items():
        n_intervals = min(count, 3)
        # 从 "now" 往回走, 每段区间随机取 6 到 24 个月
        end_marker = NOW
        intervals: list[tuple[datetime, datetime | None]] = []
        for k in range(n_intervals):
            length_days = random.randint(180, 720)
            start = end_marker - timedelta(days=length_days)
            this_end: datetime | None = None if k == 0 else end_marker
            intervals.append((start, this_end))
            end_marker = start
        # 反转一下让最早的区间排在最前 (仅为美观)
        intervals.reverse()
        # 确保最早的区间向前延伸到 PRICING_EARLIEST_FLOOR,
        # 这样任何收过货的 lot 都有一个有效的 point-in-time 合同价.
        if intervals[0][0] > PRICING_EARLIEST_FLOOR:
            intervals[0] = (PRICING_EARLIEST_FLOOR, intervals[0][1])

        list_price = round(random.uniform(500, 15000), 2)
        for start, end in intervals:
            contract_type = weighted_choice(contract_types, contract_weights)
            # 文档口径: GPO 合同相对 MSRP 折让 10-30%; Consignment 按目录价
            discount = random.uniform(0.10, 0.30) if contract_type != "Consignment" else 0.0
            contracted = round(list_price * (1 - discount), 2)
            records.append({
                "id": rec_id,
                "product_id": product_id,
                "manufacturer_id": product_manufacturer_map[product_id],
                "effective_date": start,
                "end_date": end,
                "list_price_usd": list_price,
                "contracted_price_usd": contracted,
                "contract_type": contract_type,
            })
            rec_id += 1
            # 每次续约价格小幅上涨
            list_price = round(list_price * random.uniform(1.00, 1.08), 2)

    return pl.DataFrame(records)


def gen_implant_lots(product_ids: list[int], n: int = 400) -> pl.DataFrame:
    """制造批次. quality_test_passed 不存在这里, 它在 quality_test_event 表里.
    制造窗口刻意拉宽 ([-5 年, -2 个月]), 这样有些 lot 已经过期 (使 Expired 库存状态成立),
    另一些则即将过期 (使 Q5 '90 天内过期' 能查到行)."""
    records = []
    sterilization_methods = ["Gamma Radiation", "Ethylene Oxide (EtO)", "Electron Beam"]
    for i in range(1, n + 1):
        manufacture_date = dt_between(NOW - timedelta(days=5 * 365), NOW - timedelta(days=60))
        expiration_date = manufacture_date + timedelta(days=random.randint(1095, 2190))
        records.append({
            "id": i,
            "product_id": random.choice(product_ids),
            "lot_number": fake.unique.bothify(text="LOT????####"),
            "expiration_date": expiration_date,
            "manufacture_date": manufacture_date,
            "quantity_manufactured": random.randint(50, 500),
            "sterilization_method": random.choice(sterilization_methods),
        })
    return pl.DataFrame(records)


def gen_quality_test_events(lots_df: pl.DataFrame) -> pl.DataFrame:
    """Append-only 的 QC 事件. 每个 lot 有 1 到 3 条事件: Incoming Inspection,
    可选的 Mechanical Load, 可选的 Sterility. 第一条永远是 Incoming Inspection,
    结果分布遵循 92% Pass / 5% Conditional / 3% Fail."""
    records = []
    rec_id = 1
    test_types = ["Incoming Inspection", "Mechanical Load", "Sterility", "Visual"]
    results = ["Pass", "Conditional", "Fail"]
    result_weights = [0.92, 0.05, 0.03]

    for lot in lots_df.iter_rows(named=True):
        n_events = random.randint(1, 3)
        manufacture_date = lot["manufacture_date"]
        # 第一条事件必须是 Incoming Inspection
        event_date = dt_between(manufacture_date + timedelta(hours=1),
                                manufacture_date + timedelta(days=14))
        chosen_types = ["Incoming Inspection"]
        for _ in range(n_events - 1):
            chosen_types.append(random.choice(test_types[1:]))

        for test_type in chosen_types:
            # 一旦时间线推进到 NOW, 就停止为这个 lot 生成后续事件;
            # 这样可以避免多条事件挤在同一个 NOW 时间戳上.
            if event_date > NOW:
                break
            result = weighted_choice(results, result_weights)
            records.append({
                "id": rec_id,
                "lot_id": lot["id"],
                "test_date": event_date,
                "test_type": test_type,
                "result": result,
                "tester": fake.name(),
                "notes": fake.sentence() if random.random() > 0.5 else None,
            })
            rec_id += 1
            event_date = event_date + timedelta(days=random.randint(1, 10))
    return pl.DataFrame(records)


HIGH_COST_CATEGORY_IDS = {4, 5, 6, 7}  # 髋, 膝, 脊柱, 肩
LOW_COST_CATEGORY_IDS = {1, 2, 3, 8}   # 骨板, 骨钉, 髓内钉, 外固定架


def gen_purchase_orders(
    hospital_ids: list[int],
    manufacturer_categories: dict[int, list[int]],
    n: int = 300,
) -> pl.DataFrame:
    """医院 → 制造商的采购订单 (PO). is_consignment 受该制造商的品类结构影响:
    针对那些产品线以高价值品类 (髋, 膝, 脊柱, 肩) 为主的制造商, PO 约 60% 是寄售;
    以低价值品类为主的制造商约 20% 是寄售."""
    records = []
    statuses = ["Open", "Delivered", "Cancelled"]
    status_weights = [0.10, 0.85, 0.05]

    for i in range(1, n + 1):
        order_date = dt_between(NOW - timedelta(days=2 * 365), NOW - timedelta(days=14))
        expected_delivery = order_date + timedelta(days=random.randint(7, 45))
        status = weighted_choice(statuses, status_weights)
        if status == "Delivered":
            actual_delivery = expected_delivery + timedelta(days=random.randint(-3, 14))
            actual_delivery = min(actual_delivery, NOW)
        else:
            actual_delivery = None

        # 选制造商; 再用它的主导品类去偏置 is_consignment
        mfr_id = random.choice(list(manufacturer_categories.keys()))
        mfr_categories = manufacturer_categories[mfr_id]
        high_cost_share = sum(
            1 for c in mfr_categories if c in HIGH_COST_CATEGORY_IDS
        ) / max(1, len(mfr_categories))
        # 在 0.20 (全低价) 和 0.60 (全高价) 之间线性插值得到寄售概率
        consignment_p = 0.20 + 0.40 * high_cost_share
        is_consignment = random.random() < consignment_p

        records.append({
            "id": i,
            "hospital_id": random.choice(hospital_ids),
            "manufacturer_id": mfr_id,
            "po_number": f"PO-{order_date.year}-{fake.unique.random_int(min=10000, max=999999)}",
            "order_date": order_date,
            "expected_delivery_date": expected_delivery,
            "actual_delivery_date": actual_delivery,
            "status": status,
            "is_consignment": is_consignment,
            # 粗略估算; 不约束为 Σ(单价). 见 ER 文档第 8 节 已知限制.
            "total_amount_usd": round(random.uniform(5000, 250000), 2),
        })
    return pl.DataFrame(records)


# ============================================================================
# 生成器 - 供应链 (先建原始事件, 再派生 silver 当前态)
# ----------------------------------------------------------------------------
# 重要: 库存生命周期采用两阶段 (TWO-PHASE) 生成模式.
#   Phase A - gen_initial_inventory_with_received:
#       每个单元都先以 Available 状态创建, 只带一条 Received movement.
#   Phase B - finalize_inventory_lifecycle (在 surgery_implant 和 recall
#   生成之后才调用):
#       对每个单元:
#         - 如果被某台手术用掉, 在 implantation_timestamp 处追加一条 Used movement,
#           status="Used", location=NULL.
#         - 否则, 按资格在 {Available, Expired, Recalled, Quarantined} 里采样一个
#           (Expired 要求已过有效期; Recalled 要求 lot 或 product 落在某条召回的 scope 内).
#         - 在 Received 与终态事件之间追加 0 到 2 条 Transferred movement,
#           且要落在可用的时间窗内.
#       inventory 上的 silver 当前态列 (status, location, last_updated) 随后从
#       最新一条 movement 派生, 这样它们不会与原始事件日志漂移.
# ============================================================================

STORAGE_LOCATIONS = [
    "OR Storage A", "OR Storage B", "Central Supply",
    "Sterile Processing", "Emergency OR",
]


def gen_initial_inventory_with_received(
    lots_df: pl.DataFrame,
    products_df: pl.DataFrame,
    purchase_orders_df: pl.DataFrame,
    n_inventory: int = 2500,
) -> tuple[pl.DataFrame, list[dict]]:
    """Phase A: 每个单元一开始都是 Available, 只带一条 Received movement.
    返回 (inventory_df, movements_records), 其中 movements 是一个 dict 列表,
    会在 Phase B 里继续往里追加."""
    delivered_pos_list = purchase_orders_df.filter(
        pl.col("status") == "Delivered"
    ).to_dicts()
    lots_dict = {row["id"]: row for row in lots_df.iter_rows(named=True)}
    products_dict = {row["id"]: row for row in products_df.iter_rows(named=True)}

    inv_records: list[dict] = []
    mov_records: list[dict] = []
    serial_pool: set[str] = set()

    for i in range(1, n_inventory + 1):
        po = random.choice(delivered_pos_list)
        lot_id = random.choice(list(lots_dict.keys()))
        lot = lots_dict[lot_id]
        product = products_dict[lot["product_id"]]

        floor_date = max(lot["manufacture_date"], po["actual_delivery_date"])
        if floor_date >= NOW:
            received_date = floor_date
        else:
            received_date = dt_between(floor_date, NOW)

        while True:
            sn = "SN" + fake.bothify(text="????##########")
            if sn not in serial_pool:
                serial_pool.add(sn)
                break

        udi_pi = f"(01){product['udi_di']}(10){lot['lot_number']}(21){sn}"
        initial_location = random.choice(STORAGE_LOCATIONS)

        inv_records.append({
            "id": i,
            "hospital_id": po["hospital_id"],
            "lot_id": lot_id,
            "purchase_order_id": po["id"],
            "serial_number": sn,
            "udi_pi": udi_pi,
            "received_date": received_date,
            "is_consignment": po["is_consignment"],
            # silver 当前态占位; 在 Phase B 里从最新 movement 最终确定.
            "status": "Available",
            "location": initial_location,
            "last_updated": received_date,
        })

        mov_records.append({
            "inventory_id": i,
            "movement_date": received_date,
            "movement_type": "Received",
            "from_location": "Vendor",
            "to_location": initial_location,
            "performed_by": fake.name(),
            "notes": "Initial intake from vendor",
        })

    return pl.DataFrame(inv_records), mov_records


def finalize_inventory_lifecycle(
    inventory_df: pl.DataFrame,
    movements: list[dict],
    surgery_implants_df: pl.DataFrame,
    lots_df: pl.DataFrame,
    recalls_df: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Phase B: 通过往原始日志里追加 movement, 给单元赋予
    Used/Expired/Recalled/Quarantined 状态, 再从最后一条 movement 派生 silver 当前态列.

    概率分档 (针对没有被 surgery_implant 消耗掉的单元):
        4% Quarantined
        3% Expired   (仅当 expiration_date < NOW)
        3% Recalled  (仅当 lot 或 product 落在某条活动召回的 scope 内)
        90% 保持 Available
    """
    si_by_inventory = {
        row["inventory_id"]: row for row in surgery_implants_df.iter_rows(named=True)
    }
    lots_lookup = {row["id"]: row for row in lots_df.iter_rows(named=True)}
    lot_to_product = {row["id"]: row["product_id"] for row in lots_df.iter_rows(named=True)}

    # 召回作用域索引
    recalled_lots: dict[int, datetime] = {}
    recalled_products: dict[int, datetime] = {}
    for r in recalls_df.iter_rows(named=True):
        if r["lot_id"] is not None:
            recalled_lots[r["lot_id"]] = r["recall_date"]
        else:
            recalled_products[r["product_id"]] = r["recall_date"]

    # 每个 inventory 的 movement 时间线
    per_inv: dict[int, list[dict]] = {}
    for m in movements:
        per_inv.setdefault(m["inventory_id"], []).append(m)

    finalized_inventory: list[dict] = []

    for inv in inventory_df.iter_rows(named=True):
        inv_id = inv["id"]
        unit_movements = per_inv[inv_id]
        current_location = unit_movements[-1]["to_location"]
        cur_date = unit_movements[-1]["movement_date"]

        si = si_by_inventory.get(inv_id)
        target_terminal_date: datetime | None = (
            si["implantation_timestamp"] if si else None
        )

        # 在 Received 与任何终态事件之间, 可选地加 0 到 2 条 Transferred movement
        n_transfers = random.randint(0, 2)
        for _ in range(n_transfers):
            transfer_window_end = target_terminal_date or NOW
            if cur_date + timedelta(days=1) >= transfer_window_end:
                break
            next_date = cur_date + timedelta(days=random.randint(1, 14))
            if next_date >= transfer_window_end:
                break
            next_location = random.choice(
                [loc for loc in STORAGE_LOCATIONS if loc != current_location]
            )
            unit_movements.append({
                "inventory_id": inv_id,
                "movement_date": next_date,
                "movement_type": "Transferred",
                "from_location": current_location,
                "to_location": next_location,
                "performed_by": fake.name(),
                "notes": None,
            })
            cur_date = next_date
            current_location = next_location

        # 决定终态状态
        final_status = "Available"
        final_location = current_location
        final_last_updated = cur_date

        if si:
            # 这个单元被手术消耗掉了
            implant_time = si["implantation_timestamp"]
            unit_movements.append({
                "inventory_id": inv_id,
                "movement_date": implant_time,
                "movement_type": "Used",
                "from_location": current_location,
                "to_location": None,
                "performed_by": fake.name(),
                "notes": "Unit implanted in surgery",
            })
            final_status = "Used"
            final_location = None
            final_last_updated = implant_time
        else:
            # 非 Used 的资格检查
            lot_id = inv["lot_id"]
            product_id = lot_to_product[lot_id]
            lot_row = lots_lookup[lot_id]
            past_expiration = lot_row["expiration_date"] < NOW
            in_lot_recall = lot_id in recalled_lots
            in_product_recall = product_id in recalled_products
            in_recall_scope = in_lot_recall or in_product_recall

            roll = random.random()
            terminal_type: str | None = None
            terminal_date: datetime | None = None

            # 用嵌套 if (而不是链式 elif), 保证每一档的概率精确:
            #   [0.00, 0.04) → Quarantined (总是)
            #   [0.04, 0.07) → 符合条件则 Expired, 否则保持 Available
            #   [0.07, 0.10) → 符合条件则 Recalled, 否则保持 Available
            #   [0.10, 1.00) → 保持 Available
            # 之前链式 elif 的版本, 会让 roll ∈ [0.04, 0.07) 在 past_expiration 为 False 时
            # 漏到 Recalled 分支, 把召回 scope 内单元的 Recalled 概率从 3% 抬高到最多 6%.
            if roll < 0.04:
                terminal_type = "Quarantined"
                terminal_date = min(
                    cur_date + timedelta(days=random.randint(1, 30)), NOW
                )
            elif roll < 0.07:
                if past_expiration:
                    terminal_type = "Expired"
                    terminal_date = min(
                        max(lot_row["expiration_date"], cur_date + timedelta(hours=1)),
                        NOW,
                    )
            elif roll < 0.10:
                if in_recall_scope:
                    rd = (
                        recalled_lots[lot_id]
                        if in_lot_recall
                        else recalled_products[product_id]
                    )
                    terminal_type = "Recalled"
                    terminal_date = min(
                        max(rd, cur_date) + timedelta(days=random.randint(1, 14)), NOW
                    )

            if terminal_type is not None and terminal_date is not None:
                unit_movements.append({
                    "inventory_id": inv_id,
                    "movement_date": terminal_date,
                    "movement_type": terminal_type,
                    "from_location": current_location,
                    "to_location": None,
                    "performed_by": fake.name(),
                    "notes": f"Unit marked {terminal_type}",
                })
                final_status = terminal_type
                final_location = None
                final_last_updated = terminal_date

        finalized_inventory.append({
            **inv,
            "status": final_status,
            "location": final_location,
            "last_updated": final_last_updated,
        })

    # 构建最终的 movement DataFrame, 每个 inventory_id 内带 sequence_no
    all_movement_rows: list[dict] = []
    mov_id = 1
    for inv_id, events in per_inv.items():
        for seq, e in enumerate(events, start=1):
            all_movement_rows.append({
                "id": mov_id,
                "inventory_id": inv_id,
                "sequence_no": seq,
                "movement_type": e["movement_type"],
                "movement_date": e["movement_date"],
                "from_location": e["from_location"],
                "to_location": e["to_location"],
                "performed_by": e["performed_by"],
                "notes": e["notes"],
            })
            mov_id += 1
    # 按 id 排序 movement, 保证输出稳定
    all_movement_rows.sort(key=lambda r: r["id"])

    return pl.DataFrame(finalized_inventory), pl.DataFrame(all_movement_rows)


# ============================================================================
# 生成器 - 临床
# ============================================================================
def gen_surgeries(
    patient_ids: list[int],
    surgeon_ids: list[int],
    hospital_ids: list[int],
    inventory_df: pl.DataFrame,
    n: int = 800,
) -> pl.DataFrame:
    """手术. surgery_date 采样在一个 "至少有一件库存单元已到货" 的时间窗内,
    所以时间序规则 (surgery_date ≥ received_date) 成立.
    翻修手术 (约 8%) 会链接到同一患者更早的一台手术."""
    records = []
    procedures = [
        ("27236", "Fracture femur, proximal end, neck, open treatment",
         "S72.001A", "Fracture of unspecified part of neck of right femur"),
        ("27245", "Treatment of greater trochanteric fracture with plate/screws",
         "S72.111A", "Displaced fracture of greater trochanter of right femur"),
        ("27447", "Total knee arthroplasty",
         "M17.11", "Unilateral primary osteoarthritis, right knee"),
        ("27130", "Total hip arthroplasty",
         "M16.11", "Unilateral primary osteoarthritis, right hip"),
        ("22612", "Lumbar spinal fusion",
         "M51.36", "Other intervertebral disc degeneration, lumbar region"),
        ("23472", "Total shoulder arthroplasty",
         "M19.011", "Primary osteoarthritis, right shoulder"),
        ("27758", "Open treatment of tibial shaft fracture",
         "S82.221A", "Displaced transverse fracture of shaft of right tibia"),
    ]
    anesthesia_types = ["General", "Spinal", "Regional Block"]

    # 最早收货日期: 手术只能发生在至少有一件单元上架之后
    earliest_received = inventory_df["received_date"].min()
    surgery_start = max(earliest_received, NOW - timedelta(days=2 * 365))

    # 按患者分桶, 支撑翻修链接
    patient_to_prior_surgeries: dict[int, list[tuple[int, datetime]]] = {}

    for i in range(1, n + 1):
        patient_id = random.choice(patient_ids)
        # 约 8% 是同一患者更早一台手术的翻修
        revision_of = None
        prior = patient_to_prior_surgeries.get(patient_id, [])
        if prior and random.random() < 0.08:
            revision_of = random.choice(prior)[0]
            # 手术日期必须晚于上一次手术
            prior_date = next(d for pid, d in prior if pid == revision_of)
            surgery_date = dt_between(prior_date + timedelta(days=180), NOW)
        else:
            surgery_date = dt_between(surgery_start, NOW)

        proc = random.choice(procedures)
        primary_surgeon_id = random.choice(surgeon_ids)
        duration = random.randint(60, 360)

        records.append({
            "id": i,
            "patient_id": patient_id,
            "surgeon_id": primary_surgeon_id,
            "hospital_id": random.choice(hospital_ids),
            "revision_of_surgery_id": revision_of,
            "surgery_date": surgery_date,
            "procedure_code": proc[0],
            "procedure_name": proc[1],
            "diagnosis_code": proc[2],
            "diagnosis_description": proc[3],
            "surgery_type": weighted_choice(["Elective", "Emergency"], [0.80, 0.20]),
            "duration_minutes": duration,
            "anesthesia_type": random.choice(anesthesia_types),
            "asa_score": weighted_choice([1, 2, 3, 4, 5], [0.15, 0.40, 0.30, 0.12, 0.03]),
            "notes": fake.sentence() if random.random() > 0.5 else None,
        })

        patient_to_prior_surgeries.setdefault(patient_id, []).append((i, surgery_date))

    return pl.DataFrame(records)


def gen_surgery_implants(
    surgeries_df: pl.DataFrame,
    inventory_df: pl.DataFrame,
    surgeon_ids: list[int],
) -> pl.DataFrame:
    """关联表: 哪个 inventory 单元在哪台手术里被植入, 何时植入.
    约束:
      * 每行的 inventory_id 唯一 (每个单元只用一次)
      * implantation_timestamp ∈ [surgery_date, surgery_date + duration_minutes]
      * 单元的 received_date ≤ surgery_date
      * implanted_by_surgeon_id 有 80% 是主刀, 其余是另一位医生
    """
    implant_sites = [
        "Right Femur", "Left Femur", "Right Tibia", "Left Tibia",
        "Right Hip", "Left Hip", "Right Knee", "Left Knee",
        "Lumbar Spine L4-L5", "Lumbar Spine L5-S1",
        "Right Shoulder", "Left Shoulder",
    ]

    # 按 hospital_id 给库存建索引, 便于廉价地过滤可用单元, 并按 received_date 排序
    available_units = inventory_df.filter(pl.col("status") == "Available").to_dicts()
    # 允许这个生成器产出 'Used' 状态, inventory 的 status 之后会被覆盖.
    # 但对 SurgeryImplant 来说, 我们需要一个在 surgery_date 当下可用的单元.
    # 按医院预先建索引以提速.
    from collections import defaultdict
    by_hospital: dict[int, list[dict]] = defaultdict(list)
    for u in available_units:
        by_hospital[u["hospital_id"]].append(u)

    used_ids: set[int] = set()
    records: list[dict] = []
    rec_id = 1

    # 按日期给手术排序, 让更早的手术先挑 (更贴近真实)
    sorted_surgeries = sorted(surgeries_df.to_dicts(), key=lambda s: s["surgery_date"])

    for surgery in sorted_surgeries:
        hospital_id = surgery["hospital_id"]
        primary_surgeon = surgery["surgeon_id"]
        surgery_date = surgery["surgery_date"]
        end_date = surgery_date + timedelta(minutes=surgery["duration_minutes"])

        # 候选: 同一医院, 尚未被用, 且在 surgery_date 之前已收货
        candidates = [
            u for u in by_hospital[hospital_id]
            if u["id"] not in used_ids and u["received_date"] <= surgery_date
        ]
        if not candidates:
            continue

        # 每台手术用 1 到 5 件植入物
        n_implants = min(random.randint(1, 5), len(candidates))
        picks = random.sample(candidates, n_implants)
        for unit in picks:
            used_ids.add(unit["id"])
            implant_time = dt_between(surgery_date, end_date)
            # 植入医生: 80% 与主刀相同, 20% 不同
            if random.random() < 0.80:
                implanting_surgeon = primary_surgeon
            else:
                other = [s for s in surgeon_ids if s != primary_surgeon]
                implanting_surgeon = random.choice(other) if other else primary_surgeon

            records.append({
                "id": rec_id,
                "surgery_id": surgery["id"],
                "inventory_id": unit["id"],
                "implant_site": random.choice(implant_sites),
                "implantation_timestamp": implant_time,
                "implanted_by_surgeon_id": implanting_surgeon,
            })
            rec_id += 1

    return pl.DataFrame(records)


def gen_adverse_events(surgery_implants_df: pl.DataFrame, target_n: int = 80) -> pl.DataFrame:
    """不良事件, 大约发生在 10% 的手术上 (为简化, 按 surgery_implant 建模).
    event_date 严格晚于该植入物的 implantation_timestamp."""
    records = []
    event_types = [
        "Surgical Site Infection", "Device Loosening", "Device Fracture/Breakage",
        "Allergic Reaction", "Implant Rejection", "Chronic Pain", "Nerve Damage",
        "Deep Vein Thrombosis", "Dislocation",
    ]
    severities = ["Minor", "Moderate", "Severe", "Life-threatening"]
    severity_weights = [0.70, 0.20, 0.08, 0.02]
    outcomes = [
        "Recovered with treatment", "Ongoing monitoring", "Revision surgery required",
        "Implant removed", "Permanent disability", "Hospitalization required",
    ]

    pool = surgery_implants_df.sample(
        n=min(target_n, len(surgery_implants_df)), seed=RANDOM_SEED
    ).to_dicts()

    for i, si in enumerate(pool, start=1):
        impl_time = si["implantation_timestamp"]
        latest = NOW
        if impl_time >= latest:
            continue
        event_date = dt_between(impl_time + timedelta(hours=12), latest)
        reported_date = event_date + timedelta(days=random.randint(0, 30))
        reported_date = min(reported_date, NOW)
        records.append({
            "id": i,
            "surgery_implant_id": si["id"],
            "event_date": event_date,
            "event_type": random.choice(event_types),
            "severity": weighted_choice(severities, severity_weights),
            "description": fake.paragraph(nb_sentences=3),
            "reported_by": f"Dr. {fake.last_name()}",
            "reported_date": reported_date,
            "fda_mdr_number": (
                f"MDR{random.randint(1000000, 9999999)}" if random.random() > 0.4 else None
            ),
            "patient_outcome": random.choice(outcomes),
            "corrective_action": fake.sentence() if random.random() > 0.3 else None,
        })
    return pl.DataFrame(records)


def gen_patient_followup_visits(
    surgery_implants_df: pl.DataFrame, n: int = 1500
) -> pl.DataFrame:
    """纵向随访. 随访日期严格晚于植入.
    标准节奏: 6 周, 6 个月, 1 年, 之后转为常规随访. 症状性随访穿插其间."""
    records = []
    visit_types_routine = ["6-Week", "6-Month", "1-Year", "Routine"]
    visit_types_symptomatic = ["Symptomatic"]
    functional_scores = ["Excellent", "Good", "Fair", "Poor"]
    score_weights = [0.40, 0.40, 0.15, 0.05]

    # 为每个 surgery_implant 生成 0 到 4 次随访; 总数截断到 n
    si_list = surgery_implants_df.to_dicts()
    random.shuffle(si_list)
    rec_id = 1
    for si in si_list:
        if rec_id > n:
            break
        impl_time = si["implantation_timestamp"]
        if impl_time >= NOW:
            continue
        # 70% 有常规随访; 30% 还没有录入随访
        if random.random() > 0.30:
            cadence_offsets_days = [42, 180, 365]
            for offset in cadence_offsets_days:
                if rec_id > n:
                    break
                visit_date = impl_time + timedelta(days=offset + random.randint(-7, 7))
                if visit_date >= NOW:
                    break
                records.append({
                    "id": rec_id,
                    "patient_id": si.get("_patient_id"),  # 在下面填充
                    "surgery_implant_id": si["id"],
                    "visit_date": visit_date,
                    "visit_type": random.choice(visit_types_routine),
                    "functional_score": weighted_choice(functional_scores, score_weights),
                    "revision_indicated": weighted_choice([False, True], [0.92, 0.08]),
                    "clinician_notes": fake.sentence() if random.random() > 0.4 else None,
                    "clinician_name": f"Dr. {fake.last_name()}",
                })
                rec_id += 1
        # 15% 概率额外有一次症状性随访
        if random.random() < 0.15 and rec_id <= n:
            visit_date = impl_time + timedelta(days=random.randint(30, 540))
            if visit_date < NOW:
                records.append({
                    "id": rec_id,
                    "patient_id": si.get("_patient_id"),
                    "surgery_implant_id": si["id"],
                    "visit_date": visit_date,
                    "visit_type": random.choice(visit_types_symptomatic),
                    "functional_score": weighted_choice(functional_scores, [0.20, 0.30, 0.30, 0.20]),
                    "revision_indicated": weighted_choice([False, True], [0.75, 0.25]),
                    "clinician_notes": fake.sentence(),
                    "clinician_name": f"Dr. {fake.last_name()}",
                })
                rec_id += 1

    return pl.DataFrame(records)


# ============================================================================
# 生成器 - 监管 / 风控
# ============================================================================
def gen_recalls(product_ids: list[int], lots_df: pl.DataFrame, n: int = 12) -> pl.DataFrame:
    """召回. status 与 completion_date 保持自洽.
    约 70% 是 lot 级 (被召回产品的随机一批); 约 30% 是全产品级."""
    records = []
    recall_classes = ["Class I", "Class II", "Class III"]
    class_weights = [0.10, 0.60, 0.30]
    statuses = ["Active", "Completed", "Terminated"]
    status_weights = [0.40, 0.50, 0.10]

    # 按产品给 lot 建索引, 这样全产品级和 lot 级召回都说得通
    from collections import defaultdict
    lots_by_product: dict[int, list[int]] = defaultdict(list)
    for row in lots_df.iter_rows(named=True):
        lots_by_product[row["product_id"]].append(row["id"])

    # 挑选要被召回的不同产品 (最多占产品的 5%)
    eligible_products = [p for p in product_ids if p in lots_by_product]
    chosen_products = random.sample(eligible_products, min(n, len(eligible_products)))

    for i, product_id in enumerate(chosen_products, start=1):
        recall_date = dt_between(NOW - timedelta(days=2 * 365), NOW - timedelta(days=30))
        status = weighted_choice(statuses, status_weights)
        if status in ("Completed", "Terminated"):
            completion_date = recall_date + timedelta(days=random.randint(30, 365))
            completion_date = min(completion_date, NOW)
        else:
            completion_date = None

        # lot 级还是全产品级
        if random.random() > 0.30:
            lot_id = random.choice(lots_by_product[product_id])
        else:
            lot_id = None

        records.append({
            "id": i,
            "product_id": product_id,
            "lot_id": lot_id,
            "recall_number": f"Z-{random.randint(1000, 9999)}-{recall_date.year}",
            "recall_date": recall_date,
            "recall_reason": random.choice([
                "Sterility concerns due to packaging defect",
                "Device may fracture prematurely under load",
                "Labeling error - incorrect size specification",
                "Manufacturing deviation affecting device strength",
                "Potential for screw head detachment",
            ]),
            "recall_class": weighted_choice(recall_classes, class_weights),
            "fda_enforcement_report": f"FDA-{recall_date.year}-{random.randint(1000, 9999)}",
            "status": status,
            "completion_date": completion_date,
        })
    return pl.DataFrame(records)


def gen_recall_notifications(
    recalls_df: pl.DataFrame,
    surgery_implants_df: pl.DataFrame,
    inventory_df: pl.DataFrame,
    lots_df: pl.DataFrame,
) -> pl.DataFrame:
    """每条召回所影响的每个已植入单元, 对应一条通知.
    作用域规则: 一个单元被影响, 当 (召回是 lot 级 且 inventory.lot_id == recall.lot_id)
                或 (召回是全产品级 且 inventory 对应的 product == recall.product_id)."""
    records = []
    rec_id = 1
    notification_methods = ["Email", "Phone", "Mail", "Patient Portal"]
    notified_parties = ["Patient", "Hospital", "Surgeon"]

    # 借助 lot 构建 inventory_id → product_id 的映射
    lot_product = {row["id"]: row["product_id"] for row in lots_df.iter_rows(named=True)}
    inv_lot = {row["id"]: row["lot_id"] for row in inventory_df.iter_rows(named=True)}
    inv_product = {iid: lot_product[lot_id] for iid, lot_id in inv_lot.items()}

    si_list = surgery_implants_df.to_dicts()

    for recall in recalls_df.iter_rows(named=True):
        # 过滤出受影响的植入物
        if recall["lot_id"] is not None:
            affected = [si for si in si_list if inv_lot[si["inventory_id"]] == recall["lot_id"]]
        else:
            affected = [si for si in si_list if inv_product[si["inventory_id"]] == recall["product_id"]]

        # 通知严格晚于召回日期
        for si in affected:
            # 每个单元扇出 1 到 3 条通知 (患者 + 医院 + 医生)
            n_notifs = random.randint(1, 3)
            parties = random.sample(notified_parties, n_notifs)
            for party in parties:
                # 各方 SLA: Class I 1-3 天, Class II 5-30 天, Class III 15-60 天
                if recall["recall_class"] == "Class I":
                    delay = random.randint(1, 5)
                elif recall["recall_class"] == "Class II":
                    delay = random.randint(3, 30)
                else:
                    delay = random.randint(7, 60)
                notif_date = recall["recall_date"] + timedelta(days=delay)
                notif_date = min(notif_date, NOW)
                # 约 70% 已确认
                if random.random() > 0.30:
                    ack_date = notif_date + timedelta(days=random.randint(1, 30))
                    ack_date = min(ack_date, NOW)
                else:
                    ack_date = None
                records.append({
                    "id": rec_id,
                    "recall_id": recall["id"],
                    "surgery_implant_id": si["id"],
                    "notification_date": notif_date,
                    "notification_method": random.choice(notification_methods),
                    "notified_party": party,
                    "acknowledgment_date": ack_date,
                    "action_taken": random.choice([
                        None, "Patient contacted", "Follow-up scheduled",
                        "Device inspected", "Revision surgery planned",
                    ]),
                })
                rec_id += 1

    return pl.DataFrame(records)


# ============================================================================
# 生成器 - 审计日志 (真实 ID 引用)
# ============================================================================
def _audit_payload(table_name: str, action: str) -> tuple[str | None, str | None]:
    """为每张表返回合适的 (old_values, new_values) JSON 字符串.
    INSERT 没有 old_values; DELETE 没有 new_values."""
    field_options: dict[str, tuple[str, list]] = {
        "inventory": ("status", ["Available", "Used", "Expired", "Recalled", "Quarantined"]),
        "surgery": ("duration_minutes", list(range(60, 360, 30))),
        "surgery_implant": ("implant_site", [
            "Right Femur", "Left Femur", "Right Hip", "Left Hip",
            "Right Knee", "Left Knee", "Lumbar Spine L4-L5", "Lumbar Spine L5-S1",
        ]),
        "adverse_event": ("severity", ["Minor", "Moderate", "Severe", "Life-threatening"]),
        "recall": ("status", ["Active", "Completed", "Terminated"]),
    }
    field, values = field_options[table_name]
    if action == "INSERT":
        return None, json.dumps({field: random.choice(values)})
    if action == "DELETE":
        return json.dumps({field: random.choice(values)}), None
    # UPDATE 的情况
    old_v, new_v = random.sample(values, 2) if len(values) >= 2 else (values[0], values[0])
    return json.dumps({field: old_v}), json.dumps({field: new_v})


def gen_audit_log(
    inventory_df: pl.DataFrame,
    surgery_df: pl.DataFrame,
    surgery_implants_df: pl.DataFrame,
    adverse_events_df: pl.DataFrame,
    recalls_df: pl.DataFrame,
    n: int = 800,
) -> pl.DataFrame:
    """审计日志, (table, id) 引用都是真实的, 且 change_timestamp 锚定到被引用行的
    最早有意义日期, 这样审计时间线绝不会出现 '审计了一条尚不存在的记录'.
    各表的锚点:
        inventory.received_date
        surgery.surgery_date
        surgery_implant.implantation_timestamp
        adverse_event.event_date
        recall.recall_date
    JSON payload 字段与所属表匹配 (见 _audit_payload)."""
    # 构建各表的锚点映射: id -> anchor_date
    anchors: dict[str, dict[int, datetime]] = {
        "inventory": {row["id"]: row["received_date"] for row in inventory_df.iter_rows(named=True)},
        "surgery": {row["id"]: row["surgery_date"] for row in surgery_df.iter_rows(named=True)},
        "surgery_implant": {
            row["id"]: row["implantation_timestamp"]
            for row in surgery_implants_df.iter_rows(named=True)
        },
        "adverse_event": {
            row["id"]: row["event_date"]
            for row in adverse_events_df.iter_rows(named=True)
        } if len(adverse_events_df) > 0 else {},
        "recall": {row["id"]: row["recall_date"] for row in recalls_df.iter_rows(named=True)},
    }
    table_pools = {t: list(ids.keys()) for t, ids in anchors.items() if ids}
    actions = ["INSERT", "UPDATE", "DELETE"]
    action_weights = [0.55, 0.42, 0.03]

    records = []
    for i in range(1, n + 1):
        table_name = random.choice(list(table_pools.keys()))
        action = weighted_choice(actions, action_weights)
        record_id = random.choice(table_pools[table_name])
        # 把 change_timestamp 锚定到 [anchor_date, NOW]
        anchor = anchors[table_name][record_id]
        change_ts = dt_between(anchor, NOW) if anchor < NOW else anchor
        old_vals, new_vals = _audit_payload(table_name, action)
        records.append({
            "id": i,
            "table_name": table_name,
            "record_id": record_id,
            "action": action,
            "changed_by": fake.name(),
            "change_timestamp": change_ts,
            "old_values": old_vals,
            "new_values": new_vals,
            "reason": random.choice([
                None, "Inventory audit correction", "Status update",
                "Data entry error", "System migration",
            ]),
        })
    return pl.DataFrame(records)


# ============================================================================
# 流水线
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有 TSV 文件. 幂等: 先删除已有的 TSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating data...")

    # 01 - implant_category (无依赖)
    df_categories = gen_implant_categories()
    df_categories.write_csv(DATA_DIR / "01_implant_category.tsv", separator="\t")
    print(f"  ✓ implant_category: {len(df_categories)} rows")

    # 02 - manufacturer
    df_manufacturers = gen_manufacturers(15)
    df_manufacturers.write_csv(DATA_DIR / "02_manufacturer.tsv", separator="\t")
    print(f"  ✓ manufacturer: {len(df_manufacturers)} rows")

    # 03 - hospital
    df_hospitals = gen_hospitals(12)
    df_hospitals.write_csv(DATA_DIR / "03_hospital.tsv", separator="\t")
    print(f"  ✓ hospital: {len(df_hospitals)} rows")

    # 04 - surgeon
    df_surgeons = gen_surgeons(100)
    df_surgeons.write_csv(DATA_DIR / "04_surgeon.tsv", separator="\t")
    print(f"  ✓ surgeon: {len(df_surgeons)} rows")

    # 05 - patient
    df_patients = gen_patients(500)
    df_patients.write_csv(DATA_DIR / "05_patient.tsv", separator="\t")
    print(f"  ✓ patient: {len(df_patients)} rows")

    # 06 - implant_product (依赖 category, manufacturer)
    df_products = gen_implant_products(
        df_categories["id"].to_list(),
        df_manufacturers["id"].to_list(),
        200,
    )
    df_products.write_csv(DATA_DIR / "06_implant_product.tsv", separator="\t")
    print(f"  ✓ implant_product: {len(df_products)} rows")

    # 07 - regulatory_submission (依赖 product)
    df_submissions = gen_regulatory_submissions(df_products["id"].to_list(), 250)
    df_submissions.write_csv(DATA_DIR / "07_regulatory_submission.tsv", separator="\t")
    print(f"  ✓ regulatory_submission: {len(df_submissions)} rows")

    # 08 - pricing_history (依赖 product, manufacturer)
    product_manufacturer_map = {
        row["id"]: row["manufacturer_id"] for row in df_products.iter_rows(named=True)
    }
    df_pricing = gen_pricing_history(df_products["id"].to_list(), product_manufacturer_map, 500)
    df_pricing.write_csv(DATA_DIR / "08_pricing_history.tsv", separator="\t")
    print(f"  ✓ pricing_history: {len(df_pricing)} rows")

    # 09 - implant_lot (依赖 product)
    df_lots = gen_implant_lots(df_products["id"].to_list(), 400)
    df_lots.write_csv(DATA_DIR / "09_implant_lot.tsv", separator="\t")
    print(f"  ✓ implant_lot: {len(df_lots)} rows")

    # 10 - quality_test_event (依赖 lot) - RAW 层
    df_qc = gen_quality_test_events(df_lots)
    df_qc.write_csv(DATA_DIR / "10_quality_test_event.tsv", separator="\t")
    print(f"  ✓ quality_test_event: {len(df_qc)} rows")

    # 11 - purchase_order (依赖 hospital, manufacturer; 寄售比例按品类偏置)
    manufacturer_categories: dict[int, list[int]] = {}
    for row in df_products.iter_rows(named=True):
        manufacturer_categories.setdefault(row["manufacturer_id"], []).append(row["category_id"])
    df_pos = gen_purchase_orders(
        df_hospitals["id"].to_list(),
        manufacturer_categories,
        300,
    )
    df_pos.write_csv(DATA_DIR / "11_purchase_order.tsv", separator="\t")
    print(f"  ✓ purchase_order: {len(df_pos)} rows")

    # 12 - recall (排在 inventory 之前, 这样 Phase B 能正确圈定 Recalled 状态)
    df_recalls = gen_recalls(df_products["id"].to_list(), df_lots, 12)
    df_recalls.write_csv(DATA_DIR / "12_recall.tsv", separator="\t")
    print(f"  ✓ recall: {len(df_recalls)} rows")

    # 13a - inventory PHASE A: 所有单元都是 Available, 只带 Received movement
    df_inventory_initial, movement_records = gen_initial_inventory_with_received(
        df_lots, df_products, df_pos, n_inventory=2500,
    )
    print(f"  ✓ inventory (initial): {len(df_inventory_initial)} units staged")

    # 14 - surgery (依赖 patient, surgeon, hospital, 初始 inventory)
    df_surgeries = gen_surgeries(
        df_patients["id"].to_list(),
        df_surgeons["id"].to_list(),
        df_hospitals["id"].to_list(),
        df_inventory_initial,
        800,
    )

    # 15 - surgery_implant (消耗 Available 单元; 必须在 Phase B 收尾之前运行)
    df_surgery_implants = gen_surgery_implants(
        df_surgeries, df_inventory_initial, df_surgeons["id"].to_list()
    )

    # 13b - inventory PHASE B: 用 SI + 召回 scope 确定生命周期
    df_inventory, df_movements = finalize_inventory_lifecycle(
        df_inventory_initial, movement_records,
        df_surgery_implants, df_lots, df_recalls,
    )
    df_inventory.write_csv(DATA_DIR / "13_inventory.tsv", separator="\t")
    print(f"  ✓ inventory (finalized): {len(df_inventory)} rows")
    df_movements.write_csv(DATA_DIR / "14_inventory_movement.tsv", separator="\t")
    print(f"  ✓ inventory_movement: {len(df_movements)} rows")

    df_surgeries.write_csv(DATA_DIR / "15_surgery.tsv", separator="\t")
    print(f"  ✓ surgery: {len(df_surgeries)} rows")
    df_surgery_implants.write_csv(DATA_DIR / "16_surgery_implant.tsv", separator="\t")
    print(f"  ✓ surgery_implant: {len(df_surgery_implants)} rows")

    # 17 - adverse_event (依赖 surgery_implant)
    df_adverse = gen_adverse_events(df_surgery_implants, target_n=80)
    df_adverse.write_csv(DATA_DIR / "17_adverse_event.tsv", separator="\t")
    print(f"  ✓ adverse_event: {len(df_adverse)} rows")

    # 18 - patient_followup_visit - 通过 join surgery_implant → surgery 填充 patient_id
    surgery_dict = {row["id"]: row for row in df_surgeries.iter_rows(named=True)}
    si_with_patient = df_surgery_implants.with_columns(
        pl.col("surgery_id").map_elements(
            lambda sid: surgery_dict[sid]["patient_id"], return_dtype=pl.Int64
        ).alias("_patient_id")
    )
    df_followup = gen_patient_followup_visits(si_with_patient, n=1500)
    df_followup.write_csv(DATA_DIR / "18_patient_followup_visit.tsv", separator="\t")
    print(f"  ✓ patient_followup_visit: {len(df_followup)} rows")

    # 19 - recall_notification (依赖 recall, surgery_implant, inventory, lot)
    df_recall_notifications = gen_recall_notifications(
        df_recalls, df_surgery_implants, df_inventory, df_lots
    )
    df_recall_notifications.write_csv(
        DATA_DIR / "19_recall_notification.tsv", separator="\t"
    )
    print(f"  ✓ recall_notification: {len(df_recall_notifications)} rows")

    # 20 - audit_log (真实 ID, change_timestamp 锚定到每行的相关日期)
    df_audit = gen_audit_log(
        df_inventory, df_surgeries, df_surgery_implants, df_adverse, df_recalls, n=800
    )
    df_audit.write_csv(DATA_DIR / "20_audit_log.tsv", separator="\t")
    print(f"  ✓ audit_log: {len(df_audit)} rows")

    print(f"\nAll TSV files generated in {DATA_DIR}")


def create_sqlite_database() -> None:
    """从 TSV 文件构建 SQLite 数据库. 幂等: 先删除已有数据库."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    print("\nLoading data into SQLite database...")

    # (文件名, ORM 类) 按拓扑顺序排列.
    # 注意: recall 现在排在 inventory 之前加载, 因为 inventory 的 Phase B 收尾
    # 步骤要用召回 scope 来决定哪些单元变成 "Recalled".
    load_order: list[tuple[str, type]] = [
        ("01_implant_category.tsv", ImplantCategory),
        ("02_manufacturer.tsv", Manufacturer),
        ("03_hospital.tsv", Hospital),
        ("04_surgeon.tsv", Surgeon),
        ("05_patient.tsv", Patient),
        ("06_implant_product.tsv", ImplantProduct),
        ("07_regulatory_submission.tsv", RegulatorySubmission),
        ("08_pricing_history.tsv", PricingHistory),
        ("09_implant_lot.tsv", ImplantLot),
        ("10_quality_test_event.tsv", QualityTestEvent),
        ("11_purchase_order.tsv", PurchaseOrder),
        ("12_recall.tsv", Recall),
        ("13_inventory.tsv", Inventory),
        ("14_inventory_movement.tsv", InventoryMovement),
        ("15_surgery.tsv", Surgery),
        ("16_surgery_implant.tsv", SurgeryImplant),
        ("17_adverse_event.tsv", AdverseEvent),
        ("18_patient_followup_visit.tsv", PatientFollowupVisit),
        ("19_recall_notification.tsv", RecallNotification),
        ("20_audit_log.tsv", AuditLog),
    ]

    # 这些列的内容全是数字, 否则会被推断成 Int64, 从而悄悄丢掉前导零
    # (UDI-DI 是 GS1 GTIN-14, 带前导零).
    string_schema_overrides: dict[str, dict[str, type[pl.DataType]]] = {
        "implant_product": {"udi_di": pl.String, "model_number": pl.String},
        "inventory": {"udi_pi": pl.String, "serial_number": pl.String},
        "implant_lot": {"lot_number": pl.String},
        "surgeon": {"npi_number": pl.String, "license_number": pl.String},
        "patient": {"mrn": pl.String, "insurance_policy_number": pl.String},
        "regulatory_submission": {"submission_number": pl.String},
        "purchase_order": {"po_number": pl.String},
        "recall": {"recall_number": pl.String, "fda_enforcement_report": pl.String},
        "adverse_event": {"fda_mdr_number": pl.String},
    }

    with Session(engine) as session:
        for filename, model in load_order:
            path = DATA_DIR / filename
            overrides = string_schema_overrides.get(model.__tablename__, {})
            df = pl.read_csv(
                path,
                separator="\t",
                try_parse_dates=True,
                schema_overrides=overrides,
            )
            for row in df.iter_rows(named=True):
                session.add(model(**row))
            session.flush()
            print(f"  ✓ Loaded {model.__tablename__}: {len(df)} rows")
        session.commit()

    print(f"\nSQLite database created at {DATABASE_PATH}")


def main() -> None:
    print("=" * 80)
    print("Medical Devices - Orthopedic Implant Tracking Data Generator")
    print("System of record: MAOHN hospital network implant registry")
    print("Complexity: High (enterprise-grade analytical mart)")
    print("=" * 80)
    generate_all_tsv()
    create_sqlite_database()
    print("\n" + "=" * 80)
    print("Generation complete!")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"TSV files: {DATA_DIR}")
    print(f"SQLite database: {DATABASE_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
