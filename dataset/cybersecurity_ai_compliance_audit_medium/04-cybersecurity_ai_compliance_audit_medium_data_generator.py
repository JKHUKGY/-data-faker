"""
Cybersecurity - AI Compliance Audit System fake data generator
Complexity: Medium
Tool: Fake Data Generator Agent

Business context:
This dataset simulates an enterprise AI compliance audit system, targeting organizations
that deploy AI/ML models in production. The system supports tracking compliance frameworks
such as NIST AI RMF, GDPR, and HIPAA, AI model risk assessment, security incident management,
and remediation action workflows. It serves AI security engineers, compliance auditors,
and MLOps teams.

Time anchor note:
All date fields are dynamically generated relative to datetime.now() (the moment of
generation is treated as "today"), to prevent the dataset from losing discriminative power
against julianday('now') in SQL as time passes. The random seed is fixed at 42, so the
"relative offsets" within a single run are reproducible, but the absolute dates vary
depending on the run date.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import random

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "cybersecurity_ai_compliance_audit_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# Dynamic time anchor: treat "the moment of running this script" as today; all dates roll back into the past
NOW = datetime.now().replace(microsecond=0)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


def days_ago(low: int, high: int, with_time: bool = True) -> datetime:
    """Return a random datetime within the [low, high] day range before today (including hours and minutes)."""
    delta_days = random.randint(low, high)
    if with_time:
        return NOW - timedelta(
            days=delta_days,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
    return NOW - timedelta(days=delta_days)


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class ComplianceFramework(Base):
    """Compliance framework, such as NIST AI RMF, GDPR, HIPAA, etc."""
    __tablename__ = "compliance_framework"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class RiskCategory(Base):
    """Enumeration of AI system risk categories."""
    __tablename__ = "risk_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    severity_weight: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class ControlStatus(Base):
    """Enumeration of control measure statuses."""
    __tablename__ = "control_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    """System users, including auditors, engineers, and managers."""
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AIModel(Base):
    """AI/ML model registry and metadata."""
    __tablename__ = "ai_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    deployment_env: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_audit_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ComplianceControl(Base):
    """Compliance control measures mapped to frameworks."""
    __tablename__ = "compliance_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    framework_id: Mapped[int] = mapped_column(Integer, ForeignKey("compliance_framework.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)


class RiskAssessment(Base):
    """AI model risk assessment."""
    __tablename__ = "risk_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_model.id"), nullable=False)
    risk_category_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_category.id"), nullable=False)
    assessor_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    likelihood_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # likelihood * impact * weight
    mitigation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ModelControlAssessment(Base):
    """Compliance assessment of model x control (M:N bridge table, the core action of AI compliance audit).

    Purpose: Compliance auditors assess the compliance of each applicable control for each
    model, recording the assessment conclusion, evidence summary, assessment time, and next
    review date. This table makes "which model is compliant on which control" a first-class
    query object."""
    __tablename__ = "model_control_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_model.id"), nullable=False)
    control_id: Mapped[int] = mapped_column(Integer, ForeignKey("compliance_control.id"), nullable=False)
    assessor_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    compliance_status: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    next_review_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    """Audit log for all compliance-related actions."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    ai_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_model.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)


class SecurityIncident(Base):
    """Security incidents related to AI systems."""
    __tablename__ = "security_incident"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    ai_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ai_model.id"), nullable=False)
    reported_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class RemediationAction(Base):
    """Remediation actions for security incidents and risk findings."""
    __tablename__ = "remediation_action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("security_incident.id"), nullable=True)
    risk_assessment_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_assessment.id"), nullable=True)
    control_id: Mapped[int] = mapped_column(Integer, ForeignKey("compliance_control.id"), nullable=False)
    assigned_to_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("control_status.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# ============================================================================
# Data generators
# ============================================================================

def gen_compliance_framework() -> pl.DataFrame:
    """Generate compliance framework reference data."""
    data = [
        {"id": 1, "code": "NIST_AI_RMF", "name": "NIST AI Risk Management Framework",
         "description": "Framework for managing risks in AI systems", "version": "1.0",
         "effective_date": datetime(2023, 1, 26)},
        {"id": 2, "code": "GDPR", "name": "General Data Protection Regulation",
         "description": "EU regulation on data protection and privacy", "version": "2016/679",
         "effective_date": datetime(2018, 5, 25)},
        {"id": 3, "code": "HIPAA", "name": "Health Insurance Portability and Accountability Act",
         "description": "US healthcare data privacy regulation", "version": "1996",
         "effective_date": datetime(1996, 8, 21)},
        {"id": 4, "code": "OWASP_AI", "name": "OWASP AI Security Top 10",
         "description": "Top 10 AI security vulnerabilities", "version": "2023",
         "effective_date": datetime(2023, 6, 1)},
        {"id": 5, "code": "ISO_27001", "name": "ISO/IEC 27001 Information Security",
         "description": "International standard for information security management", "version": "2022",
         "effective_date": datetime(2022, 10, 25)},
        {"id": 6, "code": "SOC2", "name": "SOC 2 Type II",
         "description": "Service Organization Control 2 audit standard", "version": "2017",
         "effective_date": datetime(2017, 1, 1)},
    ]
    return pl.DataFrame(data)


def gen_risk_category() -> pl.DataFrame:
    """Generate the risk category enumeration."""
    data = [
        {"id": 1, "code": "DATA_PRIVACY", "name": "Data Privacy Violation",
         "severity_weight": 1.5, "description": "Risks related to unauthorized data access or leakage"},
        {"id": 2, "code": "MODEL_BIAS", "name": "Algorithmic Bias",
         "severity_weight": 1.3, "description": "Unfair or discriminatory model outputs"},
        {"id": 3, "code": "ADVERSARIAL", "name": "Adversarial Attack",
         "severity_weight": 1.8, "description": "Attacks designed to manipulate model behavior"},
        {"id": 4, "code": "DATA_DRIFT", "name": "Data Drift",
         "severity_weight": 1.0, "description": "Changes in data distribution affecting model performance"},
        {"id": 5, "code": "MODEL_INVERSION", "name": "Model Inversion Attack",
         "severity_weight": 1.6, "description": "Attacks to extract training data from models"},
        {"id": 6, "code": "PROMPT_INJECTION", "name": "Prompt Injection",
         "severity_weight": 1.7, "description": "Malicious prompts to bypass LLM safeguards"},
        {"id": 7, "code": "SUPPLY_CHAIN", "name": "Supply Chain Vulnerability",
         "severity_weight": 1.4, "description": "Risks from third-party dependencies"},
        {"id": 8, "code": "EXPLAINABILITY", "name": "Lack of Explainability",
         "severity_weight": 0.9, "description": "Insufficient model interpretability"},
    ]
    return pl.DataFrame(data)


def gen_control_status() -> pl.DataFrame:
    """Generate the control status enumeration."""
    data = [
        {"id": 1, "code": "PENDING", "name": "Pending Review", "is_terminal": False},
        {"id": 2, "code": "IN_PROGRESS", "name": "In Progress", "is_terminal": False},
        {"id": 3, "code": "COMPLETED", "name": "Completed", "is_terminal": True},
        {"id": 4, "code": "DEFERRED", "name": "Deferred", "is_terminal": False},
        {"id": 5, "code": "CANCELLED", "name": "Cancelled", "is_terminal": True},
    ]
    return pl.DataFrame(data)


def gen_user(n: int = 30) -> pl.DataFrame:
    """Generate system users with different roles.

    created_at: 60-730 days ago, covering an onboarding window from 2 months to 2 years.
    """
    roles = [
        ("AI Security Engineer", "Engineering"),
        ("Compliance Auditor", "Compliance"),
        ("Data Scientist", "Data Science"),
        ("MLOps Engineer", "Engineering"),
        ("Risk Manager", "Risk Management"),
        ("Security Analyst", "Security"),
        ("Product Manager", "Product"),
        ("DevOps Engineer", "Engineering"),
    ]

    data = []
    for i in range(1, n + 1):
        role, dept = random.choice(roles)
        data.append({
            "id": i,
            "email": fake.unique.email(),
            "full_name": fake.name(),
            "role": role,
            "department": dept,
            "is_active": random.random() > 0.1,
            "created_at": days_ago(60, 730),
        })

    fake.unique.clear()
    return pl.DataFrame(data)


def gen_ai_model(n: int = 50, user_ids: list[int] = None,
                 user_created_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """Generate AI model registry records.

    Distribution:
      - risk_tier: weighted HIGH(30%), MEDIUM(35%), LOW(25%), CRITICAL(10%)
      - is_active: 85% true
      - last_audit_date: 50% within [0, 180] days (recently audited), 30% within [181, 540] days (stale),
        20% NULL (never audited). This way Query 19 (>180-day threshold) preserves discriminative power.

    Temporal constraint: created_at is strictly after owner.created_at.
    """
    model_types = [
        "Classification", "Regression", "NLP", "Computer Vision",
        "Recommendation", "Anomaly Detection", "LLM", "Embedding"
    ]
    model_prefixes = [
        "FraudDetector", "CustomerChurn", "SentimentAnalyzer", "ImageClassifier",
        "RecommendEngine", "AnomalyScorer", "ChatBot", "DocProcessor",
        "RiskScorer", "ComplianceChecker", "ThreatDetector", "DataQuality"
    ]
    environments = ["production", "staging", "development", "canary"]
    risk_tiers = ["HIGH", "MEDIUM", "LOW", "CRITICAL"]
    risk_tier_weights = [30, 35, 25, 10]  # Consistent with the ER document declaration

    data = []
    for i in range(1, n + 1):
        prefix = random.choice(model_prefixes)
        version = f"v{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 99)}"

        owner_id = random.choice(user_ids) if user_ids else random.randint(1, 30)
        owner_created = user_created_lookup.get(owner_id) if user_created_lookup else None

        # created_at: 30-540 days ago, but must be later than owner.created_at
        created_at = days_ago(30, 540)
        if owner_created and created_at < owner_created:
            # Force it to be later than owner
            min_offset = (NOW - owner_created).days
            created_at = days_ago(30, max(31, min_offset - 1))

        # last_audit_date distribution (ensures Query 19 has discriminative power):
        # 20% NULL (never audited); among audited models, sufficiently old ones are
        # preferred to become stale, otherwise they can only be recent. A model has
        # to exist long enough to accumulate a stale audit.
        model_age_days = max(1, (NOW - created_at).days)
        if random.random() < 0.20:
            last_audit_date = None
        else:
            # Models aged >= 220 days have a 50% chance of being marked as stale audit
            if model_age_days >= 220 and random.random() < 0.50:
                stale_upper = min(540, model_age_days - 1)
                stale_age = random.randint(181, stale_upper)
                last_audit_date = NOW - timedelta(
                    days=stale_age,
                    hours=random.randint(0, 23),
                )
            else:
                recent_upper = min(180, max(1, model_age_days - 1))
                recent_age = random.randint(0, recent_upper)
                last_audit_date = NOW - timedelta(
                    days=recent_age,
                    hours=random.randint(0, 23),
                )

        data.append({
            "id": i,
            "model_name": f"{prefix}_{fake.lexify('???').upper()}",
            "version": version,
            "model_type": random.choice(model_types),
            "deployment_env": random.choice(environments),
            "owner_id": owner_id,
            "risk_tier": random.choices(risk_tiers, weights=risk_tier_weights, k=1)[0],
            "description": fake.sentence(nb_words=12),
            "created_at": created_at,
            "last_audit_date": last_audit_date,
            "is_active": random.random() > 0.15,
        })

    return pl.DataFrame(data)


def gen_compliance_control(n: int = 100, framework_ids: list[int] = None) -> pl.DataFrame:
    """Generate compliance control measures."""
    categories = ["Governance", "Data Management", "Model Development", "Deployment", "Monitoring", "Incident Response"]
    priorities = ["P1-Critical", "P2-High", "P3-Medium", "P4-Low"]

    control_templates = [
        "Implement {} validation for AI model inputs",
        "Establish {} monitoring for model performance",
        "Configure {} logging for audit trails",
        "Deploy {} controls for data access",
        "Enforce {} policies for model deployment",
        "Maintain {} documentation for AI systems",
        "Conduct {} testing before production release",
        "Apply {} encryption for sensitive data",
    ]

    keywords = ["automated", "continuous", "periodic", "real-time", "comprehensive", "role-based", "risk-based"]

    data = []
    for i in range(1, n + 1):
        fw_id = random.choice(framework_ids) if framework_ids else random.randint(1, 6)
        category = random.choice(categories)
        template = random.choice(control_templates)
        keyword = random.choice(keywords)

        # Generate the control ID based on the framework
        fw_prefixes = {1: "NIST", 2: "GDPR", 3: "HIPAA", 4: "OWASP", 5: "ISO", 6: "SOC"}
        prefix = fw_prefixes.get(fw_id, "CTRL")

        data.append({
            "id": i,
            "control_id": f"{prefix}-{category[:3].upper()}-{i:03d}",
            "framework_id": fw_id,
            "name": template.format(keyword),
            "description": fake.paragraph(nb_sentences=2),
            "category": category,
            "priority": random.choice(priorities),
        })

    return pl.DataFrame(data)


def gen_risk_assessment(n: int = 200, model_ids: list[int] = None,
                        risk_cat_ids: list[int] = None, user_ids: list[int] = None,
                        model_created_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """Generate AI model risk assessment records.

    assessed_at: 0-365 days ago, but strictly later than the assessed model's created_at.
    """
    mitigation_statuses = ["NOT_STARTED", "IN_PROGRESS", "MITIGATED", "ACCEPTED", "TRANSFERRED"]

    finding_templates = [
        "Model shows {} in {} scenarios requiring attention.",
        "Assessment identified {} related to {} that needs mitigation.",
        "Review found potential {} affecting {} components.",
        "Analysis detected {} in {} requiring control implementation.",
    ]

    issues = ["elevated risk", "vulnerability", "compliance gap", "performance degradation", "bias patterns"]
    areas = ["edge case handling", "data preprocessing", "inference pipeline", "access controls", "monitoring"]

    risk_weights = {1: 1.5, 2: 1.3, 3: 1.8, 4: 1.0, 5: 1.6, 6: 1.7, 7: 1.4, 8: 0.9}

    data = []
    for i in range(1, n + 1):
        risk_cat_id = random.choice(risk_cat_ids) if risk_cat_ids else random.randint(1, 8)
        likelihood = random.randint(1, 5)
        impact = random.randint(1, 5)
        weight = risk_weights.get(risk_cat_id, 1.0)

        template = random.choice(finding_templates)
        issue = random.choice(issues)
        area = random.choice(areas)

        ai_model_id = random.choice(model_ids) if model_ids else random.randint(1, 50)
        assessed_at = days_ago(0, 365)
        if model_created_lookup and ai_model_id in model_created_lookup:
            model_created = model_created_lookup[ai_model_id]
            if assessed_at < model_created:
                # The assessment time must be at least after the model was created
                assessed_at = model_created + timedelta(days=random.randint(1, 30))

        data.append({
            "id": i,
            "ai_model_id": ai_model_id,
            "risk_category_id": risk_cat_id,
            "assessor_id": random.choice(user_ids) if user_ids else random.randint(1, 30),
            "likelihood_score": likelihood,
            "impact_score": impact,
            "risk_score": round(likelihood * impact * weight, 2),
            "mitigation_status": random.choice(mitigation_statuses),
            "findings": template.format(issue, area),
            "assessed_at": assessed_at,
        })

    return pl.DataFrame(data)


def gen_model_control_assessment(n: int = 300, model_ids: list[int] = None,
                                  control_ids: list[int] = None, user_ids: list[int] = None,
                                  model_created_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """Generate model x control compliance assessment records (M:N bridge table).

    Business semantics:
      - Compliance auditors assess each model on each applicable control, recording the
        compliance conclusion and the evidence summary.
      - (ai_model_id, control_id) is kept unique within the n records as much as possible
        (no unique constraint is enforced).
      - compliance_status distribution: COMPLIANT 50%, PARTIALLY_COMPLIANT 25%,
        NON_COMPLIANT 15%, NOT_APPLICABLE 10%.
      - assessed_at must be later than the model's creation time.
      - next_review_date is 90-365 days after assessed_at.
    """
    statuses = ["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT", "NOT_APPLICABLE"]
    status_weights = [50, 25, 15, 10]

    evidence_templates = [
        "Verified via {} during {} review; documentation in artifact registry.",
        "Evidence collected from {} logs covering {} test cases.",
        "Control validated through {} with results captured in {}.",
        "Assessment based on {} examination of {}.",
        "Findings documented in {} report indexed under {}.",
    ]
    evidence_methods = ["automated scan", "manual inspection", "policy review", "code audit", "pen test"]
    evidence_artifacts = ["Q1 audit", "Q2 audit", "annual review", "ad-hoc audit", "incident-triggered review"]

    used_pairs: set[tuple[int, int]] = set()
    model_pool = list(model_ids) if model_ids else list(range(1, 51))
    control_pool = list(control_ids) if control_ids else list(range(1, 101))
    max_unique_pairs = len(model_pool) * len(control_pool)
    n = min(n, max_unique_pairs)

    data = []
    for i in range(1, n + 1):
        # Sample a unique (model, control) pair
        attempts = 0
        while True:
            ai_model_id = random.choice(model_pool)
            control_id = random.choice(control_pool)
            pair = (ai_model_id, control_id)
            attempts += 1
            if pair not in used_pairs:
                used_pairs.add(pair)
                break
            if attempts > 100:
                # It's getting hard to draw a new pair, exit early (in theory 50*100=5000 far exceeds n=300, so this won't fire)
                used_pairs.add(pair)
                break

        assessed_at = days_ago(0, 365)
        if model_created_lookup and ai_model_id in model_created_lookup:
            model_created = model_created_lookup[ai_model_id]
            if assessed_at < model_created:
                assessed_at = model_created + timedelta(days=random.randint(1, 30))

        next_review_date = assessed_at + timedelta(days=random.randint(90, 365))

        template = random.choice(evidence_templates)
        method = random.choice(evidence_methods)
        artifact = random.choice(evidence_artifacts)

        data.append({
            "id": i,
            "ai_model_id": ai_model_id,
            "control_id": control_id,
            "assessor_id": random.choice(user_ids) if user_ids else random.randint(1, 30),
            "compliance_status": random.choices(statuses, weights=status_weights, k=1)[0],
            "evidence_summary": template.format(method, artifact),
            "assessed_at": assessed_at,
            "next_review_date": next_review_date,
        })

    return pl.DataFrame(data)


# entity_type -> upper bound of the corresponding table's id (used to coordinate audit_log.entity_id with entity_type)
ENTITY_TYPE_MAX_ID = {
    "AI_MODEL": 50,
    "RISK_ASSESSMENT": 200,
    "COMPLIANCE_CONTROL": 100,
    "SECURITY_INCIDENT": 80,
    "REMEDIATION_ACTION": 120,
    "USER": 30,
    "MODEL_CONTROL_ASSESSMENT": 300,
    "REPORT": 50,  # No entity table, used as a synthetic ID range
}


def gen_audit_log(n: int = 500, user_ids: list[int] = None, model_ids: list[int] = None,
                  user_created_lookup: dict[int, datetime] = None,
                  model_created_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """Generate audit log entries.

    Temporal constraints:
      - timestamp must be later than user.created_at (the acting user already exists).
      - If ai_model_id is non-null, it must be later than ai_model.created_at.

    Polymorphic field entity_id:
      - Choose a reasonable id range based on entity_type (still no FK constraint, but
        guaranteed to be joinable back to real records).
    """
    action_types = [
        "CREATE", "UPDATE", "DELETE", "VIEW", "EXPORT", "APPROVE", "REJECT",
        "DEPLOY", "ROLLBACK", "ASSESS", "REMEDIATE"
    ]
    entity_types = list(ENTITY_TYPE_MAX_ID.keys())

    detail_templates = [
        "User performed {} on {} record",
        "Action {} completed for {} entity",
        "System recorded {} operation on {}",
        "Audit trail captured {} for {}",
    ]

    data = []
    for i in range(1, n + 1):
        action = random.choice(action_types)
        entity = random.choice(entity_types)
        template = random.choice(detail_templates)

        user_id = random.choice(user_ids) if user_ids else random.randint(1, 30)
        # 70% of logs are related to an AI model
        model_id = random.choice(model_ids) if model_ids and random.random() > 0.3 else None

        # Compute the earliest allowed time: must be later than both user.created_at and model.created_at
        earliest = NOW - timedelta(days=400)  # Fallback default window
        if user_created_lookup and user_id in user_created_lookup:
            earliest = max(earliest, user_created_lookup[user_id])
        if model_id and model_created_lookup and model_id in model_created_lookup:
            earliest = max(earliest, model_created_lookup[model_id])

        # Sample uniformly within [earliest+1day, NOW]
        window_days = max(1, (NOW - earliest).days - 1)
        timestamp = earliest + timedelta(
            days=random.randint(1, window_days),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        # entity_id coordinated with entity_type
        entity_max = ENTITY_TYPE_MAX_ID[entity]
        entity_id = random.randint(1, entity_max)

        data.append({
            "id": i,
            "timestamp": timestamp,
            "user_id": user_id,
            "ai_model_id": model_id,
            "action_type": action,
            "entity_type": entity,
            "entity_id": entity_id,
            "details": template.format(action.lower(), entity.lower().replace("_", " ")),
            "ip_address": fake.ipv4(),
        })

    return pl.DataFrame(data)


def gen_security_incident(n: int = 80, model_ids: list[int] = None, user_ids: list[int] = None,
                          model_created_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """Generate security incident records.

    Distribution:
      - severity: weighted CRITICAL(10%), HIGH(25%), MEDIUM(40%), LOW(25%) (consistent with the ER document).
    Temporal constraint:
      - reported_at strictly later than ai_model.created_at.
    Identifier:
      - The year in incident_id is taken from reported_at.year (fixes the hardcoded 2023 year).
    """
    incident_types = [
        "ADVERSARIAL_ATTACK", "DATA_BREACH", "PROMPT_INJECTION", "MODEL_THEFT",
        "UNAUTHORIZED_ACCESS", "DATA_POISONING", "API_ABUSE", "INSIDER_THREAT"
    ]

    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    severity_weights = [10, 25, 40, 25]
    statuses = ["OPEN", "INVESTIGATING", "CONTAINED", "RESOLVED", "CLOSED"]

    description_templates = [
        "Detected {} attempt targeting {} with potential {} impact.",
        "Security monitoring identified {} activity in {} requiring immediate {}.",
        "Incident involving {} was reported affecting {} with {} severity.",
        "Automated alert triggered for {} in {} necessitating {} response.",
    ]

    targets = ["production model", "training pipeline", "inference API", "data lake", "model registry"]
    responses = ["investigation", "containment", "escalation", "patching", "monitoring"]

    root_causes = [
        "Insufficient input validation allowed malicious payload",
        "Misconfigured access controls permitted unauthorized access",
        "Outdated dependency contained known vulnerability",
        "Inadequate monitoring delayed detection of anomaly",
        "Missing rate limiting enabled API abuse",
        None,  # Some incidents may not yet have a determined root cause
    ]

    data = []
    for i in range(1, n + 1):
        incident_type = random.choice(incident_types)
        status = random.choice(statuses)
        severity = random.choices(severities, weights=severity_weights, k=1)[0]

        template = random.choice(description_templates)
        target = random.choice(targets)
        response = random.choice(responses)

        ai_model_id = random.choice(model_ids) if model_ids else random.randint(1, 50)
        reported_at = days_ago(0, 365)
        if model_created_lookup and ai_model_id in model_created_lookup:
            model_created = model_created_lookup[ai_model_id]
            if reported_at < model_created:
                reported_at = model_created + timedelta(days=random.randint(1, 30))

        resolved_at = None
        if status in ["RESOLVED", "CLOSED"]:
            resolved_at = reported_at + timedelta(
                hours=random.randint(1, 72),
                minutes=random.randint(0, 59)
            )

        data.append({
            "id": i,
            # Year taken from reported_at; incidents that span year boundaries are no longer mislabeled as 2023
            "incident_id": f"INC-{reported_at.year}-{i:04d}",
            "ai_model_id": ai_model_id,
            "reported_by_id": random.choice(user_ids) if user_ids else random.randint(1, 30),
            "incident_type": incident_type,
            "severity": severity,
            "status": status,
            "description": template.format(incident_type.lower().replace("_", " "), target, response),
            "root_cause": random.choice(root_causes) if status in ["RESOLVED", "CLOSED"] else None,
            "reported_at": reported_at,
            "resolved_at": resolved_at,
        })

    return pl.DataFrame(data)


def gen_remediation_action(n: int = 120, incident_ids: list[int] = None,
                           assessment_ids: list[int] = None, control_ids: list[int] = None,
                           user_ids: list[int] = None, status_ids: list[int] = None,
                           incident_reported_lookup: dict[int, datetime] = None,
                           assessment_assessed_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """Generate remediation action records.

    Mutual exclusion rule: incident_id and risk_assessment_id are strictly mutually exclusive
    (exactly one is non-null, the other is NULL).

    Temporal constraints:
      - A remediation is triggered by an incident or a risk assessment, so created_at must be
        later than the upstream:
        * When linked to an incident: created_at > incident.reported_at + 1~30 days
        * When linked to an assessment: created_at > risk_assessment.assessed_at + 1~30 days
      - completed_at must not exceed NOW ("completed in the future" is logically impossible).
    """
    action_templates = [
        "Implement {} to address identified vulnerability",
        "Configure {} monitoring for early detection",
        "Deploy {} patch to remediate security issue",
        "Update {} policies to prevent recurrence",
        "Enhance {} controls for improved protection",
        "Establish {} procedures for compliance",
    ]

    measures = ["automated scanning", "access control", "encryption", "logging", "rate limiting", "input validation"]

    data = []
    for i in range(1, n + 1):
        # 60% linked to an incident, 40% linked to a risk assessment (mutually exclusive)
        linked_to_incident = random.random() > 0.4

        template = random.choice(action_templates)
        measure = random.choice(measures)

        # Derive created_at: push 1-30 days forward from the upstream trigger object's time
        # If linked to an incident: upstream = incident.reported_at; otherwise: upstream = risk_assessment.assessed_at
        incident_id = random.choice(incident_ids) if linked_to_incident and incident_ids else None
        assessment_id = random.choice(assessment_ids) if not linked_to_incident and assessment_ids else None

        upstream_time: datetime | None = None
        if incident_id is not None and incident_reported_lookup is not None:
            upstream_time = incident_reported_lookup.get(incident_id)
        elif assessment_id is not None and assessment_assessed_lookup is not None:
            upstream_time = assessment_assessed_lookup.get(assessment_id)

        if upstream_time is not None:
            # created_at = upstream_time + 1~30 days, but must not exceed NOW
            offset_days = random.randint(1, 30)
            tentative = upstream_time + timedelta(
                days=offset_days,
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            if tentative > NOW:
                # The upstream event is already close to today, so created_at falls between [upstream, NOW]
                max_offset = max(1, (NOW - upstream_time).days)
                created_at = upstream_time + timedelta(
                    hours=random.randint(1, max(1, max_offset * 24 - 1))
                )
            else:
                created_at = tentative
            # Second line of defense: when upstream is extremely close to NOW, the earlier
            # hour additions can still overflow; clamp back to a random moment before NOW
            # (not exactly NOW), so multiple records don't pile up at the same timestamp
            if created_at > NOW:
                created_at = NOW - timedelta(
                    minutes=random.randint(1, 59),
                    seconds=random.randint(0, 59),
                )
        else:
            # Fallback: revert to original behavior when there is no upstream lookup
            created_at = days_ago(0, 300)

        due_date = created_at + timedelta(days=random.randint(7, 90))

        status_id = random.choice(status_ids) if status_ids else random.randint(1, 5)
        completed_at = None
        if status_id == 3:  # COMPLETED
            # completed_at = created_at + 1~60 days, but must not exceed NOW (a future completion time makes no sense)
            max_offset_days = max(1, (NOW - created_at).days)
            completion_offset = random.randint(1, min(60, max_offset_days))
            completed_at = created_at + timedelta(
                days=completion_offset,
                hours=random.randint(0, 23),
            )
            # Belt-and-suspenders: in rare edge cases, clamp back to a random moment before NOW
            # Note: must not clamp back to exactly NOW -- if multiple remediations hit this branch,
            # their completed_at would all land on the exact same second, causing a visual anomaly
            if completed_at > NOW:
                completed_at = NOW - timedelta(
                    hours=random.randint(1, 23),
                    minutes=random.randint(0, 59),
                )
            # Also ensure completed_at > created_at (extreme edge case when both are near NOW)
            if completed_at <= created_at:
                completed_at = created_at + timedelta(minutes=random.randint(5, 30))
                if completed_at > NOW:
                    completed_at = NOW - timedelta(minutes=random.randint(1, 30))

        data.append({
            "id": i,
            "incident_id": incident_id,
            "risk_assessment_id": assessment_id,
            "control_id": random.choice(control_ids) if control_ids else random.randint(1, 100),
            "assigned_to_id": random.choice(user_ids) if user_ids else random.randint(1, 30),
            "status_id": status_id,
            "title": template.format(measure),
            "description": fake.paragraph(nb_sentences=2),
            "due_date": due_date,
            "created_at": created_at,
            "completed_at": completed_at,
        })

    return pl.DataFrame(data)


# ============================================================================
# Core functions (idempotent operations)
# ============================================================================

def generate_all_tsv() -> dict[str, pl.DataFrame]:
    """Generate all TSV files. Idempotent operation: deletes existing files first."""
    # Ensure the data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Delete existing TSV files
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    # Generate data in topological order (tables without FK dependencies go first)
    dataframes = {}

    # Level 0: no dependencies
    print("生成 Level 0 表（无依赖）...")
    dataframes["compliance_framework"] = gen_compliance_framework()
    dataframes["risk_category"] = gen_risk_category()
    dataframes["control_status"] = gen_control_status()
    dataframes["user"] = gen_user(30)

    # Extract IDs and timestamps for foreign key references and temporal alignment
    user_ids = dataframes["user"]["id"].to_list()
    framework_ids = dataframes["compliance_framework"]["id"].to_list()
    risk_cat_ids = dataframes["risk_category"]["id"].to_list()
    status_ids = dataframes["control_status"]["id"].to_list()
    user_created_lookup = dict(zip(
        dataframes["user"]["id"].to_list(),
        dataframes["user"]["created_at"].to_list(),
    ))

    # Level 1: depends on Level 0
    print("生成 Level 1 表...")
    dataframes["ai_model"] = gen_ai_model(50, user_ids, user_created_lookup)
    dataframes["compliance_control"] = gen_compliance_control(100, framework_ids)

    model_ids = dataframes["ai_model"]["id"].to_list()
    control_ids = dataframes["compliance_control"]["id"].to_list()
    model_created_lookup = dict(zip(
        dataframes["ai_model"]["id"].to_list(),
        dataframes["ai_model"]["created_at"].to_list(),
    ))

    # Level 2: depends on Level 1
    print("生成 Level 2 表...")
    dataframes["risk_assessment"] = gen_risk_assessment(
        200, model_ids, risk_cat_ids, user_ids, model_created_lookup
    )
    dataframes["model_control_assessment"] = gen_model_control_assessment(
        300, model_ids, control_ids, user_ids, model_created_lookup
    )
    dataframes["audit_log"] = gen_audit_log(
        500, user_ids, model_ids, user_created_lookup, model_created_lookup
    )
    dataframes["security_incident"] = gen_security_incident(
        80, model_ids, user_ids, model_created_lookup
    )

    assessment_ids = dataframes["risk_assessment"]["id"].to_list()
    incident_ids = dataframes["security_incident"]["id"].to_list()

    # Build upstream time lookups, used for temporal alignment in remediation_action:
    #   - When linked to an incident, created_at must be later than incident.reported_at
    #   - When linked to an assessment, created_at must be later than risk_assessment.assessed_at
    incident_reported_lookup = dict(zip(
        dataframes["security_incident"]["id"].to_list(),
        dataframes["security_incident"]["reported_at"].to_list(),
    ))
    assessment_assessed_lookup = dict(zip(
        dataframes["risk_assessment"]["id"].to_list(),
        dataframes["risk_assessment"]["assessed_at"].to_list(),
    ))

    # Level 3: depends on Level 2
    print("生成 Level 3 表...")
    dataframes["remediation_action"] = gen_remediation_action(
        120, incident_ids, assessment_ids, control_ids, user_ids, status_ids,
        incident_reported_lookup=incident_reported_lookup,
        assessment_assessed_lookup=assessment_assessed_lookup,
    )

    # Save as TSV files in order
    file_order = [
        ("01", "compliance_framework"),
        ("02", "risk_category"),
        ("03", "control_status"),
        ("04", "user"),
        ("05", "ai_model"),
        ("06", "compliance_control"),
        ("07", "risk_assessment"),
        ("08", "model_control_assessment"),
        ("09", "audit_log"),
        ("10", "security_incident"),
        ("11", "remediation_action"),
    ]

    for prefix, table_name in file_order:
        filepath = DATA_DIR / f"{prefix}_{table_name}.tsv"
        dataframes[table_name].write_csv(filepath, separator="\t")
        row_count = len(dataframes[table_name])
        print(f"  创建 {filepath.name} ({row_count} 行)")

    print(f"\n{'='*60}")
    print(f"已在 {DATA_DIR} 生成所有 TSV 文件")

    return dataframes


def create_sqlite_database(dataframes: dict[str, pl.DataFrame]) -> None:
    """Create the SQLite database from the generated data. Idempotent: deletes the existing database first."""
    # Delete the existing database
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # Mapping from table name to ORM class
    orm_classes = {
        "compliance_framework": ComplianceFramework,
        "risk_category": RiskCategory,
        "control_status": ControlStatus,
        "user": User,
        "ai_model": AIModel,
        "compliance_control": ComplianceControl,
        "risk_assessment": RiskAssessment,
        "model_control_assessment": ModelControlAssessment,
        "audit_log": AuditLog,
        "security_incident": SecurityIncident,
        "remediation_action": RemediationAction,
    }

    # Load order (topological sort)
    load_order = [
        "compliance_framework", "risk_category", "control_status", "user",
        "ai_model", "compliance_control",
        "risk_assessment", "model_control_assessment", "audit_log", "security_incident",
        "remediation_action"
    ]

    with Session(engine) as session:
        for table_name in load_order:
            df = dataframes[table_name]
            orm_class = orm_classes[table_name]

            records = df.to_dicts()
            for record in records:
                # Convert empty strings to None
                for key, value in record.items():
                    if value == "" or value == "None":
                        record[key] = None

                obj = orm_class(**record)
                session.add(obj)

            print(f"  加载 {len(records)} 条记录到 {table_name}")

        session.commit()

    print(f"\n{'='*60}")
    print(f"已在 {DATABASE_PATH} 创建 SQLite 数据库")


def main() -> None:
    """Main entry point function."""
    print("="*60)
    print("AI 合规审计系统 - 假数据生成器")
    print("="*60 + "\n")
    print(f"时间锚点 NOW = {NOW.isoformat()}")
    print(f"（所有日期相对此锚点向过去回推）\n")

    print("阶段 1: 生成 TSV 文件...\n")
    dataframes = generate_all_tsv()

    print("\n阶段 2: 创建 SQLite 数据库...\n")
    create_sqlite_database(dataframes)

    print("\n" + "="*60)
    print("全部完成！")
    print("="*60)

    # Summary
    total_rows = sum(len(df) for df in dataframes.values())
    print(f"\n汇总:")
    print(f"  表数量: {len(dataframes)}")
    print(f"  总行数: {total_rows}")
    print(f"  输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
