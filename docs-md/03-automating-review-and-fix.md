# 怎么把 review 和 fix 自动串成一个无人值守的循环

[02-two-session-review.md](02-two-session-review.md) 讲了两个 session 靠 `review-NN.md` 和 `fix-NN.md` 隔空对话的机制. 这篇讲怎么把这套机制自动跑起来, 不需要人在中间来回传话. 具体实现分两层: [review_and_fix_loop.py](../review_and_fix_loop.py) 是顶层工具, 编辑一下 dataset 列表就能跑; [ai_datafaker_pro/review_and_fix_loop.py](../ai_datafaker_pro/review_and_fix_loop.py) 里的 `ReviewAndFixLoop` 是底层实现, 用 Claude Agent SDK 搭出来的. 上一篇讲的那套文件隔空对话协议, 具体怎么变成发给两个 session 的 prompt 文本, 就写在 `ReviewAndFixLoop._review_prompt` 和 `_fix_prompt` 这两个方法里, 想看细节直接读那两个方法, 这里不重复贴代码.

---

## 1. 为什么最终选择自动化, 而不是人工来回

人工开两个终端, 手动把 review 的意见念给 fix 那一边听, 不是没有价值. 它的好处是, 遇到真正有分歧的改法, 比如同一个问题有两种合理的修法, 人可以现场判断哪种更合理, 这种取舍能力目前只有人有. 但这套流程要打磨的是几十个 dataset, 每个 dataset 又要跑好几轮, 真要人工来回传话, 工作量根本扛不住, 这件事没法在人工模式下规模化.

所以默认策略是相信 AI 的判断. 只要 review 没查出明显的矛盾或者兑现失败, fix 那一边接受意见, 自主决定怎么改, 不需要停下来问人. 如果对这个信任程度不放心, 可以把 review 和 fix 都换成更强的模型 (比如 Opus), 它的判断力基本是可以托付的.

真正把 "人工来回" 这件事从流程里拿掉的, 是 Claude Agent SDK. Agent SDK 跑的是一段代码驱动的流程, 不是一个等人回话的聊天窗口, 所以 fix session 的 prompt 里明确写死不允许调用 `AskUserQuestion`, 任何拿不准的小细节都是自己拿主意直接改, 流程完全不会在中途卡住等人.

---

## 2. 两层结构: 顶层脚本和底层实现

顶层是 [review_and_fix_loop.py](../review_and_fix_loop.py), 只做一件事: 维护一份 `DATASET_NAMES` 列表, 里面是要打磨的 dataset 文件夹名字, 想跳过哪个就注释掉那一行, 然后跑 `uv run python review_and_fix_loop.py`. 多个 dataset 之间是串行跑的, 一个跑完才跑下一个, 因为一个 dataset 内部已经同时占用了两个 SDK subprocess, 并行跑多个 dataset 容易撞 IO 和撞 SDK 的速率限制.

底层是 [ai_datafaker_pro/review_and_fix_loop.py](../ai_datafaker_pro/review_and_fix_loop.py) 里的 `ReviewAndFixLoop` (这个包内模块和根目录的顶层脚本同名, 是有意的: 根目录那个只做配置和编排, 真正的循环逻辑在包里这个同名模块, 名字对齐是想让人一眼看出这两个文件是一对), 每个实例对应一个 dataset 的一整套 review → fix 循环, 内部维护两个持久化的 SDK session, 按 [02-two-session-review.md](02-two-session-review.md) 里讲的协议, 一轮一轮跑下去. 轮数默认是 3 到 4 轮, 具体是 `DEFAULT_MAX_ROUNDS`, 和 review/fix 各自用的模型, effort 等级, 单 session 的 turn 上限一样, 全部参数化, 都能在 [review_and_fix_loop.py](../review_and_fix_loop.py) 顶部直接改, 想给某个 dataset 单独调参, 把那一行 `ReviewAndFixLoop(...)` 展开, 传不同的关键字参数即可.

---

## 3. 人类该在哪儿使劲, 该在哪儿放手

自动循环不是拿到一句话描述就能直接跑的起点. 推荐的完整工作流是, 先用 [fake-data-generator](../.claude/skills/fake-data-generator/SKILL.md) skill, 至少三到五轮人机对话, 把这份数据集的业务背景和故事打磨清楚, 这一步人要出的力气, 是 project framing 选得对不对, 业务问题挑得对不对, 这种需要取舍和判断的逻辑决策, 不是那些字段命名有没有对齐, 分布参数有没有精确匹配这类细节一致性问题, 那些细节从一开始就不该指望人来改.

业务框架定型之后, 建议 (但不是必须) 人类自己手动跑一轮 review, 用这一轮把最重要的几个问题挑出来, 该怎么取舍, 心里有个数, 这一轮相当于人把大方向上的判断力用在刀刃上, 剩下那些细枝末节的判断留给 AI 去处理. 这一步不做也没关系, 直接进自动循环也是可以接受的, 只是提前手动跑一轮更稳妥.

到这一步之后才是把 dataset 名字加进 `DATASET_NAMES`, 跑 [review_and_fix_loop.py](../review_and_fix_loop.py), 让它无人值守跑完设定的轮数. 循环跑完之后, 回来看 `review-NN.md` 和 `fix-NN.md` 这些落盘的记录, 确认收敛到了预期的状态.
