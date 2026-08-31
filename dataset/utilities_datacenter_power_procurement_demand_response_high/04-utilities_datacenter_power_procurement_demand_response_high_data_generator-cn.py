"""
公用事业 - AI 数据中心电力采购与需求响应 假数据生成器
复杂度: High

业务背景:
Kestrel Compute, Inc. 是一家总部位于俄亥俄州 Columbus 的虚构 AI 算力运营商, 自建自营
6 座 AI 训练与推理园区, 横跨 ERCOT, PJM, MISO 三个电力市场, 合计签约电力容量 420 MW,
部署约 180,000 张 GPU. 电费是仅次于 GPU 折旧的第二大成本项, FY2026 约 2.05 亿美元.
本数据集覆盖 FY2026 (2025-07-01 至 2026-06-30) 完整 12 个月的 15 分钟级节点电价,
15 分钟级园区计量, 电费账单, 需求响应事件与结算, 以及被削减的 GPU 任务明细,
支持以下分析:

1. 需求响应净收益倒挂: dr_event_participation 的结算收入全年为正 (约 $3.28M), 但把
   curtailed_workload 里被中断 GPU 任务的机会成本 join 进来之后, Abilene 园区整体净
   收益为负. 只看能源侧报表永远看不见这个洞.
2. DR 基线灌水: 一批参与记录在事件前 3 天负载被人为拉高, 使按"过去 10 个工作日同时段
   均值"计算的 baseline_mw 虚高, delivered_reduction_mw 被系统性高估.
3. PPA 形状风险 (shape risk): Longhorn Ridge 风电 PPA 按月度平均价对比市场价看着省钱,
   但风电大发时 ERCOT West 节点电价恰好最低, 按小时出力加权重算后实际是亏钱的.
4. 需量电费被平均电价掩盖: energy_invoice.blended_rate_usd_per_kwh 是一个混合单价,
   看不出 DEMAND 分项的占比, 也看不出计费需量是被某一个 15 分钟区间单独决定的.
   Columbus 园区 2025 年 8 月的月度峰值来自一次 30 分钟的 burn-in 测试, 并因为需量
   棘轮 (ratchet) 条款拖累了之后 8 个月的账单.
5. 4CP 躲避失手: ERCOT 用夏季 4 个月各自的系统峰值小时用电量决定下一年的输电费.
   2025 年 4CP 季 4 次预测里错了 1 次 (8 月预测偏离约 1 小时), 那一小时园区满载,
   把 4CP 平均值整体抬高, 代价体现在下一年的输电费率上.

上述陷阱通过有意设计的相关分布注入, 而非独立随机数. 对应的 SQL 查询位于
03-utilities_datacenter_power_procurement_demand_response_high_sql_queries-cn.md,
用以暴露这些陷阱.
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
from sqlalchemy import Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = (
    OUTPUT_DIR / "utilities_datacenter_power_procurement_demand_response_high.sqlite"
)
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# Kestrel 的财年是 7 月到次年 6 月, 所以 2026-06-30 同时是 FY2026 的最后一天,
# 整个数据集就是一个完整财年. SQL 查询里凡是需要"今天"的地方也用同一个字面量日期.
REFERENCE_DATE = date(2026, 6, 30)

# 计量与电价的时间窗口: FY2026 完整 365 天, 15 分钟粒度 = 35,040 个区间.
WINDOW_START = datetime(2025, 7, 1, 0, 0, 0)
WINDOW_END = datetime(2026, 6, 30, 23, 45, 0)
INTERVAL_MINUTES = 15
INTERVALS_PER_DAY = 24 * 60 // INTERVAL_MINUTES  # 96
WINDOW_DAYS = 365
TOTAL_INTERVALS = WINDOW_DAYS * INTERVALS_PER_DAY  # 35,040

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================
# 第 4 节: 业务校准常量 (Business Calibration Constants)
# ============================================================

# --- ISO 市场 ---
# 三个市场的实时市场出清间隔是真实行业惯例: ERCOT 实时市场 15 分钟结算 (SCED 每 5 分钟
# 出清但按 15 分钟结算), PJM 与 MISO 实时市场 5 分钟出清. 本数据集把三个市场统一
# 归一化到 15 分钟区间存储, 所以 settlement_interval_minutes 记录的是各自的真实惯例,
# 而不是本数据集的存储粒度.
ISO_MARKETS = [
    {
        "code": "ERCOT",
        "name": "Electric Reliability Council of Texas",
        "settlement_interval_minutes": 15,
        "transmission_cost_method": "4CP",
        "has_capacity_market": 0,
        "region_description": "Texas-only grid with no capacity market; relies on scarcity pricing to attract generation, giving it the most volatile real-time prices in North America",
    },
    {
        "code": "PJM",
        "name": "PJM Interconnection",
        "settlement_interval_minutes": 5,
        "transmission_cost_method": "PLC",
        "has_capacity_market": 1,
        "region_description": "Covers 13 states plus DC; runs a capacity market (RPM) and allocates transmission and capacity charges by Peak Load Contribution",
    },
    {
        "code": "MISO",
        "name": "Midcontinent Independent System Operator",
        "settlement_interval_minutes": 5,
        "transmission_cost_method": "PEAK_DEMAND",
        "has_capacity_market": 1,
        "region_description": "Covers 15 midwestern states; high wind penetration makes overnight negative prices routine",
    },
]

# --- 6 座园区 ---
# 容量合计 420 MW, GPU 合计 180,000 张. workload_type 决定负载曲线形状, 也决定了
# 被 DR 削减时的机会成本: TRAINING 园区跑长周期预训练, checkpoint 间隔长, 一旦中断
# 回滚损失大; INFERENCE 园区可以秒级摘流量, 几乎无损失. 这是陷阱 1 的物理基础.
SITES = [
    {
        "site_code": "CMH1",
        "site_name": "Columbus Campus",
        "city": "Columbus",
        "state_province": "OH",
        "iso_code": "PJM",
        "contracted_capacity_mw": 95.0,
        "gpu_count": 40000,
        "primary_workload_type": "INFERENCE",
        "cooling_type": "AIR_COOLED",
        "commissioned_date": date(2021, 4, 1),
        # 气候参数: 年均干球温度 (F), 年振幅, 用于生成天气进而驱动冷却负载
        "temp_mean_f": 53.0,
        "temp_amplitude_f": 24.0,
    },
    {
        "site_code": "ALB1",
        "site_name": "New Albany East",
        "city": "New Albany",
        "state_province": "OH",
        "iso_code": "PJM",
        "contracted_capacity_mw": 60.0,
        "gpu_count": 26000,
        "primary_workload_type": "MIXED",
        "cooling_type": "LIQUID_COOLED",
        # 本园区在数据窗口中途投产, 前两个半月没有负载. 任何按 12 个月平均的口径
        # 都会低估 ALB1 的真实水平, 这是一个刻意留下的口径边界.
        "commissioned_date": date(2025, 9, 15),
        "temp_mean_f": 53.0,
        "temp_amplitude_f": 24.0,
    },
    {
        "site_code": "ABI1",
        "site_name": "Abilene Campus",
        "city": "Abilene",
        "state_province": "TX",
        "iso_code": "ERCOT",
        "contracted_capacity_mw": 110.0,
        "gpu_count": 48000,
        "primary_workload_type": "TRAINING",
        "cooling_type": "LIQUID_COOLED",
        "commissioned_date": date(2023, 8, 1),
        "temp_mean_f": 65.0,
        "temp_amplitude_f": 22.0,
    },
    {
        "site_code": "TPL1",
        "site_name": "Temple Campus",
        "city": "Temple",
        "state_province": "TX",
        "iso_code": "ERCOT",
        "contracted_capacity_mw": 75.0,
        "gpu_count": 32000,
        "primary_workload_type": "MIXED",
        "cooling_type": "AIR_COOLED",
        "commissioned_date": date(2024, 2, 1),
        "temp_mean_f": 68.0,
        "temp_amplitude_f": 20.0,
    },
    {
        "site_code": "CID1",
        "site_name": "Cedar Rapids Campus",
        "city": "Cedar Rapids",
        "state_province": "IA",
        "iso_code": "MISO",
        "contracted_capacity_mw": 50.0,
        "gpu_count": 22000,
        "primary_workload_type": "TRAINING",
        "cooling_type": "LIQUID_COOLED",
        "commissioned_date": date(2024, 6, 1),
        "temp_mean_f": 49.0,
        "temp_amplitude_f": 26.0,
    },
    {
        "site_code": "FAR1",
        "site_name": "Fargo Campus",
        "city": "Fargo",
        "state_province": "ND",
        "iso_code": "MISO",
        "contracted_capacity_mw": 30.0,
        "gpu_count": 12000,
        "primary_workload_type": "MIXED",
        "cooling_type": "AIR_COOLED",
        "commissioned_date": date(2022, 10, 1),
        "temp_mean_f": 42.0,
        "temp_amplitude_f": 30.0,
    },
]

# --- 负载曲线形状 ---
# IT 负载占签约容量的比例. TRAINING 负载极其平坦 (跑满就一直跑), INFERENCE 有明显
# 日内波峰波谷 (白天用户多), MIXED 居中. 这是数据中心行业的真实特征, 也是 ERCOT
# 那两个园区能拿出削减量参与 DR 的原因.
# IT 负载的额定值只占签约容量的一部分, 剩下的留给冷却, 配电损耗与冗余.
# 液冷把更多的签约容量让给了 GPU 本身, 这正是液冷改造最主要的经济收益.
# 这两个比例配合下面的硬上限, 保证 metered_demand_mw 不会超过 contracted_capacity_mw.
IT_CAPACITY_SHARE_BY_COOLING = {"AIR_COOLED": 0.72, "LIQUID_COOLED": 0.84}

# 园区总负载的硬上限, 相对签约容量. 超过就会触发配电侧保护, 运维上用功率封顶
# (power capping) 把 GPU 降频压回来, 所以真实计量数据里不会出现越界值.
MAX_LOAD_SHARE_OF_CAPACITY = 0.97

# 下面的 base 与 diurnal_amplitude 是相对 IT 额定值 (容量 x IT_CAPACITY_SHARE) 的比例.
LOAD_SHAPE_BY_WORKLOAD = {
    "TRAINING": {"base": 0.94, "diurnal_amplitude": 0.02, "noise_sd": 0.008},
    "MIXED": {"base": 0.80, "diurnal_amplitude": 0.09, "noise_sd": 0.020},
    "INFERENCE": {"base": 0.66, "diurnal_amplitude": 0.15, "noise_sd": 0.030},
}

# 冷却负载相对 IT 负载的比例. 基础开销来自恒定的风机与泵, 温度敏感项在湿球温度
# 超过 55F 之后线性上升. 液冷园区的温度敏感度只有风冷的一半左右, 这是液冷改造
# 最主要的卖点.
COOLING_BASE_RATIO = {"AIR_COOLED": 0.115, "LIQUID_COOLED": 0.062}
COOLING_TEMP_SENSITIVITY = {"AIR_COOLED": 0.0068, "LIQUID_COOLED": 0.0031}
COOLING_WETBULB_THRESHOLD_F = 55.0

# --- 电价节点 ---
# base_lmp 是各节点的年均基准价 (USD/MWh), 大致对应真实市场水平: ERCOT 西部因为
# 风电富集常年最便宜, PJM AEP Ohio 区域因为负荷重且输电受限最贵.
# wind_suppression 是"风电出力每高出常态 1 个单位, 节点电价下压多少 USD/MWh",
# ERCOT West 最强. 陷阱 3 (PPA 形状风险) 完全由这个系数驱动.
PRICING_NODES = [
    {
        "node_code": "HB_WEST_ABI",
        "node_name": "ERCOT West Hub - Abilene Load Zone",
        "site_code": "ABI1",
        "zone_name": "LZ_WEST",
        "base_lmp": 32.0,
        "diurnal_amplitude": 9.0,
        "volatility": 11.0,
        "wind_suppression": 165.0,
        "spike_probability": 0.0022,
    },
    {
        "node_code": "HB_NORTH_TPL",
        "node_name": "ERCOT North Hub - Temple Load Zone",
        "site_code": "TPL1",
        "zone_name": "LZ_NORTH",
        "base_lmp": 36.0,
        "diurnal_amplitude": 11.0,
        "volatility": 12.0,
        "wind_suppression": 40.0,
        "spike_probability": 0.0020,
    },
    {
        "node_code": "AEP_OHIO_CMH",
        "node_name": "PJM AEP Ohio - Columbus Bus",
        "site_code": "CMH1",
        "zone_name": "AEP",
        "base_lmp": 41.5,
        "diurnal_amplitude": 12.0,
        "volatility": 7.5,
        "wind_suppression": 4.0,
        "spike_probability": 0.0006,
    },
    {
        "node_code": "AEP_OHIO_ALB",
        "node_name": "PJM AEP Ohio - New Albany Bus",
        "site_code": "ALB1",
        "zone_name": "AEP",
        "base_lmp": 42.8,
        "diurnal_amplitude": 12.0,
        "volatility": 7.5,
        "wind_suppression": 4.0,
        "spike_probability": 0.0006,
    },
    {
        "node_code": "MISO_CENTRAL_CID",
        "node_name": "MISO Central - Cedar Rapids Bus",
        "site_code": "CID1",
        "zone_name": "MISO_Z3",
        "base_lmp": 33.5,
        "diurnal_amplitude": 8.5,
        "volatility": 8.0,
        "wind_suppression": 55.0,
        "spike_probability": 0.0008,
    },
    {
        "node_code": "MISO_NORTH_FAR",
        "node_name": "MISO North - Fargo Bus",
        "site_code": "FAR1",
        "zone_name": "MISO_Z1",
        "base_lmp": 29.0,
        "diurnal_amplitude": 7.0,
        "volatility": 8.5,
        "wind_suppression": 60.0,
        "spike_probability": 0.0009,
    },
]

# 稀缺定价区间的价格区间. ERCOT 没有容量市场, 全靠这种尖峰给发电商回本,
# 真实历史上单个 15 分钟区间摸到过 $5,000/MWh 的系统上限.
SCARCITY_PRICE_RANGE = (620.0, 4800.0)
SCARCITY_FLAG_THRESHOLD = 500.0

# --- 费率表 ---
# demand_charge_usd_per_kw_month 是陷阱 4 的核心. ERCOT 的工业大用户输电费走 4CP,
# 所以没有常规需量电费 (记为 0); PJM 与 MISO 有配电需量电费, PJM 最高.
# demand_ratchet_pct 是需量棘轮: 当月计费需量不得低于过去 11 个月最高需量的这个比例.
# 这条条款让一次 30 分钟的峰值把成本拖了整整一年, 是陷阱 4 真正的杀伤力所在.
TARIFF_SCHEDULES = [
    {
        "tariff_code": "AEP-OH-GS4",
        "utility_name": "AEP Ohio",
        "iso_code": "PJM",
        "site_code": "CMH1",
        "energy_charge_usd_per_kwh": 0.0,
        "demand_charge_usd_per_kw_month": 18.20,
        "transmission_charge_usd_per_kw_month": 6.40,
        "rider_charge_usd_per_kwh": 0.00412,
        "demand_ratchet_pct": 85.0,
        "billing_demand_basis": "MAX_15MIN_INTERVAL",
    },
    {
        "tariff_code": "AEP-OH-GS4-NA",
        "utility_name": "AEP Ohio",
        "iso_code": "PJM",
        "site_code": "ALB1",
        "energy_charge_usd_per_kwh": 0.0,
        "demand_charge_usd_per_kw_month": 17.85,
        "transmission_charge_usd_per_kw_month": 6.40,
        "rider_charge_usd_per_kwh": 0.00412,
        "demand_ratchet_pct": 85.0,
        "billing_demand_basis": "MAX_15MIN_INTERVAL",
    },
    {
        "tariff_code": "ONCOR-TX-IND",
        "utility_name": "Oncor Electric Delivery",
        "iso_code": "ERCOT",
        "site_code": "ABI1",
        "energy_charge_usd_per_kwh": 0.0,
        "demand_charge_usd_per_kw_month": 0.0,
        "transmission_charge_usd_per_kw_month": 0.0,
        "rider_charge_usd_per_kwh": 0.00298,
        "demand_ratchet_pct": 0.0,
        "billing_demand_basis": "4CP_AVERAGE",
    },
    {
        "tariff_code": "ONCOR-TX-IND-TPL",
        "utility_name": "Oncor Electric Delivery",
        "iso_code": "ERCOT",
        "site_code": "TPL1",
        "energy_charge_usd_per_kwh": 0.0,
        "demand_charge_usd_per_kw_month": 0.0,
        "transmission_charge_usd_per_kw_month": 0.0,
        "rider_charge_usd_per_kwh": 0.00298,
        "demand_ratchet_pct": 0.0,
        "billing_demand_basis": "4CP_AVERAGE",
    },
    {
        "tariff_code": "ALLIANT-IA-LGS",
        "utility_name": "Alliant Energy Iowa",
        "iso_code": "MISO",
        "site_code": "CID1",
        "energy_charge_usd_per_kwh": 0.0,
        "demand_charge_usd_per_kw_month": 12.90,
        "transmission_charge_usd_per_kw_month": 4.15,
        "rider_charge_usd_per_kwh": 0.00355,
        "demand_ratchet_pct": 75.0,
        "billing_demand_basis": "MAX_15MIN_INTERVAL",
    },
    {
        "tariff_code": "XCEL-ND-LGS",
        "utility_name": "Xcel Energy North Dakota",
        "iso_code": "MISO",
        "site_code": "FAR1",
        "energy_charge_usd_per_kwh": 0.0,
        "demand_charge_usd_per_kw_month": 11.45,
        "transmission_charge_usd_per_kw_month": 3.80,
        "rider_charge_usd_per_kwh": 0.00340,
        "demand_ratchet_pct": 75.0,
        "billing_demand_basis": "MAX_15MIN_INTERVAL",
    },
]

# ERCOT 4CP 输电费率 (USD/kW-year). 这个数字乘以 4CP 平均需量就是下一年的输电费,
# 是陷阱 5 的换算系数. 真实的 Oncor 工业费率在 $50 到 $75/kW-year 区间.
ERCOT_4CP_RATE_USD_PER_KW_YEAR = 58.0

# --- 供应合约 ---
# 三份可变出力 PPA (风光) 会生成逐小时出力曲线; 其余是固定价零售合约或批发指数敞口.
# Longhorn Ridge 是陷阱 3 的主角: strike $28.50 看着比 ERCOT West 年均价便宜,
# 但它的出力集中在电价最低的时段.
SUPPLY_CONTRACTS = [
    {
        "contract_code": "PPA-LHR-WIND-01",
        "contract_type": "WIND_PPA",
        "site_code": "ABI1",
        "counterparty_name": "Longhorn Ridge Wind Holdings LLC",
        "start_date": date(2024, 1, 1),
        "end_date": date(2035, 12, 31),
        "contracted_volume_mw": 150.0,
        "strike_price_usd_per_mwh": 28.50,
        "settlement_method": "AS_GENERATED",
        "is_variable_generation": True,
        "annual_capacity_factor": 0.305,
    },
    {
        "contract_code": "PPA-BLK-SOLAR-01",
        "contract_type": "SOLAR_PPA",
        "site_code": "TPL1",
        "counterparty_name": "Blackland Solar Partners LP",
        "start_date": date(2024, 7, 1),
        "end_date": date(2039, 6, 30),
        "contracted_volume_mw": 60.0,
        "strike_price_usd_per_mwh": 31.75,
        "settlement_method": "AS_GENERATED",
        "is_variable_generation": True,
        "annual_capacity_factor": 0.268,
    },
    {
        "contract_code": "PPA-BUC-SOLAR-01",
        "contract_type": "SOLAR_PPA",
        "site_code": "CMH1",
        "counterparty_name": "Buckeye Ridge Solar LLC",
        "start_date": date(2025, 1, 1),
        "end_date": date(2039, 12, 31),
        "contracted_volume_mw": 40.0,
        "strike_price_usd_per_mwh": 38.90,
        "settlement_method": "AS_GENERATED",
        "is_variable_generation": True,
        "annual_capacity_factor": 0.212,
    },
    {
        "contract_code": "RTL-AEP-CMH-26",
        "contract_type": "RETAIL_FIXED",
        "site_code": "CMH1",
        "counterparty_name": "Constellation Retail Supply",
        "start_date": date(2025, 1, 1),
        "end_date": date(2027, 12, 31),
        "contracted_volume_mw": 60.0,
        "strike_price_usd_per_mwh": 62.40,
        "settlement_method": "FIXED_BLOCK",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "RTL-AEP-ALB-26",
        "contract_type": "RETAIL_FIXED",
        "site_code": "ALB1",
        "counterparty_name": "Constellation Retail Supply",
        "start_date": date(2025, 9, 1),
        "end_date": date(2028, 8, 31),
        "contracted_volume_mw": 45.0,
        "strike_price_usd_per_mwh": 64.80,
        "settlement_method": "FIXED_BLOCK",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "RTL-ALT-CID-26",
        "contract_type": "RETAIL_FIXED",
        "site_code": "CID1",
        "counterparty_name": "WPS Energy Services",
        "start_date": date(2024, 6, 1),
        "end_date": date(2027, 5, 31),
        "contracted_volume_mw": 35.0,
        "strike_price_usd_per_mwh": 47.20,
        "settlement_method": "FIXED_BLOCK",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "RTL-XCL-FAR-26",
        "contract_type": "RETAIL_FIXED",
        "site_code": "FAR1",
        "counterparty_name": "WPS Energy Services",
        "start_date": date(2024, 10, 1),
        "end_date": date(2027, 9, 30),
        "contracted_volume_mw": 22.0,
        "strike_price_usd_per_mwh": 44.10,
        "settlement_method": "FIXED_BLOCK",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "IDX-ERCOT-ABI",
        "contract_type": "WHOLESALE_INDEX",
        "site_code": "ABI1",
        "counterparty_name": "Kestrel Compute Wholesale Desk",
        "start_date": date(2023, 8, 1),
        "end_date": date(2027, 7, 31),
        "contracted_volume_mw": 0.0,
        "strike_price_usd_per_mwh": 0.0,
        "settlement_method": "INDEX_PASSTHROUGH",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "IDX-ERCOT-TPL",
        "contract_type": "WHOLESALE_INDEX",
        "site_code": "TPL1",
        "counterparty_name": "Kestrel Compute Wholesale Desk",
        "start_date": date(2024, 2, 1),
        "end_date": date(2027, 7, 31),
        "contracted_volume_mw": 0.0,
        "strike_price_usd_per_mwh": 0.0,
        "settlement_method": "INDEX_PASSTHROUGH",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "IDX-MISO-CID",
        "contract_type": "WHOLESALE_INDEX",
        "site_code": "CID1",
        "counterparty_name": "Kestrel Compute Wholesale Desk",
        "start_date": date(2024, 6, 1),
        "end_date": date(2027, 5, 31),
        "contracted_volume_mw": 0.0,
        "strike_price_usd_per_mwh": 0.0,
        "settlement_method": "INDEX_PASSTHROUGH",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
    {
        "contract_code": "IDX-MISO-FAR",
        "contract_type": "WHOLESALE_INDEX",
        "site_code": "FAR1",
        "counterparty_name": "Kestrel Compute Wholesale Desk",
        "start_date": date(2024, 10, 1),
        "end_date": date(2027, 9, 30),
        "contracted_volume_mw": 0.0,
        "strike_price_usd_per_mwh": 0.0,
        "settlement_method": "INDEX_PASSTHROUGH",
        "is_variable_generation": False,
        "annual_capacity_factor": None,
    },
]

# --- 需求响应项目 ---
# baseline_method 是陷阱 2 的入口. AVG_10_BUSINESS_DAYS 是北美 DR 项目最常见的基线
# 算法 (取事件前 10 个工作日同时段的平均负载), 它的已知弱点就是可以靠事件前拉高负载
# 来抬基线. FIRM_SERVICE_LEVEL 用固定的约定负载水平做基线, 不受这种操纵影响.
DR_PROGRAMS = [
    {
        "program_code": "ERCOT-ERS-10",
        "program_name": "ERCOT Emergency Response Service (10-minute)",
        "iso_code": "ERCOT",
        "program_type": "EMERGENCY",
        "baseline_method": "AVG_10_BUSINESS_DAYS",
        "capacity_payment_usd_per_mw_month": 5600.0,
        "energy_payment_usd_per_mwh": 0.0,
        "max_events_per_year": 20,
        "max_event_duration_hours": 4,
        "notification_lead_time_minutes": 10,
        "penalty_usd_per_mw_shortfall": 2800.0,
    },
    {
        "program_code": "ERCOT-CLR-RRS",
        "program_name": "ERCOT Controllable Load Resource - Responsive Reserve",
        "iso_code": "ERCOT",
        "program_type": "ECONOMIC",
        "baseline_method": "METER_BEFORE_AFTER",
        "capacity_payment_usd_per_mw_month": 4000.0,
        "energy_payment_usd_per_mwh": 42.0,
        "max_events_per_year": 30,
        "max_event_duration_hours": 2,
        "notification_lead_time_minutes": 0,
        "penalty_usd_per_mw_shortfall": 4500.0,
    },
    {
        "program_code": "ERCOT-4CP-AVOID",
        "program_name": "ERCOT Four Coincident Peak Avoidance Program",
        "iso_code": "ERCOT",
        "program_type": "TRANSMISSION_AVOIDANCE",
        "baseline_method": "FIRM_SERVICE_LEVEL",
        "capacity_payment_usd_per_mw_month": 0.0,
        "energy_payment_usd_per_mwh": 0.0,
        "max_events_per_year": 12,
        "max_event_duration_hours": 3,
        "notification_lead_time_minutes": 240,
        "penalty_usd_per_mw_shortfall": 0.0,
    },
    {
        "program_code": "PJM-ELRP",
        "program_name": "PJM Emergency Load Response Program",
        "iso_code": "PJM",
        "program_type": "EMERGENCY",
        "baseline_method": "AVG_10_BUSINESS_DAYS",
        "capacity_payment_usd_per_mw_month": 3850.0,
        "energy_payment_usd_per_mwh": 68.0,
        "max_events_per_year": 15,
        "max_event_duration_hours": 6,
        "notification_lead_time_minutes": 120,
        "penalty_usd_per_mw_shortfall": 3200.0,
    },
    {
        "program_code": "PJM-CP",
        "program_name": "PJM Capacity Performance Demand Resource",
        "iso_code": "PJM",
        "program_type": "CAPACITY",
        "baseline_method": "FIRM_SERVICE_LEVEL",
        "capacity_payment_usd_per_mw_month": 5600.0,
        "energy_payment_usd_per_mwh": 0.0,
        "max_events_per_year": 10,
        "max_event_duration_hours": 6,
        "notification_lead_time_minutes": 60,
        "penalty_usd_per_mw_shortfall": 9400.0,
    },
    {
        "program_code": "MISO-LMR",
        "program_name": "MISO Load Modifying Resource",
        "iso_code": "MISO",
        "program_type": "CAPACITY",
        "baseline_method": "METER_BEFORE_AFTER",
        "capacity_payment_usd_per_mw_month": 5400.0,
        "energy_payment_usd_per_mwh": 55.0,
        "max_events_per_year": 18,
        "max_event_duration_hours": 4,
        "notification_lead_time_minutes": 30,
        "penalty_usd_per_mw_shortfall": 2100.0,
    },
]

# 每个 (项目, 园区) 的注册承诺削减容量 (MW). TRAINING 园区能腾出的削减量最大,
# 因为可以整片停掉训练任务; INFERENCE 园区必须保证在线服务, 承诺量小.
# 承诺量普遍只占园区容量的 8% 到 12%. AI 数据中心不敢像传统工业负荷那样承诺深度削减,
# 因为算力的机会成本远高于电费. 唯一的例外是 4CP 躲避: 它一年只做几个小时, 但削得很狠,
# 因为躲过一次就能省下整整一年输电费的四分之一.
DR_ENROLLMENTS = [
    ("ERCOT-ERS-10", "ABI1", 12.0),
    ("ERCOT-ERS-10", "TPL1", 5.0),
    ("ERCOT-CLR-RRS", "ABI1", 9.0),
    ("ERCOT-CLR-RRS", "TPL1", 3.5),
    ("ERCOT-4CP-AVOID", "ABI1", 62.0),
    ("ERCOT-4CP-AVOID", "TPL1", 38.0),
    ("PJM-ELRP", "CMH1", 9.0),
    ("PJM-ELRP", "ALB1", 6.0),
    ("PJM-CP", "CMH1", 6.0),
    ("PJM-CP", "ALB1", 5.0),
    ("MISO-LMR", "CID1", 4.5),
    ("MISO-LMR", "FAR1", 3.0),
    ("ERCOT-ERS-10", "CID1", 0.0),  # 占位注册, 已于 FY2026 中途退出, is_active = 0
]

# 每个项目在 FY2026 内触发的事件次数. ERCOT 夏季最密集是真实特征
# (2023 与 2024 年 ERCOT 都在 8 月连续发布保守运行通知).
DR_EVENT_COUNTS = {
    "ERCOT-ERS-10": 14,
    "ERCOT-CLR-RRS": 9,
    "ERCOT-4CP-AVOID": 5,
    "PJM-ELRP": 11,
    "PJM-CP": 6,
    "MISO-LMR": 13,
}

# --- 陷阱 1: 需求响应净收益倒挂 ---
# GPU 算力的内部机会成本 (USD/GPU-hour), 按任务类型区分. 这个数字是"这一小时的 GPU
# 如果没被中断, 本来能确认的收入", 由商务团队按合约档位给出.
# RESERVED 长约客户单价最高, 因为中断还要额外赔 SLA credit.
GPU_OPPORTUNITY_COST_USD_PER_HOUR = {
    "PRETRAINING": 3.15,
    "FINETUNING": 2.70,
    "INFERENCE_BATCH": 1.85,
    "INFERENCE_SERVING": 2.40,
    "RESEARCH": 1.20,
}

# checkpoint 间隔 (分钟). 预训练任务的 checkpoint 很贵 (要把上百 GB 的优化器状态
# 写到存储), 所以间隔拉得很长; 一旦中断, 平均要回滚半个间隔的计算量.
# 这是 Abilene 园区 DR 机会成本远高于其他园区的直接原因.
CHECKPOINT_INTERVAL_MINUTES = {
    "PRETRAINING": 300,
    "FINETUNING": 90,
    "INFERENCE_BATCH": 20,
    "INFERENCE_SERVING": 0,
    "RESEARCH": 120,
}

# 各园区的任务类型混合. ABI1 几乎全是长周期预训练, CMH1 几乎全是在线推理.
# 这个混合直接决定了陷阱 1 的方向: 同样削减 1 MW, ABI1 的代价是 CMH1 的数倍.
JOB_TYPE_MIX_BY_SITE = {
    "ABI1": {"PRETRAINING": 0.72, "FINETUNING": 0.16, "RESEARCH": 0.08, "INFERENCE_BATCH": 0.04},
    "CID1": {"PRETRAINING": 0.58, "FINETUNING": 0.24, "RESEARCH": 0.12, "INFERENCE_BATCH": 0.06},
    "TPL1": {"PRETRAINING": 0.26, "FINETUNING": 0.30, "INFERENCE_BATCH": 0.24, "INFERENCE_SERVING": 0.14, "RESEARCH": 0.06},
    "ALB1": {"PRETRAINING": 0.18, "FINETUNING": 0.26, "INFERENCE_BATCH": 0.28, "INFERENCE_SERVING": 0.22, "RESEARCH": 0.06},
    "FAR1": {"PRETRAINING": 0.20, "FINETUNING": 0.28, "INFERENCE_BATCH": 0.30, "INFERENCE_SERVING": 0.16, "RESEARCH": 0.06},
    "CMH1": {"INFERENCE_SERVING": 0.62, "INFERENCE_BATCH": 0.24, "FINETUNING": 0.10, "RESEARCH": 0.04},
}

# 客户合约档位分布. RESERVED 客户被中断要赔 SLA credit, SPOT 客户合同上写明可被抢占.
CONTRACT_TIER_WEIGHTS = {"RESERVED": 0.52, "ON_DEMAND": 0.31, "SPOT": 0.17}
SLA_CREDIT_USD_PER_LOST_GPU_HOUR = {"RESERVED": 0.95, "ON_DEMAND": 0.35, "SPOT": 0.0}

# --- 陷阱 2: DR 基线灌水 ---
# 被标记的参与记录会在事件前 3 天把负载抬高这个比例, 从而把
# AVG_10_BUSINESS_DAYS 基线一起抬高. 只有用 AVG_10_BUSINESS_DAYS 的项目会中招,
# FIRM_SERVICE_LEVEL 和 METER_BEFORE_AFTER 天然免疫.
BASELINE_INFLATION_RATIO_RANGE = (1.085, 1.155)
BASELINE_INFLATION_LOOKBACK_DAYS = 3
# 被灌水的事件在 TPL1 和 CMH1 上集中出现. 用固定的挑选比例保证可复现.
BASELINE_INFLATION_SITE_CODES = ["TPL1", "CMH1"]
BASELINE_INFLATION_EVENT_SHARE = 0.80
# 抬高后的总负载上限, 相对签约容量. 比 MAX_LOAD_SHARE_OF_CAPACITY 更低, 保证
# 被抬高的区间不会撞到功率封顶线而产生一堆一模一样的读数.
BASELINE_INFLATION_CEILING_SHARE = 0.88

# --- 陷阱 4: 需量电费 ---
# Columbus 园区在 2025-08-14 下午做过一次 GB200 机柜的 burn-in 满载测试, 只持续
# 30 分钟, 但恰好创下当月 15 分钟需量峰值. 因为 85% 的需量棘轮条款, 这个峰值
# 之后 8 个月一直是账单的地板 (棘轮回看窗口是 11 个月, 但真正被垫高的月份是 8 个).
BURN_IN_TEST_SITE_CODE = "CMH1"
BURN_IN_TEST_START = datetime(2025, 8, 14, 15, 30, 0)
BURN_IN_TEST_INTERVALS = 2  # 30 分钟
BURN_IN_TEST_EXTRA_MW = 19.0

# --- 陷阱 5: 4CP 躲避 ---
# ERCOT 的 4CP 是 6 月到 9 月每个月系统负荷最高的那个 15 分钟区间. 你在那 4 个区间
# 的平均用电量决定了你下一年的输电费. 2025 年 4CP 季里 Kestrel 预测对了 3 次,
# 8 月那次预测偏离约 1 小时, 结果峰值时刻园区还在满载.
FOUR_CP_MONTHS = [6, 7, 8, 9]
# (事件年月, 预测是否命中, 预测偏离分钟数). 6 月那次早于计量数据窗口,
# 只保留 ISO 结算口径的记录, 没有对应的计量与削减明细.
FOUR_CP_EVENTS = [
    {"year": 2025, "month": 6, "hit": True, "offset_minutes": 15, "in_window": False},
    {"year": 2025, "month": 7, "hit": True, "offset_minutes": 30, "in_window": True},
    {"year": 2025, "month": 8, "hit": False, "offset_minutes": 75, "in_window": True},
    {"year": 2025, "month": 9, "hit": True, "offset_minutes": 15, "in_window": True},
    {"year": 2026, "month": 6, "hit": True, "offset_minutes": 15, "in_window": True},
]
# 命中时 ERCOT 两座园区能压到的合计负荷 (MW), 未命中时基本等于满载.
FOUR_CP_SUCCESS_DEMAND_MW = (18.0, 26.0)

# --- 经济性削减 ---
# 与 DR 事件无关, 纯粹因为实时电价高到不值得跑任务而主动停机. 只在 ERCOT 发生,
# 因为只有 ERCOT 的价格波动大到让这件事划算.
ECONOMIC_CURTAILMENT_COUNT = 33
ECONOMIC_CURTAILMENT_PRICE_THRESHOLD = 240.0

# --- 任务与客户 ---
JOB_COUNT_TOTAL = 2600
CUSTOMER_NAMES = [
    "Helix Frontier Labs",
    "Northwind AI Research",
    "Cobalt Therapeutics",
    "Wayfinder Autonomy",
    "Lumen Protein Systems",
    "Ardent Robotics",
    "Beacon Language Group",
    "Ridgeline Genomics",
    "Cascade Vision Systems",
    "Ember Molecular",
    "Sable Forecasting Co.",
    "Foxglove Materials AI",
]

CURTAILMENT_DECIDED_BY = [
    "Automated Scheduler",
    "Demand Response Manager",
    "Grid Operations Specialist",
    "VP of Energy Strategy",
]


# ============================================================
# 第 5 节: SQLAlchemy ORM 模型
# ============================================================
# 时序表按 (实体, 时间) 建复合索引. 20 万行的表如果只有主键, 任何按园区或节点
# 切片再按时间过滤的查询都会退化成全表扫描, SQL 查询文档里的多数分析会慢到不可用.
class Base(DeclarativeBase):
    """所有 ORM 模型的基类."""


class IsoMarket(Base):
    """独立系统运营商 (ISO). Kestrel 的园区分布在 ERCOT, PJM, MISO 三个市场."""

    __tablename__ = "iso_market"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    settlement_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    transmission_cost_method: Mapped[str] = mapped_column(String(20), nullable=False)
    has_capacity_market: Mapped[int] = mapped_column(Integer, nullable=False)
    region_description: Mapped[str] = mapped_column(String(400), nullable=False)


class TariffSchedule(Base):
    """当地配电公司的工业大用户费率表. 决定账单里除电量以外的每一项收费."""

    __tablename__ = "tariff_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tariff_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    utility_name: Mapped[str] = mapped_column(String(120), nullable=False)
    iso_market_id: Mapped[int] = mapped_column(ForeignKey("iso_market.id"), nullable=False)
    energy_charge_usd_per_kwh: Mapped[float] = mapped_column(Numeric(10, 5), nullable=False)
    demand_charge_usd_per_kw_month: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    transmission_charge_usd_per_kw_month: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    rider_charge_usd_per_kwh: Mapped[float] = mapped_column(Numeric(10, 5), nullable=False)
    demand_ratchet_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    billing_demand_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)


class Site(Base):
    """一座 AI 算力园区. 是电力合约, 计量, 账单与 DR 注册的共同归属主体."""

    __tablename__ = "site"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    site_name: Mapped[str] = mapped_column(String(80), nullable=False)
    city: Mapped[str] = mapped_column(String(60), nullable=False)
    state_province: Mapped[str] = mapped_column(String(4), nullable=False)
    country: Mapped[str] = mapped_column(String(4), nullable=False)
    iso_market_id: Mapped[int] = mapped_column(ForeignKey("iso_market.id"), nullable=False)
    tariff_schedule_id: Mapped[int] = mapped_column(ForeignKey("tariff_schedule.id"), nullable=False)
    contracted_capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    gpu_count: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_workload_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cooling_type: Mapped[str] = mapped_column(String(20), nullable=False)
    commissioned_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False)


class PricingNode(Base):
    """ISO 结算电价节点. 每座园区在市场里对应一个结算点, 实时电价按这个点结算."""

    __tablename__ = "pricing_node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    node_name: Mapped[str] = mapped_column(String(120), nullable=False)
    iso_market_id: Mapped[int] = mapped_column(ForeignKey("iso_market.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), unique=True, nullable=False)
    zone_name: Mapped[str] = mapped_column(String(30), nullable=False)
    node_type: Mapped[str] = mapped_column(String(30), nullable=False)


class DrProgram(Base):
    """ISO 的需求响应项目. baseline_method 决定削减量怎么算, 也决定能不能被操纵."""

    __tablename__ = "dr_program"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    program_name: Mapped[str] = mapped_column(String(120), nullable=False)
    iso_market_id: Mapped[int] = mapped_column(ForeignKey("iso_market.id"), nullable=False)
    program_type: Mapped[str] = mapped_column(String(30), nullable=False)
    baseline_method: Mapped[str] = mapped_column(String(30), nullable=False)
    capacity_payment_usd_per_mw_month: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    energy_payment_usd_per_mwh: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_events_per_year: Mapped[int] = mapped_column(Integer, nullable=False)
    max_event_duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    notification_lead_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    penalty_usd_per_mw_shortfall: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class SupplyContract(Base):
    """电力供应合约. 三种形态并存: PPA 长约, 零售固定价, 批发指数敞口."""

    __tablename__ = "supply_contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    contract_type: Mapped[str] = mapped_column(String(20), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    counterparty_name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    contracted_volume_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    strike_price_usd_per_mwh: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    settlement_method: Mapped[str] = mapped_column(String(25), nullable=False)
    is_variable_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False)


class DrEnrollment(Base):
    """某座园区在某个 DR 项目下的注册. 承诺削减容量决定容量补偿与欠交罚款."""

    __tablename__ = "dr_enrollment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dr_program_id: Mapped[int] = mapped_column(ForeignKey("dr_program.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    enrolled_capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    enrollment_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    enrollment_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    capacity_payment_usd_per_mw_month: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False)


class ComputeJob(Base):
    """一个 GPU 算力任务. checkpoint_interval_minutes 决定被中断时要回滚多少计算量."""

    __tablename__ = "compute_job"
    __table_args__ = (Index("ix_job_site_started", "site_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    contract_tier: Mapped[str] = mapped_column(String(12), nullable=False)
    gpu_count: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    planned_gpu_hours: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    checkpoint_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_interruptible: Mapped[int] = mapped_column(Integer, nullable=False)
    internal_cost_usd_per_gpu_hour: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False)


class WeatherObservation(Base):
    """园区所在地的逐小时气象观测. 湿球温度是冷却负载的主要驱动变量."""

    __tablename__ = "weather_observation"
    __table_args__ = (Index("ix_weather_site_observed", "site_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dry_bulb_temp_f: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    wet_bulb_temp_f: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    relative_humidity_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    wind_speed_mph: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    cloud_cover_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class LmpIntervalPrice(Base):
    """节点 15 分钟实时电价. system_load_mw 是同一时刻的 ISO 系统总负荷, 用于 4CP 判定."""

    __tablename__ = "lmp_interval_price"
    __table_args__ = (Index("ix_lmp_node_interval", "pricing_node_id", "interval_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pricing_node_id: Mapped[int] = mapped_column(ForeignKey("pricing_node.id"), nullable=False)
    interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    lmp_usd_per_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    energy_component: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    congestion_component: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    loss_component: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    system_load_mw: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_scarcity_interval: Mapped[int] = mapped_column(Integer, nullable=False)


class PpaGenerationHourly(Base):
    """可变出力 PPA 的逐小时实际发电量. 与节点电价的相关性是 shape risk 的来源."""

    __tablename__ = "ppa_generation_hourly"
    __table_args__ = (Index("ix_ppagen_contract_observed", "supply_contract_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supply_contract_id: Mapped[int] = mapped_column(ForeignKey("supply_contract.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    generation_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    capacity_factor_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    curtailed_by_iso_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)


class IntervalMeterReading(Base):
    """园区 15 分钟计量读数. 计费需量, DR 基线与削减量全部由这张表推导."""

    __tablename__ = "interval_meter_reading"
    __table_args__ = (Index("ix_meter_site_interval", "site_id", "interval_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metered_demand_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    it_load_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    cooling_load_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    energy_mwh: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    is_curtailed: Mapped[int] = mapped_column(Integer, nullable=False)


class EnergyInvoice(Base):
    """园区月度电费账单头. blended_rate 是把所有收费摊到每度电上的混合单价."""

    __tablename__ = "energy_invoice"
    __table_args__ = (Index("ix_invoice_site_period", "site_id", "billing_period_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_energy_mwh: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    metered_peak_demand_kw: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    billing_demand_kw: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    peak_interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_ratchet_binding: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    blended_rate_usd_per_kwh: Mapped[float] = mapped_column(Numeric(10, 5), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_date: Mapped[date] = mapped_column(Date, nullable=True)


class EnergyInvoiceLine(Base):
    """账单分项. 把一张账单拆成 ENERGY, DEMAND, TRANSMISSION 等收费类别."""

    __tablename__ = "energy_invoice_line"
    __table_args__ = (Index("ix_invoice_line_invoice", "energy_invoice_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    energy_invoice_id: Mapped[int] = mapped_column(ForeignKey("energy_invoice.id"), nullable=False)
    charge_category: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(12), nullable=False)
    unit_rate_usd: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)


class DrEvent(Base):
    """一次 DR 事件. 4CP 类事件额外记录预测峰值区间与 ISO 结算口径的重合需量."""

    __tablename__ = "dr_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    dr_program_id: Mapped[int] = mapped_column(ForeignKey("dr_program.id"), nullable=False)
    event_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notification_sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(30), nullable=False)
    iso_system_load_mw: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_lmp_usd_per_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    is_mandatory: Mapped[int] = mapped_column(Integer, nullable=False)
    is_test_event: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_peak_interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    iso_actual_peak_interval_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    kestrel_coincident_demand_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=True)


class DrEventParticipation(Base):
    """某园区在某次 DR 事件里的结算记录. 两个 pre_event 均值是基线灌水的检验口."""

    __tablename__ = "dr_event_participation"
    __table_args__ = (Index("ix_participation_event_enrollment", "dr_event_id", "dr_enrollment_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dr_event_id: Mapped[int] = mapped_column(ForeignKey("dr_event.id"), nullable=False)
    dr_enrollment_id: Mapped[int] = mapped_column(ForeignKey("dr_enrollment.id"), nullable=False)
    baseline_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    actual_metered_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    committed_reduction_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    delivered_reduction_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    performance_ratio: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    pre_event_3day_avg_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    pre_event_30day_avg_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    capacity_payment_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    energy_payment_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    penalty_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_settlement_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class CurtailmentAction(Base):
    """一次实际的负载削减动作. dr_event_id 为空表示纯经济性削减, 与任何 DR 项目无关."""

    __tablename__ = "curtailment_action"
    __table_args__ = (Index("ix_curtail_event_site", "dr_event_id", "site_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), nullable=False)
    dr_event_id: Mapped[int] = mapped_column(ForeignKey("dr_event.id"), nullable=True)
    curtailment_type: Mapped[str] = mapped_column(String(25), nullable=False)
    action_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    action_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reduction_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    achieved_reduction_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    energy_avoided_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    market_price_at_action_usd_per_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    energy_cost_avoided_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    decision_made_by: Mapped[str] = mapped_column(String(40), nullable=False)


class CurtailedWorkload(Base):
    """一次削减动作打断的一个具体 GPU 任务. 机会成本在这里被逐条算出来."""

    __tablename__ = "curtailed_workload"
    __table_args__ = (Index("ix_workload_action", "curtailment_action_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curtailment_action_id: Mapped[int] = mapped_column(ForeignKey("curtailment_action.id"), nullable=False)
    compute_job_id: Mapped[int] = mapped_column(ForeignKey("compute_job.id"), nullable=False)
    gpus_released: Mapped[int] = mapped_column(Integer, nullable=False)
    interrupted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resumed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interruption_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_rollback_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    lost_gpu_hours: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    opportunity_cost_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    sla_credit_usd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)


# ============================================================
# 第 6 节: 辅助函数
# ============================================================


def all_intervals() -> list[datetime]:
    """FY2026 的全部 35,040 个 15 分钟区间起点."""
    step = timedelta(minutes=INTERVAL_MINUTES)
    return [WINDOW_START + step * i for i in range(TOTAL_INTERVALS)]


def all_hours() -> list[datetime]:
    """FY2026 的全部 8,760 个整点."""
    return [WINDOW_START + timedelta(hours=i) for i in range(WINDOW_DAYS * 24)]


def seasonal_factor(ts: datetime, peak_month: int = 7) -> float:
    """季节项, 在 peak_month 取 +1, 半年后取 -1. 用于温度与负荷的年周期."""
    day_of_year = ts.timetuple().tm_yday
    peak_day = (peak_month - 1) * 30.4 + 15
    return math.cos(2 * math.pi * (day_of_year - peak_day) / 365.0)


def diurnal_factor(ts: datetime, peak_hour: float = 16.0) -> float:
    """日内项, 在 peak_hour 取 +1, 12 小时后取 -1."""
    hour = ts.hour + ts.minute / 60.0
    return math.cos(2 * math.pi * (hour - peak_hour) / 24.0)


def is_business_day(d: date) -> bool:
    """周一到周五算工作日. DR 基线的 10 个工作日窗口只取工作日."""
    return d.weekday() < 5


def build_weather_series(site: dict) -> dict[datetime, dict[str, float]]:
    """逐小时气象序列. 干球温度 = 年周期 + 日周期 + 噪声, 湿球由干球和湿度推出."""
    series = {}
    for ts in all_hours():
        dry = (
            site["temp_mean_f"]
            + site["temp_amplitude_f"] * seasonal_factor(ts, peak_month=7)
            + 8.0 * diurnal_factor(ts, peak_hour=15.0)
            + random.gauss(0, 3.2)
        )
        # 湿度在夏季更高, 德州与中西部的夏季湿球温度是冷却系统的真正压力来源.
        humidity = max(18.0, min(96.0, 58.0 + 14.0 * seasonal_factor(ts, peak_month=7) + random.gauss(0, 9.0)))
        # 简化的湿球近似: 干球减去一个随湿度下降的差值.
        wet = dry - (1.0 - humidity / 100.0) * 26.0
        series[ts] = {
            "dry_bulb_temp_f": round(dry, 2),
            "wet_bulb_temp_f": round(wet, 2),
            "relative_humidity_pct": round(humidity, 2),
            "wind_speed_mph": round(max(0.0, 8.5 + random.gauss(0, 4.5)), 2),
            "cloud_cover_pct": round(max(0.0, min(100.0, random.gauss(46.0, 27.0))), 2),
        }
    return series


def build_renewable_cf_interval(iso_code: str) -> dict[datetime, float]:
    """各市场的可再生出力容量因子, 15 分钟粒度.

    ERCOT 返回的就是西德州风电的出力曲线, 这一条序列同时驱动两件事:
    Longhorn Ridge PPA 的实际发电量, 以及 ERCOT West 节点电价的压制项.
    两者共用同一条序列是物理事实 (风大 -> 发电多 -> 边际电价被压低), 也正是
    陷阱 3 (PPA 形状风险) 得以成立的根本原因. 如果这里用两条独立随机序列,
    发电量与电价之间就不会有任何相关性, 陷阱也就不存在了.

    形态上, 西德州风电春季最强, 夏季最弱, 夜间强于午后, 这是当地最典型的特征,
    也解释了为什么风电总是在电价最低的时候大发.
    """
    series = {}
    for ts in all_intervals():
        if iso_code == "ERCOT":
            season = 0.30 + 0.13 * math.cos(2 * math.pi * (ts.timetuple().tm_yday - 100) / 365.0)
            night = 0.10 * math.cos(2 * math.pi * (ts.hour - 3.0) / 24.0)
            cf = season + night + random.gauss(0, 0.145)
        elif iso_code == "MISO":
            season = 0.33 + 0.11 * math.cos(2 * math.pi * (ts.timetuple().tm_yday - 90) / 365.0)
            night = 0.070 * math.cos(2 * math.pi * (ts.hour - 2.0) / 24.0)
            cf = season + night + random.gauss(0, 0.100)
        else:
            cf = 0.18 + 0.05 * math.sin(math.pi * max(0, min(12, ts.hour - 7)) / 12.0) + random.gauss(0, 0.040)
        series[ts] = max(0.0, min(0.98, cf))
    return series


def build_solar_capacity_factor(latitude_factor: float) -> dict[datetime, float]:
    """光伏逐小时容量因子. 只有白天出力, 夏季正午最高."""
    series = {}
    for ts in all_hours():
        if ts.hour < 7 or ts.hour > 19:
            series[ts] = 0.0
            continue
        arc = math.sin(math.pi * (ts.hour - 7) / 12.0)
        season = 0.78 + 0.22 * seasonal_factor(ts, peak_month=6)
        cf = arc * season * latitude_factor * (1.0 + random.gauss(0, 0.12))
        series[ts] = max(0.0, min(0.97, cf))
    return series


def build_iso_system_load(iso_code: str) -> dict[datetime, float]:
    """ISO 系统总负荷 (MW), 15 分钟粒度. 4CP 判定完全依赖这条曲线的月度最大值."""
    scale = {"ERCOT": 62000.0, "PJM": 98000.0, "MISO": 78000.0}[iso_code]
    summer_swing = {"ERCOT": 0.32, "PJM": 0.22, "MISO": 0.20}[iso_code]
    winter_bump = {"ERCOT": 0.06, "PJM": 0.15, "MISO": 0.13}[iso_code]
    series = {}
    for ts in all_intervals():
        season = seasonal_factor(ts, peak_month=7)
        # 冬季也有一个次峰, PJM 与 MISO 的冬峰比 ERCOT 明显.
        winter = max(0.0, -season) * winter_bump
        load = scale * (1.0 + summer_swing * max(0.0, season) + winter)
        load *= 1.0 + 0.16 * diurnal_factor(ts, peak_hour=17.0)
        load *= 1.0 + random.gauss(0, 0.022)
        if not is_business_day(ts.date()):
            load *= 0.93
        series[ts] = load
    return series


# ============================================================
# 第 7 节: 世界构建流水线
# ============================================================
#
# 这些表之间有真实的因果依赖, 不能各自独立随机生成, 所以整个世界在一个函数里
# 按下面的顺序构建:
#
#   1. 静态维度 (市场, 费率, 园区, 节点, DR 项目, 供应合约, DR 注册)
#   2. 天气与可再生出力曲线
#   3. ISO 系统负荷 -> 节点电价
#   4. 未削减的园区负载基线
#   5. GPU 任务
#   6. DR 事件 (时点由系统负荷与电价尖峰决定)
#   7. 陷阱 2: 在被标记事件前 3 天抬高负载
#   8. 削减动作 (DR 触发 + 纯经济性)
#   9. 被中断的任务与机会成本
#  10. DR 结算 (基线取自抬高后的序列, 实测取自削减后的序列)
#  11. 最终计量序列 (含陷阱 4 的 burn-in 尖峰)
#  12. 电费账单与分项
#
# 反过来的顺序都会导致自相矛盾的数据, 比如基线算在削减之后, 或者账单峰值
# 对不上计量表.


def build_world() -> dict[str, pl.DataFrame]:
    """按因果顺序构建整个数据集, 返回 {tsv 文件基名: DataFrame}."""
    intervals = all_intervals()
    hours = all_hours()
    interval_index = {ts: i for i, ts in enumerate(intervals)}

    # ---------- 1. 静态维度 ----------
    iso_rows = []
    iso_id_by_code = {}
    for i, m in enumerate(ISO_MARKETS, start=1):
        iso_id_by_code[m["code"]] = i
        iso_rows.append({"id": i, **{k: v for k, v in m.items()}})

    tariff_rows = []
    tariff_id_by_site = {}
    for i, t in enumerate(TARIFF_SCHEDULES, start=1):
        tariff_id_by_site[t["site_code"]] = i
        tariff_rows.append(
            {
                "id": i,
                "tariff_code": t["tariff_code"],
                "utility_name": t["utility_name"],
                "iso_market_id": iso_id_by_code[t["iso_code"]],
                "energy_charge_usd_per_kwh": t["energy_charge_usd_per_kwh"],
                "demand_charge_usd_per_kw_month": t["demand_charge_usd_per_kw_month"],
                "transmission_charge_usd_per_kw_month": t["transmission_charge_usd_per_kw_month"],
                "rider_charge_usd_per_kwh": t["rider_charge_usd_per_kwh"],
                "demand_ratchet_pct": t["demand_ratchet_pct"],
                "billing_demand_basis": t["billing_demand_basis"],
                "effective_from": date(2025, 1, 1),
            }
        )

    site_rows = []
    site_id_by_code = {}
    site_by_code = {}
    for i, s in enumerate(SITES, start=1):
        site_id_by_code[s["site_code"]] = i
        site_by_code[s["site_code"]] = s
        site_rows.append(
            {
                "id": i,
                "site_code": s["site_code"],
                "site_name": s["site_name"],
                "city": s["city"],
                "state_province": s["state_province"],
                "country": "US",
                "iso_market_id": iso_id_by_code[s["iso_code"]],
                "tariff_schedule_id": tariff_id_by_site[s["site_code"]],
                "contracted_capacity_mw": s["contracted_capacity_mw"],
                "gpu_count": s["gpu_count"],
                "primary_workload_type": s["primary_workload_type"],
                "cooling_type": s["cooling_type"],
                "commissioned_date": s["commissioned_date"],
                "is_active": 1,
            }
        )

    node_rows = []
    node_id_by_site = {}
    for i, n in enumerate(PRICING_NODES, start=1):
        node_id_by_site[n["site_code"]] = i
        node_rows.append(
            {
                "id": i,
                "node_code": n["node_code"],
                "node_name": n["node_name"],
                "iso_market_id": iso_id_by_code[site_by_code[n["site_code"]]["iso_code"]],
                "site_id": site_id_by_code[n["site_code"]],
                "zone_name": n["zone_name"],
                "node_type": "SETTLEMENT_POINT",
            }
        )

    program_rows = []
    program_id_by_code = {}
    program_by_code = {}
    for i, p in enumerate(DR_PROGRAMS, start=1):
        program_id_by_code[p["program_code"]] = i
        program_by_code[p["program_code"]] = p
        program_rows.append(
            {
                "id": i,
                "program_code": p["program_code"],
                "program_name": p["program_name"],
                "iso_market_id": iso_id_by_code[p["iso_code"]],
                "program_type": p["program_type"],
                "baseline_method": p["baseline_method"],
                "capacity_payment_usd_per_mw_month": p["capacity_payment_usd_per_mw_month"],
                "energy_payment_usd_per_mwh": p["energy_payment_usd_per_mwh"],
                "max_events_per_year": p["max_events_per_year"],
                "max_event_duration_hours": p["max_event_duration_hours"],
                "notification_lead_time_minutes": p["notification_lead_time_minutes"],
                "penalty_usd_per_mw_shortfall": p["penalty_usd_per_mw_shortfall"],
            }
        )

    contract_rows = []
    contract_id_by_code = {}
    for i, c in enumerate(SUPPLY_CONTRACTS, start=1):
        contract_id_by_code[c["contract_code"]] = i
        contract_rows.append(
            {
                "id": i,
                "contract_code": c["contract_code"],
                "contract_type": c["contract_type"],
                "site_id": site_id_by_code[c["site_code"]],
                "counterparty_name": c["counterparty_name"],
                "start_date": c["start_date"],
                "end_date": c["end_date"],
                "contracted_volume_mw": c["contracted_volume_mw"],
                "strike_price_usd_per_mwh": c["strike_price_usd_per_mwh"],
                "settlement_method": c["settlement_method"],
                "is_variable_generation": 1 if c["is_variable_generation"] else 0,
                "is_active": 1,
            }
        )

    enrollment_rows = []
    enrollment_id_by_key = {}
    for i, (prog_code, site_code, mw) in enumerate(DR_ENROLLMENTS, start=1):
        enrollment_id_by_key[(prog_code, site_code)] = i
        # 承诺量为 0 的那条是已退出的历史注册, 用 is_active = 0 标记.
        active = 1 if mw > 0 else 0
        enrollment_rows.append(
            {
                "id": i,
                "dr_program_id": program_id_by_code[prog_code],
                "site_id": site_id_by_code[site_code],
                "enrolled_capacity_mw": mw,
                "enrollment_start_date": max(
                    date(2025, 7, 1), site_by_code[site_code]["commissioned_date"]
                ),
                "enrollment_end_date": date(2027, 6, 30) if active else date(2025, 12, 31),
                "capacity_payment_usd_per_mw_month": program_by_code[prog_code][
                    "capacity_payment_usd_per_mw_month"
                ],
                "is_active": active,
            }
        )

    # ---------- 2. 天气与可再生出力 ----------
    weather_by_site = {s["site_code"]: build_weather_series(s) for s in SITES}
    tpl_solar_cf = build_solar_capacity_factor(0.92)
    cmh_solar_cf = build_solar_capacity_factor(0.74)

    weather_rows = []
    wid = 1
    for s in SITES:
        sid = site_id_by_code[s["site_code"]]
        for ts in hours:
            w = weather_by_site[s["site_code"]][ts]
            weather_rows.append(
                {
                    "id": wid,
                    "site_id": sid,
                    "observed_at": ts,
                    "dry_bulb_temp_f": w["dry_bulb_temp_f"],
                    "wet_bulb_temp_f": w["wet_bulb_temp_f"],
                    "relative_humidity_pct": w["relative_humidity_pct"],
                    "wind_speed_mph": w["wind_speed_mph"],
                    "cloud_cover_pct": w["cloud_cover_pct"],
                }
            )
            wid += 1

    # ---------- 3. ISO 系统负荷与节点电价 ----------
    system_load = {code: build_iso_system_load(code) for code in ("ERCOT", "PJM", "MISO")}
    renewable_cf = {
        code: build_renewable_cf_interval(code) for code in ("ERCOT", "PJM", "MISO")
    }
    # 把负荷折算成电价压力时用的参照值, 取各市场接近年度峰值的水平而不是均值,
    # 这样 load_ratio 只在真正吃紧的夏季午后才会超过 1.
    load_scale = {"ERCOT": 88000.0, "PJM": 122000.0, "MISO": 98000.0}
    mean_cf = {"ERCOT": 0.30, "PJM": 0.20, "MISO": 0.33}

    lmp_rows = []
    lmp_by_node_ts: dict[int, list[float]] = {}
    lid = 1
    for n in PRICING_NODES:
        node_id = node_id_by_site[n["site_code"]]
        iso_code = site_by_code[n["site_code"]]["iso_code"]
        prices = []
        for ts in intervals:
            load_ratio = system_load[iso_code][ts] / load_scale[iso_code]
            cf = renewable_cf[iso_code][ts]
            # 负荷压力项: 系统越紧, 边际机组越贵, 价格是凸的.
            load_term = 260.0 * max(0.0, load_ratio - 1.0) ** 1.6
            energy_component = (
                n["base_lmp"]
                + n["diurnal_amplitude"] * diurnal_factor(ts, peak_hour=17.5)
                + load_term
                - n["wind_suppression"] * (cf - mean_cf[iso_code])
                + random.gauss(0, n["volatility"] * 0.45)
            )
            congestion = random.gauss(0, n["volatility"] * 0.55)
            loss = energy_component * random.uniform(0.008, 0.026)

            lmp = energy_component + congestion + loss
            # 稀缺定价只在系统负荷高且可再生出力低的时候出现, 这是真实的物理逻辑,
            # 也保证了 Longhorn Ridge 大发的时候永远吃不到尖峰价.
            if (
                load_ratio > 1.02
                and cf < mean_cf[iso_code]
                and random.random() < n["spike_probability"] * 25
            ):
                lmp = random.uniform(*SCARCITY_PRICE_RANGE)
                energy_component = lmp - congestion - loss
            # 价格下限: ERCOT 与 MISO 在风电大发时经常出现负电价.
            floor = -100.0 if iso_code == "ERCOT" else (-40.0 if iso_code == "MISO" else -15.0)
            lmp = max(floor, lmp)
            prices.append(lmp)
            lmp_rows.append(
                {
                    "id": lid,
                    "pricing_node_id": node_id,
                    "interval_start": ts,
                    "interval_end": ts + timedelta(minutes=INTERVAL_MINUTES),
                    "lmp_usd_per_mwh": round(lmp, 4),
                    "energy_component": round(energy_component, 4),
                    "congestion_component": round(congestion, 4),
                    "loss_component": round(loss, 4),
                    "system_load_mw": round(system_load[iso_code][ts], 2),
                    "is_scarcity_interval": 1 if lmp > SCARCITY_FLAG_THRESHOLD else 0,
                }
            )
            lid += 1
        lmp_by_node_ts[node_id] = prices

    # ---------- 4. 未削减的园区负载基线 ----------
    # base_load[site_code] 是一个与 intervals 等长的列表, 单位 MW.
    base_it = {}
    base_cooling = {}
    for s in SITES:
        shape = LOAD_SHAPE_BY_WORKLOAD[s["primary_workload_type"]]
        cap = s["contracted_capacity_mw"]
        cool_base = COOLING_BASE_RATIO[s["cooling_type"]]
        cool_sens = COOLING_TEMP_SENSITIVITY[s["cooling_type"]]
        it_share = IT_CAPACITY_SHARE_BY_COOLING[s["cooling_type"]]
        it_series = []
        cool_series = []
        for ts in intervals:
            if ts.date() < s["commissioned_date"]:
                it_series.append(0.0)
                cool_series.append(0.0)
                continue
            # 新园区投产后有一段爬坡期, 60 天内线性爬到设计负载.
            ramp_days = (ts.date() - s["commissioned_date"]).days
            ramp = min(1.0, 0.35 + 0.65 * ramp_days / 60.0) if ramp_days < 60 else 1.0
            frac = shape["base"] + shape["diurnal_amplitude"] * diurnal_factor(ts, peak_hour=14.0)
            frac *= 1.0 + random.gauss(0, shape["noise_sd"])
            it_mw = cap * it_share * frac * ramp
            wet = weather_by_site[s["site_code"]][ts.replace(minute=0)]["wet_bulb_temp_f"]
            cool_ratio = cool_base + cool_sens * max(0.0, wet - COOLING_WETBULB_THRESHOLD_F)
            cool_mw = it_mw * cool_ratio
            # 功率封顶: 总负载触到上限时按比例把 IT 与冷却一起压回去.
            ceiling = cap * MAX_LOAD_SHARE_OF_CAPACITY
            if it_mw + cool_mw > ceiling:
                shrink = ceiling / (it_mw + cool_mw)
                it_mw *= shrink
                cool_mw *= shrink
            it_series.append(it_mw)
            cool_series.append(cool_mw)
        base_it[s["site_code"]] = it_series
        base_cooling[s["site_code"]] = cool_series

    def total_base(site_code: str, idx: int) -> float:
        return base_it[site_code][idx] + base_cooling[site_code][idx]

    # ---------- 5. GPU 任务 ----------
    job_rows = []
    jobs_by_site: dict[str, list[dict]] = {s["site_code"]: [] for s in SITES}
    total_gpu = sum(s["gpu_count"] for s in SITES)
    jid = 1
    for s in SITES:
        site_code = s["site_code"]
        n_jobs = max(60, round(JOB_COUNT_TOTAL * s["gpu_count"] / total_gpu))
        mix = JOB_TYPE_MIX_BY_SITE[site_code]
        job_types = list(mix.keys())
        job_weights = list(mix.values())
        earliest = max(WINDOW_START, datetime.combine(s["commissioned_date"], datetime.min.time()))
        span_minutes = int((WINDOW_END - earliest).total_seconds() // 60)
        for _ in range(n_jobs):
            job_type = random.choices(job_types, weights=job_weights, k=1)[0]
            tier = random.choices(
                list(CONTRACT_TIER_WEIGHTS.keys()),
                weights=list(CONTRACT_TIER_WEIGHTS.values()),
                k=1,
            )[0]
            # 任务时长与 GPU 规模都按任务类型分档. 预训练是"少而大且长",
            # 在线推理是"多而小且常驻".
            if job_type == "PRETRAINING":
                gpus = random.choice([512, 1024, 1536, 2048, 3072, 4096])
                duration_h = random.uniform(120, 720)
            elif job_type == "FINETUNING":
                gpus = random.choice([64, 128, 256, 512])
                duration_h = random.uniform(6, 96)
            elif job_type == "INFERENCE_SERVING":
                gpus = random.choice([32, 64, 128, 256, 512])
                duration_h = random.uniform(360, 2400)
            elif job_type == "INFERENCE_BATCH":
                gpus = random.choice([16, 32, 64, 128])
                duration_h = random.uniform(2, 30)
            else:
                gpus = random.choice([8, 16, 32, 64])
                duration_h = random.uniform(3, 48)

            started = earliest + timedelta(minutes=random.randint(0, max(1, span_minutes)))
            planned_end = started + timedelta(hours=duration_h)
            submitted = started - timedelta(minutes=random.randint(5, 900))
            if planned_end > WINDOW_END:
                status = "RUNNING"
                actual_end = None
            else:
                status = random.choices(["COMPLETED", "FAILED"], weights=[0.94, 0.06], k=1)[0]
                actual_end = planned_end + timedelta(minutes=random.randint(-30, 240))
            # SPOT 档位与 RESEARCH / INFERENCE_BATCH 类任务合同上允许被抢占.
            interruptible = 1 if (tier == "SPOT" or job_type in ("RESEARCH", "INFERENCE_BATCH")) else 0
            job = {
                "id": jid,
                "job_code": f"JOB-{site_code}-{jid:06d}",
                "site_id": site_id_by_code[site_code],
                "customer_name": random.choice(CUSTOMER_NAMES),
                "job_type": job_type,
                "contract_tier": tier,
                "gpu_count": gpus,
                "submitted_at": submitted,
                "started_at": started,
                "planned_end_at": planned_end,
                "actual_end_at": actual_end,
                "planned_gpu_hours": round(gpus * duration_h, 2),
                "checkpoint_interval_minutes": CHECKPOINT_INTERVAL_MINUTES[job_type],
                "is_interruptible": interruptible,
                "internal_cost_usd_per_gpu_hour": GPU_OPPORTUNITY_COST_USD_PER_HOUR[job_type],
                "status": status,
            }
            job_rows.append(job)
            jobs_by_site[site_code].append(
                {"row": job, "start": started, "end": planned_end}
            )
            jid += 1

    # ---------- 6. DR 事件 ----------
    def pick_event_intervals(iso_code: str, count: int, months: list[int], min_gap_days: int) -> list[datetime]:
        """在指定月份里挑系统负荷最高的若干个下午区间, 且彼此间隔不少于 min_gap_days 天."""
        candidates = [
            ts
            for ts in intervals
            if ts.month in months and 12 <= ts.hour <= 20 and ts.minute == 0
        ]
        candidates.sort(key=lambda t: -system_load[iso_code][t])
        chosen: list[datetime] = []
        for ts in candidates:
            if all(abs((ts - c).days) >= min_gap_days for c in chosen):
                chosen.append(ts)
            if len(chosen) == count:
                break
        return sorted(chosen)

    event_rows = []
    eid = 1
    event_meta: list[dict] = []

    program_event_spec = {
        "ERCOT-ERS-10": {"months": [7, 8, 9, 6], "gap": 4, "trigger": "SYSTEM_EMERGENCY", "mandatory": 1},
        "ERCOT-CLR-RRS": {"months": [7, 8, 9, 5, 6], "gap": 5, "trigger": "PRICE_SPIKE", "mandatory": 0},
        "PJM-ELRP": {"months": [7, 8, 1, 2, 6], "gap": 6, "trigger": "SYSTEM_EMERGENCY", "mandatory": 1},
        "PJM-CP": {"months": [7, 8, 1, 6], "gap": 12, "trigger": "CAPACITY_TEST", "mandatory": 1},
        "MISO-LMR": {"months": [7, 8, 9, 1, 2, 6], "gap": 5, "trigger": "SYSTEM_EMERGENCY", "mandatory": 1},
    }

    for prog_code, spec in program_event_spec.items():
        prog = program_by_code[prog_code]
        iso_code = prog["iso_code"]
        starts = pick_event_intervals(iso_code, DR_EVENT_COUNTS[prog_code], spec["months"], spec["gap"])
        for k, start in enumerate(starts):
            duration_h = random.randint(1, prog["max_event_duration_hours"])
            end = start + timedelta(hours=duration_h)
            node_ids = [
                node_id_by_site[sc] for (pc, sc, _mw) in DR_ENROLLMENTS if pc == prog_code
            ]
            idx_range = [
                interval_index[start] + j
                for j in range(duration_h * 4)
                if interval_index[start] + j < TOTAL_INTERVALS
            ]
            max_lmp = max(
                (lmp_by_node_ts[nid][j] for nid in node_ids for j in idx_range),
                default=0.0,
            )
            # 容量测试事件不是真的系统紧急, 一年就一两次, 用来核验削减能力.
            is_test = 1 if (spec["trigger"] == "CAPACITY_TEST" and k % 3 == 0) else 0
            event_rows.append(
                {
                    "id": eid,
                    "event_code": f"{prog_code}-FY26-{k + 1:02d}",
                    "dr_program_id": program_id_by_code[prog_code],
                    "event_start": start,
                    "event_end": end,
                    "notification_sent_at": start - timedelta(minutes=prog["notification_lead_time_minutes"]),
                    "trigger_reason": spec["trigger"],
                    "iso_system_load_mw": round(system_load[iso_code][start], 2),
                    "max_lmp_usd_per_mwh": round(max_lmp, 4),
                    "is_mandatory": spec["mandatory"],
                    "is_test_event": is_test,
                    "predicted_peak_interval_start": None,
                    "iso_actual_peak_interval_start": None,
                    "kestrel_coincident_demand_mw": None,
                }
            )
            event_meta.append(
                {
                    "id": eid,
                    "program_code": prog_code,
                    "start": start,
                    "end": end,
                    "duration_h": duration_h,
                    "is_test": is_test,
                    "is_4cp": False,
                }
            )
            eid += 1

    # 4CP 躲避事件. 半窗口 60 分钟: 预测偏离在 60 分钟以内算命中, 超过就扑空.
    FOUR_CP_HALF_WINDOW_MINUTES = 60
    for spec in FOUR_CP_EVENTS:
        year, month = spec["year"], spec["month"]
        if spec["in_window"]:
            month_intervals = [ts for ts in intervals if ts.year == year and ts.month == month]
            actual_peak = max(month_intervals, key=lambda t: system_load["ERCOT"][t])
        else:
            # 该月早于计量窗口, 只保留 ISO 事后结算通知里的时点.
            actual_peak = datetime(year, month, 24, 17, 0, 0)
        predicted_peak = actual_peak - timedelta(minutes=spec["offset_minutes"])
        start = predicted_peak - timedelta(minutes=FOUR_CP_HALF_WINDOW_MINUTES)
        end = predicted_peak + timedelta(minutes=FOUR_CP_HALF_WINDOW_MINUTES)
        if spec["in_window"] and spec["hit"]:
            coincident = round(random.uniform(*FOUR_CP_SUCCESS_DEMAND_MW), 3)
        elif spec["in_window"]:
            # 扑空: 峰值时刻两座 ERCOT 园区还在满载.
            idx = interval_index[actual_peak]
            coincident = round(total_base("ABI1", idx) + total_base("TPL1", idx), 3)
        else:
            coincident = round(random.uniform(*FOUR_CP_SUCCESS_DEMAND_MW), 3)
        event_rows.append(
            {
                "id": eid,
                "event_code": f"ERCOT-4CP-AVOID-{year}-{month:02d}",
                "dr_program_id": program_id_by_code["ERCOT-4CP-AVOID"],
                "event_start": start,
                "event_end": end,
                "notification_sent_at": start - timedelta(minutes=240),
                "trigger_reason": "FORECAST_4CP_PEAK",
                "iso_system_load_mw": round(system_load["ERCOT"][actual_peak], 2)
                if spec["in_window"]
                else 79420.0,
                "max_lmp_usd_per_mwh": round(
                    max(lmp_by_node_ts[node_id_by_site["ABI1"]][interval_index[actual_peak]], 0.0), 4
                )
                if spec["in_window"]
                else 412.5,
                "is_mandatory": 0,
                "is_test_event": 0,
                "predicted_peak_interval_start": predicted_peak,
                "iso_actual_peak_interval_start": actual_peak,
                "kestrel_coincident_demand_mw": coincident,
            }
        )
        if spec["in_window"]:
            event_meta.append(
                {
                    "id": eid,
                    "program_code": "ERCOT-4CP-AVOID",
                    "start": start,
                    "end": end,
                    "duration_h": 2,
                    "is_test": 0,
                    "is_4cp": True,
                }
            )
        eid += 1

    # 灌水前先给站点共享负载序列拍一张干净快照. 下面的灌水会就地改写 base_it /
    # base_cooling, 让 metered / invoice / AVG_10 基线都物理性地看到抬高后的负载 ——
    # 这部分保持不变. 但 pre_event_3day_avg_mw / pre_event_30day_avg_mw 这两个纯诊断
    # 字段只应该在"确实被标记做过灌水"的 AVG_10 参与记录上体现. 非 AVG_10 项目
    # (FIRM_SERVICE_LEVEL / METER_BEFORE_AFTER) 即便 3 天回看窗口与同园区某个 AVG_10
    # 事件的灌水区间重叠, 也必须读这份干净快照, 否则比值会外溢到 1.03 以上, 与文档
    # "另两种基线全部在 1.03 以内"的论证自相矛盾. 具体见 window_avg 的 inflated 参数.
    base_it_clean = {sc: list(vals) for sc, vals in base_it.items()}
    base_cooling_clean = {sc: list(vals) for sc, vals in base_cooling.items()}

    # ---------- 7. 陷阱 2: 事件前 3 天抬高负载 ----------
    # 只有用 AVG_10_BUSINESS_DAYS 基线的项目值得这么干, 而且只发生在 TPL1 与 CMH1
    # 这两个有富余可调负载的园区. 抬高的是 IT 负载 (多排一批低优先级批量推理任务).
    inflated_participation_keys: set[tuple[int, str]] = set()
    for meta in event_meta:
        prog = program_by_code[meta["program_code"]]
        if prog["baseline_method"] != "AVG_10_BUSINESS_DAYS":
            continue
        for pc, sc, mw in DR_ENROLLMENTS:
            if pc != meta["program_code"] or mw <= 0:
                continue
            if sc not in BASELINE_INFLATION_SITE_CODES:
                continue
            if random.random() > BASELINE_INFLATION_EVENT_SHARE:
                continue
            ratio = random.uniform(*BASELINE_INFLATION_RATIO_RANGE)
            cap = site_by_code[sc]["contracted_capacity_mw"]
            window_start = meta["start"] - timedelta(days=BASELINE_INFLATION_LOOKBACK_DAYS)
            for idx in range(TOTAL_INTERVALS):
                ts = intervals[idx]
                if not (window_start <= ts < meta["start"]):
                    continue
                # 抬高负载时按"还剩多少余量"平滑缩放, 而不是先乘再一刀切.
                # 一刀切会让一大批区间的读数落在完全相同的封顶值上, 计量数据里
                # 出现成百上千个一模一样的数字, 稽核的人一眼就能看出是人造的.
                current = base_it[sc][idx] + base_cooling[sc][idx]
                if current <= 0:
                    continue
                headroom = max(0.0, cap * BASELINE_INFLATION_CEILING_SHARE - current)
                increment = min(current * (ratio - 1.0), headroom * 0.85)
                scale = (current + increment) / current
                base_it[sc][idx] *= scale
                base_cooling[sc][idx] *= scale
            inflated_participation_keys.add((meta["id"], sc))

    # ---------- 8. 削减动作 ----------
    curtailment_rows = []
    curtailment_meta: list[dict] = []
    cid = 1
    # 每个区间上累计的削减量, 之后一次性从基线里扣掉.
    reduction_by_site: dict[str, dict[int, float]] = {s["site_code"]: {} for s in SITES}

    for meta in event_meta:
        prog = program_by_code[meta["program_code"]]
        for pc, sc, mw in DR_ENROLLMENTS:
            if pc != meta["program_code"] or mw <= 0:
                continue
            if site_by_code[sc]["commissioned_date"] > meta["start"].date():
                continue
            # 实际达成的削减量围绕承诺量波动, 偶尔欠交. 4CP 是自己主动做的, 达成率最高.
            if meta["is_4cp"]:
                achieved = mw * random.uniform(0.96, 1.02)
            else:
                achieved = mw * random.uniform(0.82, 1.08)
            start_idx = interval_index[meta["start"]]
            n_int = meta["duration_h"] * 4
            idxs = [start_idx + j for j in range(n_int) if start_idx + j < TOTAL_INTERVALS]
            for idx in idxs:
                # 削减量不能超过当时的实际负载.
                avail = total_base(sc, idx)
                reduction_by_site[sc][idx] = min(
                    avail * 0.85, reduction_by_site[sc].get(idx, 0.0) + achieved
                )
            energy_avoided = achieved * len(idxs) * (INTERVAL_MINUTES / 60.0)
            node_id = node_id_by_site[sc]
            price = sum(lmp_by_node_ts[node_id][i] for i in idxs) / max(1, len(idxs))
            ctype = "4CP_AVOIDANCE" if meta["is_4cp"] else "DR_EVENT"
            decider = (
                "Grid Operations Specialist"
                if meta["is_4cp"]
                else random.choices(CURTAILMENT_DECIDED_BY, weights=[0.55, 0.28, 0.11, 0.06], k=1)[0]
            )
            curtailment_rows.append(
                {
                    "id": cid,
                    "action_code": f"CUR-{sc}-{cid:05d}",
                    "site_id": site_id_by_code[sc],
                    "dr_event_id": meta["id"],
                    "curtailment_type": ctype,
                    "action_start": meta["start"],
                    "action_end": meta["end"],
                    "duration_minutes": len(idxs) * INTERVAL_MINUTES,
                    "target_reduction_mw": round(mw, 3),
                    "achieved_reduction_mw": round(achieved, 3),
                    "energy_avoided_mwh": round(energy_avoided, 4),
                    "market_price_at_action_usd_per_mwh": round(price, 4),
                    "energy_cost_avoided_usd": round(energy_avoided * price, 2),
                    "decision_made_by": decider,
                }
            )
            curtailment_meta.append(
                {
                    "id": cid,
                    "site_code": sc,
                    "event_id": meta["id"],
                    "start": meta["start"],
                    "end": meta["end"],
                    "duration_minutes": len(idxs) * INTERVAL_MINUTES,
                    "achieved_mw": achieved,
                }
            )
            cid += 1

    # 纯经济性削减: 实时价格高过阈值时主动停机, 与任何 DR 项目无关.
    ercot_sites = ["ABI1", "TPL1"]
    econ_candidates = []
    for sc in ercot_sites:
        node_id = node_id_by_site[sc]
        for idx, price in enumerate(lmp_by_node_ts[node_id]):
            if price >= ECONOMIC_CURTAILMENT_PRICE_THRESHOLD:
                econ_candidates.append((price, sc, idx))
    econ_candidates.sort(reverse=True)
    used_days: set[tuple[str, date]] = set()
    econ_taken = 0
    for price, sc, idx in econ_candidates:
        if econ_taken >= ECONOMIC_CURTAILMENT_COUNT:
            break
        ts = intervals[idx]
        if (sc, ts.date()) in used_days:
            continue
        used_days.add((sc, ts.date()))
        n_int = random.choice([2, 3, 4, 6])
        idxs = [idx + j for j in range(n_int) if idx + j < TOTAL_INTERVALS]
        achieved = site_by_code[sc]["contracted_capacity_mw"] * random.uniform(0.05, 0.14)
        for i in idxs:
            avail = total_base(sc, i)
            reduction_by_site[sc][i] = min(
                avail * 0.85, reduction_by_site[sc].get(i, 0.0) + achieved
            )
        energy_avoided = achieved * len(idxs) * (INTERVAL_MINUTES / 60.0)
        node_id = node_id_by_site[sc]
        avg_price = sum(lmp_by_node_ts[node_id][i] for i in idxs) / len(idxs)
        curtailment_rows.append(
            {
                "id": cid,
                "action_code": f"CUR-{sc}-{cid:05d}",
                "site_id": site_id_by_code[sc],
                "dr_event_id": None,
                "curtailment_type": "ECONOMIC",
                "action_start": ts,
                "action_end": ts + timedelta(minutes=len(idxs) * INTERVAL_MINUTES),
                "duration_minutes": len(idxs) * INTERVAL_MINUTES,
                "target_reduction_mw": round(achieved, 3),
                "achieved_reduction_mw": round(achieved, 3),
                "energy_avoided_mwh": round(energy_avoided, 4),
                "market_price_at_action_usd_per_mwh": round(avg_price, 4),
                "energy_cost_avoided_usd": round(energy_avoided * avg_price, 2),
                "decision_made_by": "Automated Scheduler",
            }
        )
        curtailment_meta.append(
            {
                "id": cid,
                "site_code": sc,
                "event_id": None,
                "start": ts,
                "end": ts + timedelta(minutes=len(idxs) * INTERVAL_MINUTES),
                "duration_minutes": len(idxs) * INTERVAL_MINUTES,
                "achieved_mw": achieved,
            }
        )
        cid += 1
        econ_taken += 1

    # ---------- 9. 被中断的任务 ----------
    workload_rows = []
    wlid = 1
    for cm in curtailment_meta:
        sc = cm["site_code"]
        cap = site_by_code[sc]["contracted_capacity_mw"]
        gpu_total = site_by_code[sc]["gpu_count"]
        mw_per_gpu = cap / gpu_total
        gpus_to_release = int(cm["achieved_mw"] / mw_per_gpu)
        running = [
            j for j in jobs_by_site[sc] if j["start"] <= cm["start"] and j["end"] >= cm["end"]
        ]
        if not running:
            continue
        # 调度器优先抢占可中断任务, 但可中断的容量往往不够, 剩下的只能从
        # 长周期训练任务里挖. 这正是训练型园区 DR 成本失控的机制.
        running.sort(key=lambda j: (-j["row"]["is_interruptible"], j["row"]["internal_cost_usd_per_gpu_hour"]))
        released = 0
        for j in running:
            if released >= gpus_to_release:
                break
            job = j["row"]
            take = min(job["gpu_count"], gpus_to_release - released)
            if take <= 0:
                continue
            released += take
            ckpt = job["checkpoint_interval_minutes"]
            # 中断发生在两次 checkpoint 之间的随机位置, 平均回滚半个间隔.
            rollback = int(ckpt * random.uniform(0.25, 0.85)) if ckpt > 0 else 0
            lost_gpu_hours = take * (cm["duration_minutes"] + rollback) / 60.0
            opp = lost_gpu_hours * job["internal_cost_usd_per_gpu_hour"]
            sla = lost_gpu_hours * SLA_CREDIT_USD_PER_LOST_GPU_HOUR[job["contract_tier"]]
            workload_rows.append(
                {
                    "id": wlid,
                    "curtailment_action_id": cm["id"],
                    "compute_job_id": job["id"],
                    "gpus_released": take,
                    "interrupted_at": cm["start"],
                    "resumed_at": cm["end"],
                    "interruption_minutes": cm["duration_minutes"],
                    "checkpoint_rollback_minutes": rollback,
                    "lost_gpu_hours": round(lost_gpu_hours, 3),
                    "opportunity_cost_usd": round(opp, 2),
                    "sla_credit_usd": round(sla, 2),
                }
            )
            wlid += 1

    # ---------- 10. 最终计量序列 ----------
    final_load: dict[str, list[float]] = {}
    final_it: dict[str, list[float]] = {}
    final_cool: dict[str, list[float]] = {}
    for s in SITES:
        sc = s["site_code"]
        it_out, cool_out, tot_out = [], [], []
        for idx in range(TOTAL_INTERVALS):
            it_mw = base_it[sc][idx]
            cool_mw = base_cooling[sc][idx]
            cut = reduction_by_site[sc].get(idx, 0.0)
            if cut > 0 and (it_mw + cool_mw) > 0:
                # 削减动作先关 GPU, 冷却负载随之按比例下降.
                share = max(0.0, 1.0 - cut / (it_mw + cool_mw))
                it_mw *= share
                cool_mw *= share
            it_out.append(it_mw)
            cool_out.append(cool_mw)
            tot_out.append(it_mw + cool_mw)
        final_it[sc] = it_out
        final_cool[sc] = cool_out
        final_load[sc] = tot_out

    # 陷阱 4: Columbus 园区的 burn-in 满载测试, 只有 30 分钟, 却创下当月需量峰值.
    burn_idx = interval_index[BURN_IN_TEST_START]
    for j in range(BURN_IN_TEST_INTERVALS):
        i = burn_idx + j
        final_it[BURN_IN_TEST_SITE_CODE][i] += BURN_IN_TEST_EXTRA_MW
        final_load[BURN_IN_TEST_SITE_CODE][i] += BURN_IN_TEST_EXTRA_MW

    meter_rows = []
    mid = 1
    for s in SITES:
        sc = s["site_code"]
        sid = site_id_by_code[sc]
        for idx, ts in enumerate(intervals):
            total = final_load[sc][idx]
            meter_rows.append(
                {
                    "id": mid,
                    "site_id": sid,
                    "interval_start": ts,
                    "interval_end": ts + timedelta(minutes=INTERVAL_MINUTES),
                    "metered_demand_mw": round(total, 3),
                    "it_load_mw": round(final_it[sc][idx], 3),
                    "cooling_load_mw": round(final_cool[sc][idx], 3),
                    "energy_mwh": round(total * INTERVAL_MINUTES / 60.0, 4),
                    "is_curtailed": 1 if reduction_by_site[sc].get(idx, 0.0) > 0 else 0,
                }
            )
            mid += 1

    # ---------- 11. DR 结算 ----------
    def business_day_baseline(site_code: str, event_start: datetime, duration_h: int) -> float:
        """AVG_10_BUSINESS_DAYS 基线: 取事件前 10 个工作日同时段的未削减负载均值."""
        vals = []
        d = event_start.date() - timedelta(days=1)
        collected = 0
        while collected < 10 and d >= WINDOW_START.date():
            if is_business_day(d):
                day_vals = []
                for h in range(duration_h * 4):
                    ts = datetime.combine(d, event_start.time()) + timedelta(
                        minutes=INTERVAL_MINUTES * h
                    )
                    if ts in interval_index:
                        day_vals.append(total_base(site_code, interval_index[ts]))
                if day_vals:
                    vals.append(sum(day_vals) / len(day_vals))
                    collected += 1
            d -= timedelta(days=1)
        return sum(vals) / len(vals) if vals else 0.0

    def firm_service_baseline(site_code: str, event_start: datetime, duration_h: int) -> float:
        """FIRM_SERVICE_LEVEL 基线: 取事件前 30 个自然日同时段的未削减负载均值.

        与 AVG_10_BUSINESS_DAYS 的关键差别是窗口长得多. 事件前 3 天就算被人为抬高,
        摊到 30 天里也只能把基线推高一个百分点左右, 所以这类项目对基线灌水免疫.
        """
        vals = []
        d = event_start.date() - timedelta(days=1)
        collected = 0
        while collected < 30 and d >= WINDOW_START.date():
            day_vals = []
            for h in range(duration_h * 4):
                ts = datetime.combine(d, event_start.time()) + timedelta(
                    minutes=INTERVAL_MINUTES * h
                )
                if ts in interval_index:
                    day_vals.append(total_base(site_code, interval_index[ts]))
            if day_vals:
                vals.append(sum(day_vals) / len(day_vals))
                collected += 1
            d -= timedelta(days=1)
        return sum(vals) / len(vals) if vals else 0.0

    def window_avg(
        site_code: str,
        end_ts: datetime,
        days: int,
        series: str = "base",
        inflated: bool = False,
    ) -> float:
        """事件前 N 天的整体平均负载, 用来检验基线是否被人为抬高.

        inflated=True 时读取被灌水的站点负载序列, 只对确实被标记做过基线灌水的
        AVG_10 参与记录传 True; 其余记录一律传 False, 读灌水前的干净快照. 这样灌水
        只体现在被标记记录自己的诊断上, 不会因为同园区某个 AVG_10 事件的灌水窗口与
        本记录的回看窗口重叠而外溢, FIRM / METER 项目的比值因此真正压回 1.03 以内.
        """
        start_ts = end_ts - timedelta(days=days)
        vals = []
        for idx in range(TOTAL_INTERVALS):
            ts = intervals[idx]
            if start_ts <= ts < end_ts:
                if series != "base":
                    vals.append(final_load[site_code][idx])
                elif inflated:
                    vals.append(base_it[site_code][idx] + base_cooling[site_code][idx])
                else:
                    vals.append(base_it_clean[site_code][idx] + base_cooling_clean[site_code][idx])
        return sum(vals) / len(vals) if vals else 0.0

    participation_rows = []
    pid = 1
    events_per_program_year = dict(DR_EVENT_COUNTS)
    for meta in event_meta:
        prog = program_by_code[meta["program_code"]]
        for pc, sc, mw in DR_ENROLLMENTS:
            if pc != meta["program_code"] or mw <= 0:
                continue
            if site_by_code[sc]["commissioned_date"] > meta["start"].date():
                continue
            start_idx = interval_index[meta["start"]]
            n_int = meta["duration_h"] * 4
            idxs = [start_idx + j for j in range(n_int) if start_idx + j < TOTAL_INTERVALS]
            actual = sum(final_load[sc][i] for i in idxs) / len(idxs)

            if prog["baseline_method"] == "AVG_10_BUSINESS_DAYS":
                baseline = business_day_baseline(sc, meta["start"], meta["duration_h"])
            elif prog["baseline_method"] == "METER_BEFORE_AFTER":
                # 取事件前后各 1 小时的未削减负载, 对拉高基线不敏感.
                pre = [total_base(sc, i) for i in range(max(0, start_idx - 4), start_idx)]
                post_start = start_idx + n_int
                post = [
                    total_base(sc, i)
                    for i in range(post_start, min(TOTAL_INTERVALS, post_start + 4))
                ]
                pool = pre + post
                baseline = sum(pool) / len(pool) if pool else 0.0
            else:
                # FIRM_SERVICE_LEVEL: 用 30 天同时段均值作为合同约定的参照负载.
                baseline = firm_service_baseline(sc, meta["start"], meta["duration_h"])

            delivered = max(0.0, baseline - actual)
            # ISO 对超额交付设有认定上限, 通常是承诺量的 2 倍, 超出部分不予结算.
            perf = min(2.0, delivered / mw) if mw > 0 else 0.0
            # 容量补偿把全年的月度容量费摊到当年实际发生的事件上.
            n_events = events_per_program_year.get(meta["program_code"], 1)
            cap_pay = (
                mw
                * prog["capacity_payment_usd_per_mw_month"]
                * 12.0
                / max(1, n_events)
                * min(1.0, perf)
            )
            energy_pay = (
                delivered * meta["duration_h"] * prog["energy_payment_usd_per_mwh"]
            )
            penalty = (
                max(0.0, mw - delivered) * prog["penalty_usd_per_mw_shortfall"] * 0.25
                if perf < 0.85
                else 0.0
            )
            # 只有确实被标记做过灌水的 AVG_10 参与记录, 两个诊断字段才读被抬高的序列;
            # 其它记录读干净快照, 保证灌水不外溢到别的基线算法 (见 window_avg).
            is_inflated = (meta["id"], sc) in inflated_participation_keys
            participation_rows.append(
                {
                    "id": pid,
                    "dr_event_id": meta["id"],
                    "dr_enrollment_id": enrollment_id_by_key[(pc, sc)],
                    "baseline_mw": round(baseline, 3),
                    "actual_metered_mw": round(actual, 3),
                    "committed_reduction_mw": round(mw, 3),
                    "delivered_reduction_mw": round(delivered, 3),
                    "performance_ratio": round(perf, 4),
                    "pre_event_3day_avg_mw": round(window_avg(sc, meta["start"], 3, inflated=is_inflated), 3),
                    "pre_event_30day_avg_mw": round(window_avg(sc, meta["start"], 30, inflated=is_inflated), 3),
                    "capacity_payment_usd": round(cap_pay, 2),
                    "energy_payment_usd": round(energy_pay, 2),
                    "penalty_usd": round(penalty, 2),
                    "total_settlement_usd": round(cap_pay + energy_pay - penalty, 2),
                }
            )
            pid += 1

    # ---------- 12. PPA 逐小时出力 ----------
    ppa_rows = []
    ppid = 1
    # 风电 PPA 的小时出力直接由驱动 ERCOT West 电价的那条 15 分钟序列聚合而来.
    ercot_wind_hourly = {}
    for ts in hours:
        vals = [
            renewable_cf["ERCOT"][ts + timedelta(minutes=INTERVAL_MINUTES * k)]
            for k in range(4)
            if ts + timedelta(minutes=INTERVAL_MINUTES * k) in renewable_cf["ERCOT"]
        ]
        ercot_wind_hourly[ts] = sum(vals) / len(vals) if vals else 0.0

    variable_ppa_cf = {
        "PPA-LHR-WIND-01": ercot_wind_hourly,
        "PPA-BLK-SOLAR-01": tpl_solar_cf,
        "PPA-BUC-SOLAR-01": cmh_solar_cf,
    }
    for code, cf_series in variable_ppa_cf.items():
        contract = next(c for c in SUPPLY_CONTRACTS if c["contract_code"] == code)
        # 把生成的容量因子整体缩放到合约标称的年均容量因子上.
        raw_mean = sum(cf_series.values()) / len(cf_series)
        scale = contract["annual_capacity_factor"] / raw_mean if raw_mean > 0 else 1.0
        for ts in hours:
            cf = min(0.99, cf_series[ts] * scale)
            gen = contract["contracted_volume_mw"] * cf
            # ISO 弃风: 电价为负时发电商被要求减出力, 只在风电上明显.
            node_id = node_id_by_site[contract["site_code"]]
            price = lmp_by_node_ts[node_id][interval_index[ts]]
            curtailed = gen * random.uniform(0.15, 0.45) if price < 0 else 0.0
            ppa_rows.append(
                {
                    "id": ppid,
                    "supply_contract_id": contract_id_by_code[code],
                    "observed_at": ts,
                    "generation_mwh": round(max(0.0, gen - curtailed), 4),
                    "capacity_factor_pct": round(cf * 100.0, 2),
                    "curtailed_by_iso_mwh": round(curtailed, 4),
                }
            )
            ppid += 1

    # ---------- 13. 电费账单 ----------
    invoice_rows = []
    line_rows = []
    inv_id = 1
    line_id = 1
    months = []
    y, m = 2025, 7
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    for s in SITES:
        sc = s["site_code"]
        tariff = next(t for t in TARIFF_SCHEDULES if t["site_code"] == sc)
        iso_code = s["iso_code"]
        demand_history: list[float] = []
        for (yy, mm) in months:
            month_idx = [
                idx
                for idx in range(TOTAL_INTERVALS)
                if intervals[idx].year == yy and intervals[idx].month == mm
            ]
            month_load = [final_load[sc][i] for i in month_idx]
            if not month_idx or max(month_load) <= 0.0:
                continue
            total_mwh = sum(month_load) * INTERVAL_MINUTES / 60.0
            peak_pos = max(range(len(month_idx)), key=lambda k: month_load[k])
            peak_mw = month_load[peak_pos]
            peak_ts = intervals[month_idx[peak_pos]]
            peak_kw = peak_mw * 1000.0

            # 需量棘轮: 计费需量取"当月实测峰值"与"过去 11 个月最高需量 x 棘轮比例"的较大者.
            ratchet_floor = 0.0
            if tariff["demand_ratchet_pct"] > 0 and demand_history:
                ratchet_floor = max(demand_history[-11:]) * tariff["demand_ratchet_pct"] / 100.0
            billing_kw = max(peak_kw, ratchet_floor)
            is_ratchet_binding = 1 if ratchet_floor > peak_kw else 0
            demand_history.append(peak_kw)

            period_start = date(yy, mm, 1)
            period_end = (date(yy, mm, 28) + timedelta(days=8)).replace(day=1) - timedelta(days=1)

            lines = []
            # 能量费: ERCOT 与 MISO 走批发指数与 PPA 混合结算, PJM 走零售固定价.
            if iso_code == "PJM":
                energy_rate = 62.40 if sc == "CMH1" else 64.80
            elif iso_code == "ERCOT":
                energy_rate = random.uniform(31.0, 44.0)
            else:
                energy_rate = random.uniform(38.0, 49.0)
            lines.append(("ENERGY", "Energy charge, blended wholesale index and PPA settlement", total_mwh, "MWh", energy_rate))

            if tariff["demand_charge_usd_per_kw_month"] > 0:
                lines.append(
                    (
                        "DEMAND",
                        f"Distribution demand charge; billing demand set by the 15-minute interval at {peak_ts:%Y-%m-%d %H:%M}",
                        billing_kw,
                        "kW",
                        tariff["demand_charge_usd_per_kw_month"],
                    )
                )
            if tariff["transmission_charge_usd_per_kw_month"] > 0:
                lines.append(
                    (
                        "TRANSMISSION",
                        "Transmission charge allocated by Peak Load Contribution",
                        billing_kw,
                        "kW",
                        tariff["transmission_charge_usd_per_kw_month"],
                    )
                )
            else:
                # ERCOT 的输电费按 4CP 平均需量摊到 12 个月.
                lines.append(
                    (
                        "TRANSMISSION",
                        "ERCOT 4CP transmission charge, allocated on the prior season four coincident peak average demand",
                        billing_kw * 0.34,
                        "kW",
                        ERCOT_4CP_RATE_USD_PER_KW_YEAR / 12.0,
                    )
                )
            if iso_code == "PJM":
                lines.append(
                    ("CAPACITY", "PJM capacity market charge allocated by PLC", billing_kw, "kW", 4.85)
                )
            lines.append(
                ("ANCILLARY", "Ancillary services cost allocation", total_mwh, "MWh", random.uniform(2.1, 3.8))
            )
            lines.append(
                ("RIDER", "Regulatory riders and energy efficiency fund", total_mwh * 1000.0, "kWh", tariff["rider_charge_usd_per_kwh"])
            )

            subtotal = sum(q * r for (_c, _d, q, _u, r) in lines)
            tax_amount = subtotal * 0.0685
            lines.append(("TAX", "State and local utility tax", subtotal, "USD", 0.0685))
            total_amount = subtotal + tax_amount

            invoice_rows.append(
                {
                    "id": inv_id,
                    "invoice_number": f"INV-{sc}-{yy}{mm:02d}",
                    "site_id": site_id_by_code[sc],
                    "billing_period_start": period_start,
                    "billing_period_end": period_end,
                    "total_energy_mwh": round(total_mwh, 3),
                    "metered_peak_demand_kw": round(peak_kw, 2),
                    "billing_demand_kw": round(billing_kw, 2),
                    "peak_interval_start": peak_ts,
                    "is_ratchet_binding": is_ratchet_binding,
                    "total_amount_usd": round(total_amount, 2),
                    "blended_rate_usd_per_kwh": round(total_amount / (total_mwh * 1000.0), 5),
                    "due_date": period_end + timedelta(days=30),
                    "paid_date": period_end + timedelta(days=random.randint(24, 38)),
                }
            )
            for (cat, desc, qty, unit, rate) in lines:
                line_rows.append(
                    {
                        "id": line_id,
                        "energy_invoice_id": inv_id,
                        "charge_category": cat,
                        "description": desc,
                        "quantity": round(qty, 3),
                        "unit": unit,
                        "unit_rate_usd": round(rate, 5),
                        "amount_usd": round(qty * rate, 2),
                    }
                )
                line_id += 1
            inv_id += 1

    return {
        "01_iso_market": pl.DataFrame(iso_rows),
        "02_tariff_schedule": pl.DataFrame(tariff_rows),
        "03_site": pl.DataFrame(site_rows),
        "04_pricing_node": pl.DataFrame(node_rows),
        "05_dr_program": pl.DataFrame(program_rows),
        "06_supply_contract": pl.DataFrame(contract_rows),
        "07_dr_enrollment": pl.DataFrame(enrollment_rows),
        "08_compute_job": pl.DataFrame(job_rows),
        "09_weather_observation": pl.DataFrame(weather_rows),
        "10_lmp_interval_price": pl.DataFrame(lmp_rows),
        "11_ppa_generation_hourly": pl.DataFrame(ppa_rows),
        "12_interval_meter_reading": pl.DataFrame(meter_rows),
        "13_energy_invoice": pl.DataFrame(invoice_rows),
        "14_energy_invoice_line": pl.DataFrame(line_rows),
        "15_dr_event": pl.DataFrame(event_rows),
        "16_dr_event_participation": pl.DataFrame(participation_rows),
        "17_curtailment_action": pl.DataFrame(curtailment_rows),
        "18_curtailed_workload": pl.DataFrame(workload_rows),
    }


# ============================================================
# 第 8 节: TSV 输出
# ============================================================
def generate_all_tsv() -> None:
    """构建整个世界并按拓扑顺序写出 18 个 TSV 文件. 每次运行先清空旧文件."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    tables = build_world()
    for name, df in tables.items():
        df.write_csv(DATA_DIR / f"{name}.tsv", separator="\t")
        print(f"  {name}.tsv  {df.height:>7,} rows")

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
        ("01_iso_market", IsoMarket.__table__),
        ("02_tariff_schedule", TariffSchedule.__table__),
        ("03_site", Site.__table__),
        ("04_pricing_node", PricingNode.__table__),
        ("05_dr_program", DrProgram.__table__),
        ("06_supply_contract", SupplyContract.__table__),
        ("07_dr_enrollment", DrEnrollment.__table__),
        ("08_compute_job", ComputeJob.__table__),
        ("09_weather_observation", WeatherObservation.__table__),
        ("10_lmp_interval_price", LmpIntervalPrice.__table__),
        ("11_ppa_generation_hourly", PpaGenerationHourly.__table__),
        ("12_interval_meter_reading", IntervalMeterReading.__table__),
        ("13_energy_invoice", EnergyInvoice.__table__),
        ("14_energy_invoice_line", EnergyInvoiceLine.__table__),
        ("15_dr_event", DrEvent.__table__),
        ("16_dr_event_participation", DrEventParticipation.__table__),
        ("17_curtailment_action", CurtailmentAction.__table__),
        ("18_curtailed_workload", CurtailedWorkload.__table__),
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
                conn.execute(table.insert(), rows)

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("Starting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("All done!")


if __name__ == "__main__":
    main()
