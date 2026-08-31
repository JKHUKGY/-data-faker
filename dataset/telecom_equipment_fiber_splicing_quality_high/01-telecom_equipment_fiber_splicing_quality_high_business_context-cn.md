# 光纤焊接质量与成本控制数据集业务背景

NorthArc Photonics Manufacturing 是一家位于俄勒冈 Hillsboro 的光纤连接器制造商, 主营预制端接 (pre-terminated) 光跳线和 MTP trunk cable. 2014 年从 Intel 的光学组件部门拆分独立, 现在大约 250 人, FY 2025 营收 $80M USD. 公司在 Hillsboro 拥有一座 14,000 平方英尺的洁净度 Class 10K 装配厂, 厂里 12 台 fusion splicer 三班制运转, 30 名 splice operator 加上 8 名 QA 工程师, 是整个生产瓶颈所在.

你刚加入这家公司 6 个月, 头衔是 Senior Manufacturing Analyst, 直接向 VP of Operations 汇报 (Marcus Reed, 之前在 Corning 做了 15 年). CFO Linda Chen 今年初拍下一个 $1.2M 的成本压缩 KPI, 因为最大的几个 datacenter 客户 (代号 DC-Alpha, DC-Bravo, 你在这里看到的客户都用代号) 把单价压了 8%, 而你们的 splice 工序良率最近两个季度肉眼可见地下滑. Marcus 把第一个动作交给了你, 项目名叫 Phase 1 Operations Cost Take-Out Plan, 截止日期是 Q3 末. 交付物是一份给 CFO 和 COO 的 recommendation memo 加一个跑在 Tableau 上的实时 dashboard, 要拿出至少 $700K 的年化节约空间.

整个数据集就是为这个项目准备的. 它包含过去 12 个月 (2025-06 到 2026-06) Hillsboro 工厂的所有焊接生产数据, 锚定在 REFERENCE_DATE = 2026-06-15. 你要在这堆数据里找钱.

---

## 1. NorthArc Photonics 这家公司

公司只做一件事: 把光纤 (optical fiber) 跟连接器 (connector) 组装成一根一根可以即插即用的成品 cable, 卖给三类客户. 不做光纤拉丝 (那是 Corning, Sumitomo 在做), 也不做有源光器件 (那是 Lumentum, Coherent 在做). NorthArc 干的就是中间那段, 业内叫 cable assembly. 听起来不复杂, 但 splice loss (焊接损耗) 这个指标必须卡到客户的 spec 内, 否则整条 cable 报废. 这就是为什么质量数据这么重要.

工厂的组织结构很扁:

```
CEO (David Park)
 ├── VP Operations (Marcus Reed)         ← 你的老板
 │    ├── Production Manager (Sarah Klein)
 │    │    ├── Day Shift Lead
 │    │    ├── Swing Shift Lead
 │    │    └── Night Shift Lead
 │    ├── Manufacturing Analytics (你所在的位置, 1 人)
 │    └── QA Engineering Manager (Tom Vasquez)
 ├── VP Engineering (Priya Shah)
 ├── CFO (Linda Chen)
 └── VP Sales (Jorge Ramirez)
```

Marcus 给你的指令很直接: 数据应该证明工厂哪里在漏钱, 不要写学术报告. 每一条结论后面要跟一个动作和一个金额.

---

## 2. 商业模式与单位经济学

NorthArc 卖的不是数据中心方案, 是 piece part. 一根 12-fiber MTP-MTP trunk cable 比如标价 $48, 一根 LC duplex FTTH drop cable 比如标价 $7. 客户按 PO 一次性下单, 数量从几百根到几万根不等. 没有订阅, 没有 take-rate, 商业模式纯粹是制造业 unit economics.

毛利结构大致这样 (按一根 12F MTP trunk 举例):

```
售价 (ASP)                    $48.00
   光纤物料                    $11.00   23%
   连接器 + 套管                $9.00   19%
   人工 (焊接 + 测试 + 包装)     $7.50   16%
   设备折旧 + 电费 + 耗材        $3.20    7%
   返工 + 报废 (rework cost)    $4.10    9%   ← 你要砍的就是这一块
   间接费用 (管理 + 厂房)         $5.20   11%
毛利                           $8.00   17%
```

数据中心客户 (占营收 55%) 单价压最狠但量最大. FTTH 运营商 (占营收 30%) 价格 OK 但 spec 宽松. 企业网客户 (占营收 15%) 量小但单价高. 每个客户群的 splice loss 容忍度差很多, 后面 Q5 会展开讲.

公司的 contribution margin 大约 35%. CFO 想拿掉的 $1.2M 来自 cost-of-goods 这一栏 (而不是从 SG&A 砍人), 因为 SG&A 上几乎砍无可砍, 制造成本里那 9% 的 rework cost 才是肥肉. 9% 在行业里偏高 (一流厂能压到 4 到 5%), 这给项目留出了量化空间.

---

## 3. 行业概览, 光纤连接器制造

光纤连接器制造是整个 telecom infrastructure 价值链里一个不起眼但稳定的环节. 全球市场大概 $4B USD, 北美占 $1.2B, 增速跟着 hyperscale datacenter 和 FTTH buildout 走, 这两年因为 AI cluster 的光互联需求 (400G, 800G optics) 又有一波加速.

主要玩家分四类. 第一梯队是 OEM 综合厂 (公司不点名, 你只要知道有那种营收 $500M 以上, 自己拉光纤自己做组件的). 第二梯队是 contract manufacturer (NorthArc 在这里). 第三梯队是大的 distributor 自己组装 (CDW, Anixter 那类). 第四梯队是亚洲来的低成本工厂, 卖给 SMB 和 Amazon Marketplace, 质量参差.

监管层面, 北美这个细分行业相对轻量. 主要要符合的标准是 Telcordia GR-326 (FTTH connector 通用规范), IEC 61753 系列 (光纤性能 spec), 以及 IPC-A-610 (装配工艺). 客户审计远比政府检查严, hyperscale 客户每年来 source audit 一次, 看你的 SPC chart (statistical process control), 看你的 first-pass yield, 看你的 calibration log. 一次 audit 发现批量质量问题, 可能直接被踢出 AVL (approved vendor list).

行业最近三年的几个宏观动力: (1) AI 训练集群把数据中心内的光纤密度推高了一个数量级, MPO/MTP 高密度连接器需求暴涨; (2) FTTH 各州的 BEAD program 联邦补贴让运营商在拉小镇宽带, FTTH drop cable 量大了但单价被压扁; (3) labor 成本上涨, 尤其熟练 splice operator 的小时工资从 2020 年的 $22 涨到了现在的 $31; (4) hyperscale 客户在推 Total Cost of Ownership 谈判, 你不能再光卖一根 cable 了, 要绑 SLA, 要绑 RMA (return material authorization) 周转, 要绑 traceability.

---

## 4. 你的角色和这个项目

你的 title 是 Senior Manufacturing Analyst, 公司里只有你一个 manufacturing analyst. 这是一个看起来初级实际上责任极大的位置. 你的工作是把生产线产生的数据翻译成 dollar number, 告诉 Marcus 哪里在亏钱.

你之前在 Intel 做 yield engineering, 懂 wafer fab 的 SPC 那一套, 但光纤焊接对你是新东西, 入职后花了三周泡在产线上看 operator 怎么干活才搞明白. 这份业务背景的术语表就是你给自己整理的备忘录.

Phase 1 项目的范围:

第一步, 摸清楚现状. 用 12 个月的生产数据画出 splice loss 分布, reject rate 趋势, 各台设备 / 各班次 / 各操作员 / 各 fiber batch / 各客户订单 spec 的良率差异. 这一步是数据探索.

第二步, 找到八个最大的成本黑洞. Marcus 给你列了八个他从一线收到的怀疑 (你会在下一节看到), 让你用数据证实或证伪, 并给出量化的年化损失.

第三步, 给每个被证实的黑洞配一个动作建议, 估算 ROI, 排序. 例如 "在所有 fusion splicer 上把电极更换从故障触发改为每 1800 次主动更换, 一次性投入 $X, 年节约 $Y, ROI 8 个月" 这种结论.

第四步, 把上面的结论写成一份 12 页 memo 给 CFO, 配一个 Tableau dashboard 给 Production Manager 日常用.

时间表: 你拿到数据是 2026 年 6 月初, memo 必须在 9 月末交. 这个数据集就是第一步和第二步的数据底座.

---

## 5. 项目要回答的八个业务问题

Marcus 在 kickoff 会上拍给你的八个 hypothesis. 每一个都要回答 yes 或 no, 加一个 dollar number. 这八个问题贯穿后面的 SQL queries 文档.

**Q1. 总览, 钱漏在哪里**
过去 12 个月, 按 fiscal year 的口径, splice 工序的总 reject cost 是多少? 按 reject 的根因 (电极磨损 / 设备校准超期 / 操作员错配 / 批次质量 / 班次差异 / 过度 spec / 告警被忽视 / 多次重试) 拆解, 各占多少 dollar?

**Q2. 电极更换策略**
现在工厂的 electrode replacement 策略是 reactive (出告警才换). 数据上能不能证明 "splice count > 2000 后 reject 率显著上升"? 如果改成 condition-based preventive replacement (每 1800 次主动换), 年化节约多少?

**Q3. 夜班质量恶化**
车间反馈说夜班 reject 多. 数据上各班次的 reject rate 差多少? 如果每晚加一个 $80K 年薪的 floating senior supervisor, 能挽回多少 reject cost?

**Q4. Multi-core 焊接的人才错配**
multi-core fiber (用于 400G / 800G optics) 比 single-core 难焊得多, 但当前排班是不分技能等级随机分配. 各 skill level 操作员在 multi-core 上的 reject rate 差多少? 限制 multi-core 仅由 senior 以上做, 年化节约多少?

**Q5. 过度质量, FTTH 订单的 spec 松绑机会**
内部 SOP 把所有 splice 都按最严的 0.05 dB 阈值判 reject. 但 FTTH 客户的实际 spec 是 0.30 dB, 等于把大量在客户那里合格的产品当废品扔了. 如果按客户订单的 actual spec 动态判, 每月能少返工多少根?

**Q6. AI 告警被忽视的下游影响**
工厂去年上了一套 splice loss 预测 + alert 系统. 告警出来后 operator 可以选择重做 / 调参 / 忽视. 被 ignored 的告警, 下游 reject rate 是多少? 强制执行告警建议 (系统硬拦截) 的年化节约?

**Q7. 设备校准超期**
现在的校准 SOP 是每 90 天一次, 但实际执行不严格, 大约 30% 设备超期. 校准超期 vs 在期的 reject rate 差多少? 把 SOP 改成 60 天一次, 年化节约多少?

**Q8. 召回风险, 坏批次 MFG-2024-038**
QA 上周报告一个批次怀疑 cladding 直径方差异常. 这个批次的 reject rate 实际是多少? 已经交付出去多少根? 收到了几条客户投诉? 是不是要发 customer notification 启动召回?

每一个 Q 都对应数据集里实际埋下的 distribution 偏置 (后面 ER 文档的 "业务陷阱" 一节会列出 expected magnitude), SQL queries 文档会用 2 到 3 条查询把每个 Q 的答案跑出来.

---

## 6. 数据范围

时间窗口: 2025-06-16 到 2026-06-15, 整整 12 个月. REFERENCE_DATE 锚定 2026-06-15, 这一天是项目数据冻结点. 所有 SQL queries 里的 "距今", "最近 30 天" 都以这一天为基准.

地理范围: 仅 Hillsboro 工厂. 公司在 Phoenix 还有一个小厂只做 packaging, 不在本数据集里.

业务范围: 仅 fusion splicing 工序. 上游的连接器抛光 (polishing) 和下游的成品测试 (insertion loss test, return loss test) 工序不在范围内. 项目 Phase 2 才会扩展过去.

数据量级: 18 张表, 总记录数约 22 万行. 主要的事实表 splice_record 约 5 万行 (每天约 140 次焊接, 12 个月), splice_attempt 约 5.5 万行 (大多数 splice 一次过, 部分要重试 2 到 3 次). 维度表小, 客户 12 个, 设备 12 台, 操作员 30 人.

特意排除掉的范围: 不包含 Phoenix 工厂数据 (太小); 不包含 polishing 和 testing 工序 (Phase 2 范围); 不包含人力资源敏感字段 (薪资明细只在 operator 表里有一个 hourly_rate, 没有奖金 / 绩效详细记录).

---

## 7. 三十分钟入门, 光纤焊接是怎么回事

如果你以前没接触过光纤制造, 这一节是你跟工厂的同事聊天前要掌握的最低限度知识. Marcus 第一周陪你下了一次车间, 这是他讲的版本.

### 光纤本身长什么样

一根光纤的核心是一根头发丝粗细 (直径约 250 微米) 的玻璃丝, 由三层组成. 最里面是 core (纤芯), 真正传光的部分, 单模光纤 core 直径只有 9 微米. 中间是 cladding (包层), 玻璃材质, 折射率比 core 低, 把光约束在 core 里, 标准直径 125 微米. 最外面是 coating (涂覆层), 高分子材料保护玻璃, 标准直径 245 微米. 制造商发货时光纤绕在直径 30 厘米的塑料卷盘上, 一卷叫一根 spool, 通常长 25 公里.

光纤的 spec 取决于型号. 最常见的是 G.652.D 单模光纤, 用于长距离传输. 数据中心高密度场景用 G.657.A1 抗弯曲单模, 弯曲半径更小. 多模光纤 OM4 和 OM5 用在短距离 (建筑内部). NorthArc 大约 70% 业务是单模, 30% 多模. 还有一类 multi-core fiber (4 芯, 7 芯), 用在 400G / 800G 高密度光模块里, 体量不大但单价高, 焊接难度也最高.

### Splicing 这个动作

fusion splicing 是把两根光纤的端面对齐后用电弧加热熔接成一根. 整个动作 90 秒到 3 分钟搞定, 步骤是:

1. 剥涂层. 用 stripper 工具把两根光纤末端 3 厘米的 coating 剥掉, 露出 125 微米的 cladding.
2. 清洁. 用蘸了异丙醇的 lint-free wipe 擦掉残留涂层屑.
3. 切割端面. 用 cleaver (机械切割刀) 切出一个垂直的端面. 切割角度必须在 0.5 度以内, 角度偏差直接影响焊接质量.
4. 放入 splicer. 把两根光纤放入 fusion splicer 的 V-groove (V 形槽) 里, 端面相对.
5. 自动对齐. splicer 内的相机系统 (CCD) 检测两根光纤的 core 偏移, 通过马达微调到 X / Y 方向偏移都小于 0.1 微米.
6. 预熔 (prefusion). 短暂的低能量电弧把端面的微小毛刺烧平.
7. 主电弧 (arc fuse). 高能量电弧 (~12.5 mW, 持续约 1 秒) 把两根光纤端面熔成一体.
8. 评估损耗. splicer 用 LID (Loss Estimation by Deformation) 算法基于熔接形态估算 splice loss, 单位 dB. 这个估算值就是 predicted_loss_db.
9. 焊后保护. 套上 splice protector (热缩管), 加热定型.

如果 predicted loss 超出阈值, splicer 会提示 retry, operator 决定是重新 cleave 后再焊, 还是接受当前结果. 一根 splice 允许最多 3 次 attempt, 第 3 次还不行就报 reject.

splice loss 这个指标决定一根 cable 是否合格. NorthArc 内部 SOP 把所有 splice 卡在 ≤ 0.05 dB. 单模光纤的世界级水平是 0.02 dB, 一般工厂水平 0.05 dB, FTTH 客户能接受到 0.30 dB.

### 影响 splice loss 的因素

按重要性大致排序:

| 因素 | 怎么影响 | 工厂能控制的程度 |
|------|---------|------------------|
| core 对齐误差 | 偏移 0.5 μm 就能让 loss 翻倍 | 高 (设备自动对齐, 但电极磨损会让对齐失稳) |
| 端面切割角度 | 超过 0.5° 增加散射 | 高 (取决于 cleaver 刀片新旧) |
| 电极状态 | 老化电极电弧不稳定, 熔接温度漂移 | 高 (主动更换策略) |
| 光纤 cladding 直径方差 | 来料批次问题, 偏差超过 ±0.5 μm 难对齐 | 中 (依赖供应商 QC) |
| 环境湿度 | > 60% 高湿端面易吸潮 | 中 (洁净室控制) |
| 操作员熟练度 | 剥涂层和清洁手法影响残留 | 中 (培训 + 排班) |
| 多核光纤难度 | 多个 core 同时对齐, 难度指数级上升 | 中 (技能匹配) |

每一个因素在数据集里都对应一个或多个字段, 你的 SQL 会去切分每个因素的贡献.

### 电极, 这个工厂里最便宜也最致命的零件

fusion splicer 里有一对 tungsten electrode (钨电极), 负责放出电弧. 一对电极 list price 大约 $180, 但寿命有限 (典型 1500 到 2500 次焊接), 因为电弧会蒸发钨, 表面会慢慢凹陷, 电场分布不再对称. 老化的电极会让电弧温度漂移, 直接拉高 splice loss.

NorthArc 现在的电极更换策略是 reactive: 等到 splicer 自检报告 "electrode condition warning" 才换. 问题是这个告警阈值是设备厂家设的, 通常等到电极已经磨损得很严重了才报. Marcus 怀疑工厂里相当一部分 reject 实际是电极磨损过度导致的隐性问题. 这就是 Q2 要回答的事.

---

## 8. 关键术语表

以下术语在 ER 文档和 SQL queries 里会反复出现.

**Splice Loss** (焊接损耗): 一次熔接造成的光功率衰减, 单位 dB. 0.02 dB 表示 99.5% 的光通过, 0.10 dB 表示 97.7% 通过. 在数据中心长距离链路里, 多次 splice 损耗会累加, 所以单次 splice loss 越低越好.

**dB** (Decibel, 分贝): 对数单位, 衡量光功率比. 直观换算: 0.1 dB ≈ 2.3% 功率损失, 0.5 dB ≈ 10.9% 损失, 1.0 dB ≈ 20.6% 损失. 数据集里的 loss 数值都是正数, 数值越大损耗越大.

**FTTH** (Fiber To The Home): 光纤入户. 运营商把光纤拉到家庭终端的 buildout 模式. spec 较宽松, 一段 drop cable 上的 splice 可以接受到 0.30 dB.

**Hyperscale Datacenter**: AWS, Google, Meta 这类超大规模数据中心运营商. 内部光纤连接密度极高, spec 极严, 单次 splice loss 通常要 ≤ 0.05 dB.

**MTP / MPO**: Multi-fiber Push-On 连接器, 一个连接头里塞 8 / 12 / 24 根光纤, 数据中心用得最多.

**LC** / **SC** / **FC**: 三种单纤 connector 形态. LC 体积最小, 现在主流; SC 老一点, 还在用; FC 工业场景用.

**Cleave Angle** (切割角度): 光纤端面跟轴线的垂直度偏差, 单位度. 标准 < 0.5°, 优秀 < 0.3°.

**Cladding** (包层): 光纤外层玻璃, 标准直径 125 微米.

**MFD** (Mode Field Diameter, 模场直径): 单模光纤里光场的有效直径, 标准约 10.4 微米. 不同型号 MFD 略有差异, 焊接 MFD 不匹配的两根光纤损耗会偏高.

**Cleaver**: 机械切割工具. 一片刀片寿命大约 24,000 次切割.

**Electrode** (电极): fusion splicer 里产生电弧的钨电极对. 寿命 1500 到 2500 次焊接.

**LID** (Loss Estimation by Deformation): splicer 内置的 splice loss 估算算法. 基于焊后光纤形变图像估算, 不是真实 OTDR 测量, 实际 loss 跟它有 ±0.005 dB 的偏差.

**OTDR** (Optical Time Domain Reflectometer): 真正测 splice loss 的仪器, 但贵且慢, 通常只在 QA 抽检时用, 不是每根都测.

**First-Pass Yield (FPY)**: 一次焊接成功的比例. NorthArc 当前约 88%, 行业一流约 95%.

**Reject Rate**: 一次 splice 经过最多 3 次 attempt 仍不合格的比例, 当前约 2.5%.

**Quality Grade**: 内部对 splice 的四档分类. A = loss ≤ 0.02 dB, B = ≤ 0.05 dB, C = ≤ 0.08 dB, Reject = > 0.08 dB.

**Splice Attempt**: 一次 splice 的单次尝试. 一根 splice_record 对应 1 到 3 个 splice_attempt.

**Job**: 一个生产批次, 对应一个客户 PO 的某个子任务. 一个 job 由一个 operator 在一台设备上完成, 内含几十到几百次 splice.

**SPC** (Statistical Process Control): 统计过程控制, 用 control chart 监控关键工艺参数.

**AVL** (Approved Vendor List): 客户认可的供应商名单. 一次重大质量问题可以让你出局.

**RMA** (Return Material Authorization): 退货授权. 客户退货前要拿到的批准号.

**SOP** (Standard Operating Procedure): 标准作业程序.

**BOM** (Bill of Materials): 物料清单. 数据集里 fiber_batch 和 consumable_price 提供 BOM cost.

---

## 9. 关键指标和公式

下列指标会在 dashboard 和 SQL queries 里反复出现. 选定的定义在这里说清楚, 避免下游计算不一致.

**First-Pass Yield (FPY)**

```
FPY = COUNT(splice_record WHERE attempt_count = 1 AND final_grade != 'Reject')
      / COUNT(splice_record)
```

口径只看 attempt_count = 1 且非 Reject 的, 即 "一次过且合格". NorthArc 当前 FPY 约 88%.

**Reject Rate**

```
Reject Rate = COUNT(splice_record WHERE final_grade = 'Reject')
              / COUNT(splice_record)
```

口径是最终 reject (3 次 attempt 都不行). 当前约 2.5%.

**Cost Per Splice (CPS)**

```
CPS = SUM(splice_attempt.material_cost_usd + labor_cost_usd 
          + machine_cost_usd + consumable_cost_usd)
      / COUNT(DISTINCT splice_record.splice_id)
```

每根 splice 的全成本均摊到 attempt 级, 然后按 splice_record 求平均. 注意分母不是 attempt 数, 因为一根 splice 多次重试不应让 unit cost 减半.

**Rework Cost Per Splice**

```
Rework Cost = SUM(splice_attempt.material_cost_usd + labor_cost_usd 
                  + machine_cost_usd + consumable_cost_usd
                  WHERE attempt_number > 1)
              / COUNT(splice_record)
```

第 2 次和第 3 次 attempt 的全部成本, 摊到所有 splice_record 上. 这是 Q1 的主表头.

**Annualized Loss Per Cost Driver**

```
Annualized Loss(driver) = (额外的 reject 数 + 额外的 retry 数)
                          * 单位成本
                          * (365 / 数据天数)
```

每个 Q (Q2 到 Q8) 都用这个口径估算"如果消除 driver X, 一年能省多少". 单位成本约 $13 per reject (物料 + 人工 + 设备折旧 + 客户失信风险摊销), $4 per retry (主要是物料 + 时间).

**Electrode Cost Per Splice**

```
Electrode Cost = electrode_pair_price_usd / electrode_lifetime_splices
```

按 $180 / 2000 ≈ $0.09 per splice 计入 consumable_cost_usd.

**Quality Grade Distribution**

```
Grade Mix = COUNT(quality_grade = X) / COUNT(*)
            for X in (A, B, C, Reject)
```

目标分布: A 75%, B 18%, C 4.5%, Reject 2.5%.

**AI Alert Compliance Rate**

```
Alert Compliance = COUNT(quality_alert WHERE outcome = 'resolved')
                   / COUNT(quality_alert WHERE outcome IS NOT NULL)
```

当前 ~75%, ignored ~15%, escalated ~10%. Q6 要把 ignored 那 15% 的下游损失算清楚.

**Equipment Electrode Count**

```
electrode_count_at_splice = COUNT(splice_attempt
                                  WHERE equipment_id = E
                                  AND attempt_ts BETWEEN last_replacement_ts AND splice_ts)
```

某次焊接发生时, 当前电极对已经服役多少次. 这是 Q2 的主要切分维度.

**Splice Loss Spec Compliance, By Customer**

```
Customer Spec Compliance = COUNT(final_loss_db <= order.loss_threshold_db)
                           / COUNT(*)
                           grouped by customer.segment
```

按客户订单的实际 spec 判, 而不是用内部 SOP 0.05. 这是 Q5 的核心口径.

每一个指标在 SQL queries 文档里都至少出现一次, 第 03 文档不会再重复定义.
