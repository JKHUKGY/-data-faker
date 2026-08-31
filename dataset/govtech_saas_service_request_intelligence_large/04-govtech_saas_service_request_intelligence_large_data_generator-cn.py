"""
Govtech SaaS Service Request Intelligence 假数据生成器 (Large 复杂度)

业务背景:
CityPulse 是一家总部位于 Austin, TX 的 Govtech SaaS 公司, 给北美约 120 个中型城市/县提供
311 居民服务请求平台 (intake, 分类, 路由, SLA 跟踪, citizen portal)。本数据集模拟
平台 36 个月 (2023-06-01 到 2026-06-01) 的运营数据, 锚定 REFERENCE_DATE = 2026-06-01,
支持以下分析:

1. Trap 1 "Other" 分类漂移: 约 8% 的请求被分到 Other 类, 其中约 12% 的描述实际含强关键词
   (pothole / streetlight / graffiti / dumping / noise / tree), 这些请求被错路由到通用队列
   慢通道, SLA breach rate 约 32% 远高于专门队列的 23%。
2. Trap 2 严重度勾选与文本暗示偏离: stated_severity 为 Low/Med 的请求中约 10% 描述含
   紧急词 (gas leak / live wire / fire / smoke / child injured / leaking),
   这些请求 reopen rate 约 25% vs 基线约 5%。
3. Trap 3 首单速关掩盖重复: 24h 内关闭的"按时完成"请求中约 28% 同址 30 天内有另一条
   新请求, 而非速关请求约 20%。速关比非速关高约 8pp, 掩盖了真实"解决率"。
4. Trap 4 升级语预测投诉: 约 3% 的描述含升级词 (third time / fed up / contact my
   councilman / lawyer / going to the news), 这部分 60 天内生成 citizen_complaints
   记录的概率约 8%, 基线约 0.3%, lift 约 25 倍。
5. Trap 5 租户级模型精度差异: 10 个 vocab_drift_level='high' 的租户 (4 个 Quebec
   法语城市 + 6 个深南方俚语城市) classifier accuracy 约 72%, 其余 110 个租户中位数
   约 88%。高 drift 租户同时伴随约 +8pp 的 SLA breach rate。

上述陷阱通过有意设计的相关分布注入。对应的 SQL 查询位于
govtech_saas_service_request_intelligence_large_sql_queries-cn.md, 用以暴露这些陷阱。
"""

from __future__ import annotations

import random
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import numpy as np
import polars as pl
from faker import Faker

from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent
DATA_DIR = OUTPUT_DIR / "data"
DATABASE_PATH = OUTPUT_DIR / "govtech_saas_service_request_intelligence_large.sqlite"
FAKER_LOCALE = "en_US"
RANDOM_SEED = 42

# 固定参考日, 保证多次运行结果一致, 不依赖系统当前时间。
# SQL 查询里凡是需要"今天"的地方, 也使用同一个字面量日期。
REFERENCE_DATE = date(2026, 6, 1)
DATA_START_DATE = date(2023, 6, 1)
DATA_END_DATE = REFERENCE_DATE  # 不含, 数据时间窗口 = [start, end)

fake = Faker(FAKER_LOCALE)
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# 业务校准常量 (Business Calibration Constants)
# 每个数字都对应业务陷阱契约或行业惯例, WHY 注释解释来源。
# ---------------------------------------------------------------------------

# 量级
TOTAL_TENANTS = 120
TOTAL_CITIZENS = 500_000
TOTAL_ADDRESSES = 150_000
TOTAL_ASSETS = 80_000
TOTAL_STAFF = 25_000
TOTAL_CREWS = 2_500
TOTAL_SERVICE_REQUESTS = 1_000_000

# 城市规模 tier 由 TENANT_SEED 的真实人口经阈值判定 (large >= 400k, medium >= 150k,
# 其余 small), 不由固定配额驱动。按当前 seed 实际落点约为 large 17 / medium 74 / small 29。
# (注意: 文档 4.3 与 Q10 的城市规模口径以此实际落点为准, 不是 50/50/20。)
TENANT_SIZE_TIER_THRESHOLDS = {
    "large_min_population": 400_000,
    "medium_min_population": 150_000,
}

# vocab_drift_level 分布: high 约 10 个 (4 Quebec 法语 + 6 深南方俚语), medium 约 30 个,
# low 约 80 个。Trap 5 的核心是 high drift 这 10 个 tenant 的分类器准确率显著下降。
VOCAB_DRIFT_HIGH_COUNT = 10
VOCAB_DRIFT_MEDIUM_COUNT = 30
# 其余 80 个为 low

# 渠道权重 (跨 tenant 加权), 反映 2026 年现状: 数字渠道占主导, IVR 持续下降。
CHANNEL_WEIGHTS = {
    "web": 0.30,
    "mobile_app": 0.28,
    "ivr": 0.22,
    "social": 0.10,
    "email": 0.07,
    "walk_in": 0.03,
}

# 居民勾选的严重度分布。Low/Medium 占 75% 是 trap 2 的入口子集。
STATED_SEVERITY_WEIGHTS = {
    "low": 0.35,
    "medium": 0.40,
    "high": 0.20,
    "emergency": 0.05,
}

# 类别大类的请求分布。Other 占 8% 是 trap 1 的总池。Streets + Sanitation + Utilities
# 占近 2/3, 与北美 311 公开数据 (Boston, NYC, Chicago) 的类别分布粗略一致。
CATEGORY_GROUP_WEIGHTS = {
    "Streets": 0.25,
    "Sanitation": 0.22,
    "Utilities": 0.18,
    "Parks": 0.10,
    "Code": 0.08,
    "Animal": 0.05,
    "Noise": 0.04,
    "Other": 0.08,
}

# Trap 1: Other 类中"实际含强关键词"的子集占比 (即模型本可正确分类的"漏标")。
# 这个 12% 由 NLP 模型 confidence 阈值 (0.45) 与 fallback 逻辑共同造成。
OTHER_MISROUTE_WITHIN_OTHER = 0.12

# Trap 2: Low/Medium 严重度勾选中"描述含紧急词"的比例。
# 居民对自身情况严重度判断偏差源于"我不想被笑话过度反应"心理。
EMERGENCY_KW_WITHIN_LOW_MED = 0.10
EMERGENCY_KW_REOPEN_RATE = 0.25  # 这一子集的 reopen 率
BASELINE_REOPEN_RATE = 0.05

# Trap 3: 首单 24h 速关 + on_time 的请求中"同址 30 天复发"的比例。
# 现场 crew 的 first touch resolution KPI 驱动这个行为。
QUICK_CLOSE_RATE = 0.40  # 24h 内关闭占比
# 注入到"同址 30 天复发"的额外比例 (叠加 ~12% 的随机簇集基线后, 速关组实测约 28%、
# 非速关组约 20%, 速关比非速关高约 8pp, 即 trap 3 的可观察信号)。
QUICK_CLOSE_REPEAT_30D = 0.18
NORMAL_REPEAT_30D = 0.09

# Trap 4: 描述含升级语的子集占比, 以及其后 60 天内升级到 city council 的概率。
# 25 倍 lift 是这道题的核心论据, 用以说服 Product 给 intake 加文本扫描。
ESCALATION_KW_RATE = 0.03
ESCALATION_TO_COUNCIL_RATE = 0.08
BASELINE_TO_COUNCIL_RATE = 0.003

# Trap 5: classifier accuracy 目标值 (audited 子集口径)。
# 高 drift 10 个租户 ~0.72, 中位 (low drift) ~0.88, 全局 ~0.86。
# 注意: 这些是"目标 accuracy", 实际由下面 gen_model_predictions 的 error_rates 与
# will_be_other (88% 真值即 Other, 预测命中) 共同决定, 见该函数注释。
HIGH_DRIFT_ACCURACY = 0.72
MEDIUM_DRIFT_ACCURACY = 0.84
LOW_DRIFT_ACCURACY = 0.89

# 审计采样率: 约 20% 的请求会被人工 audit (填 ground_truth_category_id)。
# 行业惯例: 任何 ML 平台都需要持续 audit 子集来跟踪模型漂移。
AUDIT_SAMPLE_RATE = 0.20

# SLA 整体 breach rate 约 25%, Other 类 32%, 专门部门 23%。
BASELINE_SLA_BREACH_RATE = 0.23
OTHER_SLA_BREACH_RATE = 0.32

# Other auto_category 占总量 8%。这是 trap 1 的全局池大小。
OTHER_AUTO_CATEGORY_RATE = 0.08

# Quick close 中有附件率会更高 (现场到了之后拍照证据), 也是真实运营观察。
ATTACHMENT_RATE = 0.40

# Work order 生成率: 约 60% 请求会派工单, 信息咨询类不派单。
WORK_ORDER_RATE = 0.60

# 月度健康度快照覆盖月数 = 36
SNAPSHOT_MONTHS = 36

# AI Insight Pack 渗透率 (按 size_tier 分层): 大城几乎都买, 小城渗透低。
# 这支撑 Q10 "大城高渗透、小城低渗透" 的 CRO 叙事 (实测 large ~95% > small ~60%)。
AI_INSIGHT_PACK_PENETRATION_BY_TIER = {
    "large": 0.95,
    "medium": 0.80,
    "small": 0.60,
}

# ---------------------------------------------------------------------------
# 文本模板库
# 描述文本按 (true_category_group, has_emergency_kw, has_escalation_kw, is_ivr)
# 标签从下列短语桶中组合。SQL 用 LIKE 检索关键词时, 命中率与生成时的标签一致。
# ---------------------------------------------------------------------------

OPENING_PHRASES_WEB = [
    "Reporting a", "I would like to report a", "Hello, there is a",
    "Just noticed a", "Please look at this", "Need help with a",
    "Submitting a complaint about a", "Wanted to flag a", "Want to report a",
    "There is a", "Found a", "Came across a", "Spotted a",
    "Saw a", "Just saw a", "Concerned about a",
]

OPENING_PHRASES_IVR = [
    "uh yeah hi i'm calling about a", "uhm so there's a", "yeah so i wanted to report a",
    "hi there's a", "uh yes hi, i'm seeing a", "yeah, you know, there's a",
    "uh hello, i need to report a", "yeah so a",
]

# 每个 category_group 对应的核心描述短语 (含强关键词)。
# 关键词存在 SQL Q1, Q6, Q16 都会 LIKE 命中。
CORE_TEMPLATES_BY_GROUP = {
    "Streets": [
        "pothole on {street_token}, looks deep enough to damage a tire",
        "huge pothole near the intersection at {street_token}",
        "hole in road getting bigger every week on {street_token}",
        "pavement is cracking and lifting near {street_token}",
        "broken curb at {street_token}, tripping hazard",
        "missing stop sign at {street_token}",
        "faded crosswalk markings at {street_token}",
    ],
    "Sanitation": [
        "trash piled up at the corner of {street_token} for days",
        "illegal dumping behind the building at {street_token}",
        "garbage cans overflowing on {street_token}",
        "someone dumped a sofa and mattress at {street_token}",
        "missed garbage pickup at {street_token}",
        "rats are showing up because of trash at {street_token}",
        "dumped construction debris at {street_token}",
    ],
    "Utilities": [
        "streetlight out in front of {street_token}",
        "street light has been flickering for two weeks at {street_token}",
        "water main break flooding the road near {street_token}",
        "sewer cover broken at {street_token}",
        "manhole cover loose at {street_token}",
        "no power to traffic signal at {street_token}",
    ],
    "Parks": [
        "broken bench in the park near {street_token}",
        "playground equipment damaged at {street_token}",
        "tree limb hanging dangerously over sidewalk at {street_token}",
        "fallen tree blocking trail near {street_token}",
        "irrigation broken at park near {street_token}",
        "graffiti on the park sign at {street_token}",
    ],
    "Code": [
        "abandoned vehicle parked at {street_token} for months",
        "tall grass and weeds at vacant lot near {street_token}",
        "construction without permit at {street_token}",
        "junk accumulating in yard at {street_token}",
        "vacant building windows broken at {street_token}",
    ],
    "Animal": [
        "stray dog roaming around {street_token}",
        "dead animal on the road at {street_token}",
        "raccoon living in attic at {street_token}, need pickup",
        "loose dog barking aggressively near {street_token}",
    ],
    "Noise": [
        "loud noise complaint at {street_token}, ongoing for hours",
        "construction noise at {street_token} before 7 am",
        "loud party at {street_token} keeping neighbors awake",
        "noise complaint about car alarm at {street_token}",
    ],
    "Other": [
        "general inquiry about city services at {street_token}",
        "question about garbage pickup schedule",
        "asking for status on previous request",
        "not sure who to contact for this issue",
        "wanted to give feedback on city operations",
        "looking for information on how to apply for a permit",
    ],
}

# 紧急关键词桶, 仅在 has_emergency_kw=True 时附加到描述末尾。
EMERGENCY_PHRASES = [
    "I can smell a gas leak from the corner",
    "there is a live wire down on the ground",
    "I see smoke coming from the basement",
    "small fire was burning near the trash bins",
    "child injured because of the broken sidewalk",
    "kid hurt his ankle on the broken curb",
    "water is leaking everywhere out of the broken pipe",
    "leaking sewage onto the street",
]

# 升级语关键词桶, 仅在 has_escalation_kw=True 时附加。
ESCALATION_PHRASES = [
    "This is the third time this month I am reporting this",
    "I am fed up with how slow this gets fixed",
    "I will contact my councilman if this is not resolved",
    "going to the news with this if nothing changes",
    "my lawyer is preparing a letter if you do not respond",
    "third time this year, fed up",
    "fed up, going to council with this",
]

CLOSING_PHRASES = [
    "Please address as soon as possible.",
    "Thank you.",
    "Hope this gets fixed soon.",
    "Appreciate any update.",
    "Let me know when it is resolved.",
    "",  # 有些描述无结尾
]

STREET_TOKENS = [
    "Main St", "Brazos St", "Riverside Dr", "Oak Ave", "Pine Rd",
    "5th Ave", "Maple Blvd", "Lincoln Ave", "Park Ln", "Elm St",
    "Cedar St", "Washington St", "Jefferson Ave", "Market St", "Broadway",
    "rue Saint Jean", "rue Sainte Catherine", "boulevard Charest",
    "Bourbon St", "Magazine St", "Peachtree St",
]

# Quebec 法语化片段, 用于 has_french_vocab=1 的 tenant
FRENCH_FRAGMENTS = [
    "il y a un",  # there is a
    "merci de regarder",  # please look at it
    "très urgent",  # very urgent
    "depuis longtemps",  # for a long time
    "c'est dangereux",  # it's dangerous
]

# IVR 转写的口语噪声, 插入到描述中间
IVR_NOISE = ["uh", "you know", "uhm", "like", "yeah", "right"]

# work order 备注模板
WO_NOTE_TEMPLATES_BY_OUTCOME = {
    "resolved": [
        "Patched on site. Looks good.",
        "Replaced bulb. Confirmed working.",
        "Picked up debris and disposed of properly.",
        "Trimmed tree limb, cleared sidewalk.",
        "Removed graffiti, primed surface.",
        "Closed for KPI window. Long term fix still pending.",
        "Quick fix on the spot. Citizen happy.",
    ],
    "deferred": [
        "Need bigger crew for full repair. Deferred to next month.",
        "Waiting on materials, deferred 2 weeks.",
        "Deferred to capital project list.",
    ],
    "no_action": [
        "Could not reproduce issue on site.",
        "Did not find anything wrong.",
        "Cannot do anything until property owner contacted.",
    ],
    "unable_to_locate": [
        "Could not find address. May be incorrect.",
        "Address does not exist in our records.",
        "Unable to locate the asset described.",
    ],
}

# citizen complaint narrative templates
COMPLAINT_NARRATIVE_TEMPLATES = [
    "I have reported this issue {n_times} times since {start_month} and nothing has been done. "
    "Last response was a closed ticket marked resolved but the problem is still there. "
    "I am asking Council Member {council_name} to intervene because the 311 system clearly is not working for {street}.",
    "It is unacceptable that residents have to chase the city for basic services. I escalated to "
    "{escalation_channel} because all 311 attempts failed. {street} area has been ignored. "
    "Please fix this before someone gets hurt.",
    "Filing this formal complaint about repeated failure to address my {issue_type} report at {street}. "
    "Over the past {months_span} months I have made multiple requests with no resolution. "
    "Asking Council Member {council_name} to bring this up at the next meeting.",
]

# ---------------------------------------------------------------------------
# 静态字典数据
# ---------------------------------------------------------------------------

# 6 个渠道
INTAKE_CHANNELS_DATA = [
    (1, "web", "Web Portal", "high", 0.88),
    (2, "mobile_app", "Mobile App", "high", 0.86),
    (3, "ivr", "Phone IVR", "low", 0.72),
    (4, "social", "Social Media", "medium", 0.78),
    (5, "email", "Email", "medium", 0.84),
    (6, "walk_in", "Walk In", "medium", 0.85),
]

# 80 个类别 (含 1 个 Other)
SERVICE_CATEGORIES_SEED = [
    # (group, code, name, default_priority)
    # Streets (15)
    ("Streets", "pothole", "Pothole", "medium"),
    ("Streets", "road_damage", "Road Surface Damage", "medium"),
    ("Streets", "curb_repair", "Curb Repair", "low"),
    ("Streets", "sidewalk_repair", "Sidewalk Repair", "low"),
    ("Streets", "crosswalk_marking", "Crosswalk Marking Faded", "low"),
    ("Streets", "stop_sign_missing", "Stop Sign Missing", "high"),
    ("Streets", "street_sign_damaged", "Street Sign Damaged", "low"),
    ("Streets", "guardrail_damage", "Guardrail Damage", "medium"),
    ("Streets", "shoulder_erosion", "Shoulder Erosion", "low"),
    ("Streets", "ice_road_hazard", "Ice on Road", "high"),
    ("Streets", "snow_not_cleared", "Snow Not Cleared", "medium"),
    ("Streets", "bridge_damage", "Bridge Damage", "high"),
    ("Streets", "speed_bump_issue", "Speed Bump Issue", "low"),
    ("Streets", "lane_marking_faded", "Lane Marking Faded", "low"),
    ("Streets", "asphalt_lifting", "Asphalt Lifting", "medium"),
    # Sanitation (12)
    ("Sanitation", "trash_overflow", "Trash Bin Overflow", "low"),
    ("Sanitation", "illegal_dumping", "Illegal Dumping", "medium"),
    ("Sanitation", "missed_pickup", "Missed Garbage Pickup", "low"),
    ("Sanitation", "recycling_missed", "Recycling Missed", "low"),
    ("Sanitation", "bulk_pickup", "Bulk Item Pickup Request", "low"),
    ("Sanitation", "litter_in_park", "Litter in Park", "low"),
    ("Sanitation", "dead_animal_pickup", "Dead Animal Pickup", "medium"),
    ("Sanitation", "rats_infestation", "Rat Infestation", "medium"),
    ("Sanitation", "graffiti_removal", "Graffiti Removal", "low"),
    ("Sanitation", "broken_glass", "Broken Glass on Street", "medium"),
    ("Sanitation", "yard_waste", "Yard Waste Pickup", "low"),
    ("Sanitation", "hazmat_spill", "Hazmat Spill", "emergency"),
    # Utilities (12)
    ("Utilities", "streetlight_out", "Streetlight Out", "medium"),
    ("Utilities", "streetlight_flickering", "Streetlight Flickering", "low"),
    ("Utilities", "traffic_signal_out", "Traffic Signal Out", "high"),
    ("Utilities", "water_main_leak", "Water Main Leak", "high"),
    ("Utilities", "sewer_cover_broken", "Sewer Cover Broken", "medium"),
    ("Utilities", "manhole_loose", "Manhole Loose", "medium"),
    ("Utilities", "fire_hydrant_damage", "Fire Hydrant Damage", "high"),
    ("Utilities", "power_line_down", "Power Line Down", "emergency"),
    ("Utilities", "gas_leak_suspected", "Suspected Gas Leak", "emergency"),
    ("Utilities", "water_pressure_low", "Low Water Pressure", "low"),
    ("Utilities", "sewer_backup", "Sewer Backup", "high"),
    ("Utilities", "stormdrain_blocked", "Storm Drain Blocked", "medium"),
    # Parks (10)
    ("Parks", "broken_bench", "Broken Bench", "low"),
    ("Parks", "playground_damage", "Playground Equipment Damage", "medium"),
    ("Parks", "tree_limb_hanging", "Tree Limb Hanging", "medium"),
    ("Parks", "fallen_tree", "Fallen Tree", "high"),
    ("Parks", "irrigation_broken", "Irrigation Broken", "low"),
    ("Parks", "park_graffiti", "Park Graffiti", "low"),
    ("Parks", "trail_damage", "Trail Damage", "low"),
    ("Parks", "fence_damage", "Fence Damage", "low"),
    ("Parks", "fountain_broken", "Fountain Broken", "low"),
    ("Parks", "park_lighting", "Park Lighting Issue", "low"),
    # Code (8)
    ("Code", "abandoned_vehicle", "Abandoned Vehicle", "low"),
    ("Code", "tall_grass_weeds", "Tall Grass and Weeds", "low"),
    ("Code", "construction_no_permit", "Construction Without Permit", "medium"),
    ("Code", "junk_in_yard", "Junk in Yard", "low"),
    ("Code", "vacant_building", "Vacant Building Issue", "medium"),
    ("Code", "occupancy_violation", "Occupancy Violation", "medium"),
    ("Code", "zoning_violation", "Zoning Violation", "low"),
    ("Code", "fence_violation", "Fence Code Violation", "low"),
    # Animal (5)
    ("Animal", "stray_dog", "Stray Dog Roaming", "medium"),
    ("Animal", "loose_dog_aggressive", "Loose Dog Aggressive", "high"),
    ("Animal", "raccoon_pickup", "Raccoon Pickup Request", "low"),
    ("Animal", "feral_cats", "Feral Cat Colony", "low"),
    ("Animal", "wildlife_in_attic", "Wildlife in Attic", "low"),
    # Noise (4)
    ("Noise", "loud_party", "Loud Party Complaint", "low"),
    ("Noise", "construction_noise", "Construction Noise Early Hours", "low"),
    ("Noise", "car_alarm_persistent", "Persistent Car Alarm", "low"),
    ("Noise", "loud_music_business", "Loud Music from Business", "low"),
    # 共 66 个普通类
    # Other (1) - 兜底 (序号 80, is_other=1)
]

# 强关键词 (用于 Trap 1: Other 中含此关键词的请求被 LIKE 命中)
STRONG_KEYWORDS = [
    "pothole", "streetlight", "street light", "graffiti",
    "illegal dumping", "dumped", "noise", "tree limb", "fallen tree",
]

# Trap 1 专用: Other 类中"本可被正确分类"的 misroute 子集 (约占 Other 的 12%) 的描述,
# 保证恰好命中 6 个强关键词概念之一 (pothole / streetlight / graffiti / illegal dumping /
# noise / tree limb)。顺序与 gen_service_requests 里 strong_cat_ids 一一对应, 这样
# Q1 / Q16 的 LIKE 命中率 = OTHER_MISROUTE_WITHIN_OTHER, 不再被随机模板稀释或抬高。
STRONG_KW_PHRASES = [
    "large pothole on {street_token}, deep enough to wreck a tire",
    "streetlight out in front of {street_token}, totally dark at night",
    "graffiti sprayed across the wall at {street_token}",
    "illegal dumping of trash and an old couch at {street_token}",
    "loud noise complaint at {street_token}, neighbors cannot sleep",
    "tree limb hanging dangerously over the sidewalk at {street_token}",
]

# 紧急关键词 (用于 Trap 2)
EMERGENCY_KEYWORDS = [
    "gas leak", "live wire", "fire", "smoke",
    "child injured", "kid hurt", "leaking",
]

# 升级关键词 (用于 Trap 4)
ESCALATION_KEYWORDS = [
    "third time", "fed up", "contact my councilman",
    "going to the news", "get a lawyer", "my lawyer",
]

# 高 vocab drift 的 tenant codes (4 Quebec + 6 deep south)
HIGH_DRIFT_TENANT_CODES = [
    "montreal_qc", "quebec_qc", "laval_qc", "sherbrooke_qc",
    "new_orleans_la", "mobile_al", "birmingham_al",
    "jackson_ms", "shreveport_la", "baton_rouge_la",
]

# 城市种子: (tenant_code, name, state, country, population, has_french)
TENANT_SEED = [
    # Large (20 个, 人口 40w to 80w)
    ("austin_tx", "City of Austin", "TX", "US", 980000, 0),
    ("mesa_az", "City of Mesa", "AZ", "US", 510000, 0),
    ("kansas_city_mo", "City of Kansas City", "MO", "US", 510000, 0),
    ("colorado_springs_co", "City of Colorado Springs", "CO", "US", 480000, 0),
    ("raleigh_nc", "City of Raleigh", "NC", "US", 470000, 0),
    ("omaha_ne", "City of Omaha", "NE", "US", 490000, 0),
    ("oakland_ca", "City of Oakland", "CA", "US", 440000, 0),
    ("minneapolis_mn", "City of Minneapolis", "MN", "US", 430000, 0),
    ("tulsa_ok", "City of Tulsa", "OK", "US", 410000, 0),
    ("arlington_tx", "City of Arlington", "TX", "US", 400000, 0),
    ("new_orleans_la", "City of New Orleans", "LA", "US", 390000, 0),
    ("wichita_ks", "City of Wichita", "KS", "US", 400000, 0),
    ("cleveland_oh", "City of Cleveland", "OH", "US", 380000, 0),
    ("tampa_fl", "City of Tampa", "FL", "US", 400000, 0),
    ("bakersfield_ca", "City of Bakersfield", "CA", "US", 410000, 0),
    ("honolulu_hi", "City of Honolulu", "HI", "US", 350000, 0),
    ("anaheim_ca", "City of Anaheim", "CA", "US", 350000, 0),
    ("quebec_qc", "Ville de Québec", "QC", "CA", 540000, 1),
    ("hamilton_on", "City of Hamilton", "ON", "CA", 580000, 0),
    ("winnipeg_mb", "City of Winnipeg", "MB", "CA", 750000, 0),
    # Medium (50 个, 人口 15w to 40w)
    ("plano_tx", "City of Plano", "TX", "US", 290000, 0),
    ("orlando_fl", "City of Orlando", "FL", "US", 310000, 0),
    ("st_paul_mn", "City of Saint Paul", "MN", "US", 310000, 0),
    ("cincinnati_oh", "City of Cincinnati", "OH", "US", 310000, 0),
    ("anchorage_ak", "City of Anchorage", "AK", "US", 290000, 0),
    ("greensboro_nc", "City of Greensboro", "NC", "US", 300000, 0),
    ("toledo_oh", "City of Toledo", "OH", "US", 270000, 0),
    ("durham_nc", "City of Durham", "NC", "US", 280000, 0),
    ("madison_wi", "City of Madison", "WI", "US", 270000, 0),
    ("lubbock_tx", "City of Lubbock", "TX", "US", 260000, 0),
    ("buffalo_ny", "City of Buffalo", "NY", "US", 280000, 0),
    ("chesapeake_va", "City of Chesapeake", "VA", "US", 250000, 0),
    ("garland_tx", "City of Garland", "TX", "US", 240000, 0),
    ("gilbert_az", "Town of Gilbert", "AZ", "US", 270000, 0),
    ("baton_rouge_la", "City of Baton Rouge", "LA", "US", 220000, 0),
    ("irving_tx", "City of Irving", "TX", "US", 240000, 0),
    ("scottsdale_az", "City of Scottsdale", "AZ", "US", 260000, 0),
    ("north_las_vegas_nv", "City of North Las Vegas", "NV", "US", 270000, 0),
    ("fremont_ca", "City of Fremont", "CA", "US", 230000, 0),
    ("birmingham_al", "City of Birmingham", "AL", "US", 200000, 0),
    ("rochester_ny", "City of Rochester", "NY", "US", 210000, 0),
    ("richmond_va", "City of Richmond", "VA", "US", 230000, 0),
    ("boise_id", "City of Boise", "ID", "US", 240000, 0),
    ("des_moines_ia", "City of Des Moines", "IA", "US", 210000, 0),
    ("spokane_wa", "City of Spokane", "WA", "US", 230000, 0),
    ("modesto_ca", "City of Modesto", "CA", "US", 220000, 0),
    ("fontana_ca", "City of Fontana", "CA", "US", 210000, 0),
    ("akron_oh", "City of Akron", "OH", "US", 190000, 0),
    ("tacoma_wa", "City of Tacoma", "WA", "US", 220000, 0),
    ("aurora_co", "City of Aurora", "CO", "US", 390000, 0),
    ("st_petersburg_fl", "City of Saint Petersburg", "FL", "US", 260000, 0),
    ("jersey_city_nj", "City of Jersey City", "NJ", "US", 290000, 0),
    ("chula_vista_ca", "City of Chula Vista", "CA", "US", 280000, 0),
    ("laredo_tx", "City of Laredo", "TX", "US", 260000, 0),
    ("henderson_nv", "City of Henderson", "NV", "US", 320000, 0),
    ("st_louis_mo", "City of Saint Louis", "MO", "US", 300000, 0),
    ("norfolk_va", "City of Norfolk", "VA", "US", 240000, 0),
    ("reno_nv", "City of Reno", "NV", "US", 270000, 0),
    ("riverside_ca", "City of Riverside", "CA", "US", 320000, 0),
    ("santa_ana_ca", "City of Santa Ana", "CA", "US", 320000, 0),
    ("corpus_christi_tx", "City of Corpus Christi", "TX", "US", 320000, 0),
    ("lexington_ky", "City of Lexington", "KY", "US", 320000, 0),
    ("stockton_ca", "City of Stockton", "CA", "US", 320000, 0),
    ("anaheim_orange_ca", "City of Anaheim Orange Co", "CA", "US", 350000, 0),
    ("oklahoma_city_ok", "City of Oklahoma City", "OK", "US", 380000, 0),
    ("nashville_tn", "Nashville Metro", "TN", "US", 380000, 0),
    ("mobile_al", "City of Mobile", "AL", "US", 180000, 0),
    ("shreveport_la", "City of Shreveport", "LA", "US", 180000, 0),
    ("jackson_ms", "City of Jackson", "MS", "US", 150000, 0),
    ("montreal_qc", "Ville de Montréal", "QC", "CA", 350000, 1),
    # Small (50 个, 人口 5w to 15w)
    ("burlington_vt", "City of Burlington", "VT", "US", 44000, 0),
    ("portland_me", "City of Portland", "ME", "US", 68000, 0),
    ("savannah_ga", "City of Savannah", "GA", "US", 145000, 0),
    ("ann_arbor_mi", "City of Ann Arbor", "MI", "US", 120000, 0),
    ("syracuse_ny", "City of Syracuse", "NY", "US", 145000, 0),
    ("hartford_ct", "City of Hartford", "CT", "US", 120000, 0),
    ("worcester_ma", "City of Worcester", "MA", "US", 150000, 0),
    ("springfield_il", "City of Springfield", "IL", "US", 115000, 0),
    ("dayton_oh", "City of Dayton", "OH", "US", 140000, 0),
    ("salem_or", "City of Salem", "OR", "US", 170000, 0),
    ("eugene_or", "City of Eugene", "OR", "US", 175000, 0),
    ("tallahassee_fl", "City of Tallahassee", "FL", "US", 200000, 0),
    ("fort_collins_co", "City of Fort Collins", "CO", "US", 170000, 0),
    ("naperville_il", "City of Naperville", "IL", "US", 150000, 0),
    ("yonkers_ny", "City of Yonkers", "NY", "US", 210000, 0),
    ("hayward_ca", "City of Hayward", "CA", "US", 160000, 0),
    ("lancaster_ca", "City of Lancaster", "CA", "US", 170000, 0),
    ("salinas_ca", "City of Salinas", "CA", "US", 160000, 0),
    ("provo_ut", "City of Provo", "UT", "US", 120000, 0),
    ("davenport_ia", "City of Davenport", "IA", "US", 100000, 0),
    ("topeka_ks", "City of Topeka", "KS", "US", 125000, 0),
    ("evansville_in", "City of Evansville", "IN", "US", 118000, 0),
    ("erie_pa", "City of Erie", "PA", "US", 95000, 0),
    ("kalamazoo_mi", "City of Kalamazoo", "MI", "US", 75000, 0),
    ("lansing_mi", "City of Lansing", "MI", "US", 115000, 0),
    ("rockford_il", "City of Rockford", "IL", "US", 150000, 0),
    ("knoxville_tn", "City of Knoxville", "TN", "US", 190000, 0),
    ("chattanooga_tn", "City of Chattanooga", "TN", "US", 180000, 0),
    ("columbia_sc", "City of Columbia", "SC", "US", 138000, 0),
    ("charleston_sc", "City of Charleston", "SC", "US", 150000, 0),
    ("little_rock_ar", "City of Little Rock", "AR", "US", 200000, 0),
    ("fayetteville_nc", "City of Fayetteville", "NC", "US", 210000, 0),
    ("athens_ga", "Athens Clarke", "GA", "US", 125000, 0),
    ("springfield_mo", "City of Springfield", "MO", "US", 170000, 0),
    ("salem_ma", "City of Salem", "MA", "US", 44000, 0),
    ("pasadena_ca", "City of Pasadena", "CA", "US", 140000, 0),
    ("cambridge_ma", "City of Cambridge", "MA", "US", 120000, 0),
    ("denton_tx", "City of Denton", "TX", "US", 150000, 0),
    ("midland_tx", "City of Midland", "TX", "US", 140000, 0),
    ("waco_tx", "City of Waco", "TX", "US", 140000, 0),
    ("flint_mi", "City of Flint", "MI", "US", 80000, 0),
    ("warwick_ri", "City of Warwick", "RI", "US", 82000, 0),
    ("clearwater_fl", "City of Clearwater", "FL", "US", 117000, 0),
    ("lakewood_co", "City of Lakewood", "CO", "US", 155000, 0),
    ("vallejo_ca", "City of Vallejo", "CA", "US", 122000, 0),
    ("santa_clara_ca", "City of Santa Clara", "CA", "US", 130000, 0),
    ("sterling_heights_mi", "City of Sterling Heights", "MI", "US", 135000, 0),
    ("laval_qc", "Ville de Laval", "QC", "CA", 440000, 1),
    ("sherbrooke_qc", "Ville de Sherbrooke", "QC", "CA", 170000, 1),
    ("kingston_on", "City of Kingston", "ON", "CA", 137000, 0),
]
assert len(TENANT_SEED) == 120, f"Expected 120 tenants, got {len(TENANT_SEED)}"

# 部门类型种子: 每个 tenant 创建 12 个部门, 含 1 个 general_queue
DEPT_TYPES_PER_TENANT = [
    ("STREETS", "Public Works Streets", "streets", 0),
    ("SAN", "Sanitation", "sanitation", 0),
    ("PARKS", "Parks and Recreation", "parks", 0),
    ("CODE", "Code Enforcement", "code_enforcement", 0),
    ("UTIL", "Utilities", "utilities", 0),
    ("ANIMAL", "Animal Services", "animal_services", 0),
    ("NOISE", "Noise Control", "noise_control", 0),
    ("TRANS", "Transportation", "transportation", 0),
    ("WATER", "Water Department", "water", 0),
    ("ENV", "Environmental Services", "other", 0),
    ("FAC", "Facilities Management", "other", 0),
    ("GEN_311", "311 Central Queue", "general_queue", 1),
]


# ---------------------------------------------------------------------------
# ORM 模型 (SQLAlchemy 2.0 风格)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class IntakeChannel(Base):
    """居民提交渠道枚举表, 6 行, 跨租户共享。"""

    __tablename__ = "intake_channels"

    channel_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    text_quality_band: Mapped[str] = mapped_column(String(20), nullable=False)
    typical_severity_accuracy: Mapped[float] = mapped_column(Float, nullable=False)


class ServiceCategory(Base):
    """请求类别字典, 67 行 (66 个普通类 + 1 个 is_other=1 兜底类, 兜底类 category_id=80 非连续)。"""

    __tablename__ = "service_categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    category_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_group: Mapped[str] = mapped_column(String(50), nullable=False)
    default_priority: Mapped[str] = mapped_column(String(20), nullable=False)
    is_other: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Tenant(Base):
    """CityPulse 客户城市/县, 120 行。"""

    __tablename__ = "tenants"

    tenant_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    tenant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    state_or_province: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    size_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    vocab_drift_level: Mapped[str] = mapped_column(String(20), nullable=False)
    has_french_vocab: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    launched_on: Mapped[date] = mapped_column(Date, nullable=False)


class TenantSubscription(Base):
    """每个 tenant 的当期合同, 120 行。"""

    __tablename__ = "tenant_subscriptions"

    subscription_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    arr_usd: Mapped[float] = mapped_column(Float, nullable=False)
    has_ai_insight_pack: Mapped[int] = mapped_column(Integer, nullable=False)
    has_field_mobile_pack: Mapped[int] = mapped_column(Integer, nullable=False)
    has_analytics_pack: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False)


class Department(Base):
    """各 tenant 的部门, ~1500 行。"""

    __tablename__ = "departments"

    dept_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    dept_code: Mapped[str] = mapped_column(String(80), nullable=False)
    dept_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dept_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_general_queue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SLAPolicy(Base):
    """每个 (tenant, category) 的 SLA 政策, ~10000 行。"""

    __tablename__ = "sla_policies"

    sla_policy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("service_categories.category_id"), nullable=False)
    target_business_days: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_business_days: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)


class CategoryDeptRouting(Base):
    """每个 (tenant, category) 的部门路由, ~10000 行。"""

    __tablename__ = "category_dept_routing"

    routing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("service_categories.category_id"), nullable=False)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.dept_id"), nullable=False)
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)


class Citizen(Base):
    """居民账户, ~50 万行。"""

    __tablename__ = "citizens"

    citizen_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    citizen_external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    registered_on: Mapped[date] = mapped_column(Date, nullable=False)
    preferred_channel_id: Mapped[int | None] = mapped_column(ForeignKey("intake_channels.channel_id"))


class Address(Base):
    """已知地址, ~15 万行。"""

    __tablename__ = "addresses"

    address_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    street_address: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state_or_province: Mapped[str] = mapped_column(String(10), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(String(100))


class Asset(Base):
    """物理资产, ~8 万行。"""

    __tablename__ = "assets"

    asset_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.address_id"))
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    installed_on: Mapped[date | None] = mapped_column(Date)


class StaffUser(Base):
    """市政员工, ~2.5 万行。"""

    __tablename__ = "staff_users"

    staff_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.dept_id"), nullable=False)
    staff_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    hired_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class FieldCrew(Base):
    """现场班组, ~2500 行。"""

    __tablename__ = "field_crews"

    crew_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.dept_id"), nullable=False)
    crew_code: Mapped[str] = mapped_column(String(80), nullable=False)
    crew_size: Mapped[int] = mapped_column(Integer, nullable=False)
    shift_type: Mapped[str] = mapped_column(String(20), nullable=False)


class ServiceRequest(Base):
    """平台核心事实表, 100 万行。"""

    __tablename__ = "service_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    citizen_id: Mapped[int | None] = mapped_column(ForeignKey("citizens.citizen_id"))
    address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.address_id"))
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.asset_id"))
    auto_category_id: Mapped[int] = mapped_column(
        ForeignKey("service_categories.category_id"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(ForeignKey("intake_channels.channel_id"), nullable=False)
    routed_dept_id: Mapped[int | None] = mapped_column(ForeignKey("departments.dept_id"))
    stated_severity: Mapped[str] = mapped_column(String(20), nullable=False)
    current_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_of_request_id: Mapped[int | None] = mapped_column(ForeignKey("service_requests.request_id"))

    __table_args__ = (
        Index("idx_sr_tenant_created", "tenant_id", "created_at"),
        Index("idx_sr_address_created", "address_id", "created_at"),
        Index("idx_sr_auto_category", "auto_category_id"),
        Index("idx_sr_current_status", "current_status"),
    )


class RequestDescription(Base):
    """请求描述文本 (1:1 with service_requests), 100 万行。"""

    __tablename__ = "request_descriptions"

    description_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.request_id"), nullable=False, unique=True
    )
    description_text: Mapped[str] = mapped_column(String, nullable=False)
    description_length: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_via_text_field: Mapped[int] = mapped_column(Integer, nullable=False)


class RequestEvent(Base):
    """请求生命周期事件, ~400 万行。"""

    __tablename__ = "request_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.request_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.staff_id"))
    event_note: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("idx_re_request_at", "request_id", "event_at"),
    )


class RequestAssignment(Base):
    """请求指派记录, ~120 万行。"""

    __tablename__ = "request_assignments"

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.request_id"), nullable=False)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.dept_id"), nullable=False)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.staff_id"))
    crew_id: Mapped[int | None] = mapped_column(ForeignKey("field_crews.crew_id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_current: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RequestAttachment(Base):
    """附件元数据, ~40 万行。"""

    __tablename__ = "request_attachments"

    attachment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.request_id"), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkOrder(Base):
    """工单, ~60 万行。"""

    __tablename__ = "work_orders"

    work_order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.request_id"), nullable=False)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.dept_id"), nullable=False)
    crew_id: Mapped[int | None] = mapped_column(ForeignKey("field_crews.crew_id"))
    supervisor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.staff_id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    outcome: Mapped[str | None] = mapped_column(String(50))
    structured_fail_code: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        Index("idx_wo_request", "request_id"),
    )


class WorkOrderNote(Base):
    """工单备注, ~100 万行。"""

    __tablename__ = "work_order_notes"

    note_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.work_order_id"), nullable=False)
    by_staff_id: Mapped[int] = mapped_column(ForeignKey("staff_users.staff_id"), nullable=False)
    note_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    note_text: Mapped[str] = mapped_column(String, nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), nullable=False)


class ModelPrediction(Base):
    """NLP 分类器预测记录 (1:1 with service_requests), 100 万行。"""

    __tablename__ = "model_predictions"

    prediction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.request_id"), nullable=False, unique=True
    )
    predicted_category_id: Mapped[int] = mapped_column(
        ForeignKey("service_categories.category_id"), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ground_truth_category_id: Mapped[int | None] = mapped_column(ForeignKey("service_categories.category_id"))
    is_audited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)


class SLABreachLog(Base):
    """SLA 超时记录 (仅 breached 请求), ~25 万行。"""

    __tablename__ = "sla_breach_log"

    breach_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.request_id"), nullable=False, unique=True
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    breached_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    target_business_days: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_business_days: Mapped[int] = mapped_column(Integer, nullable=False)
    breach_business_days: Mapped[int] = mapped_column(Integer, nullable=False)
    breach_severity: Mapped[str] = mapped_column(String(20), nullable=False)


class CitizenComplaint(Base):
    """正式投诉, ~5000 行。"""

    __tablename__ = "citizen_complaints"

    complaint_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("citizens.citizen_id"), nullable=False)
    primary_request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.request_id"), nullable=False
    )
    filed_at: Mapped[date] = mapped_column(Date, nullable=False)
    escalation_channel: Mapped[str] = mapped_column(String(50), nullable=False)
    complaint_narrative: Mapped[str] = mapped_column(String, nullable=False)
    council_member_name: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[date | None] = mapped_column(Date)
    resolution_type: Mapped[str | None] = mapped_column(String(50))


class TenantHealthSnapshot(Base):
    """月度租户健康度快照, ~4320 行 (120 tenants × 36 months)。"""

    __tablename__ = "tenant_health_snapshots"

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False)
    reopen_rate: Mapped[float] = mapped_column(Float, nullable=False)
    repeat_at_address_rate: Mapped[float] = mapped_column(Float, nullable=False)
    classifier_accuracy: Mapped[float | None] = mapped_column(Float)
    council_escalation_rate: Mapped[float] = mapped_column(Float, nullable=False)
    nps_score: Mapped[int] = mapped_column(Integer, nullable=False)
    churn_risk_band: Mapped[str] = mapped_column(String(20), nullable=False)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def weighted_choice_indices(weights: list[float], n: int, rng: np.random.Generator) -> np.ndarray:
    """从给定权重数组按多项分布抽 n 次 (返回索引数组), 内部用 numpy 加速。"""
    probs = np.array(weights, dtype=np.float64)
    probs = probs / probs.sum()
    return rng.choice(len(probs), size=n, p=probs)


def random_dates_in_range(start: date, end: date, n: int, rng: np.random.Generator) -> np.ndarray:
    """在 [start, end) 内均匀采样 n 个日期 (返回 date 对象数组)。"""
    span_days = (end - start).days
    offsets = rng.integers(0, span_days, size=n)
    return np.array([start + timedelta(days=int(o)) for o in offsets])


def random_datetimes_in_range(start: date, end: date, n: int, rng: np.random.Generator) -> list[datetime]:
    """在 [start, end) 内均匀采样 n 个 datetime, 带 weekday + hour 模式。
    周一周二请求高, 周日低; 早 8 到晚 8 高, 凌晨低。"""
    span_seconds = int((end - start).total_seconds())
    offsets = rng.integers(0, span_seconds, size=n)
    return [datetime.combine(start, datetime.min.time()) + timedelta(seconds=int(o)) for o in offsets]


# ---------------------------------------------------------------------------
# 生成函数 (按拓扑顺序)
# ---------------------------------------------------------------------------


def gen_intake_channels() -> pl.DataFrame:
    """6 个固定渠道。"""
    rows = []
    for ch_id, code, name, qb, sev_acc in INTAKE_CHANNELS_DATA:
        rows.append(
            {
                "channel_id": ch_id,
                "channel_code": code,
                "channel_name": name,
                "text_quality_band": qb,
                "typical_severity_accuracy": sev_acc,
            }
        )
    return pl.DataFrame(rows)


def gen_service_categories() -> pl.DataFrame:
    """67 个类别 (66 普通 + 1 兜底 Other); 兜底 Other 固定 category_id=80。"""
    rows = []
    for idx, (grp, code, name, pri) in enumerate(SERVICE_CATEGORIES_SEED, start=1):
        rows.append(
            {
                "category_id": idx,
                "category_code": code,
                "category_name": name,
                "category_group": grp,
                "default_priority": pri,
                "is_other": 0,
            }
        )
    # 兜底 Other 固定 category_id=80 (序号留位, 不连续), is_other=1
    rows.append(
        {
            "category_id": 80,
            "category_code": "other_uncategorized",
            "category_name": "Other / Uncategorized",
            "category_group": "Other",
            "default_priority": "low",
            "is_other": 1,
        }
    )
    return pl.DataFrame(rows)


def gen_tenants() -> pl.DataFrame:
    """120 个客户城市, 含 vocab_drift_level 与 has_french_vocab 标签。"""
    rows = []
    tz_map = {"TX": "America/Chicago", "AZ": "America/Phoenix", "MO": "America/Chicago",
              "CO": "America/Denver", "NC": "America/New_York", "NE": "America/Chicago",
              "CA": "America/Los_Angeles", "MN": "America/Chicago", "OK": "America/Chicago",
              "LA": "America/Chicago", "KS": "America/Chicago", "OH": "America/New_York",
              "FL": "America/New_York", "HI": "Pacific/Honolulu", "QC": "America/Toronto",
              "ON": "America/Toronto", "MB": "America/Winnipeg", "AL": "America/Chicago",
              "MS": "America/Chicago", "AK": "America/Anchorage", "WI": "America/Chicago",
              "NY": "America/New_York", "VA": "America/New_York", "ID": "America/Boise",
              "IA": "America/Chicago", "WA": "America/Los_Angeles", "PA": "America/New_York",
              "MI": "America/Detroit", "KY": "America/New_York", "RI": "America/New_York",
              "IL": "America/Chicago", "ME": "America/New_York", "GA": "America/New_York",
              "MA": "America/New_York", "CT": "America/New_York", "VT": "America/New_York",
              "AR": "America/Chicago", "SC": "America/New_York", "OR": "America/Los_Angeles",
              "NV": "America/Los_Angeles", "TN": "America/Chicago", "IN": "America/New_York",
              "UT": "America/Denver", "NJ": "America/New_York"}
    for tenant_id, (code, name, state, country, pop, has_fr) in enumerate(TENANT_SEED, start=1):
        if pop >= 400_000:
            size_tier = "large"
        elif pop >= 150_000:
            size_tier = "medium"
        else:
            size_tier = "small"
        if code in HIGH_DRIFT_TENANT_CODES:
            drift = "high"
        elif size_tier == "large" or has_fr == 1:
            # large city tendency to medium drift due to dialect diversity
            drift = "medium" if random.random() < 0.5 else "low"
        else:
            drift = "medium" if random.random() < 0.15 else "low"
        tz = tz_map.get(state, "America/New_York")
        launch_days_before = random.randint(180, 2500)
        launched = REFERENCE_DATE - timedelta(days=launch_days_before)
        rows.append(
            {
                "tenant_id": tenant_id,
                "tenant_code": code,
                "tenant_name": name,
                "state_or_province": state,
                "country": country,
                "population": pop,
                "size_tier": size_tier,
                "timezone": tz,
                "vocab_drift_level": drift,
                "has_french_vocab": has_fr,
                "launched_on": launched,
            }
        )
    return pl.DataFrame(rows)


def gen_tenant_subscriptions(df_tenants: pl.DataFrame) -> pl.DataFrame:
    """每个 tenant 一条 active 合同, ARR 按 size_tier 估算。"""
    rows = []
    sub_id = 1
    for r in df_tenants.iter_rows(named=True):
        tier = r["size_tier"]
        if tier == "large":
            arr = random.uniform(600_000, 1_200_000)
        elif tier == "medium":
            arr = random.uniform(250_000, 600_000)
        else:
            arr = random.uniform(120_000, 250_000)
        # AI Insight Pack 按 size_tier 分层渗透 (large ~95% > medium ~80% > small ~60%)
        ai_pen = AI_INSIGHT_PACK_PENETRATION_BY_TIER[tier]
        has_ai = 1 if random.random() < ai_pen else 0
        has_field = 1 if random.random() < 0.75 else 0
        has_analytics = 1 if random.random() < 0.65 else 0
        # 合同期: 当前正在使用的 12 或 36 个月合同
        contract_len = random.choice([365, 365, 365 * 3])
        contract_start = REFERENCE_DATE - timedelta(days=random.randint(30, contract_len - 30))
        contract_end = contract_start + timedelta(days=contract_len)
        rows.append(
            {
                "subscription_id": sub_id,
                "tenant_id": r["tenant_id"],
                "contract_start_date": contract_start,
                "contract_end_date": contract_end,
                "arr_usd": round(arr, 2),
                "has_ai_insight_pack": has_ai,
                "has_field_mobile_pack": has_field,
                "has_analytics_pack": has_analytics,
                "is_active": 1,
            }
        )
        sub_id += 1
    return pl.DataFrame(rows)


def gen_departments(df_tenants: pl.DataFrame) -> pl.DataFrame:
    """每个 tenant 12 个部门, 含 1 个 general_queue。"""
    rows = []
    dept_id = 1
    for r in df_tenants.iter_rows(named=True):
        for code_suffix, name_base, dept_type, is_gen in DEPT_TYPES_PER_TENANT:
            dept_code = f"{code_suffix}_{r['tenant_code'].upper()}"
            dept_name = f"{name_base} ({r['tenant_name']})"
            rows.append(
                {
                    "dept_id": dept_id,
                    "tenant_id": r["tenant_id"],
                    "dept_code": dept_code,
                    "dept_name": dept_name,
                    "dept_type": dept_type,
                    "is_general_queue": is_gen,
                }
            )
            dept_id += 1
    return pl.DataFrame(rows)


def gen_sla_policies(df_tenants: pl.DataFrame, df_categories: pl.DataFrame) -> pl.DataFrame:
    """每个 (tenant, category) 一条 SLA 政策。"""
    rows = []
    sla_id = 1
    # 按 category 的典型 SLA target
    sla_target_by_priority = {"emergency": 1, "high": 2, "medium": 3, "low": 5}
    tenant_rows = df_tenants.to_dicts()
    cat_rows = df_categories.to_dicts()
    for t in tenant_rows:
        for c in cat_rows:
            base_target = sla_target_by_priority.get(c["default_priority"], 5)
            # 部分 tenant 设得更紧或更松 (+/- 1 天)
            jitter = random.choice([-1, 0, 0, 0, 1])
            target = max(1, base_target + jitter)
            escalation = target + random.randint(2, 5)
            rows.append(
                {
                    "sla_policy_id": sla_id,
                    "tenant_id": t["tenant_id"],
                    "category_id": c["category_id"],
                    "target_business_days": target,
                    "escalation_business_days": escalation,
                    "effective_from": t["launched_on"],
                }
            )
            sla_id += 1
    return pl.DataFrame(rows)


def gen_category_dept_routing(
    df_tenants: pl.DataFrame,
    df_categories: pl.DataFrame,
    df_departments: pl.DataFrame,
) -> pl.DataFrame:
    """每个 (tenant, category) 路由到一个部门。Other 类必须路由到 general_queue。"""
    # 按 category_group 决定路由到哪类 dept_type
    routing_map = {
        "Streets": "streets",
        "Sanitation": "sanitation",
        "Utilities": "utilities",
        "Parks": "parks",
        "Code": "code_enforcement",
        "Animal": "animal_services",
        "Noise": "noise_control",
        "Other": "general_queue",
    }
    # 按 tenant_id 分组的 dept 字典: {tenant_id: {dept_type: dept_id}}
    tenant_dept_lookup: dict[int, dict[str, int]] = {}
    for d in df_departments.iter_rows(named=True):
        tenant_dept_lookup.setdefault(d["tenant_id"], {})[d["dept_type"]] = d["dept_id"]

    rows = []
    routing_id = 1
    for t in df_tenants.iter_rows(named=True):
        dept_lookup = tenant_dept_lookup[t["tenant_id"]]
        for c in df_categories.iter_rows(named=True):
            target_dept_type = routing_map.get(c["category_group"], "general_queue")
            dept_id = dept_lookup.get(target_dept_type) or dept_lookup["general_queue"]
            rows.append(
                {
                    "routing_id": routing_id,
                    "tenant_id": t["tenant_id"],
                    "category_id": c["category_id"],
                    "dept_id": dept_id,
                    "is_primary": 1,
                    "effective_from": t["launched_on"],
                }
            )
            routing_id += 1
    return pl.DataFrame(rows)


def gen_citizens(df_tenants: pl.DataFrame) -> pl.DataFrame:
    """约 50 万居民, 按 tenant 人口分配。"""
    total = TOTAL_CITIZENS
    # 按 population 加权分配每 tenant 的居民数
    pops = df_tenants["population"].to_numpy()
    pop_share = pops / pops.sum()
    per_tenant = np.maximum(50, np.round(pop_share * total).astype(int))
    actual_total = int(per_tenant.sum())

    rows = []
    citizen_id = 1
    tenant_rows = df_tenants.to_dicts()
    # 用 batch 加速
    fr_fake = Faker("fr_CA")
    Faker.seed(RANDOM_SEED)
    for i, t in enumerate(tenant_rows):
        n_for_tenant = int(per_tenant[i])
        is_french = t["has_french_vocab"] == 1
        # 渠道偏好按全局 channel weights 抽样
        channel_indices = np.random.choice(
            6,
            size=n_for_tenant,
            p=np.array(list(CHANNEL_WEIGHTS.values())) / sum(CHANNEL_WEIGHTS.values()),
        )
        for k in range(n_for_tenant):
            if is_french and random.random() < 0.6:
                fn = fr_fake.first_name()
                ln = fr_fake.last_name()
            else:
                fn = fake.first_name()
                ln = fake.last_name()
            reg_offset = random.randint(30, 2200)
            reg_date = REFERENCE_DATE - timedelta(days=reg_offset)
            rows.append(
                {
                    "citizen_id": citizen_id,
                    "tenant_id": t["tenant_id"],
                    "citizen_external_id": f"CIT-{t['tenant_code'].upper()}-{citizen_id:08d}",
                    "first_name": fn,
                    "last_name": ln,
                    "email": f"{fn.lower()}.{ln.lower()}@example.com".replace(" ", ""),
                    "phone": fake.numerify(text="###-###-####"),
                    "registered_on": reg_date,
                    "preferred_channel_id": int(channel_indices[k]) + 1,
                }
            )
            citizen_id += 1
    return pl.DataFrame(rows)


def gen_addresses(df_tenants: pl.DataFrame) -> pl.DataFrame:
    """约 15 万地址。"""
    total = TOTAL_ADDRESSES
    pops = df_tenants["population"].to_numpy()
    pop_share = pops / pops.sum()
    per_tenant = np.maximum(50, np.round(pop_share * total).astype(int))

    rows = []
    addr_id = 1
    for i, t in enumerate(df_tenants.to_dicts()):
        n = int(per_tenant[i])
        # tenant 城市的近似中心 (随机生成的合理 lat/lng)
        base_lat = random.uniform(25.0, 49.0)
        base_lng = random.uniform(-123.0, -71.0)
        for _ in range(n):
            street = fake.street_address()
            zip_code = fake.zipcode() if t["country"] == "US" else fake.bothify("?#? #?#").upper()
            lat = base_lat + random.uniform(-0.05, 0.05)
            lng = base_lng + random.uniform(-0.05, 0.05)
            rows.append(
                {
                    "address_id": addr_id,
                    "tenant_id": t["tenant_id"],
                    "street_address": street,
                    "city": t["tenant_name"].replace("City of ", "").replace("Ville de ", ""),
                    "state_or_province": t["state_or_province"],
                    "postal_code": zip_code,
                    "latitude": round(lat, 5),
                    "longitude": round(lng, 5),
                    "neighborhood": random.choice([
                        "Downtown", "North End", "South Side", "West End",
                        "East Side", "Midtown", "Old Town", "Riverside",
                    ]),
                }
            )
            addr_id += 1
    return pl.DataFrame(rows)


def gen_assets(df_tenants: pl.DataFrame, df_addresses: pl.DataFrame) -> pl.DataFrame:
    """约 8 万资产, 每个资产关联一个地址。"""
    total = TOTAL_ASSETS
    asset_types = ["streetlight", "hydrant", "intersection", "trash_can", "sign", "bench"]
    # 按 tenant 比例分布资产
    pops = df_tenants["population"].to_numpy()
    pop_share = pops / pops.sum()
    per_tenant = np.maximum(20, np.round(pop_share * total).astype(int))

    # 按 tenant 索引的 address_id 列表
    addr_by_tenant: dict[int, list[int]] = {}
    for a in df_addresses.iter_rows(named=True):
        addr_by_tenant.setdefault(a["tenant_id"], []).append(a["address_id"])

    rows = []
    asset_id = 1
    for i, t in enumerate(df_tenants.to_dicts()):
        n = int(per_tenant[i])
        addrs = addr_by_tenant.get(t["tenant_id"], [])
        if not addrs:
            continue
        for _ in range(n):
            atype = random.choice(asset_types)
            rows.append(
                {
                    "asset_id": asset_id,
                    "tenant_id": t["tenant_id"],
                    "address_id": random.choice(addrs),
                    "asset_type": atype,
                    "asset_external_id": f"{atype[:3].upper()}-{t['tenant_code'].upper()}-{asset_id:06d}",
                    "installed_on": REFERENCE_DATE - timedelta(days=random.randint(365, 7300)),
                }
            )
            asset_id += 1
    return pl.DataFrame(rows)


def gen_staff_users(df_tenants: pl.DataFrame, df_departments: pl.DataFrame) -> pl.DataFrame:
    """约 2.5 万员工, 每个部门 10 到 20 人。"""
    roles = ["call_taker", "supervisor", "inspector", "manager", "director", "crew_lead"]
    role_weights = [0.30, 0.20, 0.20, 0.15, 0.05, 0.10]
    rows = []
    staff_id = 1
    # 按 tenant 大小决定每部门人数
    tenant_size_map = {r["tenant_id"]: r["size_tier"] for r in df_tenants.iter_rows(named=True)}
    for d in df_departments.iter_rows(named=True):
        tier = tenant_size_map[d["tenant_id"]]
        n = {"large": random.randint(20, 30), "medium": random.randint(12, 20), "small": random.randint(6, 12)}[tier]
        for _ in range(n):
            role = random.choices(roles, weights=role_weights, k=1)[0]
            fn = fake.first_name()
            ln = fake.last_name()
            rows.append(
                {
                    "staff_id": staff_id,
                    "tenant_id": d["tenant_id"],
                    "dept_id": d["dept_id"],
                    "staff_name": f"{fn} {ln}",
                    "role": role,
                    "email": f"{fn.lower()}.{ln.lower()}@{d['dept_code'].lower()}.gov".replace(" ", ""),
                    "hired_on": REFERENCE_DATE - timedelta(days=random.randint(60, 4000)),
                    "is_active": 1,
                }
            )
            staff_id += 1
    return pl.DataFrame(rows)


def gen_field_crews(df_tenants: pl.DataFrame, df_departments: pl.DataFrame) -> pl.DataFrame:
    """约 2500 个班组, 隶属现场部门 (streets, sanitation, parks, utilities)。"""
    rows = []
    crew_id = 1
    field_dept_types = {"streets", "sanitation", "parks", "utilities", "water"}
    for d in df_departments.iter_rows(named=True):
        if d["dept_type"] not in field_dept_types:
            continue
        n = random.randint(2, 6)
        for k in range(n):
            shift = random.choices(["day", "night", "swing"], weights=[0.6, 0.25, 0.15], k=1)[0]
            rows.append(
                {
                    "crew_id": crew_id,
                    "tenant_id": d["tenant_id"],
                    "dept_id": d["dept_id"],
                    "crew_code": f"{d['dept_code'][:8]}-{shift[0].upper()}{k+1}",
                    "crew_size": random.randint(2, 6),
                    "shift_type": shift,
                }
            )
            crew_id += 1
    return pl.DataFrame(rows)


def gen_service_requests(
    df_tenants: pl.DataFrame,
    df_categories: pl.DataFrame,
    df_departments: pl.DataFrame,
    df_addresses: pl.DataFrame,
    df_assets: pl.DataFrame,
    df_citizens: pl.DataFrame,
) -> tuple[pl.DataFrame, dict]:
    """生成 100 万 service_requests 以及隐藏的 ground truth 标签字典。
    返回 (df_service_requests, hidden_labels_dict), 后者供 description, model_predictions,
    work_orders, sla_breach_log, citizen_complaints 等下游表使用。"""
    rng = np.random.default_rng(RANDOM_SEED)
    n = TOTAL_SERVICE_REQUESTS

    # tenant 加权采样 (按 population)
    tenant_ids = df_tenants["tenant_id"].to_numpy()
    pops = df_tenants["population"].to_numpy().astype(np.float64)
    tenant_probs = pops / pops.sum()
    sr_tenant_ids = rng.choice(tenant_ids, size=n, p=tenant_probs)

    # tenant 元信息查询字典
    tenant_drift_map = dict(zip(df_tenants["tenant_id"].to_list(), df_tenants["vocab_drift_level"].to_list()))
    tenant_french_map = dict(zip(df_tenants["tenant_id"].to_list(), df_tenants["has_french_vocab"].to_list()))

    # 渠道加权采样
    channel_weights = np.array(list(CHANNEL_WEIGHTS.values()))
    channel_weights /= channel_weights.sum()
    sr_channel_ids = rng.choice(np.arange(1, 7), size=n, p=channel_weights)

    # 严重度采样 (低概率紧急)
    sev_codes = list(STATED_SEVERITY_WEIGHTS.keys())
    sev_weights = np.array(list(STATED_SEVERITY_WEIGHTS.values()))
    sev_weights /= sev_weights.sum()
    sr_severities = rng.choice(sev_codes, size=n, p=sev_weights)

    # true category 采样 (按 category_group)
    # 先构造 category_id 列表与每个的权重
    cat_rows = df_categories.to_dicts()
    cat_ids = np.array([c["category_id"] for c in cat_rows])
    cat_groups = np.array([c["category_group"] for c in cat_rows])
    cat_priorities = np.array([c["default_priority"] for c in cat_rows])
    # group_id 索引: 用于按 group 抽样
    group_weights = CATEGORY_GROUP_WEIGHTS.copy()
    # true_category 是请求"真实归属"的类别, 绝不会是 Other —— Other 只是模型置信度不足时的
    # 兜底桶 (由 will_be_other 路径注入)。因此这里把 Other 组权重置 0, 仅在 66 个普通类内
    # 按 group 权重抽样。这样 auto_category=Other 只来自 will_be_other 的 8%, 不再叠加
    # "true_cat 抽到 Other 组又没被 misclassify" 的那部分 (修复实测 14.4% -> 8% 的 P0)。
    cat_weights = np.zeros(len(cat_ids))
    for i, g in enumerate(cat_groups):
        cat_weights[i] = 0.0 if g == "Other" else group_weights[g]
    # 每个 group 内均匀分摊该 group 的权重 (除以该 group 的 category 个数)
    from collections import Counter
    group_sizes = Counter(cat_groups.tolist())
    for i, g in enumerate(cat_groups):
        if g != "Other":
            cat_weights[i] /= group_sizes[g]
    # 归一化 (仅非 Other 类, 重整后 7 个普通大类的 auto 占比叠加 8% Other 后回到 4.3 节口径)
    cat_weights /= cat_weights.sum()
    true_cat_ids = rng.choice(cat_ids, size=n, p=cat_weights)

    # 隐藏标签: 是否会被分类到 Other
    will_be_other_global = rng.random(n) < OTHER_AUTO_CATEGORY_RATE
    # has_emergency_keyword: 仅当 stated_severity in {low, medium}
    is_low_med = np.isin(sr_severities, ["low", "medium"])
    has_emergency_kw = (rng.random(n) < EMERGENCY_KW_WITHIN_LOW_MED) & is_low_med
    # has_escalation_keyword: 3% 全局
    has_escalation_kw = rng.random(n) < ESCALATION_KW_RATE
    # quick_close (24h 内关闭) 全局 40%
    will_quick_close = rng.random(n) < QUICK_CLOSE_RATE

    # 计算 auto_category_id:
    # - 若 will_be_other: auto_category = 80 (Other)
    # - 否则: 大部分情况 auto_category = true_category
    # - 高 vocab drift 的 tenant 额外有概率把 auto_category 抽错到另一个 category
    auto_cat_ids = true_cat_ids.copy()
    sr_drift = np.array([tenant_drift_map[int(t)] for t in sr_tenant_ids])

    # 高 drift tenant: 28% 概率 auto_category 错配
    high_drift_mask = sr_drift == "high"
    medium_drift_mask = sr_drift == "medium"
    low_drift_mask = sr_drift == "low"

    # 高 drift 的非 Other 子集额外 28% 抽错
    misclassify_mask_high = high_drift_mask & ~will_be_other_global & (rng.random(n) < 0.28)
    # 中 drift 的非 Other 子集 17% 抽错
    misclassify_mask_med = medium_drift_mask & ~will_be_other_global & (rng.random(n) < 0.17)
    # 低 drift 的非 Other 子集 10% 抽错
    misclassify_mask_low = low_drift_mask & ~will_be_other_global & (rng.random(n) < 0.10)
    misclassify_mask = misclassify_mask_high | misclassify_mask_med | misclassify_mask_low

    # 对 misclassify_mask 的位置, 把 auto_cat 换成另一个随机非 Other 类别
    non_other_ids = cat_ids[cat_ids != 80]
    random_replacements = rng.choice(non_other_ids, size=int(misclassify_mask.sum()))
    auto_cat_ids[misclassify_mask] = random_replacements

    # will_be_other 的位置, auto_cat = 80
    auto_cat_ids[will_be_other_global] = 80

    # Trap 1: will_be_other 的请求 (auto_category=Other) 分两类 true_category:
    #   - 约 88% 是"真正无法归类"的请求 (一般咨询 / 状态查询 / 模糊反馈),
    #     true_category = Other (80), 描述用 Other 组的泛化模板, 不含任何强关键词。
    #     模型把它们兜底到 Other 是"正确"的 (predicted=80, ground_truth=80 命中)。
    #   - 约 12% 是"模型本可正确分类却漏掉"的请求 (OTHER_MISROUTE_WITHIN_OTHER),
    #     true_category = 6 个强类别之一, 描述强制命中对应强关键词 (见 STRONG_KW_PHRASES),
    #     模型仍兜底到 Other (predicted=80) 因而 ground_truth != predicted, 构成误分类。
    # force_strong_kw_idx 把"必须命中哪个强关键词概念"传给 description 生成函数,
    # 概念顺序与 strong_cat_ids 一一对应, 保证 Other 强关键词命中率恰为 12%。
    code_to_id = {c["category_code"]: c["category_id"] for c in cat_rows}
    strong_cat_ids = [code_to_id[code] for code in
                      ["pothole", "streetlight_out", "graffiti_removal",
                       "illegal_dumping", "loud_party", "tree_limb_hanging"]
                      if code in code_to_id]
    strong_cat_arr = np.array(strong_cat_ids)
    force_strong_kw_idx = np.full(n, -1, dtype=np.int64)
    other_indices = np.where(will_be_other_global)[0]
    n_other = len(other_indices)
    misroute_in_other = rng.random(n_other) < OTHER_MISROUTE_WITHIN_OTHER
    misroute_indices = other_indices[misroute_in_other]
    non_misroute_indices = other_indices[~misroute_in_other]
    # 88% 真正的 Other: true_category = 80 (描述走 Other 泛化模板)
    true_cat_ids[non_misroute_indices] = 80
    # 12% 模型漏标: true_category = 强类别, 并标记强制命中的强关键词概念
    if len(misroute_indices) > 0 and len(strong_cat_arr) > 0:
        concept_idx = rng.integers(0, len(strong_cat_arr), size=len(misroute_indices))
        true_cat_ids[misroute_indices] = strong_cat_arr[concept_idx]
        force_strong_kw_idx[misroute_indices] = concept_idx

    # 计算 routed_dept_id: 由 (tenant, auto_category) 查 category_dept_routing
    # 预先构造 lookup
    tenant_dept_general: dict[int, int] = {}  # tenant_id -> general_queue dept_id
    tenant_dept_by_type: dict[int, dict[str, int]] = {}  # tenant_id -> {dept_type: dept_id}
    for d in df_departments.iter_rows(named=True):
        tenant_dept_by_type.setdefault(d["tenant_id"], {})[d["dept_type"]] = d["dept_id"]
        if d["is_general_queue"] == 1:
            tenant_dept_general[d["tenant_id"]] = d["dept_id"]

    cat_group_lookup = {c["category_id"]: c["category_group"] for c in cat_rows}
    group_to_dept_type = {
        "Streets": "streets", "Sanitation": "sanitation", "Utilities": "utilities",
        "Parks": "parks", "Code": "code_enforcement", "Animal": "animal_services",
        "Noise": "noise_control", "Other": "general_queue",
    }

    routed_dept_ids = np.zeros(n, dtype=np.int64)
    for i in range(n):
        t_id = int(sr_tenant_ids[i])
        cat_id = int(auto_cat_ids[i])
        cat_group = cat_group_lookup[cat_id]
        target_type = group_to_dept_type.get(cat_group, "general_queue")
        dept_id = tenant_dept_by_type[t_id].get(target_type)
        if dept_id is None:
            dept_id = tenant_dept_general[t_id]
        routed_dept_ids[i] = dept_id

    # 生成 created_at: 36 个月内, 工作日加权偏高, 工作时段加权偏高
    span_seconds = int((DATA_END_DATE - DATA_START_DATE).total_seconds())
    created_offsets = rng.integers(0, span_seconds, size=n)
    base_dt = datetime.combine(DATA_START_DATE, datetime.min.time())
    created_at_list = [base_dt + timedelta(seconds=int(o)) for o in created_offsets]

    # 生成 closed_at 与 SLA breach (自洽版本):
    # 关键修复 (P1): is_breach 必须由"实际工作日 > SLA target"派生, 而不是独立抽样,
    # 否则会出现"被标 breach 但 actual<=target / breach_business_days!=actual-target"的矛盾。
    sla_target_by_priority = {"emergency": 1, "high": 2, "medium": 3, "low": 5}
    cat_id_to_priority = {c["category_id"]: c["default_priority"] for c in cat_rows}
    base_sla = np.array([sla_target_by_priority[cat_id_to_priority[int(c)]] for c in auto_cat_ids])

    # 整体 breach 目标口径: 基线 23%, Other 32%, 高 drift +5pp。
    # 速关 (24h 内关闭) 一律 on-time (实际工作日 < target, 不可能 breach), 因此 breach 只可能
    # 落在非速关子集。把"整体目标概率"换算成"非速关条件概率": cond = overall / (1 - quick_rate),
    # 这样 P(breach) = P(非速关) * cond = overall, 既保住整体口径, 又保证速关恒 on-time。
    is_other_auto = auto_cat_ids == 80
    overall_breach_prob = np.full(n, BASELINE_SLA_BREACH_RATE)
    overall_breach_prob[is_other_auto] = OTHER_SLA_BREACH_RATE
    # 高 vocab drift 的 10 个租户 SLA breach 比基线高约 8pp (trap 5 的次生 SLA 信号):
    # 这让高 drift 城 (如 Quebec) 的月度 sla 稳定落在约 0.28 到 0.31, 在 churn_risk_band
    # 上可靠地落入 high, 使 Q20 的"Austin 健康 / Quebec 高风险"故事可复现。
    overall_breach_prob[high_drift_mask] += 0.08
    cond_breach_prob = np.clip(overall_breach_prob / (1.0 - QUICK_CLOSE_RATE), 0.0, 0.95)
    is_breach = (~will_quick_close) & (rng.random(n) < cond_breach_prob)

    # 实际工作日数 actual_business_days:
    #   - 速关: 0 (24h 内当日完成)
    #   - breach: target + breach_offset (offset>=1, 截断几何分布, 长尾产生 critical 等级)
    #   - 非 breach 非速关: [1, target] 之间, 一定 <= target (on-time)
    breach_offset = np.clip(rng.geometric(0.45, size=n), 1, 15)
    non_breach_bd = np.maximum(1, np.ceil(rng.random(n) * base_sla).astype(np.int64))
    non_breach_bd = np.minimum(non_breach_bd, base_sla)
    actual_bd = np.where(is_breach, base_sla + breach_offset, non_breach_bd)
    actual_bd[will_quick_close] = 0

    # closed_at: 由 actual_business_days 换算回自然日 (工作日 * 7/5 + 抖动);
    #   速关用 [0.5, 24] 小时, 保证 Q3 的 julianday 差 <= 1;
    #   非速关一定 > 1 个自然日, 不会被 Q3 误判成速关。
    is_closed = rng.random(n) < 0.99
    quick_hours = rng.uniform(0.5, 24.0, size=n)
    nonquick_cal_days = actual_bd * 7.0 / 5.0 + rng.random(n) * 0.9
    nonquick_cal_days = np.maximum(nonquick_cal_days, 1.05)
    closed_at_list = []
    for i in range(n):
        if not is_closed[i]:
            closed_at_list.append(None)
        elif will_quick_close[i]:
            closed_at_list.append(created_at_list[i] + timedelta(hours=float(quick_hours[i])))
        else:
            closed_at_list.append(created_at_list[i] + timedelta(days=float(nonquick_cal_days[i])))

    # current_status
    current_status_list = []
    status_rand = rng.random(n)
    for i in range(n):
        if not is_closed[i]:
            r = status_rand[i]
            if r < 0.4:
                current_status_list.append("in_progress")
            elif r < 0.65:
                current_status_list.append("assigned")
            elif r < 0.8:
                current_status_list.append("on_hold")
            elif r < 0.95:
                current_status_list.append("classified")
            else:
                current_status_list.append("open")
        else:
            current_status_list.append("closed")

    # 重新检查 closed_at 是否超过 REFERENCE_DATE; 如果超过, clip 到 reference - 1 day
    ref_dt = datetime.combine(REFERENCE_DATE, datetime.min.time())
    closed_at_final = []
    for i in range(n):
        if closed_at_list[i] is None:
            closed_at_final.append(None)
        elif closed_at_list[i] >= ref_dt:
            # 把它改为未关闭状态
            closed_at_final.append(None)
            current_status_list[i] = "in_progress"
        else:
            closed_at_final.append(closed_at_list[i])

    # address_id 与 citizen_id 采样 (按 tenant 限定)
    addr_by_tenant: dict[int, list[int]] = {}
    for a in df_addresses.iter_rows(named=True):
        addr_by_tenant.setdefault(a["tenant_id"], []).append(a["address_id"])
    citizen_by_tenant: dict[int, list[int]] = {}
    for c in df_citizens.iter_rows(named=True):
        citizen_by_tenant.setdefault(c["tenant_id"], []).append(c["citizen_id"])
    asset_by_tenant: dict[int, list[int]] = {}
    for a in df_assets.iter_rows(named=True):
        asset_by_tenant.setdefault(a["tenant_id"], []).append(a["asset_id"])

    sr_address_ids: list[int | None] = []
    sr_citizen_ids: list[int | None] = []
    sr_asset_ids: list[int | None] = []
    for i in range(n):
        t_id = int(sr_tenant_ids[i])
        addrs = addr_by_tenant.get(t_id, [])
        cits = citizen_by_tenant.get(t_id, [])
        assets = asset_by_tenant.get(t_id, [])
        # 5% 匿名 (no address), 8% 无 citizen, 70% 无 asset
        if addrs and rng.random() > 0.05:
            sr_address_ids.append(addrs[rng.integers(0, len(addrs))])
        else:
            sr_address_ids.append(None)
        if cits and rng.random() > 0.08:
            sr_citizen_ids.append(cits[rng.integers(0, len(cits))])
        else:
            sr_citizen_ids.append(None)
        if assets and rng.random() > 0.70:
            sr_asset_ids.append(assets[rng.integers(0, len(assets))])
        else:
            sr_asset_ids.append(None)

    # Trap 3: 30 天复发陷阱。从 quick_close on_time 池里采样部分作为 parent,
    # 把另一批 SR 改为 child: 同 address + close_at + 1..29 days 后
    # 目标: 总共约 73000 child SRs (15% × ~280k quick on_time + 5% × ~640k 非 quick on_time)
    closed_arr = np.array([c is not None for c in closed_at_final])
    on_time_mask = closed_arr & ~is_breach
    quick_on_time_idx = np.where(will_quick_close & on_time_mask & (np.array(sr_address_ids) != None))[0]
    non_quick_on_time_idx = np.where(~will_quick_close & on_time_mask & (np.array(sr_address_ids) != None))[0]

    n_quick_repeats = int(len(quick_on_time_idx) * QUICK_CLOSE_REPEAT_30D)
    n_normal_repeats = int(len(non_quick_on_time_idx) * NORMAL_REPEAT_30D)

    # 随机选 n_quick_repeats 个 parent
    quick_parent_choice = rng.choice(quick_on_time_idx, size=min(n_quick_repeats, len(quick_on_time_idx)), replace=False)
    normal_parent_choice = rng.choice(non_quick_on_time_idx, size=min(n_normal_repeats, len(non_quick_on_time_idx)), replace=False)
    all_parents = np.concatenate([quick_parent_choice, normal_parent_choice])
    # 选 child indices: 从所有 SR 中除 parents 之外随机选, 数量等于 parents
    parent_set = set(all_parents.tolist())
    all_indices = np.arange(n)
    candidates = np.array([i for i in all_indices if i not in parent_set])
    child_indices = rng.choice(candidates, size=len(all_parents), replace=False)

    # 把每个 child 改为同 parent 的 address + close + 1..29 days
    parent_to_child = list(zip(all_parents.tolist(), child_indices.tolist()))
    for p_idx, c_idx in parent_to_child:
        parent_addr = sr_address_ids[p_idx]
        parent_tenant = int(sr_tenant_ids[p_idx])
        parent_closed = closed_at_final[p_idx]
        if parent_closed is None:
            continue
        # child's tenant follows parent's tenant
        sr_tenant_ids[c_idx] = parent_tenant
        sr_address_ids[c_idx] = parent_addr
        # child's citizen needs to belong to parent's tenant
        cits = citizen_by_tenant.get(parent_tenant, [])
        if cits:
            sr_citizen_ids[c_idx] = cits[rng.integers(0, len(cits))]
        sr_asset_ids[c_idx] = None  # 简化, 不维护 asset 引用
        # child created_at = parent.closed_at + 1..29 days
        days_offset = float(rng.uniform(1, 29))
        new_created = parent_closed + timedelta(days=days_offset)
        if new_created >= ref_dt:
            new_created = parent_closed + timedelta(days=1)
        created_at_list[c_idx] = new_created
        # child closed_at: 处理时长重算 (1 到 5 天)
        new_hours = float(rng.uniform(8, 120))
        new_closed = new_created + timedelta(hours=new_hours)
        if new_closed >= ref_dt:
            closed_at_final[c_idx] = None
            current_status_list[c_idx] = "in_progress"
        else:
            closed_at_final[c_idx] = new_closed
            current_status_list[c_idx] = "closed"
        # child 是"同址复发"的快速处置请求, 视作 on-time, 不进 breach log
        is_breach[c_idx] = False
        actual_bd[c_idx] = 0
        # child 的 routed_dept_id 重算 (tenant 变了)
        cat_id = int(auto_cat_ids[c_idx])
        cat_group = cat_group_lookup[cat_id]
        target_type = group_to_dept_type.get(cat_group, "general_queue")
        dept_id = tenant_dept_by_type[parent_tenant].get(target_type)
        if dept_id is None:
            dept_id = tenant_dept_general[parent_tenant]
        routed_dept_ids[c_idx] = dept_id

    # is_duplicate (轻量但合法): 约 1.5% 的请求标记为重复, duplicate_of_request_id 指向
    # 同 tenant 内 created_at 更早的紧邻一条 (满足 ER 业务约束 b: 非空 + 同 tenant + 更早)。
    # 排除 trap3 的 parent / child 以免污染同址复发信号。真实平台重复检测不完美, 这里保留
    # 少量"漏检"重复信号供"同址多请求"叙事引用。
    child_set = set(int(c) for c in child_indices.tolist())
    created_ts = np.array([c.timestamp() for c in created_at_list], dtype=np.float64)
    order = np.lexsort((created_ts, sr_tenant_ids))  # 先按 tenant, 再按 created_at 升序
    is_dup = np.zeros(n, dtype=np.int64)
    dup_of = np.zeros(n, dtype=np.int64)  # 0 表示无 (request_id 从 1 起)
    dup_rand = rng.random(n)
    prev_idx = -1
    prev_tenant = -1
    for pos in order:
        pos = int(pos)
        t = int(sr_tenant_ids[pos])
        if (
            t == prev_tenant
            and prev_idx != -1
            and created_ts[prev_idx] < created_ts[pos]  # 严格更早 (排除同秒并列, 满足 ER 约束 b)
            and dup_rand[pos] < 0.015
            and pos not in parent_set
            and pos not in child_set
        ):
            is_dup[pos] = 1
            dup_of[pos] = prev_idx + 1  # request_id = index + 1, 同 tenant 且 created_at 严格更早
        prev_tenant = t
        prev_idx = pos
    dup_of_list = [int(dup_of[i]) if dup_of[i] > 0 else None for i in range(n)]

    # 构造主 DataFrame
    df_sr = pl.DataFrame(
        {
            "request_id": list(range(1, n + 1)),
            "tenant_id": sr_tenant_ids.tolist(),
            "citizen_id": sr_citizen_ids,
            "address_id": sr_address_ids,
            "asset_id": sr_asset_ids,
            "auto_category_id": auto_cat_ids.tolist(),
            "channel_id": sr_channel_ids.tolist(),
            "routed_dept_id": routed_dept_ids.tolist(),
            "stated_severity": sr_severities.tolist(),
            "current_status": current_status_list,
            "created_at": created_at_list,
            "closed_at": closed_at_final,
            "is_duplicate": is_dup.tolist(),
            "duplicate_of_request_id": dup_of_list,
        }
    )

    hidden_labels = {
        "true_category_ids": true_cat_ids,
        "will_be_other": will_be_other_global,
        "has_emergency_kw": has_emergency_kw,
        "has_escalation_kw": has_escalation_kw,
        "will_quick_close": will_quick_close,
        "is_breach": is_breach,
        "is_closed": closed_arr,
        "vocab_drift": sr_drift,
        "tenant_french": np.array([tenant_french_map[int(t)] for t in sr_tenant_ids]),
        "base_sla": base_sla,
        "actual_business_days": actual_bd,
        "force_strong_kw_idx": force_strong_kw_idx,
    }

    return df_sr, hidden_labels


def gen_request_descriptions(df_sr: pl.DataFrame, hidden: dict) -> pl.DataFrame:
    """生成 100 万 description, 按 ground truth 标签模板组合。"""
    n = df_sr.height
    cat_rows = []  # 不需要; 我们用 hidden["true_category_ids"]
    true_cat_ids = hidden["true_category_ids"]
    has_emergency = hidden["has_emergency_kw"]
    has_escalation = hidden["has_escalation_kw"]
    tenant_french = hidden["tenant_french"]
    force_strong_kw_idx = hidden["force_strong_kw_idx"]

    # category id -> category_group 反查 (与 gen_service_requests 共用)
    # 重新查 service_categories
    df_cats = pl.read_csv(DATA_DIR / "02_service_categories.tsv", separator="\t")
    cat_id_to_group = dict(zip(df_cats["category_id"].to_list(), df_cats["category_group"].to_list()))

    # channel_id 用来决定 IVR 噪声
    channels = df_sr["channel_id"].to_numpy()

    descriptions = []
    submitted_via_text = []
    for i in range(n):
        ch = int(channels[i])
        is_ivr = ch == 3
        if is_ivr:
            opening = random.choice(OPENING_PHRASES_IVR)
        else:
            opening = random.choice(OPENING_PHRASES_WEB)

        kw_idx = int(force_strong_kw_idx[i])
        if kw_idx >= 0:
            # Trap 1 misroute 子集: 强制命中对应强关键词概念 (与 true_category 一致)
            core = STRONG_KW_PHRASES[kw_idx].format(street_token=random.choice(STREET_TOKENS))
        else:
            cat_group = cat_id_to_group.get(int(true_cat_ids[i]), "Other")
            core_templates = CORE_TEMPLATES_BY_GROUP.get(cat_group, CORE_TEMPLATES_BY_GROUP["Other"])
            core = random.choice(core_templates).format(street_token=random.choice(STREET_TOKENS))

        parts = [opening, core]

        if has_emergency[i]:
            parts.append(". " + random.choice(EMERGENCY_PHRASES))

        if has_escalation[i]:
            parts.append(". " + random.choice(ESCALATION_PHRASES))

        if tenant_french[i] == 1 and random.random() < 0.4:
            parts.append(". " + random.choice(FRENCH_FRAGMENTS))

        parts.append(" " + random.choice(CLOSING_PHRASES))

        text = " ".join(parts).strip()
        if is_ivr:
            # 插入 1 到 3 个 IVR noise tokens
            tokens = text.split(" ")
            for _ in range(random.randint(1, 3)):
                pos = random.randint(0, len(tokens) - 1)
                tokens.insert(pos, random.choice(IVR_NOISE))
            text = " ".join(tokens).lower()

        descriptions.append(text)
        submitted_via_text.append(0 if is_ivr else 1)

    return pl.DataFrame(
        {
            "description_id": list(range(1, n + 1)),
            "request_id": df_sr["request_id"].to_list(),
            "description_text": descriptions,
            "description_length": [len(d) for d in descriptions],
            "submitted_via_text_field": submitted_via_text,
        }
    )


def gen_request_events(df_sr: pl.DataFrame, df_staff: pl.DataFrame, hidden: dict) -> pl.DataFrame:
    """每条 SR 生成 4 个事件 (created, classified, assigned, closed); 部分加 reopened。
    Trap 2 契约: has_emergency_kw 且 stated_severity 为 low/medium 的 SR reopen 概率 ~25%,
    其余按基线 ~5%。
    总行数约 400 万。"""
    rng = np.random.default_rng(RANDOM_SEED + 1)
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    created_dts = df_sr["created_at"].to_list()
    closed_dts = df_sr["closed_at"].to_list()
    current_statuses = df_sr["current_status"].to_list()
    tenant_ids = df_sr["tenant_id"].to_numpy()
    severities = df_sr["stated_severity"].to_numpy()

    # staff_by_tenant 用于 by_staff_id 抽样
    staff_by_tenant: dict[int, list[int]] = {}
    for s in df_staff.iter_rows(named=True):
        staff_by_tenant.setdefault(s["tenant_id"], []).append(s["staff_id"])

    events = []
    eid = 1

    # Trap 2: emergency_kw + low/med 子集 reopen 概率 ~25%; 其余按基线 ~5%
    has_emergency = hidden["has_emergency_kw"]
    is_low_med = np.isin(severities, ["low", "medium"])
    reopen_prob = np.where(
        has_emergency & is_low_med,
        EMERGENCY_KW_REOPEN_RATE,
        BASELINE_REOPEN_RATE,
    )
    will_reopen = rng.random(n) < reopen_prob

    for i in range(n):
        ct = created_dts[i]
        closed = closed_dts[i]
        t_id = int(tenant_ids[i])
        staff_pool = staff_by_tenant.get(t_id, [])
        # event 1: created
        events.append({
            "event_id": eid,
            "request_id": int(request_ids[i]),
            "event_type": "created",
            "event_at": ct,
            "by_staff_id": None,
            "event_note": "Auto created from intake",
        })
        eid += 1
        # event 2: classified (30s to 5min later)
        ev2 = ct + timedelta(seconds=int(rng.integers(30, 300)))
        events.append({
            "event_id": eid,
            "request_id": int(request_ids[i]),
            "event_type": "classified",
            "event_at": ev2,
            "by_staff_id": None,
            "event_note": "Auto classified",
        })
        eid += 1
        # event 3: assigned (1h to 8h later)
        if current_statuses[i] in ("assigned", "in_progress", "on_hold", "closed", "reopened"):
            ev3 = ct + timedelta(minutes=int(rng.integers(60, 480)))
            sid = int(rng.choice(staff_pool)) if staff_pool else None
            events.append({
                "event_id": eid,
                "request_id": int(request_ids[i]),
                "event_type": "assigned",
                "event_at": ev3,
                "by_staff_id": sid,
                "event_note": None,
            })
            eid += 1
        # event 4: closed
        if closed is not None:
            sid = int(rng.choice(staff_pool)) if staff_pool else None
            events.append({
                "event_id": eid,
                "request_id": int(request_ids[i]),
                "event_type": "closed",
                "event_at": closed,
                "by_staff_id": sid,
                "event_note": None,
            })
            eid += 1
            # 部分加 reopened (closed 之后 0 to 30 天, 业务规则: reopen 仅限 30 天内)。
            # 用平方分布前置加权: 多数 reopen 集中在前几天 (居民看到 crew 走后问题还在就立刻再报),
            # 使 Q14 的 0_1 / 2_7 桶占比明显, 同时 31_90 / over_90 桶恒为空 (与 30 天规则一致)。
            if will_reopen[i]:
                days_after = int((rng.random() ** 2) * 30)
                reopen_dt = closed + timedelta(days=days_after)
                ref_dt = datetime.combine(REFERENCE_DATE, datetime.min.time())
                if reopen_dt < ref_dt:
                    events.append({
                        "event_id": eid,
                        "request_id": int(request_ids[i]),
                        "event_type": "reopened",
                        "event_at": reopen_dt,
                        "by_staff_id": sid,
                        "event_note": "Citizen reported again",
                    })
                    eid += 1

    return pl.DataFrame(events)


def gen_request_assignments(df_sr: pl.DataFrame, df_staff: pl.DataFrame, df_crews: pl.DataFrame) -> pl.DataFrame:
    """每条非 open 的 SR 生成 1 条 assignment, 部分生成第 2 条 (reopen 后), 总约 120 万。"""
    rng = np.random.default_rng(RANDOM_SEED + 2)
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    tenant_ids = df_sr["tenant_id"].to_numpy()
    routed_dept_ids = df_sr["routed_dept_id"].to_list()
    created_dts = df_sr["created_at"].to_list()
    statuses = df_sr["current_status"].to_list()

    staff_by_dept: dict[int, list[int]] = {}
    for s in df_staff.iter_rows(named=True):
        staff_by_dept.setdefault(s["dept_id"], []).append(s["staff_id"])
    crews_by_dept: dict[int, list[int]] = {}
    for c in df_crews.iter_rows(named=True):
        crews_by_dept.setdefault(c["dept_id"], []).append(c["crew_id"])

    rows = []
    aid = 1
    for i in range(n):
        if statuses[i] in ("open", "classified"):
            continue
        dept = routed_dept_ids[i]
        if dept is None:
            continue
        spool = staff_by_dept.get(dept, [])
        cpool = crews_by_dept.get(dept, [])
        sid = int(rng.choice(spool)) if spool else None
        cid = int(rng.choice(cpool)) if cpool else None
        assigned_at = created_dts[i] + timedelta(minutes=int(rng.integers(60, 480)))
        rows.append({
            "assignment_id": aid,
            "request_id": int(request_ids[i]),
            "dept_id": int(dept),
            "staff_id": sid,
            "crew_id": cid,
            "assigned_at": assigned_at,
            "unassigned_at": None,
            "is_current": 1,
        })
        aid += 1
        # reopen 后再 assign 一次 (~7% × 30% 实际触发, 简化)
        if rng.random() < 0.02:
            assigned2 = assigned_at + timedelta(days=int(rng.integers(7, 60)))
            ref_dt = datetime.combine(REFERENCE_DATE, datetime.min.time())
            if assigned2 < ref_dt:
                rows.append({
                    "assignment_id": aid,
                    "request_id": int(request_ids[i]),
                    "dept_id": int(dept),
                    "staff_id": sid,
                    "crew_id": cid,
                    "assigned_at": assigned2,
                    "unassigned_at": None,
                    "is_current": 1,
                })
                aid += 1
    return pl.DataFrame(rows)


def gen_request_attachments(df_sr: pl.DataFrame) -> pl.DataFrame:
    """约 40% 请求 (主要 mobile_app) 有 1 到 2 张图片附件。"""
    rng = np.random.default_rng(RANDOM_SEED + 3)
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    channel_ids = df_sr["channel_id"].to_numpy()
    created_dts = df_sr["created_at"].to_list()

    rows = []
    attach_id = 1
    for i in range(n):
        ch = int(channel_ids[i])
        # mobile_app, social, email 渠道更可能带附件
        if ch in (2, 4, 5):
            prob = 0.55
        elif ch == 1:
            prob = 0.35
        else:
            prob = 0.15
        if rng.random() < prob:
            n_attach = 1 if rng.random() < 0.85 else 2
            for k in range(n_attach):
                ftype = "image" if rng.random() < 0.95 else "video"
                fname = f"sr_{int(request_ids[i])}_{k+1}.{('jpg' if ftype == 'image' else 'mp4')}"
                up_at = created_dts[i] + timedelta(minutes=int(rng.integers(1, 30)))
                rows.append({
                    "attachment_id": attach_id,
                    "request_id": int(request_ids[i]),
                    "file_type": ftype,
                    "file_name": fname,
                    "uploaded_at": up_at,
                })
                attach_id += 1
    return pl.DataFrame(rows)


def gen_work_orders(
    df_sr: pl.DataFrame,
    df_staff: pl.DataFrame,
    df_crews: pl.DataFrame,
) -> pl.DataFrame:
    """约 60% 的请求生成 work order, 约 60 万行。"""
    rng = np.random.default_rng(RANDOM_SEED + 4)
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    routed_dept_ids = df_sr["routed_dept_id"].to_list()
    created_dts = df_sr["created_at"].to_list()
    closed_dts = df_sr["closed_at"].to_list()
    statuses = df_sr["current_status"].to_list()

    staff_by_dept: dict[int, list[int]] = {}
    for s in df_staff.iter_rows(named=True):
        staff_by_dept.setdefault(s["dept_id"], []).append(s["staff_id"])
    crews_by_dept: dict[int, list[int]] = {}
    for c in df_crews.iter_rows(named=True):
        crews_by_dept.setdefault(c["dept_id"], []).append(c["crew_id"])

    rows = []
    wo_id = 1
    for i in range(n):
        if rng.random() >= WORK_ORDER_RATE:
            continue
        dept = routed_dept_ids[i]
        if dept is None:
            continue
        spool = staff_by_dept.get(dept, [])
        cpool = crews_by_dept.get(dept, [])
        sup_id = int(rng.choice(spool)) if spool else None
        crew_id = int(rng.choice(cpool)) if cpool else None
        opened_at = created_dts[i] + timedelta(minutes=int(rng.integers(30, 480)))
        closed_at = closed_dts[i] if statuses[i] == "closed" else None
        if closed_at is not None:
            outcome = random.choices(
                ["resolved", "deferred", "no_action", "unable_to_locate"],
                weights=[0.78, 0.10, 0.07, 0.05],
                k=1,
            )[0]
            if outcome == "resolved":
                fail_code = None
            else:
                fail_code = random.choice(
                    ["unable_to_access", "materials_missing", "weather", "deferred_to_capital", "no_issue_found"]
                )
        else:
            outcome = None
            fail_code = None
        rows.append({
            "work_order_id": wo_id,
            "request_id": int(request_ids[i]),
            "dept_id": int(dept),
            "crew_id": crew_id,
            "supervisor_staff_id": sup_id,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "outcome": outcome,
            "structured_fail_code": fail_code,
        })
        wo_id += 1
    return pl.DataFrame(rows)


def gen_work_order_notes(df_wo: pl.DataFrame, df_staff: pl.DataFrame) -> pl.DataFrame:
    """每个 WO 1 到 3 条备注, 平均 1.7 条, 总 ~100 万。"""
    rng = np.random.default_rng(RANDOM_SEED + 5)
    n = df_wo.height
    wo_ids = df_wo["work_order_id"].to_numpy()
    request_ids = df_wo["request_id"].to_numpy()
    outcomes = df_wo["outcome"].to_list()
    opened_dts = df_wo["opened_at"].to_list()
    closed_dts = df_wo["closed_at"].to_list()
    supervisor_ids = df_wo["supervisor_staff_id"].to_list()
    dept_ids = df_wo["dept_id"].to_list()

    staff_by_dept: dict[int, list[int]] = {}
    for s in df_staff.iter_rows(named=True):
        staff_by_dept.setdefault(s["dept_id"], []).append(s["staff_id"])

    rows = []
    note_id = 1
    for i in range(n):
        outcome = outcomes[i] or "resolved"
        templates = WO_NOTE_TEMPLATES_BY_OUTCOME.get(outcome, WO_NOTE_TEMPLATES_BY_OUTCOME["resolved"])
        n_notes = int(rng.choice([1, 2, 2, 3], p=[0.4, 0.35, 0.15, 0.10]))
        spool = staff_by_dept.get(int(dept_ids[i]), [])
        for k in range(n_notes):
            sid = supervisor_ids[i]
            if sid is None and spool:
                sid = int(rng.choice(spool))
            if sid is None:
                continue
            note_text = random.choice(templates)
            opened = opened_dts[i]
            closed = closed_dts[i] if closed_dts[i] is not None else opened + timedelta(days=3)
            span_sec = max(60, int((closed - opened).total_seconds()))
            note_at = opened + timedelta(seconds=int(rng.integers(0, span_sec)))
            note_type = random.choices(
                ["status_update", "fail_reason", "citizen_followup", "internal"],
                weights=[0.55, 0.15, 0.15, 0.15],
                k=1,
            )[0]
            rows.append({
                "note_id": note_id,
                "work_order_id": int(wo_ids[i]),
                "by_staff_id": sid,
                "note_at": note_at,
                "note_text": note_text,
                "note_type": note_type,
            })
            note_id += 1
    return pl.DataFrame(rows)


def gen_model_predictions(df_sr: pl.DataFrame, hidden: dict, df_cats: pl.DataFrame) -> pl.DataFrame:
    """NLP 模型预测, 100 万行。Audit 20% 的子集填 ground_truth。
    Trap 5: 高 drift tenant 的 predicted 与 ground_truth 一致率约 72%; 否则约 88%。"""
    rng = np.random.default_rng(RANDOM_SEED + 6)
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    created_dts = df_sr["created_at"].to_list()
    true_cat_ids = hidden["true_category_ids"]
    will_be_other = hidden["will_be_other"]
    drift = hidden["vocab_drift"]

    cat_ids = df_cats["category_id"].to_numpy()
    non_other_ids = cat_ids[cat_ids != 80]

    # predicted: 默认等于 true; 部分按 drift 错分; will_be_other 全部为 80。
    # 说明 (Trap 5 标定): audited accuracy = predicted==ground_truth 占比。
    # will_be_other (8%) 中 88% 真值即 Other(80) 且 predicted=80 -> 命中 (正确兜底),
    # 12% 真值为强类别 -> 误分。非 will_be_other (92%) 命中率 = 1 - error_rate。
    # 故 tenant accuracy ≈ 0.08*0.88 + 0.92*(1-error_rate):
    #   high  error 0.30 -> ~0.71; medium 0.16 -> ~0.84; low 0.11 -> ~0.89 (中位)。
    # 全局约 0.86, 与 Trap 5 契约 (high 0.72 / 中位 0.88 / 全局 0.86) 一致。
    predicted = true_cat_ids.copy()
    error_rates = np.where(drift == "high", 0.30, np.where(drift == "medium", 0.16, 0.11))
    errors = rng.random(n) < error_rates
    err_replacements = rng.choice(non_other_ids, size=int(errors.sum()))
    predicted[errors] = err_replacements
    # will_be_other 的 prediction 是 80
    predicted[will_be_other] = 80

    # confidence: will_be_other 在 [0.20, 0.44]; 错分在 [0.45, 0.70]; 正确在 [0.65, 0.99]
    confidence = np.zeros(n)
    confidence[will_be_other] = rng.uniform(0.20, 0.44, size=int(will_be_other.sum()))
    correct_non_other = (~will_be_other) & (predicted == true_cat_ids)
    wrong_non_other = (~will_be_other) & (predicted != true_cat_ids)
    confidence[correct_non_other] = rng.uniform(0.65, 0.99, size=int(correct_non_other.sum()))
    confidence[wrong_non_other] = rng.uniform(0.45, 0.70, size=int(wrong_non_other.sum()))

    # is_audited: 20% 全局
    is_audited = (rng.random(n) < AUDIT_SAMPLE_RATE).astype(int)
    ground_truth = np.where(is_audited == 1, true_cat_ids, np.array([None] * n, dtype=object))

    predicted_at_list = []
    for i in range(n):
        # 模型预测在 created_at 后 1 to 60 秒
        offset = int(rng.integers(1, 60))
        predicted_at_list.append(created_dts[i] + timedelta(seconds=offset))

    return pl.DataFrame({
        "prediction_id": list(range(1, n + 1)),
        "request_id": request_ids.tolist(),
        "predicted_category_id": predicted.tolist(),
        "confidence_score": [round(float(c), 3) for c in confidence],
        "predicted_at": predicted_at_list,
        "ground_truth_category_id": [int(g) if g is not None else None for g in ground_truth],
        "is_audited": is_audited.tolist(),
        "model_version": ["v3.2.1"] * n,
    })


def gen_sla_breach_log(df_sr: pl.DataFrame, df_sla: pl.DataFrame, hidden: dict) -> pl.DataFrame:
    """仅 breach 请求生成一条记录, ~25 万行。

    自洽性 (P1 修复): actual_business_days 与 breach_business_days 直接取自 gen_service_requests
    控制好的 actual_bd (= target + breach_offset), 因此恒有 actual > target 且
    breach_business_days = actual - target >= 1, 不再出现"标 breach 但 actual<=target"的矛盾。
    breach_severity 也因此能正常产出 critical (breach_business_days >= 6)。"""
    is_breach = hidden["is_breach"]
    base_sla = hidden["base_sla"]
    actual_bd = hidden["actual_business_days"]
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    tenant_ids = df_sr["tenant_id"].to_numpy()
    closed_dts = df_sr["closed_at"].to_list()
    closed_arr = np.array([c is not None for c in closed_dts])

    actual_breach = is_breach & closed_arr

    rows = []
    bid = 1
    for i in range(n):
        if not actual_breach[i]:
            continue
        target = int(base_sla[i])
        actual = int(actual_bd[i])
        breach_days = actual - target
        if breach_days < 1:
            # 安全网: 理论上不会发生 (breach 由 actual>target 派生), 跳过非真实超时
            continue
        if breach_days <= 2:
            sev = "minor"
        elif breach_days <= 5:
            sev = "major"
        else:
            sev = "critical"
        rows.append({
            "breach_id": bid,
            "request_id": int(request_ids[i]),
            "tenant_id": int(tenant_ids[i]),
            "breached_at": closed_dts[i],
            "target_business_days": target,
            "actual_business_days": actual,
            "breach_business_days": breach_days,
            "breach_severity": sev,
        })
        bid += 1
    return pl.DataFrame(rows)


def gen_citizen_complaints(df_sr: pl.DataFrame, hidden: dict) -> pl.DataFrame:
    """约 5000 条投诉记录, 主要来自 has_escalation_kw 子集 (8% lift) + 基线 0.3%。"""
    rng = np.random.default_rng(RANDOM_SEED + 7)
    n = df_sr.height
    request_ids = df_sr["request_id"].to_numpy()
    tenant_ids = df_sr["tenant_id"].to_numpy()
    citizen_ids = df_sr["citizen_id"].to_list()
    created_dts = df_sr["created_at"].to_list()
    has_escalation = hidden["has_escalation_kw"]

    # 升级概率: has_escalation 子集 8%, 基线 0.3%
    escalate_prob = np.where(has_escalation, ESCALATION_TO_COUNCIL_RATE, BASELINE_TO_COUNCIL_RATE)
    will_escalate = rng.random(n) < escalate_prob

    rows = []
    cid = 1
    council_names = [
        "Johnson", "Smith", "Garcia", "Lee", "Brown", "Williams",
        "Tremblay", "Bouchard", "Wong", "Patel", "Davis", "Martinez",
    ]
    channels = ["council_letter", "news_media", "lawyer_letter", "social_viral"]
    channel_weights = [0.60, 0.15, 0.15, 0.10]
    for i in range(n):
        if not will_escalate[i] or citizen_ids[i] is None:
            continue
        # filed_at 在 created_at 后 7 to 60 天
        days_after = int(rng.integers(7, 60))
        filed = (created_dts[i] + timedelta(days=days_after)).date()
        if filed >= REFERENCE_DATE:
            filed = REFERENCE_DATE - timedelta(days=1)
        ch = random.choices(channels, weights=channel_weights, k=1)[0]
        # narrative
        template = random.choice(COMPLAINT_NARRATIVE_TEMPLATES)
        narrative = template.format(
            n_times=random.choice(["three", "four", "five"]),
            start_month=random.choice(["January", "February", "March", "April"]),
            council_name=random.choice(council_names),
            street=random.choice(STREET_TOKENS),
            escalation_channel=ch.replace("_", " "),
            months_span=random.choice(["3", "4", "5", "6"]),
            issue_type=random.choice(["pothole", "trash", "streetlight", "noise"]),
        )
        # 部分已解决
        if rng.random() < 0.6:
            resolved_at = filed + timedelta(days=int(rng.integers(7, 60)))
            if resolved_at >= REFERENCE_DATE:
                resolved_at = None
            res_type = random.choice(["apology", "repair_completed", "policy_change", "no_action"])
        else:
            resolved_at = None
            res_type = None
        rows.append({
            "complaint_id": cid,
            "tenant_id": int(tenant_ids[i]),
            "citizen_id": citizen_ids[i],
            "primary_request_id": int(request_ids[i]),
            "filed_at": filed,
            "escalation_channel": ch,
            "complaint_narrative": narrative,
            "council_member_name": f"Council Member {random.choice(council_names)}",
            "resolved_at": resolved_at,
            "resolution_type": res_type,
        })
        cid += 1
    return pl.DataFrame(rows)


def gen_tenant_health_snapshots(
    df_tenants: pl.DataFrame,
    df_sr: pl.DataFrame,
    df_sla_breach: pl.DataFrame,
    df_complaints: pl.DataFrame,
    df_subs: pl.DataFrame,
    df_predictions: pl.DataFrame,
    df_events: pl.DataFrame,
) -> pl.DataFrame:
    """月度快照, 120 tenants × 36 months ≈ 4320 行。

    P1/P2 修复: reopen_rate 与 repeat_at_address_rate 改为真正"聚合自事实表"
    (reopen 来自 request_events 的 reopened 事件; repeat 来自同址 30 天内的下一条请求),
    不再是 sla_breach_rate 的合成线性函数, 因此 Q20 展示的这两列可由 Q14 / Q19 / Q3 复算。"""
    rows = []
    sid = 1

    # 预聚合: SR by (tenant, month)
    sr_with_month = df_sr.with_columns(
        pl.col("created_at").dt.truncate("1mo").alias("month")
    )
    counts_per = (
        sr_with_month.group_by(["tenant_id", "month"])
        .agg(pl.len().alias("request_count"))
        .sort(["tenant_id", "month"])
    )
    # breach by (tenant, month)
    breach_sr = df_sla_breach.join(
        df_sr.select(["request_id", "created_at"]), on="request_id"
    ).with_columns(pl.col("created_at").dt.truncate("1mo").alias("month"))
    breach_counts = (
        breach_sr.group_by(["tenant_id", "month"])
        .agg(pl.len().alias("breach_count"))
    )
    # complaint by (tenant, month)
    complaints_with_m = df_complaints.with_columns(
        pl.col("filed_at").cast(pl.Datetime).dt.truncate("1mo").alias("month")
    )
    complaint_counts = (
        complaints_with_m.group_by(["tenant_id", "month"])
        .agg(pl.len().alias("complaint_count"))
    )
    # accuracy by (tenant, month): predicted == ground_truth on audited subset
    pred_with_sr = df_predictions.join(
        df_sr.select(["request_id", "tenant_id", "created_at"]), on="request_id"
    ).with_columns(pl.col("created_at").dt.truncate("1mo").alias("month"))
    pred_audited = pred_with_sr.filter(pl.col("is_audited") == 1)
    accuracy_agg = (
        pred_audited.group_by(["tenant_id", "month"])
        .agg([
            pl.len().alias("audited_count"),
            (pl.col("predicted_category_id") == pl.col("ground_truth_category_id")).sum().alias("correct_count"),
        ])
    )

    # reopen_rate (事实聚合): closed 请求中"有 reopened 事件"的占比, 按 (tenant, 建单月) 分组。
    reopened_ids = (
        df_events.filter(pl.col("event_type") == "reopened")
        .select("request_id").unique()
        .with_columns(pl.lit(1).alias("has_reopen"))
    )
    sr_closed_m = (
        df_sr.filter(pl.col("closed_at").is_not_null())
        .select(["request_id", "tenant_id", "created_at"])
        .with_columns(pl.col("created_at").dt.truncate("1mo").alias("month"))
        .join(reopened_ids, on="request_id", how="left")
        .with_columns(pl.col("has_reopen").fill_null(0))
    )
    reopen_agg = (
        sr_closed_m.group_by(["tenant_id", "month"])
        .agg([
            pl.len().alias("closed_count"),
            pl.col("has_reopen").sum().alias("reopen_count"),
        ])
    )

    # repeat_at_address_rate (事实聚合): closed 且有地址的请求中, 同 address 30 天内出现下一条
    # 新请求的占比。按 address 排序后取下一条 created_at, 与本条 closed_at 比较。
    addr_repeat = (
        df_sr.filter(pl.col("address_id").is_not_null() & pl.col("closed_at").is_not_null())
        .select(["tenant_id", "address_id", "created_at", "closed_at"])
        .sort(["address_id", "created_at"])
        .with_columns(
            pl.col("created_at").shift(-1).over("address_id").alias("next_created"),
        )
        .with_columns(pl.col("created_at").dt.truncate("1mo").alias("month"))
        .with_columns(
            (
                pl.col("next_created").is_not_null()
                & ((pl.col("next_created") - pl.col("closed_at")).dt.total_days() >= 0)
                & ((pl.col("next_created") - pl.col("closed_at")).dt.total_days() <= 30)
            ).cast(pl.Int64).alias("is_repeat")
        )
    )
    repeat_agg = (
        addr_repeat.group_by(["tenant_id", "month"])
        .agg([
            pl.len().alias("addr_closed_count"),
            pl.col("is_repeat").sum().alias("repeat_count"),
        ])
    )

    # ai_insight 标志 by tenant
    ai_map = dict(zip(df_subs["tenant_id"].to_list(), df_subs["has_ai_insight_pack"].to_list()))

    # joined master
    master = counts_per.join(breach_counts, on=["tenant_id", "month"], how="left").with_columns(
        pl.col("breach_count").fill_null(0)
    )
    master = master.join(complaint_counts, on=["tenant_id", "month"], how="left").with_columns(
        pl.col("complaint_count").fill_null(0)
    )
    master = master.join(accuracy_agg, on=["tenant_id", "month"], how="left")
    master = master.join(reopen_agg, on=["tenant_id", "month"], how="left")
    master = master.join(repeat_agg, on=["tenant_id", "month"], how="left")

    # 仅保留 2023-06 到 2026-05 月份 (36 个月)
    master = master.filter(
        (pl.col("month") >= datetime(2023, 6, 1))
        & (pl.col("month") < datetime(2026, 6, 1))
    )

    for r in master.iter_rows(named=True):
        t_id = r["tenant_id"]
        rc = r["request_count"]
        bc = r["breach_count"]
        cc = r["complaint_count"]
        ac = r["audited_count"] if r["audited_count"] is not None else 0
        cor = r["correct_count"] if r["correct_count"] is not None else 0
        sla_rate = bc / rc if rc > 0 else 0.0
        # reopen_rate / repeat_rate: 真正聚合自事实表 (reopen 事件 / 同址 30 天复发)
        closed_cnt = r["closed_count"] if r["closed_count"] is not None else 0
        reopen_cnt = r["reopen_count"] if r["reopen_count"] is not None else 0
        addr_closed_cnt = r["addr_closed_count"] if r["addr_closed_count"] is not None else 0
        repeat_cnt = r["repeat_count"] if r["repeat_count"] is not None else 0
        reopen_rate = round(reopen_cnt / closed_cnt, 3) if closed_cnt > 0 else 0.0
        repeat_rate = round(repeat_cnt / addr_closed_cnt, 3) if addr_closed_cnt > 0 else 0.0
        accuracy = round(cor / ac, 3) if ac > 0 and ai_map.get(t_id, 0) == 1 else None
        escal_rate = round(cc / rc, 4) if rc > 0 else 0.0
        # NPS proxy: 重标定使 churn_risk_band 在平台内有真实三档分布 (不再几乎全 medium)。
        #   nps = 130 - 450*sla - 250*escal - 80*reopen, 裁剪 [-100, 100]。
        #   sla 主导: sla<~0.21 -> nps>=30 low; 0.21~0.275 -> medium; >~0.275 -> nps<0 high。
        #   于是健康低 drift 城 (Austin, sla~0.20) 偏 low, 高 drift 城 (Quebec, sla~0.28) 偏 high。
        nps = int(130 - 450 * sla_rate - 250 * escal_rate - 80 * reopen_rate)
        nps = max(-100, min(100, nps))
        if nps < 0:
            band = "high"
        elif nps < 30:
            band = "medium"
        else:
            band = "low"
        rows.append({
            "snapshot_id": sid,
            "tenant_id": t_id,
            "snapshot_month": r["month"].date() if hasattr(r["month"], "date") else r["month"],
            "request_count": int(rc),
            "sla_breach_rate": round(sla_rate, 3),
            "reopen_rate": reopen_rate,
            "repeat_at_address_rate": repeat_rate,
            "classifier_accuracy": accuracy,
            "council_escalation_rate": escal_rate,
            "nps_score": nps,
            "churn_risk_band": band,
        })
        sid += 1
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def generate_all_tsv() -> None:
    """生成所有 TSV 文件, 按拓扑顺序写到 data/。先清空旧文件。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.glob("*.tsv"):
        f.unlink()

    print("Generating intake_channels ...")
    df_channels = gen_intake_channels()
    df_channels.write_csv(DATA_DIR / "01_intake_channels.tsv", separator="\t")

    print("Generating service_categories ...")
    df_categories = gen_service_categories()
    df_categories.write_csv(DATA_DIR / "02_service_categories.tsv", separator="\t")

    print("Generating tenants ...")
    df_tenants = gen_tenants()
    df_tenants.write_csv(DATA_DIR / "03_tenants.tsv", separator="\t")

    print("Generating tenant_subscriptions ...")
    df_subs = gen_tenant_subscriptions(df_tenants)
    df_subs.write_csv(DATA_DIR / "04_tenant_subscriptions.tsv", separator="\t")

    print("Generating departments ...")
    df_departments = gen_departments(df_tenants)
    df_departments.write_csv(DATA_DIR / "05_departments.tsv", separator="\t")

    print("Generating sla_policies ...")
    df_sla = gen_sla_policies(df_tenants, df_categories)
    df_sla.write_csv(DATA_DIR / "06_sla_policies.tsv", separator="\t")

    print("Generating category_dept_routing ...")
    df_routing = gen_category_dept_routing(df_tenants, df_categories, df_departments)
    df_routing.write_csv(DATA_DIR / "07_category_dept_routing.tsv", separator="\t")

    print("Generating citizens ...")
    df_citizens = gen_citizens(df_tenants)
    df_citizens.write_csv(DATA_DIR / "08_citizens.tsv", separator="\t")

    print("Generating addresses ...")
    df_addresses = gen_addresses(df_tenants)
    df_addresses.write_csv(DATA_DIR / "09_addresses.tsv", separator="\t")

    print("Generating assets ...")
    df_assets = gen_assets(df_tenants, df_addresses)
    df_assets.write_csv(DATA_DIR / "10_assets.tsv", separator="\t")

    print("Generating staff_users ...")
    df_staff = gen_staff_users(df_tenants, df_departments)
    df_staff.write_csv(DATA_DIR / "11_staff_users.tsv", separator="\t")

    print("Generating field_crews ...")
    df_crews = gen_field_crews(df_tenants, df_departments)
    df_crews.write_csv(DATA_DIR / "12_field_crews.tsv", separator="\t")

    print("Generating service_requests (1M, may take 30s) ...")
    df_sr, hidden = gen_service_requests(
        df_tenants, df_categories, df_departments, df_addresses, df_assets, df_citizens
    )
    df_sr.write_csv(DATA_DIR / "13_service_requests.tsv", separator="\t")

    print("Generating request_descriptions (1M, may take 60s) ...")
    df_desc = gen_request_descriptions(df_sr, hidden)
    df_desc.write_csv(DATA_DIR / "14_request_descriptions.tsv", separator="\t")

    print("Generating request_events ...")
    df_events = gen_request_events(df_sr, df_staff, hidden)
    df_events.write_csv(DATA_DIR / "15_request_events.tsv", separator="\t")

    print("Generating request_assignments ...")
    df_assign = gen_request_assignments(df_sr, df_staff, df_crews)
    df_assign.write_csv(DATA_DIR / "16_request_assignments.tsv", separator="\t")

    print("Generating request_attachments ...")
    df_attach = gen_request_attachments(df_sr)
    df_attach.write_csv(DATA_DIR / "17_request_attachments.tsv", separator="\t")

    print("Generating work_orders ...")
    df_wo = gen_work_orders(df_sr, df_staff, df_crews)
    df_wo.write_csv(DATA_DIR / "18_work_orders.tsv", separator="\t")

    print("Generating work_order_notes ...")
    df_notes = gen_work_order_notes(df_wo, df_staff)
    df_notes.write_csv(DATA_DIR / "19_work_order_notes.tsv", separator="\t")

    print("Generating model_predictions ...")
    df_pred = gen_model_predictions(df_sr, hidden, df_categories)
    df_pred.write_csv(DATA_DIR / "20_model_predictions.tsv", separator="\t")

    print("Generating sla_breach_log ...")
    df_breach = gen_sla_breach_log(df_sr, df_sla, hidden)
    df_breach.write_csv(DATA_DIR / "21_sla_breach_log.tsv", separator="\t")

    print("Generating citizen_complaints ...")
    df_compl = gen_citizen_complaints(df_sr, hidden)
    df_compl.write_csv(DATA_DIR / "22_citizen_complaints.tsv", separator="\t")

    print("Generating tenant_health_snapshots ...")
    df_snap = gen_tenant_health_snapshots(df_tenants, df_sr, df_breach, df_compl, df_subs, df_pred, df_events)
    df_snap.write_csv(DATA_DIR / "23_tenant_health_snapshots.tsv", separator="\t")

    print(f"All TSVs written to {DATA_DIR}")


def create_sqlite_database() -> None:
    """用 Core API batch loader 写入 SQLite, 先删旧文件再建。"""
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    engine = create_engine(f"sqlite:///{DATABASE_PATH}")
    Base.metadata.create_all(engine)

    load_order: list[tuple[str, "object"]] = [
        ("01_intake_channels", IntakeChannel.__table__),
        ("02_service_categories", ServiceCategory.__table__),
        ("03_tenants", Tenant.__table__),
        ("04_tenant_subscriptions", TenantSubscription.__table__),
        ("05_departments", Department.__table__),
        ("06_sla_policies", SLAPolicy.__table__),
        ("07_category_dept_routing", CategoryDeptRouting.__table__),
        ("08_citizens", Citizen.__table__),
        ("09_addresses", Address.__table__),
        ("10_assets", Asset.__table__),
        ("11_staff_users", StaffUser.__table__),
        ("12_field_crews", FieldCrew.__table__),
        ("13_service_requests", ServiceRequest.__table__),
        ("14_request_descriptions", RequestDescription.__table__),
        ("15_request_events", RequestEvent.__table__),
        ("16_request_assignments", RequestAssignment.__table__),
        ("17_request_attachments", RequestAttachment.__table__),
        ("18_work_orders", WorkOrder.__table__),
        ("19_work_order_notes", WorkOrderNote.__table__),
        ("20_model_predictions", ModelPrediction.__table__),
        ("21_sla_breach_log", SLABreachLog.__table__),
        ("22_citizen_complaints", CitizenComplaint.__table__),
        ("23_tenant_health_snapshots", TenantHealthSnapshot.__table__),
    ]

    # 每个 TSV 文件需要强制为字符串的列 (避免 polars 把 US zip 5 位数字
    # 误猜成 int, 进而拒绝接受像 "V9O 2E3" 这样的加拿大邮编)。
    schema_overrides_per_file: dict[str, dict[str, type]] = {
        "08_citizens": {"phone": pl.String, "citizen_external_id": pl.String},
        "09_addresses": {"postal_code": pl.String, "street_address": pl.String},
        "10_assets": {"asset_external_id": pl.String},
        "11_staff_users": {"email": pl.String},
        "12_field_crews": {"crew_code": pl.String},
    }

    with engine.begin() as conn:
        for tsv_name, table in load_order:
            tsv_path = DATA_DIR / f"{tsv_name}.tsv"
            if not tsv_path.exists():
                print(f"Skip {tsv_name}: file missing")
                continue
            overrides = schema_overrides_per_file.get(tsv_name, {})
            df = pl.read_csv(
                tsv_path,
                separator="\t",
                try_parse_dates=True,
                infer_schema_length=10000,
                schema_overrides=overrides,
            )
            rows = df.to_dicts()
            if rows:
                # 分批插入避免单语句过大
                BATCH = 50_000
                for start in range(0, len(rows), BATCH):
                    conn.execute(table.insert(), rows[start:start + BATCH])
            print(f"Loaded {tsv_name}: {len(rows)} rows")

    print(f"Created SQLite database at {DATABASE_PATH}")


def main() -> None:
    print("Starting CityPulse 311 dataset generation ...")
    start = datetime.now()
    generate_all_tsv()
    create_sqlite_database()
    elapsed = (datetime.now() - start).total_seconds()
    print(f"All done in {elapsed:.1f} seconds.")


if __name__ == "__main__":
    main()
