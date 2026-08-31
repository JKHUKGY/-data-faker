"""
通信设备, 光纤焊接质量与成本控制数据集生成器
复杂度: High

业务背景:
NorthArc Photonics Manufacturing 是俄勒冈 Hillsboro 的光纤连接器制造商.
本数据集模拟工厂 12 个月 (2025-06-16 到 2026-06-15) 的 splice 生产数据,
支持 Senior Manufacturing Analyst 用 SQL 拆解八个业务问题:

业务陷阱清单 (与 02 ER 文档和 03 SQL queries 文档对齐):

1. electrode_wear: 电极对累计 splice > 2000 次后 reject 率显著上升.
   分桶 reject: 1.2% / 1.8% / 4.5% / 9.0% / 17.0% (0-1000, 1000-1800,
   1800-2200, 2200-2600, 2600+). 20% 的 attempts 在超寿命区段.
2. night_shift_drift: Day 1.8%, Swing 2.5%, Night 4.2%. 夜班产量 25%
   但贡献 42% 的 reject. 监督薄弱是根因.
3. bad_batch_MFG-2024-038: 该批次 cladding_diameter_std_dev_um=0.62
   (其他批次约 0.15), reject 率 ~12%. 共 280 根 splice 受影响, 50 根
   已交付 FTTH-CCom, 触发 6 条 high_loss_in_field 投诉.
4. skill_multicore_mismatch: multi_core 焊接的 junior 25% reject,
   intermediate 12%, senior 3%, expert 2%. 当前 30% 的 multi_core 任务
   分配给 junior + intermediate.
5. ai_alert_ignored: alert outcome=ignored 时下游 reject 35%,
   resolved 时 3%, escalated 时 8%. 夜班 ignored 比例约 28%.
6. over_quality_ftth: 内部 SOP 用 0.05 dB 一刀切判 reject, 但 FTTH 订单
   客户实际 spec 0.30 dB. FTTH 段 reject 里 99% 在客户那里合格.
7. calibration_overdue: 校准超 90 天的设备 reject 3.5% 到 5.5%, 在期 1.5%
   到 2.0%. 当前 30% 设备超期.
8. first_pass_yield: 88% 一次过, 9% 需 2 次 attempt, 3% 需 3 次. 每次
   retry 增加 ~$2 物料 + 工时 + 2 次电极服役.

每个陷阱在 splice_attempt.actual_loss_db 的计算公式里通过加权 penalty
注入. 03 SQL queries 文档里的对应查询会暴露这些偏置, 给出年化 dollar.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import Boolean
from sqlalchemy import create_engine
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


# ============================================================================
# 配置常量
# ============================================================================
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "telecom_equipment_fiber_splicing_quality_high.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里"今天"也用这个字面量.
REFERENCE_DATE = date(2026, 6, 15)

# 12 个月数据窗口
DATA_WINDOW_START = datetime(2025, 6, 16, 0, 0, 0)
DATA_WINDOW_END = datetime(2026, 6, 15, 23, 59, 59)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================================
# 业务校准常量
# 每一个常量都对应至少一个业务陷阱或一个行业惯例, 注释说明 why.
# ============================================================================

# Trap 1: 电极磨损惩罚.
# 厂家推荐电极对寿命 2000 splice, 超过后电弧温度漂移导致 loss 上升.
# 这组 penalty 的目标是产出分桶 reject 率: 1.2% / 1.8% / 4.5% / 9.0% / 17.0%.
ELECTRODE_WEAR_PENALTY_DB = {
    "le_1000": 0.000,   # 全新电极
    "1000_1800": 0.002, # 健康区, 轻微漂移
    "1800_2200": 0.010, # 拐点附近
    "2200_2600": 0.028, # 老化区
    "gt_2600": 0.060,   # 严重过期, 应该早就换掉
}

# Trap 2: 班次惩罚. Day 监督最严, Swing 中等, Night 没有 senior 在场.
# 目标 reject: Day 1.8%, Swing 2.5%, Night 4.2%.
SHIFT_LOSS_PENALTY_DB = {
    "SH-D": 0.000,
    "SH-S": 0.003,
    "SH-N": 0.009,
}

# Trap 3: 坏批次 MFG-2024-038 的 cladding 方差异常 (0.62 vs 正常 0.15).
# 大方差导致对齐困难和 splice loss 升高. 目标 reject ~12%.
BAD_BATCH_ID = "MFG-2024-038"
BAD_BATCH_CLADDING_STD = 0.62
NORMAL_BATCH_CLADDING_STD_RANGE = (0.10, 0.20)
BAD_BATCH_LOSS_PENALTY_DB = 0.038

# Trap 4: skill × multi_core 错配. 多核需要多 core 同时对齐.
# junior 训练不足, 失败率指数级上升.
SKILL_MULTICORE_PENALTY_DB = {
    "junior": 0.058,
    "intermediate": 0.027,
    "senior": 0.002,
    "expert": 0.000,
}

# 非多核 (single, multi mode) 的 skill 差距较小, 主要看熟练度.
SKILL_REGULAR_PENALTY_DB = {
    "junior": 0.004,
    "intermediate": 0.001,
    "senior": 0.000,
    "expert": 0.000,
}

# Trap 5: AI 告警 outcome 概率. resolved 占 75%, ignored 15%, escalated 10%.
# 夜班 ignored 比例额外提升.
ALERT_OUTCOME_BASE_WEIGHTS = {
    "resolved": 0.75,
    "escalated": 0.10,
    "ignored": 0.15,
}
ALERT_OUTCOME_NIGHT_WEIGHTS = {
    "resolved": 0.55,
    "escalated": 0.17,
    "ignored": 0.28,
}

# ignored 告警下游 attempt 不再重试, 直接成为 final_reject 的概率提升.
# 这条规则也产生 Q12, Q13 的 reject 率差异.
IGNORED_ALERT_REJECT_PROB = 0.30  # 在 ignored 路径上, 该 splice 强制成 reject 的概率

# Trap 6: 客户 spec. 三个 segment 用三个不同 loss threshold.
SEGMENT_LOSS_THRESHOLD_DB = {
    "hyperscale_datacenter": 0.05,
    "enterprise_network": 0.10,
    "ftth_carrier": 0.30,
}

# Trap 7: 校准超期惩罚. SOP 是 90 天, 超过后设备参数漂移.
CALIBRATION_PENALTY_DB = {
    "le_60": 0.000,
    "60_90": 0.002,
    "90_120": 0.008,
    "gt_120": 0.018,
}

# Trap 8: First-pass yield. 88% 一次过, 9% 两次, 3% 三次.
# attempt_count 由 attempt-level grade 自动决定 (A/B 接受, C/Reject retry).
FPY_TARGET = 0.88

# 损耗模型的几何系数.
BASE_LOSS_DB = 0.008
ALIGNMENT_COEF_DB = 0.06       # 乘以 core_to_core_distance_um
ANGLE_COEF_DB = 0.005          # 乘以 angle_deviation_deg
CLEAVE_COEF_DB = 0.004         # 乘以 left + right cleave 总和
HUMIDITY_HIGH_THRESHOLD_PCT = 60.0
HUMIDITY_HIGH_PENALTY_DB = 0.003
ARC_DEVIATION_COEF_DB = 0.002  # 乘以 |arc_power - 12.5|

# 物理噪声 sigma. 控制总体方差, 同时影响 grade 边界附近的分布形状.
NOISE_SIGMA_DB = 0.014

# Grade 阈值.
GRADE_A_THRESHOLD = 0.02
GRADE_B_THRESHOLD = 0.05
GRADE_C_THRESHOLD = 0.08

# 行业惯例: 单对电极 list price $180, 寿命 2000 splice.
ELECTRODE_PAIR_PRICE_USD = 180.00
ELECTRODE_PAIR_LIFETIME = 2000
CLEAVER_BLADE_PRICE_USD = 245.00
CLEAVER_BLADE_LIFETIME = 24000

# 每次 splice 消耗的光纤长度. 物理上每次切割损耗 0.2 米, 左右两根共 0.4 米.
FIBER_CONSUMED_PER_SPLICE_M = 0.4
SPLICE_PROTECTOR_COST_USD = 0.32

# 设备折旧摊销, 按每分钟. 月折旧约 $400, 每天 16 工时 (双班), 月 30 天.
# $400 / (30 * 16 * 60) = $0.014 per minute. 每次 attempt 取 1.5 分钟.
MACHINE_COST_PER_MINUTE_USD = 0.014
TYPICAL_ATTEMPT_MINUTES = 1.5

# 行数目标. ER 文档 22 节里的"文件清单" 同步.
N_FIBER_SPEC = 5
N_CONSUMABLE = 6
N_CUSTOMER = 12
N_SHIFT = 3
N_FIBER_BATCH = 60
N_EQUIPMENT = 12
N_OPERATOR = 30
N_CUSTOMER_ORDER = 250
N_FIBER_SPOOL = 400
N_MAINTENANCE = 150
N_SPLICE_JOB = 800
# splice_record 在 50,000 量级, 实际由 jobs.completed_splice_count 累加.
N_QUALITY_ALERT_TARGET = 5000
N_QA_AUDIT_TARGET = 2500
N_CUSTOMER_COMPLAINT = 30


# ============================================================================
# SQLAlchemy ORM 模型
# ============================================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""

    pass


class FiberSpec(Base):
    """光纤规格目录, 5 行. 决定 BOM 成本和焊接难度."""

    __tablename__ = "fiber_spec"

    spec_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    spec_name: Mapped[str] = mapped_column(String(80), nullable=False)
    mode_type: Mapped[str] = mapped_column(String(20), nullable=False)
    core_count: Mapped[int] = mapped_column(Integer, nullable=False)
    target_cladding_diameter_um: Mapped[float] = mapped_column(Float, nullable=False)
    target_mfd_um: Mapped[float] = mapped_column(Float, nullable=False)
    applications: Mapped[str] = mapped_column(String(120), nullable=False)
    bom_cost_per_meter_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)


class ConsumablePrice(Base):
    """耗材价格表, 6 行. 用于成本摊销."""

    __tablename__ = "consumable_price"

    consumable_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    consumable_name: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    typical_lifetime_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    last_updated: Mapped[date] = mapped_column(Date, nullable=False)


class Customer(Base):
    """客户主表, 12 个客户分 3 个 segment. 决定订单 spec 严格度."""

    __tablename__ = "customer"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_code: Mapped[str] = mapped_column(String(40), nullable=False)
    segment: Mapped[str] = mapped_column(String(40), nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    relationship_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_value_annual_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class Shift(Base):
    """班次定义, 3 行. has_senior_supervisor 是 Q3 夜班问题的组织根源."""

    __tablename__ = "shift"

    shift_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    shift_name: Mapped[str] = mapped_column(String(20), nullable=False)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    supervisor_name: Mapped[str] = mapped_column(String(80), nullable=False)
    has_senior_supervisor: Mapped[bool] = mapped_column(Boolean, nullable=False)


class FiberBatch(Base):
    """光纤采购批次. MFG-2024-038 是嵌入的坏批次."""

    __tablename__ = "fiber_batch"

    batch_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(40), nullable=False)
    spec_id: Mapped[str] = mapped_column(ForeignKey("fiber_spec.spec_id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    spool_count: Mapped[int] = mapped_column(Integer, nullable=False)
    length_per_spool_m: Mapped[int] = mapped_column(Integer, nullable=False)
    qc_release_status: Mapped[str] = mapped_column(String(20), nullable=False)
    cladding_diameter_std_dev_um: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_per_meter_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    notes: Mapped[str] = mapped_column(String(200), nullable=True)


class Equipment(Base):
    """焊接设备. 校准超期和电极磨损是两个独立的设备级故事."""

    __tablename__ = "equipment"

    equipment_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(40), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    depreciation_monthly_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    location: Mapped[str] = mapped_column(String(20), nullable=False)
    last_calibration_date: Mapped[date] = mapped_column(Date, nullable=False)
    calibration_interval_days_sop: Mapped[int] = mapped_column(Integer, nullable=False)
    total_splice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class Operator(Base):
    """操作员. skill_level + multi_core_certified 决定能不能接什么活."""

    __tablename__ = "operator"

    operator_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    skill_level: Mapped[str] = mapped_column(String(20), nullable=False)
    certification_date: Mapped[date] = mapped_column(Date, nullable=False)
    default_shift_id: Mapped[str] = mapped_column(ForeignKey("shift.shift_id"), nullable=False)
    hourly_rate_usd: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    multi_core_certified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    department: Mapped[str] = mapped_column(String(40), nullable=False)


class CustomerOrder(Base):
    """客户订单. loss_threshold_db 是 Q5 spec 松绑的核心字段."""

    __tablename__ = "customer_order"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customer.customer_id"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    promised_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    product_code: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_cables: Mapped[int] = mapped_column(Integer, nullable=False)
    splices_required: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    loss_threshold_db: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class FiberSpool(Base):
    """光纤物理卷盘, 库存最小单位."""

    __tablename__ = "fiber_spool"

    spool_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("fiber_batch.batch_id"), nullable=False)
    spec_id: Mapped[str] = mapped_column(ForeignKey("fiber_spec.spec_id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    remaining_length_m: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class MaintenanceEvent(Base):
    """设备维护日志, 含 calibration."""

    __tablename__ = "maintenance_event"

    event_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.equipment_id"), nullable=False)
    event_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    parts_cost_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    labor_cost_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str] = mapped_column(String(200), nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=True)


class SpliceJob(Base):
    """生产批次, 一个 operator 在一台设备上的一次作业."""

    __tablename__ = "splice_job"

    job_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("customer_order.order_id"), nullable=False)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.equipment_id"), nullable=False)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operator.operator_id"), nullable=False)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shift.shift_id"), nullable=False)
    planned_start_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_end_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_start_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_end_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    target_splice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_splice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class ElectrodeReplacement(Base):
    """电极更换日志. 当前 SOP 是 reactive, splices_on_old_pair 大多超 2000."""

    __tablename__ = "electrode_replacement"

    replacement_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.equipment_id"), nullable=False)
    replacement_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    splices_on_old_pair: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    new_pair_part_number: Mapped[str] = mapped_column(String(40), nullable=False)
    new_pair_cost_usd: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    replaced_by_operator_id: Mapped[str] = mapped_column(ForeignKey("operator.operator_id"), nullable=False)


class SpliceRecord(Base):
    """焊接记录主表. final_attempt_id 是逻辑引用, 无声明式 FK 避免循环."""

    __tablename__ = "splice_record"

    splice_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("splice_job.job_id"), nullable=False)
    left_spool_id: Mapped[str] = mapped_column(ForeignKey("fiber_spool.spool_id"), nullable=False)
    right_spool_id: Mapped[str] = mapped_column(ForeignKey("fiber_spool.spool_id"), nullable=False)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.equipment_id"), nullable=False)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operator.operator_id"), nullable=False)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shift.shift_id"), nullable=False)
    planned_position_in_job: Mapped[int] = mapped_column(Integer, nullable=False)
    started_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    final_attempt_id: Mapped[str] = mapped_column(String(20), nullable=True)
    final_loss_db: Mapped[float] = mapped_column(Float, nullable=False)
    final_grade: Mapped[str] = mapped_column(String(10), nullable=False)
    meets_customer_spec: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ai_alert_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    image_path: Mapped[str] = mapped_column(String(200), nullable=True)


class SpliceAttempt(Base):
    """焊接尝试细节. equipment_electrode_count 是 Q2 关键切分维度."""

    __tablename__ = "splice_attempt"

    attempt_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    splice_id: Mapped[str] = mapped_column(ForeignKey("splice_record.splice_id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    left_core_offset_x_um: Mapped[float] = mapped_column(Float, nullable=False)
    left_core_offset_y_um: Mapped[float] = mapped_column(Float, nullable=False)
    right_core_offset_x_um: Mapped[float] = mapped_column(Float, nullable=False)
    right_core_offset_y_um: Mapped[float] = mapped_column(Float, nullable=False)
    core_to_core_distance_um: Mapped[float] = mapped_column(Float, nullable=False)
    angle_deviation_deg: Mapped[float] = mapped_column(Float, nullable=False)
    left_cleave_angle_deg: Mapped[float] = mapped_column(Float, nullable=False)
    right_cleave_angle_deg: Mapped[float] = mapped_column(Float, nullable=False)
    arc_power_mw: Mapped[float] = mapped_column(Float, nullable=False)
    arc_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    prefusion_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    overlap_um: Mapped[float] = mapped_column(Float, nullable=False)
    ambient_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_percent: Mapped[float] = mapped_column(Float, nullable=False)
    equipment_electrode_count: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_loss_db: Mapped[float] = mapped_column(Float, nullable=False)
    actual_loss_db: Mapped[float] = mapped_column(Float, nullable=False)
    attempt_grade: Mapped[str] = mapped_column(String(10), nullable=False)
    attempt_outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    material_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    labor_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    machine_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    consumable_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)


class QualityAlert(Base):
    """AI 质量告警. outcome=ignored 时下游 reject 35%."""

    __tablename__ = "quality_alert"

    alert_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("splice_attempt.attempt_id"), nullable=False)
    alert_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    predicted_loss_db: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_db: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(40), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=True)
    resolution_ts: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class ModelPredictionLog(Base):
    """AI 模型预测日志, 每个 attempt 一条."""

    __tablename__ = "model_prediction_log"

    prediction_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("splice_attempt.attempt_id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    input_features: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_loss_db: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    feature_importance: Mapped[str] = mapped_column(Text, nullable=False)


class QAAudit(Base):
    """QA 抽检, 用 OTDR 复测 5% 样本对比 operator 自评."""

    __tablename__ = "qa_audit"

    audit_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    splice_id: Mapped[str] = mapped_column(ForeignKey("splice_record.splice_id"), nullable=False)
    audit_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    auditor_name: Mapped[str] = mapped_column(String(80), nullable=False)
    operator_self_grade: Mapped[str] = mapped_column(String(10), nullable=False)
    qa_measured_loss_db: Mapped[float] = mapped_column(Float, nullable=False)
    qa_grade: Mapped[str] = mapped_column(String(10), nullable=False)
    grade_match: Mapped[bool] = mapped_column(Boolean, nullable=False)
    variance_db: Mapped[float] = mapped_column(Float, nullable=False)


class CustomerComplaint(Base):
    """客户投诉. linked_batch_id 给召回评估提供反查路径."""

    __tablename__ = "customer_complaint"

    complaint_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customer.customer_id"), nullable=False)
    order_id: Mapped[str] = mapped_column(ForeignKey("customer_order.order_id"), nullable=True)
    complaint_date: Mapped[date] = mapped_column(Date, nullable=False)
    complaint_type: Mapped[str] = mapped_column(String(40), nullable=False)
    linked_splice_id: Mapped[str] = mapped_column(ForeignKey("splice_record.splice_id"), nullable=True)
    linked_batch_id: Mapped[str] = mapped_column(ForeignKey("fiber_batch.batch_id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_impact_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


# ============================================================================
# 辅助计算函数
# ============================================================================
def calibration_bucket(days_since_cal: int) -> str:
    """把校准距今天数归到 4 个桶, 跟 CALIBRATION_PENALTY_DB 对齐."""
    if days_since_cal <= 60:
        return "le_60"
    elif days_since_cal <= 90:
        return "60_90"
    elif days_since_cal <= 120:
        return "90_120"
    else:
        return "gt_120"


def electrode_bucket(electrode_count: int) -> str:
    """电极使用次数分桶, 跟 ELECTRODE_WEAR_PENALTY_DB 对齐."""
    if electrode_count <= 1000:
        return "le_1000"
    elif electrode_count <= 1800:
        return "1000_1800"
    elif electrode_count <= 2200:
        return "1800_2200"
    elif electrode_count <= 2600:
        return "2200_2600"
    else:
        return "gt_2600"


def compute_actual_loss(
    core_distance_um: float,
    angle_dev_deg: float,
    cleave_total_deg: float,
    electrode_count: int,
    batch_std_dev: float,
    shift_id: str,
    skill_level: str,
    mode_type: str,
    humidity_pct: float,
    arc_power_mw: float,
    days_since_cal: int,
) -> float:
    """
    依据多因素物理模型计算 actual_loss_db.

    每一项都对应一个业务陷阱, 写在常量里. 输出是 LID 算法估算的 loss
    (单位 dB), 跟真实 OTDR 测量值有 ±0.005 dB 偏差, 真实测量由 QA 补.
    """
    base = BASE_LOSS_DB
    alignment_term = core_distance_um * ALIGNMENT_COEF_DB
    angle_term = angle_dev_deg * ANGLE_COEF_DB
    cleave_term = cleave_total_deg * CLEAVE_COEF_DB

    electrode_term = ELECTRODE_WEAR_PENALTY_DB[electrode_bucket(electrode_count)]
    shift_term = SHIFT_LOSS_PENALTY_DB[shift_id]

    if mode_type == "multi_core":
        skill_term = SKILL_MULTICORE_PENALTY_DB[skill_level]
    else:
        skill_term = SKILL_REGULAR_PENALTY_DB[skill_level]

    batch_term = BAD_BATCH_LOSS_PENALTY_DB if batch_std_dev > 0.5 else 0.0
    humidity_term = HUMIDITY_HIGH_PENALTY_DB if humidity_pct > HUMIDITY_HIGH_THRESHOLD_PCT else 0.0
    arc_term = abs(arc_power_mw - 12.5) * ARC_DEVIATION_COEF_DB
    cal_term = CALIBRATION_PENALTY_DB[calibration_bucket(days_since_cal)]

    noise = random.gauss(0, NOISE_SIGMA_DB)

    loss = (
        base + alignment_term + angle_term + cleave_term
        + electrode_term + shift_term + skill_term
        + batch_term + humidity_term + arc_term + cal_term
        + noise
    )
    return max(0.001, loss)


def grade_from_loss(loss_db: float) -> str:
    """按 SOP 阈值给 splice attempt 打等级."""
    if loss_db <= GRADE_A_THRESHOLD:
        return "A"
    elif loss_db <= GRADE_B_THRESHOLD:
        return "B"
    elif loss_db <= GRADE_C_THRESHOLD:
        return "C"
    else:
        return "Reject"


# ============================================================================
# 生成器函数, 按拓扑顺序
# ============================================================================
def gen_fiber_spec() -> pl.DataFrame:
    """5 种光纤规格. multi_core (MCF-4C) 是 Q4 错配的核心数据."""
    records = [
        {
            "spec_id": "SMF-G652D",
            "spec_name": "Standard Single-Mode G.652.D",
            "mode_type": "single",
            "core_count": 1,
            "target_cladding_diameter_um": 125.0,
            "target_mfd_um": 10.4,
            "applications": "Long-haul telecom, FTTH backbone",
            "bom_cost_per_meter_usd": 0.18,
        },
        {
            "spec_id": "SMF-G657A1",
            "spec_name": "Bend-Insensitive Single-Mode G.657.A1",
            "mode_type": "single",
            "core_count": 1,
            "target_cladding_diameter_um": 125.0,
            "target_mfd_um": 9.2,
            "applications": "FTTH drop, high-density patching",
            "bom_cost_per_meter_usd": 0.34,
        },
        {
            "spec_id": "MMF-OM4",
            "spec_name": "Multi-Mode OM4",
            "mode_type": "multi",
            "core_count": 1,
            "target_cladding_diameter_um": 125.0,
            "target_mfd_um": 50.0,
            "applications": "Datacenter 10G to 100G",
            "bom_cost_per_meter_usd": 0.42,
        },
        {
            "spec_id": "MMF-OM5",
            "spec_name": "Multi-Mode OM5 Wide-Band",
            "mode_type": "multi",
            "core_count": 1,
            "target_cladding_diameter_um": 125.0,
            "target_mfd_um": 50.0,
            "applications": "Datacenter SWDM 100G to 400G",
            "bom_cost_per_meter_usd": 0.58,
        },
        {
            "spec_id": "MCF-4C",
            "spec_name": "Multi-Core 4-Channel",
            "mode_type": "multi_core",
            "core_count": 4,
            "target_cladding_diameter_um": 125.0,
            "target_mfd_um": 9.6,
            "applications": "400G to 800G AI cluster optics",
            "bom_cost_per_meter_usd": 4.80,
        },
    ]
    return pl.DataFrame(records)


def gen_consumable_price() -> pl.DataFrame:
    """6 种耗材的当前价目表. 用于 Q1 总成本拆分."""
    records = [
        {
            "consumable_id": "ELEC-FSM100",
            "consumable_name": "Electrode Pair, Fujikura FSM-100P",
            "unit_price_usd": ELECTRODE_PAIR_PRICE_USD,
            "typical_lifetime_uses": ELECTRODE_PAIR_LIFETIME,
            "last_updated": date(2025, 12, 1),
        },
        {
            "consumable_id": "BLADE-CT50",
            "consumable_name": "Cleaver Blade, Sumitomo CT-50",
            "unit_price_usd": CLEAVER_BLADE_PRICE_USD,
            "typical_lifetime_uses": CLEAVER_BLADE_LIFETIME,
            "last_updated": date(2025, 12, 1),
        },
        {
            "consumable_id": "IPA-BTL500",
            "consumable_name": "Isopropyl Alcohol 500ml",
            "unit_price_usd": 12.50,
            "typical_lifetime_uses": 800,
            "last_updated": date(2025, 8, 15),
        },
        {
            "consumable_id": "WIPE-BOX",
            "consumable_name": "Lint-Free Wipe, 200 per box",
            "unit_price_usd": 28.00,
            "typical_lifetime_uses": 200,
            "last_updated": date(2025, 8, 15),
        },
        {
            "consumable_id": "PROT-SP60",
            "consumable_name": "Splice Protector 60mm, 100 per pack",
            "unit_price_usd": 32.00,
            "typical_lifetime_uses": 100,
            "last_updated": date(2025, 8, 15),
        },
        {
            "consumable_id": "CAL-FIBER",
            "consumable_name": "Calibration Fiber Reference",
            "unit_price_usd": 480.00,
            "typical_lifetime_uses": 30,
            "last_updated": date(2025, 6, 1),
        },
    ]
    return pl.DataFrame(records)


def gen_customer() -> pl.DataFrame:
    """12 个客户, 三个 segment 各 4 个. 代号是内部命名."""
    customer_data = [
        # hyperscale_datacenter, spec 0.05
        ("DC-Alpha", "hyperscale_datacenter", "US-West", 12500000),
        ("DC-Bravo", "hyperscale_datacenter", "US-West", 9800000),
        ("DC-Charlie", "hyperscale_datacenter", "US-Central", 7600000),
        ("DC-Delta", "hyperscale_datacenter", "US-East", 6200000),
        # ftth_carrier, spec 0.30
        ("FTTH-CCom", "ftth_carrier", "US-Central", 4200000),
        ("FTTH-Pioneer", "ftth_carrier", "US-East", 3800000),
        ("FTTH-Maple", "ftth_carrier", "Canada", 2900000),
        ("FTTH-Sunset", "ftth_carrier", "US-West", 2400000),
        # enterprise_network, spec 0.10
        ("ENT-Helix", "enterprise_network", "US-East", 850000),
        ("ENT-Quantum", "enterprise_network", "US-West", 720000),
        ("ENT-Nordic", "enterprise_network", "Canada", 480000),
        ("ENT-Ranger", "enterprise_network", "US-Central", 360000),
    ]
    records = []
    for i, (code, segment, region, contract) in enumerate(customer_data, start=1):
        relationship_start = REFERENCE_DATE - timedelta(days=random.randint(400, 2200))
        records.append({
            "customer_id": f"CUS-{i:03d}",
            "customer_code": code,
            "segment": segment,
            "region": region,
            "relationship_start_date": relationship_start,
            "contract_value_annual_usd": float(contract),
        })
    return pl.DataFrame(records)


def gen_shift() -> pl.DataFrame:
    """3 个班次. Night 没有 senior supervisor, 这是 Q3 根因."""
    records = [
        {
            "shift_id": "SH-D",
            "shift_name": "Day",
            "start_hour": 8,
            "end_hour": 16,
            "supervisor_name": "Daniel O'Brien",
            "has_senior_supervisor": True,
        },
        {
            "shift_id": "SH-S",
            "shift_name": "Swing",
            "start_hour": 16,
            "end_hour": 0,
            "supervisor_name": "Rebecca Chao",
            "has_senior_supervisor": True,
        },
        {
            "shift_id": "SH-N",
            "shift_name": "Night",
            "start_hour": 0,
            "end_hour": 8,
            "supervisor_name": "Trevor Lindgren",
            "has_senior_supervisor": False,
        },
    ]
    return pl.DataFrame(records)


def gen_fiber_batch() -> pl.DataFrame:
    """60 个采购批次. 包含 1 个坏批次 MFG-2024-038."""
    suppliers = ["CorningStock", "SumiOptics"]
    spec_weights = {
        "SMF-G652D": 0.45,
        "SMF-G657A1": 0.20,
        "MMF-OM4": 0.15,
        "MMF-OM5": 0.10,
        "MCF-4C": 0.10,
    }
    spec_ids = list(spec_weights.keys())
    weights = list(spec_weights.values())

    records = []
    # 先生成 59 个正常批次
    for i in range(1, 60):
        spec_id = random.choices(spec_ids, weights)[0]
        supplier = random.choice(suppliers)
        received = REFERENCE_DATE - timedelta(days=random.randint(7, 365))
        spec_unit_cost = {
            "SMF-G652D": 0.18,
            "SMF-G657A1": 0.34,
            "MMF-OM4": 0.42,
            "MMF-OM5": 0.58,
            "MCF-4C": 4.80,
        }[spec_id]
        std_dev = round(
            random.uniform(*NORMAL_BATCH_CLADDING_STD_RANGE), 3
        )
        records.append({
            "batch_id": f"MFG-{received.year}-{i:03d}",
            "supplier_name": supplier,
            "spec_id": spec_id,
            "received_date": received,
            "spool_count": random.randint(10, 30),
            "length_per_spool_m": 25000,
            "qc_release_status": random.choices(
                ["passed", "conditional"], [0.92, 0.08]
            )[0],
            "cladding_diameter_std_dev_um": std_dev,
            "unit_price_per_meter_usd": round(spec_unit_cost * random.uniform(0.95, 1.05), 4),
            "notes": None,
        })

    # 再插入坏批次 MFG-2024-038
    records.append({
        "batch_id": BAD_BATCH_ID,
        "supplier_name": "SumiOptics",
        "spec_id": "SMF-G652D",
        "received_date": date(2025, 11, 22),
        "spool_count": 15,
        "length_per_spool_m": 25000,
        "qc_release_status": "conditional",
        "cladding_diameter_std_dev_um": BAD_BATCH_CLADDING_STD,
        "unit_price_per_meter_usd": 0.17,
        "notes": "Supplier reported elevated cladding variance. Released conditionally.",
    })

    return pl.DataFrame(records)


def gen_equipment() -> pl.DataFrame:
    """12 台 fusion splicer. 约 30% 校准超期是 Q7 数据."""
    models = ["Fujikura FSM-100P", "Sumitomo T-72C", "FITEL S179A", "Furukawa S185"]
    locations = ["Line-A", "Line-B", "Line-C", "Line-D"]

    records = []
    for i in range(1, N_EQUIPMENT + 1):
        purchase_date = REFERENCE_DATE - timedelta(days=random.randint(180, 1800))
        purchase_cost = round(random.uniform(28000, 42000), 2)

        # 30% 校准超期, 70% 在期. 在期内均匀分布 0 到 90 天, 超期则 90 到 180.
        if random.random() < 0.30:
            cal_days_ago = random.randint(91, 180)
        else:
            cal_days_ago = random.randint(0, 89)
        last_cal = REFERENCE_DATE - timedelta(days=cal_days_ago)

        # 累计 splice 数会在 splice 生成完后回填.
        records.append({
            "equipment_id": f"EQ-{i:03d}",
            "model": random.choice(models),
            "serial_number": f"SN-{random.randint(100000, 999999)}",
            "purchase_date": purchase_date,
            "purchase_cost_usd": purchase_cost,
            "depreciation_monthly_usd": round(purchase_cost / 60, 2),
            "location": locations[(i - 1) % len(locations)],
            "last_calibration_date": last_cal,
            "calibration_interval_days_sop": 90,
            "total_splice_count": 0,  # placeholder, 回填
            "status": random.choices(
                ["active", "maintenance", "offline"], [0.80, 0.15, 0.05]
            )[0],
        })

    return pl.DataFrame(records)


def gen_operator(shift_ids: list[str]) -> pl.DataFrame:
    """30 个操作员. 70% 拥有 multi-core cert 含 30% junior, 是 Q4 错配源."""
    skill_weights = {"junior": 0.25, "intermediate": 0.35, "senior": 0.25, "expert": 0.15}
    skills = list(skill_weights.keys())
    weights = list(skill_weights.values())

    shift_weights = {"SH-D": 0.45, "SH-S": 0.30, "SH-N": 0.25}
    sids = list(shift_weights.keys())
    sw = list(shift_weights.values())

    hourly_rate_by_skill = {
        "junior": (22.0, 26.0),
        "intermediate": (26.0, 31.0),
        "senior": (31.0, 36.0),
        "expert": (36.0, 42.0),
    }

    records = []
    for i in range(1, N_OPERATOR + 1):
        skill = random.choices(skills, weights)[0]
        # 70% 拥有 multi-core cert, junior 里也有 30% 错误地拿到 cert.
        if skill == "junior":
            mc_certified = random.random() < 0.30
        elif skill == "intermediate":
            mc_certified = random.random() < 0.65
        elif skill == "senior":
            mc_certified = random.random() < 0.90
        else:
            mc_certified = random.random() < 0.95

        hire_days_ago = {
            "junior": (180, 720),
            "intermediate": (720, 1800),
            "senior": (1800, 3600),
            "expert": (3600, 6000),
        }[skill]
        hire = REFERENCE_DATE - timedelta(days=random.randint(*hire_days_ago))
        cert = hire + timedelta(days=random.randint(60, 180))

        rate_low, rate_high = hourly_rate_by_skill[skill]
        records.append({
            "operator_id": f"OP-{i:03d}",
            "name": fake.name(),
            "skill_level": skill,
            "certification_date": cert,
            "default_shift_id": random.choices(sids, sw)[0],
            "hourly_rate_usd": round(random.uniform(rate_low, rate_high), 2),
            "hire_date": hire,
            "multi_core_certified": mc_certified,
            "department": random.choices(
                ["Production", "Quality Assurance", "R&D"], [0.85, 0.10, 0.05]
            )[0],
        })

    return pl.DataFrame(records)


def gen_customer_order(customer_df: pl.DataFrame) -> pl.DataFrame:
    """250 个 PO. loss_threshold_db 严格按 segment 设."""
    customers = customer_df.to_dicts()
    # 给每个客户分配 PO 比例, 大客户多, 小客户少, 按 contract_value 加权.
    weights = [c["contract_value_annual_usd"] for c in customers]
    total_w = sum(weights)

    product_pool = {
        "hyperscale_datacenter": [
            ("MTP12-OS2-3M", 48.0, 12),
            ("MTP24-OS2-5M", 92.0, 24),
            ("MTP12-OM4-3M", 56.0, 12),
            ("MCF4-DC-1M", 320.0, 4),
        ],
        "ftth_carrier": [
            ("LC-Drop-50M", 7.5, 2),
            ("SC-Drop-100M", 9.0, 2),
            ("LC-DropAssy-30M", 6.8, 2),
        ],
        "enterprise_network": [
            ("LC-Patch-2M", 12.0, 2),
            ("LC-Patch-5M", 14.5, 2),
            ("MTP12-Mini-2M", 38.0, 12),
        ],
    }

    records = []
    for i in range(1, N_CUSTOMER_ORDER + 1):
        # 按合同价值加权选客户
        customer = random.choices(customers, weights, k=1)[0]
        segment = customer["segment"]
        product_code, unit_price, splice_per_cable = random.choice(product_pool[segment])

        # 订单大小分布: 大 (1000+), 中 (200-1000), 小 (50-200)
        size_bucket = random.choices(["small", "medium", "large"], [0.45, 0.40, 0.15])[0]
        if size_bucket == "small":
            qty = random.randint(50, 200)
        elif size_bucket == "medium":
            qty = random.randint(200, 1000)
        else:
            qty = random.randint(1000, 4000)

        order_date = (
            DATA_WINDOW_START + timedelta(days=random.randint(0, 365))
        ).date()
        promised = order_date + timedelta(days=random.randint(14, 60))
        status_pool = ["closed", "shipped", "in_production", "open"]
        status_weights = [0.55, 0.25, 0.15, 0.05]

        records.append({
            "order_id": f"PO-{order_date.year}-{i:04d}",
            "customer_id": customer["customer_id"],
            "order_date": order_date,
            "promised_delivery_date": promised,
            "product_code": product_code,
            "quantity_cables": qty,
            "splices_required": qty * splice_per_cable,
            "unit_price_usd": unit_price,
            "loss_threshold_db": SEGMENT_LOSS_THRESHOLD_DB[segment],
            "status": random.choices(status_pool, status_weights)[0],
        })

    return pl.DataFrame(records)


def gen_fiber_spool(batch_df: pl.DataFrame) -> pl.DataFrame:
    """400 个 spool 分布在 60 个批次里. 坏批次保证产出 ~15 个 spool."""
    batches = batch_df.to_dicts()
    records = []
    spool_idx = 0
    for batch in batches:
        # 每个批次产出 spool_count 个 spool, 不超过总数限制.
        n_spools = batch["spool_count"]
        for j in range(n_spools):
            spool_idx += 1
            if spool_idx > N_FIBER_SPOOL:
                break
            records.append({
                "spool_id": f"SP-{batch['received_date'].year}-{spool_idx:05d}",
                "batch_id": batch["batch_id"],
                "spec_id": batch["spec_id"],
                "received_date": batch["received_date"],
                "remaining_length_m": round(
                    random.uniform(5000, 25000), 1
                ),
                "location": f"WH-{chr(65 + (spool_idx % 4))}{(spool_idx % 8) + 1}",
                "status": random.choices(
                    ["available", "in_use", "depleted"], [0.45, 0.45, 0.10]
                )[0],
            })
        if spool_idx >= N_FIBER_SPOOL:
            break

    return pl.DataFrame(records)


def gen_maintenance_event(equipment_df: pl.DataFrame) -> pl.DataFrame:
    """150 条维护事件, 主要是 calibration 和 routine cleaning."""
    equipment_ids = equipment_df["equipment_id"].to_list()
    records = []
    event_types_weights = [
        ("calibration", 0.40),
        ("pm", 0.30),
        ("cleaning", 0.20),
        ("repair", 0.10),
    ]
    types = [t for t, _ in event_types_weights]
    weights = [w for _, w in event_types_weights]

    for i in range(1, N_MAINTENANCE + 1):
        eq_id = random.choice(equipment_ids)
        event_type = random.choices(types, weights)[0]
        event_date = (
            DATA_WINDOW_START + timedelta(days=random.randint(0, 365))
        )
        cost_by_type = {
            "calibration": (480, 800),
            "pm": (200, 500),
            "cleaning": (50, 150),
            "repair": (800, 2400),
        }
        labor_by_type = {
            "calibration": (200, 400),
            "pm": (100, 250),
            "cleaning": (30, 80),
            "repair": (400, 1200),
        }
        duration_by_type = {
            "calibration": (2.0, 3.5),
            "pm": (1.0, 2.5),
            "cleaning": (0.5, 1.5),
            "repair": (4.0, 12.0),
        }

        parts_cost = round(random.uniform(*cost_by_type[event_type]), 2)
        labor_cost = round(random.uniform(*labor_by_type[event_type]), 2)
        duration = round(random.uniform(*duration_by_type[event_type]), 2)

        # 70% 内部工程师, 30% 厂家工程师.
        if random.random() < 0.30:
            performer = f"{random.choice(['Fujikura', 'Sumitomo', 'FITEL'])} FSE"
        else:
            performer = fake.name()

        next_due = None
        if event_type == "calibration":
            next_due = (event_date + timedelta(days=90)).date()

        records.append({
            "event_id": f"MAINT-{i:05d}",
            "equipment_id": eq_id,
            "event_ts": event_date,
            "event_type": event_type,
            "duration_hours": duration,
            "parts_cost_usd": parts_cost,
            "labor_cost_usd": labor_cost,
            "performed_by": performer,
            "notes": None,
            "next_due_date": next_due,
        })

    return pl.DataFrame(records)


def gen_splice_job(
    order_df: pl.DataFrame,
    equipment_df: pl.DataFrame,
    operator_df: pl.DataFrame,
) -> pl.DataFrame:
    """800 个生产 job. 每个 job 是一个 operator 在一台设备上的一次作业."""
    orders = order_df.to_dicts()
    equipment_ids = equipment_df["equipment_id"].to_list()
    operators = operator_df.to_dicts()

    # 让 job 数 = 800. 每个 job 平均 ~62 splice, 总 splice ~50000.
    job_records = []
    job_idx = 0
    # 把所有订单按时间排序, 然后给每个订单分配若干 job 来完成它的 splices_required.
    orders_sorted = sorted(orders, key=lambda o: o["order_date"])
    for order in orders_sorted:
        if job_idx >= N_SPLICE_JOB:
            break
        # 该订单大约需要多少 job 来完成. 每 job 30 到 150 splice.
        order_splices = order["splices_required"]
        # 计算这单分多少 job (大订单分多, 小订单 1 个)
        n_jobs_for_order = max(1, min(15, order_splices // random.randint(40, 120)))
        per_job_target = max(20, order_splices // n_jobs_for_order)

        for k in range(n_jobs_for_order):
            if job_idx >= N_SPLICE_JOB:
                break
            job_idx += 1

            # job 开始时间在订单日之后 1 到 14 天
            order_dt = datetime.combine(order["order_date"], datetime.min.time())
            offset_days = random.randint(1, 14)
            planned_start = order_dt + timedelta(
                days=offset_days,
                hours=random.randint(0, 23),
                minutes=random.choice([0, 15, 30, 45]),
            )

            operator = random.choice(operators)
            shift_id = operator["default_shift_id"]

            # 把 planned_start 调整到该班次的时段
            shift_hour_map = {"SH-D": 9, "SH-S": 17, "SH-N": 1}
            planned_start = planned_start.replace(
                hour=shift_hour_map[shift_id] + random.randint(0, 5),
                minute=random.choice([0, 15, 30, 45]),
            )

            target_count = max(
                25, min(180, per_job_target + random.randint(-10, 10))
            )
            # 每次 splice 平均 2.5 分钟 (含 retry), job 时长粗估
            planned_minutes = int(target_count * 2.6)
            planned_end = planned_start + timedelta(minutes=planned_minutes)
            actual_start = planned_start + timedelta(minutes=random.randint(-10, 30))
            actual_end = actual_start + timedelta(
                minutes=int(planned_minutes * random.uniform(0.95, 1.20))
            )

            # job 真实完成数会跟 target 略有差异.
            completed = target_count + random.randint(-5, 5)
            completed = max(20, completed)

            job_records.append({
                "job_id": f"JOB-{planned_start.year}-{job_idx:04d}",
                "order_id": order["order_id"],
                "equipment_id": random.choice(equipment_ids),
                "operator_id": operator["operator_id"],
                "shift_id": shift_id,
                "planned_start_ts": planned_start,
                "planned_end_ts": planned_end,
                "actual_start_ts": actual_start,
                "actual_end_ts": actual_end,
                "target_splice_count": target_count,
                "completed_splice_count": completed,
                "status": random.choices(
                    ["completed", "paused", "cancelled"], [0.94, 0.04, 0.02]
                )[0],
            })

    return pl.DataFrame(job_records)


def gen_electrode_replacement(
    equipment_df: pl.DataFrame,
    operator_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    电极更换日志. 当前 reactive 策略:
    每台设备约每 2200 splice 换一次, 持续 12 个月.
    """
    equipment_ids = equipment_df["equipment_id"].to_list()
    operator_ids = operator_df["operator_id"].to_list()

    reasons = ["condition_warning", "unplanned_failure", "scheduled", "quality_drift_detected"]
    reason_weights = [0.50, 0.20, 0.15, 0.15]

    records = []
    replacement_idx = 0
    # 给每台设备生成 12 个月里的电极更换历史.
    # reactive 模式下平均 splices_on_old_pair 约 2100 到 2600.
    for eq_id in equipment_ids:
        # 12 个月内大约 5 次更换 (假设设备月产 1000 splice, 寿命 2200, 12000/2200 ≈ 5.5).
        n_replacements = random.randint(4, 7)
        # 跨 365 天均匀分布
        ts_offsets = sorted(random.sample(range(15, 360), n_replacements))
        for offset in ts_offsets:
            replacement_idx += 1
            ts = DATA_WINDOW_START + timedelta(
                days=offset,
                hours=random.randint(8, 17),
                minutes=random.randint(0, 59),
            )
            # reactive 策略下 splices_on_old_pair 多在 2000 到 2800
            splices_done = random.choices(
                [
                    random.randint(1500, 2000),
                    random.randint(2000, 2400),
                    random.randint(2400, 2900),
                ],
                [0.15, 0.50, 0.35],
            )[0]
            records.append({
                "replacement_id": f"ER-{replacement_idx:05d}",
                "equipment_id": eq_id,
                "replacement_ts": ts,
                "splices_on_old_pair": splices_done,
                "reason": random.choices(reasons, reason_weights)[0],
                "new_pair_part_number": "FSM100P-EL-A",
                "new_pair_cost_usd": ELECTRODE_PAIR_PRICE_USD,
                "replaced_by_operator_id": random.choice(operator_ids),
            })

    return pl.DataFrame(records)


def _attempt_parameters(
    mode_type: str, electrode_count: int, is_retry: bool
) -> dict:
    """生成一次 splice attempt 的物理参数."""
    # retry 时, operator 通常调小参数偏差 (重新 cleave 后预期更准).
    offset_sigma = 0.04 if is_retry else 0.06

    left_x = round(random.gauss(0, offset_sigma), 3)
    left_y = round(random.gauss(0, offset_sigma), 3)
    right_x = round(random.gauss(0, offset_sigma), 3)
    right_y = round(random.gauss(0, offset_sigma), 3)
    core_distance = round(
        math.sqrt((left_x - right_x) ** 2 + (left_y - right_y) ** 2), 3
    )

    angle_sigma = 0.35 if is_retry else 0.5
    angle_dev = round(abs(random.gauss(0, angle_sigma)), 2)
    left_cleave = round(abs(random.gauss(0, 0.25 if is_retry else 0.30)), 2)
    right_cleave = round(abs(random.gauss(0, 0.25 if is_retry else 0.30)), 2)

    # 设备参数会略有飘移
    arc_power = round(random.gauss(12.5, 0.4), 2)
    # multi_core 焊接需要更长的 arc 时间.
    arc_dur_base = 1100 if mode_type == "multi_core" else 950
    arc_duration = random.randint(arc_dur_base - 80, arc_dur_base + 80)
    prefusion = random.randint(120, 180)
    overlap = round(random.gauss(10.0, 1.0), 2)

    temp = round(random.gauss(22.0, 1.5), 1)
    humidity_raw = random.gauss(45.0, 12.0)
    humidity = round(max(20.0, min(80.0, humidity_raw)), 1)

    return {
        "left_x": left_x,
        "left_y": left_y,
        "right_x": right_x,
        "right_y": right_y,
        "core_distance": core_distance,
        "angle_dev": angle_dev,
        "left_cleave": left_cleave,
        "right_cleave": right_cleave,
        "arc_power": arc_power,
        "arc_duration": arc_duration,
        "prefusion": prefusion,
        "overlap": overlap,
        "temp": temp,
        "humidity": humidity,
    }


def _attempt_cost(
    operator_hourly_rate: float,
    duration_seconds: int,
    spec_unit_cost: float,
    machine_depreciation_monthly: float,
) -> dict:
    """计算一次 attempt 的四项成本."""
    material_cost = round(
        FIBER_CONSUMED_PER_SPLICE_M * spec_unit_cost + SPLICE_PROTECTOR_COST_USD,
        4,
    )
    labor_cost = round(operator_hourly_rate * duration_seconds / 3600.0, 4)
    machine_cost = round(
        MACHINE_COST_PER_MINUTE_USD * (duration_seconds / 60.0)
        + machine_depreciation_monthly / (30 * 24 * 60) * (duration_seconds / 60.0),
        4,
    )
    consumable_cost = round(
        ELECTRODE_PAIR_PRICE_USD / ELECTRODE_PAIR_LIFETIME
        + CLEAVER_BLADE_PRICE_USD / CLEAVER_BLADE_LIFETIME
        + 0.015,  # IPA + wipe + protector 摊销
        4,
    )
    total = round(material_cost + labor_cost + machine_cost + consumable_cost, 4)
    return {
        "material_cost_usd": material_cost,
        "labor_cost_usd": labor_cost,
        "machine_cost_usd": machine_cost,
        "consumable_cost_usd": consumable_cost,
        "total_cost_usd": total,
    }


def gen_splices_and_attempts(
    job_df: pl.DataFrame,
    spool_df: pl.DataFrame,
    batch_df: pl.DataFrame,
    spec_df: pl.DataFrame,
    equipment_df: pl.DataFrame,
    operator_df: pl.DataFrame,
    electrode_df: pl.DataFrame,
    order_df: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """生成 splice_record 和 splice_attempt 两张表, 同时回填 equipment 累计计数."""
    jobs = job_df.to_dicts()
    spools = spool_df.to_dicts()
    batches = {b["batch_id"]: b for b in batch_df.to_dicts()}
    specs = {s["spec_id"]: s for s in spec_df.to_dicts()}
    equipment_map = {e["equipment_id"]: e for e in equipment_df.to_dicts()}
    operator_map = {o["operator_id"]: o for o in operator_df.to_dicts()}
    order_map = {o["order_id"]: o for o in order_df.to_dicts()}

    # 按 spec 把 spool 分组, 方便按订单产品挑光纤.
    spools_by_spec: dict[str, list[dict]] = {}
    for sp in spools:
        spools_by_spec.setdefault(sp["spec_id"], []).append(sp)

    # 加大坏批次曝光: 让 MFG-2024-038 在 2025-12 到 2026-03 之间有几个 job 强制使用.
    bad_batch_spools = [sp for sp in spools if sp["batch_id"] == BAD_BATCH_ID]

    # 把 electrode_replacement 按 equipment_id 排好序, 用来追踪每台设备的 electrode_count.
    electrode_events: dict[str, list[datetime]] = {}
    for r in electrode_df.to_dicts():
        electrode_events.setdefault(r["equipment_id"], []).append(r["replacement_ts"])
    for eq_id in electrode_events:
        electrode_events[eq_id].sort()

    # 每台设备的当前电极对从何时开始服役 (初始假设 6 个月前)
    initial_start = DATA_WINDOW_START - timedelta(days=180)
    # 当前电极对的"已服役 attempt 数" 计数器
    equipment_current_electrode_count: dict[str, int] = {
        eq_id: random.randint(0, 1500) for eq_id in equipment_map
    }
    equipment_current_electrode_start: dict[str, datetime] = {
        eq_id: initial_start for eq_id in equipment_map
    }

    # product_code → fiber spec_id 的简单映射, 决定 job 用哪种 spec.
    def product_to_spec(product_code: str) -> str:
        if product_code.startswith("MCF"):
            return "MCF-4C"
        if product_code.startswith("MTP") and "OM4" in product_code:
            return "MMF-OM4"
        if product_code.startswith("MTP") and "OM5" in product_code:
            return "MMF-OM5"
        if "OM" in product_code:
            return random.choice(["MMF-OM4", "MMF-OM5"])
        return random.choices(["SMF-G652D", "SMF-G657A1"], [0.7, 0.3])[0]

    splice_records = []
    splice_attempts = []
    job_idx_counter = 0
    splice_idx_counter = 0
    attempt_idx_counter = 0
    equipment_total_attempts: dict[str, int] = {eq_id: 0 for eq_id in equipment_map}

    # 排序 jobs 让 attempt 时间顺序合理.
    jobs_sorted = sorted(jobs, key=lambda j: j["actual_start_ts"])

    for job in jobs_sorted:
        job_idx_counter += 1
        order = order_map[job["order_id"]]
        equipment_id = job["equipment_id"]
        equipment = equipment_map[equipment_id]
        operator = operator_map[job["operator_id"]]
        days_since_cal = (
            REFERENCE_DATE - equipment["last_calibration_date"]
        ).days

        # 确定本 job 用的 fiber spec.
        spec_id = product_to_spec(order["product_code"])
        spec = specs[spec_id]
        mode_type = spec["mode_type"]

        # 挑可用 spool. 12-03 到 2026-03 期间, 给少数 SMF-G652D job 强制用坏批次.
        job_start = job["actual_start_ts"]
        use_bad_batch = (
            spec_id == "SMF-G652D"
            and date(2025, 12, 1) <= job_start.date() <= date(2026, 3, 31)
            and random.random() < 0.04
            and len(bad_batch_spools) >= 2
        )
        if use_bad_batch:
            candidate_spools = bad_batch_spools
        else:
            candidate_spools = [
                sp for sp in spools_by_spec.get(spec_id, [])
                if sp["batch_id"] != BAD_BATCH_ID
            ]
        if len(candidate_spools) < 2:
            candidate_spools = spools_by_spec.get(spec_id, [])
        if len(candidate_spools) < 2:
            # fallback: 用任何 spool
            candidate_spools = spools

        # 当前 attempt 时刻
        current_ts = job["actual_start_ts"]

        for position in range(1, job["completed_splice_count"] + 1):
            splice_idx_counter += 1
            splice_id = f"SPL-{splice_idx_counter:07d}"

            # 选左右 spool, 不能相同.
            left_sp = random.choice(candidate_spools)
            right_sp = random.choice([sp for sp in candidate_spools if sp["spool_id"] != left_sp["spool_id"]])

            batch_left = batches[left_sp["batch_id"]]
            batch_right = batches[right_sp["batch_id"]]
            # 用左右两个 batch 中较高的方差作为本次 splice 的"批次方差风险"
            effective_std = max(
                batch_left["cladding_diameter_std_dev_um"],
                batch_right["cladding_diameter_std_dev_um"],
            )

            # 多次 attempt 逻辑
            attempt_records_for_splice = []
            current_grade = None
            final_outcome = None
            attempt_num = 0
            ai_alert_triggered = False
            forced_ignored_reject = False

            while attempt_num < 3:
                attempt_num += 1
                attempt_idx_counter += 1
                attempt_id = f"ATT-{attempt_idx_counter:07d}"

                # 更新 electrode_count.
                # 检查这个 attempt_ts 跟 electrode_events 比较, 是否已经过了更换点.
                eq_replacements = electrode_events.get(equipment_id, [])
                while eq_replacements and current_ts >= eq_replacements[0]:
                    # 跨过一次更换, 重置计数
                    equipment_current_electrode_count[equipment_id] = 0
                    equipment_current_electrode_start[equipment_id] = eq_replacements[0]
                    eq_replacements = eq_replacements[1:]
                electrode_events[equipment_id] = eq_replacements

                equipment_current_electrode_count[equipment_id] += 1
                ec_count = equipment_current_electrode_count[equipment_id]
                equipment_total_attempts[equipment_id] += 1

                params = _attempt_parameters(
                    mode_type=mode_type,
                    electrode_count=ec_count,
                    is_retry=(attempt_num > 1),
                )

                actual_loss = compute_actual_loss(
                    core_distance_um=params["core_distance"],
                    angle_dev_deg=params["angle_dev"],
                    cleave_total_deg=params["left_cleave"] + params["right_cleave"],
                    electrode_count=ec_count,
                    batch_std_dev=effective_std,
                    shift_id=job["shift_id"],
                    skill_level=operator["skill_level"],
                    mode_type=mode_type,
                    humidity_pct=params["humidity"],
                    arc_power_mw=params["arc_power"],
                    days_since_cal=days_since_cal,
                )

                # LID 算法的 predicted_loss 有 ±0.005 的偏差
                predicted_loss = round(
                    max(0.001, actual_loss + random.gauss(0, 0.004)), 4
                )

                attempt_grade = grade_from_loss(actual_loss)

                # 判定 outcome:
                if attempt_grade in ("A", "B"):
                    attempt_outcome = "accepted"
                elif attempt_num >= 3:
                    if attempt_grade == "C":
                        attempt_outcome = "accepted"
                    else:
                        attempt_outcome = "final_reject"
                else:
                    attempt_outcome = "retry"

                # 持续时间
                base_duration = 95 if mode_type != "multi_core" else 180
                duration_seconds = base_duration + random.randint(-15, 30)

                costs = _attempt_cost(
                    operator_hourly_rate=operator["hourly_rate_usd"],
                    duration_seconds=duration_seconds,
                    spec_unit_cost=spec["bom_cost_per_meter_usd"],
                    machine_depreciation_monthly=equipment["depreciation_monthly_usd"],
                )

                attempt_records_for_splice.append({
                    "attempt_id": attempt_id,
                    "splice_id": splice_id,
                    "attempt_number": attempt_num,
                    "attempt_ts": current_ts,
                    "duration_seconds": duration_seconds,
                    "left_core_offset_x_um": params["left_x"],
                    "left_core_offset_y_um": params["left_y"],
                    "right_core_offset_x_um": params["right_x"],
                    "right_core_offset_y_um": params["right_y"],
                    "core_to_core_distance_um": params["core_distance"],
                    "angle_deviation_deg": params["angle_dev"],
                    "left_cleave_angle_deg": params["left_cleave"],
                    "right_cleave_angle_deg": params["right_cleave"],
                    "arc_power_mw": params["arc_power"],
                    "arc_duration_ms": params["arc_duration"],
                    "prefusion_time_ms": params["prefusion"],
                    "overlap_um": params["overlap"],
                    "ambient_temp_c": params["temp"],
                    "humidity_percent": params["humidity"],
                    "equipment_electrode_count": ec_count,
                    "predicted_loss_db": predicted_loss,
                    "actual_loss_db": round(actual_loss, 4),
                    "attempt_grade": attempt_grade,
                    "attempt_outcome": attempt_outcome,
                    "material_cost_usd": costs["material_cost_usd"],
                    "labor_cost_usd": costs["labor_cost_usd"],
                    "machine_cost_usd": costs["machine_cost_usd"],
                    "consumable_cost_usd": costs["consumable_cost_usd"],
                    "total_cost_usd": costs["total_cost_usd"],
                })

                # 时间推进: 一次 attempt 加上短暂间隔
                current_ts += timedelta(seconds=duration_seconds + random.randint(15, 60))

                # 如果 predicted_loss 超阈值, 触发 alert.
                if predicted_loss > 0.05:
                    ai_alert_triggered = True
                    # 决定本告警的 outcome (用 shift-specific 权重).
                    if job["shift_id"] == "SH-N":
                        outcome_pool = ALERT_OUTCOME_NIGHT_WEIGHTS
                    else:
                        outcome_pool = ALERT_OUTCOME_BASE_WEIGHTS
                    outcome_keys = list(outcome_pool.keys())
                    outcome_w = list(outcome_pool.values())
                    alert_outcome_choice = random.choices(outcome_keys, outcome_w)[0]
                    # 把 outcome 暂时附在 attempt dict 上, 后面 gen_quality_alert 用
                    attempt_records_for_splice[-1]["_alert_outcome"] = alert_outcome_choice
                    # 如果 outcome=ignored, 强制 splice 进入 reject 路径
                    if alert_outcome_choice == "ignored" and not forced_ignored_reject:
                        if random.random() < IGNORED_ALERT_REJECT_PROB:
                            forced_ignored_reject = True

                # 退出循环条件
                if attempt_outcome in ("accepted", "final_reject"):
                    current_grade = attempt_grade
                    final_outcome = attempt_outcome
                    break

            # 如果 forced_ignored_reject, 把最后一次 attempt 的 grade 强制改成 Reject
            if forced_ignored_reject and attempt_records_for_splice:
                last_attempt = attempt_records_for_splice[-1]
                # 拉高 actual_loss 到 Reject 范围
                last_attempt["actual_loss_db"] = round(
                    max(last_attempt["actual_loss_db"], 0.09 + random.uniform(0, 0.03)),
                    4,
                )
                last_attempt["attempt_grade"] = "Reject"
                last_attempt["attempt_outcome"] = "final_reject"
                current_grade = "Reject"
                final_outcome = "final_reject"

            final_attempt = attempt_records_for_splice[-1]
            final_loss_db = final_attempt["actual_loss_db"]
            final_grade = final_attempt["attempt_grade"]
            meets_spec = final_loss_db <= order["loss_threshold_db"]

            splice_records.append({
                "splice_id": splice_id,
                "job_id": job["job_id"],
                "left_spool_id": left_sp["spool_id"],
                "right_spool_id": right_sp["spool_id"],
                "equipment_id": equipment_id,
                "operator_id": operator["operator_id"],
                "shift_id": job["shift_id"],
                "planned_position_in_job": position,
                "started_ts": attempt_records_for_splice[0]["attempt_ts"],
                "completed_ts": final_attempt["attempt_ts"]
                    + timedelta(seconds=final_attempt["duration_seconds"]),
                "attempt_count": len(attempt_records_for_splice),
                "final_attempt_id": final_attempt["attempt_id"],
                "final_loss_db": final_loss_db,
                "final_grade": final_grade,
                "meets_customer_spec": meets_spec,
                "ai_alert_triggered": ai_alert_triggered,
                "image_path": f"/images/splice/{splice_id}.png",
            })
            splice_attempts.extend(attempt_records_for_splice)

    # 回填 equipment.total_splice_count
    equipment_records = equipment_df.to_dicts()
    for e in equipment_records:
        e["total_splice_count"] = equipment_total_attempts.get(e["equipment_id"], 0)
    equipment_updated = pl.DataFrame(equipment_records)

    # 写出全局变量供下游 (alert, prediction_log, qa_audit) 使用 (通过返回值)
    splice_record_df = pl.DataFrame(splice_records)
    # splice_attempts 列里多了一个 "_alert_outcome", 我们要剥离它
    # (TSV 写出时不要它, 但 alert 生成器要用)
    return splice_record_df, splice_attempts, equipment_updated


def gen_quality_alert(splice_attempts: list[dict]) -> pl.DataFrame:
    """质量告警表. 从 splice_attempts 里有 _alert_outcome 的记录抽出."""
    recommended = {
        "high_loss_predicted": "Predicted loss exceeds 0.05 dB threshold. Reclean both ends and re-cleave before retry.",
        "angle_out_of_spec": "Angle deviation > 1.0 deg. Realign fibers, recheck cleaver.",
        "equipment_drift": "Arc power drift detected. Run calibration check.",
        "cleave_angle_exceeded": "Cleave angle > 0.5 deg on at least one side. Replace cleaver blade or recleave.",
        "electrode_warning": "Electrode age > 2000 splices. Recommend replacement.",
    }
    actions_by_outcome = {
        "resolved": ["reclean_and_retry", "adjust_parameters", "equipment_check", "fiber_replaced"],
        "escalated": ["equipment_check", "fiber_replaced", "reclean_and_retry"],
        "ignored": ["ignored"],
    }

    records = []
    alert_idx = 0
    for sa in splice_attempts:
        outcome = sa.get("_alert_outcome")
        if not outcome:
            continue
        alert_idx += 1

        # 决定 alert_type
        if sa["equipment_electrode_count"] > 2000 and random.random() < 0.35:
            alert_type = "electrode_warning"
        elif sa["angle_deviation_deg"] > 1.0:
            alert_type = "angle_out_of_spec"
        elif sa["left_cleave_angle_deg"] > 0.5 or sa["right_cleave_angle_deg"] > 0.5:
            alert_type = "cleave_angle_exceeded"
        elif abs(sa["arc_power_mw"] - 12.5) > 0.6:
            alert_type = "equipment_drift"
        else:
            alert_type = "high_loss_predicted"

        action = random.choice(actions_by_outcome[outcome])
        if outcome == "ignored":
            resolution_ts = None
        else:
            resolution_ts = sa["attempt_ts"] + timedelta(minutes=random.randint(2, 20))

        records.append({
            "alert_id": f"ALT-{alert_idx:05d}",
            "attempt_id": sa["attempt_id"],
            "alert_ts": sa["attempt_ts"],
            "alert_type": alert_type,
            "predicted_loss_db": sa["predicted_loss_db"],
            "threshold_db": 0.05,
            "recommended_action": recommended[alert_type],
            "action_taken": action,
            "outcome": outcome,
            "resolution_ts": resolution_ts,
        })

    return pl.DataFrame(records)


def gen_model_prediction_log(splice_attempts: list[dict]) -> pl.DataFrame:
    """每 attempt 一条预测日志."""
    model_versions = ["v1.2.0", "v1.3.0", "v2.0.0", "v2.1.0"]
    model_weights = [0.05, 0.15, 0.30, 0.50]

    importance_template = {
        "core_to_core_distance_um": 0.30,
        "angle_deviation_deg": 0.20,
        "left_cleave_angle_deg": 0.12,
        "right_cleave_angle_deg": 0.12,
        "equipment_electrode_count": 0.10,
        "arc_power_mw": 0.07,
        "humidity_percent": 0.05,
        "ambient_temp_c": 0.04,
    }

    records = []
    for idx, sa in enumerate(splice_attempts, start=1):
        # 置信度跟 actual_loss 反相关, loss 越大越没信心
        confidence = round(
            max(0.70, min(0.99, 0.96 - sa["actual_loss_db"] * 2.5 + random.gauss(0, 0.025))),
            3,
        )

        # 特征重要性带点噪声
        importance = {
            k: round(v * random.uniform(0.85, 1.15), 3)
            for k, v in importance_template.items()
        }
        # 重新归一化
        total = sum(importance.values())
        importance = {k: round(v / total, 3) for k, v in importance.items()}

        # 输入特征快照
        features = {
            "core_to_core_distance_um": sa["core_to_core_distance_um"],
            "angle_deviation_deg": sa["angle_deviation_deg"],
            "left_cleave_angle_deg": sa["left_cleave_angle_deg"],
            "right_cleave_angle_deg": sa["right_cleave_angle_deg"],
            "arc_power_mw": sa["arc_power_mw"],
            "ambient_temp_c": sa["ambient_temp_c"],
            "humidity_percent": sa["humidity_percent"],
            "equipment_electrode_count": sa["equipment_electrode_count"],
        }

        records.append({
            "prediction_id": f"PRED-{idx:07d}",
            "attempt_id": sa["attempt_id"],
            "model_version": random.choices(model_versions, model_weights)[0],
            "prediction_ts": sa["attempt_ts"] - timedelta(seconds=random.randint(1, 5)),
            "input_features": json.dumps(features),
            "predicted_loss_db": sa["predicted_loss_db"],
            "confidence_score": confidence,
            "feature_importance": json.dumps(importance),
        })

    return pl.DataFrame(records)


def gen_qa_audit(splice_records: pl.DataFrame, operator_df: pl.DataFrame) -> pl.DataFrame:
    """随机抽 5% splice 复核. 加少量 grade mismatch."""
    sr = splice_records.to_dicts()
    audited = random.sample(sr, min(N_QA_AUDIT_TARGET, len(sr)))
    qa_engineers = ["Tom Vasquez", "Anya Petrov", "Wei Chen", "Maria Salazar"]

    records = []
    for idx, splice in enumerate(audited, start=1):
        # QA 用 OTDR 复测, 跟 LID 估算有 ±0.008 偏差
        qa_loss = round(
            max(0.001, splice["final_loss_db"] + random.gauss(0, 0.008)),
            4,
        )
        qa_grade = grade_from_loss(qa_loss)
        match = qa_grade == splice["final_grade"]
        records.append({
            "audit_id": f"QA-{idx:05d}",
            "splice_id": splice["splice_id"],
            "audit_ts": splice["completed_ts"] + timedelta(
                days=random.randint(1, 7),
                hours=random.randint(0, 23),
            ),
            "auditor_name": random.choice(qa_engineers),
            "operator_self_grade": splice["final_grade"],
            "qa_measured_loss_db": qa_loss,
            "qa_grade": qa_grade,
            "grade_match": match,
            "variance_db": round(qa_loss - splice["final_loss_db"], 4),
        })

    return pl.DataFrame(records)


def gen_customer_complaint(
    splice_records: pl.DataFrame,
    customer_df: pl.DataFrame,
    customer_order_df: pl.DataFrame,
    fiber_spool_df: pl.DataFrame,
    fiber_batch_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    30 条投诉. 6 条明确指向 MFG-2024-038 批次, 6 条 suspected 但未追溯,
    其余是杂项 audit_finding / connector_failure / intermittent.
    """
    # 找出使用了坏批次的 splice
    bad_spool_ids = set(
        fiber_spool_df.filter(pl.col("batch_id") == BAD_BATCH_ID)["spool_id"].to_list()
    )
    bad_splices = [
        s for s in splice_records.to_dicts()
        if s["left_spool_id"] in bad_spool_ids or s["right_spool_id"] in bad_spool_ids
    ]

    # FTTH-CCom 是主要受影响客户 (customer_code FTTH-CCom)
    ftth_ccom = customer_df.filter(pl.col("customer_code") == "FTTH-CCom").to_dicts()
    if ftth_ccom:
        ftth_ccom_id = ftth_ccom[0]["customer_id"]
    else:
        ftth_ccom_id = customer_df.to_dicts()[0]["customer_id"]

    ftth_orders = customer_order_df.filter(
        pl.col("customer_id") == ftth_ccom_id
    ).to_dicts()

    records = []
    complaint_idx = 0

    # 6 条明确指向 MFG-2024-038
    for i in range(6):
        complaint_idx += 1
        bs = random.choice(bad_splices) if bad_splices else None
        order_id = random.choice(ftth_orders)["order_id"] if ftth_orders else None
        cdate = date(2026, 3, 1) + timedelta(days=random.randint(0, 90))
        records.append({
            "complaint_id": f"CMP-{complaint_idx:04d}",
            "customer_id": ftth_ccom_id,
            "order_id": order_id,
            "complaint_date": cdate,
            "complaint_type": "high_loss_in_field",
            "linked_splice_id": bs["splice_id"] if bs else None,
            "linked_batch_id": BAD_BATCH_ID,
            "severity": random.choices(["high", "critical"], [0.7, 0.3])[0],
            "resolution_status": random.choices(
                ["investigating", "resolved", "escalated"], [0.4, 0.4, 0.2]
            )[0],
            "cost_impact_usd": round(random.uniform(6000, 14000), 2),
        })

    # 6 条 suspected unlinked (FTTH high-loss complaints 没有追到 batch)
    for i in range(6):
        complaint_idx += 1
        cdate = date(2025, 12, 1) + timedelta(days=random.randint(0, 180))
        records.append({
            "complaint_id": f"CMP-{complaint_idx:04d}",
            "customer_id": ftth_ccom_id,
            "order_id": random.choice(ftth_orders)["order_id"] if ftth_orders else None,
            "complaint_date": cdate,
            "complaint_type": random.choice(["high_loss_in_field", "early_failure"]),
            "linked_splice_id": None,
            "linked_batch_id": None,
            "severity": random.choices(["medium", "high"], [0.6, 0.4])[0],
            "resolution_status": random.choices(
                ["investigating", "resolved"], [0.5, 0.5]
            )[0],
            "cost_impact_usd": round(random.uniform(2000, 7000), 2),
        })

    # 剩下 18 条杂项
    other_types = ["audit_finding", "connector_failure", "intermittent", "early_failure"]
    customers = customer_df.to_dicts()
    orders_by_customer: dict[str, list[dict]] = {}
    for o in customer_order_df.to_dicts():
        orders_by_customer.setdefault(o["customer_id"], []).append(o)

    while complaint_idx < N_CUSTOMER_COMPLAINT:
        complaint_idx += 1
        customer = random.choice(customers)
        c_orders = orders_by_customer.get(customer["customer_id"], [])
        order_id = random.choice(c_orders)["order_id"] if c_orders else None
        cdate = (
            DATA_WINDOW_START + timedelta(days=random.randint(60, 360))
        ).date()
        records.append({
            "complaint_id": f"CMP-{complaint_idx:04d}",
            "customer_id": customer["customer_id"],
            "order_id": order_id,
            "complaint_date": cdate,
            "complaint_type": random.choice(other_types),
            "linked_splice_id": None,
            "linked_batch_id": None,
            "severity": random.choices(["low", "medium", "high"], [0.5, 0.35, 0.15])[0],
            "resolution_status": random.choices(
                ["resolved", "investigating", "open"], [0.7, 0.2, 0.1]
            )[0],
            "cost_impact_usd": round(random.uniform(500, 4000), 2),
        })

    return pl.DataFrame(records)


# ============================================================================
# generate_all_tsv: 编排所有 gen_* 调用并写出 TSV
# ============================================================================
def generate_all_tsv() -> None:
    """生成所有 TSV. 幂等: 先删除已存在的文件."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("[01/18] fiber_spec ...")
    df_spec = gen_fiber_spec()
    df_spec.write_csv(DATA_DIR / "01_fiber_spec.tsv", separator="\t")

    print("[02/18] consumable_price ...")
    df_consumable = gen_consumable_price()
    df_consumable.write_csv(DATA_DIR / "02_consumable_price.tsv", separator="\t")

    print("[03/18] customer ...")
    df_customer = gen_customer()
    df_customer.write_csv(DATA_DIR / "03_customer.tsv", separator="\t")

    print("[04/18] shift ...")
    df_shift = gen_shift()
    df_shift.write_csv(DATA_DIR / "04_shift.tsv", separator="\t")

    print("[05/18] fiber_batch ...")
    df_batch = gen_fiber_batch()
    df_batch.write_csv(DATA_DIR / "05_fiber_batch.tsv", separator="\t")

    print("[06/18] equipment ...")
    df_equipment = gen_equipment()

    print("[07/18] operator ...")
    df_operator = gen_operator(df_shift["shift_id"].to_list())
    df_operator.write_csv(DATA_DIR / "07_operator.tsv", separator="\t")

    print("[08/18] customer_order ...")
    df_order = gen_customer_order(df_customer)
    df_order.write_csv(DATA_DIR / "08_customer_order.tsv", separator="\t")

    print("[09/18] fiber_spool ...")
    df_spool = gen_fiber_spool(df_batch)
    df_spool.write_csv(DATA_DIR / "09_fiber_spool.tsv", separator="\t")

    print("[10/18] maintenance_event ...")
    df_maint = gen_maintenance_event(df_equipment)
    df_maint.write_csv(DATA_DIR / "10_maintenance_event.tsv", separator="\t")

    print("[11/18] splice_job ...")
    df_job = gen_splice_job(df_order, df_equipment, df_operator)
    df_job.write_csv(DATA_DIR / "11_splice_job.tsv", separator="\t")

    print("[12/18] electrode_replacement ...")
    df_electrode = gen_electrode_replacement(df_equipment, df_operator)
    df_electrode.write_csv(DATA_DIR / "12_electrode_replacement.tsv", separator="\t")

    print("[13-14/18] splice_record + splice_attempt (heavy) ...")
    df_splice, attempt_list, df_equipment_updated = gen_splices_and_attempts(
        job_df=df_job,
        spool_df=df_spool,
        batch_df=df_batch,
        spec_df=df_spec,
        equipment_df=df_equipment,
        operator_df=df_operator,
        electrode_df=df_electrode,
        order_df=df_order,
    )
    # 现在写出已回填 total_splice_count 的 equipment
    df_equipment_updated.write_csv(DATA_DIR / "06_equipment.tsv", separator="\t")
    df_splice.write_csv(DATA_DIR / "13_splice_record.tsv", separator="\t")
    # 去掉临时字段 _alert_outcome 再写
    cleaned_attempts = [
        {k: v for k, v in a.items() if k != "_alert_outcome"}
        for a in attempt_list
    ]
    df_attempt = pl.DataFrame(cleaned_attempts)
    df_attempt.write_csv(DATA_DIR / "14_splice_attempt.tsv", separator="\t")

    print("[15/18] quality_alert ...")
    df_alert = gen_quality_alert(attempt_list)
    df_alert.write_csv(DATA_DIR / "15_quality_alert.tsv", separator="\t")

    print("[16/18] model_prediction_log ...")
    df_pred = gen_model_prediction_log(attempt_list)
    df_pred.write_csv(DATA_DIR / "16_model_prediction_log.tsv", separator="\t")

    print("[17/18] qa_audit ...")
    df_audit = gen_qa_audit(df_splice, df_operator)
    df_audit.write_csv(DATA_DIR / "17_qa_audit.tsv", separator="\t")

    print("[18/18] customer_complaint ...")
    df_complaint = gen_customer_complaint(df_splice, df_customer, df_order, df_spool, df_batch)
    df_complaint.write_csv(DATA_DIR / "18_customer_complaint.tsv", separator="\t")

    print(f"\nGenerated all TSV files in {DATA_DIR}")
    print(f"  splice_record: {df_splice.height} rows")
    print(f"  splice_attempt: {len(cleaned_attempts)} rows")
    print(f"  quality_alert: {df_alert.height} rows")
    print(f"  model_prediction_log: {df_pred.height} rows")


# ============================================================================
# create_sqlite_database: Core API batch loader
# ============================================================================
def create_sqlite_database() -> None:
    """从 TSV 文件创建 SQLite. 幂等: 先删除已存在的 db."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 拓扑加载顺序. 第一个元素是不带扩展名的 TSV 文件名,
    # 第二个元素是 SQLAlchemy Core Table 对象.
    load_order: list[tuple[str, object]] = [
        ("01_fiber_spec", FiberSpec.__table__),
        ("02_consumable_price", ConsumablePrice.__table__),
        ("03_customer", Customer.__table__),
        ("04_shift", Shift.__table__),
        ("05_fiber_batch", FiberBatch.__table__),
        ("06_equipment", Equipment.__table__),
        ("07_operator", Operator.__table__),
        ("08_customer_order", CustomerOrder.__table__),
        ("09_fiber_spool", FiberSpool.__table__),
        ("10_maintenance_event", MaintenanceEvent.__table__),
        ("11_splice_job", SpliceJob.__table__),
        ("12_electrode_replacement", ElectrodeReplacement.__table__),
        ("13_splice_record", SpliceRecord.__table__),
        ("14_splice_attempt", SpliceAttempt.__table__),
        ("15_quality_alert", QualityAlert.__table__),
        ("16_model_prediction_log", ModelPredictionLog.__table__),
        ("17_qa_audit", QAAudit.__table__),
        ("18_customer_complaint", CustomerComplaint.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv",
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=10000,
            )
            rows = df.to_dicts()
            if rows:
                # 对 datetime 字段做兜底转换 (polars 偶尔会留下字符串)
                for row in rows:
                    for k, v in row.items():
                        if isinstance(v, str) and (
                            k.endswith("_ts") or k.endswith("_date")
                        ):
                            try:
                                if "T" in v or " " in v:
                                    row[k] = datetime.fromisoformat(v)
                                else:
                                    row[k] = date.fromisoformat(v)
                            except ValueError:
                                pass
                conn.execute(table.insert(), rows)
            print(f"  loaded {tsv_name}: {len(rows)} rows")

    print(f"\nCreated SQLite database at {DATABASE_PATH}")


# ============================================================================
# 入口
# ============================================================================
def main() -> None:
    """主入口."""
    print("=" * 70)
    print("NorthArc Photonics, Fiber Splicing Quality & Cost Control Dataset Generator")
    print(f"REFERENCE_DATE = {REFERENCE_DATE}")
    print("=" * 70)
    generate_all_tsv()
    print()
    create_sqlite_database()
    print("=" * 70)
    print("All done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
