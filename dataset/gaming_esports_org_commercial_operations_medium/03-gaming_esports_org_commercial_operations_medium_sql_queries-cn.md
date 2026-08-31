# Vanguard Esports 商业运营健康度复盘: SQL 查询文档

本文档覆盖 `gaming_esports_org_commercial_operations_medium` 数据集的 20 道
SQL 分析题。业务背景, 组织架构和四个核心业务问题请见
`01-gaming_esports_org_commercial_operations_medium_business_context-cn.md`;
表结构和字段含义请见
`02-gaming_esports_org_commercial_operations_medium_er_document-cn.md`。

**REFERENCE_DATE 约定**: 本数据集锚定在 `2026-06-30` 这个分析基准日。所有
查询里凡是需要"今天"的地方, 都直接写字面量日期 `'2026-06-30'`, 不使用
`DATE('now')`, 保证任何时候运行这些查询都能复现同样的结果。

## 如何使用本文档

你是 Vanguard Esports 新加入的 Commercial Operations Analyst, COO 把接下来
三周的复盘任务拆成了这 20 道题分批交给你。每道题都包含五个部分:

1. **业务背景**: 谁在问, 为什么问, 答案会用在哪个决策上。
2. **标签**: 类别 / 难度 / 提问角色三个短标签。
3. **解题思路**: 在看到 SQL 之前, 先讲清楚要连哪些表、按什么粒度聚合、
   有哪些容易踩的坑。
4. **SQL 代码**: 可以直接在数据集生成的 SQLite 数据库上运行的查询。
5. **预期结果与业务结论**: 结果长什么样, 数字对应的业务含义是什么, 以及
   分析师看到这个结果后下一步该做什么。

每道题都能追溯回业务背景文件里的 4 个业务问题(Q1 赞助曝光计费缺口, Q2 薪资
与战绩脱节, Q3 周边毛利与战绩挂钩, Q4 奖金分成支付合规性)之一, 外加几道
运营类查询打底。SQL 是用来学习的, 不只是用来跑的 —— 建议先读"解题思路"再看
代码, 自己在脑子里过一遍连表逻辑, 再对照代码验证。

## 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| 1 | 各赞助合同的曝光交付率排名 | Head of Partnerships | Aggregation + Join | Basic |
| 2 | 曝光缺口合同的年度赞助费风险敞口 | CFO | Aggregation + CASE | Intermediate |
| 3 | 按赞助范围拆分曝光交付率 | Head of Partnerships | Join + Group By | Intermediate |
| 4 | 选手近 6 个月表现 vs 历史高点 | GM of Esports | CTE + Aggregation | Advanced |
| 5 | 薪资与近期表现的错配排名 | GM of Esports | CTE + Window Function | Advanced |
| 6 | legacy star 与其余选手的薪资/表现相关性对照 | GM of Esports | Aggregation + Window Function (NTILE) | Intermediate |
| 7 | 下滑选手的合同剩余月数 | GM of Esports | Date 计算 | Basic |
| 8 | 战队近 60 天滚动胜率 vs 同期周边毛利率 | Commercial Operations Analyst | Correlated Subquery + CTE | Advanced |
| 9 | 低谷期 vs 状态期的周边营收/毛利对比 | Commercial Operations Analyst | CASE + Aggregation | Intermediate |
| 10 | 低谷期折扣力度分布 | Commercial Operations Analyst | Aggregation | Basic |
| 11 | 逾期/短付分成记录按战队汇总 | GM of Esports | Aggregation + Join | Intermediate |
| 12 | 分成到账延迟天数排名 | Player Payments Coordinator | Window Function (RANK) | Intermediate |
| 13 | 短付总金额汇总 | CFO | Aggregation | Basic |
| 14 | 赛事方打款到俱乐部收款的天数分布 | Player Payments Coordinator | Date 计算 + Aggregation | Basic |
| 15 | 各战队赛事名次分布 | GM of Esports | Aggregation | Basic |
| 16 | 直播观众规模 Top 10 场次 | Head of Content | Order By + Join | Basic |
| 17 | MVP 次数排行榜与薪资对照 | GM of Esports | Aggregation + Window Function | Intermediate |
| 18 | 周边品类营收/毛利贡献占比 | Commercial Operations Analyst | Aggregation | Basic |
| 19 | 按合同命名关键词拆分赞助价值(Global vs 战队专属) | Head of Partnerships | Pattern Matching (LIKE) | Basic |
| 20 | 董事会汇总评分卡: 四大问题一页纸 | COO | CTE 组合多个子查询 | Advanced |

---

## Query 1: 各赞助合同的曝光交付率排名

### 业务背景

Head of Partnerships 每个季度要给品牌方的续约谈判做准备, 但过去从来没有
系统性地把"合同承诺的曝光小时数"和"内容团队实测的曝光小时数"放在一起对比过。
董事会这次要求的复盘把这件事列为第一优先级: 如果有合同实际交付明显低于承诺,
续约时要么补足权益, 要么调整计费方式, 否则等品牌方自己发现就是公关危机。
这道题对应业务问题 Q1。

### 标签

类别: Aggregation + Join · 难度: Basic · 角色: Head of Partnerships

### 解题思路

需要 `sponsorship_deal` 和 `sponsor_exposure_log` 两张表, 按
`sponsorship_deal_id` 分组, 把 `measured_exposure_hours` 加总。因为合同覆盖
的自然年数不同(有的不到一年, 有的跨两年以上), 直接把加总数和
`committed_annual_exposure_hours` 相除会失真, 必须先把加总数"年化"
(除以合同在数据窗口内的有效年数), 再除以承诺值得到交付率百分比。这里用
`julianday` 计算天数再换算成年, 是 SQLite 处理日期差的标准做法。

### SQL

```sql
SELECT
    sd.deal_name,
    sd.committed_annual_exposure_hours AS committed_hours,
    ROUND(
        SUM(sel.measured_exposure_hours)
        / ((julianday(MIN(sd.contract_end_date, '2026-06-30')) - julianday(sd.contract_start_date)) / 365.25),
        1
    ) AS actual_annualized_hours,
    ROUND(
        100.0 * SUM(sel.measured_exposure_hours)
        / (sd.committed_annual_exposure_hours
           * ((julianday(MIN(sd.contract_end_date, '2026-06-30')) - julianday(sd.contract_start_date)) / 365.25)),
        1
    ) AS delivery_pct
FROM sponsorship_deal sd
JOIN sponsor_exposure_log sel ON sel.sponsorship_deal_id = sd.id
GROUP BY sd.id
ORDER BY delivery_pct;
```

### 预期结果与业务结论

结果是 12 行, 每份合同一行, 按交付率从低到高排序。最低的三份(从低到高)
—— `StreakBet Gaming Partnership`、`GridForge Fracture Protocol Hardware Deal`、
`TitanEnergy Global Partnership` —— 交付率都在约 68%-70% 区间(依次约
68.7%、69.1%、70.1%), 与其余 9 份合同(交付率约 94%-106%)形成明显断层。下一步: 把这 3 份合同标记为"续约谈判
前必须先核实"名单, 交给 Head of Partnerships 决定是补足曝光权益还是重新
定价。

---

## Query 2: 曝光缺口合同的年度赞助费风险敞口

### 业务背景

发现"哪些合同曝光不足"只是第一步, CFO 更关心的是"这件事在财务上有多大"。
如果缺口合同只占赞助总盘子的 5%, 优先级可以放低; 如果占了大头, 就需要立刻
升级到 CEO 层面。CFO 要求把 Query 1 的发现换算成美元金额, 纳入 Q3 季度
风险登记册。这道题同样对应 Q1。

### 标签

类别: Aggregation + CASE · 难度: Intermediate · 角色: CFO

### 解题思路

这里不需要重新计算交付率, 而是直接在 `sponsorship_deal` 上用 `CASE WHEN`
把 3 份已知缺口合同标记出来(交付率计算已在 Query 1 验证过, 这里为了聚焦
财务口径, 直接按合同名称枚举, 避免重复一遍复杂的年化计算), 然后按标记分组
汇总 `annual_value_usd`。这是一个典型的"先分类, 再聚合"模式: `CASE WHEN`
放在 `GROUP BY` 的分组键位置, 而不是放在 `SELECT` 的展示列里。

### SQL

```sql
SELECT
    CASE
        WHEN sd.deal_name IN (
            'TitanEnergy Global Partnership',
            'GridForge Fracture Protocol Hardware Deal',
            'StreakBet Gaming Partnership'
        ) THEN 'exposure_gap_deal'
        ELSE 'healthy_deal'
    END AS deal_health,
    COUNT(*) AS deal_count,
    SUM(sd.annual_value_usd) AS total_annual_value_usd,
    ROUND(100.0 * SUM(sd.annual_value_usd) / (SELECT SUM(annual_value_usd) FROM sponsorship_deal), 1) AS pct_of_total_sponsorship_value
FROM sponsorship_deal sd
GROUP BY deal_health;
```

### 预期结果与业务结论

结果是两行。3 份缺口合同的年度赞助费合计约 146 万美元, 占全部 12 份合同
总赞助价值的四成左右(约 42%)。这个体量不是"个别合同的小瑕疵", 而是足以
影响本季度赞助收入质量评级的问题。下一步: CFO 把这 146 万美元标记为"曝光交付风险
敞口", 写入季度风险登记册, 并要求 Head of Partnerships 在下次续约窗口前
拿出补救方案。

---

## Query 3: 按赞助范围拆分曝光交付率

### 业务背景

Head of Partnerships 想知道曝光缺口是不是"只要俱乐部整体赞助(`team_id`
为空)就容易被忽视", 还是问题也出现在战队专属合同里。这决定了整改到底该
落在内容团队的"全局曝光测量流程", 还是某支战队自己的直播运营环节。

### 标签

类别: Join + Group By · 难度: Intermediate · 角色: Head of Partnerships

### 解题思路

把 `sponsorship_deal.team_id` 是否为 NULL 作为分组维度, 用 `CASE WHEN
team_id IS NULL THEN '俱乐部整体' ELSE '战队专属' END` 分组, 对每组计算
平均交付率。这里复用 Query 1 的交付率计算逻辑(年化承诺 vs 年化实测), 包在
一层子查询里, 外层再按赞助范围分组取平均, 是"先算明细指标, 再汇总"的
两层结构。

### SQL

```sql
WITH deal_delivery AS (
    SELECT
        sd.id,
        sd.team_id,
        100.0 * SUM(sel.measured_exposure_hours)
        / (sd.committed_annual_exposure_hours
           * ((julianday(MIN(sd.contract_end_date, '2026-06-30')) - julianday(sd.contract_start_date)) / 365.25)) AS delivery_pct
    FROM sponsorship_deal sd
    JOIN sponsor_exposure_log sel ON sel.sponsorship_deal_id = sd.id
    GROUP BY sd.id
)
SELECT
    CASE WHEN team_id IS NULL THEN 'org_wide_deal' ELSE 'team_scoped_deal' END AS deal_scope,
    COUNT(*) AS deal_count,
    ROUND(AVG(delivery_pct), 1) AS avg_delivery_pct,
    ROUND(MIN(delivery_pct), 1) AS min_delivery_pct
FROM deal_delivery
GROUP BY deal_scope;
```

### 预期结果与业务结论

结果是两行。俱乐部整体赞助和战队专属赞助里都各自出现了缺口合同(`TitanEnergy
Global Partnership` 属于俱乐部整体, `GridForge` 和 `StreakBet` 属于战队
专属), 两组的最低交付率都在 68%-70% 区间, 说明问题不是某一类范围特有的, 而是
"缺乏统一的事后核对流程"这个系统性问题, 不管合同范围大小都会中招。下一步:
建议内容团队为所有赞助合同(不分范围)建立季度曝光核对机制, 而不是只加强
某一类合同的审核。

---

## Query 4: 选手近 6 个月表现 vs 历史高点

### 业务背景

GM of Esports 在准备下赛季续约预算时, 想知道"哪些选手的当前状态配不上他们
的历史身价"。仅凭教练组的主观印象容易受"这人以前很强"的光环影响, 需要用
`performance_rating` 的客观数据说话。这道题对应业务问题 Q2, 也是后面几道
薪资题的基础。

### 标签

类别: CTE + Aggregation · 难度: Advanced · 角色: GM of Esports

### 解题思路

需要两个时间窗口的平均表现评分: "近 6 个月"(`match_date >=
REFERENCE_DATE 前 6 个月`)和"历史高点窗口"(`REFERENCE_DATE 前 18 个月`
到`前 12 个月`)。用两个独立的 CTE 分别聚合这两个窗口, 再用
`roster_player_id` 把两个 CTE 连接起来, 相减算出下滑幅度。这里的坑是:
如果直接用一个 `CASE WHEN` 在同一次 `GROUP BY` 里区分两个窗口, 分母容易
搞混(两个窗口的比赛场次通常不同), 分两个 CTE 各自独立聚合再 JOIN 是更
安全的写法。

### SQL

```sql
WITH recent_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS recent_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date >= date('2026-06-30', '-6 months')
    GROUP BY pms.roster_player_id
),
peak_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS peak_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date BETWEEN date('2026-06-30', '-18 months') AND date('2026-06-30', '-12 months')
    GROUP BY pms.roster_player_id
)
SELECT
    rp.gamertag,
    t.team_name,
    ROUND(pw.peak_rating, 2) AS peak_rating,
    ROUND(rw.recent_rating, 2) AS recent_rating,
    ROUND(100.0 * (rw.recent_rating - pw.peak_rating) / pw.peak_rating, 1) AS pct_change
FROM roster_player rp
JOIN team t ON t.id = rp.team_id
JOIN recent_window rw ON rw.roster_player_id = rp.id
JOIN peak_window pw ON pw.roster_player_id = rp.id
ORDER BY pct_change
LIMIT 10;
```

### 预期结果与业务结论

结果按下滑幅度从大到小排序(`ORDER BY pct_change` 升序, 负得越多排越前)。
最靠前的 4 名选手 —— 依次是 Thornquil、Hollowmere、Zenithrax、Wraithcall
—— 近 6 个月表现评分相比历史高点下降约 30%-35%, 与榜单其余选手(下滑幅度
多在 5% 以内, 部分甚至是正增长)形成清晰断层。这里的先后只反映下滑幅度大小,
不代表薪资高低或复核优先级(四人集合本身才是结论, 具体名次会随评分噪声微调)。
下一步: 把这 4 人标记为"续约窗口重点复核对象", 交给 Query 5 进一步核对
他们的薪资是否已经因此错配。

---

## Query 5: 薪资与近期表现的错配排名

### 业务背景

Query 4 找出了"状态下滑"的选手, 但下滑本身不是问题 —— 问题是"下滑了但薪资
没跟着调整"。GM of Esports 需要一份明确的名单, 标出哪些选手的薪资已经明显
配不上近期表现, 而且合同还没到能重新谈的时候, 这样才能提前规划下赛季的
薪资预算和续约优先级。

### 标签

类别: CTE + Window Function · 难度: Advanced · 角色: GM of Esports

### 解题思路

在 Query 4 的基础上再 JOIN `player_contract`, 加入薪资和合同到期日期。
用 `RANK() OVER (ORDER BY pct_change ASC)` 给"下滑幅度"排名, 这样即使
后续有新选手数据进来, 排名会自动更新而不需要改 SQL。同时算出
`contract_end_date` 距 REFERENCE_DATE 的剩余月数, 用来判断"这个错配还要
持续多久才有机会修正"。

### SQL

```sql
WITH recent_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS recent_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date >= date('2026-06-30', '-6 months')
    GROUP BY pms.roster_player_id
),
peak_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS peak_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date BETWEEN date('2026-06-30', '-18 months') AND date('2026-06-30', '-12 months')
    GROUP BY pms.roster_player_id
)
SELECT
    rp.gamertag,
    pc.annual_salary_usd,
    ROUND(rw.recent_rating, 2) AS recent_rating,
    ROUND(100.0 * (rw.recent_rating - pw.peak_rating) / pw.peak_rating, 1) AS pct_change,
    pc.contract_end_date,
    CAST((julianday(pc.contract_end_date) - julianday('2026-06-30')) / 30 AS INTEGER) AS months_remaining,
    RANK() OVER (ORDER BY (rw.recent_rating - pw.peak_rating) / pw.peak_rating ASC) AS decline_rank
FROM roster_player rp
JOIN player_contract pc ON pc.roster_player_id = rp.id
JOIN recent_window rw ON rw.roster_player_id = rp.id
JOIN peak_window pw ON pw.roster_player_id = rp.id
ORDER BY decline_rank
LIMIT 6;
```

### 预期结果与业务结论

排名前 4 的选手(Thornquil、Hollowmere、Zenithrax、Wraithcall)年薪都在
10.5 万到 65 万美元区间的各自档位上限附近, 合同剩余都在 18 个月以上, 却是
全队下滑幅度最大的 4 人 —— 这就是"高薪低产"错配的直接证据。下一步: GM of
Esports 把这份名单纳入下赛季预算规划, 对这 4 人启动"绩效改善计划"或考虑
提前协商买断, 而不是被动等到 2028 年合同到期。

---

## Query 6: legacy star 与其余选手的薪资/表现相关性对照

### 业务背景

CFO 在董事会材料里需要说明: "薪资与战绩脱节"是个别的 4 个人的问题, 还是
整个薪资体系都有问题。如果剔除这 4 人之后, 其余选手的薪资和近期表现依然
保持合理的正相关, 说明薪资体系设计本身没问题, 只是这 4 份合同需要单独处理,
不需要推翻整个薪资框架。

### 标签

类别: Aggregation + Window Function (NTILE) · 难度: Intermediate · 角色: GM of Esports

### 解题思路

把选手按是否在"下滑名单"(4 位 legacy star, 直接用 `gamertag` 枚举, 已在
Query 4/5 里验证过身份)分成两组, 分别计算组内薪资分位数最高和最低两档
选手的平均近期表现评分, 用"高薪组表现是否明显高于低薪组"这个粗粒度对比,
代替严格的皮尔逊相关系数(SQLite 没有内置的 CORR 函数)。这是教学中常见的
变通做法: 用分组对比去逼近"相关性"这个统计学概念。

### SQL

```sql
WITH recent_rating AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS recent_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date >= date('2026-06-30', '-6 months')
    GROUP BY pms.roster_player_id
),
tagged AS (
    SELECT
        rp.gamertag,
        CASE WHEN rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
             THEN 'legacy_star' ELSE 'rest_of_roster' END AS player_group,
        pc.annual_salary_usd,
        rr.recent_rating,
        NTILE(2) OVER (PARTITION BY
            CASE WHEN rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
                 THEN 'legacy_star' ELSE 'rest_of_roster' END
            ORDER BY pc.annual_salary_usd) AS salary_half
    FROM roster_player rp
    JOIN player_contract pc ON pc.roster_player_id = rp.id
    JOIN recent_rating rr ON rr.roster_player_id = rp.id
)
SELECT
    player_group,
    salary_half,
    COUNT(*) AS player_count,
    ROUND(AVG(annual_salary_usd), 0) AS avg_salary,
    ROUND(AVG(recent_rating), 2) AS avg_recent_rating
FROM tagged
GROUP BY player_group, salary_half
ORDER BY player_group, salary_half;
```

### 预期结果与业务结论

结果是四行。`rest_of_roster` 组里, 薪资分位数higher的一半(`salary_half=2`)
平均近期表现评分明显高于薪资较低的一半 —— 薪资和表现方向一致。
`legacy_star` 组由于只有 4 人且都是高薪但近期表现不佳, 两档薪资和表现的
差异不再呈现同样的正向关系。这证明脱节问题局限在这 4 份合同, 而不是整个
薪资体系设计有缺陷。下一步: CFO 可以在董事会材料里明确说明"这是个案而非
系统性问题", 把整改范围收窄到这 4 份合同。

---

## Query 7: 下滑选手的合同剩余月数

### 业务背景

GM of Esports 需要知道: 这几位"高薪低产"的选手, 最早什么时候能重新谈判
薪资。如果剩余时间还很长, 短期内成本错配无法通过等待合同到期解决, 需要
考虑提前协商; 如果快到期了, 可以等自然续约窗口。

### 标签

类别: Date 计算 · 难度: Basic · 角色: GM of Esports

### 解题思路

直接从 `player_contract` 里取 4 位 legacy star 的 `contract_end_date`
和 `last_renegotiation_date`, 用 SQLite 的 `julianday` 函数算出距
REFERENCE_DATE 的剩余天数, 再除以 30 换算成月, 属于最基础的日期算术,
不需要窗口函数或子查询。

### SQL

```sql
SELECT
    rp.gamertag,
    pc.last_renegotiation_date,
    pc.contract_end_date,
    CAST((julianday(pc.contract_end_date) - julianday('2026-06-30')) / 30 AS INTEGER) AS months_remaining
FROM roster_player rp
JOIN player_contract pc ON pc.roster_player_id = rp.id
WHERE rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
ORDER BY months_remaining;
```

### 预期结果与业务结论

4 行结果, 剩余月数都在 18 到 23 个月之间, 且上一次续约日期都落在
2025 年 9 月到 12 月之间(也就是他们表现开始明显下滑的前后)。这说明俱乐部
在下滑刚开始、数据还不够明显时就把这几份合同续成了长约, 属于典型的"续约
时机踩在信号最模糊的窗口"。下一步: 由于合同剩余时间都在 18 个月以上, 自然
到期还很久, GM of Esports 应该在本季度就启动提前协商或绩效条款补充, 而
不是被动等待。

---

## Query 8: 战队近 60 天滚动胜率 vs 同期周边毛利率

### 业务背景

Commercial Operations Analyst(也就是你自己)需要验证一个假设: 周边商品
的毛利率是不是真的随战队近期战绩起伏。如果这个关联成立, 财务部门就不能
只看"周边总营收"这一个数字来判断周边业务是否健康 —— 营收平稳的表象下,
毛利可能已经在低谷期被显著侵蚀。这道题对应业务问题 Q3, 是本次复盘里技术
含量最高的一道题。

### 标签

类别: Correlated Subquery + CTE · 难度: Advanced · 角色: Commercial Operations Analyst

### 解题思路

每一笔 `merch_sale` 都要知道"这笔销售发生时, 对应战队过去 60 天的胜率是
多少"。这不能用简单的 `GROUP BY` 完成, 因为"过去 60 天"是相对每一笔销售
的销售日期动态计算的窗口, 必须用一个相关子查询(correlated subquery):
对每一行 `merch_sale`, 子查询回头看 `match_result` 里同一个 `team_id`、
`match_date` 落在 `[销售日期-60天, 销售日期]` 区间内的比赛, 算出胜率。
只处理 `merch_sku.team_id` 非空的战队专属商品(俱乐部整体商品没有单一
战队可归因)。算出胜率后再按"状态期(>=0.55)/中间态/低谷期(<0.35)"分桶,
对比每桶的毛利率。这类相关子查询在小数据集上可以接受, 但要提醒读者:
如果数据量到百万级, 应该改写成预先计算好的"胜率时间序列表"再 JOIN,
而不是逐行相关子查询。

### SQL

```sql
WITH sale_context AS (
    SELECT
        ms.id AS sale_id,
        ms.quantity,
        ms.unit_price_paid_usd,
        msk.unit_cost_usd,
        (
            SELECT CAST(SUM(CASE WHEN mr.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
            FROM match_result mr
            WHERE mr.team_id = msk.team_id
              AND mr.match_date BETWEEN date(ms.sale_date, '-60 days') AND ms.sale_date
        ) AS trailing_winrate
    FROM merch_sale ms
    JOIN merch_sku msk ON msk.id = ms.merch_sku_id
    WHERE msk.team_id IS NOT NULL
)
SELECT
    CASE
        WHEN trailing_winrate >= 0.55 THEN 'hot_form'
        WHEN trailing_winrate < 0.35 THEN 'slump_form'
        ELSE 'mid_form'
    END AS team_form_bucket,
    COUNT(*) AS sale_count,
    ROUND(AVG(trailing_winrate), 2) AS avg_trailing_winrate,
    ROUND(SUM(quantity * unit_price_paid_usd), 0) AS total_revenue_usd,
    ROUND(SUM(quantity * unit_price_paid_usd) / COUNT(*), 1) AS avg_revenue_per_sale_usd,
    ROUND(100.0 * SUM(quantity * (unit_price_paid_usd - unit_cost_usd)) / SUM(quantity * unit_price_paid_usd), 1) AS gross_margin_pct
FROM sale_context
WHERE trailing_winrate IS NOT NULL
GROUP BY team_form_bucket
ORDER BY avg_trailing_winrate;
```

### 预期结果与业务结论

结果是三行(低谷/中间/状态期各一行)。状态期毛利率约 50.5%, 低谷期毛利率
跌到约 37%, 差距约 13.5 个百分点; 但看"每笔销售的平均金额"这一列,
状态期约 164 美元, 低谷期约 146 美元, 只低了约 11%。也就是说, 战队低谷期
靠加大折扣硬撑住了销量和总营收的表象, 但每笔交易的赚钱能力被大幅压缩。
下一步: 建议财务报表在"周边营收"旁边并列展示"周边毛利率", 并按战队近期
战绩状态分桶追踪, 而不是只看营收同比。

---

## Query 9: 低谷期 vs 状态期的周边营收/毛利对比(按战队)

### 业务背景

COO 想在董事会材料里用一张按战队拆开的表格, 直观展示"哪支战队的周边业务
对战绩最敏感"。Query 8 证明了整体关联存在, 这道题把它拆到战队粒度, 帮助
COO 判断是不是某一支战队(比如观众基数更小的 Vanguard Academy)对战绩波动
格外敏感, 需要单独的库存和定价策略。

### 标签

类别: CASE + Aggregation · 难度: Intermediate · 角色: COO

### 解题思路

复用 Query 8 的"相关子查询算滚动胜率"逻辑, 但这次按 `team_id` 和"状态桶"
两个维度一起分组, 而不是只按状态桶分组。这样每支战队都会拆出"低谷期"和
"非低谷期"两行, 方便按行对比。

### SQL

```sql
WITH sale_context AS (
    SELECT
        msk.team_id,
        ms.quantity,
        ms.unit_price_paid_usd,
        msk.unit_cost_usd,
        (
            SELECT CAST(SUM(CASE WHEN mr.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
            FROM match_result mr
            WHERE mr.team_id = msk.team_id
              AND mr.match_date BETWEEN date(ms.sale_date, '-60 days') AND ms.sale_date
        ) AS trailing_winrate
    FROM merch_sale ms
    JOIN merch_sku msk ON msk.id = ms.merch_sku_id
    WHERE msk.team_id IS NOT NULL
)
SELECT
    t.team_name,
    CASE WHEN trailing_winrate < 0.35 THEN 'slump_form' ELSE 'non_slump_form' END AS form_bucket,
    COUNT(*) AS sale_count,
    ROUND(SUM(quantity * unit_price_paid_usd), 0) AS total_revenue_usd,
    ROUND(100.0 * SUM(quantity * (unit_price_paid_usd - unit_cost_usd)) / SUM(quantity * unit_price_paid_usd), 1) AS gross_margin_pct
FROM sale_context sc
JOIN team t ON t.id = sc.team_id
WHERE trailing_winrate IS NOT NULL
GROUP BY t.team_name, form_bucket
ORDER BY t.team_name, form_bucket;
```

### 预期结果与业务结论

结果是 6 行(3 支战队各拆两桶)。三支战队在低谷期的毛利率都比非低谷期低
10 个百分点以上, 说明这不是某一支战队特有的现象, 而是整个俱乐部周边定价
策略("低谷期就打折清库存")的通病。下一步: COO 可以要求所有 3 支战队
统一采用"低谷期限制折扣上限"的库存策略, 而不是让各战队各自为战。

---

## Query 10: 低谷期折扣力度分布

### 业务背景

在向管理层提出"限制低谷期折扣上限"之前, Commercial Operations Analyst
需要先弄清楚现在低谷期的折扣力度到底有多离谱, 才能提出一个具体、可执行
的上限建议(而不是空泛地说"折扣太多了")。

### 标签

类别: Aggregation · 难度: Basic · 角色: Commercial Operations Analyst

### 解题思路

这道题不需要相关子查询, 直接对 `merch_sale.discount_pct` 做基础的分布
统计(平均值, 最小值, 最大值), 按折扣力度是否超过 25% 分两组, 是本文档
里最简单的一道聚合查询, 适合作为"低谷期问题"系列的收尾, 承上启下引出
Query 11 开始的奖金支付主题。

### SQL

```sql
SELECT
    CASE WHEN discount_pct > 25 THEN 'heavy_discount' ELSE 'normal_discount' END AS discount_tier,
    COUNT(*) AS sale_count,
    ROUND(AVG(discount_pct), 1) AS avg_discount_pct,
    ROUND(MIN(discount_pct), 1) AS min_discount_pct,
    ROUND(MAX(discount_pct), 1) AS max_discount_pct
FROM merch_sale
GROUP BY discount_tier;
```

### 预期结果与业务结论

结果是两行。"重折扣"组(超过 25%)的平均折扣力度约 30%, 最高逼近 45%,
这个量级已经接近腰斩官方标价。下一步: 建议把折扣上限政策定在 25%,
超过这个线的促销活动需要商品部门和财务共同审批, 而不是门店/线上运营
自行决定。

---

## Query 11: 逾期/短付分成记录按战队汇总

### 业务背景

General Manager of Esports 收到的两封经纪公司投诉邮件都没有点名具体是哪支
战队的选手。在正式回复经纪公司之前, 需要先内部核实问题到底出在哪个环节,
避免把锅错误地扣在某支无辜战队头上, 也避免遗漏真正的问题战队。这道题
对应业务问题 Q4。

### 标签

类别: Aggregation + Join · 难度: Intermediate · 角色: GM of Esports

### 解题思路

把 `player_prize_distribution` 通过 `prize_pool_payout` JOIN 到 `team`,
按战队分组统计总分成记录数, 以及 `payment_status` 不等于 `on_time` 的
记录数和占比。这里要注意: `player_prize_distribution` 本身没有
`team_id`, 必须先经过 `prize_pool_payout` 这张中间表才能拿到战队信息,
漏掉这层 JOIN 会直接报错。

### SQL

```sql
SELECT
    t.team_name,
    COUNT(*) AS total_distributions,
    SUM(CASE WHEN ppd.payment_status != 'on_time' THEN 1 ELSE 0 END) AS problem_count,
    ROUND(100.0 * SUM(CASE WHEN ppd.payment_status != 'on_time' THEN 1 ELSE 0 END) / COUNT(*), 1) AS problem_pct
FROM player_prize_distribution ppd
JOIN prize_pool_payout ppo ON ppo.id = ppd.prize_pool_payout_id
JOIN team t ON t.id = ppo.team_id
GROUP BY t.team_name
ORDER BY problem_pct DESC;
```

### 预期结果与业务结论

结果是三行。`Vanguard Academy` 的问题记录占比约 40%, 远高于
`Vanguard Fracture`(约 7.5%)和 `Vanguard Aetherlane`(约 2.5%)。这说明两封
经纪公司投诉大概率都和 Vanguard Academy 的选手有关, 问题高度集中在一支
战队, 而不是全俱乐部普遍现象。下一步: GM of Esports 优先约谈
Vanguard Academy 的 Player Payments Coordinator, 排查这支战队奖金分成流程的
具体环节。

---

## Query 12: 分成到账延迟天数排名

### 业务背景

找到"哪支战队"有问题之后, Player Payments Coordinator(负责奖金分成
实际操作的岗位, 向 GM of Esports 汇报)需要一份具体到"哪一笔、迟了多少天"
的清单, 才能逐笔核实是流程问题还是个别经手人的失误。

### 标签

类别: Window Function (RANK) · 难度: Intermediate · 角色: Player Payments Coordinator

### 解题思路

用 `julianday(paid_date) - julianday(due_date)` 算出每笔分成记录的
延迟天数(负数代表提前支付), 再用 `RANK() OVER (ORDER BY ... DESC)`
按延迟天数从大到小排名。用窗口函数而不是 `ORDER BY` 加 `LIMIT` 的原因是:
排名结果本身(第几名)在后续和其他清单交叉核对时也有用, 直接把名次留在
结果里比只看行顺序更清楚。

### SQL

```sql
SELECT
    rp.gamertag,
    t.team_name,
    ppd.contracted_amount_usd,
    ppd.actual_paid_amount_usd,
    CAST(julianday(ppd.paid_date) - julianday(ppd.due_date) AS INTEGER) AS days_late,
    RANK() OVER (ORDER BY julianday(ppd.paid_date) - julianday(ppd.due_date) DESC) AS lateness_rank
FROM player_prize_distribution ppd
JOIN roster_player rp ON rp.id = ppd.roster_player_id
JOIN prize_pool_payout ppo ON ppo.id = ppd.prize_pool_payout_id
JOIN team t ON t.id = ppo.team_id
ORDER BY lateness_rank
LIMIT 10;
```

### 预期结果与业务结论

结果的前几名延迟天数都在 50 天以上(合同约定的付款期限是 30 天), 且
`team_name` 列里 `Vanguard Academy` 反复出现, 与 Query 11 的结论互相
印证。下一步: 把这份清单里延迟超过 45 天的记录逐笔核实付款凭证, 判断
是系统流程延迟还是人为疏漏, 并优先补偿这批选手。

---

## Query 13: 短付总金额汇总

### 业务背景

除了"迟到"之外, 还有一部分记录是"金额不对"(`underpaid` 或
`late_and_underpaid`)。CFO 需要知道总共欠选手多少钱, 才能在本季度的
财务预提里留出这笔"应付未付"的准备金, 避免下季度突然冒出一笔意外支出。

### 标签

类别: Aggregation · 难度: Basic · 角色: CFO

### 解题思路

直接筛选 `payment_status` 里带 `underpaid` 的两种状态(`underpaid` 和
`late_and_underpaid`), 把每笔记录的"合同应得金额减实付金额"加总, 就是
总共欠付的金额。这是一道单表聚合, 不需要 JOIN 就能回答, 因为
`player_prize_distribution` 本身已经同时存了应得和实付两个金额字段。

### SQL

```sql
SELECT
    COUNT(*) AS underpaid_record_count,
    ROUND(SUM(contracted_amount_usd - actual_paid_amount_usd), 2) AS total_shortfall_usd
FROM player_prize_distribution
WHERE payment_status IN ('underpaid', 'late_and_underpaid');
```

### 预期结果与业务结论

结果是一行, 短付记录约 10-12 笔, 总欠付金额约 5,000-5,200 美元。虽然
绝对金额不大(奖金池本身规模有限), 但这笔钱如果不主动补上, 一旦被经纪
公司发现"合同写的和实付的对不上", 造成的信任损失会远超这几千美元本身。
下一步: CFO 批准这笔金额作为"选手奖金分成补偿准备金", 要求财务在两周内
补齐差额。

---

## Query 14: 赛事方打款到俱乐部收款的天数分布

### 业务背景

在把责任完全归咎于俱乐部内部流程之前, Player Payments Coordinator 想
先排除一种可能: 是不是赛事主办方自己打款就慢, 拖累了整条链路, 俱乐部
只是"背锅"。这道题单独看链路的第一环(赛事方到俱乐部), 和后面选手环节
分开衡量。

### 标签

类别: Date 计算 + Aggregation · 难度: Basic · 角色: Player Payments Coordinator

### 解题思路

`prize_pool_payout` 表里同时有 `organizer_payout_date`(赛事方发起打款)
和 `org_received_date`(俱乐部实际收到), 两者相减就是这一段链路的天数。
按 `tier`(赛事级别)分组看是否某个级别的赛事本身打款就慢。

### SQL

```sql
SELECT
    t.tier,
    COUNT(*) AS payout_count,
    ROUND(AVG(julianday(ppo.org_received_date) - julianday(ppo.organizer_payout_date)), 1) AS avg_days_to_receive
FROM prize_pool_payout ppo
JOIN tournament t ON t.id = ppo.tournament_id
GROUP BY t.tier
ORDER BY avg_days_to_receive DESC;
```

### 预期结果与业务结论

三个赛事级别(S/A/B)的平均到账天数都在 2 到 12 天之间, 相互之间差距不大,
且都远小于 Query 12 里看到的 45 天以上的选手环节延迟。这说明问题不在
"赛事方打款慢", 而是出在俱乐部收到钱之后、转付给选手之前的这一段内部
流程。下一步: 把整改重点明确锁定在俱乐部内部的分成支付环节, 不需要
向赛事主办方施压。

---

## Query 15: 各战队赛事名次分布

### 业务背景

GM of Esports 需要一份基础的赛事战绩总览, 作为董事会材料的开场背景页 ——
在讨论"薪资是否合理"之前, 先让董事会成员对三支战队各自的竞技表现有个
直观概念。这是一道运营类打底查询, 不直接对应某个陷阱, 但为后续分析
提供背景。

### 标签

类别: Aggregation · 难度: Basic · 角色: GM of Esports

### 解题思路

`prize_pool_payout.placement` 字段记录了每次参赛的最终名次, 按战队分组
统计夺冠(第 1 名)、冠亚军、前四和未进四强各自出现的次数, 是最基础的
分组计数。注意 24 场赛事里有 1 场小组赛出局颗粒无收, 没有生成
`prize_pool_payout` 行, 所以三支战队的 `total_tournaments` 加总是 23,
不是 24。

### SQL

```sql
SELECT
    t.team_name,
    SUM(CASE WHEN ppo.placement = 1 THEN 1 ELSE 0 END) AS champion_finishes,
    SUM(CASE WHEN ppo.placement <= 2 THEN 1 ELSE 0 END) AS top2_finishes,
    SUM(CASE WHEN ppo.placement BETWEEN 3 AND 4 THEN 1 ELSE 0 END) AS top4_finishes,
    SUM(CASE WHEN ppo.placement > 4 THEN 1 ELSE 0 END) AS below_top4_finishes,
    COUNT(*) AS total_tournaments
FROM prize_pool_payout ppo
JOIN team t ON t.id = ppo.team_id
GROUP BY t.team_name
ORDER BY champion_finishes DESC;
```

### 预期结果与业务结论

三行结果里, `Vanguard Fracture` 的夺冠(第 1 名)次数最多, 与业务背景文件里
"2026 年打进季后赛, 是近三年最好战绩"的叙事一致。下一步: 把这张表作为
董事会材料的第一页背景图, 再引出后续"战绩变好但利润率下滑"的核心矛盾。

---

## Query 16: 直播观众规模 Top 10 场次

### 业务背景

Head of Content 想知道过去两个赛季里, 哪些场次的直播观众规模最大, 用来
向赞助商证明"我们的内容确实有流量价值", 也为下一轮赞助定价谈判提供
筹码。

### 标签

类别: Order By + Join · 难度: Basic · 角色: Head of Content

### 解题思路

直接对 `broadcast_session.peak_viewers` 排序取前 10, 附带 JOIN
`match_result` 拿到赛事阶段信息(注意 `match_result_id` 可能为 NULL,
需要用 `LEFT JOIN` 而不是 `JOIN`, 否则非比赛类内容直播会被意外排除,
虽然峰值观众高的场次通常都是比赛直播, 但写 `LEFT JOIN` 是更稳妥的
习惯)。

### SQL

```sql
SELECT
    t.team_name,
    bs.broadcast_date,
    mr.stage,
    bs.average_viewers,
    bs.peak_viewers
FROM broadcast_session bs
JOIN team t ON t.id = bs.team_id
LEFT JOIN match_result mr ON mr.id = bs.match_result_id
ORDER BY bs.peak_viewers DESC
LIMIT 10;
```

### 预期结果与业务结论

Top 10 场次几乎全部集中在 `playoffs` 或 `grand_final` 阶段, 峰值观众
在 8 万到 12 万区间, 且大多来自 `Vanguard Fracture` 和
`Vanguard Aetherlane` 两支一线队。下一步: Head of Content 把这份榜单作为
"季后赛档期溢价"的证据, 建议赞助合同按赛事阶段分层定价, 而不是全年
均一价。

---

## Query 17: MVP 次数排行榜与薪资对照

### 业务背景

GM of Esports 想快速核实: MVP 次数最多的选手, 薪资是不是也匹配得上他们
的高光频率。这是对 Query 4/5"下滑名单"的交叉验证 —— 如果一个人 MVP
次数很高但薪资偏低, 可能是被低估的续约机会; 反过来如果 MVP 次数低但
薪资很高, 又是一次"高薪低产"信号的复核。

### 标签

类别: Aggregation + Window Function · 难度: Intermediate · 角色: GM of Esports

### 解题思路

按 `roster_player_id` 统计 `was_mvp = true` 的次数, JOIN 薪资信息, 用
`RANK()` 按 MVP 次数排名, 一次查询同时回答"排名"和"薪资对照"两个问题。

### SQL

```sql
SELECT
    rp.gamertag,
    pc.annual_salary_usd,
    COUNT(*) AS mvp_count,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS mvp_rank
FROM player_match_stat pms
JOIN roster_player rp ON rp.id = pms.roster_player_id
JOIN player_contract pc ON pc.roster_player_id = rp.id
WHERE pms.was_mvp = 1
GROUP BY rp.gamertag
ORDER BY mvp_rank
LIMIT 10;
```

### 预期结果与业务结论

MVP 次数最多的几位选手里既有 Thornquil、Zenithrax、Hollowmere 这样的
"下滑名单"常客(说明他们历史高光时刻确实不少, 薪资定价当初有依据), 也有
Graniteshade 这样年薪不到 10 万美元、MVP 次数却和 Zenithrax(年薪超 60 万
美元)并列第 3 的选手, 是被低估的续约优先候选人。下一步: GM of Esports
把这份"MVP 多但薪资不高"的子名单单独列出来, 作为下赛季优先加薪续约的对象。

---

## Query 18: 周边品类营收/毛利贡献占比

### 业务背景

Commercial Operations Analyst 需要在复盘材料里说明"周边生意到底靠什么
品类赚钱", 帮助商品团队决定下赛季的选品和备货重点, 而不是眉毛胡子一把抓
地补货。

### 标签

类别: Aggregation · 难度: Basic · 角色: Commercial Operations Analyst

### 解题思路

按 `merch_sku.category` 分组, 汇总销售额和毛利率, 是一道标准的"品类
贡献度"聚合查询, 不涉及跨表复杂逻辑。

### SQL

```sql
SELECT
    msk.category,
    COUNT(*) AS sale_count,
    ROUND(SUM(ms.quantity * ms.unit_price_paid_usd), 0) AS total_revenue_usd,
    ROUND(100.0 * SUM(ms.quantity * (ms.unit_price_paid_usd - msk.unit_cost_usd)) / SUM(ms.quantity * ms.unit_price_paid_usd), 1) AS gross_margin_pct
FROM merch_sale ms
JOIN merch_sku msk ON msk.id = ms.merch_sku_id
GROUP BY msk.category
ORDER BY total_revenue_usd DESC;
```

### 预期结果与业务结论

`jersey`(球衣)品类营收占比最高, 超过其余三个品类总和, 四个品类的毛利率
都集中在 44%-47% 区间, 差异不大。下一步: 商品团队应把下赛季的库存和
营销预算继续向球衣品类倾斜, 同时用 Query 8/9/10 的发现约束所有品类的
促销折扣上限。

---

## Query 19: 按合同命名关键词拆分赞助价值(Global vs 战队专属)

### 业务背景

Head of Partnerships 想快速摸底: 命名里带"Global"字样的俱乐部整体级
合同, 平均价值是不是明显高于战队专属合同。如果是, 说明"把更多品牌方
从战队专属升级为俱乐部整体赞助"是一个值得主推的商务方向。

### 标签

类别: Pattern Matching (LIKE) · 难度: Basic · 角色: Head of Partnerships

### 解题思路

用 `LIKE '%Global%'` 匹配合同名称里的关键词, 把 12 份合同分成两组, 分别
统计平均年度赞助费。这是本文档里唯一一道用 `LIKE` 做文本匹配的题目,
提醒读者: 用命名规范里的关键词做分类, 前提是命名规范本身足够一致(本
数据集里俱乐部整体合同统一在名称里带"Global", 这是有意为之的商务
命名惯例, 不是巧合)。

### SQL

```sql
SELECT
    CASE WHEN sd.deal_name LIKE '%Global%' THEN 'org_wide_global_deal' ELSE 'team_scoped_deal' END AS deal_naming_pattern,
    COUNT(*) AS deal_count,
    ROUND(AVG(sd.annual_value_usd), 0) AS avg_annual_value_usd
FROM sponsorship_deal sd
GROUP BY deal_naming_pattern;
```

### 预期结果与业务结论

结果是两行。名称带"Global"的俱乐部整体合同平均年度价值约 42 万美元,
战队专属合同平均约 19.4 万美元, 前者接近后者的两倍多。下一步:
Head of Partnerships 在下一轮商务谈判里, 优先向现有战队专属赞助商
推销"升级为俱乐部整体赞助"的方案, 作为提升赞助总盘子的一个明确杠杆。

---

## Query 20: 董事会汇总评分卡: 四大问题一页纸

### 业务背景

COO 需要在 7 月董事会上, 用一页纸把四个业务问题的核心数字全部摆出来,
而不是让董事会成员翻 19 张不同的表。这是整份复盘的收尾查询, 把前面
分别验证过的四个陷阱各自的关键数字汇总成一行。

### 标签

类别: CTE 组合多个子查询 · 难度: Advanced · 角色: COO

### 解题思路

四个业务问题分别对应四个独立的 CTE, 每个 CTE 只返回一行汇总数字(赞助
曝光缺口合同数和风险敞口金额, 薪资脱节选手数和涉及薪资总额, 周边毛利
缺口百分点, 分成问题记录数和短付总金额)。因为每个 CTE 都只有一行,
可以直接用逗号分隔的隐式 `CROSS JOIN` 把四个单行结果拼成一行, 不需要
显式的 JOIN ON 条件 —— 这是"多个独立单行汇总拼成一张仪表盘"场景下的
一个实用技巧, 但只在每个 CTE 确定只返回一行时才安全, 否则会出现意外的
笛卡尔积膨胀。`merch_margin_gap` 这个 CTE 复用了 Query 8 里"按战队近 60 天
滚动胜率分桶"的相关子查询写法, 现算状态期和低谷期的毛利率再相减, 而不是
抄一个写死的数字 —— 这样即使以后重新生成数据、校准常量发生变化, 这一列
也会自动跟着数据走, 不会悄悄过期。

### SQL

```sql
WITH sponsor_exposure_gap AS (
    SELECT
        COUNT(*) AS n_rigged_deals,
        SUM(annual_value_usd) AS value_at_risk_usd
    FROM sponsorship_deal
    WHERE deal_name IN ('TitanEnergy Global Partnership', 'GridForge Fracture Protocol Hardware Deal', 'StreakBet Gaming Partnership')
),
salary_performance_gap AS (
    SELECT
        COUNT(*) AS n_legacy_stars,
        SUM(pc.annual_salary_usd) AS salary_at_risk_usd
    FROM roster_player rp
    JOIN player_contract pc ON pc.roster_player_id = rp.id
    WHERE rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
),
merch_sale_context AS (
    SELECT
        ms.quantity,
        ms.unit_price_paid_usd,
        msk.unit_cost_usd,
        (
            SELECT CAST(SUM(CASE WHEN mr.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
            FROM match_result mr
            WHERE mr.team_id = msk.team_id
              AND mr.match_date BETWEEN date(ms.sale_date, '-60 days') AND ms.sale_date
        ) AS trailing_winrate
    FROM merch_sale ms
    JOIN merch_sku msk ON msk.id = ms.merch_sku_id
    WHERE msk.team_id IS NOT NULL
),
merch_margin_gap AS (
    SELECT
        ROUND(
            100.0 * SUM(CASE WHEN trailing_winrate >= 0.55 THEN quantity * (unit_price_paid_usd - unit_cost_usd) END)
                / NULLIF(SUM(CASE WHEN trailing_winrate >= 0.55 THEN quantity * unit_price_paid_usd END), 0)
            - 100.0 * SUM(CASE WHEN trailing_winrate < 0.35 THEN quantity * (unit_price_paid_usd - unit_cost_usd) END)
                / NULLIF(SUM(CASE WHEN trailing_winrate < 0.35 THEN quantity * unit_price_paid_usd END), 0),
            1
        ) AS margin_gap_pp
    FROM merch_sale_context
),
prize_payment_gap AS (
    SELECT
        COUNT(*) AS n_late_or_underpaid,
        ROUND(SUM(contracted_amount_usd - actual_paid_amount_usd), 2) AS shortfall_usd
    FROM player_prize_distribution
    WHERE payment_status != 'on_time'
)
SELECT * FROM sponsor_exposure_gap, salary_performance_gap, merch_margin_gap, prize_payment_gap;
```

### 预期结果与业务结论

结果是一行八列: 3 份缺口合同/约 146 万美元风险敞口, 4 名薪资脱节选手/
约 204.7 万美元涉及薪资, 周边毛利缺口约 13.5 个百分点, 18 条分成问题
记录/约 5,085 美元短付金额。下一步: COO 把这一行数字直接放进董事会
PPT 的第一页, 四个问题各配一张明细图(分别取自 Query 1, 5, 8, 11 的
结果), 作为整份复盘材料的执行摘要。

---

## 业务问题与查询映射

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 赞助商曝光计费缺口 | Query 1, 2, 3, 19, 20 |
| Q2 薪资与战绩脱节 | Query 4, 5, 6, 7, 17, 20 |
| Q3 周边毛利与战绩挂钩 | Query 8, 9, 10, 18, 20 |
| Q4 奖金分成支付合规性 | Query 11, 12, 13, 14, 20 |
| 运营背景(不直接对应某个陷阱) | Query 15, 16 |
