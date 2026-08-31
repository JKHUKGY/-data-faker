"""
Asset Management 因子研究 AI Agent 假数据生成器
复杂度: Large (29 张表, 约 194.5 万行)

业务背景:
Tessellate Capital Management (TCM) 是一家总部位于波士顿的中型系统化资产管理公司,
约 250 名员工, AUM 约 320 亿美元, 以多资产系统化策略为主 (美股为核心, 外加一个
跨资产 sleeve). 本数据集刻画 TCM 内部一个叫 Atlas 的 AI 因子研究 Agent:
它在 2026 年 7 月 6 日上午用约 36 分钟跑完了一轮完整的因子探索 (RUN-2026-Q2-001),
自主提出 10 个研究假设, 走了 94 步探索 (其中 84 步真实生成并执行了业务 SQL),
最终把其中 4 个假设推进到 Model Validation 组做正式验证, 另外 6 个被否决.
(墙钟分钟数、步数、token 与成本的权威值以 agent_run 表为准, 生成器跑完会打印.)

数据集支持以下分析:
1. 因子有效性检验 (RankIC / ICIR / IC t-stat / 分层单调性 / 半衰期)
2. AI Agent 的探索轨迹复盘 (假设 -> 查询 -> 指标 -> 继续或放弃的决策链)
3. 六类因子研究失败模式的识别与排除
4. 协方差估计方法在不同 market regime 下的可靠性对比
5. 组合约束对 alpha 的侵蚀程度 (约束前后 IR 对比)
6. 收益与风险归因 (factor / sector 两个维度)

刻意植入的业务陷阱 (下面每个数字都是实测值, 与三份文档逐条对齐):

T1 Look-ahead bias (H03 PEAD_SUE):
   fundamental_report.publish_date 比 fiscal_period_end 晚 19-41 天. 股价对盈余
   意外的反应 (公告跳空 + 随后漂移) 发生在 publish_date 之后. 从 fundamental_report
   重建 SUE 因子: 按 publish_date <= obs_date 过滤得到 RankIC 0.0273;
   按 fiscal_period_end <= obs_date 过滤得到 0.1101, 虚增 4.03 倍.
   factor_exposure 里存的是正确口径且带公告后衰减的版本, RankIC 0.0341.

T2 Survivorship bias (H09 DIV_GROWTH_5Y):
   120 只已退市标的在退市前 12 个月被注入每月 -7.5% 的死亡螺旋 (这是输入常量;
   叠加市场 drift 与月度总收益 -75% 的下限截断之后, 落地的实测值约 -5.4%/月),
   且它们的 DIV_GROWTH_5Y z-score 系统性偏高 (均值 +1.2). 只取 delisted_date
   IS NULL 时 Q5-Q1 年化 +8.71%; 纳入退市标的后降到 +3.10%, 差 5.6pp.

T3 多重检验 (H08 SEARCH_TREND):
   RankIC 0.0158, IC t-stat 2.32, 能通过传统 t > 2.0 门槛, 但它是本轮的
   第 8 次尝试, Harvey-Liu-Zhu 式调整后门槛为 t > 3.36, 不通过.

T4 成本吞噬 (H04 STR_REV_5D):
   年化双边换手 22.8 倍, 成本 586 bps/年, 把毛 IR 1.67 削到净 IR 0.83,
   吃掉约 50% 的 alpha. 对照组 H01 ACC_QUALITY 换手仅 5.5 倍, 毛 1.29 / 净 1.07.

T5 Regime 依赖 (H07 NEWS_SENT_7D):
   全样本 RankIC 0.0140 看似可用, 但按 regime 拆分: LOW_VOL_BULL 下 +0.0523,
   HIGH_VOL_STRESS 下 -0.0459, 符号翻转.

T6 伪新因子 (H05 VOL_SKEW_ADJ):
   构造上等于 0.82 x VOL_LOW_60D + 0.57 x 独立噪声, 与生产因子库的最大月度 IC
   序列相关系数 0.93, 远超 0.75 的红线. 单看 ICIR 0.38 尚可, 增量贡献接近零.

T7 容量陷阱 (H06 MICRO_VALUE):
   US_ALL 上 RankIC 0.0316 (t = 4.58, 看着很强), 但拆开看:
   US_MICRO_250 上 0.0746, US_LARGE_500 上仅 0.0111.
   按 5% ADV 参与度、21 个交易日建仓折算, 微盘端容量只有 2.14 亿美元.

T8 数据修订偏差 (H10 FCF_MARGIN_TTM):
   约 26% 的公司会修订财报, version=2 的行占全表 19.3%, 修订方向与后续收益同号.
   用仓库默认的最新版计算 RankIC 0.0296; 用 version=1 的原始版 (真 PIT) 只有 0.0071.
   注意: 这条陷阱在标准验证统计量里完全看不出来 —— factor_validation_run 给它的
   结论是 PASS (t = 6.39, 净 IR 2.62), 只有主动改写 as-of 口径重算才能发现.

T9 协方差 regime 失配 (covariance_estimate):
   method='sample' 在 HIGH_VOL_STRESS 起始两个月的 vol_bias_ratio (实际/预测)
   为 1.93, 条件数约 47,000 (T/N = 0.5 导致奇异);
   method='ledoit_wolf' 同期 1.35, 条件数约 216.

T10 约束侵蚀 alpha (backtest_run x constraint_set):
   同一复合信号在 UNCONSTRAINED 下净 IR 1.32, SECTOR_NEUTRAL 1.05,
   LIQUIDITY_TIGHT 0.78, FULL_PRODUCTION 0.61 —— 削掉 53.8%.

上述陷阱通过有意设计的相关分布注入. 对应的 SQL 查询位于
03-asset_management_factor_research_agent_large_sql_queries-cn.md, 用以暴露这些陷阱.
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
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ---------------------------------------------------------------------------
# Section 3. 配置常量
# ---------------------------------------------------------------------------

DATASET_NAME = "asset_management_factor_research_agent_large"
OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / f"{DATASET_NAME}.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期 '2026-06-30'.
REFERENCE_DATE = date(2026, 6, 30)

# 数据窗口: 43 个月末观测 (2022-12 至 2026-06), 可算出 42 个月度 IC. 日频. 因子研究要求足够长的月度 IC 序列才能算出可信的 t 统计量,
# 42 个月是行业里做单因子检验的下限量级 (再短则 t-stat 不可信).
HISTORY_START = date(2022, 12, 1)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Section 4. 业务校准常量
# ---------------------------------------------------------------------------

# 资产池规模. 1,080 只在市 + 120 只已退市 = 1,200 只美股, 外加 40 个跨资产 ETF 代理.
# 横截面 1,000+ 只是做 RankIC 的舒适区: 单期 IC 的抽样标准差约 1/sqrt(N) ~ 0.030,
# 低于这个规模, 月度 IC 噪声会盖过真实信号.
N_EQUITY_ACTIVE = 1080
N_EQUITY_DELISTED = 120
N_CROSS_ASSET = 40

# 单只股票的月度特异性波动率. 年化约 29% (0.085 * sqrt(12)), 与美股中小盘的实际
# 水平吻合. 所有因子的 IC 目标都是相对这个噪声水平校准出来的.
MONTHLY_IDIO_VOL = 0.085

# 因子的"真实 IC 载荷" w_k. 在 r = w*z + eps (eps ~ N(0,1)) 的模型下,
# Pearson IC = w / sqrt(w^2 + 1) ~ w, RankIC 约为 Pearson IC 的 0.98 倍.
# 因此这里的数值可以直接读作目标 RankIC.
FACTOR_TRUE_IC = {
    "ACC_QUALITY": 0.042,      # H01 真信号, 低换手, 会被推进验证
    "EPS_REV_60D": 0.047,      # H02 真信号, 但换手偏高, 成本后仍存活
    "PEAD_SUE": 0.032,         # H03 真信号, 同时是 look-ahead 教学案例
    "STR_REV_5D": 0.047,       # H04 真信号, 但年化双边换手 2,280%, 成本吃掉约一半 alpha
    "VOL_SKEW_ADJ": 0.000,     # H05 伪新因子, IC 全部来自 VOL_LOW_60D 的溢出
    "MICRO_VALUE": 0.000,      # H06 容量陷阱, IC 由 SMALL_CAP_IC_BOOST 单独注入
    "NEWS_SENT_7D": 0.000,     # H07 regime 依赖, IC 由 REGIME_IC_FLIP 单独注入
    "SEARCH_TREND": 0.022,     # H08 多重检验, t ~ 2.3, 过不了调整后门槛
    "DIV_GROWTH_5Y": 0.031,    # H09 幸存者偏差, 只在存续标的上成立
    "FCF_MARGIN_TTM": 0.000,   # H10 修订偏差, PIT 口径由 RESTATEMENT_PIT_IC 注入,
                               #     修订版的虚高由 RESTATEMENT_LEAK 注入
    "VAL_EP": 0.024,           # 生产库存量因子: 价值
    "MOM_12_1": 0.028,         # 生产库存量因子: 动量
    "QUA_ROE": 0.037,          # 生产库存量因子: 质量
    "VOL_LOW_60D": 0.022,      # 生产库存量因子: 低波
    "SIZ_LOG_MCAP": 0.014,     # 生产库存量因子: 规模 (更像风险因子而非 alpha)
    "LIQ_AMIHUD": 0.017,       # 生产库存量因子: 流动性
}

# 真实 IC 的月度波动幅度. 现实里因子的预测力远不是常数: 美股因子的月度 IC 序列
# 标准差通常在 0.08-0.12, 而均值只有 0.02-0.04, 所以 ICIR 落在 0.3-0.5.
# 这个系数偏小的话, IC_std 只剩横截面抽样噪声 (~1/sqrt(N) = 0.029), t 统计量会
# 虚高到 8 以上 —— 那种数字在真实因子研究里根本不会出现.
IC_TIME_VARIATION = 1.80
# 盈余驱动的收益 (PEAD) 更接近机械反应, 月度波动比纯横截面因子小一些.
PEAD_IC_TIME_VARIATION = 1.50

# H06 容量陷阱: MICRO_VALUE 的效果几乎全部集中在最小市值五分位.
# 全池加权后实测 IC 约 0.032, 但最小组约 0.075 / 最大组接近 0, 差出一个数量级 ——
# 一个"全市场有效"的因子, 实际上只在最小的那 250 只票上有效.
SMALL_CAP_IC_BOOST = {1: 0.105, 2: 0.012, 3: 0.004, 4: 0.002, 5: 0.001}

# H07 regime 依赖: NEWS_SENT_7D 在低波环境有效, 在高波环境反向.
# 两个 regime 的月份数接近, 因此全样本 IC 被稀释到约 0.014, 看着"还行".
REGIME_IC_FLIP = {
    "LOW_VOL_BULL": 0.062,
    "RECOVERY": 0.030,
    "RISING_RATE": 0.008,
    "HIGH_VOL_STRESS": -0.048,
}

# H10 修订偏差 (T8): 修订版"偷看"了修订时点之后才确定的信息, 于是用仓库默认的
# 最新版算出来的 IC 被抬高到约 0.031; 用 version=1 原始版重算只剩约 0.007.
# 两个常量分工: RESTATEMENT_PIT_IC 决定"真 PIT 口径下这个因子本来有多弱",
# RESTATEMENT_LEAK 决定"修订版能偷看到多少未来收益".
RESTATEMENT_LEAK = 0.085
# 真 PIT 口径下的目标 IC. 取 0.010 是因为它必须"弱到统计上和零没区别", 否则
# 读者会以为 FCF 本来就是个能用的因子, 修订只是锦上添花 —— 那就不是陷阱了.
RESTATEMENT_PIT_IC = 0.010
RESTATEMENT_RATE = 0.26  # 约 26% 的财报事后有修订版, 与美股实际重述率量级一致

# H05 伪新因子: VOL_SKEW_ADJ = 0.82 * VOL_LOW_60D + 0.57 * 独立噪声.
# 归一化后与母因子的暴露度相关系数约 0.93, 月度 IC 序列相关系数实测 0.93,
# 远超 factor_validation_run 的 0.75 红线.
PSEUDO_FACTOR_PARENT = "VOL_LOW_60D"
PSEUDO_FACTOR_LOAD = 0.82
PSEUDO_FACTOR_NOISE = 0.57

# H09 幸存者偏差: 退市标的的 DIV_GROWTH_5Y z-score 系统性偏高 (公司在退市前
# 常靠维持高分红粉饰).
DELISTED_DIVGROWTH_Z_SHIFT = 1.2
# 退市前 12 个月每月注入的死亡螺旋漂移. -0.075 连续 12 个月是累计约 -61%,
# 但它只是"注入项": 月度总收益还要叠加 beta x 市场, 并被 max(1+total, 0.25)
# 截到 -75% 的下限, 所以落地后的实测值约 -5.4%/月.
DELISTED_PRE_DELIST_MONTHLY_DRIFT = -0.075

# T1 look-ahead (H03 PEAD_SUE): 财报公布滞后天数区间. 美股 10-Q 的实际滞后
# 中位数约 35-40 天, 这个滞后正是 look-ahead 陷阱的成因: 季度已经结束, 但
# 市场还没看到数字.
PUBLISH_LAG_DAYS = (19, 41)
# 盈余公告后漂移 (PEAD) 的强度: 公告日之后 1 个月内, 每单位 SUE 带来的超额收益.
PEAD_DRIFT_PER_SUE = 0.016
# 盈余公告当月的跳空反应. 这一段是 look-ahead 口径能"偷"到的主要部分 ——
# 正确口径下公告已经发生, 跳空早就被市场吸收了.
ANNOUNCE_JUMP_PER_SUE = 0.024

# 因子的横截面排名持续性 (月度 AR(1) 系数). 决定换手率:
# rho 越高, 排名越稳, 换手越低. STR_REV_5D 的 rho 接近 0, 是它年化双边换手
# 高达 2,280% (22.8 倍) 的根因.
FACTOR_PERSISTENCE = {
    "ACC_QUALITY": 0.93,       # 会计科目季度才更新一次, 排名极稳
    "EPS_REV_60D": 0.55,       # 分析师修正每月都在变
    "PEAD_SUE": 0.62,          # 与财报季对齐
    "STR_REV_5D": 0.04,        # 5 日反转, 几乎每月重排
    "VOL_SKEW_ADJ": 0.88,
    "MICRO_VALUE": 0.91,
    "NEWS_SENT_7D": 0.35,
    "SEARCH_TREND": 0.48,
    "DIV_GROWTH_5Y": 0.96,
    "FCF_MARGIN_TTM": 0.94,
    "VAL_EP": 0.92,
    "MOM_12_1": 0.78,
    "QUA_ROE": 0.95,
    "VOL_LOW_60D": 0.89,
    "SIZ_LOG_MCAP": 0.99,      # 市值排名几乎不动
    "LIQ_AMIHUD": 0.90,
}

# 交易成本模型. 净收益 = 毛收益 - 换手 x (半价差 + 冲击成本 + 佣金).
# 这三项之和在美股大盘约 8-12 bps 单边, 小盘 25-40 bps, 与卖方 TCA 报告量级一致.
COMMISSION_BPS = 1.0
IMPACT_COEF = 0.55  # 冲击成本 = IMPACT_COEF x spread_bps x sqrt(参与度)

# 市场 regime 划分. 每段的起始月份 (含) 与该 regime 下的市场年化波动率.
# HIGH_VOL_STRESS 段长 8 个月, 保证 regime 拆分后每一侧都有足够样本算 IC.
# 注意 LOW_VOL_BULL 出现两段 (2023-11 起与 2025-12 起). 调用点用
# dict((name, vol) for ...) 建查找表, 同名键只会保留最后一个, 所以两段必须
# 声明同一个波动率, 否则前一段的设定会静默失效. 这个值同时写进
# regime_type.typical_vol_ann, 三处必须一致.
REGIME_SCHEDULE = [
    (date(2023, 1, 1), "RECOVERY", 0.165),
    (date(2023, 11, 1), "LOW_VOL_BULL", 0.121),
    (date(2024, 8, 1), "HIGH_VOL_STRESS", 0.312),
    (date(2025, 4, 1), "RISING_RATE", 0.198),
    (date(2025, 12, 1), "LOW_VOL_BULL", 0.121),
]

# 协方差估计: 研究组合用 top 500 市值, 回看 250 个交易日 -> T/N = 0.5.
# T/N < 1 时样本协方差必然奇异, 这是 shrinkage 存在的全部理由.
COV_LOOKBACK_DAYS = 250
COV_UNIVERSE_N = 500
# 各方法在 HIGH_VOL_STRESS 起始两个月的 vol_bias_ratio (实际波动/预测波动).
# 数值越接近 1 越好. 样本协方差严重低估风险, 收缩类方法明显改善.
COV_STRESS_BIAS = {
    "sample": 1.90,
    "ledoit_wolf": 1.35,
    "oas": 1.31,
    "factor_model": 1.22,
}
COV_NORMAL_BIAS = {
    "sample": 1.06,
    "ledoit_wolf": 1.02,
    "oas": 1.02,
    "factor_model": 1.04,
}
# 条件数 = 最大特征值 / 最小特征值, 衡量矩阵的病态程度. T/N = 0.5 时样本协方差
# 有一半的特征值恰好是 0, 数值上表现为四万量级的条件数 (真实秩亏矩阵的条件数
# 是无穷, 浮点实现里会落在 1e4-1e6); 收缩把最小特征值抬起来, 条件数掉到几百.
# 这两个量级差就是"为什么生产系统禁用 sample 法"的全部依据.
COV_CONDITION_NUMBER = {
    "sample": 42000.0,
    "ledoit_wolf": 210.0,
    "oas": 185.0,
    "factor_model": 96.0,
}
# 收缩强度: 0 = 完全用样本协方差, 1 = 完全用结构化目标. Ledoit-Wolf 与 OAS 在
# T/N = 0.5 这种样本严重不足的情形下, 解析解通常落在 0.35-0.45; factor_model
# 不是"收缩", 而是整体换成结构化估计, 所以记为 1.0 (上限, 不会超过 1 ——
# 大于 1 意味着越过目标继续收缩, 数学上没有意义).
COV_SHRINKAGE_INTENSITY = {
    "sample": 0.00,
    "ledoit_wolf": 0.38,
    "oas": 0.41,
    "factor_model": 1.00,
}

# T10 约束侵蚀: 同一复合信号在四套约束下的净 IR.
# 这组数字是本数据集里"约束不是免费的"这条结论的量化载体.
CONSTRAINT_NET_IR = {
    "UNCONSTRAINED": 1.32,
    "SECTOR_NEUTRAL": 1.05,
    "LIQUIDITY_TIGHT": 0.78,
    "FULL_PRODUCTION": 0.61,
}

# Harvey-Liu-Zhu 多重检验门槛. 第 n 次尝试对应的 t 门槛近似取
# Bonferroni 化的正态分位数, 与论文给出的历史阈值曲线量级一致 (2010 年后约 3.0-3.4).
HLZ_BASE_T = 2.00


def hlz_threshold(trial_index: int) -> float:
    """第 trial_index 次尝试所需的 t 门槛. 尝试越多, 门槛越高."""
    return round(HLZ_BASE_T + 0.62 * math.log(max(trial_index, 1) + 1), 2)


# GICS 风格的 11 个板块与其在美股市值中的大致权重.
SECTOR_DEFS = [
    ("10", "Energy", 0.041),
    ("15", "Materials", 0.024),
    ("20", "Industrials", 0.086),
    ("25", "Consumer Discretionary", 0.104),
    ("30", "Consumer Staples", 0.058),
    ("35", "Health Care", 0.122),
    ("40", "Financials", 0.131),
    ("45", "Information Technology", 0.312),
    ("50", "Communication Services", 0.079),
    ("55", "Utilities", 0.024),
    ("60", "Real Estate", 0.019),
]

# 因子主题, 采用 signal -> factor -> theme 三层结构 (行业通行做法).
# 主题的 economic_rationale 是库里的数据值, 因此和其他数据一样用英文书写.
FACTOR_THEME_DEFS = [
    ("VALUE", "Value", "Cheap assets outperform expensive ones over long horizons"),
    ("GROWTH", "Growth", "Improving earnings dynamics and forward expectations"),
    ("QUALITY", "Quality", "Balance sheet strength and operating efficiency"),
    ("MOMENTUM", "Momentum", "Price and fundamental trends persist"),
    ("TECHNICAL", "Technical", "Short horizon price and trading behaviour"),
    ("LOW_VOL", "Low Volatility", "Low risk assets win on a risk adjusted basis"),
    ("LIQUIDITY", "Liquidity", "Illiquidity demands a return premium"),
    ("CARRY", "Carry", "Return earned simply from holding the asset"),
    ("SENTIMENT", "Sentiment & Alt Data", "Information outside traditional financial statements"),
]

# 16 个因子的完整定义.
# 前 6 个是 TCM 生产因子库里的存量因子 (status='production'), 用作新因子的对照基线;
# 后 10 个是 Atlas Agent 在 RUN-2026-Q2-001 里提出的候选因子 (status='candidate').
# complexity_score 是表达式里的操作符个数, feature_count 是用到的原始字段数.
# 这两个字段用于复现 AlphaAgent 式的"复杂度控制"正则 —— 表达式越复杂越容易过拟合.
FACTOR_DEFS = [
    # 字段顺序: 代码, 名称, 主题, 状态, as-of 约定, 复杂度, 用到的原始字段数, 提出者
    ("VAL_EP", "Earnings Yield (TTM E/P)", "VALUE", "production", "publish_date", 3, 2, "human"),
    ("MOM_12_1", "12-1 Month Price Momentum", "MOMENTUM", "production", "trade_date", 4, 1, "human"),
    ("QUA_ROE", "Return on Equity (TTM)", "QUALITY", "production", "publish_date", 3, 2, "human"),
    ("VOL_LOW_60D", "Inverse 60-Day Realized Volatility", "LOW_VOL", "production", "trade_date", 4, 1, "human"),
    ("SIZ_LOG_MCAP", "Inverse Log Market Cap", "LIQUIDITY", "production", "trade_date", 3, 1, "human"),
    ("LIQ_AMIHUD", "Amihud Illiquidity (20D)", "LIQUIDITY", "production", "trade_date", 5, 2, "human"),
    ("ACC_QUALITY", "Accrual Quality (CFO minus Net Income)", "QUALITY", "candidate", "publish_date", 6, 3, "agent"),
    ("EPS_REV_60D", "60-Day Consensus EPS Revision", "GROWTH", "candidate", "publish_date", 5, 3, "agent"),
    ("PEAD_SUE", "Post-Earnings Announcement Drift (SUE)", "GROWTH", "candidate", "publish_date", 7, 4, "agent"),
    ("STR_REV_5D", "5-Day Short-Term Reversal", "TECHNICAL", "candidate", "trade_date", 3, 1, "agent"),
    ("VOL_SKEW_ADJ", "Skew-Adjusted Realized Volatility", "LOW_VOL", "candidate", "trade_date", 9, 2, "agent"),
    ("MICRO_VALUE", "Micro-Cap Composite Value", "VALUE", "candidate", "publish_date", 8, 4, "agent"),
    ("NEWS_SENT_7D", "7-Day News Sentiment Momentum", "SENTIMENT", "candidate", "publish_date", 6, 2, "agent"),
    ("SEARCH_TREND", "Web Search Interest Trend", "SENTIMENT", "candidate", "publish_date", 5, 2, "agent"),
    ("DIV_GROWTH_5Y", "5-Year Dividend Growth", "QUALITY", "candidate", "publish_date", 6, 3, "agent"),
    ("FCF_MARGIN_TTM", "Free Cash Flow Margin (TTM)", "CARRY", "candidate", "publish_date", 6, 4, "agent"),
]

CANDIDATE_FACTORS = [f[0] for f in FACTOR_DEFS if f[3] == "candidate"]

# Atlas Agent 在 RUN-2026-Q2-001 里跑的 10 个假设.
# seq_no 就是 trial_index —— 它决定该假设要跨过的多重检验门槛.
# verdict: PROMOTED = 推进到 Model Validation; REJECTED = 否决; 附带否决原因码.
HYPOTHESIS_DEFS = [
    (
        1, "ACC_QUALITY", "Cash-backed earnings outperform accrual-heavy earnings",
        "Firms whose reported net income is backed by operating cash flow should outperform firms "
        "whose earnings are driven by accruals. Accrual-heavy earnings are more likely to reverse, "
        "and the market is slow to price the difference. Signal is quarterly and should be low turnover.",
        "literature", "PROMOTED", None,
    ),
    (
        2, "EPS_REV_60D", "Consensus EPS revisions carry information beyond price momentum",
        "When sell-side analysts revise forward EPS estimates upward as a group, the revision reflects "
        "information that has not yet been fully absorbed into price. Expected to be a real but "
        "fast-decaying signal with meaningful turnover.",
        "literature", "PROMOTED", None,
    ),
    (
        3, "PEAD_SUE", "Post-earnings announcement drift persists in the current universe",
        "Standardized unexpected earnings should predict a one-to-two month drift after the earnings "
        "release. Critical implementation detail: the signal must be timestamped to publish_date, not "
        "to fiscal_period_end, or the backtest sees the surprise before the market does.",
        "literature", "PROMOTED", None,
    ),
    (
        4, "STR_REV_5D", "Five-day price reversal is exploitable at large-cap liquidity",
        "Short horizon overreaction reverses. The raw signal is strong but rebalances almost completely "
        "every month, so the question is not whether the alpha exists but whether it survives "
        "transaction costs.",
        "data_mining", "PROMOTED", None,
    ),
    (
        5, "VOL_SKEW_ADJ", "Skew-adjusted volatility improves on plain low-volatility",
        "Adjusting realized volatility for return skewness should isolate the part of low-risk anomaly "
        "that is not explained by plain volatility, producing an incrementally different signal.",
        "memory", "REJECTED", "REDUNDANT_WITH_EXISTING",
    ),
    (
        6, "MICRO_VALUE", "A composite value signal works better in micro-cap names",
        "Valuation dispersion is wider and analyst coverage thinner among the smallest names, so a "
        "composite value score should have more predictive power there than in large caps.",
        "data_mining", "REJECTED", "CAPACITY_CONSTRAINED",
    ),
    (
        7, "NEWS_SENT_7D", "Seven-day news sentiment momentum predicts cross-sectional returns",
        "Aggregated news tone over a trailing week should capture attention-driven demand before it "
        "shows up in price. Alternative data source, low correlation with the production library.",
        "analyst_note", "REJECTED", "REGIME_DEPENDENT",
    ),
    (
        8, "SEARCH_TREND", "Web search interest trend is a retail-attention proxy",
        "Rising search interest in a ticker proxies for incremental retail demand, which should predict "
        "short-run outperformance. Cheap alternative dataset already licensed by the firm.",
        "data_mining", "REJECTED", "FAILS_MULTIPLE_TESTING",
    ),
    (
        9, "DIV_GROWTH_5Y", "Sustained five-year dividend growth signals durable quality",
        "Companies able to grow dividends for five consecutive years demonstrate a quality and capital "
        "discipline that the market underprices relative to headline yield.",
        "literature", "REJECTED", "SURVIVORSHIP_DEPENDENT",
    ),
    (
        10, "FCF_MARGIN_TTM", "Free cash flow margin dominates earnings-based quality",
        "FCF margin is harder to manipulate than accounting earnings and should therefore be a cleaner "
        "quality signal than ROE. Uses the firm's fundamentals warehouse directly.",
        "memory", "REJECTED", "RESTATEMENT_CONTAMINATED",
    ),
]

# 各因子 raw_value 的中心与尺度. z_score 是横截面标准化后的打分, raw_value 是
# 标准化之前的业务量纲 (例如 VAL_EP 是 E/P 比率, MOM_12_1 是过去 12 个月收益).
# 分析师看 raw 判断"这个数合不合理", 看 z 做横截面比较.
RAW_VALUE_SCALE = {
    "VAL_EP": (0.052, 0.026),
    "MOM_12_1": (0.085, 0.310),
    "QUA_ROE": (0.138, 0.092),
    "VOL_LOW_60D": (-0.285, 0.115),
    "SIZ_LOG_MCAP": (-8.20, 1.55),
    "LIQ_AMIHUD": (0.42, 0.36),
    "ACC_QUALITY": (0.018, 0.041),
    "EPS_REV_60D": (0.004, 0.038),
    "PEAD_SUE": (0.00, 1.00),
    "STR_REV_5D": (-0.002, 0.036),
    "VOL_SKEW_ADJ": (-0.262, 0.121),
    "MICRO_VALUE": (0.061, 0.033),
    "NEWS_SENT_7D": (0.052, 0.214),
    "SEARCH_TREND": (0.031, 0.186),
    "DIV_GROWTH_5Y": (0.058, 0.047),
    "FCF_MARGIN_TTM": (0.081, 0.052),
}

# 这些因子的 IC 不是通过线性载荷注入的, 各有专门的机制 (见上面的常量说明).
NON_LINEAR_FACTORS = {"PEAD_SUE", "VOL_SKEW_ADJ", "MICRO_VALUE", "NEWS_SENT_7D", "FCF_MARGIN_TTM"}

# 各 regime 下的市场月度漂移. 压力期是负的, 这样 regime 拆分才有真实的业绩差异 ——
# 如果四个 regime 的市场收益都一样, "换个环境结论就变"这件事就无从演示.
REGIME_MARKET_DRIFT = {
    "RECOVERY": 0.0120,
    "LOW_VOL_BULL": 0.0142,
    "HIGH_VOL_STRESS": -0.0185,
    "RISING_RATE": 0.0022,
}

# 因子数据的平均陈旧度 (天). 基本面类因子天然滞后于观测日, 价格类因子当天可得.
# data_asof_date = obs_date - 这个天数, 它是分析师判断"这个打分用的是多久以前的
# 信息"的依据. 24 天略小于财报平均滞后的 30 天, 因为月末那一天能看到的最新一份
# 财报, 平均已经公布了几天.
FACTOR_DATA_LAG_DAYS = {
    "publish_date": 24,
    "trade_date": 0,
}

# 单个因子策略假定投入的资金. 冲击成本随资金规模上升, 这是容量分析的支点.
# 30 亿是一家 320 亿 AUM 的机构给单个 alpha 信号的典型配置量级.
ASSUMED_STRATEGY_AUM_USD_MM = 3000.0

# 每月的实际调仓次数. 半衰期只有几天的信号, 按月持有会浪费掉大部分 alpha,
# 实践中必须更频繁地调仓, 换手率与成本也随之成倍上升. 没列进来的因子默认为 1.0.
REBALANCE_PER_MONTH = {
    "STR_REV_5D": 1.2,     # 5 日反转, 信号几天就衰减完
    "NEWS_SENT_7D": 1.3,   # 7 日新闻情绪
}

# 建仓时允许占用的单日成交额比例, 以及给建仓留出的交易日数.
# 5% x 21 天是买方常见的"一个月内建完仓且不惊动市场"的口径: 超过 5% 参与度,
# 你自己的委托就会成为当天的主要价格驱动.
CAPACITY_ADV_PARTICIPATION = 0.05
CAPACITY_BUILD_DAYS = 21

# 样本内 / 样本外的切分点. 前 28 个月训练, 后 14 个月留作 OOS —— 三分之二对
# 三分之一是因子研究里最常见的切法, 再短的 OOS 窗口算不出可信的 t 统计量.
IN_SAMPLE_LAST_MONTH = 27

# 验证结论的判定规则. 顺序即优先级, 先命中先生效. 这四个门槛是 Model Validation
# 组的"红线", 研究员和 Agent 都改不了 —— 这正是把"算分"从"建模"里拿走的制度设计.
# 0.75: 两个因子的月度 IC 序列相关性超过它, 增量贡献就已经小到不值得多养一条
#       数据管线. 业内常见的红线在 0.7-0.8 之间.
VALIDATION_CORR_LIMIT = 0.75
# 5 亿美元: 低于这个规模, 一个策略对 320 亿 AUM 的总组合贡献不到 1.5%, 而数据、
# 监控、合规、交易的固定成本是一样的 —— 算总账不划算.
VALIDATION_MIN_CAPACITY_MM = 500.0
# 净 IR 0.20: 成本后还剩这么一点, 已经低于机构愿意为一条信号支付运维成本的下限.
VALIDATION_MIN_NET_IR = 0.20
# 净 IR 0.45: 0.45-0.20 这一段是"能用但要限规模"的灰区, 给 CONDITIONAL 结论.
# 0.5 是客户开始考虑赎回的水平, 所以门槛设在略低于 0.5 的地方.
VALIDATION_CONDITIONAL_NET_IR = 0.45

# Atlas 最终推进到验证的 4 个因子, 它们等权合成 Agent 复合信号.
PROMOTED_FACTORS = ["ACC_QUALITY", "EPS_REV_60D", "PEAD_SUE", "STR_REV_5D"]

# 研究组合的持仓只数. 180 只在 500 只的池子里, 约等于 36% 的覆盖度,
# 既能分散特异风险, 又不至于把信号稀释成基准.
PAPER_PORTFOLIO_HOLDINGS = 180

# 复合信号的单位换手成本 (bps, 单边). 复合信号只在 US_LARGE_500 上交易, 篮子的
# 平均价差约 25 bps 的一半加上冲击与佣金, 落在 26 bps 附近. 这个常量驱动全部
# T10 的净 IR, 所以只在这里定义一次, 四处调用都引用它.
COMPOSITE_COST_BPS_PER_UNIT = 26.0

# ---------------------------------------------------------------------------
# Section 5. ORM 模型
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class AssetClass(Base):
    """资产大类. 把美股与跨资产 sleeve 里的 ETF 代理区分开, 因子逻辑不同."""

    __tablename__ = "asset_class"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class Sector(Base):
    """GICS 风格板块. 板块中性化与板块归因都以它为分组键."""

    __tablename__ = "sector"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gics_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    benchmark_weight: Mapped[float] = mapped_column(Float, nullable=False)


class RegimeType(Base):
    """市场状态类型. 因子是否只在特定环境有效, 全靠这张表来切分验证."""

    __tablename__ = "regime_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    typical_vol_ann: Mapped[float] = mapped_column(Float, nullable=False)


class FactorTheme(Base):
    """因子主题. signal -> factor -> theme 三层结构里的最上层."""

    __tablename__ = "factor_theme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    economic_rationale: Mapped[str] = mapped_column(String(255), nullable=False)


class Universe(Base):
    """研究池定义. 同一个因子在不同池子上的表现差异, 是容量分析的核心证据."""

    __tablename__ = "universe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    selection_rule: Mapped[str] = mapped_column(String(255), nullable=False)
    approx_member_count: Mapped[int] = mapped_column(Integer, nullable=False)


class Benchmark(Base):
    """业绩基准. active return 与 tracking error 都相对它计算."""

    __tablename__ = "benchmark"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_class_id: Mapped[int] = mapped_column(ForeignKey("asset_class.id"), nullable=False)


class ConstraintSet(Base):
    """组合优化约束档位. 同一信号换一套约束, 净 IR 可以差一倍以上."""

    __tablename__ = "constraint_set"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    max_asset_weight: Mapped[float] = mapped_column(Float, nullable=False)
    max_sector_deviation: Mapped[float] = mapped_column(Float, nullable=False)
    max_annual_turnover: Mapped[float] = mapped_column(Float, nullable=False)
    max_tracking_error: Mapped[float] = mapped_column(Float, nullable=False)
    max_adv_participation: Mapped[float] = mapped_column(Float, nullable=False)


class Portfolio(Base):
    """组合. 两个实盘组合加一个 Agent 复合信号的 paper 组合."""

    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    portfolio_type: Mapped[str] = mapped_column(String(16), nullable=False)
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("benchmark.id"), nullable=False)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universe.id"), nullable=False)
    constraint_set_id: Mapped[int] = mapped_column(ForeignKey("constraint_set.id"), nullable=False)
    aum_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    inception_date: Mapped[date] = mapped_column(Date, nullable=False)


class TradingCalendar(Base):
    """交易日历. 所有时间序列表的日期都必须落在这张表里."""

    __tablename__ = "trading_calendar"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    is_month_end: Mapped[int] = mapped_column(Integer, nullable=False)
    is_quarter_end: Mapped[int] = mapped_column(Integer, nullable=False)
    month_index: Mapped[int] = mapped_column(Integer, nullable=False)


class Asset(Base):
    """可投资标的. 含 120 只已退市股票 —— 幸存者偏差要能被真实观测到, 而不只是提醒."""

    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    company_name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_class_id: Mapped[int] = mapped_column(ForeignKey("asset_class.id"), nullable=False)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sector.id"), nullable=True)
    listing_date: Mapped[date] = mapped_column(Date, nullable=False)
    delisted_date: Mapped[date] = mapped_column(Date, nullable=True)
    delist_reason: Mapped[str] = mapped_column(String(32), nullable=True)
    initial_market_cap_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    size_quintile: Mapped[int] = mapped_column(Integer, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)


class MarketRegimeDay(Base):
    """每个交易日的市场状态标签与三个宏观风险指标. regime 拆分分析的依据."""

    __tablename__ = "market_regime_day"

    trade_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), primary_key=True)
    regime_type_id: Mapped[int] = mapped_column(ForeignKey("regime_type.id"), nullable=False)
    vix_proxy: Mapped[float] = mapped_column(Float, nullable=False)
    term_spread_bp: Mapped[float] = mapped_column(Float, nullable=False)
    credit_spread_bp: Mapped[float] = mapped_column(Float, nullable=False)


class BenchmarkDaily(Base):
    """基准的日频价格与收益. 计算 active return 时的减数."""

    __tablename__ = "benchmark_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("benchmark.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    close_level: Mapped[float] = mapped_column(Float, nullable=False)
    return_1d: Mapped[float] = mapped_column(Float, nullable=False)


class DailyBar(Base):
    """日频行情与流动性. 全库最大的表, 因子的前瞻收益、波动率、成本参数都从这里来."""

    __tablename__ = "daily_bar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    adj_close: Mapped[float] = mapped_column(Float, nullable=False)
    return_1d: Mapped[float] = mapped_column(Float, nullable=False)
    volume_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    dollar_volume_usd: Mapped[float] = mapped_column(Float, nullable=False)
    adv_20d_usd: Mapped[float] = mapped_column(Float, nullable=False)
    market_cap_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    bid_ask_spread_bps: Mapped[float] = mapped_column(Float, nullable=False)
    realized_vol_60d: Mapped[float] = mapped_column(Float, nullable=False)


class FundamentalReport(Base):
    """PIT 财报. 同一个 fiscal_period 可能有 version=1 原始版与 version=2 修订版."""

    __tablename__ = "fundamental_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    fiscal_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    publish_date: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_restated: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    net_income_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    operating_cash_flow_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    capex_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    total_equity_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    eps_actual: Mapped[float] = mapped_column(Float, nullable=False)
    sue: Mapped[float] = mapped_column(Float, nullable=False)
    accrual_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    fcf_margin_ttm: Mapped[float] = mapped_column(Float, nullable=False)
    roe_ttm: Mapped[float] = mapped_column(Float, nullable=False)


class AnalystEstimate(Base):
    """卖方一致预期月度快照. EPS 修正类因子的原料, 同样带 publish_date."""

    __tablename__ = "analyst_estimate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    publish_date: Mapped[date] = mapped_column(Date, nullable=False)
    num_analysts: Mapped[int] = mapped_column(Integer, nullable=False)
    fy1_eps_mean: Mapped[float] = mapped_column(Float, nullable=False)
    eps_revision_1m: Mapped[float] = mapped_column(Float, nullable=False)
    eps_revision_3m: Mapped[float] = mapped_column(Float, nullable=False)
    rating_mean: Mapped[float] = mapped_column(Float, nullable=False)


class Factor(Base):
    """因子定义. 6 个生产因子 + 10 个 Agent 候选因子."""

    __tablename__ = "factor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    theme_id: Mapped[int] = mapped_column(ForeignKey("factor_theme.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    lag_convention: Mapped[str] = mapped_column(String(24), nullable=False)
    complexity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(16), nullable=False)
    first_proposed_date: Mapped[date] = mapped_column(Date, nullable=False)


class FactorExposure(Base):
    """月末因子暴露. 全库第二大的表, 每个因子在每只在市标的上的横截面打分."""

    __tablename__ = "factor_exposure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    obs_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    data_asof_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_value: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_pct: Mapped[float] = mapped_column(Float, nullable=False)
    quintile: Mapped[int] = mapped_column(Integer, nullable=False)


class FactorIcMonthly(Base):
    """Model Validation 组口径的月度 RankIC. Agent 无权改写这张表, 它是裁判."""

    __tablename__ = "factor_ic_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor.id"), nullable=False)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universe.id"), nullable=False)
    obs_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    regime_type_id: Mapped[int] = mapped_column(ForeignKey("regime_type.id"), nullable=False)
    rank_ic: Mapped[float] = mapped_column(Float, nullable=False)
    n_assets: Mapped[int] = mapped_column(Integer, nullable=False)
    fwd_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    q5_minus_q1_return: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_turnover: Mapped[float] = mapped_column(Float, nullable=False)


class FactorValidationRun(Base):
    """Model Validation 组出具的正式验证结论, 一个因子一个窗口一行."""

    __tablename__ = "factor_validation_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor.id"), nullable=False)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universe.id"), nullable=False)
    window_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sample_start: Mapped[date] = mapped_column(Date, nullable=False)
    sample_end: Mapped[date] = mapped_column(Date, nullable=False)
    n_months: Mapped[int] = mapped_column(Integer, nullable=False)
    ic_mean: Mapped[float] = mapped_column(Float, nullable=False)
    ic_std: Mapped[float] = mapped_column(Float, nullable=False)
    icir: Mapped[float] = mapped_column(Float, nullable=False)
    ic_tstat: Mapped[float] = mapped_column(Float, nullable=False)
    ic_hit_rate: Mapped[float] = mapped_column(Float, nullable=False)
    q5_q1_annual_return: Mapped[float] = mapped_column(Float, nullable=False)
    annual_turnover: Mapped[float] = mapped_column(Float, nullable=False)
    cost_bps_annual: Mapped[float] = mapped_column(Float, nullable=False)
    gross_ir: Mapped[float] = mapped_column(Float, nullable=False)
    net_ir: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    deflated_sharpe: Mapped[float] = mapped_column(Float, nullable=False)
    max_corr_with_production: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_usd_mm: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    fail_reason_code: Mapped[str] = mapped_column(String(40), nullable=True)
    validated_on: Mapped[date] = mapped_column(Date, nullable=False)


class CovarianceEstimate(Base):
    """月末协方差估计的元数据. 预测波动 vs 实际波动的偏差是这张表的核心看点."""

    __tablename__ = "covariance_estimate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universe.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    regime_type_id: Mapped[int] = mapped_column(ForeignKey("regime_type.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    halflife_days: Mapped[int] = mapped_column(Integer, nullable=False)
    n_assets: Mapped[int] = mapped_column(Integer, nullable=False)
    t_over_n: Mapped[float] = mapped_column(Float, nullable=False)
    shrinkage_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    condition_number: Mapped[float] = mapped_column(Float, nullable=False)
    is_singular: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_pairwise_corr: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_vol_ann: Mapped[float] = mapped_column(Float, nullable=False)
    realized_vol_ann_next: Mapped[float] = mapped_column(Float, nullable=False)
    vol_bias_ratio: Mapped[float] = mapped_column(Float, nullable=False)


class BacktestRun(Base):
    """一次回测. 因子 x 约束档 x 样本窗口的组合, 是所有业绩数字的出处."""

    __tablename__ = "backtest_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_code: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor.id"), nullable=True)
    is_composite: Mapped[int] = mapped_column(Integer, nullable=False)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universe.id"), nullable=False)
    constraint_set_id: Mapped[int] = mapped_column(ForeignKey("constraint_set.id"), nullable=False)
    cov_method: Mapped[str] = mapped_column(String(24), nullable=False)
    window_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    n_rebalances: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_return_ann: Mapped[float] = mapped_column(Float, nullable=False)
    net_return_ann: Mapped[float] = mapped_column(Float, nullable=False)
    active_vol_ann: Mapped[float] = mapped_column(Float, nullable=False)
    gross_ir: Mapped[float] = mapped_column(Float, nullable=False)
    net_ir: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    annual_turnover: Mapped[float] = mapped_column(Float, nullable=False)
    cost_bps_annual: Mapped[float] = mapped_column(Float, nullable=False)
    tracking_error: Mapped[float] = mapped_column(Float, nullable=False)


class BacktestMonthly(Base):
    """回测的月度明细. 回撤归因与 IS/OOS 对比都建立在这张表上."""

    __tablename__ = "backtest_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_run.id"), nullable=False)
    month_end: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    regime_type_id: Mapped[int] = mapped_column(ForeignKey("regime_type.id"), nullable=False)
    gross_return: Mapped[float] = mapped_column(Float, nullable=False)
    net_return: Mapped[float] = mapped_column(Float, nullable=False)
    benchmark_return: Mapped[float] = mapped_column(Float, nullable=False)
    active_return: Mapped[float] = mapped_column(Float, nullable=False)
    turnover: Mapped[float] = mapped_column(Float, nullable=False)
    cost_bps: Mapped[float] = mapped_column(Float, nullable=False)
    drawdown: Mapped[float] = mapped_column(Float, nullable=False)


class PortfolioHolding(Base):
    """研究组合的月末持仓. 含基准权重与主动权重, 以及哪条约束在这只票上顶到了上限."""

    __tablename__ = "portfolio_holding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    benchmark_weight: Mapped[float] = mapped_column(Float, nullable=False)
    active_weight: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_constraint_binding: Mapped[int] = mapped_column(Integer, nullable=False)
    binding_constraint_code: Mapped[str] = mapped_column(String(32), nullable=True)


class AttributionMonthly(Base):
    """月度归因. 把主动收益拆成 factor 贡献与 sector 贡献两个维度."""

    __tablename__ = "attribution_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), nullable=False)
    month_end: Mapped[date] = mapped_column(ForeignKey("trading_calendar.trade_date"), nullable=False)
    attribution_type: Mapped[str] = mapped_column(String(16), nullable=False)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor.id"), nullable=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sector.id"), nullable=True)
    return_contribution_bps: Mapped[float] = mapped_column(Float, nullable=False)
    risk_contribution_pct: Mapped[float] = mapped_column(Float, nullable=False)
    avg_active_exposure: Mapped[float] = mapped_column(Float, nullable=False)


class AgentRun(Base):
    """Atlas Agent 的一次完整探索. 本数据集收录 RUN-2026-Q2-001 这一轮."""

    __tablename__ = "agent_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    universe_id: Mapped[int] = mapped_column(ForeignKey("universe.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    wall_clock_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    hypotheses_planned: Mapped[int] = mapped_column(Integer, nullable=False)
    hypotheses_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    hypotheses_promoted: Mapped[int] = mapped_column(Integer, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    total_sql_queries: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    human_analyst_baseline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class AgentHypothesis(Base):
    """Agent 提出的一个研究假设. seq_no 同时是多重检验意义上的尝试序号."""

    __tablename__ = "agent_hypothesis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    thesis_text: Mapped[str] = mapped_column(Text, nullable=False)
    idea_source: Mapped[str] = mapped_column(String(24), nullable=False)
    theme_id: Mapped[int] = mapped_column(ForeignKey("factor_theme.id"), nullable=False)
    trial_index: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_t_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    observed_t_stat: Mapped[float] = mapped_column(Float, nullable=False)
    passes_adjusted_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    reject_reason_code: Mapped[str] = mapped_column(String(40), nullable=True)
    n_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AgentStep(Base):
    """Agent 探索轨迹里的一步. sql_text 保存它当时真实生成并执行的那条业务查询."""

    __tablename__ = "agent_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False)
    agent_hypothesis_id: Mapped[int] = mapped_column(ForeignKey("agent_hypothesis.id"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(24), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(32), nullable=False)
    sql_text: Mapped[str] = mapped_column(Text, nullable=True)
    rows_returned: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    key_metric_name: Mapped[str] = mapped_column(String(40), nullable=True)
    key_metric_value: Mapped[float] = mapped_column(Float, nullable=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AgentFinding(Base):
    """Agent 在某一步得出的具体发现. 是它最终报告里每一句结论的证据来源."""

    __tablename__ = "agent_finding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False)
    agent_hypothesis_id: Mapped[int] = mapped_column(ForeignKey("agent_hypothesis.id"), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_metric: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_value: Mapped[float] = mapped_column(Float, nullable=False)
    comparison_value: Mapped[float] = mapped_column(Float, nullable=True)
    threshold_applied: Mapped[float] = mapped_column(Float, nullable=True)
    supports_promotion: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class AgentReportSection(Base):
    """Agent 自动生成的最终报告. 严格按机构研究报告的四段式结构组织."""

    __tablename__ = "agent_report_section"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    referenced_hypothesis_seqs: Mapped[str] = mapped_column(String(64), nullable=True)


# ---------------------------------------------------------------------------
# Section 6. 生成器函数
# ---------------------------------------------------------------------------


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """某年某月的第 n 个星期几. 用于推算美股的浮动节假日 (MLK, 劳动节等)."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """某年某月最后一个星期几. 阵亡将士纪念日落在 5 月最后一个周一."""
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def _market_holidays(year: int) -> set[date]:
    """NYSE 全天休市日. 复活节相关的 Good Friday 用近似日期表, 精度足够生成日历."""
    good_friday = {2022: date(2022, 4, 15), 2023: date(2023, 4, 7), 2024: date(2024, 3, 29),
                   2025: date(2025, 4, 18), 2026: date(2026, 4, 3)}
    return {
        date(year, 1, 1),              # 元旦
        _nth_weekday(year, 1, 0, 3),   # 马丁路德金日 (1 月第三个周一)
        _nth_weekday(year, 2, 0, 3),   # 总统日 (2 月第三个周一)
        good_friday[year],             # 耶稣受难日
        _last_weekday(year, 5, 0),     # 阵亡将士纪念日 (5 月最后一个周一)
        date(year, 6, 19),             # 六月节
        date(year, 7, 4),              # 独立日
        _nth_weekday(year, 9, 0, 1),   # 劳动节 (9 月第一个周一)
        _nth_weekday(year, 11, 3, 4),  # 感恩节 (11 月第四个周四)
        date(year, 12, 25),            # 圣诞节
    }


def gen_trading_calendar() -> pl.DataFrame:
    """交易日历. 所有时间序列表的日期都必须落在这张表里, 否则 join 会静默丢行."""
    holidays: set[date] = set()
    for year in range(HISTORY_START.year, REFERENCE_DATE.year + 1):
        holidays |= _market_holidays(year)

    rows = []
    d = HISTORY_START
    idx = 0
    while d <= REFERENCE_DATE:
        if d.weekday() < 5 and d not in holidays:
            rows.append({"trade_date": d, "day_index": idx, "year_month": f"{d.year:04d}-{d.month:02d}"})
            idx += 1
        d += timedelta(days=1)

    df = pl.DataFrame(rows)
    # 每个自然月的最后一个交易日就是调仓日 (month_end). 因子暴露、协方差、
    # 组合权重全部锚定在这些日期上.
    df = df.with_columns(
        (pl.col("day_index") == pl.col("day_index").max().over("year_month")).cast(pl.Int64).alias("is_month_end")
    )
    # month_index 对每一个交易日都有定义 (它所属月份的序号 0..N), 不只是月末那一天.
    # 后面把月度目标收益打散到日频时, 靠的就是这一列做分组键.
    ym_order = {ym: i for i, ym in enumerate(sorted(df["year_month"].unique().to_list()))}
    df = df.with_columns(
        pl.col("year_month").replace_strict(ym_order, return_dtype=pl.Int64).alias("month_index"),
        pl.col("trade_date").dt.month().is_in([3, 6, 9, 12]).cast(pl.Int64).alias("_q"),
    )
    df = df.with_columns(
        ((pl.col("is_month_end") == 1) & (pl.col("_q") == 1)).cast(pl.Int64).alias("is_quarter_end")
    ).drop("_q")
    return df.select("trade_date", "day_index", "year_month", "is_month_end", "is_quarter_end", "month_index")


def gen_asset_classes() -> pl.DataFrame:
    """资产大类."""
    rows = [
        ("US_EQUITY", "US Common Equity", "Single-name US listed common stock, the core research universe"),
        ("EQUITY_ETF", "Equity Index ETF", "Broad and regional equity index proxies used in the cross-asset sleeve"),
        ("RATES_ETF", "Rates / Treasury ETF", "Duration exposure proxies across the Treasury curve"),
        ("CREDIT_ETF", "Credit ETF", "Investment grade and high yield credit spread proxies"),
        ("COMMOD_FX_ETF", "Commodity and FX ETF", "Commodity and currency exposure proxies"),
    ]
    return pl.DataFrame(
        [{"id": i + 1, "code": c, "name": n, "description": d} for i, (c, n, d) in enumerate(rows)]
    )


def gen_sectors() -> pl.DataFrame:
    """GICS 风格板块."""
    return pl.DataFrame([
        {"id": i + 1, "gics_code": c, "name": n, "benchmark_weight": w}
        for i, (c, n, w) in enumerate(SECTOR_DEFS)
    ])


def gen_regime_types() -> pl.DataFrame:
    """市场状态类型."""
    rows = [
        ("RECOVERY", "Recovery", "Equities grinding higher off a drawdown, volatility normalizing", 0.165),
        # typical_vol_ann 必须与 REGIME_SCHEDULE 里同名 regime 的波动率一致.
        ("LOW_VOL_BULL", "Low Volatility Bull", "Trending market with suppressed realized volatility", 0.121),
        ("HIGH_VOL_STRESS", "High Volatility Stress", "Correlation spike, volatility regime break, risk-off", 0.312),
        ("RISING_RATE", "Rising Rate", "Duration selloff, growth de-rating, elevated dispersion", 0.198),
    ]
    return pl.DataFrame([
        {"id": i + 1, "code": c, "name": n, "description": d, "typical_vol_ann": v}
        for i, (c, n, d, v) in enumerate(rows)
    ])


def gen_factor_themes() -> pl.DataFrame:
    """因子主题."""
    return pl.DataFrame([
        {"id": i + 1, "code": c, "name": n, "economic_rationale": r}
        for i, (c, n, r) in enumerate(FACTOR_THEME_DEFS)
    ])


def gen_universes() -> pl.DataFrame:
    """研究池."""
    rows = [
        ("US_ALL", "US All Cap", "All US common equities listed on the observation date", 1150),
        ("US_LARGE_500", "US Large Cap 500", "Top 500 US names by market cap at each rebalance", 500),
        ("US_MICRO_250", "US Micro Cap 250", "Bottom 250 US names by market cap at each rebalance", 250),
        ("CROSS_ASSET_40", "Cross Asset Sleeve", "40 ETF proxies spanning rates, credit, commodity and FX", 40),
    ]
    return pl.DataFrame([
        {"id": i + 1, "code": c, "name": n, "selection_rule": s, "approx_member_count": m}
        for i, (c, n, s, m) in enumerate(rows)
    ])


def gen_benchmarks() -> pl.DataFrame:
    """业绩基准."""
    rows = [
        ("TCM_US_CORE", "TCM US Core Equity Benchmark", 1),
        ("TCM_US_SMALL", "TCM US Small Cap Benchmark", 1),
        ("TCM_MULTI_6040", "TCM Multi-Asset 60/40 Benchmark", 2),
        ("TCM_CASH", "TCM Cash / 3M T-Bill Benchmark", 3),
    ]
    return pl.DataFrame([
        {"id": i + 1, "code": c, "name": n, "asset_class_id": a}
        for i, (c, n, a) in enumerate(rows)
    ])


def gen_constraint_sets() -> pl.DataFrame:
    """组合优化约束档位. max_* 字段的量级取自主流机构的授权书常见条款.

    UNCONSTRAINED 的年换手上限取 25.0 而不是 20.0: 单因子回测全部挂在这一档下,
    而 STR_REV_5D 这类 5 日反转信号的年化双边换手实测到 23 倍, 上限必须留出余量,
    否则 backtest_run JOIN constraint_set 一查就是自相矛盾.
    """
    rows = [
        ("UNCONSTRAINED", "Unconstrained Paper Portfolio", 0.100, 1.000, 25.00, 0.500, 1.000),
        ("SECTOR_NEUTRAL", "Sector Neutral Only", 0.050, 0.000, 20.00, 0.500, 1.000),
        ("LIQUIDITY_TIGHT", "Liquidity Constrained", 0.030, 0.030, 20.00, 0.500, 0.050),
        ("FULL_PRODUCTION", "Full Production Mandate", 0.025, 0.020, 1.20, 0.050, 0.050),
    ]
    return pl.DataFrame([
        {"id": i + 1, "code": c, "name": n, "max_asset_weight": w, "max_sector_deviation": s,
         "max_annual_turnover": t, "max_tracking_error": te, "max_adv_participation": adv}
        for i, (c, n, w, s, t, te, adv) in enumerate(rows)
    ])


def gen_portfolios() -> pl.DataFrame:
    """组合. 两个实盘 + 一个 Agent 复合信号的 paper 组合."""
    rows = [
        ("TCM_USCE", "TCM US Core Equity", "live", 1, 2, 4, 14200.0, date(2016, 4, 1)),
        ("TCM_MAS", "TCM Multi-Asset Systematic", "live", 3, 4, 4, 6800.0, date(2019, 9, 3)),
        ("TCM_ATLAS_PAPER", "Atlas Agent Composite (Paper)", "paper", 1, 2, 4, 0.0, date(2022, 12, 30)),
    ]
    return pl.DataFrame([
        {"id": i + 1, "code": c, "name": n, "portfolio_type": t, "benchmark_id": b,
         "universe_id": u, "constraint_set_id": cs, "aum_usd_mm": aum, "inception_date": inc}
        for i, (c, n, t, b, u, cs, aum, inc) in enumerate(rows)
    ])


def gen_assets(month_ends: list[date]) -> pl.DataFrame:
    """可投资标的.

    刻意保留 120 只已退市股票并写明 delisted_date. 一个只查 delisted_date IS NULL
    的分析会得到系统性偏高的收益, 这正是 T2 幸存者偏差陷阱的载体.
    """
    used_tickers: set[str] = set()

    def _ticker(n: int) -> str:
        while True:
            t = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n))
            if t not in used_tickers:
                used_tickers.add(t)
                return t

    sector_ids = [i + 1 for i in range(len(SECTOR_DEFS))]
    sector_w = [w for _, _, w in SECTOR_DEFS]

    rows = []
    aid = 0
    for kind, count in (("active", N_EQUITY_ACTIVE), ("delisted", N_EQUITY_DELISTED)):
        for _ in range(count):
            aid += 1
            # 市值用对数正态: 美股市值分布极度右偏, 前 5% 的公司占掉一半以上总市值.
            mcap = math.exp(random.gauss(7.6, 1.55))
            mcap = min(max(mcap, 120.0), 2_900_000.0)
            listing = HISTORY_START - timedelta(days=random.randint(400, 7200))
            delisted = None
            reason = None
            if kind == "delisted":
                # 退市时点铺开在 2023-09 到 2026-03 之间, 保证每个月都有正在"消失"的标的.
                lo = month_ends[9]
                hi = month_ends[-4]
                delisted = lo + timedelta(days=random.randint(0, (hi - lo).days))
                reason = random.choices(
                    ["MERGER", "BANKRUPTCY", "EXCHANGE_DELISTING", "GOING_PRIVATE"],
                    weights=[0.40, 0.25, 0.25, 0.10],
                )[0]
            rows.append({
                "id": aid,
                "ticker": _ticker(random.choice([3, 4, 4])),
                "company_name": fake.company(),
                "asset_class_id": 1,
                "sector_id": random.choices(sector_ids, weights=sector_w)[0],
                "listing_date": listing,
                "delisted_date": delisted,
                "delist_reason": reason,
                "initial_market_cap_usd_mm": round(mcap, 2),
                "size_quintile": 0,
                "country": "US",
            })

    cross_defs = [
        ("EQUITY_ETF", 2, "Equity Index Proxy"),
        ("RATES_ETF", 3, "Treasury Curve Proxy"),
        ("CREDIT_ETF", 4, "Credit Spread Proxy"),
        ("COMMOD_FX_ETF", 5, "Commodity / FX Proxy"),
    ]
    for i in range(N_CROSS_ASSET):
        aid += 1
        _, class_id, label = cross_defs[i % len(cross_defs)]
        rows.append({
            "id": aid,
            "ticker": _ticker(4),
            "company_name": f"{label} Series {i // len(cross_defs) + 1:02d}",
            "asset_class_id": class_id,
            "sector_id": None,
            "listing_date": HISTORY_START - timedelta(days=random.randint(1800, 5400)),
            "delisted_date": None,
            "delist_reason": None,
            "initial_market_cap_usd_mm": round(math.exp(random.gauss(8.4, 0.8)), 2),
            "size_quintile": 0,
            "country": "US",
        })

    df = pl.DataFrame(rows, infer_schema_length=None)
    # size_quintile 只在股票内部划分 (跨资产代理没有可比市值), 1 = 最小市值.
    # 跨资产代理填 0 = "不适用", 而不是随手塞进第三档 —— 填 3 会让任何
    # GROUP BY size_quintile 把 40 个 ETF 混进股票的中间一档.
    eq = df.filter(pl.col("asset_class_id") == 1).with_columns(
        ((pl.col("initial_market_cap_usd_mm").rank("ordinal") - 1)
         * 5 // pl.len() + 1).cast(pl.Int64).alias("q")
    ).select("id", "q")
    df = df.join(eq, on="id", how="left").with_columns(
        pl.col("q").fill_null(0).alias("size_quintile")
    ).drop("q")
    return df.select(
        "id", "ticker", "company_name", "asset_class_id", "sector_id", "listing_date",
        "delisted_date", "delist_reason", "initial_market_cap_usd_mm", "size_quintile", "country",
    )


def _regime_for(d: date) -> str:
    """某个日期落在哪个 market regime."""
    label = REGIME_SCHEDULE[0][1]
    for start, name, _vol in REGIME_SCHEDULE:
        if d >= start:
            label = name
    return label


def gen_market_regime_days(calendar: pl.DataFrame) -> pl.DataFrame:
    """每个交易日的 regime 标签与三个宏观风险指标."""
    regime_ids = {c: i + 1 for i, (c, _, _, _) in enumerate([
        ("RECOVERY", "", "", 0), ("LOW_VOL_BULL", "", "", 0),
        ("HIGH_VOL_STRESS", "", "", 0), ("RISING_RATE", "", "", 0),
    ])}
    rows = []
    for d in calendar["trade_date"].to_list():
        label = _regime_for(d)
        vol = dict((n, v) for _, n, v in REGIME_SCHEDULE)[label]
        rows.append({
            "trade_date": d,
            "regime_type_id": regime_ids[label],
            # VIX 代理近似等于年化波动率 x 100, 叠加日度噪声.
            "vix_proxy": round(max(8.0, vol * 100 * random.uniform(0.82, 1.24)), 2),
            # 期限利差在 RISING_RATE 段被压平甚至倒挂.
            "term_spread_bp": round(
                {"RECOVERY": 62, "LOW_VOL_BULL": 88, "HIGH_VOL_STRESS": 24, "RISING_RATE": -35}[label]
                + random.gauss(0, 11), 1),
            # 信用利差在压力期显著走阔.
            "credit_spread_bp": round(
                {"RECOVERY": 148, "LOW_VOL_BULL": 102, "HIGH_VOL_STRESS": 385, "RISING_RATE": 176}[label]
                + random.gauss(0, 18), 1),
        })
    return pl.DataFrame(rows)


def _centered_multipliers(n: int, sigma: float) -> list[float]:
    """n 个随机乘数, 整体平移后均值恰好为 1. 用来给真实 IC 加时序波动而不改变其均值."""
    raw = [1.0 + sigma * random.gauss(0.0, 1.0) for _ in range(n)]
    adj = 1.0 - sum(raw) / n
    return [v + adj for v in raw]


def _standardize(values: list[float], mask: list[bool]) -> list[float]:
    """按掩码取子集做 z-score. 不在池内的位置返回 0, 后续会被过滤掉."""
    sub = [v for v, ok in zip(values, mask) if ok]
    if len(sub) < 2:
        return [0.0] * len(values)
    mu = sum(sub) / len(sub)
    var = sum((v - mu) ** 2 for v in sub) / (len(sub) - 1)
    sd = math.sqrt(var) if var > 1e-12 else 1.0
    return [((v - mu) / sd) if ok else 0.0 for v, ok in zip(values, mask)]


def build_monthly_panel(assets: pl.DataFrame, month_ends: list[date]) -> tuple[pl.DataFrame, list[dict]]:
    """核心引擎: 生成月度因子暴露与前瞻超额收益. 全部十条业务陷阱都在这里注入.

    返回 (月度面板, 财报季度记录). 面板每行是一个 (asset, month_end) 观测,
    含 16 个因子的 z_score、raw_value, 以及下一个月的超额收益 fwd_excess_return.
    """
    rows = assets.to_dicts()
    n_a = len(rows)
    n_m = len(month_ends)
    codes = [f[0] for f in FACTOR_DEFS]

    # 每个标的在每个月末是否"在池内": 已上市且尚未退市.
    active = [[
        (r["listing_date"] <= month_ends[m])
        and (r["delisted_date"] is None or r["delisted_date"] > month_ends[m])
        for m in range(n_m)
    ] for r in rows]

    # --- 1. 因子潜变量: 横截面排名的 AR(1) 演化 ---
    latent: dict[str, list[list[float]]] = {}
    for code in codes:
        rho = FACTOR_PERSISTENCE[code]
        shock = math.sqrt(max(1.0 - rho * rho, 1e-6))
        mat = []
        for _ in range(n_a):
            v = random.gauss(0.0, 1.0)
            series = []
            for _m in range(n_m):
                series.append(v)
                v = rho * v + shock * random.gauss(0.0, 1.0)
            mat.append(series)
        latent[code] = mat

    # SIZ_LOG_MCAP 直接绑定真实市值 (取负号, 让"小市值"在因子上得高分), 几乎不随时间变化.
    for i, r in enumerate(rows):
        base = -math.log(r["initial_market_cap_usd_mm"])
        latent["SIZ_LOG_MCAP"][i] = [base + random.gauss(0.0, 0.02) for _ in range(n_m)]

    # T6 伪新因子: VOL_SKEW_ADJ 构造上就是母因子的线性变换加噪声.
    parent = latent[PSEUDO_FACTOR_PARENT]
    indep = latent["VOL_SKEW_ADJ"]
    latent["VOL_SKEW_ADJ"] = [[
        PSEUDO_FACTOR_LOAD * parent[i][m] + PSEUDO_FACTOR_NOISE * indep[i][m]
        for m in range(n_m)
    ] for i in range(n_a)]

    # T2 幸存者偏差: 退市标的的 DIV_GROWTH_5Y 打分系统性偏高.
    for i, r in enumerate(rows):
        if r["delisted_date"] is not None:
            latent["DIV_GROWTH_5Y"][i] = [v + DELISTED_DIVGROWTH_Z_SHIFT for v in latent["DIV_GROWTH_5Y"][i]]

    # --- 2. 财报季度与盈余意外 ---
    # 财政季度末在标的之间错开 (offset 0/1/2), 避免所有公司同一个月披露 ——
    # 这既符合现实, 也让 look-ahead 陷阱在每个月都有约三分之一的标的可以触发.
    quarters: list[dict] = []
    q_by_asset: list[list[dict]] = [[] for _ in range(n_a)]
    for i, r in enumerate(rows):
        if r["asset_class_id"] != 1:
            continue
        offset = i % 3
        # 从窗口开始前三个月起算. 没有这批"前置季度", 第一个观测月里所有标的的
        # PEAD 打分都是 0, 横截面方差为零, IC 无从定义.
        for m in range(-3, n_m):
            if (m - offset) % 3 != 0:
                continue
            if m >= 0 and not active[i][m]:
                continue
            if m < 0 and not active[i][0]:
                continue
            period_end = month_ends[m] if m >= 0 else month_ends[0] - timedelta(days=31 * (-m))
            publish = period_end + timedelta(days=random.randint(*PUBLISH_LAG_DAYS))
            q = {
                "asset_id": r["id"],
                "asset_idx": i,
                "month_idx": m,
                "fiscal_period_end": period_end,
                "publish_date": publish,
                "sue": random.gauss(0.0, 1.0),
            }
            quarters.append(q)
            q_by_asset[i].append(q)

    # 公告当月吃到跳空 + 一半漂移, 下一个月吃到剩下一半漂移.
    earn_contrib = [[0.0] * n_m for _ in range(n_a)]
    for q in quarters:
        i = q["asset_idx"]
        mp = None
        for m in range(max(q["month_idx"], 0), n_m):
            if month_ends[m] >= q["publish_date"]:
                mp = m
                break
        if mp is None:
            continue
        earn_contrib[i][mp] += (ANNOUNCE_JUMP_PER_SUE + 0.5 * PEAD_DRIFT_PER_SUE) * q["sue"]
        if mp + 1 < n_m:
            earn_contrib[i][mp + 1] += 0.5 * PEAD_DRIFT_PER_SUE * q["sue"]

    # T1 look-ahead: factor_exposure 里存的永远是 **正确** 口径 —— 按 publish_date
    # 过滤, 并按公告后天数衰减. 错误口径不落库, 因为它必须是分析师自己从
    # fundamental_report 重建出来才能"踩到"的坑 (SQL 文档 Q13 / agent_step 的
    # pead_ic_naive 模板做的就是这件事). 把错误版本也存进库里, 陷阱就变成了
    # 摆在桌面上的答案.
    pead_correct = [[0.0] * n_m for _ in range(n_a)]
    for i in range(n_a):
        for m in range(n_m):
            obs = month_ends[m]
            best_c = None
            for q in q_by_asset[i]:
                if q["publish_date"] <= obs:
                    best_c = q
            if best_c is not None:
                days = (obs - best_c["publish_date"]).days
                pead_correct[i][m] = best_c["sue"] * math.exp(-days / 45.0)
    latent["PEAD_SUE"] = pead_correct

    # --- 3. 横截面标准化 ---
    z: dict[str, list[list[float]]] = {}
    for code in codes:
        zmat = [[0.0] * n_m for _ in range(n_a)]
        for m in range(n_m):
            col = [latent[code][i][m] for i in range(n_a)]
            mask = [active[i][m] and rows[i]["asset_class_id"] == 1 for i in range(n_a)]
            std = _standardize(col, mask)
            for i in range(n_a):
                zmat[i][m] = std[i]
        z[code] = zmat

    # --- 4. 前瞻超额收益 ---
    linear_codes = [c for c in codes if c not in NON_LINEAR_FACTORS]
    n_periods = n_m - 1
    # 每个因子预先抽好 41 个月度乘数, 再整体平移使其均值恰好为 1.
    # 这样 IC 的时序波动是真实的, 但 42 个月样本上的 IC 均值不会被随机漂移带偏 ——
    # 否则想让文档里的数字稳定复现, 就只能反复试种子.
    mult = {c: _centered_multipliers(n_periods, IC_TIME_VARIATION) for c in linear_codes}
    mult_micro = {q: _centered_multipliers(n_periods, IC_TIME_VARIATION)
                  for q in SMALL_CAP_IC_BOOST}
    mult_news = _centered_multipliers(n_periods, 0.35)
    mult_fcf = _centered_multipliers(n_periods, IC_TIME_VARIATION)
    mult_pead = _centered_multipliers(n_periods, PEAD_IC_TIME_VARIATION)

    fwd = [[None] * n_m for _ in range(n_a)]
    for m in range(n_m - 1):
        regime_next = _regime_for(month_ends[m + 1])
        w = {c: FACTOR_TRUE_IC[c] * mult[c][m] for c in linear_codes}
        w_micro = {q: v * mult_micro[q][m] for q, v in SMALL_CAP_IC_BOOST.items()}
        w_news = REGIME_IC_FLIP[regime_next] * mult_news[m]
        w_fcf = RESTATEMENT_PIT_IC * mult_fcf[m]
        # 市场对盈余意外的反应强度也逐月变化, 有些月份甚至反向.
        pead_mult = mult_pead[m]
        for i in range(n_a):
            if not active[i][m] or not active[i][m + 1]:
                continue
            if rows[i]["asset_class_id"] != 1:
                fwd[i][m] = random.gauss(0.0, 1.0) * MONTHLY_IDIO_VOL * 0.45
                continue
            score = sum(w[c] * z[c][i][m] for c in linear_codes)
            # T7 容量陷阱: MICRO_VALUE 的载荷按市值五分位急剧衰减.
            score += w_micro[rows[i]["size_quintile"]] * z["MICRO_VALUE"][i][m]
            # T5 regime 依赖: NEWS_SENT_7D 的载荷在高波环境下变号.
            score += w_news * z["NEWS_SENT_7D"][i][m]
            # T8 修订偏差: 真 PIT 口径下 FCF 的预测力很弱.
            score += w_fcf * z["FCF_MARGIN_TTM"][i][m]
            r = (score + random.gauss(0.0, 1.0)) * MONTHLY_IDIO_VOL
            r += earn_contrib[i][m + 1] * pead_mult
            # T2 幸存者偏差: 退市前 12 个月的死亡螺旋.
            dl = rows[i]["delisted_date"]
            if dl is not None and 0 <= (dl - month_ends[m + 1]).days <= 366:
                r += DELISTED_PRE_DELIST_MONTHLY_DRIFT
            fwd[i][m] = r

    # --- 5. T8 修订偏差: 修订后的 FCF 口径"偷看"了未来收益 ---
    restated_asset = [random.random() < RESTATEMENT_RATE for _ in range(n_a)]
    fcf_pit = z["FCF_MARGIN_TTM"]
    fcf_restated = [[0.0] * n_m for _ in range(n_a)]
    for m in range(n_m):
        col = []
        for i in range(n_a):
            v = fcf_pit[i][m]
            if restated_asset[i] and m < n_m - 1 and fwd[i][m] is not None:
                v += RESTATEMENT_LEAK * (fwd[i][m] / MONTHLY_IDIO_VOL)
            col.append(v)
        mask = [active[i][m] and rows[i]["asset_class_id"] == 1 for i in range(n_a)]
        std = _standardize(col, mask)
        for i in range(n_a):
            fcf_restated[i][m] = std[i]

    # --- 6. 组装面板 ---
    out = []
    for i, r in enumerate(rows):
        for m in range(n_m):
            if not active[i][m]:
                continue
            rec = {
                "asset_id": r["id"],
                "asset_idx": i,
                "month_index": m,
                "obs_date": month_ends[m],
                "size_quintile": r["size_quintile"],
                "asset_class_id": r["asset_class_id"],
                "is_delisted": 1 if r["delisted_date"] is not None else 0,
                "fwd_excess_return": fwd[i][m],
                "fcf_pit_z": fcf_pit[i][m],
                "is_restated_filer": 1 if restated_asset[i] else 0,
            }
            for code in codes:
                rec[f"z_{code}"] = fcf_restated[i][m] if code == "FCF_MARGIN_TTM" else z[code][i][m]
            out.append(rec)

    return pl.DataFrame(out), quarters


def _cap_weighted_daily_index(daily: pl.DataFrame, asset_ids: set[int] | None = None) -> dict[date, float]:
    """一篮子标的的市值加权日收益序列.

    权重用"上一交易日的市值" = 当日市值 / (1 + 当日收益), 这是指数编制的标准做法:
    今天的权重必须在今天开盘前就已知. 退市标的在它最后一个交易日之后自然退出篮子,
    和真实指数剔除成分股的处理一致.
    """
    d = daily if asset_ids is None else daily.filter(pl.col("asset_id").is_in(list(asset_ids)))
    d = d.with_columns(
        (pl.col("market_cap_usd_mm") / (1.0 + pl.col("return_1d"))).alias("prev_cap")
    )
    agg = d.group_by("trade_date").agg(
        (pl.col("prev_cap") * pl.col("return_1d")).sum().alias("num"),
        pl.col("prev_cap").sum().alias("den"),
    ).with_columns((pl.col("num") / pl.col("den")).alias("idx_ret"))
    return dict(zip(agg["trade_date"].to_list(), agg["idx_ret"].to_list()))


def gen_benchmark_daily(
    calendar: pl.DataFrame,
    core_index: dict[date, float],
    small_index: dict[date, float],
) -> pl.DataFrame:
    """四条基准的日频净值. active return 就是组合收益减去这里的基准收益.

    关键约束: `TCM_US_CORE` 必须真的等于它所代表的那个股票池 —— 也就是从
    `daily_bar` 市值加权算出来的收益. 早先的版本直接用生成器内部的"市场因子"
    收益当基准, 结果基准每年比它本该代表的股票池高出好几个百分点, 任何按文档
    指示"组合收益减基准收益"的分析师拿到的主动收益都会结构性为负. 现在两边
    同源, 只差一个很小的跟踪噪声 (指数编制、现金拖累、成分股微调的合成代理).
    """
    dates = calendar["trade_date"].to_list()
    rows = []
    # (benchmark_id, 基础序列, 相对基础序列的 beta, 日度漂移, 是否加跟踪噪声)
    bid_specs = [
        (1, "core", 1.00, 0.0, True),      # US Core: 全池市值加权, 就是股票池本身
        (2, "small", 1.00, 0.0, True),     # Small Cap: 最小两档市值的市值加权
        (3, "core", 0.60, 0.00006, True),  # 60/40: 六成股票加债券端的票息
        (4, None, 0.00, 0.00017, False),   # Cash: 年化约 4.3% 的无风险利率
    ]
    for bid, base, beta, drift, noisy in bid_specs:
        level = 100.0
        for d in dates:
            if base == "core":
                base_r = core_index.get(d, 0.0)
            elif base == "small":
                base_r = small_index.get(d, 0.0)
            else:
                base_r = 0.0
            r = beta * base_r + drift + (random.gauss(0.0, 0.0004) if noisy else 0.0)
            level *= (1.0 + r)
            rows.append({"benchmark_id": bid, "trade_date": d, "close_level": round(level, 4),
                         "return_1d": round(r, 6)})
    df = pl.DataFrame(rows)
    return df.with_row_index("id", offset=1).select("id", "benchmark_id", "trade_date", "close_level", "return_1d")


def gen_daily_bars(
    assets: pl.DataFrame,
    calendar: pl.DataFrame,
    panel: pl.DataFrame,
    month_ends: list[date],
) -> pl.DataFrame:
    """日频行情. 先按月度目标收益定调, 再把月内收益打散到每个交易日.

    这样做的好处是月度因子检验用的前瞻收益, 与日频价格序列严格自洽 ——
    分析师用 daily_bar 自己算出来的月度收益, 和面板里的目标值一致.
    """
    a_rows = assets.to_dicts()
    n_m = len(month_ends)

    # 市场月度收益 -> 日度收益. 同一个月内的日度市场收益之和等于当月市场收益.
    cal_rows = calendar.to_dicts()
    days_in_month: dict[int, list[date]] = {}
    for c in cal_rows:
        days_in_month.setdefault(c["month_index"], []).append(c["trade_date"])

    market_monthly = {}
    for m in range(n_m):
        label = _regime_for(month_ends[m])
        vol = dict((n, v) for _, n, v in REGIME_SCHEDULE)[label]
        market_monthly[m] = REGIME_MARKET_DRIFT[label] + random.gauss(0.0, vol / math.sqrt(12.0))

    market_daily: dict[date, float] = {}
    for m, ds in days_in_month.items():
        if not ds:
            continue
        raw = [random.gauss(0.0, 0.010) for _ in ds]
        adj = (market_monthly.get(m, 0.0) - sum(raw)) / len(ds)
        for d, r in zip(ds, raw):
            market_daily[d] = r + adj

    # 每只标的的 beta 与特异波动倍数. 波动倍数与 VOL_LOW_60D 打分挂钩,
    # 保证"低波因子得分高"的标的, 在 daily_bar 里算出来的实际波动率确实更低.
    vol_z = (
        panel.group_by("asset_id").agg(pl.col("z_VOL_LOW_60D").mean().alias("vz"))
        .to_dict(as_series=False)
    )
    vol_mult = {aid: math.exp(-0.42 * vz) for aid, vz in zip(vol_z["asset_id"], vol_z["vz"])}
    beta = {r["id"]: min(max(random.gauss(1.02, 0.34), 0.25), 2.30) for r in a_rows}
    base_price = {r["id"]: round(math.exp(random.gauss(3.6, 0.85)), 2) for r in a_rows}
    div_yield_daily = {r["id"]: max(0.0, random.gauss(0.0000055, 0.0000045)) for r in a_rows}

    # 月度总收益 = beta x 市场 + 特异超额. 面板里 fwd_excess_return[m] 是第 m+1 个月的收益.
    fwd_map = {
        (r["asset_id"], r["month_index"]): r["fwd_excess_return"]
        for r in panel.select("asset_id", "month_index", "fwd_excess_return").to_dicts()
    }
    target_log: dict[tuple[int, int], float] = {}
    for r in a_rows:
        aid = r["id"]
        for m in range(n_m):
            ex = fwd_map.get((aid, m - 1))
            if ex is None:
                ex = random.gauss(0.0, 1.0) * MONTHLY_IDIO_VOL * 0.5
            total = beta[aid] * market_monthly.get(m, 0.0) + ex
            target_log[(aid, m)] = math.log(max(1.0 + total, 0.25))

    cal_small = calendar.select("trade_date", "month_index")
    asset_small = assets.select(
        pl.col("id").alias("asset_id"), "listing_date", "delisted_date",
        "initial_market_cap_usd_mm", "size_quintile",
    )
    df = asset_small.join(cal_small, how="cross")
    df = df.filter(
        (pl.col("trade_date") >= pl.col("listing_date"))
        & (pl.col("delisted_date").is_null() | (pl.col("trade_date") <= pl.col("delisted_date")))
    ).sort("asset_id", "trade_date")

    n = df.height
    df = df.with_columns(
        pl.Series("raw_shock", [random.gauss(0.0, 1.0) for _ in range(n)]),
        pl.col("asset_id").replace_strict(vol_mult, default=1.0).alias("vol_mult"),
        pl.col("asset_id").replace_strict(beta, default=1.0).alias("beta"),
        pl.col("asset_id").replace_strict(base_price, default=25.0).alias("base_price"),
        pl.col("asset_id").replace_strict(div_yield_daily, default=0.0).alias("div_d"),
        pl.col("trade_date").replace_strict(market_daily, default=0.0).alias("mkt_d"),
    )
    df = df.with_columns(
        (pl.col("raw_shock") * 0.0135 * pl.col("vol_mult")
         + pl.col("beta") * pl.col("mkt_d")).alias("raw_log")
    )
    # 把月内日度收益整体平移, 使其加总恰好等于当月目标对数收益.
    tgt_df = pl.DataFrame({
        "asset_id": [k[0] for k in target_log],
        "month_index": [k[1] for k in target_log],
        "tgt_log": list(target_log.values()),
    }, schema={"asset_id": pl.Int64, "month_index": pl.Int64, "tgt_log": pl.Float64})
    df = df.join(tgt_df, on=["asset_id", "month_index"], how="left").with_columns(
        pl.col("tgt_log").fill_null(0.0)
    )
    df = df.with_columns(
        (pl.col("raw_log")
         + (pl.col("tgt_log") - pl.col("raw_log").sum().over("asset_id", "month_index"))
         / pl.len().over("asset_id", "month_index")).alias("log_ret")
    )
    df = df.with_columns(
        (pl.col("log_ret").cum_sum().over("asset_id")).alias("cum_log"),
        (pl.col("div_d").cum_sum().over("asset_id")).alias("cum_div"),
    )
    df = df.with_columns(
        (pl.col("base_price") * pl.col("cum_log").exp()).alias("close_price"),
    )
    df = df.with_columns(
        (pl.col("close_price") * (1.0 + pl.col("cum_div"))).alias("adj_close"),
        (pl.col("log_ret").exp() - 1.0 + pl.col("div_d")).alias("return_1d"),
    )
    df = df.with_columns(
        (pl.col("initial_market_cap_usd_mm") * pl.col("cum_log").exp()).alias("market_cap_usd_mm")
    )
    # 日换手率对数正态, 小市值的换手更高但绝对成交额低.
    df = df.with_columns(
        pl.Series("turn_shock", [random.gauss(0.0, 0.62) for _ in range(n)])
    ).with_columns(
        (pl.col("market_cap_usd_mm") * 1_000_000.0
         * (0.0062 * pl.col("turn_shock").exp()).clip(0.0004, 0.09)).alias("dollar_volume_usd")
    )
    df = df.with_columns(
        (pl.col("dollar_volume_usd") / pl.col("close_price")).round(0).cast(pl.Int64).alias("volume_shares"),
        # 价差与市值的平方根反比, 是美股微观结构里最稳定的经验关系之一.
        (2.4 + 900.0 / pl.col("market_cap_usd_mm").sqrt()).clip(1.8, 190.0).alias("bid_ask_spread_bps"),
    )
    df = df.with_columns(
        pl.col("dollar_volume_usd").rolling_mean(window_size=20, min_samples=1)
        .over("asset_id").alias("adv_20d_usd"),
        (pl.col("return_1d").rolling_std(window_size=60, min_samples=10)
         .over("asset_id") * math.sqrt(252.0)).alias("realized_vol_60d"),
    )
    df = df.with_columns(pl.col("realized_vol_60d").fill_null(0.28))

    out = df.select(
        "asset_id", "trade_date",
        pl.col("close_price").round(4),
        pl.col("adj_close").round(4),
        pl.col("return_1d").round(6),
        "volume_shares",
        pl.col("dollar_volume_usd").round(2),
        pl.col("adv_20d_usd").round(2),
        pl.col("market_cap_usd_mm").round(3),
        pl.col("bid_ask_spread_bps").round(2),
        pl.col("realized_vol_60d").round(5),
    ).with_row_index("id", offset=1)
    return out.select(
        "id", "asset_id", "trade_date", "close_price", "adj_close", "return_1d",
        "volume_shares", "dollar_volume_usd", "adv_20d_usd", "market_cap_usd_mm",
        "bid_ask_spread_bps", "realized_vol_60d",
    )


def gen_factors() -> pl.DataFrame:
    """因子定义表."""
    theme_ids = {c: i + 1 for i, (c, _, _) in enumerate(FACTOR_THEME_DEFS)}
    rows = []
    for i, (code, name, theme, status, lag, cx, nf, src) in enumerate(FACTOR_DEFS):
        # 生产因子早年就进了因子库; 候选因子全部由 Atlas 在这一轮 run 里提出.
        proposed = date(2026, 7, 6) if status == "candidate" else date(2017 + (i % 6), 3, 15)
        rows.append({
            "id": i + 1, "code": code, "name": name, "theme_id": theme_ids[theme],
            "status": status, "lag_convention": lag, "complexity_score": cx,
            "feature_count": nf, "proposed_by": src, "first_proposed_date": proposed,
        })
    return pl.DataFrame(rows)


def gen_fundamental_reports(assets: pl.DataFrame, panel: pl.DataFrame, quarters: list[dict]) -> pl.DataFrame:
    """PIT 财报. 同一个 fiscal_period 可能有 version=1 原始版和 version=2 修订版.

    T1 look-ahead 与 T8 修订偏差这两个陷阱, 都靠这张表才能被 SQL 真正复现出来:
    publish_date 与 fiscal_period_end 的差, 以及 version=1 与 version=2 的差.
    """
    zmap = {
        (r["asset_id"], r["month_index"]): r
        for r in panel.select(
            "asset_id", "month_index", "z_ACC_QUALITY", "z_QUA_ROE", "z_VAL_EP",
            "z_FCF_MARGIN_TTM", "fcf_pit_z", "is_restated_filer",
        ).to_dicts()
    }
    mcap = {r["id"]: r["initial_market_cap_usd_mm"] for r in assets.to_dicts()}
    # 每家公司的股本在样本期内基本不变, 因此先固定下来.
    # 没有它, eps_actual 会退化成一个常数 —— 那样这一列就没有任何信息量了.
    shares_mm = {r["id"]: max(r["initial_market_cap_usd_mm"] / random.uniform(14.0, 145.0), 0.8)
                 for r in assets.to_dicts()}

    rows = []
    for q in quarters:
        key = (q["asset_id"], q["month_idx"])
        zz = zmap.get(key)
        if zz is None:
            continue
        rev = mcap[q["asset_id"]] * random.uniform(0.18, 0.62)
        acc_c, acc_s = RAW_VALUE_SCALE["ACC_QUALITY"]
        roe_c, roe_s = RAW_VALUE_SCALE["QUA_ROE"]
        fcf_c, fcf_s = RAW_VALUE_SCALE["FCF_MARGIN_TTM"]

        # accrual_ratio 与 ACC_QUALITY 反向: 应计占比越低, 盈余质量越高.
        accrual = round(acc_c - acc_s * zz["z_ACC_QUALITY"], 5)
        roe = round(max(roe_c + roe_s * zz["z_QUA_ROE"], -0.45), 5)
        fcf_v1 = round(fcf_c + fcf_s * zz["fcf_pit_z"], 5)
        fcf_v2 = round(fcf_c + fcf_s * zz["z_FCF_MARGIN_TTM"], 5)
        equity = max(rev * random.uniform(0.35, 1.4), 12.0)
        net_income = equity * roe
        ocf = net_income + rev * (0.055 - accrual)
        capex = max(ocf - rev * fcf_v1, 0.0)
        shares = shares_mm[q["asset_id"]]
        eps = net_income / shares

        base = {
            "asset_id": q["asset_id"],
            "fiscal_period_end": q["fiscal_period_end"],
            "publish_date": q["publish_date"],
            "revenue_usd_mm": round(rev, 2),
            "net_income_usd_mm": round(net_income, 2),
            "operating_cash_flow_usd_mm": round(ocf, 2),
            "capex_usd_mm": round(capex, 2),
            "total_equity_usd_mm": round(equity, 2),
            "eps_actual": round(eps, 4),
            "sue": round(q["sue"], 4),
            "accrual_ratio": accrual,
            "roe_ttm": roe,
        }
        rows.append({**base, "version": 1, "is_restated": 0, "fcf_margin_ttm": fcf_v1})
        # 只有被标为 restated filer 的公司才会出现修订版, 且修订发生在原始版之后约一个季度.
        if zz["is_restated_filer"] == 1 and abs(fcf_v2 - fcf_v1) > 1e-6:
            rows.append({
                **base,
                "publish_date": q["publish_date"] + timedelta(days=random.randint(78, 132)),
                "version": 2,
                "is_restated": 1,
                "fcf_margin_ttm": fcf_v2,
                "net_income_usd_mm": round(net_income * random.uniform(0.94, 1.07), 2),
            })

    df = pl.DataFrame(rows, infer_schema_length=None).sort("asset_id", "fiscal_period_end", "version")
    # PIT 纪律: 这是一个"截止到 REFERENCE_DATE 的时点数据仓库", 里面不可能存着
    # 参考日之后才公布的财报. 最后一个财季的原始版和临近参考日的修订版都会落在
    # 参考日之后, 全部剔除. 所有查询都带 publish_date <= obs_date, 所以剔除它们
    # 不改变任何查询结果, 但能让 SELECT MAX(publish_date) 说得通.
    df = df.filter(pl.col("publish_date") <= REFERENCE_DATE)
    return df.with_row_index("id", offset=1).select(
        "id", "asset_id", "fiscal_period_end", "publish_date", "version", "is_restated",
        "revenue_usd_mm", "net_income_usd_mm", "operating_cash_flow_usd_mm", "capex_usd_mm",
        "total_equity_usd_mm", "eps_actual", "sue", "accrual_ratio", "fcf_margin_ttm", "roe_ttm",
    )


def gen_analyst_estimates(panel: pl.DataFrame, assets: pl.DataFrame) -> pl.DataFrame:
    """卖方一致预期的月度快照. EPS 修正类因子 (H02) 的原料."""
    sizeq = {r["id"]: r["size_quintile"] for r in assets.to_dicts()}
    rev_c, rev_s = RAW_VALUE_SCALE["EPS_REV_60D"]
    rows = []
    src = panel.filter(pl.col("asset_class_id") == 1).select(
        "asset_id", "obs_date", "z_EPS_REV_60D", "z_QUA_ROE"
    ).to_dicts()
    for r in src:
        q = sizeq.get(r["asset_id"], 3)
        # 覆盖分析师数量与市值强相关: 大盘股 20+ 人跟, 微盘股常常只有 1-2 人.
        # 用 round 而不是 int 截断 —— int() 会把每一档的均值系统性压低约 0.5 人.
        n_an = max(1, round(random.gauss(2.5 + 4.6 * q, 2.2)))
        rev1 = rev_c + rev_s * r["z_EPS_REV_60D"]
        rows.append({
            "asset_id": r["asset_id"],
            "as_of_date": r["obs_date"],
            # 一致预期数据商在月末后两天发布汇总, 所以它也带一个 (很短的) 发布滞后.
            "publish_date": r["obs_date"] + timedelta(days=2),
            "num_analysts": n_an,
            "fy1_eps_mean": round(max(0.05, 2.4 + 1.6 * r["z_QUA_ROE"] + random.gauss(0, 0.4)), 4),
            "eps_revision_1m": round(rev1, 5),
            "eps_revision_3m": round(rev1 * random.uniform(1.4, 2.6) + random.gauss(0, 0.006), 5),
            "rating_mean": round(min(max(3.0 - 0.42 * r["z_EPS_REV_60D"] + random.gauss(0, 0.25), 1.0), 5.0), 2),
        })
    return pl.DataFrame(rows).with_row_index("id", offset=1).select(
        "id", "asset_id", "as_of_date", "publish_date", "num_analysts",
        "fy1_eps_mean", "eps_revision_1m", "eps_revision_3m", "rating_mean",
    )


def gen_factor_exposures(panel: pl.DataFrame, factors: pl.DataFrame) -> pl.DataFrame:
    """月末因子暴露. 全库第二大的表.

    每个因子在每个在池标的上都有一行. quintile 1 = 打分最低, 5 = 最高;
    分层单调性检验就是按这一列分组算下期收益.
    """
    lag_by_code = {r["code"]: FACTOR_DATA_LAG_DAYS[r["lag_convention"]] for r in factors.to_dicts()}
    fid_by_code = {r["code"]: r["id"] for r in factors.to_dicts()}

    # 只过滤一次, 后面每个因子都从这同一个帧里 select 出 (asset_id, obs_date, z_*).
    # 早先的写法是过滤两次、再用位置赋值把第二个帧的 Series 塞进第一个帧, 只要
    # 任何一次排序或惰性重排就会静默打乱全部 78 万行暴露, 而且不会报错.
    eqp = panel.filter(pl.col("asset_class_id") == 1)
    parts = []
    for code in [f[0] for f in FACTOR_DEFS]:
        center, scale = RAW_VALUE_SCALE[code]
        part = eqp.select(
            "asset_id", "obs_date",
            pl.lit(fid_by_code[code]).cast(pl.Int64).alias("factor_id"),
            pl.col(f"z_{code}").alias("z_score"),
        ).with_columns(
            (pl.col("obs_date") - pl.duration(days=lag_by_code[code])).alias("data_asof_date"),
            (pl.lit(center) + pl.lit(scale) * pl.col("z_score")).alias("raw_value"),
        )
        parts.append(part)

    df = pl.concat(parts)
    df = df.with_columns(
        ((pl.col("z_score").rank("ordinal").over("factor_id", "obs_date") - 1)
         / (pl.len().over("factor_id", "obs_date") - 1)).alias("rank_pct")
    ).with_columns(
        (pl.col("rank_pct").mul(5).floor().clip(0, 4) + 1).cast(pl.Int64).alias("quintile")
    )
    return df.sort("factor_id", "obs_date", "asset_id").with_row_index("id", offset=1).select(
        "id", "factor_id", "asset_id", "obs_date", "data_asof_date",
        pl.col("raw_value").round(6), pl.col("z_score").round(6),
        pl.col("rank_pct").round(6), "quintile",
    )


def _cost_bps_per_unit_turnover(spread_bps: float, adv_usd: float, dollars_per_name: float) -> float:
    """单位换手的单边成本 (bps) = 半价差 + 冲击成本 + 佣金.

    冲击成本按参与度的平方根缩放 —— 这是买方 TCA 里最通用的平方根冲击模型.
    参与度 = 单只标的要成交的金额 / 该标的的 20 日平均成交额.
    """
    participation = min(max(dollars_per_name / max(adv_usd, 1.0), 0.0005), 1.5)
    impact = IMPACT_COEF * spread_bps * math.sqrt(participation)
    return 0.5 * spread_bps + impact + COMMISSION_BPS


def gen_factor_ic_monthly(
    panel: pl.DataFrame,
    factors: pl.DataFrame,
    regime_by_month: dict[int, int],
) -> tuple[pl.DataFrame, dict]:
    """Model Validation 组口径的月度 RankIC.

    这张表是 Agent 无法操纵的裁判: 它由统一的评价流水线算出来, 口径固定为
    "月末因子排名 vs 下一个自然月的总收益的 Spearman 相关系数"
    (月末复权价->下月末复权价的总收益, 不做 beta 调整, 即代码里的 fwd_total_return).
    同时返回一份给验证报告用的中间统计量.
    """
    fid_by_code = {r["code"]: r["id"] for r in factors.to_dicts()}
    eq = panel.filter((pl.col("asset_class_id") == 1) & pl.col("fwd_total_return").is_not_null())

    parts = []
    for code in [f[0] for f in FACTOR_DEFS]:
        parts.append(eq.select(
            pl.lit(fid_by_code[code]).cast(pl.Int64).alias("factor_id"),
            "asset_id", "month_index", "obs_date",
            pl.col("fwd_total_return").alias("fwd_excess_return"),
            "mcap_rank", "spread_bps", "adv_usd",
            pl.col(f"z_{code}").alias("z_score"),
        ))
    long = pl.concat(parts)

    universes = {
        1: pl.lit(True),
        2: pl.col("mcap_rank") <= 500,
        3: pl.col("mcap_rank") > pl.col("mcap_rank").max().over("month_index") - 250,
    }

    out_frames = []
    aux: dict = {}
    for uid, cond in universes.items():
        d = long.filter(cond)
        d = d.with_columns(
            pl.col("z_score").rank("average").over("factor_id", "month_index").alias("rz"),
            pl.col("fwd_excess_return").rank("average").over("factor_id", "month_index").alias("rf"),
            ((pl.col("z_score").rank("ordinal").over("factor_id", "month_index") - 1)
             / (pl.len().over("factor_id", "month_index") - 1)).alias("rpct"),
        ).with_columns(
            (pl.col("rpct").mul(5).floor().clip(0, 4) + 1).cast(pl.Int64).alias("q")
        )
        ic = d.group_by("factor_id", "month_index").agg(
            pl.corr("rz", "rf").alias("rank_ic"),
            pl.len().alias("n_assets"),
            pl.col("obs_date").first(),
        )
        legs = d.filter(pl.col("q").is_in([1, 5])).group_by("factor_id", "month_index", "q").agg(
            pl.col("fwd_excess_return").mean().alias("mret"),
            pl.col("spread_bps").mean().alias("mspread"),
            pl.col("adv_usd").median().alias("madv"),
            pl.len().alias("leg_n"),
        )
        wide = legs.pivot(on="q", index=["factor_id", "month_index"], values="mret")
        # pivot 出来的列顺序取决于数据中先遇到哪个分层, 不同池子可能不一致.
        # 这里显式定序, 否则三个池子的结果 concat 不到一起.
        wide = wide.rename({"1": "q1", "5": "q5"}).select(
            "factor_id", "month_index", "q1", "q5"
        ).with_columns(
            (pl.col("q5") - pl.col("q1")).alias("q5_minus_q1")
        )
        basket = legs.group_by("factor_id", "month_index").agg(
            pl.col("mspread").mean().alias("basket_spread_bps"),
            pl.col("madv").mean().alias("basket_adv_usd"),
            pl.col("leg_n").sum().alias("basket_n"),
        )

        # 换手率: 本月 Q5 篮子里有多大比例是上个月不在 Q5 的新面孔.
        q5sets: dict[tuple[int, int], set[int]] = {}
        for r in d.filter(pl.col("q") == 5).select("factor_id", "month_index", "asset_id").to_dicts():
            q5sets.setdefault((r["factor_id"], r["month_index"]), set()).add(r["asset_id"])
        turn_rows = []
        for (fid, m), cur in q5sets.items():
            prev = q5sets.get((fid, m - 1))
            t = 1.0 if prev is None else (1.0 - len(cur & prev) / max(len(cur), 1))
            turn_rows.append({"factor_id": fid, "month_index": m, "monthly_turnover": round(t, 6)})
        turn = pl.DataFrame(turn_rows)

        frame = (
            ic.join(wide, on=["factor_id", "month_index"])
            .join(turn, on=["factor_id", "month_index"])
            .join(basket, on=["factor_id", "month_index"])
            .with_columns(
                pl.lit(uid).cast(pl.Int64).alias("universe_id"),
                pl.col("month_index").replace_strict(regime_by_month, default=1)
                .cast(pl.Int64).alias("regime_type_id"),
                pl.lit(21).cast(pl.Int64).alias("fwd_horizon_days"),
            )
        )
        frame = frame.filter(
            pl.col("rank_ic").is_not_null() & pl.col("rank_ic").is_not_nan()
        ).select(
            "factor_id", "month_index", "obs_date", "universe_id", "regime_type_id",
            "rank_ic", "n_assets", "fwd_horizon_days", "q1", "q5", "q5_minus_q1",
            "monthly_turnover", "basket_spread_bps", "basket_adv_usd", "basket_n",
        )
        out_frames.append(frame)
        aux[uid] = frame

    # 极少数 (因子, 月份) 组合里横截面方差为零, Spearman 相关系数无从定义.
    # 这类观测直接剔除, 而不是填 0 —— 填 0 会把"没有信息"伪装成"没有预测力".
    full = pl.concat(out_frames).filter(
        pl.col("rank_ic").is_not_null() & pl.col("rank_ic").is_not_nan()
    ).sort("factor_id", "universe_id", "month_index")
    df = full.with_row_index("id", offset=1).select(
        "id", "factor_id", "universe_id", "obs_date", "regime_type_id",
        pl.col("rank_ic").round(6), "n_assets", "fwd_horizon_days",
        pl.col("q5_minus_q1").round(6).alias("q5_minus_q1_return"),
        pl.col("monthly_turnover").round(6),
    )
    return df, aux


def _stats(values: list[float]) -> tuple[float, float]:
    """均值与样本标准差."""
    n = len(values)
    if n < 2:
        return (values[0] if values else 0.0), 0.0
    mu = sum(values) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in values) / (n - 1))
    return mu, sd


def _max_drawdown(monthly: list[float]) -> float:
    """按月度收益序列算最大回撤 (返回正数)."""
    peak = 1.0
    nav = 1.0
    mdd = 0.0
    for r in monthly:
        nav *= (1.0 + r)
        peak = max(peak, nav)
        mdd = max(mdd, (peak - nav) / peak)
    return mdd


def _capacity_usd_mm(gross_ann: float, annual_turnover: float, spread_bps: float,
                     adv_usd: float, basket_n: int) -> float:
    """容量 (百万美元). 取两条约束里更紧的那一条.

    约束一 (成本): 冲击成本吃掉一半毛 alpha 时的资金规模, 二分搜索求解.
    约束二 (建仓): 在参与度上限内, 一个月能建起来的最大仓位.
    真实的容量瓶颈往往是第二条 —— 微盘股上再高的 alpha, 也塞不进去钱.
    """
    if gross_ann <= 0 or annual_turnover <= 0 or basket_n <= 0:
        return 0.0
    lo, hi = 1.0, 50_000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        per_name = mid * 1_000_000.0 / basket_n
        cost = annual_turnover * _cost_bps_per_unit_turnover(spread_bps, adv_usd, per_name) / 10_000.0
        if cost < 0.5 * gross_ann:
            lo = mid
        else:
            hi = mid
    build_limit = (CAPACITY_ADV_PARTICIPATION * adv_usd * basket_n
                   * CAPACITY_BUILD_DAYS / 1_000_000.0)
    return round(min(lo, build_limit), 1)


def gen_factor_validation_runs(
    ic_aux: dict,
    factors: pl.DataFrame,
    month_ends: list[date],
    trial_by_code: dict[str, int],
) -> pl.DataFrame:
    """Model Validation 组出具的正式验证结论.

    结构不是"每个因子 × 每个池子 × 每个窗口"的满笛卡尔积: universe 1 上 16 个
    因子各跑三个窗口 (FULL / IN_SAMPLE / OUT_OF_SAMPLE) = 48 行, universe 2 与
    universe 3 上只跑 FULL 窗口、且只对 10 个候选因子跑 = 各 10 行, 合计 68 行.
    6 个生产因子在 US_LARGE_500 / US_MICRO_250 上没有验证行 —— 生产因子早就上线
    了, 验证组不会为它们重复做池子拆分.

    判定规则写死在 VALIDATION_* 常量里, 研究员改不了 —— 这正是把"算分"从"建模"
    里拿走的制度设计.
    """
    code_by_id = {r["id"]: r["code"] for r in factors.to_dicts()}
    prod_ids = {r["id"] for r in factors.to_dicts() if r["status"] == "production"}

    def _corr(a: list[float], b: list[float]) -> float:
        n = min(len(a), len(b))
        if n < 3:
            return 0.0
        ma, sa = _stats(a[:n])
        mb, sb = _stats(b[:n])
        if sa < 1e-12 or sb < 1e-12:
            return 0.0
        cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)
        return cov / (sa * sb)

    # 与生产因子库的 IC 序列相关性必须在"这一行所属的那个池子"上算.
    # 在全池上测出来的相关系数, 不能拿去当微盘池上那一行的否决依据 ——
    # 换个池子, 两个因子的共同暴露完全可能不一样.
    max_corr_by_universe: dict[int, dict[int, float]] = {}
    series_by_universe: dict[int, dict[int, list[float]]] = {}
    for uid in (1, 2, 3):
        base = ic_aux[uid].sort("factor_id", "month_index")
        series: dict[int, list[float]] = {}
        for r in base.select("factor_id", "month_index", "rank_ic").to_dicts():
            series.setdefault(r["factor_id"], []).append(r["rank_ic"] or 0.0)
        series_by_universe[uid] = series
        mc: dict[int, float] = {}
        for fid, s in series.items():
            peers = [p for p in prod_ids if p != fid]
            mc[fid] = max((abs(_corr(s, series[p])) for p in peers if p in series), default=0.0)
        max_corr_by_universe[uid] = mc
    series = series_by_universe[1]

    jobs = []
    for uid in (1, 2, 3):
        frame = ic_aux[uid]
        for fid in sorted(series.keys()):
            windows = [("FULL", 0, len(month_ends))]
            if uid == 1:
                windows += [("IN_SAMPLE", 0, IN_SAMPLE_LAST_MONTH + 1),
                            ("OUT_OF_SAMPLE", IN_SAMPLE_LAST_MONTH + 1, len(month_ends))]
            elif code_by_id[fid] not in CANDIDATE_FACTORS:
                continue
            for wname, lo, hi in windows:
                jobs.append((uid, fid, wname, lo, hi, frame))

    rows = []
    for uid, fid, wname, lo, hi, frame in jobs:
        sub = frame.filter(
            (pl.col("factor_id") == fid) & (pl.col("month_index") >= lo) & (pl.col("month_index") < hi)
        ).sort("month_index")
        if sub.height < 6:
            continue
        d = sub.to_dicts()
        ics = [r["rank_ic"] or 0.0 for r in d]
        q51 = [r["q5_minus_q1"] or 0.0 for r in d]
        turns = [r["monthly_turnover"] for r in d]
        spread = sum(r["basket_spread_bps"] for r in d) / len(d)
        adv = sum(r["basket_adv_usd"] for r in d) / len(d)
        basket_n = int(sum(r["basket_n"] for r in d) / len(d))

        ic_mu, ic_sd = _stats(ics)
        n = len(ics)
        icir = ic_mu / ic_sd if ic_sd > 1e-9 else 0.0
        tstat = ic_mu / (ic_sd / math.sqrt(n)) if ic_sd > 1e-9 else 0.0
        hit = sum(1 for v in ics if v > 0) / n

        # 年化换手按双边计: 多头腿换掉的部分要卖出再买入, 空头腿同理.
        ann_turnover = ((sum(turns) / len(turns)) * 12.0 * 2.0
                        * REBALANCE_PER_MONTH.get(code_by_id[fid], 1.0))
        per_name = ASSUMED_STRATEGY_AUM_USD_MM * 1_000_000.0 / max(basket_n, 1)
        cost_unit = _cost_bps_per_unit_turnover(spread, adv, per_name)
        cost_ann_bps = ann_turnover * cost_unit

        gross_ann = (sum(q51) / len(q51)) * 12.0
        _, q_sd = _stats(q51)
        vol_ann = q_sd * math.sqrt(12.0)
        gross_ir = gross_ann / vol_ann if vol_ann > 1e-9 else 0.0
        net_ann = gross_ann - cost_ann_bps / 10_000.0
        net_ir = net_ann / vol_ann if vol_ann > 1e-9 else 0.0
        net_monthly = [v - cost_ann_bps / 10_000.0 / 12.0 for v in q51]
        mdd = _max_drawdown(net_monthly)

        # Deflated Sharpe: 先算 SR 的标准误 (Lo 2002), 再扣掉"试 N 次必然出现的最好那个".
        sr_m = (sum(net_monthly) / len(net_monthly)) / (q_sd if q_sd > 1e-9 else 1.0)
        se_sr = math.sqrt((1.0 + 0.5 * sr_m * sr_m) / n)
        trials = trial_by_code.get(code_by_id[fid], 1)
        expected_max = se_sr * math.sqrt(2.0 * math.log(max(trials, 2)))
        dsr = (sr_m - expected_max) / se_sr if se_sr > 1e-9 else 0.0

        capacity = _capacity_usd_mm(gross_ann, ann_turnover, spread, adv, basket_n)
        mcorr = max_corr_by_universe.get(uid, {}).get(fid, 0.0)
        applied_t = hlz_threshold(trials)

        if mcorr > VALIDATION_CORR_LIMIT:
            verdict, reason = "FAIL", "REDUNDANT_WITH_EXISTING"
        elif tstat < applied_t:
            verdict, reason = "FAIL", "FAILS_MULTIPLE_TESTING"
        elif capacity < VALIDATION_MIN_CAPACITY_MM:
            verdict, reason = "FAIL", "CAPACITY_CONSTRAINED"
        elif net_ir < VALIDATION_MIN_NET_IR:
            verdict, reason = "FAIL", "COST_PROHIBITIVE"
        elif net_ir < VALIDATION_CONDITIONAL_NET_IR:
            verdict, reason = "CONDITIONAL", None
        else:
            verdict, reason = "PASS", None

        rows.append({
            "factor_id": fid, "universe_id": uid, "window_type": wname,
            "sample_start": month_ends[lo], "sample_end": month_ends[min(hi, len(month_ends)) - 1],
            "n_months": n,
            "ic_mean": round(ic_mu, 6), "ic_std": round(ic_sd, 6), "icir": round(icir, 4),
            "ic_tstat": round(tstat, 4), "ic_hit_rate": round(hit, 4),
            "q5_q1_annual_return": round(gross_ann, 6),
            "annual_turnover": round(ann_turnover, 4),
            "cost_bps_annual": round(cost_ann_bps, 2),
            "gross_ir": round(gross_ir, 4), "net_ir": round(net_ir, 4),
            "max_drawdown": round(mdd, 5), "deflated_sharpe": round(dsr, 4),
            "max_corr_with_production": round(mcorr, 4),
            "capacity_usd_mm": capacity,
            "verdict": verdict, "fail_reason_code": reason,
            "validated_on": date(2026, 7, 9),
        })

    # --- 跨 regime / 跨池子的两条规则, 必须等全部行都算完才能应用 ---
    # 它们改写的只有 universe=1 且 window=FULL 的那一行, 也就是对外发布的那份结论.
    regime_ic: dict[int, list[float]] = {}
    for r in ic_aux[1].group_by("factor_id", "regime_type_id").agg(
        pl.col("rank_ic").mean().alias("ic"), pl.len().alias("n")
    ).filter(pl.col("n") >= 5).to_dicts():
        regime_ic.setdefault(r["factor_id"], []).append(r["ic"])

    small = {r["factor_id"]: r for r in rows if r["universe_id"] == 3 and r["window_type"] == "FULL"}
    allcap = {r["factor_id"]: r for r in rows if r["universe_id"] == 1 and r["window_type"] == "FULL"}

    for r in rows:
        if r["universe_id"] != 1 or r["window_type"] != "FULL":
            continue
        if r["fail_reason_code"] == "REDUNDANT_WITH_EXISTING":
            continue
        ics = regime_ic.get(r["factor_id"], [])
        # 符号翻转: 一个方向随环境变号的因子, 本质是在赌 regime, 不是 alpha.
        if ics and max(ics) > 0.02 and min(ics) < -0.02:
            r["verdict"], r["fail_reason_code"] = "FAIL", "REGIME_DEPENDENT"
            continue
        sm = small.get(r["factor_id"])
        ac = allcap.get(r["factor_id"])
        # 容量陷阱: 效果几乎全在小市值端, 而小市值端根本装不下钱.
        if sm and ac and ac["ic_mean"] > 0 and sm["ic_mean"] > 2.0 * ac["ic_mean"] \
                and sm["capacity_usd_mm"] < VALIDATION_MIN_CAPACITY_MM:
            r["verdict"], r["fail_reason_code"] = "FAIL", "CAPACITY_CONSTRAINED"

    return pl.DataFrame(rows, infer_schema_length=None).with_row_index("id", offset=1).select(
        "id", "factor_id", "universe_id", "window_type", "sample_start", "sample_end", "n_months",
        "ic_mean", "ic_std", "icir", "ic_tstat", "ic_hit_rate", "q5_q1_annual_return",
        "annual_turnover", "cost_bps_annual", "gross_ir", "net_ir", "max_drawdown",
        "deflated_sharpe", "max_corr_with_production", "capacity_usd_mm", "verdict",
        "fail_reason_code", "validated_on",
    )


def gen_covariance_estimates(month_ends: list[date], regime_by_month: dict[int, int],
                             regime_code_by_month: dict[int, str]) -> pl.DataFrame:
    """月末协方差估计的元数据.

    T9 陷阱在这里: 250 天回看 x 500 只标的意味着 T/N = 0.5, 样本协方差必然奇异.
    在 regime 切换的头两个月, 样本法预测的波动率会严重低估实际波动.
    """
    rows = []
    stress_start_idx = min(m for m, c in regime_code_by_month.items() if c == "HIGH_VOL_STRESS")
    for m, me in enumerate(month_ends):
        code = regime_code_by_month[m]
        base_vol = dict((n, v) for _, n, v in REGIME_SCHEDULE)[code]
        # regime 刚切换到压力期的头两个月, 回看窗口里全是平静期的数据 -> 低估风险.
        in_stress_onset = code == "HIGH_VOL_STRESS" and m - stress_start_idx < 2
        for method in ("sample", "ledoit_wolf", "oas", "factor_model"):
            bias = (COV_STRESS_BIAS if in_stress_onset else COV_NORMAL_BIAS)[method]
            bias *= random.uniform(0.94, 1.06)
            realized = base_vol * random.uniform(0.92, 1.10)
            predicted = realized / bias
            rows.append({
                "universe_id": 2,
                "as_of_date": me,
                "regime_type_id": regime_by_month[m],
                "method": method,
                "lookback_days": COV_LOOKBACK_DAYS,
                "halflife_days": 0 if method == "sample" else 90,
                "n_assets": COV_UNIVERSE_N,
                "t_over_n": round(COV_LOOKBACK_DAYS / COV_UNIVERSE_N, 4),
                # 收缩强度是一个比例, 上限就是 1.0 (完全用目标矩阵). 抖动之后必须
                # 截回来, 否则 factor_model 会出现 1.09 这种没有数学含义的值.
                "shrinkage_intensity": round(
                    min(COV_SHRINKAGE_INTENSITY[method] * random.uniform(0.9, 1.1), 1.0), 4),
                "condition_number": round(COV_CONDITION_NUMBER[method] * random.uniform(0.8, 1.3), 1),
                "is_singular": 1 if method == "sample" else 0,
                "avg_pairwise_corr": round(
                    {"RECOVERY": 0.26, "LOW_VOL_BULL": 0.19, "HIGH_VOL_STRESS": 0.58,
                     "RISING_RATE": 0.33}[code] * random.uniform(0.92, 1.08), 4),
                "predicted_vol_ann": round(predicted, 5),
                "realized_vol_ann_next": round(realized, 5),
                "vol_bias_ratio": round(realized / predicted, 4),
            })
    return pl.DataFrame(rows).with_row_index("id", offset=1).select(
        "id", "universe_id", "as_of_date", "regime_type_id", "method", "lookback_days",
        "halflife_days", "n_assets", "t_over_n", "shrinkage_intensity", "condition_number",
        "is_singular", "avg_pairwise_corr", "predicted_vol_ann", "realized_vol_ann_next",
        "vol_bias_ratio",
    )


def gen_backtests(
    ic_aux: dict,
    factors: pl.DataFrame,
    validations: pl.DataFrame,
    month_ends: list[date],
    regime_by_month: dict[int, int],
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """回测与其月度明细.

    单因子回测直接复用 Model Validation 算出来的 Q5-Q1 序列, 保证"回测里的数字"
    和"验证报告里的数字"天然对得上 —— 现实中两边对不上是最常见的事故来源.
    复合信号的回测则按 CONSTRAINT_NET_IR 校准, 用来量化 T10 约束侵蚀.
    """
    code_by_id = {r["id"]: r["code"] for r in factors.to_dicts()}
    fid_by_code = {r["code"]: r["id"] for r in factors.to_dicts()}
    frame = ic_aux[1].sort("factor_id", "month_index")
    by_factor: dict[int, list[dict]] = {}
    for r in frame.to_dicts():
        by_factor.setdefault(r["factor_id"], []).append(r)

    vmap = {(r["factor_id"], r["window_type"]): r
            for r in validations.filter(pl.col("universe_id") == 1).to_dicts()}

    runs = []
    monthly = []
    run_id = 0

    def _emit(series: list[tuple[int, float, float]], run_row: dict) -> None:
        """写入一次回测的 run 行与月度明细行. series = (month_index, gross, net)."""
        nav = 1.0
        peak = 1.0
        for m, g, nt in series:
            nav *= (1.0 + nt)
            peak = max(peak, nav)
            monthly.append({
                "backtest_run_id": run_row["id"],
                "month_end": month_ends[m],
                "regime_type_id": regime_by_month[m],
                "gross_return": round(g, 6),
                "net_return": round(nt, 6),
                "benchmark_return": 0.0,
                "active_return": round(nt, 6),
                "turnover": round(run_row["annual_turnover"] / 24.0, 6),
                "cost_bps": round((g - nt) * 10_000.0, 3),
                "drawdown": round((peak - nav) / peak, 6),
            })
        runs.append(run_row)

    windows = {
        "FULL": (0, len(month_ends)),
        "IN_SAMPLE": (0, IN_SAMPLE_LAST_MONTH + 1),
        "OUT_OF_SAMPLE": (IN_SAMPLE_LAST_MONTH + 1, len(month_ends)),
    }
    for fid in sorted(by_factor.keys()):
        for wname, (lo, hi) in windows.items():
            v = vmap.get((fid, wname))
            if v is None:
                continue
            rows_w = [r for r in by_factor[fid] if lo <= r["month_index"] < hi]
            if len(rows_w) < 6:
                continue
            cost_m = v["cost_bps_annual"] / 10_000.0 / 12.0
            series = [(r["month_index"], r["q5_minus_q1"] or 0.0,
                       (r["q5_minus_q1"] or 0.0) - cost_m) for r in rows_w]
            run_id += 1
            _emit(series, {
                "id": run_id,
                "run_code": f"BT-{code_by_id[fid]}-{wname}",
                "factor_id": fid, "is_composite": 0, "universe_id": 1, "constraint_set_id": 1,
                "cov_method": "ledoit_wolf", "window_type": wname,
                "start_date": month_ends[lo], "end_date": month_ends[min(hi, len(month_ends)) - 1],
                "n_rebalances": len(series),
                "gross_return_ann": v["q5_q1_annual_return"],
                "net_return_ann": round(v["q5_q1_annual_return"] - v["cost_bps_annual"] / 10_000.0, 6),
                "active_vol_ann": round(
                    v["q5_q1_annual_return"] / v["gross_ir"] if abs(v["gross_ir"]) > 1e-6 else 0.05, 5),
                "gross_ir": v["gross_ir"], "net_ir": v["net_ir"],
                "max_drawdown": v["max_drawdown"],
                "annual_turnover": v["annual_turnover"],
                "cost_bps_annual": v["cost_bps_annual"],
                "tracking_error": round(
                    abs(v["q5_q1_annual_return"] / v["gross_ir"]) if abs(v["gross_ir"]) > 1e-6 else 0.05, 5),
            })

    # --- 复合信号: 四个入围因子等权合成, 分别过四套约束 ---
    promoted_ids = [fid_by_code[c] for c in PROMOTED_FACTORS]
    n_m = len(month_ends)
    comp_raw = []
    for m in range(n_m):
        vals = []
        for fid in promoted_ids:
            hit = [r for r in by_factor.get(fid, []) if r["month_index"] == m]
            if hit:
                vals.append(hit[0]["q5_minus_q1"] or 0.0)
        if vals:
            comp_raw.append((m, sum(vals) / len(vals)))
    _, comp_sd = _stats([v for _, v in comp_raw])
    comp_mu = sum(v for _, v in comp_raw) / len(comp_raw)
    vol_ann = comp_sd * math.sqrt(12.0)

    cs_ids = {"UNCONSTRAINED": 1, "SECTOR_NEUTRAL": 2, "LIQUIDITY_TIGHT": 3, "FULL_PRODUCTION": 4}
    for cs_code, target_ir in CONSTRAINT_NET_IR.items():
        target_m = target_ir * vol_ann / 12.0
        # 约束越紧, 换手上限越低, 成本也越低 —— 但 alpha 被削掉得更多.
        turn = {"UNCONSTRAINED": 3.10, "SECTOR_NEUTRAL": 2.85,
                "LIQUIDITY_TIGHT": 1.90, "FULL_PRODUCTION": 1.15}[cs_code]
        cost_m = turn * COMPOSITE_COST_BPS_PER_UNIT / 10_000.0 / 12.0
        series = [(m, v - comp_mu + target_m + cost_m, v - comp_mu + target_m) for m, v in comp_raw]
        gross_ann = (sum(g for _, g, _ in series) / len(series)) * 12.0
        net_ann = (sum(nt for _, _, nt in series) / len(series)) * 12.0
        run_id += 1
        _emit(series, {
            "id": run_id,
            "run_code": f"BT-ATLAS-COMPOSITE-{cs_code}",
            "factor_id": None, "is_composite": 1, "universe_id": 2,
            "constraint_set_id": cs_ids[cs_code],
            "cov_method": "ledoit_wolf", "window_type": "FULL",
            "start_date": month_ends[0], "end_date": month_ends[-1],
            "n_rebalances": len(series),
            "gross_return_ann": round(gross_ann, 6),
            "net_return_ann": round(net_ann, 6),
            "active_vol_ann": round(vol_ann, 5),
            "gross_ir": round(gross_ann / vol_ann, 4),
            "net_ir": round(net_ann / vol_ann, 4),
            "max_drawdown": round(_max_drawdown([nt for _, _, nt in series]), 5),
            "annual_turnover": turn,
            "cost_bps_annual": round(turn * COMPOSITE_COST_BPS_PER_UNIT, 2),
            "tracking_error": round(vol_ann, 5),
        })

    # --- 同一复合信号换四种协方差估计法做 walk-forward, 检验风险模型的影响 ---
    for method in ("sample", "ledoit_wolf", "oas", "factor_model"):
        # 协方差估不准会直接体现为实现波动偏离目标, 从而拉低 IR.
        penalty = {"sample": 0.58, "ledoit_wolf": 1.00, "oas": 1.02, "factor_model": 0.94}[method]
        target_m = CONSTRAINT_NET_IR["FULL_PRODUCTION"] * penalty * vol_ann / 12.0
        vol_scale = {"sample": 1.42, "ledoit_wolf": 1.00, "oas": 0.98, "factor_model": 1.05}[method]
        cost_m = 1.15 * COMPOSITE_COST_BPS_PER_UNIT / 10_000.0 / 12.0
        series = [(m, (v - comp_mu) * vol_scale + target_m + cost_m,
                   (v - comp_mu) * vol_scale + target_m) for m, v in comp_raw
                  if m > IN_SAMPLE_LAST_MONTH - 12]
        gross_ann = (sum(g for _, g, _ in series) / len(series)) * 12.0
        net_ann = (sum(nt for _, _, nt in series) / len(series)) * 12.0
        v_ann = vol_ann * vol_scale
        run_id += 1
        _emit(series, {
            "id": run_id,
            "run_code": f"BT-ATLAS-WALKFWD-{method.upper()}",
            "factor_id": None, "is_composite": 1, "universe_id": 2, "constraint_set_id": 4,
            "cov_method": method, "window_type": "WALK_FORWARD",
            "start_date": month_ends[IN_SAMPLE_LAST_MONTH - 11], "end_date": month_ends[-1],
            "n_rebalances": len(series),
            "gross_return_ann": round(gross_ann, 6),
            "net_return_ann": round(net_ann, 6),
            "active_vol_ann": round(v_ann, 5),
            "gross_ir": round(gross_ann / v_ann, 4),
            "net_ir": round(net_ann / v_ann, 4),
            "max_drawdown": round(_max_drawdown([nt for _, _, nt in series]), 5),
            "annual_turnover": 1.15,
            "cost_bps_annual": round(1.15 * COMPOSITE_COST_BPS_PER_UNIT, 2),
            "tracking_error": round(v_ann, 5),
        })

    runs_df = pl.DataFrame(runs, infer_schema_length=None).select(
        "id", "run_code", "factor_id", "is_composite", "universe_id", "constraint_set_id",
        "cov_method", "window_type", "start_date", "end_date", "n_rebalances",
        "gross_return_ann", "net_return_ann", "active_vol_ann", "gross_ir", "net_ir",
        "max_drawdown", "annual_turnover", "cost_bps_annual", "tracking_error",
    )
    monthly_df = pl.DataFrame(monthly, infer_schema_length=None).with_row_index("id", offset=1).select(
        "id", "backtest_run_id", "month_end", "regime_type_id", "gross_return", "net_return",
        "benchmark_return", "active_return", "turnover", "cost_bps", "drawdown",
    )
    return runs_df, monthly_df


def gen_portfolio_holdings(panel: pl.DataFrame, month_ends: list[date]) -> pl.DataFrame:
    """Atlas 复合信号的 paper 组合月末持仓.

    权重来自复合打分排序, 再套上 FULL_PRODUCTION 约束档的 2.5% 单票上限与
    5% 的 ADV 参与度上限. is_constraint_binding 标出哪些票被约束顶住了 ——
    这是"约束到底削掉了多少 alpha"这个问题的微观证据.
    """
    cols = [f"z_{c}" for c in PROMOTED_FACTORS]
    d = panel.filter(
        (pl.col("asset_class_id") == 1) & (pl.col("mcap_rank") <= 500)
    ).with_columns(
        (sum(pl.col(c) for c in cols) / len(cols)).alias("composite_score")
    )
    d = d.with_columns(
        pl.col("composite_score").rank("ordinal", descending=True).over("obs_date").alias("srank"),
        (pl.col("mcap") / pl.col("mcap").sum().over("obs_date")).alias("benchmark_weight"),
    ).filter(pl.col("srank") <= PAPER_PORTFOLIO_HOLDINGS)

    # 打分转权重: 先线性映射到正数, 再归一, 最后套上限并把溢出部分按比例摊回去.
    d = d.with_columns(
        (pl.col("composite_score") - pl.col("composite_score").min().over("obs_date") + 0.15).alias("raw_w")
    ).with_columns(
        (pl.col("raw_w") / pl.col("raw_w").sum().over("obs_date")).alias("w0")
    )
    # 截上限之后要重新归一, 而归一会把已经顶格的那几只重新推过 2.5% ——
    # 所以必须再截一次再归一 (标准优化器里的迭代投影). 只做一轮的话, 全表会
    # 留下一行 2.5010% 的越界权重, 而 2.5% 是一条硬上限.
    d = d.with_columns(pl.col("w0").clip(upper_bound=0.025).alias("w_cap"))
    for _ in range(3):
        d = d.with_columns(
            (pl.col("w_cap") / pl.col("w_cap").sum().over("obs_date"))
            .clip(upper_bound=0.025).alias("w_cap")
        )
    d = d.with_columns(
        (pl.col("w_cap") / pl.col("w_cap").sum().over("obs_date")).alias("weight"),
        (pl.col("w0") > 0.025).alias("cap_binding"),
    )
    # ADV 参与度约束: 单只票的目标持仓不能超过其 20 日平均成交额的 5%.
    d = d.with_columns(
        ((pl.col("weight") * ASSUMED_STRATEGY_AUM_USD_MM * 1_000_000.0)
         > (0.05 * pl.col("adv_usd") * 21.0)).alias("adv_binding")
    )
    d = d.with_columns(
        (pl.col("weight") - pl.col("benchmark_weight")).alias("active_weight"),
        (pl.col("cap_binding") | pl.col("adv_binding")).cast(pl.Int64).alias("is_constraint_binding"),
        pl.when(pl.col("cap_binding")).then(pl.lit("MAX_ASSET_WEIGHT"))
        .when(pl.col("adv_binding")).then(pl.lit("MAX_ADV_PARTICIPATION"))
        .otherwise(None).alias("binding_constraint_code"),
    )
    return d.sort("obs_date", "srank").with_row_index("id", offset=1).select(
        "id",
        pl.lit(3).cast(pl.Int64).alias("portfolio_id"),
        "asset_id",
        pl.col("obs_date").alias("as_of_date"),
        pl.col("weight").round(8),
        pl.col("benchmark_weight").round(8),
        pl.col("active_weight").round(8),
        pl.col("composite_score").round(6),
        "is_constraint_binding", "binding_constraint_code",
    )


def gen_attribution_monthly(
    holdings: pl.DataFrame,
    panel: pl.DataFrame,
    assets: pl.DataFrame,
    factors: pl.DataFrame,
    ic_aux: dict,
) -> pl.DataFrame:
    """月度归因: 把 paper 组合的主动收益拆成 factor 与 sector 两个维度.

    因子贡献 = 组合在该因子上的主动暴露 x 当月因子收益.
    这正好回答"我赚的到底是 alpha, 还是偷偷承担了某个风险因子的敞口".
    """
    fid_by_code = {r["code"]: r["id"] for r in factors.to_dicts()}
    sec_by_asset = {r["id"]: r["sector_id"] for r in assets.to_dicts()}

    # 因子当月收益: 用 Q5-Q1 除以两端平均 z 差 (约 2.8), 折算成"每单位 z 暴露"的收益.
    fac_ret: dict[tuple[int, date], float] = {}
    for r in ic_aux[1].to_dicts():
        fac_ret[(r["factor_id"], r["obs_date"])] = (r["q5_minus_q1"] or 0.0) / 2.8

    zcols = [f"z_{f[0]}" for f in FACTOR_DEFS]
    h = holdings.join(
        panel.select(["asset_id", "obs_date", *zcols]),
        left_on=["asset_id", "as_of_date"], right_on=["asset_id", "obs_date"], how="left",
    )

    rows = []
    for code in [f[0] for f in FACTOR_DEFS]:
        fid = fid_by_code[code]
        agg = h.group_by("as_of_date").agg(
            (pl.col("active_weight") * pl.col(f"z_{code}")).sum().alias("expo")
        ).to_dicts()
        for r in agg:
            fr = fac_ret.get((fid, r["as_of_date"]), 0.0)
            rows.append({
                "portfolio_id": 3, "month_end": r["as_of_date"], "attribution_type": "factor",
                "factor_id": fid, "sector_id": None,
                "return_contribution_bps": round(r["expo"] * fr * 10_000.0, 4),
                "risk_contribution_pct": abs(r["expo"]),
                "avg_active_exposure": round(r["expo"], 6),
            })

    hs = holdings.with_columns(
        pl.col("asset_id").replace_strict(sec_by_asset, default=None).alias("sector_id")
    )
    sec_ret = {}
    for r in ic_aux[1].filter(pl.col("factor_id") == 1).to_dicts():
        sec_ret[r["obs_date"]] = r["q5_minus_q1"] or 0.0
    for r in hs.group_by("as_of_date", "sector_id").agg(
        pl.col("active_weight").sum().alias("aw")
    ).to_dicts():
        if r["sector_id"] is None:
            continue
        # 板块收益用一个与当月市场同向的小幅随机项代表, 板块间彼此不同.
        sr = sec_ret.get(r["as_of_date"], 0.0) * random.uniform(-1.4, 1.4) + random.gauss(0, 0.004)
        rows.append({
            "portfolio_id": 3, "month_end": r["as_of_date"], "attribution_type": "sector",
            "factor_id": None, "sector_id": r["sector_id"],
            "return_contribution_bps": round(r["aw"] * sr * 10_000.0, 4),
            "risk_contribution_pct": abs(r["aw"]),
            "avg_active_exposure": round(r["aw"], 6),
        })

    df = pl.DataFrame(rows, infer_schema_length=None)
    # risk_contribution_pct 在每个 (月份, 归因维度) 内部归一到 100%.
    df = df.with_columns(
        (pl.col("risk_contribution_pct") * 100.0
         / pl.col("risk_contribution_pct").sum().over("month_end", "attribution_type"))
        .round(4).alias("risk_contribution_pct")
    )
    return df.sort("month_end", "attribution_type").with_row_index("id", offset=1).select(
        "id", "portfolio_id", "month_end", "attribution_type", "factor_id", "sector_id",
        "return_contribution_bps", "risk_contribution_pct", "avg_active_exposure",
    )


# Atlas Agent 在每一步真实生成并执行的 SQL 模板. app 端可以直接把这些语句
# 作为 few-shot 示例喂给模型, 也可以拿来做回归测试.
AGENT_SQL_TEMPLATES = {
    "scope_universe": """SELECT c.year_month,
       COUNT(DISTINCT b.asset_id) AS live_names,
       ROUND(AVG(b.market_cap_usd_mm), 1) AS avg_mcap_usd_mm,
       ROUND(AVG(b.bid_ask_spread_bps), 2) AS avg_spread_bps
FROM daily_bar b
JOIN trading_calendar c ON c.trade_date = b.trade_date
JOIN asset a ON a.id = b.asset_id
WHERE c.is_month_end = 1 AND a.asset_class_id = 1
GROUP BY c.year_month
ORDER BY c.year_month;""",
    # 日期在 SQLite 里存成 TEXT, 直接相减会把两边都数值强转成年份而恒得 0,
    # 必须先过 JULIANDAY. 这条模板会被 app 当 few-shot 素材喂给模型, 所以它
    # 自己不能踩这个坑.
    "build_factor": """SELECT COUNT(*) AS n_scored,
       COUNT(DISTINCT fe.obs_date) AS n_month_ends,
       ROUND(AVG(fe.raw_value), 5) AS avg_raw,
       ROUND(AVG(fe.z_score), 6) AS avg_z,
       MIN(fe.quintile) AS min_q,
       MAX(fe.quintile) AS max_q,
       ROUND(MAX(JULIANDAY(fe.obs_date) - JULIANDAY(fe.data_asof_date)), 0) AS max_data_lag_days
FROM factor_exposure fe
JOIN factor f ON f.id = fe.factor_id
WHERE f.code = '{code}';""",
    "compute_ic": """SELECT COUNT(*) AS n_months,
       ROUND(AVG(i.rank_ic), 6) AS rank_ic_mean,
       ROUND(SQRT(AVG(i.rank_ic * i.rank_ic) - AVG(i.rank_ic) * AVG(i.rank_ic))
             * SQRT(COUNT(*) * 1.0 / (COUNT(*) - 1)), 6) AS rank_ic_std,
       ROUND(100.0 * SUM(CASE WHEN i.rank_ic > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS hit_rate_pct
FROM factor_ic_monthly i
JOIN factor f ON f.id = i.factor_id
WHERE f.code = '{code}' AND i.universe_id = 1;""",
    # H03 第一遍: 从 fundamental_report 重建 SUE, 用 fiscal_period_end 做 as-of
    # 过滤 (常见的错误口径). 这一步还没有意识到有 publish_date 这回事.
    "pead_ic_naive": """WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
asof AS (
    SELECT m.asset_id, m.obs_date, fr.sue,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.fiscal_period_end DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.fiscal_period_end <= m.obs_date
),
paired AS (
    SELECT fw.obs_date, fw.fwd_ret, a.sue
    FROM fwd fw
    JOIN asof a ON a.asset_id = fw.asset_id AND a.obs_date = fw.obs_date AND a.rn = 1
    WHERE fw.fwd_ret IS NOT NULL
),
ranked AS (
    SELECT obs_date,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY fwd_ret) AS rr,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY sue)     AS rs
    FROM paired
),
per_month AS (
    SELECT obs_date,
           (AVG(rs*rr) - AVG(rs)*AVG(rr))
             / (SQRT(AVG(rs*rs)-AVG(rs)*AVG(rs)) * SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic
    FROM ranked GROUP BY obs_date
)
SELECT COUNT(*) AS n_months, ROUND(AVG(ic), 6) AS rank_ic_mean_naive
FROM per_month;""",
    # H03 第二遍: 同一份数据, 两种 as-of 规则并排算, 只在两边都有值的共同样本上
    # 比较 —— 一次只动一个变量, 差异才归因于口径本身.
    "pead_ic_asof_compare": """WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
leaky AS (
    SELECT m.asset_id, m.obs_date, fr.sue,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.fiscal_period_end DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.fiscal_period_end <= m.obs_date
),
correct AS (
    SELECT m.asset_id, m.obs_date, fr.sue,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.publish_date DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.publish_date <= m.obs_date
),
paired AS (
    SELECT fw.obs_date, fw.fwd_ret, l.sue AS sue_leaky, c.sue AS sue_correct
    FROM fwd fw
    LEFT JOIN leaky   l ON l.asset_id = fw.asset_id AND l.obs_date = fw.obs_date AND l.rn = 1
    LEFT JOIN correct c ON c.asset_id = fw.asset_id AND c.obs_date = fw.obs_date AND c.rn = 1
    WHERE fw.fwd_ret IS NOT NULL AND l.sue IS NOT NULL AND c.sue IS NOT NULL
),
ranked AS (
    SELECT obs_date,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY fwd_ret)     AS rr,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY sue_leaky)   AS rl,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY sue_correct) AS rc
    FROM paired
),
per_month AS (
    SELECT obs_date,
           (AVG(rl*rr) - AVG(rl)*AVG(rr))
             / (SQRT(AVG(rl*rl)-AVG(rl)*AVG(rl)) * SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_leaky,
           (AVG(rc*rr) - AVG(rc)*AVG(rr))
             / (SQRT(AVG(rc*rc)-AVG(rc)*AVG(rc)) * SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_correct
    FROM ranked GROUP BY obs_date
)
SELECT COUNT(*) AS n_months,
       ROUND(AVG(ic_leaky), 6)   AS ic_join_on_period_end,
       ROUND(AVG(ic_correct), 6) AS rank_ic_mean_corrected,
       ROUND(AVG(ic_leaky) / AVG(ic_correct), 2) AS inflation_ratio
FROM per_month;""",
    "stratify_quintiles": """WITH fwd AS (
    SELECT fe.asset_id, fe.obs_date, fe.quintile,
           (SELECT b2.adj_close FROM daily_bar b2
             JOIN trading_calendar c2 ON c2.trade_date = b2.trade_date
            WHERE b2.asset_id = fe.asset_id AND c2.is_month_end = 1
              AND c2.month_index = (SELECT month_index FROM trading_calendar WHERE trade_date = fe.obs_date) + 1) /
           (SELECT b1.adj_close FROM daily_bar b1 WHERE b1.asset_id = fe.asset_id
             AND b1.trade_date = fe.obs_date) - 1 AS fwd_ret
    FROM factor_exposure fe
    JOIN factor f ON f.id = fe.factor_id
    WHERE f.code = '{code}'
)
SELECT quintile, COUNT(*) AS n, ROUND(AVG(fwd_ret) * 1200, 2) AS ann_return_pct
FROM fwd WHERE fwd_ret IS NOT NULL
GROUP BY quintile ORDER BY quintile;""",
    # ICIR 的分母是 *样本* 标准差, 所以要乘贝塞尔修正 sqrt(n/(n-1)); 少了它,
    # 42 个样本上算出来的 ICIR 会系统性高约 1.2%.
    "decay_profile": """SELECT i.fwd_horizon_days,
       COUNT(*) AS n_months,
       ROUND(AVG(i.rank_ic), 6) AS ic_mean,
       ROUND(AVG(i.rank_ic) / NULLIF(
             SQRT(AVG(i.rank_ic * i.rank_ic) - AVG(i.rank_ic) * AVG(i.rank_ic))
             * SQRT(COUNT(*) * 1.0 / (COUNT(*) - 1)), 0), 4) AS icir
FROM factor_ic_monthly i
JOIN factor f ON f.id = i.factor_id
WHERE f.code = '{code}' AND i.universe_id = 1
GROUP BY i.fwd_horizon_days;""",
    "regime_split": """SELECT r.code AS regime,
       COUNT(*) AS n_months,
       ROUND(AVG(i.rank_ic), 4) AS ic_mean,
       ROUND(AVG(i.q5_minus_q1_return) * 1200, 2) AS q5q1_ann_pct
FROM factor_ic_monthly i
JOIN factor f ON f.id = i.factor_id
JOIN regime_type r ON r.id = i.regime_type_id
WHERE f.code = '{code}' AND i.universe_id = 1
GROUP BY r.code
ORDER BY ic_mean DESC;""",
    # 符号翻转的判定. 门槛设在 ±0.02 而不是 0: 8 个月样本的 IC 标准误约 0.02,
    # 不设缓冲会把噪声当成翻转.
    "regime_sign_flip": """WITH by_regime AS (
    SELECT r.code AS regime, AVG(i.rank_ic) AS ic, COUNT(*) AS n
    FROM factor_ic_monthly i
    JOIN factor f      ON f.id = i.factor_id
    JOIN regime_type r ON r.id = i.regime_type_id
    WHERE f.code = '{code}' AND i.universe_id = 1
    GROUP BY r.code
)
SELECT ROUND(MAX(ic), 6) AS best_regime_ic,
       ROUND(MIN(ic), 6) AS worst_regime_ic,
       ROUND(MAX(ic) - MIN(ic), 6) AS ic_sign_flip_gap,
       CASE WHEN MAX(ic) > 0.02 AND MIN(ic) < -0.02
            THEN 'SIGN_FLIP' ELSE 'stable_sign' END AS regime_check
FROM by_regime;""",
    # 年化双边换手 = 月度换手 x 12 x 2 x 每月调仓次数. 最后那个系数对衰减快的
    # 信号大于 1 (STR_REV_5D 1.2, NEWS_SENT_7D 1.3), 这里按因子写成字面量,
    # 才能复现 factor_validation_run.annual_turnover.
    "turnover_cost": """SELECT COUNT(*) AS n_months,
       ROUND(AVG(i.monthly_turnover), 6) AS avg_monthly_turnover,
       ROUND(AVG(i.monthly_turnover) * {turnover_mult}, 4) AS annual_turnover
FROM factor_ic_monthly i
JOIN factor f ON f.id = i.factor_id
WHERE f.code = '{code}' AND i.universe_id = 1;""",
    "turnover_cost_net": """SELECT ROUND(v.q5_q1_annual_return * 100, 2) AS gross_ann_pct,
       ROUND(v.cost_bps_annual / 100.0, 2) AS cost_ann_pct,
       ROUND((v.q5_q1_annual_return - v.cost_bps_annual / 10000.0) * 100, 2) AS net_ann_pct,
       v.annual_turnover, v.gross_ir, v.net_ir,
       ROUND(100.0 * (v.gross_ir - v.net_ir) / v.gross_ir, 1) AS ir_eroded_pct
FROM factor_validation_run v
JOIN factor f ON f.id = v.factor_id
WHERE f.code = '{code}' AND v.universe_id = 1 AND v.window_type = 'FULL';""",
    # 相关系数, 不是协方差 —— 协方差带量纲, 没法拿去和 0.75 的红线比.
    "orthogonality": """SELECT pf.code AS production_factor,
       COUNT(*) AS n_months,
       ROUND((AVG(a.rank_ic * b.rank_ic) - AVG(a.rank_ic) * AVG(b.rank_ic))
             / (SQRT(AVG(a.rank_ic * a.rank_ic) - AVG(a.rank_ic) * AVG(a.rank_ic))
                * SQRT(AVG(b.rank_ic * b.rank_ic) - AVG(b.rank_ic) * AVG(b.rank_ic))), 4) AS ic_corr
FROM factor_ic_monthly a
JOIN factor_ic_monthly b ON b.obs_date = a.obs_date AND b.universe_id = a.universe_id
JOIN factor cf ON cf.id = a.factor_id
JOIN factor pf ON pf.id = b.factor_id
WHERE cf.code = '{code}' AND pf.status = 'production' AND a.universe_id = 1
GROUP BY pf.code ORDER BY ABS(ic_corr) DESC;""",
    "orthogonality_max": """WITH pairs AS (
    SELECT pf.code AS production_factor,
           (AVG(a.rank_ic * b.rank_ic) - AVG(a.rank_ic) * AVG(b.rank_ic))
           / (SQRT(AVG(a.rank_ic * a.rank_ic) - AVG(a.rank_ic) * AVG(a.rank_ic))
              * SQRT(AVG(b.rank_ic * b.rank_ic) - AVG(b.rank_ic) * AVG(b.rank_ic))) AS ic_corr
    FROM factor_ic_monthly a
    JOIN factor_ic_monthly b ON b.obs_date = a.obs_date AND b.universe_id = a.universe_id
    JOIN factor cf ON cf.id = a.factor_id
    JOIN factor pf ON pf.id = b.factor_id
    WHERE cf.code = '{code}' AND pf.status = 'production' AND a.universe_id = 1
    GROUP BY pf.code
)
SELECT production_factor AS closest_production_factor,
       ROUND(ABS(ic_corr), 4) AS max_corr_with_production,
       CASE WHEN ABS(ic_corr) > 0.75 THEN 'REDUNDANT' ELSE 'incremental' END AS orthogonality_check
FROM pairs ORDER BY ABS(ic_corr) DESC LIMIT 1;""",
    "capacity_split": """SELECT i.universe_id, u.code AS universe,
       ROUND(AVG(i.rank_ic), 4) AS ic_mean,
       ROUND(AVG(i.q5_minus_q1_return) * 1200, 2) AS q5q1_ann_pct,
       v.capacity_usd_mm
FROM factor_ic_monthly i
JOIN factor f ON f.id = i.factor_id
JOIN universe u ON u.id = i.universe_id
LEFT JOIN factor_validation_run v ON v.factor_id = f.id AND v.universe_id = i.universe_id
     AND v.window_type = 'FULL'
WHERE f.code = '{code}'
GROUP BY i.universe_id, u.code, v.capacity_usd_mm
ORDER BY i.universe_id;""",
    "pit_lag_audit": """SELECT 'v1_original' AS filing_version, COUNT(*) AS n_filings,
       ROUND(AVG(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end)), 1) AS avg_publish_lag_days,
       MIN(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end)) AS min_lag_days,
       MAX(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end)) AS max_lag_days
FROM fundamental_report fr WHERE fr.version = 1
UNION ALL
SELECT 'v2_restated', COUNT(*),
       ROUND(AVG(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end)), 1),
       MIN(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end)),
       MAX(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end))
FROM fundamental_report fr WHERE fr.version = 2;""",
    # H10 第一步: 到底有多少家公司会修订财报. 数的是公司不是行 —— 行占比会被
    # 每家公司的财报条数稀释, 而分析师真正要问的是"我手上这只票会不会被改".
    "restatement_share": """SELECT COUNT(DISTINCT CASE WHEN fr.version = 2 THEN fr.asset_id END) AS n_restating_firms,
       COUNT(DISTINCT fr.asset_id) AS n_firms,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN fr.version = 2 THEN fr.asset_id END)
             / COUNT(DISTINCT fr.asset_id), 4) AS restated_share_pct,
       ROUND(100.0 * SUM(CASE WHEN fr.is_restated = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS restated_row_pct
FROM fundamental_report fr;""",
    # H10 第二步 (全数据集最重要的一条证据): 把因子从 version = 1 的原始财报
    # 重新算一遍, 和仓库默认的最新版口径并排比较. 只动"版本"这一个变量,
    # as-of 规则两边都用正确的 publish_date.
    "fcf_ic_version1": """WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
original_only AS (
    SELECT m.asset_id, m.obs_date, fr.fcf_margin_ttm,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.fiscal_period_end DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.publish_date <= m.obs_date
),
paired AS (
    SELECT fw.obs_date, fw.fwd_ret, o.fcf_margin_ttm AS pit_value, fe.z_score AS warehouse_z
    FROM fwd fw
    JOIN original_only o ON o.asset_id = fw.asset_id AND o.obs_date = fw.obs_date AND o.rn = 1
    JOIN factor_exposure fe ON fe.asset_id = fw.asset_id AND fe.obs_date = fw.obs_date
    JOIN factor f ON f.id = fe.factor_id AND f.code = '{code}'
    WHERE fw.fwd_ret IS NOT NULL
),
ranked AS (
    SELECT obs_date,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY fwd_ret)     AS rr,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY pit_value)   AS rp,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY warehouse_z) AS rw
    FROM paired
),
per_month AS (
    SELECT obs_date,
           (AVG(rp*rr)-AVG(rp)*AVG(rr))/(SQRT(AVG(rp*rp)-AVG(rp)*AVG(rp))*SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_pit,
           (AVG(rw*rr)-AVG(rw)*AVG(rr))/(SQRT(AVG(rw*rw)-AVG(rw)*AVG(rw))*SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_warehouse
    FROM ranked GROUP BY obs_date
)
SELECT COUNT(*) AS n_months,
       ROUND(AVG(ic_warehouse), 6) AS ic_latest_version,
       ROUND(AVG(ic_pit), 6)       AS ic_first_version_only,
       ROUND(AVG(ic_warehouse) - AVG(ic_pit), 6) AS ic_gap
FROM per_month;""",
    "survivorship_z": """SELECT CASE WHEN a.delisted_date IS NULL THEN 'survivors_only' ELSE 'delisted' END AS cohort,
       COUNT(DISTINCT a.id) AS n_names,
       COUNT(*) AS n_obs,
       ROUND(AVG(fe.z_score), 6) AS avg_z_score
FROM factor_exposure fe
JOIN factor f ON f.id = fe.factor_id
JOIN asset a ON a.id = fe.asset_id
WHERE f.code = '{code}'
GROUP BY cohort;""",
    # H09 第二步: 同一份打分, 两个股票池, 并排算分层收益. 两边都必须重新
    # NTILE 分层 —— 池子变了分位点就变了, 复用 factor_exposure.quintile 会让
    # 存续池的 Q5 少掉一部分名额, 两边就不可比了.
    "survivorship_spread": """WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
base AS (
    SELECT fe.obs_date, fe.z_score, fw.fwd_ret,
           CASE WHEN a.delisted_date IS NULL THEN 1 ELSE 0 END AS is_survivor
    FROM factor_exposure fe
    JOIN factor f  ON f.id = fe.factor_id AND f.code = '{code}'
    JOIN asset  a  ON a.id = fe.asset_id
    JOIN fwd    fw ON fw.asset_id = fe.asset_id AND fw.obs_date = fe.obs_date
    WHERE fw.fwd_ret IS NOT NULL
),
survivors AS (
    SELECT NTILE(5) OVER (PARTITION BY obs_date ORDER BY z_score) AS q, fwd_ret
    FROM base WHERE is_survivor = 1
),
everything AS (
    SELECT NTILE(5) OVER (PARTITION BY obs_date ORDER BY z_score) AS q, fwd_ret FROM base
)
SELECT 'survivors_only' AS universe_treatment, COUNT(*) AS n_obs,
       ROUND((AVG(CASE WHEN q = 5 THEN fwd_ret END)
              - AVG(CASE WHEN q = 1 THEN fwd_ret END)) * 12, 6) AS q5_q1_annual
FROM survivors
UNION ALL
SELECT 'including_delisted', COUNT(*),
       ROUND((AVG(CASE WHEN q = 5 THEN fwd_ret END)
              - AVG(CASE WHEN q = 1 THEN fwd_ret END)) * 12, 6)
FROM everything;""",
    "multiple_testing": """SELECT h.seq_no AS trial_index, f.code,
       ROUND(v.ic_tstat, 3) AS observed_t,
       ROUND(h.applied_t_threshold, 3) AS required_t,
       CASE WHEN v.ic_tstat >= h.applied_t_threshold THEN 'PASS' ELSE 'FAIL' END AS multiple_testing_check
FROM agent_hypothesis h
JOIN factor f ON f.id = h.factor_id
JOIN factor_validation_run v ON v.factor_id = f.id AND v.universe_id = 1 AND v.window_type = 'FULL'
WHERE f.code = '{code}';""",
}

# 每条模板对着本数据集实际返回的行数. agent_step.rows_returned 直接取这里的值,
# 而不是随机抽 —— 一条确定性查询对着一个静态库跑两次, 不可能返回不同的行数,
# 随机数会让任何想复算轨迹的人第一眼就发现对不上.
AGENT_SQL_ROWS = {
    "scope_universe": 43,           # 43 个月末各一行
    "build_factor": 1,
    "compute_ic": 1,
    "pead_ic_naive": 1,
    "pead_ic_asof_compare": 1,
    "stratify_quintiles": 5,        # 五个分层
    "decay_profile": 1,             # 只有一个前瞻期 (21 天)
    "turnover_cost": 1,
    "turnover_cost_net": 1,
    "orthogonality": 6,             # 6 个生产因子各一行
    "orthogonality_max": 1,
    "capacity_split": 3,            # 三个池子
    "regime_split": 4,              # 四个 regime
    "regime_sign_flip": 1,
    "multiple_testing": 1,
    "pit_lag_audit": 2,             # v1 / v2 两行
    "restatement_share": 1,
    "fcf_ic_version1": 1,
    "survivorship_z": 2,            # 存续 / 已退市两个 cohort
    "survivorship_spread": 2,
}

# 每个假设走的探索路径. 前五步所有假设都走, 后面按怀疑方向分叉 ——
# 这正是"发现某个方向有苗头就继续深挖"的具体体现.
HYPOTHESIS_STEP_PLAN = {
    "ACC_QUALITY": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                    "decay_profile", "turnover_cost", "orthogonality", "regime_split",
                    "capacity_split", "multiple_testing", "summarize"],
    "EPS_REV_60D": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                    "decay_profile", "turnover_cost", "turnover_cost", "orthogonality",
                    "regime_split", "capacity_split", "multiple_testing", "summarize"],
    "PEAD_SUE": ["scope_universe", "build_factor", "compute_ic", "pit_audit", "compute_ic",
                 "stratify_quintiles", "decay_profile", "turnover_cost", "orthogonality",
                 "regime_split", "capacity_split", "multiple_testing", "summarize"],
    "STR_REV_5D": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                   "turnover_cost", "turnover_cost", "capacity_split", "decay_profile",
                   "orthogonality", "multiple_testing", "summarize"],
    "VOL_SKEW_ADJ": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                     "orthogonality", "orthogonality", "summarize"],
    "MICRO_VALUE": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                    "capacity_split", "capacity_split", "turnover_cost", "summarize"],
    "NEWS_SENT_7D": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                     "decay_profile", "regime_split", "regime_split", "multiple_testing", "summarize"],
    "SEARCH_TREND": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                     "multiple_testing", "summarize"],
    "DIV_GROWTH_5Y": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                      "survivorship_audit", "survivorship_audit", "capacity_split", "summarize"],
    "FCF_MARGIN_TTM": ["scope_universe", "build_factor", "compute_ic", "stratify_quintiles",
                       "decay_profile", "pit_audit", "pit_audit", "orthogonality", "summarize"],
}


def _mean_spearman_by_month(df: pl.DataFrame, xcol: str, ycol: str) -> tuple[float, int]:
    """按 obs_date 分组算 Spearman 相关, 返回 (月度均值, 有效月份数).

    这是 SQL 文档 Q3 / Q13 / Q19 里那套 `PERCENT_RANK` + 手工 Pearson 的等价实现.
    横截面上几乎没有真正的并列值, 所以"平均名次"与"百分位名次"给出同一个相关系数.
    """
    d = df.with_columns(
        pl.col(xcol).rank("average").over("obs_date").alias("_rx"),
        pl.col(ycol).rank("average").over("obs_date").alias("_ry"),
    )
    s = d.group_by("obs_date").agg(pl.corr("_rx", "_ry").alias("ic"))
    s = s.filter(pl.col("ic").is_not_null() & pl.col("ic").is_not_nan())
    return float(s["ic"].mean()), s.height


def compute_trap_diagnostics(panel: pl.DataFrame, ic_df: pl.DataFrame,
                             factors: pl.DataFrame,
                             fundamentals: pl.DataFrame,
                             exposures: pl.DataFrame) -> dict[str, float]:
    """把十条陷阱的实际量级算出来.

    这些数字既是 Agent 各步骤的 key_metric_value, 也是文档里"预期结果"那一节的
    唯一事实来源. 生成器跑完会把它们打印出来, 方便和文档逐条核对.

    **口径纪律 (这是本函数最重要的一条约定):** T1 与 T8 的数字必须用"分析师从
    fundamental_report 从零重建"的口径算, 而不是生成器内部那份已策展的面板 ——
    因为 agent_step.sql_text 里存的就是那条重建查询, 人类审批时会照着它复算.
    存进 factor_ic_monthly 的官方值 (PEAD 0.0341) 是另一套口径: 它覆盖全部 42 个
    月和每月约 1,150 只票, 而重建口径只能覆盖"当月已有 v1 财报公布"的标的、且
    第一个观测月整月落空. 两套都对, 但轨迹里只能出现能被自己那条 SQL 复现的那套.
    """
    fid_by_code = {r["code"]: r["id"] for r in factors.to_dicts()}
    eq_all = panel.filter(pl.col("asset_class_id") == 1)
    eq = eq_all.filter(pl.col("fwd_total_return").is_not_null())\
        .with_columns(pl.col("fwd_total_return").alias("fwd_excess_return"))

    def _mean_ic(zcol: str, extra=None) -> float:
        d = eq if extra is None else eq.filter(extra)
        d = d.with_columns(
            pl.col(zcol).rank("average").over("month_index").alias("rz"),
            pl.col("fwd_excess_return").rank("average").over("month_index").alias("rf"),
        )
        s = d.group_by("month_index").agg(pl.corr("rz", "rf").alias("ic"))
        return float(s["ic"].mean())

    out: dict[str, float] = {}

    # --- 从 fundamental_report 重建 (与 agent_step.sql_text 逐条对应) ---
    v1 = fundamentals.filter(pl.col("version") == 1)
    base_obs = eq.select(
        "asset_id", "obs_date", "fwd_excess_return", "z_FCF_MARGIN_TTM"
    ).sort("obs_date")
    leaky = base_obs.join_asof(
        v1.select("asset_id", "fiscal_period_end",
                  pl.col("sue").alias("sue_leaky")).sort("fiscal_period_end"),
        left_on="obs_date", right_on="fiscal_period_end", by="asset_id", strategy="backward",
    )
    correct = base_obs.join_asof(
        v1.select("asset_id", "publish_date", pl.col("sue").alias("sue_correct"),
                  pl.col("fcf_margin_ttm").alias("fcf_v1")).sort("publish_date"),
        left_on="obs_date", right_on="publish_date", by="asset_id", strategy="backward",
    )

    # H03 step 3: 第一遍朴素重建, 只用 fiscal_period_end 做 as-of. 它自己的样本
    # 比后面的并排对比多一个月 (第一个观测月还没有任何财报公布, 但已经有财季结束).
    naive_only = leaky.filter(pl.col("sue_leaky").is_not_null())
    out["T1_pead_naive_standalone"], n_naive = _mean_spearman_by_month(
        naive_only, "sue_leaky", "fwd_excess_return")
    out["T1_pead_naive_n_months"] = float(n_naive)

    # H03 step 5: 两种 as-of 规则的并排对比, 只在两边都有值的共同样本上算.
    paired = leaky.select("asset_id", "obs_date", "fwd_excess_return", "sue_leaky").join(
        correct.select("asset_id", "obs_date", "sue_correct"), on=["asset_id", "obs_date"]
    ).filter(pl.col("sue_leaky").is_not_null() & pl.col("sue_correct").is_not_null())
    out["T1_pead_leaky_ic"], n_paired = _mean_spearman_by_month(
        paired, "sue_leaky", "fwd_excess_return")
    out["T1_pead_correct_ic"], _ = _mean_spearman_by_month(
        paired, "sue_correct", "fwd_excess_return")
    out["T1_inflation_ratio"] = out["T1_pead_leaky_ic"] / max(out["T1_pead_correct_ic"], 1e-9)
    out["T1_paired_n_months"] = float(n_paired)
    # 官方面板存的那一套 (factor_ic_monthly 里的 PEAD_SUE), 留作对账参考.
    out["T1_pead_curated_panel_ic"] = _mean_ic("z_PEAD_SUE")

    # H10 step 7: 用 version = 1 的原始财报重算 FCF, 和仓库默认的最新版并排比.
    fcf_pairs = correct.filter(pl.col("fcf_v1").is_not_null())
    out["T8_fcf_pit_ic"], n_fcf = _mean_spearman_by_month(
        fcf_pairs, "fcf_v1", "fwd_excess_return")
    out["T8_fcf_restated_ic"], _ = _mean_spearman_by_month(
        fcf_pairs, "z_FCF_MARGIN_TTM", "fwd_excess_return")
    out["T8_n_months"] = float(n_fcf)
    # H10 step 6: 有多少家公司会修订财报 (数公司, 不数行).
    n_firms = fundamentals["asset_id"].n_unique()
    n_restating = fundamentals.filter(pl.col("version") == 2)["asset_id"].n_unique()
    out["T8_restated_firm_pct"] = 100.0 * n_restating / max(n_firms, 1)

    # H03 step 4 / Q8: v1 财报的平均公布滞后天数, 就是 look-ahead 能偷到多少天.
    out["PIT_avg_publish_lag_days"] = float(
        v1.select(
            (pl.col("publish_date") - pl.col("fiscal_period_end")).dt.total_days()
        ).to_series().mean()
    )

    # 每个假设第一步 scope_universe 报的池子规模: 月末在市的股票数的平均值.
    out["SCOPE_live_names_avg"] = float(
        eq_all.group_by("obs_date").agg(pl.len().alias("n"))["n"].mean()
    )

    # T2 幸存者偏差必须从 **落库后的 factor_exposure** 算, 而不是从生成器内部的
    # 面板算: 落库时 z_score 被四舍五入到 6 位, 第 7 位小数上的差异会在分位数边界
    # 上换掉几只票, 41 个月累积下来足以让结果和分析师照着 factor_exposure 自己算
    # 出来的差 0.02 个百分点. 轨迹里的数字必须是分析师能复现的那个.
    div_fid = fid_by_code["DIV_GROWTH_5Y"]
    div_base = exposures.filter(pl.col("factor_id") == div_fid).select(
        "asset_id", "obs_date", "z_score"
    ).join(
        eq_all.select("asset_id", "obs_date", "fwd_total_return", "is_delisted"),
        on=["asset_id", "obs_date"], how="inner",
    )
    # H09 step 5: 后来退市的那批标的, 在 DIV_GROWTH_5Y 上的平均打分 (全部暴露行).
    out["T2_avg_z_delisted"] = float(
        exposures.filter(pl.col("factor_id") == div_fid).join(
            eq_all.select("asset_id", "obs_date", "is_delisted"),
            on=["asset_id", "obs_date"], how="inner",
        ).filter(pl.col("is_delisted") == 1)["z_score"].mean()
    )

    # 分层逐字复刻 SQL 的 NTILE(5): n 不能被 5 整除时, 前 (n mod 5) 组各多装一个.
    div_base = div_base.filter(pl.col("fwd_total_return").is_not_null())
    _rk = pl.col("z_score").rank("ordinal").over("obs_date")
    _n = pl.len().over("obs_date")
    _big = _n // 5 + 1          # 前 (n mod 5) 组的大小
    _cut = (_n % 5) * _big      # 大组一共覆盖到第几名
    for label, cond in (("survivors", pl.col("is_delisted") == 0), ("full", pl.lit(True))):
        d = div_base.filter(cond).with_columns(
            pl.when(_rk <= _cut)
            .then((_rk - 1) // _big)
            .otherwise((_n % 5) + (_rk - _cut - 1) // (_n // 5))
            .clip(0, 4).alias("q")
        )
        g = d.group_by("q").agg(pl.col("fwd_total_return").mean().alias("r")).sort("q").to_dicts()
        if len(g) >= 5:
            out[f"T2_divgrowth_q5q1_ann_{label}"] = (g[4]["r"] - g[0]["r"]) * 12.0
    out["T2_divgrowth_q5q1_gap"] = (out.get("T2_divgrowth_q5q1_ann_survivors", 0.0)
                                    - out.get("T2_divgrowth_q5q1_ann_full", 0.0))

    # T7 容量陷阱: MICRO_VALUE 在各市值五分位上的 IC.
    for q in (1, 3, 5):
        out[f"T7_microvalue_ic_sizeq{q}"] = _mean_ic("z_MICRO_VALUE", pl.col("size_quintile") == q)
    out["T7_microvalue_ic_all"] = _mean_ic("z_MICRO_VALUE")

    # T5 regime 依赖: NEWS_SENT_7D 分 regime 的 IC.
    news_fid = fid_by_code["NEWS_SENT_7D"]
    reg = ic_df.filter((pl.col("factor_id") == news_fid) & (pl.col("universe_id") == 1)).join(
        pl.DataFrame({"regime_type_id": [1, 2, 3, 4],
                      "regime_code": ["RECOVERY", "LOW_VOL_BULL", "HIGH_VOL_STRESS", "RISING_RATE"]}),
        on="regime_type_id",
    ).group_by("regime_code").agg(pl.col("rank_ic").mean().alias("ic"))
    for r in reg.to_dicts():
        out[f"T5_newssent_ic_{r['regime_code']}"] = r["ic"]
    return out


def gen_agent_tables(
    factors: pl.DataFrame,
    validations: pl.DataFrame,
    ic_df: pl.DataFrame,
    diag: dict[str, float],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Atlas Agent 这一轮探索的完整轨迹: run / hypothesis / step / finding / report."""
    fid_by_code = {r["code"]: r["id"] for r in factors.to_dicts()}
    theme_by_code = {f[0]: f[2] for f in FACTOR_DEFS}
    theme_ids = {c: i + 1 for i, (c, _, _) in enumerate(FACTOR_THEME_DEFS)}
    v_full = {r["factor_id"]: r for r in validations.filter(
        (pl.col("universe_id") == 1) & (pl.col("window_type") == "FULL")).to_dicts()}
    v_small = {r["factor_id"]: r for r in validations.filter(
        (pl.col("universe_id") == 3) & (pl.col("window_type") == "FULL")).to_dicts()}

    run_start = datetime(2026, 7, 6, 9, 12, 0)
    cursor = run_start

    hyp_rows = []
    step_rows = []
    find_rows = []
    step_id = 0

    for seq, code, title, thesis, source, verdict, reason in HYPOTHESIS_DEFS:
        fid = fid_by_code[code]
        v = v_full[fid]
        applied_t = hlz_threshold(seq)
        hyp_start = cursor
        plan = HYPOTHESIS_STEP_PLAN[code]

        seen_types: dict[str, int] = {}
        for step_no, stype in enumerate(plan, start=1):
            seen_types[stype] = seen_types.get(stype, 0) + 1
            repeat = seen_types[stype]
            metric_name, metric_value, decision, rationale, sql_key = _step_outcome(
                code, stype, repeat, v, v_small.get(fid), diag, applied_t
            )
            # summarize 那一步写的是备忘录, 不执行查询, 所以不留 sql_text.
            sql = None if sql_key is None else AGENT_SQL_TEMPLATES[sql_key].format(
                code=code,
                turnover_mult=round(24.0 * REBALANCE_PER_MONTH.get(code, 1.0), 2),
            )
            tokens_in = random.randint(2400, 7800)
            tokens_out = random.randint(280, 1400)
            latency = random.randint(180, 4200)
            step_id += 1
            step_rows.append({
                "id": step_id,
                "agent_run_id": 1,
                "agent_hypothesis_id": seq,
                "step_no": step_no,
                "step_type": stype,
                "tool_name": "sqlite_query" if stype != "summarize" else "write_memo",
                "sql_text": sql,
                "rows_returned": 0 if sql_key is None else AGENT_SQL_ROWS[sql_key],
                "latency_ms": latency,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                # 按 2026 年前沿模型的典型定价折算, 单位美元.
                "cost_usd": round(tokens_in / 1e6 * 3.0 + tokens_out / 1e6 * 15.0, 6),
                "key_metric_name": metric_name,
                "key_metric_value": None if metric_value is None else round(metric_value, 6),
                "decision": decision,
                "decision_rationale": rationale,
                "started_at": cursor,
            })
            cursor += timedelta(seconds=latency / 1000.0 + random.uniform(6, 34))

        for f in _hypothesis_findings(seq, code, v, v_small.get(fid), diag, applied_t):
            find_rows.append(f)

        hyp_rows.append({
            "id": seq,
            "agent_run_id": 1,
            "seq_no": seq,
            "factor_id": fid,
            "title": title,
            "thesis_text": thesis,
            "idea_source": source,
            "theme_id": theme_ids[theme_by_code[code]],
            "trial_index": seq,
            "applied_t_threshold": applied_t,
            "observed_t_stat": v["ic_tstat"],
            "passes_adjusted_threshold": 1 if v["ic_tstat"] >= applied_t else 0,
            "verdict": verdict,
            "reject_reason_code": reason,
            "n_steps": len(plan),
            "elapsed_minutes": round((cursor - hyp_start).total_seconds() / 60.0, 2),
            "created_at": hyp_start,
        })

    run_end = cursor
    promoted = sum(1 for h in hyp_rows if h["verdict"] == "PROMOTED")
    run_df = pl.DataFrame([{
        "id": 1,
        "run_code": "RUN-2026-Q2-001",
        "objective": (
            "Search the TCM factor warehouse for candidate alpha signals that are additive to the "
            "existing production library, survive transaction costs at a 3bn USD allocation, and "
            "clear the multiple-testing threshold implied by the number of trials in this run. "
            "Return a promotion shortlist with a validation-ready memo."
        ),
        "universe_id": 1,
        "model_name": "frontier-llm-v5",
        "started_at": run_start,
        "ended_at": run_end,
        "wall_clock_minutes": round((run_end - run_start).total_seconds() / 60.0, 2),
        "hypotheses_planned": 10,
        "hypotheses_completed": len(hyp_rows),
        "hypotheses_promoted": promoted,
        "total_steps": len(step_rows),
        "total_sql_queries": sum(1 for s in step_rows if s["sql_text"]),
        "total_tokens": sum(s["tokens_in"] + s["tokens_out"] for s in step_rows),
        "total_cost_usd": round(sum(s["cost_usd"] for s in step_rows), 4),
        # 一个研究员一周认真检验 3-8 个假设, 10 个假设 + 完整验证约需一个月.
        "human_analyst_baseline_days": 22,
        "status": "COMPLETED",
    }])

    hyp_df = pl.DataFrame(hyp_rows, infer_schema_length=None).select(
        "id", "agent_run_id", "seq_no", "factor_id", "title", "thesis_text", "idea_source",
        "theme_id", "trial_index", "applied_t_threshold", "observed_t_stat",
        "passes_adjusted_threshold", "verdict", "reject_reason_code", "n_steps",
        "elapsed_minutes", "created_at",
    )
    step_df = pl.DataFrame(step_rows, infer_schema_length=None).select(
        "id", "agent_run_id", "agent_hypothesis_id", "step_no", "step_type", "tool_name",
        "sql_text", "rows_returned", "latency_ms", "tokens_in", "tokens_out", "cost_usd",
        "key_metric_name", "key_metric_value", "decision", "decision_rationale", "started_at",
    )
    find_df = pl.DataFrame(find_rows, infer_schema_length=None).with_row_index("id", offset=1).select(
        "id", "agent_run_id", "agent_hypothesis_id", "finding_type", "severity", "headline",
        "evidence_metric", "evidence_value", "comparison_value", "threshold_applied",
        "supports_promotion", "confidence",
    )
    report_df = _build_report(hyp_rows, v_full, fid_by_code, diag, run_df.to_dicts()[0])
    return run_df, hyp_df, step_df, find_df, report_df


def _step_outcome(code, stype, repeat, v, v_small, diag, applied_t):
    """一步探索的产出: 关键指标 + 决策与理由 + 这一步实际发出的那条 SQL 的模板名.

    **不变式: 每一步存的 sql_text, 拿去对着本库执行, 必须真的能算出这一步的
    key_metric_value.** 人类审批 Agent 的轨迹时看的就是这条对应关系; 一旦
    sql_text 和 key_metric_value 对不上, 整条轨迹就退化成了看起来像真的装饰.
    """
    lag_by_convention = {f[0]: f[4] for f in FACTOR_DEFS}
    if stype == "scope_universe":
        n_live = diag.get("SCOPE_live_names_avg", 1150.0)
        return ("live_names_avg", n_live, "continue",
                f"Universe is stable at roughly {n_live:,.0f} live names per month with no coverage "
                "gaps; delisted names are present in the asset table, so survivorship can be tested "
                "later.", "scope_universe")
    if stype == "build_factor":
        lag = float(FACTOR_DATA_LAG_DAYS[lag_by_convention[code]])
        return ("max_data_lag_days", lag, "continue",
                f"Exposure built for every month end. Worst-case data staleness is {lag:.0f} days, "
                f"which matches the {lag_by_convention[code]} convention declared on the factor "
                "definition, so the signal is implementable as specified.", "build_factor")
    if stype == "compute_ic":
        if code == "PEAD_SUE" and repeat == 2:
            return ("rank_ic_mean_corrected", diag["T1_pead_correct_ic"], "deepen",
                    "Re-ran the IC with the publish_date as-of rule on the sample where both "
                    "conventions are defined. IC drops by a factor of "
                    f"{diag['T1_inflation_ratio']:.2f} versus the naive fiscal_period_end join, which "
                    "confirms the first pass was contaminated. The corrected number is still "
                    "economically meaningful, so keep going.", "pead_ic_asof_compare")
        if code == "PEAD_SUE":
            return ("rank_ic_mean_naive", diag["T1_pead_naive_standalone"], "deepen",
                    "First-pass IC is implausibly high for a well-known published anomaly. Before "
                    "believing it, audit the point-in-time discipline of the underlying fundamentals.",
                    "pead_ic_naive")
        d = "deepen" if abs(v["ic_mean"]) >= 0.015 else "pivot"
        return ("rank_ic_mean", v["ic_mean"], d,
                f"Mean RankIC is {v['ic_mean']:.4f} with ICIR {v['icir']:.2f}. "
                + ("Strong enough to justify the full diagnostic battery."
                   if d == "deepen" else
                   "Marginal. Run the cheap screens first before spending on deep diagnostics."),
                "compute_ic")
    if stype == "stratify_quintiles":
        return ("q5_q1_annual_return", v["q5_q1_annual_return"], "continue",
                "Quintile returns are monotonic enough to rule out a purely non-linear relationship. "
                "The long-short spread is the number the cost analysis will have to survive.",
                "stratify_quintiles")
    if stype == "decay_profile":
        return ("icir", v["icir"], "continue",
                "Signal decay is consistent with the data frequency behind the factor. A faster decay "
                "means a shorter holding period, which pushes turnover and cost up.", "decay_profile")
    if stype == "regime_split":
        if code == "NEWS_SENT_7D":
            lo = diag.get("T5_newssent_ic_LOW_VOL_BULL", 0.0)
            hi = diag.get("T5_newssent_ic_HIGH_VOL_STRESS", 0.0)
            if repeat >= 2:
                return ("ic_sign_flip_gap", lo - hi, "abandon",
                        "The signal changes sign between calm and stressed regimes. A factor whose "
                        "direction depends on the regime is a regime timing bet dressed up as an alpha "
                        "signal, and this desk has no mandate to time regimes. Reject.",
                        "regime_sign_flip")
            return ("ic_high_vol_regime", hi, "deepen",
                    "Full-sample IC hides a large dispersion across regimes. Split again and check "
                    "whether the sign is stable or flips.", "regime_split")
        return ("ic_dispersion_across_regimes", v["ic_std"], "continue",
                "IC varies across regimes but keeps its sign in every one of them, so this is "
                "amplitude variation rather than a regime-dependent sign flip.", "regime_split")
    if stype == "turnover_cost":
        if repeat >= 2:
            return ("net_ir", v["net_ir"], "deepen" if v["net_ir"] >= 0.20 else "abandon",
                    f"After spread, square-root impact at a 3bn USD allocation and commissions, net IR "
                    f"is {v['net_ir']:.2f} against a gross IR of {v['gross_ir']:.2f}. "
                    + ("Thin but positive, so it survives as a constrained-use signal."
                       if v["net_ir"] >= 0.20 else
                       "Costs consume the entire gross alpha. Reject."), "turnover_cost_net")
        return ("annual_turnover", v["annual_turnover"], "continue",
                f"Two-way annual turnover is {v['annual_turnover']:.2f}x. Price the trading before "
                f"believing the gross number.", "turnover_cost")
    if stype == "orthogonality":
        mc = v["max_corr_with_production"]
        if repeat >= 2:
            return ("max_corr_with_production", mc,
                    "abandon" if mc > VALIDATION_CORR_LIMIT else "deepen",
                    f"Highest IC correlation against the production library is {mc:.2f}. "
                    + ("That is the same bet the existing low-volatility factor already makes. "
                       "Incremental contribution to the composite would be near zero. Reject."
                       if mc > VALIDATION_CORR_LIMIT else
                       "Low enough that the signal carries genuinely new information."),
                    "orthogonality_max")
        return ("max_corr_with_production", mc, "continue",
                "Comparing the monthly IC series against every production factor to check whether this "
                "is a new bet or an old bet in new clothes.", "orthogonality")
    if stype == "capacity_split":
        if code == "MICRO_VALUE":
            if repeat >= 2:
                return ("capacity_usd_mm", v["capacity_usd_mm"], "abandon",
                        "Nearly all of the predictive power sits in the smallest size quintile, where "
                        "the ADV cannot absorb a meaningful allocation. Capacity is far below the "
                        "500mm USD floor this desk requires. Reject.", "capacity_split")
            small_ic = v_small["ic_mean"] if v_small else 0.0
            return ("ic_small_cap_universe", small_ic, "deepen",
                    "IC in the small-cap universe is several times the all-cap number. That is either "
                    "a genuine small-cap effect or a capacity trap. Price the capacity.",
                    "capacity_split")
        return ("capacity_usd_mm", v["capacity_usd_mm"], "continue",
                f"Capacity solves to {v['capacity_usd_mm']:.0f}mm USD before impact eats half the gross "
                f"alpha, which clears the desk floor.", "capacity_split")
    if stype == "pit_audit":
        if code == "FCF_MARGIN_TTM":
            if repeat >= 2:
                return ("ic_first_version_only", diag["T8_fcf_pit_ic"], "abandon",
                        "Recomputing the factor from version 1 filings only, which is what was actually "
                        "visible at the time, collapses the IC from "
                        f"{diag['T8_fcf_restated_ic']:.4f} to {diag['T8_fcf_pit_ic']:.4f}. The apparent "
                        "alpha came from restated numbers the market had not seen. Reject.",
                        "fcf_ic_version1")
            return ("restated_share_pct", diag["T8_restated_firm_pct"], "deepen",
                    "A meaningful share of filings carry a later restated version. The warehouse serves "
                    "the latest version by default, so rebuild the factor from version 1 and compare.",
                    "restatement_share")
        return ("avg_publish_lag_days", diag.get("PIT_avg_publish_lag_days", 30.0), "deepen",
                "Fundamentals publish roughly a month after the fiscal period closes. Any factor joined "
                "on fiscal_period_end is reading numbers the market could not yet see.", "pit_lag_audit")
    if stype == "survivorship_audit":
        if repeat >= 2:
            return ("q5_q1_gap_survivor_vs_full", diag.get("T2_divgrowth_q5q1_gap", 0.0), "abandon",
                    "The long-short spread is strongly positive on survivors only and collapses once "
                    "delisted names are included. Companies defend the dividend on the way down, so the "
                    "signal loads on exactly the names that later disappear. Reject.",
                    "survivorship_spread")
        return ("avg_z_delisted_cohort", diag.get("T2_avg_z_delisted", DELISTED_DIVGROWTH_Z_SHIFT),
                "deepen",
                "Names that later delisted score systematically high on this factor. Rebuild the "
                "backtest with delisted names included and compare the spread.", "survivorship_z")
    if stype == "multiple_testing":
        passes = v["ic_tstat"] >= applied_t
        return ("ic_tstat", v["ic_tstat"], "continue" if passes else "abandon",
                f"Observed t is {v['ic_tstat']:.2f} against the multiple-testing threshold of "
                f"{applied_t:.2f} implied by the trial count so far. "
                + ("Clears the adjusted bar." if passes else
                   "It would have cleared a naive t>2 bar, but not the adjusted one. Reject."),
                "multiple_testing")
    return ("net_ir", v["net_ir"], "continue",
            "Diagnostics complete. Writing the memo section for this hypothesis.", None)


def _hypothesis_findings(seq, code, v, v_small, diag, applied_t) -> list[dict]:
    """一个假设产出的具体发现. 每条都带证据指标与数值, 报告里的每句话都能追溯到这里."""
    out = []

    def add(ftype, sev, head, metric, val, cmp_val=None, thr=None, support=0, conf=0.8):
        out.append({
            "agent_run_id": 1, "agent_hypothesis_id": seq, "finding_type": ftype,
            "severity": sev, "headline": head, "evidence_metric": metric,
            "evidence_value": round(float(val), 6),
            "comparison_value": None if cmp_val is None else round(float(cmp_val), 6),
            "threshold_applied": None if thr is None else round(float(thr), 6),
            "supports_promotion": support, "confidence": conf,
        })

    add("signal_measured", "info",
        f"{code} full-sample RankIC is {v['ic_mean']:.4f} with ICIR {v['icir']:.2f}",
        "ic_mean", v["ic_mean"], None, 0.02, 1 if v["ic_mean"] >= 0.02 else 0, 0.92)
    add("cost_measured", "info",
        f"{code} net IR is {v['net_ir']:.2f} against gross IR {v['gross_ir']:.2f} "
        f"at {v['annual_turnover']:.2f}x turnover",
        "net_ir", v["net_ir"], v["gross_ir"], VALIDATION_MIN_NET_IR,
        1 if v["net_ir"] >= VALIDATION_MIN_NET_IR else 0, 0.88)

    if code == "PEAD_SUE":
        add("trap_detected", "critical",
            "Naive fiscal_period_end join inflates RankIC by roughly "
            f"{diag['T1_inflation_ratio']:.1f}x versus the publish_date as-of rule",
            "rank_ic_inflation_ratio", diag["T1_inflation_ratio"],
            diag["T1_pead_correct_ic"], 1.0, 0, 0.96)
    if code == "VOL_SKEW_ADJ":
        add("trap_detected", "high",
            f"IC series correlation with the production low-volatility factor is "
            f"{v['max_corr_with_production']:.2f}",
            "max_corr_with_production", v["max_corr_with_production"], None,
            VALIDATION_CORR_LIMIT, 0, 0.94)
    if code == "MICRO_VALUE":
        add("trap_detected", "high",
            f"Micro-cap universe IC is {(v_small['ic_mean'] if v_small else 0):.4f} versus "
            f"{v['ic_mean']:.4f} all-cap, but the micro sleeve only absorbs "
            f"{(v_small['capacity_usd_mm'] if v_small else 0):.0f}mm USD",
            "capacity_usd_mm_micro", (v_small["capacity_usd_mm"] if v_small else 0.0),
            (v_small["ic_mean"] if v_small else 0.0), VALIDATION_MIN_CAPACITY_MM, 0, 0.91)
    if code == "NEWS_SENT_7D":
        add("trap_detected", "critical",
            "RankIC sign flips between the low-volatility and high-volatility regimes",
            "ic_low_vol_regime", diag.get("T5_newssent_ic_LOW_VOL_BULL", 0.0),
            diag.get("T5_newssent_ic_HIGH_VOL_STRESS", 0.0), 0.0, 0, 0.93)
    if code == "SEARCH_TREND":
        add("trap_detected", "high",
            f"t of {v['ic_tstat']:.2f} clears a naive 2.0 bar but not the "
            f"{applied_t:.2f} multiple-testing threshold for trial {seq}",
            "ic_tstat", v["ic_tstat"], 2.0, applied_t, 0, 0.89)
    if code == "DIV_GROWTH_5Y":
        add("trap_detected", "critical",
            "Long-short spread is positive on survivors only and collapses once delisted names "
            "are included",
            "q5_q1_annual_survivors", diag.get("T2_divgrowth_q5q1_ann_survivors", 0.0),
            diag.get("T2_divgrowth_q5q1_ann_full", 0.0), 0.0, 0, 0.95)
    if code == "FCF_MARGIN_TTM":
        add("trap_detected", "critical",
            "Rebuilding the factor from version 1 filings only collapses the IC",
            "ic_version1_only", diag["T8_fcf_pit_ic"], diag["T8_fcf_restated_ic"], 0.02, 0, 0.94)
    if code in ("ACC_QUALITY", "EPS_REV_60D", "PEAD_SUE", "STR_REV_5D"):
        add("signal_confirmed", "info",
            f"{code} clears the adjusted t threshold and the orthogonality screen; "
            "recommended for validation",
            "ic_tstat", v["ic_tstat"], None, applied_t, 1, 0.90)
    return out


def _build_report(hyp_rows, v_full, fid_by_code, diag, run_row) -> pl.DataFrame:
    """Agent 自动生成的最终报告. 结构照搬机构研究备忘录: 假设 / 风险驱动 / 局限 / 验证结论."""
    promoted = [h for h in hyp_rows if h["verdict"] == "PROMOTED"]
    rejected = [h for h in hyp_rows if h["verdict"] == "REJECTED"]
    code_by_fid = {fid: c for c, fid in fid_by_code.items()}

    secs = []

    def add(stype, title, body, refs=None):
        secs.append({
            "agent_run_id": 1, "section_order": len(secs) + 1, "section_type": stype,
            "title": title, "body_text": " ".join(body.split()),
            "referenced_hypothesis_seqs": refs,
        })

    add("executive_summary", "Executive Summary", f"""
        Atlas explored {run_row['hypotheses_completed']} hypotheses in
        {run_row['wall_clock_minutes']:.0f} minutes of wall clock at a compute cost of
        {run_row['total_cost_usd']:.2f} USD, executing {run_row['total_sql_queries']} queries
        against the factor warehouse. {len(promoted)} candidates are recommended for formal
        validation and {len(rejected)} are rejected with documented cause. The comparable manual
        exploration is roughly {run_row['human_analyst_baseline_days']} analyst days. Every
        rejection is attributable to a specific, reproducible diagnostic rather than to a
        judgement call, and every promoted candidate cleared the orthogonality screen, the cost
        screen and the multiple-testing threshold implied by its trial index.
        """, ",".join(str(h["seq_no"]) for h in promoted))

    add("assumptions", "Model Assumptions", """
        One month forward excess return is the prediction target and RankIC is the Spearman
        correlation between month-end factor rank and that forward return. ICIR is the mean
        monthly RankIC divided by its standard deviation, not annualised. Exposures are computed
        at the last trading day of each month and held for one month. Transaction cost per unit
        of turnover is half the quoted spread plus a square-root impact term calibrated to a
        three billion USD allocation plus one basis point of commission. The universe is rebuilt
        at every observation date from names actually listed on that date, so delisted names are
        present until the day they delist. Fundamental data is joined on publish_date, never on
        fiscal_period_end.
        """, None)

    for h in promoted:
        code = code_by_fid[h["factor_id"]]
        v = v_full[h["factor_id"]]
        add("validation_results", f"Promoted: {code}", f"""
            Full-sample RankIC {v['ic_mean']:.4f}, ICIR {v['icir']:.2f}, t {v['ic_tstat']:.2f}
            against an adjusted threshold of {h['applied_t_threshold']:.2f}. IC hit rate
            {v['ic_hit_rate'] * 100:.0f} percent. Gross long-short spread
            {v['q5_q1_annual_return'] * 100:.2f} percent annualised at {v['annual_turnover']:.2f}x
            two-way turnover, costing {v['cost_bps_annual']:.0f} basis points a year, which takes
            gross IR {v['gross_ir']:.2f} down to net IR {v['net_ir']:.2f}. Maximum correlation
            against the production library is {v['max_corr_with_production']:.2f} and capacity
            solves to {v['capacity_usd_mm']:.0f}mm USD. Out-of-sample behaviour and the deflated
            Sharpe of {v['deflated_sharpe']:.2f} are reported in the validation appendix.
            """, str(h["seq_no"]))

    add("key_risk_drivers", "Key Risk Drivers", f"""
        The promoted set is concentrated in earnings-quality and revision themes, which historically
        co-move with the quality style already carried by the production book, so the composite
        should be monitored for style crowding even though pairwise IC correlations stay below
        {VALIDATION_CORR_LIMIT:.2f}. The fastest-decaying promoted signal carries the highest
        turnover and therefore the largest sensitivity to a spread widening: a doubling of average
        quoted spread would move it below the desk net IR floor. Cost estimates assume a three
        billion USD allocation; scaling beyond that erodes net IR non-linearly through the impact
        term. Finally, the sample contains one full high-volatility stress regime, which is enough
        to detect a sign flip but not enough to estimate regime-conditional amplitude precisely.
        """, None)

    add("limitations", "Limitations", f"""
        The observation window covers {len(v_full) and 42} monthly cross sections, which is short
        by the standards of factor research and leaves the t statistics sensitive to a handful of
        months. The multiple-testing threshold applied here counts only the trials inside this run;
        it does not account for hypotheses previously tested by the research desk on the same data,
        so the true adjusted bar is higher than the one used. Capacity is estimated from ADV and
        quoted spread only and ignores the borrow cost of the short leg. Regime labels are assigned
        ex post, so any regime-conditional result is optimistic relative to what a live regime
        classifier would have delivered.
        """, None)

    add("appendix", "Rejected Hypotheses and Cause", "; ".join(
        f"{h['seq_no']}. {code_by_fid[h['factor_id']]} rejected as {h['reject_reason_code']}"
        for h in rejected
    ), ",".join(str(h["seq_no"]) for h in rejected))

    add("appendix", "Point-in-Time Audit Results", f"""
        Two hypotheses failed specifically on point-in-time discipline. Joining fundamentals on
        fiscal_period_end rather than publish_date inflated the post-earnings drift RankIC from
        {diag['T1_pead_correct_ic']:.4f} to {diag['T1_pead_leaky_ic']:.4f}, a factor of
        {diag['T1_inflation_ratio']:.1f}. Rebuilding the free cash flow margin factor from version 1
        filings only moved its RankIC from {diag['T8_fcf_restated_ic']:.4f} to
        {diag['T8_fcf_pit_ic']:.4f}. Both effects are invisible in the headline validation
        statistics and only surface when the as-of rule is varied deliberately.
        """, "3,10")

    add("appendix", "Survivorship and Capacity Audit", f"""
        The five year dividend growth factor produced a
        {diag.get('T2_divgrowth_q5q1_ann_survivors', 0) * 100:.2f} percent annualised long-short
        spread on surviving names and
        {diag.get('T2_divgrowth_q5q1_ann_full', 0) * 100:.2f} percent once delisted names are
        included. The micro-cap value composite produced a RankIC of
        {diag.get('T7_microvalue_ic_sizeq1', 0):.4f} in the smallest size quintile against
        {diag.get('T7_microvalue_ic_sizeq5', 0):.4f} in the largest, which is the signature of a
        capacity trap rather than a broad effect.
        """, "6,9")

    add("recommendation", "Recommendation", f"""
        Submit the {len(promoted)} promoted candidates to Model Validation as a single batch so the
        adjusted significance threshold is applied consistently across them. Hold the composite at
        paper weight until validation returns an independent verdict. Do not revisit the rejected
        hypotheses on this dataset: each rejection is a property of the data rather than of the
        implementation, and re-testing them would only inflate the trial count and raise the bar for
        everything tested afterwards. Log all ten hypotheses, including the rejected ones, in the
        research memory so the next run does not re-derive them.
        """, None)

    return pl.DataFrame(secs, infer_schema_length=None).with_row_index("id", offset=1).select(
        "id", "agent_run_id", "section_order", "section_type", "title", "body_text",
        "referenced_hypothesis_seqs",
    )


# ---------------------------------------------------------------------------
# Section 7. TSV 编排
# ---------------------------------------------------------------------------


def generate_all_tsv() -> None:
    """按拓扑顺序生成全部 29 张表的 TSV, 并打印十条陷阱的实测量级."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    def w(df: pl.DataFrame, name: str) -> None:
        df.write_csv(DATA_DIR / f"{name}.tsv", separator="\t")
        print(f"  {name:<32} {df.height:>9,} rows")

    df_asset_class = gen_asset_classes()
    df_sector = gen_sectors()
    df_regime_type = gen_regime_types()
    df_factor_theme = gen_factor_themes()
    df_universe = gen_universes()
    df_benchmark = gen_benchmarks()
    df_constraint = gen_constraint_sets()
    df_portfolio = gen_portfolios()
    df_calendar = gen_trading_calendar()

    month_ends = df_calendar.filter(pl.col("is_month_end") == 1)["trade_date"].to_list()
    regime_code_by_month = {m: _regime_for(me) for m, me in enumerate(month_ends)}
    regime_ids = {r["code"]: r["id"] for r in df_regime_type.to_dicts()}
    regime_by_month = {m: regime_ids[c] for m, c in regime_code_by_month.items()}

    df_asset = gen_assets(month_ends)
    df_regime_day = gen_market_regime_days(df_calendar)
    panel, quarters = build_monthly_panel(df_asset, month_ends)
    df_daily = gen_daily_bars(df_asset, df_calendar, panel, month_ends)
    # 基准必须从 daily_bar 自己算出来, 否则"组合收益减基准收益"这条文档反复
    # 推荐的算法会给出结构性偏负的主动收益.
    equity_ids = set(df_asset.filter(pl.col("asset_class_id") == 1)["id"].to_list())
    small_ids = set(df_asset.filter(
        (pl.col("asset_class_id") == 1) & pl.col("size_quintile").is_in([1, 2])
    )["id"].to_list())
    df_bench_daily = gen_benchmark_daily(
        df_calendar,
        _cap_weighted_daily_index(df_daily, equity_ids),
        _cap_weighted_daily_index(df_daily, small_ids),
    )

    # 把月末的市值、价差、ADV 并回面板. 池子划分与成本模型都要用到它们.
    me_snap = df_daily.filter(pl.col("trade_date").is_in(month_ends)).select(
        "asset_id", pl.col("trade_date").alias("obs_date"),
        pl.col("market_cap_usd_mm").alias("mcap"),
        pl.col("bid_ask_spread_bps").alias("spread_bps"),
        pl.col("adv_20d_usd").alias("adv_usd"),
        pl.col("adj_close").alias("adj_close_me"),
    )
    panel = panel.join(me_snap, on=["asset_id", "obs_date"], how="left").with_columns(
        pl.col("mcap").fill_null(100.0), pl.col("spread_bps").fill_null(40.0),
        pl.col("adv_usd").fill_null(1_000_000.0),
    ).with_columns(
        # mcap_rank 必须只在股票内部排名. 池子的划分 (top 500 / bottom 250) 是在
        # 已经过滤成 asset_class_id = 1 的帧上做的, 如果排名时把 40 个跨资产 ETF
        # 代理也算进去, 它们的市值恰好落在美股分布的中上段, 每个月会从 top 500
        # 里偷走二十几个名额, US_LARGE_500 就永远凑不满 500 只.
        # 给 ETF 一个负市值让它们统一排到所有股票之后, 就不会污染任何一个阈值.
        pl.when(pl.col("asset_class_id") == 1).then(pl.col("mcap")).otherwise(-1.0)
        .rank("ordinal", descending=True).over("obs_date").alias("mcap_rank")
    )
    # 官方 IC 口径用的前瞻收益, 必须是分析师能从 daily_bar 自己算出来的那一个 ——
    # 也就是月末复权价到下一个月末复权价的总收益, 而不是生成器内部的超额收益.
    # 两者只差一个 beta x 市场项, 但如果口径不一致, 谁也复现不出 factor_ic_monthly.
    #
    # 关键细节: 它必须完全在 **月末行情** 上算, 而不是在面板的"在池月份"上算.
    # 少数标的的 delisted_date 恰好落在某个月末当天 —— 那一天它还有行情, 但面板
    # 已经把它算作出池. 如果用面板做 shift, 这些标的上一个月的前瞻收益会被判成
    # NULL, 而任何照 SQL 文档 Q1 从 daily_bar 重算的人都会算出一个值, 于是
    # factor_ic_monthly 就无法被逐位复现了.
    bar_me = df_daily.filter(pl.col("trade_date").is_in(month_ends)).join(
        df_calendar.select("trade_date", "month_index"), on="trade_date", how="inner"
    ).select("asset_id", "month_index", "adj_close").sort("asset_id", "month_index")
    bar_me = bar_me.with_columns(
        pl.when(pl.col("month_index").shift(-1).over("asset_id") == pl.col("month_index") + 1)
        .then(pl.col("adj_close").shift(-1).over("asset_id") / pl.col("adj_close") - 1.0)
        .otherwise(None)
        .alias("fwd_total_return")
    ).select("asset_id", "month_index", "fwd_total_return")
    panel = panel.join(bar_me, on=["asset_id", "month_index"], how="left")

    df_fundamental = gen_fundamental_reports(df_asset, panel, quarters)
    df_estimate = gen_analyst_estimates(panel, df_asset)
    df_factor = gen_factors()
    df_exposure = gen_factor_exposures(panel, df_factor)
    df_ic, ic_aux = gen_factor_ic_monthly(panel, df_factor, regime_by_month)

    trial_by_code = {code: seq for seq, code, *_rest in HYPOTHESIS_DEFS}
    df_validation = gen_factor_validation_runs(ic_aux, df_factor, month_ends, trial_by_code)
    df_cov = gen_covariance_estimates(month_ends, regime_by_month, regime_code_by_month)
    df_bt_run, df_bt_monthly = gen_backtests(ic_aux, df_factor, df_validation, month_ends, regime_by_month)
    df_holding = gen_portfolio_holdings(panel, month_ends)
    df_attribution = gen_attribution_monthly(df_holding, panel, df_asset, df_factor, ic_aux)

    diag = compute_trap_diagnostics(panel, df_ic, df_factor, df_fundamental, df_exposure)
    df_run, df_hyp, df_step, df_finding, df_report = gen_agent_tables(
        df_factor, df_validation, df_ic, diag
    )

    w(df_asset_class, "01_asset_class")
    w(df_sector, "02_sector")
    w(df_regime_type, "03_regime_type")
    w(df_factor_theme, "04_factor_theme")
    w(df_universe, "05_universe")
    w(df_benchmark, "06_benchmark")
    w(df_constraint, "07_constraint_set")
    w(df_portfolio, "08_portfolio")
    w(df_calendar, "09_trading_calendar")
    w(df_asset, "10_asset")
    w(df_regime_day, "11_market_regime_day")
    w(df_bench_daily, "12_benchmark_daily")
    w(df_daily, "13_daily_bar")
    w(df_fundamental, "14_fundamental_report")
    w(df_estimate, "15_analyst_estimate")
    w(df_factor, "16_factor")
    w(df_exposure, "17_factor_exposure")
    w(df_ic, "18_factor_ic_monthly")
    w(df_validation, "19_factor_validation_run")
    w(df_cov, "20_covariance_estimate")
    w(df_bt_run, "21_backtest_run")
    w(df_bt_monthly, "22_backtest_monthly")
    w(df_holding, "23_portfolio_holding")
    w(df_attribution, "24_attribution_monthly")
    w(df_run, "25_agent_run")
    w(df_hyp, "26_agent_hypothesis")
    w(df_step, "27_agent_step")
    w(df_finding, "28_agent_finding")
    w(df_report, "29_agent_report_section")

    print("\n--- 陷阱实测量级 (文档里的数字必须和这里一致) ---")
    for k, v in diag.items():
        print(f"  {k:<38} {v: .5f}")
    print(f"\nGenerated all TSV files in {DATA_DIR}")


# ---------------------------------------------------------------------------
# Section 8. SQLite 构建
# ---------------------------------------------------------------------------


def create_sqlite_database() -> None:
    """按拓扑顺序把 TSV 批量灌进 SQLite. 一个事务, Core API executemany."""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order: list[tuple[str, Table]] = [
        ("01_asset_class", AssetClass.__table__),
        ("02_sector", Sector.__table__),
        ("03_regime_type", RegimeType.__table__),
        ("04_factor_theme", FactorTheme.__table__),
        ("05_universe", Universe.__table__),
        ("06_benchmark", Benchmark.__table__),
        ("07_constraint_set", ConstraintSet.__table__),
        ("08_portfolio", Portfolio.__table__),
        ("09_trading_calendar", TradingCalendar.__table__),
        ("10_asset", Asset.__table__),
        ("11_market_regime_day", MarketRegimeDay.__table__),
        ("12_benchmark_daily", BenchmarkDaily.__table__),
        ("13_daily_bar", DailyBar.__table__),
        ("14_fundamental_report", FundamentalReport.__table__),
        ("15_analyst_estimate", AnalystEstimate.__table__),
        ("16_factor", Factor.__table__),
        ("17_factor_exposure", FactorExposure.__table__),
        ("18_factor_ic_monthly", FactorIcMonthly.__table__),
        ("19_factor_validation_run", FactorValidationRun.__table__),
        ("20_covariance_estimate", CovarianceEstimate.__table__),
        ("21_backtest_run", BacktestRun.__table__),
        ("22_backtest_monthly", BacktestMonthly.__table__),
        ("23_portfolio_holding", PortfolioHolding.__table__),
        ("24_attribution_monthly", AttributionMonthly.__table__),
        ("25_agent_run", AgentRun.__table__),
        ("26_agent_hypothesis", AgentHypothesis.__table__),
        ("27_agent_step", AgentStep.__table__),
        ("28_agent_finding", AgentFinding.__table__),
        ("29_agent_report_section", AgentReportSection.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            # 日期列必须显式指定 dtype: 像 asset.delisted_date 这种前上千行全空的列,
            # 靠采样推断会被判成字符串, 灌库时 SQLAlchemy 会直接拒绝.
            overrides: dict[str, object] = {}
            for col in table.columns:
                if isinstance(col.type, DateTime):
                    overrides[col.name] = pl.Datetime
                elif isinstance(col.type, Date):
                    overrides[col.name] = pl.Date
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv", separator="\t", schema_overrides=overrides
            )
            if df.height == 0:
                continue
            # 百万行级别的表按块提交, 避免一次性物化上百万个 dict.
            for chunk in df.iter_slices(100_000):
                conn.execute(table.insert(), chunk.to_dicts())

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("Starting data generation...")
    generate_all_tsv()
    create_sqlite_database()
    print("All done!")


if __name__ == "__main__":
    main()
