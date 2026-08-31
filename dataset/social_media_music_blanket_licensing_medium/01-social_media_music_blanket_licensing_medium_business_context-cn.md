# 社交媒体 — 短视频平台音乐打包授权与合规稽核 业务背景

> 本文档是 `social_media_music_blanket_licensing_medium` 数据集的业务背景说明，负责回答"这是一家什么公司、做什么生意、要解决什么问题"。数据结构请见 `02-social_media_music_blanket_licensing_medium_er_document-cn.md`，SQL 查询请见 `03-social_media_music_blanket_licensing_medium_sql_queries-cn.md`。
>
> 读者设定：你是一个刚加入项目的聪明新人，不需要懂音乐版权或社交媒体产品。读完本文档，你应该能在第一次站会上跟同事聊清楚这家公司的业务、行业和这次分析要回答的问题。

---

## 1. 公司画像

**ReelWave, Inc.** 是一家总部位于加州旧金山的虚构北美短视频社交平台公司，2018 年成立，产品形态类似"竖屏刷视频"的社交 App。用户免费刷视频、免费社交，公司靠广告变现——用户是产品，广告主才是客户。

公司画像（数量级，非精确值）：

- **用户规模：** 美国和加拿大月活跃用户 (MAU) 约 8500 万。
- **收入：** 年广告收入约 19 亿美元。
- **员工：** 约 3200 人。
- **本数据集聚焦的业务线：** 公司内部叫 **"Sounds"** 的音乐功能团队，隶属于 Content Partnerships（内容合作）与 Label Relations（厂牌关系）组织之下。这个团队干两件事：一是和唱片厂牌签**打包授权 (blanket license)** 合同，换取平台整个"Sounds"曲库的合法使用权；二是运营 **Creator Fund（创作者基金）**，把一部分收入分给靠原创"声音"（用户自制的 remix/混音）带火视频的普通创作者。
- **地域：** 平台面向美加两国用户，签约的唱片厂牌和聚合发行商（label aggregator）总部同样以美加为主。

公司里和本次分析相关的角色（SQL 查询会按头衔点名这些人）：

| 头衔 | 中文 | 关心什么 |
|------|------|----------|
| General Counsel | 法务总顾问 | 打包授权合同的整体法律风险敞口，尤其是可能被追溯索赔的合同违约 |
| Head of Label Relations | 厂牌关系负责人 | 20 家厂牌打包授权组合的整体谈判策略、续约优先级 |
| Director of Rights Compliance | 版权合规总监 | 稽核政策制定、合规风险升级、向法务和财务汇报敞口 |
| Rights & Licensing Compliance Officer | 版权与授权合规专员 | 本数据集的**主视角**——具体稽核每份合同、每条 UGC 采样标记、每周 Creator Fund 分账是否合规 |
| Creator Fund Program Manager | Creator Fund 项目经理 | Creator Fund 分账公式、创作者体验、头部创作者留存 |
| VP of Finance (FP&A) | 财务规划与分析副总裁 | 打包授权总支出、合规风险敞口对应的潜在追溯赔付金额 |

---

## 2. 商业模式

ReelWave 赚钱靠广告，但它旗下的"Sounds"音乐功能团队本身不直接赚钱——它管理的是一项**必要的合规成本兼产品护城河**：平台上绝大多数爆款视频都配有背景音乐或声音，如果这些音乐没有合法授权，公司随时可能面临版权方的侵权诉讼。

这门"生意"的运作方式是：

1. ReelWave 和唱片厂牌（或代表多个独立厂牌的**聚合发行商, label aggregator**）签订**打包授权合同 (blanket license agreement)**——不是一首歌一首歌地谈价，而是花一笔**固定年费 (annual license fee)**，换取该厂牌**整个曲库的录音母带 (master recording)** 在平台上被合法使用的权利：无论是完整播放，还是把**原封不动的**曲目整段配进用户视频，都被这份母带打包授权覆盖。
2. 这笔年费在签约时是根据一个**曲库使用份额假设 (usage share assumption)** 谈出来的——也就是"我们预计你的曲库大概占平台音乐类视频总播放量的多少百分比"。份额假设越高，年费通常也越高。
3. 问题在于：合同一旦签下通常锁定 2 到 3 年，年费在合同期内基本不变，但曲库的**实际使用份额会随时间漂移**——某个厂牌旗下歌曲可能因为一场 TikTok 式挑战赛突然爆红，实际使用份额远超当初签约时的假设；也可能因为热度消退，实际份额远低于假设。年费却没有跟着重新谈。
4. 但打包授权只覆盖"原封不动地使用母带"。用户自己制作的 **remix（混音/二创声音）** 一旦**采样 (sample)** 了某首官方曲目的片段并做了变速、变调、切片、混音等改动，就创造了一个**衍生作品 (derivative work)**——这会触及母带打包授权**通常不覆盖**的两块权利：衍生作品的改编权，以及词曲**publishing（出版/作曲）**那一侧的权利；被采样的对象也可能**根本不在任何当前合同覆盖范围内**（艺人已离开厂牌、曲目不在合同窗口内、或来自没签打包合同的厂牌）。因此，凡是没走完内部采样审批流程的 remix，都构成潜在的**未授权采样 (unauthorized sample)** 等版权冲突，需要进入人工稽核队列被标记、核实、处理。这正是"厂牌明明签了打包合同、平台却仍会因为一条 remix 惹上版权风险"的原因。
5. 对于用原创声音（自己写的旋律或人声，不基于任何官方曲目）带火视频的创作者，公司运营 **Creator Fund**：按周计算每个"声音"的播放量份额，从一个固定的周度资金池里按比例分钱。

所以这条业务线的核心矛盾是：**合同锁定的假设 vs 不断变化的现实**。年费假设一旦写进合同就很难反映真实情况，无论是厂牌的曲库热度、UGC 是否越权采样，还是 Creator Fund 的分账窗口切法，都存在"合同/规则跟不上真实使用情况"的结构性缺口——这正是版权合规专员需要靠数据主动发现的问题，而不是等厂牌或创作者投诉上门才知道。

---

## 3. 行业普及：短视频平台的音乐版权打包授权

如果你来自别的行业，这一节让你快速看懂这门生意。

**这个行业创造什么价值。** 短视频平台的核心内容形态离不开音乐——一段配了合适 BGM 的视频比静音视频更容易被完播、被转发。但平台不可能对亿万条用户视频里用到的每一首歌单独谈判付费，**打包授权 (blanket license)** 解决了这个规模问题：平台一次性拿下某个厂牌的整个曲库使用权，厂牌换来一笔可预期的固定收入，用户则可以在创作时"随便挑歌"而不用操心版权。

**主要玩家类别（不点名真实公司）。**

- **唱片厂牌 (record label)：** 拥有歌曲录音版权的公司，从大型跨国厂牌 (major label) 到区域性中型厂牌 (mid-size label) 不等。
- **聚合发行商 (label aggregator)：** 代表一批独立音乐人或小厂牌统一对外授权的中间商，本数据集里归为 **indie aggregator** 类别。
- **短视频平台 (short-video platform)：** 像 ReelWave 这样的产品，既是曲库的使用方，也是打包授权年费和 Creator Fund 的付款方。
- **创作者 (creator)：** 在平台上发布视频的普通用户，其中一部分靠自制的原创"声音"或 remix 带来大量播放，可能有资格拿 Creator Fund 分成。

**监管与合规框架（北美）。** 音乐版权在美国主要受《版权法》(Copyright Act) 和法院判例里的"合理使用" (fair use) 边界约束，虽然没有一个专门盯着短视频平台的联邦监管机构，但几类框架仍然构成合规底线：

- **著作权侵权责任：** 未经授权使用受版权保护的录音或词曲构成侵权，版权方可以起诉索赔，这是"打包授权"存在的根本原因。
- **DMCA (Digital Millennium Copyright Act)：** 平台对用户上传内容的"避风港"保护以及配套的通知-删除 (notice-and-takedown) 义务。
- **合同法下的最惠国条款 (Most-Favored-Nation, MFN)：** 很多打包授权合同会写入 MFN 条款——如果平台后来给了别的厂牌更好的条件，这份合同也要跟着调整，这是本数据集陷阱之一的合同基础。
- **平台创作者收益分配的行业惯例：** 虽然没有强制法规，但创作者基金 (creator fund) 类项目的分账透明度已经成为舆论和监管都在关注的议题。

**当下的宏观力量。** 短视频驱动的"洗脑神曲"现象让曲库热度变化极快——一首歌可能在两周内从籍籍无名变成平台霸榜声音，也可能同样迅速地过气；平台之间为了抢占独家或优先曲库使用权，正在给新兴聚合发行商开出越来越激进的价格，这直接冲击了老牌厂牌当初签约时谈下的 MFN 保护条款是否还被真正遵守；与此同时，UGC remix 的爆发式增长让"到底谁在合法使用谁的版权"变得比以往任何时候都难追踪。

---

## 4. 项目框架：你在做什么

你是 ReelWave **Rights & Licensing Compliance（版权与授权合规）团队** 新入职的 **Rights & Licensing Compliance Officer（版权与授权合规专员，即第 1 节表格里标注的本数据集主视角）**，直接向 **Director of Rights Compliance** 汇报，产出结果会被同时呈给 **General Counsel** 和 **VP of Finance (FP&A)**。

在你之前，"Sounds"团队一直靠厂牌关系经理的个人经验和零散的 Excel 表格判断合同是否划算、UGC 是否合规、Creator Fund 是否公平——没有人系统性地把打包授权合同条款、月度曲库使用数据、UGC 采样标记和 Creator Fund 分账记录放在一起交叉核查过。Director 交给你的任务，是赶在下一轮厂牌续约谈判开始前，用 SQL 把这几块数据打通，产出一份**季度打包授权合规与风险稽核报告 (Quarterly Blanket License Compliance & Risk Report)**，直接支撑续约谈判策略、UGC 合规整改优先级和 Creator Fund 分账规则调整。

所有分析都锚定固定参考日 **REFERENCE_DATE = 2026-06-30**（详见第 6 节）。

---

## 5. 本项目要解决的业务问题

整个数据集是为回答下面四个核心业务问题而设计的。每个问题都在 ER 文档里有对应的数据陷阱，并在 SQL 查询文档里有对应的查询。

1. **Q1 曲库使用份额漂移 (Usage-Share Drift)：** 哪些厂牌的曲库**实际使用份额**已经严重偏离签约时写进合同的**份额假设**，导致年费和真实使用价值明显不匹配？偏离方向是"平台占了便宜"还是"厂牌被亏待了"？
2. **Q2 UGC 未授权采样合规稽核 (Unauthorized-Sample Compliance)：** 有多少条被标记的 UGC remix 采样冲突，已经超过公司内部约定的处理时限 (SLA) 还没解决？这部分悬而未决的曲目背后牵扯多少广告收入敞口？
3. **Q3 Creator Fund 热度快照错位 (Weekly Snapshot Misalignment)：** Creator Fund 按自然周结算的分账逻辑，是否系统性低估了那些"爆火窗口跨越了两个自然周"的声音应得的分成？
4. **Q4 MFN 条款合规稽核 (MFN Clause Compliance)：** 有没有受最惠国条款 (MFN) 保护的厂牌，实际拿到的"每 1 个使用份额百分点对应的年费"比后来签约、没有 MFN 保护的厂牌还低？这意味着公司可能正在违反合同，面临追溯索赔风险。

除了这四个 marquee 问题，数据集还支持一批运营类分析：厂牌组合结构、曲库释放节奏、创作者构成、季度性趋势等，用来回答日常运营和组合管理的问题。

---

## 6. 数据范围概览

- **时间跨度：** 曲库月度使用数据覆盖 18 个月（2025-01 至 2026-06）；Creator Fund 按周分账数据覆盖最近约 12 个月；曲库使用份额漂移、UGC 合规标记、MFN 条款合规都是基于这些历史数据在固定参考日做的一次快照分析。所有"今天/当前快照"的语义都锚定到固定参考日 **REFERENCE_DATE = 2026-06-30**。
- **数据量（数量级，白话）：** 20 家签约厂牌（3 家大型厂牌、7 家中型厂牌、10 家独立聚合发行商）、约 600 个被追踪的"Sounds"（400 首官方曲目 + 200 个创作者自制 remix/原创声音）、约 150 位有 Creator Fund 资格的创作者、约 9,700 行月度曲库使用记录、约 8,800 行 Creator Fund 周度分账记录、约 5,400 行针对 120 个"热门候选声音"的每日精细化使用记录，合计约 2.5 万行。
- **刻意的范围取舍：**
  - **只覆盖打包授权曲库，不覆盖单曲 sync 授权：** ReelWave 另有单独的团队处理广告/影视的单曲同步授权 (sync licensing)，本数据集不涉及，避免两种完全不同的授权逻辑混在一起。
  - **每家厂牌只建模当前生效的一份合同：** 不追踪历史上已到期的旧合同，聚焦"当前生效组合"是否合规这一实际决策场景。
  - **Creator Fund 只覆盖 UGC remix/原创声音，不覆盖官方曲目：** 官方曲目的收益已经通过打包授权年费覆盖，不会重复计入 Creator Fund。

（本节不列具体表；表结构见 ER 文档。）

---

## 7. 行业知识科普

外行看懂这份数据前，需要的大约半小时背景。建议按"一份打包授权合同的一生"来理解。

**1) 打包授权合同的三个关键条款。**

```
曲库使用份额假设 (usage share assumption) → 年费 (annual license fee) → MFN 条款 (可选)
```

- **曲库使用份额假设：** 签约时，双方对"这个厂牌的曲库未来大概会占平台音乐类视频总播放量的百分之多少"做出的估计，通常基于该厂牌过去的热度和知名度。
- **年费：** 基于份额假设谈出来的固定年费，合同期内（通常 2-3 年）基本不变。可以反推出一个**有效费率 (effective rate)**：年费 ÷ 份额假设百分点，即"每拿下 1 个百分点的曲库使用份额，平台愿意付多少钱"。
- **MFN 条款：** 部分合同（通常是大型厂牌才有议价能力谈到）会写明——如果平台之后跟任何其他厂牌达成了更高的有效费率，这份合同的费率也要跟着上调到不低于新的水平。这是大厂牌保护自己不被"后来者用更好条件插队"的手段。

**2) 曲库使用份额是怎么算的。** 每个月，平台上所有官方曲目、以及采样了某首官方曲目的 UGC remix 产生的视频播放量，会被归属到对应的厂牌名下。某厂牌当月的使用份额 = 归属给它的视频量 ÷ 所有可归属厂牌的视频量总和 × 100%。这个份额会随时间波动——一首歌爆红，份额就涨；热度消退，份额就跌。**签约时的份额假设只是一个静态快照，不会随实际使用情况自动更新。**

**3) UGC remix 与采样。** 用户可以基于一首官方曲目做二次创作（截取片段、加速、混入其他音效），这叫 **remix**，其中截取/使用了原曲片段的行为叫 **采样 (sampling)**。平台有内部审批流程判断一次采样是否走了合规授权路径；没走完流程或明显越界的，会被标记为**未授权采样 (unauthorized sample)** 等**版权冲突 (rights conflict)**，需要在内部约定的时限 (SLA) 内完成稽核处理（澄清、追溯补授权，或下架）。

这里有一个容易被忽视的关键点：打包授权买断的是"**原封不动地播放/嵌入母带**"的权利，而 remix 采样做了改动、构成衍生作品，落在母带授权覆盖不到的灰区，所以即便原曲来自已签约厂牌，采样仍需单独清权。此外，平台绝大多数音频匹配是在视频上传时靠**指纹自动识别 (audio fingerprinting)** 实时完成的，本数据集的 `rights_conflict_flag` 表记录的只是自动识别拿不准、需要**人工升级稽核**的那部分争议残差——这也是为什么它的记录数（几十条）远小于平台海量视频的总量。

**4) Creator Fund 的按周分账逻辑。** Creator Fund 是一个每周有固定预算的资金池，按各个参与声音当周的播放量占比来分钱——播放量占比越高，当周分到的钱越多。这个机制的隐含假设是"一首歌的爆火过程会完整地落在某一个自然周里"，但现实中一段视频可能在周四开始发酵、周六达到峰值、周日到下周一还在持续传播——**爆火窗口横跨两个自然周**，导致这首声音在任何一周单独看都不算"当周最火"，实际能分到的钱会比它本该拿到的更少。

**5) 有效费率与 MFN 稽核的算法。** 判断 MFN 条款有没有被违反，核心是把每份合同的**有效费率**（年费 ÷ 份额假设）都算出来，然后检查：任何一份带 MFN 保护的合同，它的有效费率有没有低于**没有 MFN 保护**的合同里最高的那个有效费率。如果低于，就说明平台应该把这份 MFN 合同的费率上调到与最高值持平，却一直没有调整——这构成合同违约，且违约期越长，追溯索赔的金额敞口越大。

---

## 8. 术语表

每个在 ER 文档或 SQL 查询里出现的 jargon，这里给一句白话解释，外加"在本项目里为什么重要"。术语一律保留英文形式。

| 术语 | 白话解释 | 在本项目里为什么重要 |
|------|----------|----------------------|
| Blanket license | 打包授权，一次性买断某个厂牌整个曲库的使用权，而非逐曲谈判 | `label_blanket_license` 表的核心业务对象 |
| Usage share assumption | 曲库使用份额假设，签约时对未来实际使用占比的估计 | 陷阱 1 和陷阱 4 的共同输入变量 |
| Effective rate | 有效费率，年费除以份额假设，即"每 1 个份额百分点付多少钱" | 陷阱 4（MFN 合规）的核心计算 |
| MFN (Most-Favored-Nation) clause | 最惠国条款，保证自己拿到的条件不比别人差 | 陷阱 4 的合同基础 |
| Label aggregator | 聚合发行商，代表多个独立音乐人/小厂牌统一授权的中间商 | `label` 表里 indie_aggregator 类别 |
| Sound | ReelWave 平台内对"一段可被视频使用的音乐素材"的统称，包含官方曲目和用户 remix | `sound` 表的核心实体 |
| Official track | 官方曲目，厂牌拥有版权、通过打包授权覆盖的完整歌曲 | `sound.sound_type = official_track` |
| UGC remix | 用户自制的二次创作声音（混音/二创），可能基于官方曲目采样，也可能完全原创 | `sound.sound_type = ugc_remix`，陷阱 2/3 的核心对象 |
| Sampling | 采样，UGC remix 截取/使用官方曲目片段的行为 | 决定是否需要走版权审批 |
| Rights conflict | 版权冲突，remix 采样了母带打包授权覆盖不到的内容（衍生改编、publishing 侧、或不在合同内的曲目），需进入人工升级稽核队列 | `rights_conflict_flag` 表，陷阱 2 的核心 |
| SLA (Service-Level Agreement) | 服务水平约定，这里指版权冲突从标记到必须处理完毕的内部时限 | 判断陷阱 2 是否"逾期"的基准 |
| Revenue at risk | 风险敞口收入，某条有版权冲突的 remix 相关联的广告收入估算 | 衡量陷阱 2 的财务后果（保守的广告收入代理值，非法定赔偿口径） |
| Creator Fund | 创作者基金，平台按周分给热门原创声音创作者的固定预算资金池 | `creator_fund_weekly_payout` 表 |
| Trending snapshot / snapshot week | 热度快照周，Creator Fund 按自然周（周一至周日）计算分账的时间粒度 | 陷阱 3 的分账周期定义 |
| Viral spike window | 爆火窗口，一段声音播放量集中暴涨的连续几天 | 陷阱 3 里和快照周对比的"真实"热度窗口 |
| Spike week alignment | 爆火窗口对齐状态：完整落在一周内 (aligned) 还是跨周 (split_across_weeks) | `sound` 表字段，直接驱动陷阱 3 的分账差异 |
| MAU (Monthly Active Users) | 月活跃用户数 | 描述平台规模的常用指标 |

---

## 9. 关键指标与公式

下面是 SQL 查询里用到、或读者应当知道的指标。公式用通俗记法（SQL 风格伪代码），并注明输入和口径约定。

**曲库使用份额漂移（陷阱 1）**

```
label_month_videos(label, month) = SUM(sound_monthly_usage.video_count)
    WHERE sound.primary_label_id = label OR sound.source_sound_id IN (label 名下官方曲目)
      AND sound_monthly_usage.usage_month = month
labeled_total_videos(month) = SUM(label_month_videos) 跨全部 20 家厂牌
usage_share_pct(label, month) = label_month_videos(label, month) / labeled_total_videos(month) * 100
usage_share_drift_pp(label) = 最近 3 个月 usage_share_pct 均值 − label_blanket_license.usage_share_assumption_pct
```

**有效费率与 MFN 合规（陷阱 4）**

```
effective_rate_per_point(label) = label_blanket_license.annual_license_fee_usd / label_blanket_license.usage_share_assumption_pct
max_non_mfn_rate = MAX(effective_rate_per_point) WHERE has_mfn_clause = FALSE
mfn_breach(label) = has_mfn_clause = TRUE AND effective_rate_per_point(label) < max_non_mfn_rate
mfn_breach_exposure_usd(label) = (max_non_mfn_rate − effective_rate_per_point(label)) × usage_share_assumption_pct   -- 仅对 mfn_breach = TRUE 的厂牌计算
```

**UGC 未授权采样合规稽核（陷阱 2）**

```
is_overdue(flag) =
    (resolution_status IN ('open', 'under_review') AND (REFERENCE_DATE − flagged_date) > sla_days_target)
    OR (resolved_date IS NOT NULL AND (resolved_date − flagged_date) > sla_days_target)
open_revenue_at_risk_usd = SUM(revenue_at_risk_usd) WHERE resolution_status IN ('open', 'under_review')
```

**Creator Fund 热度快照错位（陷阱 3）**

```
payout_rate_per_1000_views(group) = SUM(payout_usd) / SUM(weekly_view_count) × 1000
    按 sound.spike_week_alignment 分组 (aligned vs split_across_weeks)
underpayment_gap_pct = (payout_rate_per_1000_views(aligned) − payout_rate_per_1000_views(split_across_weeks))
    / payout_rate_per_1000_views(aligned) × 100
```

> **口径说明（避免下游 SQL 打架）：**
> - `usage_share_pct` 的分母 `labeled_total_videos` 只统计**能归属到某个厂牌**的视频量（官方曲目 + 采样了官方曲目的 remix），完全原创、不采样任何官方曲目的 UGC 声音不计入这个分母，因为它们不受任何打包授权合同覆盖。
> - `effective_rate_per_point` 用**签约时的份额假设**而不是当前实际份额计算，因为合同年费本来就是按签约时的假设谈定的——这正是陷阱 1 和陷阱 4 分别关注"假设 vs 实际用量"和"假设 vs 合同费率公平性"两个不同角度的原因。
> - `is_overdue` 对已解决 (resolved) 和仍未解决 (open/under_review) 的记录用不同的时间差计算方式，两者不能用同一个 `resolved_date` 字段统一处理，因为未解决的记录 `resolved_date` 为空。
> - **两个"收入敞口"切面不要混为一谈**：`open_revenue_at_risk_usd`（上面这条公式）只统计**仍未解决**（`open` / `under_review`）的标记，量级约 14 万美元，回答"现在还悬在手上、随时可能被追责的敞口有多大"；而 SQL Query 6 汇总的是**逾期集合**（仍未解决且已超期 + 已解决但处理超时，两类相加）的 `revenue_at_risk_usd`，量级约 21 万美元，回答"历史上处理超时、暴露过法律风险的敞口有多大"。两个数都对，但口径不同（一个按"是否已解决"切，一个按"是否超时"切），报告里引用时务必写清是哪一个切面，避免读者以为它们是同一个数。
> - **`revenue_at_risk_usd` 是保守的下限代理值，不等于真实法律敞口。** 它只估算涉事 remix 关联视频赚到的广告收入（并与该 remix 的热度正相关：越火的越高）。但在美国版权法下，真正驱动法律风险的是**法定赔偿 (statutory damages, 17 U.S.C. §504)**——故意侵权每件最高可达 15 万美元——外加禁令和判例风险，这些才是 General Counsel 真正紧张的部分。所以报告里引用这个 21 万 / 14 万美元时，要说明它衡量的是"广告收入敞口"，而非"潜在赔付金额"；真实敞口在法定赔偿的长尾里，通常远高于这个代理值。
> - `spike_week_alignment` 只在 `sound.is_trending_monitored = TRUE` 的 120 个热门候选声音上有意义；其余声音没有做每日精细化追踪，无法判断爆火窗口是否跨周。
