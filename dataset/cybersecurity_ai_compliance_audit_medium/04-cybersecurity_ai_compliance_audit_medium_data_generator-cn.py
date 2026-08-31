"""
网络安全 - AI合规审计系统 假数据生成器
复杂度: Medium
生成工具: Fake Data Generator Agent

业务背景:
本数据集模拟企业级 AI 合规审计系统，面向在生产环境部署 AI/ML 模型的组织。
系统支持 NIST AI RMF、GDPR、HIPAA 等合规框架的追踪，AI 模型风险评估，
安全事件管理，以及整改行动工作流。适用于 AI 安全工程师、合规审计师和 MLOps 团队。

时间锚点说明:
所有日期字段均相对 datetime.now() 动态生成（生成时刻为"今天"），
以避免数据集与 SQL 中 julianday('now') 之间因时间推移而失去区分度。
随机种子固定为 42，保证同一运行内的"相对偏移"可复现，但绝对日期会随运行日期变化。
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
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "cybersecurity_ai_compliance_audit_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 动态时间锚点：以"运行此脚本的时刻"为今天，所有日期向过去回推
NOW = datetime.now().replace(microsecond=0)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


def days_ago(low: int, high: int, with_time: bool = True) -> datetime:
    """返回今天向前 [low, high] 天范围内的随机 datetime（含小时分钟）"""
    delta_days = random.randint(low, high)
    if with_time:
        return NOW - timedelta(
            days=delta_days,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
    return NOW - timedelta(days=delta_days)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


class ComplianceFramework(Base):
    """合规框架，如 NIST AI RMF、GDPR、HIPAA 等"""
    __tablename__ = "compliance_framework"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class RiskCategory(Base):
    """AI 系统风险类别枚举"""
    __tablename__ = "risk_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    severity_weight: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class ControlStatus(Base):
    """控制措施状态枚举"""
    __tablename__ = "control_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    """系统用户，包括审计师、工程师和管理人员"""
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AIModel(Base):
    """AI/ML 模型注册和元数据"""
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
    """映射到框架的合规控制措施"""
    __tablename__ = "compliance_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    framework_id: Mapped[int] = mapped_column(Integer, ForeignKey("compliance_framework.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)


class RiskAssessment(Base):
    """AI 模型风险评估"""
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
    """模型 × 控制项的合规评估（M:N 桥接表，AI 合规审计的核心动作）

    用途：合规审计师为每个模型逐项评估每个适用控制项的符合性，留下评估结论、
    证据摘要、评估时间与下次复审日期。本表使"哪个模型在哪个控制项上是否合规"
    成为一等查询对象。"""
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
    """所有合规相关操作的审计日志"""
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
    """AI 系统相关的安全事件"""
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
    """安全事件和风险发现的整改措施"""
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
# 数据生成器
# ============================================================================

def gen_compliance_framework() -> pl.DataFrame:
    """生成合规框架参考数据"""
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
    """生成风险类别枚举"""
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
    """生成控制状态枚举"""
    data = [
        {"id": 1, "code": "PENDING", "name": "Pending Review", "is_terminal": False},
        {"id": 2, "code": "IN_PROGRESS", "name": "In Progress", "is_terminal": False},
        {"id": 3, "code": "COMPLETED", "name": "Completed", "is_terminal": True},
        {"id": 4, "code": "DEFERRED", "name": "Deferred", "is_terminal": False},
        {"id": 5, "code": "CANCELLED", "name": "Cancelled", "is_terminal": True},
    ]
    return pl.DataFrame(data)


def gen_user(n: int = 30) -> pl.DataFrame:
    """生成不同角色的系统用户

    created_at: 距今 60-730 天，覆盖 2 个月到 2 年的入职窗口
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
    """生成 AI 模型注册记录

    分布:
      - risk_tier: 加权 HIGH(30%), MEDIUM(35%), LOW(25%), CRITICAL(10%)
      - is_active: 85% true
      - last_audit_date: 50% 在 [0, 180] 天内（近期审计）, 30% 在 [181, 540] 天内（已过期）,
        20% 为 NULL（从未审计）。这样 Query 19（>180 天阈值）保留判别力。

    时序约束: created_at 严格在 owner.created_at 之后
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
    risk_tier_weights = [30, 35, 25, 10]  # 与 ER 文档声明一致

    data = []
    for i in range(1, n + 1):
        prefix = random.choice(model_prefixes)
        version = f"v{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 99)}"

        owner_id = random.choice(user_ids) if user_ids else random.randint(1, 30)
        owner_created = user_created_lookup.get(owner_id) if user_created_lookup else None

        # created_at: 30-540 天前，但必须晚于 owner.created_at
        created_at = days_ago(30, 540)
        if owner_created and created_at < owner_created:
            # 强制晚于 owner
            min_offset = (NOW - owner_created).days
            created_at = days_ago(30, max(31, min_offset - 1))

        # last_audit_date 分布（保证 Query 19 有判别力）:
        # 20% NULL（从未审计）; 在已审计的模型中, 模型足够老的优先变成 stale,
        # 否则只能是 recent。模型必须存在足够长时间才能积累过期审计。
        model_age_days = max(1, (NOW - created_at).days)
        if random.random() < 0.20:
            last_audit_date = None
        else:
            # 模型年龄 ≥ 220 天的有 50% 概率被标为 stale audit
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
    """生成合规控制措施"""
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

        # 根据框架生成控制 ID
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
    """生成 AI 模型风险评估记录

    assessed_at: 距今 0-365 天，但严格晚于所评估模型的 created_at
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
                # 评估时间至少在模型创建之后
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
    """生成模型 × 控制项的合规评估记录（M:N 桥接表）

    业务语义:
      - 合规审计师为每个适用控制项评估每个模型，记录符合性结论与证据摘要
      - (ai_model_id, control_id) 在 n 条记录内尽量保持唯一（不强制 unique 约束）
      - compliance_status 分布: COMPLIANT 50%, PARTIALLY_COMPLIANT 25%,
        NON_COMPLIANT 15%, NOT_APPLICABLE 10%
      - assessed_at 必须晚于模型创建时间
      - next_review_date 在 assessed_at 之后 90-365 天
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
        # 抽到唯一的 (model, control) 配对
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
                # 已经很难抽到新配对，提前结束（理论上 50*100=5000 远大于 n=300，不会触发）
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


# entity_type → 对应表的 id 上界（用于 audit_log.entity_id 与 entity_type 联动）
ENTITY_TYPE_MAX_ID = {
    "AI_MODEL": 50,
    "RISK_ASSESSMENT": 200,
    "COMPLIANCE_CONTROL": 100,
    "SECURITY_INCIDENT": 80,
    "REMEDIATION_ACTION": 120,
    "USER": 30,
    "MODEL_CONTROL_ASSESSMENT": 300,
    "REPORT": 50,  # 没有实体表，作为合成 ID 范围
}


def gen_audit_log(n: int = 500, user_ids: list[int] = None, model_ids: list[int] = None,
                  user_created_lookup: dict[int, datetime] = None,
                  model_created_lookup: dict[int, datetime] = None) -> pl.DataFrame:
    """生成审计日志条目

    时序约束:
      - timestamp 必须晚于 user.created_at（操作用户已存在）
      - 若 ai_model_id 非空，必须晚于 ai_model.created_at

    多态字段 entity_id:
      - 根据 entity_type 选择合理的 id 范围（仍无 FK 约束，但保证可 join 回真实记录）
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
        # 70% 的日志与 AI 模型相关
        model_id = random.choice(model_ids) if model_ids and random.random() > 0.3 else None

        # 计算最早允许的时间：必须晚于 user.created_at 与 model.created_at
        earliest = NOW - timedelta(days=400)  # 兜底默认窗口
        if user_created_lookup and user_id in user_created_lookup:
            earliest = max(earliest, user_created_lookup[user_id])
        if model_id and model_created_lookup and model_id in model_created_lookup:
            earliest = max(earliest, model_created_lookup[model_id])

        # 在 [earliest+1day, NOW] 之间均匀采样
        window_days = max(1, (NOW - earliest).days - 1)
        timestamp = earliest + timedelta(
            days=random.randint(1, window_days),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        # entity_id 与 entity_type 联动
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
    """生成安全事件记录

    分布:
      - severity: 加权 CRITICAL(10%), HIGH(25%), MEDIUM(40%), LOW(25%)（与 ER 文档一致）
    时序约束:
      - reported_at 严格晚于 ai_model.created_at
    标识符:
      - incident_id 中的年份取自 reported_at.year（修复年份硬编码 2023）
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
        None,  # 部分事件可能尚未确定根因
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
            # 年份取自 reported_at，跨年事件不再被错误标注为 2023
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
    """生成整改措施记录

    互斥规则: incident_id 与 risk_assessment_id 严格互斥（恰好一个为非空，另一个为 NULL）

    时序约束:
      - 整改是被事件或风险评估触发的，所以 created_at 必须晚于上游：
        * 关联事件时: created_at > incident.reported_at + 1~30 天
        * 关联评估时: created_at > risk_assessment.assessed_at + 1~30 天
      - completed_at 不可超过 NOW（"未来已完成"在逻辑上不可能）
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
        # 60% 关联事件，40% 关联风险评估（互斥）
        linked_to_incident = random.random() > 0.4

        template = random.choice(action_templates)
        measure = random.choice(measures)

        # 派生 created_at：从上游触发对象时间往后推 1-30 天
        # 若关联事件: upstream = incident.reported_at; 否则: upstream = risk_assessment.assessed_at
        incident_id = random.choice(incident_ids) if linked_to_incident and incident_ids else None
        assessment_id = random.choice(assessment_ids) if not linked_to_incident and assessment_ids else None

        upstream_time: datetime | None = None
        if incident_id is not None and incident_reported_lookup is not None:
            upstream_time = incident_reported_lookup.get(incident_id)
        elif assessment_id is not None and assessment_assessed_lookup is not None:
            upstream_time = assessment_assessed_lookup.get(assessment_id)

        if upstream_time is not None:
            # created_at = upstream_time + 1~30 天，但不可超过 NOW
            offset_days = random.randint(1, 30)
            tentative = upstream_time + timedelta(
                days=offset_days,
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            if tentative > NOW:
                # 上游事件本身就接近今天，则 created_at 落在 [upstream, NOW] 之间
                max_offset = max(1, (NOW - upstream_time).days)
                created_at = upstream_time + timedelta(
                    hours=random.randint(1, max(1, max_offset * 24 - 1))
                )
            else:
                created_at = tentative
            # 二次防线：上游极接近 NOW 时，前面的 hour 累加仍可能溢出，统一夹回到
            # NOW 之前的随机时刻（而非精确 NOW），避免多条记录堆积到完全相同时间戳
            if created_at > NOW:
                created_at = NOW - timedelta(
                    minutes=random.randint(1, 59),
                    seconds=random.randint(0, 59),
                )
        else:
            # 兜底：无上游 lookup 时退回原行为
            created_at = days_ago(0, 300)

        due_date = created_at + timedelta(days=random.randint(7, 90))

        status_id = random.choice(status_ids) if status_ids else random.randint(1, 5)
        completed_at = None
        if status_id == 3:  # COMPLETED
            # completed_at = created_at + 1~60 天，但不可超过 NOW（未来完成时间不合逻辑）
            max_offset_days = max(1, (NOW - created_at).days)
            completion_offset = random.randint(1, min(60, max_offset_days))
            completed_at = created_at + timedelta(
                days=completion_offset,
                hours=random.randint(0, 23),
            )
            # 双保险：极少数边界情况夹回到 NOW 之前的随机时刻
            # 注意：不能夹回到精确 NOW —— 若多条 remediation 触发这条分支，
            # 它们的 completed_at 会全部落到完全相同的一秒，造成视觉异常
            if completed_at > NOW:
                completed_at = NOW - timedelta(
                    hours=random.randint(1, 23),
                    minutes=random.randint(0, 59),
                )
            # 同时保证 completed_at > created_at（极端边界下两者都接近 NOW 时）
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
# 核心函数（幂等操作）
# ============================================================================

def generate_all_tsv() -> dict[str, pl.DataFrame]:
    """生成所有 TSV 文件。幂等操作：先删除已存在的文件"""
    # 确保数据目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 删除已存在的 TSV 文件
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    # 按拓扑顺序生成数据（无外键依赖的表优先）
    dataframes = {}

    # Level 0: 无依赖
    print("生成 Level 0 表（无依赖）...")
    dataframes["compliance_framework"] = gen_compliance_framework()
    dataframes["risk_category"] = gen_risk_category()
    dataframes["control_status"] = gen_control_status()
    dataframes["user"] = gen_user(30)

    # 提取 ID 与时间戳用于外键引用与时序对齐
    user_ids = dataframes["user"]["id"].to_list()
    framework_ids = dataframes["compliance_framework"]["id"].to_list()
    risk_cat_ids = dataframes["risk_category"]["id"].to_list()
    status_ids = dataframes["control_status"]["id"].to_list()
    user_created_lookup = dict(zip(
        dataframes["user"]["id"].to_list(),
        dataframes["user"]["created_at"].to_list(),
    ))

    # Level 1: 依赖 Level 0
    print("生成 Level 1 表...")
    dataframes["ai_model"] = gen_ai_model(50, user_ids, user_created_lookup)
    dataframes["compliance_control"] = gen_compliance_control(100, framework_ids)

    model_ids = dataframes["ai_model"]["id"].to_list()
    control_ids = dataframes["compliance_control"]["id"].to_list()
    model_created_lookup = dict(zip(
        dataframes["ai_model"]["id"].to_list(),
        dataframes["ai_model"]["created_at"].to_list(),
    ))

    # Level 2: 依赖 Level 1
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

    # 构造上游时间 lookup，用于 remediation_action 时序对齐：
    #   - 关联事件时, created_at 必须晚于 incident.reported_at
    #   - 关联评估时, created_at 必须晚于 risk_assessment.assessed_at
    incident_reported_lookup = dict(zip(
        dataframes["security_incident"]["id"].to_list(),
        dataframes["security_incident"]["reported_at"].to_list(),
    ))
    assessment_assessed_lookup = dict(zip(
        dataframes["risk_assessment"]["id"].to_list(),
        dataframes["risk_assessment"]["assessed_at"].to_list(),
    ))

    # Level 3: 依赖 Level 2
    print("生成 Level 3 表...")
    dataframes["remediation_action"] = gen_remediation_action(
        120, incident_ids, assessment_ids, control_ids, user_ids, status_ids,
        incident_reported_lookup=incident_reported_lookup,
        assessment_assessed_lookup=assessment_assessed_lookup,
    )

    # 按顺序保存为 TSV 文件
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
    """从生成的数据创建 SQLite 数据库。幂等操作：先删除已存在的数据库"""
    # 删除已存在的数据库
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 表名到 ORM 类的映射
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

    # 加载顺序（拓扑排序）
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
                # 将空字符串转换为 None
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
    """主入口函数"""
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

    # 汇总
    total_rows = sum(len(df) for df in dataframes.values())
    print(f"\n汇总:")
    print(f"  表数量: {len(dataframes)}")
    print(f"  总行数: {total_rows}")
    print(f"  输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
