# 媒体娱乐 — 动画 IP 衍生品授权与零售动销分析 SQL 查询参考

## 概述

本文档为 `media_anime_ip_licensing_retail_medium` 数据集提供 **20 个面向业务的 SQL 查询**。每个查询都对应 Ember & Ash Licensing Group 利益相关者在管理动画 IP 授权组合、稽核版税、监控渠道合规时会真实提出的问题。业务背景、公司角色、行业科普与术语表请见 `01-media_anime_ip_licensing_retail_medium_business_context-cn.md`;表结构与字段含义请见 `02-media_anime_ip_licensing_retail_medium_er_document-cn.md`。

> **参考日约定。** 数据集锚定到固定的 `REFERENCE_DATE = 2026-06-30`。需要"今天"的查询使用字面量 `'2026-06-30'` 而非 `DATE('now')`,使结果与执行时间无关、可复现。若你把数据集重新锚定到其他参考日,请在下面所有查询里替换这个字面量。

## 如何使用本文档

本文档写给刚读完业务背景文档(`01-...business_context-cn.md`)和 ER 文档(`02-...er_document-cn.md`)、准备上手做分析的新人数据分析师。把它当成一份"项目交接":VP of Licensing 把这 20 道题交给你,你这一周要逐一做完,并理解为什么这么写。

每个查询都按统一的**五段式**组织:

1. **业务背景** —— 谁在问、为什么问、答案要支撑什么决策、为什么现在紧急。
2. **类别 / 难度 / 业务角色** —— 三个快速标签,帮你判断这道题练的是哪类 SQL、对应公司里哪个角色。
3. **解题思路** —— 在你看到 SQL 之前,先讲清楚要碰哪些表、怎么 join、聚合到什么粒度、为什么用(或不用)CTE / 窗口函数 / 子查询、有哪些 SQLite 专属坑要避开。这一段是学习重点。
4. **SQL 代码** —— 可直接在生成器产出的 SQLite 库上运行。
5. **期望结果说明** —— 结果集长什么样、关键数值对应哪个业务陷阱、以及拿到结果后下一步该做什么。

两个使用提示:

- **每个查询都映射回一个业务问题。** 文档末尾有"业务问题 → 查询"对照表;读 SQL 之前先想清楚它要回答 Q1–Q5 中的哪一个。
- **SQL 是用来读和学的,不只是用来跑的。** 解题思路解释了"为什么这样写";真正的功夫在看懂 join 的方向、聚合的粒度、口径的选择,而不是把数跑出来就完事。

---

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|------|----------|------|------|
| 1 | IP x 品类零售动销排名 | Retail Channel Analyst | Aggregation + Join | Intermediate |
| 2 | 被授权商版税低报排行 | Royalty Audit Specialist | Aggregation + Join | Intermediate |
| 3 | 热度-动销滞后:首播事件对齐分析 | Retail Channel Analyst | CTE + Date Analysis | Advanced |
| 4 | 越权渠道铺货检测 | Director of Royalty Compliance | Join + Aggregation | Intermediate |
| 5 | 保底金额达成进度追踪 | Licensing Manager | CTE + Aggregation | Advanced |
| 6 | 授权经理合同组合负荷看板 | Director of Licensing | Aggregation + Join | Basic |
| 7 | 合规评分与稽核结果一致性验证 | Royalty Audit Specialist | Aggregation + Join | Intermediate |
| 8 | 品类版税率对基准偏离分析 | Licensing Manager | Aggregation | Basic |
| 9 | 被授权商品牌名称与签约品类不一致检测 | VP of Licensing | Pattern Matching + Join | Intermediate |
| 10 | 季度新签合同节奏趋势 | VP of Licensing | Date Aggregation | Basic |
| 11 | 临界未确认低报合同预警 Top 10 | Royalty Audit Specialist | CTE + Window Function | Advanced |
| 12 | 产品上市后动销爬坡曲线 | Retail Channel Analyst | Date + Aggregation | Intermediate |
| 13 | 地域范围与保底金额规模关系 | Senior Licensing Manager | Aggregation | Basic |
| 14 | SKU 畅销 / 滞销 Top 5 | Retail Channel Analyst | Window Function | Intermediate |
| 15 | 未来 6 个月到期合同续约决策清单 | Licensing Manager | CTE + Date Analysis | Intermediate |
| 16 | 被授权商综合风险评分卡 | Director of Royalty Compliance | CTE + Aggregation | Advanced |
| 17 | 线上 vs 线下渠道动销对比 | Retail Channel Analyst | Aggregation + Join | Basic |
| 18 | 版税报告提交时效分析 | Royalty Audit Specialist | Date Calculation | Basic |
| 19 | IP 热度层级与合同规模关系 | VP of Licensing | Aggregation + Join | Intermediate |
| 20 | 续约优先级综合评分 | VP of Licensing | CTE + Window Function | Advanced |

---

## 查询正文

### Query 1: IP x 品类零售动销排名

**业务背景:**
零售渠道分析师正在为季度组合评审准备材料。VP of Licensing 想知道:过去一年多签下的 117 份授权合同里,到底是哪些"IP x 品类"组合真正在零售终端动销,值得在到期后优先续签更长期限或更大范围的授权;哪些组合动销持续低迷,该考虑到期后不再续约。这是整份季度评审 deck 的开场页,后续所有续约建议都要能追溯到这张排名表。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Retail Channel Analyst

**解题思路:**
这题的分析粒度是"一个 IP x 一个品类一行",但原始销售数据在 `pos_sell_through` 是"SKU x 渠道 x 周"粒度,中间要经过 `anime_ip → license_agreement → product_sku → pos_sell_through` 四层 JOIN 才能把周度销售记录归到 IP x 品类上,`product_category` 再 JOIN 一次拿到品类名称。因为一个 IP 可能通过多份合同签给多个品类,`GROUP BY ai.id, pc.id` 而不是只 `GROUP BY ai.id`,才能保留品类维度。这里全部用 INNER JOIN 是安全的——只要一个 SKU 存在,它必然可以一路 JOIN 回 IP 和品类,不会有孤儿行需要用 LEFT JOIN 保护。不需要窗口函数或子查询,一次 GROUP BY + ORDER BY 即可完成。

```sql
-- Rank IP x category combinations by total sell-through volume and revenue
SELECT
    ai.title,
    pc.category_name,
    ai.popularity_tier,
    SUM(p.units_sold) AS total_units_sold,
    ROUND(SUM(p.net_wholesale_revenue_usd), 2) AS total_wholesale_revenue
FROM anime_ip ai
JOIN license_agreement la ON la.anime_ip_id = ai.id
JOIN product_category pc ON pc.id = la.product_category_id
JOIN product_sku s ON s.license_agreement_id = la.id
JOIN pos_sell_through p ON p.product_sku_id = s.id
GROUP BY ai.id, pc.id
ORDER BY total_units_sold DESC
LIMIT 10;
```

**期望结果说明:**
结果集每行是一个 IP x 品类组合,按总销量降序排列。前 10 名几乎全部被 **Collectible Trading Cards(收藏卡牌)** 品类占据——`Petalfall`(breakout 级 IP)以约 10.6 万件、约 82.1 万美元批发收入排名第一,`Sakura Static`、`Whispering Gears`、`Rustlight` 紧随其后,均超过 7 万件。这不是巧合:卡牌品类的基础复购频次(生成器里的 `CATEGORY_BASE_WEEKLY_UNITS`)本来就远高于其他品类。零售渠道分析师应该据此建议:续约优先级清单里,卡牌品类的 IP 组合应该拿到更长期限或更宽渠道范围的续约条款;同时要提醒管理层,这个排名天然对高频复购品类有利,评估"哪个 IP 更值得投资"时应该在品类内部比较,而不是跨品类直接比总件数。

---

### Query 2: 被授权商版税低报排行

**业务背景:**
版税稽核专员每个季度都要出一份"疑似低报被授权商"名单交给 Director of Royalty Compliance。公司最近升级了稽核流程——不再只是抽查,而是用零售终端 POS 数据反推每家被授权商"应该"交多少版税,和他们自己申报的数字逐一比对。她需要一份按差异幅度排序的名单,搞清楚问题是个别被授权商的偶发失误,还是有一批被授权商在系统性地少报。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Royalty Audit Specialist

**解题思路:**
核心是把 `royalty_audit_finding.variance_pct`(已经在生成阶段算好的"POS 推算版税 vs 自报版税"差异百分比)按被授权商聚合。路径是 `licensee → license_agreement → royalty_report → royalty_audit_finding`,四张表严格按 FK 一路 INNER JOIN 下去——因为 `royalty_audit_finding` 和 `royalty_report` 是强制 1:1 关系,不会有孤儿行,不需要 LEFT JOIN。聚合粒度是"一个被授权商一行",用 `AVG(variance_pct)` 看平均偏差幅度,再用 `SUM(CASE WHEN audit_status='confirmed_underreport' THEN 1 ELSE 0 END)` 数清楚这家被授权商有几次被正式判定为低报。`ORDER BY avg_variance_pct DESC` 把差异最大的排在最前面。

```sql
-- Rank licensees by average royalty variance (POS-derived vs self-reported)
SELECT
    l.company_name,
    l.risk_tier,
    ROUND(l.compliance_score, 1) AS compliance_score,
    COUNT(raf.id) AS n_reports_audited,
    ROUND(AVG(raf.variance_pct), 2) AS avg_variance_pct,
    SUM(CASE WHEN raf.audit_status = 'confirmed_underreport' THEN 1 ELSE 0 END) AS n_confirmed_underreport,
    ROUND(SUM(raf.variance_usd), 2) AS total_underreported_royalty_usd
FROM licensee l
JOIN license_agreement la ON la.licensee_id = l.id
JOIN royalty_report rr ON rr.license_agreement_id = la.id
JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
GROUP BY l.id
ORDER BY avg_variance_pct DESC
LIMIT 10;
```

**期望结果说明:**
结果不是"个别失误"——前 7 名清一色是 `risk_tier = 'risk'` 的被授权商,平均差异 12.2%-14.1%,累计被判定 `confirmed_underreport` 的报告数从 4 次到 13 次不等,其中 **Mcclain, Miller and Henderson Merch Studio** 单家累计少报版税约 10,086 美元。第 8 名开始骤降到 `clean` 群体的 0.5%-0.7%(正常申报噪音)。这个断层证实了一件事:低报不是随机分布,而是集中在一小群合规评分本就偏低(compliance_score < 50)的被授权商身上。全组合层面看,369 份报告里 17.9% 被判定 `confirmed_underreport`、10.0% `flagged_for_review`,POS 推算总版税($1,443,655)比自报总版税($1,381,232)多出约 62,000 美元,占 POS 推算口径的约 4.32%(这里以 POS 推算额为分母,和 `variance_pct` 的口径一致;若换成以自报额为分母,则约为 4.52%——两个数都对,只是分母不同,别混用)。稽核专员的下一步:对前 7 名启动正式稽核约谈,并在下一轮续约谈判里加入更严格的审计权条款。

---

### Query 3: 热度-动销滞后:首播事件对齐分析

**业务背景:**
一部动画新一季首播,流媒体热度立刻冲高,但零售渠道分析师发现衍生品销量并没有当周就跟着涨——被授权商和零售商都抱怨"要货要晚了"。VP of Licensing 想知道这个滞后到底有多长,好据此提前通知被授权商在首播前就开始备货,而不是等销量数据已经证明"这波火了"才追加生产。这道题要用数据回答:从首播热度峰值到零售动销明显上升,平均要等几周?

**类别:** CTE + Date Analysis
**难度:** Advanced
**业务角色:** Retail Channel Analyst

**解题思路:**
这是全文档里最容易踩坑的一题。**直觉上的做法**——分别找出每个 IP 全部追踪历史里"热度最高的那一周"和"销量最高的那一周",再比较两者相差几周——是错的:一个 IP 的 SKU 会陆续在两年窗口里持续新增,越晚的周份"在架 SKU 数"天然越多,全局销量最高的周份很可能只是因为那时候在售 SKU 最多,跟热度毫无关系,这是一个隐藏的混杂变量 (confounder)。正确做法是**事件对齐法**:以每次首播周为"第 0 周"基准点,只取"首播时已经在架"的 SKU(`launch_date <= premiere_week`,排除掉后续才上市、跟这次首播无关的新品),把首播前后各 4-16 周的销量按"相对首播的周数偏移" (`weeks_since_premiere`) 重新对齐、聚合求平均。第一个 CTE `premieres` 找出所有首播周;第二个 CTE `eligible_skus` 圈定"首播时已上架"的 SKU;第三个 CTE `event_aligned_sales` 用 `JULIANDAY` 差值除以 7 再四舍五入算出相对周数,这一步必须先转成 `JULIANDAY` 再做减法,不能直接对 `DATE` 类型做算术。最后按 `weeks_since_premiere` 分组求平均,峰值出现在哪个偏移量,就是滞后期。

```sql
-- Align retail sales to premiere-week zero point to detect the popularity-to-sales lag
WITH premieres AS (
    SELECT anime_ip_id, week_start_date AS premiere_week
    FROM streaming_popularity_index
    WHERE is_season_premiere_week = 1
),
eligible_skus AS (
    -- Map each product SKU to its IP and launch date (the shelf-time filter is applied in the JOIN below)
    SELECT s.id AS sku_id, la.anime_ip_id, s.launch_date
    FROM product_sku s
    JOIN license_agreement la ON la.id = s.license_agreement_id
),
event_aligned_sales AS (
    SELECT
        CAST(ROUND((JULIANDAY(p.week_start_date) - JULIANDAY(pr.premiere_week)) / 7.0) AS INTEGER) AS weeks_since_premiere,
        p.units_sold
    FROM premieres pr
    JOIN eligible_skus es
        -- keep only SKUs already on shelf at premiere time (excludes later unrelated launches)
        ON es.anime_ip_id = pr.anime_ip_id AND es.launch_date <= pr.premiere_week
    JOIN pos_sell_through p ON p.product_sku_id = es.sku_id
    WHERE p.week_start_date BETWEEN date(pr.premiere_week, '-28 days') AND date(pr.premiere_week, '+112 days')
)
SELECT
    weeks_since_premiere,
    ROUND(AVG(units_sold), 2) AS avg_weekly_units,
    COUNT(*) AS n_sku_weeks
FROM event_aligned_sales
GROUP BY weeks_since_premiere
ORDER BY weeks_since_premiere;
```

**期望结果说明:**
结果是一条"相对周数 → 平均销量"的曲线。首播前后(第 -3 周到第 +5 周)销量维持在约 33-40 件/周的平稳基线,第 6 周开始爬升,在**第 8-10 周**达到峰值(约 55-60 件/周,相对基线提升约 50%-75%),随后逐渐回落到第 12 周之后的次高原。这证实了供应链滞后的存在,滞后期落在**约 6-10 周**——和公司现在"看到热度才催货"的做法相比,这意味着被授权商应该在首播确认后的第一周就启动追加生产,而不是等 2 个月后销量数据自己证明"这波值得追加"。**注意**:这个分析只在 breakout / mainstream 级 IP 上有意义,因为只有它们在追踪窗口内有明确的首播事件;niche 级 IP 没有首播峰值,不适用这套方法论。

---

### Query 4: 越权渠道铺货检测

**业务背景:**
版税合规总监最近收到一个零售商的投诉:某个只签了"专卖店 + 展会快闪"渠道授权的被授权商,商品却大量出现在电商平台上,价格比专卖店低不少,扰乱了渠道价格体系。她需要一份系统性的越权铺货清单,而不是等零售商投诉才被动发现问题——数据里应该能主动揪出所有"卖到了合同没授权的渠道"的记录。

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Director of Royalty Compliance

**解题思路:**
这题的核心技巧是用 **LEFT JOIN + `WHERE ... IS NULL`** 做"反连接" (anti-join),这是 SQL 里判断"某条记录在另一张表里找不到匹配"的标准写法。把每一条 `pos_sell_through` 记录,通过它所属的 `product_sku → license_agreement` 找到对应合同,再用 `license_agreement_channel` 的**复合条件**(`license_agreement_id` 和 `retail_channel_id` 同时匹配)去 LEFT JOIN——如果这个渠道确实在授权范围内,`lac.id` 会有值;如果找不到匹配(未授权),`lac.id` 就是 NULL。`WHERE lac.id IS NULL` 精确筛出所有越权销售记录。这里绝不能把 LEFT JOIN 换成 INNER JOIN,那样会直接把越权记录全部过滤掉,查询结果变成"看起来完全合规"的假象——这正是陷阱的核心:如果不做这个 JOIN,越权收入会被悄悄算进"合规收入"里。

```sql
-- Detect POS sales occurring in channels not authorized by the license agreement
SELECT
    l.company_name,
    l.risk_tier,
    rc.channel_name AS unauthorized_channel,
    COUNT(*) AS n_weeks_with_unauthorized_sales,
    SUM(p.units_sold) AS total_unauthorized_units,
    ROUND(SUM(p.net_wholesale_revenue_usd), 2) AS total_unauthorized_revenue
FROM pos_sell_through p
JOIN product_sku s ON s.id = p.product_sku_id
JOIN license_agreement la ON la.id = s.license_agreement_id
JOIN licensee l ON l.id = la.licensee_id
JOIN retail_channel rc ON rc.id = p.retail_channel_id
LEFT JOIN license_agreement_channel lac
    ON lac.license_agreement_id = la.id AND lac.retail_channel_id = p.retail_channel_id
WHERE lac.id IS NULL
GROUP BY l.id, rc.id
ORDER BY total_unauthorized_revenue DESC
LIMIT 10;
```

**期望结果说明:**
结果清一色是 `risk_tier = 'risk'` 的被授权商,越权渠道**几乎全部落在线上**——以 **E-commerce Marketplace(电商平台)** 为主,其余约四分之一落在 **Direct-to-Consumer Online(官网直营)**(当某份合同已经授权了电商渠道,泄漏就退化到官网直营,因此榜单里也会出现 DTC-online 的行,如 Blake and Sons Toys 一行约 3.1 万美元)。榜首 **Mcclure, Ward and Lee Merch Studio** 一家就有 135 周次、约 6.1 万美元的越权线上销售。跨整个组合看,risk 群体约 6.85% 的 POS 记录(约 6.6% 的收入)发生在未授权渠道,clean 群体这一比例只有约 0.59%(正常噪音水平)。这印证了合规总监的直觉:电商平台准入门槛低、货源难追溯,是越权铺货最常见的泄漏口。下一步:对榜单前几名启动正式渠道合规约谈,并考虑在续约合同里把电商渠道单独列为需要额外授权费的选项,而不是留一个模糊地带。

---

### Query 5: 保底金额达成进度追踪

**业务背景:**
每个季度末,授权经理都要给自己名下的合同组合过一遍"健康检查"——哪些合同的版税进度已经落后于保底金额 (minimum guarantee, MG) 的时间进度,需要在下一轮续约谈判前重新评估条款,甚至考虑不再续约。上一季度有一份合同到期时公司才发现被授权商全期只交了保底金额的一小部分,却因为没人盯着分期进度,错过了提前介入的窗口。这道题就是要把"提前预警"这件事系统化。

**类别:** CTE + Aggregation
**难度:** Advanced
**业务角色:** Licensing Manager

**解题思路:**
保底金额是"合同期总额",不能直接拿 `REFERENCE_DATE` 时点的累计版税跟它比——一份还剩一半期限的合同,累计版税本来就只会是保底金额的一部分,这不代表出问题。正确做法是**按时间进度折算 (proration)**:先算出"合同已经过去的时间比例" `elapsed_fraction = (REFERENCE_DATE − contract_start_date) / (contract_end_date − contract_start_date)`,乘以保底金额得到"这个时间点应该达到多少"的目标值 `prorated_mg_target`,再拿实际累计版税 (`SUM(reported_royalty_due_usd)`, 用一个 CTE `royalty_to_date` 先按合同聚合) 除以这个目标值,得到 `pacing_ratio`。`MIN(1.0, ...)` 防止已经跑满全期的合同 `elapsed_fraction` 超过 1。只筛 `contract_status = 'active'` 的合同,因为已到期/已终止的合同不该再被要求"追赶进度"——这条筛选条件容易被新手漏掉,漏掉的话已到期合同的 `elapsed_fraction` 会一直卡在 1.0,让"进度不足"的判断失真。

**另一个容易漏掉的边界情形:** 刚签约不久、连第一个 91 天报告周期都还没走完的活跃合同,`royalty_to_date` 里根本没有它的行,`pacing_ratio` 会自然算成 0——这和"卖得差、真被拖欠"是两回事,不该混进"落后预警"名单。所以 `royalty_to_date` 这里要用 `JOIN` 而不是 `LEFT JOIN`:`LEFT JOIN` 会把这些"还没到报告期"的合同也保留下来(用 `COALESCE(..., 0)` 垫成 0),让它们和真正拖欠的合同混在一起;换成 `JOIN`,只有已经至少提交过一份报告的合同才会进入 `pacing` CTE,`pacing_ratio` 才只反映"交了但交得不够"的合同,而不是"还没轮到交"的合同。

```sql
-- Track cumulative royalty progress against the prorated minimum guarantee target
WITH royalty_to_date AS (
    SELECT license_agreement_id, SUM(reported_royalty_due_usd) AS cumulative_royalty_usd
    FROM royalty_report
    GROUP BY license_agreement_id
),
pacing AS (
    SELECT
        la.id,
        la.agreement_number,
        ai.title,
        l.company_name,
        la.minimum_guarantee_usd,
        rtd.cumulative_royalty_usd,
        MIN(1.0, CAST((JULIANDAY('2026-06-30') - JULIANDAY(la.contract_start_date)) AS REAL)
            / (JULIANDAY(la.contract_end_date) - JULIANDAY(la.contract_start_date))) AS elapsed_fraction
    FROM license_agreement la
    JOIN anime_ip ai ON ai.id = la.anime_ip_id
    JOIN licensee l ON l.id = la.licensee_id
    JOIN royalty_to_date rtd ON rtd.license_agreement_id = la.id
    -- JOIN (不是 LEFT JOIN): 排除掉一份报告都还没提交过的新签合同,
    -- 否则它们的 cumulative_royalty_usd 会被 COALESCE 成 0, 和真正拖欠的合同混在一起
    WHERE la.contract_status = 'active'
)
SELECT
    agreement_number,
    title,
    company_name,
    ROUND(minimum_guarantee_usd, 0) AS minimum_guarantee_usd,
    ROUND(minimum_guarantee_usd * elapsed_fraction, 0) AS prorated_mg_target,
    ROUND(cumulative_royalty_usd, 0) AS cumulative_royalty_usd,
    ROUND(cumulative_royalty_usd / NULLIF(minimum_guarantee_usd * elapsed_fraction, 0), 2) AS pacing_ratio
FROM pacing
WHERE cumulative_royalty_usd / NULLIF(minimum_guarantee_usd * elapsed_fraction, 0) < 0.40
ORDER BY pacing_ratio ASC
LIMIT 10;
```

**期望结果说明:**
117 份合同中 99 份是 `active`,其中 **94 份已经至少提交过一份版税报告**(剩下 5 份太新,连第一个报告周期都还没走完,已被 `JOIN` 排除在外)。这 94 份里,有 **21 份(约 22.3%)** 的 `pacing_ratio` 低于 0.40——按时间比例本该交够的版税,这些合同实际只交了不到四成。榜首几份合同 `pacing_ratio` 低至 0-0.03(比如 `LA-00005` 保底 19,039 美元、按进度本该交约 6,346 美元、实际只交了 20 美元)。这不是随机噪音:超过五分之一的"已经有机会证明自己"的活跃合同正在朝"保底金额收不回来"的方向走。授权经理的下一步:对这 21 份合同逐一评估——是 IP 本身热度不够(该考虑到期不续),还是被授权商执行不力(该在续约时收紧条款或换被授权商),分类之后分别制定应对策略,而不是等到期日才发现问题。剩下那 5 份"太新还没报告"的合同不代表没问题,只是现在还判断不了,应该单独放进"观察名单",等它们的第一份报告提交后再评估,而不是现在就当成风险合同处理。

---

### Query 6: 授权经理合同组合负荷看板

**业务背景:**
Director of Licensing 在做团队年度绩效评估前,想先摸清楚每位授权经理名下到底管了多少份合同、多大规模的保底金额敞口。这不只是工作量分配的问题——如果某位经理名下合同数量远超同事,可能意味着他的合同组合更容易因为精力分散而错过续约窗口或稽核预警。

**类别:** Aggregation + Join
**难度:** Basic
**业务角色:** Director of Licensing

**解题思路:**
最直接的一题:`account_manager` LEFT JOIN `license_agreement`,按经理分组统计合同数、活跃合同数、管理的保底金额总规模。这里用 LEFT JOIN 而不是 INNER JOIN,是为了保证即便某位经理暂时名下一份合同都没有,也会在结果里显示为 0,而不是从结果集里直接消失——8 位授权经理里任何一位"挂零"都是管理层需要知道的信息。`SUM(CASE WHEN ... THEN 1 ELSE 0 END)` 是条件计数的标准写法,比用子查询单独再数一次活跃合同更简洁。

```sql
-- Portfolio load per account manager: total agreements, active count, MG exposure
SELECT
    am.first_name || ' ' || am.last_name AS manager_name,
    am.title,
    am.region_focus,
    COUNT(la.id) AS total_agreements,
    SUM(CASE WHEN la.contract_status = 'active' THEN 1 ELSE 0 END) AS active_agreements,
    ROUND(SUM(la.minimum_guarantee_usd), 0) AS total_mg_managed_usd
FROM account_manager am
LEFT JOIN license_agreement la ON la.account_manager_id = am.id
GROUP BY am.id
ORDER BY total_agreements DESC;
```

**期望结果说明:**
8 位授权经理,合同数从 11 到 18 份不等,管理的保底金额敞口从约 14.1 万到约 34.7 万美元。**Meagan Romero**(Director of Licensing)名下 18 份合同、约 32.5 万美元敞口,负荷最重;**Caitlin Mcdonald** 最少,11 份、约 15.0 万美元。这份看板本身不直接说明谁表现好坏——负荷高低要结合 Query 5(保底达成)和 Query 2(版税稽核)的结果交叉看:如果一位经理负荷高**且**名下合同的 pacing_ratio 普遍偏低,才是真正需要关注的信号,单看合同数量意义有限。

---

### Query 7: 合规评分与稽核结果一致性验证

**业务背景:**
版税稽核专员想验证一件事:公司内部给每家被授权商打的 `compliance_score`(合规评分,来自历史合作记录的定性评估),是不是真的能预测稽核会不会发现问题。如果两者脱节——评分高的公司照样被抓到低报——那这个评分体系就该重新设计;如果高度一致,评分就可以作为"要不要优先稽核"的筛选依据,省下不必要的稽核成本。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Royalty Audit Specialist

**解题思路:**
用 `CASE WHEN` 把连续的 `compliance_score` 分桶成几个可读的区间("80-100 高"、"66-79 中"等),再按分桶聚合稽核结果。这不是简单地按 `risk_tier` 字段分组——那样等于直接采信了系统已经打好的标签;这里特意从**原始分数**重新分桶,是为了独立验证"分数本身"和"稽核结果"是否一致,而不是循环论证"risk_tier 标记的公司确实是 risk"。`GROUP BY compliance_band` 之后按 `MIN(l.compliance_score) DESC` 排序,保证分桶按分数从高到低出现,而不是按字母序或插入顺序这种无意义的顺序。

```sql
-- Verify whether the internal compliance_score actually predicts audit outcomes
SELECT
    CASE
        WHEN l.compliance_score >= 80 THEN '80-100 (High)'
        WHEN l.compliance_score >= 66 THEN '66-79 (Medium)'
        WHEN l.compliance_score >= 50 THEN '50-65 (Low)'
        ELSE 'Below 50 (Very Low)'
    END AS compliance_band,
    COUNT(raf.id) AS n_reports,
    ROUND(AVG(raf.variance_pct), 2) AS avg_variance_pct,
    ROUND(100.0 * SUM(CASE WHEN raf.audit_status = 'confirmed_underreport' THEN 1 ELSE 0 END) / COUNT(raf.id), 1) AS pct_confirmed_underreport
FROM licensee l
JOIN license_agreement la ON la.licensee_id = l.id
JOIN royalty_report rr ON rr.license_agreement_id = la.id
JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
GROUP BY compliance_band
ORDER BY MIN(l.compliance_score) DESC;
```

**期望结果说明:**
结果只出现三个分桶,不是四个——"50-65 (Low)"这一档在当前数据里没有任何被授权商落入(本数据集的 8 家 risk 群体被授权商合规评分恰好都集中在 35-48 分之间,和 clean 群体的 70-98 分之间有明显空隙,没有"中间地带"公司)。"80-100"和"66-79"两档平均差异都在 0.1% 左右、confirmed_underreport 比例 0%;"Below 50"档平均差异高达 13.05%、64.1% 被判定低报。结论很清楚:合规评分**确实**能预测稽核结果,而且预测力很强、几乎是二元分类而非连续渐变。稽核专员可以放心地把 `compliance_score < 50` 作为"优先稽核"名单的筛选阈值,省下对高分被授权商的常规抽查资源。

> **稳健性提示:** 这里"结果只有三个分桶、8 家 risk 恰好都落在 35-48 分区间"是当前固定种子 `RANDOM_SEED = 42` 下的具体落点,而非硬约束。生成器给 risk 群体分配 `compliance_score` 的采样区间其实是 **35-65 分**(见 ER 文档 `licensee.compliance_score` 列定义),理论上完全可能产出落在 `50-65 (Low)` 桶里的被授权商,从而让结果出现第四个分桶。本数据集用固定种子保证可复现,当前 seed 下不会发生;但若日后有人调整种子,"没有中间地带公司"这句叙述需要重新核对。稽核阈值本身(`compliance_score < 50`)不受影响,只是"恰好三桶"这个观察点依赖种子。

---

### Query 8: 品类版税率对基准偏离分析

**业务背景:**
授权经理团队想知道,实际谈下来的版税率跟品类基准比,谈判空间到底有多大。有经理反映"卡牌品类越来越难谈到高于基准的费率了",这道题用数据验证这个说法站不站得住脚,为下一轮标准合同模板的费率区间设定提供依据。

**类别:** Aggregation
**难度:** Basic
**业务角色:** Licensing Manager

**解题思路:**
一次简单的 JOIN + GROUP BY:把 `license_agreement.royalty_rate_pct` 按品类聚合求平均,和 `product_category.benchmark_royalty_rate_pct` 相减得到偏离幅度。没有陷阱,是一道热身题——重点在于养成"拿到一个平均值,先问它跟某个基准比是高是低"的分析习惯,而不是只看平均值本身。

```sql
-- Compare negotiated royalty rates against the category benchmark
SELECT
    pc.category_name,
    pc.benchmark_royalty_rate_pct,
    COUNT(la.id) AS n_agreements,
    ROUND(AVG(la.royalty_rate_pct), 2) AS avg_actual_rate,
    ROUND(AVG(la.royalty_rate_pct) - pc.benchmark_royalty_rate_pct, 2) AS avg_deviation_pp,
    ROUND(MIN(la.royalty_rate_pct), 2) AS min_rate,
    ROUND(MAX(la.royalty_rate_pct), 2) AS max_rate
FROM product_category pc
JOIN license_agreement la ON la.product_category_id = pc.id
GROUP BY pc.id
ORDER BY avg_deviation_pp DESC;
```

**期望结果说明:**
六个品类的平均实际费率都紧贴基准,偏离幅度在 -0.31pp 到 +0.42pp 之间——**Collectible Trading Cards** 品类平均反而比基准**低** 0.31pp(11.69% vs 基准 12.00%),印证了那位经理的说法:卡牌品类谈判议价能力偏弱,可能是因为供给端(愿意做卡牌的被授权商)相对充裕,议价筹码在 Ember & Ash 这边反而没那么强。**Toys & Action Figures** 品类平均反而略高于基准(+0.42pp),议价空间最好。这份结果可以直接喂给下一轮标准合同模板的费率区间设定。

---

### Query 9: 被授权商品牌名称与签约品类不一致检测

**业务背景:**
VP of Licensing 注意到公司这几年签的合同里,不少被授权商正在从自己的"招牌品类"往外扩张——一家叫 "XXX Toys" 的公司开始签服饰或家居用品的合同。这本身不是坏事(说明公司在多元化),但 VP 想摸清楚这个趋势的规模,判断要不要在下一轮渠道策略会议上专门讨论"是否鼓励被授权商跨品类扩张"。

**类别:** Pattern Matching + Join
**难度:** Intermediate
**业务角色:** VP of Licensing

**解题思路:**
这题用 `LIKE` 做文本模式匹配——被授权商的 `company_name` 里经常带着品类风格的后缀(如 "... Toys"、"... Apparel Co."、"... Home Goods"、"... Collectibles"),这是生成器刻意设计的命名习惯,不是巧合。用 `company_name LIKE '%Toys%'` 之类的模式识别"名字暗示的品类",再跟 `license_agreement` 实际签约的 `product_category` 做比较——如果名字暗示的品类和实际签约品类不一致,就是一次"跨品类扩张"记录。四个 `LIKE` 条件用 `OR` 连接,每个条件对应一种品牌命名模式;注意 `%` 通配符两边都要留,因为品牌名里这些关键词可能出现在任意位置(如 "Blake and Sons Toys" 里 "Toys" 在末尾)。

```sql
-- Detect licensees signing agreements outside the product category implied by their brand name
SELECT
    l.company_name,
    pc.category_name AS signed_category,
    COUNT(*) AS n_agreements,
    ROUND(SUM(la.minimum_guarantee_usd), 0) AS total_mg_usd
FROM licensee l
JOIN license_agreement la ON la.licensee_id = l.id
JOIN product_category pc ON pc.id = la.product_category_id
WHERE
    (l.company_name LIKE '%Toys%' AND pc.category_code != 'toys_action_figures')
    OR (l.company_name LIKE '%Apparel%' AND pc.category_code != 'apparel')
    OR (l.company_name LIKE '%Home Goods%' AND pc.category_code != 'home_goods_decor')
    OR (l.company_name LIKE '%Collectibles%' AND pc.category_code != 'collectible_trading_cards')
GROUP BY l.id, pc.id
ORDER BY total_mg_usd DESC
LIMIT 10;
```

**期望结果说明:**
先说清楚计数口径,以免照抄 SQL 时对不上数:这条查询按 `GROUP BY l.id, pc.id`(被授权商 × 品类)聚合,实测返回 **51 行**组合(加了 `LIMIT 10` 只显示保底金额最高的前 10 组);而底层的"跨品类"签约**合同**总数是 **65 份**——同一个(被授权商 × 品类)组合下可能不止一份合同,所以合同数(65)比组合行数(51)多。两个数都对,只是口径不同。排名最高的组合是 **Rodriguez, Figueroa and Sanchez Apparel Co.**——名字带 "Apparel",却签了 3 份 Collectible Trading Cards 合同,合计约 10.7 万美元保底金额。这说明跨品类扩张已经是一个有实际规模的现象,而不是零星个案。VP of Licensing 可以据此判断:与其把这当成"品牌定位漂移"的问题去纠正,不如把它当成被授权商生态在自然多元化的信号,考虑在渠道策略会议上正式讨论要不要为"多品类被授权商"设计打包合同条款。

---

### Query 10: 季度新签合同节奏趋势

**业务背景:**
VP of Licensing 每个季度要向公司管理层汇报授权业务的签约节奏。她想知道过去几个季度新签合同数量和承诺的保底金额总额是在加速、放缓,还是持平,这个趋势会直接影响下一年度的收入预测和团队招聘计划。

**类别:** Date Aggregation
**难度:** Basic
**业务角色:** VP of Licensing

**解题思路:**
按 `signed_date` 所在的自然日历季度分组统计。SQLite 没有内建的"取季度"函数,标准做法是组合 `strftime('%Y', ...)` 取年份,和 `(CAST(strftime('%m', ...) AS INTEGER) - 1) / 3 + 1` 用整数除法把月份 (1-12) 映射到季度 (1-4)——这里 `strftime('%m', ...)` 返回的是字符串,必须先 `CAST` 成 `INTEGER` 才能做整数除法,直接对字符串做算术在 SQLite 里会得到意外结果(字符串会被隐式转换,但容易出错,显式 CAST 更安全)。这是一道基础但很常用的日期分桶模式。

```sql
-- Quarterly trend of new agreement signings and committed minimum guarantees
SELECT
    strftime('%Y', signed_date) || '-Q' || ((CAST(strftime('%m', signed_date) AS INTEGER) - 1) / 3 + 1) AS signing_quarter,
    COUNT(*) AS n_agreements_signed,
    ROUND(SUM(minimum_guarantee_usd), 0) AS total_mg_committed_usd
FROM license_agreement
GROUP BY signing_quarter
ORDER BY signing_quarter;
```

**期望结果说明:**
签约节奏从 2024-Q3 到 2025-Q4 大体稳定在每季度 14-21 份新合同、约 26-32 万美元承诺保底金额,2026-Q1 只有 5 份、约 9.2 万美元——但这不代表业务放缓,而是因为数据窗口本身在 REFERENCE_DATE (2026-06-30) 附近截断,2026-Q1 及之后签约的合同还没来得及积累足够长的历史。VP 汇报时应该明确标注这一点,避免管理层把"数据窗口截断"误读成"签约放缓的真实业务信号"。

---

### Query 11: 临界未确认低报合同预警 Top 10

**业务背景:**
版税稽核专员不想只看"已经被正式判定为低报"(`confirmed_underreport`,差异 ≥12%)的合同——那些已经在处理流程里了。她更想提前揪出那些差异幅度**接近但还没跨过** 12% 阈值的合同(`flagged_for_review` 或 `within_tolerance`,但差异其实已经不小),这些合同大概率会在下个季度滑过阈值,提前介入能省下后续正式稽核的成本。

**类别:** CTE + Window Function
**难度:** Advanced
**业务角色:** Royalty Audit Specialist

**解题思路:**
先用一个 CTE 把"尚未被判定为 confirmed_underreport"的合同(`WHERE raf.audit_status != 'confirmed_underreport'`)按合同聚合出平均差异 `avg_variance_pct`,再用窗口函数 `RANK() OVER (ORDER BY AVG(variance_pct) DESC)` 给它们按差异幅度排名。这里用 `RANK()` 而不是 `ROW_NUMBER()`,是因为如果两份合同的平均差异恰好相同,应该给相同的名次(`RANK()` 会在并列后跳号),而不是随意打散成不同名次——`ROW_NUMBER()` 会强行给出不同序号,掩盖"这两份合同其实一样值得关注"这个事实。窗口函数和 `GROUP BY` 在同一个 CTE 里合法共存:先 `GROUP BY` 聚合出每份合同一行,窗口函数再对聚合后的结果集算排名,这是"先聚合后开窗"的标准模式。

```sql
-- Rank agreements not yet formally flagged, by variance proximity to the underreport threshold
WITH agreement_variance AS (
    SELECT
        la.agreement_number,
        l.company_name,
        l.compliance_score,
        ai.title,
        ROUND(AVG(raf.variance_pct), 2) AS avg_variance_pct,
        RANK() OVER (ORDER BY AVG(raf.variance_pct) DESC) AS variance_rank
    FROM license_agreement la
    JOIN licensee l ON l.id = la.licensee_id
    JOIN anime_ip ai ON ai.id = la.anime_ip_id
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
    WHERE raf.audit_status != 'confirmed_underreport'
    GROUP BY la.id
)
SELECT agreement_number, company_name, compliance_score, title, avg_variance_pct, variance_rank
FROM agreement_variance
WHERE variance_rank <= 10
ORDER BY variance_rank;
```

**期望结果说明:**
Top 10 合同的平均差异集中在 **10.58%-11.96%**——全部紧贴着 12% 的 `confirmed_underreport` 阈值,却还没有正式跨过去。榜首的 `LA-00081`(**Abbott-Munoz Merch Studio**,合规评分 37.94)差异达 11.96%,只差 0.04 个百分点就会被正式判定为低报。这份名单里的合同,合规评分普遍偏低(35-48 分区间),几乎全部来自已知的 risk 群体被授权商——说明这不是一批"新发现的可疑对象",而是同一批高风险被授权商名下还没滑过阈值的其他合同。稽核专员的下一步:对这 10 份合同提前启动约谈,而不是被动等下个季度的自动判定结果。

---

### Query 12: 产品上市后动销爬坡曲线

**业务背景:**
零售渠道分析师要给被授权商写一份"新品上市后大概多久能起量"的参考指引,帮他们规划首批备货量和补货节奏,避免要么首批囤太多压库存,要么备货不足错过早期销售窗口。她需要用历史数据描出一条典型的"上市后第几周,平均卖多少"曲线。

**类别:** Date + Aggregation
**难度:** Intermediate
**业务角色:** Retail Channel Analyst

**解题思路:**
对每一条 `pos_sell_through` 记录,计算它的 `week_start_date` 距离所属 SKU 的 `launch_date`过去了几周——同样要先转 `JULIANDAY` 再做减法、除以 7、`CAST` 成整数。按这个"上市后第几周" (`weeks_since_launch`) 分组求平均销量,就得到一条跨全部 SKU 汇总的生命周期曲线。这里不需要 CTE 或窗口函数,是一次直接的 JOIN + GROUP BY。SQLite 的 `GROUP BY` 可以直接引用 `SELECT` 里定义的别名(如下面的 `GROUP BY weeks_since_launch`),不需要重复写表达式;但 `WHERE` 子句不行——`WHERE` 在 `SELECT` 的别名生效之前就已经求值,所以要过滤 `weeks_since_launch` 的范围时,必须把完整的日期差表达式在 `WHERE` 里重新写一遍,不能直接写 `WHERE weeks_since_launch BETWEEN 0 AND 20`。

```sql
-- Build the average sell-through curve by weeks since SKU launch
SELECT
    CAST((JULIANDAY(p.week_start_date) - JULIANDAY(s.launch_date)) / 7 AS INTEGER) AS weeks_since_launch,
    COUNT(*) AS n_sku_weeks,
    ROUND(AVG(p.units_sold), 2) AS avg_units_sold
FROM pos_sell_through p
JOIN product_sku s ON s.id = p.product_sku_id
WHERE CAST((JULIANDAY(p.week_start_date) - JULIANDAY(s.launch_date)) / 7 AS INTEGER) BETWEEN 0 AND 20
GROUP BY weeks_since_launch
ORDER BY weeks_since_launch;
```

**期望结果说明:**
曲线形状非常清晰:上市第 0 周平均只卖约 2.5 件(刚铺货,渠道还没完全备齐),随后逐周爬升——第 1 周约 10.1 件,第 4 周约 26.5 件,到**第 8 周左右稳定在约 43-44 件/周**的满速水平,此后维持在这个区间(不在本查询窗口内的更长期数据显示,第 30 周之后才开始缓慢衰减)。给被授权商的实操建议:首批备货不必按"满速"来囤,前 8 周本来就是自然爬坡期;真正需要在第 6-8 周前后确认补货计划,以免满速期到货跟不上。

---

### Query 13: 地域范围与保底金额规模关系

**业务背景:**
高级授权经理在跟一位新客户谈判地域范围条款时,对方问"多授权加拿大能让保底金额提高多少"。她想用历史数据给出一个数量级的参考答案,而不是凭感觉报价。

**类别:** Aggregation
**难度:** Basic
**业务角色:** Senior Licensing Manager

**解题思路:**
一次简单的 `GROUP BY territory`,对比三种地域范围(`US`、`CANADA`、`US_CANADA`)的平均保底金额和平均版税率。没有 JOIN 需求,`license_agreement` 表本身就包含所有需要的列。这是一道典型的"为谈判提供参考数字"的基础查询,重点在于结果要按有业务意义的方式排序和呈现,而不是技巧本身。

```sql
-- Compare average minimum guarantee and royalty rate by territory scope
SELECT
    territory,
    COUNT(*) AS n_agreements,
    ROUND(AVG(minimum_guarantee_usd), 0) AS avg_mg_usd,
    ROUND(AVG(royalty_rate_pct), 2) AS avg_royalty_rate_pct
FROM license_agreement
GROUP BY territory
ORDER BY avg_mg_usd DESC;
```

**期望结果说明:**
`US_CANADA`(美加两国)平均保底金额约 18,920 美元,`US`(仅美国)约 13,710 美元,`CANADA`(仅加拿大)约 3,554 美元——地域范围越宽,保底金额规模越大,基本符合直觉(市场覆盖越大,期望销售额越高,保底也水涨船高)。三种范围的平均版税率(9.25%-9.48%)几乎没有差异,说明版税率主要由品类决定,和地域范围关系不大。高级授权经理可以据此回答:把仅美国授权扩展为美加两国,保底金额大约有 35% 左右的上浮空间,版税率本身不需要跟着调整。

---

### Query 14: SKU 畅销 / 滞销 Top 5

**业务背景:**
零售渠道分析师要给下季度的补货优先级排序,同时也要识别出该考虑下架的滞销 SKU,腾出货架和生产产能给真正动销的产品线。她需要一份"两端都要看"的清单:最好卖的 5 个和最不好卖的 5 个。

**类别:** Window Function
**难度:** Intermediate
**业务角色:** Retail Channel Analyst

**解题思路:**
用两个方向相反的 `RANK()` 窗口函数——一个按平均周销量降序排名 (`rank_top`),一个升序排名 (`rank_bottom`)——在同一个 CTE 里一次算出来,避免写两次几乎相同的查询再手工拼接。`HAVING COUNT(p.id) >= 10` 过滤掉上市时间太短、销售周数不足以稳定反映真实动销水平的 SKU(否则一个刚上市两周的 SKU 偶然卖爆或滞销,会因为样本量太小而误导排名)。最后用 `UNION ALL` 把两端结果拼在一起,加一列 `bucket` 标注是 TOP 还是 BOTTOM,方便阅读。

```sql
-- Rank SKUs by average weekly sell-through velocity, both ends of the distribution
WITH sku_perf AS (
    SELECT
        s.sku_code,
        s.sku_name,
        pc.category_name,
        ROUND(AVG(p.units_sold), 2) AS avg_weekly_units,
        RANK() OVER (ORDER BY AVG(p.units_sold) DESC) AS rank_top,
        RANK() OVER (ORDER BY AVG(p.units_sold) ASC) AS rank_bottom
    FROM product_sku s
    JOIN license_agreement la ON la.id = s.license_agreement_id
    JOIN product_category pc ON pc.id = la.product_category_id
    JOIN pos_sell_through p ON p.product_sku_id = s.id
    GROUP BY s.id
    HAVING COUNT(p.id) >= 10
)
SELECT sku_code, sku_name, category_name, avg_weekly_units, 'TOP' AS bucket FROM sku_perf WHERE rank_top <= 5
UNION ALL
SELECT sku_code, sku_name, category_name, avg_weekly_units, 'BOTTOM' AS bucket FROM sku_perf WHERE rank_bottom <= 5
ORDER BY bucket, avg_weekly_units DESC;
```

**期望结果说明:**
BOTTOM 5 全部来自 Home Goods & Decor、Stationery & Office、Accessories & Bags 三个低频品类(平均周销量 2.5-5.6 件);TOP 5 全部是 Collectible Trading Cards(平均周销量 98.3-106.7 件)。这再次印证 Query 1 的结论——品类本身的复购频次差异,比同品类内部 SKU 之间的差异大得多。分析师给出补货建议时,应该在"同品类内部"比较 SKU 排名(比如只在 Home Goods 品类内部找出该品类里最好卖的),而不是把不同品类的 SKU 直接混在一张榜单里比较,否则低频品类会永远垫底,掩盖了它内部真正值得关注的差异。

---

### Query 15: 未来 6 个月到期合同续约决策清单

**业务背景:**
授权经理团队每个季度要提前准备一份"即将到期合同"清单,附上每份合同最近的动销表现,好在续约窗口关闭前主动联系被授权商,而不是等合同自然到期后才手忙脚乱。这道题要把"哪些合同快到期"和"这些合同最近卖得好不好"拼在一张表里。

**类别:** CTE + Date Analysis
**难度:** Intermediate
**业务角色:** Licensing Manager

**解题思路:**
先用一个 CTE `recent_sales` 算出每份合同最近 12 周(84 天)的累计销量——用 `date('2026-06-30', '-84 days')` 做日期偏移,SQLite 的 `date()` 函数支持这种 `'-N days'` 修饰符语法。主查询筛出 `contract_status = 'active'` 且 `contract_end_date` 落在 `REFERENCE_DATE` 未来 180 天内的合同,LEFT JOIN 最近销量 CTE——这里必须用 LEFT JOIN 而不是 INNER JOIN,因为有些即将到期的合同可能近 12 周完全没有销售记录(SKU 已经不再补货),这种"零销量却快到期"的合同恰恰是最需要被看到的,INNER JOIN 会把它们直接漏掉。`COALESCE(rs.units_last_12w, 0)` 把 NULL 显式转成 0,避免结果里出现难以排序的空值。

```sql
-- Agreements expiring within 6 months, joined with recent sell-through for renewal triage
WITH recent_sales AS (
    SELECT s.license_agreement_id, SUM(p.units_sold) AS units_last_12w
    FROM pos_sell_through p
    JOIN product_sku s ON s.id = p.product_sku_id
    WHERE p.week_start_date > date('2026-06-30', '-84 days')
    GROUP BY s.license_agreement_id
)
SELECT
    la.agreement_number,
    ai.title,
    l.company_name,
    la.contract_end_date,
    COALESCE(rs.units_last_12w, 0) AS units_last_12w
FROM license_agreement la
JOIN anime_ip ai ON ai.id = la.anime_ip_id
JOIN licensee l ON l.id = la.licensee_id
LEFT JOIN recent_sales rs ON rs.license_agreement_id = la.id
WHERE la.contract_status = 'active'
  AND la.contract_end_date <= date('2026-06-30', '+180 days')
ORDER BY units_last_12w DESC
LIMIT 10;
```

**期望结果说明:**
未来 6 个月内共有 **29 份**活跃合同到期。近 12 周动销表现差异巨大——排名第一的 `LA-00094`(**Rustlight**,由 Davis and Sons Collectibles 持有)近 12 周卖出 11,200 件,是续约的优先候选;而榜单末尾会出现近 12 周销量为 0 的合同(需要单独运行不带 `LIMIT` 的完整查询查看),这些合同的续约谈判应该优先降级或直接放弃。授权经理的下一步:把这 29 份合同按近 12 周销量分成"优先续约"、"观望"、"不建议续约"三档,附上各自的 Query 5 保底达成进度作为补充依据,一起提交给下一轮续约决策会议。

---

### Query 16: 被授权商综合风险评分卡

**业务背景:**
版税合规总监想要一个"一眼看出谁最需要关注"的综合评分卡,而不是分别翻三张不同的报表(版税差异、越权铺货、合规评分)。她希望把版税低报幅度和越权铺货收入占比合并成一个单一的"综合风险分",用来决定下个季度稽核资源该优先投向哪几家被授权商。

**类别:** CTE + Aggregation
**难度:** Advanced
**业务角色:** Director of Royalty Compliance

**解题思路:**
这题把 Query 2(版税差异)和 Query 4(越权铺货)背后的两套聚合逻辑,各自封装成一个 CTE(`audit_summary` 和 `channel_summary`),再用 `LEFT JOIN` 拼到 `licensee` 主表上——`LEFT JOIN` 是必须的,因为不是每家被授权商都恰好有越权铺货记录,`channel_summary` 可能没有该被授权商的行,这时 `pct_unauthorized_revenue` 应该显示为 0 而不是让整行从结果里消失。最后把两个独立指标(`avg_variance_pct` 和 `pct_unauthorized_revenue`)直接相加得到 `combined_risk_score`——这是一个简化的合成指标,业务上假定两个风险维度权重相等,实际生产环境中可能需要按历史稽核成本或损失金额重新加权,这里保持简单是为了教学清晰。

```sql
-- Composite risk score combining royalty variance and unauthorized channel exposure
WITH audit_summary AS (
    SELECT la.licensee_id, AVG(raf.variance_pct) AS avg_variance_pct
    FROM license_agreement la
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
    GROUP BY la.licensee_id
),
channel_summary AS (
    SELECT
        la.licensee_id,
        ROUND(100.0 * SUM(CASE WHEN lac.id IS NULL THEN p.net_wholesale_revenue_usd ELSE 0 END) / SUM(p.net_wholesale_revenue_usd), 2) AS pct_unauthorized_revenue
    FROM pos_sell_through p
    JOIN product_sku s ON s.id = p.product_sku_id
    JOIN license_agreement la ON la.id = s.license_agreement_id
    LEFT JOIN license_agreement_channel lac
        ON lac.license_agreement_id = la.id AND lac.retail_channel_id = p.retail_channel_id
    GROUP BY la.licensee_id
)
SELECT
    l.company_name,
    l.risk_tier,
    ROUND(l.compliance_score, 1) AS compliance_score,
    ROUND(a.avg_variance_pct, 2) AS avg_royalty_variance_pct,
    COALESCE(c.pct_unauthorized_revenue, 0) AS pct_unauthorized_revenue,
    ROUND(a.avg_variance_pct + COALESCE(c.pct_unauthorized_revenue, 0), 2) AS combined_risk_score
FROM licensee l
JOIN audit_summary a ON a.licensee_id = l.id
LEFT JOIN channel_summary c ON c.licensee_id = l.id
ORDER BY combined_risk_score DESC
LIMIT 10;
```

**期望结果说明:**
结果出现一条极其干净的断层线:综合风险分排名前 7 名全部是 `risk_tier = 'risk'` 的被授权商(分数 14.76-25.37),第 8 名开始骤降到 `clean` 群体的 1.38-2.57 分。**Williams and Sons Toys** 综合分最高(25.37 = 13.61% 版税差异 + 11.76% 越权铺货收入占比),是下季度稽核资源应该优先投入的对象。这份评分卡证实了一个重要的业务洞察:版税低报和越权铺货这两个看似独立的合规问题,在这个组合里高度共现于同一小群被授权商身上——低合规评分不是"运气不好被抓到一次",而是系统性的多维度问题,合规总监应该把这 7 家列为"重点监控名单",而不是分别独立处理两类问题。

---

### Query 17: 线上 vs 线下渠道动销对比

**业务背景:**
零售渠道分析师想知道公司整体的动销规模在线上(电商、官网直营)和线下(大盒子连锁、专卖店、展会快闪)渠道之间是怎么分布的,为下一年度的渠道拓展预算分配提供参考——该继续押线下,还是加大线上渠道的授权范围。

**类别:** Aggregation + Join
**难度:** Basic
**业务角色:** Retail Channel Analyst

**解题思路:**
一次直接的 `pos_sell_through JOIN retail_channel`,按 `channel_type`(`online`/`offline`)分组统计总销量、总收入、以及每行记录的平均销量。`COUNT(DISTINCT rc.id)` 用来同时展示每个大类下有几个具体渠道,帮助读者理解"线下总量更大"有多少是因为线下渠道数量本身更多(3 个 vs 2 个),而不是单渠道效率更高。

```sql
-- Compare total sell-through volume between online and offline channel types
SELECT
    rc.channel_type,
    COUNT(DISTINCT rc.id) AS n_channels,
    SUM(p.units_sold) AS total_units,
    ROUND(SUM(p.net_wholesale_revenue_usd), 0) AS total_revenue,
    ROUND(AVG(p.units_sold), 2) AS avg_weekly_units_per_row
FROM pos_sell_through p
JOIN retail_channel rc ON rc.id = p.retail_channel_id
GROUP BY rc.channel_type;
```

**期望结果说明:**
线下渠道(3 个渠道合计)总销量约 101.6 万件、总收入约 1,126 万美元;线上渠道(2 个渠道合计)总销量约 60.8 万件、总收入约 699 万美元。但**单行平均销量几乎相同**(线下约 35.4 件/行,线上约 34.9 件/行)——说明总量差异主要来自线下渠道数量更多、被授权商在渠道选择时更偏好线下(回忆生成器里 `CHANNEL_SELECTION_WEIGHTS`:big_box_retail 和 specialty_retail 的权重明显高于电商),而不是线下渠道本身"卖得更快"。给渠道拓展预算的建议:线上渠道的单位效率并不差,如果目前渠道授权覆盖里线上占比偏低,加大线上渠道的授权范围有潜力贡献增量,而不只是分流现有线下销量。

---

### Query 18: 版税报告提交时效分析

**业务背景:**
版税稽核专员发现,被授权商提交版税报告的时间点参差不齐,有的报告期一结束很快就交了,有的拖到临近截止日才交。她想搞清楚公司整体的提交时效分布,判断要不要在标准合同模板里把提交时限从现在的默认宽限期收紧。

**类别:** Date Calculation
**难度:** Basic
**业务角色:** Royalty Audit Specialist

**解题思路:**
计算 `report_submitted_date` 和 `report_period_end_date` 之间的天数差(同样要先转 `JULIANDAY` 再相减),按天数分组计数,得到一个提交时效的分布直方图。这是一道纯粹的日期计算题,不涉及 JOIN,重点在于练习"两个日期相减得到天数"这个在几乎所有时序分析里都会用到的基本操作。

```sql
-- Distribution of days between report period end and actual submission
SELECT
    CAST(JULIANDAY(report_submitted_date) - JULIANDAY(report_period_end_date) AS INTEGER) AS submission_lag_days,
    COUNT(*) AS n_reports
FROM royalty_report
GROUP BY submission_lag_days
ORDER BY submission_lag_days;
```

**期望结果说明:**
提交时滞分布在 15-45 天之间,平均约 30.5 天,大致均匀分布在这个区间内,没有明显的"扎堆卡着最后期限交"的现象。这说明当前的提交时限设计比较宽松、没有制造出不必要的压力,但也意味着 Ember & Ash 平均要等一个月才能拿到上季度的版税数据——如果公司想加快现金流周转,可以考虑把默认提交时限从当前的上限 45 天收紧到 30 天左右,同时监控这是否会推高逾期未交的比例。

---

### Query 19: IP 热度层级与合同规模关系

**业务背景:**
VP of Licensing 在做下一年度的 IP 招募策略时,想验证一个假设:公司是不是把资源过度集中在少数几部 breakout 级 IP 上,而对 niche 级 IP 的投入明显不足?这会影响明年该不该主动拓展更多 niche 级长尾 IP 来分散风险。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** VP of Licensing

**解题思路:**
按 `anime_ip.popularity_tier` 分组,统计每个层级有多少部 IP、签了多少份合同、平均每部 IP 吸引多少份合同、平均保底金额规模。`COUNT(DISTINCT ai.id)` 和 `COUNT(la.id)` 分别统计"IP 数量"和"合同数量"两个不同粒度,两者相除得到"平均每部 IP 吸引几份合同"这个衍生指标,这是一次典型的"两个不同粒度的 COUNT 相除得到比率"模式。

```sql
-- Compare agreement volume and MG scale across IP popularity tiers
SELECT
    ai.popularity_tier,
    COUNT(DISTINCT ai.id) AS n_ips,
    COUNT(la.id) AS n_agreements,
    ROUND(1.0 * COUNT(la.id) / COUNT(DISTINCT ai.id), 1) AS avg_agreements_per_ip,
    ROUND(AVG(la.minimum_guarantee_usd), 0) AS avg_mg_usd
FROM anime_ip ai
JOIN license_agreement la ON la.anime_ip_id = ai.id
GROUP BY ai.popularity_tier
ORDER BY avg_mg_usd DESC;
```

**期望结果说明:**
breakout 级 IP(5 部)平均每部吸引 **7.2** 份合同、平均保底金额约 21,772 美元;mainstream 级(13 部)平均 5.5 份、约 14,455 美元;niche 级(6 部)只有平均 **1.7** 份、约 6,778 美元。差距确实存在,但没有 VP 担心的那么极端——niche 级 IP 平均仍能吸引接近 2 份合同,不是完全被放弃。这个结果支撑一个平衡的结论:公司资源确实向 breakout 级倾斜(合理,因为动销证据更强),但 niche 级 IP 组合仍保留了基本的多元化敞口,不需要大幅调整招募策略,可以考虑温和增加 niche 级 IP 的签约数量作为风险对冲,而不是大规模转向。

---

### Query 20: 续约优先级综合评分

**业务背景:**
一年一度的授权组合战略会议前,VP of Licensing 需要一份把"卖得好不好"(Query 1)、"版税诚不诚实"(Query 2)、"保底跟不跟得上"(Query 5)三个独立维度合并成一个单一优先级排名的清单,而不是让与会者自己在脑子里权衡三张不同的报表。这是整份季度评审 deck 的收尾页,直接决定哪些合同进入"优先续约"候选名单。

**类别:** CTE + Window Function
**难度:** Advanced
**业务角色:** VP of Licensing

**解题思路:**
这题把三个独立维度——总销量(`sku_perf`)、平均版税差异(`audit_summary`)、保底达成进度(`pacing`,复用 Query 5 的折算逻辑)——各自封装成 CTE,再用 `NTILE(4)` 窗口函数把每个维度分别切成四个分位桶(而不是直接用原始数值相加,因为三个维度的量纲完全不同:销量是件数、差异是百分比、达成进度是比率,直接相加没有意义)。销量按降序切分(卖得越多分位数越小、越好),版税差异按升序切分(差异越小分位数越小、越健康),保底达成按降序切分(进度越高分位数越小)——三个 `NTILE` 的排序方向要刻意保持"分位数越小 = 表现越好"的一致语义,否则相加得到的 `renewal_priority_score` 会失去意义。最后把三个分位数相加,分数越低代表三个维度综合表现越好,越应该优先续约。这是一种简化版的多指标合成打分法,在没有明确权重依据时,用分位数代替原始值是常见的稳健处理方式。

**和 Query 5 一样的边界情形在这里更棘手:** 一份刚签约、还没提交过版税报告的合同,如果用 `LEFT JOIN` 拼 `audit_summary` 和 `pacing`,再用 `COALESCE(..., 0)` 兜底,会出现自相矛盾的结果——`avg_variance_pct` 缺失值被垫成 0,在 `audit_health_quartile` 里等于"零差异、完全合规",排到最好的一档;但 `pacing_ratio` 缺失值同样被垫成 0,在 `mg_pacing_quartile` 里却等于"零进度、最差表现",排到最差的一档。同一份"数据还没攒够"的合同,在两个维度上被这个综合评分打出两种相反的解读。修复办法是把 `audit_summary` 和 `pacing` 的 `LEFT JOIN` 全部换成 `JOIN`,连同 `COALESCE` 兜底一起去掉——这样只有已经提交过至少一份报告的合同才会进入 `composite` CTE 参与打分,刚签约的新合同和 Query 5 一样,应该先进观察名单,不该直接出现在综合评分榜单里。

```sql
-- Composite renewal priority score combining sell-through, audit health, and MG pacing
WITH sku_perf AS (
    SELECT s.license_agreement_id, SUM(p.units_sold) AS total_units
    FROM pos_sell_through p JOIN product_sku s ON s.id = p.product_sku_id
    GROUP BY s.license_agreement_id
),
audit_summary AS (
    SELECT la.id AS agreement_id, AVG(raf.variance_pct) AS avg_variance_pct
    FROM license_agreement la
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
    GROUP BY la.id
),
pacing AS (
    SELECT la.id AS agreement_id,
        SUM(rr.reported_royalty_due_usd) / NULLIF(la.minimum_guarantee_usd * MIN(1.0,
            CAST((JULIANDAY('2026-06-30') - JULIANDAY(la.contract_start_date)) AS REAL)
            / (JULIANDAY(la.contract_end_date) - JULIANDAY(la.contract_start_date))), 0) AS pacing_ratio
    FROM license_agreement la
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    GROUP BY la.id
),
composite AS (
    SELECT
        la.agreement_number,
        ai.title,
        l.company_name,
        COALESCE(sp.total_units, 0) AS total_units_sold,
        NTILE(4) OVER (ORDER BY COALESCE(sp.total_units, 0) DESC) AS sell_through_quartile,
        NTILE(4) OVER (ORDER BY au.avg_variance_pct ASC) AS audit_health_quartile,
        NTILE(4) OVER (ORDER BY pc.pacing_ratio DESC) AS mg_pacing_quartile
    FROM license_agreement la
    JOIN anime_ip ai ON ai.id = la.anime_ip_id
    JOIN licensee l ON l.id = la.licensee_id
    LEFT JOIN sku_perf sp ON sp.license_agreement_id = la.id
    JOIN audit_summary au ON au.agreement_id = la.id
    JOIN pacing pc ON pc.agreement_id = la.id
    -- audit_summary / pacing 用 JOIN(不是 LEFT JOIN): 排除掉还没提交过报告的新签合同,
    -- 避免它们在两个分位桶上被打出自相矛盾的分数(见上方解题思路)
    WHERE la.contract_status = 'active'
)
SELECT
    agreement_number, title, company_name, total_units_sold,
    sell_through_quartile, audit_health_quartile, mg_pacing_quartile,
    (sell_through_quartile + audit_health_quartile + mg_pacing_quartile) AS renewal_priority_score
FROM composite
ORDER BY renewal_priority_score ASC
LIMIT 10;
```

**期望结果说明:**
参与打分的是 94 份"至少提交过一份版税报告"的活跃合同(刚签约的新合同已被排除,单独进观察名单)。最低(最优)分是 3——三个维度都排在第一分位——出现在 3 份合同上:`LA-00042`(Ember Knights: Genesis)、`LA-00075`(Wildfire Dorm)、`LA-00054`(Skybound Mariners),都是最没有争议的优先续约候选。分数在 4 的合同则是"某一个维度稍弱但整体仍健康"——比如 `LA-00085`(**Whispering Gears**,由 Rodriguez, Figueroa and Sanchez Apparel Co. 持有)总销量高达约 79,570 件,但 `audit_health_quartile` 排到第二档,提醒 VP 在续约时可以顺带加强对这份合同被授权商的稽核条款,而不是简单地"续约"或"不续约"二选一。这份榜单就是季度评审会议的核心议题清单:分数最低的一批直接进入续约谈判,分数最高(12 分,三个维度都垫底)的一批则应该重点讨论是否到期后终止合作。

---

## 业务问题对照表

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 内容动销与续约优先级 | Query 1, Query 14, Query 20 |
| Q2 版税稽核与低报风险 | Query 2, Query 7, Query 11, Query 16 |
| Q3 热度-动销滞后 | Query 3, Query 12 |
| Q4 越权铺货合规 | Query 4, Query 16 |
| Q5 保底金额达成追踪 | Query 5, Query 15, Query 20 |
| 运营与组合管理(未单独列为 marquee 问题,但支撑日常决策) | Query 6, Query 8, Query 9, Query 10, Query 13, Query 17, Query 18, Query 19 |
