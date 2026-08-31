# 医疗器械: 骨科植入物追踪 SQL 查询参考

> **数据所属系统：** MAOHN（米德大西洋骨科医疗网络）植入物登记系统。
> **视角：** 医院侧。所有 "成本" 口径都是 MAOHN 站在医院方算的成本；所有 "召回" 口径都是 MAOHN 站在患者安全响应方做的事。
> **业务背景, 行业科普, 术语表请见** `01-medical_devices_orthopedic_implant_tracking_high_business_context-cn.md`; **表结构与字段定义请见** `02-medical_devices_orthopedic_implant_tracking_high_er_document-cn.md`。

---

## 如何使用本文档

这份文档是写给刚读完 `01` 号业务背景和 `02` 号 ER 文档, 正准备被经理派去做查询的新分析师的。它不是一份 "SQL 语法速查", 而是 20 道 **从真实业务问题出发** 的练习: 每道题都对应 MAOHN 内部某个具体岗位真实会问的一个问题, 也都能追溯回 `01` 号文档第 5 节列出的五大业务问题之一。

**每道题都按同样的五段式组织, 建议照顺序读:**

1. **业务背景**: 谁在问, 为什么现在问, 答案要支撑什么决策。先看懂这一段, 才知道这道题为什么值得做。
2. **类别 / 难度 / 业务角色**: 三个标签, 帮你判断这题练的是哪种 SQL 技术, 难到什么程度, 服务的是哪个岗位。
3. **解题思路**: 在你看到 SQL 之前, 先讲清楚要碰哪些表, join 怎么搭, 聚合的粒度是什么, 哪里有坑 (fan-out, NULL 语义, 该用 LEFT 还是 INNER)。这一段是这份文档最该精读的部分。
4. **SQL**: 可直接在生成出来的 SQLite 库上运行的查询。读的时候对照上一段的思路看。
5. **预期结果与业务结论**: 结果长什么样, 关键数字落在什么量级, 以及拿到结果后分析师下一步该做什么。跑出数字只是分析的开始, 不是终点。

**关于 REFERENCE_DATE。** 整个数据集的日期都锚定在固定参考时点 `2026-06-01` (生成器里的 `NOW`)。涉及 "当前" 语义的查询用 `DATE('now')` 或固定字面量, 结果会随系统时钟与该锚点的距离而漂移; 要复现就重新跑生成器。

如果同一类指标有两种合理算法（比如 "事件率" 可以按手术算也可以按植入物算），本文档 **指定一种唯一口径** 并贯穿全文。

**统一口径如下：**

| 指标 | 唯一口径 | 为什么 |
|---|---|---|
| **不良事件率** | 每 100 **手术** 的事件数（不是每 100 植入物） | 一台用了多枚植入物的手术里出现 1 起事件，应该算 1 次受影响的手术，不是 N 次 |
| **"被召回影响的"** | 已植入的某单元，其 `lot_id` 与某条 lot 级召回匹配，**或** 其 `product_id` 与某条全产品召回（`recall.lot_id IS NULL`）匹配 | 两类作用域都是真实存在的；SQL 必须两种都处理 |
| **植入器械成本** | 在该单元 `received_date` 时点生效的 `pricing_history.contracted_price_usd`（point-in-time 价格） | MSRP 会误导，因为合同价随时间和合同类型变 |
| **"已用 (Used)"** | 该单元出现在 `surgery_implant` | silver 层 `inventory.status = 'Used'` 是从这里派生的，所以两边永远一致 |
| **批次质检状态** | 该批次最近一条 `result IN ('Pass', 'Fail')` 的 `quality_test_event`（`Conditional` 不算定论） | |

**金层视图** （Q18 / Q19 使用）是预定义的 `CREATE VIEW`，把常用的 join 和派生包好。原始事件仍然驱动一切；视图只是便利封装。

---

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|---|---|---|---|
| 1 | 各品类植入物使用量汇总 | 高管 | 聚合 + Join | Basic |
| 2 | 活动召回涉及的患者清单（lot 级 + 全产品级） | 经理 | 多表 Join | Advanced |
| 3 | 医生手术量排名 | 经理 | 窗口函数 | Intermediate |
| 4 | 各制造商不良事件率 | 分析师 | 聚合 + Join | Intermediate |
| 5 | 未来 90 天内即将过期的可用库存 | 运营 | 日期范围 | Basic |
| 6 | 高价值产品 FDA 在审清单 | 监管 | Join + 聚合 | Intermediate |
| 7 | 近 12 个月手术量环比 | 高管 | 窗口 + 日期 | Intermediate |
| 8 | Class I 召回涉及患者全量名单 | 运营 | 多表 Join + CASE | Advanced |
| 9 | 各医院库存周转率 | 分析师 | 聚合 + Join | Intermediate |
| 10 | GPO 合同价合规审计 | 财务 | CTE + Join | Advanced |
| 11 | 超出 SLA 仍未确认的召回通知 | 运营 | 日期过滤 + CASE | Intermediate |
| 12 | 各术式平均手术时长 | 分析师 | 聚合 + GROUP BY | Basic |
| 13 | 最近一次质检失败的批次 | 经理 | CTE + 窗口 | Advanced |
| 14 | 不良事件全溯源报告 | 分析师 | 多表 Join | Advanced |
| 15 | 按手术量校准的高不良事件率医生 | 经理 | CTE + 窗口函数 | Advanced |
| 16 | 各医院各存放地的库存状态分布 | 运营 | 聚合 + GROUP BY | Basic |
| 17 | 各 FDA 申报类型的批准率 | 监管 | 条件聚合 | Intermediate |
| 18 | 各医院年度植入成本（使用 `v_hospital_monthly_implant_cost` 金层视图） | 财务 | 视图 + 聚合 | Intermediate |
| 19 | 召回响应 SLA 合规度（使用 `v_recall_response_sla` 金层视图） | 经理 | 视图 + CTE | Advanced |
| 20 | 患者 2 年内翻修率 | 分析师 | CTE + 自连接 | Advanced |

---

## 查询

### Query 1：各品类植入物使用量汇总

**业务背景：**
MAOHN 首席医疗官（CMO）每季度复盘全网络 12 家医院骨科植入物的使用结构，把使用量份额最高的品类拿出来推动采购委员会做战略级供应商谈判。份额到 35% 以上的品类有理由让供应商签订更高的服务水平承诺。

**类别：** 聚合 + Join
**难度：** Basic
**业务角色：** 高管

**解题思路：**
这题要把 "使用量" 从品类一路 join 到 `surgery_implant`（只有出现在这张表里的单元才算真正被植入用掉）。链路是 `implant_category → implant_product → implant_lot → inventory → surgery_implant`，全程 INNER JOIN，因为没被用过的库存不该进分子。先用一个 CTE `used` 把每一件已用植入物连同它的品类摊平成一行，再按品类 GROUP BY 计数；占比的分母用对同一个 CTE 的子查询 `SELECT COUNT(*) FROM used`，分子分母同源，百分比加总必然是 100%。一次 GROUP BY 就够，不需要窗口函数。

```sql
-- 统计各品类的使用量及全网络占比。
-- 分母用 CTE 内 FK-trimmed 后的行数，所以占比和必然为 100%。
WITH used AS (
    SELECT ic.id AS category_id, ic.name AS category_name, si.id AS si_id
    FROM implant_category ic
    JOIN implant_product ip ON ic.id = ip.category_id
    JOIN implant_lot il ON ip.id = il.product_id
    JOIN inventory i ON il.id = i.lot_id
    JOIN surgery_implant si ON i.id = si.inventory_id
)
SELECT
    category_name,
    COUNT(si_id) AS total_implants_used,
    ROUND(COUNT(si_id) * 100.0 / (SELECT COUNT(*) FROM used), 2) AS percentage_of_total
FROM used
GROUP BY category_id, category_name
ORDER BY total_implants_used DESC;
```

**预期结果：** 各品类的使用量排名 + 占比。典型信号：1–2 个品类占走 50% 以上的量，必然是采购支出的主战场。

---

### Query 2：活动召回涉及的患者清单（lot 级 + 全产品级）

**业务背景：**
MAOHN 风控总监需要随时拿到 "当前所有活动召回所牵涉到的全部已植入患者" 的清单 —— 既要覆盖 lot 级召回（只拉某一批 bad lot），也要覆盖全产品召回（整条产品线召回）。落下任何一类都已经在同行医院引发过监管处罚。本 query 必须同时正确处理两种 scope。

**类别：** 多表 Join
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
召回有两种作用域，这题最大的坑就是必须同时处理：lot 级召回（`recall.lot_id` 非空）只波及那一批，全产品召回（`recall.lot_id IS NULL`）波及整条产品线。所以 `recall` 连 `implant_lot` 的 ON 子句写成 `(r.lot_id = il.id) OR (r.lot_id IS NULL AND il.product_id = r.product_id)`，一条 ON 把两种 scope 都覆盖。从 lot 再顺着 `inventory → surgery_implant → surgery → patient` 落到具体患者。通知状态用 `LEFT JOIN recall_notification`，不能换成 INNER，否则还没发通知的患者会直接消失，而那些恰恰是最该联系的人；再用 CASE 把 "没通知 / 通知未确认 / 已确认" 三态标出来。最后只保留 `status = 'Active'` 的召回。

```sql
-- 受影响 = (召回是 lot 级 AND inventory.lot_id 命中) 
--          OR (召回是全产品 AND inventory 对应产品命中)。
-- 下面这条 ON 子句精确表达了这一作用域。
SELECT
    r.recall_number,
    r.recall_class,
    r.recall_reason,
    p.mrn,
    p.first_name || ' ' || p.last_name AS patient_name,
    ip.product_name,
    il.lot_number,
    s.surgery_date,
    h.name AS hospital_name,
    CASE
        WHEN rn.id IS NULL THEN 'NOT NOTIFIED'
        WHEN rn.acknowledgment_date IS NULL THEN 'NOTIFIED - NO ACK'
        ELSE 'ACKNOWLEDGED'
    END AS notification_status
FROM recall r
JOIN implant_product ip ON r.product_id = ip.id
JOIN implant_lot il
    ON (r.lot_id = il.id)                                  -- lot 级召回
    OR (r.lot_id IS NULL AND il.product_id = r.product_id) -- 全产品召回
JOIN inventory i ON il.id = i.lot_id
JOIN surgery_implant si ON i.id = si.inventory_id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN hospital h ON s.hospital_id = h.id
LEFT JOIN recall_notification rn
    ON r.id = rn.recall_id AND si.id = rn.surgery_implant_id
WHERE r.status = 'Active'
ORDER BY r.recall_class, p.last_name;
```

**预期结果：** 每行 = 一条（召回 × 一件已植入受影响单元）。Class I 行是紧急处置项；`NOT NOTIFIED` 行直接进入主动联系工作流。

---

### Query 3：医生手术量排名

**业务背景：**
医院运营总监按手术量给医生排名，用来决定 OR 时段分配和高产医生的留任策略。亚专科内排名能把 "本专科真高产" 和 "总量大但全科分摊" 区分开。

**类别：** 窗口函数
**难度：** Intermediate
**业务角色：** 经理

**解题思路：**
一次 `surgeon JOIN surgery` 之后按医生 GROUP BY，就能拿到每位医生的手术量和平均时长。排名用两个窗口函数：`RANK() OVER (ORDER BY COUNT(...) DESC)` 给全院总排名，`DENSE_RANK() OVER (PARTITION BY specialty ORDER BY COUNT(...) DESC)` 给同专科内排名。窗口函数可以直接对聚合结果 `COUNT(surg.id)` 排序，因为它们在 GROUP BY 之后才求值。注意 RANK 与 DENSE_RANK 的差别：前者遇到并列会跳号，后者不跳；专科内人数少，用 DENSE_RANK 读起来更顺。`LIMIT 20` 取头部医生。

```sql
SELECT
    s.first_name || ' ' || s.last_name AS surgeon_name,
    s.specialty,
    COUNT(surg.id) AS total_surgeries,
    ROUND(AVG(surg.duration_minutes), 1) AS avg_duration_minutes,
    RANK()       OVER (ORDER BY COUNT(surg.id) DESC) AS overall_rank,
    DENSE_RANK() OVER (PARTITION BY s.specialty ORDER BY COUNT(surg.id) DESC) AS specialty_rank
FROM surgeon s
JOIN surgery surg ON s.id = surg.surgeon_id
GROUP BY s.id, s.first_name, s.last_name, s.specialty
ORDER BY total_surgeries DESC
LIMIT 20;
```

**预期结果：** 量最大的 Top 20 医生 + 同专科排名。手术量高且平均时长短的医生，是培养内部 mentor 的候选。

---

### Query 4：各制造商不良事件率

**业务背景：**
临床质量总监按 **每 100 手术** 算每家制造商的不良事件率（这是本文档统一的口径），仅保留数据中至少有 10 台手术使用其器械的制造商，让结果有统计意义。该指标进供应商记分卡。

**类别：** 聚合 + Join
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
难点在 "事件率按手术算，不按植入物算" 这条统一口径。一台手术可能用了同一厂商的多枚植入物，直接数植入物会把这台手术重复计数。所以先用 CTE 把粒度压到 (厂商, 手术) 一行：`manufacturer → implant_product → implant_lot → inventory → surgery_implant`，再 `LEFT JOIN adverse_event`（LEFT 保证没出事的手术也留在分母里），在这一层 `COUNT(ae.id)` 得到 "这台手术上这家厂商的植入物出了几起事件"。外层再 `COUNT(DISTINCT surgery_id)` 当分母，`SUM(CASE WHEN events > 0 THEN 1 ELSE 0 END)` 当分子。`HAVING COUNT(DISTINCT surgery_id) >= 10` 滤掉样本太小的厂商，否则一两台手术就能算出吓人的百分比。

```sql
-- 按统一口径，"事件率" 按手术算，不按植入物算。
-- 一台多植入物手术里任何一枚植入物出事，这台手术算 1 次。
WITH manufacturer_surgeries AS (
    SELECT
        m.id AS manufacturer_id,
        m.name AS manufacturer_name,
        m.country,
        si.surgery_id,
        COUNT(ae.id) AS events_on_this_surgery_for_this_mfr
    FROM manufacturer m
    JOIN implant_product ip ON m.id = ip.manufacturer_id
    JOIN implant_lot il ON ip.id = il.product_id
    JOIN inventory i ON il.id = i.lot_id
    JOIN surgery_implant si ON i.id = si.inventory_id
    LEFT JOIN adverse_event ae ON si.id = ae.surgery_implant_id
    GROUP BY m.id, m.name, m.country, si.surgery_id
)
SELECT
    manufacturer_name,
    country,
    COUNT(DISTINCT surgery_id) AS total_surgeries,
    SUM(CASE WHEN events_on_this_surgery_for_this_mfr > 0 THEN 1 ELSE 0 END) AS surgeries_with_event,
    ROUND(
        SUM(CASE WHEN events_on_this_surgery_for_this_mfr > 0 THEN 1 ELSE 0 END) * 100.0
        / COUNT(DISTINCT surgery_id),
        2
    ) AS adverse_event_rate_per_100_surgeries
FROM manufacturer_surgeries
GROUP BY manufacturer_id, manufacturer_name, country
HAVING COUNT(DISTINCT surgery_id) >= 10
ORDER BY adverse_event_rate_per_100_surgeries DESC;
```

**预期结果：** 事件率偏高的制造商浮到顶部，触发质量审查或合同重谈。

---

### Query 5：未来 90 天内即将过期的可用库存

**业务背景：**
供应链分析师每天跑一次这个查询，找出高价值且 90 天内到期的 `Available` 单元。`unit_cost` 用 **该单元 `received_date` 时点的 `pricing_history` 价格**，不是某个固定目录价 —— 这才是 MAOHN 真实付出去的钱。

**类别：** 日期范围 + Join
**难度：** Intermediate
**业务角色：** 运营

**解题思路：**
主表是 `inventory`，两条过滤：`status = 'Available'`，以及所属 lot 在未来 90 天内过期（`expiration_date BETWEEN DATE('now') AND DATE('now','+90 days')`）。价格是这题的关键：不能用产品的当前目录价，要用 **该单元收货当时** 生效的合同价，所以 `pricing_history` 的 join 谓词带上 `effective_date <= received_date AND (end_date IS NULL OR end_date > received_date)` 这组 point-in-time 条件。用 LEFT JOIN 接价格，万一某单元收货时点找不到价格行也不至于整行丢失。按到期日升序排，越紧急越靠前。

```sql
-- 拉出 'Available' 且所属 lot 在 90 天内过期的单元。
-- 价格用收货当时的 contracted price。
SELECT
    i.serial_number,
    ip.product_name,
    m.name AS manufacturer,
    il.lot_number,
    il.expiration_date,
    CAST(JULIANDAY(il.expiration_date) - JULIANDAY('now') AS INTEGER) AS days_until_expiration,
    i.location,
    h.name AS hospital,
    ph.contracted_price_usd AS unit_cost_at_receipt,
    i.is_consignment
FROM inventory i
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
JOIN manufacturer m ON ip.manufacturer_id = m.id
JOIN hospital h ON i.hospital_id = h.id
LEFT JOIN pricing_history ph
    ON ph.product_id = ip.id
   AND ph.manufacturer_id = m.id
   AND ph.effective_date <= i.received_date
   AND (ph.end_date IS NULL OR ph.end_date > i.received_date)
WHERE i.status = 'Available'
  AND il.expiration_date BETWEEN DATE('now') AND DATE('now', '+90 days')
ORDER BY il.expiration_date ASC, ph.contracted_price_usd DESC;
```

**预期结果：** 按紧迫程度和价值排序的清单。`is_consignment = TRUE` 的单元财务损失较小 —— 所有权在厂家手里。

---

### Query 6：高价值产品 FDA 在审清单

**业务背景：**
MAOHN 监管事务部要预判什么时候会有新的高价值技术放入 formulary（院内可选用器械目录），需要盯住制造商在 FDA 在审的产品。"高价值" 按当前合同价定义。

**类别：** Join + 聚合
**难度：** Intermediate
**业务角色：** 监管

**解题思路：**
"当前价格" 这里用简化口径，即 SCD2 里 `end_date IS NULL` 的那一行（代表现在生效），先用 CTE `current_price` 取出来。主体是 `implant_product` join `regulatory_submission`，只留 `status = 'Pending'` 的在审记录，再 `LEFT JOIN current_price` 接上当前合同价，用 `cp.contracted_price_usd > 5000` 卡 "高价值"。`days_in_review` 用 `JULIANDAY('now') - JULIANDAY(submission_date)` 算在审天数。要留意这道题的当前价口径比 Q5 / Q10 / Q18 的 point-in-time 口径简单，因为这里只关心 "现在值不值钱"，不关心历史某个时点的价格。

```sql
-- "当前价格" = SCD2 中 end_date IS NULL 的那行，是 "现在生效" 的简写。
-- 任意时间点的 point-in-time 价格请参考 Q5/Q10/Q18 的完整谓词。
WITH current_price AS (
    SELECT
        product_id,
        manufacturer_id,
        contracted_price_usd
    FROM pricing_history
    WHERE end_date IS NULL
)
SELECT
    ip.product_name,
    ip.model_number,
    cp.contracted_price_usd AS current_contracted_price,
    m.name AS manufacturer,
    ic.name AS category,
    rs.submission_type,
    rs.submission_number,
    rs.submission_date,
    CAST(JULIANDAY('now') - JULIANDAY(rs.submission_date) AS INTEGER) AS days_in_review,
    rs.regulatory_body
FROM implant_product ip
JOIN manufacturer m ON ip.manufacturer_id = m.id
JOIN implant_category ic ON ip.category_id = ic.id
JOIN regulatory_submission rs ON ip.id = rs.product_id
LEFT JOIN current_price cp ON cp.product_id = ip.id AND cp.manufacturer_id = m.id
WHERE rs.status = 'Pending'
  AND cp.contracted_price_usd > 5000
ORDER BY cp.contracted_price_usd DESC, rs.submission_date ASC;
```

**预期结果：** 高价值在审产品 + 在审天数。510(k) 在审超过 180 天就属于偏慢，值得关注。

---

### Query 7：近 12 个月手术量环比

**业务背景：**
MAOHN COO 需要真实的滚动 12 个月视图来识别季节性 pattern 或量级下滑。早期版本忘记加日期过滤，跑成全历史 —— 这一版显式加上。

**类别：** 窗口函数 + 日期分析
**难度：** Intermediate
**业务角色：** 高管

**解题思路：**
先用 CTE 把手术按月聚合，关键是别忘了 `WHERE surgery_date >= DATE('now','-12 months')` 这条日期过滤（早期版本漏了它，结果跑成全历史）。月份用 `STRFTIME('%Y-%m', surgery_date)` 取。环比用窗口函数 `LAG(surgery_count) OVER (ORDER BY surgery_month)` 取上个月的值，再算差值和百分比；百分比的分母套 `NULLIF(..., 0)` 兜底，避免上月为 0 时除零。窗口函数比自连接干净，因为它天然按月份有序地取前一行。

```sql
WITH monthly AS (
    SELECT
        STRFTIME('%Y-%m', surgery_date) AS surgery_month,
        COUNT(*) AS surgery_count
    FROM surgery
    WHERE surgery_date >= DATE('now', '-12 months')
    GROUP BY STRFTIME('%Y-%m', surgery_date)
)
SELECT
    surgery_month,
    surgery_count,
    LAG(surgery_count) OVER (ORDER BY surgery_month) AS prev_month_count,
    surgery_count - LAG(surgery_count) OVER (ORDER BY surgery_month) AS volume_change,
    ROUND(
        (surgery_count - LAG(surgery_count) OVER (ORDER BY surgery_month)) * 100.0
        / NULLIF(LAG(surgery_count) OVER (ORDER BY surgery_month), 0),
        1
    ) AS percent_change
FROM monthly
ORDER BY surgery_month;
```

**预期结果：** 按时间序输出 12 行 + 环比。月度下滑 > 10% 应触发原因排查；12 月的季节性回落用来指导排班。

---

### Query 8：Class I 召回涉及患者全量名单

**业务背景：**
某条 Class I 召回通知到达，CMO 需要在一个结果集里拿到联系患者所需的全部信息。**与早期版本最关键的差别：本版同时处理 lot 级和全产品级 Class I 召回** —— 旧版本悄悄漏掉了全产品召回，而设计缺陷类召回常常是全产品的。

**类别：** 多表 Join + CASE
**难度：** Advanced
**业务角色：** 运营

**解题思路：**
结构上和 Q2 是同一套 dual-scope join（lot 级 OR 全产品级），但这道题是给 CMO 准备 "拿起电话就能联系" 的全字段清单，所以 join 面更宽：一路带出患者人口学、主刀医生电话、医院电话、保险状态。过滤收紧到 `recall_class = 'Class I' AND status = 'Active'`。用 `SELECT DISTINCT` 去重，因为宽 join 下同一患者可能因多件受影响单元出现多行。`recall_scope` 用 CASE 区分全产品和 lot 级，方便协调员把全产品召回单独拎出来（设计缺陷类召回常常是全产品的，也是最容易被漏掉的一类）。

```sql
SELECT DISTINCT
    r.recall_number,
    r.recall_reason,
    p.mrn,
    p.first_name || ' ' || p.last_name AS patient_name,
    p.date_of_birth,
    CAST((JULIANDAY('now') - JULIANDAY(p.date_of_birth)) / 365.25 AS INTEGER) AS patient_age,
    ip.product_name,
    ip.model_number,
    i.serial_number,
    s.surgery_date,
    s.procedure_name,
    si.implant_site,
    surg.first_name || ' ' || surg.last_name AS surgeon_name,
    surg.phone AS surgeon_phone,
    h.name AS hospital_name,
    h.phone AS hospital_phone,
    COALESCE(p.insurance_provider, 'UNINSURED') AS insurance_status,
    CASE
        WHEN r.lot_id IS NULL THEN 'PRODUCT-WIDE'
        ELSE 'LOT-SCOPED'
    END AS recall_scope
FROM recall r
JOIN implant_product ip ON r.product_id = ip.id
JOIN implant_lot il
    ON (r.lot_id = il.id)
    OR (r.lot_id IS NULL AND il.product_id = r.product_id)
JOIN inventory i ON il.id = i.lot_id
JOIN surgery_implant si ON i.id = si.inventory_id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN surgeon surg ON s.surgeon_id = surg.id
JOIN hospital h ON s.hospital_id = h.id
WHERE r.recall_class = 'Class I'
  AND r.status = 'Active'
ORDER BY s.surgery_date DESC;
```

**预期结果：** 逐患者明细表，带 `recall_scope` 标记，方便协调员把全产品召回拎出来单独处置。

---

### Query 9：各医院库存周转率

**业务背景：**
区域供应链总监找出资金占用过高的 "慢动" 医院。"Used" 是从 `inventory.status` 来的（而 status 又是从 `inventory_movement` 派生），所以指标和审计日志完全一致。

**类别：** 聚合 + Join
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
主体是 `hospital JOIN inventory`，按医院 GROUP BY。周转率口径是 `Used 单元数 / 全部库存单元数`，用 `SUM(CASE WHEN status='Used' ...)` 和 `COUNT(*)` 算；这里的 `Used` 来自 `inventory.status`，而 status 又派生自 `inventory_movement`，所以和审计日志完全一致。资金占用 `capital_tied_up` 是个有业务含义的坑：只算 `status='Available' AND NOT is_consignment` 的单元价值，因为寄售单元在被用之前医院根本没付钱，不该算进占用的资金。价格用当前价 CTE 接上。按周转率升序排，最 "慢动" 的医院浮到最上面。

```sql
WITH current_price AS (
    SELECT product_id, manufacturer_id, contracted_price_usd
    FROM pricing_history
    WHERE end_date IS NULL
)
SELECT
    h.name AS hospital_name,
    h.city,
    h.state,
    COUNT(*) AS total_inventory_units,
    SUM(CASE WHEN i.status = 'Available' THEN 1 ELSE 0 END) AS available_units,
    SUM(CASE WHEN i.status = 'Used' THEN 1 ELSE 0 END) AS used_units,
    ROUND(
        SUM(CASE WHEN i.status = 'Used' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
    ) AS turnover_percentage,
    ROUND(
        SUM(CASE WHEN i.status = 'Available' AND NOT i.is_consignment
                 THEN cp.contracted_price_usd ELSE 0 END), 2
    ) AS capital_tied_up_usd
FROM hospital h
JOIN inventory i ON h.id = i.hospital_id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
LEFT JOIN current_price cp ON cp.product_id = ip.id AND cp.manufacturer_id = ip.manufacturer_id
GROUP BY h.id, h.name, h.city, h.state
ORDER BY turnover_percentage ASC;
```

**预期结果：** 周转率低 + 占用资金高的医院是库存调拨候选。Consignment 单元在 `capital_tied_up_usd` 里被剔除，因为 MAOHN 在用之前不拥有它。

---

### Query 10：GPO 合同价合规审计

**业务背景：**
采购负责人确认 MAOHN 是不是真按合同价付的 GPO 货款。本 query 把收货时点的合同价对照行业基线（这里用 `list_price_usd` 代表 MSRP）比较折扣。长期超付要触发与供应商的对话。

**类别：** CTE + Join
**难度：** Advanced
**业务角色：** 财务

**解题思路：**
这题审 "我们实付的折扣是否合理"。先用 CTE `unit_at_receipt` 把每个收货单元接上它 **收货当时** 的合同价（又是 point-in-time 谓词），顺手算出折扣率 `(list - contracted) / list`。外层按 (厂商, 合同类型) 聚合，看每组的平均目录价、平均合同价、平均折扣，以及相对目录价省下的总额。这里 join `pricing_history` 必须用时点谓词而不是当前价，否则历史收货会被套上今天的价格，审计就失真了。读结果时对照行业基线：GPO 合同折扣应落在 10% 到 30%，明显偏低的组就是该重谈合同的信号。

```sql
WITH unit_at_receipt AS (
    SELECT
        i.id AS inventory_id,
        i.received_date,
        ip.id AS product_id,
        ip.product_name,
        m.name AS manufacturer,
        ph.contract_type,
        ph.list_price_usd,
        ph.contracted_price_usd,
        ROUND(
            (ph.list_price_usd - ph.contracted_price_usd) * 100.0
            / NULLIF(ph.list_price_usd, 0),
            1
        ) AS discount_pct
    FROM inventory i
    JOIN implant_lot il ON i.lot_id = il.id
    JOIN implant_product ip ON il.product_id = ip.id
    JOIN manufacturer m ON ip.manufacturer_id = m.id
    JOIN pricing_history ph
        ON ph.product_id = ip.id
       AND ph.manufacturer_id = m.id
       AND ph.effective_date <= i.received_date
       AND (ph.end_date IS NULL OR ph.end_date > i.received_date)
)
SELECT
    manufacturer,
    contract_type,
    COUNT(*) AS units_received,
    ROUND(AVG(list_price_usd), 2)        AS avg_list_price,
    ROUND(AVG(contracted_price_usd), 2)  AS avg_contracted_price,
    ROUND(AVG(discount_pct), 1)          AS avg_discount_pct,
    ROUND(SUM(list_price_usd - contracted_price_usd), 2) AS total_savings_vs_list
FROM unit_at_receipt
GROUP BY manufacturer, contract_type
ORDER BY total_savings_vs_list DESC;
```

**预期结果：** GPO 合同应该落在 10–30% 折扣区间；Consignment 显示 0%（本模型 Consignment 是按 MSRP 入账，使用时再结算）。GPO 折扣不到 5% 的应触发合同复盘。

---

### Query 11：超出 SLA 仍未确认的召回通知

**业务背景：**
召回协调员盯已发未确认的通知，对照按召回等级设的 FDA 对齐 SLA（Class I 3 天、Class II 30 天、Class III 60 天）。

**类别：** 日期过滤 + CASE
**难度：** Intermediate
**业务角色：** 运营

**解题思路：**
主表是 `recall_notification`，先用 `acknowledgment_date IS NULL` 筛出 "已发未确认" 的，再 join 回 `recall` 拿等级。SLA 阈值随等级变，用 `CASE recall_class WHEN 'Class I' THEN 3 ...` 算出该行的 SLA 天数，然后在 WHERE 里用 `JULIANDAY('now') - JULIANDAY(notification_date) > 那个 CASE` 把超时的留下。其余 join 到患者、医院、产品只是为了让清单可读可联系。按等级和逾期天数排序，让 Class I 的逾期项顶到最上面。

```sql
SELECT
    rn.id AS notification_id,
    r.recall_number,
    r.recall_class,
    r.recall_reason,
    rn.notification_date,
    CAST(JULIANDAY('now') - JULIANDAY(rn.notification_date) AS INTEGER) AS days_since_notification,
    CASE r.recall_class
        WHEN 'Class I' THEN 3
        WHEN 'Class II' THEN 30
        WHEN 'Class III' THEN 60
    END AS sla_days,
    rn.notified_party,
    rn.notification_method,
    p.mrn,
    p.first_name || ' ' || p.last_name AS patient_name,
    ip.product_name,
    h.name AS hospital_name
FROM recall_notification rn
JOIN recall r ON rn.recall_id = r.id
JOIN surgery_implant si ON rn.surgery_implant_id = si.id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN hospital h ON s.hospital_id = h.id
JOIN inventory i ON si.inventory_id = i.id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
WHERE rn.acknowledgment_date IS NULL
  AND r.status = 'Active'
  AND (JULIANDAY('now') - JULIANDAY(rn.notification_date)) > (
        CASE r.recall_class
            WHEN 'Class I' THEN 3
            WHEN 'Class II' THEN 30
            WHEN 'Class III' THEN 60
        END
      )
ORDER BY r.recall_class, days_since_notification DESC;
```

**预期结果：** 超 SLA 的行立即上升。Class I 超 3 天就等于在 "等监管发现"。

---

### Query 12：各术式平均手术时长

**业务背景：**
OR 排班经理用历史时长校准 block-time。方差大的术式排班缓冲就要宽一些，方差小的可以排紧。

**类别：** 聚合 + GROUP BY
**难度：** Basic
**业务角色：** 分析师

**解题思路：**
最简单的一道，单表 `surgery` 就够。按 (CPT 码, 术式名) GROUP BY，算 COUNT、平均 / 最小 / 最大时长。`WHERE duration_minutes IS NOT NULL` 先排掉没记时长的行，否则 AVG 会忽略它们但 COUNT(*) 仍计数，口径不一致。`HAVING COUNT(*) >= 5` 滤掉样本太少、极值没代表性的术式。极差（max 减 min）大的术式说明耗时不稳定，排班缓冲要留宽。

```sql
SELECT
    procedure_name,
    procedure_code,
    COUNT(*) AS procedure_count,
    ROUND(AVG(duration_minutes), 1)          AS avg_duration_minutes,
    MIN(duration_minutes)                    AS min_duration,
    MAX(duration_minutes)                    AS max_duration,
    ROUND(AVG(duration_minutes) / 60.0, 1)   AS avg_duration_hours
FROM surgery
WHERE duration_minutes IS NOT NULL
GROUP BY procedure_code, procedure_name
HAVING COUNT(*) >= 5
ORDER BY procedure_count DESC;
```

**预期结果：** 按 CPT 列出平均时长 + 极值。TKA 平均 135 分钟、范围 90–210 分钟 → 排班按 2.5 小时块即可。

---

### Query 13：最近一次质检失败的批次

**业务背景：**
QA 工程师验证 "最近一次定论性质检 = Fail 的批次" 没有混入库存。判断基于原始 `quality_test_event` 表 —— `implant_lot.quality_test_passed` 这个布尔字段被故意删除，因为一个布尔表达不了多阶段质检。

**类别：** CTE + 窗口函数
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
批次质检状态不是一个存好的布尔，而是 "最近一条定论性结果"。所以先用 CTE `ranked` 只取 `result IN ('Pass','Fail')` 的事件（把 `Conditional` 排除，因为它不算定论），用 `ROW_NUMBER() OVER (PARTITION BY lot_id ORDER BY test_date DESC)` 给每批的检测按时间倒排。`rn = 1 AND result = 'Fail'` 就是 "最近一次定论是失败" 的批次。再 `LEFT JOIN inventory` 看这些坏批次有没有单元还在库（Available）甚至已被用掉（Used）。`GROUP_CONCAT(DISTINCT h.name)` 把波及的医院拼成一列。

```sql
-- "批次质检状态" = 最近一条 Pass/Fail 的结果（Conditional 不算定论）。
WITH ranked AS (
    SELECT
        lot_id,
        result,
        test_date,
        ROW_NUMBER() OVER (
            PARTITION BY lot_id
            ORDER BY test_date DESC
        ) AS rn
    FROM quality_test_event
    WHERE result IN ('Pass', 'Fail')
),
failed_lots AS (
    SELECT lot_id FROM ranked WHERE rn = 1 AND result = 'Fail'
)
SELECT
    il.lot_number,
    ip.product_name,
    m.name AS manufacturer,
    il.manufacture_date,
    il.quantity_manufactured,
    COUNT(i.id) AS units_in_inventory,
    SUM(CASE WHEN i.status = 'Available' THEN 1 ELSE 0 END) AS available_units,
    SUM(CASE WHEN i.status = 'Used'      THEN 1 ELSE 0 END) AS used_units,
    GROUP_CONCAT(DISTINCT h.name) AS hospitals_affected
FROM failed_lots fl
JOIN implant_lot il ON fl.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
JOIN manufacturer m ON ip.manufacturer_id = m.id
LEFT JOIN inventory i ON il.id = i.lot_id
LEFT JOIN hospital h ON i.hospital_id = h.id
GROUP BY il.id, il.lot_number, ip.product_name, m.name,
         il.manufacture_date, il.quantity_manufactured
ORDER BY used_units DESC, available_units DESC;
```

**预期结果：** 理想情况是没有任何行的 `used_units > 0`。任意一行 `Available > 0` 的失败批次都要立刻隔离。

---

### Query 14：不良事件全溯源报告

**业务背景：**
临床质量分析师准备每季度 FDA MAUDE 评审包。每行带完整的 UDI-DI / UDI-PI 追溯链 + 临床上下文。

**类别：** 多表 Join
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
这是一张 "宽表" 报告，从 `adverse_event` 出发，把 FDA MAUDE 评审需要的全链路一次 join 齐：经 `surgery_implant` 上溯到手术、患者、主刀、医院，再下接 `inventory → implant_lot → implant_product → manufacturer → implant_category` 拿到完整的 UDI-DI / UDI-PI 追溯链。两个日期派生值得注意：`patient_age` 用 **手术当时** 而非 `'now'` 计算（`JULIANDAY(surgery_date) - JULIANDAY(date_of_birth)`），这样数据集放久了年龄也不漂；`days_post_surgery` 是事件距手术的天数，因为生成器强制 `event_date > implantation_timestamp`，它必然非负。全程 INNER JOIN，因为每起不良事件都必然挂在一件真实植入单元上。

```sql
SELECT
    ae.id AS event_id,
    ae.event_date,
    ae.event_type,
    ae.severity,
    ae.fda_mdr_number,
    p.mrn,
    -- patient_age 用手术当时算（不是 'now'），即使数据集放久了语义也稳定。
    CAST((JULIANDAY(s.surgery_date) - JULIANDAY(p.date_of_birth)) / 365.25 AS INTEGER) AS patient_age,
    p.gender,
    p.allergies,
    s.surgery_date,
    CAST(JULIANDAY(ae.event_date) - JULIANDAY(s.surgery_date) AS INTEGER) AS days_post_surgery,
    s.procedure_name,
    s.surgery_type,
    si.implant_site,
    ip.product_name,
    ip.udi_di,
    i.udi_pi,
    ip.model_number,
    m.name AS manufacturer,
    ic.name AS implant_category,
    surg.first_name || ' ' || surg.last_name AS surgeon_name,
    surg.specialty,
    surg.years_experience,
    h.name AS hospital_name,
    ae.patient_outcome,
    ae.corrective_action,
    ae.reported_by,
    ae.reported_date
FROM adverse_event ae
JOIN surgery_implant si ON ae.surgery_implant_id = si.id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN surgeon surg ON s.surgeon_id = surg.id
JOIN hospital h ON s.hospital_id = h.id
JOIN inventory i ON si.inventory_id = i.id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
JOIN manufacturer m ON ip.manufacturer_id = m.id
JOIN implant_category ic ON ip.category_id = ic.id
ORDER BY ae.severity DESC, ae.event_date DESC;
```

**预期结果：** 全溯源的逐事件明细。`days_post_surgery` 一定 ≥ 0，因为生成器强制 `event_date > implantation_timestamp`。

---

### Query 15：按手术量校准的高不良事件率医生

**业务背景：**
医务总监做同行评议，用统一口径的 **per-surgery 事件率**，最少 20 台手术起评以排除小样本噪声。

**类别：** CTE + 窗口函数
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
又是 per-surgery 口径，但这次按医生汇总。第一个 CTE `per_surgery_events` 把粒度压到 (医生, 手术) 一行，用 `MAX(CASE WHEN ae.id IS NOT NULL ...)` 标记 "这台手术有没有出过事件"（用 MAX 是因为一台手术多枚植入物里只要有一起就算这台中招）。第二个 CTE 按医生聚合，`HAVING COUNT(*) >= 20` 设最低手术量门槛，排除小样本噪声（做 3 台中 1 台的医生不该被排到 33% 的吓人率）。最后 `RANK() OVER (ORDER BY 事件率 DESC)` 给离群医生排名，进同行评议。

```sql
WITH per_surgery_events AS (
    -- 每行 = 一台 (医生, 手术)，标记该手术是否有事件。
    SELECT
        surg.id AS surgeon_id,
        s.id    AS surgery_id,
        MAX(CASE WHEN ae.id IS NOT NULL THEN 1 ELSE 0 END) AS had_event,
        MAX(CASE WHEN ae.severity IN ('Severe', 'Life-threatening') THEN 1 ELSE 0 END) AS had_serious_event
    FROM surgeon surg
    JOIN surgery s ON surg.id = s.surgeon_id
    JOIN surgery_implant si ON s.id = si.surgery_id
    LEFT JOIN adverse_event ae ON si.id = ae.surgery_implant_id
    GROUP BY surg.id, s.id
),
surgeon_metrics AS (
    -- GROUP BY 列出 SELECT 里所有非聚合列（兼容严格 SQL）。
    SELECT
        pse.surgeon_id,
        s.first_name,
        s.last_name,
        s.specialty,
        s.years_experience,
        COUNT(*)                AS total_surgeries,
        SUM(pse.had_event)      AS surgeries_with_event,
        SUM(pse.had_serious_event) AS surgeries_with_serious_event
    FROM per_surgery_events pse
    JOIN surgeon s ON pse.surgeon_id = s.id
    GROUP BY pse.surgeon_id, s.first_name, s.last_name, s.specialty, s.years_experience
    HAVING COUNT(*) >= 20
)
SELECT
    first_name || ' ' || last_name AS surgeon_name,
    specialty,
    years_experience,
    total_surgeries,
    surgeries_with_event,
    surgeries_with_serious_event,
    ROUND(surgeries_with_event * 100.0 / total_surgeries, 2)         AS adverse_event_rate,
    ROUND(surgeries_with_serious_event * 100.0 / total_surgeries, 2) AS serious_event_rate,
    RANK() OVER (ORDER BY surgeries_with_event * 100.0 / total_surgeries DESC) AS rate_rank
FROM surgeon_metrics
ORDER BY adverse_event_rate DESC
LIMIT 15;
```

**预期结果：** 按 per-surgery 事件率排序的医生。outlier 触发同行评议和补充培训。

---

### Query 16：各医院各存放地的库存状态分布

**业务背景：**
物料经理直观看每个存放地（OR Storage A、Sterile Processing 等）当前的库存状态分布。`Quarantined` 表示有 QA 隔离；`Expired` 表示需要清理浪费。

**类别：** 聚合 + GROUP BY
**难度：** Basic
**业务角色：** 运营

**解题思路：**
单层 `inventory JOIN hospital`，按 (医院, 存放地, 状态) 三维 GROUP BY 计数即可。一个要解释给读者的点：终态单元（`Used` / `Expired` / `Recalled`）的 `location` 是 NULL，因为它派生自最新一条 movement，而终态 movement 的 `to_location` 本就是空。所以用 `COALESCE(i.location, 'NO LOCATION (terminal state)')` 把 NULL 显示成可读标签，而不是留空让人误以为数据缺失。

```sql
SELECT
    h.name AS hospital_name,
    COALESCE(i.location, 'NO LOCATION (terminal state)') AS storage_location,
    i.status,
    COUNT(*) AS unit_count
FROM inventory i
JOIN hospital h ON i.hospital_id = h.id
GROUP BY h.name, i.location, i.status
ORDER BY h.name, unit_count DESC;
```

**预期结果：** 干净的库存网格。注意：终态单元（`Used`、`Expired`、`Recalled`）的 `location` 是 NULL，这是设计 —— 它派生自最新 movement，终态 movement 的 `to_location` 就是空。

---

### Query 17：各 FDA 申报类型的批准率

**业务背景：**
监管事务总监比较各通路的成功率。**`Withdrawn` 不计入分母** —— 它表示流程被主动撤回，不是被否决，把它计入会混淆 "撤回" 和 "拒批"。

**类别：** 条件聚合
**难度：** Intermediate
**业务角色：** 监管

**解题思路：**
单表 `regulatory_submission`，按 (申报类型, 监管机构) 分组。核心是 "批准率" 的分母口径：`Withdrawn`（主动撤回）不计入，因为撤回不是被否决，算进去会混淆两件事。所以分母用 `SUM(CASE WHEN status IN ('Approved','Pending','Denied') ...)`，分子用 Approved 数，中间套 `NULLIF(..., 0)` 防止某组全是 Withdrawn 时除零。`avg_approval_days` 只对 Approved 的行算 `approval_date - submission_date`，其余状态没有批准日，CASE 里自然落空，NULL 不进 AVG。

```sql
SELECT
    submission_type,
    regulatory_body,
    COUNT(*) AS total_submissions,
    SUM(CASE WHEN status = 'Approved'  THEN 1 ELSE 0 END) AS approved_count,
    SUM(CASE WHEN status = 'Pending'   THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN status = 'Denied'    THEN 1 ELSE 0 END) AS denied_count,
    SUM(CASE WHEN status = 'Withdrawn' THEN 1 ELSE 0 END) AS withdrawn_count,
    ROUND(
        SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) * 100.0
        / NULLIF(
            SUM(CASE WHEN status IN ('Approved', 'Pending', 'Denied') THEN 1 ELSE 0 END),
            0
        ),
        1
    ) AS approval_rate_pct,
    ROUND(
        AVG(CASE
                WHEN status = 'Approved'
                THEN JULIANDAY(approval_date) - JULIANDAY(submission_date)
            END
        ), 0
    ) AS avg_approval_days
FROM regulatory_submission
GROUP BY submission_type, regulatory_body
ORDER BY total_submissions DESC;
```

**预期结果：** 510(k) 通常 ~90% 批准率、~145 天周期；PMA 批准率更低、周期长得多。

---

### Query 18：各医院年度植入成本（金层视图）

**业务背景：**
CFO 例行需要的 "各医院年度植入成本" 汇总。本 query 从 **金层视图** 读 —— 视图把 join + point-in-time 价格封装好，让财务看板只对接一个可信的源。

**类别：** 视图 + 聚合
**难度：** Intermediate
**业务角色：** 财务

**解题思路：**
这题先 `CREATE VIEW v_hospital_monthly_implant_cost`，把 "医院 → 手术 → 植入单元 → 收货时点合同价" 这条 join 链（含 point-in-time 价格谓词）封装成金层视图，让财务看板只对接一个可信源。难点是 fan-out：一台手术有多枚植入物，视图里就是多行，直接 `AVG(unit_cost)` 会把 "平均每台手术成本" 算错。正确做法是 CTE `per_surgery` 先在 **手术粒度** 上 `SUM(unit_cost)` 求每台手术总成本，再在外层按 (医院, 年度) 聚合，这样 `avg_cost_per_surgery` 是 "每台手术" 的平均，不是 "每枚植入物" 的平均。

```sql
-- 金层视图 —— 定义一次，到处用。
CREATE VIEW IF NOT EXISTS v_hospital_monthly_implant_cost AS
SELECT
    h.id   AS hospital_id,
    h.name AS hospital_name,
    h.city,
    h.state,
    STRFTIME('%Y', s.surgery_date)    AS fiscal_year,
    STRFTIME('%Y-%m', s.surgery_date) AS fiscal_month,
    s.id                              AS surgery_id,
    si.id                             AS surgery_implant_id,
    i.id                              AS inventory_id,
    ip.id                             AS product_id,
    -- 单元收货时点的合同价
    ph.contracted_price_usd           AS unit_cost_at_receipt
FROM hospital h
JOIN surgery s ON h.id = s.hospital_id
JOIN surgery_implant si ON s.id = si.surgery_id
JOIN inventory i  ON si.inventory_id = i.id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
LEFT JOIN pricing_history ph
    ON ph.product_id      = ip.id
   AND ph.manufacturer_id = ip.manufacturer_id
   AND ph.effective_date <= i.received_date
   AND (ph.end_date IS NULL OR ph.end_date > i.received_date);

-- 使用视图：
WITH per_surgery AS (
    SELECT
        hospital_id, hospital_name, city, state, fiscal_year,
        surgery_id,
        COUNT(*)                   AS implants_per_surgery,
        SUM(unit_cost_at_receipt)  AS cost_per_surgery
    FROM v_hospital_monthly_implant_cost
    WHERE fiscal_year >= STRFTIME('%Y', DATE('now', '-1 year'))
    GROUP BY hospital_id, hospital_name, city, state, fiscal_year, surgery_id
)
SELECT
    hospital_name,
    city,
    state,
    fiscal_year,
    COUNT(*)                              AS total_surgeries,
    SUM(implants_per_surgery)             AS total_implants_used,
    ROUND(AVG(implants_per_surgery), 2)   AS avg_implants_per_surgery,
    ROUND(SUM(cost_per_surgery), 2)       AS total_implant_cost,
    ROUND(AVG(cost_per_surgery), 2)       AS avg_cost_per_surgery
FROM per_surgery
GROUP BY hospital_name, city, state, fiscal_year
ORDER BY total_implant_cost DESC;
```

**预期结果：** 各医院年度成本 + **正确的 "平均植入物数 / 手术"** —— fan-out bug 通过先在 surgery 层聚合的 CTE 修掉，不在 per-implant 行直接 AVG。

---

### Query 19：召回响应 SLA 合规度（金层视图）

**业务背景：**
召回协调员每周看 MAOHN 召回通知 SLA 达标情况。本 query 从一个预计算 per-recall SLA 的金层视图读。

**类别：** 视图 + CTE
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
先建金层视图 `v_recall_response_sla`，用 `LEFT JOIN recall_notification`（LEFT 很关键：一条召回可能一封通知都还没发，这种 "零通知" 的召回恰恰最危险，不能被 INNER JOIN 滤掉）把每条召回连同它的通知摊开，顺手算 `days_to_notify` 和按等级定的 `sla_notify_days`。外层按召回聚合：通知量、确认数、确认率、平均 / 最大通知耗时，以及超 SLA 的通知数和占比。`pct_past_sla` 大于 0 的 Class I 行要立即上报。

```sql
CREATE VIEW IF NOT EXISTS v_recall_response_sla AS
SELECT
    r.id            AS recall_id,
    r.recall_number,
    r.recall_class,
    r.recall_date,
    r.status        AS recall_status,
    rn.id           AS notification_id,
    rn.notification_date,
    rn.acknowledgment_date,
    JULIANDAY(rn.notification_date)  - JULIANDAY(r.recall_date)        AS days_to_notify,
    JULIANDAY(rn.acknowledgment_date) - JULIANDAY(rn.notification_date) AS days_to_ack,
    CASE r.recall_class
        WHEN 'Class I'   THEN 3
        WHEN 'Class II'  THEN 30
        WHEN 'Class III' THEN 60
    END AS sla_notify_days
FROM recall r
LEFT JOIN recall_notification rn ON r.id = rn.recall_id;

SELECT
    recall_number,
    recall_class,
    recall_date,
    recall_status,
    COUNT(notification_id)                                   AS notifications_sent,
    SUM(CASE WHEN acknowledgment_date IS NOT NULL THEN 1 ELSE 0 END) AS acknowledgments_received,
    ROUND(
        SUM(CASE WHEN acknowledgment_date IS NOT NULL THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(notification_id), 0),
        1
    ) AS acknowledgment_rate_pct,
    ROUND(AVG(days_to_notify), 1)               AS avg_days_to_notify,
    MAX(days_to_notify)                         AS max_days_to_notify,
    SUM(CASE WHEN days_to_notify > sla_notify_days THEN 1 ELSE 0 END) AS notifications_past_sla,
    ROUND(
        SUM(CASE WHEN days_to_notify > sla_notify_days THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(notification_id), 0),
        1
    ) AS pct_past_sla
FROM v_recall_response_sla
GROUP BY recall_id, recall_number, recall_class, recall_date, recall_status
ORDER BY recall_class, pct_past_sla DESC;
```

**预期结果：** 每行展示通知量、确认率、平均 / 最大通知耗时、超 SLA 占比。Class I 行 `pct_past_sla > 0` 必须立即上报。

---

### Query 20：患者 2 年内翻修率

**业务背景：**
临床质量分析师测算 24 个月内翻修率 —— 骨科结果学的核心指标。借助 `surgery.revision_of_surgery_id` 自引用 FK 识别翻修事件，并 join `patient_followup_visit` 看那些已经被 "revision indicated" 但尚未真正翻修的潜在病例。

**类别：** CTE + 自连接
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
翻修率的分母要严谨。`first_per_patient` 用 `ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY surgery_date)` 在每位患者的 **非翻修** 手术里挑出真正的首例（index case），避免双膝置换这种 "一位患者两台初次手术" 把分母放大。`index_surgeries` 把 index case 接上植入物拿到厂商和术式。`revisions` 借 `surgery.revision_of_surgery_id` 自引用 FK 找到翻修事件。`revision_flags` 用 `LEFT JOIN` 把翻修挂回 index case，并用 `JULIANDAY(revision_date) - JULIANDAY(index_date) <= 730` 卡 2 年窗口；同时用 `EXISTS` 子查询查 `patient_followup_visit` 里有没有被标 `revision_indicated`、但还没真翻修的预兆病例。最后按 (厂商, 术式) 算翻修率，`HAVING COUNT(*) >= 5` 滤小样本。

```sql
WITH first_per_patient AS (
    -- 每位患者真正的首次非翻修植入手术。
    -- 一位患者两次独立的初次膝置换（双膝）只贡献 1 个 index case，
    -- 分母不会被放大。
    SELECT
        s.id           AS surgery_id,
        s.patient_id,
        s.procedure_code,
        s.procedure_name,
        s.surgery_date,
        ROW_NUMBER() OVER (
            PARTITION BY s.patient_id
            ORDER BY s.surgery_date ASC, s.id ASC
        ) AS rn
    FROM surgery s
    WHERE s.revision_of_surgery_id IS NULL
),
index_surgeries AS (
    SELECT
        fpp.surgery_id   AS index_surgery_id,
        fpp.patient_id,
        fpp.procedure_code,
        fpp.procedure_name,
        fpp.surgery_date AS index_date,
        ip.id  AS product_id,
        m.name AS manufacturer
    FROM first_per_patient fpp
    JOIN surgery_implant si ON fpp.surgery_id = si.surgery_id
    JOIN inventory i  ON si.inventory_id = i.id
    JOIN implant_lot il ON i.lot_id = il.id
    JOIN implant_product ip ON il.product_id = ip.id
    JOIN manufacturer m ON ip.manufacturer_id = m.id
    WHERE fpp.rn = 1
),
revisions AS (
    SELECT
        rev.revision_of_surgery_id AS index_surgery_id,
        rev.surgery_date           AS revision_date
    FROM surgery rev
    WHERE rev.revision_of_surgery_id IS NOT NULL
),
revision_flags AS (
    SELECT
        idx.product_id,
        idx.manufacturer,
        idx.procedure_name,
        idx.index_surgery_id,
        CASE
            WHEN r.revision_date IS NOT NULL
                 AND (JULIANDAY(r.revision_date) - JULIANDAY(idx.index_date)) <= 730
            THEN 1 ELSE 0
        END AS revised_within_2y,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM patient_followup_visit f
                JOIN surgery_implant si2 ON f.surgery_implant_id = si2.id
                WHERE si2.surgery_id = idx.index_surgery_id
                  AND f.revision_indicated = TRUE
            ) THEN 1 ELSE 0
        END AS revision_indicated_in_followup
    FROM index_surgeries idx
    LEFT JOIN revisions r ON idx.index_surgery_id = r.index_surgery_id
)
SELECT
    manufacturer,
    procedure_name,
    COUNT(*) AS index_cases,
    SUM(revised_within_2y) AS revisions_within_2y,
    SUM(revision_indicated_in_followup) AS revision_indicated_followup_count,
    ROUND(SUM(revised_within_2y) * 100.0 / COUNT(*), 2) AS revision_rate_pct
FROM revision_flags
GROUP BY manufacturer, procedure_name
HAVING COUNT(*) >= 5
ORDER BY revision_rate_pct DESC;
```

**预期结果：** 按 (制造商, 术式) 的 2 年翻修率。超过 5% 值得深挖；`revision_indicated_followup_count` 是 "尚未发生但极可能发生" 的翻修预兆。

---

## 类别汇总

一个 query 可以归到多个类别 —— 下面的计数有意重复，方便学习者按技术点反查全部示例。

| 类别 | 数量 | Query 编号 |
|---|---|---|
| 聚合 | 6 | 1, 4, 9, 12, 16, 17 |
| 多表 Join | 5 | 2, 8, 11, 14, 18 |
| 窗口函数 | 4 | 3, 7, 13, 20 |
| 日期 / 时间分析 | 3 | 5, 7, 11 |
| CTE / 子查询 | 9 | 1, 4, 6, 10, 13, 15, 18, 19, 20 |
| 自连接 / 自引用 FK | 1 | 20 |
| 金层视图 | 2 | 18, 19 |

## 业务角色覆盖

| 角色 | 数量 | Query 编号 |
|---|---|---|
| 高管 | 2 | 1, 7 |
| 经理 | 5 | 2, 3, 13, 15, 19 |
| 分析师 | 5 | 4, 9, 12, 14, 20 |
| 运营 | 4 | 5, 8, 11, 16 |
| 财务 | 2 | 10, 18 |
| 监管 | 2 | 6, 17 |

## 难度分布

每个 query 只归入一个 bucket。

| 难度 | 数量 | Query 编号 |
|---|---|---|
| Basic | 3 | 1, 12, 16 |
| Intermediate | 9 | 3, 4, 5, 6, 7, 9, 11, 17, 18 |
| Advanced | 8 | 2, 8, 10, 13, 14, 15, 19, 20 |

---

## 备注

- 所有 query 都按 SQLite 3.x 语法写。窗口函数需要 SQLite 3.25+。
- 所有时间序不变式（`event_date > implantation_timestamp`、`notification_date > recall_date` 等）都由生成器强制，所以像 `days_post_surgery` 这种日期差列保证非负。
- Q2 和 Q8 用同一套 canonical join 同时处理 **lot 级** 和 **全产品级** 召回。
- 涉及价格的 query 全部使用 **单元 `received_date` 时点的 point-in-time 价格**，不使用单一去归一化的 `unit_cost`。这才是销货成本（COGS）报表的正确口径。
- 金层视图（Q18、Q19）每个数据库定义一次即可重用；生产环境会做成物化视图以提升性能。
- 引用 `DATE('now')` 的 query 假定数据集新鲜；生成器把所有日期锚到固定的 `NOW` 常量，所以数据集时间会逐渐漂离 `DATE('now')`。重用前请重新生成。
