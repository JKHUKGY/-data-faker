---
name: skill-subagent-design
description: How Agent Skills and Subagents differ and how to combine them — the skill-as-caller / subagent-as-doer best practice. Use when deciding whether a task should be a skill or a subagent, or when authoring a skill and subagent that work together (e.g. a /name skill that delegates to an isolated subagent).
---
Read references/claude-code-skills-subagents-and-slash-commands.md before designing any skill + subagent combination. It covers the real dividing line between a skill and a subagent (visibility/steering vs. isolated result), why legacy slash commands are obsolete, and the recommended caller/doer pattern: a skill provides the discoverable `/name` front door, the subagent does the noisy legwork in an isolated context and returns a clean summary. Apply its guidance when choosing between the two primitives or wiring them together.
