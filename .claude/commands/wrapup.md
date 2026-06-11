---
description: Full session wrapup — verify, commit, update work items, handoff with progress, retro
tier: scale
version: 2.13.2
created: 2026-03-21
changelog:
  - 2.13.2 (2026-06-10): Task 3c — collapse the two `bd list --updated-after` calls into a single corpus fetch + in-memory `select(.status == "closed")` filter. Same pattern as `check-bead-contract.py`'s corpus-fetch. Saves one ~750ms bd subprocess call per wrapup; total bd calls across /wrapup drops from 3 → 2 (Task 3c at 1 + Task 9b's check-bead-contract.py at 1). No semantic change to the three sets (TRACKED/TOUCHED/CLOSED).
  - 2.13.1 (2026-06-10): Task 3c — align with the `check-bead-contract.py --session` session-bounded pattern. Work set now derived from `bd list --updated-after $SESSION_STARTED` (three sets: TRACKED_BEADS from session tracker, TOUCHED_BEADS from bd, CLOSED_BEADS from bd). Surfaces two new audit gaps as wrapup-report WARNs: (1) UNTRACKED_TOUCHED — beads updated via direct bd commands outside /leroy claim flow, missing effort data; (2) ORPHANED_CLOSURES — beads closed without tracking, silent gaps in the forecast-vs-actual calibration loop. Synthesis-mode cross-checks falcon worker reports: stashed `effort_actual` per closed bead synthesizes a metrics.jsonl line (`phase: "implement"`, `allocation_method: null`). Outcome summary block emitted at task end with tracked/untracked/orphaned/synthesized counts. Future `--strict-tracking` flag noted for promoting WARNs → FAILs (out of scope for this version). Pattern parallels lint flow: derive work-set from session start, validate each bead, surface gaps inline, wrapup continues.
  - 2.13.0 (2026-06-10): Add Task 3c (Finalize Token Tracking). Flushes pending token-tracking segments from `.claude/tmp/.token_tracking/` to `.claude/metrics.jsonl` via the `jq -n -c` template (schema reference `.claude/docs/metrics-schema.md`; validator `.claude/schemas/metrics.schema.json`). Handles: status-check per bead, orphan auto-stop with warning, coordinate-phase flush for multi-bead claims (allocation_method: "equal_split"), verify (every `worked_beads` entry appears in metrics.jsonl), schema spot-check on last N lines, tracker cleanup. Runs unconditionally — even under `--minimal` — because the calibration data is too valuable to skip for fast-path sessions. Pairs with leroy v2.9.0 (Step 1b schema v3 + Step 3d/3e tracking starts), token-tracking.py (5-phase: plan/discover/implement/test/fix + coordinate), session-start.sh hook, and the kit-shipped settings.json hook registration. Closes the forecast-vs-actual calibration loop introduced by DAR 5/8 (Effort Forecast contract + check-bead-contract.py 5-phase enforcement). check-bead-contract.py CONTRACTS_VERSION bumped 1.1 → 1.2.
  - 2.12.0 (2026-06-10): Convert `.claude/standards-history.md` (free-form markdown) → `.claude/standards-history.yaml` (typed audit log with slug-keyed rules + ID-bearing firings). Same pattern as DAR 4 (enhancements.md → YAML). Schema reference: new `.claude/docs/standards-history-schema.md`. Rules keyed by stable slug (auto-generated kebab-case from title, manually overridable); `section_ref` is presentational and can change on renumbering without breaking firing references. Each firing carries `id: YYYYMMDD-N` (sequential within date) for cross-reference; `rule_id` MUST match a key in `rules{}`. Task 8b rewritten to emit structured YAML firing entries via `yq -i` (resolves rule slug from stashed `section_ref`; files workflow_friction if the rule isn't recorded). Task 9 Self-Reflection prompt 2's promotion path now executes the full sequence: generate slug, pick section_ref, append rule definition to `rules/development-standards.md`, add rule entry to `standards-history.yaml`, transition the enhancements.yaml entry to `status: promoted`. New Promotion Pipeline Review step after prompts 1-3 surfaces three cohorts: near-promotion (firings:2), aged-out (firings:1 + >180d, batch-prompt to retire), deprecation candidates (rules with no firings in 90d, advisory only). Closes the DAR 9 promise that the candidate pipeline is visible and actionable. Migration path: same Option 1 (archive + start fresh) / Option 2 (hand-port) pattern as DAR 4.
  - 2.11.0 (2026-06-10): Task 9b subsection `b. Validate beads touched this session` now calls `.claude/scripts/check-bead-contract.py --session` as the primary tier-contract check (replaces the inline `bd lint <id>` loop). The script enforces the full tier contract from `work-item-templates.md` (backlog/triaged/ready label + section + rule requirements) across beads touched this session, derived from the session-tracker's `started` timestamp (Dolt-aware; no dependency on `.beads/issues.jsonl` being staged). Exit codes block wrapup on HARD violations; SOFT violations warn but continue. Fallback path preserved for projects that haven't vendored the script. Companion: new `.claude/docs/lint-integration.md` documents pre-push hook, CI step, and wrapup integration recipes. Closes the DAR 5 promise that "Required Context is enforced by bd lint per the kit's contract" — the kit now ships the contract enforcer directly.
  - 2.10.0 (2026-06-10): Add `/wrapup --minimal` tier. New "Tier Detection" section between Pre-Check and the IMPORTANT TaskCreate preamble decides Full vs Minimal. Minimal runs only Tasks 2 (verify), 7 (commit + push), 8 (handoff). All other tasks skipped. Conflict handling: `--minimal` + synthesis mode → fall back to Full with inline warning (worker reports must be absorbed; the `--minimal` intent contradicts synthesis-mode reality). `--minimal` + `--feedback` → `--feedback` becomes no-op (Task 9 skipped under --minimal). Task 8 emits a session-shape hint when --minimal is invoked AND substantive markers fire (≥1 bead closed, ≥2 opened, ≥3 commits, ≥5 files touched, or `.claude/*.md` edited). Hint warns the user --minimal may have under-captured signal; soft warning, not a block. Estimated savings ~5M eff-tokens + ~5 min turn-time per qualifying minimal wrapup; ~20% of wrapups qualify (typo fixes, mid-feature checkpoints).
  - 2.9.0 (2026-06-10): Task 4 absorbs falcon worker `unlisted_context_reads[]` (new in falcon v7.2.0) as `kind: doc_gap` entries against the originating bead. Each ad-hoc `.claude/*.md` Read a worker had to do during execution becomes structured signal that the bead's `## Required Context` section was incomplete. Closes the hydration-discipline learning loop introduced by the bead Required Context contract (work-item-templates.md) + navigator-recon v1.4.0 + falcon dispatch yaml `required_context[]` field. The doc_gap's `target` is `bd:<bead_id>` (the bead itself), not a `.claude/*.md` file — the gap is in the bead spec.
  - 2.8.0 (2026-06-10): Convert `.claude/enhancements.md` (free-form markdown) → `.claude/enhancements.yaml` (typed log with status state machine). Resolves a long-standing category collision where Task 4 wrote small doc-gap items intended for `[RESOLVED]` lifecycle and Task 9 wrote retro narratives + standards candidates intended to accumulate. New schema (see `.claude/docs/enhancements-schema.md`) splits content by `kind: doc_gap | retro | standards_candidate | workflow_friction | tooling_pain | other`, each with its own state transitions. Task 4 rewritten to emit structured YAML entries via `yq -i`. Task 6 rewritten to query open doc-gap/friction/pain entries by target doc, apply fixes, and transition `status: resolved` via `yq -i` (explicit field mutation replaces the buried inline `[RESOLVED]` tag that historically never fired). Task 9 Self-Reflection Mode prompt 2 now detects existing matching candidates via fuzzy search, increments `firings` count rather than appending duplicates, and transitions to `status: promoted` when `firings >= 3`. Task 9 Interactive Mode questions now route to specific kinds (retro / standards_candidate / doc_gap / tooling_pain / workflow_friction). Paired with `navigator-recon` v1.3.0 (new §9 Enhancements Alert at /leroy startup) and `leroy.md` v2.6.0 (alert rendering + triage subagent dispatch). Migration path for projects with legacy markdown enhancements.md documented in `.claude/docs/enhancements-schema.md` (Option 1: archive and start fresh; Option 2: hand-port entries — no automated script ships; the category collision in legacy files doesn't auto-classify cleanly).
  - 2.7.1 (2026-06-10): Restore Task 10 (Update Environment Health Checks) — v2.7.0 removed it and tried to absorb the coverage into Task 6's path-mapping table, but that conflates the two concerns. Task 10's purpose is forward-looking maintenance of `/leroy`'s startup signal (the `architecture.md` Environment Health Checks table that future sessions consume) and warrants its own visible task even when it no-ops, so the discipline of "did anything infrastructure-shaped change?" doesn't get lost. Task 6's `architecture.md` row reverted to the v2.6.0 form (no env-health row). Pairs with the new `/leroy --skip-health` flag (leroy v2.5.0) which lets the user opt out of running the checks at startup without changing the wrapup-side maintenance discipline.
  - 2.7.0 (2026-06-10): Consolidate low-frequency tasks. Tasks 1 (archive plans), 3b (validate beads), and 11 (improve session startup) merge into a single new Task 9b (Verification Sweep) — one TaskCreate/TaskUpdate cycle instead of three. Rationale (measured field-deployment data): Tasks 1/3b/11 produced zero artifacts in the majority of sessions where they fired (Task 11: 0/1; Task 3b: 0/9; Task 1: 1/6) yet each spent 300–500k eff-tokens on TaskCreate→Bash→TaskUpdate ceremony for a "look around and report" check. Single sweep saves ~3× the cache-read floor while preserving visibility — the user still sees a "Sweep: plans=none, beads=3 linted clean, startup=none" outcome line. No semantic change for sessions where these checks actually fire: any non-trivial action surfaced by the sweep spawns a separate follow-up TaskCreate per the spec.
  - 2.6.0 (2026-06-10): Task 9 — default to focused Self-Reflection Mode (3 prompts: what burned time, what should never happen again, surprise-DAR patterns). The model reflects internally and writes to enhancements.md / standards-history.md without pausing for user input. Adds `/wrapup --feedback` flag for the original 6-question Interactive Mode that waits for user responses. Rationale (from measured field-deployment data 2026-05-04 → 2026-06-06): self-retros produced the durable rule library (§3.6, §3.9, §3.10, §3.12 + multiple candidates) and should not be cut, but the 6-question form burns ~743k eff-tokens median when the user is absent and the high-value signal concentrates in 2 of 6 prompts (what burned time + what should never happen again). Self-Reflection Mode keeps the rule-promotion pipeline while focusing the prompts on the signals that historically promoted. Interactive Mode is preserved unchanged behind the explicit flag for sessions where the user wants to provide feedback.
  - 2.5.0 (2026-06-10): Pre-Check gate hoists the falcon-stash detection above the TaskCreate phase. When no stash is present, Tasks 0, 0b, 8b, 8c are OMITTED from the TaskList entirely (not just no-op'd via TaskUpdate completion). Saves ~1.5M eff-tokens per direct-work wrapup (the ~70% case in measured field-deployment data) by eliminating the per-task cache-read floor + TaskCreate→TaskUpdate ceremony for tasks that produce nothing in direct-work mode. Synthesis-mode behavior on stash-present sessions is unchanged. The synthesis-mode forks inside Tasks 3, 4, 5, 6, 8 already no-op correctly when stash is absent, so the gate is purely a ceremony-cost optimization with no behavior change.
  - 2.4.0 (2026-05-22): Task 3 — adopt `bd batch` (added in bd 1.0.1) as an opt-in optimization on the existing **Close completed** and **Update in-progress** bullets when 3+ beads need state changes in one wrapup. The semantic-category bullet structure (close / update / create / comment / validate) is preserved; bd batch is mentioned in-line on the applicable bullets and the caveats live in one consolidated "bd batch notes" callout below the bullets. Atomic-rollback applies: if any entry fails (stale ID, already-closed bead, invalid status), the entire batch rolls back. Batch grammar covers only close + update-status/priority/title/assignee — NOT body writes, label ops, `set-state`, `comments add`, or `bd export`. The `bd export -o .beads/issues.jsonl` flush is still required after `bd batch` because batch does not auto-flush jsonl.
  - 2.3.0 (2026-05-21): Falcon-awareness — check for `.claude/tmp/falcon-reports-<branch>.yaml` at start; if present, switch to synthesis mode (draw changelog + handoff + enhancements + standards_firings + decisions from the stashed report rather than reconstructing from raw git/bd). Retire `bd sync` reference (removed in bd 1.0; use `bd export -o .beads/issues.jsonl`). New Task 0 (falcon synthesis check) + augmented Tasks 3, 4, 5, 6, 7, 8 + new Task 8b (standards-history append) + new Task 8c (decisions log) + stash cleanup on wrapup success.
  - 2.2.0 (2026-05-03): Task 3c — split per-bead and coordinate-phase metrics flush so multi-bead planning cost is no longer silently dropped at wrapup
  - 2.1.0 (2026-04-25): Wrap token-tracking flush in metrics:on blocks; upgrade to status-check + jq metrics.jsonl flush
  - 2.0.0 (2026-03-21): Full rewrite — TaskCreate enforcement, beads validation, token tracking, context doc checklist
  - 1.1.0 (2026-03-21): Add tracker-conditional blocks, env health check updates
  - 1.0.0 (2026-03-21): Initial tiered version
---

# /wrapup — Full Session Wrapup

> **Philosophy:** No wrap-up, no merge. If you don't wrap up, your next session starts by rediscovering decisions.

---

### Pre-Check: Synthesis-Mode Detection (run BEFORE creating any tasks)

Determine whether this wrapup runs in **synthesis mode** (a falcon dispatch produced a stash to consume) or **direct-work mode** (no stash; everything came from this session). The result decides which tasks appear in your TaskList.

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD | tr '/' '-')
STASH=".claude/tmp/falcon-reports-${BRANCH}.yaml"
LOCKS=$(ls .claude/tmp/falcon-*.json 2>/dev/null | head -1)
if [ -f "$STASH" ] || [ -n "$LOCKS" ]; then
  echo "SYNTHESIS-MODE: stash=$([ -f "$STASH" ] && echo yes || echo no) locks=$([ -n "$LOCKS" ] && echo yes || echo no)"
else
  echo "DIRECT-WORK"
fi
```

- **If output starts with `SYNTHESIS-MODE`** → create the **full TaskList** below, including Tasks 0, 0b, 8b, 8c. Each synthesis-mode task operates on the stash + lock-registry.
- **If output is `DIRECT-WORK`** → create the TaskList **OMITTING Tasks 0, 0b, 8b, 8c entirely**. Do NOT create them with intent to immediately mark complete — skip the TaskCreate for those four tasks. State once, inline: *"Direct-work mode — no falcon stash; synthesis-mode tasks (0, 0b, 8b, 8c) omitted from TaskList."*

The synthesis-mode forks inside Tasks 3, 4, 5, 6, and 8 already no-op gracefully when the stash is absent, so their direct-work branches handle the rest. The gate here is a ceremony-cost optimization (~1.5M eff-tokens saved per direct-work wrapup) — no behavior change for synthesis-mode wrapups.

---

---

### Tier Detection: Full vs Minimal

`/wrapup` runs at one of two tiers, decided by whether the invocation included the `--minimal` flag:

- **Default (no flag) — Full wrapup.** Run the standard TaskList below (gated by Pre-Check for synthesis tasks). Use for sessions that produced substantive output: closed beads, new patterns, doc updates, multi-commit work.
- **`--minimal` flag — Minimal wrapup.** Run only **Task 2 (build verification)**, **Task 7 (commit + push)**, **Task 8 (handoff entry)**. Skip all other tasks. Use for: typo fixes, single-commit tweaks, mid-feature checkpoints, experiments that didn't pan out. Saves ~5M eff-tokens vs full ritual.

**Conflict: `--minimal` + synthesis mode → fall back to Full.** If Pre-Check returned `SYNTHESIS-MODE` AND the user invoked `--minimal`, falcon worker reports landed and need to be absorbed (changelog seeds, standards firings, DAR decisions, `unlisted_context_reads[]`). The `--minimal` intent ("this was small") contradicts the synthesis-mode reality ("workers landed real work"). Emit the warning inline and run the full ritual:

> "`--minimal` invoked but synthesis mode detected ({stash path}). Falcon worker reports must be absorbed — running full ritual to preserve worker signal. Run `/wrapup` without `--minimal` next time when workers landed."

**`--minimal` + `--feedback` interaction.** Under `--minimal`, Task 9 (retro) is skipped, so `--feedback` (which controls Task 9's interactive mode) becomes a no-op. Document this inline if both flags appear.

---

**IMPORTANT: You MUST use TaskCreate to create a task for EVERY checklist item below BEFORE starting any work — EXCEPT the synthesis-mode tasks (0, 0b, 8b, 8c) gated by the Pre-Check above AND, when running `--minimal`, tasks other than 2/7/8 (and synthesis tasks if the conflict fallback fired). Then use TaskUpdate to mark each task `in_progress` when you start it and `completed` when done. Do NOT skip any task — if a step is not applicable, mark it completed with a note explaining why. The user can see task progress and will hold you accountable for completing every item.**

Create all tasks first (per the Pre-Check + tier decision), then work through them in order:

---

### Task 0: Check for Falcon Synthesis Mode

> **Gated:** include this task in the TaskList ONLY if the Pre-Check returned `SYNTHESIS-MODE`. In direct-work mode, omit entirely.

**This MUST run before Task 3.** If falcon dispatched workers on this branch, the stash file pre-structures bead outcomes / commits / enhancements / standards firings / DARs / next steps / epic progress that downstream tasks should consume rather than re-derive cold.

```bash
# Falcon sanitizes `/` → `-` in the stash filename so branches like
# feature/work-YYYYMMDD-foo don't accidentally create a directory hierarchy.
BRANCH=$(git rev-parse --abbrev-ref HEAD | tr '/' '-')
STASH=".claude/tmp/falcon-reports-${BRANCH}.yaml"
[ -f "$STASH" ] && echo "synthesis-mode: $STASH"
```

- **If the stash file exists** (synthesis mode): downstream tasks draw from the stashed `beads[]`, `discovered_beads[]`, `enhancements[]`, `standards_firings[]`, `decisions_for_human[]`, `blockers_for_steering_session[]`, `recommended_next_steps[]`, `epic_progress[]`, `changelog_seed{}`. Each task notes its synthesis-mode behavior inline.
- **If absent** (direct-work mode): proceed as before — derive everything from `git log`, `bd list`, `bd ready`, and what this session did.
- **After Task 8c completes successfully:** archive the stash so the next session's wrapup doesn't double-count:

   ```bash
   mkdir -p .archive/falcon-reports/
   mv "$STASH" .archive/falcon-reports/${BRANCH}-$(date +%Y%m%d-%H%M%S).yaml
   ```

Per `.claude/commands/falcon.md`: the stash is **branch-keyed** and accumulates across `/falcon` invocations within the same branch. One wrapup at branch-close consumes the union.

**If no falcon dispatches happened this branch:** mark completed with "Direct-work mode — no falcon stash."

### Task 0b: Audit Falcon Lock Registry

> **Gated:** include this task in the TaskList ONLY if the Pre-Check returned `SYNTHESIS-MODE`. In direct-work mode, omit entirely.

Run `/falcon list-locks` (or inline the equivalent: glob `.claude/tmp/*.json`, parse each `falcon_dispatches[]` array, filter `status: "in_progress"` for this branch). For each lingering entry:

- **Lock has a matching entry in the stash** → benign; the lock release happens when steering validates that dispatch's report. Skip.
- **Lock has NO matching entry in the stash** → orphan; worker crashed or session ended without returning a report. Run `/falcon release <dispatch-id>` after confirming with the user.

This protects the next session from a HARD-reject on file_scope overlap when no real work is in progress.

**Agent-viewer post-release check (v7.0.1, fdev-lbq.18):** in `--bg` mode, `/falcon release` follows a poll-then-rm ordering that ends with `claude rm <worker_bg_session_id>` to remove the dead row from `claude agents`. After releasing each orphan, verify the row is gone:

```bash
claude agents --json | jq -r ".[] | select(.sessionId == \"<worker_bg_session_id>\") | .sessionId"
```

If the query returns the session ID (row still present), either `claude rm` failed silently OR `worker_bg_session_id` was null on the dispatch file. Surface the inconsistency inline — don't block wrapup, but log a single-line warning.

- **If no orphan locks:** mark completed with "No stale falcon locks."
- **If orphan locks were released:** confirm post-release that `claude agents --json` shows no rows for the released session IDs. Note any mismatches inline.

---

### Task 2: Build Verification

**No green, no commit.**

Run the full verification suite. Read `architecture.md` or `package.json` / `Cargo.toml` / `pyproject.toml` to determine the correct commands:

- **Typecheck:** if applicable (e.g., `npx tsc --noEmit`, `mypy .`)
- **Tests:** project test runner (e.g., `npm test`, `pytest tests/ -q`, `cargo test`)
- **Linter:** project linter (e.g., `npm run lint`, `ruff check .`)
- **E2E tests:** if configured (e.g., `npm run test:e2e`, `npx playwright test`)
  - If E2E tests fail due to infrastructure (backend/frontend not running), note it and skip
  - If E2E tests fail due to actual regressions, fix before committing
- **Bead lint:** run `bd lint` on any beads closed this session to validate completeness

**Do NOT proceed to commit if builds fail — fix first.**

> **Synthesis-mode note:** falcon workers already ran their own bead-specific verification before close. This wrapup-level pass is a regression sweep across the union of all work on the branch. Each report's `beads[].verification.evidence` field documents what the worker exercised; the wrapup verification need not duplicate that, but must catch cross-bead interactions the worker couldn't see.

### Task 3: Beads Issue Updates

Update issue tracking for work completed this session:

**Synthesis-mode partition (do this first):** for each stashed `beads[]` entry, run `bd state <id>` to confirm the worker's outcome matches reality. Partition into:
- **Falcon-closed** (`outcome: closed` AND `bd state` returns closed) → skip `bd close` (already done; idempotent re-close is harmless but clutters output)
- **Falcon-partial** (`outcome: in_progress` OR `blocked`) → these still need steering-session decisions; treat as direct-work beads below
- **Direct-work** (worked in this steering session, not in any stash) → full close/update flow below

Then for the non-Falcon set:

- **Close completed:** `bd close <id>` for finished work. When closing 3+ beads in one wrapup, prefer wrapping all closes in a single `bd batch` invocation (see "bd batch notes" below).
- **Update in-progress:** `bd update <id> --status in_progress` for beads worked on but not finished this session. Same `bd batch` optimization applies when 3+ status updates are needed at once.
- **Create follow-ups:** `bd create "<title>"` for discovered work items.
- **Add comments:** `bd comments add <id> "<note>"` with implementation details or decisions made.
- **Validate effort forecasts:** `bd comments add <id> "Effort: forecast=N actual=N"` — compare estimated vs actual.

**`bd batch` notes (when wrapping bulk close + status-update writes):**

- Atomic-rollback applies: if any entry fails (stale ID, already-closed bead, invalid status), the entire batch rolls back and none of the others apply. A single bad ID in a 15-bead close set means re-running the whole batch after fixing the bad ID.
- Batch grammar covers `close <id> [reason...]` and `update <id> <key>=<value>` where key ∈ `{status, priority, title, assignee}`. It does NOT cover `--body-file`, label operations, `bd set-state`, `bd comments add`, or `bd export` — those continue to use their dedicated commands per-call.
- `bd create` is technically in the grammar but only supports `<type> <priority> <title>` (no labels, no body, no parent) — verify scope before adopting.
- `bd batch` does NOT auto-flush jsonl. Always follow with `bd export -o .beads/issues.jsonl`.

**Synthesis mode — discovered_beads:** for each stashed `discovered_beads[]` entry with `created: false`, run `bd create` now using `title`, `type`, and `--deps "discovered-from:<discovered_from>"`. Entries with `created: true` are already in bd — verify with `bd show <id>` and skip.

**Synthesis mode — out-of-band closures:** for each stashed bead with `verification.out_of_band_required: true` AND `outcome: in_progress`, surface the bead ID + the closure command per falcon Step 3 so the user can relay the human verification outcome before close.

- **If no beads changed:** mark completed with "No beads to update"

### Task 3c: Finalize Token Tracking

Flush pending token-tracking segments to `.claude/metrics.jsonl` AND audit completeness — every bead with bd state changes this session should have effort data. Schema reference: [`.claude/docs/metrics-schema.md`](../docs/metrics-schema.md). Validator: [`.claude/schemas/metrics.schema.json`](../schemas/metrics.schema.json).

**Pattern parallel to `check-bead-contract.py --session`:** both tasks derive their work set from `bd list --updated-after $SESSION_STARTED` (the session tracker's `started` timestamp). One validates contract compliance; the other validates effort tracking completeness. Surfacing untracked closed beads is the calibration loop's "lint" — closures without metrics are silent gaps in the forecast vs actual signal.

**Runs unconditionally — even in `--minimal` mode.** The flush is cheap (~50k eff-tokens per bead) and the data is the calibration signal that makes Effort Forecast refinement possible.

**Skip ONLY if:** the session tracker JSON (`.claude/tmp/{session_id}.json`) doesn't exist — that's an ad-hoc session that never claimed a bead through /leroy Step 3e. Mark completed with "No session tracker — ad-hoc session."

---

**1. Derive the session work set** from the session tracker + bd state. ONE `bd list` call + in-memory filter — same corpus-fetch pattern as `check-bead-contract.py`:

```bash
TRACKER=".claude/tmp/${SESSION_ID}.json"
SESSION_STARTED=$(jq -r '.started' "$TRACKER")

# Set A: beads we tracked (keys of worked_beads) — no bd call
TRACKED_BEADS=$(jq -r '.worked_beads | keys[]' "$TRACKER" | sort -u)

# Single bd corpus fetch for everything touched this session
CORPUS=$(bd list --json --limit 0 --updated-after "$SESSION_STARTED")

# Set B: ALL beads with bd state changes this session
TOUCHED_BEADS=$(echo "$CORPUS" | jq -r '.[] | .id' | sort -u)

# Set C: beads CLOSED this session (in-memory filter, no additional bd call)
CLOSED_BEADS=$(echo "$CORPUS" | jq -r '.[] | select(.status == "closed") | .id' | sort -u)
```

The cross-sections that matter:

| Set | Meaning | Action |
|---|---|---|
| `TRACKED_BEADS` | Have tracking data from /leroy Step 3e | **Flush** segments to metrics.jsonl (steps 2-5) |
| `TOUCHED_BEADS - TRACKED_BEADS` | Updated via `bd update`/`bd comments add` outside /leroy claim flow | **WARN** — bead touched but no effort data captured |
| `CLOSED_BEADS - TRACKED_BEADS` | Closed without going through /leroy claim flow | **WARN** — orphaned closure; effort data missing for the calibration loop |

---

**2. For each `BEAD_ID` in `TRACKED_BEADS`:** check tracking status:

```bash
.claude/scripts/token-tracking.py status --bead "$BEAD_ID" --json
```

- **If `active_phase` is null** — properly stopped. Proceed to step 4 with the existing segments.
- **If `active_phase` is not null** — orphan (user left a phase open). Stop it:

  ```bash
  .claude/scripts/token-tracking.py stop --bead "$BEAD_ID" --json
  ```

  Mark resulting segments as `orphaned: true`. Surface a one-line warning so the user knows the last phase was auto-stopped.

**3. Coordinate-tracking flush:** if the session tracker's `coordinate_tracking` field is non-null AND `metrics_written: false`:

```bash
.claude/scripts/token-tracking.py status --coordinate --session "$SESSION_ID" --json
```

If `active_phase` is still set, stop it first. Append the resulting segment to metrics.jsonl with `phase: "coordinate"`, `allocation_method: "equal_split"`, `beads_in_scope: [...]`.

**4. Append all pending segments to `.claude/metrics.jsonl`** using the `jq -n -c` template documented in [`metrics-schema.md`](../docs/metrics-schema.md) ("Writer pattern"). Required fields: `schema_version: 1`, `record_type: "bead_effort"`, bead/session/branch metadata, phase, forecast_*, actual_*, turns, started/stopped/timestamp.

- For multi-bead planning records: `allocation_method: "equal_split"`, populate `beads_in_scope`
- For per-bead records: `allocation_method: null`, `beads_in_scope: []`
- After each append, flip `metrics_written: true` in the session tracker (idempotent reruns)

---

**5. Audit gaps — touched but not tracked.** Compute the gap set:

```bash
UNTRACKED_TOUCHED=$(comm -23 <(echo "$TOUCHED_BEADS") <(echo "$TRACKED_BEADS"))
```

For each ID in `UNTRACKED_TOUCHED`, emit a warning to the wrapup report:

```
WARN: bead <id> was updated this session but has no effort tracking.
  - State change: <bd state summary>
  - To capture effort next time: invoke `.claude/scripts/token-tracking.py start --bead <id> --phase <phase> --session $SID` after claiming.
  - No metrics record will be created for this bead this session.
```

This is the **same shape as `check-bead-contract.py --ids fail`** — gap surfaced inline, user has clear remediation, wrapup continues.

**6. Audit gaps — closed without tracking (critical).** Compute the orphaned-closure set:

```bash
ORPHANED_CLOSURES=$(comm -23 <(echo "$CLOSED_BEADS") <(echo "$TRACKED_BEADS"))
```

For each ID in `ORPHANED_CLOSURES`, emit a stronger warning:

```
WARN: bead <id> closed this session but no effort tracking record exists.
  - This is a silent gap in the forecast vs actual calibration loop.
  - The bead's Effort Forecast cannot be calibrated without an actuals record.
  - If you intend metrics: re-open the bead (`bd reopen <id>`), start tracking, finish work, then re-close.
  - If you accept the data loss: continue. The bead stays closed; metrics.jsonl gets no record for it.
```

For the synthesis-mode case: stashed falcon worker reports include `effort_actual` per bead, which IS the metrics record. Cross-check: if the falcon stash has the closed bead's `effort_actual`, the closure isn't truly orphaned — synthesize a metrics.jsonl line from the worker report's effort numbers using `phase: "implement"` (or the phase named in the worker report) and `allocation_method: null`.

---

**7. Verify the flush** for tracked beads:

```bash
EXPECTED=$(echo "$TRACKED_BEADS")
ACTUAL=$(jq -r --arg sid "$SESSION_ID" 'select(.session_id == $sid) | .bead_id' \
         .claude/metrics.jsonl | sort -u)
MISSING=$(comm -23 <(echo "$EXPECTED") <(echo "$ACTUAL"))
[ -z "$MISSING" ] || echo "ERROR: flush incomplete — missing: $MISSING"
```

If any tracked bead is missing from metrics.jsonl, the flush is incomplete — go back to step 4.

**8. Validate the schema** on the most-recently appended lines:

```bash
N=$(echo "$TRACKED_BEADS" | wc -l)
tail -n "$N" .claude/metrics.jsonl | \
  while IFS= read -r line; do
    echo "$line" | jq -e '.schema_version == 1 and .record_type and .bead_id and .phase' > /dev/null \
      || echo "ERROR: invalid metrics line: $line"
  done
```

(Optional: use `ajv-cli` for full schema validation against `.claude/schemas/metrics.schema.json`.)

**9. Cleanup:**
- Delete `.claude/tmp/{session_id}.json` (the session tracker)
- Delete `.claude/tmp/.token_tracking/<bead-id>.json` for beads that closed this session

---

**Outcome summary** (emit to wrapup report):

```
Task 3c — Finalize Token Tracking:
  ✓ Tracked beads flushed: N (forecast/actual records appended to metrics.jsonl)
  ⚠ Untracked-touched beads: M (effort data NOT captured; see warnings above)
  ⚠ Orphaned closures: K (closures without metrics record; see warnings above)
  Synthesis-mode synthesized records: J (from falcon worker reports)
```

**Skip conditions:**
- **No session tracker** → "No session tracker — ad-hoc session"
- **Empty TRACKED + TOUCHED + CLOSED sets** → "No beads touched this session"
- **`--minimal` mode:** runs unchanged. The flush + gap audit is the same cost as in full mode (one bd_list + per-bead status). Data capture is too valuable to skip for fast-path sessions.

**Future:** a `--strict-tracking` wrapup flag could promote the orphaned-closure WARNs to FAILs and block wrapup until each is resolved. Out of scope for v2.13.1; tracked as a kit follow-up.

### Task 4: Log Documentation Enhancements

**Run this BEFORE updating any `.claude/*.md` files AND before the retro (Task 9) — synthesis-mode enhancements become context for the retro questions.**

This task writes structured entries to `.claude/enhancements.yaml` (typed YAML, replaces legacy enhancements.md). Schema reference: [`.claude/docs/enhancements-schema.md`](../docs/enhancements-schema.md). Each entry has a `kind` (`doc_gap` here; retro/candidate kinds belong to Task 9), a `status` (defaults `open`), and a `target` doc the future Task 6 will resolve against.

**ID convention:** `id` is `YYYYMMDD-N` where N is the next available integer for today. Compute via `yq "[.entries[] | select(.id | test(\"^$(date +%Y%m%d)-\"))] | length + 1" .claude/enhancements.yaml`.

**Synthesis mode (run first):** for each stashed `enhancements[]` entry across all `beads[]` (worker emits `kind: doc_gap | workflow_friction | tooling_pain | standards_candidate`), append a YAML entry to `.claude/enhancements.yaml` mapping the worker's fields:
- `kind` ← worker's kind verbatim
- `summary` ← worker's `summary`
- `body` ← worker's `suggested_fix` plus provenance line (`bead_context` + dispatch_id)
- `source` ← `falcon-dispatch-<id>`
- `target` ← inferred from `body` (which `.claude/*.md` would fix it?) or null
- `status: open`, `firings: 1` (only meaningful for standards_candidate)

**Synthesis mode — absorb `unlisted_context_reads[]` (v7.2.0+):** for each stashed bead in `beads[]`, check the `unlisted_context_reads[]` field. Each entry is a `.claude/*.md` file the worker had to read mid-execution that wasn't in the bead's `## Required Context` section — direct evidence the bead was under-hydrated. Append one `kind: doc_gap` entry per `unlisted_context_reads[]` item:

- `kind: doc_gap`
- `summary` ← `"Bead {bead_id} Required Context omitted {path}"`
- `target` ← `"bd:{bead_id}"` (the originating bead, NOT the .claude/*.md file — the gap is in the bead spec, not the doc)
- `body` ← `"Worker had to Read {path} during execution; reason given: {reason}. Add to the bead's ## Required Context section if this pattern recurs for similar beads (per work-item-templates.md Required Context contract)."`
- `source` ← `"falcon-dispatch-<id>"`
- `status: open`

This closes the hydration-discipline learning loop: under-hydration → worker ad-hoc Reads → wrapup files structured doc_gaps → next-similar-bead's Required Context tightens. Empty `unlisted_context_reads[]` is the expected normal for well-hydrated beads.

Then add any direct-session doc-gaps:

- Did you need information that wasn't in `.claude/*.md` and had to discover it from source code or trial-and-error?
- Categories to check: data model, API routes, business logic, frontend components, schemas/types, process
- For each gap, append a `kind: doc_gap` entry with the target doc named. Be specific in `body:` — Task 6 in this wrapup (or a future one) will read the entry and apply the fix.

**Append using yq -i** (newest-first prepend):

```bash
TODAY=$(date +%Y%m%d)
NEXT_N=$(yq "[.entries[] | select(.id | test(\"^${TODAY}-\"))] | length + 1" .claude/enhancements.yaml)
yq -i ".entries = [{
  \"id\": \"${TODAY}-${NEXT_N}\",
  \"date\": \"$(date -u +%Y-%m-%d)\",
  \"kind\": \"doc_gap\",
  \"status\": \"open\",
  \"summary\": \"<one-line>\",
  \"source\": \"direct\",
  \"target\": \".claude/<file>.md\",
  \"body\": \"<2-3 sentences or multi-paragraph>\"
}] + .entries" .claude/enhancements.yaml
```

**Lint after each write:** `yq '.' .claude/enhancements.yaml > /dev/null` — fail-fast if the YAML is corrupt.

- **If no gaps discovered (and synthesis-mode `enhancements[]` empty):** mark completed with "No documentation gaps to log."

### Task 5: Update changelog.yaml

**First-time creation:** if `.claude/changelog.yaml` does not exist yet, bootstrap it. Write the header comments + `template_entry:` block + `entries: []` (the canonical bootstrap content lives in [`changelog-schema.md`](../docs/changelog-schema.md) — copy the schema block from there). Then proceed with the prepend below.

**Prepend** a new entry to the top of the `entries:` list in `.claude/changelog.yaml`. Use the `template_entry` as the format reference (full field semantics in [`changelog-schema.md`](../docs/changelog-schema.md)):

```yaml
- version: "0.X.Y"
  date: "YYYY-MM-DD"
  branch: "<current-branch-name>"
  focus: [feature, bugfix, refactor, infrastructure, documentation, stabilization]
  summary: "<one-line summary>"
  beads: [bead-id-1, bead-id-2]
  backend:
    - "added: description"
    - "fixed: description"
  frontend:
    - "changed: description"
  infra:
    - "added: description"
  docs:
    - "added: description"
```

**Synthesis mode:** seed the entry from the stash:
- `focus` ← union of all `beads[*].changelog_seed.focus` arrays (dedupe)
- `beads` ← every closed bead id from `beads[]` with `outcome: closed`
- `summary` ← join `beads[*].changelog_seed.one_line_summary` with "; " OR write a 1-line meta-summary if too long
- `backend` / `frontend` / `infra` / `docs` ← concat `area_changes.<area>` across all `beads[]` entries (dedupe; preserve order)
- Augment with anything done in this session directly (outside any falcon dispatch).

- Omit area keys that have no changes (don't write empty lists)
- Prefix each bullet with `added:`, `changed:`, or `fixed:`
- **Lint:** Run `yq '.' .claude/changelog.yaml > /dev/null` to validate YAML
- **Verify:** Run `yq '.entries[0].summary' .claude/changelog.yaml` to confirm
- **If no features/fixes completed:** mark completed with "No changelog entries needed"

### Task 6: Update Context Docs

Check if this session changed any source code paths and update the corresponding `.claude/*.md` file:

| Changed path | Update |
|-------------|--------|
| Models, migrations, schemas | `data-model.md` |
| API routes, new endpoints | `backend.md` |
| Dependencies (package.json, pyproject.toml, etc.) | `architecture.md` Technology Decisions |
| Directory structure | `architecture.md` Directory Structure |
| Pages, components, UI | `frontend.md` |
| Dev tools, scripts | `architecture.md` Developer Tools |

**Synthesis mode:** the stashed `beads[*].files_changed` arrays give an authoritative path list per dispatch. Union them and run the table lookup against the union — this is faster + more complete than re-deriving from `git diff main...HEAD`.

**Resolve open enhancements.** Query open `doc_gap` / `workflow_friction` / `tooling_pain` entries from `.claude/enhancements.yaml` whose `target` matches a doc that was touched this session, or whose body suggests a fix this session can apply now:

```bash
yq '[.entries[] | select(.status == "open" and (.kind == "doc_gap" or .kind == "workflow_friction" or .kind == "tooling_pain"))] | .[] | "\(.id) | \(.kind) | \(.target) | \(.summary)"' .claude/enhancements.yaml
```

For each entry you apply a fix for:
1. Edit the target doc with the fix from the entry's `body`.
2. Transition status:

   ```bash
   yq -i "(.entries[] | select(.id == \"${ID}\") | .status) = \"resolved\"" .claude/enhancements.yaml
   yq -i "(.entries[] | select(.id == \"${ID}\") | .resolution_note) = \"Applied to ${TARGET_DOC} in this wrapup\"" .claude/enhancements.yaml
   ```

3. Lint: `yq '.' .claude/enhancements.yaml > /dev/null`.

If you decide an entry isn't worth fixing (out of scope, superseded, no longer accurate), transition to `status: deferred` (keep visible, suppress §9 alert) or `status: retired` (drop from active counts) with a `resolution_note` explaining why.

- **If no changes AND no enhancements to resolve:** mark completed with "No context doc updates needed."

### Task 7: Git Commit & Push

- **NEVER commit directly to `main`.** All work MUST be on a feature branch.
  - If on `main`, create a branch first: `git checkout -b feature/work-YYYYMMDD-<short-description>`
- Run `git status` to check for uncommitted changes
- Stage and commit using Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Reference bead IDs in commit messages: `feat: add auth flow [BD-12]`
- Flush bd state to disk: `bd export -o .beads/issues.jsonl` (bd 1.0 removed `bd sync`; the export keeps the canonical jsonl in sync with Dolt after batch writes per `.claude/rules/workflow-execution.md`). Stage `.beads/issues.jsonl` alongside code.
- **Synthesis mode:** worker code commits are already pushed under the worker's own protocol. This wrapup commit covers only the wrapup-generated artifacts (changelog, handoff, enhancements, standards-history) plus any direct-session code changes that happened outside the dispatches.
- Run `git pull --rebase` to catch remote changes
- Run `git push -u origin <branch>`
- **Critical:** Work is not complete until push succeeds. If push fails, resolve and retry.
- Verify: `git status` must show "working tree clean"
- **Do NOT create a PR automatically.** Only create when explicitly asked. Per `falcon.md`: in falcon-multi-dispatch workflows, the steering session opens the PR after ALL workers have completed AND been validated — not at first wrapup.

### Task 8: Session Summary & Handoff

**First-time creation:** if `.claude/handoff.yaml` does not exist yet, bootstrap it. Write the header comments + `template_entry:` block + `entries: []` (the canonical bootstrap content lives in [`handoff-schema.md`](../docs/handoff-schema.md) — copy the schema block from there). Then proceed with the prepend below.

**Prepend** a new entry to the top of the `entries:` list in `.claude/handoff.yaml`. Use the `template_entry` as the format reference (full field semantics in [`handoff-schema.md`](../docs/handoff-schema.md)):

```yaml
- date: "YYYY-MM-DD HH:MM UTC"
  branch: "<current-branch-name>"
  focus: [feature, bugfix, refactor, infrastructure, documentation, stabilization]
  completed:
    - "item-id: what was accomplished"
  discovered:
    - "item-id: new work filed this session"
  in_progress:
    - "item-id: current state of partial work"
  blockers:
    - "item-id: what's stuck and why"
  next_steps:
    - "item-id: what to do next, in priority order"
  epic_progress: "epic-id XX% → YY%"
  commits: ["abc1234", "def5678"]
```

**Synthesis mode:** seed from the stash:
- `completed` ← `[f"{b.id}: {b.outcome_reason}" for b in beads[] if outcome == "closed"]`
- `discovered` ← `[f"{d.id}: {d.title}" for d in discovered_beads[]]`
- `in_progress` ← `[f"{b.id}: {b.outcome_reason}" for b in beads[] if outcome == "in_progress"]`
- `blockers` ← stashed `blockers_for_steering_session[]` (one per entry)
- `next_steps` ← stashed `recommended_next_steps[]` (priority-ordered union; dedupe)
- `epic_progress` ← last `delta` wins per epic across all stashed `epic_progress[]` entries
- `commits` ← union of `beads[*].commits[]` (dedupe; chronological)
- Augment with anything done in this session directly.

- Omit keys that are empty (don't write empty lists)
- **Lint:** Run `yq '.' .claude/handoff.yaml > /dev/null` to validate YAML
- **Verify:** Run `yq '.entries[0].date' .claude/handoff.yaml` to confirm
- Display the summary inline so the user sees it immediately
- End with: "Ready to resume. Next session: [specific task] (see issue <id>)"

**Session-shape hint (`--minimal` only):** when running under `--minimal`, evaluate the session against substantive-session markers and emit a one-line hint at the bottom of the handoff entry's `next_steps[]` list if any marker fires. The hint warns the user that `--minimal` may have under-captured signal:

Substantive markers (any one triggers the hint):
- Beads closed this session: ≥ 1
- Beads opened this session: ≥ 2
- New patterns / standards candidates surfaced inline during work
- Files touched: ≥ 5 (rough cut — get from `git diff --stat HEAD~N..HEAD` where N = commits this session)
- Commits this session: ≥ 3
- `.claude/*.md` files edited: ≥ 1

Hint format (single line appended to the handoff entry):

```
- "Session shape hint: --minimal invoked but session shows substantive markers ({list fired markers, e.g., 'closed 3 beads, touched 12 files'}). Consider follow-up /wrapup (no --minimal) next session to capture missed signal: changelog entry, enhancements scan, retro."
```

If NO markers fire, omit the hint — the user correctly identified a minimal session.

The hint is a soft warning, not a block. User keeps control; if they accidentally invoked `--minimal` on a substantive session, they see the hint in the handoff and can re-run.

### Task 8b: Append Standards Firings (synthesis mode only)

> **Gated:** include this task in the TaskList ONLY if the Pre-Check returned `SYNTHESIS-MODE`. In direct-work mode, omit entirely.

This task writes structured firing entries to `.claude/standards-history.yaml` (typed YAML, replaces legacy standards-history.md). Schema reference: [`.claude/docs/standards-history-schema.md`](../docs/standards-history-schema.md).

**For each stashed `standards_firings[]` entry across all `beads[]`:**

1. **Resolve `rule_id` (the stable slug).** The stashed firing carries a `rule` reference like `§3.10`. Look up the slug in `.claude/standards-history.yaml`:

   ```bash
   yq ".rules | to_entries[] | select(.value.section_ref == \"${SECTION_REF}\") | .key" .claude/standards-history.yaml
   ```

   If found, use that slug. If not found, the rule isn't yet recorded as promoted — file a `kind: workflow_friction` entry against the steering session in `.claude/enhancements.yaml` (Task 4 covers this) and skip the firing.

2. **Compute next firing ID** (`YYYYMMDD-N`):

   ```bash
   TODAY=$(date +%Y%m%d)
   NEXT_N=$(yq "[.firings[] | select(.id | test(\"^${TODAY}-\"))] | length + 1" .claude/standards-history.yaml)
   FIRING_ID="${TODAY}-${NEXT_N}"
   ```

3. **Prepend the firing entry** (newest-first):

   ```bash
   yq -i ".firings = [{
     \"id\": \"${FIRING_ID}\",
     \"date\": \"$(date -u +%Y-%m-%d)\",
     \"rule_id\": \"${SLUG}\",
     \"section_ref_at_firing\": \"${SECTION_REF}\",
     \"fired_correctly\": true,
     \"bead_id\": \"${BEAD_ID}\",
     \"dispatch_id\": \"${DISPATCH_ID}\",
     \"action_taken\": \"${ACTION_TAKEN}\",
     \"context\": \"${CONTEXT}\"
   }] + .firings" .claude/standards-history.yaml
   ```

   - `fired_correctly: false` for deviations / misapplications (signal of rule misunderstanding worth tracking)
   - `dispatch_id` is the falcon dispatch ID; null for direct-session firings
   - `context` is a one-paragraph narrative (block scalar `|` for multi-line)

4. **Lint after each write:** `yq '.' .claude/standards-history.yaml > /dev/null`.

**Promotion check moved to Task 9.** The "rule fired 3+ times → propose promotion" path now lives in the Self-Reflection Mode's Promotion Pipeline Review (Task 9), where it can survey the full candidate state at once across `enhancements.yaml` and `standards-history.yaml`.

- **If no firings (or direct-work mode):** mark completed with "No standards firings to log."

### Task 8c: Surface DAR Decisions (synthesis mode only)

> **Gated:** include this task in the TaskList ONLY if the Pre-Check returned `SYNTHESIS-MODE`. In direct-work mode, omit entirely.

For each stashed `decisions_for_human[]` entry:
- **High-stakes + `stopped pending arbitration`**: already surfaced by `/falcon` Step 3 at report-receipt time; verify the user actually arbitrated (no unresolved). If unresolved, BLOCK wrapup until resolved.
- **Low-stakes + `proceeded with recommendation`**: append a single rollup line to `.claude/handoff.yaml`'s top entry — "N autonomous decisions during dispatch X; see archived falcon report for detail." Optionally append the full DAR list to a project-specific decisions log if one exists.

- **If no DAR entries (or direct-work mode):** mark completed with "No DAR entries to surface"

### Task 9: Retro

Two modes, decided by whether the `/wrapup` invocation included the `--feedback` flag:

- **Default (no flag) — Self-Reflection Mode.** Run as a focused 3-prompt self-retrospective targeting the signals that historically promoted to durable rules. DO NOT pause for user input. The model reflects on the session and writes findings directly to `.claude/enhancements.md` (and `.claude/standards-history.md` when a candidate hits its promotion threshold). This is the high-leverage path — the retro habit that produced §3.6, §3.9, §3.10, §3.12 and the candidate-rule pipeline.
- **`--feedback` flag — Interactive Mode.** Run the full 6-question form below and wait for user responses between each question. Use this when the user wants to provide their own observations rather than reading the model's self-reflection.

---

#### Self-Reflection Mode (default)

Walk through these three prompts internally and write structured entries to `.claude/enhancements.yaml`. Be specific (cite bead IDs, file paths, line numbers) — generic retros don't promote. Schema reference: [`.claude/docs/enhancements-schema.md`](../docs/enhancements-schema.md).

**ID convention:** same as Task 4 — `id` is `YYYYMMDD-N`. Compute with `yq "[.entries[] | select(.id | test(\"^$(date +%Y%m%d)-\"))] | length + 1" .claude/enhancements.yaml`.

1. **What burned time this session?** — Identify the 2–3 highest-cost detours (debug loops, mis-scoped beads, surprise dependencies). For each: ~1 paragraph naming the cost shape + suggested mitigation. Append as `kind: retro` entries:

   ```bash
   yq -i ".entries = [{
     \"id\": \"${TODAY}-${NEXT_N}\",
     \"date\": \"$(date -u +%Y-%m-%d)\",
     \"kind\": \"retro\",
     \"status\": \"open\",
     \"summary\": \"<one-line cost shape>\",
     \"source\": \"direct\",
     \"target\": null,
     \"body\": \"<paragraph: cost shape + mitigation + cite bead IDs / file paths>\"
   }] + .entries" .claude/enhancements.yaml
   ```

2. **What should never happen again?** — Identify any pattern that, if it fires again, would cost real time. For each pattern, FIRST query existing entries to detect prior firings:

   ```bash
   # Search by summary keyword or pattern signature in body
   yq "[.entries[] | select(.kind == \"standards_candidate\" and (.summary + \" \" + .body | test(\"<pattern-keyword>\", \"i\")))]" .claude/enhancements.yaml
   ```

   Then:
   - **No existing match (first firing this session)** → append a new `kind: standards_candidate` entry with `firings: 1`, status `open`, a draft rule sentence in `body`, and the pattern signature in `summary` so future sessions can find it.
   - **Existing match found (2nd or 3rd firing)** → increment its `firings` count:

     ```bash
     yq -i "(.entries[] | select(.id == \"${EXISTING_ID}\") | .firings) += 1" .claude/enhancements.yaml
     ```

     If `firings >= 3` after increment, this is the promotion event. Execute the full promotion sequence:

     a. **Generate the slug.** Auto-derive from the candidate's `summary` (kebab-case, lowercase, ASCII): `SLUG=$(echo "$SUMMARY" | iconv -t ASCII//TRANSLIT | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g; s/^-\+\|-\+$//g')`. If the slug collides with an existing key in `standards-history.yaml`, append `-2`, `-3`, etc. Manual override is allowed — if the auto-slug is awkward, choose a better one before continuing.

     b. **Pick the section ref.** Inspect `rules/development-standards.md` for the next available section number (e.g., `§3.25` if §3.24 is the latest). Manual choice if numbering is fluid.

     c. **Append the rule definition to `rules/development-standards.md`.** New section header `## §X.Y <Title>` matching the slug + section_ref. Include CORRECT/WRONG pattern examples + rationale derived from the candidate's `body` field + cite the 3 firings by enhancements.yaml entry IDs.

     d. **Add the rule entry to `standards-history.yaml`:**

        ```bash
        yq -i ".rules.\"${SLUG}\" = {
          \"section_ref\": \"§X.Y\",
          \"title\": \"<Title>\",
          \"promoted_date\": \"$(date -u +%Y-%m-%d)\",
          \"promoted_from_bead\": \"${BEAD_THAT_TRIGGERED_PROMOTION}\",
          \"promoted_from_firings\": [\"<enh-id-1>\", \"<enh-id-2>\", \"<enh-id-3>\"],
          \"deprecation_status\": null
        }" .claude/standards-history.yaml
        ```

     e. **Transition the enhancements.yaml entry:**

        ```bash
        yq -i "(.entries[] | select(.id == \"${EXISTING_ID}\") | .status) = \"promoted\"" .claude/enhancements.yaml
        yq -i "(.entries[] | select(.id == \"${EXISTING_ID}\") | .resolution_note) = \"Promoted to ${SLUG} (§X.Y) in this wrapup\"" .claude/enhancements.yaml
        ```

     f. **DO NOT modify `rules/workflow*.md`** — those are kit-managed.

     g. **Lint:** `yq '.' .claude/standards-history.yaml > /dev/null && yq '.' .claude/enhancements.yaml > /dev/null`.

3. **(Synthesis mode only) Did any falcon dispatch produce unexpected DARs or scope expansions?** — If yes, append a `kind: workflow_friction` entry naming falcon as the target system and citing the dispatch ID:

   ```yaml
   kind: workflow_friction
   summary: "Falcon dispatch <id> produced unexpected DAR shape"
   source: "falcon-dispatch-<id>"
   target: ".claude/skills/falcon/PROTOCOL.md"
   body: |
     <Dispatch surprise shape + suggested pre-dispatch grep / intent-confirm gap to close>
   ```

**Lint after each write:** `yq '.' .claude/enhancements.yaml > /dev/null`.

Skip prompts that have nothing to say — `enhancements.yaml` is the durable signal, not a fill-out-the-form ritual. A zero-finding self-retro is acceptable and should be marked completed with "No retro-worthy signals this session."

---

**Promotion Pipeline Review (always run after prompts 1-3).** Survey the candidate pipeline and surface near-promotion + aged-out cohorts inline. Three yq queries against `enhancements.yaml`:

```bash
# Near-promotion: candidates one firing away from auto-promotion
yq '[.entries[] | select(.kind == "standards_candidate" and .status == "open" and .firings == 2)] | .[] | "\(.id) | \(.summary)"' .claude/enhancements.yaml

# Aged-out: firings stuck at 1 for >180 days (likely never promoting)
CUTOFF=$(date -d '180 days ago' +%Y-%m-%d)
yq "[.entries[] | select(.kind == \"standards_candidate\" and .status == \"open\" and .firings == 1 and .date < \"$CUTOFF\")] | .[] | \"\(.id) | \(.date) | \(.summary)\"" .claude/enhancements.yaml

# Deprecation candidates: promoted rules that haven't fired in 90 days
# (queries standards-history.yaml; surfaces rules potentially obsolete)
FIRE_CUTOFF=$(date -d '90 days ago' +%Y-%m-%d)
RECENT_FIRED=$(yq "[.firings[] | select(.date >= \"$FIRE_CUTOFF\")] | map(.rule_id) | unique" .claude/standards-history.yaml)
yq ".rules | to_entries[] | select(.value.deprecation_status == null and (.key as \$k | $RECENT_FIRED | index(\$k) | not)) | \"\(.key) | promoted \(.value.promoted_date) | \(.value.title)\"" .claude/standards-history.yaml
```

Render output as a 3-block summary:

- **Promoted this session:** [list slugs from prompt 2's promotion path, if any fired]
- **Near promotion (firings: 2):** [N candidates, list IDs + summaries]
- **Aged out (firings: 1, >180d):** [N candidates, action: batch-prompt to retire]
- **Deprecation candidates (no firings in 90d):** [N rules, action: surface for human review]

For aged-out candidates, ask ONCE (single batched question, not per-entry): *"N candidates have been sitting at firings:1 for >180 days. Retire them (mark status:retired)? (y / n / show-each)"*

- `y` → batch yq -i to transition all to `status: retired` with `resolution_note: "Aged out — single firing >180d without recurrence"`
- `n` → leave open; reappears next wrapup
- `show-each` → walk one-by-one with retire / defer / keep options

For deprecation candidates (rules in standards-history.yaml with no recent firings), DO NOT auto-mutate — just surface inline as advisory. Deprecation is a human decision (the rule may still be load-bearing even if no recent code triggered it).

---

#### Interactive Mode (`--feedback`)

Ask the user these questions and wait for responses between each. For each substantive answer, append a structured entry to `.claude/enhancements.yaml` per the kinds noted (use the yq pattern from Self-Reflection Mode above):

1. **What went well this session?** — Reinforce good patterns. (No file write — verbal acknowledgement only.)
2. **What burned time?** — Append `kind: retro`.
3. **What should never happen again?** — Append `kind: standards_candidate`. Check for existing matches first and increment `firings` if found (same logic as Self-Reflection prompt 2). If `firings >= 3`, propose promotion to `rules/development-standards.md`. Do NOT modify `rules/workflow*.md` — kit-managed.
4. **Were any beads underspecified when you started implementing?** — Append `kind: doc_gap` with `target: .claude/docs/work-item-templates.md` and a suggested improvement to the readiness checklist in `body`.
5. **Were any effort forecasts significantly off?** — Append `kind: tooling_pain` with the sizing-calibration note in `body` so it surfaces for review.
6. **(Synthesis mode) Did any falcon dispatch produce unexpected DARs or scope expansions?** — Append `kind: workflow_friction` with `target: .claude/skills/falcon/PROTOCOL.md`.

Lint after each write: `yq '.' .claude/enhancements.yaml > /dev/null`.

### Task 9b: Verification Sweep

Single consolidated task covering low-frequency checks. Run all sections inline, then mark this task completed with a one-line bullet summary like `"Sweep: plans=none, beads=3 linted clean, startup=none"`. If any check surfaces a real action, spawn a separate follow-up TaskCreate for it — do NOT inline the action here; this task is the sweep, not the fix.

#### a. Archive plan files

If a plan was created during this session, save it to `.archive/plans/<feature-name>.md`:
- Strip `feature/` or `fix/` prefix from branch name, strip work-ID prefix (`work-YYYYMMDD-` or similar), use remaining description as filename. Example: `feature/work-20260321-auth-flow` → `.archive/plans/auth-flow.md`.
- Ensure all work items from the plan exist as beads; add plan context as `bd comments add <id> "Plan context: <summary>"`.
- Plans persist after branch merge for historical reference. If no plan, skip.

#### b. Validate beads touched this session

Run the tier-contract check against beads touched during this session:

```bash
python3 .claude/scripts/check-bead-contract.py --session
```

This validates every bead updated since the session started (derives the time bound from `.claude/tmp/<session_id>.json`'s `started` field) against the tier contracts in `.claude/docs/work-item-templates.md`:

- `triage:backlog` → stub-template completeness
- `triage:triaged` → mid-refinement labels + Acceptance Criteria
- `triage:ready` → full template + per-phase Effort Forecast + Required Context (for `cynefin:complicated`/`complex`) + no TBDs
- No `triage:*` label → defect (must be triaged)

Exit codes: `0` clean / `1` HARD violation (block wrapup; refine then re-run) / `2` SOFT violation (warn but continue).

If the script reports violations, surface them inline and refine the offending beads before continuing Task 7 (commit + push). If the script is missing (project hasn't vendored it), fall back to manual checks:

- [ ] `bd lint <id>` — no warnings (project-level fallback)
- [ ] Effort Forecast per-phase per [`work-item-templates.md`](../docs/work-item-templates.md)
- [ ] Required Context for `cynefin:complicated`/`complex`
- [ ] Priority assigned, epic parent assigned (or justified standalone), dependencies set

Then in either path:

- **Assign orphaned beads** to existing epics: `bd dep add <bead-id> <epic-id> -t parent-child`. If no epic fits, evaluate whether a new epic is warranted (3+ related orphans) or leave standalone.
- Run `bd epic status` to verify epic health after assignments.
- If no beads were touched this session, skip.

Full integration paths (pre-push hook, CI step, etc.) documented in [`lint-integration.md`](../docs/lint-integration.md).

#### c. Session-startup improvement candidates

Evaluate if anything learned during this session should improve `/leroy`:
- New context files that should be loaded at startup
- Additional checks that would have been helpful
- Environment variables, ports, or dependencies that surfaced as friction

Cross-reference the Task 9 retro's `what burned time?` output — startup-improvement candidates often surface there first. If anything is identified, append to `.claude/enhancements.md` under a `### Startup-improvement candidates` subhead. If none, skip.

### Task 10: Update Environment Health Checks

Forward-looking maintenance of `/leroy`'s startup signal. Even when this check feels like a no-op (most sessions), the architecture.md **Environment Health Checks** table is what `/leroy` reads at every future session start — if it drifts from reality, every future startup gets bad signals.

If this session added, removed, or changed infrastructure (new service, new port, new dependency, docker-compose changes, new `.env` variables):

1. Read the **Environment Health Checks** table in `.claude/architecture.md`
2. Update it to reflect the current state:
   - Add rows for new services (with check command + expected output)
   - Remove rows for decommissioned services
   - Update check commands if ports or endpoints changed
3. Update the "Local Development" commands if startup steps changed

- **If no infrastructure changes:** mark completed with "No env health-check updates needed (table still current)."
