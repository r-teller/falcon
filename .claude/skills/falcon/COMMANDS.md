---
parent: SKILL.md
version: 7.0.0
---

# Falcon — Commands and Flags Reference

> **Status legend:** `✓` implemented and active · `⊘` proposed (design only, not yet wired into the skill)
>
> For lifecycle protocol: see [`PROTOCOL.md`](./PROTOCOL.md).
> For schemas and templates: see [`REFERENCE.md`](./REFERENCE.md).

---

## Dispatch Commands

### `/falcon work beads <spec>` ✓

Primary dispatch command. Ships a bead set to a remote worker session.

`<spec>` is one of:

- **Range:** `foo.7-19` → expands to foo.7, foo.8, …, foo.19 (remote session filters to those that exist + are claimable)
- **List:** `foo.7,foo.12,bar.52`
- **Single:** `foo.7`
- **Label query:** `label:foo` → all beads matching the label

---

### `/falcon release <dispatch-id>` ✓

Manual lock release for a single dispatch. The normal path is **automatic** (Step 4 auto-release when validation + cognitive audit both pass). Use this only as an escape hatch when:

- A worker session abandoned its dispatch without returning a report
- You want to release a lock that the auto-release path declined (e.g., a held DAR was resolved externally)

---

### `/falcon release-session <session-id>` ✓

Bulk release for a dead worker session. Removes every entry from the named session's `falcon_dispatches[]`, updates each dispatch file's `session_status: complete`, and archives the session JSON to `.archive/falcon-sessions/<session-id>-<timestamp>.json`. Refuses if any dispatch in the session has `status: in_progress` AND last-active < 1h ago (likely still alive — use individual `/falcon release` instead).

---

### `/falcon list-locks` ✓

Show all active dispatches across all session files, grouped by dispatch. Use before `/falcon release` to confirm what you'd be releasing.

---

### `/falcon list-sessions` ✓

Show all session JSON files with their dispatches + last-activity timestamps + staleness warnings (> 2h since last transcript activity = STALE). Groups by session so you can see which dispatches a session holds at a glance. Use before `/falcon release-session` to confirm scope.

---

### `/falcon list-pending` ✓

Scan all active dispatch files and print a flat grouped list of items waiting on human action. Designed for the return-from-AFK workflow under `--autopilot`: you've been away, you want a single command that tells you what needs your attention before you can do anything else.

Categories surfaced (each with action hints):

1. **HIGH-STAKES DAR awaiting arbitration** — `decisions_for_human[]` entries with `stakes: high` AND `action_taken: stopped pending arbitration` AND no recorded resolution
2. **OUT-OF-SPEC APPROVAL REQUESTS** — `out_of_spec_approval_requests[]` entries with `response: null`
3. **OUT-OF-BAND VERIFICATION pending** — beads with `verification.out_of_band_required: true` and bd state still `in_progress`
4. **AMENDMENT BUDGET EXHAUSTED** — dispatches where `auto_amendment_count >= amendment_budget` AND lock still held
5. **PR CLOSED UNMERGED** — dispatches with `release_on_merge: true` where the merge cron's last snapshot recorded `pr_state: CLOSED` (PR abandoned; user must release or re-dispatch)
6. **STALE LOCKS** — dispatches whose Step 4 hold-the-lock condition has been met for > 2h (auto-release declined; manual arbitration overdue)

Each entry includes a one-line action hint (`/falcon release <id>` / `bd close <id>` / `manual amendment` / etc.). Total count at the bottom. Empty categories shown with `(0)` so you know they were checked.

Output sketch:

```
Pending human action (across N active dispatches):

  HIGH-STAKES DAR awaiting arbitration (1):
    dispatch abc123 (bead example-foo.5):
      DAR: "Should X be Y or Z?"
      Recommendation: <one-line>
      Action: arbitrate inline, then /falcon release abc123 OR amend

  OUT-OF-SPEC APPROVAL REQUESTS (0):

  OUT-OF-BAND VERIFICATION pending (2):
    dispatch def456 (bead example-bar.3): "Robert verifies http://localhost:3000/foo returns 200"
    dispatch ghi789 (bead example-baz.1): "replay-validator PASS for hash ..."

  AMENDMENT BUDGET EXHAUSTED (1):
    dispatch jkl012 (auto_amendment_count=3, amendment_budget=3)
    Action: issue manual amendments OR /falcon release jkl012

  PR CLOSED UNMERGED (0):

  STALE LOCKS (> 2h held past validation pass) (0):

Total: 4 items across 4 dispatches.
```

Fits the existing `list-locks` / `list-sessions` read-and-present pattern. Read-only; no side effects.

For implementation walkthrough: see [`PROTOCOL.md`](./PROTOCOL.md#falcon-list-pending) `### /falcon list-pending`.

**Recommended cadence:** run at the start of any session that touches a branch with active dispatches (`/leroy` or `/gogogo` skills can wire this in as part of session-startup orientation). Also run after any `--watch` cron STATUS UPDATE block that mentions a new DAR or amendment-pending state.

---

### `/falcon status <dispatch-id>` ✓

One-shot status query (manual equivalent to a single cron fire). Returns:

- `session_status`, `implementation_intent` presence, `implementation_results_hash` presence
- bd state for each bead in the dispatch
- commit count on branch since dispatch opened
- amendment count + open DAR count
- watch cron ID and cadence (if one is armed)

Use when you don't have a watch cron armed but want a quick read.

For implementation detail: see [`PROTOCOL.md`](./PROTOCOL.md#falcon-status-dispatch-id).

---

### `/falcon retro --branch <name>` ✓

Synthesize the branch-keyed stash (`.claude/tmp/falcon-reports-<sanitized-branch>.yaml`) AND all dispatch files matching the branch into an autopilot audit. Counts:

- auto-acked intents (auto-issued:cron label)
- auto-issued amendments (auto-issued:cron label)
- advisor forks per agent (response_source: /<agent>)
- autonomous arbitrations (response_source: autonomous)
- DAR resolutions (high-stakes vs low-stakes)
- budget-exhausted dispatches
- release-on-merge dispatches
- standards firings + discovered work + per-dispatch detail

Emits a `RETRO SUMMARY` block (per the v6.5.3 labeled-copy convention) — no inline narrative. Output is consumed by `/wrapup` (v2.4+ reads it automatically when present in the steering transcript; older `/wrapup` requires the user to paste the block).

Use at `/wrapup` time to assess whether autopilot bounds were calibrated correctly for the session — e.g., budget too tight (high exhaustion rate), auto-ack defer rate high (gates too strict), advisor forked more than expected (whitelist coverage gaps).

For implementation walkthrough: see [`PROTOCOL.md`](./PROTOCOL.md#falcon-retro---branch-name) `### /falcon retro --branch <name>`.

---

### `/falcon release-cron <dispatch-id>` ✓

Tear down the watch/autopilot cron associated with a dispatch. Looks up matching crons by the `falcon-watch-<dispatch-id>` slug convention (Phase 1; future phases extend the prefix set) via `CronList`, `CronDelete`s each match, removes the sidecar snapshot file at `.claude/tmp/falcon-watch-<dispatch-id>-state.json`, and nulls `watch_cron_id` in the dispatch file.

Does NOT release the dispatch lock — use `/falcon release <dispatch-id>` for that. Useful when a cron survived past its dispatch lifecycle (user cancelled the dispatch manually but forgot the cron) or when the snapshot file got out of sync.

For implementation detail: see [`PROTOCOL.md`](./PROTOCOL.md#falcon-release-cron-dispatch-id).

---

### `/falcon respawn-fresh <dispatch-id> [--reason=<reason>] [--force]` ✓

**v7.0.0+ sub-command.** Spawn a FRESH `--bg` worker that continues an existing dispatch where the prior worker died (context exhausted, safety-tripped, stuck/looping, or operator-chosen replacement). The new worker picks up via a three-step recovery sequence that pushes any unpushed commits, closes beads with landed-but-bd-still-open work, and reconciles in-progress amendments — all before resuming normal lifecycle.

**Behavior:**

1. Read the dispatch file at `.claude/tmp/falcon-dispatch-<dispatch-id>.yaml`. Refuse if not found OR if `session_status: complete` (the dispatch is finished; respawn doesn't make sense). Refuse if `worker_dispatch_mode != "bg"` (respawn-fresh only applies to background-session dispatches).
2. Append the current `worker_bg_session_id` + spawn timestamp + now + reason to `worker_bg_prior_sessions[]` (read-only forensic record; never re-claimed).
3. Spawn new `claude --bg --name "falcon-<dispatch-id>-r<N>"` where N counts the respawn generation (initial dispatch = no suffix; first respawn = `-r2`; second = `-r3`; etc.). The bootstrap-prompt template substitutes `dispatch_id` + `repo_path` exactly as for an initial dispatch.
4. Update `worker_bg_session_id` to the new short ID.
5. Set `dispatch_continuation: true` on the dispatch file so the new worker's bootstrap detects continuation mode and executes the three-step recovery sequence (see PROTOCOL.md `### --bg dispatch mode (v7.0.0)` for the bootstrap branch).
6. **Confirmation-gated `claude stop` (per quartermaster R1):** print the suggested `claude stop <old-id>` command alongside a one-line confirmation prompt: `Prior session <id> may still be alive (reason: <reason>). Stop it? [y/n]`. On `y`, run `claude stop <old-id>` to free the dead session's process. On `n` (or anything else), skip — the prior entry stays in `worker_bg_prior_sessions[]` for forensics either way. Skip the prompt entirely if `--force` is passed.
7. Print summary: new session ID + suggested `claude agents` row name + reason for respawn.

**Reasons (informational, not enforcement):**

- `context-exhausted` — worker hit context budget; fresh context needed
- `safety-tripped` — worker session got contaminated by safety-filter refusal or similar
- `stuck-looping` — worker in non-productive state
- `manual-replace` — user-initiated for any other reason (model swap, etc.)
- `crashed` — supervisor lost the session unexpectedly
- omit `--reason` → defaults to `manual-replace`

**safety-tripped advisory (per development-standards.md §3.15):** if `reason: safety-tripped`, the prior session's log may contain the triggering content. Do NOT read `claude logs <prior-session-id>` in a new session for forensics — the log may reproduce the triggering content and re-trip the safety filter in the reader's session. The safe recovery path is `/falcon respawn-fresh` + capturing the `reason` code for retro; deeper forensics on the contaminated content is out-of-band and operator-responsibility. The forensic record (timestamp + reason code in `worker_bg_prior_sessions[]`) is sufficient for retro analysis without reading logs.

**When to invoke:**

- Context exhaustion: `claude agents` peek shows the worker is stalling on context-full errors; the worker can't make progress
- safety-tripped: worker hit a content-policy refusal it can't recover from; `claude logs <id>` shows the refusal in recent output (read in OPERATOR'S OWN judgment — see §3.15 advisory)
- Stuck/looping: worker is repeating the same tool call without progress; `claude logs <id>` shows repetition
- Manual: any other reason (model swap, environmental change, etc.) where a fresh context is preferable to attaching to the existing session

**When NOT to invoke:**

- Worker is just slow — `claude attach` and observe; respawn loses context productivity
- Worker is supervisor-stopped (idle > 1hr) — `claude attach` auto-resumes it with full state intact; no respawn needed
- Worker is waiting on intent ack — peek and reply directly; no respawn needed

**Flags:**

- `--reason=<code>` — optional informational reason; defaults to `manual-replace`. Captured in `worker_bg_prior_sessions[].reason` for forensics + `/falcon retro --branch` audit categorization.
- `--force` — skip the `claude stop` confirmation prompt. Suitable for scripted invocation; not recommended interactively.

**Compatibility with autopilot:**

- All five autopilot crons continue to work — they read/write the dispatch file regardless of which worker session is current.
- Auto-ack-resume guard (v6.9.0) naturally handles the continuation case (skips intent-confirm if `intent_acknowledged_utc` is non-null, which it will be after a respawn since the prior worker presumably acked already).
- `/falcon list-pending` (v6.12.2) gains a "respawn generations: N" indicator per dispatch (informational, not a pending-human item).
- `/falcon retro --branch` (v6.12.0) counts respawns per dispatch (autopilot stress indicator — many respawns signals autopilot calibration tuning needed).

For implementation walkthrough: see [`PROTOCOL.md`](./PROTOCOL.md#falcon-respawn-fresh-dispatch-id-reasonreason) `### /falcon respawn-fresh <dispatch-id>`.

---

### `/falcon create-rules` ✓

Populate `.claude/rules/falcon-autopilot.md` with the project-specific gate spec consumed by autopilot flags (`--auto-ack`, `--auto-amend`, `--advisor`, `--amendment-budget`). The file is a forward-looking spec — the autopilot flags themselves are `⊘` (proposed), but the gate file can be authored, reviewed, and iterated on independently so it's ready when the autopilot consumer lands.

The command writes the template from [`REFERENCE.md`](./REFERENCE.md#falcon-autopilotmd-template) to `.claude/rules/falcon-autopilot.md`. The template has six sections:

1. **`SAFE_TO_ACK_INTENT` predicate** — 4-gate spec for auto-acking worker intent paragraphs
2. **`SAFE_TO_AMEND` whitelist** — universal defaults + project-specific safe amendments
3. **`SAFE_TO_AMEND` denylist** — universal defaults + project-specific forbidden amendments
4. **Bead-type-specific cognitive audit hints** — "any project-binding concern the AC didn't gate on?" prompts
5. **Advisor delegation policy** — when to fork to `/quartermaster` (or other registered advisors) for ambiguous decisions
6. **Default amendment budget** — recommended `--amendment-budget` per bead type

Universal sections (those that apply to every falcon-using project) are pre-populated and marked `UNIVERSAL — do not edit`. Project-specific sections contain placeholders + examples drawn from the project's existing `.claude/rules/*.md` files (the command reads `standards.md`, `development-standards.md`, `workflow-execution.md`, `workflow-agents.md` to seed sensible defaults).

**Flags:**

- `--force` — overwrite an existing `.claude/rules/falcon-autopilot.md`. Default: refuse if the file exists (avoid clobbering hand-tuned gates).
- `--dry-run` — print the file contents to stdout without writing. Use to preview before committing to the placement.
- `--bead-types <list>` — comma-separated list of bead-type tags the project uses (e.g., `chore,bug,feature,decision,spike,clj-pair,7hq-pair`). Default: `chore,bug,feature,decision` (universal types). Project-specific types get a templated cognitive-audit hint stub.

**Behavior:**

1. Check the project for `.claude/rules/falcon-autopilot.md`:
   - If present AND no `--force`: print the existing file's location + a one-line summary of what's already in it, then exit without writing. Suggest `--force` if user wants to overwrite.
   - If present AND `--force`: archive the existing file to `.archive/falcon-autopilot-<timestamp>.md`, then write the new one.
   - If absent: write the new file.
2. Read the project's existing rule files to seed project-specific sections:
   - `.claude/rules/standards.md` — surface any standards mentioning autopilot-relevant gates (wave-pack mutation, paired-bead contracts, multi-agent coordination)
   - `.claude/rules/development-standards.md` — surface § references that should be cited in cognitive audit hints
   - `.claude/rules/workflow-execution.md` — surface "Persist work-tracking state" requirements that should be in `SAFE_TO_AMEND` whitelist
   - `.claude/rules/workflow-agents.md` — surface multi-agent fan-out conventions
3. Write the templated file with universal sections fixed and project-specific sections pre-populated with detected `.claude/rules/` references (left as comments for the user to confirm before activating).
4. Print: file path + a one-line summary of what's in each section + suggested next step (`Open .claude/rules/falcon-autopilot.md and review the project-specific sections; uncomment the gates you want active.`).
5. **`bypassPermissions` setup check (v7.0.0+; non-blocking).** After writing the rules file, check:
   - `.claude/settings.json` for `bypassPermissions: true` (project-level)
   - `~/.claude/settings.json` for `bypassPermissions: true` (user-level)

   If NEITHER is true, emit a non-blocking warning (does NOT refuse):

   ```
   Note: workers dispatched via --bg will pause for permission prompts unless
   bypassPermissions is enabled. To allow unattended autopilot operation:

     Add `"bypassPermissions": true` to .claude/settings.json (project-level)
     OR `~/.claude/settings.json` (user-level)

   This is required for --autopilot AFK mode. It is OPTIONAL for --via-paste
   and --paste modes, and for single-shot --bg dispatches you plan to babysit.
   See COMMANDS.md `--bg` flag for the full context.
   ```

   The check is informational; `/falcon create-rules` proceeds normally regardless of the warning. Rationale: `bypassPermissions` is a settings-file value, not a CLI dispatch-time switch — it belongs alongside other one-time autopilot setup actions, not at activation time. If either settings file has `bypassPermissions: true` already, emit a one-line confirmation (`bypassPermissions: true detected in <project|user> settings.json — --autopilot AFK mode supported`) so the user sees the check ran.

**When to invoke:**

- Once per project, the first time you intend to use autopilot flags (or plan to soon).
- Re-run with `--force` after major rule-file changes if the project-specific seed defaults have drifted.
- Never invoke as part of an autopilot dispatch itself — the file should be reviewed by a human before any autopilot run consumes it.

**Caveat:** the autopilot consumer (`--auto-ack`, `--auto-amend`, `--worker-cron`, `--advisor`, `--amendment-budget`, `--autopilot`) is `⊘` in this falcon version. Authoring `falcon-autopilot.md` is a forward-looking spec that doesn't change current behavior — it gives the autopilot rollout a concrete project target when implemented.

> **Note (v6.12.0+):** the autopilot consumer flags listed above are now all `✓` implemented as of the v6.8.0-v6.12.0 rollout. The caveat above describes the v6.6.0-era state when `/falcon create-rules` was originally added. The file it produces is no longer "inert" — uncommenting `# PROJECT —` blocks activates real cron behavior. Use `/falcon enable-autopilot --profile=<name>` (v6.14.0) to bulk-uncomment per a chosen profile instead of finding the right blocks manually.

---

### `/falcon enable-autopilot --profile=<conservative|standard|aggressive>` ✓

Bulk-uncomment `# PROJECT —` gates in `.claude/rules/falcon-autopilot.md` per a chosen profile. Replaces the manual "find the right blocks to uncomment in a 449-line file" friction that the refuse-on-MVM design (Phase 2 v6.9.0 precedent for write-bearing autopilot) creates by requiring the user to opt every gate in explicitly.

Profile is REQUIRED — there is no default. The command refuses to operate without an explicit `--profile=<name>`. Forces a conscious choice between three bounded levels of autopilot autonomy.

**The three profiles:**

- **`conservative`** — minimum-viable autopilot. Activates ALL `safe_to_amend_denylist` items (denylist is safety; more is better). Activates at most 1-2 `safe_to_ack_intent.project_gates` items (highest-priority intent-time risks). Leaves `safe_to_amend_whitelist` PROJECT items COMMENTED (universal whitelist only — `rephrase_existing_test`, `missing_regression_check`, `missing_bd_export`, `missing_wave_pack_pin`). Tight `amendment_budget_defaults` (chore: 1, all features: 1, decision/spike: 0). Use when first activating autopilot on a new project and you want bounded amendment surface while you build trust.

- **`standard`** — recommended for general use. Activates ALL §3 denylist items + project-seeded §1 gates + project-seeded §2 whitelist items where their detection conditions hold + project-seeded §4 cognitive audit hints + §5 advisor delegation (if quartermaster or other registered skill exists). Per-bead-type `amendment_budget_defaults` from the template's recommended values (chore: 2, bug: 1, feature_small: 2, feature_medium: 3, feature_large: 5, decision/spike: 0, paired: 1, epic: 0). Use after running conservative for a sprint or two and confirming the autopilot is well-calibrated.

- **`aggressive`** — maximum autopilot autonomy. Activates EVERY `# PROJECT —` item across all 6 sections, subject only to the detection conditions (items whose detection condition fails stay commented). Generous `amendment_budget_defaults` (chore: 3, feature_small: 3, feature_medium: 5, feature_large: 8, others same as standard). Use only after running standard for several sprints and you've verified the autopilot does not over-issue amendments OR forks too many ambiguous decisions to the advisor.

**Detection-driven uncommenting**: profiles aren't blind bulk-uncomment. Each profile defines a list of `(section, item, detection-condition)` tuples. The detection condition is a file-existence or grep check against the project (e.g., `example_project_gate` activates only if `.claude/fair-play-policy.md` exists; `missing_wave_pack_version_pin_bump` activates only if `development-standards.md` references `wave_pack_version`). Items whose condition fails are left commented even at aggressive. This prevents activating gates that reference standards the project doesn't have.

For the canonical profile definitions (the source of truth for what each profile activates per section): see [`REFERENCE.md`](./REFERENCE.md#profile-definitions) `### Profile definitions` inside `## falcon-autopilot.md Template`.

**Flags:**

- `--profile=<conservative|standard|aggressive>` — REQUIRED. No default.
- `--dry-run` — print the diff that would be applied without writing. Shows per-section the items that would flip from commented to uncommented, with the detection condition that triggered each.
- `--force` — skip the pre-write confirmation prompt. Use for scripted invocation (e.g., project-bootstrap automation). NOT recommended for interactive use; the confirmation prompt is the per-gate comprehension checkpoint.

**Behavior:**

1. Refuse if `.claude/rules/falcon-autopilot.md` does not exist. Suggest `/falcon create-rules` first.
2. Refuse if `--profile=<name>` is missing OR not one of the three known profiles.
3. Read the rules file; parse to identify all `# PROJECT —` blocks across the 6 sections.
4. For each candidate item from the chosen profile, evaluate its detection condition. Build the diff (items to uncomment).
5. Print the diff (always — for both dry-run and live).
6. If `--dry-run`: exit. No write, no backup.
7. If NOT `--force`: prompt `"Apply N changes across M sections? (y/n)"`. If `n`, exit.
8. Archive the existing `.claude/rules/falcon-autopilot.md` to `.archive/falcon-autopilot-<timestamp>.md`.
9. Apply the diff via position-anchored regex (per development-standards.md §3.18 — scope mutations by section header, not by indentation alone). Strip `# ` prefix from each targeted line.
10. Print summary: archive path + count of items uncommented per section + suggested next steps.

**Examples:**

```
# Preview what standard profile would activate
/falcon enable-autopilot --profile=standard --dry-run

# Activate conservative interactively (with confirmation prompt)
/falcon enable-autopilot --profile=conservative

# Activate aggressive in a bootstrap script (skip confirmation)
/falcon enable-autopilot --profile=aggressive --force
```

**When to use:**

- First-time autopilot setup, after `/falcon create-rules`, when you want to enable autopilot without manually finding the right blocks across all 6 sections.
- Profile upgrade — re-run with a different profile to switch from conservative → standard or standard → aggressive. The archive-before-write pattern preserves the prior state.
- Profile downgrade is also supported, but you'll need to manually re-comment items that the new profile leaves out (the command only uncomments; it doesn't re-comment).

For implementation walkthrough: see [`PROTOCOL.md`](./PROTOCOL.md#falcon-enable-autopilot---profilename) `### /falcon enable-autopilot --profile=<name>`.

---

## Dispatch Flags

### `--bg` ✓

**Default dispatch mode as of v7.0.0.** Steering invokes `claude --bg --name "falcon-<dispatch-id>" "<short-bootstrap>"` via the Bash tool; the supervisor process spawns the worker as a detached background session observable via `claude agents`. No paste-into-tab required.

Why this is the default: the mapping between falcon's dispatch lifecycle and Claude Code's background-session model is essentially 1:1, with ergonomic wins — single agent-view UI monitors all dispatches, real-time `Working / Needs input / Completed` states, built-in peek-and-reply for INTENT-confirm pauses (Space → read INTENT → type `proceed <id>` → Enter), session persistence across machine sleep, no shell-quoting concerns for the dispatch prompt (passed as CLI arg pointer-style).

**Eager environment detection + auto-downgrade.** Before any dispatch action, steering runs:

1. **Version gate (cheapest, fails fast):** `claude --version` parsed; require >= 2.1.139. On failure: emit one-line note `--bg requires Claude Code >= 2.1.139 (detected: <version>). Auto-downgrading to --via-paste. Upgrade Claude Code OR pass --via-paste explicitly to suppress this message.` Proceed with `--via-paste` dispatch.
2. **`disableAgentView` settings check:** read `.claude/settings.json` first (project-level wins); fall back to `~/.claude/settings.json` (user-level). If `disableAgentView: true` in either: emit `agent-view disabled by <project|user> settings.json. Auto-downgrading to --via-paste.` Proceed with `--via-paste` dispatch.
3. **Mode override:** if user explicitly passed `--via-paste` or `--paste`, skip the checks and use the explicit mode.
4. **Success path:** emit one-line confirmation `Dispatch mode: --bg (agent-view v<version> detected)` so the user sees the default mode + the version that drove the choice.

Detection runs eagerly (Step 2 of PROTOCOL.md, before the dispatch file is written) so failures don't half-create state.

**Bootstrap-prompt pattern (extends v6.7.0 thin init_prompt design).** The CLI argument to `claude --bg` is a SHORT bootstrap (~5 lines) pointing at the dispatch file using `repo_path`-anchored absolute paths. The full multi-line dispatch prompt content stays in the dispatch file's `init_prompt` field, eliminating shell-quoting concerns for multi-line content with backticks/quotes/etc. The bootstrap MUST include: (1) the literal `dispatch_id`; (2) the absolute `repo_path`; (3) an instruction to VERIFY `dispatch_id` matches once loaded. For the full template + substitution variables + rationale: see [`REFERENCE.md`](./REFERENCE.md#bootstrap-prompt-template-v700) `### Bootstrap Prompt Template (v7.0.0)`.

**Worker observability:**

```
Monitor:        claude agents (look for row 'falcon-<dispatch-id>')
Peek INTENT:    in agent view, Space on the row when state flips to 'Needs input'
Detail:         claude attach <short-id>
Logs:           claude logs <short-id>
```

Steering does NOT auto-open `claude agents` for the user (could steal terminal focus); user opens it themselves in any terminal. `claude agents` monitors ALL dispatches in one view (not per-dispatch).

**Compatibility with autopilot flags:** all five autopilot crons (Phases 1-5) continue to operate unchanged because they read/write the dispatch file on disk — they don't care HOW the worker was spawned. STATUS UPDATE / AMENDMENT AUTO-ISSUED / etc. emissions surface in both the steering session's chat AND the worker session's chat (visible via `claude attach` or peek).

**`--worker-cron` is a no-op in `--bg` mode.** The auto-ack-resume guard (v6.9.0) handles amendment pickup within the same persistent background session; no separate worker-side cron needed. The `--worker-cron` flag stays explicit for `--via-paste` / `--paste` users who depend on it. See `--autopilot` flag below for the macro-expansion note.

**Mutual exclusion:** `--bg` and `--paste` cannot co-exist (they select different worker spawn paths). Steering refuses with an informative error if both flags are set (or `--via-paste` and `--paste`); suggests picking one based on shared-filesystem availability. The auto-downgrade path from `--bg` to `--via-paste` is internal — it does not conflict with explicit `--via-paste`.

**Recommended for autopilot:** when running `--autopilot` (AFK), enabling `bypassPermissions: true` in `.claude/settings.json` (project-level) OR `~/.claude/settings.json` (user-level) prevents permission prompts from stalling background sessions. See `/falcon create-rules` below for the setup-time check.

For wiring + detection sequence + worktree-isolation handling: see [`PROTOCOL.md`](./PROTOCOL.md#--bg-dispatch-mode-v700) `### --bg dispatch mode (v7.0.0)`.

---

### `--via-paste` ✓

The renamed paste-into-tab dispatch mode (equivalent to falcon ≤ 6.14.0 default behavior). Steering emits the standard DISPATCH PROMPT labeled-copy block; user pastes it into a manually-opened Claude Code tab; worker proceeds with the lifecycle.

**Auto-downgrade target.** When `--bg` is the requested mode but the environment-detection check fails (Claude Code version too old, or `disableAgentView: true` in settings), steering automatically downgrades to `--via-paste` and emits the standard paste-block alongside an auto-downgrade note explaining which check failed.

**Use when:**
- Explicitly preferring manual tab control over agent-view's auto-spawn (some users find tab juggling clearer than agent-view's row UI)
- Claude Code version < 2.1.139 (auto-downgrade target)
- `disableAgentView: true` set in project or user settings (auto-downgrade target)

**Worker-cron still applies.** Unlike `--bg` (where `--worker-cron` is no-op), `--via-paste` benefits from the worker-cron's amendment-pickup polling because the worker session is independent and does not have an auto-resume guard equivalent. `--autopilot` expansion includes `--worker-cron` for this mode.

Lock registry + amendments protocol behave identically to `--bg` (both write to `.claude/tmp/` on shared filesystem).

For lifecycle detail: see [`PROTOCOL.md`](./PROTOCOL.md#--bg-dispatch-mode-v700) `### --bg dispatch mode (v7.0.0)` (which documents both `--bg` and `--via-paste` paths alongside the auto-downgrade logic).

---

### `--bg-isolated` ✓

Force the `--bg` worker into a Claude Code git worktree (under `.claude/worktrees/<id>/`) regardless of the project's `worktree.bgIsolation` setting in `.claude/settings.json`. Per-dispatch override.

**Operational consequence — the `.claude/tmp/` shared-path concern:** when the worker runs in an isolated worktree, the worktree branch does NOT contain `.claude/tmp/` (it's an ephemeral directory in the main checkout, not committed). The worker MUST resolve dispatch-file paths via the dispatch file's `repo_path` field (absolute path to the main checkout), NOT via a relative `.claude/tmp/` reference. The bootstrap-prompt template (see REFERENCE.md `### Bootstrap Prompt Template`) enforces this by including `repo_path` literally in its content.

Use when: you want belt-and-suspenders isolation for a contract-bearing change (the worktree branch keeps the worker's WIP separate from the main checkout's tree until commit/push).

Mutually exclusive with `--bg-no-isolation`.

---

### `--bg-no-isolation` ✓

Force the `--bg` worker to share the main checkout's working tree (no Claude Code worktree). Per-dispatch override of `worktree.bgIsolation`.

Use when: the dispatch needs to read in-flight uncommitted changes from the main checkout, OR you want to minimize disk footprint when running many short dispatches.

Mutually exclusive with `--bg-isolated`.

**Default (neither flag set):** the worker inherits `worktree.bgIsolation` from `.claude/settings.json`; if no setting present, the default is `"auto"` (let Claude Code use its built-in default — currently isolated, but this defers to Claude Code's evolution).

---

### `--sequential` ✓

Opt-in override of the self-conflict check for the **single-worker case**. When set, two or more beads in the spec are ALLOWED to share `file_scope` overlap because one worker handles them in declared order in a single session (inheriting context cleanly, avoiding merge conflicts, saving ~10-20 steering turns vs the 2-dispatch pattern).

CLI list-order is the default execution order; `bd blocked_by` ordering wins if present. Worker handles beads as separate close-cycles (claim → implement → verify → commit with per-bead `Closes: <id>` → close → next).

NOT appropriate when:
- Total worker context budget would exceed ~120 turns (split into separate dispatches for fresh context)
- Failure isolation between beads is more valuable than orchestration savings

---

### `--skip-intent` ✓

Omit the intent-confirm pre-flight; remote proceeds straight from bead lookup to claim. Use when steering is confident the bead is unambiguous (e.g., a small chore with a 5-line change) and wants a single round-trip.

---

### `--inline-beads` ✓

Inline the full bead bodies in the dispatch file's `init_prompt` instead of pointer-style. Use for single-bead dispatches where the prompt benefits from being self-contained without a bd lookup, OR when steering has tweaked the spec for this dispatch only and doesn't want to push the tweak to bd.

---

### `--paste` ✓

**Cross-machine paste-fallback mode.** Use when the worker is on a different machine, browser, or cross-network environment and cannot access `.claude/tmp/`. Steering emits the full init_prompt as a self-contained paste block. Worker returns the YAML report inline in chat rather than writing to the dispatch file. Lock registry and amendment protocol do not apply — treat as a single-round-trip dispatch.

**Distinct from `--via-paste`:** `--paste` assumes NO shared filesystem (the entire init_prompt must travel in the paste-block; lifecycle + return contract sections inlined). `--via-paste` assumes shared filesystem (same machine, paste-to-tab UX preferred over `--bg` agent-view; dispatch file at `.claude/tmp/` is the source of truth). Pick `--paste` ONLY when cross-machine; use `--via-paste` otherwise.

**Mutual exclusion:** `--paste` cannot coexist with `--bg` or `--via-paste` — steering refuses with an informative error citing the shared-filesystem requirement.

**v6.7.0 inline-expansion:** as of v6.7.0, the default init_prompt template is thin (pointer-style — workers Read PROTOCOL.md + REFERENCE.md from disk for the lifecycle, return contract, and labeled-copy convention). Paste-mode is the documented exception: the init_prompt expands those pointers inline so the worker has the full binding spec without filesystem access. Expect the paste-mode init_prompt to be ~200-300 lines vs the default ~70-90 lines. See REFERENCE.md "## init_prompt Content Template (`--paste` mode: fully inlined)".

---

### `--watch[=Nm]` ✓

Arm a steering-side cron in **report-only mode** (no auto-ack, no auto-amend, no auto-release). The cron fires every N minutes (default 10m for Phase 1; tuned by `--cron-cadence`) and emits a status block inline ONLY when state changed since the last fire. Cron self-cancels when the dispatch reaches a terminal state (`session_status: complete`).

Use when: "I want to step away and come back to a summary, but I want to make every decision myself."

**v6.8.0 Phase 1 — foundational artifact.** Every subsequent autopilot flag (`--auto-ack`, `--auto-amend`, `--worker-cron`) extends the cron prompt template established here. See [`REFERENCE.md`](./REFERENCE.md#autopilot-cron-prompt-templates) `## Autopilot Cron Prompt Templates ### --watch cron prompt template` for the template body and [`PROTOCOL.md`](./PROTOCOL.md#--watch-mode-autopilot-observability-foundation-v680) `### --watch mode` for the wiring.

**Minimum-viable mode:** when `.claude/rules/falcon-autopilot.md` exists but every `# PROJECT —` section is commented (the post-`/falcon create-rules` default), `--watch` runs using universal gates only. It does NOT refuse — report-only mode does not need the project gates at all (those become load-bearing under `--auto-ack` and later phases that gate writes).

---

### `--auto-ack` ✓

Autonomous intent acknowledgement. When the worker emits an intent paragraph, the steering cron applies the `SAFE_TO_ACK_INTENT` 4-gate predicate. If it passes (no new scope, no cross-dispatch conditional, intent matches Changes Needed, no open DAR), the cron auto-writes `intent_acknowledged_utc` and emits the `proceed <dispatch-id>` block for paste to the worker.

All post-completion decisions (amendments, release) still surface inline for user action.

Use when: "trust the worker's strategy choice but I want to vet anything heavier."

**v6.9.0 Phase 2 — first write-bearing autopilot cron.** `--auto-ack` is the second entry in the cron prompt template registry (after `--watch` from Phase 1). It uses the same prefix-match teardown convention (`falcon-autoack-<dispatch-id>`) and same sidecar-snapshot pattern (`.claude/tmp/falcon-autoack-<dispatch-id>-state.json`). Default cadence: 5m (shorter than `--watch`'s 10m because intent windows are brief). Override with `--cron-cadence Nm`.

When co-armed with `--watch`, two independent crons run side-by-side; the prefix-match teardown handles both together. See [`PROTOCOL.md`](./PROTOCOL.md#--auto-ack-mode-autopilot-intent-acknowledgement-v690) `### --auto-ack mode` for the wiring + cross-cron coordination notes, and [`REFERENCE.md`](./REFERENCE.md#--auto-ack-cron-prompt-template-v690) `### --auto-ack cron prompt template` for the template body.

**Refuse-on-MVM (NOT minimum-viable mode like `--watch`).** Because `--auto-ack` is write-bearing (it writes `intent_acknowledged_utc` which the worker treats as authorization to skip the intent-confirm pause), the cron REFUSES to operate when `.claude/rules/falcon-autopilot.md` either does not exist or has every `# PROJECT —` section under `## 1. SAFE_TO_ACK_INTENT predicate` commented. The refuse-block names the specific gate the user should uncomment. Universal gates alone are NOT sufficient — the project must explicitly opt in.

**Worker-side complement:** worker checks `intent_acknowledged_utc` on each resume prompt; if already acked and no commits landed yet, worker skips intent-confirm pause and proceeds straight to claim. See PROTOCOL.md Worker Lifecycle Step 3 auto-ack-resume guard.

---

### `--auto-amend` ✓

Auto-issue amendments within the project's `SAFE_TO_AMEND` whitelist (defined in `.claude/rules/falcon-autopilot.md § 2`). Higher-risk than `--auto-ack`; requires a project-confirmed whitelist (universal-only is NOT sufficient — see refuse-on-MVM below).

Universal whitelist (conservative defaults): rephrase-existing-test, missing-regression-check, missing-bd-export, missing-wave-pack-pin.

Universal denylist: new-AC-item, new-file, new-endpoint, architectural-change.

`--amendment-budget N` should be set to a safe limit before `--auto-amend` is used in production.

**v6.10.0 Phase 3 — third entry in the cron prompt template registry.** Uses slug `falcon-amend-<dispatch-id>` and sidecar `.claude/tmp/falcon-amend-<dispatch-id>-state.json`. Default cadence 5m (matches `--auto-ack`; amendment evaluation needs the worker's completion signal). Override with `--cron-cadence Nm`.

When co-armed with `--watch` and/or `--auto-ack`, the three crons run side-by-side as independent single-responsibility templates. `/falcon release-cron` tears down all three via prefix-match. See [`PROTOCOL.md`](./PROTOCOL.md#--auto-amend-mode-amendment-budget-halt-v6100) `### --auto-amend mode + --amendment-budget HALT` for wiring and [`REFERENCE.md`](./REFERENCE.md#--auto-amend-cron-prompt-template-v6100) `### --auto-amend cron prompt template` for the template body.

**Refuse-on-MVM (REQUIRED).** Carries the Phase 2 precedent for write-bearing autopilot flags. `--auto-amend` is the most write-bearing flag in the rollout (issued amendments cause the worker to write code). The cron REFUSES when `.claude/rules/falcon-autopilot.md` is missing OR has every `# PROJECT —` item under `## 2. SAFE_TO_AMEND whitelist` commented. The refuse-block names a specific whitelist item the user should uncomment.

**Budget HALT semantics:** when `auto_amendment_count >= amendment_budget`, the `--auto-amend` cron emits one `AMENDMENT BUDGET EXHAUSTED` block (first fire only) and stops auto-issuing for the rest of the dispatch. The `--watch` and `--auto-ack` crons continue uninterrupted. Only `auto-issued:cron`-labeled amendments count against the budget; manual amendments are exempt.

---

### `--autopilot` ✓

Full bundle for AFK dispatch. Expands to: `--auto-ack --auto-amend --worker-cron --watch`.

**`--bg`-mode behavior (v7.0.0+):** when the effective dispatch mode is `--bg` (the v7.0.0 default), `--worker-cron` in the macro expansion is a SILENT NO-OP — steering does not emit the worker-cron setup paste-block and the worker session does not arm a `falcon-worker-` cron. The auto-ack-resume guard (v6.9.0; PROTOCOL.md Worker Lifecycle Step 3) handles amendment pickup naturally because the worker is a persistent background session that re-reads the dispatch file on every active turn. Steering still arms its THREE crons (`falcon-watch-`, `falcon-autoack-`, `falcon-amend-`) as documented. **Amendment-propagation latency caveat:** without a worker-cron, the worker picks up amendments on its next active turn (which may be triggered by a user peek/reply or an autopilot cron's STATUS UPDATE) rather than on a predictable cron cadence. This is NOT a regression from `--via-paste` UX (the user had to wait for the worker tab to poll); document as a known interaction in PROTOCOL.md `### --bg dispatch mode`.

**`--via-paste` / `--paste` behavior:** the original v6.11.0 macro expansion applies — steering arms three crons AND emits the worker-cron setup paste-block; the worker arms a `falcon-worker-` cron alongside the dispatch prompt. `--worker-cron` is fully active in these modes.

Steering arms THREE crons in its own session (`falcon-watch-`, `falcon-autoack-`, `falcon-amend-`) and emits TWO paste blocks for the worker tab:

1. **Standard dispatch prompt** — the normal worker-onboarding block (per [`REFERENCE.md`](./REFERENCE.md#dispatch-prompt-template) `## Dispatch Prompt Template`)
2. **Worker-cron setup paste-block** — instructions for the worker session to arm its own `falcon-worker-<dispatch-id>` cron (per [`REFERENCE.md`](./REFERENCE.md#--worker-cron-setup-paste-block-v6110) `### --worker-cron setup paste-block`)

User pastes both into the worker tab in order. The worker session reads the dispatch file, arms its cron via `CronCreate`, and writes `worker_cron_id`. Four crons then run concurrently and coordinate via atomic writes to the dispatch file.

Use when: "I'm going AFK and authorized everything safe to proceed without me."

For wiring + four-cron coordination detail + teardown coverage: see [`PROTOCOL.md`](./PROTOCOL.md#--autopilot-mode-full-afk-bundle-v6110) `### --autopilot mode (full AFK bundle, v6.11.0)`.

**Prerequisites** (the macro REFUSES on first cron fire if not met):

- `.claude/rules/falcon-autopilot.md` is committed AND has at least one `# PROJECT —` item uncommented under BOTH `## 1. SAFE_TO_ACK_INTENT predicate` (for `--auto-ack`) AND `## 2. SAFE_TO_AMEND whitelist` (for `--auto-amend`). The `--watch` and `--worker-cron` crons do NOT have refuse-on-MVM and would still run, but the autonomous decision-making is empty if 2 of 3 steering crons refuse.
- `--amendment-budget N` is set to a safe cap (use the `falcon-autopilot.md § 6` recommended defaults per bead type).

---

### `--worker-cron` ✓

Alongside the steering dispatch prompt, emit a canonical worker-cron-setup block for the user to paste into the worker tab. The worker cron polls its dispatch file for `session_status: amendments_pending` on each fire; when found, it executes pending amendments per the Amendments Workflow and emits the amendment-completion preamble.

Without `--worker-cron`, auto-issued amendments (from `--auto-amend`) sit unread in the dispatch file until the user manually relays `check amendments <dispatch-id>` to the worker tab.

Implied by `--autopilot`.

**`--bg`-mode no-op (v7.0.0+):** when the effective dispatch mode is `--bg`, `--worker-cron` is a SILENT NO-OP. The worker is a persistent Claude Code background session; the auto-ack-resume guard (v6.9.0; PROTOCOL.md Worker Lifecycle Step 3) re-reads the dispatch file on every active turn, so amendments are picked up on next interaction without a separate cron. The flag stays explicit for `--via-paste` and `--paste` users who depend on the polling behavior; no formal deprecation in v7.0.0. Revisit formal deprecation in v7.1.0 or v8.0.0 based on usage data.

**v6.11.0 Phase 4 — first worker-side cron.** Phases 1-3 ran crons in the steering session; this is the first cron that runs in the WORKER session. Steering's `CronList` cannot see worker-session crons, so:

- Slug: `falcon-worker-<dispatch-id>` (follows the prefix-match convention for consistency, but discoverable only from the worker session)
- The worker writes its `CronCreate`-returned ID to `worker_cron_id` on the dispatch file — that field is steering's source of truth for worker-cron existence (`/falcon status` reads it)
- `/falcon release-cron` (running in steering) tears down ONLY steering-side crons; worker-cron teardown requires either the worker session naturally ending (`durable: false` means the cron dies with the session) OR a manual teardown paste-block into the worker tab
- Default cadence: 3 minutes (faster than steering's 5m default for amendment issuance because the worker needs to clear `amendments_pending` quickly). Override with `--cron-cadence Nm` (applies to all armed crons — steering and worker — so they fire at compatible intervals).

**No refuse-on-MVM for `--worker-cron`.** Unlike Phases 2-3, this cron does not write to the gate file or evaluate any project gates. It only picks up and executes amendments that already exist in `amendments[]`. Those amendments were either auto-issued (gated by Phase 3's refuse-on-MVM upstream) or manually issued (user-authorized). The worker cron executes already-gated work; it does not gate writes itself.

For wiring + setup paste-block + template body: see [`PROTOCOL.md`](./PROTOCOL.md#--autopilot-mode-full-afk-bundle-v6110) `### --autopilot mode` (the wiring is shared with the macro) and [`REFERENCE.md`](./REFERENCE.md#--worker-cron-cron-prompt-template-v6110) `### --worker-cron cron prompt template` + `### --worker-cron setup paste-block`.

---

### `--advisor=<agent>` ✓

When autopilot's policy gate returns "defer" (decision is ambiguous — not clearly auto-approve or clearly reject), fork to the named project agent for a second opinion before falling back to human defer.

Example: `--advisor=quartermaster` delegates to the `/quartermaster` skill for project-standards review of ambiguous amendment decisions. Every fork is recorded in the dispatch file as `response_source: /quartermaster` for audit (the per-amendment `response_source` field added in v6.12.0).

**v6.12.0 wiring** — `--advisor=<agent>` is NOT a separate cron. It extends the `--auto-ack` and `--auto-amend` cron evaluation paths: when the existing cron encounters an ambiguous decision AND the project's `advisor_delegation` policy in `.claude/rules/falcon-autopilot.md § 5` matches the decision shape, the cron invokes the named agent via the Skill tool and uses the recommendation as the auto-decision input. If the advisor's recommendation falls within `safe_to_amend_whitelist` (for amendments) or passes `safe_to_ack_intent` gates (for intent), the cron auto-issues/acks with `response_source: /<agent>` annotation. Otherwise surfaces inline.

Sets the `advisor: "<agent-name>"` field on the dispatch file at dispatch time. The cron templates check this field; null = no advisor configured, ambiguous decisions default to user-relay path.

For wiring + advisor-extension blocks (appended to the `--auto-ack` and `--auto-amend` templates): see [`REFERENCE.md`](./REFERENCE.md#--auto-ack-advisor-extension-v6120) `#### --auto-ack advisor-extension` and `#### --auto-amend advisor-extension`.

Advisors honor their own `refuses` lists in `falcon-autopilot.md § 5` — e.g., `quartermaster.refuses` includes fair-play-policy questions and scoring-semantics calls, which always defer to human regardless of the policy match. The advisor refuses such forks; the cron then defers to user per the normal path.

---

### `--amendment-budget N` ✓

Hard cap on the number of amendments the autopilot may auto-issue before entering HALT mode. After N auto-issued amendments, the `--auto-amend` cron emits one `AMENDMENT BUDGET EXHAUSTED` block and stays silent on amendment evaluation for the rest of the dispatch.

Counts only `auto-issued:cron`-labeled amendments; user-issued (or steering-relayed) amendments do not decrement the budget. The `--watch` and `--auto-ack` crons continue uninterrupted after budget exhaustion — only amendment auto-issuance is halted.

Recommended values per bead type (defaults seeded by `/falcon create-rules` into `.claude/rules/falcon-autopilot.md § 6`): chore 2, bug 1, feature_small 2, feature_medium 3, feature_large 5, decision/spike 0 (defer all judgment to user), clj_pair / 7hq_pair 1 (sibling-bead interaction is brittle), epic 0.

Sets the `amendment_budget` field on the dispatch file at dispatch time. Meaningless without `--auto-amend` (the budget HALT check is inside the `--auto-amend` cron template).

For detail: see [`PROTOCOL.md`](./PROTOCOL.md#--auto-amend-mode-amendment-budget-halt-v6100) `### --auto-amend mode + --amendment-budget HALT`.

---

### `--cron-cadence Nm` ✓

Override the default cron cadence. Defaults vary by flag (Phase 1: `--watch` defaults to 10m, balancing observability latency against cache-cost; future Phase 2 `--auto-ack` defaults to 5m per the cache-cost analysis). Use shorter (e.g., `2m`) for tight feedback loops on quick-iteration bugs; longer (e.g., `15m`) for long-running content/template work where 10-minute polling is wasteful.

Folds into whichever cron is being armed (Phase 1: only `--watch`; future phases extend coverage).

---

### `--release-on-merge` ✓

Defer lock release until the PR merges, rather than at validation pass. Keeps the lock held across the validation → review → merge gap so a follow-up dispatch cannot accidentally claim overlapping files before the PR lands.

Use when: "I want the lock held during PR review for safety."

**v6.12.0 wiring** — `--release-on-merge` is a NEW separate single-responsibility cron `falcon-merge-<dispatch-id>` (not folded into `--watch`, to keep that cron report-only per the Phase 1 contract). The merge cron polls `gh pr view --json state --head <branch>` every 15 minutes by default (longer than the write-bearing crons because PR merges are low-frequency state changes). On `state: MERGED`, the cron sets `session_status: complete` on the dispatch file, which triggers the normal auto-release path in Step 4 + self-cancellation across all other crons for this dispatch.

Sets `release_on_merge: true` AND `merge_cron_id: <id>` on the dispatch file. Step 4 (Stash for Wrapup + Auto-Release) reads `release_on_merge: true` as a new hold-the-lock condition (added in v6.12.0).

**No refuse-on-MVM.** The merge cron does not evaluate project gates; it only observes external state (PR merge in GitHub) and writes a single status transition. The "gate" is the PR review process itself.

**Usable standalone** without `--watch`, `--auto-ack`, or `--auto-amend` — useful for paranoid lock-release on a single-bead dispatch touching contract-bearing files where lock-overlap during the review → merge gap is unacceptable.

For wiring + cron template body: see [`PROTOCOL.md`](./PROTOCOL.md#--release-on-merge-mode-v6120) `### --release-on-merge mode` and [`REFERENCE.md`](./REFERENCE.md#--release-on-merge-cron-prompt-template-v6120) `### --release-on-merge cron prompt template`.

---

### `--dry-run` ✓

Print what the dispatch + cron would look like without writing the dispatch file, registering the lock, or scheduling the cron. Shows:

- Resolved bead set (IDs + titles + triage states)
- Derived `file_scope` (directories + files; union for `--sequential`)
- Lock-registry check result (overlap vs clean) — performed read-only; no entry registered
- Autopilot policy effects (which flags would fire — Phase 1: `--watch` cron cadence + offset preview; future phases: `SAFE_TO_ACK_INTENT` gate preview, `SAFE_TO_AMEND` preview, `--amendment-budget` cap)
- Cron prompt body (if `--watch` / `--autopilot` co-set) — the literal string `CronCreate` would have received

No dispatch file is written; no lock is registered; no cron is scheduled. Use when previewing autopilot effects on a bead you're not sure is well-scoped, or to verify file_scope before committing to a multi-bead dispatch.

For implementation detail: see [`PROTOCOL.md`](./PROTOCOL.md#--dry-run-mode) `### --dry-run mode`.

---

## Flag Bundles

| Shorthand | Expands to |
|---|---|
| `--autopilot` | `--auto-ack --auto-amend --worker-cron --watch` |
| `--autopilot --advisor=quartermaster` | adds `/quartermaster` fork for ambiguous decisions |
| `--watch --auto-ack` | semi-autonomy: status pings + auto-ack intent, defer all post-completion to user |

---

## Examples

### Example 1 — Basic dispatch (current behavior)

```
/falcon work beads example-73sz
```

Dispatch written; dispatch prompt emitted for paste to worker tab. Worker follows the full lifecycle: branch verify → intent-confirm → claim → implement → verify → commit → push → close → report. All decisions (ack, amendment, release) require manual user action.

---

### Example 2 — Sequential paired beads

```
/falcon work beads example-clj.40,example-7hq.40 --sequential
```

One worker handles both beads in declared order (clj.40 first, then 7hq.40). File scope is the union of both. Useful for recipe + patch pairs where the second bead inherits context from the first.

---

### Example 3 — Skip intent for an unambiguous chore

```
/falcon work beads example-sbgo --skip-intent
```

Worker proceeds directly from bead lookup to claim, skipping the intent-confirm pause. Single round-trip. Use when the bead is a small, unambiguous chore with a 5-line change.

---

### Example 4 — Watch only (status pings, no autonomy)

```
/falcon work beads example-73sz --watch
```

Dispatch written as normal. Steering arms a cron polling the dispatch file every 5min. Output is REPORT-ONLY: "still active / DAR pending / amendment pending / worker complete". All decisions still require user paste. Cron self-cancels when dispatch reaches terminal state.

Use when: "I want to step away for an hour and come back to a summary, but I want to make every call myself."

---

### Example 5 — Semi-autonomous (auto-ack only)

```
/falcon work beads example-73sz --auto-ack
```

Cron auto-arms (same as `--watch`). When worker emits intent, cron applies `SAFE_TO_ACK_INTENT` 4-gate. If passes: auto-writes `intent_acknowledged_utc` + emits `proceed <dispatch-id>` block for paste to worker. Everything else (amendments, release) still surfaces inline for user action.

This eliminates the intent-confirm stall (typically ~80min) for well-scoped dispatches without yielding control over post-completion decisions.

---

### Example 6 — Full autopilot (AFK)

```
/falcon work beads example-73sz --autopilot
```

Expands to: `--auto-ack --auto-amend --worker-cron --watch`. Emits BOTH the steering dispatch prompt AND a worker-cron-setup block for the user to paste into the worker tab. Full bidirectional autopilot: steering auto-acks intent + auto-issues whitelisted amendments + auto-releases on validation pass; worker auto-picks-up amendments from dispatch file without manual relay.

User sees: completion summary on return, OR inline interrupt for hard fail / out-of-whitelist gap / DAR-defer.

---

### Example 7 — Autopilot with advisor delegation

```
/falcon work beads example-clj.41,example-7hq.41 --sequential --autopilot --advisor=quartermaster
```

Full autopilot AND when a DAR or amendment decision is ambiguous (not clearly auto-approve or clearly defer), autopilot first forks to `/quartermaster` for a second opinion. Every fork recorded as `response_source: /quartermaster` in the dispatch file.

Use when: "I'm AFK on technically complex work and want autonomous progress within bounded technical judgment."

---

### Example 8 — Budget-capped autopilot

```
/falcon work beads example-73sz --autopilot --amendment-budget=2
```

Same as `--autopilot` but HALT after issuing 2 auto-issued amendments. Subsequent gaps surface inline as "amendment budget exhausted — defer to user." Prevents runaway scope-creep if `SAFE_TO_AMEND` predicate is too loose for this dispatch.

---

### Example 9 — Long-running content rewrite (tuned cadence)

```
/falcon work beads example-clj.41,example-7hq.41 --sequential --autopilot --cron-cadence=15m
```

Steering + worker crons fire every 15 min instead of 5 min default. 3x cheaper (fewer fires over a 2-hour run) with 15-min worst-case latency on transitions. Use for dispatches expected to run 60+ min where 5-min polling is wasteful.

---

### Example 10 — Paranoid lock-release

```
/falcon work beads example-hz38 --autopilot --release-on-merge
```

Same as `--autopilot` but lock releases only when the PR merges, not at validation pass. Steering cron stays armed across the validation → review → merge gap. Use when you want the lock held during PR review so a follow-up dispatch can't claim overlapping files prematurely.

---

### Example 11 — Dry-run preview

```
/falcon work beads example-73sz --autopilot --dry-run
```

Prints the derived `file_scope`, lock-registry check result, autopilot policy effects, and cron preview without writing any files or scheduling any crons. Use when previewing autopilot effects before committing.

---

### Example 12 — Mixed-autonomy multi-dispatch sprint

```
# Heavy work running while user is AFK — full autopilot:
/falcon work beads example-hz38,example-gh4t,example-1xz4 --sequential --autopilot --advisor=quartermaster
/falcon work beads example-qc82,example-ppkg,example-krux --sequential --autopilot

# Quick doc fix — semi-autonomous (intent-ack only):
/falcon work beads example-sbgo --auto-ack

# Single content file — full autopilot, narrow budget:
/falcon work beads example-73sz --autopilot --amendment-budget=1
```

Four commands replace ~12 turns of manual cron construction + DAR arbitration + worker-cron setup. Flags encode the policy bounds; the project's `.claude/rules/falcon-autopilot.md` encodes the project-specific gates for `SAFE_TO_ACK_INTENT` and `SAFE_TO_AMEND`.
