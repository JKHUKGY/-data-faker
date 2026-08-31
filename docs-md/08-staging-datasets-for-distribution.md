# 怎么把 dataset 打包给别的地方用

这篇讲 [stage_datasets_to_tmp.py](../stage_datasets_to_tmp.py) 这个脚本. 和 [03-automating-review-and-fix.md](03-automating-review-and-fix.md) 里 [review_and_fix_loop.py](../review_and_fix_loop.py) 与 [ai_datafaker_pro/review_and_fix_loop.py](../ai_datafaker_pro/review_and_fix_loop.py) 的关系一样, 这里也拆成了顶层和底层两块: [stage_datasets_to_tmp.py](../stage_datasets_to_tmp.py) 是根目录下的一个薄封装, 真正的拷贝逻辑都在 [ai_datafaker_pro/staging.py](../ai_datafaker_pro/staging.py) 这个模块里, 顶层脚本只负责读配置, 调用模块里的函数, 把进度打印出来.

---

## 1. 为什么需要一个专门的打包脚本

这个仓库本质上是一个工作目录, 不是一个干净的发布物. 跑一次生成脚本会在 dataset 目录里留下 SQLite 数据库和一整个 `data/` 文件夹的 TSV, 跑一轮 [02-two-session-review.md](02-two-session-review.md) 里讲的 review 和 fix 会留下 `review-NN.md`, `fix-NN.md`. 这些文件都被 `.gitignore` 挡在版本控制之外, 属于过程性产物, 但它们并不会消失, 就静静地留在每个 dataset 的目录里, 跟真正要交付的那八份 Markdown 和 Python 文件混在一起.

真正想做的事情是, 挑出这八份文件, 批量拷贝到别的地方去, 比如喂给另一个工具, 分享给别人, 或者干脆导出去看. 如果直接去 `dataset/<name>/` 目录里手动挑, 每个 dataset 都要在一堆 SQLite 和 TSV 里分辨哪些是真正该带走的文件, 数据集一多, 这件事就变得很烦. `stage_datasets_to_tmp.py` 就是专门解决这个 "挑出来打包" 的问题, 一次跑完, `tmp/stage/` 下就是一份干净的, 只包含八份 canonical 文件的拷贝, 想怎么分发都行. 之所以专门落在 `tmp/stage/` 这一层, 而不是直接落在 `tmp/` 根下, 是因为 `tmp/` 底下还会有别的临时产物, 单独开一个 `stage/` 子目录, 这份一次性打包的结果就不会跟其它东西混在一起.

---

## 2. 两种打包形状: 按 dataset 打包, 按类别打包

脚本一次跑会同时产出两种布局, 服务两种不同的使用场景.

第一种是按 dataset 打包, 落在 `tmp/stage/dataset/<name>/` 下, 一个 dataset 一个文件夹, 里面是它自己的八份文件. 这种形状适合想要完整交付一个 dataset 的场景, 比如把某一个数据集整个发给别人, 拿到的就是一个自包含的文件夹.

第二种是按类别打包, 落在 `tmp/stage/business-context/`, `tmp/stage/er-document/`, `tmp/stage/sql-queries/`, `tmp/stage/data-generator/` 以及各自的 `-cn` 版本这几个共享文件夹下, 每个文件夹汇总了所有 dataset 同一类文件. 这种形状适合想要横向扫一遍所有数据集的某一类文档, 比如想把所有 dataset 的业务背景文件一次性读一遍, 不用一个个进 dataset 目录去找, 一个文件夹里就是全部.

每份文件的文件名已经带了 `NN-<dataset_name>_` 前缀, 天然不会在同一个类别文件夹里重名, 两种布局用的是同一份源文件, 只是摆放方式不同.

---

## 3. 只打包八份 canonical 文件, 每次先整个清空再重建

打包只认 [01-dataset-anatomy.md](01-dataset-anatomy.md) 里定义的那四份核心文件, 中英文各一套, 一共八份: 业务背景, ER 文档, SQL 查询题, 生成脚本. SQLite 数据库, `data/` 下的 TSV, review/fix 这些审计记录, 以及那份给索引用的一行摘要 (`00-<name>_summary*.md`), 都不在打包范围内 — 前几样是跑出来的过程产物, 摘要则是给索引清单用的派生物, 都不属于要交付的 dataset 本身.

`tmp/stage/` 这整个目录只属于这个脚本, 没有别的东西会往里面写. 正因为如此, 每次跑脚本的第一步, 是把 `tmp/stage/` 整个删掉, 再从头重建, 而不是挨个文件夹去比对增量. 这样如果某个 dataset 被重命名或者删掉了, 它的旧痕迹不会留在任何一个角落, `tmp/stage/` 里的内容永远精确对应当前 `dataset/INDEX-cn.md` 里登记的那份列表, 不会有过期的残留文件混在里面误导人.

---

## 4. 和 review, fix 一样的顶层, 底层结构

复制逻辑 (`parse_dataset_names`, `stage_dataset`, `stage_categories` 这些函数) 都在 [ai_datafaker_pro/staging.py](../ai_datafaker_pro/staging.py) 这个模块里, 和 `dataset.py` 里的 `Dataset`, `paths.py` 里的 `path_enum` 平级. 根目录下的 [stage_datasets_to_tmp.py](../stage_datasets_to_tmp.py) 只有一个 `main()`, 负责串起流程和打印进度, 不直接持有拷贝逻辑.

这和 [03-automating-review-and-fix.md](03-automating-review-and-fix.md) 里 [review_and_fix_loop.py](../review_and_fix_loop.py) 与 [ai_datafaker_pro/review_and_fix_loop.py](../ai_datafaker_pro/review_and_fix_loop.py) 的关系是同一个模式: 有实际业务逻辑的代码放进 `ai_datafaker_pro` 库, 根目录下的脚本只做配置和编排, 保持薄. 以后如果有别的地方 (比如一次性脚本, 或者一个新的 CLI 命令) 想复用同一份打包逻辑, 直接 `import ai_datafaker_pro.staging` 就行, 不需要再复制一遍代码.
