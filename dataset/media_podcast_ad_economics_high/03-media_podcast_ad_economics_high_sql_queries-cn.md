# 媒体行业 - 播客广告经济学 SQL 查询参考

> **业务背景 / 行业科普 / 术语表 / 指标公式:** `01-media_podcast_ad_economics_high_business_context-cn.md` (建议先读完它再来看 SQL)
> **数据结构 / ER 图 / DDL:** `02-media_podcast_ad_economics_high_er_document-cn.md`
> **数据库:** `media_podcast_ad_economics_high.sqlite`
> **SQL 方言:** SQLite 3.x
> **参考"今天" (REFERENCE_DATE):** 2026-06-21 (所有查询用字面日期 `'2026-06-21'`,不用 `DATE('now')`,保证可复现)

---

## 给实习生的话:这份文档怎么用

你是 StreamCast Media 公司 Revenue Operations 团队的 **数据分析师实习生**。你的导师告诉你:**"这 27 条 SQL 是你未来 3 个月会反复用到的'肌肉记忆',抄熟、改熟、看懂背后的业务,你就出师了。"**

每条查询都有**五块内容**,**请按这个顺序读**:

1. **业务背景 (Business Context)** — **先读这个**!理解"谁在问这个问题、为什么问、想拿数据干什么"。不理解业务,只看 SQL 就是无意义的字符。
2. **业务知识科普 / 分类难度角色** — 对含义不直观的指标补充行业常识,并标注 SQL 类别、难度、业务角色。
3. **解题思路 (Approach)** — **看 SQL 之前先看这个**。它告诉你:要 JOIN 哪些表、聚合粒度 (一行代表什么)、有哪些坑要避 (双重计数 / 该用 LEFT JOIN / 除零 / 多值定向匹配),以及为什么这里用 CTE 或窗口函数。把思路想清楚再看代码,SQL 就不再是天书。
4. **SQL 代码** — 实际可跑的 SQL (SQLite 方言)。
5. **结果解读 + 业务结论** — 拿到数据后哪些数字是"健康"、哪些是"红色警报",以及下一步该采取什么动作。

> ⚠️ **重要提醒:** 这些查询里的数据是 fake 的,所以跑出来的具体数值不会和真实业务完全一致。**请重点学方法论,不要死记数值。**

---

## 公司背景速通 (3 分钟版)

如果你忘了 ER 文档里的背景,这里再快速复习一下:

- **StreamCast Media** 是美国的播客广告平台,服务 150+ 档播客节目
- **怎么赚钱:** 广告主在节目里塞 pre-roll/mid-roll/post-roll 广告 → 平台抽 30% → 主播拿 70%
- **核心机制:** 听众每次播放节目,实时拍卖广告位 (RTB) → 第二价格成交 (Vickrey Auction)
- **三方利益:** 平台要 fill rate 高、CPM 高;广告主要 CPA 低、ROI 高;主播要 RPM 高
- **核心矛盾:** 多塞广告赚得多 vs 听众体验变差

**核心指标速记:**
- **CPM** = 千次曝光成本 (广告主付的单价)
- **RPM** = 千次播放收入 (主播净赚的单价)
- **Fill Rate** = 广告位填充率
- **Completion Rate** = 广告完播率
- **CPA** = 单次获客成本

---

## 27 条查询索引

按 6 大业务主题分类。

### 主题 A:平台收入优化 (Revenue Optimization)

> 关注人:平台运营、销售策略团队、CFO
> 核心问题:怎么把广告卖出更高的总价?

| # | 标题 | 角色 | 难度 |
|---|------|------|------|
| 1 | 按广告位类型分析表现 | 平台运营 | 中级 |
| 2 | 高峰 vs 低谷时段填充率分析 | 平台分析 | 高级 |
| 3 | 高价值听众标签的 CPM 排行 | 平台策略 | 中级 |
| 4 | 按一周中不同日子的库存利用率 | 平台运营 | 中级 |
| 5 | 广告主预算消耗预警 | 平台销售 | 高级 |
| 6 | 被低估的广告位识别 | 平台策略 | 高级 |

### 主题 B:广告主 ROI (Advertiser ROI)

> 关注人:广告主、客户经理 (AE)
> 核心问题:广告主的钱花得值不值?

| # | 标题 | 角色 | 难度 |
|---|------|------|------|
| 7 | 单 campaign 的 ROI 仪表盘 | 广告主 | 中级 |
| 8 | 广告素材表现对比 (A/B 测试) | 广告主 | 高级 |
| 9 | 人群定向有效性分析 | 广告主 | 高级 |
| 10 | 出价金额 vs 赢拍率的关联 | 广告主 | 中级 |
| 11 | 单次完整收听成本 (CPCV) 分析 | 广告主 | 中级 |
| 12 | 竞争对手出价行为洞察 | 广告主 | 高级 |

### 主题 C:主播变现 (Creator Monetization)

> 关注人:播客主播、平台内容合作 BD
> 核心问题:主播能赚多少?怎么赚更多?

| # | 标题 | 角色 | 难度 |
|---|------|------|------|
| 13 | 按节目类型的 RPM 对标 | 主播 | 中级 |
| 14 | 单集表现深度分析 | 主播 | 中级 |
| 15 | 主播月度营收趋势分析 | 主播 | 高级 |
| 16 | 内容优化建议 (时长/发布日) | 主播 | 高级 |

### 主题 D:听众体验 (Listener Experience)

> 关注人:平台用户体验 (UX) 团队、留存团队
> 核心问题:别把听众气走!

| # | 标题 | 角色 | 难度 |
|---|------|------|------|
| 17 | 广告疲劳侦测 (Ad Fatigue) | 平台 UX | 高级 |
| 18 | 按素材属性分析跳过率 | 平台 UX | 中级 |
| 19 | 最优广告频次推荐 | 平台 UX | 高级 |
| 20 | 听众标签满意度评分 | 平台 UX | 高级 |

### 主题 E:拍卖市场动态 (Auction Dynamics)

> 关注人:平台拍卖系统、定价策略团队
> 核心问题:拍卖机制运转得健康吗?

| # | 标题 | 角色 | 难度 |
|---|------|------|------|
| 21 | 拍卖竞争激烈度热力图 | 平台分析 | 高级 |
| 22 | 第二价格拍卖机制效率验证 | 平台分析 | 中级 |
| 23 | 预算调配 (Pacing) 有效性 | 平台分析 | 高级 |
| 24 | 出价调整的弹性分析 | 平台分析 | 高级 |

### 主题 F:战略洞察 (Strategic Insights)

> 关注人:平台高层、战略团队
> 核心问题:下一个季度押注哪里?

| # | 标题 | 角色 | 难度 |
|---|------|------|------|
| 25 | 新兴广告主行业趋势 | 平台策略 | 中级 |
| 26 | 节目分类增长预测 | 平台策略 | 高级 |
| 27 | 听众行为变化侦测 | 平台策略 | 高级 |

---

# 查询正文

---

## Query 1: 按广告位类型分析表现

**业务背景:**
StreamCast 的 VP of Monetization (变现副总裁) 需要为 Q2 的定价策略做支撑。**业内"公认"** mid-roll 广告位最值钱 (完播率高 → 广告主更想买),所以基础 CPM 定的是 pre-roll 的 1.67 倍 ($25 vs $15)。但 VP 怀疑实际市场可能比官方定价更"看好" mid-roll — 也就是说 **底价是不是定低了?** 这条查询比较 pre/mid/post-roll 三种广告位的真实成交均价、完播率、跳过率,用数据回答这个定价问题。

**业务知识:**
- **底价 (Base CPM):** 平台对每种广告位设定的"最低起拍价",广告主出价不得低于此
- **实际成交价 (eCPM, effective CPM):** 经过实际拍卖后的真实平均售价
- 如果 **eCPM 显著 > Base CPM**,说明市场实际愿付远高于底价,**平台留了钱在桌上** (= 该提价)

**分类:** Revenue Optimization
**难度:** 中级
**业务角色:** 平台运营

**解题思路:**
触三张表 `ad_slot_template → episode_ad_slot → ad_impression`,按广告位模板聚合。这里用 INNER JOIN 即可,因为只关心"已经成交的曝光"(没成交的位不在分析范围)。要记住 `ad_impression` 是**事件级表**——一行 = 一次曝光,所以 `COUNT/AVG` 的聚合粒度是"曝光",`GROUP BY` 到 slot 模板就把 pre/mid/post 三类各汇成一行。完播率、跳过率用 `SUM(CASE WHEN 布尔 THEN 1 ELSE 0 END) / COUNT(*)` 算占比。不需要 CTE 或窗口函数,一次 `GROUP BY` 搞定。分析重点是对比 `avg_realized_cpm`(实际成交价) 与 `base_cpm_rate`(底价) 的差距。

```sql
-- 对比三种广告位的实际市场表现
SELECT
    ast.slot_type,
    ast.slot_name,
    ast.base_cpm_rate AS current_base_cpm,
    COUNT(ai.id) AS total_impressions,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_realized_cpm,
    ROUND(AVG(ai.winning_bid_cpm), 2) AS avg_winning_bid,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS skip_rate_pct,
    ROUND(AVG(ai.ad_duration_played_sec), 1) AS avg_duration_played_sec,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_revenue_usd
FROM ad_slot_template ast
JOIN episode_ad_slot eas ON ast.id = eas.slot_template_id
JOIN ad_impression ai ON eas.id = ai.ad_slot_id
GROUP BY ast.id, ast.slot_type, ast.slot_name, ast.base_cpm_rate
ORDER BY avg_realized_cpm DESC;
```

**结果解读:**
返回 3 行 (每种广告位一行)。**预期看到 (本数据集实际量级):**
- **Mid-roll** eCPM ~$31-34(约为底价 $25 的 +25~35%),完播率高 → 验证 "mid-roll 最贵",且明显有提价空间
- **Pre-roll** eCPM ~$18-20,完播率较高 → 略高于底价 $15,表现稳定
- **Post-roll** eCPM ~$9-10,完播率最低 → 触达低,贴近底价 $8

**如何向业务方汇报:** "Mid-roll 实际成交已比底价高约 30%,建议把底价从 $25 上调到 $30 左右提升整体收入。Post-roll 贴近底价、表现符合预期,不动。"

---

## Query 2: 高峰 vs 低谷时段填充率分析

**业务背景:**
运营经理发现 **凌晨/深夜的广告位很多空着没卖出去** (即 fill rate 低),意味着 **库存浪费 = 收入损失**。同时,广告主天天抱怨白天高峰时段 CPM 太贵抢不到。她想知道:**有没有可能通过"动态定价" (Dynamic Pricing) — 凌晨降低 CPM 底价,吸引中小广告主来填补空缺?** 这条查询按一天 24 小时分别看 fill rate,识别低利用时段的潜在收入空间。

**业务知识:**
- **Fill Rate (填充率)** = 实际卖出广告的次数 ÷ 可用广告位次数
- 健康 fill rate ≥ 90%。低于 70% 意味着大量库存被浪费
- **动态定价** 在 Google AdSense、Meta 广告平台都是核心策略 — 高峰高价,低谷打折

**分类:** Revenue Optimization
**难度:** 高级
**业务角色:** 平台分析

**解题思路:**
这题要算"被听到的广告位里成交了多少",分母和分子要分开搭。先用 `play_session → podcast_episode → episode_ad_slot` 三表 JOIN 出"会话×广告位对"作为**分母** (每个被收听到的广告位一行),再 `LEFT JOIN ad_impression`(带 `ai.play_session_id = ps.id` 的连接条件) 作为**分子**。**这里的 LEFT JOIN 不能换成 INNER JOIN**,否则没成交的广告位会被剔除、fill rate 永远是 100%。用 CTE `hourly_potential` 先按小时 (`strftime('%H', ...)`) 聚合,外层再贴 demand_tier 分档和"拉到 90% 能多赚多少"的估算。grain = 一小时一行,共 24 行。

```sql
-- 按一天的小时分析填充率和收入,识别低谷时段机会
WITH hourly_potential AS (
    SELECT
        CAST(strftime('%H', ps.session_start_time) AS INTEGER) AS hour_of_day,
        -- 分母是"会话-广告位对"(每个被收听的广告位一行), 不是去重后的广告位定义数,
        -- 否则一个广告位被 N 个会话播放会让 fill_rate 远超 100%。
        COUNT(eas.id) AS total_slots_available,
        COUNT(ai.id) AS slots_filled,
        ROUND(100.0 * COUNT(ai.id) / COUNT(eas.id), 1) AS fill_rate_pct,
        ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS revenue_generated
    FROM play_session ps
    JOIN podcast_episode pe ON ps.episode_id = pe.id
    JOIN episode_ad_slot eas ON pe.id = eas.episode_id
    LEFT JOIN ad_impression ai ON eas.id = ai.ad_slot_id
        AND ai.play_session_id = ps.id
    GROUP BY hour_of_day
)
SELECT
    hour_of_day,
    total_slots_available,
    slots_filled,
    (total_slots_available - slots_filled) AS unfilled_slots,
    fill_rate_pct,
    avg_cpm,
    revenue_generated,
    CASE
        WHEN fill_rate_pct < 70 THEN 'Off-Peak (低填充)'
        WHEN fill_rate_pct >= 70 AND fill_rate_pct < 85 THEN 'Moderate (中等)'
        ELSE 'Peak (高需求)'
    END AS demand_tier,
    -- 估算:如果 fill rate 提到 90%,能多赚多少
    ROUND((total_slots_available * 0.90 - slots_filled) * (avg_cpm / 1000.0), 2) AS potential_revenue_gain
FROM hourly_potential
ORDER BY hour_of_day;
```

**结果解读:**
返回 24 行。这里的 fill_rate 是 "**被听到的广告位中,实际成交了广告的比例**"(分母是会话-广告位对,故恒 ≤ 100%):
- **高峰时段** (早 7-9 点通勤、午 12-1 点午饭、晚 6-10 点) → fill rate 相对高,CPM 也更高
- **低谷时段** (凌晨 1-5 点) → fill rate 偏低,库存空置更多
- `potential_revenue_gain` 是 **最关键的列** — 它估算把低谷时段 fill rate 拉到 90% 后能多赚多少
- ⚠️ 注意:很多 mid/post-roll 因为听众没听到那里而未被触达,所以整体 fill rate 看起来不会是满的 — 这正是"播放进度决定库存"的体现

**业务建议:** "建议凌晨 1-5 点把 CPM 底价下调 20-30%,吸引电商类对预算敏感的广告主进场。估算月增收 $XX,XXX。"

---

## Query 3: 高价值听众标签的 CPM 排行

**业务背景:**
销售总监要准备 Q2 给 SaaS、FinTech 行业广告主的 pitch deck (推销案)。他需要数据证明:**"我们平台的 Tech_Enthusiast 听众标签是真值钱的"** — 不是空口白话。这条查询按听众标签 (segment) 排序 CPM,直接拿数据告诉广告主"想要这类高质量受众,你得多出钱"。

**业务知识:**
- **Listener Segment (听众标签):** 平台基于收听历史给听众打的兴趣标签 (如 Tech_Enthusiast / Health_Conscious)
- **Premium Audience (高价值受众):** 这些人群因为购买力强、转化率高,广告主愿意为他们多付钱
- **Programmatic Guaranteed (PG):** 平台和大广告主直签的"定向人群保底量" — 不走开放拍卖,固定价

**分类:** Revenue Optimization
**难度:** 中级
**业务角色:** 平台策略

**解题思路:**
链路 `listener_segment → listener → play_session → ad_impression`,按 `segment_name` 聚合。**要清楚一个坑**:一个听众可同时有 1-3 个标签,JOIN 后同一次曝光会在它所属的每个标签下各计一次——这是**有意为之**(衡量"这类人群的广告值多少钱"),但意味着 `total_impressions` 是"标签维度"的计数,不是去重曝光。听众数用 `COUNT(DISTINCT l.id)` 去重,避免被标签数放大。`HAVING total_impressions >= 100` 过滤掉样本太小的标签,`ORDER BY avg_cpm DESC` 排出最值钱人群。

```sql
-- 按听众标签排出最赚钱的人群
SELECT
    ls.segment_name,
    COUNT(DISTINCT l.id) AS listener_count,
    COUNT(ai.id) AS total_impressions,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
    ROUND(AVG(ai.winning_bid_cpm), 2) AS avg_winning_bid,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_revenue_generated,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / COUNT(DISTINCT l.id), 2) AS revenue_per_listener
FROM listener_segment ls
JOIN listener l ON ls.listener_id = l.id
JOIN play_session ps ON l.id = ps.listener_id
JOIN ad_impression ai ON ps.id = ai.play_session_id
GROUP BY ls.segment_name
HAVING total_impressions >= 100  -- 至少 100 次曝光才有统计意义
ORDER BY avg_cpm DESC
LIMIT 15;
```

**结果解读:**
- **Tech_Enthusiast** 和 **Finance_Savvy** → CPM $25-35 (SaaS/FinTech 死磕)
- **Fitness_Oriented** 和 **Health_Conscious** → CPM $20-28 (健康消费品牌追)
- `revenue_per_listener` 告诉销售:"每个 Tech_Enthusiast 听众一年给我们贡献 $X,所以拓展这类听众的 CAC 上限是 $X * 留存年数"

---

## Query 4: 按一周中不同日子的库存利用率

**业务背景:**
库存规划团队想弄清楚 **"周末广告主为什么不买?"** 听众周末听播客的量并没减少,但 fill rate 显著低于工作日 (~80% vs 95%)。是不是该周末搞促销?这条查询输出工作日/周末的对比,为定价和销售策略提供依据。

**业务知识:**
- **B2B 广告主** 偏好工作日投放 (因为他们的目标客户是商务人士,周末"心不在工作上")
- **零售 / 电商** 通常周一到周三买广告,因为消费者周末购物决策周四前才下单
- **周末空置库存** 给到 DTC (Direct-to-Consumer) 品牌反而是机会

**分类:** Revenue Optimization
**难度:** 中级
**业务角色:** 平台运营

**解题思路:**
和 Query 2 同构,只是把分组维度从"小时"换成"星期几" (`strftime('%w', ...)`,返回 0=周日)。同样用 `play_session → episode_ad_slot` 出"会话-广告位对"作分母、`LEFT JOIN ad_impression` 作分子,**LEFT JOIN 不能换 INNER**。用 `CASE strftime('%w')` 把数字映射成英文星期名便于阅读,但 `GROUP BY` 要用数字 `day_num` (字符串名排序不对)。grain = 一周 7 天各一行。分析重点是看工作日 vs 周末的 fill rate 落差。

```sql
-- 按一周天数分析填充率、CPM 和收入
SELECT
    CASE CAST(strftime('%w', ps.session_start_time) AS INTEGER)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_of_week,
    CAST(strftime('%w', ps.session_start_time) AS INTEGER) AS day_num,
    -- 同 Query 2: 分母用"会话-广告位对", 避免去重成广告位定义数导致 >100%
    COUNT(eas.id) AS total_slots,
    COUNT(ai.id) AS filled_slots,
    ROUND(100.0 * COUNT(ai.id) / COUNT(eas.id), 1) AS fill_rate_pct,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_revenue,
    COUNT(DISTINCT ps.listener_id) AS unique_listeners
FROM play_session ps
JOIN episode_ad_slot eas ON ps.episode_id = eas.episode_id
LEFT JOIN ad_impression ai ON eas.id = ai.ad_slot_id AND ps.id = ai.play_session_id
GROUP BY day_num
ORDER BY day_num;
```

**结果解读:**
- 周一到周四 fill rate 85-95%,周末 70-80% → 周末库存浪费明显
- **建议:** 周六给 15% CPM 折扣,吸引零售/电商广告主"周末促销前抢量"

---

## Query 5: 广告主预算消耗预警

**业务背景:**
**客户经理 (AE) 的核心 KPI 是续约率。** 如果一个广告主的预算快烧完了,AE 必须 **提前 3 天** 主动出击聊续费/加预算,否则 campaign 自动暂停 → 平台损失收入 + 广告主流失。这条查询每天凌晨跑,自动生成 AE 工作清单。

**业务知识:**
- **Account Manager (客户经理 AE):** 负责一组重点广告主的续约和增长
- **Renewal (续费):** 老客户再签
- **Upsell (加单):** 老客户加预算
- **Pacing Burn Rate:** 预算消耗速率,通常按"日均花费"算

**分类:** Revenue Optimization
**难度:** 高级
**业务角色:** 平台销售

**解题思路:**
链路 `ad_campaign → advertiser`,再 `LEFT JOIN ad_creative → ad_impression` 累加每个 campaign 的实际花费 (`SUM(actual_charge_cpm)/1000`)。**最关键的坑:预算要用 `window_budget_usd` 而不是 `total_budget_usd`**——后者是广告主级大额承诺,在 60 天采样下花费仅几十美元、剩余可烧上万天,会导致整查询返回空集、永不告警。用 CTE `campaign_spending` 先把花费、日均花费、剩余预算算出来,外层再算 `days_until_exhaustion = 剩余 / 日均` 并分级。`WHERE end_date >= '2026-06-21'` 只看活跃 campaign,再筛 7 天内将耗尽的。grain = 一个 campaign 一行。

```sql
-- 识别预算即将耗尽的 campaign (3 天内有暂停风险)
-- 用 window_budget_usd (本 60 天窗口实际部署的预算, 与真实交付同量级),
-- 而非 total_budget_usd (广告主级的大额承诺) — 否则单 campaign 花费仅几十美元 → days_until_exhaustion 高达上万天 → 永不告警、整查询返回空集。
WITH campaign_spending AS (
    SELECT
        ac.id AS campaign_id,
        ac.campaign_name,
        a.company_name,
        a.account_manager_email,
        ac.window_budget_usd,
        ac.end_date,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS spent_to_date,
        ROUND(ac.window_budget_usd - SUM(ai.actual_charge_cpm / 1000.0), 2) AS remaining_budget,
        COUNT(ai.id) AS total_impressions,
        ROUND(COUNT(ai.id) * 1.0 /
            NULLIF((JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date)), 0), 0) AS avg_daily_impressions,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) /
            NULLIF((JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date)), 0), 2) AS avg_daily_spend
    FROM ad_campaign ac
    JOIN advertiser a ON ac.advertiser_id = a.id
    LEFT JOIN ad_creative acr ON ac.id = acr.campaign_id
    LEFT JOIN ad_impression ai ON acr.id = ai.creative_id
    WHERE ac.end_date >= DATE('2026-06-21')  -- 只看活跃 campaign
    GROUP BY ac.id, ac.campaign_name, a.company_name, a.account_manager_email, ac.window_budget_usd, ac.end_date
)
SELECT
    campaign_name,
    company_name,
    account_manager_email,
    window_budget_usd,
    spent_to_date,
    remaining_budget,
    ROUND(100.0 * spent_to_date / window_budget_usd, 1) AS budget_used_pct,
    avg_daily_spend,
    ROUND(remaining_budget / NULLIF(avg_daily_spend, 0), 1) AS days_until_exhaustion,
    CASE
        WHEN remaining_budget / NULLIF(avg_daily_spend, 0) <= 1 THEN '🚨 紧急:不足 1 天'
        WHEN remaining_budget / NULLIF(avg_daily_spend, 0) <= 3 THEN '🔴 高优先:1-3 天'
        WHEN remaining_budget / NULLIF(avg_daily_spend, 0) <= 7 THEN '🟡 中优先:3-7 天'
        ELSE '🟢 低优先:>7 天'
    END AS urgency_level
FROM campaign_spending
WHERE remaining_budget > 0
    AND remaining_budget / NULLIF(avg_daily_spend, 0) <= 7
ORDER BY days_until_exhaustion ASC;
```

**结果解读:**
- **🚨 紧急** 类需要 AE 当天电话,否则明天就暂停
- **🔴 高优先** 是最理想的 upsell 机会 — 客户已经看到效果数据,还没体验到预算约束
- 预算/花费用的是 `window_budget_usd`(本 60 天窗口部署的预算),与实际交付同量级,故绝对值偏小是正常的;**重点看 `budget_used_pct` 与 `days_until_exhaustion`**。
- **业务话术(示例):** "您这条 campaign 的窗口预算已消耗 ~90%,按当前日均花费约 1-2 天就跑完。ROI 数据不错,建议现在追加预算延长投放。"

---

## Query 6: 被低估的广告位识别

**业务背景:**
定价策略团队怀疑某些热门节目的广告位 **底价定低了**。判断逻辑:如果一个广告位每次都有 8-10 个广告主竞价、赢拍价是底价的 2 倍,说明市场远远愿意付更多 → 该提底价。这条查询找出"实际成交价 / 底价"比例最高的广告位,作为提价候选。

**业务知识:**
- **Pricing Gap (定价缺口):** 实际成交价 - 底价。缺口越大说明底价定低了
- **Bidders per Auction (单场参与者):** 越多说明竞争越激烈
- **Floor Price Lift (底价上调):** 提高底价能直接拉升赢拍价,因为出价低于底价的会被自动剔除

**分类:** Revenue Optimization
**难度:** 高级
**业务角色:** 平台策略

**解题思路:**
这题有个**双重计数陷阱**:曝光级指标 (eCPM、曝光数) 如果直接 JOIN `ad_auction_log`,会被"每次曝光 2-6 条出价"放大 2-6 倍。所以拆成两个 CTE:`imp_stats` 只在 `podcast → ... → ad_impression` 链路上算 eCPM / 曝光数 (不碰拍卖日志),`bid_stats` 单独在 `ad_auction_log` 上算每场平均出价者数,最后按 `(podcast_id, slot_template_id)` 把两个 CTE JOIN 起来。grain = 节目 × 广告位类型。`HAVING COUNT(ai.id) >= 50` 过滤小样本,按低估幅度 (`underpriced_pct`) 排序取 top 20。

```sql
-- 识别实际 CPM 远超底价的广告位
-- 关键: 曝光级指标 (imp_stats) 不 JOIN 拍卖日志, 拍卖级指标 (bid_stats) 单独算,
-- 否则 ad_auction_log 每曝光 2-6 行会把 total_impressions / missed_revenue 虚增 2-6 倍。
WITH imp_stats AS (
    SELECT
        p.id AS podcast_id,
        p.podcast_name,
        p.category,
        ast.id AS slot_template_id,
        ast.slot_type,
        ast.base_cpm_rate,
        COUNT(ai.id) AS total_impressions,
        ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_realized_cpm,
        ROUND(AVG(ai.winning_bid_cpm), 2) AS avg_winning_bid
    FROM podcast p
    JOIN podcast_episode pe ON p.id = pe.podcast_id
    JOIN episode_ad_slot eas ON pe.id = eas.episode_id
    JOIN ad_slot_template ast ON eas.slot_template_id = ast.id
    JOIN ad_impression ai ON eas.id = ai.ad_slot_id
    GROUP BY p.id, p.podcast_name, p.category, ast.id, ast.slot_type, ast.base_cpm_rate
    HAVING COUNT(ai.id) >= 50
),
bid_stats AS (
    SELECT
        pe.podcast_id,
        eas.slot_template_id,
        COUNT(aal.id) * 1.0 / COUNT(DISTINCT aal.impression_id) AS avg_bidders_per_auction
    FROM ad_auction_log aal
    JOIN ad_impression ai ON aal.impression_id = ai.id
    JOIN episode_ad_slot eas ON ai.ad_slot_id = eas.id
    JOIN podcast_episode pe ON eas.episode_id = pe.id
    GROUP BY pe.podcast_id, eas.slot_template_id
)
SELECT
    s.podcast_name,
    s.category,
    s.slot_type,
    s.base_cpm_rate AS current_floor,
    s.avg_realized_cpm,
    s.avg_winning_bid,
    ROUND(b.avg_bidders_per_auction, 1) AS avg_bidders_per_auction,
    ROUND((s.avg_realized_cpm - s.base_cpm_rate), 2) AS pricing_gap,
    ROUND(100.0 * (s.avg_realized_cpm - s.base_cpm_rate) / s.base_cpm_rate, 1) AS underpriced_pct,
    ROUND((s.avg_realized_cpm - s.base_cpm_rate) * s.total_impressions / 1000.0, 2) AS missed_revenue_usd,
    CASE
        WHEN s.avg_realized_cpm > s.base_cpm_rate * 1.5 THEN '🚨 严重低估:提价 30-50%'
        WHEN s.avg_realized_cpm > s.base_cpm_rate * 1.25 THEN '🟡 中度低估:提价 15-25%'
        WHEN s.avg_realized_cpm > s.base_cpm_rate * 1.1 THEN '🟢 轻度低估:提价 5-10%'
        ELSE '✓ 价格合理'
    END AS pricing_recommendation
FROM imp_stats s
JOIN bid_stats b ON s.podcast_id = b.podcast_id AND s.slot_template_id = b.slot_template_id
WHERE s.avg_realized_cpm > s.base_cpm_rate * 1.1
ORDER BY underpriced_pct DESC
LIMIT 20;
```

**结果解读:**
- Tech 类 mid-roll 通常是 **最严重低估的** (因为 SaaS 广告主疯抢)
- 例:"AI Unplugged" mid-roll 底价 $25,实际成交 $38,平均 6.5 个出价者 → 安全提价到 $30-32 不会丢量
- `missed_revenue_usd` 量化损失:"如果不提价,每月损失 $XX,XXX"

---

## Query 7: 单 campaign 的 ROI 仪表盘

**业务背景:**
广告主 SquareSpace 投了 $50K 的播客广告,他们的市场总监要在月度评审会上回答 CFO:**"这钱花得值不值?"** 这条查询给出一个 campaign 的完整 ROI 一目了然,包括:花了多少 / 触达多少人 / 完播率 / 估算获客数 / 估算 CPA。

**业务知识:**
- **Budget Utilization (预算消耗率):** 实际花费 / 总预算。100% = 完美消耗;> 100% = 超支 (不会发生,平台会自动限);< 80% = 预算花不出去 (定向太窄或出价太低)
- **Estimated Conversion Rate (估算转化率):** 行业基准:完整听完广告的用户,2% 会成为客户。这是 **业内 rule of thumb**
- **Target CPA (目标 CPA):** 广告主可接受的获客成本上限。低于这个是 ROI 正

**分类:** Advertiser ROI
**难度:** 中级
**业务角色:** 广告主

**解题思路:**
链路 `ad_campaign → advertiser → ad_creative → ad_impression`,`WHERE` 锁定一个 campaign 名 (用 generator 强制植入的 curated 名,保证有行返回)。grain = 单行汇总。完播/跳过数用 `SUM(CASE WHEN 布尔...)`;CPCV、估算 CPA 的分母可能为 0,必须用 `NULLIF(..., 0)` 防除零。预算消耗率用 `window_budget_usd`。**重点看比率类指标** (完播率、CPCV、估算 CPA 与 target_cpa 对比),不要纠结绝对金额——60 天采样下单 campaign 花费本来就只有几~几十美元。

```sql
-- 单 campaign 综合表现仪表盘 (ROI 评估)
SELECT
    ac.campaign_name,
    a.company_name AS advertiser,
    ac.start_date,
    ac.end_date,
    ac.window_budget_usd,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_spent_usd,
    ROUND(100.0 * SUM(ai.actual_charge_cpm / 1000.0) / ac.window_budget_usd, 1) AS budget_utilized_pct,
    COUNT(ai.id) AS total_impressions,
    SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) AS skipped_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS skip_rate_pct,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm_paid,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0), 2) AS cost_per_completed_view,
    -- 估算转化数 (按 2% 完播→转化基准)
    ROUND(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) * 0.02, 0) AS estimated_conversions,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) * 0.02, 0), 2) AS estimated_cpa
FROM ad_campaign ac
JOIN advertiser a ON ac.advertiser_id = a.id
JOIN ad_creative acr ON ac.id = acr.campaign_id
JOIN ad_impression ai ON acr.id = ai.creative_id
WHERE ac.campaign_name = 'SquareSpace - Website Builder Promotion'  -- 改成实际 campaign 名
GROUP BY ac.id, ac.campaign_name, a.company_name, ac.start_date, ac.end_date, ac.window_budget_usd;
```

**结果解读:**
- 单行汇总。**看什么:** 完播率 (>75% 为佳) / CPCV (越低越好) / 估算 CPA 与 target_cpa 的对比。
- ⚠️ **量级提醒:** 本数据集是 60 天采样,单个 campaign 通常只交付 **数百到数千次曝光**,绝对花费只有几~几十美元。`budget_utilized_pct` 用的是 `window_budget_usd`(本窗口部署预算),所以会落在有意义的区间;但仍请**重点看比率类指标 (完播率/CPCV/CPA),不要纠结绝对金额**。
- 读法示例:"完播率 ~80%,CPCV ~$0.02,按 2% 完播→转化估算 CPA 远低于目标 CPA → 投放效率健康,可加预算。"
- 想用**真实转化**而非 2% 经验值时,可改用 `SUM(converted)` 列 (本数据集已建模点击/转化)。

---

## Query 8: 广告素材表现对比 (A/B 测试)

**业务背景:**
Nike 同时投放了 15 秒、30 秒、60 秒三种版本的素材,做 A/B 测试。他们的媒介主管要决定:**"接下来主推哪一版?"** 15 秒完播率最高但信息量少;60 秒信息全但常被跳过。这条查询用 CPCV (单次完整收听成本) 作为统一衡量,给出客观推荐。

**业务知识:**
- **A/B 测试:** 同时跑多个素材版本,看哪个表现最好
- **Cost per Completion (CPCV):** = 总花费 / 完整收听次数。**比 CPM 更接近真实效果**,因为 CPM 包含没听完的水分
- **Scale (规模化):** 数字广告里的"放量" — 把胜出素材的预算分配比例从 20% 提到 80%

**分类:** Advertiser ROI
**难度:** 高级
**业务角色:** 广告主

**解题思路:**
链路 `ad_creative → ad_campaign → ad_impression`,`WHERE` 锁定一个 campaign,按素材聚合做 A/B 对比。用 CTE `creative_performance` 先算各素材的完播率、CPCV,外层用窗口函数 `RANK() OVER (ORDER BY cost_per_completion ASC)` 给效率排名,再用 `CASE` 给"放量/继续测/暂停"建议。grain = 一个素材一行。这里窗口函数 RANK 比自连接或子查询更直接。CPCV 分母用 `NULLIF` 防零。

```sql
-- 对比 campaign 内不同素材的表现
WITH creative_performance AS (
    SELECT
        acr.creative_name,
        acr.duration_sec,
        acr.has_call_to_action,
        COUNT(ai.id) AS total_impressions,
        SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_impressions,
        ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
        ROUND(AVG(ai.ad_duration_played_sec), 1) AS avg_duration_played,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_cost,
        ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0), 2) AS cost_per_completion
    FROM ad_creative acr
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN ad_impression ai ON acr.id = ai.creative_id
    WHERE ac.campaign_name = 'Nike - Running Shoes Spring Launch'  -- 改成实际 campaign 名
    GROUP BY acr.id, acr.creative_name, acr.duration_sec, acr.has_call_to_action
)
SELECT
    creative_name,
    duration_sec,
    has_call_to_action,
    total_impressions,
    completed_impressions,
    completion_rate_pct,
    avg_duration_played,
    avg_cpm,
    total_cost,
    cost_per_completion,
    RANK() OVER (ORDER BY cost_per_completion ASC) AS efficiency_rank,
    CASE
        WHEN completion_rate_pct >= 85 AND cost_per_completion <= 0.02 THEN '🏆 胜出:放量主推'
        WHEN completion_rate_pct >= 70 AND cost_per_completion <= 0.03 THEN '🟢 良好:继续测试'
        WHEN completion_rate_pct < 60 OR cost_per_completion > 0.04 THEN '🔴 暂停:表现差'
        ELSE '🟡 一般:继续观察'
    END AS recommendation
FROM creative_performance
ORDER BY efficiency_rank;
```

**结果解读:**
- **常见 winner:** 30 秒 + CTA → 完播率 75-85%,CPCV $0.02-0.025
- **15 秒** 完播率 90%+ 但信息密度低,转化弱
- **60 秒** 完播率 60-70%,除非产品复杂 (如 SaaS) 否则不划算

---

## Query 9: 人群定向有效性分析

**业务背景:**
Robinhood (金融科技公司) 投了 "25-34 岁、Tech_Enthusiast、加州/纽约" 的精准定向,但定向溢价让 CPM 比泛投高 30%。他们想验证:**这 30% 溢价是不是带来了等量的效果提升?** 这条查询拆分"完全匹配 / 部分匹配 / 不匹配"三档,对比表现。

**业务知识:**
- **Targeting (定向):** 限定广告只投给特定人群
- **Targeting Premium (定向溢价):** 精准人群单价更贵
- **Reach (触达广度):** 越精准的定向 → 可触达人数越少 → 预算可能花不出去
- **Incremental Lift (增量提升):** 多花的钱带来的额外效果

**分类:** Advertiser ROI
**难度:** 高级
**业务角色:** 广告主

**解题思路:**
要把曝光同时连到 campaign 的定向条件 (`ad_creative → ad_campaign`) 和听众的真实属性 (`play_session → listener`),`WHERE` 锁定一个广告主。**核心技巧:逗号分隔的多值定向要用"两端补逗号 + LIKE"做成员判断**——`(',' || target || ',') LIKE ('%,' || 值 || ',%')`,这样 "25-34,35-44"、"US-CA,US-NY" 这类多值才能正确匹配 (老式 `=` 整串比较会漏)。CTE 里逐曝光算"匹配分"(年龄命中 + 地域命中 = 0/1/2),外层按"完全/部分/不匹配"分档对比完播率、跳过率、CPCV。grain = campaign × 匹配档。

```sql
-- 评估定向有效性:对比"完全匹配"vs"不匹配"的曝光表现
WITH impression_targeting_match AS (
    SELECT
        ai.id AS impression_id,
        ac.campaign_name,
        ac.target_segment_age,
        ac.target_segment_geo,
        l.age_group,
        l.location_state,
        -- 用"两端加逗号 + LIKE"做逗号分隔多值的成员判断,
        -- 正确支持 "25-34,35-44" / "US-CA,US-NY" 这类多值定向 (旧写法只会比整串)。
        (CASE
            WHEN ac.target_segment_age IS NOT NULL
                 AND (',' || ac.target_segment_age || ',') LIKE ('%,' || l.age_group || ',%')
            THEN 1 ELSE 0
         END)
        +
        (CASE
            WHEN ac.target_segment_geo IS NOT NULL
                 AND (',' || ac.target_segment_geo || ',') LIKE ('%,US-' || l.location_state || ',%')
            THEN 1 ELSE 0
         END) AS targeting_match_score,
        ai.actual_charge_cpm,
        ai.was_completed,
        ai.was_skipped
    FROM ad_impression ai
    JOIN ad_creative acr ON ai.creative_id = acr.id
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    JOIN play_session ps ON ai.play_session_id = ps.id
    JOIN listener l ON ps.listener_id = l.id
    WHERE a.company_name = 'Robinhood'  -- 改成实际广告主名 (FinTech, 有年龄+地域定向)
)
SELECT
    campaign_name,
    CASE
        WHEN targeting_match_score = 0 THEN '不匹配 (泛投)'
        WHEN targeting_match_score = 1 THEN '部分匹配 (1 项)'
        WHEN targeting_match_score >= 2 THEN '完全匹配 (2+ 项)'
    END AS targeting_alignment,
    COUNT(impression_id) AS total_impressions,
    ROUND(AVG(actual_charge_cpm), 2) AS avg_cpm,
    ROUND(100.0 * SUM(CASE WHEN was_completed THEN 1 ELSE 0 END) / COUNT(impression_id), 1) AS completion_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN was_skipped THEN 1 ELSE 0 END) / COUNT(impression_id), 1) AS skip_rate_pct,
    ROUND(SUM(actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN was_completed THEN 1 ELSE 0 END), 0), 3) AS cost_per_completion
FROM impression_targeting_match
GROUP BY campaign_name, targeting_alignment
ORDER BY campaign_name, targeting_match_score DESC;
```

**结果解读:**
- **完全匹配** 应比"不匹配"完播率高 15-25%、跳过率低 20-35%
- 如果 **CPCV (完全匹配) ≈ CPCV (不匹配)** → 定向溢价没带来等量回报 → 建议放宽定向降本

---

## Query 10: 出价金额 vs 赢拍率的关联

**业务背景:**
广告主用的程序化采购工具 (DSP) 要做 **bid shading (出价优化)** — 在能赢拍的前提下出最低价。这条查询画出"出价 → 赢拍率"曲线,帮 DSP 算法找到最优出价点。

**业务知识:**
- **Bid Shading:** 算法根据历史数据,把出价"贴着市场清算价"压低,既能赢拍又能省钱
- **Marginal Cost / Marginal Win Rate:** 每多出 $1 能多赢几个百分点的拍卖?
- **Sweet Spot:** 边际赢拍率最高的出价区间

**分类:** Advertiser ROI
**难度:** 中级
**业务角色:** 广告主

**解题思路:**
这题只用 `ad_auction_log` 一张表 (出价和是否赢拍都在里面,不用 JOIN)。用 CTE `bid_buckets` 把 `bid_cpm` 切成价格档,外层按档算 `win_rate = SUM(won_auction) / COUNT(*)`。grain = 一个价格档一行。`won_auction` 是布尔,SQLite 存 0/1,用 `CASE WHEN ... THEN 1 ELSE 0 END` 求和。`ORDER BY min_bid` 让价格档从低到高排,读出来就是一条"出价→赢拍率"曲线,找边际赢拍率最陡的甜蜜点。

```sql
-- 分析出价金额与赢拍率的关系
WITH bid_buckets AS (
    SELECT
        campaign_id,
        CASE
            WHEN bid_cpm < 10 THEN '$0-10'
            WHEN bid_cpm < 15 THEN '$10-15'
            WHEN bid_cpm < 20 THEN '$15-20'
            WHEN bid_cpm < 25 THEN '$20-25'
            WHEN bid_cpm < 30 THEN '$25-30'
            ELSE '$30+'
        END AS bid_range,
        bid_cpm,
        won_auction
    FROM ad_auction_log
)
SELECT
    bid_range,
    COUNT(*) AS total_bids,
    SUM(CASE WHEN won_auction THEN 1 ELSE 0 END) AS auctions_won,
    ROUND(100.0 * SUM(CASE WHEN won_auction THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate_pct,
    ROUND(AVG(bid_cpm), 2) AS avg_bid_in_range,
    ROUND(MIN(bid_cpm), 2) AS min_bid,
    ROUND(MAX(bid_cpm), 2) AS max_bid
FROM bid_buckets
GROUP BY bid_range
ORDER BY min_bid;
```

**结果解读:**
- 低价段 ($0-10) → 赢拍率 <15% (低于市场清算价)
- 中价段 ($15-20) → 赢拍率 40-60% (效率最优)
- 高价段 ($30+) → 赢拍率 85-95% 但花费多
- **最优出价:** 赢拍率随每 $1 增量陡升的区间 (例 $18-22)

---

## Query 11: 单次完整收听成本 (CPCV) 分析

**业务背景:**
HelloFresh (生鲜电商) 设定:**"我愿意为每次完整听完广告付 $0.05"**。他们要分析哪些节目的 CPCV 最低,把预算往那边挪。

**业务知识:**
- **CPCV (Cost per Completed View):** 比 CPM 更贴近"真实效果",因为没听完的不算
- **Quality Scoring:** 节目的"广告变现质量",由完播率决定
- **Budget Reallocation:** 业内常态 — 每周根据 CPCV 调整在不同节目的预算分配

**分类:** Advertiser ROI
**难度:** 中级
**业务角色:** 广告主

**解题思路:**
长链路:`ad_impression → ad_creative → ad_campaign → advertiser` 拿广告主,再 `ad_impression → play_session → podcast_episode → podcast` 拿节目,`WHERE` 锁定一个广告主,按"广告主×campaign×节目"聚合。grain = 一个节目一行。CPCV = 花费 / 完播数,用 `NULLIF` 防零、`ROUND(...,4)` 保留 4 位 (金额很小)。**`HAVING total_impressions >= 5` 阈值故意放低**:60 天采样下"单广告主×单节目"的曝光量不多,阈值太高会返回空集。`ORDER BY cost_per_completed_view ASC` 找最高效的库存来源。

```sql
-- 计算 CPCV 找出最高效的库存来源
SELECT
    a.company_name AS advertiser,
    ac.campaign_name,
    p.podcast_name,
    p.category AS podcast_category,
    COUNT(ai.id) AS total_impressions,
    SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_views,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_cost_usd,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0), 4) AS cost_per_completed_view,
    CASE
        WHEN SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0) <= 0.03 THEN '🟢 优秀:加投'
        WHEN SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0) <= 0.05 THEN '🟡 良好:维持'
        WHEN SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0) <= 0.08 THEN '🟠 一般:观察'
        ELSE '🔴 差:减投或暂停'
    END AS efficiency_rating
FROM ad_impression ai
JOIN ad_creative acr ON ai.creative_id = acr.id
JOIN ad_campaign ac ON acr.campaign_id = ac.id
JOIN advertiser a ON ac.advertiser_id = a.id
JOIN play_session ps ON ai.play_session_id = ps.id
JOIN podcast_episode pe ON ps.episode_id = pe.id
JOIN podcast p ON pe.podcast_id = p.id
WHERE a.company_name = 'HelloFresh'  -- 改成实际广告主名
GROUP BY a.company_name, ac.campaign_name, p.podcast_name, p.category
HAVING total_impressions >= 5  -- 60 天采样下单广告主×单节目的曝光不多, 阈值放低保证有行返回
ORDER BY cost_per_completed_view ASC;
```

**结果解读:**
- **高粘性节目** (true crime / business) → CPCV $0.02-0.035 → 加投
- **低粘性节目** (背景音乐类) → CPCV $0.06-0.10 → 减投

---

## Query 12: 竞争对手出价行为洞察

**业务背景:**
战略广告主 Coca-Cola 要做 **竞品情报**:Pepsi、Dr. Pepper 在抢同一批播客库存吗?他们出价多高?如果 Pepsi 比我们高 20%,要么我们加价,要么找差异化库存。这条查询拆解 CPG (快消) 行业内各广告主的拍卖参与情况。

**业务知识:**
- **Share of Voice (SOV):** 在同行业拍卖中赢拍的比例 — 反映"声音占比"
- **Competitive Intelligence:** B2B 营销情报
- **Differentiated Inventory:** 竞品不在抢的差异化库存 (例小众类目)

**分类:** Advertiser ROI
**难度:** 高级
**业务角色:** 广告主

**解题思路:**
链路 `ad_auction_log → ad_campaign → advertiser`,`WHERE` 锁定一个行业 (CPG)。CTE `competitor_bids` 把同行所有出价摊平,外层按广告主聚合赢拍率、均价、第二名出价。**注意参与场次要用 `COUNT(DISTINCT impression_id)` 去重**——一场拍卖在日志里有多条出价,不去重会高估参与度。`AVG(CASE WHEN bid_rank=2 THEN bid_cpm END)` 只对第二名求均价 (`CASE` 不命中返回 NULL,AVG 自动忽略)。`HAVING ≥50 场` 过滤,排出谁在用钱压制竞品。

```sql
-- 分析同行业广告主的竞争出价行为
WITH competitor_bids AS (
    SELECT
        a.company_name AS advertiser,
        a.industry_vertical,
        aal.impression_id,
        aal.bid_cpm,
        aal.won_auction,
        aal.bid_rank
    FROM ad_auction_log aal
    JOIN ad_campaign ac ON aal.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    WHERE a.industry_vertical = 'CPG'  -- 聚焦快消行业
)
SELECT
    advertiser,
    COUNT(DISTINCT impression_id) AS auctions_participated,
    COUNT(CASE WHEN won_auction THEN 1 END) AS auctions_won,
    ROUND(100.0 * COUNT(CASE WHEN won_auction THEN 1 END) / COUNT(DISTINCT impression_id), 1) AS win_rate_pct,
    ROUND(AVG(bid_cpm), 2) AS avg_bid_cpm,
    ROUND(AVG(CASE WHEN won_auction THEN bid_cpm END), 2) AS avg_winning_bid,
    ROUND(AVG(CASE WHEN bid_rank = 2 THEN bid_cpm END), 2) AS avg_second_place_bid,
    ROUND(MIN(bid_cpm), 2) AS min_bid,
    ROUND(MAX(bid_cpm), 2) AS max_bid
FROM competitor_bids
GROUP BY advertiser
HAVING auctions_participated >= 50
ORDER BY win_rate_pct DESC;
```

**结果解读:**
- Coca-Cola 赢拍率 58% / 均价 $22;Pepsi 赢拍率 48% / 均价 $19 → Coca-Cola 在 **用钱压制竞品**
- 新入局者 Olipop 赢拍率 35% / 均价 $28 → 愿意付高价但定向不准

---

## Query 13: 按节目类型的 RPM 对标

**业务背景:**
主播 "Tech Explained" 的 RPM 大约 $28 (每 1000 次播放主播净赚 $28),他自己不知道这是高还是低。这条查询给出同类节目的 RPM 平均值与区间,帮主播判断自己在行业里什么位置。
(注:RPM 是"每千次播放主播净收入",量级通常是**十几到几十美元**,不是几百几千 — 别和"每月总收入"混淆。)

**业务知识:**
- **RPM (Revenue Per Mille):** 主播视角 — 每 1000 次播放主播净赚多少
- **Benchmarking (对标):** 和同类节目比 — 不和不同分类节目比 (Tech vs Comedy 没意义)
- **Percentile:** P50 = 中位数,P75 = "好于 75% 同行的水平"

**分类:** Creator Monetization
**难度:** 中级
**业务角色:** 主播

**解题思路:**
链路 `podcast → podcast_episode → play_session`,再 `LEFT JOIN ad_impression`。**LEFT JOIN 是关键**:RPM 的分母是"播放数",没成交广告的会话也得算进去,否则 RPM 会虚高。`WHERE p.is_premium = 0` 排除会员节目。两层聚合:CTE `podcast_metrics` 先按单节目算 RPM (主播分成 = 收入×0.70,RPM = 分成/播放数×1000),外层再按 `category` 聚合出 avg/min/max。**SQLite 原生没有 `PERCENTILE_CONT`**,所以这里只给区间,真要算中位数/分位需用 `NTILE` 或导出外部算 (注释已注明)。

```sql
-- 按节目分类对标 RPM
WITH podcast_metrics AS (
    SELECT
        p.id AS podcast_id,
        p.podcast_name,
        p.category,
        COUNT(DISTINCT ps.id) AS total_play_sessions,
        COUNT(ai.id) AS total_ad_impressions,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_ad_revenue,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) * 0.70, 2) AS creator_payout_70pct,
        ROUND((SUM(ai.actual_charge_cpm / 1000.0) * 0.70) / NULLIF(COUNT(DISTINCT ps.id), 0) * 1000, 2) AS rpm
    FROM podcast p
    JOIN podcast_episode pe ON p.id = pe.podcast_id
    JOIN play_session ps ON pe.id = ps.episode_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE p.is_premium = 0
    GROUP BY p.id, p.podcast_name, p.category
    HAVING total_play_sessions >= 100
)
SELECT
    category,
    COUNT(podcast_id) AS podcasts_in_category,
    ROUND(AVG(rpm), 2) AS avg_rpm,
    ROUND(MIN(rpm), 2) AS min_rpm,
    ROUND(MAX(rpm), 2) AS max_rpm,
    ROUND(AVG(rpm) - MIN(rpm), 2) AS rpm_range,
    -- 注:SQLite 原生不支持 PERCENTILE_CONT,生产环境建议改 NTILE 或外部计算
    ROUND(AVG(total_ad_revenue), 2) AS avg_total_revenue_per_podcast
FROM podcast_metrics
GROUP BY category
ORDER BY avg_rpm DESC;
```

**结果解读:**
- RPM 量级 = **十几到几十美元/千次播放** (CPM ~$15-30 × 约 1.5 个广告/播放 × 70% 分成),不是几百上千。
- **Technology / Business** 通常最高 (SaaS/FinTech 抢量把 CPM 推高);**Comedy / Entertainment** 偏低 (广告主溢价低)。
- SQL 给的是 avg / min / max 区间;SQLite 原生没有 PERCENTILE_CONT,真要算中位数 / 75 分位需用 NTILE 或导出到外部计算。主播可先用 "自己的 RPM vs 同类 max" 的差距判断离头部还有多远。

---

## Query 14: 单集表现深度分析

**业务背景:**
主播要弄明白 **"哪类内容最赚钱"**。例如 "ChatGPT 解读" 这一集是不是比其他集赚 3 倍?如果是,下一季就多做 AI 主题。

**业务知识:**
- **Content Analytics (内容分析):** 用数据指导内容创作方向
- **Halo Effect (光环效应):** 热门话题集自带流量 + 高 CPM 双重收益

**分类:** Creator Monetization
**难度:** 中级
**业务角色:** 主播

**解题思路:**
链路 `podcast → podcast_episode → play_session` `LEFT JOIN ad_impression`,`WHERE` 锁定一档节目,按单集聚合。grain = 一集一行。**坑:LEFT JOIN 后一个会话会因为有多条曝光而"翻倍"**,所以播放数必须用 `COUNT(DISTINCT ps.id)`,否则播放数被广告条数放大、RPM 被压低。RPM = 主播分成 / 去重播放数 × 1000。`ORDER BY rpm DESC` 找最赚钱的选题——关注集与集之间的**相对差异**而非绝对值。

```sql
-- 按收入排单集,识别内容变现规律
SELECT
    p.podcast_name,
    pe.episode_number,
    pe.title,
    pe.publish_date,
    pe.duration_seconds / 60 AS duration_minutes,
    COUNT(DISTINCT ps.id) AS total_plays,
    COUNT(ai.id) AS total_ad_impressions,
    ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS gross_ad_revenue,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) * 0.70, 2) AS creator_earnings_70pct,
    ROUND((SUM(ai.actual_charge_cpm / 1000.0) * 0.70) / NULLIF(COUNT(DISTINCT ps.id), 0) * 1000, 2) AS rpm
FROM podcast p
JOIN podcast_episode pe ON p.id = pe.podcast_id
JOIN play_session ps ON pe.id = ps.episode_id
LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
WHERE p.podcast_name = 'Tech Explained'
GROUP BY p.podcast_name, pe.episode_number, pe.title, pe.publish_date, pe.duration_seconds
ORDER BY rpm DESC
LIMIT 20;
```

**结果解读:**
- 单集 RPM 量级同样是**几十美元/千次播放**;集与集之间的**相对差异**才是重点 (例:某 AI 主题集 RPM ~$35,高于普通集 ~$20)。
- **内容策略:** 哪类选题 RPM 持续更高 (通常 AI/Tech 主题更值钱) → 下季重点投入。

---

## Query 15: 主播月度营收趋势分析

**业务背景:**
主播想看 **月度收入增长趋势**:是 MoM (Month-over-Month) 增长 10%?还是停滞?Q4 是否因为圣诞旺季 CPM 涨 25%?

**业务知识:**
- **MoM (Month-over-Month):** 环比 — 本月 vs 上月
- **YoY (Year-over-Year):** 同比 — 本月 vs 去年同月
- **Q4 Seasonality:** 11-12 月零售旺季,所有数字广告平台 CPM 涨 15-30%

**分类:** Creator Monetization
**难度:** 高级
**业务角色:** 主播

**解题思路:**
直接用汇总表 `revenue_settlement → podcast` (不必回到曝光明细,settlement 已是真实聚合),`WHERE` 锁定一档节目。CTE 按月聚合 (`DATE(settlement_date, 'start of month')` 归月),外层用窗口函数 `LAG(creator_earnings) OVER (ORDER BY month)` 取上月值算 MoM 环比。grain = 一个月一行。**LAG 是算环比的标准工具**,比自连接简洁得多;增长率分母用 `NULLIF` 防上月为 0。

```sql
-- 月度营收趋势 + 增长率
WITH monthly_revenue AS (
    SELECT
        p.podcast_name,
        DATE(rs.settlement_date, 'start of month') AS month,
        SUM(rs.total_impressions) AS total_impressions,
        ROUND(SUM(rs.total_revenue_usd), 2) AS gross_revenue,
        ROUND(SUM(rs.podcast_payout_usd), 2) AS creator_earnings,
        ROUND(AVG(rs.avg_cpm), 2) AS avg_cpm,
        ROUND(AVG(rs.rpm), 2) AS avg_rpm,
        ROUND(AVG(rs.fill_rate), 3) AS avg_fill_rate
    FROM revenue_settlement rs
    JOIN podcast p ON rs.podcast_id = p.id
    WHERE p.podcast_name = 'Tech Explained'
    GROUP BY p.podcast_name, month
)
SELECT
    podcast_name,
    month,
    total_impressions,
    gross_revenue,
    creator_earnings,
    avg_cpm,
    avg_rpm,
    avg_fill_rate,
    LAG(creator_earnings) OVER (ORDER BY month) AS prev_month_earnings,
    ROUND(creator_earnings - LAG(creator_earnings) OVER (ORDER BY month), 2) AS earnings_change,
    ROUND(100.0 * (creator_earnings - LAG(creator_earnings) OVER (ORDER BY month)) /
        NULLIF(LAG(creator_earnings) OVER (ORDER BY month), 0), 1) AS growth_rate_pct
FROM monthly_revenue
ORDER BY month DESC;
```

**结果解读:**
- 增长中节目:MoM 5-15%
- 成熟节目:稳定 ±5%,Q4 高峰
- 下滑节目:需调查 — 内容老化?广告主转移?

---

## Query 16: 内容优化建议 (时长 / 发布日)

**业务背景:**
主播想要 **数据驱动的内容建议**。例如:超过 45 分钟的集完播率低 20%? 周一发的集比周五多 30% 播放?这条查询拆分时长档位 + 发布日,给出最优组合。

**业务知识:**
- **Duration Tradeoff:** 短集完播率高但广告位少;长集广告位多但完播率低
- **Publishing Cadence (发布节奏):** 业内最佳 — 工作日早晨发,通勤听众抓住

**分类:** Creator Monetization
**难度:** 高级
**业务角色:** 主播

**解题思路:**
链路 `podcast_episode → podcast → play_session` `LEFT JOIN ad_impression`,`WHERE` 锁定一档节目。CTE `episode_analysis` 给每集打两个标签:时长档 (`CASE` 切 `duration_seconds`) 和发布星期 (`strftime('%w', publish_date)`);外层按时长档聚合,并用**关联子查询** `(SELECT AVG(rpm) FROM episode_analysis)` 取全局平均 RPM 作基准给"强/弱/平均"建议。grain = 一个时长档一行。播放数同样用 `COUNT(DISTINCT ps.id)` 防 LEFT JOIN 翻倍。

```sql
-- 按时长档位 + 发布日的内容优化建议
WITH episode_analysis AS (
    SELECT
        pe.id AS episode_id,
        CASE
            WHEN pe.duration_seconds < 1200 THEN '<20 分钟'
            WHEN pe.duration_seconds < 1800 THEN '20-30 分钟'
            WHEN pe.duration_seconds < 2700 THEN '30-45 分钟'
            WHEN pe.duration_seconds < 3600 THEN '45-60 分钟'
            ELSE '>60 分钟'
        END AS duration_bucket,
        CASE CAST(strftime('%w', pe.publish_date) AS INTEGER)
            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday' WHEN 6 THEN 'Saturday'
        END AS publish_day,
        COUNT(DISTINCT ps.id) AS total_plays,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
        COUNT(ai.id) AS total_impressions,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) * 0.70, 2) AS creator_earnings,
        ROUND((SUM(ai.actual_charge_cpm / 1000.0) * 0.70) / NULLIF(COUNT(DISTINCT ps.id), 0) * 1000, 2) AS rpm
    FROM podcast_episode pe
    JOIN podcast p ON pe.podcast_id = p.id
    JOIN play_session ps ON pe.id = ps.episode_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE p.podcast_name = 'Tech Explained'
    GROUP BY pe.id, duration_bucket, publish_day
)
SELECT
    duration_bucket,
    COUNT(episode_id) AS episodes,
    ROUND(AVG(total_plays), 0) AS avg_plays_per_episode,
    ROUND(AVG(avg_completion_pct), 1) AS avg_completion_pct,
    ROUND(AVG(rpm), 2) AS avg_rpm,
    ROUND(SUM(creator_earnings), 2) AS total_earnings,
    CASE
        WHEN AVG(rpm) >= (SELECT AVG(rpm) FROM episode_analysis) * 1.1 THEN '✓ 强:维持此时长'
        WHEN AVG(rpm) <= (SELECT AVG(rpm) FROM episode_analysis) * 0.9 THEN '✗ 弱:考虑调整'
        ELSE '- 平均:不变'
    END AS recommendation
FROM episode_analysis
GROUP BY duration_bucket
ORDER BY avg_rpm DESC;
```

**结果解读:**
- **30-45 分钟** 通常 RPM 最高 — 够塞 mid-roll 又不至于让人弃听
- **<20 分钟** 完播率最高但广告位少
- **>60 分钟** 完播率掉到 60%,后半段广告位空置

---

## Query 17: 广告疲劳侦测 (Ad Fatigue)

**业务背景:**
UX 团队怀疑 **某些听众被同一广告主轰炸太多次**,产生反感开始狂跳广告,甚至有流失风险。例:某听众两周内听了 Geico 广告 8 次,他可能崩溃了。这条查询识别这类高风险听众。

**业务知识:**
- **Ad Fatigue (广告疲劳):** 听众对同一广告重复曝光产生的心理排斥
- **Frequency Cap (频次封顶):** 限制同一广告主对同一听众的曝光次数 (业内最佳 3 次/周/广告主)
- **Churn Risk (流失风险):** 反感 → 不开 App → 流失

**分类:** Listener Experience
**难度:** 高级
**业务角色:** 平台 UX

**解题思路:**
长链路 `listener → play_session → ad_impression → ad_creative → ad_campaign → advertiser`,按"听众×广告主"聚合,找被同一广告主反复轰炸的人。`WHERE ai.impression_time >= DATE('2026-06-21','-14 days')` 限近 14 天。grain = 听众×广告主一行。`HAVING total_impressions_from_advertiser >= 5` 先筛高频,外层再用 `WHERE skip_rate >= 0.5` 锁定"高频 + 高跳过"的疲劳信号。`MAX(impression_time)` 配 `JULIANDAY` 算距今天数。`CASE` 分严重/高/中/正常四档给降频建议。

```sql
-- 识别可能产生广告疲劳的听众
WITH listener_ad_exposure AS (
    SELECT
        l.id AS listener_id,
        l.listener_uuid,
        a.company_name AS advertiser,
        COUNT(DISTINCT ps.id) AS sessions_with_this_advertiser,
        COUNT(ai.id) AS total_impressions_from_advertiser,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS skip_rate,
        MAX(ai.impression_time) AS last_impression_time,
        ROUND(JULIANDAY('2026-06-21') - JULIANDAY(MAX(ai.impression_time)), 1) AS days_since_last_ad
    FROM listener l
    JOIN play_session ps ON l.id = ps.listener_id
    JOIN ad_impression ai ON ps.id = ai.play_session_id
    JOIN ad_creative acr ON ai.creative_id = acr.id
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    WHERE ai.impression_time >= DATE('2026-06-21', '-14 days')
    GROUP BY l.id, l.listener_uuid, a.company_name
    HAVING total_impressions_from_advertiser >= 5
)
SELECT
    listener_uuid,
    advertiser,
    sessions_with_this_advertiser,
    total_impressions_from_advertiser,
    skip_rate,
    days_since_last_ad,
    CASE
        WHEN total_impressions_from_advertiser >= 12 AND skip_rate >= 0.7 THEN '🚨 严重:屏蔽 30 天'
        WHEN total_impressions_from_advertiser >= 8 AND skip_rate >= 0.6 THEN '🔴 高:降频 50%'
        WHEN total_impressions_from_advertiser >= 5 AND skip_rate >= 0.5 THEN '🟡 中:降频 25%'
        ELSE '🟢 正常'
    END AS fatigue_level
FROM listener_ad_exposure
WHERE skip_rate >= 0.5
ORDER BY total_impressions_from_advertiser DESC, skip_rate DESC
LIMIT 100;
```

**结果解读:**
- **严重案例:** 立即对该广告主全平台屏蔽 30 天
- **平台行动:** 全局规则 — "单广告主对单听众每 7 天最多 3 次"

---

## Query 18: 按素材属性分析跳过率

**业务背景:**
UX 团队想给广告主一份 **"素材最佳实践指南"**:60 秒比 30 秒跳过率高一倍吗?没 CTA 的会被跳得更多吗?数据出来后可以发给广告主"按这个做素材效果最好"。

**业务知识:**
- **Creative Best Practices:** 平台向广告主输出的素材制作指南
- **CTA (Call to Action):** "立即访问 xxx.com"、"现在下单送 50 元" 这类号召
- 行业共识:**30 秒带 CTA 是综合最优**

**分类:** Listener Experience
**难度:** 中级
**业务角色:** 平台 UX

**解题思路:**
链路 `ad_creative → ad_impression`,按 `(duration_sec, has_call_to_action)` 两个素材属性的组合聚合。grain = 时长×是否含CTA 的组合一行。无需 CTE,一次 `GROUP BY` 即可。跳过率、完播率用布尔 `SUM/COUNT`。`HAVING total_impressions >= 50` 过滤小样本,`ORDER BY skip_rate_pct ASC` 让跳过率最低的组合 (通常是 30 秒 + CTA) 排最前——这就是要发给广告主的"素材最佳实践"。

```sql
SELECT
    acr.duration_sec,
    acr.has_call_to_action,
    COUNT(ai.id) AS total_impressions,
    SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) AS skipped_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS skip_rate_pct,
    SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(AVG(ai.ad_duration_played_sec), 1) AS avg_seconds_listened,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm_paid
FROM ad_creative acr
JOIN ad_impression ai ON acr.id = ai.creative_id
GROUP BY acr.duration_sec, acr.has_call_to_action
HAVING total_impressions >= 50
ORDER BY skip_rate_pct ASC;
```

**结果解读:**
- 30 秒 + CTA:跳过率 32-38%,完播率 65-72% ← **最佳**
- 60 秒无 CTA:跳过率 58-68% ← **最差**

---

## Query 19: 最优广告频次推荐

**业务背景:**
策略团队要决定 **频次封顶** 应该设几次?现在 "每小时最多 5 个广告" 是不是太多?会赶走听众?太少又会少赚钱?这条查询找出"广告频次 → 听众参与度"的拐点。

**业务知识:**
- **Frequency Cap (频次封顶):** 业内通用做法,平衡收入与体验
- **Sweet Spot:** 收入边际效益 = 体验边际损失的拐点
- **Diminishing Returns (边际递减):** 多塞一个广告,收入增量 < 体验损失

**分类:** Listener Experience
**难度:** 高级
**业务角色:** 平台 UX

**解题思路:**
链路 `listener → play_session` `LEFT JOIN ad_impression`,CTE `listener_ad_frequency` 先按听众算"每会话广告数" `ads_per_session` 及完播率、跳过率、贡献收入,外层按频次档聚合看拐点。`WHERE` 限近 30 天且 `is_premium_subscriber=0` (会员不投广告)。**LEFT JOIN 让"听了但没收到广告"的会话也计入分母**,否则频次会被高估。`HAVING total_sessions >= 5` 保证每个听众样本稳定。grain:内层一听众一行,外层一频次档一行。找"收入增量 < 体验损失"的甜蜜点定频次封顶。

```sql
WITH listener_ad_frequency AS (
    SELECT
        l.id AS listener_id,
        COUNT(ps.id) AS total_sessions,
        COUNT(ai.id) AS total_ads_heard,
        ROUND(COUNT(ai.id) * 1.0 / NULLIF(COUNT(ps.id), 0), 2) AS ads_per_session,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_episode_completion_pct,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS avg_ad_skip_rate,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS revenue_generated
    FROM listener l
    JOIN play_session ps ON l.id = ps.listener_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE ps.session_start_time >= DATE('2026-06-21', '-30 days')
        AND l.is_premium_subscriber = 0
    GROUP BY l.id
    HAVING total_sessions >= 5
)
SELECT
    CASE
        WHEN ads_per_session < 2 THEN '0-2 个/会话'
        WHEN ads_per_session < 3 THEN '2-3 个/会话'
        WHEN ads_per_session < 4 THEN '3-4 个/会话'
        WHEN ads_per_session < 5 THEN '4-5 个/会话'
        ELSE '5+ 个/会话'
    END AS frequency_tier,
    COUNT(listener_id) AS listener_count,
    ROUND(AVG(ads_per_session), 2) AS avg_ads_per_session,
    ROUND(AVG(avg_episode_completion_pct), 1) AS avg_completion_pct,
    ROUND(AVG(avg_ad_skip_rate), 2) AS avg_skip_rate,
    ROUND(AVG(revenue_generated), 2) AS avg_revenue_per_listener,
    ROUND(SUM(revenue_generated), 2) AS total_revenue_in_tier
FROM listener_ad_frequency
GROUP BY frequency_tier
ORDER BY avg_ads_per_session;
```

**结果解读:**
- **甜蜜点 2-4 个/会话** — 收入与体验平衡
- 5+ 个:收入小幅增加但跳过率飙到 55%+
- **建议:** 频次封顶 3-3.5/会话

---

## Query 20: 听众标签满意度评分

**业务背景:**
留存团队要识别 **哪些听众群体在流失**。如果 "Tech_Enthusiast" 听众突然完播率下降、跳过率上升,可能预示流失。这条查询给每个标签算个"健康分"。

**业务知识:**
- **Composite Score (综合分):** 把多个指标加权合成一个分,方便排序
- **Cohort Retention:** 按"群组"看留存,而不是个体

**分类:** Listener Experience
**难度:** 高级
**业务角色:** 平台 UX

**解题思路:**
链路 `listener_segment → listener → play_session` `LEFT JOIN ad_impression`,CTE `segment_engagement` 按标签算完播率、人均会话数、广告跳过率、人均收听时长,外层用一个**加权公式**把它们合成单一"满意度分":完播率×40 + 频次档×30 + (1−跳过率)×30。grain = 一个标签一行。`WHERE` 限近 30 天,`HAVING listener_count >= 50` 过滤小群体。把"健康/关注/风险"做成 `CASE` 分档,识别正在流失的人群。

```sql
WITH segment_engagement AS (
    SELECT
        ls.segment_name,
        COUNT(DISTINCT l.id) AS listener_count,
        COUNT(DISTINCT ps.id) AS total_sessions,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
        ROUND(COUNT(DISTINCT ps.id) * 1.0 / NULLIF(COUNT(DISTINCT l.id), 0), 1) AS sessions_per_listener,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS avg_ad_skip_rate,
        ROUND(AVG(l.total_listening_hours), 1) AS avg_listening_hours
    FROM listener_segment ls
    JOIN listener l ON ls.listener_id = l.id
    JOIN play_session ps ON l.id = ps.listener_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE ps.session_start_time >= DATE('2026-06-21', '-30 days')
    GROUP BY ls.segment_name
    HAVING listener_count >= 50
)
SELECT
    segment_name,
    listener_count,
    sessions_per_listener,
    avg_completion_pct,
    avg_ad_skip_rate,
    avg_listening_hours,
    -- 满意度分:完播率 40% + 频次 30% + 广告容忍 30%
    ROUND(
        (avg_completion_pct / 100.0) * 40 +
        (CASE WHEN sessions_per_listener >= 10 THEN 30
              WHEN sessions_per_listener >= 5 THEN 20
              ELSE 10 END) +
        ((1 - avg_ad_skip_rate) * 30),
    1) AS satisfaction_score,
    CASE
        WHEN (avg_completion_pct / 100.0) * 40 +
             (CASE WHEN sessions_per_listener >= 10 THEN 30 WHEN sessions_per_listener >= 5 THEN 20 ELSE 10 END) +
             ((1 - avg_ad_skip_rate) * 30) >= 75 THEN '🟢 健康'
        WHEN (avg_completion_pct / 100.0) * 40 +
             (CASE WHEN sessions_per_listener >= 10 THEN 30 WHEN sessions_per_listener >= 5 THEN 20 ELSE 10 END) +
             ((1 - avg_ad_skip_rate) * 30) >= 60 THEN '🟡 关注趋势'
        ELSE '🔴 风险:需介入'
    END AS segment_health
FROM segment_engagement
ORDER BY satisfaction_score DESC;
```

**结果解读:**
- 健康标签:Tech_Enthusiast, Finance_Savvy
- 风险标签:可能是 Frequent_Traveler (出差变少) — 启动专项留存

---

## Query 21: 拍卖竞争激烈度热力图

**业务背景:**
市场分析团队要可视化 **各类库存的竞争激烈度**。Tech 类 mid-roll 平均 8 个出价 (惨烈),Comedy 类 post-roll 只有 2 个 (库存被低估)。

**业务知识:**
- **Seller's Market:** 卖家市场 — 库存稀缺,平台占优
- **Buyer's Market:** 买家市场 — 库存充裕,广告主占优
- **Bid Spread:** 出价分散度 — 大 = 估值分歧大,拍卖效率高

**分类:** Auction Dynamics
**难度:** 高级
**业务角色:** 平台分析

**解题思路:**
链路 `ad_impression → ad_auction_log`,再回连 `episode_ad_slot → ad_slot_template` 取 slot 类型、`play_session → podcast_episode → podcast` 取节目分类。CTE `auction_competition` **必须先按单次曝光 (`GROUP BY ai.id`) 算出价者数、最高/最低价、价差**,否则跨曝光混算会出错;外层再按"分类×slot类型"聚合。`COUNT(DISTINCT campaign_id)` 算每场出价者数。grain:内层一曝光一行,外层一(分类,slot)一行。`CASE` 按出价者数分"惨烈/强/一般/弱"竞争档,做成热力图。

```sql
WITH auction_competition AS (
    SELECT
        p.category AS podcast_category,
        ast.slot_type,
        ai.id AS impression_id,
        COUNT(DISTINCT aal.campaign_id) AS bidder_count,
        MAX(aal.bid_cpm) AS highest_bid,
        MIN(aal.bid_cpm) AS lowest_bid,
        MAX(aal.bid_cpm) - MIN(aal.bid_cpm) AS bid_spread
    FROM ad_impression ai
    JOIN ad_auction_log aal ON ai.id = aal.impression_id
    JOIN episode_ad_slot eas ON ai.ad_slot_id = eas.id
    JOIN ad_slot_template ast ON eas.slot_template_id = ast.id
    JOIN play_session ps ON ai.play_session_id = ps.id
    JOIN podcast_episode pe ON ps.episode_id = pe.id
    JOIN podcast p ON pe.podcast_id = p.id
    GROUP BY p.category, ast.slot_type, ai.id
)
SELECT
    podcast_category,
    slot_type,
    COUNT(impression_id) AS total_auctions,
    ROUND(AVG(bidder_count), 1) AS avg_bidders_per_auction,
    ROUND(AVG(highest_bid), 2) AS avg_winning_bid,
    ROUND(AVG(lowest_bid), 2) AS avg_floor_bid,
    ROUND(AVG(bid_spread), 2) AS avg_bid_spread,
    CASE
        WHEN AVG(bidder_count) >= 6 THEN '🔥 惨烈:6+ 出价 (卖方市场)'
        WHEN AVG(bidder_count) >= 4 THEN '🟢 强:4-5 出价 (平衡)'
        WHEN AVG(bidder_count) >= 2 THEN '🟡 一般:2-3 出价 (买方市场)'
        ELSE '❄️ 弱:<2 出价 (库存被低估)'
    END AS competition_intensity
FROM auction_competition
GROUP BY podcast_category, slot_type
ORDER BY avg_bidders_per_auction DESC;
```

**结果解读:**
- **Mid-roll** 出价者最多(设计上最抢手)→ 多为 "🔥 惨烈 (6+)" 或 "🟢 强";叠加最高 eCPM → 提价空间最大。
- **Post-roll** 出价者最少 → 多为 "🟡 一般 (2-3) 买方市场";触达低,销售可拓展 DTC 新广告主填补。
- 注:本数据集竞价者数量按 slot 需求建模(mid 4-8 / pre 2-6 / post 2-4),所以"mid 最抢手"与"mid 最值钱"两个叙事一致。

---

## Query 22: 第二价格拍卖机制效率验证

**业务背景:**
产品团队要验证 **二价拍卖代码有没有 bug**。理论上赢家应付 "第二价 + $0.01"。如果平均超收远 > $0.05,说明代码有问题在多收钱 → 广告主投诉。

**业务知识:**
- **Vickrey Auction (维克瑞拍卖):** 二价拍卖,1996 年诺奖得主提出
- **Truthful Bidding:** 二价机制让广告主"如实出心理价" — 因为反正不多付
- **Efficient Allocation:** 资源分配最优 — 真正价值高的人拿到

**分类:** Auction Dynamics
**难度:** 中级
**业务角色:** 平台分析

**解题思路:**
只用 `ad_impression → ad_auction_log`。CTE `auction_pricing` 用 `MAX(CASE WHEN bid_rank=1/2 THEN bid_cpm END)` 把每次曝光的第一价、第二价"透视"成两列,并按出价者数标记单人/多人拍卖。外层按拍卖类型聚合,验证"实付 − 第二价"是否 ≈ $0.01。grain:内层一曝光一行,外层单人/多人各一行。**关键:只对多人拍卖判定超收**——单人拍卖没有第二价 (`second_bid` 为 NULL),按赢拍价折扣计费,不参与超收判断。健康值:超收 ≈ $0.01。

```sql
WITH auction_pricing AS (
    SELECT
        ai.id AS impression_id,
        MAX(CASE WHEN aal.bid_rank = 1 THEN aal.bid_cpm END) AS first_bid,
        MAX(CASE WHEN aal.bid_rank = 2 THEN aal.bid_cpm END) AS second_bid,
        ai.winning_bid_cpm,
        ai.actual_charge_cpm,
        CASE
            WHEN COUNT(DISTINCT aal.campaign_id) = 1 THEN 'Single_Bidder'
            ELSE 'Multi_Bidder'
        END AS auction_type
    FROM ad_impression ai
    JOIN ad_auction_log aal ON ai.id = aal.impression_id
    GROUP BY ai.id, ai.winning_bid_cpm, ai.actual_charge_cpm
)
SELECT
    auction_type,
    COUNT(impression_id) AS total_auctions,
    ROUND(AVG(first_bid), 2) AS avg_winning_bid,
    ROUND(AVG(second_bid), 2) AS avg_second_bid,
    ROUND(AVG(actual_charge_cpm), 2) AS avg_actual_charge,
    ROUND(AVG(first_bid - actual_charge_cpm), 2) AS avg_winner_savings,
    -- 只对多人拍卖计算"超收";单人拍卖无第二价 (second_bid 为 NULL),不参与判定
    ROUND(AVG(CASE WHEN auction_type = 'Multi_Bidder' THEN actual_charge_cpm - second_bid END), 2) AS avg_overpayment_vs_second,
    ROUND(100.0 * AVG(first_bid - actual_charge_cpm) / NULLIF(AVG(first_bid), 0), 1) AS pct_savings_for_winner,
    CASE
        WHEN auction_type = 'Single_Bidder' THEN '— 单人拍卖:无第二价, 不判定超收'
        WHEN AVG(actual_charge_cpm - second_bid) BETWEEN 0 AND 0.05 THEN '✓ 健康:按二价收费'
        WHEN AVG(actual_charge_cpm - second_bid) > 0.05 THEN '✗ 异常:超收!'
        ELSE '⚠️ 警告:检查逻辑'
    END AS auction_health
FROM auction_pricing
GROUP BY auction_type;
```

**结果解读:**
- 多人拍卖:`avg_overpayment_vs_second` 应 $0.01-0.02 (正常)
- 单人拍卖:无第二价 → 按赢拍价折扣 10% 计费

---

## Query 23: 预算调配 (Pacing) 有效性

**业务背景:**
广告主用 budget pacing 让预算 **匀速消耗**。平台要评估算法效果:有没有 campaign 烧得太快 (10 天烧 50% 预算)?或太慢 (50 天才烧 20%)?

**业务知识:**
- **Pacing Algorithm:** 业内核心算法,平衡"早烧完没量"vs"烧不完浪费"
- **Pacing Variance:** 实际消耗% - 时间过去%。> +15 = 烧太快;< -15 = 烧太慢

**分类:** Auction Dynamics
**难度:** 高级
**业务角色:** 平台分析

**解题思路:**
链路 `ad_campaign → advertiser` `LEFT JOIN ad_creative → ad_impression`。CTE `campaign_pacing` 同时算"已过时间%" (用 `JULIANDAY` 算天数比) 和"已花预算%",外层算 `pacing_variance = 已花% − 已过%` 并分档。**预算用 `window_budget_usd`**,否则消耗率恒≈0%、所有 campaign 都被判"烧太慢"。`WHERE` 只看横跨今天的活跃 campaign 且 `days_elapsed >= 3` (太新的没意义)。grain = 一个 campaign 一行。`ORDER BY ABS(变化) DESC` 把偏离最大的排最前。

```sql
WITH campaign_pacing AS (
    SELECT
        ac.id AS campaign_id,
        ac.campaign_name,
        a.company_name,
        ac.start_date,
        ac.end_date,
        ac.window_budget_usd,
        (JULIANDAY(ac.end_date) - JULIANDAY(ac.start_date) + 1) AS total_days,
        (JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date) + 1) AS days_elapsed,
        ROUND(100.0 * (JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date) + 1) /
            (JULIANDAY(ac.end_date) - JULIANDAY(ac.start_date) + 1), 1) AS pct_time_elapsed,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS spent_to_date,
        -- 用 window_budget_usd (窗口部署预算) 才能算出有意义的消耗率, 否则恒≈0% → 全判"烧太慢"
        ROUND(100.0 * SUM(ai.actual_charge_cpm / 1000.0) / ac.window_budget_usd, 1) AS pct_budget_spent
    FROM ad_campaign ac
    JOIN advertiser a ON ac.advertiser_id = a.id
    LEFT JOIN ad_creative acr ON ac.id = acr.campaign_id
    LEFT JOIN ad_impression ai ON acr.id = ai.creative_id
    WHERE ac.start_date <= DATE('2026-06-21')
        AND ac.end_date >= DATE('2026-06-21')
    GROUP BY ac.id, ac.campaign_name, a.company_name, ac.start_date, ac.end_date, ac.window_budget_usd
)
SELECT
    campaign_name,
    company_name,
    total_days AS campaign_duration_days,
    days_elapsed,
    pct_time_elapsed,
    window_budget_usd,
    spent_to_date,
    pct_budget_spent,
    ROUND(pct_budget_spent - pct_time_elapsed, 1) AS pacing_variance,
    CASE
        WHEN pct_budget_spent > pct_time_elapsed + 15 THEN '⚠️ 烧太快:有提前耗尽风险'
        WHEN pct_budget_spent > pct_time_elapsed + 8 THEN '↑ 偏快'
        WHEN pct_budget_spent < pct_time_elapsed - 15 THEN '⚠️ 烧太慢:预算花不完'
        WHEN pct_budget_spent < pct_time_elapsed - 8 THEN '↓ 偏慢'
        ELSE '✓ 节奏正常'
    END AS pacing_status
FROM campaign_pacing
WHERE days_elapsed >= 3
ORDER BY ABS(pct_budget_spent - pct_time_elapsed) DESC;
```

**结果解读:**
- 烧太快 → 降低出价激进度
- 烧太慢 → 提价或放宽定向

---

## Query 24: 出价调整的弹性分析

**业务背景:**
Adobe 想做 bid 调整实验:**出价从 $20 → $24 (+20%) 能多赢多少拍卖?** 这条查询画出"出价 → 赢拍率"弹性曲线。

**业务知识:**
- **Elasticity (弹性):** 经济学概念 — 输出变化率 / 输入变化率
- **Marginal Win Rate:** 每多出 $1 多赢的赢拍率
- **Diminishing Returns:** 边际递减 — 过了某点继续加钱意义不大

**分类:** Auction Dynamics
**难度:** 高级
**业务角色:** 平台分析

**解题思路:**
链路 `ad_auction_log → ad_campaign → advertiser`,`WHERE` 锁定一个广告主。CTE `bid_performance_buckets` 按出价档算赢拍率,外层用窗口函数 `LAG() OVER (ORDER BY avg_bid_in_bucket)` 取相邻档的赢拍率和出价,算出"边际弹性 = 赢拍率增幅 / 出价增幅"。grain = 一个出价档一行。**LAG 是算边际弹性的关键工具**(把相邻两档错位相减)。弹性分母用 `NULLIF` 防零。弹性最高的档 = 最划算的加价点;过了某档弹性陡降 = 加钱意义不大。

```sql
WITH bid_performance_buckets AS (
    SELECT
        ac.advertiser_id,
        a.company_name,
        aal.campaign_id,
        CASE
            WHEN aal.bid_cpm < 15 THEN '$0-15'
            WHEN aal.bid_cpm < 20 THEN '$15-20'
            WHEN aal.bid_cpm < 25 THEN '$20-25'
            WHEN aal.bid_cpm < 30 THEN '$25-30'
            ELSE '$30+'
        END AS bid_bucket,
        ROUND(AVG(aal.bid_cpm), 2) AS avg_bid_in_bucket,
        COUNT(*) AS total_bids,
        SUM(CASE WHEN aal.won_auction THEN 1 ELSE 0 END) AS auctions_won,
        ROUND(100.0 * SUM(CASE WHEN aal.won_auction THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate_pct
    FROM ad_auction_log aal
    JOIN ad_campaign ac ON aal.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    WHERE a.company_name = 'Adobe'
    GROUP BY ac.advertiser_id, a.company_name, aal.campaign_id, bid_bucket
)
SELECT
    company_name,
    bid_bucket,
    avg_bid_in_bucket,
    total_bids,
    auctions_won,
    win_rate_pct,
    LAG(win_rate_pct) OVER (ORDER BY avg_bid_in_bucket) AS prev_bucket_win_rate,
    ROUND(win_rate_pct - LAG(win_rate_pct) OVER (ORDER BY avg_bid_in_bucket), 1) AS win_rate_gain,
    ROUND((avg_bid_in_bucket - LAG(avg_bid_in_bucket) OVER (ORDER BY avg_bid_in_bucket)), 2) AS bid_increase,
    ROUND((win_rate_pct - LAG(win_rate_pct) OVER (ORDER BY avg_bid_in_bucket)) /
        NULLIF((avg_bid_in_bucket - LAG(avg_bid_in_bucket) OVER (ORDER BY avg_bid_in_bucket)), 0), 2) AS win_rate_elasticity
FROM bid_performance_buckets
ORDER BY avg_bid_in_bucket;
```

**结果解读:**
- 弹性最高的区间 (~$22-24) = 最划算的加价点
- > $28 后弹性陡降 → 加钱意义小

---

## Query 25: 新兴广告主行业趋势

**业务背景:**
销售战略团队要找 **下一波要重点拓展的广告主行业**。哪个行业 **月环比 (MoM)** 花费快速上涨?哪个在下滑?这条查询识别快速增长行业。
(注:真实业务里常看季度环比 QoQ,但本数据集只有 60 天,只能做月环比;方法论一致。)

**业务知识:**
- **MoM (Month-over-Month):** 月环比 — 本月 vs 上月 (数据跨度足够时换成 QoQ 季度环比即可)
- **Vertical (垂直行业):** 广告主所属细分行业
- **Sales Resource Allocation:** 销售把销售代表往高增长行业倾斜

**分类:** Strategic Insights
**难度:** 中级
**业务角色:** 平台策略

**解题思路:**
链路 `ad_impression → ad_creative → ad_campaign → advertiser`,CTE `monthly_spend` 按"行业×月"聚合花费,外层用 `LAG() OVER (PARTITION BY industry_vertical ORDER BY month)` 算月环比。**`PARTITION BY` 让每个行业各自独立算环比**,不会串台。**为什么是 MoM 不是 QoQ**:本数据集只有 60 天 (横跨约 3 个自然月),做季度环比会全落同一季度、LAG 全为 NULL——注释里已说明,方法论一致,数据跨度够时换成 QoQ 即可。grain = 行业×月。`CASE` 给爆发/高增长/下滑分类。

```sql
-- 注:本数据集只有 60 天 (横跨约 3 个自然月),做季度环比 (QoQ) 会全落在同一季度 →
-- LAG 全为 NULL。这里改成 **月环比 (MoM)**,在 60 天窗口里能产出 2-3 个对比点。
WITH monthly_spend AS (
    SELECT
        a.industry_vertical,
        DATE(ai.impression_time, 'start of month') AS month,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_spend,
        COUNT(DISTINCT ac.advertiser_id) AS active_advertisers,
        COUNT(ai.id) AS total_impressions
    FROM ad_impression ai
    JOIN ad_creative acr ON ai.creative_id = acr.id
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    GROUP BY a.industry_vertical, month
)
SELECT
    industry_vertical,
    month AS current_month,
    total_spend AS current_month_spend,
    active_advertisers,
    LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month) AS prev_month_spend,
    ROUND(total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 2) AS spend_change,
    ROUND(100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
        NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0), 1) AS growth_rate_pct,
    CASE
        WHEN 100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
            NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0) >= 50 THEN '🚀 爆发:重点拓展'
        WHEN 100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
            NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0) >= 20 THEN '📈 高增长:加投'
        WHEN 100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
            NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0) <= -20 THEN '📉 下滑:复盘'
        ELSE '➡️ 稳定'
    END AS trend_status
FROM monthly_spend
WHERE month >= DATE('2026-06-21', '-6 months')
ORDER BY month DESC, growth_rate_pct DESC;
```

**结果解读:**
- SaaS / FinTech 通常 40-80% 增长
- AI Tools / Web3 等新兴行业可能 150%+
- 下滑行业 — 区分宏观 (整个行业不行) vs 平台特殊问题 (被竞品抢走份额)

---

## Query 26: 节目分类增长预测

**业务背景:**
内容合作团队要预测 **下一年应该签哪类节目**。Tech 类已经饱和?Mental Health 是不是新蓝海?这条查询基于历史趋势预测 6 个月后的收入水平。

**业务知识:**
- **Compound Growth (复合增长):** 月环比 × 6 而非简单线性外推
- **Creator Recruitment:** 内容合作 BD 团队的"签约名单"决定平台 2 年后的样子

**分类:** Strategic Insights
**难度:** 高级
**业务角色:** 平台策略

**解题思路:**
用汇总表 `revenue_settlement → podcast`,CTE 按"分类×月"聚合。这是全文档**窗口函数最密集**的一题:外层先用多个 `LAG(total_revenue, 1/2)` 取前 1、前 2 个月的收入,再把环比公式套进 `AVG(...) OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` 算 3 个月移动平均增长。grain = 分类×月。注意 SQLite 支持这种"LAG 嵌在 AVG OVER 里"的写法,但要分清每个窗口的 `PARTITION BY category`。按 3 月均增长排序定签约优先级。

```sql
WITH monthly_category_revenue AS (
    SELECT
        p.category,
        DATE(rs.settlement_date, 'start of month') AS month,
        COUNT(DISTINCT p.id) AS podcast_count,
        SUM(rs.total_impressions) AS total_impressions,
        ROUND(SUM(rs.total_revenue_usd), 2) AS total_revenue,
        ROUND(AVG(rs.avg_cpm), 2) AS avg_cpm,
        ROUND(AVG(rs.fill_rate), 3) AS avg_fill_rate
    FROM revenue_settlement rs
    JOIN podcast p ON rs.podcast_id = p.id
    GROUP BY p.category, month
)
SELECT
    category,
    podcast_count,
    month AS latest_month,
    total_revenue AS current_month_revenue,
    LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month) AS prev_month_revenue,
    LAG(total_revenue, 2) OVER (PARTITION BY category ORDER BY month) AS two_months_ago_revenue,
    ROUND(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
        NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0), 1) AS mom_growth_pct,
    ROUND(AVG(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
        NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0))
        OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS three_month_avg_growth_pct,
    CASE
        WHEN AVG(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
            NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0))
            OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) >= 10 THEN '🎯 高优先:重点拓展'
        WHEN AVG(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
            NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0))
            OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) >= 5 THEN '✓ 中优先:维持渠道'
        ELSE '➡️ 稳定:机会型签约'
    END AS recruitment_strategy
FROM monthly_category_revenue
WHERE month >= DATE('2026-06-21', '-6 months')
ORDER BY three_month_avg_growth_pct DESC;
```

**结果解读:**
- 高增长类:Tech / Finance 12-18% MoM → 重金签约头部
- 成熟类:News 3-5% → 不主动

---

## Query 27: 听众行为变化侦测

**业务背景:**
产品战略团队要 **早期预警** 听众行为变化。例:倍速播放比例突然涨 10pp → 听众想效率 → 是否做"自动加速" 功能?智能音箱占比涨 → 优化语音 UX。

**业务知识:**
- **Behavior Shift Detection:** 用统计方法侦测 KPI 显著变化
- **Product Roadmap Implications:** 这些变化直接影响下一季度产品方向

**分类:** Strategic Insights
**难度:** 高级
**业务角色:** 平台策略

**解题思路:**
主表 `play_session` `LEFT JOIN ad_impression`,CTE `behavior_trends` 按月聚合倍速占比、各设备占比、广告跳过率等行为指标,外层用 `LAG()` 与上月比、用 `CASE` 触发警报。`WHERE` 限近 6 个月。grain = 一个月一行。占比类用 `SUM(CASE WHEN ... THEN 1 ELSE 0 END) / COUNT(*)`(如 `playback_speed > 1.0` 算倍速占比)。任一指标月度跳变超阈值 (完播率 ±5pp / 倍速 ±8pp / 跳过率 ±0.1) 就报警,给产品路线图早期预警。

```sql
WITH behavior_trends AS (
    SELECT
        DATE(ps.session_start_time, 'start of month') AS month,
        COUNT(DISTINCT ps.id) AS total_sessions,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
        ROUND(100.0 * SUM(CASE WHEN ps.playback_speed > 1.0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_accelerated_playback,
        ROUND(100.0 * SUM(CASE WHEN ps.device_type = 'mobile' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mobile,
        ROUND(100.0 * SUM(CASE WHEN ps.device_type = 'smart_speaker' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_smart_speaker,
        ROUND(100.0 * SUM(CASE WHEN ps.device_type = 'desktop' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_desktop,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS avg_ad_skip_rate
    FROM play_session ps
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE ps.session_start_time >= DATE('2026-06-21', '-6 months')
    GROUP BY month
)
SELECT
    month,
    total_sessions,
    avg_completion_pct,
    LAG(avg_completion_pct) OVER (ORDER BY month) AS prev_month_completion,
    ROUND(avg_completion_pct - LAG(avg_completion_pct) OVER (ORDER BY month), 1) AS completion_change,
    pct_accelerated_playback,
    LAG(pct_accelerated_playback) OVER (ORDER BY month) AS prev_month_accelerated,
    ROUND(pct_accelerated_playback - LAG(pct_accelerated_playback) OVER (ORDER BY month), 1) AS accelerated_change,
    pct_mobile,
    pct_smart_speaker,
    pct_desktop,
    avg_ad_skip_rate,
    CASE
        WHEN ABS(avg_completion_pct - LAG(avg_completion_pct) OVER (ORDER BY month)) >= 5 THEN '⚠️ 警报:完播率显著变化'
        WHEN ABS(pct_accelerated_playback - LAG(pct_accelerated_playback) OVER (ORDER BY month)) >= 8 THEN '⚠️ 警报:倍速行为变化'
        WHEN ABS(avg_ad_skip_rate - LAG(avg_ad_skip_rate) OVER (ORDER BY month)) >= 0.1 THEN '⚠️ 警报:广告容忍度变化'
        ELSE '✓ 稳定'
    END AS behavior_alert
FROM behavior_trends
ORDER BY month DESC;
```

**结果解读:**
- 倍速 28% → 38% (+10pp) → 产品该考虑自动加速功能
- 智能音箱 18% → 26% → 语音 UX 优化优先级提升
- 跳过率 0.42 → 0.53 (+11pp) → 广告疲劳全平台 → 紧急降频

---

# 总结:实习生应掌握的核心心智模型

读完这 27 条查询,你应该掌握:

### 1. 业务三方利益不对称
| 角色 | 想要 | 怕什么 |
|------|------|--------|
| 平台 | 收入大 | 听众流失,广告主撤资 |
| 广告主 | 转化高 / CPA 低 | 钱花了没效果 |
| 主播 | RPM 高 | 平台抽得多,听众跑了 |
| 听众 | 没广告 / 体验好 | 烦人广告 / 反复广告 |

### 2. 核心 trade-off 永远存在
- **填充率 vs 价格**:卖完了价格压低,卖不完空着浪费
- **广告频次 vs 听众体验**:多塞赚得多,塞太多被跳过
- **精准定向 vs 触达量**:窄了花不出去,宽了浪费钱

### 3. 数据分析的三种基本动作
1. **诊断 (Diagnose)** — 现状如何?Q1, Q2, Q4
2. **对标 (Benchmark)** — 跟同行比如何?Q13
3. **预测 (Forecast)** — 未来怎么走?Q15, Q26

### 4. 业务话术 vs 技术话术

| 技术语言 | 业务语言 (向 PM / 老板汇报时这么说) |
|---------|--------------------------------------|
| "avg_realized_cpm 高于 base_cpm_rate 50%" | "这个广告位市场愿付远超我们定的价,建议提价 30%" |
| "fill_rate 是 65%" | "凌晨广告位有 1/3 卖不出去,每天损失 X 千美元" |
| "win_rate_elasticity = 4.6 at $20" | "在 $20 出价档,每加 $1 多赢 4.6% 的拍卖" |

---

**版本:** v1.0
**最后更新:** 2026-06-21

> 💡 **下一步:** 把这份文档当字典反复查。每完成一个 ad-hoc 提数需求,回来看相似的 query 是怎么写的,**复用 + 改造** 比从零写快 10 倍。
