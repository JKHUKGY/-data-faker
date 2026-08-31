# 金融科技 — 中小企业贷款流水线 业务背景

> 本文档是 `fintech_smb_lending_pipeline_medium` 数据集的业务背景说明,负责回答"这是一家什么公司、做什么生意、要解决什么问题"。数据结构请见 `02-fintech_smb_lending_pipeline_medium_er_document-cn.md`,SQL 查询请见 `03-fintech_smb_lending_pipeline_medium_sql_queries-cn.md`。
>
> 读者设定:你是一个刚加入项目的聪明新人,不需要是金融老手。读完本文档,你应该能在第一次站会上跟同事聊清楚这家公司的业务、行业和这次分析要回答的问题。

---

## 1. 公司画像

**Pacific Bridge Lending** 是一家总部位于加州旧金山湾区(Oakland)的中型金融科技(fintech)公司,专注于**中小企业(SMB, Small and Medium-sized Business)贷款**。它不是银行,而是一家"用数据做承保、放款比银行快"的非银放贷机构(non-bank lender)。

公司画像(数量级,非精确值):

- **客户:** 约 800 家活跃借款企业,典型客户是年营收 20 万到 1000 万美元的本地餐饮、零售、技术服务、建筑、酒店等小企业。
- **放款规模:** 过去约两年累计放款数亿美元(单笔 5 万到 50 万美元),折合年放款数量级在两到三亿美元。
- **员工:** 约 50 人,含约 20 名信贷员(loan officer)、一支承保(underwriting)团队、一支催收(collections)团队、财务团队和高管层。
- **地域:** 当前业务集中在加州一个州,客户分布在 Los Angeles、San Francisco、San Diego、Sacramento、San Jose、Fresno、Oakland、Bakersfield、Anaheim、Riverside 等城市。

公司里和本次分析相关的角色(SQL 查询会按头衔点名这些人):

| 头衔 | 中文 | 关心什么 |
|------|------|----------|
| CEO | 首席执行官 | 获客策略、营销预算分配、客户分层 |
| CFO | 首席财务官 | 现金流预测、损失拨备、流动性 |
| CRO (Chief Risk Officer) | 首席风险官 | 风险定价、组合集中度、投资者沟通 |
| Chief Credit Officer | 首席信贷官 | 在贷高风险敞口、每周风险委员会 |
| VP of Underwriting | 承保副总裁 | 审批漏失、信贷员绩效 |
| VP of Operations | 运营副总裁 | 申请处理时长、SLA、人力规划 |
| Marketing Director | 市场总监 | 区域转化率、获客成本 |
| Collections Manager | 催收经理 | 早期预警、逾期趋势 |
| Relationship Manager | 关系经理 | 再定价/再融资机会、客户留存 |
| Investment Committee | 投资委员会 | Vintage 表现、承保标准松紧 |

---

## 2. 商业模式

Pacific Bridge 的赚钱方式很直接:**赚利差(interest spread)**。

公司用自有资本和一条**仓储融资额度(warehouse line,简称"仓储线")**借入资金,再把钱以更高的利率贷给小企业,赚"借出利率 减去 资金成本"的差额。

- 借给客户的利率按风险等级在 **5.5% 到 16.0%** 之间。
- 公司自己的资金成本约 **4%**。
- 因此每笔贷款的毛利差(gross spread)在 **1.5pp 到 12pp** 之间(pp = percentage point,百分点)。
- 一旦借款人违约(default),损失会直接吞掉这些毛利,甚至侵蚀本金。

所以这家公司的利润最终只取决于两件事:

1. **风险定价是否准确** —— 收的利率有没有覆盖真实的违约风险。
2. **能否尽早识别违约** —— 在借款人彻底崩盘前介入,把损失压小、把回收做大。

单位经济(unit economics)层面:平均单笔贷款约 20 万美元,期限 12 到 60 个月,按月等额本息(amortizing)还款。一笔定价正确、按时还清的贷款贡献几个百分点的净利差;一笔违约贷款则可能亏掉本金的一半以上(取决于回收率)。整盘生意是"用很多小的正利差,去对冲少数大的违约损失"。

---

## 3. 行业普及:北美中小企业贷款

如果你来自别的行业,这一节让你快速看懂 SMB lending 这门生意。

**这个行业创造什么价值。** 小企业(餐厅、零售店、技术服务公司、建筑公司)经常需要一笔成长资本:买设备、扩门店、补营运资金(working capital)、扛过淡季。传统银行往往不爱做这种生意——单笔金额小、企业财务不规范、尽调成本高、回报却不成比例。Fintech lender 用数据化承保和更快的审批(几天而非几周)填补了这个空白。

**主要玩家类别(不点名真实公司)。**

- **传统银行与信用社(banks / credit unions):** 资金成本最低,但审批慢、门槛高。
- **SBA 贷款机构:** 通过美国小企业管理局(SBA, Small Business Administration)担保项目放贷,利率低但流程繁琐。
- **在线 / fintech lender:** 像 Pacific Bridge 这样的,快、灵活、利率较高,服务银行不愿碰的客户。
- **商户预付现金(MCA, Merchant Cash Advance)机构:** 按未来营收的折扣买断,实际成本极高,是市场最贵的一档。

**监管与合规框架(北美)。** SMB 放贷受多重监管:

- **ECOA(Equal Credit Opportunity Act,公平信贷机会法)与 Reg B:** 禁止基于种族、性别等的信贷歧视。
- **FCRA(Fair Credit Reporting Act,公平信用报告法):** 规范如何拉取和使用信用报告。
- **CFPB(Consumer Financial Protection Bureau,消费者金融保护局):** 联邦层面的消费者/小微金融监管者。
- **OCC、FDIC:** 银行体系的审慎监管者(非银 lender 通过合作银行间接相关)。
- **州级监管:** 加州由 **DFPI(Department of Financial Protection and Innovation,加州金融保护与创新局)** 监管放贷牌照。
- **KYC / BSA / AML:** 反洗钱与"了解你的客户"要求。
- (加拿大对照:联邦 FCAC 与 OSFI、各省消费者保护法规——本数据集默认市场为美国加州。)

**当下的宏观力量。** 利率上行抬高了仓储线的资金成本,挤压利差;fintech 行业在整合;AI 承保正在改变风险评估;疫情之后,餐饮、酒店等周期性行业(cyclical industries)的信用质量仍受关注;整体信贷在收紧。这些都让"定价是否准确、集中度是否过高"成为高管层每个季度都要盯的事。

---

## 4. 项目框架:你在做什么

你是 Pacific Bridge 的**数据分析师**,被拉进一个**季度组合评审(quarterly portfolio review)**项目,直接向 **CRO(首席风险官)** 汇报,同时为 CFO、投资委员会和董事会准备材料。

公司刚跑完一个季度,管理层手上有一堆悬而未决的问题:Grade C 贷款到底有没有定价不足?组合是不是太集中在餐饮酒店?承保是不是把好客户拒掉了?违约前有没有可识别的预警信号?老客户是不是真的比新客户值钱?你的任务,是用过去约 22 个月的完整贷款数据,把这些问题用 SQL 一个个回答清楚,产出能直接进董事会和投资者材料的结论。

交付物:季度风险评审 deck、定价调整提案、投资者风险更新、以及给运营和催收团队的可执行清单。所有分析都锚定固定参考日 **REFERENCE_DATE = 2026-06-03**(详见第 6 节)。

---

## 5. 本项目要解决的业务问题

整个数据集是为回答下面五个核心业务问题而设计的。每个问题都在 ER 文档里有对应的数据陷阱(deliberately embedded trap),并在 SQL 查询文档里有对应的查询。

1. **Q1 风险定价对齐(Risk Pricing Alignment):** 各风险等级的实际违约率,是否和定价模型假设的违约率匹配?具体说——Grade C 是不是被低估了风险、定价不足?
2. **Q2 组合集中度(Portfolio Concentration):** 我们的未偿组合是不是过度集中在某些周期性行业(尤其餐饮 + 酒店)?单一行业冲击会不会引发连锁违约?
3. **Q3 审批漏失(Approval Leakage / False Negatives):** 我们是不是把一批"画像跟已批优质客户一样好"的申请人错误拒绝了?这些假阴性每年损失多少利息收入?
4. **Q4 早期预警信号(Early Warning Signals):** 违约发生前的几个月,还款行为里有没有可测的恶化(逾期增加、部分付款)?能不能提前 3 个月发现并介入?
5. **Q5 客户全生命周期价值(Customer Lifecycle Value):** 复购客户(repeat customer)和新客户在违约率、贷款金额、审批率上差多少?营销预算该投获客还是投留存?

除了这五个 marquee 问题,数据集还支持一批运营类分析:月度申请量趋势、信贷员绩效记分卡、区域转化率、申请处理时长 SLA、月度现金流预测、Vintage 队列分析等,用来回答日常运营和财务规划的问题。

---

## 6. 数据范围概览

- **时间跨度:** 约 22 个月的申请活动,全部锚定到固定参考日 **REFERENCE_DATE = 2026-06-03**。所有"今天 / 当前快照"的语义(如未偿余额、是否到期、距今月数)都按这个日期计算,而不是系统当前时间,保证多次运行和多次查询结果一致、可复现。
- **数据量(数量级,白话):** 约 800 家客户、约 3000 份申请、约 2230 笔贷款、约 8.1 万行还款计划、约 2.4 万条实际还款、约 190 起违约事件,合计约 11 万行。
- **刻意的范围取舍:**
  - **单一州(加州):** 全部客户都在加州,避免跨州监管和地理噪声,让分析聚焦在风险和定价上。
  - **单一产品线:** 只有面向 SMB 的定期摊销贷款(term loan),没有信用卡、循环额度等其他产品。
  - **个人担保人信用:** 此规模的 SMB 贷款通常以法人/担保人的**个人信用分(FICO 风格)**承保,而非商业信用局分数(如 Paydex、Intelliscore),数据集据此建模。

(本节不列具体表;表结构见 ER 文档。)

---

## 7. 行业知识科普

外行看懂这份数据前,需要的大约半小时背景。建议按"一笔贷款的一生"来理解。

**1) 信贷流水线(lending pipeline)的七个阶段。**

```
申请(application) → 承保/审批(underwriting/decision) → 放款(disbursement)
   → 按月还款(repayment) → (可能)违约(default) → 催收回收(recovery) → 结清/核销
```

- **申请:** 客户提交申请金额和期限,信贷员受理。
- **审批:** 承保团队根据信用分等决定批准(APPROVED)或拒绝(REJECTED)。
- **放款:** 批准后把钱打给客户(disbursement),贷款正式"上账"。
- **还款:** 客户按摊销计划逐月还款(每月一期 installment)。
- **违约:** 连续漏付到一定程度(行业标准 **90 DPD**)被宣告违约。
- **回收:** 违约后通过催收、抵押处置、法律程序追回部分本金。
- **结清/核销:** 还清(PAID_OFF)或确认损失。

**2) 信用分与风险等级。** 借款人有一个 **FICO 风格信用分(300–850)**。Pacific Bridge 把信用分映射到 **A 到 E 五个风险等级(risk grade)**:A(Prime,最优)到 E(Deep Subprime,最次)。等级越低,违约风险越高,因此定价利率越高。

| 等级 | 名称 | 信用分区间 | 利率 | 定价假设违约率(implied) |
|------|------|------------|------|--------------------------|
| A | Prime | 720–850 | 5.5% | 3.0% |
| B | Near Prime | 680–719 | 7.5% | 6.0% |
| C | Standard | 640–679 | 9.5% | 6.0% |
| D | Subprime | 600–639 | 12.5% | 13.0% |
| E | Deep Subprime | 300–599 | 16.0% | 18.0% |

**3) 摊销(amortization)。** 月供(monthly payment)固定,但每期里"利息部分"和"本金部分"的比例随时间变化:早期利息多、本金少,后期反过来。**未偿余额(outstanding balance)**就是还剩多少本金没还。本数据集用标准摊销闭式公式计算每笔贷款截至 REFERENCE_DATE 的未偿余额。

**4) 违约相关概念。**

- **DPD(Days Past Due,逾期天数):** 超过应还日多少天没还。
- **违约(default):** 行业惯例在 **90 DPD** 宣告违约。
- **回收(recovery)与回收率(recovery rate):** 违约后追回的金额 / 违约时的未偿余额。
- **损失严重度(loss severity / LGD):** 1 − 回收率,即每 1 美元违约敞口最终亏掉多少。

**5) 定价是否对齐。** 把每个等级的**实际违约率(actual default rate)**和**定价假设违约率(implied default rate)**对比:实际 > 假设,说明定价不足(under-priced),收的利率不够覆盖风险,正在赔钱放贷。

**6) Vintage / 队列(cohort)分析。** 按"放款季度"把贷款分组,跟踪每组随时间的违约表现。近期放的贷款还没经历完整周期,违约看起来低是正常的——所以看**趋势**比看绝对值重要。

**7) 仓储融资(warehouse line)。** Pacific Bridge 不是用储户存款放贷,而是从大型金融机构借一条循环额度(仓储线)来放贷,这条额度要求维持最低现金准备金。所以 CFO 必须做现金流预测,确保有钱还仓储线、又有钱继续放新贷。

**8) 季节性与周期性行业。** 申请量有季节波动(如 Q4 旺、Q1 淡),影响人力规划;餐饮、酒店属于**周期性行业(cyclical)**,经济下行时最先承压,所以组合里这类敞口越大,系统性风险越高。

---

## 8. 术语表

每个在 ER 文档或 SQL 查询里出现的 jargon,这里给一句白话解释,外加"在本项目里为什么重要"。术语一律保留英文形式。

| 术语 | 白话解释 | 在本项目里为什么重要 |
|------|----------|----------------------|
| SMB (Small and Medium-sized Business) | 中小企业,本公司的客户群 | 整个业务围绕给 SMB 放贷展开 |
| FICO score | 一种 300–850 的个人信用分 | 决定客户被映射到哪个风险等级 |
| Risk grade (A–E) | 把信用分分档的风险等级 | 定价、违约率分析的核心维度 |
| Implied default rate | 定价模型**假设**的违约率 | Q1 用它和实际违约率对比 |
| Actual default rate | 数据里**实测**的违约率 = 违约数/贷款数 | Q1 的另一半;暴露定价缺口 |
| Pricing gap | implied − actual,负值=定价不足 | Q1 的结论指标;Grade C 约 −4pp |
| DPD (Days Past Due) | 逾期天数 | 90 DPD 是违约宣告口径 |
| Default | 借款人严重逾期被判定违约 | 损失的源头,多个查询的核心 |
| Charge-off | 会计上确认无法收回而核销 | 和违约相关的财务动作 |
| Recovery rate | 违约后追回比例 = 回收额/违约敞口 | Q10 按等级看回收强度 |
| Loss severity / LGD | 损失严重度 = 1 − recovery rate | CFO 算预期损失拨备用 |
| EAD (Exposure at Default) | 违约时点的敞口(未偿余额) | 预期损失公式的一项 |
| Outstanding balance | 还剩多少本金没还 | 组合敞口、集中度、现金流的基础 |
| Amortization | 等额本息摊销,月供拆本金+利息 | 决定还款计划和未偿余额怎么算 |
| Monthly payment / installment | 每月应还的一期 | 还款计划与实际还款比对的单位 |
| Disbursement | 放款,把钱打给客户 | 贷款生命周期的起点 |
| Maturity date | 预期最后还款日 | 判断贷款是否到期结清 |
| Term (months) | 贷款期限(12/24/36/48/60 月) | 影响月供和摊销节奏 |
| Origination | 放款发起(上账) | Vintage 分析按 origination 季度分组 |
| Vintage | 按放款时间分的队列 | Q13 看不同时期承保质量 |
| Cohort | 队列,按某共同特征分组 | 早期还款行为队列(Q8) |
| Warehouse line | 放贷用的仓储融资额度 | 决定资金成本与现金流约束 |
| Interest spread / NIM | 利差 / 净息差 | 公司的核心盈利来源 |
| Approval rate | 批准率 = 批准/申请 | 承保松紧的总体指标 |
| Conversion rate | 转化率(申请→放款) | 区域/营销效率(Q11) |
| False negative / Approval leakage | 把好客户错拒(假阴性) | Q3 的主题;漏掉的收入 |
| Early warning | 违约前的行为预警 | Q4 的主题;提前介入的依据 |
| Repeat customer | 复购客户(入职时打的层级标记) | Q5/Q20 区分新老客户表现 |
| LTV (Lifetime Value) | 客户生命周期价值 | Q20 做客户分层 |
| CAC (Customer Acquisition Cost) | 获客成本 | Q11 提供分母(申请量) |
| DTI (Debt-to-Income) | 负债收入比 | 常见拒绝原因之一 |
| DSCR (Debt Service Coverage Ratio) | 偿债覆盖率 | 真实承保会用,本集已简化 |
| Collateral | 抵押物 | 影响回收率 |
| EIN / tax_id | 联邦雇主识别号(企业税号) | 客户唯一标识 |
| ECOA / Reg B | 公平信贷机会法 | 承保不得歧视的合规底线 |
| FCRA | 公平信用报告法 | 规范信用报告使用 |
| CFPB / OCC / FDIC / DFPI / SBA | 北美各级金融监管者 | 行业合规背景 |
| KYC / BSA / AML | 反洗钱与客户尽职调查 | 放贷准入合规 |
| SLA (Service Level Agreement) | 服务时效承诺(如 7 个工作日决策) | Q18 衡量处理时长 |
| ACH | 美国自动清算转账 | 主要还款方式之一 |
| NTILE / decile | 等分排名(十分位) | Q20 客户分层用窗口函数 |

---

## 9. 关键指标与公式

下面是 SQL 查询里用到、或读者应当知道的指标。公式用通俗记法(SQL 风格伪代码),并注明输入和口径约定。

**违约与定价**

```
actual_default_rate(grade) = COUNT(defaulted_loans) / COUNT(loans)        -- 按等级
pricing_gap(grade)         = implied_default_rate − actual_default_rate    -- 负值=定价不足
```

**回收与损失**

```
recovery_rate  = SUM(recovery_amount)   / SUM(outstanding_at_default)
loss_severity  = SUM(loss_amount)       / SUM(outstanding_at_default)  = 1 − recovery_rate
expected_loss  = outstanding_balance × implied_default_rate            -- 单笔预期损失近似
```

**摊销(口径:标准等额本息)**

```
r = annual_interest_rate / 100 / 12
monthly_payment    = P × r × (1+r)^n / ((1+r)^n − 1)        -- P=本金, n=期数
outstanding_balance(k) = P × (1+r)^k − monthly_payment × ((1+r)^k − 1) / r   -- 已付 k 期后的剩余本金(闭式)
```

**审批与运营**

```
approval_rate     = COUNT(approved_applications) / COUNT(applications)
conversion_rate   = COUNT(approved_loans) / COUNT(applications)            -- 按区域(Q11)
days_to_decision  = decision_date − application_date
sla_compliance    = COUNT(days_to_decision ≤ 7) / COUNT(applications)      -- SLA=7 个工作日(Q18)
late_payment_rate = COUNT(payments WHERE days_late > 0) / COUNT(payments)  -- 逾期率(Q14)
```

**客户与组合**

```
repeat_default_lift = default_rate(first_time) / default_rate(repeat)      -- 约 2 倍(Q5)
concentration(industry) = SUM(outstanding_balance WHERE industry) / SUM(outstanding_balance)  -- 组合占比(Q2/Q19)
ltv_score = total_borrowed + estimated_lifetime_interest − (defaults × 50000)  -- 相对排名用(Q20)
estimated_lifetime_interest = SUM(approved_amount × interest_rate/100 × term_months/12)  -- 单利近似, 高估真实摊销利息约 2x, 仅用于相对排序
```

> **口径说明(避免下游 SQL 打架):**
> - 违约率统一按"违约贷款数 / 贷款数"计,不按金额加权。
> - `is_repeat_customer` 是**入职时设置的营销/忠诚度层级标记**,不是从贷款数派生的统计字段;它与"多笔贷款"正相关但不等同(详见 ER 文档 customer 表说明)。Q12 的"留存机会"用的是另一套**操作性定义**(近 12 个月有 PAID_OFF 且近 6 个月无申请),两者群体有重叠但不相同。
> - `expected_loss` 用 `implied_default_rate`(定价假设)而非实际违约率,因为它代表"按当初定价模型应计提的预期损失"。
> - `ltv_score` 里的 `estimated_lifetime_interest` 用单利近似,会高估真实摊销利息约 2 倍,仅用于客户**相对**排序,不可当真实利息核算。
