---
description: Full session wrapup — verify, commit, update work items, handoff with progress, retro
tier: scale
version: 2.4.0
created: 2026-03-21
changelog:
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

**IMPORTANT: You MUST use TaskCreate to create a task for EVERY checklist item below BEFORE starting any work. Then use TaskUpdate to mark each task `in_progress` when you start it and `completed` when done. Do NOT skip any task — if a step is not applicable, mark it completed with a note explaining why. The user can see task progress and will hold you accountable for completing every item.**

Create all tasks first, then work through them in order:

---

### Task 0: Check for Falcon Synthesis Mode

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

### Task 1: Archive Plan Files

If a plan was created during this session, ensure it's saved to `.archive/plans/`:

- Check if a plan file exists for the current work
- Save/move to `.archive/plans/<feature-name>.md` using the naming convention:
  - Strip `feature/` or `fix/` prefix from branch name
  - Strip work ID prefix (`work-YYYYMMDD-` or similar)
  - Use remaining description as filename
  - Example: `feature/work-20260321-auth-flow` → `.archive/plans/auth-flow.md`
- Ensure all work items from the plan exist as beads
- Add plan context as comments on relevant beads: `bd comments add <id> "Plan context: <summary>"`
- Plans persist after branch merge for historical reference
- **If no plans were created:** mark completed with "No plans to archive"

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

### Task 3b: Validate Beads

For each bead created or touched this session (including Falcon-closed beads), run the readiness checklist:
- [ ] `bd lint <id>` — no warnings (acceptance criteria, required sections)
- [ ] **Effort Forecast: per-phase breakdown** present (plan/implement/test minimum + Total + Confidence) per `.claude/docs/work-item-templates.md` Effort Forecast contract — single-number forecasts must be revised before the item can reach `triage:ready`
- [ ] Priority assigned
- [ ] Epic parent assigned (or justified as standalone)
- [ ] Dependencies set if sequencing matters

Then:
- **Assign orphaned beads** to existing epics using `bd dep add <bead-id> <epic-id> -t parent-child`
- If no existing epic fits, evaluate whether a new epic is warranted (3+ related orphans) or leave as standalone
- Run `bd epic status` to verify epic health after assignments
- **If no beads created or touched:** mark completed with "No beads to validate"


### Task 4: Log Documentation Enhancements

**Run this BEFORE updating any `.claude/*.md` files AND before the retro (Task 9) — synthesis-mode enhancements become context for the retro questions.**

Review the session and log documentation gaps discovered to `.claude/enhancements.md`:

**Synthesis mode (run first):** for each stashed `enhancements[]` entry across all `beads[]` (kinds: `doc_gap | workflow_friction | tooling_pain | standards_candidate`), append a new entry to `.claude/enhancements.md` using its `summary` + `suggested_fix` + provenance line (`bead_context` from the stash + dispatch_id). Then add any direct-session gaps below.

- Did you need information that wasn't in `.claude/*.md` and had to discover it from source code or trial-and-error?
- Log new gaps using the template in `enhancements.md`: what was needed, where the gap is, suggested fix
- Categories to check: data model, API routes, business logic, frontend components, schemas/types, process
- **If no gaps discovered (and synthesis-mode `enhancements[]` empty):** mark completed with "No documentation gaps to log"

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

Also review open (non-`[RESOLVED]`) entries in `.claude/enhancements.md` and apply fixes to the target docs. After applying, mark entries `[RESOLVED]`.

- **If no changes:** mark completed with "No context doc updates needed"

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

### Task 8b: Append Standards Firings (synthesis mode only)

For each stashed `standards_firings[]` entry across all `beads[]`, append a line to `.claude/standards-history.md` capturing:

- The `rule` reference (e.g., `§3.10`, rule name)
- The `context` (what triggered)
- The `action_taken` (followed, deviation rationale, file-contract violation flag, etc.)
- Provenance: bead ID + dispatch ID from the stash

If a rule fired 3+ times across recent history, this is the promotion threshold for `development-standards.md` Candidate → Confirmed. Surface that recommendation inline at wrapup.

- **If no firings (or direct-work mode):** mark completed with "No standards firings to log"

### Task 8c: Surface DAR Decisions (synthesis mode only)

For each stashed `decisions_for_human[]` entry:
- **High-stakes + `stopped pending arbitration`**: already surfaced by `/falcon` Step 3 at report-receipt time; verify the user actually arbitrated (no unresolved). If unresolved, BLOCK wrapup until resolved.
- **Low-stakes + `proceeded with recommendation`**: append a single rollup line to `.claude/handoff.yaml`'s top entry — "N autonomous decisions during dispatch X; see archived falcon report for detail." Optionally append the full DAR list to a project-specific decisions log if one exists.

- **If no DAR entries (or direct-work mode):** mark completed with "No DAR entries to surface"

### Task 9: Retro (recommended)

Ask the user these questions and wait for responses:

1. **What went well this session?** — Reinforce good patterns.
2. **What burned time?** — Capture as a follow-up work item or enhancement in `.claude/enhancements.md`.
3. **What should never happen again?** — If actionable, add as a CORRECT/WRONG pattern in `rules/development-standards.md`. Do NOT modify `rules/workflow.md` — that file is kit-managed and will be overwritten by updates.
4. **Were any beads underspecified when you started implementing?** — Note the gap in `.claude/enhancements.md` with a suggested improvement to the readiness checklist.
5. **Were any effort forecasts significantly off?** — Note the variance in `.claude/enhancements.md` so sizing calibration can be reviewed.
6. **(Synthesis mode) Did any falcon dispatch produce unexpected DARs or scope expansions?** — Capture the pattern in `.claude/enhancements.md` so falcon's pre-dispatch grep audit + intent-confirm pre-flight can absorb the gap.

### Task 10: Update Environment Health Checks

If this session added, removed, or changed infrastructure (new service, new port, new dependency, docker-compose changes, new .env variables):

1. Read the **Environment Health Checks** table in `.claude/architecture.md`
2. Update it to reflect the current state:
   - Add rows for new services (with check command + expected output)
   - Remove rows for decommissioned services
   - Update check commands if ports or endpoints changed
3. Update the "Local Development" commands if startup steps changed

This ensures `/leroy` checks the right services in future sessions.

- **If no infrastructure changes:** mark completed with "No env check updates needed"

### Task 11: Improve Session Startup (optional)

Evaluate if anything learned during this session should improve `/leroy`:
- New context files that should be loaded at startup
- Additional checks that would have been helpful
- Environment variables or dependencies that caused issues

If improvements are identified, note them in `.claude/enhancements.md` for review.
- **If no improvements identified:** mark completed with "No startup updates needed"
