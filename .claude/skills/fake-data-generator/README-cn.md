# Fake Data Generator Skill

## 1. 这个 Skill 是什么

一个垂直行业假数据生成专家 skill. 为任意行业 (金融, SaaS, 医疗器械, 电商, 广告 等) 生成业务驱动的模拟数据集. 不是单纯的 schema 演示, 而是一家北美 (美国 或 加拿大) 虚构公司用数据回答真实业务问题的完整故事.

默认市场是北美. 虚构公司位于美国或加拿大, 货币是 USD, 监管语境是 SEC, OCC, FDA, CFPB, OSC, FINRA, Health Canada 这类机构. 中文文档使用中文叙述, 但描述的业务依然是北美.

---

## 2. 产出什么

每次运行产出一个 dataset, 命名规范 `{industry}_{use_case}_{complexity}`, 输出到 `dataset/{dataset_name}/`.

四份产物文件都带 `01-` 到 `04-` 的数字前缀, 使数据集目录按读者阅读顺序自然排序 (业务背景 → ER 文档 → SQL 查询 → Python 生成器).

完整产物清单 (经历两段工作流之后):

- `01-{dataset_name}_business_context-cn.md` (本 skill 写) 与 `01-{dataset_name}_business_context.md` (translate-to-en 翻译)
- `02-{dataset_name}_er_document-cn.md` (本 skill 写) 与 `02-{dataset_name}_er_document.md` (翻译)
- `03-{dataset_name}_sql_queries-cn.md` (本 skill 写) 与 `03-{dataset_name}_sql_queries.md` (翻译)
- `04-{dataset_name}_data_generator-cn.py` (本 skill 写) 与 `04-{dataset_name}_data_generator.py` (翻译)
- `{dataset_name}.sqlite` 与 `data/{NN}_{table}.tsv` (运行 Python 脚本时产生)

两个 Python 文件的可执行代码完全相同, 区别仅在注释和 docstring 的语言. 翻译过程不动代码. `data/` 下面的 TSV 文件用下划线分隔的 `NN_table.tsv` 命名, 是独立的拓扑排序约定, 与外层四份文件的 `NN-` 前缀分开看.

---

## 3. 怎么干事的

按七阶段执行. 前三个阶段交互, Phase 3 设计, Phase 4 写中文四件套, Phase 5 跑数据校验, Phase 6 切换到翻译.

- **Phase 0.** 行业目录确认, 定下 `{industry}` 前缀.
- **Phase 1.** Agent 提 2 到 3 个虚构北美公司画像 (含项目角色与 3 到 5 个业务问题), 用户挑一个. 决定 `{use_case}`.
- **Phase 2.** 复杂度选择 (Low / Medium / High / Large).
- **Phase 3.** Schema 设计, 同时确定要嵌入的"业务陷阱" (每个业务问题对应一个故意设计的分布偏置或相关性, 让特定 SQL 查询能精准暴露).
- **Phase 4.** 写四份中文文件: `01-{dataset_name}_business_context-cn.md`, `02-{dataset_name}_er_document-cn.md` (含 Mermaid ER 图), `03-{dataset_name}_sql_queries-cn.md`, `04-{dataset_name}_data_generator-cn.py`. 四份联动精修.
- **Phase 5.** 执行 Python 脚本, 用 sqlite3 抽查嵌入陷阱的实际分布是否匹配文档承诺.
- **Phase 6.** 用户对中文文件签字定稿后, 调用 `translate-to-en` skill 产出四份英文文件. Skill 不手写英文.

---

## 4. 关键硬性规定

写 Markdown 文件之前先加载 `markdown-style` skill, 按它的规范来.

写 Python 文件遵循:

- SQLAlchemy 2.0 ORM 写法.
- 每行只 import 一个东西. `from datetime import date, datetime` 这种是不允许的, 必须拆成三行.
- 默认 `FAKER_LOCALE = "en_US"`.
- 用 `REFERENCE_DATE` 常量锚定"今天", 不调 `datetime.now()`.
- TSV 到 SQLite 用 Core API 批量导入, 一个有序列表 + 一个 for-loop + 一个 `engine.begin()` 事务搞定.
- Business Calibration Constants 段落里每个权重 / 概率 / 阈值都带"为什么是这个值"的注释.

写 ER 文档时, 每张表必须有 Mermaid ER 图覆盖到 (可拆分多个子图), 并且每张表都需要业务用途段落 (面向小白, 不假设领域专家).

写 SQL 查询时, 每个查询五段式: 业务背景 → 类别难度角色 → 解题思路 → SQL → 期望结果与业务结论. 解题思路那段是教学重点, 不能只复述 SQL.

---

## 5. 有哪些文件

- `SKILL.md` 主入口, 定义工作流, 命名规范, 约束.
- `README-cn.md` 本文档.
- `references/industry_catelog.md` 与 `_cn.md` 与 `_en.md`: 三级行业分类, 浏览找选题用.
- `references/business_context_guidance.md`: 业务背景文档写什么.
- `references/er_document_guidance.md`: ER 文档写什么 (含 Mermaid 强制要求).
- `references/sql_queries_guidance.md`: SQL 查询文档写什么 (含教学口吻要求).
- `references/data_generator_guidance.md`: Python 脚本硬性规定 + Core API 批量导入模板.

每份 guidance 文档描述必须包含的内容点和踩坑提示, 不限定章节标题. 版本变迁与改动详情见 `CHANGELOG.md`.
