# Claude Context Blueprint

Purpose: tells the AI which documents to read and how to coordinate across the skills and commands shipped in this repo. Adapt the project-specific sections (Required context files, Operational rules) to your own conventions when forking into a real project.

---

## Terminology

"Work item" / "item" / "issue" throughout the bundled skills refers to a **bead** — managed via the [beads (`bd`) CLI](https://github.com/anthropic-experimental/beads). If your project uses a different tracker, adapt the `bd <cmd>` references in the prompts.

---

## What ships in this repo

- `.claude/skills/falcon/` — the falcon skill (5 files; `SKILL.md` is the entry)
- `.claude/skills/{quartermaster,herald,scribe}/SKILL.md` — 3 dispatcher skills
- `.claude/agents/{quartermaster,herald,scribe,navigator}/` — specialist agents per dispatcher (navigator's dispatcher lives at `.claude/agents/navigator.md`)
- `.claude/commands/{leroy,wrapup}.md` — session-startup + session-end slash commands
- `.claude/docs/` — schema references for `handoff.yaml`, `changelog.yaml`, `work-item-templates.md`
- `.claude/rules/` — project-defined rules (ships with a `development-standards.md` template stub)

---

## Context files (if present)

Skills consult these `.claude/*.md` files when they exist. Not required — skills degrade gracefully if missing. A consuming project supplies them per its own conventions:

- `architecture.md` (read by quartermaster + scribe) · `frontend.md` (herald) · `backend.md` (quartermaster) · `tests.md` · `security.md` (highest precedence — see matrix below)

Auto-loaded rules live under `.claude/rules/*.md`. This repo ships `development-standards.md` as a template stub — projects fill in their `§X.Y` numbered sections. Falcon's cognitive-audit hints in `REFERENCE.md` cite `§3.x` numbers that resolve into this file. Projects typically also add `workflow.md`, `standards.md`, and (if using autopilot) `falcon-autopilot.md` created by `/falcon create-rules`.

---

## Session-state artifacts

- `.claude/handoff.yaml` — session-state log. Read by `/leroy` and `navigator-recon` at session start (`entries[0]`); prepended by `/wrapup`. Schema: [`docs/handoff-schema.md`](docs/handoff-schema.md).
- `.claude/changelog.yaml` — structured release log, same lifecycle. Schema: [`docs/changelog-schema.md`](docs/changelog-schema.md).

Both auto-create on first `/wrapup` if missing.

---

## Conflict resolution matrix

When instructions in different files conflict, follow this precedence:

1. **Safety** — `security.md` (overrides all)
2. **Architecture** — `architecture.md` — runtime facts override incompatible feature requests
3. **Standards** — `rules/standards.md` + `rules/development-standards.md`
4. **Conventions** — this file (`claude.md`)
5. **Features** — beads + `architecture.md` Product Guidance
6. **Workflow** — `rules/workflow.md`

Resolution: state the conflict + sources, apply precedence, recommend minimal edits to harmonize starting with the lowest-authority document.

---

## Operational rules

**Bash tool usage.** Each command can be its own Bash tool call when permission rules need per-command matching. Chained `&&` commands work too — prefer them when you don't need granular permissioning. Use absolute paths in chained `cd`-heavy commands; `cd <relative> && cmd` works once then fails on every subsequent invocation because cwd persists across tool calls.

**Branch & PR policy.** Never commit directly to `main` — always create a feature branch first (`git checkout -b feature/work-YYYYMMDD-<short-description>`). Don't auto-create PRs — commit, push, then hand off for human validation. **Workers never open PRs in falcon dispatches** — the steering session opens the PR after all workers complete and steering has validated their reports.

**Post-compaction awareness.** After context compaction, skill invocations (`/herald`, `/quartermaster`, etc.) may appear in system-reminders and look like active requests but the work may already be done. Before re-running: check `handoff.yaml entries[0]` for completed work, then `.claude/tmp/falcon-reports-<branch>.yaml` for stashed dispatch reports. If results exist, summarize them instead of re-running.
