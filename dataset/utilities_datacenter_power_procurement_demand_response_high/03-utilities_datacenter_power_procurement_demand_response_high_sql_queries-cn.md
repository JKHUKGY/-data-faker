# Kestrel Compute 电力数据集 SQL 查询集

本文档覆盖 `utilities_datacenter_power_procurement_demand_response_high` 数据集. 公司背景, 行业科普与术语表在 `01-utilities_datacenter_power_procurement_demand_response_high_business_context-cn.md`, 表结构与字段含义在 `02-utilities_datacenter_power_procurement_demand_response_high_er_document-cn.md`. 建议按顺序读完那两份再来看这里.

数据集锚定在一个固定的参考日 `REFERENCE_DATE = 2026-06-30`, 它同时是 Kestrel FY2026 财年的最后一天. 所有查询里凡是需要 "今天" 或者财年边界的地方, 都直接写成字面量日期字符串, 不用 `DATE('now')`. 这样无论什么时候跑, 结果都一样.

---

## 1. 如何使用本文档

这二十道查询是 VP of Energy Strategy Dana Whitfield 交给你的第一批活. 交付物是九月董事会那份 FY2027 能源预算复核备忘录, 这些查询就是备忘录里每一个结论的证据链.

每道查询都有五个部分. **业务背景** 说明谁在问, 为什么现在问, 答案要用来做什么决定. **标签** 标出 SQL 类别, 难度和对应岗位. **解题思路** 在你看到 SQL 之前先把思路走一遍, 讲清楚要碰哪几张表, join 的结构有什么坑, 聚合的粒度是什么, 为什么这里需要 CTE 或窗口函数. **SQL** 是可以直接跑的代码. **预期结果与业务结论** 给出结果的形状和真实量级, 并且说明拿到这个数字之后下一步该做什么.

最后一部分才是重点. 跑出数字不是分析的终点, 是起点. 每道题的结论里都写了下一个动作, 那个动作才是这份工作真正的产出.

二十道题里有几道是成对出现的. 一道给出 "所有人一直以来相信的那个数字", 紧接着一道给出 "把被忽略的成本算进来之后的真实数字". Q4 与 Q5 是一对, Q9 与 Q10 是一对. 这种成对结构不是为了炫技, 它复现的是真实工作里最常见的一幕: 一个长期被引用的指标, 口径本身是错的.

---

## 2. 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
| :-- | :--- | :--- | :--- | :--- |
| Q1 | 六座园区 FY2026 电费总览 | CFO Helen Okafor | 聚合 + 外连接 | 基础 |
| Q2 | 账单结构拆解, 钱到底花在哪一项 | CFO Helen Okafor | 聚合 + 窗口函数 | 基础 |
| Q3 | 需求响应项目注册与承诺容量 | Demand Response Manager Priya Raghavan | 连接 + 聚合 | 基础 |
| Q4 | 需求响应结算收入排行 | Demand Response Manager Priya Raghavan | 多表连接 + 聚合 | 中级 |
| Q5 | 需求响应的真实净收益 | VP of Energy Strategy Dana Whitfield | CTE + 多表连接 | 高级 |
| Q6 | 哪些园区的哪些事件在亏钱 | VP of Energy Strategy Dana Whitfield | CTE + 相关子查询 | 中级 |
| Q7 | 基线灌水嫌疑事件筛查 | Demand Response Manager Priya Raghavan | 连接 + 比值过滤 | 中级 |
| Q8 | 用干净基线重算, 虚增了多少 | VP of Energy Strategy Dana Whitfield | 多层 CTE | 高级 |
| Q9 | 风电 PPA 月度对比市场均价 | Power Procurement Manager Marcus Ellery | CTE + 聚合 | 基础 |
| Q10 | 按出力加权的 PPA 真实价差 | Power Procurement Manager Marcus Ellery | CTE + 加权聚合 | 高级 |
| Q11 | 风电出力越大, 电价越低吗 | Energy Data Analyst | CASE 分档 + 窗口函数 | 中级 |
| Q12 | 每月计费需量峰值区间定位 | Energy Data Analyst | 窗口函数 RANK | 中级 |
| Q13 | 那次 burn-in 测试值多少钱 | Director of Data Center Operations Tom Brennan | 多层 CTE + 反事实 | 高级 |
| Q14 | 4CP 预测复盘 | Grid Operations Specialist Luis Ferrer | 日期计算 + 区间判定 | 中级 |
| Q15 | 4CP 失手的财务代价 | CFO Helen Okafor | CTE + 反事实 | 中级 |
| Q16 | 电价尖峰时我们在干什么 | Energy Data Analyst | 窗口函数 LAG + 分档 | 中级 |
| Q17 | 湿球温度与冷却负载 | Energy Data Analyst | 时间对齐连接 + 分档 | 中级 |
| Q18 | 三类供应合约的评估口径 | Power Procurement Manager Marcus Ellery | 聚合 + 分类 | 基础 |
| Q19 | SLA 赔付敞口最大的客户 | COO Rafael Duarte | 聚合 + HAVING | 基础 |
| Q20 | 削减决策由谁做, 做得对吗 | VP of Energy Strategy Dana Whitfield | 文本匹配 + 聚合 | 中级 |

---

## 3. Q1 六座园区 FY2026 电费总览

### 业务背景

CFO Helen Okafor 在准备董事会材料时提了一个很朴素的要求: 先给我一张表, 六座园区各花了多少电费, 用了多少电, 单价是多少. 她想先看清楚基本盘, 再决定往哪个方向追问.

这个要求看着简单, 但有一个具体的动机. FY2026 全公司电费 2.05 亿美元, 比 FY2025 涨了不少, 而管理层内部对涨价原因有两种说法: 一种说是市场电价上涨, 一种说是新园区投产带来的自然增长. 这张表要能把两种说法区分开.

答案会决定 FY2027 预算按什么口径编: 如果单价差异是主因, 预算应该按园区分别编; 如果是总量增长, 按公司整体编即可.

### 标签

聚合 + 外连接 / 基础 / CFO

### 解题思路

只需要 `site`, `iso_market` 和 `energy_invoice` 三张表. 关键在于用 `LEFT JOIN` 而不是 `INNER JOIN` 连账单: New Albany East 园区在 2025 年 9 月才投产, 如果哪天它某个月没出账单, `INNER JOIN` 会直接把这座园区整行丢掉, 而我们恰恰需要看到它只有 10 个月账单这件事. 把 `COUNT(i.id)` 也选出来, 就是为了让这个差异显式地出现在结果里.

聚合的粒度是一座园区一行. 混合单价不要用 `AVG(i.blended_rate_usd_per_kwh)`, 那是对十二个月度单价做简单平均, 每个月的权重一样, 但实际上各月用电量差很多. 正确做法是先把金额和电量分别求和, 再相除, 也就是用电量加权. 这两种算法在 ALB1 上差了将近 5%.

不需要 CTE 也不需要窗口函数, 一次 `GROUP BY` 就够.

### SQL

```sql
SELECT
    s.site_code,
    s.site_name,
    m.code AS iso,
    s.contracted_capacity_mw,
    COUNT(i.id) AS invoice_months,
    ROUND(SUM(i.total_energy_mwh), 0) AS total_mwh,
    ROUND(SUM(i.total_amount_usd), 0) AS total_usd,
    -- 先求和再相除, 等价于按用电量加权. 直接 AVG(blended_rate) 会给小月份过高权重
    ROUND(SUM(i.total_amount_usd) / (SUM(i.total_energy_mwh) * 1000), 5) AS blended_usd_per_kwh
FROM site s
JOIN iso_market m ON m.id = s.iso_market_id
LEFT JOIN energy_invoice i
    ON i.site_id = s.id
    AND i.billing_period_end <= '2026-06-30'
GROUP BY s.id
ORDER BY total_usd DESC;
```

### 预期结果与业务结论

六行, 每座园区一行.

| site_code | iso | capacity_mw | invoice_months | total_mwh | total_usd | blended_usd_per_kwh |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| CMH1 | PJM | 95 | 12 | 454,376 | 63,024,433 | 0.13871 |
| ABI1 | ERCOT | 110 | 12 | 825,817 | 40,000,389 | 0.04844 |
| ALB1 | PJM | 60 | 10 | 277,873 | 36,076,902 | 0.12983 |
| CID1 | MISO | 50 | 12 | 370,234 | 29,680,728 | 0.08017 |
| TPL1 | ERCOT | 75 | 12 | 449,195 | 22,897,485 | 0.05097 |
| FAR1 | MISO | 30 | 12 | 170,818 | 13,265,331 | 0.07766 |

最刺眼的一行是 CMH1 和 ABI1 的对比. Columbus 园区容量比 Abilene 小 15 MW, 用电量只有它的 55%, 电费却高出 58%. 单价 0.13871 对 0.04844, 差了 2.9 倍. 两座俄亥俄园区加起来占全公司电费的 48.4%, 但只占用电量的 28.7%.

这直接回答了 Helen 的问题: 电费上涨不是总量问题, 是结构问题. 钱集中在 PJM 那两座园区.

下一步动作: 把 CMH1 的账单拆开, 看看那 0.13871 里有多大比例不是电量费. 这就是 Q2.

---

## 4. Q2 账单结构拆解, 钱到底花在哪一项

### 业务背景

Q1 给出了三倍的单价差, Helen 的下一个问题是这个差是怎么来的. 她的假设是 PJM 的批发电价本来就贵, 所以贵在电量上. 如果是这样, 除了搬迁园区之外没什么可做的, 这条线就到此为止.

VP of Energy Strategy Dana Whitfield 不同意这个假设. 她认为 PJM 账单里有很大一块根本不是电量费, 而是按功率峰值收的固定费用, 那一块是有办法压的. 两人在预算会上没谈拢, 需要数据来定论.

答案决定 FY2027 要不要立项做削峰: 如果需量类费用占比高, 这笔投资值得做; 如果账单基本就是电量费, 那就是白费力气.

### 标签

聚合 + 窗口函数 / 基础 / CFO

### 解题思路

要碰 `energy_invoice_line`, `energy_invoice`, `site` 和 `iso_market` 四张表. 分项金额在 line 表, 但市场归属要一路 join 回 `iso_market`, 所以是一条四张表的链式连接.

难点在于算占比. 每个收费类别的金额要除以它所在市场的总金额, 而不是全公司总金额, 否则 ERCOT 和 PJM 的数字没法横向比. 这里用窗口函数最省事: `SUM(SUM(l.amount_usd)) OVER (PARTITION BY m.code)`. 两层 `SUM` 看着别扭, 但逻辑是清楚的, 里层是 `GROUP BY` 产生的分组小计, 外层的窗口函数在这些小计上再按市场求和. 如果不用窗口函数, 就得写一个子查询算各市场总额再 join 回来, 代码长一倍.

聚合粒度是一个市场加一个收费类别一行.

### SQL

```sql
SELECT
    m.code AS iso,
    l.charge_category,
    ROUND(SUM(l.amount_usd), 0) AS amount_usd,
    -- 内层 SUM 是分组小计, 外层窗口函数在小计上按市场再求和, 得到该市场的总额
    ROUND(SUM(l.amount_usd) * 100.0 / SUM(SUM(l.amount_usd)) OVER (PARTITION BY m.code), 1)
    AS pct_of_iso_total
FROM energy_invoice_line l
JOIN energy_invoice i ON i.id = l.energy_invoice_id
JOIN site s           ON s.id = i.site_id
JOIN iso_market m     ON m.id = s.iso_market_id
WHERE i.billing_period_end <= '2026-06-30'
GROUP BY m.code, l.charge_category
ORDER BY m.code, amount_usd DESC;
```

### 预期结果与业务结论

十八行左右, 因为三个市场的收费类别数不一样.

| iso | charge_category | amount_usd | pct_of_iso_total |
| :-- | :--- | :-- | :-- |
| ERCOT | ENERGY | 48,069,782 | 76.4 |
| ERCOT | TRANSMISSION | 3,221,580 | 5.1 |
| MISO | ENERGY | 23,266,991 | 54.2 |
| MISO | DEMAND | 10,179,091 | 23.7 |
| PJM | ENERGY | 46,359,265 | 46.8 |
| PJM | DEMAND | 25,456,220 | 25.7 |
| PJM | TRANSMISSION | 9,009,964 | 9.1 |
| PJM | CAPACITY | 6,827,863 | 6.9 |

Dana 赢了这场争论. ERCOT 的账单有 76.4% 是电量费, 剩下的都是零头. PJM 只有 46.8% 是电量费, 而 `DEMAND` 一项就占了 25.7%, 金额 2,546 万美元; 加上按同一个计费需量收的 `TRANSMISSION` 和 `CAPACITY`, 三项合计占 PJM 账单的 41.7%, 金额 4,129 万美元.

换句话说, PJM 那两座园区四成以上的电费不取决于用了多少电, 只取决于功率峰值冲到过多高. 这是一块和用电量脱钩的成本, 也就意味着它是可以单独优化的.

下一步动作: 搞清楚这个计费需量到底是怎么定出来的, 是不是被少数几个瞬间决定的. 这条线在 Q12 和 Q13 继续.

---

## 5. Q3 需求响应项目注册与承诺容量

### 业务背景

Demand Response Manager Priya Raghavan 每年七月要向 ISO 重新申报下一个项目年度的注册容量, FY2027 的申报窗口在八月中旬关闭. 在动笔之前她需要一张现状表: 我们一共参加了几个项目, 每个项目在哪些园区注册了多少容量, 用的是哪种基线算法.

这张表还有一个额外用途. 财务在做审计准备时发现 DR 相关的应收账款科目里有一条挂了很久的零金额记录, 怀疑是某个项目注册信息有误. Priya 需要顺便核实一下注册清单是不是干净的.

### 标签

连接 + 聚合 / 基础 / Demand Response Manager

### 解题思路

三张表: `dr_program`, `dr_enrollment`, `site`, 外加 `iso_market` 取市场代码.

这题最容易出错的地方是过滤条件的位置. `dr_enrollment` 里有一条 `is_active = 0` 的历史遗留注册, 承诺容量为 0. 如果把 `e.is_active = 1` 写进 `WHERE`, 那么假如某个项目所有注册都失效了, 这个项目会整行消失; 写进 `LEFT JOIN` 的 `ON` 子句里, 项目依然会出现, 只是承诺容量为 0. 后者才是 Priya 想要的, 因为她要看的是完整的项目清单.

`GROUP_CONCAT` 把园区代码拼成一列, 省掉一次人工对照. SQLite 的 `GROUP_CONCAT` 第二个参数是分隔符, 和 MySQL 的 `SEPARATOR` 关键字写法不同, 注意别写混.

### SQL

```sql
SELECT
    p.program_code,
    m.code AS iso,
    p.program_type,
    p.baseline_method,
    COUNT(e.id)                           AS enrolled_sites,
    ROUND(SUM(e.enrolled_capacity_mw), 1) AS total_committed_mw,
    GROUP_CONCAT(s.site_code, ', ')       AS sites
FROM dr_program p
JOIN iso_market m ON m.id = p.iso_market_id
-- is_active 过滤放在 ON 里而不是 WHERE 里, 保证没有有效注册的项目也不会整行消失
LEFT JOIN dr_enrollment e ON e.dr_program_id = p.id AND e.is_active = 1
LEFT JOIN site s          ON s.id = e.site_id
GROUP BY p.id
ORDER BY total_committed_mw DESC;
```

### 预期结果与业务结论

六行, 每个项目一行.

| program_code | iso | program_type | baseline_method | sites | total_committed_mw |
| :--- | :-- | :--- | :--- | :--- | :-- |
| ERCOT-4CP-AVOID | ERCOT | TRANSMISSION_AVOIDANCE | FIRM_SERVICE_LEVEL | ABI1, TPL1 | 100.0 |
| ERCOT-ERS-10 | ERCOT | EMERGENCY | AVG_10_BUSINESS_DAYS | ABI1, TPL1 | 17.0 |
| PJM-ELRP | PJM | EMERGENCY | AVG_10_BUSINESS_DAYS | CMH1, ALB1 | 15.0 |
| ERCOT-CLR-RRS | ERCOT | ECONOMIC | METER_BEFORE_AFTER | ABI1, TPL1 | 12.5 |
| PJM-CP | PJM | CAPACITY | FIRM_SERVICE_LEVEL | CMH1, ALB1 | 11.0 |
| MISO-LMR | MISO | CAPACITY | METER_BEFORE_AFTER | CID1, FAR1 | 7.5 |

两件事值得注意. 第一, 4CP 躲避的承诺容量 100 MW 比其他所有项目加起来还多一倍, 但它一年只做四次, 每次两小时. 这个项目的经济学和其他五个完全不同, 后面所有涉及 DR 收益的分析都必须把它单独拿出来算.

第二, 六个项目里有两个用 `AVG_10_BUSINESS_DAYS` 基线, 合计承诺 32 MW. 这是行业里公认最容易被操纵的基线算法, 后面 Q7 会专门查它.

至于财务那条零金额记录: 用 `is_active = 1` 过滤掉的那条注册是 Cedar Rapids 园区登记在 ERCOT 项目下的, 而 Cedar Rapids 在 MISO. 这是当年的登记错误, FY2026 中途已注销. 回复财务可以结掉这个科目.

下一步动作: 这些注册在 FY2026 实际拿到了多少钱, 见 Q4.

---

## 6. Q4 需求响应结算收入排行

### 业务背景

这是 Priya 每个季度都会做的那张表, 也是过去两年她向管理层汇报 DR 成果时用的唯一一张表. FY2026 结束了, 她需要把全年的结算收入按项目和园区拆开, 放进年度总结.

背景是这样: DR 项目在公司内部一直被当成一个纯收入项. 装机已经在那里了, 电网需要的时候压一压负载, ISO 就付钱, 听起来像白捡的. Priya 的年度目标里有一条就是 DR 结算收入, 完成情况直接影响团队考核.

### 标签

多表连接 + 聚合 / 中级 / Demand Response Manager

### 解题思路

要从 `dr_event_participation` 出发, 一路 join 到 `dr_event`, `dr_program`, `dr_enrollment`, `site`, 五张表. 这条链子有点长, 原因是园区信息不在参与记录上, 而是通过注册记录间接确定的, 这是规范化建模的正常代价.

关键的过滤条件是 `pr.program_type <> 'TRANSMISSION_AVOIDANCE'`. 4CP 躲避项目不产生容量补偿, 它的收益体现在下一年的输电费上, 混进来会让人误以为它是个不赚钱的项目. 把它排除掉, 这张表就是纯粹的付费 DR 项目收入.

聚合粒度是一个项目加一个园区一行. 把 `capacity_payment_usd`, `energy_payment_usd`, `penalty_usd` 三项分开列出来, 是因为它们的业务含义完全不同: 容量补偿是保底的, 能量补偿看实际削减量, 罚款是没削够时倒扣的.

### SQL

```sql
SELECT
    pr.program_code,
    s.site_code,
    COUNT(*)                                AS participations,
    ROUND(SUM(p.delivered_reduction_mw), 1) AS total_delivered_mw,
    ROUND(AVG(p.performance_ratio), 2)      AS avg_performance,
    ROUND(SUM(p.capacity_payment_usd), 0)   AS capacity_usd,
    ROUND(SUM(p.energy_payment_usd), 0)     AS energy_usd,
    ROUND(SUM(p.penalty_usd), 0)            AS penalty_usd,
    ROUND(SUM(p.total_settlement_usd), 0)   AS settlement_usd
FROM dr_event_participation p
JOIN dr_event ev      ON ev.id = p.dr_event_id
JOIN dr_program pr    ON pr.id = ev.dr_program_id
JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
JOIN site s           ON s.id = en.site_id
-- 4CP 躲避不产生结算收入, 它的回报在下一年的输电费上, 混进来会失真
WHERE pr.program_type <> 'TRANSMISSION_AVOIDANCE'
GROUP BY pr.program_code, s.site_code
ORDER BY settlement_usd DESC;
```

### 预期结果与业务结论

十行, 每个项目与园区的组合一行.

| program_code | site_code | participations | total_delivered_mw | avg_performance | settlement_usd |
| :--- | :-- | :-- | :-- | :-- | :-- |
| ERCOT-ERS-10 | ABI1 | 14 | 228.7 | 1.35 | 800,513 |
| PJM-ELRP | CMH1 | 11 | 147.0 | 1.48 | 443,423 |
| ERCOT-CLR-RRS | ABI1 | 9 | 180.7 | 1.84 | 439,837 |
| PJM-CP | CMH1 | 6 | 93.0 | 2.00 | 403,200 |
| ERCOT-ERS-10 | TPL1 | 14 | 135.2 | 1.73 | 325,249 |
| MISO-LMR | CID1 | 13 | 51.3 | 0.88 | 258,438 |
| ERCOT-CLR-RRS | TPL1 | 9 | 96.1 | 1.96 | 174,518 |
| PJM-CP | ALB1 | 3 | 29.9 | 1.95 | 168,000 |
| MISO-LMR | FAR1 | 13 | 31.9 | 0.82 | 159,191 |
| PJM-ELRP | ALB1 | 4 | 32.3 | 1.34 | 109,574 |

全年结算收入合计 3,281,943 美元 (约 328 万), 十行全部为正, 罚款只有 7,275 美元. 平均达成率大多超过 1.0, 说明实际削减量普遍高于承诺量. 从这张表看, DR 是一门无可挑剔的生意, Abilene 园区更是贡献了 124 万美元, 是当之无愧的头名.

这就是过去两年管理层看到的全部内容. 数字没有错, 口径也没有算错, 问题在于这张表只统计了钱进来的那一侧.

下一步动作: 把削减掉的算力值多少钱算出来, 放在同一张表上. 这就是 Q5, 也是整份备忘录里最重要的一道题.

---

## 7. Q5 需求响应的真实净收益

### 业务背景

Dana Whitfield 在看完 Q4 之后问了一个问题: 我们削减的那些负载, 上面跑的是什么.

这个问题之所以关键, 是因为 Kestrel 削减的不是抽水站也不是电炉, 是正在训练模型的 GPU 集群. 一个跑了十一天的预训练任务被打断, 损失的不只是中断那几个小时, 还有从上一个 checkpoint 到中断点之间全部白算的部分. 数据集里预训练任务的 checkpoint 间隔是 300 分钟, 平均回滚接近一半, 也就是说停两小时实际损失接近四小时.

商务团队为每类任务给出了内部机会成本单价, 存在 `compute_job.internal_cost_usd_per_gpu_hour` 里, 口径是 "这一小时的 GPU 如果没被中断本来能确认的收入". `curtailed_workload` 表已经把每一次中断的损失逐条算好了.

答案直接决定 FY2027 的 DR 申报: 继续按现状申报, 还是把承诺容量从某些园区挪走.

### 标签

CTE + 多表连接 / 高级 / VP of Energy Strategy

### 解题思路

这题的本质是把两个来源完全不同的金额对齐到同一个粒度上, 所以用两个 CTE 分别算, 最后 join 起来是最清晰的写法.

第一个 CTE 算结算收入, 沿用 Q4 的链路, 但聚合粒度收敛到园区. 第二个 CTE 算算力成本, 从 `curtailed_workload` 出发 join `curtailment_action` 拿到园区.

这里有一个必须踩准的过滤条件: `c.curtailment_type = 'DR_EVENT'`. 削减动作一共有三类, 除了 DR 事件触发的, 还有 4CP 躲避和纯经济性削减. 后两类的成本和 DR 结算收入毫无关系, 混进来会凭空多出两百多万美元的成本, 把结论推向一个错误的极端. 这是这道题最容易翻车的地方.

两个 CTE 之间必须用 `LEFT JOIN` 而不是 `INNER JOIN`. 理论上每个有结算的园区都应该有对应的削减记录, 但如果某个园区某次事件恰好没有任何任务在跑, 它就不会出现在成本 CTE 里, `INNER JOIN` 会把这个园区整行丢掉, 而那恰恰是净收益最高的情况. 用 `LEFT JOIN` 加 `COALESCE` 兜住.

最后按净收益升序排, 亏得最多的排最前面.

### SQL

```sql
WITH settlement AS (
    SELECT
        s.id   AS site_id,
        s.site_code,
        SUM(p.total_settlement_usd) AS settlement_usd
    FROM dr_event_participation p
    JOIN dr_event ev      ON ev.id = p.dr_event_id
    JOIN dr_program pr    ON pr.id = ev.dr_program_id
    JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
    JOIN site s           ON s.id = en.site_id
    WHERE pr.program_type <> 'TRANSMISSION_AVOIDANCE'
    GROUP BY s.id
),
compute_cost AS (
    -- 只统计 DR_EVENT 类削减. ECONOMIC 与 4CP_AVOIDANCE 各有各的账,
    -- 混进来会虚增成本两百多万美元, 把结论推到错误的方向
    SELECT
        c.site_id,
        SUM(w.opportunity_cost_usd) AS opportunity_usd,
        SUM(w.sla_credit_usd)       AS sla_credit_usd,
        SUM(w.lost_gpu_hours)       AS lost_gpu_hours
    FROM curtailed_workload w
    JOIN curtailment_action c ON c.id = w.curtailment_action_id
    WHERE c.curtailment_type = 'DR_EVENT'
    GROUP BY c.site_id
)
SELECT
    st.site_code,
    si.primary_workload_type,
    ROUND(st.settlement_usd, 0)                 AS settlement_usd,
    ROUND(COALESCE(cc.lost_gpu_hours, 0), 0)    AS lost_gpu_hours,
    ROUND(COALESCE(cc.opportunity_usd, 0), 0)   AS opportunity_usd,
    ROUND(COALESCE(cc.sla_credit_usd, 0), 0)    AS sla_credit_usd,
    ROUND(st.settlement_usd
        - COALESCE(cc.opportunity_usd, 0)
        - COALESCE(cc.sla_credit_usd, 0), 0)  AS net_benefit_usd
FROM settlement st
JOIN site si              ON si.id = st.site_id
LEFT JOIN compute_cost cc ON cc.site_id = st.site_id
ORDER BY net_benefit_usd;
```

### 预期结果与业务结论

六行, 每座园区一行, 按净收益升序.

| site_code | workload_type | settlement_usd | lost_gpu_hours | opportunity_usd | sla_credit_usd | net_benefit_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- |
| ABI1 | TRAINING | 1,240,350 | 497,529 | 1,561,080 | 95,690 | -416,419 |
| CID1 | TRAINING | 258,438 | 135,916 | 426,672 | 35,085 | -203,319 |
| FAR1 | MIXED | 159,191 | 63,401 | 187,698 | 31,327 | -59,835 |
| ALB1 | MIXED | 277,574 | 62,270 | 152,178 | 32,552 | 92,844 |
| TPL1 | MIXED | 499,767 | 130,551 | 391,150 | 6,978 | 101,639 |
| CMH1 | INFERENCE | 846,623 | 165,423 | 396,395 | 73,787 | 376,442 |

全公司合计: 结算收入 328.2 万美元, 算力机会成本加 SLA 赔付 339.1 万美元, 真实净收益 **负 10.9 万美元**. 那个被汇报了两年的 328 万利润, 净值其实是亏的.

但真正有用的信息不是这个总数, 而是它的分布. `primary_workload_type` 这一列把结论摆得很清楚: 两座跑长周期训练的园区 (ABI1, CID1) 合计净亏 62 万美元, 而跑在线推理的 CMH1 净赚 37.6 万美元. 同样一个 DR 项目, 在不同类型的园区上是两门完全不同的生意.

原因藏在 `lost_gpu_hours` 那一列里. 把它和结算收入放在一起算个比值, 差距就清楚了: ABI1 每牺牲 1 个 GPU 小时只换回 2.49 美元结算收入 (1,240,350 除以 497,529), 而每个 GPU 小时的实际代价是 3.14 美元; CMH1 每牺牲 1 个 GPU 小时换回 5.12 美元 (846,623 除以 165,423), 代价只有 2.40 美元. 两座园区在电量口径上削减的规模接近, 但 ABI1 付出的 GPU 小时是 CMH1 的三倍. 原因是 ABI1 上跑的是 checkpoint 间隔 300 分钟的预训练任务, 中断一次还要额外赔上大半个间隔的回滚, 而在线推理任务摘掉流量再挂回去, 回滚成本是零.

下一步动作: 不是退出 DR, 是把 DR 换个地方做. 起草一份 FY2027 申报调整方案, 把 ABI1 和 CID1 的承诺容量降到接近零, 把腾出来的额度挪给 CMH1 和 ALB1. 在提交之前先用 Q6 确认这不是被少数几次极端事件带偏的.

---

## 8. Q6 哪些园区的哪些事件在亏钱

### 业务背景

Dana 拿到 Q5 的结论之后没有立刻签字. 她的顾虑很具体: 全年汇总的亏损可能是被两三次特别糟糕的事件拉出来的, 比如某次事件恰好撞上一个用了四千张卡的大任务. 如果是这样, 结论应该是 "改进调度时避开大任务", 而不是 "退出这个园区的 DR".

要区分这两种情况, 就得看亏损的分布: 是集中在少数几次, 还是每一次都在亏.

这个判断决定方案的性质: 前者是运营改进, 后者是战略退出.

### 标签

CTE + 相关子查询 / 中级 / VP of Energy Strategy

### 解题思路

粒度要下沉到 "一次事件在一座园区" 这一层. 结算金额本来就是这个粒度 (`dr_event_participation` 一行就是一个事件加一个注册), 但算力成本存在 `curtailed_workload` 上, 需要通过 `curtailment_action` 的 `dr_event_id` 和 `site_id` 两个字段一起匹配才能对齐.

这里用相关子查询比再写一个 CTE 更直观, 因为匹配条件有两个字段, 写成 CTE 再 join 反而要处理 join key 为空的情况. 相关子查询里的 `COALESCE(SUM(...), 0)` 保证没有任何任务被中断的事件返回 0 而不是 NULL, 否则后面的减法会整行变成 NULL, 这是 SQL 里最常见的静默错误之一.

注意 CTE 里 join 了两次 `site` (别名 `s` 和 `si`), 这是为了让主查询能同时拿到园区代码和负载类型. 其实一次 join 就够, 保留两个别名只是为了让每个字段的来源一目了然.

外层按园区聚合, 统计净收益为负的事件数和占比. 有了占比就能回答 Dana 的问题.

### SQL

```sql
WITH per_event AS (
    SELECT
        ev.id           AS event_id,
        ev.event_code,
        pr.program_code,
        s.site_code,
        si.primary_workload_type,
        p.total_settlement_usd,
        -- 用 dr_event_id 和 site_id 两个字段一起匹配才能对齐到 "一次事件在一座园区"
        -- COALESCE 兜住没有任务被中断的情况, 否则后面减法会整行变 NULL
        (SELECT COALESCE(SUM(w.opportunity_cost_usd + w.sla_credit_usd), 0)
        FROM curtailed_workload w
        JOIN curtailment_action c ON c.id = w.curtailment_action_id
        WHERE c.dr_event_id = ev.id
            AND c.site_id     = s.id
            AND c.curtailment_type = 'DR_EVENT') AS compute_cost_usd
    FROM dr_event_participation p
    JOIN dr_event ev      ON ev.id = p.dr_event_id
    JOIN dr_program pr    ON pr.id = ev.dr_program_id
    JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
    JOIN site s           ON s.id = en.site_id
    JOIN site si          ON si.id = s.id
    WHERE pr.program_type <> 'TRANSMISSION_AVOIDANCE'
)
SELECT
    site_code,
    primary_workload_type,
    COUNT(*) AS participations,
    SUM(CASE WHEN total_settlement_usd - compute_cost_usd < 0 THEN 1 ELSE 0 END) AS negative_events,
    ROUND(SUM(CASE WHEN total_settlement_usd - compute_cost_usd < 0 THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1)                          AS negative_pct,
    ROUND(MIN(total_settlement_usd - compute_cost_usd), 0) AS worst_event_usd,
    ROUND(AVG(total_settlement_usd - compute_cost_usd), 0) AS avg_net_usd
FROM per_event
GROUP BY site_code
ORDER BY avg_net_usd;
```

### 预期结果与业务结论

六行.

| site_code | workload_type | participations | negative_events | negative_pct | worst_event_usd | avg_net_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- |
| ABI1 | TRAINING | 23 | 18 | 78.3 | -72,169 | -18,105 |
| CID1 | TRAINING | 13 | 12 | 92.3 | -28,684 | -15,640 |
| FAR1 | MIXED | 13 | 9 | 69.2 | -17,246 | -4,603 |
| TPL1 | MIXED | 23 | 9 | 39.1 | -23,969 | 4,419 |
| ALB1 | MIXED | 7 | 3 | 42.9 | -21,880 | 13,263 |
| CMH1 | INFERENCE | 17 | 6 | 35.3 | -20,401 | 22,144 |

Dana 的顾虑被排除了. CID1 有 92.3% 的事件净收益为负, ABI1 是 78.3%, 这不是个别极端事件, 是系统性的. 六座园区合计 96 次参与里有 57 次亏钱 (这里只统计非 4CP 的付费 DR 参与, 4CP 的 8 次已被 `program_type <> 'TRANSMISSION_AVOIDANCE'` 排除).

反过来看 CMH1: 65% 的事件是赚钱的, 平均每次净赚 22,144 美元. 最差的一次亏 20,401 美元, 和 ABI1 最差的 72,169 美元不在一个量级.

结论从 "运营改进" 变成 "战略调整": ABI1 和 CID1 应该退出付费 DR 项目, 承诺容量转移到 CMH1 和 ALB1. 按平均值粗算, 把 ABI1 的 21 MW 承诺量挪到 CMH1, FY2027 的净收益能从负 10.9 万转正到 60 万以上.

下一步动作: 把这个建议写进备忘录第二节. 但在提交之前, 还有一个更麻烦的问题要查清楚, 就是我们报给 ISO 的削减量本身是不是可信的. 见 Q7.

---

## 9. Q7 基线灌水嫌疑事件筛查

### 业务背景

Priya 在一次行业会议上听到一件事: 某个 ISO 在去年做了一轮回溯审计, 对多家参与者的削减量重新核算, 追回了七位数的结算款. 审计的切入点是基线, 具体做法是检查事件前几天的负载有没有异常升高.

这件事让她坐立不安. Kestrel 参加的六个项目里有两个用 `AVG_10_BUSINESS_DAYS` 基线, 也就是拿事件前十个工作日同时段的平均负载做参照. 这个算法的弱点众所周知: 只要事件前几天多用点电, 基线就抬上去了, 削减量凭空变大, 而且完全合规, 因为没有任何规则禁止你多用电.

问题是 Kestrel 内部有没有人在这么干. 调度系统是自动的, 但调度策略是人配的. Priya 需要在 ISO 找上门之前先自己查一遍.

数据里有两个现成的诊断字段: `pre_event_3day_avg_mw` 和 `pre_event_30day_avg_mw`. 它们不参与结算, 就是留给这种核查用的.

### 标签

连接 + 比值过滤 / 中级 / Demand Response Manager

### 解题思路

思路本身很简单: 算两个诊断字段的比值, 大于某个阈值就标出来. 难点在于比值阈值定多少, 以及只查哪些项目.

只查 `AVG_10_BUSINESS_DAYS` 的项目, 因为另外两种基线算法对事件前三天的行为不敏感. `METER_BEFORE_AFTER` 取事件前后各一小时, `FIRM_SERVICE_LEVEL` 取前三十天同时段均值, 三天的异常摊到三十天里只能推高一个百分点. 把它们混进来只会稀释信号.

阈值取 1.06. 正常运行下负载有季节性和周内波动, 三天均值和三十天均值差个百分之三四很常见, 但超过 6% 就需要解释了.

除法要注意分母. 这个数据集里 `pre_event_30day_avg_mw` 不会是 0 (每座园区在事件发生时都在运行), 所以可以直接除. 换个数据集就该加 `NULLIF` 保护.

把 `baseline_mw`, `delivered_reduction_mw` 和 `settlement_usd` 一起列出来, 是为了让每一条嫌疑记录都能直接看到涉及多少钱.

### SQL

```sql
SELECT
    pr.program_code,
    pr.baseline_method,
    s.site_code,
    ev.event_code,
    DATE(ev.event_start)                                         AS event_date,
    p.pre_event_3day_avg_mw,
    p.pre_event_30day_avg_mw,
    ROUND(p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw, 4) AS inflation_ratio,
    p.baseline_mw,
    p.delivered_reduction_mw,
    ROUND(p.total_settlement_usd, 0)                             AS settlement_usd
FROM dr_event_participation p
JOIN dr_event ev      ON ev.id = p.dr_event_id
JOIN dr_program pr    ON pr.id = ev.dr_program_id
JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
JOIN site s           ON s.id = en.site_id
-- 只有这种基线算法会被事件前三天的行为影响, 另外两种天然免疫
WHERE pr.baseline_method = 'AVG_10_BUSINESS_DAYS'
    AND p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw >= 1.06
ORDER BY inflation_ratio DESC;
```

### 预期结果与业务结论

十行左右, 全部集中在 TPL1 和 CMH1 两座园区.

| program_code | site_code | event_code | event_date | 3day_mw | 30day_mw | inflation_ratio | settlement_usd |
| :--- | :-- | :--- | :--- | :-- | :-- | :-- | :-- |
| PJM-ELRP | CMH1 | PJM-ELRP-FY26-11 | 2026-06-29 | 63.130 | 55.072 | 1.1463 | 40,521 |
| ERCOT-ERS-10 | TPL1 | ERCOT-ERS-10-FY26-11 | 2026-06-11 | 60.445 | 53.989 | 1.1196 | 24,000 |
| PJM-ELRP | CMH1 | PJM-ELRP-FY26-09 | 2026-06-01 | 57.835 | 52.188 | 1.1082 | 42,727 |
| ERCOT-ERS-10 | TPL1 | ERCOT-ERS-10-FY26-12 | 2026-06-19 | 61.021 | 55.245 | 1.1046 | 24,000 |

十条记录合计涉及结算金额 337,283 美元, 认定削减量 117.1 MW, 平均灌水比 1.0922.

分布很说明问题. 用 `AVG_10_BUSINESS_DAYS` 基线的两个项目里有相当比例的事件被标出来, 而用另外两种基线的项目一条都没有, 比值全部在 1.03 以内. 如果这是自然波动, 三种基线算法下的分布应该差不多. 它们差这么多, 说明这不是波动.

还有一个细节: 被标出来的事件里有六条集中在 2026 年 6 月, 也就是财年最后一个月. 这个时间分布很难用巧合解释.

下一步动作: 这些记录本身还不能定性为违规, 因为多用电不违反任何规则. 但 Priya 需要知道如果 ISO 用干净基线重算, 敞口有多大. 见 Q8.

---

## 10. Q8 用干净基线重算, 虚增了多少

### 业务背景

Q7 标出了十条嫌疑记录, 涉及 33.7 万美元. 但 33.7 万是这些事件的全部结算金额, 不等于要退回的金额. 真正的敞口是 "用干净基线重算之后, 少掉的那部分削减量对应的钱".

Dana 要在备忘录里给董事会一个具体数字, 而且要能顶住追问: 你说的敞口是怎么算出来的.

这个数字还有一个更实际的用途. 如果敞口只有几万美元, 内部纠正一下调度策略就行; 如果是六位数, 就需要主动向 ISO 报备, 因为主动报备和被审计出来是两种完全不同的性质.

### 标签

多层 CTE / 高级 / VP of Energy Strategy

### 解题思路

核心是构造一个反事实基线. 逻辑是这样: 现有的 `baseline_mw` 是按被抬高之后的负载算出来的, 抬高的幅度可以用 `pre_event_3day_avg_mw / pre_event_30day_avg_mw` 这个比值来估计. 那么把 `baseline_mw` 除以这个比值 (等价于乘以它的倒数), 就得到了 "如果事件前三天没有异常, 基线大概会是多少".

这是一个估计而不是精确重算, 因为真正的重算需要拿到事件前十个工作日每一天的逐区间负载再做一次平均. 但作为敞口量级的估计它是站得住的, 而且逻辑简单到可以在董事会上一句话讲清楚.

第一个 CTE `flagged` 沿用 Q7 的筛选条件, 顺便把修正后的基线算出来. 第二个 CTE `recomputed` 用修正基线减去实测负载得到修正削减量, 这里必须套 `MAX(0, ...)`, 因为修正之后基线可能低于实测负载, 削减量不能是负数. SQLite 的 `MAX` 在给两个参数时是标量函数不是聚合函数, 这一点和别的方言不同, 正好可以直接用.

最后按园区聚合, 给出认定量, 修正量, 虚增量和虚增比例.

### SQL

```sql
WITH flagged AS (
    SELECT
        p.id,
        s.site_code,
        p.baseline_mw,
        p.actual_metered_mw,
        p.delivered_reduction_mw,
        p.total_settlement_usd,
        p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw AS inflation_ratio,
        -- 把基线按灌水比例还原回去, 得到 "事件前三天没有异常时" 的估计基线
        p.baseline_mw * (p.pre_event_30day_avg_mw / p.pre_event_3day_avg_mw) AS corrected_baseline_mw
    FROM dr_event_participation p
    JOIN dr_event ev      ON ev.id = p.dr_event_id
    JOIN dr_program pr    ON pr.id = ev.dr_program_id
    JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
    JOIN site s           ON s.id = en.site_id
    WHERE pr.baseline_method = 'AVG_10_BUSINESS_DAYS'
        AND p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw >= 1.06
),
recomputed AS (
    SELECT
        site_code,
        delivered_reduction_mw,
        -- 修正基线可能低于实测负载, 削减量不能为负. SQLite 的双参数 MAX 是标量函数
        MAX(0, corrected_baseline_mw - actual_metered_mw) AS corrected_delivered_mw,
        total_settlement_usd
    FROM flagged
)
SELECT
    site_code,
    COUNT(*)                                                       AS flagged_participations,
    ROUND(SUM(delivered_reduction_mw), 1)                          AS claimed_mw,
    ROUND(SUM(corrected_delivered_mw), 1)                          AS corrected_mw,
    ROUND(SUM(delivered_reduction_mw - corrected_delivered_mw), 1) AS overstated_mw,
    ROUND(SUM(delivered_reduction_mw - corrected_delivered_mw) * 100.0
        / SUM(delivered_reduction_mw), 1)                        AS overstated_pct,
    ROUND(SUM(total_settlement_usd), 0)                            AS settlement_at_risk_usd
FROM recomputed
GROUP BY site_code
ORDER BY overstated_mw DESC;
```

### 预期结果与业务结论

两行, TPL1 和 CMH1.

| site_code | flagged_participations | claimed_mw | corrected_mw | overstated_mw | overstated_pct | settlement_at_risk_usd |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| CMH1 | 6 | 82.1 | 51.6 | 30.5 | 37.2 | 241,283 |
| TPL1 | 4 | 35.0 | 15.3 | 19.6 | 56.1 | 96,000 |

两座园区合计: 认定削减量 117.1 MW, 修正后 66.9 MW, 虚增 50.1 MW, 虚增比例约 43%. 涉及结算金额 33.7 万美元, 按虚增比例折算, 敞口大约在 14 万美元上下.

TPL1 的虚增比例 56.1% 尤其扎眼: 这些事件里认定的削减量有一多半是基线抬高带来的, 而不是真的少用了电.

十四万美元这个量级落在 "需要主动处理但不至于是灾难" 的区间. 主动报备的成本是退款加上一次合规检查, 被审计出来的成本是退款加罚款加上未来几年的重点关注.

下一步动作: 三件事. 第一, 把调度策略里事件前的负载安排规则改掉, 这是根因. 第二, 建一个月度监控, 把 Q7 那个比值做成告警, 超过 1.06 自动提示. 第三, 就 FY2026 这十条记录起草一份主动报备材料, 交法务和 Dana 会签之后提交 ISO.

---

## 11. Q9 风电 PPA 月度对比市场均价

### 业务背景

Power Procurement Manager Marcus Ellery 每个月都出一张 PPA 结算对比表, 内容是 Longhorn Ridge 那份 150 MW 风电长约的锁定价和当月市场均价的差额. 这张表是他向管理层证明 PPA 价值的主要依据, 也是他去年推动续签另外两份光伏 PPA 时用的论据.

FY2027 的续约窗口在明年一月, Longhorn Ridge 这份合约还有九年才到期, 但里面有一个五年重议条款, 明年一月是第一个行权窗口. Marcus 要决定是行权重议还是维持原样.

他的判断依据一直是: 锁价 28.50 美元每 MWh, 西德州节点全年均价 35.47, 每 MWh 省 6.97, 全年发电 36.7 万 MWh, 省两百五十多万. 这是笔好买卖, 不需要重议.

### 标签

CTE + 聚合 / 基础 / Power Procurement Manager

### 解题思路

需要把两个不同粒度的东西对齐到月: `lmp_interval_price` 是 15 分钟粒度, `ppa_generation_hourly` 是小时粒度. 各自先按月聚合成两个 CTE, 再按年月 join.

节点和合约的对应关系要通过 `site_id` 建立: `pricing_node.site_id` 指向园区, `supply_contract.site_id` 也指向园区, 两者在同一座园区上碰头. 这是数据模型里一个不太直观但很关键的连接路径.

用 `STRFTIME('%Y-%m', ...)` 提取年月. SQLite 没有 `DATE_TRUNC`, 也没有 `EXTRACT`, 日期处理基本都靠 `STRFTIME`, 格式串和 C 语言的 `strftime` 一致.

市场均价这里用的是 `AVG(lmp_usd_per_mwh)`, 也就是对全月每一个 15 分钟区间做简单平均, 每个区间权重相同. 这正是 Marcus 一直以来的算法. 记住这一点, Q10 会回来处理它.

### SQL

```sql
WITH monthly_market AS (
    SELECT
        n.site_id,
        STRFTIME('%Y-%m', l.interval_start) AS ym,
        AVG(l.lmp_usd_per_mwh)              AS simple_avg_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id, ym
),
monthly_gen AS (
    SELECT
        g.supply_contract_id,
        STRFTIME('%Y-%m', g.observed_at) AS ym,
        SUM(g.generation_mwh)            AS gen_mwh
    FROM ppa_generation_hourly g
    GROUP BY g.supply_contract_id, ym
)
SELECT
    mg.ym,
    ROUND(mg.gen_mwh, 0)                       AS ppa_mwh,
    c.strike_price_usd_per_mwh                 AS strike,
    ROUND(mm.simple_avg_lmp, 2)                AS market_simple_avg,
    ROUND((mm.simple_avg_lmp - c.strike_price_usd_per_mwh) * mg.gen_mwh, 0) AS apparent_saving_usd
FROM monthly_gen mg
JOIN supply_contract c ON c.id = mg.supply_contract_id
-- 节点与合约通过 site_id 碰头, 这是数据模型里不太直观但必须走的路径
JOIN monthly_market mm ON mm.site_id = c.site_id AND mm.ym = mg.ym
WHERE c.contract_code = 'PPA-LHR-WIND-01'
ORDER BY mg.ym;
```

### 预期结果与业务结论

十二行, 每月一行.

| ym | ppa_mwh | strike | market_simple_avg | apparent_saving_usd |
| :--- | :-- | :-- | :-- | :-- |
| 2025-07 | 30,429 | 28.50 | 60.31 | 968,072 |
| 2025-08 | 24,985 | 28.50 | 54.95 | 660,779 |
| 2025-12 | 26,954 | 28.50 | 40.72 | 329,270 |
| 2026-02 | 33,870 | 28.50 | 20.12 | -283,955 |
| 2026-03 | 40,857 | 28.50 | 12.79 | -641,694 |
| 2026-04 | 40,571 | 28.50 | 10.65 | -724,018 |
| 2026-05 | 39,594 | 28.50 | 14.09 | -570,409 |

这张表本身就藏着答案, 只是 Marcus 一直没往那个方向看. 注意两列的关系: 发电量最高的四个月 (2026 年 2 月到 5 月, 每月三万四到四万 MWh) 恰好是市场均价最低的四个月 (10.65 到 20.12 美元每 MWh), 这几个月的 "节省" 全是负的. 而节省最多的 7 月和 8 月, 发电量是全年最低的.

换句话说, 这份合约在电价便宜的时候拼命买, 在电价贵的时候几乎买不到. 用年度均价做的那个 "省两百五十万" 的结论, 是把每个月的权重当成一样了.

下一步动作: 用发电量加权重算, 得到真实价差. 见 Q10.

---

## 12. Q10 按出力加权的 PPA 真实价差

### 业务背景

Q9 那张月度表让 Marcus 意识到问题可能出在口径上. 但他需要一个能直接写进续约建议书的数字, 而且这个数字要能同时算给三份可变出力 PPA, 因为如果风电 PPA 有问题, 那两份光伏 PPA 也得一起复核.

行业里这个概念叫 shape risk, 也就是形状风险: 你实际买到的电集中在电站出力最高的那些小时里, 如果那些小时恰好市场价最低, 用年均价做的对比就是错的. 正确口径是按发电量加权的市场价.

这个数字直接决定明年一月的重议决定, 涉及九年合约期, 是 Marcus 今年最重要的一个判断.

### 标签

CTE + 加权聚合 / 高级 / Power Procurement Manager

### 解题思路

关键是把 15 分钟电价先聚合到小时, 才能和逐小时的发电量一一对齐. 直接拿 15 分钟数据去 join 小时数据会产生四倍的行数膨胀, 加权结果虽然碰巧还是对的 (因为每小时四个区间权重相同), 但行数膨胀会让后面的 `SUM(generation_mwh)` 变成四倍, 年发电量直接错掉. 这是这道题最容易翻车的地方.

`hourly_price` 这个 CTE 用 `STRFTIME('%Y-%m-%d %H', ...)` 生成小时键, 把电价压到小时粒度. `simple_avg` 这个 CTE 保留 Q9 的简单平均口径, 目的是把两种算法并排放在同一行上, 让差异一眼可见.

加权平均的写法是 `SUM(generation_mwh * hourly_lmp) / SUM(generation_mwh)`. 注意不能写成 `AVG(generation_mwh * hourly_lmp)`, 那算的是别的东西.

最后两列是给决策用的: `apparent_saving_usd` 是错误口径下的结论, `true_net_cost_usd` 是正确口径下的结论, 正数表示这份 PPA 比直接在市场买电更贵.

三份合约一起算, 光伏正好做对照组.

### SQL

```sql
WITH hourly_price AS (
    -- 必须先把 15 分钟电价压到小时. 直接和小时级发电量 join 会产生四倍行数膨胀,
    -- 加权价碰巧还对, 但 SUM(generation_mwh) 会变成四倍, 年发电量直接错掉
    SELECT
        n.site_id,
        STRFTIME('%Y-%m-%d %H', l.interval_start) AS hour_key,
        AVG(l.lmp_usd_per_mwh)                    AS hourly_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id, hour_key
),
simple_avg AS (
    SELECT n.site_id, AVG(l.lmp_usd_per_mwh) AS simple_avg_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id
)
SELECT
    c.contract_code,
    c.contract_type,
    s.site_code,
    c.strike_price_usd_per_mwh AS strike,
    ROUND(sa.simple_avg_lmp, 2) AS market_simple_avg,
    ROUND(SUM(g.generation_mwh * hp.hourly_lmp) / SUM(g.generation_mwh), 2) AS market_gen_weighted,
    ROUND(SUM(g.generation_mwh), 0) AS annual_mwh,
    ROUND((sa.simple_avg_lmp - c.strike_price_usd_per_mwh) * SUM(g.generation_mwh), 0)
    AS apparent_saving_usd,
    ROUND(SUM(g.generation_mwh) * c.strike_price_usd_per_mwh
        - SUM(g.generation_mwh * hp.hourly_lmp), 0) AS true_net_cost_usd
FROM ppa_generation_hourly g
JOIN supply_contract c ON c.id = g.supply_contract_id
JOIN site s            ON s.id = c.site_id
JOIN hourly_price hp   ON hp.site_id  = c.site_id
    AND hp.hour_key = STRFTIME('%Y-%m-%d %H', g.observed_at)
JOIN simple_avg sa     ON sa.site_id = c.site_id
GROUP BY c.id
ORDER BY true_net_cost_usd DESC;
```

### 预期结果与业务结论

三行, 三份可变出力 PPA 各一行.

| contract_code | type | strike | market_simple_avg | market_gen_weighted | annual_mwh | apparent_saving_usd | true_net_cost_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| PPA-LHR-WIND-01 | WIND_PPA | 28.50 | 35.47 | 25.54 | 367,498 | 2,560,062 | 1,088,973 |
| PPA-BUC-SOLAR-01 | SOLAR_PPA | 38.90 | 45.09 | 49.56 | 74,259 | 459,894 | -791,768 |
| PPA-BLK-SOLAR-01 | SOLAR_PPA | 31.75 | 39.37 | 48.59 | 139,168 | 1,060,405 | -2,343,603 |

风电这一行给出了明确答案. 简单均价 35.47, 出力加权均价 25.54, 相差 9.93 美元每 MWh. 锁价 28.50 高于加权均价, 所以这份合约实际上比直接在市场买电多花了 108.9 万美元. 而按 Marcus 原来的口径, 结论是省了 256 万. 两个数字相差 365 万, 符号相反.

两份光伏 PPA 是完美的对照组. 它们的出力加权均价 (49.56 和 48.59) 反而高于简单均价 (45.09 和 39.37), 因为太阳最好的时候通常也是用电最多, 电价最高的时候. 所以光伏 PPA 的形状价值是正的, 两份合约真实省下 79.2 万和 234.4 万美元.

结论不是 "PPA 都是坑", 而是 "风电 PPA 在西德州这个节点上是坑, 光伏不是". 差别在于出力形状和电价形状是同向还是反向.

下一步动作: 明年一月的重议窗口必须行权, 目标是把 Longhorn Ridge 的结算方式从 as generated 改成带 shape 调整的结构, 或者干脆减量. 建议书里要附上 Q11 那张图作为机理说明, 因为董事会需要理解为什么会这样, 而不只是知道结果.

---

## 13. Q11 风电出力越大, 电价越低吗

### 业务背景

你把 Q10 的结论给 Dana 看之后, 她的反应是: 这个结论会被挑战, 因为它反直觉. 董事会里有人会问, 风电便宜是好事, 为什么锁了个便宜价反而亏.

要回答这个问题, 需要展示背后的机理, 而不只是给出一个加权平均数. 机理是这样: 西德州风电装机极其密集, 风大的时候几百台机组同时满发, 把当地节点的边际电价压到很低甚至为负; 风停的时候电价飙升, 但那时候你的 PPA 一度电也发不出来.

这张表就是要把这个机理量化出来, 放进建议书的附录.

### 标签

CASE 分档 + 窗口函数 / 中级 / Energy Data Analyst

### 解题思路

按容量因子分档, 看每一档对应的平均电价. 如果机理成立, 电价应该随出力档位单调下降.

先用 CTE 把节点电价压到小时, 和 Q10 同一个理由. 然后用 `CASE WHEN` 按 `capacity_factor_pct` 分成五档. 分档的边界要选得有意义: 10% 以下基本是无风, 55% 以上是满发, 中间三档覆盖常态运行区间.

`pct_of_annual_gen` 这一列用了窗口函数 `SUM(SUM(generation_mwh)) OVER ()`. 空的 `OVER ()` 表示不分区, 在全部分组结果上求和, 也就是全年总发电量. 这个写法比再套一层子查询干净得多.

最后加一列 `negative_price_hours`, 直接数每一档里有多少小时电价为负. 这一列的说服力比平均值更强, 因为负电价是个非黑即白的事实.

### SQL

```sql
WITH hourly_price AS (
    SELECT
        STRFTIME('%Y-%m-%d %H', l.interval_start) AS hour_key,
        AVG(l.lmp_usd_per_mwh)                    AS hourly_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    WHERE n.node_code = 'HB_WEST_ABI'
    GROUP BY hour_key
),
bucketed AS (
    SELECT
        CASE
        WHEN g.capacity_factor_pct <  10 THEN '1. 0-10 pct 几乎无风'
        WHEN g.capacity_factor_pct <  25 THEN '2. 10-25 pct 小风'
        WHEN g.capacity_factor_pct <  40 THEN '3. 25-40 pct 常态'
        WHEN g.capacity_factor_pct <  55 THEN '4. 40-55 pct 大风'
        ELSE                                  '5. 55 pct 以上 满发'
        END AS cf_bucket,
        hp.hourly_lmp,
        g.generation_mwh
    FROM ppa_generation_hourly g
    JOIN supply_contract c ON c.id = g.supply_contract_id
    JOIN hourly_price hp   ON hp.hour_key = STRFTIME('%Y-%m-%d %H', g.observed_at)
    WHERE c.contract_code = 'PPA-LHR-WIND-01'
)
SELECT
    cf_bucket,
    COUNT(*)                      AS hours,
    ROUND(AVG(hourly_lmp), 2)     AS avg_lmp,
    ROUND(SUM(generation_mwh), 0) AS gen_mwh,
    -- 空的 OVER () 表示在全部分组上求和, 得到全年总发电量
    ROUND(SUM(generation_mwh) * 100.0 / SUM(SUM(generation_mwh)) OVER (), 1) AS pct_of_annual_gen,
    SUM(CASE WHEN hourly_lmp < 0 THEN 1 ELSE 0 END) AS negative_price_hours
FROM bucketed
GROUP BY cf_bucket
ORDER BY cf_bucket;
```

### 预期结果与业务结论

五行, 每档一行.

| cf_bucket | hours | avg_lmp | gen_mwh | pct_of_annual_gen | negative_price_hours |
| :--- | :-- | :-- | :-- | :-- | :-- |
| 1. 0-10 pct 几乎无风 | 470 | 83.07 | 4,744 | 1.3 | 0 |
| 2. 10-25 pct 小风 | 2,700 | 62.38 | 74,074 | 20.2 | 0 |
| 3. 25-40 pct 常态 | 3,419 | 30.86 | 159,180 | 43.3 | 2 |
| 4. 40-55 pct 大风 | 1,888 | 2.09 | 110,823 | 30.2 | 805 |
| 5. 55 pct 以上 满发 | 283 | -22.04 | 18,676 | 5.1 | 282 |

单调性完美成立, 而且幅度惊人. 从几乎无风到满发, 平均电价从 83.07 美元每 MWh 一路掉到 负 22.04, 跨度超过 100 美元.

最关键的一行是最后两档: 大风和满发这两档合计贡献了全年发电量的 35.3%, 但这些小时的平均电价一档是 2.09, 一档是 负 22.04. 也就是说超过三分之一的 PPA 电量, 是在市场电价接近零甚至为负的时候买的, 而 Kestrel 为它付了 28.50 美元每 MWh.

满发那一档 283 小时里有 282 小时电价为负, 几乎是一比一. 这不是概率问题, 是物理必然.

反过来看第一档: 电价 83.07 美元每 MWh 的那 470 小时, PPA 只提供了全年 1.3% 的电量. 最需要便宜电的时候, 这份合约帮不上忙.

下一步动作: 这张表直接作为续约建议书的附录 A. 同时把它抄送给做选址的团队, 因为它说明了一件更大的事: 在风电富集节点签固定价 PPA, 需要的是带 shape 调整的结构, 而不是简单的 as generated.

---

## 14. Q12 每月计费需量峰值区间定位

### 业务背景

Q2 显示 PJM 那两座园区有四成以上的电费按计费需量收. Director of Data Center Operations Tom Brennan 接到 Dana 的请求, 要搞清楚这个计费需量到底是被什么决定的.

Tom 的直觉是它反映的是园区的正常运行水平, 压不下来: 机器就那么多, 满负荷跑的时候功率就是那么高. 如果是这样, 唯一的办法是少接单, 那显然不划算.

但如果计费需量是被少数几个孤立的瞬间决定的, 而且这些瞬间和正常运行水平差得很远, 那就完全是另一回事了.

### 标签

窗口函数 RANK / 中级 / Director of Data Center Operations

### 解题思路

计费需量取自当月功率最高的那个 15 分钟区间, 所以要按月找出 Top N. 这是窗口函数的标准场景: `RANK() OVER (PARTITION BY 月份 ORDER BY 功率 DESC)`.

用 `RANK` 而不是 `ROW_NUMBER`, 是因为如果出现并列最高值, 我们希望它们都被标成第 1 名, 那本身就是一个值得注意的信号 (说明可能撞到了某种上限).

拿到排名之后, 需要把第 1, 2, 3 名横过来放在同一行上, 方便看差距. 这一步用 `MAX(CASE WHEN rk = 1 THEN ... END)` 做条件聚合, 是 SQL 里做行转列的通用手法. `MAX` 在这里不是求最大值, 而是在一组里只有一个非空值时把它取出来.

最后一列 `gap_1_to_2_mw` 是这道题的重点: 最高值比第二高值高出多少. 如果这个差距一直很小, 说明峰值是连续运行的自然结果; 如果某个月突然冒出一个大差距, 说明那个月的峰值是个孤立事件.

时间过滤用 `< '2026-07-01'` 而不是 `<= '2026-06-30'`, 因为 `interval_start` 是带时分的 datetime, 用 `<=` 会漏掉 6 月 30 日当天零点之后的所有区间.

### SQL

```sql
WITH cmh_intervals AS (
    SELECT
        m.interval_start,
        m.metered_demand_mw,
        STRFTIME('%Y-%m', m.interval_start) AS ym
    FROM interval_meter_reading m
    JOIN site s ON s.id = m.site_id
    WHERE s.site_code = 'CMH1'
        -- interval_start 带时分, 用 <= '2026-06-30' 会漏掉当天零点之后的全部区间
        AND m.interval_start < '2026-07-01'
),
ranked AS (
    SELECT
        ym,
        interval_start,
        metered_demand_mw,
        RANK() OVER (PARTITION BY ym ORDER BY metered_demand_mw DESC) AS rk
    FROM cmh_intervals
)
SELECT
    ym,
    -- 条件聚合做行转列, MAX 在这里只是 "取出组里唯一的非空值"
    MAX(CASE WHEN rk = 1 THEN interval_start END)              AS peak_interval,
    ROUND(MAX(CASE WHEN rk = 1 THEN metered_demand_mw END), 3) AS peak_1_mw,
    ROUND(MAX(CASE WHEN rk = 2 THEN metered_demand_mw END), 3) AS peak_2_mw,
    ROUND(MAX(CASE WHEN rk = 3 THEN metered_demand_mw END), 3) AS peak_3_mw,
    ROUND(MAX(CASE WHEN rk = 1 THEN metered_demand_mw END)
        - MAX(CASE WHEN rk = 2 THEN metered_demand_mw END), 3) AS gap_1_to_2_mw
FROM ranked
WHERE rk <= 3
GROUP BY ym
ORDER BY ym;
```

### 预期结果与业务结论

十二行, 每月一行.

| ym | peak_interval | peak_1_mw | peak_2_mw | peak_3_mw | gap_1_to_2_mw |
| :--- | :--- | :-- | :-- | :-- | :-- |
| 2025-07 | 2025-07-03 15:00 | 82.569 | 82.390 | 82.380 | 0.179 |
| 2025-08 | 2025-08-14 15:45 | 88.638 | 87.977 | 82.813 | 0.661 |
| 2025-09 | 2025-09-11 15:00 | 71.834 | 71.630 | 70.721 | 0.204 |
| 2025-11 | 2025-11-09 12:15 | 67.331 | 66.151 | 65.755 | 1.180 |
| 2026-02 | 2026-02-22 14:00 | 66.391 | 66.213 | 66.023 | 0.178 |
| 2026-05 | 2026-05-30 15:30 | 77.609 | 77.360 | 77.166 | 0.249 |

Tom 的直觉部分对部分不对. 大多数月份的第一名和第二名只差零点几 MW, 峰值确实是正常运行的自然结果, 压不下来.

但八月是个例外, 而且是决定性的例外. 八月的峰值 88.638 MW 出现在 2025-08-14 15:45 这一个区间, 比第二高的月份 (七月 82.569 MW) 高出 6 MW. 更重要的是八月内部第三名 82.813 MW 和前两名之间有 5.2 MW 的断层, 而其他月份第一名到第三名的跨度都不到 1.2 MW. 这说明八月前两个区间 (15:30 和 15:45, 正好 30 分钟) 是一个孤立事件, 不属于正常运行.

对照运维日志, 那 30 分钟是一次新到货 GB200 机柜的 burn-in 满载测试.

一次 30 分钟的测试创下了全财年最高需量. 而 AEP Ohio 的费率里有 85% 的需量棘轮条款, 意味着这个峰值会像地板一样垫高之后 11 个月的账单.

下一步动作: 把这次测试值多少钱算清楚. 见 Q13.

---

## 15. Q13 那次 burn-in 测试值多少钱

### 业务背景

Tom 需要一个具体金额去说服基础设施团队修改测试流程. 光说 "burn-in 测试会推高需量" 没用, 工程团队会回答测试是必须做的.

要让这个对话有结果, 必须回答两个问题: 这一次测试一共多花了多少钱, 以及有没有不影响测试目的的替代做法. 第一个问题是这道查询的任务.

金额要拆成两块. 一块是八月账单自身多付的需量电费. 另一块更隐蔽, 是棘轮条款带来的: 这个峰值成为之后若干个月计费需量的下限, 那些月份即使用电很少也要按这个下限付钱.

### 标签

多层 CTE + 反事实 / 高级 / Director of Data Center Operations

### 解题思路

这是一道反事实分析题. 要算的是 "如果那次测试没做, 账单会是多少", 然后和实际账单相减.

第一步构造反事实的八月峰值: 把 burn-in 那两个区间排除掉, 重新求八月的最大值. 用 `NOT IN` 排除两个具体的时间戳.

第二步构造反事实的棘轮下限: 拿十二个月的峰值, 其中八月替换成反事实值, 求最大值再乘以棘轮比例. 这里用了一个 `CASE WHEN` 在子查询里做替换, 比先算再修正要干净.

第三步算两块差额. 八月自身的差额是 (实际峰值 减 反事实峰值) 乘以需量电价. 棘轮的差额是每个棘轮生效月份的 "实际计费需量 减 反事实计费需量" 之和, 再乘以需量电价. 反事实计费需量本身也要取 "当月实测峰值" 和 "反事实棘轮下限" 的较大者, 所以又套了一层 `MAX`.

这道题 CTE 层数比较多, 但每一层只做一件事, 拆开写比嵌套子查询好读得多.

### SQL

```sql
WITH cmh_invoice AS (
    SELECT i.*,
        t.demand_charge_usd_per_kw_month AS demand_rate,
        t.demand_ratchet_pct             AS ratchet_pct
    FROM energy_invoice i
    JOIN site s            ON s.id = i.site_id
    JOIN tariff_schedule t ON t.id = s.tariff_schedule_id
    WHERE s.site_code = 'CMH1'
),
aug_without_burnin AS (
    -- 反事实: 剔除 burn-in 那两个区间之后, 八月的峰值会是多少
    SELECT MAX(m.metered_demand_mw) * 1000 AS peak_kw
    FROM interval_meter_reading m
    JOIN site s ON s.id = m.site_id
    WHERE s.site_code = 'CMH1'
        AND STRFTIME('%Y-%m', m.interval_start) = '2025-08'
        AND m.interval_start NOT IN ('2025-08-14 15:30:00.000000',
            '2025-08-14 15:45:00.000000')
),
counterfactual_floor AS (
    -- 没有 burn-in 的话, 全年最高需量是各月峰值的最大值 (八月换成反事实值)
    SELECT MAX(peak_kw) * (SELECT ratchet_pct FROM cmh_invoice LIMIT 1) / 100.0 AS floor_kw
    FROM (
        SELECT CASE WHEN STRFTIME('%Y-%m', billing_period_start) = '2025-08'
            THEN (SELECT peak_kw FROM aug_without_burnin)
            ELSE metered_peak_demand_kw END AS peak_kw
        FROM cmh_invoice
    )
)
SELECT
    ROUND((SELECT MAX(metered_peak_demand_kw) FROM cmh_invoice), 2)  AS actual_annual_peak_kw,
    ROUND((SELECT peak_kw FROM aug_without_burnin), 2)               AS aug_peak_without_burnin_kw,
    ROUND((SELECT MAX(billing_demand_kw) FROM cmh_invoice
        WHERE is_ratchet_binding = 1), 2)                       AS actual_ratchet_floor_kw,
    ROUND((SELECT floor_kw FROM counterfactual_floor), 2)            AS counterfactual_floor_kw,
    (SELECT COUNT(*) FROM cmh_invoice WHERE is_ratchet_binding = 1)  AS ratchet_bound_months,
    ROUND(((SELECT MAX(metered_peak_demand_kw) FROM cmh_invoice)
            - (SELECT peak_kw FROM aug_without_burnin)) * 18.20, 0)     AS august_extra_usd,
    ROUND((SELECT SUM(billing_demand_kw
                - MAX(metered_peak_demand_kw,
                    (SELECT floor_kw FROM counterfactual_floor)))
        FROM cmh_invoice WHERE is_ratchet_binding = 1) * 18.20, 0) AS ratchet_extra_usd;
```

### 预期结果与业务结论

一行.

| 字段 | 值 |
| :--- | :-- |
| actual_annual_peak_kw | 88,637.67 |
| aug_peak_without_burnin_kw | 82,813.00 |
| actual_ratchet_floor_kw | 75,342.02 |
| counterfactual_floor_kw | 70,391.05 |
| ratchet_bound_months | 8 |
| august_extra_usd | 106,009 |
| ratchet_extra_usd | 681,401 |

那次 30 分钟的 burn-in 测试, 直接后果是八月账单多付 10.6 万美元, 间接后果是之后 8 个月的棘轮下限被抬高约 4,951 kW, 累计多付 68.1 万美元. 合计约 **78.7 万美元**.

换个角度看这个数字: 30 分钟的测试, 平均每分钟成本 2.6 万美元.

而且这笔钱几乎是白花的. burn-in 测试的目的是验证新机柜在满载下的稳定性, 它不需要在下午三点四十五分做, 也不需要和园区其他负载叠加在一起做.

下一步动作: 三条建议写进给基础设施团队的备忘录. 第一, 所有 burn-in 与压力测试挪到凌晨 2 点到 5 点的负载低谷窗口, 光这一条就能把增量峰值削掉大半. 第二, 测试期间对其他机房启用临时功率封顶, 保证园区总功率不突破当月已有峰值. 第三, 在 DCIM 系统里加一条硬规则, 任何会让 15 分钟平均功率超过当月已有峰值的操作需要 Tom 本人审批. 三条加起来的实施成本不到五万美元.

---

## 16. Q14 4CP 预测复盘

### 业务背景

Grid Operations Specialist Luis Ferrer 负责得州两座园区的 4CP 躲避. 这件事的规则是: ERCOT 会在 6 月到 9 月每个月挑出全德州用电最高的那一个 15 分钟, 你在那四个时刻的平均用电量决定你下一整年的输电费.

问题在于没人事先知道哪个 15 分钟会是峰值. Luis 每天下午盯着 ERCOT 的负荷预测, 判断今天会不会出现月峰值, 如果判断是, 就提前四小时通知两座园区, 在预测峰值前后各一小时的窗口里把负载压到最低.

FY2027 的运营计划要在八月定稿, Luis 需要先复盘 FY2026 的表现: 预测准不准, 窗口开得够不够宽.

### 标签

日期计算 + 区间判定 / 中级 / Grid Operations Specialist

### 解题思路

数据都在 `dr_event` 一张表里, 不需要 join, 但有三个字段要理解清楚. `predicted_peak_interval_start` 是 Luis 事前的预测, `iso_actual_peak_interval_start` 是 ERCOT 事后确认的真实峰值, `kestrel_coincident_demand_mw` 是我们在真实峰值那一刻的用电量. 而 `event_start` 到 `event_end` 是实际执行的削减窗口.

要算两件事. 第一是预测偏差多少分钟, 用 `JULIANDAY` 把两个时间戳转成儒略日 (带小数的天数), 相减再乘以 1440 得到分钟. SQLite 没有 `DATEDIFF`, 这是标准做法. 结果要 `CAST AS INTEGER`, 否则会带一串浮点尾数.

第二是判定命中还是扑空: 真实峰值有没有落在削减窗口内, 用 `BETWEEN` 判断即可. 这里 `BETWEEN` 的闭区间语义正好合适, 因为峰值恰好落在窗口边界上也算命中.

只有 4CP 类事件才有这三个字段, 其余 53 条记录全是 NULL, 所以必须用 `trigger_reason` 过滤.

### SQL

```sql
SELECT
    ev.event_code,
    DATE(ev.event_start)              AS event_date,
    ev.predicted_peak_interval_start  AS predicted_peak,
    ev.iso_actual_peak_interval_start AS iso_actual_peak,
    -- SQLite 没有 DATEDIFF, 用 JULIANDAY 相减乘 1440 得到分钟数
    CAST(ROUND((JULIANDAY(ev.iso_actual_peak_interval_start)
                - JULIANDAY(ev.predicted_peak_interval_start)) * 1440) AS INTEGER)
    AS forecast_miss_minutes,
    ev.event_start                    AS curtail_window_start,
    ev.event_end                      AS curtail_window_end,
    CASE WHEN ev.iso_actual_peak_interval_start BETWEEN ev.event_start AND ev.event_end
    THEN 'HIT' ELSE 'MISS' END   AS outcome,
    ROUND(ev.kestrel_coincident_demand_mw, 1) AS coincident_demand_mw
FROM dr_event ev
-- 只有 4CP 类事件才填这三个字段, 其余 53 条全是 NULL
WHERE ev.trigger_reason = 'FORECAST_4CP_PEAK'
ORDER BY ev.event_start;
```

### 预期结果与业务结论

五行, 2025 年 4CP 季四次加 2026 年 4CP 季第一次.

| event_code | predicted_peak | iso_actual_peak | miss_minutes | outcome | coincident_mw |
| :--- | :--- | :--- | :-- | :--- | :-- |
| ERCOT-4CP-AVOID-2025-06 | 2025-06-24 16:45 | 2025-06-24 17:00 | 15 | HIT | 23.6 |
| ERCOT-4CP-AVOID-2025-07 | 2025-07-14 15:30 | 2025-07-14 16:00 | 30 | HIT | 24.7 |
| ERCOT-4CP-AVOID-2025-08 | 2025-08-01 16:45 | 2025-08-01 18:00 | 75 | MISS | 163.9 |
| ERCOT-4CP-AVOID-2025-09 | 2025-09-04 17:45 | 2025-09-04 18:00 | 15 | HIT | 19.6 |
| ERCOT-4CP-AVOID-2026-06 | 2026-06-26 18:00 | 2026-06-26 18:15 | 15 | HIT | 22.2 |

五次里四次命中. 命中的四次预测偏差都在 30 分钟以内, 真实峰值稳稳落在窗口里, 重合需量压到了 19.6 到 24.7 MW.

八月那次偏了 75 分钟. 削减窗口是 15:45 到 17:45, 真实峰值出现在 18:00, 差了整整 15 分钟才出窗口. 那一刻两座得州园区已经恢复运行, 重合需量 163.9 MW, 是其他四次的七倍.

值得注意的是失手的原因: 不是完全预测错了日期, 日期是对的; 是低估了当天负荷峰值出现的时间. 八月一日那天傍晚气温回落得比预期慢, 空调负荷一直没降下来, 峰值比历史规律晚了一个多小时.

另一个细节: 命中的四次偏差分别是 15, 30, 15, 15 分钟, 而窗口半径是 60 分钟. 也就是说这四次都还有相当余量, 窗口并不是勉强兜住的. 唯一失手的那次偏差 75 分钟, 只比窗口半径多 15 分钟.

下一步动作: 把削减窗口从前后各 60 分钟放宽到前后各 90 分钟. 按 FY2026 的偏差分布, 90 分钟能覆盖全部五次. 代价是每次多削减一小时, 但和失手的代价相比微不足道. 具体多少钱见 Q15.

---

## 17. Q15 4CP 失手的财务代价

### 业务背景

CFO Helen Okafor 在预算会上对 4CP 这件事表示怀疑. 她的原话是: 一年就四个小时的事, 能有多大影响, 值得专门配一个人天天盯吗.

Luis 需要一个数字回答她, 而且这个数字要能同时支持两件事: 证明这个岗位的价值, 以及证明放宽窗口的提案值得批. 最有说服力的做法是把 FY2026 那次失手的代价算出来.

这个数字也直接进 FY2027 预算: 输电费是按上一年 4CP 结果算的, 所以 2025 年那次失手的账单要在 FY2027 付.

### 标签

CTE + 反事实 / 中级 / CFO

### 解题思路

又是一道反事实题, 但比 Q13 简单. 逻辑是: 实际的 4CP 平均需量是四次的均值; 如果八月也命中, 那次的重合需量应该和其他三次差不多, 所以用命中那几次的平均值代替它.

第一个 CTE 圈出 2025 年 4CP 季的四次事件. 注意时间范围要写 `>= '2025-06-01' AND < '2025-10-01'`, 因为 2026 年 6 月那次属于下一个 4CP 季, 混进来会把四个月变成五个月, 平均值直接错掉. 这是这道题最容易出错的地方, 而且错了之后结果看起来还挺合理, 很难发现.

顺带算一个 `is_hit` 标志, 沿用 Q14 的 `BETWEEN` 判定.

第二个 CTE 算实际平均, 第三个算只看命中场次的平均. 最后用交叉连接 (`FROM actual a, hit_only h`) 把两个单行结果拼在一起. 两个 CTE 各自只有一行, 交叉连接就是最直接的写法, 不需要 join 条件.

输电费率 58 美元每 kW 每年是 Oncor 的工业费率, 写死在查询里. 单位换算要注意: 需量是 MW, 费率是每 kW, 所以要乘 1000.

### SQL

```sql
WITH season_2025 AS (
    -- 只圈 2025 年 4CP 季的四个月. 2026 年 6 月那次属于下一季,
    -- 混进来会把四个月算成五个月, 而且结果看起来还挺合理, 很难发现
    SELECT
        event_code,
        kestrel_coincident_demand_mw AS mw,
        CASE WHEN iso_actual_peak_interval_start BETWEEN event_start AND event_end
        THEN 1 ELSE 0 END AS is_hit
    FROM dr_event
    WHERE trigger_reason = 'FORECAST_4CP_PEAK'
        AND event_start >= '2025-06-01'
        AND event_start <  '2025-10-01'
),
actual AS (
    SELECT AVG(mw) AS avg_mw,
        COUNT(*) AS months,
        SUM(CASE WHEN is_hit = 1 THEN 1 ELSE 0 END) AS hits
    FROM season_2025
),
hit_only AS (
    SELECT AVG(mw) AS avg_hit_mw FROM season_2025 WHERE is_hit = 1
)
SELECT
    a.months                                          AS four_cp_months,
    a.hits                                            AS forecast_hits,
    a.months - a.hits                                 AS forecast_misses,
    ROUND(a.avg_mw, 2)                                AS actual_4cp_avg_mw,
    ROUND(h.avg_hit_mw, 2)                            AS counterfactual_avg_mw,
    -- 需量单位是 MW, 费率是每 kW 每年, 所以乘 1000
    ROUND(a.avg_mw * 1000 * 58.0, 0)                  AS actual_transmission_usd,
    ROUND(h.avg_hit_mw * 1000 * 58.0, 0)              AS counterfactual_transmission_usd,
    ROUND((a.avg_mw - h.avg_hit_mw) * 1000 * 58.0, 0) AS cost_of_the_miss_usd
FROM actual a, hit_only h;
```

### 预期结果与业务结论

一行.

| 字段 | 值 |
| :--- | :-- |
| four_cp_months | 4 |
| forecast_hits | 3 |
| forecast_misses | 1 |
| actual_4cp_avg_mw | 57.97 |
| counterfactual_avg_mw | 22.66 |
| actual_transmission_usd | 3,362,362 |
| counterfactual_transmission_usd | 1,314,319 |
| cost_of_the_miss_usd | 2,048,043 |

一次 75 分钟的预测偏差, 代价 **204.8 万美元**.

机理是 4CP 取的是四个月的平均值, 所以任何一个月失手, 影响会被四个月摊薄, 但基数太大了: 163.9 MW 对 22 MW 左右, 差了 140 MW, 摊到四个月上还是 35 MW, 乘以 58 美元每 kW 每年就是两百万.

这也回答了 Helen 的问题. 这个岗位一年只有四个真正关键的小时, 但那四个小时值三百多万美元的输电费, 命中和失手之间的差额是七位数. 三次命中省下的钱 (相对于完全不做躲避的满载 163.9 MW 基准) 远超过整个团队的成本.

下一步动作: 批准 Luis 提的两条. 第一, 削减窗口从前后 60 分钟放宽到前后 90 分钟, 按 FY2026 的偏差分布能覆盖全部五次, 增量成本是每次多削减一小时的算力机会成本, 按 ABI1 和 TPL1 的任务混合估算约 12 万美元一次, 四次不到 50 万, 相对两百万的风险敞口显然划算. 第二, 在 8, 9 两个月气温回落慢的日子里, 加做一次 17:00 的二次判断, 允许临时延长窗口.

---

## 18. Q16 电价尖峰时我们在干什么

### 业务背景

Abilene 园区的电量费全部按实时电价结算, 没有零售固定价合约兜底. 这意味着 ERCOT 那些动辄几千美元每 MWh 的尖峰时段, Kestrel 是直接暴露在里面的.

自动调度系统里有一条规则: 实时电价超过 240 美元每 MWh 就触发经济性削减, 主动停掉一部分任务. 这条规则是两年前配的, 从来没复核过.

Dana 想知道这条规则实际执行得怎么样: 尖峰时段我们真的削了吗, 削了多少, 以及在负电价时段我们有没有反过来多用电.

### 标签

窗口函数 LAG + 分档 / 中级 / Energy Data Analyst

### 解题思路

要把电价和同一时刻的园区负载对齐, 所以 `lmp_interval_price` 和 `interval_meter_reading` 按 `site_id` 加 `interval_start` 两个字段 join. 两张表都是 15 分钟粒度, 时间戳完全对齐, 不需要任何聚合就能一对一匹配.

`LAG` 窗口函数取上一个区间的电价, 用来算价格跳变幅度. 这一列的意义是展示 ERCOT 价格波动的剧烈程度: 从一个区间到下一个区间能跳几千美元, 意味着自动调度规则的响应速度是关键.

分档用 `CASE WHEN`, 边界选在 0 (负电价分界), 50 (常态上沿), 240 (经济性削减阈值), 1000 (真正的尖峰). 这几个边界都有业务含义, 不是随便切的.

`curtailed_pct` 用 `SUM(is_curtailed) * 100.0 / COUNT(*)` 算, 注意要乘 100.0 而不是 100, 否则 SQLite 会做整数除法, 结果全是 0. 这是个很常见的坑.

最后一列算每档的实际电费支出, 用负载乘以 0.25 小时再乘电价.

### SQL

```sql
WITH abi AS (
    SELECT
        l.interval_start,
        l.lmp_usd_per_mwh,
        m.metered_demand_mw,
        m.is_curtailed,
        LAG(l.lmp_usd_per_mwh) OVER (ORDER BY l.interval_start) AS prev_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    -- 两张表都是 15 分钟粒度且时间戳对齐, 可以直接一对一 join
    JOIN interval_meter_reading m
        ON m.site_id        = n.site_id
        AND m.interval_start = l.interval_start
    WHERE n.node_code = 'HB_WEST_ABI'
),
bucketed AS (
    SELECT
        CASE
        WHEN lmp_usd_per_mwh <    0 THEN '1. 负电价'
        WHEN lmp_usd_per_mwh <   50 THEN '2. 0 到 50'
        WHEN lmp_usd_per_mwh <  240 THEN '3. 50 到 240'
        WHEN lmp_usd_per_mwh < 1000 THEN '4. 240 到 1000'
        ELSE                             '5. 1000 以上'
        END AS price_bucket,
        lmp_usd_per_mwh,
        metered_demand_mw,
        is_curtailed,
        lmp_usd_per_mwh - prev_lmp AS lmp_jump
    FROM abi
    WHERE prev_lmp IS NOT NULL
)
SELECT
    price_bucket,
    COUNT(*)                       AS intervals,
    ROUND(AVG(lmp_usd_per_mwh), 2) AS avg_lmp,
    ROUND(AVG(metered_demand_mw), 2) AS avg_load_mw,
    -- 必须写 100.0 而不是 100, 否则 SQLite 走整数除法, 结果全是 0
    ROUND(SUM(is_curtailed) * 100.0 / COUNT(*), 1) AS curtailed_pct,
    ROUND(MAX(lmp_jump), 0)        AS max_jump_from_prev_interval,
    ROUND(SUM(metered_demand_mw * 0.25 * lmp_usd_per_mwh), 0) AS energy_cost_usd
FROM bucketed
GROUP BY price_bucket
ORDER BY price_bucket;
```

### 预期结果与业务结论

五行.

| price_bucket | intervals | avg_lmp | avg_load_mw | curtailed_pct | max_jump | energy_cost_usd |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| 1. 负电价 | 6,303 | -18.12 | 92.74 | 0.1 | 86 | -2,638,794 |
| 2. 0 到 50 | 17,771 | 26.08 | 94.11 | 0.5 | 108 | 10,933,145 |
| 3. 50 到 240 | 10,918 | 70.11 | 95.40 | 1.3 | 136 | 18,273,714 |
| 4. 240 到 1000 | 3 | 875.66 | 98.35 | 33.3 | 929 | 64,823 |
| 5. 1000 以上 | 44 | 2,849.10 | 96.80 | 47.7 | 4,563 | 2,992,590 |

三个发现.

第一, 负电价时段的表现很好. 全年有 6,303 个区间 (18%) 电价为负, 这些时段园区平均跑 92.74 MW, 几乎满载, 削减率只有 0.1%. 结果是这一档的电费是 负 264 万美元, 也就是说 Kestrel 因为在这些时段用电而净收入了 264 万. 这一条不用改.

第二, 尖峰时段的响应不够. 1000 美元以上那一档 44 个区间, 削减率只有 47.7%, 一半以上的尖峰区间园区仍在接近满载运行. 这 44 个区间总共 11 个小时, 电费 299 万美元, 占 ABI1 全年电量费的将近一成.

第三, 价格跳变幅度说明了原因. 最高一档从上一个区间到这个区间跳了 4,563 美元每 MWh. 自动调度规则是在价格已经越过阈值之后才触发, 而 ERCOT 的尖峰经常在一两个区间内完成, 等系统反应过来削减动作已经晚了.

下一步动作: 把经济性削减规则从 "事后触发" 改成 "事前预警". ERCOT 的实时价格有前瞻指标, 比如运行备用容量和五分钟预出清价格. 建议引入这两个信号做提前判断, 目标是把 1000 美元以上档位的削减率从 47.7% 提到 80% 以上. 不过在动手之前要先看 Q20, 因为经济性削减本身的经济性也值得怀疑.

---

## 19. Q17 湿球温度与冷却负载

### 业务背景

FY2027 资本预算里有一个待定项目: 把 Columbus 园区从风冷改造成液冷, 预算 4,200 万美元. 项目的主要卖点是降低冷却能耗, 但基础设施团队给出的节能测算被 Helen 质疑, 理由是测算基于厂商提供的参数, 不是 Kestrel 自己的运行数据.

Dana 让你用现有数据做一次交叉验证. 手上正好有两座工况可比但冷却方式不同的园区: Columbus 是风冷, Abilene 是液冷. 如果液冷的冷却能耗占比确实明显更低, 而且优势随温度上升而扩大, 那么厂商的测算方向是对的.

### 标签

时间对齐连接 + 分档 / 中级 / Energy Data Analyst

### 解题思路

难点是两张表粒度不同: `weather_observation` 是小时级, `interval_meter_reading` 是 15 分钟级. 必须先把计量数据聚合到小时, 否则一条气象记录会匹配到四条计量记录, 每小时被重复计算四次. 虽然算平均值时结果碰巧还对, 但 `COUNT(*)` 会变成四倍, 一眼就能看出不对.

聚合到小时之后, 用 `STRFTIME('%Y-%m-%d %H', ...)` 生成的小时键做 join. 注意 `hourly_load` 这个 CTE 里要加 `WHERE m.metered_demand_mw > 0`, 把 ALB1 投产前的零值排除掉. 虽然这道题只看 CMH1 和 ABI1, 但养成这个习惯能避免以后扩展查询时踩坑.

冷却开销比例用 `AVG(cooling_mw) / AVG(it_mw)` 而不是 `AVG(cooling_mw / it_mw)`. 前者是 "总冷却量除以总 IT 量", 后者是 "每小时比值的平均". 两者在 IT 负载波动大时会有差异, 前者才是工程上关心的那个数.

按湿球温度分五档, 边界选在 40, 55, 65, 75 华氏度. 55 度是冷却系统开始明显吃力的拐点.

### SQL

```sql
WITH hourly_load AS (
    -- 必须先把 15 分钟计量聚合到小时, 否则一条气象记录会匹配四条计量记录,
    -- 平均值碰巧还对, 但 COUNT(*) 会变成四倍
    SELECT
        m.site_id,
        STRFTIME('%Y-%m-%d %H', m.interval_start) AS hour_key,
        AVG(m.it_load_mw)      AS it_mw,
        AVG(m.cooling_load_mw) AS cooling_mw
    FROM interval_meter_reading m
    WHERE m.metered_demand_mw > 0
    GROUP BY m.site_id, hour_key
)
SELECT
    s.site_code,
    s.cooling_type,
    CASE
    WHEN w.wet_bulb_temp_f < 40 THEN '1. 40F 以下'
    WHEN w.wet_bulb_temp_f < 55 THEN '2. 40 到 55F'
    WHEN w.wet_bulb_temp_f < 65 THEN '3. 55 到 65F'
    WHEN w.wet_bulb_temp_f < 75 THEN '4. 65 到 75F'
    ELSE                              '5. 75F 以上'
    END AS wet_bulb_bucket,
    COUNT(*)                     AS hours,
    ROUND(AVG(hl.cooling_mw), 3) AS avg_cooling_mw,
    -- 总冷却除以总 IT, 不是每小时比值再平均. 前者才是工程上的能耗开销比
    ROUND(AVG(hl.cooling_mw) * 100.0 / AVG(hl.it_mw), 1) AS cooling_overhead_pct
FROM weather_observation w
JOIN site s ON s.id = w.site_id
JOIN hourly_load hl
    ON hl.site_id  = w.site_id
    AND hl.hour_key = STRFTIME('%Y-%m-%d %H', w.observed_at)
WHERE s.site_code IN ('CMH1', 'ABI1')
GROUP BY s.site_code, wet_bulb_bucket
ORDER BY s.site_code, wet_bulb_bucket;
```

### 预期结果与业务结论

十行, 两座园区各五档.

| site_code | cooling_type | wet_bulb_bucket | hours | avg_cooling_mw | cooling_overhead_pct |
| :--- | :--- | :--- | :-- | :-- | :-- |
| ABI1 | LIQUID_COOLED | 1. 40F 以下 | 2,635 | 5.361 | 6.2 |
| ABI1 | LIQUID_COOLED | 3. 55 到 65F | 1,172 | 6.768 | 7.8 |
| ABI1 | LIQUID_COOLED | 5. 75F 以上 | 1,544 | 12.535 | 14.4 |
| CMH1 | AIR_COOLED | 1. 40F 以下 | 4,163 | 5.090 | 11.5 |
| CMH1 | AIR_COOLED | 3. 55 到 65F | 1,486 | 6.671 | 15.0 |
| CMH1 | AIR_COOLED | 5. 75F 以上 | 342 | 14.745 | 27.2 |

厂商的方向是对的, 而且优势比他们说的还明显. 低温档位下液冷开销 6.2% 对风冷 11.5%, 差 5.3 个百分点; 高温档位下 14.4% 对 27.2%, 差 12.8 个百分点. 液冷的优势不是固定的, 它随温度上升而扩大, 因为风冷系统在高湿球温度下效率衰减得快得多.

但有一个 Helen 会立刻问到的问题: Columbus 一年里湿球温度超过 75 华氏度的时间只有 342 小时, 占全年 3.9%, 而 Abilene 有 1,544 小时. 液冷优势最大的那个档位, 在 Columbus 一年只出现十几天. 按小时数加权重算, Columbus 改造后的年度节能会明显低于按 Abilene 数据外推的结果.

下一步动作: 把这张表交回给基础设施团队, 要求他们用 Columbus 自己的湿球温度分布 (而不是行业平均或 Abilene 数据) 重做投资回收测算, 并且把两种冷却方式在每个温度档位的实测开销比作为输入参数. 在拿到重做的测算之前, 这 4,200 万的资本项目建议暂缓进入 FY2027 预算.

---

## 20. Q18 三类供应合约的评估口径

### 业务背景

Q10 那份 PPA 复核结论出来之后, Marcus 意识到一个更基础的问题: 公司现在有十一份供应合约, 分四种类型, 而他一直用同一套口径去评价它们. 风电 PPA 的教训说明这套口径至少对一类合约是错的, 那对其他类型呢.

在准备 FY2027 采购策略之前, 他需要先把评估框架理清楚: 每种合约类型应该用什么口径评价, 哪些数字可以直接比, 哪些不能.

### 标签

聚合 + 分类 / 基础 / Power Procurement Manager

### 解题思路

以 `supply_contract` 为主表按合约类型聚合. 需要两个辅助信息: 每座园区所在节点的市场均价 (从 `lmp_interval_price` 算), 以及可变出力合约的实际发电量 (从 `ppa_generation_hourly` 算).

两个辅助信息都用 CTE 预先算好再 join, 比写成相关子查询快得多, 因为电价表有 21 万行, 相关子查询会对每份合约重复扫描一遍.

PPA 发电量那个 CTE 要注意: 只有三份合约有发电记录, 另外八份没有, 所以必须 `LEFT JOIN` 加 `COALESCE`, 否则那八份合约会整行消失.

最后一列不是计算结果, 是一句评估口径说明. 把它写进 SQL 而不是留给人工注释, 是为了让这张表可以直接贴进采购策略文档, 每一行都自带解释.

### SQL

```sql
WITH node_price AS (
    SELECT n.site_id, AVG(l.lmp_usd_per_mwh) AS avg_market_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id
),
ppa_realised AS (
    SELECT c.site_id,
        c.contract_type,
        SUM(g.generation_mwh) AS mwh
    FROM ppa_generation_hourly g
    JOIN supply_contract c ON c.id = g.supply_contract_id
    GROUP BY c.id
)
SELECT
    c.contract_type,
    COUNT(DISTINCT c.id)                      AS contracts,
    ROUND(AVG(c.strike_price_usd_per_mwh), 2) AS avg_strike,
    ROUND(AVG(np.avg_market_lmp), 2)          AS avg_node_market_price,
    ROUND(SUM(COALESCE(pr.mwh, 0)), 0)        AS ppa_delivered_mwh,
    CASE WHEN c.contract_type IN ('WIND_PPA', 'SOLAR_PPA')
    THEN '有逐小时出力, 需要按出力加权评估'
    WHEN c.contract_type = 'RETAIL_FIXED'
    THEN '固定到户价, 含输配, 不可与批发价直接比'
    ELSE '随行就市, 无锁价' END           AS evaluation_note
FROM supply_contract c
JOIN node_price np ON np.site_id = c.site_id
-- 只有三份合约有发电记录, 必须 LEFT JOIN 否则另外八份会整行消失
LEFT JOIN ppa_realised pr ON pr.site_id = c.site_id AND pr.contract_type = c.contract_type
GROUP BY c.contract_type
ORDER BY avg_strike DESC;
```

### 预期结果与业务结论

四行, 每种合约类型一行.

| contract_type | contracts | avg_strike | avg_node_market_price | ppa_delivered_mwh | evaluation_note |
| :--- | :-- | :-- | :-- | :-- | :--- |
| RETAIL_FIXED | 4 | 54.63 | 40.34 | 0 | 固定到户价, 含输配, 不可与批发价直接比 |
| SOLAR_PPA | 2 | 35.33 | 42.23 | 213,427 | 有逐小时出力, 需要按出力加权评估 |
| WIND_PPA | 1 | 28.50 | 35.47 | 367,498 | 有逐小时出力, 需要按出力加权评估 |
| WHOLESALE_INDEX | 4 | 0.00 | 36.24 | 0 | 随行就市, 无锁价 |

这张表最重要的作用是提醒: `avg_strike` 和 `avg_node_market_price` 这两列放在一起看非常诱人, 但只有对同一类合约内部做纵向比较才有意义, 跨类型横着比是错的.

`RETAIL_FIXED` 那一行看起来最贵, 锁价 54.63 远高于市场均价 40.34, 像是签亏了 14 美元每 MWh. 但零售固定价是到户价, 里面已经含了输配电费, 而市场均价是纯批发价, 不含输配. 拿含输配的价格和不含输配的价格比, 结论必然是错的. 要比就得给市场均价加上对应的输配成本, 那两座俄亥俄园区的输配相关费用折算下来大约 20 美元每 MWh, 加上去之后零售固定价其实是划算的.

`WHOLESALE_INDEX` 那一行的锁价是 0, 因为它根本没有锁价, 就是随行就市. 这一行不能参与任何价格比较.

真正可以横向比的只有两份 PPA 之间, 而且必须用 Q10 那个出力加权口径, 不能用这张表里的简单均价.

下一步动作: 把这个评估框架写进采购策略文档的第一节, 作为以后所有合约评估的口径基准. 具体规则是: 可变出力 PPA 一律按出力加权市场价评估; 零售固定价合约要先把输配成本加到市场基准上再比; 批发指数敞口不做价格评估, 只评估风险敞口占比.

---

## 21. Q19 SLA 赔付敞口最大的客户

### 业务背景

COO Rafael Duarte 收到了销售团队转来的一封投诉信. Cascade Vision Systems 是公司第三大客户, 签的是 RESERVED 长约, 合同里写明了可用性承诺. 他们在信里列举了 FY2026 内多次任务被中断的记录, 要求解释, 并且暗示续约时会重新谈价格.

Rafael 需要知道两件事: 这家客户被中断的实际情况是什么, 以及类似的敞口在其他客户身上有多大. 因为如果这是个普遍问题, 那就不只是一封投诉信的事, 而是续约季的系统性风险.

背景是: 参与需求响应意味着主动中断客户任务, 而 RESERVED 档位客户被中断要按合同赔付 SLA credit. 这笔钱一直被记在服务成本里, 从来没有和 DR 收入放在一起看过.

### 标签

聚合 + HAVING / 基础 / COO

### 解题思路

从 `curtailed_workload` 出发, join `compute_job` 拿客户名和合约档位, join `curtailment_action` 拿时间做财年过滤.

按客户加合约档位分组. 为什么要带上 `contract_tier`: 同一个客户可能同时有 RESERVED 和 ON_DEMAND 两种任务, 赔付率完全不同, 混在一起看不出问题在哪一类合约上.

`HAVING SUM(w.sla_credit_usd) > 0` 把 SPOT 档位的客户过滤掉. SPOT 合同明确写了可被抢占, 不产生赔付, 留在结果里只会干扰阅读. 注意这个条件必须写在 `HAVING` 而不是 `WHERE`, 因为它作用在聚合结果上.

`COUNT(DISTINCT w.id)` 和 `COUNT(DISTINCT j.id)` 分别是中断次数和涉及任务数, 两个数字都要, 因为一个任务可能被中断多次.

`avg_rollback_min` 这一列是解释性的: 它说明为什么有些客户的损失特别大.

### SQL

```sql
SELECT
    j.customer_name,
    j.contract_tier,
    COUNT(DISTINCT w.id)                         AS interruptions,
    COUNT(DISTINCT j.id)                         AS jobs_affected,
    ROUND(SUM(w.lost_gpu_hours), 0)              AS lost_gpu_hours,
    ROUND(SUM(w.opportunity_cost_usd), 0)        AS opportunity_cost_usd,
    ROUND(SUM(w.sla_credit_usd), 0)              AS sla_credit_usd,
    ROUND(AVG(w.checkpoint_rollback_minutes), 0) AS avg_rollback_min
FROM curtailed_workload w
JOIN compute_job j        ON j.id = w.compute_job_id
JOIN curtailment_action c ON c.id = w.curtailment_action_id
WHERE c.action_start >= '2025-07-01'
    AND c.action_start <  '2026-07-01'
GROUP BY j.customer_name, j.contract_tier
-- 条件作用在聚合结果上, 必须写 HAVING. SPOT 档位不产生赔付, 顺便过滤掉
HAVING SUM(w.sla_credit_usd) > 0
ORDER BY sla_credit_usd DESC
LIMIT 12;
```

### 预期结果与业务结论

十二行.

| customer_name | tier | interruptions | jobs_affected | lost_gpu_hours | opportunity_cost_usd | sla_credit_usd | avg_rollback_min |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| Cascade Vision Systems | RESERVED | 18 | 11 | 105,094 | 323,394 | 99,839 | 100 |
| Lumen Protein Systems | RESERVED | 30 | 14 | 93,537 | 288,083 | 88,860 | 91 |
| Ardent Robotics | RESERVED | 22 | 10 | 79,532 | 242,294 | 75,555 | 83 |
| Cobalt Therapeutics | RESERVED | 30 | 11 | 69,555 | 209,993 | 66,077 | 71 |
| Helix Frontier Labs | RESERVED | 24 | 10 | 65,791 | 199,729 | 62,501 | 65 |
| Ember Molecular | ON_DEMAND | 10 | 5 | 63,103 | 198,704 | 22,086 | 150 |

Cascade Vision 的投诉是有依据的. 他们在 FY2026 被中断 18 次, 涉及 11 个任务, 损失 10.5 万 GPU 小时, 我们赔了 9.98 万美元的 SLA credit.

但更值得 Rafael 注意的是第二个问题的答案: 这不是个别现象. 前十一名全是 RESERVED 客户, SLA 赔付合计约 62.5 万美元. 而 RESERVED 恰恰是签约期最长, 单价最低, 最需要维护的那批客户. 我们在用最重要客户的服务体验去换需求响应收入.

`avg_rollback_min` 那一列解释了损失的构成: 前几名客户的平均回滚时间在 65 到 100 分钟, 意味着他们跑的多是长 checkpoint 间隔的训练任务, 每次中断都要白算一个多小时.

把这个数字和 Q5 放在一起看要小心口径: 这 62.5 万美元的 SLA 赔付里, 只有 `curtailment_type = 'DR_EVENT'` 那一部分计入了 Q5 的成本侧, 经济性削减 (ECONOMIC) 与 4CP 削减产生的 SLA 赔付并不在 Q5 里. 换句话说, Q5 里的 DR 净收益已经很难看, 但它连这些客户的全部赔付都还没算全. 而 Q5 更没有计入的是续约风险, 那可能比赔付本身贵得多.

下一步动作: 两件事. 第一, 给 Cascade Vision 的回复不要只谈赔付, 直接告知我们已经决定调整 DR 策略, 并承诺 FY2027 把他们的任务从削减池里移出, 这比退钱更有价值. 第二, 在调度系统里加一条硬约束: RESERVED 档位的任务不进入 DR 削减候选池, 只有 ON_DEMAND 和 SPOT 可以被削. 这条约束会降低可削减容量, 需要和 Q5 的申报调整方案一起做容量测算.

---

## 22. Q20 削减决策由谁做, 做得对吗

### 业务背景

这是备忘录的收尾. Dana 需要在最后一节回答一个更根本的问题: 削减这件事本身, 我们做得对吗.

公司里有四类主体会下达削减指令: 自动调度系统按预设规则触发, Demand Response Manager 在收到 ISO 通知后人工决策, Grid Operations Specialist 负责 4CP 躲避, VP 本人在特殊情况下直接介入. 四类主体用的判断依据不同, 响应速度不同, 结果自然也不同.

Dana 想看的是: 按决策来源拆开, 每一类的达成率如何, 以及最关键的, 每一类削减在 "省下的电费" 和 "损失的算力" 之间是什么关系.

### 标签

文本匹配 + 聚合 / 中级 / VP of Energy Strategy

### 解题思路

以 `curtailment_action` 为主表, 按 `decision_made_by` 和 `curtailment_type` 两个维度分组.

算力成本要从 `curtailed_workload` 汇总上来. 这里必须先在子查询里按 `curtailment_action_id` 聚合成一行, 再 join 回主表. 如果直接 join 明细表再聚合, `curtailment_action` 的字段 (比如 `energy_cost_avoided_usd`) 会被重复计算, 一次削减动作打断了八个任务, 省下的电费就会被算八遍. 这是聚合查询里最经典的扇出错误.

达成率用 `achieved_reduction_mw / target_reduction_mw`, 分母套 `NULLIF` 防止除零.

`decision_made_by` 的过滤用 `LIKE` 做模式匹配. 这里其实可以用 `IN` 列出四个值, 用 `LIKE` 是因为这个字段存的是职位名称, 未来可能出现 "Senior Demand Response Manager" 这类变体, 模式匹配更稳健.

最后一列 `energy_side_net_usd` 是这道题的落点: 省下的电费减去损失的算力, 纯粹从这一次削减动作本身看划不划算.

### SQL

```sql
SELECT
    c.decision_made_by,
    c.curtailment_type,
    COUNT(*) AS actions,
    ROUND(AVG(c.achieved_reduction_mw / NULLIF(c.target_reduction_mw, 0)), 3) AS avg_attainment,
    ROUND(AVG(c.duration_minutes), 0)                   AS avg_duration_min,
    ROUND(AVG(c.market_price_at_action_usd_per_mwh), 2) AS avg_price_at_action,
    ROUND(SUM(c.energy_cost_avoided_usd), 0)            AS energy_avoided_usd,
    ROUND(COALESCE(SUM(wl.cost), 0), 0)                 AS compute_cost_usd,
    ROUND(SUM(c.energy_cost_avoided_usd) - COALESCE(SUM(wl.cost), 0), 0) AS energy_side_net_usd
FROM curtailment_action c
-- 必须先聚合成一行再 join. 直接 join 明细表会让 energy_cost_avoided_usd
-- 按被打断的任务数重复计算, 一次削减打断八个任务就会被算八遍
LEFT JOIN (
    SELECT curtailment_action_id,
        SUM(opportunity_cost_usd + sla_credit_usd) AS cost
    FROM curtailed_workload
    GROUP BY curtailment_action_id
) wl ON wl.curtailment_action_id = c.id
WHERE c.decision_made_by LIKE '%Manager%'
    OR c.decision_made_by LIKE '%Scheduler%'
    OR c.decision_made_by LIKE '%Specialist%'
    OR c.decision_made_by LIKE '%VP%'
GROUP BY c.decision_made_by, c.curtailment_type
ORDER BY actions DESC;
```

### 预期结果与业务结论

六行.

| decision_made_by | type | actions | avg_attainment | avg_price | energy_avoided_usd | compute_cost_usd | energy_side_net_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| Automated Scheduler | DR_EVENT | 52 | 0.964 | 94.71 | 88,912 | 1,847,692 | -1,758,780 |
| Automated Scheduler | ECONOMIC | 33 | 1.000 | 1,334.64 | 301,559 | 1,318,646 | -1,017,087 |
| Demand Response Manager | DR_EVENT | 31 | 0.947 | 83.25 | 41,434 | 874,304 | -832,870 |
| Grid Operations Specialist | 4CP_AVOIDANCE | 8 | 0.995 | 55.83 | 44,630 | 2,495,115 | -2,450,485 |
| Grid Operations Specialist | DR_EVENT | 9 | 0.941 | 75.04 | 18,413 | 363,371 | -344,958 |
| VP of Energy Strategy | DR_EVENT | 4 | 1.014 | 56.85 | 6,658 | 305,224 | -298,566 |

达成率这一列没什么可说的, 四类主体都在 0.94 到 1.01 之间, 执行层面没有问题.

有问题的是最后一列, 而且它揭示了一件之前没人系统看过的事: **所有类型的削减, 单看能源侧都是亏的**. 这不奇怪, 因为削减省下的是电费, 损失的是算力, 而算力的单位价值本来就远高于电力. 削减能不能成立, 从来不取决于省下的电费, 而取决于电费之外的那笔收入或者避免的那笔支出.

按这个标准逐类看:

DR 事件触发的削减, 能源侧净亏 324 万, 但它换来了 328 万的 DR 结算收入, 所以整体接近打平 (这就是 Q5 的结论). 4CP 躲避能源侧净亏 245 万, 但它避免了 205 万的输电费增量, 而且三次命中相对完全不做躲避的基准省下的钱远超这个数, 所以是划算的 (Q15).

真正站不住的是 `Automated Scheduler` 那一行的 `ECONOMIC`. 经济性削减没有任何结算收入, 也不避免任何输电费, 它唯一的收益就是省下的那 30.2 万美元电费. 而它的算力成本是 131.9 万美元. **净亏 101.7 万美元, 而且没有任何东西可以抵消**.

这条两年前配的规则, 逻辑是 "电价超过 240 美元每 MWh 就停机", 在当时可能是对的. 但那是在公司还以 HPC 托管为主的时候, 算力的单位价值低得多. 转向 AI 训练之后, GPU 小时的机会成本涨了好几倍, 而这条规则的阈值一直没动过.

反过来推算盈亏平衡点: 要让经济性削减划算, 电价必须高到让省下的电费覆盖算力损失. 按当前 ABI1 和 TPL1 的任务混合, 平均每 MW 削减一小时损失约 1,340 美元的算力, 而省下的电费是电价乘以 1 MWh. 也就是说触发阈值应该在 1,300 美元每 MWh 以上, 而不是 240.

下一步动作: 立刻把经济性削减的触发阈值从 240 调到 1,400 美元每 MWh, 这是一行配置改动, 预计 FY2027 能挽回约 90 万美元. 同时把这个阈值改成由 `internal_cost_usd_per_gpu_hour` 动态推导, 而不是写死一个常数, 这样商务侧调整 GPU 定价时阈值会自动跟着走. 这条建议单独列进备忘录的执行摘要, 因为它是全部二十道分析里投入产出比最高的一条.

---

## 23. 业务问题与查询映射

| 业务问题 | 对应查询 |
| :--- | :--- |
| Q1 需求响应到底赚不赚钱 | Q3, Q4, Q5, Q6, Q19, Q20 |
| Q2 报给 ISO 的削减量可信吗 | Q7, Q8 |
| Q3 风电 PPA 是资产还是负债 | Q9, Q10, Q11, Q18 |
| Q4 电费账单里能压的是哪一块 | Q1, Q2, Q12, Q13, Q17 |
| Q5 4CP 躲避失手代价多大 | Q14, Q15, Q16 |

二十道题跑完, 备忘录的五个结论就都有了证据. 按金额排, 优先级是这样的: 4CP 窗口放宽 (风险敞口 205 万), 经济性削减阈值调整 (可挽回 102 万), burn-in 测试时段调整 (可省 79 万), DR 承诺容量从训练园区转移到推理园区 (可改善 70 万), 风电 PPA 重议 (年化 109 万但需要谈判). 五条加起来, FY2027 的可改善空间在 500 万美元以上, 而全部五条的实施成本不到 60 万.
