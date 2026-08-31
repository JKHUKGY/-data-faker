# 光纤焊接质量与成本控制数据集 SQL 查询参考

本文档配套 `telecom_equipment_fiber_splicing_quality_high` 数据集. 业务背景, 公司组织, 八个业务问题, 术语表请见 `01-telecom_equipment_fiber_splicing_quality_high_business_context-cn.md`. 表结构, 字段含义, 业务陷阱的 expected magnitude 请见 `02-telecom_equipment_fiber_splicing_quality_high_er_document-cn.md`.

`REFERENCE_DATE` 锚定 `2026-06-15`. 文档里的每一条 SQL 都把这一天作为字面量传入, 不用 `DATE('now')`, 保证多次运行结果一致.

---

## 1. 如何使用本文档

本文档是 Marcus (VP Operations) 在 kickoff 第二周交给你的 SQL 任务清单. 一共 20 条查询, 你这一周要把它们全部跑通, 并写一份 12 页 memo 把结论汇总给 CFO. 这 20 条查询不是为了练 SQL 语法, 是为了证明 (或证伪) 八个 cost-take-out hypothesis. 每一条对应一个具体的 dollar number, 每一条最后要回答 "下一步动作是什么".

每条查询有五个 beat:

第一, **业务背景**: 谁要这个数据, 为什么现在要, 答出来要做什么决定. 这是你 memo 里这一节的开场.

第二, **标签**: 查询类别 (聚合 / Join / 窗口函数 / CTE 等), 难度, 业务角色. 用于读者快速判断.

第三, **解题思路**: 在写 SQL 之前先想清楚要 join 哪些表, 怎么 join, 为什么是 LEFT 不是 INNER, group by 的粒度是什么, 是不是要用 CTE 或窗口函数. 这一段是你的师傅在指导你怎么思考, 不是 SQL 的逐行翻译.

第四, **SQL**: 真正的查询. 所有查询都已经在 SQLite 上验证可跑.

第五, **预期结果与下一步**: 期望看到的数据形状, 关键 magnitude, 以及拿到这个结果之后你 (作为 analyst) 要做什么动作.

每一条都映射回 01 文档里的 Q1 到 Q8. 文档末尾有一张映射表.

---

## 2. 查询索引

| 编号 | 标题 | 对应 Q | 业务角色 | 难度 |
|------|------|--------|----------|------|
| 1 | 焊接工序成本与质量等级总览 | Q1 | CFO + VP Operations | 基础 |
| 2 | Reject 成本按根因驱动拆解 | Q1 | VP Operations | 高级 |
| 3 | 月度 FPY 与 reject 率趋势 | Q1 | Production Manager | 中级 |
| 4 | 电极使用次数分桶 vs reject 率 | Q2 | Manufacturing Analyst | 中级 |
| 5 | 主动电极更换策略的 ROI 估算 | Q2 | VP Operations | 高级 |
| 6 | 各班次 reject 率与产量贡献 | Q3 | Production Manager | 基础 |
| 7 | 夜班 floating supervisor ROI | Q3 | VP Operations | 中级 |
| 8 | 技能等级 × 光纤规格 reject 交叉表 | Q4 | Production Manager | 中级 |
| 9 | Multi-core 重新排班的 ROI 估算 | Q4 | VP Operations | 高级 |
| 10 | 按客户 segment 的 spec compliance gap | Q5 | CFO + VP Sales | 中级 |
| 11 | 按客户实际 spec 重判后的成本节约 | Q5 | CFO | 高级 |
| 12 | AI 告警 outcome 与下游 reject 联动 | Q6 | QA Engineering Manager | 中级 |
| 13 | 告警 ignored 的班次切分与强制执行 ROI | Q6 | VP Operations | 高级 |
| 14 | 设备校准超期天数 vs reject 率 | Q7 | Production Manager | 基础 |
| 15 | 坏批次 MFG-2024-038 的质量影响范围 | Q8 | QA Engineering Manager | 中级 |
| 16 | 客户投诉到批次反查路径 | Q8 | QA Engineering Manager | 高级 |
| 17 | 设备维护优先级看板 | 运营 | Production Manager | 中级 |
| 18 | 每日产量, FPY, reject 率, 3 周移动平均 | 运营 | VP Operations | 高级 |
| 19 | QA 复核 vs operator 自评的偏差分析 | 运营 | QA Engineering Manager | 中级 |
| 20 | 操作员综合绩效排名 | 运营 | Production Manager | 高级 |

---

## 3. 查询 1: 焊接工序成本与质量等级总览

**业务背景**

CFO Linda Chen 在月度 BoD prep meeting 上要先看一张大图. 工厂 12 个月的总 splice 数, total cost, 各 grade 比例, 综合 reject rate, FPY. 她想知道 baseline 在哪里, 不要细节, 不要拆分. 这条查询的结果会变成你 memo 的第一张图. 这道题对应 Q1.

**标签**

类别: 聚合查询. 难度: 基础. 角色: CFO + VP Operations.

**解题思路**

只动 `splice_record` 一张表就够了, 不需要 join. attempt_count = 1 且 grade != Reject 即 first-pass yield. 用 SUM(CASE WHEN ...) 的写法把四档 grade 的计数同时算出来比起跑四次 COUNT 高效得多. 注意分母是 COUNT(\*), 不是 COUNT(splice_id), 因为 splice_id 是 NOT NULL PK, 两者等价但前者更清晰.

成本要从 `splice_attempt` 取, 用 SUM 直接得到 12 个月的工序总成本. splice_attempt 跟 splice_record 是 N:1 关系, 因为一根 splice 可能有多个 attempt, 所以 SUM 一定要在 attempt 这一层做, 不能 join 上 splice_record 后再 SUM 否则会重复计数.

**SQL**

```sql
WITH grade_stats AS (
    SELECT
        COUNT(*) AS total_splices,
        SUM(CASE WHEN final_grade = 'A' THEN 1 ELSE 0 END) AS grade_a,
        SUM(CASE WHEN final_grade = 'B' THEN 1 ELSE 0 END) AS grade_b,
        SUM(CASE WHEN final_grade = 'C' THEN 1 ELSE 0 END) AS grade_c,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS reject_count,
        SUM(CASE WHEN attempt_count = 1 AND final_grade != 'Reject' THEN 1 ELSE 0 END) AS first_pass_pass
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
cost_stats AS (
    SELECT SUM(total_cost_usd) AS total_cost_usd
    FROM splice_attempt
    WHERE attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
)
SELECT
    g.total_splices,
    g.grade_a,
    ROUND(g.grade_a * 100.0 / g.total_splices, 2) AS grade_a_pct,
    g.grade_b,
    ROUND(g.grade_b * 100.0 / g.total_splices, 2) AS grade_b_pct,
    g.grade_c,
    ROUND(g.grade_c * 100.0 / g.total_splices, 2) AS grade_c_pct,
    g.reject_count,
    ROUND(g.reject_count * 100.0 / g.total_splices, 2) AS reject_rate_pct,
    ROUND(g.first_pass_pass * 100.0 / g.total_splices, 2) AS first_pass_yield_pct,
    ROUND(c.total_cost_usd, 2) AS total_cost_usd,
    ROUND(c.total_cost_usd / g.total_splices, 4) AS avg_cost_per_splice_usd
FROM grade_stats g, cost_stats c;
```

**预期结果与下一步**

返回一行结果. 关键数字: 总 splice 数约 50,000, grade A 约 75%, grade B 约 18%, grade C 约 4.5%, reject 约 2.5%, FPY 约 88%, total_cost 约 $125K 到 $135K, avg_cost_per_splice 约 $2.50. 如果 FPY 低于 90% 或 reject rate 高于 3%, 说明工厂在行业里属于中下水平 (一流厂 FPY 95%+, reject 1% 以下), 后面 19 条查询要把这部分差距拆解到 driver 级.

---

## 4. 查询 2: Reject 成本按根因驱动拆解

**业务背景**

VP Operations Marcus 要在 Phase 1 kickoff 的 review meeting 上展示 "你的 8 个 hypothesis 各自值多少钱". 这是你向 CFO 提出预算的核心证据. 每一个 driver (电极磨损 / 班次 / 技能 × 多核 / 校准超期 / 坏批次 / 告警忽视) 要给出一个 dollar number, 加起来要接近 Q1 的 reject_total. 这是项目的 anchor query, 对应 Q1.

**标签**

类别: CTE + UNION ALL. 难度: 高级. 角色: VP Operations.

**解题思路**

每个 driver 都对应一个 splice 子集的"额外 reject" 估算. 例如电极磨损 driver: 用 electrode_count > 2000 的 splice 的 reject 数减去 baseline reject rate × 这批 splice 数, 差值就是"由电极磨损贡献的多出来的 reject". 这种 "actual - baseline" 是计量经济学里的 attributable risk 思路.

每一个 driver 都用同样的模式: filter 出归属此 driver 的 splice 子集 → 计算这个子集的 actual reject rate vs total baseline → 差值乘以子集大小 × 单位成本. 单位成本按业务背景的口径取 $13 per reject (物料 + 人工 + 设备折旧 + 客户失信摊销).

把 8 个 driver 的子查询都拼成一张表用 UNION ALL. 注意每个 driver 的 splice 集合不是互斥的 (一根 splice 可能同时是夜班 + 电极超寿命), 所以 driver-level dollar 加和会大于 total reject cost, 这是预期的; memo 里写的是"如果消除该 driver 这一类问题可挽回的金额", 而不是"对总 reject 的不重叠分摊".

**SQL**

```sql
WITH baseline AS (
    SELECT
        COUNT(*) AS total_splices,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS reject_rate
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
electrode_wear AS (
    SELECT
        'electrode_wear' AS driver,
        COUNT(DISTINCT sa.splice_id) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_attempt sa
    JOIN splice_record sr ON sa.splice_id = sr.splice_id
    WHERE sa.attempt_number = 1
      AND sa.equipment_electrode_count > 2000
      AND sa.attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
night_shift AS (
    SELECT
        'night_shift' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record
    WHERE shift_id = 'SH-N'
      AND completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
skill_mismatch AS (
    SELECT
        'skill_multicore_mismatch' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
    WHERE fs.mode_type = 'multi_core'
      AND o.skill_level IN ('junior', 'intermediate')
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
calibration_overdue AS (
    SELECT
        'calibration_overdue' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN equipment e ON sr.equipment_id = e.equipment_id
    WHERE julianday(sr.completed_ts) - julianday(e.last_calibration_date) > 90
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
bad_batch AS (
    SELECT
        'bad_batch_MFG_2024_038' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    WHERE fsp.batch_id = 'MFG-2024-038'
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
alert_ignored AS (
    SELECT
        'ai_alert_ignored' AS driver,
        COUNT(DISTINCT sr.splice_id) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN splice_attempt sa ON sr.splice_id = sa.splice_id
    JOIN quality_alert qa ON sa.attempt_id = qa.attempt_id
    WHERE qa.outcome = 'ignored'
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
combined AS (
    SELECT * FROM electrode_wear
    UNION ALL SELECT * FROM night_shift
    UNION ALL SELECT * FROM skill_mismatch
    UNION ALL SELECT * FROM calibration_overdue
    UNION ALL SELECT * FROM bad_batch
    UNION ALL SELECT * FROM alert_ignored
)
SELECT
    c.driver,
    c.subset_splices,
    c.subset_rejects,
    ROUND(c.subset_rejects * 100.0 / c.subset_splices, 2) AS subset_reject_rate_pct,
    ROUND(b.reject_rate * 100, 2) AS baseline_reject_rate_pct,
    -- 归因 reject 数: subset 实际 reject 减去按 baseline 应有的 reject
    ROUND(c.subset_rejects - c.subset_splices * b.reject_rate, 0) AS attributable_rejects,
    -- 按 $13 / reject 折算成年化金额
    ROUND((c.subset_rejects - c.subset_splices * b.reject_rate) * 13.0, 0) AS attributable_cost_usd
FROM combined c, baseline b
ORDER BY attributable_cost_usd DESC;
```

**预期结果与下一步**

6 行结果, 按 attributable_cost 降序. 预期看到: electrode_wear ~$180K, skill_multicore_mismatch ~$145K, ai_alert_ignored ~$130K, calibration_overdue ~$105K, night_shift ~$70K, bad_batch_MFG_2024_038 ~$50K. 合计约 $680K 到 $730K, 跟 CFO 目标 $700K 接近, 给 Marcus 在 BoD prep 的图. 下一步: 进入 Q2 到 Q8 拆分每个 driver 的细节并出具体动作建议.

---

## 5. 查询 3: 月度 FPY 与 reject 率趋势

**业务背景**

Production Manager Sarah Klein 每月例会上向 Marcus 汇报产线健康. 她要看月度的 FPY 和 reject 率有没有恶化. 如果发现 FPY 连续两个月下滑超过 1 个百分点, 立即触发现场调查. 这条查询是 Sarah 仪表盘上最重要的一张图. 对应 Q1.

**标签**

类别: 日期分组 + 窗口函数. 难度: 中级. 角色: Production Manager.

**解题思路**

按 `strftime('%Y-%m', completed_ts)` 切月. FPY 用 attempt_count = 1 AND final_grade != 'Reject' 的比例算. SQLite 不直接支持 PERCENT_RANK 跟 LAG 在月度上的窗口需求, 但用 `LAG(... ) OVER(ORDER BY month)` 取上月 FPY 算同比变化最干净. 注意 LAG 的 ORDER BY 必须是月份字段, 不能是 row_number 否则跨月顺序会乱.

**SQL**

```sql
WITH monthly AS (
    SELECT
        strftime('%Y-%m', completed_ts) AS month,
        COUNT(*) AS splices,
        SUM(CASE WHEN attempt_count = 1 AND final_grade != 'Reject' THEN 1 ELSE 0 END) AS fpy_pass,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY strftime('%Y-%m', completed_ts)
)
SELECT
    month,
    splices,
    ROUND(fpy_pass * 100.0 / splices, 2) AS fpy_pct,
    ROUND(rejects * 100.0 / splices, 2) AS reject_rate_pct,
    ROUND(
        fpy_pass * 100.0 / splices
        - LAG(fpy_pass * 100.0 / splices) OVER(ORDER BY month),
        2
    ) AS fpy_mom_change_pp
FROM monthly
ORDER BY month;
```

**预期结果与下一步**

12 行 (12 个月). FPY 应该围绕 88% 上下波动, reject rate 围绕 2.5%. 看 fpy_mom_change_pp 是否连续两个月下滑超 1pp. 如果有, Sarah 需要跟当月当班的 shift lead 复盘. 这一查询是产线监控的常规心电图, 没有大新闻就保持安静.

---

## 6. 查询 4: 电极使用次数分桶 vs reject 率

**业务背景**

Marcus 要你证明 (或证伪) Q2 假设: "splice_count 越多电极越老, reject 越高". 如果数据能拍出陡峭的非线性曲线, 主动更换电极的 case 就成立. 如果曲线平的, 假设证伪, 这一项就不在 ROI 清单里. 这是 Q2 第一道关键 query.

**标签**

类别: CASE 分桶 + 聚合. 难度: 中级. 角色: Manufacturing Analyst (你).

**解题思路**

直接在 splice_attempt 上 group by electrode_count 分桶. 桶位选 1000 / 1800 / 2200 / 2600 是因为厂家推荐寿命 2000 次, 你想看到拐点是不是在 2000 附近. 只看 attempt_number = 1 这一档, 排除 retry 数据 (retry 是另一个 driver 的故事). attempt 级 reject 用 attempt_grade = 'Reject' 判, 这是 splice_attempt 自带字段, 不需要 join splice_record.

**SQL**

```sql
SELECT
    CASE
        WHEN equipment_electrode_count < 1000 THEN '1. 0 to 1000'
        WHEN equipment_electrode_count < 1800 THEN '2. 1000 to 1800'
        WHEN equipment_electrode_count < 2200 THEN '3. 1800 to 2200'
        WHEN equipment_electrode_count < 2600 THEN '4. 2200 to 2600'
        ELSE '5. 2600+'
    END AS electrode_count_bucket,
    COUNT(*) AS attempts,
    SUM(CASE WHEN attempt_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN attempt_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct,
    ROUND(AVG(actual_loss_db), 4) AS avg_loss_db,
    ROUND(AVG(actual_loss_db) FILTER (WHERE 1=0), 4) AS placeholder_unused
FROM splice_attempt
WHERE attempt_number = 1
  AND attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY electrode_count_bucket
ORDER BY electrode_count_bucket;
```

**预期结果与下一步**

5 行. reject_rate_pct 应呈陡峭非线性: 1.2 → 1.8 → 4.5 → 9.0 → 17.0. avg_loss_db 也单调上升. 这条曲线就是主动换电极 case 的 smoking gun. 拐点出现在 1800 到 2200 之间, 跟厂家 spec 2000 一致. 下一步: Q2-2 用这条曲线估算 ROI.

---

## 7. 查询 5: 主动电极更换策略的 ROI 估算

**业务背景**

Q4 那条曲线证实了电极磨损是大头. 现在 Marcus 要的是 ROI: 如果工厂改成"每 1800 次主动换", 一年新增多少电极成本, 挽回多少 reject 成本, 净节约多少, payback period 多长. 你把这个数字交给 CFO 决定要不要 approve 新 SOP. 对应 Q2.

**标签**

类别: 多 CTE + 算术. 难度: 高级. 角色: VP Operations.

**解题思路**

新策略下电极更换次数 = total_attempts / 1800. 旧策略实际更换次数从 electrode_replacement 表数. 差值 × $180 是额外成本. 挽回的 reject 数 = (electrode_count > 1800 的 attempt 数) × (该桶 reject rate 减去 < 1800 桶的 reject rate). 挽回的金额 = 挽回 reject 数 × $13.

把"新策略成本", "挽回成本", "净节约" 用 CTE 拼出来, 最后一行 SELECT 输出.

**SQL**

```sql
WITH attempt_stats AS (
    SELECT
        COUNT(*) AS total_attempts,
        SUM(CASE WHEN equipment_electrode_count > 1800 THEN 1 ELSE 0 END) AS attempts_above_1800,
        SUM(CASE WHEN equipment_electrode_count > 1800 AND attempt_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects_above_1800,
        SUM(CASE WHEN equipment_electrode_count <= 1800 AND attempt_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects_below_1800,
        SUM(CASE WHEN equipment_electrode_count <= 1800 THEN 1 ELSE 0 END) AS attempts_below_1800
    FROM splice_attempt
    WHERE attempt_number = 1
      AND attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
old_replacements AS (
    SELECT COUNT(*) AS old_replacement_count
    FROM electrode_replacement
    WHERE replacement_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
calc AS (
    SELECT
        a.total_attempts,
        -- 新策略下年更换次数
        CAST(a.total_attempts * 1.0 / 1800 AS INTEGER) AS new_replacement_count,
        o.old_replacement_count,
        -- 高磨损桶的 reject rate
        a.rejects_above_1800 * 1.0 / a.attempts_above_1800 AS rate_high,
        -- 低磨损桶的 reject rate
        a.rejects_below_1800 * 1.0 / a.attempts_below_1800 AS rate_low,
        a.attempts_above_1800,
        a.rejects_above_1800
    FROM attempt_stats a, old_replacements o
)
SELECT
    total_attempts,
    old_replacement_count,
    new_replacement_count,
    new_replacement_count - old_replacement_count AS extra_replacements,
    ROUND((new_replacement_count - old_replacement_count) * 180.0, 2) AS extra_electrode_cost_usd,
    ROUND(rate_high * 100, 2) AS rate_high_pct,
    ROUND(rate_low * 100, 2) AS rate_low_pct,
    -- 如果把高磨损桶降到低磨损 rate, 能少多少 reject
    ROUND(attempts_above_1800 * (rate_high - rate_low), 0) AS avoided_rejects,
    ROUND(attempts_above_1800 * (rate_high - rate_low) * 13.0, 0) AS avoided_reject_cost_usd,
    -- 净节约 = 挽回的 reject 成本 减去 额外电极成本
    ROUND(
        attempts_above_1800 * (rate_high - rate_low) * 13.0
        - (new_replacement_count - old_replacement_count) * 180.0,
        0
    ) AS net_annual_savings_usd
FROM calc;
```

**预期结果与下一步**

一行. extra_replacements 约 60 到 80 对 (额外电极成本约 $12K), avoided_rejects 约 14,000 (按 attempts_above_1800 * 5 个百分点), avoided_reject_cost 约 $180K, net_annual_savings 约 $165K. payback period < 1 个月. 下一步: Marcus 把这条结果连同 Q4 的曲线一起带去 BoD, 申请把 SOP 改成每 1800 次主动换.

---

## 8. 查询 6: 各班次 reject 率与产量贡献

**业务背景**

车间一线传闻"夜班 reject 多", 但没人量化过. Sarah 要用数据确认或否定这个传闻, 因为如果属实, 给夜班加 senior supervisor 会写进 Q3 工资预算. 对应 Q3.

**标签**

类别: 简单聚合. 难度: 基础. 角色: Production Manager.

**解题思路**

按 shift_id group by, 数 splice, 数 reject, 算 reject_rate, 同时算每个班次的产量占比 (用 SUM 总数当分母). 不需要 join 任何表. 简单到几乎无脑.

**SQL**

```sql
SELECT
    sh.shift_name,
    sr.shift_id,
    COUNT(*) AS splices,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS volume_share_pct,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0
        / SUM(SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END)) OVER(),
        2
    ) AS reject_share_pct
FROM splice_record sr
JOIN shift sh ON sr.shift_id = sh.shift_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY sr.shift_id, sh.shift_name
ORDER BY sr.shift_id;
```

**预期结果与下一步**

3 行. 期望: Day reject 1.8%, Swing 2.5%, Night 4.2%. Night 产量占 25% 但 reject_share 占 42%. 传闻成立. 下一步: Q7 计算夜班加 supervisor 的 ROI.

---

## 9. 查询 7: 夜班 floating supervisor ROI

**业务背景**

Marcus 想知道给夜班加一个 $80K 年薪 senior supervisor 能不能 pay off. 这个 supervisor 的工作是巡场, 对一线异常做即时处置, 给夜班的 reject rate 拉到接近 swing shift 的水平. 假设可以把夜班 reject 率从 4.2% 拉到 2.5% (swing 水平), 挽回多少 reject 成本? ROI 多少? 对应 Q3.

**标签**

类别: 多 CTE + ROI 计算. 难度: 中级. 角色: VP Operations.

**解题思路**

夜班 splice 数 × (4.2% 减 2.5%) = 可挽回的 reject 数. × $13 单位成本 = 可挽回金额. supervisor 一年 $80K (含 benefits + 1.4x 系数). 比值就是 ROI.

实际 SQL 里不要硬编码 4.2% 和 2.5%, 直接从 splice_record 算出来, 这样数据变了结论自然变. 用 CTE 把 swing reject rate 和 night reject rate 分别算出来再做 arithmetic.

**SQL**

```sql
WITH night AS (
    SELECT
        COUNT(*) AS night_splices,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS night_rejects
    FROM splice_record
    WHERE shift_id = 'SH-N'
      AND completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
swing AS (
    SELECT
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS swing_rate
    FROM splice_record
    WHERE shift_id = 'SH-S'
      AND completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
)
SELECT
    n.night_splices,
    n.night_rejects,
    ROUND(n.night_rejects * 100.0 / n.night_splices, 2) AS night_reject_rate_pct,
    ROUND(s.swing_rate * 100, 2) AS swing_reject_rate_pct,
    -- 假设夜班拉到 swing 水平能挽回的 reject 数
    ROUND(n.night_rejects - n.night_splices * s.swing_rate, 0) AS avoidable_night_rejects,
    -- 挽回成本
    ROUND((n.night_rejects - n.night_splices * s.swing_rate) * 13.0, 0) AS avoidable_cost_usd,
    -- 加 supervisor 年成本
    80000 AS supervisor_annual_cost_usd,
    -- 净节约
    ROUND((n.night_rejects - n.night_splices * s.swing_rate) * 13.0 - 80000, 0) AS net_savings_usd,
    -- ROI 比值
    ROUND((n.night_rejects - n.night_splices * s.swing_rate) * 13.0 / 80000.0, 2) AS roi_ratio
FROM night n, swing s;
```

**预期结果与下一步**

一行. avoidable_night_rejects 约 200 到 250, avoidable_cost 约 $90K 到 $110K, net_savings 约 $25K, roi_ratio 约 1.3 到 1.4. 边际正收益但不夸张. Marcus 评估: 加 supervisor 不只为了 reject 成本, 还能改善夜班士气和留人率, 综合判定 approve. 下一步: 写 supervisor 岗位 JD 提交 HR.

---

## 10. 查询 8: 技能等级 × 光纤规格 reject 交叉表

**业务背景**

车间排班政策是 multi_core_certified 的 operator 都可以接 multi-core 任务, 不分技能等级. Sarah 怀疑 junior 拿到 multi-core cert 后实际做得很差. 这条查询就是 4×3 交叉表, 看哪个格子最危险. 对应 Q4.

**标签**

类别: 交叉表 + 多表 JOIN. 难度: 中级. 角色: Production Manager.

**解题思路**

需要 splice_record + operator + fiber_spool + fiber_spec 四表. 关键是不要 INNER JOIN 多次造成 splice 行重复. 一根 splice 有 left_spool 和 right_spool, 在多数情况下两者同规格. 取 left_spool 的 spec 就够代表整根 splice. 用 left_spool_id → fiber_spool → fiber_spec 这条路径. 然后按 skill_level × mode_type group by, 用 SUM(CASE) 同时算 reject 率.

为了显示 cell counts 太少时不要被误导, 顺手加上 splices count 列.

**SQL**

```sql
SELECT
    o.skill_level,
    fs.mode_type,
    COUNT(*) AS splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct
FROM splice_record sr
JOIN operator o ON sr.operator_id = o.operator_id
JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY o.skill_level, fs.mode_type
ORDER BY
    CASE o.skill_level
        WHEN 'junior' THEN 1
        WHEN 'intermediate' THEN 2
        WHEN 'senior' THEN 3
        WHEN 'expert' THEN 4
    END,
    CASE fs.mode_type
        WHEN 'single' THEN 1
        WHEN 'multi' THEN 2
        WHEN 'multi_core' THEN 3
    END;
```

**预期结果与下一步**

12 行 (4 skill × 3 mode). 关键格子: junior × multi_core ~25%, intermediate × multi_core ~12%, senior × multi_core ~3%, expert × multi_core ~2%. 单核所有 skill 都在 1 到 2%. 数据成立: 错配主要在 multi-core. 下一步: Q9 估算重新排班的 ROI.

---

## 11. 查询 9: Multi-core 重新排班的 ROI 估算

**业务背景**

Marcus 决定推一个新政策: multi-core 任务只能分给 senior + expert 操作员, junior + intermediate 不再接 multi-core. 你要估算: 一年挽回多少 reject, 但是否会造成 senior + expert 产能瓶颈, 是否需要额外培训预算. 对应 Q4.

**标签**

类别: 多 CTE + 反事实计算. 难度: 高级. 角色: VP Operations.

**解题思路**

反事实: 把 junior + intermediate 在 multi-core 上的 splice 替换到 senior + expert 的 reject 率上, 算挽回的 reject 数. 但同时要检查 senior + expert 当前产能是否足够吸收这些 splice. 用 senior + expert 当前 multi-core 工作量 vs 总 multi-core 工作量比较. 如果 senior + expert 当前只占 multi-core 工作量的 70%, 要把另 30% 也接过来意味着多上 30% 的工时, 可能要加班或招人.

写两个 CTE, 一个是 junior + intermediate 在 multi-core 的现状 (rate_low_skill), 一个是 senior + expert 在 multi-core 的现状 (rate_high_skill). 反事实 = 把 splice 量从前者转给后者, 用 rate_high_skill 重算 reject.

**SQL**

```sql
WITH low_skill_mc AS (
    SELECT
        COUNT(*) AS low_mc_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS low_mc_rejects
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
    WHERE fs.mode_type = 'multi_core'
      AND o.skill_level IN ('junior', 'intermediate')
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
high_skill_mc AS (
    SELECT
        COUNT(*) AS high_mc_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS high_mc_rate
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
    WHERE fs.mode_type = 'multi_core'
      AND o.skill_level IN ('senior', 'expert')
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
)
SELECT
    l.low_mc_splices,
    l.low_mc_rejects,
    ROUND(l.low_mc_rejects * 100.0 / l.low_mc_splices, 2) AS low_skill_mc_reject_pct,
    h.high_mc_splices,
    ROUND(h.high_mc_rate * 100, 2) AS high_skill_mc_reject_pct,
    -- 反事实, 把 low_skill multi-core 移给 high_skill 后预期 reject 数
    ROUND(l.low_mc_splices * h.high_mc_rate, 0) AS counterfactual_rejects,
    -- 避免的 reject 数
    ROUND(l.low_mc_rejects - l.low_mc_splices * h.high_mc_rate, 0) AS avoided_rejects,
    -- 挽回成本
    ROUND((l.low_mc_rejects - l.low_mc_splices * h.high_mc_rate) * 13.0, 0) AS avoided_cost_usd,
    -- 检查 senior + expert 是否需要多承担, 增量产能需求 (%)
    ROUND(l.low_mc_splices * 100.0 / h.high_mc_splices, 1) AS extra_capacity_load_pct
FROM low_skill_mc l, high_skill_mc h;
```

**预期结果与下一步**

一行. avoided_rejects 约 11,000, avoided_cost 约 $145K. extra_capacity_load 约 40% (senior + expert 当前 multi-core 工作量上要再加 40%). 决策: 一年要新增 senior 培训 4 人, 培训成本 $40K, 净节约 ~$105K. 下一步: HR 启动 senior 培训计划, 排班系统加 hard constraint 禁止 junior + intermediate 接 multi-core.

---

## 12. 查询 10: 按客户 segment 的 spec compliance gap

**业务背景**

VP Sales Jorge 在跟 CFO 讨论一个想法: 把 FTTH 订单的内部 reject 阈值松绑到客户实际 spec (0.30 dB), 不再用一刀切的 0.05. CFO 想先看数据: 当前各 segment 的 internal reject rate 多少, 但按客户实际 spec 判 (即 final_loss_db ≤ order.loss_threshold_db), compliance rate 多少, 两者 gap 多大. 对应 Q5.

**标签**

类别: 多表 JOIN + 双口径对比. 难度: 中级. 角色: CFO + VP Sales.

**解题思路**

需要 splice_record + splice_job + customer_order + customer 四表. splice_record → splice_job → customer_order → customer. 然后按 customer.segment group by, 算两个口径:

口径 A (internal reject): final_grade = 'Reject' 的比例.
口径 B (customer spec compliance): final_loss_db ≤ order.loss_threshold_db 的比例.

两者的 gap (B - (1 - A)) 就是"被内部 SOP 错判为废品但客户实际能接受"的体量.

**SQL**

```sql
SELECT
    c.segment,
    COUNT(*) AS splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS internal_rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS internal_reject_rate_pct,
    -- 按客户实际 spec 判合格的比例
    SUM(CASE WHEN sr.final_loss_db <= co.loss_threshold_db THEN 1 ELSE 0 END) AS customer_spec_passes,
    ROUND(
        SUM(CASE WHEN sr.final_loss_db <= co.loss_threshold_db THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS customer_spec_pass_rate_pct,
    -- 内部判 reject 但客户实际接受的数量 (过度质量的 splice 数)
    SUM(
        CASE
            WHEN sr.final_grade = 'Reject' AND sr.final_loss_db <= co.loss_threshold_db THEN 1
            ELSE 0
        END
    ) AS over_quality_count,
    ROUND(
        SUM(
            CASE
                WHEN sr.final_grade = 'Reject' AND sr.final_loss_db <= co.loss_threshold_db THEN 1
                ELSE 0
            END
        ) * 100.0 / COUNT(*),
        2
    ) AS over_quality_rate_pct
FROM splice_record sr
JOIN splice_job j ON sr.job_id = j.job_id
JOIN customer_order co ON j.order_id = co.order_id
JOIN customer c ON co.customer_id = c.customer_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY c.segment
ORDER BY over_quality_rate_pct DESC;
```

**预期结果与下一步**

3 行 (三个 segment). hyperscale: internal_reject 3.0%, customer_spec_pass 96.5% (gap ~0, 客户 spec 严格); enterprise: internal_reject 2.5%, customer_spec_pass 99%, over_quality 0.5%; **ftth: internal_reject 2.5%, customer_spec_pass 99.8%, over_quality 2.2%**. FTTH 的 over_quality 数量最多, 是松绑的最大机会. 下一步: Q11 估算松绑后的具体成本节约.

---

## 13. 查询 11: 按客户实际 spec 重判后的成本节约

**业务背景**

把 Q10 的发现变成 dollar number 给 CFO. 如果把 FTTH 订单按 0.30 dB 而不是 0.05 dB 判 reject, 一年少返工多少根, 少 retry 多少次, 节约多少 attempt 成本? 这个数字会进 memo, 也会触发 SOP 修订. 对应 Q5.

**标签**

类别: CTE + 多源成本汇总. 难度: 高级. 角色: CFO.

**解题思路**

过度质量 splice 的 cost-impact 不止 reject 成本, 还包括 retry attempt 的成本. 一根 splice 如果 attempt 2 后 final_grade = Reject 但客户实际 spec 能接受, 那 attempt 2 完全是浪费的 (在新 spec 下 attempt 1 就该接受). 这一类 splice 的额外成本 = attempt 2 和 attempt 3 的 total_cost_usd 之和.

先用 CTE 标出哪些 splice 是"过度质量"(internal reject 但 customer pass), 然后对这些 splice 的所有 attempt_number > 1 的 attempts 求 total_cost. 这部分成本就是松绑 SOP 能省下的钱.

注意 attempt_number = 1 的成本是必然付出的 (无论 SOP 如何, 第一次焊接都得做), 不能算节约.

**SQL**

```sql
WITH over_quality_splices AS (
    SELECT sr.splice_id
    FROM splice_record sr
    JOIN splice_job j ON sr.job_id = j.job_id
    JOIN customer_order co ON j.order_id = co.order_id
    JOIN customer c ON co.customer_id = c.customer_id
    WHERE c.segment = 'ftth_carrier'
      AND sr.final_grade = 'Reject'
      AND sr.final_loss_db <= co.loss_threshold_db
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
waste_cost AS (
    SELECT
        COUNT(DISTINCT sa.splice_id) AS over_quality_splice_count,
        COUNT(*) AS wasted_attempts,
        ROUND(SUM(sa.total_cost_usd), 2) AS wasted_attempt_cost_usd
    FROM splice_attempt sa
    JOIN over_quality_splices oqs ON sa.splice_id = oqs.splice_id
    WHERE sa.attempt_number > 1
),
reject_cost AS (
    -- 这批 splice 还要算"被内部判 reject" 衍生的下游成本 (返工, 物料浪费, 入库审计)
    -- 单位 $13, 跟 Q2 一致
    SELECT
        COUNT(*) AS over_quality_splices,
        COUNT(*) * 13.0 AS downstream_reject_cost_usd
    FROM over_quality_splices
)
SELECT
    rc.over_quality_splices,
    wc.wasted_attempts,
    wc.wasted_attempt_cost_usd,
    rc.downstream_reject_cost_usd,
    ROUND(wc.wasted_attempt_cost_usd + rc.downstream_reject_cost_usd, 2) AS total_annual_savings_usd
FROM waste_cost wc, reject_cost rc;
```

**预期结果与下一步**

一行. over_quality_splices 约 800 到 1100, wasted_attempts 约 1500 (大多有 1 到 2 次额外 attempt), wasted_attempt_cost 约 $4K, downstream_reject_cost 约 $13K, total 约 $17K. 数字不大但实施成本几乎为零 (只需改 SOP 文档). ROI 极高. 下一步: QA 经理 Tom 起草 SOP 修订, 加 `dynamic_threshold = order.loss_threshold_db` 逻辑, 8 周内上线.

---

## 14. 查询 12: AI 告警 outcome 与下游 reject 联动

**业务背景**

Tom (QA Engineering Manager) 一直怀疑 operator 忽视 AI 告警的成本. 他要数据证明 outcome = ignored 的告警下游真的更容易 reject. 如果差异显著, 他会推动给告警系统加"硬拦截" (告警时强制 operator 选择 reclean 或 escalate, 不能选 ignore). 对应 Q6.

**标签**

类别: 多表 JOIN + 聚合. 难度: 中级. 角色: QA Engineering Manager.

**解题思路**

quality_alert 挂在 splice_attempt 上, 不直接连 splice_record. 要从 alert.outcome 追到 splice_record.final_grade, 需要走 alert → attempt → splice_record. 用 INNER JOIN 是正确的, 因为每一个 alert 都关联唯一 attempt 进而唯一 splice. 按 outcome group by, 算 reject rate.

注意一根 splice 可能有多个 alert (3 次 attempt 都可能触发). 同一个 splice 算多次 outcome 没问题, 因为 outcome 是 attempt 级别的, 但要意识到 DISTINCT splice count 跟 alert count 不一样.

**SQL**

```sql
SELECT
    qa.outcome,
    COUNT(*) AS alert_count,
    COUNT(DISTINCT sr.splice_id) AS distinct_splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS downstream_rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS downstream_reject_rate_pct,
    ROUND(AVG(sr.final_loss_db), 4) AS avg_final_loss_db
FROM quality_alert qa
JOIN splice_attempt sa ON qa.attempt_id = sa.attempt_id
JOIN splice_record sr ON sa.splice_id = sr.splice_id
WHERE qa.alert_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY qa.outcome
ORDER BY downstream_reject_rate_pct DESC;
```

**预期结果与下一步**

3 行 (resolved, ignored, escalated). 期望: ignored 35%, escalated 8%, resolved 3%. ignored 的下游 reject 率是 resolved 的 11 倍. 数据明确支持 Tom 的怀疑. 下一步: Q13 给硬拦截的 ROI, Tom 拿去提产品 / IT 改造工单.

---

## 15. 查询 13: 告警 ignored 的班次切分与强制执行 ROI

**业务背景**

Q12 证明 ignored 告警下游 reject 很高, 但不知道是不是均匀分布. Marcus 想知道哪个班次 ignore 最多. 如果集中在夜班, 加 Q7 的 supervisor + 告警硬拦截可能要分两步走. 如果均匀分布, 直接走告警硬拦截就够. 同时给出强制执行的年化 ROI. 对应 Q6.

**标签**

类别: 二维 group by + 反事实计算. 难度: 高级. 角色: VP Operations.

**解题思路**

二维 group: shift_id × outcome. 算每个 shift 的 ignored_share (ignored 占该 shift 总 alert 的比例). 然后反事实: 如果强制把所有 ignored 变成 resolved, 这些 splice 的预期 reject rate 应当掉到 resolved 水平, 挽回的 reject 数 = ignored 数 × (ignored_rate - resolved_rate).

注意 GROUP BY shift × outcome 后用 SUM(SUM) OVER PARTITION BY shift 算同一 shift 内 outcome 占比. SQLite 支持这种"先聚合再窗口" 的写法.

**SQL**

```sql
WITH alert_by_shift_outcome AS (
    SELECT
        sr.shift_id,
        qa.outcome,
        COUNT(*) AS alerts,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS downstream_rejects
    FROM quality_alert qa
    JOIN splice_attempt sa ON qa.attempt_id = sa.attempt_id
    JOIN splice_record sr ON sa.splice_id = sr.splice_id
    WHERE qa.alert_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY sr.shift_id, qa.outcome
),
shift_distribution AS (
    SELECT
        shift_id,
        outcome,
        alerts,
        downstream_rejects,
        ROUND(alerts * 100.0 / SUM(alerts) OVER(PARTITION BY shift_id), 2) AS outcome_share_within_shift_pct,
        ROUND(downstream_rejects * 100.0 / alerts, 2) AS outcome_reject_rate_pct
    FROM alert_by_shift_outcome
),
ignored_savings AS (
    -- 如果把 ignored 告警的 reject 率拉到 resolved 水平, 每个 shift 能挽回多少 reject
    SELECT
        a.shift_id,
        a.alerts AS ignored_alerts,
        a.downstream_rejects AS ignored_rejects,
        r.outcome_reject_rate_pct AS resolved_rate_pct,
        ROUND(
            a.downstream_rejects - a.alerts * r.outcome_reject_rate_pct / 100.0,
            0
        ) AS avoidable_rejects,
        ROUND(
            (a.downstream_rejects - a.alerts * r.outcome_reject_rate_pct / 100.0) * 13.0,
            0
        ) AS avoidable_cost_usd
    FROM alert_by_shift_outcome a
    JOIN shift_distribution r
        ON a.shift_id = r.shift_id AND r.outcome = 'resolved'
    WHERE a.outcome = 'ignored'
)
SELECT * FROM shift_distribution
ORDER BY shift_id, outcome;
```

跟着再跑一句汇总:

```sql
WITH alert_by_shift_outcome AS (
    SELECT
        sr.shift_id,
        qa.outcome,
        COUNT(*) AS alerts,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS downstream_rejects
    FROM quality_alert qa
    JOIN splice_attempt sa ON qa.attempt_id = sa.attempt_id
    JOIN splice_record sr ON sa.splice_id = sr.splice_id
    WHERE qa.alert_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY sr.shift_id, qa.outcome
),
resolved_rate AS (
    SELECT
        shift_id,
        downstream_rejects * 1.0 / alerts AS resolved_rate
    FROM alert_by_shift_outcome
    WHERE outcome = 'resolved'
)
SELECT
    a.shift_id,
    a.alerts AS ignored_alerts,
    a.downstream_rejects AS ignored_rejects_actual,
    ROUND(a.alerts * r.resolved_rate, 0) AS ignored_rejects_if_forced,
    ROUND(a.downstream_rejects - a.alerts * r.resolved_rate, 0) AS avoidable_rejects,
    ROUND((a.downstream_rejects - a.alerts * r.resolved_rate) * 13.0, 0) AS avoidable_cost_usd
FROM alert_by_shift_outcome a
JOIN resolved_rate r ON a.shift_id = r.shift_id
WHERE a.outcome = 'ignored'
ORDER BY avoidable_cost_usd DESC;
```

**预期结果与下一步**

第一张表 9 行 (3 shift × 3 outcome). 关键 cell: Night × ignored share 约 28%, Day × ignored share 约 5%. 第二张表 3 行 (各 shift 的强制执行节约). Night avoidable 约 $90K, Swing 约 $25K, Day 约 $10K. 总 $125K 量级. 下一步: Marcus 把 Q12 + Q13 一起带去给 CIO, 申请 24 小时硬拦截 (告警必须选 reclean / escalate, 移除 ignore 按钮), 4 周内上线.

---

## 16. 查询 14: 设备校准超期天数 vs reject 率

**业务背景**

Sarah 怀疑校准超期的设备质量不稳. SOP 是 90 天一次, 但执行不严. 这条 query 把校准距今天数分桶, 看 reject rate 怎么变. 数据如果支持, 把 SOP 改成 60 天的提议就有 leverage. 对应 Q7.

**标签**

类别: 日期函数 + 聚合. 难度: 基础. 角色: Production Manager.

**解题思路**

`julianday(REFERENCE_DATE) - julianday(equipment.last_calibration_date)` 算天数. 但这是设备级数据, 不是 splice 级. 一根 splice 的校准状态由它所在设备在那一刻的 last_calibration_date 决定. 简化处理: 直接用 equipment 当前的 last_calibration_date 跟 REFERENCE_DATE 比 (假设最近一次校准之后没再校准过, 跟数据集生成方式一致).

把每个 splice 用对应 equipment 的天数分桶, group by 算 reject rate.

**SQL**

```sql
SELECT
    CASE
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) <= 60 THEN '1. <=60 days'
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) <= 90 THEN '2. 60 to 90 days'
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) <= 120 THEN '3. 90 to 120 days'
        ELSE '4. 120+ days'
    END AS calibration_age_bucket,
    COUNT(DISTINCT e.equipment_id) AS equipment_count,
    COUNT(*) AS splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct
FROM splice_record sr
JOIN equipment e ON sr.equipment_id = e.equipment_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY calibration_age_bucket
ORDER BY calibration_age_bucket;
```

**预期结果与下一步**

4 行. reject rate 应从 1.5% 单调上升到 5.5%. 超 90 天和 ≤ 90 天的差距清晰. 下一步: Marcus 提议把 SOP 改成 60 天, 跟 maintenance 团队确认 calibration capacity 是否够 (一次 calibration 2.5 小时). 用 Q5 同样的 ROI 公式跑一下: 12 台设备额外 4 次 calibration / 年, 成本 $480 × 4 × 12 = $23K, 挽回成本约 $90K, ROI 4x. Approve.

---

## 17. 查询 15: 坏批次 MFG-2024-038 的质量影响范围

**业务背景**

QA Engineering Manager Tom 上周收到 SumiOptics 一封发来通知 "MFG-2024-038 批次 cladding 方差超出我们内部 control limit, 但 release 给你们时认为可接受". Tom 想知道这个批次到底用掉了多少, 用在哪些客户的订单上, 跟出现的 customer complaint 有没有匹配. 这条查询是召回评估的第一步. 对应 Q8.

**标签**

类别: 多表 JOIN + 过滤. 难度: 中级. 角色: QA Engineering Manager.

**解题思路**

从 fiber_batch 出发, 找到该批次下所有 fiber_spool, 再找 splice_record (left_spool_id 或 right_spool_id 命中即可). 一根 splice 用了左右两个 spool, 任一个匹配批次就算"碰到了". 用 OR 条件而不是 UNION 更简洁.

然后 join 到 customer 看影响的客户分布. 同时 join customer_complaint 看是否能匹配上.

**SQL**

```sql
SELECT
    fb.batch_id,
    fb.supplier_name,
    fb.cladding_diameter_std_dev_um,
    fb.qc_release_status,
    COUNT(DISTINCT sr.splice_id) AS impacted_splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0
            / NULLIF(COUNT(DISTINCT sr.splice_id), 0),
        2
    ) AS reject_rate_pct,
    COUNT(DISTINCT co.order_id) AS impacted_orders,
    COUNT(DISTINCT co.customer_id) AS impacted_customers,
    GROUP_CONCAT(DISTINCT c.customer_code) AS customer_codes
FROM fiber_batch fb
JOIN fiber_spool fsp ON fb.batch_id = fsp.batch_id
JOIN splice_record sr
    ON (sr.left_spool_id = fsp.spool_id OR sr.right_spool_id = fsp.spool_id)
JOIN splice_job j ON sr.job_id = j.job_id
JOIN customer_order co ON j.order_id = co.order_id
JOIN customer c ON co.customer_id = c.customer_id
WHERE fb.batch_id = 'MFG-2024-038'
  AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY fb.batch_id, fb.supplier_name, fb.cladding_diameter_std_dev_um, fb.qc_release_status;
```

**预期结果与下一步**

一行. impacted_splices 约 280, reject_rate 约 12% (vs baseline 2.5%), impacted_orders 约 5, impacted_customers 1 到 2 (主要是 FTTH-CCom). customer_codes 列出受影响客户代号. 下一步: Q16 把这个批次跟 customer_complaint 关联起来, 决定是否要走 customer notification 流程.

---

## 18. 查询 16: 客户投诉到批次反查路径

**业务背景**

Tom 要给 CEO David Park 出一份"是否启动 customer notification" 的判断备忘. 关键事实: 批次 MFG-2024-038 收到了几条 customer_complaint, severity 是什么, 已花了多少 cost_impact. 如果 high + critical complaint 数 > 5 或 cost_impact > $30K, 走 customer notification 是法律建议. 对应 Q8.

**标签**

类别: 多表 JOIN + 条件聚合. 难度: 高级. 角色: QA Engineering Manager.

**解题思路**

从 customer_complaint 出发, filter linked_batch_id = 'MFG-2024-038'. 按 severity group by, 算 count 和 cost_impact 总和. 但还要看 unlinked complaint (linked_batch_id 是 NULL 但 complaint_date 跟批次使用窗口重合 + complaint_type = high_loss_in_field), 这是"可能也是这个批次造成但 QA 没追到"的潜在风险.

用 UNION ALL 把"已确认归因" 和"可能归因" 分两栏展示, 给决策留余地.

**SQL**

```sql
WITH confirmed AS (
    SELECT
        'confirmed_to_MFG-2024-038' AS category,
        cc.severity,
        COUNT(*) AS complaint_count,
        ROUND(SUM(cc.cost_impact_usd), 2) AS total_cost_impact_usd
    FROM customer_complaint cc
    WHERE cc.linked_batch_id = 'MFG-2024-038'
    GROUP BY cc.severity
),
suspected AS (
    SELECT
        'suspected_unlinked' AS category,
        cc.severity,
        COUNT(*) AS complaint_count,
        ROUND(SUM(cc.cost_impact_usd), 2) AS total_cost_impact_usd
    FROM customer_complaint cc
    WHERE cc.linked_batch_id IS NULL
      AND cc.complaint_type IN ('high_loss_in_field', 'early_failure')
      AND cc.complaint_date BETWEEN '2025-12-01' AND '2026-06-15'
    GROUP BY cc.severity
),
combined AS (
    SELECT * FROM confirmed
    UNION ALL
    SELECT * FROM suspected
)
SELECT
    category,
    severity,
    complaint_count,
    total_cost_impact_usd
FROM combined
ORDER BY
    category,
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END;
```

**预期结果与下一步**

约 4 到 6 行. 关键: confirmed_to_MFG-2024-038 的 high 类 6 条, cost_impact 总和约 $50K 到 $60K. 触发 customer notification 阈值. 下一步: Tom 起草 notification 草稿, 跟法律和销售团队评审 24 小时内发给 FTTH-CCom. 同时与 SumiOptics 启动 supplier corrective action.

---

## 19. 查询 17: 设备维护优先级看板

**业务背景**

Sarah 每周一早晨开早会要看一张设备状态表. 哪些设备校准要超期, 哪些累计 splice 数过万要全面检修, 哪些近期 reject 偏高. 排好优先级当周安排. 对应 NorthArc 日常运营.

**标签**

类别: CTE + CASE 排序. 难度: 中级. 角色: Production Manager.

**解题思路**

equipment 表加 30 天内的近期 reject 统计 (LEFT JOIN, 避免 maintenance 状态的设备被剔除). 用 CASE 给每台设备打优先级标签: 校准过期 > 近期 reject 高 > 累计 splice 多 > 正常. 排序按优先级数字升序, 同优先级按近期 reject 率降序.

**SQL**

```sql
WITH recent_perf AS (
    SELECT
        equipment_id,
        COUNT(*) AS recent_splices,
        ROUND(AVG(final_loss_db), 4) AS recent_avg_loss,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS recent_rejects,
        ROUND(
            SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
            2
        ) AS recent_reject_rate_pct
    FROM splice_record
    WHERE completed_ts BETWEEN date('2026-06-15', '-30 days') AND '2026-06-15'
    GROUP BY equipment_id
)
SELECT
    e.equipment_id,
    e.model,
    e.location,
    e.status,
    e.last_calibration_date,
    CAST(julianday('2026-06-15') - julianday(e.last_calibration_date) AS INTEGER) AS days_since_cal,
    e.total_splice_count,
    COALESCE(rp.recent_splices, 0) AS recent_splices,
    COALESCE(rp.recent_reject_rate_pct, 0) AS recent_reject_rate_pct,
    CASE
        WHEN e.status = 'maintenance' THEN 'IN_MAINTENANCE'
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) > 90 THEN 'P1_CAL_OVERDUE'
        WHEN COALESCE(rp.recent_reject_rate_pct, 0) > 5 THEN 'P2_QUALITY_ALERT'
        WHEN e.total_splice_count > 8000 THEN 'P3_HIGH_USAGE'
        ELSE 'OK'
    END AS priority
FROM equipment e
LEFT JOIN recent_perf rp ON e.equipment_id = rp.equipment_id
ORDER BY
    CASE
        WHEN e.status = 'maintenance' THEN 1
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) > 90 THEN 2
        WHEN COALESCE(rp.recent_reject_rate_pct, 0) > 5 THEN 3
        WHEN e.total_splice_count > 8000 THEN 4
        ELSE 5
    END,
    recent_reject_rate_pct DESC;
```

**预期结果与下一步**

12 行 (所有设备). 应该有 3 到 4 台落在 P1_CAL_OVERDUE, 1 到 2 台落在 P2_QUALITY_ALERT, 1 台落在 IN_MAINTENANCE, 其余 OK. Sarah 当周排校准. P2 的设备额外安排技师诊断.

---

## 20. 查询 18: 每日产量, FPY, reject 率, 3 周移动平均

**业务背景**

Marcus 月度向董事会 prep 的标准图: 每日产量曲线叠 3 周移动平均的 reject 率. 移动平均能盖过单日噪声看到趋势. 这是 BoD deck 上必有一页. 对应 NorthArc 日常运营.

**标签**

类别: 日期聚合 + 窗口函数. 难度: 高级. 角色: VP Operations.

**解题思路**

按日 group by 算 daily_splices, daily_fpy, daily_reject_rate. 然后用 `AVG(...) OVER (ORDER BY day ROWS BETWEEN 20 PRECEDING AND CURRENT ROW)` 计算 3 周 (21 天) 移动平均.

SQLite 支持这种窗口语法, 但要小心 ROWS 跟 RANGE 的区别. ROWS 按行数, RANGE 按值范围. 在日数据上两者只有缺失日期时有差异. 假设没缺失日, 用 ROWS 即可.

**SQL**

```sql
WITH daily AS (
    SELECT
        DATE(completed_ts) AS day,
        COUNT(*) AS splices,
        SUM(CASE WHEN attempt_count = 1 AND final_grade != 'Reject' THEN 1 ELSE 0 END) AS fpy_pass,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY DATE(completed_ts)
)
SELECT
    day,
    splices,
    ROUND(fpy_pass * 100.0 / splices, 2) AS fpy_pct,
    ROUND(rejects * 100.0 / splices, 2) AS reject_rate_pct,
    ROUND(
        AVG(rejects * 100.0 / splices)
            OVER (ORDER BY day ROWS BETWEEN 20 PRECEDING AND CURRENT ROW),
        2
    ) AS reject_rate_3w_avg_pct,
    ROUND(
        AVG(splices)
            OVER (ORDER BY day ROWS BETWEEN 20 PRECEDING AND CURRENT ROW),
        0
    ) AS splices_3w_avg
FROM daily
ORDER BY day;
```

**预期结果与下一步**

约 360 行 (一年). 看 reject_rate_3w_avg 是不是平稳在 2.5% 附近. 如果中间某段 (例如 2025-12 到 2026-02 那段, 跟 bad batch 时间窗口对齐) 出现 spike 上 4%, 就是数据故事的高潮. Marcus 用这张图做 BoD slide 5 的 anchor.

---

## 21. 查询 19: QA 复核 vs operator 自评的偏差分析

**业务背景**

Tom 想知道 operator 自评的 quality_grade 跟 QA 用 OTDR 复核后判定有多大偏差. 如果 grade_match 率低于 90%, 内部数据信任度下降, 整个 Tableau dashboard 都要打折扣. 同时 LID 算法的系统偏差能反映出来. 对应 NorthArc 日常运营.

**标签**

类别: 聚合 + JOIN. 难度: 中级. 角色: QA Engineering Manager.

**解题思路**

直接看 qa_audit 表. grade_match = False 的样本分类: operator self_grade 太宽松 (实际更差) 还是太严 (实际更好). 用 SIGN(variance_db) 判: variance > 0 说明 QA 测得比自评更差, variance < 0 说明更好.

按 operator 切分能找出特定 operator 评分系统性偏松或偏紧. 这是绩效面谈材料.

**SQL**

```sql
SELECT
    o.operator_id,
    o.name,
    o.skill_level,
    COUNT(*) AS audited,
    SUM(CASE WHEN qa.grade_match THEN 1 ELSE 0 END) AS matches,
    ROUND(
        SUM(CASE WHEN qa.grade_match THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS match_rate_pct,
    SUM(CASE WHEN qa.variance_db > 0.01 THEN 1 ELSE 0 END) AS operator_overgraded,
    SUM(CASE WHEN qa.variance_db < -0.01 THEN 1 ELSE 0 END) AS operator_undergraded,
    ROUND(AVG(qa.variance_db), 5) AS avg_variance_db
FROM qa_audit qa
JOIN splice_record sr ON qa.splice_id = sr.splice_id
JOIN operator o ON sr.operator_id = o.operator_id
WHERE qa.audit_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY o.operator_id, o.name, o.skill_level
HAVING COUNT(*) >= 10
ORDER BY match_rate_pct ASC
LIMIT 20;
```

**预期结果与下一步**

20 行, 按 match_rate 升序 (最差的在前). 总体 match_rate 应该 92% 到 96%. 如果某操作员 match_rate < 85%, Tom 跟 Sarah 谈话, 要么 retrain, 要么这位操作员的 splice 强制 QA 复核率从 5% 拉到 20%.

---

## 22. 查询 20: 操作员综合绩效排名

**业务背景**

Sarah 每个季度做 operator performance review. 不能只看 reject rate (否则 junior 永远输), 不能只看产量 (否则 expert 在 multi-core 上吃亏). 公平的排名要看 z-score normalized 后的多维加权. 这是 HR 决定加薪 / 晋升的输入. 对应 NorthArc 日常运营.

**标签**

类别: 多 CTE + 窗口函数. 难度: 高级. 角色: Production Manager.

**解题思路**

三个维度: 产量 (splices), 质量 (reject_rate, 越低越好), 一次通过率 (FPY). 每个维度按 skill_level 内部排名 (而不是全体排名), 因为不同 skill level 的基准期望不同. SQLite 用 RANK() OVER (PARTITION BY skill_level ORDER BY ...). 三个 rank 加和倒序排, 得到综合分.

为了避免样本太少操作员上榜, 加 HAVING COUNT(*) >= 100.

**SQL**

```sql
WITH stats AS (
    SELECT
        sr.operator_id,
        o.name,
        o.skill_level,
        COUNT(*) AS splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
        SUM(CASE WHEN sr.attempt_count = 1 AND sr.final_grade != 'Reject' THEN 1 ELSE 0 END) AS fpy_pass
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY sr.operator_id, o.name, o.skill_level
    HAVING COUNT(*) >= 100
),
ranked AS (
    SELECT
        operator_id,
        name,
        skill_level,
        splices,
        ROUND(rejects * 100.0 / splices, 2) AS reject_rate_pct,
        ROUND(fpy_pass * 100.0 / splices, 2) AS fpy_pct,
        RANK() OVER (PARTITION BY skill_level ORDER BY splices DESC) AS volume_rank,
        RANK() OVER (PARTITION BY skill_level ORDER BY rejects * 1.0 / splices ASC) AS quality_rank,
        RANK() OVER (PARTITION BY skill_level ORDER BY fpy_pass * 1.0 / splices DESC) AS fpy_rank
    FROM stats
)
SELECT
    operator_id,
    name,
    skill_level,
    splices,
    reject_rate_pct,
    fpy_pct,
    volume_rank,
    quality_rank,
    fpy_rank,
    volume_rank + quality_rank + fpy_rank AS composite_score
FROM ranked
ORDER BY skill_level, composite_score ASC;
```

**预期结果与下一步**

按 skill_level 分块. 每块里 composite_score 最低的 (即三项都靠前) 是当季度 MVP. Sarah 给前 20% 加 5% 工资, 给后 20% 排额外培训.

---

## 23. 业务问题到查询的映射表

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 总览, 钱漏在哪里 | Q1, Q2, Q3 |
| Q2 电极更换策略 | Q4, Q5 |
| Q3 夜班质量恶化 | Q6, Q7 |
| Q4 multi-core 错配 | Q8, Q9 |
| Q5 过度质量 spec 松绑 | Q10, Q11 |
| Q6 AI 告警 ignored | Q12, Q13 |
| Q7 校准超期 | Q14 |
| Q8 召回风险 MFG-2024-038 | Q15, Q16 |
| 日常运营 | Q17, Q18, Q19, Q20 |

每一个业务问题至少 1 条查询, 大头问题 (Q1, Q2, Q3, Q4, Q5, Q6) 各 2 条. Q7 和 Q8 因为分别是单点验证 + 召回评估, 量上稍少. 日常运营 4 条覆盖 Sarah 和 Marcus 的周例会输入.

---

## 24. 备注

所有 SQL 已在 SQLite 3.x 上验证. 几个 SQLite 特有的写法说明:

- `julianday(date)` 返回从儒略日开始的天数, 两个 julianday 相减得到天数差, 比直接日期减更可靠.
- `strftime('%Y-%m', ts)` 把 datetime 切成月份字符串, 比 `EXTRACT(MONTH FROM ...)` (PostgreSQL 写法) 更兼容.
- `JULIANDAY` 和 `STRFTIME` 都接受字符串日期 (ISO 8601 格式), 不需要先转 DATE.
- `GROUP_CONCAT(DISTINCT col)` 是 SQLite 的字符串聚合, PostgreSQL 里是 `STRING_AGG`.
- 移动平均用 `AVG(...) OVER (ORDER BY ... ROWS BETWEEN N PRECEDING AND CURRENT ROW)`, SQLite 3.25+ 支持.
- 所有日期字面量用 ISO 格式 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM:SS`. SQLite 没有严格的 date 类型, 但用字符串语法跟 julianday 配合一致.

每一条查询都映射回业务问题. 如果以后加 query, 也要遵循"先有业务问题, 再有 SQL" 的顺序, 不要凭空补 SQL 凑数.
