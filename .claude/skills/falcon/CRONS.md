# Falcon — Cron Prompt Templates

> Cron prompt templates for the falcon dispatch system. Split out of `REFERENCE.md` at v7.2.0 when the parent file exceeded the 1500-line tripwire documented in `falcon-dev/.claude/architecture.md` Design Decisions.
>
> **What lives here:**
> - `## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)` — worker-side self-poll crons armed at intent-emission + DAR-pause-for-response points
> - `## Autopilot Cron Prompt Templates` — the 5 steering-side autopilot crons (`--watch`, `--auto-ack`, `--auto-amend`, `--worker-cron`, `--release-on-merge`) with full Step 0-N specs + v7.1.2 condensed `CronCreate` prompts
> - Shared cron infrastructure subsections: `### Cron Telemetry Instrumentation (v7.1.0, fdev-lbq.30)`, `### Cron Dispatch-Mode Conventions (v7.0.1)`, `### Wake-opportunism convention (v7.7.0)`, `### claude agents CLI surface (v7.0.1)`
>
> **What does NOT live here:**
> - Dispatch file YAML schema → see [`REFERENCE.md`](./REFERENCE.md#dispatch-file-yaml-schema) `## Dispatch File YAML Schema`
> - init_prompt content templates → see [`REFERENCE.md`](./REFERENCE.md#init_prompt-content-template-default-thin--pointer-style) `## init_prompt Content Template`
> - Worker return contract → see [`REFERENCE.md`](./REFERENCE.md#worker-return-contract) `## Worker Return Contract`
> - Steering-side dispatch protocol → see [`PROTOCOL.md`](./PROTOCOL.md)
> - falcon-autopilot.md rules-file template → see [`AUTOPILOT-RULES.md`](./AUTOPILOT-RULES.md)

---

## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)

Literal `CronCreate` substitution blocks referenced by REFERENCE.md `## init_prompt Content Template` § `### Worker self-poll at pause points (--bg mode only, v7.1.1)` and by PROTOCOL.md `### Worker self-poll at pause points (v7.1.1)`. The worker substitutes `{{ dispatch_id }}` and `{{ dispatch_file_path }}` (and DAR `request_id` where applicable) into the prompt string at CronCreate time from its bootstrap context. Both crons are armed by the WORKER, not steering.

**Role split (load-bearing).** The cron's prompt is a *wake nudge with state-check instructions*. When the cron fires, its prompt is delivered to the worker session as a user-message-style notification. The WORKER, which holds the cron ID in session memory from the `CronCreate` return value, interprets the prompt, checks the dispatch file, and — if the wait condition is satisfied — calls `CronDelete(captured_id)` and resumes past the pause point. The cron prompt does NOT need a `<self-id>` placeholder because the WORKER does the cleanup using the ID it captured at arm time.

**At intent emission** — after writing `implementation_intent` and BEFORE the STOP-await-ack pause at Worker Lifecycle Step 3:

```
# Worker captures the returned cron ID in session memory.
intent_self_poll_cron_id = CronCreate(
  cron="*/2 * * * *",
  recurring=true,
  durable=false,
  prompt="Worker self-poll for dispatch {{ dispatch_id }}. Re-read
          {{ dispatch_file_path }}. If `intent_acknowledged_utc` is
          non-null: CronDelete this self-poll cron (worker holds its
          ID in session memory from CronCreate's return value), then
          resume past intent-confirm into Step 4 (`bd update -s
          in_progress` + claim). Otherwise silent."
)
```

Predicate is intentionally `intent_acknowledged_utc != null` alone (no commit-attribution check). At this pause point, no commits could have landed for this dispatch yet by construction — the worker is paused BEFORE Step 4 (`bd update -s in_progress`), and no Step-8 commits could exist. The `CronDelete`-on-wake convention is the load-bearing safety, not a defensive predicate. Contrast with PROTOCOL.md Step 3's *auto-ack-resume guard* which uses a richer predicate because it runs on session resume and must disambiguate against "ack consumed by an earlier session" history.

**At DAR pause for response** — after writing an `out_of_spec_approval_requests[]` entry with `response: null` IF the worker stays alive waiting on the response (rather than partial-reporting per the HIGH-stakes DAR path in PROTOCOL.md `### DAR protocol`):

```
# Worker captures the returned cron ID in session memory.
dar_self_poll_cron_id = CronCreate(
  cron="*/3 * * * *",
  recurring=true,
  durable=false,
  prompt="Worker self-poll for dispatch {{ dispatch_id }} DAR
          request_id=<id>. Re-read {{ dispatch_file_path }}. If the
          out_of_spec_approval_requests[] entry with request_id=<id>
          has its `response` field non-null: CronDelete this self-poll
          cron (worker holds its ID in session memory) and resume to
          incorporate the response. Otherwise silent."
)
```

Predicate is `response != null` on the specific DAR entry — a 1-bit signal matching this pause's wait condition exactly.

**Mode applicability.** Both blocks are `--bg`-mode only. In `--via-paste` / `--paste` modes, do NOT arm these crons — the operator's `proceed {{ dispatch_id }}` paste (or the worker-cron polling the dispatch file in `--via-paste`) is the wake mechanism. The template's mode-skip note enforces this; this section documents the literal block for that conditional.

**Scope guardrail.** Arm ONLY at the two pause points above. Never arm an always-on background poller. `durable: false` is mandatory — the cron must die with the worker session if the operator kills the agent. Recurring crons auto-expire after 7 days per the `CronCreate` contract; this bounds the worst-case orphaned-cron lifetime if `CronDelete` is ever missed.

## Autopilot Cron Prompt Templates

Templates for the prompts that steering-side CronCreate fires against a specific dispatch. Each template embeds the literal dispatch ID at CronCreate time — there are no generic crons. The cron reads the dispatch file at fire time to learn `repo_path` and other per-dispatch context.

Cron ID naming convention: `falcon-watch-<dispatch-id>` (Phase 1, this section). Future phases extend the slug (e.g., `falcon-autoack-<dispatch-id>`, `falcon-amend-<dispatch-id>`) so `/falcon status` and `/falcon release-cron` can do prefix-match lookups via `CronList | grep '<slug>-<dispatch-id>'`.

Snapshot-file convention: each cron-armed dispatch gets a sidecar `.claude/tmp/falcon-watch-<dispatch-id>-state.json` (one per cron slug per dispatch) that carries the cron's last-observed state so successive fires can detect transitions. The cron writes after each fire; the snapshot is removed on self-cancel (terminal state) or by `/falcon release-cron`.

This section is the registry. Phase 1 (v6.8.0) lands the `--watch` template; subsequent phases append additional templates here as they ship.

### Cron-schedule offset staggering (v7.0.1, fdev-lbq.5)

The `CronCreate` examples in each template below use `cron: "*/<N> * * * *"` for readability — but at substitution time, steering Step 2 SHOULD compute offset-staggered cron expressions per dispatch so multiple crons don't bunch their fires at the same minute boundary.

Without staggering, every `*/N` cron fires at minutes divisible by N (e.g. `*/4` fires at :00, :04, :08, …). When 3-4 crons share a dispatch (watch + auto-ack + auto-amend + release-on-merge), several can fire in the same wall-clock minute — observed in production retro as "3 crons firing in one steering turn" bursts.

Recommended substitution at Step 2 (per dispatch — different dispatches can pick different offsets to spread load further):

| Cron | Default cadence | Staggered cron expression (offset N) |
|------|-----------------|--------------------------------------|
| `--watch` | 11m | `1,12,23,34,45,56 * * * *` (offset 1 from minute boundary) |
| `--auto-ack` | 5m | `2,7,12,17,22,27,32,37,42,47,52,57 * * * *` (offset 2) |
| `--auto-amend` | 7m | `4,11,18,25,32,39,46,53 * * * *` (offset 4) |
| `--release-on-merge` | 15m | `5,20,35,50 * * * *` (offset 5) |

The LCM of cadences (5, 7, 11, 15) is 1155 minutes — total alignment cycle is ~19hr. Within any given minute, at most 1 cron should fire if the offsets are chosen carefully. The `*/N` shorthand in each template below is the simplified form; steering MAY emit the staggered form at CronCreate-time without changing semantics.

If the cadence is overridden via `--cron-cadence Nm`, the offset SHOULD shift to maintain LCM-minimization. A reasonable heuristic: pick `offset = (cron_slug_hash mod N)` where `cron_slug_hash` is the SHA256 of `falcon-<role>-<dispatch-id>` reduced to an integer. This deterministically spreads multiple dispatches across the cycle.

### Two cadence-adaptation mechanisms (v7.1 spec; impl deferred)

Falcon's v7.0.1 + v7.1 cron cadence model has TWO orthogonal adaptation mechanisms operating at different scales:

1. **Per-fire Step 0 adaptive cadence guards (v7.0.1, fdev-lbq.2 + fdev-lbq.3)**: each `--auto-ack` and `--auto-amend` cron template carries a Step 0 early-exit guard that probes the dispatch file's state-driving fields via a minimal yq query and exits silently when there's nothing to do. **Token cost** is what adapts (the cadence itself stays fixed at the CronCreate-assigned schedule). Implemented in v7.0.1.

2. **Per-phase cadence re-arming via CronCreate (v7.1.0 LIVE, fdev-lbq.29 implements fdev-lbq.27 spec)**: steering observes dispatch lifecycle phase (computed from existing fields per PROTOCOL.md `### Mode selection + detection` §"Dispatch lifecycle phases") and on each phase transition, performs CronDelete-then-CronCreate to RE-ARM each cron at the phase-appropriate cadence. **The cadence itself** is what adapts (Step 0 still fires per the same CronCreate-assigned schedule, just at a different schedule across phases). Handler runs at Step 4 before auto-release; the `/falcon transition <dispatch-id>` operator command (fdev-lbq.31 pending) fills the non-Step-4 invocation gap. Watch-cron no-op optimization skips CronDelete/CronCreate when new_cadence == current_cadence (still records forensic entry in cron_re_arms[]).

3. **Forecast-driven initial cadence (v7.1.0 LIVE, fdev-lbq.28 implements fdev-lbq.25 spec)**: at dispatch-time Step 2, steering parses the bead's Effort Forecast Total turns + Confidence and selects a bucket (short/medium/long) for each cron's initial CronCreate cadence. See PROTOCOL.md `### Mode selection + detection` §"Forecast-driven initial cadence" for the bucket table and parser pseudocode.

The three mechanisms compose: **forecast picks the initial bucket** (.28, live); **per-phase re-arm shifts the cadence as the dispatch progresses** (.27, pending impl); **Step 0 makes each fire cheap when state hasn't shifted** (.2/.3, live). When all three ship, autopilot crons should land on signal-density > 30% across the dispatch lifetime per the .6 telemetry validation.

### `claude agents` CLI surface (v7.0.1)

Reference table of the Claude Code `claude agents` (and adjacent `claude <verb>`) commands that falcon cron templates + operators can use. Falcon does NOT wrap these — they're used directly per the upstream docs at https://code.claude.com/docs/en/agent-view. This subsection exists so cron-template authors and operators don't have to leave the falcon docs to look up the surface.

| Command | What it does | Falcon use case |
|---------|--------------|-----------------|
| `claude agents` | Open agent-viewer TUI (interactive) | Operator monitor; not used by crons. |
| `claude agents --cwd <path>` | Filter agent-viewer to sessions started under `<path>` (v2.1.141+) | Per-project session filtering. Operators with multi-project setups. |
| `claude agents --json` | Print live sessions as JSON array and exit. Each entry: `pid`, `cwd`, `kind`, `startedAt`, `sessionId`, `name`, `status`. Combine with `--cwd <path>` to filter. | **Cron-driven state reads in `--bg` mode** — the canonical machine-readable surface. Used by `--watch` and `--auto-ack` crons for live session state. |
| `claude attach <id>` | Attach to a session in the current terminal (interactive) | Operator-only; not scripted. |
| `claude logs <id>` | Print the session's recent output | Operator-only; not used by crons. |
| `claude stop <id>` (alias `claude kill`) | Stop a session's process. State preserved on disk; restart on attach/peek/reply. **NOT a terminal kill** — agent-viewer row stays. | Pause-but-resume; rarely used by falcon directly. |
| `claude rm <id>` | Remove a session from agent-viewer. Transcript preserved on disk (reachable via `claude --resume`). Claude-created worktree removed if no uncommitted changes. **This is the terminal-kill primitive.** | Used by `/falcon release` post-completion to clear agent-viewer row (per fdev-lbq.18). |
| `claude respawn <id>` | Restart a session (running or stopped) with conversation intact. Distinct from `/falcon respawn-fresh`. | Pick up an updated Claude Code binary mid-dispatch; falcon does not use this directly. |
| `claude respawn --all` | Restart every running session | Operator escape hatch; not scripted. |
| `claude --bg --name "<name>" "<bootstrap>"` | Spawn a detached background session with the given name + bootstrap prompt; prints short ID + name | Used by falcon Step 2 in `--bg` dispatch mode. |
| `claude --version` | Print Claude Code version | Used by falcon Step 2 version gate (≥ 2.1.139 for `--bg`). |
| `claude daemon status` | Print supervisor state, version, socket directory, worker count | Operator diagnostic. |
| `claude --resume <session-name>` | Resume a previously-saved interactive session | **NEVER use against a running `--bg` session** — rejected with "session running as bg agent" error. See Cron Dispatch-Mode Conventions below. |
| `claude --fork-session` | Branch off a copy of a session | **NEVER use for falcon dispatches** — creates duplicate session violating single-worker-per-dispatch invariant. See Cron Dispatch-Mode Conventions below. |

**Anti-patterns explicitly documented above:** `claude --resume` and `claude --fork-session` are listed so cron-template authors and AI assistants seeing them suggested in error messages know NOT to reach for them. Both are valid in other Claude Code contexts (resume a saved interactive session; branch off for experimental exploration), but neither fits falcon's running-`--bg`-worker model.

### Cron Telemetry Instrumentation (v7.1.0, fdev-lbq.30)

Every autopilot cron template carries a telemetry-counter contract — on each fire entry, increment `cron_telemetry.<slug>.fires`; before exit, classify the outcome and increment EITHER `silent` (Step 0 early-exit OR no state change detected by Step 1+) OR `useful` (Step 1+ executed any real work: emitted a STATE/fence block, wrote to the dispatch file, called CronDelete/CronCreate, etc.). The atomic-write discipline that already governs dispatch-file edits applies — counter increments are dispatch-file writes; the same locking + write-temp-then-rename pattern preserves correctness under concurrent fires.

**Slug map (`<slug>` in `cron_telemetry.<slug>`):**

| Cron type | Slug | Notes |
|-----------|------|-------|
| `--watch` | `watch` | Always armed in `--autopilot`; cadence × 1 across phases |
| `--auto-ack` | `autoack` | CronDelete'd on `implementation` transition per fdev-lbq.29 |
| `--auto-amend` | `amend` | Peak in `verify_amendment` phase |
| `--worker-cron` | `worker` | `--via-paste` only (no-op in `--bg`) |
| `--release-on-merge` | `merge` | Optional flag; PR-merge polling |

**Invariant**: for any slug, `fires == silent + useful` at all times. A fire that crashes mid-execution (rare; the cron prompt is short-running) leaves `fires` incremented but neither `silent` nor `useful` — this is the only legitimate accumulated drift and surfaces in /falcon retro as an unaccounted-for delta.

**Source attribution (v7.7.0, wake-opportunism):** when work is executed opportunistically on another trigger's wake (per `### Wake-opportunism convention (v7.7.0)` below), the EXECUTING role's slug takes the `fires`/`useful` increments, and the telemetry entry gains a `source=` label naming the actual trigger (e.g. `source=opportunistic-via-amend-cron`, `source=steering-manual-review`). The `fires == silent + useful` invariant is explicitly UNCHANGED: opportunistic execution increments `fires` and `useful` together under the executing role's slug; the triggering cron's own slug counts only its own role's outcome. Precedent recorded on dispatch b92a16's telemetry (2026-06-13).

**Backward compat**: dispatches predating v7.1.0 have `cron_telemetry: {}` (empty object — the schema field was reserved in v7.0.1). On first fire after upgrade, each cron initializes its sub-map. /falcon retro emission gracefully reports "telemetry not available" for dispatches with no `cron_telemetry` field at all.

**Each template below has been updated to call this contract** at its Step 1 (fire entry) and at each exit path. The instrumentation is mechanical — no logic change in any cron's existing decision tree.

### Cron Dispatch-Mode Conventions (v7.0.1)

Every cron template below reads `worker_dispatch_mode` from the dispatch file at fire-time and branches on it. The two paths have fundamentally different interaction contracts. Each template's emission step and manual-ack guidance are mode-conditional per the rules below; the rules are written here once to avoid duplication across 5 templates.

**`--bg` path** (worker is a Claude Code background agent, v7.0.0+ default on Claude Code ≥ 2.1.139):

- **Cron→worker interaction is FILE WRITES ONLY.** The dispatch file is the sole state-change interface. Write `intent_acknowledged_utc`, append to `amendments[]`, etc. Worker picks up via auto-ack-resume guard or self-poll on next active turn.
- **DO NOT invoke `claude --resume <worker-session>` against a running --bg agent.** Claude Code refuses with `Error: Session <uuid> is currently running as a background agent (bg). Use claude agents to find and attach to it, or add --fork-session to branch off a copy.` The cron output becomes noisy stderr; the worker doesn't get the nudge. Per upstream agent-view doc, there is NO scriptable peer-to-peer message-injection primitive for running `--bg` sessions.
- **DO NOT invoke `claude --fork-session`** even though the error message above suggests it. Forking creates a DUPLICATE session — original `--bg` worker AND a forked copy could both write to the dispatch file, double-claim file scope, double-commit. This violates falcon's single-worker-per-dispatch invariant. The error message's suggestion is wrong for falcon's use case.
- **Emission shape** (when state changes): emit a single inline `STATE:` line, NOT a labeled-copy fence:
  ```
  STATE: <event> dispatch=<id> <key>=<value>,<key>=<value>,...
  ```
  Rationale: `--bg` operators monitor the steering session's chat for cron output. No paste-into-worker-tab step is needed (worker reads the file directly). A 20-30 line fence is vestigial overhead; a one-line state notification preserves the operator's signal density.
- **Manual nudge mechanism** (when operator wants to wake an idle/stopped `--bg` worker): operator opens `claude agents`, presses `Space` on the worker's row to peek, and types either `proceed <dispatch-id>` (to relay the ack manually) or `falcon poll` (per the wake-phrase convention — worker re-reads dispatch file + emits STATE:). The cron MUST NOT attempt this from its own context.

**`--via-paste` path** (worker is an operator-attached Claude Code tab; pre-v7.0.0 default):

- **Cron→worker interaction is FILE WRITES + LABELED-COPY FENCE.** The dispatch file is still authoritative for state, AND the cron emits a fence the operator pastes into the worker tab. Workers in `--via-paste` mode do NOT have an auto-ack-resume guard; they rely on the operator's paste action to receive cron output.
- **DO NOT invoke `claude --resume`** here either. Even in `--via-paste`, the path is paste-driven, not `--resume`-driven. The worker tab is interactively attached.
- **Emission shape**: full labeled-copy fence as documented in the per-template emission sections below.
- **Manual ack/nudge**: operator pastes the fence contents into the worker tab; the worker reads as a regular user message.

**`--paste` path** (cross-machine fallback): behaves like `--via-paste` for cron emission purposes. The cross-machine aspect is handled by the dispatch-file-on-shared-filesystem assumption being relaxed; the cron emission shape itself is the same as `--via-paste`.

**Mode detection inside each cron template**: read `worker_dispatch_mode` from the dispatch file at Step 1 alongside the other state fields. Branch on it in the emission step (Step 3 or 4 depending on template) and the manual-ack/nudge guidance.

### Wake-opportunism convention (v7.7.0)

**Rule:** on ANY steering-session wake — cron fire, operator message, monitor event — after executing the triggering role's template, probe ALL active dispatches for pending actionable state (unacked intent, completed-but-unvalidated results, terminal states needing release, purposeless crons needing retirement) and process each finding under the appropriate role's rules. Scheduled crons are the AFK latency FLOOR, not a ceiling when steering is awake: cron cadence exists so unattended dispatches make progress, never to delay work a wake has already surfaced.

**Provenance (live incident, dispatch b92a16, 2026-06-13):** the `--auto-amend` cron's probe observed a pending unacked intent, but role separation gave it no mandate to act — steering deferred to the `--auto-ack` cron's next fire, discarding ~4 minutes of free latency. After operator correction, the convention was validated in production the same session: the b92a16 completion was detected and fully closed out (validate → audit → release) from an auto-amend cron wake, and the now-purposeless auto-ack cron was opportunistically retired from a different role's wake.

**Resolved design decisions (DAR, settled with user 2026-06-13 — recommendations accepted; do not relitigate):**

1. **Cross-dispatch scope: YES** — a wake triggered by dispatch A's cron also processes dispatch B's pending state; each dispatch is processed under its own gates/rules file, so contexts don't conflate.
2. **Telemetry attribution: executing role's slug** gets the fires/useful increment, plus a `source=` label naming the actual trigger (e.g. `source=opportunistic-via-amend-cron`, `source=steering-manual-review`). Precedent recorded on dispatch b92a16's telemetry. Mechanics in `### Cron Telemetry Instrumentation (v7.1.0, fdev-lbq.30)` above — the `fires == silent + useful` invariant is unchanged.

**Per-template exit step:** each steering cron template below (`--watch`, `--auto-ack`, `--auto-amend`, `--release-on-merge`) carries a one-line pointer at its exit step — before exiting, apply the wake-opportunism check. Opportunistic processing runs under each dispatch's own autopilot gates; the gates themselves are unchanged by this convention. (`--worker-cron` is worker-side and out of scope — opportunism is a STEERING-wake convention.)

**Relation to event-driven monitoring:** file monitoring as a cron alternative (README backlog) is the event-driven endgame — instant reaction to dispatch-file state changes. This convention is the cheap interim: it recovers most of the wasted latency at zero added infrastructure by spending wakes that already happened.

### `--watch` cron prompt template (v6.8.0)

Fired by the cron armed at Step 2 of the dispatch protocol when `--watch` is set. Report-only — never writes to the dispatch file, never auto-acks, never auto-amends. The cron self-cancels on terminal `session_status: complete`.

CronCreate call shape (steering side, at Step 2):

```
CronCreate(
  cron: "{{ schedule_expression }}",            # v7.1.0 (fdev-lbq.28): N computed from bead Effort Forecast bucket at Step 2 (watch slot of compute_initial_cadence tuple); default = MEDIUM bucket value (11). Override via --cron-cadence Nm forces N regardless of bucket. Offset-staggered per fdev-lbq.5.
  prompt: <the template below, with literals substituted>,
  durable: false,                              # session-bound; not persisted across restarts
  recurring: true,
)
```

The returned ID is written to `watch_cron_id` in the dispatch file.

Template (literal `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}` are substituted at CronCreate time; everything else is literal text the cron interprets at fire time):

```
You are a falcon --watch cron firing against dispatch {{ dispatch_id }}.

Mode: REPORT-ONLY. Do NOT write to the dispatch file. Do NOT acknowledge intent.
Do NOT issue amendments. Do NOT release the lock. Do NOT modify any bd state.
This cron's only job is to detect state transitions on the dispatch and emit a
status block when one is observed.

## Step 1 — Read current state

Read the dispatch file: {{ dispatch_file_path }}

Capture the following fields from the dispatch:
- session_status              (active | amendments_pending | complete)
- implementation_intent       (null | non-null string)
- implementation_results_hash (null | non-null sha256 string)
- amendments[]                (count + per-entry status)
- intent_acknowledged_utc     (null | ISO8601 — Phase 2 will populate; Phase 1 reads as status)
- watch_cron_id               (this cron's own ID; sanity check)
- auto_amendments_issued      (Phase 3 will populate; Phase 1 reads as status, does not act)
- amendment_budget            (Phase 3 will populate; Phase 1 reads as status, does not act)
- worker_dispatch_mode        ("bg" | "via-paste" | "paste" — drives Step 3 emission shape per "Cron Dispatch-Mode Conventions (v7.0.1)" above)

For each bead in bead_ids[]:
- Run `bd show --json <bead-id>` and capture status.

Compute commit attribution (v7.0.1 — per-dispatch, not branch-wide):

```
# 1. Branch-wide count since dispatch open (raw, unfiltered)
git fetch origin
branch_total=$(git log origin/<branch> --oneline --since="<dispatch created_utc>" | wc -l)

# 2. Per-dispatch attributed count via `Closes: <bead-id>` commit trailer
#    (one expression per bead in bead_ids[]; sum the counts)
dispatch_attributed=0
for bead_id in <bead_ids[]>:
  count=$(git log origin/<branch> --oneline --grep="Closes: <bead_id>" --since="<dispatch created_utc>" | wc -l)
  dispatch_attributed=$((dispatch_attributed + count))

# 3. Unattributed = anything on branch that we couldn't attribute to a known dispatch.
#    This includes amend/rebase commits that dropped the trailer, legacy commits
#    from before the convention was enforced, OR commits from OTHER dispatches
#    running on the same branch in parallel (which is exactly the noise this
#    metric is designed to suppress — they're attributed to a DIFFERENT dispatch).
unattributed=$((branch_total - dispatch_attributed))
# (Note: unattributed > 0 is NOT necessarily a problem in parallel-dispatch mode
# — it means another dispatch on the same branch authored those commits.
# Step 3 emits the degraded "unattributed commit detected" notification only
# when unattributed_grew_since_prior_fire is true; not on every fire.)
```

**Rationale (v7.0.1, fdev-lbq.4):** before this change, watch cron used `branch_total` directly as the "commits on branch since open" metric. When N parallel dispatches shared a branch, dispatch A's commit caused N spurious STATUS UPDATEs (one per watching cron, each reporting the same commit as if it were attributable to that dispatch). The fix is per-dispatch attribution via the `Closes: <bead-id>` commit trailer (a convention that workers are already required to follow per PROTOCOL.md Worker Lifecycle Step 8). Watch cron now reports `dispatch_attributed_commits` (its own) and `unattributed_branch_commits` (everyone else's) separately. The dispatch-attributed count drives the STATE: emission; the unattributed count drives a degraded "unattributed commit detected" notification only when it changes (catches amend/rebase that dropped the trailer; ignores routine parallel-dispatch noise).

## Step 2 — Read prior snapshot

Read {{ snapshot_file_path }} if it exists. If absent, treat as first fire and set
prior_state = null.

The snapshot is a JSON object with the same fields captured in Step 1.

## Step 3 — Compare and emit on change

If prior_state is null (first fire): emit a status block describing the current
state. Then write the current state to the snapshot file and exit.

If prior_state matches current state on every captured field: exit silently
(no emission, no snapshot write).

If any field changed: emit a formatted notification per `worker_dispatch_mode`:

- **If `worker_dispatch_mode == "bg"`**: emit a single inline `STATE:` line
  (no fence), per "Cron Dispatch-Mode Conventions (v7.0.1)" above. Format:

      STATE: WATCH-STATUS-UPDATE dispatch={{ dispatch_id }} session_status=<value> intent_acknowledged_utc=<value> implementation_results_hash=<presence> amendments=<count> beads=<dot-separated id:status> commits_attributed=<count> commits_unattributed=<count>

  If `commits_unattributed` GREW since the prior fire (was N, now > N), append
  one extra STATE: line flagging the degraded condition (catches amend/rebase
  that dropped the `Closes:` trailer; ignores routine parallel-dispatch noise
  where unattributed stays steady):

      STATE: WATCH-UNATTRIBUTED-COMMIT-DETECTED dispatch={{ dispatch_id }} branch={{ branch_name }} unattributed_delta=<N>

  If the high-stakes DAR headline applies (see v6.12.2 paragraph below), prepend
  it as a separate line above the STATE: line(s) — keep all inline, no fences.

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit a formatted
  labeled-copy block using the v6.5.3 convention with label `STATUS UPDATE`
  (full fence template below).

**v6.12.2 — high-stakes DAR headline:** before emitting the block,
inspect `implementation_results.falcon_report.decisions_for_human[]` (if
implementation_results is non-null). Filter to entries where
`stakes: "high"` AND `action_taken: "stopped pending arbitration"` AND no
recorded resolution in either the dispatch file or the branch-keyed stash
file at `.claude/tmp/falcon-reports-<sanitized-branch>.yaml`. If the count
is > 0, prepend a one-line headline INSIDE the fence, ABOVE the existing
state-change body:

    ⚠️ HIGH-STAKES DAR PENDING (<count> entries): arbitrate via /falcon release <id> after manual investigation, OR see /falcon list-pending for full pending-human surface.

This makes the DAR call out from a long inline history of routine STATUS
UPDATE blocks. If no high-stakes DARs are pending, skip the headline; emit
the body as before.

(The labeled-copy block below applies ONLY to `--via-paste` / `--paste`
modes; in `--bg` mode the cron emits the inline `STATE:` line shown above
instead.)

    ## STATUS UPDATE — dispatch {{ dispatch_id }} at <UTC ISO8601 at fire time>

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    ⚠️ HIGH-STAKES DAR PENDING (1 entries): arbitrate via /falcon release {{ dispatch_id }} after manual investigation, OR see /falcon list-pending for full pending-human surface.

    Dispatch {{ dispatch_id }} state changed since last fire:

    session_status:                <prior> → <current>
    implementation_intent:         <prior presence> → <current presence>
    implementation_results_hash:   <prior presence> → <current presence>
    intent_acknowledged_utc:       <prior> → <current>
    amendments (count by status):  <prior breakdown> → <current breakdown>
    auto_amendments_issued:        <prior> → <current> (budget: <amendment_budget>)
    beads:
      - <bead-id>: <prior bd status> → <current bd status>
    commits attributed to dispatch: <prior count> → <current count>   (via `Closes: <bead-id>` trailer)
    commits unattributed on branch: <prior count> → <current count>   (other dispatches OR amend/rebase dropped trailer)

    Dispatch file: {{ dispatch_file_path }}
    Snapshot:      {{ snapshot_file_path }}
    Cron cadence:  every <N> min (cron id: falcon-watch-{{ dispatch_id }})

    REPORT-ONLY. No autopilot action taken.
    ~~~
    ═══ END COPY ═══

Then write the current state to the snapshot file (overwriting prior).

## Step 4 — Self-cancel on terminal state

If current session_status == "complete":
1. CronDelete this cron (look up by slug: `falcon-watch-{{ dispatch_id }}`)
2. Remove the snapshot file at {{ snapshot_file_path }}
3. Emit a final status block with label `WATCH CRON RELEASED` confirming the cron
   cancelled itself and the dispatch reached terminal state.

Before exiting — on EVERY fire, terminal or not — apply the wake-opportunism
check per `### Wake-opportunism convention (v7.7.0)` above: probe all active
dispatches for pending actionable state; process each under its own role's rules.

## Phase 2-5 note (forward compatibility)

This template is the foundation for the wider autopilot rollout. Phase 2
(`--auto-ack`) will land a sibling cron template that READS the same dispatch
fields but ALSO writes `intent_acknowledged_utc` when the `SAFE_TO_ACK_INTENT`
predicate in `.claude/rules/falcon-autopilot.md` passes. Phase 3 (`--auto-amend`)
adds an amendment-issuing cron. Phase 4 (`--worker-cron`) adds a worker-side
amendment-pickup cron. Phase 5 (`--advisor`, `--release-on-merge`) extends both
sides. Every future cron template lives in this file section and follows
the same `falcon-<role>-<dispatch-id>` slug + sidecar-snapshot-file convention.
```

#### Condensed CronCreate prompt (v7.1.2)

The literal text steering passes to `CronCreate(prompt=...)` for the `--watch` cron — a thin pointer that Reads the canonical Step 1-4 spec above at fire time. ~250 tokens vs. ~3000 for the full template body. Substituted literals at CronCreate time: `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ branch_name }}`. `--watch` has no Step 0 adaptive guard (it's report-only; no quiescent silence-pattern), so the entire execution path is pointer-style.

```
You are a falcon --watch cron firing against dispatch {{ dispatch_id }}.

Mode: REPORT-ONLY. Self-cancel slug: falcon-watch-{{ dispatch_id }}.
Dispatch file: {{ dispatch_file_path }}
Snapshot file: {{ snapshot_file_path }}
Branch: {{ branch_name }}

Read CRONS.md `## Autopilot Cron Prompt Templates` → `### --watch cron
prompt template (v6.8.0)` and follow Steps 1-4 verbatim against the
captured dispatch state. Mode-conditional emission per `### Cron
Dispatch-Mode Conventions (v7.0.1)` — the worker_dispatch_mode field on
the dispatch file drives whether to emit STATE: line (--bg) or
labeled-copy fence (--via-paste / --paste). Per-dispatch commit
attribution (`Closes: <bead-id>` trailer) per the same section's
v7.0.1 fdev-lbq.4 rationale. Telemetry-counter contract per
`### Cron Telemetry Instrumentation (v7.1.0, fdev-lbq.30)` applies on
every fire.
```

(End of `--watch` cron prompt template.)

### `--auto-ack` cron prompt template (v6.9.0)

Fired by the cron armed at Step 2 of the dispatch protocol when `--auto-ack` is set. Evaluates the `SAFE_TO_ACK_INTENT` 4-gate predicate against the worker's latest intent paragraph; on all-pass, writes `intent_acknowledged_utc` to the dispatch file and emits the `proceed <dispatch-id>` block inline for the user to relay. On any-fail, defers silently (one inline note per fire that gates failed and why, so the user knows manual ack is needed).

CronCreate call shape (steering side, at Step 2):

```
CronCreate(
  cron: "{{ schedule_expression }}",            # v7.1.0 (fdev-lbq.28): N computed from bead Effort Forecast bucket at Step 2 (auto-ack slot of compute_initial_cadence tuple); default = MEDIUM bucket value (4). Override via --cron-cadence Nm forces N regardless of bucket. Offset-staggered per fdev-lbq.5.
  prompt: <the template below, with literals substituted>,
  durable: false,
  recurring: true,
)
```

The returned ID is written to `autoack_cron_id` in the dispatch file.

Template (literal `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}` are substituted at CronCreate time):

```
You are a falcon --auto-ack cron firing against dispatch {{ dispatch_id }}.

Mode: AUTONOMOUS INTENT ACKNOWLEDGEMENT. This cron may write
`intent_acknowledged_utc` to the dispatch file when all gates pass. It does
NOT issue amendments, does NOT release the lock, does NOT modify any bd state,
and does NOT touch any file other than the dispatch file + this cron's sidecar
snapshot.

## Step 0 — Adaptive cadence early-exit guard (v7.0.1, fdev-lbq.2)

Before reading full dispatch state in Step 1, run a MINIMAL state probe to
detect whether this cron has anything to do this fire. The `--auto-ack` cron
is relevant ONLY in the narrow intent-emission-to-ack window; outside that
window (pre-intent or post-ack), every fire is silent overhead. This guard
reduces per-fire token cost to a single yq query when there's nothing to do.

Read ONLY the following fields from the dispatch file via a focused yq query
(avoid the full Step 1 capture):

```
session_status=$(yq '.session_status' {{ dispatch_file_path }})
intent_acked=$(yq '.intent_acknowledged_utc' {{ dispatch_file_path }})
```

Decision tree:

1. **Terminal-state exit**: if `session_status == "complete"`, proceed to Step 6
   (self-cancel + exit). Skip Step 1; the cron is on its way out.
2. **Post-ack quiescence**: if `intent_acked` is non-null AND `session_status
   != "complete"`, the ack already landed (by prior fire or by user); this
   cron has nothing to do. Exit silently — do NOT write to snapshot; do NOT
   execute Step 1.
3. **Active window**: if `intent_acked` is null AND `session_status !=
   "complete"`, there may be work to do this fire. Proceed to Step 1 for
   full state read + gate evaluation.

Per-dispatch behavioral envelope:

- **Pre-intent** (worker hasn't emitted yet): every fire exits at Step 0
  case 3-but-then-pre-intent-check-in-Step-1 — low cost (just file reads,
  no gate eval).
- **Intent-emission-to-ack window** (typically 5-20 min): fires execute
  Step 1+ and evaluate gates; at most one fire writes
  `intent_acknowledged_utc`.
- **Post-ack** (until terminal): every fire exits at Step 0 case 2 (single
  yq query, minimum cost).
- **Terminal**: Step 0 case 1 self-cancels.

The cadence itself stays at default 5m; this guard makes per-fire cost
adaptive to dispatch phase. CronCreate-driven cadence-change is a possible
v7.1 enhancement (re-arm at slower cadence post-ack); v7.0.1 ships the
in-prompt guard because it's the minimum-risk change.

## Step 1 — Read current state

Read the dispatch file: {{ dispatch_file_path }}

Capture:
- session_status              (active | amendments_pending | complete)
- implementation_intent       (null | non-null string)
- intent_acknowledged_utc     (null | ISO8601)
- file_scope                  (directories[] + files[])
- bead_ids[]                  (for cross-checking the intent's Changes Needed reference)
- amendments[]                (count — for cross-dispatch-conditional check)
- worker_dispatch_mode        ("bg" | "via-paste" | "paste" — drives all emission shapes below per "Cron Dispatch-Mode Conventions (v7.0.1)")

If session_status == "complete": self-cancel (Step 5 below) and exit.
If implementation_intent is null: nothing to ack; exit silently.
If intent_acknowledged_utc is already non-null: already acked (by prior fire or by user); exit silently.

## Step 2 — Read prior snapshot

Read {{ snapshot_file_path }} if it exists. If absent, set prior_intent_hash = null.

Compute current intent hash: `sha256(implementation_intent.encode('utf-8')).hexdigest()`.

If current intent hash == prior intent hash: this intent was already evaluated on a
prior fire; exit silently (avoid re-emitting the same defer-note on every fire).

## Step 3 — Read the autopilot gate file

Read `{{ repo_path }}/.claude/rules/falcon-autopilot.md`.

REFUSE (do NOT auto-ack, do NOT write anything) if any of the following hold:
- File does not exist → emit refuse-block citing "falcon-autopilot.md not committed; run /falcon create-rules and uncomment gate sections, OR ack intent manually."
- File exists but every `# PROJECT —` section under `## 1. SAFE_TO_ACK_INTENT predicate` is commented (minimum-viable mode) → emit refuse-block naming the specific gate the user should uncomment. Universal gates alone are NOT sufficient for --auto-ack writes; the project must opt in.

Refuse-block emission is mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":

- **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line:

      STATE: AUTO-ACK-REFUSED dispatch={{ dispatch_id }} reason=<short-code> action=<short-code> manual_ack=peek-and-reply-`proceed {{ dispatch_id }}`-OR-`falcon poll`

  No fence. Operator nudges via `claude agents` peek-and-reply if they want to relay the ack manually (per Cron Dispatch-Mode Conventions §`--bg` path).

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block with label `AUTO-ACK REFUSED`:

      ## AUTO-ACK REFUSED — dispatch {{ dispatch_id }} at <UTC ISO8601 at fire time>

      ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
      ~~~
      Dispatch {{ dispatch_id }} intent acknowledgement refused.

      Reason: <one-line — missing file / all PROJECT gates commented>
      Action: <specific instruction — run /falcon create-rules / uncomment
               `safe_to_ack_intent.project_gates.<gate-name>` in
               .claude/rules/falcon-autopilot.md>

      Manual ack alternative: paste `proceed {{ dispatch_id }}` to the worker tab.
      ~~~
      ═══ END COPY ═══

Write the current intent hash to the snapshot file (so the same refuse doesn't fire again next cron tick), then exit.

## Step 4 — Evaluate the 4-gate predicate

For each gate under `safe_to_ack_intent.gates` (universal) + each uncommented gate under `safe_to_ack_intent.project_gates` in the gate file, evaluate the `check:` description against the captured state. The 4 universal gates are:

1. `no_new_file_scope` — regex-extract paths from implementation_intent; cross-check against dispatch.file_scope.directories + .files. Any match outside scope fails this gate.
2. `no_cross_dispatch_conditional` — search implementation_intent for phrases like "after X bead closes", "depending on", "if X succeeds", "waiting on", "blocked-by" + bead IDs. Any match fails this gate.
3. `intent_matches_changes_needed` — for each bead in bead_ids[], `bd show --json <id>` to load the Changes Needed file list. Extract file paths + key nouns from intent; overlap must be ≥ 50% of Changes Needed items by token count.
4. `no_open_dar_arbitration` — read `.claude/tmp/falcon-reports-<sanitized-branch>.yaml` (derive sanitized branch via `git rev-parse --abbrev-ref HEAD | tr '/' '-'`). Any decisions_for_human[] entry with stakes: high and unrecorded resolution fails this gate.

If ANY gate fails: emit a defer notification citing which gate failed + why + the manual-ack alternative. Write current intent hash to snapshot. Exit.

Defer emission is mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":

- **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line:

      STATE: AUTO-ACK-DEFERRED dispatch={{ dispatch_id }} failed_gate=<gate-name> reason=<short-code> manual_ack=peek-and-reply-`proceed {{ dispatch_id }}`

  No fence. Operator reviews the intent (via peek), arbitrates, and relays `proceed {{ dispatch_id }}` manually via peek-and-reply if appropriate.

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block with label `AUTO-ACK DEFERRED`:

      ## AUTO-ACK DEFERRED — dispatch {{ dispatch_id }} at <UTC ISO8601 at fire time>

      ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
      ~~~
      Dispatch {{ dispatch_id }} intent NOT auto-acked.

      Failed gate: <gate name>
      Reason: <one-line — what the intent said that triggered the fail>

      Manual ack: paste `proceed {{ dispatch_id }}` to the worker tab after
      confirming the intent is acceptable.
      ~~~
      ═══ END COPY ═══

## Step 5 — All gates passed → auto-ack

Write `intent_acknowledged_utc: <UTC ISO8601 at fire time>` to the dispatch file (atomic write; preserve all other fields). **This file write IS the ack contract** — in `--bg` mode the worker reads `intent_acknowledged_utc` from the dispatch file on its next active turn via the auto-ack-resume guard; no `proceed {{ dispatch_id }}` paste-block is required.

Ack notification emission is mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":

- **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line confirming the file write:

      STATE: INTENT-AUTO-ACK dispatch={{ dispatch_id }} intent_acknowledged_utc=<UTC ISO8601 at fire time> gates=all-passed

  **DO NOT invoke `claude --resume <worker-session> --print "proceed {{ dispatch_id }}"`** — Claude Code refuses `--resume` on running background agents (per Cron Dispatch-Mode Conventions §`--bg` path). The file write is sufficient. If the worker is idle/supervisor-stopped, operator types `falcon poll` on attach to nudge dispatch-file re-read (per the wake-phrase convention).

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block with label `INTENT AUTO-ACK` (operator pastes the `proceed` line into the worker tab):

      ## INTENT AUTO-ACK — dispatch {{ dispatch_id }} at <UTC ISO8601 at fire time>

      ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
      ~~~
      proceed {{ dispatch_id }}

      Intent for dispatch {{ dispatch_id }} auto-acknowledged after all 4 SAFE_TO_ACK_INTENT
      gates passed. Worker may resume claim/implement.

      Acknowledged by: --auto-ack cron at <UTC ISO8601>
      Dispatch file: {{ dispatch_file_path }}
      ~~~
      ═══ END COPY ═══

Write current intent hash to the snapshot file (so next fire doesn't re-ack the same intent).

## Step 6 — Self-cancel on terminal state

If current session_status == "complete":
1. CronDelete this cron (lookup by slug: `falcon-autoack-{{ dispatch_id }}`)
2. Remove the snapshot file at {{ snapshot_file_path }}
3. Emit a final block with label `AUTO-ACK CRON RELEASED` confirming cancellation.

Before exiting — on EVERY fire, terminal or not — apply the wake-opportunism
check per `### Wake-opportunism convention (v7.7.0)` above: probe all active
dispatches for pending actionable state; process each under its own role's rules.

## Cross-cron coordination note

When BOTH `--watch` and `--auto-ack` are armed for the same dispatch, two separate
crons run: `falcon-watch-<dispatch-id>` (10m cadence, report-only) and
`falcon-autoack-<dispatch-id>` (5m cadence, write-bearing). They use independent
sidecar snapshots. /falcon release-cron tears down both via the
`falcon-(watch|autoack)-<dispatch-id>` prefix-match.
```

#### Condensed CronCreate prompt (v7.1.2)

The literal text steering passes to `CronCreate(prompt=...)` for the `--auto-ack` cron — Step 0's adaptive-cadence early-exit guard is kept INLINE (~60-70% of fires short-circuit there per v7.0.1 fdev-lbq.2; pointer-style Step 0 would defeat the per-fire amortized win by replacing a system-prompt-cached predicate with a tool-result-loaded one). Steps 1-6 (and the advisor-extension below if `advisor` field is non-null) are pointer-style: the cron Reads this file at fire time. ~400 tokens vs. ~3500 for the full template body + extension. Substituted literals at CronCreate time: `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}`, `{{ branch_name }}`.

```
You are a falcon --auto-ack cron firing against dispatch {{ dispatch_id }}.

Mode: AUTONOMOUS INTENT ACKNOWLEDGEMENT. May write intent_acknowledged_utc
to the dispatch file when all gates pass. Self-cancel slug:
falcon-autoack-{{ dispatch_id }}.
Dispatch file: {{ dispatch_file_path }}
Snapshot file: {{ snapshot_file_path }}
Repo path: {{ repo_path }}
Branch: {{ branch_name }}

## Step 0 — Adaptive cadence early-exit guard (INLINE, v7.0.1 fdev-lbq.2)

Run a minimal state probe via focused yq queries before full Step 1 capture:

    session_status=$(yq '.session_status' {{ dispatch_file_path }})
    intent_acked=$(yq '.intent_acknowledged_utc' {{ dispatch_file_path }})

Decision tree:

1. If `session_status == "complete"`: proceed to Step 6 self-cancel (no
   Step 1 capture, no gate eval).
2. If `intent_acked` is non-null AND `session_status != "complete"`: ack
   already landed (by prior fire or by user); exit silently. Do NOT
   write snapshot. Do NOT execute Step 1.
3. If `intent_acked` is null AND `session_status != "complete"`: active
   window. Proceed to Step 1 below.

Telemetry: increment `cron_telemetry.autoack.fires` on entry; on
Step 0 case 2 silent-exit, increment `cron_telemetry.autoack.silent`
and exit. (Case 1 + case 3 paths increment `useful` at the action
boundary downstream.)

## Steps 1-6 — execute per canonical spec

Read CRONS.md `## Autopilot Cron Prompt Templates` → `### --auto-ack
cron prompt template (v6.9.0)` and follow Steps 1 through 6 verbatim.
If the dispatch's `advisor` field is non-null, ALSO read `#### --auto-ack
advisor-extension (v6.12.0)` for the Step 4b advisor-fork extension to
the gate evaluation. Mode-conditional emission per `### Cron Dispatch-Mode
Conventions (v7.0.1)`. Telemetry-counter contract per `### Cron Telemetry
Instrumentation (v7.1.0, fdev-lbq.30)` applies on every fire.
```

(End of `--auto-ack` cron prompt template.)

#### `--auto-ack` advisor-extension (v6.12.0)

When `--advisor=<agent>` is set on the dispatch (`advisor: "<agent>"` field non-null), the `--auto-ack` cron's Step 4 (gate evaluation) gains a fork-on-ambiguous-decision step. Append to the existing Step 4 logic:

```
## Step 4b — Advisor fork (v6.12.0; only when advisor field is non-null)

After evaluating the 4 universal gates + project gates in Step 4:

If ALL gates clearly passed → proceed to Step 5 (write intent_acknowledged_utc).
If ALL gates clearly failed → defer per Step 4 defer-block.

If the evaluation is AMBIGUOUS — exactly one gate failed but it's a project gate
matching the advisor_delegation policy in .claude/rules/falcon-autopilot.md § 5
(e.g., dar_in_scope_question for quartermaster) — fork to the named advisor:

1. Read .claude/rules/falcon-autopilot.md § 5 advisor_delegation entries.
2. Find the entry matching `advisor: "<agent>"` from the dispatch file.
3. Check the entry's `delegates` list for a matching decision pattern.
4. If match found AND not in `refuses` list: invoke the advisor agent (using
   the Skill tool with the named skill), passing:
   - the intent paragraph
   - the gate that failed
   - the dispatch context (file_scope, bead IDs)
   The advisor returns a recommendation.
5. Capture the advisor's recommendation as response_source: /<agent>.
6. If the recommendation is "ack" → proceed to Step 5 with response_source:
   /<agent> annotation.
7. If the recommendation is "defer" → emit defer-block citing the advisor's
   reasoning + manual-ack alternative.
8. Emit an ADVISOR FORK block for audit trail before either path:

    ## ADVISOR FORK — dispatch {{ dispatch_id }} at <UTC ISO8601>

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    Ambiguous gate decision forked to advisor.

    Advisor:        /<agent>
    Failed gate:    <gate name>
    Recommendation: <ack | defer>
    Rationale:      <one-line from advisor>
    ~~~
    ═══ END COPY ═══

If the advisor refuses the question (per the `refuses` list in falcon-autopilot.md
§ 5) → defer to user per the normal defer-block path; do NOT fork.
```

(End of `--auto-ack` advisor-extension.)

### `--auto-amend` cron prompt template (v6.10.0)

Fired by the cron armed at Step 2 of the dispatch protocol when `--auto-amend` is set. Evaluates the `SAFE_TO_AMEND` whitelist (`.claude/rules/falcon-autopilot.md § 2`) against gaps surfaced from the dispatch's Step 3 mechanical validation + Step 3b cognitive audit; on whitelist match, auto-issues an amendment to the dispatch file's `amendments[]` array (`issued_by: steering-cron`, `label: auto-issued:cron`). On budget exhaustion (`auto_amendment_count >= amendment_budget`), HALTs issuance and emits one `AMENDMENT BUDGET EXHAUSTED` block.

CronCreate call shape (steering side, at Step 2):

```
CronCreate(
  cron: "{{ schedule_expression }}",            # v7.1.0 (fdev-lbq.28): N computed from bead Effort Forecast bucket at Step 2 (auto-amend slot of compute_initial_cadence tuple); default = MEDIUM bucket value (7). Override via --cron-cadence Nm forces N regardless of bucket. Offset-staggered per fdev-lbq.5.
  prompt: <the template below, with literals substituted>,
  durable: false,
  recurring: true,
)
```

The returned ID is written to `amend_cron_id` in the dispatch file.

Template (literal `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}` substituted at CronCreate time):

```
You are a falcon --auto-amend cron firing against dispatch {{ dispatch_id }}.

Mode: AUTONOMOUS AMENDMENT ISSUANCE. This cron may write entries to
`amendments[]` on the dispatch file when SAFE_TO_AMEND whitelist matches AND
the budget has not been exhausted. It does NOT acknowledge intent, does NOT
release the lock, does NOT modify any bd state, and does NOT touch any file
other than the dispatch file + this cron's sidecar snapshot.

## Step 0 — Adaptive cadence early-exit guard (v7.0.1, fdev-lbq.3)

Before reading full dispatch state in Step 1, run a MINIMAL state probe to
detect whether this cron has anything to do this fire. The `--auto-amend`
cron is relevant ONLY in the completion-to-validated window; outside that
window (pre-completion, budget-exhausted, or terminal), every fire is silent
overhead. This guard reduces per-fire token cost to a single yq query when
there's nothing to do.

Read ONLY the following fields from the dispatch file via a focused yq query
(avoid the full Step 1 capture):

```
session_status=$(yq '.session_status' {{ dispatch_file_path }})
impl_results_hash=$(yq '.implementation_results_hash' {{ dispatch_file_path }})
amend_budget=$(yq '.amendment_budget' {{ dispatch_file_path }})
auto_amend_count=$(yq '.auto_amendments_issued // 0' {{ dispatch_file_path }})
```

Decision tree (three quiescent windows):

1. **Terminal-state exit**: if `session_status == "complete"`, proceed to
   Step 7 (self-cancel + exit). Skip Step 1.
2. **Pre-completion quiescence**: if `impl_results_hash` is null AND
   `session_status != "complete"`, worker hasn't emitted COMPLETION yet;
   no validation gaps to find. Exit silently. Skip Step 1.
3. **Budget-exhausted quiescence**: if `amend_budget` is non-null AND
   `auto_amend_count >= amend_budget`, the HALT was already detected and
   emitted on a prior fire (Step 4). This cron has no further amendments
   to issue for this dispatch. Exit silently. Skip Step 1. (The FIRST
   detection of HALT — when `auto_amend_count` first reaches the budget —
   still flows through Step 4 to emit the AMENDMENT BUDGET EXHAUSTED
   notification; subsequent fires hit this Step 0 guard and stay silent.)
4. **Active window**: if `impl_results_hash` is non-null AND
   `session_status != "complete"` AND budget is not exhausted, there may
   be gaps to evaluate. Proceed to Step 1 for the full state read.

Per-dispatch behavioral envelope:

- **Pre-completion** (worker hasn't emitted COMPLETION yet): every fire
  exits at Step 0 case 2 (minimum cost).
- **Active window** (completion → validated/released, typically 1-3 fires):
  fires execute Step 1+ and evaluate gaps against the SAFE_TO_AMEND
  whitelist.
- **Budget-exhausted** (after HALT fires once at Step 4): every subsequent
  fire exits at Step 0 case 3 (minimum cost) until terminal.
- **Post-validated, no-gaps** (gap_set has been empty for multiple fires):
  Step 1's existing "gap_set is empty" early-exit in Step 5 still applies.
  Step 0 doesn't catch this case (would require reading gap state, which
  is the expensive part of Step 1). Acceptable — the post-validated cost-
  per-fire is already low after Step 5's `current_gap_hash == prior_gap_hash`
  silent-exit check.
- **Terminal**: Step 0 case 1 self-cancels.

The cadence itself stays at default 5m; this guard makes per-fire cost
adaptive to dispatch phase. CronCreate-driven cadence-change is a possible
v7.1 enhancement; v7.0.1 ships the in-prompt guard because it's the
minimum-risk change.

## Step 1 — Read current state

Read the dispatch file: {{ dispatch_file_path }}

Capture:
- session_status                  (active | amendments_pending | complete)
- implementation_results_hash     (null | non-null — completion signal)
- amendments[]                    (full list — to compute auto_amendment_count by label)
- amendment_budget                (null | int — cap from --amendment-budget N)
- auto_amendment_count            (running counter; recompute from amendments[] for safety:
                                   count entries where label == "auto-issued:cron")
- bead_ids[]                      (for cross-checking gap fingerprints)
- file_scope                      (for the in-scope check on candidate amendments)
- worker_dispatch_mode            ("bg" | "via-paste" | "paste" — drives all emission shapes below per "Cron Dispatch-Mode Conventions (v7.0.1)")

If session_status == "complete": self-cancel (Step 6) and exit.
If implementation_results_hash is null: worker hasn't completed yet; nothing to validate; exit silently.

## Step 2 — Read prior snapshot

Read {{ snapshot_file_path }} if it exists. If absent, set prior_gap_hash = null and prior_outcome = null.

The snapshot stores: { gap_set_hash, last_outcome } from the previous fire.

## Step 3 — Read the autopilot gate file

Read `{{ repo_path }}/.claude/rules/falcon-autopilot.md`.

REFUSE (do NOT auto-issue, do NOT write anything) if any of the following hold:
- File does not exist → emit refuse-block citing "falcon-autopilot.md not committed; run /falcon create-rules and uncomment safe_to_amend_whitelist items, OR issue amendments manually."
- File exists but every `# PROJECT —` item under `## 2. SAFE_TO_AMEND whitelist` is commented (minimum-viable mode) → emit refuse-block naming a specific whitelist item the user should uncomment (the most-likely-relevant one based on the project's `.claude/rules/*.md` references). Universal whitelist alone is NOT sufficient for --auto-amend writes; the project must opt in.

Refuse-block emission is mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":

- **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line:

      STATE: AMENDMENT-AUTO-ISSUE-REFUSED dispatch={{ dispatch_id }} reason=<short-code> action=<short-code> manual_alt=steering-side-writeback

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block with label `AMENDMENT AUTO-ISSUE REFUSED`:

      ## AMENDMENT AUTO-ISSUE REFUSED — dispatch {{ dispatch_id }} at <UTC ISO8601>

      ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
      ~~~
      Dispatch {{ dispatch_id }} amendment auto-issuance refused.

      Reason: <one-line — missing file / all PROJECT whitelist items commented>
      Action: <specific instruction — run /falcon create-rules /
               uncomment `safe_to_amend_whitelist.<item-name>` in
               .claude/rules/falcon-autopilot.md>

      Manual amendment alternative: see PROTOCOL.md "## Amendments Workflow"
      for the steering-side amendment writeback procedure.
      ~~~
      ═══ END COPY ═══

Update snapshot with outcome: "refused"; exit.

## Step 4 — Budget HALT check

If `amendment_budget` is non-null AND `auto_amendment_count >= amendment_budget`:
HALT auto-issuance. Behavior depends on prior_outcome:

- If prior_outcome != "halted": emit ONE `AMENDMENT BUDGET EXHAUSTED` block (this is the first fire to detect exhaustion).
- If prior_outcome == "halted": stay silent (don't spam the user every fire).

In either case, update snapshot with outcome: "halted"; exit.

`AMENDMENT BUDGET EXHAUSTED` notification is mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":

- **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line:

      STATE: AMENDMENT-BUDGET-EXHAUSTED dispatch={{ dispatch_id }} budget_cap=<amendment_budget> auto_issued=<auto_amendment_count> halt=true

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block:

      ## AMENDMENT BUDGET EXHAUSTED — dispatch {{ dispatch_id }} at <UTC ISO8601>

      ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
      ~~~
      Dispatch {{ dispatch_id }} --auto-amend budget exhausted.

      Budget cap:           <amendment_budget>
      Auto-issued so far:   <auto_amendment_count>

      --auto-amend cron will stay silent on subsequent fires for this dispatch.
      --watch cron (if armed) continues reporting state changes normally.

      Any further gaps will require manual amendment relay via the steering
      session per PROTOCOL.md "## Amendments Workflow" (Steering side).
      ~~~
      ═══ END COPY ═══

The `--watch` cron continues unaffected; the `--auto-ack` cron (if armed) also continues. ONLY amendment auto-issuance is halted for this dispatch.

## Step 5 — Identify gaps + evaluate whitelist

Compute the current gap set by re-running the Step 3 validation + Step 3b cognitive audit logic against the dispatch:

1. Schema validate `implementation_results` content.
2. Cross-check commits exist on origin (`git log <sha> --oneline`).
3. Cross-check bead state matches expected (`bd show --json <id>`).
4. File-contract audit: diff dispatch commits against declared `file_scope`.
5. Amendment-status discipline audit: confirm all entries in `amendments[]` are in terminal state (`completed | satisfied | rejected`).
6. Cognitive audit hints from `.claude/rules/falcon-autopilot.md § 4 cognitive_audit_hints` (uncommented only) — apply each `trigger` against the dispatch state; on match, capture the prompts as candidate gaps.

Compute current_gap_hash: `sha256(json.dumps(gap_set, sort_keys=True).encode('utf-8')).hexdigest()`.

If current_gap_hash == prior_gap_hash: gaps unchanged since last fire; exit silently (avoid re-emitting the same defer block on every fire).

If gap_set is empty: nothing to amend; exit silently. Update snapshot with outcome: "no-gaps".

For each gap in gap_set, attempt to match against `safe_to_amend_whitelist` (universal + uncommented project items):

- **Match found AND not in denylist:** prepare the amendment. Construct an `amendments[]` entry per the Amendments Workflow schema (PROTOCOL.md): `amendment_id: "amend-NN"` (next sequential, zero-padded), `created_utc: <now>`, `issued_by: "steering-cron"`, `label: "auto-issued:cron"`, `request: <amendment_text from whitelist entry, with gap-specific substitutions>`, `status: "pending"`, `worker_response: null`, `commits: []`, `worker_completed_utc: null`.

- **Match found BUT also matches denylist (`safe_to_amend_denylist`):** denylist wins. Surface as `AMENDMENT AUTO-ISSUE DEFERRED` block citing the denylist rationale. Update snapshot with outcome: "deferred-denylist".

- **No whitelist match:** surface as `AMENDMENT AUTO-ISSUE DEFERRED` block citing "gap not in SAFE_TO_AMEND whitelist; manual amendment may be appropriate." Update snapshot with outcome: "deferred-no-match".

Defer notification is mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":

- **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line:

      STATE: AMENDMENT-AUTO-ISSUE-DEFERRED dispatch={{ dispatch_id }} gap=<short-summary> reason=<not-in-whitelist|denylist-match> almost_matched=<name-or-none>

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block with label `AMENDMENT AUTO-ISSUE DEFERRED`:

      ## AMENDMENT AUTO-ISSUE DEFERRED — dispatch {{ dispatch_id }} at <UTC ISO8601>

      ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
      ~~~
      Dispatch {{ dispatch_id }} gap NOT auto-amended.

      Gap:    <one-line description of the gap surfaced>
      Reason: <not in whitelist / matches denylist>
      Whitelist entry that almost matched: <name or "none">

      Manual amendment alternative: see PROTOCOL.md "## Amendments Workflow".
      ~~~
      ═══ END COPY ═══

## Step 6 — Auto-issue (when whitelist matches AND budget allows)

For each matched amendment (after budget HALT check passed in Step 4 AND whitelist matched in Step 5):

1. Atomically append the amendment entry to `amendments[]` in the dispatch file (preserve all other fields).
2. Set `session_status: amendments_pending` if not already.
3. Increment `auto_amendment_count` by 1.
4. Re-check budget: if NEW `auto_amendment_count` would exceed `amendment_budget`, issue THIS amendment but skip the rest of the matched amendments this fire (subsequent fires will hit the Step 4 HALT cleanly).
5. Emit the auto-issued notification per `worker_dispatch_mode`. The amendment-file write IS the contract — the notification informs steering; the worker reads `amendments[]` directly. **In `--bg` mode, DO NOT invoke `claude --resume <worker-session> --print "check amendments {{ dispatch_id }}"`** — Claude Code refuses `--resume` on running background agents. The file write of the amendment entry plus session_status amendments_pending is sufficient; the worker self-polls (or operator nudges via `falcon poll` peek-and-reply).

    - **If `worker_dispatch_mode == "bg"`**: emit a single inline STATE: line:

          STATE: AMENDMENT-AUTO-ISSUED dispatch={{ dispatch_id }} amend_id=amend-NN gap=<short-summary> whitelist=<entry-name> budget=<auto_amendment_count>/<amendment_budget or "unlimited">

    - **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block (operator pastes `check amendments` into worker tab):

          ## AMENDMENT AUTO-ISSUED amend-NN — dispatch {{ dispatch_id }} at <UTC ISO8601>

          ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
          ~~~
          check amendments {{ dispatch_id }}

          Amendment amend-NN auto-issued by --auto-amend cron.
          Gap addressed:    <one-line>
          Whitelist match:  <whitelist entry name>
          Budget status:    <auto_amendment_count> of <amendment_budget or "unlimited">

          Dispatch file: {{ dispatch_file_path }}
          Worker should re-read, find pending amendment, and execute per
          PROTOCOL.md "## Amendments Workflow" (Worker side).
          ~~~
          ═══ END COPY ═══

Update snapshot with current_gap_hash + outcome: "issued".

## Step 7 — Self-cancel on terminal state

If current session_status == "complete":
1. CronDelete this cron (lookup by slug: `falcon-amend-{{ dispatch_id }}`)
2. Remove the snapshot file at {{ snapshot_file_path }}
3. Emit a final block with label `AMEND CRON RELEASED` confirming cancellation.

Before exiting — on EVERY fire, terminal or not — apply the wake-opportunism
check per `### Wake-opportunism convention (v7.7.0)` above: probe all active
dispatches for pending actionable state; process each under its own role's rules.

## Multi-cron coordination

When `--watch --auto-ack --auto-amend` are all armed, THREE separate crons run with
independent slugs (`falcon-watch-`, `falcon-autoack-`, `falcon-amend-`) and
independent sidecars. They do not coordinate; each evaluates its own state-change
criteria. /falcon release-cron tears down all three via prefix-match. Cadences
differ: watch defaults to 10m; auto-ack and auto-amend both default to 5m.
```

#### Condensed CronCreate prompt (v7.1.2)

The literal text steering passes to `CronCreate(prompt=...)` for the `--auto-amend` cron — Step 0's adaptive-cadence early-exit guard is kept INLINE (per v7.0.1 fdev-lbq.3; three quiescent windows where the cron has nothing to do, every fire would otherwise pay the full gap-eval cost). Steps 1-7 (and the advisor-extension below if `advisor` field is non-null) are pointer-style. ~450 tokens vs. ~4500 for the full template body + extension. Substituted literals at CronCreate time: `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}`, `{{ branch_name }}`.

```
You are a falcon --auto-amend cron firing against dispatch {{ dispatch_id }}.

Mode: AUTONOMOUS AMENDMENT ISSUANCE. May write entries to amendments[]
on the dispatch file when SAFE_TO_AMEND whitelist matches AND budget not
exhausted. Self-cancel slug: falcon-autoamend-{{ dispatch_id }}.
Dispatch file: {{ dispatch_file_path }}
Snapshot file: {{ snapshot_file_path }}
Repo path: {{ repo_path }}
Branch: {{ branch_name }}

## Step 0 — Adaptive cadence early-exit guard (INLINE, v7.0.1 fdev-lbq.3)

Run a minimal state probe via focused yq queries before full Step 1 capture:

    session_status=$(yq '.session_status' {{ dispatch_file_path }})
    impl_results_hash=$(yq '.implementation_results_hash' {{ dispatch_file_path }})
    amend_budget=$(yq '.amendment_budget' {{ dispatch_file_path }})
    auto_amend_count=$(yq '.auto_amendments_issued // 0' {{ dispatch_file_path }})

Decision tree (three quiescent windows):

1. If `session_status == "complete"`: proceed to Step 7 self-cancel
   (no Step 1 capture).
2. If `impl_results_hash` is null AND `session_status != "complete"`:
   worker hasn't emitted COMPLETION yet; no validation gaps to find.
   Exit silently. Skip Step 1.
3. If `amend_budget` is non-null AND `auto_amend_count >= amend_budget`:
   HALT already detected on a prior fire (Step 4 emission). No further
   amendments to issue. Exit silently. Skip Step 1. (The FIRST detection
   of HALT — when `auto_amend_count` first reaches the budget — flows
   through Step 4 to emit the AMENDMENT BUDGET EXHAUSTED notification;
   only subsequent fires hit this Step 0 case 3 guard.)
4. If `impl_results_hash` non-null AND `session_status != "complete"`
   AND budget not exhausted: active window. Proceed to Step 1 below.

Telemetry: increment `cron_telemetry.autoamend.fires` on entry; on
Step 0 case 2 or case 3 silent-exit, increment `cron_telemetry.autoamend.silent`
and exit. (Case 1 + case 4 paths increment `useful` at the action
boundary downstream.)

## Steps 1-7 — execute per canonical spec

Read CRONS.md `## Autopilot Cron Prompt Templates` → `### --auto-amend
cron prompt template (v6.10.0)` and follow Steps 1 through 7 verbatim.
If the dispatch's `advisor` field is non-null, ALSO read `#### --auto-amend
advisor-extension (v6.12.0)` for the Step 5b advisor-fork extension to
gap evaluation. Mode-conditional emission per `### Cron Dispatch-Mode
Conventions (v7.0.1)`. Telemetry-counter contract per `### Cron Telemetry
Instrumentation (v7.1.0, fdev-lbq.30)` applies on every fire.
```

(End of `--auto-amend` cron prompt template.)

#### `--auto-amend` advisor-extension (v6.12.0)

When `--advisor=<agent>` is set on the dispatch (`advisor: "<agent>"` field non-null), the `--auto-amend` cron's Step 5 (gap evaluation against whitelist) gains a fork-on-ambiguous-gap step. Append to the existing Step 5 logic:

```
## Step 5b — Advisor fork (v6.12.0; only when advisor field is non-null)

After matching each gap against safe_to_amend_whitelist + safe_to_amend_denylist:

If gap matches whitelist AND not in denylist → proceed to Step 6 (auto-issue).
If gap matches denylist → defer per Step 5 deferred-denylist block.

If the evaluation is AMBIGUOUS — gap doesn't clearly match whitelist OR matches
loosely (substring match in trigger but not exact rule_ref hit) AND matches the
advisor_delegation policy in .claude/rules/falcon-autopilot.md § 5 — fork to the
named advisor:

1. Read .claude/rules/falcon-autopilot.md § 5 advisor_delegation entries.
2. Find the entry matching `advisor: "<agent>"` from the dispatch file.
3. Check the entry's `delegates` list for a matching gap-type pattern
   (e.g., `dar_shared_script_extraction` for quartermaster on §3.21-related gaps).
4. If match found AND not in `refuses` list: invoke the advisor agent via Skill,
   passing:
   - the gap description (one-line)
   - the relevant rule reference (from cognitive_audit_hints)
   - the candidate amendment_text (if any whitelist item came close)
   - the dispatch context (bead IDs, file_scope, commits)
   The advisor returns: { recommendation: "issue" | "defer" | "modify",
                          amendment_text: <optional revised text>,
                          rationale: <one-line> }
5. If recommendation == "issue": proceed to Step 6 with response_source:
   /<agent> annotation on the amendment entry. If amendment_text was modified
   by the advisor, use the modified version.
6. If recommendation == "defer": emit deferred-block citing the advisor's
   reasoning. Manual amendment may still be appropriate.
7. If recommendation == "modify" but no amendment_text returned: treat as
   defer; surface for user attention.
8. Emit an ADVISOR FORK block for audit trail before either path:

    ## ADVISOR FORK — dispatch {{ dispatch_id }} at <UTC ISO8601>

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    Ambiguous gap decision forked to advisor.

    Advisor:        /<agent>
    Gap:            <one-line description>
    Recommendation: <issue | defer | modify>
    Rationale:      <one-line from advisor>
    Resulting amendment_text: <quoted if issue/modify, "n/a" if defer>
    ~~~
    ═══ END COPY ═══

If the advisor refuses the question (per the `refuses` list, e.g.
quartermaster refuses fair_play_policy_question and scoring_semantics)
→ defer to user per the normal deferred-block path; do NOT fork.
```

(End of `--auto-amend` advisor-extension.)

### `--worker-cron` cron prompt template (v6.11.0)

The FIRST worker-side cron template (Phases 1-3 templates all run in the steering session). The worker session invokes `CronCreate` with this template body in response to the `--worker-cron` setup paste-block emitted by steering (see below). On each fire, the cron polls the dispatch file for `session_status: amendments_pending`; when found, executes pending amendments per the Amendments Workflow and emits the amendment-completion preamble — eliminating the manual `check amendments <dispatch-id>` relay step.

Worker-side context note: this cron does NOT need refuse-on-MVM. It only acts on amendments that already exist in `amendments[]` — those amendments were either auto-issued (already gated by Phase 3's refuse-on-MVM upstream) or manually issued (user-authorized). The worker cron does not gate writes; it executes already-gated work.

CronCreate call shape (WORKER side, invoked by the worker session after pasting the setup block):

```
CronCreate(
  cron: "{{ schedule_expression }}",            # v7.1.0 (fdev-lbq.28): worker-cron is --via-paste-only (no-op in --bg per PROTOCOL.md); cadence remains operator-supplied via the setup paste-block; default 3. Not bucket-computed because the worker cron's relevance is binary (amendments pending or not) rather than dispatch-shape-driven.
  prompt: <the template below, with literals substituted>,
  durable: false,                              # worker-session-bound; dies when worker session ends
  recurring: true,
)
```

The returned ID is written to `worker_cron_id` in the dispatch file by the worker session.

Template (literal `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}`, `{{ branch_name }}` substituted at CronCreate time, on the WORKER side):

```
You are a falcon --worker-cron firing in the worker session for dispatch {{ dispatch_id }}.

Mode: AUTONOMOUS AMENDMENT EXECUTION. This cron acts on amendments that already
exist in `amendments[]` on the dispatch file. It does NOT issue amendments
itself; it executes them. Per the Amendments Workflow (PROTOCOL.md), the worker
side of the dispatch lifecycle owns this responsibility — this cron just runs
it on a schedule instead of waiting for a manual `check amendments <dispatch-id>`
relay from steering.

## Step 1 — Read current state

Read the dispatch file: {{ dispatch_file_path }}

Capture:
- session_status        (active | amendments_pending | complete)
- amendments[]          (full list, with per-entry status)
- intent_acknowledged_utc (status check only — Phase 2 field)
- worker_dispatch_mode  ("bg" | "via-paste" | "paste" — see defensive check below per "Cron Dispatch-Mode Conventions (v7.0.1)")

**Defensive mode check (v7.0.1)**: if `worker_dispatch_mode == "bg"`, this cron should never have been armed — `--worker-cron` is a no-op in `--bg` mode (the auto-ack-resume guard handles amendment pickup within the persistent background session per PROTOCOL.md `### --bg dispatch mode`). If somehow armed (e.g. operator manually ran the setup paste-block inside a `--bg` worker), self-cancel via Step 5 and exit. This cron only operates in `--via-paste` / `--paste` modes.

If session_status == "complete": self-cancel (Step 5 below) and exit. Steering
has released the lock; the worker's work for this dispatch is done.
If session_status == "active": no amendments expected; exit silently. (Active
means initial dispatch in progress; amendments come after the worker emits
COMPLETION.)
If session_status == "amendments_pending": proceed to Step 2.

## Step 2 — Read prior snapshot

Read {{ snapshot_file_path }} if it exists. If absent, set last_processed_amendment_id = null.

The snapshot stores: { last_processed_amendment_id } — the highest amendment_id
this cron has already executed (terminal status set + worker_response written).

## Step 3 — Identify pending amendments newer than the snapshot

Filter `amendments[]` to entries where status == "pending" AND amendment_id >
last_processed_amendment_id (string-compare works because the IDs are
zero-padded sequential: amend-01, amend-02, …).

If no pending amendments newer than the snapshot: exit silently. (Either there
are no pending amendments at all, OR this cron has already processed everything
pending — perhaps the user manually triggered them between fires.)

## Step 4 — Execute each pending amendment

For each pending amendment (in amendment_id order):

a. Atomically set `status: in_progress` on the amendment entry (preserve all
   other fields).
b. Read the `request` field as the binding spec.
c. **Check first whether the amendment's intent is already satisfied** (per the
   Amendments Workflow `satisfied` semantic). If yes → set `status: satisfied`
   with a `worker_response` citing the verification. Emit
   `AMENDMENT SATISFIED amend-NN` per the labeled-copy convention. Skip to
   next pending amendment.
d. Otherwise: execute the request within the same file_scope as the original
   dispatch (raise high-stakes DAR if amendment requires out-of-scope files;
   emit `AMENDMENT REJECTED amend-NN` and continue).
e. Write `worker_response` with observable evidence (not just "done").
f. Write `commits[]` with any new commit shas.
g. Set `worker_completed_utc: <UTC ISO8601>` + `status: completed`.
h. Commit + push if there were code changes:
   `git pull --rebase origin {{ branch_name }} && git push`
i. Emit the amendment-completion preamble using label
   `AMENDMENT COMPLETION amend-NN` per the v6.5.3 labeled-copy convention.

After processing each amendment, update the snapshot:
`last_processed_amendment_id = <amendment_id just processed>`.

If ANY amendment processing raises a high-stakes DAR or a hard error: STOP
iteration on remaining amendments this fire (subsequent fires will retry the
unprocessed ones). Emit the DAR / error per the standard worker-side DAR
protocol; the steering session will handle.

## Step 5 — Self-cancel on terminal state

If current session_status == "complete":
1. CronDelete this cron (lookup by slug: `falcon-worker-{{ dispatch_id }}`)
2. Remove the snapshot file at {{ snapshot_file_path }}
3. Emit a final block with label `WORKER-CRON RELEASED` confirming cancellation.

## Coordination with steering-side crons

Steering arms `falcon-watch-`, `falcon-autoack-`, `falcon-amend-` in its own
session. This worker cron `falcon-worker-` runs in the worker session. The four
crons do not communicate directly; they all read/write the same dispatch file
on shared filesystem. The dispatch file's atomic-write semantics are the
coordination primitive.

The worker cron's writes to `amendments[].status` are visible to steering's
`--auto-amend` cron on its next fire (which uses them as part of the
amendment-status discipline audit). Conversely, the steering `--auto-amend`
cron's writes to `amendments[]` (new pending entries) are visible to this worker
cron on its next fire (which picks them up via Step 3).

The `durable: false` flag on this cron ensures it dies with the worker session.
If the worker session exits before steering releases the lock, the cron is gone
— amendments queued after worker death cannot be picked up by this cron and
require re-dispatch (per the dead-worker constraint in Amendments Workflow).
```

#### Condensed CronCreate prompt (v7.1.2)

The literal text the worker session passes to `CronCreate(prompt=...)` for the `--worker-cron` cron (worker-side, after pasting the setup block below). The defensive `worker_dispatch_mode == "bg"` self-cancel check is kept INLINE because it's a single-field probe that prevents bogus operation if the cron is somehow armed in `--bg` mode (no-op per PROTOCOL.md). Steps 1-5 are pointer-style. ~250 tokens vs. ~2500 for the full template body. Substituted literals at CronCreate time: `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}`, `{{ branch_name }}`.

```
You are a falcon --worker-cron firing in the worker session for dispatch
{{ dispatch_id }}.

Mode: AUTONOMOUS AMENDMENT EXECUTION. Acts on amendments already in
amendments[] on the dispatch file. Self-cancel slug:
falcon-workercron-{{ dispatch_id }}.
Dispatch file: {{ dispatch_file_path }}
Snapshot file: {{ snapshot_file_path }}
Repo path: {{ repo_path }}
Branch: {{ branch_name }}

## Defensive mode check (INLINE, v7.0.1)

    worker_dispatch_mode=$(yq '.worker_dispatch_mode' {{ dispatch_file_path }})

If `worker_dispatch_mode == "bg"`: this cron should never have been armed
(--worker-cron is a no-op in --bg per PROTOCOL.md `### --bg dispatch mode`;
the worker self-poll mechanism at v7.1.1 `## Worker Self-Poll Cron
Templates` handles --bg amendment pickup natively). Self-cancel via
Step 5 and exit. Increment `cron_telemetry.workercron.silent` and
record the bogus-arm event in cron telemetry.

## Steps 1-5 — execute per canonical spec

Read CRONS.md `## Autopilot Cron Prompt Templates` → `### --worker-cron
cron prompt template (v6.11.0)` and follow Steps 1 through 5 verbatim
against `amendments[]` per the Amendments Workflow (PROTOCOL.md). Mode-
conditional emission per `### Cron Dispatch-Mode Conventions (v7.0.1)`
applies to `--via-paste` / `--paste` only (this cron is no-op in `--bg`
per the defensive check above). Telemetry-counter contract per `### Cron
Telemetry Instrumentation (v7.1.0, fdev-lbq.30)` applies on every fire.
```

(End of `--worker-cron` cron prompt template.)

### `--worker-cron` setup paste-block (v6.11.0)

The short message steering emits for the user to paste into the worker tab when `--worker-cron` (or `--autopilot`) is set. The worker session receives this paste, invokes `CronCreate` with the `--worker-cron` cron prompt template body (above), and writes the returned ID to `worker_cron_id` on the dispatch file.

Emitted by steering at Step 2 (Write Dispatch File + Emit Worker Prompt), alongside the standard dispatch prompt. The user pastes both into the worker tab (in order: dispatch prompt first, then worker-cron-setup).

Wrapped per the v6.5.3 labeled-copy convention with label `WORKER-CRON SETUP`:

    ## WORKER-CRON SETUP — dispatch {{ dispatch_id }} at {{ created_utc }}

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    Arm the falcon worker cron for dispatch {{ dispatch_id }}.

    This dispatch was created with --worker-cron (or --autopilot). The worker
    session should poll the dispatch file periodically for pending amendments
    and execute them automatically instead of waiting for manual relay.

    Steps:

    1. Read the worker-cron template body from:
       .claude/skills/falcon/REFERENCE.md
       Section: ## Autopilot Cron Prompt Templates
       Entry:   ### --worker-cron cron prompt template (v6.11.0)

    2. Invoke CronCreate with these parameters:
         cron: "*/3 * * * *"            # default 3-minute cadence; OR
                                        # "*/<N> * * * *" if --cron-cadence Nm was set
         prompt: <the template body from step 1, with literals substituted:
                  {{ dispatch_id }}        → {{ dispatch_id }}
                  {{ dispatch_file_path }} → {{ dispatch_file_path }}
                  {{ snapshot_file_path }} → .claude/tmp/falcon-worker-{{ dispatch_id }}-state.json
                  {{ repo_path }}          → {{ repo_path }}
                  {{ branch_name }}        → {{ branch_name }} >
         durable: false                 # worker-session-bound
         recurring: true

    3. Capture the returned cron ID.

    4. Write the cron ID to worker_cron_id on the dispatch file:
       (use yq or atomic-replace; preserve all other fields)
       yq -i ".worker_cron_id = \"<cron-id-from-step-3>\"" {{ dispatch_file_path }}

    5. Emit the ack block per the labeled-copy convention:

           ## WORKER-CRON ARMED — dispatch {{ dispatch_id }} at <UTC ISO8601>

           ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
           ~~~
           Worker cron armed for dispatch {{ dispatch_id }}.

           Cron ID:    <cron-id>
           Cadence:    <N>-minute polling for session_status: amendments_pending
           Sidecar:    .claude/tmp/falcon-worker-{{ dispatch_id }}-state.json

           Amendments will be picked up and executed automatically. Manual
           `check amendments {{ dispatch_id }}` relays from steering are no
           longer needed for this dispatch. The cron dies with this worker
           session (durable: false).
           ~~~
           ═══ END COPY ═══

    Then proceed with the rest of the dispatch lifecycle (intent confirm,
    claim, implement, etc.) as the normal worker would. The cron runs
    in the background and acts only when session_status transitions to
    amendments_pending.
    ~~~
    ═══ END COPY ═══

(End of `--worker-cron` setup paste-block.)

### `--release-on-merge` cron prompt template (v6.12.0)

Fired by the cron armed at Step 2 of the dispatch protocol when `--release-on-merge` is set. Polls `gh pr view --json state` for the dispatch's branch on each fire; on `state: MERGED`, sets `session_status: complete` on the dispatch file, which triggers the normal auto-release path in Step 4 and self-cancellation across all other crons for this dispatch.

This cron is intentionally simple — single external dependency (`gh pr view`), single state transition on detection, no whitelist/gate evaluation. No refuse-on-MVM (does not consult the gate file at all).

CronCreate call shape (steering side, at Step 2):

```
CronCreate(
  cron: "*/<N> * * * *",                       # N from --cron-cadence; default 15. Release-on-merge cron is NOT bucket-computed (cadence reflects PR-merge polling frequency, not bead shape).
  prompt: <the template below, with literals substituted>,
  durable: false,
  recurring: true,
)
```

The returned ID is written to `merge_cron_id` in the dispatch file.

Template (literal `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}`, `{{ branch_name }}` substituted at CronCreate time):

```
You are a falcon --release-on-merge cron firing against dispatch {{ dispatch_id }}.

Mode: PR-MERGE OBSERVATION + LOCK-RELEASE TRIGGER. This cron polls the PR for
the dispatch's branch, and on merge detection, sets session_status: complete on
the dispatch file. It does NOT release the lock directly (Step 4 of the dispatch
protocol does that on the session_status transition). It does NOT issue
amendments, does NOT acknowledge intent, does NOT modify bd state.

## Step 1 — Read current state

Read the dispatch file: {{ dispatch_file_path }}

Capture:
- session_status      (active | amendments_pending | complete)
- release_on_merge    (should be true; if false, exit silently as a sanity check)
- branch              (target for gh pr view)
- worker_dispatch_mode ("bg" | "via-paste" | "paste" — drives all emission shapes below per "Cron Dispatch-Mode Conventions (v7.0.1)")

If session_status == "complete": self-cancel (Step 5 below) and exit.
If release_on_merge != true: exit silently (operator error; cron should not have been armed).

## Step 2 — Read prior snapshot

Read {{ snapshot_file_path }} if it exists. If absent, set prior_pr_state = null.

Snapshot stores: { pr_state, pr_number, last_polled_utc }.

## Step 3 — Poll PR state

Run: `gh pr view --json state,number --head {{ branch_name }} --repo <derived from git remote>`

Two possible outcomes:
- **No PR found** (gh returns error): emit `MERGE CRON NO-PR` block ONCE (only if prior_pr_state was non-null, OR this is the first fire). Then write snapshot { pr_state: null, ... } and exit. The cron continues running; eventually a PR will exist and the next fire will pick it up.
- **PR found**: capture pr_state (DRAFT | OPEN | MERGED | CLOSED) and pr_number.

If pr_state == prior_pr_state: state unchanged; exit silently. (Avoid emitting on every fire when the PR sits in OPEN for hours.)

## Step 4 — Act on state transition

State transitions of interest:

- **null → DRAFT/OPEN**: emit `MERGE-WATCH PR-DETECTED` notification citing pr_number + state. The cron continues running; will trigger on MERGED.
- **DRAFT/OPEN → MERGED**: this is the trigger. Atomically set `session_status: complete` on the dispatch file (preserve all other fields). Emit `MERGE-DETECTED` notification citing the merge commit + pr_number. The cron stays armed until next fire when Step 1 detects session_status: complete and self-cancels.
- **DRAFT/OPEN → CLOSED (not merged)**: emit `MERGE-CRON PR-CLOSED-UNMERGED` notification. DO NOT set session_status: complete (the work was abandoned, not released). Steering must decide manually whether to release the lock via /falcon release.
- **DRAFT → OPEN**: emit `MERGE-WATCH PR-READY` notification (informational). No state change.

**All four emissions are mode-conditional per "Cron Dispatch-Mode Conventions (v7.0.1)":**

- **If `worker_dispatch_mode == "bg"`**: emit a single inline `STATE:` line per transition (no fence):

      STATE: MERGE-DETECTED dispatch={{ dispatch_id }} branch={{ branch_name }} pr=<pr_number> merge_sha=<sha>
      STATE: MERGE-WATCH-PR-DETECTED dispatch={{ dispatch_id }} pr=<pr_number> state=<DRAFT|OPEN>
      STATE: MERGE-CRON-PR-CLOSED-UNMERGED dispatch={{ dispatch_id }} pr=<pr_number> manual_release=required
      STATE: MERGE-WATCH-PR-READY dispatch={{ dispatch_id }} pr=<pr_number>
      STATE: MERGE-CRON-NO-PR dispatch={{ dispatch_id }} branch={{ branch_name }}

- **If `worker_dispatch_mode == "via-paste"` or `"paste"`**: emit the labeled-copy block. The `MERGE-DETECTED` (load-bearing) block format is shown below as the canonical example; the other transitions use analogous block shapes (labels: `MERGE-WATCH PR-DETECTED`, `MERGE-CRON PR-CLOSED-UNMERGED`, `MERGE-WATCH PR-READY`, `MERGE-CRON NO-PR`).

`MERGE-DETECTED` block (the load-bearing emission — `--via-paste`/`--paste` mode):

    ## MERGE-DETECTED — dispatch {{ dispatch_id }} at <UTC ISO8601>

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    PR for dispatch {{ dispatch_id }} merged.

    Branch:        {{ branch_name }}
    PR number:     <pr_number>
    Merged commit: <gh-returned merge sha>

    session_status: complete written to {{ dispatch_file_path }}.
    Step 4 auto-release path will pick this up on next steering invocation.
    Other crons for this dispatch (watch/autoack/amend/worker) will self-cancel
    on their next fires.
    ~~~
    ═══ END COPY ═══

Update snapshot { pr_state: MERGED, pr_number, last_polled_utc }.

## Step 5 — Self-cancel on terminal state

If current session_status == "complete":
1. CronDelete this cron (lookup by slug: `falcon-merge-{{ dispatch_id }}`)
2. Remove the snapshot file at {{ snapshot_file_path }}
3. Emit a final block with label `MERGE-CRON RELEASED` confirming cancellation.

Before exiting — on EVERY fire, terminal or not — apply the wake-opportunism
check per `### Wake-opportunism convention (v7.7.0)` above: probe all active
dispatches for pending actionable state; process each under its own role's rules.

## Interaction with Step 4 (Stash for Wrapup + Auto-Release)

Step 4 of the dispatch protocol has a NEW hold-the-lock condition added in v6.12.0:
"release_on_merge: true AND session_status != complete". This means that when the
worker completes and steering reaches Step 4, the lock STAYS HELD until this cron
detects merge and flips session_status to complete. On the next steering invocation
after that, Step 4 sees the new session_status and runs the auto-release path
normally.

This decouples PR merge from worker completion: the worker can finish, push commits,
emit COMPLETION, and steering can stash the report — but the lock blocks other
dispatches from claiming overlapping files until the human review + merge actually
happens. Useful for paranoid lock-release on sensitive file scopes.
```

#### Condensed CronCreate prompt (v7.1.2)

The literal text steering passes to `CronCreate(prompt=...)` for the `--release-on-merge` cron — a thin pointer to the canonical Steps 1-5 spec above. ~200 tokens vs. ~2200 for the full template body. `--release-on-merge` has no Step 0 adaptive guard (single-purpose poller with one external call and one state-transition write; no quiescent window to optimize). Substituted literals at CronCreate time: `{{ dispatch_id }}`, `{{ dispatch_file_path }}`, `{{ snapshot_file_path }}`, `{{ repo_path }}`, `{{ branch_name }}`.

```
You are a falcon --release-on-merge cron firing against dispatch
{{ dispatch_id }}.

Mode: PR-MERGE OBSERVATION + LOCK-RELEASE TRIGGER. Polls `gh pr view` for
the dispatch's branch; on `state: MERGED`, sets session_status: complete
on the dispatch file (the auto-release path in PROTOCOL.md Step 4 picks
up from there). Self-cancel slug: falcon-mergewatch-{{ dispatch_id }}.
Dispatch file: {{ dispatch_file_path }}
Snapshot file: {{ snapshot_file_path }}
Repo path: {{ repo_path }}
Branch: {{ branch_name }}

Read CRONS.md `## Autopilot Cron Prompt Templates` → `### --release-on-merge
cron prompt template (v6.12.0)` and follow Steps 1 through 5 verbatim.
Mode-conditional emission per `### Cron Dispatch-Mode Conventions
(v7.0.1)`. Telemetry-counter contract per `### Cron Telemetry
Instrumentation (v7.1.0, fdev-lbq.30)` applies on every fire.
```

(End of `--release-on-merge` cron prompt template.)
