# -*- coding: utf-8 -*-

"""
CLI: run the multi-round review→fix improvement loop against one or more
0.2.1-layout datasets.

================================================================================
1. 用法
================================================================================

只要编辑下面的 DATASET_NAMES 列表, 把需要打磨的 dataset 名留下, 不想动的注释掉.
然后跑:

    python review_and_fix_loop.py

或者 (推荐, 用 venv 的 python):

    uv run python review_and_fix_loop.py

================================================================================
2. 这个脚本干了什么
================================================================================

每个 dataset 名通过 ``Dataset.from_name(name)`` 解析为绝对路径的 Dataset 实例,
然后构造一个 ``ReviewAndFixLoop`` 实例 (Command Pattern) 并 ``run()``. 每个 task
内部跑 ``max_rounds`` 轮 review→fix 循环, 用两个持久 SDK session 串起来.

具体行为请参见 ``ai_datafaker_pro/review_and_fix_loop.py`` 的 module docstring.

Task 之间是串行执行的, 一个跑完才跑下一个. review+fix 本身已经会同时占用两个
SDK subprocess, 同时跑多个 dataset 容易撞 IO / 撞 SDK rate limit; 串行更稳.

只接受已经升级到 0.2.1 layout 的 dataset (四份 -cn 文件齐全). 如果还是 0.1.1
layout, 先跑 ``upgrade_legacy_datasets.py``. ``ReviewAndFixLoop.__post_init__``
会在构造时把不符合的 dataset 拦下, 不会偷偷开 session.

================================================================================
3. 调参
================================================================================

想统一改模型 / effort / round 数 / 单 session turn 上限, 改下面的常量.
想给单个 dataset 单独设置, 把那一行的 ``ReviewAndFixLoop(...)`` 调用展开, 传不
同的关键字参数即可.

================================================================================
4. 额外项目背景 (EXTRA_CONTEXT)
================================================================================

有些 dataset 是某个更大项目的一部分, 脱离项目上下文就讲不通. 典型症状是评审
把"刻意设计"当成"实现瑕疵"去修 —— 比如把一条故意植入的业务陷阱抹平, 或者为了
"一致性"去改掉一个本来就该矛盾的地方.

在 ``EXTRA_CONTEXT`` 里按 dataset 名加一段文本, 它会被原样注入到 **每一轮**
review 和 fix 的 prompt 里. 没有条目的 dataset 走空字符串, 行为不变.

每轮都重发是有意的: 两个 session 都会累积很长的历史, 而项目定位恰恰是最先
被挤出 context 的那类信息.
"""

from __future__ import annotations

import asyncio

from ai_datafaker_pro.dataset import Dataset
from ai_datafaker_pro.review_and_fix_loop import ReviewAndFixLoop
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_FIX_EFFORT
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_FIX_MAX_TURNS
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_FIX_MODEL
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_MAX_ROUNDS
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_REVIEW_EFFORT
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_REVIEW_MAX_TURNS
from ai_datafaker_pro.review_and_fix_loop import DEFAULT_REVIEW_MODEL


# 要打磨的 dataset 列表. 想跳过哪个就注释掉那一行.
DATASET_NAMES: list[str] = [
    # "gaming_esports_org_commercial_operations_medium",  # 已跑完 (review-01~03, fix-01~02)
    # "gaming_f2p_whale_monetization_medium",  # 已跑完 (review-01~04, fix-01~04, 已翻译)
    # "social_media_music_blanket_licensing_medium",  # 已跑完 (review-01~04, fix-01,02,04, 已翻译)
    # "cloud_provider_gpu_fleet_selfhealing_large",
    "asset_management_factor_research_agent_large",
]


# ==============================================================================
# 每个 dataset 的额外项目背景
# ==============================================================================
#
# 有些 dataset 脱离了它所属的更大项目就讲不通 —— 评审如果不知道这套数据最终要
# 喂给什么, 就会把"刻意设计"当成"实现瑕疵"去修. 这个 dict 里的文本会被原样注入
# 到 **每一轮** review 和 fix 的 prompt 里 (带分隔线的独立块).
#
# 没有条目的 dataset 走空字符串, 行为和以前完全一致.
#
# 写这段文本时的取舍: 只写"改错了会造成实质损失"的那些约束, 不要复述业务文档里
# 已经有的内容. 它每一轮都会重发一遍, 太长会挤占 context.
# ==============================================================================

EXTRA_CONTEXT: dict[str, str] = {
    "asset_management_factor_research_agent_large": """这套数据集不是一个孤立的教学数据集, 它是一个更大项目的燃料与验收标准.

**项目最终要做的东西: 一个因子研究 AI Agent app.**
它没日没夜地挂在时间序列数据库上自主探索因子 —— 自己提假设、自己写复杂的
业务查询 (多层嵌套 / 聚合 / 组合 / 筛选)、自己读结果决定继续深挖还是放弃、
最后自动整理成研究备忘录. 人类只做两件事: **批准** 和 **验证**.
目标是把一个真人研究员一个月的探索量压进一小时.

完整的项目背景 (缘起 / 最终形态 / 人机分工 / 路线图) 留档在:
  dataset/asset_management_factor_research_agent_large/05-asset_management_factor_research_agent_large_industry_research-cn.md
**第一轮请先把这份文件读一遍**, 它解释了下面这些约束为什么存在.
注意: 05 这份文件是项目备忘, **不是** 本次评审的审查对象, 不要去改它.

由此产生的、不可动摇的设计约束 (改掉任何一条都会破坏项目, 请当成 ground truth):

1. **10 个假设的结局是标准答案.** 4 个推进 (ACC_QUALITY / EPS_REV_60D /
   PEAD_SUE / STR_REV_5D) + 6 个否决, 每个否决理由固定. 这套结局是用来给
   未来任何一版 Agent 打分的尺子. 不要改推进/否决的数量或归属.

2. **十条业务陷阱的量级是刻意校准的, 不是 bug.** 例如 look-ahead 让 IC 从
   0.0273 虚增到 0.1096 (4.02 倍), 幸存者偏差让 Q5-Q1 从 8.71% 塌到 3.10%.
   看到"不合理"的数字先想想它是不是某条陷阱, 别顺手抹平.

3. **FCF_MARGIN_TTM 在 factor_validation_run 里是 PASS, 却被 Agent 否决 ——
   这不是矛盾, 这是全数据集最重要的教学点.** 它演示的是"标准验证流水线有盲区:
   污染发生在数据层, 而验证发生在指标层". 千万不要为了"一致性"去把它改成 FAIL.

4. **agent_run / agent_hypothesis / agent_step / agent_finding /
   agent_report_section 这五张表是 app 的数据契约**, 不是装饰. 尤其
   agent_step.sql_text (Agent 真实生成的查询) 与 decision + decision_rationale
   (为什么深挖 / 为什么放弃) —— 人类审批时看的就是这条轨迹. 不要简化.

5. **三道闸是核心机制, 不能弱化**: (a) factor_ic_monthly 与
   factor_validation_run 是 Agent 无权改写的独立裁判; (b) 尝试次数会抬高显著性
   门槛 (agent_hypothesis.applied_t_threshold); (c) 人类终审看轨迹不看结论.

6. **factor_ic_monthly 必须能被分析师从 factor_exposure + daily_bar 自己重算出来**
   (SQL 文档 Q3 就在做这件事, 目前吻合到小数点后三位). 任何改动都不能破坏这个
   可复现性 —— 前瞻收益的口径是月末复权价到下月末复权价的总收益, 不做 beta 调整.

7. **复杂度是 Large, 不要降低.** 约 194.5 万行、899 个交易日、1,200 只美股
   (含 120 只已退市) 是撑起真实横截面统计量的下限.

在以上约束之内, 请照常严格审查: 文档之间的一致性、schema 与代码是否忠实兑现、
SQL 的正确性与教学口吻、数据质量问题. 发现真的错误请照改.
""",
}


# 全局默认参数, 想统一调整就改这里.
MAX_ROUNDS = DEFAULT_MAX_ROUNDS
REVIEW_MODEL = DEFAULT_REVIEW_MODEL
REVIEW_EFFORT = DEFAULT_REVIEW_EFFORT
REVIEW_MAX_TURNS = DEFAULT_REVIEW_MAX_TURNS
FIX_MODEL = DEFAULT_FIX_MODEL
FIX_EFFORT = DEFAULT_FIX_EFFORT
FIX_MAX_TURNS = DEFAULT_FIX_MAX_TURNS


async def main() -> None:
    """Run the review+fix loop against each dataset in DATASET_NAMES, sequentially."""
    for name in DATASET_NAMES:
        dataset = Dataset.from_name(name)
        task = ReviewAndFixLoop(
            dataset=dataset,
            extra_context=EXTRA_CONTEXT.get(name, ""),
            max_rounds=MAX_ROUNDS,
            review_model=REVIEW_MODEL,
            review_effort=REVIEW_EFFORT,
            review_max_turns=REVIEW_MAX_TURNS,
            fix_model=FIX_MODEL,
            fix_effort=FIX_EFFORT,
            fix_max_turns=FIX_MAX_TURNS,
        )
        await task.run()


if __name__ == "__main__":
    asyncio.run(main())
