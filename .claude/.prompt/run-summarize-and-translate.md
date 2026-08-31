/run-summarize-and-translate

下面的每一个 Folder 是已经用 fake-data-generator 做完中文四件套、并且用户已经签字确认的产出物. 请将每一个 Folder 视为一个 Task:

```
/path/to/ai_datafaker_pro-project/dataset/<dataset-name-1>
/path/to/ai_datafaker_pro-project/dataset/<dataset-name-2>
```

请对每一个 Task 执行 run-summarize-and-translate Skill 中定义的操作: 先给这个 dataset 写一行中文摘要 (00-<name>_summary-cn.md), 再把包括这份摘要在内的所有 -cn.md / -cn.py 翻译成对应的英文文件.

注意, 对于每个 Folder, 我们必须是串行一个个去执行. 由于 run-summarize-and-translate Skill 内部会先派一个 dataset-digest subagent 写摘要, 再派多个 translator subagent 并行翻译, 如果我们连 Task 也并行, 则会导致 launch 太多 subagent 导致错误率飙升, 得不偿失.

请执行吧.
