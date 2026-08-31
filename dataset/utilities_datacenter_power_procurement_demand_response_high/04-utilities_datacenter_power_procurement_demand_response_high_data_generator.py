"""
Utilities - AI Data Center Power Procurement and Demand Response fake data generator
Complexity: High

Business context:
Kestrel Compute, Inc. is a fictional AI compute operator headquartered in Columbus, Ohio,
that builds and operates 6 AI training and inference campuses of its own, spanning the
three power markets ERCOT, PJM, and MISO, with a combined contracted power capacity of
420 MW and roughly 180,000 GPUs deployed. Electricity is the second-largest cost item
after GPU depreciation, at roughly $205M in FY2026. This dataset covers the complete
12 months of FY2026 (2025-07-01 through 2026-06-30) at 15-minute granularity for nodal
electricity prices, 15-minute campus metering, energy invoices, demand response events
and settlements, and curtailed GPU workload detail, supporting the following analyses:

1. Demand response net-benefit inversion: dr_event_participation settlement income is
   positive across the whole year (about $3.28M), but once the opportunity cost of
   interrupted GPU jobs in curtailed_workload is joined in, the Abilene campus's overall
   net benefit turns negative. Looking only at the energy-side report can never reveal
   this gap.
2. DR baseline inflation: a subset of participation records had load artificially raised
   for 3 days before the event, inflating baseline_mw as computed by the "trailing
   10-business-day same-interval average" method, which systematically overstates
   delivered_reduction_mw.
3. PPA shape risk: the Longhorn Ridge wind PPA looks cheap when comparing its monthly
   average price to the market price, but when wind generation is high, ERCOT West nodal
   prices happen to be at their lowest, so once you re-weight by hourly output it is
   actually losing money.
4. Demand charges concealed by the blended rate: energy_invoice.blended_rate_usd_per_kwh
   is a blended unit price that hides the share attributable to the DEMAND line item, and
   also hides the fact that billing demand was determined by a single 15-minute interval.
   The Columbus campus's August 2025 monthly peak came from a 30-minute burn-in test, and
   because of the demand ratchet clause it weighed down the bills for the following 8
   months.
5. A missed 4CP avoidance: ERCOT uses each of the four summer months' own system peak
   hour usage to determine next year's transmission charges. Of the 4 forecasts made
   during the 2025 4CP season, 1 missed (the August forecast was off by about 1 hour),
   and at that hour the campus was running at full load, pulling up the overall 4CP
   average, with the cost showing up in next year's transmission rate.

The traps above are injected through deliberately designed correlated distributions
rather than independent randomness. The corresponding SQL queries live in
03-utilities_datacenter_power_procurement_demand_response_high_sql_queries-cn.md,
which are used to expose these traps.
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

# Fixed reference date, to keep results consistent across runs without depending on
# the system's current time.
# Kestrel's fiscal year runs from July to the following June, so 2026-06-30 is both
# the last day of FY2026 and the end of the whole dataset's one complete fiscal year.
# Anywhere the SQL queries need "today," they use the same literal date.
REFERENCE_DATE = date(2026, 6, 30)

# Time window for metering and pricing: the full 365 days of FY2026, at 15-minute
# granularity = 35,040 intervals.
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
# Section 4: Business Calibration Constants
# ============================================================

# --- ISO markets ---
# The real-time market clearing intervals for the three markets follow real industry
# practice: ERCOT's real-time market settles at 15 minutes (SCED clears every 5 minutes
# but settles at 15 minutes), while PJM and MISO real-time markets clear every 5 minutes.
# This dataset normalizes all three markets to a uniform 15-minute interval for storage,
# so settlement_interval_minutes records each market's real-world convention, not this
# dataset's storage granularity.
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

# --- The 6 campuses ---
# Total capacity of 420 MW, total GPU count of 180,000. workload_type determines the
# shape of the load curve, and also the opportunity cost when curtailed under DR:
# TRAINING campuses run long-cycle pretraining with long checkpoint intervals, so an
# interruption triggers a costly rollback; INFERENCE campuses can shed traffic within
# seconds, at nearly zero loss. This is the physical basis for Trap 1.
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
        # Climate parameters: annual mean dry-bulb temperature (F) and annual amplitude,
        # used to generate weather which in turn drives cooling load.
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
        # This campus went live mid-window, with no load for the first two and a half
        # months. Any metric averaged over 12 months will underestimate ALB1's true
        # run-rate — this is a deliberately left boundary condition for reporting.
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

# --- Load curve shapes ---
# The IT load's share of contracted capacity. TRAINING load is extremely flat (once
# running at capacity it stays there), INFERENCE has a clear intraday peak and trough
# (more users during the day), and MIXED sits in between. This reflects a real
# data-center industry characteristic, and is also why the two ERCOT campuses have
# curtailable capacity to offer for DR.
# The IT load's rated value is only a fraction of contracted capacity; the rest is set
# aside for cooling, distribution losses, and redundancy.
# Liquid cooling frees up more of the contracted capacity for the GPUs themselves,
# which is precisely the main economic benefit of a liquid-cooling retrofit.
# Together with the hard cap below, these two ratios ensure metered_demand_mw never
# exceeds contracted_capacity_mw.
IT_CAPACITY_SHARE_BY_COOLING = {"AIR_COOLED": 0.72, "LIQUID_COOLED": 0.84}

# The hard ceiling on a campus's total load, relative to contracted capacity. Exceeding
# it would trigger distribution-side protection; operations use power capping to throttle
# GPUs back down, so real metering data never shows values beyond this bound.
MAX_LOAD_SHARE_OF_CAPACITY = 0.97

# The base and diurnal_amplitude below are ratios relative to the IT rated load
# (capacity x IT_CAPACITY_SHARE).
LOAD_SHAPE_BY_WORKLOAD = {
    "TRAINING": {"base": 0.94, "diurnal_amplitude": 0.02, "noise_sd": 0.008},
    "MIXED": {"base": 0.80, "diurnal_amplitude": 0.09, "noise_sd": 0.020},
    "INFERENCE": {"base": 0.66, "diurnal_amplitude": 0.15, "noise_sd": 0.030},
}

# Cooling load as a ratio of IT load. The base overhead comes from constant fans and
# pumps, and the temperature-sensitive term rises linearly once wet bulb temperature
# exceeds 55F. Liquid-cooled campuses have only about half the temperature sensitivity
# of air-cooled ones, which is the main selling point of a liquid-cooling retrofit.
COOLING_BASE_RATIO = {"AIR_COOLED": 0.115, "LIQUID_COOLED": 0.062}
COOLING_TEMP_SENSITIVITY = {"AIR_COOLED": 0.0068, "LIQUID_COOLED": 0.0031}
COOLING_WETBULB_THRESHOLD_F = 55.0

# --- Pricing nodes ---
# base_lmp is each node's annual average base price (USD/MWh), roughly reflecting real
# market levels: ERCOT West is nearly always the cheapest year-round due to abundant
# wind, while PJM's AEP Ohio region is the most expensive because of heavy load and
# transmission constraints.
# wind_suppression is "how many USD/MWh the nodal price is pushed down for each unit
# of wind output above normal," strongest at ERCOT West. Trap 3 (PPA shape risk) is
# driven entirely by this coefficient.
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

# Price range for scarcity-pricing intervals. ERCOT has no capacity market, so it relies
# entirely on this kind of spike pricing to let generators recover their costs; in real
# history, individual 15-minute intervals have hit the system cap of $5,000/MWh.
SCARCITY_PRICE_RANGE = (620.0, 4800.0)
SCARCITY_FLAG_THRESHOLD = 500.0

# --- Tariff schedules ---
# demand_charge_usd_per_kw_month is the core of Trap 4. ERCOT's large industrial
# transmission charges run through 4CP, so there is no regular demand charge (recorded
# as 0); PJM and MISO both have distribution demand charges, with PJM the highest.
# demand_ratchet_pct is the demand ratchet: the current month's billed demand cannot
# fall below this percentage of the highest demand over the trailing 11 months. This
# clause is what lets a single 30-minute peak drag down costs for an entire year — the
# real teeth of Trap 4.
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

# ERCOT 4CP transmission rate (USD/kW-year). This number multiplied by the 4CP average
# demand gives next year's transmission charge — the conversion factor for Trap 5. Real
# Oncor industrial rates fall in the $50 to $75/kW-year range.
ERCOT_4CP_RATE_USD_PER_KW_YEAR = 58.0

# --- Supply contracts ---
# Three variable-generation PPAs (wind and solar) generate hourly output curves; the
# rest are fixed-price retail contracts or wholesale index exposure.
# Longhorn Ridge is the protagonist of Trap 3: at a $28.50 strike price it looks cheaper
# than ERCOT West's annual average price, but its generation is concentrated in the
# hours when the price is lowest.
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

# --- Demand response programs ---
# baseline_method is the entry point for Trap 2. AVG_10_BUSINESS_DAYS is the most common
# DR baseline algorithm in North America (the average load over the same time period on
# the 10 business days before the event), and its known weakness is that it can be gamed
# by raising load before the event to inflate the baseline. FIRM_SERVICE_LEVEL uses a
# fixed, contractually agreed load level as the baseline, and is immune to this kind
# of manipulation.
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

# Enrolled committed curtailable capacity (MW) for each (program, site) pair. TRAINING
# campuses can free up the largest curtailment volume, because whole batches of training
# jobs can be shut down at once; INFERENCE campuses must keep serving online, so their
# commitments are small.
# Commitments generally amount to only 8% to 12% of a campus's capacity. AI data centers
# do not dare commit to deep curtailment the way traditional industrial loads do, because
# the opportunity cost of compute far exceeds the cost of electricity. The one exception
# is 4CP avoidance: it only happens for a few hours a year, but the curtailment is
# aggressive, because avoiding it just once saves a quarter of an entire year's
# transmission charges.
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
    ("ERCOT-ERS-10", "CID1", 0.0),  # Placeholder enrollment, exited mid-FY2026, is_active = 0
]

# Number of events triggered per program during FY2026. ERCOT's summer being the busiest
# season is a real-world characteristic (both 2023 and 2024 saw ERCOT issue consecutive
# conservation operations notices in August).
DR_EVENT_COUNTS = {
    "ERCOT-ERS-10": 14,
    "ERCOT-CLR-RRS": 9,
    "ERCOT-4CP-AVOID": 5,
    "PJM-ELRP": 11,
    "PJM-CP": 6,
    "MISO-LMR": 13,
}

# --- Trap 1: DR net-benefit inversion ---
# Internal opportunity cost of GPU compute (USD/GPU-hour), broken out by job type. This
# number represents "the revenue this hour of GPU would have confirmed if it hadn't been
# interrupted," as provided by the commercial team based on contract tier.
# RESERVED long-term customers carry the highest unit price, since an interruption also
# incurs an additional SLA credit payout.
GPU_OPPORTUNITY_COST_USD_PER_HOUR = {
    "PRETRAINING": 3.15,
    "FINETUNING": 2.70,
    "INFERENCE_BATCH": 1.85,
    "INFERENCE_SERVING": 2.40,
    "RESEARCH": 1.20,
}

# Checkpoint interval (minutes). Pretraining jobs have expensive checkpoints (writing
# hundreds of GB of optimizer state to storage), so the interval is stretched out; when
# interrupted, on average half an interval's worth of computation must be rolled back.
# This is the direct reason the Abilene campus's DR opportunity cost is so much higher
# than other campuses.
CHECKPOINT_INTERVAL_MINUTES = {
    "PRETRAINING": 300,
    "FINETUNING": 90,
    "INFERENCE_BATCH": 20,
    "INFERENCE_SERVING": 0,
    "RESEARCH": 120,
}

# Job-type mix per campus. ABI1 is almost entirely long-cycle pretraining, CMH1 is
# almost entirely online inference. This mix directly determines the direction of
# Trap 1: curtailing the same 1 MW costs several times more at ABI1 than at CMH1.
JOB_TYPE_MIX_BY_SITE = {
    "ABI1": {"PRETRAINING": 0.72, "FINETUNING": 0.16, "RESEARCH": 0.08, "INFERENCE_BATCH": 0.04},
    "CID1": {"PRETRAINING": 0.58, "FINETUNING": 0.24, "RESEARCH": 0.12, "INFERENCE_BATCH": 0.06},
    "TPL1": {"PRETRAINING": 0.26, "FINETUNING": 0.30, "INFERENCE_BATCH": 0.24, "INFERENCE_SERVING": 0.14, "RESEARCH": 0.06},
    "ALB1": {"PRETRAINING": 0.18, "FINETUNING": 0.26, "INFERENCE_BATCH": 0.28, "INFERENCE_SERVING": 0.22, "RESEARCH": 0.06},
    "FAR1": {"PRETRAINING": 0.20, "FINETUNING": 0.28, "INFERENCE_BATCH": 0.30, "INFERENCE_SERVING": 0.16, "RESEARCH": 0.06},
    "CMH1": {"INFERENCE_SERVING": 0.62, "INFERENCE_BATCH": 0.24, "FINETUNING": 0.10, "RESEARCH": 0.04},
}

# Distribution of customer contract tiers. RESERVED customers must be paid an SLA credit
# when interrupted; SPOT customers' contracts explicitly allow preemption.
CONTRACT_TIER_WEIGHTS = {"RESERVED": 0.52, "ON_DEMAND": 0.31, "SPOT": 0.17}
SLA_CREDIT_USD_PER_LOST_GPU_HOUR = {"RESERVED": 0.95, "ON_DEMAND": 0.35, "SPOT": 0.0}

# --- Trap 2: DR baseline inflation ---
# Flagged participation records have their load raised by this ratio for the 3 days
# before the event, thereby inflating the AVG_10_BUSINESS_DAYS baseline along with it.
# Only programs using AVG_10_BUSINESS_DAYS are vulnerable; FIRM_SERVICE_LEVEL and
# METER_BEFORE_AFTER are naturally immune.
BASELINE_INFLATION_RATIO_RANGE = (1.085, 1.155)
BASELINE_INFLATION_LOOKBACK_DAYS = 3
# Inflated events are concentrated at TPL1 and CMH1. A fixed selection share keeps
# the result reproducible.
BASELINE_INFLATION_SITE_CODES = ["TPL1", "CMH1"]
BASELINE_INFLATION_EVENT_SHARE = 0.80
# Ceiling on the inflated total load, relative to contracted capacity. Set lower than
# MAX_LOAD_SHARE_OF_CAPACITY, to ensure inflated intervals don't hit the power-capping
# line and produce a batch of identical readings.
BASELINE_INFLATION_CEILING_SHARE = 0.88

# --- Trap 4: demand charges ---
# The Columbus campus ran a full-load GB200 rack burn-in test on the afternoon of
# 2025-08-14, lasting only 30 minutes, but it happened to set that month's 15-minute
# demand peak. Because of the 85% demand ratchet clause, this peak served as the bill's
# floor for the following 8 months (the ratchet lookback window is 11 months, but only
# 8 months are actually inflated by it).
BURN_IN_TEST_SITE_CODE = "CMH1"
BURN_IN_TEST_START = datetime(2025, 8, 14, 15, 30, 0)
BURN_IN_TEST_INTERVALS = 2  # 30 minutes
BURN_IN_TEST_EXTRA_MW = 19.0

# --- Trap 5: 4CP avoidance ---
# ERCOT's 4CP is the single highest-system-load 15-minute interval in each month from
# June through September. Your average usage in those 4 intervals determines your
# transmission charges for the following year. During the 2025 4CP season, Kestrel got
# 3 out of 4 forecasts right; the August forecast was off by about 1 hour, and at the
# actual peak moment the campus was still running at full load.
FOUR_CP_MONTHS = [6, 7, 8, 9]
# (event year and month, whether the forecast hit, forecast offset in minutes). The June
# event predates the metering data window, so only the ISO settlement-side record is
# kept, with no corresponding metering or curtailment detail.
FOUR_CP_EVENTS = [
    {"year": 2025, "month": 6, "hit": True, "offset_minutes": 15, "in_window": False},
    {"year": 2025, "month": 7, "hit": True, "offset_minutes": 30, "in_window": True},
    {"year": 2025, "month": 8, "hit": False, "offset_minutes": 75, "in_window": True},
    {"year": 2025, "month": 9, "hit": True, "offset_minutes": 15, "in_window": True},
    {"year": 2026, "month": 6, "hit": True, "offset_minutes": 15, "in_window": True},
]
# Combined load (MW) that the two ERCOT campuses could squeeze down to on a successful
# hit; on a miss it is essentially full load.
FOUR_CP_SUCCESS_DEMAND_MW = (18.0, 26.0)

# --- Economic curtailment ---
# Unrelated to any DR event, this is a purely voluntary shutdown because real-time
# prices are too high to make running the job worthwhile. Only happens at ERCOT, since
# only ERCOT's price volatility is large enough to make this worthwhile.
ECONOMIC_CURTAILMENT_COUNT = 33
ECONOMIC_CURTAILMENT_PRICE_THRESHOLD = 240.0

# --- Jobs and customers ---
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
# Section 5: SQLAlchemy ORM Models
# ============================================================
# Time-series tables have composite indexes on (entity, time). A 200,000-row table with
# only a primary key would force any query that slices by site or node and then filters
# by time into a full table scan, making most analyses in the SQL query document too
# slow to be usable.
class Base(DeclarativeBase):
    """Base class for all ORM models."""


class IsoMarket(Base):
    """An Independent System Operator (ISO). Kestrel's campuses are spread across the
    three markets ERCOT, PJM, and MISO."""

    __tablename__ = "iso_market"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    settlement_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    transmission_cost_method: Mapped[str] = mapped_column(String(20), nullable=False)
    has_capacity_market: Mapped[int] = mapped_column(Integer, nullable=False)
    region_description: Mapped[str] = mapped_column(String(400), nullable=False)


class TariffSchedule(Base):
    """The local utility's large-industrial-customer tariff schedule. Determines every
    charge on the bill besides energy."""

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
    """An AI compute campus. The shared parent entity for power contracts, metering,
    billing, and DR enrollment."""

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
    """ISO settlement pricing node. Each campus maps to a settlement point in the
    market, against which real-time prices are settled."""

    __tablename__ = "pricing_node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    node_name: Mapped[str] = mapped_column(String(120), nullable=False)
    iso_market_id: Mapped[int] = mapped_column(ForeignKey("iso_market.id"), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), unique=True, nullable=False)
    zone_name: Mapped[str] = mapped_column(String(30), nullable=False)
    node_type: Mapped[str] = mapped_column(String(30), nullable=False)


class DrProgram(Base):
    """An ISO demand response program. baseline_method determines how curtailment
    volume is calculated, and also whether it can be gamed."""

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
    """A power supply contract. Three types coexist: long-term PPAs, fixed-price
    retail, and wholesale index exposure."""

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
    """A campus's enrollment in a given DR program. The committed curtailment capacity
    determines capacity payments and shortfall penalties."""

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
    """A GPU compute job. checkpoint_interval_minutes determines how much computation
    must be rolled back when interrupted."""

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
    """Hourly weather observation at a campus's location. Wet bulb temperature is the
    main driver of cooling load."""

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
    """15-minute real-time nodal price. system_load_mw is the ISO's total system load
    at the same moment, used to determine 4CP."""

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
    """Actual hourly generation for variable-generation PPAs. The correlation with
    nodal prices is the source of shape risk."""

    __tablename__ = "ppa_generation_hourly"
    __table_args__ = (Index("ix_ppagen_contract_observed", "supply_contract_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supply_contract_id: Mapped[int] = mapped_column(ForeignKey("supply_contract.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    generation_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    capacity_factor_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    curtailed_by_iso_mwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)


class IntervalMeterReading(Base):
    """A campus's 15-minute meter reading. Billing demand, DR baselines, and
    curtailment volume are all derived from this table."""

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
    """Header of a campus's monthly energy invoice. blended_rate is the single unit
    price that spreads every charge across each kWh."""

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
    """An invoice line item. Splits one invoice into charge categories such as ENERGY,
    DEMAND, and TRANSMISSION."""

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
    """A single DR event. 4CP-type events additionally record the predicted peak
    interval and the coincident demand under the ISO settlement basis."""

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
    """A campus's settlement record for a given DR event. The two pre_event averages
    are the check point for baseline inflation."""

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
    """An actual load curtailment action. A null dr_event_id means a purely economic
    curtailment, unrelated to any DR program."""

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
    """A single specific GPU job interrupted by a curtailment action. Opportunity cost
    is computed line by line here."""

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
# Section 6: Helper functions
# ============================================================


def all_intervals() -> list[datetime]:
    """All 35,040 15-minute interval start times in FY2026."""
    step = timedelta(minutes=INTERVAL_MINUTES)
    return [WINDOW_START + step * i for i in range(TOTAL_INTERVALS)]


def all_hours() -> list[datetime]:
    """All 8,760 whole-hour timestamps in FY2026."""
    return [WINDOW_START + timedelta(hours=i) for i in range(WINDOW_DAYS * 24)]


def seasonal_factor(ts: datetime, peak_month: int = 7) -> float:
    """Seasonal term, equal to +1 at peak_month and -1 half a year later. Used for the
    annual cycle of temperature and load."""
    day_of_year = ts.timetuple().tm_yday
    peak_day = (peak_month - 1) * 30.4 + 15
    return math.cos(2 * math.pi * (day_of_year - peak_day) / 365.0)


def diurnal_factor(ts: datetime, peak_hour: float = 16.0) -> float:
    """Intraday term, equal to +1 at peak_hour and -1 twelve hours later."""
    hour = ts.hour + ts.minute / 60.0
    return math.cos(2 * math.pi * (hour - peak_hour) / 24.0)


def is_business_day(d: date) -> bool:
    """Monday through Friday count as business days. The DR baseline's 10-business-day
    window only uses business days."""
    return d.weekday() < 5


def build_weather_series(site: dict) -> dict[datetime, dict[str, float]]:
    """Hourly weather series. Dry bulb temperature = annual cycle + daily cycle + noise;
    wet bulb is derived from dry bulb and humidity."""
    series = {}
    for ts in all_hours():
        dry = (
            site["temp_mean_f"]
            + site["temp_amplitude_f"] * seasonal_factor(ts, peak_month=7)
            + 8.0 * diurnal_factor(ts, peak_hour=15.0)
            + random.gauss(0, 3.2)
        )
        # Humidity is higher in summer; Texas and Midwest summer wet bulb temperature
        # is the real source of stress on the cooling system.
        humidity = max(18.0, min(96.0, 58.0 + 14.0 * seasonal_factor(ts, peak_month=7) + random.gauss(0, 9.0)))
        # Simplified wet bulb approximation: dry bulb minus a difference that shrinks
        # as humidity rises.
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
    """Renewable output capacity factor for each market, at 15-minute granularity.

    For ERCOT, this returns the West Texas wind output curve, and that single series
    drives two things at once: the actual generation of the Longhorn Ridge PPA, and
    the suppression term for the ERCOT West nodal price. The two sharing the same
    underlying series is a physical fact (high wind -> more generation -> marginal
    price pushed down), and it is exactly the reason Trap 3 (PPA shape risk) holds
    together. If two independent random series were used here instead, there would be
    no correlation at all between generation and price, and the trap would not exist.

    In terms of shape, West Texas wind is strongest in spring, weakest in summer, and
    stronger at night than in the afternoon, which is the region's most typical pattern
    and also explains why wind generation is always highest exactly when prices are
    lowest.
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
    """Hourly solar capacity factor. Only produces output during the day, highest at
    midday in summer."""
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
    """ISO total system load (MW), at 15-minute granularity. 4CP determination depends
    entirely on this curve's monthly maximum."""
    scale = {"ERCOT": 62000.0, "PJM": 98000.0, "MISO": 78000.0}[iso_code]
    summer_swing = {"ERCOT": 0.32, "PJM": 0.22, "MISO": 0.20}[iso_code]
    winter_bump = {"ERCOT": 0.06, "PJM": 0.15, "MISO": 0.13}[iso_code]
    series = {}
    for ts in all_intervals():
        season = seasonal_factor(ts, peak_month=7)
        # There is also a secondary winter peak; PJM and MISO show a clearly larger
        # winter peak than ERCOT.
        winter = max(0.0, -season) * winter_bump
        load = scale * (1.0 + summer_swing * max(0.0, season) + winter)
        load *= 1.0 + 0.16 * diurnal_factor(ts, peak_hour=17.0)
        load *= 1.0 + random.gauss(0, 0.022)
        if not is_business_day(ts.date()):
            load *= 0.93
        series[ts] = load
    return series


# ============================================================
# Section 7: World-Building Pipeline
# ============================================================
#
# These tables have real causal dependencies on one another and cannot be randomly
# generated independently, so the entire world is built in a single function, following
# this order:
#
#   1. Static dimensions (markets, tariffs, sites, nodes, DR programs, supply
#      contracts, DR enrollments)
#   2. Weather and renewable output curves
#   3. ISO system load -> nodal prices
#   4. Un-curtailed campus load baselines
#   5. GPU jobs
#   6. DR events (timing determined by system load and price spikes)
#   7. Trap 2: raise load for 3 days before flagged events
#   8. Curtailment actions (DR-triggered + purely economic)
#   9. Interrupted jobs and opportunity cost
#  10. DR settlement (baseline taken from the inflated series, actual taken from the
#      post-curtailment series)
#  11. Final metering series (including Trap 4's burn-in spike)
#  12. Energy invoices and line items
#
# Doing these steps out of order results in self-contradictory data, such as computing
# the baseline after curtailment, or an invoice peak that doesn't match the metering
# table.


def build_world() -> dict[str, pl.DataFrame]:
    """Build the entire dataset in causal order, returning {tsv file base name: DataFrame}."""
    intervals = all_intervals()
    hours = all_hours()
    interval_index = {ts: i for i, ts in enumerate(intervals)}

    # ---------- 1. Static dimensions ----------
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
        # The entry with 0 committed capacity is a historical enrollment that has
        # already exited, flagged with is_active = 0.
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

    # ---------- 2. Weather and renewable output ----------
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

    # ---------- 3. ISO system load and nodal prices ----------
    system_load = {code: build_iso_system_load(code) for code in ("ERCOT", "PJM", "MISO")}
    renewable_cf = {
        code: build_renewable_cf_interval(code) for code in ("ERCOT", "PJM", "MISO")
    }
    # Reference value used when converting load into price pressure; uses a level
    # near each market's annual peak rather than the mean, so load_ratio only exceeds
    # 1 during genuinely tight summer afternoons.
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
            # Load-pressure term: the tighter the system, the more expensive the
            # marginal unit, and the price is convex.
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
            # Scarcity pricing only appears when system load is high and renewable
            # output is low, which is real physical logic, and also ensures that
            # Longhorn Ridge never catches a spike price when it's generating heavily.
            if (
                load_ratio > 1.02
                and cf < mean_cf[iso_code]
                and random.random() < n["spike_probability"] * 25
            ):
                lmp = random.uniform(*SCARCITY_PRICE_RANGE)
                energy_component = lmp - congestion - loss
            # Price floor: ERCOT and MISO commonly see negative prices when wind
            # generation is high.
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

    # ---------- 4. Un-curtailed campus load baselines ----------
    # base_load[site_code] is a list the same length as intervals, in MW.
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
            # New campuses have a ramp-up period after commissioning, climbing
            # linearly to the design load over 60 days.
            ramp_days = (ts.date() - s["commissioned_date"]).days
            ramp = min(1.0, 0.35 + 0.65 * ramp_days / 60.0) if ramp_days < 60 else 1.0
            frac = shape["base"] + shape["diurnal_amplitude"] * diurnal_factor(ts, peak_hour=14.0)
            frac *= 1.0 + random.gauss(0, shape["noise_sd"])
            it_mw = cap * it_share * frac * ramp
            wet = weather_by_site[s["site_code"]][ts.replace(minute=0)]["wet_bulb_temp_f"]
            cool_ratio = cool_base + cool_sens * max(0.0, wet - COOLING_WETBULB_THRESHOLD_F)
            cool_mw = it_mw * cool_ratio
            # Power capping: when total load hits the ceiling, IT and cooling are
            # scaled back proportionally together.
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

    # ---------- 5. GPU jobs ----------
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
            # Job duration and GPU scale are both bucketed by job type. Pretraining
            # is "few, large, and long"; online inference is "many, small, and
            # long-running."
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
            # SPOT tier and RESEARCH / INFERENCE_BATCH type jobs are contractually
            # allowed to be preempted.
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

    # ---------- 6. DR events ----------
    def pick_event_intervals(iso_code: str, count: int, months: list[int], min_gap_days: int) -> list[datetime]:
        """Pick the given number of afternoon intervals with the highest system load
        within the specified months, spaced at least min_gap_days apart."""
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
            # Capacity test events are not real system emergencies, only one or two
            # per year, used to verify curtailment capability.
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

    # 4CP avoidance events. Half-window of 60 minutes: a forecast offset within 60
    # minutes counts as a hit, beyond that it's a miss.
    FOUR_CP_HALF_WINDOW_MINUTES = 60
    for spec in FOUR_CP_EVENTS:
        year, month = spec["year"], spec["month"]
        if spec["in_window"]:
            month_intervals = [ts for ts in intervals if ts.year == year and ts.month == month]
            actual_peak = max(month_intervals, key=lambda t: system_load["ERCOT"][t])
        else:
            # This month predates the metering window, so only keep the timestamp
            # from the ISO's after-the-fact settlement notice.
            actual_peak = datetime(year, month, 24, 17, 0, 0)
        predicted_peak = actual_peak - timedelta(minutes=spec["offset_minutes"])
        start = predicted_peak - timedelta(minutes=FOUR_CP_HALF_WINDOW_MINUTES)
        end = predicted_peak + timedelta(minutes=FOUR_CP_HALF_WINDOW_MINUTES)
        if spec["in_window"] and spec["hit"]:
            coincident = round(random.uniform(*FOUR_CP_SUCCESS_DEMAND_MW), 3)
        elif spec["in_window"]:
            # Missed: at the actual peak moment, the two ERCOT campuses were still
            # running at full load.
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

    # Before inflating anything, take a clean snapshot of the shared campus load
    # series. The inflation step below rewrites base_it / base_cooling in place, so
    # that metered / invoice / AVG_10 baselines all physically see the inflated load —
    # that part stays as-is. But the two purely diagnostic fields
    # pre_event_3day_avg_mw / pre_event_30day_avg_mw should only reflect it on AVG_10
    # participation records that were actually flagged for inflation. Non-AVG_10
    # programs (FIRM_SERVICE_LEVEL / METER_BEFORE_AFTER) must read this clean snapshot
    # even if their 3-day lookback window happens to overlap an AVG_10 event's
    # inflation window at the same campus — otherwise the ratio would leak above 1.03,
    # contradicting the documentation's claim that "the other two baseline methods stay
    # within 1.03." See the inflated parameter of window_avg for details.
    base_it_clean = {sc: list(vals) for sc, vals in base_it.items()}
    base_cooling_clean = {sc: list(vals) for sc, vals in base_cooling.items()}

    # ---------- 7. Trap 2: raise load for 3 days before the event ----------
    # Only programs using the AVG_10_BUSINESS_DAYS baseline are worth doing this for,
    # and it only happens at TPL1 and CMH1, the two campuses with spare adjustable
    # load. What gets raised is IT load (scheduling an extra batch of low-priority
    # batch inference jobs).
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
                # When inflating load, scale smoothly based on remaining headroom,
                # rather than multiplying and then hard-clipping. Hard-clipping would
                # cause a large batch of intervals to land on exactly the same
                # capped value, producing hundreds or thousands of identical readings
                # in the metering data that an auditor would spot as artificial at
                # a glance.
                current = base_it[sc][idx] + base_cooling[sc][idx]
                if current <= 0:
                    continue
                headroom = max(0.0, cap * BASELINE_INFLATION_CEILING_SHARE - current)
                increment = min(current * (ratio - 1.0), headroom * 0.85)
                scale = (current + increment) / current
                base_it[sc][idx] *= scale
                base_cooling[sc][idx] *= scale
            inflated_participation_keys.add((meta["id"], sc))

    # ---------- 8. Curtailment actions ----------
    curtailment_rows = []
    curtailment_meta: list[dict] = []
    cid = 1
    # Cumulative curtailment volume per interval per site, later subtracted from the
    # baseline all at once.
    reduction_by_site: dict[str, dict[int, float]] = {s["site_code"]: {} for s in SITES}

    for meta in event_meta:
        prog = program_by_code[meta["program_code"]]
        for pc, sc, mw in DR_ENROLLMENTS:
            if pc != meta["program_code"] or mw <= 0:
                continue
            if site_by_code[sc]["commissioned_date"] > meta["start"].date():
                continue
            # Actual delivered curtailment fluctuates around the committed amount,
            # occasionally falling short. 4CP is done proactively, so it has the
            # highest achievement rate.
            if meta["is_4cp"]:
                achieved = mw * random.uniform(0.96, 1.02)
            else:
                achieved = mw * random.uniform(0.82, 1.08)
            start_idx = interval_index[meta["start"]]
            n_int = meta["duration_h"] * 4
            idxs = [start_idx + j for j in range(n_int) if start_idx + j < TOTAL_INTERVALS]
            for idx in idxs:
                # Curtailment cannot exceed the actual load at the time.
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

    # Purely economic curtailment: voluntary shutdown when real-time prices exceed a
    # threshold, unrelated to any DR program.
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

    # ---------- 9. Interrupted jobs ----------
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
        # The scheduler prioritizes preempting interruptible jobs, but the
        # interruptible capacity is often not enough, and the rest has to come out of
        # long-cycle training jobs. This is exactly the mechanism behind runaway DR
        # costs at training-heavy campuses.
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
            # The interruption occurs at a random point between two checkpoints,
            # rolling back half an interval on average.
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

    # ---------- 10. Final metering series ----------
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
                # Curtailment actions turn off GPUs first, and cooling load drops
                # proportionally with them.
                share = max(0.0, 1.0 - cut / (it_mw + cool_mw))
                it_mw *= share
                cool_mw *= share
            it_out.append(it_mw)
            cool_out.append(cool_mw)
            tot_out.append(it_mw + cool_mw)
        final_it[sc] = it_out
        final_cool[sc] = cool_out
        final_load[sc] = tot_out

    # Trap 4: the Columbus campus's full-load burn-in test, only 30 minutes, yet it
    # set that month's demand peak.
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

    # ---------- 11. DR settlement ----------
    def business_day_baseline(site_code: str, event_start: datetime, duration_h: int) -> float:
        """AVG_10_BUSINESS_DAYS baseline: average un-curtailed load over the same time
        period on the 10 business days before the event."""
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
        """FIRM_SERVICE_LEVEL baseline: average un-curtailed load over the same time
        period across the 30 calendar days before the event.

        The key difference from AVG_10_BUSINESS_DAYS is a much longer window. Even if
        load is artificially raised for the 3 days before the event, spreading that
        over 30 days only pushes the baseline up by about a percentage point, so this
        type of program is immune to baseline inflation.
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
        """Overall average load in the N days before an event, used to check whether
        the baseline was artificially inflated.

        With inflated=True, reads the inflated site load series; this should only be
        passed True for AVG_10 participation records that were actually flagged for
        baseline inflation. All other records must pass False and read the clean,
        pre-inflation snapshot. This way, inflation only shows up in the diagnostics
        of the records that were actually flagged, and does not leak in just because
        this record's lookback window happens to overlap the inflation window of some
        AVG_10 event at the same campus — so the ratio for FIRM / METER programs
        genuinely stays within 1.03.
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
                # Takes the un-curtailed load for the 1 hour before and 1 hour after
                # the event, insensitive to inflated load.
                pre = [total_base(sc, i) for i in range(max(0, start_idx - 4), start_idx)]
                post_start = start_idx + n_int
                post = [
                    total_base(sc, i)
                    for i in range(post_start, min(TOTAL_INTERVALS, post_start + 4))
                ]
                pool = pre + post
                baseline = sum(pool) / len(pool) if pool else 0.0
            else:
                # FIRM_SERVICE_LEVEL: uses the 30-day same-interval average as the
                # contractually agreed reference load.
                baseline = firm_service_baseline(sc, meta["start"], meta["duration_h"])

            delivered = max(0.0, baseline - actual)
            # The ISO caps recognized over-delivery, typically at 2x the committed
            # amount, with anything beyond that not counted toward settlement.
            perf = min(2.0, delivered / mw) if mw > 0 else 0.0
            # Capacity payments spread the full-year monthly capacity fee across the
            # events that actually occurred that year.
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
            # Only for AVG_10 participation records that were actually flagged for
            # inflation do the two diagnostic fields read the inflated series; all
            # other records read the clean snapshot, so inflation doesn't leak into
            # other baseline methods (see window_avg).
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

    # ---------- 12. PPA hourly output ----------
    ppa_rows = []
    ppid = 1
    # The wind PPA's hourly output is aggregated directly from the same 15-minute
    # series that drives the ERCOT West price.
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
        # Scale the generated capacity factor overall to match the contract's stated
        # annual average capacity factor.
        raw_mean = sum(cf_series.values()) / len(cf_series)
        scale = contract["annual_capacity_factor"] / raw_mean if raw_mean > 0 else 1.0
        for ts in hours:
            cf = min(0.99, cf_series[ts] * scale)
            gen = contract["contracted_volume_mw"] * cf
            # ISO curtailment: generators are asked to reduce output when prices go
            # negative, which is mainly noticeable for wind.
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

    # ---------- 13. Energy invoices ----------
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

            # Demand ratchet: billing demand is the greater of "this month's actual
            # measured peak" and "the trailing 11 months' highest demand x the
            # ratchet percentage."
            ratchet_floor = 0.0
            if tariff["demand_ratchet_pct"] > 0 and demand_history:
                ratchet_floor = max(demand_history[-11:]) * tariff["demand_ratchet_pct"] / 100.0
            billing_kw = max(peak_kw, ratchet_floor)
            is_ratchet_binding = 1 if ratchet_floor > peak_kw else 0
            demand_history.append(peak_kw)

            period_start = date(yy, mm, 1)
            period_end = (date(yy, mm, 28) + timedelta(days=8)).replace(day=1) - timedelta(days=1)

            lines = []
            # Energy charge: ERCOT and MISO settle through a mix of wholesale index
            # and PPA, PJM uses a retail fixed price.
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
                # ERCOT's transmission charge is spread across 12 months based on the
                # 4CP average demand.
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
# Section 8: TSV Output
# ============================================================
def generate_all_tsv() -> None:
    """Build the entire dataset and write out 18 TSV files in topological order.
    Clears old files at the start of every run."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    tables = build_world()
    for name, df in tables.items():
        df.write_csv(DATA_DIR / f"{name}.tsv", separator="\t")
        print(f"  {name}.tsv  {df.height:>7,} rows")

    print(f"Generated all TSV files in {DATA_DIR}")


# ============================================================
# Section 9: SQLite Build
# ============================================================
def create_sqlite_database() -> None:
    """Use the Core API's bulk loader to load the TSVs into SQLite. One transaction,
    one loop."""
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
