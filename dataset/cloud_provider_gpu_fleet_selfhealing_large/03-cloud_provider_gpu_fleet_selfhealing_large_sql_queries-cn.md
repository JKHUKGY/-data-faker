# Kestrel Compute 自愈调度数据集 SQL 查询集

本文档覆盖 `cloud_provider_gpu_fleet_selfhealing_large` 数据集. 业务背景与模型族说明在 `01-cloud_provider_gpu_fleet_selfhealing_large_business_context-cn.md`, 表结构在 `02-cloud_provider_gpu_fleet_selfhealing_large_er_document-cn.md`.

数据集锚定在 `REFERENCE_DATE = 2026-05-31`, 也是这份快照的截止时刻. 所有查询里的日期都是字面量, 不用 `DATE('now')`.

---

## 1. 如何使用本文档

这二十条查询和典型的分析型 SQL 文档不一样. 它们不是用来回答 "上个季度业绩怎么样", 而是用来回答 "我手上这份数据能不能训出一个上线不会翻车的模型".

顺序是有意安排的, 大致对应一个 Data Scientist 接手一个已上线项目的真实动作序列:

**先做数据体检** (Q1 到 Q4). 样本量够不够, 正例有多稀疏, 哪些特征根本不能用, 标签什么时候才可知. 这四步做完之前不要碰模型.

**再找方法论陷阱** (Q5 到 Q10). 泄漏, 时间泄漏, 选择性标签, 删失, 幸存者偏差. 这些问题不会让代码报错, 只会让你的离线指标好得不真实, 然后上线翻车.

**然后评估现有模型** (Q11 到 Q15). 在真实预算约束下召回率是多少, 概率校准得怎么样, 有没有漂移, 线上线下特征是否一致.

**最后核算业务价值** (Q16 到 Q20). 模型到底赚没赚钱, 误报代价多大, 另外几个模型的训练集长什么样.

每条查询有五个部分: 业务背景说明谁在问和为什么现在问, 标签给出 SQL 类别与难度, 解题思路在你看到 SQL 之前把陷阱先讲清楚, SQL 是可直接运行的代码, 预期结果给出真实数字并说明下一步该做什么.

文档里所有数字都是在生成好的数据库上真跑出来的, 建模相关的指标 (AUC, PR-AUC) 用 scikit-learn 的 `HistGradientBoostingClassifier` 训练测得, 不是编的.

---

## 2. 查询索引

| 编号 | 标题 | 阶段 | SQL 类别 | 难度 |
| :-- | :--- | :--- | :--- | :--- |
| Q1 | 切分体检, 正例有多稀疏 | 数据体检 | 聚合 | 基础 |
| Q2 | 特征可用性审计 | 数据体检 | CASE 分组 | 基础 |
| Q3 | point-in-time 训练集组装 | 数据体检 | 多表连接 + CTE | 中级 |
| Q4 | 标签什么时候才可知 | 数据体检 | 日期计算 | 基础 |
| Q5 | 泄漏特征的判别力有多离谱 | 陷阱排查 | 条件聚合 + UNION | 中级 |
| Q6 | 正例的块状结构 | 陷阱排查 | 窗口函数 | 中级 |
| Q7 | 上线前后正例率断崖 | 陷阱排查 | 分段聚合 | 基础 |
| Q8 | 四个处置臂的真实故障率 | 陷阱排查 | 多表连接 + CASE | 中级 |
| Q9 | 右删失的规模与方向 | 陷阱排查 | 聚合 | 基础 |
| Q10 | 消失的坏卡 | 陷阱排查 | 标量子查询 | 中级 |
| Q11 | 预算约束下的召回率 | 模型评估 | 窗口函数 NTILE | 高级 |
| Q12 | 可靠性曲线, 概率高估了多少倍 | 模型评估 | 聚合 | 基础 |
| Q13 | 按硬件批次切片的漂移 | 模型评估 | 切片查询 | 中级 |
| Q14 | 特征分布本身漂移了吗 | 模型评估 | CTE + 分组对比 | 中级 |
| Q15 | 训练服务偏斜的证据 | 模型评估 | 日期差 + 子查询 | 中级 |
| Q16 | 模型到底赚了多少钱 | 价值核算 | 多表连接 + 聚合 | 中级 |
| Q17 | 为什么不能用故障率评估排空决策 | 价值核算 | 条件聚合 | 高级 |
| Q18 | M2 作业时长训练集的删失结构 | 价值核算 | 条件聚合 | 中级 |
| Q19 | M3 恢复时长的驱动因素 | 价值核算 | 连接 + 聚合 | 中级 |
| Q20 | M5 慢节点, 没有标签怎么办 | 价值核算 | CTE + 相关子查询 | 高级 |

---

## 3. Q1 切分体检, 正例有多稀疏

### 业务背景

你入职第一天, Ana 给了你数据库访问权限和一句话: "先看看数据, 别急着训模型". 这条查询是你该跑的第一条 SQL.

在极端不平衡的问题上, 样本量这个词是有歧义的. 说 "训练集有两万四千行" 毫无意义, 真正决定模型能学到什么的是正例数. 一百个正例和一千个正例是完全不同的两个问题, 前者你基本只能做特征工程加简单模型, 后者才谈得上调参.

### 标签

聚合 / 基础 / 数据体检

### 解题思路

`dataset_split` 表已经把切分边界和统计量物化好了, 直接查即可. 关键是自己再算一列 "多少行才出一个正例", 因为百分比在 0.1% 到 1% 这个区间, 人的直觉很差, 换成 "每 227 行一个正例" 立刻就有体感了.

不要跳过 production 那一行. 它的正例率和前面三行差一个数量级, 这不是数据出错, 后面 Q7 会解释.

### SQL

```sql
SELECT
    s.split_name,
    s.window_start,
    s.window_end,
    s.row_count,
    s.positive_count,
    ROUND(s.positive_count * 100.0 / s.row_count, 3) AS positive_pct,
    -- 百分比在这个区间没有体感, 换成 "多少行出一个正例"
    ROUND(s.row_count * 1.0 / NULLIF(s.positive_count, 0), 0) AS one_positive_per_n_rows
FROM dataset_split s
ORDER BY s.window_start;
```

### 预期结果与业务结论

| split_name | row_count | positive_count | positive_pct | one_positive_per_n_rows |
| :--- | :-- | :-- | :-- | :-- |
| train | 24,028 | 106 | 0.441% | 227 |
| validation | 8,000 | 77 | 0.963% | 104 |
| test | 8,000 | 50 | 0.625% | 160 |
| production | 48,800 | 60 | 0.123% | 813 |

训练集只有 106 个正例. 这个数字决定了你后面所有的方法选择: 深层网络不用考虑, 复杂的特征交叉容易过拟合, 交叉验证的折数不能太多否则每折正例个位数.

production 段 48,800 行只有 60 个正例, 每 813 行才一个. 如果你不知道模型 4 月 1 日上线过, 你会以为硬件突然变可靠了.

下一步: 在训练之前先搞清楚哪些特征根本不能用, 见 Q2.

---

## 4. Q2 特征可用性审计

### 业务背景

上一位 DS 留下了 26 个特征. 你需要在用它们之前判断哪些能用. 这不是可选步骤: `feature_snapshot` 是一张宽表, 谁都可以 `SELECT *` 然后丢进模型, 而其中两列会让你的 AUC 虚高十个百分点, 上线之后原形毕露.

判断依据是 `feature_definition.availability_lag_minutes`, 它记录了线上打分时这个特征相对当前时刻滞后多久可得.

### 标签

CASE 分组 / 基础 / 数据体检

### 解题思路

只需要 `feature_definition` 一张表. 核心是理解那一列的三种取值各意味着什么.

滞后为 0, 实时可得, 训练和线上一致, 放心用.

滞后为正, 说明这个特征走的是数仓批处理链路, 线上只能拿到一小时前的值. 训练时如果按 `as_of_ts` 取理想值, 模型会依赖线上根本拿不到的信息, 这叫训练服务偏斜.

滞后为负, 说明这个特征的计算窗口取到了 `as_of` 之后的数据. 这不是滞后, 这是穿越. 直接排除.

用 `GROUP_CONCAT` 把特征名拼出来, 这样一条查询就能当特征清单用.

### SQL

```sql
SELECT
    CASE WHEN availability_lag_minutes < 0 THEN '1. 禁用, 取用了未来信息'
    WHEN availability_lag_minutes > 0 THEN '2. 可用但线上有滞后'
    ELSE                                   '3. 可用, 实时' END AS usability,
    availability_lag_minutes,
    COUNT(*) AS feature_count,
    GROUP_CONCAT(feature_name, ', ') AS features
FROM feature_definition
GROUP BY usability, availability_lag_minutes
ORDER BY usability;
```

### 预期结果与业务结论

| usability | lag | 数量 | 特征 |
| :--- | :-- | :-- | :--- |
| 1. 禁用, 取用了未来信息 | -1080 | 2 | `ops_attention_flag`, `pending_drain_flag` |
| 2. 可用但线上有滞后 | 60 | 3 | `hbm_temp_excess_over_lot`, `firmware_age_days`, `open_work_order_count` |
| 3. 可用, 实时 | 0 | 21 | 其余 21 个遥测与资产特征 |

26 个特征里有 2 个必须排除, 3 个需要按滞后后的时点取值. 真正可以直接用的是 21 个.

那两个负滞后的特征名字起得很无辜, 一个叫 "运维关注标记" 一个叫 "待排空标记", 光看名字完全看不出问题. `availability_lag_minutes = -1080` 是唯一的线索, 意思是它们的计算窗口伸进了未来 18 小时.

下一步: 用筛过的特征组装训练集, 见 Q3.

---

## 5. Q3 point-in-time 训练集组装

### 业务背景

现在你要把训练集拉出来. 这一步看起来只是个 join, 但它是整个项目里最容易出错的地方, 而且错了不会报错.

要点有三个: 特征和标签必须按 `(节点, as_of)` 对齐; 只能用可用的特征; 而且训练某个时点的模型时, 只能使用那个时点已经可知的标签.

### 标签

多表连接 + CTE / 中级 / 数据体检

### 解题思路

`feature_snapshot` 与 `label_record` 都以 `(gpu_node_id, as_of_ts)` 为键, 一一对应, 两表都是 88,828 行. join 条件必须两个字段都带上, 只按节点 join 会产生笛卡尔积, 行数直接炸到几千万.

第一个 CTE 从 `feature_definition` 里筛出可用特征名, 第二个 CTE 取训练窗边界. 边界不要写死在 SQL 里, 从 `dataset_split` 读, 这样窗口滚动时查询不用改.

最后一列 `labels_not_yet_known` 是这条查询真正的价值所在: 统计训练窗内有多少标签在窗口结束时还不可知. 这些样本你在训练时点是拿不到的, 如果直接用了就是穿越.

### SQL

```sql
WITH usable AS (
    SELECT feature_name FROM feature_definition WHERE availability_lag_minutes >= 0
),
train_window AS (
    SELECT window_start, window_end FROM dataset_split WHERE split_name = 'train'
)
SELECT
    (SELECT COUNT(*) FROM usable)                    AS usable_feature_count,
    COUNT(*)                                         AS training_rows,
    SUM(l.label_value)                               AS positives,
    ROUND(SUM(l.label_value) * 100.0 / COUNT(*), 3)  AS positive_pct,
    -- 训练窗结束时还不可知的标签. 用了就是穿越
    SUM(CASE WHEN l.label_known_at > w.window_end THEN 1 ELSE 0 END) AS labels_not_yet_known
FROM feature_snapshot f
-- 必须两个字段都 join. 只按节点 join 会产生笛卡尔积
JOIN label_record l ON l.gpu_node_id = f.gpu_node_id AND l.as_of_ts = f.as_of_ts
CROSS JOIN train_window w
WHERE f.as_of_ts >= w.window_start AND f.as_of_ts < w.window_end;
```

### 预期结果与业务结论

| usable_feature_count | training_rows | positives | positive_pct | labels_not_yet_known |
| :-- | :-- | :-- | :-- | :-- |
| 24 | 24,028 | 106 | 0.441% | 800 |

24,028 行里有 800 行的标签在训练窗结束时还不可知. 这 800 行占 3.3%, 单看比例不大, 但它们全部集中在窗口末尾, 而窗口末尾恰好是离预测时点最近, 信息量最大的那批样本.

严格的做法是训练时把它们排除, 或者把训练窗的右边界往前推 26 小时. 两种做法在这个数据集上差别不大, 但在标签迟到几天甚至几周的场景 (信贷违约, 医疗结局) 里, 忽略这件事会让离线评估完全失真.

下一步: 看看这个 26 小时是怎么来的, 见 Q4.

---

## 6. Q4 标签什么时候才可知

### 业务背景

Q3 提到有 800 个标签在训练时点还不可知. 这条查询确认这个滞后有多长, 以及它是不是稳定的.

这件事在做在线学习或者频繁重训的系统里尤其重要: 如果你每天重训一次, 而标签要 26 小时后才可知, 那么昨天的数据里有一整天是不能用的.

### 标签

日期计算 / 基础 / 数据体检

### 解题思路

`JULIANDAY` 相减得到天数, 乘 24 换成小时. SQLite 没有 `DATEDIFF`, 这是标准做法.

按滞后小时数分组, 如果分组结果只有一行, 说明滞后是固定的; 如果有多行, 说明不同样本的标签可知时间不同, 那就要按样本分别处理.

### SQL

```sql
SELECT
    -- SQLite 没有 DATEDIFF, 用 JULIANDAY 相减乘 24 得到小时
    ROUND((JULIANDAY(label_known_at) - JULIANDAY(as_of_ts)) * 24, 1) AS lag_hours,
    COUNT(*)          AS n,
    SUM(label_value)  AS positives
FROM label_record
GROUP BY lag_hours;
```

### 预期结果与业务结论

| lag_hours | n | positives |
| :-- | :-- | :-- |
| 26.0 | 88,828 | 293 |

只有一行, 说明滞后是固定的 26 小时: 24 小时观测窗加 2 小时运维定性时间.

固定滞后是好消息, 处理起来简单: 训练时把右边界往前推 26 小时就行. 如果这里出现多个值, 就说明不同故障的定性时间不同, 需要按样本处理, 那要麻烦得多.

下一步: 开始查陷阱. 先看那两个被标为禁用的特征到底有多离谱, 见 Q5.

---

## 7. Q5 泄漏特征的判别力有多离谱

### 业务背景

你在 `training_run` 表里看到上一位 DS 有一次实验 test AUC 到了 0.9438, 而基线只有 0.8513. 那次实验的 `includes_leaky_features` 是 1. 你需要证明那 0.09 的提升来自泄漏而不是真本事.

最直接的证明方式是看单变量判别力: 一个合法特征不可能单靠自己就把正负例分开, 但泄漏特征可以, 因为它本质上就是标签的一个变形.

### 标签

条件聚合 + UNION / 中级 / 陷阱排查

### 解题思路

拿泄漏特征 `ops_attention_flag` 和一个正经的强特征 `hbm_temp_excess_over_lot` 做对照, 各自算分组正例率.

`ops_attention_flag` 是 0 或 1, 直接分组即可. `hbm_temp_excess_over_lot` 是连续值, 需要先切一刀. 这里取 P99 作为阈值, 也就是只看最极端的 1% 样本, 给合法特征最有利的条件.

SQLite 没有 `PERCENTILE_CONT`, 用 `ORDER BY ... LIMIT 1 OFFSET n` 的方式取分位数. `OFFSET` 里的表达式要用 `CAST(... AS INT)` 转整数.

两段用 `UNION ALL` 拼起来, 放在一张表里对比才有冲击力.

### SQL

```sql
SELECT 'ops_attention_flag' AS feature, f.ops_attention_flag AS value,
    COUNT(*) AS n, SUM(l.label_value) AS positives,
    ROUND(SUM(l.label_value) * 100.0 / COUNT(*), 2) AS positive_pct
FROM feature_snapshot f
JOIN label_record l ON l.gpu_node_id = f.gpu_node_id AND l.as_of_ts = f.as_of_ts
GROUP BY f.ops_attention_flag

UNION ALL

SELECT 'hbm_temp_excess_over_lot (>P99)',
    -- SQLite 没有 PERCENTILE_CONT, 用 LIMIT/OFFSET 取分位数
    CASE WHEN f.hbm_temp_excess_over_lot >
    (SELECT hbm_temp_excess_over_lot FROM feature_snapshot
    ORDER BY hbm_temp_excess_over_lot
    LIMIT 1 OFFSET (SELECT CAST(COUNT(*) * 0.99 AS INT) FROM feature_snapshot))
    THEN 1 ELSE 0 END,
    COUNT(*), SUM(l.label_value), ROUND(SUM(l.label_value) * 100.0 / COUNT(*), 2)
FROM feature_snapshot f
JOIN label_record l ON l.gpu_node_id = f.gpu_node_id AND l.as_of_ts = f.as_of_ts
GROUP BY 2
ORDER BY feature, value;
```

### 预期结果与业务结论

| feature | value | n | positives | positive_pct |
| :--- | :-- | :-- | :-- | :-- |
| hbm_temp_excess_over_lot (>P99) | 0 | 87,940 | 290 | 0.33% |
| hbm_temp_excess_over_lot (>P99) | 1 | 888 | 3 | 0.34% |
| ops_attention_flag | 0 | 88,454 | 73 | 0.08% |
| ops_attention_flag | 1 | 374 | 220 | 58.82% |

结论毫无悬念. `ops_attention_flag = 1` 的 374 个样本里有 220 个是正例, 正例率 58.82%, 是基线 0.33% 的 178 倍. 一个合法特征做不到这种事.

更有意思的是对照组. `hbm_temp_excess_over_lot` 取最极端的 1%, 正例率 0.34%, 和基线的 0.33% 几乎没差别. 这说明真实信号不在任何单个特征里, 它藏在多个特征的时间趋势的组合中. 这也解释了为什么这个问题需要模型而不是阈值告警: 任何单变量阈值都是没用的.

下一步: 把那两列从特征集里删掉, 然后检查第二种更隐蔽的泄漏, 见 Q6.

---

## 8. Q6 正例的块状结构

### 业务背景

你打算做交叉验证. 在动手之前需要确认一件事: 这些正例是彼此独立的吗.

如果不是, 随机划分就会把同一次故障产生的多个样本拆到训练集和验证集两边, 模型只要认出 "这是那台机器" 就能答对, 验证指标会虚高.

### 标签

窗口函数 / 中级 / 陷阱排查

### 解题思路

一次故障会让它之前 24 小时内的所有 as_of 点都变成正例. as_of 每 6 小时一个, 所以一次故障产生 4 个正例样本, 而且这 4 个样本来自同一台机器的连续时间段, 特征高度相似.

用 `ROW_NUMBER()` 按节点分区给正例编号, 再按节点聚合数正例个数, 就能看出块状结构: 如果绝大多数节点的正例数是 4 的倍数, 说明每个块就是一次故障.

这条查询本身不复杂, 价值在于它给出的那个数字直接决定了你的交叉验证策略.

### SQL

```sql
WITH pos AS (
    SELECT l.gpu_node_id, l.as_of_ts,
        ROW_NUMBER() OVER (PARTITION BY l.gpu_node_id ORDER BY l.as_of_ts) AS seq
    FROM label_record l
    WHERE l.label_value = 1
),
runs AS (
    SELECT gpu_node_id, COUNT(*) AS positives_for_node FROM pos GROUP BY gpu_node_id
)
SELECT
    positives_for_node AS positives_per_node,
    COUNT(*)           AS nodes,
    positives_for_node * COUNT(*) AS positive_rows,
    ROUND(positives_for_node * COUNT(*) * 100.0 /
        (SELECT SUM(label_value) FROM label_record), 1) AS pct_of_all_positives
FROM runs
GROUP BY positives_for_node
ORDER BY positives_for_node;
```

### 预期结果与业务结论

| positives_per_node | nodes | positive_rows | pct_of_all_positives |
| :-- | :-- | :-- | :-- |
| 2 | 1 | 2 | 0.7% |
| 3 | 1 | 3 | 1.0% |
| 4 | 54 | 216 | 73.7% |
| 8 | 9 | 72 | 24.6% |

结构一清二楚. 54 个节点各有 4 个正例 (一次故障), 9 个节点有 8 个 (两次故障). 293 个正例其实只来自 65 台机器的 74 次故障事件.

这意味着你的有效样本量不是 293 而是 74. 交叉验证必须按节点分组 (GroupKFold) 或者按时间划分, 绝不能随机打散. 实测数据: 随机划分 AUC 0.9209, 按时间划分 0.8513, 虚高 6.96 个百分点.

下一步: 前面查的都是训练数据本身的问题. 接下来看上线之后数据发生了什么变化, 见 Q7.

---

## 9. Q7 上线前后正例率断崖

### 业务背景

Ana 交给你的第二项任务是诊断模型有没有退化. 你打算用上线后的数据重训一版看看, 但在那之前, 先看一眼上线前后的标签分布.

这一眼可能会让你放弃原来的计划.

### 标签

分段聚合 / 基础 / 陷阱排查

### 解题思路

按 2026-04-01 这条线把 `label_record` 切成两段, 各自算正例率和删失率.

`is_label_censored` 这一列是关键. 它标记的是 "该节点在观测窗内被模型主动排空了, 因此真实结局无从观测" 的样本. 上线前这个数应该接近 0, 上线后应该显著大于 0.

### SQL

```sql
SELECT
    CASE WHEN l.as_of_ts < '2026-04-01' THEN '1. 上线前 (无干预)'
    ELSE '2. 上线后 (模型在改变世界)' END AS period,
    COUNT(*)                                          AS rows,
    SUM(l.label_value)                                AS positives,
    ROUND(SUM(l.label_value) * 100.0 / COUNT(*), 3)   AS positive_pct,
    SUM(l.is_label_censored)                          AS censored,
    ROUND(SUM(l.is_label_censored) * 100.0 / COUNT(*), 3) AS censored_pct
FROM label_record l
GROUP BY period;
```

### 预期结果与业务结论

| period | rows | positives | positive_pct | censored | censored_pct |
| :--- | :-- | :-- | :-- | :-- | :-- |
| 1. 上线前 (无干预) | 40,028 | 233 | 0.582% | 3 | 0.007% |
| 2. 上线后 (模型在改变世界) | 48,800 | 60 | 0.123% | 201 | 0.412% |

正例率从 0.582% 掉到 0.123%, 少了 79%. 同时删失样本从 3 个涨到 201 个.

这不是硬件变可靠了, 是模型把故障拦掉了. 被拦掉的故障没有发生, 于是它们在数据里表现为 "高风险特征 + 标签 0", 也就是模型自己制造的假阴性.

如果你拿这份数据直接重训, 模型会学到 "这些特征不再预示故障", 然后越训越差. 实测: 含删失样本重训, 5 月下旬 AUC 0.5688; 剔除删失样本重训, 回到 0.6562.

这就是选择性标签, 是这份数据集最重要的陷阱, 也是所有上线后的预测系统都会遇到的问题.

下一步: 既然被处置过的样本不能用, 那哪些样本能用? 见 Q8.

---

## 10. Q8 四个处置臂的真实故障率

### 业务背景

Q7 说明上线后的标签被污染了. 但也不是全部污染, 总有一些被判高风险却没有被处置的节点, 它们的结局是真实可观测的.

问题是, 这些 "没被处置" 的样本能不能当无偏样本用. 答案取决于它们为什么没被处置.

### 标签

多表连接 + CASE / 中级 / 陷阱排查

### 解题思路

`decision_log` 里有三个字段共同决定一个决策落在哪个臂: `executed_action` (实际做了什么), `is_holdout` (是不是随机留出), `override_reason` (人工驳回的理由).

四种组合的业务含义完全不同, 用 `CASE` 分开, 再 join `action_outcome` 看各臂的真实故障率.

`GROUP_CONCAT(DISTINCT ...)` 把 override 的理由列出来, 这一列是判断该臂能不能当无偏样本的关键证据.

### SQL

```sql
SELECT
    CASE WHEN d.is_holdout = 1                 THEN '1. 留出组 (随机, 无偏)'
    WHEN d.override_reason IS NOT NULL    THEN '2. 人工 override (非随机, 有偏)'
    WHEN d.executed_action = 'DRAIN'      THEN '3. 已处置 (标签被删失)'
    ELSE                                       '4. 仅监控' END AS arm,
    COUNT(*)                                        AS decisions,
    SUM(o.node_failed_within_horizon)               AS actually_failed,
    ROUND(AVG(o.node_failed_within_horizon) * 100, 1) AS failure_pct,
    GROUP_CONCAT(DISTINCT d.override_reason)        AS reasons
FROM decision_log d
JOIN action_outcome o ON o.decision_log_id = d.id
GROUP BY arm
ORDER BY arm;
```

### 预期结果与业务结论

| arm | decisions | actually_failed | failure_pct | reasons |
| :--- | :-- | :-- | :-- | :--- |
| 1. 留出组 (随机, 无偏) | 20 | 16 | 80.0% | EXPLORATION_HOLDOUT |
| 2. 人工 override (非随机, 有偏) | 17 | 17 | 100.0% | NO_SPARE_CAPACITY, OPS_DISAGREED, CRITICAL_CUSTOMER_JOB |
| 3. 已处置 (标签被删失) | 51 | 0 | 0.0% | |
| 4. 仅监控 | 376 | 1 | 0.3% | |

三件事.

第一, 留出组 20 个样本里有 16 个真的故障了, 故障率 80%. 这是模型在高分段的真实精度, 也是唯一可信的估计. 20 个样本很少, 但它是干净的.

第二, override 组故障率 100%, 比留出组还高. 这不能说明模型更准, 恰恰说明这批样本是被挑过的: 运维驳回的理由是 "这节点上跑着关键客户的作业" 或者 "没有备用容量", 而关键作业往往跑在负载最重的机器上, 负载重又和故障相关. 拿这 17 个样本当无偏样本用, 会高估模型精度.

第三, 已处置组故障率 0%. 这不是模型判错了, 是因为节点被修好了所以没坏. 这一列在这批样本上没有任何信息量.

结论: 上线后唯一能用来评估和重训的干净样本是留出组的 20 个, 以及全部未被判为高风险的样本. 留出比例 18% 看起来是在浪费钱, 但没有它, 模型上线之后就再也无法被评估了.

下一步: 换个模型看看, M2 那边有没有类似的问题. 见 Q9.

---

## 11. Q9 右删失的规模与方向

### 业务背景

M2 是预测作业剩余时长的模型, 上一位 DS 的做法是 `WHERE actual_hours IS NOT NULL` 然后训一个回归. 你需要判断这个做法有没有问题.

问题在于, 快照时刻还在运行的作业没有结束时间. 它们不是缺失值, 是右删失: 你知道它们至少跑了这么久, 只是还不知道最终跑多久.

### 标签

聚合 / 基础 / 陷阱排查

### 解题思路

按 `is_censored` 分两组, 对比几个关键量. 最重要的是 `planned_hours` 的对比, 因为这一列删失与否都有值, 是唯一可以公平比较的口径.

如果两组的 `planned_hours` 差不多, 说明删失是随机的, 丢掉影响不大. 如果删失组明显更长, 说明删失和结局相关, 丢掉会产生系统性偏差.

同时看 `requested_gpus`, 因为 GPU 规模直接决定中断代价, 这关系到删失偏差会不会影响下游决策.

### SQL

```sql
SELECT
    j.is_censored,
    COUNT(*)                       AS jobs,
    ROUND(AVG(j.planned_hours), 1) AS avg_planned_h,
    ROUND(AVG(j.actual_hours), 1)  AS avg_actual_h,
    ROUND(MAX(j.planned_hours), 1) AS max_planned_h,
    ROUND(AVG(j.requested_gpus), 0) AS avg_gpus,
    GROUP_CONCAT(DISTINCT j.job_type) AS job_types
FROM training_job j
GROUP BY j.is_censored;
```

### 预期结果与业务结论

| is_censored | jobs | avg_planned_h | avg_actual_h | avg_gpus |
| :-- | :-- | :-- | :-- | :-- |
| 0 | 675 | 127.0 | 128.5 | 144 |
| 1 | 225 | 553.9 | (空) | 630 |

删失组的计划时长是已完成组的 4.4 倍, GPU 规模是 4.4 倍. 删失完全不是随机的: 跑得越久的作业越可能在快照时刻还没结束.

这意味着 `WHERE actual_hours IS NOT NULL` 会把最长, 最大, 中断代价最高的那 25% 作业整体从训练集里剔掉. 训出来的模型会系统性低估长作业的剩余时间, 而决策公式恰恰依赖这个估计来确定风险窗口. 低估作业时长会让你放过本该迁移的节点.

正确做法是用生存分析或者删失感知的损失函数, 把删失样本作为 "至少跑了这么久" 的信息纳入. `model_registry` 里的 v1.1-censor-aware 版本用的就是 AFT 模型.

下一步: 最后一个数据完整性陷阱, 见 Q10.

---

## 12. Q10 消失的坏卡

### 业务背景

你想做卡级的可靠性分析, 算一下各批次的 GPU 故障率, 为采购决策提供输入. 自然的做法是拿 `gpu_device` 和维修工单按序列号 join.

结果一个都 join 不上.

### 标签

标量子查询 / 中级 / 陷阱排查

### 解题思路

用四个标量子查询把关键数字并排放出来: 有多少张 RMA 工单, 其中有多少能在设备表里找到对应序列号, 设备表现有多少行, 加起来原本装了多少张.

这条查询的写法很简单, 难的是想到要查它. 触发点是: 当一个 join 返回 0 行时, 先怀疑数据模型而不是 SQL 写法.

### SQL

```sql
SELECT
    (SELECT COUNT(*) FROM maintenance_work_order WHERE rma_returned = 1) AS rma_work_orders,
    -- 按序列号回连设备表, 看能匹配上几条
    (SELECT COUNT(*) FROM maintenance_work_order w
    JOIN gpu_device d ON d.serial_number = w.replaced_serial
    WHERE w.rma_returned = 1)                                          AS matched_in_device_table,
    (SELECT COUNT(*) FROM gpu_device)                                    AS devices_in_table,
    (SELECT COUNT(*) FROM gpu_device)
    + (SELECT COUNT(*) FROM maintenance_work_order WHERE rma_returned = 1)
    AS originally_installed;
```

### 预期结果与业务结论

| rma_work_orders | matched_in_device_table | devices_in_table | originally_installed |
| :-- | :-- | :-- | :-- |
| 28 | 0 | 1,572 | 1,600 |

28 张卡被 RMA 退回, 但在设备表里一张都找不到. 因为退回的卡已经从主表移除了.

后果是: 任何以 `gpu_device` 为基础的可靠性分析, 分母里都不包含最不可靠的那 28 张卡, 分子里也不包含它们的故障. 算出来的故障率是幸存者的故障率, 必然偏低.

要算准, 必须把工单里的 RMA 记录并回来, 也就是把 `gpu_device` 和 `maintenance_work_order` 做全外连接式的合并, 而不是从设备表出发做内连接.

这个坑在任何做了软删除或者归档的系统里都会出现, 而且很难被发现, 因为查询不报错, 只是结果偏乐观.

下一步: 数据体检和陷阱排查做完了, 开始评估现有模型. 见 Q11.

---

## 13. Q11 预算约束下的召回率

### 业务背景

Ana 要在季度评审上回答一个问题: 这个模型每天能帮我们避免多少次崩溃.

AUC 回答不了这个问题. 现场运维每天能处理的节点数是有限的, 每次排空都要迁移作业, 占用备用容量, 影响客户. 实际预算大约是每天最多动 1% 到 2% 的节点. 真正的问题是: 在这个预算下, 能抓住多少故障.

### 标签

窗口函数 NTILE / 高级 / 模型评估

### 解题思路

先把线上打分和标签 join 起来, 然后用 `NTILE(200)` 把样本按分数降序切成 200 个等份, 每份 0.5%. 这样 `pct_bucket <= 2` 就是分数最高的 1%, `<= 4` 就是 2%, 以此类推.

用 `NTILE` 而不是 `PERCENT_RANK`, 是因为前者直接给出桶编号, 后面按预算过滤更直观.

预算列表用 `VALUES` 子句构造成一个内联表, 然后和排名结果做不等值连接. SQLite 支持 `VALUES` 作为 CTE, 写法是 `budgets(budget_pct) AS (VALUES (1), (2), ...)`.

分母要用全体正例数而不是当前桶的正例数, 所以用标量子查询单独算.

### SQL

```sql
WITH scored AS (
    SELECT p.gpu_node_id, p.as_of_ts, p.raw_score, l.label_value
    FROM prediction_log p
    JOIN label_record l ON l.gpu_node_id = p.gpu_node_id AND l.as_of_ts = p.as_of_ts
),
    -- 按分数降序切 200 份, 每份 0.5%. pct_bucket <= 2 即分数最高的 1%
ranked AS (
    SELECT *, NTILE(200) OVER (ORDER BY raw_score DESC) AS pct_bucket FROM scored
),
budgets(budget_pct) AS (VALUES (1), (2), (5), (10))
SELECT
    b.budget_pct || '%'                        AS daily_budget,
    COUNT(*)                                   AS nodes_touched,
    SUM(r.label_value)                         AS failures_caught,
    (SELECT SUM(label_value) FROM scored)      AS failures_total,
    ROUND(SUM(r.label_value) * 100.0 /
        (SELECT SUM(label_value) FROM scored), 1) AS recall_pct,
    ROUND(SUM(r.label_value) * 100.0 / COUNT(*), 2) AS precision_pct
FROM budgets b
JOIN ranked r ON r.pct_bucket <= b.budget_pct * 2
GROUP BY b.budget_pct
ORDER BY b.budget_pct;
```

### 预期结果与业务结论

| daily_budget | nodes_touched | failures_caught | failures_total | recall_pct | precision_pct |
| :--- | :-- | :-- | :-- | :-- | :-- |
| 1% | 488 | 34 | 60 | 56.7% | 6.97% |
| 2% | 976 | 35 | 60 | 58.3% | 3.59% |
| 5% | 2,440 | 39 | 60 | 65.0% | 1.60% |
| 10% | 4,880 | 41 | 60 | 68.3% | 0.84% |

这才是可以拿去评审的数字. 在每天动 1% 节点的预算下, 能抓住 56.7% 的故障, 精确率 6.97% (每 14 次排空里有 1 次是真的要坏).

注意边际收益衰减得非常快: 预算从 1% 放到 10%, 触碰的节点数翻了十倍, 召回只从 56.7% 涨到 68.3%. 说明剩下那 30% 的故障在分数上和正常节点几乎无法区分, 它们多半是劣化期极短的突发故障, 24 小时前根本没有征兆.

这个结论直接影响下一步投资方向: 继续调模型的边际收益很低, 不如去改善 checkpoint 策略, 让中断本身变便宜.

下一步: 精确率 6.97% 意味着大量误报. 但在动阈值之前, 先确认分数本身是不是可信的概率. 见 Q12.

---

## 14. Q12 可靠性曲线, 概率高估了多少倍

### 业务背景

决策公式里 `P_fail` 要拿去乘美元. 这意味着模型输出的不能只是一个排序分, 必须是一个校准过的概率: 模型说 0.8, 就应该有 80% 真的坏.

`calibration_bin` 表已经把可靠性曲线的分箱数据存好了. 你要做的是看一眼预测值和真实频率差多远.

### 标签

聚合 / 基础 / 模型评估

### 解题思路

直接查 `calibration_bin`, 挑一个评估窗口. 关键是自己加一列 `overestimate_factor`, 也就是预测均值除以真实频率. 除法要用 `NULLIF` 保护, 因为有些分箱的真实频率是 0.

过滤掉样本数太少的分箱 (这里取 15), 否则真实频率的估计噪声太大, 比值会很离谱.

### SQL

```sql
SELECT
    c.bin_lower, c.bin_upper, c.sample_count,
    ROUND(c.mean_predicted, 4) AS mean_predicted,
    ROUND(c.observed_rate, 4)  AS observed_rate,
    -- 真实频率可能为 0, 必须用 NULLIF 保护
    ROUND(c.mean_predicted / NULLIF(c.observed_rate, 0), 1) AS overestimate_factor
FROM calibration_bin c
WHERE c.eval_window_start = '2026-05-01 00:00:00.000000'
    AND c.sample_count >= 15
ORDER BY c.bin_lower;
```

### 预期结果与业务结论

| bin | sample_count | mean_predicted | observed_rate | overestimate_factor |
| :--- | :-- | :-- | :-- | :-- |
| 0.0 到 0.1 | 6,326 | 0.0541 | 0.0002 | 342.2 |
| 0.1 到 0.2 | 3,248 | 0.1414 | 0.0003 | 459.2 |
| 0.2 到 0.3 | 1,302 | 0.2426 | 0.0008 | 315.9 |
| 0.3 到 0.4 | 587 | 0.3427 | 0.0000 | NULL |
| 0.4 到 0.5 | 268 | 0.4466 | 0.0037 | 119.7 |
| 0.5 到 0.6 | 136 | 0.5451 | 0.0000 | NULL |
| 0.6 到 0.7 | 80 | 0.6466 | 0.0125 | 51.7 |
| 0.7 到 0.8 | 24 | 0.7490 | 0.0000 | NULL |
| 0.8 到 0.9 | 16 | 0.8480 | 0.0625 | 13.6 |

`sample_count >= 15` 的过滤下这个窗口一共返回 9 箱. 其中三箱 (0.3-0.4 / 0.5-0.6 / 0.7-0.8) 的真实频率是 0, 被 `NULLIF` 保护后 `overestimate_factor` 返回 NULL —— 这三箱样本量本来就小 (最少的只有 24 个), 窗口内没有一个节点真的故障, 这本身也是高分段极度稀疏的佐证. 有非零真实频率的那六箱, 每一档都高估了一个数量级以上. 模型说 84.8% 会坏的那批节点, 实际只有 6.25% 坏了.

这个模型的**排序能力是好的** (AUC 0.85, 高分段确实更容易坏), 但**数值完全不能信**. 把它直接塞进 `P_fail x 中断代价 > 迁移代价` 这个公式, 会让几乎所有决策都倾向于迁移, 因为收益被系统性放大了几十倍.

修复很便宜: 在验证集上套一层保序回归 (isotonic regression), 排序不变, 数值对齐. `model_registry` 里的 v1.1-isotonic 就是这个版本, 它的 AUC 和基线完全一样 (0.8513), 但 Brier score 显著改善.

这是整个项目里投入产出比最高的一个改动, 而且上一位 DS 已经训好了模型, 只是没上线.

下一步: 校准之外, 模型还有没有别的问题? 看看不同硬件上的表现, 见 Q13.

---

## 15. Q13 按硬件批次切片的漂移

### 业务背景

集群在 2026 年 2 月底上了一批 GB200 节点, 现在占机队四分之一. 这批硬件的功率密度和互联架构都和上一代不同. 你需要确认模型在新硬件上还管不管用.

整体指标看不出这件事, 因为新硬件只占四分之一, 它的问题会被稀释.

### 标签

切片查询 / 中级 / 模型评估

### 解题思路

`evaluation_metric` 表已经按 `slice_dimension` 存好了切片指标, 直接过滤 `purchase_lot` 即可, 不用自己算.

这张表的设计本身就是要点: 上线的时候就应该把切片维度定下来并持续计算, 而不是等出了问题再回头算. 切片维度选什么, 取决于你预期哪些子群体可能不同, 硬件批次, 客户等级, 地理位置, 时间段.

按 `slice_value` 和窗口排序, 这样同一批次的时间趋势能连起来看.

### SQL

```sql
SELECT
    e.slice_dimension,
    e.slice_value,
    DATE(e.eval_window_start) AS window_start,
    e.sample_count,
    e.positive_count,
    e.auc,
    e.precision_at_threshold,
    e.recall_at_threshold,
    e.brier_score
FROM evaluation_metric e
WHERE e.slice_dimension = 'purchase_lot'
ORDER BY e.slice_value, e.eval_window_start;
```

### 预期结果与业务结论

十二行, 三个批次乘以四个半月窗口. 摘录:

| slice_value | window_start | sample_count | positive_count | auc | recall |
| :--- | :--- | :-- | :-- | :-- | :-- |
| LOT-GB200-2026Q1 | 2026-04-16 | 3,000 | 12 | 0.8574 | 0.4167 |
| LOT-GB200-2026Q1 | 2026-05-16 | 3,200 | 12 | 0.8370 | 0.5000 |
| LOT-H100-2024Q3 | 2026-04-01 | 5,040 | 4 | 0.9982 | 1.0000 |
| LOT-H100-2024Q3 | 2026-04-16 | 5,040 | 5 | 0.7833 | 0.4000 |
| LOT-H200-2025Q2 | 2026-04-16 | 3,960 | 8 | 0.9987 | 1.0000 |

有两件事要说清楚, 而且第二件比第一件重要.

第一, 用完整的上线后数据训练评估 (不受这里每窗正例数太少的限制), 三个批次的 AUC 是 H100 0.9016, H200 0.8274, GB200 0.8207. GB200 确实是最差的一个, 差距约 8 个百分点. 机理在 Q14.

第二, 这张表本身给出了一个更重要的教训: **每个切片每个窗口只有 4 到 12 个正例, 这个样本量下的 AUC 是没法用的**. 你可以看到 H100 在 4 月上半月 AUC 0.9982, 下半月掉到 0.7833, 这不是模型两周内退化了, 是 4 个正例和 5 个正例之间的随机波动.

所以正确的做法是: 切片监控要用更长的窗口 (至少累计 30 个正例再算), 或者改用对样本量不敏感的指标. 在正例这么稀疏的问题上, 把监控窗口切太细, 得到的只是噪声, 而且会不断触发假警报, 最后没人再看告警.

下一步: GB200 到底哪里不一样, 见 Q14.

---

## 16. Q14 特征分布本身漂移了吗

### 业务背景

Q13 说 GB200 上模型表现差一些. 你需要知道原因, 因为原因决定了修法: 如果只是数值平移, 做个归一化就行; 如果是失效机理变了, 就必须重训甚至重新做特征.

### 标签

CTE + 分组对比 / 中级 / 模型评估

### 解题思路

对比训练窗和生产窗的特征均值, 按批次分组. 挑三个代表不同失效机理的特征: `hbm_temp_excess_over_lot` 代表热, `nvlink_retrans_mean_24h` 代表互联, `power_dev_mean_24h` 代表供电.

用 CTE 先给每行打上时期标签, 再和节点表 join 拿批次. 注意 `WHERE` 要把 3 月 12 日到 4 月 1 日这段排除掉, 那是验证集和测试集, 混进来会模糊对比.

NVLink 重传率的数值很小 (万分之几), 乘 1000 再展示, 否则四舍五入之后全是 0.

### SQL

```sql
WITH periods AS (
    SELECT f.*,
        CASE WHEN f.as_of_ts < '2026-03-12' THEN 'train' ELSE 'production' END AS period
    FROM feature_snapshot f
    -- 中间的验证与测试窗排除掉, 只做训练窗与生产窗的干净对比
    WHERE f.as_of_ts < '2026-03-12' OR f.as_of_ts >= '2026-04-01'
)
SELECT
    n.purchase_lot,
    p.period,
    COUNT(*) AS n,
    ROUND(AVG(p.hbm_temp_excess_over_lot), 3)        AS avg_hbm_excess,
    -- 重传率量级在万分之几, 乘 1000 才看得见
    ROUND(AVG(p.nvlink_retrans_mean_24h) * 1000, 4)  AS avg_nvlink_x1000,
    ROUND(AVG(p.power_dev_mean_24h) * 100, 4)        AS avg_power_dev_pct
FROM periods p
JOIN gpu_node n ON n.id = p.gpu_node_id
GROUP BY n.purchase_lot, p.period
ORDER BY n.purchase_lot, p.period;
```

### 预期结果与业务结论

| purchase_lot | period | n | avg_hbm_excess | avg_nvlink_x1000 | avg_power_dev_pct |
| :--- | :--- | :-- | :-- | :-- | :-- |
| LOT-GB200-2026Q1 | train | 1,228 | 8.056 | 0.6831 | 0.4190 |
| LOT-GB200-2026Q1 | production | 12,200 | 7.846 | 0.6536 | 0.3487 |
| LOT-H100-2024Q3 | train | 12,768 | 9.313 | 0.4930 | 0.0792 |
| LOT-H100-2024Q3 | production | 20,496 | 9.355 | 0.4938 | 0.0750 |
| LOT-H200-2025Q2 | train | 10,032 | 8.886 | 0.5051 | 0.0940 |
| LOT-H200-2025Q2 | production | 16,104 | 8.907 | 0.5054 | 0.0921 |

关键不在于时间上的漂移, 每个批次自己的 train 和 production 几乎一样, 说明没有时间维度的漂移.

关键在于批次之间的差异. GB200 的 NVLink 重传率是上一代的 1.3 倍, 功耗偏离是 4.4 倍 (0.349% 对 0.075%). 而训练窗里 GB200 只有 1,228 行, 占 5.1%, 生产窗里涨到 12,200 行, 占 25%.

这解释了 Q13 的结果. 模型在训练时几乎只见过热失效样本, 于是学会了 "看温度和 ECC"; GB200 的劣化信号却主要出现在 NVLink 和功耗上, 这两个特征在训练集里的信噪比很低, 模型没怎么用.

修法不是归一化 (数值平移可以归一化, 机理不同不行), 而是重训, 而且重训时要对 GB200 样本加权, 或者干脆按批次分别建模.

下一步: 还有一个更隐蔽的一致性问题, 见 Q15.

---

## 17. Q15 训练服务偏斜的证据

### 业务背景

有一件事一直让上一位 DS 困惑: 离线评估的指标总是比线上实际表现好一截, 但他没找到原因就离职了.

这条查询给出答案.

### 标签

日期差 + 子查询 / 中级 / 模型评估

### 解题思路

`prediction_log` 里有两个时间: `as_of_ts` 是预测的目标时点, `feature_as_of_ts` 是线上真正取到特征的时点. 两者的差就是服务侧的特征滞后.

把这个滞后和 `feature_definition` 里 `availability_lag_minutes > 0` 的特征列表放在一起看, 就能确认是哪几个特征受影响.

用标量子查询把特征清单直接拼进结果, 一条查询就能得到完整结论.

### SQL

```sql
SELECT
    ROUND((JULIANDAY(p.as_of_ts) - JULIANDAY(p.feature_as_of_ts)) * 1440, 0) AS serving_lag_minutes,
    COUNT(*) AS predictions,
    (SELECT COUNT(*) FROM feature_definition WHERE availability_lag_minutes > 0) AS lagged_features,
    (SELECT GROUP_CONCAT(feature_name, ', ') FROM feature_definition
    WHERE availability_lag_minutes > 0) AS affected
FROM prediction_log p
GROUP BY serving_lag_minutes;
```

### 预期结果与业务结论

| serving_lag_minutes | predictions | lagged_features | affected |
| :-- | :-- | :-- | :--- |
| 60 | 48,800 | 3 | `hbm_temp_excess_over_lot`, `firmware_age_days`, `open_work_order_count` |

全部 48,800 次线上打分, 特征都是取自一小时前. 而离线训练时, 如果按 `as_of_ts` 去 join `feature_snapshot`, 拿到的是那一刻的理想值.

三个受影响的特征里, `hbm_temp_excess_over_lot` 是热族里最强的那个. 一小时的滞后在劣化后期是有实质影响的, 因为那正是指标变化最快的阶段.

修法有两条. 短期: 离线评估时按 `feature_as_of_ts` 取特征, 让离线和线上对齐, 这样至少指标是诚实的. 长期: 把这三个特征的计算链路从数仓批处理挪到实时流, 把滞后消掉, 这样模型能拿到更新的信息, 性能会真的提升.

下一步: 模型评估做完了. 最后核算业务价值, 见 Q16.

---

## 18. Q16 模型到底赚了多少钱

### 业务背景

这是 Ana 交给你的第一项任务, 也是季度评审上唯一会被 CTO 追问的数字.

`action_outcome` 表里有一列 `net_benefit_usd`, 直接求和就有答案. 但你需要先搞清楚这一列是怎么算出来的.

### 标签

多表连接 + 聚合 / 中级 / 价值核算

### 解题思路

按 `executed_action` 和 `is_holdout` 分组, 把反事实损失, 实际损失, 迁移成本, 净收益四个量并排列出来.

分组是必要的, 因为四个臂的经济学完全不同. 只有真的执行了排空的那 51 次才既产生迁移成本又产生收益; 留出组和 override 组既没花钱也没省钱; 仅监控组什么都没发生.

`expected_cost_usd` 这一列要小心: 它是决策时的**预估** 迁移成本, 每条决策都有, 但只有实际执行了排空的那些才真的花掉了. 把它对全部 464 条决策求和会得到一个虚构的支出.

### SQL

```sql
SELECT
    d.executed_action,
    d.is_holdout,
    COUNT(*)                                 AS decisions,
    ROUND(SUM(o.counterfactual_lost_usd), 0) AS counterfactual_loss_usd,
    ROUND(SUM(o.actual_lost_usd), 0)         AS actual_loss_usd,
    -- 注意: 这是决策时的预估成本, 只有 DRAIN 那一行是真的花掉了
    ROUND(SUM(d.expected_cost_usd), 0)       AS migration_cost_usd,
    ROUND(SUM(o.net_benefit_usd), 0)         AS reported_net_benefit_usd
FROM decision_log d
JOIN action_outcome o ON o.decision_log_id = d.id
GROUP BY d.executed_action, d.is_holdout
ORDER BY reported_net_benefit_usd DESC;
```

### 预期结果与业务结论

| executed_action | is_holdout | decisions | counterfactual_loss_usd | actual_loss_usd | migration_cost_usd | reported_net_benefit_usd |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| DRAIN | 0 | 51 | 854,733 | 1,693 | 105,741 | 747,299 |
| MONITOR | 0 | 376 | 119 | 119 | 798,214 | 0 |
| NO_ACTION | 0 | 17 | 4,078 | 4,078 | 34,027 | 0 |
| NO_ACTION | 1 | 20 | 6,109 | 6,109 | 44,373 | 0 |

全部 464 条决策的净收益合计 747,299 美元, 全部来自那 51 次真的执行了的排空.

但这个数字**建立在一个假设上**, 报告时必须说明. `counterfactual_lost_usd` 是 "如果不排空会损失多少" 的估计, 而不是观测值, 节点被修好了, 我们永远不知道它到底会不会坏, 会波及哪些作业.

那个 798,214 美元的 `migration_cost_usd` 是一个陷阱: 它是 376 次仅监控决策的预估迁移成本, 而这 376 次什么都没做, 一分钱没花. 如果你不分组直接把这一列求和, 会凭空多出八十万美元的支出.

诚实的报告应该这样写: 模型上线两个月, 主动排空 51 次, 直接支出 10.6 万美元; 基于留出组观测到的 80% 高分段真实故障率, 估计避免了约 85 万美元的中断损失, 净收益约 75 万美元, 置信度受限于留出组仅 20 个样本.

下一步: 那 51 次排空里有多少是必要的? 见 Q17.

---

## 19. Q17 为什么不能用故障率评估排空决策

### 业务背景

评审会上一定会有人问: 你们排空了 51 次, 其中多少次是真的要坏, 多少次是白折腾.

这是个合理的问题, 但它没有直接答案. 这条查询要说明的就是为什么.

### 标签

条件聚合 / 高级 / 价值核算

### 解题思路

最自然的写法是按 `node_failed_within_horizon` 分组数一下. 先跑这条查询, 然后盯着结果想清楚它为什么是那个样子.

关键在于理解 `node_failed_within_horizon` 是怎么来的: 它记录的是该节点在观测窗内**实际上** 有没有进入 DOWN 状态. 而排空的目的就是让它不进入 DOWN 状态.

### SQL

```sql
SELECT
    CASE WHEN o.node_failed_within_horizon = 1 THEN ' 真阳性' ELSE ' 假阳性' END AS outcome,
    COUNT(*) AS drains,
    ROUND(SUM(d.expected_cost_usd)) AS migration_cost_usd
FROM decision_log d
JOIN action_outcome o ON o.decision_log_id = d.id
WHERE d.executed_action = 'DRAIN'
GROUP BY outcome;
```

### 预期结果与业务结论

| outcome | drains | migration_cost_usd |
| :--- | :-- | :-- |
| 假阳性 | 51 | 105,741 |

只有一行. 51 次排空**全部** 是 "假阳性", 真阳性 0 次.

如果照着这个结果汇报, 结论会是 "模型 100% 误报, 白花了 10.6 万美元, 建议关停". 而这个结论是完全错误的.

原因是: 排空的作用就是阻止故障发生. 节点被排空并检修之后当然不会进入 DOWN 状态, 所以 `node_failed_within_horizon` 必然是 0. 这一列在被处置过的样本上恒等于 0, 没有任何信息量.

这是选择性标签在评估环节的表现形式, 而且比训练环节更危险, 训练环节的偏差至少会体现为指标下降, 这里的偏差会直接给出一个符号相反的结论.

唯一正确的评估方式是用留出组. Q8 已经给出: 留出组 20 个样本里 16 个真的故障了, 高分段真实故障率 80%. 把这个 80% 应用到被排空的 51 个节点上, 估计其中约 41 个本来会坏.

所以正确的说法是: 我们排空了 51 次, 基于留出组估计约 41 次是必要的, 精确率约 80%, 而不是 0%.

这条查询的教学点不是 SQL, 是 **"在有干预的系统里, 观测到的结果不能直接用来评估干预本身"**. 这是因果推断的入门课, 也是所有上线后的决策系统都必须面对的问题.

下一步: 前面都在讲 M1. 最后三条看看模型族里其他几个模型的数据长什么样. 见 Q18.

---

## 20. Q18 M2 作业时长训练集的删失结构

### 业务背景

你要重建 M2. Q9 已经说明删失不是随机的, 这条查询进一步看删失在各类作业上的分布, 因为这决定了要不要按作业类型分别建模.

### 标签

条件聚合 / 中级 / 价值核算

### 解题思路

按 `job_type` 分组, 同时算三个口径的时长: 只用已完成作业的平均实际时长 (天真做法), 全部作业的平均计划时长 (无偏但不是目标变量), 以及删失作业的平均计划时长.

三个数字放在一起, 就能看出天真做法在哪类作业上偏得最厉害.

条件聚合的写法是 `AVG(CASE WHEN ... THEN col END)`, `CASE` 不写 `ELSE` 时返回 NULL, 而 `AVG` 会自动跳过 NULL, 这正是需要的行为.

### SQL

```sql
SELECT
    j.job_type,
    COUNT(*)                                        AS jobs,
    SUM(j.is_censored)                              AS censored,
    ROUND(SUM(j.is_censored) * 100.0 / COUNT(*), 1) AS censored_pct,
    -- 天真做法: 只看已完成的
    ROUND(AVG(CASE WHEN j.is_censored = 0 THEN j.actual_hours END), 1) AS naive_avg_hours,
    ROUND(AVG(j.planned_hours), 1)                  AS planned_avg_hours_all,
    ROUND(AVG(CASE WHEN j.is_censored = 1 THEN j.planned_hours END), 1) AS censored_planned_avg
FROM training_job j
GROUP BY j.job_type
ORDER BY censored_pct DESC;
```

### 预期结果与业务结论

| job_type | jobs | censored | censored_pct | naive_avg_hours | planned_avg_hours_all | censored_planned_avg |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| PRETRAIN | 339 | 208 | 61.4% | 445.5 | 532.9 | 591.5 |
| FINETUNE | 253 | 12 | 4.7% | 62.6 | 63.1 | 82.3 |
| RLHF | 95 | 4 | 4.2% | 104.3 | 105.4 | 151.4 |
| EVAL_SWEEP | 113 | 1 | 0.9% | 8.1 | 7.7 | 3.4 |
| RESEARCH | 100 | 0 | 0.0% | 28.9 | 28.5 | 28.9 |

删失几乎全部集中在预训练上: 339 个预训练作业里 208 个还在跑, 删失率 61.4%. 其他类型的删失率都在 5% 以下.

而预训练恰恰是唯一重要的那一类, 它的 GPU 规模最大, 中断代价最高, 也正是自愈调度要保护的对象. 换句话说, 删失偏差集中打击了模型最需要准确的那个区域.

两条建议. 第一, 必须用删失感知的方法, 简单丢弃在预训练上会低估将近 20% 的时长 (445.5 对 532.9). 第二, 考虑按作业类型分别建模, 因为删失机制在不同类型上差别太大, 一个统一模型很难同时处理好.

下一步: M3 的训练数据, 见 Q19.

---

## 21. Q19 M3 恢复时长的驱动因素

### 业务背景

M3 预测的是 "中断之后多久能恢复满速". 这个量直接进中断代价公式, 而且它不是常数, 取决于中断原因, 作业规模, 以及当时集群的拥挤程度.

在建模之前, 先看看数据里这个量的结构.

### 标签

连接 + 聚合 / 中级 / 价值核算

### 解题思路

`job_interruption` 里有三段时长: 回滚, 重排队, 恢复满速. 三者加起来乘 GPU 数就是损失. join `job_attempt` 拿到 GPU 规模.

按 `cause` 分组, 因为不同原因的恢复过程是不一样的: 硬件故障要等换件或者重新调度到别的节点, 而用户主动取消基本可以立刻重启.

按总损失降序排, 直接看出该优先建模哪一类.

### SQL

```sql
SELECT
    i.cause,
    COUNT(*)                              AS interruptions,
    ROUND(AVG(a.gpus_allocated), 0)       AS avg_gpus,
    ROUND(AVG(i.rollback_minutes), 1)     AS avg_rollback_min,
    ROUND(AVG(i.requeue_wait_minutes), 1) AS avg_requeue_min,
    ROUND(AVG(i.recovery_minutes), 1)     AS avg_recovery_min,
    ROUND(AVG(i.lost_gpu_hours), 0)       AS avg_lost_gpu_hours,
    ROUND(SUM(i.lost_usd), 0)             AS total_lost_usd
FROM job_interruption i
JOIN job_attempt a ON a.id = i.job_attempt_id
GROUP BY i.cause
ORDER BY total_lost_usd DESC;
```

### 预期结果与业务结论

| cause | interruptions | avg_gpus | avg_rollback_min | avg_recovery_min | avg_lost_gpu_hours | total_lost_usd |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| NODE_HARDWARE_FAILURE | 814 | 644 | 137.1 | 53.4 | 2,465 | 5,717,886 |
| SOFTWARE_OOM | 36 | 390 | 84.8 | 46.5 | 1,377 | 141,233 |
| NETWORK_FABRIC_FAULT | 32 | 299 | 82.7 | 45.1 | 944 | 86,105 |
| PREEMPTION_BY_HIGHER_PRIORITY | 30 | 275 | 73.7 | 45.6 | 978 | 83,599 |
| DR_CURTAILMENT | 39 | 208 | 66.1 | 39.8 | 691 | 76,762 |
| USER_CANCEL | 27 | 306 | 70.9 | 45.2 | 982 | 75,545 |

节点硬件故障占了 978 次中断的 83%, 占 618 万美元损失的 92.5%. 自愈调度项目瞄准的方向是对的.

从建模角度看, 三段时长里最大的是回滚 (137.1 分钟), 而回滚时长完全由 checkpoint 间隔决定, 是可以用公式算出来的, 不需要模型. 真正需要预测的是恢复时长 (53.4 分钟), 它的方差来自重新调度和 warmup.

有意思的是恢复时长在各类原因上差别不大 (39.8 到 53.4 分钟), 而回滚时长差别很大 (66.1 到 137.1 分钟). 这说明 M3 其实可以做得很简单, 甚至用分组均值就够了, 把建模精力放到 M1 和 M2 上更划算.

顺带一提, `DR_CURTAILMENT` 那 39 次是园区参与电网需求响应主动削减负载造成的, 对应能源团队那份数据集里的削减事件. 它不是故障, 是一个商业决策的副作用.

下一步: 最后一个模型, 见 Q20.

---

## 22. Q20 M5 慢节点, 没有标签怎么办

### 业务背景

M5 要找的是 "还没坏但已经变慢" 的节点. 这类节点不会触发任何告警, 但会拖慢整个同步训练组, 分布式训练的速度由最慢的那个节点决定.

难点在于这个问题没有标签. 没人标注过 "这台机器是慢节点", 只有训练步的耗时数据.

### 标签

CTE + 相关子查询 / 高级 / 价值核算

### 解题思路

`job_step_metric` 里有一列 `slowest_node_id`, 记录该步中最慢的节点. 这是一个弱标签: 它不告诉你哪台机器有问题, 但如果某台机器反复出现在这一列里, 就值得怀疑.

第一个 CTE 按节点聚合出现次数和平均指标. 第二个 CTE 算全集群基准, 注意基准要用 `slowest_node_id IS NULL` 的记录, 也就是没有明显慢节点的那些步, 否则基准会被慢节点自己拉低.

最后用相关子查询数这些嫌疑节点的 DOWN 次数, 验证 "慢是不是故障前兆". 注意这个子查询统计的是该节点**全时段**的 DOWN 次数 (所以列名叫 `total_failures`, 没有做 "变慢之后才发生" 的时间约束); 由于慢与坏基本不相关, 这个简化不影响结论.

### SQL

```sql
WITH node_steps AS (
    SELECT s.slowest_node_id AS node_id,
        COUNT(*) AS times_slowest,
        ROUND(AVG(s.step_time_ms), 1) AS avg_step_ms,
        ROUND(AVG(s.mfu_pct), 2) AS avg_mfu
    FROM job_step_metric s
    WHERE s.slowest_node_id IS NOT NULL
    GROUP BY s.slowest_node_id
),
    -- 基准要用 "没有明显慢节点" 的步, 否则基准会被慢节点自己拉低
fleet AS (
    SELECT AVG(mfu_pct) AS fleet_mfu FROM job_step_metric WHERE slowest_node_id IS NULL
)
SELECT
    n.node_code, n.purchase_lot,
    ns.times_slowest, ns.avg_step_ms, ns.avg_mfu,
    ROUND((SELECT fleet_mfu FROM fleet) - ns.avg_mfu, 2) AS mfu_gap_vs_fleet,
    -- 该节点全时段的 DOWN 次数, 未限定 "变慢之后", 故命名为 total 而非 later
    (SELECT COUNT(*) FROM node_state_transition t
    WHERE t.gpu_node_id = n.id AND t.to_state = 'DOWN') AS total_failures
FROM node_steps ns
JOIN gpu_node n ON n.id = ns.node_id
ORDER BY ns.times_slowest DESC
LIMIT 10;
```

### 预期结果与业务结论

| node_code | purchase_lot | times_slowest | avg_mfu | mfu_gap_vs_fleet | total_failures |
| :--- | :--- | :-- | :-- | :-- | :-- |
| A3-199 | LOT-GB200-2026Q1 | 83 | 37.30 | 13.71 | 1 |
| A3-119 | LOT-H200-2025Q2 | 81 | 36.94 | 14.07 | 0 |
| A3-059 | LOT-H100-2024Q3 | 74 | 36.71 | 14.30 | 0 |
| A3-104 | LOT-H200-2025Q2 | 73 | 36.67 | 14.34 | 0 |
| A3-063 | LOT-H100-2024Q3 | 72 | 37.26 | 13.75 | 0 |

上表是按 `times_slowest DESC` 排序的连续前 5 行 (`LIMIT 10` 的完整结果还有 5 行).

嫌疑节点的 MFU 比集群基准低 13 到 15 个百分点. 对一个 1,024 卡的训练作业, 这相当于白白浪费七分之一的算力.

但最后一列给出了一个重要的否定结论: 完整的前十名里只有两个节点全时段真的故障过 (排第 1 的 A3-199 和排第 9 的 A3-105, 各 1 次), 上面展示的前五名里只有 A3-199 一个. 慢和坏基本不相关.

这意味着 M5 不应该被当成 M1 的补充信号 (慢节点不是故障前兆), 而是一个独立的价值来源: 找出慢节点并把它们从同步组里剔除, 直接提升训练吞吐, 和故障预测是两件事.

也意味着 M5 不能用故障标签来验证. 它的验证方式只能是干预实验: 剔除嫌疑节点, 看训练吞吐有没有提升.

---

## 23. 陷阱与查询映射

| 陷阱 | 对应查询 | 实测量级 |
| :--- | :--- | :--- |
| 1. 选择性标签 | Q7, Q8, Q17 | 正例率 0.582% 掉到 0.123%; 重训 AUC 0.5688 对 0.6562 |
| 2. 特征泄漏 | Q2, Q5 | 泄漏特征单变量正例率 58.82% 对基线 0.33%; AUC 0.8513 涨到 0.9438 |
| 3. 时间泄漏 | Q6 | 293 个正例只来自 74 次事件; 随机划分 AUC 虚高 6.96pp |
| 4. 训练服务偏斜 | Q15 | 3 个特征滞后 60 分钟, 影响全部 48,800 次线上打分 |
| 5. 标签迟到 | Q3, Q4 | 固定滞后 26 小时; 训练窗内 800 行标签不可知 |
| 6. 分布漂移 | Q13, Q14 | GB200 功耗偏离是上一代 4.4 倍; AUC 0.9016 对 0.8207 |
| 7. 极端不平衡 | Q1, Q11 | 训练集 106 个正例; 1% 预算下召回 56.7% 精确 6.97% |
| 8. 概率未校准 | Q12 | 高估 13.6 倍到 459 倍 |
| 9. 右删失 | Q9, Q18 | 预训练删失率 61.4%; 天真估计低估 20% |
| 10. 幸存者偏差 | Q10 | 28 张 RMA 卡全部不在设备表里 |

二十条查询跑完, 你应该能给 Ana 三个交付物: 一份说明模型上线两个月净收益约 75 万美元 (并附上置信度限制) 的评审材料; 一份诊断报告, 指出模型未校准是当前最大的问题, 修复成本极低; 一份 v2 重训方案, 核心是剔除删失样本, 排除两个泄漏特征, 按批次加权处理 GB200 漂移, 并把三个滞后特征的链路改成实时.
