# Vantage Media CTV 广告投放分析 SQL 查询参考

> 业务背景, 公司画像, 行业科普, 术语表请见 `01-advertising_ctv_campaign_analytics_high_business_context-cn.md`. 表结构, 字段含义, 数据生成规则请见 `02-advertising_ctv_campaign_analytics_high_er_document-cn.md`.

本文档提供 20 个面向业务的 SQL 查询, 针对 `advertising_ctv_campaign_analytics_high` 数据集设计。每个查询都解决一个业务相关人员可能提出的实际问题, 模拟虚构 AdTech SaaS 公司 Vantage Media (核心产品 Booking Copilot, 一个 AutoML 驱动的 CTV 媒体采购优化平台) 的真实分析场景。

---

## 1. 如何使用本文档

这份文档是给你 (刚加入 Vantage Media 的数据分析实习生) 的。你已经读过业务背景文档和 ER 文档, 现在经理把这份查询清单交给你, 说"这周把这些跑一遍, 弄懂每一道"。它不是一份"能跑的 SQL 集合", 而是一份教学材料: SQL 是用来读懂和学会的, 不只是拿来执行的。

**每个查询都按统一的五段式组织**, 按顺序读下来你会经历一个真实分析师的思考过程:

- **业务背景**: 谁在问, 为什么现在问, 答案要支撑什么决策。把查询锚定到一个具体的人和一个具体的决定上。
- **分类 / 难度 / 业务角色**: 三个标签, 帮你判断这道题练的是哪类 SQL 技能、难度几何、服务公司里的哪个角色。
- **解题思路**: 在看 SQL 之前, 先想清楚要碰哪些表、怎么 JOIN、聚合的粒度是什么、为什么用 (或不用) CTE 和窗口函数、SQLite 有哪些坑。这一段是这份文档的核心教学价值。
- **SQL 代码**: 可直接在生成的 SQLite 库上运行的查询。关键子句有行内注释。
- **预期结果与业务结论**: 结果集长什么样, 关键数字对应业务背景文档里埋的哪个分布, 以及拿到数后分析师下一步该做什么。跑出数字只是分析的开始, 不是结束。

**关于参考日期 (AS_OF_DATE = `2025-10-31`)。** 数据集覆盖 2025-05-01 到 2025-10-31。所有涉及"最近 N 天""过去 X 周"的查询都用固定字符串 `'2025-10-31'` 作为"今天", 而不是 `DATE('now')`。这样在历史数据上跑结果才稳定可复现, 不会因为真实的当前日期跑出空结果。

**每个查询都能追溯到一个业务问题。** 业务背景文档第 5 节列了四个核心业务问题 (媒体采购盲区、客户差异化、归因难题、数据质量) 外加 AutoML 模型监控这条产品线。文档末尾有一张映射表, 把 20 个查询对回这些问题。如果一道查询找不到对应的业务需求, 它就不该出现在这里。

> **数据集规模:** 50,000 placements + 42,350 performance records + 50,000 ML predictions (每条同时挂 1 个 clearance classifier + 1 个配对 ROAS regressor, 共 3 代版本 shadow scoring)。支撑 AutoML 训练 + Shadow Scoring 评估 + BI 监控全链路。

---

## 2. 查询索引

| 编号 | 标题 | 业务角色 | 分类 | 难度 |
|------|------|----------|------|------|
| 1 | 网络清除率排名分析 | Operations | 聚合 + 排序 | 基础 |
| 2 | ML 模型清除率预测准确度评估 | Analyst | 聚合 + 连接 | 中级 |
| 3 | 高风险广告位识别（清除概率 < 0.65） | Manager | 连接 + 过滤 | 基础 |
| 4 | ROAS 预测 vs 实际对比分析 | Analyst | 连接 + 计算字段 | 中级 |
| 5 | 数据质量告警趋势分析（过去 30 天） | Operations | 日期范围 + 聚合 | 基础 |
| 6 | 广告主按 ROAS 排名（Top 10） | Executive | 聚合 + 排序 | 基础 |
| 7 | Q4 体育网络抢占率分析 | Manager | 日期过滤 + 聚合 | 中级 |
| 8 | 归因方法对 ROAS 的影响对比 | Analyst | 连接 + 分组 | 中级 |
| 9 | 预订提前期与清除率的相关性 | Analyst | 聚合 + 分组 | 中级 |
| 10 | 数据源 SLA 达标率分析 | Operations | 连接 + 日期计算 | 中级 |
| 11 | 每日广告位预订量趋势 | Manager | 日期聚合 | 基础 |
| 12 | 抢占导致的预算浪费量化 | Finance | 聚合 + 计算 | 中级 |
| 13 | 用户操作审计（最近 7 天 Top 活跃用户） | Operations | 聚合 + 排序 | 基础 |
| 14 | 模型版本迭代效果对比 | Executive | 窗口函数 + 聚合 | 高级 |
| 15 | 广告活动 ROI 分析（完整链路） | Finance | CTE + 多表连接 | 高级 |
| 16 | 网络月度清除率趋势（时间序列） | Analyst | 窗口函数 + 日期 | 中级 |
| 17 | P0 数据质量事件平均解决时间 (MTTR) | Manager | 日期计算 + 聚合 | 中级 |
| 18 | 清除率预测分布直方图数据 | Analyst | 聚合 + CASE + 窗口函数 | 中级 |
| 19 | 广告主名称模糊搜索 | Operations | 文本匹配 | 基础 |
| 20 | 跨网络类型 ROAS 对比（子查询） | Executive | 子查询 + 聚合 | 高级 |

---

## 3. 查询详情

### 查询 1: 网络清除率排名分析

**业务背景:**
媒体采购经理 Sarah 在每周规划会议前，需要查看各个电视网络和流媒体平台的实际清除率表现，以便决定下周应该优先预订哪些网络的广告位。清除率低的网络（如 ESPN）会导致大量预订被抢占，浪费团队时间和客户预算。她需要一个简单的排名列表，显示哪些网络最可靠（清除率高），哪些网络风险最大（清除率低）。

**分类:** 聚合 + 排序
**难度:** 基础
**业务角色:** Operations / Manager

**解题思路:**

这道题只需要两张表: 事实表 `ad_placement` 提供每条预订的状态, 维度表 `network` 提供网络名称和类型, 用 `network_id` 做一次 INNER JOIN 即可。清除率的口径是关键: 分母只算已结案的预订 (status 是 cleared 或 preempted), 要在 WHERE 里排除 status='pending', 否则尚未确认结果的位会把清除率算低。清除率本身用 `AVG(CASE WHEN status='cleared' THEN 1.0 ELSE 0.0 END)` 这个技巧算, 比先 COUNT 再相除更简洁。聚合粒度是"一个网络一行", 所以 GROUP BY 网络名称和类型即可, 不需要 CTE 或窗口函数。按清除率升序排, 风险最高的网络浮在最上面。

```sql
-- 按网络统计实际清除率，从低到高排序
-- 注意：与 Q9/Q14/Q16/Q18 保持一致，只统计已结案 (cleared/preempted) 的广告位，
-- 排除尚未确认结果的 pending 状态。
SELECT
    n.network_name AS 网络名称,
    n.network_type AS 网络类型,
    COUNT(*) AS 总预订数,
    SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS 实际播出数,
    SUM(CASE WHEN a.status = 'preempted' THEN 1 ELSE 0 END) AS 被抢占数,
    ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS 实际清除率
FROM ad_placement a
JOIN network n ON a.network_id = n.id
WHERE a.status IN ('cleared', 'preempted')
GROUP BY n.network_name, n.network_type
ORDER BY 实际清除率 ASC
LIMIT 15;
```

**预期结果说明:**
结果集显示每个网络的总预订数、实际播出数、被抢占数和清除率。ESPN 和 ESPN2 等体育网络会出现在列表顶部（清除率最低，~55-65%），而 HGTV、Hulu、Pluto TV 等非直播网络会出现在底部（清除率 >90%）。经理可以据此调整预订策略，减少对高风险网络的依赖。

---

### 查询 2: ML 模型清除率预测准确度评估

**业务背景:**
数据科学团队负责人需要评估最新部署的 ML 模型（v2.3.1）在清除率预测上的准确性。他们需要知道模型预测"会清除"（predicted_clearance_prob >= 0.5）和"会被抢占"（< 0.5）的准确率，以及与旧版本模型的对比。这个指标直接影响团队是否需要重新训练模型或调整特征工程策略。当前的产品门槛是 **88% 准确率**——这是因为基线（始终预测多数类）已经能在 ~85% 数据是 cleared 的不平衡场景下拿到 ~85%，所以模型必须比基线显著好（>3pp）才有产品价值；只有达到这个门槛，产品团队才会把预测分数暴露给媒体采购团队作为决策依据。

**分类:** 聚合 + 连接 + 条件逻辑
**难度:** 中级
**业务角色:** Analyst

**解题思路:**

这题要把预测 (`prediction_result`) 和真实结果 (`ad_placement.status`) 对齐, 再按模型版本算混淆矩阵。三张表: 预测表挂真实结果靠 `placement_id`, 挂模型版本靠 `model_version_id`。有一个容易踩的坑: `model_version_id` 只指向 clearance classifier (id 1/2/3), 但 model_version 表里还混着 roas regressor (id 4/5/6), 所以要加 `mv.model_type='clearance_classifier'` 把口径锁死, 和 Q14 保持一致。用一个 CTE 先把每条预测打上 True Positive / False Positive / False Negative / True Negative 标签 (预测概率是否 >=0.5 对照真实是否 cleared), 再在外层按版本聚合, 逻辑分两层更清晰。聚合粒度是"一个模型版本一行"。注意 shadow scoring 让三代版本评分同一批数据, 所以每版本样本量接近 (约 16,600), 对比才公平。

```sql
-- 评估模型预测准确度（混淆矩阵）
WITH prediction_evaluation AS (
    SELECT
        p.prediction_code,
        p.predicted_clearance_prob,
        CASE
            WHEN a.status = 'cleared' THEN 1
            WHEN a.status = 'preempted' THEN 0
            ELSE NULL
        END AS actual_cleared,
        CASE
            WHEN p.predicted_clearance_prob >= 0.5 AND a.status = 'cleared' THEN 'True Positive'
            WHEN p.predicted_clearance_prob >= 0.5 AND a.status = 'preempted' THEN 'False Positive'
            WHEN p.predicted_clearance_prob < 0.5 AND a.status = 'cleared' THEN 'False Negative'
            WHEN p.predicted_clearance_prob < 0.5 AND a.status = 'preempted' THEN 'True Negative'
        END AS prediction_outcome,
        mv.version_code AS 模型版本
    FROM prediction_result p
    JOIN ad_placement a ON p.placement_id = a.id
    JOIN model_version mv ON p.model_version_id = mv.id
    WHERE a.status IN ('cleared', 'preempted')
      AND mv.model_type = 'clearance_classifier'  -- 与 Q14 口径一致，明确只评估分类器
)
SELECT
    模型版本,
    COUNT(*) AS 总预测数,
    SUM(CASE WHEN prediction_outcome IN ('True Positive', 'True Negative') THEN 1 ELSE 0 END) AS 正确预测数,
    ROUND(AVG(CASE WHEN prediction_outcome IN ('True Positive', 'True Negative') THEN 1.0 ELSE 0.0 END), 4) AS 准确率,
    SUM(CASE WHEN prediction_outcome = 'True Positive' THEN 1 ELSE 0 END) AS TP,
    SUM(CASE WHEN prediction_outcome = 'False Positive' THEN 1 ELSE 0 END) AS FP,
    SUM(CASE WHEN prediction_outcome = 'False Negative' THEN 1 ELSE 0 END) AS FN,
    SUM(CASE WHEN prediction_outcome = 'True Negative' THEN 1 ELSE 0 END) AS TN
FROM prediction_evaluation
GROUP BY 模型版本
ORDER BY 模型版本 DESC;
```

**预期结果说明:**
结果集显示每个模型版本的准确率和混淆矩阵 (shadow scoring 同分布对比,每版本 n ≈ **16,600**):

| 版本 | 准确率 | TP | FP | FN | TN |
|---|---|---|---|---|---|
| v2.1.5 | ~86.0% | ~13,900 | ~2,030 | ~270 | ~470 |
| v2.2.0 | ~85.8% | ~13,900 | ~2,070 | ~270 | ~430 |
| v2.3.1 | ~85.6% | ~13,900 | ~2,100 | ~270 | ~410 |

**业务结论**:三个版本都**未达 88% 产品门槛** (实际全部约 86.0%,差 2pp)。这意味着即使是最新模型也只比"始终预测 cleared"的多数类 baseline (~85.5%) 好 ~0.5pp,**预测分数还不能正式暴露给媒体采购团队作为决策依据**——团队需要继续优化 (如引入新特征、模型架构升级、对 preempted 类做 oversampling 等)。

**为什么三版本准确率几乎持平?** 数据扩到 50K 后,样本量增大让 noise smoothing 收敛到极小,三个版本在 `predicted_clearance_prob` 的均值/方差上趋于一致;而**类别极度不均衡 (cleared 占 85%)** 让 majority-class baseline 主导了整体准确率,model_noise 收窄无法突破这个上限。**这正是 Vantage Media Data Science 团队当前的真实痛点 — 应转向算法层 (class weighting / focal loss / 重采样) 而不是继续调参**。

**混淆矩阵解读**: cleared 占 ~85% 的不平衡数据让模型严重偏向预测多数类——TP 远多于 TN,FP (preempted 被错判为 cleared) 显著多于 FN。如果业务关心的是"识别会被抢占的高风险位",更适合用 **Recall on preempted** = TN / (TN + FP) ≈ 18% (而不是整体准确率),这是 v2 模型应该重点优化的方向。这也对应 Q14 的递进叙事:单靠 noise 收窄无法解决 class imbalance,需要算法层改动。

---

### 查询 3: 高风险广告位识别（清除概率 < 0.65）

**业务背景:**
媒体采购团队主管每天早上需要查看当天和未来 7 天内所有预测清除概率低于 0.65 的"高风险广告位"。这些广告位有超过 35% 的概率被抢占，需要主管与客户沟通风险，或者考虑更换到更可靠的网络和时段。这个列表帮助团队从"被动救火"转变为"主动风险管理"，减少客户投诉和预算浪费。

**分类:** 连接 + 过滤
**难度:** 基础
**业务角色:** Manager

**解题思路:**

这是一个明细列表查询, 不做聚合, 输出的是"需要人逐条处理的高风险位"。主表是 `ad_placement`, 用 `placement_id` 挂上预测表拿到预测清除概率, 再分别 JOIN advertiser、network、daypart 把代码翻译成人能读的名字。过滤条件有两层含义: `predicted_clearance_prob < 0.65` 圈出模型认为风险高的位, `status='pending'` 圈出尚未确认结果、还来得及干预的位 (已经 cleared 或 preempted 的没有干预价值)。日期窗用固定参考日 `'2025-10-29'` 往后 7 天, 模拟主管站在那一天看未来一周。因为 pending 位只出现在快照末期, 这个列表天然很短 (约 80 条), 正是 Manager 视图"少而精、逐条联系客户"的设计意图。

```sql
-- 识别高风险广告位（清除概率 < 0.65）
SELECT
    a.placement_code AS 广告位代码,
    adv.advertiser_name AS 广告主,
    n.network_name AS 网络,
    d.daypart_name AS 时段,
    DATE(a.scheduled_air_time) AS 计划播出日期,
    a.booked_cpm AS 预订CPM,
    p.predicted_clearance_prob AS 预测清除概率,
    p.predicted_roas AS 预测ROAS,
    p.confidence_level AS 置信度,
    ROUND((1 - p.predicted_clearance_prob) * 100, 1) || '%' AS 抢占风险
FROM ad_placement a
JOIN prediction_result p ON a.id = p.placement_id
JOIN advertiser adv ON a.advertiser_id = adv.id
JOIN network n ON a.network_id = n.id
JOIN daypart d ON a.daypart_id = d.id
WHERE p.predicted_clearance_prob < 0.65
  AND a.status = 'pending'
  -- 参考日期：使用数据快照截止日期 '2025-10-31'，模拟"今天"是 10/29 时主管的视角
  AND DATE(a.scheduled_air_time) BETWEEN DATE('2025-10-29') AND DATE('2025-10-29', '+7 days')
ORDER BY p.predicted_clearance_prob ASC, a.scheduled_air_time ASC
LIMIT 50;
```

**预期结果说明:**
结果集列出所有高风险广告位,按清除概率从低到高排序。pending 队列在本数据集中**~250 条** (仅出现在快照末期 2025-10-29 → 2025-10-31),满足"低预测清除率 + 仍 pending"的高风险位约 **~80 条**。这正是 Manager 视图的设计目的——少数高风险事件需要逐条联系客户处理。ESPN/ESPN2/FOX 黄金时段的 NFL 时段广告位会出现在顶部 (清除概率 0.30-0.55)。

---

### 查询 4: ROAS 预测 vs 实际对比分析

**业务背景:**
产品团队需要向公司高管展示"ML 驱动的 ROAS 预测"功能的价值。他们需要计算预测 ROAS 与实际 ROAS 的平均绝对百分比误差（MAPE），并按广告主类别细分。如果 MAPE 低于 25%，说明预测足够可靠，可以作为客户决策的参考；如果 MAPE 高于 35%，说明需要改进模型。这个分析结果将直接决定产品路线图中是否要加大对 ROAS 预测功能的投入。

**分类:** 连接 + 计算字段 + 聚合
**难度:** 中级
**业务角色:** Analyst

**解题思路:**

这题算 ROAS 预测的 MAPE (平均绝对百分比误差), 按广告主类别细分。链路是 `prediction_result` 经 `placement_id` 连 `ad_placement`, 再连 `performance_actual` 拿真实 ROAS, 然后顺着 advertiser 连到 advertiser_category。这里 INNER JOIN 到 performance_actual 有一个隐含效果: 只有 cleared 的位才有 actual, 所以样本自动限定在已播出的位上, 符合"只对有真值的预测算误差"。MAPE 用 `AVG(ABS(predicted_roas - roas) / roas)` 算, 分母用 `NULLIF(roas, 0)` 加 `WHERE roas > 0` 双保险, 避免除零。聚合粒度是"一个类别一行"。要注意一个解读陷阱: 因为 `predicted_roas` 在生成时锚定到真实 ROAS 加版本噪声, 各类别的 MAPE 会很接近, 类别差异在这道题里看不出来。想看真正的梯度, 应该按模型版本 (roas regressor) 分组, 会看到 12% 到 8% 到 5% 的下降。

```sql
-- ROAS 预测准确度分析（MAPE）
SELECT
    ac.category_name AS 广告主类别,
    COUNT(*) AS 样本数,
    ROUND(AVG(p.predicted_roas), 2) AS 平均预测ROAS,
    ROUND(AVG(pa.roas), 2) AS 平均实际ROAS,
    ROUND(AVG(ABS(p.predicted_roas - pa.roas)), 2) AS 平均绝对误差,
    ROUND(AVG(ABS(p.predicted_roas - pa.roas) / NULLIF(pa.roas, 0)) * 100, 2) || '%' AS MAPE
FROM prediction_result p
JOIN ad_placement a ON p.placement_id = a.id
JOIN performance_actual pa ON a.id = pa.placement_id
JOIN advertiser adv ON a.advertiser_id = adv.id
JOIN advertiser_category ac ON adv.category_id = ac.id
WHERE pa.roas > 0  -- 排除 ROAS 为 0 的样本以保证 MAPE 计算稳定
GROUP BY ac.category_name
ORDER BY 样本数 DESC;
```

**预期结果说明:**
结果集显示每个广告主类别的 ROAS 预测误差。整体 MAPE 在 ~7-10% 之间（v2.3.1 主导），符合业务"MAPE < 25%"的目标。

> **解读 caveat**: 由于 `predicted_roas` 在生成时锚定到 `actual_roas` + 版本噪声（详见 ER 文档"模型预测准确度递增"段的设计简化），所有类别 MAPE 大致均匀，落在 ~8% ± 1pp 的窄区间内。**类别 × 网络维度的差异在本查询里看不到** —— 因为 `predicted_roas` 的误差仅由 `model_noise` 决定，与类别无关。
>
> 如果想看 **按模型版本的 MAPE 差异**，应在本查询里加 `mv.version_code` 维度——会看到 v2.1.5 ~12% / v2.2.0 ~8% / v2.3.1 ~5%（这是数据生成器里 model_noise 真正发挥作用的地方）。但每个版本内部，各类别仍然均匀。
>
> 如果想看 **类别 × 网络的 ROAS 矩阵差异**（"Health on HGTV 1.2-1.8x 而 on ESPN 0.5-0.9x"），应该直接查 `performance_actual.roas`——这是数据生成器里 ROAS_MATRIX 真正落地的位置，见 ER doc 数据生成规则 4。

---

### 查询 5: 数据质量告警趋势分析（过去 30 天）

**业务背景:**
数据工程团队负责人需要在每月的运维回顾会上展示数据质量状况。他需要统计过去 30 天内每天触发了多少次 P0/P1/P2 级别的数据质量告警，以及告警的解决率。如果 P0 告警（阻塞下游的严重问题）频繁出现，说明上游数据源质量在恶化，需要与供应商沟通改进。这个趋势图帮助团队识别数据质量是在改善还是在恶化。

**分类:** 日期范围 + 聚合 + 分组
**难度:** 基础
**业务角色:** Operations

**解题思路:**

这题画的是数据质量的日趋势, 按严重程度拆开看。两张表: `data_quality_log` 是每次检查的结果, JOIN `data_quality_rule` 拿到规则的 severity (P0/P1/P2)。聚合粒度是"一天一个严重程度一行", 所以 GROUP BY 用 `DATE(run_timestamp)` 和 severity 两列。失败数、告警数都用条件求和 (SUM CASE) 在同一次扫描里算出来。平均解决时长是个时间差, SQLite 里没有原生的小时差函数, 要用 `(JULIANDAY(resolved_at) - JULIANDAY(run_timestamp)) * 24` 把儒略日差转成小时, 且只对已解决 (resolved_at 非空) 的记录算, 用 CASE 把未解决的排除在平均之外。日期窗口用 `DATE('2025-10-31', '-30 days')` 回看 30 天。

```sql
-- 数据质量告警趋势（按严重程度分组）
SELECT
    DATE(l.run_timestamp) AS 日期,
    r.severity AS 严重程度,
    COUNT(*) AS 检查次数,
    SUM(CASE WHEN l.status = 'failed' THEN 1 ELSE 0 END) AS 失败次数,
    SUM(CASE WHEN l.alert_fired THEN 1 ELSE 0 END) AS 告警次数,
    SUM(CASE WHEN l.resolved_at IS NOT NULL THEN 1 ELSE 0 END) AS 已解决数,
    ROUND(AVG(CASE WHEN l.resolved_at IS NOT NULL
                   THEN (JULIANDAY(l.resolved_at) - JULIANDAY(l.run_timestamp)) * 24
                   ELSE NULL END), 2) AS 平均解决时长_小时
FROM data_quality_log l
JOIN data_quality_rule r ON l.rule_id = r.id
-- 参考日期：数据快照截止 '2025-10-31'，统计回看 30 天
WHERE l.run_timestamp >= DATE('2025-10-31', '-30 days')
GROUP BY DATE(l.run_timestamp), r.severity
ORDER BY DATE(l.run_timestamp) DESC, r.severity ASC;
```

**预期结果说明:**
结果集显示每天每个严重程度级别的告警情况。P0 告警应该非常少（每月 < 5 次），P1 告警偶尔出现（每月 10-20 次），P2 告警较常见。平均解决时长应在 2-4 小时内（P0 目标 < 2 小时，P1 < 4 小时）。

---

### 查询 6: 广告主按 ROAS 排名（Top 10）

**业务背景:**
CEO 在季度董事会上需要展示"哪些客户的电视广告投放效果最好"。CFO 关心的是客户投入的每一美元广告费带来了多少收入回报。高 ROAS 客户是公司的优质客户，值得继续深化合作；低 ROAS 客户可能需要优化投放策略或调整定价。这个 Top 10 列表是公司客户健康度的核心指标之一，直接影响续约率和增长策略。

**分类:** 聚合 + 排序
**难度:** 基础
**业务角色:** Executive

**解题思路:**

这题给广告主按 ROAS 排名。四张表串起来: advertiser 连 category 拿行业, 连 ad_placement 拿到该客户的所有位, 再连 performance_actual 拿花费和收入。INNER JOIN 到 performance_actual 意味着只统计已播出 (cleared) 的位, 这正是算真实回报该用的口径。这里有个重要的 SQL 教学点: ROAS 有两种算法。`AVG(roas)` 是把每条记录的 ROAS 取平均, 会被小订单的极端值带偏; `SUM(收入)/SUM(花费)` 是按花费加权的整体 ROAS, 才是 CFO 关心的真实回报。两个都列出来对照, 但用整体 ROAS 排序。`HAVING COUNT(DISTINCT a.id) >= 10` 过滤掉投放太少、样本不可信的客户。

```sql
-- Top 10 ROAS 表现最佳的广告主
SELECT
    adv.advertiser_name AS 广告主,
    ac.category_name AS 行业类别,
    COUNT(DISTINCT a.id) AS 投放广告位数,
    ROUND(SUM(pa.spend_usd), 2) AS 总花费_美元,
    ROUND(SUM(pa.attributed_revenue_usd), 2) AS 总归因收入_美元,
    ROUND(AVG(pa.roas), 2) AS 平均ROAS,
    ROUND(SUM(pa.attributed_revenue_usd) / SUM(pa.spend_usd), 2) AS 整体ROAS
FROM advertiser adv
JOIN advertiser_category ac ON adv.category_id = ac.id
JOIN ad_placement a ON adv.id = a.advertiser_id
JOIN performance_actual pa ON a.id = pa.placement_id
-- 注意：performance_actual.finalized_at 在 schema 中已是 NOT NULL，
-- 因此不需要额外过滤；通过 JOIN 已经只保留有归因数据的 placement。
GROUP BY adv.advertiser_name, ac.category_name
HAVING COUNT(DISTINCT a.id) >= 10  -- 至少投放过 10 个广告位
ORDER BY 整体ROAS DESC
LIMIT 10;
```

**预期结果说明:**
结果集展示 ROAS 最高的 10 个广告主。Health & Wellness 和 Apparel 类别的客户在流媒体平台上的 ROAS 可能达到 1.6-2.0x。Finance 客户在 NBC/CBS 黄金时段的 ROAS 在 1.2-1.5x。这些客户是公司的明星客户，应该优先服务。

---

### 查询 7: Q4 体育网络抢占率分析

**业务背景:**
媒体采购经理在 Q4（10-12 月）规划时需要特别小心体育网络（ESPN、FOX）的高抢占风险。由于 NFL 常规赛、季后赛等大型直播赛事，这些网络的广告位经常被临时抢占。经理需要量化这个风险：Q4 期间体育网络的实际抢占率是多少？与 Q3 相比恶化了多少？这个数据帮助团队决定是否要减少对体育网络的依赖，或者为客户预留更多的"备用预算"以应对抢占。

**分类:** 日期过滤 + 聚合 + 对比
**难度:** 中级
**业务角色:** Manager

**解题思路:**

这题要把同一批体育网络的 Q3 和 Q4 抢占率并排放, 看 NFL 赛季把抢占率推高了多少。先用一个 CTE `quarterly_stats` 算出每个网络每个季度的抢占率, 范围限定在受 NFL 直接影响的三个网络 (ESPN/ESPN2/FOX), 季度用 `strftime('%m', scheduled_air_date)` 取月份再映射。季度的判断要把月份转成整数 (CAST AS INTEGER) 再比较, 这是 SQLite 处理 strftime 字符串结果的常见写法。外层做一次"行转列": 用 `MAX(CASE WHEN 季度='Q3' THEN 抢占率 END)` 和对应的 Q4 版本, 把两行 (Q3 行、Q4 行) 压成一行两列, 这样恶化幅度可以直接相减。聚合粒度最终是"一个网络一行"。注意 Q3 本身已经含 9 月开赛的影响, 所以 Q3 到 Q4 的差是赛季深入 (10 月赛事密集) 的额外恶化。

```sql
-- Q4 体育网络抢占率分析（与 Q3 对比）
-- 范围：ER 文档定义受 NFL Regular Season 直接影响的体育向网络 = ESPN/ESPN2/FOX
WITH quarterly_stats AS (
    SELECT
        n.network_name AS 网络名称,
        CASE
            WHEN CAST(strftime('%m', a.scheduled_air_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
            WHEN CAST(strftime('%m', a.scheduled_air_date) AS INTEGER) BETWEEN 10 AND 12 THEN 'Q4'
        END AS 季度,
        COUNT(*) AS 总预订数,
        SUM(CASE WHEN a.status = 'preempted' THEN 1 ELSE 0 END) AS 抢占数,
        ROUND(AVG(CASE WHEN a.status = 'preempted' THEN 1.0 ELSE 0.0 END), 4) AS 抢占率
    FROM ad_placement a
    JOIN network n ON a.network_id = n.id
    WHERE n.network_code IN ('ESPN', 'ESPN2', 'FOX')
      AND a.status IN ('cleared', 'preempted')
      AND CAST(strftime('%m', a.scheduled_air_date) AS INTEGER) BETWEEN 7 AND 12
    GROUP BY n.network_name, 季度
)
SELECT
    网络名称,
    MAX(CASE WHEN 季度 = 'Q3' THEN 抢占率 END) AS Q3抢占率,
    MAX(CASE WHEN 季度 = 'Q4' THEN 抢占率 END) AS Q4抢占率,
    ROUND(MAX(CASE WHEN 季度 = 'Q4' THEN 抢占率 END) - MAX(CASE WHEN 季度 = 'Q3' THEN 抢占率 END), 4) AS 恶化幅度
FROM quarterly_stats
GROUP BY 网络名称
ORDER BY Q4抢占率 DESC;
```

**预期结果说明:**
结果集显示体育网络在 Q4 的抢占率显著上升。注意:Q3 已包含 9 月 NFL 赛季开赛的影响 (NFL 季节 9/5 → 10/31 是数据集明确的事件窗口)。

| 网络 | Q3 抢占率 | Q4 抢占率 | 恶化幅度 |
|------|----------|----------|---------|
| ESPN | ~23% | ~57% | +34 pp |
| ESPN2 | ~25% | ~63% | +38 pp |
| FOX | ~20% | ~54% | +34 pp |

Q3 → Q4 抢占率差异在 30-40 个百分点之间,单网络差异源自随机 NFL 罚分 (uniform 0.15-0.20) + 网络基础清除率波动。经理据此可以向客户预警风险,特别是 10 月体育节目密集期的广告位需要 +50% 备用预算。

---

### 查询 8: 归因方法对 ROAS 的影响对比

**业务背景:**
数据分析师需要评估不同归因合作伙伴提供的 ROAS 数据是否一致。AttributionPro 使用 pixel matching（精确），Nielsen 使用 panel extrapolation（估算），ImpactTracker 使用 IP matching（中等精度）。如果三个合作伙伴对同一批广告位报告的 ROAS 差异超过 30%，说明归因方法存在系统性偏差，需要与合作伙伴沟通校准。这个分析帮助团队判断哪个合作伙伴的数据更可靠，是否需要更换供应商。

**分类:** 连接 + 分组 + 聚合
**难度:** 中级
**业务角色:** Analyst

**解题思路:**

这题对比四个归因 partner 报出的 ROAS 是否一致。只需两张表: `performance_actual` 提供每条效果记录, JOIN `attribution_partner` 拿到 partner 名称和归因方法。一次 GROUP BY (partner + method) 就够, 不需要 CTE 或窗口函数。这道题能成立的前提是干净的对照: 因为 partner 是随机分配到 placement 的, 四个 partner 覆盖的底层投放分布相同, 所以 ROAS 的差异纯粹来自归因方法 (pixel / IP / panel) 的系统性偏差, 而不是某个 partner 恰好分到了好位。看到两个 pixel partner 的 ROAS 几乎一样, 就能确认差异来自方法而非供应商。AVG、MIN、MAX 一起列出来能直观看到每种方法的离散程度。

```sql
-- 不同归因方法的 ROAS 对比
SELECT
    ap.partner_name AS 归因合作伙伴,
    ap.attribution_method AS 归因方法,
    COUNT(*) AS 样本数,
    ROUND(AVG(pa.roas), 2) AS 平均ROAS,
    ROUND(MIN(pa.roas), 2) AS 最小ROAS,
    ROUND(MAX(pa.roas), 2) AS 最大ROAS,
    ROUND(AVG(pa.attributed_conversions), 1) AS 平均转化数,
    ROUND(AVG(pa.attribution_window_days), 1) AS 平均归因窗口_天
FROM performance_actual pa
JOIN attribution_partner ap ON pa.attribution_partner_id = ap.id
GROUP BY ap.partner_name, ap.attribution_method
ORDER BY 平均ROAS DESC;
```

**预期结果说明:**
结果集按平均 ROAS 降序显示 4 个归因合作伙伴的对比 (数据生成器对每条 performance_actual 的
ROAS 叠加了 *归因方法系数*: `pixel_match ×1.10` / `ip_match ×1.00` / `panel_extrapolation ×0.80`,
故 partner 维度出现稳定梯度):

| 归因合作伙伴 | 归因方法 | 平均 ROAS (约) |
|--------------|----------|----------------|
| ConversionPixel | pixel_match | ~1.32 |
| AttributionPro | pixel_match | ~1.32 |
| ImpactTracker | ip_match | ~1.20 |
| Nielsen Digital | panel_extrapolation | ~0.96 |

**业务结论**: pixel matching (精确像素匹配) 系统性地报出最高 ROAS (~1.32x),IP matching 居中 (~1.20x),
而 **panel extrapolation (Nielsen 面板外推) 系统性低估 ROAS** (~0.96x, 比 pixel 低约 27%)。
两个 pixel 合作伙伴口径一致,佐证差异来自归因*方法*而非单个供应商。这超过 30% 的口径差异
提示: 跨 partner 对比 ROAS 时必须先按归因方法归一化,否则会错误地判定某些投放"不赚钱"。

> **方法学 caveat**: 四个 partner 的 `attribution_partner_id` 是随机分配到 placement 的,
> 因此它们覆盖的是*同分布*的底层投放——ROAS 差异纯粹来自归因方法系数,不含选择偏差。
> 这正是用来演示"归因方法系统性偏差"的干净对照。各 network_type 的平均 ROAS 不受影响
> (4 个 partner 的方法系数加权平均 = 1.00)。

---

### 查询 9: 预订提前期与清除率的相关性

**业务背景:**
数据分析师在优化 ML 模型特征时，需要验证"预订提前期"是否是清除率的有效预测因子。业务假设是：提前 30-60 天预订的广告位更容易被抢占（因为电视台还不确定那个时段会播什么内容），而提前 3-7 天预订的广告位清除率更高（因为时段已经确定）。这个分析帮助团队决定是否要鼓励客户"晚预订"以提高清除率，或者在 ML 模型中加大 booking_lead_days 特征的权重。

**分类:** 聚合 + 分组 + 趋势分析
**难度:** 中级
**业务角色:** Analyst

**解题思路:**

这题验证一个业务假设: 订得越早越容易被抢占。只用 `ad_placement` 一张表, 不需要 JOIN。核心技巧是用 CASE 把连续的 `booking_lead_days` 切成 5 个分桶 (7 天内、8 到 14 天、依此类推)。SQLite 不能在 GROUP BY 里引用 SELECT 的列别名, 所以分桶的 CASE 表达式要在 SELECT 和 GROUP BY 里各写一遍 (内容必须完全一致)。清除率同样用 `AVG(CASE WHEN cleared)` 算, 并且和 Q1 一样只统计已结案的位。排序是个小坑: 直接按分桶文字排会得到字典序 (乱序), 要用 `ORDER BY MIN(booking_lead_days)` 让分桶按真实的天数顺序排列, 才能看出清除率单调下降的趋势。

```sql
-- 预订提前期与清除率的相关性分析
SELECT
    CASE
        WHEN a.booking_lead_days <= 7 THEN '≤7天'
        WHEN a.booking_lead_days <= 14 THEN '8-14天'
        WHEN a.booking_lead_days <= 30 THEN '15-30天'
        WHEN a.booking_lead_days <= 60 THEN '31-60天'
        ELSE '>60天'
    END AS 预订提前期,
    COUNT(*) AS 总预订数,
    SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS 实际播出数,
    ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS 清除率,
    ROUND(AVG(a.booked_cpm), 2) AS 平均CPM
FROM ad_placement a
WHERE a.status IN ('cleared', 'preempted')
GROUP BY
    CASE
        WHEN a.booking_lead_days <= 7 THEN '≤7天'
        WHEN a.booking_lead_days <= 14 THEN '8-14天'
        WHEN a.booking_lead_days <= 30 THEN '15-30天'
        WHEN a.booking_lead_days <= 60 THEN '31-60天'
        ELSE '>60天'
    END
ORDER BY MIN(a.booking_lead_days) ASC;
```

**预期结果说明:**
结果集显示 5 个提前期分桶,清除率随提前期增加**单调下降** (数据生成器对 booking_lead_days
施加分级清除率加成: ≤7 +7.5pp / 8-14 +3.5pp / 15-30 +0.5pp / 31-60 -3pp / >60 -6pp
(加权均值 ≈ +2.1pp, 与旧版 ≤7 +5pp 单档持平, 保证整体清除率仍 ~85%),
并在 lead 取值集合里引入 75/90 天,使 `>60天` 桶非空):

| 预订提前期 | 总预订数 | 清除率 (约) |
|------------|----------|-------------|
| ≤7 天 | ~16,850 | ~0.899 |
| 8-14 天 | ~7,800 | ~0.863 |
| 15-30 天 | ~11,950 | ~0.835 |
| 31-60 天 | ~8,070 | ~0.805 |
| >60 天 | ~5,090 | ~0.787 |

≤7 天预订的广告位清除率最高 (~90%),>60 天预订的最低 (~79%),呈清晰的单调下降趋势。
这验证了业务假设——提前期是清除率的有效预测因子,应该在 ML 模型中强化这个特征,
并可建议客户对关键广告位"晚预订"以降低被抢占风险。

---

### 查询 10: 数据源 SLA 达标率分析

**业务背景:**
数据运营团队每周需要向上游数据供应商（电视网络、归因合作伙伴）汇报 SLA 达标情况。例如，ESPN 承诺每天早上 6:00 前交付前一天的播出日志，容忍 2 小时延迟（SLA 阈值）。如果 ESPN 在过去 30 天内有超过 10% 的天数延迟超过 8:00，说明 SLA 严重违约，需要升级到供应商管理层。这个分析帮助团队量化供应商可靠性，并在续约谈判中提供数据支持。

**分类:** 连接 + 日期计算 + 聚合
**难度:** 中级
**业务角色:** Operations

**解题思路:**

这题算每个数据源近 30 天的 SLA 达标率。两张表逻辑上按 `source_name` 对应 (它们之间没有硬外键, 是约定的等值连接)。这里 JOIN 的方向和谓词位置是关键教学点: 用 `data_source_sla LEFT JOIN ingestion_metadata`, 并且把 30 天的日期过滤放在 ON 子句里而不是 WHERE 里。原因是如果放 WHERE, 一个近期完全没有采集记录的数据源会因为右表全是 NULL 而被整行过滤掉; 放在 ON 里能保留这个源, 让它显示成达标率 0%, 这正是运维要看到的信号。达标判断要算实际到达时间和"当天预期到达时刻"的差: 用 `julianday(ingested_at) - julianday(ingestion_date) - expected_delivery_hour/24.0` 再乘 24 转成小时, 这样能正确处理跨日的延迟。

```sql
-- 数据源 SLA 达标率分析
-- SLA 定义：实际到达时间 vs ("当天预期到达时刻") 的时间差不超过 sla_threshold_hours
-- 实际到达时间用 ingested_at（绝对 datetime）和 expected = date(ingestion_date) + expected_delivery_hour 比较
-- 用 julianday 计算小时差，正确处理跨日延迟。
-- 参考日期：'2025-10-31'，回看 30 天
SELECT
    sla.source_name AS 数据源,
    sla.source_type AS 数据源类型,
    sla.expected_delivery_hour AS 预期交付时刻,
    sla.sla_threshold_hours AS SLA阈值_小时,
    COUNT(im.id) AS 采集天数,
    SUM(CASE
        WHEN (julianday(im.ingested_at)
              - julianday(im.ingestion_date) - sla.expected_delivery_hour / 24.0
             ) * 24 <= sla.sla_threshold_hours
        THEN 1 ELSE 0
    END) AS SLA达标天数,
    ROUND(
        SUM(CASE
            WHEN (julianday(im.ingested_at)
                  - julianday(im.ingestion_date) - sla.expected_delivery_hour / 24.0
                 ) * 24 <= sla.sla_threshold_hours
            THEN 1.0 ELSE 0.0
        END) / NULLIF(COUNT(im.id), 0),
        4
    ) AS SLA达标率
FROM data_source_sla sla
-- 谓词放在 ON 子句中，保留没有近期采集记录的数据源（SLA 达标率 = 0% 而不是被丢弃）
LEFT JOIN ingestion_metadata im
       ON sla.source_name = im.source_name
      AND im.ingestion_date >= DATE('2025-10-31', '-30 days')
GROUP BY sla.source_name, sla.source_type, sla.expected_delivery_hour, sla.sla_threshold_hours
ORDER BY SLA达标率 ASC;
```

**预期结果说明:**
结果集显示每个数据源近 30 天的 SLA 达标率(2025-10-01 → 2025-10-31):

| 数据源 | 采集天数 | SLA 达标率 |
|--------|---------|----------|
| Nielsen Panel Data | ~23 | ~100% (panel 数据有 48h 宽容窗,延迟容忍度高) |
| AttributionPro API | ~20 | ~85% (典型 attribution API 表现) |
| ESPN Delivery Log | ~25 | ~64% (Q4 NFL 期间网络日志高峰,延迟明显) |
| NBC Delivery Log | ~21 | ~52% (类似 ESPN,需要供应商跟进) |
| Hulu Impression Feed | ~24 | ~0% (**数据源 SLA 与上游真实交付时刻错配的已知历史问题**,SLA 配置 expected=4h 但供应商实际中午前后交付——典型的"业务运营和数据治理需要对齐"的运维场景) |

Hulu 那一行 0% 是 Vantage Media 运维团队当前的 **真实痛点案例**:数据治理团队 12 个月前签了 SLA 模板,但 Hulu 供应商的真实交付节奏是中午,SLA 一直没修正。这种"配置与现实脱节"的运维问题,正是 BI 告警 + 季度供应商回顾需要捕捉的。

---

### 查询 11: 每日广告位预订量趋势

**业务背景:**
业务发展经理需要监控公司的业务增长趋势。每日广告位预订量是一个重要的先行指标——如果预订量持续增长，说明客户需求旺盛；如果预订量下降，可能预示客户流失或市场竞争加剧。这个趋势图会在每周管理层会议上展示，帮助 CEO 判断公司是否在正轨上。特别是在 Q4（旺季）预订量应该比 Q3 增长 30-40%。

**分类:** 日期聚合 + 趋势分析
**难度:** 基础
**业务角色:** Manager

**解题思路:**

这题画每日预订量的趋势线, 是业务健康度的先行指标。只用 `ad_placement` 一张表, 按 `DATE(scheduled_air_date)` 聚合到天。媒体购买金额用 `SUM(booked_cpm * booked_impressions / 1000)` 算 (CPM 是每千次曝光价, 所以要除以 1000)。这里要提醒一个口径: 算出来的是客户的总支出 (gross media buy), 不是平台净收入, 平台还要再乘 take-rate (10% 到 15%)。日期窗用固定参考日往前 60 天、往后 30 天。往后那 30 天 (11 月) 在本数据集是空的, 因为快照截止在 10-31, 这是"快照语义"的有意取舍, 生产环境里这段会有已预订未播出的未来位。

```sql
-- 每日广告位预订量趋势
-- 参考日期：'2025-10-31' (数据快照截止)；回看 60 天 + 前看 30 天
-- 字段命名：媒体购买金额 (gross media buy) 是广告主的总支出，不是平台净收入；
-- 平台 take-rate 通常 10-15%，需要单独换算。
SELECT
    DATE(a.scheduled_air_date) AS 播出日期,
    COUNT(*) AS 预订数,
    SUM(a.booked_impressions) AS 总预订曝光数,
    ROUND(SUM(a.booked_cpm * a.booked_impressions / 1000), 2) AS 媒体购买金额_美元
FROM ad_placement a
WHERE DATE(a.scheduled_air_date) >= DATE('2025-10-31', '-60 days')
  AND DATE(a.scheduled_air_date) <= DATE('2025-10-31', '+30 days')
GROUP BY DATE(a.scheduled_air_date)
ORDER BY DATE(a.scheduled_air_date) ASC;
```

**预期结果说明:**
结果集显示每天的预订量和媒体购买金额。覆盖范围实际是 2025-09-01 → 2025-10-31 (61 天):
- 9 月日均预订 ~253 条 / 媒体购买金额 ~$0.41M
- 10 月日均预订 ~358 条 / 媒体购买金额 ~$0.57M (**Q4 booking +40% 设计**)
- 月总量:9 月 7,605 条 (~$12.2M) / 10 月 **11,095 条** (~$17.7M)
- 前瞻 30 天 (11 月) 在本数据集为空,因为数据快照截止 2025-10-31。**生产环境中** 11 月这段会有已预订但未播出的未来 placement;本数据集刻意省略以保持"快照截止"语义清晰。

工作日通常高于周末。这个趋势图用于业务健康度监控。

---

### 查询 12: 抢占导致的未交付机会成本量化

**业务背景:**
CFO 需要向董事会解释"为什么公司要投资 ML 预测功能"。需要量化的指标不是真实金钱损失（抢占位 spec 上不计费），而是**未交付的机会成本** —— 这些原本可以兑现为广告主投放和平台收入的曝光被锁定后没能播出。如果平均每个被抢占位的潜在媒体购买金额为 ~$1,600，每月 ~900 个抢占就是 ~$1.5M 的未实现 GMV。通过 ML 预测减少 30% 的可预防抢占，每月可挽回 ~$45 万的可计费容量，这是 ROI 计算的基础。

**分类:** 聚合 + 计算 + 财务分析
**难度:** 中级
**业务角色:** Finance

**解题思路:**

这题给 CFO 算抢占造成的未交付机会成本, 按月汇总。只用 `ad_placement` 一张表, 过滤 `status='preempted'`, 按 `strftime('%Y-%m', scheduled_air_date)` 聚合到月。机会成本的口径要想清楚: 被抢占的位本来不向客户计费, 所以这不是真实金钱损失, 而是"如果正常播出本应产生的媒体购买金额", 用 `booked_cpm * booked_impressions / 1000` 估算。这是一个故意区别于"实际损失"的概念, 用来给 ML 投资算 ROI: 如果模型能提前识别可预防的抢占, 这部分机会成本就能挽回一部分。10 月的数字会特别大, 因为 Q4 预订量上浮和 NFL 高峰两个因素叠加。

```sql
-- 抢占导致的未交付机会成本量化
-- 注意：CTV 中被抢占的广告位通常不向广告主计费，这里计算的是
-- "如果广告位正常播出本应产生的媒体购买金额"（机会成本），不是真实损失。
SELECT
    strftime('%Y-%m', a.scheduled_air_date) AS 月份,
    COUNT(*) AS 被抢占广告位数,
    ROUND(SUM(a.booked_cpm * a.booked_impressions / 1000), 2) AS 未交付机会成本_美元,
    ROUND(AVG(a.booked_cpm * a.booked_impressions / 1000), 2) AS 平均单个机会成本,
    SUM(a.booked_impressions) AS 未交付曝光数
FROM ad_placement a
WHERE a.status = 'preempted'
GROUP BY strftime('%Y-%m', a.scheduled_air_date)
ORDER BY 月份 DESC;
```

**预期结果说明:**
结果集按月统计被抢占的未交付机会成本:

| 月份 | 被抢占数 | 未交付机会成本 | 平均单条 |
|------|---------|---------------|---------|
| 2025-05 | ~884 | ~$1.45M | ~$1.6K |
| 2025-06 | ~853 | ~$1.37M | ~$1.6K |
| 2025-07 | ~921 | ~$1.48M | ~$1.6K |
| 2025-08 | ~876 | ~$1.43M | ~$1.6K |
| 2025-09 | ~1,081 | ~$1.84M | ~$1.7K (NFL 开赛恶化) |
| 2025-10 | **~2,783** | **~$4.55M** | ~$1.6K (Q4 +40% + NFL 高峰双重打击) |

10 月单月就有 ~$4.5M 未交付机会成本——这是 **AutoML Booking Copilot 投资 ROI 的核心 KPI**。CFO 据此估算:即使 ML 预测能减少 25% 的可预防抢占 (典型 baseline → 优化模型提升幅度),10 月就能挽回 ~$1.1M 可计费容量,**全年滚动估算 $8-10M 量级**——足以支撑 AutoML 平台和数据科学团队的研发投入。

---

### 查询 13: 用户操作审计（最近 7 天 Top 活跃用户）

**业务背景:**
安全团队需要监控平台上的用户活动，识别异常行为。例如，如果某个用户在短时间内创建/取消了大量广告位预订，可能是在测试系统漏洞或进行恶意操作。这个审计报告列出最近 7 天内操作次数最多的用户，以及他们的主要操作类型。如果发现异常（如某用户 1 天内执行了 500 次 modify_booking），需要立即调查。

**分类:** 聚合 + 排序 + 日期过滤
**难度:** 基础
**业务角色:** Operations

**解题思路:**

这题是安全审计视角, 找出最近 7 天操作最频繁的用户。只用 `user_action` 一张表, 按 `user_name` 聚合。除了总操作次数, 还用条件求和 (SUM CASE) 把每个用户的预订、修改、取消、查看分析各类型的次数拆开, 这样异常模式 (比如某人取消占比异常高) 一眼可见。日期过滤用 `DATETIME('2025-10-31', '-7 days')`, 注意这里用 DATETIME 而不是 DATE, 因为 action_timestamp 是带时分秒的时间戳。最后按总操作次数降序取前 20。这是一道结构简单但业务上很常用的运营查询。

```sql
-- 最近 7 天最活跃用户审计
SELECT
    ua.user_name AS 用户名,
    COUNT(*) AS 总操作次数,
    SUM(CASE WHEN ua.action_type = 'book_placement' THEN 1 ELSE 0 END) AS 预订操作,
    SUM(CASE WHEN ua.action_type = 'modify_booking' THEN 1 ELSE 0 END) AS 修改操作,
    SUM(CASE WHEN ua.action_type = 'cancel_booking' THEN 1 ELSE 0 END) AS 取消操作,
    SUM(CASE WHEN ua.action_type = 'view_analytics' THEN 1 ELSE 0 END) AS 查看分析,
    MAX(ua.action_timestamp) AS 最后活动时间
FROM user_action ua
-- 参考日期：数据快照截止 '2025-10-31'，回看 7 天
WHERE ua.action_timestamp >= DATETIME('2025-10-31', '-7 days')
GROUP BY ua.user_name
ORDER BY 总操作次数 DESC
LIMIT 20;
```

**预期结果说明:**
结果集显示最活跃的 20 个用户。正常情况下，媒体采购员（如 sarah_chen）应该有大量预订和查看操作。如果某用户的取消操作占比异常高（>50%），需要调查原因。

---

### 查询 14: 模型版本迭代效果对比（窗口函数）

**业务背景:**
首席数据官（CDO）需要向 CEO 展示"数据科学团队的模型迭代工作是否有价值"。他需要一个清晰的对比表，显示每个模型版本相比前一个版本的准确率提升幅度。如果 v2.3.1 相比 v2.2.0 的准确率提升只有 1%，说明边际收益递减，可能需要调整研发重点；如果提升了 5%，说明投入产出比很好。这个分析使用窗口函数计算环比增长，是高级 SQL 技能的体现。

**分类:** 窗口函数 + 聚合 + 对比
**难度:** 高级
**业务角色:** Executive

**解题思路:**

这题用窗口函数算模型版本之间的环比提升。先用 CTE `model_performance` 把每个版本的清除率预测准确率算出来 (口径和 Q2 一致, 用 `model_type='clearance_classifier'` 锁定分类器)。外层用 `LAG(准确率) OVER (ORDER BY 部署时间, 模型版本)` 取上一个版本的准确率, 相减得到提升幅度。ORDER BY 里加 `模型版本` 作为第二排序键是个细节: 万一有版本同日部署, 它能保证 LAG 的结果稳定可复现。聚合粒度是"一个版本一行"。这道题的业务结论是反直觉的: 三代准确率几乎持平, 因为类别不均衡锁死了上限。本题末尾还给了一段把同样逻辑接到 roas regressor 上的查询 (改用 `roas_model_version_id` 关联), 那条线才能看到 MAPE 单调下降。

```sql
-- 模型版本迭代效果对比（带环比增长）
WITH model_performance AS (
    SELECT
        mv.version_code AS 模型版本,
        mv.deployed_at AS 部署时间,
        COUNT(*) AS 预测数,
        ROUND(AVG(CASE
            WHEN (p.predicted_clearance_prob >= 0.5 AND a.status = 'cleared') OR
                 (p.predicted_clearance_prob < 0.5 AND a.status = 'preempted')
            THEN 1.0 ELSE 0.0
        END), 4) AS 清除率预测准确率
    FROM prediction_result p
    JOIN ad_placement a ON p.placement_id = a.id
    JOIN model_version mv ON p.model_version_id = mv.id
    WHERE a.status IN ('cleared', 'preempted')
      AND mv.model_type = 'clearance_classifier'
    GROUP BY mv.version_code, mv.deployed_at
)
SELECT
    模型版本,
    部署时间,
    预测数,
    清除率预测准确率,
    LAG(清除率预测准确率) OVER (ORDER BY 部署时间, 模型版本) AS 前版本准确率,
    ROUND(清除率预测准确率 - LAG(清除率预测准确率) OVER (ORDER BY 部署时间, 模型版本), 4) AS 准确率提升,
    ROUND((清除率预测准确率 - LAG(清除率预测准确率) OVER (ORDER BY 部署时间, 模型版本)) /
          LAG(清除率预测准确率) OVER (ORDER BY 部署时间, 模型版本) * 100, 2) || '%' AS 提升百分比
FROM model_performance
-- ORDER BY tiebreaker (模型版本) 保证多版本同日部署时 LAG 结果稳定
ORDER BY 部署时间 DESC, 模型版本 DESC;
```

**预期结果说明:**
结果集显示三个版本的清除率二分类准确率几乎持平 (~86%):v2.1.5 ~86.0%、v2.2.0 ~85.8%、v2.3.1 ~85.6% (每版本 n ≈ 16,600)。**这是一个有意为之的负向叙事** —— 在 50K 大样本下,noise smoothing 让三版本预测分布趋同,但 **类别不均衡 (85% cleared)** 让整体准确率被 majority-class baseline 锁死,model_noise 收窄无法突破。

**CDO 决策建议**:别再在 clearance classifier 上继续调超参——下一代模型应该:
1. 改换损失函数 (focal loss / class-weighted cross-entropy) 强化对 preempted 类的学习
2. 对训练集做 oversampling (SMOTE) 或 undersampling
3. 引入新特征 (实时 NFL 赛程、网络当周节目结构、广告主历史抢占率)
4. 转向 ROAS 回归任务投入 (Q4 显示 MAPE 已从 12% → 5%,边际收益还在)

> **Shadow scoring 说明**:三个模型版本同时挂载,每个 placement 由随机一个版本评分。`model_version.deployed_at` 是主用版本上线时间,但所有版本都做了 backtesting 评估。这让版本对比基于同分布数据,避免"老版本只看简单数据、新版本只看难数据"的混淆。这种**多版本并存 + 同分布回溯**正是 Vantage Media AutoML 平台向客户演示"我们持续在评估每个候选模型"的关键 BI 能力。

> **ROAS Regressor 对比**:本查询只看 clearance classifier (经 `p.model_version_id` 关联)。
> 每条预测同时挂了一个配对的 **ROAS regressor**,记录在 `prediction_result.roas_model_version_id`
> (v2.1.5-roas/id4 → v2.2.0-roas/id5 → v2.3.1-roas/id6)。若要看 ROAS 回归的版本迭代效果,
> 把下面这段接到 performance_actual 上按 regressor 版本算 MAPE,会看到**单调下降 12% → 8% → 5%**:
>
> ```sql
> SELECT mv.version_code,
>        ROUND(AVG(ABS(p.predicted_roas - pa.roas) / pa.roas) * 100, 2) AS roas_mape_pct
> FROM prediction_result p
> JOIN performance_actual pa ON p.placement_id = pa.placement_id
> JOIN model_version mv ON p.roas_model_version_id = mv.id   -- 注意: 关联 roas_model_version_id
> WHERE pa.roas > 0 AND mv.model_type = 'roas_regressor'
> GROUP BY mv.version_code ORDER BY mv.version_code;
> ```
>
> 这条边际收益还存在,所以 AutoML 团队应该继续优化 ROAS 模型而暂缓 clearance 模型迭代。

---

### 查询 15: 广告活动 ROI 分析（完整链路 CTE）

**业务背景:**
财务总监需要为每个广告活动计算完整的 ROI（投资回报率）。这需要汇总活动下所有广告位的实际花费和归因收入，计算 ROI = (收入 - 成本) / 成本。如果某活动的 ROI 为负（成本 > 收入），说明这个活动失败了，需要分析原因。这个查询使用 CTE 分层计算，先汇总广告位级数据，再汇总到活动级，是复杂财务分析的典型场景。

**分类:** CTE + 多表连接 + 财务计算
**难度:** 高级
**业务角色:** Finance

**解题思路:**

这是一道完整链路的财务分析, 用 CTE 分两层算。CTE `campaign_spend` 先把每个活动的预算、预订位数、实际花费、归因收入、转化数汇总到活动粒度。链路是 campaign 连 advertiser, 再 LEFT JOIN ad_placement, 再 LEFT JOIN performance_actual。这里必须用 LEFT JOIN 而不是 INNER: 有的活动可能一个位都没投, 有的位被抢占没有 actual, INNER JOIN 会把这些活动直接丢掉, 导致分母失真。配合 `COALESCE(..., 0)` 把 NULL 的花费和收入补成 0。外层再算 ROI = (收入 - 花费) / 花费、ROAS、预算剩余率, 除法都用 `NULLIF(..., 0)` 防除零。预算剩余率是个有意义的真实区间, 因为生成器是按位的计划花费反推 budget 的, 所以多数活动落在预算内, 少数轻微超支。

```sql
-- 广告活动 ROI 完整分析
WITH campaign_spend AS (
    SELECT
        c.campaign_code,
        c.campaign_name,
        adv.advertiser_name,
        c.budget_usd AS 预算,
        COUNT(DISTINCT a.id) AS 预订广告位数,
        SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS 实际播出数,
        SUM(COALESCE(pa.spend_usd, 0)) AS 实际花费,
        SUM(COALESCE(pa.attributed_revenue_usd, 0)) AS 归因收入,
        SUM(COALESCE(pa.attributed_conversions, 0)) AS 总转化数
    FROM campaign c
    JOIN advertiser adv ON c.advertiser_id = adv.id
    LEFT JOIN ad_placement a ON c.id = a.campaign_id
    LEFT JOIN performance_actual pa ON a.id = pa.placement_id
    GROUP BY c.campaign_code, c.campaign_name, adv.advertiser_name, c.budget_usd
)
SELECT
    campaign_code AS 活动代码,
    campaign_name AS 活动名称,
    advertiser_name AS 广告主,
    预算,
    预订广告位数,
    实际播出数,
    ROUND(实际花费, 2) AS 实际花费,
    ROUND(归因收入, 2) AS 归因收入,
    总转化数,
    ROUND((归因收入 - 实际花费) / NULLIF(实际花费, 0), 2) AS ROI,
    ROUND(归因收入 / NULLIF(实际花费, 0), 2) AS ROAS,
    ROUND((预算 - 实际花费) / NULLIF(预算, 0) * 100, 1) || '%' AS 预算剩余率
FROM campaign_spend
WHERE 实际花费 > 0
ORDER BY ROI DESC
LIMIT 20;
```

**预期结果说明:**
结果集显示每个活动的 ROI。成功的活动 ROI 应在 0.2-0.8（即 20-80% 回报），ROAS 在 1.2-1.8x。失败的活动 ROI 为负，需要财务团队与客户沟通。

**预算剩余率**: 数据生成器按每个 campaign 的 placement 计划花费 (Σ booked_cpm×booked_impressions/1000)
反推 `budget_usd`(× uniform 0.9-1.4),因此本列是**有意义的真实区间**:平均预算 ~$226K、
平均实际花费 ~$170K,**预算剩余率中位 ~27%**(多数活动在预算内),范围约 -7% ~ +88%;
少数活动 (~2%) 因清除率偏高而轻微超支(剩余率 < 0),对应 ER `DQR-009 Campaign Budget Overrun`
"偶发超支告警"的设计意图。财务团队据此识别接近/突破预算的活动。

> **预算口径**: `campaign.budget_usd`(均值 ~$226K)按 placement 体量反推,且 placement 按
> `advertiser.total_budget_usd`(§1.2 客户分档,均值 ~$1.42M/年)加权分配,因此每个客户旗下
> 全部 campaign 预算之和(6 个月)约为其年度预算的一半量级(中位 ~0.53×),单 campaign 预算
> 几乎不会超过客户整年预算 —— Q6/Q15/Q19 同时展示客户预算与花费时口径自洽。

---

### 查询 16: 网络月度清除率趋势（时间序列 + 窗口函数）

**业务背景:**
数据分析师需要为产品团队提供"网络清除率趋势预测"功能的数据支持。他需要展示每个网络过去 6 个月的清除率变化趋势，以及每个月相比上月的变化率。如果某网络的清除率持续下降（如 ESPN 从 7 月的 75% 降到 10 月的 58%），说明该网络的风险在加剧，ML 模型应该相应调整权重。这个时间序列分析使用窗口函数计算环比变化。

**分类:** 窗口函数 + 日期聚合 + 趋势分析
**难度:** 中级
**业务角色:** Analyst

**解题思路:**

这题做时间序列趋势, 看每个网络每个月的清除率以及环比变化。先用 CTE `monthly_clearance` 把清除率聚合到"网络 + 月份"粒度 (月份用 `strftime('%Y-%m', scheduled_air_date)`), 同样只算已结案的位。重点是窗口函数 `LAG(清除率) OVER (PARTITION BY 网络 ORDER BY 月份)`: PARTITION BY 网络 保证环比只在同一个网络内部比, 不会拿 ESPN 的上月去对 HGTV; ORDER BY 月份 决定"上一个"是谁。拿到上月清除率后相减得到环比变化, 再用 CASE 翻译成改善 / 恶化 / 持平的箭头。聚合粒度是"一个网络一个月一行"。ESPN 在 9 到 10 月会明显走低 (NFL), HGTV 全年平稳。

```sql
-- 网络月度清除率趋势（时间序列）
WITH monthly_clearance AS (
    SELECT
        n.network_name AS 网络,
        strftime('%Y-%m', a.scheduled_air_date) AS 月份,
        COUNT(*) AS 预订数,
        SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS 清除数,
        ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS 清除率
    FROM ad_placement a
    JOIN network n ON a.network_id = n.id
    WHERE a.status IN ('cleared', 'preempted')
    GROUP BY n.network_name, strftime('%Y-%m', a.scheduled_air_date)
)
SELECT
    网络,
    月份,
    预订数,
    清除数,
    清除率,
    LAG(清除率) OVER (PARTITION BY 网络 ORDER BY 月份) AS 上月清除率,
    ROUND(清除率 - LAG(清除率) OVER (PARTITION BY 网络 ORDER BY 月份), 4) AS 环比变化,
    CASE
        WHEN 清除率 > LAG(清除率) OVER (PARTITION BY 网络 ORDER BY 月份) THEN '↑ 改善'
        WHEN 清除率 < LAG(清除率) OVER (PARTITION BY 网络 ORDER BY 月份) THEN '↓ 恶化'
        ELSE '→ 持平'
    END AS 趋势
FROM monthly_clearance
ORDER BY 网络, 月份 DESC;
```

**预期结果说明:**
结果集显示每个网络每个月的清除率趋势。ESPN 在 9-10 月（NFL 赛季开始）清除率应该明显下降，趋势标记为"↓ 恶化"。HGTV 全年保持稳定，趋势为"→ 持平"。

---

### 查询 17: P0 数据质量事件平均解决时间 (MTTR)

**业务背景:**
数据工程总监需要在季度 OKR 回顾中汇报"数据质量事件响应速度"。公司目标是 P0 事件（阻塞下游的严重问题）的平均解决时间（MTTR, Mean Time To Resolve）控制在 2 小时以内。他需要计算过去 90 天内所有 P0 事件的 MTTR，并按规则类型细分。如果某类规则（如"归因数据延迟检查"）的 MTTR 持续超标，说明需要优化响应流程或自动化修复逻辑。

**分类:** 日期计算 + 聚合 + 过滤
**难度:** 中级
**业务角色:** Manager

**解题思路:**

这题专算 P0 (最严重) 数据质量事件的平均解决时长 (MTTR)。两张表: `data_quality_log` JOIN `data_quality_rule`, 过滤 `severity='P0'` 且 `status IN ('failed','warning')` (passed 的没有解决时长可言)。MTTR 和 Q5 一样用 `(JULIANDAY(resolved_at) - JULIANDAY(run_timestamp)) * 24` 转小时, 并用 CASE 只对已解决的算, 把未解决的排除在平均之外。除了平均还取了 MAX, 让总监看到最坏情况有没有失控。聚合粒度是"一个规则一行", 这样能定位是哪类检查响应慢。日期窗用固定参考日回看 90 天, 覆盖整个数据窗。解决率应接近 100%。

```sql
-- P0 数据质量事件平均解决时间 (MTTR)
SELECT
    r.rule_name AS 规则名称,
    r.severity AS 严重程度,
    COUNT(*) AS 事件数,
    SUM(CASE WHEN l.resolved_at IS NOT NULL THEN 1 ELSE 0 END) AS 已解决数,
    ROUND(AVG(CASE
        WHEN l.resolved_at IS NOT NULL
        THEN (JULIANDAY(l.resolved_at) - JULIANDAY(l.run_timestamp)) * 24
        ELSE NULL
    END), 2) AS 平均解决时长_小时,
    ROUND(MAX(CASE
        WHEN l.resolved_at IS NOT NULL
        THEN (JULIANDAY(l.resolved_at) - JULIANDAY(l.run_timestamp)) * 24
        ELSE NULL
    END), 2) AS 最长解决时长_小时,
    ROUND(AVG(CASE WHEN l.resolved_at IS NOT NULL THEN 1.0 ELSE 0.0 END), 4) AS 解决率
FROM data_quality_log l
JOIN data_quality_rule r ON l.rule_id = r.id
WHERE r.severity = 'P0'
  AND l.status IN ('failed', 'warning')
  -- 参考日期：数据快照截止 '2025-10-31'，回看 90 天覆盖整个数据窗
  AND l.run_timestamp >= DATETIME('2025-10-31', '-90 days')
GROUP BY r.rule_name, r.severity
ORDER BY 平均解决时长_小时 DESC;
```

**预期结果说明:**
结果集显示每个 P0 规则的 MTTR。大部分 P0 事件应该在 1-2 小时内解决。如果某规则的 MTTR 超过 4 小时，需要工程总监介入优化流程。解决率应接近 100%。

---

### 查询 18: 清除率预测分布直方图数据

**业务背景:**
产品经理需要在用户界面上展示一个"清除率预测分布"图表，帮助用户理解"大部分广告位的清除概率集中在哪个区间"。例如，如果 60% 的广告位预测清除概率在 0.8-1.0 之间（高可靠性），说明平台选择的广告位质量很高；如果 30% 的广告位在 0.4-0.6 之间（高风险区），说明需要优化选品策略。这个查询生成直方图的数据源，按清除概率区间聚合。

**分类:** 聚合 + CASE 分桶
**难度:** 中级
**业务角色:** Analyst

**解题思路:**

这题给产品经理出一张预测清除概率的直方图数据。`prediction_result` JOIN `ad_placement`, 用 CASE 把 `predicted_clearance_prob` 切成 5 个概率区间 (极高风险到极低风险)。和 Q9 一样, 分桶的 CASE 在 SELECT 和 GROUP BY 里要各写一遍。亮点是用窗口函数算占比: `COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()`。这里 `SUM(COUNT(*)) OVER ()` 是聚合套窗口的写法, 先 GROUP BY 把每个桶的数量算出来 (COUNT(*)), 再用一个空窗口 OVER () 把所有桶的数量加总作分母, 一步算出每个桶占全体的百分比, 不必再开子查询。只统计已结案的位, 并按概率区间下界排序。

```sql
-- 清除率预测分布直方图数据
SELECT
    CASE
        WHEN p.predicted_clearance_prob < 0.2 THEN '0.0-0.2 (极高风险)'
        WHEN p.predicted_clearance_prob < 0.4 THEN '0.2-0.4 (高风险)'
        WHEN p.predicted_clearance_prob < 0.6 THEN '0.4-0.6 (中风险)'
        WHEN p.predicted_clearance_prob < 0.8 THEN '0.6-0.8 (低风险)'
        ELSE '0.8-1.0 (极低风险)'
    END AS 清除概率区间,
    COUNT(*) AS 广告位数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS 占比,
    ROUND(AVG(p.predicted_roas), 2) AS 平均预测ROAS,
    SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS 实际清除数,
    ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS 实际清除率
FROM prediction_result p
JOIN ad_placement a ON p.placement_id = a.id
WHERE a.status IN ('cleared', 'preempted')
GROUP BY
    CASE
        WHEN p.predicted_clearance_prob < 0.2 THEN '0.0-0.2 (极高风险)'
        WHEN p.predicted_clearance_prob < 0.4 THEN '0.2-0.4 (高风险)'
        WHEN p.predicted_clearance_prob < 0.6 THEN '0.4-0.6 (中风险)'
        WHEN p.predicted_clearance_prob < 0.8 THEN '0.6-0.8 (低风险)'
        ELSE '0.8-1.0 (极低风险)'
    END
ORDER BY MIN(p.predicted_clearance_prob) ASC;
```

**预期结果说明:**
结果集显示 5 个清除概率区间的广告位分布 (n ≈ 49,748 cleared+preempted):

| 区间 | 数量 | 占比 |
|------|-----|------|
| 0.0-0.2 (极高风险) | 0 | 0% (本数据集 model_noise 限制不出极端值) |
| 0.2-0.4 (高风险) | ~710 | ~1.4% |
| 0.4-0.6 (中风险) | ~2,200 | ~4.4% |
| 0.6-0.8 (低风险) | ~9,990 | ~20.1% |
| 0.8-1.0 (极低风险) | **~36,840** | **~74.1%** |

这个分布给产品经理一个清晰信号:**~74% 的预订都是低风险的**,说明 Vantage Media 推荐引擎已经在帮买手过滤掉大部分高风险位;真正需要 ML 介入决策的是约 12,900 条 (~26%) 中低风险位。这也是 Booking Copilot 在 UI 上**只对清除率 < 0.65 的位高亮预警**的依据 (见 Q3)。

---

### 查询 19: 广告主名称模糊搜索

**业务背景:**
客户成功团队在 CRM 系统中需要快速查找广告主信息。由于广告主名称可能有多种拼写或缩写（如 "Luminary Health" vs "Luminary" vs "LumHealth"），团队需要一个模糊搜索功能。用户输入部分关键词（如 "Lum"），系统返回所有匹配的广告主及其基本信息。这是一个简单的 LIKE 查询，但在实际业务中非常常用。

**分类:** 文本匹配 + 连接
**难度:** 基础
**业务角色:** Operations

**解题思路:**

这题是 CRM 里常见的模糊搜索功能。主表 advertiser 连 category 拿行业, 再 LEFT JOIN campaign 和 ad_placement 统计这个客户有多少活动、多少位。用 LEFT JOIN 是为了即使某客户还没投放过, 也能在搜索结果里出现 (活动数和位数显示为 0), 而不是被 INNER JOIN 过滤掉。模糊匹配用 `WHERE advertiser_name LIKE '%Health%'`, 百分号是通配符, 实际使用时换成用户输入的关键词。因为一个客户连多个活动多个位会产生行的扇出, 统计活动数和位数必须用 `COUNT(DISTINCT c.id)` 和 `COUNT(DISTINCT a.id)` 去重, 否则会被 JOIN 放大。

```sql
-- 广告主名称模糊搜索
SELECT
    adv.advertiser_code AS 广告主代码,
    adv.advertiser_name AS 广告主名称,
    ac.category_name AS 行业类别,
    adv.total_budget_usd AS 总预算,
    DATE(adv.onboarded_at) AS 入驻日期,
    COUNT(DISTINCT c.id) AS 活动数,
    COUNT(DISTINCT a.id) AS 广告位数
FROM advertiser adv
JOIN advertiser_category ac ON adv.category_id = ac.id
LEFT JOIN campaign c ON adv.id = c.advertiser_id
LEFT JOIN ad_placement a ON adv.id = a.advertiser_id
WHERE adv.advertiser_name LIKE '%Health%'  -- 替换为实际搜索关键词
GROUP BY adv.advertiser_code, adv.advertiser_name, ac.category_name,
         adv.total_budget_usd, adv.onboarded_at
ORDER BY adv.advertiser_name ASC;
```

**预期结果说明:**
结果集返回所有名称中包含"Health"的广告主，以及他们的活动数和广告位数。客户成功经理可以快速定位目标客户。

---

### 查询 20: 跨网络类型 ROAS 对比（子查询）

**业务背景:**
CEO 在战略规划会议上需要回答"我们应该把重点放在线性电视还是流媒体平台上？"这需要对比不同网络类型（线性有线、线性广播、流媒体）的 ROAS 表现。如果流媒体的平均 ROAS 比线性电视高 30%，说明应该加大对流媒体平台的投入。这个查询使用子查询计算每种网络类型的 ROAS，并进行横向对比，是高管决策的重要依据。

**分类:** 子查询 + 聚合 + 对比
**难度:** 高级
**业务角色:** Executive

**解题思路:**

这题给 CEO 回答"该押线性电视还是流媒体"。用两个 CTE: `network_type_performance` 按网络类型 (linear_cable / linear_broadcast / streaming_avod) 算花费、收入、整体 ROAS; `platform_total` 算全平台的整体 ROAS 作基准。链路是 ad_placement 连 network 拿类型, 连 performance_actual 拿花费收入。这里再次强调两种 ROAS 口径: 平均 ROAS (AVG) 对小订单敏感, 整体 ROAS (SUM 收入 / SUM 花费) 是花费加权的真实回报, 战略决策用后者。最后一列"相对全平台差异"是用每个类型的整体 ROAS 对比 spend-weighted 的全平台整体 ROAS (用子查询取出那个基准值), 而不是对三个类型整体 ROAS 取算术平均, 这个基准的选择会直接影响结论, 是本题最容易出错的地方。

```sql
-- 跨网络类型 ROAS 对比
-- 设计要点：
-- 1) "平均 ROAS" 是 row-level mean(roas)，对小订单容易偏置
-- 2) "整体 ROAS" = SUM(revenue) / SUM(spend) 是 spend-weighted，是 CFO 关心的真实回报
-- 3) "相对全平台差异" 以 *spend-weighted 全平台整体 ROAS* 为基准
--    （不是 3 个网络类型整体 ROAS 的算术平均）
WITH network_type_performance AS (
    SELECT
        n.network_type AS 网络类型,
        COUNT(DISTINCT a.id) AS 投放广告位数,
        SUM(pa.spend_usd) AS 总花费,
        SUM(pa.attributed_revenue_usd) AS 总收入,
        SUM(pa.attributed_conversions) AS 总转化数,
        ROUND(AVG(pa.roas), 2) AS 平均ROAS,
        ROUND(SUM(pa.attributed_revenue_usd) / NULLIF(SUM(pa.spend_usd), 0), 2) AS 整体ROAS
    FROM ad_placement a
    JOIN network n ON a.network_id = n.id
    JOIN performance_actual pa ON a.id = pa.placement_id
    GROUP BY n.network_type
),
platform_total AS (
    SELECT
        SUM(pa.attributed_revenue_usd) / NULLIF(SUM(pa.spend_usd), 0) AS 全平台整体ROAS
    FROM performance_actual pa
)
SELECT
    网络类型,
    投放广告位数,
    ROUND(总花费, 2) AS 总花费_美元,
    ROUND(总收入, 2) AS 总收入_美元,
    总转化数,
    平均ROAS,
    整体ROAS,
    ROUND((整体ROAS - (SELECT 全平台整体ROAS FROM platform_total)) /
          (SELECT 全平台整体ROAS FROM platform_total) * 100, 2) || '%' AS 相对全平台差异
FROM network_type_performance
ORDER BY 整体ROAS DESC;
```

**预期结果说明:**
结果集对比三种网络类型。streaming_avod 的整体 ROAS 应该在 1.5-1.7x，比 linear_cable 的 1.2-1.4x 高出 20-30%。CEO 可以据此决定战略重点。

---

## 4. 查询分类汇总

注：一个查询可属于多个分类（例如 Q16 同时用窗口函数和 CTE），下表"数量"按主分类计。

| 分类 | 数量 | 查询编号 |
|------|------|----------|
| 聚合查询 | 5 | 1, 5, 6, 11, 13 |
| 连接操作 | 5 | 3, 4, 8, 10, 19 |
| 窗口函数 | 3 | 14, 16, 18 |
| 日期时间分析 | 3 | 7, 9, 17 |
| 子查询/CTE | 6 | 2, 7, 14, 15, 16, 20 |
| 文本匹配 | 1 | 19 |
| 计算字段（派生指标） | 6 | 4, 9, 11, 12, 15, 20 |

## 5. 业务角色覆盖

每个查询归一个主角色；Q18 主角色为 Analyst（产品/数据团队使用），Manager 视图见 Q3。

| 角色 | 数量 | 查询编号 |
|------|------|----------|
| Executive / C-Level | 3 | 6, 14, 20 |
| Manager | 4 | 3, 7, 11, 17 |
| Analyst | 6 | 2, 4, 8, 9, 16, 18 |
| Operations | 5 | 1, 5, 10, 13, 19 |
| Finance | 2 | 12, 15 |

## 6. 难度分布

| 难度 | 数量 | 查询编号 |
|------|------|----------|
| 基础 | 7 | 1, 3, 5, 6, 11, 13, 19 |
| 中级 | 10 | 2, 4, 7, 8, 9, 10, 12, 16, 17, 18 |
| 高级 | 3 | 14, 15, 20 |

---

## 7. 查询与业务问题映射

每个查询都追溯到业务背景文档第 5 节列出的核心业务问题。四个业务问题外加 AutoML 模型监控这条产品线, 共同覆盖全部 20 道查询。

| 业务问题 | 对应查询 |
|----------|----------|
| 媒体采购盲区 (清除率 / 抢占 / 机会成本) | Q1, Q3, Q7, Q9, Q11, Q12, Q16 |
| 客户差异化 (ROAS 按客户 / 品类 / 网络) | Q4, Q6, Q15, Q19, Q20 |
| 归因难题 (归因方法系统性偏差) | Q8 |
| 数据质量黑洞 (DQ 告警 / SLA / MTTR / 审计) | Q5, Q10, Q13, Q17 |
| AutoML 模型监控 (产品线) | Q2, Q14, Q18 |

---

## 8. 备注

- 所有查询均使用 SQLite 3.x 语法编写
- 查询可以稍作修改后用于其他数据库（PostgreSQL、MySQL、Snowflake）
- TSV 文件名中的数字表示表加载顺序（拓扑排序）
- 建议在分析前先运行 ER 文档中的"数据完整性验证"查询
- 日期函数使用 SQLite 的 `DATE()`, `DATETIME()`, `strftime()` 语法

---

**文档版本:** 2.1 (0.2.1 spec 重组: 加"如何使用本文档"导读 + 每题补"解题思路"段 + 业务问题映射表, SQL 逻辑未改动)
**生成日期:** 2026-06-22
**适用数据集:** advertising_ctv_campaign_analytics_high (Vantage Media · Booking Copilot)
**总查询数:** 20
**核心 ML 用例:** Clearance Prediction (二分类) + ROAS Prediction (回归)
**Shadow Scoring:** 3 代模型版本同时在线评估 (clearance classifier + 配对 ROAS regressor),每代 n ≈ 16,600
