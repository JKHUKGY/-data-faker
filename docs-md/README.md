# AI Datafaker Pro 项目总览

## 1. 这个 repo 要解决什么问题

我们平时靠做 project 来提升技能, 大部分技能都好练, 唯独数据库和数据分析这类技能很难练, 因为手头往往没有真实的业务数据可用. 找一份看起来像样的业务数据似乎不难, 随便造几张表, 塞点随机数字就能凑出一个 demo. 但真正难的地方在于, 这份数据要经得起推敲: 数字要严丝合缝, 表和表之间的关系不能有漏洞, 业务叙事和实际数据不能互相矛盾, 更不能出现常识性错误. 一旦某个环节露馅, 后面基于这份数据做的所有分析和练习都会跟着失真.

这个项目要解决的就是这件事本身: 针对一个具体的 project, 一段具体的业务背景, 和一个具体的 use case, 造出一份严丝合缝, 内部自洽, 经得起业务专家审视的 dummy data 和 business background.

---

## 2. 每个 dataset 长什么样子

`dataset/` 目录下的每个子目录都是一份独立的 dataset, 对应一家虚构公司的一段业务故事. 每份 dataset 包含一行摘要, 业务背景说明, ER 文档, 一批贴近生产场景的 SQL 查询题, 以及生成数据的 Python 脚本, 中英文各一套. 数据库文件和 TSV 数据本身不入库, 而是运行生成脚本之后现造出来的, 这样仓库体积不会因为数据量变大而膨胀.

---

## 3. 整条流水线, 以及 skill 与 subagent 的分工

从一个点子到一份可以合并进仓库的 dataset, 中间要走一条固定的流水线, 每一环都有对应的 skill 或脚本:

1. **想 Idea** — `brainstorm-dataset-ideas` 读现有索引当覆盖地图, 找空白或从一份 Job Description 反推, 把点子写进 `tmp/idea.md`.
2. **写初稿** — `fake-data-generator` 从零起草四份中文文件, `review-fake-data-generator` 在另一个 session 里只读审查, 两者配合把大方向问题先摆出来给人决策. 这两个 skill 是 "造" 和 "挑刺" 的核心生产力工具.
3. **左右互搏打磨** — `review_and_fix_loop.py` 用两个持久化的 SDK session 模拟两个人对着打, 一个只管挑问题, 一个只管照着问题改, 全程无人值守, 跑完几轮数据和文档的一致性明显提升.
4. **写摘要 + 翻译** — `run-summarize-and-translate` 给定稿的 dataset 写一行中文摘要, 再把全套中文产出物翻译成英文.
5. **更新索引** — `update-dataset-index` (底层是 `update_dataset_index.py`) 全量重扫每份 dataset 现成的一行摘要, 从头重新生成 `dataset/INDEX.md` 和 `dataset/INDEX-cn.md`.

这里有一个贯穿全项目的架构取舍: **skill 当 caller, subagent 当 doer**. skill 跑在主上下文里负责编排 (发现文件, fan-out, 校验), 真正读大文件, 写大文件这类重活丢给独立上下文, 锁定模型的 subagent 去干 — 摘要和翻译那一步的 `dataset-digest` / `dataset-md-translator` / `dataset-py-translator` 就是这么拆的. 而像更新索引这种纯确定性, 不需要 AI 推理的活, 就退化成一个薄 skill 直接去跑脚本, 连 subagent 都不必上.

---

## 4. 想深入了解: 按顺序读这八篇

这个目录下的八篇文档按流水线顺序展开, 讲的是每一环的设计意图 (Why), 而不是操作手册:

1. [01-dataset-anatomy.md](01-dataset-anatomy.md) — 一个 dataset 由哪些文件组成, 又由哪些变量决定.
2. [02-two-session-review.md](02-two-session-review.md) — 初稿写完之后怎么审, 为什么审和改要拆成两个 session.
3. [03-automating-review-and-fix.md](03-automating-review-and-fix.md) — 怎么把审和改自动串成一个无人值守的循环.
4. [04-summarizing-and-translating.md](04-summarizing-and-translating.md) — 定稿后怎么写摘要并翻译成英文, 为什么这两件事合成一步.
5. [05-dataset-index.md](05-dataset-index.md) — 摘要写好后, 索引怎么从这些一行摘要全量重生成.
6. [06-brainstorming-new-dataset-ideas.md](06-brainstorming-new-dataset-ideas.md) — 索引建好之后, 怎么拿它当覆盖地图想下一个点子.
7. [07-adding-a-new-dataset-end-to-end.md](07-adding-a-new-dataset-end-to-end.md) — 把前面几步串成一条从零到合并的完整工作流, 附一页速查表.
8. [08-staging-datasets-for-distribution.md](08-staging-datasets-for-distribution.md) — 怎么把 dataset 打包给别的地方用.

想快速上手直接做一个新 dataset, 从 [07-adding-a-new-dataset-end-to-end.md](07-adding-a-new-dataset-end-to-end.md) 那篇操作清单读起, 遇到 "为什么要这么设计" 再翻回对应的单篇.
