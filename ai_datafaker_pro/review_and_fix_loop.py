# -*- coding: utf-8 -*-

"""
ReviewAndFixLoop: a multi-round review-then-fix improvement loop for a
single dataset that is already in 0.2.1 layout.

================================================================================
1. 这个 task 在做什么
================================================================================

拿一个已经存在的 dataset 目录 (必须是 0.2.1 layout, 四份 -cn 文件齐全),
自动跑 N 轮 "review → fix" 流水线, 把数据集打磨到可发布质量, 全程无人值守.

如果 dataset 还是 0.1.1 layout, 请先跑 ``upgrade_legacy_datasets.py`` 升级到
0.2.1, 再跑这个 loop. ``__post_init__`` 会在构造时就把缺文件的 dataset 拦下.

================================================================================
2. 两个 Skill: 生成数据 vs 评审数据
================================================================================

项目里有两个互补的 skill (放在 ``.claude/skills/`` 下):

  .claude/skills/fake-data-generator/SKILL.md
    生成 / 修改 dataset. 可以从零搭, 也可以修改一个已有 dataset.

  .claude/skills/review-fake-data-generator/SKILL.md
    用领域专家视角审查一个已有 dataset, 分 4 个 stage 输出问题清单:
      Stage 1: 业务背景文档 (公司 / 行业 / 项目 / 业务问题 / 术语表 / 指标公式)
      Stage 2: ER 文档 (Mermaid / schema / 实体完整性 / 不变式声明 / 业务陷阱)
      Stage 3: SQL queries (教学口吻 / 业务语义 / 正确性 / 跨 query 一致性)
      Stage 4: data_generator-cn.py + 跑 sqlite3 实测验证业务陷阱在数据里真的落地

业务文档 (4 份 -cn 文件) 是**作者已经定型的 ground truth**.
本流程**不重新协商业务设定**, 只验证实现是否忠实兑现.

================================================================================
3. Session 拓扑 (无论 max_rounds 多大, 全程只有 2 个 subprocess)
================================================================================

    [Review SDK Client]  ─ R1 prompt ──> Read 四份 -cn 文件 ──> Write review-01.md
                         ─ R2 prompt ──> 重新 Read (上一轮 Fix 改过了) ──> Write review-02.md
                         ─ R3 prompt ──> ...
                              ▲
                              │ 同一 ClaudeSDKClient, 同一 subprocess.
                              │ R2/R3/R4 都能看到 R1 的对话历史.

    [Fix    SDK Client]  ─ R1 prompt ──> Read review-01.md ──> Edit + 跑 generator ──> Write fix-01.md
                         ─ R2 prompt ──> Read review-02.md ──> Edit + 跑 generator ──> Write fix-02.md
                         ─ R3 prompt ──> ...
                              ▲
                              │ 另一个 ClaudeSDKClient, 另一个 subprocess.
                              │ 跨 round 累积上下文, 但跟 Review session 互不知情.

时间上一轮内 review 串行先跑, fix 后跑. 两个 client 各自维护一个 async with.

================================================================================
4. 关键反模式防御
================================================================================

  - 严令**先 Write fix-NN.md 再跑 generator 验证**. 因为 generator 跑一次可能要
    几分钟 (输出几十 MB SQLite), 中途如果被 Ctrl-C, fix-NN.md 也已经落盘了,
    下一轮 Review 不会因为找不到 fix 结论直接走空.
  - 禁止在 dataset 目录里写临时验证脚本 (_verify.py / sim_*.py / tmp_*.py).
    模型有强烈倾向在长 prompt 下 "主动" 造验证脚本, 会吃 turns 也容易卡住.
  - 禁止 ``time python ...`` 写法 — shell builtin, 会增加输出和等待行为.
  - 所有路径都用绝对路径, 防止 ``cd`` 之后相对解析错位.

================================================================================
5. 怎么用
================================================================================

Python:
    from ai_datafaker_pro.dataset import Dataset
    from ai_datafaker_pro.review_and_fix_loop import ReviewAndFixLoop
    import asyncio

    task = ReviewAndFixLoop(
        dataset=Dataset.from_name("b2b_saas_demand_generation_high"),
        max_rounds=4,
    )
    asyncio.run(task.run())

可调参数 (Command Pattern, 都是 dataclass 字段):
    dataset             Dataset 实例 (必填)
    max_rounds          review+fix 轮数 (默认 4)
    review_model        review session 模型 (默认 "opus")
    review_effort       review session effort 等级 (默认 "xhigh")
    review_max_turns    review session 单 session 内 turn 上限 (默认 80)
    fix_model           fix session 模型 (默认 "opus")
    fix_effort          fix session effort 等级 (默认 "xhigh")
    fix_max_turns       fix session 单 session 内 turn 上限 (默认 200)

================================================================================
6. Log 风格
================================================================================

任务级头两行无 elapsed:
    ===== Improvement Task "<dataset_name>" =====
    Started at: YYYY-MM-DD-HH-MM-SS (local)

之后每一行 log 都带 ``[HH:MM:SS +Xs] / +XmYs / +XhYmZs`` 前缀. 例:
    [00:18:32 +1s] ----- Review 01 -----
    [00:19:48 +1m16s]   [Read] /Users/.../02-foo_er_document-cn.md
    [01:23:45 +1h5m13s]   [Bash] /Users/.../.venv/bin/python /Users/.../generator.py

不打印: thinking block (effort=xhigh 产物很多, 噪音太大), UserMessage 工具结果.

``_probe_client`` 在 pre-query / post-query / post-response 三个时刻打底层状态
(subprocess.returncode, transport._ready 等), 排查 session 是否健康.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
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


DEFAULT_MAX_ROUNDS = 4
DEFAULT_REVIEW_MODEL = ModelEnum.opus.value
DEFAULT_REVIEW_EFFORT = EffortEnum.xhigh.value
DEFAULT_REVIEW_MAX_TURNS = 80
DEFAULT_FIX_MODEL = ModelEnum.opus.value
DEFAULT_FIX_EFFORT = EffortEnum.xhigh.value
DEFAULT_FIX_MAX_TURNS = 200


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


def _base_options(
    *,
    skills: list[str] | None,
    model: str,
    effort: str,
    max_turns: int,
) -> ClaudeAgentOptions:
    """Build session options.

    - ``permission_mode="acceptEdits"``: auto-approve Write/Edit/MultiEdit and
      common filesystem commands (mkdir/touch/mv/cp).
    - ``allowed_tools`` includes ``"Bash"``: any bash command (including
      ``python /abs/path.py``) is pre-approved.

    Net result: editing files + running scripts is allowed by default,
    which is exactly what an unattended improvement loop needs.
    """
    return ClaudeAgentOptions(
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
        skills=skills,
        max_turns=max_turns,
        model=model,
        effort=effort,
    )


@dataclass
class ReviewAndFixLoop:
    """A multi-round review→fix loop on one dataset (Command Pattern).

    A dataclass. Every per-task knob is a declared field with a sensible
    default. Construct, then call ``await task.run()`` (or wrap with
    ``asyncio.run``).

    The dataset must be in 0.2.1 layout. If any of the four ``-cn``
    artifacts is missing, ``__post_init__`` raises ``FileNotFoundError``
    immediately so the failure is visible at construction time, not
    after the first SDK roundtrip.

    Fields:
        dataset: The Dataset to improve. Must be 0.2.1 layout.
        max_rounds: Number of review+fix iterations (default 4).
        review_model: Claude model for the review session (default ``"opus"``).
        review_effort: Effort level for the review session (default ``"xhigh"``).
        review_max_turns: Turn limit per review session (default 80).
        fix_model: Claude model for the fix session.
        fix_effort: Effort level for the fix session.
        fix_max_turns: Turn limit per fix session (default 200; fix is
            heavier because it edits, runs generator, and writes the
            fix-NN.md summary).
        extra_context: Optional free-form project background, injected
            verbatim into **every** review and fix prompt inside a
            delimited block. Use it when the dataset only makes sense in
            the context of a wider project (what the data is ultimately
            for, which invariants are load-bearing, what must not be
            simplified away). Empty string means no block is emitted, so
            existing callers are unaffected.
    """

    dataset: Dataset
    max_rounds: int = DEFAULT_MAX_ROUNDS
    review_model: str = DEFAULT_REVIEW_MODEL
    review_effort: str = DEFAULT_REVIEW_EFFORT
    review_max_turns: int = DEFAULT_REVIEW_MAX_TURNS
    fix_model: str = DEFAULT_FIX_MODEL
    fix_effort: str = DEFAULT_FIX_EFFORT
    fix_max_turns: int = DEFAULT_FIX_MAX_TURNS
    extra_context: str = ""

    # Runtime state, not part of the command spec.
    _run_start: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate the dataset is in 0.2.1 layout and ``max_rounds >= 1``.

        Surfacing the failure here, at construction time, means a
        misconfigured task in ``review_and_fix_loop.py`` blows up
        before the first SDK subprocess is even spawned.
        """
        ds = self.dataset
        missing: list[str] = []
        if ds.business_context_cn is None:
            missing.append("*business_context-cn.md")
        if ds.er_document_cn is None:
            missing.append("*er_document-cn.md")
        if ds.sql_queries_cn is None:
            missing.append("*sql_queries-cn.md")
        if ds.data_generator_cn is None:
            missing.append("*_data_generator-cn.py")
        if missing:
            raise FileNotFoundError(
                f"dataset {ds.name!r} is not in 0.2.1 layout: missing "
                f"{missing}. Run the upgrade pipeline first."
            )
        if self.max_rounds < 1:
            raise ValueError(
                f"max_rounds must be >= 1, got {self.max_rounds}"
            )

    # ---------- per-round paths ----------

    def _review_md_path(self, round_no: int) -> Path:
        """Absolute path to the ``review-NN.md`` file produced by the review session."""
        return self.dataset.dataset_dir / f"review-{round_no:02d}.md"

    def _fix_md_path(self, round_no: int) -> Path:
        """Absolute path to the ``fix-NN.md`` file produced by the fix session."""
        return self.dataset.dataset_dir / f"fix-{round_no:02d}.md"

    # ---------- logging ----------

    def _log(self, msg: str) -> None:
        """Print one log line with ``[HH:MM:SS +elapsed]`` prefix.

        Before ``run()`` is called the elapsed is omitted.
        """
        now = time.time()
        hms = time.strftime("%H:%M:%S", time.localtime(now))
        if self._run_start is None:
            print(f"[{hms}] {msg}")
        else:
            delta = int(now - self._run_start)
            print(f"[{hms} +{_format_elapsed(delta)}] {msg}")

    def _probe_client(self, label: str, client: ClaudeSDKClient) -> None:
        """Diagnose the SDK client's underlying state at a check point.

        Prints:
          - ``_query._closed``: SDK-level closed flag.
          - ``subprocess.returncode``: None=alive, otherwise the exit code.
          - ``transport._ready``: whether transport is writable.
          - ``stdin_open``: whether stdin is still open.
          - ``exit_error``: transport's recorded exit error, if any.

        Used at pre-query / post-query / post-response of every turn so a
        hung session shows up as a clear log artefact rather than silence.
        """
        q = getattr(client, "_query", None)
        closed = getattr(q, "_closed", "?") if q is not None else "?"
        transport = getattr(client, "_transport", None)
        proc = getattr(transport, "_process", None) if transport is not None else None
        rc = proc.returncode if proc is not None else "?"
        ready = getattr(transport, "_ready", "?") if transport is not None else "?"
        stdin_open = (
            getattr(transport, "_stdin_stream", None) is not None
            if transport is not None
            else "?"
        )
        exit_err = (
            getattr(transport, "_exit_error", None) if transport is not None else None
        )
        self._log(
            f"  [diag {label}] _query._closed={closed} subprocess.returncode={rc} "
            f"transport._ready={ready} stdin_open={stdin_open} exit_error={exit_err!r}"
        )

    @staticmethod
    def _format_block(block: object) -> str | None:
        """Format one AssistantMessage content block as a log line.

        Returns None for blocks that should not produce log output
        (thinking blocks, unknown shapes).
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

    # ---------- prompt builders ----------

    def _context_block(self) -> str:
        """Wrap ``extra_context`` in a delimited block, or return empty string.

        Emitted at the top of every turn's prompt (after the slash command
        on round 1, since the slash command must lead the message for the
        skill to trigger). Repeating it every round is deliberate: both
        sessions accumulate a lot of history, and the project framing is
        exactly the thing that gets crowded out first.
        """
        text = self.extra_context.strip()
        if not text:
            return ""
        return (
            "===== 项目背景 (每一轮都重新读一遍, 不要只依赖 context 里的记忆) =====\n"
            f"{text}\n"
            "===== 项目背景结束 =====\n\n"
        )

    def _review_prompt(self, round_no: int) -> str:
        """Build the review prompt for round ``round_no``.

        R1: explicit slash command to trigger the skill plus full absolute
        paths to the four ``-cn`` artifacts.
        R2+: same review session, the prompt is shorter and relies on the
        cross-turn context the SDK keeps.
        """
        ds = self.dataset
        tag = f"{round_no:02d}"
        review_md = self._review_md_path(round_no)

        if round_no == 1:
            head = f"/review-fake-data-generator {ds.dataset_dir}\n\n"
            return head + self._context_block() + dedent(f"""\
                这次是 Review {tag}:

                请详细深入审查 data faker 的四份业务文件 + 代码, 并给出修改意见.

                目标文件 (全部使用绝对路径):
                  - 业务背景 (-cn): {ds.business_context_cn}
                  - ER doc (-cn):  {ds.er_document_cn}
                  - SQL queries (-cn): {ds.sql_queries_cn}
                  - 数据生成脚本 (-cn): {ds.data_generator_cn}

                业务文档 (4 份 -cn 文件) 已经定型, 业务背景以业务文档为准.
                Cardinal principle: 精修, 不重新设计. 不要质疑业务设定本身, 只关注:
                - 业务背景文档与 ER / SQL / generator 之间是否一致 (有没有自相矛盾)
                - schema / 数据生成代码 是否忠实兑现了业务文档里的字段, 关系, 不变式
                - SQL queries 的教学口吻 / 业务语义 / 正确性 / 跨 query 一致性
                - 字段分布, 时间排序, 跨表引用一致性等数据质量问题
                - 如有 sqlite 数据库, 用 sqlite3 跑几条 SQL 实测业务陷阱是否落地

                在聊天中简短回复摘要既可, 详细修改意见写入 (绝对路径):
                {review_md}

                请用中文跟我交互.
            """)

        prev = f"{round_no - 1:02d}"
        prev_fix = self._fix_md_path(round_no - 1)
        return self._context_block() + dedent(f"""\
            这次是 Review {tag}:

            作者已经根据 Review {prev} 的修改意见进行了修改 (修改记录在:
            {prev_fix}). 请重新审查:

            - 看是否已经修复了之前发现的问题
            - 这次修复是否引入了新问题
            - 整体一起看是否还有遗漏的新问题

            注意: 四份目标文件 (业务背景 / ER doc / SQL queries / generator.py)
            上一轮可能已经被改过了, 你 context 里记得的版本是旧的,
            **请重新 Read 一遍**再下判断.

            详细修改意见写入 (绝对路径): {review_md}

            如果你认为本数据集已经足够干净, 没有需要修改的 P0 / P1 项, 也请在
            上面这个 review-{tag}.md 中明确写出 "无需修改" 并给出理由.

            请用中文跟我交互.
        """)

    def _fix_prompt(self, round_no: int) -> str:
        """Build the fix prompt for round ``round_no``.

        R1: explicit slash command + absolute paths. R2+: relies on the
        fix session's cumulative history. All rounds enforce the
        "Write fix-NN.md before running the generator" rule so an
        interrupted run still leaves a usable summary on disk.
        """
        ds = self.dataset
        tag = f"{round_no:02d}"
        review_md = self._review_md_path(round_no)
        fix_md = self._fix_md_path(round_no)

        # Hard constraints shared by every fix turn. Built as a list+join
        # rather than a nested f-string, so dedent's indentation parsing
        # does not fight with multi-line dynamic content.
        constraints = "\n".join([
            "执行约束 (硬性, 不要违反):",
            "- 所有 Read/Edit/Write 都使用绝对路径 (上面已经给出).",
            "- 跑数据生成或验证脚本时, 必须用这个 venv 的 python 解释器:",
            f"  `{PYTHON_BIN}`",
            "  不要用裸 `python`, 不要 `source activate`, 也不要写 `time python`.",
            "- **关键顺序: 先把 fix-NN.md 总结写出来, 再去跑 generator 验证.**",
            "  因为 generator 跑一次可能要好几分钟 (输出 SQLite 可能几十 MB),",
            "  中途若被打断, 必须保证 fix-NN.md 已经落盘. 验证通过/失败的细节可以",
            "  fix-NN.md 之后再补写一段 '验证结果'.",
            "- 不要在 dataset 目录里新增任何临时文件 (_verify.py / sim_*.py / tmp_*.py",
            "  等都不要). 验证就只跑 generator 本身, 它自带的 print 已经够用.",
            "- 不要重新走 fake-data-generator 的 Phase 0 / 1 / 2 (行业 / 用例 / 复杂度选择),",
            "  dataset 名字已经定型, 直接进入修复模式.",
            "- 不要调用 AskUserQuestion, 任何不确定的小细节自己拿主意.",
        ])

        if round_no == 1:
            head = f"/fake-data-generator {ds.dataset_dir}\n\n"
            body = head + self._context_block() + dedent(f"""\
                这次是修复 Review {tag} 中的修改意见. 修改意见在 (绝对路径):
                {review_md}

                目标文件 (全部使用绝对路径):
                  - 业务背景 (-cn): {ds.business_context_cn}
                  - ER doc (-cn):  {ds.er_document_cn}
                  - SQL queries (-cn): {ds.sql_queries_cn}
                  - 数据生成脚本 (-cn): {ds.data_generator_cn}

                业务文档 (4 份 -cn 文件) 是 ground truth. 以业务为准做数据.
                数据复杂度已经在创建时定型 (medium / high / large), 不要降低复杂度.

                请根据评审意见, 决定哪些接受, 哪些拒绝:
                - 接受的修改: 自主决定如何修改并执行, 任何细节自己拿主意.
                - 拒绝的修改: 不要打断我, 在 fix-NN.md 中写明拒绝理由.

                流程 (严格按顺序执行):
                  1. Read review-{tag}.md 拿到修改清单.
                  2. 必要的 Read 业务文件了解上下文 (4 份 -cn 文件: 业务背景 / ER / SQL / generator).
                  3. 用 Edit/MultiEdit 改业务背景 / ER doc / SQL doc / generator.py.
                  4. **立刻** Write fix-NN.md 总结这一轮做了什么 (绝对路径):
                     {fix_md}
                     即使还没跑 generator 验证, 也要先把 fix-NN.md 落盘.
                  5. 跑 generator 验证: `{PYTHON_BIN} {ds.data_generator_cn}`
                  6. 验证结果 (成功/失败 + 关键观察) 再 Edit 追加到 fix-NN.md 末尾.
            """)
            return f"{body}\n{constraints}\n\n请用中文跟我交互.\n"

        body = self._context_block() + dedent(f"""\
            又让评审审了一遍. 这次是修复 Review {tag} 中的修改意见.
            修改意见在 (绝对路径): {review_md}

            按之前规定的流程: 自主决定如何修改并执行, 任何细节自己拿主意, 不要询问我.

            注意: 四份目标文件 (业务背景 / ER doc / SQL queries / generator.py) 相对
            你 context 里记得的版本可能已经又被改过. 不放心就 Read 一遍当前版本.

            流程 (严格按顺序):
              1. Read review-{tag}.md.
              2. 必要的 Read 当前文件.
              3. 用 Edit/MultiEdit 修改.
              4. **立刻** Write fix-NN.md 落盘 (绝对路径): {fix_md}
              5. 跑 generator 验证: `{PYTHON_BIN} {ds.data_generator_cn}`
              6. 验证结果再追加到 fix-NN.md.

            如果 review-{tag}.md 已经说 "无需修改", 也请在 fix-{tag}.md 中确认并简单收尾.
        """)
        return f"{body}\n{constraints}\n\n请用中文跟我交互.\n"

    # ---------- session runner ----------

    async def _send_turn(
        self,
        name: str,
        client: ClaudeSDKClient,
        prompt: str,
    ) -> ResultMessage:
        """Send one new turn on a persistent client and stream the response.

        Probes the client at pre-query / post-query / post-response so a
        dead subprocess shows up immediately in the log.
        """
        print()  # blank line separator
        self._log(f"----- {name} -----")
        self._probe_client(f"{name} pre-query", client)
        await client.query(prompt)
        self._probe_client(f"{name} post-query", client)
        last: ResultMessage | None = None
        n_assistant = 0
        async for message in client.receive_response():
            if isinstance(message, SystemMessage) and message.subtype == "init":
                # New init message at the start of every turn (not just the first).
                self._log(f"  session_id={message.data.get('session_id')}")
            if isinstance(message, AssistantMessage):
                n_assistant += 1
                for block in message.content:
                    line = self._format_block(block)
                    if line is not None:
                        self._log(f"  {line}")
            if isinstance(message, ResultMessage):
                last = message
                cost = message.total_cost_usd or 0.0
                self._log(
                    f"  -> subtype={message.subtype} cost=${cost:.4f} "
                    f"n_assistant_msgs={n_assistant}"
                )
        if last is None:
            raise RuntimeError(f"{name}: response ended without ResultMessage")
        self._probe_client(f"{name} post-response", client)
        return last

    # ---------- main entry ----------

    async def run(self) -> None:
        """Run the full N-round review→fix loop.

        Two persistent ``ClaudeSDKClient`` subprocesses are opened back to
        back. Inside the nested ``async with`` block we loop ``max_rounds``
        times, sending one review turn then one fix turn per iteration.
        Both clients keep their conversation history across rounds, so
        round N sees everything round N-1 did within the same session.
        """
        ds = self.dataset
        self._run_start = time.time()
        start_str = time.strftime(
            "%Y-%m-%d-%H-%M-%S", time.localtime(self._run_start)
        )

        # Task-level header: the only two lines without an elapsed prefix.
        print(f'===== Improvement Task "{ds.name}" =====')
        print(f"Started at: {start_str} (local)")
        self._log(f"Dataset dir: {ds.dataset_dir}")
        self._log(f"  business context (-cn): {ds.business_context_cn.name}")
        self._log(f"  ER doc (-cn):           {ds.er_document_cn.name}")
        self._log(f"  SQL queries (-cn):      {ds.sql_queries_cn.name}")
        self._log(f"  generator (-cn):        {ds.data_generator_cn.name}")
        self._log(f"  python:                 {PYTHON_BIN}")
        self._log(f"Rounds: {self.max_rounds}")
        self._log(
            f"Extra context: {len(self.extra_context.strip())} chars"
            if self.extra_context.strip()
            else "Extra context: (none)"
        )
        self._log(
            f"Review: model={self.review_model} effort={self.review_effort} "
            f"max_turns={self.review_max_turns}"
        )
        self._log(
            f"Fix:    model={self.fix_model} effort={self.fix_effort} "
            f"max_turns={self.fix_max_turns}"
        )

        review_options = _base_options(
            skills=["review-fake-data-generator"],
            model=self.review_model,
            effort=self.review_effort,
            max_turns=self.review_max_turns,
        )
        fix_options = _base_options(
            skills=["fake-data-generator"],
            model=self.fix_model,
            effort=self.fix_effort,
            max_turns=self.fix_max_turns,
        )

        async with ClaudeSDKClient(options=review_options) as review_client:
            async with ClaudeSDKClient(options=fix_options) as fix_client:
                for round_no in range(1, self.max_rounds + 1):
                    # === Review turn ===
                    await self._send_turn(
                        f"Review {round_no:02d}",
                        review_client,
                        self._review_prompt(round_no),
                    )
                    review_path = self._review_md_path(round_no)
                    if not review_path.exists():
                        self._log(
                            f"  WARNING: expected {review_path.name} not found"
                        )

                    # === Fix turn ===
                    await self._send_turn(
                        f"Fix {round_no:02d}",
                        fix_client,
                        self._fix_prompt(round_no),
                    )
                    fix_path = self._fix_md_path(round_no)
                    if not fix_path.exists():
                        self._log(
                            f"  WARNING: expected {fix_path.name} not found"
                        )

        print()
        self._log(f"===== Done: {self.max_rounds} review+fix round(s) =====")
