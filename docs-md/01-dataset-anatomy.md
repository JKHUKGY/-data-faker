# 一个 Dataset 由哪些文件组成, 又由哪些变量决定

这份文档描述的规则, 由 [.claude/skills/fake-data-generator](../.claude/skills/fake-data-generator/SKILL.md) 这个 Skill 具体实现. 这里讲的是设计层面的 Why, Skill 本身负责把这些规则落成可执行的 Phase 和可复用的 reference 文件. 读这篇文档是为了理解设计意图, 真正动手生成一个 dataset 时, 调用的是这个 Skill.

这一篇只讲 dataset 的**核心规范**: 一份 dataset 该由哪些文件组成, 每份文件回答什么问题, 设计它时要定哪几个变量. 至于我们在这个仓库里围绕 dataset 做的那些事情 (审查, 打磨, 写摘要, 翻译, 索引), 是叠在这份核心规范之上的生产流程, 由后面几篇分别去讲, 这一篇有意不掺进来.

## 1. 为什么是这四份文件

一份 dataset 的核心是四份文件: 业务背景说明, ER 文档, SQL 查询题, 以及 Python 生成脚本. 这四份文件不是随意拼凑的清单, 而是回答四个不同的问题. 业务背景说明回答 "这是一家什么公司, 它遇到了什么 business problem". ER 文档回答 "这些 business problem 落到 schema 上长什么样, 表和表之间怎么连". SQL 查询题回答 "拿到这份数据之后, 分析师具体要怎么用它回答业务问题". Python 生成脚本回答 "这一切怎么变成真实存在的数据". 四份文件互相印证, 缺一份, 剩下三份就立不住.

这份文档只讲 Why, 不重复 How. 每份文件具体要写哪些 section, 用什么格式, 这些决策已经在 skill 的 reference 文件里定好了, 以那里为准, 不在这里重复一遍:

- 业务背景说明的写法参见 [business_context_guidance.md](../.claude/skills/fake-data-generator/references/business_context_guidance.md)
- ER 文档的写法参见 [er_document_guidance.md](../.claude/skills/fake-data-generator/references/er_document_guidance.md)
- SQL 查询题的写法参见 [sql_queries_guidance.md](../.claude/skills/fake-data-generator/references/sql_queries_guidance.md)
- Python 生成脚本的写法参见 [data_generator_guidance.md](../.claude/skills/fake-data-generator/references/data_generator_guidance.md)

---

## 2. 还有一份一句话摘要, 但它不归 fake-data-generator 管

除了这四份核心文件, 一份成熟的 dataset 还会带一份一句话摘要, 用来在仓库的索引清单里代表它自己. 摘要的用途很单纯: dataset 一多, 谁都不想为了知道某个目录里装的是什么就把四份文件挨个打开, 摘要就是把这份查阅成本一次性付清, 换成清单里的一行字.

关键在于, 这份摘要**不是** fake-data-generator 生成的, 这是有意的分工. 原因有两层. 第一, 摘要是四份文件写完, 定稿冻结之后才浓缩出来的**派生产物**, 它天然属于 "把已经做好的东西总结一下", 而不属于 "从零把 dataset 做出来"; 让负责创作的 skill 顺手把摘要也写了, 等于把两个发生在不同时间点的动作硬塞进一个环节. 第二, 一份 dataset 的初稿往往要反复打磨很多轮, 如果摘要在这个阶段就生成, 每打磨一轮四份文件变一点, 摘要就得跟着重写一遍, 而这些中间态的摘要没有任何人会用到, 纯属浪费. 所以正确的做法是等四份文件真正稳定下来, 再一次性把摘要浓缩出来.

这份摘要具体在什么时候, 由谁生成, 怎么被索引消费, 是 [04-summarizing-and-translating.md](04-summarizing-and-translating.md) 和 [05-dataset-index.md](05-dataset-index.md) 的内容, 这里只需要记住一点: 它是核心规范的一部分, 但它的生成不是 fake-data-generator 的职责.

---

## 3. 设计一个 dataset 要定几个变量

动手写这些文件之前, 真正要做决定的只有三个变量: industry, 复杂度, 和 project framing. 前两个相对确定, 好判断; 第三个是这份文档想强调的重点, 也是最容易被忽视, 但对整个 dataset 形态影响最大的一个.

**Industry** 决定了故事发生在哪个行业, 公司卖什么, 客户是谁, 术语体系是什么. 它的取值范围来自 [industry_catelog.md](../.claude/skills/fake-data-generator/references/industry_catelog.md) 里的三级行业分类.

**复杂度** 决定了 schema 的规模, 表的数量, 数据量级. 它的取值是 low, medium, high, large 四档, 具体每档多少张表多少行数据, 由 fake-data-generator skill 的 SKILL.md 定义.

**Project framing** 决定了这份数据到底是为了支持什么样的工作场景, 是这三个变量里对 schema 形态, 数据分布, 甚至 SQL 查询风格影响最直接的一个. 同样是 industry 和复杂度, 支撑日常业务操作的数据和支撑机器学习建模的数据, 长得完全不一样. 常见的 project framing 有:

- **operation**, 日常业务的增删查改, 数据强调事务完整性和实时状态
- **analytics**, 数据分析场景, 又分小数据量的 BI 报表和大数据量的数仓两种, 数据强调可聚合性和历史留存
- **ML**, 机器学习和数据建模, 数据强调特征丰富度和标签质量, 通常需要更长的时间跨度
- **audit**, 留档审计, 数据强调不可篡改的历史记录和完整的操作轨迹
- **agent development**, 给 AI agent 用的后端, 数据强调结构清晰, 语义明确, 适合被工具调用而不是被人读

选定 project framing 之后, 业务问题, schema 设计, 甚至 SQL 查询题的难度和角色分布, 都应该围绕它展开, 而不是先把表画完再回头凑一个用途.

---

## 4. 最后也最难的一步, 是那个 .py 文件

四份文件里, 前三份是叙事和文档, 只有 Python 生成脚本是真正的产出物, 也是唯一一份被当作 "数据即代码" 来对待的文件. 这个设计的核心是: 进版本控制的是生成数据的代码, 不是数据本身. TSV 文件和 SQLite 数据库都是这份代码的构建产物, 就像源代码和编译出来的二进制文件的关系一样, 构建产物不入库, 需要的时候现跑现造.

这里要澄清一个容易想当然的误解: 跑两次这个脚本, 得到的不是保证字节级完全一致的两份文件. 脚本内部用的是随机数生成器, 哪怕设了固定的 random seed, Python 里 set 的遍历顺序, hash 随机化, 第三方库版本差异这些因素, 都可能让两次运行的产物在细节上有出入. "数据即代码" 真正保证的东西不是逐字节可复现, 而是数据的分布形状, 表间关系, 和业务陷阱这些设计层面的东西完全由代码决定, 只要代码不变, 这些设计层面的性质就不变, 这也是为什么 review 和 fix 只需要盯着代码改, 不需要保存任何一版旧数据做对比.

真正难的地方也不是把 Faker 调用堆出几万行数据, 而是让生成出来的数据分布经得起业务目标和 project framing 的检验. 一个 SaaS 公司的月流失率该是多少, 一批贷款里坏账率该往哪个 tier 集中, 一个客服 agent 场景里工单该有多少比例被自动解决, 这些分布如果只是均匀随机撒出来, 数据看起来热闹, 但完全撑不住业务背景说明里写下的那些论断. 生成脚本要做的, 就是把业务背景文件里写的每一个 business problem, 转成一段能在真实数据里被复现, 也能被后面的 SQL 查询题验证出来的分布逻辑.

---

## 5. 核心规范是一回事, 我们的生产流程是另一回事

上面讲的这些, 都是 dataset 的核心规范: 它有哪些文件, 每份文件回答什么问题, 要定哪几个变量. 这份规范本身和用什么语言叙述无关. fake-data-generator 这个 skill 从 SKILL.md 到 reference 文件全是用英文写的, 它定义的也是这样一份与叙述语言无关的规范 — 规范只关心一份 dataset 该长成什么样, 至于这些文件最终以什么语言呈现, 不是规范要操心的事.

真正引入语言这件事的, 是我们这个项目的生产流程. 我们希望每份产出物最后都有中英两个版本, 具体做法是先把四份文件和那份摘要用中文起草打磨到位, 再由一个专门的翻译环节产出对应的英文版, 于是一份做完的 dataset, 四份文件加一份摘要, 每一份都有中英两套. 但要分清楚: 这套中英双版本的维护, 是我们叠在核心规范之上的生产流程, 不是核心规范本身的一部分. 这一篇只讲规范, 从下一篇开始才是流程.
