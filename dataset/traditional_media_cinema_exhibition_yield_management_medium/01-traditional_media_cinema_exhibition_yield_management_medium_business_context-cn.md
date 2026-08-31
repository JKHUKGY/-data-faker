# 传统媒体 — 院线场次与卖品盈利分析 业务背景

> 本文档是 `traditional_media_cinema_exhibition_yield_management_medium` 数据集的业务背景说明,负责回答"这是一家什么公司、做什么生意、要解决什么问题"。数据结构请见 `02-traditional_media_cinema_exhibition_yield_management_medium_er_document-cn.md`,SQL 查询请见 `03-traditional_media_cinema_exhibition_yield_management_medium_sql_queries-cn.md`。
>
> 读者设定:你是一个刚加入项目的聪明新人,不需要是电影行业老手。读完本文档,你应该能在第一次站会上跟同事聊清楚这家公司的业务、行业和这次分析要回答的问题。

---

## 1. 公司画像

**Lakeshore Cinemas** 是一家总部位于伊利诺伊州芝加哥的区域性院线连锁(cinema exhibition chain)。公司 2006 年由几家独立单银幕影院合并而来,此后逐步在中西部扩张,目前运营 **18 家影院、92 块银幕**,分布在伊利诺伊、威斯康星、印第安纳、俄亥俄、密歇根五个州,既覆盖芝加哥都会区这样的一线市场,也覆盖皮奥里亚(Peoria)、韦恩堡(Fort Wayne)、绿湾(Green Bay)这类二线市场。

公司画像(数量级,非精确值):

- **规模:** 约 450 名员工,以放映员、卖品柜台、票务等小时工为主,全职管理岗约 60 人。
- **营收:** 年营收数量级约 9500 万美元,其中绝大部分来自票务(box office),卖品(concession)营收的绝对额要小得多;但卖品几乎不与发行商分账、**毛利率**高达 60% 以上,对**利润**的贡献远超其营收占比,因此"卖品账面毛利是否真实"(Q1)才是管理层格外在意的问题。
- **会员体系:** 忠诚度计划 **Lakeshore Rewards** 面向所有观众免费开放,通过观影和消费积分,积分可兑换爆米花、饮料等卖品;本数据集覆盖 2026 年第二季度内活跃的约 7500 名会员。
- **市场分层:** 内部把 18 家影院分为 **Primary(一线市场,12 家)** 和 **Secondary(二线市场,6 家)** 两档,用于排片策略、卖品备货和资本开支决策。

公司里和本次分析相关的角色(SQL 查询会按头衔点名这些人):

| 头衔 | 中文 | 关心什么 |
|------|------|----------|
| CFO | 首席财务官 | 卖品真实现金毛利、季度董事会材料 |
| VP of Concessions & Merchandising | 卖品与商品副总裁 | 卖品定价、备货、会员兑换成本 |
| VP of Film Programming | 排片副总裁 | 与发行商的排片合约、场次安排 |
| Director of Loyalty & Marketing | 会员与营销总监 | Lakeshore Rewards 的兑换行为与获客效果 |
| Regional Operations Manager | 区域运营经理 | 一线/二线市场影院的日常运营 |
| Facilities & Engineering Manager | 设施工程经理 | 银幕设备的能耗与维保开支 |
| Concession Operations Supervisor | 卖品运营主管 | 各场次时段的卖品备货、人手排班 |

---

## 2. 商业模式

Lakeshore Cinemas 的收入来自两条线,盈利逻辑完全不同:

1. **票务收入(box office):** 观众为一场电影买票入场,票价按银幕类型(Standard、Premium 大画幅躺椅厅、IMAX)和场次时段(matinee 日场、prime 黄金档、late_night 深夜场)、以及是否周末浮动。票务是"高收入、低毛利"的生意——收入里有相当一部分要以片租(film rental)形式付给发行商,本数据集不刻画这部分分账细节,只关注影院自己留存的票房和场次运营本身。
2. **卖品收入(concession):** 爆米花、饮料、糖果等零售商品,营收的绝对额比票务小得多,但毛利率通常在 **60% 以上**,而且几乎不用和发行商分账——每一块钱卖品收入落到利润上的比例远高于票务,所以卖品是院线**利润结构**里被高度看重的一环(哪怕它并不是营收的大头)。行业里有句老话:"we sell popcorn, and the movie is the excuse to sell popcorn(我们卖的是爆米花,电影只是卖爆米花的理由)"——这句话明显夸张,却点出了院线财务结构的一个真相:**利润**往往藏在高毛利的卖品里,而不是那笔要和发行商分账的票房里。也正因如此,卖品的账面毛利率是否真实(Q1),才是本次分析的头号问题。

Lakeshore Rewards 会员计划是连接这两条线的纽带:免费注册、按消费积分,积分可以兑换卖品。管理层的假设是"会员计划提升复购频次,带来的增量票房和卖品消费,值得付出免费兑换的成本"。这个假设**是否成立**,恰恰是这次分析要检验的问题之一——因为兑换发生在卖品这条高毛利业务线上,如果兑换规模被低估或核算方式有问题,账面上"健康"的卖品毛利率可能只是一个假象。

单位经济数量级:一张标准票约 12.5 美元,一份中杯爆米花约 7-8 美元、成本约 2.5-3 美元。银幕本身也是资本开支和运营成本的来源——尤其是 IMAX 银幕,设备授权费、镜头/激光光源维护费用远高于普通银幕,这部分固定成本经常在"票价溢价看起来划算"的直觉判断里被忽略。

---

## 3. 行业普及:北美院线放映业(cinema exhibition)

如果你来自别的行业,这一节让你快速看懂"开电影院"这门生意。

**这个行业创造什么价值。** 院线(exhibitor)是电影产业链里离观众最近的一环:制片方(studio/production company)拍电影,发行商(distributor)把拷贝和放映权卖给院线,院线负责场地、设备、放映和现场体验,再从票房里按合约比例(通常首周院线只留 40%-50%,逐周递增)分得收入。这意味着**院线真正能自主定价、毛利又能全额留存的生意其实是卖品**,而不是要和发行商分账的电影票本身。

**主要玩家类别(不点名真实公司)。**

- **全国性大型院线连锁:** 银幕数上千块,议价能力强,能拿到更好的分账条款和首轮排片。
- **区域性院线连锁(如 Lakeshore Cinemas):** 银幕数在几十到几百块,深耕特定区域市场,靠本地化运营和会员计划维持复购。
- **独立艺术影院:** 小规模、专注艺术片和repertory 放映,商业模式与主流商业院线差异较大。
- **高端体验型影院:** 主打躺椅、餐饮堂食、IMAX/4DX 等差异化体验,票价溢价更高。

**监管与合规背景。** 院线行业本身监管强度不算高,但仍有几条相关规则:消防与建筑安全规范(每个市/县不同)、ADA(Americans with Disabilities Act,美国残疾人法案)对无障碍座位的要求、劳动法对小时工排班和最低工资的规定,以及与发行商之间的**排片合约(film booking agreement)**——这类合约不是政府监管,而是行业内的商业惯例,但对院线的场次安排有实质约束力(详见第 7 节)。

**当下的宏观力量。** 流媒体分流了部分观影需求,尤其是中等预算的成人向电影;院线越来越依赖"事件型"大片(tentpole films)和高端体验厅(IMAX、Premium)拉动票房;卖品和会员计划成为院线证明自己"不只是卖电影票"的关键叙事。这些压力让"我们的高端银幕是不是真的赚钱""我们的卖品毛利是不是真实健康"成为董事会每个季度都要追问的问题。

---

## 4. 项目框架:你在做什么

你是 Lakeshore Cinemas 新加入的 **BI 分析师(BI Analyst)**,直接向 **CFO** 汇报,同时为 VP of Concessions & Merchandising、VP of Film Programming 和董事会准备 **2026 年第二季度(Q2)运营评审(quarterly operating review)** 材料。

CFO 在上一次高管会上抛出了三个让她坐立不安的问题:卖品毛利率这几年账面上一直很漂亮,是不是掩盖了会员兑换的真实成本?公司这几年砸钱升级的 IMAX 银幕,是不是真的每一块都在赚钱?排片副总裁提到"深夜场上座率还不错",这个数字里是不是掺了水分?你的任务,是用 2026 年 Q2(4 月 1 日到 6 月 30 日,共 91 天)的完整场次、卖品和会员数据,把这几个问题用 SQL 一个个查清楚,产出能直接进董事会材料的结论。

交付物:Q2 运营评审 deck、卖品定价与兑换政策修订提案、银幕资本开支(capex)建议清单、以及给排片和运营团队的场次调整清单。所有分析都锚定固定参考日 **REFERENCE_DATE = 2026-06-30**(详见第 6 节)。

---

## 5. 本项目要解决的业务问题

整个数据集是为回答下面五个核心业务问题而设计的。其中前三个核心问题(Q1-Q3)各对应 ER 文档里一个**刻意埋设的数据陷阱**(deliberately embedded trap);后两个(Q4-Q5)是建立在同一套数据上的**运营分析型发现**,并没有额外埋设陷阱。五个问题在 SQL 查询文档里都有对应的查询。

1. **Q1 卖品真实现金毛利(Concession Cash Margin vs Recognized Margin):** Lakeshore Rewards 的免费兑换,是否被当作"正常销售收入"计入了卖品账面毛利?如果把兑换的"虚拟收入"剔除,只看真实收到的现金,毛利率会掉多少?
2. **Q2 高端银幕单银幕盈亏(Premium Screen Contribution):** IMAX 和 Premium 银幕的票价溢价,是否真的覆盖了这些银幕更高的能耗与维保成本?哪些具体银幕在持续亏钱,只是被其他银幕的盈利掩盖了?
3. **Q3 深夜场"保底票"侵蚀上座率真实性(Late-Night Buyback Inflation):** 部分热门大片的发行合约要求每场"最低开场人数",深夜场的上座率里,有多少其实是影院自己买回的票(comp/buyback ticket),而非真实观众?
4. **Q4 银幕与影院利用率(Screen Utilization & Rationalization):** 哪些银幕、哪些影院的场次利用率持续偏低,该考虑调整排片、转换银幕类型甚至关闭?
5. **Q5 场次时段与卖品匹配(Daypart Concession Alignment):** 不同场次时段(matinee/prime/late_night)的上座率和卖品客单价、销售构成有什么规律?这对卖品备货和小时工排班有什么指导意义?

除了这五个 marquee 问题,数据集还支持一批运营类分析:月度票房与卖品趋势、影院层级对比、会员分层消费行为、Top 卖品 SKU 排名等,用来回答日常运营和财务规划的问题。

---

## 6. 数据范围概览

- **时间跨度:** 2026 年第二季度(2026-04-01 至 2026-06-30,共 91 天)的完整场次、卖品和会员活动,全部锚定到固定参考日 **REFERENCE_DATE = 2026-06-30**。所有"今天 / 当前快照"的语义都按这个日期计算,而不是系统当前时间,保证多次运行和多次查询结果一致、可复现。
- **数据量(数量级,白话):** 18 家影院、92 块银幕、70 部影片、约 490 份排片合约、约 3.8 万场放映场次、约 2.1 万条卖品销售明细、7500 名活跃会员、约 2.8 万条会员积分兑换记录,合计约 9.7 万行。
- **刻意的范围取舍:**
  - **单一季度快照:** 只取 2026 Q2 一个季度,避免跨年度片单、票价调整等噪声,让分析聚焦在场次、卖品和会员这三条线的内部关系上。
  - **不刻画片租分账细节:** 院线与发行商之间的票房分账比例、结算周期是另一套独立的业务(属于发行商视角,不在本数据集范围),这里只关注院线自己留存的票房和运营成本。
  - **会员计划只取"活跃会员":** Lakeshore Rewards 注册用户远多于 7500 人,但本数据集只建模季度内有实际消费或兑换行为的活跃会员,避免大量从未使用积分的"僵尸账户"稀释分析。

(本节不列具体表;表结构见 ER 文档。)

---

## 7. 行业知识科普

外行看懂这份数据前,需要的大约三十分钟背景。建议按"一部电影从排片到散场"来理解。

**1) 排片合约(film booking)是什么。** 院线不能想放什么就放什么。每部电影上映前,院线要和发行商签一份**排片合约**,约定这块银幕在多长时间内放这部电影、以及一些附加条款。对于**事件型大片(tentpole film)**,发行商经常会附加一条**最低开场人数条款(minimum attendance clause)**:要求每场放映的到场人数不能低于某个门槛(比如 20 人),否则院线可能面临排片配额减少等后续影响。这条条款原本是为了保证发行商的票房曝光,但也制造了一个灰色地带——见下面第 3 点。

**2) 银幕类型与场次时段。** 银幕分三档:**Standard(标准厅)**、**Premium(大画幅躺椅厅)**、**IMAX(巨幕厅)**,票价逐档递增。一天的场次按开场时间分三个时段(**daypart**):**matinee(日场,中午前)**、**prime(黄金档,傍晚到晚间)**、**late_night(深夜场,23 点以后)**。不同时段的自然上座率差异很大——黄金档最高,深夜场通常最低。

**3) Comp ticket(赠票/买回票)与最低开场人数条款的灰色地带。** 院线偶尔会发放少量赠票(comp ticket)做促销或员工福利,这很正常,占比很低。但当某场深夜场的事件型大片自然上座率远低于发行合约要求的最低开场人数时,一些影院经理会选择自己"买回"一批票(即公司出钱买单,买家实际上还是自己),把到场人数凑到门槛以上——这样账面上的"上座率"和"comp ticket 占比"就会出现明显异常,这正是 Q3 要挖出来的模式。

**4) 忠诚度计划与积分兑换。** Lakeshore Rewards 会员每消费一定金额积累积分,积分可以 1:1 兑换成免费的卖品(比如一份中杯爆米花)。从公司角度看,这份"免费"卖品仍然产生了**真实的原材料成本(COGS)**,但**没有产生真实的现金收入**。如果财务系统把这份兑换按"正常售出"记为收入(即按该商品的正常售价确认收入),账面毛利率会显得比真实情况更健康——这正是 Q1 的核心陷阱。

**5) 银幕的隐藏固定成本。** 每块银幕,尤其是 IMAX,每个月都有能耗(激光光源、空调制冷)和维保(设备保养合同、镜头校准)的固定开支,这笔钱不随场次多少线性变化,是一笔"不管有没有人来看都要花"的固定成本。二线市场的 IMAX 厅如果观众基础小,即使票价溢价看起来不错,也可能覆盖不了这笔固定成本——这正是 Q2 的核心陷阱。

**6) 上座率与利用率。** **上座率(occupancy rate)** = 某场次实际付费观众 / 银幕座位数,衡量单场次的表现;**利用率(utilization)** 则是更长周期(比如一个季度)里银幕/影院的场次和上座综合表现,是资本开支和撤场决策的依据。

---

## 8. 术语表

每个在 ER 文档或 SQL 查询里出现的 jargon,这里给一句白话解释,外加"在本项目里为什么重要"。术语一律保留英文形式。

| 术语 | 白话解释 | 在本项目里为什么重要 |
|------|----------|----------------------|
| Exhibitor | 院线,即经营影院放映业务的公司 | Lakeshore Cinemas 本身的行业身份 |
| Film booking | 院线与发行商之间的排片合约 | 决定某银幕在某段时间放哪部片,以及是否有最低开场人数条款 |
| Minimum attendance clause | 排片合约里的"最低开场人数条款" | Q3 陷阱的合约来源 |
| Comp ticket / buyback ticket | 赠票或"影院自己买回的票" | Q3 用来识别虚假上座率的关键字段 |
| Daypart | 场次时段:matinee / prime / late_night | 决定自然上座率高低的核心维度 |
| Matinee | 日场,中午前的低价场次 | 自然上座率通常较低 |
| Prime | 黄金档,傍晚到晚间的场次 | 自然上座率通常最高 |
| Late night | 深夜场,23 点以后的场次 | Q3 陷阱最集中出现的时段 |
| Occupancy rate | 上座率 = 付费观众 / 座位数,按单场次计 | 场次表现的基本指标 |
| Screen utilization | 银幕利用率,按季度综合场次和上座衡量 | Q4 撤场/调整排片的依据 |
| Screen type | 银幕类型:Standard / Premium / IMAX | 决定票价档位和固定成本档位 |
| Market tier | 影院市场分层:Primary(一线)/ Secondary(二线) | Q2 陷阱集中出现在二线市场的 IMAX 厅 |
| Concession | 卖品,即爆米花、饮料、糖果等零售商品 | 营收占比不大,但毛利率极高、几乎全额留存,是院线利润的关键来源;Q1 检验其账面毛利是否被兑换稀释 |
| COGS (Cost of Goods Sold) | 卖品的原材料成本 | 计算真实毛利的分母之一 |
| Gross margin | 毛利率 = (收入 − COGS) / 收入 | Q1 对比"账面"与"现金"两个版本 |
| Recognized revenue | 财务系统确认入账的收入(可能包含兑换的虚拟收入) | Q1 陷阱的"虚高"一侧 |
| Cash revenue | 真实收到现金的收入(不含兑换) | Q1 陷阱的"真实"一侧 |
| Loyalty program | 忠诚度计划,即 Lakeshore Rewards | 连接会员消费与卖品兑换的载体 |
| Redemption | 会员用积分兑换卖品的行为 | Q1 陷阱的直接来源 |
| Redemption share | 兑换份额 = 兑换件数 / (付费件数 + 兑换件数) | 衡量兑换规模对毛利的稀释程度 |
| Screen contribution | 银幕贡献利润 = 票价溢价收入 − 该银幕能耗与维保成本 | Q2 用来识别亏钱的高端银幕 |
| Energy cost | 银幕的月度能耗开支 | Q2 固定成本的一部分 |
| Maintenance cost | 银幕的月度维保开支(含 IMAX 授权/镜头保养) | Q2 固定成本的一部分,IMAX 尤其高 |
| Tentpole film | 事件型大片,发行商重点押注的作品 | 通常附带最低开场人数条款 |
| Attach rate | 卖品搭售强度,本项目按"卖品件数 ÷ 付费观众数"计(单位:件/人),而非"买了卖品的人数占比" | Q5 场次与卖品匹配分析的核心概念 |

---

## 9. 关键指标与公式

下面是 SQL 查询里用到、或读者应当知道的指标。公式用通俗记法(SQL 风格伪代码),并注明输入和口径约定。

**卖品毛利(Q1)**

```
recognized_concession_revenue = SUM(concession_sale.gross_revenue) + SUM(loyalty_redemption.item_full_price × 1)
                                 -- 兑换按"全价"计入账面收入,这是本项目要检验的做法
cash_concession_revenue       = SUM(concession_sale.gross_revenue)
                                 -- 兑换不产生现金,真实现金收入不含兑换
total_concession_cogs         = SUM(concession_sale.cogs_amount) + SUM(loyalty_redemption.item_unit_cost)
                                 -- 兑换出去的商品仍然产生了真实成本
recognized_margin  = (recognized_concession_revenue − total_concession_cogs) / recognized_concession_revenue
cash_margin        = (cash_concession_revenue − total_concession_cogs) / cash_concession_revenue
margin_gap         = recognized_margin − cash_margin       -- 正值 = 账面毛利被高估了多少百分点
redemption_share   = COUNT(loyalty_redemption 行数=兑换件数) / (SUM(concession_sale.units_sold) + COUNT(loyalty_redemption 行数=兑换件数))
                     -- 付费侧用 SUM(units_sold) 件数总和 (concession_sale 是聚合表, 一行含多件); 兑换表一行=一件, 故用 COUNT(*)
```

**高端银幕贡献(Q2)**

```
premium_ticket_revenue(screen) = SUM(showtime.paid_attendance × (showtime.ticket_price − standard_baseline_price))
                                  -- 该银幕相对标准厅多收的票价部分
screen_fixed_cost(screen)      = SUM(screen_monthly_cost.energy_cost + screen_monthly_cost.maintenance_cost)
screen_net_contribution(screen) = premium_ticket_revenue(screen) − screen_fixed_cost(screen)
                                   -- 负值 = 这块银幕的票价溢价覆盖不了固定成本
```

**深夜场保底票(Q3)**

```
comp_share(daypart, has_minimum_guarantee) = SUM(showtime.comp_attendance) / SUM(showtime.paid_attendance + showtime.comp_attendance)
```

**上座率与利用率(Q4/Q5)**

```
occupancy_rate(showtime) = showtime.paid_attendance / screen.seat_capacity
screen_utilization(screen, period) = AVG(occupancy_rate) OVER (该银幕在该周期内的所有场次)
```

**卖品搭售(Q5)**

```
attach_rate(daypart) = SUM(concession_sale.units_sold WHERE daypart) / SUM(showtime.paid_attendance WHERE daypart)
                        -- 近似指标,按场次时段汇总,不做逐笔观众级别的匹配
```

> **口径说明(避免下游 SQL 打架):**
> - `recognized_concession_revenue` 是本数据集里刻意设计的"有问题的账面口径"——它把会员兑换按全价计入收入。SQL 查询会同时展示 `recognized_margin` 和 `cash_margin` 两个版本,不要只看其中一个。
> - `standard_baseline_price` 取同一影院内 Standard 银幕当期的平均票价,作为计算"溢价"的基准(只按影院分组,不按 daypart——票价只随银幕类型和周末浮动、不随 daypart 变化,这样口径才与 Query 4/5 一致)。
> - `screen_net_contribution` 只计算"票价溢价"部分,不含该银幕分摊的房租、人力等共同成本,是一个偏保守但足以暴露问题的近似口径。
> - `comp_share` 的正常基线在 2% 左右(促销赠票、员工福利票);Q3 要找的是明显偏离基线的组合(深夜场 × 有最低开场人数条款的排片)。
