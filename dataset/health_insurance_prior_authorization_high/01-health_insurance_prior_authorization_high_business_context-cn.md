# Meridian Health Plan 事前授权运营 业务背景

这份文档是 `health_insurance_prior_authorization_high` 数据集的总入口。它解释这家虚构公司是谁、靠什么赚钱、所在的健康保险行业怎么运转、你在项目里扮演什么角色、要回答哪些业务问题,以及读懂数据前需要先掌握的行业常识和术语。读完它,一个刚加入项目的新人就能在第一次站会上听懂同事在聊什么。

ER 文档 (`02-health_insurance_prior_authorization_high_er_document-cn.md`) 负责讲数据本身 (表、字段、约束、生成规则),SQL 查询文档 (`03-health_insurance_prior_authorization_high_sql_queries-cn.md`) 负责教你怎么用 SQL 把这些业务问题问出来。两份文档都假设你已经读过这一篇。

市场默认是北美。公司在美国德州,货币是 USD,监管机构是 CMS、HIPAA 这类美国联邦框架。中文只是叙述语言,业务本身是一家美国区域性健康保险公司。

---

## 1. 公司画像

**Meridian Health Plan** 是一家虚构的区域性健康保险支付方 (payer),总部设在德州奥斯汀 (Austin, Texas)。它在 ACA 个险交易所 (ACA marketplace) 上卖保险,产品按 Bronze、Silver、Gold、Platinum 四个金属层级 (metal tier) 划分,覆盖 HMO、PPO、EPO 三条产品线。它主要在德州及四个邻州销售,会员的居住州分布大致是 TX 70%、OK 8%、LA 8%、AR 7%、NM 7%。

按生产规模,Meridian 大约服务 25 万名参保会员。本数据集是从这本生产业务簿里刻意抽小的一份分析样本,只保留 400 名会员、12 个月的事前授权运营历史。抽小是为了让查询结果的数字直观可读,放到生产规模下,故事逻辑完全一样。

公司的组织结构里,有几个角色会反复出现在本数据集的报表里。运营条线有运营总监 (Operations Director) 和每天主持站会 (ops huddle) 的运营经理;医疗条线有医疗运营经理 (Medical Operations Manager) 和负责升级疑难案件的医疗主任 (Medical Director);合规条线有盯处理时限的 SLA 总监 (SLA Director);申诉条线有申诉运营团队;网络条线有 provider 网络经理 (Provider Network Manager);高层有 CEO、CMO (首席医疗官)、COO (首席运营官)、CFO。分析团队 (也就是你所在的位置) 给这些人产出报表。

---

## 2. 商业模式

健康保险支付方的赚钱逻辑和大多数行业不一样,值得花一分钟讲清楚。Meridian 向会员收取每月保费 (monthly premium),把这些保费汇成一个资金池,再用这个池子去支付会员产生的医疗费用 (claims)。利润大致等于 "保费收入 加 投资收益" 减去 "已付医疗费用 加 行政成本"。换句话说,公司本质是在做风险池管理:多数会员付的保费用不完,少数高费用会员把钱花超,精算的活儿就是让整池子收支为正。

衡量这门生意是否健康的核心指标叫 Medical Loss Ratio (MLR,医疗赔付率),也就是医疗赔付占保费收入的比例。ACA 规定个险 MLR 不得低于 80%,意思是每收 100 美元保费,至少 80 美元要花在会员医疗上,否则要把差额返还给会员。这条规则把支付方的利润空间压得很薄,所以控制医疗支出 (而不是简单地拒赔) 就成了运营的命脉。

定价上,保费随金属层级递增。本数据集里,Bronze 月保费约 320 美元、Silver 约 480、Gold 约 640、Platinum 约 820;层级越高,会员自付门槛 (deductible) 和自付上限 (out-of-pocket max) 越低,保费越贵,保障越厚。

事前授权 (Prior Authorization,PA) 就是支付方控费的关键杠杆。在做某些高价操作或开某些高价药之前,provider 必须先向 Meridian 申请授权,审核团队按医疗必要性 (medical necessity) 和覆盖政策 (coverage policy) 决定批不批。批准意味着公司承诺为这次服务买单,拒绝则把不必要或不达标的支出挡在门外。PA 既要防止过度医疗,又不能误伤合理治疗,这中间的平衡正是本数据集要量化的东西。

---

## 3. 行业概览

美国健康保险是一个由支付方和服务方两端拉扯、再被联邦和州两级监管夹在中间的市场。支付方 (payer,也叫 health plan 或 insurer) 收保费、担风险、付账单;服务方 (provider,包括医院、诊所、手术中心、医生) 提供医疗服务并向支付方计费。本数据集站在支付方 Meridian 这一侧。

市场里的主要玩家分几类。第一类是全国性大型支付方,体量巨大、产品线全。第二类是像 Meridian 这样的区域性支付方,扎根几个州、更懂本地 provider 网络。第三类是 Blue Cross Blue Shield 这类各州牌照的计划。围绕支付方还有两个配套角色:药品福利管理方 (PBM) 管处方药这一块,独立审查机构 (Independent Review Organization,IRO) 在会员把拒绝申诉到外部时做第三方裁决。

监管方面,最重要的是 CMS (Centers for Medicare & Medicaid Services,联邦医保医助中心),它规定了 PA 的处理时限 (例如加急申请 72 小时内必须决定)。HIPAA 管患者隐私和数据交换标准,本数据集里的临床笔记、诊断码都属于 HIPAA 保护的受保护健康信息 (PHI)。ACA (平价医疗法案) 定义了个险交易所、金属层级和 MLR 下限。

当下塑造这个行业的几股力量值得知道。一是 PA 改革:CMS 在 2024 年敲定了 Interoperability and Prior Authorization 最终规则,要求支付方公开 PA 审批数据、缩短时限、走电子化流程,行业正被推着把 PA 做得更快更透明。二是自动化和 AI:越来越多的 "无脑批准" 类决定交给规则引擎自动处理,人工只留疑难案件,本数据集里的 auto_rule 审核员就是这股趋势的体现。三是对拒绝率的舆论和监管审视:拒绝太多会引来投诉、申诉、媒体和监管关注,支付方必须能证明自己的拒绝是有依据的,而不是为了省钱乱拒。

---

## 4. 项目背景与你的角色

你是 Meridian 的一名数据分析师,坐在 utilization management (UM,使用管理) 分析团队里,向 UM 条线汇报,日常服务对象是运营、医疗、合规、申诉、财务几个部门的负责人。公司刚把过去 12 个月的 PA 运营数据汇成一个支付方侧的运营数据集市 (data mart),你的任务是用它搭建一套常态化的分析层:每天的运营报表、每周的合规和申诉复盘、每月给董事会和高管看的趋势材料。

你的产出会落到很多人手上。运营站会要看开放队列和滞留请求;SLA 总监要看处理时限达标率;CMO 和 COO 要看决定构成和自动化率的季度趋势;CFO 要看授权到理赔的转化、漏损和申诉挽回金额;provider 网络经理要看哪些 provider 的批准率异常。这些不是一次性的取数,而是要能反复跑、口径一致的指标。

时间上,数据锚定在生成当天 (TODAY),覆盖往前 12 个月。所有滚动窗口的报表 (近 30 天、近 90 天、近 6 个月) 都以这个锚点为基准。

---

## 5. 要解决的业务问题

整个数据集和它的 SQL 查询都围绕下面这几个具体问题展开。每个问题都能在数据里被一条或几条查询问出来。

**问题一,处理时限与产能。** 我们各紧急度的 PA 请求量是多少、状态怎么构成、有没有踩 CMS 规定的处理时限?哪些请求卡在队列里超了 SLA 还没决定?这关系到合规风险和人力调度。

**问题二,批准与拒绝是否公平合理。** 批准率在不同金属层级、不同专科、网络内外之间差多少?Bronze 的批准率明显低于 Platinum,这是精算设计使然还是政策标定偏差?provider 里有没有批准率异常高或异常低的离群点值得审计?

**问题三,拒绝原因的集中度。** 拒绝背后的结构化原因码 (CARC/RARC) 怎么分布?是不是少数几个码解释了大部分拒绝 (Pareto 形态)?找出这些 "vital few" 码,就能定向做 provider 再培训和政策澄清。

**问题四,授权到理赔的漏损。** 有多少已批准的授权最终没有变成 claim (会员拿了授权却没真去做服务)?这个漏损率是 CFO 判断准备金是否高估的前瞻信号。

**问题五,申诉流程与推翻率。** 拒绝被申诉的比例、多级申诉 (L1 内审、L2 内审、外部 IRO) 的走向、各层级的推翻率分别是多少?L1 推翻率过高说明一审判错太多,外部推翻率过高说明内部拒绝政策过严。被推翻的拒绝还能折算出一笔 "挽回金额"。

**问题六,自动化效果。** auto_rule 引擎、临床审核员、医疗主任各处理了多少决定、成本和批准构成如何?自动化份额能不能撑住,人工是不是只在啃硬骨头?

---

## 6. 数据范围概览

数据集覆盖锚定在生成当天往前 12 个月的 PA 运营历史。它是一份支付方侧的运营数据集市,而不是某个 SaaS 厂商的 AI 模型评测日志:每一张表都对应 Meridian PA 业务里的一个真实环节,从会员的保险计划、provider 的网络状态、PA 请求本身,到请求携带的结构化临床条目和非结构化临床笔记、抽取出的事实、决定、所应用的政策、由此引发的申诉,直至服务执行后的下游理赔单。

数据体量刻意做小:400 名会员、约 700 条 PA 请求、约 8,200 行数据,分布在 15 张表里。范围上做了几个有意的收窄。会员只覆盖 Meridian 实际销售的 5 个州;理赔做了 "一条授权对应一条 claim" 的建模简化 (真实业务里一条长期治疗授权会产生多条 claim);开放队列里人为预留了约 70 条在途请求,好让 "开放队列" 和 "滞留请求" 这类运营指标有可观测的样本。这些简化的目的都是让 BI 表面干净、数字直观。

关于时间锚点,需要特别说明本数据集的一个约定。生成器在运行时用 `date.today()` 解析出 TODAY,把所有时间戳锚定到运行当天。因此 SQL 查询里用的是 `DATE('now', '-N days')` 这种滚动窗口写法,而不是写死某个固定日期。每次重新生成数据,时间轴会整体平移到新的当天,所以滚动窗口的过滤条件在重生成后总能拿到非空结果。同一天内重新生成 (种子固定为 42) 产出的数据字节一致;跨天重生成行数和分布稳定,但各行的具体时间会随当天平移。

---

## 7. 行业知识科普

这一节是外行读懂本数据集前需要的半小时背景。

**PA 的全流程。** 一条事前授权大致走这么几步。Provider 先提交 PA 请求 (`pa_requests`),请求里挂着诊断码和操作码 (`request_clinical_items`) 以及非结构化的临床笔记 (`clinical_notes`)。前端分诊环节从笔记里抽取关键的结构化事实 (`extracted_clinical_facts`)。审核员对照支付方政策做出决定 (`pa_decisions`,记下所应用的政策)。如果被拒,会员或 provider 可以提起申诉 (`appeals`、`appeal_letters`)。如果批准且实际开展了服务,就生成下游的理赔单 (`claims`)。

**紧急度与 CMS 处理时限。** PA 请求按紧急度分三档,每档有不同的处理时限 (SLA):routine (常规) 14 天 (336 小时,CMS 标准)、urgent (加急) 72 小时 (CMS 加急标准)、emergent (急症) 2 小时 (内部 SLA)。emergent 一次踩线就可能直接耽误患者治疗,而 100 个 routine 里踩 1 个属于正常噪声,所以同样是 SLA 违约,严重程度天差地别。

**金属层级与成本分担。** ACA 用金属层级表达保障厚度。Bronze 保费最低但会员自付最多,Platinum 反之。会员自付由几部分组成:copay (固定挂号费式的共付额)、deductible (年度自付门槛,达到前自己掏)、coinsurance (达到门槛后按比例分担)。本数据集里,会员自付占 allowed 金额的比例大致是 Bronze 30%、Silver 24%、Gold 17%、Platinum 13%。

**医疗编码体系。** 临床世界用三套编码说话。CPT 码描述 "做了什么操作" (例如 27447 是全膝置换);ICD-10 码描述 "得了什么病" (例如 M17.11 是右膝原发性骨关节炎);HCPCS 码 (尤其 J 开头的 J-code) 描述药品和耗材 (例如 J1745 是英夫利昔单抗)。一条 PA 请求通常同时挂诊断码 (说明为什么需要) 和操作码 (说明要做什么)。

**拒绝原因码。** 拒绝不是一句自由文本说了算,背后有结构化的原因码:CARC (Claim Adjustment Reason Code) 和 RARC (Remittance Advice Remark Code),例如 CO-50 "服务非医疗必要"、N-130 "请查阅计划福利文件"。结构化码能干净地聚类统计,这是做拒绝分析的基础。

**申诉的层级。** 被拒后申诉分三级:L1 是第一次内部复审,L2 是更高级别的内部复审 (常由医疗主任经手),外部审查则交给独立的第三方机构 IRO 裁决 (在数据里以 level_number = 3 且 is_external_review = TRUE 表示)。每升一级,人力成本和时限要求都更高。推翻 (overturn) 意味着原始拒绝被判错。

**自动审核。** 不是每条决定都要人看。auto_rule 引擎处理大量规则明确的 "无脑批准",每个决定成本只有几美元;临床审核员 (clinical_reviewer) 和医疗主任 (medical_director) 处理疑难和拒绝案件,后者每个决定的人力成本高得多。自动化率是衡量运营效率的关键。

---

## 8. 术语表

下面这张表收录 ER 文档和 SQL 查询里会用到的英文术语,给出 layman 解释和它在本数据集里为什么重要。首次出现的缩写给出全称。

| 术语 | 含义 (大白话) | 为什么在这里重要 |
|---|---|---|
| Prior Authorization (PA) | 事前授权,做某些操作或开某些药前先向保险公司申请批准 | 整个数据集的核心业务对象 |
| Payer | 支付方,也就是保险公司,收保费、付账单 | Meridian 就是支付方,数据站在它这一侧 |
| Provider | 服务方,提供医疗服务的医院、诊所、医生 | PA 请求的发起者 |
| ACA Marketplace | 平价医疗法案下的个险交易所,个人在上面买保险 | Meridian 的销售渠道 |
| Metal Tier | 金属层级 (Bronze/Silver/Gold/Platinum),表达保障厚度 | 批准率、自付比例都按层级分布 |
| HMO / PPO / EPO | 三种网络管理模式,区别在能不能看网络外医生、要不要转诊 | 产品线维度 |
| Premium | 保费,会员每月交的钱 | 支付方的收入来源 |
| Deductible | 年度自付门槛,达到前医疗费自己掏 | 决定会员自付结构 |
| Out-of-Pocket Max | 年度自付上限,超过后保险全包 | 保障厚度的关键参数 |
| Cost-sharing | 成本分担,会员自付的统称 (含 copay、deductible、coinsurance) | Q27 算会员自付比例 |
| Coinsurance | 共保,达到门槛后会员按比例分担费用 | 自付的组成部分 |
| MLR (Medical Loss Ratio) | 医疗赔付率,赔付占保费的比例,ACA 要求个险不低于 80% | 决定控费为什么重要 |
| Utilization Management (UM) | 使用管理,通过 PA 等手段管理医疗资源使用 | 你所在团队的职能 |
| CPT | 操作码,描述 "做了什么操作" (如 27447 全膝置换) | 请求和理赔的核心编码 |
| ICD-10 | 诊断码,描述 "得了什么病" (如 M17.11 右膝骨关节炎) | 说明医疗必要性 |
| HCPCS / J-code | 药品耗材码,J 开头的是注射类药品 (如 J1745 英夫利昔单抗) | 药品类 PA 的编码 |
| DME | Durable Medical Equipment,耐用医疗设备 (轮椅、助行器等) | 部分 HCPCS 码对应的品类 |
| NPI | National Provider Identifier,国家提供方标识符 | provider 主键 |
| CARC | Claim Adjustment Reason Code,理赔调整原因码 (如 CO-50) | 结构化拒绝原因 |
| RARC | Remittance Advice Remark Code,汇款通知备注码 (如 N-130) | 结构化拒绝原因 |
| SLA | Service Level Agreement,服务时限承诺 | 合规和运营的核心约束 |
| TAT (Turnaround Time) | 处理时长,从提交到决定花了多久 | 物化在 tat_hours 字段 |
| Medical Necessity | 医疗必要性,这次服务在临床上是否确有必要 | 批准与否的核心判据 |
| Step Therapy | 阶梯治疗,要求先试便宜的一线疗法再上贵的 | 常见拒绝原因之一 |
| Pended | 挂起,缺材料暂时定不了、待补充 | 一种非终态决定 |
| Escalated | 升级,转给医疗主任进一步审 | 疑难案件的处置 |
| Partial Approval | 部分批准,批一部分服务线、拒一部分 | 决定类型之一 |
| Appeal | 申诉,会员或 provider 对拒绝提出复审 | Q10 到 Q12、Q28 的主题 |
| IRO | Independent Review Organization,独立审查机构,做外部第三方裁决 | 申诉的最外层 |
| Overturn | 推翻,申诉成功、原拒绝被改判 | 衡量首审质量 |
| Claim | 理赔单,服务实际发生后向支付方计费的单据 | PA 的下游 |
| Billed / Allowed / Paid Amount | 计费金额 / 计划认可金额 / 实付金额 | claim 的三层金额 |
| Member Responsibility | 会员自付金额 | Q27 的核心 |
| Leakage | 漏损,已批准却没变成 claim 的授权 | Q9 的主题 |
| Auto-adjudication / auto_rule | 自动审核,规则引擎自动出决定 | 自动化率的来源 |
| Medical Director | 医疗主任,处理升级和疑难拒绝的资深医生 | 高成本审核角色 |
| Confidence Score | 置信分,审核员对该决定的把握程度 (0.55 到 0.99) | Q15 的分析对象 |
| Coverage Policy | 覆盖政策,规定某操作在什么条件下能批的文件 | 决定的依据,Q21 的主题 |

---

## 9. 关键指标与公式

下面是本数据集 SQL 查询里会用到的核心指标。口径统一在这里给定,避免下游查询各算各的。

**批准率 (Approval Rate)** 衡量已决定请求里批准的占比。注意分子要把 partial_approved 也算成 "批了一部分"。

```
approval_rate = COUNT(decision IN ('approved','partial_approved')) / COUNT(all decisions)
```

**拒绝率 (Denial Rate)** 是 denied 决定占已决定请求的比例。

```
denial_rate = COUNT(decision = 'denied') / COUNT(all decisions)
```

**处理时长 (TAT, Turnaround Time)** 是从提交到决定经过的小时数,已物化在 `pa_decisions.tat_hours`,查询直接用即可,不必每次算 JULIANDAY 差。

```
tat_hours = (decided_at - submitted_at) 折算成小时
```

**SLA 违约率 (SLA Breach Rate)** 是处理时长超过该紧急度对应 SLA 窗口的决定占比。是否违约已物化在 `pa_decisions.sla_breached`。

```
sla_breach_rate = COUNT(tat_hours > sla_hours) / COUNT(all decisions)，按 urgency 分组
```

**PA 到 Claim 转化率与漏损 (Conversion / Leakage)** 衡量批准的授权里有多少真的产生了 claim。

```
conversion_rate = COUNT(DISTINCT claims) / COUNT(DISTINCT approved decisions)
leakage_count   = COUNT(approved decisions) - COUNT(approved decisions with a claim)
```

**申诉率与升级率 (Appeal / Escalation Rate)** 描述申诉漏斗的形状。

```
l1_appeal_rate      = COUNT(denials with an L1 appeal) / COUNT(all denials)
l1_to_l2_escalation = COUNT(decisions reaching L2) / COUNT(decisions with L1)
l2_to_ext_escalation = COUNT(decisions reaching external) / COUNT(decisions with L2)
```

**推翻率 (Overturn Rate)** 是某层级里被推翻的申诉占已结案申诉的比例。

```
overturn_rate = COUNT(overturned) / COUNT(resolved appeals)，按 level_number 分组
```

**自动化率 (Automation Rate)** 是 auto_rule 角色做出的决定占全部决定的比例。

```
automation_rate = COUNT(decisions by auto_rule) / COUNT(all decisions)
```

**会员自付比例 (Member Cost-share %)** 是会员自付占计划认可金额的比例,用来核对精算设计是否在 claim 落地后成立。

```
member_share_pct = SUM(member_responsibility_usd) / SUM(allowed_amount_usd)，按 metal_tier 分组
```

**实付占计费比 (Paid % of Billed)** 反映计费到实付之间的折扣力度。

```
paid_pct_of_billed = SUM(paid_amount_usd) / SUM(billed_amount_usd)
```

**环比增长 (MoM Growth)** 用于月度量趋势。

```
mom_growth_pct = (本月量 - 上月量) / 上月量
```

**申诉挽回金额 (Recovery Amount)** 是被推翻拒绝所对应操作码的预期计费金额之和,量化首审错误的运营成本。

```
recovery = SUM(service_catalog.avg_billed_amount_usd) 覆盖所有被推翻拒绝的 CPT/HCPCS 行项
```
