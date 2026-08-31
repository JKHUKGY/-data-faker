# 金融科技 消费信用卡全生命周期 SQL 查询集

本文档配套 `fintech_credit_card_lifecycle_high` 数据集. 读它之前, 请先读业务背景 `01-fintech_credit_card_lifecycle_high_business_context-cn.md` 和数据结构 `02-fintech_credit_card_lifecycle_high_er_document-cn.md`. 如果你对某个分析背后的"为什么这么算"还不清楚, 去看配套的分析入门读本 `05-fintech_credit_card_lifecycle_high_analytics_primer-cn.md`.

---

## 1. 关于 REFERENCE_DATE

整个数据集锚定在固定参考日 `REFERENCE_DATE = 2026-06-30`. 所有需要"今天 / 当前"语义的查询, 都用这个字面量日期 `'2026-06-30'`, 而不是 `DATE('now')`. 这样无论哪天跑, 结果都一样, 方便对答案. 账龄 (months_on_book), 是否到期这类概念也都以这一天为基准.

---

## 2. 如何使用本文档

这份文档是写给一个刚入职 Keystone Card 的分析师看的 (可能是 Business Analyst, 也可能是 Data Scientist). 你的经理把这 20 道查询丢给你, 说"这周把它们过一遍". 每道查询都有五段固定结构:

1. **业务背景**: 谁在问, 为什么现在问, 答案要拿去做什么决策.
2. **标签**: SQL 类别, 难度, 业务角色.
3. **解题思路**: 在你看到 SQL 之前, 先讲清楚该怎么下手, 用哪些表, 为什么这么连.
4. **SQL 代码**: 可以直接在 SQLite 上跑.
5. **预期结果与业务结论**: 结果长什么样, 关键数字是多少, 拿到后该做什么.

每道查询都能追溯到业务背景文档里的某个业务问题. 文档末尾有一张映射表. SQL 是用来读懂和学习的, 不只是拿来跑的. 特别留意那些注释, 它们解释了为什么这里用 LEFT JOIN 而不是 INNER JOIN, 为什么要用 NTILE, 为什么按这个列分组.

---

## 3. 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| Q1 | 获客漏斗转化 | VP of Acquisitions | 聚合 | 基础 |
| Q2 | 响应模型分层校验 | Head of Card Intelligence | 窗口函数 | 中等 |
| Q3 | 承保分整体区分度 | Head of Card Intelligence | 窗口 + CASE | 中等 |
| Q4 | 承保分在 Subprime 段失效 | Data Scientist | 窗口 + Join + 过滤 | 进阶 |
| Q5 | 各风险等级批准率与 booked FICO | VP of Underwriting | 聚合 + Join | 基础 |
| Q6 | 渠道逆向选择 | CMO | 聚合 + Join | 中等 |
| Q7 | 渠道损失调整后的真实获客价值 | CMO | 多 CTE + LEFT JOIN | 进阶 |
| Q8 | 组合利用率分布 | VP of Portfolio Management | CTE + 窗口 | 中等 |
| Q9 | 提额 (CLI) 逆向选择 | Chief Credit Officer | Join + CASE | 中等 |
| Q10 | 逾期桶分布 (roll 快照) | Collections Manager | CTE + 聚合 | 基础 |
| Q11 | 产品阶梯完整 P&L | CFO | 多 CTE + Join | 进阶 |
| Q12 | Transactor vs Revolver 单账户贡献 | Product Manager | CTE + Join | 中等 |
| Q13 | Promo APR 悬崖 | Data Scientist | 条件聚合 + 时序 | 进阶 |
| Q14 | interchange 按 MCC 拆解 | CFO | Join + 聚合 | 基础 |
| Q15 | Bonus churner 负 LTV | VP of Acquisitions | CTE + Join | 中等 |
| Q16 | Vintage 损失曲线 | Chief Risk Officer | 日期 + 条件聚合 | 中等 |
| Q17 | 承保标准随时间漂移 | Chief Risk Officer | 日期函数 | 中等 |
| Q18 | Champion vs Challenger 表现 | CMO | Join + 聚合 | 基础 |
| Q19 | rewards 侵蚀 interchange | CFO | CTE + Join | 中等 |
| Q20 | 月度新开卡趋势 | Data Analyst | 日期 + 聚合 | 基础 |

---

## 4. 查询

### Q1. 获客漏斗转化

**业务背景.** VP of Acquisitions 每个月要向管理层汇报获客漏斗的健康度. 一张卡从"寄出预筛信"到"真正激活开卡"要穿过好几道关: 寄信 (prescreen) 到有人回应, 回应到正式申请, 申请到承保批准, 批准到激活. 每一道关都在漏客户. 她需要一眼看到每一层的转化率, 判断是营销触达不行, 还是承保卡太紧, 还是激活环节掉链子. 这道题对应业务问题 Q_funnel.

**标签.** 聚合 | 基础 | VP of Acquisitions.

**解题思路.** 这里其实是**两个相互独立的漏斗**, 不是一条链, 这一点必须先讲清楚. 第一个是**预筛响应漏斗**: 寄信 (`prescreen_offer`) 到有人回应. 第二个是**申请转化漏斗**: 提交申请 (`application`) 到承保批准到激活开卡 (`account`). 两者住在不同的表, 之间没有外键直连: 申请端的人既有预筛响应者, 也有自然流量和网点转介, 所以**不能**把"回应数"当成"申请数"的上游 (回应 1,000 出头, 申请却有 1.8 万, 二者不在一条链上). 做法是分别在每张表里算出各层的绝对数, 用几个单行 CTE 交叉连接拼成一行来并排展示. 批准率 = 批准数 / 申请数, 激活率 = 开卡数 / 批准数; 响应率单独算 = 回应数 / 寄信数.

```sql
WITH pres AS (
    SELECT COUNT(*) AS mailed, SUM(responded) AS responded
    FROM prescreen_offer
),
app AS (
    SELECT COUNT(*) AS apps,
           SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) AS approved
    FROM application
),
acct AS (
    SELECT COUNT(*) AS booked FROM account
)
SELECT pres.mailed,
       pres.responded,
       app.apps,
       app.approved,
       acct.booked,
       ROUND(100.0 * app.approved / app.apps, 1) AS approval_rate,
       ROUND(100.0 * acct.booked / app.approved, 1) AS activation_rate
FROM pres, app, acct;
```

**预期结果与业务结论.** 一行, 读成两个独立漏斗. 预筛响应漏斗: 约 20,000 封预筛信只有约 1,040 人回应 (响应率约 5%). 申请转化漏斗: 申请端约 18,000 份 (含预筛响应者, 自然流量和网点转介), 批准约 10,400 份 (批准率约 58%), 最终激活约 8,900 个账户 (激活率约 86%). 结论: 承保批准率和激活率都算健康; 真正窄的一环是营销触达端的 5% 响应率. 下一步是把预算往响应率更高的渠道倾斜, 这正好接 Q2 (响应模型) 和 Q6 (渠道质量).

---

### Q2. 响应模型分层校验

**业务背景.** Head of Card Intelligence (数据科学负责人) 要验收营销团队用的"响应模型". 这个模型给每个预筛名单上的人打一个 0 到 999 的分, 预测他会不会回应邮件. 如果模型有用, 那么分数越高的人实际回应率就该越高. 数据科学家要把预测分数和真实结局 (`responded`) 摆在一起, 看模型有没有区分度. 这是最基础的模型评估, 也是画 ROC 曲线, 算 AUC 的前一步. 这道题对应业务问题 Q_responsemodel.

**标签.** 窗口函数 | 中等 | Head of Card Intelligence.

**解题思路.** "分数越高回应率越高吗"这类问题的标准打法是**按分数分箱, 逐箱看真实率**. 用窗口函数 `NTILE(10)` 按 `response_model_score` 把人群切成 10 个等大的十分位 (decile), 第 1 层是分最低的 10%, 第 10 层是分最高的 10%. 然后每层算真实响应率. 注意 SQLite 不允许直接在 `GROUP BY` 里引用窗口函数的别名, 所以要先在一个 CTE 里把 decile 算出来, 外层再按它分组. 如果响应率随 decile 单调上升, 模型就是有区分度的.

```sql
WITH scored AS (
    SELECT response_model_score,
           responded,
           NTILE(10) OVER (ORDER BY response_model_score) AS decile
    FROM prescreen_offer
)
SELECT decile,
       COUNT(*) AS n,
       ROUND(AVG(response_model_score), 0) AS avg_score,
       ROUND(100.0 * SUM(responded) / COUNT(*), 2) AS actual_response_rate
FROM scored
GROUP BY decile
ORDER BY decile;
```

**预期结果与业务结论.** 10 行, 响应率从第 1 层的约 2.0% 单调爬升到第 10 层的约 8.7%, 高分层是低分层的约 4 倍. 结论: 响应模型有效, 区分度良好. 建议营销把预筛预算集中投放到模型高分段 (decile 8 到 10), 低分段减少投放. 这就是 Capital One 式"个性化每一张 offer"的雏形.

---

### Q3. 承保分整体区分度

**业务背景.** 同样是 Head of Card Intelligence, 但这次看的是承保侧的"风险模型". 每份申请在承保时会拿到一个 `underwriting_score` (0 到 999, 越高代表模型认为越安全). 如果模型好用, 那么账户开出去以后, 分数越高的账户实际核销 (charge-off) 率就该越低. 季度模型监控会先看整体区分度. 这道题对应业务问题 Q_underwriting (承保模型校准).

**标签.** 窗口 + CASE | 中等 | Head of Card Intelligence.

**解题思路.** 和 Q2 同一个套路, 只是把"响应"换成"核销". 用 `NTILE(10)` 按 `underwriting_score` 把账户切成十分位, 每层算核销率. 核销与否用 `account_status = 'CHARGED_OFF'` 判断, 用 `CASE WHEN ... THEN 1 ELSE 0 END` 转成 0/1 再求和. 分数从低到高排, 期望核销率整体呈下降趋势 (含噪声, 非严格逐层单调, 中段个别十分位可能回升). 这是评估一个风险模型 rank-ordering 能力最直接的表. 先在 CTE 里算 decile 和 0/1 标签, 外层再分组.

```sql
WITH ranked AS (
    SELECT a.id,
           a.underwriting_score,
           CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END AS co,
           NTILE(10) OVER (ORDER BY a.underwriting_score) AS score_decile
    FROM account a
)
SELECT score_decile,
       COUNT(*) AS n,
       ROUND(100.0 * SUM(co) / COUNT(*), 2) AS chargeoff_rate
FROM ranked
GROUP BY score_decile
ORDER BY score_decile;
```

**预期结果与业务结论.** 10 行, 核销率从最低分段的约 9.7% 整体下滑到最高分段的约 3.2%. 结论: 从整体看, 承保模型是有区分度的, 分数确实能排序风险. 看起来一切正常. 但"整体正常"往往会掩盖局部失灵, 所以下一步必须分段再看一次, 这正是 Q4 要揭穿的.

---

### Q4. 承保分在 Subprime 段失效

**业务背景.** 承接 Q3. 一个资深数据科学家养成的直觉是: 整体 AUC 好看, 不代表每个子群都好. 她怀疑承保模型在某些客群里可能已经失效, 只是被整体数字盖住了. 她决定挑风险最高的 Subprime (band D) 单独看: 在这个段里, 承保分还能不能排序风险? 如果不能, 说明模型对这群人相当于瞎猜, 该给 D 段单独重训一个模型. 这道题对应业务问题 Q_underwriting.

**标签.** 窗口 + Join + 过滤 | 进阶 | Data Scientist.

**解题思路.** 关键动作是**先过滤再分箱**. 先 join `credit_band` 把 band_code 带上, `WHERE band_code = 'D'` 只留 Subprime 账户, 然后在这个子集内部用 `NTILE(5)` 按承保分切五等分 (D 段账户不多, 切 5 份比 10 份稳). 每份看核销率. 如果核销率随分数单调下降, 模型在 D 段有效; 如果上下乱跳没有趋势, 模型在 D 段就是失效的. 这一步只有把过滤放在开窗之前才对, 否则 NTILE 会按全体账户切分, 就不是"D 段内部"的分层了.

```sql
WITH d AS (
    SELECT a.id,
           a.underwriting_score,
           CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END AS co,
           NTILE(5) OVER (ORDER BY a.underwriting_score) AS score_quintile
    FROM account a
    JOIN credit_band b ON a.credit_band_id = b.id
    WHERE b.band_code = 'D'
)
SELECT score_quintile,
       COUNT(*) AS n,
       ROUND(100.0 * SUM(co) / COUNT(*), 2) AS chargeoff_rate
FROM d
GROUP BY score_quintile
ORDER BY score_quintile;
```

**预期结果与业务结论.** 5 行, 核销率在约 9% 到 14% 之间无规律地上下跳 (比如 12%, 11%, 14%, 9%, 11%), 完全没有随分数下降的趋势. 对比 Q3 的整体下降曲线, 这就是铁证: 承保模型在 Subprime 段失去了区分能力. 结论: 立刻把这个发现提交模型风险委员会, 给 D 段单独训练一个子模型或引入新特征. 在此之前, D 段的授信额度和 offer 应保守处理. 这是本数据集给 Data Scientist 岗位量身定做的核心分析.

---

### Q5. 各风险等级批准率与 booked FICO

**业务背景.** VP of Underwriting 要在信贷政策评审会上汇报当前的承保口径. 他需要一张表, 展示每个风险等级 (A 到 E) 收到多少申请, 批准了多少, 以及批准账户的平均 FICO. 这张表是理解"我们到底在给谁放卡"的地基, 也是后面所有风险分析的背景板. 这道题对应业务问题 Q_underwriting.

**标签.** 聚合 + Join | 基础 | VP of Underwriting.

**解题思路.** 单表聚合加一个维度 join. 从 `application` 出发, join `credit_band` 拿到 band_code 和 band_name, 按等级分组. 批准率用 `CASE WHEN decision='APPROVED'` 求和再除以总数. 平均 booked FICO 要注意只对批准的行算, 所以用 `CASE WHEN decision='APPROVED' THEN fico_at_application END` (被拒的返回 NULL, AVG 会自动忽略 NULL). 这是"条件聚合"的常见手法.

```sql
SELECT b.band_code,
       b.band_name,
       COUNT(*) AS apps,
       ROUND(100.0 * SUM(CASE WHEN ap.decision = 'APPROVED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_rate,
       ROUND(AVG(CASE WHEN ap.decision = 'APPROVED' THEN ap.fico_at_application END), 0) AS avg_booked_fico
FROM application ap
JOIN credit_band b ON ap.credit_band_id = b.id
GROUP BY b.band_code, b.band_name
ORDER BY b.band_code;
```

**预期结果与业务结论.** 5 行. 批准率随等级递减: A 约 95%, B 约 80%, C 约 59%, D 约 40%, E 约 18%. Booked FICO 从 A 的约 804 递减到 E 的约 581. 结论: 承保口径整体合理 (风险越高批得越少). 组合以 near-prime (C) 为主, 符合 Keystone 的市场定位. 这张表本身没有陷阱, 但它是 Q16, Q17 (承保随时间放松) 的对照基线.

---

### Q6. 渠道逆向选择

**业务背景.** CMO 在季度营销复盘上遇到一个尴尬问题. 联盟渠道 (affiliate_partner) 的获客成本 (每触达 2 美元) 看起来很划算, 批准率也高, 团队一直想给它加预算. 但 CRO 私下提醒: affiliate 带来的账户后来核销率高得吓人. CMO 需要一张表, 把每个渠道的获客成本和它带来的账户核销率并排放, 看"便宜的渠道是不是其实很贵". 这道题对应业务问题 Q_channel (渠道逆向选择).

**标签.** 聚合 + Join | 中等 | CMO.

**解题思路.** 从 `account` 出发 (因为核销是账户层的事), join `marketing_channel` 拿到渠道名和触达成本, 按渠道分组. 核销率还是 `CASE WHEN account_status='CHARGED_OFF'` 那套. 关键是把 `cost_per_contact_usd` 和 `chargeoff_rate` 放在同一行对照, 让"便宜但坏账高"的矛盾一目了然. 按核销率降序排, 最差的渠道排最前面.

```sql
SELECT mc.channel_name,
       mc.cost_per_contact_usd,
       COUNT(*) AS booked,
       ROUND(100.0 * SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) / COUNT(*), 2) AS chargeoff_rate
FROM account a
JOIN marketing_channel mc ON a.acquisition_channel_id = mc.id
GROUP BY mc.channel_name, mc.cost_per_contact_usd
ORDER BY chargeoff_rate DESC;
```

**预期结果与业务结论.** 6 行. affiliate_partner 核销率约 12.5%, 高居榜首, 约是最便宜两个渠道的 3 倍; 但它的触达成本 (2.00) 却比 digital (4.50) 和 social (3.20) 更低 (只有 direct_mail 0.85 和 prescreen_mail 1.10 比它更便宜, 而这两个更便宜的渠道核销率恰恰落在全场最低的一档——direct_mail 约 4.0%, prescreen_mail 约 4.2%, 都不到 affiliate 的三分之一). 这就是"逆向选择": 一个获客成本不高, 批准率又高的渠道, 带来了最差的客户. 结论: 不能只按获客成本 (CPA) 分配预算, 必须看损失调整后的价值, 这正是 Q7 要算的. 建议先冻结 affiliate 的预算增长.

---

### Q7. 渠道损失调整后的真实获客价值

**业务背景.** 承接 Q6. CMO 被说服了, 现在要一个能真正指导预算分配的指标: 每个渠道每 booked 一个账户, 平均带来多少净核销损失. 把这个"损失成本"和获客成本放一起, 才能算出渠道的真实性价比. 这是从"虚荣指标 CPA"升级到"风险调整后单位经济"的关键一步. 这道题对应业务问题 Q_channel.

**标签.** 多 CTE + LEFT JOIN | 进阶 | CMO.

**解题思路.** 需要把两块信息拼起来: 每个渠道的账户数 (来自 `account`), 和每个渠道的净核销损失 (来自 `charge_off`, 净损失 = 核销余额 - 回收). 因为不是每个账户都核销, 从渠道到损失必须走 LEFT JOIN, 否则没有核销的渠道会整行消失. 第一个 CTE 用 `marketing_channel LEFT JOIN account` 数账户 (保证每个渠道都在), 第二个 CTE 从 `account JOIN charge_off` 汇总每渠道净损失, 外层再 LEFT JOIN 起来, 用 `COALESCE(net_loss, 0)` 把没损失的渠道补 0. 每 booked 净损失 = 净损失 / 账户数.

```sql
WITH ch AS (
    SELECT mc.id,
           mc.channel_name,
           mc.cost_per_contact_usd,
           COUNT(a.id) AS booked,
           SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) AS co
    FROM marketing_channel mc
    LEFT JOIN account a ON a.acquisition_channel_id = mc.id
    GROUP BY mc.id
),
loss AS (
    SELECT a.acquisition_channel_id AS cid,
           SUM(co.charged_off_balance_usd - co.recovery_amount_usd) AS net_loss
    FROM account a
    JOIN charge_off co ON co.account_id = a.id
    GROUP BY a.acquisition_channel_id
)
SELECT ch.channel_name,
       ch.cost_per_contact_usd,
       ch.booked,
       ROUND(100.0 * ch.co / ch.booked, 2) AS co_rate,
       ROUND(COALESCE(loss.net_loss, 0) / ch.booked, 0) AS net_loss_per_booked
FROM ch
LEFT JOIN loss ON loss.cid = ch.id
ORDER BY net_loss_per_booked DESC;
```

**预期结果与业务结论.** 6 行. affiliate_partner 每 booked 净损失约 625 美元, 是 prescreen_mail (约 165 美元) 的约 3.8 倍. 把它和 Q6 的低触达成本放一起, 结论很硬: affiliate 每个账户省下的几美元获客成本, 被几百美元的核销损失彻底吞没. 建议把预算从 affiliate 转向 prescreen_mail 和 branch_referral (损失最低), 并要求 affiliate 合作方改进流量质量后再谈加预算.

---

### Q8. 组合利用率分布

**业务背景.** VP of Portfolio Management 要给风险委员会准备一张组合利用率 (utilization) 分布图. 利用率 = 余额 / 额度, 是衡量"客户把额度用到多满"的核心指标. 利用率高的账户既贡献利息 (好事), 又更接近违约边缘 (坏事). 他需要知道当前有多少账户挤在高利用率区间, 因为这直接关系到组合的脆弱程度和 CECL 拨备. 这道题对应业务问题 Q_portfolio.

**标签.** CTE + 窗口 | 中等 | VP of Portfolio Management.

**解题思路.** 每个账户有很多期账单, 我们只要"最新一期"的利用率作为当前快照. 取每个账户 `cycle_month` 最大的那期账单. 常见做法有两种: 窗口函数 `ROW_NUMBER`, 或者先算每账户的 `MAX(cycle_month)` 再 join 回去. 这里用后者 (更直观): 一个 CTE 算每账户最大 cycle_month, 再 join 回 `statement` 取那一行. 然后用 `CASE` 把 `utilization_pct` 分桶 (0-30, 30-60, 60-90, 90+), 分桶计数.

```sql
WITH latest AS (
    SELECT account_id, MAX(cycle_month) AS mx
    FROM statement
    GROUP BY account_id
),
s AS (
    SELECT st.*
    FROM statement st
    JOIN latest l ON st.account_id = l.account_id AND st.cycle_month = l.mx
)
SELECT CASE
           WHEN utilization_pct < 30 THEN '0-30'
           WHEN utilization_pct < 60 THEN '30-60'
           WHEN utilization_pct < 90 THEN '60-90'
           ELSE '90+'
       END AS util_bucket,
       COUNT(*) AS n,
       ROUND(AVG(statement_balance_usd), 0) AS avg_balance
FROM s
GROUP BY util_bucket
ORDER BY util_bucket;
```

**预期结果与业务结论.** 4 行. 相当一部分账户 (约 47%) 落在 90%+ 的高利用率桶, 平均余额约 5,800 美元, 主要是 revolver. 结论: 组合里高利用率账户占比不低, 这既是利息收入的来源, 也是风险的集中点. 这批高利用率账户正是 Q9 (提额逆向选择) 要重点盯的人群, 因为给他们提额可能适得其反.

---

### Q9. 提额 (CLI) 逆向选择

**业务背景.** Chief Credit Officer 要复盘去年的提额 (Credit Line Increase, CLI) 策略. 常规逻辑是: 给用卡活跃, 利用率高的"好客户"提额, 让他们花更多. 但他担心一件事: 那些提额前就已经把额度用到 70% 以上的人, 会不会本身就是快撑不住的人? 给他们提额相当于往火上浇油. 他需要按"提额前利用率"分组, 对比核销率. 这道题对应业务问题 Q_cli (提额逆向选择).

**标签.** Join + CASE | 中等 | Chief Credit Officer.

**解题思路.** 核心字段是 `credit_line_change.pre_change_utilization_pct` (提额前利用率), 这是数据集专门为这个分析埋的. 从 `credit_line_change` 里筛出 `change_type='CLI'` 的提额事件, join 回 `account` 拿核销状态, 用 `CASE` 按提额前利用率是否超过 70% 分两组, 各算核销率. 因为一个账户理论上可能多次提额, 用 `COUNT(DISTINCT a.id)` 去重更稳妥. 对比两组核销率就能看出逆向选择.

```sql
SELECT CASE
           WHEN clc.pre_change_utilization_pct > 70 THEN 'pre-CLI util > 70%'
           ELSE 'pre-CLI util <= 70%'
       END AS segment,
       COUNT(DISTINCT a.id) AS n,
       ROUND(100.0 * SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) / COUNT(DISTINCT a.id), 2) AS chargeoff_rate
FROM credit_line_change clc
JOIN account a ON clc.account_id = a.id
WHERE clc.change_type = 'CLI'
GROUP BY segment
ORDER BY chargeoff_rate DESC;
```

**预期结果与业务结论.** 2 行. 提额前利用率 > 70% 的账户核销率约 10.6%, 而 <= 70% 的只约 3.0%, 差了约 3.6 倍. 结论: 现行 CLI 策略存在明显逆向选择, "高利用率就提额"这条规则在给风险最高的人加杠杆. 建议把 CLI 审批规则改成: 高利用率账户先看还款行为再决定, 不能只凭"用得多"就提. 这能直接降低未来的核销损失.

---

### Q10. 逾期桶分布 (roll 快照)

**业务背景.** Collections Manager 每周一早上要看一张"逾期快照": 当前组合里, 有多少账户是正常 (CURRENT), 多少落在各个逾期桶 (DPD30, DPD60, DPD90, DPD120PLUS). 这是催收团队排班和预测损失的起点. 逾期越深, 救回来的概率越低. 这道题对应业务问题 Q_collections.

**标签.** CTE + 聚合 | 基础 | Collections Manager.

**解题思路.** 和 Q8 一样, 先取每个账户的最新账单作为当前状态. 一个 CTE 算每账户 `MAX(cycle_month)`, join 回去取最新账单的 `dpd_bucket`. 然后按逾期桶计数, 并算占比 (用一个标量子查询拿总数当分母). 按账户数降序, 让最大的桶 (通常是 CURRENT) 排最前.

```sql
WITH latest AS (
    SELECT account_id, MAX(cycle_month) AS mx
    FROM statement
    GROUP BY account_id
),
s AS (
    SELECT st.dpd_bucket
    FROM statement st
    JOIN latest l ON st.account_id = l.account_id AND st.cycle_month = l.mx
)
SELECT dpd_bucket,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM s), 2) AS pct
FROM s
GROUP BY dpd_bucket
ORDER BY n DESC;
```

**预期结果与业务结论.** 4 行左右. 约 92.5% 的账户当前是 CURRENT (正常), 约 7% 落在 DPD120PLUS (这些大多是正走向核销的账户的最后一期账单), DPD30 和 DPD60 各只占零点几个百分点. 结论: 组合当前逾期率健康, 但深度逾期 (120+) 占比就是未来核销的先行指标. 催收资源应优先投给还有救的 DPD30 到 DPD60 账户, 因为它们 roll 到核销之前还有 3 个月窗口 (见 Q13 的早期预警逻辑).

---

### Q11. 产品阶梯完整 P&L

**业务背景.** CFO 要在董事会上回答一个看似简单其实很难的问题: 我们 6 款卡, 到底哪款真赚钱? 直觉上高端旅行卡 (Venture Premium) 又收 395 美元年费又刷得多, 应该最赚; 起步的 Secured 卡没年费没 rewards, 应该最不赚. CFO 要求一张完整 P&L: 每款产品的利息, interchange, 费用 (收入侧), 减去 rewards 和净核销损失 (成本侧), 再减去发出去的开卡奖金. 这道题对应业务问题 Q_productpnl (产品阶梯盈利性).

**标签.** 多 CTE + Join | 进阶 | CFO.

**解题思路.** 收入和成本散在两张表: 逐月的经济项在 `statement`, 核销损失在 `charge_off`. 先用一个 CTE 从 `statement` 按账户汇总利息, interchange, 费用, rewards 四项; 再用一个 CTE 从 `charge_off` 按账户汇总净损失. 主查询从 `account` join 产品, 两个 CTE 都用 LEFT JOIN 接上 (因为大多数账户没核销), 用 `COALESCE(..., 0)` 补空. 最后按产品聚合, net P&L = 利息 + interchange + 费用 - rewards - 净损失 - 开卡奖金. 关键陷阱: 一定要用 LEFT JOIN 接 charge_off, 否则只剩核销账户, P&L 会算成一片亏损.

```sql
WITH econ AS (
    SELECT account_id,
           SUM(interest_charged_usd) AS interest,
           SUM(interchange_revenue_usd) AS interchange,
           SUM(fees_charged_usd) AS fees,
           SUM(rewards_earned_usd) AS rewards
    FROM statement
    GROUP BY account_id
),
loss AS (
    SELECT account_id,
           SUM(charged_off_balance_usd - recovery_amount_usd) AS net_loss
    FROM charge_off
    GROUP BY account_id
)
SELECT p.product_name,
       COUNT(*) AS accts,
       ROUND(SUM(COALESCE(e.interest, 0)), 0) AS interest,
       ROUND(SUM(COALESCE(e.interchange, 0)), 0) AS interchange,
       ROUND(SUM(COALESCE(e.fees, 0)), 0) AS fees,
       ROUND(SUM(COALESCE(e.rewards, 0)), 0) AS rewards,
       ROUND(SUM(COALESCE(l.net_loss, 0)), 0) AS net_loss,
       ROUND(SUM(COALESCE(e.interest, 0) + COALESCE(e.interchange, 0) + COALESCE(e.fees, 0)
                 - COALESCE(e.rewards, 0) - COALESCE(l.net_loss, 0) - a.signup_bonus_usd), 0) AS net_pnl
FROM account a
JOIN card_product p ON a.card_product_id = p.id
LEFT JOIN econ e ON e.account_id = a.id
LEFT JOIN loss l ON l.account_id = a.id
GROUP BY p.product_name
ORDER BY net_pnl DESC;
```

**预期结果与业务结论.** 6 行, 结论出人意料. 最赚钱的是没人看好的 Keystone Secured (净利约 +108 万美元, 靠 26.99% 高 APR 的 revolver 利息), 其次是 Venture Premium 和 Student (各约 +22 万到 +25 万). 而两款主打高返现的 Cashback Plus (约 -32 万) 和 Travel (约 -8 万) 整体是亏损的; 返现率较低的基础款 Cashback 反倒小幅盈利 (约 +5 万). 结论: 高 rewards 卡的 rewards 成本和获客成本吃掉了利润, 而低调的 Secured/near-prime revolver 才是利润引擎. 建议重新审视 Cashback Plus 和 Travel 的 rewards 结构和年费定价, 具体原因见 Q12 和 Q19.

---

### Q12. Transactor vs Revolver 单账户贡献

**业务背景.** Product Manager 看到 Q11 的结果很困惑: 为什么高端卡反而亏? CFO 让她再往下切一层, 把每款卡的客户按行为分成两类. Transactor (每月全额还款, 从不付利息) 和 revolver (滚动余额, 付利息). 她怀疑亏损集中在 transactor 身上: 这些人只薅 rewards 不付利息. 她要对比每款 rewards 卡上两类客户的单账户完整贡献. 这道题对应业务问题 Q_productpnl 和 Q_transactor (transactor 盈利性).

**标签.** CTE + Join | 中等 | Product Manager.

**解题思路.** "完整贡献"和 Q11 口径一致, 但下沉到单账户平均, 并按 `behavior_segment` 再分一层. 用一个 CTE 从 `statement` 算每账户的经营 margin (利息 + interchange + 费用 - rewards), 再用一个 CTE 算每账户净核销损失. 主查询 join 产品, 按 (产品, 行为) 分组, 算平均的 (margin - 开卡奖金 - 净损失). 只看 rewards 卡 (`rewards_rate_pct >= 0.015`), 因为陷阱只在有意义的 rewards 率上出现. Transactor 在正常还款月不计息 (`interest_charged_usd` 为 0), 这是他们贡献低的根源.

```sql
WITH econ AS (
    SELECT account_id,
           SUM(interest_charged_usd + interchange_revenue_usd + fees_charged_usd - rewards_earned_usd) AS margin
    FROM statement
    GROUP BY account_id
),
loss AS (
    SELECT account_id,
           SUM(charged_off_balance_usd - recovery_amount_usd) AS net_loss
    FROM charge_off
    GROUP BY account_id
)
SELECT p.product_name,
       p.rewards_rate_pct,
       a.behavior_segment,
       COUNT(*) AS n,
       ROUND(AVG(COALESCE(e.margin, 0) - a.signup_bonus_usd - COALESCE(l.net_loss, 0)), 2) AS avg_contribution
FROM account a
JOIN card_product p ON a.card_product_id = p.id
LEFT JOIN econ e ON e.account_id = a.id
LEFT JOIN loss l ON l.account_id = a.id
WHERE p.rewards_rate_pct >= 0.015
GROUP BY p.product_name, a.behavior_segment
ORDER BY p.id, a.behavior_segment;
```

**预期结果与业务结论.** 在每款 rewards 卡上, transactor 的单账户平均贡献都是负的 (Cashback 约 -223, Cashback Plus 约 -426, Travel 约 -168, 连 Venture Premium 也约 -28), 而同产品的 revolver 都是正的 (从 +20 到 +1,010). 结论: 高端卡亏损的真凶是 transactor. 他们贡献 interchange (约 1.8% 刷卡额), 却被更高的 rewards (2% 到 2.5%) 吃穿, 又不付利息. 建议要么降 rewards 率, 要么提年费, 要么在营销上别再用高 rewards 去吸引明显的 transactor 画像人群 (可以直接接 Data Science 的客群模型).

---

### Q13. Promo APR 悬崖

**业务背景.** 有一批账户是靠"0% APR 余额代偿 (balance transfer) 12 个月"的促销拉来的. Data Scientist 在做流失和风险预测时发现一个诡异现象: 这批账户前 11 个月乖得很, 一到第 12 到 14 个月就集体出问题. 她怀疑是"促销悬崖": 0% 一到期, 利率突然跳到 20% 以上, 月供陡增, 一批人扛不住就逾期了. 她要按账龄 (cycle_month) 对比促销账户和非促销账户的 DPD30+ 率, 把悬崖画出来. 这道题对应业务问题 Q_promo (promo APR 悬崖).

**标签.** 条件聚合 + 时序 | 进阶 | Data Scientist.

**解题思路.** 这题的巧妙之处是**在同一次扫描里, 按账龄横向对比两个人群**. 从 `statement` join `account`, 不做人群过滤, 而是在聚合里用两组条件求和: 一组只统计促销账户 (`is_promo_apr=1`) 的 DPD30+ 率, 另一组只统计非促销账户. 用 `SUM(CASE WHEN is_promo_apr=1 AND days_past_due>=30 ...)` 除以 `SUM(is_promo_apr=1)` 得到促销组的率, 非促销组同理. 按 `cycle_month` 分组, 就能看到两条曲线随账龄怎么走. 促销组应在 12 到 14 月出现尖峰. `NULLIF` 防止某个账龄某组为 0 时除零.

```sql
SELECT s.cycle_month,
       ROUND(100.0 * SUM(CASE WHEN a.is_promo_apr = 1 AND s.days_past_due >= 30 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN a.is_promo_apr = 1 THEN 1 ELSE 0 END), 0), 2) AS promo_dpd30,
       ROUND(100.0 * SUM(CASE WHEN a.is_promo_apr = 0 AND s.days_past_due >= 30 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN a.is_promo_apr = 0 THEN 1 ELSE 0 END), 0), 2) AS nonpromo_dpd30
FROM statement s
JOIN account a ON s.account_id = a.id
WHERE s.cycle_month BETWEEN 6 AND 16
GROUP BY s.cycle_month
ORDER BY s.cycle_month;
```

**预期结果与业务结论.** 约 11 行. 促销组的 DPD30+ 在 cycle_month 6 到 11 只有约 2% 到 5%, 到第 12 到 14 月骤升到约 12%, 之后又回落; 而非促销组的 DPD30+ 一路平缓下滑到 1% 以下, 没有任何尖峰. 两条曲线的对比让"悬崖"无所遁形. 结论: 0% 促销到期是一个可预测的风险事件. 建议在促销到期前 1 到 2 个月主动触达这批客户 (提醒, 提供分期或再融资), 把悬崖填平; 同时数据科学团队可以把"距促销到期月数"做成风险模型的一个强特征.

---

### Q14. interchange 按 MCC 拆解

**业务背景.** CFO 办公室的财务分析师要拆解 interchange 收入的来源. Interchange 是每笔刷卡商户方付给发卡行的手续费, 是 Keystone 的三大收入之一. 不同商户类别 (MCC) 的费率不同 (航空, 酒店高, 超市, 加油低). 分析师要知道钱主要从哪些品类刷出来, 好向支付网络谈判和做品类营销. 这道题对应业务问题 Q_interchange.

**标签.** Join + 聚合 | 基础 | CFO office.

**解题思路.** 直接从抽样交易表 `transaction` 出发 (注意这是 SQL 保留字, 要用双引号括起来), join `mcc_category` 拿品类名, 按品类聚合. 汇总交易笔数, 刷卡额, interchange 收入, 并算一个有效费率 (interchange / 刷卡额) 验证数据合理性. 按 interchange 收入降序, 看哪些品类贡献最大. 这里的 interchange 用的是交易表里已经算好的 `interchange_revenue_usd`.

```sql
SELECT m.category_name,
       COUNT(*) AS txns,
       ROUND(SUM(t.amount_usd), 0) AS spend,
       ROUND(SUM(t.interchange_revenue_usd), 0) AS interchange,
       ROUND(100.0 * SUM(t.interchange_revenue_usd) / SUM(t.amount_usd), 3) AS eff_rate
FROM "transaction" t
JOIN mcc_category m ON t.mcc_category_id = m.id
GROUP BY m.category_name
ORDER BY interchange DESC;
```

**预期结果与业务结论.** 12 行. Restaurants, Online Retail, Grocery 贡献的 interchange 最多 (各约 4.3 万到 5.2 万美元, 因为刷卡量大), 有效费率在 1.3% (Utilities) 到 2.1% (Airlines, Hotels) 之间, 和各 MCC 的挂牌费率吻合. 结论: 收入集中在高频日常消费品类. 建议把 rewards 活动设计得鼓励高费率品类 (餐饮, 旅行) 的消费, 在不亏 rewards 的前提下抬高 interchange 收入. 这是产品和财务的结合点.

---

### Q15. Bonus churner 负 LTV

**业务背景.** VP of Acquisitions 在复盘大额开卡奖金 (signup bonus) 活动. 营销团队爱用大 bonus 冲开卡量, 但她怀疑有一批"奖金猎人 (bonus churner)": 刷够最低消费拿到 bonus, 然后就把卡打入冷宫, 几个月后销卡, 全程几乎不给公司赚钱. 她要按销卡原因 (close_reason) 分组, 算每组账户的平均 lifetime 价值 (LTV), 看 bonus_churn 那组是不是负的. 这道题对应业务问题 Q_bonus (bonus churner 负 LTV).

**标签.** CTE + Join | 中等 | VP of Acquisitions.

**解题思路.** LTV 的一个简化口径 = 账户一生的经营 margin 减去发给它的开卡奖金. 用一个 CTE 从 `statement` 算每账户的 margin (利息 + interchange + 费用 - rewards). 主查询从 `attrition_event` (只有销卡的账户在这) join `account`, 再 LEFT JOIN margin, 按 `close_reason` 分组算平均 LTV. 用 LEFT JOIN 是因为极少数销卡账户可能没有账单. bonus_churn 组的 LTV 应显著为负, 且是所有原因里最低的.

```sql
WITH econ AS (
    SELECT account_id,
           SUM(interest_charged_usd + interchange_revenue_usd + fees_charged_usd - rewards_earned_usd) AS margin
    FROM statement
    GROUP BY account_id
)
SELECT ae.close_reason,
       COUNT(*) AS n,
       ROUND(AVG(COALESCE(e.margin, 0) - a.signup_bonus_usd), 2) AS avg_ltv
FROM attrition_event ae
JOIN account a ON ae.account_id = a.id
LEFT JOIN econ e ON e.account_id = a.id
GROUP BY ae.close_reason
ORDER BY avg_ltv;
```

**预期结果与业务结论.** 6 行. `bonus_churn` 的平均 LTV 约 -280 美元, 是唯一为负的销卡原因; 其余 (rate_shopping, inactivity, dissatisfaction, product_upgrade, charge_off) 的 LTV 都在 +325 以上. 一个要留意的口径: 这里的 LTV 只减了开卡奖金, **没有减核销损失** (它衡量的是"经营 margin 扣 bonus", 不是完整贡献), 所以 `charge_off` 那组的 LTV 反而排最高 (约 +560), 这是口径使然而非说核销账户最赚钱; 要看含核销损失的完整贡献, 去看 Q11 或 Q12 的 account_contribution. 本题的教学重点是 bonus_churn 是唯一为负的群体. 结论: 奖金猎人确实在系统性地亏钱. 建议对大额 bonus 活动加"反薅"设计: 提高最低消费门槛, 拉长 bonus 兑现周期, 或对短期销卡做 bonus 清回 (clawback). 同时数据科学可以在申请环节就用模型识别高 churn 风险画像.

---

### Q16. Vintage 损失曲线

**业务背景.** Chief Risk Officer 要给投资人准备一份组合质量报告. 信用卡风险最怕"越放越松而不自知". 判断的经典方法是 vintage (按开卡季度分组) 损失曲线: 把每个季度开出的账户当成一个 cohort, 看它们在相同账龄 (比如 month_on_book <= 6) 时的核销率. 如果近期 cohort 在同样账龄时核销更高, 说明承保质量在恶化. 这道题对应业务问题 Q_vintage (vintage 恶化).

**标签.** 日期 + 条件聚合 | 中等 | Chief Risk Officer.

**解题思路.** 数据集已经把开卡季度算好放在 `account.open_vintage` (形如 '2025Q2'), 省了自己从日期拼季度. 按 `open_vintage` 分组, 每组算"在账龄 6 个月内就核销的账户占比", 即 `account_status='CHARGED_OFF' AND months_on_book <= 6` 的比例. 要排除最近两个季度 (2026), 因为它们大部分账户还没活到 6 个月账龄, 分母不可比 (用 `WHERE open_vintage < '2026Q1'`). 比较各季度的 mob6 核销率, 看趋势.

```sql
SELECT open_vintage,
       COUNT(*) AS n,
       ROUND(100.0 * SUM(CASE WHEN account_status = 'CHARGED_OFF' AND months_on_book <= 6 THEN 1 ELSE 0 END) / COUNT(*), 2) AS co_rate_by_mob6
FROM account
WHERE open_vintage < '2026Q1'
GROUP BY open_vintage
ORDER BY open_vintage;
```

**预期结果与业务结论.** 6 行. 早期 vintage (2024Q3) 的 mob6 核销率约 0.7%, 到近期 vintage (2025Q4) 升到约 4.4% (把 2024Q3 到 2025Q2 合起来约 1.2%, 2025 下半年约 3.4%). 尽管季度间有噪声, 上升趋势清楚. 结论: 承保质量在系统性恶化, 近期批次坏得更快. 这是要立刻上报董事会和投资人的信号. 下一步用 Q17 定位恶化的原因 (是不是批准放松了).

---

### Q17. 承保标准随时间漂移

**业务背景.** 承接 Q16. CRO 已经看到近期 vintage 坏得更快, 现在要找原因. 最可能的解释是承保标准在悄悄放松: 批准率往上爬, 批准账户的平均 FICO 往下滑. 她要按申请季度看批准率和 booked FICO 的时间趋势, 把"放水"坐实. 这道题对应业务问题 Q_vintage.

**标签.** 日期函数 | 中等 | Chief Risk Officer.

**解题思路.** 这次没有现成的季度列 (application 表没有 open_vintage), 要自己从 `application_date` 用 `strftime` 拆出年和季度. 年用 `strftime('%Y', application_date)`, 季度用月份 `(月 - 1) / 3 + 1`. 注意 `strftime` 返回字符串, 参与算术前要 `CAST(... AS INT)`. 按 (年, 季度) 分组, 算批准率和 booked FICO 均值 (booked FICO 用 Q5 里那招条件聚合). 按时间排序看趋势.

```sql
SELECT CAST(strftime('%Y', application_date) AS INT) AS yr,
       (CAST(strftime('%m', application_date) AS INT) - 1) / 3 + 1 AS quarter,
       COUNT(*) AS apps,
       ROUND(100.0 * SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_rate,
       ROUND(AVG(CASE WHEN decision = 'APPROVED' THEN fico_at_application END), 0) AS avg_booked_fico
FROM application
GROUP BY yr, quarter
ORDER BY yr, quarter;
```

**预期结果与业务结论.** 8 行. 批准率从 2024Q3 的约 55% 缓升到 2026Q2 的约 60%, 同时 booked FICO 从约 722 一路滑到约 694. 结论: 承保标准确实在放松, 这解释了 Q16 的 vintage 恶化. 建议把 FICO 审批下限拉回来, 或至少对近期放松的边际客群加强定价和额度管控. CRO 现在有了完整的因果链条 (放松承保 → vintage 恶化) 去说服业务团队踩刹车.

---

### Q18. Champion vs Challenger 表现

**业务背景.** CMO 要评估营销的 champion/challenger 测试机制. Champion 是稳态主推的 offer, challenger 是试验性的新 offer (常带更大的 bonus 或更激进的促销). 她想知道: challenger 这些花哨 offer 拉来的客户, 质量和 champion 比如何? 会不会为了冲量牺牲了资产质量? 这道题对应业务问题 Q_champion.

**标签.** Join + 聚合 | 基础 | CMO.

**解题思路.** 从 `campaign` 出发, 按 `is_champion` 分两组, LEFT JOIN `account` 拿到每组拉来的账户. 用 LEFT JOIN 保证即使某类 campaign 没拉到账户也不丢. 每组算 campaign 数, booked 账户数, 平均开卡奖金, 以及核销率. 对比两组核销率和 bonus, 看 challenger 是不是"高 bonus 换低质量".

```sql
SELECT c.is_champion,
       COUNT(DISTINCT c.id) AS campaigns,
       COUNT(a.id) AS booked,
       ROUND(AVG(a.signup_bonus_usd), 0) AS avg_bonus,
       ROUND(100.0 * SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) / COUNT(a.id), 2) AS chargeoff_rate
FROM campaign c
LEFT JOIN account a ON a.campaign_id = c.id
GROUP BY c.is_champion;
```

**预期结果与业务结论.** 2 行. Challenger (is_champion=0) 平均 bonus 更高 (约 106 vs champion 约 66), 但它的核销率反而更低 (约 5.6% vs champion 约 9.4%). 这个结果需要小心解读: 差异主要来自 champion/challenger 各自绑定的产品和渠道不同, 而不是"challenger 更好". 结论: champion/challenger 的对比必须控制产品和渠道后再看, 否则会得出误导性结论. 这是提醒分析师"辛普森悖论"风险的一道教学题, 建议下一步按产品分层复算.

---

### Q19. rewards 侵蚀 interchange

**业务背景.** CFO 在 Q11 看到高端卡亏损后, 要一个更聚焦的证据: rewards 到底有没有把 interchange 收入吃穿. 逻辑很简单, 发卡行刷卡赚约 1.8% 的 interchange, 但如果一张卡返 2% 到 2.5% 的 rewards, 那每刷 1 美元反而净亏. 她要按产品对比 interchange 收入和 rewards 成本, 算净差. 这道题对应业务问题 Q_transactor 和 Q_productpnl.

**标签.** CTE + Join | 中等 | CFO.

**解题思路.** 从 `statement` join `account` 拿到产品维度, 按产品汇总 interchange 收入和 rewards 成本. 一个 CTE 就够. 主查询算 `interchange - rewards` 这个净差, 按产品 id 排序 (让 rewards 率从低到高排). 净差为负的产品就是"rewards 侵蚀 interchange"的铁证. 这是 Q11/Q12 的一个更纯粹的切片.

```sql
WITH s AS (
    SELECT a.card_product_id,
           SUM(st.interchange_revenue_usd) AS interchange,
           SUM(st.rewards_earned_usd) AS rewards
    FROM statement st
    JOIN account a ON st.account_id = a.id
    GROUP BY a.card_product_id
)
SELECT p.product_name,
       p.rewards_rate_pct,
       ROUND(s.interchange, 0) AS interchange,
       ROUND(s.rewards, 0) AS rewards,
       ROUND(s.interchange - s.rewards, 0) AS net_interchange_after_rewards
FROM card_product p
JOIN s ON s.card_product_id = p.id
ORDER BY p.id;
```

**预期结果与业务结论.** 6 行, 呈现一个漂亮的梯度. 返现率 0 到 1.5% 的卡 (Secured, Student, Cashback) 净差为正 (interchange 覆盖 rewards); 而返现率 >= 2% 的卡 (Cashback Plus 约 -5.8 万, Travel 约 -7.1 万, Venture Premium 约 -29.6 万) 净差为负, rewards 把 interchange 吃穿. 结论: rewards 率一旦逼近或超过 interchange 费率 (约 1.8%), 单靠刷卡就开始亏, 必须靠利息 (revolver) 或年费补. 建议把高端卡的 rewards 率下调到 interchange 之下, 或用年费兜底. 这条结论和 Q12 的 transactor 亏损互为印证.

---

### Q20. 月度新开卡趋势

**业务背景.** 一名新入职的 Data Analyst 被安排的第一个任务: 做一张月度新开卡趋势图, 供高管周会看. 这是最基础的运营监控, 也是分析师熟悉数据的起手式. 看开卡量有没有季节性, 有没有异常月份. 这道题对应业务问题 Q_ops.

**标签.** 日期 + 聚合 | 基础 | Data Analyst.

**解题思路.** 最简单的时间序列聚合. 用 `strftime('%Y-%m', open_date)` 把开卡日截断到月, 按月计数. 按月份排序. 这题的教学点是熟悉 SQLite 的日期函数 `strftime` 和"按时间粒度分组"的通用模式, 后面很多趋势分析都是它的变体.

```sql
SELECT strftime('%Y-%m', open_date) AS month,
       COUNT(*) AS new_accounts
FROM account
GROUP BY month
ORDER BY month;
```

**预期结果与业务结论.** 约 24 行 (每月一行). 除最早的 2024-07 偏低 (数据窗口起点, 只有半个月, 约 165) 外, 月开卡量大致在约 320 到 450 之间波动, 并随组合累积逐步走高 (近月 2026 年多在 400 以上, 收尾月约 440). 结论: 开卡量总体平稳, 无异常断崖, 也无单日堆积. 这张表是所有运营看板的基础, 分析师可以在此基础上叠加渠道, 产品维度做更细的拆分.

---

## 5. 查询与业务问题映射

| 业务问题 | 对应查询 |
|----------|----------|
| 承保模型校准 (陷阱 1) | Q3, Q4 |
| 渠道逆向选择 (陷阱 2) | Q6, Q7 |
| Transactor 盈利性 (陷阱 3) | Q12, Q19 |
| Promo APR 悬崖 (陷阱 4) | Q13 |
| CLI 逆向选择 (陷阱 5) | Q9 |
| Bonus churner 负 LTV (陷阱 6) | Q15 |
| Vintage 恶化 (陷阱 7) | Q16, Q17 |
| 产品阶梯 P&L (陷阱 8) | Q11, Q12, Q19 |
| 获客与响应模型 | Q1, Q2, Q18 |
| 承保与组合运营 | Q5, Q8, Q10 |
| 收入与运营监控 | Q14, Q20 |
