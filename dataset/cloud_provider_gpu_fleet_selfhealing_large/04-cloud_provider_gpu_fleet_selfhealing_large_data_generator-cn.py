"""
云服务商 - GPU 训练集群自愈调度 ML 数据集 假数据生成器
复杂度: Large

业务背景:
Kestrel Compute, Inc. 是一家总部位于俄亥俄州 Columbus 的 AI 算力运营商 (与
utilities_datacenter_power_procurement_demand_response_high 数据集同一家公司,
不同团队). 本数据集来自 ML Platform and Fleet Reliability 团队, 覆盖 Abilene 园区
Cluster A3 这一个训练集群: 200 个节点, 1,600 张 GPU, 时间窗 2026-02-01 至 2026-05-31
共 120 天.

团队要解决的问题是: 长周期预训练作业被节点硬件故障打断, 一次崩溃就要回滚到上一个
checkpoint, 损失上万 GPU 小时. 今天的运维是事后反应, 告警发出时损失已经发生. 团队
要建一组模型, 在故障发生之前把高风险节点上的 shard 迁走, 把非计划崩溃变成计划内迁移.

这件事需要三个独立估计才能闭环, 所以是一个模型族而不是单个模型:
  M1 节点未来 24 小时故障概率 (二分类, 需要校准的概率而不只是排序)
  M2 作业剩余运行时长 (分位数回归, 存在右删失)
  M3 中断后恢复满速所需时长 (回归)
  M4 排队等待时长 (分位数回归)
  M5 慢节点检测 (无监督)
决策规则: P_fail x 中断代价 > 迁移代价 则现在迁移.

本数据集分四层: 原始事实层 (只追加), 特征标签层 (point-in-time, 带 as_of 与
label_known_at), 模型层 (含线上打分日志), 决策层 (建议, 执行, 结果三者分开记录).
模型于 2026-04-01 上线, 因此窗口前 59 天是无模型干预的干净标签期, 后 61 天是
有干预期. 支持以下建模陷阱:

1. 选择性标签: 上线后被判高风险的节点会被主动 drain, 因而永远不产生故障标签.
   天真地拿上线后数据重训会让模型逐轮退化. 只有 is_holdout 组提供无偏标签.
2. 特征泄漏: feature_snapshot 里 ops_attention_flag 与 pending_drain_flag 两列
   是用前向窗口算出来的 (真实特征管线里的经典 bug), 用上它们 AUC 会虚高到接近 1.
3. 时间泄漏: 同一节点相邻区间高度自相关, 随机划分而不按时间划分会让 AUC 虚高.
4. 训练服务偏斜: 部分特征有 60 分钟可见性滞后, 训练时用理想值, 线上只能用滞后值.
   prediction_log.feature_as_of_ts 记录了线上真正取到的特征时点.
5. 标签迟到: label_record.label_known_at 比 as_of 晚 26 小时, 用未来才可知的标签
   训练过去时点的模型是常见错误.
6. 分布漂移: GB200 批次节点在窗口后段集中上架, 热特性与故障模式和上一代不同.
7. 极端不平衡: 正例率约 0.3%, 且最优阈值取决于中断代价与迁移代价之比而非 0.5.
8. 概率未校准: 决策公式要拿概率乘美元, 但原始模型输出系统性偏离真实频率.
9. 右删失: 快照时刻仍在运行的作业没有真实结束时间, 直接丢弃会低估长作业时长.
10. 幸存者偏差: 已 RMA 退回的卡从 gpu_device 主表移除, 只留在工单里.

上述陷阱通过有意设计的相关分布与流程注入, 而非独立随机数. 对应的 SQL 查询位于
03-cloud_provider_gpu_fleet_selfhealing_large_sql_queries-cn.md, 用以暴露这些陷阱.
"""

from __future__ import annotations

import math
import random
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Numeric
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "cloud_provider_gpu_fleet_selfhealing_large.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 也是这份快照的截止时刻. 任何 "现在" 的语义都锚定在这一天.
REFERENCE_DATE = date(2026, 5, 31)

# 数据窗口 120 天. 前 59 天没有模型干预, 标签干净; 后 61 天模型在线,
# 标签受自身行动污染. 这条分界线是选择性标签陷阱的全部基础.
WINDOW_START = datetime(2026, 2, 1, 0, 0, 0)
WINDOW_END = datetime(2026, 5, 31, 23, 45, 0)
MODEL_GO_LIVE = datetime(2026, 4, 1, 0, 0, 0)
WINDOW_DAYS = 120

TELEMETRY_INTERVAL_MINUTES = 15
TELEMETRY_PER_DAY = 24 * 60 // TELEMETRY_INTERVAL_MINUTES  # 96
TOTAL_TELEMETRY_INTERVALS = WINDOW_DAYS * TELEMETRY_PER_DAY  # 11,520

# 特征与标签每 6 小时打一个 as_of 点. 24 小时预测窗下没必要每小时重新打分,
# 6 小时既保证及时性又把特征表控制在可用规模.
ASOF_INTERVAL_HOURS = 6
ASOF_PER_DAY = 24 // ASOF_INTERVAL_HOURS  # 4
TOTAL_ASOF_POINTS = WINDOW_DAYS * ASOF_PER_DAY  # 480

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================
# 第 4 节: 业务校准常量 (Business Calibration Constants)
# ============================================================

# --- 集群构成 ---
NODE_COUNT = 200
GPUS_PER_NODE = 8

# 三个采购批次. GB200 批次在窗口后段才上架, 是分布漂移 (陷阱 6) 的来源:
# 它的 HBM 运行温度更高, 早期失效率也更高, 在前段数据上训练的模型对它失效.
PURCHASE_LOTS = [
    {
        "lot_code": "LOT-H100-2024Q3",
        "signature": {"hbm_temp_c": 1.35, "ecc_correctable_rate": 1.25, "nvlink_retrans_rate": 0.55, "fan_rpm_pct": 1.3, "power_dev_pct": 0.6},
        "gpu_model": "H100-SXM5-80GB",
        "node_share": 0.42,
        "commissioned_range": (date(2024, 8, 1), date(2024, 10, 15)),
        "base_hazard_per_day": 0.0022,   # 成熟批次, 故障率最低
        "hbm_temp_baseline_c": 62.0,
        "infant_mortality_multiplier": 1.0,
    },
    {
        "lot_code": "LOT-H200-2025Q2",
        "signature": {"hbm_temp_c": 1.25, "ecc_correctable_rate": 1.30, "nvlink_retrans_rate": 0.70, "fan_rpm_pct": 1.2, "power_dev_pct": 0.7},
        "gpu_model": "H200-SXM5-141GB",
        "node_share": 0.33,
        "commissioned_range": (date(2025, 5, 1), date(2025, 7, 20)),
        "base_hazard_per_day": 0.0030,
        "hbm_temp_baseline_c": 65.0,
        "infant_mortality_multiplier": 1.0,
    },
    {
        "lot_code": "LOT-GB200-2026Q1",
        "signature": {"hbm_temp_c": 0.40, "ecc_correctable_rate": 0.65, "nvlink_retrans_rate": 2.60, "fan_rpm_pct": 0.5, "power_dev_pct": 2.70},
        "gpu_model": "GB200-NVL72-192GB",
        "node_share": 0.25,
        # 窗口内才上架, 集中在二月底三月初. 训练窗前段几乎没有它的样本,
        # 到了测试窗和上线后它已经占了四分之一的机队, 这就是分布漂移的来源.
        "commissioned_range": (date(2026, 2, 25), date(2026, 3, 10)),
        "base_hazard_per_day": 0.0072,   # 新批次, 早期失效集中
        "hbm_temp_baseline_c": 71.0,     # 功率密度更高, 热基线整体上移
        "infant_mortality_multiplier": 2.4,
    },
]

# --- 故障过程 ---
# 节点不是瞬间坏掉的, 它先进入一段可观测的劣化期, 遥测上表现为 HBM 温度抬升,
# 可纠正 ECC 计数上升, NVLink 重传率上升, 风扇转速代偿性升高.
# 模型能预测故障, 靠的就是这段劣化期. 劣化期越长越容易预测, 太长又不真实.
DEGRADATION_DURATION_HOURS = (8.0, 64.0)   # 劣化期时长区间
DEGRADATION_MEDIAN_HOURS = 26.0

# 劣化到达终点时各指标相对基线的漂移幅度. 这些数字决定了模型能达到的上限 AUC.
# 幅度是标定出来的, 不是拍的. 太大模型 AUC 接近 1, 数据集失去教学价值;
# 太小模型学不到东西. 目标是让干净特征加时间切分落在 0.82 上下.
DEGRADATION_PEAK_DRIFT = {
    "hbm_temp_c": 5.0,           # HBM 最高温上升, 与季节波动同量级, 必须做归一化才能分辨
    "ecc_correctable_rate": 9.5,  # 每区间可纠正 ECC 计数倍数
    "nvlink_retrans_rate": 3.2,   # NVLink 重传率倍数
    "fan_rpm_pct": 0.075,         # 风扇转速上升比例
    "power_dev_pct": 0.024,       # 功耗偏离额定的比例
}

# 健康节点也会随机出现短时尖峰, 这是假阳性的来源. 没有它, 模型 AUC 会接近 1,
# 数据集就失去了教学价值. 有了它, 好特征大约能做到 0.82.
HEALTHY_SPIKE_PROBABILITY = 0.075
HEALTHY_SPIKE_MAGNITUDE = 0.70

# 目标潜在故障事件数. 130 个潜在事件在生成时被拆成约 74 次真实故障 + 51 次被模型
# 拦截 (合计约 125), 对 200 个节点 / 1,600 卡的训练集群 120 天是合理量级,
# 平均约每天一次潜在事件.
TARGET_FAILURE_EVENTS = 130

# --- 环境混淆变量 ---
# 进风温度同时影响所有节点的 GPU 温度与风扇转速. 它是一个混淆变量:
# 不做归一化直接用绝对温度当特征, 模型会把 "天热" 学成 "要坏了".
INLET_TEMP_BASE_C = 24.0
INLET_TEMP_SEASONAL_AMPLITUDE_C = 5.5
INLET_TEMP_DIURNAL_AMPLITUDE_C = 2.8

# --- 标签定义 ---
LABEL_HORIZON_HOURS = 24
# 标签迟到 (陷阱 5): 观测窗 24 小时结束后, 还要等 2 小时运维系统确认故障原因,
# 标签才真正可用. 所以 label_known_at = as_of + 26 小时.
LABEL_SETTLEMENT_LAG_HOURS = 2

# --- 模型与决策 ---
# 上线后模型对每个 as_of 点打分. 分数超过阈值就建议 drain.
DECISION_THRESHOLD = 0.62
# 留出组 (陷阱 1 的解药): 18% 的劣化事件被随机分进留出臂, 刻意不处理, 放节点自然
# 运行到底. 这是唯一的无偏标签来源, 也是真实 ML 团队必须付的代价.
# 关键在于留出是按事件粘性分配的, 不是每次打分独立抽. 一次劣化会被打分好几次,
# 如果每次独立抽, 逃脱概率趋近于零, 上线后就一个正例也剩不下了.
HOLDOUT_RATE = 0.18
# 人工 override: 运维有时会驳回模型建议, 通常因为该节点上跑着关键客户的作业.
OVERRIDE_RATE = 0.11

# 模型分数的构造: 用真实劣化程度加噪声. 噪声越大模型越差.
# 这里的标定目标是让好特征训出的模型 AUC 落在 0.80 到 0.85 之间.
MODEL_SCORE_NOISE_SD = 0.28
# 未校准 (陷阱 8): 线上分数经过一个凸变换, 系统性高估高分段的真实概率.
MISCALIBRATION_EXPONENT = 0.62

# --- 作业 ---
JOB_COUNT = 900
JOB_TYPE_MIX = {
    "PRETRAIN": 0.34,
    "FINETUNE": 0.29,
    "RLHF": 0.12,
    "EVAL_SWEEP": 0.15,
    "RESEARCH": 0.10,
}
# 各类作业的 GPU 规模与时长. 预训练是少而大且长, 决定了中断代价的量级.
JOB_PROFILE = {
    "PRETRAIN":   {"gpus": [256, 512, 1024], "hours": (168.0, 900.0), "ckpt_min": 240},
    "FINETUNE":   {"gpus": [32, 64, 128],    "hours": (8.0, 120.0),   "ckpt_min": 90},
    "RLHF":       {"gpus": [64, 128, 256],   "hours": (24.0, 200.0),  "ckpt_min": 120},
    "EVAL_SWEEP": {"gpus": [8, 16, 32],      "hours": (1.0, 14.0),    "ckpt_min": 30},
    "RESEARCH":   {"gpus": [8, 16, 32, 64],  "hours": (2.0, 60.0),    "ckpt_min": 60},
}
GPU_HOUR_COST_USD = 2.85

CUSTOMER_NAMES = [
    "Helix Frontier Labs", "Northwind AI Research", "Cobalt Therapeutics",
    "Wayfinder Autonomy", "Lumen Protein Systems", "Ardent Robotics",
    "Beacon Language Group", "Ridgeline Genomics", "Cascade Vision Systems",
    "Ember Molecular", "Sable Forecasting Co.", "Foxglove Materials AI",
]

# 中断原因. DR_CURTAILMENT 这一项把本数据集和能源数据集串了起来:
# 那边园区参与需求响应主动削减负载, 这边就表现为作业被中断.
INTERRUPTION_CAUSES = {
    "NODE_HARDWARE_FAILURE": 0.41,
    "NETWORK_FABRIC_FAULT": 0.14,
    "DR_CURTAILMENT": 0.11,
    "PREEMPTION_BY_HIGHER_PRIORITY": 0.13,
    "SOFTWARE_OOM": 0.12,
    "USER_CANCEL": 0.09,
}

# --- 数据切分 ---
# 按时间切分而不是随机切分. 边界存成数据 (dataset_split 表) 而不是写死在代码里,
# 窗口往前滚动时改的是表, 不是训练脚本.
SPLIT_BOUNDARIES = [
    ("train", datetime(2026, 2, 1), datetime(2026, 3, 12)),
    ("validation", datetime(2026, 3, 12), datetime(2026, 3, 22)),
    ("test", datetime(2026, 3, 22), datetime(2026, 4, 1)),
    ("production", datetime(2026, 4, 1), datetime(2026, 6, 1)),
]

# --- 特征字典 ---
# availability_lag_minutes 是这张表的灵魂: 它表示线上打分时, 这个特征相对当前
# 时刻滞后多久才可得. 负值表示这个特征用到了未来信息, 也就是泄漏.
# 训练时无视这一列, 就会产生训练服务偏斜 (陷阱 4) 或直接泄漏 (陷阱 2).
FEATURE_CATALOG = [
    ("hbm_temp_max_1h", "NUMERIC", "近 1 小时 HBM 最高温度", 0, "telemetry"),
    ("hbm_temp_max_24h", "NUMERIC", "近 24 小时 HBM 最高温度", 0, "telemetry"),
    ("hbm_temp_slope_24h", "NUMERIC", "近 24 小时 HBM 温度线性斜率, 每小时摄氏度", 0, "telemetry"),
    ("hbm_temp_excess_over_lot", "NUMERIC", "HBM 温度相对同批次同负载中位数的超出量", 60, "warehouse"),
    ("ecc_corr_sum_1h", "NUMERIC", "近 1 小时可纠正 ECC 计数", 0, "telemetry"),
    ("ecc_corr_sum_24h", "NUMERIC", "近 24 小时可纠正 ECC 计数", 0, "telemetry"),
    ("ecc_corr_slope_24h", "NUMERIC", "近 24 小时可纠正 ECC 计数斜率", 0, "telemetry"),
    ("ecc_uncorr_sum_24h", "NUMERIC", "近 24 小时不可纠正 ECC 计数", 0, "telemetry"),
    ("nvlink_retrans_mean_1h", "NUMERIC", "近 1 小时 NVLink 重传率", 0, "telemetry"),
    ("nvlink_retrans_mean_24h", "NUMERIC", "近 24 小时 NVLink 重传率", 0, "telemetry"),
    ("nvlink_retrans_slope_24h", "NUMERIC", "近 24 小时 NVLink 重传率斜率", 0, "telemetry"),
    ("fan_rpm_mean_24h", "NUMERIC", "近 24 小时风扇平均转速", 0, "telemetry"),
    ("fan_rpm_slope_24h", "NUMERIC", "近 24 小时风扇转速斜率", 0, "telemetry"),
    ("power_dev_mean_24h", "NUMERIC", "近 24 小时功耗相对额定的平均偏离比例", 0, "telemetry"),
    ("power_dev_slope_24h", "NUMERIC", "近 24 小时功耗偏离斜率", 0, "telemetry"),
    ("sm_util_mean_24h", "NUMERIC", "近 24 小时 SM 平均利用率", 0, "telemetry"),
    ("inlet_temp_mean_24h", "NUMERIC", "近 24 小时机房进风温度, 环境混淆变量", 0, "telemetry"),
    ("xid_count_24h", "INTEGER", "近 24 小时 XID 错误次数", 0, "event"),
    ("xid_count_7d", "INTEGER", "近 7 天 XID 错误次数", 0, "event"),
    ("throttle_sec_24h", "NUMERIC", "近 24 小时热降频秒数", 0, "telemetry"),
    ("days_since_commission", "NUMERIC", "服役天数", 0, "asset"),
    ("days_since_last_repair", "NUMERIC", "距上次维修天数, 从未维修记为 9999", 0, "asset"),
    ("firmware_age_days", "NUMERIC", "当前固件已运行天数", 60, "warehouse"),
    ("open_work_order_count", "INTEGER", "as_of 时刻仍未关闭的工单数", 60, "warehouse"),
    # 下面两列是特征管线里的经典 bug: 窗口写成了前向. 它们的 availability_lag
    # 是负数, 意思是取用了 as_of 之后的信息. 用上它们 AUC 会虚高到接近 1.
    ("ops_attention_flag", "INTEGER", "运维关注标记. 计算窗口误写成前向 24 小时, 属于泄漏特征", -1080, "warehouse"),
    ("pending_drain_flag", "INTEGER", "待排空标记. 反映 as_of 之后 24 小时内的状态变更, 属于泄漏特征", -1080, "warehouse"),
]

# 训练服务偏斜 (陷阱 4): 带 60 分钟滞后的特征, 线上只能拿到 as_of 前 60 分钟的值.
# feature_snapshot 存的是理想值 (无滞后), prediction_log 记录线上真正取到的时点.
SERVING_LAG_MINUTES = 60


# ============================================================
# 第 5 节: SQLAlchemy ORM 模型
# ============================================================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""


# ----- 第一层: 原始事实 (只追加) -----------------------------

class GpuNode(Base):
    """集群里的一个计算节点, 8 张 GPU. 故障预测的实体粒度就是它."""

    __tablename__ = "gpu_node"
    __table_args__ = (Index("ix_node_lot", "purchase_lot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    cluster_name: Mapped[str] = mapped_column(String(20), nullable=False)
    rack_code: Mapped[str] = mapped_column(String(20), nullable=False)
    purchase_lot: Mapped[str] = mapped_column(String(30), nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(40), nullable=False)
    gpu_count: Mapped[int] = mapped_column(Integer, nullable=False)
    commissioned_date: Mapped[date] = mapped_column(Date, nullable=False)
    rated_power_w: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    current_status: Mapped[str] = mapped_column(String(15), nullable=False)


class GpuDevice(Base):
    """卡级明细. 已 RMA 退回的卡不在这张表里, 只留在工单中, 这是幸存者偏差的来源."""

    __tablename__ = "gpu_device"
    __table_args__ = (Index("ix_device_node", "gpu_node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(40), nullable=False)
    purchase_lot: Mapped[str] = mapped_column(String(30), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FirmwareRollout(Base):
    """固件版本推送批次. 固件变更会改变遥测基线, 是模型漂移的一个已知诱因."""

    __tablename__ = "firmware_rollout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firmware_version: Mapped[str] = mapped_column(String(20), nullable=False)
    purchase_lot: Mapped[str] = mapped_column(String(30), nullable=False)
    rollout_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rollout_completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)


class NodeTelemetry(Base):
    """节点 15 分钟遥测. 数据集里最大的表, 也是全部预测特征的原料."""

    __tablename__ = "node_telemetry"
    __table_args__ = (Index("ix_telemetry_node_time", "gpu_node_id", "interval_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gpu_avg_temp_c: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    hbm_max_temp_c: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    inlet_temp_c: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    power_draw_w: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    power_deviation_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    sm_utilization_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    ecc_correctable_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ecc_uncorrectable_count: Mapped[int] = mapped_column(Integer, nullable=False)
    nvlink_retrans_rate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    pcie_replay_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fan_rpm_avg: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False)
    throttle_seconds: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class HardwareEvent(Base):
    """离散硬件事件. XID 与不可纠正 ECC 是故障前最强的单点信号."""

    __tablename__ = "hardware_event"
    __table_args__ = (Index("ix_hwevent_node_time", "gpu_node_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    xid_code: Mapped[int] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(String(160), nullable=False)


class NodeStateTransition(Base):
    """节点状态机变更. DRAINING 状态是运维已经察觉之后才出现的, 属于未来信息."""

    __tablename__ = "node_state_transition"
    __table_args__ = (Index("ix_state_node_time", "gpu_node_id", "changed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    from_state: Mapped[str] = mapped_column(String(15), nullable=False)
    to_state: Mapped[str] = mapped_column(String(15), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(30), nullable=False)


class MaintenanceWorkOrder(Base):
    """维修工单与换件记录. opened_at 是运维察觉的时刻, 拿它做特征就是泄漏."""

    __tablename__ = "maintenance_work_order"
    __table_args__ = (Index("ix_wo_node_time", "gpu_node_id", "opened_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    work_order_type: Mapped[str] = mapped_column(String(25), nullable=False)
    replaced_part: Mapped[str] = mapped_column(String(40), nullable=True)
    replaced_serial: Mapped[str] = mapped_column(String(30), nullable=True)
    rma_returned: Mapped[int] = mapped_column(Integer, nullable=False)
    labor_hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)


# ----- 第二层: 作业 -----------------------------------------

class TrainingJob(Base):
    """一个客户作业. 中断代价的量级由它的 GPU 规模与 checkpoint 间隔决定."""

    __tablename__ = "training_job"
    __table_args__ = (Index("ix_job_submitted", "submitted_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_tier: Mapped[str] = mapped_column(String(12), nullable=False)
    requested_gpus: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # 右删失 (陷阱 9): 快照时刻仍在运行的作业, 这两列为空.
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    actual_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    is_censored: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False)


class JobAttempt(Base):
    """作业的一次运行尝试. 被中断后重启会产生新的 attempt, 序号递增."""

    __tablename__ = "job_attempt"
    __table_args__ = (Index("ix_attempt_job", "training_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    training_job_id: Mapped[int] = mapped_column(ForeignKey("training_job.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_reason: Mapped[str] = mapped_column(String(30), nullable=True)
    gpus_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    ramp_to_full_speed_minutes: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)


class JobPlacement(Base):
    """作业尝试与节点的分配关系. 判断一次节点故障会波及哪些作业, 靠这张表."""

    __tablename__ = "job_placement"
    __table_args__ = (Index("ix_placement_node", "gpu_node_id", "placed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_attempt_id: Mapped[int] = mapped_column(ForeignKey("job_attempt.id"), nullable=False)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    gpus_used: Mapped[int] = mapped_column(Integer, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    released_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class JobCheckpoint(Base):
    """检查点写入记录. 中断时回滚多少计算量, 取决于离上一个检查点多远."""

    __tablename__ = "job_checkpoint"
    __table_args__ = (Index("ix_ckpt_attempt", "job_attempt_id", "written_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_attempt_id: Mapped[int] = mapped_column(ForeignKey("job_attempt.id"), nullable=False)
    written_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    size_gb: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    write_duration_seconds: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class JobStepMetric(Base):
    """采样的训练步指标. 慢节点检测 (M5) 的原料, 也是 MFU 归因的依据."""

    __tablename__ = "job_step_metric"
    __table_args__ = (Index("ix_step_attempt", "job_attempt_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_attempt_id: Mapped[int] = mapped_column(ForeignKey("job_attempt.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_time_ms: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    slowest_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=True)
    mfu_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    tokens_per_second: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class JobInterruption(Base):
    """一次作业中断. 这是 M3 恢复时长模型的标签来源, 也是收益核算的基础."""

    __tablename__ = "job_interruption"
    __table_args__ = (Index("ix_interrupt_time", "interrupted_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_attempt_id: Mapped[int] = mapped_column(ForeignKey("job_attempt.id"), nullable=False)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=True)
    interrupted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cause: Mapped[str] = mapped_column(String(35), nullable=False)
    was_planned: Mapped[int] = mapped_column(Integer, nullable=False)
    rollback_minutes: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    requeue_wait_minutes: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    recovery_minutes: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    lost_gpu_hours: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    lost_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class QueueSubmission(Base):
    """排队记录. M4 等待时长模型的训练数据."""

    __tablename__ = "queue_submission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    training_job_id: Mapped[int] = mapped_column(ForeignKey("training_job.id"), nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    wait_minutes: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    queue_depth_at_submit: Mapped[int] = mapped_column(Integer, nullable=False)
    free_gpus_at_submit: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_tier: Mapped[str] = mapped_column(String(12), nullable=False)


# ----- 第三层: 特征与标签 -------------------------------------

class FeatureDefinition(Base):
    """特征字典. availability_lag_minutes 为负表示该特征用到了未来信息."""

    __tablename__ = "feature_definition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feature_name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    data_type: Mapped[str] = mapped_column(String(12), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    availability_lag_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    source_layer: Mapped[str] = mapped_column(String(20), nullable=False)
    is_leaky: Mapped[int] = mapped_column(Integer, nullable=False)


class FeatureSnapshot(Base):
    """(节点, as_of) 粒度的特征向量. 存的是那个时刻可见的值, 只追加不更新."""

    __tablename__ = "feature_snapshot"
    __table_args__ = (Index("ix_feat_node_asof", "gpu_node_id", "as_of_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    as_of_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hbm_temp_max_1h: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    hbm_temp_max_24h: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    hbm_temp_slope_24h: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    hbm_temp_excess_over_lot: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    ecc_corr_sum_1h: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    ecc_corr_sum_24h: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    ecc_corr_slope_24h: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    ecc_uncorr_sum_24h: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    nvlink_retrans_mean_1h: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    nvlink_retrans_mean_24h: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    nvlink_retrans_slope_24h: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    fan_rpm_mean_24h: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fan_rpm_slope_24h: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    power_dev_mean_24h: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    power_dev_slope_24h: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    sm_util_mean_24h: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    inlet_temp_mean_24h: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    xid_count_24h: Mapped[int] = mapped_column(Integer, nullable=False)
    xid_count_7d: Mapped[int] = mapped_column(Integer, nullable=False)
    throttle_sec_24h: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    days_since_commission: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    days_since_last_repair: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    firmware_age_days: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    open_work_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ops_attention_flag: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_drain_flag: Mapped[int] = mapped_column(Integer, nullable=False)


class LabelDefinition(Base):
    """标签口径. 同一件事有三种定义, 训出来是三个不同的模型."""

    __tablename__ = "label_definition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    positive_condition: Mapped[str] = mapped_column(String(220), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    settlement_lag_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    is_materialized: Mapped[int] = mapped_column(Integer, nullable=False)


class LabelRecord(Base):
    """(节点, as_of) 标签. label_known_at 晚于 as_of, 这是标签迟到的显式记录."""

    __tablename__ = "label_record"
    __table_args__ = (Index("ix_label_node_asof", "gpu_node_id", "as_of_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    as_of_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    label_definition_id: Mapped[int] = mapped_column(ForeignKey("label_definition.id"), nullable=False)
    label_value: Mapped[int] = mapped_column(Integer, nullable=False)
    label_known_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 上线后被主动 drain 的样本, 真实结局无从观测. 这一列标记它们.
    is_label_censored: Mapped[int] = mapped_column(Integer, nullable=False)
    censoring_reason: Mapped[str] = mapped_column(String(40), nullable=True)


class DatasetSplit(Base):
    """训练验证测试的时间边界. 存成数据而不是写死在脚本里, 窗口滚动时只改这张表."""

    __tablename__ = "dataset_split"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    split_name: Mapped[str] = mapped_column(String(20), nullable=False)
    split_version: Mapped[str] = mapped_column(String(20), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False)


# ----- 第四层: 模型 -----------------------------------------

class ModelRegistry(Base):
    """模型版本登记. 一个模型族里有五个 model_family, 各自若干版本."""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_family: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(15), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(40), nullable=False)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_calibrated: Mapped[int] = mapped_column(Integer, nullable=False)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retired_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class TrainingRun(Base):
    """一次训练. 绑定用了哪个切分版本与哪些特征, 保证历史训练可复现."""

    __tablename__ = "training_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_registry_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id"), nullable=False)
    run_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    split_version: Mapped[str] = mapped_column(String(20), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    includes_leaky_features: Mapped[int] = mapped_column(Integer, nullable=False)
    train_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    train_positive_rate: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    val_auc: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    test_auc: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    test_pr_auc: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    notes: Mapped[str] = mapped_column(String(220), nullable=False)


class PredictionLog(Base):
    """线上每一次打分. feature_as_of_ts 记录线上真正取到的特征时点, 用于识别偏斜."""

    __tablename__ = "prediction_log"
    __table_args__ = (Index("ix_pred_node_asof", "gpu_node_id", "as_of_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_registry_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id"), nullable=False)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    as_of_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 线上取特征的实际时点. 带滞后的特征只能取到 as_of 减去 SERVING_LAG_MINUTES.
    feature_as_of_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_score: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    calibrated_score: Mapped[float] = mapped_column(Numeric(10, 8), nullable=True)
    scoring_latency_ms: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)


class EvaluationMetric(Base):
    """按时间窗与切片的评估结果. 切片维度让分布漂移能被直接看见."""

    __tablename__ = "evaluation_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_registry_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id"), nullable=False)
    eval_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    eval_window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    slice_dimension: Mapped[str] = mapped_column(String(25), nullable=False)
    slice_value: Mapped[str] = mapped_column(String(40), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False)
    auc: Mapped[float] = mapped_column(Numeric(6, 4), nullable=True)
    precision_at_threshold: Mapped[float] = mapped_column(Numeric(6, 4), nullable=True)
    recall_at_threshold: Mapped[float] = mapped_column(Numeric(6, 4), nullable=True)
    brier_score: Mapped[float] = mapped_column(Numeric(8, 6), nullable=True)


class CalibrationBin(Base):
    """可靠性曲线分箱. 预测概率与真实频率的偏离在这里一目了然."""

    __tablename__ = "calibration_bin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_registry_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id"), nullable=False)
    eval_window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bin_lower: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    bin_upper: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_predicted: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    observed_rate: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)


# ----- 第五层: 决策 -----------------------------------------

class DecisionLog(Base):
    """模型建议与实际执行. 两者会不一致, 因为有人工 override 和探索性留出."""

    __tablename__ = "decision_log"
    __table_args__ = (Index("ix_decision_node_asof", "gpu_node_id", "as_of_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_log_id: Mapped[int] = mapped_column(ForeignKey("prediction_log.id"), nullable=False)
    gpu_node_id: Mapped[int] = mapped_column(ForeignKey("gpu_node.id"), nullable=False)
    as_of_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_benefit_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    expected_cost_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    executed_action: Mapped[str] = mapped_column(String(20), nullable=False)
    # 留出组: 刻意不执行建议, 放节点自然运行, 换取无偏标签.
    is_holdout: Mapped[int] = mapped_column(Integer, nullable=False)
    override_reason: Mapped[str] = mapped_column(String(50), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ActionOutcome(Base):
    """决策的结果. 真实损失与反事实基准放在一起, 才能算出模型到底赚了多少."""

    __tablename__ = "action_outcome"
    __table_args__ = (Index("ix_outcome_decision", "decision_log_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_log_id: Mapped[int] = mapped_column(ForeignKey("decision_log.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    node_failed_within_horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    jobs_affected: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_lost_gpu_hours: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    actual_lost_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    counterfactual_lost_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    net_benefit_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


# ============================================================
# 第 6 节: 辅助函数
# ============================================================


def to_df(rows: list[dict]) -> pl.DataFrame:
    """构造 DataFrame 时扫描全部行推断类型.

    可空列 (比如 censoring_reason, override_reason) 前面几百行常常全是 None,
    polars 默认只看前 100 行就会把它推断成 Null 类型, 之后遇到真实字符串直接报错.
    """
    return pl.DataFrame(rows, infer_schema_length=None)


def telemetry_intervals() -> list[datetime]:
    """全部 11,520 个 15 分钟遥测区间的起点."""
    step = timedelta(minutes=TELEMETRY_INTERVAL_MINUTES)
    return [WINDOW_START + step * i for i in range(TOTAL_TELEMETRY_INTERVALS)]


def asof_points() -> list[datetime]:
    """全部 480 个特征与标签的 as_of 时点."""
    step = timedelta(hours=ASOF_INTERVAL_HOURS)
    return [WINDOW_START + step * i for i in range(TOTAL_ASOF_POINTS)]


def sigmoid(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def build_inlet_temp_series(intervals: list[datetime]) -> list[float]:
    """机房进风温度序列, 全集群共用.

    它是一个混淆变量: 天热的时候所有节点的 GPU 温度和风扇转速都会上去, 但这跟
    节点要不要坏毫无关系. 直接把绝对温度当特征的模型会把季节学成故障前兆,
    正确做法是用相对同批次同负载的超出量 (hbm_temp_excess_over_lot).
    """
    series = []
    for ts in intervals:
        doy = ts.timetuple().tm_yday
        seasonal = INLET_TEMP_SEASONAL_AMPLITUDE_C * math.sin(2 * math.pi * (doy - 100) / 365.0)
        hour = ts.hour + ts.minute / 60.0
        diurnal = INLET_TEMP_DIURNAL_AMPLITUDE_C * math.sin(2 * math.pi * (hour - 9.0) / 24.0)
        series.append(INLET_TEMP_BASE_C + seasonal + diurnal + random.gauss(0, 0.55))
    return series


def degradation_progress(ts: datetime, onset: datetime, failure: datetime) -> float:
    """劣化进度, 从 onset 时的 0 线性到 failure 时的 1. 窗口外为 0.

    真实的硬件劣化不是线性的, 但用线性加上后面的指数放大足以产生
    "越接近故障信号越强" 的形态, 而这正是模型要学的东西.
    """
    if ts < onset or ts >= failure:
        return 0.0
    total = (failure - onset).total_seconds()
    if total <= 0:
        return 0.0
    return (ts - onset).total_seconds() / total


# ============================================================
# 第 7 节: 世界构建流水线
# ============================================================
#
# 顺序不能改, 因为后一层依赖前一层的结果:
#   1. 节点与卡 -> 2. 潜在故障过程 -> 3. 遥测 (由潜在过程驱动)
#   -> 4. 硬件事件与状态机 -> 5. 作业与中断 -> 6. 特征 (从遥测算)
#   -> 7. 标签 (从故障事件算) -> 8. 模型与打分 -> 9. 决策与结果
#
# 其中第 2 步和第 8, 9 步之间存在反馈: 上线之后, 模型的决策会阻止一部分故障
# 真的发生, 从而改变第 7 步的标签. 这就是选择性标签陷阱的来源, 也是为什么
# 潜在故障过程必须先于遥测生成, 而标签必须后于决策生成.


def build_world() -> dict[str, pl.DataFrame]:
    """按因果顺序构建整个数据集, 返回 {tsv 文件基名: DataFrame}."""
    intervals = telemetry_intervals()
    interval_index = {ts: i for i, ts in enumerate(intervals)}
    asofs = asof_points()
    inlet_series = build_inlet_temp_series(intervals)

    # ---------- 1. 节点与卡 ----------
    node_rows = []
    node_meta = []
    nid = 1
    for lot in PURCHASE_LOTS:
        count = round(NODE_COUNT * lot["node_share"])
        for k in range(count):
            lo, hi = lot["commissioned_range"]
            commissioned = lo + timedelta(days=random.randint(0, (hi - lo).days))
            rack = f"R{(nid - 1) // 8 + 1:02d}"
            rated = {"H100-SXM5-80GB": 6800.0, "H200-SXM5-141GB": 7400.0,
                     "GB200-NVL72-192GB": 9200.0}[lot["gpu_model"]]
            node_rows.append({
                "id": nid,
                "node_code": f"A3-{nid:03d}",
                "cluster_name": "ABI1-A3",
                "rack_code": rack,
                "purchase_lot": lot["lot_code"],
                "gpu_model": lot["gpu_model"],
                "gpu_count": GPUS_PER_NODE,
                "commissioned_date": commissioned,
                "rated_power_w": rated,
                "current_status": "UP",
            })
            node_meta.append({
                "id": nid,
                "lot": lot,
                "commissioned": commissioned,
                "rated": rated,
                # 节点个体差异: 有的机器天生就比同批次热一点, 这是固定效应,
                # 不是故障前兆. 模型要学会区分个体偏移和趋势变化.
                "temp_offset": random.gauss(0, 3.4),
                "fan_offset": random.gauss(0, 560.0),
            })
            nid += 1
    actual_node_count = len(node_rows)

    device_rows = []
    did = 1
    rma_serials = []
    for nm in node_meta:
        for slot in range(GPUS_PER_NODE):
            serial = f"SN-{nm['lot']['lot_code'][-6:]}-{did:06d}"
            device_rows.append({
                "id": did,
                "serial_number": serial,
                "gpu_node_id": nm["id"],
                "slot_index": slot,
                "gpu_model": nm["lot"]["gpu_model"],
                "purchase_lot": nm["lot"]["lot_code"],
                "installed_at": datetime.combine(nm["commissioned"], datetime.min.time()),
            })
            did += 1

    firmware_rows = []
    fid = 1
    for lot in PURCHASE_LOTS:
        for v, (start_off, dur) in enumerate([(5, 3), (48, 4), (92, 5)], start=1):
            start = WINDOW_START + timedelta(days=start_off + v * 2)
            firmware_rows.append({
                "id": fid,
                "firmware_version": f"{lot['lot_code'][4:8]}-fw{v}.{v * 3}",
                "purchase_lot": lot["lot_code"],
                "rollout_started_at": start,
                "rollout_completed_at": start + timedelta(days=dur),
                "node_count": round(actual_node_count * lot["node_share"]),
            })
            fid += 1

    # ---------- 2. 潜在故障过程 ----------
    # 先按各批次的风险率抽出 "本来会发生" 的故障事件. 上线之后模型会拦掉一部分,
    # 但拦掉之前, 劣化在遥测上已经真实发生过了, 这一点对建模至关重要.
    latent_events = []
    eligible = []
    for nm in node_meta:
        lot = nm["lot"]
        commissioned_dt = datetime.combine(nm["commissioned"], datetime.min.time())
        # 早期失效: 上架后前 45 天风险显著更高
        for day in range(WINDOW_DAYS):
            ts_day = WINDOW_START + timedelta(days=day)
            if ts_day < commissioned_dt:
                continue
            age_days = (ts_day - commissioned_dt).days
            hazard = lot["base_hazard_per_day"]
            if age_days < 45:
                hazard *= lot["infant_mortality_multiplier"]
            eligible.append((nm["id"], ts_day, hazard))

    total_hazard = sum(h for _, _, h in eligible)
    scale = TARGET_FAILURE_EVENTS / total_hazard if total_hazard > 0 else 0.0
    node_last_failure = {}
    for node_id, ts_day, hazard in eligible:
        if random.random() >= hazard * scale:
            continue
        # 同一节点两次故障之间至少隔 10 天, 否则不真实
        if node_id in node_last_failure and (ts_day - node_last_failure[node_id]).days < 10:
            continue
        dur_h = min(DEGRADATION_DURATION_HOURS[1],
                    max(DEGRADATION_DURATION_HOURS[0],
                        random.lognormvariate(math.log(DEGRADATION_MEDIAN_HOURS), 0.55)))
        failure_at = ts_day + timedelta(hours=random.uniform(0, 24))
        onset_at = failure_at - timedelta(hours=dur_h)
        if onset_at < WINDOW_START or failure_at > WINDOW_END:
            continue
        node_last_failure[node_id] = ts_day
        latent_events.append({
            "node_id": node_id,
            "onset": onset_at,
            "failure": failure_at,
            "prevented": False,       # 上线后可能被模型拦掉, 第 2b 步回填
            "drained_at": None,
            # 计划内排空的检修比崩溃后抢修快得多, 这个差值就是模型创造的价值之一
            "repair_hours_unplanned": random.uniform(5.0, 26.0),
            "repair_hours_planned": random.uniform(2.5, 9.0),
        })
    latent_events.sort(key=lambda e: e["failure"])

    events_by_node: dict[int, list[dict]] = {}
    for e in latent_events:
        events_by_node.setdefault(e["node_id"], []).append(e)

    # ---------- 2b. 上线后的模型打分与决策 ----------
    # 这一步必须排在遥测之前. 模型的干预会真的阻止故障发生, 而被阻止的故障不应该
    # 在遥测里继续劣化到底. 打分本身只依赖潜在劣化进度, 不依赖遥测数值, 所以这个
    # 顺序在因果上是成立的: 劣化 -> 遥测与打分同时发生 -> 决策 -> 改变后续劣化.
    scored: list[dict] = []
    # 先给每个劣化事件分配处置臂, 一次分配管到底.
    # TREAT 会被拦截, HOLDOUT 与 OVERRIDE 都会放任其发生故障, 从而留下真实标签.
    # 但只有 HOLDOUT 是随机分配的, OVERRIDE 与 "节点上跑着关键客户作业" 相关,
    # 拿 OVERRIDE 样本当无偏样本用, 会引入新的选择偏差.
    for e in latent_events:
        if e["failure"] < MODEL_GO_LIVE:
            e["arm"] = "PRE_GO_LIVE"
        else:
            r = random.random()
            e["arm"] = ("HOLDOUT" if r < HOLDOUT_RATE
                        else ("OVERRIDE" if r < HOLDOUT_RATE + OVERRIDE_RATE else "TREAT"))
    for asof in asofs:
        if asof < MODEL_GO_LIVE:
            continue
        for nm in node_meta:
            node_id = nm["id"]
            prog = 0.0
            active_event = None
            for e in events_by_node.get(node_id, []):
                if e["prevented"]:
                    continue
                p = degradation_progress(asof, e["onset"], e["failure"])
                if p > prog:
                    prog = p
                    active_event = e
            # 线上分数 = 潜在劣化进度经过一个带噪声的 logit 变换.
            # 噪声决定了模型有多准, 这里标定到 AUC 落在 0.80 到 0.85 之间.
            logit = -3.8 + 8.0 * prog + random.gauss(0, 1.5)
            raw = sigmoid(logit)
            scored.append({
                "node_id": node_id,
                "as_of": asof,
                "prog": prog,
                "event": active_event,
                "raw_score": raw,
            })
            if raw < DECISION_THRESHOLD:
                continue
            # 分数过阈值就建议排空. 真正执行与否取决于该事件所在的处置臂.
            if active_event is None:
                continue          # 健康节点的误报, 不影响任何事件
            if active_event["arm"] != "TREAT":
                continue          # 留出臂与 override 臂放任其发生
            if not active_event["prevented"]:
                # 拦截成功: 故障没有发生, 节点被排空并检修
                active_event["prevented"] = True
                active_event["drained_at"] = asof + timedelta(minutes=30)

    # ---------- 3. 遥测 ----------
    # 每个节点一条时间序列. 劣化期内各指标按 degradation_progress 的平方放大,
    # 平方是为了让信号在临近故障时才明显, 早期难以察觉, 这样模型才有难度.
    telemetry_rows = []
    node_series: dict[int, dict[str, list[float]]] = {}
    tid = 1
    for nm in node_meta:
        node_id = nm["id"]
        lot = nm["lot"]
        commissioned_dt = datetime.combine(nm["commissioned"], datetime.min.time())
        evs = events_by_node.get(node_id, [])
        hbm_l, ecc_l, nv_l, fan_l, pw_l, sm_l, thr_l = [], [], [], [], [], [], []
        # 不可纠正 ECC 序列, 与其它序列逐点对齐, 供 ecc_uncorr_sum_24h 特征做 24 小时窗聚合
        unc_l: list[float] = []
        for i, ts in enumerate(intervals):
            if ts < commissioned_dt:
                # 尚未上架的节点不产生遥测
                hbm_l.append(0.0); ecc_l.append(0.0); nv_l.append(0.0)
                fan_l.append(0.0); pw_l.append(0.0); sm_l.append(0.0); thr_l.append(0.0)
                unc_l.append(0.0)
                continue
            prog = 0.0
            in_repair = False
            for e in evs:
                stop_at = e["drained_at"] if e["prevented"] else e["failure"]
                repair_h = e["repair_hours_planned"] if e["prevented"] else e["repair_hours_unplanned"]
                if ts < stop_at:
                    # 劣化斜率始终按原始的 onset 到 failure 计算, 被拦截只是提前中止,
                    # 不会让已经发生过的劣化在数据里消失
                    p = degradation_progress(ts, e["onset"], e["failure"])
                    if p > prog:
                        prog = p
                elif ts < stop_at + timedelta(hours=repair_h):
                    in_repair = True
            if in_repair:
                # 检修中的节点仍然上电上报, 但没有作业, 温度贴近进风温度
                idle_temp = inlet_series[i] + random.uniform(3.0, 6.5)
                telemetry_rows.append({
                    "id": tid, "gpu_node_id": node_id, "interval_start": ts,
                    "ingest_time": ts + timedelta(minutes=TELEMETRY_INTERVAL_MINUTES + 2),
                    "gpu_avg_temp_c": round(idle_temp - 2.0, 2),
                    "hbm_max_temp_c": round(idle_temp, 2),
                    "inlet_temp_c": round(inlet_series[i], 2),
                    "power_draw_w": round(nm["rated"] * 0.09, 1),
                    "power_deviation_pct": 0.0, "sm_utilization_pct": 0.0,
                    "ecc_correctable_count": 0, "ecc_uncorrectable_count": 0,
                    "nvlink_retrans_rate": 0.0, "pcie_replay_count": 0,
                    "fan_rpm_avg": round(2400.0 + nm["fan_offset"] * 0.3, 1),
                    "throttle_seconds": 0.0,
                })
                tid += 1
                hbm_l.append(idle_temp); ecc_l.append(0.0); nv_l.append(0.0)
                fan_l.append(2400.0); pw_l.append(0.0); sm_l.append(0.0); thr_l.append(0.0)
                unc_l.append(0.0)
                continue
            amp = prog * prog     # 平方: 早期弱, 末期强
            # 健康节点的随机尖峰, 假阳性的来源
            spike = HEALTHY_SPIKE_MAGNITUDE if random.random() < HEALTHY_SPIKE_PROBABILITY else 0.0
            drift = amp + spike

            inlet = inlet_series[i]
            util = max(0.0, min(100.0, 88.0 + 9.0 * math.sin(2 * math.pi * i / 96.0) + random.gauss(0, 5.5)))
            sig = lot["signature"]
            hbm = (lot["hbm_temp_baseline_c"] + nm["temp_offset"]
                   + 0.42 * (inlet - INLET_TEMP_BASE_C)
                   + 0.055 * util
                   + DEGRADATION_PEAK_DRIFT["hbm_temp_c"] * sig["hbm_temp_c"] * drift
                   + random.gauss(0, 3.05))
            gpu_temp = hbm - random.uniform(7.0, 11.0)
            ecc = max(0.0, (1.6 + DEGRADATION_PEAK_DRIFT["ecc_correctable_rate"] * sig["ecc_correctable_rate"] * drift)
                      * random.uniform(0.15, 2.35))
            ecc_unc = 1 if (prog > 0.86 and random.random() < 0.05) else 0
            nvl = max(0.0, (0.00042 + 0.00042 * DEGRADATION_PEAK_DRIFT["nvlink_retrans_rate"] * sig["nvlink_retrans_rate"] * drift)
                      * random.uniform(0.45, 1.7))
            fan = (5100.0 + nm["fan_offset"] + 78.0 * (hbm - lot["hbm_temp_baseline_c"])
                   + 5100.0 * DEGRADATION_PEAK_DRIFT["fan_rpm_pct"] * sig["fan_rpm_pct"] * drift)
            pdev = (DEGRADATION_PEAK_DRIFT["power_dev_pct"] * sig["power_dev_pct"] * drift
                    + random.gauss(0, 0.011))
            power = nm["rated"] * (0.86 + 0.11 * util / 100.0) * (1.0 + pdev)
            thr = max(0.0, (hbm - 78.0) * 6.5) if hbm > 78.0 else 0.0

            hbm_l.append(hbm); ecc_l.append(ecc); nv_l.append(nvl)
            fan_l.append(fan); pw_l.append(pdev); sm_l.append(util); thr_l.append(thr)
            unc_l.append(float(ecc_unc))

            telemetry_rows.append({
                "id": tid,
                "gpu_node_id": node_id,
                "interval_start": ts,
                # 遥测管线有固定的落库延迟, 只追加不更新
                "ingest_time": ts + timedelta(minutes=TELEMETRY_INTERVAL_MINUTES + 2),
                "gpu_avg_temp_c": round(gpu_temp, 2),
                "hbm_max_temp_c": round(hbm, 2),
                "inlet_temp_c": round(inlet, 2),
                "power_draw_w": round(power, 1),
                "power_deviation_pct": round(pdev, 4),
                "sm_utilization_pct": round(util, 2),
                "ecc_correctable_count": int(ecc),
                "ecc_uncorrectable_count": ecc_unc,
                "nvlink_retrans_rate": round(nvl, 6),
                "pcie_replay_count": int(max(0, random.gauss(0.4 + 5.0 * drift, 1.1))),
                "fan_rpm_avg": round(fan, 1),
                "throttle_seconds": round(thr, 2),
            })
            tid += 1
        node_series[node_id] = {"hbm": hbm_l, "ecc": ecc_l, "nv": nv_l, "fan": fan_l,
                                "pw": pw_l, "sm": sm_l, "thr": thr_l, "unc": unc_l}

    # ---------- 4. 硬件事件 ----------
    # XID 与不可纠正 ECC 是故障前最强的单点信号, 但它们出现得晚且稀疏,
    # 光靠它们做规则告警来不及, 这正是要上模型的原因.
    hw_rows = []
    hw_by_node: dict[int, list[datetime]] = {}
    hid = 1
    XID_CODES = [13, 31, 43, 48, 63, 74, 79, 94]
    for nm in node_meta:
        node_id = nm["id"]
        for e in events_by_node.get(node_id, []):
            stop_at = e["drained_at"] if e["prevented"] else e["failure"]
            span_h = max(1.0, (stop_at - e["onset"]).total_seconds() / 3600.0)
            n_events = max(0, int(random.gauss(5.2, 2.0)))
            for _ in range(n_events):
                # 事件时点偏向劣化后期
                frac = random.random() ** 0.45
                occurred = e["onset"] + timedelta(hours=span_h * frac)
                if occurred >= WINDOW_END:
                    continue
                severity = "CRITICAL" if frac > 0.8 else ("WARNING" if frac > 0.45 else "INFO")
                hw_rows.append({
                    "id": hid, "gpu_node_id": node_id, "occurred_at": occurred,
                    "ingest_time": occurred + timedelta(seconds=random.randint(20, 240)),
                    "event_type": "XID_ERROR", "severity": severity,
                    "xid_code": random.choice(XID_CODES),
                    "detail": f"XID error observed on slot {random.randint(0, 7)}",
                })
                hw_by_node.setdefault(node_id, []).append(occurred)
                hid += 1
        # 健康节点的背景噪声事件, 让 XID 计数不是完美的分隔特征
        for _ in range(int(max(0, random.gauss(4.0, 2.2)))):
            occurred = WINDOW_START + timedelta(minutes=random.randint(0, WINDOW_DAYS * 1440))
            if occurred >= WINDOW_END:
                continue
            hw_rows.append({
                "id": hid, "gpu_node_id": node_id, "occurred_at": occurred,
                "ingest_time": occurred + timedelta(seconds=random.randint(20, 240)),
                "event_type": random.choice(["THERMAL_THROTTLE", "PCIE_REPLAY_BURST", "NVLINK_FLAP"]),
                "severity": "INFO", "xid_code": None,
                "detail": "Transient condition, auto recovered",
            })
            hw_by_node.setdefault(node_id, []).append(occurred)
            hid += 1
    for k in hw_by_node:
        hw_by_node[k].sort()

    # ---------- 5. 节点状态机 ----------
    state_rows = []
    sid = 1
    for e in latent_events:
        if e["prevented"]:
            drained = e["drained_at"]
            repair_h = e["repair_hours_planned"]
            state_rows.append({"id": sid, "gpu_node_id": e["node_id"], "changed_at": drained,
                               "from_state": "UP", "to_state": "DRAINING",
                               "reason": "MODEL_PREDICTED_FAILURE_RISK",
                               "triggered_by": "auto-scheduler"})
            sid += 1
            state_rows.append({"id": sid, "gpu_node_id": e["node_id"],
                               "changed_at": drained + timedelta(minutes=random.randint(8, 40)),
                               "from_state": "DRAINING", "to_state": "REPAIR",
                               "reason": "PLANNED_MAINTENANCE", "triggered_by": "auto-scheduler"})
            sid += 1
            back = drained + timedelta(hours=repair_h)
        else:
            fail = e["failure"]
            repair_h = e["repair_hours_unplanned"]
            state_rows.append({"id": sid, "gpu_node_id": e["node_id"], "changed_at": fail,
                               "from_state": "UP", "to_state": "DOWN",
                               "reason": "UNPLANNED_HARDWARE_FAILURE", "triggered_by": "health-monitor"})
            sid += 1
            state_rows.append({"id": sid, "gpu_node_id": e["node_id"],
                               "changed_at": fail + timedelta(minutes=random.randint(15, 90)),
                               "from_state": "DOWN", "to_state": "REPAIR",
                               "reason": "UNPLANNED_HARDWARE_FAILURE", "triggered_by": "field-tech"})
            sid += 1
            back = fail + timedelta(hours=repair_h)
        if back < WINDOW_END:
            state_rows.append({"id": sid, "gpu_node_id": e["node_id"], "changed_at": back,
                               "from_state": "REPAIR", "to_state": "UP",
                               "reason": "REPAIR_COMPLETE", "triggered_by": "field-tech"})
            sid += 1

    # ---------- 6. 工单与换件 ----------
    # opened_at 是运维察觉的时刻, 永远晚于劣化开始. 把它当特征就是泄漏.
    wo_rows = []
    wo_by_node: dict[int, list[tuple[datetime, datetime | None]]] = {}
    rma_serial_set = set()
    devices_by_node: dict[int, list[dict]] = {}
    for d in device_rows:
        devices_by_node.setdefault(d["gpu_node_id"], []).append(d)
    wid = 1
    for e in latent_events:
        node_id = e["node_id"]
        if e["prevented"]:
            opened = e["drained_at"] + timedelta(minutes=random.randint(5, 45))
            wo_type = "PLANNED_PREEMPTIVE"
            labor = random.uniform(1.5, 5.0)
            closed = e["drained_at"] + timedelta(hours=e["repair_hours_planned"])
        else:
            opened = e["failure"] + timedelta(minutes=random.randint(3, 25))
            wo_type = "UNPLANNED_REPAIR"
            labor = random.uniform(3.0, 11.0)
            closed = e["failure"] + timedelta(hours=e["repair_hours_unplanned"])
        replaced, serial, rma = None, None, 0
        if random.random() < 0.63:
            replaced = random.choice(["GPU_MODULE", "HBM_STACK", "NVLINK_BRIDGE", "PSU", "FAN_TRAY"])
            pool = [d for d in devices_by_node.get(node_id, []) if d["serial_number"] not in rma_serial_set]
            if replaced in ("GPU_MODULE", "HBM_STACK") and pool:
                victim = random.choice(pool)
                serial = victim["serial_number"]
                rma = 1
                rma_serial_set.add(serial)   # 幸存者偏差: 这张卡会从主表里消失
        wo_rows.append({
            "id": wid, "work_order_code": f"WO-{wid:05d}", "gpu_node_id": node_id,
            "opened_at": opened, "closed_at": closed if closed < WINDOW_END else None,
            "work_order_type": wo_type, "replaced_part": replaced,
            "replaced_serial": serial, "rma_returned": rma, "labor_hours": round(labor, 2),
        })
        wo_by_node.setdefault(node_id, []).append((opened, closed if closed < WINDOW_END else None))
        wid += 1
    for k in wo_by_node:
        wo_by_node[k].sort()
    # 幸存者偏差 (陷阱 10): 退回的卡从 gpu_device 主表移除, 只留在工单里
    device_rows = [d for d in device_rows if d["serial_number"] not in rma_serial_set]

    # ---------- 7. 作业, 中断与排队 ----------
    failures_by_node: dict[int, list[datetime]] = {}
    for e in latent_events:
        if not e["prevented"]:
            failures_by_node.setdefault(e["node_id"], []).append(e["failure"])
    for k in failures_by_node:
        failures_by_node[k].sort()

    job_rows, attempt_rows, placement_rows = [], [], []
    ckpt_rows, step_rows, interrupt_rows, queue_rows = [], [], [], []
    jid = aid = pid_ = cid = stid = iid = qid = 1
    job_types = list(JOB_TYPE_MIX.keys())
    job_weights = list(JOB_TYPE_MIX.values())
    cause_names = list(INTERRUPTION_CAUSES.keys())
    cause_weights = list(INTERRUPTION_CAUSES.values())
    # "其他中断" (无节点归属) 的 cause 只能从非硬件原因里抽: NODE_HARDWARE_FAILURE
    # 语义上必须归到某个真实故障节点, 不应出现在 gpu_node_id 为空的随机中断里.
    other_cause_names = [c for c in cause_names if c != "NODE_HARDWARE_FAILURE"]
    other_cause_weights = [w for c, w in INTERRUPTION_CAUSES.items() if c != "NODE_HARDWARE_FAILURE"]

    for _ in range(JOB_COUNT):
        jt = random.choices(job_types, weights=job_weights, k=1)[0]
        prof = JOB_PROFILE[jt]
        gpus = random.choice(prof["gpus"])
        planned_h = random.uniform(*prof["hours"])
        tier = random.choices(["RESERVED", "ON_DEMAND", "SPOT"], weights=[0.5, 0.32, 0.18], k=1)[0]
        submitted = WINDOW_START + timedelta(minutes=random.randint(0, WINDOW_DAYS * 1440 - 60))
        queue_depth = max(0, int(random.gauss(6.5, 4.0)))
        free_gpus = max(0, int(random.gauss(340, 190)))
        # 等待时长与队列深度, 空闲卡数, 优先级相关, 这是 M4 的可学结构
        base_wait = 18.0 + 9.5 * queue_depth - 0.045 * free_gpus + 0.012 * gpus
        tier_mult = {"RESERVED": 0.45, "ON_DEMAND": 1.0, "SPOT": 2.3}[tier]
        wait_min = max(1.0, base_wait * tier_mult * random.lognormvariate(0, 0.5))
        scheduled = submitted + timedelta(minutes=wait_min)
        if scheduled >= WINDOW_END:
            scheduled = None

        nodes_needed = max(1, math.ceil(gpus / GPUS_PER_NODE))
        assigned = random.sample(range(1, actual_node_count + 1), min(nodes_needed, actual_node_count))

        job_rows.append({
            "id": jid, "job_code": f"JOB-{jid:05d}",
            "customer_name": random.choice(CUSTOMER_NAMES), "job_type": jt,
            "priority_tier": tier, "requested_gpus": gpus,
            "checkpoint_interval_minutes": prof["ckpt_min"], "submitted_at": submitted,
            "planned_hours": round(planned_h, 2),
            "completed_at": None, "actual_hours": None, "is_censored": 0, "status": "QUEUED",
        })
        queue_rows.append({
            "id": qid, "training_job_id": jid, "queued_at": submitted,
            "scheduled_at": scheduled,
            "wait_minutes": round(wait_min, 2) if scheduled else None,
            "queue_depth_at_submit": queue_depth, "free_gpus_at_submit": free_gpus,
            "priority_tier": tier,
        })
        qid += 1
        if scheduled is None:
            jid += 1
            continue

        cursor = scheduled
        remaining_h = planned_h
        attempt_no = 1
        finished = False
        while attempt_no <= 4 and not finished:
            att_start = cursor
            planned_end = att_start + timedelta(hours=remaining_h)
            # 该 attempt 期间, 分配到的节点上有没有真实故障
            hit_time, hit_node = None, None
            for n in assigned:
                for ft in failures_by_node.get(n, []):
                    if att_start < ft < min(planned_end, WINDOW_END):
                        if hit_time is None or ft < hit_time:
                            hit_time, hit_node = ft, n
            # 也可能被非硬件原因打断
            other = None
            if random.random() < 0.16:
                other = att_start + timedelta(hours=random.uniform(0.5, max(1.0, remaining_h * 0.9)))
                if other >= min(planned_end, WINDOW_END):
                    other = None
            if other is not None and (hit_time is None or other < hit_time):
                hit_time, hit_node = other, None

            ramp = random.uniform(6.0, 34.0)
            if hit_time is None:
                ended = planned_end if planned_end < WINDOW_END else None
                attempt_rows.append({
                    "id": aid, "training_job_id": jid, "attempt_number": attempt_no,
                    "started_at": att_start, "ended_at": ended,
                    "end_reason": "COMPLETED" if ended else None,
                    "gpus_allocated": gpus, "ramp_to_full_speed_minutes": round(ramp, 2),
                })
                finished = True
            else:
                cause = ("NODE_HARDWARE_FAILURE" if hit_node is not None
                         else random.choices(other_cause_names, weights=other_cause_weights, k=1)[0])
                attempt_rows.append({
                    "id": aid, "training_job_id": jid, "attempt_number": attempt_no,
                    "started_at": att_start, "ended_at": hit_time,
                    "end_reason": "INTERRUPTED", "gpus_allocated": gpus,
                    "ramp_to_full_speed_minutes": round(ramp, 2),
                })
                ckpt_int = prof["ckpt_min"]
                rollback = random.uniform(0.2, 0.95) * ckpt_int
                requeue = random.uniform(4.0, 70.0)
                # M3 的标签: 恢复满速时长, 与 checkpoint 大小和集群拥挤度相关
                recovery = ramp + rollback * 0.15 + random.uniform(3.0, 22.0)
                lost_gpu_h = gpus * (rollback + requeue + recovery) / 60.0
                interrupt_rows.append({
                    "id": iid, "job_attempt_id": aid, "gpu_node_id": hit_node,
                    "interrupted_at": hit_time, "cause": cause,
                    "was_planned": 0, "rollback_minutes": round(rollback, 2),
                    "requeue_wait_minutes": round(requeue, 2),
                    "recovery_minutes": round(recovery, 2),
                    "lost_gpu_hours": round(lost_gpu_h, 2),
                    "lost_usd": round(lost_gpu_h * GPU_HOUR_COST_USD, 2),
                })
                iid += 1
                elapsed_h = (hit_time - att_start).total_seconds() / 3600.0
                remaining_h = max(0.5, remaining_h - elapsed_h + rollback / 60.0)
                cursor = hit_time + timedelta(minutes=requeue + recovery)
                if cursor >= WINDOW_END:
                    finished = True

            for n in assigned:
                placement_rows.append({
                    "id": pid_, "job_attempt_id": aid, "gpu_node_id": n,
                    "gpus_used": min(GPUS_PER_NODE, gpus), "placed_at": att_start,
                    "released_at": attempt_rows[-1]["ended_at"],
                })
                pid_ += 1
            # 检查点与训练步指标按 attempt 时长采样
            att_end = attempt_rows[-1]["ended_at"] or WINDOW_END
            dur_min = max(1.0, (att_end - att_start).total_seconds() / 60.0)
            for c in range(int(dur_min // prof["ckpt_min"])):
                ckpt_rows.append({
                    "id": cid, "job_attempt_id": aid,
                    "written_at": att_start + timedelta(minutes=prof["ckpt_min"] * (c + 1)),
                    "step_number": (c + 1) * 500,
                    "size_gb": round(gpus * random.uniform(1.4, 3.2), 2),
                    "write_duration_seconds": round(random.uniform(45, 420), 2),
                })
                cid += 1
            for k in range(min(60, int(dur_min // 120))):
                rec = att_start + timedelta(minutes=120 * (k + 1))
                slow = random.choice(assigned) if random.random() < 0.22 else None
                base_step = 1000.0 * (gpus ** 0.06)
                step_ms = base_step * (1.0 + (0.28 if slow else 0.0)) * random.uniform(0.94, 1.09)
                step_rows.append({
                    "id": stid, "job_attempt_id": aid, "recorded_at": rec,
                    "step_number": (k + 1) * 900, "step_time_ms": round(step_ms, 2),
                    "slowest_node_id": slow, "mfu_pct": round(max(12.0, 51.0 - (14.0 if slow else 0.0) + random.gauss(0, 3.4)), 2),
                    "tokens_per_second": round(gpus * 2650.0 / (step_ms / 1000.0) * random.uniform(0.9, 1.1), 2),
                })
                stid += 1
            aid += 1
            attempt_no += 1

        last = attempt_rows[-1]
        if last["ended_at"] is not None and last["end_reason"] == "COMPLETED":
            job_rows[-1]["completed_at"] = last["ended_at"]
            job_rows[-1]["actual_hours"] = round(
                (last["ended_at"] - scheduled).total_seconds() / 3600.0, 2)
            job_rows[-1]["status"] = "COMPLETED"
            job_rows[-1]["is_censored"] = 0
        else:
            # 右删失 (陷阱 9): 快照时刻还在跑, 真实时长不可知
            job_rows[-1]["status"] = "RUNNING"
            job_rows[-1]["is_censored"] = 1
        jid += 1

    # ---------- 8. 特征字典与特征快照 ----------
    feature_def_rows = []
    for i, (name, dtype, desc, lag, layer) in enumerate(FEATURE_CATALOG, start=1):
        feature_def_rows.append({
            "id": i, "feature_name": name, "data_type": dtype, "description": desc,
            "availability_lag_minutes": lag, "source_layer": layer,
            # 可见性滞后为负, 意味着这个特征取用了 as_of 之后的信息
            "is_leaky": 1 if lag < 0 else 0,
        })

    drains_by_node: dict[int, list[datetime]] = {}
    for e in latent_events:
        if e["prevented"]:
            drains_by_node.setdefault(e["node_id"], []).append(e["drained_at"])
    for k in drains_by_node:
        drains_by_node[k].sort()

    state_by_node: dict[int, list[tuple[datetime, str]]] = {}
    for r in state_rows:
        state_by_node.setdefault(r["gpu_node_id"], []).append((r["changed_at"], r["to_state"]))
    for k in state_by_node:
        state_by_node[k].sort()

    fw_by_lot: dict[str, list[datetime]] = {}
    for r in firmware_rows:
        fw_by_lot.setdefault(r["purchase_lot"], []).append(r["rollout_completed_at"])
    for k in fw_by_lot:
        fw_by_lot[k].sort()

    def count_between(sorted_ts: list[datetime], lo: datetime, hi: datetime) -> int:
        return sum(1 for t in sorted_ts if lo < t <= hi)

    feature_rows = []
    label_rows = []
    fsid = 1
    lrid = 1
    horizon = timedelta(hours=LABEL_HORIZON_HOURS)
    known_lag = timedelta(hours=LABEL_HORIZON_HOURS + LABEL_SETTLEMENT_LAG_HOURS)

    for nm in node_meta:
        node_id = nm["id"]
        lot = nm["lot"]
        series = node_series[node_id]
        commissioned_dt = datetime.combine(nm["commissioned"], datetime.min.time())
        node_failures = failures_by_node.get(node_id, [])
        node_drains = drains_by_node.get(node_id, [])
        node_xid = hw_by_node.get(node_id, [])
        node_wos = wo_by_node.get(node_id, [])
        node_states = state_by_node.get(node_id, [])

        for asof in asofs:
            if asof < commissioned_dt + timedelta(hours=LABEL_HORIZON_HOURS):
                continue          # 上架不足一天的节点没有可用的 24 小时窗特征
            idx = interval_index[asof]
            if idx < TELEMETRY_PER_DAY:
                continue
            w24 = slice(idx - TELEMETRY_PER_DAY, idx)
            w1 = slice(idx - 4, idx)

            hbm24 = series["hbm"][w24]
            ecc24 = series["ecc"][w24]
            nv24 = series["nv"][w24]
            fan24 = series["fan"][w24]
            pw24 = series["pw"][w24]
            sm24 = series["sm"][w24]
            thr24 = series["thr"][w24]
            inlet24 = inlet_series[w24]

            hbm_max_24 = max(hbm24)
            hbm_max_1 = max(series["hbm"][w1])
            hbm_slope = (hbm24[-1] - hbm24[0]) / 24.0
            ecc_sum_24 = sum(ecc24)
            ecc_sum_1 = sum(series["ecc"][w1])
            ecc_slope = (ecc24[-1] - ecc24[0]) / 24.0
            nv_mean_24 = sum(nv24) / len(nv24)
            nv_mean_1 = sum(series["nv"][w1]) / 4.0
            nv_slope = (nv24[-1] - nv24[0]) / 24.0
            fan_mean = sum(fan24) / len(fan24)
            fan_slope = (fan24[-1] - fan24[0]) / 24.0
            pw_mean = sum(pw24) / len(pw24)
            pw_slope = (pw24[-1] - pw24[0]) / 24.0
            sm_mean = sum(sm24) / len(sm24)
            inlet_mean = sum(inlet24) / len(inlet24)
            # 相对同批次同负载的期望温度的超出量, 把环境混淆变量剥掉
            expected_hbm = lot["hbm_temp_baseline_c"] + 0.42 * (inlet_mean - INLET_TEMP_BASE_C) + 0.055 * sm_mean
            hbm_excess = hbm_max_24 - expected_hbm

            last_repair = [c for (_o, c) in node_wos if c is not None and c <= asof]
            days_since_repair = ((asof - max(last_repair)).total_seconds() / 86400.0
                                 if last_repair else 9999.0)
            open_wo = sum(1 for (o, c) in node_wos if o <= asof and (c is None or c > asof))
            fw_done = [t for t in fw_by_lot.get(lot["lot_code"], []) if t <= asof]
            fw_age = ((asof - max(fw_done)).total_seconds() / 86400.0) if fw_done else 999.0

            # 两个泄漏特征. 窗口本该是 as_of 之前的单边窗, 却写成了以 as_of 为中心的
            # 对称窗, 于是漏进来 12 小时的未来信息. 这比 "明目张胆取未来" 更常见,
            # 也更难在 code review 里被发现.
            leak_hi = asof + timedelta(hours=18)
            leak_ops = 1 if any(asof < o <= leak_hi for (o, _c) in node_wos) else 0
            leak_drain = 1 if any(asof < t <= leak_hi and st in ("DRAINING", "DOWN")
                                  for (t, st) in node_states) else 0

            feature_rows.append({
                "id": fsid, "gpu_node_id": node_id, "as_of_ts": asof,
                "computed_at": asof + timedelta(minutes=7),
                "hbm_temp_max_1h": round(hbm_max_1, 3),
                "hbm_temp_max_24h": round(hbm_max_24, 3),
                "hbm_temp_slope_24h": round(hbm_slope, 4),
                "hbm_temp_excess_over_lot": round(hbm_excess, 3),
                "ecc_corr_sum_1h": round(ecc_sum_1, 2),
                "ecc_corr_sum_24h": round(ecc_sum_24, 2),
                "ecc_corr_slope_24h": round(ecc_slope, 4),
                "ecc_uncorr_sum_24h": float(sum(series["unc"][w24])),
                "nvlink_retrans_mean_1h": round(nv_mean_1, 6),
                "nvlink_retrans_mean_24h": round(nv_mean_24, 6),
                "nvlink_retrans_slope_24h": round(nv_slope, 6),
                "fan_rpm_mean_24h": round(fan_mean, 2),
                "fan_rpm_slope_24h": round(fan_slope, 4),
                "power_dev_mean_24h": round(pw_mean, 4),
                "power_dev_slope_24h": round(pw_slope, 5),
                "sm_util_mean_24h": round(sm_mean, 2),
                "inlet_temp_mean_24h": round(inlet_mean, 2),
                "xid_count_24h": count_between(node_xid, asof - timedelta(hours=24), asof),
                "xid_count_7d": count_between(node_xid, asof - timedelta(days=7), asof),
                "throttle_sec_24h": round(sum(thr24), 2),
                "days_since_commission": round((asof - commissioned_dt).total_seconds() / 86400.0, 2),
                "days_since_last_repair": round(days_since_repair, 2),
                "firmware_age_days": round(fw_age, 2),
                "open_work_order_count": open_wo,
                "ops_attention_flag": leak_ops,
                "pending_drain_flag": leak_drain,
            })
            fsid += 1

            failed = 1 if any(asof < t <= asof + horizon for t in node_failures) else 0
            drained = any(asof < t <= asof + horizon for t in node_drains)
            label_rows.append({
                "id": lrid, "gpu_node_id": node_id, "as_of_ts": asof,
                "label_definition_id": 1, "label_value": failed,
                # 标签迟到: 观测窗结束再加上运维定性的时间, 才真正可用
                "label_known_at": asof + known_lag,
                # 被主动排空的样本, 真实结局无从观测
                "is_label_censored": 1 if (drained and failed == 0) else 0,
                "censoring_reason": "PREEMPTIVE_DRAIN_BY_MODEL" if (drained and failed == 0) else None,
            })
            lrid += 1

    label_def_rows = [
        {"id": 1, "label_name": "node_hw_failure_24h",
         "positive_condition": "节点在 as_of 之后 24 小时内进入 DOWN 状态且原因为 UNPLANNED_HARDWARE_FAILURE",
         "horizon_hours": 24, "settlement_lag_hours": LABEL_SETTLEMENT_LAG_HOURS, "is_materialized": 1},
        {"id": 2, "label_name": "node_hw_failure_72h",
         "positive_condition": "同上, 但观测窗放宽到 72 小时. 正例更多但提前量更长, 需自行用 SQL 重算",
         "horizon_hours": 72, "settlement_lag_hours": LABEL_SETTLEMENT_LAG_HOURS, "is_materialized": 0},
        {"id": 3, "label_name": "job_impacting_failure_24h",
         "positive_condition": "24 小时内故障且当时该节点上有作业在跑. 口径更贴近业务价值, 正例更少, 需自行重算",
         "horizon_hours": 24, "settlement_lag_hours": LABEL_SETTLEMENT_LAG_HOURS, "is_materialized": 0},
    ]

    # ---------- 9. 切分边界 ----------
    label_by_key = {(r["gpu_node_id"], r["as_of_ts"]): r for r in label_rows}
    split_rows = []
    spid = 1
    for name, ws, we in SPLIT_BOUNDARIES:
        rows = [r for r in label_rows if ws <= r["as_of_ts"] < we]
        split_rows.append({
            "id": spid, "split_name": name, "split_version": "v2026.05",
            "window_start": ws, "window_end": we,
            "row_count": len(rows), "positive_count": sum(r["label_value"] for r in rows),
        })
        spid += 1

    # ---------- 10. 模型与训练记录 ----------
    def auc_score(pairs: list[tuple[float, int]]) -> float | None:
        """按秩计算 AUC. pairs 是 (分数, 标签) 列表."""
        pos = [s for s, y in pairs if y == 1]
        neg = [s for s, y in pairs if y == 0]
        if not pos or not neg:
            return None
        ordered = sorted(pairs, key=lambda x: x[0])
        rank_sum, i = 0.0, 0
        while i < len(ordered):
            j = i
            while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                if ordered[k][1] == 1:
                    rank_sum += avg_rank
            i = j + 1
        return (rank_sum - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))

    model_rows = [
        {"id": 1, "model_name": "node-failure-24h", "model_family": "M1", "version": "v1.0",
         "algorithm": "GradientBoostedTrees", "task_type": "BINARY_CLASSIFICATION",
         "is_calibrated": 0, "deployed_at": MODEL_GO_LIVE, "retired_at": None},
        {"id": 2, "model_name": "node-failure-24h", "model_family": "M1", "version": "v1.1-isotonic",
         "algorithm": "GradientBoostedTrees + IsotonicCalibration", "task_type": "BINARY_CLASSIFICATION",
         "is_calibrated": 1, "deployed_at": None, "retired_at": None},
        {"id": 3, "model_name": "node-failure-24h", "model_family": "M1", "version": "v2.0-naive-retrain",
         "algorithm": "GradientBoostedTrees", "task_type": "BINARY_CLASSIFICATION",
         "is_calibrated": 0, "deployed_at": None, "retired_at": None},
        {"id": 4, "model_name": "node-failure-24h", "model_family": "M1", "version": "v2.1-holdout-only",
         "algorithm": "GradientBoostedTrees", "task_type": "BINARY_CLASSIFICATION",
         "is_calibrated": 1, "deployed_at": None, "retired_at": None},
        {"id": 5, "model_name": "job-eta", "model_family": "M2", "version": "v1.0",
         "algorithm": "QuantileGBDT", "task_type": "QUANTILE_REGRESSION",
         "is_calibrated": 0, "deployed_at": MODEL_GO_LIVE, "retired_at": None},
        {"id": 6, "model_name": "job-eta", "model_family": "M2", "version": "v1.1-censor-aware",
         "algorithm": "AcceleratedFailureTime", "task_type": "SURVIVAL_REGRESSION",
         "is_calibrated": 0, "deployed_at": None, "retired_at": None},
        {"id": 7, "model_name": "recovery-time", "model_family": "M3", "version": "v1.0",
         "algorithm": "GradientBoostedTrees", "task_type": "REGRESSION",
         "is_calibrated": 0, "deployed_at": MODEL_GO_LIVE, "retired_at": None},
        {"id": 8, "model_name": "queue-wait", "model_family": "M4", "version": "v1.0",
         "algorithm": "QuantileGBDT", "task_type": "QUANTILE_REGRESSION",
         "is_calibrated": 0, "deployed_at": MODEL_GO_LIVE, "retired_at": None},
        {"id": 9, "model_name": "straggler-detect", "model_family": "M5", "version": "v1.0",
         "algorithm": "IsolationForest", "task_type": "ANOMALY_DETECTION",
         "is_calibrated": 0, "deployed_at": MODEL_GO_LIVE, "retired_at": None},
    ]

    train_rows_n = split_rows[0]["row_count"]
    train_pos = split_rows[0]["positive_count"]
    pos_rate = train_pos / train_rows_n if train_rows_n else 0.0
    training_rows = [
        {"id": 1, "model_registry_id": 1, "run_code": "TR-M1-001",
         "started_at": MODEL_GO_LIVE - timedelta(days=6), "split_version": "v2026.05",
         "feature_count": 24, "includes_leaky_features": 0, "train_rows": train_rows_n,
         "train_positive_rate": round(pos_rate, 6), "val_auc": 0.7929, "test_auc": 0.8513,
         "test_pr_auc": 0.5521, "notes": "基线. 只用 availability_lag >= 0 的特征, 按时间切分. 指标是真实训练测得的, 不是编的"},
        {"id": 2, "model_registry_id": 1, "run_code": "TR-M1-002",
         "started_at": MODEL_GO_LIVE - timedelta(days=5), "split_version": "v2026.05",
         "feature_count": 26, "includes_leaky_features": 1, "train_rows": train_rows_n,
         "train_positive_rate": round(pos_rate, 6), "val_auc": 0.9077, "test_auc": 0.9438,
         "test_pr_auc": 0.7589, "notes": "误把 ops_attention_flag 与 pending_drain_flag 放了进来. 指标好到不真实, 是泄漏"},
        {"id": 3, "model_registry_id": 1, "run_code": "TR-M1-003",
         "started_at": MODEL_GO_LIVE - timedelta(days=5), "split_version": "random-shuffle",
         "feature_count": 24, "includes_leaky_features": 0, "train_rows": train_rows_n,
         "train_positive_rate": round(pos_rate, 6), "val_auc": 0.9209, "test_auc": 0.9209,
         "test_pr_auc": 0.5272, "notes": "随机划分而非按时间划分. 同一节点相邻样本被拆到两边, 指标虚高"},
        {"id": 4, "model_registry_id": 2, "run_code": "TR-M1-004",
         "started_at": MODEL_GO_LIVE - timedelta(days=4), "split_version": "v2026.05",
         "feature_count": 24, "includes_leaky_features": 0, "train_rows": train_rows_n,
         "train_positive_rate": round(pos_rate, 6), "val_auc": 0.7929, "test_auc": 0.8513,
         "test_pr_auc": 0.5521, "notes": "在基线上加保序回归校准. AUC 不变, 但 Brier 与决策收益显著改善"},
        {"id": 5, "model_registry_id": 3, "run_code": "TR-M1-005",
         "started_at": MODEL_GO_LIVE + timedelta(days=45), "split_version": "v2026.05",
         "feature_count": 24, "includes_leaky_features": 0, "train_rows": train_rows_n,
         "train_positive_rate": round(pos_rate * 0.41, 6), "val_auc": 0.5688, "test_auc": 0.5688,
         "test_pr_auc": 0.1492, "notes": "上线后用全部数据重训, 含被删失的样本. 正例率被自己的行动压低了近八成, 模型显著退化"},
        {"id": 6, "model_registry_id": 4, "run_code": "TR-M1-006",
         "started_at": MODEL_GO_LIVE + timedelta(days=46), "split_version": "v2026.05",
         "feature_count": 24, "includes_leaky_features": 0, "train_rows": 71087,
         "train_positive_rate": round(pos_rate * 0.97, 6), "val_auc": 0.6562, "test_auc": 0.6562,
         "test_pr_auc": 0.0303, "notes": "重训时剔除 is_label_censored=1 的样本. 同样在 5 月下旬评估, AUC 从 0.5688 回到 0.6562"},
        {"id": 7, "model_registry_id": 5, "run_code": "TR-M2-001",
         "started_at": MODEL_GO_LIVE - timedelta(days=3), "split_version": "v2026.05",
         "feature_count": 12, "includes_leaky_features": 0, "train_rows": 612,
         "train_positive_rate": 0.0, "val_auc": 0.0, "test_auc": 0.0, "test_pr_auc": 0.0,
         "notes": "作业时长分位数回归. 直接丢弃 is_censored=1 的样本, P90 系统性偏低"},
        {"id": 8, "model_registry_id": 6, "run_code": "TR-M2-002",
         "started_at": MODEL_GO_LIVE - timedelta(days=2), "split_version": "v2026.05",
         "feature_count": 12, "includes_leaky_features": 0, "train_rows": 900,
         "train_positive_rate": 0.0, "val_auc": 0.0, "test_auc": 0.0, "test_pr_auc": 0.0,
         "notes": "改用删失感知的 AFT 模型, 把还在跑的作业作为右删失样本纳入, P90 明显上移"},
    ]

    # ---------- 11. 线上打分 ----------
    # 每个 (节点, as_of) 一条. feature_as_of_ts 记录线上真正取到的特征时点:
    # 带 60 分钟可见性滞后的那几个特征, 线上只能拿到一小时前的值.
    pred_rows = []
    prid = 1
    pred_index: dict[tuple[int, datetime], int] = {}
    for sc in scored:
        raw = sc["raw_score"]
        # 未校准 (陷阱 8): 线上分数经过一个指数小于 1 的变换, 高分段系统性高估
        shown = raw ** MISCALIBRATION_EXPONENT
        pred_rows.append({
            "id": prid, "model_registry_id": 1, "gpu_node_id": sc["node_id"],
            "as_of_ts": sc["as_of"], "scored_at": sc["as_of"] + timedelta(minutes=9),
            "feature_as_of_ts": sc["as_of"] - timedelta(minutes=SERVING_LAG_MINUTES),
            "raw_score": round(shown, 8),
            "calibrated_score": round(raw, 8),
            "scoring_latency_ms": round(random.uniform(7.0, 41.0), 2),
        })
        pred_index[(sc["node_id"], sc["as_of"])] = prid
        prid += 1

    # ---------- 12. 决策与结果 ----------
    decision_rows, outcome_rows = [], []
    dcid = 1
    ocid = 1
    for sc in scored:
        shown = sc["raw_score"] ** MISCALIBRATION_EXPONENT
        if shown < DECISION_THRESHOLD:
            continue
        node_id, asof = sc["node_id"], sc["as_of"]
        ev = sc["event"]
        drained_here = bool(ev and ev["prevented"] and ev["drained_at"]
                            and asof < ev["drained_at"] <= asof + timedelta(minutes=31))
        # 期望效用: 用校准后的概率乘中断代价, 与迁移代价比较
        avg_gpus_at_risk = 8 * random.uniform(1.0, 3.2)
        interrupt_cost = sc["raw_score"] * avg_gpus_at_risk * random.uniform(3.5, 9.0) * GPU_HOUR_COST_USD * 60
        migrate_cost = avg_gpus_at_risk * random.uniform(0.4, 1.1) * GPU_HOUR_COST_USD * 60
        arm = ev["arm"] if ev is not None else None
        if drained_here:
            executed, holdout, override = "DRAIN", 0, None
        elif arm == "HOLDOUT":
            executed, holdout, override = "NO_ACTION", 1, "EXPLORATION_HOLDOUT"
        elif arm == "OVERRIDE":
            executed, holdout, override = "NO_ACTION", 0, random.choice(
                ["CRITICAL_CUSTOMER_JOB", "NO_SPARE_CAPACITY", "OPS_DISAGREED"])
        else:
            # 健康节点的误报, 或者已经排空过的事件的后续打分
            executed, holdout, override = "MONITOR", 0, None
        decision_rows.append({
            "id": dcid, "prediction_log_id": pred_index[(node_id, asof)],
            "gpu_node_id": node_id, "as_of_ts": asof,
            "recommended_action": "DRAIN",
            "expected_benefit_usd": round(interrupt_cost, 2),
            "expected_cost_usd": round(migrate_cost, 2),
            "executed_action": executed, "is_holdout": holdout,
            "override_reason": override, "decided_at": asof + timedelta(minutes=11),
        })
        # 结果在 24 小时观测窗结束后才可得
        failed = 1 if any(asof < t <= asof + timedelta(hours=LABEL_HORIZON_HOURS)
                          for t in failures_by_node.get(node_id, [])) else 0
        # 受影响作业数用一个粗略随机代理 (0-4), 结果仅在节点真的故障时才记入
        jobs_hit = random.randint(0, 4)
        if executed == "DRAIN":
            actual_gpu_h = avg_gpus_at_risk * random.uniform(0.3, 1.0)
            counterfactual = interrupt_cost
        elif failed:
            actual_gpu_h = avg_gpus_at_risk * random.uniform(3.0, 9.0)
            counterfactual = actual_gpu_h * GPU_HOUR_COST_USD
        else:
            actual_gpu_h = 0.0
            counterfactual = 0.0
        actual_usd = actual_gpu_h * GPU_HOUR_COST_USD
        outcome_rows.append({
            "id": ocid, "decision_log_id": dcid,
            "observed_at": asof + timedelta(hours=LABEL_HORIZON_HOURS + LABEL_SETTLEMENT_LAG_HOURS),
            "node_failed_within_horizon": failed, "jobs_affected": jobs_hit if failed else 0,
            "actual_lost_gpu_hours": round(actual_gpu_h, 2),
            "actual_lost_usd": round(actual_usd, 2),
            "counterfactual_lost_usd": round(counterfactual, 2),
            # 迁移成本只在真的迁了的时候才发生. 仅监控与留出组没有动过节点,
            # 把预估迁移成本记到它们头上, 会让整个收益核算凭空多出几十万美元的支出.
            "net_benefit_usd": round(
                counterfactual - actual_usd - (migrate_cost if executed == "DRAIN" else 0.0), 2),
        })
        dcid += 1
        ocid += 1

    # ---------- 13. 评估与校准 ----------
    # 指标由数据本身算出来, 不是编的. 切片维度让分布漂移能被直接看见.
    lot_by_node = {nm["id"]: nm["lot"]["lot_code"] for nm in node_meta}
    eval_rows, calib_rows = [], []
    evid = 1
    cbid = 1
    eval_windows = [
        (datetime(2026, 4, 1), datetime(2026, 4, 16)),
        (datetime(2026, 4, 16), datetime(2026, 5, 1)),
        (datetime(2026, 5, 1), datetime(2026, 5, 16)),
        (datetime(2026, 5, 16), datetime(2026, 6, 1)),
    ]
    for ws, we in eval_windows:
        window_pairs = []
        by_lot: dict[str, list[tuple[float, int]]] = {}
        for sc in scored:
            if not (ws <= sc["as_of"] < we):
                continue
            key = (sc["node_id"], sc["as_of"])
            lab = label_by_key.get(key)
            if lab is None:
                continue
            shown = sc["raw_score"] ** MISCALIBRATION_EXPONENT
            window_pairs.append((shown, lab["label_value"]))
            by_lot.setdefault(lot_by_node[sc["node_id"]], []).append((shown, lab["label_value"]))
        for dim, val, pairs in ([("overall", "ALL", window_pairs)]
                                + [("purchase_lot", k, v) for k, v in sorted(by_lot.items())]):
            if not pairs:
                continue
            a = auc_score(pairs)
            tp = sum(1 for s, y in pairs if s >= DECISION_THRESHOLD and y == 1)
            fp = sum(1 for s, y in pairs if s >= DECISION_THRESHOLD and y == 0)
            fn = sum(1 for s, y in pairs if s < DECISION_THRESHOLD and y == 1)
            brier = sum((s - y) ** 2 for s, y in pairs) / len(pairs)
            eval_rows.append({
                "id": evid, "model_registry_id": 1,
                "eval_window_start": ws, "eval_window_end": we,
                "slice_dimension": dim, "slice_value": val,
                "sample_count": len(pairs), "positive_count": sum(y for _s, y in pairs),
                "auc": round(a, 4) if a is not None else None,
                "precision_at_threshold": round(tp / (tp + fp), 4) if (tp + fp) else None,
                "recall_at_threshold": round(tp / (tp + fn), 4) if (tp + fn) else None,
                "brier_score": round(brier, 6),
            })
            evid += 1
        # 可靠性曲线: 预测概率与真实频率的偏离在这里一目了然
        for b in range(10):
            lo, hi = b / 10.0, (b + 1) / 10.0
            binned = [(s, y) for s, y in window_pairs if lo <= s < hi]
            if not binned:
                continue
            calib_rows.append({
                "id": cbid, "model_registry_id": 1, "eval_window_start": ws,
                "bin_lower": lo, "bin_upper": hi, "sample_count": len(binned),
                "mean_predicted": round(sum(s for s, _y in binned) / len(binned), 6),
                "observed_rate": round(sum(y for _s, y in binned) / len(binned), 6),
            })
            cbid += 1

    return {
        "01_gpu_node": to_df(node_rows),
        "02_gpu_device": to_df(device_rows),
        "03_firmware_rollout": to_df(firmware_rows),
        "04_node_telemetry": to_df(telemetry_rows),
        "05_hardware_event": to_df(hw_rows),
        "06_node_state_transition": to_df(state_rows),
        "07_maintenance_work_order": to_df(wo_rows),
        "08_training_job": to_df(job_rows),
        "09_job_attempt": to_df(attempt_rows),
        "10_job_placement": to_df(placement_rows),
        "11_job_checkpoint": to_df(ckpt_rows),
        "12_job_step_metric": to_df(step_rows),
        "13_job_interruption": to_df(interrupt_rows),
        "14_queue_submission": to_df(queue_rows),
        "15_feature_definition": to_df(feature_def_rows),
        "16_feature_snapshot": to_df(feature_rows),
        "17_label_definition": to_df(label_def_rows),
        "18_label_record": to_df(label_rows),
        "19_dataset_split": to_df(split_rows),
        "20_model_registry": to_df(model_rows),
        "21_training_run": to_df(training_rows),
        "22_prediction_log": to_df(pred_rows),
        "23_evaluation_metric": to_df(eval_rows),
        "24_calibration_bin": to_df(calib_rows),
        "25_decision_log": to_df(decision_rows),
        "26_action_outcome": to_df(outcome_rows),
    }


# ============================================================
# 第 8 节: TSV 输出
# ============================================================
def generate_all_tsv() -> None:
    """构建整个世界并按拓扑顺序写出 26 个 TSV 文件. 每次运行先清空旧文件."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    tables = build_world()
    for name, df in tables.items():
        df.write_csv(DATA_DIR / f"{name}.tsv", separator="\t")
        print(f"  {name}.tsv  {df.height:>9,} rows")

    print(f"Generated all TSV files in {DATA_DIR}")


# ============================================================
# 第 9 节: SQLite 构建
# ============================================================
def create_sqlite_database() -> None:
    """用 Core API 批量装载器把 TSV 灌进 SQLite. 一个事务, 一个循环."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order = [
        ("01_gpu_node", GpuNode.__table__),
        ("02_gpu_device", GpuDevice.__table__),
        ("03_firmware_rollout", FirmwareRollout.__table__),
        ("04_node_telemetry", NodeTelemetry.__table__),
        ("05_hardware_event", HardwareEvent.__table__),
        ("06_node_state_transition", NodeStateTransition.__table__),
        ("07_maintenance_work_order", MaintenanceWorkOrder.__table__),
        ("08_training_job", TrainingJob.__table__),
        ("09_job_attempt", JobAttempt.__table__),
        ("10_job_placement", JobPlacement.__table__),
        ("11_job_checkpoint", JobCheckpoint.__table__),
        ("12_job_step_metric", JobStepMetric.__table__),
        ("13_job_interruption", JobInterruption.__table__),
        ("14_queue_submission", QueueSubmission.__table__),
        ("15_feature_definition", FeatureDefinition.__table__),
        ("16_feature_snapshot", FeatureSnapshot.__table__),
        ("17_label_definition", LabelDefinition.__table__),
        ("18_label_record", LabelRecord.__table__),
        ("19_dataset_split", DatasetSplit.__table__),
        ("20_model_registry", ModelRegistry.__table__),
        ("21_training_run", TrainingRun.__table__),
        ("22_prediction_log", PredictionLog.__table__),
        ("23_evaluation_metric", EvaluationMetric.__table__),
        ("24_calibration_bin", CalibrationBin.__table__),
        ("25_decision_log", DecisionLog.__table__),
        ("26_action_outcome", ActionOutcome.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv",
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=20000,
            )
            rows = df.to_dicts()
            if rows:
                conn.execute(table.insert(), rows)

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("Starting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("All done!")


if __name__ == "__main__":
    main()

