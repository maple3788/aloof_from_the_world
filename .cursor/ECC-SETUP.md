# ECC Setup — tailored for this project

Curated subset of [ECC](https://github.com/affaan-m/ECC) (Everything Claude Code), installed for a
**FastAPI + LangGraph RAG backend / Next.js frontend** stack. Installed 2026-07-31, refined the same day.

## What's installed

| Component | Count | Location | Token cost |
|---|---|---|---|
| Common rules (always-on) | 6 | `.cursor/rules/common-*.mdc` | ~2–3K/msg |
| Python + FastAPI rules | 6 | `.cursor/rules/python-*.mdc` | only when editing `.py` |
| TypeScript + React rules | 10 | `.cursor/rules/{typescript,react}-*.mdc` | only when editing `.ts/.tsx` |
| Agents | 13 | `.cursor/agents/ecc-*.md` | 0 until invoked |
| Skills | 9 | `.cursor/skills/` | 0 until invoked |
| Hooks | 10 scripts | `.cursor/hooks/` + `hooks.json` | 0 (Node scripts) |

Your pre-existing `rules/karpathy-guidelines.mdc` was preserved.

## Stack-specific agents

- `ecc-python-reviewer`, `ecc-fastapi-reviewer` — backend code review
- `ecc-typescript-reviewer`, `ecc-react-reviewer`, `ecc-react-build-resolver` — frontend
- `ecc-mle-reviewer` — RAG pipeline review (data contracts, evals, serving, rollback)
- Core: `ecc-planner`, `ecc-architect`, `ecc-tdd-guide`, `ecc-code-reviewer`,
  `ecc-security-reviewer`, `ecc-build-error-resolver`, `ecc-e2e-runner`

Agent frontmatter follows Cursor's subagent spec (`name`, `description`, `readonly`).
Reviewers/planners are `readonly: true`; model defaults to `inherit`.

## Skills of note

- `mle-workflow` — production ML workflow for your ingestion/retrieval pipeline
- `tdd-workflow`, `security-review`, `error-handling`, `api-design`,
  `backend-patterns`, `frontend-patterns`, `nextjs-turbopack`, `documentation-lookup`

## Hooks (all functional)

- `beforeSubmitPrompt` — warns on secrets in prompts (OpenAI/GitHub/AWS/Slack patterns)
- `beforeReadFile` — warns when the agent reads `.env`/`.key`/`.pem`
- `beforeTabFileRead` — blocks Tab from reading `.env`/`.key`/`.pem` (exit 2)
- `beforeShellExecution` — blocks `--no-verify` (flag-position-aware matcher in
  `scripts/hooks/block-no-verify.js`)
- `afterShellExecution`, `before/afterMCPExecution`, `subagentStart/Stop` — audit logging

**Known limitation:** the prompt secret regex `sk-[a-zA-Z0-9]{20,}` doesn't match
hyphenated keys (`sk-ant-...`, `sk-proj-...`). The `.env` read-block is the reliable guard.

## Removed during refinement (2026-07-31)

- Dead hooks delegating to never-installed `scripts/hooks/*.js`: `session-start`,
  `session-end`, `stop`, `pre-compact`, `after-file-edit` (the claimed auto-format —
  it never ran), `after-tab-file-edit`
- `before-shell-execution.js` — blocked `npm run dev` outside tmux (exit 2); tmux is a
  Claude Code-ism, Cursor manages background shells natively
- `common-hooks.mdc`, `common-performance.mdc` — Claude Code-specific (settings.json,
  model names); `common-development-workflow` + `common-git-workflow` merged into
  `common-workflow.mdc`; `common-agents.mdc` repointed at the real agents above
- Agent frontmatter: `model: opus|sonnet` and `tools:` (not valid in Cursor) replaced
  with `readonly: true` where appropriate; generic SaaS example removed from `ecc-architect`

## Not installed (intentionally)

Django, Java/Kotlin, Go, Rust, C++, Swift, Dart/Flutter, React Native, Angular, Vue,
HarmonyOS rules; network/homelab/healthcare agents; marketing/investor/brand/video skills;
ECC commands (legacy shims); MCP configs.

## Uninstall

```bash
rm -rf .cursor/agents .cursor/skills .cursor/hooks .cursor/hooks.json scripts/hooks scripts/lib
# then delete .cursor/rules/{common,python,typescript,react}-*.mdc (keep karpathy-guidelines.mdc)
```
