# SQL 查询文档

本文档覆盖 `social_media_music_blanket_licensing_medium` 数据集，业务背景请见 `01-social_media_music_blanket_licensing_medium_business_context-cn.md`。数据结构请见 `02-social_media_music_blanket_licensing_medium_er_document-cn.md`。

## REFERENCE_DATE 约定

本数据集所有"今天/当前快照"的语义都锚定在固定参考日 **`2026-06-30`**。每条查询里凡是需要"当前日期"的地方，都直接写死这个日期字面量，而不是 `DATE('now')`——这样无论谁在什么时候重新跑这些查询，结果都完全一致、可复现。

## 如何使用本文档

你是刚加入 ReelWave Rights & Licensing Compliance 团队的分析师，Director 把这 20 道题作为这一周的上手任务交给你。每道题都有五个固定部分：

1. **业务语境**——谁在问这个问题、为什么现在问、答案会支撑什么决策。
2. **标签**——SQL 类别、难度、提问的业务角色。
3. **解题思路**——动手写 SQL 之前，先想清楚要连哪些表、用什么粒度聚合、有没有连接陷阱。
4. **SQL**——可以直接在生成的 SQLite 数据库上跑通的查询。
5. **预期结果与结论**——结果长什么样、对应哪个业务问题、看完之后该做什么。

每道题都能追溯到业务背景文档第 5 节列出的某个业务问题（Q1-Q4）。这些 SQL 不只是用来执行的，更是用来学习"一个真实分析师拿到这类问题会怎么想"的示范。

## 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| 1 | 当月厂牌曲库使用份额 vs 签约假设 | Rights & Licensing Compliance Officer | Join + Aggregation | Basic |
| 2 | 近 3 个月平均份额漂移排名 | Director of Rights Compliance | Window Function | Intermediate |
| 3 | 各厂牌有效费率计算与排名 | VP of Finance (FP&A) | CTE | Intermediate |
| 4 | MFN 条款违反检测 | General Counsel | CTE + Subquery | Advanced |
| 5 | 版权冲突标记状态分布 | Rights & Licensing Compliance Officer | Aggregation | Basic |
| 6 | SLA 逾期标记数量与风险敞口 | Director of Rights Compliance | Date/Time + Aggregation | Intermediate |
| 7 | 按来源厂牌统计采样引发的版权冲突 | Head of Label Relations | Join (Self-Join) | Basic |
| 8 | 逾期天数最长的 Top 10 版权冲突 | Rights & Licensing Compliance Officer | Window Function | Intermediate |
| 9 | Creator Fund 按爆火窗口对齐状态的有效费率对比 | Creator Fund Program Manager | CTE + Aggregation | Advanced |
| 10 | 单个跨周案例的周度分成环比变化 | Creator Fund Program Manager | Window Function (LAG) | Intermediate |
| 11 | Creator Fund 总支出按创作者层级拆分 | Creator Fund Program Manager | Aggregation | Basic |
| 12 | 单个爆款 remix 的每日播放曲线 vs 周度分成 | Rights & Licensing Compliance Officer | Join + Date/Time | Intermediate |
| 13 | 厂牌组合结构总览 | Head of Label Relations | Aggregation | Basic |
| 14 | 合同实付累计 vs 按时间进度应付金额 | VP of Finance (FP&A) | Join + Date/Time | Intermediate |
| 15 | 曲库构成：官方曲目 vs UGC remix | Rights & Licensing Compliance Officer | Aggregation | Basic |
| 16 | 份额漂移 Top 5 / Bottom 5 厂牌 | Director of Rights Compliance | Window Function | Intermediate |
| 17 | 季度合规风险优先级清单 | Director of Rights Compliance | CTE (多表综合) | Advanced |
| 18 | 二创声音标题关键词模式匹配 | Rights & Licensing Compliance Officer | Pattern Matching | Basic |
| 19 | 平台月度可归属曲库用量趋势 | Head of Label Relations | Date/Time Trend | Basic |
| 20 | 续约优先级清单（到期临近 + 份额漂移） | Head of Label Relations | CTE + Window Function | Advanced |

---

## Query 1: 当月厂牌曲库使用份额 vs 签约假设

**业务语境**

你是 Rights & Licensing Compliance Officer，Director 让你为下周的季度合规评审准备第一张幻灯片：把每个厂牌"当前实际用了多少"和"签约时我们以为它会用多少"放在一起看。这是整份报告最核心的一张表——如果差距很大，后面所有关于续约、补款、风险敞口的讨论都要围绕它展开。现在是季度末，正好是回顾过去一个月数据最合适的时点。

**标签**：Join + Aggregation ｜ Basic ｜ Rights & Licensing Compliance Officer

**解题思路**

一个视频用了哪个厂牌的曲子，取决于两种情况：视频直接用了该厂牌的官方曲目，或者视频用的是某个采样了该厂牌官方曲目的 UGC remix。所以第一步要用一个 CTE 把 `sound` 表"拆"成"能归属到某个厂牌的声音清单"——用 `UNION ALL` 把"官方曲目自己"和"采样了官方曲目的 remix（通过 `source_sound_id` 找到源官方曲目再找到 `primary_label_id`）"拼在一起。第二步用这份清单去连 `sound_monthly_usage`，按厂牌聚合当月 `video_count`。第三步算出当月"可归属曲库"总量作为分母，两者相除得到实际份额，再减去 `label_blanket_license.usage_share_assumption_pct` 得到漂移。这里不需要窗口函数，一次 GROUP BY 加一次 CROSS JOIN（拿总量）就够。

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
)
SELECT
    l.label_name,
    l.label_tier,
    lbl.usage_share_assumption_pct,
    ROUND(mu.label_video_count * 100.0 / t.total_video_count, 2) AS actual_usage_share_pct,
    ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp
FROM month_usage mu
JOIN label l
    ON l.id = mu.label_id
JOIN label_blanket_license lbl
    ON lbl.label_id = l.id
CROSS JOIN total t
ORDER BY drift_pp DESC;
```

**预期结果与业务结论**

结果是 20 行（每个厂牌一行）。`drift_pp` 为正代表这个厂牌"越用越多但年费没涨"，为负代表"越用越少但年费没降"。排在最前面的几家（约 5 家"growth"型厂牌）`drift_pp` 应在 +1 到 +4.5 个百分点之间，排在最后面的几家（约 4 家"decline"型厂牌）应在 -2 到 -4.8 个百分点之间，其余约 11 家（含全部 3 家大型厂牌）在 ±1 个百分点内。下一步动作：把 `drift_pp` 绝对值最大的几家列进续约谈判优先级清单（Query 20 会给出更结构化的版本），准备在下一轮谈判里重新核算年费。

---

## Query 2: 近 3 个月平均份额漂移排名

**业务语境**

Director of Rights Compliance 看了 Query 1 的单月快照后，担心某个月的数据可能有偶然波动，要求你用最近 3 个月的平均值重新算一遍，确保排在前面的厂牌不是"一个月的运气"，而是持续性趋势。这份排名会被直接放进下周提交给 General Counsel 的简报里。

**标签**：Window Function ｜ Intermediate ｜ Director of Rights Compliance

**解题思路**

思路和 Query 1 类似，但这次要按厂牌和月份两个维度聚合，然后用窗口函数 `SUM(...) OVER (PARTITION BY usage_month)` 算出"每个月各自的总量"（不能用一个全局总量，因为月与月之间总盘子在增长）。拿到每个厂牌每月的份额后，再按厂牌做一次 `AVG`，得到 3 个月的平均实际份额，最后用 `RANK() OVER (ORDER BY drift_pp DESC)` 排名。注意 `WHERE usage_month IN (...)` 要精确写出这 3 个月的月初日期，SQLite 存的是字符串日期，写成 `'2026-04-01'` 这种完整格式才能精确匹配。

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
monthly_share AS (
    SELECT
        ls.label_id,
        smu.usage_month,
        SUM(smu.video_count) AS label_video_count,
        SUM(SUM(smu.video_count)) OVER (PARTITION BY smu.usage_month) AS month_total_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month IN ('2026-04-01', '2026-05-01', '2026-06-01')
    GROUP BY ls.label_id, smu.usage_month
),
label_avg_share AS (
    SELECT
        label_id,
        AVG(label_video_count * 100.0 / month_total_video_count) AS avg_share_pct
    FROM monthly_share
    GROUP BY label_id
)
SELECT
    l.label_name,
    l.label_tier,
    lbl.usage_share_assumption_pct,
    ROUND(las.avg_share_pct, 2) AS avg_actual_share_pct_last3m,
    ROUND(las.avg_share_pct - lbl.usage_share_assumption_pct, 2) AS drift_pp,
    RANK() OVER (ORDER BY las.avg_share_pct - lbl.usage_share_assumption_pct DESC) AS growth_rank
FROM label_avg_share las
JOIN label l
    ON l.id = las.label_id
JOIN label_blanket_license lbl
    ON lbl.label_id = l.id
ORDER BY drift_pp DESC;
```

**预期结果与业务结论**

结果 20 行，`growth_rank = 1` 到 `5` 应该稳定对应 Query 1 里份额上涨最快的那批厂牌，数值和单月快照相比波动不大（说明是持续趋势而非偶然）。下一步动作：`growth_rank` 前 5 且合同年费未做过调整的厂牌，列入下季度重新谈判年费的候选名单；`growth_rank` 倒数几名（decline 型）列入"续约时考虑降低年费或缩小份额假设"的候选名单。

---

## Query 3: 各厂牌有效费率计算与排名

**业务语境**

VP of Finance (FP&A) 在准备年度预算复盘时，想知道公司在打包授权上到底是按什么"隐含单价"付钱的——把每份合同的年费换算成"每拿下 1 个百分点的曲库份额，我们愿意付多少钱"，方便和其他厂牌、其他年份的合同做横向比较。

**标签**：CTE ｜ Intermediate ｜ VP of Finance (FP&A)

**解题思路**

这题本身逻辑不复杂——年费除以份额假设就是有效费率——但用一个 CTE 把这个计算独立出来，是因为 Query 4 的 MFN 检测要复用同一个"有效费率"定义。把计算逻辑放进 CTE 而不是直接写在 SELECT 里，可以保证两道题对"有效费率"的定义完全一致，不会出现两处口径打架的风险。

**SQL**

```sql
WITH effective_rate AS (
    SELECT
        lbl.label_id,
        lbl.has_mfn_clause,
        lbl.usage_share_assumption_pct,
        lbl.annual_license_fee_usd,
        lbl.annual_license_fee_usd / lbl.usage_share_assumption_pct AS effective_rate_per_point_usd
    FROM label_blanket_license lbl
)
SELECT
    l.label_name,
    l.label_tier,
    er.has_mfn_clause,
    er.usage_share_assumption_pct,
    er.annual_license_fee_usd,
    ROUND(er.effective_rate_per_point_usd, 0) AS effective_rate_per_point_usd
FROM effective_rate er
JOIN label l
    ON l.id = er.label_id
ORDER BY effective_rate_per_point_usd DESC;
```

**预期结果与业务结论**

结果 20 行，按有效费率从高到低排列。规律不是简单的"major > mid > indie"，真正拉开差距的是**有没有 MFN 保护**：

- 带 MFN 保护、且报价正常的 4 家厂牌（2 家 major + 2 家 mid_size）有效费率整体最高，约 84 万到 96 万美元/份额点——因为 MFN 条款写死了"费率不能比别人差"，它们被系统性抬到全场最高，其中带 MFN 的中型厂牌完全可能高过某些大型厂牌。
- **Northline Aggregator**（一家没有 MFN 保护的独立聚合发行商）靠激进报价冲到约 80 万美元/点，挤进榜单前列。
- **Titan Sound Group**（带 MFN 保护的 major）却被压在约 75 万美元/点，反而低于 Northline——这正是 Query 4 要抓的 MFN 违反线索。
- 其余没有 MFN 保护的中型厂牌和独立聚合发行商整体更低（约 28 万到 62 万美元/点）。

换句话说，榜单前列由"带 MFN 的厂牌 + Northline"混合占据，并不严格按厂牌规模排序。下一步动作：把这份排名交给 Query 4 做 MFN 合规检测。

---

## Query 4: MFN 条款违反检测

**业务语境**

General Counsel 上周收到一封 Titan Sound Group 法务团队的邮件，隐约提到"想重新核对一下我们的费率条款"。General Counsel 怀疑这可能是在为一次合同违约索赔做铺垫，要求 Rights & Licensing Compliance 团队在下周正式回复前，先自己算一遍：有没有任何带 MFN（最惠国）保护的厂牌，实际拿到的有效费率反而比后来签约、没有 MFN 保护的厂牌更差。如果有，需要立刻评估追溯补差的金额敞口。

**标签**：CTE + Subquery ｜ Advanced ｜ General Counsel

**解题思路**

判断 MFN 有没有被违反，核心逻辑是两步：第一步找出"所有没有 MFN 保护的厂牌里，有效费率最高的那个值"（用一个子查询的 `MAX(...)`）；第二步检查每一家带 MFN 保护的厂牌，它自己的有效费率是不是低于第一步算出来的那个最高值。如果低于，说明这家厂牌本该按 MFN 条款被"補齐"到那个最高值，但合同里没有体现——这就是违反。这里复用 Query 3 定义的 `effective_rate` CTE，再加一个 `non_mfn_max` CTE 存放非 MFN 厂牌里的最高有效费率，最后用 `WHERE has_mfn_clause = 1 AND effective_rate_per_point_usd < max_rate` 过滤出真正违反的记录，并顺手算出补差的年化金额敞口（"应该达到的费率" 减去 "实际费率"，再乘以这家厂牌的份额假设）。

**SQL**

```sql
WITH effective_rate AS (
    SELECT
        lbl.label_id,
        lbl.has_mfn_clause,
        lbl.usage_share_assumption_pct,
        lbl.annual_license_fee_usd / lbl.usage_share_assumption_pct AS effective_rate_per_point_usd
    FROM label_blanket_license lbl
),
non_mfn_max AS (
    SELECT MAX(effective_rate_per_point_usd) AS max_rate
    FROM effective_rate
    WHERE has_mfn_clause = 0
)
SELECT
    l.label_name,
    l.label_tier,
    ROUND(er.effective_rate_per_point_usd, 0) AS own_effective_rate_usd,
    ROUND(nm.max_rate, 0) AS max_non_mfn_rate_usd,
    ROUND(nm.max_rate - er.effective_rate_per_point_usd, 0) AS rate_shortfall_per_point_usd,
    ROUND((nm.max_rate - er.effective_rate_per_point_usd) * er.usage_share_assumption_pct, 0) AS annual_exposure_usd
FROM effective_rate er
JOIN label l
    ON l.id = er.label_id
CROSS JOIN non_mfn_max nm
WHERE er.has_mfn_clause = 1
  AND er.effective_rate_per_point_usd < nm.max_rate
ORDER BY annual_exposure_usd DESC;
```

**预期结果与业务结论**

结果应该只有 **1 行**：Titan Sound Group。它的有效费率（约 75 万美元/点）低于 Northline Aggregator（一家没有 MFN 保护、但后来靠更高报价拿下的独立聚合发行商，约 80 万美元/点），`annual_exposure_usd` 应在 70 万到 80 万美元量级。下一步动作：这是一个真实的合同违约风险，需要立刻升级给 General Counsel，评估是主动补签费率调整协议，还是等对方提出索赔——拖延只会让追溯期变长、敞口变大。

---

## Query 5: 版权冲突标记状态分布

**业务语境**

你是 Rights & Licensing Compliance Officer，每周一都要给团队做一次"版权冲突看板"更新。今天的第一件事，是先看清楚现在手上到底积压了多少条待处理的标记，分布在哪些状态。

**标签**：Aggregation ｜ Basic ｜ Rights & Licensing Compliance Officer

**解题思路**

这是最简单的一类题——按 `resolution_status` 分组计数，再算一下每类占比和对应的风险敞口金额总和。唯一要注意的地方是"占比"的分母要用一个子查询单独算总数，而不是想当然地用 `COUNT(*) OVER ()` 之类更复杂的写法——五种状态、几十条记录，用子查询完全够用，没必要上窗口函数。

**SQL**

```sql
SELECT
    resolution_status,
    COUNT(*) AS flag_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rights_conflict_flag), 1) AS pct_of_total,
    ROUND(SUM(revenue_at_risk_usd), 2) AS total_revenue_at_risk_usd
FROM rights_conflict_flag
GROUP BY resolution_status
ORDER BY flag_count DESC;
```

**预期结果与业务结论**

结果 5 行，对应 `open`、`under_review`、`cleared`、`takedown`、`licensed_retroactively` 五种状态。`open` 加 `under_review` 两类合计占比约 43%——意味着四成多的标记还没有走完流程。下一步动作：把 `open` 状态里 `revenue_at_risk_usd` 最高的几条挑出来，优先分配稽核资源（配合 Query 8 使用）。

---

## Query 6: SLA 逾期标记数量与风险敞口

**业务语境**

Director of Rights Compliance 每个季度要向 General Counsel 汇报一次"我们内部约定的 30 天处理时限，到底有没有被遵守"。这不只是流程效率问题——处理越慢，被认定为"平台明知道风险还继续赚广告费"的法律风险就越大。

**标签**：Date/Time Analysis + Aggregation ｜ Intermediate ｜ Director of Rights Compliance

**解题思路**

"逾期"需要分两种情况计算，不能用同一个公式：已经解决的记录，用 `resolved_date - flagged_date` 和 30 天比；还没解决的记录（`open` 或 `under_review`），`resolved_date` 是空的，只能用"参考日 `2026-06-30` 减去 `flagged_date`"来判断已经拖了多久。这里用 SQLite 的 `JULIANDAY()` 函数把日期转成儒略日再相减，得到天数差。用一个 `CASE WHEN` 把两种情况和"完全没超时"三种状态分到一个 `sla_bucket` 字段里，再聚合。

**SQL**

```sql
SELECT
    CASE
        WHEN resolution_status IN ('open', 'under_review')
             AND (JULIANDAY('2026-06-30') - JULIANDAY(flagged_date)) > sla_days_target
            THEN 'overdue_still_open'
        WHEN resolved_date IS NOT NULL
             AND (JULIANDAY(resolved_date) - JULIANDAY(flagged_date)) > sla_days_target
            THEN 'overdue_resolved_late'
        ELSE 'within_sla'
    END AS sla_bucket,
    COUNT(*) AS flag_count,
    ROUND(SUM(revenue_at_risk_usd), 2) AS revenue_at_risk_usd
FROM rights_conflict_flag
GROUP BY sla_bucket
ORDER BY revenue_at_risk_usd DESC;
```

**预期结果与业务结论**

结果 3 行。`overdue_still_open` 和 `overdue_resolved_late` 两类合计占比应在 60%-65% 之间，对应的 `revenue_at_risk_usd` 汇总约在 20 万到 22 万美元量级。下一步动作：如果逾期占比超过 40%，需要在下季度合规报告里向 General Counsel 提出增加稽核人手的申请，而不是继续用现有节奏"消化"积压。

---

## Query 7: 按来源厂牌统计采样引发的版权冲突

**业务语境**

Head of Label Relations 注意到，最近几次续约谈判里，有厂牌代表提到"你们平台上到处都是我们歌的盗版 remix，你们管得也太松了"。他想知道这个说法有没有数据支撑——具体是哪些厂牌的官方曲目最容易被 UGC remix"惹上"版权冲突。

**标签**：Join (Self-Join) ｜ Basic ｜ Head of Label Relations

**解题思路**

`rights_conflict_flag.remix_sound_id` 指向的是 remix 本身，要找到这个 remix "惹的祸"源自哪个厂牌，需要经过两次 JOIN：先从 `rights_conflict_flag` 连到 `sound`（拿到 remix 这一行），再用 remix 的 `source_sound_id` 二次连接 `sound` 表本身（拿到它采样的官方曲目），最后从官方曲目的 `primary_label_id` 连到 `label`。这是一个典型的"表自己连自己"场景，两次出现的 `sound` 表需要用不同别名（`remix` 和 `official`）区分，否则 SQL 引擎分不清你说的是哪一行。

**SQL**

```sql
SELECT
    l.label_name,
    l.label_tier,
    COUNT(rcf.id) AS conflict_count,
    ROUND(SUM(rcf.revenue_at_risk_usd), 2) AS total_revenue_at_risk_usd
FROM rights_conflict_flag rcf
JOIN sound remix
    ON remix.id = rcf.remix_sound_id
JOIN sound official
    ON official.id = remix.source_sound_id
JOIN label l
    ON l.id = official.primary_label_id
GROUP BY l.id
ORDER BY conflict_count DESC;
```

**预期结果与业务结论**

结果行数等于"至少有一首官方曲目被采样后引发过版权冲突"的厂牌数量（不超过 20 行），按冲突数量降序排列。下一步动作：把排名前几位的厂牌名单反馈给 Head of Label Relations，在续约谈判里主动提及"我们已经在加强这方面的稽核"，而不是被动等对方投诉。

---

## Query 8: 逾期天数最长的 Top 10 版权冲突

**业务语境**

你（Rights & Licensing Compliance Officer）刚才在 Query 6 看到整体逾期比例后，现在需要一份具体的"个案清单"——到底是哪几条记录拖得最久，好在今天下班前分配给团队成员逐一跟进。

**标签**：Window Function ｜ Intermediate ｜ Rights & Licensing Compliance Officer

**解题思路**

"已解决"和"未解决"两类记录的"逾期天数"算法不同（参考 Query 6），这里用同一个 `CASE WHEN` 表达式计算出统一的 `days_open`，然后用 `RANK() OVER (ORDER BY days_open DESC)` 给每条记录一个排名，最后用 `LIMIT 10` 只取前十。用窗口函数而不是直接 `ORDER BY ... LIMIT 10`，是为了在结果里保留 `overdue_rank` 这一列，方便团队成员用"第几名"互相沟通，而不是只看一堆没有编号的行。

**SQL**

```sql
SELECT
    rcf.remix_sound_id,
    s.title,
    rcf.conflict_type,
    rcf.flagged_date,
    rcf.resolution_status,
    rcf.resolved_date,
    ROUND(
        CASE
            WHEN rcf.resolved_date IS NOT NULL
                THEN JULIANDAY(rcf.resolved_date) - JULIANDAY(rcf.flagged_date)
            ELSE JULIANDAY('2026-06-30') - JULIANDAY(rcf.flagged_date)
        END, 0
    ) AS days_open,
    RANK() OVER (
        ORDER BY
            CASE
                WHEN rcf.resolved_date IS NOT NULL
                    THEN JULIANDAY(rcf.resolved_date) - JULIANDAY(rcf.flagged_date)
                ELSE JULIANDAY('2026-06-30') - JULIANDAY(rcf.flagged_date)
            END DESC
    ) AS overdue_rank
FROM rights_conflict_flag rcf
JOIN sound s
    ON s.id = rcf.remix_sound_id
ORDER BY days_open DESC
LIMIT 10;
```

**预期结果与业务结论**

结果 10 行，`days_open` 从最大值依次递减，最长的几条应远超过 30 天 SLA（部分可能超过 100 天）。下一步动作：把这 10 条按 `resolution_status` 分给团队里对应负责"未授权采样"或"权属重复申领"的成员，今天之内至少推进状态更新。

---

## Query 9: Creator Fund 按爆火窗口对齐状态的有效费率对比

**业务语境**

Creator Fund Program Manager 最近收到几个头部创作者的私信抱怨——"我这条视频明明比上个月那条爆得更狠，怎么分成反而更少？"她怀疑这和 Creator Fund 按自然周结算的规则有关系，想先用数据验证一下：爆火窗口"完整落在一周内"和"跨越两周"的声音，实际拿到的分成率是不是真的不一样。

**标签**：CTE + Aggregation ｜ Advanced ｜ Creator Fund Program Manager

**解题思路**

这题的关键是找到正确的对比分组：`sound.spike_week_alignment` 字段已经把 120 个被追踪的热门声音分成了 `aligned` 和 `split_across_weeks` 两类，只需要把 `creator_fund_weekly_payout` 按这个字段分组聚合。"有效分成率"不能简单算每行的 `payout_usd / weekly_view_count` 再取平均——那样会让播放量小的周被过度加权。正确做法是先把两组的 `payout_usd` 和 `weekly_view_count` 分别求和，再相除，得到"整体口径下"的每千次播放分成率，这样大播放量的周自然占更大权重，更接近真实的资金分配情况。记得用 `WHERE s.is_trending_monitored = 1` 限定在有对齐状态标记的声音范围内，否则 `spike_week_alignment` 为 NULL 的行会单独成组，干扰对比。

**SQL**

```sql
SELECT
    s.spike_week_alignment,
    COUNT(DISTINCT s.id) AS sound_count,
    SUM(cfwp.weekly_view_count) AS total_views,
    ROUND(SUM(cfwp.payout_usd), 2) AS total_payout_usd,
    ROUND(SUM(cfwp.payout_usd) * 1000.0 / SUM(cfwp.weekly_view_count), 4) AS payout_rate_per_1000_views
FROM creator_fund_weekly_payout cfwp
JOIN sound s
    ON s.id = cfwp.remix_sound_id
WHERE s.is_trending_monitored = 1
GROUP BY s.spike_week_alignment;
```

**预期结果与业务结论**

结果 2 行。`aligned` 组的 `payout_rate_per_1000_views` 应在约 1.14-1.25 美元附近，`split_across_weeks` 组应低约 28%-30%（约 0.80-0.90 美元）。下一步动作：这证实了创作者的抱怨有数据依据——Creator Fund Program Manager 需要向产品团队提出，把按自然周结算改成"按创作者自己视频的滚动 7 天窗口"结算，或者至少对跨周案例做一次性补偿。

---

## Query 10: 单个跨周案例的周度分成环比变化

**业务语境**

Creator Fund Program Manager 想拿一个具体、有说服力的案例去说服产品团队，而不是只甩一个抽象的百分比。她让你挑出受影响最大的一个跨周声音，把它逐周的播放量和分成金额环比变化列出来，做成一页 PPT 里的图表素材。

**标签**：Window Function (LAG) ｜ Intermediate ｜ Creator Fund Program Manager

**解题思路**

先用一个 CTE 从所有 `split_across_weeks` 声音里，按累计分成金额排序选出最具代表性的一个（分成金额最高，说明它确实火过，但仍然被规则拖累）。选定这个声音后，用 `LAG(payout_usd) OVER (ORDER BY week_start_date)` 拿到"上一周的分成金额"，和当周做对比，就能清楚看到分成在跨周那一刻掉了多少。这里不需要 `PARTITION BY`，因为已经用 `WHERE` 把范围收窄到了单一 `remix_sound_id`。

**SQL**

```sql
WITH top_split_sound AS (
    SELECT cfwp.remix_sound_id
    FROM creator_fund_weekly_payout cfwp
    JOIN sound s
        ON s.id = cfwp.remix_sound_id
    WHERE s.spike_week_alignment = 'split_across_weeks'
    GROUP BY cfwp.remix_sound_id
    ORDER BY SUM(cfwp.payout_usd) DESC
    LIMIT 1
)
SELECT
    s.title,
    cfwp.week_start_date,
    cfwp.weekly_view_count,
    cfwp.payout_usd,
    LAG(cfwp.payout_usd) OVER (ORDER BY cfwp.week_start_date) AS prev_week_payout_usd,
    ROUND(
        cfwp.payout_usd - LAG(cfwp.payout_usd) OVER (ORDER BY cfwp.week_start_date),
        2
    ) AS wow_change_usd
FROM creator_fund_weekly_payout cfwp
JOIN sound s
    ON s.id = cfwp.remix_sound_id
WHERE cfwp.remix_sound_id = (SELECT remix_sound_id FROM top_split_sound)
ORDER BY cfwp.week_start_date;
```

**预期结果与业务结论**

结果是该声音全部结算周的逐行记录，行数等于它从上线到 REFERENCE_DATE 之间的周数。爆火发生的那两周附近，`weekly_view_count` 应该出现明显跳升，但 `payout_usd` 的跳升幅度会因为跨周被"摊薄"而不如预期。下一步动作：把这个案例连同 Query 9 的整体统计一起放进给产品团队的提案里。

---

## Query 11: Creator Fund 总支出按创作者层级拆分

**业务语境**

Creator Fund Program Manager 每季度要向财务汇报一次 Creator Fund 的实际花销结构——头部创作者、中部创作者、长尾创作者分别拿走了多少，用来判断这笔预算是不是真的在往"扶持更多普通创作者"的目标上花，而不是全被头部拿走。

**标签**：Aggregation ｜ Basic ｜ Creator Fund Program Manager

**解题思路**

标准的分组聚合：按 `creator.creator_tier` 分组，汇总 `payout_usd`，再算一下人均分成方便和"头部创作者是不是拿得不成比例"这个问题对照。唯一要注意的是 `COUNT(DISTINCT c.id)`，因为一个创作者可能有多个 remix、每周多条分成记录，不去重会把创作者人数算错。

**SQL**

```sql
SELECT
    c.creator_tier,
    COUNT(DISTINCT c.id) AS creator_count,
    ROUND(SUM(cfwp.payout_usd), 2) AS total_payout_usd,
    ROUND(SUM(cfwp.payout_usd) / COUNT(DISTINCT c.id), 2) AS avg_payout_per_creator_usd
FROM creator_fund_weekly_payout cfwp
JOIN creator c
    ON c.id = cfwp.creator_id
GROUP BY c.creator_tier
ORDER BY total_payout_usd DESC;
```

**预期结果与业务结论**

结果 3 行（top / mid / long_tail）。`avg_payout_per_creator_usd` 在 top 组应远高于 long_tail 组，这符合"平台效应天然向头部集中"的预期，本身不是陷阱，是运营现状。下一步动作：作为 Query 9/10 揭示的"跨周低估"问题的背景板——如果长尾创作者本来分成就少，跨周规则造成的额外损失对他们的相对影响会更大，这一点值得在提案里一并提及。

---

## Query 12: 单个爆款 remix 的每日播放曲线 vs 周度分成

**业务语境**

你要给 Director of Rights Compliance 做一次内部培训，用一个具体案例讲清楚"为什么按自然周结算会系统性低估某些创作者"。抽象的百分比不够直观，你想找一个真实的爆款声音，把它每天的播放曲线和它对应的周度分成金额放在一起看。

**标签**：Join + Date/Time ｜ Intermediate ｜ Rights & Licensing Compliance Officer

**解题思路**

先用一个 CTE 挑出"属于 split_across_weeks 类型、且单日播放峰值最高"的那个声音——这样能保证案例既有代表性（跨周），又足够爆（数字好看，讲课有说服力）。然后用 `UNION ALL` 把这个声音的"每日播放明细"（来自 `sound_daily_viral_window`）和"每周分成明细"（来自 `creator_fund_weekly_payout`）拼在同一个结果集里，用 `granularity` 列区分两种粒度，按日期排序后交替展示。这样读结果的人能直观看到：某几天播放量猛涨，但涨势横跨了两个 `week_start_date`，导致任何一周单独看分成都不算离谱地高。

**SQL**

```sql
WITH top_viral_sound AS (
    SELECT s.id AS sound_id
    FROM sound s
    JOIN sound_daily_viral_window sdw
        ON sdw.sound_id = s.id
    WHERE s.spike_week_alignment = 'split_across_weeks'
    GROUP BY s.id
    ORDER BY MAX(sdw.daily_view_count) DESC
    LIMIT 1
)
SELECT
    'daily' AS granularity,
    usage_date AS period_start,
    daily_view_count AS view_count,
    NULL AS payout_usd
FROM sound_daily_viral_window
WHERE sound_id = (SELECT sound_id FROM top_viral_sound)

UNION ALL

SELECT
    'weekly' AS granularity,
    week_start_date AS period_start,
    weekly_view_count AS view_count,
    payout_usd
FROM creator_fund_weekly_payout
WHERE remix_sound_id = (SELECT sound_id FROM top_viral_sound)

ORDER BY period_start, granularity;
```

**预期结果与业务结论**

结果混合了逐日和逐周两种粒度的行，`payout_usd` 只在 `granularity = 'weekly'` 的行上有值。仔细看日期能发现：播放量的峰值集中在某个周五到下周一之间的几天，正好横跨两个 `week_start_date`。下一步动作：把这个案例做成一页对比图，作为 Query 9 结论的具体佐证，用于内部培训和产品提案。

---

## Query 13: 厂牌组合结构总览

**业务语境**

Head of Label Relations 新接手这个组合，想先有一个"全局体检报告"——三种厂牌类型各自的数量、平均份额假设、MFN 覆盖率和年费总盘子分别是多少，作为后续所有细项分析的背景板。

**标签**：Aggregation ｜ Basic ｜ Head of Label Relations

**解题思路**

按 `label_tier` 分组，把 `label` 和 `label_blanket_license` 连起来算平均份额假设、MFN 覆盖数量和年费总和。`has_mfn_clause` 存的是 0/1，直接 `SUM(CASE WHEN has_mfn_clause = 1 THEN 1 ELSE 0 END)` 就能数出每个 tier 里有几家带 MFN 保护，不需要额外的子查询。

**SQL**

```sql
SELECT
    l.label_tier,
    COUNT(*) AS label_count,
    ROUND(AVG(lbl.usage_share_assumption_pct), 2) AS avg_usage_share_assumption_pct,
    SUM(CASE WHEN lbl.has_mfn_clause = 1 THEN 1 ELSE 0 END) AS mfn_protected_count,
    ROUND(SUM(lbl.annual_license_fee_usd), 0) AS total_annual_fee_usd
FROM label l
JOIN label_blanket_license lbl
    ON lbl.label_id = l.id
GROUP BY l.label_tier
ORDER BY total_annual_fee_usd DESC;
```

**预期结果与业务结论**

结果 3 行（major / mid_size / indie_aggregator）。`major` 类型的 `label_count` 最少（3 家）但 `total_annual_fee_usd` 应该最高，`mfn_protected_count` 应等于 3（全部大型厂牌都带 MFN）；`mid_size` 类型的 `mfn_protected_count` 应为 2；`indie_aggregator` 类型应为 0。下一步动作：作为组合结构背景，配合后续每一份细项分析一起呈现给 Head of Label Relations。

---

## Query 14: 合同实付累计 vs 按时间进度应付金额

**业务语境**

VP of Finance (FP&A) 在做现金流对账时，想确认每份合同目前的实际累计付款，是否跟合同已经走过的时间比例大致匹配——如果某份合同"该付的还没付"，可能是财务流程卡住了；如果"付多了"，可能是重复付款或者计算错误。

**标签**：Join + Date/Time ｜ Intermediate ｜ VP of Finance (FP&A)

**解题思路**

先用一个 CTE 把每份合同的 `license_fee_payment` 汇总成"累计实付金额"和"已付款期数"。然后用 `JULIANDAY('2026-06-30') - JULIANDAY(contract_start_date)` 算出合同已经生效了多少天，除以 365 得到"已过去的年数比例"，乘以 `annual_license_fee_usd` 就是"按时间进度理论上应该已经付了多少"。两者相减得到 `variance_usd`，正值代表多付，负值代表少付。

**SQL**

```sql
WITH paid AS (
    SELECT
        license_id,
        SUM(amount_paid_usd) AS cumulative_paid_usd,
        COUNT(*) AS payments_made
    FROM license_fee_payment
    GROUP BY license_id
)
SELECT
    l.label_name,
    lbl.contract_start_date,
    lbl.annual_license_fee_usd,
    p.cumulative_paid_usd,
    p.payments_made,
    ROUND(
        (JULIANDAY('2026-06-30') - JULIANDAY(lbl.contract_start_date)) / 365.0 * lbl.annual_license_fee_usd,
        0
    ) AS expected_cumulative_paid_usd,
    ROUND(
        p.cumulative_paid_usd
            - (JULIANDAY('2026-06-30') - JULIANDAY(lbl.contract_start_date)) / 365.0 * lbl.annual_license_fee_usd,
        0
    ) AS variance_usd
FROM paid p
JOIN label_blanket_license lbl
    ON lbl.id = p.license_id
JOIN label l
    ON l.id = lbl.label_id
ORDER BY variance_usd;
```

**预期结果与业务结论**

结果 20 行。因为 `license_fee_payment` 覆盖了每份合同从签约日至今的全部季度付款，`expected_cumulative_paid_usd`（按时间进度应付）和 `cumulative_paid_usd`（实付）口径一致，`variance_usd` 不会出现"老合同只保留近 2 年付款、凭空缺一大截"那种百万级系统性负差。

需要理解的一点是：季度授权费是**后付制**（一个季度走完、结算完才付款），所以参考日总会落在"当前这一季还没结算"的中途，实付天然比"按天数比例应付"少一点点——`variance_usd` 会普遍是**小幅负值**，且幅度上限约等于该合同**一个季度的年费**（`annual_license_fee_usd / 4`）。大型厂牌年费高（上千万美元），这个"一个季度的滞后"换算成绝对额也更大（可能到几十万甚至一两百万美元），但相对合同规模仍属正常范围，不是漏付。

另外，`variance_usd` 也可能出现**小幅正值**（本数据集有几家，最大约 43 万美元）。这不是"多付"，而是"季度额按 `年费/4` 计，但每个自然季度的实际天数与 `365/4` 略有出入，再叠加每期 ±1% 的付款噪声"带来的离散化残差——只要正差的绝对值仍在**一个季度年费以内**，就和小幅负差一样属于正常范围。

下一步动作：判断标准对正负两个方向是统一的——真正要交给财务单独核实的，是 `variance_usd` 绝对值**明显超过该合同一个季度年费**的合同：正差远超一个季度年费才可能是重复付款，负差远超才可能是漏付或流程卡壳。反过来，凡是绝对值仍落在一个季度年费以内的（无论正负、也无论大型厂牌绝对额看起来多大），都属正常滞后/噪声，不必逐一核实。

---

## Query 15: 曲库构成：官方曲目 vs UGC remix

**业务语境**

你（Rights & Licensing Compliance Officer）要给新入职的团队成员做一次入门培训，第一步是让对方直观理解"Sounds"曲库到底由什么构成——官方曲目和用户二创各占多少、曲风分布如何。

**标签**：Aggregation ｜ Basic ｜ Rights & Licensing Compliance Officer

**解题思路**

最基础的 `GROUP BY sound_type, genre` 加计数，没有陷阱，是整份文档里最简单的一题，专门留给刚上手、还在熟悉数据表结构的场景。

**SQL**

```sql
SELECT
    sound_type,
    genre,
    COUNT(*) AS sound_count
FROM sound
GROUP BY sound_type, genre
ORDER BY sound_type, sound_count DESC;
```

**预期结果与业务结论**

结果约 14 行（2 种 sound_type × 7 种曲风）。`official_track` 总数约 400，`ugc_remix` 总数约 200，Pop 曲风在两类里应该都是占比最高的曲风。下一步动作：无——这是一张纯背景信息表，用来帮团队成员建立对曲库规模的直觉。

---

## Query 16: 份额漂移 Top 5 / Bottom 5 厂牌

**业务语境**

Director of Rights Compliance 要在周会上用一页纸讲清楚"哪几家厂牌份额涨得最猛、哪几家跌得最惨"，不需要看全部 20 家的完整名单，只要两端的极值。

**标签**：Window Function ｜ Intermediate ｜ Director of Rights Compliance

**解题思路**

复用 Query 1 的份额漂移计算逻辑，但这次要同时拿到"涨幅最大的 5 个"和"跌幅最大的 5 个"。做法是在同一个 CTE 里用两次 `RANK() OVER`——一次按漂移值降序排（找涨幅最大），一次按升序排（找跌幅最大）——然后用 `UNION ALL` 把 `growth_rank <= 5` 和 `decline_rank <= 5` 的行拼起来。注意如果厂牌数量少于 10 家，这两组可能会有重叠，但本数据集有 20 家厂牌，两组不会重叠。

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
),
drift AS (
    SELECT
        l.label_name,
        lbl.usage_share_assumption_pct,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count, 2) AS actual_share_pct,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp,
        RANK() OVER (ORDER BY mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct DESC) AS growth_rank,
        RANK() OVER (ORDER BY mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct ASC) AS decline_rank
    FROM month_usage mu
    JOIN label l
        ON l.id = mu.label_id
    JOIN label_blanket_license lbl
        ON lbl.label_id = l.id
    CROSS JOIN total t
)
SELECT label_name, usage_share_assumption_pct, actual_share_pct, drift_pp, 'growth' AS bucket
FROM drift
WHERE growth_rank <= 5

UNION ALL

SELECT label_name, usage_share_assumption_pct, actual_share_pct, drift_pp, 'decline' AS bucket
FROM drift
WHERE decline_rank <= 5

ORDER BY drift_pp DESC;
```

**预期结果与业务结论**

结果 10 行，前 5 行是涨幅最大的厂牌（`drift_pp` 为正且较大），后 5 行是跌幅最大的厂牌（`drift_pp` 为负且绝对值较大）。下一步动作：直接作为周会的第一张幻灯片素材。

---

## Query 17: 季度合规风险优先级清单

**业务语境**

季度末，Director of Rights Compliance 需要把陷阱 1（份额漂移）、陷阱 2（未解决版权冲突）、陷阱 4（MFN 违反）三条线的信号汇总到同一张表里，做成给 General Counsel 的"这个季度最该关注哪几家厂牌"优先级清单，而不是让对方分别看三份独立报告。

**标签**：CTE（多表综合）｜ Advanced ｜ Director of Rights Compliance

**解题思路**

这是全文档里综合度最高的一题，需要三个独立的 CTE 分别算出三条信号，再用 `LEFT JOIN` 拼到 `label` 主表上（用 `LEFT JOIN` 是因为不是每家厂牌都有未解决的版权冲突，用 `INNER JOIN` 会把"完全没问题"的厂牌漏掉，而这些厂牌本该显示在清单里、只是风险值为 0）。`mfn_check` 这个 CTE 复用了 Query 4 的 MFN 违反判断逻辑，但这次算的是布尔标记而不是具体金额。最后排序时优先把 MFN 违反的厂牌排在最前面（这是最紧急的合规风险），然后按份额漂移绝对值和未解决风险敞口金额依次排序。

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
),
drift AS (
    SELECT
        l.id AS label_id,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp
    FROM month_usage mu
    JOIN label l
        ON l.id = mu.label_id
    JOIN label_blanket_license lbl
        ON lbl.label_id = l.id
    CROSS JOIN total t
),
conflict_summary AS (
    SELECT
        o.primary_label_id AS label_id,
        COUNT(*) AS open_conflict_count,
        ROUND(SUM(rcf.revenue_at_risk_usd), 2) AS open_revenue_at_risk_usd
    FROM rights_conflict_flag rcf
    JOIN sound remix
        ON remix.id = rcf.remix_sound_id
    JOIN sound o
        ON o.id = remix.source_sound_id
    WHERE rcf.resolution_status IN ('open', 'under_review')
    GROUP BY o.primary_label_id
),
mfn_check AS (
    SELECT
        lbl.label_id,
        CASE
            WHEN lbl.has_mfn_clause = 1
                 AND lbl.annual_license_fee_usd / lbl.usage_share_assumption_pct <
                     (SELECT MAX(annual_license_fee_usd / usage_share_assumption_pct)
                      FROM label_blanket_license
                      WHERE has_mfn_clause = 0)
                THEN 1
            ELSE 0
        END AS mfn_breach_flag
    FROM label_blanket_license lbl
)
SELECT
    l.label_name,
    l.label_tier,
    COALESCE(d.drift_pp, 0) AS usage_share_drift_pp,
    COALESCE(cs.open_conflict_count, 0) AS open_conflict_count,
    COALESCE(cs.open_revenue_at_risk_usd, 0) AS open_revenue_at_risk_usd,
    mc.mfn_breach_flag
FROM label l
LEFT JOIN drift d
    ON d.label_id = l.id
LEFT JOIN conflict_summary cs
    ON cs.label_id = l.id
JOIN mfn_check mc
    ON mc.label_id = l.id
ORDER BY mc.mfn_breach_flag DESC, ABS(COALESCE(d.drift_pp, 0)) DESC, open_revenue_at_risk_usd DESC;
```

**预期结果与业务结论**

结果 20 行（每家厂牌一行）。第一行应该是 Titan Sound Group（`mfn_breach_flag = 1`），之后按份额漂移幅度和未解决冲突敞口依次排列。下一步动作：这就是提交给 General Counsel 的季度合规风险清单本身，前 3-5 行是这个季度必须处理的最高优先级事项。

---

## Query 18: 二创声音标题关键词模式匹配

**业务语境**

你在整理 UGC remix 清单时，想快速找出所有标题里带有"remix"、"freestyle"、"sped up"、"slowed"这类典型二创关键词的声音，作为抽样审查未授权采样的起点——这些关键词往往暗示这段声音大概率基于某个原曲二次创作。

**标签**：Pattern Matching ｜ Basic ｜ Rights & Licensing Compliance Officer

**解题思路**

标准的 `LIKE` 模糊匹配，用 `OR` 把几个关键词并列。因为 SQLite 的 `LIKE` 默认对 ASCII 字母不区分大小写，这里不需要额外套 `LOWER()`。限定 `sound_type = 'ugc_remix'`，避免误把官方曲目标题（理论上不会包含这些关键词，但加上这个条件更严谨、更符合分析意图）纳入结果。

**SQL**

```sql
SELECT
    title,
    sound_type,
    release_date
FROM sound
WHERE sound_type = 'ugc_remix'
  AND (
        title LIKE '%remix%'
        OR title LIKE '%freestyle%'
        OR title LIKE '%sped up%'
        OR title LIKE '%slowed%'
      )
ORDER BY release_date DESC;
```

**预期结果与业务结论**

结果行数取决于实际标题里包含这些关键词的 remix 数量，按上线日期从新到旧排列。下一步动作：把这份名单和 `rights_conflict_flag` 表做一次交叉核对，看有没有明显带"二创关键词"但从未被标记过的漏网记录，作为下一轮稽核抽样的起点。

---

## Query 19: 平台月度可归属曲库用量趋势

**业务语境**

Head of Label Relations 在准备年度业务回顾时，想先看一眼过去 18 个月里，平台上"能归属到某个厂牌"的整体用量是怎么增长的，作为讨论个别厂牌份额涨跌之前的大盘背景。

**标签**：Date/Time Trend ｜ Basic ｜ Head of Label Relations

**解题思路**

复用 Query 1 里"哪些声音能归属到某个厂牌"的 CTE 逻辑，这次不按厂牌分组，而是按 `usage_month` 分组，看整体趋势。这是一道基础的时间序列聚合题，帮助读者在看后面涉及份额百分比的题目之前，先建立"分母本身也在增长"这个背景认知。

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id
    FROM sound r
    WHERE r.sound_type = 'ugc_remix'
      AND r.source_sound_id IS NOT NULL
)
SELECT
    smu.usage_month,
    SUM(smu.video_count) AS total_labeled_video_count,
    SUM(smu.view_count) AS total_labeled_view_count
FROM sound_monthly_usage smu
JOIN label_sound ls
    ON ls.sound_id = smu.sound_id
GROUP BY smu.usage_month
ORDER BY smu.usage_month;
```

**预期结果与业务结论**

结果 18 行（2025-01 到 2026-06 每月一行），`total_labeled_video_count` 应呈现平稳的逐月上涨趋势（整体约 30%-40% 的 18 个月累计增幅）。下一步动作：作为年度业务回顾的背景图表，说明"个别厂牌份额下降不代表它绝对用量在萎缩，可能只是大盘涨得比它快"。

---

## Query 20: 续约优先级清单（到期临近 + 份额漂移）

**业务语境**

Head of Label Relations 要规划下个季度的续约谈判日程，需要一份综合清单：优先处理"合同即将到期"且"份额漂移幅度大"的厂牌，而不是按到期日期机械排序——一个只剩 2 个月到期但份额几乎没变的厂牌，紧迫程度不如一个还有 8 个月但份额已经涨了 4 个百分点的厂牌。

**标签**：CTE + Window Function ｜ Advanced ｜ Head of Label Relations

**解题思路**

在 Query 1 的份额漂移计算基础上，多算一个 `months_to_renewal`（合同到期日减去参考日，换算成月）。优先级排序用一个复合的 `CASE WHEN` 做一级排序键——"12 个月内到期"的厂牌整体排在"12 个月以上"的前面——然后在每一级内部再按份额漂移的绝对值降序排，用 `RANK() OVER` 生成一个统一的 `renewal_priority_rank`。这种"先分层、再排序"的写法比单纯按一个维度排序更贴近真实的业务优先级判断逻辑。

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
),
drift AS (
    SELECT
        l.label_name,
        lbl.contract_end_date,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp,
        (JULIANDAY(lbl.contract_end_date) - JULIANDAY('2026-06-30')) / 30.0 AS months_to_renewal
    FROM month_usage mu
    JOIN label l
        ON l.id = mu.label_id
    JOIN label_blanket_license lbl
        ON lbl.label_id = l.id
    CROSS JOIN total t
)
SELECT
    label_name,
    contract_end_date,
    ROUND(months_to_renewal, 1) AS months_to_renewal,
    drift_pp,
    RANK() OVER (
        ORDER BY
            CASE WHEN months_to_renewal <= 12 THEN 1 ELSE 2 END,
            ABS(drift_pp) DESC
    ) AS renewal_priority_rank
FROM drift
ORDER BY renewal_priority_rank
LIMIT 10;
```

**预期结果与业务结论**

结果 10 行，`renewal_priority_rank = 1` 的厂牌应同时满足"12 个月内到期"和"份额漂移幅度大"两个条件。下一步动作：这份清单直接交给 Head of Label Relations 排入下季度续约谈判日程，前 3 名安排最优先的谈判时段。

---

## 业务问题对照表

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 曲库使用份额漂移 | Query 1, Query 2, Query 16, Query 19, Query 20 |
| Q2 UGC 未授权采样合规稽核 | Query 5, Query 6, Query 7, Query 8, Query 18 |
| Q3 Creator Fund 热度快照错位 | Query 9, Query 10, Query 11, Query 12 |
| Q4 MFN 条款合规稽核 | Query 3, Query 4, Query 17 |
| 运营背景类 | Query 13, Query 14, Query 15 |
