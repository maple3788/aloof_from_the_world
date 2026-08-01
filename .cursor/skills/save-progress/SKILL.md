---
name: save-progress
description: Record the current session's work into PROGRESS.md for session handoff. Use when the user asks to save progress, record session context, snapshot project state, or prepare a handoff so a new session can review quickly.
disable-model-invocation: true
---

# Save Progress

Maintain `PROGRESS.md` at the repo root as the project's session-handoff log.
The goal: a new session (or teammate) can get oriented in under a minute.

## Workflow

1. **Gather facts.** Review what this session actually changed:
   - `git status` / `git diff` if the workspace is a git repo; otherwise rely on
     conversation context and recently edited files.
   - Note verification results (tests, lint, type checks). If you claim tests pass,
     run them first — never record unverified claims.
2. **Read the existing `PROGRESS.md`** (create it from the template below if missing).
3. **Update "Current state snapshot"** — test counts, feature flags, notable structural
   facts. This section always reflects *now*, not history.
4. **Prepend a new dated session entry** under "Session log" (newest first), using the
   entry template. Facts over narrative: decisions made (and who made them), what
   changed, how it was verified.
5. **Refresh "Next steps"** — check off items completed this session, add newly
   discovered work. Keep each item actionable with a pointer (file/endpoint/setting).
6. **Report back** one short paragraph: what was recorded.

## Rules

- Never delete past session entries; they are the project's memory.
- Keep entries concise — a reviewer should skim one entry in ~30 seconds.
- Record *decisions and rationale*, not just diffs (e.g. "Redis = cache only, user's call").
- If a session produced a durable artifact (canvas, ADR, doc), link its path.
- Don't record secrets, tokens, or `.env` values.

## File template

```markdown
# Project Progress — <project name>

Session handoff log. Newest session first. For a quick review: read the snapshot,
the latest session entry, and "Next steps".

## Current state snapshot
- <stack / shape of the system in 2-4 bullets>
- <test/lint status>
- <feature flags or optional subsystems and how to enable them>

## Session log

### YYYY-MM-DD — <short title>
- <what was done, decisions, verification>
- <artifacts produced, with paths>

## Next steps
- <actionable item with pointer>

## Pointers
- <config references, key docs, agent/skill locations>
```
