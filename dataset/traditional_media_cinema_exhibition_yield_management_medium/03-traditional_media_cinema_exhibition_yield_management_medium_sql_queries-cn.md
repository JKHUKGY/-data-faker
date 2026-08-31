# 传统媒体 — 院线场次与卖品盈利分析 SQL 查询集

> 本文档覆盖 `traditional_media_cinema_exhibition_yield_management_medium` 数据集,业务背景请见 `01-traditional_media_cinema_exhibition_yield_management_medium_business_context-cn.md`,数据结构请见 `02-traditional_media_cinema_exhibition_yield_management_medium_er_document-cn.md`。
>
> **REFERENCE_DATE 约定:** 本数据集锚定在固定参考日 **2026-06-30**,数据窗口为 **2026-04-01 至 2026-06-30**。下面每条查询涉及日期边界的地方,都直接写字面量日期(如 `'2026-06-30'`),不使用 `DATE('now')`——这样无论你在哪一天运行这份文档里的 SQL,结果都完全可复现。

---

## 如何使用本文档

你是 Lakeshore Cinemas 新加入的 BI 分析师。这份文档里的 20 道查询,是 CFO 交给你的第一批任务——覆盖卖品毛利、高端银幕盈亏、深夜场保底票、银幕利用率和卖品搭售这五大类问题。每道查询包含五个部分:

1. **业务背景** —— 谁在问这个问题、为什么现在问、答案要拿去做什么决定。
2. **标签** —— 类别、难度、提问角色,方便你按技能或按业务线检索。
3. **解题思路** —— 在看 SQL 之前,先讲清楚该摸哪几张表、连接方式有什么坑、聚合粒度是什么、要不要用 CTE 或窗口函数。
4. **SQL** —— 可以直接在这份数据集的 SQLite 数据库里跑通的代码。
5. **预期结果与业务结论** —— 结果长什么样、对应哪个业务陷阱、下一步该做什么。

每道查询都能追溯到业务背景文档第 5 节列出的五个核心业务问题(Q1-Q5)之一,或者一个日常运营问题。这些 SQL 不是用来"跑一下看看"的,而是用来学的——注意每个 JOIN 为什么这样写、每个聚合粒度代表什么业务含义。

---

## 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| 1 | 卖品账面毛利率 vs 现金调整后毛利率 | CFO | 聚合 + CTE | 中级 |
| 2 | 按影院拆解会员兑换对卖品毛利的稀释 | VP of Concessions & Merchandising | 聚合 + 连接 + 子查询 | 中级 |
| 3 | 会员分层的兑换频次是否符合 Gold ≈ 3.6 倍 Standard 的假设 | Director of Loyalty & Marketing | 聚合 + 连接 | 基础 |
| 4 | 每块 IMAX 银幕的单银幕季度净贡献排名 | Facilities & Engineering Manager | CTE + 窗口函数 + 连接 | 高级 |
| 5 | Premium 与 IMAX 银幕按市场分层的平均净贡献对比 | BI Analyst | 聚合 + 连接 | 中级 |
| 6 | 银幕类型月度固定成本趋势 | Facilities & Engineering Manager | 聚合 + 日期分析 | 基础 |
| 7 | 周末 vs 工作日票价与上座率对比 | VP of Film Programming | 聚合 + CTE | 中级 |
| 8 | 深夜场"保底票"充场场次清单 | Regional Operations Manager | 连接 + 过滤 | 基础 |
| 9 | 按影院统计疑似充场场次数与赠票人次 | Regional Operations Manager | 聚合 + CTE | 中级 |
| 10 | 银幕利用率(上座率)排名,定位撤场候选 | BI Analyst | 窗口函数 + 聚合 | 高级 |
| 11 | Primary vs Secondary 市场整体利用率对比 | VP of Film Programming | 聚合 + 连接 | 基础 |
| 12 | 月度票房与观众人次趋势 | CFO | 日期分析 + 窗口函数 | 高级 |
| 13 | 各场次时段(daypart)的卖品搭售率对比 | BI Analyst | 聚合 + 连接 + CTE | 中级 |
| 14 | 爆米花家族 vs 其他卖品品类的销售表现 | BI Analyst | 聚合 + 文本匹配 | 基础 |
| 15 | Top 10 畅销卖品 SKU 排名(按毛利) | BI Analyst | 窗口函数 + 聚合 | 中级 |
| 16 | 各影院季度票房与卖品收入汇总(董事会材料) | Concession Operations Supervisor | 聚合 + 连接 + 日期分析 | 中级 |
| 17 | 各 daypart 的人均卖品消费额 | Concession Operations Supervisor | 聚合 + 日期分析 | 中级 |
| 18 | 各发行商的排片合约覆盖度 | VP of Film Programming | 聚合 + 连接 | 基础 |
| 19 | 会员跨影院兑换比例 | BI Analyst | 聚合 + 连接 | 基础 |
| 20 | 影院综合贡献排名(票房 + 卖品毛利 − 固定成本) | CFO | CTE + 窗口函数 + 多表连接 | 高级 |

---

## Query 1: 卖品账面毛利率 vs 现金调整后毛利率

**业务背景。** CFO 正在准备 2026 Q2 董事会材料的"卖品业务"这一页。过去几个季度,财务报表里卖品毛利率始终稳定在 70% 以上,是公司叙事里"我们不只是卖电影票"的核心证据。但上次高管会上,VP of Concessions & Merchandising 提到 Lakeshore Rewards 的兑换量这两年涨得很快,CFO 担心账面上的"卖品收入"里混入了会员免费兑换的部分——如果属实,真实收到现金的毛利率可能远低于财报展示的数字,董事会看到的可能是一个被美化过的故事。她需要在下周的董事会材料定稿前拿到"账面口径"和"现金口径"两个版本的对比。这题对应业务问题 Q1。

**标签。** 类别: 聚合 + CTE | 难度: 中级 | 角色: CFO

**解题思路。** 这题要同时摸两张表:`concession_sale`(正常付费销售)和 `loyalty_redemption`(会员兑换)。关键是理解"账面收入"和"现金收入"的口径差异——账面收入把兑换按 `item_full_price` 全价计入,现金收入只算 `concession_sale.gross_revenue`(兑换不产生现金)。成本侧两个口径相同:兑换出去的商品仍然产生了真实的 `item_unit_cost`。用两个 CTE 分别汇总这两张表,再在最终 SELECT 里手工组合出两个毛利率——不需要 JOIN,因为两张表之间没有需要连接的公共维度,直接各自聚合后用一个笛卡尔积(两个单行 CTE 相乘等价于并列)组合即可。

```sql
WITH paid_sales AS (
    SELECT
        SUM(gross_revenue) AS cash_revenue,
        SUM(cogs_amount) AS cogs_from_paid,
        SUM(units_sold) AS paid_units
    FROM concession_sale
    WHERE sale_date BETWEEN '2026-04-01' AND '2026-06-30'
),
redemptions AS (
    SELECT
        SUM(item_full_price) AS phantom_revenue,
        SUM(item_unit_cost) AS cogs_from_redeemed,
        COUNT(*) AS redeemed_units
    FROM loyalty_redemption
    WHERE redemption_date BETWEEN '2026-04-01' AND '2026-06-30'
)
SELECT
    ps.cash_revenue,
    ps.cash_revenue + rd.phantom_revenue AS recognized_revenue,
    ps.cogs_from_paid + rd.cogs_from_redeemed AS total_cogs,
    ROUND(
        100.0 * ((ps.cash_revenue + rd.phantom_revenue) - (ps.cogs_from_paid + rd.cogs_from_redeemed))
        / (ps.cash_revenue + rd.phantom_revenue), 2
    ) AS recognized_margin_pct,
    ROUND(
        100.0 * (ps.cash_revenue - (ps.cogs_from_paid + rd.cogs_from_redeemed)) / ps.cash_revenue, 2
    ) AS cash_margin_pct,
    ROUND(100.0 * rd.redeemed_units / (ps.paid_units + rd.redeemed_units), 2) AS redemption_share_pct
FROM paid_sales ps, redemptions rd;
```

**预期结果与业务结论。** 结果只有一行:`recognized_margin_pct` 约 **72.6%**,`cash_margin_pct` 约 **71.1%**,两者相差约 **1.5 个百分点**;`redemption_share_pct`(兑换件数占总件数比例)约 **5.4%**。也就是说,财报展示的毛利率比公司实际能收到现金的毛利率高出约 1.5 个百分点,而这个差距完全来自把免费兑换按全价确认收入的会计处理方式。这个缺口看似很小,但它发生在毛利率 70% 以上、几乎全额留存的卖品线上,而且会随会员兑换规模逐季累积——1.5 个百分点乘以全年卖品体量,是一笔实实在在会误导董事会的钱。CFO 应该在董事会材料里同时展示两个版本,并推动财务团队修改确认口径——用 `cash_margin_pct` 而不是 `recognized_margin_pct` 作为管理层真正盯的指标。

---

## Query 2: 按影院拆解会员兑换对卖品毛利的稀释

**业务背景。** VP of Concessions & Merchandising 看到 Query 1 的整体数字后,想知道问题是不是集中在少数几家影院——如果只是某几家影院的店长过度使用兑换做促销,那这是一个可以针对性纠正的运营问题,而不是全公司性的政策漏洞。她需要一份按影院排名的清单,找出兑换稀释最严重的几家。

**标签。** 类别: 聚合 + 连接 + 子查询 | 难度: 中级 | 角色: VP of Concessions & Merchandising

**解题思路。** 和 Query 1 一样需要两个口径的对比,但这次要按 `theater_id` 分组,所以两张表都需要保留 `theater_id` 维度。用两个子查询(或 CTE)分别按影院汇总 `concession_sale` 和 `loyalty_redemption`,再用 `LEFT JOIN` 把两者拼到一起——这里必须用 `LEFT JOIN` 而不是 `INNER JOIN`,因为理论上可能存在"某影院本季度完全没有兑换记录"的边界情况(虽然本数据集里每家影院都有兑换,但写 `LEFT JOIN` 是更安全的习惯,并配合 `COALESCE` 处理 NULL)。最后按 `redemption_share`(该影院的兑换稀释程度)降序排列。

```sql
WITH theater_paid AS (
    SELECT theater_id, SUM(gross_revenue) AS cash_revenue, SUM(units_sold) AS paid_units
    FROM concession_sale
    GROUP BY theater_id
),
theater_redeemed AS (
    SELECT theater_id, SUM(item_full_price) AS phantom_revenue, COUNT(*) AS redeemed_units
    FROM loyalty_redemption
    GROUP BY theater_id
)
SELECT
    t.theater_name,
    t.market_tier,
    tp.cash_revenue,
    COALESCE(tr.phantom_revenue, 0) AS phantom_revenue,
    tp.paid_units,
    COALESCE(tr.redeemed_units, 0) AS redeemed_units,
    ROUND(
        100.0 * COALESCE(tr.redeemed_units, 0) / (tp.paid_units + COALESCE(tr.redeemed_units, 0)), 2
    ) AS redemption_share_pct
FROM theater_paid tp
JOIN theater t ON t.id = tp.theater_id
LEFT JOIN theater_redeemed tr ON tr.theater_id = tp.theater_id
ORDER BY redemption_share_pct DESC
LIMIT 6;
```

**预期结果与业务结论。** 返回 18 家影院中稀释最严重的前 6 家,结果不是随机噪声,而是一个清晰的断层:这排名前 6(兑换稀释最严重)的影院**全部是 Secondary 市场影院**,`redemption_share_pct` 落在 **9%-11%**;而 12 家 Primary 市场影院的 `redemption_share_pct` 全部落在 **4%-6%**,两组之间没有交叉重叠。原因不难理解:会员注册时按"主场影院"分配,而分配权重(以及会员日常消费量)是按影院银幕数定的,但 Secondary 市场影院本身的自然客流(付费卖品件数的分母)比同等银幕数的 Primary 影院低得多——分子(兑换)降得慢,分母(付费)降得快,稀释比例自然被放大。VP of Concessions & Merchandising 应该优先在这 6 家 Secondary 影院调整兑换规则(比如降低这些影院的每会员月度兑换上限,或提高积分兑换门槛),而不是把政策一刀切地套用到全公司。

---

## Query 3: 会员分层的兑换频次是否符合 Gold ≈ 3.6 倍 Standard 的假设

**业务背景。** Director of Loyalty & Marketing 每个季度要向 CMO 证明分层会员体系(Standard/Silver/Gold)的投入产出比。她的假设是 Gold 会员(消费门槛最高、权益最多)的兑换频次显著高于 Standard 会员,值得继续投入更多权益去推动会员升级。这题用真实数据验证这个假设是否成立,以及成立到什么程度。

**标签。** 类别: 聚合 + 连接 | 难度: 基础 | 角色: Director of Loyalty & Marketing

**解题思路。** 只需要 `loyalty_member` 和 `loyalty_redemption` 两张表做一次 `LEFT JOIN`(用 LEFT JOIN 保留"本季度零兑换"的会员,虽然本数据集里这种会员很少),按 `tier` 分组统计会员数、兑换总数,再用兑换数除以会员数得到人均兑换频次。这是一次简单的 `GROUP BY` 聚合,不需要窗口函数或子查询。

```sql
SELECT
    lm.tier,
    COUNT(DISTINCT lm.id) AS n_members,
    COUNT(lr.id) AS n_redemptions,
    ROUND(1.0 * COUNT(lr.id) / COUNT(DISTINCT lm.id), 2) AS avg_redemptions_per_member,
    ROUND(SUM(lr.item_full_price), 0) AS total_phantom_value
FROM loyalty_member lm
LEFT JOIN loyalty_redemption lr ON lr.member_id = lm.id
GROUP BY lm.tier
ORDER BY avg_redemptions_per_member DESC;
```

**预期结果与业务结论。** 三行结果:`Gold` 约 767 名会员、人均兑换约 **9.1 次**;`Silver` 约 2,191 名会员、人均约 **4.6 次**;`Standard` 约 4,542 名会员、人均约 **2.5 次**。Gold 会员的兑换频次约为 Standard 的 **3.6 倍**,假设成立且幅度符合预期。Director 可以把这个数据放进 CMO 汇报,支持继续投入"消费满额自动升级 Gold"的营销活动——但也要提醒 CFO,Gold 会员兑换越多,Query 1 里的现金毛利稀释问题也会越严重,这是一个需要在会员权益设计和毛利保护之间做平衡的取舍。

---

## Query 4: 每块 IMAX 银幕的单银幕季度净贡献排名

**业务背景。** Facilities & Engineering Manager 每年都要向 CFO 提交下一年度的银幕设备资本开支(capex)计划,包括是否续签或升级各影院的 IMAX 设备授权合同。这些合同的续约费用不低,如果续约的银幕本身在持续亏钱,不如把预算转投到表现更好的影院。她需要一份按银幕(而不是按影院或整体项目)拆解的净贡献排名,把每一块 IMAX 银幕单独拎出来看。

**标签。** 类别: CTE + 窗口函数 + 连接 | 难度: 高级 | 角色: Facilities & Engineering Manager

**解题思路。** 这是本数据集里最考验建模思路的一题。核心概念是"银幕贡献" = 该银幕相对 Standard 银幕多收的票价溢价收入,减去该银幕的能耗与维保固定成本。第一步用一个 CTE 算出每家影院的 Standard 银幕平均票价(`standard_baseline`)作为比较基准——这里必须按 `theater_id` 分组算,因为不同影院的 Standard 定价可能因为周末场次占比不同而略有差异,不能用全公司统一基准。第二步把每场 `showtime` 的 `paid_attendance × (ticket_price − 该影院 Standard 均价)` 加总到银幕层级,得到溢价收入。第三步从 `screen_monthly_cost` 按银幕汇总整季度的固定成本。最后用 `RANK() OVER (ORDER BY 净贡献 ASC)` 给所有 IMAX 银幕排名,升序排列让最差的银幕排在最前面,方便直接看到谁在亏钱。

```sql
WITH standard_baseline AS (
    SELECT
        t.id AS theater_id,
        AVG(s.ticket_price) AS std_avg_price
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    WHERE sc.screen_type = 'Standard'
    GROUP BY t.id
),
screen_premium_revenue AS (
    SELECT
        sc.id AS screen_id,
        sc.theater_id,
        t.market_tier,
        SUM(s.paid_attendance * (s.ticket_price - sb.std_avg_price)) AS premium_ticket_revenue
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    JOIN standard_baseline sb ON sb.theater_id = sc.theater_id
    WHERE sc.screen_type = 'IMAX'
    GROUP BY sc.id, sc.theater_id, t.market_tier
),
screen_fixed_cost AS (
    SELECT screen_id, SUM(total_cost) AS fixed_cost
    FROM screen_monthly_cost
    GROUP BY screen_id
)
SELECT
    t.theater_name,
    spr.market_tier,
    ROUND(spr.premium_ticket_revenue, 0) AS premium_ticket_revenue,
    ROUND(sfc.fixed_cost, 0) AS fixed_cost,
    ROUND(spr.premium_ticket_revenue - sfc.fixed_cost, 0) AS net_contribution,
    RANK() OVER (ORDER BY spr.premium_ticket_revenue - sfc.fixed_cost ASC) AS worst_to_best_rank
FROM screen_premium_revenue spr
JOIN screen_fixed_cost sfc ON sfc.screen_id = spr.screen_id
JOIN theater t ON t.id = spr.theater_id
ORDER BY worst_to_best_rank;
```

**预期结果与业务结论。** 返回全部 10 块 IMAX 银幕,按净贡献从差到好排列。排名前三(最差)的三块银幕,`market_tier` 全部是 **Secondary**,`net_contribution` 约为 **-$12,900 到 -$13,300**;从第四名开始全部是 **Primary** 银幕,净贡献跳升到 **+$47,000 以上**,断层非常明显。结论很清楚:亏钱的不是"IMAX 这个业态",而是特定 3 家二线市场影院的 IMAX 银幕——Facilities & Engineering Manager 应该把这 3 份合同标记为"不建议续约或需重新谈判客流保底条款",而不是质疑整个 IMAX 升级计划。

---

## Query 5: Premium 与 IMAX 银幕按市场分层的平均净贡献对比

**业务背景。** 你(BI 分析师)在完成 Query 4 后,想再往前退一步,看一个更概括的对比:Premium(大画幅躺椅厅)银幕是不是也存在类似 IMAX 的"二线市场不划算"问题?还是这个问题只出现在 IMAX 身上?这能帮公司判断以后扩张躺椅厅时要不要也考虑市场分层的限制。

**标签。** 类别: 聚合 + 连接 | 难度: 中级 | 角色: BI Analyst

**解题思路。** 这题是 Query 4 逻辑的简化推广版:同样需要先算出 Standard 基准价,再算溢价收入和固定成本,但这次不需要窗口函数排名,只需要按 `(screen_type, market_tier)` 两个维度分组求平均净贡献即可。注意 `screen_type` 要同时包含 `'Premium'` 和 `'IMAX'`(`Standard` 本身不需要算,因为它就是基准,溢价恒为 0)。

```sql
WITH standard_baseline AS (
    SELECT t.id AS theater_id, AVG(s.ticket_price) AS std_avg_price
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    WHERE sc.screen_type = 'Standard'
    GROUP BY t.id
),
screen_premium_revenue AS (
    SELECT
        sc.id AS screen_id,
        sc.screen_type,
        t.market_tier,
        SUM(s.paid_attendance * (s.ticket_price - sb.std_avg_price)) AS premium_ticket_revenue
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    JOIN standard_baseline sb ON sb.theater_id = sc.theater_id
    WHERE sc.screen_type IN ('Premium', 'IMAX')
    GROUP BY sc.id, sc.screen_type, t.market_tier
),
screen_fixed_cost AS (
    SELECT screen_id, SUM(total_cost) AS fixed_cost
    FROM screen_monthly_cost
    GROUP BY screen_id
)
SELECT
    spr.screen_type,
    spr.market_tier,
    COUNT(*) AS n_screens,
    ROUND(AVG(spr.premium_ticket_revenue), 0) AS avg_premium_revenue,
    ROUND(AVG(sfc.fixed_cost), 0) AS avg_fixed_cost,
    ROUND(AVG(spr.premium_ticket_revenue - sfc.fixed_cost), 0) AS avg_net_contribution
FROM screen_premium_revenue spr
JOIN screen_fixed_cost sfc ON sfc.screen_id = spr.screen_id
GROUP BY spr.screen_type, spr.market_tier
ORDER BY spr.screen_type, spr.market_tier;
```

**预期结果与业务结论。** 三行结果(Premium 只在 Primary 出现,因为本数据集里 Secondary 影院都没有 Premium 银幕):`IMAX / Primary` 平均净贡献约 **+$53,500**,`IMAX / Secondary` 约 **-$13,100**,`Premium / Primary` 约 **+$44,000**。因为 Premium 银幕全部集中在 Primary 市场,这份数据本身还不能直接证明"Premium 在二线市场也会亏钱",但可以明确提醒扩张团队:**在批准任何 Secondary 影院新增 Premium 或 IMAX 银幕之前,必须先用 Query 4 的方法论做客流预测,而不是默认"高端厅=高回报"**。

---

## Query 6: 银幕类型月度固定成本趋势

**业务背景。** Facilities & Engineering Manager 需要向财务团队报告 Q2 三个月(4/5/6 月)各类型银幕的固定成本是否稳定,还是有异常波动(比如某月因为设备故障多花了一笔维保费)。这是一份常规的月度对账材料。

**标签。** 类别: 聚合 + 日期分析 | 难度: 基础 | 角色: Facilities & Engineering Manager

**解题思路。** 只需要 `screen` 和 `screen_monthly_cost` 两张表做一次 `JOIN`,按 `screen_type` 和 `cost_month` 两个维度分组求和。`cost_month` 已经是月初日期(如 `2026-04-01`),所以不需要额外的日期函数处理,直接分组即可——这是本数据集里少数几个"日期维度就是现成分组键"的例子。

```sql
SELECT
    sc.screen_type,
    smc.cost_month,
    COUNT(*) AS n_screens,
    ROUND(SUM(smc.energy_cost), 0) AS total_energy_cost,
    ROUND(SUM(smc.maintenance_cost), 0) AS total_maintenance_cost,
    ROUND(SUM(smc.total_cost), 0) AS total_cost
FROM screen_monthly_cost smc
JOIN screen sc ON sc.id = smc.screen_id
GROUP BY sc.screen_type, smc.cost_month
ORDER BY sc.screen_type, smc.cost_month;
```

**预期结果与业务结论。** 9 行结果(3 种银幕类型 x 3 个月)。`IMAX` 每月合计固定成本约在 **$104,000 到 $107,000** 之间波动(10 块银幕),`Premium` 约在 **$44,000 上下**(17 块银幕),`Standard` 约在 **$97,000 上下**(65 块银幕)。三个月之间的波动幅度都在 ±5% 以内,没有异常尖峰,说明本季度没有发生大额突发维修——这份材料可以原样交给财务团队做常规对账,不需要额外说明。

---

## Query 7: 周末 vs 工作日票价与上座率对比

**业务背景。** VP of Film Programming 想确认现行的周五/周六票价上浮 15% 的定价策略,有没有把观众吓跑——如果周末涨价后上座率反而下降,说明溢价定得过高,应该考虑下调。

**标签。** 类别: 聚合 + CTE | 难度: 中级 | 角色: VP of Film Programming

**解题思路。** 关键在于怎么从 `showtime_datetime` 判断"是不是周五或周六"。SQLite 的 `strftime('%w', ...)` 返回 0(周日)到 6(周六)的星期数字,所以周五是 `5`、周六是 `6`。用一个 `CASE WHEN` 把每场场次打上 `Weekend` / `Weekday` 标签,再按这个标签分组聚合平均票价和平均上座人数。这里不需要 CTE 也能写,但用一层包装(子查询或 CTE)把"打标签"这一步单独隔离出来,可读性更好。

```sql
WITH labeled_showtimes AS (
    SELECT
        *,
        CASE
            WHEN CAST(strftime('%w', showtime_datetime) AS INTEGER) IN (5, 6) THEN 'Weekend (Fri/Sat)'
            ELSE 'Weekday'
        END AS day_group
    FROM showtime
)
SELECT
    day_group,
    COUNT(*) AS n_showtimes,
    ROUND(AVG(ticket_price), 2) AS avg_ticket_price,
    ROUND(AVG(paid_attendance), 1) AS avg_paid_attendance
FROM labeled_showtimes
GROUP BY day_group;
```

**预期结果与业务结论。** 两行结果:`Weekday` 平均票价约 **$13.39**、平均上座人数约 **30.4**;`Weekend (Fri/Sat)` 平均票价约 **$15.39**(涨了约 15%,符合定价规则)、平均上座人数约 **37.5**(不降反升,涨幅约 23%)。结论是周末溢价没有吓跑观众,反而周末本身自然客流更大——**现行定价策略是合理的,VP 甚至可以研究是否还有进一步上调周末票价的空间**,而不是像最初担心的那样需要降价。

---

## Query 8: 深夜场"保底票"充场场次清单

**业务背景。** Regional Operations Manager 上周收到一线员工的匿名反馈,说某些深夜场"经理会自己刷卡买一堆票"。她需要一份具体的场次清单去核实这个说法,而不是听传闻——如果清单存在且模式清晰,她要带着证据去找排片副总裁讨论怎么处理。

**标签。** 类别: 连接 + 过滤 | 难度: 基础 | 角色: Regional Operations Manager

**解题思路。** 这题不需要聚合,只需要把 `showtime` 和 `film_booking` 连接起来,过滤出 `daypart = 'late_night'` 且 `has_minimum_guarantee = 1` 且 `paid_attendance` 明显低于 `minimum_attendance_per_showtime` 的场次——这种"自然客流不够、但还是达标了"的场次就是充场嫌疑最大的。用 `paid_attendance < minimum_attendance_per_showtime * 0.6` 作为筛选阈值(自然客流不到门槛六成),同时展示 `comp_attendance` 让读者一眼看出赠票有多少。

```sql
SELECT
    t.theater_name,
    ft.title,
    s.showtime_datetime,
    fb.minimum_attendance_per_showtime,
    s.paid_attendance,
    s.comp_attendance,
    ROUND(100.0 * s.comp_attendance / (s.paid_attendance + s.comp_attendance), 1) AS comp_share_pct
FROM showtime s
JOIN film_booking fb ON fb.id = s.film_booking_id
JOIN film_title ft ON ft.id = fb.film_id
JOIN screen sc ON sc.id = s.screen_id
JOIN theater t ON t.id = sc.theater_id
WHERE s.daypart = 'late_night'
    AND fb.has_minimum_guarantee = 1
    AND s.paid_attendance < fb.minimum_attendance_per_showtime * 0.6
ORDER BY comp_share_pct DESC
LIMIT 20;
```

**预期结果与业务结论。** 返回一份场次清单(本数据集里这类场次近 3,000 场,这里只取 `comp_share_pct` 最高的 20 条),典型的一行长这样:`paid_attendance = 8`,`comp_attendance = 14`,`comp_share_pct ≈ 63.6%`——超过六成的"到场观众"其实是影院自己买单的。这份清单证实了员工反馈属实,而且不是个例,是一个跨影院普遍存在的模式。Regional Operations Manager 可以直接把这份清单带给 VP of Film Programming,推动重新和发行商谈判最低开场人数条款,或者调整这些影片深夜场的排片策略(比如干脆取消深夜场,把银幕时间让给上座率更好的场次)。

---

## Query 9: 按影院统计疑似充场场次数与赠票人次

**业务背景。** Regional Operations Manager 看完 Query 8 的清单后,想知道这个问题在 18 家影院里是不是分布均匀,还是集中在少数几家。这决定了她是要发一份全员通知,还是只找几个店长单独谈话。

**标签。** 类别: 聚合 + CTE | 难度: 中级 | 角色: Regional Operations Manager

**解题思路。** 在 Query 8 的过滤逻辑基础上,加一层聚合。先用 CTE 把符合"疑似充场"条件的场次筛出来(和 Query 8 一样的 WHERE 条件),再按 `theater_id` 分组统计场次数和赠票总人次。这里 CTE 的作用是把"什么算充场"这个业务规则和后续的聚合逻辑分开,如果以后规则要调整(比如阈值从 0.6 改成 0.5),只需要改 CTE 内部,不影响外层聚合逻辑。

```sql
WITH suspected_buyback AS (
    SELECT
        sc.theater_id,
        s.comp_attendance
    FROM showtime s
    JOIN film_booking fb ON fb.id = s.film_booking_id
    JOIN screen sc ON sc.id = s.screen_id
    WHERE s.daypart = 'late_night'
        AND fb.has_minimum_guarantee = 1
        AND s.paid_attendance < fb.minimum_attendance_per_showtime * 0.6
)
SELECT
    t.theater_name,
    t.market_tier,
    COUNT(*) AS n_suspected_showtimes,
    SUM(sb.comp_attendance) AS total_comp_attendance
FROM suspected_buyback sb
JOIN theater t ON t.id = sb.theater_id
GROUP BY t.theater_name, t.market_tier
ORDER BY n_suspected_showtimes DESC;
```

**预期结果与业务结论。** 返回全部 18 家影院,每家都有一定数量的疑似充场场次(因为这个模式是排片合约层面的系统性行为,不是个别影院的问题),场次数大致与该影院的银幕数和 tentpole 排片密度成正比,没有哪一家显著异常偏高。结论是:**这是一个全公司性的合约执行问题,而不是个别影院管理不善**,Regional Operations Manager 应该发一份全员政策通知,而不是针对个别店长约谈——真正该解决问题的地方是和发行商重新谈判条款(见 Query 8 结论),而不是运营层面的执行监督。

---

## Query 10: 银幕利用率(上座率)排名,定位撤场候选

**业务背景。** CFO 在做年度资本开支规划,想知道哪些银幕的利用率持续偏低,值得考虑改造成其他用途(比如缩小放映厅、腾出空间做私人影院包场业务)。你需要给出一份全公司银幕的利用率排名。

**标签。** 类别: 窗口函数 + 聚合 | 难度: 高级 | 角色: BI Analyst

**解题思路。** 上座率(occupancy rate) = `paid_attendance / seat_capacity`,这是场次层面的指标,要先算出每场场次的上座率,再按银幕聚合成平均值。用窗口函数 `RANK()` 而不是简单 `ORDER BY` 的原因是:管理层不仅想知道排名,还想知道这块银幕在全公司 92 块银幕里处于什么百分位,方便后续设定"利用率排名后 10% 考虑改造"这样的统一规则,而 `RANK()` 的输出可以直接支持这种阈值判断。

```sql
SELECT
    sc.id AS screen_id,
    sc.screen_type,
    t.market_tier,
    t.theater_name,
    ROUND(AVG(1.0 * s.paid_attendance / sc.seat_capacity) * 100, 1) AS avg_occupancy_pct,
    COUNT(*) AS n_showtimes,
    RANK() OVER (ORDER BY AVG(1.0 * s.paid_attendance / sc.seat_capacity) ASC) AS lowest_occupancy_rank
FROM showtime s
JOIN screen sc ON sc.id = s.screen_id
JOIN theater t ON t.id = sc.theater_id
GROUP BY sc.id, sc.screen_type, t.market_tier, t.theater_name
ORDER BY lowest_occupancy_rank
LIMIT 10;
```

**预期结果与业务结论。** 排名最低的 3 块银幕全部是 **Secondary 市场的 IMAX 银幕**(平均上座率仅 **3%-4%**),紧随其后的是几块 Secondary 市场的 Standard 银幕(约 **12%**)。这份排名和 Query 4 的净贡献排名高度一致,进一步印证了 Q2 陷阱——**利用率最低的银幕正是净贡献为负的那 3 块 IMAX**。CFO 可以据此优先审查这 3 块银幕的资本开支去留,而不是均匀地对所有银幕做维护预算削减。

---

## Query 11: Primary vs Secondary 市场整体利用率对比

**业务背景。** VP of Film Programming 想在做全年排片策略之前,先看一个宏观数字:Primary 和 Secondary 两类市场整体的上座率差异有多大,以此判断要不要对 Secondary 影院采取不同的排片密度(比如减少场次数而不是硬凑满 5 场/天)。

**标签。** 类别: 聚合 + 连接 | 难度: 基础 | 角色: VP of Film Programming

**解题思路。** 比 Query 10 更简化的版本,不需要窗口函数,只需要按 `market_tier` 一个维度分组求平均上座率。三张表(`showtime`、`screen`、`theater`)做两次 `JOIN` 即可。

```sql
SELECT
    t.market_tier,
    ROUND(AVG(1.0 * s.paid_attendance / sc.seat_capacity) * 100, 1) AS avg_occupancy_pct,
    COUNT(*) AS n_showtimes,
    SUM(s.paid_attendance) AS total_paid_attendance
FROM showtime s
JOIN screen sc ON sc.id = s.screen_id
JOIN theater t ON t.id = sc.theater_id
GROUP BY t.market_tier;
```

**预期结果与业务结论。** 两行结果:`Primary` 平均上座率明显高于 `Secondary`(差距在 10-15 个百分点量级)。这不算意外发现,但为排片策略提供了量化依据:VP 可以考虑给 Secondary 影院的场次密度做适度精简(比如把 IMAX 从 3 场/天降到 2 场/天),把节省下来的放映窗口让给上座率更稳的 Standard 银幕。

---

## Query 12: 月度票房与观众人次趋势

**业务背景。** CFO 在准备董事会材料的"本季度趋势"这一页,需要看 4/5/6 三个月票房和观众人次是逐月增长、持平还是下滑,并且想用环比变化率而不是绝对值来讲这个故事。

**标签。** 类别: 日期分析 + 窗口函数 | 难度: 高级 | 角色: CFO

**解题思路。** 先用 `strftime('%Y-%m', ...)` 把场次日期归到月份,聚合出每月票房和人次。然后用窗口函数 `LAG()` 取出"上一个月"的数值,在同一行里算出环比变化率——这样比自己写自连接(self join)更简洁,也是这题选择窗口函数而不是普通聚合的原因。

```sql
WITH monthly_summary AS (
    SELECT
        strftime('%Y-%m', showtime_datetime) AS year_month,
        SUM(ticket_revenue) AS total_ticket_revenue,
        SUM(paid_attendance) AS total_paid_attendance
    FROM showtime
    GROUP BY year_month
)
SELECT
    year_month,
    ROUND(total_ticket_revenue, 0) AS total_ticket_revenue,
    total_paid_attendance,
    ROUND(
        100.0 * (total_ticket_revenue - LAG(total_ticket_revenue) OVER (ORDER BY year_month))
        / LAG(total_ticket_revenue) OVER (ORDER BY year_month), 1
    ) AS revenue_mom_change_pct
FROM monthly_summary
ORDER BY year_month;
```

**预期结果与业务结论。** 三行结果:4 月票房约 **$614.9 万**,5 月约 **$635.4 万**(环比 **+3.3%**),6 月约 **$534.8 万**(环比 **-15.8%**)。6 月的明显下滑,第一反应不该是恐慌,而是结合 `film_booking` 的数据检查——6 月是否恰好缺少新的 tentpole 影片上映,导致片单强度不如 4/5 月。CFO 在董事会材料里应该把这个下滑归因于片单排期的季节性,而不是把它讲成"生意在变差",同时提醒排片团队关注 Q3 的片单强度是否能接上。

---

## Query 13: 各场次时段(daypart)的卖品搭售率对比

**业务背景。** 你在协助 Concession Operations Supervisor 准备下季度的卖品备货计划,想搞清楚 matinee、prime、late_night 三个时段的卖品搭售率(每个买票观众平均带动多少件卖品消费)有没有显著差异,这会影响不同时段的柜台人手安排和备货量。

**标签。** 类别: 聚合 + 连接 + CTE | 难度: 中级 | 角色: BI Analyst

**解题思路。** 需要把 `showtime`(观众数的来源)和 `concession_sale`(卖品件数的来源)分别按 `daypart` 汇总,再拿两个汇总结果相除。这两张表之间没有直接的外键连接(`concession_sale` 的粒度是"影院 x 日期 x 时段 x SKU",不是场次级别),所以正确做法是用两个独立的 CTE 各自按 `daypart` 聚合,最后用 `daypart` 做连接键拼在一起,而不是直接 JOIN 两张明细表(那样会造成不正确的笛卡尔积展开)。

```sql
WITH attendance_by_daypart AS (
    SELECT daypart, SUM(paid_attendance) AS total_attendance
    FROM showtime
    GROUP BY daypart
),
units_by_daypart AS (
    SELECT daypart, SUM(units_sold) AS total_units
    FROM concession_sale
    GROUP BY daypart
)
SELECT
    a.daypart,
    a.total_attendance,
    u.total_units,
    ROUND(1.0 * u.total_units / a.total_attendance, 3) AS attach_rate
FROM attendance_by_daypart a
JOIN units_by_daypart u ON u.daypart = a.daypart
ORDER BY attach_rate DESC;
```

**预期结果与业务结论。** 三行结果,三个时段的搭售率其实非常接近,都在 **0.40** 附近(即平均每个买票观众带动约 0.4 件卖品消费——大量观众结伴合买一份、部分观众完全不买,所以人均件数远低于 1),没有哪个时段明显更高或更低。这个"没有差异"本身就是一个有用的结论:**卖品备货和人手安排可以简单按各时段的观众人次比例分配,不需要为特定时段单独设计不同的搭售假设**——比想象中更简单,也提醒 Concession Operations Supervisor 不要过度设计排班规则。

---

## Query 14: 爆米花家族 vs 其他卖品品类的销售表现

**业务背景。** 公司内部一直流传"我们卖的是爆米花,电影只是卖爆米花的理由"这句话(详见业务背景文档第 2 节)。Concession Operations Supervisor 想用数据验证这句话是不是夸张——爆米花家族(`item_name` 含 "Popcorn" 的 4 个 SKU)在卖品业务里到底占多大比重。

**标签。** 类别: 聚合 + 文本匹配 | 难度: 基础 | 角色: Concession Operations Supervisor

**解题思路。** 用 `LIKE '%Popcorn%'` 对 `concession_item.item_name`做文本匹配,把 24 个 SKU 分成"爆米花家族"和"其他"两组,再按这个分组聚合销量、收入和毛利。这是本文档里唯一用到 `LIKE` 模式匹配的查询——因为爆米花家族没有单独的 `category` 值可以直接筛(`category = 'Popcorn'` 也可以达到同样效果,这里用 `LIKE` 是为了展示当品类命名不规范、或者想跨品类抓取"名字里带某关键词的商品"时的处理方式)。

```sql
SELECT
    CASE WHEN ci.item_name LIKE '%Popcorn%' THEN 'Popcorn family' ELSE 'Other' END AS product_group,
    SUM(cs.units_sold) AS total_units,
    ROUND(SUM(cs.gross_revenue), 0) AS total_revenue,
    ROUND(SUM(cs.gross_revenue - cs.cogs_amount), 0) AS total_gross_profit
FROM concession_sale cs
JOIN concession_item ci ON ci.id = cs.item_id
GROUP BY product_group;
```

**预期结果与业务结论。** 两行结果:`Popcorn family`(仅 4 个 SKU)贡献约 **161,000 件**、收入约 **$142.4 万**、毛利约 **$99.0 万**;`Other`(其余 20 个 SKU)贡献约 **337,500 件**、收入约 **$199.0 万**、毛利约 **$148.8 万**。爆米花家族只占 24 个 SKU 里的 4 个(约 17% 的品类数),却贡献了约 **32%-40%** 的销量和毛利——集中度确实很高,但"电影只是卖爆米花的理由"这句话略有夸张(爆米花没有占到毛利的一半)。Concession Operations Supervisor 可以据此确认爆米花补货优先级最高,但备货预算不应完全压在爆米花上,饮料和组合套餐同样重要。

---

## Query 15: Top 10 畅销卖品 SKU 排名(按毛利)

**业务背景。** Concession Operations Supervisor 需要一份 SKU 级别的畅销榜,用于跟供应商谈下季度的采购折扣——采购量最大的几个 SKU 有资格争取更好的批发价。

**标签。** 类别: 窗口函数 + 聚合 | 难度: 中级 | 角色: BI Analyst

**解题思路。** 按 `item_id` 聚合销量和毛利,用 `RANK()` 按毛利降序排名,取前 10。这里选择按"毛利"而不是"销量"排名,是因为供应商谈判真正该优先争取折扣的是对公司利润贡献最大的商品,而不是单纯卖得最多的商品——这两者不一定是同一批 SKU(单价低但走量的商品销量可能很高,毛利贡献却不一定最大)。

```sql
SELECT
    ci.item_name,
    ci.category,
    SUM(cs.units_sold) AS total_units,
    ROUND(SUM(cs.gross_revenue - cs.cogs_amount), 0) AS total_gross_profit,
    RANK() OVER (ORDER BY SUM(cs.gross_revenue - cs.cogs_amount) DESC) AS gross_profit_rank
FROM concession_sale cs
JOIN concession_item ci ON ci.id = cs.item_id
GROUP BY ci.item_name, ci.category
ORDER BY gross_profit_rank
LIMIT 10;
```

**预期结果与业务结论。** 返回毛利贡献前 10 的 SKU,前 6 名被 `Large Popcorn`、`Large Fountain Drink`、`Caramel Popcorn`、`Medium Popcorn`、`Medium Fountain Drink`、`ICEE Frozen Drink` 占据——大号/中号的爆米花与饮料因为件数基数大,总毛利贡献反而超过单价更高但件数少得多的组合套餐(`Popcorn + Drink Combo` 系列排在第 7、9 名)。这提醒 Concession Operations Supervisor 一个容易被直觉误导的地方:**单价最高的商品不一定是毛利贡献最大的商品,走量的基础款爆米花和饮料才是真正的现金牛**。供应商谈判应该优先聚焦这几款基础 SKU 的采购价,而不是把精力放在组合套餐上。

---

## Query 16: 各影院季度票房与卖品收入汇总(董事会材料)

**业务背景。** Concession Operations Supervisor 需要为董事会材料准备一份最基础的"全影院一览表",列出每家影院本季度的票房、卖品收入和观众规模,作为其他所有深入分析的背景参照表。

**标签。** 类别: 聚合 + 连接 + 日期分析 | 难度: 中级 | 角色: Concession Operations Supervisor

**解题思路。** 需要把票房(来自 `showtime`,经过 `screen` 关联到 `theater`)和卖品收入(`concession_sale` 已经直接带 `theater_id`)分别汇总后按影院拼接。这是一个三路数据源的汇总:场次表、卖品表、影院维度表。用两个 CTE 分头聚合,再各自 JOIN 到 `theater` 主表,避免在同一个 JOIN 链路里因为多对多关系造成数据重复计算。

```sql
WITH theater_ticket AS (
    SELECT t.id AS theater_id, SUM(s.ticket_revenue) AS ticket_revenue, SUM(s.paid_attendance) AS paid_attendance
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    GROUP BY t.id
),
theater_concession AS (
    SELECT theater_id, SUM(gross_revenue) AS concession_revenue
    FROM concession_sale
    GROUP BY theater_id
)
SELECT
    t.theater_name,
    t.market_tier,
    ROUND(tt.ticket_revenue, 0) AS ticket_revenue,
    tt.paid_attendance,
    ROUND(tc.concession_revenue, 0) AS concession_revenue,
    ROUND(tt.ticket_revenue + tc.concession_revenue, 0) AS total_revenue
FROM theater_ticket tt
JOIN theater t ON t.id = tt.theater_id
JOIN theater_concession tc ON tc.theater_id = tt.theater_id
ORDER BY total_revenue DESC;
```

**预期结果与业务结论。** 返回全部 18 家影院,按总收入降序排列。Primary 市场影院(尤其是芝加哥、密尔沃基这几家)稳居前列,Secondary 市场影院普遍排在末尾。这份表格本身不直接得出结论,而是作为董事会材料的背景页——后续的 Query 20(综合贡献排名)会在这份收入表的基础上,进一步扣除固定成本,给出更接近"真实盈利能力"的排名。

---

## Query 17: 各 daypart 的人均卖品消费额

**业务背景。** Concession Operations Supervisor 想知道 matinee、prime、late_night 三个时段,平均每个观众花在卖品上的金额有没有差异——如果某个时段人均消费明显更高,值得在那个时段加派柜台人手、优先补货高毛利商品。

**标签。** 类别: 聚合 + 日期分析 | 难度: 中级 | 角色: Concession Operations Supervisor

**解题思路。** 和 Query 13 的结构类似(两个独立 CTE 按 `daypart` 汇总后拼接),但这次算的是"人均消费额"(总收入 / 总观众数)而不是"人均件数"。这题保留独立展示是因为消费金额和商品件数是运营团队关心的两个不同指标——件数决定备货数量,金额决定利润贡献,两者不一定同向变化(比如某时段件数少但都买了高价组合套餐)。

```sql
WITH attendance_by_daypart AS (
    SELECT daypart, SUM(paid_attendance) AS total_attendance
    FROM showtime
    GROUP BY daypart
),
revenue_by_daypart AS (
    SELECT daypart, SUM(gross_revenue) AS total_revenue
    FROM concession_sale
    GROUP BY daypart
)
SELECT
    a.daypart,
    a.total_attendance,
    ROUND(r.total_revenue, 0) AS total_concession_revenue,
    ROUND(r.total_revenue / a.total_attendance, 2) AS revenue_per_attendee
FROM attendance_by_daypart a
JOIN revenue_by_daypart r ON r.daypart = a.daypart
ORDER BY revenue_per_attendee DESC;
```

**预期结果与业务结论。** 三行结果,`revenue_per_attendee` 在三个时段之间差异很小(与 Query 13 的搭售率结论一致,因为件数和金额的分布模式高度相关)。结论同样是:**不需要为特定时段设计差异化的卖品运营策略,现有的按观众人次比例分配人手和备货的做法已经足够**,Concession Operations Supervisor 可以把精力更多放在 Query 14/15 揭示的品类和 SKU 优化上,而不是时段优化上。

---

## Query 18: 各发行商的排片合约覆盖度

**业务背景。** VP of Film Programming 每季度要评估和各大发行商的合作深度,决定下季度的排片谈判优先级——覆盖影院数最多、合约数量最大的发行商,通常也是最值得投入关系维护精力(比如优先给他们的新片留出黄金档期)的合作伙伴。

**标签。** 类别: 聚合 + 连接 | 难度: 基础 | 角色: VP of Film Programming

**解题思路。** 把 `film_title` 和 `film_booking` 用发行商名称关联后分组聚合,统计每个发行商名下的影片数、排片合约总数,以及覆盖的不同影院数量(用 `COUNT(DISTINCT theater_id)`,因为同一个发行商的多部电影可能覆盖同一家影院多次,不去重会重复计数)。

```sql
SELECT
    ft.distributor_name,
    COUNT(DISTINCT ft.id) AS n_films,
    COUNT(fb.id) AS n_bookings,
    COUNT(DISTINCT fb.theater_id) AS n_theaters_covered
FROM film_title ft
JOIN film_booking fb ON fb.film_id = ft.id
GROUP BY ft.distributor_name
ORDER BY n_bookings DESC;
```

**预期结果与业务结论。** 六行结果(对应 6 家虚构发行商),`Northgate Media` 和 `Redline Entertainment` 排片合约数最多(均超过 100 份);`Prairie Peak Studios` 和 `Brightwell Films` 排片合约数明显更少(30-40 份左右),说明这两家目前的合作体量明显小于头部——名下影片更少、常规影片占比更高。(注意:六家发行商都覆盖了全部 18 家影院,因为每家手里至少有一部 tentpole 大片,而 tentpole 是全院线宽发行的,所以 `n_theaters_covered` 这一列区分度不大,真正拉开差距的是 `n_films` 和 `n_bookings`。)VP of Film Programming 可以据此在下季度和头部两家谈更优惠的分账条款(既然合作量最大,议价筹码也更大),同时评估是否要扩大与 Prairie Peak、Brightwell 的合作、或引入新发行商来分散对头部的依赖。

---

## Query 19: 会员跨影院兑换比例

**业务背景。** Director of Loyalty & Marketing 想知道会员是不是真的会"跨影院"兑换积分(比如去另一个城市出差时顺便看场电影、用主场影院攒的积分兑换),这关系到 Lakeshore Rewards 要不要在会员卡面/App 里加一个"附近影院"的引导功能,提升跨店转化。

**标签。** 类别: 聚合 + 连接 | 难度: 基础 | 角色: BI Analyst

**解题思路。** 把 `loyalty_redemption.theater_id` 和 `loyalty_member.home_theater_id` 做比较,统计两者不一致的比例。这题的重点是理解为什么要用 `JOIN` 而不是直接在 `loyalty_redemption` 表里找答案——因为"主场影院"这个信息存在 `loyalty_member` 表里,不在 `loyalty_redemption` 表里,必须先连接两张表才能做比较。

```sql
SELECT
    ROUND(
        100.0 * SUM(CASE WHEN lr.theater_id != lm.home_theater_id THEN 1 ELSE 0 END) / COUNT(*), 2
    ) AS cross_theater_redemption_pct,
    COUNT(*) AS total_redemptions
FROM loyalty_redemption lr
JOIN loyalty_member lm ON lm.id = lr.member_id;
```

**预期结果与业务结论。** 一行结果:`cross_theater_redemption_pct` 约 **14.6%**——不到六分之一的兑换发生在非主场影院,大部分兑换还是发生在会员日常光顾的那家影院。这个比例不算特别高,但也不可忽略。Director of Loyalty & Marketing 可以据此判断"附近影院"引导功能的潜在提升空间有限但确实存在,值得作为一个中优先级的 App 功能迭代,而不是当季度的头号项目。

---

## Query 20: 影院综合贡献排名(票房 + 卖品毛利 − 固定成本)

**业务背景。** 董事会要求 CFO 在下季度提交一份"影院层级"的综合盈利能力排名,作为未来是否新开影院、关闭影院或调整资源投入的依据。这是全季度最高层级的一份材料,把前面所有查询里拆解过的收入和成本项重新汇总回影院这个管理颗粒度。

**标签。** 类别: CTE + 窗口函数 + 多表连接 | 难度: 高级 | 角色: CFO

**解题思路。** 这是本文档里涉及数据源最多的一题,需要综合三个独立的成本/收入来源:`showtime`(票房)、`concession_sale`(卖品毛利,注意这里要用收入减成本而不是只用收入)、`screen_monthly_cost`(固定成本,需要先按 `screen_id` 关联到 `theater_id` 再汇总)。用三个 CTE 分别独立聚合到影院层级,再用三次 `JOIN` 拼接,最后组合出一个"综合贡献"指标并用 `RANK()` 排名。**这里刻意提醒一个容易踩的坑:如果直接把 `showtime` 和 `concession_sale` 做 JOIN 再聚合,会因为两张表的粒度不同(一个是场次级别,一个是影院/日期/时段/SKU 级别)造成笛卡尔积重复计算,票房金额会被夸大好几倍——正确做法必须像下面这样先分别聚合成三个独立的、以 `theater_id` 为唯一粒度的 CTE,再做 1:1 的 JOIN 拼接。**

```sql
WITH ticket_rev AS (
    SELECT t.id AS theater_id, SUM(s.ticket_revenue) AS ticket_revenue
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    GROUP BY t.id
),
concession_profit AS (
    SELECT theater_id, SUM(gross_revenue - cogs_amount) AS concession_gross_profit
    FROM concession_sale
    GROUP BY theater_id
),
fixed_cost AS (
    SELECT sc.theater_id, SUM(smc.total_cost) AS total_fixed_cost
    FROM screen sc
    JOIN screen_monthly_cost smc ON smc.screen_id = sc.id
    GROUP BY sc.theater_id
)
SELECT
    t.theater_name,
    t.market_tier,
    ROUND(tr.ticket_revenue, 0) AS ticket_revenue,
    ROUND(cp.concession_gross_profit, 0) AS concession_gross_profit,
    ROUND(fc.total_fixed_cost, 0) AS screen_fixed_cost,
    ROUND(tr.ticket_revenue + cp.concession_gross_profit - fc.total_fixed_cost, 0) AS blended_contribution,
    RANK() OVER (ORDER BY tr.ticket_revenue + cp.concession_gross_profit - fc.total_fixed_cost DESC) AS contribution_rank
FROM ticket_rev tr
JOIN theater t ON t.id = tr.theater_id
JOIN concession_profit cp ON cp.theater_id = tr.theater_id
JOIN fixed_cost fc ON fc.theater_id = tr.theater_id
ORDER BY contribution_rank;
```

**预期结果与业务结论。** 返回全部 18 家影院的排名。芝加哥 Lincoln Square 影院(公司旗舰店)排名第一,综合贡献约 **$196 万**;排名末位的几家均为 Secondary 市场影院,综合贡献在 **$37 万-$52 万** 区间。**关键的提醒是:这份影院层级的排名会把 Query 4 揭示的"3 块 IMAX 银幕持续亏损"这个问题完全掩盖掉**——因为这几家影院的整体票房规模足够大,银幕层级的小额亏损在影院总盘子里根本看不出来。CFO 在董事会材料里应该同时展示这份影院层级排名(回答"该不该关某家影院")和 Query 4 的银幕层级排名(回答"该不该续某块银幕的合同"),两者服务于不同颗粒度的决策,不能互相替代。

---

## 业务问题对应表

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 卖品真实现金毛利 | Query 1, Query 2, Query 3 |
| Q2 高端银幕单银幕盈亏 | Query 4, Query 5, Query 6, Query 10 |
| Q3 深夜场"保底票"侵蚀上座率真实性 | Query 8, Query 9 |
| Q4 银幕与影院利用率 | Query 10, Query 11, Query 20 |
| Q5 场次时段与卖品匹配 | Query 13, Query 14, Query 15, Query 17 |
| 运营类(不对应特定 marquee 问题) | Query 7, Query 12, Query 16, Query 18, Query 19 |
