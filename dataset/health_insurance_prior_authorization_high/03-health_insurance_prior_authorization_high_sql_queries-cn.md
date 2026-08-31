# 事前授权运营业务 SQL 查询

**数据集:** `health_insurance_prior_authorization_high`
**引擎:** SQLite(所有查询都兼容 SQLite)
**查询总数:** 30
**参考日期 (TODAY):** 在生成时通过 `date.today()` 解析。生成器每次都把时间戳重锚到系统当天,所以 `DATE('now', '-N days')` 过滤条件在重新生成后不久执行总会返回非空结果。

业务背景、公司画像、行业科普、术语表请见 `01-health_insurance_prior_authorization_high_business_context-cn.md`;表结构、字段、生成规则请见 `02-health_insurance_prior_authorization_high_er_document-cn.md`。本文档假设你已经读过这两份。

---

## 1. 如何使用本文档

这份文档是写给一名刚读完业务背景和 ER 文档、即将被经理派去跑这些查询的实习生看的。它不只是 SQL 清单,而是一份教学材料:每道题先讲清楚为什么要问、怎么想,再给 SQL,最后告诉你拿到数字后该做什么。

每个查询都按同一个五段式结构组织,建议按顺序读:

- **业务背景** 交代谁在问、什么场景触发、答案会影响什么决定。这一段把查询和真实业务挂钩。
- **类别 / 难度 / 业务角色** 三个标签,帮你快速判断这道题练的是哪种 SQL 技巧、难度几何、服务于哪个岗位。
- **解题思路** 在你看到 SQL 之前,先讲该碰哪些表、join 怎么搭、聚合的粒度是什么、为什么用 (或不用) CTE 与窗口函数、以及 SQLite 上要注意的坑。读完这一段,你应该能自己写个八九不离十。
- **SQL** 可直接在生成的 SQLite 数据库上运行的查询本体。
- **预期结果** 先描述结果集的形状和关键量级 (这些量级对应 ER 文档里声明的业务陷阱),再点明分析师下一步该做什么。跑出数字只是分析的开始,不是结束。

两个约定贯穿全文。第一,每个查询的时间过滤都用 `DATE('now', '-N days')` 这种滚动窗口写法,而不是写死某个固定日期,因为生成器把数据锚定到运行当天,这样重新生成后查询永远有数据。第二,每道题都能追溯回业务背景文档里列出的某个业务问题;文末有一张业务问题到查询的映射表。

---

## 2. 查询索引

| # | 标题 | 类别 | 难度 | 角色 |
|---|---|---|---|---|
|  1 | 按状态查看每日 PA 请求量 | Aggregation + Date | Basic | Operations |
|  2 | 按金属层级查看批准率 | Join + Aggregation | Basic | Executive |
|  3 | 高频拒绝码 Top N(JSON 展开) | Aggregation + JSON | Intermediate | Analyst |
|  4 | 按角色看审核员产能 | Join + Aggregation | Basic | Manager |
|  5 | 按紧急度看平均处理小时数 | Join + Aggregation + Date | Intermediate | Manager |
|  6 | 按紧急度看 SLA 违约率 | Join + Aggregation | Intermediate | Operations |
|  7 | Provider 批准率离群点 | Join + Aggregation | Intermediate | Manager |
|  8 | 网络内 vs 网络外批准率对比 | Join + Aggregation | Basic | Finance |
|  9 | PA → Claim 转化率(漏损分析) | Join + Aggregation | Intermediate | Finance |
| 10 | 各层级申诉量 | Aggregation | Basic | Operations |
| 11 | 各层级申诉推翻率 | Aggregation | Basic | Manager |
| 12 | 多级申诉漏斗 | CTE + Aggregation | Advanced | Analyst |
| 13 | 按专科看拒绝热力图 | Join + Aggregation | Intermediate | Analyst |
| 14 | 请求量 Top 10 操作编码 | Join + Aggregation | Basic | Operations |
| 15 | 按决定看 confidence 分位数 | Window (NTILE) | Intermediate | Analyst |
| 16 | 月度 PA 量趋势 + 环比增长 | Window (LAG) | Intermediate | Executive |
| 17 | 6 个月决定构成漂移 | CTE + Window | Advanced | Executive |
| 18 | 开放请求老化 + SLA 风险 | Date + Join | Intermediate | Operations |
| 19 | 多次提请的会员(慢性病 cohort) | Subquery | Basic | Analyst |
| 20 | 审核员工作量均衡 | CTE + Window (RANK) | Advanced | Manager |
| 21 | 按类别看政策被引用率 | Join + JSON | Intermediate | Analyst |
| 22 | 保障即将到期的会员 | Date + Join | Intermediate | Operations |
| 23 | 自动规则 vs 人工决定结果 | Join + Aggregation | Intermediate | Executive |
| 24 | 临床笔记类型分布 | Aggregation + Subquery | Basic | Operations |
| 25 | 低置信抽取事实(QA 复核) | Join + Filter | Basic | Analyst |
| 26 | 已授权付款金额 Top 10 Provider | Join + Aggregation | Intermediate | Finance |
| 27 | 按金属层级看会员自付比例 | Join + Aggregation | Intermediate | Finance |
| 28 | 申诉挽回金额(被推翻的拒绝) | CTE + Join | Advanced | Finance |
| 29 | 超 SLA 仍未决定的滞留请求 | Date + Subquery | Advanced | Operations |
| 30 | 拒绝原因 Pareto(累计 %) | Window + JSON | Advanced | Analyst |

---

## 3. 查询正文

### Query 1: 按状态查看每日 PA 请求量

**类别:** Aggregation + Date
**难度:** Basic
**业务角色:** Operations

**业务背景:**
运营团队每天上午 8 点跑这份报表来评估当天审核队列规模。请求量尖峰(周一早晨、长假之后)直接驱动当天的人力调度;状态构成则提示是否有足够案件出清,还是堆在 `pending` / `in_review`。状态构成持续偏移会上报给运营总监。

**解题思路:**
这题只碰 `pa_requests` 一张表,不需要 join。关键是聚合粒度:按"天 加 状态"两个维度分组,所以一行代表某一天某个状态的请求数。用 `DATE(submitted_at)` 把时间戳截断到日期 (去掉时分秒),再和 `status` 一起 GROUP BY。WHERE 用 `DATE('now', '-30 days')` 取最近 30 天的滚动窗口。最后按日期倒序、当天量倒序排,方便运营从最近的高峰看起。不需要 CTE 或窗口函数,一次 GROUP BY 就够。

**SQL:**
```sql
SELECT
    DATE(submitted_at)            AS submission_date,
    status,
    COUNT(*)                      AS request_count
FROM pa_requests
WHERE submitted_at >= DATE('now', '-30 days')
GROUP BY DATE(submitted_at), status
ORDER BY submission_date DESC, request_count DESC;
```

**预期结果:**
近 30 天的每日明细。状态值来自 `pa_requests.status` 枚举:`approved` / `denied` / `pended` / `appealed` / `withdrawn`(`pending` / `in_review` 较少,因为生成器对老旧请求做了抑制)。按每个状态每天 ~2 单计算,典型日子有 4–8 行。

---

### Query 2: 按金属层级查看批准率

**类别:** Join + Aggregation
**难度:** Basic
**业务角色:** Executive

**业务背景:**
按金属层级的批准率会进入 Meridian 季度产品评审。较低层级(Bronze)的医疗必要性把控通常比 Platinum 更严;任何一个层级如果批准率与其它层级相差超过 10 个百分点,就会被排查是政策标定偏差还是 provider 行为异常。

**解题思路:**
`metal_tier` 这个维度长在 `plans` 表上,而决定长在 `pa_decisions` 上,所以要顺着 `pa_decisions` → `pa_requests` → `members` → `plans` 一路 join 上去,四张表串起来。聚合粒度是每个金属层级一行。批准要把 `partial_approved` 也算进分子 (部分批准也是批了),所以用 `SUM(CASE WHEN decision IN ('approved','partial_approved') ...)` 这种条件求和。这里全部用 INNER JOIN 没问题,因为每条决定一定有对应的请求、会员和计划。

**SQL:**
```sql
SELECT
    pl.metal_tier,
    COUNT(*)                                                          AS total_decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)            AS denied,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(*), 2)          AS approval_rate_pct
FROM pa_decisions d
JOIN pa_requests  r  ON d.request_id = r.request_id
JOIN members      m  ON r.member_id  = m.member_id
JOIN plans        pl ON m.plan_id    = pl.plan_id
GROUP BY pl.metal_tier
ORDER BY approval_rate_pct DESC;
```

**预期结果:**
四行(Bronze / Silver / Gold / Platinum)。批准率按设计随层级倾斜:Bronze ~50%、Silver ~61%、Gold ~68%、Platinum ~84%。

---

### Query 3: 高频拒绝码 Top N(JSON 展开)

**类别:** Aggregation + JSON
**难度:** Intermediate
**业务角色:** Analyst

**业务背景:**
拒绝码(CARC/RARC)是拒绝背后的 **结构化** 原因 — 与自由文本的 `decision_reason_text` 不同,它能干净地聚类。拒绝管理分析师每月发布这份榜单:占拒绝量 >10% 的码会进入 provider 再培训或政策澄清候选清单。

**解题思路:**
`denial_codes_json` 是一个以 TEXT 存的 JSON 数组,一条拒绝可能带 1 到 2 个码。要按码统计就得先把数组展开成行,这正是 SQLite 的 `json_each` 用武之地:写 `FROM pa_decisions d, json_each(d.denial_codes_json) je` 做隐式交叉连接,数组里每个元素变成一行。WHERE 先排掉 `denial_codes_json IS NULL` 的非拒绝行,再限定 6 个月窗口。按 `je.value` (展开后的码) 分组计数。占比用 `SUM(COUNT(*)) OVER ()` 这个无分区窗口拿到总数当分母,省得再写一个子查询。

**SQL:**
```sql
SELECT
    je.value                                  AS denial_code,
    COUNT(*)                                  AS occurrences,
    ROUND(100.0 * COUNT(*) /
          SUM(COUNT(*)) OVER (), 2)           AS pct_of_total
FROM pa_decisions d, json_each(d.denial_codes_json) je
WHERE d.denial_codes_json IS NOT NULL
  AND d.decided_at >= DATE('now', '-6 months')
GROUP BY je.value
ORDER BY occurrences DESC;
```

**预期结果:**
~9 行(每个 CARC/RARC 码一行)。头部码(如 `N-130`)通常占拒绝码提及数的 ~15–18%;长尾每条 ~5–10%。

---

### Query 4: 按角色看审核员产能

**类别:** Join + Aggregation
**难度:** Basic
**业务角色:** Manager

**业务背景:**
医疗运营经理追踪各审核角色做出的决定数,以衡量自动化率。`auto_rule` 每个决定成本约 2 美元;`medical_director` 每个约 80 美元。医疗主任份额持续上升要么说明规则覆盖在收缩、要么说明案件复杂度在上升,两者都需处置。

**解题思路:**
`role` 长在 `reviewers` 表上,决定长在 `pa_decisions` 上,两表按 `reviewer_id` join。聚合粒度是每个角色一行。`COUNT(d.decision_id)` 数该角色做了多少决定,各角色占比同样用 `SUM(COUNT(...)) OVER ()` 这个窗口函数算 (一次扫描里既分组又算总)。这里用 INNER JOIN 即可,因为我们只关心在窗口期内真正做过决定的角色;若想把零产能的在职审核员也列出来则要换成 LEFT JOIN (Query 20 就是那种写法)。

**SQL:**
```sql
SELECT
    rv.role,
    COUNT(d.decision_id)                                              AS decisions,
    ROUND(100.0 * COUNT(d.decision_id) /
          SUM(COUNT(d.decision_id)) OVER (), 2)                       AS pct_of_total,
    ROUND(AVG(d.confidence_score), 3)                                 AS avg_confidence,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved_count,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct
FROM reviewers rv
JOIN pa_decisions d ON d.reviewer_id = rv.reviewer_id
WHERE d.decided_at >= DATE('now', '-90 days')
GROUP BY rv.role
ORDER BY decisions DESC;
```

**预期结果:**
四个角色。`clinical_reviewer` 与 `auto_rule` 占主导(~60% + ~30%)。`medical_director` 与 `external_reviewer` 体量较小但批准率最低 — 因为他们处理的是被升级上来的硬骨头。

---

### Query 5: 按紧急度看平均处理小时数

**类别:** Join + Aggregation + Date
**难度:** Intermediate
**业务角色:** Manager

**业务背景:**
处理时长 vs SLA 是头号运营指标。SLA 总监每周发布。任何一个紧急度层级平均时长超 SLA 窗口的 50% 都会触发流程评审。

**解题思路:**
处理时长已经物化在 `pa_decisions.tat_hours`,所以直接对它做 `AVG` / `MIN` / `MAX` 即可,不必每次现算 `JULIANDAY` 差,既快又不易错。三张表 join:`pa_requests` 提供 urgency,`pa_decisions` 提供 tat_hours,`sla_config` 提供该紧急度的 SLA 窗口做对照。聚合粒度是每个紧急度一行。排序上用 `CASE` 把 emergent / urgent / routine 排成业务上的轻重顺序,而不是字母序。

**SQL:**
```sql
-- 用 pa_decisions.tat_hours(物化的处理时长字段),省掉每次都算 JULIANDAY 差。
SELECT
    r.urgency,
    sla.sla_hours,
    COUNT(*)                  AS decided_requests,
    ROUND(AVG(d.tat_hours), 2) AS avg_hours_to_decide,
    ROUND(MIN(d.tat_hours), 2) AS min_hours,
    ROUND(MAX(d.tat_hours), 2) AS max_hours
FROM pa_requests   r
JOIN pa_decisions  d   ON d.request_id = r.request_id
JOIN sla_config    sla ON sla.urgency  = r.urgency
WHERE r.submitted_at >= DATE('now', '-90 days')
GROUP BY r.urgency, sla.sla_hours
ORDER BY
    CASE r.urgency
        WHEN 'emergent' THEN 1
        WHEN 'urgent'   THEN 2
        WHEN 'routine'  THEN 3
    END;
```

**预期结果:**
三行。`emergent` 平均接近 1 小时(SLA = 2);`urgent` 平均 30–50 小时(SLA = 72);`routine` 平均 100–200 小时(SLA = 336)。

---

### Query 6: 按紧急度看 SLA 违约率

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Operations

**业务背景:**
`emergent` 一次违约就可能直接耽误患者治疗;100 个 routine 违约 1 个属正常噪声。这份报表驱动运营升级,每天的 ops huddle 都会过一遍。

**解题思路:**
是否违约也已经物化成布尔列 `pa_decisions.sla_breached`,所以违约数就是 `SUM(CASE WHEN sla_breached ...)`,违约率再除以总决定数。表 join 和上一题一样 (requests 加 decisions 加 sla_config),粒度也是每个紧急度一行。把 `sla_hours` 一并选出来,是为了让读报表的人看到分母背后的时限标准。按违约率倒序排,最糟的紧急度排在最前。

**SQL:**
```sql
-- 用 pa_decisions.sla_breached(物化的违约标志)。
SELECT
    r.urgency,
    sla.sla_hours,
    COUNT(*)                                              AS total_decisions,
    SUM(CASE WHEN d.sla_breached THEN 1 ELSE 0 END)       AS breaches,
    ROUND(100.0 * SUM(CASE WHEN d.sla_breached THEN 1 ELSE 0 END)
                / COUNT(*), 2)                            AS breach_rate_pct
FROM pa_requests  r
JOIN pa_decisions d   ON d.request_id = r.request_id
JOIN sla_config   sla ON sla.urgency  = r.urgency
WHERE r.submitted_at >= DATE('now', '-90 days')
GROUP BY r.urgency, sla.sla_hours
ORDER BY breach_rate_pct DESC;
```

**预期结果:**
按设计生成器注入了 ~10% 的 breach 长尾。各紧急度的违约率应在 8–12% 之间。

---

### Query 7: Provider 批准率离群点

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Manager

**业务背景:**
Provider 网络经理识别两类离群:批准率异常低(文档差、超专科开方、欺诈嫌疑),以及批准率异常高(可能存在橡皮图章风险,值得审计)。两端都会被跟进。

**解题思路:**
从 `providers` 出发,join `pa_requests` 再 join `pa_decisions`,粒度是每个 provider 一行。这里有个关键的统计学坑:小样本上的比率不可信 (只做过 2 个决定的 provider 批准率不是 0% 就是 100%),所以用 `HAVING COUNT(d.decision_id) >= 5` 把低量 provider 滤掉,只看有统计意义的。按批准率升序排是为了把最低的离群点顶到最前;`LIMIT 20` 控制清单长度。要找异常高的另一端,把排序反过来即可。

**SQL:**
```sql
SELECT
    p.npi,
    p.provider_name,
    p.specialty,
    p.in_network,
    COUNT(d.decision_id)                                              AS total_decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct
FROM providers     p
JOIN pa_requests   r ON r.provider_npi = p.npi
JOIN pa_decisions  d ON d.request_id   = r.request_id
WHERE r.submitted_at >= DATE('now', '-180 days')
GROUP BY p.npi, p.provider_name, p.specialty, p.in_network
HAVING COUNT(d.decision_id) >= 5
ORDER BY approval_rate_pct ASC, total_decisions DESC
LIMIT 20;
```

**预期结果:**
近 180 天至少有 5 个决定的 20 家 provider。批准率最低的(常在 30–45%)被标记跟进;名单天然偏向网络外 provider 以及 Oncology / Pain Management 这类专科。

---

### Query 8: 网络内 vs 网络外批准率对比

**类别:** Join + Aggregation
**难度:** Basic
**业务角色:** Finance

**业务背景:**
财务追踪网络内 vs OON 的批准率差,以估算成本敞口:OON 批准会引发余额账单投诉和更高的 allowed 金额。差距 >15 个点就触发网络充分性评审。

**解题思路:**
和上一题的三表 join 一样 (providers 加 requests 加 decisions),但聚合粒度变成只按 `in_network` 这个布尔分组,所以结果就两行:网络内一行、网络外一行。条件求和算出各自的批准 / 拒绝数和批准率,再顺带把平均 confidence 选出来对比。布尔列在 SQLite 里实际是 0/1,所以可以直接 GROUP BY,按它倒序排让网络内 (1) 在上。

**SQL:**
```sql
SELECT
    p.in_network,
    COUNT(d.decision_id)                                              AS total_decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)            AS denied,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct,
    ROUND(AVG(d.confidence_score), 3)                                 AS avg_confidence
FROM providers     p
JOIN pa_requests   r ON r.provider_npi = p.npi
JOIN pa_decisions  d ON d.request_id   = r.request_id
WHERE r.submitted_at >= DATE('now', '-180 days')
GROUP BY p.in_network
ORDER BY p.in_network DESC;
```

**预期结果:**
两行。85% 的 provider 在网内,所以 in-network 行约占 85% 的决定数,并且批准率高于 OON 行。

---

### Query 9: PA → Claim 转化率(漏损分析)

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Finance

**业务背景:**
"PA 已批准但 claim 从未提交"即漏损:会员已获授权但未真的接受服务。一定漏损正常(排期延迟、会员改主意);持续高漏损意味着 pre-auth 疲劳或 provider 套利。CFO 把这个指标当作准备金高估的前瞻信号。

**解题思路:**
漏损的定义是"批了但没产生 claim",所以必须用 `LEFT JOIN claims`:从已批准的决定出发,左连理赔,没匹配上的就是漏损。这里把 INNER 换成 LEFT 是性命攸关的,因为我们恰恰要数那些没有 claim 的决定,用 INNER 会把它们全删掉、漏损永远算成 0。用 `COUNT(DISTINCT ...)` 防止一对多关系造成的重复计数。整个查询输出一行汇总:批准决定数、claim 数、转化率、漏损数。

**SQL:**
```sql
SELECT
    COUNT(DISTINCT d.decision_id)                                     AS approved_decisions,
    COUNT(DISTINCT c.claim_id)                                        AS claims_filed,
    ROUND(100.0 * COUNT(DISTINCT c.claim_id) /
                  COUNT(DISTINCT d.decision_id), 2)                   AS conversion_pct,
    COUNT(DISTINCT d.decision_id) - COUNT(DISTINCT c.decision_id)     AS leakage_count
FROM pa_decisions d
LEFT JOIN claims  c ON c.decision_id = d.decision_id
WHERE d.decision     IN ('approved', 'partial_approved')
  AND d.decided_at   >= DATE('now', '-180 days');
```

**预期结果:**
单行汇总。批准决定 ~300;claim ~180;转化率 ~60%;漏损 ~120 个决定。

---

### Query 10: 各层级申诉量

**类别:** Aggregation
**难度:** Basic
**业务角色:** Operations

**业务背景:**
申诉运营按层级估算案件负载:level-1 是内部复审,level-2 是医疗主任复审,external 是独立审查机构(IRO)。每个层级有不同的人手和 SLA 要求。

**解题思路:**
这题只查 `appeals` 一张表,不用 join。按 `level_number` 和 `appeal_level` 分组 (整数列负责正确排序,文本列负责好读),所以一行代表一个申诉层级。用条件求和分别数出 pending / upheld / overturned 三种结局的数量,一眼看清每层的在办与已结。WHERE 限定最近 180 天。按 `level_number` 升序排,从 L1 往外看漏斗逐层收窄。

**SQL:**
```sql
SELECT
    level_number,
    appeal_level,
    COUNT(*)                                                AS total_appeals,
    SUM(CASE WHEN outcome = 'pending'    THEN 1 ELSE 0 END) AS still_open,
    SUM(CASE WHEN outcome = 'upheld'     THEN 1 ELSE 0 END) AS upheld,
    SUM(CASE WHEN outcome = 'overturned' THEN 1 ELSE 0 END) AS overturned
FROM appeals
WHERE submitted_at >= DATE('now', '-180 days')
GROUP BY level_number, appeal_level
ORDER BY level_number;
```

**预期结果:**
三行,反映升级漏斗的形状。L1 占主导(~100 件),L2 ~25 件,external review ~10 件。`still_open` 列显示尚未结案的"in-flight"申诉 — 通常每层 ~5-10% — 由申诉团队每周分诊。

---

### Query 11: 各层级申诉推翻率

**类别:** Aggregation
**难度:** Basic
**业务角色:** Manager

**业务背景:**
推翻意味着原始拒绝判错。L1 推翻率高于外部审查 → 一审员需要培训;外部审查推翻率高 → 内部拒绝政策过严。

**解题思路:**
还是 `appeals` 单表。和上一题的区别是分母:推翻率只该在"已结案"的申诉里算,所以 WHERE 要先排掉 `outcome = 'pending'` 的在办案,否则未结案会把分母撑大、推翻率被低估。按层级分组,`overturn_rate = SUM(overturned) / COUNT(*)`。`overturned` 是个便捷布尔列,直接求和就是被推翻数。

**SQL:**
```sql
-- appeal_level(文本)与 level_number(整数)同时存,整数列天然可排序,文本列读起来直观。
SELECT
    level_number,
    appeal_level,
    COUNT(*)                                          AS resolved_appeals,
    SUM(CASE WHEN overturned THEN 1 ELSE 0 END)       AS overturned,
    ROUND(100.0 * SUM(CASE WHEN overturned THEN 1 ELSE 0 END)
                / COUNT(*), 2)                        AS overturn_rate_pct
FROM appeals
WHERE outcome <> 'pending'
GROUP BY level_number, appeal_level
ORDER BY level_number;
```

**预期结果:**
三行。生成数据上的推翻率近似:L1 ~35%、L2 ~25%、external ~18%。

---

### Query 12: 多级申诉漏斗

**类别:** CTE + Aggregation
**难度:** Advanced
**业务角色:** Analyst

**业务背景:**
分析师把"拒绝 → L1 → L2 → 外部"画成漏斗,算各步在拒绝总量中的占比。这帮助申诉团队做人力规划,也用来估算挽回金额的分布。

**解题思路:**
这题要把"一个拒绝对应最多三行申诉"压平成"一个拒绝一行"再算漏斗,所以用 CTE 分两步走。第一个 CTE `denials` 取出所有被拒决定;第二个 CTE `levels` 用 `LEFT JOIN appeals` 接上申诉,再用 `MAX(CASE WHEN level_number = N ...)` 把每个决定的多行申诉折叠成 has_l1 / has_l2 / has_ext 几个 0/1 标志,这一步避免了一对多 join 带来的重复计数。最外层对这些标志求和算各级转化率,`NULLIF(分母, 0)` 防止除零。LEFT JOIN 是必须的,否则提了拒绝却没人申诉的案子会被丢掉。结果是一行漏斗汇总。

**SQL:**
```sql
WITH denials AS (
    SELECT decision_id FROM pa_decisions WHERE decision = 'denied'
),
levels AS (
    SELECT
        d.decision_id,
        MAX(CASE WHEN a.level_number = 1       THEN 1 ELSE 0 END) AS has_l1,
        MAX(CASE WHEN a.level_number = 2       THEN 1 ELSE 0 END) AS has_l2,
        MAX(CASE WHEN a.is_external_review = 1 THEN 1 ELSE 0 END) AS has_ext,
        MAX(CASE WHEN a.overturned             THEN 1 ELSE 0 END) AS any_overturned
    FROM denials d
    LEFT JOIN appeals a ON a.decision_id = d.decision_id
    GROUP BY d.decision_id
)
SELECT
    COUNT(*)                                                          AS total_denials,
    SUM(has_l1)                                                       AS appealed_l1,
    SUM(has_l2)                                                       AS escalated_l2,
    SUM(has_ext)                                                      AS escalated_external,
    SUM(any_overturned)                                               AS ever_overturned,
    ROUND(100.0 * SUM(has_l1)         / COUNT(*), 2)                  AS l1_appeal_rate_pct,
    ROUND(100.0 * SUM(has_l2)         / NULLIF(SUM(has_l1), 0), 2)    AS l1_to_l2_escalation_pct,
    ROUND(100.0 * SUM(has_ext)        / NULLIF(SUM(has_l2), 0), 2)    AS l2_to_ext_escalation_pct,
    ROUND(100.0 * SUM(any_overturned) / COUNT(*), 2)                  AS overall_overturn_rate_pct
FROM levels;
```

**预期结果:**
单行汇总。~140 个拒绝里 ~60% 在 L1 提起申诉(`l1_appeal_rate_pct`),其中 ~25-30% 升级至 L2(`l1_to_l2_escalation_pct`;内部升级闸门以 50% 概率触发,但 ~35% 的 L1 被推翻、~5-10% 仍在 pending,两者都会结束链路),~25-35% 的 L2 抵达外部审查(`l2_to_ext_escalation_pct`)。总体推翻率 ~25%。

---

### Query 13: 按专科看拒绝热力图

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Analyst

**业务背景:**
拒绝集中在哪里?分析师按 provider 专科切分决定构成,识别某个专科(如 Pain Management、Oncology)是否在主导拒绝量。这驱动按专科的政策澄清和 provider 外联活动。

**解题思路:**
`specialty` 在 `providers` 上,决定在 `pa_decisions` 上,中间靠 `pa_requests` 串联,三表 join。粒度是每个专科一行,用条件求和把 approved / partial / denied / pended 摊成几列,做成一张"专科 × 决定类型"的热力图。同样用 `HAVING COUNT >= 10` 滤掉样本太小的专科,避免噪声。按拒绝率倒序排,把拒绝最集中的专科顶到前面。

**SQL:**
```sql
SELECT
    p.specialty,
    COUNT(d.decision_id)                                              AS total_decisions,
    SUM(CASE WHEN d.decision = 'approved'         THEN 1 ELSE 0 END)  AS approved,
    SUM(CASE WHEN d.decision = 'partial_approved' THEN 1 ELSE 0 END)  AS partial,
    SUM(CASE WHEN d.decision = 'denied'           THEN 1 ELSE 0 END)  AS denied,
    SUM(CASE WHEN d.decision = 'pended'           THEN 1 ELSE 0 END)  AS pended,
    ROUND(100.0 * SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)
                / COUNT(d.decision_id), 2)                            AS denial_rate_pct
FROM providers    p
JOIN pa_requests  r ON r.provider_npi = p.npi
JOIN pa_decisions d ON d.request_id   = r.request_id
GROUP BY p.specialty
HAVING COUNT(d.decision_id) >= 10
ORDER BY denial_rate_pct DESC;
```

**预期结果:**
最多 10 行,对应至少有 10 个决定的专科。拒绝率通常在 20–40% 之间。

---

### Query 14: 请求量 Top 10 操作编码

**类别:** Join + Aggregation
**难度:** Basic
**业务角色:** Operations

**业务背景:**
运营管理者想知道哪些操作编码主导着 PA 量 — 这份榜单决定哪些政策需要最硬核的自动化规则。出现在 >5% 请求里的码是高杠杆的自动化目标。

**解题思路:**
`request_clinical_items` 是请求和编码的关联表,要拿到编码的描述就 join `service_catalog`,注意这张表是复合主键,join 条件得同时带上 `service_code` 和 `code_type` 两列,缺一就会错配。用 `COUNT(DISTINCT i.request_id)` 而不是 `COUNT(*)`,因为同一个码在一条请求里可能挂多次,我们要数的是"多少条请求用了这个码"。WHERE 只留 CPT / HCPCS (操作和药品),排除 ICD 诊断码。分母用子查询 `(SELECT COUNT(*) FROM pa_requests)` 取请求总数,`LIMIT 10` 取榜单前十。

**SQL:**
```sql
SELECT
    sc.service_code,
    sc.code_type,
    sc.description,
    sc.category,
    COUNT(DISTINCT i.request_id)                                      AS request_count,
    ROUND(100.0 * COUNT(DISTINCT i.request_id) /
          (SELECT COUNT(*) FROM pa_requests), 2)                      AS pct_of_all_requests
FROM request_clinical_items i
JOIN service_catalog sc
     ON sc.service_code = i.service_code
    AND sc.code_type    = i.code_type
WHERE sc.code_type IN ('CPT', 'HCPCS')
GROUP BY sc.service_code, sc.code_type, sc.description, sc.category
ORDER BY request_count DESC
LIMIT 10;
```

**预期结果:**
按挂载请求数排序的 Top 10 操作编码。常见头部为高量码如 `27447`(全膝置换)与 `J1745`(英夫利昔单抗),各占所有请求的 ~3%。

---

### Query 15: 按决定看 confidence 分位数

**类别:** Window (NTILE)
**难度:** Intermediate
**业务角色:** Analyst

**业务背景:**
审核员为每个决定给一个 confidence 分。分析师检查"分位分布"是否与决定类型匹配 — 比如 `pended` 和 `escalated` 的分位应低于 `approved`。失配意味着 confidence 评分手册在漂移。

**解题思路:**
要看每种决定类型内部的 confidence 分位,得用窗口函数 `NTILE(4)`,关键是 `PARTITION BY decision`:这样四分位是在每种决定内部各自切的,而不是全表一刀切。先在 CTE `ranked` 里给每行打上 1 到 4 的分位号,再到外层用 `MAX(CASE WHEN quartile = k ...)` 把各分位的上界提取成 p25 / p50 / p75 几列 (这是 SQLite 没有原生 PERCENTILE 函数时的常用变通)。粒度是每种决定一行,按 p50 倒序排,直观看出哪种决定的把握更高。

**SQL:**
```sql
WITH ranked AS (
    SELECT
        decision,
        confidence_score,
        NTILE(4) OVER (PARTITION BY decision ORDER BY confidence_score) AS quartile
    FROM pa_decisions
    WHERE decided_at >= DATE('now', '-90 days')
)
SELECT
    decision,
    COUNT(*)                                                          AS decisions,
    ROUND(MAX(CASE WHEN quartile = 1 THEN confidence_score END), 3)   AS p25_max,
    ROUND(MAX(CASE WHEN quartile = 2 THEN confidence_score END), 3)   AS p50_max,
    ROUND(MAX(CASE WHEN quartile = 3 THEN confidence_score END), 3)   AS p75_max,
    ROUND(MAX(confidence_score), 3)                                   AS max_score
FROM ranked
GROUP BY decision
ORDER BY p50_max DESC;
```

**预期结果:**
五行。`approved` 的 p50 通常 ~0.90,`escalated` / `pended` ~0.65–0.75。

---

### Query 16: 月度 PA 量趋势 + 环比增长

**类别:** Window (LAG)
**难度:** Intermediate
**业务角色:** Executive

**业务背景:**
CEO 的月度董事会材料开篇就是月度 PA 量的环比。稳定的两位数 MoM 增长决定产能扩张节奏;某个月异常下滑(>15%)会触发市场份额复盘。

**解题思路:**
先在 CTE `monthly` 里用 `strftime('%Y-%m', submitted_at)` 把请求按月归并、数出每月量 (SQLite 没有 DATE_TRUNC,月份分桶就靠 strftime)。环比要拿到"上个月的量",这正是窗口函数 `LAG` 的活:`LAG(request_count) OVER (ORDER BY month)` 取前一行的值。MoM 增长 = (本月 减 上月) / 上月,分母用 `NULLIF(..., 0)` 防止第一个月没有前值时除零。粒度是每月一行,按月倒序展示。

**SQL:**
```sql
WITH monthly AS (
    SELECT
        strftime('%Y-%m', submitted_at)                AS month,
        COUNT(*)                                       AS request_count
    FROM pa_requests
    GROUP BY strftime('%Y-%m', submitted_at)
)
SELECT
    month,
    request_count,
    LAG(request_count) OVER (ORDER BY month)           AS prev_month,
    ROUND(100.0 *
          (request_count - LAG(request_count) OVER (ORDER BY month)) /
          NULLIF(LAG(request_count) OVER (ORDER BY month), 0), 2)     AS mom_growth_pct
FROM monthly
ORDER BY month DESC;
```

**预期结果:**
~12 个月度行。每月 ~50–70 单;在这种适中体量下 MoM 增长在 ±20% 之间波动。

---

### Query 17: 6 个月决定构成漂移

**类别:** CTE + Window
**难度:** Advanced
**业务角色:** Executive

**业务背景:**
CMO 关注 approved/denied/pended 构成是否随时间漂移。连续多季度拒绝份额上升提示政策收紧或 provider 行为变化;pended 份额下降说明审核员决定更果断。

**解题思路:**
这题分三步,用三个 CTE 串起来:`decided` 先把决定按月打标,`counts` 按"月 加 决定类型"计数,`month_totals` 再算每月总量。有了月度总量才能算每种决定占当月的份额。份额的环比变化要用 `LAG`,而且必须 `PARTITION BY decision`,这样每种决定各自和自己上个月比,不会串台。粒度是"月 × 决定类型",数据量是 6 个月乘最多 5 种决定。这种逐层加工的逻辑用 CTE 写比嵌套子查询清楚得多。

**SQL:**
```sql
WITH decided AS (
    SELECT
        strftime('%Y-%m', d.decided_at) AS month,
        d.decision
    FROM pa_decisions d
    WHERE d.decided_at >= DATE('now', '-6 months')
),
counts AS (
    SELECT month, decision, COUNT(*) AS n
    FROM decided GROUP BY month, decision
),
month_totals AS (
    SELECT month, SUM(n) AS total FROM counts GROUP BY month
)
SELECT
    c.month,
    c.decision,
    c.n,
    mt.total,
    ROUND(100.0 * c.n / mt.total, 2)                                  AS pct_of_month,
    ROUND(100.0 * c.n / mt.total
          - LAG(ROUND(100.0 * c.n / mt.total, 2))
                OVER (PARTITION BY c.decision ORDER BY c.month), 2)   AS mom_share_change_pct
FROM counts c
JOIN month_totals mt ON mt.month = c.month
ORDER BY c.month DESC, c.decision;
```

**预期结果:**
较长的表(6 个月 × 最多 5 种决定)。`pct_of_month` 应在长期均值附近(approved ~60%、denied ~25%);`mom_share_change_pct` 显示期间漂移的百分点。

---

### Query 18: 开放请求老化 + SLA 风险

**类别:** Date + Join
**难度:** Intermediate
**业务角色:** Operations

**业务背景:**
上午 9 点的 ops 站会用这份报表分诊卡住的请求。超过 SLA 50% 的列为"at risk",超过 100% 的列为"breach"。列表按最差靠前排,运营总监现场分派负责人。

**解题思路:**
这题盯的是还没决定的开放请求 (`status IN ('pending','in_review')`),它们还没有 `pa_decisions` 行,所以没有物化的 tat 可用,只能现算等待时长:`(JULIANDAY('now') - JULIANDAY(submitted_at)) * 24` 得到小时数。join `sla_config` 拿到该紧急度的 SLA 窗口,再用 `CASE` 把每条请求分到 ON_TRACK / AT_RISK (过半 SLA) / BREACH (超 SLA) 三档。join `providers` 是为了在分诊清单上显示 provider 名字。按等待时长倒序,最久的排最前。

**SQL:**
```sql
SELECT
    r.request_id,
    r.member_id,
    p.provider_name,
    r.urgency,
    sla.sla_hours,
    r.submitted_at,
    ROUND((JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0, 1)   AS hours_pending,
    CASE
        WHEN (JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0
                > sla.sla_hours              THEN 'BREACH'
        WHEN (JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0
                > sla.sla_hours * 0.5        THEN 'AT_RISK'
        ELSE 'ON_TRACK'
    END                                                               AS sla_status
FROM pa_requests r
JOIN providers   p   ON p.npi      = r.provider_npi
JOIN sla_config  sla ON sla.urgency = r.urgency
WHERE r.status IN ('pending', 'in_review')
ORDER BY hours_pending DESC;
```

**预期结果:**
~70 条当前开放请求(生成器预留了一个活跃队列:~50 routine / ~15 urgent / ~5 emergent)。其中大约 35–40 条 on-track,~25–30 条 at risk(过半 SLA),~5–10 条 breach。

---

### Query 19: 多次提请的会员(慢性病 cohort)

**类别:** Subquery
**难度:** Basic
**业务角色:** Analyst

**业务背景:**
一年内多次提交 PA 的会员往往是慢性病患者,适合纳入个案管理。临床运营分析师把这份名单交给个案管理团队主动招募。

**解题思路:**
"一年内提交 3 次以上"这个条件天然适合先做一个子查询:在子查询里按 `member_id` 分组、`HAVING COUNT(*) >= 3` 把高频会员筛出来,再把这个结果集 join 回 `members` 和 `plans` 补上姓名和层级。这种"先聚合筛选、再补维度"的两段式写法,比在主查询里又分组又 join 更清晰。粒度是每个会员一行,按申请次数倒序、`LIMIT 50` 取最活跃的一批。

**SQL:**
```sql
SELECT
    m.member_id,
    m.first_name || ' ' || m.last_name        AS member_name,
    pl.metal_tier,
    cnt.request_count
FROM (
    SELECT member_id, COUNT(*) AS request_count
    FROM pa_requests
    WHERE submitted_at >= DATE('now', '-365 days')
    GROUP BY member_id
    HAVING COUNT(*) >= 3
) cnt
JOIN members m  ON m.member_id = cnt.member_id
JOIN plans   pl ON pl.plan_id  = m.plan_id
ORDER BY cnt.request_count DESC, m.member_id
LIMIT 50;
```

**预期结果:**
约 50 名最近一年 ≥3 次申请的会员 — 即幂律分布浮现出的高用量 / 慢性 cohort。最活跃的成员可达 8–15 次申请。

---

### Query 20: 审核员工作量均衡

**类别:** CTE + Window (RANK)
**难度:** Advanced
**业务角色:** Manager

**业务背景:**
经理在每个角色内部按决定数排名,识别工作量过载(top 5 vs bottom 5)。长期失衡导致 burnout;auto-rule"审核员"也可以被排名,以评估哪个版本的规则覆盖了最多案件。

**解题思路:**
先在 CTE `per_reviewer` 里算出每个在职审核员的决定数和平均 confidence。这里有个容易踩的坑:日期过滤要写在 `LEFT JOIN ... ON` 的条件里,而不是 WHERE 里,否则 LEFT JOIN 会被 WHERE 退化成 INNER JOIN,那些窗口期内零产能的审核员就消失了,而我们恰恰想看到他们 (工作量为 0 也是信息)。外层用两个窗口函数:`RANK() OVER (PARTITION BY role ...)` 给同角色内排名,`PERCENT_RANK()` 给出相对位置。粒度是每个在职审核员一行。

**SQL:**
```sql
WITH per_reviewer AS (
    SELECT
        rv.reviewer_id,
        rv.reviewer_name,
        rv.role,
        COUNT(d.decision_id)                            AS decisions,
        ROUND(AVG(d.confidence_score), 3)               AS avg_conf
    FROM reviewers rv
    LEFT JOIN pa_decisions d
        ON d.reviewer_id = rv.reviewer_id
       AND d.decided_at  >= DATE('now', '-90 days')
    WHERE rv.active = 1
    GROUP BY rv.reviewer_id, rv.reviewer_name, rv.role
)
SELECT
    role,
    reviewer_id,
    reviewer_name,
    decisions,
    avg_conf,
    RANK()      OVER (PARTITION BY role ORDER BY decisions DESC) AS rank_in_role,
    PERCENT_RANK() OVER (PARTITION BY role ORDER BY decisions)   AS pct_rank_in_role
FROM per_reviewer
ORDER BY role, decisions DESC;
```

**预期结果:**
~28 行(每个在职审核员一行)。在 `clinical_reviewer` 角色里,头部审核员可能处理 40+ 决定,而尾部 <10 — 是工作量再平衡的素材。

---

### Query 21: 按类别看政策被引用率

**类别:** Join + JSON
**难度:** Intermediate
**业务角色:** Analyst

**业务背景:**
当一条决定行的 `applied_policy_id` 指向某政策时,该政策视为"被引用"。按临床类别追踪引用率可暴露空洞:如果 `behavioral_health` 类决定从未匹配到任何政策,要么政策库缺覆盖、要么匹配逻辑坏掉。

**解题思路:**
要回答"哪些类别的政策没被用到",必须用 `LEFT JOIN`:从 `payer_policies` 出发左连 `pa_decisions`,这样从未被任何决定引用的政策类别也会留在结果里 (引用数为 0),正是这种空洞才是要找的。直接用 `payer_policies.category` 列分组,不必再脆弱地解析 `policy_id` 字符串。`json_array_length(cpt_codes_json)` 顺带统计每类政策覆盖了多少操作码槽位。粒度是每个临床类别一行,按被引用数倒序。

**SQL:**
```sql
-- 直接用 payer_policies.category(不再脆弱地解析 policy_id)。
SELECT
    pp.category,
    COUNT(DISTINCT pp.policy_id)                          AS policies_in_catalog,
    SUM(json_array_length(pp.cpt_codes_json))             AS covered_procedure_slots,
    COUNT(d.decision_id)                                  AS decisions_applied
FROM payer_policies pp
LEFT JOIN pa_decisions d ON d.applied_policy_id = pp.policy_id
GROUP BY pp.category
ORDER BY decisions_applied DESC;
```

**预期结果:**
每个类别一行。`orthopedic` 与 `cardiac` 通常在 `decisions_applied` 上占主导,因为目录里 CPT 偏这两类。

---

### Query 22: 保障即将到期的会员

**类别:** Date + Join
**难度:** Intermediate
**业务角色:** Operations

**业务背景:**
保障在 60 天内到期且有未决 PA 请求的会员高度危险 — 一旦保障过期请求就会因不合规被拒。会员服务部主动外联续保或延期。这份名单每周五交给留存团队。

**解题思路:**
主表是 `members`,join `plans` 拿层级,再 `LEFT JOIN pa_requests` 接上未决请求。注意"只算 pending / in_review"这个条件要写进 LEFT JOIN 的 ON 里,这样即便会员没有任何未决请求也仍然出现在名单上 (open_requests 计 0),不会被筛掉。WHERE 用 `plan_end_date BETWEEN DATE('now') AND DATE('now','+60 days')` 圈出 60 天内到期的会员。粒度是每个会员一行,按到期日和未决请求数排序,留存团队优先处理最紧迫的。

**SQL:**
```sql
SELECT
    m.member_id,
    m.first_name || ' ' || m.last_name                                AS member_name,
    pl.metal_tier,
    m.plan_end_date,
    CAST(JULIANDAY(m.plan_end_date) - JULIANDAY('now') AS INTEGER)    AS days_until_end,
    COUNT(r.request_id)                                               AS open_requests
FROM members m
JOIN plans   pl ON pl.plan_id   = m.plan_id
LEFT JOIN pa_requests r
       ON r.member_id = m.member_id
      AND r.status IN ('pending', 'in_review')
WHERE m.plan_end_date BETWEEN DATE('now') AND DATE('now', '+60 days')
GROUP BY m.member_id, m.first_name, m.last_name, pl.metal_tier, m.plan_end_date
ORDER BY m.plan_end_date, open_requests DESC;
```

**预期结果:**
几位 60 天内到期的会员。留存团队优先处理有未决请求的会员。

---

### Query 23: 自动规则 vs 人工决定结果

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Executive

**业务背景:**
COO 季度上汇报自动化效果。预期画面:自动规则引擎吃掉大量"无脑批准",人工处理硬骨头(denied / pended)。一旦自动化份额跌到 30% 以下就触发投资评审。

**解题思路:**
关键技巧是用 `CASE WHEN rv.role = 'auto_rule' THEN 'automated' ELSE 'human' END` 把四个审核角色二分成"自动"和"人工"两组,然后既在 SELECT 里用它、也在 GROUP BY 里用它 (SQLite 允许按表达式分组)。`pa_decisions` join `reviewers` 取角色。条件求和把两组的批准 / 拒绝 / 挂起摊开对比,验证"自动吃简单、人工啃硬骨头"的预期画面。结果就两行。

**SQL:**
```sql
SELECT
    CASE WHEN rv.role = 'auto_rule' THEN 'automated' ELSE 'human' END AS reviewer_group,
    COUNT(d.decision_id)                                              AS decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)            AS denied,
    SUM(CASE WHEN d.decision IN ('pended', 'escalated')
             THEN 1 ELSE 0 END)                                       AS pended_or_escalated,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct,
    ROUND(AVG(d.confidence_score), 3)                                 AS avg_confidence
FROM pa_decisions d
JOIN reviewers    rv ON rv.reviewer_id = d.reviewer_id
GROUP BY CASE WHEN rv.role = 'auto_rule' THEN 'automated' ELSE 'human' END
ORDER BY decisions DESC;
```

**预期结果:**
两行。`automated` 承担 30–40% 的决定且偏批准;`human` 组处理更硬的案件构成。

---

### Query 24: 临床笔记类型分布

**类别:** Aggregation + Subquery
**难度:** Basic
**业务角色:** Operations

**业务背景:**
运营检查文档习惯,识别在 PA 提交时缺关键支撑文档的 provider。如果 `physician_letter` 出现率 <90%,说明 provider 在跳过最关键的文档类型。

**解题思路:**
主体是 `clinical_notes` 按 `note_type` 分组。这里要区分两个计数:`COUNT(*)` 是笔记总条数 (一条请求可能有多条同类型笔记),`COUNT(DISTINCT request_id)` 才是"有多少条请求带了这种笔记",出现率要用后者。分母是请求总数,用子查询 `(SELECT COUNT(*) FROM pa_requests)` 取。粒度是每种笔记类型一行,按笔记数倒序。

**SQL:**
```sql
SELECT
    note_type,
    COUNT(*)                                                          AS note_count,
    COUNT(DISTINCT request_id)                                        AS requests_with_type,
    ROUND(100.0 * COUNT(DISTINCT request_id) /
          (SELECT COUNT(*) FROM pa_requests), 2)                      AS pct_of_requests
FROM clinical_notes
GROUP BY note_type
ORDER BY note_count DESC;
```

**预期结果:**
五行(每种笔记类型一行)。`physician_letter` 出现在最多的请求里;`referral` 通常最少。

---

### Query 25: 低置信抽取事实(QA 复核)

**类别:** Join + Filter
**难度:** Basic
**业务角色:** Analyst

**业务背景:**
QA 分析师抽查 confidence < 0.80 的事实抽取,以校准抽取规则手册并识别文档质量问题。每周三过一遍。

**解题思路:**
这是一道过滤型查询,不做聚合。`extracted_clinical_facts` join `pa_requests` 是为了在抽查清单上带出每条事实所属请求的紧急度和状态,方便 QA 判断优先级。两个过滤条件:`confidence < 0.80` 锁定低置信事实,`extracted_at >= DATE('now','-30 days')` 限定最近一个月。按 confidence 升序排,最不靠谱的排最前,`LIMIT 50` 控制抽查量。

**SQL:**
```sql
SELECT
    ecf.fact_id,
    ecf.request_id,
    ecf.fact_category,
    ecf.fact_key,
    ecf.fact_value,
    ROUND(ecf.confidence, 3)                                          AS confidence,
    r.urgency,
    r.status
FROM extracted_clinical_facts ecf
JOIN pa_requests              r ON r.request_id = ecf.request_id
WHERE ecf.confidence < 0.80
  AND ecf.extracted_at >= DATE('now', '-30 days')
ORDER BY ecf.confidence ASC, ecf.extracted_at DESC
LIMIT 50;
```

**预期结果:**
最多 50 条低置信事实。大多落在 `prior_treatment` 或 `contraindication` 类别,因为自由文本文档在这两类最模糊。

---

### Query 26: 已授权付款金额 Top 10 Provider

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Finance

**业务背景:**
财务关注实际 *付款* 金额(而非单纯请求量)最大的 provider。Top 10 通常拿走 ~40% 的付款,作为战略客户管理。任何 Top 10 provider 月度付款双位数下滑都是流失信号。

**解题思路:**
这题要追的是真金白银,所以链路最长:`providers` → `pa_requests` → `pa_decisions` → `claims` 四张表串起来,只有这样才能把付款金额归到 provider 头上。`WHERE claim_status = 'paid'` 只算真付出去的钱。按 provider 分组,`SUM(paid_amount_usd)` 是核心指标,顺带算实付占计费比 (`paid / billed`) 看折扣力度。`COUNT(DISTINCT claim_id)` 防止 join 造成的重复计数。按总付款倒序、`LIMIT 10` 取大客户。

**SQL:**
```sql
SELECT
    p.npi,
    p.provider_name,
    p.specialty,
    COUNT(DISTINCT c.claim_id)                                        AS claims,
    ROUND(SUM(c.paid_amount_usd), 2)                                  AS total_paid_usd,
    ROUND(SUM(c.billed_amount_usd), 2)                                AS total_billed_usd,
    ROUND(SUM(c.paid_amount_usd) /
          NULLIF(SUM(c.billed_amount_usd), 0) * 100.0, 2)             AS paid_pct_of_billed
FROM providers     p
JOIN pa_requests   r ON r.provider_npi = p.npi
JOIN pa_decisions  d ON d.request_id   = r.request_id
JOIN claims        c ON c.decision_id  = d.decision_id
WHERE c.claim_status = 'paid'
GROUP BY p.npi, p.provider_name, p.specialty
ORDER BY total_paid_usd DESC
LIMIT 10;
```

**预期结果:**
付款总额最大的 10 家 provider。头部通常是医院或手术中心 — 单 claim 金额更大。

---

### Query 27: 按金属层级看会员自付比例

**类别:** Join + Aggregation
**难度:** Intermediate
**业务角色:** Finance

**业务背景:**
Bronze 会员相对 allowed 金额承担最大自付份额,Platinum 最小。财务核对精算设计在 claim 落地后是否成立。如果出现 Gold 会员自付与 Silver 一样,提示福利配置 bug 或异常使用模式。

**解题思路:**
从 `claims` 出发 join `members` 再 join `plans` 拿到金属层级。`WHERE claim_status = 'paid'` 只看已结清的理赔。按层级分组,核心指标 `member_share_pct = SUM(member_responsibility_usd) / SUM(allowed_amount_usd)`。注意要先各自求和再相除 (汇总层面的比率),而不是对每条 claim 的比率取平均,后者会被小额 claim 带偏。粒度是每个层级一行,按自付占比倒序,Bronze 应在最上、Platinum 在最下。

**SQL:**
```sql
SELECT
    pl.metal_tier,
    COUNT(c.claim_id)                                                 AS claims,
    ROUND(SUM(c.allowed_amount_usd), 2)                               AS total_allowed,
    ROUND(SUM(c.paid_amount_usd), 2)                                  AS plan_paid,
    ROUND(SUM(c.member_responsibility_usd), 2)                        AS member_share,
    ROUND(100.0 * SUM(c.member_responsibility_usd) /
                  NULLIF(SUM(c.allowed_amount_usd), 0), 2)            AS member_share_pct_of_allowed
FROM claims c
JOIN members m  ON m.member_id = c.member_id
JOIN plans   pl ON pl.plan_id  = m.plan_id
WHERE c.claim_status = 'paid'
GROUP BY pl.metal_tier
ORDER BY member_share_pct_of_allowed DESC;
```

**预期结果:**
四行。Bronze 会员 `member_share_pct` 最高(~30%);Platinum 最低(~13%);Silver ~24%;Gold ~17%。

---

### Query 28: 申诉挽回金额(被推翻的拒绝)

**类别:** CTE + Join
**难度:** Advanced
**业务角色:** Finance

**业务背景:**
当一个拒绝被推翻,会员 / provider 最终拿到了原本被挡住的治疗。财务通过累加这些 CPT 的预期 billed 金额来估算"挽回金额"。这个数字量化了首审错误的运营成本,是申诉职能的头号指标。

**解题思路:**
分两个 CTE 走。第一个 `overturned` 用 `DISTINCT decision_id` 取出所有被推翻的拒绝 (DISTINCT 是因为一个决定可能在多个层级都被记了推翻,去重才不会重复计算)。第二个 `overturned_items` 把这些决定连回 `request_clinical_items`,只留 CPT / HCPCS 操作行项。最外层 join `service_catalog` 用复合键 (service_code 加 code_type) 取每个码的 `avg_billed_amount_usd`,求和就是预期挽回金额。结果是一行汇总:被推翻拒绝数、行项数、挽回总额、单行项均值。

**SQL:**
```sql
WITH overturned AS (
    SELECT DISTINCT a.decision_id
    FROM appeals a
    WHERE a.overturned = 1
),
overturned_items AS (
    SELECT
        o.decision_id,
        i.service_code,
        i.code_type
    FROM overturned o
    JOIN pa_decisions d ON d.decision_id = o.decision_id
    JOIN request_clinical_items i ON i.request_id = d.request_id
    WHERE i.code_type IN ('CPT', 'HCPCS')
)
SELECT
    COUNT(DISTINCT oi.decision_id)                                    AS overturned_denials,
    COUNT(*)                                                          AS line_items,
    ROUND(SUM(sc.avg_billed_amount_usd), 2)                           AS estimated_recovery_billed_usd,
    ROUND(AVG(sc.avg_billed_amount_usd), 2)                           AS avg_line_item_value_usd
FROM overturned_items oi
JOIN service_catalog sc
     ON sc.service_code = oi.service_code
    AND sc.code_type    = oi.code_type;
```

**预期结果:**
单行汇总。~20–30 个被推翻的拒绝,带来数十万美元量级的挽回金额(取决于 CPT 构成)。

---

### Query 29: 超 SLA 仍未决定的滞留请求

**类别:** Date + Subquery
**难度:** Advanced
**业务角色:** Operations

**业务背景:**
这是最糟糕的运营情况:开放请求(`pending` 或 `in_review` 状态)的 hours-pending 已经超过其紧急度对应的 SLA。生成器在活跃队列里注入了 ~10% 的"stalled"尾巴,所以这份报表通常返回 5–10 条 — 每一条都是合规风险敞口,会被升级到医疗主任并开 CAPA 工单。

(说明:对 *已决定* 请求的违约,已经物化到 `pa_decisions.sla_breached`。本查询处理的是尚未决定的正交场景,因此直接计算 hours-pending。)

**解题思路:**
这题和 Query 18 同源,但只保留最坏的一档:开放请求里等待时长已经超过自身 SLA 的。因为请求尚未决定、没有物化 tat,所以等待时长现算 `(JULIANDAY('now') - JULIANDAY(submitted_at)) * 24`,并把它和 `sla_config.sla_hours` 比较放进 WHERE 做硬过滤。多算一列 `hours_over_sla` (超了多少小时) 用于排序。用一个相关子查询 `(SELECT COUNT(*) FROM clinical_notes ...)` 顺带带出每条请求的笔记数,帮分诊判断材料是否齐。按超 SLA 时长倒序,最严重的排最前。

**SQL:**
```sql
SELECT
    r.request_id,
    r.member_id,
    p.provider_name,
    p.specialty,
    r.urgency,
    sla.sla_hours,
    r.submitted_at,
    ROUND((JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0, 1)   AS hours_pending,
    ROUND((JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0
          - sla.sla_hours, 1)                                         AS hours_over_sla,
    (SELECT COUNT(*) FROM clinical_notes cn
       WHERE cn.request_id = r.request_id)                            AS note_count
FROM pa_requests r
JOIN providers   p   ON p.npi      = r.provider_npi
JOIN sla_config  sla ON sla.urgency = r.urgency
WHERE r.status IN ('pending', 'in_review')
  AND (JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0 > sla.sla_hours
ORDER BY hours_over_sla DESC;
```

**预期结果:**
通常 5–10 条滞留请求,按超 SLA 的时长降序排列。构成偏 `routine`(基数最大),榜单顶端可能出现少数 `emergent` — 每个 `emergent` 都是最高优先级,因为它的 SLA 只有 2 小时。

---

### Query 30: 拒绝原因 Pareto(累计 %)

**类别:** Window + JSON
**难度:** Advanced
**业务角色:** Analyst

**业务背景:**
帕累托原则说 ~80% 的拒绝由 ~20% 的拒绝码解释。分析师确认这一点,并识别"vital few"码作为 provider 再培训的目标。累计百分比告诉团队"80% 线"落在哪里。

**解题思路:**
帕累托图的核心是"累计百分比",得用带排序的运行总和窗口函数。第一个 CTE `denial_counts` 先用 `json_each` 展开 `denial_codes_json` 并按码计数。第二个 CTE `ranked` 里:`pct_of_total` 用无分区窗口 `SUM(occurrences) OVER ()` 当分母;累计占比用 `SUM(occurrences) OVER (ORDER BY occurrences DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`,这个有序的运行总和就是帕累托曲线;`ROW_NUMBER()` 给出排名。最外层用 `CASE WHEN cumulative_pct <= 80 THEN 'vital_few' ELSE 'trivial_many'` 划出关键少数和琐碎多数。粒度是每个拒绝码一行,按排名升序。

**SQL:**
```sql
WITH denial_counts AS (
    SELECT
        je.value                                       AS denial_code,
        COUNT(*)                                       AS occurrences
    FROM pa_decisions d, json_each(d.denial_codes_json) je
    WHERE d.denial_codes_json IS NOT NULL
    GROUP BY je.value
),
ranked AS (
    SELECT
        denial_code,
        occurrences,
        ROUND(100.0 * occurrences /
              SUM(occurrences) OVER (), 2)             AS pct_of_total,
        ROUND(100.0 *
              SUM(occurrences) OVER (ORDER BY occurrences DESC
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / SUM(occurrences) OVER (), 2)           AS cumulative_pct,
        ROW_NUMBER() OVER (ORDER BY occurrences DESC)  AS rank
    FROM denial_counts
)
SELECT
    rank,
    denial_code,
    occurrences,
    pct_of_total,
    cumulative_pct,
    CASE WHEN cumulative_pct <= 80.0 THEN 'vital_few'
         ELSE 'trivial_many' END                       AS pareto_class
FROM ranked
ORDER BY rank;
```

**预期结果:**
9 行(每个 CARC/RARC 码一行)。拒绝码权重按设计成 Pareto 形:`N-130`(~30%)与 `CO-50`(~21%)合占所有拒绝码提及的 ~50%;头 4 个码累计达到 ~80%;余下 5 个是长尾。

---

## 4. 查询覆盖度总结

### 按类别

| 类别 | Query 编号 | 数量 | % |
|---|---|---|---|
| Aggregation(含 Date 变体) | 1, 10, 11, 24 | 4 | 13% |
| Join + Aggregation | 2, 4, 5, 6, 7, 8, 9, 13, 14, 22, 23, 26, 27 | 13 | 43% |
| Window function | 15, 16, 17, 20, 30 | 5 | 17% |
| CTE | 12, 17, 20, 28 | 4 | 13% |
| Subquery | 19, 29 | 2 | 7% |
| JSON unnest | 3, 21, 30 | 3 | 10% |
| Date analysis | 1, 5, 6, 16, 17, 18, 22, 29 | 8 | 27% |

*(部分查询跨多个类别,所以加总超过 30。)*

### 按难度

| 难度 | Query 编号 | 数量 | % |
|---|---|---|---|
| Basic        | 1, 2, 4, 8, 10, 11, 14, 19, 24, 25 | 10 | 33% |
| Intermediate | 3, 5, 6, 7, 9, 13, 15, 16, 18, 21, 22, 23, 26, 27 | 14 | 47% |
| Advanced     | 12, 17, 20, 28, 29, 30 | 6 | 20% |

### 按业务角色

| 角色 | Query 编号 | 数量 | % |
|---|---|---|---|
| Executive  | 2, 16, 17, 23 | 4 | 13% |
| Manager    | 4, 5, 7, 11, 20 | 5 | 17% |
| Analyst    | 3, 12, 13, 15, 19, 21, 25, 30 | 8 | 27% |
| Operations | 1, 6, 10, 14, 18, 22, 24, 29 | 8 | 27% |
| Finance    | 8, 9, 26, 27, 28 | 5 | 17% |

### 按业务问题

每个查询都追溯回 `01-..._business_context-cn.md` 第 5 节列出的业务问题。下表给出映射。

| 业务问题 | 对应查询 |
|---|---|
| 问题一:处理时限与产能 (SLA、开放队列) | 1, 5, 6, 18, 22, 29 |
| 问题二:批准与拒绝是否公平合理 | 2, 7, 8, 13 |
| 问题三:拒绝原因的集中度 | 3, 30 |
| 问题四:授权到理赔的漏损 | 9, 26, 27 |
| 问题五:申诉流程与推翻率 | 10, 11, 12, 28 |
| 问题六:自动化效果 | 4, 20, 23 |
| 运营 / 质量支撑类 (无单一对应问题) | 14, 15, 16, 17, 19, 21, 24, 25 |

---

**SQL 查询文档完**
