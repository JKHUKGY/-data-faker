# 摘要写好之后, 索引怎么攒起来

[04-summarizing-and-translating.md](04-summarizing-and-translating.md) 讲的那一步跑完之后, 每个定稿的 dataset 都已经带上了自己的一句话摘要, 中英各一份. 这时候仓库里的 dataset 会越积越多, 需要一份清单, 让人一页扫下来就知道仓库里有什么, 该点开哪一个. 这篇讲怎么把那些现成的摘要攒成这份清单, 也就是 [dataset/INDEX-cn.md](../dataset/INDEX-cn.md) 和 `dataset/INDEX.md`.

---

## 1. 索引解决的是查阅问题, 不是生成问题

索引这一步和前面几篇讲的生成, 审查, 打磨, 摘要都不是一回事. 前面那些步骤做的是把一个 dataset 从无到有做扎实并总结好, 索引做的只是让这些成果变得好找. dataset 数量一多, 挨个点开目录看里面装的是什么, 这种查阅成本会变得不可持续, 索引就是把这份查阅成本一次性付清, 换成清单里一行摘要.

清单本身分中英文两份, 分别是 [dataset/INDEX-cn.md](../dataset/INDEX-cn.md) 和 [dataset/INDEX.md](../dataset/INDEX.md), 跟 dataset 自己中英文两套文件的惯例保持一致.

---

## 2. 索引直接读现成的摘要, 不现算

摘要在 [04-summarizing-and-translating.md](04-summarizing-and-translating.md) 那一步就已经写成了文件, 冻结在每个 dataset 目录下:

- `dataset/<name>/00-<name>_summary-cn.md` → 进 `dataset/INDEX-cn.md`
- `dataset/<name>/00-<name>_summary.md` → 进 `dataset/INDEX.md`

所以索引这一步不需要现算任何东西, 更不需要 AI: 它只是把这些现成的一行摘要读出来, 套上 `- [<name>](<name>): ` 的壳, 写进两份清单. 读一个文件是确定性的动作, 于是这一步整个就是一段确定性的操作, 又便宜又可以随便重跑, 每次结果一致.

也正因为索引原样搬运摘要文件里的字, 摘要 "会不会编数字" 这个顾虑在这一步根本不存在 — 摘要的忠实性由写它的 [dataset-digest](../.claude/agents/dataset-digest.md) subagent 在上一步保证, 索引只负责搬运。

---

## 3. 两层结构, 外加一个可自然语言唤醒的 skill

既然是纯确定性的文件操作, 这一步就用一个普通的 Python 脚本实现, 和 [03-automating-review-and-fix.md](03-automating-review-and-fix.md) 里 [review_and_fix_loop.py](../review_and_fix_loop.py) 与 [ai_datafaker_pro/review_and_fix_loop.py](../ai_datafaker_pro/review_and_fix_loop.py) 的关系一样, 拆成顶层和底层:

- 顶层 [update_dataset_index.py](../update_dataset_index.py) 是根目录下的薄 CLI, 负责跑一遍并把结果打印出来, 不接受任何参数.
- 底层 [ai_datafaker_pro/update_dataset_index.py](../ai_datafaker_pro/update_dataset_index.py) 是包里的模块, 装真正的逻辑: 扫描 `dataset/` 下所有子目录, 用 `pathlib` 的 glob 找到每份摘要文件, 用字符串模板从头生成两份清单.

在这之上还包了一层 [.claude/skills/update-dataset-index](../.claude/skills/update-dataset-index/SKILL.md) Skill. 这个 Skill 很薄, 存在的意义只是让人能用自然语言把这件事唤起来 ("更新一下索引"), 它自己不读文件不写摘要, 只是去跑那个脚本, 再把脚本的输出转述给人。之所以这里合适放一个 Skill 而不是像摘要那样放一个 subagent, 是因为这一步没有任何需要 AI 推理, 需要上下文隔离的东西 — 就是跑个确定性脚本, subagent 在这里是多余的仪式。

---

## 4. 每次全量重扫重生成, 没有 "更新" 一说

这一步刻意不做 "增量更新": 每次跑都是把 `dataset/` 全量重扫一遍, 用字符串模板把两份清单从头重新生成. 因为读摘要是确定性的, 重生成出来的清单就是 "当前磁盘上存在哪些摘要文件" 的一个纯函数, 既不会漏掉新的, 也不可能残留过期的旧条目, 那自然就没有 "按名字合并, 保留其它条目" 这类逻辑要维护了 — 全量重生成本身就保证了正确, 比小心翼翼地做增量合并更简单也更不容易出错.

唯一留的一手是对付找不到摘要的情况: 一个 dataset 如果还没生成摘要 (还在草稿阶段, 或者还没翻译), 脚本用 glob 找不到它的摘要文件, 就打一条 warning 跳过它, 而不是报错中断 — 这只是个防御机制. 结果是这个 dataset 这一轮不会出现在清单里. 所以有一个次序上的前提: 因为是全量重生成, 要等该有摘要的 dataset 都在 [04-summarizing-and-translating.md](04-summarizing-and-translating.md) 那一步跑完之后再更新索引, 否则没摘要的那些会从清单里掉出去。
