# 金融科技 消费信用卡全生命周期 业务背景

> 本文档是 `fintech_credit_card_lifecycle_high` 数据集的业务背景说明, 负责回答"这是一家什么公司, 做什么生意, 要解决什么问题". 数据结构见 `02-fintech_credit_card_lifecycle_high_er_document-cn.md`, SQL 查询见 `03-fintech_credit_card_lifecycle_high_sql_queries-cn.md`.
>
> 如果你读到某个分析 (比如"承保分校准", "transactor 盈利性", "vintage 恶化") 完全不知道它在讲什么, 有一份专门为外行写的长教程: `05-fintech_credit_card_lifecycle_high_analytics_primer-cn.md`. 它把这 8 个分析逐个讲透, 从"这是什么, 为什么重要, 公式怎么算", 一直讲到"在我们的数据里长什么样".
>
> 读者设定: 你是一个刚加入项目的聪明新人, 不需要是信用卡行业老手. 读完本文档, 你应该能在第一次站会上跟同事聊清楚这家公司的业务, 行业和这次分析要回答的问题.

---

## 1. 公司画像

**Keystone Card Company** 是一家总部位于加州尔湾 (Irvine, CA) 的中型**消费信用卡发行商 (credit card issuer)**. 它不是支付网络 (不是 Visa/Mastercard), 也不是给银行卖软件的科技供应商. 它就是那个**自己发卡, 自己决定批不批, 自己承担坏账**的公司. 你钱包里那张卡背后的公司, 就是它这种角色.

Keystone 的基因是"用数据做决策". 它相信每一张卡的 offer (给谁, 什么额度, 什么利率, 什么 rewards) 都应该由统计模型个性化决定, 而不是一刀切. 这套"数据驱动发卡"的打法, 正是过去三十年美国信用卡行业最成功的玩法.

公司画像 (数量级, 非精确值):

- **持卡账户:** 约 8,900 个在册账户, 客户是加州各地的普通消费者 (年收入从 2 万到十几万美元不等).
- **放贷规模:** 循环信贷余额 (outstanding balance) 数量级在数千万美元, 靠利息和刷卡手续费赚钱.
- **员工:** 约 300 人, 含承保 (underwriting), 风险 (risk), 营销 (marketing/acquisitions), 数据科学 (Card Intelligence), 催收 (collections), 财务和产品团队.
- **地域:** 当前业务集中在加州一个州, 申请人分布在 Los Angeles, San Diego, San Jose, San Francisco, Sacramento, Fresno, Irvine 等城市.

公司里和本次分析相关的角色 (SQL 查询会按头衔点名这些人):

| 头衔 | 中文 | 关心什么 |
|------|------|----------|
| CEO | 首席执行官 | 增长, 产品组合, 整体盈利 |
| CFO | 首席财务官 | 产品 P&L, 损失拨备, rewards 成本, 资金成本 |
| CRO (Chief Risk Officer) | 首席风险官 | 组合质量, vintage 损失曲线, 承保标准 |
| Chief Credit Officer | 首席信贷官 | 承保政策, 额度管理 (CLI) |
| CMO | 首席营销官 | 获客, campaign ROI, 渠道质量 |
| VP of Underwriting | 承保副总裁 | 批准率, 审批口径, 风险分层 |
| VP of Acquisitions | 获客副总裁 | 漏斗转化, 获客成本, bonus 活动 |
| VP of Portfolio Management | 组合管理副总裁 | 利用率, 敞口, 再定价 |
| Head of Card Intelligence | 数据科学负责人 | 承保/响应/流失模型的效果与校准 |
| Collections Manager | 催收经理 | 逾期桶, roll rate, 早期预警 |
| Product Manager | 产品经理 | 各卡产品的客群与盈利性 |
| Data Analyst / Data Scientist | 数据分析师/科学家 | 就是你, 用数据回答上面所有人的问题 |

---

## 2. 商业模式

Keystone 靠三条腿赚钱, 再减去三块成本.

**收入三条腿:**

1. **利息 (interest).** 客户如果不全额还款, 剩下的余额 (revolving balance) 要按 APR (年化利率) 计息. 这是发卡行最大的一块收入. APR 按风险从约 15% 到 30% 不等.
2. **Interchange (刷卡手续费).** 客户每刷一笔, 商户方要付一笔手续费给发卡行, 约刷卡额的 1.5% 到 2.1%. 客户刷得越多, Keystone 赚得越多, 而且这块不承担信用风险.
3. **费用 (fees).** 年费 (高端卡 95 到 395 美元), 滞纳金 (late fee), 取现费等.

**成本三块:**

1. **Rewards (返现/积分).** 为了吸引客户刷卡, 很多卡返 1% 到 2.5% 的 rewards. 这是直接的现金成本.
2. **Charge-off (核销损失).** 客户彻底还不上, 公司只能把这笔钱当损失核销. 这是最大的风险成本.
3. **获客成本 (acquisition cost) 和运营成本.** 营销触达, 开卡奖金 (signup bonus), 人力等.

所以 Keystone 的利润, 说到底取决于两件事的平衡: **风险定价准不准** (收的利息和 interchange 能不能覆盖坏账和 rewards), 以及**给对的客户配对的产品** (让爱刷卡还利息的人拿高利润产品, 别把高 rewards 卡送给只薅羊毛的人).

**一个反直觉的单位经济 (unit economics) 要点:** 一个每月全额还款, 从不付利息的客户 (行业叫 transactor), 对发卡行不一定是好客户. 他贡献 interchange (约 1.8%), 却要拿走 rewards (可能 2% 以上), 又不付利息. 在高 rewards 卡上, 这种客户是**亏钱**的. 真正的利润引擎是那些滚动余额, 老老实实付利息的 revolver. 这个反直觉的事实, 是本数据集好几个分析的核心 (Transactor 盈利性和产品阶梯 P&L, 见第 5 节业务问题, 对应 SQL 查询 Q12, Q19, Q11).

---

## 3. 行业普及: 美国消费信用卡发行

如果你来自别的行业, 这一节让你快速看懂发卡这门生意.

**这个行业创造什么价值.** 信用卡给消费者提供了两样东西: 支付的便利 (不用带现金) 和短期的信贷 (这个月先花, 下个月还, 甚至分期). 对商户, 它扩大了消费. 对发卡行, 它是一门"用规模化的小额利差和手续费, 去覆盖少数人违约损失"的生意. 美国是全球信用卡最发达的市场, 人均持卡数, 循环余额规模都很高.

**主要玩家类别 (不点名真实公司).**

- **大型综合发卡行:** 既是银行又发卡, 产品线全, 资金成本低.
- **数据驱动的专业发卡商:** 像 Keystone 这样, 以统计建模, 个性化 offer, 快速迭代见长, 在 near-prime 和 subprime 客群里特别能打.
- **联名卡发行商:** 和航空, 零售, 酒店合作发联名卡, 靠合作方的会员流量获客.
- **金融科技新贵:** 主打移动端体验, secured 卡帮人建立信用, 或先买后付 (BNPL) 等新形态.

**监管与合规框架 (北美).** 发卡行受多重监管:

- **CARD Act (2009):** 规范信用卡的定价, 加息, 费用披露, 保护消费者.
- **TILA (Truth in Lending Act) 与 Reg Z:** 要求清晰披露 APR, 费用等信贷条款.
- **ECOA (Equal Credit Opportunity Act) 与 Reg B:** 禁止基于种族, 性别等的信贷歧视. 承保模型必须能证明不产生歧视性结果.
- **FCRA (Fair Credit Reporting Act):** 规范如何拉取和使用征信报告 (FICO 分就来自这里).
- **CFPB (Consumer Financial Protection Bureau):** 联邦层面的消费者金融监管者, 盯定价公平和催收行为.
- **CECL (Current Expected Credit Loss):** 会计准则, 要求发卡行前瞻性地为预期损失计提拨备. 这让 vintage 损失曲线 (Vintage 恶化, 对应 SQL 查询 Q16) 直接关系到财报.
- (加拿大对照: FCAC 与各省消费者保护法规. 本数据集默认市场为美国加州.)

**当下的宏观力量.** 利率环境抬高了发卡行的资金成本; rewards 军备竞赛让 rewards 成本持续攀升; AI 和机器学习正在重塑承保和反欺诈; 监管对定价公平和模型可解释性 (explainability) 要求越来越高; 经济周期波动让"承保标准会不会在好日子里悄悄放松"成为风险官每季度都要盯的事. 这些都让"定价是否准确, 客群是否配对, 承保是否漂移"成为高管层反复追问的问题.

---

## 4. 项目框架: 你在做什么

你是 Keystone 的一名**数据分析师** (可能挂 Business Analyst, 也可能挂 Data Scientist 的头衔, 这两个岗位在 Keystone 共用同一套数据). 你被拉进一个**季度组合与获客评审 (quarterly portfolio and acquisition review)** 项目, 横向支持 CRO, CFO, CMO 和数据科学负责人几条线.

公司刚跑完一个季度, 管理层手上有一堆悬而未决的问题: 承保模型是不是在某些客群里已经失效? 获客成本看着不高的营销渠道是不是其实带来最差的客户? 高端 rewards 卡到底赚不赚钱? 0% 促销到期会不会引发一波逾期? 给高利用率客户提额是帮忙还是帮倒忙? 大额开卡奖金是不是养了一批羊毛党? 承保标准是不是在悄悄放松? 你的任务, 是用过去约 24 个月的完整信用卡生命周期数据, 把这些问题用 SQL 一个个回答清楚.

交付物: 给董事会和投资人的组合质量报告, 给 CMO 的渠道预算建议, 给产品和财务的产品 P&L, 给数据科学团队的模型校准发现, 以及给运营和催收的可执行清单. 所有分析都锚定固定参考日 **REFERENCE_DATE = 2026-06-30** (详见第 6 节).

这个项目特意设计成同时喂饱两类人. **Business Analyst** 用 SQL 沿获客到坏账的全漏斗回答业务问题 (定价, ROI, 集中度, P&L). **Data Scientist** 则能从数据里直接建模和验证: 承保分和真实核销结局摆在一起可以画 ROC 曲线, 算 AUC, 做混淆矩阵; 时间序列, vintage cohort, 二元标签一应俱全.

---

## 5. 本项目要解决的业务问题

整个数据集是为回答下面八个核心业务问题设计的. 每个问题都在 ER 文档里有对应的数据陷阱 (deliberately embedded trap), 并在 SQL 查询文档里有对应的查询. 为避免和 SQL 查询编号 (SQL 文档里的 Q1 到 Q20) 混淆, 这里的业务问题用**名字**而不是数字来标识, 并在括号里给出对应的 SQL 查询号. 全文其它地方凡出现"Qn"字样, 一律指 `03` 里的 SQL 查询编号.

1. **承保模型校准 (Underwriting Model Calibration):** 我们上线中的承保风险分 (underwriting_score) 真的能排序风险吗? 整体看行, 但在某个客群 (Subprime) 里是不是已经失效, 只是被整体数字盖住了? 这题给 Data Scientist 用 ROC/AUC/混淆矩阵回答. (对应 SQL 查询 Q3, Q4)
2. **渠道逆向选择 (Channel Adverse Selection):** 哪个营销渠道获客成本看着不高却带来最差的客户 (核销率最高)? 我们是不是在按错误的指标 (CPA) 分配营销预算? (对应 SQL 查询 Q6, Q7)
3. **Transactor 盈利性 (Transactor Profitability):** 每月全额还款的 transactor, 在高 rewards 卡上是不是其实亏钱? 哪些产品的哪类客户在给公司做贡献, 哪些在吸血? (对应 SQL 查询 Q12, Q19)
4. **Promo APR 悬崖 (Promo APR Cliff):** 靠 0% 促销拉来的账户, 促销一到期是不是会集体逾期? 这个风险能不能提前预测和干预? (对应 SQL 查询 Q13)
5. **提额逆向选择 (CLI Adverse Selection):** 我们给"高利用率客户"提额的策略, 是在奖励好客户, 还是在给风险最高的人加杠杆? (对应 SQL 查询 Q9)
6. **Bonus churner 负 LTV:** 大额开卡奖金养出的"奖金猎人", 是不是拿了钱就跑, 给公司留下负的 lifetime 价值? (对应 SQL 查询 Q15)
7. **Vintage 恶化 (Vintage Deterioration):** 我们的承保标准是不是在悄悄放松, 导致近期开出的账户比早期的坏得更快? (对应 SQL 查询 Q16, Q17)
8. **产品阶梯 P&L (Product Ladder Profitability):** 我们 6 款卡到底哪款真赚钱? 直觉 (高端卡最赚) 靠得住吗? (对应 SQL 查询 Q11, Q12, Q19)

除了这八个 marquee 问题, 数据集还支持一批运营类分析: 获客漏斗转化, 响应模型校验, 各等级批准率, 利用率分布, 逾期桶快照, interchange 品类拆解, champion/challenger 对比, 月度开卡趋势等, 用来回答日常运营和财务规划的问题.

---

## 6. 数据范围概览

- **时间跨度:** 约 24 个月的信用卡生命周期活动, 全部锚定到固定参考日 **REFERENCE_DATE = 2026-06-30**. 所有"当前快照, 账龄 (months_on_book), 距今多少月"的语义都按这个日期计算, 而不是系统当前时间, 保证多次运行和多次查询结果一致, 可复现.
- **数据量 (数量级, 白话):** 约 8,900 个账户, 约 8.9 万行月度账单, 约 3.1 万条抽样交易, 2 万封预筛信, 各 1.8 万的申请人与申请, 外加一批生命周期事件表, 合计约 19.4 万行.
- **刻意的范围取舍:**
  - **单一州 (加州):** 全部申请人都在加州, 避免跨州监管和地理噪声, 让分析聚焦在风险, 定价和客群上.
  - **单一产品类别:** 只有消费信用卡, 6 款产品构成一个从 secured 到 premium 的阶梯. 没有房贷, 车贷, 存款等其他银行产品.
  - **抽样交易:** `transaction` 表不是每一笔真实刷卡都落库 (那会是百万级), 而是抽样保留, 用于 MCC 和 interchange 结构分析. 账户级的完整经济画面在 `statement` (月度账单) 里.
  - **一人一申请:** 一个申请人恰好对应一份申请, 简化了"同一人多次申请"的复杂度.

(本节不列具体表; 表结构见 ER 文档.)

---

## 7. 行业知识科普

外行看懂这份数据前, 需要的大约半小时背景. 建议按"一张卡的一生"来理解.

**1) 信用卡生命周期的几个阶段.**

营销触达 (marketing) 先给潜在客户寄预筛信或投数字广告. 有人回应就提交申请 (application). 承保 (underwriting) 根据 FICO 等决定批准还是拒绝, 批准的话分配额度和 APR. 客户激活后开卡 (account). 之后每月产生账单 (statement): 刷了多少, 还了多少, 计了多少息. 一路上可能提额 (CLI), 赚 rewards. 如果连续逾期到约 180 天, 账户被核销 (charge-off). 客户也可能主动销卡 (attrition).

**2) FICO 分与风险等级.** 每个申请人有一个 **FICO 信用分 (300 到 850)**, 由征信局根据历史还款记录算出. Keystone 把 FICO 映射到 **A 到 E 五个风险等级**: A (Superprime, 最优) 到 E (Deep-Subprime, 最次). 等级越低违约风险越高, 因此定价 APR 越高. 这套映射见 ER 文档的 `credit_band` 表.

**3) APR, revolver 与 transactor.** APR (年化利率) 是不全额还款时余额要付的利息率. 每月全额还清的人叫 **transactor** (不付利息), 滚动余额的人叫 **revolver** (付利息). 这个区分是理解发卡行盈利的钥匙: revolver 贡献利息, transactor 只贡献 interchange.

**4) Interchange 与 rewards.** Interchange 是刷卡时商户方付给发卡行的手续费 (约 1.5% 到 2.1%). Rewards 是发卡行返给客户的现金或积分 (0 到 2.5%). 当 rewards 率逼近甚至超过 interchange 率, 单靠刷卡这门生意就开始亏, 必须靠利息或年费来补.

**5) 逾期, 核销与回收.** DPD (Days Past Due, 逾期天数) 衡量欠款拖了多久. 逾期会一级一级往深 roll (30 到 60 到 90 天...), 到约 180 天 (DPD180) 被 charge-off (会计上确认损失). 核销后通过催收还能追回一部分 (recovery). 净损失 = 核销余额 - 回收金额.

**6) Vintage (队列) 分析.** 按"开卡季度"把账户分组 (一个季度一个 vintage/cohort), 跟踪每组随账龄的表现. 近期开的卡还没走完违约周期, 绝对核销数低是正常的, 所以要比**相同账龄下**的核销率 (比如都看 month_on_book=6 时), 才能公平比较不同时期的承保质量.

**7) 提额 (CLI) 与利用率.** 利用率 (utilization) = 余额 / 额度, 衡量客户把额度用到多满. 提额 (Credit Line Increase) 能让好客户花更多, 但如果提给已经把额度用爆的人, 可能是在给风险加杠杆.

**8) 承保分, ROC 与混淆矩阵.** 承保时模型给每份申请打一个风险分 (underwriting_score). 要评估这个模型好不好, 数据科学家会把分数和真实结局 (有没有核销) 摆在一起: 画 ROC 曲线看区分度, 算 AUC (0.5 是瞎猜, 1.0 是完美), 或做混淆矩阵. 一个模型整体 AUC 好看, 不代表在每个子群都有效, 这正是承保模型校准问题的核心 (对应 SQL 查询 Q3, Q4).

---

## 8. 术语表

每个在 ER 文档或 SQL 查询里出现的 jargon, 这里给一句白话解释, 外加"在本项目里为什么重要". 术语一律保留英文形式. 想要更深, 更长的讲解, 去看 `05` 分析入门读本.

| 术语 | 白话解释 | 在本项目里为什么重要 |
|------|----------|----------------------|
| Credit card issuer | 发卡行, 自己发卡自己扛坏账的公司 | Keystone 就是这个角色 |
| FICO score | 300 到 850 的个人信用分 | 决定申请人被分到哪个风险等级 |
| Credit band (A to E) | 把 FICO 分档的风险等级 | 定价, 承保, 核销分析的核心维度 |
| Underwriting | 承保, 决定批不批, 给多少额度多少利率 | application 表的决策来源 |
| underwriting_score | 承保风险模型分 (0 到 999, 越高越安全) | Q3, Q4 校准分析和 ROC/AUC 的主角 |
| APR (Annual Percentage Rate) | 年化利率, 不全额还款时的计息率 | 利息收入的定价 |
| Revolver | 滚动余额, 付利息的客户 | 发卡行的利润引擎 |
| Transactor | 每月全额还款, 不付利息的客户 | 高 rewards 卡上可能亏钱 (Q12) |
| Interchange | 刷卡时商户方付给发卡行的手续费 | 三大收入之一, 按 MCC 拆解 (Q14) |
| Rewards | 返给客户的现金/积分/里程 | 主要成本之一, 会吃穿 interchange (Q19) |
| MCC (Merchant Category Code) | 商户类别码 | 决定 interchange 费率和消费结构 |
| Annual fee | 年费 | 高端卡靠它兜底 rewards 成本 |
| DPD (Days Past Due) | 逾期天数 | roll rate 和早期预警的基础 |
| Delinquency | 逾期状态 | 逾期桶 (dpd_bucket) 的统称 |
| Charge-off | 会计上确认无法收回而核销 | 最大的风险成本, 多个查询的核心结局标签 |
| Recovery | 核销后追回的金额 | 净损失 = 核销余额 - 回收 |
| EAD (Exposure at Default) | 违约时点的敞口 (核销余额) | 损失计算的一项 |
| Vintage / Cohort | 按开卡季度分的队列 | Q16 看承保质量随时间怎么变 |
| Months on book (MOB) | 账龄, 开卡至今多少个月 | vintage 曲线, 早期预警都按它 |
| Utilization | 利用率 = 余额 / 额度 | 高利用率既贡献利息又逼近风险 |
| CLI (Credit Line Increase) | 提额 | Q9 逆向选择的主题 |
| Prescreen | 预筛, 从征信局买名单寄预批信 | 营销漏斗的起点 (prescreen_offer 表) |
| Response model | 预测谁会回应邮件的模型 | Q2 用它做混淆矩阵 |
| Signup bonus | 开卡奖金 | 大额 bonus 会养出 churner (Q15) |
| Bonus churner | 拿了 bonus 就销卡的羊毛党 | 负 LTV 的源头 |
| Attrition | 流失, 销卡 | 分主动和被动 (attrition_event 表) |
| LTV (Lifetime Value) | 客户生命周期价值 | Q15 判断哪类客户在亏钱 |
| Champion / Challenger | 稳态主推 offer / 试验性新 offer | Q18 对比两者质量 |
| Promo APR / Balance transfer | 促销利率 / 余额代偿 | Q13 promo 悬崖的机制 |
| Approval rate | 批准率 = 批准数 / 申请数 | 承保松紧的总体指标 |
| Charge-off rate | 核销率 = 核销账户数 / 账户数 | 组合质量的核心指标 |
| ROC / AUC | 评估分类模型区分度的曲线与面积 | Q3, Q4 校准承保模型用 |
| Confusion matrix | 混淆矩阵, 预测 vs 真实的 2x2 表 | 评估承保/响应模型 |
| CECL | 前瞻性预期损失拨备准则 | 让 vintage 损失直通财报 |
| CFPB / CARD Act / Reg Z / ECOA | 美国信用卡相关监管 | 承保和定价的合规底线 |

---

## 9. 关键指标与公式

下面是 SQL 查询里用到, 或读者应当知道的指标. 公式用通俗记法 (SQL 风格伪代码), 并注明输入和口径约定. 更细的推导和举例见 `05` 分析入门读本.

**承保与风险**

```
approval_rate       = COUNT(decision='APPROVED') / COUNT(applications)          -- 按等级或时间
chargeoff_rate      = COUNT(account_status='CHARGED_OFF') / COUNT(accounts)      -- 组合质量核心
co_rate_by_mob6     = COUNT(CHARGED_OFF AND months_on_book<=6) / COUNT(accounts) -- vintage 曲线 (Q16)
net_loss            = charged_off_balance_usd - recovery_amount_usd             -- 单笔核销净损失
```

**单账户与产品 P&L**

```
account_margin      = SUM(interest_charged + interchange_revenue + fees_charged - rewards_earned)  -- 逐月账单求和
account_contribution= account_margin - signup_bonus_usd - net_loss             -- 完整单账户贡献 (Q12)
product_pnl         = SUM over accounts of account_contribution                 -- 按产品 (Q11)
net_interchange     = SUM(interchange_revenue) - SUM(rewards_earned)            -- rewards 侵蚀 (Q19)
```

> **口径说明 (避免下游 SQL 打架):**
> - `chargeoff_rate` 统一按"核销账户数 / 账户数"计, 不按金额加权.
> - 单账户 P&L 的"收入"含利息, interchange, 费用三项; "成本"含 rewards, 净核销损失, 开卡奖金三项. 计息 (`interest_charged_usd`) 对 transactor 在正常还款月为 0 (只有当一个 transactor 停止全额还款, 逾期走向核销时才开始计息), 这正是陷阱 3 (transactor 盈利性) 的根源.
> - vintage 比较必须固定账龄 (如 months_on_book <= 6), 否则近期批次因账龄短会显得"更好".
> - `underwriting_score` 越高代表模型认为越安全, 因此健康的模型应表现为"分数越高, 核销率越低".

**营销与获客**

```
response_rate       = COUNT(responded=1) / COUNT(prescreen_offer)               -- 按模型分层看 (Q2)
activation_rate     = COUNT(accounts) / COUNT(approved applications)            -- 漏斗 (Q1)
net_loss_per_booked = SUM(net_loss by channel) / COUNT(accounts by channel)     -- 渠道真实成本 (Q7)
avg_ltv             = AVG(account_margin - signup_bonus)                        -- 按销卡原因 (Q15)
```

**利用率与逾期**

```
utilization_pct     = statement_balance_usd / credit_limit_usd * 100           -- 当前用最新账单 (Q8)
dpd30plus_rate      = COUNT(days_past_due>=30) / COUNT(statements)              -- 按账龄看 promo 悬崖 (Q13)
```
