# Claude Code: Skills, Subagents, and Slash Commands

A practical reference for when to use each extension primitive.

---

## 1. Definitions

**Agent Skill** — `.claude/skills/<skill-name>/SKILL.md`
A directory containing a `SKILL.md` file (YAML frontmatter + Markdown body), optionally bundled with scripts, references, and assets. Runs **inline** in the main conversation thread. Can be invoked by you (`/skill-name`), by Claude automatically (based on `description` matching), or both. Follows the open Agent Skills standard, with Claude Code–specific extensions layered on top.

**Subagent** — `.claude/agents/<agent-name>.md`
A single Markdown file (YAML frontmatter + system prompt) that defines an isolated worker. Runs in its **own fresh context window**, with its own tools, permissions, and optionally its own model. Only its final result returns to the main conversation — none of its intermediate work (file reads, searches, tool calls) enters your context. Invoked via the Task tool, either by Claude's own judgment or by you naming it in natural language.

**Slash Command** — `.claude/commands/<command-name>.md`
The legacy format: a bare Markdown file, manually triggered via `/command-name`, optionally with `$ARGUMENTS`. No directory, no bundled files, no Claude Code extension fields. Still supported for backward compatibility.

---

## 2. Why commands are effectively obsolete

Every capability of `.claude/commands/` is a strict subset of `.claude/skills/`:

| | Legacy command | Skill |
|---|---|---|
| `/name` manual invocation | ✅ | ✅ |
| Auto-invocation by Claude | ❌ | ✅ (via `description`) |
| Bundled scripts/references/assets | ❌ | ✅ |
| `context: fork`, `model`, `allowed-tools`, etc. | ❌ | ✅ |

A skill with `disable-model-invocation: true` reproduces the exact behavior of a legacy command (manual-only, no auto-firing) while still gaining directory structure and every Claude Code extension field. Anthropic's own docs now describe `.claude/commands/` as legacy and recommend `.claude/skills/<name>/SKILL.md` going forward. **There is no reason to create new files in `.claude/commands/`.**

---

## 3. Skill vs. Subagent: the real dividing line

It's not about whether the task has "clear input/output boundaries" — almost anything can be framed that way. The actual question:

> **Do you need to see and steer the intermediate steps, or do you only care about the final result?**

- **Need visibility / want to interject mid-process** → **Skill**. It plays out inline, in the main thread. You can watch it reason, correct it, ask follow-ups mid-task.
- **Intermediate steps are noise you'll never reference again** → **Subagent**. It runs in an isolated context window; only the final message comes back. Ideal for things like scanning 30 files to trace an auth flow — you don't need those 30 reads cluttering your session.

**Shared capability, different scope:** both skills and subagents support a `model` field to override the inherited model (`sonnet`, `opus`, `haiku`, or a full model ID). The scope differs:
- On a **skill**, the override is temporary — the session model resumes once the skill finishes.
- On a **subagent**, the override applies for that agent's entire run.

**Key asymmetry — no slash command for subagents:** a subagent has no `/agent-name` entry point. It can only be invoked via natural language (Claude deciding to delegate, or you explicitly naming it: "use the research-summarizer agent") or by starting the whole session as that agent (`claude --agent <name>`). Skills, by contrast, always get a `/skill-name` shortcut for free.

**Composability:** skills and subagents aren't mutually exclusive. A skill with `context: fork` hands its own body off as the task prompt to an isolated subagent — the skill defines *what to do*, the subagent provides *where to do it in isolation*. This only works when the skill body contains explicit, actionable instructions; reference-only content (style guides, conventions) forked into a subagent produces no meaningful output, since the subagent gets guidance but no task.

---

## 4. Best practice: skill as the "caller," subagent as the "doer"

Because subagents lack a slash-command entry point, the recommended pattern is:

> **Write a skill whose only job is to invoke a specific subagent with a clear task, and let the skill provide the `/name` shortcut.**

This gets you:
- A memorable, discoverable `/name` trigger (which subagents alone can't provide)
- Full context isolation for the actual work (via the subagent)
- The option to still let Claude auto-invoke the skill when relevant, on top of manual triggering

Example shape:

```
---
name: audit-deps
description: Audit all dependencies for outdated or vulnerable packages. Use when checking for security issues or update opportunities.
---
Delegate to the dependency-auditor subagent with the following task:
Scan the repository for outdated or vulnerable dependencies across all
package manifests. Return a prioritized summary — do not modify any files.
```

The skill is the front door; the subagent does the (potentially noisy) legwork in isolation and reports back a clean summary.

---

## Additional notes worth keeping in mind

- **Portability boundary:** only `name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools` belong to the open Agent Skills standard. `model`, `context: fork`, `disable-model-invocation`, `user-invocable`, and the entire subagent frontmatter schema are Claude Code–specific extensions. A skill using only the standard fields is portable across tools; anything beyond that is Claude Code–only.
- **Two separate invocation knobs on skills:** `disable-model-invocation: true` (Claude can't auto-fire it) and `user-invocable: false` (you can't manually fire it) are independent. Setting both makes the skill unreachable by anyone — use one or the other, not both.
- **Context persistence differs sharply:** once a skill is invoked, its rendered content stays in the conversation for the rest of the session (and gets re-injected after compaction, oldest first if space runs out). A subagent's internal work never enters main context at all — only its final message does.
- **Batch model default for subagents:** setting `CLAUDE_CODE_SUBAGENT_MODEL` lets you run the main session on one model (e.g., Opus) while every subagent left on `model: inherit` defaults to another (e.g., Sonnet), without editing each agent file individually.
- **Nesting:** subagents can nest up to five levels deep, enabling dynamic multi-agent orchestration without hand-specifying every layer.
