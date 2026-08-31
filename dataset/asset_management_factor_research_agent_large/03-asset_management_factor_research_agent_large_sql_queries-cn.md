# Tessellate Capital Management 因子研究 AI Agent - SQL 查询

> 业务背景, 公司介绍, 术语表请见 `01-asset_management_factor_research_agent_large_business_context-cn.md`
> 表结构, 字段含义, 生成规则请见 `02-asset_management_factor_research_agent_large_er_document-cn.md`

## 参考日期约定

本数据集锚定在 **`REFERENCE_DATE = 2026-06-30`**。下面每一条查询里凡是需要"今天"的地方,都写成字面量日期字符串 (比如 `'2026-06-30'`),**不使用 `DATE('now')`**。这样无论哪一天运行,结果都完全一致 —— 因子研究的第一条纪律就是可复现。

## 如何使用本文档

本文档写给一个已经读完业务背景与 ER 文档、正要被经理派活的实习生。你的经理刚刚说: "这周把这 22 道题做完。"

**每一条查询有五个部分:**

| 部分 | 作用 |
|------|------|
| **业务背景** | 谁在问、为什么现在问、答案会推动什么决定 |
| **标签** | SQL 类别、难度、提问的角色 |
| **解题思路** | 在你看到 SQL 之前, 先想清楚要 join 哪些表、以什么粒度聚合、哪里有坑 |
| **SQL** | 可以直接跑的代码 |
| **预期结果与业务结论** | 结果长什么样、数字大概在什么量级、拿到之后该做什么 |

**几条通用提醒:**

1. **每一条查询都能追溯到业务背景文档里的五个业务问题之一** (Q1 到 Q5),文末有映射表。
2. **前 10 条是支撑性查询**,负责把基础指标、衍生指标和中间变量算出来。**后 12 条是分析性查询**,负责真正验证因子、比较假设、并给出结论。做题请按顺序 —— 后面的题假设你已经理解了前面的口径。
3. **本文档里有一个反复出现的 CTE 组合 `month_end_bar` + `fwd`**,它负责算"月末到下一个月末的前瞻收益"。第一条查询会把它讲透,后面直接复用。
4. **SQL 要读, 不只是跑。** 这份文档里有好几处地方,同一个问题写两种写法会给出完全不同的答案 —— 那不是 bug,那是重点。

---

## 查询索引

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 |
|------|------|----------|----------|------|
| **支撑性查询** | | | | |
| Q1 | 月度前瞻收益: 唯一正确的算法 | Head of Data Engineering | Window Function + Join | 基础 |
| Q2 | 因子暴露的日常体检 | Quantitative Research Analyst | Aggregation + Join | 基础 |
| Q3 | 自己动手算 RankIC, 并和官方口径对账 | Head of Model Validation | CTE + Window + 统计 | 中级 |
| Q4 | 因子库总览: IC 汇总统计 | Head of Quantitative Research | Aggregation + 统计 | 中级 |
| Q5 | 分层单调性检验 | Quantitative Research Analyst | Aggregation + Join | 基础 |
| Q6 | 换手率与单位交易成本 | Head of Trading | 多 CTE + Join | 中级 |
| Q7 | 数据覆盖度与退市节奏 | Head of Data Engineering | Aggregation + 日期函数 | 基础 |
| Q8 | PIT 发布滞后与财报修订率 | Head of Data Engineering | Aggregation + UNION ALL | 基础 |
| Q9 | 市场 regime 时间线 | Chief Risk Officer | Aggregation + LEFT JOIN | 基础 |
| Q10 | 研究组合持仓画像与约束顶格 | Director of Portfolio Construction | Aggregation + 条件计数 | 中级 |
| **分析性查询** | | | | |
| Q11 | 成本前后 IR 全景: alpha 被吃掉了多少 | Head of Trading | Aggregation + 派生指标 | 中级 |
| Q12 | 成本敏感性: 价差翻倍会怎样 | Head of Trading | CROSS JOIN + 情景计算 | 高级 |
| Q13 | **Look-ahead bias: 两种 as-of 口径的对决** | Head of Model Validation | 多 CTE + 窗口 + 统计 | 高级 |
| Q14 | **幸存者偏差: 加回退市标的会怎样** | Head of Model Validation | CTE + NTILE + UNION ALL | 高级 |
| Q15 | **多重检验: 试得越多, 门槛越高** | Head of Quantitative Research | Join + 条件判定 | 中级 |
| Q16 | **Regime 拆分: 谁在换环境后翻脸** | Chief Risk Officer | 条件聚合 (透视) | 中级 |
| Q17 | **正交性: 这是新因子还是旧因子换皮** | Head of Quantitative Research | 自连接 + 相关系数 | 高级 |
| Q18 | **容量: 效果是不是全在装不下钱的地方** | Director of Portfolio Construction | 条件聚合 (透视) | 中级 |
| Q19 | **财报修订: 用原始版重算一遍** | Head of Model Validation | 多 CTE + 窗口 + 统计 | 高级 |
| Q20 | 协方差估计在 regime 切换时靠不靠谱 | Chief Risk Officer | Aggregation + HAVING | 中级 |
| Q21 | 约束档位如何一步步削掉 alpha | Director of Portfolio Construction | Join + 标量子查询 | 中级 |
| Q22 | Atlas 产能复盘: 36 分钟到底做了什么 | Chief Investment Officer | 多表聚合 + 相关子查询 | 中级 |

---

## 第一部分: 支撑性查询 (Q1 - Q10)

这十条负责把地基打好。它们本身不产生结论,但后面每一条分析性查询都建立在它们的口径之上。**如果这一部分的口径错了,后面全错。**

---

### Q1. 月度前瞻收益: 唯一正确的算法

**业务背景**

Head of Data Engineering 在上周的数据治理评审上被 Head of Model Validation 当场质疑: 研究部门有三个人各写了一版"月度前瞻收益"的计算,三份结果都不一样。追查下来,分歧全在同一个地方 —— **已退市标的的最后一个月怎么处理**。

有人用 `LEAD(adj_close)` 直接取下一行,完全没意识到一只 2024 年 3 月退市的股票,它的"下一行"可能是好几个月之后另一段数据,甚至根本不存在。这个 bug 会让退市股票的最后一个月凭空多出一个来路不明的收益,而恰恰是这批标的的收益最极端。

他要先定一个全公司统一的口径,写进数据字典,然后才允许任何人提交因子。这道题对应业务问题 Q3。

**标签:** Window Function + Join | 难度: 基础 | 角色: Head of Data Engineering

**解题思路**

这题只需要两张表: `daily_bar` 提供复权价,`trading_calendar` 提供"哪天是月末"。先用 `is_month_end = 1` 把日频数据压成月频,这一步同时把 `month_index` 带出来 —— 它是这道题的关键。

然后用 `LEAD()` 窗口函数往后取一行。**核心在于不能盲信这一行。** 必须同时取出 `LEAD(month_index)`,并检查它是否恰好等于 `month_index + 1`。只有相邻的两个月末,收益才有意义;一旦中间断了 (标的退市了、或者还没上市),就必须让结果为 NULL 而不是硬算。

`CASE WHEN ... THEN ... END` 在条件不满足时自然返回 NULL,不需要写 `ELSE NULL`。最后按 `obs_date` 聚合,把"有多少标的算得出前瞻收益、多少被丢弃"数出来,这是数据质量报告要的那两列。

注意 `WINDOW w AS (...)` 这个写法: 同一个窗口定义要用两次,抽出来命名可以避免复制粘贴出错。SQLite 3.25 以上支持。

**SQL**

```sql
WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b
    JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date, adj_close,
           LEAD(month_index) OVER w AS next_month_index,
           LEAD(adj_close)   OVER w AS next_adj_close
    FROM month_end_bar
    WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
)
SELECT obs_date,
       COUNT(*)                                              AS names_scored,
       SUM(CASE WHEN next_month_index = month_index + 1
                THEN 1 ELSE 0 END)                           AS names_with_fwd_return,
       COUNT(*) - SUM(CASE WHEN next_month_index = month_index + 1
                THEN 1 ELSE 0 END)                           AS names_dropped,
       ROUND(AVG(CASE WHEN next_month_index = month_index + 1
                THEN next_adj_close / adj_close - 1 END) * 100, 3) AS avg_fwd_return_pct
FROM fwd
WHERE obs_date <= '2026-06-30'
GROUP BY obs_date
ORDER BY obs_date;
```

**预期结果与业务结论**

返回 43 行 (每个月末一行)。列的含义: `names_scored` 是当月末有行情的标的数 (含 40 个跨资产 ETF 代理, 这条查询没有按 `asset_class_id` 过滤), `names_with_fwd_return` 是能算出合法前瞻收益的数量, `names_dropped` 是被正确丢弃的数量。

**不要只看前几行 —— 第一只退市股要到 2023-10 才出现, 窗口开头的 `names_dropped` 全是 0。** 挑四行看:

| obs_date | names_scored | names_with_fwd_return | **names_dropped** | avg_fwd_return_pct |
|----------|--------------|----------------------|-------------------|--------------------|
| 2022-12-30 (第一个月) | 1,240 | 1,240 | **0** | -1.051 |
| 2023-12-29 | 1,228 | 1,223 | **5** | 5.339 |
| 2024-01-31 (退市最密集) | 1,223 | 1,215 | **8** | -2.501 |
| 2026-06-30 (最后一个月) | 1,120 | 0 | **1,120** | NULL |

43 个月里有 **32 个月** 出现了非零的 `names_dropped` —— **正是当月退市的那批标的**, 每月几个到八个不等。在最后一个月末 (2026-06-30), `names_dropped` 等于全部标的数, 因为没有下一个月了。整个数据集因此只有 **42 个可用的月度 IC 观测**, 而不是 43 个。

`names_scored` 从 1,240 一路降到 1,120: 掉的正好是 120 只退市股, 40 个 ETF 代理自始至终都在。

**拿到结果之后:** 把这个 CTE 写进公司的数据字典, 作为提交因子的强制模板。任何一份因子提交, 如果 `names_dropped` 恒为 0, 就说明作者用了错误的 `LEAD`, 直接打回。

---

### Q2. 因子暴露的日常体检

**业务背景**

你是 Quantitative Research Analyst, 每天早上第一件事是看隔夜的因子计算管线跑得怎么样。今天早上 Atlas 的 10 个候选因子第一次全量落库, 你需要在把它们交给 Model Validation 之前做一次基础体检: 每个因子是不是覆盖了全部标的、z-score 有没有正确标准化、五分位是不是完整、**以及最容易被忽略的一项 —— 这个打分背后的数据到底有多陈旧**。

最后一项尤其重要。一个 `lag_convention = 'publish_date'` 的因子, 它的 `data_asof_date` 应该明显早于 `obs_date`; 如果它等于 `obs_date`, 说明有人在构造时忘了做 as-of 过滤 —— 那就是一个 look-ahead bug 已经溜进来了。这道题对应业务问题 Q3。

**标签:** Aggregation + Join | 难度: 基础 | 角色: Quantitative Research Analyst

**解题思路**

单表聚合加一次维表 join 就够了。`factor_exposure` 按 `(factor_id, obs_date)` 分组, join `factor` 只是为了把可读的 `code` 拿出来。

三个检查点各对应一列: `AVG(z_score)` 应该接近 0 (标准化的定义), `MIN/MAX(quintile)` 应该是 1 和 5 (分层完整), `JULIANDAY(obs_date) - JULIANDAY(data_asof_date)` 就是数据陈旧度。

SQLite 里日期是字符串, 相减必须先转成 `JULIANDAY`, 直接减会得到 NULL 或者奇怪的结果 —— 这是 SQLite 最常见的日期坑之一。

选一个具体的月末 (这里用 2026-05-29, 也就是倒数第二个调仓日) 而不是全窗口聚合, 因为体检要看的是"最新一期正不正常"。

**SQL**

```sql
SELECT f.code,
       fe.obs_date,
       COUNT(*)                          AS n_scored,
       ROUND(AVG(fe.z_score), 6)         AS avg_z,
       ROUND(AVG(fe.raw_value), 5)       AS avg_raw,
       MIN(fe.quintile)                  AS min_q,
       MAX(fe.quintile)                  AS max_q,
       ROUND(JULIANDAY(fe.obs_date) - JULIANDAY(fe.data_asof_date), 0) AS data_lag_days
FROM factor_exposure fe
JOIN factor f ON f.id = fe.factor_id
WHERE fe.obs_date = '2026-05-29'
GROUP BY f.code, fe.obs_date
ORDER BY data_lag_days DESC, f.code;
```

**这里刻意不加 `LIMIT`。** 体检要看的是"有没有哪个因子不对劲", 而不是"最差的几个"。加了 `LIMIT 8` 会把 6 个价格类因子整组截掉 —— 而这道题最重要的一列 (`data_lag_days` 分成两组) 恰恰只有把两组都看到才成立。**截断是体检类查询最常见的自欺方式。**

**预期结果与业务结论**

返回 16 行 (每个因子一行)。`n_scored` 全部是 1,080 (该月末在市的股票数), `avg_z` 全部约等于 0, `min_q` / `max_q` 是 1 和 5 —— 三项基础检查全过。

`data_lag_days` 干净地分成两组:

| data_lag_days | 因子数 | 是哪些 |
|---------------|--------|--------|
| **24 天** | 10 | `lag_convention = 'publish_date'` 的那批: ACC_QUALITY、DIV_GROWTH_5Y、EPS_REV_60D、FCF_MARGIN_TTM、MICRO_VALUE、NEWS_SENT_7D、PEAD_SUE、QUA_ROE、SEARCH_TREND、VAL_EP |
| **0 天** | 6 | `lag_convention = 'trade_date'` 的那批: LIQ_AMIHUD、MOM_12_1、SIZ_LOG_MCAP、STR_REV_5D、VOL_LOW_60D、VOL_SKEW_ADJ |

这和 `factor.lag_convention` 完全对应。如果哪个 `publish_date` 约定的因子出现 0 天滞后, 立刻停下来查它的构造代码 —— **那说明有人在构造时忘了做 as-of 过滤, 一个 look-ahead bug 已经溜进来了。**

**拿到结果之后:** 三项检查全过才提交给 Model Validation。任何一项异常, 因子退回研究员, 不进入验证队列 —— 验证组的产能很贵, 不能拿来做基础体检。

---

### Q3. 自己动手算 RankIC, 并和官方口径对账

**业务背景**

Head of Model Validation 在给新人做入职培训。她的第一课永远是同一件事: **不要相信任何你自己算不出来的数字。**

`factor_ic_monthly` 表里躺着现成的 RankIC, 但一个研究员如果只会读这张表, 他就永远不知道这个数是怎么来的, 也就永远发现不了口径出错。她要求每个新人第一周必须做一件事: **从最原始的 `factor_exposure` 和 `daily_bar` 出发, 自己算一遍 RankIC, 然后和官方值逐月对账。**

对账差异必须能解释。这道题对应业务问题 Q3。

**标签:** CTE + Window Function + 统计 | 难度: 中级 | 角色: Head of Model Validation

**解题思路**

分四层 CTE。第一二层就是 Q1 那个 `month_end_bar` + `fwd`, 直接复用。第三层 `paired` 把因子打分和前瞻收益按 `(asset_id, obs_date)` 配对起来。

第四层是关键: **Spearman 相关系数就是"先把两列各自转成排名, 再算 Pearson 相关"。** SQLite 没有内置的 `CORR()`, 但 Pearson 相关可以完全用聚合函数拼出来:

```
corr(x, y) = (AVG(xy) - AVG(x)AVG(y)) / (SQRT(AVG(x²) - AVG(x)²) × SQRT(AVG(y²) - AVG(y)²))
```

排名用 `PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY ...)`。按 `obs_date` 分区非常重要 —— IC 是 **横截面** 指标, 每个月单独算一次, 绝不能把 42 个月混在一起排名。

最后按差异绝对值降序排, 一眼就能看到最不吻合的月份。

**SQL**

```sql
WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
paired AS (
    SELECT fe.obs_date, fe.z_score, f2.fwd_ret
    FROM factor_exposure fe
    JOIN factor f  ON f.id = fe.factor_id
    JOIN fwd   f2  ON f2.asset_id = fe.asset_id AND f2.obs_date = fe.obs_date
    WHERE f.code = 'ACC_QUALITY' AND f2.fwd_ret IS NOT NULL
),
ranked AS (
    SELECT obs_date,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY z_score) AS rz,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY fwd_ret) AS rr
    FROM paired
),
my_ic AS (
    SELECT obs_date,
           (AVG(rz * rr) - AVG(rz) * AVG(rr))
           / (SQRT(AVG(rz * rz) - AVG(rz) * AVG(rz)) * SQRT(AVG(rr * rr) - AVG(rr) * AVG(rr)))
           AS rank_ic_recomputed
    FROM ranked GROUP BY obs_date
)
SELECT m.obs_date,
       ROUND(m.rank_ic_recomputed, 5) AS my_rank_ic,
       ROUND(i.rank_ic, 5)            AS official_rank_ic,
       ROUND(ABS(m.rank_ic_recomputed - i.rank_ic), 6) AS abs_diff
FROM my_ic m
JOIN factor_ic_monthly i ON i.obs_date = m.obs_date AND i.universe_id = 1
JOIN factor f ON f.id = i.factor_id AND f.code = 'ACC_QUALITY'
ORDER BY abs_diff DESC
LIMIT 5;
```

**预期结果与业务结论**

返回差异最大的 5 个月。**`abs_diff` 全部小于 0.00001** —— 最大的一个月是 0.000004。把同样的重算扩展到全部 16 个因子, 单月最大偏差也只有 **0.00038**。

**剩下那点差异是从哪来的?** 官方口径用的是 `rank(method="average")`, 遇到并列值取平均名次; 而 `PERCENT_RANK()` 的并列处理略有不同。在 1,000 多个标的、几乎没有真正并列的横截面上, 这点差异可以忽略。

**这个结果本身就是本数据集的一个核心承诺: `factor_ic_monthly` 完全可以从 `factor_exposure` 加 `daily_bar` 重建出来。** 官方口径没有任何黑箱 —— 前瞻收益就是月末复权价到下月末复权价的总收益, 不做任何 beta 调整, 不做任何 winsorize。

**拿到结果之后:** 如果你的重算和官方值差出 0.01 以上, 别急着报 bug, 先检查三件事: (a) 前瞻收益是不是漏了 `month_index + 1` 的连续性检查; (b) `PERCENT_RANK` 是不是按 `obs_date` 分区了; (c) 用的是不是 `adj_close` 而不是 `close_price`。这三条覆盖了 90% 的对账失败。

---

### Q4. 因子库总览: IC 汇总统计

**业务背景**

Head of Quantitative Research 要在周一的研究例会上过一遍整个因子库的状态: 6 个生产因子、10 个 Atlas 候选因子, 一共 16 个, 每个的 RankIC 均值、稳定性、显著性、胜率各是多少。

这张表是他排优先级的唯一依据: **ICIR 高的先看, ICIR 低的直接跳过。** 他不想看 16 份分开的报告, 他要一张能排序的表。这道题对应业务问题 Q2。

**标签:** Aggregation + 统计 | 难度: 中级 | 角色: Head of Quantitative Research

**解题思路**

只查 `factor_ic_monthly` 一张表, 但要在 SQL 里手工拼出样本标准差 —— **SQLite 没有 `STDDEV()`**。

总体标准差可以用 `SQRT(AVG(x²) - AVG(x)²)` 算出来, 但统计上我们要的是 **样本** 标准差 (分母 n-1 而不是 n)。所以要乘一个贝塞尔修正因子 `SQRT(n / (n-1))`。这个细节在 42 个样本上影响约 1.2%, 看起来不大, 但 t 统计量恰好在门槛附近时就会改变结论。

ICIR = IC 均值 ÷ IC 标准差 (**本数据集统一不年化**)。t 统计量 = ICIR × √n。胜率就是 IC 为正的月份占比。

`WHERE universe_id = 1` 必须写 —— 不加的话三个池子的数据会混在一起, 每个因子变成 126 个月而不是 42 个。

**SQL**

```sql
SELECT f.code,
       f.status,
       COUNT(*)                                              AS n_months,
       ROUND(AVG(i.rank_ic), 4)                              AS ic_mean,
       ROUND(SQRT(AVG(i.rank_ic * i.rank_ic) - AVG(i.rank_ic) * AVG(i.rank_ic))
             * SQRT(COUNT(*) * 1.0 / (COUNT(*) - 1)), 4)     AS ic_std,
       ROUND(AVG(i.rank_ic)
             / (SQRT(AVG(i.rank_ic * i.rank_ic) - AVG(i.rank_ic) * AVG(i.rank_ic))
                * SQRT(COUNT(*) * 1.0 / (COUNT(*) - 1))), 3) AS icir,
       ROUND(AVG(i.rank_ic)
             / (SQRT(AVG(i.rank_ic * i.rank_ic) - AVG(i.rank_ic) * AVG(i.rank_ic))
                * SQRT(COUNT(*) * 1.0 / (COUNT(*) - 1)))
             * SQRT(COUNT(*)), 2)                            AS ic_tstat,
       ROUND(100.0 * SUM(CASE WHEN i.rank_ic > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS hit_rate_pct
FROM factor_ic_monthly i
JOIN factor f ON f.id = i.factor_id
WHERE i.universe_id = 1
GROUP BY f.code, f.status
ORDER BY icir DESC;
```

**预期结果与业务结论**

返回 16 行, 按 ICIR 降序。所有因子的 `n_months` 都是 42。

**ICIR 的分布很说明问题:** 最高的 `FCF_MARGIN_TTM` 是 0.99, 最低的 `DIV_GROWTH_5Y` 是 0.24。**0.3 以下基本可以不用看了; 0.5 以上算好因子。** 生产因子库的 6 个都落在 0.38 到 0.53 之间 (最低的是 QUA_ROE 0.38, 最高的是 LIQ_AMIHUD 0.53) —— 这是一个成熟因子库的正常水平, 说明它们既不是垃圾, 也没有任何一个是印钞机。

**留意 `FCF_MARGIN_TTM` 高居榜首 (ICIR 0.99, t 6.39, 胜率 83.3%)。** 一个候选因子在所有常规统计量上碾压全部 6 个生产因子, 这本身就该让人警觉 —— 天上不会掉这么大的馅饼。Q19 会告诉你它到底是怎么回事。

**拿到结果之后:** 把 ICIR 高于 0.4 的因子排进深度检验队列, 低于 0.3 的直接归档。但 **ICIR 高不等于可以上线** —— 后面还有成本、容量、正交性、数据完整性四道关。

---

### Q5. 分层单调性检验

**业务背景**

你正在准备 `ACC_QUALITY` 的提交材料。Head of Model Validation 有一条硬规定: **只有 IC 是不够的, 必须同时看分层。**

理由是 IC 只衡量线性单调关系的强度, 它对"两头有效、中间无效"或者"只有最高一层有效"这类形态毫无分辨力。而这两类形态在实盘里表现完全不同: 前者可以做多空, 后者只能做多头且容量极小。

你顺便把 `VOL_SKEW_ADJ` 也一起跑了 —— 这是 Atlas 提的另一个因子, 你想看看它和 `ACC_QUALITY` 的分层形态有什么区别。这道题对应业务问题 Q2。

**标签:** Aggregation + Join | 难度: 基础 | 角色: Quantitative Research Analyst

**解题思路**

`factor_exposure` 已经算好了 `quintile`, 所以不需要自己分层, 直接按它分组即可。

关键在于 join 的方向: `factor_exposure` 是左表 (它定义了"哪些标的在哪个月被打了分"), `fwd` 用 INNER JOIN 接上去。**这里用 INNER JOIN 是对的** —— 没有前瞻收益的观测 (最后一个月、退市当月) 本来就不该进入统计, 不像 Q13 那种场景需要 LEFT JOIN 保留全集。

`AVG(fwd_ret) * 1200` 把月度收益折算成年化百分比: 乘 12 变年化, 再乘 100 变百分数。把 `avg_z` 一起选出来, 是为了确认分层本身没问题 —— Q1 到 Q5 的平均 z 应该从约 -1.4 单调升到约 +1.4。

**SQL**

```sql
WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
)
SELECT f.code, fe.quintile,
       COUNT(*)                                   AS n_obs,
       ROUND(AVG(fw.fwd_ret) * 1200, 2)           AS ann_return_pct,
       ROUND(AVG(fe.z_score), 3)                  AS avg_z
FROM factor_exposure fe
JOIN factor f  ON f.id = fe.factor_id
JOIN fwd   fw  ON fw.asset_id = fe.asset_id AND fw.obs_date = fe.obs_date
WHERE f.code IN ('ACC_QUALITY', 'VOL_SKEW_ADJ') AND fw.fwd_ret IS NOT NULL
GROUP BY f.code, fe.quintile
ORDER BY f.code, fe.quintile;
```

**预期结果与业务结论**

返回 10 行 (2 个因子 × 5 层), 每层约 9,600 个观测。

**`ACC_QUALITY` 的分层是漂亮的单调递增:** 8.80% → 8.57% → 10.99% → 12.71% → **17.23%**。Q1 到 Q2 略微反了一点点, 但幅度在噪声范围内, Q3 往上非常干净, **Q5 - Q1 = 8.4pp**。

**`VOL_SKEW_ADJ` 的分层也是单调的:** 8.86% → 10.02% → 12.06% → 12.35% → 15.01%, Q5 - Q1 = 6.2pp。**它的形态没有任何问题。** 这一点很重要 —— Q17 会证明这个因子该被否决, 但否决的理由不是分层, 而是它和已有因子重复。**一个因子可以在分层上完美无瑕, 同时毫无价值。**

**拿到结果之后:** 分层单调是提交的必要条件, 不是充分条件。`ACC_QUALITY` 通过这一关, 继续往下走成本和正交性检验。

---

### Q6. 换手率与单位交易成本

**业务背景**

Head of Trading 每个季度要给研究部门出一份"成本预算表": 每个因子如果上线, 按当前的资金规模, 一年大概要付多少交易成本。

研究员提交因子时经常只报毛收益, 而他知道 **成本可以差出一个数量级** —— 一个季度才变一次的会计类因子, 和一个几乎每月重排的短期反转因子, 完全不是一门生意。他需要把"换手率"和"单位成本"这两个乘数分开看, 才能判断问题出在哪一边。这道题对应业务问题 Q4。

**标签:** 多 CTE + Join | 难度: 中级 | 角色: Head of Trading

**解题思路**

成本 = 换手 × 单位成本, 所以要分别算两块, 用两个 CTE。

`basket` CTE 从 `factor_ic_monthly` 取月度换手。**注意 `c.month_index > 0` 这个过滤**: 第一个观测月没有上月可比, 换手率恒为 1.0, 不排除掉会把所有因子的平均换手抬高约 2%。

`spread` CTE 算多空篮子实际要交易的那批标的的平均价差和 ADV。**这里必须过滤 `quintile IN (1, 5)`** —— 你只交易两头, 中间三层的价差和你无关。join `daily_bar` 时用 `(asset_id, trade_date = obs_date)` 精确对上月末那一天。

年化双边换手 = 月度换手 × 12 × 2 (多空两腿都要换)。最后把官方口径的 `annual_turnover` 和 `cost_bps_annual` 并排放上去做对照 —— 官方值额外乘了一个调仓频率系数, 对衰减快的信号大于 1。

**SQL**

```sql
WITH basket AS (
    SELECT f.code, i.obs_date, i.monthly_turnover
    FROM factor_ic_monthly i
    JOIN factor f ON f.id = i.factor_id
    JOIN trading_calendar c ON c.trade_date = i.obs_date
    WHERE i.universe_id = 1 AND c.month_index > 0
),
spread AS (
    SELECT f.code,
           AVG(b.bid_ask_spread_bps) AS avg_spread_bps,
           AVG(b.adv_20d_usd)        AS avg_adv_usd
    FROM factor_exposure fe
    JOIN factor f ON f.id = fe.factor_id
    JOIN daily_bar b ON b.asset_id = fe.asset_id AND b.trade_date = fe.obs_date
    WHERE fe.quintile IN (1, 5)
    GROUP BY f.code
)
SELECT b.code,
       ROUND(AVG(b.monthly_turnover), 4)                        AS avg_monthly_turnover,
       ROUND(AVG(b.monthly_turnover) * 24, 1)                   AS annual_two_way_turnover,
       ROUND(s.avg_spread_bps, 1)                               AS basket_spread_bps,
       ROUND(s.avg_adv_usd / 1e6, 1)                            AS basket_adv_usd_mm,
       ROUND(0.5 * s.avg_spread_bps + 1.0, 2)                   AS cost_floor_bps_per_unit,
       v.annual_turnover                                        AS official_annual_turnover,
       v.cost_bps_annual                                        AS official_cost_bps
FROM basket b
JOIN spread s ON s.code = b.code
JOIN factor f ON f.code = b.code
JOIN factor_validation_run v ON v.factor_id = f.id AND v.universe_id = 1 AND v.window_type = 'FULL'
GROUP BY b.code, s.avg_spread_bps, s.avg_adv_usd, v.annual_turnover, v.cost_bps_annual
ORDER BY annual_two_way_turnover DESC
LIMIT 6;
```

**预期结果与业务结论**

返回换手最高的 6 个因子。

**换手率的跨度接近 85 倍:** `STR_REV_5D` 月度换手 0.787 (每个月 Q5 篮子里近 79% 是新面孔), 本查询口径下年化双边 **18.9** 倍; 而 `SIZ_LOG_MCAP` (未进前 6) 只有 **0.2** 倍 —— 市值排名一年也动不了几名。按官方 `annual_turnover` 那一列 (它不排除首月) 是 22.8 对 0.8, 跨度 29 倍。**两个跨度都对, 差别就在排不排除首月, 而首月对低换手因子的影响大得多。**

**篮子的价差和 ADV 反而非常接近** (各因子都在 29 bps 和 5,400 万美元附近)。这说明 **成本的差异几乎完全来自换手率, 而不是标的选择** —— 各因子的多空篮子在流动性特征上没有系统性差别。

`official_annual_turnover` 对 `STR_REV_5D` 是 22.8 而不是 18.9, 差的那部分就是调仓频率系数 1.2: **一个 5 日信号按月持有会浪费掉大部分 alpha, 实践中必须更频繁地调仓。**

**拿到结果之后:** 换手超过 15 倍的因子, 在提交时必须附带成本后 IR, 否则不予受理。这条规则直接来自这张表。

---

### Q7. 数据覆盖度与退市节奏

**业务背景**

Head of Data Engineering 要给研究部门出一份"池子稳定性"报告。研究员经常默认股票池是恒定的, 但实际上每个月都有标的在消失。

他特别关心 **退市集中的月份**: 如果某个月一口气掉了 8 只标的, 那个月的横截面统计量就会比平时更脆弱, 而且如果研究员用的是"今天还活着的名单"回溯历史, 这 8 只的收益就被整段抹掉了。他要把这些月份标出来, 提醒研究部门。这道题对应业务问题 Q3。

**标签:** Aggregation + 日期函数 | 难度: 基础 | 角色: Head of Data Engineering

**解题思路**

三表 join: `daily_bar` 提供月末快照, `trading_calendar` 筛出月末, `asset` 提供退市日。

"下个月要退市的数量"用条件计数实现: `delisted_date` 落在 `(当前月末, 当前月末 + 35 天]` 这个区间内。**为什么是 35 天而不是 30 天?** 因为月末之间的实际间隔在 28 到 31 天不等, 加上缓冲避免漏掉月底退市的标的。这是 SQLite 里 `DATE(x, '+35 day')` 的典型用法。

`HAVING delisting_next_month > 0` 只保留有退市发生的月份。注意 `HAVING` 里可以直接引用 SELECT 里的别名 —— 这是 SQLite 的方言特性, 换成 PostgreSQL 要写完整表达式。

**SQL**

```sql
SELECT c.year_month,
       COUNT(DISTINCT b.asset_id)                                              AS live_names,
       SUM(CASE WHEN a.delisted_date IS NOT NULL
                 AND a.delisted_date <= DATE(c.trade_date, '+35 day')
                 AND a.delisted_date >  c.trade_date
                THEN 1 ELSE 0 END)                                             AS delisting_next_month,
       ROUND(AVG(b.market_cap_usd_mm), 0)                                      AS avg_mcap_usd_mm,
       ROUND(AVG(b.bid_ask_spread_bps), 2)                                     AS avg_spread_bps,
       ROUND(SUM(b.adv_20d_usd) / 1e9, 1)                                      AS total_adv_usd_bn
FROM daily_bar b
JOIN trading_calendar c ON c.trade_date = b.trade_date
JOIN asset a           ON a.id = b.asset_id
WHERE c.is_month_end = 1 AND a.asset_class_id = 1
GROUP BY c.year_month
HAVING delisting_next_month > 0
ORDER BY delisting_next_month DESC
LIMIT 6;
```

**预期结果与业务结论**

返回退市最集中的 6 个月:

| year_month | live_names | delisting_next_month | avg_mcap | avg_spread |
|------------|-----------|---------------------|----------|------------|
| 2025-06 | 1,111 | **8** | 7,596 | 28.73 |
| 2024-04 | 1,168 | **8** | 6,392 | 30.30 |
| 2024-01 | 1,183 | **8** | 6,435 | 30.17 |
| 2025-05 | 1,117 | 7 | 7,157 | 29.65 |
| 2024-12 | 1,138 | 7 | 6,888 | 30.05 |
| 2024-11 | 1,144 | 7 | 6,085 | 31.79 |

**注意这六行不是按时间排的, 是按退市数排的** (`ORDER BY delisting_next_month DESC`)。所以不要把它们读成一条时间趋势 —— 这里能看到的只是"最集中的三个月各掉了 8 只标的"。

**想看趋势要另外查 (去掉 `HAVING` 和 `LIMIT`, 改成 `ORDER BY c.year_month`):** `live_names` 从 2022-12 的 **1,200** 一路降到 2026-06 的 **1,080** —— **三年半里池子缩水了整整 10%**, 这就是幸存者偏差的物理来源。同一条时间序列上, `avg_mcap_usd_mm` 从 6,902 涨到 9,442 (市场上涨), `avg_spread_bps` 从 28.42 降到 26.82 (流动性随市值改善)。

**拿到结果之后:** 把这几个高退市月份标进研究部门的共享日历。任何一个在这些月份出现异常 IC 的因子, 第一件要排查的事就是它是不是在做多正在死掉的公司 —— Q14 会把这件事做到底。

---
### Q8. PIT 发布滞后与财报修订率

**业务背景**

Head of Data Engineering 要在数据治理评审上量化两件事, 因为研究部门反复在这两件事上踩坑:

**第一, 财报公布到底滞后多久。** 研究员写 join 条件时如果用了 `fiscal_period_end`, 到底会偷看多少天的未来? 这个数字必须写进培训材料。

**第二, 有多少财报事后被修订过。** 数据仓库默认只返回最新版本 —— 如果修订比例很低, 这个默认无伤大雅; 如果比例很高, 那所有用了基本面的因子都要重新审一遍。

这道题对应业务问题 Q3。

**标签:** Aggregation + UNION ALL | 难度: 基础 | 角色: Head of Data Engineering

**解题思路**

主体是按 `version` 分组的一次聚合。滞后天数用 `JULIANDAY(publish_date) - JULIANDAY(fiscal_period_end)`, 同时取均值、最小值、最大值 —— 只看均值会掩盖分布的形状。

`ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)` 是一个值得记住的写法: **在聚合结果之上再套一个空窗口 `OVER ()`**, 就能拿到"全部分组的总和", 从而算出占比。不需要额外的子查询。

第二个问题 (多少 **公司** 会修订, 而不是多少 **行** 是修订) 粒度不同, 所以用 `UNION ALL` 追加一行, 用 `COUNT(DISTINCT asset_id)` 统计。UNION ALL 要求列数对齐, 用不上的列填 NULL。

**SQL**

```sql
SELECT CASE WHEN fr.version = 1 THEN 'v1_original' ELSE 'v2_restated' END AS filing_version,
       COUNT(*)                                                            AS n_filings,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)                  AS pct_of_all,
       ROUND(AVG(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end)), 1) AS avg_lag_days,
       MIN(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end))   AS min_lag_days,
       MAX(JULIANDAY(fr.publish_date) - JULIANDAY(fr.fiscal_period_end))   AS max_lag_days,
       ROUND(AVG(fr.fcf_margin_ttm), 5)                                    AS avg_fcf_margin
FROM fundamental_report fr
GROUP BY filing_version
UNION ALL
SELECT 'companies_that_restate', COUNT(DISTINCT asset_id),
       ROUND(100.0 * COUNT(DISTINCT asset_id)
             / (SELECT COUNT(DISTINCT asset_id) FROM fundamental_report), 1),
       NULL, NULL, NULL, NULL
FROM fundamental_report WHERE version = 2;
```

**预期结果与业务结论**

返回 3 行:

| filing_version | n_filings | pct_of_all | avg_lag_days | min_lag | max_lag |
|----------------|-----------|-----------|--------------|---------|---------|
| v1_original | 15,915 | 80.7% | **29.9** | 19 | 41 |
| v2_restated | 3,809 | **19.3%** | 134.0 | 97 | 172 |
| companies_that_restate | 316 家 | **26.3%** | - | - | - |

**第一个数字 29.9 天就是 look-ahead 陷阱的大小。** 用 `fiscal_period_end` 做 as-of 过滤, 平均偷看一个月的未来。区间 19 到 41 天与美股实际情况吻合 (SEC 对大型加速申报人的 10-Q 截止是 40 天)。

**第二个数字更让人不安: 26.3% 的公司有过修订。** 这不是一个可以忽略的边角案例 —— 四分之一的公司会让"最新版"和"当时看到的版本"不一致。修订版平均在财季结束后 134 天才出现, 也就是说, 在原始版公布后又过了三个多月。

**拿到结果之后:** 立刻在数据字典里加两条强制规则: (a) 所有基本面 join 必须用 `publish_date`; (b) 所有回测必须显式声明用的是 `version = 1` 还是最新版。Q13 和 Q19 分别量化这两条规则被违反的代价。

---

### Q9. 市场 regime 时间线

**业务背景**

Chief Risk Officer 在准备季度风险委员会材料。她需要一张最基础的表: 这三年半分成了几个市场环境, 每个环境持续多久, 各自的波动、利差、相关性水平是什么样。

**这张表是后面所有 regime 拆分分析的地基。** 如果某个 regime 只有三四个月, 那么在它上面算出来的任何因子统计量都不可信 —— 她必须先知道每一段有多长, 才能判断后面的结论有多少分量。这道题对应业务问题 Q5。

**标签:** Aggregation + LEFT JOIN | 难度: 基础 | 角色: Chief Risk Officer

**解题思路**

三表 join 加一次可选 join。`market_regime_day` 是主表, `trading_calendar` 提供 `year_month` 用来数月份, `regime_type` 提供可读名称。

`covariance_estimate` 用 **LEFT JOIN** 接上去, 因为它只在月末有数据, 而 `market_regime_day` 是日频的。用 INNER JOIN 会把非月末的日子全部丢掉, 导致 `avg_vix` 只反映月末那一天 —— 这是这道题唯一的坑。同时要加 `AND cv.method = 'ledoit_wolf'` 限定一种方法, 否则四种方法的相关系数会被重复计入。

`COUNT(DISTINCT c.year_month)` 而不是 `COUNT(*)`, 因为要数的是月份数不是交易日数。

**SQL**

```sql
SELECT r.code AS regime,
       MIN(c.year_month) AS first_month,
       MAX(c.year_month) AS last_month,
       COUNT(DISTINCT c.year_month) AS n_months,
       ROUND(AVG(m.vix_proxy), 1)         AS avg_vix,
       ROUND(AVG(m.term_spread_bp), 1)    AS avg_term_spread_bp,
       ROUND(AVG(m.credit_spread_bp), 1)  AS avg_credit_spread_bp,
       ROUND(AVG(cv.avg_pairwise_corr), 3) AS avg_pairwise_corr
FROM market_regime_day m
JOIN trading_calendar c ON c.trade_date = m.trade_date
JOIN regime_type r      ON r.id = m.regime_type_id
LEFT JOIN covariance_estimate cv ON cv.as_of_date = m.trade_date AND cv.method = 'ledoit_wolf'
GROUP BY r.code
ORDER BY avg_vix DESC;
```

**预期结果与业务结论**

返回 4 行, 按平均 VIX 降序:

| regime | 区间 | 月数 | avg_vix | 期限利差 bp | 信用利差 bp | 平均两两相关 |
|--------|------|------|---------|------------|------------|-------------|
| HIGH_VOL_STRESS | 2024-08 至 2025-03 | **8** | 32.3 | 24.5 | **387.9** | **0.585** |
| RISING_RATE | 2025-04 至 2025-11 | 8 | 20.3 | **-34.8** | 174.4 | 0.335 |
| RECOVERY | 2022-12 至 2023-10 | 11 | 16.9 | 61.4 | 146.9 | 0.264 |
| LOW_VOL_BULL | 2023-11 至 2026-06 | **16** | 12.4 | 88.8 | 102.6 | 0.191 |

**先看一眼"区间"这一列的坑。** `LOW_VOL_BULL` 显示成 "2023-11 至 2026-06",看起来是连续 32 个月,但 `n_months` 只有 16 —— 因为它其实是 **两段**: 2023-11 至 2024-07,以及 2025-12 至 2026-06,中间隔着 HIGH_VOL_STRESS 和 RISING_RATE。**`MIN` / `MAX` 天生描述不了不连续的区间**,它只会给你一个横跨全部空洞的外包络。想看真实的分段,得先用窗口函数做 gaps-and-islands (相邻月份 regime 变了就开一段新的)。这是聚合函数最常见的一类误读,记住它比记住这张表本身更有用。

四个 regime 的画像各自自洽: 压力期 VIX 32、信用利差走阔到 388 bp、**平均两两相关系数飙到 0.585** (分散化在最需要的时候失效, 这是压力期的教科书特征); 加息期期限利差倒挂到 -34.8 bp。

**最短的一段是 8 个月。** 这意味着任何 regime 拆分的结论都建立在 8 个观测上, **标准误约 IC_std / √8 ≈ 0.02**。这个精度足够识别符号翻转, 但不足以精确估计幅度。

**拿到结果之后:** 把"regime 拆分的最小样本 = 8 个月"写进方法论文档。Q16 的结论要在这个前提下解读: 我们能说"符号翻了", 但不能说"翻了多少"。

---

### Q10. 研究组合持仓画像与约束顶格

**业务背景**

Director of Portfolio Construction 拿到了 Atlas 的复合信号 paper 组合, 要在投委会上回答一个具体问题: **"如果我们真按这个信号投, 组合会长什么样, 哪些地方被约束卡住了?"**

他特别关心 `is_constraint_binding` 那一列。**每一个被卡住的位置, 都是模型想多买但规则不让的地方 —— 也就是 alpha 具体流失的现场。** 如果卡住的全是单票上限, 说明信号过度集中; 如果卡住的全是流动性约束, 说明信号在往小票上跑。两种情况的处方完全不同。这道题对应业务问题 Q5。

**标签:** Aggregation + 条件计数 | 难度: 中级 | 角色: Director of Portfolio Construction

**解题思路**

单表聚合, 但用了几个值得学的模式。

**条件计数** `SUM(CASE WHEN 条件 THEN 1 ELSE 0 END)` 比 `COUNT(CASE WHEN ...)` 更明确, 而且不受 NULL 影响。这里用它把两类约束分开数。

**Active Share** 是主动管理里最常引用的一个指标: `SUM(ABS(active_weight)) / 2`。除以 2 是因为超配和低配会重复计一次同一笔偏离。它衡量"组合有多不像基准", 40% 以下通常被认为是"抱着指数收费"。

`SUM(weight)` 拿出来是一个自检项 —— 应该恒等于 1。

只看最近 6 个月 (`>= '2026-01-01'`), 因为这是投委会关心的当前状态, 不是历史。

**SQL**

```sql
SELECT h.as_of_date,
       COUNT(*)                                                       AS n_holdings,
       ROUND(SUM(h.weight), 4)                                        AS total_weight,
       ROUND(MAX(h.weight) * 100, 3)                                  AS max_weight_pct,
       SUM(h.is_constraint_binding)                                   AS n_binding,
       SUM(CASE WHEN h.binding_constraint_code = 'MAX_ASSET_WEIGHT'
                THEN 1 ELSE 0 END)                                    AS n_cap_binding,
       SUM(CASE WHEN h.binding_constraint_code = 'MAX_ADV_PARTICIPATION'
                THEN 1 ELSE 0 END)                                    AS n_adv_binding,
       ROUND(SUM(ABS(h.active_weight)) / 2 * 100, 2)                  AS active_share_pct
FROM portfolio_holding h
WHERE h.portfolio_id = 3 AND h.as_of_date >= '2026-01-01'
GROUP BY h.as_of_date
ORDER BY h.as_of_date;
```

**预期结果与业务结论**

返回 6 行, 每月一行。`n_holdings` 恒为 180, `total_weight` 恒为 1.0 —— 自检通过。

**关键发现: `n_cap_binding` 全部是 0, 所有顶格都是 `n_adv_binding`。** 最大单票权重在 1.60% 到 1.96% 之间波动, **这 6 个月里一次都没有触及 2.5% 的上限**。也就是说, 约束这个组合的不是集中度, 而是 **流动性** —— 每个月有 4 到 12 只票, 模型想要的仓位超过了它们 5% ADV 所能支撑的规模。

**这个结论在全窗口上也成立, 但要说得更准一点。** 全部 43 个月 7,740 行里, `MAX_ADV_PARTICIPATION` 顶格 **414 次**, `MAX_ASSET_WEIGHT` 只顶格 **1 次**。**不要把"我查的 6 个月里是 0"直接说成"从来没有"** —— 加一句范围限定, 或者干脆去掉 `WHERE` 再查一遍。结论性的措辞比查询本身更容易出错。

`active_share_pct` 在 41.8% 到 44.5% 之间, 说明组合和基准有实质性差异, 不是伪主动管理。

**拿到结果之后:** 处方很明确 —— **不要放宽单票上限 (它根本没绑住), 要么把池子往大市值收窄, 要么接受这部分 alpha 拿不到。** Q18 会告诉你为什么这个问题在某些因子上会严重得多。

---

## 第二部分: 分析性查询 (Q11 - Q22)

前十条把地基打好了。接下来这十二条负责真正回答业务问题 —— **哪些因子该推进、哪些该否决、否决的证据是什么。**

其中 Q13 到 Q19 这七条是本数据集的核心。**它们每一条都在演示同一件事: 同一个因子, 换一种正确的问法, 结论就翻盘。**

---

### Q11. 成本前后 IR 全景: alpha 被吃掉了多少

**业务背景**

Head of Trading 和 Head of Quantitative Research 在为一件事争执: 研究部门提交因子时报的是毛收益, 而交易台看到的是净收益, 两边说的从来不是一个数。

CIO 让他们各退一步, 先做一张所有人都认的表: **16 个因子, 每个的毛收益、成本、净收益、以及成本吃掉了 IR 的百分之几**, 按侵蚀比例排序。这张表会成为以后所有因子提交的标准附件。这道题对应业务问题 Q4。

**标签:** Aggregation + 派生指标 | 难度: 中级 | 角色: Head of Trading

**解题思路**

数据全在 `factor_validation_run` 里, 这题的重点不是 join 而是 **派生指标的构造**。

`ir_eroded_pct = 100 × (gross_ir - net_ir) / gross_ir` 是本题的主角。用比例而不是绝对差值, 是因为不同因子的 IR 量级差很多, 绝对差没有可比性。

`WHERE gross_ir > 0` 这个过滤必须有 —— 毛 IR 为负或为零时, 侵蚀比例这个指标没有意义 (分母为零或符号翻转会给出荒唐的数字)。这是一个典型的"派生指标要保护分母"的场景。

成本从 bps 转成百分数要除以 100, 从 bps 转成小数要除以 10000, 这两个换算在同一条 SQL 里都出现了, 容易写错。

**SQL**

```sql
SELECT f.code, f.status,
       ROUND(v.q5_q1_annual_return * 100, 2)                      AS gross_ann_pct,
       ROUND(v.cost_bps_annual / 100.0, 2)                        AS cost_ann_pct,
       ROUND((v.q5_q1_annual_return - v.cost_bps_annual / 10000.0) * 100, 2) AS net_ann_pct,
       ROUND(v.annual_turnover, 1)                                AS annual_turnover,
       ROUND(v.gross_ir, 2)                                       AS gross_ir,
       ROUND(v.net_ir, 2)                                         AS net_ir,
       ROUND(100.0 * (v.gross_ir - v.net_ir) / v.gross_ir, 1)     AS ir_eroded_pct
FROM factor_validation_run v
JOIN factor f ON f.id = v.factor_id
WHERE v.universe_id = 1 AND v.window_type = 'FULL' AND v.gross_ir > 0
ORDER BY ir_eroded_pct DESC;
```

**预期结果与业务结论**

返回 16 行, 按侵蚀比例降序。**这是全文档信息量最大的一张表之一:**

| code | 毛收益% | 成本% | 净收益% | 年换手 | 毛 IR | 净 IR | **IR 侵蚀%** |
|------|---------|-------|---------|--------|-------|-------|-------------|
| NEWS_SENT_7D | 3.35 | 5.27 | **-1.92** | 20.5 | 0.65 | **-0.37** | **157.3** |
| SEARCH_TREND | 5.82 | 3.61 | 2.21 | 14.0 | 1.40 | 0.53 | 62.0 |
| **STR_REV_5D** | 11.66 | 5.86 | 5.80 | **22.8** | 1.67 | **0.83** | **50.3** |
| MOM_12_1 | 6.48 | 2.43 | 4.06 | 9.4 | 1.16 | 0.73 | 37.4 |
| ... | | | | | | | |
| ACC_QUALITY | 8.36 | 1.44 | 6.91 | 5.5 | 1.30 | **1.07** | **17.3** |
| FCF_MARGIN_TTM | 10.09 | 1.29 | 8.80 | 5.1 | 3.01 | 2.62 | 12.8 |
| SIZ_LOG_MCAP | 4.23 | 0.20 | 4.03 | 0.8 | 1.34 | 1.28 | **4.7** |

**三条结论一目了然:**

1. **`NEWS_SENT_7D` 的成本 (5.27%) 超过了它的毛收益 (3.35%)** —— 侵蚀 157.3%, 净 IR 是负的。这个因子交易得越多亏得越多。
2. **`STR_REV_5D` 是最有教学价值的一行:** 毛收益 11.66% 相当可观, 毛 IR 1.67 看着很健康, 但 22.8 倍的年换手带来 5.86% 的成本, **一半的 alpha 直接消失**。它仍然可用, 但必须限规模。
3. **但"换手率就是成本的全部"这句话是错的 —— 这张表自己就能推翻它。** 换手最高的 `STR_REV_5D` (22.8 倍) 侵蚀 50.3%,只排第三;换手 20.5 倍的 `NEWS_SENT_7D` 却侵蚀 157.3%;而换手只有 4.2 倍的 `DIV_GROWTH_5Y` 侵蚀 35.0%,**比换手是它 1.6 倍的 `VOL_SKEW_ADJ` (6.9 倍 / 28.5%) 还高**。
   真正的等式是:

   ```
   IR 侵蚀比例 = 成本 ÷ 毛收益 = (换手 × 单位成本) ÷ 毛收益
   ```

   **换手只是分子的一半, 分母同样重要。** `NEWS_SENT_7D` 之所以爆表, 是因为它的毛收益只有 3.35% —— 分母太小; `DIV_GROWTH_5Y` 同理 (毛收益 3.12%)。反过来 `PEAD_SUE` 换手 12.5 倍却只侵蚀 25.4%, 因为它的毛收益有 12.77% 顶着。**看到一个高侵蚀比例, 先问是分子太大还是分母太小 —— 两者的处方完全不同: 前者降调仓频率, 后者直接放弃。**

**拿到结果之后:** 把"IR 侵蚀 > 40%"设为红线。越线的因子要么限规模、要么降调仓频率、要么不上。`NEWS_SENT_7D` 直接出局 —— 它连 Q16 的 regime 检验都不用做就已经死了。

---

### Q12. 成本敏感性: 价差翻倍会怎样

**业务背景**

Chief Risk Officer 在压力测试的框架下问了 Head of Trading 一个问题: **"2024 年 8 月那种压力期, 买卖价差普遍走阔到平时的一倍半到两倍。如果那种环境再来一次, 我们的因子还剩多少?"**

这不是假设性问题。压力期恰恰是流动性最差、而模型信号最想调仓的时候 —— 两件事叠在一起, 成本会以非线性的方式爆炸。她要一张情景表: 基准、价差 ×1.5、价差 ×2 三种情况下, 三个代表性因子的净 IR 各是多少。这道题对应业务问题 Q4。

**标签:** CROSS JOIN + 情景计算 | 难度: 高级 | 角色: Head of Trading

**解题思路**

这是本文档唯一用到 **`VALUES` 构造情景表 + `CROSS JOIN` 展开** 的查询, 值得学。

`WITH scenarios(scenario, spread_multiplier) AS (VALUES ('base', 1.0), ...)` 在 SQL 里凭空造出一张三行的表。然后 `CROSS JOIN` 让它和因子篮子做笛卡尔积, 三个情景 × 三个因子 = 九行。**这个模式适用于任何"同一份数据跑多组参数"的需求**, 比写三遍 UNION 干净得多。

成本公式必须原地重算 (不能用 `factor_validation_run` 里现成的 `cost_bps_annual`, 那是基准情景的值):

```
cost_per_unit = 0.5 × spread × mult  +  0.55 × spread × mult × sqrt(participation)  +  1.0
```

其中 `participation = min(3000mm × 1e6 / basket_n / adv_usd, 1.5)`。**注意冲击成本那一项里 `spread × mult` 出现了两次** —— 价差走阔既抬高半价差, 也抬高冲击成本, 这是它杀伤力大的原因。

**`basket_n` 这一行是本题最容易写错的地方。** 它要的是"多空篮子里有多少只票", 也就是 **每个月** Q1 加 Q5 的平均只数。正确写法是 `COUNT(*) / COUNT(DISTINCT obs_date)` —— 总行数除以月份数。
如果手滑写成 `COUNT(DISTINCT fe.asset_id) / COUNT(DISTINCT fe.obs_date)`, 分子就变成了"43 个月里 **曾经** 进过 Q1/Q5 的不重复标的数", 算出来只有 27.7 而不是 458.8, **差 16.5 倍**。后果是连锁的: `participation` 会被顶到 1.5 的上限, 于是 `SQRT(participation)` 在三个情景里恒等于常数, 成本对价差退化成一条直线, 整道题想演示的东西就没了。**分母是月份数的时候, 分子几乎不可能是 `DISTINCT`。**

净 IR 的分母 (主动波动) 用 `q5_q1_annual_return / gross_ir` 反解出来 —— 因为 `factor_validation_run` 没有直接存这一列。

**SQL**

```sql
WITH scenarios(scenario, spread_multiplier) AS (
    VALUES ('base', 1.0), ('spread_x1.5', 1.5), ('spread_x2', 2.0)
),
basket AS (
    SELECT f.id AS factor_id, f.code,
           AVG(b.bid_ask_spread_bps) AS spread_bps,
           AVG(b.adv_20d_usd)        AS adv_usd,
           COUNT(*) * 1.0 / COUNT(DISTINCT fe.obs_date) AS basket_n
    FROM factor_exposure fe
    JOIN factor f    ON f.id = fe.factor_id
    JOIN daily_bar b ON b.asset_id = fe.asset_id AND b.trade_date = fe.obs_date
    WHERE fe.quintile IN (1, 5) AND f.code IN ('ACC_QUALITY', 'PEAD_SUE', 'STR_REV_5D')
    GROUP BY f.id, f.code
)
SELECT s.scenario, bk.code,
       ROUND(bk.spread_bps * s.spread_multiplier, 1)                       AS spread_bps,
       ROUND(v.q5_q1_annual_return * 100, 2)                               AS gross_ann_pct,
       ROUND(v.annual_turnover
             * (0.5 * bk.spread_bps * s.spread_multiplier
                + 0.55 * bk.spread_bps * s.spread_multiplier
                  * SQRT(MIN(3000.0 * 1e6 / bk.basket_n / bk.adv_usd, 1.5))
                + 1.0) / 100.0, 2)                                         AS cost_ann_pct,
       ROUND((v.q5_q1_annual_return
              - v.annual_turnover
                * (0.5 * bk.spread_bps * s.spread_multiplier
                   + 0.55 * bk.spread_bps * s.spread_multiplier
                     * SQRT(MIN(3000.0 * 1e6 / bk.basket_n / bk.adv_usd, 1.5))
                   + 1.0) / 10000.0)
             / (v.q5_q1_annual_return / v.gross_ir), 2)                     AS net_ir_scenario
FROM scenarios s
CROSS JOIN basket bk
JOIN factor_validation_run v ON v.factor_id = bk.factor_id
 AND v.universe_id = 1 AND v.window_type = 'FULL'
ORDER BY bk.code, s.spread_multiplier;
```

**预期结果与业务结论**

返回 9 行 (`basket_n` 三个因子都是 458.8, `participation` 约 0.12, 远没有顶到 1.5 的上限):

| 情景 | ACC_QUALITY | PEAD_SUE | STR_REV_5D |
|------|-------------|----------|------------|
| base (约 29 bps) | 1.11 | 1.86 | **0.98** |
| ×1.5 (约 44 bps) | 1.03 | 1.63 | **0.66** |
| ×2 (约 58 bps) | **0.94** | **1.40** | **0.34** |
| **净 IR 损失** | **-15%** | **-25%** | **-65%** |

**三条曲线的斜率完全不同, 而斜率就是换手率。**

- `ACC_QUALITY` (换手 5.5 倍): 价差翻倍, 净 IR 从 1.11 掉到 0.94, 损失 15%。撑得住。
- `PEAD_SUE` (换手 12.5 倍): 从 1.86 掉到 1.40, 损失 25%。要盯着。
- `STR_REV_5D` (换手 22.8 倍): 从 0.98 掉到 0.34, **损失 65% —— 一次压力期就能把它从"可用"打到"不值得运维"。**

**说清楚哪一处是非线性的, 哪一处不是, 这道题才算做对了:**

- **对价差冲击, 成本是线性的。** 半价差和冲击成本这两项里都带着 `spread × mult`, 而 `participation` 不随价差变化, 所以价差翻倍 → 成本大致翻倍。三个因子的成本比值都接近 1.5× / 2.0×。
- **真正非线性的是资金规模那一维。** `participation = 配置金额 / (篮子只数 × ADV)`, 而冲击成本按 `SQRT(participation)` 缩放。在 30 亿的配置下 participation 只有 0.12, 还在这条平方根曲线比较平的一段; 一旦规模翻上去, 边际成本就会加速上升 —— **那才是 Q18 容量分析要处理的问题。**
- **所以真正杀死一个因子的不是"成本变成非线性", 而是"线性的成本乘上一个很大的换手率"。** `STR_REV_5D` 每年要付 22.8 次这个成本, 价差涨 1 bps 对它的伤害是 `ACC_QUALITY` 的四倍。

**这就是压力期量化策略集体失血的机制:** 波动上来 → 信号变化加快 → 想调仓 → 但价差同时走阔 → 成本吃掉大半 alpha。**换手率高的因子, 恰好在最需要它的时候最贵。**

> **base 情景的净 IR 为什么比 Q11 里的官方 `net_ir` (1.07 / 1.74 / 0.83) 高几个百分点?** 因为两边取流动性参数的口径不同: 官方口径用的是每月多空篮子 ADV 的 **中位数** 再跨月平均, 而这里用的是全部暴露行 ADV 的 **算术平均**, 后者被大市值票拉高, 于是估出来的冲击成本略低。**这不是 bug, 是"同一个公式换一组输入"的正常差异** —— 但它提醒你: 报告净 IR 时必须同时报清楚成本参数是怎么取的。

**拿到结果之后:** 给 `STR_REV_5D` 加一条硬性风控: 当组合层面的平均价差超过基准的 1.3 倍时, 自动降低它在复合信号里的权重。这条规则要写进生产系统, 而不是留给人临场判断。

---

### Q13. Look-ahead bias: 两种 as-of 口径的对决

**业务背景**

**这是 Atlas 在这一轮里最重要的一个发现, 也是本数据集的核心教学案例。**

Atlas 跑到第 3 个假设 `PEAD_SUE` (盈余公告后漂移) 时, 第一遍计算给出的 RankIC 是 **0.1200**。它没有高兴, 而是在决策日志里写下了这样一句话:

> *"First-pass IC is implausibly high for a well-known published anomaly. Before believing it, audit the point-in-time discipline of the underlying fundamentals."*
> (对一个众所周知的公开异象来说, 第一遍的 IC 高得不合理。在相信它之前, 先审计底层基本面数据的时点纪律。)

**它是因为"这个数字太好了"才去查的, 不是碰巧查到的。** 随后的 `pit_audit` 步骤发现财报平均滞后 30 天, 于是它换了 as-of 口径重算一遍。

Head of Model Validation 要把这个对比做成培训材料的第一页。这道题对应业务问题 Q3。

**标签:** 多 CTE + 窗口函数 + 统计 | 难度: 高级 | 角色: Head of Model Validation

**解题思路**

这题的骨架是: **同一份数据, 两种 as-of 规则, 并排算 IC。**

`leaky` CTE 用 `fr.fiscal_period_end <= m.obs_date` 关联 —— 这是错误口径, 它会取到那些季度已经结束、但财报还没公布的记录。`correct` CTE 用 `fr.publish_date <= m.obs_date` —— 这才是当时真正能看到的。

两个 CTE 都用 `ROW_NUMBER() OVER (PARTITION BY asset_id, obs_date ORDER BY ... DESC)` 取"最近的那一份", 外层用 `rn = 1` 过滤。**这是 SQL 里取每组最新一行的标准模式**, 比相关子查询快得多。

两处都加了 `fr.version = 1`, 把修订版排除掉 —— 这道题只研究 as-of 规则这一个变量, 修订版的问题留给 Q19。**一次只动一个变量, 是所有归因分析的基本纪律。**

`paired` 里用 LEFT JOIN 再在 WHERE 里过滤非空, 是为了让"两种口径都有值"成为显式条件 —— 只有在同一批观测上比较, 差异才归因于口径本身。

最后的 `per_month` 和 Q3 一样, 用 `PERCENT_RANK` + 手工 Pearson 拼出 Spearman。t 统计量同样要记得贝塞尔修正。

**SQL**

```sql
WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
leaky AS (
    SELECT m.asset_id, m.obs_date, fr.sue,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.fiscal_period_end DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.fiscal_period_end <= m.obs_date
),
correct AS (
    SELECT m.asset_id, m.obs_date, fr.sue,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.publish_date DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.publish_date <= m.obs_date
),
paired AS (
    SELECT f.obs_date, f.fwd_ret, l.sue AS sue_leaky, c.sue AS sue_correct
    FROM fwd f
    LEFT JOIN leaky   l ON l.asset_id = f.asset_id AND l.obs_date = f.obs_date AND l.rn = 1
    LEFT JOIN correct c ON c.asset_id = f.asset_id AND c.obs_date = f.obs_date AND c.rn = 1
    WHERE f.fwd_ret IS NOT NULL AND l.sue IS NOT NULL AND c.sue IS NOT NULL
),
ranked AS (
    SELECT obs_date,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY fwd_ret)     AS rr,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY sue_leaky)   AS rl,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY sue_correct) AS rc
    FROM paired
),
per_month AS (
    SELECT obs_date,
           (AVG(rl*rr) - AVG(rl)*AVG(rr))
             / (SQRT(AVG(rl*rl)-AVG(rl)*AVG(rl)) * SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_leaky,
           (AVG(rc*rr) - AVG(rc)*AVG(rr))
             / (SQRT(AVG(rc*rc)-AVG(rc)*AVG(rc)) * SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_correct
    FROM ranked GROUP BY obs_date
)
SELECT COUNT(*) AS n_months,
       ROUND(AVG(ic_leaky), 4)                     AS ic_join_on_period_end,
       ROUND(AVG(ic_correct), 4)                   AS ic_join_on_publish_date,
       ROUND(AVG(ic_leaky) / AVG(ic_correct), 2)   AS inflation_ratio,
       ROUND(AVG(ic_leaky) / (SQRT(AVG(ic_leaky*ic_leaky) - AVG(ic_leaky)*AVG(ic_leaky))
             * SQRT(COUNT(*)*1.0/(COUNT(*)-1))) * SQRT(COUNT(*)), 2)   AS t_leaky,
       ROUND(AVG(ic_correct) / (SQRT(AVG(ic_correct*ic_correct) - AVG(ic_correct)*AVG(ic_correct))
             * SQRT(COUNT(*)*1.0/(COUNT(*)-1))) * SQRT(COUNT(*)), 2)   AS t_correct
FROM per_month;
```

**预期结果与业务结论**

返回 1 行, 但这一行是本数据集最重要的一行:

| n_months | ic_join_on_period_end | ic_join_on_publish_date | inflation_ratio | t_leaky | t_correct |
|----------|----------------------|------------------------|-----------------|---------|-----------|
| 41 | **0.1101** | **0.0273** | **4.03** | 4.23 | 3.79 |

**一个 join 条件, 让 RankIC 虚增 4 倍。**

0.1101 这个数字如果出现在一份研究报告里, 任何有经验的人都该起疑 —— **公开发表了几十年的盈余漂移异象, 不可能还有 0.11 的 IC。** 而 0.0273 就非常合理: 一个真实存在、但已经被大量交易过、只剩微弱残余的经典因子。

**特别注意 t 统计量:** 两种口径的 t 值分别是 4.23 和 3.79, **都远超任何门槛**。这说明 **显著性检验完全无法识别 look-ahead bias** —— 错误的口径给出的是一个"显著且强大"的假因子。能救你的只有对数字量级的业务直觉, 以及主动去审计 as-of 规则的纪律。

> **两个必须解释清楚的数字, 否则你会以为哪里错了:**
>
> **(1) 为什么 `n_months = 41` 而不是全文一直在说的 42?** 因为第一个观测月是 2022-12-30, 而库里最早的一份财报 `publish_date` 是 **2023-01-18**。那一天没有任何"当时已公布"的 v1 财报, `correct` CTE 整月落空, 于是共同样本只剩 41 个月。**这不是 bug, 这就是 PIT 纪律本身:仓库里有的东西, 不等于当时看得到的东西。**
>
> **(2) 为什么这里的 0.0273 和 `factor_ic_monthly` 里存的 0.0341 不一样?** 因为它们是两套口径, 两个都对:
>
> | | 仓库口径 | 本查询的重建口径 |
> |--|---------|----------------|
> | 数据来源 | `factor_exposure` (已策展的面板) | `fundamental_report` (从零重建) |
> | 覆盖 | 42 个月 × 每月约 1,150 只票 | 41 个月 × 只有"当月已有财报公布"的标的 |
> | `PEAD_SUE` RankIC | **0.0341** | **0.0273** |
>
> 重建口径的横截面更小、样本更短, 数字自然不同。**`agent_step` / `agent_finding` 里记录的是重建口径的这一套** (因为 Agent 那一步执行的就是这条查询); `factor_validation_run` 和 Q4 / Q15 / Q18 显示的是仓库口径的那一套。**同一个因子在同一个库里有两个 IC, 而且都对 —— 这是分析师迟早要撞上的现实, 本数据集刻意让你在这里先撞一次。**

**拿到结果之后:** 三件事。(a) 把这张对比表放进新人培训的第一页。(b) 在 CI 里加一条自动检查: 任何提交的因子, 如果 RankIC 超过 0.08, 自动触发 PIT 审计流程。(c) `PEAD_SUE` 按 **0.0273** 的正确口径提交验证, 而不是 0.1101。

---

### Q14. 幸存者偏差: 加回退市标的会怎样

**业务背景**

Atlas 跑到第 9 个假设 `DIV_GROWTH_5Y` (连续 5 年股息增长) 时, 在存续标的上得到了一个相当漂亮的结果。但它的 `survivorship_audit` 步骤先做了一件事: **看看那些后来退市的公司, 在这个因子上得分是高是低。**

答案是: **系统性偏高 (平均 z-score +1.2)。** 这完全说得通 —— **一家公司在走下坡路时, 往往会咬牙维持甚至提高分红, 用来向市场传递"我们没事"的信号。** 于是"连续 5 年股息增长"这个筛选, 反而会精准地捞起一批正在慢性死亡的公司。

Head of Model Validation 要把这个对比做成培训材料的第二页。这道题对应业务问题 Q3。

**标签:** CTE + NTILE + UNION ALL | 难度: 高级 | 角色: Head of Model Validation

**解题思路**

结构是: **同一份因子打分, 两个不同的股票池, 并排算分层收益。**

`base` CTE 把因子暴露、前瞻收益、以及"是不是幸存者"这个标记拼在一起。`is_survivor` 用 `CASE WHEN a.delisted_date IS NULL` 判定。

然后是两个平行的 CTE: `survivors` 只取 `is_survivor = 1`, `everything` 取全部。**两边都必须重新用 `NTILE(5) OVER (PARTITION BY obs_date ORDER BY z_score)` 分层**, 而不能复用 `factor_exposure.quintile` —— 因为池子变了, 分位点就变了。这是这道题最容易错的地方: 如果直接用现成的 quintile, 存续池的 Q5 会少掉一部分名额, 两边就不可比了。

`NTILE(5)` 是 SQLite 支持的窗口函数, 把每个分区等分成 5 份。

最后用 `UNION ALL` 把两组结果堆起来, 加一列文字标签区分。同时把 Q5 和 Q1 各自的年化收益也选出来 —— **只看 Q5-Q1 的差值会掩盖问题出在哪一头。**

**SQL**

```sql
WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
base AS (
    SELECT fe.obs_date, fe.z_score, fw.fwd_ret,
           CASE WHEN a.delisted_date IS NULL THEN 1 ELSE 0 END AS is_survivor
    FROM factor_exposure fe
    JOIN factor f  ON f.id = fe.factor_id AND f.code = 'DIV_GROWTH_5Y'
    JOIN asset  a  ON a.id = fe.asset_id
    JOIN fwd    fw ON fw.asset_id = fe.asset_id AND fw.obs_date = fe.obs_date
    WHERE fw.fwd_ret IS NOT NULL
),
survivors AS (
    SELECT NTILE(5) OVER (PARTITION BY obs_date ORDER BY z_score) AS q, fwd_ret
    FROM base WHERE is_survivor = 1
),
everything AS (
    SELECT NTILE(5) OVER (PARTITION BY obs_date ORDER BY z_score) AS q, fwd_ret FROM base
)
SELECT 'survivors_only' AS universe_treatment,
       COUNT(*) AS n_obs,
       ROUND(AVG(CASE WHEN q = 5 THEN fwd_ret END) * 1200, 2) AS q5_ann_pct,
       ROUND(AVG(CASE WHEN q = 1 THEN fwd_ret END) * 1200, 2) AS q1_ann_pct,
       ROUND((AVG(CASE WHEN q = 5 THEN fwd_ret END)
              - AVG(CASE WHEN q = 1 THEN fwd_ret END)) * 1200, 2) AS q5_q1_ann_pct
FROM survivors
UNION ALL
SELECT 'including_delisted', COUNT(*),
       ROUND(AVG(CASE WHEN q = 5 THEN fwd_ret END) * 1200, 2),
       ROUND(AVG(CASE WHEN q = 1 THEN fwd_ret END) * 1200, 2),
       ROUND((AVG(CASE WHEN q = 5 THEN fwd_ret END)
              - AVG(CASE WHEN q = 1 THEN fwd_ret END)) * 1200, 2)
FROM everything;
```

**预期结果与业务结论**

返回 2 行:

| 池子处理方式 | 观测数 | Q5 年化% | Q1 年化% | **Q5-Q1 年化%** |
|-------------|--------|---------|---------|----------------|
| survivors_only | 45,360 | **17.86** | 9.15 | **8.71** |
| including_delisted | 48,082 | **12.12** | 9.02 | **3.10** |

**长短腿价差从 8.71% 塌到 3.10%, 损失 5.6 个百分点, 只因为多算了 2,722 个观测 (占全部的 5.7%)。**

**关键在于问题出在哪一头:** Q1 几乎没变 (9.15% → 9.02%), **Q5 从 17.86% 掉到 12.12%**。也就是说, 退市标的几乎全部落在 **最高分那一层** —— 完美印证了"垂死的公司靠死撑分红维持高分"这个机制。

**这是一个只有 5.7% 的观测就能颠覆整个结论的例子。** 如果你的数据供应商只提供"当前成分股"的历史数据 (很多便宜的数据源就是这样), 你会得到 8.71% 这个数, 并且完全没有办法发现它是错的。

**拿到结果之后:** (a) `DIV_GROWTH_5Y` 按 3.10% 的口径提交 —— 在这个水平上它已经过不了 t 检验了 (Q15 会看到 t = 1.54)。(b) 在数据采购标准里加一条: **任何不提供退市标的历史的数据源, 不得用于因子研究。** 这条规则的价值就是这 5.6 个百分点。

---

### Q15. 多重检验: 试得越多, 门槛越高

**业务背景**

Head of Quantitative Research 要向投委会解释一件反直觉的事: **Atlas 这一轮里有一个因子 (`SEARCH_TREND`) 的 t 统计量是 2.32, 按传统标准算显著, 但他决定否决它。**

理由是它是本轮的第 8 次尝试。按 Harvey、Liu、Zhu 在《Review of Financial Studies》上给出的多重检验框架, 在因子动物园的语境下, 一个新因子需要跨过的门槛远高于 t > 2.0。**试到第 8 个的时候, 门槛已经升到 3.36。**

这个道理不好讲, 所以他要一张表把它讲清楚: 十个假设, 每个的尝试序号、实测 t、传统门槛下的结论、调整后门槛下的结论, 并排放。这道题对应业务问题 Q1 与 Q2。

**标签:** Join + 条件判定 | 难度: 中级 | 角色: Head of Quantitative Research

**解题思路**

三表 join: `agent_hypothesis` 提供尝试序号和门槛, `factor` 提供代码, `factor_validation_run` 提供实测 t。

`applied_t_threshold` 已经由生成器按 `2.00 + 0.62 × ln(seq_no + 1)` 算好存进表里 —— **把这个规则物化成一列, 而不是留在文档的注意事项里, 是本数据集刻意的设计。** 规则写在文档里会被忽略, 写在表里就绕不过去。

两个 `CASE WHEN` 分别给出两种门槛下的结论。把它们并排放, 差异一眼就能看到。

`deflated_sharpe` 一起选出来做交叉验证: 它是从另一个角度 (按尝试次数、偏度、峰度打折的 Sharpe) 做同一件事, 两个指标应该给出一致的信号。

**SQL**

```sql
SELECT h.seq_no                                        AS trial_index,
       f.code,
       h.idea_source,
       ROUND(v.ic_tstat, 2)                            AS observed_t,
       2.00                                            AS naive_threshold,
       ROUND(h.applied_t_threshold, 2)                 AS adjusted_threshold,
       CASE WHEN v.ic_tstat >= 2.00 THEN 'PASS' ELSE 'FAIL' END AS naive_verdict,
       CASE WHEN v.ic_tstat >= h.applied_t_threshold THEN 'PASS' ELSE 'FAIL' END AS adjusted_verdict,
       ROUND(v.deflated_sharpe, 2)                     AS deflated_sharpe,
       h.verdict                                       AS agent_verdict,
       COALESCE(h.reject_reason_code, '-')             AS reject_reason
FROM agent_hypothesis h
JOIN factor f ON f.id = h.factor_id
JOIN factor_validation_run v ON v.factor_id = f.id
 AND v.universe_id = 1 AND v.window_type = 'FULL'
ORDER BY h.seq_no;
```

**预期结果与业务结论**

返回 10 行:

| trial | code | 实测 t | 传统门槛 | 调整后门槛 | 传统结论 | **调整后结论** | DSR | Agent 裁决 |
|-------|------|--------|---------|-----------|---------|---------------|-----|-----------|
| 1 | ACC_QUALITY | 2.73 | 2.0 | 2.43 | PASS | **PASS** | 0.78 | PROMOTED |
| 2 | EPS_REV_60D | 3.52 | 2.0 | 2.68 | PASS | **PASS** | 1.35 | PROMOTED |
| 3 | PEAD_SUE | 4.43 | 2.0 | 2.86 | PASS | **PASS** | 1.59 | PROMOTED |
| 4 | STR_REV_5D | 3.11 | 2.0 | 3.00 | PASS | **PASS** | -0.14 | PROMOTED |
| 5 | VOL_SKEW_ADJ | 2.47 | 2.0 | 3.11 | PASS | **FAIL** | -0.08 | REJECTED |
| 6 | MICRO_VALUE | 4.58 | 2.0 | 3.21 | PASS | **PASS** | 1.81 | REJECTED |
| 7 | NEWS_SENT_7D | 1.83 | 2.0 | 3.29 | FAIL | **FAIL** | -2.67 | REJECTED |
| 8 | **SEARCH_TREND** | **2.32** | 2.0 | **3.36** | **PASS** | **FAIL** | -1.05 | REJECTED |
| 9 | DIV_GROWTH_5Y | 1.54 | 2.0 | 3.43 | FAIL | **FAIL** | -1.37 | REJECTED |
| 10 | FCF_MARGIN_TTM | 6.39 | 2.0 | 3.49 | PASS | **PASS** | 2.18 | REJECTED |

**三组值得单独看:**

1. **第 8 行是这张表的主角。** t = 2.32 在传统标准下是"显著"的, 换个上下文就是"不显著"。同一个数字, 两个结论 —— **差别不在数据, 而在你之前试了几次。**
2. **第 5 行 (`VOL_SKEW_ADJ`) 同样倒在门槛上** (2.47 < 3.11), 而且它的 `deflated_sharpe` 是负的 —— 两个独立的指标给出同一个信号。
3. **第 6 和第 10 行最值得琢磨: 它们轻松跨过了调整后门槛, 却仍然被否决。** `MICRO_VALUE` 死于容量 (Q18), `FCF_MARGIN_TTM` 死于数据修订 (Q19)。**统计显著只是入场券, 不是通行证。**

另外注意 **前 4 个被推进的假设都排在最前面**。这不是巧合, 而是 Atlas 的排序策略: 它把文献支撑最强、先验最高的假设放在前面试, 因为 **越早试的假设, 门槛越低**。在多重检验的框架下, **探索顺序本身就是一种资源。**

**拿到结果之后:** 把 `applied_t_threshold` 做成因子提交系统的强制字段, 并且累计计数不能只算本轮 —— 研究部门在同一份数据上历史累计试过的次数, 才是真正的分母。这意味着实际门槛只会比这张表里的更高。

---
### Q16. Regime 拆分: 谁在换环境后翻脸

**业务背景**

Chief Risk Officer 对 Atlas 提的 `NEWS_SENT_7D` (7 日新闻情绪) 有一个具体的怀疑。这类"关注度"因子在情绪驱动的上涨市里通常很灵, 但她见过太多次它们在恐慌里反向 —— **恐慌的时候, 新闻多的股票是被卖得最狠的那批, 不是被买得最猛的那批。**

全样本 RankIC 只有 0.0140, 看着平平无奇。她担心的正是这个"平平无奇": **如果它在一半时间里 +0.05, 另一半时间里 -0.05, 平均下来就是接近零 —— 而这比一个真正无效的因子危险得多**, 因为它会在某些时期给出强烈但错误的信号。

她要把全部 16 个因子按 regime 拆一遍, 一次性看清楚谁稳、谁不稳。这道题对应业务问题 Q5。

**标签:** 条件聚合 (SQL 透视) | 难度: 中级 | 角色: Chief Risk Officer

**解题思路**

这是一个 **SQL 透视 (pivot)** 的标准场景: 行是因子, 列是 regime。SQLite 没有 `PIVOT` 语法, 用 `MAX(CASE WHEN ... THEN ... END)` 手工实现。

先用 `by_regime` CTE 把数据聚合成 (因子, regime, IC) 的长表, 再在外层透视成宽表。**分两步比一步到位更清晰, 也更容易调试** —— 你可以单独跑 CTE 看中间结果。

外层用 `MAX()` 而不是 `AVG()`: 因为经过 CTE 聚合后每个 (因子, regime) 只剩一行, `CASE WHEN` 对其他 regime 返回 NULL, 而 `MAX()` 会忽略 NULL 恰好取到那唯一的值。这是透视的惯用手法。

最后两列是判定逻辑: `ic_range` 衡量波动幅度, `regime_check` 用 `MAX(ic) > 0.02 AND MIN(ic) < -0.02` 判定符号翻转。**门槛设在 ±0.02 而不是 0, 是为了避免把噪声当成翻转** —— 8 个月样本的 IC 标准误约 0.02, 不设缓冲会满屏误报。

**排序这一行值得单独说。** 这道题的全部教学 payload 就在"一眼看到那一行", 所以 `SIGN_FLIP` 必须排在第一。**不要写 `ORDER BY regime_check DESC`** —— 那排的是一个文本列, 而 ASCII 里小写字母大于大写字母, `'stable_sign' > 'SIGN_FLIP'`, 唯一那条 `SIGN_FLIP` 会被推到第 16 行去。正确做法是显式给出排序键:

```sql
ORDER BY CASE WHEN regime_check = 'SIGN_FLIP' THEN 0 ELSE 1 END, ic_range DESC
```

**凡是按"状态文本"排序的地方都要停一下想想大小写和字典序** —— 这类 bug 不会报错, 只会让你在预期表里写错顺序。

**SQL**

```sql
WITH by_regime AS (
    SELECT f.code, r.code AS regime, AVG(i.rank_ic) AS ic, COUNT(*) AS n
    FROM factor_ic_monthly i
    JOIN factor f      ON f.id = i.factor_id
    JOIN regime_type r ON r.id = i.regime_type_id
    WHERE i.universe_id = 1
    GROUP BY f.code, r.code
)
SELECT code,
       ROUND(MAX(CASE WHEN regime = 'LOW_VOL_BULL'    THEN ic END), 4) AS low_vol_bull,
       ROUND(MAX(CASE WHEN regime = 'RECOVERY'        THEN ic END), 4) AS recovery,
       ROUND(MAX(CASE WHEN regime = 'RISING_RATE'     THEN ic END), 4) AS rising_rate,
       ROUND(MAX(CASE WHEN regime = 'HIGH_VOL_STRESS' THEN ic END), 4) AS high_vol_stress,
       ROUND(MAX(ic) - MIN(ic), 4)                                     AS ic_range,
       CASE WHEN MAX(ic) > 0.02 AND MIN(ic) < -0.02
            THEN 'SIGN_FLIP' ELSE 'stable_sign' END                    AS regime_check
FROM by_regime
GROUP BY code
ORDER BY CASE WHEN MAX(ic) > 0.02 AND MIN(ic) < -0.02 THEN 0 ELSE 1 END, ic_range DESC;
```

**预期结果与业务结论**

返回 16 行, 第一行就是唯一被标为 `SIGN_FLIP` 的那个因子:

| code | low_vol_bull | recovery | rising_rate | high_vol_stress | ic_range | 判定 |
|------|--------------|----------|-------------|-----------------|----------|------|
| **NEWS_SENT_7D** | **+0.0523** | +0.0159 | -0.0005 | **-0.0459** | **0.0982** | **SIGN_FLIP** |
| EPS_REV_60D | 0.0792 | 0.0264 | 0.0558 | -0.0034 | 0.0826 | stable_sign |
| VAL_EP | 0.0264 | 0.0208 | 0.0596 | -0.0125 | 0.0721 | stable_sign |
| STR_REV_5D | 0.0650 | 0.0117 | 0.0010 | 0.0358 | 0.0640 | stable_sign |
| ... | | | | | | |
| FCF_MARGIN_TTM | 0.0367 | 0.0195 | 0.0379 | 0.0314 | 0.0185 | stable_sign |

**`NEWS_SENT_7D` 在低波牛市里 +0.0523, 在高波压力期里 -0.0459 —— 幅度接近、符号相反。** 全样本的 0.0140 完全是这两段互相抵消的结果, 它是一个统计假象, 不是一个"弱信号"。

**对比 `EPS_REV_60D`**: 它的 `ic_range` 是 0.0826, 几乎和 `NEWS_SENT_7D` 一样大, 但四个 regime 里有三个显著为正, 最差的一个只有 -0.0034 (在噪声内)。**这是幅度变化, 不是方向变化。** 两者的区别就是 `regime_check` 这一列存在的全部理由。

**这也是为什么 CRO 说它"比无效因子更危险":** 一个 IC 为零的因子只会浪费你的成本; 一个符号会翻的因子, 会在市场最紧张的时候把你推向完全错误的方向。

**拿到结果之后:** `NEWS_SENT_7D` 直接否决, 理由记为 `REGIME_DEPENDENT`。**不要试图"给它加一个 regime 择时开关"** —— 那等于把一个 alpha 问题偷换成一个 regime 预测问题, 而 TCM 没有 regime 预测能力, 也没有这个授权。

---

### Q17. 正交性: 这是新因子还是旧因子换皮

**业务背景**

Head of Quantitative Research 对 Atlas 提的 `VOL_SKEW_ADJ` (偏度调整波动率) 有一个直觉上的怀疑。这个因子的 `complexity_score` 是 9, **全库最高** —— 它的表达式比其他任何因子都复杂。

而复杂本身就是一个信号。一个 LLM 在被要求"提出一个新的低波动因子"时, 最容易走的路就是 **把已有的低波动因子做一个复杂的变换, 然后声称它是新的**。表达式越复杂, 越容易掩盖这件事。

他要对全部 10 个候选因子做同一件事: **把它们的月度 IC 序列和 6 个生产因子逐一算相关系数, 找出最像的那一个。** 相关性超过 0.75 的, 无论 IC 多漂亮都不要 —— 它带来的不是新 alpha, 是同一个赌注换了个名字。这道题对应业务问题 Q2。

**标签:** 自连接 + 相关系数 | 难度: 高级 | 角色: Head of Quantitative Research

**解题思路**

这题的核心是 **`factor_ic_monthly` 表的自连接**: 候选因子的 IC 序列 vs 生产因子的 IC 序列, 按 `obs_date` 对齐。

```text
FROM factor_ic_monthly a
JOIN factor cand ON cand.id = a.factor_id AND cand.status = 'candidate'
JOIN factor_ic_monthly b ON b.obs_date = a.obs_date AND b.universe_id = a.universe_id
JOIN factor prod ON prod.id = b.factor_id AND prod.status = 'production'
```

**`b.universe_id = a.universe_id` 这个条件绝不能漏。** 少了它, 每个 (候选, 生产) 组合会匹配出 3 × 3 = 9 倍的行 (三个池子交叉), 相关系数会被算得一塌糊涂。**这是自连接最典型的扇出 (fan-out) 陷阱。**

相关系数还是那个手工 Pearson 公式, 和 Q3、Q13 一模一样。

`ranked` CTE 用 `ROW_NUMBER() OVER (PARTITION BY candidate ORDER BY ABS(ic_corr) DESC)` 找出每个候选因子最像的那个生产因子。**排序用 `ABS()`** —— 相关性 -0.9 和 +0.9 一样糟糕, 它们都意味着"同一个赌注", 只是方向相反。

**SQL**

```sql
WITH pairs AS (
    SELECT cand.code AS candidate, prod.code AS production,
           (AVG(a.rank_ic * b.rank_ic) - AVG(a.rank_ic) * AVG(b.rank_ic))
           / (SQRT(AVG(a.rank_ic * a.rank_ic) - AVG(a.rank_ic) * AVG(a.rank_ic))
              * SQRT(AVG(b.rank_ic * b.rank_ic) - AVG(b.rank_ic) * AVG(b.rank_ic))) AS ic_corr
    FROM factor_ic_monthly a
    JOIN factor cand ON cand.id = a.factor_id AND cand.status = 'candidate'
    JOIN factor_ic_monthly b ON b.obs_date = a.obs_date AND b.universe_id = a.universe_id
    JOIN factor prod ON prod.id = b.factor_id AND prod.status = 'production'
    WHERE a.universe_id = 1
    GROUP BY cand.code, prod.code
),
ranked AS (
    SELECT candidate, production, ic_corr,
           ROW_NUMBER() OVER (PARTITION BY candidate ORDER BY ABS(ic_corr) DESC) AS rn
    FROM pairs
)
SELECT candidate,
       production                     AS closest_production_factor,
       ROUND(ic_corr, 3)              AS ic_correlation,
       CASE WHEN ABS(ic_corr) > 0.75 THEN 'REDUNDANT' ELSE 'incremental' END AS orthogonality_check
FROM ranked WHERE rn = 1
ORDER BY ABS(ic_corr) DESC;
```

**预期结果与业务结论**

返回 10 行, 按相关性绝对值降序:

| candidate | 最接近的生产因子 | IC 相关性 | 判定 |
|-----------|-----------------|----------|------|
| **VOL_SKEW_ADJ** | **VOL_LOW_60D** | **0.931** | **REDUNDANT** |
| DIV_GROWTH_5Y | SIZ_LOG_MCAP | 0.354 | incremental |
| NEWS_SENT_7D | VOL_LOW_60D | -0.338 | incremental |
| PEAD_SUE | SIZ_LOG_MCAP | 0.333 | incremental |
| ... | | | |
| ACC_QUALITY | SIZ_LOG_MCAP | **0.188** | incremental |
| FCF_MARGIN_TTM | LIQ_AMIHUD | -0.190 | incremental |

**结果极其干净: 一个 0.931, 其余全部低于 0.36。** 中间没有任何灰色地带, 判断毫不费力。

**`VOL_SKEW_ADJ` 和生产库里的 `VOL_LOW_60D` 相关性 0.931** —— 它们在 42 个月里几乎同涨同跌。回想 Q5: 这个因子的分层单调性完全没问题, Q4 里它的 ICIR 0.38 也在可用区间。**它在所有单因子指标上都是合格的, 唯独它不是新的。**

**注意 `ACC_QUALITY` 是最正交的候选因子之一 (0.190)。** 这解释了为什么它虽然 IC 不是最高的 (0.0275, 排在中游), 却被排在第一个推进 —— **在组合语境下, 一个中等强度但完全独立的信号, 比一个强但重复的信号有价值得多。**

**拿到结果之后:** `VOL_SKEW_ADJ` 否决, 理由 `REDUNDANT_WITH_EXISTING`。同时给研究部门加一条流程: **正交性检验必须在成本检验之前做** —— 为一个注定被否决的因子去算成本和容量, 是纯粹的浪费。Atlas 就是这么排的 (它只花了 **7 步** 就结束了这个假设 —— 只有第 8 个假设 `SEARCH_TREND` 的 6 步更少, 而那一个是在多重检验那一步直接被判死的)。

---

### Q18. 容量: 效果是不是全在装不下钱的地方

**业务背景**

Atlas 的第 6 个假设 `MICRO_VALUE` 在全池上给出了 RankIC 0.0316、t = 4.58、净 IR 2.17 —— **按 Q15 的多重检验门槛, 它轻松过关。** 按 Q17 的正交性检验, 它也过关 (相关性 -0.33)。

但 Atlas 在 `capacity_split` 那一步做了一件事: **把同一个因子分别在大盘池和微盘池上重算。** 结果让它立刻改变了判断。

Director of Portfolio Construction 要把这个分析扩展到全部 10 个候选因子 —— 他管着 320 亿美元, **一个只能装 2 亿的策略, 对他来说和不存在没有区别。** 这道题对应业务问题 Q4。

**标签:** 条件聚合 (SQL 透视) | 难度: 中级 | 角色: Director of Portfolio Construction

**解题思路**

又是一次透视, 但这次的列是 universe 而不是 regime。数据全在 `factor_validation_run` 里 —— 它对每个候选因子都存了三个池子的验证结论。

`MAX(CASE WHEN u.code = '...' THEN v.ic_mean END)` 把三个池子的 IC 摊平成三列。

`micro_over_large` 是这道题的核心派生指标: 微盘 IC ÷ 大盘 IC。**用 `NULLIF(..., 0)` 保护分母** —— 大盘 IC 理论上可能接近零, 除零会让整行变成 NULL 或报错。这是写派生指标时的基本防御。

同时把两个池子的容量并排放。**容量的定义取两条约束里更紧的一条**: (a) 冲击成本吃掉一半毛 alpha 时的规模; (b) 在 5% ADV 参与度上限内、21 个交易日能建起来的规模。真实世界里瓶颈通常是后者。

**SQL**

```sql
SELECT f.code,
       ROUND(MAX(CASE WHEN u.code = 'US_ALL'       THEN v.ic_mean END), 4) AS ic_all_cap,
       ROUND(MAX(CASE WHEN u.code = 'US_LARGE_500' THEN v.ic_mean END), 4) AS ic_large_cap,
       ROUND(MAX(CASE WHEN u.code = 'US_MICRO_250' THEN v.ic_mean END), 4) AS ic_micro_cap,
       ROUND(MAX(CASE WHEN u.code = 'US_MICRO_250' THEN v.ic_mean END)
             / NULLIF(MAX(CASE WHEN u.code = 'US_LARGE_500' THEN v.ic_mean END), 0), 1) AS micro_over_large,
       ROUND(MAX(CASE WHEN u.code = 'US_MICRO_250' THEN v.capacity_usd_mm END), 0) AS micro_capacity_mm,
       ROUND(MAX(CASE WHEN u.code = 'US_ALL'       THEN v.capacity_usd_mm END), 0) AS all_cap_capacity_mm
FROM factor_validation_run v
JOIN factor f   ON f.id = v.factor_id
JOIN universe u ON u.id = v.universe_id
WHERE v.window_type = 'FULL' AND f.status = 'candidate'
GROUP BY f.code
ORDER BY micro_over_large DESC;
```

**预期结果与业务结论**

返回 10 行, 按微盘/大盘 IC 之比降序:

| code | 全池 IC | 大盘 IC | 微盘 IC | **微盘/大盘** | 微盘容量 mm | 全池容量 mm |
|------|---------|---------|---------|--------------|------------|------------|
| **MICRO_VALUE** | 0.0316 | **0.0111** | **0.0746** | **6.7×** | **214** | 7,225 |
| NEWS_SENT_7D | 0.0140 | 0.0198 | 0.0292 | 1.5× | 1 | 1 |
| PEAD_SUE | 0.0341 | 0.0301 | 0.0419 | 1.4× | 219 | 7,293 |
| EPS_REV_60D | 0.0452 | 0.0436 | 0.0507 | 1.2× | 71 | 7,488 |
| ACC_QUALITY | 0.0275 | 0.0264 | 0.0311 | 1.2× | 215 | 7,196 |
| ... | | | | | | |
| DIV_GROWTH_5Y | 0.0124 | 0.0287 | 0.0067 | 0.2× | 1 | 7,229 |

**`MICRO_VALUE` 是唯一一个比值超过 2 的因子 (6.7×)。** 它在微盘池上 RankIC 0.0746 (相当强), 在大盘池上只有 0.0111 (基本是噪声)。全池的 0.0316 是这两者加权平均的产物 —— **一个看起来"全市场有效"的因子, 实际上只在最小的那 250 只票上有效。**

**而微盘池的容量只有 2.14 亿美元。** 对一家管理 320 亿的机构, 这意味着即使全额配置, 它对总组合的贡献也不到 0.7%, 而运维一个策略的固定成本 (数据、监控、合规、交易) 完全不划算。

**其余因子的比值都在 0.2 到 1.5 之间, 也就是说它们在大小盘上的表现基本一致** —— 这才是一个能上规模的因子该有的样子。特别看 `ACC_QUALITY`: 1.2×, 三个池子的 IC 几乎相同, 说明它捕捉的是一个普适的定价机制, 而不是小盘股的流动性溢价。

**拿到结果之后:** `MICRO_VALUE` 否决, 理由 `CAPACITY_CONSTRAINED`。同时把"微盘/大盘 IC 比值"加进因子提交的标准附件 —— **比值超过 2 的因子, 必须附带微盘池的容量测算才予受理。**

---

### Q19. 财报修订: 用原始版重算一遍

**业务背景**

**这是本数据集最重要的一道题。**

`FCF_MARGIN_TTM` 是 Atlas 的第 10 个假设, 也是它跑出来的所有数字里最漂亮的一个: RankIC 0.0314、ICIR 0.99、**t = 6.39**、净 IR **2.62**、与生产因子相关性只有 0.19、容量 76 亿美元、IC 胜率 83.3%。

**它在 `factor_validation_run` 里拿到的结论是 PASS。** 全部 7 条判定规则, 它一条都没有触碰。按 Model Validation 的标准流水线, 它应该直接进生产。

但 Atlas 否决了它。

理由在它的 `pit_audit` 步骤里: 它先查了修订率 (26% 的公司会修订财报, 见 Q8), 然后做了一件标准流水线不会做的事 —— **把这个因子从 `version = 1` 的原始财报重新算了一遍。**

Head of Model Validation 要亲自验证这个结论, 因为如果 Atlas 是对的, 那她的整条流水线都有一个系统性盲区。这道题对应业务问题 Q3。

**标签:** 多 CTE + 窗口函数 + 统计 | 难度: 高级 | 角色: Head of Model Validation

**解题思路**

结构和 Q13 是同构的: **同一个因子, 两种数据口径, 并排算 IC。** 但这次变的不是 as-of 规则, 而是 **版本**。

`original_only` CTE 取 `version = 1` 且 `publish_date <= obs_date` 的最近一份财报。**注意这里 as-of 规则用的是正确的 `publish_date`** —— 我们只想隔离"版本"这一个变量, 不能让 look-ahead 混进来污染结论。**一次只动一个变量**, 和 Q13 是同一条纪律。

`warehouse_z` 直接取 `factor_exposure.z_score` —— 那是数据仓库默认口径 (最新版本) 算出来的打分, 也就是 Atlas 第一遍看到的东西。

**这里有一个可能让人困惑的地方: 一边是 `fcf_margin_ttm` 原始值, 一边是 `z_score` 标准化打分, 两者量纲完全不同, 能直接比吗?** 能。因为 RankIC 只依赖 **排名**, 而 z-score 是原始值的单调变换 —— 单调变换不改变排名。所以两边的 `PERCENT_RANK()` 是可比的。**这是 RankIC 相对 Pearson IC 的一个实用优势。**

**SQL**

```sql
WITH month_end_bar AS (
    SELECT b.asset_id, c.month_index, c.trade_date AS obs_date, b.adj_close
    FROM daily_bar b JOIN trading_calendar c ON c.trade_date = b.trade_date
    WHERE c.is_month_end = 1
),
fwd AS (
    SELECT asset_id, month_index, obs_date,
           CASE WHEN LEAD(month_index) OVER w = month_index + 1
                THEN LEAD(adj_close) OVER w / adj_close - 1 END AS fwd_ret
    FROM month_end_bar WINDOW w AS (PARTITION BY asset_id ORDER BY month_index)
),
original_only AS (
    SELECT m.asset_id, m.obs_date, fr.fcf_margin_ttm,
           ROW_NUMBER() OVER (PARTITION BY m.asset_id, m.obs_date
                              ORDER BY fr.fiscal_period_end DESC) AS rn
    FROM month_end_bar m
    JOIN fundamental_report fr ON fr.asset_id = m.asset_id
     AND fr.version = 1 AND fr.publish_date <= m.obs_date
),
paired AS (
    SELECT fw.obs_date, fw.fwd_ret, o.fcf_margin_ttm AS pit_value, fe.z_score AS warehouse_z
    FROM fwd fw
    JOIN original_only o ON o.asset_id = fw.asset_id AND o.obs_date = fw.obs_date AND o.rn = 1
    JOIN factor_exposure fe ON fe.asset_id = fw.asset_id AND fe.obs_date = fw.obs_date
    JOIN factor f ON f.id = fe.factor_id AND f.code = 'FCF_MARGIN_TTM'
    WHERE fw.fwd_ret IS NOT NULL
),
ranked AS (
    SELECT obs_date,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY fwd_ret)      AS rr,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY pit_value)    AS rp,
           PERCENT_RANK() OVER (PARTITION BY obs_date ORDER BY warehouse_z)  AS rw
    FROM paired
),
per_month AS (
    SELECT obs_date,
           (AVG(rp*rr)-AVG(rp)*AVG(rr))/(SQRT(AVG(rp*rp)-AVG(rp)*AVG(rp))*SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_pit,
           (AVG(rw*rr)-AVG(rw)*AVG(rr))/(SQRT(AVG(rw*rw)-AVG(rw)*AVG(rw))*SQRT(AVG(rr*rr)-AVG(rr)*AVG(rr))) AS ic_warehouse
    FROM ranked GROUP BY obs_date
)
SELECT COUNT(*) AS n_months,
       ROUND(AVG(ic_warehouse), 4) AS ic_latest_version,
       ROUND(AVG(ic_pit), 4)       AS ic_version1_only,
       ROUND(AVG(ic_warehouse) - AVG(ic_pit), 4) AS ic_gap,
       (SELECT ROUND(100.0 * SUM(CASE WHEN is_restated = 1 THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM fundamental_report) AS restated_row_pct
FROM per_month;
```

**预期结果与业务结论**

返回 1 行:

| n_months | ic_latest_version | ic_version1_only | ic_gap | restated_row_pct |
|----------|-------------------|------------------|--------|------------------|
| 41 | **0.0296** | **0.0071** | 0.0225 | 19.3% |

**用当时真正能看到的原始财报重算, RankIC 从 0.0296 掉到 0.0071 —— 剩下不到四分之一, 而 0.0071 在统计上和零没有区别。**

> **和 Q13 一样, 这里的 `n_months = 41` 与 0.0296 都需要一句解释。** 41 是因为第一个观测月没有任何已公布的 v1 财报 (最早的 `publish_date` 是 2023-01-18); 0.0296 是 **重建口径** 的最新版 IC, 而 `factor_validation_run` 里存的 **仓库口径** 是 0.0314。两者的差别只来自样本 (41 个月、只覆盖有财报的标的 vs 42 个月、全池)。**这道题真正的结论不依赖用哪一套: 无论 0.0296 还是 0.0314, 换成 version 1 之后都塌到 0.0071。**

**这个因子的 alpha 几乎全部来自它不该知道的信息。** 机制是这样的: 一家公司在财季结束后先公布一份数字, 三个多月后又修订一次。修订的方向往往和这段时间里实际发生的经营状况同向 —— 也就是说, **修订版"知道"原始版不知道的事**。数据仓库默认返回最新版本, 于是整个回测都在用一份带着后视镜的财报。

**为什么标准验证流水线抓不到它:** `factor_validation_run` 的输入就是被污染的 `factor_exposure`。**污染发生在数据层, 而验证发生在指标层 —— 指标层的任何检验都无法发现输入本身是错的。** 无论你把 t 门槛提到多高、把 Deflated Sharpe 算得多精确, 都救不了你。

**能救你的只有一件事: 主动去改写数据口径, 然后看结论会不会变。** 这恰恰是 AI Agent 最适合做的事 —— **对人来说, 把一整套回测在四种数据口径下各重跑一遍是几天的工作量; 对 Agent 来说是几分钟。**

**拿到结果之后:** 三件事。(a) `FCF_MARGIN_TTM` 否决, 理由 `RESTATEMENT_CONTAMINATED`。(b) **在 `factor_validation_run` 的判定规则里增加一条强制项**: 所有依赖基本面的因子, 必须同时提交 `version = 1` 口径的 IC, 两者落差超过 50% 直接否决。(c) 把这道题的结论写进给 CIO 的备忘录 —— **Atlas 发现了一个人类流水线三年来一直没发现的系统性缺陷, 这本身就是它值得追加预算的最强论据。**

---

### Q20. 协方差估计在 regime 切换时靠不靠谱

**业务背景**

Chief Risk Officer 要为季度风险委员会准备一份风险模型的可靠性评估。她的问题很具体: **我们用哪种方法估协方差, 在市场环境切换的时候会不会低估风险?**

这不是学术问题。TCM 的研究池是 500 只标的, 回看窗口 250 个交易日 —— **T/N = 0.5, 待估参数远多于观测样本, 样本协方差矩阵在数学上必然奇异。** 她想知道这件事在实践中的代价有多大, 以及收缩方法到底改善了多少。这道题对应业务问题 Q5。

**标签:** Aggregation + HAVING | 难度: 中级 | 角色: Chief Risk Officer

**解题思路**

单表聚合加一次维表 join, 按 `(method, regime)` 双重分组。

关键是选对指标。`vol_bias_ratio = 实际波动 ÷ 预测波动` 是落脚点: **等于 1 完美, 大于 1 说明低估了风险。** `condition_number` 衡量矩阵的病态程度, `is_singular` 直接标出数学上不可逆的情况。

用 `MAX(cv.is_singular)` 而不是 `AVG()` —— 我们要问的是"有没有出现过奇异", 不是"平均有多奇异"。

`HAVING r.code IN (...)` 只保留两个对比最鲜明的 regime。**注意 `HAVING` 而不是 `WHERE`**: 这里其实两者都能用 (因为过滤的是分组键), 但用 `HAVING` 更符合"先聚合再筛选"的语义表达。

**SQL**

```sql
SELECT cv.method,
       r.code                                      AS regime,
       COUNT(*)                                    AS n_months,
       ROUND(AVG(cv.shrinkage_intensity), 3)       AS avg_shrinkage,
       ROUND(AVG(cv.condition_number), 0)          AS avg_condition_number,
       MAX(cv.is_singular)                         AS ever_singular,
       ROUND(AVG(cv.predicted_vol_ann) * 100, 2)   AS avg_predicted_vol_pct,
       ROUND(AVG(cv.realized_vol_ann_next) * 100, 2) AS avg_realized_vol_pct,
       ROUND(AVG(cv.vol_bias_ratio), 3)            AS avg_vol_bias_ratio
FROM covariance_estimate cv
JOIN regime_type r ON r.id = cv.regime_type_id
GROUP BY cv.method, r.code
HAVING r.code IN ('HIGH_VOL_STRESS', 'LOW_VOL_BULL')
ORDER BY CASE WHEN r.code = 'HIGH_VOL_STRESS' THEN 0 ELSE 1 END, avg_vol_bias_ratio DESC;
```

**注意最后那行排序。** 这里要的是"压力期在前", 但 `ORDER BY r.code DESC` 排的是文本 —— 字典序里 `'LOW_VOL_BULL' > 'HIGH_VOL_STRESS'` (`L` > `H`), 结果会把平静期排在前面, 和你想讲的顺序正好相反。**又是一个"按状态文本排序"的坑, 和 Q16 是同一个。**

**预期结果与业务结论**

返回 8 行 (4 种方法 × 2 个 regime), 完整如下:

| method | regime | 收缩强度 | 条件数 | 曾奇异 | 预测波动% | 实际波动% | **vol_bias** |
|--------|--------|---------|--------|--------|----------|----------|--------------|
| sample | HIGH_VOL_STRESS | 0.000 | **46,011** | **1** | 26.09 | 31.23 | **1.280** |
| ledoit_wolf | HIGH_VOL_STRESS | 0.401 | 231 | 0 | 28.64 | 31.52 | 1.115 |
| factor_model | HIGH_VOL_STRESS | 0.970 | 108 | 0 | 30.09 | 32.42 | 1.080 |
| oas | HIGH_VOL_STRESS | 0.404 | 185 | 0 | 29.05 | 30.75 | **1.075** |
| sample | LOW_VOL_BULL | 0.000 | 45,360 | **1** | 11.89 | 12.48 | 1.051 |
| factor_model | LOW_VOL_BULL | 0.982 | 101 | 0 | 11.55 | 11.96 | 1.036 |
| oas | LOW_VOL_BULL | 0.413 | 204 | 0 | 12.01 | 12.36 | 1.029 |
| ledoit_wolf | LOW_VOL_BULL | 0.381 | 217 | 0 | 12.14 | 12.24 | **1.010** |

**三条结论:**

1. **条件数差了 200 倍。** 样本协方差 46,000, 收缩后 185 到 231, 因子模型 101 到 108。**`is_singular = 1` 意味着这个矩阵在数学上不可逆 —— 优化器拿到它会给出荒唐的权重。**
2. **平静期各方法差别不大** (vol_bias 都在 1.01 到 1.05), **压力期拉开了**: 样本法 1.280, 收缩类 1.075 到 1.115。
3. **压力期起始的头两个月更极端 —— 而这一条要自己查, 上面这张表里看不到。** 全 regime 平均只有 1.28, 因为它把压力期的 8 个月都平均进去了, 而回看窗口在第三个月之后就已经吃进了新数据。只看市场刚切进压力期的那两个月:

```sql
SELECT method,
       COUNT(*)                                  AS n_obs,
       ROUND(AVG(condition_number), 0)           AS avg_condition_number,
       ROUND(AVG(predicted_vol_ann) * 100, 2)    AS avg_predicted_vol_pct,
       ROUND(AVG(realized_vol_ann_next) * 100, 2) AS avg_realized_vol_pct,
       ROUND(AVG(vol_bias_ratio), 3)             AS avg_vol_bias_ratio
FROM covariance_estimate
WHERE as_of_date IN ('2024-08-30', '2024-09-30')
GROUP BY method
ORDER BY avg_vol_bias_ratio DESC;
```

| method | n_obs | 条件数 | **vol_bias** |
|--------|-------|--------|--------------|
| **sample** | 2 | **47,463** | **1.932** |
| ledoit_wolf | 2 | 216 | 1.349 |
| oas | 2 | 183 | 1.314 |
| factor_model | 2 | 102 | 1.176 |

**样本法的 vol_bias 飙到 1.932 —— 实际风险接近预测的两倍。** 原因很直白: 250 天的回看窗口里全是平静期的数据, 模型根本不知道环境已经变了。**注意这只有 2 个观测, 说"接近两倍"可以, 说"精确是 1.93 倍"不行。**

**这就是 2008 和 2020 年不少量化基金爆仓的机制。** 不是模型"错了", 是模型的记忆太长, 而市场变得太快。

**拿到结果之后:** (a) 生产系统禁用 `sample` 方法 —— 它在任何 regime 下都不该被用。(b) 在 regime 切换的判定触发后, **手工把风险预算下调 30%**, 直到收缩估计吃进足够的新数据。(c) 把 `vol_bias_ratio` 做成日度监控指标, 连续两个月超过 1.3 就升级到风险委员会。

---

### Q21. 约束档位如何一步步削掉 alpha

**业务背景**

Director of Portfolio Construction 要回答投委会的一个尖锐问题: **"如果 Atlas 的复合信号在纸面上净 IR 是 1.32, 为什么我们的实盘产品只能做到 0.6?"**

答案是约束。但"约束削掉了 alpha"是一句正确的废话 —— 他需要把它拆成一条阶梯: 板块中性削掉多少、流动性约束削掉多少、完整生产授权又削掉多少。**每一级的代价, 对应买回来的是什么保障。** 只有把这笔账摊开, 投委会才能判断哪些约束值得放宽、哪些绝对不能动。这道题对应业务问题 Q5。

**标签:** Join + 标量子查询 | 难度: 中级 | 角色: Director of Portfolio Construction

**解题思路**

两表 join 加一个标量子查询。`backtest_run` 里已经存了同一个复合信号在四套约束下的回测结果, join `constraint_set` 把约束参数拿出来放在一起看。

**核心是那个标量子查询**: `(SELECT net_ir FROM backtest_run WHERE run_code = 'BT-ATLAS-COMPOSITE-UNCONSTRAINED')`。它取出无约束基准的净 IR, 让每一行都能算出"相对基准损失了百分之几"。

标量子查询在这里比 CTE + JOIN 更合适, 因为它返回的就是一个值, 不需要参与任何行的匹配。**判断标准: 如果子查询保证只返回一行一列, 用标量子查询; 否则用 CTE。**

`WHERE b.is_composite = 1 AND b.window_type = 'FULL'` 两个条件缺一不可 —— 前者排除单因子回测, 后者排除 walk-forward 的那四条。

**SQL**

```sql
SELECT cs.code                                             AS constraint_set,
       ROUND(cs.max_asset_weight * 100, 1)                 AS max_asset_weight_pct,
       ROUND(cs.max_sector_deviation * 100, 1)             AS max_sector_dev_pct,
       ROUND(cs.max_annual_turnover * 100, 0)              AS max_turnover_pct,
       ROUND(b.gross_return_ann * 100, 2)                  AS gross_ann_pct,
       ROUND(b.net_return_ann * 100, 2)                    AS net_ann_pct,
       ROUND(b.annual_turnover, 2)                         AS realised_turnover,
       ROUND(b.gross_ir, 2)                                AS gross_ir,
       ROUND(b.net_ir, 2)                                  AS net_ir,
       ROUND(100.0 * (1 - b.net_ir
             / (SELECT net_ir FROM backtest_run
                WHERE run_code = 'BT-ATLAS-COMPOSITE-UNCONSTRAINED')), 1) AS alpha_lost_vs_unconstrained_pct
FROM backtest_run b
JOIN constraint_set cs ON cs.id = b.constraint_set_id
WHERE b.is_composite = 1 AND b.window_type = 'FULL'
ORDER BY b.net_ir DESC;
```

**预期结果与业务结论**

返回 4 行, 构成一条清晰的阶梯:

| 约束档 | 单票% | 板块偏离% | 换手上限% | 毛 IR | **净 IR** | 实际换手 | **相对无约束损失** |
|--------|-------|----------|-----------|-------|-----------|---------|-------------------|
| UNCONSTRAINED | 10.0 | 100.0 | **2500** | 1.57 | **1.32** | 3.10 | 0.0% |
| SECTOR_NEUTRAL | 5.0 | **0.0** | 2000 | 1.28 | **1.05** | 2.85 | **20.5%** |
| LIQUIDITY_TIGHT | 3.0 | 3.0 | 2000 | 0.93 | **0.78** | 1.90 | **40.9%** |
| FULL_PRODUCTION | **2.5** | **2.0** | **120** | 0.70 | **0.61** | **1.15** | **53.8%** |

**每一级的代价与买到的东西:**

- **板块中性 (-20.5%):** 买到的是"不会变成一只伪行业基金"。信号本身有相当一部分收益来自行业押注, 掐掉它就掐掉了五分之一。**客户明确不想为行业押注付主动管理费, 这 20.5% 是合同义务, 不是选择。**
- **流动性约束 (再 -20.4%):** 买到的是"能真正建起仓位而不推飞价格"。注意实际换手从 2.85 降到 1.90 —— 约束不只削收益, 也削成本, 所以毛 IR 掉得比净 IR 更多。
- **完整生产授权 (再 -12.9%):** 主要来自 120% 的年换手上限。实际换手被压到 1.15, 已经顶到上限。

**总共 53.8%。** 这个数字应该让每个只看纸面回测的人清醒一下: **一个 paper 组合的 IR, 打对折才是它上线后的样子。**

**拿到结果之后:** 向投委会提一个具体建议 —— **换手上限从 120% 放宽到 200%, 预计可以拿回约 5 到 8 个百分点的 alpha, 代价是每年多约 30 bps 的交易成本。** 板块中性和流动性约束不建议动, 前者是合同义务, 后者是物理约束。这就是把 Q21 从一张表变成一个决策的方式。

---

### Q22. Atlas 产能复盘: 36 分钟到底做了什么

**业务背景**

**这是整份文档的收官题, 也是 CIO 唯一真正关心的那个问题。**

下周的投委会要决定是否给 Atlas 项目追加预算。CIO 不关心 RankIC 是什么, 他关心的是: **这 36 分钟里, Agent 到底做了多少实质工作? 它的探索深度和一个真人研究员比是深还是浅? 它在什么时候决定放弃、什么时候决定深挖, 这些决定合不合理?**

他见过太多"AI 提效"的演示, 最后发现只是把同一件事做了一百遍。他要看的是 **每个假设做了几种不同的诊断** —— 这个数字骗不了人。这道题对应业务问题 Q1。

**标签:** 多表聚合 + 相关子查询 | 难度: 中级 | 角色: Chief Investment Officer

**解题思路**

`agent_hypothesis` join `agent_step`, 按假设聚合。几个指标各有讲究:

- **`COUNT(DISTINCT s.step_type)` 是这道题的灵魂。** 它衡量的不是"做了多少步", 而是"做了多少 **种** 诊断"。一个 Agent 如果把同一种检验跑 20 遍, `n_steps` 会很好看, 但 `distinct_diagnostics` 会暴露它。
- `deepen_calls` 和 `abandon_calls` 分别数"决定深挖"和"决定放弃"的次数, 反映决策链的形状。
- `sql_queries` 用 `SUM(CASE WHEN s.sql_text IS NOT NULL ...)` 数实际发出的查询 —— `summarize` 步骤写的是备忘录, 不发查询。

最后的 `findings` 用 **相关子查询** 而不是再 join 一次 `agent_finding`。**原因是扇出**: 如果直接把 `agent_finding` join 进来, 每个 step 会和每个 finding 配对, 前面所有的 `COUNT` 和 `SUM` 全部会被放大。**相关子查询是避免多路 join 扇出的标准解法**, 代价是每行一次子查询, 但这里只有 10 行, 完全不是问题。

外层把列名逐个写出来而不是 `SELECT p.*`: 因为 CTE 里为了匹配外键多带了一列 `hypothesis_id`, 它是实现细节, 不该出现在给 CIO 看的结果里。

**SQL**

```sql
WITH per_hypothesis AS (
    SELECT h.id AS hypothesis_id, h.seq_no, f.code, h.verdict, h.n_steps, h.elapsed_minutes,
           COUNT(DISTINCT s.step_type)                                    AS distinct_diagnostics,
           SUM(CASE WHEN s.decision = 'deepen'  THEN 1 ELSE 0 END)        AS deepen_calls,
           SUM(CASE WHEN s.decision = 'abandon' THEN 1 ELSE 0 END)        AS abandon_calls,
           ROUND(SUM(s.cost_usd), 4)                                      AS cost_usd,
           SUM(CASE WHEN s.sql_text IS NOT NULL THEN 1 ELSE 0 END)        AS sql_queries
    FROM agent_hypothesis h
    JOIN factor f     ON f.id = h.factor_id
    JOIN agent_step s ON s.agent_hypothesis_id = h.id
    GROUP BY h.id, h.seq_no, f.code, h.verdict, h.n_steps, h.elapsed_minutes
)
SELECT p.seq_no, p.code, p.verdict, p.n_steps, p.elapsed_minutes,
       p.distinct_diagnostics, p.deepen_calls, p.abandon_calls, p.cost_usd, p.sql_queries,
       (SELECT COUNT(*) FROM agent_finding af WHERE af.agent_hypothesis_id = p.hypothesis_id) AS findings
FROM per_hypothesis p
ORDER BY p.seq_no;
```

**这里有一个容易一路错到底的细节, 单独点出来。** `agent_finding.agent_hypothesis_id` 是指向 **`agent_hypothesis.id`** 的外键, 不是指向 `seq_no`。本库里恰好 `id == seq_no` (ER 文档 §2.5 #26 有注明), 所以拿 `seq_no` 去匹配 **碰巧** 也对。**但那是运气, 不是正确。** 换一个 `id` 与业务序号不重合的库, 或者以后补跑第二轮 run 让 `seq_no` 从 1 重新开始, 这条子查询会静默给出错的计数 —— 不报错, 只是数字变小。所以 CTE 里多选一列 `h.id AS hypothesis_id`, 用它去匹配外键。**外键就该和外键指向的那一列比, 哪怕另一列现在看起来一样。**

**预期结果与业务结论**

返回 10 行:

| seq | code | 裁决 | 步数 | 分钟 | **诊断种类** | deepen | abandon | 成本$ | 查询数 | 发现数 |
|-----|------|------|------|------|-------------|--------|---------|-------|--------|--------|
| 1 | ACC_QUALITY | PROMOTED | 11 | 4.54 | **11** | 1 | 0 | 0.31 | 10 | 3 |
| 2 | EPS_REV_60D | PROMOTED | 12 | 4.49 | **11** | 2 | 0 | 0.36 | 11 | 3 |
| 3 | PEAD_SUE | PROMOTED | **13** | **4.68** | **12** | **3** | 0 | 0.36 | 12 | **4** |
| 4 | STR_REV_5D | PROMOTED | 11 | 3.86 | 10 | 2 | 0 | 0.29 | 10 | 3 |
| 5 | VOL_SKEW_ADJ | REJECTED | **7** | **2.66** | 6 | 1 | 1 | 0.22 | 6 | 3 |
| 6 | MICRO_VALUE | REJECTED | 8 | 2.37 | 7 | 2 | 1 | 0.25 | 7 | 3 |
| 7 | NEWS_SENT_7D | REJECTED | 9 | 3.70 | 8 | 1 | **2** | 0.25 | 8 | 3 |
| 8 | SEARCH_TREND | REJECTED | **6** | **2.50** | 6 | 1 | 1 | 0.18 | 5 | 3 |
| 9 | DIV_GROWTH_5Y | REJECTED | 8 | 3.40 | 7 | 1 | 1 | 0.21 | 7 | 3 |
| 10 | FCF_MARGIN_TTM | REJECTED | 9 | 3.52 | 8 | 2 | 1 | 0.23 | 8 | 3 |

**这张表回答了 CIO 的全部三个问题:**

**第一, 探索深度够不够?** 被推进的 4 个假设, 每个跑了 **10 到 12 种不同的诊断** (池子摸底、因子构造、IC 计算、分层、衰减、换手成本、正交性、regime、容量、多重检验、汇总)。**这就是一个人类研究员为一个候选因子该做的全套体检, 一样不少。** 而被否决的 6 个只跑了 6 到 8 种 —— 它在拿到否决证据后就停了。

**第二, 预算分配合不合理?** **被推进的 4 个假设占了总步数的 47 步 (50%) 和总成本的约 1.31 美元 (约 49%), 但它们只占假设数的 40%。** Agent 把预算集中投给了有希望的方向。最极端的对比是: `PEAD_SUE` 花了 13 步 4.68 分钟 (最多), 而 `SEARCH_TREND` 只花了 6 步 2.50 分钟 (最少) —— 后者在 `multiple_testing` 那一步拿到否决依据后就直接结束了。

**第三, 决策链合不合理?** `PEAD_SUE` 的 3 次 `deepen` 是全场最多的 —— 对应它先发现 IC 高得不合理、再去审计 PIT 口径、再重算的完整链条 (Q13)。**`NEWS_SENT_7D` 有 2 次 `abandon`**, 对应它在 regime 拆分上连续两次拿到否决证据。**每一次深挖和每一次放弃, 都能追溯到一个具体的数字。**

**总账:** 35.74 分钟, 94 步, 84 条 SQL 查询, 57.2 万 token, **2.66 美元**, 10 个假设收敛到 4 个。人工基线 **22 个 analyst 工作日**。

**拿到结果之后:** 给投委会的建议书里放三个数字: **(a) 时间 36 分钟 vs 22 天; (b) 成本 2.66 美元 vs 一个研究员一个月的薪资; (c) 最重要的一条 —— Atlas 发现了标准验证流水线三年来一直没发现的一个系统性缺陷 (Q19)。**

**第三条才是真正的论据。** 前两条只能证明它 **快**, 第三条证明它 **看得见人看不见的东西** —— 因为系统性地改写数据口径重跑一切, 对人来说是几天的工作量, 对它来说是几分钟。

---

## 业务问题与查询的映射

| 业务问题 | 对应查询 |
|----------|----------|
| **Q1. Atlas 一轮 36 分钟真的顶得上一个 analyst 一个月吗?** | Q15, **Q22** |
| **Q2. 这 10 个候选因子里, 哪 3 到 4 个真的值得推进?** | Q4, Q5, Q15, **Q17** |
| **Q3. 标准验证流水线的盲区在哪里?** | Q1, Q2, Q3, Q7, Q8, **Q13**, **Q14**, **Q19** |
| **Q4. 毛 alpha 里有多少能真正落到客户账户上?** | Q6, **Q11**, **Q12**, **Q18** |
| **Q5. 风险模型和约束设置如何影响可实现的 IR?** | Q9, Q10, **Q16**, **Q20**, **Q21** |

---

## 做完这 22 题之后

如果你从头到尾做完了, 你应该已经内化了下面这几条:

1. **一个 join 条件可以让 RankIC 虚增 4 倍 (0.0273 → 0.1101, Q13), 而任何显著性检验都抓不到它。**
2. **5.7% 的观测可以让长短腿价差从 8.71% 塌到 3.10% (Q14)。**
3. **同一个 t = 2.32, 是第 1 次尝试就显著, 是第 8 次尝试就不显著 (Q15)。**
4. **一个因子可以在分层、ICIR、显著性上全部合格, 却因为和已有因子相关性 0.93 而毫无价值 (Q5 + Q17)。**
5. **一个 t = 6.39、净 IR 2.62、通过全部 7 条验证规则的因子, 可以是彻头彻尾的假货 (Q19)。**
6. **纸面 IR 打对折, 才是它上线后的样子 (Q21)。**

**最后一条最重要:** 上面这六件事, 没有一件是靠"更强的模型"或者"更多的数据"解决的。**它们全部靠的是同一件事 —— 换一种问法, 再问一遍。** 这恰恰是 AI Agent 相对人类研究员最大的结构性优势: **穷尽所有的问法, 对人是几天, 对它是几分钟。**
