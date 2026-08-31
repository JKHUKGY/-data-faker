# Review Fake Data Generator Skill

## 1. 这个 Skill 是什么

一个针对 `fake-data-generator` 产出的数据集做外部代码评审的 skill. 扮演领域专家加代码审查者角色, 对 `dataset/` 下任意北美行业的数据集做评审, 输出结构化报告.

最高原则: 精修, 不重新设计. 作者选定的虚构北美公司, 业务背景, 项目框架是地基. 只在严重自相矛盾或与工业界常识严重不符时挑战, 其他改动都是打磨细节.

---

## 2. 能做什么

接收 `<dataset-name-or-path>` 参数, 定位数据集目录, 按严格四阶段顺序评审, 最后给出优先级修复清单和总体可用性判断.

本 skill 只读四份中文文件作为 source of truth: `01-{dataset_name}_business_context-cn.md`, `02-{dataset_name}_er_document-cn.md`, `03-{dataset_name}_sql_queries-cn.md`, `04-{dataset_name}_data_generator-cn.py`. 英文版本由 translate-to-en skill 在中文版定稿后一次性产出, 评审不读英文文件, 也不针对英文文件提修改建议. 中文文件里发现的所有问题, 翻译时会自然传到英文版.

Stage 4 会用 `sqlite3` 直接查询生成的数据库, 验证文档承诺的"业务陷阱" (分布偏置, 计算字段, 时序约束, FK 完整性) 在实际数据中真的落地. 允许工具加了 `Bash(sqlite3 *)`, `Bash(python *)`, `Bash(uv *)`.

---

## 3. 怎么干事的

按四阶段顺序执行. 每阶段完成报告后再读下一份文件.

- **Stage 1.** 业务背景评审. 检查 `01-{dataset_name}_business_context-cn.md`: 北美市场, 公司画像合理性, 收入模式具体度, 项目角色, 业务问题, 行业科普, 术语表, 指标公式.
- **Stage 2.** ER 文档评审. 检查 `02-{dataset_name}_er_document-cn.md`: Mermaid ER 图存在 (硬性要求), 实体完整性, 关系正确性, 字段真实性, 每张表的业务用途, 计算字段声明, 嵌入业务陷阱声明, Mermaid 与表定义一致.
- **Stage 3.** SQL 查询评审. 检查 `03-{dataset_name}_sql_queries-cn.md`: 教学口吻 (五段式与解题思路), 业务逻辑, SQL 正确性 (含 SQLite 兼容性, fan-out, NULL 语义), 跨查询一致性.
- **Stage 4.** 生成器评审加实测. 静态阅读 `04-{dataset_name}_data_generator-cn.py` (硬性规定合规, Schema 对齐, 跨表完整性, 分布真实性), 然后用 sqlite3 跑 SQL 验证 Stage 2 catalogued 的每个业务陷阱, 检查 FK 完整性, 时序不变量, 计算字段不变量, 行数与 manifest 一致.

最后产出 Prioritized fix list 表格加一段总体判断.

---

## 4. 有哪些文件

- `SKILL.md` 唯一定义文件: 评审协议, 四阶段流程, 各阶段报告格式, cardinal principle (精修 vs 重设计), 评审基调.
- `README-cn.md` 本文档.

本 skill 没有独立 references 目录. SKILL.md 通过 `cat ${CLAUDE_SKILL_DIR}/../fake-data-generator/SKILL.md` 自动注入被评审 skill 的上下文, 需要时再按需打开 fake-data-generator 的 guidance 文档.
