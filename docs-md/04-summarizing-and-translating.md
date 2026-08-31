# 定稿之后: 写一句话摘要, 再翻译成英文

[03-automating-review-and-fix.md](03-automating-review-and-fix.md) 里那个左右互搏循环跑完之后, 一份 dataset 的四份中文文件就算定稿冻结了. 但在它能进索引清单之前, 还有两件事要做: 给它浓缩一份一句话摘要 ([01-dataset-anatomy.md](01-dataset-anatomy.md) 里讲过, 这份摘要是核心规范的一部分, 但不归 fake-data-generator 管), 以及把中文产出物翻译成英文. 这两件事被合并成同一步, 由 [.claude/skills/run-summarize-and-translate](../.claude/skills/run-summarize-and-translate/SKILL.md) 这个 Skill 完成. 这一篇讲这一步的设计和取舍, 也就是 Why.

## 1. 为什么摘要和翻译是同一步

摘要和翻译看起来是两件事, 但它们的输入完全一样: 都是那几份定稿的 `-cn` 文件. 把它们合成一步, 是因为这一步里最贵的动作是**把整份 dataset 完整读一遍**, 而这个动作两件事都躲不开, 合起来做就只需要读一次.

翻译这一侧本来就需要先把所有文件通读一遍, 消化出一份 consistency brief — 也就是把虚构公司名, 产品名, 那些内嵌业务陷阱的术语, 已经是英文缩写的行话 (ARR, DSO, FICO 之类) 统一记下来, 好让后面并行翻译各个文件时口径一致. 而写摘要需要的, 恰恰就是这份 "读完整份 dataset 之后消化出来的理解". 换句话说, 如果摘要和翻译各用一个环节, 就要把那几份大文件读两遍; 合成一步, 读一遍就够, 摘要是这次通读顺手的副产物.

顺序也是有讲究的: **先写中文摘要, 再翻译**. 因为中文摘要一旦落成文件, 它就和其它 `-cn` 文件一样, 会被同一轮翻译一并处理, 英文版摘要就这么免费产出了. 反过来先翻译再写摘要, 那份摘要就赶不上这趟翻译, 还得单独再翻一次。所以这一步内部的次序是固定的: 通读并写出中文摘要, 然后才是并行翻译。

---

## 2. Skill 负责编排, subagent 负责干活

这一步的实现刻意分成两层: 一个 Skill 做编排, 三个 subagent 做实际的读写. 这个 "skill 当 caller, subagent 当 doer" 的拆法是关键的设计决定, 值得说清楚为什么.

[run-summarize-and-translate](../.claude/skills/run-summarize-and-translate/SKILL.md) 这个 Skill 本身只做编排: 发现有哪些 `-cn` 文件, 先派一个 subagent 写摘要, 再并行派多个 subagent 翻译, 最后校验. 它必须跑在主上下文里, 因为只有主上下文里的东西才能 fan-out 出 subagent. 真正的重活落在三个 subagent 身上, 每个都是一个独立的上下文, 各自锁定了自己的模型:

- [dataset-digest](../.claude/agents/dataset-digest.md): 把三份中文文件 (业务背景, ER, SQL) 完整读一遍, 写出中文摘要 `00-<name>_summary-cn.md`, 并把 consistency brief 作为返回值交回去. 上一节说的那次 "唯一的一遍通读" 就发生在这里.
- [dataset-md-translator](../.claude/agents/dataset-md-translator.md): 每个 `-cn.md` 文件派一个, 把它整篇改写成英文.
- [dataset-py-translator](../.claude/agents/dataset-py-translator.md): 处理那份 `-cn.py` 生成脚本, 只翻译注释和 docstring, 可执行代码逐字不动.

为什么是 subagent 而不是让 Skill 自己在主上下文里干? 三个原因. 一是**上下文隔离**: 那几份大文件的全文只在 subagent 自己的上下文里翻腾, 不会灌进主对话, 主对话只拿到一份很短的 brief. 二是**锁定模型**: 翻译质量对模型很敏感 (实测下来要用够强的模型才能稳定遵循一大堆翻译规范), 而 subagent 的定义文件正是钉死 `model` 字段, 并预加载翻译规范 skill 的地方 — 这是 Skill 的一句 prose 指令替代不了的. 三是**并行**: 各文件的翻译互不依赖, 一文件一个 subagent 同时跑, 靠的就是第 1 节那份 brief 保证它们口径一致.

这三个 subagent 各自的翻译规则, 文件命名约定, 硬约束, 都写在它们自己的定义文件里, Skill 不重复这些, 只负责把文件路径和 brief 递给它们, 再把结果收回来校验.

---

## 3. 为什么摘要偏偏在这一步生成

摘要这份东西, 位置卡得很讲究: 不在它前面的 fake-data-generator, 也不在它后面的索引, 恰恰在这一步。两头都有明确的理由不接这活。

前面 [01-dataset-anatomy.md](01-dataset-anatomy.md) 已经讲过, fake-data-generator 不写摘要, 是因为摘要是四份文件冻结之后才浓缩的派生物, 而且初稿要反复打磨很多轮, 摘要在那个阶段生成只会被一遍遍重写, 纯属浪费。

后面的索引也不该在自己那一步现算摘要。索引是一份会被反复重跑的清单 (细节见 [05-dataset-index.md](05-dataset-index.md)): 每加一个新 dataset 可能就要重扫一遍。如果索引每次都现读大文件现浓缩摘要, 那些没有任何改动的老 dataset 就会被一遍遍重读重算, 成本花在了不变的东西上。把摘要在这一步**一次性写成文件**, 索引那一步就退化成一个便宜的确定性拼装器, 只需要读这些已经冻结的一行摘要即可。那份摘要文件就是缓存, 只有当 dataset 本身被重新生成时才需要重算。

所以这一步是摘要唯一合理的家: 时间点上, 它紧跟在四份文件冻结之后, 摘要反映的是最终状态; 产物上, 它同时交出中文摘要, 又借同一轮翻译顺手交出英文摘要, 而这两份正是索引要吃的东西。

---

## 4. 输入, 产出, 顺序

一句话把这一步收束一下:

- **输入**: 定稿的 `*-cn.md` (业务背景, ER, SQL) 加 `*-cn.py` 生成脚本。
- **产出**: 先是 `00-<name>_summary-cn.md`, 然后是每一份 `-cn` 文件的英文版, 其中包括 `00-<name>_summary.md`。摘要文件两种语言都只有一行, 不带任何标题。
- **顺序**: digest 通读并写出中文摘要 → 多个 translator 并行产出全部英文文件。
- **下一步**: [05-dataset-index.md](05-dataset-index.md) 会把这两份摘要文件收进索引清单。

至于怎么实际驱动这一步 (串行处理多个 dataset 的提示词等操作细节), 放在 [07-adding-a-new-dataset-end-to-end.md](07-adding-a-new-dataset-end-to-end.md) 那篇工作流攻略里讲, 这一篇只讲设计。
