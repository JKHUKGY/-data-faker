"""
Medical Devices - Orthopedic Implant Tracking synthetic data generator.
Complexity: High (enterprise-grade analytical mart).
System of record: the central orthopedic implant registry operated by the
MidAtlantic Orthopedic Health Network (MAOHN), a fictional 12-hospital system.

This generator produces a hospital-side implant registry whose data is sourced
from five upstream feeds (Epic EHR, ERP, the Surgical Information System (SIS),
the FDA GUDID feed, and the FDA enforcement RSS). The raw event tables
(inventory_movement, quality_test_event, pricing_history, patient_followup_visit,
audit_log) are the single source of truth; the silver-tier "current state"
columns on inventory are derived from the raw events during generation, so the
two tiers never drift apart.

For business context, data ownership, data flow, and the full list of generation
invariants, see the ER document.
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
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "medical_devices_orthopedic_implant_tracking_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# "Now" anchor: every generated date is relative to this, so repeated runs stay stable.
NOW = datetime(2026, 6, 1, 12, 0, 0)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# SQLAlchemy ORM models
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
# Helper functions
# ============================================================================
def dt_between(start: datetime, end: datetime) -> datetime:
    """Sample a datetime in [start, end). Falls back to start when the range is empty."""
    if end <= start:
        return start
    delta_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(1, delta_seconds - 1)))


def weighted_choice(values: list, weights: list[float]):
    return random.choices(values, weights=weights, k=1)[0]


# ============================================================================
# Generators - reference data
# ============================================================================
def gen_implant_categories() -> pl.DataFrame:
    """Static catalog of orthopedic implant categories."""
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
    """Manufacturer dimension. Reference data sourced from the GUDID feed."""
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
    """Product dimension. Reference data sourced from the GUDID feed."""
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
            # GS1 AI 01 = 14-digit GTIN
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
    """The hospital network owned by MAOHN."""
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
    """Credentialed orthopedic surgeons. NPI is globally unique."""
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
    """Patient dimension, sourced from Epic EHR."""
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
# Generators - regulatory and pricing reference (raw + silver)
# ============================================================================
def gen_regulatory_submissions(product_ids: list[int], n: int = 250) -> pl.DataFrame:
    """Regulatory submission records. The single source of truth for FDA approval dates.
    status and approval_date stay self-consistent: Approved/Denied have a date, Pending/Withdrawn do not."""
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
            # Approved/Denied must have a decision date strictly later than the submission date
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
    """SCD2 price history. Every product gets at least one interval so a point-in-time
    LEFT JOIN never yields NULL. The latest interval has end_date=NULL (currently in effect).
    Contract discount: 10-30% for GPO/Direct, 0% for Consignment."""
    records = []
    contract_types = ["GPO", "Direct", "Consignment"]
    contract_weights = [0.55, 0.25, 0.20]
    rec_id = 1

    from collections import defaultdict
    # Ensure every product has at least one interval.
    per_product: dict[int, int] = defaultdict(lambda: 1)
    for pid in product_ids:
        _ = per_product[pid]  # touch to insert with default value 1

    # Then sprinkle remaining quota randomly across products (so some products end up with 2 or 3 intervals).
    extra_budget = max(0, n - len(product_ids))
    for _ in range(extra_budget):
        per_product[random.choice(product_ids)] += 1

    # The earliest possible received_date in this dataset is bounded by the earliest
    # lot.manufacture_date (NOW - 5 years; see gen_implant_lots). Pricing must cover
    # at least that lower bound, otherwise point-in-time price lookups would return NULL.
    # We pin the earliest interval's start at NOW - 6 years to leave a 1-year safety margin.
    PRICING_EARLIEST_FLOOR = NOW - timedelta(days=6 * 365)

    for product_id, count in per_product.items():
        n_intervals = min(count, 3)
        # Walk backwards from "now", each interval randomly 6 to 24 months long
        end_marker = NOW
        intervals: list[tuple[datetime, datetime | None]] = []
        for k in range(n_intervals):
            length_days = random.randint(180, 720)
            start = end_marker - timedelta(days=length_days)
            this_end: datetime | None = None if k == 0 else end_marker
            intervals.append((start, this_end))
            end_marker = start
        # Reverse so the earliest interval is first (cosmetic)
        intervals.reverse()
        # Make sure the earliest interval extends back to PRICING_EARLIEST_FLOOR,
        # so any received lot has a valid point-in-time contract price.
        if intervals[0][0] > PRICING_EARLIEST_FLOOR:
            intervals[0] = (PRICING_EARLIEST_FLOOR, intervals[0][1])

        list_price = round(random.uniform(500, 15000), 2)
        for start, end in intervals:
            contract_type = weighted_choice(contract_types, contract_weights)
            # Per the documentation: GPO contracts discount 10-30% off MSRP; Consignment is at list price
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
            # Each renewal nudges the price up slightly
            list_price = round(list_price * random.uniform(1.00, 1.08), 2)

    return pl.DataFrame(records)


def gen_implant_lots(product_ids: list[int], n: int = 400) -> pl.DataFrame:
    """Manufacturing lots. quality_test_passed does not live here; it lives in quality_test_event.
    The manufacture window is intentionally wide ([-5 years, -2 months]) so some lots have
    already expired (making the Expired inventory status reachable), and others are about to
    expire (so Q5 '90 days to expiration' returns rows)."""
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
    """Append-only QC events. Each lot has 1 to 3 events: Incoming Inspection, plus optionally
    Mechanical Load and Sterility. The first event is always Incoming Inspection, and the
    result distribution is 92% Pass / 5% Conditional / 3% Fail."""
    records = []
    rec_id = 1
    test_types = ["Incoming Inspection", "Mechanical Load", "Sterility", "Visual"]
    results = ["Pass", "Conditional", "Fail"]
    result_weights = [0.92, 0.05, 0.03]

    for lot in lots_df.iter_rows(named=True):
        n_events = random.randint(1, 3)
        manufacture_date = lot["manufacture_date"]
        # The first event must be Incoming Inspection
        event_date = dt_between(manufacture_date + timedelta(hours=1),
                                manufacture_date + timedelta(days=14))
        chosen_types = ["Incoming Inspection"]
        for _ in range(n_events - 1):
            chosen_types.append(random.choice(test_types[1:]))

        for test_type in chosen_types:
            # Once the timeline reaches NOW, stop generating further events for this lot;
            # this avoids piling multiple events on the same NOW timestamp.
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


HIGH_COST_CATEGORY_IDS = {4, 5, 6, 7}  # hip, knee, spine, shoulder
LOW_COST_CATEGORY_IDS = {1, 2, 3, 8}   # bone plate, bone screw, intramedullary nail, external fixator


def gen_purchase_orders(
    hospital_ids: list[int],
    manufacturer_categories: dict[int, list[int]],
    n: int = 300,
) -> pl.DataFrame:
    """Hospital -> manufacturer purchase orders (POs). is_consignment is biased by the
    manufacturer's category mix: for manufacturers whose lineup is dominated by high-value
    categories (hip, knee, spine, shoulder), about 60% of POs are consignment; for those
    dominated by low-value categories, about 20%."""
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

        # Pick the manufacturer; then use its dominant categories to bias is_consignment
        mfr_id = random.choice(list(manufacturer_categories.keys()))
        mfr_categories = manufacturer_categories[mfr_id]
        high_cost_share = sum(
            1 for c in mfr_categories if c in HIGH_COST_CATEGORY_IDS
        ) / max(1, len(mfr_categories))
        # Linearly interpolate the consignment probability between 0.20 (all low value) and 0.60 (all high value)
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
            # Rough estimate; not constrained to Sigma(unit price). See Section 8 Known Limitations of the ER document.
            "total_amount_usd": round(random.uniform(5000, 250000), 2),
        })
    return pl.DataFrame(records)


# ============================================================================
# Generators - supply chain (build raw events first, then derive silver current state)
# ----------------------------------------------------------------------------
# Important: the inventory lifecycle uses a TWO-PHASE generation pattern.
#   Phase A - gen_initial_inventory_with_received:
#       Every unit is created as Available with only a Received movement.
#   Phase B - finalize_inventory_lifecycle (called only after surgery_implant
#   and recall have been generated):
#       For each unit:
#         - If consumed by a surgery, append a Used movement at the
#           implantation_timestamp, status="Used", location=NULL.
#         - Otherwise sample one of {Available, Expired, Recalled, Quarantined}
#           subject to eligibility (Expired requires the lot to be past its
#           expiration; Recalled requires the lot or product to fall within a
#           recall's scope).
#         - Append 0 to 2 Transferred movements between Received and the
#           terminal event, fitting within the available time window.
#       The silver current-state columns on inventory (status, location,
#       last_updated) are then derived from the latest movement, so they
#       cannot drift away from the raw event log.
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
    """Phase A: every unit starts as Available with only a Received movement.
    Returns (inventory_df, movements_records), where movements is a list of dicts
    that Phase B will continue appending to."""
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
            # silver current-state placeholder; finalized from the latest movement in Phase B.
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
    """Phase B: append movements to the raw log to give units their
    Used/Expired/Recalled/Quarantined status, then derive the silver current-state
    columns from the last movement.

    Probability buckets (for units not consumed by surgery_implant):
        4% Quarantined
        3% Expired   (only when expiration_date < NOW)
        3% Recalled  (only when the lot or product is in some active recall's scope)
        90% stay Available
    """
    si_by_inventory = {
        row["inventory_id"]: row for row in surgery_implants_df.iter_rows(named=True)
    }
    lots_lookup = {row["id"]: row for row in lots_df.iter_rows(named=True)}
    lot_to_product = {row["id"]: row["product_id"] for row in lots_df.iter_rows(named=True)}

    # Recall scope index
    recalled_lots: dict[int, datetime] = {}
    recalled_products: dict[int, datetime] = {}
    for r in recalls_df.iter_rows(named=True):
        if r["lot_id"] is not None:
            recalled_lots[r["lot_id"]] = r["recall_date"]
        else:
            recalled_products[r["product_id"]] = r["recall_date"]

    # The movement timeline for each inventory
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

        # Between Received and any terminal event, optionally add 0 to 2 Transferred movements
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

        # Decide the terminal status
        final_status = "Available"
        final_location = current_location
        final_last_updated = cur_date

        if si:
            # This unit was consumed by a surgery
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
            # Eligibility checks for the non-Used path
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

            # Use nested if (instead of chained elif) to keep each bucket's probability exact:
            #   [0.00, 0.04) -> Quarantined (always)
            #   [0.04, 0.07) -> Expired if eligible, otherwise stays Available
            #   [0.07, 0.10) -> Recalled if eligible, otherwise stays Available
            #   [0.10, 1.00) -> stays Available
            # The earlier chained-elif version would let roll in [0.04, 0.07) leak into the
            # Recalled branch when past_expiration was False, inflating the Recalled probability
            # for units in recall scope from 3% to as high as 6%.
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

    # Build the final movement DataFrame, with sequence_no within each inventory_id
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
    # Sort movements by id to keep output stable
    all_movement_rows.sort(key=lambda r: r["id"])

    return pl.DataFrame(finalized_inventory), pl.DataFrame(all_movement_rows)


# ============================================================================
# Generators - clinical
# ============================================================================
def gen_surgeries(
    patient_ids: list[int],
    surgeon_ids: list[int],
    hospital_ids: list[int],
    inventory_df: pl.DataFrame,
    n: int = 800,
) -> pl.DataFrame:
    """Surgeries. surgery_date is sampled within a time window where "at least one inventory
    unit has already been received," so the temporal rule (surgery_date >= received_date) holds.
    Revision surgeries (about 8%) link back to an earlier surgery on the same patient."""
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

    # Earliest received date: a surgery can only happen after at least one unit is on the shelf
    earliest_received = inventory_df["received_date"].min()
    surgery_start = max(earliest_received, NOW - timedelta(days=2 * 365))

    # Bucket by patient to support revision linking
    patient_to_prior_surgeries: dict[int, list[tuple[int, datetime]]] = {}

    for i in range(1, n + 1):
        patient_id = random.choice(patient_ids)
        # About 8% are revisions of an earlier surgery on the same patient
        revision_of = None
        prior = patient_to_prior_surgeries.get(patient_id, [])
        if prior and random.random() < 0.08:
            revision_of = random.choice(prior)[0]
            # The surgery date must be later than the prior surgery
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
    """Bridge table: which inventory unit was implanted in which surgery, and when.
    Constraints:
      * Each row's inventory_id is unique (each unit is used at most once)
      * implantation_timestamp is in [surgery_date, surgery_date + duration_minutes]
      * The unit's received_date <= surgery_date
      * implanted_by_surgeon_id is the lead surgeon 80% of the time, otherwise another surgeon
    """
    implant_sites = [
        "Right Femur", "Left Femur", "Right Tibia", "Left Tibia",
        "Right Hip", "Left Hip", "Right Knee", "Left Knee",
        "Lumbar Spine L4-L5", "Lumbar Spine L5-S1",
        "Right Shoulder", "Left Shoulder",
    ]

    # Index inventory by hospital_id for cheap filtering of available units, sorted by received_date
    available_units = inventory_df.filter(pl.col("status") == "Available").to_dicts()
    # This generator is allowed to produce 'Used' status; the inventory.status will be overwritten later.
    # But for SurgeryImplant, we need a unit that's available as of surgery_date.
    # Pre-index by hospital for speed.
    from collections import defaultdict
    by_hospital: dict[int, list[dict]] = defaultdict(list)
    for u in available_units:
        by_hospital[u["hospital_id"]].append(u)

    used_ids: set[int] = set()
    records: list[dict] = []
    rec_id = 1

    # Sort surgeries by date so earlier ones pick first (closer to reality)
    sorted_surgeries = sorted(surgeries_df.to_dicts(), key=lambda s: s["surgery_date"])

    for surgery in sorted_surgeries:
        hospital_id = surgery["hospital_id"]
        primary_surgeon = surgery["surgeon_id"]
        surgery_date = surgery["surgery_date"]
        end_date = surgery_date + timedelta(minutes=surgery["duration_minutes"])

        # Candidates: same hospital, not yet used, and received before surgery_date
        candidates = [
            u for u in by_hospital[hospital_id]
            if u["id"] not in used_ids and u["received_date"] <= surgery_date
        ]
        if not candidates:
            continue

        # Each surgery uses 1 to 5 implants
        n_implants = min(random.randint(1, 5), len(candidates))
        picks = random.sample(candidates, n_implants)
        for unit in picks:
            used_ids.add(unit["id"])
            implant_time = dt_between(surgery_date, end_date)
            # Implanting surgeon: 80% same as the lead surgeon, 20% different
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
    """Adverse events, occurring in roughly 10% of surgeries (modeled per surgery_implant for simplicity).
    event_date is strictly later than the implant's implantation_timestamp."""
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
    """Longitudinal follow-ups. Visit dates are strictly later than implantation.
    Standard cadence: 6 weeks, 6 months, 1 year, then routine. Symptomatic visits are interleaved."""
    records = []
    visit_types_routine = ["6-Week", "6-Month", "1-Year", "Routine"]
    visit_types_symptomatic = ["Symptomatic"]
    functional_scores = ["Excellent", "Good", "Fair", "Poor"]
    score_weights = [0.40, 0.40, 0.15, 0.05]

    # Generate 0 to 4 visits per surgery_implant; truncate the total to n
    si_list = surgery_implants_df.to_dicts()
    random.shuffle(si_list)
    rec_id = 1
    for si in si_list:
        if rec_id > n:
            break
        impl_time = si["implantation_timestamp"]
        if impl_time >= NOW:
            continue
        # 70% have routine follow-ups; 30% have no recorded visits yet
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
                    "patient_id": si.get("_patient_id"),  # filled in below
                    "surgery_implant_id": si["id"],
                    "visit_date": visit_date,
                    "visit_type": random.choice(visit_types_routine),
                    "functional_score": weighted_choice(functional_scores, score_weights),
                    "revision_indicated": weighted_choice([False, True], [0.92, 0.08]),
                    "clinician_notes": fake.sentence() if random.random() > 0.4 else None,
                    "clinician_name": f"Dr. {fake.last_name()}",
                })
                rec_id += 1
        # 15% chance of an additional symptomatic visit
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
# Generators - regulatory / risk
# ============================================================================
def gen_recalls(product_ids: list[int], lots_df: pl.DataFrame, n: int = 12) -> pl.DataFrame:
    """Recalls. status and completion_date stay self-consistent.
    About 70% are lot-level (a random batch of the recalled product); about 30% are full-product."""
    records = []
    recall_classes = ["Class I", "Class II", "Class III"]
    class_weights = [0.10, 0.60, 0.30]
    statuses = ["Active", "Completed", "Terminated"]
    status_weights = [0.40, 0.50, 0.10]

    # Index lots by product so both full-product and lot-level recalls make sense
    from collections import defaultdict
    lots_by_product: dict[int, list[int]] = defaultdict(list)
    for row in lots_df.iter_rows(named=True):
        lots_by_product[row["product_id"]].append(row["id"])

    # Pick distinct products to recall (at most 5% of products)
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

        # lot-level or full-product
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
    """One notification record per implanted unit affected by each recall.
    Scope rule: a unit is affected when (the recall is lot-level AND inventory.lot_id == recall.lot_id)
                or (the recall is full-product AND the inventory's product == recall.product_id)."""
    records = []
    rec_id = 1
    notification_methods = ["Email", "Phone", "Mail", "Patient Portal"]
    notified_parties = ["Patient", "Hospital", "Surgeon"]

    # Build inventory_id -> product_id mapping via lot
    lot_product = {row["id"]: row["product_id"] for row in lots_df.iter_rows(named=True)}
    inv_lot = {row["id"]: row["lot_id"] for row in inventory_df.iter_rows(named=True)}
    inv_product = {iid: lot_product[lot_id] for iid, lot_id in inv_lot.items()}

    si_list = surgery_implants_df.to_dicts()

    for recall in recalls_df.iter_rows(named=True):
        # Filter to the affected implants
        if recall["lot_id"] is not None:
            affected = [si for si in si_list if inv_lot[si["inventory_id"]] == recall["lot_id"]]
        else:
            affected = [si for si in si_list if inv_product[si["inventory_id"]] == recall["product_id"]]

        # Notifications are strictly later than the recall date
        for si in affected:
            # Each unit fans out into 1 to 3 notifications (patient + hospital + surgeon)
            n_notifs = random.randint(1, 3)
            parties = random.sample(notified_parties, n_notifs)
            for party in parties:
                # Per-party SLA: Class I 1-3 days, Class II 5-30 days, Class III 15-60 days
                if recall["recall_class"] == "Class I":
                    delay = random.randint(1, 5)
                elif recall["recall_class"] == "Class II":
                    delay = random.randint(3, 30)
                else:
                    delay = random.randint(7, 60)
                notif_date = recall["recall_date"] + timedelta(days=delay)
                notif_date = min(notif_date, NOW)
                # About 70% acknowledged
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
# Generator - audit log (real ID references)
# ============================================================================
def _audit_payload(table_name: str, action: str) -> tuple[str | None, str | None]:
    """Return appropriate (old_values, new_values) JSON strings per table.
    INSERT has no old_values; DELETE has no new_values."""
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
    # UPDATE case
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
    """Audit log. The (table, id) references are real, and change_timestamp is anchored
    to the referenced row's earliest meaningful date so the audit timeline never shows
    "an audit of a record that doesn't exist yet."
    Per-table anchors:
        inventory.received_date
        surgery.surgery_date
        surgery_implant.implantation_timestamp
        adverse_event.event_date
        recall.recall_date
    The JSON payload field matches the owning table (see _audit_payload)."""
    # Build per-table anchor mapping: id -> anchor_date
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
        # Anchor change_timestamp inside [anchor_date, NOW]
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
# Pipeline
# ============================================================================
def generate_all_tsv() -> None:
    """Generate all TSV files. Idempotent: delete existing TSVs first."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating data...")

    # 01 - implant_category (no dependencies)
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

    # 06 - implant_product (depends on category, manufacturer)
    df_products = gen_implant_products(
        df_categories["id"].to_list(),
        df_manufacturers["id"].to_list(),
        200,
    )
    df_products.write_csv(DATA_DIR / "06_implant_product.tsv", separator="\t")
    print(f"  ✓ implant_product: {len(df_products)} rows")

    # 07 - regulatory_submission (depends on product)
    df_submissions = gen_regulatory_submissions(df_products["id"].to_list(), 250)
    df_submissions.write_csv(DATA_DIR / "07_regulatory_submission.tsv", separator="\t")
    print(f"  ✓ regulatory_submission: {len(df_submissions)} rows")

    # 08 - pricing_history (depends on product, manufacturer)
    product_manufacturer_map = {
        row["id"]: row["manufacturer_id"] for row in df_products.iter_rows(named=True)
    }
    df_pricing = gen_pricing_history(df_products["id"].to_list(), product_manufacturer_map, 500)
    df_pricing.write_csv(DATA_DIR / "08_pricing_history.tsv", separator="\t")
    print(f"  ✓ pricing_history: {len(df_pricing)} rows")

    # 09 - implant_lot (depends on product)
    df_lots = gen_implant_lots(df_products["id"].to_list(), 400)
    df_lots.write_csv(DATA_DIR / "09_implant_lot.tsv", separator="\t")
    print(f"  ✓ implant_lot: {len(df_lots)} rows")

    # 10 - quality_test_event (depends on lot) - RAW tier
    df_qc = gen_quality_test_events(df_lots)
    df_qc.write_csv(DATA_DIR / "10_quality_test_event.tsv", separator="\t")
    print(f"  ✓ quality_test_event: {len(df_qc)} rows")

    # 11 - purchase_order (depends on hospital, manufacturer; consignment share biased by category)
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

    # 12 - recall (sequenced before inventory so Phase B can correctly mark Recalled status)
    df_recalls = gen_recalls(df_products["id"].to_list(), df_lots, 12)
    df_recalls.write_csv(DATA_DIR / "12_recall.tsv", separator="\t")
    print(f"  ✓ recall: {len(df_recalls)} rows")

    # 13a - inventory PHASE A: all units are Available with only a Received movement
    df_inventory_initial, movement_records = gen_initial_inventory_with_received(
        df_lots, df_products, df_pos, n_inventory=2500,
    )
    print(f"  ✓ inventory (initial): {len(df_inventory_initial)} units staged")

    # 14 - surgery (depends on patient, surgeon, hospital, initial inventory)
    df_surgeries = gen_surgeries(
        df_patients["id"].to_list(),
        df_surgeons["id"].to_list(),
        df_hospitals["id"].to_list(),
        df_inventory_initial,
        800,
    )

    # 15 - surgery_implant (consumes Available units; must run before Phase B finalization)
    df_surgery_implants = gen_surgery_implants(
        df_surgeries, df_inventory_initial, df_surgeons["id"].to_list()
    )

    # 13b - inventory PHASE B: finalize lifecycle using SI + recall scope
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

    # 17 - adverse_event (depends on surgery_implant)
    df_adverse = gen_adverse_events(df_surgery_implants, target_n=80)
    df_adverse.write_csv(DATA_DIR / "17_adverse_event.tsv", separator="\t")
    print(f"  ✓ adverse_event: {len(df_adverse)} rows")

    # 18 - patient_followup_visit - fill patient_id by joining surgery_implant -> surgery
    surgery_dict = {row["id"]: row for row in df_surgeries.iter_rows(named=True)}
    si_with_patient = df_surgery_implants.with_columns(
        pl.col("surgery_id").map_elements(
            lambda sid: surgery_dict[sid]["patient_id"], return_dtype=pl.Int64
        ).alias("_patient_id")
    )
    df_followup = gen_patient_followup_visits(si_with_patient, n=1500)
    df_followup.write_csv(DATA_DIR / "18_patient_followup_visit.tsv", separator="\t")
    print(f"  ✓ patient_followup_visit: {len(df_followup)} rows")

    # 19 - recall_notification (depends on recall, surgery_implant, inventory, lot)
    df_recall_notifications = gen_recall_notifications(
        df_recalls, df_surgery_implants, df_inventory, df_lots
    )
    df_recall_notifications.write_csv(
        DATA_DIR / "19_recall_notification.tsv", separator="\t"
    )
    print(f"  ✓ recall_notification: {len(df_recall_notifications)} rows")

    # 20 - audit_log (real IDs, change_timestamp anchored to each row's relevant date)
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

    # (filename, ORM class) listed in topological order.
    # Note: recall is now loaded before inventory, because inventory's Phase B finalization
    # step needs the recall scope to decide which units become "Recalled".
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

    # These columns contain only digits, otherwise they would be inferred as Int64 and silently drop leading zeros
    # (UDI-DI is a GS1 GTIN-14 with leading zeros).
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
