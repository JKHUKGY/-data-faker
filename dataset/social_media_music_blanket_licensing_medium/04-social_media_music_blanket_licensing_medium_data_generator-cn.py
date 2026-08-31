"""
社交媒体 - 短视频平台音乐打包授权与合规稽核 假数据生成器
复杂度: Medium

业务背景:
ReelWave, Inc. 是一家总部位于旧金山的虚构短视频社交平台公司. 本数据集模拟其内部
"Sounds" 音乐团队与 20 家唱片厂牌/聚合发行商签订的打包授权 (blanket license) 合同,
平台曲库的月度使用数据、Creator Fund 周度分账、UGC remix 版权冲突稽核记录, 以及
120 个热门候选声音的每日精细化使用数据, 支持以下分析:

1. 曲库使用份额漂移 (usage share drift): 厂牌实际曲库使用份额相对签约时的假设发生
   了系统性偏离, 但年费从未跟着调整.
2. UGC 未授权采样合规稽核: 一批版权冲突标记长期悬而未决, 超过内部 30 天 SLA, 背后
   牵扯真实的广告收入风险敞口.
3. Creator Fund 热度快照错位: 爆火窗口恰好横跨两个自然周结算边界的声音, 每千次播放
   拿到的分成系统性低于爆火窗口完整落在一周内的声音.
4. MFN (最惠国) 条款合规稽核: 带 MFN 保护的厂牌 Titan Sound Group, 其有效费率低于
   没有 MFN 保护、但后来签约的 Northline Aggregator, 构成对 Titan 合同条款的违反.

上述陷阱通过有意设计的相关分布注入, 而非独立随机数. 对应的 SQL 查询位于
03-social_media_music_blanket_licensing_medium_sql_queries-cn.md, 用以暴露这些陷阱.
"""

from __future__ import annotations

import random
from datetime import date
from datetime import timedelta
from pathlib import Path

import polars as pl
from faker import Faker

from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import Numeric
from sqlalchemy import Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "social_media_music_blanket_licensing_medium.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间.
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期.
REFERENCE_DATE = date(2026, 6, 30)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ============================================================
# 第 4 节: 业务校准常量 (Business Calibration Constants)
# ============================================================

# --- 厂牌组合结构 ---
# 3 家大型厂牌 + 7 家中型厂牌 + 10 家独立聚合发行商 = 20 家, 与 ER 文档一致.
LABEL_TIER_COUNTS = {
    "major": 3,
    "mid_size": 7,
    "indie_aggregator": 10,
}

# 固定命名, 保证 Titan Sound Group (陷阱 4 受害方) 和 Northline Aggregator
# (陷阱 4 触发方) 每次生成都出现在同样的位置, 便于稽核脚本核对.
MAJOR_LABEL_NAMES = [
    "Titan Sound Group",
    "Meridian Recorded Music",
    "Cascade Harmonic Group",
]
MID_SIZE_LABEL_NAMES = [
    "Bluecrest Music Group",
    "Foundry Sound Partners",
    "Amberlight Recordings",
    "Ironwood Music Co.",
    "Solstice Recorded Arts",
    "Harborline Music Group",
    "Redwood Sound Partners",
]
INDIE_AGGREGATOR_NAMES = [
    "Northline Aggregator",
    "Coastal Wave Distribution",
    "Fernway Music Collective",
    "Basecamp Sound Aggregation",
    "Driftwood Indie Alliance",
    "Signal Path Music",
    "Lowlight Aggregator Group",
    "Tenfold Music Distribution",
    "Greenroom Indie Network",
    "Anchor Point Aggregation",
]

# --- 曲库使用份额假设 (签约时) ---
# 大型厂牌议价能力强, 份额假设通常更高; 独立聚合发行商刚起步, 份额假设很低.
USAGE_SHARE_ASSUMPTION_RANGE_BY_TIER = {
    "major": (16.0, 26.0),
    "mid_size": (5.0, 12.0),
    "indie_aggregator": (1.0, 5.0),
}
NORTHLINE_USAGE_SHARE_ASSUMPTION_PCT = 3.0  # Northline 归一化前的份额种子; 全场归一化到合计 100% 后约为 1.74 (即数据库里的最终值). 陷阱 4 真正依赖的是其有效费率 (NORTHLINE_EFFECTIVE_RATE_USD = 800k), 年费按"份额 x 费率"反推, 因此该费率不受归一化影响

# --- 合同期限与生效日期 ---
CONTRACT_TERM_MONTHS_BY_TIER = {
    "major": 36,
    "mid_size": 36,
    "indie_aggregator": 24,
}
CONTRACT_START_RANGE_BY_TIER = {
    # (起始日下界, 起始日上界) —— 大型厂牌签约最早, 独立聚合发行商普遍更晚签约,
    # 呼应"新兴聚合发行商靠激进报价抢曲库"这一行业背景. 每个区间都保证
    # start + 合同期限 > REFERENCE_DATE, 即"当前生效合同"在参考日这天真的还没到期
    # (不然 is_current=TRUE 但 contract_end_date 已经过去, 会自相矛盾).
    "major": (date(2023, 8, 1), date(2024, 7, 1)),
    "mid_size": (date(2023, 8, 1), date(2024, 10, 1)),
    "indie_aggregator": (date(2024, 8, 1), date(2025, 8, 1)),
}
NORTHLINE_CONTRACT_START_DATE = date(2026, 1, 15)  # 最近签约, 陷阱 4 的关键设定

# --- MFN (最惠国) 条款覆盖 ---
# 3 家大型厂牌全部带 MFN 保护(议价能力最强); 中型厂牌里随机 2 家带 MFN;
# 独立聚合发行商全部没有 MFN 保护(刚起步, 没有议价筹码).
MFN_HOLDER_COUNT_MID_SIZE = 2

# --- 有效费率 (每 1 个曲库使用份额百分点对应的年费, 美元) ---
# 这组常量是陷阱 4 (MFN 合规) 的核心: 精心构造出恰好一起、且只有一起 MFN 违反案例.
EFFECTIVE_RATE_RANGE_NON_MFN_INDIE = (280_000.0, 480_000.0)
EFFECTIVE_RATE_RANGE_NON_MFN_MID = (430_000.0, 620_000.0)
# Northline 的有效费率被刻意设为全部非 MFN 厂牌里的最高值, 且明显高于 Titan.
NORTHLINE_EFFECTIVE_RATE_USD = 800_000.0
# Titan 的有效费率被刻意设为低于 Northline, 构成对 Titan 自己 MFN 条款的违反.
TITAN_EFFECTIVE_RATE_RANGE = (680_000.0, 750_000.0)
# 其余带 MFN 保护的厂牌, 有效费率被设为安全地高于 max(非 MFN 费率), 不构成违反.
OTHER_MFN_RATE_MULTIPLIER_RANGE = (1.05, 1.20)

# --- 曲库规模 ---
NUM_OFFICIAL_TRACKS_BY_TIER = {
    "major": 50,  # 3 家 x 50 = 150
    "mid_size": 20,  # 7 家 x 20 = 140
    "indie_aggregator": 11,  # 10 家 x 11 = 110
}  # 官方曲目总数约 400, 与 ER 文档一致
NUM_SAMPLING_REMIXES = 130  # 采样了官方曲目的 UGC remix
NUM_ORIGINAL_REMIXES = 70  # 完全原创、不采样任何官方曲目的 UGC remix
NUM_MONITORED_REMIXES = 120  # 按热度评分选出的"热门候选声音", 才有每日精细化数据

GENRE_WEIGHTS = {
    "Pop": 0.30,
    "Hip-Hop": 0.22,
    "Electronic": 0.16,
    "R&B": 0.12,
    "Country": 0.10,
    "Indie Rock": 0.06,
    "Latin": 0.04,
}

# --- 歌名构造词表 ---
# 官方曲目和原创 remix 的标题用"形容词 + 名词 / 名词短语 / 动词 + 名词"组合成
# 像真实歌名的短语, 而不是 fake.catch_phrase() 那种企业口号 (如 "Multi-tiered
# local intranet"), 让一个音乐版权数据集读起来更可信. 采样类 remix 则用
# "名词词根 + 二创后缀"(如 "midnight sped up"), 承接 sound.title 的真实感.
SONG_TITLE_ADJECTIVES = [
    "Golden", "Midnight", "Neon", "Velvet", "Electric", "Silent", "Crimson",
    "Faded", "Wild", "Lonely", "Endless", "Broken", "Sacred", "Frozen",
    "Restless", "Hollow", "Gilded", "Distant", "Reckless", "Fading",
    "Scarlet", "Amber", "Cosmic", "Paper", "Weightless", "Feral",
]
SONG_TITLE_NOUNS = [
    "Hearts", "Nights", "Dreams", "Echoes", "Skyline", "Horizon", "Fire",
    "Rain", "Waves", "Shadows", "Lights", "Roads", "Summer", "Ghosts",
    "Static", "Neon", "Fever", "Bloom", "Static", "Currents", "Embers",
    "Mirage", "Gravity", "Silhouette", "Riptide", "Afterglow", "Lullaby",
]
SONG_TITLE_VERBS = [
    "Chasing", "Losing", "Breaking", "Falling", "Burning", "Dancing",
    "Drowning", "Running", "Fading", "Holding",
]
REMIX_TITLE_SUFFIXES = ["remix", "sped up", "slowed + reverb", "freestyle over it"]

# --- 创作者构成 ---
NUM_CREATORS = 150
CREATOR_TIER_WEIGHTS = {"top": 0.10, "mid": 0.30, "long_tail": 0.60}
# Creator Fund 分成的层级系数: 头部创作者内容质量/制作水平通常更高, 略微加成.
CREATOR_TIER_QUALITY_MULTIPLIER = {"top": 1.15, "mid": 1.00, "long_tail": 0.90}

# --- 曲库使用份额漂移 (陷阱 1) ---
# 20 家厂牌里, 5 家 "growth" 型份额上涨, 4 家 "decline" 型份额下跌, 11 家 "stable"
# 份额基本原封不动 (只吸收很小的残差调整); 3 家大型厂牌一律划入 stable (原因见
# `_pick_drift_targets`). growth/decline 都用"乘以签约假设的倍数"而不是加减固定
# 百分点, 避免小份额厂牌被减成负数; 倍数区间校准成两组总变动量大致相当.
USAGE_SHARE_DRIFT_GROWTH_COUNT = 5
USAGE_SHARE_DRIFT_DECLINE_COUNT = 4
USAGE_SHARE_DRIFT_GROWTH_MULTIPLIER_RANGE = (1.4, 1.8)  # 目标份额是签约假设的 1.4-1.8 倍
USAGE_SHARE_DRIFT_DECLINE_MULTIPLIER_RANGE = (0.25, 0.45)  # 目标份额萎缩到签约假设的 25%-45%
# 单家厂牌 pp 级漂移的硬顶/硬底: growth/decline 名额优先落在份额基数较大的 mid_size 上
# (见 `_pick_drift_targets`), 若大份额厂牌抽到极端倍数, 纯乘法会算出 +5pp 以上的漂移,
# 超过文档声明的 "+1~+4.5pp / -2~-4.8pp" 区间. 这里对绝对漂移量封顶, 让信号既够显著
# 又稳定落在声明区间内 (对小份额厂牌不 binding, 倍数天然算不到这么大的 pp).
USAGE_SHARE_DRIFT_MAX_GROWTH_PP = 4.1
USAGE_SHARE_DRIFT_MAX_DECLINE_PP = 4.4

# --- 月度曲库使用量池 ---
USAGE_MONTHS_COUNT = 18  # 2025-01 至 2026-06
LABELED_POOL_BASE_VIDEOS = 520_000  # 2025-01 当月, 可归属到某个厂牌的视频总量
LABELED_POOL_MONTHLY_GROWTH = 1.018  # 每月环比增长
ORIGINAL_POOL_BASE_VIDEOS = 55_000  # 2025-01 当月, 完全原创 remix 的视频总量
ORIGINAL_POOL_MONTHLY_GROWTH = 1.025

# --- 版权冲突标记 (陷阱 2) ---
RIGHTS_CONFLICT_FLAG_RATE = 0.45  # 130 个采样 remix 里约 45% 会被标记
CONFLICT_TYPE_WEIGHTS = {
    "unauthorized_sample": 0.55,
    "mismatched_metadata": 0.25,
    "duplicate_claim": 0.20,
}
RESOLUTION_STATUS_WEIGHTS = {
    "cleared": 0.28,
    "licensed_retroactively": 0.14,
    "takedown": 0.10,
    "under_review": 0.26,
    "open": 0.22,
}
SLA_DAYS_TARGET = 30
# 已解决记录里约一半实际处理时长超过 SLA, 制造"处理慢"这一真实存在的问题;
# 校准到 0.52 让全部标记的综合逾期占比稳定落在文档声明的 60%-65% 区间.
RESOLVED_LATE_PROBABILITY = 0.52
RESOLVED_ON_TIME_DAYS_RANGE = (5, 29)
RESOLVED_LATE_DAYS_RANGE = (31, 70)

# --- Creator Fund 分成 (陷阱 3) ---
CREATOR_FUND_BASE_RATE_PER_1000_VIEWS = 1.20  # 美元, 对齐案例的基础费率
# 爆火窗口跨自然周的声音, 有效费率打七折 —— 这就是陷阱 3 的量化定义 (每千次播放
# 分成比 aligned 声音低约 28%-30%, 校准到 0.70 让聚合口径稳定落在文档声明区间).
SPLIT_WEEK_ALIGNMENT_PENALTY_MULTIPLIER = 0.70
ACTIVE_WEEKS_LOOKBACK = 52  # Creator Fund 周度分账覆盖最近 52 周
SPIKE_VIEW_MULTIPLIER_RANGE = (12.0, 30.0)  # 爆火周相对基线播放量的倍数

# --- 每日爆火窗口 (仅 120 个被监控声音) ---
DAILY_WINDOW_DAYS_BEFORE_SPIKE = 20
DAILY_WINDOW_DAYS_AFTER_SPIKE = 24  # 共 45 天窗口
DAILY_SPIKE_CORE_MULTIPLIER_RANGE = (15.0, 40.0)
DAILY_SHOULDER_MULTIPLIER_RANGE = (3.0, 8.0)  # 爆火核心日前后 1-2 天的过渡倍数


def add_months(start: date, n: int) -> date:
    """给定日期所在月份的第一天, 向后推 n 个月, 返回目标月份第一天."""
    month_index = start.month - 1 + n
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def most_recent_monday(d: date) -> date:
    """返回不晚于 d 的最近一个周一日期."""
    return d - timedelta(days=d.weekday())


def compute_spike_anchor_date(sound: dict) -> date:
    """给热门候选声音计算爆火核心的锚点日期. `creator_fund_weekly_payout`
    (决定哪一周或哪两周套用爆火倍数) 和 `sound_daily_viral_window` (决定
    45 天精细化窗口居中在哪) 都调用这个函数, 保证同一个声音在两张表里的
    爆火时间点完全一致, 不会出现"周度分账的爆火周"和"每日曲线的爆火日"
    对不上号的情况. 用 sound_id 派生一个独立的随机源 (而不是共享的全局
    random 状态), 这样无论先调用哪张表的生成函数, 结果都相同.
    """
    local_rng = random.Random(RANDOM_SEED * 1_000_003 + sound["id"])
    release = sound["release_date"]
    if sound["spike_week_alignment"] == "aligned":
        candidate_weekdays = (1, 2)  # 周二/周三, 保证 3-4 天核心窗口不跨自然周边界
    else:
        candidate_weekdays = (5,)  # 周六, 让核心窗口横跨到下周一/周二
    # 爆火核心日必须让 45 天窗口 [core-20, core+24] 完整落在
    # [release_date, REFERENCE_DATE] 内, 否则 sound_daily_viral_window 会生成
    # 越过参考日的未来日期, 破坏"所有数据锚定固定快照日"的语义.
    #   下界: 优先 release+60 (更真实的发酵期); 若发布很晚导致 60 天窗口越界,
    #         退回到 release+20 (让窗口头部刚好不早于 release_date).
    #   上界: min(release+320, REFERENCE_DATE-25), 后者保证窗口尾部 (+24 天) 不
    #         越过参考日, 留 1 天余量.
    latest_valid = REFERENCE_DATE - timedelta(days=25)
    lower = release + timedelta(days=60)
    if lower > latest_valid:
        lower = release + timedelta(days=20)
    upper = min(release + timedelta(days=320), latest_valid)
    if lower > upper:
        # 极端晚发布, 连最小窗口都放不下: 直接夹到最晚合法锚点.
        return latest_valid
    candidates = [
        offset
        for offset in range((lower - release).days, (upper - release).days + 1)
        if (release + timedelta(days=offset)).weekday() in candidate_weekdays
    ]
    if candidates:
        return release + timedelta(days=local_rng.choice(candidates))
    # 合法区间内没有匹配到目标星期几 (窗口极窄): 夹到最晚合法锚点保证不越界.
    return latest_valid


def weighted_choice(weights: dict[str, float]) -> str:
    """按字典给出的权重做一次加权抽样, 返回抽中的 key."""
    keys = list(weights.keys())
    values = list(weights.values())
    return random.choices(keys, weights=values, k=1)[0]


def make_song_title() -> str:
    """用词表拼出一个"像歌名"的短标题, 供官方曲目和原创 remix 使用.
    随机在几种常见歌名句式之间切换 (形容词+名词 / 名词 in the 名词 /
    单名词 / 动词+名词), 制造足够的多样性又不失音乐感."""
    noun = random.choice(SONG_TITLE_NOUNS)
    roll = random.random()
    if roll < 0.40:
        return f"{random.choice(SONG_TITLE_ADJECTIVES)} {noun}"
    if roll < 0.68:
        other = random.choice(SONG_TITLE_NOUNS)
        while other == noun:
            other = random.choice(SONG_TITLE_NOUNS)
        return f"{noun} in the {other}"
    if roll < 0.85:
        return noun
    return f"{random.choice(SONG_TITLE_VERBS)} {noun}"


USAGE_MONTHS = [add_months(date(2025, 1, 1), i) for i in range(USAGE_MONTHS_COUNT)]
LATEST_MONDAY = most_recent_monday(REFERENCE_DATE)
ALL_WEEK_STARTS = [
    LATEST_MONDAY - timedelta(weeks=i) for i in range(ACTIVE_WEEKS_LOOKBACK)
][::-1]  # 从最早到最近排列


# ============================================================
# 第 5 节: ORM 模型
# ============================================================


class Base(DeclarativeBase):
    pass


class Label(Base):
    """签订打包授权合同的唱片厂牌或聚合发行商."""

    __tablename__ = "label"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    label_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    hq_country: Mapped[str] = mapped_column(String(20), nullable=False)
    onboarded_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Creator(Base):
    """在 ReelWave 上发布 UGC remix、有资格参与 Creator Fund 分成的创作者."""

    __tablename__ = "creator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    handle: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(20), nullable=False)
    join_date: Mapped[date] = mapped_column(Date, nullable=False)
    creator_tier: Mapped[str] = mapped_column(String(20), nullable=False)


class LabelBlanketLicense(Base):
    """厂牌当前生效的打包授权合同条款: 份额假设, 年费, MFN 保护."""

    __tablename__ = "label_blanket_license"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    label_id: Mapped[int] = mapped_column(ForeignKey("label.id"), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    usage_share_assumption_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    annual_license_fee_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    has_mfn_clause: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Sound(Base):
    """平台内被追踪的一段音乐素材: 官方曲目或用户二创 remix."""

    __tablename__ = "sound"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sound_type: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_label_id: Mapped[int | None] = mapped_column(ForeignKey("label.id"))
    source_sound_id: Mapped[int | None] = mapped_column(ForeignKey("sound.id"))
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("creator.id"))
    genre: Mapped[str] = mapped_column(String(30), nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_trending_monitored: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spike_week_alignment: Mapped[str | None] = mapped_column(String(20))
    popularity_score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)


class LicenseFeePayment(Base):
    """打包授权合同的季度实付款记录."""

    __tablename__ = "license_fee_payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    license_id: Mapped[int] = mapped_column(ForeignKey("label_blanket_license.id"), nullable=False)
    payment_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    payment_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paid_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)


class SoundMonthlyUsage(Base):
    """每个声音每月的视频量和播放量汇总, 是曲库使用份额计算的原始事实数据."""

    __tablename__ = "sound_monthly_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    usage_month: Mapped[date] = mapped_column(Date, nullable=False)
    video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False)


class RightsConflictFlag(Base):
    """UGC remix 因疑似未授权采样等原因被标记的版权冲突记录."""

    __tablename__ = "rights_conflict_flag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    remix_sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(30), nullable=False)
    flagged_date: Mapped[date] = mapped_column(Date, nullable=False)
    sla_days_target: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(30), nullable=False)
    resolved_date: Mapped[date | None] = mapped_column(Date)
    revenue_at_risk_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class CreatorFundWeeklyPayout(Base):
    """Creator Fund 按自然周给 UGC remix 及其创作者计算的分成记录."""

    __tablename__ = "creator_fund_weekly_payout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    remix_sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.id"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekly_video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_view_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    payout_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class SoundDailyViralWindow(Base):
    """120 个热门候选声音在爆火前后约 45 天窗口内的每日播放量明细."""

    __tablename__ = "sound_daily_viral_window"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    sound_id: Mapped[int] = mapped_column(ForeignKey("sound.id"), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_video_count: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_view_count: Mapped[int] = mapped_column(Integer, nullable=False)


# ============================================================
# 第 6 节: 生成器函数 (拓扑顺序)
# ============================================================


def gen_labels() -> pl.DataFrame:
    """生成 20 家厂牌, 固定命名以承载陷阱 4 的 Titan / Northline 案例."""
    rows = []
    label_id = 1
    tier_name_pools = {
        "major": MAJOR_LABEL_NAMES,
        "mid_size": MID_SIZE_LABEL_NAMES,
        "indie_aggregator": INDIE_AGGREGATOR_NAMES,
    }
    for tier, names in tier_name_pools.items():
        for name in names:
            if name == "Northline Aggregator":
                onboarded = date(2025, 8, 1)
            elif tier == "major":
                onboarded = fake.date_between(date(2019, 6, 1), date(2020, 12, 1))
            elif tier == "mid_size":
                onboarded = fake.date_between(date(2020, 6, 1), date(2022, 6, 1))
            else:
                onboarded = fake.date_between(date(2021, 6, 1), date(2024, 6, 1))
            rows.append(
                {
                    "id": label_id,
                    "label_name": name,
                    "label_tier": tier,
                    "hq_country": "US" if random.random() < 0.85 else "Canada",
                    "onboarded_date": onboarded,
                    "is_active": True,
                }
            )
            label_id += 1
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_creators() -> pl.DataFrame:
    """生成 150 位有 Creator Fund 资格的创作者."""
    rows = []
    for creator_id in range(1, NUM_CREATORS + 1):
        tier = weighted_choice(CREATOR_TIER_WEIGHTS)
        rows.append(
            {
                "id": creator_id,
                "handle": f"@{fake.user_name()}.{creator_id}",
                "country": "US" if random.random() < 0.82 else "Canada",
                "join_date": fake.date_between(date(2022, 1, 1), date(2026, 3, 1)),
                "creator_tier": tier,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_label_blanket_licenses(labels_df: pl.DataFrame) -> pl.DataFrame:
    """生成每家厂牌当前生效的打包授权合同. 精心构造陷阱 4 的唯一 MFN 违反案例."""
    labels = labels_df.to_dicts()
    by_name = {row["label_name"]: row for row in labels}

    # 第一步: 决定谁有 MFN 保护.
    mid_size_labels = [row for row in labels if row["label_tier"] == "mid_size"]
    mfn_mid_size_names = {
        row["label_name"]
        for row in random.sample(mid_size_labels, MFN_HOLDER_COUNT_MID_SIZE)
    }
    has_mfn_by_name = {}
    for row in labels:
        if row["label_tier"] == "major":
            has_mfn_by_name[row["label_name"]] = True
        elif row["label_name"] in mfn_mid_size_names:
            has_mfn_by_name[row["label_name"]] = True
        else:
            has_mfn_by_name[row["label_name"]] = False

    # 第二步: 决定份额假设. 20 份合同是独立谈出来的, 但既然它们共同覆盖了整个
    # "可归属曲库"的播放量, 一份份额假设合理的做法是让它们的总和大致落在 100%
    # 附近 —— 否则每家厂牌的"假设"和"实际"之间会出现一个和陷阱 1 无关的系统性
    # 缩放偏差, 掩盖掉刻意设计的 growth/decline/stable 信号.
    raw_usage_share_by_name = {}
    for row in labels:
        if row["label_name"] == "Northline Aggregator":
            raw_usage_share_by_name[row["label_name"]] = NORTHLINE_USAGE_SHARE_ASSUMPTION_PCT
        else:
            low, high = USAGE_SHARE_ASSUMPTION_RANGE_BY_TIER[row["label_tier"]]
            raw_usage_share_by_name[row["label_name"]] = random.uniform(low, high)
    raw_total = sum(raw_usage_share_by_name.values())
    rescale_factor = 100.0 / raw_total
    usage_share_by_name = {
        name: round(value * rescale_factor, 2) for name, value in raw_usage_share_by_name.items()
    }

    # 第三步: 先算所有"没有 MFN 保护"的厂牌的有效费率, 找出其中的最大值.
    effective_rate_by_name = {}
    for row in labels:
        name = row["label_name"]
        if has_mfn_by_name[name]:
            continue
        if name == "Northline Aggregator":
            effective_rate_by_name[name] = NORTHLINE_EFFECTIVE_RATE_USD
        elif row["label_tier"] == "indie_aggregator":
            effective_rate_by_name[name] = random.uniform(*EFFECTIVE_RATE_RANGE_NON_MFN_INDIE)
        else:
            effective_rate_by_name[name] = random.uniform(*EFFECTIVE_RATE_RANGE_NON_MFN_MID)
    max_non_mfn_rate = max(effective_rate_by_name.values())

    # 第四步: 带 MFN 保护的厂牌. Titan 被刻意设为低于 max_non_mfn_rate (违反 MFN);
    # 其余 MFN 厂牌被设为安全地高于这个值 (合规).
    for row in labels:
        name = row["label_name"]
        if not has_mfn_by_name[name]:
            continue
        if name == "Titan Sound Group":
            effective_rate_by_name[name] = random.uniform(*TITAN_EFFECTIVE_RATE_RANGE)
        else:
            effective_rate_by_name[name] = max_non_mfn_rate * random.uniform(
                *OTHER_MFN_RATE_MULTIPLIER_RANGE
            )

    rows = []
    license_id = 1
    for row in labels:
        name = row["label_name"]
        tier = row["label_tier"]
        if name == "Northline Aggregator":
            start = NORTHLINE_CONTRACT_START_DATE
        else:
            low, high = CONTRACT_START_RANGE_BY_TIER[tier]
            start = fake.date_between(low, high)
        term_months = CONTRACT_TERM_MONTHS_BY_TIER[tier]
        end = add_months(start, term_months) - timedelta(days=1)
        usage_share = usage_share_by_name[name]
        effective_rate = effective_rate_by_name[name]
        annual_fee = round(effective_rate * usage_share, 2)
        rows.append(
            {
                "id": license_id,
                "label_id": by_name[name]["id"],
                "contract_start_date": start,
                "contract_end_date": end,
                "usage_share_assumption_pct": usage_share,
                "annual_license_fee_usd": annual_fee,
                "has_mfn_clause": has_mfn_by_name[name],
                "is_current": True,
            }
        )
        license_id += 1
    return pl.DataFrame(rows, infer_schema_length=None)


def _pick_drift_targets(labels: list[dict]) -> dict[int, str]:
    """把 20 家厂牌分成 growth / decline / stable 三类, Northline 固定 growth,
    Titan 固定 stable, 其余厂牌随机分配, 呼应 ER 文档规定的 5/4/11 分布.

    3 家大型厂牌一律划入 stable: 大型厂牌曲库分散在成百上千首歌里, 单月份额
    本来就不容易被一两首歌带动大幅波动; 而且如果让份额基数动辄 15%+ 的大型
    厂牌也参与 growth/decline 的大幅漂移, 零和约束下需要挪动的份额会大到把
    stable 组一起拖下水, 详见 gen_sound_monthly_usage 里的说明.
    """
    eligible = [
        row
        for row in labels
        if row["label_tier"] != "major" and row["label_name"] != "Northline Aggregator"
    ]
    random.shuffle(eligible)
    # 让 growth/decline 名额优先落在 mid_size 厂牌上: 它们归一化后的份额基数
    # (约 3-8pp) 明显大于独立聚合发行商 (约 1-2.5pp), 乘以漂移倍数后产生的 pp 级
    # 漂移更显著, 能稳定落在文档声明的 +1~+4.5pp / -2~-4.8pp 区间; 若把名额随机
    # 分给微小份额的独立发行商, 漂移信号会被压平到 ±1pp 以内、失去教学冲击力.
    # sorted 是稳定排序, mid_size 内部仍保留上面 shuffle 出的随机次序.
    remaining = sorted(eligible, key=lambda r: 0 if r["label_tier"] == "mid_size" else 1)
    drift_type_by_id = {}
    for row in labels:
        if row["label_name"] == "Northline Aggregator":
            drift_type_by_id[row["id"]] = "growth"
        elif row["label_tier"] == "major":
            drift_type_by_id[row["id"]] = "stable"
    remaining_growth = USAGE_SHARE_DRIFT_GROWTH_COUNT - 1  # Northline 已经占了一个 growth 名额
    remaining_decline = USAGE_SHARE_DRIFT_DECLINE_COUNT
    idx = 0
    for _ in range(remaining_growth):
        drift_type_by_id[remaining[idx]["id"]] = "growth"
        idx += 1
    for _ in range(remaining_decline):
        drift_type_by_id[remaining[idx]["id"]] = "decline"
        idx += 1
    while idx < len(remaining):
        drift_type_by_id[remaining[idx]["id"]] = "stable"
        idx += 1
    return drift_type_by_id


def gen_sounds(labels_df: pl.DataFrame, creators_df: pl.DataFrame) -> pl.DataFrame:
    """生成 600 个声音: 400 首官方曲目 + 200 个 UGC remix (含自引用采样关系)."""
    labels = labels_df.to_dicts()
    creator_ids = creators_df["id"].to_list()

    rows = []
    sound_id = 1
    official_track_ids_by_label: dict[int, list[int]] = {row["id"]: [] for row in labels}
    all_official_track_ids: list[int] = []
    official_popularity: dict[int, float] = {}
    official_release_by_id: dict[int, date] = {}

    # 官方曲目: 全部早于曲库使用窗口起点 (2025-01-01), 保证签约初期就有完整曲库.
    for row in labels:
        n_tracks = NUM_OFFICIAL_TRACKS_BY_TIER[row["label_tier"]]
        for _ in range(n_tracks):
            popularity = min(8.0, random.paretovariate(2.3))
            release = fake.date_between(date(2021, 1, 1), date(2024, 12, 1))
            rows.append(
                {
                    "id": sound_id,
                    "title": make_song_title(),
                    "sound_type": "official_track",
                    "primary_label_id": row["id"],
                    "source_sound_id": None,
                    "creator_id": None,
                    "genre": weighted_choice(GENRE_WEIGHTS),
                    "release_date": release,
                    "is_trending_monitored": False,
                    "spike_week_alignment": None,
                    "popularity_score": round(popularity, 4),
                }
            )
            official_track_ids_by_label[row["id"]].append(sound_id)
            all_official_track_ids.append(sound_id)
            official_popularity[sound_id] = popularity
            official_release_by_id[sound_id] = release
            sound_id += 1

    # 采样 remix 的来源官方曲目按热度加权抽取, 越热门的官方曲目越容易被采样;
    # 具体候选在下方按"发布日早于该 remix"过滤后再加权 (见 is_sampling 分支).

    # 先给每个创作者保底分配一个 remix, 保证 150 位创作者全部至少有一个作品,
    # 剩余的 remix 名额再按创作者层级加权抽样, 制造"部分创作者有多个 remix"的现实分布.
    creator_tier_by_id = dict(zip(creators_df["id"].to_list(), creators_df["creator_tier"].to_list()))
    tier_weight_for_extra = {"top": 3.0, "mid": 1.5, "long_tail": 1.0}
    total_remixes = NUM_SAMPLING_REMIXES + NUM_ORIGINAL_REMIXES
    remix_creator_ids = list(creator_ids)  # 前 150 个 remix 保底分配
    extra_count = total_remixes - len(creator_ids)
    extra_weights = [tier_weight_for_extra[creator_tier_by_id[cid]] for cid in creator_ids]
    remix_creator_ids += random.choices(creator_ids, weights=extra_weights, k=extra_count)
    random.shuffle(remix_creator_ids)

    remix_popularity: dict[int, float] = {}
    remix_release_dates: dict[int, date] = {}
    remix_ids: list[int] = []
    remix_creator_map: dict[int, int] = {}
    remix_source_map: dict[int, int | None] = {}

    creator_cursor = 0
    for i in range(total_remixes):
        is_sampling = i < NUM_SAMPLING_REMIXES
        popularity = min(6.0, random.paretovariate(2.1))
        release = fake.date_between(date(2024, 6, 1), date(2026, 5, 15))
        creator_id = remix_creator_ids[creator_cursor]
        creator_cursor += 1
        if is_sampling:
            # 采样源必须早于该 remix 自身发布日 (ER 时序规则: 被采样的官方曲目
            # release_date < remix.release_date). 官方曲目全部早于 2025-01-01,
            # remix 最早 2024-06, 所以合格候选恒非空; 仍按热度加权抽取.
            eligible_source_ids = [
                sid for sid in all_official_track_ids if official_release_by_id[sid] < release
            ]
            eligible_weights = [official_popularity[sid] for sid in eligible_source_ids]
            source_id = random.choices(eligible_source_ids, weights=eligible_weights, k=1)[0]
            title_suffix = random.choice(REMIX_TITLE_SUFFIXES)
            title = f"{random.choice(SONG_TITLE_NOUNS).lower()} {title_suffix}"
        else:
            source_id = None
            title = make_song_title()
        rows.append(
            {
                "id": sound_id,
                "title": title,
                "sound_type": "ugc_remix",
                "primary_label_id": None,
                "source_sound_id": source_id,
                "creator_id": creator_id,
                "genre": weighted_choice(GENRE_WEIGHTS),
                "release_date": release,
                "is_trending_monitored": False,  # 下面按热度排序后再回填
                "spike_week_alignment": None,
                "popularity_score": round(popularity, 4),
            }
        )
        remix_popularity[sound_id] = popularity
        remix_release_dates[sound_id] = release
        remix_ids.append(sound_id)
        remix_creator_map[sound_id] = creator_id
        remix_source_map[sound_id] = source_id
        sound_id += 1

    # 按热度评分选出前 120 个作为"热门候选声音", 一半 aligned 一半 split_across_weeks.
    monitored_ids = sorted(remix_ids, key=lambda sid: remix_popularity[sid], reverse=True)[
        :NUM_MONITORED_REMIXES
    ]
    monitored_set = set(monitored_ids)
    alignment_pool = ["aligned"] * (NUM_MONITORED_REMIXES // 2) + ["split_across_weeks"] * (
        NUM_MONITORED_REMIXES - NUM_MONITORED_REMIXES // 2
    )
    random.shuffle(alignment_pool)
    alignment_by_id = dict(zip(monitored_ids, alignment_pool))

    for r in rows:
        if r["id"] in monitored_set:
            r["is_trending_monitored"] = True
            r["spike_week_alignment"] = alignment_by_id[r["id"]]

    return pl.DataFrame(rows, infer_schema_length=None)


def gen_license_fee_payments(licenses_df: pl.DataFrame) -> pl.DataFrame:
    """按季度生成每份合同从签约日到参考日的全部实付款记录 (不做回溯期数封顶).

    Query 14 用"合同已生效时长比例 × 年费"作为"按时间进度应付", 因此实付款必须
    从签约日起完整覆盖到参考日, 累计实付才能和应付口径对齐. 若像早期版本那样只
    保留近 2 年 (8 期), 大型厂牌 3 年期老合同的"应付"按 2.5-2.9 年算、实付只有
    2 年, 会凭空产生百万级系统性负差, 与 Query 14 "只有季度后付制自然滞后"的
    教学预期直接打架. 现在唯一的差异只剩"当期尚未结算" (季度后付) 带来的、上限
    为一个季度年费的滞后.
    """
    rows = []
    payment_id = 1
    for lic in licenses_df.to_dicts():
        quarterly_amount = round(lic["annual_license_fee_usd"] / 4.0, 2)
        period_start = lic["contract_start_date"]
        while period_start <= REFERENCE_DATE:
            period_end = add_months(period_start, 3) - timedelta(days=1)
            if period_end > REFERENCE_DATE:
                break
            amount = round(quarterly_amount * random.uniform(0.99, 1.01), 2)
            payment_date = period_end + timedelta(days=random.randint(10, 20))
            rows.append(
                {
                    "id": payment_id,
                    "license_id": lic["id"],
                    "payment_period_start": period_start,
                    "payment_period_end": period_end,
                    "amount_paid_usd": amount,
                    "payment_date": payment_date,
                }
            )
            payment_id += 1
            period_start = add_months(period_start, 3)
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_sound_monthly_usage(sounds_df: pl.DataFrame, labels_df: pl.DataFrame, licenses_df: pl.DataFrame) -> pl.DataFrame:
    """生成 18 个月的月度使用数据, 精心构造陷阱 1 (曲库使用份额漂移)."""
    labels = labels_df.to_dicts()
    licenses = licenses_df.to_dicts()
    usage_share_assumption_by_label_id = {lic["label_id"]: lic["usage_share_assumption_pct"] for lic in licenses}
    drift_type_by_label_id = _pick_drift_targets(labels)

    # 曲库使用份额是零和的 (20 家厂牌份额之和恒为 100%): 任何一家厂牌涨的份额,
    # 都必须来自其他厂牌跌的份额. growth 用"乘以一个倍数"而不是加一个固定百分点,
    # 这样无论抽到哪家厂牌都不会把目标算成负数, 也不需要额外的下限保护. growth
    # 和 decline 的倍数区间被校准成两组总的"份额变动量"大致相当 (grow 组平均
    # 每家多拿约自身份额的 60%, decline 组平均每家失去约自身份额的 65%, 两组
    # 都只从大型厂牌以外的 9 家厂牌里挑选, 详见 `_pick_drift_targets`), 让两组
    # 近似在内部自成闭环. 剩余的小额不平衡按厂牌规模比例摊到 11 家 stable 厂牌
    # (含全部 3 家大型厂牌) 身上, 残差通常很小, 每家分到的调整量可以忽略不计.
    stable_ids = [lid for lid, t in drift_type_by_label_id.items() if t == "stable"]
    growth_ids = [lid for lid, t in drift_type_by_label_id.items() if t == "growth"]
    decline_ids = [lid for lid, t in drift_type_by_label_id.items() if t == "decline"]

    final_target_share_by_label_id = {}
    for lid in growth_ids:
        assumption = usage_share_assumption_by_label_id[lid]
        target = assumption * random.uniform(*USAGE_SHARE_DRIFT_GROWTH_MULTIPLIER_RANGE)
        # pp 级硬顶: 大份额厂牌抽到高倍数时, 绝对漂移不超过约 +4.5pp.
        final_target_share_by_label_id[lid] = min(target, assumption + USAGE_SHARE_DRIFT_MAX_GROWTH_PP)
    for lid in decline_ids:
        assumption = usage_share_assumption_by_label_id[lid]
        target = assumption * random.uniform(*USAGE_SHARE_DRIFT_DECLINE_MULTIPLIER_RANGE)
        # pp 级硬底: 绝对漂移不低于约 -4.8pp.
        final_target_share_by_label_id[lid] = max(target, assumption - USAGE_SHARE_DRIFT_MAX_DECLINE_PP)
    for lid in stable_ids:
        final_target_share_by_label_id[lid] = usage_share_assumption_by_label_id[lid]

    residual = 100.0 - sum(final_target_share_by_label_id.values())
    stable_total_assumption = sum(usage_share_assumption_by_label_id[lid] for lid in stable_ids)
    for lid in stable_ids:
        weight = usage_share_assumption_by_label_id[lid] / stable_total_assumption
        final_target_share_by_label_id[lid] += residual * weight

    sounds = sounds_df.to_dicts()
    official_tracks_by_label: dict[int, list[dict]] = {row["id"]: [] for row in labels}
    official_track_by_id: dict[int, dict] = {}
    for s in sounds:
        if s["sound_type"] == "official_track":
            official_tracks_by_label[s["primary_label_id"]].append(s)
            official_track_by_id[s["id"]] = s

    sampling_remixes_by_label: dict[int, list[dict]] = {row["id"]: [] for row in labels}
    original_remixes: list[dict] = []
    for s in sounds:
        if s["sound_type"] != "ugc_remix":
            continue
        if s["source_sound_id"] is not None:
            source_label_id = official_track_by_id[s["source_sound_id"]]["primary_label_id"]
            sampling_remixes_by_label[source_label_id].append(s)
        else:
            original_remixes.append(s)

    rows = []
    usage_id = 1

    for month_index, month in enumerate(USAGE_MONTHS):
        # 每个月各厂牌的份额: 从签约假设线性插值到该厂牌的最终目标份额, 加噪声, 再归一化.
        raw_shares = {}
        for row in labels:
            assumption = usage_share_assumption_by_label_id[row["id"]]
            target = final_target_share_by_label_id[row["id"]]
            progress = month_index / (USAGE_MONTHS_COUNT - 1)
            share = assumption + (target - assumption) * progress + random.uniform(-0.4, 0.4)
            raw_shares[row["id"]] = max(0.5, min(35.0, share))
        share_sum = sum(raw_shares.values())
        normalized_shares = {lid: value / share_sum * 100.0 for lid, value in raw_shares.items()}

        pool = LABELED_POOL_BASE_VIDEOS * (LABELED_POOL_MONTHLY_GROWTH**month_index)

        for row in labels:
            label_id = row["id"]
            label_videos = pool * normalized_shares[label_id] / 100.0
            eligible = list(official_tracks_by_label[label_id])
            for remix in sampling_remixes_by_label[label_id]:
                if remix["release_date"] <= month:
                    eligible.append(remix)
            weight_sum = sum(s["popularity_score"] for s in eligible)
            if weight_sum <= 0:
                continue
            for s in eligible:
                video_count = max(1, round(label_videos * s["popularity_score"] / weight_sum))
                avg_views_per_video = 300.0 * (1.0 + s["popularity_score"]) * random.uniform(0.85, 1.15)
                view_count = max(video_count, round(video_count * avg_views_per_video))
                rows.append(
                    {
                        "id": usage_id,
                        "sound_id": s["id"],
                        "usage_month": month,
                        "video_count": video_count,
                        "view_count": view_count,
                    }
                )
                usage_id += 1

        # 完全原创 remix 的用量来自一个独立的、更小的资金池, 与厂牌无关.
        original_pool = ORIGINAL_POOL_BASE_VIDEOS * (ORIGINAL_POOL_MONTHLY_GROWTH**month_index)
        eligible_original = [s for s in original_remixes if s["release_date"] <= month]
        weight_sum = sum(s["popularity_score"] for s in eligible_original)
        if weight_sum > 0:
            for s in eligible_original:
                video_count = max(1, round(original_pool * s["popularity_score"] / weight_sum))
                avg_views_per_video = 280.0 * (1.0 + s["popularity_score"]) * random.uniform(0.85, 1.15)
                view_count = max(video_count, round(video_count * avg_views_per_video))
                rows.append(
                    {
                        "id": usage_id,
                        "sound_id": s["id"],
                        "usage_month": month,
                        "video_count": video_count,
                        "view_count": view_count,
                    }
                )
                usage_id += 1

    return pl.DataFrame(rows, infer_schema_length=None)


def gen_rights_conflict_flags(sounds_df: pl.DataFrame) -> pl.DataFrame:
    """生成版权冲突标记, 精心构造陷阱 2 (约 45%-55% 的记录构成 SLA 逾期)."""
    sampling_remixes = sounds_df.filter(
        (pl.col("sound_type") == "ugc_remix") & (pl.col("source_sound_id").is_not_null())
    ).to_dicts()
    n_flagged = round(len(sampling_remixes) * RIGHTS_CONFLICT_FLAG_RATE)
    flagged_remixes = random.sample(sampling_remixes, n_flagged)

    rows = []
    flag_id = 1
    for remix in flagged_remixes:
        release = remix["release_date"]
        latest_possible = REFERENCE_DATE - timedelta(days=5)
        earliest_possible = release + timedelta(days=7)
        if earliest_possible >= latest_possible:
            continue
        flagged_date = fake.date_between(earliest_possible, latest_possible)
        resolution_status = weighted_choice(RESOLUTION_STATUS_WEIGHTS)

        resolved_date = None
        if resolution_status in ("cleared", "licensed_retroactively", "takedown"):
            if random.random() < RESOLVED_LATE_PROBABILITY:
                days = random.randint(*RESOLVED_LATE_DAYS_RANGE)
            else:
                days = random.randint(*RESOLVED_ON_TIME_DAYS_RANGE)
            candidate = flagged_date + timedelta(days=days)
            resolved_date = min(candidate, REFERENCE_DATE)

        revenue_at_risk = round(
            400.0 + remix["popularity_score"] * 2500.0 + random.uniform(-200.0, 800.0), 2
        )
        revenue_at_risk = max(300.0, revenue_at_risk)

        rows.append(
            {
                "id": flag_id,
                "remix_sound_id": remix["id"],
                "conflict_type": weighted_choice(CONFLICT_TYPE_WEIGHTS),
                "flagged_date": flagged_date,
                "sla_days_target": SLA_DAYS_TARGET,
                "resolution_status": resolution_status,
                "resolved_date": resolved_date,
                "revenue_at_risk_usd": revenue_at_risk,
            }
        )
        flag_id += 1
    return pl.DataFrame(rows, infer_schema_length=None)


def gen_creator_fund_weekly_payouts(sounds_df: pl.DataFrame, creators_df: pl.DataFrame) -> pl.DataFrame:
    """生成 Creator Fund 周度分账记录, 精心构造陷阱 3 (跨周声音有效费率低约 28%)."""
    creator_tier_by_id = dict(zip(creators_df["id"].to_list(), creators_df["creator_tier"].to_list()))
    remixes = sounds_df.filter(pl.col("sound_type") == "ugc_remix").to_dicts()

    rows = []
    payout_id = 1
    week_view_accumulator: dict[date, list[dict]] = {w: [] for w in ALL_WEEK_STARTS}

    for remix in remixes:
        remix_monday = most_recent_monday(remix["release_date"])
        active_weeks = [w for w in ALL_WEEK_STARTS if w >= remix_monday]
        if not active_weeks:
            continue

        # 为热门候选声音选定爆火周(一周或两个相邻周), 决定何时套用 spike 倍数.
        # 爆火锚点日期和 sound_daily_viral_window 共用同一个计算函数, 保证两张
        # 表对同一个声音使用完全一致的爆火时间点.
        active_weeks_set = set(active_weeks)
        spike_weeks: set[date] = set()
        if remix["is_trending_monitored"]:
            spike_anchor = compute_spike_anchor_date(remix)
            spike_monday = most_recent_monday(spike_anchor)
            if remix["spike_week_alignment"] == "aligned":
                candidate_weeks = {spike_monday}
            else:
                candidate_weeks = {spike_monday, spike_monday + timedelta(weeks=1)}
            spike_weeks = candidate_weeks & active_weeks_set

        tier = creator_tier_by_id[remix["creator_id"]]
        quality_multiplier = CREATOR_TIER_QUALITY_MULTIPLIER[tier]
        alignment_multiplier = 1.0
        if remix["spike_week_alignment"] == "split_across_weeks":
            alignment_multiplier = SPLIT_WEEK_ALIGNMENT_PENALTY_MULTIPLIER

        baseline_weekly_views = 150.0 + remix["popularity_score"] * 3500.0

        for week in active_weeks:
            noise = random.uniform(0.7, 1.3)
            weekly_view_count = baseline_weekly_views * noise
            if week in spike_weeks:
                weekly_view_count *= random.uniform(*SPIKE_VIEW_MULTIPLIER_RANGE)
            weekly_view_count = max(50, round(weekly_view_count))
            weekly_video_count = max(1, round(weekly_view_count / (400.0 + remix["popularity_score"] * 100.0)))
            payout_usd = round(
                weekly_view_count / 1000.0
                * CREATOR_FUND_BASE_RATE_PER_1000_VIEWS
                * quality_multiplier
                * alignment_multiplier,
                2,
            )
            row = {
                "id": payout_id,
                "remix_sound_id": remix["id"],
                "creator_id": remix["creator_id"],
                "week_start_date": week,
                "weekly_video_count": weekly_video_count,
                "weekly_view_count": weekly_view_count,
                "snapshot_rank": 0,  # 下面按周单独计算排名后回填
                "payout_usd": payout_usd,
            }
            rows.append(row)
            week_view_accumulator[week].append(row)
            payout_id += 1

    for week, week_rows in week_view_accumulator.items():
        ranked = sorted(week_rows, key=lambda r: r["weekly_view_count"], reverse=True)
        for rank, row in enumerate(ranked, start=1):
            row["snapshot_rank"] = rank

    return pl.DataFrame(rows, infer_schema_length=None)


def gen_sound_daily_viral_window(sounds_df: pl.DataFrame) -> pl.DataFrame:
    """生成 120 个热门候选声音的每日播放明细, 让 aligned/split_across_weeks
    两类声音的爆火高峰在日历上分别落在一个自然周内, 或跨越两个自然周. 爆火
    锚点日期来自 `compute_spike_anchor_date`, 和 creator_fund_weekly_payout
    里同一个声音套用爆火倍数的自然周完全对应, 便于案例分析里逐日曲线和周度
    分账互相印证."""
    monitored = sounds_df.filter(pl.col("is_trending_monitored")).to_dicts()

    rows = []
    row_id = 1
    for s in monitored:
        spike_core_start = compute_spike_anchor_date(s)
        core_duration = random.randint(3, 4)
        window_start = spike_core_start - timedelta(days=DAILY_WINDOW_DAYS_BEFORE_SPIKE)
        window_end = spike_core_start + timedelta(days=DAILY_WINDOW_DAYS_AFTER_SPIKE)

        baseline_daily_views = 60.0 + s["popularity_score"] * 200.0
        current = window_start
        while current <= window_end:
            days_from_core = (current - spike_core_start).days
            if 0 <= days_from_core < core_duration:
                multiplier = random.uniform(*DAILY_SPIKE_CORE_MULTIPLIER_RANGE)
            elif days_from_core in (-1, core_duration) or days_from_core in (-2, core_duration + 1):
                multiplier = random.uniform(*DAILY_SHOULDER_MULTIPLIER_RANGE)
            else:
                multiplier = random.uniform(0.7, 1.3)
            daily_view_count = max(20, round(baseline_daily_views * multiplier))
            daily_video_count = max(1, round(daily_view_count / (350.0 + s["popularity_score"] * 80.0)))
            rows.append(
                {
                    "id": row_id,
                    "sound_id": s["id"],
                    "usage_date": current,
                    "daily_video_count": daily_video_count,
                    "daily_view_count": daily_view_count,
                }
            )
            row_id += 1
            current += timedelta(days=1)

    return pl.DataFrame(rows, infer_schema_length=None)


# ============================================================
# 第 7 节: TSV 生成编排
# ============================================================


def generate_all_tsv() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    df_label = gen_labels()
    df_label.write_csv(DATA_DIR / "01_label.tsv", separator="\t")

    df_creator = gen_creators()
    df_creator.write_csv(DATA_DIR / "02_creator.tsv", separator="\t")

    df_license = gen_label_blanket_licenses(df_label)
    df_license.write_csv(DATA_DIR / "03_label_blanket_license.tsv", separator="\t")

    df_sound = gen_sounds(df_label, df_creator)
    df_sound.write_csv(DATA_DIR / "04_sound.tsv", separator="\t")

    df_payment = gen_license_fee_payments(df_license)
    df_payment.write_csv(DATA_DIR / "05_license_fee_payment.tsv", separator="\t")

    df_monthly_usage = gen_sound_monthly_usage(df_sound, df_label, df_license)
    df_monthly_usage.write_csv(DATA_DIR / "06_sound_monthly_usage.tsv", separator="\t")

    df_conflict = gen_rights_conflict_flags(df_sound)
    df_conflict.write_csv(DATA_DIR / "07_rights_conflict_flag.tsv", separator="\t")

    df_payout = gen_creator_fund_weekly_payouts(df_sound, df_creator)
    df_payout.write_csv(DATA_DIR / "08_creator_fund_weekly_payout.tsv", separator="\t")

    df_daily = gen_sound_daily_viral_window(df_sound)
    df_daily.write_csv(DATA_DIR / "09_sound_daily_viral_window.tsv", separator="\t")

    print(f"Generated all TSV files in {DATA_DIR}")


# ============================================================
# 第 8 节: SQLite 数据库构建
# ============================================================


def create_sqlite_database() -> None:
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    # 拓扑加载顺序. 第一个元素是不带扩展名的 TSV 文件名;
    # 第二个元素是 SQLAlchemy Core Table 对象.
    load_order: list[tuple[str, "Table"]] = [
        ("01_label", Label.__table__),
        ("02_creator", Creator.__table__),
        ("03_label_blanket_license", LabelBlanketLicense.__table__),
        ("04_sound", Sound.__table__),
        ("05_license_fee_payment", LicenseFeePayment.__table__),
        ("06_sound_monthly_usage", SoundMonthlyUsage.__table__),
        ("07_rights_conflict_flag", RightsConflictFlag.__table__),
        ("08_creator_fund_weekly_payout", CreatorFundWeeklyPayout.__table__),
        ("09_sound_daily_viral_window", SoundDailyViralWindow.__table__),
    ]

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            df = pl.read_csv(
                DATA_DIR / f"{tsv_name}.tsv",
                separator="\t",
                try_parse_dates=True,
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
