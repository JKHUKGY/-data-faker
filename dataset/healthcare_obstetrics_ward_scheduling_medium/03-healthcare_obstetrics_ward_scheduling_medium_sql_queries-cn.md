# Healthcare - 妇产科病房调度 SQL 查询参考

> 业务背景 / 公司 / 行业 / 术语表: `01-healthcare_obstetrics_ward_scheduling_medium_business_context-cn.md`
> 表结构 / 字段 / DDL: `02-healthcare_obstetrics_ward_scheduling_medium_er_document-cn.md`
> 所有查询均兼容 **SQLite 3.x** (使用 `julianday()` 做日期算术)。
> 参考"当前时间" (`REFERENCE_DATE`) = `2026-02-13 08:00` (Demo 起点)。所有需要"今天"的地方都用这个**字面量日期**, 不用 `DATE('now')`, 以保证结果可重现。
> 数据库文件: `healthcare_obstetrics_ward_scheduling_medium.sqlite`

---

## 概述

### 这不是 BI 查询集,这是 POC 验收清单

本文档列出 **20 条业务问题导向的 SQL 查询**,目的**不**是覆盖通用 BI 场景,而是回答**乙方 (IT 咨询公司) 需要在 POC 演示当天向甲方 (妇产科连锁医院) 证明的具体业务问题**。

| 维度 | 本数据集 | 一般 BI 查询集 |
|------|---------|--------------|
| 数据规模 | ~500 行, POC 沙盘 | 数百万到上亿 |
| 用户角色 | 一线 Charge Nurse + Attending + 病房经理 (一两个人) | 高管 + 分析师 + 数据科学家 |
| 查询时机 | **实时操作时** (交班、找床、安排手术) | **回顾分析** (本季度趋势、KPI) |
| 查询目的 | 替代旧 CMS 的护士手动检索动作 | 决策支持 |
| 容错性 | **极低** — 漏掉一个高危患者就是医疗事故 | 中等 — 趋势能看就行 |

### 如何使用本文档

这份文档是写给**刚入职 Halcyon 的数据实习生**看的: 你已经读过 `01-..._business_context-cn.md` (知道公司、行业、5 个业务问题) 和 `02-..._er_document-cn.md` (知道表结构), 现在经理把这 20 条查询丢给你, 说"这周把它们走一遍"。请按下面的方式读:

1. **每条查询都是一次项目交接**, 固定五段式, 照着读就能学会一个真实分析师怎么思考一个问题:
   - **业务背景** — 谁在问、为什么问、答案用来做什么决策、为什么现在急 (绑定到业务问题 P1–P5)。
   - **类别 / 难度 / 业务角色** — 三个标签, 帮你判断这条 SQL 用到什么技术、有多难、对应哪个职位。
   - **解题思路** — 在你看到 SQL *之前*, 先讲清楚要碰哪些表、为什么用这种 join / 聚合 / 窗口函数、一行结果代表什么粒度、有哪些坑 (扇出、NULL、大小写)。这一段是本文档最重要的教学部分。
   - **SQL** — 可直接在数据库上运行的代码。日期用字面量 `'2026-02-13'`。
   - **预期结果说明 + 业务结论** — 结果长什么样 (行数、列义、关键量级), 以及拿到数字后**下一步做什么** (跑查询是分析的开始, 不是结束)。

2. **每条查询都能追溯到一个业务问题**。文末有「业务问题 → 查询」映射表。看不出一条查询对应哪个业务问题, 就回 `01` 文档对一下。

3. **SQL 是用来读和学的, 不只是执行**。重点理解 `解题思路` 里"为什么这么写", 比如为什么是 `LEFT JOIN` 而不是 `INNER JOIN`、为什么 census 要排除 `discharged`、为什么 LOS 口径统一从 `delivery_time` 起算。

4. **演示日, 护士不会看到 SQL**。她只会自然提问 (如 "Any beds open in labor?"), AI agent 在背后调用对应查询。本文档的价值是让甲方 IT 团队**事后审计**: 每条 AI 回答都对得上 schema 里的真实数据。

### 查询与 Demo 场景的对应关系

POC 演示日,乙方会带着甲方一线护士走 **5 个 demo 场景**。每个场景对应 2-5 条 SQL 查询。AI agent 不直接展示 SQL,但**底层依赖**这些查询作为工具 (tool calls) 来回答护士的口语提问。

| Demo 场景 | 涉及查询 |
|----------|---------|
| 1️⃣ Shift Handover 交班简报 | Q1, Q5, Q6, Q14 |
| 2️⃣ Room Availability 房间余量 | Q2, Q10, Q18 |
| 3️⃣ Length-of-Stay 出院预测 | Q9, Q13, Q17 |
| 4️⃣ High-Risk Alert 高危预警 | Q3, Q7, Q16 |
| 5️⃣ Order Scheduling 医嘱安排 | Q4, Q14, Q19 |
| (横向分析) | Q8, Q11, Q12, Q15, Q20 |

### 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 | Demo 场景 |
|---|------|---------|------|------|----------|
| 1 | 当前病房人口分布 (按 status) | Charge Nurse | Aggregation | Basic | 1 |
| 2 | 各类房间的床位余量 | Charge Nurse | Join | Basic | 2 |
| 3 | 当前在院的高危产妇清单 | Attending Physician | Join | Intermediate | 4 |
| 4 | 未来 48 小时内的计划手术 | OR Coordinator | Join | Basic | 5 |
| 5 | 临近分娩的产妇 (产程进展) | Charge Nurse | Window Function | Intermediate | 1, 2 |
| 6 | 未确认告警汇总 | Charge Nurse | Join | Basic | 1, 4 |
| 7 | 高危产妇血压趋势 | Attending Physician | Window Function | Advanced | 4 |
| 8 | 医护人员当前工作量 | Department Manager | Aggregation | Intermediate | 横向 |
| 9 | 按分娩方式的平均住院时长 | Quality Analyst | Aggregation | Intermediate | 3 |
| 10 | 各类房间的床位使用率 | Operations Manager | Subquery | Intermediate | 2 |
| 11 | 一周内即将到预产期的产妇 | Scheduling Coordinator | Date Analysis | Basic | 横向 |
| 12 | 当前住院产妇的保险结构 | Finance Analyst | Aggregation | Basic | 横向 |
| 13 | 产程时长分析 (按胎次 + 分娩方式) | Quality Analyst | CTE | Advanced | 3 |
| 14 | 班次排班覆盖报告 | Nurse Manager | Join | Intermediate | 1, 5 |
| 15 | 并发症 (complications) 分布 | Clinical Director | Aggregation | Intermediate | 横向 |
| 16 | 最近生命体征异常的产妇 | Clinical Nurse | Window + Filter | Intermediate | 4 |
| 17 | LOS 预测准确度 (predicted vs actual) | Quality Analyst | CTE | Advanced | 3 |
| 18 | 多胎妊娠跟踪 + NICU 余量 | MFM Specialist | Join + Subquery | Intermediate | 2, 4 |
| 19 | 各类医嘱的执行率 | Operations Analyst | Aggregation | Intermediate | 5 |
| 20 | 入院时段分布 (周几 × 班次) | Capacity Planner | Date Analysis | Intermediate | 横向 |

---

## 查询正文

### Q1: 当前病房人口分布 (按 status)

**业务背景:**
**Demo 场景 1 (Shift Handover) 的第一个动作。** 凌晨 7 点 night → day 换班,接班的 charge nurse 走到护士站第一句话就是: "*现在病房里有多少人?都在哪个阶段?*" 这条查询是**整个 POC 演示的开场白** — AI agent 必须在 1 秒内吐出准确的人头数,因为它决定了后续所有调度动作的基线 (baseline)。任何一个状态漏掉都会让接班护士措手不及。

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** Charge Nurse

**解题思路:**
只用 `admission` 一张表, 不需要 join。按 `status` 分组 `COUNT(*)`, 关键是 `WHERE status != 'discharged'` 把已出院的排除掉 (census 只数在院的)。`percentage` 列用 `SUM(COUNT(*)) OVER ()` 这种"聚合 + 窗口"混用拿到全局总数做分母, 一遍 GROUP BY 就能算出每个状态的占比——这是 SQLite 也支持的写法。最后用 `CASE` 把状态按产程先后 (admitted → … → ready_for_discharge) 排序, 而不是字母序, 让护士读起来符合临床流向。一行结果 = 一个在院状态及其人数。

```sql
-- 按 admission status 汇总当前在院产妇人数
SELECT
    status,
    COUNT(*) AS patient_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS percentage
FROM admission
WHERE status != 'discharged'
GROUP BY status
ORDER BY
    CASE status
        WHEN 'admitted' THEN 1
        WHEN 'in_labor' THEN 2
        WHEN 'delivered' THEN 3
        WHEN 'postpartum' THEN 4
        WHEN 'ready_for_discharge' THEN 5
    END;
```

**预期结果说明:**
返回 5 行 (跳过 `discharged`,本数据集另有 1 条 discharged 不计入),每行一个状态及人数。本数据集分布: 4 人 admitted, 4 人 in_labor, 2 人 delivered, 3 人 postpartum, 2 人 ready_for_discharge (合计 15 active)。`percentage` 列让护士直观看到产程瓶颈 — 比如 in_labor 占比过高意味着接下来 2-4 小时 OR 会忙。

---

### Q2: 各类房间的床位余量

**业务背景:**
**Demo 场景 2 (Room Availability) 的核心查询。** 急诊室刚通知:"有产妇宫缩 5 分钟一次,马上送过来了,有没有 labor room?" Charge nurse 需要 **3 秒内** 回答。旧 CMS 只显示总数,不区分 `cleaning` (清洁中,不能马上用) 和 `available` (真正可用)。本 POC 必须证明 AI 能正确**分辨这 4 个状态**,这是甲方一线护士最早提出的痛点。

**Category:** Join
**Difficulty:** Basic
**Business Role:** Charge Nurse

**解题思路:**
要把 `room` 和 `bed` 连起来 (`JOIN bed ON room.room_id = b.room_id`), 因为床位状态在 `bed` 表、房型在 `room` 表。按 `room_type` 分组后, 用 `COUNT(CASE WHEN b.status = 'xxx' THEN 1 END)` 这种"条件计数"把 4 种床位状态拆成 4 列——这是不写子查询就做行转列的常用手法。**故意不**把 `cleaning` / `maintenance` 合并进"不可用", 因为 charge nurse 需要单独看到 cleaning (再等 ~30 分钟就能用)。这里 JOIN 用 INNER 即可, 每张床必有所属房间, 不会丢行。一行结果 = 一种房型的床位状态全景。

```sql
-- 各类房间的床位状态分布
SELECT
    r.room_type,
    COUNT(CASE WHEN b.status = 'available' THEN 1 END) AS available_beds,
    COUNT(CASE WHEN b.status = 'occupied' THEN 1 END) AS occupied_beds,
    COUNT(CASE WHEN b.status = 'cleaning' THEN 1 END) AS cleaning_beds,
    COUNT(CASE WHEN b.status = 'maintenance' THEN 1 END) AS maintenance_beds,
    COUNT(*) AS total_beds
FROM room r
JOIN bed b ON r.room_id = b.room_id
GROUP BY r.room_type
ORDER BY r.room_type;
```

**预期结果说明:**
5 行,对应 5 种 room_type (`labor` / `delivery` / `postpartum` / `nicu` / `triage`)。Demo 当天 labor room 通常已满,需要看 `cleaning_beds` 判断 ~30 分钟后能否腾出。`postpartum` 一般有余量,可以容纳从 delivery 转过来的产妇。

> 注意: 这条查询**故意**不把 `cleaning + maintenance` 合并到"不可用"里,因为 charge nurse 需要看到 "再等 20 分钟就能用一张" 的信息来调度。

---

### Q3: 当前在院的高危产妇清单

**业务背景:**
**Demo 场景 4 (High-Risk Alert) 的开场。** 主治医师 (attending) 早晨查房前,要拿到一份**今天必须重点关注**的产妇名单。高危分类来自 `ob_profile.risk_level = 'high'`,触发条件包括: 高龄产妇 / 多胎 / 早产 / 既往剖宫产做 VBAC / 多种并发症。这条查询是 attending 查房路径规划的输入 — 沿着 gestational_weeks 升序走 (早产风险大的优先),减少来回跑。

**Category:** Join
**Difficulty:** Intermediate
**Business Role:** Attending Physician

**解题思路:**
从 `admission` 出发, INNER JOIN `patient` 和 `ob_profile` 拿人口学与临床信息 (这两者必然存在), 再 **LEFT JOIN** `bed` 和 `room` 拿位置。位置用 LEFT 是因为有的在院产妇 `current_bed_id` 可能为空 (如刚进 triage 还没分床), 用 INNER 会把她们漏掉——漏掉一个高危产妇就是事故。过滤条件 `status != 'discharged'` (只看在院) + `risk_level = 'high'`。按 `gestational_weeks ASC` 排序, 让孕周最小 (早产风险最大) 的排最前, 给 attending 规划查房路径。一行 = 一位当前在院的高危产妇。

```sql
-- 当前在院的所有高危产妇及其位置 + 并发症
SELECT
    p.name AS patient_name,
    p.age,
    ob.risk_level,
    ob.gestational_weeks,
    ob.fetus_count,
    ob.complications,
    a.status AS current_status,
    r.room_number,
    b.bed_label
FROM admission a
JOIN patient p ON a.patient_id = p.patient_id
JOIN ob_profile ob ON a.ob_id = ob.ob_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE a.status != 'discharged'
    AND ob.risk_level = 'high'
ORDER BY ob.gestational_weeks ASC;
```

**预期结果说明:**
~4-6 行 (idx2 / idx3 / idx4 三例被**确定性**置为高危,另有随机抽样命中的高危若干,本数据集实际 6 例)。按 `gestational_weeks ASC` 排序,**最早出现的是 34.2 周的双胎** (idx4, 带 preterm_risk),其后是两例血压上升的高危产妇 (带 Preeclampsia / IUGR 等)。`complications` 列是 JSON 数组形式,attending 一眼能看到具体并发症类型,决定要不要请 MFM (Maternal-Fetal Medicine) 会诊。

---

### Q4: 未来 48 小时内的计划手术

**业务背景:**
**Demo 场景 5 (Order Scheduling) 的核心。** OR (Operating Room) coordinator 每天早 7 点排今日 + 明日的手术。她需要看: 几点几分? 哪个产妇? 哪间 OR? 主刀谁? 麻醉谁? 这条查询直接喂给 OR coordinator 的早晨简报,**未来 POC 会扩展成自动识别冲突** (比如同一时间两台剖宫产排了同一间 delivery room)。

**Category:** Join
**Difficulty:** Basic
**Business Role:** OR Coordinator

**解题思路:**
以 `medical_order` 为主表, JOIN `admission` → `patient` 拿产妇姓名, JOIN `provider` 拿主刀 / 负责人, 再 **LEFT JOIN** `room`。房间用 LEFT 是因为有些医嘱 (如 induction) 不绑 OR, `assigned_room_id` 为 NULL, 用 INNER 会把它们漏掉。时间窗用两个**字面量**边界 `scheduled_time >= '2026-02-13 08:00:00' AND < '2026-02-15 08:00:00'` 框住"未来 48 小时", 不用 `DATE('now')` 以保证 demo 可重现。`status = 'scheduled'` 只取还没执行的。一行 = 一台计划中的手术 / 操作。

```sql
-- 未来 48 小时内的 scheduled 医嘱 (剖宫产 / 引产 / 等)
SELECT
    o.scheduled_time,
    o.order_type,
    o.priority,
    p.name AS patient_name,
    r.room_number,
    prov.name AS assigned_provider,
    o.notes
FROM medical_order o
JOIN admission a ON o.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN room r ON o.assigned_room_id = r.room_id
JOIN provider prov ON o.assigned_provider_id = prov.provider_id
WHERE o.status = 'scheduled'
    AND o.scheduled_time >= datetime('2026-02-13 08:00:00')
    AND o.scheduled_time < datetime('2026-02-15 08:00:00')
ORDER BY o.scheduled_time;
```

**预期结果说明:**
~2 行 (明天 09:00 的 c_section + 明天 14:00 的 induction,数据集精心安排)。c_section 必须有 `assigned_room_id` 指向 delivery 类型房间; induction 通常在 labor room 就地做,可以 NULL。priority 默认 `routine`,POC 后续可扩展 emergency (即来即排)。

> 注: 真实临床场景里 `datetime('now')` 是动态的,但本 POC 用固定 reference time 让 demo 可重现。

---

### Q5: 临近分娩的产妇 (产程进展)

**业务背景:**
**Demo 场景 1 (交班) + 场景 2 (房间余量) 都用到。** Charge nurse 需要预测: **接下来 2 小时内哪几张 labor room 会腾出来?** 临床经验是: 宫口 ≥ 8 cm + 胎膜已破 ≈ 1-2 小时内娩出。本查询取每位 in_labor 产妇的**最新一条** labor_progress,按宫口降序排列。AI agent 会用结果反推: "Emily 现在 8 cm 了,她那张 L-202 大概 10:00 能腾出来给 ER 那个新来的"。

**Category:** Window Function
**Difficulty:** Intermediate
**Business Role:** Charge Nurse

**解题思路:**
难点是每位产妇有多条 `labor_progress`, 我们只要"最新一条"。标准做法是用窗口函数 `ROW_NUMBER() OVER (PARTITION BY admission_id ORDER BY recorded_at DESC)` 给每位产妇的记录按时间倒序编号, 外层 `WHERE rn = 1` 取最新那条。拿到最新内诊后 JOIN 回 `admission` / `patient`, 再 LEFT JOIN `bed` / `room` 拿位置 (床可能为空)。只保留 `status IN ('admitted','in_labor')` (还没生的), 按 `cervical_dilation_cm DESC` 排序——宫口最大的最接近分娩, 排最前。用 CTE + 窗口比相关子查询更清晰、更快。一行 = 一位待产产妇的最新产程。

```sql
-- 每位住院产妇最新的产程进展,按宫口降序
WITH latest_progress AS (
    SELECT
        lp.*,
        ROW_NUMBER() OVER (
            PARTITION BY lp.admission_id
            ORDER BY lp.recorded_at DESC
        ) AS rn
    FROM labor_progress lp
)
SELECT
    p.name AS patient_name,
    r.room_number,
    lp.cervical_dilation_cm,
    lp.station,
    lp.membrane_status,
    lp.recorded_at AS last_check,
    a.status
FROM latest_progress lp
JOIN admission a ON lp.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE lp.rn = 1
    AND a.status IN ('admitted', 'in_labor')
ORDER BY lp.cervical_dilation_cm DESC;
```

**预期结果说明:**
~5-8 行。排在第一的应是宫口 8 cm 左右 + ruptured 的产妇 (1-2 小时内分娩); 排在末尾的是宫口 1-2 cm + intact 的 admitted 产妇 (8-12 小时还不会生)。

---

### Q6: 未确认告警汇总

**业务背景:**
**Demo 场景 1 交班的最严肃环节。** 下班的护士必须把所有**未确认的 alert** 交给接班的护士,不能漏。每条 alert 代表一个**可能影响产妇/胎儿安全**的事件,critical 级别要求即刻 page (呼叫) attending。本数据集 demo 时刻有 2 条 high_bp warning 未确认 (落在 idx2 / idx3),1 条 preterm_risk 已被护士确认 — 这条查询应该只返回前两条。

**Category:** Join
**Difficulty:** Basic
**Business Role:** Charge Nurse

**解题思路:**
以 `alert` 为主表, JOIN `admission` / `patient` 拿人, LEFT JOIN `bed` / `room` 拿位置 (床可能为空)。核心过滤是 `acknowledged = 0`——SQLite 把 boolean 存成 0/1, 写 `= 0` 而不是 `= false`。排序用 `CASE al.severity WHEN 'critical' THEN 1 ELSE 2 END` 把 critical 顶到最前 (severity 是字符串, 不能直接排出"严重在前"), 同级再按 `triggered_at DESC` 最新优先。一行 = 一条待护士确认的告警。本快照只有 2 条未确认 high_bp, 那条已确认的 preterm_risk 不会出现。

```sql
-- 所有未确认告警 + 产妇位置 + 严重等级排序
SELECT
    al.alert_type,
    al.severity,
    al.message,
    al.triggered_at,
    p.name AS patient_name,
    r.room_number,
    b.bed_label,
    a.status AS patient_status
FROM alert al
JOIN admission a ON al.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE al.acknowledged = 0
ORDER BY
    CASE al.severity WHEN 'critical' THEN 1 ELSE 2 END,
    al.triggered_at DESC;
```

**预期结果说明:**
2 行 (本数据集精心控制),都是 high_bp warning。message 字段会有 "Blood pressure trending upward: 125 → 131 → 137 → 143 mmHg systolic" 这种叙述性内容,直接展示给护士看,不需要再去查 vital_sign。如果出现 critical,POC 后续可叠加 "自动 page attending" 动作。

---

### Q7: 高危产妇血压趋势

**业务背景:**
**Demo 场景 4 (High-Risk Alert) 的"AI 比单点阈值更聪明"证明题。** 旧 CMS 只在某次测量 BP ≥ 140 时报警,**漏掉了缓慢上升趋势**这种早期妊娠期高血压综合征 (PIH/Preeclampsia) 的征兆。POC 要证明 AI 能识别 "125 → 131 → 137 → 143" 这种**连续上升**模式,即使每一次单独看都不算 critical。本查询用 `LAG()` 算每次与上次的差值,展示给 attending 看完整轨迹。

**Category:** Window Function
**Difficulty:** Advanced
**Business Role:** Attending Physician

**解题思路:**
这是"趋势识别"题, 关键是把每位产妇相邻两次 BP 读数放到同一行做差。用窗口函数 `LAG(bp_systolic) OVER (PARTITION BY admission_id ORDER BY recorded_at)` 取"上一条"读数, 外层算 `bp_systolic - prev_systolic` 就是变化量。CTE `bp_readings` 先把 LAG 算好, 外层再 JOIN 人 / 房并用 `CASE` 贴阈值标签 (CRITICAL / WARNING / Normal-but-watch)。`WHERE bp_systolic >= 130 OR bp_diastolic >= 85` 把明显正常的低读数滤掉, 聚焦需要盯的轨迹。一行 = 一位产妇的一次 BP 读数 + 与上次的差值。`systolic_change` 连续为正即上升趋势——这正是单点阈值法看不出的早期征兆。

```sql
-- 血压时间序列 + 与上次的差值 + 阈值分类
WITH bp_readings AS (
    SELECT
        vs.admission_id,
        vs.recorded_at,
        vs.bp_systolic,
        vs.bp_diastolic,
        LAG(vs.bp_systolic) OVER (
            PARTITION BY vs.admission_id ORDER BY vs.recorded_at
        ) AS prev_systolic,
        LAG(vs.bp_diastolic) OVER (
            PARTITION BY vs.admission_id ORDER BY vs.recorded_at
        ) AS prev_diastolic
    FROM vital_sign vs
)
SELECT
    p.name AS patient_name,
    r.room_number,
    br.recorded_at,
    br.bp_systolic,
    br.bp_diastolic,
    br.bp_systolic - br.prev_systolic AS systolic_change,
    CASE
        WHEN br.bp_systolic >= 160 THEN 'CRITICAL'
        WHEN br.bp_systolic >= 140 THEN 'WARNING'
        ELSE 'Normal-but-watch'
    END AS bp_status
FROM bp_readings br
JOIN admission a ON br.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE br.bp_systolic >= 130 OR br.bp_diastolic >= 85
ORDER BY p.name, br.recorded_at;
```

**预期结果说明:**
~6-10 行 (只取那位埋点的高 BP 产妇的全部 vital 记录)。`systolic_change` 连续为正即趋势上升 — POC 评审会盯着这一列看 AI 是否能识别。

---

### Q8: 医护人员当前工作量

**业务背景:**
**横向支持型查询。** 部门经理 (Department Manager) 早晨例会要看: 哪个 attending / nurse 名下产妇最多?有没有人手忙脚乱 (overload) 或闲着 (underutilized)?POC 验证 AI 能正确按 attending + primary_nurse 两个字段聚合。

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Department Manager

**解题思路:**
一个 provider 既可能是 `attending_provider_id` 又可能是 `primary_nurse_id`, 所以 JOIN 条件用 `OR` 把两种角色都算进负载。从 `provider` 出发 **LEFT JOIN** `admission` (有的医护此刻名下没产妇, 用 INNER 会让他们消失), 再 LEFT JOIN `ob_profile` 拿 risk_level。`WHERE is_active = 1 AND (a.status IS NULL OR a.status != 'discharged')`——注意 LEFT JOIN 后未匹配行的 `status` 是 NULL, 必须显式 `IS NULL` 放行, 否则 `!= 'discharged'` 对 NULL 求值为假会把这些空闲医护误删。`COUNT(DISTINCT a.admission_id)` 防止 OR 连接的重复计数。一行 = 一位在岗医护及其当前负载。

```sql
-- 每位医护人员当前主管的产妇数 + 其中高危人数
SELECT
    prov.name AS provider_name,
    prov.role,
    COUNT(DISTINCT a.admission_id) AS current_patients,
    SUM(CASE WHEN ob.risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_patients
FROM provider prov
LEFT JOIN admission a ON (
    a.attending_provider_id = prov.provider_id
    OR a.primary_nurse_id = prov.provider_id
)
LEFT JOIN ob_profile ob ON a.ob_id = ob.ob_id
WHERE prov.is_active = 1
    AND (a.status IS NULL OR a.status != 'discharged')
GROUP BY prov.provider_id, prov.name, prov.role
ORDER BY prov.role, current_patients DESC;
```

**预期结果说明:**
~15 行 (所有 active provider)。Attending 通常每人 3-4 人 in charge, nurse 每人 2-3 人。如果某护士有 4 个 high_risk,而另一个护士只有 1 个 low-risk,manager 会重新分配。

---

### Q9: 按分娩方式的平均住院时长

**业务背景:**
**Demo 场景 3 (LOS 预测) 的对标基线。** 临床经验 LOS: 顺产 24-48h, 剖宫产 72-96h。Quality Analyst 用这条查询**校验 AI 模型的预测值是否落在合理区间内**。如果 AI 把剖宫产预测成 40 小时,说明 model 没识别 delivery_method = c_section。

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Quality Analyst

**解题思路:**
只用 `admission` 一张表。按 `delivery_method_actual` 分组——用**实际**分娩方式而非 planned, 避免"计划顺产转急诊剖宫产"被错归到 vaginal。`avg_predicted` 直接对 `predicted_los_hours` 求平均; `avg_actual` 用 `(julianday(actual_discharge_time) - julianday(delivery_time)) * 24` 算实际产后小时数, 但只有已出院的才有 `actual_discharge_time`, 故包在 `CASE WHEN ... IS NOT NULL` 里 (没出院的不参与实际均值)。**口径统一**: 预测与实际都从 `delivery_time` 起算的产后时长才可比。一行 = 一种实际分娩方式 (vaginal / c_section) 的 LOS 对标。

```sql
-- 按实际分娩方式比较“预测产后 LOS” vs “实际产后 LOS”
-- 口径统一: 二者均从 delivery_time 起算 (predicted_los_hours 即产后时长)
SELECT
    a.delivery_method_actual AS delivery_method,
    COUNT(*) AS delivered_count,
    ROUND(AVG(a.predicted_los_hours), 1) AS avg_predicted_postpartum_los_hours,
    ROUND(AVG(
        CASE WHEN a.actual_discharge_time IS NOT NULL
            THEN (julianday(a.actual_discharge_time) - julianday(a.delivery_time)) * 24
        END
    ), 1) AS avg_actual_postpartum_los_hours,
    SUM(CASE WHEN a.actual_discharge_time IS NOT NULL THEN 1 ELSE 0 END) AS discharged_count
FROM admission a
WHERE a.delivery_method_actual IS NOT NULL
GROUP BY a.delivery_method_actual
ORDER BY avg_predicted_postpartum_los_hours DESC;
```

**预期结果说明:**
~2 行 (实际分娩方式只会是 `vaginal` / `c_section` —— VBAC 是 *planned* 类别,真分娩时落地为顺产或剖宫产,**不会**作为 actual 出现)。c_section 的预测产后 LOS (72-96h) 明显高于 vaginal (24-48h)。`avg_actual_postpartum_los_hours` 仅对**已出院** admission 有值 (本快照 c_section 有 1 条 discharged,实际产后 LOS ≈ 84h,与预测接近)。**口径已统一为产后时长 (从 delivery 起算)**,不再把"产前在院时间"混入均值,也不再拿"总时长"去对标"产后预测"。

---

### Q10: 各类房间的床位使用率

**业务背景:**
**支持 Demo 场景 2 的扩展。** 运营经理 (Operations Manager) 关心结构性问题: labor room 是不是长期 > 85% 占用 (说明产能瓶颈, 该扩床)? postpartum 是不是 < 60% 利用率 (说明过度配置)?POC 演示 AI 能用单一数据源跑出运营级 KPI。

**Category:** Subquery / Aggregation
**Difficulty:** Intermediate
**Business Role:** Operations Manager

**解题思路:**
与 Q2 同源, 都从 `bed JOIN room` 出发, 但这里算"率"。`occupied_beds` 用条件求和 `SUM(CASE WHEN b.status='occupied' THEN 1 ELSE 0 END)`, 除以 `COUNT(*)` 得 `utilization_pct`——乘 `100.0` (带小数点) 强制浮点除法, 否则 SQLite 整数除会截断成 0。`available_soon` 把 `available` 和 `cleaning` 一起算 (cleaning ~30 分钟后可用), 是给 charge nurse 的实用口径。按 `utilization_pct DESC` 排序, 让最紧张的房型 (通常 labor) 排最前, 暴露产能瓶颈。一行 = 一种房型的占用率画像。

```sql
-- 各类房间的占用率 + 即将可用数 (含 cleaning)
SELECT
    r.room_type,
    COUNT(*) AS total_beds,
    SUM(CASE WHEN b.status = 'occupied' THEN 1 ELSE 0 END) AS occupied_beds,
    ROUND(
        SUM(CASE WHEN b.status = 'occupied' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS utilization_pct,
    SUM(CASE WHEN b.status IN ('available', 'cleaning') THEN 1 ELSE 0 END) AS available_soon
FROM bed b
JOIN room r ON b.room_id = r.room_id
GROUP BY r.room_type
ORDER BY utilization_pct DESC;
```

**预期结果说明:**
5 行,labor 类型 utilization_pct 通常最高 (~80-100%),NICU 因为本数据集只有少数早产场景一般偏低 (~25%)。`available_soon` 把 cleaning 算进来 — 这是给 charge nurse 看"30 分钟后能用多少"的实用数字。

---

### Q11: 一周内即将到预产期的产妇

**业务背景:**
**调度员 (Scheduling Coordinator) 的预约视图。** 妇产科与门诊不同,产妇并不全是"到期才来",有些是**预约入院引产 / 剖宫产**,有些会突然临产。Scheduling Coordinator 拿到这份名单后会逐个打电话确认:"您预约的是 9 号上午 9 点引产,确认吗?"。高危的还会安排专门床位预留。

**Category:** Date Analysis
**Difficulty:** Basic
**Business Role:** Scheduling Coordinator

**解题思路:**
从 `patient JOIN ob_profile` 拿预产期, 难点是"排除已住院的"。用 **LEFT JOIN admission ... AND a.status != 'discharged'** 再 `WHERE a.admission_id IS NULL`——这是经典的"反连接 (anti-join)"写法, 只保留在 admission 里找不到在院记录的产妇。注意那个 `status != 'discharged'` 条件必须写在 `ON` 里而不是 `WHERE`, 否则 LEFT JOIN 会退化成 INNER JOIN, anti-join 就失效。日期窗用 `edd BETWEEN '2026-02-13' AND date('2026-02-13','+7 days')`; `days_until_due` 用 `julianday` 差值算剩余天数。一行 = 一位一周内到期、当前未住院的产妇。

```sql
-- EDD 在未来 7 天内 + 尚未住院的产妇
SELECT
    p.name AS patient_name,
    p.phone,
    ob.edd AS due_date,
    ob.gestational_weeks,
    ob.planned_delivery_method,
    ob.risk_level,
    ob.fetus_count,
    ROUND(julianday(ob.edd) - julianday('2026-02-13'), 1) AS days_until_due
FROM patient p
JOIN ob_profile ob ON p.patient_id = ob.patient_id
LEFT JOIN admission a ON p.patient_id = a.patient_id AND a.status != 'discharged'
WHERE a.admission_id IS NULL
    AND ob.edd BETWEEN date('2026-02-13') AND date('2026-02-13', '+7 days')
ORDER BY ob.edd;
```

**预期结果说明:**
~12-14 行 (本数据集实测约 13 行)。`edd` 由 `gestational_weeks` 确定性推导,孕周 ~39-40 周的产妇其 EDD 正好落在未来 7 天内,故命中数不低;再减去当前已住院的产妇 (`a.admission_id IS NULL` 过滤掉) 即为结果。预产期 ≤ 3 天的算"高优先" — 这些产妇随时可能临产,scheduling 要做床位预留。high-risk + planned c_section 的必须提前确认 OR 时间。

---

### Q12: 当前住院产妇的保险结构

**业务背景:**
**财务分析师 (Finance Analyst) 的 payer mix 视图。** 美国医疗对**保险类型**敏感: Medicaid 报销周期长但量大, commercial 单次报销高但需要更细 documentation, self_pay 要预收押金。这条查询让财务部知道"本周末账单结构大致是什么样的"。Demo 中 attending 也可能用 — 因为 Medicaid 患者的 prenatal visit 频次往往不同。

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** Finance Analyst

**解题思路:**
从 `admission` JOIN `patient` (拿保险) 和 `ob_profile` (拿风险), 只看在院 (`status != 'discharged'`)。按 `insurance_type` 分组, `COUNT(*)` 数人, 用窗口 `SUM(COUNT(*)) OVER ()` 做分母算占比 (同 Q1 的聚合 + 窗口写法)。`high_risk_count` 用条件求和顺带统计每类保险里的高危人数。**大小写坑**: `insurance_type` 的取值 `Medicaid` 首字母大写 (美国政府项目专名), SQLite 比较大小写敏感, 写成 `'medicaid'` 会漏数据。一行 = 一种保险类型的在院产妇结构。

```sql
-- 当前在院产妇按 insurance_type 分布 + 高危人数
SELECT
    p.insurance_type,
    COUNT(*) AS patient_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS percentage,
    SUM(CASE WHEN ob.risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_count
FROM admission a
JOIN patient p ON a.patient_id = p.patient_id
JOIN ob_profile ob ON a.ob_id = ob.ob_id
WHERE a.status != 'discharged'
GROUP BY p.insurance_type
ORDER BY patient_count DESC;
```

**预期结果说明:**
3 行 (`commercial` / `Medicaid` / `self_pay`)。当前在院的比例与总产妇池接近 (~55/35/10)。如果 high_risk_count 在 Medicaid 中显著偏高,Finance 会和临床部门讨论是否需要额外的 case management 资源。

---

### Q13: 产程时长分析 (按胎次 + 分娩方式)

**业务背景:**
**Quality Analyst 的临床效率指标。** 经典临床知识: **初产妇 (P0)** 平均产程 12-18 小时,**经产妇 (P≥1)** 平均 6-8 小时。如果某段时期数据显著偏离,可能是临床路径有问题 (e.g. 过早 induction 反而拉长产程)。POC 用这个查询展示 AI 能做**多维度分组聚合** — para + planned_delivery_method 两维。

**Category:** CTE
**Difficulty:** Advanced
**Business Role:** Quality Analyst

**解题思路:**
先用 CTE `labor_times` 把每次住院的产程跨度算出来: `MIN(lp.recorded_at)` 作产程起点, `delivery_time` 作终点。这里用 **INNER JOIN labor_progress** 意味着只有真正产生过内诊记录的分娩才计入 (纯计划剖、尚未进产程的不算——有意取舍, 产程时长只对"产过程"有意义)。外层按 (`para = 0` 初产 / 否则经产) × `delivery_method_actual` 两维分组, 求产程小时数的 AVG / MIN / MAX, 用 `julianday` 差 × 24 换算成小时。一行 = 一个 (胎次 × 分娩方式) 组合的产程统计。注意小样本 + 场景驱动下不会复现教科书式初 / 经产差距, 此查询重在演示多维分组聚合能力。

```sql
-- 已分娩 admission 的产程时长 (第一次 labor_progress → delivery_time)
-- 按 (初产/经产) × 实际分娩方式 分组
WITH labor_times AS (
    SELECT
        a.admission_id,
        MIN(lp.recorded_at) AS labor_start,
        a.delivery_time,
        ob.para,
        a.delivery_method_actual
    FROM admission a
    JOIN labor_progress lp ON a.admission_id = lp.admission_id
    JOIN ob_profile ob ON a.ob_id = ob.ob_id
    WHERE a.delivery_time IS NOT NULL
    GROUP BY a.admission_id
)
SELECT
    CASE WHEN lt.para = 0 THEN 'First-time mom (初产)'
         ELSE 'Experienced mom (经产)' END AS parity,
    lt.delivery_method_actual,
    COUNT(*) AS deliveries,
    ROUND(AVG((julianday(lt.delivery_time) - julianday(lt.labor_start)) * 24), 1) AS avg_labor_hours,
    ROUND(MIN((julianday(lt.delivery_time) - julianday(lt.labor_start)) * 24), 1) AS min_labor_hours,
    ROUND(MAX((julianday(lt.delivery_time) - julianday(lt.labor_start)) * 24), 1) AS max_labor_hours
FROM labor_times lt
GROUP BY
    CASE WHEN lt.para = 0 THEN 'First-time mom (初产)'
         ELSE 'Experienced mom (经产)' END,
    lt.delivery_method_actual;
```

**预期结果说明:**
~3-5 行。度量用**实际**分娩方式 (`delivery_method_actual`) 分组(而非 planned),避免"计划顺产转急诊剖宫产"被错归到 vaginal。

> ⚠️ **关于产程时长量级:** 上方业务背景引用的"初产 12-18h、经产 6-8h"是**真实临床 norm**,但本 POC 的产程跨度 = `delivery_time − MIN(recorded_at)`,而这两个时间点由各 admission 的**场景参数** (`hours_ago` / `delivered_hours_ago`) 决定,**与 `para` 无因果关系**。因此本 ~500 行沙盘里各组产程都落在 ~5-8h、**不会**复现教科书式的初/经产差距。这是**小样本 + 场景驱动**的必然结果,不是查询错误 —— 此查询的价值在于演示 **schema 已支持 para × 分娩方式的多维分组聚合**,真实 EMR 接入后才会显现统计规律。

> 注: 本查询用 INNER JOIN `labor_progress`,因此**纯计划性剖宫产 (尚未进入产程、无内诊记录) 不会出现** —— 例如本数据集 idx13"明日剖宫产"还在 admitted、未产生 labor_progress,故不计入;只有真正经历过产程的分娩才会被度量。这是有意取舍 (产程时长只对"产过程"有意义)。

---

### Q14: 班次排班覆盖报告

**业务背景:**
**Demo 场景 1 (交班) + 场景 5 (Order Scheduling) 都需要。** Nurse manager 要确认: 接下来 3 天每个班次都**齐人**吗?有没有班次少了 anesthesiologist? 如果第二天 09:00 排了剖宫产但麻醉师那天 day 班是空的, POC 必须能识别这种**资源缺口**。

**Category:** Join
**Difficulty:** Intermediate
**Business Role:** Nurse Manager

**解题思路:**
`shift JOIN provider` 后按 (`shift_date`, `shift_type`) 分组, 每个班次一行。用 `GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'xxx' THEN p.name END)` 把同班次同角色的人名拼成一串——CASE 在分组内只挑某个角色的人名, GROUP_CONCAT 再聚合成名单。同时用 `COUNT(DISTINCT CASE WHEN p.role = 'xxx' THEN p.provider_id END)` 数每种角色人数, 用来核对是否齐编 (attending ≥ 1, day 护士 3 / night 2)。若 anesthesiologist 列为 NULL 说明该班没排麻醉师, 该班的剖宫产 / epidural 要标红 (P5 的资源缺口)。一行 = 一个班次的花名册 + 角色配置。

```sql
-- 每个班次的医护花名册 + 每种角色人数
SELECT
    s.shift_date,
    s.shift_type,
    GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'attending' THEN p.name END) AS attendings,
    GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'nurse' THEN p.name END) AS nurses,
    GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'anesthesiologist' THEN p.name END) AS anesthesiologists,
    COUNT(DISTINCT CASE WHEN p.role = 'attending' THEN p.provider_id END) AS attending_count,
    COUNT(DISTINCT CASE WHEN p.role = 'nurse' THEN p.provider_id END) AS nurse_count
FROM shift s
JOIN provider p ON s.provider_id = p.provider_id
GROUP BY s.shift_date, s.shift_type
ORDER BY s.shift_date, s.shift_type;
```

**预期结果说明:**
6 行 (3 天 × 2 班/天)。所有 attending_count ≥ 1 才算合格; nurse_count day 班 3 人 / night 班 2 人为标准。如果 anesthesiologist 列出现 NULL, 说明那个班次没安排麻醉师 — 任何在该班次的 c_section / epidural 都要被标红。

> 注: 本快照**每个班次都满编** (含 1 名 anesthesiologist),故不会出现"缺麻醉师"的正例 —— 这是 POC 满编设定的有意结果。此查询演示的是**识别资源缺口的能力 (schema 已支持)**,真实排班一旦出现空缺即会被本查询的 NULL 列暴露。

---

### Q15: 并发症 (complications) 分布

**业务背景:**
**Clinical Director 的产妇结构画像。** 全院的并发症 mix 影响**人员配置** (e.g. 高比例妊娠期糖尿病 → 需要 nutrition consult)、**药物储备** (e.g. Preeclampsia 多 → 多备 magnesium sulfate)、**与 MFM 科的协作频次**。本查询通过对 JSON 字段做 LIKE 匹配的方式提取频次 — POC 用的 SQLite JSON 支持有限,故用此 workaround。

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Clinical Director

**解题思路:**
`complications` 是 JSON 数组字符串, SQLite 的 JSON 支持有限, 这里用务实的 `LIKE` 模式匹配。先在 CTE 里把 JSON 的方括号引号清洗掉 (`REPLACE` 三连), 再对 10 种并发症各写一个 `SELECT ... COUNT(CASE WHEN ... LIKE '%name%' THEN 1 END)`, 用 `UNION ALL` 纵向拼成 10 行。`WHERE complications IS NOT NULL AND != 'null'` 先把没有并发症的过滤掉。按 `count DESC` 排序看哪种最常见。一行 = 一种并发症及其出现人次。生产环境会改用 PostgreSQL 的 JSONB 函数, SQLite 下 LIKE 是合理的 workaround。

```sql
-- 并发症频次 (通过 LIKE 模式匹配 JSON 字段)
WITH complication_list AS (
    SELECT
        ob.ob_id,
        ob.patient_id,
        REPLACE(REPLACE(REPLACE(ob.complications, '["', ''), '"]', ''), '", "', '|') AS complications_clean
    FROM ob_profile ob
    WHERE ob.complications IS NOT NULL AND ob.complications != 'null'
)
SELECT 'Gestational diabetes' AS complication,
       COUNT(CASE WHEN complications_clean LIKE '%Gestational diabetes%' THEN 1 END) AS count
FROM complication_list
UNION ALL
SELECT 'Gestational hypertension',
       COUNT(CASE WHEN complications_clean LIKE '%Gestational hypertension%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Preeclampsia',
       COUNT(CASE WHEN complications_clean LIKE '%Preeclampsia%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Placenta previa',
       COUNT(CASE WHEN complications_clean LIKE '%Placenta previa%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Oligohydramnios',
       COUNT(CASE WHEN complications_clean LIKE '%Oligohydramnios%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Polyhydramnios',
       COUNT(CASE WHEN complications_clean LIKE '%Polyhydramnios%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Intrauterine growth restriction',
       COUNT(CASE WHEN complications_clean LIKE '%Intrauterine growth restriction%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Previous cesarean section',
       COUNT(CASE WHEN complications_clean LIKE '%Previous cesarean section%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Advanced maternal age',
       COUNT(CASE WHEN complications_clean LIKE '%Advanced maternal age%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Anemia',
       COUNT(CASE WHEN complications_clean LIKE '%Anemia%' THEN 1 END)
FROM complication_list
ORDER BY count DESC;
```

**预期结果说明:**
10 行 (覆盖 §4.2 全部 10 种并发症,按出现频次降序)。Gestational hypertension / Preeclampsia / Anemia 因被埋点到高危住院上通常靠前;其余按随机抽样分布。覆盖**全部 10 种**才能让 Clinical Director 据此做不失真的培训重点与药品采购决策 (此前只统计 5 种会漏掉一半)。

> 注: 生产环境会改用 PostgreSQL JSONB 或 jsonb_array_elements;SQLite 限制下 LIKE 是务实之选。

---

### Q16: 最近生命体征异常的产妇

**业务背景:**
**Demo 场景 4 的护士视角版本。** 临床护士 (Clinical Nurse) 巡房前看 dashboard, 问: "**这一轮**有哪几位产妇 vital 异常?" 这条查询取每位 active admission 的**最新一条** vital_sign,只显示触发任一阈值的产妇,并按严重程度排序。护士据此规划巡房顺序。

**Category:** Window Function + Filter
**Difficulty:** Intermediate
**Business Role:** Clinical Nurse

**解题思路:**
与 Q5 同构: 用 `ROW_NUMBER() OVER (PARTITION BY admission_id ORDER BY recorded_at DESC)` 取每位产妇**最新一条** vital, 外层 `WHERE rn = 1`。然后用 `CASE` 按优先级 (BP-CRITICAL > BP-HIGH > FHR-ABNORMAL > FEVER) 打异常标签, 同时 `WHERE` 里再写一遍阈值条件, 只保留触发任一阈值的产妇 (正常的不显示)。`bp_systolic || '/' || bp_diastolic` 用 SQLite 的 `||` 把收缩 / 舒张压拼成 "140/90" 形式。`ORDER BY` 用 `CASE` 把最严重的顶到最前。一行 = 一位最新读数异常的在院产妇。标签优先级与阈值要与 ER §4.9 的告警阈值一致。

```sql
-- 每位住院产妇的最新一次 vital_sign + 异常标签
WITH recent_vitals AS (
    SELECT
        vs.*,
        ROW_NUMBER() OVER (PARTITION BY vs.admission_id ORDER BY vs.recorded_at DESC) AS rn
    FROM vital_sign vs
)
SELECT
    p.name AS patient_name,
    r.room_number,
    rv.recorded_at,
    rv.bp_systolic || '/' || rv.bp_diastolic AS blood_pressure,
    rv.fetal_heart_rate AS fhr,
    rv.temperature,
    CASE
        WHEN rv.bp_systolic >= 160 OR rv.bp_diastolic >= 110 THEN 'BP-CRITICAL'
        WHEN rv.bp_systolic >= 140 OR rv.bp_diastolic >= 90 THEN 'BP-HIGH'
        WHEN rv.fetal_heart_rate < 110 OR rv.fetal_heart_rate > 160 THEN 'FHR-ABNORMAL'
        WHEN rv.temperature >= 100.4 THEN 'FEVER'
        ELSE 'Normal'
    END AS concern
FROM recent_vitals rv
JOIN admission a ON rv.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE rv.rn = 1
    AND a.status != 'discharged'
    AND (rv.bp_systolic >= 140 OR rv.bp_diastolic >= 90
         OR rv.fetal_heart_rate < 110 OR rv.fetal_heart_rate > 160
         OR rv.temperature >= 100.4)
ORDER BY
    CASE
        WHEN rv.bp_systolic >= 160 THEN 1
        WHEN rv.bp_systolic >= 140 THEN 2
        ELSE 3
    END;
```

**预期结果说明:**
~1-3 行。本数据集有埋点的 BP-HIGH 产妇会稳出现。critical 行如果出现必须立即上报 attending。

---

### Q17: LOS 预测准确度 (predicted vs actual)

**业务背景:**
**POC 阶段甲方最关心的数字之一**: "你们的 AI 预测 LOS, 误差到底有多大?" Quality Analyst 拿这条查询的结果**直接答辩**: 平均误差 6 小时? 那基本可以用; 平均 24 小时? 那再调。本查询对**已出院 (有 actual_discharge_time)** 的 admission 计算 predicted vs actual 偏差。

**Category:** CTE
**Difficulty:** Advanced
**Business Role:** Quality Analyst

**解题思路:**
在 CTE `los_comparison` 里只取已出院 (`actual_discharge_time IS NOT NULL`) 且有预测值的 admission, 算实际产后 LOS = `(julianday(actual_discharge_time) - julianday(delivery_time)) * 24`。外层按 `delivery_method_actual` 分组, 算平均预测、平均实际、平均偏差 (`actual - predicted`)、平均绝对误差 (`ABS(...)`)、以及误差 ≤ 12h 的命中数。**预测与实际同口径** (都从 `delivery_time` 起算) 才能直接相减——这是相对旧版的关键修正, 旧版拿"总时长"减"产后预测"导致基准错位。一行 = 一种分娩方式的准确度报告。POC 阶段 discharged 样本少 (仅 1 条), 重在证明口径已对齐、schema 与 query 就绪。

```sql
-- 预测 vs 实际“产后 LOS”偏差 (仅已出院 admission, 口径统一从 delivery_time 起算)
WITH los_comparison AS (
    SELECT
        a.admission_id,
        a.delivery_method_actual,
        a.predicted_los_hours,
        ROUND((julianday(a.actual_discharge_time) - julianday(a.delivery_time)) * 24, 1) AS actual_postpartum_los_hours
    FROM admission a
    WHERE a.actual_discharge_time IS NOT NULL
        AND a.predicted_los_hours IS NOT NULL
        AND a.delivery_time IS NOT NULL
)
SELECT
    delivery_method_actual,
    COUNT(*) AS cases,
    ROUND(AVG(predicted_los_hours), 1) AS avg_predicted,
    ROUND(AVG(actual_postpartum_los_hours), 1) AS avg_actual,
    ROUND(AVG(actual_postpartum_los_hours - predicted_los_hours), 1) AS avg_variance,
    ROUND(AVG(ABS(actual_postpartum_los_hours - predicted_los_hours)), 1) AS avg_abs_error,
    SUM(CASE WHEN ABS(actual_postpartum_los_hours - predicted_los_hours) <= 12 THEN 1 ELSE 0 END) AS within_12hrs
FROM los_comparison
GROUP BY delivery_method_actual;
```

**预期结果说明:**
返回 **1 行** (本快照有 1 条 discharged c_section: 实际产后 LOS ≈ 84h vs 预测 72-96h,`avg_abs_error` 较小、`within_12hrs = 1`)。**预测与实际现在同口径** (都从 `delivery_time` 起算的产后时长),不再像旧版那样拿"总时长 (admit→discharge)"去减"产后预测"导致基准错位、也不再因 `actual_discharge_time` 全空而恒返回 0 行。POC 阶段 discharged 样本仍少 (仅 1 条),真实部署后才会积累统计有效的样本量。

> POC 答辩话术: "现在数据少,但 schema 与 query 都已就绪、口径已对齐 — 上线 2 周后就能跑出统计有效的准确度报告。"

---

### Q18: 多胎妊娠跟踪 + NICU 余量

**业务背景:**
**MFM (Maternal-Fetal Medicine) Specialist 的专项视图。** 双胎 / 三胎是产科最高警觉 — 早产率 60%+, 必须确保 **NICU 同时有空床**才能进 OR。本查询联合两件事: 全部多胎产妇清单 + 实时 NICU 余量。这条 query 也是 demo 4 的"AI 能同时看跨表"的证明。

**Category:** Join + Subquery
**Difficulty:** Intermediate
**Business Role:** MFM Specialist

**解题思路:**
主查询从 `ob_profile JOIN patient` 取全部多胎 (`fetus_count > 1`), LEFT JOIN `admission` (只取在院) → `bed` → `room` 拿当前位置 (多胎产妇可能还没入院, 故用 LEFT 不丢人)。NICU 余量用一个**标量子查询** `(SELECT COUNT(*) FROM bed JOIN room WHERE room_type = 'nicu' AND status = 'available')` 作为一列贴在每行上——它与外层无关联, 每行都是同一个全局数字, 这正是"同时看两件事 (多胎清单 + NICU 余量)"的需求。按孕周升序排, 早产风险大的在前。一行 = 一位多胎产妇 + 当前 NICU 可用床数。

```sql
-- 全部多胎妊娠 + 当前 NICU 可用床数 (作为标量子查询)
SELECT
    p.name AS patient_name,
    ob.fetus_count,
    ob.gestational_weeks,
    ob.risk_level,
    ob.planned_delivery_method,
    a.status AS admission_status,
    r.room_number,
    ob.complications,
    (SELECT COUNT(*) FROM bed b2
     JOIN room r2 ON b2.room_id = r2.room_id
     WHERE r2.room_type = 'nicu' AND b2.status = 'available') AS nicu_beds_available
FROM ob_profile ob
JOIN patient p ON ob.patient_id = p.patient_id
LEFT JOIN admission a ON ob.ob_id = a.ob_id AND a.status != 'discharged'
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE ob.fetus_count > 1
ORDER BY ob.gestational_weeks ASC;
```

**预期结果说明:**
~2-4 行 (按 ~3.5% 多胎率 + 1 例确定性埋点的 34.2 周双胎 idx4,50 个产妇约有 2-4 个多胎)。`nicu_beds_available` 是当前 NICU 真实可用床数;本快照 NICU 8 张床均空闲 (产妇本人不入 NICU、且本 POC 无 newborn 实体),故恒为 8 —— 演示时这意味着"双胎可安全进 OR"。真实部署中一旦 NICU 满 (= 0) 且有 34 周双胎在 in_labor,MFM 会立即与 NICU 协调转出。

---

### Q19: 各类医嘱的执行率

**业务背景:**
**Demo 场景 5 的追踪视图。** 运营分析师 (Operations Analyst) 关心: 多少 lab_test 真的在 scheduled_time 完成了? 多少 c_section 排了又取消 (overbook 表征)? 高 cancellation 率说明排班质量低; 长期 scheduled 不动说明执行瓶颈。

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Operations Analyst

**解题思路:**
只用 `medical_order` 一张表, 按 `order_type` 分组。用一组条件求和 `SUM(CASE WHEN status = 'xxx' THEN 1 ELSE 0 END)` 把 4 种状态 (completed / in_progress / scheduled / cancelled) 各数一列, `completion_rate` = completed / 总数 × 100.0 (带小数点避免整数除截断)。按 `total_orders DESC` 让量最大的医嘱类型排前。注意 scheduled 的 c_section / induction 是有意埋的"明日手术", 处于 scheduled 不算异常、不是执行瓶颈。一行 = 一种医嘱类型的状态分布 + 完成率。

```sql
-- 按 order_type 分组的状态分布 + 完成率
SELECT
    order_type,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
    SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) AS scheduled,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
    ROUND(
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS completion_rate
FROM medical_order
GROUP BY order_type
ORDER BY total_orders DESC;
```

**预期结果说明:**
~3-4 行 (本数据集约 **20 条** order, 主要是 lab_test ~14 + epidural ~4,外加明日 c_section/induction 各 1)。lab_test 多为 `completed`、epidural 为 `completed`/`in_progress`;c_section / induction 在 `scheduled` 状态 (未到执行时间, 这不是问题,是埋点)。

---

### Q20: 入院时段分布 (周几 × 班次)

**业务背景:**
**Capacity Planner 的长期排班视图。** 妇产科自然分娩的入院时间是**非随机**的 — 经验上夜间入院偏多 (宫缩规律后才会出发到医院),工作日 vs 周末分布也不同。Planner 用这条查询的结果**优化未来 3 个月的护士排班**: 如果周二 night 班入院多,就多排一名 nurse。

**Category:** Date Analysis
**Difficulty:** Intermediate
**Business Role:** Capacity Planner

**解题思路:**
只用 `admission JOIN ob_profile` (拿 risk_level)。用 SQLite 的 `strftime('%w', admit_time)` 取周几 (0 = 周日), `strftime('%H', ...)` 取小时, 再 `CAST(... AS INTEGER)` 转数字后用 `CASE` 分别映射成星期名和 3 段时段 (Day / Evening / Night)。按 (周几, 时段) 分组数入院量, 并用 `AVG(CASE WHEN risk_level = 'high' THEN 1.0 ELSE 0.0 END) * 100` 算每桶的高危占比。`ORDER BY` 里也用 `strftime` 数字保证周日到周六顺序正确。一行 = 一个 (周几 × 时段) 桶。注意这 3 段分桶是 capacity-planning 视角, 与运营的 2 班制 (见 ER §4.6) 是两套切分, 有意并存; 本数据集只 3 天, 真实环境要跑 3-6 个月才有统计意义。

```sql
-- 入院按周几 + 时段分桶
SELECT
    CASE CAST(strftime('%w', admit_time) AS INTEGER)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_of_week,
    CASE
        WHEN CAST(strftime('%H', admit_time) AS INTEGER) BETWEEN 7 AND 14 THEN 'Day Shift (7AM-3PM)'
        WHEN CAST(strftime('%H', admit_time) AS INTEGER) BETWEEN 15 AND 22 THEN 'Evening (3PM-11PM)'
        ELSE 'Night Shift (11PM-7AM)'
    END AS shift_period,
    COUNT(*) AS admission_count,
    ROUND(AVG(CASE WHEN ob.risk_level = 'high' THEN 1.0 ELSE 0.0 END) * 100, 1) AS high_risk_pct
FROM admission a
JOIN ob_profile ob ON a.ob_id = ob.ob_id
GROUP BY day_of_week, shift_period
ORDER BY
    CAST(strftime('%w', admit_time) AS INTEGER),
    CASE shift_period
        WHEN 'Day Shift (7AM-3PM)' THEN 1
        WHEN 'Evening (3PM-11PM)' THEN 2
        ELSE 3
    END;
```

**预期结果说明:**
~6-9 行 (本数据集只覆盖 3 天, 真实环境跑 3-6 个月才有统计意义)。POC 阶段这条查询主要是**展示 schema 已经支持**这种分析,而不是产出结论 — 这是给甲方看的 "未来扩展的钩子"。

> 注: 本查询的时段分桶用 3 段 (Day 7-14 / Evening 15-22 / Night 其余),这是 **capacity-planning 的分析视角**,与运营侧的 **2 班制** (day 07-19 / night 19-07,见 ER §4.6) 是两套不同的切分。二者并存是有意的:排班用 2 班,容量分析用更细的 3 段以发现晚间高峰。

---

## 查询类别汇总

| 类别 | 数量 | 查询编号 |
|------|------|---------|
| Aggregation | 6 | Q1, Q8, Q9, Q12, Q15, Q19 |
| Join | 6 | Q2, Q3, Q4, Q6, Q14, Q18 |
| Window Function | 3 | Q5, Q7, Q16 |
| Date/Time Analysis | 2 | Q11, Q20 |
| CTE / Subquery | 3 | Q10, Q13, Q17 |

## 业务角色覆盖

| 角色 | 数量 | 查询编号 |
|------|------|---------|
| Charge Nurse (一线总责护士) | 4 | Q1, Q2, Q5, Q6 |
| Attending Physician (主治) | 2 | Q3, Q7 |
| Clinical Nurse (临床护士) | 1 | Q16 |
| Department Manager / Nurse Manager | 2 | Q8, Q14 |
| OR Coordinator (手术室协调) | 1 | Q4 |
| Quality Analyst (质量) | 3 | Q9, Q13, Q17 |
| Operations Manager / Analyst | 2 | Q10, Q19 |
| Scheduling Coordinator | 1 | Q11 |
| Finance Analyst | 1 | Q12 |
| Clinical Director | 1 | Q15 |
| MFM Specialist | 1 | Q18 |
| Capacity Planner | 1 | Q20 |

## 难度分布

| 难度 | 数量 | 占比 |
|------|------|------|
| Basic | 6 | 30% |
| Intermediate | 11 | 55% |
| Advanced | 3 | 15% |

---

## POC 演示日的预期对话流

> 这是乙方设计的演示脚本骨架, 列出来便于读者理解 SQL 与 demo 之间的映射。

| 时刻 | 护士口语提问 (Demo 真实台词) | AI 调用的查询 |
|------|---------------------------|--------------|
| 07:05 | "Show me where everyone is right now." | Q1 |
| 07:08 | "Any beds open in labor?" | Q2 |
| 07:11 | "Who's about to deliver?" | Q5 |
| 07:14 | "Any alerts I should know about?" | Q6 |
| 07:18 | "Pull up the high-risk patient list for rounds." | Q3 |
| 07:22 | "What's Emily's BP doing — is it really trending up?" | Q7 |
| 07:30 | "OK, who delivers today? Any C-sections scheduled?" | Q4 |
| 07:35 | "Anesthesiology is on for the 9 AM C-section, right?" | Q14 |
| 09:45 | "Sarah delivered at 7:50 — when will she be ready to go home?" | Q9, Q17 (基线对比) |

---

## 备注

1. **日期函数**: 全部用 SQLite 的 `julianday()`,迁移到 PostgreSQL 时换成 `EXTRACT(EPOCH FROM ...) / 86400`。
2. **JSON 解析**: 用 LIKE workaround,因为 POC 在 SQLite。生产环境用 PostgreSQL JSONB 操作符。
3. **`datetime('now')` 替换为固定 reference time**: Demo 可重现,真实部署时换回 `'now'`。
4. **索引提示**: 本数据集 ~500 行,不需要索引。生产环境时,推荐至少在 `admission(status, admit_time)`、`vital_sign(admission_id, recorded_at)`、`labor_progress(admission_id, recorded_at)` 上建索引。
5. **POC 验收**: 乙方在演示日不需要让护士看到 SQL,而是让她**自然提问**, AI agent 在背后调用上述查询。本文档存在的目的是让甲方 IT 团队**事后审计**: 每一条 AI 回答都对得上 schema 中的真实数据。
