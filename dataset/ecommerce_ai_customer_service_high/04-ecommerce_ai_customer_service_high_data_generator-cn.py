"""
电商平台 - AI客服工单处理系统 假数据生成器
复杂度: High
生成工具: Fake Data Generator Agent

业务背景:
NestMart 是一家专注于中高端家居生活用品的垂直电商平台,主要品类包括寝具、厨房用品、
家居收纳、照明等。本数据集模拟完整的AI客服工单处理系统,包含:
- 4-step Pipeline: 意图识别 → 信息提取 → 策略决策 → 回复生成
- 标注数据集: 人工标注的ground truth用于Evaluation
- Prompt版本管理: 不同版本的Prompt及其效果对比
- Evaluation框架: LLM Judge评分、规则检查、准确率统计
- 多轮迭代记录: Prompt优化历史和A/B测试结果

本数据集适用于: Prompt Evaluation框架测试、LLM工具链开发、AI客服系统教学
"""

from __future__ import annotations
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
import random
import json

import polars as pl
from faker import Faker
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ============================================================================
# 配置
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "ecommerce_ai_customer_service_high.sqlite"
FAKER_LOCALE = "zh_CN"  # 中文地区设置
RANDOM_SEED = 42

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


# 1. 用户会员等级枚举表
class UserTier(Base):
    """用户会员等级定义"""
    __tablename__ = "user_tier"

    tier_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    tier_name_cn: Mapped[str] = mapped_column(String(50), nullable=False)
    tier_name_en: Mapped[str] = mapped_column(String(50), nullable=False)
    priority_level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text)


# 2. 商家类型枚举表
class SellerType(Base):
    """商家类型定义"""
    __tablename__ = "seller_type"

    seller_type_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    seller_type_name_cn: Mapped[str] = mapped_column(String(50), nullable=False)
    seller_type_name_en: Mapped[str] = mapped_column(String(50), nullable=False)
    refund_authority: Mapped[str] = mapped_column(String(50))  # 退款决策权归属
    description: Mapped[str] = mapped_column(Text)


# 3. 意图分类枚举表
class IntentCategory(Base):
    """工单意图分类体系"""
    __tablename__ = "intent_category"

    intent_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    intent_name_cn: Mapped[str] = mapped_column(String(100), nullable=False)
    intent_name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    category_level: Mapped[int] = mapped_column(Integer)  # 1=primary, 2=secondary
    typical_scenario: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(String(50))


# 4. 决策规则定义表
class DecisionRule(Base):
    """策略决策规则库"""
    __tablename__ = "decision_rule"

    rule_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_condition: Mapped[str] = mapped_column(Text, nullable=False)
    action_required: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)


# 5. 用户表
class User(Base):
    """用户主表"""
    __tablename__ = "user"

    user_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str] = mapped_column(String(20))
    tier_code: Mapped[str] = mapped_column(String(20), ForeignKey("user_tier.tier_code"))
    registration_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_order_count: Mapped[int] = mapped_column(Integer, default=0)
    total_spent_amount: Mapped[float] = mapped_column(Float, default=0.0)
    refund_count_30days: Mapped[int] = mapped_column(Integer, default=0)


# 6. 商品表
class Product(Base):
    """商品SKU"""
    __tablename__ = "product"

    product_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # 寝具/厨房/收纳/照明
    seller_type_code: Mapped[str] = mapped_column(String(20), ForeignKey("seller_type.seller_type_code"))
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)


# 7. 订单表
class Order(Base):
    """订单主表"""
    __tablename__ = "order"

    order_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(20), ForeignKey("user.user_id"))
    product_id: Mapped[str] = mapped_column(String(20), ForeignKey("product.product_id"))
    order_amount: Mapped[float] = mapped_column(Float, nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    logistics_status: Mapped[str] = mapped_column(String(50))  # in_transit/delivered/signed/lost
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime)
    tracking_number: Mapped[str] = mapped_column(String(50))


# 8. 原始工单表
class RawTicket(Base):
    """用户提交的原始工单"""
    __tablename__ = "raw_ticket"

    ticket_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(20), ForeignKey("user.user_id"))
    order_id: Mapped[str | None] = mapped_column(String(30), ForeignKey("order.order_id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    channel: Mapped[str] = mapped_column(String(20))  # web_form/app/chat/email
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    has_attachment: Mapped[bool] = mapped_column(Boolean, default=False)


# 9. Prompt版本表
class PromptVersion(Base):
    """Prompt版本管理"""
    __tablename__ = "prompt_version"

    prompt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_name: Mapped[str] = mapped_column(String(50), nullable=False)  # step1_intent/step3_decision
    version_code: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    change_description: Mapped[str] = mapped_column(Text)
    is_production: Mapped[bool] = mapped_column(Boolean, default=False)


# 10. Step 1 意图识别输出表
class Step1IntentOutput(Base):
    """Step 1: 意图识别模型输出"""
    __tablename__ = "step1_intent_output"

    output_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.prompt_id"))
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    primary_intent: Mapped[str] = mapped_column(String(50), ForeignKey("intent_category.intent_code"))
    secondary_intents: Mapped[str] = mapped_column(String(200))  # JSON数组字符串
    sentiment: Mapped[str] = mapped_column(String(20))  # neutral/frustrated/angry/satisfied
    urgency: Mapped[str] = mapped_column(String(20))  # low/medium/high
    reasoning: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)


# 11. Step 3 策略决策输出表
class Step3DecisionOutput(Base):
    """Step 3: 策略决策模型输出"""
    __tablename__ = "step3_decision_output"

    output_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.prompt_id"))
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    alternative_action: Mapped[str | None] = mapped_column(String(50))
    escalate_to_human: Mapped[bool] = mapped_column(Boolean, default=False)
    rules_checked: Mapped[str] = mapped_column(String(200))  # JSON数组字符串
    rules_violated: Mapped[str] = mapped_column(String(200))  # JSON数组字符串
    latency_ms: Mapped[int] = mapped_column(Integer)


# 12. 人工标注数据表 (Ground Truth)
class AnnotationGroundTruth(Base):
    """人工标注的Ground Truth数据"""
    __tablename__ = "annotation_ground_truth"

    annotation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    annotator_id: Mapped[str] = mapped_column(String(20), ForeignKey("annotator.annotator_id"))
    annotation_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    true_primary_intent: Mapped[str] = mapped_column(String(50), ForeignKey("intent_category.intent_code"))
    true_secondary_intents: Mapped[str] = mapped_column(String(200))
    true_sentiment: Mapped[str] = mapped_column(String(20))
    true_urgency: Mapped[str] = mapped_column(String(20))
    annotator_confidence: Mapped[int] = mapped_column(Integer)  # 1-3
    annotation_notes: Mapped[str | None] = mapped_column(Text)
    annotation_version: Mapped[str] = mapped_column(String(10), default="v2")


# 13. 标注一致性检查表
class AnnotationAgreement(Base):
    """双人标注一致性记录"""
    __tablename__ = "annotation_agreement"

    agreement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    annotation_id_1: Mapped[int] = mapped_column(Integer, ForeignKey("annotation_ground_truth.annotation_id"))
    annotation_id_2: Mapped[int] = mapped_column(Integer, ForeignKey("annotation_ground_truth.annotation_id"))
    is_agreement: Mapped[bool] = mapped_column(Boolean, nullable=False)
    disagreement_field: Mapped[str | None] = mapped_column(String(50))
    resolution_status: Mapped[str] = mapped_column(String(20))  # pending/resolved/escalated
    arbitrator_id: Mapped[str | None] = mapped_column(String(20))
    final_decision: Mapped[str | None] = mapped_column(Text)


# 14. Evaluation运行记录表
class EvaluationRun(Base):
    """Evaluation执行记录"""
    __tablename__ = "evaluation_run"

    run_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    triggered_by: Mapped[str] = mapped_column(String(30))  # github_push/manual/scheduled
    step1_prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.prompt_id"))
    step3_prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompt_version.prompt_id"))
    dataset_version: Mapped[str] = mapped_column(String(20), nullable=False)
    run_status: Mapped[str] = mapped_column(String(20))  # running/completed/failed
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_tickets_evaluated: Mapped[int | None] = mapped_column(Integer)
    step1_accuracy: Mapped[float | None] = mapped_column(Float)
    step3_rule_violation_rate: Mapped[float | None] = mapped_column(Float)
    step1_judge_avg_score: Mapped[float | None] = mapped_column(Float)
    step3_judge_avg_score: Mapped[float | None] = mapped_column(Float)


# 15. Step1 详细评估结果表
class Step1EvalDetail(Base):
    """Step 1 详细评估结果"""
    __tablename__ = "step1_eval_detail"

    eval_detail_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), ForeignKey("evaluation_run.run_id"))
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    output_id: Mapped[int] = mapped_column(Integer, ForeignKey("step1_intent_output.output_id"))
    annotation_id: Mapped[int] = mapped_column(Integer, ForeignKey("annotation_ground_truth.annotation_id"))
    predicted_intent: Mapped[str] = mapped_column(String(50))
    true_intent: Mapped[str] = mapped_column(String(50))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    judge_reasoning_score: Mapped[int | None] = mapped_column(Integer)  # 1-5
    judge_completeness_score: Mapped[int | None] = mapped_column(Integer)  # 0/1
    judge_comment: Mapped[str | None] = mapped_column(Text)


# 16. Step3 详细评估结果表
class Step3EvalDetail(Base):
    """Step 3 详细评估结果"""
    __tablename__ = "step3_eval_detail"

    eval_detail_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), ForeignKey("evaluation_run.run_id"))
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    output_id: Mapped[int] = mapped_column(Integer, ForeignKey("step3_decision_output.output_id"))
    rule_check_passed: Mapped[bool] = mapped_column(Boolean)
    rules_violated: Mapped[str] = mapped_column(String(200))  # JSON数组
    violation_severity: Mapped[str | None] = mapped_column(String(20))  # critical/high/medium
    judge_rationale_completeness: Mapped[int | None] = mapped_column(Integer)  # 1-5
    judge_risk_awareness: Mapped[int | None] = mapped_column(Integer)  # 0/1
    judge_overall_quality: Mapped[int | None] = mapped_column(Integer)  # 1-5
    judge_comment: Mapped[str | None] = mapped_column(Text)


# 17. Confusion Matrix表
class ConfusionMatrix(Base):
    """意图分类混淆矩阵"""
    __tablename__ = "confusion_matrix"

    matrix_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), ForeignKey("evaluation_run.run_id"))
    true_label: Mapped[str] = mapped_column(String(50), ForeignKey("intent_category.intent_code"))
    predicted_label: Mapped[str] = mapped_column(String(50), ForeignKey("intent_category.intent_code"))
    count: Mapped[int] = mapped_column(Integer, nullable=False)


# 18. Prompt迭代对比表
class PromptComparison(Base):
    """Prompt版本效果对比"""
    __tablename__ = "prompt_comparison"

    comparison_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baseline_run_id: Mapped[str] = mapped_column(String(50), ForeignKey("evaluation_run.run_id"))
    experiment_run_id: Mapped[str] = mapped_column(String(50), ForeignKey("evaluation_run.run_id"))
    comparison_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50))
    baseline_value: Mapped[float] = mapped_column(Float)
    experiment_value: Mapped[float] = mapped_column(Float)
    improvement_pct: Mapped[float] = mapped_column(Float)
    is_significant: Mapped[bool] = mapped_column(Boolean)  # 统计显著性


# 19. 规则违反案例库
class RuleViolationCase(Base):
    """规则违反典型案例"""
    __tablename__ = "rule_violation_case"

    case_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), ForeignKey("evaluation_run.run_id"))
    ticket_id: Mapped[str] = mapped_column(String(20), ForeignKey("raw_ticket.ticket_id"))
    rule_id: Mapped[str] = mapped_column(String(10), ForeignKey("decision_rule.rule_id"))
    violation_type: Mapped[str] = mapped_column(String(50))
    ai_decision: Mapped[str] = mapped_column(String(50))
    expected_decision: Mapped[str] = mapped_column(String(50))
    impact_severity: Mapped[str] = mapped_column(String(20))  # critical/high/medium/low
    discovered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fix_status: Mapped[str] = mapped_column(String(20), default="open")  # open/fixed/wont_fix
    fix_prompt_version: Mapped[str | None] = mapped_column(String(20))


# 20. 标注员信息表
class Annotator(Base):
    """标注员基本信息"""
    __tablename__ = "annotator"

    annotator_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    annotator_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30))  # annotator/reviewer/arbitrator
    total_annotations: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float)
    agreement_rate: Mapped[float | None] = mapped_column(Float)  # Cohen's Kappa
    joined_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ============================================================================
# 数据生成器
# ============================================================================

def gen_user_tier() -> pl.DataFrame:
    """生成用户会员等级枚举数据"""
    records = [
        {"tier_code": "new", "tier_name_cn": "新用户", "tier_name_en": "New User", "priority_level": 1,
         "description": "注册未满30天或首单未完成的用户"},
        {"tier_code": "regular", "tier_name_cn": "普通会员", "tier_name_en": "Regular", "priority_level": 2,
         "description": "完成首单且累计消费<$500的用户"},
        {"tier_code": "vip_silver", "tier_name_cn": "白银会员", "tier_name_en": "VIP Silver", "priority_level": 3,
         "description": "累计消费$500-$1500的用户"},
        {"tier_code": "vip_gold", "tier_name_cn": "黄金会员", "tier_name_en": "VIP Gold", "priority_level": 4,
         "description": "累计消费$1500-$5000的用户"},
        {"tier_code": "vip_platinum", "tier_name_cn": "铂金会员", "tier_name_en": "VIP Platinum", "priority_level": 5,
         "description": "累计消费>$5000的高价值用户"},
    ]
    return pl.DataFrame(records)


def gen_seller_type() -> pl.DataFrame:
    """生成商家类型枚举数据"""
    records = [
        {"seller_type_code": "nestmart_original", "seller_type_name_cn": "NestMart自营", "seller_type_name_en": "NestMart Original",
         "refund_authority": "platform", "description": "平台自营商品,退款决策权在平台"},
        {"seller_type_code": "third_party", "seller_type_name_cn": "第三方商家", "seller_type_name_en": "Third Party Merchant",
         "refund_authority": "merchant", "description": "第三方入驻商家,退换货由商家处理"},
    ]
    return pl.DataFrame(records)


def gen_intent_category() -> pl.DataFrame:
    """生成意图分类体系数据"""
    records = [
        {"intent_code": "dispute_non_receipt", "intent_name_cn": "物流纠纷-未收到货", "intent_name_en": "Dispute - Non Receipt",
         "category_level": 1, "typical_scenario": "快递显示已签收但用户声称未实际收到包裹", "recommended_action": "investigate_logistics"},
        {"intent_code": "dispute_damaged", "intent_name_cn": "物流纠纷-收到破损商品", "intent_name_en": "Dispute - Damaged",
         "category_level": 1, "typical_scenario": "收到的商品在运输中损坏", "recommended_action": "reship_or_refund"},
        {"intent_code": "dispute_wrong_item", "intent_name_cn": "物流纠纷-收到错误商品", "intent_name_en": "Dispute - Wrong Item",
         "category_level": 1, "typical_scenario": "收到的商品与订单不符", "recommended_action": "reship"},
        {"intent_code": "refund_request", "intent_name_cn": "退款请求", "intent_name_en": "Refund Request",
         "category_level": 1, "typical_scenario": "正常退款请求(七天无理由等)", "recommended_action": "approve_refund"},
        {"intent_code": "exchange_request", "intent_name_cn": "换货请求", "intent_name_en": "Exchange Request",
         "category_level": 1, "typical_scenario": "用户希望换货而非退款", "recommended_action": "arrange_exchange"},
        {"intent_code": "logistics_inquiry", "intent_name_cn": "物流查询", "intent_name_en": "Logistics Inquiry",
         "category_level": 1, "typical_scenario": "查询物流状态,无纠纷", "recommended_action": "provide_tracking_info"},
        {"intent_code": "complaint_quality", "intent_name_cn": "质量投诉", "intent_name_en": "Quality Complaint",
         "category_level": 1, "typical_scenario": "商品质量问题(已使用)", "recommended_action": "evaluate_warranty"},
        {"intent_code": "complaint_service", "intent_name_cn": "服务投诉", "intent_name_en": "Service Complaint",
         "category_level": 1, "typical_scenario": "对客服态度或服务质量的投诉", "recommended_action": "escalate_to_supervisor"},
        {"intent_code": "policy_inquiry", "intent_name_cn": "政策咨询", "intent_name_en": "Policy Inquiry",
         "category_level": 1, "typical_scenario": "咨询退换货政策规定", "recommended_action": "explain_policy"},
        {"intent_code": "reship_request", "intent_name_cn": "重发请求", "intent_name_en": "Reship Request",
         "category_level": 2, "typical_scenario": "用户希望重新发货", "recommended_action": "reship"},
        {"intent_code": "compensation_request", "intent_name_cn": "补偿要求", "intent_name_en": "Compensation Request",
         "category_level": 2, "typical_scenario": "用户要求额外补偿", "recommended_action": "evaluate_compensation"},
        {"intent_code": "complaint_logistics", "intent_name_cn": "物流服务投诉", "intent_name_en": "Logistics Complaint",
         "category_level": 2, "typical_scenario": "对物流公司服务的投诉", "recommended_action": "forward_to_logistics"},
    ]
    return pl.DataFrame(records)


def gen_decision_rule() -> pl.DataFrame:
    """生成决策规则库数据"""
    base_date = datetime(2024, 11, 1)
    records = [
        {"rule_id": "R001", "rule_name": "自营商品七天无理由退款",
         "rule_condition": "seller_type == 'nestmart_original' AND days_since_receipt <= 7 AND intent IN ['refund_request']",
         "action_required": "auto_approve_refund", "priority": 1, "effective_date": base_date,
         "note": "自营商品支持7天无理由退款,商品需完好"},
        {"rule_id": "R002", "rule_name": "第三方商家转交处理",
         "rule_condition": "seller_type == 'third_party'",
         "action_required": "transfer_to_merchant", "priority": 2, "effective_date": base_date,
         "note": "第三方商家商品的退换货由商家负责,平台不能自行决定退款"},
        {"rule_id": "R003", "rule_name": "高金额必须人工审核",
         "rule_condition": "order_amount > 225",
         "action_required": "escalate_to_human", "priority": 3, "effective_date": base_date,
         "note": "金额超过$225的订单退款需人工审核防止欺诈"},
        {"rule_id": "R004", "rule_name": "高频退款用户升级人工",
         "rule_condition": "user_refund_count_30days >= 3",
         "action_required": "escalate_to_human", "priority": 4, "effective_date": base_date,
         "note": "30天内退款3次以上的用户可能存在异常,需人工介入"},
        {"rule_id": "R005", "rule_name": "物流运输中不得判定丢件",
         "rule_condition": "logistics_status == 'in_transit' AND intent == 'dispute_non_receipt'",
         "action_required": "reject_dispute_pending_logistics", "priority": 5, "effective_date": base_date,
         "note": "包裹仍在运输中不能判定为未收到货"},
        {"rule_id": "R006", "rule_name": "VIP用户物流纠纷优先处理",
         "rule_condition": "user_tier IN ['vip_gold', 'vip_platinum'] AND intent == 'dispute_non_receipt'",
         "action_required": "priority_full_refund", "priority": 6, "effective_date": base_date,
         "note": "VIP用户的物流纠纷倾向全额退款而非重发"},
        {"rule_id": "R007", "rule_name": "商品破损需提供照片证据",
         "rule_condition": "intent == 'dispute_damaged' AND has_attachment == False",
         "action_required": "request_evidence", "priority": 7, "effective_date": base_date,
         "note": "破损商品退款需要用户提供照片证据"},
    ]
    return pl.DataFrame(records)


def gen_user(n: int = 500) -> pl.DataFrame:
    """生成用户数据"""
    tiers = ["new", "regular", "vip_silver", "vip_gold", "vip_platinum"]
    tier_weights = [0.15, 0.40, 0.25, 0.15, 0.05]  # 符合实际用户分布

    records = []
    base_date = datetime(2022, 1, 1)

    for i in range(1, n + 1):
        tier = random.choices(tiers, weights=tier_weights)[0]
        reg_date = base_date + timedelta(days=random.randint(0, 900))

        # 根据tier设置合理的订单和消费金额
        if tier == "new":
            total_orders = random.randint(0, 2)
            total_spent = random.uniform(0, 150)
            refund_count = 0
        elif tier == "regular":
            total_orders = random.randint(3, 8)
            total_spent = random.uniform(150, 500)
            refund_count = random.randint(0, 1)
        elif tier == "vip_silver":
            total_orders = random.randint(8, 15)
            total_spent = random.uniform(500, 1500)
            refund_count = random.randint(0, 2)
        elif tier == "vip_gold":
            total_orders = random.randint(15, 30)
            total_spent = random.uniform(1500, 5000)
            refund_count = random.randint(0, 2)
        else:  # platinum
            total_orders = random.randint(30, 60)
            total_spent = random.uniform(5000, 15000)
            refund_count = random.randint(0, 1)

        # ~3% 用户为高频退款用户 (30 天内 >=3 次), 用于触发 R004 反欺诈规则
        # (new 用户订单太少, 不参与高频退款画像)
        if tier != "new" and random.random() < 0.03:
            refund_count = random.randint(3, 6)

        records.append({
            "user_id": f"U{i:08d}",
            "user_name": fake.name(),
            "email": fake.unique.email(),
            "phone": fake.phone_number(),
            "tier_code": tier,
            "registration_date": reg_date,
            "total_order_count": total_orders,
            "total_spent_amount": round(total_spent, 2),
            "refund_count_30days": refund_count,
        })

    fake.unique.clear()
    return pl.DataFrame(records)


def gen_product(n: int = 200) -> pl.DataFrame:
    """生成商品SKU数据"""
    categories = {
        "寝具": ["天丝四件套", "羽绒被", "记忆枕", "床笠", "毛毯", "夏凉被"],
        "厨房用品": ["铸铁锅", "刀具套装", "砧板", "储物罐", "调料架", "不粘锅"],
        "家居收纳": ["收纳箱", "衣柜整理架", "抽屉分隔器", "鞋架", "储物篮", "挂钩"],
        "照明": ["台灯", "落地灯", "氛围灯", "床头灯", "吊灯", "装饰灯串"],
    }

    seller_types = ["nestmart_original", "third_party"]
    seller_weights = [0.70, 0.30]  # 70%自营

    records = []
    product_counter = 1

    for category, items in categories.items():
        for _ in range(n // 4):  # 每个品类生成约1/4的商品
            item_name = random.choice(items)
            seller_type = random.choices(seller_types, weights=seller_weights)[0]

            # 根据品类设置价格区间
            if category == "寝具":
                price = random.uniform(50, 250)
            elif category == "厨房用品":
                price = random.uniform(30, 120)
            elif category == "家居收纳":
                price = random.uniform(25, 100)
            else:  # 照明
                price = random.uniform(60, 300)

            records.append({
                "product_id": f"SKU{product_counter:06d}",
                "product_name": f"{category}-{item_name}-{fake.color_name()}",
                "category": category,
                "seller_type_code": seller_type,
                "unit_price": round(price, 2),
                "stock_quantity": random.randint(10, 500),
            })
            product_counter += 1

    return pl.DataFrame(records[:n])


def gen_order(n: int = 2000, user_df: pl.DataFrame = None, product_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成订单数据"""
    if user_df is None or product_df is None:
        raise ValueError("需要提供user和product数据")

    user_ids = user_df["user_id"].to_list()
    product_ids = product_df["product_id"].to_list()
    product_prices = dict(zip(product_df["product_id"].to_list(), product_df["unit_price"].to_list()))

    logistics_statuses = ["in_transit", "delivered", "signed", "lost"]
    status_weights = [0.10, 0.15, 0.70, 0.05]

    records = []
    base_date = datetime(2024, 9, 1)

    for i in range(1, n + 1):
        user_id = random.choice(user_ids)
        product_id = random.choice(product_ids)
        # 订单日期落在 2024-09-01 ~ 2024-10-31 (60 天窗口),
        # 保证全部订单早于工单提交期 (2024-11), 满足 order_date < submitted_at 时序约束
        order_date = base_date + timedelta(days=random.randint(0, 60))
        status = random.choices(logistics_statuses, weights=status_weights)[0]

        # 根据状态设置配送日期
        if status in ["delivered", "signed"]:
            delivery_date = order_date + timedelta(days=random.randint(2, 7))
        elif status == "lost":
            delivery_date = None
        else:  # in_transit
            delivery_date = None

        records.append({
            "order_id": f"ORD-2024-{i:06d}",
            "user_id": user_id,
            "product_id": product_id,
            "order_amount": product_prices[product_id],
            "order_date": order_date,
            "logistics_status": status,
            "delivery_date": delivery_date,
            "tracking_number": f"SF{random.randint(100000000000, 999999999999)}",
        })

    return pl.DataFrame(records)


def gen_raw_ticket(n: int = 5000, user_df: pl.DataFrame = None, order_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成原始工单数据"""
    if user_df is None or order_df is None:
        raise ValueError("需要提供user和order数据")

    user_ids = user_df["user_id"].to_list()
    order_ids = order_df["order_id"].to_list()
    # 预构建订单 ID -> 订单详情的查找字典 (避免循环内 filter 慢)
    order_lookup = {
        row["order_id"]: row
        for row in order_df.to_dicts()
    }
    channels = ["web_form", "app", "chat", "email", "phone_transcript"]

    # 工单模板(根据NestMart项目中的真实场景)
    ticket_templates = {
        "dispute_non_receipt": [
            "您好,我于{order_date}在NestMart平台购买了{product_name}(订单号{order_id},金额${amount}),预计{expected_date}送达。但截至今天{submit_date},我仍未收到任何包裹。我查询了快递单号,显示状态为已签收,签收时间为{sign_date}。然而我本人当天全天在公司上班,家中也无其他人员,快递员并未联系我本人。我多次拨打快递公司客服,对方仅表示系统显示已签收,无法给出进一步说明。现要求平台介入处理,并给予退款或重新发货。",
            "订单{order_id}显示已签收,但我根本没收到货!快递公司说在门口,但我找遍了都没有。这是怎么回事?要求退款!",
            "你们这个物流太差了,{order_id}显示签收了,但我们小区没人签收。现在货找不到了,我要投诉!必须给我退款或者重发!",
        ],
        "dispute_damaged": [
            "订单{order_id}今天收到了,但是打开包裹发现{product_name}已经破损了,外包装也有明显挤压痕迹。我已拍照留证。这种情况能否安排换货或退款?",
            "刚收到货,{product_name}摔碎了,包装盒都瘪了,明显是运输问题。订单号{order_id},金额${amount},要求退款!",
        ],
        "refund_request": [
            "您好,我购买的{product_name}(订单号{order_id})收到后发现颜色与图片不符,不太喜欢,想申请七天无理由退款。商品包装完好未使用,请问如何办理退货?",
            "订单{order_id}想退货,商品没拆封,在7天内,麻烦安排退款。",
        ],
        "exchange_request": [
            "{order_id}的{product_name}尺寸买小了,能否换一个大一号的?",
            "您好,订单{order_id}购买的床品套件,颜色收到后觉得不太适合,希望能换成灰色款。请问可以换货吗?",
        ],
        "complaint_quality": [
            "订单{order_id}的{product_name}用了一个星期就出现问题了,这质量也太差了吧?要求换货或者退款!",
        ],
    }

    records = []
    base_date = datetime(2024, 11, 1)

    # 按照意图类别分层生成 (主意图分布, 见 ER §7.3)
    intent_distribution = {
        "dispute_non_receipt": 0.25,  # ~1250 条
        "dispute_damaged": 0.15,      # ~750 条
        "refund_request": 0.20,       # ~1000 条
        "exchange_request": 0.10,     # ~500 条
        "complaint_quality": 0.10,    # ~500 条
        "logistics_inquiry": 0.10,    # ~500 条
        "policy_inquiry": 0.10,       # ~500 条
    }

    for intent_type, ratio in intent_distribution.items():
        count = int(n * ratio)
        for _ in range(count):
            # 70%的工单关联订单, 30%不关联(咨询类)
            # 关键修复: 关联订单时, 工单提交人 user_id = 该订单的 user_id (跨表归因一致)
            if random.random() < 0.7:
                order_id = random.choice(order_ids)
                order_info = order_lookup[order_id]
                user_id = order_info["user_id"]
                order_date_str = order_info["order_date"].strftime("%m月%d日")
                amount = order_info["order_amount"]
            else:
                order_id = None
                user_id = random.choice(user_ids)
                order_date_str = "10月15日"
                amount = 68.00

            # 工单提交期: 2024-11-01 ~ 2024-11-30 (30 天窗口),
            # 订单已在 9-10 月生成 → 始终满足 order_date < submitted_at
            submit_date = base_date + timedelta(days=random.randint(0, 29))

            # 根据意图类型选择模板
            if intent_type in ticket_templates:
                template = random.choice(ticket_templates[intent_type])
                text = template.format(
                    order_id=order_id or "ORD-2024-XXXXX",
                    order_date=order_date_str,
                    product_name="北欧风格四件套" if random.random() < 0.5 else "铸铁锅",
                    amount=f"{amount:.2f}",
                    expected_date=f"{(submit_date - timedelta(days=4)).strftime('%m月%d日')}",
                    submit_date=submit_date.strftime("%m月%d日"),
                    sign_date=f"{(submit_date - timedelta(days=1)).strftime('%m月%d日')}",
                )
            else:
                text = f"订单{order_id or 'ORD-2024-XXXXX'}的问题咨询,请帮忙处理。" + fake.text(max_nb_chars=100)

            # 破损类工单高频附带照片证据 (~75%), 其它类 ~20% (见 ER §7.3 / R007)
            attach_prob = 0.75 if intent_type == "dispute_damaged" else 0.20

            records.append({
                "ticket_id": None,  # 占位, shuffle 后统一重排
                "user_id": user_id,
                "order_id": order_id,
                "submitted_at": submit_date,
                "channel": random.choice(channels),
                "raw_text": text,
                "has_attachment": random.random() < attach_prob,
                "true_intent": intent_type,  # 内部列: 工单真实意图 (写 TSV 前会丢弃)
            })

    # 关键修复: 打散意图顺序, 使评估样本 (随机分层抽样) 能覆盖全部意图,
    # 避免"前 N 条全是 dispute_non_receipt"导致评估退化为单一意图
    records = records[:n]
    random.shuffle(records)
    for idx, rec in enumerate(records, start=1):
        rec["ticket_id"] = f"T{idx:08d}"

    return pl.DataFrame(records)


def gen_prompt_version() -> pl.DataFrame:
    """生成Prompt版本数据

    Step1: v1 → v5 (意图识别) 共 5 个版本, v5 为 production
    Step3: v1 → v3 (策略决策) 共 3 个版本, v3 为 production
    """
    MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    records = [
        # Step1 Prompt 演进史 (prompt_id 1-5)
        {
            "prompt_id": 1, "step_name": "step1_intent", "version_code": "v1",
            "prompt_content": "你是NestMart电商平台的资深客服分析师...(省略具体内容)",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 1),
            "change_description": "初始版本",
            "is_production": False,
        },
        {
            "prompt_id": 2, "step_name": "step1_intent", "version_code": "v2",
            "prompt_content": "你是NestMart电商平台的资深客服分析师...特别注意先读完全文再做分类,常见陷阱用户在开头提到退款但实际问题是物流纠纷...(改进版)",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 8),
            "change_description": "修复dispute_non_receipt被误判为refund_request的问题,加入先读完全文的指引",
            "is_production": False,
        },
        {
            "prompt_id": 3, "step_name": "step1_intent", "version_code": "v3",
            "prompt_content": "你是NestMart电商平台的资深客服分析师...优化 sentiment 判断: angry 不再过度泛化,只在明确的极端情绪表达时才标记...(微调版)",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 14),
            "change_description": "优化 sentiment 判断: angry 不再过度泛化",
            "is_production": False,
        },
        {
            "prompt_id": 4, "step_name": "step1_intent", "version_code": "v4",
            "prompt_content": "你是NestMart电商平台的资深客服分析师...(包含 5 个 few-shot 示例,覆盖最难分的意图对: dispute_non_receipt vs refund_request, dispute_damaged vs complaint_quality...)",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 18),
            "change_description": "加入 5 个 few-shot 示例,覆盖最难分的意图对",
            "is_production": False,
        },
        {
            "prompt_id": 5, "step_name": "step1_intent", "version_code": "v5",
            "prompt_content": "你是NestMart电商平台的资深客服分析师...(production 版本, 微调 urgency 阈值, 含 few-shot)",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 22),
            "change_description": "微调 urgency 阈值, 当前 production 版本",
            "is_production": True,
        },
        # Step3 Prompt 演进史 (prompt_id 6-8)
        {
            "prompt_id": 6, "step_name": "step3_decision", "version_code": "v1",
            "prompt_content": "你是NestMart电商平台的客服决策系统...(省略具体内容)",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 1),
            "change_description": "初始版本",
            "is_production": False,
        },
        {
            "prompt_id": 7, "step_name": "step3_decision", "version_code": "v2",
            "prompt_content": "你是NestMart电商平台的客服决策系统...在 Prompt 头部强调: 第三方商家商品必须 transfer_to_merchant, 平台无权自行退款 (R002)...",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 10),
            "change_description": "强调 R002 第三方商家规则, 降低 unauthorized_refund 违反率",
            "is_production": False,
        },
        {
            "prompt_id": 8, "step_name": "step3_decision", "version_code": "v3",
            "prompt_content": "你是NestMart电商平台的客服决策系统...(production 版本, 加入 R003-R007 规则的逐条解释 + 决策树)...",
            "model_id": MODEL_ID, "temperature": 0.0,
            "created_at": datetime(2024, 11, 20),
            "change_description": "加入 R003-R007 规则的逐条解释 + 决策树, 当前 production 版本",
            "is_production": True,
        },
    ]
    return pl.DataFrame(records)


# 最易混淆的意图对 (用于生成贴近业务的误判模式, 见 ER §5.18 / SQL Query 3)
CONFUSABLE_INTENTS = {
    "dispute_non_receipt": ["refund_request", "logistics_inquiry"],
    "refund_request": ["dispute_non_receipt", "exchange_request"],
    "dispute_damaged": ["complaint_quality", "refund_request"],
    "complaint_quality": ["dispute_damaged", "complaint_service"],
    "exchange_request": ["refund_request", "dispute_wrong_item"],
    "logistics_inquiry": ["dispute_non_receipt", "policy_inquiry"],
    "policy_inquiry": ["logistics_inquiry", "refund_request"],
}
# 9 个主意图 (category_level=1)
PRIMARY_INTENTS = [
    "dispute_non_receipt", "dispute_damaged", "dispute_wrong_item",
    "refund_request", "exchange_request", "logistics_inquiry",
    "complaint_quality", "complaint_service", "policy_inquiry",
]


def _confusable_wrong(true_intent: str) -> str:
    """给定真实意图, 以业务贴近的方式抽一个错误意图 (60% 落在最易混淆对上)"""
    partners = CONFUSABLE_INTENTS.get(true_intent)
    if partners and random.random() < 0.6:
        return random.choice(partners)
    wrong = [i for i in PRIMARY_INTENTS if i != true_intent]
    return random.choice(wrong)


def gen_step1_intent_output(n: int = 5000, ticket_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成Step1意图识别输出数据 (production pipeline 输出, 使用 production prompt v5)

    主意图沿用工单 true_intent (~88% 与真实意图一致, ~12% 产生业务贴近的误判),
    保证主意图分布与分层抽样 (ER §7.3) 一致且覆盖全部意图类别。
    情绪/紧急度按 ER §7.3 目标分布加权采样 (含 satisfied / low)。
    processed_at 紧随 submitted_at (AI 秒级处理), 满足时序约束。
    """
    if ticket_df is None:
        raise ValueError("需要提供ticket数据")

    rows = ticket_df.select(["ticket_id", "raw_text", "true_intent", "submitted_at"]).to_dicts()[:n]

    # 情绪 / 紧急度目标分布 (ER §7.3)
    sentiments = ["neutral", "frustrated", "angry", "satisfied"]
    sentiment_weights = [0.50, 0.25, 0.20, 0.05]
    urgencies = ["low", "medium", "high"]
    urgency_weights = [0.30, 0.40, 0.30]

    records = []
    for i, row in enumerate(rows):
        ticket_id = row["ticket_id"]
        true_intent = row["true_intent"]
        submitted_at = row["submitted_at"]
        ticket_text = row["raw_text"]

        # 主意图: 88% 命中真实意图, 12% 业务贴近误判
        if random.random() < 0.88:
            primary_intent = true_intent
        else:
            primary_intent = _confusable_wrong(true_intent)

        # 次意图 (文本启发式, 仅作辅助信息)
        secondary = []
        if "退款" in ticket_text and primary_intent != "refund_request":
            secondary.append("refund_request")
        if "重发" in ticket_text or "重新发货" in ticket_text:
            secondary.append("reship_request")
        if "投诉" in ticket_text:
            secondary.append("complaint_logistics")

        sentiment = random.choices(sentiments, weights=sentiment_weights)[0]
        urgency = random.choices(urgencies, weights=urgency_weights)[0]

        # AI 秒级处理: processed_at = submitted_at + 1~4 秒 (始终晚于提交)
        processed_at = submitted_at + timedelta(seconds=random.randint(1, 4))

        records.append({
            "output_id": i + 1,
            "ticket_id": ticket_id,
            "prompt_id": 5,  # production Step1 prompt (v5)
            "processed_at": processed_at,
            "primary_intent": primary_intent,
            "secondary_intents": json.dumps(secondary, ensure_ascii=False),
            "sentiment": sentiment,
            "urgency": urgency,
            "reasoning": f"用户主要诉求为{primary_intent},情绪{sentiment},紧急度{urgency}。{fake.text(max_nb_chars=80)}",
            "latency_ms": random.randint(1200, 2500),
            "input_tokens": random.randint(350, 550),
            "output_tokens": random.randint(150, 250),
        })

    return pl.DataFrame(records)


def gen_step3_decision_output(n: int = 5000, ticket_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成Step3策略决策输出数据 (production pipeline 输出, 使用 production prompt v3)

    processed_at 紧随 step1 (再 +几秒), 始终晚于 submitted_at。
    rules_checked 覆盖 R001-R007 全部七条规则。
    """
    if ticket_df is None:
        raise ValueError("需要提供ticket数据")

    rows = ticket_df.select(["ticket_id", "submitted_at"]).to_dicts()[:n]
    actions = ["full_refund", "partial_refund", "reship", "transfer_to_merchant", "reject", "escalate_to_human"]
    all_rules = ["R001", "R002", "R003", "R004", "R005", "R006", "R007"]

    records = []
    for i, row in enumerate(rows):
        ticket_id = row["ticket_id"]
        submitted_at = row["submitted_at"]

        # 决策动作分布 (ER §7.3): escalate ~15% → AI 自动处理率 ~85%
        action = random.choices(actions, weights=[0.35, 0.05, 0.20, 0.15, 0.10, 0.15])[0]
        escalate = (action == "escalate_to_human")

        # 检查过的规则: 覆盖 R001-R007 全集中的一个子集
        checked = sorted(random.sample(all_rules, k=random.randint(4, 7)))

        # ~10% 概率违反规则 (从已检查规则中抽), 与 §2.5 七条规则一致
        violated = []
        if random.random() < 0.10:
            violated.append(random.choice(["R002", "R003", "R004", "R005", "R006", "R007"]))

        # processed_at = submitted_at + 5~9 秒 (晚于 step1 的 1~4 秒)
        processed_at = submitted_at + timedelta(seconds=random.randint(5, 9))

        records.append({
            "output_id": i + 1,
            "ticket_id": ticket_id,
            "prompt_id": 8,  # production Step3 prompt (v3)
            "processed_at": processed_at,
            "action": action,
            "rationale": f"综合评估后决定采取{action}。{fake.text(max_nb_chars=120)}",
            "confidence": round(random.uniform(0.65, 0.95), 2),
            "alternative_action": random.choice(["reship", "partial_refund", None]),
            "escalate_to_human": escalate,
            "rules_checked": json.dumps(checked, ensure_ascii=False),
            "rules_violated": json.dumps(violated, ensure_ascii=False),
            "latency_ms": random.randint(1800, 3000),
        })

    return pl.DataFrame(records)


def gen_annotation_ground_truth(n: int = 500, ticket_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成人工标注Ground Truth数据

    n = 评估样本工单数 (~500), 不是总工单数 (5000)。

    关键修复:
    - 评估样本改为"分层随机抽样": 从 2024-11-07 之前提交的工单中, 按 true_intent
      分层随机抽取 n 条 → 样本覆盖全部 7 个生成意图, 不再退化为单一 dispute_non_receipt。
      (限定早期提交是为了让标注/评估时序成立: 标注晚于提交, 又早于 2024-11-10 首次评估)
    - 真实意图直接取工单 true_intent 列 (不再用关键词反推)。
    - annotation_date 晚于工单 submitted_at (满足时序约束)。
    - 双人标注一致率 ~95% (两人直接对齐, 而非各自独立 95% 导致联合仅 ~90%)。
    """
    if ticket_df is None:
        raise ValueError("需要提供ticket数据")

    annotators = ["ANN001", "ANN002", "ANN003", "ANN004", "ANN005"]

    # 候选池: 早期提交的工单 (保证标注晚于提交、早于首次评估 2024-11-10)
    cutoff = datetime(2024, 11, 7)
    pool = ticket_df.filter(pl.col("submitted_at") <= cutoff).to_dicts()
    if len(pool) < n:  # 兜底: 候选不足则放宽到全量
        pool = ticket_df.to_dicts()

    # 按 true_intent 分层抽样, 各意图按其在候选池中的占比分配名额
    by_intent: dict[str, list] = {}
    for row in pool:
        by_intent.setdefault(row["true_intent"], []).append(row)

    sampled: list = []
    for intent, rows in by_intent.items():
        random.shuffle(rows)
        quota = max(1, round(n * len(rows) / len(pool)))
        sampled.extend(rows[:quota])
    random.shuffle(sampled)
    sampled = sampled[:n]

    records = []
    for row in sampled:
        ticket_id = row["ticket_id"]
        true_intent = row["true_intent"]
        submitted_at = row["submitted_at"]

        # 标注员 1 的标注: ~93% 命中真实意图, ~7% 业务贴近误判
        label1 = true_intent if random.random() < 0.93 else _confusable_wrong(true_intent)
        # 标注员 2: 95% 与标注员 1 一致 → 双人一致率 ~95%
        label2 = label1 if random.random() < 0.95 else _confusable_wrong(label1)

        # 标注日期: 提交后 1~2 天完成 (晚于工单, 早于 2024-11-10 首次评估)
        annotation_date = submitted_at + timedelta(days=random.randint(1, 2))

        for annotator, labeled_intent in zip(random.sample(annotators, k=2), [label1, label2]):
            records.append({
                "annotation_id": len(records) + 1,
                "ticket_id": ticket_id,
                "annotator_id": annotator,
                "annotation_date": annotation_date,
                "true_primary_intent": labeled_intent,
                "true_secondary_intents": json.dumps([], ensure_ascii=False),
                "true_sentiment": random.choices(
                    ["neutral", "frustrated", "angry", "satisfied"],
                    weights=[0.50, 0.25, 0.20, 0.05])[0],
                "true_urgency": random.choices(
                    ["low", "medium", "high"], weights=[0.30, 0.40, 0.30])[0],
                # 置信度分布 (ER §7.3): 60% level-3 / 35% level-2 / 5% level-1
                "annotator_confidence": random.choices([3, 2, 1], weights=[0.60, 0.35, 0.05])[0],
                "annotation_notes": fake.text(max_nb_chars=50) if random.random() < 0.15 else None,
                "annotation_version": "v2",
            })

    return pl.DataFrame(records)


def gen_annotation_agreement(annotation_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成标注一致性检查数据"""
    if annotation_df is None:
        raise ValueError("需要提供annotation数据")

    # 按ticket_id分组,找出有2个标注的
    grouped = annotation_df.group_by("ticket_id").agg([
        pl.col("annotation_id").alias("annotation_ids"),
        pl.col("true_primary_intent").alias("intents"),
    ])

    records = []
    for row in grouped.iter_rows(named=True):
        ticket_id = row["ticket_id"]
        annotation_ids = row["annotation_ids"]
        intents = row["intents"]

        if len(annotation_ids) == 2:
            is_agreement = (intents[0] == intents[1])
            records.append({
                "agreement_id": len(records) + 1,
                "ticket_id": ticket_id,
                "annotation_id_1": annotation_ids[0],
                "annotation_id_2": annotation_ids[1],
                "is_agreement": is_agreement,
                "disagreement_field": None if is_agreement else "primary_intent",
                "resolution_status": "resolved" if is_agreement else random.choice(["pending", "resolved", "escalated"]),
                "arbitrator_id": None if is_agreement else random.choice(["ARB001", "ARB002"]),
                "final_decision": None if is_agreement else intents[0],  # 仲裁选择第一个
            })

    return pl.DataFrame(records)


def gen_evaluation_run() -> pl.DataFrame:
    """生成 Evaluation 运行记录数据 (6 次运行, 覆盖 v1→v5 Prompt 迭代历程)"""
    records = [
        # Run 1: 基线 (baseline) - Step1 v1 + Step3 v1
        {
            "run_id": "eval_20241110_140000",
            "triggered_by": "manual",
            "step1_prompt_id": 1, "step3_prompt_id": 6,
            "dataset_version": "v2", "run_status": "completed",
            "started_at": datetime(2024, 11, 10, 14, 0, 0),
            "completed_at": datetime(2024, 11, 10, 14, 25, 30),
            "total_tickets_evaluated": 500,
            "step1_accuracy": 0.81, "step3_rule_violation_rate": 0.12,
            "step1_judge_avg_score": 3.2, "step3_judge_avg_score": 3.5,
        },
        # Run 2: Step1 v2 (修复 dispute_non_receipt 误判)
        {
            "run_id": "eval_20241112_093000",
            "triggered_by": "github_push",
            "step1_prompt_id": 2, "step3_prompt_id": 6,
            "dataset_version": "v2", "run_status": "completed",
            "started_at": datetime(2024, 11, 12, 9, 30, 0),
            "completed_at": datetime(2024, 11, 12, 9, 52, 15),
            "total_tickets_evaluated": 500,
            "step1_accuracy": 0.87, "step3_rule_violation_rate": 0.042,
            "step1_judge_avg_score": 3.8, "step3_judge_avg_score": 4.1,
        },
        # Run 3: Step1 v3 (优化 sentiment) + Step3 v2 (强调 R002)
        {
            "run_id": "eval_20241115_143000",
            "triggered_by": "github_push",
            "step1_prompt_id": 3, "step3_prompt_id": 7,
            "dataset_version": "v2", "run_status": "completed",
            "started_at": datetime(2024, 11, 15, 14, 30, 0),
            "completed_at": datetime(2024, 11, 15, 14, 53, 0),
            "total_tickets_evaluated": 500,
            "step1_accuracy": 0.875, "step3_rule_violation_rate": 0.040,
            "step1_judge_avg_score": 3.9, "step3_judge_avg_score": 4.2,
        },
        # Run 4: Step1 v4 (加入 few-shot 示例)
        {
            "run_id": "eval_20241119_100000",
            "triggered_by": "github_push",
            "step1_prompt_id": 4, "step3_prompt_id": 7,
            "dataset_version": "v2", "run_status": "completed",
            "started_at": datetime(2024, 11, 19, 10, 0, 0),
            "completed_at": datetime(2024, 11, 19, 10, 24, 30),
            "total_tickets_evaluated": 500,
            "step1_accuracy": 0.890, "step3_rule_violation_rate": 0.035,
            "step1_judge_avg_score": 4.0, "step3_judge_avg_score": 4.3,
        },
        # Run 5: production 候选版 - Step1 v5 + Step3 v3
        {
            "run_id": "eval_20241123_140000",
            "triggered_by": "manual",
            "step1_prompt_id": 5, "step3_prompt_id": 8,
            "dataset_version": "v2", "run_status": "completed",
            "started_at": datetime(2024, 11, 23, 14, 0, 0),
            "completed_at": datetime(2024, 11, 23, 14, 26, 45),
            "total_tickets_evaluated": 500,
            "step1_accuracy": 0.905, "step3_rule_violation_rate": 0.030,
            "step1_judge_avg_score": 4.1, "step3_judge_avg_score": 4.4,
        },
        # Run 6: 回归验证 (上线后, 同样的 v5 + v3 在新样本上)
        {
            "run_id": "eval_20241128_090000",
            "triggered_by": "scheduled",
            "step1_prompt_id": 5, "step3_prompt_id": 8,
            "dataset_version": "v2", "run_status": "completed",
            "started_at": datetime(2024, 11, 28, 9, 0, 0),
            "completed_at": datetime(2024, 11, 28, 9, 25, 20),
            "total_tickets_evaluated": 500,
            "step1_accuracy": 0.902, "step3_rule_violation_rate": 0.031,
            "step1_judge_avg_score": 4.1, "step3_judge_avg_score": 4.3,
        },
    ]
    return pl.DataFrame(records)


def gen_step1_eval_detail(
    ticket_df: pl.DataFrame,
    step1_output_df: pl.DataFrame,
    annotation_df: pl.DataFrame,
    eval_run_df: pl.DataFrame,
) -> pl.DataFrame:
    """生成 Step1 详细评估结果数据 - 对每个 completed run 生成 ~500 条评估明细

    对每次评估运行,从评估样本工单池中抽取 500 条做评估。
    根据该 run 的 target_accuracy (来自 evaluation_run.step1_accuracy),
    控制 is_correct 的比例,以匹配整体准确率指标。
    """
    # 预构建 ticket_id -> annotation_id, true_intent 查找 (取每条工单的第一个标注)
    annot_lookup = {}
    for row in annotation_df.iter_rows(named=True):
        ticket_id = row["ticket_id"]
        if ticket_id not in annot_lookup:
            annot_lookup[ticket_id] = (row["annotation_id"], row["true_primary_intent"])

    # 预构建 ticket_id -> output_id (用于关联 step1 输出)
    output_lookup = dict(zip(
        step1_output_df["ticket_id"].to_list(),
        step1_output_df["output_id"].to_list(),
    ))

    # 评估样本: 取已标注的 ticket_id (即 annot_lookup 的 key)
    sample_ticket_ids = list(annot_lookup.keys())
    all_intents = [
        "dispute_non_receipt", "dispute_damaged", "dispute_wrong_item",
        "refund_request", "exchange_request", "logistics_inquiry",
        "complaint_quality", "complaint_service", "policy_inquiry",
    ]

    records = []
    detail_id = 1

    for run_row in eval_run_df.iter_rows(named=True):
        if run_row["run_status"] != "completed":
            continue
        run_id = run_row["run_id"]
        target_acc = run_row["step1_accuracy"] or 0.85

        for ticket_id in sample_ticket_ids:
            if ticket_id not in output_lookup:
                continue
            annotation_id, true_intent = annot_lookup[ticket_id]
            output_id = output_lookup[ticket_id]

            # 按 target_accuracy 概率生成 is_correct
            is_correct = random.random() < target_acc
            if is_correct:
                predicted = true_intent
                reasoning_score = random.choice([4, 5])
                completeness_score = 1
            else:
                # 误判: 优先落在业务上最易混淆的意图对 (见 CONFUSABLE_INTENTS)
                predicted = _confusable_wrong(true_intent)
                reasoning_score = random.choice([2, 3])
                completeness_score = random.choice([0, 1])

            records.append({
                "eval_detail_id": detail_id,
                "run_id": run_id,
                "ticket_id": ticket_id,
                "output_id": output_id,
                "annotation_id": annotation_id,
                "predicted_intent": predicted,
                "true_intent": true_intent,
                "is_correct": is_correct,
                "judge_reasoning_score": reasoning_score,
                "judge_completeness_score": completeness_score,
                "judge_comment": fake.text(max_nb_chars=40) if random.random() < 0.2 else None,
            })
            detail_id += 1

    return pl.DataFrame(records)


def gen_step3_eval_detail(
    ticket_df: pl.DataFrame,
    step3_output_df: pl.DataFrame,
    annotation_df: pl.DataFrame,
    eval_run_df: pl.DataFrame,
) -> pl.DataFrame:
    """生成 Step3 详细评估结果数据 - 对每个 completed run 生成 ~500 条评估明细

    根据该 run 的 step3_rule_violation_rate 控制 rule_check_passed 的比例。
    """
    # 评估样本: 与 step1 一致, 取已标注的 ticket_id
    annotated_ticket_ids = list(annotation_df["ticket_id"].unique().to_list())

    # 预构建 ticket_id -> output_id 查找
    output_lookup = dict(zip(
        step3_output_df["ticket_id"].to_list(),
        step3_output_df["output_id"].to_list(),
    ))

    rule_candidates = ["R002", "R003", "R004", "R005"]
    records = []
    detail_id = 1

    for run_row in eval_run_df.iter_rows(named=True):
        if run_row["run_status"] != "completed":
            continue
        run_id = run_row["run_id"]
        target_violation_rate = run_row["step3_rule_violation_rate"] or 0.05

        for ticket_id in annotated_ticket_ids:
            if ticket_id not in output_lookup:
                continue
            output_id = output_lookup[ticket_id]

            # 按 target_violation_rate 概率生成违反
            violates = random.random() < target_violation_rate
            if violates:
                violated_rules = [random.choice(rule_candidates)]
                rule_check_passed = False
                severity = random.choice(["critical", "high", "medium"])
            else:
                violated_rules = []
                rule_check_passed = True
                severity = None

            rationale_completeness = random.choice([3, 4, 5])
            risk_awareness = 1 if rule_check_passed else random.choice([0, 1])
            overall_quality = random.choice([4, 5]) if rule_check_passed else random.choice([2, 3])

            records.append({
                "eval_detail_id": detail_id,
                "run_id": run_id,
                "ticket_id": ticket_id,
                "output_id": output_id,
                "rule_check_passed": rule_check_passed,
                "rules_violated": json.dumps(violated_rules, ensure_ascii=False),
                "violation_severity": severity,
                "judge_rationale_completeness": rationale_completeness,
                "judge_risk_awareness": risk_awareness,
                "judge_overall_quality": overall_quality,
                "judge_comment": fake.text(max_nb_chars=50) if random.random() < 0.15 else None,
            })
            detail_id += 1

    return pl.DataFrame(records)


def gen_confusion_matrix(step1_eval_detail_df: pl.DataFrame) -> pl.DataFrame:
    """生成混淆矩阵数据 - 直接从 step1_eval_detail 聚合派生 (关键修复)

    每行 = 某次评估运行里 (true_intent, predicted_intent) 的计数。
    这样混淆矩阵与评估明细严格一致: 每个 run 的合计 = 该 run 的评估样本数,
    且对角线/非对角线分布完全来自真实评估结果, 不再独立伪造。
    """
    grouped = (
        step1_eval_detail_df
        .group_by(["run_id", "true_intent", "predicted_intent"])
        .agg(pl.len().alias("count"))
        .sort(["run_id", "count"], descending=[False, True])
    )

    records = []
    matrix_id = 1
    for row in grouped.iter_rows(named=True):
        records.append({
            "matrix_id": matrix_id,
            "run_id": row["run_id"],
            "true_label": row["true_intent"],
            "predicted_label": row["predicted_intent"],
            "count": row["count"],
        })
        matrix_id += 1

    return pl.DataFrame(records)


def update_evaluation_run_metrics(
    eval_run_df: pl.DataFrame,
    step1_eval_detail_df: pl.DataFrame,
    step3_eval_detail_df: pl.DataFrame,
) -> pl.DataFrame:
    """用评估明细的真实聚合值, 回填 evaluation_run 的头部指标 (关键修复)

    保证 evaluation_run.step1_accuracy / step3_rule_violation_rate / judge 均分
    == 对应明细的聚合结果, 消除"头部硬编码 vs 明细重抽"的抽样噪声差异。
    """
    s1 = (
        step1_eval_detail_df
        .group_by("run_id")
        .agg([
            pl.col("is_correct").mean().alias("acc"),
            pl.col("judge_reasoning_score").mean().alias("s1_judge"),
        ])
    )
    s1_acc = dict(zip(s1["run_id"].to_list(), s1["acc"].to_list()))
    s1_judge = dict(zip(s1["run_id"].to_list(), s1["s1_judge"].to_list()))

    s3 = (
        step3_eval_detail_df
        .group_by("run_id")
        .agg([
            (1.0 - pl.col("rule_check_passed").mean()).alias("viol"),
            pl.col("judge_overall_quality").mean().alias("s3_judge"),
        ])
    )
    s3_viol = dict(zip(s3["run_id"].to_list(), s3["viol"].to_list()))
    s3_judge = dict(zip(s3["run_id"].to_list(), s3["s3_judge"].to_list()))

    rows = eval_run_df.to_dicts()
    for r in rows:
        rid = r["run_id"]
        if rid in s1_acc:
            r["step1_accuracy"] = round(s1_acc[rid], 4)
            r["step1_judge_avg_score"] = round(s1_judge[rid], 2)
        if rid in s3_viol:
            r["step3_rule_violation_rate"] = round(s3_viol[rid], 4)
            r["step3_judge_avg_score"] = round(s3_judge[rid], 2)
    return pl.DataFrame(rows)


def gen_prompt_comparison(
    eval_run_df: pl.DataFrame,
    step1_eval_detail_df: pl.DataFrame,
) -> pl.DataFrame:
    """生成 Prompt 版本对比数据 (15 条, 覆盖关键 A/B 对比)

    关键修复: baseline_value / experiment_value 直接回指 evaluation_run 的真实指标
    (step1_accuracy / step3_rule_violation_rate) 与 step1_eval_detail 的 per-intent 准确率,
    不再硬编码。这样 A/B 对比与 evaluation_run / eval_detail 严格自洽。
    """
    # 每个 run 的真实头部指标
    run_acc = dict(zip(eval_run_df["run_id"].to_list(), eval_run_df["step1_accuracy"].to_list()))
    run_viol = dict(zip(eval_run_df["run_id"].to_list(), eval_run_df["step3_rule_violation_rate"].to_list()))

    # 每个 run 中 dispute_non_receipt 的 per-intent 准确率 (来自明细)
    dnr = (
        step1_eval_detail_df
        .filter(pl.col("true_intent") == "dispute_non_receipt")
        .group_by("run_id")
        .agg(pl.col("is_correct").mean().alias("acc"))
    )
    run_dnr = dict(zip(dnr["run_id"].to_list(), dnr["acc"].to_list()))

    pairs = [
        # 基线 run, 实验 run, 对比日期
        ("eval_20241110_140000", "eval_20241112_093000", datetime(2024, 11, 12, 10, 30)),  # v1 → v2
        ("eval_20241112_093000", "eval_20241115_143000", datetime(2024, 11, 15, 15, 0)),   # v2 → v3
        ("eval_20241115_143000", "eval_20241119_100000", datetime(2024, 11, 19, 10, 30)),  # v3 → v4
        ("eval_20241119_100000", "eval_20241123_140000", datetime(2024, 11, 23, 14, 30)),  # v4 → v5
        ("eval_20241110_140000", "eval_20241123_140000", datetime(2024, 11, 24, 10, 0)),   # v1 → v5 (整体)
    ]
    # (指标名, 取值函数)
    metrics = [
        ("step1_accuracy", run_acc),
        ("dispute_non_receipt_accuracy", run_dnr),
        ("step3_rule_violation_rate", run_viol),
    ]
    records = []
    comparison_id = 1
    for metric_name, value_map in metrics:
        for baseline_run, exp_run, comp_date in pairs:
            baseline_value = round(value_map.get(baseline_run, 0.0), 4)
            experiment_value = round(value_map.get(exp_run, 0.0), 4)
            improvement_pct = round(
                (experiment_value - baseline_value) / baseline_value * 100, 1
            ) if baseline_value else 0.0
            records.append({
                "comparison_id": comparison_id,
                "baseline_run_id": baseline_run,
                "experiment_run_id": exp_run,
                "comparison_date": comp_date,
                "metric_name": metric_name,
                "baseline_value": baseline_value,
                "experiment_value": experiment_value,
                "improvement_pct": improvement_pct,
                "is_significant": abs(improvement_pct) >= 2.0,
            })
            comparison_id += 1
    return pl.DataFrame(records)


def gen_rule_violation_case(n: int = 150, ticket_df: pl.DataFrame = None) -> pl.DataFrame:
    """生成规则违反案例数据

    分布: v1 (60%) > v2 (20%) > v3 (10%) > v4 (5%) > v5 (5%) - 随版本迭代下降
    """
    if ticket_df is None:
        raise ValueError("需要提供ticket数据")

    ticket_ids = ticket_df["ticket_id"].to_list()
    # rule_id 加权: R002 (第三方商家转交) 最高频违反, R003 次之 (与 §1.3 / SQL Query 4 叙事一致)
    rule_ids = ["R002", "R003", "R004", "R005", "R006", "R007"]
    rule_weights = [0.35, 0.25, 0.13, 0.10, 0.09, 0.08]

    # 每条规则的违反语义 (violation_type / AI 错误决策 / 规则期望决策) — 保证三者业务自洽
    rule_semantics = {
        "R002": ("unauthorized_refund", ["full_refund", "partial_refund"], "transfer_to_merchant"),
        "R003": ("threshold_exceeded", ["full_refund", "reship"], "escalate_to_human"),
        "R004": ("missing_escalation", ["full_refund", "partial_refund"], "escalate_to_human"),
        "R005": ("premature_decision", ["full_refund", "reship"], "reject_dispute_pending_logistics"),
        "R006": ("missing_escalation", ["partial_refund", "reship"], "priority_full_refund"),
        "R007": ("premature_decision", ["full_refund", "reship"], "request_evidence"),
    }

    # 按 run 分布违反案例
    run_distribution = [
        ("eval_20241110_140000", "v2", 0.60, datetime(2024, 11, 10, 14, 20)),
        ("eval_20241112_093000", "v3", 0.20, datetime(2024, 11, 12, 9, 35)),
        ("eval_20241115_143000", "v4", 0.10, datetime(2024, 11, 15, 14, 35)),
        ("eval_20241119_100000", "v5", 0.05, datetime(2024, 11, 19, 10, 5)),
        ("eval_20241123_140000", None, 0.05, datetime(2024, 11, 23, 14, 5)),
    ]
    records = []
    case_id = 1

    for run_id, fix_version, ratio, base_time in run_distribution:
        run_n = int(n * ratio)
        for i in range(run_n):
            ticket_id = random.choice(ticket_ids)
            rule_id = random.choices(rule_ids, weights=rule_weights)[0]
            violation_type, ai_choices, expected_decision = rule_semantics[rule_id]
            records.append({
                "case_id": case_id,
                "run_id": run_id,
                "ticket_id": ticket_id,
                "rule_id": rule_id,
                "violation_type": violation_type,
                "ai_decision": random.choice(ai_choices),
                "expected_decision": expected_decision,
                "impact_severity": random.choice(["critical", "high", "medium", "low"]),
                "discovered_at": base_time + timedelta(minutes=i * 2),
                "fix_status": "fixed" if fix_version and random.random() < 0.75 else random.choice(["open", "wont_fix"]),
                "fix_prompt_version": fix_version if fix_version and random.random() < 0.75 else None,
            })
            case_id += 1
    return pl.DataFrame(records)


def gen_annotator() -> pl.DataFrame:
    """生成标注员信息数据 (10 人: 5 名标注员 + 3 名审核员 + 2 名仲裁员)"""
    records = [
        {"annotator_id": "ANN001", "annotator_name": "张晓月", "role": "annotator",
         "total_annotations": 250, "avg_confidence": 2.8, "agreement_rate": 0.92,
         "joined_date": datetime(2024, 10, 1)},
        {"annotator_id": "ANN002", "annotator_name": "李文强", "role": "annotator",
         "total_annotations": 240, "avg_confidence": 2.7, "agreement_rate": 0.89,
         "joined_date": datetime(2024, 10, 1)},
        {"annotator_id": "ANN003", "annotator_name": "王静怡", "role": "annotator",
         "total_annotations": 235, "avg_confidence": 2.9, "agreement_rate": 0.94,
         "joined_date": datetime(2024, 10, 5)},
        {"annotator_id": "ANN004", "annotator_name": "刘美琪", "role": "annotator",
         "total_annotations": 220, "avg_confidence": 2.6, "agreement_rate": 0.87,
         "joined_date": datetime(2024, 10, 8)},
        {"annotator_id": "ANN005", "annotator_name": "周一帆", "role": "annotator",
         "total_annotations": 215, "avg_confidence": 2.7, "agreement_rate": 0.90,
         "joined_date": datetime(2024, 10, 10)},
        {"annotator_id": "REV001", "annotator_name": "陈浩然", "role": "reviewer",
         "total_annotations": 180, "avg_confidence": 2.9, "agreement_rate": None,
         "joined_date": datetime(2024, 10, 5)},
        {"annotator_id": "REV002", "annotator_name": "孙立诚", "role": "reviewer",
         "total_annotations": 160, "avg_confidence": 2.9, "agreement_rate": None,
         "joined_date": datetime(2024, 10, 6)},
        {"annotator_id": "REV003", "annotator_name": "吴佳琪", "role": "reviewer",
         "total_annotations": 145, "avg_confidence": 2.85, "agreement_rate": None,
         "joined_date": datetime(2024, 10, 12)},
        {"annotator_id": "ARB001", "annotator_name": "赵建国", "role": "arbitrator",
         "total_annotations": 45, "avg_confidence": 3.0, "agreement_rate": None,
         "joined_date": datetime(2024, 9, 25)},
        {"annotator_id": "ARB002", "annotator_name": "钱守信", "role": "arbitrator",
         "total_annotations": 30, "avg_confidence": 3.0, "agreement_rate": None,
         "joined_date": datetime(2024, 9, 28)},
    ]
    return pl.DataFrame(records)


# ============================================================================
# 核心函数(幂等操作)
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有TSV文件。幂等操作:先删除已存在的文件"""
    # 确保数据目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 删除已存在的TSV文件
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("开始生成TSV文件...")

    # --- 枚举与配置 (无依赖) ---
    user_tier_df = gen_user_tier()
    seller_type_df = gen_seller_type()
    intent_category_df = gen_intent_category()
    decision_rule_df = gen_decision_rule()
    annotator_df = gen_annotator()
    prompt_version_df = gen_prompt_version()

    # --- 业务实体 ---
    user_df = gen_user(n=500)
    product_df = gen_product(n=200)
    order_df = gen_order(n=2000, user_df=user_df, product_df=product_df)

    # --- 工单 (主 fact 表 ~5000 条, 内部携带 true_intent 辅助列) ---
    raw_ticket_df = gen_raw_ticket(n=5000, user_df=user_df, order_df=order_df)

    # --- AI 输出 (每工单一条, 沿用 true_intent / submitted_at) ---
    step1_output_df = gen_step1_intent_output(n=5000, ticket_df=raw_ticket_df)
    step3_output_df = gen_step3_decision_output(n=5000, ticket_df=raw_ticket_df)

    # --- 标注 (分层随机抽样 500 条工单 × 2 标注员) ---
    annotation_df = gen_annotation_ground_truth(n=500, ticket_df=raw_ticket_df)
    annotation_agreement_df = gen_annotation_agreement(annotation_df=annotation_df)

    # 标注员工作量 rollup: 用实际标注条数回填 annotator.total_annotations (annotator 角色)
    annot_counts = (
        annotation_df.group_by("annotator_id").agg(pl.len().alias("cnt"))
    )
    count_map = dict(zip(annot_counts["annotator_id"].to_list(), annot_counts["cnt"].to_list()))
    annotator_rows = annotator_df.to_dicts()
    for r in annotator_rows:
        if r["annotator_id"] in count_map:  # 仅一线标注员真正参与了 GT 标注
            r["total_annotations"] = int(count_map[r["annotator_id"]])
    annotator_df = pl.DataFrame(annotator_rows)

    # --- 评估 ---
    eval_run_df = gen_evaluation_run()  # 头部指标先作为目标值驱动明细抽样
    step1_eval_detail_df = gen_step1_eval_detail(
        ticket_df=raw_ticket_df,
        step1_output_df=step1_output_df,
        annotation_df=annotation_df,
        eval_run_df=eval_run_df,
    )
    step3_eval_detail_df = gen_step3_eval_detail(
        ticket_df=raw_ticket_df,
        step3_output_df=step3_output_df,
        annotation_df=annotation_df,
        eval_run_df=eval_run_df,
    )
    # 关键修复: 用明细真实聚合回填 evaluation_run 头部指标 (头部 == 明细)
    eval_run_df = update_evaluation_run_metrics(
        eval_run_df, step1_eval_detail_df, step3_eval_detail_df
    )

    # 关键修复: 混淆矩阵从 step1_eval_detail 聚合派生 (与评估明细严格一致)
    confusion_matrix_df = gen_confusion_matrix(step1_eval_detail_df=step1_eval_detail_df)
    # 关键修复: A/B 对比回指 evaluation_run 实际指标 + 明细 per-intent 准确率
    prompt_comparison_df = gen_prompt_comparison(eval_run_df, step1_eval_detail_df)
    rule_violation_case_df = gen_rule_violation_case(n=150, ticket_df=raw_ticket_df)

    # 写 TSV 时丢弃工单内部辅助列 true_intent (不属于 raw_ticket schema)
    raw_ticket_tsv_df = raw_ticket_df.drop("true_intent")

    # 按拓扑排序组织输出 (无 FK 依赖的表优先)
    datasets = [
        ("01_user_tier.tsv", user_tier_df),
        ("02_seller_type.tsv", seller_type_df),
        ("03_intent_category.tsv", intent_category_df),
        ("04_decision_rule.tsv", decision_rule_df),
        ("05_annotator.tsv", annotator_df),
        ("06_prompt_version.tsv", prompt_version_df),
        ("07_user.tsv", user_df),
        ("08_product.tsv", product_df),
        ("09_order.tsv", order_df),
        ("10_raw_ticket.tsv", raw_ticket_tsv_df),
        ("11_step1_intent_output.tsv", step1_output_df),
        ("12_step3_decision_output.tsv", step3_output_df),
        ("13_annotation_ground_truth.tsv", annotation_df),
        ("14_annotation_agreement.tsv", annotation_agreement_df),
        ("15_evaluation_run.tsv", eval_run_df),
        ("16_step1_eval_detail.tsv", step1_eval_detail_df),
        ("17_step3_eval_detail.tsv", step3_eval_detail_df),
        ("18_confusion_matrix.tsv", confusion_matrix_df),
        ("19_prompt_comparison.tsv", prompt_comparison_df),
        ("20_rule_violation_case.tsv", rule_violation_case_df),
    ]

    # 写入所有TSV文件
    for filename, df in datasets:
        filepath = DATA_DIR / filename
        df.write_csv(filepath, separator="\t")
        print(f"✓ {filename}: {len(df)} 条记录")

    print(f"\n所有TSV文件已生成到: {DATA_DIR}")


def create_sqlite_database() -> None:
    """创建SQLite数据库。幂等操作:先删除已存在的数据库"""
    # 删除已存在的数据库
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        print(f"已删除旧数据库: {DATABASE_PATH}")

    # 创建引擎
    engine = create_engine(f"sqlite:///{DATABASE_PATH}")

    # 创建所有表
    Base.metadata.create_all(engine)
    print("数据库表结构已创建")

    # 从TSV读取数据并导入
    print("\n开始导入数据...")

    table_file_mapping = [
        (UserTier, "01_user_tier.tsv"),
        (SellerType, "02_seller_type.tsv"),
        (IntentCategory, "03_intent_category.tsv"),
        (DecisionRule, "04_decision_rule.tsv"),
        (Annotator, "05_annotator.tsv"),
        (PromptVersion, "06_prompt_version.tsv"),
        (User, "07_user.tsv"),
        (Product, "08_product.tsv"),
        (Order, "09_order.tsv"),
        (RawTicket, "10_raw_ticket.tsv"),
        (Step1IntentOutput, "11_step1_intent_output.tsv"),
        (Step3DecisionOutput, "12_step3_decision_output.tsv"),
        (AnnotationGroundTruth, "13_annotation_ground_truth.tsv"),
        (AnnotationAgreement, "14_annotation_agreement.tsv"),
        (EvaluationRun, "15_evaluation_run.tsv"),
        (Step1EvalDetail, "16_step1_eval_detail.tsv"),
        (Step3EvalDetail, "17_step3_eval_detail.tsv"),
        (ConfusionMatrix, "18_confusion_matrix.tsv"),
        (PromptComparison, "19_prompt_comparison.tsv"),
        (RuleViolationCase, "20_rule_violation_case.tsv"),
    ]

    with Session(engine) as session:
        for model_class, filename in table_file_mapping:
            filepath = DATA_DIR / filename
            df = pl.read_csv(filepath, separator="\t", try_parse_dates=True)

            # 转换为字典列表
            records = df.to_dicts()

            # 修复datetime字段 - Polars读取CSV时可能将datetime转为字符串
            for record in records:
                for key, value in record.items():
                    if isinstance(value, str) and ('_at' in key or '_date' in key):
                        # 尝试解析ISO格式的日期时间字符串
                        try:
                            from dateutil import parser
                            record[key] = parser.parse(value)
                        except:
                            pass

            # 批量插入
            objects = [model_class(**record) for record in records]
            session.add_all(objects)
            session.commit()

            print(f"✓ {model_class.__tablename__}: {len(objects)} 条记录已导入")

    print(f"\nSQLite数据库已创建: {DATABASE_PATH}")


def main() -> None:
    """主函数:执行所有生成步骤"""
    print("=" * 80)
    print("NestMart AI客服工单处理系统 - 数据生成器")
    print("=" * 80)
    print()

    # Step 1: 生成TSV文件
    generate_all_tsv()
    print()

    # Step 2: 创建SQLite数据库
    create_sqlite_database()
    print()

    print("=" * 80)
    print("数据生成完成!")
    print(f"TSV文件位置: {DATA_DIR}")
    print(f"SQLite数据库: {DATABASE_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
