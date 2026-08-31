# -*- coding: utf-8 -*-

"""
UpgradeTask: take a legacy (0.1.1 layout) dataset and upgrade it in-place
to the current 0.2.1 spec.

================================================================================
1. 这个 task 在做什么
================================================================================

0.1.1 layout (旧):

    dataset/<name>/
      <name>_data_generator.py        # 单一 Python, 一般是英文注释
      <name>_er_document-cn.md        # ER 文档 (含业务背景章节)
      <name>_er_document.md           # 英文 ER 文档
      <name>_sql_queries-cn.md        # 20 条 SQL queries
      <name>_sql_queries.md           # 英文 SQL queries
      <name>.sqlite
      data/

0.2.1 layout (新):

    dataset/<name>/
      01-<name>_business_context-cn.md   # 业务背景独立成文 (新建)
      02-<name>_er_document-cn.md        # 纯数据文档
      03-<name>_sql_queries-cn.md        # 教学口吻的 SQL queries
      04-<name>_data_generator-cn.py     # 中文注释的 Python
      <name>.sqlite
      data/
      (01-...04- 的 .md 英文版稍后由 translate-to-en 一次性产出)

升级的工作:
  * 信息基本不动. 业务设定 / 表结构 / 字段 / 数据分布 全部维持原样.
  * 重组. 把业务背景从 ER 文档抽离出去, 写到新的 business_context-cn.md.
  * 重命名. 四份核心文件加 `NN-` 前缀, generator 加 `-cn` 后缀.
  * 翻译 generator 注释. 把 generator 里的英文 docstring/注释翻成中文,
    SQLAlchemy 模型, Faker 调用, 业务常量等代码本身保持不变.
  * 清理. 删除旧的英文版 ER / SQL 文档 (translate-to-en 会重新生成).
  * 验证. 跑一遍 generator 确认 sqlite 和 TSV 还能正常产出.

业务背景的"补充"部分严格按 fake-data-generator 的
references/business_context_guidance.md 9 个 content beat 来写:
公司, 商业模式, 行业概览, 项目框架, 业务问题, 数据范围, 行业知识科普,
术语表, 关键指标公式. 这些信息原本散落在 ER 文档里, 这一步只是搬家+
按规范补全, 不重新设计.

================================================================================
2. 怎么用
================================================================================

Python:
    from ai_datafaker_pro.dataset import Dataset
    from ai_datafaker_pro.upgrade_task import UpgradeTask
    import asyncio

    task = UpgradeTask(dataset=Dataset.from_name("foo_bar_high"))
    asyncio.run(task.run())

可调参数 (Command Pattern, 都是 __init__ 的关键字参数):
    dataset      Dataset 实例 (必填)
    model        Claude 模型 (默认 "opus")
    effort       effort 等级 (默认 "xhigh")
    max_turns    单 session 内 turn 上限 (默认 200, 升级任务通常不需要这么多)

================================================================================
3. Log 风格
================================================================================

跟 review_and_fix_loop.py 完全一致. 任务级头两行无 elapsed, 之后每行都带
[HH:MM:SS +elapsed] 前缀. tool_use / text block / SystemMessage(init) /
ResultMessage 都会打印.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass
from dataclasses import field
from textwrap import dedent

from claude_agent_sdk import AssistantMessage
from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk import ResultMessage
from claude_agent_sdk import SystemMessage

from .dataset import Dataset
from .paths import path_enum


PROJECT_ROOT = path_enum.dir_project_root
PYTHON_BIN = path_enum.path_venv_bin_python


class ModelEnum(enum.StrEnum):
    haiku = "haiku"
    sonnet = "sonnet"
    opus = "opus"


class EffortEnum(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"
    max = "max"


DEFAULT_MODEL = ModelEnum.opus.value
DEFAULT_EFFORT = EffortEnum.xhigh.value
DEFAULT_MAX_TURNS = 200


def _format_elapsed(secs: int) -> str:
    """Format elapsed seconds as Xs / XmYs / XhYmZs."""
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        m, s = divmod(secs, 60)
        return f"{m}m{s}s"
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m}m{s}s"


@dataclass
class UpgradeTask:
    """Upgrade one dataset from 0.1.1 layout to 0.2.1 layout (Command Pattern).

    A dataclass: each per-task knob is a declared field. Construct directly
    via the auto-generated ``__init__`` and call ``await task.run()`` (or wrap
    with ``asyncio.run``).

    A second invocation against the same dataset is safe; the agent prompt
    asks it to skip steps that are already done.

    Fields:
        dataset: The Dataset to upgrade.
        model: Claude model name (default ``"opus"``).
        effort: Effort level (default ``"xhigh"``).
        max_turns: Max turns per SDK session (default 200). Upgrade is a
            one-shot job, so 200 is comfortably above what is needed.
    """

    dataset: Dataset
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    max_turns: int = DEFAULT_MAX_TURNS

    # Runtime state, not part of the command spec. Set in ``run()``; read by
    # ``_log()`` to compute the elapsed prefix on each log line.
    _run_start: float | None = field(default=None, init=False, repr=False)

    # ---------- logging ----------

    def _log(self, msg: str) -> None:
        """Print one log line with ``[HH:MM:SS +elapsed]`` prefix.

        Before ``run()`` is called the elapsed is omitted. Same behaviour
        as ``review_and_fix_loop.py``.
        """
        now = time.time()
        hms = time.strftime("%H:%M:%S", time.localtime(now))
        if self._run_start is None:
            print(f"[{hms}] {msg}")
        else:
            delta = int(now - self._run_start)
            print(f"[{hms} +{_format_elapsed(delta)}] {msg}")

    @staticmethod
    def _format_block(block: object) -> str | None:
        """Format one AssistantMessage content block as a log line.

        Returns None for blocks that should not produce log output
        (thinking blocks, unknown shapes). Same logic as
        ``review_and_fix_loop.py``.
        """
        tool_name = getattr(block, "name", None)
        if tool_name:
            tool_input = getattr(block, "input", {}) or {}
            if tool_name in ("Write", "Edit", "MultiEdit", "Read"):
                fp = tool_input.get("file_path", "?")
                return f"[{tool_name}] {fp}"
            if tool_name == "Bash":
                cmd = (tool_input.get("command") or "")[:140]
                return f"[Bash] {cmd}"
            if tool_name == "Glob":
                pattern = tool_input.get("pattern", "?")
                path = tool_input.get("path", "")
                return f"[Glob] pattern={pattern}" + (f" path={path}" if path else "")
            if tool_name == "Grep":
                pattern = tool_input.get("pattern", "?")
                path = tool_input.get("path", "")
                return f"[Grep] pattern={pattern}" + (f" path={path}" if path else "")
            if tool_name == "Skill":
                skill = tool_input.get("skill", "?")
                args = tool_input.get("args", "")
                return f"[Skill] {skill}" + (f" args={args[:80]}" if args else "")
            snippet = str(tool_input)[:100]
            return f"[{tool_name}] {snippet}"
        text = getattr(block, "text", None)
        if text:
            single = text.replace("\n", " ⏎ ")
            if len(single) > 80:
                single = single[:80] + "…"
            return f"[text] {single}"
        return None

    # ---------- prompt builder ----------

    def _upgrade_prompt(self) -> str:
        """Build the single comprehensive upgrade prompt.

        One prompt drives the whole upgrade. The agent reads, renames,
        rewrites, runs the generator to verify, and writes ``upgrade.md``
        summarising the changes. The prompt is idempotent-aware: if any
        step is already done, the agent should skip it rather than redo.
        """
        ds = self.dataset
        upgrade_md = ds.dataset_dir / "upgrade.md"
        target_bc = ds.dataset_dir / f"01-{ds.name}_business_context-cn.md"
        target_er = ds.dataset_dir / f"02-{ds.name}_er_document-cn.md"
        target_sql = ds.dataset_dir / f"03-{ds.name}_sql_queries-cn.md"
        target_gen = ds.dataset_dir / f"04-{ds.name}_data_generator-cn.py"

        return dedent(f"""\
            /fake-data-generator {ds.dataset_dir}

            这是一个 dataset 升级任务: 把 0.1.1 layout 升级为 0.2.1 spec.

            Dataset name: {ds.name}
            Dataset directory (绝对路径): {ds.dataset_dir}

            原则: **不重新设计, 只重新组织 + 按新规范补充**.
            - 业务设定 (公司, 行业, 项目, 表结构, 字段, 数据分布) 不要改.
            - 中文文档信息已经齐全, 只是组织和命名按旧规范, 缺独立的业务背景文档.
            - 重命名 + 加 `NN-` 前缀, 信息按新规范重新归位.
            - 业务背景按 references/business_context_guidance.md 的 9 个 content beat
              补全 (公司 / 商业模式 / 行业 / 项目 / 业务问题 / 数据范围 / 知识科普 /
              术语表 / 指标公式). 默认市场是北美.

            目标产物 (四份 -cn 文件, 全部加 `NN-` 前缀, 绝对路径):
              {target_bc}
              {target_er}
              {target_sql}
              {target_gen}

            执行步骤 (按顺序, 已经做过的步骤就 skip):

              1. Read 当前的 ER doc (`*_er_document-cn.md`), SQL queries
                 (`*_sql_queries-cn.md`), data_generator (`*_data_generator.py`)
                 了解全貌. 用 Glob 先列目录, 看看现在的命名是什么样.

              2. 创建 `{target_bc}`. 按 business_context_guidance.md 的 9 个
                 content beat 写 (Beat 1 公司 → Beat 9 关键指标公式). 公司画像,
                 商业模式, 行业普及, 项目框架, 业务问题, 数据范围概览, 行业知识
                 科普, 术语表 (英文术语 + 中文 layman 解释), 指标公式都要写到位.
                 默认市场北美 (USD, 北美城市, 北美监管机构).
                 业务信息从现有 ER 文档里搬过来 + 按规范补全, 不要重新设计.

              3. 用 Bash mv 把 `*_er_document-cn.md` 改名为
                 `{target_er}`,
                 然后 Edit 删除已经迁移到业务背景文档里的内容. 文档开头加一行:
                 "业务背景, 行业科普, 术语表请见 01-{ds.name}_business_context-cn.md".
                 确保 ER 文档里有 Mermaid 图 (按 er_document_guidance.md 要求).
                 数据生成规则, 业务陷阱声明, Faker 策略表, DDL 都保留.

              4. 用 Bash mv 把 `*_sql_queries-cn.md` 改名为
                 `{target_sql}`.
                 然后按 sql_queries_guidance.md 检查每个 query 是否满足五段式
                 (业务背景 / 类别难度角色 / 解题思路 / SQL / 期望结果+业务结论).
                 缺什么补什么. **SQL 本身的逻辑不要改**.
                 开头加 "如何使用本文档" 教学型导读段.

              5. 用 Bash mv 把 `*_data_generator.py` 改名为
                 `{target_gen}`.
                 然后 Edit 把英文注释和 docstring 翻译成中文. **代码本身保持
                 不变**: SQLAlchemy 模型, Faker 调用, 业务常量, 函数体逻辑,
                 imports, 变量名都不要碰. 只改注释和 docstring 的语言.

              6. 用 Bash rm 删除旧的英文版文件 (translate-to-en 之后会重新产生):
                 `*_er_document.md` (不带 -cn 的那份)
                 `*_sql_queries.md` (不带 -cn 的那份)
                 注意: 不要删 `.sqlite` 或 `data/`, 不要删上面已经改名过的
                 `_data_generator-cn.py`.

              7. 跑 generator 验证: `{PYTHON_BIN} {target_gen}`
                 确认 sqlite 还在, data/ 下面 TSV 还在, 行数和升级前差不多.
                 升级前可以用 Bash 先记一下 sqlite 大小或 data/ 下文件数, 跑完
                 再对比.

              8. 最后, Write `{upgrade_md}` 总结这次升级做了什么 (中文 Markdown):
                 - 改名了哪些文件
                 - 新建的 business_context-cn.md 从 ER 文档抽取了哪些内容,
                   按 9 个 beat 补全了哪些
                 - generator 验证结果 (成功 / 失败 + 关键观察)
                 - 业务和数据有无实质改动 (应该是无)

            执行约束 (硬性):
              - 全程用绝对路径.
              - 用 venv 的 python: `{PYTHON_BIN}` 跑 generator,
                不要用裸 `python`, 不要 `source activate`.
              - 不要走 Phase 0/1/2 交互确认, 这是已存在 dataset 的升级.
              - 不要 AskUserQuestion, 任何不确定的小细节自己拿主意.
              - 不要在 dataset 目录里写临时验证脚本.
              - 不要碰 review-NN.md / fix-NN.md / upgrade.md 以外的任何额外文件.
              - **关键顺序: 先 Write upgrade.md 把改动总结落盘, 再跑 generator
                验证.** 跑 generator 可能要几分钟, 中途若被打断要保留改动记录.

            请用中文跟我交互.
        """)

    # ---------- main entry ----------

    async def run(self) -> None:
        """Run the upgrade. Single agent session, single comprehensive prompt.

        Topology:

            One persistent ClaudeSDKClient subprocess.
            One prompt sent in.
            Stream the response, log every tool_use / text block.
            Done when ResultMessage arrives.
        """
        ds = self.dataset
        self._run_start = time.time()
        start_str = time.strftime(
            "%Y-%m-%d-%H-%M-%S", time.localtime(self._run_start)
        )

        print(f'===== Upgrade Task "{ds.name}" =====')
        print(f"Started at: {start_str} (local)")
        self._log(f"Dataset dir: {ds.dataset_dir}")
        self._log(f"  legacy layout detected: {ds.is_legacy_layout}")
        self._log(
            f"Model: {self.model} effort: {self.effort} max_turns: {self.max_turns}"
        )
        self._log(f"Python:      {PYTHON_BIN}")

        options = ClaudeAgentOptions(
            cwd=str(PROJECT_ROOT),
            permission_mode="acceptEdits",
            setting_sources=["project"],
            allowed_tools=[
                "Read",
                "Write",
                "Edit",
                "MultiEdit",
                "Glob",
                "Grep",
                "Bash",
                "Skill",
            ],
            skills=["fake-data-generator"],
            max_turns=self.max_turns,
            model=self.model,
            effort=self.effort,
        )

        async with ClaudeSDKClient(options=options) as client:
            print()
            self._log(f"----- Upgrade {ds.name} -----")
            await client.query(self._upgrade_prompt())
            n_assistant = 0
            async for message in client.receive_response():
                if isinstance(message, SystemMessage) and message.subtype == "init":
                    self._log(f"  session_id={message.data.get('session_id')}")
                if isinstance(message, AssistantMessage):
                    n_assistant += 1
                    for block in message.content:
                        line = self._format_block(block)
                        if line is not None:
                            self._log(f"  {line}")
                if isinstance(message, ResultMessage):
                    cost = message.total_cost_usd or 0.0
                    self._log(
                        f"  -> subtype={message.subtype} cost=${cost:.4f} "
                        f"n_assistant_msgs={n_assistant}"
                    )

        print()
        self._log(f"===== Done: upgraded {ds.name} =====")
