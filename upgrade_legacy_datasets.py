# -*- coding: utf-8 -*-

"""
CLI: upgrade legacy (0.1.1 layout) datasets to the current 0.2.1 spec.

================================================================================
1. 用法
================================================================================

只要编辑下面的 DATASET_NAMES 列表, 把需要升级的 dataset 名留下, 不想动的注释掉.
然后跑:

    python upgrade_legacy_datasets.py

或者 (推荐, 用 venv 的 python):

    uv run python upgrade_legacy_datasets.py

================================================================================
2. 这个脚本干了什么
================================================================================

每个 dataset 名通过 ``Dataset.from_name(name)`` 解析为绝对路径的 Dataset 实例,
然后构造一个 ``UpgradeTask`` 实例 (Command Pattern) 并 ``run()``. 每个 task 就
是一个独立的升级生命周期, 内部细节参见
``ai_datafaker_pro/upgrade_task.py`` 的 module docstring.

Task 之间是串行执行的, 一个跑完才跑下一个. 因为升级要跑 generator, 同时跑多个
有可能撞磁盘 IO; 串行更稳.

================================================================================
3. 调参
================================================================================

如果想统一改模型 / effort / 单 session turn 上限, 改下面的 MODEL / EFFORT /
MAX_TURNS 常量. 想给单个 dataset 单独设置, 把那一行的 ``UpgradeTask(...)`` 调
用展开, 传不同的关键字参数即可.
"""

from __future__ import annotations

import asyncio

from ai_datafaker_pro.dataset import Dataset
from ai_datafaker_pro.upgrade_task import UpgradeTask
from ai_datafaker_pro.upgrade_task import DEFAULT_EFFORT
from ai_datafaker_pro.upgrade_task import DEFAULT_MAX_TURNS
from ai_datafaker_pro.upgrade_task import DEFAULT_MODEL


# 要升级的 dataset 列表. 想跳过哪个就注释掉那一行.
DATASET_NAMES: list[str] = [
    "b2b_saas_demand_generation_high",
    "cloud_provider_customer_success_medium",
    "cybersecurity_ai_compliance_audit_medium",
    "digital_lending_credit_approval_assistant_high",
    "ecommerce_ai_customer_service_high",
    "ecommerce_subscription_growth_marketing_high",
    "fintech_real_time_fraud_aml_platform_high",
    "fintech_smb_lending_pipeline_medium",
    "health_insurance_prior_authorization_high",
    "healthcare_obstetrics_ward_scheduling_medium",
    "media_podcast_ad_economics_high",
    "medical_devices_orthopedic_implant_tracking_high",
    "property_casualty_commercial_underwriting_high",
    "real_estate_brokerage_market_intelligence_raw_data_high",
    "search_ads_360_agent_large",
    "search_advertising_attribution_agent_large",
]


# 全局默认参数, 想统一调整就改这里.
MODEL = DEFAULT_MODEL
EFFORT = DEFAULT_EFFORT
MAX_TURNS = DEFAULT_MAX_TURNS


async def main() -> None:
    """Run the upgrade pipeline against each dataset in DATASET_NAMES, sequentially."""
    for name in DATASET_NAMES:
        dataset = Dataset.from_name(name)
        task = UpgradeTask(
            dataset=dataset,
            model=MODEL,
            effort=EFFORT,
            max_turns=MAX_TURNS,
        )
        await task.run()


if __name__ == "__main__":
    asyncio.run(main())
