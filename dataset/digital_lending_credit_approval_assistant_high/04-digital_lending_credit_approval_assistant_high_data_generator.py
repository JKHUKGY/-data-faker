"""
Northpeak Lending AI Credit Approval Assistant Fake Data Generator
Complexity: High (18 tables, ~18,000+ rows)
Tooling: Fake Data Generator Agent
Market: North America (United States), currency USD

Business context:
This dataset simulates the intelligent credit approval system of Northpeak Lending,
a North American digital consumer lender. After receiving a loan application, the
AI Agent automatically pulls the applicant's credit report, evaluates the risk
rules, looks up similar historical cases, and ultimately produces an approval
recommendation for the human underwriter to consider. For full business context,
see the companion business_context document.

Demo uses:
- Text-to-SQL: an underwriter can ask in natural language, "Which loan products
  had the highest decline rate in the past 30 days?"
- Agent: an LLM Agent can call tools to query the database, analyze risk factors,
  and generate recommendations
- RAG: similar historical cases and risk policy documents can be retrieved

Time anchor:
The generator uses relative time (looking back about 18 months from "now" at run
time); there is no fixed REFERENCE_DATE constant, so the window shifts whenever
the script is re-run across days.

Business traps and simplifications (see the er_document for details):
- Two definitions of approval rate: approval_decision.is_approved is ~60%, while
  the application_status definition (APPROVED plus FUNDED) is ~50%; the two
  tables are generated independently and are not forced to agree.
- Every application has one approval_decision record, including those still in
  PENDING / IN_REVIEW.
- Rule triggering is independently sampled at a fixed 15% probability with no
  link to the application's actual risk, so rule effectiveness is essentially
  random (this is the anti-example used in query Q20).
- DTI is uniformly distributed from 15% to 55%, and the approval-history status
  transitions are randomly generated; both are demo-only simplifications.
"""

from __future__ import annotations
import os
import shutil
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Callable, List, Optional
import random
from decimal import Decimal

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, Text, Date, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# Configuration
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "digital_lending_credit_approval_assistant_high.sqlite"
FAKER_LOCALE = "en_US"  # Use the English locale to match Northpeak's North American (U.S.) market scenario
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# SQLAlchemy ORM models
# ============================================================================
class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


# ============= Enum tables =============

class ApplicationStatus(Base):
    """Loan application status"""
    __tablename__ = "application_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text)


class EmploymentType(Base):
    """Employment type"""
    __tablename__ = "employment_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class LoanPurpose(Base):
    """Loan purpose"""
    __tablename__ = "loan_purpose"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text)


class DecisionType(Base):
    """Decision type"""
    __tablename__ = "decision_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_auto: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RiskLevel(Base):
    """Risk level"""
    __tablename__ = "risk_level"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    score_min: Mapped[int] = mapped_column(Integer, nullable=False)
    score_max: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(20))


# ============= Core business tables =============

class LoanProduct(Base):
    """Loan product"""
    __tablename__ = "loan_product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    min_amount: Mapped[float] = mapped_column(Float, nullable=False)
    max_amount: Mapped[float] = mapped_column(Float, nullable=False)
    min_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    max_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    base_interest_rate: Mapped[float] = mapped_column(Float, nullable=False)  # Annual rate %
    min_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Applicant(Base):
    """Applicant"""
    __tablename__ = "applicant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ssn_last4: Mapped[str] = mapped_column(String(4), nullable=False)  # Last 4 digits of SSN
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CreditReport(Base):
    """Credit report (from a credit bureau)"""
    __tablename__ = "credit_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("applicant.id"), nullable=False)
    bureau: Mapped[str] = mapped_column(String(20), nullable=False)  # Experian/Equifax/TransUnion
    fico_score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_accounts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_accounts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_credit_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    utilization_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100%
    delinquent_accounts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    public_records: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Bankruptcies/judgments/etc.
    inquiries_last_6mo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oldest_account_age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # Raw JSON-formatted data


class EmploymentInfo(Base):
    """Employment information"""
    __tablename__ = "employment_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("applicant.id"), nullable=False)
    employment_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("employment_type.id"), nullable=False)
    employer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    annual_income: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_income: Mapped[float] = mapped_column(Float, nullable=False)
    employment_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    verification_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # paystub/employer_call/bank_statement


class LoanApplication(Base):
    """Loan application (core table)"""
    __tablename__ = "loan_application"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    applicant_id: Mapped[int] = mapped_column(Integer, ForeignKey("applicant.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_product.id"), nullable=False)
    purpose_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_purpose.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("application_status.id"), nullable=False)
    requested_amount: Mapped[float] = mapped_column(Float, nullable=False)
    requested_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    approved_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_payment: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_income_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)  # DTI
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)  # web/mobile/branch/partner
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    funded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ============= Approval workflow tables =============

class RiskRule(Base):
    """Risk rule library"""
    __tablename__ = "risk_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # credit/income/fraud/compliance
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # info/warning/hard_stop
    condition_sql: Mapped[str | None] = mapped_column(Text, nullable=True)  # SQL condition expression
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)  # flag/reduce_amount/reject
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RuleEvaluation(Base):
    """Rule evaluation record"""
    __tablename__ = "rule_evaluation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_rule.id"), nullable=False)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    trigger_value: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Actual value at trigger time
    threshold_value: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Threshold
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ApprovalDecision(Base):
    """Approval decision"""
    __tablename__ = "approval_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    decision_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("decision_type.id"), nullable=False)
    risk_level_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_level.id"), nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-1000
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decline_codes: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Comma-separated decline codes
    reviewer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Human underwriter ID
    ai_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI recommendation text
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # AI confidence 0-1
    decision_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ApprovalHistory(Base):
    """Approval status transition history"""
    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    from_status_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("application_status.id"), nullable=True)
    to_status_id: Mapped[int] = mapped_column(Integer, ForeignKey("application_status.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # system/agent/human
    actor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ============= Extension tables =============

class SimilarCase(Base):
    """Similar case library (used by the Agent to query historical references)"""
    __tablename__ = "similar_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    similar_application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1
    matching_factors: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: matching factors
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Document(Base):
    """Supporting document"""
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)  # income_proof/id_card/bank_statement
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # pending/verified/rejected
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FraudFlag(Base):
    """Fraud flag"""
    __tablename__ = "fraud_flag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("loan_application.id"), nullable=False)
    flag_type: Mapped[str] = mapped_column(String(50), nullable=False)  # identity/income/address/device
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # low/medium/high/critical
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-formatted evidence
    is_resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    """Audit log"""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # application/applicant/decision
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create/update/delete/view
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # system/agent/human/api
    actor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ============================================================================
# Data generators
# ============================================================================

US_STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
             "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
             "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
             "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
             "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

CREDIT_BUREAUS = ["Experian", "Equifax", "TransUnion"]
CHANNELS = ["web", "mobile", "branch", "partner"]
VERIFICATION_METHODS = ["paystub", "employer_call", "bank_statement", "tax_return"]
DOC_TYPES = ["income_proof", "id_card", "bank_statement", "tax_return", "employment_letter", "utility_bill"]
FRAUD_TYPES = ["identity", "income", "address", "device", "velocity", "synthetic_id"]


def gen_application_status() -> pl.DataFrame:
    """Generate the application status enum"""
    records = [
        {"id": 1, "code": "PENDING", "name": "Pending Review", "description": "Application submitted, awaiting initial review"},
        {"id": 2, "code": "IN_REVIEW", "name": "In Review", "description": "Application is being reviewed by underwriter"},
        {"id": 3, "code": "APPROVED", "name": "Approved", "description": "Application approved, pending funding"},
        {"id": 4, "code": "DECLINED", "name": "Declined", "description": "Application declined"},
        {"id": 5, "code": "CANCELLED", "name": "Cancelled", "description": "Application cancelled by applicant"},
        {"id": 6, "code": "FUNDED", "name": "Funded", "description": "Loan has been funded and disbursed"},
        {"id": 7, "code": "EXPIRED", "name": "Expired", "description": "Application expired due to inactivity"},
    ]
    return pl.DataFrame(records)


def gen_employment_type() -> pl.DataFrame:
    """Generate the employment type enum"""
    records = [
        {"id": 1, "code": "FULL_TIME", "name": "Full-time Employee"},
        {"id": 2, "code": "PART_TIME", "name": "Part-time Employee"},
        {"id": 3, "code": "SELF_EMPLOYED", "name": "Self-employed"},
        {"id": 4, "code": "CONTRACTOR", "name": "Contract/Freelance"},
        {"id": 5, "code": "RETIRED", "name": "Retired"},
        {"id": 6, "code": "UNEMPLOYED", "name": "Unemployed"},
        {"id": 7, "code": "STUDENT", "name": "Student"},
    ]
    return pl.DataFrame(records)


def gen_loan_purpose() -> pl.DataFrame:
    """Generate the loan purpose enum"""
    records = [
        {"id": 1, "code": "HOME_PURCHASE", "name": "Home Purchase", "description": "Buying a primary residence"},
        {"id": 2, "code": "HOME_REFINANCE", "name": "Home Refinance", "description": "Refinancing existing mortgage"},
        {"id": 3, "code": "AUTO_PURCHASE", "name": "Auto Purchase", "description": "Buying a new or used vehicle"},
        {"id": 4, "code": "AUTO_REFINANCE", "name": "Auto Refinance", "description": "Refinancing existing auto loan"},
        {"id": 5, "code": "DEBT_CONSOLIDATION", "name": "Debt Consolidation", "description": "Consolidating multiple debts"},
        {"id": 6, "code": "CREDIT_CARD_PAYOFF", "name": "Credit Card Payoff", "description": "Paying off credit card balances"},
        {"id": 7, "code": "HOME_IMPROVEMENT", "name": "Home Improvement", "description": "Home renovation or repair"},
        {"id": 8, "code": "MEDICAL", "name": "Medical Expenses", "description": "Covering medical or dental costs"},
        {"id": 9, "code": "EDUCATION", "name": "Education", "description": "Paying for tuition or education costs"},
        {"id": 10, "code": "SMALL_BUSINESS", "name": "Small Business", "description": "Starting or expanding a business"},
        {"id": 11, "code": "OTHER", "name": "Other", "description": "Other personal use"},
    ]
    return pl.DataFrame(records)


def gen_decision_type() -> pl.DataFrame:
    """Generate the decision type enum"""
    records = [
        {"id": 1, "code": "AUTO_APPROVE", "name": "Auto-Approved", "is_auto": True},
        {"id": 2, "code": "AUTO_DECLINE", "name": "Auto-Declined", "is_auto": True},
        {"id": 3, "code": "MANUAL_APPROVE", "name": "Manual Approval", "is_auto": False},
        {"id": 4, "code": "MANUAL_DECLINE", "name": "Manual Decline", "is_auto": False},
        {"id": 5, "code": "REFERRED", "name": "Referred for Review", "is_auto": True},
    ]
    return pl.DataFrame(records)


def gen_risk_level() -> pl.DataFrame:
    """Generate the risk level enum"""
    records = [
        {"id": 1, "code": "VERY_LOW", "name": "Very Low Risk", "score_min": 0, "score_max": 200, "color": "green"},
        {"id": 2, "code": "LOW", "name": "Low Risk", "score_min": 201, "score_max": 400, "color": "lightgreen"},
        {"id": 3, "code": "MEDIUM", "name": "Medium Risk", "score_min": 401, "score_max": 600, "color": "yellow"},
        {"id": 4, "code": "HIGH", "name": "High Risk", "score_min": 601, "score_max": 800, "color": "orange"},
        {"id": 5, "code": "VERY_HIGH", "name": "Very High Risk", "score_min": 801, "score_max": 1000, "color": "red"},
    ]
    return pl.DataFrame(records)


def gen_loan_product() -> pl.DataFrame:
    """Generate loan products"""
    records = [
        {"id": 1, "code": "MORTGAGE_30Y", "name": "30-Year Fixed Mortgage", "description": "Traditional 30-year fixed-rate home loan",
         "min_amount": 50000, "max_amount": 2000000, "min_term_months": 360, "max_term_months": 360, "base_interest_rate": 6.5, "min_credit_score": 620, "is_active": True},
        {"id": 2, "code": "MORTGAGE_15Y", "name": "15-Year Fixed Mortgage", "description": "15-year fixed-rate home loan with lower rate",
         "min_amount": 50000, "max_amount": 1500000, "min_term_months": 180, "max_term_months": 180, "base_interest_rate": 5.75, "min_credit_score": 660, "is_active": True},
        {"id": 3, "code": "AUTO_NEW", "name": "New Auto Loan", "description": "Financing for new vehicle purchases",
         "min_amount": 5000, "max_amount": 100000, "min_term_months": 24, "max_term_months": 84, "base_interest_rate": 5.99, "min_credit_score": 600, "is_active": True},
        {"id": 4, "code": "AUTO_USED", "name": "Used Auto Loan", "description": "Financing for used vehicle purchases",
         "min_amount": 3000, "max_amount": 75000, "min_term_months": 24, "max_term_months": 72, "base_interest_rate": 7.49, "min_credit_score": 580, "is_active": True},
        {"id": 5, "code": "PERSONAL", "name": "Personal Loan", "description": "Unsecured personal loan for various purposes",
         "min_amount": 1000, "max_amount": 50000, "min_term_months": 12, "max_term_months": 60, "base_interest_rate": 9.99, "min_credit_score": 640, "is_active": True},
        {"id": 6, "code": "PERSONAL_PRIME", "name": "Prime Personal Loan", "description": "Lower rate personal loan for excellent credit",
         "min_amount": 5000, "max_amount": 100000, "min_term_months": 24, "max_term_months": 84, "base_interest_rate": 7.49, "min_credit_score": 720, "is_active": True},
        {"id": 7, "code": "HELOC", "name": "Home Equity Line of Credit", "description": "Revolving credit secured by home equity",
         "min_amount": 10000, "max_amount": 500000, "min_term_months": 60, "max_term_months": 240, "base_interest_rate": 8.25, "min_credit_score": 680, "is_active": True},
        {"id": 8, "code": "DEBT_CONSOL", "name": "Debt Consolidation Loan", "description": "Fixed-rate loan to consolidate multiple debts",
         "min_amount": 5000, "max_amount": 75000, "min_term_months": 24, "max_term_months": 60, "base_interest_rate": 10.99, "min_credit_score": 620, "is_active": True},
    ]
    for r in records:
        r["created_at"] = fake.date_time_between(start_date="-3y", end_date="-1y").isoformat()
    return pl.DataFrame(records)


def gen_applicants(n: int = 500) -> pl.DataFrame:
    """Generate applicants"""
    records = []
    for i in range(1, n + 1):
        dob = fake.date_of_birth(minimum_age=21, maximum_age=75)
        records.append({
            "id": i,
            "ssn_last4": str(random.randint(1000, 9999)),
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(),
            "phone": fake.phone_number(),
            "date_of_birth": dob.isoformat(),
            "address_line1": fake.street_address(),
            "address_line2": fake.secondary_address() if random.random() < 0.2 else None,
            "city": fake.city(),
            "state": random.choice(US_STATES),
            "zip_code": fake.zipcode(),
            "created_at": fake.date_time_between(start_date="-2y", end_date="now").isoformat(),
        })
    fake.unique.clear()
    return pl.DataFrame(records)


def gen_credit_reports(applicant_ids: List[int]) -> pl.DataFrame:
    """Generate credit reports (1-3 per applicant from different bureaus)"""
    records = []
    record_id = 1
    for app_id in applicant_ids:
        # Randomly pick 1-3 credit bureaus
        bureaus = random.sample(CREDIT_BUREAUS, k=random.randint(1, 3))
        base_score = random.randint(520, 820)

        for bureau in bureaus:
            score = base_score + random.randint(-30, 30)
            score = max(300, min(850, score))  # FICO range

            total_accounts = random.randint(3, 25)
            open_accounts = random.randint(1, total_accounts)
            total_limit = random.uniform(5000, 150000)
            total_balance = total_limit * random.uniform(0.05, 0.85)

            records.append({
                "id": record_id,
                "applicant_id": app_id,
                "bureau": bureau,
                "fico_score": score,
                "total_accounts": total_accounts,
                "open_accounts": open_accounts,
                "total_balance": round(total_balance, 2),
                "total_credit_limit": round(total_limit, 2),
                "utilization_ratio": round((total_balance / total_limit) * 100, 1),
                "delinquent_accounts": random.choices([0, 1, 2, 3], weights=[70, 20, 7, 3])[0],
                "public_records": random.choices([0, 1, 2], weights=[90, 8, 2])[0],
                "inquiries_last_6mo": random.choices([0, 1, 2, 3, 4, 5], weights=[30, 30, 20, 10, 7, 3])[0],
                "oldest_account_age_months": random.randint(12, 300),
                "report_date": fake.date_time_between(start_date="-1y", end_date="now").isoformat(),
                "raw_data": None,  # Simplified handling
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_employment_info(applicant_ids: List[int], employment_type_ids: List[int]) -> pl.DataFrame:
    """Generate employment information"""
    records = []
    JOB_TITLES = ["Software Engineer", "Manager", "Analyst", "Director", "Sales Representative",
                  "Teacher", "Nurse", "Accountant", "Marketing Specialist", "Project Manager",
                  "Data Scientist", "Product Manager", "Business Analyst", "Consultant", "Designer"]

    for i, app_id in enumerate(applicant_ids, 1):
        emp_type = random.choices(employment_type_ids, weights=[50, 10, 15, 10, 10, 3, 2])[0]

        if emp_type in [5, 6, 7]:  # Retired / Unemployed / Student
            annual_income = random.uniform(0, 40000)
            employer_name = None
            job_title = None
            start_date = None
        else:
            annual_income = random.uniform(35000, 350000)
            employer_name = fake.company()
            job_title = random.choice(JOB_TITLES)
            start_date = fake.date_between(start_date="-20y", end_date="-1m").isoformat()

        is_verified = random.random() < 0.7

        records.append({
            "id": i,
            "applicant_id": app_id,
            "employment_type_id": emp_type,
            "employer_name": employer_name,
            "job_title": job_title,
            "annual_income": round(annual_income, 2),
            "monthly_income": round(annual_income / 12, 2),
            "employment_start_date": start_date,
            "is_verified": is_verified,
            "verification_date": fake.date_time_between(start_date="-6m", end_date="now").isoformat() if is_verified else None,
            "verification_method": random.choice(VERIFICATION_METHODS) if is_verified else None,
        })
    return pl.DataFrame(records)


def gen_risk_rules() -> pl.DataFrame:
    """Generate the risk rule library"""
    records = [
        # Credit-category rules
        {"id": 1, "rule_code": "CREDIT_SCORE_MIN", "name": "Minimum Credit Score Check",
         "description": "Applicant must meet minimum credit score for the product",
         "category": "credit", "severity": "hard_stop", "condition_sql": "fico_score < product.min_credit_score", "action": "reject", "is_active": True, "version": 1},
        {"id": 2, "rule_code": "CREDIT_UTIL_HIGH", "name": "High Credit Utilization Warning",
         "description": "Credit utilization above 80% indicates high risk",
         "category": "credit", "severity": "warning", "condition_sql": "utilization_ratio > 80", "action": "flag", "is_active": True, "version": 1},
        {"id": 3, "rule_code": "DELINQUENT_ACCOUNTS", "name": "Delinquent Accounts Check",
         "description": "Multiple delinquent accounts in credit history",
         "category": "credit", "severity": "warning", "condition_sql": "delinquent_accounts >= 2", "action": "flag", "is_active": True, "version": 1},
        {"id": 4, "rule_code": "RECENT_INQUIRIES", "name": "Excessive Recent Inquiries",
         "description": "Too many credit inquiries in last 6 months",
         "category": "credit", "severity": "warning", "condition_sql": "inquiries_last_6mo > 5", "action": "reduce_amount", "is_active": True, "version": 1},
        {"id": 5, "rule_code": "THIN_FILE", "name": "Thin Credit File",
         "description": "Limited credit history (less than 3 accounts or 2 years)",
         "category": "credit", "severity": "info", "condition_sql": "total_accounts < 3 OR oldest_account_age_months < 24", "action": "flag", "is_active": True, "version": 1},

        # Income-category rules
        {"id": 6, "rule_code": "DTI_MAX", "name": "Maximum Debt-to-Income Ratio",
         "description": "DTI must not exceed 43% for qualified mortgages",
         "category": "income", "severity": "hard_stop", "condition_sql": "debt_to_income_ratio > 43", "action": "reject", "is_active": True, "version": 1},
        {"id": 7, "rule_code": "DTI_WARNING", "name": "High DTI Warning",
         "description": "DTI above 35% warrants additional review",
         "category": "income", "severity": "warning", "condition_sql": "debt_to_income_ratio > 35", "action": "flag", "is_active": True, "version": 1},
        {"id": 8, "rule_code": "INCOME_VERIFY", "name": "Income Verification Required",
         "description": "Income must be verified for loans above threshold",
         "category": "income", "severity": "hard_stop", "condition_sql": "requested_amount > 50000 AND NOT employment.is_verified", "action": "flag", "is_active": True, "version": 1},
        {"id": 9, "rule_code": "EMPLOYMENT_TENURE", "name": "Minimum Employment Tenure",
         "description": "At least 6 months at current employer recommended",
         "category": "income", "severity": "info", "condition_sql": "DATEDIFF(NOW(), employment_start_date) < 180", "action": "flag", "is_active": True, "version": 1},

        # Fraud-category rules
        {"id": 10, "rule_code": "VELOCITY_CHECK", "name": "Application Velocity Check",
         "description": "Multiple applications from same IP in 24 hours",
         "category": "fraud", "severity": "warning", "condition_sql": "ip_application_count_24h > 3", "action": "flag", "is_active": True, "version": 1},
        {"id": 11, "rule_code": "DEVICE_FRAUD", "name": "Known Fraud Device",
         "description": "Device fingerprint associated with previous fraud",
         "category": "fraud", "severity": "hard_stop", "condition_sql": "device_fingerprint IN known_fraud_devices", "action": "reject", "is_active": True, "version": 1},
        {"id": 12, "rule_code": "ADDRESS_MISMATCH", "name": "Address Mismatch",
         "description": "Application address doesn't match credit report",
         "category": "fraud", "severity": "warning", "condition_sql": "applicant.state != credit_report.state", "action": "flag", "is_active": True, "version": 1},
        {"id": 13, "rule_code": "SYNTHETIC_ID", "name": "Synthetic Identity Detection",
         "description": "Credit profile indicates potential synthetic identity",
         "category": "fraud", "severity": "hard_stop", "condition_sql": "synthetic_id_score > 0.8", "action": "reject", "is_active": True, "version": 1},

        # Compliance-category rules
        {"id": 14, "rule_code": "AGE_MIN", "name": "Minimum Age Requirement",
         "description": "Applicant must be at least 18 years old",
         "category": "compliance", "severity": "hard_stop", "condition_sql": "DATEDIFF(NOW(), date_of_birth) / 365 < 18", "action": "reject", "is_active": True, "version": 1},
        {"id": 15, "rule_code": "AMOUNT_RANGE", "name": "Loan Amount Within Product Range",
         "description": "Requested amount must be within product limits",
         "category": "compliance", "severity": "hard_stop", "condition_sql": "requested_amount < product.min_amount OR requested_amount > product.max_amount", "action": "reject", "is_active": True, "version": 1},
        {"id": 16, "rule_code": "PUBLIC_RECORDS", "name": "Public Records Check",
         "description": "Recent bankruptcy or judgment on file",
         "category": "compliance", "severity": "hard_stop", "condition_sql": "public_records > 0", "action": "reject", "is_active": True, "version": 2},
    ]
    now = datetime.utcnow()
    for r in records:
        r["created_at"] = (now - timedelta(days=random.randint(100, 500))).isoformat()
        r["updated_at"] = (now - timedelta(days=random.randint(0, 99))).isoformat()
    return pl.DataFrame(records)


def gen_loan_applications(applicant_ids: List[int], product_ids: List[int],
                          purpose_ids: List[int], status_ids: List[int], n: int = 800) -> pl.DataFrame:
    """Generate loan applications"""
    records = []

    # Product-purpose mapping (logical consistency)
    product_purpose_map = {
        1: [1, 2],      # MORTGAGE_30Y -> home purchase / refinance
        2: [1, 2],      # MORTGAGE_15Y
        3: [3],         # AUTO_NEW
        4: [3, 4],      # AUTO_USED
        5: [5, 6, 7, 8, 9, 10, 11],  # PERSONAL -> various purposes
        6: [5, 6, 7, 11],  # PERSONAL_PRIME
        7: [2, 7, 11],     # HELOC
        8: [5, 6],         # DEBT_CONSOL
    }

    # Product amount ranges
    product_amounts = {
        1: (100000, 750000),
        2: (100000, 500000),
        3: (15000, 65000),
        4: (8000, 40000),
        5: (3000, 35000),
        6: (10000, 75000),
        7: (25000, 200000),
        8: (10000, 50000),
    }

    for i in range(1, n + 1):
        product_id = random.choices(product_ids, weights=[15, 8, 20, 15, 25, 5, 7, 5])[0]
        purpose_id = random.choice(product_purpose_map.get(product_id, purpose_ids))

        amt_min, amt_max = product_amounts.get(product_id, (5000, 50000))
        requested_amount = round(random.uniform(amt_min, amt_max), 2)

        # Determine term based on product
        if product_id in [1]:
            term = 360
        elif product_id in [2]:
            term = 180
        elif product_id in [3, 4]:
            term = random.choice([36, 48, 60, 72])
        elif product_id in [7]:
            term = random.choice([60, 120, 180, 240])
        else:
            term = random.choice([24, 36, 48, 60])

        # Status distribution: most are completed
        status_id = random.choices(status_ids, weights=[5, 5, 40, 25, 10, 10, 5])[0]

        submitted_at = fake.date_time_between(start_date="-18m", end_date="now")

        # Decision time (only for decided applications)
        decision_at = None
        funded_at = None
        approved_amount = None
        approved_term = None
        approved_rate = None
        monthly_payment = None

        if status_id in [3, 4, 6]:  # Approved / Declined / Funded
            decision_at = submitted_at + timedelta(hours=random.randint(1, 72))
        if status_id in [3, 6]:  # Approved / Funded
            approved_amount = requested_amount * random.uniform(0.7, 1.0)
            approved_amount = round(approved_amount, 2)
            approved_term = term
            approved_rate = round(random.uniform(4.5, 18.0), 2)
            # Simplified monthly payment calculation
            monthly_rate = approved_rate / 100 / 12
            monthly_payment = round(approved_amount * monthly_rate * (1 + monthly_rate)**approved_term / ((1 + monthly_rate)**approved_term - 1), 2)
        if status_id == 6:  # Funded
            funded_at = decision_at + timedelta(days=random.randint(1, 7)) if decision_at else None

        dti = round(random.uniform(15, 55), 1)

        records.append({
            "id": i,
            "application_number": f"APP{submitted_at.strftime('%Y%m')}{str(i).zfill(6)}",
            "applicant_id": random.choice(applicant_ids),
            "product_id": product_id,
            "purpose_id": purpose_id,
            "status_id": status_id,
            "requested_amount": requested_amount,
            "requested_term_months": term,
            "approved_amount": approved_amount,
            "approved_term_months": approved_term,
            "approved_interest_rate": approved_rate,
            "monthly_payment": monthly_payment,
            "debt_to_income_ratio": dti,
            "channel": random.choices(CHANNELS, weights=[45, 35, 10, 10])[0],
            "ip_address": fake.ipv4(),
            "device_fingerprint": fake.uuid4()[:32],
            "submitted_at": submitted_at.isoformat(),
            "decision_at": decision_at.isoformat() if decision_at else None,
            "funded_at": funded_at.isoformat() if funded_at else None,
            "created_at": submitted_at.isoformat(),
        })
    return pl.DataFrame(records)


def gen_rule_evaluations(application_ids: List[int], rule_ids: List[int]) -> pl.DataFrame:
    """Generate rule evaluation records"""
    records = []
    record_id = 1

    for app_id in application_ids:
        # Each application is evaluated against 8-12 rules
        rules_to_eval = random.sample(rule_ids, k=min(len(rule_ids), random.randint(8, 12)))
        eval_time = fake.date_time_between(start_date="-18m", end_date="now")

        for rule_id in rules_to_eval:
            triggered = random.random() < 0.15  # 15% trigger rate

            records.append({
                "id": record_id,
                "application_id": app_id,
                "rule_id": rule_id,
                "triggered": triggered,
                "trigger_value": str(random.randint(300, 850)) if triggered else None,
                "threshold_value": str(random.randint(600, 700)) if triggered else None,
                "evaluated_at": eval_time.isoformat(),
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_approval_decisions(application_ids: List[int], decision_type_ids: List[int],
                           risk_level_ids: List[int]) -> pl.DataFrame:
    """Generate approval decisions"""
    records = []

    AI_RECOMMENDATIONS = [
        "Based on strong credit history and stable income, recommend approval at standard rates.",
        "Credit score meets threshold but high utilization suggests reduced approval amount.",
        "Income verification complete. DTI within acceptable range. Recommend standard approval.",
        "Multiple risk factors present. Recommend manual review before decision.",
        "Excellent credit profile with no adverse factors. Recommend prime rate approval.",
        "Application shows fraud risk indicators. Recommend decline pending investigation.",
        "Thin credit file but stable employment. Consider approval with conditions.",
        "High DTI ratio but excellent payment history. Recommend approval with monitoring.",
        "Recent inquiries suggest credit seeking behavior. Recommend reduced approval.",
        "Income inconsistent with stated employment. Flag for verification before approval.",
    ]

    DECLINE_REASONS = [
        "Credit score below minimum requirement for this product.",
        "Debt-to-income ratio exceeds policy maximum.",
        "Unable to verify stated income with documentation.",
        "Insufficient credit history to assess risk.",
        "Recent delinquencies indicate elevated default risk.",
        "Application flagged for potential fraud indicators.",
        "Public records (bankruptcy/judgment) on credit report.",
        "Employment tenure insufficient for loan amount requested.",
    ]

    for i, app_id in enumerate(application_ids, 1):
        is_approved = random.random() < 0.6  # 60% approval rate

        if is_approved:
            decision_type = random.choices([1, 3], weights=[70, 30])[0]  # Auto vs. manual approval
            risk_level = random.choices(risk_level_ids[:3], weights=[30, 50, 20])[0]
            risk_score = random.randint(100, 500)
            decline_codes = None
            decision_reason = random.choice(AI_RECOMMENDATIONS[:5])
        else:
            decision_type = random.choices([2, 4], weights=[60, 40])[0]  # Auto vs. manual decline
            risk_level = random.choices(risk_level_ids[2:], weights=[40, 40, 20])[0]
            risk_score = random.randint(500, 900)
            decline_codes = ",".join(random.sample(["CR01", "CR02", "IN01", "FR01", "CP01"], k=random.randint(1, 3)))
            decision_reason = random.choice(DECLINE_REASONS)

        records.append({
            "id": i,
            "application_id": app_id,
            "decision_type_id": decision_type,
            "risk_level_id": risk_level,
            "risk_score": risk_score,
            "is_approved": is_approved,
            "decision_reason": decision_reason,
            "decline_codes": decline_codes,
            "reviewer_id": f"UW{random.randint(1001, 1020)}" if decision_type in [3, 4] else None,
            "ai_recommendation": random.choice(AI_RECOMMENDATIONS),
            "ai_confidence": round(random.uniform(0.65, 0.98), 2),
            "decision_at": fake.date_time_between(start_date="-18m", end_date="now").isoformat(),
        })
    return pl.DataFrame(records)


def gen_approval_history(application_ids: List[int], status_ids: List[int]) -> pl.DataFrame:
    """Generate approval status transition history"""
    records = []
    record_id = 1

    ACTIONS = ["submit", "auto_review", "assign", "review", "approve", "decline", "fund", "cancel", "expire"]
    ACTOR_TYPES = ["system", "agent", "human"]

    for app_id in application_ids:
        # 2-5 transition records per application
        num_transitions = random.randint(2, 5)
        base_time = fake.date_time_between(start_date="-18m", end_date="-1d")

        prev_status = None
        for j in range(num_transitions):
            to_status = random.choice(status_ids[:5])

            records.append({
                "id": record_id,
                "application_id": app_id,
                "from_status_id": prev_status,
                "to_status_id": to_status,
                "action": random.choice(ACTIONS),
                "actor_type": random.choice(ACTOR_TYPES),
                "actor_id": f"ACT{random.randint(1, 100)}" if random.random() < 0.7 else None,
                "notes": fake.sentence() if random.random() < 0.3 else None,
                "created_at": (base_time + timedelta(hours=j * random.randint(1, 24))).isoformat(),
            })
            prev_status = to_status
            record_id += 1
    return pl.DataFrame(records)


def gen_similar_cases(application_ids: List[int], sample_size: int = 1000) -> pl.DataFrame:
    """Generate the similar case library"""
    records = []

    MATCHING_FACTORS = [
        '{"factors": ["credit_score", "loan_amount", "dti"], "weights": [0.4, 0.3, 0.3]}',
        '{"factors": ["product_type", "employment", "income"], "weights": [0.5, 0.25, 0.25]}',
        '{"factors": ["purpose", "state", "credit_history"], "weights": [0.35, 0.3, 0.35]}',
        '{"factors": ["loan_amount", "term", "rate"], "weights": [0.4, 0.3, 0.3]}',
    ]

    for i in range(1, sample_size + 1):
        source = random.choice(application_ids)
        similar = random.choice([x for x in application_ids if x != source])

        records.append({
            "id": i,
            "source_application_id": source,
            "similar_application_id": similar,
            "similarity_score": round(random.uniform(0.7, 0.99), 3),
            "matching_factors": random.choice(MATCHING_FACTORS),
            "computed_at": fake.date_time_between(start_date="-1y", end_date="now").isoformat(),
        })
    return pl.DataFrame(records)


def gen_documents(application_ids: List[int]) -> pl.DataFrame:
    """Generate supporting documents"""
    records = []
    record_id = 1

    MIME_TYPES = ["application/pdf", "image/jpeg", "image/png"]
    VERIFICATION_STATUS = ["pending", "verified", "rejected"]

    for app_id in application_ids:
        # 1-4 documents per application
        num_docs = random.randint(1, 4)
        doc_types = random.sample(DOC_TYPES, k=num_docs)

        for doc_type in doc_types:
            uploaded = fake.date_time_between(start_date="-18m", end_date="now")
            status = random.choices(VERIFICATION_STATUS, weights=[20, 70, 10])[0]

            records.append({
                "id": record_id,
                "application_id": app_id,
                "doc_type": doc_type,
                "file_name": f"{doc_type}_{app_id}_{record_id}.{random.choice(['pdf', 'jpg', 'png'])}",
                "file_size_bytes": random.randint(50000, 5000000),
                "mime_type": random.choice(MIME_TYPES),
                "ocr_extracted_text": fake.paragraph(nb_sentences=3) if random.random() < 0.6 else None,
                "verification_status": status,
                "uploaded_at": uploaded.isoformat(),
                "verified_at": (uploaded + timedelta(hours=random.randint(1, 48))).isoformat() if status != "pending" else None,
            })
            record_id += 1
    return pl.DataFrame(records)


def gen_fraud_flags(application_ids: List[int]) -> pl.DataFrame:
    """Generate fraud flags (only for a subset of applications)"""
    records = []
    record_id = 1

    # About 10% of applications have a fraud flag
    flagged_apps = random.sample(application_ids, k=int(len(application_ids) * 0.1))

    FLAG_DESCRIPTIONS = {
        "identity": "SSN mismatch with stated name or DOB",
        "income": "Stated income inconsistent with industry/position norms",
        "address": "Address linked to known fraud ring or PO Box",
        "device": "Device previously used in confirmed fraud case",
        "velocity": "Multiple applications from same identity within 24 hours",
        "synthetic_id": "Credit profile indicates potential synthetic identity",
    }

    SEVERITIES = ["low", "medium", "high", "critical"]

    for app_id in flagged_apps:
        flag_type = random.choice(FRAUD_TYPES)
        severity = random.choices(SEVERITIES, weights=[30, 40, 20, 10])[0]
        flagged_at = fake.date_time_between(start_date="-18m", end_date="now")
        is_resolved = random.random() < 0.6

        records.append({
            "id": record_id,
            "application_id": app_id,
            "flag_type": flag_type,
            "severity": severity,
            "description": FLAG_DESCRIPTIONS.get(flag_type, "Suspicious activity detected"),
            "evidence": f'{{"score": {random.uniform(0.6, 0.99):.2f}, "model": "fraud_v2"}}',
            "is_resolved": is_resolved,
            "resolution_notes": "Verified with applicant - false positive" if is_resolved else None,
            "flagged_at": flagged_at.isoformat(),
            "resolved_at": (flagged_at + timedelta(days=random.randint(1, 14))).isoformat() if is_resolved else None,
        })
        record_id += 1
    return pl.DataFrame(records)


def gen_audit_logs(application_ids: List[int], applicant_ids: List[int]) -> pl.DataFrame:
    """Generate audit logs"""
    records = []

    ACTIONS = ["create", "update", "view", "approve", "decline", "query", "export"]
    ACTOR_TYPES = ["system", "agent", "human", "api"]
    ENTITY_TYPES = ["application", "applicant", "decision", "document"]

    # Generate approximately 2000 log records
    for i in range(1, 2001):
        entity_type = random.choices(ENTITY_TYPES, weights=[50, 20, 20, 10])[0]

        if entity_type == "application":
            entity_id = random.choice(application_ids)
        elif entity_type == "applicant":
            entity_id = random.choice(applicant_ids)
        else:
            entity_id = random.randint(1, 500)

        records.append({
            "id": i,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": random.choice(ACTIONS),
            "actor_type": random.choices(ACTOR_TYPES, weights=[20, 30, 40, 10])[0],
            "actor_id": f"ACT{random.randint(1, 50)}",
            "old_value": None if random.random() < 0.6 else '{"status": "pending"}',
            "new_value": None if random.random() < 0.4 else '{"status": "approved"}',
            "ip_address": fake.ipv4(),
            "user_agent": fake.user_agent() if random.random() < 0.7 else None,
            "created_at": fake.date_time_between(start_date="-18m", end_date="now").isoformat(),
        })
    return pl.DataFrame(records)


# ============================================================================
# Core functions (idempotent operations)
# ============================================================================
def generate_all_tsv() -> dict:
    """Generate all TSV files. Idempotent: existing files are deleted first."""
    # Ensure the data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Delete existing TSV files
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    # Generate in topological order (tables without foreign-key dependencies first)
    print("Generating enum tables...")

    # 01-05: enum tables (no dependencies)
    df_app_status = gen_application_status()
    df_app_status.write_csv(DATA_DIR / "01_application_status.tsv", separator="\t")

    df_emp_type = gen_employment_type()
    df_emp_type.write_csv(DATA_DIR / "02_employment_type.tsv", separator="\t")

    df_loan_purpose = gen_loan_purpose()
    df_loan_purpose.write_csv(DATA_DIR / "03_loan_purpose.tsv", separator="\t")

    df_decision_type = gen_decision_type()
    df_decision_type.write_csv(DATA_DIR / "04_decision_type.tsv", separator="\t")

    df_risk_level = gen_risk_level()
    df_risk_level.write_csv(DATA_DIR / "05_risk_level.tsv", separator="\t")

    # 06-07: product and rule tables (no dependencies)
    print("Generating product and rule tables...")
    df_product = gen_loan_product()
    df_product.write_csv(DATA_DIR / "06_loan_product.tsv", separator="\t")

    df_rules = gen_risk_rules()
    df_rules.write_csv(DATA_DIR / "07_risk_rule.tsv", separator="\t")

    # 08: applicants
    print("Generating applicants...")
    df_applicant = gen_applicants(n=500)
    df_applicant.write_csv(DATA_DIR / "08_applicant.tsv", separator="\t")
    applicant_ids = df_applicant["id"].to_list()

    # 09: credit reports (depend on applicants)
    print("Generating credit reports...")
    df_credit = gen_credit_reports(applicant_ids)
    df_credit.write_csv(DATA_DIR / "09_credit_report.tsv", separator="\t")

    # 10: employment information (depends on applicants, employment_type)
    print("Generating employment info...")
    df_employment = gen_employment_info(applicant_ids, df_emp_type["id"].to_list())
    df_employment.write_csv(DATA_DIR / "10_employment_info.tsv", separator="\t")

    # 11: loan applications (depend on multiple tables)
    print("Generating loan applications...")
    df_applications = gen_loan_applications(
        applicant_ids=applicant_ids,
        product_ids=df_product["id"].to_list(),
        purpose_ids=df_loan_purpose["id"].to_list(),
        status_ids=df_app_status["id"].to_list(),
        n=800
    )
    df_applications.write_csv(DATA_DIR / "11_loan_application.tsv", separator="\t")
    application_ids = df_applications["id"].to_list()

    # 12: rule evaluations (depend on applications, rules)
    print("Generating rule evaluations...")
    df_rule_eval = gen_rule_evaluations(application_ids, df_rules["id"].to_list())
    df_rule_eval.write_csv(DATA_DIR / "12_rule_evaluation.tsv", separator="\t")

    # 13: approval decisions
    print("Generating approval decisions...")
    df_decisions = gen_approval_decisions(
        application_ids,
        df_decision_type["id"].to_list(),
        df_risk_level["id"].to_list()
    )
    df_decisions.write_csv(DATA_DIR / "13_approval_decision.tsv", separator="\t")

    # 14: approval history
    print("Generating approval history...")
    df_history = gen_approval_history(application_ids, df_app_status["id"].to_list())
    df_history.write_csv(DATA_DIR / "14_approval_history.tsv", separator="\t")

    # 15: similar cases
    print("Generating similar cases...")
    df_similar = gen_similar_cases(application_ids, sample_size=1000)
    df_similar.write_csv(DATA_DIR / "15_similar_case.tsv", separator="\t")

    # 16: documents
    print("Generating documents...")
    df_docs = gen_documents(application_ids)
    df_docs.write_csv(DATA_DIR / "16_document.tsv", separator="\t")

    # 17: fraud flags
    print("Generating fraud flags...")
    df_fraud = gen_fraud_flags(application_ids)
    df_fraud.write_csv(DATA_DIR / "17_fraud_flag.tsv", separator="\t")

    # 18: audit logs
    print("Generating audit logs...")
    df_audit = gen_audit_logs(application_ids, applicant_ids)
    df_audit.write_csv(DATA_DIR / "18_audit_log.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")

    return {
        "applicant_ids": applicant_ids,
        "application_ids": application_ids,
    }


def parse_datetime_fields(row: dict, datetime_fields: list, date_fields: list) -> dict:
    """Parse string-form datetime and date fields into Python objects"""
    from datetime import datetime, date
    result = {}
    for k, v in row.items():
        if v is None:
            continue
        if k in datetime_fields and isinstance(v, str):
            try:
                result[k] = datetime.fromisoformat(v)
            except ValueError:
                result[k] = v
        elif k in date_fields and isinstance(v, str):
            try:
                result[k] = date.fromisoformat(v)
            except ValueError:
                result[k] = v
        else:
            result[k] = v
    return result


def create_sqlite_database() -> None:
    """Create the SQLite database from TSV files. Idempotent: existing database is deleted first."""
    # Delete existing database
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # Define datetime and date fields for each model
    datetime_cols = ["created_at", "updated_at", "submitted_at", "decision_at", "funded_at",
                     "report_date", "verification_date", "evaluated_at", "computed_at",
                     "uploaded_at", "verified_at", "flagged_at", "resolved_at"]
    date_cols = ["date_of_birth", "employment_start_date"]

    with Session(engine) as session:
        # Load TSV files in topological order
        table_model_map = [
            ("01_application_status.tsv", ApplicationStatus),
            ("02_employment_type.tsv", EmploymentType),
            ("03_loan_purpose.tsv", LoanPurpose),
            ("04_decision_type.tsv", DecisionType),
            ("05_risk_level.tsv", RiskLevel),
            ("06_loan_product.tsv", LoanProduct),
            ("07_risk_rule.tsv", RiskRule),
            ("08_applicant.tsv", Applicant),
            ("09_credit_report.tsv", CreditReport),
            ("10_employment_info.tsv", EmploymentInfo),
            ("11_loan_application.tsv", LoanApplication),
            ("12_rule_evaluation.tsv", RuleEvaluation),
            ("13_approval_decision.tsv", ApprovalDecision),
            ("14_approval_history.tsv", ApprovalHistory),
            ("15_similar_case.tsv", SimilarCase),
            ("16_document.tsv", Document),
            ("17_fraud_flag.tsv", FraudFlag),
            ("18_audit_log.tsv", AuditLog),
        ]

        for tsv_file, model in table_model_map:
            print(f"Loading {tsv_file}...")
            df = pl.read_csv(DATA_DIR / tsv_file, separator="\t", null_values=["", "null"])
            for row in df.iter_rows(named=True):
                # Parse datetime / date fields
                clean_row = parse_datetime_fields(row, datetime_cols, date_cols)
                session.add(model(**clean_row))
            session.flush()

        session.commit()

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    """Main entry function"""
    print("=" * 60)
    print("Digital Lending - Credit Approval Assistant Data Generator")
    print("=" * 60)
    print("\nStarting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("\n" + "=" * 60)
    print("All done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
