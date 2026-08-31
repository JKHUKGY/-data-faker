# 把前面几步串起来: 添加一个新 dataset 的完整工作流

前面六篇分别讲了一个 dataset 由哪些文件组成 ([01-dataset-anatomy.md](01-dataset-anatomy.md)), 写完初稿之后怎么审 ([02-two-session-review.md](02-two-session-review.md)), 怎么把审和改自动串成无人值守的循环 ([03-automating-review-and-fix.md](03-automating-review-and-fix.md)), 定稿后怎么写摘要并翻译成英文 ([04-summarizing-and-translating.md](04-summarizing-and-translating.md)), 摘要写好后索引怎么攒起来 ([05-dataset-index.md](05-dataset-index.md)), 以及怎么想下一个 dataset 的点子 ([06-brainstorming-new-dataset-ideas.md](06-brainstorming-new-dataset-ideas.md)). 那六篇讲的是每一个环节各自的 Why 和机制. 这一篇不引入任何新机制, 只做一件事: 站在一个要往这个仓库里添加新 dataset 的维护者的角度, 把这些环节按实际操作顺序拼成一条从零到合并的流水线, 告诉你每一步具体动哪个 Skill, 跑哪个脚本, 在哪儿停下来做人工判断.

读这一篇的前提是前六篇已经读过. 这里不会重复解释 project framing 是什么, 两个 session 为什么不能自己审自己, 摘要为什么要在翻译那一步生成这些设计层面的道理, 需要的时候直接给回链接. 把这一篇当成一张操作清单来用, 遇到某一步想知道 "为什么要这么设计", 再翻回对应的那一篇.

---

## 1. 第一步: 想 Idea

动手做之前, 先得有一个值得做的点子. 这一步的机制在 [06-brainstorming-new-dataset-ideas.md](06-brainstorming-new-dataset-ideas.md) 里讲过, 这里只说操作顺序.

**1.1 先自己读一遍 [dataset/INDEX-cn.md](../dataset/INDEX-cn.md).** 不要一上来就让 Skill 帮你想, 先自己扫一遍现有的覆盖, 对仓库里已经有哪些行业, 哪些 use case 心里有个数. 这一步花不了几分钟, 但它决定了你后面能不能一眼看出 Skill 给的点子是不是在重复造轮子.

**1.2 用 [brainstorm-dataset-ideas](../.claude/skills/brainstorm-dataset-ideas/SKILL.md) Skill 头脑风暴.** 这个 Skill 有两种用法:

- **凭空想 (Mode A)**: 不带参数直接调用, 让它照着覆盖地图找空白, 一次给五到八个尽量分散在不同格子里的点子.
- **由岗位反推 (Mode B)**: 丢给它一段 Job Description, 让它倒推出这个岗位每天要看, 要查, 要喂给模型的那份数据. 一个现成的 JD 来源是 [offer_forge_blogs-project 里的 by-job-description 目录](https://github.com/easyscale-academy/offer_forge_blogs-project/tree/main/blogs/by-job-description). 挑一个感兴趣的子目录 (一份 job description), 把整个目录下载下来, **删掉所有 `-cn.md` 结尾的文件, 只留英文版就够了** — 英文那份携带的信息已经足够 Skill 反推, 中英两份都喂进去只是徒增噪音. 然后把这个 JD 交给 Skill, 让它针对这个岗位来想.

**1.3 读 [tmp/idea.md](../tmp/idea.md), 挑一个或者继续聊.** Skill 只把点子写进 `tmp/idea.md` 就停, 做不做, 做哪个, 决定权在你手里. 打开这份点子清单扫一遍: 有中意的, 挑一个进入第二步; 一个都不满意, 就继续用 `brainstorm-dataset-ideas` 接着聊, 补充约束, 换个行业, 换个岗位, 直到聊出一个你真愿意动手做的点子为止. 这个交接点是故意做轻的, 别指望一次就出完美点子.

---

## 2. 第二步: 根据 Idea 写 dataset 的初稿

有了选定的点子, 就进入起草. 这一步全程围绕 [fake-data-generator](../.claude/skills/fake-data-generator/SKILL.md) 和 [review-fake-data-generator](../.claude/skills/review-fake-data-generator/SKILL.md) 两个 Skill, 关键是它们分别开在**两个独立的 session** 里, 原因见 [02-two-session-review.md](02-two-session-review.md).

**2.1 在 fake-data-generator 的 session 里起草并粗修.** 开一个新 session, 调用 `fake-data-generator`, 把第一步选中的那个点子内容直接复制粘贴进去. 先别急着让它出文件, 跟它头脑风暴个 **3 到 5 轮**, 把这家虚构公司的 background, project framing, 业务问题这些方向性的东西聊扎实 — 这一步正是人该出力的地方, 那些需要取舍和判断的逻辑决策, 只有人做得来. 聊清楚之后让它出一版初稿, 然后**在同一个 session 里继续迭代 5 到 10 轮**, 对产出的四份文档做粗修.

**2.2 换一个新 session, 用 review-fake-data-generator 走一轮.** 保留 2.1 那个 session 不要关. 另开一个新 session 调用 `review-fake-data-generator`, 让它对刚起草的 dataset 做一轮只读审查. 这一轮的目的不是求全, 而是借 review 的力量, 把几个最重要的方向性问题, 矛盾性问题先跳出来, 摆到台面上, 好让你这个人类去对这些重要问题做决策. 这一步对应 [03-automating-review-and-fix.md](03-automating-review-and-fix.md) 里说的 "人类自己手动跑一轮 review, 把大方向上的判断力用在刀刃上".

**2.3 回到 fake-data-generator 的 session, 把 review 结果丢回去改.** 切回 2.1 那个还留着的 session, 把 2.2 生成的 review report 交给它 — 复制粘贴那份 review 文件的路径就行, 不用把内容整段贴进去. 然后**你来做判断**: 对每一条意见, 说说你认为该怎么改; 自己拿不准的, 就让 `fake-data-generator` 给你出选择题式的建议, 由你来选. 定了方向之后, 让它在同一个 session 里按你的意思把**最大的方向性问题, 矛盾性问题**改掉. 这一步通常最多 **1 到 3 轮**. 改完, 初稿就算完成了.

> **重要**: 这一步结束之后, 把 2.2 和 2.3 过程中生成的 review 和 fix 文件删掉. 不删的话, 它们会残留在 dataset 目录里, 影响后面第四步左右互搏循环的编号 (那一步会重新从 `review-01.md`, `fix-01.md` 开始编号, 见 [02-two-session-review.md](02-two-session-review.md)).

---

## 3. (可选) 一次性多做几个 dataset

如果你这一轮只打算做一个 dataset, 这一步整段跳过, 直接进第四步.

实践中更推荐的做法是一次攒几个, 比如 3 到 5 个 dataset 的初稿. 原因是从第四步开始, 后续的几步 (左右互搏循环, 写摘要与翻译) 都可以比较丝滑地无人值守顺序执行, 特别适合放在晚上睡觉的时候让它慢慢跑. 前期人工密集的只有第一步和第二步, 把这两步集中做几遍, 攒出一批初稿, 后面的自动化环节就能一口气覆盖掉整批.

具体节奏你可以自由组合: 做一次第一步, 然后紧接着连续做几次第二步; 或者做几次第一步和第二步交替进行, 最终产出多个 dataset 的初版, 一起进入下面的自动化流水线.

---

## 4. 第四步: 执行 Review and Fix 左右互搏循环

初稿完成之后, 进入无人值守的自动打磨. 这一步的机制在 [03-automating-review-and-fix.md](03-automating-review-and-fix.md) 里讲透了, 操作上没什么玄机:

1. 打开 [review_and_fix_loop.py](../review_and_fix_loop.py), 把要打磨的 dataset 文件夹名字填进顶部的 `DATASET_NAMES` 列表; 想跳过哪个就把那一行注释掉.
2. 用 `.venv/bin/python review_and_fix_loop.py` 跑起来 (等价于 `uv run python review_and_fix_loop.py`), 让它跑完设定的多轮 review 和 fix 左右互搏.

可以只放一个 dataset, 也可以放多个 — 多个 dataset 之间是串行跑的, 一个跑完才跑下一个, 这正是第三步攒一批初稿之后适合放到夜里跑的原因. 跑完回来看落盘的 `review-NN.md` 和 `fix-NN.md`, 确认收敛到了预期的状态.

---

## 5. 第五步: 用 run-summarize-and-translate 写摘要并翻译成英文

左右互搏跑完, 中文四件套就打磨定稿了. 接下来用 [run-summarize-and-translate](../.claude/skills/run-summarize-and-translate/SKILL.md) Skill 干两件事: 先给这个 dataset 写一行中文摘要 (`00-<name>_summary-cn.md`), 再把包括这份摘要在内的所有 `-cn.md` 和 `-cn.py` 翻译成对应的英文版本. 摘要和翻译为什么合成一步, 顺序为什么是先摘要后翻译, 见 [04-summarizing-and-translating.md](04-summarizing-and-translating.md), 这里只讲操作.

操作上不直接裸调 Skill, 而是走 [.claude/.prompt/run-summarize-and-translate.md](../.claude/.prompt/run-summarize-and-translate.md) 这份现成的提示词: 把里面的 dataset folder 路径占位符替换成这一批实际要处理的 folder 路径, 然后把整段发出去, 让它慢慢跑. 注意这份提示词里已经写明了**多个 dataset 之间必须串行**执行 — 因为 `run-summarize-and-translate` 内部会先派一个 `dataset-digest` subagent 写摘要, 再派多个 translator subagent 并行翻译, 如果连 dataset 这一层也并行, 会一次性 launch 太多 subagent, 错误率飙升, 得不偿失.

跑完之后, 每个 dataset 目录里就多了中英两份摘要 (`00-<name>_summary-cn.md` 和 `00-<name>_summary.md`) 以及全套英文文件, 这正是下一步索引要吃的东西.

---

## 6. 第六步: 更新索引, 然后 commit 开 PR

检查摘要和翻译都没问题之后, 最后一步是更新索引, 让 [dataset/INDEX-cn.md](../dataset/INDEX-cn.md) 和 [dataset/INDEX.md](../dataset/INDEX.md) 反映当前所有 dataset 的摘要. 机制见 [05-dataset-index.md](05-dataset-index.md): 这一步是纯脚本, 全量重扫 `dataset/`, 从每个 dataset 现成的一行摘要重新生成两份清单, 不涉及 LLM, 也不需要你指定改哪几个 — 直接 `uv run python update_dataset_index.py` 就行, 或者用 [update-dataset-index](../.claude/skills/update-dataset-index/SKILL.md) Skill 让它替你跑 (对人类更友好). 唯一要注意的是次序: 因为是全量重生成, 没有摘要的 dataset 会被跳过并 warning, 所以要等这一批的第五步都跑完再更新索引, 别在摘要还没生成时就跑, 否则那些 dataset 会从清单里掉出去.

索引更新完, 一个 (或一批) 新 dataset 就彻底完工了. 剩下的就是常规的仓库动作: `git commit`, 开 PR, 走一遍 Code Review, 然后 Merge. 到这里, 流程正好转了一整圈 — 新 dataset 进了索引, 而这份索引又会成为下一次第一步里 `brainstorm-dataset-ideas` 找空白的输入, 循环重新开始.

---

## 附: 一页速查

| 步骤 | 动作 | 用什么 | 人工还是自动 |
|------|------|--------|--------------|
| 1 想 Idea | 读索引 → 头脑风暴 → 挑点子 | [brainstorm-dataset-ideas](../.claude/skills/brainstorm-dataset-ideas/SKILL.md) → [tmp/idea.md](../tmp/idea.md) | 人工为主 |
| 2 写初稿 | 起草粗修 → 手动 review 一轮 → 改大问题, 删 review/fix 文件 | [fake-data-generator](../.claude/skills/fake-data-generator/SKILL.md) + [review-fake-data-generator](../.claude/skills/review-fake-data-generator/SKILL.md), 两个 session | 人工密集 |
| 3 (可选) 攒批 | 重复 1 和 2, 攒 3-5 个初稿 | 同上 | 人工 |
| 4 左右互搏 | 填 `DATASET_NAMES`, 跑脚本 | [review_and_fix_loop.py](../review_and_fix_loop.py) | 无人值守 |
| 5 摘要 + 翻译 | 替换路径占位符, 串行跑 | [run-summarize-and-translate](../.claude/skills/run-summarize-and-translate/SKILL.md) via [提示词](../.claude/.prompt/run-summarize-and-translate.md) | 无人值守 |
| 6 索引 | 跑脚本全量重生成索引, 开 PR | `uv run python update_dataset_index.py` 或 [update-dataset-index](../.claude/skills/update-dataset-index/SKILL.md) | 半自动 |
