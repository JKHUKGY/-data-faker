# CityPulse 311 数据集 SQL 查询手册

本文档是数据集 `govtech_saas_service_request_intelligence_large` 配套的 20 道 SQL 查询。业务背景请见 `govtech_saas_service_request_intelligence_large_business_context-cn.md`, 表结构与字段说明请见 `govtech_saas_service_request_intelligence_large_er_document-cn.md`。

所有查询都用字面日期 `'2026-06-01'` 作为"今天" (`REFERENCE_DATE`), 不允许 `DATE('now')`, 这样运行结果可复现。所有查询都能在 generator 产出的 SQLite 数据库上直接跑。

## 1. 如何使用本文档

读这份文档的人是新加入 CityPulse 分析组的实习生。Director of Analytics Tom Brennan 把这 20 道查询交给你, 让你这周走一遍, 既是 onboarding, 也是为 Q3 QBR (Quarterly Business Review) 攒分析素材。

每道查询有五个固定模块, 顺序如下:

1. *业务背景*: 谁在问, 为什么问, 答案要喂给哪个决策。这部分不读懂, SQL 跑出来你也不知道意味着什么。
2. *标签*: 类别, 难度, 业务角色。三个短标签, 帮助你按主题或按角色筛选。
3. *解题思路*: 在你看 SQL 之前, 想清楚要碰哪些表, 怎么 join, 聚合粒度是什么, 为什么用 CTE 而不是子查询。这部分是这份文档最重要的部分。
4. *SQL*: 直接可跑的 SQLite 代码。
5. *预期结果与业务结论*: 跑完之后该看到什么, 数字落在什么区间算正常, 拿到这个结果之后下一步该做什么。

每道查询都映射回 business context 文档里五个业务问题之一 (Q1 Other 分类漂移, Q2 严重度文本偏离, Q3 首单速关掩盖, Q4 升级语预测投诉, Q5 租户级模型精度), 或者归到"运营常规题", 文末有一张映射表。

---

## 2. 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| Q1 | Other 类中含强关键词的请求与 SLA 影响 | Senior Analyst | Pattern + Aggregation | 中级 |
| Q2 | 严重度勾选与紧急词不一致的请求 reopen 率 | Senior Analyst | Pattern + Aggregation | 中级 |
| Q3 | 24 小时速关后 30 天同址复发的请求识别 | Director of Analytics | Window Function | 高级 |
| Q4 | 升级语对 council 投诉的预测力 | VP of Customer Success | Pattern + Subquery | 中级 |
| Q5 | 按 tenant 的 classifier accuracy 与 SLA 联动 | CDO | Aggregation + Join | 中级 |
| Q6 | Other 路由到通用队列的 SLA 表现对比 | Senior Analyst | Aggregation + Join | 基础 |
| Q7 | 月度请求量与渠道 mix 趋势 | Senior Analyst | Aggregation + Date | 基础 |
| Q8 | SLA breach rate 最差的 20 个 tenants | VP of Customer Success | Aggregation + Join | 基础 |
| Q9 | 各 channel 的严重度勾选准确性对比 | Director of Data Science | Aggregation + Pattern | 中级 |
| Q10 | ARR 按城市大小与 AI Insight Pack 渗透率 | CRO | Aggregation + Join | 基础 |
| Q11 | 按 vocab_drift_level 分层的模型准确率 | CDO | Aggregation + RANK | 中级 |
| Q12 | 真实"按时解决率"扣除 30 天复发后的重算 | Director of Analytics | CTE + Join | 高级 |
| Q13 | 升级语请求的 council 投诉升级渠道构成 | VP of Customer Success | Pattern + EXISTS | 中级 |
| Q14 | Reopen 时间分布与 cohort 分析 | Senior Analyst | Date + Aggregation | 中级 |
| Q15 | 按 category_group 的请求量 top 10 | Senior Analyst | Aggregation + Join | 基础 |
| Q16 | Other misroute 对 SLA 总损失估算 (按 tenant) | CDO | CTE + Pattern | 高级 |
| Q17 | French vocab tenants 的 classifier accuracy 下降 | Director of Data Science | CTE + Join | 中级 |
| Q18 | Top staff users 处理量与 SLA 表现 | Senior Analyst | Subquery + Join | 中级 |
| Q19 | Reopen 率最高的 categories | Senior Analyst | Window + Aggregation | 中级 |
| Q20 | 12 个核心指标的 tenant health 仪表板 | CEO (经 Senior Analyst 提交) | Aggregation | 基础 |

---

## 3. Q1 Other 类中含强关键词的请求与 SLA 影响

业务背景:

你的直接 manager Tom Brennan 把这题放在 onboarding 第一题。Marcus Chen (CDO) 一直怀疑分类器对 Other 类用得太"保守": 模型对置信度低的请求一概兜底到 Other, 而 Other 在所有 tenant 的路由里都进了 `is_general_queue = 1` 的部门, 这个部门 SLA target 普遍是 5 个工作日, 比专门部门的 1 到 2 天慢得多。如果 Other 类里有相当一部分本来应该被分到 pothole, streetlight, illegal_dumping, graffiti, noise_complaint, tree 这六个大类之一, 那这些请求就是被"错路由"到了慢通道, SLA 表现差是必然的。Tom 让你先把这个数量级量出来, 再决定要不要给 Marcus 写一份模型置信度阈值调整的备忘录。

这题对应业务问题 1 (Other 分类漂移)。预期看到的画面: Other 类中含强关键词的子集占 Other 总量约 12%, 这一子集的 SLA breach rate 显著高于非 Other 请求的 breach rate, 形成约 ~8pp 的差距 (Other 约 0.29 vs 非 Other 约 0.21)。

标签: Pattern Matching, Aggregation, 中级, Senior Analyst。

解题思路:

这题要把"Other 类"和"非 Other 类"对比 SLA breach rate, 还要在 Other 类里进一步切出"描述含强关键词"和"不含"两个子集。要点表是 `service_requests` 加 `request_descriptions` 加 `service_categories` (为了拿到 `is_other` 标志), 再 LEFT JOIN `sla_breach_log` 判断是否 breach (注意是 LEFT JOIN, 因为 sla_breach_log 只有 breach 的请求, 不 LEFT JOIN 会把非 breach 的请求剔除导致分母错)。聚合粒度是 (auto_category 是否 Other, 描述是否含关键词) 的 2 × 2 表。关键词检索用 `LOWER(...) LIKE` 来不区分大小写。

```sql
WITH labeled AS (
    SELECT
        sr.request_id,
        sc.is_other,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%pothole%'
              OR LOWER(rd.description_text) LIKE '%hole in road%'
              OR LOWER(rd.description_text) LIKE '%streetlight%'
              OR LOWER(rd.description_text) LIKE '%street light%'
              OR LOWER(rd.description_text) LIKE '%graffiti%'
              OR LOWER(rd.description_text) LIKE '%illegal dumping%'
              OR LOWER(rd.description_text) LIKE '%dumped%'
              OR LOWER(rd.description_text) LIKE '%noise%'
              OR LOWER(rd.description_text) LIKE '%tree limb%'
              OR LOWER(rd.description_text) LIKE '%fallen tree%'
            THEN 1 ELSE 0
        END AS has_strong_keyword,
        CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END AS is_breach
    FROM service_requests sr
    JOIN service_categories sc ON sc.category_id = sr.auto_category_id
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
      AND sr.closed_at IS NOT NULL
)
SELECT
    is_other,
    has_strong_keyword,
    COUNT(*) AS request_count,
    SUM(is_breach) AS breach_count,
    ROUND(1.0 * SUM(is_breach) / COUNT(*), 3) AS sla_breach_rate
FROM labeled
GROUP BY is_other, has_strong_keyword
ORDER BY is_other, has_strong_keyword;
```

预期结果与业务结论:

4 行结果 (以下行数是 trailing 12 个月窗口 `created_at >= '2025-06-01'` 的量级, 约为全量 36 个月的 1/3; 实测见括号)。`(is_other=0, has_strong_keyword=0)` 是最大的一块, 约 19 万 closed 请求 (实测 191223), breach rate 约 0.21。`(is_other=0, has_strong_keyword=1)` 约 11 万 (实测 111144; 这些是被正确分类、描述里本就带强关键词的常规请求, 例如真的报 pothole 的 Streets 请求), breach rate 与上者相近 (约 0.21)。`(is_other=1, has_strong_keyword=0)` 约 2.3 万 (实测 22955, 真正无法归类的 Other), breach rate 约 0.29 (Other 通道本就慢)。`(is_other=1, has_strong_keyword=1)` 是关键块, 约 3100 条 (实测 3100), breach rate 约 0.29, 比非 Other 高约 8pp。

这告诉 Tom: `auto_category = Other` 在窗口内约 2.6 万条 (全量约 8 万, 占总量约 8%), 其中约 12% (窗口内约 3000 条、全量约 9600 条) 是模型本可以正确分类却漏掉的 (描述里明确含强关键词), 这些请求被路由到慢通道, 拖累了整体 SLA 表现。下一步动作: 给 Marcus 和 Priya 写一页备忘, 建议把 NLP 模型 fallback 阈值从 0.45 下调到 0.35, 同时检查这六个大类的 token vocabulary 是否覆盖了 IVR 转写常见错拼。

---

## 4. Q2 严重度勾选与紧急词不一致的请求 reopen 率

业务背景:

Tom 让你接着 Q1 往严重度方向看。CityPulse 让居民在提交时勾选 Low / Medium / High / Emergency 四档严重度, 但居民对自己情况的严重程度判断常常和直觉相反: 真正紧急的事 (家里闻到燃气味, 看到电线落地, 小孩被流浪狗咬伤) 反而有人勾"Medium", 因为他们觉得"还没到 emergency"; 反过来一些小事 (邻居晚上音乐声大) 有人勾"High"因为忍无可忍。这种偏差结构化字段是看不见的, 但文本里的紧急词 (gas leak, live wire, fire, smoke, child injured, leaking) 能暴露。我们看 stated_severity 为 Low / Medium 但描述里出现紧急词的请求, 它们的 reopen rate 是否显著高于基线, 因为这种"被错配到普通队列"的请求往往现场处置后问题还在。

这题对应业务问题 2。预期看到的画面: 紧急词子集 reopen rate 约 24%, 基线约 5%, lift 约 5 倍。(generator 把"emergency-kw 且 stated_severity 为 low/med"子集的 reopen 概率设到 0.25; 由于已从普通模板里去掉了 'leaking' 的污染, 紧急词命中集是纯注入子集, 实测稳定落在约 0.24。)

标签: Pattern Matching, Aggregation, 中级, Senior Analyst。

解题思路:

reopen 的判定要看 `request_events` 表中是否存在 event_type = 'reopened' 的事件。一种写法是 EXISTS 子查询, 一种写法是 LEFT JOIN 再 COUNT。这里 LEFT JOIN 更直观也更快。把 SR 限制在 stated_severity in ('low', 'medium') 的子集, 再按"描述是否含紧急词"切两组, 算各组的 reopen rate。注意时间窗口要让 reopen 有发生的余地, 这里用过去 12 个月 (2025-06-01 到 2026-06-01) closed 的请求。

```sql
WITH base AS (
    SELECT
        sr.request_id,
        sr.stated_severity,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%gas leak%'
              OR LOWER(rd.description_text) LIKE '%live wire%'
              OR LOWER(rd.description_text) LIKE '%fire%'
              OR LOWER(rd.description_text) LIKE '%smoke%'
              OR LOWER(rd.description_text) LIKE '%child injured%'
              OR LOWER(rd.description_text) LIKE '%kid hurt%'
              OR LOWER(rd.description_text) LIKE '%leaking%'
            THEN 1 ELSE 0
        END AS has_emergency_keyword
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    WHERE sr.stated_severity IN ('low', 'medium')
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
      AND sr.closed_at IS NOT NULL
),
reopens AS (
    SELECT DISTINCT request_id
    FROM request_events
    WHERE event_type = 'reopened'
      AND event_at >= '2025-06-01'
      AND event_at < '2026-07-01'
)
SELECT
    b.has_emergency_keyword,
    COUNT(*) AS closed_request_count,
    SUM(CASE WHEN r.request_id IS NOT NULL THEN 1 ELSE 0 END) AS reopened_count,
    ROUND(
        1.0 * SUM(CASE WHEN r.request_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        3
    ) AS reopen_rate
FROM base b
LEFT JOIN reopens r ON r.request_id = b.request_id
GROUP BY b.has_emergency_keyword
ORDER BY b.has_emergency_keyword;
```

预期结果与业务结论:

2 行 (trailing 12 个月窗口, low/med 子集)。`has_emergency_keyword = 0` 约 22 万行 (实测 221974), reopen rate 约 0.05 (实测 0.048)。`has_emergency_keyword = 1` 约 2.4 万行 (实测 24280), reopen rate 约 0.24 (实测 0.241)。lift 约 5 倍。(全量 36 个月口径下分别约 67 万 / 7.5 万行。)

这约 2.4 万条请求是 CityPulse 给客户做"AI Insight Pack 价值故事"时最有说服力的一组: 它们是模型唯一能识别但目前没被识别的"被错配紧急请求", 平台理论上能基于文本提前 elevate 它们的优先级, 减少 reopen 与下游升级。下一步动作: 把这个 lift 数字带进 QBR deck 的 page 3, 配一个产品建议"在 intake 阶段对 description 跑紧急词扫描, 自动提示 supervisor 重评严重度"。

---

## 5. Q3 24 小时速关后 30 天同址复发的请求识别

业务背景:

Tom 把这题留到第三天, 因为它是技术上最有挑战的一道, 但也是 CityPulse 团队最在意的一道。VP of Field Operations Practice (公司内 Customer Success 的一个垂直小组) Andrea Chu 在上次客户复盘会上听一个客户城市的 311 主任抱怨: "你们的 SLA 数字看起来漂亮, 但我家附近的垃圾报修每三个月就来一次, 而你们的报告说 95% 按时解决了"。Tom 怀疑是现场 crew 的"first touch close"KPI 在驱动行为: crew 到现场后快速关单冲 KPI, 但问题没真正解决, 居民 30 天内换个口径再报。

这题对应业务问题 3。预期看到的画面: 24 小时内关闭且 SLA 达标的请求里约 28% 有同址 30 天内复发, 而非速关请求约 20%, 速关组比非速关高约 8pp。(绝对水平偏高是因为 36 个月、100 万请求集中在 15 万地址上, 随机簇集本身就贡献了约 20% 的同址 30 天碰撞基线; trap 的可观察信号是速关组比基线高出的那 ~8pp。)

标签: Window Function, 高级, Director of Analytics。

解题思路:

这题的核心是"同址 30 天内有另一条新请求"。同地址的判定用 address_id 相等, 同时要求不是同一条 request_id 也不是 duplicate 关系。窗口函数 `LEAD` 在按 (address_id, created_at) 排序后能拿到下一条请求的时间, 但仅当下一条存在且属于同 address 才有意义, 因此要用分区窗口 `PARTITION BY address_id ORDER BY created_at`。注意 address_id 可能为 NULL (匿名地址或者 walk_in 没记录地址), 这些行要排除, 否则 NULL 之间会被错误地聚到一起。最后判断"24 小时内关闭"的逻辑用 `julianday(closed_at) - julianday(created_at) <= 1.0`。

```sql
WITH base AS (
    SELECT
        sr.request_id,
        sr.address_id,
        sr.created_at,
        sr.closed_at,
        CASE
            WHEN sr.closed_at IS NOT NULL
             AND julianday(sr.closed_at) - julianday(sr.created_at) <= 1.0
            THEN 1 ELSE 0
        END AS is_quick_close,
        CASE WHEN sbl.breach_id IS NULL THEN 1 ELSE 0 END AS is_on_time
    FROM service_requests sr
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.address_id IS NOT NULL
      AND sr.is_duplicate = 0
      AND sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-05-01'
),
with_next AS (
    SELECT
        request_id,
        address_id,
        created_at,
        closed_at,
        is_quick_close,
        is_on_time,
        LEAD(created_at) OVER (
            PARTITION BY address_id
            ORDER BY created_at
        ) AS next_request_at_same_address
    FROM base
)
SELECT
    is_quick_close,
    COUNT(*) AS closed_on_time_count,
    SUM(
        CASE
            WHEN next_request_at_same_address IS NOT NULL
             AND julianday(next_request_at_same_address) - julianday(closed_at) <= 30
            THEN 1 ELSE 0
        END
    ) AS repeat_within_30d,
    ROUND(
        1.0 * SUM(
            CASE
                WHEN next_request_at_same_address IS NOT NULL
                 AND julianday(next_request_at_same_address) - julianday(closed_at) <= 30
                THEN 1 ELSE 0
            END
        ) / COUNT(*),
        3
    ) AS repeat_at_address_rate
FROM with_next
WHERE is_on_time = 1
GROUP BY is_quick_close
ORDER BY is_quick_close;
```

预期结果与业务结论:

2 行 (window 为 11 个月 `created_at` 在 ['2025-06-01','2026-05-01')、address 非空、is_duplicate=0、on-time)。`is_quick_close = 0` 大约 11.6 万条 (实测 116223), repeat_at_address_rate 约 0.22。`is_quick_close = 1` 大约 10.8 万条 (实测 107873), repeat_at_address_rate 约 0.30。绝对水平较高 (因为 100 万请求集中在 15 万地址上随机簇集本身就有 ~22% 同址 30 天碰撞), 但速关组比非速关组高约 8.1pp (0.302 vs 0.221), 这是 trap 的可观察信号。(注: 修复后速关请求一律 on-time, 两组行数接近。)

这是 Tom 想要的"被掩盖的失败率"。下一步: Tom 让你把这道查询固化成"shadow SLA"指标, 每周给 Rachel Wong 送一份 top 10 worst tenants 名单, 让她去和这些城市的 311 主任谈话, 调整 crew 的 KPI 设计 (例如把"first touch close"换成"30 天内不复发的 first touch close")。这个数字也会出现在 QBR deck 的 page 5, 作为"产品视角下需要给客户提供的新指标"的论据。

---

## 6. Q4 升级语对 council 投诉的预测力

业务背景:

VP of Customer Success Rachel Wong 这周问 Marcus 一个具体问题: "我们有没有一个早期信号能在居民升级到 city council 之前把这个请求 flag 出来, 让我的 CSM 团队能预先介入到客户城市内部?" Marcus 把题转给你。你的假设是, 居民升级前在 311 平台上的描述文字里通常已经露过马脚: "third time this month", "fed up", "going to the news", "I will contact my councilman", "lawyer" 这类话本身就是预升级信号。问题是, 这种文本特征和最终 council 升级之间的 lift 到底有多大, 值得不值得 product 团队在 intake 阶段加一层文本扫描。

这题对应业务问题 4。预期看到的画面: 含升级语的请求 60 天内升级到 council 的概率约 8%, 不含的约 0.3%, lift 约 25 倍。

标签: Pattern Matching, Subquery (EXISTS), 中级, VP of Customer Success。

解题思路:

升级判定用 `citizen_complaints` 表是否存在引用本 request_id 的记录, 且 `filed_at` 在 `service_requests.created_at` 之后 60 天内。EXISTS 子查询是最自然的写法, 也比 LEFT JOIN 后 DISTINCT 更高效。文本扫描用 LOWER LIKE 覆盖 5 个升级短语。这题的输出是 2 行, 但其商业价值在 lift 的倍数。

```sql
SELECT
    has_escalation_phrase,
    COUNT(*) AS request_count,
    SUM(escalated_within_60d) AS escalated_count,
    ROUND(1.0 * SUM(escalated_within_60d) / COUNT(*), 4) AS council_escalation_rate
FROM (
    SELECT
        sr.request_id,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%third time%'
              OR LOWER(rd.description_text) LIKE '%fed up%'
              OR LOWER(rd.description_text) LIKE '%contact my councilman%'
              OR LOWER(rd.description_text) LIKE '%going to the news%'
              OR LOWER(rd.description_text) LIKE '%get a lawyer%'
              OR LOWER(rd.description_text) LIKE '%my lawyer%'
            THEN 1 ELSE 0
        END AS has_escalation_phrase,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM citizen_complaints cc
                WHERE cc.primary_request_id = sr.request_id
                  AND julianday(cc.filed_at) - julianday(sr.created_at) <= 60
            ) THEN 1 ELSE 0
        END AS escalated_within_60d
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    WHERE sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-04-01'
) t
GROUP BY has_escalation_phrase
ORDER BY has_escalation_phrase;
```

预期结果与业务结论:

2 行 (window 为 10 个月 `created_at` 在 ['2025-06-01','2026-04-01'))。`has_escalation_phrase = 0` 约 27 万行, escalation rate 约 0.003 (0.3%)。`has_escalation_phrase = 1` 约 8000 行, escalation rate 约 0.08 (8%)。Lift 约 25 倍, P value 用 Fisher exact 不用算就显著。(全量 36 个月口径下分别约 80 万 / 2.4 万行。)

下一步动作: 这个 lift 是 Rachel 在 QBR 上要给客户讲的故事的核心数据。建议 Product 把"升级语扫描"作为 AI Insight Pack v3 的功能, 在请求落库后第一时间 flag 这类请求并通知客户的 311 主任, 同时 CityPulse 自己的 CSM 在月度健康度 review 时把这类请求多的客户列入风险关注。

---

## 7. Q5 按 tenant 的 classifier accuracy 与 SLA 联动

业务背景:

Marcus Chen 这次直接给你下指令了: 准备一张表, 列出每个 tenant 在 audited subset 上的 classifier accuracy, 同时附上同期的 SLA breach rate。他想看的是, accuracy 低的城市是不是 SLA 也差, 用一张散点图证明"模型质量直接影响客户运营产出"。这个故事最终要喂给 CEO Linda 用来在 QBR 上做"AI Insight Pack 价值兑现"的论证。

这题对应业务问题 5。预期看到的画面: 大多数 tenant accuracy 在 0.85 到 0.92 之间, 10 个 vocab_drift_level = 'high' 的 tenant 在 0.72 到 0.78 之间; 同时这 10 个 tenant 的 SLA breach rate 平均比中位数高约 8 个百分点。

标签: Aggregation + Join, 中级, CDO。

解题思路:

需要把两张派生指标在 tenant 粒度对齐: classifier accuracy 来自 `model_predictions` 在 `is_audited = 1` 子集上 (predicted_category_id 等于 ground_truth_category_id 的占比), SLA breach rate 来自 `sla_breach_log` 与 `service_requests` 的对照。聚合粒度都是 tenant_id, 因此分别算两张子查询再 JOIN 即可。也可以用 CTE 让两个聚合分开写清楚。注意只算 closed 的请求, 否则 SLA breach 分母失真。

```sql
WITH accuracy_by_tenant AS (
    SELECT
        sr.tenant_id,
        COUNT(*) AS audited_count,
        SUM(
            CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
        ) AS correct_count,
        ROUND(
            1.0 * SUM(
                CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
            ) / COUNT(*),
            3
        ) AS classifier_accuracy
    FROM model_predictions mp
    JOIN service_requests sr ON sr.request_id = mp.request_id
    WHERE mp.is_audited = 1
      AND mp.predicted_at >= '2025-06-01'
      AND mp.predicted_at < '2026-06-01'
    GROUP BY sr.tenant_id
),
sla_by_tenant AS (
    SELECT
        sr.tenant_id,
        COUNT(*) AS closed_count,
        SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) AS breach_count,
        ROUND(
            1.0 * SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
            3
        ) AS sla_breach_rate
    FROM service_requests sr
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
    GROUP BY sr.tenant_id
)
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    t.vocab_drift_level,
    a.classifier_accuracy,
    s.sla_breach_rate,
    a.audited_count,
    s.closed_count
FROM tenants t
JOIN accuracy_by_tenant a ON a.tenant_id = t.tenant_id
JOIN sla_by_tenant s ON s.tenant_id = t.tenant_id
ORDER BY a.classifier_accuracy ASC;
```

预期结果与业务结论:

120 行 (注意是全部 120 个 tenant, 不是 85 个: `model_predictions` 对未启用 AI Pack 的 tenant 也有 audited 子集, 模拟"在 sandbox 跑模型但没在生产路由器使用", 因此 raw accuracy 覆盖全部租户; 只有 tenant_health_snapshots.classifier_accuracy 对未启用者为 NULL)。前 10 行 (即 accuracy 最低的 10 个) 应该全部是 vocab_drift_level = 'high', accuracy 在 0.72 到 0.78 之间 (实测 0.717 到 0.777, 最低 sherbrooke_qc 0.717, 最高 jackson_ms 0.777; 第 11、12 名才是 medium, 约 0.82), SLA breach rate 大约 0.30 左右 (而全局中位数约 0.21)。

下一步动作: 把这张表导出成 CSV 喂给 Marcus 的散点图; 同时把这 10 个 tenant 的名字单独拉一张子表, 与 Director of Data Science Priya Iyer 约一次会议, 讨论是否对这批城市做"本地化 fine tune" (法语城市用 fr_CA 训练子集, 深南方城市用 region tagged subcorpus)。这些 tenant 也是 Rachel 的"续约风险关注名单"的第一梯队。

---

## 8. Q6 Other 路由到通用队列的 SLA 表现对比

业务背景:

接 Q1 的链路再往下看: Other 类的请求确实路由到了 `is_general_queue = 1` 的部门, 那这些部门的实际 SLA target 多长, 实际处理时长多长, 与专门部门 (例如 Streets, Sanitation) 比, 差多少? 你写一道相对简单的查询给 Tom, 让他在和 Rachel 对齐每周 sync 时用。

这题对应业务问题 1。

标签: Aggregation + Join, 基础, Senior Analyst。

解题思路:

把 service_requests 按 routed_dept 是否 general_queue 分两组, 算 SLA breach rate 和 average actual_business_days。涉及表 `service_requests`, `departments`, `sla_breach_log`。只看 closed 请求。LEFT JOIN sla_breach_log 因为非 breach 的请求在这张表里没有记录。

```sql
SELECT
    d.is_general_queue,
    COUNT(*) AS closed_request_count,
    SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) AS breach_count,
    ROUND(
        1.0 * SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        3
    ) AS sla_breach_rate,
    ROUND(AVG(sbl.actual_business_days), 2) AS avg_actual_business_days_for_breached,
    ROUND(AVG(julianday(sr.closed_at) - julianday(sr.created_at)), 2) AS avg_calendar_days
FROM service_requests sr
JOIN departments d ON d.dept_id = sr.routed_dept_id
LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
WHERE sr.closed_at IS NOT NULL
  AND sr.created_at >= '2025-06-01'
  AND sr.created_at < '2026-06-01'
GROUP BY d.is_general_queue
ORDER BY d.is_general_queue;
```

预期结果与业务结论:

2 行 (trailing 12 个月窗口)。`is_general_queue = 0` 约 30 万行, breach rate 约 0.21, avg_calendar_days 约 3 到 4。`is_general_queue = 1` 约 2.6 万行, breach rate 约 0.29, avg_calendar_days 约 5 到 6 (通用队列 target 5 个工作日且 breach 占比更高, 因此处理时长明显更长)。`avg_actual_business_days_for_breached` 这一列也是通用队列更高 (约 8 vs 专门部门约 5 到 6)。

下一步动作: 把这个数字写进周会, 提醒 Customer Success 在和客户讨论 SLA 表现时主动区分"专门部门"和"通用队列", 防止客户拿全口径 SLA 当 sole KPI 来谈续约。

---

## 9. Q7 月度请求量与渠道 mix 趋势

业务背景:

最简单的运营题, Tom 让你周一早会汇报"过去 12 个月平台流量趋势", 顺便看渠道 mix 是否在迁移 (语音下降, 移动 / 社交上升)。

不直接挂在五个业务问题之一, 但是 QBR deck 的开场页内容, 也是月度 CRO 看板上的固定一张表。

标签: Aggregation + Date, 基础, Senior Analyst。

解题思路:

按 (month, channel_code) 双维聚合 request_id 计数。`strftime('%Y-%m', created_at)` 拿到月份。从 `intake_channels` 拿 `channel_code` 友好名。结果按月排序, 横向看每个 channel 的份额变动。

```sql
SELECT
    strftime('%Y-%m', sr.created_at) AS month_label,
    ic.channel_code,
    COUNT(*) AS request_count
FROM service_requests sr
JOIN intake_channels ic ON ic.channel_id = sr.channel_id
WHERE sr.created_at >= '2025-06-01'
  AND sr.created_at < '2026-06-01'
GROUP BY month_label, ic.channel_code
ORDER BY month_label, ic.channel_code;
```

预期结果与业务结论:

12 个月 × 6 渠道 = 72 行。web 月度量 25000 左右, mobile_app 23000 左右且月度环比小幅增长, ivr 18000 左右且月度环比小幅下降, social 8000 左右, email 6000 左右, walk_in 2500 左右。整体月度趋势平稳, 季节性在 4 月 (春季城市清洁季) 略升。

下一步动作: 这张图直接进 QBR deck page 1, 提示客户城市的运营压力主要在春季和初秋 (落叶季, 路面坑洼修补季)。

---

## 10. Q8 SLA breach rate 最差的 20 个 tenants

业务背景:

Rachel Wong 每周二早会想要的一张固定表: 过去 30 天 SLA breach rate 最差的 20 个客户城市, 她拿去派给对应的 CSM 跟进。注意她要的是过去 30 天 (rolling 30 days), 不是月度滚动。

不直接挂业务问题, 但 Rachel 团队每周的运营核心输入。

标签: Aggregation + Join, 基础, VP of Customer Success。

解题思路:

按 tenant 聚合过去 30 天 closed 请求的 breach rate。注意要把分母门槛设到 50 条以上, 避免少量请求的小城市 (人口几万, 30 天可能只有 10 几条请求) 因为偶然事件登上 worst 榜。

```sql
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    t.size_tier,
    COUNT(*) AS closed_request_count,
    SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) AS breach_count,
    ROUND(
        1.0 * SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        3
    ) AS sla_breach_rate
FROM tenants t
JOIN service_requests sr ON sr.tenant_id = t.tenant_id
LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
WHERE sr.closed_at IS NOT NULL
  AND sr.closed_at >= '2026-05-01'
  AND sr.closed_at < '2026-06-01'
GROUP BY t.tenant_id, t.tenant_code, t.tenant_name, t.size_tier
HAVING COUNT(*) >= 50
ORDER BY sla_breach_rate DESC, breach_count DESC
LIMIT 20;
```

预期结果与业务结论:

20 行。Top 5 大概率包含 vocab_drift_level = 'high' 的几个 tenant (Quebec 系, 深南方系), breach rate 在 0.30 到 0.40 区间。其余 15 行是常规分布偶尔波动到顶部的 tenant, breach rate 在 0.28 到 0.30 之间。

下一步动作: Rachel 给 top 20 的 CSM 各发一封"本周 SLA 异常关注"邮件, 让 CSM 在客户城市的周会上主动 raise 起来。

---

## 11. Q9 各 channel 的严重度勾选准确性对比

业务背景:

Director of Data Science Priya Iyer 在和你的 1:1 里聊到, 她怀疑 IVR 渠道因为语音转文字加上居民口语化, 真实严重度被勾选的准确率比 web 低很多。这关系到她在 model card 里要不要按 channel 加 feature。你帮她快速量化这件事。

这题对应业务问题 2。

标签: Aggregation + Pattern, 中级, Director of Data Science。

解题思路:

定义"严重度勾选准确"为: 描述含紧急词时 stated_severity 是 high 或 emergency; 描述不含紧急词时 stated_severity 是 low 或 medium。然后按 channel 聚合这个 0/1 指标的平均值。这题的 trick 在于"准确"的定义对每个分组是两个互斥子集合的混合, 用 CASE 表达式就能搞定, 不需要 union。

```sql
WITH labeled AS (
    SELECT
        ic.channel_code,
        sr.stated_severity,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%gas leak%'
              OR LOWER(rd.description_text) LIKE '%live wire%'
              OR LOWER(rd.description_text) LIKE '%fire%'
              OR LOWER(rd.description_text) LIKE '%smoke%'
              OR LOWER(rd.description_text) LIKE '%child injured%'
              OR LOWER(rd.description_text) LIKE '%kid hurt%'
              OR LOWER(rd.description_text) LIKE '%leaking%'
            THEN 1 ELSE 0
        END AS has_emergency_keyword
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    JOIN intake_channels ic ON ic.channel_id = sr.channel_id
    WHERE sr.created_at >= '2025-12-01'
      AND sr.created_at < '2026-06-01'
)
SELECT
    channel_code,
    COUNT(*) AS request_count,
    SUM(
        CASE
            WHEN has_emergency_keyword = 1 AND stated_severity IN ('high', 'emergency') THEN 1
            WHEN has_emergency_keyword = 0 AND stated_severity IN ('low', 'medium') THEN 1
            ELSE 0
        END
    ) AS consistent_count,
    ROUND(
        1.0 * SUM(
            CASE
                WHEN has_emergency_keyword = 1 AND stated_severity IN ('high', 'emergency') THEN 1
                WHEN has_emergency_keyword = 0 AND stated_severity IN ('low', 'medium') THEN 1
                ELSE 0
            END
        ) / COUNT(*),
        3
    ) AS consistency_rate
FROM labeled
GROUP BY channel_code
ORDER BY consistency_rate DESC;
```

预期结果与业务结论:

6 行。web 和 mobile_app 在 0.86 到 0.88 之间, email 在 0.84 左右, social 在 0.78 左右 (短文本, hashtag 多), ivr 在 0.70 到 0.74 之间 (转写损失), walk_in 在 0.85 左右 (call_taker 代填严重度)。

下一步动作: Priya 在 model card 加一个 channel feature, 让模型在 IVR 来的请求上更主动地用文本严重度覆盖 stated_severity。CityPulse Product 也可以基于这个数据决定是否给 IVR 接入"实时紧急词监听"模块。

---

## 12. Q10 ARR 按城市大小与 AI Insight Pack 渗透率

业务背景:

CRO Daniel Ortega 在 QBR 上做的最常见的事是把 ARR 分解到 size_tier × pack 渗透维度。他要看的是: large 城市的 AI Insight Pack 渗透率多少 (理论上应该接近 100%), small 城市渗透率多少 (理论上 50% 到 70%)。这道题是他每季度都跑一次的常规题。

不直接挂业务问题, 但 CRO 看板固定题。

标签: Aggregation + Join, 基础, CRO。

解题思路:

按 (size_tier, has_ai_insight_pack) 双维聚合 tenant 数量和 ARR 总和。只取 active 合同。

```sql
SELECT
    t.size_tier,
    ts.has_ai_insight_pack,
    COUNT(*) AS tenant_count,
    ROUND(SUM(ts.arr_usd), 0) AS total_arr_usd,
    ROUND(AVG(ts.arr_usd), 0) AS avg_arr_usd
FROM tenants t
JOIN tenant_subscriptions ts ON ts.tenant_id = t.tenant_id
WHERE ts.is_active = 1
GROUP BY t.size_tier, ts.has_ai_insight_pack
ORDER BY t.size_tier, ts.has_ai_insight_pack DESC;
```

预期结果与业务结论:

最多 6 行 (3 个 size_tier × has_ai_insight_pack 0/1), 实测落点: large 城市 17 个、全部启用 (17/17 = 100%, 因为大城样本小且渗透目标 95% 偏高), avg_arr 约 90 万; medium 城市 74 个、启用 62 个 (84%), avg_arr 约 42 万; small 城市 29 个、启用 17 个 (59%), avg_arr 约 18 万。120 个 active 合同的总 ARR 合计约 5200 万美元 (实测 51.9M)。注意 medium 偏多是因为不少 18 万到 21 万人口的城市按定义 (≥15 万) 落在 medium。

下一步动作: 给 Daniel 的明年 budget 提案补一组数据, 重点是 small tier 的 AI Insight Pack 升级机会 (渗透只有约 60%, 是分层里最低的), 估算如果渗透从 60% 提到 80% 大约新增 ARR 多少。

---

## 13. Q11 按 vocab_drift_level 分层的模型准确率

业务背景:

继续 Q5 的故事。Marcus 在看完 Q5 散点图后, 让你把 tenant 按 vocab_drift_level 三档 (low / medium / high) 分组, 给每组做一个 accuracy 的统计摘要, 还要按 size_tier 进一步 cross tab。他想知道是不是 large + high vocab drift 的 tenant 拖累最大。

这题对应业务问题 5。

标签: Aggregation + Window (RANK), 中级, CDO。

解题思路:

先按 (vocab_drift_level, size_tier) 双维分组算每组的 accuracy 平均值和 tenant 数, 然后用 RANK 在 vocab_drift_level 内部按 accuracy 升序排序。这道题展示 GROUP BY 后再 OVER 的"按分组排序"用法。

```sql
WITH per_tenant_accuracy AS (
    SELECT
        sr.tenant_id,
        ROUND(
            1.0 * SUM(
                CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
            ) / COUNT(*),
            3
        ) AS accuracy
    FROM model_predictions mp
    JOIN service_requests sr ON sr.request_id = mp.request_id
    WHERE mp.is_audited = 1
      AND mp.predicted_at >= '2025-06-01'
      AND mp.predicted_at < '2026-06-01'
    GROUP BY sr.tenant_id
),
joined AS (
    SELECT
        t.tenant_id,
        t.vocab_drift_level,
        t.size_tier,
        pta.accuracy
    FROM tenants t
    JOIN per_tenant_accuracy pta ON pta.tenant_id = t.tenant_id
)
SELECT
    vocab_drift_level,
    size_tier,
    COUNT(*) AS tenant_count,
    ROUND(AVG(accuracy), 3) AS avg_accuracy,
    MIN(accuracy) AS min_accuracy,
    MAX(accuracy) AS max_accuracy,
    RANK() OVER (
        PARTITION BY vocab_drift_level
        ORDER BY AVG(accuracy) ASC
    ) AS rank_within_drift_level
FROM joined
GROUP BY vocab_drift_level, size_tier
ORDER BY vocab_drift_level, avg_accuracy ASC;
```

预期结果与业务结论:

9 行 (3 drift levels × 3 size tiers)。vocab_drift_level = 'high' 的三档 size_tier 上 avg_accuracy 都在 0.70 到 0.75; vocab_drift_level = 'medium' 在 0.83 到 0.86; vocab_drift_level = 'low' 在 0.87 到 0.90。规模对准确率影响不大, vocab drift 是主导因子。

下一步动作: 这张表确证了 Q5 散点的"vocab drift 是关键"假设。Marcus 拿去和 Priya 对齐: 下季度 Data Science 团队要做的是按方言/词表分层做模型, 而不是简单地按规模分层。

---

## 14. Q12 真实"按时解决率"扣除 30 天复发后的重算

业务背景:

Tom 给你的"最难一题": Q3 暴露了 24 小时速关组里约 28% 同址复发 (非速关约 20%), 那如果我们对全体请求把"30 天内同址复发"也算成失败, 重算"真实按时解决率", 这个新指标比当前报告的"按时解决率"低多少? 这个数字直接关系到客户能信任 CityPulse 的报告到什么程度。

这题对应业务问题 3。

标签: CTE + Join + Window, 高级, Director of Analytics。

解题思路:

这题要先打三个标签: (a) 是否 on_time (即非 breach), (b) 是否同址 30 天内复发, (c) "真实" 按时 = on_time AND NOT repeated。然后按 tenant 算两个 rate: reported (即仅看 (a)) 和 true (即 (c))。最后输出两个 rate 的差值。窗口函数 LAG/LEAD 用来识别同址下一个请求, 与 Q3 相同。CTE 让两个 rate 在 tenant 粒度上 JOIN。

```sql
WITH base AS (
    SELECT
        sr.tenant_id,
        sr.request_id,
        sr.address_id,
        sr.created_at,
        sr.closed_at,
        CASE WHEN sbl.breach_id IS NULL THEN 1 ELSE 0 END AS is_on_time
    FROM service_requests sr
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.closed_at IS NOT NULL
      AND sr.address_id IS NOT NULL
      AND sr.is_duplicate = 0
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-05-01'
),
with_next AS (
    SELECT
        b.*,
        LEAD(created_at) OVER (
            PARTITION BY address_id
            ORDER BY created_at
        ) AS next_request_at_same_address
    FROM base b
),
labeled AS (
    SELECT
        tenant_id,
        is_on_time,
        CASE
            WHEN next_request_at_same_address IS NOT NULL
             AND julianday(next_request_at_same_address) - julianday(closed_at) <= 30
            THEN 1 ELSE 0
        END AS has_repeat_within_30d
    FROM with_next
)
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    COUNT(*) AS total_requests,
    ROUND(1.0 * SUM(is_on_time) / COUNT(*), 3) AS reported_on_time_rate,
    ROUND(
        1.0 * SUM(CASE WHEN is_on_time = 1 AND has_repeat_within_30d = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        3
    ) AS true_on_time_rate,
    ROUND(
        1.0 * SUM(is_on_time) / COUNT(*)
        - 1.0 * SUM(CASE WHEN is_on_time = 1 AND has_repeat_within_30d = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        3
    ) AS gap
FROM labeled l
JOIN tenants t ON t.tenant_id = l.tenant_id
GROUP BY t.tenant_id, t.tenant_code, t.tenant_name
HAVING COUNT(*) >= 500
ORDER BY gap DESC
LIMIT 30;
```

预期结果与业务结论:

约 30 行。reported_on_time_rate 在 0.72 到 0.85 之间, true_on_time_rate 比 reported 低 0.18 到 0.25 (因为同址 30 天复发的基线本身就高)。Gap top 10 集中在请求量大的 large tenant, 因为同址簇集效应更明显。即使扣除自然簇集 (~20pp 是基线噪声), 速关组对真实解决率的相对损耗仍可以从分组对比中读出。

下一步动作: 这是 QBR deck 最有冲击力的一页。提醒 Linda 和 Daniel: 我们之前给客户城市发的月度报告 dashboard 里"按时解决率"是高估的, 需要在下个迭代里把"真实按时解决率"作为可选第二口径加进去, 否则当客户自己发现这件事时我们会很被动。

---

## 15. Q13 升级语请求的 council 投诉升级渠道构成

业务背景:

Q4 给了一个 lift 数字 (含升级语 vs 不含的总体升级概率)。Rachel 进一步想看的是: 在真的升级了的请求里, 不同 escalation_channel (council_letter, news_media, lawyer_letter, social_viral) 的构成是什么样? 含升级语的子集是不是更偏向某一种升级渠道? 这关系到 product 把扫描器命中后该优先提醒哪种风险。

这题对应业务问题 4。注意它是 Q4 的"按渠道拆细"补充: Q4 给总体升级率与 lift, Q13 给渠道构成。两题的"升级"口径必须一致 (都限 created 后 60 天内), 因此本查询的 LEFT JOIN 也带 60 天约束。

标签: Pattern + EXISTS + Aggregation, 中级, VP of Customer Success。

解题思路:

把 Q4 的"升级到 council"按 escalation_channel 拆细。把 has_escalation_phrase 标签和 escalation_channel 在 SR 粒度上对齐 (LEFT JOIN 限 60 天, 与 Q4 同口径), 然后按 (has_escalation_phrase, escalation_channel) 双维聚合。escalation_channel 为 NULL 的行 (没升级的请求) 也要保留, 但展示时归成 'no_escalation' 一类。`pct_within_phrase_group` 用窗口函数算出"在同一个 has_escalation_phrase 组内, 各渠道占比", 这样能直接读出升级语子集 vs 非升级语子集的渠道构成差异。

```sql
WITH labeled AS (
    SELECT
        sr.request_id,
        sr.created_at,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%third time%'
              OR LOWER(rd.description_text) LIKE '%fed up%'
              OR LOWER(rd.description_text) LIKE '%contact my councilman%'
              OR LOWER(rd.description_text) LIKE '%going to the news%'
              OR LOWER(rd.description_text) LIKE '%get a lawyer%'
              OR LOWER(rd.description_text) LIKE '%my lawyer%'
            THEN 1 ELSE 0
        END AS has_escalation_phrase
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    WHERE sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-04-01'
),
joined AS (
    SELECT
        l.request_id,
        l.has_escalation_phrase,
        COALESCE(cc.escalation_channel, 'no_escalation') AS escalation_channel
    FROM labeled l
    LEFT JOIN citizen_complaints cc
        ON cc.primary_request_id = l.request_id
       -- 与 Q4 口径对齐: 只算 created 后 60 天内提交的投诉
       AND julianday(cc.filed_at) - julianday(l.created_at) <= 60
)
SELECT
    has_escalation_phrase,
    escalation_channel,
    COUNT(*) AS request_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY has_escalation_phrase), 2) AS pct_within_phrase_group
FROM joined
GROUP BY has_escalation_phrase, escalation_channel
ORDER BY has_escalation_phrase, escalation_channel;
```

预期结果与业务结论:

最多 10 行 (2 个 has_escalation_phrase 值 × 最多 5 种 escalation_channel 含 no_escalation)。每个 phrase 组里绝大多数仍是 `no_escalation` (含升级语组约 92%, 不含组约 99.7%, 因为升级本身是小概率事件)。真正升级的那一小部分里, 渠道构成大致 council_letter 约 60%, news_media 约 15%, lawyer_letter 约 15%, social_viral 约 10%; 含升级语子集的升级总量 (= 1 - no_escalation 占比) 明显大于不含组, 这正是 Q4 lift 的渠道级体现。`pct_within_phrase_group` 让你一眼看出两组的渠道分布差异。

下一步动作: 把 "contact my councilman" 这一类升级语作为最强信号继续单拎, 因为它在 council_letter 类升级里 lift 最高。Product 把扫描器命中这条短语时单独配高优先级提醒。

---

## 16. Q14 Reopen 时间分布与 cohort 分析

业务背景:

你自己想搞清楚: closed 之后多久最容易 reopen? 24 小时内? 2 到 7 天? 还是 8 到 30 天? (业务规则上 reopen 只允许发生在 close 后 30 天内, 超过 30 天的再次报修会被当作一条全新请求, 不算 reopen。) 这关系到 CityPulse 的"reopen 监控窗口"应该设多久, 以及要不要额外加一个更短的即时 alert。

不直接挂业务问题, 但 product 团队会关心的运营题。

标签: Date 分析 + Aggregation, 中级, Senior Analyst。

解题思路:

对每条 reopen 事件, 计算它的 event_at 与对应 service_request 最近一次 closed event_at 的差。需要从 request_events 里取出 reopened 事件和它之前最近的 closed 事件, 然后做差。SQLite 没有直接的"上一个事件"概念, 用窗口函数 LAG 按 (request_id, event_at) 排序拿到。

```sql
WITH events_ordered AS (
    SELECT
        request_id,
        event_type,
        event_at,
        LAG(event_at) OVER (PARTITION BY request_id ORDER BY event_at) AS prev_event_at,
        LAG(event_type) OVER (PARTITION BY request_id ORDER BY event_at) AS prev_event_type
    FROM request_events
    WHERE event_at >= '2025-06-01'
      AND event_at < '2026-06-01'
),
reopens_with_gap AS (
    SELECT
        request_id,
        event_at AS reopened_at,
        prev_event_at AS last_closed_at,
        CAST(julianday(event_at) - julianday(prev_event_at) AS INTEGER) AS days_since_close
    FROM events_ordered
    WHERE event_type = 'reopened'
      AND prev_event_type = 'closed'
)
SELECT
    CASE
        WHEN days_since_close <= 1 THEN '0_1_day'
        WHEN days_since_close <= 7 THEN '2_7_days'
        WHEN days_since_close <= 30 THEN '8_30_days'
        WHEN days_since_close <= 90 THEN '31_90_days'
        ELSE 'over_90_days'
    END AS days_bucket,
    COUNT(*) AS reopen_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_reopens
FROM reopens_with_gap
GROUP BY days_bucket
ORDER BY
    CASE days_bucket
        WHEN '0_1_day' THEN 1
        WHEN '2_7_days' THEN 2
        WHEN '8_30_days' THEN 3
        WHEN '31_90_days' THEN 4
        ELSE 5
    END;
```

预期结果与业务结论:

3 个非空桶 (业务规则: reopen 只发生在 close 后 30 天内, 因此 31_90_days 与 over_90_days 恒为 0, 这两桶不会出现在结果里)。reopen 延迟是前置加权的 (越靠近 close 越密集): 0_1_day 约 27% (居民现场看到 crew 走后还有问题就马上 reopen), 2_7_days 约 25%, 8_30_days 约 48%。结论: 30 天窗口按设计覆盖 100% 的 reopen, 而前两天就贡献了超过四分之一。

下一步动作: 把这个分布作为依据告诉 Product, 当前"reopen 监控窗口 30 天"覆盖全部 reopen 是合理的, 同时应该额外给 supervisor 一个"close 后 48 小时 alert"功能 (因为前两天就贡献了约 25% 的 reopen, 是最该抢救的一批)。

---

## 17. Q15 按 category_group 的请求量 top 10

业务背景:

最简单的一题。Tom 让你给 deck page 2 准备"过去 12 个月平台上最常见的请求大类"。

不直接挂业务问题, 是 deck 常规页。

标签: Aggregation + Join, 基础, Senior Analyst。

解题思路:

按 category_group 聚合 SR 数量, 取 top 10。注意 category_group 一共 8 个, 所以实际是按数量排序的 8 行。

```sql
SELECT
    sc.category_group,
    COUNT(*) AS request_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM service_requests sr
JOIN service_categories sc ON sc.category_id = sr.auto_category_id
WHERE sr.created_at >= '2025-06-01'
  AND sr.created_at < '2026-06-01'
GROUP BY sc.category_group
ORDER BY request_count DESC
LIMIT 10;
```

预期结果与业务结论:

8 行 (实际 category_group 数)。Streets 约 24.5%, Sanitation 约 21%, Utilities 约 18%, Parks 约 10.5%, Code 约 8.4%, Other 约 8.0%, Animal 约 5%, Noise 约 4%。(修复后 Other 回到约 8%, 不再因抽样泄漏涨到 14%; Code 与 Other 几乎并列。)

下一步动作: 这是 deck page 2 直接配的柱状图。Tom 看完后会让你单独把 Other 那一栏拎到 page 3, 引出 Q1 的故事。

---

## 18. Q16 Other misroute 对 SLA 总损失估算 (按 tenant)

业务背景:

Marcus 看完 Q1 的数据后想知道, 如果 Other 类中含强关键词的子集本可以被正确路由, 那能减少多少 SLA breach? 这个估算是给 Linda 的 QBR deck 上"AI Insight Pack 改进的潜在 ROI"页配的数字。每个 tenant 算一遍, 找出 ROI 最大的前 10 个 tenant, 这些就是 CityPulse 优先 fine tune 的目标客户。

这题对应业务问题 1, 也是 Q1 的下游应用。

标签: CTE + Pattern + Aggregation, 高级, CDO。

解题思路:

每个 tenant: 算其 Other 类中含强关键词的请求数 (作为"可挽救池"), 估算这些请求如果被正确分类的 SLA breach rate (用非 Other 类的 breach rate 作为代理), 与当前 Other 类整体 breach rate 的差额乘以池大小, 得到"可避免的 breach 数"。Tenant 间 rank 后取 top 10。

```sql
WITH classified AS (
    SELECT
        sr.tenant_id,
        sr.request_id,
        sc.is_other,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%pothole%'
              OR LOWER(rd.description_text) LIKE '%hole in road%'
              OR LOWER(rd.description_text) LIKE '%streetlight%'
              OR LOWER(rd.description_text) LIKE '%street light%'
              OR LOWER(rd.description_text) LIKE '%graffiti%'
              OR LOWER(rd.description_text) LIKE '%illegal dumping%'
              OR LOWER(rd.description_text) LIKE '%dumped%'
              OR LOWER(rd.description_text) LIKE '%noise%'
              OR LOWER(rd.description_text) LIKE '%tree limb%'
              OR LOWER(rd.description_text) LIKE '%fallen tree%'
            THEN 1 ELSE 0
        END AS has_strong_keyword,
        CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END AS is_breach
    FROM service_requests sr
    JOIN service_categories sc ON sc.category_id = sr.auto_category_id
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
),
rates AS (
    SELECT
        tenant_id,
        SUM(CASE WHEN is_other = 1 AND has_strong_keyword = 1 THEN 1 ELSE 0 END) AS misroute_pool,
        SUM(CASE WHEN is_other = 1 AND has_strong_keyword = 1 AND is_breach = 1 THEN 1 ELSE 0 END) AS misroute_breach_count,
        SUM(CASE WHEN is_other = 0 THEN is_breach ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN is_other = 0 THEN 1 ELSE 0 END), 0) AS non_other_breach_rate,
        SUM(CASE WHEN is_other = 1 THEN is_breach ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN is_other = 1 THEN 1 ELSE 0 END), 0) AS other_breach_rate
    FROM classified
    GROUP BY tenant_id
)
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    r.misroute_pool,
    ROUND(r.other_breach_rate, 3) AS other_breach_rate,
    ROUND(r.non_other_breach_rate, 3) AS non_other_breach_rate,
    ROUND(
        r.misroute_pool * (r.other_breach_rate - r.non_other_breach_rate),
        1
    ) AS avoidable_breaches
FROM rates r
JOIN tenants t ON t.tenant_id = r.tenant_id
WHERE r.misroute_pool >= 20
ORDER BY avoidable_breaches DESC
LIMIT 10;
```

预期结果与业务结论:

最多 10 行 (受 `misroute_pool >= 20` 过滤, 只有请求量大的 large 城市能进榜, 因为 12 个月窗口里单 tenant 的 Other 强关键词池通常只有几十到一百多条)。Top 1 tenant 大概率是请求量最大的 large 城市 + AI Insight Pack 启用; `misroute_pool` 约几十到一百多, `other_breach_rate - non_other_breach_rate` 约 0.08 (0.29 vs 0.21), 因此 `avoidable_breaches` 约 5 到 15 (12 个月窗口口径)。Top 10 加起来约 60 到 120 个 avoidable breaches。换算到全量 36 个月约为这个数的 3 倍。

下一步动作: 这个数字本身不大, 但 Marcus 关注的是"这是仅靠调阈值就能拿到的免费收益", 边际成本几乎为零。建议立即在这 10 个 tenant 上 A/B 测试新阈值。

---

## 19. Q17 French vocab tenants 的 classifier accuracy 下降

业务背景:

继续 Marcus 和 Priya 的故事。Priya 想单独看 Quebec 系城市 (has_french_vocab = 1) 的 classifier accuracy 比同等规模的其他城市低多少, 这个数字决定她要不要专门为这批城市做一个法语 fine tune 子模型。

这题对应业务问题 5。

标签: CTE + Join + Aggregation, 中级, Director of Data Science。

解题思路:

按 has_french_vocab 分组, 在 size_tier 控制下对比 accuracy。涉及 CTE 算 per-tenant accuracy, 然后 JOIN tenants 表分组。

```sql
WITH per_tenant_accuracy AS (
    SELECT
        sr.tenant_id,
        1.0 * SUM(
            CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
        ) / COUNT(*) AS accuracy,
        COUNT(*) AS audited_count
    FROM model_predictions mp
    JOIN service_requests sr ON sr.request_id = mp.request_id
    WHERE mp.is_audited = 1
      AND mp.predicted_at >= '2025-06-01'
      AND mp.predicted_at < '2026-06-01'
    GROUP BY sr.tenant_id
)
SELECT
    t.has_french_vocab,
    t.size_tier,
    COUNT(*) AS tenant_count,
    ROUND(AVG(pta.accuracy), 3) AS avg_accuracy,
    ROUND(MIN(pta.accuracy), 3) AS min_accuracy,
    ROUND(MAX(pta.accuracy), 3) AS max_accuracy
FROM tenants t
JOIN per_tenant_accuracy pta ON pta.tenant_id = t.tenant_id
GROUP BY t.has_french_vocab, t.size_tier
ORDER BY t.has_french_vocab DESC, t.size_tier;
```

预期结果与业务结论:

6 行。`has_french_vocab=1` 的 4 个 tenant 在 large 和 medium 两档上, accuracy 约 0.70 到 0.74。`has_french_vocab=0` 的同等规模 tenant 中 vocab_drift_level 不全为 high (只有深南方那 6 个城市是 high), accuracy 整体 0.85 到 0.88。差距约 15pp。

下一步动作: 给 Priya 一份建议书, 提议建一个 fr_CA fine tune subset, 用过去 24 个月 Quebec 系 tenant 的 description 做训练, 预期 lift accuracy 至少 10pp。

---

## 20. Q18 Top staff users 处理量与 SLA 表现

业务背景:

你自己有点好奇: 在 staff_users 里, 哪些 staff 处理量最大? 他们处理过的请求 SLA 表现如何? 这个有点像内部"个人 KPI 板", 但 Tom 提醒你不要把这个发给客户城市, 只给 CityPulse 内部参考。

不直接挂业务问题, 是内部探索题。

标签: Subquery + Join, 中级, Senior Analyst。

解题思路:

通过 request_assignments 找到每条请求最早的 assigned staff, 再聚合到 staff_id 算处理量。SLA 表现通过 LEFT JOIN sla_breach_log。一个 staff 处理多条请求, 因此 group by staff_id。

```sql
WITH first_assignment AS (
    SELECT
        request_id,
        staff_id,
        MIN(assigned_at) AS first_assigned_at
    FROM request_assignments
    WHERE staff_id IS NOT NULL
      AND assigned_at >= '2025-06-01'
      AND assigned_at < '2026-06-01'
    GROUP BY request_id, staff_id
),
joined AS (
    SELECT
        fa.staff_id,
        fa.request_id,
        CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END AS is_breach
    FROM first_assignment fa
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = fa.request_id
)
SELECT
    su.staff_id,
    su.staff_name,
    su.role,
    d.dept_name,
    t.tenant_code,
    COUNT(*) AS handled_count,
    SUM(j.is_breach) AS breach_count,
    ROUND(1.0 * SUM(j.is_breach) / COUNT(*), 3) AS breach_rate
FROM joined j
JOIN staff_users su ON su.staff_id = j.staff_id
JOIN departments d ON d.dept_id = su.dept_id
JOIN tenants t ON t.tenant_id = su.tenant_id
GROUP BY su.staff_id, su.staff_name, su.role, d.dept_name, t.tenant_code
HAVING COUNT(*) >= 100
ORDER BY handled_count DESC
LIMIT 20;
```

预期结果与业务结论:

20 行。前几名通常是 large 城市的 supervisor 角色, 每人 12 个月内处理 1000 到 3000 条请求, breach rate 在 0.15 到 0.30 之间, 与该 tenant 整体水平相近 (没有特别离群)。

下一步动作: 把这张表存档, 等季度内部 ops review 时 Director Tom 用来对照不同客户城市的"work load 分布是否均衡"。

---

## 21. Q19 Reopen 率最高的 categories

业务背景:

Tom 想看哪些 category 的请求最容易被 reopen, 这关系到 CityPulse 在和客户讨论 SLA 设置时是否要建议"对这些 category 设置更长的 SLA, 让现场 crew 有时间一次解决"。

不直接挂业务问题, 但和 trap 2, 3 有关。

标签: Window + Aggregation, 中级, Senior Analyst。

解题思路:

按 category 聚合 reopen rate, 再用 RANK 排序输出 top 10。reopen 判定用 request_events 表。

```sql
WITH category_stats AS (
    SELECT
        sc.category_id,
        sc.category_code,
        sc.category_group,
        COUNT(DISTINCT sr.request_id) AS total_closed,
        COUNT(DISTINCT
            CASE WHEN re.event_type = 'reopened' THEN sr.request_id END
        ) AS reopened_count
    FROM service_requests sr
    JOIN service_categories sc ON sc.category_id = sr.auto_category_id
    LEFT JOIN request_events re
        ON re.request_id = sr.request_id
       AND re.event_type = 'reopened'
       AND re.event_at >= '2025-06-01'
       AND re.event_at < '2026-07-01'
    WHERE sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
    GROUP BY sc.category_id, sc.category_code, sc.category_group
),
ranked AS (
    SELECT
        category_id,
        category_code,
        category_group,
        total_closed,
        reopened_count,
        ROUND(1.0 * reopened_count / total_closed, 3) AS reopen_rate,
        RANK() OVER (ORDER BY 1.0 * reopened_count / total_closed DESC) AS rk
    FROM category_stats
    WHERE total_closed >= 500
)
SELECT *
FROM ranked
WHERE rk <= 10
ORDER BY rk;
```

预期结果与业务结论:

10 行。Top 大概率是 illegal_dumping, abandoned_vehicle, noise_complaint, tree_limb (这些是现场处置后容易"问题原样回来"的 category), reopen rate 在 0.10 到 0.18 之间。Streets 大类的 pothole 反而较低 (一次修补能管久)。

下一步动作: 把这份名单给 Customer Success, 在和这些 category 占比大的客户做季度 review 时, 主动提议"对 illegal_dumping 等高 reopen 类目放宽 SLA 或者引入二次回访检查"。

---

## 22. Q20 12 个核心指标的 tenant health 仪表板

业务背景:

最后一道。Linda 想要在 QBR deck 的最后一页放一张 12 个核心指标 × 4 个代表 tenant 的对照表, 直接喂给董事会。你来准备这张表。4 个代表 tenant 是: City of Austin (large + healthy + low drift), Ville de Québec (large + high vocab drift), City of Plano (medium + average + low drift), City of Burlington (small)。(注意: Mesa 人口约 51 万, 按定义是 large, 所以这里用 Plano 作为 medium 的代表, 不用 Mesa。)

不直接挂业务问题, 是 deck 闭页。

标签: Aggregation, 基础, CEO (经 Senior Analyst 提交)。

解题思路:

直接从 `tenant_health_snapshots` 取一行月度快照, JOIN tenants 做展示。这张表是 generator 在所有事实表生成后聚合写入的, 所以直接 SELECT 即可, 不需要重新算。注意取的是 **2026-03-01** 这个**已完全结算的月份**, 而不是最新的 2026-05: 因为锚点 2026-06-01 前一两个月里那些"长耗时 breach"还没来得及在锚点前关闭, 会让最近月的 sla_breach_rate 系统性偏低 (真实运营仪表板都有这种近因偏差); 取一个完全结算的月份更能代表稳定状态。

```sql
SELECT
    t.tenant_code,
    t.tenant_name,
    t.size_tier,
    t.vocab_drift_level,
    ths.request_count,
    ROUND(ths.sla_breach_rate, 3) AS sla_breach_rate,
    ROUND(ths.reopen_rate, 3) AS reopen_rate,
    ROUND(ths.repeat_at_address_rate, 3) AS repeat_at_address_rate,
    ROUND(ths.classifier_accuracy, 3) AS classifier_accuracy,
    ROUND(ths.council_escalation_rate, 4) AS council_escalation_rate,
    ths.nps_score,
    ths.churn_risk_band
FROM tenant_health_snapshots ths
JOIN tenants t ON t.tenant_id = ths.tenant_id
WHERE ths.snapshot_month = '2026-03-01'
  AND t.tenant_code IN ('austin_tx', 'quebec_qc', 'plano_tx', 'burlington_vt')
ORDER BY
    CASE t.tenant_code
        WHEN 'austin_tx' THEN 1
        WHEN 'quebec_qc' THEN 2
        WHEN 'plano_tx' THEN 3
        WHEN 'burlington_vt' THEN 4
    END;
```

预期结果与业务结论:

4 行 (取 2026-03 月度快照, 固定 seed 下数值可复现):

| tenant | size/drift | request_count | sla_breach_rate | reopen_rate | repeat_at_address_rate | classifier_accuracy | council_escalation_rate | nps_score | churn_risk_band |
|--------|-----------|---------------|-----------------|-------------|------------------------|---------------------|-------------------------|-----------|------------------|
| Austin | large / low | 968 | 0.191 | 0.064 | 0.238 | 0.909 | 0.0031 | 38 | **low** |
| Québec | large / high | 509 | 0.301 | 0.057 | 0.282 | 0.722 | 0.0020 | -10 | **high** |
| Plano | medium / low | 286 | 0.210 | 0.091 | 0.232 | 0.803 | 0.0035 | 27 | **medium** |
| Burlington | small / low | 46 | 0.304 | 0.091 | 0.310 | 0.909 | 0.0000 | -14 | **high** |

故事很清楚: Austin (健康大城) churn low; Québec (high vocab drift) 是真正的麻烦 —— classifier_accuracy 只有 0.72 (全场最低, 即 trap 5 的 laggard), 叠加最高的 SLA breach, churn 落 high; Plano 作为 medium 均值代表落 medium。Burlington 是个有意思的教学点: 它是只有 46 单/月的小城, 单月 SLA 抖到 0.30 就把 churn 顶成 high, 但它的 classifier_accuracy 高达 0.91, 说明它的 high 是"小样本月度噪声 + 偶发 SLA", 不是模型质量问题 —— 提醒分析师对小 tenant 的单月指标不要过度反应。

> 注 (修复后的两个口径): (1) `reopen_rate` / `repeat_at_address_rate` 现在是真聚合值, 可用 Q14 / Q19 / Q3 在事实表上交叉验证, 不再是 sla 的合成函数。(2) 取 2026-03 而非最新月, 是为了避开"锚点附近长耗时 breach 未结算"的近因偏差; churn_risk_band 三档 (low/medium/high) 在平台内都有真实分布, 不再像旧版那样全是 medium。

下一步动作: 这就是 deck 最后一页, Linda 在 QBR 上用这一页讲完后会跳到 Q&A。准备好回答董事会的"为什么 Quebec 那么差"问题, 答案是 Q11 和 Q17 的数据组合 (vocab drift 导致 classifier accuracy 掉到 0.72)。

---

## 23. 业务问题与查询的对应

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 Other 分类漂移 | Q1, Q6, Q16 |
| Q2 严重度文本暗示偏离 | Q2, Q9 |
| Q3 首单速关掩盖重复 | Q3, Q12 |
| Q4 升级语对投诉的预测 | Q4, Q13 |
| Q5 租户级模型精度差异 | Q5, Q11, Q17 |
| 运营常规题 (不直接挂问题) | Q7, Q8, Q10, Q14, Q15, Q18, Q19, Q20 |

每道查询都映射到至少一个业务问题或运营关注点。运营常规题虽然不直接对应五个业务问题之一, 但都是 CityPulse 各角色 (CRO, VP CS, Director of Analytics) 日常会跑的固定题, 它们的存在保证了这份手册的实用性而不仅仅是"五个陷阱的演示集合"。
