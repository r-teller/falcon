# Falcon — Remote Bead Dispatch for Claude Code

Falcon is a [Claude Code](https://claude.com/claude-code) skill that ships a self-contained prompt to a **different agent session** for autonomous work, then returns a structured report the steering session uses to update its changelog and handoff state. It's designed for projects that track work as discrete units (issues, beads, tickets) and want to maximize context budget by offloading per-unit execution to worker sessions.

**Current version:** the latest [release tag](https://github.com/r-teller/falcon/releases) (`git tag` in a clone). Individual components (falcon skill, `/leroy`, `/wrapup`, agents) carry their own `version:` frontmatter and changelogs.

## Contents

- [What it does](#what-it-does)
- [When to use](#when-to-use) · [When NOT to use](#when-not-to-use) · [What's NOT for you](#whats-not-for-you)
- [What this costs](#what-this-costs)
- [Installation](#installation)
- [Advisor cluster](#advisor-cluster)
- [Bootstrap a new project from your PRD](#bootstrap-a-new-project-from-your-prd)
- [First-run setup](#first-run-setup-optional-recommended-for-autopilot-use)
- [Quick start: manual dispatch](#quick-start-manual-dispatch) · [Quick start: autopilot](#quick-start-autopilot--afk-mode)
- [Flags and tiers](#flags-and-tiers)
- [Project assumptions](#project-assumptions)
- [Architecture](#architecture)
- [Contributing](#contributing) · [Backlog](#backlog) · [License](#license)

## What it does

**Dispatch.** The steering session writes a per-dispatch YAML file at `.claude/tmp/falcon-dispatch-<6hex>.yaml` and (v7.0.0+ default) spawns a Claude Code background session via `claude --bg --name falcon-<dispatch-id>` that loads it. The worker session reads the dispatch file and executes the full lifecycle (claim → implement → verify → commit → push → close → return report); INTENT and COMPLETION are observable in `claude agents`. Older Claude Code (< 2.1.139) auto-downgrades to `--via-paste` mode — steering emits a paste block, you copy it into a worker tab.

**File-scope locking.** Cross-session aggregation via the session JSON `falcon_dispatches[]` array prevents two workers from claiming the same files. HARD-reject at dispatch time on conflict.

**Intent confirmation.** The worker writes a single-paragraph intent at the intent-confirm pause; the steering session acks before any state change. Cheapest catch for "worker misread the bead."

**Amendments.** Post-completion follow-up instructions from steering land in the dispatch file's `amendments[]` array; the worker re-reads, executes, writes back. No re-dispatch overhead for gap-closing.

**Autopilot (v6.8.0+).** Five-phase cron-driven automation rollout:

- `--watch` — observation
- `--auto-ack` — intent gate eval
- `--auto-amend` — whitelist-driven amendment issuance with budget HALT
- `--worker-cron` — worker-side amendment pickup
- `--release-on-merge` — lock held until PR merge
- `--advisor=<agent>` — fork ambiguous decisions to a registered skill

The `--autopilot` macro bundles four of these for full bidirectional AFK operation.

**Return-to-AFK utility.** `/falcon list-pending` surfaces every pending-human item across all active dispatches in one read-only command; the `--watch` cron prepends `⚠️ HIGH-STAKES DAR PENDING` headlines so DARs can't get lost in routine status emissions.

**Forecast vs Actual calibration loop.** Bead authors forecast effort per phase at `triage:ready` time (5 phases: plan / discover / implement / test / fix); `.claude/scripts/token-tracking.sh` captures actuals per phase per session; `/wrapup` Task 3c flushes to `.claude/metrics.jsonl`. `velocity-report.py` produces a self-contained HTML dashboard. Per-bead, per-cynefin, per-size variance is queryable via `jq` against the JSONL (recipes in [`metrics-schema.md`](.claude/docs/metrics-schema.md)). Closes the loop: forecast → claim → track → close → metric → calibrate → refine forecasts.

## When to use

- **Multi-unit work:** you have a backlog of well-scoped units (beads/tickets) and want to dispatch them in parallel across worker tabs while keeping steering's context budget for review + arbitration.
- **AFK operation:** you want the work to progress without you, with bounded autonomy (refuse-on-MVM for write-bearing flags; project-defined `SAFE_TO_AMEND` whitelist; per-dispatch amendment budget cap).
- **Cross-cutting reviews:** the steering session can validate worker reports against project-specific standards files without re-reading the work from scratch — the worker writes structured output the steering parses.

## When NOT to use

- **Architectural decisions that need active steering** — keep those in the steering session, don't dispatch.
- **Beads that aren't `triage:ready`** — refine first, then dispatch.
- **Single-shot exploratory work** — overhead isn't worth it for one-off questions.

## What's NOT for you

The kit is heavyweight. Some project shapes won't see ROI on the overhead:

- **Single-developer projects with <5 beads/sprint.** The contract enforcement, structured handoff/changelog, falcon dispatch, and `/wrapup` ceremony all overhead-tax small projects. If you'd never spin up another worker session, you're paying for machinery you won't use.
- **Quick-prototype work.** The hydrated-bead contract (Required Context, per-phase Effort Forecast, cynefin classification) is overkill for "let me try this and see if it works."
- **Projects already on a different work-tracking system.** Falcon assumes bd; adapting workers to Jira / Linear / GitHub Issues is possible but requires rewriting the worker lifecycle (`bd show`, `bd update`, `bd close` → equivalents in your tracker).
- **Conversational / exploratory sessions.** No code changes to wrap up. `/wrapup` doesn't add value when nothing landed; skip it.
- **You don't want opinionated structure.** The kit imposes file conventions (typed YAML for handoff/changelog/enhancements/standards-history), task ordering, and a promotion lifecycle. If you prefer free-form workflow tracking, this isn't the kit.

If most of those apply, falcon's dispatch primitive alone (Option 2 in Installation) without the `/leroy` + `/wrapup` cluster may still fit. Otherwise consider lighter-weight alternatives.

## What this costs

Falcon's full kit (`/leroy` + `/wrapup` + falcon dispatch) is heavyweight by design. Typical token spend at Opus pricing (~$15/M effective tokens, where eff-tokens = `input + 1.25·cache_create + 0.1·cache_read + 5·output`):

| Operation | Median eff-tokens | Median turn-time | Cost (approx) |
|---|---|---|---|
| `/leroy` startup orientation (full) | ~9M | ~7.5 min | ~$0.14 |
| `/leroy --minimal` (continuation; handoff + corpus + label filter) | ~4-5M | ~3 min | ~$0.07 |
| `/wrapup` (full ritual) | ~7.5M | ~7 min | ~$0.11 |
| `/wrapup --minimal` (typo fix, checkpoint) | ~2M | ~2.5 min | ~$0.03 |
| One falcon dispatch (steering + worker, ex-work) | ~30–100M | varies | ~$0.50–1.50 |

A typical full session (`/leroy` → work → `/wrapup`) at the kit-level cost (excluding the actual work) is ~$0.30 per session. At ~30 sessions/month with ~5 falcon dispatches, the kit overhead is ~$10–15/month; the work itself adds variable cost depending on project size.

## Installation

### Prerequisites

- **Claude Code** — any version works. Falcon v7.0.0+ defaults to `--bg` dispatch mode (uses Claude Code's background-session feature, requires **Claude Code ≥ 2.1.139**); older versions auto-downgrade to `--via-paste` and everything still works.
- **[`beads` (`bd`) CLI](https://github.com/anthropic-experimental/beads)** — required for the Bootstrap workflow below and for `/falcon work beads <id>` invocations. Install per the beads README.

### What this distribution contains

Beyond the falcon skill itself, this repo ships a coordinated set of pieces that make the Bootstrap workflow + `/leroy` + `/wrapup` work out of the box:

| Path | What it is |
|---|---|
| `.claude/skills/falcon/` | Falcon itself (5 files) |
| `.claude/skills/{quartermaster,herald,scribe}/` + `.claude/agents/{quartermaster,herald,scribe,navigator}/` | Vendored advisor cluster (3 dispatcher skills + 13 specialist agents) + navigator subagent |
| `.claude/commands/{leroy,wrapup}.md` | Session-startup + session-end slash commands (current: leroy v2.9.0, wrapup v2.13.2) |
| `.claude/docs/` | Schema references (handoff, changelog, work-item-templates, enhancements, standards-history, lint-integration) |
| `.claude/rules/` | Workflow modules + `development-standards.md` template stub |
| `.claude/hooks/` | Claude Code auto-invoked scripts: `session-start.sh` (injects session_id + transcript_path into context), `statusline.sh` (status-line refresh) |
| `.claude/scripts/` | Workflow/user/CI utility scripts: `check-bead-contract.py` (bead tier-contract enforcement — see [`lint-integration.md`](.claude/docs/lint-integration.md)), `token-tracking.sh` (5-phase forecast-vs-actual capture), `velocity-report.py` (HTML velocity report from metrics.jsonl) |
| `.claude/schemas/` | JSON Schema validators for the 5 typed YAML/JSONL artifacts (handoff, changelog, enhancements, standards-history, metrics); each YAML file carries a `# yaml-language-server: $schema=...` header for editor live-validation |
| `.claude/{architecture,backend,frontend,data-model,security,tests,claude}.md` | Context-file stubs (asteroid-themed; hydrate via the [Bootstrap section](#bootstrap-a-new-project-from-your-prd) below) |
| `.claude/{handoff,changelog}.yaml` | Session-state file stubs with `template_entry:` + a commented-out worked example |
| `.claude/{enhancements,standards-history}.yaml` | Typed audit logs: `enhancements.yaml` for doc gaps / retros / standards candidates; `standards-history.yaml` for rule firings / promoted rules with slug-keyed identity |
| `.claude/metrics.jsonl` | Append-only forecast-vs-actual log (committed by default for team-shared calibration; can be gitignored — see `.gitignore`) |
| `.claude/settings.json` | Kit-shipped settings: `statusLine` config + `SessionStart` hook registration; override per-machine via `settings.local.json` (gitignored) |

### Option 1 — Full distribution (recommended)

Copy everything under `.claude/`. Gives you `/leroy`, `/falcon`, `/wrapup`, the advisor cluster, schemas, workflow rules, and hydration-ready context stubs — i.e., the full Bootstrap workflow.

```bash
git clone https://github.com/r-teller/falcon /tmp/falcon
cp -r /tmp/falcon/.claude /path/to/your/project/
cp /tmp/falcon/BOOTSTRAP.md /path/to/your/project/   # one-time bootstrap prompt; delete after first run if you like
```

### Option 2 — Falcon skill only (minimal)

Just the 5 falcon files. Works for manual dispatch (`/falcon work beads ...` with paste-blocks) but does NOT give you `/leroy`, `/wrapup`, the advisor cluster, or the Bootstrap workflow. Choose this only if you want to slot falcon into an existing project that already has its own session-start / wrapup conventions.

```bash
git clone https://github.com/r-teller/falcon /tmp/falcon
cp -r /tmp/falcon/.claude/skills/falcon /path/to/your/project/.claude/skills/
```

### Option 3 — Git submodule (track upstream updates)

```bash
cd /path/to/your/project
git submodule add https://github.com/r-teller/falcon .claude/falcon-upstream
# Symlink the pieces you want (falcon-only example shown; add others as needed)
ln -s falcon-upstream/.claude/skills/falcon .claude/skills/falcon
ln -s falcon-upstream/.claude/agents/navigator.md .claude/agents/navigator.md
ln -s falcon-upstream/.claude/agents/navigator .claude/agents/navigator
ln -s falcon-upstream/.claude/commands/leroy.md .claude/commands/leroy.md
ln -s falcon-upstream/.claude/commands/wrapup.md .claude/commands/wrapup.md
```

### Verify the install

Open Claude Code in your project. Type `/falcon` — falcon's commands should appear in autocomplete. If you installed Option 1, also try `/leroy` and `/wrapup`. Run `/falcon list-locks` (or any read-only command) to confirm the skill loaded.

> **Heads-up:** `claude --help` does NOT list `--bg` among its flags as of current Claude Code releases, but the flag IS supported on Claude Code ≥ 2.1.139. Falcon detects support via `claude --version`, never `--help`. If an adopter or AI assistant reports "`--bg` is not a supported command" after probing `--help`, that's the false signal — verify with `claude --version` instead.

## Advisor cluster

> **Included with Option 1** (Full distribution). The install commands below only apply if you used Option 2 (Falcon skill only) and now want to add the advisors.

This repo bundles an **advisor cluster** — three dispatcher skills with specialist agents — that demonstrates the `--advisor=<agent>` wiring described in `COMMANDS.md`:

- **`quartermaster`** — Technical/Solution Architect (4 specialist agents: `backlog-review`, `feature-fit`, `tech-review`, `coordination`)
- **`herald`** — UX/UI design (4 specialist agents: `review`, `system`, `prototype`, `a11y`)
- **`scribe`** — Backlog write-counterpart referenced by both above (5 specialist agents: `init`, `prd`, `plan`, `refine`, `brief`)

Each dispatcher skill (under `.claude/skills/<name>/SKILL.md`) routes intent to one of its specialist agents (under `.claude/agents/<name>/<name>-<specialty>.md`). The dispatcher pattern is independent of falcon — these are reusable advisor skills you can use directly, or use as forking targets via `--advisor=quartermaster` in autopilot mode.

**Adding them to a minimal install:**

```bash
cp -r /tmp/falcon/.claude/skills/{quartermaster,herald,scribe} /path/to/your/project/.claude/skills/
mkdir -p /path/to/your/project/.claude/agents
cp -r /tmp/falcon/.claude/agents/{quartermaster,herald,scribe} /path/to/your/project/.claude/agents/
```

To wire them as falcon advisors, configure `.claude/rules/falcon-autopilot.md § 5` (advisor delegation policy) per the template in [`REFERENCE.md`](.claude/skills/falcon/REFERENCE.md#falcon-autopilotmd-template).

## Bootstrap a new project from your PRD

Goal: from a PRD to a session where you can run `/leroy`, `bd ready`, and `/falcon work beads <id>` against real work.

The full 6-step bootstrap prompt lives in [`BOOTSTRAP.md`](BOOTSTRAP.md). Use it in a fresh Claude Code session in your project:

```
Follow @BOOTSTRAP.md with my PRD @PRD.md
```

(or copy-paste the prompt block from the file). It walks through PRD summary → context-file hydration → beads init → bead creation → Phase 1 refinement → next steps, with confirmation checkpoints at each stage.

**If you don't have a PRD yet:** skip this section. Edit the 8 context files directly, or run `/scribe prd` to draft a Product Guidance section into `architecture.md` from a rough idea, then come back once it's solid enough to seed beads.

**Want to try the workflow first?** Use [`examples/asteroids_prd.md`](examples/asteroids_prd.md) — a sample PRD matching this distribution's example content — to smoke-test the bootstrap end-to-end before bringing in your real PRD.


## First-run setup (optional, recommended for autopilot use)

If you plan to use `--auto-ack` / `--auto-amend` / `--autopilot`, set up the autopilot rules file in two steps:

**Step 1 — Create the rules file** (required for any autopilot):

```
/falcon create-rules
```

This populates `.claude/rules/falcon-autopilot.md` from the template. Universal gates are active by default; project-specific gates ship commented out. See [`COMMANDS.md`](.claude/skills/falcon/COMMANDS.md#falcon-create-rules) `### /falcon create-rules` for the template structure (6 sections: SAFE_TO_ACK_INTENT predicate, SAFE_TO_AMEND whitelist, SAFE_TO_AMEND denylist, cognitive audit hints, advisor delegation policy, amendment budget defaults).

**Step 2 — Activate project gates** (recommended; v6.14.0+):

```
/falcon enable-autopilot --profile=conservative --dry-run   # preview which gates would activate
/falcon enable-autopilot --profile=conservative             # apply
```

Bulk-uncomments project gates per the chosen profile. Three profiles ship:

- **`conservative`** — minimum-viable autopilot. All universal denylist items active, 1-2 highest-priority intent gates, zero project-side whitelist items. Use when first activating autopilot on a new project.
- **`standard`** — recommended general use. Seeds intent gates + whitelist + cognitive audit hints + advisor (if `quartermaster` is installed). Per-bead-type budget defaults.
- **`aggressive`** — maximum autonomy. Every gate where the detection condition holds. Use only after `standard` is well-calibrated.

Without `enable-autopilot`, you can manually uncomment gates by editing `falcon-autopilot.md` directly — it's a regular markdown file.

For manual-only use (no autopilot flags), both steps are optional — the skill works fine without `falcon-autopilot.md`.

## Quick start (manual dispatch)

```
/falcon work beads <bead-spec>
```

Where `<bead-spec>` is a comma-separated list, range, or single bead ID. **Default behavior (v7.0.0+, `--bg` mode):** steering writes the dispatch file and spawns a Claude Code background session via `claude --bg --name falcon-<dispatch-id>`. Observe via `claude agents`; when INTENT appears, peek the row and type `proceed <dispatch-id>` to authorize. Completion lands automatically; auto-release fires when validation passes.

**Fallback (`--via-paste` mode):** on Claude Code < 2.1.139 or with `disableAgentView: true`, falcon auto-downgrades and emits a paste block. Copy it into a worker tab; the worker executes the same lifecycle.

See [`COMMANDS.md`](.claude/skills/falcon/COMMANDS.md) for the full surface and [`PROTOCOL.md`](.claude/skills/falcon/PROTOCOL.md) for the lifecycle.

## Quick start (autopilot — AFK mode)

After `/falcon create-rules` + `/falcon enable-autopilot --profile=<name>` (see [First-run setup](#first-run-setup-optional-recommended-for-autopilot-use)):

```
/falcon work beads <bead-spec> --autopilot --amendment-budget=3
```

**Default (`--bg` mode, v7.0.0+):** steering arms three crons in its own session (`watch`, `autoack`, `amend`) and spawns the worker as a Claude Code background session. `--worker-cron` is suppressed. **As of v7.1.1**, the worker arms its own self-poll cron at intent-emission and DAR pause points (`durable: false`, `CronDelete`s on wait-condition-satisfied) so steering's ack/amendment writes are observed without operator paste relay — full AFK in `--bg` mode no longer requires peek-and-reply at each intent gate. The three steering crons + worker self-poll coordinate via atomic writes to the dispatch file.

**`--via-paste` fallback:** steering emits TWO paste blocks for the worker tab (dispatch prompt + worker-cron setup); once both pastes land, four crons coordinate via atomic writes.

On return:

```
/falcon list-pending      # check what needs your attention
/falcon retro --branch <current-branch>     # autopilot audit for wrapup
```

See [`PROTOCOL.md`](.claude/skills/falcon/PROTOCOL.md#--autopilot-mode-full-afk-bundle-v6110) `### --autopilot mode` for the wiring.

## Flags and tiers

The kit's commands accept flags that gate behavior or pick a faster path:

### `/leroy`

- `--skip-health` — skip the architecture.md Environment Health Checks at startup. Use when env is known healthy or working offline. (leroy v2.5.0+)
- `--minimal` — continuation mode. Assumes you're resuming existing work (not picking new). ~50% savings (~$0.07 vs ~$0.14). (leroy v2.8.0+, paired with navigator-recon v1.5.0)
  - Skips env health checks, `git log -5`, navigator §3/6/7/8/9, and per-bead `bd show` calls for Effort Forecast.
  - Navigator runs one `bd list --json --limit 0` corpus fetch + in-memory label filter for `triage:ready` picks.
  - The "Ready to Start" picker still surfaces alternatives by label (Size + Cynefin columns), but the `~Turns` column shows `N/A` since `bd show` is skipped.
  - Falls back to full /leroy automatically if `handoff.yaml entries[0]` is null/empty.

### `/wrapup`

- `--minimal` — run only Tasks 2 (verify) + 7 (commit) + 8 (handoff). Use for typo fixes, mid-feature checkpoints, tiny experiments. Auto-falls back to full ritual if synthesis-mode falcon stash detected. Task 8 emits a session-shape hint if substantive markers (≥1 bead closed, ≥3 commits, ≥5 files, etc.) suggest the session was bigger than `--minimal` warranted. (wrapup v2.10.0+)
- `--feedback` — interactive 6-question retro mode (default is self-reflection mode that auto-captures findings without user interaction). Use when you want to provide your own observations. (wrapup v2.6.0+)
- Flag composition: `/wrapup --minimal --feedback` runs minimal ritual; `--feedback` becomes no-op since Task 9 retro is skipped.

### `/falcon work beads`

See [`COMMANDS.md`](.claude/skills/falcon/COMMANDS.md) for the full flag surface (`--bg`, `--via-paste`, `--sequential`, `--autopilot`, `--advisor=<agent>`, `--skip-intent`, `--inline-beads`, etc.).

## Project assumptions

Falcon makes a few assumptions about how the consuming project tracks work:

- **Work-tracking CLI** — falcon's examples use [`beads (bd)`](https://github.com/anthropic-experimental/beads) as the work-tracking tool. The protocol references `bd show`, `bd update`, `bd close`, etc. If your project uses a different tracker, you'll need to adapt the prompts (replace `bd <cmd>` with your tracker's equivalent in the init_prompt and worker lifecycle steps).
- **Shared filesystem + shared branch** — steering and all workers must operate on the same git checkout (or the worker can use `--paste` mode for cross-network operation, with reduced functionality).
- **Project standards live in `.claude/rules/*.md`** — falcon's workers read project-specific rules from this directory. The skill is project-agnostic; project conventions live in the project's own rule files.
- **Claude Code version** — falcon adjusts its surface to whatever Claude Code version is present:
  - `≥ 2.1.139` (v7.0.0+) → `--bg` default dispatch mode (Claude Code background sessions, observable via `claude agents`)
  - `1.0`–`2.1.138` → autopilot crons (`--watch`, `--auto-ack`, `--auto-amend`, `--release-on-merge`) via `CronCreate` / `CronList` / `CronDelete`; falcon auto-downgrades dispatch to `--via-paste`
  - older → manual dispatch via `--via-paste` only; no autopilot

## Architecture

The repo has three layers — **falcon itself** (the skill), the **session / contract layer** (`/leroy`, `/wrapup`, scripts, typed-YAML artifacts), and an **optional advisor cluster** (vendored alongside).

### Falcon skill (~5 files, ~3,500 lines)

- **`SKILL.md`** — entry point + cross-cutting protocol notes
- **`COMMANDS.md`** — CLI surface with `✓` / `⊘` status legend
- **`PROTOCOL.md`** — lifecycle steps (Step 1 → Step 5 + Worker Lifecycle + Amendments Workflow + Paste-Fallback Mode + Background-Agent Dispatch Limitation)
- **`REFERENCE.md`** — Dispatch File YAML Schema, Session JSON Schema Extension, init_prompt Content Templates (default + paste-mode), Worker Return Contract, Dispatch Prompt Template, Stash File Format, falcon-autopilot.md Template, Autopilot Cron Prompt Templates (six entries)
- **`changelog.md`** — version history, most recent first

Read `SKILL.md` first; it points to the other files.

### Session / contract layer

- **`.claude/commands/{leroy,wrapup}.md`** — session orchestration commands. Both carry versioned changelogs at the top of the file documenting flag additions and behavior changes.
- **`.claude/agents/navigator/{navigator-recon,navigator-survey,navigator-maintenance}.md`** — orientation subagent (recon) + specialist routing (survey for complex, maintenance for simple). `/leroy` Step 3d cynefin-gates the routing dispatch.
- **`.claude/docs/{enhancements,standards-history,handoff,changelog,work-item-templates,lint-integration}-schema.md`** — schema references for the typed artifacts the kit ships and the lint-integration recipes
- **`.claude/scripts/check-bead-contract.py`** — bead tier-contract enforcement (backlog / triaged / ready label + section + rule requirements).
  - Six mode flags (`--beads`, `--session`, `--since`, `--in-progress`, `--stale`, `--all`); three output modes (human-readable text, `--json`, `--ids`).
  - Severity-by-tier: HARD for ready / structural defects; SOFT for backlog/triaged refinement.
  - ~1 sec for 160 beads via single bd_list corpus fetch. `CONTRACTS_VERSION` currently 1.2.
- **`.claude/scripts/token-tracking.sh`** — phase-aware token tracking per bead.
  - Five work phases (`plan / discover / implement / test / fix`) + coordinate phase for multi-bead planning.
  - Bookmarks transcript line offsets at start/stop; computes deltas at stop. Per-project state at `.claude/tmp/.token_tracking/`. Cross-session resume + orphan detection.
  - Started by `/leroy` Step 3e (per-bead) and Step 3d.2 (coordinate); flushed by `/wrapup` Task 3c. Closes the forecast → claim → track → close → metric → calibrate → refine loop.
- **`.claude/scripts/velocity-report.py`** — generates a self-contained HTML velocity report from `metrics.jsonl` with embedded chart data. Open in any browser.
- **`.claude/hooks/session-start.sh`** — fires on `SessionStart` event. Injects session_id + transcript_path into context so workflow knows where to capture metrics from.
- **`.claude/{enhancements,standards-history,handoff,changelog}.yaml`** — typed audit and state artifacts. `enhancements.yaml` tracks doc gaps + retros + standards candidates with status state machine (DAR 4 / wrapup v2.8.0). `standards-history.yaml` tracks rule firings + promoted rules with slug-keyed identity (DAR 9 / wrapup v2.12.0). `handoff.yaml` + `changelog.yaml` are session-state logs consumed by `/leroy`'s navigator-recon via `yq '.entries[0]'`.

### Advisor cluster (~16 files, ~2,000 lines)

Independent of falcon. See "Optional: Advisor cluster" above for purpose and install.

- **`.claude/skills/{quartermaster,herald,scribe}/SKILL.md`** — three dispatcher skills (1 file each)
- **`.claude/agents/{quartermaster,herald,scribe}/`** — 13 specialist agents that the dispatchers route to (4 + 4 + 5)

## Contributing

This is an opinionated personal tool, but PRs are welcome for bug fixes, documentation clarifications, and obvious gaps. For larger design changes, open an issue first to discuss whether it fits the skill's scope.

## Backlog

- **File monitoring as a cron alternative for autopilot:** watch dispatch files and sidecar state via filesystem events (inotify / fsevents) instead of polling on a `--watch` / `--auto-ack` / `--auto-amend` / worker-self-poll cadence. Autopilot reacts to state changes (intent emission, completion-hash write, `amendments_pending` flip) instantly rather than on the next bucket-driven interval, and silent-fire overhead drops to zero.
- **Model-selection follow-ups:** per-worker model selection shipped in v7.4.0 (`worker_model` dispatch field, `--bg` mode). Model choice binds at session boundaries by design — a worker never switches models mid-dispatch, so a `--sequential` dispatch intentionally runs all its beads on one model (a mid-sequence switch would discard the inherited context that `--sequential` exists to preserve). Remaining: per-respawn model override (escalate on `respawn-fresh`), autopilot per-bead-type model defaults for unattended dispatch.

## License

[MIT](LICENSE) — see the LICENSE file. Copyright (c) 2026 Robert Teller.
