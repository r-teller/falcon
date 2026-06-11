---
parent: SKILL.md
version: 7.0.0
---

# Falcon — Dispatch Protocol

> This file covers the full lifecycle steps, amendments workflow, paste-fallback mode, and sequential dispatch override.
> For CLI surface (commands + flags + examples): see [`COMMANDS.md`](./COMMANDS.md).
> For schemas and templates: see [`REFERENCE.md`](./REFERENCE.md).

---

## Step 1 — Resolve Bead Set (this session)

Run `bd show <id>` for each ID in spec. For each:
- Confirm it exists
- Capture: ID, title, type, size, cynefin, triage state, dependencies, parent epic, current status, full description body

If any bead is not `triage:ready`, flag to user and ask whether to (a) drop it, (b) refine here first, (c) include with a warning to the remote, or (d) hand refinement to the remote — remote brings the bead to `triage:ready` per project work-item-templates before claiming, then proceeds with normal lifecycle. Option (d) trades steering-session context cost for remote turns; pick it when the bead's gaps are mechanical (missing file paths, AC formalization, dependency formalization) rather than design-level.

If the project's conventions require sanitizing or filtering bead content before inlining into a remote-session prompt (e.g., redacting dual-use detail), apply that here using whatever helper the project provides. Falcon itself does not know about project-specific content classes — the steering session is responsible for project-appropriate handling.

**File scope derivation:** for each bead, derive a `file_scope` object containing:
- `directories[]` — directory roots the bead's "Changes Needed" implies (e.g., `score-tracker/workbench/`, `score-tracker/tests/persistence/`)
- `files[]` — specific files listed in "Changes Needed" outside any declared directory

Heuristic for derivation: parse the bead's "Changes Needed" table; group entries by common path prefix; promote prefixes touched by 3+ entries to a `directories[]` entry; keep singleton paths as `files[]` entries. Show the derived scope to the user before lock-check; user can correct (add/remove directories, narrow scope) before dispatch.

**Self-conflict check:** if the same dispatch claims multiple beads whose file_scopes overlap (e.g., bead A and bead B both touch `score-tracker/workbench/routes.py`), the dispatch is self-conflicting. Default behavior is to reject at the bead-resolution step BEFORE writing to the lock registry. Tell the user: `"Beads A and B cannot share a single dispatch — both claim <path>. Split into separate dispatches OR consolidate the touch points first OR re-invoke with --sequential to opt one worker into handling both in order."`

**Self-conflict override with `--sequential` (v6.4.0):** when the user invokes `/falcon work beads A,B --sequential`, the HARD-reject is replaced by a single-worker sequential-handling resolution:

1. **Derive union file_scope.** Compute the union of all beads' file_scopes (directories + files). The dispatch's `file_scope` is the union; the file-contract audit at Step 3 validates against the union, not per-bead.

2. **Resolve execution order.** Three signals, applied in priority order:
   - **bd `blocked_by` ordering wins** — if A is in B's `blocked_by` chain (via `bd dep tree`), the order is A→B regardless of CLI list-order. If both are independent OR mutually-blocked, fall to next signal.
   - **CLI list-order is the default** — `/falcon work beads A,B --sequential` → A first, then B. Least-surprise.
   - **Bead-body "Patterns to Reuse" sanity scan** — if bead B's "Patterns to Reuse" section text references bead A's deliverables (helper names, file paths bead A creates, "Phase N from <prior-bead>" prose), and the declared order is B,A, flag as a likely mis-ordering. Steering MUST confirm or reorder before the dispatch file is written.

3. **Surface resolved order to steering for ack.** Before writing the dispatch file, print: `"Sequential dispatch: bead order [A, B]. Resolution: <CLI list-order | bd-dep-override | Patterns-scan-flagged>. File_scope union: <list>. Proceed?"`. Steering acks or reorders. Once confirmed, proceed to Step 2 dispatch-file write.

4. **Self-conflict ON FILE-SCOPE-WITHIN-SEQUENTIAL is permitted.** The union-file_scope is locked at dispatch time against other concurrent dispatches as one set (a different dispatch claiming any file in the union is HARD-rejected per the normal lock-registry check). Within the sequential dispatch, the worker iterates the beads in order; per-bead file-touch is unconstrained within the union.

**When `--sequential` is NOT appropriate** (steering should reject + recommend separate dispatches instead):
- Total worker context budget would exceed ~120 turns (split into separate dispatches for fresh context per worker)
- Failure isolation between beads is more valuable than orchestration savings (e.g., sweep operations across N independent beads where partial-batch closure is desirable; if bead 3 of 5 dies, you'd rather have 1+2 cleanly closed than have a half-state for the whole batch — that's a normal multi-bead dispatch, NOT a `--sequential` case)
- The beads are truly independent (no logical sequencing benefit) — use a normal multi-bead dispatch with separate file_scopes

**Bead body sanity check (for beads that reference multi-section design spikes):** if the bead body cites design-spike question numbers (e.g., Q1, Q5, Q12 from a parent spike), verify the Q references harmonize. Spike bodies can accumulate addendum-style updates (e.g., QM review additions) that supersede earlier Q&A; the bead body inheriting both creates internal contradictions the worker has to resolve via DAR. Re-read the spike body before dispatch if the bead is more than ~7 days old or has been touched since the spike was amended. If contradictions exist, either: (a) update the bead body to harmonize before dispatch, OR (b) flag in steering-session notes which Q supersedes which so the worker doesn't surprise-DAR mid-flight.

---

## Step 1b — Pre-Dispatch Grep Audit (for migration/rename beads)

For beads that retire identifiers (enum values, function names, field names) or rename across the codebase, run a grep audit BEFORE declaring file_scope. This catches files touched by the rename that the bead's Changes Needed table missed at authoring time.

Heuristic:
1. Identify the "touched identifiers" from the bead's Changes Needed + ACs (e.g., `bonus-fake`, `entry_type`, `_entry_type_from_result`, retired enum literals)
2. For each identifier, run `grep -rln <identifier> <project-root>` (excluding `node_modules`, `__pycache__`, `.git`, etc.)
3. Cross-reference grep results against:
   - The bead's Changes Needed table (files explicitly listed)
   - Directories already in the derived file_scope (files implicitly covered)
4. Files in grep results NOT covered by either → surface to user: `"<file> contains <identifier> but isn't in the bead's declared scope. Should it be added to file_scope, OR is the touch intentional and the bead spec just incomplete?"`
5. User confirms scope expansion → update derived `file_scope` BEFORE Step 1c (lock-check) and Step 2 (dispatch write)

Skip this step for beads that:
- Author NEW files (no existing touch points to enumerate)
- Touch a single file explicitly named in Changes Needed
- Have a tightly-scoped, single-purpose change (e.g., a one-line bugfix)

Why: workers can catch missed files via intent-confirm scope-question (file_contract design intent — this is the safety net that DID catch a real miss in production). Catching at dispatch time avoids the intent-confirm round-trip + lets the user pre-expand scope before the worker even reads the bead. Both safety nets are valid; using both is belt-and-suspenders.

---

## Step 1c — Lock Registry Check

Before writing the dispatch file, check the lock registry:

1. Glob all session JSON files: `.claude/tmp/*.json`
2. For each session file, parse `falcon_dispatches[]` array (may not exist on older session files — treat absence as empty)
3. Filter to entries with `status: "in_progress"`
4. Aggregate active scope: union of all `file_scope.directories[]` and `file_scope.files[]` from in-progress dispatches
5. Compare new dispatch's derived file_scope against aggregated active scope:
   - `directory ∩ directory`: overlap if same dir, ancestor, or descendant (e.g., `score-tracker/` overlaps `score-tracker/workbench/`)
   - `file ∈ directory`: overlap if file resides under any active directory
   - `directory ⊃ file`: overlap if any active file resides under new directory
   - `file == file`: overlap if exact path match
6. On overlap → **HARD reject** the dispatch with informative error:

   ```
   Dispatch <new-id> cannot be created: <path> is locked by active dispatch
   <existing-id> (bead <bead-id>, started <ts>, session <session-id>).
   Either:
   - Wait for that dispatch to complete (the steering session auto-releases on validation success)
   - Run /falcon release <existing-id> if the dispatch was abandoned (worker died without returning a report)
   - Run /falcon list-locks to see all active dispatches
   ```

7. On no overlap → register new dispatch in the CURRENT session's JSON file by appending to `falcon_dispatches[]` (create the field if it doesn't exist) — see schema in [`REFERENCE.md`](./REFERENCE.md#session-json-schema-extension).

8. Proceed to Step 2 (Emit Prompt).

**Note on glob patterns:** `file_scope` supports only directories and explicit files. Glob patterns (e.g., `*_thin.yml`) are NOT supported. Two beads that touch different files within the same directory cannot run in parallel — they must be serialized OR consolidated into one dispatch with both bead IDs.

---

## Step 2 — Write Dispatch File + Emit Worker Prompt

1. Write a per-dispatch YAML file at `.claude/tmp/falcon-dispatch-<6hex>.yaml` containing:
   - `dispatch_id`, `bead_ids[]`, `branch`, `repo_path`, `file_scope` (from Step 1, optionally expanded in Step 1b)
   - `session_status: active` — set by steering; worker checks on resume prompts; transitions: `active → amendments_pending → complete` (steering sets complete via `/falcon release`)
   - `required_context[]` (v7.2.0+): union of `.claude/*.md` file paths from each bead's `## Required Context` section. Populate via:

     ```bash
     for id in "${BEAD_IDS[@]}"; do
       bd show "$id" | awk '/^## Required Context/,/^## /' | grep -oE '\.claude/[a-zA-Z_/-]+\.md(\s+§\s+"[^"]*")?'
     done | awk '!seen[$0]++'   # dedupe, preserve first-seen order
     ```

     Empty list is valid for all-`cynefin:clear` dispatches. Under-hydrated `cynefin:complicated` / `cynefin:complex` beads should NOT reach this stage — the readiness checklist in `.claude/docs/work-item-templates.md` hard-binds against it. If a worker reports `unlisted_context_reads[]` entries in its return contract, /wrapup Task 4 absorbs each as a `kind: doc_gap` enhancement against the originating bead.
   - `init_prompt` section: the full lifecycle + project-rules + return-contract content per the "init_prompt Content Template" in [`REFERENCE.md`](./REFERENCE.md) (this is the worker's binding spec — read it before any state change)
   - Empty placeholder sections: `implementation_intent: null`, `out_of_spec_approval_requests: []`, `implementation_results: null`, `implementation_results_hash: null`, `amendments: []`
2. Print a SHORT prompt for the user to paste into the worker session (per the "Dispatch Prompt Template" in [`REFERENCE.md`](./REFERENCE.md)).
3. Tell the user: dispatch ID, lock summary ("locked: <directories/files>"), expected worker pause point (intent-confirm), how to resume worker after acks.

The worker's first action is to read the dispatch file — that gives them the full init_prompt + all binding-spec context.

**Why pointer-style bead set as default in init_prompt:** for multi-bead workflows, inlining full bodies bloats the init_prompt linearly with bead count. Pointer-style keeps it small + makes the bd state the single source of truth (no inline-vs-bd drift). Steering can opt in to inline (`--inline-beads`) for single beads where the prompt benefits from being self-contained.

**Why intent-confirm as default:** the biggest failure mode of autonomous workers is misreading what the bead is asking for. A single-paragraph intent statement written to the dispatch file before any state change catches this cheaply (~1 paragraph from worker, ~1 word ack from steering). Skip-intent (`--skip-intent`) is the opt-out for steering-confident dispatches.

Do not enumerate project-specific rules in the init_prompt itself. The worker will read them from `.claude/rules/*.md` and `.claude/standards-history.md` in its own context — those files are the source of truth and rot less than copy-pasted rule lists.

**Steering-session-notes hypothesis-framing convention (v6.13.0+):** when the steering notes call out a known DAR or investigation that the worker may need to handle, frame the hypothesis space as **"investigate these N candidates"** rather than **"likely X."** Workers tend to test the "likely" path first and spend turns disproving it before broadening; presenting candidates as equal-weight options invites the worker to gather evidence and select rather than to confirm. Example:

- **WRONG framing:** "The 2 baseline FAIL→ERROR flips are likely caused by the recent rename migration's recursive scalar substitution rewriting a non-ID token in a config URL/path. Investigate + file follow-up bug bead if confirmed."
- **CORRECT framing:** "The 2 baseline FAIL→ERROR flips need root-cause investigation. Candidate hypotheses (test each empirically, don't assume one is correct): (1) the rename migration's recursive substitution rewrote a non-ID token in a config field; (2) stateful container reuse between Phase 1+2 corrupted the baseline container's data (e.g., user already-registered from Phase 1 setup); (3) a behavior-equivalent fixture-data drift unrelated to either migration or container state. Inspect via `git show <migration-commit>` for hypothesis 1, `curl` against the live baseline container for hypothesis 2, fixture-data diff for hypothesis 3."

Provenance: a worker session tested the "likely" path first, spent ~5 turns disproving via `git show` inspection (the suspected cause didn't actually touch the relevant fields), then broadened the search and found the second hypothesis (stateful container reuse) was the real root cause. Equal-weight candidate framing in the steering notes would have saved the disproof turns.

### Mode selection + detection (v7.0.0)

As of v7.0.0, `/falcon work beads <spec>` (no mode flag) defaults to `--bg` mode (worker spawned as a Claude Code background session, observable via `claude agents`). The renamed `--via-paste` mode preserves the prior paste-into-tab default; `--paste` continues to serve the cross-machine fallback. Mode selection runs eagerly in Step 2 BEFORE the dispatch file is written, so detection failures don't half-create state.

**Detection sequence:**

1. **Mode override check.** If user explicitly passed `--via-paste`, `--paste`, `--bg-isolated`, or `--bg-no-isolation`, capture the explicit mode and skip the auto-detection branches. Mutually-exclusive flag combos (`--bg + --paste`, `--via-paste + --paste`, `--bg-isolated + --bg-no-isolation`) fail with an informative error before any other action.
2. **Version gate (cheapest, fails fast).** Run `claude --version`; parse semver. Require >= 2.1.139.
   - On failure: emit one-line note `--bg requires Claude Code >= 2.1.139 (detected: <version>). Auto-downgrading to --via-paste. Upgrade Claude Code OR pass --via-paste explicitly to suppress this message.` Set effective mode to `--via-paste`.
   - **Detection authority — do NOT consult `claude --help`.** As of Claude Code's current `--help` output, `--bg` is NOT listed among the printed flags despite being supported on 2.1.139+. Implementers (and AI assistants doing falcon-related work) that probe `claude --help | grep -- --bg` will get an empty result and incorrectly conclude `--bg` is unsupported. The version gate above is the canonical check. If you (or another agent) reach for `--help` as a fallback verification, stop — trust `claude --version >= 2.1.139` and let the dispatch itself surface any real incompatibility downstream.
3. **`disableAgentView` settings check (v7.0.1, fdev-lbq.26 — four-file cascade).** Walk these four candidate settings files in this precedence order, taking the first non-null value:
   - `<repo>/.claude/settings.local.json` (project-level machine-local; gitignored)
   - `<repo>/.claude/settings.json` (project-level committed)
   - `~/.claude/settings.local.json` (user-level machine-local)
   - `~/.claude/settings.json` (user-level committed)

   This matches Claude Code's own settings precedence (see https://code.claude.com/docs/en/settings). Operators encoding machine-local overrides in `.local.json` (the conventional location for per-machine config that should NOT be committed) get those honored.
   - If `disableAgentView: true` in any of the four: emit `agent-view disabled by <project-local|project|user-local|user> settings (<file-path>). Auto-downgrading to --via-paste.` Set effective mode to `--via-paste`.
4. **Success path.** Emit one-line confirmation `Dispatch mode: --bg (agent-view v<version> detected; isolated: <yes|no>)` so the user sees the default mode + the version + worktree-isolation choice that drove the dispatch shape.
5. Set `worker_dispatch_mode: <"bg" | "via-paste" | "paste">` on the dispatch file at Step 2 write-time.

**Recording the choice:** the dispatch file's `worker_dispatch_mode` field is steering's source of truth for observation/coordination expectations. Autopilot crons consult this field to decide whether to use the `--bg`-aware behavior (skip worker-cron paste-block emission; auto-ack-resume guard suffices) or the legacy `--via-paste` path (emit paste-blocks as before).

**Auto-downgrade messaging cadence:** if the same auto-downgrade fires on every dispatch (e.g., Claude Code stays below 2.1.139), the user may want to suppress the note. The escape hatch is passing `--via-paste` explicitly — the auto-downgrade message is meant to surface ONLY when the user expected `--bg` but got `--via-paste`. Steering does NOT remember prior downgrades across dispatches (each dispatch evaluates fresh).

### --bg dispatch mode (v7.0.0)

When the effective mode is `--bg` (either default or explicit), after Step 1c (lock-registry check) and the Mode selection + detection above, steering invokes `claude --bg` via the Bash tool with a SHORT bootstrap prompt pointing at the dispatch file. The supervisor spawns a detached Claude Code background session; the shell call returns the short session ID; steering captures it and writes `worker_bg_session_id` to the dispatch file. No paste-block emission; no DISPATCH PROMPT label.

**Wiring:**

1. Steering computes the bootstrap from the literal template in [`REFERENCE.md`](./REFERENCE.md#bootstrap-prompt-template-v700) `### Bootstrap Prompt Template (v7.0.0)`, substituting `dispatch_id` + `repo_path`. Bootstrap MUST include the literal `dispatch_id`, the absolute `repo_path`, and an instruction to VERIFY the loaded dispatch file's `dispatch_id` matches once read (mitigates the residual concern that steering code logic could pass a wrong ID — see "Architectural shifts" in the v7.0.0 changelog).
2. Steering invokes (via Bash):
   ```
   claude --bg --name "<prefix>-falcon-<dispatch-id>" "<bootstrap>"
   ```
   **Session-name prefix (v7.0.1, fdev-lbq.17):** `<prefix>` is the bd project prefix detected via `bd config get database.prefix` (or equivalent inspection of `.beads/`). Falls back to bare `falcon-<dispatch-id>` if no bd workspace is detected (operator using falcon outside a bd-managed project). Rationale: when multiple projects operate concurrently, `claude agents` rows look like `fdev-falcon-a3f8e9`, `myapp-falcon-b27c41` — project sorts first, so all dispatches within a project cluster together visually. Complements `claude agents --cwd <path>` (v2.1.141+) which provides per-directory filtering at the CLI level.

   If `--bg-isolated` is set: append `--worktree` (or whichever Claude Code flag triggers isolation; flag name defers to Claude Code's CLI). If `--bg-no-isolation`: append the Claude-Code-side opt-out flag. If neither: defer to the project's `worktree.bgIsolation` setting; if no setting, defer to Claude Code's default.
3. Capture the returned session ID. Write to `worker_bg_session_id` on the dispatch file (atomic; preserve other fields).
4. Emit the steering-session output block:

   ```
   Dispatch mode: --bg (agent-view v2.1.139+ detected; isolated: <yes|no>)
   Dispatched as session <short-id> (worker_bg_session_id: <id>).

   Monitor:        claude agents (look for row 'falcon-<dispatch-id>')
   Peek INTENT:    in agent view, Space on the row when state flips to 'Needs input'
   Detail:         claude attach <short-id>
   Logs:           claude logs <short-id>

   Steering-side crons (--watch / --auto-ack / --auto-amend / --release-on-merge)
   operate as before via the dispatch file. /falcon list-pending and
   /falcon retro --branch are unchanged.
   ```

   Steering does NOT auto-open `claude agents` (could steal terminal focus); user opens it themselves in any terminal.

**Worktree isolation handling — the `.claude/tmp/` shared-path concern:** when the worker runs in an isolated worktree (under `.claude/worktrees/<id>/`), the worktree branch does NOT contain `.claude/tmp/` (it's an ephemeral directory in the main checkout, not committed). The worker MUST resolve dispatch-file paths via the dispatch file's `repo_path` field (absolute path to the main checkout), NOT via a relative `.claude/tmp/` reference. The bootstrap-prompt template (REFERENCE.md `### Bootstrap Prompt Template (v7.0.0)`) enforces this by including `repo_path` literally in its content. See Worker Lifecycle Step 1 (branch verify) below for the worker-side handling.

**Amendment-propagation latency note:** in `--via-paste` mode, the worker-cron fires every 3 min to check for amendments. In `--bg` mode without a worker-cron, the worker only picks up amendments when it actively reads the dispatch file (next active turn — typically triggered by a user peek/reply, an autopilot cron's STATUS UPDATE, or the worker's own self-poll if it's mid-execution). This is NOT a regression from current UX (the `--via-paste` user had to wait for the worker tab to poll), but the cadence is event-driven rather than predictable. For long-running autopilot dispatches with no other activity, consider pinning the agent-view row (`Ctrl+T`) to keep the worker process alive past the ~1hr supervisor-stop window.

**Supervisor-stopped worker note (corrected v7.0.1 per upstream agent-view docs at https://code.claude.com/docs/en/agent-view):** the Claude Code supervisor auto-stops a background session ONLY after it FINISHES (session_status: complete or similar terminal state) and sits unattached for ~1 hour. Sessions that are working, waiting on input, or have a terminal attached are NOT auto-stopped. Sessions pinned with `Ctrl+T` in agent view are ALSO exempt from auto-stop.

A supervisor-stopped session does NOT auto-revive at a new pid. Restart happens on **user interaction** (attach / peek / reply) — Claude restarts the session from where it left off; observably this looks like a fresh pid taking over the same session ID, but the trigger is the user's interaction, not a supervisor-side revival.

This matters for falcon's auto-ack auto-resume guard: if the worker is supervisor-stopped before the cron writes `intent_acknowledged_utc`, the worker doesn't pick up the ack until user interaction restarts the session. Mitigation: pin long-running autopilot dispatches in agent view (`Ctrl+T` on the row) so the worker process stays alive even when sitting idle past the ~1hr boundary.

**Worker termination primitives (v7.0.1, fdev-lbq.8):** three distinct CLI primitives have different effects on a `--bg` worker; operators should choose deliberately:

| Goal | Right command | Effect |
|------|---------------|--------|
| Pause briefly; resume on next user interaction | `claude stop <id>` (alias `claude kill`) | Process stops; state preserved on disk; restart on attach/peek/reply. NOT a terminal kill — agent-viewer row stays. |
| Remove from agent-viewer entirely (terminal kill from operator POV) | `claude rm <id>` | Agent-viewer row disappears; transcript remains on disk via `claude --resume`; Claude-created worktree removed if no uncommitted changes (worktree path printed if uncommitted changes preserved). |
| Replace worker forensically (preserve dispatch, new worker session) | `/falcon respawn-fresh <dispatch-id>` | Spawns new `<prefix>-falcon-<id>-r<N>` row; prior session captured in `worker_bg_prior_sessions[]`. Use after AUP trips, environmental issues, etc., where the dispatch should continue with a fresh worker. |

The retro observation that "supervisor revived a stopped worker at a new pid" was a misreading — what was actually happening was user interaction (peek or attach) triggering the standard restart-on-interaction path. There is no autonomous supervisor-side revival.

See https://code.claude.com/docs/en/agent-view "How background sessions are hosted" for the upstream contract.

**`--worker-cron` suppression in `--bg` mode (Q3 verdict):** when the dispatch mode is `--bg`, steering does NOT emit the worker-cron setup paste-block, and `--worker-cron` (whether explicit or via `--autopilot` expansion) is a SILENT NO-OP. The auto-ack-resume guard (PROTOCOL.md Worker Lifecycle Step 3) handles amendment pickup naturally because the worker re-reads the dispatch file on each active turn. The flag stays explicit for `--via-paste` / `--paste` users; no formal deprecation in v7.0.0. `--autopilot` macro behavior: in `--bg` mode, the macro still expands to `--auto-ack --auto-amend --worker-cron --watch`, but `--worker-cron` is suppressed at emission time.

**Worker-side polling in `--bg` mode (v7.1.1+ — clarification, fdev-b2f):** users coming from `--worker-cron`-flag documentation may wonder what fills the gap if `--worker-cron` is a no-op in `--bg`. The answer is the v7.1.1 **worker self-poll** mechanism (`### Worker self-poll at pause points (v7.1.1)` above), which is a worker-side convention armed automatically at intent + DAR pause points — not a steering flag. The worker self-poll is `--bg`-mode-only and supersedes `--worker-cron` semantics in that mode; `--worker-cron` remains the worker-side polling mechanism for `--via-paste` / `--paste` modes.

**Cron emission dispatch-mode split (v7.0.1):** all autopilot cron templates in CRONS.md branch their emission shape on the dispatch's `worker_dispatch_mode` field (set once at dispatch-time, read fresh on each fire). The two paths have fundamentally different interaction contracts; see CRONS.md `### Cron Dispatch-Mode Conventions (v7.0.1)` for the full rules. In summary:

- **`--bg` path** — cron writes to the dispatch file (state-change contract) and emits a single inline `STATE:` line to steering's chat. No labeled-copy fences (operator monitors steering output directly; no paste-into-worker-tab step exists in `--bg`). Cron MUST NOT invoke `claude --resume <worker-session>` against a running `--bg` agent — Claude Code refuses with `Error: Session <uuid> is currently running as a background agent (bg). Use claude agents to find and attach to it, or add --fork-session to branch off a copy.` Cron MUST NOT invoke `claude --fork-session` either — forking creates a duplicate session that violates the single-worker-per-dispatch invariant (both sessions could write conflicting state to the dispatch file). The cron's file write is the contract; the worker self-polls via auto-ack-resume guard or `falcon poll` operator nudge.
- **`--via-paste` / `--paste` path** — cron writes to the dispatch file AND emits the full labeled-copy fence (unchanged from prior versions). Operator pastes the fence contents into the worker tab; the worker reads as a regular user message.

The mode-conditional logic appears in every cron template (`--watch`, `--auto-ack`, `--auto-amend`, `--release-on-merge`) at the emission step. `--worker-cron` carries a defensive check that self-cancels if the cron is somehow armed in `--bg` mode (it should never be — `--bg` suppresses it at emission time per the paragraph above).

**Worker continuation mode (when `dispatch_continuation: true`):** if the worker's bootstrap detects `dispatch_continuation: true` on the loaded dispatch file (set by `/falcon respawn-fresh`), it executes a THREE-STEP RECOVERY SEQUENCE before normal lifecycle:

```
STEP A — Push any local-only commits from prior worker:
* Run `git log <branch>` (local) and `git log origin/<branch>` (canonical)
* If local HEAD has commits NOT on origin/<branch>: `git push` first to
  land them. The prior worker may have committed but died before pushing.
* Do NOT skip this; without it, the successor will redo committed work
  and produce duplicate commits.

STEP B — Close any beads with landed-but-not-bd-closed commits:
* For each bead in bead_ids[]: run `bd show <id>` to read current status
* If bead status is "in_progress" BUT a commit on origin/<branch> with
  "Closes: <id>" in the message already exists (check via `git log
  origin/<branch> --grep="Closes: <id>"`):
  → run `bd close <id>` with a close_reason noting "respawned-fresh
     successor closing prior worker's landed work"
  → continue to next bead; do NOT re-implement
* If bead status is "in_progress" AND no closes-commit exists yet:
  bead is genuinely incomplete; the successor will pick up the work

STEP C — Reconcile amendments[]:
* status: completed | satisfied | rejected → already done; skip
* status: in_progress (prior worker died mid-execution):
  → BEFORE resetting to pending: check the amendment's commits[] field
  → if commits[] is non-empty AND all SHAs exist on origin: mark
    status: satisfied with worker_response noting "prior worker
    committed changes before death; successor verified"
  → else: set back to pending with a worker_response noting the prior
    session's death; re-execute from scratch on next amendment cycle
* status: pending → execute normally per Amendments Workflow

After three-step recovery, continue with Worker Lifecycle as normal:
* For beads: `bd update <id> -s in_progress` is idempotent; safe to re-issue
* For intent confirmation: if intent_acknowledged_utc is non-null, skip
  intent-confirm (existing auto-ack-resume guard handles this)
* Note: successor may inherit multiple queued amendments from autopilot
  crons fired during the dead-session gap; process them all in order on
  first active turn before emitting completion signal
```

For initial dispatch (`dispatch_continuation: false`, the default), the worker follows Worker Lifecycle from Step 1 as written.

**Mutual exclusion:** `--bg` cannot coexist with `--paste` (steering refuses at the Mode selection branch above). `--bg-isolated` and `--bg-no-isolation` cannot coexist (steering refuses).

For the bootstrap-prompt template + substitution variables + repo_path-anchor rationale: see [`REFERENCE.md`](./REFERENCE.md#bootstrap-prompt-template-v700) `### Bootstrap Prompt Template (v7.0.0)`.

### Worker self-poll at pause points (v7.1.1)

**Problem (v7.0.0 carryover).** In `--bg` mode the steering autopilot crons (`--auto-ack`, `--auto-amend`) write decisions into the dispatch file, but the worker is idle in `claude agents` at intent-confirm — it never reads those writes without an external poke (peek/reply, attach, `falcon poll`). The auto-ack-resume guard at Worker Lifecycle Step 3 only fires when the worker takes a turn; it cannot schedule the turn itself. The amendment-propagation latency note above and the supervisor-stopped worker note describe the wake-gap; this section is the fix.

`--worker-cron` stays a SILENT NO-OP in `--bg` (its setup-paste-block UX is orthogonal — there's no worker tab to paste into). The fix is a worker-side convention: at known pause-for-steering points, the worker arms a self-poll cron scoped to that pause's wait condition, then `CronDelete`s it as soon as the condition is satisfied.

**Where it arms.** Two points qualify (see Worker Lifecycle Step 3 and DAR protocol below):

1. **Intent emission** (Step 3, after writing `implementation_intent` and before STOP-await-ack) — arms a self-poll watching `intent_acknowledged_utc`. On non-null observation, the worker calls `CronDelete` with the cron ID it captured from `CronCreate`'s return value at arm time, then resumes past intent-confirm into claim.
2. **DAR pause for response** (when a DAR is written with `response: null` AND the worker stays alive waiting on the response, rather than partial-reporting per the HIGH-stakes path) — arms a self-poll watching the DAR entry's `response` field. On non-null observation, the worker calls `CronDelete` with the captured ID and incorporates the response.

**Role split.** The cron's prompt is a *wake nudge with state-check instructions*. When the cron fires, its prompt is delivered to the worker session as a user-message-style notification. The WORKER — which holds the cron ID in session memory from the `CronCreate` return value — interprets the prompt, checks state, and executes `CronDelete(captured_id)` + resume on wait-condition-satisfied. The cron prompt does NOT carry a `<self-id>` placeholder; the worker resolves the reference using its captured ID.

For the literal `CronCreate` blocks (armed by the worker; templated into the dispatch's `init_prompt` flow), see [`CRONS.md`](./CRONS.md#worker-self-poll-cron-templates---bg-mode-only-v711) `## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)`.

**Critical scope guardrail.** Self-poll crons are armed ONLY at explicit pause-for-steering points, NEVER as an always-on background poller. Armed during normal implementation, they would burn API calls polling the worker's own state while the worker is actively working. The worker's `CronDelete(captured_id)` on wait-condition-satisfied is part of the contract, not optional. `durable: false` is mandatory — the cron must die with the worker session if the operator kills the agent.

**Mode applicability.** Self-poll is `--bg`-mode only. In `--via-paste` and `--paste` modes, the operator's `proceed <id>` paste (or the worker-cron polling the dispatch file in `--via-paste`) is the wake mechanism — the self-poll does NOT apply. The init_prompt template includes an explicit mode-skip note.

**Coordination model.** The two-cron design (steering cron + worker self-poll) leverages the existing atomic-write semantics described in `### --autopilot mode (full AFK bundle, v6.11.0)` below: each cron's writes are observable to the others on their next fires. No new IPC primitive; no schema change. Worst-case observation lag: ~2 min (intent) or ~3 min (DAR).

**Cost.** ~2 API calls per minute during a paused window. Negligible relative to v7.1.0's signal-density target (>30% across the dispatch lifetime) — paused windows are precisely where signal density would otherwise be zero.

### --watch mode (autopilot observability foundation, v6.8.0)

When `--watch` is set, after Step 1c (lock-registry check) and Step 2 (dispatch file write), steering arms a steering-side cron via `CronCreate` against the dispatch. The cron runs in **report-only mode** — it never writes to the dispatch file, never acknowledges intent, never issues amendments, never releases the lock. Its only job is to detect state transitions on the dispatch and emit a status block when one is observed.

Wiring:

1. Steering calls `CronCreate` with the **condensed** prompt body from [`CRONS.md`](./CRONS.md#--watch-cron-prompt-template-v680) `## Autopilot Cron Prompt Templates ### --watch cron prompt template (v6.8.0) #### Condensed CronCreate prompt (v7.1.2)` (~250-token pointer-style; the cron Reads the canonical Steps 1-4 spec from the same section at fire time per the v7.1.2 condensation work). Dispatch ID, dispatch file path, snapshot file path, and branch name are substituted into the template at CronCreate time — there are no generic crons.
2. `CronCreate` returns an ID; steering writes it to `watch_cron_id` in the dispatch file.
3. Cron cadence: default 10 minutes; override via `--cron-cadence Nm`.
4. Cron ID naming convention: `falcon-watch-<dispatch-id>` — used by `/falcon status` and `/falcon release-cron` for prefix-match lookups via `CronList`.
5. Snapshot file: `.claude/tmp/falcon-watch-<dispatch-id>-state.json` — the cron writes its last-observed state here between fires so successive fires can compute deltas. The snapshot is removed when the cron self-cancels (on terminal `session_status: complete`) or when `/falcon release-cron` runs.

The cron self-cancels on terminal state. Manual teardown is `/falcon release-cron <dispatch-id>` (see Step 5 below).

**Minimum-viable mode when project gates are commented:** when `.claude/rules/falcon-autopilot.md` exists but every `# PROJECT —` section is commented (the post-`/falcon create-rules` default), `--watch` still works — it reads the dispatch file and bd state without consulting the autopilot rules at all (report-only does not need them). The rules file only becomes load-bearing under Phase 2+ flags (`--auto-ack`, `--auto-amend`, etc.) that gate writes against `SAFE_TO_ACK_INTENT` / `SAFE_TO_AMEND`. Phase 1's `--watch` does NOT refuse on a fully-commented rules file.

**Per-dispatch commit attribution (v7.0.1, fdev-lbq.4):** when N dispatches share a branch (the v7.0.x parallel-dispatch model), the watch cron MUST distinguish commits authored by its own dispatch from commits authored by sibling dispatches. The attribution mechanism is the `Closes: <bead-id>` commit trailer that workers already include per Worker Lifecycle Step 8. The watch cron computes:

- `commits_attributed` — `git log origin/<branch> --grep="Closes: <bead-id>"` summed across `bead_ids[]` (this dispatch's contribution)
- `commits_unattributed` — `branch_total - commits_attributed` (sibling dispatches OR amend/rebase commits that dropped the trailer)

The STATUS UPDATE / `STATE: WATCH-STATUS-UPDATE` emission reports both counts. A separate degraded notification (`STATE: WATCH-UNATTRIBUTED-COMMIT-DETECTED` or the labeled-copy variant in paste-mode) fires only when `commits_unattributed` GREW since the prior fire — this catches amend/rebase that dropped the trailer without spamming on routine parallel-dispatch noise (where unattributed stays steady across many fires).

**Worker contract**: per Worker Lifecycle Step 8, every commit MUST include `Closes: <bead-id>` in the message. In single-dispatch mode this was best-practice; in parallel-dispatch mode it's a CORRECTNESS requirement — without the trailer, the watch cron cannot attribute the commit and falls through to the degraded notification on first observation. Amend/rebase that drops the trailer triggers a one-time degraded notification per fire; subsequent fires stay quiet.

**Adaptive cadence (v7.0.1, fdev-lbq.2):** the `--watch` cron does NOT have a per-fire adaptive guard — it's report-only and the file-read it does is already cheap. The other write-bearing crons (`--auto-ack`, `--auto-amend`) DO have a "Step 0 — Adaptive cadence early-exit guard" that short-circuits at minimum token cost when there's no work to do this fire (pre-window or post-window state). See CRONS.md cron templates for the exact guards.

**Dispatch lifecycle phases (v7.1 spec; impl deferred, fdev-lbq.27):** a dispatch moves through five phases over its lifetime. Each phase has a different relevance window for each cron type. `current_phase` is COMPUTED from existing dispatch-file fields (no new schema field needed):

| Phase | Detection |
|-------|-----------|
| `pre_intent` | `implementation_intent` is null |
| `intent_confirm` | `implementation_intent` non-null AND `intent_acknowledged_utc` is null |
| `implementation` | `intent_acknowledged_utc` non-null AND `implementation_results_hash` is null |
| `verify_amendment` | `implementation_results_hash` non-null AND `session_status` != "complete" |
| `post_validated` | `session_status` == "complete" |

A new `phase_transitions[]` field on the dispatch file records each transition forensically (`{from, to, utc, cron_re_arms: [...]}`); see REFERENCE.md Dispatch File YAML Schema for the entry shape.

The Phase Transition Handler (below) detects transitions on each steering invocation and re-arms crons at phase-appropriate cadence. See `### Phase Transition Handler (v7.1)` below this section.

**Forecast-driven initial cadence (v7.1.0 LIVE, fdev-lbq.28 implements fdev-lbq.25 spec):** at dispatch-time Step 2, steering parses the bead's Effort Forecast from the bead body (via `bd show --json <bead-id>` → description field; regex on the `- Total: ~N turns` and `- Confidence: <low|medium|high>` lines per the work-item-templates.md §Effort Forecast contract), maps Total turns to a bucket, applies the confidence modulator, and computes the per-cron initial cadence used in each subsequent CronCreate call. The bucket table:

| Total Turns | Initial cadence (auto-ack / auto-amend / watch) |
|---|---|
| ≤ 15 (short)  | 2m / 4m / 6m |
| 16-50 (medium) | 4m / 7m / 11m (current default) |
| > 50 (long) | 8m / 14m / 22m |

Confidence modulator: `low` → shift one bucket faster (catch overruns); `high` → shift one bucket slower (reduce noise). Missing Effort Forecast → use medium bucket default (graceful degrade); steering emits one inline log line `no Effort Forecast found on bead <id> — using medium bucket default (4m/7m/11m)`.

**Parser pseudocode (the implementation at Step 2):**

```
def compute_initial_cadence(bead_id):
    body = bd_show_json(bead_id).description            # string
    total_match = regex(r'-\s*Total:\s*~?(\d+)\s*turns', body)
    conf_match  = regex(r'-\s*Confidence:\s*(low|medium|high)', body, IGNORECASE)
    if not total_match:
        log_inline(f"no Effort Forecast found on bead {bead_id} — using medium default (4m/7m/11m)")
        return MEDIUM_BUCKET                            # (4, 7, 11)
    total = int(total_match.group(1))
    confidence = (conf_match.group(1).lower() if conf_match else "medium")
    if total <= 15:    bucket_idx = SHORT
    elif total <= 50:  bucket_idx = MEDIUM
    else:              bucket_idx = LONG
    if confidence == "low":  bucket_idx = max(SHORT, bucket_idx - 1)
    elif confidence == "high": bucket_idx = min(LONG,  bucket_idx + 1)
    return BUCKETS[bucket_idx]                          # (ack_m, amend_m, watch_m)
```

The computed `(ack_m, amend_m, watch_m)` tuple feeds into each CronCreate call's schedule string at Step 2: `*/<ack_m> * * * *` for the autoack cron, `*/<amend_m> * * * *` for autoamend, `*/<watch_m> * * * *` for watch. Release-on-merge cadence is a separate constant (15m default) — not in this bucket table.

**Multi-bead dispatches**: if `bead_ids[]` has multiple entries, compute the per-bead cadence for each and pick the FASTEST cadence (smallest minute value) across the set per cron type. Rationale: a short-bucket bead in the set drives the cadence; longer-bucket beads are over-polled but the short bead's relevance window dominates the dispatch.

**Cadence prose elsewhere in PROTOCOL.md is bucket-computed-at-dispatch-time, not hardcoded.** References to "default 10m watch" / "default 5m auto-ack" etc. in `### --watch mode`, `### --auto-ack mode`, etc. now reflect the MEDIUM bucket value as the documented default; actual cadence at a given dispatch depends on the bead's forecast.

**v7.1.0 ships the impl** (fdev-lbq.28 closed). v7.0.1 shipped only the SPEC + bucket table because the in-prompt Step 0 adaptive-cadence guards (fdev-lbq.2/.3) already reduce per-fire cost in quiescent windows. The v7.1.0 impl extends that with dispatch-time cadence bucketing — short beads get tighter cadences (2m/4m/6m), long beads get relaxed (8m/14m/22m), missing-forecast falls back to medium default.

### Phase Transition Handler (v7.1.0 LIVE, fdev-lbq.29 implements fdev-lbq.27 spec)

Builds on the bucket table above. Where fdev-lbq.28 sets the INITIAL cadence at dispatch start, this handler detects phase transitions during the dispatch lifecycle and RE-ARMS each cron at the phase-appropriate cadence. Each phase × cron-type pair has a multiplier applied to the bucket cadence.

**Discover-phase resolutions (from fdev-lbq.29 impl):**

- **Auto-ack self-cancel ownership in `implementation` phase**: ACTIVE CronDelete on the transition. The handler explicitly `CronDelete`s the auto-ack cron when entering `implementation` and records `{cron: "autoack", self_cancelled: true}` in phase_transitions[].cron_re_arms[]. The Step 0 adaptive-cadence guard (fdev-lbq.2) remains in the auto-ack template as redundant safety, but the canonical owner of the self-cancel transition is this handler.

- **verify_amendment auto-ack "(quiescent)" code path**: by the time the dispatch reaches `verify_amendment`, the auto-ack cron was already CronDeleted in the implementation-phase transition above; its `autoack_cron_id` field on the dispatch file is null. The handler checks each cron's `<cron>_cron_id` field at the top of the per-cron loop; if null, the cron is skipped entirely with `{cron: "autoack", skipped: true, reason: "not armed"}` recorded in cron_re_arms[]. No CronDelete attempt, no CronCreate, no error.

- **Atomic-write ordering vs partial failures**: the handler collects ALL per-cron outcomes (CronDelete attempted; CronCreate attempted with success/failure) in memory FIRST, then writes the dispatch file ONCE — both the `<cron>_cron_id` field updates AND the new `phase_transitions[]` entry — in a single atomic write. Never partial-state on disk. Each cron's outcome is captured in cron_re_arms[] regardless of success or failure (`error: "create_failed"` for graceful-degrade cases).

**Per-phase cadence multiplier table:**

| Phase | `--auto-ack` multiplier | `--auto-amend` multiplier | `--watch` multiplier |
|-------|-------------------------|---------------------------|----------------------|
| `pre_intent` | × 2 (SLOW — nothing to ack yet) | × 2 (SLOW — no completion yet) | × 1 (default — watching for intent emission) |
| `intent_confirm` | × 0.5 (FAST — ack-latency matters) | × 2 (SLOW — still no completion) | × 1 (default) |
| `implementation` | self-cancel via Step 0 (already-acked early-exit) | × 2 (SLOW — completion pending) | × 1 (default — watching for completion + commits) |
| `verify_amendment` | (quiescent; Step 0 catches) | × 0.5 (FAST — gap detection latency matters) | × 1 (default) |
| `post_validated` | self-cancel | self-cancel | self-cancel |

Multipliers stack on top of fdev-lbq.25's bucket cadence: `effective_cadence = bucket_cadence × phase_multiplier`. Floors at 1m to prevent over-polling on a short-bucket fast-phase combination.

**Transition-detection ownership: STEERING-SIDE.** A cron cannot reliably re-arm itself mid-fire (CronCreate semantics + race with self-cancel + Claude Code's cron sandbox lifecycle). Steering observes phase on each invocation (or on each cron-fire's STATE: emission via this handler) and re-arms when needed.

**Re-arm sequence on transition:**

```
1. Compute current_phase from dispatch file fields (see "Dispatch lifecycle phases" above).
2. Read previous_phase from phase_transitions[].last_or_null.
3. If current_phase == previous_phase: no transition; exit.
4. For each armed cron (watch, autoack, amend):
   a. CronDelete <cron_id>  (best-effort — ignore failure; cron may have
      self-cancelled already)
   b. Compute new cadence:
        new_cadence_minutes = bucket_minutes × multiplier(cron, current_phase)
        floor(1m, new_cadence_minutes)
      If multiplier indicates self-cancel (post_validated phase OR ack in
      implementation phase): skip CronCreate; this cron is done.
   c. CronCreate with the new schedule string (offset-staggered per
      fdev-lbq.5 convention; cron_slug_hash mod new_N for the offset)
   d. Update <cron>_cron_id on dispatch file with the new returned ID
      (atomic write; preserve all other fields)
5. Append a new entry to phase_transitions[] (forensic record):
     - from: <previous_phase>
     - to: <current_phase>
     - utc: <UTC ISO8601 at transition detection>
     - cron_re_arms:
         - cron: "watch", old_id: "<x>", new_id: "<y>", old_cadence_m: N, new_cadence_m: M
         - cron: "autoack", ... (or { cron: "autoack", self_cancelled: true })
         - cron: "amend", ...
```

**Failure modes:**

- **CronDelete fails** (cron already self-cancelled, ID is stale): proceed with CronCreate. Emit ONE inline log line per failed CronDelete: `CronDelete <id> failed (likely already self-cancelled); proceeding with re-arm.` Do not block transition.
- **CronCreate fails on re-arm** (transient API error, quota, etc.): log inline + graceful degrade — keep running with the OLD cadence by NOT updating `<cron>_cron_id` on the dispatch file. Surface: `CronCreate re-arm failed for <cron>; continuing with prior cadence <N>m. Investigate.` Never end up cron-less for a phase that needs polling.
- **Multiple transitions within one cycle** (e.g., worker emits intent and gets acked within 30s, before steering's next invocation): later-transition-wins. The handler computes current_phase fresh on each invocation; only ONE re-arm executes per cron per steering invocation regardless of how many intermediate phases were technically crossed.
- **`current_phase` regression** (theoretically impossible since detection is forward-only on existing fields): if observed, log a warning, take no action, and surface the dispatch file state inline for investigation.

**Where this handler runs in Step 4:** Step 4 (Stash for Wrapup + Auto-Release) runs the handler AFTER the safe-to-release check but BEFORE the auto-release path itself. Rationale: a successful auto-release triggers the `post_validated` transition which self-cancels all crons; running the handler first catches the transition + re-arms (or self-cancels) cleanly.

**Known limitation: non-Step-4 invocations miss transitions.** If steering is invoked mid-dispatch without reaching Step 4 (e.g., operator runs `/falcon status` or `/falcon list-locks`), the handler does NOT auto-fire. Cron cadences stay at their last-armed value until the next Step 4 invocation. The `/falcon transition <dispatch-id>` operator command (v7.1.0 LIVE, fdev-lbq.31) fills this gap as a deliberate manual-invocation path — invoke it to reconcile phase + re-arm crons on demand. See [`COMMANDS.md`](./COMMANDS.md) `### /falcon transition <dispatch-id>` for the user-facing spec. Auto-invocation on every steering command is out-of-scope (would couple every read-only command to a potential dispatch-file write).

**Watch-cron no-op optimization (fdev-lbq.29 R4):** when `new_cadence == current_cadence` for a cron (most commonly the `--watch` cron at × 1 across all non-terminal phases), the handler SKIPS the CronDelete/CronCreate for that cron. Forensic record still appears in `cron_re_arms[]` as `{cron: "watch", no_op: true, old_cadence_m: N, new_cadence_m: N}` so the audit trail shows the handler considered the cron at the transition.

**Cross-references:**
- Bucket cadences: `### Mode selection + detection` (above) §Forecast-driven initial cadence
- Step 0 per-fire adaptive guards: fdev-lbq.2/.3 (orthogonal — Step 0 = per-fire cost; this handler = per-phase cadence)
- Cron telemetry instrumentation: fdev-lbq.6 (records `phase_transitions[]` events alongside fire counts)
- Offset staggering for re-arm cadences: fdev-lbq.5 convention applies to new CronCreate calls

### --auto-ack mode (autopilot intent acknowledgement, v6.9.0)

When `--auto-ack` is set, after Step 1c (lock-registry check) and Step 2 (dispatch file write), steering arms a steering-side cron via `CronCreate` that evaluates the `SAFE_TO_ACK_INTENT` 4-gate predicate against the worker's intent paragraph on each fire. When all gates pass, the cron writes `intent_acknowledged_utc` to the dispatch file and emits the `proceed <dispatch-id>` block inline. When any gate fails, the cron defers silently with one inline note (per intent) explaining which gate failed and how to manually ack.

This is the FIRST write-bearing autopilot cron (Phase 1's `--watch` was report-only). The wiring mirrors `--watch` but with stricter preconditions:

1. Steering calls `CronCreate` with the **condensed** prompt body from [`CRONS.md`](./CRONS.md#--auto-ack-cron-prompt-template-v690) `## Autopilot Cron Prompt Templates ### --auto-ack cron prompt template (v6.9.0) #### Condensed CronCreate prompt (v7.1.2)` (~400-token pointer-style with INLINE Step 0 adaptive guard; Steps 1-6 + advisor extension are pointer-style per the v7.1.2 condensation work). Dispatch ID, dispatch file path, snapshot file path, repo path, and branch name are substituted at CronCreate time.
2. `CronCreate` returns an ID; steering writes it to `autoack_cron_id` in the dispatch file.
3. Cron cadence: default 5 minutes (shorter than `--watch`'s 10m because intent windows are brief and the cache-cost analysis from the v6.8.0 changelog applies here); override via `--cron-cadence Nm`.
4. Cron ID naming convention: `falcon-autoack-<dispatch-id>` — same prefix-match convention as `--watch`; `/falcon status` and `/falcon release-cron` discover both via slug-prefix.
5. Snapshot file: `.claude/tmp/falcon-autoack-<dispatch-id>-state.json` — tracks the last-evaluated intent-paragraph hash so successive fires don't re-evaluate (or re-emit a defer/refuse block for) an unchanged intent.

The cron self-cancels on terminal state (`session_status: complete`). Manual teardown is `/falcon release-cron <dispatch-id>` — same as `--watch`; both prefixes are torn down together.

**Refuse-on-MVM (REQUIRED, NOT optional):** unlike `--watch`, `--auto-ack` REFUSES to operate when `.claude/rules/falcon-autopilot.md` either does not exist or has every `# PROJECT —` section under `## 1. SAFE_TO_ACK_INTENT predicate` commented (the post-`/falcon create-rules` default minimum-viable mode). The refuse-block emitted by the cron names the specific gate the user should uncomment. Rationale: `--auto-ack` writes `intent_acknowledged_utc` which the worker treats as authorization to skip the intent-confirm pause — writing without a project-confirmed gate is a much larger blast radius than the report-only observation `--watch` does. Universal gates alone are NOT sufficient for write-bearing autopilot; the project must opt in.

**Dual-cron coordination with `--watch`:** when both flags are set, two separate crons run with independent slugs and sidecars. They do not coordinate; each evaluates its own state-change criteria. Combining them was rejected at Phase 2 design time because flag-aware branching inside a single cron template adds complexity for marginal cron-count savings, and the prefix-match teardown convention already handles multi-cron-per-dispatch cleanly.

**Worker-side complement (see Worker Lifecycle Step 3 below):** the worker checks `intent_acknowledged_utc` on each resume prompt. If non-null AND no commits have landed yet, the worker skips the intent-confirm pause and proceeds straight to claim — eliminating the double-prompt that would otherwise occur if the worker session restarts after the cron already acked.

**Phase-active windows (v7.1.0 LIVE, fdev-lbq.29):** `--auto-ack` peaks at fast cadence (× 0.5 bucket) in the `intent_confirm` phase; is slow (× 2) in `pre_intent`; and ACTIVELY self-cancels (CronDelete by the Phase Transition Handler) when transitioning to `implementation` (intent_acknowledged_utc is non-null). The Step 0 adaptive-cadence guard remains as redundant safety, but the canonical owner of the self-cancel transition is the Phase Transition Handler. See `### Phase Transition Handler (v7.1.0 LIVE)` for the multiplier table and re-arm sequence.

### --auto-amend mode + --amendment-budget HALT (v6.10.0)

When `--auto-amend` is set, after Step 1c (lock-registry check) and Step 2 (dispatch file write), steering arms a steering-side cron via `CronCreate` that evaluates the `SAFE_TO_AMEND` whitelist against gaps surfaced from the dispatch's Step 3 validation + Step 3b cognitive audit. On whitelist match, the cron auto-issues an amendment to the dispatch file's `amendments[]` array (`issued_by: steering-cron`, `label: auto-issued:cron`) and emits a `check amendments <dispatch-id>` block inline for the worker to pick up.

This is the THIRD entry in the cron prompt template registry (after `--watch` from Phase 1 and `--auto-ack` from Phase 2). Wiring follows the established pattern:

1. Steering calls `CronCreate` with the **condensed** prompt body from [`CRONS.md`](./CRONS.md#--auto-amend-cron-prompt-template-v6100) `## Autopilot Cron Prompt Templates ### --auto-amend cron prompt template (v6.10.0) #### Condensed CronCreate prompt (v7.1.2)` (~450-token pointer-style with INLINE Step 0 adaptive guard; Steps 1-7 + advisor extension are pointer-style per the v7.1.2 condensation work). Dispatch ID, dispatch file path, snapshot file path, repo path, and branch name are substituted at CronCreate time.
2. `CronCreate` returns an ID; steering writes it to `amend_cron_id` in the dispatch file.
3. Cron cadence: default 5 minutes (matches `--auto-ack`; amendment evaluation requires the worker's completion signal to be present, so the same fast-feedback window applies); override via `--cron-cadence Nm`.
4. Cron ID naming convention: `falcon-amend-<dispatch-id>` — same prefix-match teardown via `/falcon status` + `/falcon release-cron`.
5. Snapshot file: `.claude/tmp/falcon-amend-<dispatch-id>-state.json` — tracks the last-evaluated gap-set hash + last fire outcome (issued / refused / deferred / halted / silent / no-gaps) so successive fires don't spam.

`--amendment-budget N` works in concert with `--auto-amend` (and is meaningless without it). It sets `amendment_budget: N` on the dispatch file at dispatch time. The cron's Step 4 (budget HALT check) compares `auto_amendment_count` against this cap on every fire:

- `amendment_budget == null` → no cap; cron issues indefinitely while gaps surface AND whitelist matches.
- `auto_amendment_count < amendment_budget` → proceed with amendment evaluation.
- `auto_amendment_count >= amendment_budget` → HALT auto-issuance for the rest of the dispatch. Emit `AMENDMENT BUDGET EXHAUSTED` block ONCE (on the first fire to detect exhaustion); stay silent thereafter on amendment evaluation. The `--watch` and `--auto-ack` crons continue uninterrupted; only the amendment-issuance path is halted.

**Refuse-on-MVM (REQUIRED, NOT optional):** carrying the Phase 2 precedent. `--auto-amend` is the most write-bearing autopilot flag in the rollout — issued amendments cause the worker to write code. The cron REFUSES to operate when `.claude/rules/falcon-autopilot.md` is missing OR has every `# PROJECT —` item under `## 2. SAFE_TO_AMEND whitelist` commented. The refuse-block names a specific whitelist item the user should uncomment. Universal whitelist alone is NOT sufficient; the project must opt in.

**Manual-amendment budget exemption:** only `auto-issued:cron`-labeled amendments decrement the budget. Amendments written by the user (or by steering on manual relay) do NOT count against the cap. This lets the user keep iterating manually after the cron has halted, without changing the cap.

**Triple-cron coordination:** when `--watch --auto-ack --auto-amend` are all armed, three separate crons run side-by-side with independent slugs and sidecars. They do not coordinate; the `--watch` cron observes state changes that the other two crons cause. The prefix-match teardown convention handles all three together via `/falcon release-cron`.

**Phase-active windows (v7.1.0 LIVE, fdev-lbq.29):** `--auto-amend` peaks at fast cadence (× 0.5 bucket) in the `verify_amendment` phase (completion emitted → released); is slow (× 2) in `pre_intent` / `intent_confirm` / `implementation` (no completion yet); and self-cancels in `post_validated`. The amendment-budget HALT path is orthogonal to the phase-active cadence — when the budget exhausts, the cron stays at the verify_amendment cadence but Step 0 / Step 4 guards suppress further amendment issuance. See `### Phase Transition Handler (v7.1.0 LIVE)` for the multiplier table and re-arm sequence.

### --autopilot mode (full AFK bundle, v6.11.0)

`--autopilot` is a macro flag that expands to `--auto-ack --auto-amend --worker-cron --watch`. It is the full bidirectional AFK setup: steering autonomously acknowledges intent + auto-issues whitelisted amendments + observes state changes; worker autonomously picks up amendments without manual relay. The user's only post-dispatch action is reading the completion summary or arbitrating an inline interrupt (DAR defer, budget exhaustion, hard fail).

Wiring at Step 2:

1. Steering computes the expansion: `--auto-ack --auto-amend --worker-cron --watch`. All four flags' Step 2 wiring fires.
2. Steering arms THREE crons (its own session): `falcon-watch-<dispatch-id>` (10m cadence by default), `falcon-autoack-<dispatch-id>` (5m by default), `falcon-amend-<dispatch-id>` (5m by default). All three armed via separate `CronCreate` calls; the returned IDs written to `watch_cron_id`, `autoack_cron_id`, `amend_cron_id` respectively.
3. Steering emits TWO paste blocks for the user to copy into the worker tab:
   - Standard dispatch prompt (per [`REFERENCE.md`](./REFERENCE.md#dispatch-prompt-template) `## Dispatch Prompt Template`)
   - Worker-cron setup paste-block (per [`CRONS.md`](./CRONS.md#--worker-cron-setup-paste-block-v6110) `### --worker-cron setup paste-block`)
4. User pastes both into the worker tab (order: dispatch prompt first, then worker-cron-setup). The worker session reads the dispatch file, arms its own `falcon-worker-<dispatch-id>` cron (3m cadence by default), and writes `worker_cron_id`.

Four-cron coordination once everything is armed:

- `falcon-watch-` (steering): report-only state observation; 10m
- `falcon-autoack-` (steering): SAFE_TO_ACK_INTENT evaluation; writes `intent_acknowledged_utc`; 5m
- `falcon-amend-` (steering): SAFE_TO_AMEND evaluation + budget HALT; writes `amendments[]`; 5m
- `falcon-worker-` (worker session): polls `amendments_pending`; executes pending amendments; writes per-amendment `status` + `worker_response` + `commits[]`; 3m

They do not communicate directly; the dispatch file's atomic-write semantics are the coordination primitive. Each cron's writes are visible to the others on their next fires.

Teardown coverage:

- `/falcon release-cron <dispatch-id>` runs in steering and tears down all THREE steering-side crons via prefix-match (`falcon-watch-`, `falcon-autoack-`, `falcon-amend-`). It does NOT teardown `falcon-worker-` (which lives in the worker session that steering's `CronList` cannot reach).
- The worker cron is `durable: false` and dies naturally with the worker session. If the worker tab is closed, the cron is gone.
- Manual worker-cron teardown (while worker session is still alive) requires a separate paste-block: `CronDelete <worker_cron_id_from_dispatch_file>` into the worker tab.
- All four crons self-cancel on `session_status: complete` per their individual Step N self-cancel logic.

When to use:

- Bead is well-scoped (no design questions remain)
- Project has both `safe_to_ack_intent.project_gates` AND `safe_to_amend_whitelist` PROJECT items uncommented in `falcon-autopilot.md` (refuse-on-MVM would otherwise block 2 of 3 steering crons)
- `--amendment-budget N` is set to a safe cap appropriate for the bead type (per `falcon-autopilot.md § 6` defaults)
- User is going AFK and wants minimum-touch operation

When NOT to use:

- First time using autopilot on a given project (start with `--watch` only to build confidence)
- Bead requires unresolved architectural decisions (intent gate will defer, amendment whitelist won't match — autopilot adds nothing over the manual flow)
- Worker is on a different machine without shared filesystem access (use `--paste` instead, which is incompatible with all cron-based autopilot flags)

### --release-on-merge mode (v6.12.0)

When `--release-on-merge` is set, after Step 1c (lock-registry check) and Step 2 (dispatch file write), steering arms a steering-side cron via `CronCreate` that polls `gh pr view --json state` for the dispatch's branch on each fire. On `state: MERGED`, the cron sets `session_status: complete` on the dispatch file, which triggers the normal auto-release path in Step 4 and self-cancellation across all other crons for this dispatch.

Wiring:

1. Steering calls `CronCreate` with the **condensed** prompt body from [`CRONS.md`](./CRONS.md#--release-on-merge-cron-prompt-template-v6120) `## Autopilot Cron Prompt Templates ### --release-on-merge cron prompt template (v6.12.0) #### Condensed CronCreate prompt (v7.1.2)` (~200-token pointer-style; no Step 0 — single-purpose poller; Steps 1-5 are pointer-style per the v7.1.2 condensation work). Dispatch ID, dispatch file path, snapshot file path, repo path, and branch name are substituted at CronCreate time.
2. `CronCreate` returns an ID; steering writes it to `merge_cron_id` in the dispatch file.
3. Cron cadence: default 15 minutes (longer than the write-bearing crons because PR merges are low-frequency state changes; the cache-miss is amortized over the longer wait per the v6.7.0 cache-cost guidance). Override via `--cron-cadence Nm`.
4. Cron ID naming convention: `falcon-merge-<dispatch-id>` — same prefix-match teardown via `/falcon release-cron`.
5. Snapshot file: `.claude/tmp/falcon-merge-<dispatch-id>-state.json` — tracks last-observed PR state so successive cron fires don't re-poll on unchanged state.
6. Steering also sets `release_on_merge: true` on the dispatch file (this field is the source of truth for the new Step 4 hold-the-lock condition, even if the cron is somehow not running).

No refuse-on-MVM: `--release-on-merge` does not evaluate project gates. It only observes external state (PR merge) and writes a single status transition. The "gate" is the PR review process itself (held in GitHub, outside the autopilot rules file).

Usable standalone (without `--watch`, `--auto-ack`, or `--auto-amend`) — if the user only wants the merge-blocked lock-release behavior without other autopilot. Common pattern: paranoid lock-release on a single-bead dispatch touching contract-bearing files where lock-overlap during the review→merge gap is unacceptable.

### --dry-run mode

When `--dry-run` is set, the dispatch protocol short-circuits before any persistent state mutation. Specifically:

1. Steps 1, 1b (if applicable) run normally — bead resolution + grep audit.
2. Step 1c (lock-registry check) runs in **read-only mode**: the check is performed and the result reported (overlap vs clean), but the new dispatch is NOT registered in the current session's `falcon_dispatches[]`.
3. Step 2 (dispatch file write + worker prompt emit) is **skipped entirely** — no `.claude/tmp/falcon-dispatch-<6hex>.yaml` is written, no worker prompt is emitted.
4. If `--watch` or `--autopilot` is co-set, the cron is NOT scheduled — instead, the cron prompt that WOULD be scheduled is printed inline.

Steering prints a preview block summarizing what would have happened:

- Resolved bead set (IDs + titles + triage states)
- Derived `file_scope` (directories + files; union for `--sequential`)
- Lock-registry check result (`clean` or `overlap with dispatch <id> on <path>`)
- Autopilot policy effects (which flags would fire — Phase 1: `--watch` cron cadence + offset preview; future phases: `SAFE_TO_ACK_INTENT` gate preview, `SAFE_TO_AMEND` preview, `--amendment-budget` cap)
- Cron prompt body (if `--watch` / `--autopilot` co-set) — the literal string CronCreate would have received

Use when previewing autopilot effects on a bead you're not sure is well-scoped, or to verify file_scope before committing to a multi-bead dispatch.

---

## Step 3 — Receive and Validate Worker Report

When the user signals worker completion (typically by pasting the worker's short "Work stream completed at `<UTC ISO8601>`. Re-read `<dispatch-file>`." message), read the dispatch file's `implementation_results` section.

**Content-hash verification (before parsing results):** compute `sha256(implementation_results_content)` and compare to `implementation_results_hash` in the dispatch file. If they do not match — or if `implementation_results_hash` is null — the worker may have crashed mid-write or updated the results without updating the hash. Treat as a partial report and prompt the user to investigate before proceeding.

**Hash computation specifics:** `sha256(raw_string_as_written.encode('utf-8'))` — NOT sha256 of any normalized form. The worker writes a literal string; steering reads that literal string; hashes must agree byte-for-byte. Strip-trailing-whitespace variants are NOT equivalent.

Validation steps:

1. **Schema validate.** Run `yq '.' <results-section> > /dev/null` (or equivalent) — fail-fast on malformed YAML.
2. **Cross-check commits.** For each commit listed, `git fetch && git log <sha> --oneline` to confirm it exists on origin.
3. **Cross-check bead state.** For each closed bead, `bd show <id>` confirms `status: closed`.
4. **File-contract audit.** Diff the commits in this dispatch against the registered `file_scope`. If the worker touched files outside the declared scope (without raising an approved out-of-spec ask), flag as a `standards_firings` entry with action_taken: "file-contract violation — investigate before next dispatch."
5. **Amendment-status discipline audit.** Parse `amendments[]` in the dispatch file. For each amendment, confirm `status` is in a terminal state: `completed`, `satisfied`, or `rejected`. Any amendment still in `pending` or `in_progress` at completion-signal time indicates the worker abandoned the amendment cycle mid-flight (or stopped before processing it). Treat as a **hold-the-lock condition** — surface to user: `"Amendment <id> still in status '<pending|in_progress>'. Worker did not resolve before completion signal. Recovery: (a) re-prompt worker with 'check amendments <dispatch-id>' if session still alive, (b) manually set status if work is verifiably done outside the worker, OR (c) treat as worker-discipline lapse and decide whether to amend / re-dispatch / release-anyway."`
6. **Surface DAR decisions immediately** (do NOT defer to wrapup):
   - For each high-stakes DAR with `action_taken: stopped pending arbitration`: render full DAR inline and ask the user to arbitrate before next dispatch
   - For each low-stakes DAR with `action_taken: proceeded with recommendation`: render as one-liner ("N autonomous decisions made — see stashed report for detail")
7. **Surface out-of-band closes.** For each bead with `verification.out_of_band_required: true`: print the closure protocol so the user knows what to relay after human verification.

---

## Step 3b — Steering-Side Cognitive Audit (before deciding lock release vs amendments)

After the mechanical validation steps above, perform one additional check that no automated gate can substitute for:

**Ask yourself: "Is there a project-binding concern this bead's AC did NOT gate on?"**

Prompts to force the cognitive pause:
- Does the output contain content classes that the project's safety rules restrict, even if the AC was silent on them?
- Does the implementation strategy the worker chose create a pattern that will need to be undone when the sibling bead lands?
- Are there bead-type-specific validation checks the project convention calls for that are NOT in the bead's AC?
- **Are all amendments resolved (status: completed / satisfied / rejected)?** Backstop for Step 3 step 5.

**Per-bead-type validation hints (project-provided).** Falcon does NOT inline a taxonomy of "this bead type → run this command." Project-specific validation rituals belong in the project's own rule or doc files — typically `.claude/docs/work-item-templates.md` or a dedicated `.claude/rules/validation-hints.md`. At cognitive-audit time, steering consults whichever the project maintains.

**Universal patterns worth checking regardless of project:**
- **Migration / rename / retire beads** — run a post-commit grep for the identifiers the bead retired; flag any surviving occurrences.
- **Schema-bearing beads** — confirm any "this enum / contract value is what consumers expect" assumption still holds.
- **Beads that produce output a sibling bead consumes** — confirm the output shape matches what the sibling bead's AC declares as input.

If the cognitive audit surfaces a concern, treat it as an amendment opportunity (Step 3c) — NOT a lock release. Write the amendment, set `session_status: amendments_pending` in the dispatch file, relay the amendment to the worker before proceeding.

If the cognitive audit finds nothing, document explicitly: "Cognitive audit: no project-binding concerns beyond AC scope."

---

## Step 3c — Decide: auto-release vs amendments vs reject

After validation + cognitive audit, steering has three choices:

1. **Auto-release** (default; Step 4 handles it) — validation passed, cognitive audit found no concerns, no DARs pending arbitration. Step 4 stashes the report AND releases the lock in one go.
2. **Add an amendment** — work has gaps that the same worker can address without re-dispatching. Set `session_status: amendments_pending` in the dispatch file; lock STAYS HELD.
3. **Reject + reopen** — work has fundamental issues; worker session ends; re-dispatch a revised bead from scratch.

The **safe-to-release predicate**: validation steps 1-4 all pass AND step 5 (amendment-status discipline audit) returns "all amendments terminal" AND cognitive audit (Step 3b) returned "no concerns found" AND no high-stakes DAR has `action_taken: stopped pending arbitration` without a recorded resolution.

Amendments are appropriate when:
- Validation or cognitive audit surfaced a gap the worker can fix in-context
- A next-step emerged that's closely related to the original dispatch
- A test flake or minor issue needs the worker's debugging knowledge before lock release

Amendments are NOT appropriate when:
- The work requires new design decisions that should be in a fresh bead
- The scope expands beyond what the original file_scope can cover
- **The worker session has ended** (see "Dead-worker constraint" in Amendments Workflow below)

---

## Step 4 — Stash for Wrapup + Auto-Release (when safe)

Stash path is **branch-keyed**, not session-keyed:

```
.claude/tmp/falcon-reports-<sanitized-branch>.yaml
```

Derive the sanitized branch via `git rev-parse --abbrev-ref HEAD | tr '/' '-'`. The `tr '/' '-'` step is load-bearing — feature-branch names like `feature/work-20260521-foo` contain a `/` which would otherwise create a directory hierarchy instead of a single flat file.

If the file exists, **merge** the new report into the existing arrays — do not overwrite. For the `amendments` sub-field of each dispatch's contribution to the stash, **append only** — never overwrite an existing amendment entry.

After stash, run `git fetch origin && git log origin/<branch> --oneline -5` so this session has visibility into the remote's commits before the next dispatch.

**Phase Transition Handler invocation (v7.1.0, fdev-lbq.29):** before the auto-release path below, invoke the Phase Transition Handler (per `### Phase Transition Handler (v7.1.0 LIVE)` above) to detect any current_phase change since the prior fire and re-arm crons accordingly. Sequence: compute current_phase → compare to phase_transitions[].last (or null) → if different, run the per-cron re-arm loop → write updated cron_ids + phase_transitions[] entry atomically. Handler is idempotent when current_phase == previous_phase (early exit before the per-cron loop). On any CronCreate failure during re-arm, the handler logs an inline warning and continues with OLD cadence (`<cron>_cron_id` unchanged); never cron-less for a phase requiring polling.

**Auto-release (default path):** if the safe-to-release predicate holds, release the lock here as part of stash. Glob `.claude/tmp/*.json`, parse each, find entry matching `<dispatch-id>`, remove from `falcon_dispatches[]`, write back. Update the dispatch file `session_status: complete`. (NOTE: setting `session_status: complete` here triggers the post_validated phase transition. Since the Phase Transition Handler ran ABOVE this step, it observed the pre-release phase and re-armed accordingly. The post_validated transition self-cancels all crons via the next steering invocation — operators or wrapup running `/falcon status` / `/falcon list-locks` / `/wrapup` after release will trigger the handler one more time to catch the post_validated → all-self-cancel transition. Alternatively, the handler can be invoked synchronously at the end of Step 4 to self-cancel crons immediately on release; v7.1.0 ships the asynchronous-via-next-invocation pattern because it avoids ordering complexity inside Step 4 itself.)

**Agent-viewer row cleanup (v7.0.1, fdev-lbq.18):** after writing `session_status: complete` and clearing the lock registry, the agent-viewer row for the worker session should also be removed (otherwise dead rows accumulate in `claude agents` over multi-dispatch sessions). The right primitive is `claude rm <worker_bg_session_id>` — NOT `claude stop` (which only stops the process; row stays). Ordering is poll-then-rm to avoid losing the worker's final report write:

```
1. Write session_status: complete (above)
2. Remove from falcon_dispatches[] lock registry (above)
3. Poll the dispatch file for worker's final report fields (e.g.
   worker_close_utc, implementation_results.falcon_report filled in)
   up to TIMEOUT (default 30s; tunable per project in
   .claude/rules/falcon-autopilot.md if needed)
4. On poll success before TIMEOUT: invoke `claude rm <worker_bg_session_id>`
5. On TIMEOUT: log a single warning ("worker did not write final report
   within Ns; removing agent-viewer row anyway — investigate"), then
   invoke `claude rm` regardless. Warning visibility is the operator's
   signal that something on the worker side didn't terminate cleanly.
6. If `claude rm` prints a worktree path (uncommitted changes preserved):
   surface that path inline so the operator can clean up the worktree.
```

Skip the `claude rm` step in `--via-paste` / `--paste` modes — there's no `--bg` session row to remove. Skip ALSO if `worker_bg_session_id` is null (older dispatches predate this convention) — log a single-line "skipping claude rm; no worker_bg_session_id captured" and continue. Per-mode contract is captured in the cron Dispatch-Mode Conventions (CRONS.md).

This applies to:
- Step 4 auto-release (above)
- `/falcon release <dispatch-id>` manual path (Step 5 below — same implementation)
- `/wrapup` Task 0b orphan-release loop (sees the same primitive on each orphan it releases)

**Hold-the-lock conditions** (Step 4 stashes the report but does NOT release):
- An amendment is in `amendments[]` with non-terminal `status` (`pending` or `in_progress`)
- A high-stakes DAR has `action_taken: stopped pending arbitration` with no recorded resolution
- Cognitive audit returned a concern that steering hasn't decided how to handle
- Validation steps 1-5 surfaced a hard failure
- **(v6.12.0+) `release_on_merge: true` AND `session_status != complete`** — the lock stays held until the `falcon-merge-<dispatch-id>` cron detects PR merge and flips `session_status` to `complete`. Step 4's auto-release path then picks up the change on the next steering invocation.

When the lock is held, surface the reason to the user (single line: "Lock held: `<reason>`. Resolve with amendment / arbitration / manual release.") and wait.

**Manual release escape hatch:** `/falcon release <dispatch-id>` is available for cases where the auto-release path declined and steering wants to override.

Acknowledge to the user: `Report N stashed. M beads closed, K discovered, L blockers, D decisions (H high-stakes / L low-stakes), O out-of-band closures pending. Lock released for <files/dirs>. Dispatch another or run /wrapup.`

---

## Step 5 — Stale Lock Cleanup (manual)

**Single dispatch:** `/falcon release <dispatch-id>` — same implementation as Step 4 auto-release.

**Whole session:** `/falcon release-session <session-id>` — bulk release. Use when a whole worker session died and held multiple dispatches.

**Discovery commands:**

`/falcon list-locks` — flat list of all active dispatches across all session files:

```
Active dispatches (across N session files):

  Dispatch abc123 (session sess-7f, started 2026-05-21T18:20Z, status: amendments_pending):
    Beads: example-ckl.5
    Directories: docs/level-designs/samples/replays/
    Files: (none)

  Dispatch def456 (session sess-c2, started 2026-05-21T16:00Z, status: in_progress):
    Beads: example-ckl.4
    Directories: score-tracker/persistence/, score-tracker/tests/persistence/
    Files: score-tracker/scoreboard_module.py
```

`/falcon list-sessions` — sessions grouped, with staleness flags:

```
Sessions (across N JSON files):

  Session sess-7f (leroy, started 2026-05-21T18:20Z, last-active 2026-05-21T20:05Z [42m ago])
    Branch: feature/work-20260521-multi-workstream
    Dispatches: 2
      - 5e6f25  status: complete            bead ckl.4
      - abc123  status: amendments_pending  bead ckl.5

  Session sess-c2 (leroy, started 2026-05-20T09:15Z, last-active 2026-05-20T11:30Z [~30h ago])  STALE
    Branch: feature/work-20260520-old-thing
    Dispatches: 1
      - deadbe  status: active              bead ckl.3
    Suggested: /falcon release-session sess-c2
```

Staleness heuristic: `last-active > 2h ago` flags as STALE. The `last-active` timestamp comes from the session JSON's transcript path's mtime; if unreadable, fall back to the session JSON's own mtime.

### /falcon status <dispatch-id>

One-shot status query — the manual equivalent of a single `--watch` cron fire. Use when no watch cron is armed but you want a quick read.

Implementation:

1. Read the dispatch file at `.claude/tmp/falcon-dispatch-<dispatch-id>.yaml`. Capture: `session_status`, `implementation_intent` (presence), `implementation_results_hash` (presence), `amendments[]` (count + per-entry status), `intent_acknowledged_utc` (Phase 2 field — read as status, no action in Phase 1), `auto_amendments_issued` + `amendment_budget` (Phase 3 fields — read as status, no action in Phase 1), `watch_cron_id`.
2. For each bead in `bead_ids[]`: `bd show --json <id>` and capture status.
3. Compute commit count on branch since dispatch open: `git fetch origin && git log origin/<branch> --oneline --since=<dispatch.created_utc> | wc -l`.
4. If `watch_cron_id` is non-null: `CronList` and look up the matching slug `falcon-watch-<dispatch-id>`; capture the registered cadence.
5. Print:
   - `session_status`, intent presence, results-hash presence
   - bd state for each bead
   - commit count
   - amendment count + open DAR count (DARs are parsed from `out_of_spec_approval_requests[]`)
   - watch cron ID + cadence (or "no watch cron armed")

### /falcon release-cron <dispatch-id>

Tear down the watch/autopilot cron associated with a dispatch. Useful when the cron survived past the dispatch lifecycle (e.g., user cancelled the dispatch manually but the cron is still firing, or the snapshot file got out of sync).

Implementation:

1. `CronList` and prefix-match for `falcon-watch-<dispatch-id>` (Phase 1 slug; future phases will add additional prefixes).
2. For each match: `CronDelete <cron-id>`.
3. Remove the snapshot file at `.claude/tmp/falcon-watch-<dispatch-id>-state.json` if it exists.
4. Read the dispatch file; if `watch_cron_id` is non-null, null it out and write back.
5. Print: how many crons were cancelled + whether the snapshot file was removed + whether the dispatch file was updated.

This command does NOT release the dispatch lock — use `/falcon release <dispatch-id>` for that. It only tears down the cron + sidecar state, leaving the dispatch itself intact.

### /falcon list-pending

Scan all active dispatch files and print a flat grouped list of items waiting on human action. Designed for the return-from-AFK workflow: one command surfaces every pending-human item across all active dispatches so you know what needs your attention before doing anything else.

Implementation:

1. Glob all dispatch files: `.claude/tmp/falcon-dispatch-*.yaml`.
2. Parse each into a structured representation. Skip dispatches where `session_status == "complete"` (terminal — nothing pending).
3. For each remaining dispatch, evaluate the 6 categories:

   **Category 1 — HIGH-STAKES DAR awaiting arbitration:**
   Parse `implementation_results.falcon_report.decisions_for_human[]`. Filter to entries where `stakes: "high"` AND `action_taken: "stopped pending arbitration"` AND no recorded resolution (the dispatch file may also carry a resolution annotation; check both inline and in the branch-keyed stash file for the resolution). Output: dispatch ID, bead ID(s), DAR question (one-line), recommendation (one-line), action hint (`arbitrate inline, then /falcon release <id> OR amend`).

   **Category 2 — OUT-OF-SPEC APPROVAL REQUESTS:**
   Parse `out_of_spec_approval_requests[]`. Filter to entries where `response: null`. Output: dispatch ID, request_id, ask (one-line), file_path, rationale (one-line), action hint (`write response field on the dispatch entry OR relay to worker tab`).

   **Category 3 — OUT-OF-BAND VERIFICATION pending:**
   Parse `implementation_results.falcon_report.beads[]`. Filter to entries where `verification.out_of_band_required: true`. For each, run `bd show --json <id>` and confirm bd state is still `in_progress` (closed beads are no longer pending). Output: dispatch ID, bead ID, verification method (one-line from the bead spec), action hint (`run the named verification, then bd close <id>`).

   **Category 4 — AMENDMENT BUDGET EXHAUSTED:**
   Check dispatch fields `auto_amendment_count` and `amendment_budget`. Filter to dispatches where `amendment_budget` is non-null AND `auto_amendment_count >= amendment_budget` AND the lock is still held (cross-check session JSON `falcon_dispatches[]` for an entry with `status: in_progress`). Output: dispatch ID, exhaustion ratio, action hint (`issue manual amendments OR /falcon release <id>`).

   **Category 5 — PR CLOSED UNMERGED:**
   For dispatches with `release_on_merge: true`, read the merge-cron sidecar at `.claude/tmp/falcon-merge-<dispatch-id>-state.json`. Filter to dispatches where `last_outcome == "pr-closed-unmerged"` (the cron emitted `MERGE-CRON PR-CLOSED-UNMERGED` on a prior fire). Output: dispatch ID, PR number, last-polled timestamp, action hint (`/falcon release <id> OR re-dispatch as new bead`).

   **Category 6 — STALE LOCKS:**
   For each in-progress dispatch from the session JSON, compute time-since-last-validation-attempt. A dispatch is STALE if it was last validated (Step 3) > 2h ago AND the lock is still held. Cross-check the dispatch's session JSON `started_utc` and the dispatch file's `implementation_results_hash` (presence indicates completion was emitted at least once). Output: dispatch ID, time held past completion, hold-the-lock reason (from Step 4 conditions), action hint (`/falcon status <id> for detail; arbitrate per hold reason`).

4. Print the grouped output per the format sketch in [`COMMANDS.md`](./COMMANDS.md#falcon-list-pending) `### /falcon list-pending`. Empty categories shown with `(0)` so the user knows they were checked.
5. Total count at the bottom: `Total: <N> items across <M> dispatches.`

Read-only; no side effects. The command does not write to any dispatch file, does not release any lock, does not tear down any cron, does not modify bd state. Use freely as often as needed.

Compatible with autopilot — when run on a branch with active `--autopilot` dispatches, the output complements the inline STATUS UPDATE blocks from the `--watch` cron by aggregating across dispatches (the watch cron emits per-dispatch; `/falcon list-pending` emits per-branch-or-global).

### /falcon retro --branch <name>

Branch-keyed stash synthesis for `/wrapup` audit. Reads the entire autopilot-relevant history for a branch and emits a structured retro block summarizing autonomous vs human-driven activity. User invokes explicitly at wrapup time; not auto-invoked.

Implementation:

1. Derive sanitized branch: `git rev-parse --abbrev-ref HEAD | tr '/' '-'` (or use the explicit `<name>` argument; sanitization is the same).
2. Read the branch-keyed stash file at `.claude/tmp/falcon-reports-<sanitized-branch>.yaml`. If absent, treat as empty (no completions recorded for this branch yet).
3. Glob all dispatch files at `.claude/tmp/falcon-dispatch-*.yaml`. Filter to those whose `branch` field matches `<name>` (the unsanitized form for the filter — the dispatch file stores the original branch).
4. For each matching dispatch file, parse:
   - `amendments[]` — count entries by `label` (`"auto-issued:cron"` vs other) and by `response_source` (`"autonomous"` vs `"/<agent>"` vs `"user-relay"` vs `"steering-cron"`)
   - `intent_acknowledged_utc` (non-null = either auto-ack cron or manual relay landed)
   - `auto_amendment_count` + `amendment_budget` — flag entries where the budget was hit
   - `release_on_merge` — flag dispatches that used the merge-poll cron
   - Validation `standards_firings[]` from the implementation_results section (if present in stash)
5. Read the stash file (if present) for the cross-dispatch synthesized fields: union of `discovered_beads[]`, `decisions_for_human[]`, `blockers_for_steering_session`, `epic_progress`.
6. Emit a structured retro block wrapped in v6.5.3 labeled-copy convention:

    ## RETRO SUMMARY — branch <name> at <UTC ISO8601>

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    Branch:           <name>
    Sanitized:        <sanitized-branch>
    Dispatches:       <count>
    Stash file:       .claude/tmp/falcon-reports-<sanitized-branch>.yaml (<present|absent>)

    ## Autopilot metrics

    Intent auto-acks (cron):             <N>  (of <total intents emitted>)
    Manual intent acks:                  <N>
    Amendments auto-issued (cron):       <N>  (of <total amendments>)
    Amendments via advisor (/<agent>):   <N>
    Amendments manual:                   <N>
    Budget-exhausted dispatches:         <N>  (of <release-on-merge-armed>)
    Release-on-merge dispatches:         <N>

    ## DAR resolutions

    High-stakes DARs:                    <N>  (resolved: <Y>, pending: <N-Y>)
    Low-stakes DARs (proceeded):         <N>
    Advisor-forked decisions:            <N>  (by /<agent>: <breakdown>)

    ## Standards firings (across dispatches)

    <one-line per firing with rule_ref + dispatch_id>

    ## Discovered work

    <one-line per discovered_bead with id + title + originating dispatch>

    ## Per-dispatch detail

    <dispatch_id> (<bead_ids>):
      - Status:      <session_status>
      - Crons armed: <slug list from *_cron_id fields>
      - Amendments:  <count> (auto: <X>, manual: <Y>)
      - Commits:     <count>
      - Outcome:     <closed | in_progress | blocked | deferred>

    <next dispatch...>

    ## Cron Telemetry (v7.1.0, fdev-lbq.30)

    <Per-cron aggregate across all dispatches on the branch. Source:
    cron_telemetry field on each dispatch file. Format: per-row
    fires / silent / useful / signal_density = useful / fires × 100.
    Dispatches predating v7.1.0 (no cron_telemetry field) are
    excluded from aggregation and reported on a final line.>

    Cron        Fires   Silent  Useful  Signal density
    watch       <N>     <N>     <N>     <N>%
    autoack     <N>     <N>     <N>     <N>%
    amend       <N>     <N>     <N>     <N>%
    worker      <N>     <N>     <N>     <N>%
    merge       <N>     <N>     <N>     <N>%
    (dispatches without telemetry: <N>)

    Target signal density (per v7.1.0 design intent): > 30% per cron.
    If autoack or amend signal density < 30%, autopilot calibration
    may need tuning: shrink bucket cadences, sharpen phase multipliers,
    or revisit the Step 0 early-exit predicates.

    ## Calibration notes

    <any "amendment budget too tight" / "auto-ack defer rate high" / "advisor
    forked more than expected" / "cron signal density below 30%" patterns
    the synthesizer detects>

    For incorporation into wrapup: feed RETRO SUMMARY block into the
    autopilot_audit section of the wrapup synthesis.
    ~~~
    ═══ END COPY ═══

7. Output ONLY the retro block — no inline narrative. The user pipes it to `/wrapup` or includes it directly in the changelog/retro entry.

Use case: at end-of-session wrapup, run `/falcon retro --branch <current-branch>` to get the autopilot audit data. `/wrapup` (v2.4+) reads this block automatically when present in the steering session's recent transcript; older `/wrapup` versions require the user to paste the block into their wrapup synthesis prompt.

### /falcon enable-autopilot --profile=<name>

Bulk-uncomment `# PROJECT —` gates in `.claude/rules/falcon-autopilot.md` per a chosen profile (`conservative` | `standard` | `aggressive`). Replaces the manual block-finding friction that the refuse-on-MVM design intentionally creates. Profile is REQUIRED; no default. See COMMANDS.md `### /falcon enable-autopilot --profile=<name>` for the user-facing spec; this section is the implementation walkthrough.

Implementation:

1. **Preconditions check.**
   - Verify `.claude/rules/falcon-autopilot.md` exists. If not, refuse with: "falcon-autopilot.md not found; run /falcon create-rules first to scaffold it."
   - Verify `--profile=<name>` is present and is one of `conservative`, `standard`, `aggressive`. If missing or invalid: refuse with the three valid values + a one-line description of each.

2. **Load profile definition from AUTOPILOT-RULES.md.**
   The canonical profile definitions live in [`AUTOPILOT-RULES.md`](./AUTOPILOT-RULES.md#profile-definitions) `### Profile definitions` inside AUTOPILOT-RULES.md `## falcon-autopilot.md Template`. Parse the chosen profile's `(section, item, detection)` tuple list.

3. **Evaluate detection conditions per item.**
   Each profile item has a detection condition expressed as one of:
   - `file_exists: <path>` — true if the file exists in the project
   - `file_grep: <path>, pattern: <regex>` — true if the file exists AND the pattern matches at least one line
   - `directory_has_files: <path>, pattern: <glob>` — true if the directory contains at least one file matching the glob
   - `always` — unconditionally true (used for `safe_to_amend_denylist` items which apply universally)
   - `skill_installed: <skill-slug>` — true if `.claude/skills/<slug>/SKILL.md` exists (for `advisor_delegation` entries)

   Evaluate each item's condition against the project. Build the diff: list of `(section, item, before-line-numbers, after-content)` for items whose condition is true AND are currently commented.

4. **Print the diff (always — both dry-run and live).**
   Group by section. Per item, show: section header, item name, detection condition that triggered it, and the rule_ref / description from the falcon-autopilot.md content. Total count at bottom.

5. **Handle `--dry-run`.**
   If `--dry-run` is set: exit after printing the diff. No write, no backup, no confirmation.

6. **Confirmation prompt (unless `--force`).**
   Print: `"Apply N changes across M sections? (y/n)"`. If user answers `n` or anything other than `y`/`yes`: exit without writing.

7. **Backup before write.**
   Copy the current `.claude/rules/falcon-autopilot.md` to `.archive/falcon-autopilot-<UTC-ISO8601-timestamp>.md`. Create `.archive/` if it doesn't exist. The archive is the recovery path if the profile uncomments more than intended.

8. **Apply the diff via position-anchored regex (per development-standards.md §3.18).**
   This is a multi-block multi-line YAML-in-markdown mutation; surgical-line edits would collide on shared indentation across sections (the candidate-rule `Bulk YAML mutations: scope by block position, not by indentation alone`). Use the proven pattern:
   a. Read the entire file into memory.
   b. For each target section (e.g., `## 1. SAFE_TO_ACK_INTENT predicate`): find the section header line number; identify the `# PROJECT —` subsection start within that section; identify the target item by name within the subsection.
   c. For each line in the target item's block (the item name line + all indented continuation lines until the next `# - <item>` or end of subsection), strip the `# ` prefix.
   d. Preserve all UNIVERSAL lines, all OTHER PROJECT items not in the diff, all section headers, all blank lines, and all surrounding markdown structure.
   e. Write the modified content back atomically.

9. **Print summary.**
   - Archive path
   - Count of items uncommented per section
   - Per-section summary (which items were uncommented, which were skipped due to failed detection)
   - Suggested next steps:
     - `Review .claude/rules/falcon-autopilot.md to confirm activated gates.`
     - `Run /falcon work beads <id> --autopilot to test (or --auto-ack alone first).`
     - `To revert: cp <archive-path> .claude/rules/falcon-autopilot.md`

**Mutation correctness:** the position-anchored pattern is the same one development-standards.md §3.18 prescribes for `docs/findings/*.yaml` bulk mutations. The risk is identical: a regex like `^# - <item_name>:` matches in multiple `# PROJECT —` blocks across sections if scoping isn't section-anchored. Solution: find the section header first, then only operate after that line and before the next section header.

**No re-commenting.** This command only uncomments. To downgrade a profile (e.g., aggressive → standard), the user must manually re-comment the items the new profile leaves out, OR restore from the `.archive/` backup. The asymmetry is intentional — autopilot deactivation should be a conscious manual step, not a one-liner.

**Compatible with `/falcon create-rules --force`** — if the user re-runs create-rules with `--force` after enabling autopilot, the existing activations are CLOBBERED by the fresh template. They'd need to re-run `/falcon enable-autopilot --profile=<name>` to re-activate. This is correct behavior (create-rules is the reset path).

### /falcon respawn-fresh <dispatch-id> [--reason=<reason>] [--force]

**v7.0.0+ sub-command.** Spawn a FRESH `--bg` worker that continues an existing dispatch where the prior worker died. The new worker picks up via the three-step recovery sequence (push unpushed commits → close landed-but-bd-open beads → reconcile in-progress amendments) before resuming normal lifecycle. Forensic record of replaced workers persists in `worker_bg_prior_sessions[]`.

Implementation:

1. **Preconditions check.**
   - Read the dispatch file at `.claude/tmp/falcon-dispatch-<dispatch-id>.yaml`. Refuse with `dispatch <id> not found` if absent.
   - Refuse if `session_status: complete` — the dispatch is finished; respawn doesn't make sense. Suggest `/falcon release <id>` for cleanup or `/falcon work beads <bead-ids> --bg` for a fresh dispatch.
   - Refuse if `worker_dispatch_mode != "bg"` — respawn-fresh only applies to background-session dispatches. Suggest manually re-pasting the dispatch prompt for `--via-paste` workers OR re-spawning `--paste` workers via the original mechanism.
   - Validate `--reason=<code>` if provided; accept any of the five canonical codes (`context-exhausted`, `safety-tripped`, `stuck-looping`, `manual-replace`, `crashed`). Omitted → default to `manual-replace`.

2. **Append prior session to forensic record.**

   Atomically append to `worker_bg_prior_sessions[]` (preserve all other fields):

   ```yaml
   worker_bg_prior_sessions:
     - session_id: "<current worker_bg_session_id>"
       spawned_utc: "<original spawn time from dispatch.created_utc OR the prior entry's replaced_utc + 1s gap>"
       replaced_utc: "<now>"
       reason: "<reason from --reason or 'manual-replace'>"
   ```

   The list is read-only forensic record; never re-claimed. Each entry preserves spawn timestamp + replacement timestamp + reason code so `/falcon retro --branch` can audit respawn patterns.

3. **Compute respawn generation N.**

   Count existing `worker_bg_prior_sessions[]` entries (now including the one just appended). N = count + 1 (first respawn = -r2; second = -r3; etc. — initial dispatch is N=1, no suffix).

4. **Set `dispatch_continuation: true` on the dispatch file.**

   Atomic write. The successor worker's bootstrap reads this field to detect continuation mode and execute the three-step recovery sequence (see PROTOCOL.md `### --bg dispatch mode (v7.0.0)` for the bootstrap's continuation branch).

5. **Spawn the successor.**

   Invoke via Bash:

   ```
   claude --bg --name "falcon-<dispatch-id>-r<N>" "<bootstrap from REFERENCE.md template>"
   ```

   Inherit the same worktree-isolation flag the original dispatch used (read from `worker_bg_isolation`; respect the same default-fallback chain). The bootstrap substitutes `dispatch_id` + `repo_path` (same template as initial dispatch).

6. **Capture new session ID; update `worker_bg_session_id`.**

   Atomic write to the dispatch file (preserve all other fields). The `worker_bg_session_id` field is the source of truth for "the current worker"; consumers (`claude attach`, `claude logs`, `/falcon status`, etc.) read this field.

7. **Confirmation-gated `claude stop` (per quartermaster R1).**

   Print the suggested `claude stop <old-id>` command. Unless `--force` was passed, prompt:

   ```
   Prior session <old-id> may still be alive (reason: <reason>).
   Stop it? [y/n]
   ```

   - On `y`: run `claude stop <old-id>`. The prior process is freed; the entry stays in `worker_bg_prior_sessions[]` for forensics.
   - On `n` (or anything other than `y`/`yes`): skip the stop call. Prior process may continue running until idle-supervisor-stop. Forensic entry unchanged.
   - On `--force`: skip the prompt entirely, run `claude stop <old-id>` unconditionally.

   This prompt is the user's last chance to record notes before the prior session's state is cleared. Particularly important for `reason: context-exhausted` and `reason: stuck-looping` where the prior session may still be alive and making slow progress.

8. **Print summary.**

   ```
   Respawned dispatch <id> as session <new-short-id> (generation: <N>).

   Prior session:     <old-id> (reason: <reason>)
   New session name:  falcon-<dispatch-id>-r<N> (look for this row in `claude agents`)
   Worktree:          <isolated under .claude/worktrees/<id>/ | shared with main checkout>
   Continuation mode: dispatch_continuation: true set; successor will execute
                      three-step recovery sequence (push commits → close landed
                      beads → reconcile amendments) before resuming lifecycle.

   Monitor: claude agents
   Peek:    Space on the row when state flips to 'Needs input'
   Detail:  claude attach <new-short-id>
   ```

**safety-tripped advisory (REQUIRED implementer constraint per development-standards.md §3.15):** if `reason: safety-tripped`, the prior session's log may contain the triggering content. The implementer MUST NOT read `claude logs <prior-session-id>` in a new session for forensics — the log may reproduce the triggering content and re-trip the safety filter in the reader's session. The safe recovery path is `/falcon respawn-fresh` + capturing the `reason` code; deeper forensics on the contaminated content is out-of-band and operator-responsibility. The forensic record (timestamp + reason code in `worker_bg_prior_sessions[]`) is sufficient for retro analysis without reading logs.

**AUP-recovery decision tree (v7.0.1, fdev-lbq.7):** when a worker reports AUP (Anthropic Usage Policy) trip — almost always surfaced as `reason: safety-tripped` — operators face a choice between `/falcon respawn-fresh` and spawning a fresh dispatch with a hardened init_prompt. The correct choice depends on what tripped the filter:

```
Worker reports session_status: failed, reason: safety-tripped
│
├── Source of trip: init_prompt content (skill prompts, autopilot rules, or
│   project rules referenced from init_prompt)
│   → DO NOT /falcon respawn-fresh — it preserves the init_prompt, which is
│     what tripped the filter; the fresh session would just trip again on
│     the same content.
│   → SPAWN A FRESH DISPATCH:
│       1. Edit the offending init_prompt content (PROTOCOL.md, REFERENCE.md
│          init_prompt template, .claude/rules/*.md, OR project rules pulled
│          in via the rules reference).
│       2. Commit the harden.
│       3. Open a fresh dispatch on the same bead set:
│            /falcon work beads <bead-spec>
│          The new dispatch loads the now-hardened init_prompt.
│       4. Manually close the old dispatch via /falcon release <old-id>
│          (the old worker is dead; no auto-release will fire).
│
└── Source of trip: bead body content (the work itself referenced sensitive
    material — e.g. customer PII in a bug-repro script, security incident
    details in a postmortem doc, sensitive credential names)
    → /falcon respawn-fresh IS appropriate after rewriting the bead body.
      The init_prompt is fine; only the bead content needs hardening.
    → SEQUENCE:
        1. Identify the offending bead body section (without reading the
           prior session's logs — those carry the contaminated content).
        2. Edit the bead via bd update <id> --body-file <hardened.md> or
           equivalent.
        3. /falcon respawn-fresh <dispatch-id> --reason=safety-tripped
           — the new worker loads the (preserved) init_prompt + the now-
           hardened bead body.
```

**Default if uncertain:** prefer the SPAWN FRESH DISPATCH path. It's the higher-overhead but lower-risk option — a hardened init_prompt is permanently safer for future dispatches, whereas respawn-fresh only fixes the current dispatch.

`claude respawn <id>` (the CLI primitive — restart same session) is the WRONG choice for AUP recovery in either case — it restarts the prior conversation including any contaminated state.

**Compatibility:**

- All five autopilot crons (Phases 1-5) continue to work — they read/write the dispatch file regardless of which worker session is current.
- Auto-ack-resume guard (v6.9.0) naturally handles the continuation case (skips intent-confirm if `intent_acknowledged_utc` is non-null, which it will be after a respawn since the prior worker presumably acked already).
- `/falcon list-pending` (per quartermaster R2) gains a respawn-loop heuristic: if `worker_bg_prior_sessions[]` has N >= 2 entries AND current `session_status` is still `active` after the stale threshold, flag as `STALE (respawn-N)` with stronger emphasis (catches runaway respawn loops where successive respawns aren't fixing the underlying problem).
- `/falcon retro --branch` (per quartermaster R2) breaks down respawn-count by reason category: `context-exhausted` → "bead-decomposition signal"; `safety-tripped` → "content-policy gap signal"; `stuck-looping` → "environment/tool issue signal"; `manual-replace` + `crashed` → "operator-discretion / Claude Code stability signal".

---

## Amendments Workflow

> **Dead-worker constraint (read this first):** Amendments require the worker session to still be active. If the worker's browser tab, terminal, or remote session was closed after initial completion, amendments CANNOT be sent. In this case, you MUST re-dispatch as a new bead. Do NOT attempt to write amendments to the dispatch file and expect a dead session to pick them up. Release the lock promptly once amendments are no longer needed, because holding the lock past worker death blocks future dispatches for no benefit.

An amendment is a follow-up instruction from steering to a **still-active** worker, written into the dispatch file's `amendments[]` array. The worker resumes, executes the amendment, writes results back to the same array entry.

**Steering side (adding an amendment):**

1. Set `session_status: amendments_pending` in the dispatch file
2. Read the dispatch file (`yq` or direct Read)
3. Append a new entry to `amendments[]`:

   ```yaml
   amendments:
     - amendment_id: "amend-01"
       created_utc: "<ISO8601>"
       request: |
         <paragraph from steering describing what to do, why, and what
          observable evidence will close the amendment>
       status: "pending"
       worker_response: null
       commits: []
       worker_completed_utc: null
   ```

   Amendment IDs use the format `amend-01`, `amend-02`, etc. (sequential, zero-padded).

4. Write the dispatch file back atomically (append-only — never overwrite an existing amendment entry)
5. Emit the resume trigger to the user wrapped in the v6.5.3 labeled-copy convention:

   ```
   ## AMENDMENT amend-01 — dispatch <dispatch-id> at <UTC ISO8601>

   ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
   ~~~
   check amendments <dispatch-id>

   Amendment amend-01 written to <dispatch-file>. Worker should re-read,
   find pending amendments, and execute per the Amendments Workflow.
   ~~~
   ═══ END COPY ═══
   ```

**Worker side (executing an amendment):**

On resume prompt ("check amendments `<dispatch-id>`"):

1. Re-read the dispatch file
2. Check `session_status` — if `complete`, steering has ended your work; stop. If `amendments_pending`, proceed.
3. Find amendments with `status: "pending"` — there may be multiple if steering queued several
4. For each pending amendment (in order):
   - Set `status: "in_progress"` (write back)
   - Read the `request` field as the binding spec — no intent-confirm pre-flight needed
   - **Check first whether the amendment's intent is already satisfied** (e.g., user pre-edits in worktree already implement the request; a prior amendment already applied this change; the trigger condition no longer holds). If yes → set `status: "satisfied"` with a `worker_response` citing the verification. Skip to next pending amendment.
   - Otherwise: execute the request, within the same file_scope as the original dispatch (raise high-stakes DAR if amendment requires out-of-scope files)
   - Write `worker_response` with observable evidence — NOT just "done"
   - Write `commits[]` with any new commit shas
   - Set `worker_completed_utc` + `status: "completed"`
   - Commit + push if there were code changes
5. Emit the amendment-completion preamble wrapped in the v6.5.3 labeled-copy convention:

   ```
   ## AMENDMENT COMPLETION amend-NN — dispatch <dispatch-id> at <UTC ISO8601>

   ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
   ~~~
   Amendment amend-NN completed at <UTC ISO8601>. Re-read <dispatch-file>.
   <optional one-paragraph preamble citing observable evidence>
   ~~~
   ═══ END COPY ═══
   ```

   For `satisfied`, use `## AMENDMENT SATISFIED amend-NN` as heading + "Amendment amend-NN satisfied at ..." inside the fence.
   For `rejected`, use `## AMENDMENT REJECTED amend-NN` as heading + "Amendment amend-NN rejected at ..." inside the fence.

If an amendment is genuinely impossible (e.g., requires out-of-scope files OR contradicts the original bead), set `status: "rejected"` with a `worker_response` explaining why.

**Amendment status values (canonical):**

- `pending` — steering has written; worker has not started
- `in_progress` — worker has started execution
- `completed` — work performed; commits + worker_response captured
- `satisfied` — amendment's intent is met without action from this branch. Two sub-cases: (i) moot trigger — the condition no longer applies; (ii) already done elsewhere — work was performed outside this amendment cycle. Worker verifies + records evidence in `worker_response`.
- `rejected` — work is impossible / out-of-scope / contradicts original bead; worker explained why

**MUST-set rule:** the worker MUST update each amendment's status to one of `completed`, `satisfied`, or `rejected` before emitting any completion signal. Leaving an amendment in `pending` or `in_progress` at completion time is a worker-discipline lapse that Step 3 step 5 validation will catch.

**DAR Response Writeback Discipline:**

Who writes the `response` field on `out_of_spec_approval_requests[]`?
- If user relays approval/rejection directly to worker tab: worker SHOULD write the response field on action (currently no protocol — worker just acts on the relay-text and the field stays null, leaving a stale-state artifact)
- If autopilot arbitrates: steering writes the response field at arbitration time
- If user relays to steering and steering forwards: steering writes the response field
- Stale-null response field with completed work = worker-discipline lapse (catch this in Step 3 step 5 amendment-status discipline audit)

**When to use amendments vs re-dispatch:**

- Amendment: same file_scope, related to original work, **worker session still active**
- Re-dispatch: new file_scope, design questions remain, **OR worker session ended**

---

## Paste-Fallback Mode (--paste)

For workers on a different machine, browser, or cross-network environment that cannot access `.claude/tmp/`:

When `--paste` is specified:
1. Skip dispatch-file creation and lock registry steps entirely
2. Emit the full init_prompt content as a self-contained paste block (not a "load `<file>`" pointer)
3. Include bead bodies inline (implied `--inline-beads` behavior) since the worker has no bd access
4. The worker returns the YAML report inline in chat rather than writing to the dispatch file
5. Lock registry, amendments protocol, and `session_status` do NOT apply in paste mode
6. Treat as a single-round-trip dispatch: intent → proceed → report (no amendment cycles)
7. Stash the inline YAML report to `.claude/tmp/falcon-reports-<sanitized-branch>.yaml` as a normal stash entry (no lock to release)

Use paste mode as a fallback, not a default.

**v6.7.0 note:** `--paste` is the one mode that still inlines the full Worker Lifecycle + Worker Return Contract + Copy-Paste Emission Convention sections in `init_prompt` (since the worker cannot Read filesystem files). The default + `--sequential` + `--skip-intent` + `--inline-beads` modes use the thin pointer-style template that references the skill files. See REFERENCE.md "## init_prompt Content Template (`--paste` mode: fully inlined)".

---

## Worker Lifecycle (inside the dispatch)

**Canonical reference (v6.7.0+):** as of falcon v6.7.0 the default `init_prompt` template no longer embeds this lifecycle verbatim — it points workers here. This section IS the binding spec for workers under the default + `--sequential` + `--skip-intent` + `--inline-beads` modes. Only the `--paste` mode init_prompt inlines this section directly (since paste-mode workers cannot Read filesystem files). See REFERENCE.md "## init_prompt Content Template (default: thin / pointer-style)".

1. Branch verify: `git fetch origin && git checkout <branch> && git rev-parse --abbrev-ref HEAD` (MUST return the declared branch name — stop on mismatch)

   **`--bg` mode + worktree isolation (v7.0.0+):** if the worker is running in a Claude Code worktree (under `.claude/worktrees/<id>/`), the worktree branch does NOT contain `.claude/tmp/` (it's an ephemeral directory in the main checkout). The worker MUST resolve dispatch-file paths via the dispatch file's `repo_path` field (absolute path to the main checkout), NOT via a relative `.claude/tmp/` reference. The bootstrap prompt provides `repo_path` literally. Read the dispatch file at `<repo_path>/.claude/tmp/falcon-dispatch-<dispatch-id>.yaml`; verify the loaded file's `dispatch_id` matches the bootstrap-provided ID before any state change (cheap mitigation for the residual concern that steering code logic could pass a wrong ID).

   **`/rename` for session identity (v7.0.0+; canonical mechanism for `--via-paste` and `--paste` modes):** as the first action after branch verify, run the `/rename falcon-<dispatch-id>` slash command so the session shows up correctly in `claude agents` (when available) and on the prompt bar. This replaces the prior tmux/printf/IDE-bullet terminal-title approach (which silently failed across most real-world setups — see P5.1 in the v7.0.0 changelog for the failure-mode catalog). `--bg` mode does NOT need this step because `claude --bg --name "falcon-<dispatch-id>"` already sets the session name at spawn time.

2. For each bead: `bd show <id>` to load the full body; confirm `triage:ready`.

2b. **Required Context load (v7.2.0+):** read the dispatch file's `required_context[]` field (populated by steering at Step 2 from each bead's `## Required Context` section per `.claude/docs/work-item-templates.md`). For each entry, `Read` the named `.claude/*.md` file before writing implementation_intent. If a path contains an explicit `§ <anchor>` suffix, that's a doc-author hint to focus on the named section — read with `offset` / `limit` around that section's heading after a first pass to locate it.

   The point is to enter intent-confirm with the same context envelope the steering session would have had at /leroy startup. Workers that skip this step write intents grounded in title-keyword guessing rather than the contracts the bead is bound to preserve.

   If `required_context[]` is empty AND all beads in this dispatch are `cynefin:clear`: skip with no warning (atomic execution is the intended contract).

   If `required_context[]` is empty AND any bead is `cynefin:complicated` / `cynefin:complex`: this is an under-hydration signal — the bead should not have reached `triage:ready` per the readiness checklist. Proceed with execution but during the bead body parse, look for `.claude/*.md` references inline AND track every ad-hoc `.claude/*.md` Read into the worker's `unlisted_context_reads[]` field on the eventual report. Steering's /wrapup will absorb each as a `kind: doc_gap` entry against the originating bead.

3. **Intent confirmation (default; skip if `skip_intent: true` directive present, OR if `intent_acknowledged_utc` is already non-null on this resume — see auto-ack-resume guard below):** emit single-paragraph intent including one-sentence approach. Write to `implementation_intent` field AND emit wrapped in labeled-copy convention. STOP, await steering "proceed" ack.

   **Dispatch-identity header (v6.12.1; mandatory):** prepend a 2-line identity header INSIDE the INTENT fence, ABOVE the intent paragraph: `Working dispatch <id> on branch <branch>` on the first line, `Beads: [<bead-id>: "<title>", ...]` on the second (titles abbreviated to ~40 chars each if long). Rationale: when the user has multiple worker tabs open across concurrent dispatches, this is the last visual checkpoint where a wrong-dispatch-paste shows up — if the dispatch ID, branch, or bead titles don't match what the user expected for this tab, they reject the paste with a corrective revision instead of typing `proceed <id>`. The header is doc-only; steering does not parse the INTENT format. See REFERENCE.md "## Copy-Paste Emission Convention" and "## Dispatch Prompt Template" for the format example. This is Safeguard B of the worker-side wrong-paste-detection design (Safeguard A — `worker_session_id` field + claim mechanic — is tracked in example-r3q9 for separate Phase-N treatment).

   **Auto-ack-resume guard (v6.9.0):** before emitting the intent paragraph, re-read the dispatch file and inspect `intent_acknowledged_utc`. If it is already non-null AND no commits have landed for this dispatch yet (the worker can confirm by `git log origin/<branch> --oneline --since=<dispatch.created_utc>` returning zero entries from this worker's commit set), the auto-ack cron has already acked an intent on a prior session — skip the intent-confirm pause entirely and proceed straight to Step 4 (`bd update -s in_progress`). This prevents double-prompt confusion when a worker session restarts mid-dispatch after the cron already wrote `intent_acknowledged_utc`. If `intent_acknowledged_utc` is null OR commits have already landed (intent was acked AND consumed), proceed normally per the unguarded path: emit the intent paragraph, write to `implementation_intent`, await ack.

   **Worker self-poll at intent pause (v7.1.1, `--bg` mode only):** in `--bg` mode, after writing `implementation_intent` and before the STOP-await-ack, arm a self-poll `CronCreate` scoped to the intent-ack wait condition (literal block in CRONS.md `## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)`); CAPTURE the returned cron ID in session memory. The cron prompt — delivered to the worker session as a user-message-style notification when it fires every ~2 min — instructs the worker to re-read the dispatch file and, on observing `intent_acknowledged_utc` non-null, call `CronDelete(captured_id)` and proceed past intent-confirm into claim. This closes the `--bg` wake-gap where steering's `--auto-ack` cron has written the ack but the idle worker never observes it without an external poke. The predicate is intentionally `intent_acknowledged_utc != null` alone (no commit-attribution check): at this pause point, no commits could have landed for this dispatch yet by construction — contrast with the *auto-ack-resume guard* above, which uses a richer predicate because it runs on session resume and must disambiguate against history. Mandatory `durable: false` so the cron dies with the worker session. The self-poll does NOT apply in `--via-paste` / `--paste` modes (operator's `proceed <id>` paste is the wake mechanism). See [`### Worker self-poll at pause points (v7.1.1)`](#worker-self-poll-at-pause-points-v711) above for the full scope guardrail and coordination rationale.
4. For each bead: `bd update <id> -s in_progress`.
5. Implement per the bead's description. Follow project standards.
6. Verify per the bead's Testing Strategy AND project-level verification-gate rules. Verification is a CLOSE gate.
7. If any bead names out-of-band or encapsulator verification: do NOT execute the check yourself — set `verification.out_of_band_required: true` in the report and leave the bead `in_progress`.
8. Commit atomically with `Closes: <id>` in messages. Stage `.beads/issues.jsonl` alongside code (flush via `bd export -o .beads/issues.jsonl` after batch writes).
9. Push the feature branch with `git push` (do NOT open a PR — that stays with the steering session).
10. `bd close <id>` only after Step 6 verification produced observable evidence.
11. Write `implementation_results` to the dispatch file. Compute `sha256(implementation_results_content)` and write to `implementation_results_hash` in the same atomic write.
12. Emit the completion preamble wrapped in the v6.5.3 labeled-copy convention.
13. **Optional amendments cycle:** after emitting completion, check `session_status` on each resume prompt. `amendments_pending` → execute pending amendments. `complete` → work is done.

### Sequential dispatch lifecycle override (v6.4.0)

When the dispatch has more than one bead AND was created with `--sequential`, Steps 4-10 iterate per-bead in declared array order instead of batching:

For each bead in `bead_ids[]` (in array order):

  a. `bd update <id> -s in_progress`
  b. Implement per the bead's description. Inherit context naturally from prior bead(s).
  c. Verify per the bead's Testing Strategy + project verification-gate rules (CLOSE gate).
  d. Commit atomically with `Closes: <id>` in the message — one commit per bead.
  e. Push (`git pull --rebase origin <branch>` first if not already current).
  f. `bd close <id>` only after step c produced observable evidence.
  g. Populate per-bead entry in `implementation_results.beads[]`.
  h. Move to next bead.

Step 11 (write `implementation_results`) runs ONCE at end. Step 12 emits the completion signal ONCE.

**Failure isolation:** if bead N fails (high-stakes DAR, blocked, test regression), STOP iteration. Beads 1..N-1 stay cleanly closed. Bead N reports `outcome: in_progress` or `blocked`. Beads N+1..end report `outcome: deferred` with `outcome_reason: "deferred due to upstream bead <N> failure in --sequential dispatch"`. Set `partial_report: true`.

### DAR protocol (inside the dispatch)

For judgment calls beyond the bead spec, capture as a **DAR (Decision, Alternatives, Recommendation)**:

- **LOW stakes** (reversible, single-file, no contract impact, no sibling-bead impact): pick the recommendation, proceed, document in DAR for human review
- **HIGH stakes** (cross-file, contract-bearing, sibling-bead-affecting, schema/migration, anything in a project standard's "WRONG" example): STOP, document in DAR, return partial report. Do NOT implement.

DAR shape:
- Decision: one sentence framing the choice
- Alternatives: 2–4 distinct paths, each with a one-line trade-off
- Recommendation: which alternative + why (one sentence)
- Stakes: low | high
- Action taken: "proceeded with recommendation" | "stopped pending arbitration"

**When to stop and report instead of pressing on:**
- High-stakes DAR
- Bead requires unresolved architectural decision → file a decision bead, capture as DAR, partial report
- Test failure surfaces a regression in a different bead's work → stop, do not paper over with one-off interop
- Any project-specific tripwire your reading of `.claude/rules/` surfaces → STOP IMMEDIATELY

**Worker self-poll at DAR pause (v7.1.1, `--bg` mode only):** when a worker stays alive waiting on a DAR `response` field (rather than partial-reporting per the HIGH-stakes path), arm a self-poll `CronCreate` scoped to the response-non-null wait condition (literal block in CRONS.md `## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)`); CAPTURE the returned cron ID in session memory. The cron prompt — delivered to the worker session as a user-message-style notification when it fires every ~3 min — instructs the worker to re-read the dispatch file and, on observing the DAR entry's `response` field non-null, call `CronDelete(captured_id)` and incorporate the response. Mandatory `durable: false`. Self-poll does NOT apply in `--via-paste` / `--paste` modes. See `### Worker self-poll at pause points (v7.1.1)` in the `--bg dispatch mode` section above for scope guardrail and coordination rationale.

---

## Background-Agent Dispatch Limitation

The Agent tool surface is NOT available to a background general-purpose agent that itself spawns sub-agents. Workaround: the background agent uses `claude --print` subprocess fan-out instead.

Worth noting because bulk-validation protocols assume Agent tool fan-out; that assumption fails when the steering session is itself a background agent.
