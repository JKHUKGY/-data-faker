# Vantage Media 的 CTV 广告投放分析业务背景

这份文档是整个数据集的入口。它要回答的不是"表里有什么字段",而是"这家公司是谁,靠什么赚钱,为什么要做这套数据,以及一个外行需要先懂哪些行话才能看懂后面的 ER 文档和 SQL 查询"。如果你是刚加入项目的实习生,先把这份读完,再去翻 `02-advertising_ctv_campaign_analytics_high_er_document-cn.md` (数据模型) 和 `03-advertising_ctv_campaign_analytics_high_sql_queries-cn.md` (查询练习)。

这家公司是虚构的。市场设定在北美,货币是 USD,城市是北美城市,监管机构是美国和加拿大的机构。叙述用中文,但业务本身是一家北美公司,所有行业术语保留英文原词,术语表会逐条解释。

---

## 1. 公司画像

**Vantage Media** 是一家虚构的 AdTech (广告技术) SaaS 公司,总部在纽约,在洛杉矶设有第二办公室 (靠近好莱坞的媒体与娱乐生态)。公司 2019 年成立,专注做一件具体的事:帮品牌把广告投到 **Connected TV (CTV,联网电视)** 上,并且把这个过程自动化。

它的客户几乎全是 **DTC (Direct-to-Consumer,直接面向消费者) 品牌**。这些品牌做补充剂、金融科技 App、流媒体订阅、汽车保险、电商家居之类的生意,过去主要在 Facebook 和 Google 上买数字广告。当它们想把预算扩展到电视屏幕 (Hulu、Peacock、线性有线电视) 时,会发现传统电视广告采购 (TV media buying) 是一门需要资源和人脉的老派生意,自己玩不转。Vantage Media 就是来填这个空缺的:用软件 + 数据科学,让一个不懂电视采购的 DTC 营销经理也能像买数字广告一样买电视广告位。

公司规模大致是这个量级 (都按数量级理解,不必当成精确财报):

| 维度 | 量级 |
|------|------|
| 员工 | 约 80 人 (Trading Desk、AutoML 平台、Customer Success、Data Engineering、RevOps 五个团队) |
| 活跃客户 (advertiser) | 约 120 个 DTC 品牌 |
| 客户平均年媒体预算 | 约 1.3M USD,横跨三档 (SMB / Mid-Market / Enterprise) |
| 业务覆盖网络 | 15 个电视与流媒体网络 (有线、广播、流媒体三类) |

公司内部按职能分成五个团队。Trading Desk 负责实际下单和应对突发调整,AutoML Platform 是数据科学家和 ML 工程师,负责核心产品 Booking Copilot 的模型,Customer Success 管续约和业务回顾,Data Engineering 维护上游数据管道,RevOps & BI 做跨团队的归因、预测和管道分析。后面 SQL 查询里出现的角色名 (Trading Desk Lead、Data Science Lead、CDO、CFO、Media Buyer) 都来自这个组织结构。

---

## 2. 商业模式

Vantage Media 的收入由三块拼起来,理解这三块就能看懂后面所有跟钱有关的指标。

第一块是 **媒体费 take-rate**。客户通过平台买电视广告位时,平台从媒体采购金额里抽 10% 到 15% 的佣金。这是收入的大头。所以"客户花了多少媒体费"(gross media buy) 直接决定平台收入,后面 Q11、Q12、Q15 这些算媒体购买金额的查询,本质都是在算平台收入的基数。注意一个口径区别:媒体购买金额是客户的总支出,不是平台净收入,平台净收入要再乘 take-rate。

第二块是 **Platform fee (平台订阅费)**。客户按年付一笔软件使用费,类似 SaaS 订阅。这部分相对稳定。

第三块是 **AutoML 模块附加费**。这是 Vantage Media 的差异化所在。基础平台只是帮你下单,但如果客户想要 Booking Copilot 的智能预测能力 (预测某个广告位会不会被抢占、预期回报多少),需要额外付费,Mid-Market 和 Enterprise 客户尤其愿意为定制化模型买单。

客户按年度媒体预算分三档,这个分层直接影响销售模式和服务等级:

| 层级 | 年预算区间 (USD) | 销售模式 | AutoML 服务等级 |
|------|------------------|----------|-----------------|
| SMB | 200K 到 500K | 自助平台 + Email 支持 | 共享多租户模型,周更 |
| Mid-Market | 500K 到 1.5M | AE 主导,每月业务回顾 | 半定制模型,日更 + Shadow scoring |
| Enterprise | 1.5M 到 5M+ | Account Director,POC 6 到 9 个月 | 独占模型 + 客户自有转化数据训练 + 实时再评分 |

理解单位经济 (unit economics) 的关键在于:平台的利润最终取决于客户愿不愿意持续把预算放在 CTV 上,而这又取决于客户能不能在 CTV 上赚到钱 (即 ROAS 够不够高)。所以 Vantage Media 的产品和客户利益是对齐的:平台越能帮客户避开会被抢占的广告位、挑出高回报的网络,客户的 ROAS 越高,就越愿意加预算,平台的 take-rate 收入也就越多。

---

## 3. 行业概览 CTV 与广告技术

如果你来自别的行业,这一节帮你建立对 CTV 广告这门生意的整体认知。

电视广告正在经历一次大迁移。过去看电视意味着固定时间坐在电视机前看 **linear TV (线性电视,即按节目表播出的传统电视)**,广告也是按时段插播。现在越来越多人通过流媒体 App (在电视机上装的 Hulu、Peacock、Pluto TV 这类应用) 看节目,这种通过互联网在电视屏幕上看内容的方式就叫 **CTV (Connected TV)**。CTV 广告结合了电视的大屏沉浸感和数字广告的可定向、可衡量,因此成了广告预算流向的新洼地。

这个市场的玩家大致分几类。**品牌方 (advertiser)** 是出钱买广告的一端,本数据集里是 DTC 品牌。**网络方 (network)** 是卖广告位的一端,包括线性有线频道 (cable,如 ESPN、HGTV、TBS)、线性广播网 (broadcast,如 NBC、CBS、ABC、FOX) 和流媒体平台 (streaming AVOD,如 Hulu、Peacock、Pluto TV)。中间还有像 Vantage Media 这样的 **采购与技术平台 (media buying / AdTech platform)**,以及专门做转化衡量的 **归因合作伙伴 (attribution partner)**。

电视广告和数字广告有一个根本差别:**电视广告没有点击**。在网页上你点了广告就有一条点击记录,能直接追踪到购买。但电视广告是看的,没有点击链路,所以"这次投放到底带来了多少转化"是个老大难问题。行业用 **attribution (归因)** 来近似解决,常见方法有 pixel match (像素匹配)、IP match (IP 匹配) 和 panel extrapolation (面板外推),不同方法的精度差异很大,这正是本数据集 Q8 要分析的问题之一。

监管方面,北美 CTV 广告受几条线约束。**FTC (Federal Trade Commission,美国联邦贸易委员会)** 管广告的真实性和反欺诈。**FCC (Federal Communications Commission)** 管广播电视的内容与传输。隐私层面,**CCPA / CPRA (加州消费者隐私法案及其修正案)** 和 **VPPA (Video Privacy Protection Act,视频隐私保护法)** 限制了观看数据和定向数据的使用,这也是为什么 CTV 归因更依赖 pixel 和 panel 这类间接方法。行业自律组织 **IAB (Interactive Advertising Bureau)** 和 **MRC (Media Rating Council)** 制定衡量标准,**Nielsen** 是老牌收视率与受众衡量机构,本数据集里 Nielsen Digital 就是一个归因 partner。

宏观上有三股力量在塑造这个行业。一是预算从线性电视持续流向 CTV,流媒体广告库存快速增长。二是衡量与归因的标准化和隐私合规收紧同时进行,衡量越来越难也越来越重要。三是 AI 和 AutoML 进入媒体采购决策,从"靠人脉和经验下单"转向"靠模型预测下单"。Vantage Media 押的就是第三股力量。

---

## 4. 项目背景与你的角色

你是 Vantage Media 的 **数据分析师 (BI / RevOps 方向)**,直接向 RevOps 负责人汇报,日常也会被 Trading Desk、Data Science、Data Engineering 几个团队拉去做专项分析。你手上的活儿不是写一份一次性的报告,而是要把这套 CTV 投放数据盘活成一组可复用的分析查询,支撑公司从战略到运营三个层级的决策。

你的产出会送到不同的人手里。给 CEO、CFO、CDO 的是月度和季度的战略概览 (媒体购买金额趋势、AutoML 投资回报、各网络类型的回报对比)。给 Trading Desk Lead、Data Science Lead、Data Engineering Lead 的是日更的运营看板 (网络清除率监控、高风险位预警、模型准确率监控、数据质量驾驶舱)。给分析师同事和数据科学家的是按需的探索查询 (归因方法对比、预订提前期相关性、活动 ROI 完整链路)。

`03-advertising_ctv_campaign_analytics_high_sql_queries-cn.md` 里的 20 个查询就是这套分析的具体落地。每个查询都标了它服务的角色和对应的业务问题,你可以把它当成一份"经理交给你这周做的任务清单"来逐条练习。

公司内部除了你这样的分析角色,还有几类人会反复出现在数据里,理解他们有助于读懂审计类表 (booking_history、user_action):

| 角色 | 在干什么 | 主要碰哪些表 |
|------|----------|--------------|
| Media Buyer | 下单 placement,应对抢占后的调整 | ad_placement、booking_history、user_action |
| Trading Desk Lead | 监控当日抢占率,调整未来一周策略 | ad_placement、network_clearance_history |
| Data Scientist | 训练和评估 AutoML 模型,做特征工程 | prediction_result、model_version、performance_actual |
| Data Engineer | 维护数据管道,响应数据质量告警 | ingestion_metadata、data_quality_log、alert_notification |

客户那一端也有一条决策链 (B2B 销售里常说的 5 个 persona):Champion 是客户公司里推动 CTV 试投的增长营销经理,Economic Buyer 是掌握预算的 VP Marketing,Decision Maker 是做渠道战略的 CMO,Influencer 是评估模型效果的数据科学家或分析师,Blocker 是把关合同和合规的采购或法务。这条链解释了为什么 Enterprise 客户的 POC 要做 6 到 9 个月。

---

## 5. 要解决的业务问题

整套数据集是围绕四个具体的业务问题搭起来的。每一个都对应 ER 文档里某种刻意埋下的数据分布,以及 SQL 文档里若干道查询。

**问题一,媒体采购盲区。** 买手在向客户报价前,手里没有前瞻数据,不知道哪些广告位会被抢占 (preemption),也无法量化预期 ROAS。被抢占意味着客户预订的广告位最后没播出,这是纯粹的机会损失。粗算下来每月约 7000 个被抢占的 placement,累计 30M 到 50M USD 的未交付机会成本。这是 Booking Copilot 这个产品要解决的核心痛点,对应 Q1、Q3、Q7、Q12。

**问题二,客户差异太大,通用模型失效。** 同一个网络,对不同行业的客户回报完全不同。Health 品牌在 ESPN 上的 ROAS 大约 0.7x,在 HGTV 上能到 1.5x,但 Auto 品牌正好相反 (体育内容对汽车广告反而有效)。一个全局模型会把这些差异平均掉,给出谁都不满意的预测。这正是 Vantage Media 要为客户做定制 AutoML 模型的根本动机,对应 Q4、Q6、Q8、Q20。

**问题三,归因难题。** 电视广告没有点击,转化要靠 4 个第三方归因 partner (AttributionPro、Nielsen Digital、ImpactTracker、ConversionPixel) 用不同方法 (pixel、IP、panel) 来估算,精度差异很大。如果不先按归因方法做归一化,跨 partner 比较 ROAS 会得出错误结论。对应 Q8。

**问题四,数据质量黑洞。** 数据来自 10 多个上游源 (电视网络日志、流媒体日志、归因 partner API),延迟、重复、缺失频发,直接污染 ML 训练特征的质量。公司用一套数据质量规则 (data quality rule) 和告警机制来守护,对应 Q5、Q10、Q13、Q17。

除了这四个业务问题,数据集还专门支撑一条产品线的故事:**Booking Copilot 的 AutoML 模型监控**。这是公司给 CDO 和客户演示"我们的模型在持续变好"的能力,对应 Q2、Q14、Q18,以及下面知识科普里详细讲的 shadow scoring。值得一提的是,这条线里埋了一个反直觉的结论 (见 Q2 / Q14):clearance 二分类的准确率三代模型几乎持平,因为类别极度不均衡;真正在变好的是 ROAS 回归的误差。这告诉数据科学团队该把力气转去解决类别不均衡,而不是继续调参。

---

## 6. 数据范围概览

数据快照锚定在 **AS_OF_DATE = 2025-10-31**。所有涉及"最近 N 天""过去几周"的 SQL 查询都用 `'2025-10-31'` 这个固定日期字符串作为参考点,而不是 `DATE('now')`,这样在历史数据上跑查询结果才稳定可复现。

活跃业务数据覆盖 **2025-05-01 到 2025-10-31,共 6 个月**。在这之外还有一段 2024-11 到 2025-04 的 ML 训练特征回看窗 (通过 network_clearance_history 表),它故意早于活跃数据窗口,这是机器学习里避免时间泄漏的标准做法 (用历史窗口算特征,在另一个窗口做预测和评估)。

数据量用大白话说大概是:120 个广告主,400 个广告活动,5 万条广告位预订 (核心事实表),4.2 万条实际效果记录 (只有播出了的广告位才有),5 万条 ML 预测记录 (每条广告位都有),外加各类审计、运维、配置表,总计约 16.4 万行,落在 High 复杂度档。

有几个刻意的范围决定值得提前说明。一是只覆盖 6 个月而不是整年,因为这段正好横跨 Q3 平峰和 Q4 旺季 (含 NFL 赛季),足够展示季节性而不冗余。二是市场限定北美 (USD、北美网络、北美监管),不掺杂其他地区。三是模型版本只保留 3 代 (v2.1.5、v2.2.0、v2.3.1),足够讲清楚迭代故事。

具体每张表的字段、约束、样例数据,以及埋下的数据分布陷阱,都在 ER 文档里,这里不展开。

---

## 7. 行业知识科普

这一节是外行看懂数据前需要的半小时背景。按"一次投放从预订到结算"的顺序讲。

**第一步,广告位是怎么定价和预订的。** 电视广告按 **CPM (Cost Per Mille,每千次曝光成本)** 计价,即每给一千个人看到广告收多少钱。一个广告位的总价 = CPM × 曝光数 / 1000。买手在播出前若干天下单,这个提前的天数叫 **booking lead time (预订提前期)**。同一个时段里广告分多条插播,广告在插播段里的位置叫 **break position**。播出的时间段按 **daypart (时段)** 划分,典型的有 early morning、daytime、early fringe、primetime (黄金时段,最贵)、late night。Primetime 的 CPM 通常比 daytime 高 30% 以上。

**第二步,广告位会不会真的播出。** 这是 CTV 采购最关键也最反直觉的一点。你预订了不代表一定播,电视台可能临时把你的广告位让给更值钱的内容 (尤其是直播体育),这叫 **preemption (抢占)**。成功播出叫 **clearance (清除)**。一个网络成功播出的比例叫 **clearance rate (清除率)**,被抢占的比例叫 **preemption rate (抢占率)**。直播节目占比高的网络 (体育向的 ESPN) 清除率低且波动大,生活方式向的 HGTV 和流媒体平台清除率高且稳定。最典型的季节性冲击是 **NFL season (橄榄球赛季,9 月到 10 月底)**,这期间 ESPN、ESPN2、FOX 的清除率会掉 15 到 20 个百分点,因为大量广告位被让给了赛事直播。

清除率还和预订提前期相关:订得越早,时段内容越不确定,越容易被抢占;订得越晚 (7 天内),时段已经定了,清除率反而更高。这是 Q9 要验证的假设。

**第三步,播出后怎么算回报。** 广告播出后,要衡量它带来了多少转化和收入。核心指标是 **ROAS (Return On Ad Spend,广告支出回报率)** = 归因收入 / 花费。ROAS 1.5x 意思是每花 1 美元带回 1.5 美元收入。由于电视没有点击,转化数要靠归因 partner 估算,不同 **attribution method (归因方法)** 精度不同:pixel match 用像素回传,最精确,会略微高估;IP match 用 IP 地址关联,居中;panel extrapolation 用样本面板外推到总体,系统性偏低。归因还有延迟,partner 拿到完整数据需要时间,叫 **attribution window (归因窗口)** 加上 partner 自身的处理延迟。

**第四步,AutoML 怎么介入决策。** Vantage Media 的产品 **Booking Copilot** 在买手报价前,对每个候选广告位用模型预测两个数,叠加到买手界面上:一个是 clearance probability (这条位会不会被抢占,二分类任务),一个是预期 ROAS (回归任务)。预测出来的最重要特征 (top features) 也会展示给买手,类似简化版的 SHAP 解释。

这里有一个产品差异化的关键设计,叫 **shadow scoring (影子评分)**。Vantage Media 不是只有一个固定模型,而是让 3 代模型版本同时在线,对同一批广告位都打分。主用版本负责线上决策,其他版本在后台做回溯评估 (backtesting)。这样比较版本好坏时,大家看的是同一批数据,避免"老版本只评估了简单数据、新版本只评估了难数据"的混淆。模型质量用两个指标衡量:分类任务看 **AUC-ROC** (排序质量) 和准确率,回归任务看 **MAPE (平均绝对百分比误差)**。

一个贯穿全数据集的重要教训藏在这里:clearance 这个二分类任务因为类别极度不均衡 (约 85% 的广告位都会清除),一个"永远预测会清除"的傻瓜基线就能拿到约 85% 的准确率,所以三代模型的准确率几乎卡在同一条线上,光靠调参的噪声收窄突破不了。真正在单调变好的是 ROAS 回归的 MAPE (从 12% 降到 8% 再到 5%)。这说明该转向算法层 (类别加权、focal loss、重采样) 去解决不均衡,而不是继续在 clearance 模型上调超参。Q2 和 Q14 就是讲这个故事的。

**第五步,数据怎么保证可信。** 上面这一切都建立在数据质量上。公司用一组 **data quality rule (数据质量规则)** 每天自动检查上游数据,规则按严重程度分 P0 (阻塞下游的严重问题)、P1、P2 三级,检查结果落到 data quality log,触发告警时通过 Slack 或 Email 发给值班工程师。衡量响应速度的指标是 **MTTR (Mean Time To Resolve,平均解决时长)**。上游数据源还有交付 **SLA (Service Level Agreement,服务等级协议)**,约定每天几点前交付、容忍多少延迟,SLA 达标率是供应商管理的关键。

---

## 8. 术语表

下面把全数据集会用到的行话逐条解释,术语保留英文,后面 ER 文档和 SQL 查询里出现这些词时可以回来查。

| 术语 | 中文通俗解释 | 为什么在这里重要 |
|------|--------------|------------------|
| CTV (Connected TV) | 通过互联网在电视屏幕上看内容 (流媒体 App) | 整个公司的业务载体 |
| Linear TV | 按节目表播出的传统电视 | 与 CTV 对照的旧形态,本数据集 cable 和 broadcast 都属线性 |
| AVOD (Ad-supported Video On Demand) | 靠广告免费看的点播流媒体 | Hulu、Peacock、Pluto TV 的商业模式,清除率高 |
| DTC (Direct-to-Consumer) | 不经渠道直接卖给消费者的品牌 | Vantage Media 的客户全是这类 |
| AdTech | 广告技术,用软件和数据驱动广告投放 | 公司所属行业 |
| Media Buying | 媒体采购,即买广告位 | 平台帮客户做的核心动作 |
| Trading Desk | 负责下单和实时调整的采购团队 | 内部团队,对应 Media Buyer 角色 |
| advertiser | 广告主,出钱投广告的品牌客户 | 一张维度表,本数据集 120 个 |
| network | 卖广告位的电视台或流媒体平台 | 维度表,15 个,分三类 |
| network_type | 网络类型,分 linear_cable / linear_broadcast / streaming_avod | 决定清除率和 ROAS 的关键维度 |
| campaign | 广告活动,一个客户的一轮投放,含预算和周期 | placement 挂在 campaign 下 |
| placement | 一个具体的广告播出位置 (某网络某时段某天的一条广告) | 核心事实表,5 万条 |
| CPM (Cost Per Mille) | 每千次曝光的成本 | 电视广告的计价单位 |
| impressions | 曝光数,广告被看到的次数 | CPM 计价的分母 |
| booked CPM / booked impressions | 预订时约定的 CPM 和曝光数 | 算媒体购买金额的输入 |
| gross media buy | 媒体购买金额,客户总支出 | 平台 take-rate 的计算基数,不是平台净收入 |
| take-rate | 平台从媒体费里抽成的比例 (10% 到 15%) | 平台主要收入来源 |
| clearance | 广告位成功播出 | 二分类任务的正类 |
| preemption | 广告位被临时抢占,没播出 | 机会成本的来源,产品要预测的核心 |
| clearance rate | 清除率,成功播出占已结案的比例 | 衡量网络可靠性的核心指标 |
| daypart | 播出时段 (primetime、daytime 等) | 影响 CPM 和受众 |
| primetime | 黄金时段 (晚 8 到 11 点),最贵 | CPM 加成 30% |
| break position | 广告在插播段里的位置 | placement 的一个特征 |
| booking lead time | 预订提前期,下单到播出的天数 | 与清除率相关 (Q9) |
| NFL season | 橄榄球赛季 (9 月到 10 月底) | 体育网络清除率骤降的季节性冲击 |
| ROAS (Return On Ad Spend) | 广告支出回报率 = 收入 / 花费 | 衡量投放效果的核心指标 |
| AOV (Average Order Value) | 平均客单价 | 由收入反推转化数 |
| CPA (Cost Per Acquisition) | 单转化成本 = 花费 / 转化数 | 效果衡量的另一面 |
| conversion | 转化,广告带来的实际购买或注册 | ROAS 的分子来源 |
| attribution | 归因,把转化归到具体广告上 | 电视无点击,只能估算 |
| pixel match | 用像素回传做归因,最精确 | 略微高估 ROAS (Q8) |
| IP match | 用 IP 地址关联做归因,中等精度 | ROAS 居中 (Q8) |
| panel extrapolation | 用样本面板外推到总体 | 系统性低估 ROAS (Q8) |
| attribution window | 归因窗口,等转化数据完整的天数 | 影响归因延迟 |
| attribution partner | 提供归因数据的第三方 | 本数据集 4 个 |
| AutoML | 自动化机器学习,自动做特征、选模型、调参 | 产品差异化的工程杠杆 |
| Booking Copilot | Vantage Media 的核心 ML 产品 | 在买手下单前给出预测 |
| clearance classifier | 预测清除概率的二分类模型 | model_version 里的一类 |
| ROAS regressor | 预测 ROAS 的回归模型 | model_version 里的另一类 |
| shadow scoring | 多版本同时在线对同一批数据打分 | 让版本对比基于同分布数据 |
| backtesting | 用历史数据回溯评估模型 | shadow scoring 的评估方式 |
| AUC-ROC | 二分类排序质量指标 (0.5 到 1) | 分类模型的衡量 |
| MAPE (Mean Absolute Percentage Error) | 平均绝对百分比误差 | 回归模型 (ROAS) 的衡量 |
| confidence level | 预测置信度 (low / medium / high) | 给买手的辅助信号 |
| top features | 一次预测里最重要的几个特征 | 简化版 SHAP,展示给买手 |
| class imbalance | 类别不均衡,正负样本比例悬殊 | clearance 准确率瓶颈的根源 |
| recall / precision | 召回率 / 精确率 | 不均衡场景下比准确率更有意义 |
| SLA (Service Level Agreement) | 服务等级协议,约定交付时效 | 上游数据源管理 |
| MTTR (Mean Time To Resolve) | 平均解决时长 | 数据质量响应速度 |
| data quality rule | 数据质量检查规则 | 守护 ML 训练数据 |
| P0 / P1 / P2 | 数据质量问题的严重程度分级 | P0 最严重,阻塞下游 |
| ingestion | 数据采集入库 | 上游数据进入平台的环节 |
| z-score anomaly | 用标准分检测异常值 | 一类数据质量规则 |

---

## 9. 关键指标与公式

下面列出后面 SQL 查询会用到的核心指标定义。当两种定义都常见时,这里固定一种口径,避免不同查询给出互相矛盾的数。公式用 SQL 风味的伪代码表示。

**媒体采购类指标。**

```
Clearance Rate    = SUM(status = 'cleared') / COUNT(status IN ('cleared','preempted'))
Preemption Rate   = SUM(status = 'preempted') / COUNT(status IN ('cleared','preempted'))
Gross Media Buy   = SUM(booked_cpm * booked_impressions / 1000)
Average Lead Time = AVG(booking_lead_days)
Preemption Opportunity Cost
                  = SUM(booked_cpm * booked_impressions / 1000) WHERE status = 'preempted'
```

清除率和抢占率统一只在已结案的广告位 (cleared 或 preempted) 上计算,排除尚未确认结果的 pending 状态。这条口径约定贯穿 Q1、Q7、Q9、Q14、Q16、Q18,务必一致,否则各查询的清除率对不上。

**效果归因类指标。**

```
ROAS (placement 级)     = attributed_revenue_usd / spend_usd
ROAS (spend-weighted)   = SUM(attributed_revenue_usd) / SUM(spend_usd)
CPA                     = SUM(spend_usd) / SUM(attributed_conversions)
Attribution Lag (小时)  = AVG(finalized_at - scheduled_air_time)
```

ROAS 有两种算法。按行取平均 (AVG(roas)) 对小订单敏感,容易被少数极端值带偏;按花费加权 (SUM(revenue)/SUM(spend)) 才是 CFO 关心的真实整体回报。涉及战略决策的查询 (Q6、Q20) 优先用 spend-weighted 口径,并会把两种都列出来对照。

**AutoML 模型监控类指标。**

```
Clearance Accuracy       = AVG((pred >= 0.5 AND status='cleared') OR (pred < 0.5 AND status='preempted'))
Recall on preempted      = TN / (TN + FP)   即在所有真实 preempted 里被正确预测为低清除的比例
ROAS MAPE                = AVG(ABS(predicted_roas - roas) / roas) * 100
```

在类别不均衡的场景里,整体准确率会被多数类锁死,意义有限。真正衡量"模型能不能抓住会被抢占的高风险位"的是 Recall on preempted。这是 Q2、Q14 反复强调的点。ROAS MAPE 越低越好,本数据集三代 regressor 的 MAPE 单调下降 (约 12% 到 8% 到 5%)。

**数据质量与运维类指标。**

```
DQ Pass Rate         = SUM(status = 'passed') / COUNT(*)
MTTR (小时)          = AVG(resolved_at - run_timestamp)
SLA Compliance Rate  = 实际到达不晚于 (expected_delivery_hour + sla_threshold_hours) 的比例
DQ Resolution Rate   = SUM(resolved_at IS NOT NULL) / SUM(alert_fired = 1)
```

这些指标支撑 Q5、Q10、Q17。SLA 达标率的计算要用绝对时间差 (julianday 算小时),正确处理跨日延迟,具体写法见 SQL 文档 Q10。
