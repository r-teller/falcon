---
description: Lightweight session startup — env check, git status, navigator subagent for context-efficient orientation
tier: scale
version: 2.9.0
created: 2026-03-21
changelog:
  - 2.9.0 (2026-06-10): Token-tracking integration. Step 1b session tracker JSON bumped to schema v3 (`worked_beads` is now an object keyed by bead_id; new `coordinate_tracking` field; entries carry per-phase forecasts/actuals/segments). Step 3d.2 starts coordinate-phase tracking for multi-bead claims via `.claude/scripts/token-tracking.py start --coordinate`. Step 3d.5 stops coordinate tracking after plan confirmed. Step 3e starts per-bead phase tracking (`--bead <id> --phase plan`) for each claimed bead and populates `worked_beads[<id>]` with forecasts pulled from the bead body's Effort Forecast section. Cross-session resume handled by tracker. `--minimal` (continuation mode) does NOT auto-start tracking — deliberate tradeoff for fast-path; user can invoke tracker manually if needed. Pairs with wrapup v2.13.0 (Task 3c flush), schema docs `.claude/docs/metrics-schema.md`, schema `.claude/schemas/metrics.schema.json`, script `.claude/scripts/token-tracking.py` (5-phase: plan/discover/implement/test/fix + coordinate). Hook `.claude/hooks/session-start.sh` injects session_id + transcript_path into context (kit-shipped + registered in settings.json).
  - 2.8.0 (2026-06-10): Add `/leroy --minimal` continuation-mode flag. Parallel to `/wrapup --minimal` (wrapup v2.10.0). When `--minimal` is passed, /leroy assumes the user is continuing existing work (not picking new) and skips: Step 1 env health checks, Step 2 `git log -5`, navigator §6 Sequential-Group, navigator §7 Enhancements Alert, and the per-bead `bd show` calls that populate Effort Forecast in §5. Navigator runs in continuation mode: one `bd list --json --limit 0` corpus fetch + in-memory label filter for triage:ready picks (instead of 5 separate bd calls + 3 bd shows). The "Ready to Start" picker still surfaces alternatives — label-filtered by triage:ready, with Size + Cynefin columns from labels — but the Effort Forecast `~Turns` column shows `N/A` since bd show is skipped. Unified picker table now includes a Size column in BOTH full and minimal modes (free upgrade — Size is a required label at triage:ready per work-item-templates.md, but the prior orientation table didn't surface it). Estimated savings: ~50% on /leroy (~$0.07 vs ~$0.14), ~9.5 sec wall-clock saved on tool calls. Fallback: if `handoff.yaml entries[0]` is null/empty (first /leroy in project or post-archive), --minimal falls back to full /leroy automatically with an inline note.
  - 2.7.0 (2026-06-10): Step 3d — cynefin-gate specialist routing. Single `cynefin:clear` bead claims skip the specialist subagent dispatch entirely and present the bead body directly as the execution plan (Changes Needed table + AC checklist IS the plan for atomic work). Complicated, complex, and multi-bead claims continue to dispatch the specialist as before. Saves ~250k eff-tokens + ~1.5 min turn-time per qualifying claim; estimated ~35% of /leroy claims qualify at the reference deployment's cadence. Honors the bead author's cynefin classification — if they marked it clear, the bead is atomic by their own assertion and the specialist adds no signal. Step 3e's context-load instructions now branch on the Step 3d path: skip-path reads only the bead's Required Context section (often empty for clear beads); run-path reads the specialist's recommendations. Pairs with the DAR 5 hydrated-bead contract — a clear bead with concrete Changes Needed + empty Required Context is the ideal atomic work unit.
  - 2.6.0 (2026-06-10): Step 3 — consume new navigator-recon §9 Enhancements Alert. When navigator emits §9 (i.e., at least one enhancements.yaml `kind` exceeds its open-count threshold OR has an aging cohort), render the alert bullets + ask "review now? (y / n / defer-this-session)". On `y`, dispatch a triage subagent that walks open entries one-by-one and applies `yq -i` transitions for resolve/defer/retire. On `n`, alert reappears next startup. On `defer-this-session`, suppress for rest of session (no file change). This is the forcing function that prevents enhancements.yaml from becoming a write-only museum (the failure mode observed on the reference deployment's legacy markdown file). Pairs with wrapup v2.8.0 (typed YAML schema migration) and navigator-recon v1.3.0 (§9 detection). §9 follows empty-state suppression — when nothing exceeds + no aging cohorts, the section is omitted entirely from navigator output, so clean-state startups see no friction.
  - 2.5.0 (2026-06-10): Add `/leroy --skip-health` flag — when present, Step 1 skips reading the architecture.md Environment Health Checks table and running the per-service probes; reports inline "Health checks skipped" and continues to Step 1b. Use for fast startups when the env is known-healthy, offline work, or quick orientation. The wrapup-side Task 10 still maintains the table on infrastructure changes (per wrapup v2.7.1) — this flag only changes startup behavior, not the maintenance discipline.
  - 2.4.1 (2026-05-22): Fix stale section count in Step 3 navigator prompt — "ALL 7" → "ALL 8" to match Step 3a's validation list (v2.4.0 added §8 but didn't bump the prompt count).
  - 2.4.0 (2026-05-22): Consume new navigator-recon §8 "Sequential-Group Candidates" — when navigator detects 2+ ready beads with overlapping file_scopes + shared epic or formal blocked-by, render a prose hint suggesting `/falcon work beads A,B --sequential` (per example-t0l falcon v6.4.0 flag). Empty-state suppressed — block only renders when candidates exist. example-8qy.
  - 2.3.0 (2026-05-21): Add session-wide Bash path convention to Step 1 — require absolute paths for cd targets and command args; relative `cd <subdir> && cmd` breaks on second invocation because cwd persists across Bash tool calls.
  - 2.2.0 (2026-04-25): Add worked_beads object schema reference in step 1b (metrics:on block)
  - 2.1.0 (2026-04-25): Cynefin column unconditional in work table; coordinate-phase tracking in metrics:on blocks
  - 2.0.0 (2026-03-21): Full rewrite — env checks, session tracking, structured output formatting, post-selection planning
  - 1.0.0 (2026-03-21): Initial tiered version
allowed-tools: Task
---

## Leroy — Token-Efficient Session Startup

Lightweight session startup that keeps context files out of the main window. The navigator subagent reads everything and returns a summary with recommendations. Use for focused, context-conscious sessions.

---

### Tier Detection: Full vs Minimal (run BEFORE Step 0)

`/leroy` runs at one of two tiers, decided by whether the invocation included the `--minimal` flag:

- **Default (no flag) — Full /leroy.** Run all steps below. Use for sessions where you may pick new work, need fresh queue state, or want the full enhancements alert + sequential-group detection.
- **`--minimal` flag — Continuation mode.** Skip Step 1 (env health checks), Step 2's `git log -5`, and dispatch the navigator subagent in continuation mode (one bd corpus fetch + label filter instead of 5 bd calls + 3 bd shows). Use when continuing existing work you already know about — you want orientation to "where I left off" + a quick pick of `triage:ready` alternatives, not the full new-work survey.

**Fallback: `--minimal` + empty handoff → full /leroy.** Before entering --minimal flow, check `yq '.entries[0]' .claude/handoff.yaml`. If the result is `null` (first session in a project, post-archive, etc.), emit inline: *"No handoff state — falling back to full /leroy for new-work selection."* Then proceed with the full flow. This guarantees --minimal never strands a new project.

**`--minimal` + Step 1b:** the session tracker JSON IS still created in --minimal mode — `check-bead-contract.py --session` depends on the `started` timestamp.

The table below shows which steps differ by tier:

| Step | Full /leroy | `--minimal` |
|---|---|---|
| 0 — Status line check | run | run (same) |
| 1 — Env health check | run | **skip** |
| 1b — Session tracker init | run | run (same) |
| 2 — git status | run | run (same) |
| 2 — git log -5 | run | **skip** |
| 3 — Navigator (recon) | full 9-section output | continuation mode (sections 1, 2, 4, 5; §3/6/7 skipped or condensed; §5 `~Turns` shows `N/A`) |
| 3d — Specialist routing | cynefin-gated (per DAR 6) | cynefin-gated (same) |

---

### 0. Status Line Check (First Time Only)

Check if the context status line is configured by checking if `~/.claude/statusline.sh` exists.

**If the file does NOT exist**, offer to set it up:

"I noticed you don't have the context status line configured yet. This shows you real-time token usage at the bottom of your terminal, helping you stay aware of context limits before autocompact triggers.

Would you like me to set it up now? (This is a one-time setup that works across all projects.)"

- **If yes:** Follow the setup process from `/setup-statusline`
- **If no:** Continue with the session startup

**If the file already exists**, skip this step silently and continue.

---

### 1. Quick Environment Check

> **Skipped in `--minimal`:** if continuation mode (per Tier Detection above), skip this entire step. Emit inline: *"Step 1 skipped (--minimal — env assumed healthy from prior session)."*

**Bash path convention (session-wide):** for every Bash invocation this session, use **absolute paths** — both for `cd` targets and for command/file arguments. Cwd persists across Bash tool calls, so `cd <relative> && cmd` will succeed once then fail on every subsequent identical call (the second `cd score-tracker` errors because cwd is already `score-tracker/`). Use `cd /path/to/project/<subdir> && cmd` OR skip cd entirely with absolute argument paths (e.g., `/path/to/project/score-tracker/.venv/bin/pytest /path/to/project/score-tracker/tests/`). The only place a relative cd is acceptable is the dedicated `cd "$(git rev-parse --show-toplevel)"` anchoring pattern.

**`--skip-health` flag.** If the `/leroy` invocation included `--skip-health`, skip the health-check pass below and report inline: *"Health checks skipped per `--skip-health` flag — proceed at your own risk."* Continue to Step 1b. Use this when you know the environment is already healthy, you're working offline, or fast startup matters more than a clean baseline. The wrapup-side Task 10 still maintains the table; this flag only skips reading and exercising it at startup.

Otherwise, read the **Environment Health Checks** table from `.claude/architecture.md` (the "How to Run" section). Run each check command and compare against the expected output.

For each service:
- If healthy: note briefly (e.g., "Backend: healthy")
- If unhealthy or not running: warn with the service name and status
- If the check command fails entirely: note the service is not reachable

Report all results in a compact block before continuing. Do not auto-start services without asking.

If `architecture.md` doesn't have an Environment Health Checks table, fall back to basic checks:
- `curl -s http://localhost:8000/health || echo "not running"` (common backend)
- `docker ps --format "table {{.Names}}\t{{.Status}}"` (Docker services)
- `test -f .env && echo "exists" || echo "missing"` (env file)

And suggest the user add the table to architecture.md for future sessions.

### 1b. Initialize Session Tracking

Create the session tracker JSON for this working session. The session ID is
injected by the `session-start.sh` hook (visible in context). The transcript path
follows the pattern `~/.claude/projects/{project-hash}/{session_id}.jsonl`.

**Create session tracker** at `.claude/tmp/{session_id}.json` using the Write tool. The schema (v3+) supports per-bead phase tracking and coordinate-phase tracking via the `worked_beads` object and `coordinate_tracking` field:

```json
{
  "schema_version": 3,
  "session_id": "{session_id}",
  "tracking_mode": "leroy",
  "started": "{UTC ISO8601 timestamp}",
  "branch": "{current git branch}",
  "transcript": "{transcript path from context}",
  "worked_beads": {},
  "coordinate_tracking": null,
  "compactions": []
}
```

**Schema notes (v3):**
- `worked_beads` is now an **object keyed by bead_id** (was array in v1). Each entry tracks per-phase forecasts/actuals, started timestamp, segments list, and `metrics_written` flag. See `.claude/docs/metrics-schema.md` for the full structure.
- `coordinate_tracking` is `null` until a multi-bead claim at Step 3d. When active: `{beads: [<id1>, <id2>], started: "ISO8601", session_id: "<sid>"}`.
- `--minimal` mode uses the same schema but doesn't auto-populate `worked_beads` (continuation mode skips new-bead claims). Users who want tracking on continued beads can invoke `.claude/scripts/token-tracking.py start` manually.


This file is gitignored (`.claude/tmp/.gitignore` excludes `*.json`).

### 2. Git Status Check

- Run `git status` and `git log -5 --oneline` as **two separate sequential Bash tool calls** (never chain with `&&`). In `--minimal` mode, skip `git log -5` — `git status` alone suffices.
- **If on `main`:** Pull latest with `git pull`, then create a feature branch before any work begins
  - Branch naming: `feature/work-YYYYMMDD-<short-description>`
  - **NEVER commit work directly to `main`** — all work must go through a feature branch + PR
- **If on a feature branch:** Check if it's up to date with origin, pull if needed
- **If there are uncommitted changes:** Ask the user what to do:
  - Commit them now (with a message)
  - Stash them for later
  - Continue without committing

### 3. Session Orientation (Navigator Subagent)

Delegate orientation to the navigator subagent to keep file reads out of the main context window:

Use the `Agent` tool with `subagent_type: navigator` and an invocation that matches the tier:

**Full mode prompt:**
> "Run session orientation for /leroy startup in FULL mode. Follow the procedure in your agent spec exactly — read handoff.yaml, changelog.yaml, enhancements.yaml, run bd commands, and return sections 1-8 as raw structured data. Section 9 (Enhancements Alert) is conditional — include only when triggered per the empty-state suppression rule."

**Minimal (continuation) mode prompt:**
> "Run session orientation for /leroy startup in CONTINUATION mode. Follow the procedure's continuation-mode subsection — read handoff.yaml entries[0], changelog.yaml entries[0], run a single `bd list --json --limit 0` corpus fetch, and emit sections 1, 2, 4, 5 only. Skip §3 (epic health from corpus is OK if cheap; else use handoff[0].epic_progress), §6 (no context-file mapping needed), §7 (no Recommended Work prompt — user continues from handoff), §8 (no sequential-group), §9 (no enhancements alert). In §5, render `~Turns` as `N/A` (do NOT call bd show per bead). Use label filter for triage:ready (not bd ready — no dependency check). Footer note must surface this trade-off."

The navigator reads handoff, changelog, enhancements counts (full mode only), and work item state in its own context. Main context only sees the returned summary.

**After the navigator returns, validate and format:**

**Step 3a — Validate.** Check the raw output contains the required section headers for the active tier:

**Full mode** — sections 1-8 required, §9 conditional:

1. `## 1. Last Handoff`
2. `## 2. Recent Work`
3. `## 3. Epic Health`
4. `## 4. In Progress`
5. `## 5. Ready to Start`
6. `## 6. Load Into Main Context`
7. `## 7. Recommended Work`
8. `## 8. Sequential-Group Candidates`
9. `## 9. Enhancements Alert` — **conditional**; absent on clean state (no kind exceeds threshold + no aging cohorts). Do NOT warn if missing — empty-state is the expected normal.

**Minimal mode** — sections 1, 2, 4, 5 required:

1. `## 1. Last Handoff`
2. `## 2. Recent Work`
4. `## 4. In Progress`
5. `## 5. Ready to Start` — with `~Turns: N/A` cells (Effort Forecast intentionally not loaded)

If the required sections for the active tier are missing, note it when presenting to the user:
"Navigator did not include [section] — may need to check manually."

**Step 3b — Format and present.** Convert the navigator's raw output into formatted tables for the user:

**Last Handoff** — render as a summary block:
```
**Last Session:** [branch] — [focus]
Completed: [work item IDs]. Next: [next_steps or "all done"].
```

**Recent Work** — render inline:
```
**Recent:** v[version] — [summary]
```

**Epic Health** — render as a table:
```
| Epic | Progress | Remaining |
|------|----------|-----------|
| [name] | [N]% ([X]/[Y]) | [Z] items |
```
Sort by completion % descending. Highlight any epic at 80%+ as near-complete.

**In Progress** — render as a table (or "None"):
```
| Item | Type | Description |
|------|------|-------------|
```

**Ready to Start** — render as a table with the unified column set (same shape in both Full and Minimal modes):

```
| Pri | Item | Type | Size | Cynefin | ~Turns | Description |
|-----|------|------|------|---------|--------|-------------|
```

- **Size** — from `size:*` label (S / M / L). Use `?` if absent (legacy bead).
- **Cynefin** — from `cynefin:*` label (clear / complicated / complex). Use `--` if unclassified. Beads labeled `cynefin:disorder` should be flagged with a warning — they need classification before claiming.
- **~Turns** — from per-bead Effort Forecast (full mode) OR `N/A` in `--minimal` mode (bd show intentionally skipped). Use `??` if Full mode and the forecast is missing.
- Show triage state (`ready`, `triaged`, `backlog`, or `unlabeled` for legacy beads) inline if not already filtered.

**Minimal mode footer note** (when rendering the table under `--minimal`):

> Label-filtered list (not bd-ready dep-checked). Beads with unmet blockers may appear; run `/leroy` (no `--minimal`) for dependency-checked picks.
> `~Turns: N/A` — Effort Forecast requires `bd show` (skipped in `--minimal`). For per-bead forecast, run `bd show <id>` after picking.

**Recommended Work** — render as numbered options for user selection:
```
1. **Continue:** [item-id] — [title] (if in-progress work exists)
2. **Close out:** [epic name] — [remaining item IDs]
3. **Next up:** [item-id] — [title]
```

**Sequential-Group Candidates** — render ONLY if §8 has entries (suppress empty-state noise). For each pair:
```
**Sequential-group candidate:** [A] + [B] share `[shared_scope_path]`; [B] [reason — e.g., "builds on A's helper" | "shares parent epic with A" | "overlapping file scope"]. Consider `/falcon work beads [A],[B] --sequential` (per example-t0l).
```
This surfaces opportunities to land overlapping-bead work in a single-worker sequential dispatch instead of two separate dispatches (saves ~10-20 steering orchestration turns + auto-inherits context). Only render the prose block when navigator returned at least one candidate.

**Enhancements Alert (§9)** — render ONLY if navigator emitted §9 (it's omitted entirely on clean state). For each bullet, render as:

```
**Enhancements alert — [kind]:** [N] open ([threshold] threshold)[, [M] over [age-floor]d old]. Suggestion: [review | retire-aged | archive-aged | promote-candidates].
```

Then ask the user once:

> N open `[kind]` entries exceed threshold — review now? (y / n / defer-this-session, default `n`)

Decision handling:
- **y** → dispatch a triage subagent with prompt: *"Walk the open `[kind]` entries from `.claude/enhancements.yaml` one-by-one. For each, present its summary + body + age and ask the user: resolve (apply now) / defer (keep open, suppress alert until next surface) / retire (drop from active count) / skip. Apply chosen transitions via `yq -i`. Lint with `yq '.' .claude/enhancements.yaml > /dev/null` after each write. Cap session at 10 entries to bound triage budget."* Then continue session orientation when the triage subagent returns.
- **n** → continue with session orientation; the alert reappears on next /leroy startup.
- **defer-this-session** → continue with session orientation; suppress this kind's alert for the rest of this session only (no file change). Useful when you want to focus on work and address the queue later.

This is the forcing function that prevents `enhancements.yaml` from drifting into a museum: accumulation surfaces at startup; triage is opt-in but visible.

**Load Into Main Context** — do not display to user; hold for Step 3e.

**Step 3c — Ask and select.** Ask what the user would like to work on:
   - Continue: [in-progress item if any]
   - Close out: [near-complete epic with specific remaining items]
   - Next up: [top ready item]
   - Something else — describe what you'd like to do

**Step 3d — Plan selected work.** After the user selects beads to work on:

- Gather bead metadata: run `bd show <id>` for each selected bead.
- **Decide whether to dispatch a specialist (cynefin-gated):**

  | Selected beads | Specialist? | Action |
  |---|---|---|
  | Single bead, `cynefin:clear` label | **Skip** | The bead body IS the plan — present it directly. See "Direct presentation" below. |
  | Single bead, `cynefin:complicated` | Run | Specialist sanity-checks the approach against Required Context contracts. |
  | Single bead, `cynefin:complex` | Run | Spike/decision template — specialist must plan the findings work. |
  | Multi-bead (2+) any cynefin mix | Run | Specialist coordinates execution order + catches cross-bead dependencies. |
  | Single bead, `cynefin:disorder` / `chaotic` | N/A | These cannot reach `triage:ready` — should not appear here. If they do, refine before claim. |

  Inspect cynefin via the `cynefin:*` label on `bd show` output. The label is required by the Readiness Checklist (per `.claude/docs/work-item-templates.md`).

- **Skip path (single `cynefin:clear`):** present the bead body directly as the plan:
  - Echo a 3-line summary: `Bead: [id] | cynefin:clear | effort: [Total turns from Effort Forecast]`
  - Echo the `## Changes Needed` table verbatim (it IS the plan)
  - Echo the AC checklist (it IS the verification gate)
  - State: "cynefin:clear — no specialist routing needed. Bead body is the execution plan. Proceed to Step 3e on user confirm."
  - The Required Context section (optional for clear beads, often empty) determines whether any `.claude/*.md` Read is needed in Step 3e.

- **Run path (everything else):** call navigator dispatcher with bead IDs + metadata — use the `Agent` tool with `subagent_type: navigator` and prompt:
  ```
  "Route to the appropriate specialist for these beads: [IDs].
  Bead metadata:
  [paste full bd show output for each bead]"
  ```
  - Navigator auto-routes to survey (complex/multi-bead) or maintenance (simple/chore).
  - Present the returned plan to the user.

The cynefin gate honors the bead author's own classification — if they marked it `clear`, the bead is atomic and the specialist adds no signal. Authors who want a specialist sanity check on a `clear` bead can downgrade the label to `complicated` OR ask explicitly ("can you sanity-check this before I start?") — either is cheaper than routing every clear claim through a specialist by default.


**Step 3d.2 — Start coordinate tracking (multi-bead claims only).** If the user selected 2+ beads in Step 3c, start coordinate-phase tracking BEFORE navigator dispatches the specialist (the planning cost is real and should be captured):

```bash
.claude/scripts/token-tracking.py start --coordinate \
  --beads "<id1>,<id2>,..." \
  --session "$SESSION_ID"
```

Update the session tracker's `coordinate_tracking` field: `{beads: [...], started: "<ISO8601>", session_id: "<sid>"}`.

Skip this if user picked a single bead (no coordination overhead to measure).

**Step 3d.5 — Stop coordinate tracking after plan is confirmed.** Only if Step 3d.2 started it. After the user confirms the specialist's plan (or before Step 3e claims), stop:

```bash
.claude/scripts/token-tracking.py stop --coordinate --session "$SESSION_ID" --json
```

The stop output's JSON includes the coordinate-phase token counts and per-bead allocation method (`equal_split` is the default). The next /wrapup Task 3c flushes this segment to metrics.jsonl with `phase: "coordinate"`.

**Step 3e — Claim and track.** After the plan is presented and user confirms (and coordinate tracking is stopped if applicable):

- For each bead: verify `bd state <id> triage` returns `ready` or has no triage label (legacy). If `backlog` or `triaged`, complete triage first per workflow.md.
- For each bead: `bd update <id> -s in_progress`
- **For each bead, start per-phase tracking:**

  ```bash
  .claude/scripts/token-tracking.py start --bead "<id>" --phase plan --session "$SESSION_ID"
  ```

  Update the session tracker's `worked_beads[<id>]` entry with:
  ```json
  {
    "started": "<ISO8601>",
    "phase_active": "plan",
    "forecasts": { ...from bd show Effort Forecast section... },
    "segments": [],
    "metrics_written": false
  }
  ```

  Phase transitions during work: user/agent runs `stop --bead <id>` then `start --bead <id> --phase <next>` to move plan → discover/implement/test/fix. The tracker handles cross-session resume automatically (start with same bead + same phase + new session ID banks tokens and starts new segment).

- **Read context files based on the Step 3d path:**
  - **Skip path (single `cynefin:clear`):** read ONLY the files named in the bead's `## Required Context` section (often empty for clear beads — read nothing). No specialist recommendations to honor.
  - **Run path (specialist dispatched):** read ONLY the context files recommended by the navigator specialist in its output.
- Confirm: "Beads claimed, tracking active (phase: plan). Ready to implement."

**`--minimal` (continuation mode) note:** in --minimal, Step 3d/3d.5/3e are skipped (no new claims). Per-bead tracking is NOT auto-started. If the user wants metrics on a resumed bead, they can invoke `.claude/scripts/token-tracking.py start --bead <id> --phase <phase> --session "$SESSION_ID"` manually. This is the deliberate tradeoff for the fast-path mode.
