# Falcon — Changelog

Version history for the falcon skill. Current version is in `SKILL.md` frontmatter (`version:` field).

## 7.0.1 (2026-05-27)

Bundled v7.0.x operational retro pass — multiple targeted fixes landed on the same release branch.

### Detection-authority caveats: `claude --help` does NOT list `--bg`; falcon must not probe it (fdev-uwx)

Adopters and AI assistants doing falcon-related work were repeatedly mis-identifying `--bg` as unsupported by probing `claude --help | grep -- --bg` (empty result despite the flag being supported on Claude Code ≥ 2.1.139). Falcon's own detection logic was already correct (version gate via `claude --version`, never `--help`) — but the docs didn't pre-empt the natural fallback of consulting `--help`. This version adds explicit "Detection authority — do NOT consult `claude --help`" caveats in PROTOCOL.md, COMMANDS.md, and README.md `Verify the install` so AI assistants reading falcon docs don't fall through to a `--help` probe.

- `PROTOCOL.md` Step 2 §"Mode selection + detection" version-gate step — appended "Detection authority — do NOT consult `claude --help`" paragraph with rationale
- `COMMANDS.md` `--bg ✓` detection sequence step 1 — appended short caveat with link back to PROTOCOL
- `README.md` §"Verify the install" — adopter-facing heads-up that `claude --help` may not list `--bg`
- `SKILL.md` frontmatter — `version: 7.0.0` → `7.0.1`

### Cron emission dispatch-mode split: `--bg` uses inline `STATE:` lines; `--via-paste` keeps fences (fdev-lbq.9 + fdev-lbq.19)

Production retro observation: in `--bg` mode, autopilot crons were emitting 20-30 line labeled-copy fences (intended for paste into a worker tab) AND an AI assistant was improvising `claude --resume <worker-session> --print "proceed <id>"` to "relay" the fence — only to be rejected by Claude Code with `Error: Session <uuid> is currently running as a background agent (bg). Use claude agents to find and attach to it, or add --fork-session to branch off a copy.` Both are vestigial paste-mode behaviors that don't fit `--bg` semantics (no worker tab to paste into; no peer-to-peer message-injection primitive for running `--bg` agents).

This release adds explicit `Cron Dispatch-Mode Conventions (v7.0.1)` to REFERENCE.md establishing the dual-path contract, then applies mode-conditional emission across all five autopilot cron templates:

- **`--watch`**, **`--auto-ack`**, **`--auto-amend`**, **`--release-on-merge`** templates now branch on `worker_dispatch_mode` at the emission step. In `--bg`: emit a single inline `STATE:` line; the file write of `intent_acknowledged_utc` / `amendments[].request` / `session_status: complete` is the contract; the worker self-polls via auto-ack-resume guard. In `--via-paste` / `--paste`: emit the full labeled-copy fence (unchanged).
- **`--worker-cron`** template carries a defensive check that self-cancels if armed in `--bg` mode (it should never be — `--bg` suppresses it at emission time, but the defensive check catches operator missteps).
- Explicit anti-pattern callouts in the conventions section: cron MUST NOT invoke `claude --resume` (Claude Code rejects on running `--bg` sessions) or `claude --fork-session` (creates duplicate session that violates falcon's single-worker-per-dispatch invariant).
- PROTOCOL.md `### --bg dispatch mode` — added "Cron emission dispatch-mode split (v7.0.1)" subsection summarizing the contract and cross-referencing the REFERENCE.md conventions.
- COMMANDS.md `### --autopilot ✓` — added v7.0.1 note summarizing the dual-path emission.

No protocol-breaking changes for paste-mode operators. `--bg` operators see significantly less cron noise per fire (single line vs full fence) and no more `--resume` rejection errors in steering output.

### Per-dispatch commit attribution: watch cron no longer emits N×N spurious STATUS UPDATEs on shared branch (fdev-lbq.4)

Production retro observation: when N parallel dispatches share a branch (the v7.0.x parallel-dispatch model), the `--watch` cron's `commits_on_branch_since_open` metric was branch-global, not per-dispatch. When dispatch A pushed a commit, dispatch B's next watch fire saw `branch_total` ticked up and emitted a STATUS UPDATE — claiming a change that wasn't actually about dispatch B. With N dispatches, 1 commit produced N spurious updates (N×N worst case).

Watch cron now computes per-dispatch attribution via the `Closes: <bead-id>` commit trailer (a Worker Lifecycle convention since pre-v7.0). Two metrics surface in the STATE: / STATUS UPDATE emission: `commits_attributed` (this dispatch's via trailer match) and `commits_unattributed` (everyone else's commits + amend/rebase that dropped the trailer). The attributed count drives state-change detection; the unattributed count fires a degraded "unattributed commit detected" notification ONLY when it GROWS since the prior fire (catches amend/rebase mistakes; ignores routine parallel-dispatch noise).

- REFERENCE.md `--watch` cron Step 1 — rewrote the `git log` block to compute per-dispatch attribution + branch-wide unattributed counts
- REFERENCE.md `--watch` cron Step 3 — STATE: and labeled-copy fence both now report `commits_attributed` + `commits_unattributed` separately; degraded notification fires on unattributed-grew
- PROTOCOL.md `### --watch mode` — added "Per-dispatch commit attribution (v7.0.1, fdev-lbq.4)" subsection explaining the mechanism + the worker contract

Worker-side contract reinforced: every commit MUST carry `Closes: <bead-id>` in the message. In single-dispatch mode this was best-practice; in parallel-dispatch mode it's now a correctness requirement. Workers already follow this convention per Worker Lifecycle Step 8; this release makes the watch-cron-side consumption explicit.

### Adaptive cadence: per-fire cost short-circuits outside the relevance window (fdev-lbq.2 + fdev-lbq.3)

Production retro: autopilot crons fire on fixed cadences (4m ack / 7m amend) for the entire dispatch lifecycle (~30-60 min), but each cron's relevance window is narrow — `--auto-ack` matters only intent-emission-to-ack (typically 5-20 min); `--auto-amend` matters only completion-to-validated (typically 1-3 fires after the worker emits COMPLETION). Outside these windows the existing in-template early-exits did fire, but each fire still read the full dispatch state before short-circuiting. Operator observation: "auto-ack fired 18 times, 17 silent exits, 1 useful = 5% signal density."

Both write-bearing crons now have a **Step 0 — Adaptive cadence early-exit guard** at the top of their templates that probes ONLY the state-driving fields via a focused yq query (not a full file read), and exits silently when the cron is in a quiescent window. The cadence itself is unchanged (still 5m default); per-fire token cost is what becomes adaptive.

**`--auto-ack` Step 0 quiescent windows:**

- **Pre-intent**: implementation_intent is null → Step 1's existing null-check catches this; minimal additional cost.
- **Post-ack**: `intent_acknowledged_utc` is non-null AND not terminal → Step 0 case 2 exits immediately.
- **Terminal**: session_status == "complete" → Step 0 case 1 routes to Step 6 self-cancel.

**`--auto-amend` Step 0 quiescent windows:**

- **Pre-completion**: `implementation_results_hash` is null → Step 0 case 2 exits immediately.
- **Budget-exhausted**: `auto_amendments_issued >= amendment_budget` → Step 0 case 3 exits immediately (the FIRST HALT detection still flows through Step 4 to emit AMENDMENT BUDGET EXHAUSTED; subsequent fires stay silent).
- **Terminal**: session_status == "complete" → Step 0 case 1 routes to Step 7 self-cancel.

CronCreate-driven cadence-change (re-arming at a slower cadence on state transition) was considered but deferred to v7.1 — the in-prompt Step 0 guard is the minimum-risk fix that captures most of the noise reduction without touching CronCreate semantics. PROTOCOL.md `### --watch mode` documents the dual-guard pattern; `### --auto-ack mode` and `### --auto-amend mode` cross-reference the REFERENCE.md Step 0 templates.

### Worker termination primitives + `claude agents` CLI surface documented (fdev-lbq.8 + fdev-lbq.20 + fdev-lbq.21 + fdev-lbq.22)

Three primitives that affect a running `--bg` worker have different effects; operators were conflating them. This release adds a comparison table to PROTOCOL.md `### --bg dispatch mode` and an extended CLI-surface reference to REFERENCE.md:

| Goal | Right command | Effect |
|------|---------------|--------|
| Pause; resume on next user interaction | `claude stop <id>` (alias `claude kill`) | Process stops; state preserved; agent-viewer row stays. NOT terminal. |
| Remove from agent-viewer entirely | `claude rm <id>` | Row disappears; transcript preserved via `claude --resume`; Claude-created worktree removed if clean. Terminal kill. |
| Replace worker forensically | `/falcon respawn-fresh <id>` | New session ID + `-r<N>` suffix; prior session recorded in `worker_bg_prior_sessions[]`. Dispatch continues. |

Plus the orthogonal Claude Code `claude respawn <id>` (CLI) — restart same session with conversation intact (e.g. to pick up updated Claude Code binary). NOT the same as `/falcon respawn-fresh`. The two-primitive disambiguation is called out in COMMANDS.md `### /falcon respawn-fresh`.

**Supervisor-stop semantics corrected:** PROTOCOL.md L187 prose updated to match upstream agent-view docs. Auto-stop fires only on FINISHED sessions sitting unattached for ~1hr. Working / Needs-input / attached sessions are NOT auto-stopped. Pinned sessions (Ctrl+T in agent view) are exempt. The supervisor does NOT autonomously revive stopped sessions at a new pid; restart happens on user interaction (attach/peek/reply). The retro observation that "supervisor revived at a new pid" was a misreading of the user-interaction-driven restart path.

**`claude agents` CLI surface reference table** added to REFERENCE.md before the `Cron Dispatch-Mode Conventions` subsection — covers `claude agents`, `--cwd`, `--json`, `attach`, `logs`, `stop`/`kill`, `rm`, `respawn`, `--bg`, `--version`, `daemon status`, plus explicit anti-patterns (`--resume`, `--fork-session`) so cron-template authors don't have to leave the falcon docs to look up the surface.

Cross-references added to https://code.claude.com/docs/en/agent-view as the upstream source of truth.

## 7.0.0 (2026-05-26)

**MAJOR bump — new default dispatch mode via Claude Code background sessions.** `/falcon work beads <spec>` (no mode flag) defaults to `--bg`: steering invokes `claude --bg --name "falcon-<dispatch-id>" "<short-bootstrap>"` via the Bash tool, spawning a detached Claude Code background session observable via the `claude agents` UI. The prior paste-into-tab default is preserved as the renamed `--via-paste` flag for environments without agent-view OR users who prefer manual tab control. The cross-machine `--paste` mode is unchanged. The shift is motivated by ergonomic wins discovered in conversation 2026-05-25:

- **No tab management** — one agent-view terminal monitors every dispatch (`Working / Needs input / Completed` state per row)
- **Built-in peek-and-reply** for INTENT-confirm pauses (Space → read INTENT → type `proceed <id>` → Enter)
- **No paste-block reliability concerns** — steering passes the bootstrap as a CLI arg pointer; the multi-line init_prompt content stays in the dispatch file (where it already lives)
- **Session persistence** across machine sleep + Claude Code auto-updates
- **Built-in worktree isolation per session** (configurable per-dispatch via `--bg-isolated` / `--bg-no-isolation`)
- **Built-in PR status indicators** on session rows

The architectural fit between falcon's dispatch lifecycle and Claude Code's background-session model is essentially 1:1; retrofitting agent-view as a dispatch mode supersedes several v6.x design decisions (notably example-r3q9 Safeguard A — wrong-paste-by-human is structurally impossible in `--bg` because there's no paste).

**What flipped from `⊘` to `✓` (new flags + sub-command):**

- **`--bg`** — default for local; auto-downgrades to `--via-paste` on detection failure. Per-dispatch worktree isolation via `--bg-isolated` / `--bg-no-isolation`.
- **`--via-paste`** — renamed from the implicit pre-v7.0.0 default. Auto-downgrade target. Worker-cron still applies (unlike `--bg`).
- **`--bg-isolated`** / **`--bg-no-isolation`** — per-dispatch worktree-isolation overrides. Default inherits `worktree.bgIsolation` from `.claude/settings.json`.
- **`/falcon respawn-fresh <dispatch-id> [--reason=<reason>] [--force]`** — NEW SUB-COMMAND. Spawn a FRESH `--bg` worker that continues an existing dispatch where the prior worker died. Three-step recovery sequence (push unpushed commits → close landed-but-bd-open beads → reconcile in-progress amendments) executes before normal lifecycle. Forensic record of replaced workers persists in `worker_bg_prior_sessions[]`; never re-claimed.

**Environment detection + auto-downgrade.** Before any dispatch action, steering runs version gate (`claude --version >= 2.1.139`) → `disableAgentView` settings check (project-level wins over user-level) → mode override → success path. Eager (Step 2 entry, before dispatch file written) so failures don't half-create state. Failure messages are actionable — cite the version, name the setting, suggest the explicit `--via-paste` flag.

**Bootstrap-prompt pattern (extends v6.7.0 thin init_prompt design).** The CLI arg to `claude --bg` is a SHORT bootstrap (~5 lines) pointing at the dispatch file using `repo_path`-anchored absolute paths. MUST include: (1) literal `dispatch_id`; (2) absolute `repo_path`; (3) instruction to VERIFY `dispatch_id` matches once loaded. Full template lives in REFERENCE.md `### Bootstrap Prompt Template (v7.0.0)`.

**Worktree-isolation handling — the `.claude/tmp/` shared-path concern:** isolated workers run in `<repo_path>/.claude/worktrees/<id>/` where the branch does NOT contain `.claude/tmp/` (ephemeral, lives in main checkout, not committed). Workers MUST resolve dispatch-file paths via `<repo_path>/.claude/tmp/...`. The bootstrap-prompt template enforces this by including `repo_path` literally; PROTOCOL.md Worker Lifecycle Step 1 carries the convention.

**New dispatch file fields:**

- `worker_dispatch_mode: "bg"` — values: `"bg"` | `"via-paste"` | `"paste"`. Autopilot crons consult this to apply `--bg`-aware behavior vs legacy paste-block emission.
- `worker_bg_session_id: null` — short session ID returned by `claude --bg`. Source of truth for `claude attach` / `claude logs` / `claude stop` reference.
- `worker_bg_isolation: null` — values: `null` (inherit project setting) | `"isolated"` | `"none"`.
- `worker_bg_prior_sessions: []` — read-only forensic record of replaced workers, oldest first. Each entry: `{session_id, spawned_utc, replaced_utc, reason}`. safety-tripped advisory (REQUIRED): if `reason: safety-tripped`, do NOT read `claude logs <session_id>` in a new session — the log may reproduce the triggering content and re-trip the safety filter in the reader's session (development-standards.md §3.15).
- `dispatch_continuation: false` — set to `true` by `/falcon respawn-fresh` so the successor's bootstrap detects continuation mode.

**`--worker-cron` is a no-op in `--bg` mode.** The auto-ack-resume guard (v6.9.0; Worker Lifecycle Step 3) handles amendment pickup within the same persistent background session — no separate worker-side cron needed. The flag stays explicit for `--via-paste` / `--paste` users; no formal deprecation in v7.0.0. `--autopilot` macro still expands to `--auto-ack --auto-amend --worker-cron --watch`; `--worker-cron` is suppressed at emission time in `--bg` mode.

**Amendment-propagation latency caveat (`--bg` mode).** Without a worker-cron, the worker picks up amendments on its next active turn (typically triggered by user peek/reply, autopilot cron STATUS UPDATE, or the worker's own self-poll mid-execution) rather than on a predictable cron cadence. NOT a regression from `--via-paste` UX (the user had to wait for the worker tab to poll), but cadence is event-driven rather than predictable. Pinning long-running autopilot dispatches in agent view (`Ctrl+T` on the row) keeps the worker process alive past the ~1hr supervisor-stop window.

**`/falcon create-rules` bypassPermissions setup check (NEW SCOPE — Q6 verdict).** After writing the rules file, the command checks for `bypassPermissions: true` in `.claude/settings.json` (project) → `~/.claude/settings.json` (user). If neither: emit a non-blocking warning describing how to enable for unattended autopilot operation. If either: emit a one-line confirmation. Check belongs at setup-time (rules-file creation), NOT at activation-time (`/falcon enable-autopilot`), per quartermaster's reasoning that `bypassPermissions` is a settings-file value, not a CLI dispatch-time switch.

**`/rename` is the canonical session-identity mechanism (P5.1 fix).** The prior v6.7.0 Dispatch Prompt Template Step 1 advised tmux/printf/IDE-escape terminal-title setting; all three mechanisms silently failed across most real-world setups (shell-prompt redraw hooks override the OSC escape within milliseconds; tmux rename errors silently when not in tmux; IDE terminals vary). Replaced with single-line `/rename falcon-<dispatch-id>` for `--via-paste` and `--paste` modes — environment-agnostic, can't be overridden by shell prompts, shown on the prompt bar AND in `claude agents`. `--bg` mode does NOT need this step because `claude --bg --name "falcon-<dispatch-id>"` sets the session name at spawn time.

**Supersedes / resolves:**

- **example-r3q9 (Safeguard A: worker_session_id field + claim mechanic)** — RESOLVED by superseding design. In `--bg` mode there is no paste — steering invokes the session directly with the dispatch ID. Wrong-dispatch-paste-by-human is structurally impossible. Closes as "resolved by v7.0.0 default dispatch mode change."
- **Residual concern (different class):** steering code logic could pass a wrong `dispatch_id` to `claude --bg`. This is NOT what r3q9 was designed to prevent (which was user-attention errors). Mitigation: bootstrap-prompt's verify step ("Verify the dispatch_id field in the loaded file matches <id> before any state change"). Documented in the bootstrap template + Worker Lifecycle Step 1.

**Kept (still valuable):**

- **v6.12.1 Safeguard B (INTENT identity header)** — still valuable for `--via-paste` and `--paste` modes; also helps users peeking the INTENT block in agent-view to verify dispatch ID matches the row name they're peeking.
- **v6.11.0 `--worker-cron`** — superseded for `--bg` mode but kept for `--via-paste` and `--paste` modes.
- **v6.12.2 `/falcon list-pending`** — still useful; complements `claude agents` (the former is per-branch; the latter is global).
- **v6.12.2 `--watch` HIGH-STAKES DAR PENDING headline** — still useful; agent-view's row "Needs input" shows that something needs attention but doesn't classify urgency.
- **v6.14.0 `/falcon enable-autopilot --profile=<name>`** — independent of dispatch mode.

**8 resolved design decisions (initial draft → final):**

1. **Q1** — `--bg` is DEFAULT in v7.0.0 (not opt-in). Version-gate + `disableAgentView` detection logic IS the opt-out path. Eager detection + auto-downgrade is the safety net.
2. **Q2** — Worktree isolation: per-dispatch flag (`--bg-isolated` / `--bg-no-isolation`) with default inheriting `worktree.bgIsolation` from settings; if absent, defer to Claude Code default. `.claude/tmp/` shared-path concern resolved via repo_path-anchored absolute paths.
3. **Q3** — `--worker-cron` suppressed in `--bg` mode (silent no-op); flag stays explicit for other modes; no formal deprecation. `--autopilot` macro expansion description must document the `--bg`-mode behavior.
4. **Q4** — Bootstrap prompt generated from string template at dispatch time (NOT a `bootstrap_prompt` schema field). Template lives in REFERENCE.md.
5. **Q5** — One background session per dispatch (matches current model; `--sequential` continues to work unchanged in `--bg`).
6. **Q6** — `bypassPermissions` check belongs in `/falcon create-rules` (setup-time), NOT `/falcon enable-autopilot` (activation-time). Non-blocking warning. NEW SCOPE.
7. **Q7** — Cost transparency out of scope. Claude Code's billing visibility is the right surface; `worker_bg_session_id` enables manual correlation to usage dashboard.
8. **Q8** — Detection logic: version gate FIRST (cheapest), then `disableAgentView` (project-level wins over user-level). Failure messages cite version, name the setting, suggest the explicit `--via-paste` flag.

**Perspective-review gaps addressed during implementation (P5.1 / P5.2 / P5.3):**

- **P5.1** — `/rename` replaces tmux/printf/IDE-bullet terminal-title block (above).
- **P5.2** — Supervisor-stopped worker note added to PROTOCOL.md `### --bg dispatch mode`: long-running autopilot dispatches should be pinned in agent view (`Ctrl+T`) to keep the worker process alive past the ~1hr supervisor-stop window; otherwise auto-ack auto-resume won't fire while supervisor-stopped (user interaction restarts the session).
- **P5.3** — `--bg + --paste` (and `--via-paste + --paste`, `--bg-isolated + --bg-no-isolation`) mutually exclusive; steering refuses with informative error suggesting the user pick one based on shared-filesystem availability.

**Forward-look (filed separately):**

- The two-mode simplification (`--dispatch=<agent|paste>`, drop cross-machine `--paste`) is parked for v8.0.0. Sequencing v7.0.0 first lets users adopt agent-view before we remove their cross-machine fallback. v7.0.0 ships the new default; v8.0.0 ships the cleanup after adoption data confirms safety. Tracked in example-tn54.

**Where each artifact lives:**

- SKILL.md — version bump to 7.0.0
- COMMANDS.md — new flags (`--bg`, `--via-paste`, `--bg-isolated`, `--bg-no-isolation`); new sub-command (`/falcon respawn-fresh`); `/falcon create-rules` bypassPermissions check augmentation; `--autopilot` macro `--bg`-mode behavior note; `--worker-cron` `--bg`-mode no-op note; `--paste` distinct-from-`--via-paste` clarifier
- PROTOCOL.md — new Step 2 subsections (`### Mode selection + detection (v7.0.0)`, `### --bg dispatch mode (v7.0.0)`); Worker Lifecycle Step 1 updated for `repo_path`-anchored dispatch-file path requirement + `/rename` canonical mechanism; new Step 5 sub-command (`### /falcon respawn-fresh <dispatch-id>`)
- REFERENCE.md — 5 new schema fields (`worker_dispatch_mode`, `worker_bg_session_id`, `worker_bg_isolation`, `worker_bg_prior_sessions`, `dispatch_continuation`) with detailed comments incl. safety-tripped advisory; new `## Mode-Selection Decision Tree (v7.0.0)` section; new `## Bootstrap Prompt Template (v7.0.0)` section with literal template + substitution variables + repo_path-anchor rationale; Dispatch Prompt Template Step 1 updated to `/rename`
- changelog.md — this entry

**Out-of-band verification (POST-merge, recommended):** user manually tests `--bg` mode against a low-stakes bead in a separate session. Document the test scenario + outcome in a follow-up handoff or wrapup note. Optional but recommended before claiming v7.0.0 is production-ready for autopilot use.

## 6.14.0 (2026-05-25)

**New sub-command `/falcon enable-autopilot --profile=<conservative|standard|aggressive>`.** Bulk-uncomments `# PROJECT —` gates in `.claude/rules/falcon-autopilot.md` per a chosen profile, replacing the manual "find the right blocks to uncomment in a 449-line file" friction that the refuse-on-MVM design (Phase 2 v6.9.0 precedent) intentionally creates.

**The three profiles:**

- **`conservative`** — minimum-viable autopilot. ALL §3 denylist items active (safety: more is better). 1-2 highest-priority §1 intent gates. ZERO project §2 whitelist items (universal whitelist only). §4 claims-OOB cognitive hint. NO advisor. Tight §6 budgets (chore: 1, all features: 1, decision: 0). Use when first activating autopilot on a new project.
- **`standard`** — recommended for general use. ALL §3 denylist + project-seeded §1 + §2 + §4 items where their detection conditions hold + §5 advisor (if quartermaster skill exists). §6 per-bead-type defaults from the template's recommended values.
- **`aggressive`** — maximum autopilot autonomy. Every `# PROJECT —` item across all 6 sections where detection holds. Generous §6 budgets. Use only after confirming standard is well-calibrated.

**Detection-driven uncommenting**: profiles aren't blind bulk-uncomment. Each profile entry has a detection condition (file-exists, file-grep, directory-has-files, always, skill-installed). Items whose detection fails are LEFT COMMENTED even at aggressive — prevents activating gates that reference standards the project doesn't have. Profiles degrade gracefully when shipped to a new project.

**Safeguards** (preserve the refuse-on-MVM design philosophy):

- Profile REQUIRED — no naked `/falcon enable-autopilot` that picks one for the user. Forces conscious choice.
- `--dry-run` previews the diff without writing.
- Pre-write confirmation prompt unless `--force` (the per-gate comprehension checkpoint).
- Archive existing file to `.archive/falcon-autopilot-<UTC-timestamp>.md` before write. Recovery path if profile uncomments more than intended.
- Mutation via position-anchored regex (per development-standards.md §3.18 — bulk YAML mutations must scope by section header, not indentation alone). Prevents the cross-section collision the §3.18 candidate rule names.

**No re-commenting** — the command only uncomments. Downgrading a profile (e.g., aggressive → standard) requires manually re-commenting OR restoring from `.archive/` backup. Asymmetry is intentional; autopilot deactivation should be a conscious manual step.

**Where each artifact lives:**

- COMMANDS.md — new sub-command entry `### /falcon enable-autopilot --profile=<name> ✓` with profile descriptions + flags + examples + when-to-use
- PROTOCOL.md — new subsection `### /falcon enable-autopilot --profile=<name>` in Step 5 with full implementation walkthrough (preconditions, profile load, detection eval, diff print, dry-run handling, confirmation, backup, position-anchored mutation, summary print)
- REFERENCE.md — new subsection `### Profile definitions (v6.14.0)` inside `## falcon-autopilot.md Template` defining all three profiles as `(section, item, detection, value?)` tuple lists; documentation of detection condition types; "Adapting profiles to a new project" section for downstream consumers
- SKILL.md — version bump only

**Workflow change for autopilot setup** (the new recommended sequence):

1. `/falcon create-rules` — scaffolds the rules file with everything commented (unchanged)
2. `/falcon enable-autopilot --profile=conservative --dry-run` — preview what conservative would activate
3. `/falcon enable-autopilot --profile=conservative` — apply (with confirmation prompt)
4. Run a dispatch with `--auto-ack` to verify it works
5. After 1-2 sprints: `/falcon enable-autopilot --profile=standard` to upgrade
6. After several sprints with standard working well: `/falcon enable-autopilot --profile=aggressive` if you want more autonomy

**Forward-look:** Option B from the design conversation (smart-seed `/falcon create-rules` to auto-uncomment based on detected files at scaffold time) and Option A (read-only `/falcon recommend-gates` for users who already have the rules file) are NOT included in v6.14.0 but remain candidates for future work if usage data shows Option C alone isn't enough.

## 6.13.0 (2026-05-25)

**Hypothesis-framing convention for steering-session-notes.** Added to PROTOCOL.md Step 2: when steering notes call out a known DAR or investigation that the worker may need to handle, frame the hypothesis space as "investigate these N candidates" rather than "likely X." Workers tend to test the "likely" path first and spend turns disproving before broadening; equal-weight candidate framing invites evidence-gathering over confirmation-bias.

**Provenance:** a worker session tested the "likely" path first, spent ~5 turns disproving via git inspection (the suspected cause didn't actually touch the relevant fields), then broadened the search and found the actual root cause (stateful container reuse). Equal-weight framing — "candidate 1: migration-side rewrite; candidate 2: container-state corruption; candidate 3: fixture drift" — would have saved the disproof turns.

No new flags, no schema changes. Documentation + convention addition only.

## 6.12.2 (2026-05-25)

**Two coordinated AFK-return workflow enhancements: `/falcon list-pending` sub-command + `⚠️ HIGH-STAKES DAR PENDING` headline in `--watch` STATUS UPDATE blocks.** Designed for the return-from-AFK autopilot workflow — when you come back to a session that ran `--autopilot` for hours, find the items waiting on your attention in one place instead of grepping dispatch files manually.

**What was added:**

- **`/falcon list-pending`** — new read-only sub-command that scans all active dispatch files and prints a flat grouped list of pending-human items across 6 categories: HIGH-STAKES DAR awaiting arbitration, OUT-OF-SPEC APPROVAL REQUESTS with null response, OUT-OF-BAND VERIFICATION pending, AMENDMENT BUDGET EXHAUSTED, PR CLOSED UNMERGED (release-on-merge edge case), STALE LOCKS (> 2h held past validation pass). Each entry includes an action hint (`/falcon release <id>` / `bd close <id>` / `issue manual amendment` / etc.). Empty categories shown with `(0)` so you know they were checked. Fits the existing `list-locks` / `list-sessions` read-and-present pattern.

- **`⚠️ HIGH-STAKES DAR PENDING` headline** in the `--watch` cron's STATUS UPDATE block (REFERENCE.md `### --watch cron prompt template` Step 3). When the watch cron fires and detects any open high-stakes DAR on the dispatch (`stakes: high` + `action_taken: stopped pending arbitration` + no recorded resolution), it prepends a one-line headline at the top of the fence so the DAR can't be missed when scanning a long inline history of routine STATUS UPDATE emissions. Pre-existing state-change body emits below the headline as before.

**Both are doc-only enhancements; backward-compatible.** No schema changes, no new flags, no behavior changes to existing flows. Pure surfacing improvements for the autopilot workflow.

**Why the dual deliverable:** the user's question that prompted this revealed two complementary gaps —
(a) "is there a command to check items waiting on human?" (pull-based: user explicitly queries when they return) and
(b) "the watch cron's STATUS UPDATE doesn't headline ⚠️ HIGH-STAKES DAR PENDING" (push-based: cron-emitted notifications during their absence).
Landing both together closes both halves of the AFK-return surfacing problem in a single PATCH bump.

**Where:**

- COMMANDS.md `/falcon list-pending ✓` — new sub-command entry between `/falcon list-sessions` and `/falcon status` with the 6-category output sketch + recommended cadence + cross-link to PROTOCOL.md
- PROTOCOL.md `### /falcon list-pending` — new subsection in Step 5 with per-category parse + filter + output logic
- REFERENCE.md `### --watch cron prompt template` Step 3 — augmented to detect high-stakes DARs and prepend the headline before the state-change body emits

**Forward-look (uncommitted):** Safeguard A (worker_session_id field + claim mechanic + `/falcon claim-as-worker` escape hatch) for wrong-dispatch-paste detection at branch-verify time — tracked in example-r3q9 for proper Phase-N treatment. Also: `/wrapup` integration to auto-pickup the `RETRO SUMMARY` block (v6.12.0) and the `/falcon list-pending` output for session-start orientation in `/leroy` and `/gogogo` skills.

## 6.12.1 (2026-05-25)

**INTENT block gains a 2-line dispatch-identity header (Safeguard B of the wrong-paste-detection design).** Workers prepend `Working dispatch <id> on branch <branch>` + `Beads: [<id>: "<title>", ...]` INSIDE the INTENT fence, ABOVE the intent paragraph. This is the last visual checkpoint where a user with multiple worker tabs can spot a wrong-dispatch-paste before typing `proceed <id>`. If the dispatch ID, branch, or bead titles don't match what the user expected for this tab, they reject the paste with a revision instead of authorizing the worker.

**Why this matters.** In a four-cron `--autopilot` world (v6.11.0+) with multiple concurrent dispatches across worker tabs, branch-verify + `bd show` catch non-existent branches/beads but NOT a wrong-paste where dispatch A's branch+beads happen to exist and don't overlap with what was intended for the target tab. The lock registry catches `file_scope` collision but not wrong-paste-to-idle-tab. The terminal title (set in v6.7.0) is a visual cue but can be missed. The dispatch-identity header puts identity inside the human-action loop right before `proceed <id>` — the cheapest possible safeguard.

**Doc-only enhancement; backward-compatible.** Steering doesn't parse the INTENT block format — it's a human-facing visual aid. Workers emitting the pre-v6.12.1 format still validate. The hash-based completion gate (v6.3.0+) and dispatch file content are unchanged.

**Where:**

- PROTOCOL.md Worker Lifecycle Step 3 — instructs workers to prepend the identity header; cross-references to REFERENCE.md format example
- REFERENCE.md `## Copy-Paste Emission Convention` — updated INTENT example showing the new format
- REFERENCE.md `## Dispatch Prompt Template` Step 5 — updated INTENT emission instructions for the worker

**Safeguard A (worker_session_id field + claim mechanic + `/falcon claim-as-worker` escape hatch) deferred** to example-r3q9 for proper Phase-N treatment. Safeguard A requires schema changes, session-ID plumbing, and a legitimate-restart edge-case handler — too much surface for a PATCH bump. Safeguards A and B are independent and B catches the common case (human-attention check at intent-confirm), so the deferral is safe.

## 6.12.0 (2026-05-25)

**Autopilot Phase 5 — final phase. `--advisor=<agent>` + `--release-on-merge` + `/falcon retro --branch <name>`.** Completes the autopilot rollout established by epic `example-um2p`. After this version, the autopilot operating model is feature-complete: steering can auto-ack intent + auto-issue amendments + observe state + fork ambiguous decisions to a registered advisor + hold the lock until PR merge; worker can auto-pick-up amendments; user can synthesize a per-branch autopilot retro at wrapup.

**What flipped from `⊘` to `✓`:**

- `--advisor=<agent>` — fork ambiguous decisions (gate-fail + advisor_delegation policy match) to a registered project agent (e.g., quartermaster). Recorded as `response_source: /<agent>` in the amendment entry. NOT a separate cron — extends the `--auto-ack` and `--auto-amend` cron evaluation paths.
- `--release-on-merge` — new separate single-responsibility cron `falcon-merge-<dispatch-id>` that polls `gh pr view --json state` every 15 min and, on `state: MERGED`, sets `session_status: complete` to trigger the auto-release path. Step 4 (Stash for Wrapup + Auto-Release) gains a new hold-the-lock condition for `release_on_merge: true`.
- `/falcon retro --branch <name>` — branch-keyed stash + dispatch-file synthesis for autopilot audit. Emits a `RETRO SUMMARY` block counting auto-acks, auto-issued amendments, advisor forks, DAR resolutions, budget exhaustion, release-on-merge usage — for `/wrapup` to incorporate.

**What was added to the schemas + conventions:**

- New dispatch file field `release_on_merge: false` — set by `--release-on-merge`; read by Step 4 (new hold-the-lock condition) and by the merge cron template.
- New dispatch file field `merge_cron_id: null` — `CronCreate`-returned ID for the merge-poll cron. Mirrors `watch_cron_id` etc.
- New dispatch file field `advisor: null` — set by `--advisor=<agent>` to the agent's name (e.g., `"quartermaster"`). Read by `--auto-ack` and `--auto-amend` cron templates to know whether/where to fork ambiguous decisions.
- New per-amendment-entry field `response_source: null` — set when the amendment is issued. Values: `"autonomous"` (gate match, no advisor), `"/<agent>"` (advisor-delegated), `"user-relay"` (manual), `"steering-cron"` (default for autopilot writes). `/falcon retro` counts by this field for the autopilot audit.
- New cron slug `falcon-merge-<dispatch-id>` — extends the prefix-match teardown set. `/falcon release-cron` already supports it via prefix-match (no command-side changes needed).
- New scratch-file convention `.claude/tmp/falcon-merge-<dispatch-id>-state.json` — tracks last-observed PR state.

**Design deviation from bead-body suggestion (caught at readiness pass):** the original quartermaster-coordination bead body proposed folding the PR-merge poll into the existing `--watch` cron template. Readiness review caught the issue: that would make `--watch` write-bearing (it would set `session_status: complete` on merge detection) and force `--watch` to refuse-on-MVM when `release_on_merge: true`, violating the Phase 1 report-only contract. The implementation deviates: separate `falcon-merge-` cron preserves `--watch`'s single-responsibility report-only design and lets `--release-on-merge` be usable standalone (without `--watch`) for paranoid lock-release on a single-bead dispatch.

**`--advisor` is an extension, not a cron.** Phases 1-4 each added a new cron. Phase 5's `--advisor` extends the EXISTING `--auto-ack` (intent gate evaluation) and `--auto-amend` (gap evaluation) crons with an advisor-fork sub-step. The advisor is invoked via the Skill tool from inside the cron template's gate-evaluation logic. Advisors honor their own `refuses` lists (e.g., quartermaster.refuses includes fair-play-policy questions, scoring-semantics) — when the advisor refuses, the cron defers to user per the normal path. This means `--advisor` is the first autopilot flag with no associated cron slug or sidecar file — it's purely a behavioral switch on existing crons.

**No refuse-on-MVM for `--release-on-merge` or `--advisor`.** `--release-on-merge` does not evaluate project gates (the "gate" is the PR review process held in GitHub). `--advisor` is itself a refinement of the refuse-on-MVM path — when project gates clearly fail and there's an advisor, the advisor can rescue the decision; the refuse-on-MVM for `--auto-ack` and `--auto-amend` still applies otherwise.

**New copy-paste emission labels:** `MERGE-DETECTED` (merge cron emits on merge confirmation — triggers the chain), `MERGE-WATCH PR-DETECTED` (informational; PR exists), `MERGE-WATCH PR-READY` (informational; DRAFT→OPEN), `MERGE-CRON PR-CLOSED-UNMERGED` (PR closed without merge — manual lock-release needed), `MERGE-CRON NO-PR` (PR not yet created), `MERGE-CRON RELEASED` (self-cancel), `ADVISOR FORK` (advisor consulted, recommendation captured), `RETRO SUMMARY` (/falcon retro output).

**Where each artifact lives:**

- COMMANDS.md — three `⊘`→`✓` flips (`--advisor=<agent>`, `--release-on-merge`, `/falcon retro --branch <name>`); spec text updated with v6.12.0 wiring + deviation rationale
- PROTOCOL.md — new subsection `### --release-on-merge mode (v6.12.0)` in Step 2; new hold-the-lock condition in Step 4 (one-line addition citing v6.12.0); new subsection `### /falcon retro --branch <name>` in Step 5 with full implementation walkthrough
- REFERENCE.md — four new schema fields (3 dispatch + 1 per-amendment), `### --release-on-merge cron prompt template (v6.12.0)` (~120 lines) added as sixth registry entry, `#### --auto-ack advisor-extension (v6.12.0)` and `#### --auto-amend advisor-extension (v6.12.0)` appended to the existing Phase 2/3 templates
- SKILL.md — version bump only

**Autopilot rollout complete.** Epic `example-um2p` closes with 5/5 children complete. The cron prompt template registry has six entries (`--watch`, `--auto-ack`, `--auto-amend`, `--worker-cron` template + setup paste-block, `--release-on-merge`) plus two advisor-extension appendices. The dispatch file schema has gained 8 fields across Phases 1-5 (`watch_cron_id`, `autoack_cron_id`, `intent_acknowledged_utc`, `amend_cron_id`, `amendment_budget`, `auto_amendment_count`, `worker_cron_id`, `release_on_merge`, `merge_cron_id`, `advisor` — and the per-amendment `response_source`). Five new cron slugs follow the `falcon-<role>-<dispatch-id>` prefix-match convention established in Phase 1.

**Forward-look:** Phase 6+ work is uncommitted at v6.12.0. Discovered work during the rollout includes (a) worker session-ID handshake (single-worker-per-dispatch enforcement; detect wrong-dispatch paste), (b) runtime wiring (actual CronCreate invocation behind the cron template documentation — Phases 1-5 are documentation-only), (c) `/wrapup` integration for `RETRO SUMMARY` auto-pickup. These would be filed as new beads under fresh epics, not as Phase 6 of `um2p`.

## 6.11.0 (2026-05-25)

**Autopilot Phase 4: `--worker-cron` (first worker-side cron) + `--autopilot` macro (full AFK bundle).** Phases 1-3 ran crons in the steering session. Phase 4 introduces the worker-side counterpart: `--worker-cron` emits a setup paste-block that the user copies into the worker tab; the worker session then arms its own `CronCreate` against the dispatch file. The worker cron polls for `session_status: amendments_pending` and executes pending amendments per the Amendments Workflow — eliminating the manual `check amendments <dispatch-id>` relay step.

The `--autopilot` macro expands to `--auto-ack --auto-amend --worker-cron --watch` — the full bidirectional AFK setup. Steering arms three crons in its own session and emits two paste blocks (dispatch prompt + worker-cron setup) for the worker tab. Once both pastes land, four crons coordinate via atomic writes to the dispatch file.

**What flipped from `⊘` to `✓`:**

- `--worker-cron` — first worker-side cron. Default cadence 3m (faster than steering's 5m for amendment issuance because the worker needs to clear `amendments_pending` quickly). Slug `falcon-worker-<dispatch-id>` (discoverable only from the worker session, not from steering's `CronList`).
- `--autopilot` — macro expands to the four-flag bundle. Steering autonomously emits the dispatch prompt + worker-cron-setup paste-block AND arms three steering crons. User's only action: paste both blocks into the worker tab in order.

**What was added to the schemas + conventions:**

- New dispatch file field `worker_cron_id: null` — written by the WORKER session (not steering) when it arms the worker cron in response to the setup paste-block. Steering reads it via `/falcon status` as the source of truth for worker-cron existence.
- New scratch-file convention `.claude/tmp/falcon-worker-<dispatch-id>-state.json` — worker-side sidecar tracking the last-processed `amendment_id` so successive cron fires don't re-process the same amendment.
- New cron ID slug `falcon-worker-<dispatch-id>` — follows the prefix-match convention for consistency, but visibility is asymmetric: `/falcon status` (steering) reports the field; `/falcon release-cron` (steering) cannot tear it down (worker session owns it).

**No refuse-on-MVM for `--worker-cron`.** Phases 2-3 established refuse-on-MVM for flags that gate writes. `--worker-cron` does not gate; it executes amendments that already exist in `amendments[]` — those entries are gated upstream (auto-issued by `--auto-amend`'s gate evaluation, OR manually issued by the user). The worker cron acts on already-gated work.

**Four-cron coordination model:**

- `falcon-watch-` (steering, 10m): state observation
- `falcon-autoack-` (steering, 5m): SAFE_TO_ACK_INTENT evaluation; writes `intent_acknowledged_utc`
- `falcon-amend-` (steering, 5m): SAFE_TO_AMEND evaluation + budget HALT; writes `amendments[]`
- `falcon-worker-` (worker session, 3m): polls `amendments_pending`; executes pending amendments; writes per-amendment `status` + `worker_response` + `commits[]`

They do not communicate directly; the dispatch file's atomic-write semantics are the coordination primitive. Each cron's writes are visible to the others on their next fires.

**Teardown coverage:**

- `/falcon release-cron <dispatch-id>` (in steering) tears down the three STEERING-side crons via prefix-match.
- `falcon-worker-` cron uses `durable: false`, dies with the worker session naturally.
- Manual worker-cron teardown while worker is alive requires a paste-block: `CronDelete <worker_cron_id>` into the worker tab.
- All four crons self-cancel on `session_status: complete`.

**New copy-paste emission labels:** `WORKER-CRON SETUP` (steering→worker setup block), `WORKER-CRON ARMED` (worker→steering ack with cron ID), `WORKER-CRON RELEASED` (self-cancel confirmation), `AMENDMENT PICKED UP amend-NN` (worker-cron internal log when it processes an amendment).

**Where each artifact lives:**

- COMMANDS.md — `--autopilot ✓` flip with dual-paste UX + prerequisites; `--worker-cron ✓` flip with worker-side asymmetry note + no-MVM-refuse rationale
- PROTOCOL.md — new subsection `### --autopilot mode (full AFK bundle, v6.11.0)` in Step 2 (between `--auto-amend mode` and `--dry-run mode`); documents four-cron coordination + teardown coverage
- REFERENCE.md — `worker_cron_id` added to Dispatch File YAML Schema; `### --worker-cron cron prompt template (v6.11.0)` (~150 lines) + `### --worker-cron setup paste-block (v6.11.0)` added as fourth and fifth entries in `## Autopilot Cron Prompt Templates`
- SKILL.md — version bump only

**Forward-look (Phase 5, final):** `--advisor=<agent>` (fork ambiguous DARs to a registered advisor before falling back to human), `--release-on-merge` (hold lock until PR merge), `/falcon retro --branch <name>` (branch-keyed stash synthesis for wrapup audit). After Phase 5, the autopilot rollout is complete and the epic `example-um2p` closes.

## 6.10.0 (2026-05-25)

**Autopilot Phase 3: `--auto-amend` + `--amendment-budget` HALT.** Third entry in the cron prompt template registry. The cron evaluates the `SAFE_TO_AMEND` whitelist against gaps surfaced from the dispatch's Step 3 validation + Step 3b cognitive audit; on whitelist match (and not in denylist, and budget allows), auto-issues an amendment to the dispatch file's `amendments[]` array and emits a `check amendments <dispatch-id>` block for the worker to pick up. `--amendment-budget N` caps the number of auto-issued amendments per dispatch; on exhaustion, the cron HALTs amendment issuance but the `--watch` and `--auto-ack` crons continue uninterrupted.

**What flipped from `⊘` to `✓`:**

- `--auto-amend` — autonomous amendment issuance via SAFE_TO_AMEND whitelist evaluation. Default cadence 5m (matches `--auto-ack`). Slug `falcon-amend-<dispatch-id>` extends the prefix-match teardown convention.
- `--amendment-budget N` — per-dispatch cap on `auto-issued:cron`-labeled amendments. Meaningless without `--auto-amend`. Recommended defaults per bead type seeded by `/falcon create-rules` into `falcon-autopilot.md § 6`.

**What was added to the schemas + conventions:**

- New dispatch file field `amend_cron_id: null` — mirrors `watch_cron_id` and `autoack_cron_id`.
- New dispatch file field `amendment_budget: null` — set by `--amendment-budget N`; null = no cap.
- New dispatch file field `auto_amendment_count: 0` — running counter, incremented by the cron on each auto-issue. Reset implicitly per dispatch.
- New scratch-file convention `.claude/tmp/falcon-amend-<dispatch-id>-state.json` — tracks last-evaluated gap-set hash + last fire outcome (issued / refused / deferred / halted / silent / no-gaps) so successive fires don't spam.
- New cron ID prefix `falcon-amend-<dispatch-id>` — `/falcon status` and `/falcon release-cron` discover this via existing prefix-match.

**Refuse-on-MVM (REQUIRED, inherits Phase 2 precedent for write-bearing flags).** Cron REFUSES when `falcon-autopilot.md` is missing or has every `# PROJECT —` whitelist item commented. Universal whitelist alone is NOT sufficient — `--auto-amend` issues amendments that cause the worker to write code, which is the largest blast radius of any autopilot flag in the rollout. Project must opt in.

**Budget HALT semantics:** when `auto_amendment_count >= amendment_budget`, the `--auto-amend` cron emits ONE `AMENDMENT BUDGET EXHAUSTED` block (on first detection) and stays silent on amendment evaluation for the rest of the dispatch. The cron self-cancels normally on terminal state (`session_status: complete`); budget exhaustion does NOT cancel the cron prematurely (other crons still benefit from its existence as a teardown reference). Manual amendments (issued by user or steering-relay) do NOT decrement the budget; only `auto-issued:cron`-labeled amendments count.

**Triple-cron coordination:** when `--watch --auto-ack --auto-amend` are all armed, three single-responsibility crons run side-by-side with independent slugs (`falcon-watch-`, `falcon-autoack-`, `falcon-amend-`) and independent sidecars. The prefix-match teardown via `/falcon release-cron` handles all three together. Cadences differ: watch 10m default, auto-ack and auto-amend 5m default. This is the maximum write-bearing autopilot surface; Phase 4's `--worker-cron` and `--autopilot` macro extend the model further but do not add new gate semantics.

**New copy-paste emission labels:** `AMENDMENT AUTO-ISSUED amend-NN` (successful auto-issue with the `check amendments <dispatch-id>` trigger), `AMENDMENT AUTO-ISSUE REFUSED` (MVM-refuse), `AMENDMENT AUTO-ISSUE DEFERRED` (no whitelist match OR matches denylist), `AMENDMENT BUDGET EXHAUSTED` (one-shot HALT signal), `AMEND CRON RELEASED` (self-cancel confirmation).

**Where each artifact lives:**

- COMMANDS.md — `--auto-amend ✓` flip with refuse-on-MVM + budget HALT notes; `--amendment-budget N ✓` flip with recommended-defaults pointer to `falcon-autopilot.md § 6`
- PROTOCOL.md — new subsection `### --auto-amend mode + --amendment-budget HALT (v6.10.0)` in Step 2 (between `--auto-ack mode` and `--dry-run mode`)
- REFERENCE.md — three new dispatch schema fields (`amend_cron_id`, `amendment_budget`, `auto_amendment_count`); `### --auto-amend cron prompt template (v6.10.0)` added as third entry in `## Autopilot Cron Prompt Templates` (~190 lines)
- SKILL.md — version bump only

**Forward-look (Phases 4-5):** Phase 4 adds `--worker-cron` + `--autopilot` macro (worker-side amendment-pickup cron + the full AFK bundle). Phase 5 adds `--advisor` + `--release-on-merge` + `/falcon retro`. Both inherit the refuse-on-MVM precedent for any new write-bearing flags.

## 6.9.0 (2026-05-25)

**Autopilot Phase 2: `--auto-ack` (first write-bearing cron).** Second entry in the cron prompt template registry established in v6.8.0. The cron evaluates the `SAFE_TO_ACK_INTENT` 4-gate predicate against the worker's intent paragraph on each fire; on all-pass, writes `intent_acknowledged_utc` to the dispatch file and emits the `proceed <dispatch-id>` block inline for relay to the worker. Workers gain a guard at intent-confirm that skips the manual pause when `intent_acknowledged_utc` is already non-null on resume — eliminating the double-prompt that would otherwise occur if a worker session restarts after the cron already acked.

**What flipped from `⊘` to `✓`:**

- `--auto-ack` — autonomous intent acknowledgement via 4-gate predicate. Default cadence 5m (shorter than `--watch`'s 10m because intent windows are brief). Slug `falcon-autoack-<dispatch-id>` extends the prefix-match teardown convention.

**What was added to the schemas + conventions:**

- New dispatch file field `autoack_cron_id: null` — mirrors `watch_cron_id` from Phase 1; carries the `CronCreate`-returned ID.
- New dispatch file field `intent_acknowledged_utc: null` — moved from forward-look comment (v6.6.0) to active field. Written by the auto-ack cron or by steering on manual relay.
- New scratch-file convention `.claude/tmp/falcon-autoack-<dispatch-id>-state.json` — tracks last-evaluated intent-paragraph hash so successive fires don't re-evaluate (or re-emit a defer/refuse block for) an unchanged intent.
- New cron ID prefix `falcon-autoack-<dispatch-id>` — `/falcon status` and `/falcon release-cron` discover this via the existing prefix-match (no command-side changes needed; both Phase 1 sub-commands already support it).

**Refuse-on-MVM (NEW design constraint for write-bearing autopilot).** Unlike Phase 1's `--watch` (which safely defaulted to minimum-viable mode when `.claude/rules/falcon-autopilot.md` had all PROJECT sections commented), Phase 2's `--auto-ack` REFUSES to operate in that state. The cron template emits an `AUTO-ACK REFUSED` block naming the specific gate the user should uncomment. Rationale: `--auto-ack` writes `intent_acknowledged_utc` which the worker treats as authorization to skip intent-confirm — writing without a project-confirmed gate has a much larger blast radius than report-only observation. Universal gates alone are NOT sufficient for write-bearing flags; the project must opt in. This MVM-refuse policy is the precedent for Phase 3-5's later write-bearing flags.

**Dual-cron coordination with `--watch`:** when both flags are armed, two independent crons run side-by-side (10m watch + 5m auto-ack). They do not coordinate; each evaluates its own state-change criteria. The prefix-match teardown convention handles multi-cron-per-dispatch cleanly via `/falcon release-cron`. Combining them was rejected at Phase 2 design time because flag-aware branching inside a single cron template adds complexity for marginal cron-count savings.

**New copy-paste emission labels:** `AUTO-ACK REFUSED` (MVM-refuse block), `AUTO-ACK DEFERRED` (gate-fail defer block), `INTENT AUTO-ACK` (successful auto-ack with the `proceed <dispatch-id>` block), `AUTO-ACK CRON RELEASED` (self-cancel confirmation). Per v6.5.3 labeled-copy convention.

**Where each artifact lives:**

- COMMANDS.md — `--auto-ack ✓` flip with refuse-on-MVM note + worker-side guard note + cross-links to PROTOCOL.md and REFERENCE.md
- PROTOCOL.md — new subsection `### --auto-ack mode (autopilot intent acknowledgement, v6.9.0)` in Step 2; Worker Lifecycle Step 3 gains the auto-ack-resume guard (in-place edit to the existing Step 3 description)
- REFERENCE.md — `autoack_cron_id` and `intent_acknowledged_utc` added to Dispatch File YAML Schema; `### --auto-ack cron prompt template (v6.9.0)` added as second entry in `## Autopilot Cron Prompt Templates` (~140 lines)
- SKILL.md — version bump only

**Forward-look (Phases 3-5, beads under `example-um2p`):** Phase 3 adds `--auto-amend` + `--amendment-budget` HALT; Phase 4 adds `--worker-cron` + `--autopilot` macro; Phase 5 adds `--advisor` + `--release-on-merge` + `/falcon retro`. Each future write-bearing flag inherits the refuse-on-MVM precedent established in this version.

## 6.8.0 (2026-05-25)

**Autopilot Phase 1: `--watch` cron foundation + 4 immediate `⊘`→`✓` flips.** First cut of the autopilot rollout sequenced under epic `example-um2p`. The artifact this version lands is the **cron prompt template registry** in REFERENCE.md — every subsequent autopilot phase (Phases 2-5) extends this template, so Phase 1 is intentionally documentation-only (no live cron is fired during this change; the template IS the deliverable).

**What flipped from `⊘` to `✓`:**

- `--watch[=Nm]` — steering-side cron in report-only mode. Fires every N minutes (default 10m); emits a status block inline only when state changes. Self-cancels on `session_status: complete`. The cron is the foundational artifact — every subsequent autopilot flag (`--auto-ack`, `--auto-amend`, `--worker-cron`) extends the prompt template authored here.
- `--cron-cadence Nm` — override the default. 10m default for `--watch` (Phase 1); future Phase 2 `--auto-ack` defaults to 5m per the cache-cost analysis.
- `--dry-run` — print what the dispatch + cron would look like without any persistent state mutation. Shows resolved bead set, derived file_scope, lock-registry check (read-only), autopilot policy effects, and the literal cron prompt body that would have been scheduled.
- `/falcon status <dispatch-id>` — manual one-shot status query; the human equivalent of a single `--watch` cron fire. Useful when no watch cron is armed but a quick read is wanted.
- `/falcon release-cron <dispatch-id>` — tear down the watch/autopilot cron associated with a dispatch via `CronList` prefix-match + `CronDelete`. Does NOT release the dispatch lock; only the cron + sidecar snapshot file.

**What was added to the schemas + conventions:**

- New dispatch file field `watch_cron_id: null` — set by steering at Step 2 when `--watch` is armed; carries the `CronCreate`-returned ID for the watch cron. `/falcon status` and `/falcon release-cron` use this for lookups.
- New scratch-file convention `.claude/tmp/falcon-watch-<dispatch-id>-state.json` — per-cron sidecar carrying last-observed-state snapshot so successive fires can detect transitions. The cron writes after each fire; the snapshot is removed on self-cancel (terminal state) or by `/falcon release-cron`.
- New cron ID naming convention `falcon-watch-<dispatch-id>` — Phase 1 slug. Future phases extend the prefix set (`falcon-autoack-<dispatch-id>`, `falcon-amend-<dispatch-id>`, etc.) so the lookup tooling stays prefix-match-driven.
- New top-level section in REFERENCE.md `## Autopilot Cron Prompt Templates` — the registry every future phase appends to. First entry: `### --watch cron prompt template (v6.8.0)`.

**Where each artifact lives:**

- COMMANDS.md — the 5 status-legend flips with updated spec text + minimum-viable-mode note for `--watch`
- PROTOCOL.md — new subsections `### --watch mode (autopilot observability foundation, v6.8.0)` + `### --dry-run mode` in Step 2; `### /falcon status <dispatch-id>` + `### /falcon release-cron <dispatch-id>` in Step 5
- REFERENCE.md — `watch_cron_id` added to Dispatch File YAML Schema with snapshot-file note; `## Autopilot Cron Prompt Templates` section added as new top-level registry
- SKILL.md — version bump only

**Forward-look (Phases 2-5, each a separate bead under `example-um2p`):**

- **Phase 2** — `--auto-ack` (steering-side cron writes `intent_acknowledged_utc` when `SAFE_TO_ACK_INTENT` 4-gate passes) + worker-lifecycle guard in Step 3 (skip intent-confirm if already acknowledged on resume).
- **Phase 3** — `--auto-amend` + `--amendment-budget` HALT (whitelist-driven amendment issuance, budget cap blocks writes when exhausted; watch function continues).
- **Phase 4** — `--worker-cron` + `--autopilot` macro (worker-side amendment-pickup cron + the full AFK bundle `--auto-ack --auto-amend --worker-cron --watch`).
- **Phase 5** — `--advisor=<agent>` + `--release-on-merge` + `/falcon retro --branch <name>` (advisor delegation for ambiguous DARs; hold lock until PR merge; branch-keyed stash synthesis for wrapup audit).

**Minimum-viable mode:** when `.claude/rules/falcon-autopilot.md` exists but every `# PROJECT —` section is commented (the post-`/falcon create-rules` default), `--watch` does NOT refuse — report-only mode does not need the project gates. Those become load-bearing under Phase 2+ flags that gate writes against `SAFE_TO_ACK_INTENT` / `SAFE_TO_AMEND`.

## 6.7.0 (2026-05-25)

**Thin pointer-style init_prompt template + extracted Worker Return Contract.** The default `init_prompt` template (lines ~200+ in every dispatch since v6.0) duplicated content that already lives canonically in PROTOCOL.md + REFERENCE.md: the 13-step Worker Lifecycle, the DAR protocol, the labeled-copy emission convention, and the full Worker Return Contract YAML schema. v6.7.0 strips that duplication.

**What changed:**

- The default `init_prompt` template (REFERENCE.md `## init_prompt Content Template (default: thin / pointer-style)`) is now ~70-90 lines instead of ~200+. It contains only per-dispatch content: branch verify, bead pointer table, steering session notes, optional pre-intent grep block, project-rules pointer.
- The thin template points workers at three canonical skill-file sections for everything else:
  1. `PROTOCOL.md "## Worker Lifecycle (inside the dispatch)"` — the 13-step lifecycle
  2. `REFERENCE.md "## Worker Return Contract"` (NEW top-level section, extracted from the old template) — the YAML report schema
  3. `REFERENCE.md "## Copy-Paste Emission Convention"` (existing) — INTENT / COMPLETION / AMENDMENT label conventions
- PROTOCOL.md "## Worker Lifecycle" gains a v6.7.0 preamble noting it is now the canonical reference for workers.
- `--paste` mode gets a new dedicated section `REFERENCE.md "## init_prompt Content Template (--paste mode: fully inlined)"` describing how the steering session expands the three pointers inline for cross-network workers without filesystem access. Paste-mode init_prompts stay ~200-300 lines; this is the documented exception.
- COMMANDS.md `--paste` flag spec gains the inline-expansion note.

**Why this matters:**

- **Single source of truth.** Protocol updates land in PROTOCOL.md and REFERENCE.md; all future dispatches pick them up automatically. Old dispatch files don't carry stale spec.
- **Smaller dispatch files.** Each per-dispatch YAML drops ~150 lines. Multi-bead and multi-worker sprints benefit linearly.
- **No drift risk.** Pre-v6.7.0, an init_prompt template change in REFERENCE.md required regenerating the in-flight dispatch files (or accepting that workers continued running against old spec). v6.7.0+ workers always read the live skill files.
- **Compatible with the v6.5.3 labeled-copy convention + v6.6.0 autopilot rules.** No semantic changes — only the placement / referencing changes.

**Migration:**

- Active dispatches at the v6.6.0 verbose-template format keep running with their existing init_prompts (no in-flight rewrite). New dispatches use the thin template.
- The lifecycle, return contract, and DAR protocol are unchanged — only the template that wraps them moved.

**Caveat:**

- The thin template assumes the worker can Read filesystem files at `.claude/skills/falcon/{PROTOCOL,REFERENCE}.md`. For workers that genuinely can't (browser-tab worker on a different machine, no shared filesystem), use `--paste` — it auto-inlines the three sections.

## 6.6.0 (2026-05-25)

**Add `/falcon create-rules` command + `falcon-autopilot.md` template.** First wire-in for the autopilot rules file that the proposed (`⊘`) autopilot flag bundle (`--auto-ack`, `--auto-amend`, `--worker-cron`, `--advisor`, `--amendment-budget`) is specified to consume.

The command is `✓` implemented (deterministic file generator); the consumer flags remain `⊘` (proposed). The rationale for landing the producer before the consumer: the rules file is a forward-looking project policy spec that benefits from review-and-iterate cycles independent of when the consumer ships. Authoring it now means the autopilot rollout has a concrete project target.

**What the command does:**

- Writes `.claude/rules/falcon-autopilot.md` from the template in [`REFERENCE.md`](./REFERENCE.md#falcon-autopilotmd-template)
- Refuses to overwrite an existing file unless `--force`; `--force` archives the prior version to `.archive/falcon-autopilot-<timestamp>.md`
- Reads the project's existing rule files (`.claude/rules/standards.md`, `development-standards.md`, `workflow-execution.md`, `workflow-agents.md`) to seed project-specific gate placeholders with sensible defaults

**Template structure** (six sections — universal sections fixed, project sections placeholder-with-examples):

1. `SAFE_TO_ACK_INTENT` predicate (4-gate)
2. `SAFE_TO_AMEND` whitelist (universal + project additions)
3. `SAFE_TO_AMEND` denylist (universal + project additions)
4. Bead-type-specific cognitive audit hints
5. Advisor delegation policy (`/quartermaster`, `/herald`, etc.)
6. Default amendment budget per bead type

**Flags:** `--force` (overwrite + archive prior), `--dry-run` (print without write), `--bead-types <list>` (customize cognitive-audit section).

Sources COMMANDS.md `/falcon create-rules ✓` for full command spec; REFERENCE.md `## falcon-autopilot.md Template` for the body.

---

## 6.5.3 (2026-05-23)

**Unified labeled-copy convention across both directions + timestamp on all worker→steering emissions.** Two related gaps folded into one patch:

(a) **v6.5.2 added timestamps to completion + amendment-completion emissions but missed intent emissions.** Same correlation problem applies — multiple parallel dispatches produce interleaved intent acks; without a timestamp, sorting + correlation is guesswork. v6.5.3 extends the UTC ISO8601 timestamp convention to intent emissions.

(b) **v6.3.1 added the `═══ COPY ═══` wrap to steering→worker emissions (dispatch prompt, amendments, scope-expansion revisions) but did NOT wrap worker→steering emissions (intent, completion, amendment completion).** This asymmetry made it awkward to relay a worker emission back to the steering thread for review: no clear boundary to copy, no self-describing metadata on paste. v6.5.3 extends the wrap to all worker→steering emissions and adds a markdown `##` heading layer above the existing fence carrying `LABEL — dispatch <id> at <UTC ISO8601>`.

**Unified format (both directions):**

```
## LABEL — dispatch <id> at <UTC ISO8601>

═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
~~~
<content>
~~~
═══ END COPY ═══
```

Labels: `DISPATCH PROMPT`, `AMENDMENT amend-NN`, `SCOPE-EXPANSION REVISION` (steering→worker); `INTENT`, `COMPLETION`, `AMENDMENT COMPLETION amend-NN`, `AMENDMENT SATISFIED amend-NN`, `AMENDMENT REJECTED amend-NN` (worker→steering). Extensible — projects can define additional labels as new emission types emerge.

**Relay-for-review pattern:** when the user wants to send a worker emission back to the steering thread for review, copy from the `##` heading through the `═══ END COPY ═══` line — both inclusive. The heading travels with the paste, so steering knows what it's looking at without the user adding narrative context.

**Side benefit:** the `##` headings make the steering transcript scannable — grep for "## DISPATCH PROMPT" or "## AMENDMENT" across multiple parallel dispatches finds specific exchange points.

**Backward compatibility:** doc-only change. Steering does NOT parse the signal string (the `implementation_results_hash` gate is the real completion signal), so workers emitting the older bare-string format still validate. Workers SHOULD migrate to the wrapped format on next dispatch; steering SHOULD accept either form during the migration window.

## 6.5.2 (2026-05-22)

Completion signal MUST include UTC ISO8601 timestamp — format: `"Work stream completed at <UTC ISO8601>. Re-read <dispatch-file-path>."` (or `"Work stream partial at <UTC ISO8601>. ..."` for partial reports). Same convention applies to amendment-completion signals (`"Amendment <id> completed at <UTC ISO8601>. ..."`, `satisfied`, `rejected`). Rationale: long-running async dispatches accumulate multiple completion messages in the steering thread; without timestamps, sorting + correlation is guesswork. Timestamp is the wall-clock time the worker emitted the signal (typically equal to the `completed` field in `falcon_report` for the initial dispatch; for amendments, the per-amendment `worker_completed_utc`). Doc-only change; backward compatible (steering does not parse the signal string — it reads dispatch-file content via the hash gate). Workers should generate the timestamp at emission time via `date -u +%Y-%m-%dT%H:%M:%SZ` or equivalent.

## 6.5.1 (2026-05-22)

Renamed `vacuous` amendment status → `satisfied` (clearer semantic, less academic word, pairs better with `worker_response` as the satisfaction evidence). Also expanded the `satisfied` definition to cover TWO cases: (i) trigger no longer applies / nothing to do (the original "vacuous" intent), AND (ii) work was performed outside this amendment cycle (user pre-edits, sibling work, parent bead commit covers it) — verified by worker, no new commits from this amendment branch. A worker emitted a novel `applied_pending_commit` status trying to capture case (ii); v6.5.1 folds that need into the now-broader `satisfied`. Schema rename; v6.5.0 dispatch files with `vacuous` status still parse correctly (steering normalizes `vacuous` → `satisfied` on read for backward compat).

## 6.5.0 (2026-05-22)

Amendment-status discipline tightened (post-incident). Three changes:

(a) New `vacuous` amendment status added — for the case where amendment intent is already satisfied (e.g., user pre-edits in worktree cover the amendment's request; prior amendment subsumed it; trigger condition no longer applies). Worker sets `status: vacuous` with a worker_response citing the verification (e.g., "grep confirms power-up-shop/server.ts refs already present from user pre-edits; no new commits needed"). Distinct from `completed` (work was performed) and `rejected` (work is impossible/contradictory).

(b) Step 3 validation strengthened — new step 5 (amendment-status discipline audit) checks all amendments are in a terminal state (`completed`, `vacuous`, or `rejected`) before lock release; non-terminal status holds the lock pending resolution.

(c) Step 3b cognitive audit prompt added as backstop for the mechanical step 5 check.

A prior dispatch surfaced the gap: worker stopped on a high-stakes DAR with amend-01 still in `status: pending`; protocol had no mechanical gate to catch this. Schema additive; backward-compatible.

## 6.4.0 (2026-05-22)

`--sequential` flag added — opt-in override of the Step 1 self-conflict check for the single-worker case. When set, two or more beads with overlapping `file_scope`s are allowed in the same dispatch because one worker handles them in declared order (inheriting context cleanly, avoiding merge conflicts, saving ~10-20 steering turns vs the 2-dispatch sequential pattern). CLI list-order is the default execution order; bd `blocked_by` ordering wins if present; bead-body "Patterns to Reuse" text scan flags likely mis-orderings and prompts steering to confirm before dispatch-file write. Worker iterates per-bead (claim → implement → verify → commit with per-bead `Closes:` → close → next). Failure mid-bead-N leaves 1..N-1 cleanly closed; N reports in_progress/blocked; N+1..end deferred. Default HARD-reject remains for non-`--sequential` overlapping-bead invocations. example-t0l.

## 6.3.1 (2026-05-22)

Copy-paste emission convention added to "The Dispatch Prompt Template" section. Steering now wraps multi-line paste blocks (dispatch prompts, amendments, scope-expansion revisions) in explicit boundaries: sentinel header `═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══` + tilde fence `~~~` (not backticks, so command-syntax backticks in content don't need escaping) + paste content + closing tilde fence + sentinel footer `═══ END COPY ═══`. Eliminates ambiguity between steering narrative and worker-bound content. Single-line emissions (e.g., bare `proceed <id>`) skip the convention. Doc-only change; no protocol-breaking shift.

## 6.3.0 (2026-05-21)

Eleven improvements from post-ckl.6 wrapup feedback.

(11) `/falcon list-sessions` + `/falcon release-session <session-id>` — session-level discovery + bulk release for dead worker sessions that held multiple dispatches. list-sessions groups by session (not dispatch) with staleness flags + suggested cleanup. release-session removes every entry from a session's `falcon_dispatches[]` in one shot and archives the session JSON, instead of requiring N invocations of `/falcon release`.

(1) Step 3c: steering-side cognitive audit added — "is there a project-binding concern the AC didn't gate on?" before lock release.

(2) Smart auto-release in Step 4 — when steering pastes worker completion, Step 4 stashes + auto-releases the lock IF the safe-to-release predicate holds (validation clean, cognitive audit clean, no unresolved DARs, no queued amendments). When the predicate fails, Step 4 holds the lock and surfaces the reason; lock naturally persists across amendment cycles. /falcon release <id> stays as manual escape hatch for stale locks and auto-release-declined cases.

(3) Intent-confirm adds optional one-line "approach" sentence — surfaces implementation strategy (programmatic vs fan-out, etc.) without requiring a full plan.

(4) Amendment numbering standardized: amend-01, amend-02, ... (was ad-hoc v2/v3); initial dispatch has no amendment_id.

(5) results_complete sentinel replaced by content hash: implementation_results_hash field — steering verifies sha256(implementation_results content) matches before parsing to detect mid-write crashes.

(6) paste_fallback mode re-documented — for workers on a different machine/browser/cross-network; --paste flag mirrors --skip-intent/--inline-beads.

(7) Stash amendments append-only — each report's amendments field grows by append; never overwrite.

(8) Per-bead-type validation hints in Step 3 taxonomy — falcon documents 3 universal patterns (post-commit grep for migration/rename beads, schema-contract recheck, sibling-bead output-shape match); project-specific hints live in the project's own rule or doc files (e.g., `.claude/docs/work-item-templates.md` or `.claude/rules/validation-hints.md`), NOT inlined here.

(9) Explicit session_status field added to dispatch file: active | amendments_pending | complete — set by steering, checked by worker on resume.

(10) Dead-worker amendment constraint documented prominently in Amendments Workflow section header.

## 6.2.1 (2026-05-21)

Document the load-bearing `tr '/' '-'` branch-name sanitization for the stash path. Behavior was already in the writer; doc said only `git rev-parse --abbrev-ref HEAD` which led `/wrapup` v2.3.0 to derive the wrong path for feature/* branches. All path templates updated from `<branch>` to `<sanitized-branch>` so consumers know to apply the transform.

## 6.2.0 (2026-05-21)

Amendments mechanism. Steering session can write follow-up instructions to a still-active worker (after initial completion but before lock release) via an `amendments[]` array in the dispatch file. Worker re-reads dispatch file on resume prompt, finds pending amendments, executes them, writes worker_response per amendment, emits "amendment <id> completed" message. Lock stays held until steering explicitly releases. Supports iterative gap-closing without re-dispatch overhead: take next steps that emerged from validation, resolve test flakiness, etc. Amendments skip intent-confirm by default (steering already specified the request); worker proceeds directly to execute. Schema additive — no protocol-breaking change.

## 6.1.0 (2026-05-21)

Worker emits intent paragraph(s) INLINE in chat output (alongside file write) at the intent-confirm pause, so the human can ack directly without bouncing to the orchestrator to read the dispatch file. Additive UX improvement; no protocol-breaking change. Same applies to completion summary — workers can paste a short preamble verbatim instead of forcing the orchestrator to re-read the dispatch file for routine acks.

File-based dispatch protocol with pre-dispatch grep audit + worker pre-intent grep verification for migration/rename beads. Per-dispatch YAML file at `.claude/tmp/falcon-dispatch-<6hex>.yaml` with 4 named sections (`init_prompt`, `implementation_intent`, `out_of_spec_approval_requests`, `implementation_results`) + `results_complete` sentinel. Lock registry via session JSON `falcon_dispatches[]` array; cross-session aggregation prevents two workers from claiming the same files. HARD reject on file/directory conflict at dispatch time. Pointer-style bead set default (worker bd-shows the body); `--inline-beads` opt-in for self-contained dispatches. Intent-confirm pre-flight default; `--skip-intent` opt-out for unambiguous dispatches. Bead body sanity check at dispatch time for beads referencing multi-section design spikes. Multi-worker coordination via human-relay only (no polling). `/falcon release <dispatch-id>` for manual stale-lock cleanup. Assumes shared filesystem + shared branch between steering and worker sessions.
