# Ember Realms Saga 玩家经济与代充渠道健康度分析: SQL 查询

本文档覆盖数据集 `gaming_f2p_whale_monetization_medium` 的 20 道 SQL 查询。业务
背景、公司故事和五个核心业务问题请见
`01-gaming_f2p_whale_monetization_medium_business_context-cn.md`；表结构和字段
定义请见 `02-gaming_f2p_whale_monetization_medium_er_document-cn.md`。

**关于 REFERENCE_DATE。** 本数据集固定锚定在 `2026-06-30` 这一天, 所有查询里
凡是需要"今天"的地方都直接写字面量日期 `'2026-06-30'`, 而不是 `DATE('now')`——
这样无论什么时候运行, 结果都完全可复现。

## 如何使用本文档

你是 Pinnacle Peak Games 新入职的 Game Economy Analyst, 这份文档是你 manager
(Director of Live Operations) 交给你的第一批任务清单。每一道查询都包含五个部分:

1. **业务背景**: 谁在问这个问题, 为什么现在要问, 答案会用来做什么决定。
2. **标签**: SQL 技巧类别 / 难度 / 提问角色。
3. **解题思路**: 在看到 SQL 之前, 先讲清楚要连哪些表、按什么粒度聚合、要避开
   哪些坑(比如 JOIN 方向错了会不会重复计数)。
4. **SQL**: 可以直接在生成好的 SQLite 数据库上运行的查询。
5. **预期结果与业务结论**: 结果长什么样, 数字意味着什么, 以及看到这个结果后
   你下一步该做什么。

20 道查询里, 每一道都能回溯到业务背景文档里 5 个业务问题(Q1-Q5)之一, 或者是
支撑日常运营监控的操作性查询。SQL 本身是用来学的, 不只是用来跑的——建议你先读
"解题思路"再看 SQL, 而不是反过来对着 SQL 抄思路。

## 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| 1 | 巨鲸收入集中度总览 | VP of Monetization & Publishing | Aggregation | Basic |
| 2 | 各付费分层的购买频次与客单价 | CFO | Aggregation | Basic |
| 3 | 生涯付费排行与百分位定位 | VP of Monetization & Publishing | Window Function | Intermediate |
| 4 | 抽卡池实际掉率逐池比对公示概率 | Senior Game Economy Analyst | Join + Aggregation | Intermediate |
| 5 | 常驻池 vs 限定池整体掉率对比 | Head of Game Design | Aggregation | Basic |
| 6 | Live-Ops 活动日历与扎堆识别 | Senior Game Economy Analyst | Window Function + Date/Time | Basic |
| 7 | 扎堆活动窗口期间的客单价变化 | Live Ops Program Manager | Join + Aggregation | Intermediate |
| 8 | 扎堆疲劳留存对照(剂量-反应分析) | Director of Live Operations | CTE + Aggregation | Advanced |
| 9 | 各支付渠道实付价占牌价比例 | Senior Game Economy Analyst | Join + Aggregation | Basic |
| 10 | 各支付渠道退款/拒付发生率 | Senior Game Economy Analyst | Join + Aggregation | Intermediate |
| 11 | 区域优惠码越界核销率(泄露 vs 正常) | Senior Game Economy Analyst | Join + Subquery | Intermediate |
| 12 | 代充/马甲号相关的高风险交易明细 | Trust & Safety Analyst | Join + Pattern Matching | Intermediate |
| 13 | 设备指纹共享账号团伙风险率 | Trust & Safety Lead | CTE + Aggregation | Advanced |
| 14 | 疑似欺诈团伙成员名单 | Trust & Safety Lead | Subquery | Basic |
| 15 | 月度收入趋势与 3 个月移动平均 | CFO | Window Function + Date/Time | Intermediate |
| 16 | 客服工单分类分布与 SLA 表现 | Player Support Manager | Aggregation | Basic |
| 17 | 安装月度 cohort 的 30 天留存曲线 | Senior Game Economy Analyst | CTE + Date/Time | Intermediate |
| 18 | 获客渠道质量对比 | Senior Game Economy Analyst | Join + Aggregation | Intermediate |
| 19 | 各计费地区收入与套利地区占比 | CFO | Join + Aggregation | Basic |
| 20 | 五大陷阱综合评分卡 | VP of Monetization & Publishing | CTE + Subquery | Advanced |

---

## Query 1: 巨鲸收入集中度总览

**业务背景**

VP of Monetization & Publishing 下周要向 CEO 汇报"这门生意到底靠谁撑起来的"。
她听 Live Ops 团队提过一句"大概 1% 的玩家贡献了大部分收入", 但从没看过精确
数字。如果这个说法属实, 意味着公司应该认真考虑给这批人配一个类似"大客户
成功经理"的专属维系机制, 而不是把所有玩家一视同仁地推同一套活动。这道题
对应业务背景文档里的 Q1。

**标签**: Aggregation | Basic | VP of Monetization & Publishing

**解题思路**

这题只需要 `player` 和 `iap_transaction` 两张表。`player.player_segment`
已经在生成时按精确人数分好了层(whale/dolphin/minnow/non_payer), 所以不需要
自己写分位数逻辑, 直接按这一列 `GROUP BY` 即可。要注意用 `LEFT JOIN` 而不是
`INNER JOIN`——non_payer 玩家在 `iap_transaction` 里完全没有记录, 用
`INNER JOIN` 会把这整层玩家从结果里悄悄剔除, 让人误以为"没有不付费玩家"。
占比分母要用一个不带 `GROUP BY` 的标量子查询取全库总收入, 不能直接在
`GROUP BY` 结果里互相除。同样因为 `LEFT JOIN` 会给 non_payer 产生全 NULL 的
`paid_price_usd`, 分子的 `SUM(t.paid_price_usd)` 也必须包一层 `COALESCE(...,
0)`——否则 non_payer 那一行的 `pct_of_revenue` 会显示为空值而不是 0%, 让人误
以为这个指标算错了或者数据缺失。

**SQL**

```sql
SELECT
    p.player_segment,
    COUNT(DISTINCT p.id) AS player_count,
    ROUND(100.0 * COUNT(DISTINCT p.id) / (SELECT COUNT(*) FROM player), 2) AS pct_of_players,
    ROUND(COALESCE(SUM(t.paid_price_usd), 0), 2) AS total_revenue_usd,
    ROUND(100.0 * COALESCE(SUM(t.paid_price_usd), 0) / (SELECT SUM(paid_price_usd) FROM iap_transaction), 2) AS pct_of_revenue
FROM player p
LEFT JOIN iap_transaction t ON t.player_id = p.id
GROUP BY p.player_segment
ORDER BY total_revenue_usd DESC;
```

**预期结果与业务结论**

4 行, 每个付费分层一行。whale 只占玩家总数的 1%, 却贡献约 65.8% 的收入;
dolphin 占 3%, 贡献约 28.4%; minnow 占 6%, 贡献约 5.7%; non_payer 占 90%,
贡献 0%。前 4%(whale+dolphin)合计贡献了超过 90% 的收入。下一步行动: 建议
VP 批准为 whale 单独设立专属客户维系流程(比如异常行为优先人工复核、专属
客服通道), 因为这批人一旦流失, 收入冲击是断崖式的, 不是线性的。

---

## Query 2: 各付费分层的购买频次与客单价

**业务背景**

CFO 想更进一步理解 Query 1 的收入差距是怎么来的: 是巨鲸买得更频繁, 还是
巨鲸每次买得更贵, 还是两者都是? 这决定了下个季度的商品定价策略应该往哪个
方向使劲。

**标签**: Aggregation | Basic | CFO

**解题思路**

这次只需要看已经产生过交易的玩家, 所以用 `INNER JOIN` 就够了(不像 Query 1
需要保留 non_payer)。核心是同时算两个比率: "人均交易笔数"(交易总数 /
去重玩家数)和"平均客单价"(`AVG(paid_price_usd)`), 两个数字放在一起看才能
判断收入差距的来源。

**SQL**

```sql
SELECT
    p.player_segment,
    COUNT(DISTINCT p.id) AS paying_players,
    COUNT(t.id) AS tx_count,
    ROUND(1.0 * COUNT(t.id) / COUNT(DISTINCT p.id), 1) AS avg_tx_per_player,
    ROUND(AVG(t.paid_price_usd), 2) AS avg_tx_value_usd
FROM player p
JOIN iap_transaction t ON t.player_id = p.id
GROUP BY p.player_segment
ORDER BY avg_tx_value_usd DESC;
```

**预期结果与业务结论**

3 行(whale/dolphin/minnow, non_payer 没有交易记录不会出现)。whale 人均
交易笔数最多(约 117 笔), 平均客单价也最高(约 67.9 美元); dolphin 人均约
50 笔、客单价约 22.8 美元; minnow 人均约 14 笔、客单价约 8.2 美元, 说明
巨鲸的收入优势是"买得更频繁"和"买得更贵"两者叠加, 而不是单靠某一个因素。下一步
行动: 商品团队可以针对 whale 设计更高客单价的档位(比如现有的 Ultimate Shard
Vault), 针对 dolphin 主推"提高购买频次"的订阅类商品(月卡/战令)。

---

## Query 3: 生涯付费排行与百分位定位

**业务背景**

VP of Monetization & Publishing 想要一份具体的"前 10 大玩家"名单, 而不只是
分层汇总——她要判断这批人里有没有已经很久没登录、值得专人挽留的高价值玩家。

**标签**: Window Function | Intermediate | VP of Monetization & Publishing

**解题思路**

用 `RANK()` 窗口函数按 `lifetime_spend_usd` 降序排名, 比先 `ORDER BY` 再
`LIMIT` 多了一个好处: 排名结果里如果出现并列(两人付费金额完全相同), `RANK()`
会给出相同名次, 不会武断地拆开——这在数据量小、金额可能重复时比单纯的
`ROW_NUMBER()` 更贴近业务直觉。百分位用排名除以全库玩家总数得到。

**SQL**

```sql
SELECT
    id AS player_id,
    player_segment,
    lifetime_spend_usd,
    RANK() OVER (ORDER BY lifetime_spend_usd DESC) AS spend_rank,
    ROUND(100.0 * RANK() OVER (ORDER BY lifetime_spend_usd DESC) / (SELECT COUNT(*) FROM player), 2) AS percentile_from_top
FROM player
ORDER BY lifetime_spend_usd DESC
LIMIT 10;
```

**预期结果与业务结论**

10 行, 全部是 `player_segment = 'whale'`, 生涯付费从约 15,200 美元往下排列,
`percentile_from_top` 都在 0.2% 以内。下一步行动: 把这份名单转给 Player
Support Manager, 交叉核对这 10 人最近的 `last_active_date` 和
`churn_risk_score`(这两列都直接落在 `player` 表上, 字段定义见 ER 文档
`player` 表), 对任何已经出现流失迹象的头部玩家启动一对一挽留流程。

---

## Query 4: 抽卡池实际掉率逐池比对公示概率

**业务背景**

你(Game Economy Analyst)拿到 Trust & Safety 转来的玩家投诉摘要, 里面有
零星几条"感觉限定池抽不出東西"的抱怨。在正式升级给 Head of Game Design 之前,
你需要先自己核实: 8 个抽卡池里, 是否真的存在某些卡池的实际 Legendary(传说)
掉率显著低于官方公示概率。这是全数据集里最敏感的一道题——如果坐实, 涉及的
不只是数据问题, 还有对玩家的诚信问题。对应业务背景文档 Q2。

**标签**: Join + Aggregation | Intermediate | Senior Game Economy Analyst

**解题思路**

`gacha_pool` 表只存官方公示概率, 真正抽到了什么稀有度记录在
`gacha_pull_log.result_rarity` 里, 所以必须 `JOIN` 两张表, 按
`gacha_pool.id` 聚合出每个卡池的实际 Legendary 占比, 再用这个实际值减去
公示值算出"缺口"(gap, 单位是百分点 pp, 不是"缺口占公示值的比例")。这里
必须按卡池 `id` 分组, 而不是先按 `pool_type`(常驻/限定)汇总——如果先按
`pool_type` 汇总, 5 个限定池里 2 个诚实的会把 3 个有问题的平均下来, 掩盖
具体是哪几个卡池的问题(Query 5 会专门演示这个陷阱)。

**SQL**

```sql
SELECT
    gp.pool_name,
    gp.pool_type,
    gp.disclosed_legendary_prob_pct AS disclosed_pct,
    COUNT(gpl.id) AS total_pulls,
    SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) AS legendary_count,
    ROUND(100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id), 2) AS actual_pct,
    ROUND(
        100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id)
        - gp.disclosed_legendary_prob_pct,
        2
    ) AS gap_pp
FROM gacha_pool gp
JOIN gacha_pull_log gpl ON gpl.gacha_pool_id = gp.id
GROUP BY gp.id
ORDER BY gap_pp ASC;
```

**预期结果与业务结论**

8 行, 按缺口从最负到最正排序。排在最前面的 3 个限定池(Anniversary
Celebration Banner 约 -2.25pp, Frostbound Knight Rate-Up Banner 约 -1.59pp,
Ember Queen Rate-Up Banner 约 -1.58pp)缺口都超过 1.5 个百分点; 其余 5 个
卡池(2 个限定池 + 3 个常驻池)缺口都在 ±0.5 个百分点以内, 属于正常抽样
噪声。下一步行动: 把这 3 个卡池标记为"需要立即升级给 Head of Game Design
和法务复核"的清单, 其余 5 个不需要升级。

---

## Query 5: 常驻池 vs 限定池整体掉率对比

**业务背景**

Head of Game Design 第一反应是"我们从来没系统性操纵过限定池", 想先看一眼
"常驻池整体"和"限定池整体"这种最粗粒度的对比, 判断有没有必要往下细查。

**标签**: Aggregation | Basic | Head of Game Design

**解题思路**

和 Query 4 几乎一样的 `JOIN`, 唯一区别是 `GROUP BY gp.pool_type` 而不是
`GROUP BY gp.id`。这道题存在的意义正是为了对比: 它自己给出的结论有多大程度
上是"正确但不够用"的。

还有一个容易对不上数字的 fan-out 加权细节要提前点破: `gacha_pool` 在 `JOIN`
到 `gacha_pull_log` 之后, 每个卡池的那一行会按它的抽卡笔数被复制成很多行, 所以
`AVG(gp.disclosed_legendary_prob_pct)` 得到的是**按抽卡笔数加权**的公示概率均值,
而不是"几个卡池的简单算术平均"。举例: 3 个常驻池的公示值是 2.0% / 3.0% / 5.0%,
简单平均是 (2.0+3.0+5.0)/3 = 3.33%, 但因为三个池的抽卡量并不相等, 加权之后
`avg_disclosed_pct` 会显示成约 3.19%。这不是算错, 只是读者若拿"简单平均"去核对
就会对不上, 心里要有数(如果确实想要简单平均, 应该先对 `gacha_pool` 去重再求均值)。

**SQL**

```sql
SELECT
    gp.pool_type,
    ROUND(AVG(gp.disclosed_legendary_prob_pct), 2) AS avg_disclosed_pct,
    COUNT(gpl.id) AS total_pulls,
    ROUND(100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id), 2) AS avg_actual_pct
FROM gacha_pool gp
JOIN gacha_pull_log gpl ON gpl.gacha_pool_id = gp.id
GROUP BY gp.pool_type;
```

**预期结果与业务结论**

2 行。`standard`(常驻池)公示均值约 3.19%, 实际约 3.44%, 基本吻合;
`limited_rateup`(限定池)公示均值约 3.13%, 实际约 2.07%, 整体缺口约
1.06 个百分点。这个整体缺口确实提示"限定池整体上有点问题", 但它做不到的是
告诉你具体该修哪几个——5 个限定池里有 2 个完全诚实, 如果只看这张汇总表就去
问责"限定池团队", 会冤枉设计 Shadowfang Assassin 和 Golden Phoenix 这两个
诚实卡池的策划。下一步行动: 必须回到 Query 4 的逐池结果, 精确定位到 3 个
具体卡池再采取行动, 不能止步于这张汇总表。

---

## Query 6: Live-Ops 活动日历与扎堆识别

**业务背景**

你要开始核实"活动排得太密"的说法, 第一步是先把全年活动日历过一遍, 确认
哪些活动确实符合"扎堆"(与上一场活动间隔不到 7 天)的定义, 而不是凭印象
猜测。

**标签**: Window Function + Date/Time | Basic | Senior Game Economy Analyst

**解题思路**

用 `LAG()` 窗口函数按 `start_date` 排序取出"上一场活动的结束日", 再用
`julianday()` 做日期差, 就能重新算出每场活动与上一场的间隔天数, 和
`live_ops_event.is_stacked_event` 这个已经落地的标记做交叉验证。这道题
本身不难, 但它是 Query 7、Query 8 的基础——先确认"扎堆"的定义站得住脚,
后面的留存分析才有意义。

**SQL**

```sql
SELECT
    id,
    event_name,
    event_type,
    start_date,
    end_date,
    is_stacked_event,
    LAG(end_date) OVER (ORDER BY start_date) AS previous_event_end_date,
    julianday(start_date) - julianday(LAG(end_date) OVER (ORDER BY start_date)) AS gap_days_from_previous
FROM live_ops_event
ORDER BY start_date;
```

**预期结果与业务结论**

30 行, 按时间顺序排列。`gap_days_from_previous` 小于 7 的行, 其
`is_stacked_event` 都应该是 1(true); 大于等于 7 的行都应该是 0(false)——
这道查询本身就是对 `is_stacked_event` 标记的一次独立复核。全年 30 场活动里
有 8 场被标记为扎堆, 集中在 4 个连续小簇里。下一步行动: 确认标记无误后,
把这 8 场活动的 `id` 传给 Query 7 和 Query 8 继续分析。

---

## Query 7: 扎堆活动窗口期间的客单价变化

**业务背景**

Live Ops Program Manager 想先看一个最直观的问题: 扎堆活动窗口期间, 玩家
是不是真的花得更多? 这是"活动拉动短期收入"这个假设的第一步验证, 还没有
涉及后续留存。

**标签**: Join + Aggregation | Intermediate | Live Ops Program Manager

**解题思路**

要判断一笔交易的 `transaction_date` 是否落在任意一个"扎堆活动窗口"内, 最
自然的写法是用一个相关子查询(correlated subquery)配合 `EXISTS`——对每笔
交易检查"是否存在至少一个扎堆活动的日期区间包含这笔交易日期"。这里不能用
简单的 `JOIN` 后 `GROUP BY transaction.id`, 否则如果一笔交易恰好落在两个
扎堆活动窗口的重叠区(理论上少见但不能排除), `JOIN` 会把这笔交易重复计数;
`EXISTS` 天然是"存在即可, 不重复"的语义, 更安全。

算完平均客单价之后, 顺便算一下 ARPPU(每付费玩家收入)会发现一个反直觉的
陷阱: 如果直接拿"窗口内总收入 / 窗口内去重付费玩家数"去和"窗口外总收入 /
窗口外去重付费玩家数"比, 窗口外的原始 ARPPU 反而会更高——这不是因为窗口外
付费效率更好, 而是因为 30 场活动里只有 8 场是扎堆活动, 窗口内总共只覆盖
72 个自然日, 窗口外却覆盖了从上线到 REFERENCE_DATE 之间剩余的 469 个自然日,
分母的"观察时长"完全不对等。正确做法是把两边的 ARPPU 都按各自窗口的自然日
天数做归一化(即 ARPPU / 天数), 才是公平的"付费效率"对比。

**SQL**

```sql
WITH stacked_windows AS (
    SELECT start_date, end_date FROM live_ops_event WHERE is_stacked_event = 1
),
tx_flagged AS (
    SELECT
        t.*,
        EXISTS (
            SELECT 1 FROM stacked_windows sw
            WHERE t.transaction_date BETWEEN sw.start_date AND sw.end_date
        ) AS in_stacked_window
    FROM iap_transaction t
)
SELECT
    in_stacked_window,
    COUNT(*) AS tx_count,
    COUNT(DISTINCT player_id) AS paying_players,
    ROUND(AVG(paid_price_usd), 2) AS avg_tx_value_usd,
    ROUND(SUM(paid_price_usd) / COUNT(DISTINCT player_id), 2) AS raw_arppu_usd,
    ROUND(
        SUM(paid_price_usd) / COUNT(DISTINCT player_id)
        / (CASE WHEN in_stacked_window THEN 72.0 ELSE 469.0 END),
        3
    ) AS arppu_per_day_usd
FROM tx_flagged
GROUP BY in_stacked_window;
```

`72.0` 和 `469.0` 分别是全年 8 场扎堆活动窗口的总天数, 和"上线日 2025-01-06
到 REFERENCE_DATE 2026-06-30"总观察期(541 天)减去这 72 天后的剩余天数——
两个数字都可以用 Query 6 的结果手动核对, 这里直接写成字面量, 和文档里
`REFERENCE_DATE` 的写法保持同一个原则: 常量直接写死, 保证可复现。

**预期结果与业务结论**

2 行。落在扎堆窗口内的交易(约 3,869 笔, 369 名付费玩家)平均客单价约
41.96 美元, 窗口外的交易(约 13,804 笔, 499 名付费玩家)平均客单价约
32.06 美元, 扎堆窗口内客单价高出约 31%。但如果只看 `raw_arppu_usd`
(窗口内约 439.94 美元, 窗口外约 886.94 美元), 会得出"窗口外付费效率更高"
这个错误结论——这正是术语表里提到的"ARPPU 会被活动假繁荣现象拉高"这句话
容易被误解的地方: 拉高的不是未经归一化的原始 ARPPU, 而是按天数归一化后的
`arppu_per_day_usd`。归一化后, 窗口内约 6.11 美元/天, 窗口外约 1.89 美元/天,
扎堆窗口内的付费效率大约是窗口外的 3.2 倍。下一步行动: 这证实了"扎堆活动
确实拉高了短期客单价和付费效率"这个假设的前半段;
但这只是硬币的一面, 必须继续看 Query 8 的留存数据, 才能判断这是不是"寅吃
卯粮"式的假繁荣。

---

## Query 8: 扎堆疲劳留存对照(剂量-反应分析)

**业务背景**

Director of Live Operations 要在两周后的董事会材料里给出最终结论: 高频
扎堆活动到底是净正贡献, 还是在透支玩家的留存? 这是全篇最关键的一道题,
直接决定下个季度的活动排期节奏要不要收紧。对应业务背景文档 Q3。

**标签**: CTE + Aggregation | Advanced | Director of Live Operations

**解题思路**

这道题最容易踩的坑是选错对照组。如果直接对比"参与过 >= 2 场扎堆活动的
玩家" vs "完全没参与过扎堆活动的玩家", 会得到一个违反直觉的结果: 后者
留存看起来反而更差——原因是"能参与到 2 场扎堆活动"这件事本身就要求玩家
活得够久, 天然筛选出了长期玩家(幸存者偏差), 这个偏差比疲劳效应本身还大,
会把结论完全带偏。正确的对照组应该是"剂量-反应"式的: 都已经参与过至少
1 场扎堆活动(意味着两组的"能活到遇上扎堆活动"这个前提是一样的), 再看
参与了 2 场及以上的人 和只参与了 1 场的人, 各自在"最后一场扎堆活动结束
30 天后是否还有活跃记录"上是否有差异。另外要注意右删失(right censoring):
如果某玩家最后一场扎堆活动的结束日期离 REFERENCE_DATE 不到 45 天, 就没有
足够的观察窗口判断"30 天后是否活跃", 必须把这些还没到观察期的玩家过滤掉,
否则会人为拉低两组的留存比例。

**SQL**

```sql
WITH stacked_exposure AS (
    SELECT
        ep.player_id,
        COUNT(*) AS stacked_count,
        MAX(loe.end_date) AS last_stacked_end
    FROM event_participation ep
    JOIN live_ops_event loe ON loe.id = ep.live_ops_event_id
    WHERE loe.is_stacked_event = 1
    GROUP BY ep.player_id
    HAVING COUNT(*) >= 1
)
SELECT
    CASE WHEN se.stacked_count >= 2 THEN 'exposed_2plus_fatigue_eligible' ELSE 'exposed_1_control' END AS cohort,
    COUNT(*) AS player_count,
    SUM(CASE WHEN p.last_active_date >= date(se.last_stacked_end, '+30 days') THEN 1 ELSE 0 END) AS active_30d_later,
    ROUND(
        100.0 * SUM(CASE WHEN p.last_active_date >= date(se.last_stacked_end, '+30 days') THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS pct_active_30d_later
FROM stacked_exposure se
JOIN player p ON p.id = se.player_id
WHERE date(se.last_stacked_end, '+45 days') <= '2026-06-30'
GROUP BY cohort;
```

**预期结果与业务结论**

2 行。只参与过 1 场扎堆活动的对照组(约 977 人), 30 天后仍有活跃记录的
比例约 34.5%; 参与过 2 场及以上的组(约 403 人), 这一比例降到约 23.6%,
低了约 11 个百分点。下一步行动: 建议 Director of Live Operations 在下季度
活动日历里, 把任意两场活动之间的最小间隔从当前偶尔出现的 3-4 天提高到
至少 10 天, 用 Query 7 证实的短期客单价提升去换 11 个百分点的留存损失,
这笔账算下来大概率不划算。

---

## Query 9: 各支付渠道实付价占牌价比例

**业务背景**

Trust & Safety 团队升级过来的第一手材料显示"疑似有玩家通过非官方渠道用
明显偏低的价格买到了水晶"。在追查具体是谁之前, 你需要先用数据证实: 不同
支付渠道的实付价相对官方牌价, 到底差多少。对应业务背景文档 Q4。

**标签**: Join + Aggregation | Basic | Senior Game Economy Analyst

**解题思路**

`iap_transaction` 已经同时存了 `list_price_usd`(按玩家所在地区折算的官方
牌价)和 `paid_price_usd`(实际到账金额), 所以只需要按渠道类型和是否官方
授权分组, 算 `paid_price_usd / list_price_usd` 的平均比例即可, 不需要额外
子查询。

**SQL**

```sql
SELECT
    cp.channel_type,
    cp.is_authorized,
    COUNT(*) AS tx_count,
    ROUND(100.0 * AVG(t.paid_price_usd / t.list_price_usd), 1) AS avg_paid_pct_of_list
FROM iap_transaction t
JOIN channel_partner cp ON cp.id = t.channel_partner_id
GROUP BY cp.channel_type, cp.is_authorized
ORDER BY avg_paid_pct_of_list;
```

**预期结果与业务结论**

4 行。未经授权的第三方代充渠道(`third_party_agent`, `is_authorized=false`)
实付价平均只有官方牌价的约 71.4%; 官方应用商店、官方网页直购、官方授权的
区域代收款伙伴, 实付价都在牌价的 106%-110% 左右(略高于 100% 是因为扎堆
活动期间的加价交易被计入了平均数, 见 Query 7)。下一步行动: 71.4% 这个
数字本身就是"未授权代充商靠什么赚钱"的答案——他们用比官方低约 30% 的价格
从低价地区批量买入, 再转卖给其他地区玩家, 中间的价差就是他们的利润, 而
公司在这些交易里损失了本该由官方渠道赚到的支付分成。

---

## Query 10: 各支付渠道退款/拒付发生率

**业务背景**

价格折价只是代充问题的一半, Trust & Safety Lead 更关心的是: 这些渠道来的
交易, 后续引发退款或拒付的比例是不是也偏高——拒付会让公司额外承担银行手续费
和信誉分。

**标签**: Join + Aggregation | Intermediate | Senior Game Economy Analyst

**解题思路**

这里必须用 `LEFT JOIN` 把 `refund_chargeback_risk_event` 接到
`iap_transaction` 上, 而不是 `INNER JOIN`——绝大多数交易根本没有引发任何
风险事件, 用 `INNER JOIN` 会把这些"正常"交易全部丢弃, 让分母(`tx_count`)
被严重低估, 算出来的风险率会虚高好几倍。分子分母都要用 `COUNT(DISTINCT
...)`, 因为理论上一笔交易可能对应不止一条风险记录(虽然本数据集里每笔
交易最多一条), 用 `DISTINCT` 更保险。

**SQL**

```sql
SELECT
    cp.channel_name,
    cp.is_authorized,
    COUNT(DISTINCT t.id) AS tx_count,
    COUNT(DISTINCT r.id) AS risk_events,
    ROUND(100.0 * COUNT(DISTINCT r.id) / COUNT(DISTINCT t.id), 1) AS risk_rate_pct
FROM iap_transaction t
JOIN channel_partner cp ON cp.id = t.channel_partner_id
LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
GROUP BY cp.id
ORDER BY risk_rate_pct DESC;
```

**预期结果与业务结论**

10 行, 每个支付渠道一行。5 个未授权代充商渠道的风险率普遍在约 17%-23% 区间
(把 5 个渠道合并计算约 20.5%), 远高于官方应用商店(同样因逐渠道输出, Apple 与
Google 各约 2.0%-2.4%)和官方网页(约 2.7%)。这里要留意粒度: 本查询 `GROUP BY cp.id`
是**逐渠道**输出, 所以 2 个
官方授权的区域代收款伙伴会各自成一行(SEA Regional Billing Partner 约 6.1%,
LatAm Regional Billing Partner 约 2.0%), 而不是合并成"约 4.2%"的一行——4.2% 是
这两个伙伴按 `is_authorized` 聚合后的整体基线值, 逐渠道拆开后因为每个伙伴各自只有
约 100 笔交易, 风险率会围绕该基线上下抖动。下一步行动: 把
"官方渠道 2%-3% 的基线风险率"作为公司内部的正常参考区间写进 Trust & Safety
的监控手册, 任何渠道风险率超过基线 3 倍以上(比如这 5 个未授权代充商)都
应触发自动人工复核。

---

## Query 11: 区域优惠码越界核销率(泄露 vs 正常)

**业务背景**

营销团队最近发现有几个原本只在东南亚/南美市场投放的区域专属优惠码, 使用
量高得反常。你需要核实这些码是不是被泄露到目标地区之外套利使用了。

**标签**: Join + Subquery | Intermediate | Senior Game Economy Analyst

**解题思路**

优惠码的"目标地区"记在 `discount_code.intended_region_scope`(存的是国家
全名字符串), 玩家的实际计费地区要经过 `player -> region_price_tier` 两次
`JOIN` 才能拿到国家全名, 两者做字符串不等比较(`<>`)就能标出"越界核销"。
只有 `intended_region_scope IS NOT NULL` 的区域专属码才适用这个概念, 全球
通用的邮件营销码/达人码要先用 `WHERE` 过滤掉, 否则它们会被误判成"全部越界"
(因为 `NULL <> 任何值` 在 SQL 里的结果是 `NULL`, 不会被计入 `SUM` 的
`CASE WHEN` 分支, 但也不该出现在这道题的讨论范围里, 干脆先排除更清晰)。

**SQL**

```sql
SELECT
    dc.leaked_beyond_scope,
    COUNT(*) AS redemptions,
    SUM(CASE WHEN rpt.country_name <> dc.intended_region_scope THEN 1 ELSE 0 END) AS out_of_scope_count,
    ROUND(100.0 * SUM(CASE WHEN rpt.country_name <> dc.intended_region_scope THEN 1 ELSE 0 END) / COUNT(*), 1) AS out_of_scope_pct
FROM iap_transaction t
JOIN discount_code dc ON dc.id = t.discount_code_id
JOIN player p ON p.id = t.player_id
JOIN region_price_tier rpt ON rpt.id = p.region_price_tier_id
WHERE dc.intended_region_scope IS NOT NULL
GROUP BY dc.leaked_beyond_scope;
```

**预期结果与业务结论**

2 行。已确认泄露的 4 个优惠码(`leaked_beyond_scope=1`), 核销记录里约
72.1% 发生在目标地区之外; 其余 15 个正常区域码(`leaked_beyond_scope=0`),
越界核销比例只有约 5.7%, 属于正常的偶发跨区旅行/VPN 噪声。下一步行动:
把这 4 个泄露码立即作废, 并用同样的"越界核销率"指标去巡检全部在售的区域
促销码, 超过 15%-20% 越界率的码优先复核。

---

## Query 12: 代充/马甲号相关的高风险交易明细

**业务背景**

Trust & Safety Analyst 需要一份可以直接拿去逐笔复核的交易清单, 而不是
汇总数字——董事会材料要汇总, 但实际执行(比如联系发卡行申诉拒付)需要
具体到每一笔交易。

**标签**: Join + Pattern Matching | Intermediate | Trust & Safety Analyst

**解题思路**

`refund_chargeback_risk_event.risk_note` 是一个枚举字段, 但可以用 `LIKE`
做关键词匹配来筛选出和"代充"(`agent`)以及"马甲号团伙"(`multi_account`)
相关的两类风险(区别于普通的 `genuine_dissatisfaction`), 这样即使未来
`risk_note` 的取值增加了新的细分类别(比如 `agent_sourced_dispute_v2`),
只要类别名里还含有 `agent` 关键词, 这条查询依然能捕捉到, 不用每次改枚举值
列表。

**SQL**

```sql
SELECT
    r.id AS risk_event_id,
    p.id AS player_id,
    p.player_segment,
    cp.channel_name,
    t.paid_price_usd,
    r.event_type,
    r.risk_note,
    r.resolution_status
FROM refund_chargeback_risk_event r
JOIN iap_transaction t ON t.id = r.iap_transaction_id
JOIN player p ON p.id = r.player_id
JOIN channel_partner cp ON cp.id = t.channel_partner_id
WHERE r.risk_note LIKE '%agent%' OR r.risk_note LIKE '%multi_account%'
ORDER BY t.paid_price_usd DESC
LIMIT 20;
```

**预期结果与业务结论**

20 行, 按涉及金额从高到低排序, 每行是一笔具体的风险交易, 可以直接核对
`channel_name` 是不是集中在那 5 个未授权代充商, 以及 `resolution_status`
里有多少还处于 `pending`(待处理)状态。下一步行动: 把 `resolution_status
= 'pending'` 且金额较大的记录列为本周优先处理清单, 交给 Trust & Safety
团队逐笔联系发卡行核实。

---

## Query 13: 设备指纹共享账号团伙风险率

**业务背景**

Trust & Safety Lead 要向公司证明"这不只是个别玩家反悔退款, 而是有组织的
团伙行为"——最直接的证据就是一批账号共享同一个设备指纹, 且这批账号的
退款/拒付发生率远高于正常水平。对应业务背景文档 Q5。

**标签**: CTE + Aggregation | Advanced | Trust & Safety Lead

**解题思路**

先用一个 CTE 找出哪些 `device_fingerprint_hash` 被 2 个及以上玩家共用
(`GROUP BY ... HAVING COUNT(*) >= 2`), 这一步本身就是"团伙识别"。接着用
这个 CTE 去左连接全体玩家, 把玩家分成"团伙成员"和"独立设备"两组, 分别算
风险事件发生率。这里同样要用 `LEFT JOIN` 而不是 `INNER JOIN`(理由同
Query 10), 而且要格外小心 `COUNT(DISTINCT ...)`——一个玩家可能有多笔交易
和多条风险记录, 如果不加 `DISTINCT` 直接 `COUNT(*)`, 会把"多笔交易 ×
多条风险记录"的笛卡尔积重复计数, 严重高估风险率。

**SQL**

```sql
WITH device_groups AS (
    SELECT device_fingerprint_hash, COUNT(*) AS ring_size
    FROM player
    GROUP BY device_fingerprint_hash
    HAVING COUNT(*) >= 2
)
SELECT
    CASE WHEN dg.ring_size IS NOT NULL THEN 'shared_device_ring' ELSE 'unique_device' END AS cohort,
    COUNT(DISTINCT p.id) AS player_count,
    COUNT(DISTINCT t.id) AS tx_count,
    COUNT(DISTINCT r.id) AS risk_events,
    ROUND(100.0 * COUNT(DISTINCT r.id) / NULLIF(COUNT(DISTINCT t.id), 0), 1) AS risk_rate_pct
FROM player p
LEFT JOIN device_groups dg ON dg.device_fingerprint_hash = p.device_fingerprint_hash
LEFT JOIN iap_transaction t ON t.player_id = p.id
LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
GROUP BY cohort;
```

**预期结果与业务结论**

2 行。共享设备指纹的团伙玩家(10 组, 共 48 人)风险事件发生率约 47.4%,
是独立设备玩家基线(约 2.5%)的近 19 倍。下一步行动: 这个近 19 倍的差距
足以支撑 Trust & Safety Lead 向法务和风控委员会提交"批量封禁 + 追回争议
款项"的正式提案, 而不只是逐个账号单独处理。

---

## Query 14: 疑似欺诈团伙成员名单

**业务背景**

Query 13 证明了"团伙"整体的风险率异常, 但执行封号需要一份具体到每个账号
的名单, 交给 Trust & Safety Lead 逐一审核后再执行。

**标签**: Subquery | Basic | Trust & Safety Lead

**解题思路**

用一个子查询先找出所有"被 2 个及以上账号共享"的 `device_fingerprint_hash`
值, 再用 `WHERE device_fingerprint_hash IN (...)` 把 `player` 表过滤到只剩
这些团伙成员, 按指纹分组排序方便人工逐组审阅。

**SQL**

```sql
SELECT
    p.id AS player_id,
    p.device_fingerprint_hash,
    p.install_date,
    p.player_segment,
    p.lifetime_spend_usd,
    p.churn_risk_score
FROM player p
WHERE p.device_fingerprint_hash IN (
    SELECT device_fingerprint_hash FROM player GROUP BY device_fingerprint_hash HAVING COUNT(*) >= 2
)
ORDER BY p.device_fingerprint_hash, p.id;
```

**预期结果与业务结论**

48 行, 按设备指纹分成 10 组, 每组 4-5 人。这份名单里绝大多数是
`non_payer`(生涯付费为 0), 只有少数几个是已经付过费的 `minnow` / `dolphin`。
这正是马甲团伙的典型形态: **大量从未付费的待激活空号 + 少数已付费的"操作号"**——
真正制造退款/拒付的是那几个已付费账号(它们做的是"先买后退"套利), 大批空号则
是随时可以顶上来的备用马甲, 一旦操作号被封就换一个继续。所以看这份名单不能只盯
`lifetime_spend_usd` 高不高, 共享同一枚设备指纹这件事本身就是团伙信号。下一步行动:
交给 Trust & Safety Lead 逐组整体封禁(付费号与空号一并处理), 并冻结待处理的退款申请。

---

## Query 15: 月度收入趋势与 3 个月移动平均

**业务背景**

CFO 要在董事会材料里放一张收入趋势图, 原始月度收入波动较大(受活动节奏
影响), 她希望看到一条更平滑的趋势线来判断整体方向。

**标签**: Window Function + Date/Time | Intermediate | CFO

**解题思路**

先用 CTE 把交易按月聚合出月度收入, 再用 `AVG() OVER (ORDER BY year_month
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` 算 3 个月移动平均——这里必须
先聚合再开窗, 如果直接在明细交易上开窗会导致同一个月内的移动平均值毫无
意义(粒度不对)。

**SQL**

```sql
WITH monthly AS (
    SELECT
        strftime('%Y-%m', transaction_date) AS year_month,
        SUM(paid_price_usd) AS revenue
    FROM iap_transaction
    GROUP BY year_month
)
SELECT
    year_month,
    ROUND(revenue, 2) AS revenue_usd,
    ROUND(AVG(revenue) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3mo_usd
FROM monthly
ORDER BY year_month;
```

**预期结果与业务结论**

18 行左右(覆盖 2025-01 到 2026-06)。2025 年 4 月出现一个明显的**早期收入尖峰**
(约 24,570 美元), 与 Ember Queen Rate-Up Banner 限定活动窗口重合; 但要注意这只是
游戏上线头几个月里的**局部高点**, 并非全期最高月——随着用户盘子做大, 后续 2026 年的
月收入普遍更高。3 个月移动平均线把这个早期尖峰磨平后, 能看出全年收入整体呈上升趋势。
下一步行动:
把这张移动平均趋势图放进董事会材料的"整体健康度"部分, 原始月度数字放进
附录供细看活动效应的人参考。

---

## Query 16: 客服工单分类分布与 SLA 表现

**业务背景**

Player Support Manager 每周要看一次工单大盘, 判断哪类问题堆积最多、解决
时效最差, 决定下周客服排班往哪个方向倾斜。

**标签**: Aggregation | Basic | Player Support Manager

**解题思路**

直接按 `category` 分组聚合即可, 同时算平均解决时长、高优先级工单数量和
平均满意度, 三个指标放在一起看, 才能判断"这类工单多"和"这类工单处理得差"
是不是同一件事。

**SQL**

```sql
SELECT
    category,
    COUNT(*) AS ticket_count,
    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
    SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) AS high_priority_count,
    ROUND(AVG(csat_score), 2) AS avg_csat
FROM support_ticket
GROUP BY category
ORDER BY ticket_count DESC;
```

**预期结果与业务结论**

5 行。`general_bug` 数量最多但优先级偏低; `billing_dispute`(账单纠纷)
和 `gacha_odds_complaint`(概率投诉)数量不算最多, 但值得结合 Query 4 的
结论重点关注——概率投诉工单如果在 Ember Queen / Frostbound Knight /
Anniversary 这几个限定池活跃期间出现聚集, 就是 Query 4 发现的问题已经
传导到客服端的证据。下一步行动: 建议客服团队给 `gacha_odds_complaint`
类别单独打标签按卡池统计, 作为 Query 4 分析结果的独立佐证来源。

---

## Query 17: 安装月度 cohort 的 30 天留存曲线

**业务背景**

Senior Game Economy Analyst(也就是你自己下个季度要交付的常规报表之一)
需要一条基础的留存曲线, 作为后续所有留存类分析(包括 Query 8)的背景参照——
如果不知道"正常"留存率大概是多少, 就无法判断扎堆活动造成的 11 个百分点
差距算大还是算小。

**标签**: CTE + Date/Time | Intermediate | Senior Game Economy Analyst

**解题思路**

按 `strftime('%Y-%m', install_date)` 把玩家分到安装月份的 cohort 里,
用 `julianday(last_active_date) - julianday(install_date) >= 30` 判断
这个玩家是否"活过了 30 天"(即最后一次活跃记录距安装日至少 30 天)。这里
用 `WHERE install_date <= '2026-05-31'` 提前把"安装还不满 30 天"的近期
新玩家排除掉, 否则这批玩家会被错误地计入"未留存", 拉低最近月份的留存率。
`REFERENCE_DATE` 是 `2026-06-30`, 要保证完整 30 天观察窗口, 截止日期必须
精确到 `2026-05-31`(5 月 31 日 + 30 天 = 6 月 30 日, 刚好够 30 天)——早一天
会多排除一天的合法安装用户。

**SQL**

```sql
WITH cohort AS (
    SELECT id, strftime('%Y-%m', install_date) AS install_month, install_date, last_active_date
    FROM player
    WHERE install_date <= '2026-05-31'
)
SELECT
    install_month,
    COUNT(*) AS installs,
    SUM(CASE WHEN julianday(last_active_date) - julianday(install_date) >= 30 THEN 1 ELSE 0 END) AS retained_30d,
    ROUND(
        100.0 * SUM(CASE WHEN julianday(last_active_date) - julianday(install_date) >= 30 THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS retention_30d_pct
FROM cohort
GROUP BY install_month
ORDER BY install_month;
```

**预期结果与业务结论**

约 17 行(每个安装月份一行)。全局 30 天留存率大致在 29%-55% 之间波动,
这就是本游戏"正常"的留存基准线。下一步行动: 把这条基准线作为 Query 8
结论的对照参照——扎堆疲劳组从对照组的 34.5% 降到 23.6%, 相当于比"这批
本来就已经参与过至少一场活动、更活跃的玩家"的正常水平还要低不少, 说明
疲劳效应是真实存在的, 不是数据噪声。

---

## Query 18: 获客渠道质量对比

**业务背景**

市场部下季度要重新分配用户获取(UA)预算, Senior Game Economy Analyst
需要给出"哪个获客渠道带来的玩家真正有付费价值"的结论, 而不只是看安装量。

**标签**: Join + Aggregation | Intermediate | Senior Game Economy Analyst

**解题思路**

`player.acquisition_channel` 已经是每个玩家自带的属性, 不需要额外
`JOIN` 别的表就能拿到安装量; 但要算"人均收入贡献", 需要把
`lifetime_spend_usd`(已经是预计算好的快照字段)按渠道汇总。付费转化率
用 `CASE WHEN player_segment != 'non_payer'` 的条件计数实现, 不需要额外
连接 `iap_transaction`。

**SQL**

```sql
SELECT
    p.acquisition_channel,
    COUNT(DISTINCT p.id) AS installs,
    COUNT(DISTINCT CASE WHEN p.player_segment != 'non_payer' THEN p.id END) AS paying_players,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN p.player_segment != 'non_payer' THEN p.id END) / COUNT(DISTINCT p.id),
        2
    ) AS payer_conversion_pct,
    ROUND(SUM(p.lifetime_spend_usd) / COUNT(DISTINCT p.id), 2) AS avg_revenue_per_install_usd
FROM player p
GROUP BY p.acquisition_channel
ORDER BY avg_revenue_per_install_usd DESC;
```

**预期结果与业务结论**

7 行, 每个获客渠道一行(Organic - App Store Search / Organic - Word of
Mouth / Meta Ads UA / TikTok Ads UA / Google UAC / AppLovin Network /
Influencer Partnership)。由于付费分层是随机独立分配的(与获客渠道没有
刻意设计的相关性), 各渠道的付费转化率和人均收入应该大致接近, 只在正常
抽样噪声范围内波动。下一步行动: 如果某个渠道的安装量占比明显偏高但
`avg_revenue_per_install_usd` 明显偏低, 提示市场部适当削减该渠道预算,
但要结合更长时间窗口的数据再做决定, 避免单季度噪声导致误判。

---

## Query 19: 各计费地区收入与套利地区占比

**业务背景**

CFO 想知道公司的收入地理分布, 顺便看一眼那些"套利高发地区"(土耳其、
阿根廷等)占了多大的收入盘子——这决定了如果公司调整这些地区的官方定价,
影响面有多大。

**标签**: Join + Aggregation | Basic | CFO

**解题思路**

从 `region_price_tier` 出发用 `LEFT JOIN` 逐步接上 `player` 和
`iap_transaction`(两次都要用 `LEFT JOIN`, 保留哪怕一笔交易都没有的地区),
按地区聚合收入和玩家数。

**SQL**

```sql
SELECT
    rpt.country_name,
    rpt.is_arbitrage_source_region,
    COUNT(DISTINCT p.id) AS player_count,
    ROUND(COALESCE(SUM(t.paid_price_usd), 0), 2) AS total_revenue_usd
FROM region_price_tier rpt
LEFT JOIN player p ON p.region_price_tier_id = rpt.id
LEFT JOIN iap_transaction t ON t.player_id = p.id
GROUP BY rpt.id
ORDER BY total_revenue_usd DESC;
```

**预期结果与业务结论**

10 行, 每个计费地区一行。美国、加拿大等非套利地区合计贡献大部分收入,
6 个套利高发地区(巴西、土耳其、阿根廷、菲律宾、印度、印尼)合计贡献
的收入占比相对更小, 但玩家数占比不低——这正是代充产业链的经济学基础:
这些地区玩家多但官方定价低, 天然有价差可套。下一步行动: 作为
Query 9/Query 10 结论的背景数据放进董事会材料, 帮助非运营背景的董事
理解"为什么代充问题偏偏出现在这几个地区"。

---

## Query 20: 五大陷阱综合评分卡

**业务背景**

VP of Monetization & Publishing 要在董事会材料的第一页放一张"一眼扫完
全部结论"的评分卡, 把前面 19 道查询里最核心的几个数字浓缩成 4 行, 后面
再逐一展开细节。

**标签**: CTE + Subquery | Advanced | VP of Monetization & Publishing

**解题思路**

用 4 个独立的 CTE 分别复用前面几道题的核心逻辑(巨鲸收入占比取自
Query 1、最差限定池缺口取自 Query 4、未授权代充渠道风险率取自 Query 10、
欺诈团伙风险率取自 Query 13), 每个 CTE 只返回一个标量值, 最后用
`UNION ALL` 把 4 个单值结果拼成一张纵向的评分卡。这种写法的好处是每个
指标的计算逻辑都独立可测, 不会因为塞进一个巨大的查询里而互相干扰。

**SQL**

```sql
WITH whale_share AS (
    SELECT ROUND(
        100.0 * SUM(CASE WHEN p.player_segment = 'whale' THEN t.paid_price_usd ELSE 0 END) / SUM(t.paid_price_usd),
        1
    ) AS metric_value
    FROM iap_transaction t
    JOIN player p ON p.id = t.player_id
),
gacha_worst_gap AS (
    SELECT ROUND(MIN(actual_pct - disclosed_pct), 2) AS metric_value
    FROM (
        SELECT
            gp.disclosed_legendary_prob_pct AS disclosed_pct,
            100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id) AS actual_pct
        FROM gacha_pool gp
        JOIN gacha_pull_log gpl ON gpl.gacha_pool_id = gp.id
        WHERE gp.pool_type = 'limited_rateup'
        GROUP BY gp.id
    )
),
agent_risk_rate AS (
    SELECT ROUND(100.0 * COUNT(DISTINCT r.id) / COUNT(DISTINCT t.id), 1) AS metric_value
    FROM iap_transaction t
    JOIN channel_partner cp ON cp.id = t.channel_partner_id
    LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
    WHERE cp.is_authorized = 0
),
fraud_ring_risk_rate AS (
    SELECT ROUND(100.0 * COUNT(DISTINCT r.id) / COUNT(DISTINCT t.id), 1) AS metric_value
    FROM player p
    JOIN iap_transaction t ON t.player_id = p.id
    LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
    WHERE p.device_fingerprint_hash IN (
        SELECT device_fingerprint_hash FROM player GROUP BY device_fingerprint_hash HAVING COUNT(*) >= 2
    )
)
SELECT 'Q1 巨鲸(前1%)收入占比(%)' AS trap_metric, metric_value FROM whale_share
UNION ALL
SELECT 'Q2 最差限定池概率缺口(pp)', metric_value FROM gacha_worst_gap
UNION ALL
SELECT 'Q4 未授权代充渠道风险事件率(%)', metric_value FROM agent_risk_rate
UNION ALL
SELECT 'Q5 设备指纹团伙风险事件率(%)', metric_value FROM fraud_ring_risk_rate;
```

**预期结果与业务结论**

4 行, 一目了然: 巨鲸收入占比约 65.8%; 最差限定池概率缺口约 -2.25 个百分点;
未授权代充渠道风险事件率约 20.5%; 设备指纹团伙风险事件率约 47.4%。下一步
行动: 这 4 个数字就是董事会材料第一页要放的核心结论, 每个数字后面配一句
"建议行动"(专属客户维系 / 卡池概率整改 / 代充渠道封堵 / 团伙账号封禁),
后续页码再展开各自的详细分析(对应 Query 1、4、10、13 的完整结果)。

## 业务问题与查询映射

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 巨鲸依赖 | Query 1, Query 2, Query 3, Query 20 |
| Q2 概率池披露偏差 | Query 4, Query 5, Query 20 |
| Q3 Live-Ops 活动假繁荣 | Query 6, Query 7, Query 8, Query 17 |
| Q4 代充/优惠渠道套利 | Query 9, Query 10, Query 11, Query 12, Query 19, Query 20 |
| Q5 退款欺诈团伙 | Query 12, Query 13, Query 14, Query 20 |
| 运营监控(非直接对应某个 Q, 但支撑日常复盘) | Query 15, Query 16, Query 18 |
