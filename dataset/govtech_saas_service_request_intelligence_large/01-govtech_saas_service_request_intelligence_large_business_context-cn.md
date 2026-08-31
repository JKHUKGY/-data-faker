# CityPulse 311 服务请求智能平台业务背景

本文档是数据集 `govtech_saas_service_request_intelligence_large` 的业务背景说明。读完本文你应该能像一位刚入职 CityPulse 分析团队的新人那样, 在第一次 stand up 上和同事正常对话: 知道公司靠什么赚钱, 知道客户是谁, 知道我们的产品在城市政府里扮演什么角色, 知道你接下来要回答的五个业务问题分别是什么意思, 也知道每个英文 jargon (311, SLA, FCR, NPS, ARR) 指的具体是哪件事。

数据细节 (有哪些表, 每张表干什么, 字段类型, 样例行) 都放在同目录下的 `govtech_saas_service_request_intelligence_large_er_document-cn.md`。SQL 查询和分析方法放在 `govtech_saas_service_request_intelligence_large_sql_queries-cn.md`。本文档只讲业务和行业, 不讲表结构。

---

## 1. 公司简介

CityPulse 是一家总部位于 Texas 州 Austin 的 Govtech SaaS 公司, 成立于 2014 年, 主营业务是给北美中型城市和县级政府提供"311 服务请求"全流程管理平台。所谓 311, 是北美城市设置的"非紧急市政热线", 类似 911 (紧急救援) 的姊妹号码: 居民可以通过电话, 手机 App, 网站, 邮件, 社交媒体 (Twitter/X 和 Facebook 上的城市账号) 等任何一个渠道, 上报路面坑洼, 垃圾未清运, 路灯不亮, 树枝压线, 流浪动物, 噪声扰民这类"不需要警察消防, 但需要市政部门解决"的事。CityPulse 卖的就是承接, 分类, 路由, 派单, 跟踪这一整条工单流的系统。

公司当前规模大致是: 全职员工 252 人, 2025 财年 ARR 约 5000 万美元 (对应数据集里 120 个 active 合同的 arr_usd 合计口径), 服务的城市和县级客户 120 个 (其中 US 城市 98 个, US 县级 8 个, Canadian 城市 14 个), 平台真实运营中年聚合处理居民服务请求约 1000 万条。注意: 本数据集是平台真实流量的**抽样子集** (36 个月共约 100 万条请求, 约每年 33 万条), 不是全量, 所以"年处理 1000 万条"是平台规模口径, 与数据集行数差一个数量级是正常的。客户体量从人口 5 万的小城 (Burlington, VT) 到接近 100 万的旗舰大城 (Austin, TX, 约 98 万, 也是 CityPulse 总部所在地; 另有 Winnipeg 约 75 万) 都有, 但不接 New York City, Los Angeles, Toronto 这一级的超大城市, 因为大城市通常自己开发系统或者用 Tier 1 厂商 (Accenture, Tyler Technologies)。

组织架构上, CEO 是 Linda Park, 下面分 Engineering, Product, Customer Success, Data, Go to Market, Finance 六条线。和你工作直接相关的: CDO Marcus Chen 管 Data 组, 下设 Data Science (NLP 模型, 由 Director Priya Iyer 带), Analytics (你所在的组, 由 Director Tom Brennan 带), 以及 Data Platform。VP of Customer Success Rachel Wong 管所有 tenant 关系, 她的团队是 SQL queries 文档里很多"客户健康度"相关问题的最终消费者。CRO Daniel Ortega 管销售和续约, 因此一切和 churn risk, ARR retention 相关的分析最终都要送到他桌上。

---

## 2. 商业模式

CityPulse 卖的是订阅 SaaS。每个客户城市签的是 12 个月或 36 个月合同, 按"城市人口分段 + 模块选配"定价。基础平台模块 (intake, routing, SLA tracking, 居民查询门户) 是必选; AI Insight Pack (含自动分类模型, 情绪分析, 重复请求识别), Field Mobile Pack (现场 crew 用的手机端), Analytics Pack (BI 仪表板) 是选配。

合同 ACV (Annual Contract Value) 大致区间: 人口 5 万到 15 万的小城在 12 万到 25 万美元之间; 人口 15 万到 40 万的中等城市在 25 万到 60 万美元之间; 人口 40 万以上的较大城市在 60 万到 120 万美元之间 (最大的旗舰大城如 Austin 接近 100 万人口, 落在这一档上沿)。算上选配模块, ACV 中位数约 32 万美元, top 10 客户每家 ACV 都超过 80 万。Gross margin 在 72% 到 78% 之间 (SaaS 标准带), 但其中"AI Insight Pack 的边际成本几乎为零, 续约率高"是公司过去三年增长的核心引擎, 所以高层非常在意这个模块的实际效果。

收入确认按订阅期均摊。客户合同中通常包含一次性"implementation fee" (12 万到 40 万不等, 取决于和客户原有系统的集成复杂度), 这部分按 implementation 完成里程碑确认, 不在 ARR 口径里。Net Revenue Retention (NRR) 是公司的北极星指标之一, 2025 财年是 112%, 主要靠"客户先签基础包, 第二年加 AI Insight Pack"驱动。Gross Logo Retention 是 94%, 意味着每年大约 7 个客户城市流失 (通常是市长换届后启动新一轮采购, 或者预算冻结)。

收费定价之外, 平台还有一类隐性收入: 每年大约 6 到 10 个客户会请 CityPulse 的"Professional Services"团队做定制报告, 报告费按小时计 (300 美元/小时), 这块业务一年加起来约 200 万美元, 不在 ARR 里, 但贡献正向 cash flow。

---

## 3. 行业概览

Govtech (政府科技) 行业指的是把现代软件方法卖给政府的细分市场。和企业 SaaS 比, Govtech 的几个特征要先理解:

第一, 客户决策周期长。市政采购走 RFP (Request For Proposal) 流程, 从立项到签约平均 9 到 14 个月。客户内部要过预算委员会, City Council 投票, 偶尔还要居民公示。这意味着 CityPulse 销售周期长, 但客户一旦签约, 离开的成本也高 (数据迁移, 居民再教育, 部门流程重写), 所以行业 NRR 普遍高于 100%, 流失率低。

第二, 客户高度同质化但又高度分散。每个北美城市的市政部门构成大同小异 (Streets, Sanitation, Parks, Code Enforcement, Utilities), 但每个城市的命名, 部门切分, SLA 标准, 编码规则都不一样。这是为什么 CityPulse 的核心产品功能就是"可配置的路由规则引擎"和"按租户隔离的元数据"。

第三, 监管和透明度要求高。北美很多州/省强制要求城市公开 311 数据。Boston, Chicago, New York 都有 open data portal 把 311 数据 csv/json 公开下载。这对 CityPulse 是双刃剑: 一方面客户必须给居民提供"查询自己请求状态"的入口 (CityPulse 提供 citizen portal); 另一方面公开数据让对手很容易做竞品对标。相关法规和合规框架包括 FOIA (US 联邦, 公民有权索取政府文件), state level Open Records Acts (各州有自己版本), Canadian FIPPA (Freedom of Information and Protection of Privacy Act, 安省版本最有名), 以及涉及居民个人信息时的 GDPR-like state law (CCPA in California, BIPA in Illinois 等)。CityPulse 平台天然要遵守这些, 设计上把"哪些字段对公众可见, 哪些只对市政内部可见, 哪些必须删除"做成租户级配置项。

第四, 行业当前的几个宏观趋势: (1) AI 替代人工分类。过去 311 中心需要十几个 call taker 听完居民描述后手工选类别和部门, 现在主流厂商都在卖 NLP 自动分类模型, CityPulse 的 AI Insight Pack 就是这个赛道。(2) 渠道从语音迁移到数字。十年前 70% 的 311 请求来自电话, 现在低于 35%; 来自移动 App 和社交媒体的份额每年增长 15% 左右。(3) 合并与收购。Tyler Technologies, Granicus, OpenGov 这些 Tier 1 厂商在过去三年合计完成了 11 起 Govtech 收购, 中型厂商 (CityPulse 就是) 面临要么被并要么扩张到隔壁品类 (permitting, procurement) 的选择。

---

## 4. 项目背景与你的角色

你的身份是 CityPulse 的 Senior Data Analyst, 直接汇报给 Director of Analytics Tom Brennan, 工作两年, 平台所有租户的数据你都有只读权限 (公司内部叫 cross tenant view)。今天是 2026 年 6 月初, 公司正在准备 Q3 的 Quarterly Business Review (QBR), CEO Linda 给 Marcus Chen (CDO) 派了一个跨季度的题目: "AI Insight Pack 到底有没有兑现卖给客户时承诺的价值"。这个题目层层往下分, 最后到了你头上, 变成接下来几周你要主导的一份分析。

这份分析的具体诉求来自三方面利益相关者的不同关切。第一, CEO 关心的是商业问题: AI Insight Pack 的实际效果如果没卖点强, 续约时会不会被砍掉, 影响 NRR? 第二, CDO 关心模型质量本身: 我们的分类器在不同客户城市的实际准确率是多少, 哪些城市效果差, 为什么? 第三, VP of Customer Success Rachel 关心客户运营: 哪些客户的 SLA 表现在恶化, 我们应该提前介入的预警信号有哪些?

更深层的痛点是, CityPulse 平台上有大量"非结构化文本"信号 (居民提交的请求描述, 现场 crew 写的工单备注, 居民升级到议会时的投诉叙述), 但目前公司绝大多数运营指标和模型评估都只用结构化字段 (auto category, stated_severity, channel, dept_id, sla_breach_flag)。Marcus 长期怀疑"结构化字段和文本之间存在系统性偏差", 但一直没人系统地量化。这次 QBR 是一次正当的机会, 把这个怀疑落到具体数字上。

你的产出物有三个: 一份给 Linda 的 8 页 deck (高层结论 + 商业建议), 一份给 Marcus 和 Priya 的技术备忘 (模型质量诊断, 含建议的改进方向), 一份给 Rachel 的客户预警名单 (按风险排序的 top 20 tenants)。Deck 的截止日期是 2026 年 7 月 18 日, 离今天还有 6 周。

你能调取的数据范围是平台过去 36 个月所有租户的全量数据, 锚定在 `REFERENCE_DATE = 2026-06-01`。所有"今天", "当前", "snapshot" 的 SQL 查询都用这个字面日期, 不用 `DATE('now')`, 保证结果可复现。

---

## 5. 业务问题

下面五个问题就是你接下来要回答的核心问题。每个问题在 SQL 查询文档里都有对应的查询直接揭示, 在 ER 文档里都有对应的"数据陷阱"作为生成层面的契约。

问题一: 自动分类器把多少请求错分到了 "Other", 这个误分类对 SLA 表现造成了多大的伤害? CityPulse 的自动分类器目前把约 8% 的请求归入 `Other / Uncategorized` 类, 平台默认把这类请求送到客户城市的"综合咨询队列", SLA 是 5 个工作日 (vs 专门部门队列普遍是 1 到 2 个工作日)。怀疑是: 实际上这 8% 里有相当一部分文本里明确含有 pothole, streetlight, graffiti 这类强关键词, 模型应该认得出来。如果属实, 这些请求被"错配"到慢 SLA 通道, 是 CityPulse AI Insight Pack 在 churn talk 中被攻击的把柄。

问题二: 居民勾选的严重度 (stated_severity) 和描述文本暗示的真实严重度之间有多大偏离, 偏离的请求有多严重的下游后果? CityPulse 让居民在提交时四选一: Low, Medium, High, Emergency。但很多居民 (尤其是通过 IVR 电话或社交媒体提交的) 描述里出现 "gas leak", "live wire", "fire", "smoke", "child injured", "leaking" 这类关键词时仍然只勾了 Medium 或 High。这些请求按结构化字段被分到普通优先级队列, 真实严重度对不上, 后续往往出现 reopen 或者升级。

问题三: 我们看到的"24 小时内关闭, 按时完成"的请求里, 有多少是同址在 30 天内又被报修一次的"假闭环"? 现场 crew 有 KPI 压力 ("first touch resolution rate" 这个指标和奖金挂钩), 所以有动机在初次到场后"快速关闭", 但问题没真正解决。如果同址 30 天内复发率高, 我们的"按时解决率"就高估了真实绩效。

问题四: 哪些文本特征能预测居民最终升级到 city council 投诉? 平台外的 City Council 投诉 (居民给市议员写信, 议员转给市政府, 议员办公室再要求 CityPulse 客户做 root cause 报告) 数量上虽然小 (大约请求总量的 0.4%), 但是政治成本极高, 也是 city council 在续约时是否支持继续用 CityPulse 的关键。我们怀疑居民在原始描述里写下 "third time this month", "fed up", "I will contact my councilman", "going to the news", "lawyer" 之类的话时, 后续被升级的概率显著高于基线。如果属实, 我们能给客户城市的 Customer Success 人员一个"投诉预警"功能。

问题五: 同一个全球分类模型, 在不同客户城市的实际准确率有多大差异, 差异背后的解释因素是什么? CityPulse 的模型是用所有客户聚合数据训练的, 但部署到不同城市时, 当地词汇 (Quebec 法语化的英文混用, 美国深南方俚语, 西海岸技术圈用语) 都会影响识别效果。如果某些城市模型准确率显著低于中位数, 这些城市的 SLA 表现也会被拖累。识别出这批城市可以驱动两件事: (a) Customer Success 主动介入避免续约风险; (b) Data Science 团队对这批城市做模型微调或者本地化词表。

---

## 6. 数据范围

数据集覆盖 36 个月的平台运营数据, 锚定 `REFERENCE_DATE = 2026-06-01`, 因此数据时间范围是 2023-06-01 到 2026-06-01。所有"今天", "本月", "上季度"在 SQL 中都解析为基于这个固定日期的字面值, 不允许使用 `DATE('now')`。

总体量级 (口径都是 order of magnitude, 不是精确值): 大约 120 个租户城市, 50 万注册居民账号, 15 万已知地址, 8 万市政资产 (路灯, 消防栓, 垃圾桶, 路口编号等可被请求引用的对象), 2.5 万市政员工账号, 100 万条服务请求, 400 万条请求生命周期事件 (created/assigned/in_progress/closed/reopened), 60 万张工单, 100 万条工单备注, 100 万条模型预测记录, 约 21 万条 SLA 超时记录, 约 5000 条 city council 投诉记录, 4000 条租户月度健康度快照。总行数约 1000 万, 落在 Large 复杂度的"百万级以上"区间。

刻意的范围裁剪: 暂不包含 (1) 计费和合同的 finance 数据 (Finance 组用 Salesforce 和 NetSuite, 不在本平台), (2) 现场 crew 的实际行驶轨迹 GPS 数据 (隐私敏感, 部分客户禁止收集), (3) 客户城市自己上传的 GIS 图层 (体积大, 不在本次分析需要)。地理范围限定北美 (US + Canada), 货币 USD。语言上居民描述文本以英文为主, Quebec 系城市包含少量 French/English 混合表达 (用于触发问题五的"租户级模型精度差异"陷阱)。

---

## 7. 行业知识入门

下面这 30 到 60 分钟的内容是你做这份分析前需要知道的"行业默认知识"。代码和模型都建立在这些约定之上。

311 全流程从居民端到现场作业一共有六个阶段: (1) Intake 接收: 居民通过电话, 网站, 手机 App, 社交媒体, 邮件, 步入式 (walk in) 等渠道提交, 系统记录原始描述和元数据。(2) Classification 分类: 自动模型或者人工 call taker 给请求打上类别 (pothole, streetlight, sanitation, noise complaint 等 66 个细分类别之一, 再加上一个兜底的 Other, 合计 67 个) 和初步优先级。(3) Routing 路由: 系统根据租户级的"类别到部门"映射表把请求派给对应部门 (Streets, Parks, Code Enforcement, Sanitation, Utilities, Animal Services 等)。(4) Assignment 派单: 部门内派给 supervisor 再转派给具体 crew 或者 inspector, 生成 work order (WO)。(5) Field Work 现场作业: crew 到现场处置, 在手机端 (CityPulse Field Mobile Pack) 写工单备注, 关闭工单。(6) Closure 关闭: 系统自动或人工关闭 service request, 通知居民。

SLA 的具体含义: 每个租户城市对每个类别都配置了 SLA target (以工作日为单位, 比如 pothole 是 2 个工作日, streetlight 是 5 个工作日, illegal dumping 是 3 个工作日)。从 created_at 到 closed_at 的工作日差大于 SLA target 就算"breach"。注意是 business days, 跳过周末和市政公共假期。CityPulse 平台把每个客户的假期日历存在租户配置里, 所以同一天对 Austin 和 Toronto 来说工作日定义可能不同。

请求的几种状态机转移: created -> classified (有了类别) -> assigned (派给某部门) -> in_progress (现场处置中) -> closed (关闭) 是主流转换。还有几个分支: closed 之后 30 天内同一个请求可以被 reopened (主动重开, 或者居民再次报告并系统识别到关联), 重开后回到 in_progress; assigned 之后可以转到 on_hold (现场无法处理, 比如等天气, 等设备), on_hold 之后回到 in_progress 或者直接 closed。每次状态转换在 `request_events` 表里留下一条记录。

居民端的几个常见行为: 同一个居民有时候同一天对同一件事提交两到三次 (从不同渠道, 或者忘了已经提交过), 系统会做"重复检测"把后续视为 duplicate, 但 duplicate 检测不完美。重复检测漏掉的, 就会变成"同址多请求"的数据信号, 也是问题三 (假闭环) 检测的依据。

NLP 自动分类模型的工作方式: CityPulse Data Science 团队维护一个文本分类模型 (BERT 微调的多分类器), 输入是请求描述 (description_text) 加上一些元数据 (channel, asset_type), 输出是 67 个类别上的 softmax 概率分布。取 top 1 类别作为 `predicted_category`, 如果 top 1 的概率低于 0.45 阈值就 fallback 到 Other。预测结果写入 `model_predictions` 表; 但请求表里实际使用的 `auto_category` 可能被 call taker 或者 supervisor 人工 override, 因此 `auto_category` 不一定等于 `predicted_category`。当 `auto_category` 和事实类别 (`ground_truth_category`, 由 audit 人员事后标注的子集) 不一致, 就构成"误分类"。

---

## 8. 关键术语

| 术语 | 中文解释 | 在本数据集中的相关性 |
|------|----------|----------------------|
| 311 | 北美城市的"非紧急市政热线"号码, 类似 911 的姊妹号 | 整个数据集的业务核心 |
| Tenant | CityPulse 平台上的一个客户城市或者县 | tenants 表的每一行, 跨租户分析是你的工作 |
| Service Request (SR) | 居民提交的一条请求记录, 平台核心实体 | service_requests 表 |
| Work Order (WO) | 派给现场 crew 处置的工单, 一个 SR 可能对应 0 或 1 个 WO | work_orders 表 |
| SLA (Service Level Agreement) | 每个类别在每个租户设定的"几个工作日内必须关闭" | sla_policies 表, sla_breach_log 表 |
| Breach | SLA 超时, 即实际关闭工作日数大于约定值 | sla_breach_log.is_breach |
| FCR (First Contact Resolution) | 居民提交后, 第一次现场处置就结清, 不需要二次回访 | 问题三的核心指标 |
| Reopen | 已关闭的请求在 30 天内重新打开 | request_events 中 event_type = reopened |
| Repeat at Address | 同一地址 30 天内有多于一条请求, 是真实未解决的信号 | 问题三, 用窗口函数检测 |
| Stated Severity | 居民提交时勾选的严重度 (Low/Medium/High/Emergency) | service_requests.stated_severity |
| Text Implied Severity | 从描述文本关键词推断的真实严重度 | 问题二的核心冲突源 |
| Channel | 提交渠道 (web, mobile_app, ivr, social, email, walk_in) | intake_channels 表 |
| Auto Category | 平台落库时使用的类别 (模型预测或人工 override 后的结果) | service_requests.auto_category |
| Predicted Category | NLP 模型 raw 输出的 top 1 类别 | model_predictions.predicted_category |
| Ground Truth Category | 事后审计标注的真实类别 (仅覆盖采样子集) | model_predictions.ground_truth_category |
| Model Confidence | NLP 模型 top 1 类别的 softmax 概率 | model_predictions.confidence_score |
| City Council Complaint | 居民越过 311 直接投诉到市议员或议员转来的正式投诉 | citizen_complaints 表, 问题四的目标变量 |
| Tenant Health Snapshot | 每月一次按租户聚合的运营健康度快照 (SLA, NPS, 续约风险等) | tenant_health_snapshots 表 |
| ARR | Annual Recurring Revenue, 年度经常性收入 | tenant_subscriptions.arr_usd, CityPulse 的北极星之一 |
| NRR | Net Revenue Retention, 含 expansion 的留存率 | 来自 tenant_subscriptions 的衍生指标 |
| AI Insight Pack | CityPulse 的 AI 模块 (自动分类, 情绪分析, 重复检测) | tenant_subscriptions.has_ai_insight_pack |
| RFP | Request For Proposal, 政府采购流程的标书 | 行业背景, 不在本数据集表里 |
| FOIA | Freedom of Information Act, 美国公民信息公开法 | 平台的合规约束, 不在表里 |
| Code Enforcement | 城市的"违规执法"部门, 处理建筑违规, 占道经营, 高草等 | departments 表的一种 dept_type |
| IVR | Interactive Voice Response, 电话语音交互系统 | intake_channels 的一种, 文本质量最低 |
| call taker | 311 中心接电话的人工坐席 | 人工 override auto_category 的角色, 不是表 |

---

## 9. 关键指标与公式

下面这些指标在 SQL queries 文档里反复出现, 这里给出唯一的定义, 避免下游 SQL 之间互相打架。

SLA Breach Rate (按请求): 一段时间内 closed 的请求中, breach 的占比。

```
SLA Breach Rate = COUNT(SR WHERE is_breach = 1 AND closed_in_period) / COUNT(SR WHERE closed_in_period)
```

`is_breach` 的计算: 从 created_at 到 closed_at 之间的"业务日"个数, 减去类别对应 SLA target 天数, 大于 0 即为 breach。本数据集为了简化, 把"业务日"近似为"自然日跳过周六周日", 不再扣除公共假期 (这是一个有意的近似, 真实平台会扣假期)。

Reopen Rate: closed 的请求中, 30 天内被 reopen 的占比。

```
Reopen Rate = COUNT(SR WHERE reopened_within_30d) / COUNT(SR WHERE closed_in_period)
```

Repeat at Address Rate: closed 且 SLA 达标的请求中, 同地址 30 天内有另一条新请求 (不同 request_id) 的占比。这个指标和 Reopen Rate 不同: reopen 是同一条 SR 被重新打开, repeat at address 是新开一条 SR。

```
Repeat at Address Rate = COUNT(SR WHERE closed_in_period AND is_breach=0 AND new_SR_within_30d_same_address) 
                       / COUNT(SR WHERE closed_in_period AND is_breach=0)
```

Classifier Accuracy (租户级): `model_predictions` 中 `predicted_category = ground_truth_category` 的占比, 仅在 ground_truth 非空的子集上计算。

```
Classifier Accuracy = COUNT(MP WHERE predicted_category = ground_truth_category) 
                    / COUNT(MP WHERE ground_truth_category IS NOT NULL)
```

Other Misroute Rate: `auto_category = 'Other'` 的请求中, 描述文本里实际含有强关键词 (pothole, streetlight, graffiti, trash, noise, tree) 的占比。这个指标对应问题一。

```
Other Misroute Rate = COUNT(SR WHERE auto_category='Other' AND description matches keyword)
                    / COUNT(SR WHERE auto_category='Other')
```

Council Escalation Rate: 一段时间内 created 的 SR 中, 60 天内生成 citizen_complaints 记录的占比。

```
Council Escalation Rate = COUNT(SR WHERE has_complaint_within_60d) / COUNT(SR created_in_period)
```

ARR per Tenant: 每个 tenant 的当期 ARR, 来自 tenant_subscriptions 表当前 active 合同的 arr_usd 求和。

```
ARR per Tenant = SUM(tenant_subscriptions.arr_usd WHERE is_active = 1)
```

NRR (Net Revenue Retention, 月口径): 当月 active 客户中, 12 个月前也 active 的子集的 ARR 变动比。

```
NRR_t = SUM(ARR_t for tenants active at both t and t-12m) 
      / SUM(ARR_{t-12m} for same tenants)
```

NPS Proxy: tenant_health_snapshots 月度快照里的 nps_score, 范围 -100 到 +100。本数据集没有真实 NPS 调研, 我们用"该月该 tenant 的 SLA breach rate, council escalation rate, reopen rate" 复合反推出一个 proxy 分, 由 generator 计算后写入快照表, 当作真实 NPS 用就好。

All metrics 默认按 `REFERENCE_DATE = 2026-06-01` 为锚点。"trailing 12 months"指 2025-06-01 到 2026-05-31; "current quarter"指 2026-04-01 到 2026-06-30; "prior quarter"指 2026-01-01 到 2026-03-31。
