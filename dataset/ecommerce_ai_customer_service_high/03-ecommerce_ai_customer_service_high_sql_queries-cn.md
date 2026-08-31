# NestMart AI 客服系统 — SQL 查询参考

本文档包含 **20 个业务导向的 SQL 查询示例**, 覆盖 NestMart AI 客服工单处理系统的核心分析场景。这是整个数据集里最偏"教学"的一份: 它既证明前面的表结构和数据真的能回答业务问题, 也带你像一个真实分析师那样一步步把每个问题写成 SQL。

> **先读这两份再来:** 公司、行业、业务问题、术语、指标公式见 [`01-ecommerce_ai_customer_service_high_business_context-cn.md`](01-ecommerce_ai_customer_service_high_business_context-cn.md); 表结构、字段、外键、分布见 [`02-ecommerce_ai_customer_service_high_er_document-cn.md`](02-ecommerce_ai_customer_service_high_er_document-cn.md)。

## 如何使用本文档

这份文档是写给**刚读完业务背景和 ER 文档、即将被经理派活的实习生**看的。读法:

1. **每个查询有五段, 按这个顺序读。**
   - **业务背景** — 谁在问、为什么问、答案要支撑什么决策、为什么是现在问。
   - **类别 / 难度 / 角色** — 三个标签, 帮你判断该花多少力气、对应哪个岗位。
   - **解题思路** — 在看 SQL 之前, 先想清楚要碰哪些表、JOIN 怎么搭 (哪里该 LEFT、哪里会扇出)、聚合的粒度是什么、为什么用 CTE/窗口/子查询、有没有 SQLite 的坑。**这一段是把"会读 SQL"变成"会写 SQL"的关键。**
   - **SQL 查询** — 真正能在生成的 SQLite 上跑的代码。
   - **预期结果说明** — 结果长什么样、关键数字对应哪个业务陷阱、以及**拿到数字之后该做什么**。跑出结果只是分析的开始, 不是结束。
2. **每个查询都能追溯到一个业务问题。** 业务背景文档 §5 列了 Q1–Q6 六个业务问题; 本文档每个查询的预期结果都会指回其中之一。
3. **SQL 是用来读和学的, 不只是用来跑的。** 解题思路里解释了"为什么这样写", 照着模仿就能迁移到新问题。
4. **所有"今天"都用固定参考日 `'2024-12-01'`** (见下方说明), 不要换成 `DATE('now')`。

### 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 | 业务问题 |
|------|------|----------|----------|------|----------|
| Q1 | 高价值用户工单处理优先级 | Operations Manager | Join + Aggregation | Basic | Q4 |
| Q2 | Prompt 版本迭代效果对比 | ML Engineer | Join + Calculated Fields | Intermediate | Q3 |
| Q3 | 最容易混淆的意图对识别 | ML Engineer | Aggregation + Subquery | Intermediate | Q1 |
| Q4 | 规则违反案例根因分析 | Quality Manager | Join + Aggregation | Intermediate | Q2 |
| Q5 | 标注员绩效和一致性排名 | Annotation Manager | Aggregation + Ranking | Basic | Q6 |
| Q6 | 用户退款频次风险预警 | Risk Analyst | Join + Filtering | Intermediate | Q5 |
| Q7 | AI 处理性能和成本分析 | Technical Operations | Aggregation + Calculated | Intermediate | Q5 |
| Q8 | 工单情绪分布与紧急度关联 | Customer Experience Manager | Cross Tab + Aggregation | Basic | Q1 |
| Q9 | 每日工单量趋势与容量规划 | Operations Analyst | Date/Time + Aggregation | Intermediate | Q4 |
| Q10 | LLM Judge 评分与标注一致性 | ML Researcher | Aggregation + Statistical | Advanced | Q1 |
| Q11 | 商品品类与工单类型关联 | Product Operations | Join + Cross Tab | Intermediate | Q4 |
| Q12 | Evaluation 运行历史趋势 | Tech Lead | Time Series + Trend | Intermediate | Q3 |
| Q13 | 高频违反规则的工单画像 | Quality Analyst | Join + Feature Analysis | Advanced | Q2 |
| Q14 | 工单处理时效 SLA 监控 | Operations Manager | Date/Time + SLA | Intermediate | Q4 |
| Q15 | AI 决策置信度与准确率相关性 | ML Engineer | Statistical + Bucketing | Advanced | Q2 |
| Q16 | 用户生命周期价值与客诉 | Customer Success Manager | Join + Segmentation | Advanced | Q4 |
| Q17 | 标注争议案例与仲裁效率 | Annotation Manager | Join + Status Tracking | Intermediate | Q6 |
| Q18 | 多渠道工单质量对比 | Product Manager | Aggregation + Cross-channel | Intermediate | Q1 |
| Q19 | Prompt 变更影响范围预测 | ML Engineer | Aggregation + Classification | Advanced | Q1 |
| Q20 | 综合 Dashboard 关键指标汇总 | Executive (VP/CTO) | Multi-table Aggregation | Advanced | Q3 |

## 数据集规模 (供查询预期结果对照)

| 类别 | 行数 | 说明 |
|------|------|------|
| **raw_ticket** | ~5,000 条 | 2024-11 月共 30 天的工单, 约 167 条/日 |
| **step1/step3 输出** | 各 ~5,000 条 | AI 系统每工单产生 1 条 Step1 + 1 条 Step3 输出 |
| **annotation_ground_truth** | ~1,000 条 | 评估样本 500 工单 × 2 标注员 |
| **evaluation_run** | 6 次 | v1 (baseline) → v2 → v3 → v4 → v5 (production) → v5 (回归) |
| **step1/step3_eval_detail** | 各 ~3,000 条 | 500 评估样本 × 6 次运行 |
| **confusion_matrix** | ~250 条 | 从 step1_eval_detail 聚合派生, 每 run 合计 = 该 run 评估样本数 |

## 关键 Evaluation Run ID 速查

| run_id | Step1 Prompt | Step3 Prompt | 备注 |
|--------|--------------|--------------|------|
| `eval_20241110_140000` | v1 | v1 | baseline (准确率 81.0%, 违反率 12.0%) |
| `eval_20241112_093000` | v2 | v1 | 修复 dispute_non_receipt 误判 (准确率 87.0%) |
| `eval_20241115_143000` | v3 | v2 | 优化 sentiment + 强调 R002 |
| `eval_20241119_100000` | v4 | v2 | 加 few-shot 示例 |
| `eval_20241123_140000` | v5 | v3 | production 候选 (准确率 90.5%, 违反率 3.0%) |
| `eval_20241128_090000` | v5 | v3 | production 上线后回归验证 |

> **术语速查 (Cohen's Kappa, LLM Judge, 混淆矩阵, A/B Test, R001-R007 规则等):** 见 [`01-ecommerce_ai_customer_service_high_business_context-cn.md`](01-ecommerce_ai_customer_service_high_business_context-cn.md) 的 §8 术语表。

> **关于"当前日期":** 本数据集是 **2024-11 的静态快照** (工单 `submitted_at` 落在 2024-11-01 ~ 11-30)。涉及"近 N 天 / 等待时长 / 积压天数"的查询统一以 **固定参考日 `2024-12-01`** 作为"今天",而不是用 `DATE('now')`/`JULIANDAY('now')` (运行时真实日期会落在数据范围之外, 导致结果为空或失真)。如需改成实时, 把 `'2024-12-01'` 替换成 `'now'` 即可。

---

## 查询 1: 高价值用户的工单处理优先级分析

**业务背景:**
客服团队主管每天需要了解VIP用户(金卡和铂金卡)提交的工单处理情况,确保高价值用户得到优先服务。主管关注的问题是:有多少VIP工单正在等待处理?这些工单的平均提交时间是多久?哪些VIP用户提交了工单?这个查询帮助主管在早会上快速了解需要优先处理的高价值客户诉求,避免客户流失。

**查询类别:** Join + Aggregation
**难度级别:** Basic
**业务角色:** Operations Manager

**解题思路:**
这题要把工单 `raw_ticket` 和用户 `user` 关联起来才能按会员等级筛 VIP。用 INNER JOIN, 因为每条工单一定有对应用户。先在 WHERE 里把范围缩到 `tier_code IN ('vip_gold','vip_platinum')`, 再用 `submitted_at >= DATE('2024-12-01','-7 days')` 限定近 7 天——注意参考日是固定字面量, 不用 `DATE('now')`, 否则运行时真实日期落在数据范围外会查不到。聚合粒度是"一个会员等级一行", 所以 `GROUP BY tier_code`; `COUNT(DISTINCT ticket_id)` 数工单、`COUNT(DISTINCT user_id)` 数涉及用户 (DISTINCT 防止 JOIN 扇出重复计数)。平均等待天数用 `JULIANDAY(参考日) - JULIANDAY(submitted_at)` 求差值, `GROUP_CONCAT(DISTINCT user_name)` 把用户名拼成一列方便主管点名。

**SQL查询:**
```sql
SELECT
    u.tier_code AS 会员等级,
    COUNT(DISTINCT rt.ticket_id) AS 工单数量,
    COUNT(DISTINCT u.user_id) AS 涉及用户数,
    ROUND(AVG(JULIANDAY('2024-12-01') - JULIANDAY(rt.submitted_at)), 1) AS 平均等待天数,
    GROUP_CONCAT(DISTINCT u.user_name) AS 用户列表
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
WHERE u.tier_code IN ('vip_gold', 'vip_platinum')
    AND rt.submitted_at >= DATE('2024-12-01', '-7 days')
GROUP BY u.tier_code
ORDER BY 工单数量 DESC;
```

**预期结果说明:**
返回最近 7 天 VIP 用户的工单统计。基于本数据集规模 (~5,000 工单 × 30 天, VIP 占 ~20%), 7 天 VIP 工单约 230 条。结果显示金卡用户可能有 ~190 条工单 (涉及 ~80 个用户, 平均等待 2.3 天); 铂金用户可能有 ~40 条工单 (涉及 ~20 个用户, 平均等待 1.8 天)。主管可据此判断是否需要加派人手处理 VIP 工单。

---

## 查询 2: Prompt版本迭代效果对比

**业务背景:**
ML工程师在优化Step1意图识别Prompt后,需要向团队展示新版本Prompt相比基线版本的提升效果。工程师需要回答:准确率提升了多少?哪些指标有显著改进?改进是否值得部署到生产环境?这个查询生成一份版本对比报告,包含所有关键指标的变化百分比,帮助技术决策者快速判断是否应该切换到新版本Prompt。

**查询类别:** Join + Calculated Fields
**难度级别:** Intermediate
**业务角色:** ML Engineer

**解题思路:**
A/B 对比的事实表是 `prompt_comparison` (一对 baseline/experiment run + 一个指标 = 一行)。难点在于要显示版本号, 得把两端的 run 各自 JOIN 回 `evaluation_run`, 再各自 JOIN `prompt_version`——也就是同一张 `prompt_version` 被别名 JOIN 了两次 (baseline 一次、experiment 一次), 这是典型的"多次别名 JOIN"。`WHERE pv_baseline.step_name='step1_intent'` 把对比限定在 Step1 指标。改进幅度直接读 `improvement_pct` 字段 (生成器已回指真实指标算好, 不必自己再算), 用 CASE 给正值补 "+" 号; 显著性读 `is_significant`。这题不需要 GROUP BY, 因为每行已经是一条对比记录。

**SQL查询:**
```sql
SELECT
    pc.metric_name AS 指标名称,
    ROUND(pc.baseline_value * 100, 2) || '%' AS 基线值,
    ROUND(pc.experiment_value * 100, 2) || '%' AS 实验值,
    CASE
        WHEN pc.improvement_pct > 0 THEN '+' || ROUND(pc.improvement_pct, 1) || '%'
        ELSE ROUND(pc.improvement_pct, 1) || '%'
    END AS 改进幅度,
    CASE WHEN pc.is_significant THEN '✓ 显著' ELSE '- 不显著' END AS 统计显著性,
    pv_baseline.version_code AS 基线版本,
    pv_exp.version_code AS 实验版本
FROM prompt_comparison pc
JOIN evaluation_run er_baseline ON pc.baseline_run_id = er_baseline.run_id
JOIN evaluation_run er_exp ON pc.experiment_run_id = er_exp.run_id
JOIN prompt_version pv_baseline ON er_baseline.step1_prompt_id = pv_baseline.prompt_id
JOIN prompt_version pv_exp ON er_exp.step1_prompt_id = pv_exp.prompt_id
WHERE pv_baseline.step_name = 'step1_intent'
ORDER BY pc.comparison_id;
```

**预期结果说明:**
返回类似"step1_accuracy: 81% → 87%, +7.4%, ✓显著"的对比结果。工程师可以看到v2相比v1在整体准确率、特定意图(dispute_non_receipt)准确率等指标上的全面提升,支撑部署决策。

---

## 查询 3: 最容易混淆的意图对识别

**业务背景:**
Prompt工程师在改进意图识别系统时,需要找出最容易被AI误判的意图组合。例如,"未收到货"经常被误判为"退款请求",因为用户在描述未收到货时通常会提及"退款"。工程师需要问:哪些意图对最容易混淆?混淆样本有多少?这个信息帮助工程师在Prompt中针对性地添加区分性指引(如"先读完全文再分类"),从而提升准确率。

**查询类别:** Aggregation + Subquery
**难度级别:** Intermediate
**业务角色:** ML Engineer

**解题思路:**
混淆矩阵 `confusion_matrix` 每行是"某次 run 里 真实=X、预测=Y 的工单数"。要算"误判率", 分母应是该真实意图在该 run 的总样本数, 所以先用一个子查询按 `(run_id, true_label)` 把 `SUM(count)` 求出来当分母, 再 JOIN 回明细。**最关键的陷阱: 这个分母子查询必须 `WHERE run_id = 同一个 run`, 否则跨 6 个 run 求和会把分母放大约 6 倍, 误判率被严重低估。** 主查询用 `WHERE true_label != predicted_label` 只看非对角线 (误分类), 锁定 v1 run, `ORDER BY count DESC LIMIT 5` 取最严重的 5 个组合。两次 JOIN `intent_category` 只是为了把意图代码翻译成中文名。

**SQL查询:**
```sql
SELECT
    cm.true_label AS 真实意图,
    cm.predicted_label AS 误判为,
    cm.count AS 样本数,
    ROUND(cm.count * 100.0 / total.true_total, 1) AS 误判率百分比,
    ic_true.intent_name_cn AS 真实意图名称,
    ic_pred.intent_name_cn AS 误判意图名称
FROM confusion_matrix cm
JOIN intent_category ic_true ON cm.true_label = ic_true.intent_code
JOIN intent_category ic_pred ON cm.predicted_label = ic_pred.intent_code
JOIN (
    SELECT run_id, true_label, SUM(count) AS true_total
    FROM confusion_matrix
    WHERE run_id = 'eval_20241110_140000'  -- 分母必须限定同一 run, 否则跨 6 个 run 串味
    GROUP BY run_id, true_label
) total ON cm.true_label = total.true_label AND cm.run_id = total.run_id
WHERE cm.true_label != cm.predicted_label  -- 只看误分类
    AND cm.run_id = 'eval_20241110_140000'  -- 使用v1 Prompt的运行
ORDER BY cm.count DESC
LIMIT 5;
```

**预期结果说明:**
返回前5个最常见的误分类组合,例如"dispute_non_receipt → refund_request: 15样本, 23%误判率"。工程师据此在v2 Prompt中加入"先读完全文"的指引,将该误判率降低到8%。

---

## 查询 4: 规则违反案例根因分析

**业务背景:**
客服质量管理员在每周质检会上需要报告AI系统的规则遵守情况。管理员关注:有哪些规则被频繁违反?违反的严重性如何?是否有特定模式?例如,如果发现AI经常在"第三方商家商品"上错误地自行批准退款(违反R002规则),这意味着AI没有理解"决策权归商家"这一核心业务规则,需要在Prompt中强调。这个查询生成规则违反的Top案例列表,帮助定位Prompt改进方向。

**查询类别:** Join + Aggregation
**难度级别:** Intermediate
**业务角色:** Quality Manager

**解题思路:**
从规则表 `decision_rule` JOIN 违反案例 `rule_violation_case` (一条规则可对多条案例, 一对多关系)。聚合粒度是"一条规则一行", 所以 `GROUP BY rule_id, rule_name`。核心技巧是条件聚合: `COUNT(case_id)` 数总违反次数, `SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END)` 数严重违反, `SUM(CASE WHEN fix_status='fixed' ...)` 数已修复。平均严重度用 CASE 把 critical/high/medium 映射成 1.0/0.7/0.3 再 `AVG`。`WHERE run_id` 限定 v1 run 看基线最差状态, `ORDER BY 违反次数 DESC` 会让 R002 (第三方退款) 浮到最顶——这正对应 ER §7.6 的 T3 陷阱。

**SQL查询:**
```sql
SELECT
    dr.rule_id AS 规则编号,
    dr.rule_name AS 规则名称,
    COUNT(rvc.case_id) AS 违反次数,
    SUM(CASE WHEN rvc.impact_severity = 'critical' THEN 1 ELSE 0 END) AS 严重违反次数,
    SUM(CASE WHEN rvc.fix_status = 'fixed' THEN 1 ELSE 0 END) AS 已修复次数,
    GROUP_CONCAT(DISTINCT rvc.fix_prompt_version) AS 修复版本,
    ROUND(AVG(CASE WHEN rvc.impact_severity = 'critical' THEN 1.0
                   WHEN rvc.impact_severity = 'high' THEN 0.7
                   WHEN rvc.impact_severity = 'medium' THEN 0.3
                   ELSE 0 END), 2) AS 平均严重度评分
FROM decision_rule dr
JOIN rule_violation_case rvc ON dr.rule_id = rvc.rule_id
WHERE rvc.run_id = 'eval_20241110_140000'
GROUP BY dr.rule_id, dr.rule_name
ORDER BY 违反次数 DESC, 平均严重度评分 DESC
LIMIT 10;
```

**预期结果说明:**
返回类似"R002(第三方商家转交处理): 8次违反, 5次严重, 7次已在v2修复"的统计。管理员可以看到R002是最高频违反规则,已在v2 Prompt中针对性改进。

---

## 查询 5: 标注员绩效和一致性排名

**业务背景:**
标注项目负责人每月需要评估标注团队的工作质量,决定绩效奖金分配和培训需求。负责人需要回答:哪些标注员工作量最大?标注质量如何?与其他标注员的一致率(Cohen's Kappa)是否达标(>0.75)?是否有标注员需要额外培训?这个查询生成标注员绩效排行榜,结合工作量、质量、一致性三个维度,帮助负责人做出公平的绩效评估。

**查询类别:** Aggregation + Ranking
**难度级别:** Basic
**业务角色:** Annotation Manager

**解题思路:**
这题只查单表 `annotator`, 不需要 JOIN。重点是用 CASE 把 `agreement_rate` (Cohen's Kappa) 分档成"优秀/良好/合格/需改进", 并注意 arbitrator 的 Kappa 是 NULL, 要单独判 `IS NULL → N/A`, 否则会落进错误档位。`COALESCE(agreement_rate, 0)` 防止 NULL 参与 ROUND 报错。在职天数用 `JULIANDAY(参考日)-JULIANDAY(joined_date)` 求差再 `CAST AS INTEGER`。`WHERE role IN ('annotator','reviewer')` 排除仲裁员 (他们不做一线标注, 没有 Kappa)。`ORDER BY total_annotations DESC, agreement_rate DESC` 双键排序: 先按工作量, 再按质量。

**SQL查询:**
```sql
SELECT
    a.annotator_name AS 标注员,
    a.role AS 角色,
    a.total_annotations AS 总标注数,
    ROUND(a.avg_confidence, 2) AS 平均置信度,
    ROUND(COALESCE(a.agreement_rate, 0), 3) AS 一致率Kappa,
    CASE
        WHEN a.agreement_rate >= 0.90 THEN '优秀'
        WHEN a.agreement_rate >= 0.75 THEN '良好'
        WHEN a.agreement_rate >= 0.60 THEN '合格'
        WHEN a.agreement_rate IS NULL THEN 'N/A'
        ELSE '需改进'
    END AS 质量等级,
    CAST((JULIANDAY('2024-12-01') - JULIANDAY(a.joined_date)) AS INTEGER) AS 在职天数
FROM annotator a
WHERE a.role IN ('annotator', 'reviewer')
ORDER BY a.total_annotations DESC, a.agreement_rate DESC;
```

**预期结果说明:**
返回标注员排名,例如"王静怡: 235条标注, 2.9平均置信度, 0.94 Kappa, 优秀"。负责人可以看到王静怡质量最高,张晓月工作量最大,刘美琪一致率偏低(0.87)需要培训。

---

## 查询 6: 用户退款频次风险预警

**业务背景:**
风控分析师每天监控高频退款用户,防止恶意退款和欺诈行为。根据业务规则R004,30天内退款3次以上的用户需要升级人工审核。分析师需要识别:有哪些用户正在接近或已触发该阈值?这些用户的消费金额和会员等级如何?是否需要提前介入?这个查询生成高风险用户预警列表,帮助分析师提前识别异常行为模式,保护平台利益。

**查询类别:** Join + Filtering
**难度级别:** Intermediate
**业务角色:** Risk Analyst

**解题思路:**
这题本质是单表 `user` 的过滤 + 算术, 不必真的 JOIN 订单 (高频退款次数已经聚合在 `refund_count_30days` 字段里)。`WHERE refund_count_30days >= 2` 一网打尽两类人: 已触发 R004 的 (≥3) 和接近阈值的预警 (=2)。退款率用 `refund_count_30days*100.0/NULLIF(total_order_count,0)`, **用 NULLIF 把分母为 0 的情况转成 NULL, 避免除零错误** (新用户订单可能为 0)。风险状态用 CASE 打三档标签。`ORDER BY refund_count_30days DESC, total_spent_amount DESC` 让"最危险且最高价值"的用户排在最前, 优先人工介入。

**SQL查询:**
```sql
SELECT
    u.user_id AS 用户ID,
    u.user_name AS 用户姓名,
    u.tier_code AS 会员等级,
    u.refund_count_30days AS 30天退款次数,
    u.total_order_count AS 累计订单数,
    ROUND(u.total_spent_amount, 2) AS 累计消费金额,
    ROUND(u.refund_count_30days * 100.0 / NULLIF(u.total_order_count, 0), 1) AS 退款率百分比,
    CASE
        WHEN u.refund_count_30days >= 3 THEN '⚠️ 已触发R004规则'
        WHEN u.refund_count_30days = 2 THEN '⚡ 接近阈值'
        ELSE '正常'
    END AS 风险状态
FROM user u
WHERE u.refund_count_30days >= 2
ORDER BY u.refund_count_30days DESC, u.total_spent_amount DESC
LIMIT 20;
```

**预期结果说明:**
返回高风险用户列表,例如"U00000123(李某): vip_silver, 3次退款(30天), 15笔总订单, $650消费, 20%退款率, ⚠️已触发R004"。分析师可以看到该用户虽然是白银会员,但退款频次异常,需要人工介入审查。

---

## 查询 7: AI处理性能和成本分析

**业务背景:**
技术运营经理需要向CFO汇报AI系统的运营成本和性能指标。CFO关心:AI处理每条工单的平均耗时是多少?Token消耗成本如何?是否有优化空间?根据业务背景,Claude 3.5 Sonnet每1000 output tokens约$0.015。经理需要计算:Step1和Step3的总Token消耗和对应成本,评估相比人工客服(日薪$150)的成本节省比例,证明AI投资的价值。

**查询类别:** Aggregation + Calculated Fields
**难度级别:** Intermediate
**业务角色:** Technical Operations

**解题思路:**
要把 Step1 和 Step3 的成本并成一张表, 用 `UNION ALL` 把三段 (Step1 明细 / Step3 明细 / 合计) 纵向拼起来。Step1 段从 `step1_intent_output` 的真实 `output_tokens` 算成本 `SUM(output_tokens)/1000*0.015`; Step3 段没有存 token, 用业务估算常量 224 tokens/条。合计段用标量子查询把两表的数字相加。**UNION ALL 的硬要求: 每一段的列数和列顺序必须完全对齐, 某段没有的列 (如 Step3 没有 input_tokens) 要用 `NULL` 占位**, 否则会报错或串列。整题不 JOIN, 全靠聚合 + 算术, 目的是给 CFO 一份"AI 比人工省多少"的成本账 (对应 T5 陷阱)。

**SQL查询:**
```sql
SELECT
    'Step 1: 意图识别' AS 处理步骤,
    COUNT(*) AS 处理工单数,
    ROUND(AVG(s1.latency_ms), 0) AS 平均延迟毫秒,
    ROUND(AVG(s1.input_tokens), 0) AS 平均输入Tokens,
    ROUND(AVG(s1.output_tokens), 0) AS 平均输出Tokens,
    SUM(s1.output_tokens) AS 总输出Tokens,
    ROUND(SUM(s1.output_tokens) / 1000.0 * 0.015, 2) AS 总成本美元,
    ROUND(SUM(s1.output_tokens) / 1000.0 * 0.015 / COUNT(*), 4) AS 单条成本美元
FROM step1_intent_output s1

UNION ALL

SELECT
    'Step 3: 策略决策',
    COUNT(*),
    ROUND(AVG(s3.latency_ms), 0),
    NULL AS 平均输入Tokens,
    NULL AS 平均输出Tokens,
    NULL AS 总输出Tokens,
    ROUND(COUNT(*) * 224 / 1000.0 * 0.015, 2),  -- 估算输出tokens约224
    ROUND(224 / 1000.0 * 0.015, 4)
FROM step3_decision_output s3

UNION ALL

SELECT
    '合计',
    (SELECT COUNT(*) FROM step1_intent_output) + (SELECT COUNT(*) FROM step3_decision_output),
    NULL,
    NULL,
    NULL,
    (SELECT SUM(output_tokens) FROM step1_intent_output) +
        (SELECT COUNT(*) * 224 FROM step3_decision_output),
    ROUND((SELECT SUM(output_tokens) FROM step1_intent_output) / 1000.0 * 0.015 +
          (SELECT COUNT(*) FROM step3_decision_output) * 224 / 1000.0 * 0.015, 2),
    ROUND(((SELECT SUM(output_tokens) FROM step1_intent_output) / 1000.0 * 0.015 +
           (SELECT COUNT(*) FROM step3_decision_output) * 224 / 1000.0 * 0.015) /
          ((SELECT COUNT(*) FROM step1_intent_output) + (SELECT COUNT(*) FROM step3_decision_output)), 4);
```

**预期结果说明:**
返回"Step1: ~5,000 条工单, 1847ms 平均延迟, 178 平均输出 tokens, $13.35 总成本, $0.0027 单条成本"。Step3 类似规模, 合计成本约 $25/5000 条工单 ($0.005/条), 远低于人工处理成本 (约 $4.69/条, 假设客服日均处理 71 条, 日薪 $150)。经理可以证明 AI 每月节省约 $11,100 (按 3,200 条/日 × 30 天 × $0.115 节省估算)。

---

## 查询 8: 工单情绪分布与紧急度关联分析

**业务背景:**
客户体验经理需要了解用户情绪与问题紧急度的关系,优化客服响应策略。经理想知道:愤怒用户的工单是否都被标记为高紧急度?中性情绪用户的工单中有多少是真正紧急的?如果发现大量愤怒用户但紧急度被误判为"低",说明AI对情绪理解不足,需要调整。这个查询生成情绪-紧急度交叉统计表,帮助经理识别AI判断的盲点,改进用户体验。

**查询类别:** Cross Tabulation + Aggregation
**难度级别:** Basic
**业务角色:** Customer Experience Manager

**解题思路:**
这是一张情绪 × 紧急度的交叉表。从 `step1_intent_output` JOIN `step1_eval_detail` (借它拿 `is_correct` 算准确率), 再 JOIN `intent_category` 拿意图中文名。`WHERE run_id='eval_20241112_093000'` 必须锁定一次评估, 否则一条工单在 6 次 run 里都有明细, 会被重复计数。聚合粒度是"情绪×紧急度"组合, 所以 `GROUP BY sentiment, urgency`。占比这一列用窗口函数 `COUNT(*)*100.0/SUM(COUNT(*)) OVER (PARTITION BY sentiment)`——`PARTITION BY sentiment` 让占比表示"同一种情绪内部、各紧急度的分布"。排序用 CASE 把 high/medium/low 排成业务优先序, 而不是字母序。

**SQL查询:**
```sql
SELECT
    s1.sentiment AS 情绪,
    s1.urgency AS 紧急度,
    COUNT(*) AS 工单数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY s1.sentiment), 1) AS 该情绪占比百分比,
    ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 意图识别准确率,
    GROUP_CONCAT(DISTINCT ic.intent_name_cn) AS 主要意图类型
FROM step1_intent_output s1
JOIN step1_eval_detail sed ON s1.output_id = sed.output_id
JOIN intent_category ic ON s1.primary_intent = ic.intent_code
WHERE sed.run_id = 'eval_20241112_093000'
GROUP BY s1.sentiment, s1.urgency
ORDER BY s1.sentiment,
    CASE s1.urgency WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END;
```

**预期结果说明:**
返回"angry情绪 + high紧急度: 85条工单(90%), 0.88准确率, 主要意图有dispute_non_receipt/complaint_quality"。经理可以看到angry用户的工单90%被正确标记为高紧急,但仍有10%标记为中低紧急,需要改进。

---

## 查询 9: 每日工单量趋势与AI处理容量规划

**业务背景:**
运营分析师需要预测未来工单量,规划AI系统的处理容量。分析师需要回答:过去30天的工单量趋势如何?是否有周期性模式(周末低,工作日高)?旺季(如Black Friday)工单量会激增到多少?当前AI系统处理3200条/日,如果旺季达到8000条/日,是否需要扩容?这个查询生成每日工单量时间序列,帮助分析师用历史数据预测未来需求,避免系统过载。

**查询类别:** Date/Time Analysis + Aggregation
**难度级别:** Intermediate
**业务角色:** Operations Analyst

**解题思路:**
时间序列按天聚合: `DATE(submitted_at)` 把时间戳截断到日再 `GROUP BY`。星期几用 `STRFTIME('%w', submitted_at)` 取 0–6 (0=周日) 再用 CASE 翻译成中文。JOIN `user` 是为了算每天的 VIP 占比。含附件工单数用 `COUNT(CASE WHEN has_attachment THEN 1 END)`——CASE 不满足时返回 NULL, 而 COUNT 会跳过 NULL, 这是"条件计数"的惯用写法。`WHERE DATE(submitted_at) >= DATE('2024-12-01','-30 days')` 限定近 30 天, `ORDER BY 日期 DESC` 让最近的日子排在最上面, 方便看最新趋势。

**SQL查询:**
```sql
SELECT
    DATE(rt.submitted_at) AS 日期,
    CASE CAST(STRFTIME('%w', rt.submitted_at) AS INTEGER)
        WHEN 0 THEN '周日'
        WHEN 1 THEN '周一'
        WHEN 2 THEN '周二'
        WHEN 3 THEN '周三'
        WHEN 4 THEN '周四'
        WHEN 5 THEN '周五'
        WHEN 6 THEN '周六'
    END AS 星期,
    COUNT(*) AS 工单数,
    COUNT(CASE WHEN rt.has_attachment THEN 1 END) AS 含附件工单数,
    ROUND(AVG(CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 1.0 ELSE 0.0 END), 3) AS VIP占比,
    GROUP_CONCAT(DISTINCT rt.channel) AS 提交渠道
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-30 days')
GROUP BY DATE(rt.submitted_at)
ORDER BY 日期 DESC;
```

**预期结果说明:**
返回每日统计,例如"2024-11-15 (周五): ~180 条工单, ~55 条含附件, 0.20 VIP 占比, 渠道有 web_form/app/chat/email/phone_transcript"。分析师可以看到工作日平均约 170-200 条/日, 周末降至 ~120 条/日 (本数据集 5,000 工单 ÷ 30 天 ≈ 167 条/日均值), 据此规划资源。

---

## 查询 10: LLM Judge评分与人工标注一致性对比

**业务背景:**
ML研究员在验证LLM-as-Judge方法的可靠性时,需要对比LLM Judge的评分与人工标注结果的相关性。研究员想知道:LLM Judge给出高分(4-5分)的样本中,有多少确实是人工标注正确的?LLM Judge是否存在系统性偏差(如对正确分类的样本评分虚高)?如果发现Judge评分与实际准确率不相关,说明Judge本身需要校准。这个查询生成Judge评分的准确性分布,帮助评估Judge方法的有效性。

**查询类别:** Aggregation + Statistical Analysis
**难度级别:** Advanced
**业务角色:** ML Researcher

**解题思路:**
这题检验 LLM Judge 的评分到底和实际准确率相不相关 (Judge 会不会虚高)。先用 CASE 把 `judge_reasoning_score` 分成高/中/低三档, `GROUP BY` 同一个 CASE 表达式。每档算实际准确率 `AVG(is_correct)` 和平均 Judge 分对照。**SQLite 没有内置 `STDEV()`, 所以标准差要用 `SQRT(AVG(x*x) - AVG(x)*AVG(x))` 这个总体方差公式手算**——这是本题最大的教学点。`WHERE run_id` 锁定一次评估。`ORDER BY` 也用 CASE 保证高→低档位顺序, 而不是按文本排。

**SQL查询:**
```sql
SELECT
    CASE
        WHEN sed.judge_reasoning_score >= 4 THEN '高分(4-5)'
        WHEN sed.judge_reasoning_score >= 3 THEN '中分(3)'
        ELSE '低分(1-2)'
    END AS Judge评分档位,
    COUNT(*) AS 样本数,
    SUM(CASE WHEN sed.is_correct THEN 1 ELSE 0 END) AS 正确分类数,
    ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 实际准确率,
    ROUND(AVG(sed.judge_reasoning_score), 2) AS 平均推理评分,
    ROUND(AVG(sed.judge_completeness_score), 2) AS 平均完整性评分,
    -- 原生 SQLite 无 STDEV(): 用 sqrt(E[x^2] - E[x]^2) 手算总体标准差
    ROUND(SQRT(
        AVG(sed.judge_reasoning_score * sed.judge_reasoning_score)
        - AVG(sed.judge_reasoning_score) * AVG(sed.judge_reasoning_score)
    ), 2) AS 推理评分标准差
FROM step1_eval_detail sed
WHERE sed.run_id = 'eval_20241112_093000'
GROUP BY
    CASE
        WHEN sed.judge_reasoning_score >= 4 THEN '高分(4-5)'
        WHEN sed.judge_reasoning_score >= 3 THEN '中分(3)'
        ELSE '低分(1-2)'
    END
ORDER BY
    CASE
        WHEN sed.judge_reasoning_score >= 4 THEN 1
        WHEN sed.judge_reasoning_score >= 3 THEN 2
        ELSE 3
    END;
```

**预期结果说明:**
返回"高分(4-5): 320样本, 305正确, 0.953实际准确率, 4.4平均推理分"。研究员可以看到Judge高分与高准确率强相关,但仍有15个高分样本实际分类错误,需要分析这些False Positive案例。

---

## 查询 11: 商品品类与工单类型关联分析

**业务背景:**
产品运营经理需要了解不同商品品类的客诉特征,优化商品质量和物流。经理想知道:寝具类商品是否更容易破损?照明类商品是否退货率高?厨房用品是否质量投诉多?这个信息帮助经理识别高风险品类,向供应链团队反馈改进需求。例如,如果发现"寝具-破损投诉"占比异常高,需要检查包装质量;如果"照明-七天无理由退款"高,可能是图片与实物差异大。

**查询类别:** Join + Cross Tabulation
**难度级别:** Intermediate
**业务角色:** Product Operations

**解题思路:**
工单要先经 `order` 再到 `product` 才知道商品品类, 所以链式 `raw_ticket LEFT JOIN order LEFT JOIN product`。**这里必须用 LEFT JOIN: 30% 的咨询类工单没有 order_id, 用 INNER JOIN 会把它们整批剔除**, 扭曲分母。但随后 `WHERE p.category IS NOT NULL` 又主动把没有品类的工单滤掉 (无品类就无法按品类统计)。再 JOIN `step1_intent_output` 和 `intent_category` 拿意图名。聚合粒度是"品类×意图", 占比用窗口 `PARTITION BY category`, `HAVING COUNT >= 3` 过滤样本过少的格子。**预期结果要强调: 意图与品类是独立生成的 (ER §7.6 反陷阱), 本查询是相关性检验模板, 不预设强相关。

**SQL查询:**
```sql
SELECT
    p.category AS 商品品类,
    ic.intent_name_cn AS 工单意图,
    COUNT(DISTINCT rt.ticket_id) AS 工单数,
    ROUND(AVG(o.order_amount), 2) AS 平均订单金额,
    ROUND(COUNT(DISTINCT rt.ticket_id) * 100.0 /
        SUM(COUNT(DISTINCT rt.ticket_id)) OVER (PARTITION BY p.category), 1) AS 该品类占比,
    GROUP_CONCAT(DISTINCT p.seller_type_code) AS 商家类型
FROM raw_ticket rt
LEFT JOIN "order" o ON rt.order_id = o.order_id
LEFT JOIN product p ON o.product_id = p.product_id
JOIN step1_intent_output s1 ON rt.ticket_id = s1.ticket_id
JOIN intent_category ic ON s1.primary_intent = ic.intent_code
WHERE p.category IS NOT NULL
GROUP BY p.category, ic.intent_name_cn
HAVING COUNT(DISTINCT rt.ticket_id) >= 3  -- 至少3条工单
ORDER BY p.category, 工单数 DESC;
```

**预期结果说明:**
返回类似"寝具 - 物流纠纷-收到破损商品: 18条工单, $128平均金额, 35%品类占比, nestmart_original商家"的品类×意图交叉表。经理可以逐格对比各品类下不同工单意图的分布与平均金额,定位需要重点关注的"品类-意图"组合(再结合业务经验判断是包装问题还是商品描述问题)。注:本数据集中工单意图与商品品类为独立生成,不预设"某品类必然高破损"的强相关,真实业务中可用本查询模板去检验是否存在此类相关性。

---

## 查询 12: Evaluation运行历史趋势分析

**业务背景:**
Tech Lead需要向VP of Engineering展示AI系统的持续改进历程。VP关心:过去几周Prompt迭代带来了哪些指标提升?Step1准确率和Step3规则违反率的趋势如何?改进是否稳定?是否有回归风险?这个查询生成时间序列的评估指标变化图表,帮助Tech Lead可视化展示团队的工程成果,争取更多资源投入。

**查询类别:** Time Series + Trend Analysis
**难度级别:** Intermediate
**业务角色:** Tech Lead

**解题思路:**
直接查 `evaluation_run`, 并两次别名 JOIN `prompt_version` 拿 Step1 和 Step3 各自的版本号。`WHERE run_status='completed'` 只看跑完的 run。运行时长用 `(JULIANDAY(completed_at)-JULIANDAY(started_at))*24*60` 把天差转成分钟。**关键是 `ORDER BY started_at` 按时间正序排**, 这样读者能看到 v1→v5 准确率单调上升、违反率单调下降的清晰曲线 (ER §7.6 的 T2 陷阱)。这题不聚合, 因为 `evaluation_run` 每行已经是一次 run 的指标汇总。

**SQL查询:**
```sql
SELECT
    er.run_id AS 运行ID,
    DATETIME(er.started_at) AS 运行时间,
    pv1.version_code AS Step1Prompt版本,
    pv3.version_code AS Step3Prompt版本,
    er.triggered_by AS 触发方式,
    ROUND(er.step1_accuracy, 3) AS Step1准确率,
    ROUND(er.step3_rule_violation_rate, 3) AS Step3违反率,
    ROUND(er.step1_judge_avg_score, 2) AS Step1Judge均分,
    ROUND(er.step3_judge_avg_score, 2) AS Step3Judge均分,
    er.total_tickets_evaluated AS 评估工单数,
    CAST((JULIANDAY(er.completed_at) - JULIANDAY(er.started_at)) * 24 * 60 AS INTEGER) AS 运行时长分钟
FROM evaluation_run er
JOIN prompt_version pv1 ON er.step1_prompt_id = pv1.prompt_id
JOIN prompt_version pv3 ON er.step3_prompt_id = pv3.prompt_id
WHERE er.run_status = 'completed'
ORDER BY er.started_at;
```

**预期结果说明:**
返回 6 次运行的完整迭代趋势: `eval_20241110 (v1, 0.81 准确率, 0.12 违反率) → eval_20241112 (v2, 0.87 / 0.042) → eval_20241115 (v3, 0.875 / 0.040) → eval_20241119 (v4, 0.890 / 0.035) → eval_20241123 (v5, 0.905 / 0.030) → eval_20241128 (v5 回归, 0.902 / 0.031)`。Tech Lead 可以展示清晰的"5 个版本累计提升准确率 +9.5pp、规则违反率下降 75%"的工程价值。

---

## 查询 13: 高频违反规则的工单特征画像

**业务背景:**
质量分析师需要深入分析为什么某些工单容易触发规则违反。分析师想知道:哪些用户特征(会员等级、退款历史)、订单特征(金额、商家类型)与规则违反强相关?例如,如果发现第三方商家订单的规则违反率特别高,说明AI对"转交商家"规则理解不足。这个查询生成违反案例的特征分布,帮助分析师定位问题根因,向ML团队提供改进建议。

**查询类别:** Join + Feature Analysis
**难度级别:** Advanced
**业务角色:** Quality Analyst

**解题思路:**
先用 CTE `violation_tickets` 把"v1 run 里 critical/high 严重违反的工单"用 `SELECT DISTINCT ticket_id` 去重抽出来。然后用 `UNION ALL` 拼两段: 第一段按用户等级拆解 (`raw_ticket JOIN user LEFT JOIN order`), 第二段按商家类型拆解 (要 JOIN 到 `product`, 用 INNER JOIN 因为只看有订单有商品的)。用 CTE 的价值在于"严重违反工单"这个集合被两段复用, 不必把筛选逻辑写两遍。**预期结果要声明: 违反案例与 seller_type 是独立采样的 (ER §7.6), 本查询是检验相关性的模板, 不预设 third_party 必然集中违反。

**SQL查询:**
```sql
WITH violation_tickets AS (
    SELECT DISTINCT rvc.ticket_id
    FROM rule_violation_case rvc
    WHERE rvc.run_id = 'eval_20241110_140000'
        AND rvc.impact_severity IN ('critical', 'high')
)
SELECT
    '用户特征' AS 特征类别,
    u.tier_code AS 特征值,
    COUNT(DISTINCT rt.ticket_id) AS 违反工单数,
    ROUND(AVG(u.refund_count_30days), 1) AS 平均30天退款次数,
    ROUND(AVG(o.order_amount), 2) AS 平均订单金额,
    GROUP_CONCAT(DISTINCT dr.rule_id) AS 违反规则列表
FROM violation_tickets vt
JOIN raw_ticket rt ON vt.ticket_id = rt.ticket_id
JOIN user u ON rt.user_id = u.user_id
LEFT JOIN "order" o ON rt.order_id = o.order_id
JOIN rule_violation_case rvc ON vt.ticket_id = rvc.ticket_id
JOIN decision_rule dr ON rvc.rule_id = dr.rule_id
GROUP BY u.tier_code

UNION ALL

SELECT
    '商家类型',
    p.seller_type_code,
    COUNT(DISTINCT rt.ticket_id),
    ROUND(AVG(u.refund_count_30days), 1),
    ROUND(AVG(o.order_amount), 2),
    GROUP_CONCAT(DISTINCT dr.rule_id)
FROM violation_tickets vt
JOIN raw_ticket rt ON vt.ticket_id = rt.ticket_id
JOIN user u ON rt.user_id = u.user_id
JOIN "order" o ON rt.order_id = o.order_id
JOIN product p ON o.product_id = p.product_id
JOIN rule_violation_case rvc ON vt.ticket_id = rvc.ticket_id
JOIN decision_rule dr ON rvc.rule_id = dr.rule_id
GROUP BY p.seller_type_code
ORDER BY 特征类别, 违反工单数 DESC;
```

**预期结果说明:**
返回"用户特征-regular: 12条违反工单, 1.8平均退款次数, $75平均金额, 违反R002/R003";"商家类型-third_party: 8条违反, $85平均金额, 违反R002/R003"。本查询把严重违反案例 (critical/high) 按用户等级、商家类型两个维度拆解,帮助分析师定位"哪类用户/哪类商家的工单更容易触发严重违反"。注:本数据集中规则违反案例 (`rule_violation_case`) 的违反规则以 R002(第三方转交)、R003(高金额) 最高频(见 Query 4),但案例与具体工单的 seller_type 为独立采样,不预设"third_party 必然集中违反 R002"的强相关;该模板可用于在真实数据上检验是否存在此类相关性。

---

## 查询 14: 工单处理时效SLA监控

**业务背景:**
客服运营主管设定了SLA目标:VIP用户工单需在24小时内处理,普通用户48小时内处理。主管每天早上需要检查:有多少工单超时未处理?超时工单的用户等级分布如何?AI系统是否及时将紧急工单升级到人工?这个查询生成SLA达标率报表,帮助主管识别需要加急处理的工单,避免客户投诉升级。

**查询类别:** Date/Time Calculation + SLA Monitoring
**难度级别:** Intermediate
**业务角色:** Operations Manager

**解题思路:**
SLA 的正确定义是"处理时长 = `step3.processed_at - submitted_at`", 而不是"工单年龄 = now - submitted", 所以必须 JOIN `step3_decision_output` 拿到处理完成时间。各等级 SLA 阈值用 CASE 给 (VIP 24h / 其余 48h)。达标判定: `(JULIANDAY(processed_at)-JULIANDAY(submitted_at))*24 <= 阈值`, 用 SUM(CASE...) 分别数达标和超时, 再算达标率。`GROUP BY tier_code`。**这是一个反直觉陷阱 (ER §7.6 T6): 因为 AI 秒级处理, 各等级达标率都会≈100%——这恰恰是要教的点, 真正的人工时延藏在 escalate_to_human=1 的工单里。** 排序用 CASE 按等级从高到低。

**SQL查询:**
```sql
-- SLA = "处理时长" = step3 决策完成时间 - 工单提交时间 (而非"工单年龄 = now - submitted")
-- AI 秒级处理, 因此达标率应接近 100%; 超时主要发生在升级人工的工单上
SELECT
    u.tier_code AS 会员等级,
    CASE
        WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24
        ELSE 48
    END AS SLA小时,
    COUNT(*) AS 工单总数,
    SUM(CASE
        WHEN (JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24 <=
            CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24 ELSE 48 END
        THEN 1 ELSE 0
    END) AS SLA内工单数,
    SUM(CASE
        WHEN (JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24 >
            CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24 ELSE 48 END
        THEN 1 ELSE 0
    END) AS 超时工单数,
    ROUND(SUM(CASE
        WHEN (JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24 <=
            CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24 ELSE 48 END
        THEN 1.0 ELSE 0.0
    END) / COUNT(*) * 100, 1) AS SLA达标率百分比,
    ROUND(MAX((JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24), 2) AS 最大处理小时数
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
JOIN step3_decision_output s3 ON rt.ticket_id = s3.ticket_id
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-7 days')
GROUP BY u.tier_code
ORDER BY
    CASE u.tier_code
        WHEN 'vip_platinum' THEN 1
        WHEN 'vip_gold' THEN 2
        WHEN 'vip_silver' THEN 3
        WHEN 'regular' THEN 4
        ELSE 5
    END;
```

**预期结果说明:**
返回类似"vip_gold: 24h SLA, ~190 条总工单, ~190 条 SLA 内, 0 条超时, 100.0% 达标率, 最大处理 0.01 小时"。由于 AI 秒级处理 (`processed_at - submitted_at` ≈ 几秒), 各等级达标率均接近 100% —— 这正是 AI 客服相比人工 (AHT ~8 分钟) 的核心价值。主管真正要盯的是被升级人工 (`escalate_to_human = 1`) 的那部分工单, 它们才会进入人工队列产生真实时延 (本查询只反映 AI 自动处理时延)。本数据集 7 天滚动窗口下, 普通 (48h SLA) 工单约 900 条, vip_silver/gold/platinum 共约 230 条。

---

## 查询 15: AI决策置信度与实际准确率相关性分析

**业务背景:**
ML工程师在评估AI系统的"自知之明"时,需要检验:AI给出高置信度(>0.9)的决策是否真的更准确?低置信度决策是否应该自动升级人工?如果发现高置信度决策仍有20%错误率,说明模型过于自信,需要校准。这个查询生成置信度分档与准确率的对比,帮助工程师设定合理的"升级人工"阈值(如置信度<0.7自动升级)。

**查询类别:** Statistical Analysis + Bucketing
**难度级别:** Advanced
**业务角色:** ML Engineer

**解题思路:**
先用 CTE 把 `step3_decision_output` JOIN `step3_eval_detail`, 并在 CTE 里用 CASE 把 `confidence` 分成 4 档。`WHERE run_id` 锁定一次评估。外层按档位 `GROUP BY`, 算每档的规则遵守率 `AVG(rule_check_passed)`、升级率 `AVG(escalate_to_human)`。用 CTE 而不是把 CASE 塞进外层, 是因为分档表达式较复杂, 先在 CTE 里算好"置信度档位"这个标签, 外层直接 GROUP BY 标签, 可读性更好、也避免重复书写。`ORDER BY` 用 CASE 保证高→低档位顺序。教学点: 验证"高置信度是否真的更准", 用于设定自动升级阈值。

**SQL查询:**
```sql
WITH confidence_buckets AS (
    SELECT
        s3.output_id,
        s3.action,
        s3.confidence,
        s3.escalate_to_human,
        sed.rule_check_passed,
        CASE
            WHEN s3.confidence >= 0.90 THEN '高置信(>=0.90)'
            WHEN s3.confidence >= 0.75 THEN '中高置信(0.75-0.89)'
            WHEN s3.confidence >= 0.60 THEN '中置信(0.60-0.74)'
            ELSE '低置信(<0.60)'
        END AS 置信度档位
    FROM step3_decision_output s3
    JOIN step3_eval_detail sed ON s3.output_id = sed.output_id
    WHERE sed.run_id = 'eval_20241112_093000'
)
SELECT
    置信度档位,
    COUNT(*) AS 样本数,
    ROUND(AVG(confidence), 3) AS 平均置信度,
    SUM(CASE WHEN rule_check_passed THEN 1 ELSE 0 END) AS 规则检查通过数,
    ROUND(AVG(CASE WHEN rule_check_passed THEN 1.0 ELSE 0.0 END), 3) AS 规则遵守率,
    SUM(CASE WHEN escalate_to_human THEN 1 ELSE 0 END) AS 升级人工数,
    ROUND(AVG(CASE WHEN escalate_to_human THEN 1.0 ELSE 0.0 END), 3) AS 升级率,
    GROUP_CONCAT(DISTINCT action) AS 决策类型分布
FROM confidence_buckets
GROUP BY 置信度档位
ORDER BY
    CASE 置信度档位
        WHEN '高置信(>=0.90)' THEN 1
        WHEN '中高置信(0.75-0.89)' THEN 2
        WHEN '中置信(0.60-0.74)' THEN 3
        ELSE 4
    END;
```

**预期结果说明:**
返回"高置信(>=0.90): 280样本, 0.91平均置信度, 275通过, 0.982规则遵守率, 8升级, 0.029升级率"。工程师发现高置信决策有98%规则遵守率,但仍有2%违反,可以设定阈值"置信度<0.75自动升级"以保险。

---

## 查询 16: 用户生命周期价值与客诉关系分析

**业务背景:**
客户成功经理需要平衡客户满意度与运营成本。经理想知道:高价值用户(累计消费>$3000)的客诉处理成本是否值得?这些用户的工单类型主要是什么?如果发现高价值用户主要是咨询类工单(低处理成本),而低价值用户主要是退款纠纷(高处理成本),可以调整客服资源分配策略。这个查询生成用户价值分层与工单成本的关系,帮助经理优化ROI。

**查询类别:** Join + Customer Segmentation
**难度级别:** Advanced
**业务角色:** Customer Success Manager

**解题思路:**
先用 CTE `user_segments` 按 `total_spent_amount` 把用户分成 4 个价值层 (CASE)。然后 JOIN `raw_ticket → step1_intent_output → intent_category`, 并 `LEFT JOIN step3_decision_output` (用 LEFT 是怕个别工单没有决策输出时把整行丢掉)。聚合粒度是"价值层一行": 人均工单数 `COUNT(DISTINCT ticket)/COUNT(DISTINCT user)`, 升级率 `SUM(escalate)/COUNT(*)`。**预期结果要声明独立性 (ER §7.6): 工单类型与价值层独立生成, 各层升级率主要反映全局 ~15%, 不预设"高价值客户更少纠纷", 本查询是检验该假设的模板。

**SQL查询:**
```sql
WITH user_segments AS (
    SELECT
        user_id,
        user_name,
        tier_code,
        total_spent_amount,
        CASE
            WHEN total_spent_amount >= 5000 THEN '高价值(>=$5000)'
            WHEN total_spent_amount >= 1500 THEN '中高价值($1500-4999)'
            WHEN total_spent_amount >= 500 THEN '中价值($500-1499)'
            ELSE '低价值(<$500)'
        END AS 价值分层
    FROM user
)
SELECT
    us.价值分层,
    COUNT(DISTINCT rt.ticket_id) AS 工单数,
    COUNT(DISTINCT us.user_id) AS 用户数,
    ROUND(COUNT(DISTINCT rt.ticket_id) * 1.0 / COUNT(DISTINCT us.user_id), 2) AS 人均工单数,
    ROUND(AVG(us.total_spent_amount), 2) AS 平均消费金额,
    GROUP_CONCAT(DISTINCT ic.intent_name_cn) AS 主要工单类型,
    ROUND(SUM(CASE WHEN s3.escalate_to_human THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS 升级人工比例
FROM user_segments us
JOIN raw_ticket rt ON us.user_id = rt.user_id
JOIN step1_intent_output s1 ON rt.ticket_id = s1.ticket_id
JOIN intent_category ic ON s1.primary_intent = ic.intent_code
LEFT JOIN step3_decision_output s3 ON rt.ticket_id = s3.ticket_id
GROUP BY us.价值分层
ORDER BY
    CASE us.价值分层
        WHEN '高价值(>=$5000)' THEN 1
        WHEN '中高价值($1500-4999)' THEN 2
        WHEN '中价值($500-1499)' THEN 3
        ELSE 4
    END;
```

**预期结果说明:**
返回类似"高价值(>=$5000): 15条工单, 8个用户, 1.88人均工单, $8250平均消费, 涵盖多种工单类型, 6.7%升级率"。本查询按消费分层统计人均工单数与升级人工比例,帮助经理评估各价值层的客诉处理成本。注:本数据集中工单意图与用户价值分层为独立生成,各层的升级率主要反映全局 ~15% 的 escalate 比例;真实业务中可用本模板检验"高价值用户是否更多咨询类、更少纠纷类"这一假设,从而优化客服资源分配。

---

## 查询 17: 标注争议案例与仲裁效率分析

**业务背景:**
标注质量管理员需要监控标注团队的争议解决效率。管理员关心:有多少标注不一致案例已解决?仲裁员的平均处理时长是多少?未解决案例是否积压?如果发现pending状态案例过多(>20条),说明仲裁资源不足,需要增派人手。这个查询生成争议案例处理状态看板,帮助管理员及时干预,保证标注数据集按时交付。

**查询类别:** Join + Status Tracking
**难度级别:** Intermediate
**业务角色:** Annotation Manager

**解题思路:**
只看不一致的争议案例, 所以 `WHERE is_agreement = 0` 是第一道过滤。从 `annotation_agreement` JOIN `annotation_ground_truth` (用 `annotation_id_1` 拿到标注日期, 好算积压天数)。按 `resolution_status` (pending/resolved/escalated) 分组统计案例数。占比用窗口 `COUNT(*)*100.0/SUM(COUNT(*)) OVER ()`——**空的 `OVER ()` 表示"全表总数"做分母**, 这是算占比常用的窗口写法。积压天数 `JULIANDAY(参考日)-JULIANDAY(annotation_date)`。排序用 CASE 把 pending 排最前, 因为待仲裁的最需要管理员关注。

**SQL查询:**
```sql
SELECT
    aa.resolution_status AS 解决状态,
    COUNT(*) AS 案例数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS 占比百分比,
    COUNT(DISTINCT aa.arbitrator_id) AS 涉及仲裁员数,
    COUNT(DISTINCT aa.ticket_id) AS 涉及工单数,
    ROUND(AVG(JULIANDAY('2024-12-01') - JULIANDAY(ag1.annotation_date)), 1) AS 平均积压天数,
    GROUP_CONCAT(DISTINCT aa.disagreement_field) AS 争议字段类型
FROM annotation_agreement aa
JOIN annotation_ground_truth ag1 ON aa.annotation_id_1 = ag1.annotation_id
WHERE aa.is_agreement = 0  -- 只看不一致案例
GROUP BY aa.resolution_status
ORDER BY
    CASE aa.resolution_status
        WHEN 'pending' THEN 1
        WHEN 'escalated' THEN 2
        WHEN 'resolved' THEN 3
        ELSE 4
    END;
```

**预期结果说明:**
返回"pending: 8案例(32%), 1位仲裁员, 8条工单, 3.5天平均积压, 争议字段primary_intent"。管理员发现pending案例占比32%,平均积压3.5天,可接受范围,但需要持续监控。

---

## 查询 18: 多渠道工单质量对比分析

**业务背景:**
产品经理需要评估不同提交渠道(web表单、APP、在线聊天、邮件、电话录音)的工单质量,优化用户体验。经理想知道:哪个渠道的工单文本最清晰(AI识别准确率高)?哪个渠道用户情绪最负面?是否需要优化某些渠道的引导文案?例如,如果发现"电话录音"渠道的准确率特别低(65%),可能是语音转文字质量差,需要改进ASR模型。

**查询类别:** Aggregation + Cross-channel Analysis
**难度级别:** Intermediate
**业务角色:** Product Manager

**解题思路:**
按提交渠道对比工单质量。链路是 `raw_ticket JOIN step1_intent_output JOIN step1_eval_detail` (借 eval_detail 拿准确率)。`WHERE run_id` 锁定一次评估。`GROUP BY channel`: 准确率 `AVG(is_correct)`、平均文本长度 `AVG(LENGTH(raw_text))`、愤怒比例和高紧急比例用条件 `AVG(CASE...)`。**一个量级陷阱: 因为 JOIN 了 `step1_eval_detail`, 这题只覆盖约 500 条评估样本, 不是全量 5,000 工单**, 预期结果必须说明这点, 否则读者会以为 web_form 只有几百条 (实际全量约 2,500 条)。教学点: 找出哪个渠道质量最差以改进引导文案。

**SQL查询:**
```sql
SELECT
    rt.channel AS 提交渠道,
    COUNT(DISTINCT rt.ticket_id) AS 工单数,
    ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 意图识别准确率,
    ROUND(AVG(LENGTH(rt.raw_text)), 0) AS 平均文本长度,
    ROUND(AVG(CASE WHEN s1.sentiment = 'angry' THEN 1.0 ELSE 0.0 END), 3) AS 愤怒情绪比例,
    ROUND(AVG(CASE WHEN s1.urgency = 'high' THEN 1.0 ELSE 0.0 END), 3) AS 高紧急度比例,
    ROUND(AVG(s1.latency_ms), 0) AS 平均处理延迟ms,
    SUM(CASE WHEN rt.has_attachment THEN 1 ELSE 0 END) AS 含附件工单数
FROM raw_ticket rt
JOIN step1_intent_output s1 ON rt.ticket_id = s1.ticket_id
JOIN step1_eval_detail sed ON s1.output_id = sed.output_id
WHERE sed.run_id = 'eval_20241112_093000'
GROUP BY rt.channel
ORDER BY 工单数 DESC;
```

**预期结果说明:**
返回类似"web_form: ~250 条 (评估样本中), 0.89 准确率, 245 平均长度, 0.15 愤怒比例, 0.62 高紧急比例, 1850ms 延迟, ~75 含附件"。产品经理发现 web 表单工单质量最高 (准确率 0.89), 邮件渠道略低 (0.82), 可以优化邮件提交页的引导文案。注意本查询只看 ~500 条评估样本; 全量工单 (5,000 条) 中 web_form 约 2,500 条。

---

## 查询 19: Prompt变更影响范围预测

**业务背景:**
ML工程师在修改Prompt前,需要评估变更的影响范围,避免引入回归bug。工程师想知道:如果修改Step1 Prompt来提升dispute_non_receipt准确率,是否会影响其他意图的识别?哪些意图可能受影响?应该重点测试哪些样本?这个查询分析当前Prompt在各意图上的表现,帮助工程师识别脆弱点,设计针对性的测试用例。

**查询类别:** Aggregation + Classification Report
**难度级别:** Advanced
**业务角色:** ML Engineer

**解题思路:**
目标是产出一份分类报告: 每个真实意图的准确率 + 它被误判成了什么。先用 CTE `intent_performance`: 从 `step1_eval_detail` JOIN `annotation_ground_truth` (拿真实意图) JOIN `intent_category` (拿名字), 按真实意图聚合算准确率, 并用 `GROUP_CONCAT(DISTINCT predicted_intent)` 把"被误判成的意图"拼成清单。外层再加"质量评级"和"变更风险评估"两个 CASE 派生列。**为什么要 CTE: 外层的 CASE 要基于聚合后的准确率再分档, 不能在同一个 GROUP BY 里直接对聚合值做判断, 所以先聚合 (CTE) 再分类 (外层)。** `ORDER BY 准确率` 让最薄弱、最该回归测试的意图排最前。

**SQL查询:**
```sql
WITH intent_performance AS (
    SELECT
        ag.true_primary_intent AS intent_code,
        ic.intent_name_cn,
        COUNT(*) AS 样本总数,
        SUM(CASE WHEN sed.is_correct THEN 1 ELSE 0 END) AS 正确分类数,
        ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 准确率,
        ROUND(AVG(sed.judge_reasoning_score), 2) AS 平均推理评分,
        GROUP_CONCAT(DISTINCT sed.predicted_intent) AS 被误判为意图列表
    FROM step1_eval_detail sed
    JOIN annotation_ground_truth ag ON sed.annotation_id = ag.annotation_id
    JOIN intent_category ic ON ag.true_primary_intent = ic.intent_code
    WHERE sed.run_id = 'eval_20241112_093000'
    GROUP BY ag.true_primary_intent, ic.intent_name_cn
)
SELECT
    intent_name_cn AS 意图名称,
    样本总数,
    正确分类数,
    准确率,
    平均推理评分,
    被误判为意图列表,
    CASE
        WHEN 准确率 >= 0.90 THEN '✓ 优秀'
        WHEN 准确率 >= 0.75 THEN '→ 良好'
        ELSE '⚠ 需改进'
    END AS 质量评级,
    CASE
        WHEN 准确率 < 0.75 THEN '高风险:修改可能进一步降低'
        WHEN 准确率 BETWEEN 0.75 AND 0.85 THEN '中风险:需回归测试'
        ELSE '低风险:可放心修改'
    END AS 变更风险评估
FROM intent_performance
ORDER BY 准确率, 样本总数 DESC;
```

**预期结果说明:**
返回"dispute_non_receipt: 125样本, 111正确, 0.888准确率, 3.9推理分, 被误判为refund_request, → 良好, 中风险"。工程师可以看到dispute_non_receipt虽然已达0.888,但仍有提升空间,修改Prompt时需重点回归测试refund_request意图(易混淆)。

---

## 查询 20: 综合Dashboard关键指标汇总

**业务背景:**
VP of Engineering每周一早会需要快速了解AI系统的整体健康度。VP关心5个核心问题:1)上周处理了多少工单?2)意图识别准确率达标吗?3)规则违反率是否受控?4)升级人工的比例合理吗?5)系统性能稳定吗?这个查询生成一份Executive Summary,包含所有关键指标的最新值和周环比变化,帮助VP在5分钟内掌握全局,做出资源分配决策。

**查询类别:** Multi-table Aggregation + Executive Summary
**难度级别:** Advanced
**业务角色:** Executive (VP/CTO)

**解题思路:**
这是给高管的一页纸看板, 用 `UNION ALL` 把 7 个来自不同表的 KPI 纵向拼成"指标-值-目标-状态"四列表 (工单量、VIP 占比、准确率、违反率、自动处理率、延迟、成本)。每段各查一张相关表, 用 CASE 对照目标值打 ✓/⚠。**最值得记的 SQLite 限制: UNION 的中间分支不能直接写 `ORDER BY ... LIMIT`, 所以"取最新一次 completed run"必须用子查询 `(SELECT * FROM evaluation_run WHERE run_status='completed' ORDER BY started_at DESC LIMIT 1)` 整体包起来, 再从这个子查询里取字段。** 教学点: 如何把异构 KPI 组装成 5 分钟看懂的 Executive Summary。

**SQL查询:**
```sql
SELECT
    '业务量指标' AS 指标类别,
    '总工单处理量(本周)' AS 指标名称,
    CAST(COUNT(DISTINCT rt.ticket_id) AS TEXT) AS 指标值,
    '' AS 目标值,
    '' AS 状态
FROM raw_ticket rt
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-7 days')

UNION ALL

SELECT
    '业务量指标',
    'VIP工单占比',
    ROUND(AVG(CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 1.0 ELSE 0.0 END) * 100, 1) || '%',
    '15-25%',
    CASE
        WHEN AVG(CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 1.0 ELSE 0.0 END) BETWEEN 0.15 AND 0.25 THEN '✓'
        ELSE '⚠'
    END
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-7 days')

UNION ALL

-- 复合查询的中间分支不能直接写 ORDER BY/LIMIT (SQLite 限制),
-- 改用子查询挑出"最新一次 completed run"再取指标
SELECT
    '质量指标',
    'Step1意图识别准确率',
    ROUND(er.step1_accuracy * 100, 1) || '%',
    '>85%',
    CASE WHEN er.step1_accuracy >= 0.85 THEN '✓' ELSE '⚠' END
FROM (
    SELECT * FROM evaluation_run
    WHERE run_status = 'completed'
    ORDER BY started_at DESC LIMIT 1
) er

UNION ALL

SELECT
    '质量指标',
    'Step3规则违反率',
    ROUND(er.step3_rule_violation_rate * 100, 1) || '%',
    '<5%',
    CASE WHEN er.step3_rule_violation_rate < 0.05 THEN '✓' ELSE '⚠' END
FROM (
    SELECT * FROM evaluation_run
    WHERE run_status = 'completed'
    ORDER BY started_at DESC LIMIT 1
) er

UNION ALL

SELECT
    '效率指标',
    'AI自动处理率(未升级人工)',
    ROUND((1 - AVG(CASE WHEN s3.escalate_to_human THEN 1.0 ELSE 0.0 END)) * 100, 1) || '%',
    '>75%',
    CASE
        WHEN AVG(CASE WHEN s3.escalate_to_human THEN 1.0 ELSE 0.0 END) <= 0.25 THEN '✓'
        ELSE '⚠'
    END
FROM step3_decision_output s3

UNION ALL

SELECT
    '性能指标',
    'Step1平均延迟',
    ROUND(AVG(s1.latency_ms), 0) || 'ms',
    '<2500ms',
    CASE WHEN AVG(s1.latency_ms) < 2500 THEN '✓' ELSE '⚠' END
FROM step1_intent_output s1

UNION ALL

SELECT
    '成本指标',
    '单条工单处理成本(Token费用)',
    '$' || ROUND(AVG(s1.output_tokens) / 1000.0 * 0.015 + 0.003, 4),
    '<$0.01',
    CASE WHEN AVG(s1.output_tokens) / 1000.0 * 0.015 + 0.003 < 0.01 THEN '✓' ELSE '⚠' END
FROM step1_intent_output s1;
```

**预期结果说明:**
返回 Dashboard 视图 (基于本数据集 ~5,000 工单规模):
```
业务量指标 | 总工单处理量 (本周)  | ~1,100  | -       | -
业务量指标 | VIP 工单占比         | 19.2%   | 15-25%  | ✓
质量指标   | Step1 准确率 (v5)    | 90.5%   | >85%    | ✓
质量指标   | Step3 违反率 (v3)    | 3.0%    | <5%     | ✓
效率指标   | AI 自动处理率         | 85.0%   | >75%    | ✓
性能指标   | Step1 平均延迟        | 1847ms  | <2500ms | ✓
成本指标   | 单条成本             | $0.0057 | <$0.01  | ✓
```
VP 看到所有指标均达标 (✓), 系统运行健康, 可继续投资优化。注: 本周工单 ~1,100 是 ~5,000 工单 × 7/30 天的估算; 实际值视提交时间分布而定。

---

## 查询使用指南

### 1. 按业务角色索引

| 角色 | 相关查询编号 |
|-----|------------|
| Operations Manager | 1, 14 |
| ML Engineer | 2, 3, 10, 15, 19 |
| Quality Manager | 4, 13 |
| Annotation Manager | 5, 17 |
| Risk Analyst | 6 |
| Technical Operations | 7 |
| Customer Experience Manager | 8 |
| Operations Analyst | 9 |
| ML Researcher | 10 |
| Product Operations | 11 |
| Tech Lead | 12 |
| Quality Analyst | 13 |
| Customer Success Manager | 16 |
| Product Manager | 18 |
| Executive (VP/CTO) | 20 |

### 2. 按难度级别索引

| 难度 | 查询编号 |
|-----|---------|
| Basic | 1, 5, 8 |
| Intermediate | 2, 3, 4, 6, 7, 9, 11, 12, 14, 17, 18 |
| Advanced | 10, 13, 15, 16, 19, 20 |

### 3. 按查询类别索引

| 类别 | 查询编号 |
|-----|---------|
| Aggregation | 1, 4, 5, 7, 8, 10, 18 |
| Join | 1, 2, 4, 6, 11, 13, 16, 17 |
| Subquery | 3 |
| Window Function | 8, 11, 17 |
| Date/Time Analysis | 9, 14 |
| Statistical Analysis | 10, 15 |
| Cross Tabulation | 8, 11 |
| CTE (Common Table Expression) | 13, 16, 19 |
| Multi-table Aggregation | 20 |

---

## 教学价值

这20个SQL查询覆盖了以下教学点:

1. **业务分析思维:** 每个查询都从业务问题出发,而非技术炫技
2. **JOIN技巧:** 多表关联、LEFT JOIN处理NULL、自引用JOIN
3. **聚合函数:** COUNT/AVG/SUM结合CASE WHEN做条件聚合
4. **窗口函数:** OVER PARTITION BY做分组占比、排名
5. **日期计算:** JULIANDAY差值计算天数、STRFTIME格式化
6. **CTE应用:** WITH子句提升可读性,复用中间结果
7. **UNION组合:** 合并多维度统计结果
8. **字符串函数:** GROUP_CONCAT拼接列表、LENGTH计算长度
9. **条件逻辑:** 复杂CASE WHEN分支、嵌套条件
10. **性能优化:** 合理使用索引字段(PK/FK)、避免全表扫描

---

**生成工具:** Fake Data Generator Agent
**查询版本:** v1.1
**生成日期:** 2024-12-01
