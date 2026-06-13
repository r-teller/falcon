---
parent: SKILL.md
version: 7.0.0
---

# Falcon — Reference: Schemas and Templates

> This file contains the dispatch file YAML schema, session JSON schema extension, init_prompt content template, dispatch prompt template, and copy-paste emission convention.
> For lifecycle protocol: see [`PROTOCOL.md`](./PROTOCOL.md).
> For CLI surface: see [`COMMANDS.md`](./COMMANDS.md).

---

## Copy-Paste Emission Convention

Applies to ALL multi-line paste blocks in BOTH directions (steering→worker and worker→steering).

When emitting a paste block, wrap the content in an explicit labeled boundary:

1. **Markdown heading** on its own line: `## LABEL — dispatch <id> at <UTC ISO8601>`
2. Blank line
3. **Sentinel header** on its own line: `═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══`
4. **Tilde code fence** (`~~~`) opening the block. Tildes (NOT backticks) so the content can freely contain backticks for command syntax without escaping.
5. **Paste content** (the actual prompt / amendment / revision / intent / completion text).
6. **Tilde code fence** (`~~~`) closing the block.
7. **Sentinel footer** on its own line: `═══ END COPY ═══`

### Labels (extensible)

| Label | Direction | When used |
|---|---|---|
| `DISPATCH PROMPT` | steering→worker | Initial worker-onboarding block |
| `AMENDMENT amend-NN` | steering→worker | Follow-up instruction during active dispatch |
| `SCOPE-EXPANSION REVISION` | steering→worker | Response to worker scope-question at intent-confirm |
| `INTENT` | worker→steering | Intent paragraph emitted at intent-confirm pause |
| `COMPLETION` | worker→steering | Completion-signal preamble |
| `COMPLETION (partial)` | worker→steering | Partial report completion preamble |
| `AMENDMENT COMPLETION amend-NN` | worker→steering | Per-amendment completion preamble |
| `AMENDMENT SATISFIED amend-NN` | worker→steering | Amendment satisfied without action |
| `AMENDMENT REJECTED amend-NN` | worker→steering | Amendment rejected (impossible/out-of-scope) |

Projects may define additional labels as new emission types emerge.

### Timestamp format

UTC ISO8601 generated at emission time via `date -u +%Y-%m-%dT%H:%M:%SZ` or Python `datetime.utcnow().isoformat() + 'Z'`. The timestamp is the wall-clock time of emission — useful for correlating interleaved messages across multiple concurrent dispatches.

### Relay-for-review pattern (worker→steering)

When the user wants to send a worker emission back to the steering thread for review, copy from the `##` heading through the `═══ END COPY ═══` line — both inclusive. The heading carries dispatch id + timestamp, so the steering thread knows what it's looking at without the user adding narrative context.

### Example (steering→worker dispatch prompt)

```
## DISPATCH PROMPT — dispatch abc123 at 2026-05-23T18:20:00Z

═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
~~~
You are working autonomously in the repo at /opt/git/example.
This is a falcon dispatch.
Dispatch file: .claude/tmp/falcon-dispatch-abc123.yaml
...
~~~
═══ END COPY ═══
```

### Example (worker→steering intent emission, v6.12.1+)

INTENT blocks include a 2-line dispatch-identity header (`Working dispatch <id> on branch <branch>` + `Beads: [<id>: "<title>", ...]`) ABOVE the intent paragraph. This is the last visual checkpoint where a user with multiple worker tabs can spot a wrong-dispatch paste before typing `proceed <id>`. See PROTOCOL.md "## Worker Lifecycle" Step 3 (intent confirmation) for the requirement.

```
## INTENT — dispatch abc123 at 2026-05-23T18:25:00Z

═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
~~~
Working dispatch abc123 on branch feature/work-20260523-foo
Beads: [example-xyz.1: "Add foo to bar", example-xyz.2: "Test foo"]

<intent paragraph(s)>

Intent above written to .claude/tmp/falcon-dispatch-abc123.yaml.
Trigger 'proceed abc123' when ready, or paste revisions.
~~~
═══ END COPY ═══
```

(For single-bead dispatches, `Beads:` is a one-entry list. For long bead titles, abbreviate each to ~40 chars to keep the header scannable.)

**Skip the convention** only for single-line emissions where the boundary is obvious (e.g., just `proceed abc123` alone — no surrounding narrative).

---

## Dispatch File YAML Schema

The dispatch file at `.claude/tmp/falcon-dispatch-<6hex>.yaml` has this structure:

```yaml
dispatch_id: "<6hex>"
schema_version: 2
created_utc: "<ISO8601>"
repo_path: "<absolute repo path>"
branch: "<branch name>"
spec: "<original spec, e.g. ckl.5,ckl.6>"
bead_ids: ["<bead-id>", ...]

session_status: "active"   # steering sets: active | amendments_pending | complete
                            # worker checks on each resume prompt

watch_cron_id: null   # set by steering at Step 2 (Write Dispatch File) when --watch is set;
                      # the CronCreate-returned ID for the steering-side watch cron armed
                      # against this dispatch. Naming convention: `falcon-watch-<dispatch-id>`
                      # (see PROTOCOL.md "### --watch mode (autopilot observability
                      # foundation, v6.8.0)" and REFERENCE.md "## Autopilot Cron Prompt
                      # Templates"). The cron writes its last-observed-state snapshot to
                      # `.claude/tmp/falcon-watch-<dispatch-id>-state.json` between fires so
                      # successive fires can detect state changes. /falcon status and
                      # /falcon release-cron use the convention for prefix-match lookups.

autoack_cron_id: null   # set by steering at Step 2 (Write Dispatch File) when --auto-ack is set;
                        # the CronCreate-returned ID for the steering-side intent-ack cron
                        # armed against this dispatch. Naming convention:
                        # `falcon-autoack-<dispatch-id>` (see PROTOCOL.md "### --auto-ack mode
                        # (autopilot intent acknowledgement, v6.9.0)" and REFERENCE.md
                        # "### --auto-ack cron prompt template (v6.9.0)"). Sidecar snapshot:
                        # `.claude/tmp/falcon-autoack-<dispatch-id>-state.json` tracks the
                        # last-evaluated intent-paragraph hash so successive fires don't
                        # re-evaluate an unchanged intent. Same prefix-match convention as
                        # watch_cron_id for /falcon status + /falcon release-cron.

intent_acknowledged_utc: null   # written by the --auto-ack cron when SAFE_TO_ACK_INTENT
                                # passes (or by steering on manual relay). Worker checks on
                                # resume: if non-null AND no commits yet, skip intent-confirm
                                # pause and proceed straight to claim. See PROTOCOL.md
                                # "## Worker Lifecycle" Step 3 (intent confirmation) for the
                                # worker-side guard. v6.9.0+ (Phase 2 of autopilot rollout).

amend_cron_id: null   # set by steering at Step 2 (Write Dispatch File) when --auto-amend is set;
                      # CronCreate-returned ID for the steering-side amendment-issuance cron
                      # armed against this dispatch. Naming convention:
                      # `falcon-amend-<dispatch-id>` (see PROTOCOL.md "### --auto-amend mode
                      # + --amendment-budget HALT (v6.10.0)" and REFERENCE.md "### --auto-amend
                      # cron prompt template (v6.10.0)"). Sidecar snapshot:
                      # `.claude/tmp/falcon-amend-<dispatch-id>-state.json` tracks the
                      # last-evaluated gap-set hash + last fire outcome so successive fires
                      # don't re-issue the same amendment for an unchanged gap set. Same
                      # prefix-match teardown convention via /falcon release-cron.

amendment_budget: null   # cap value set by --amendment-budget N at dispatch time (v6.10.0+).
                         # null = no cap (cron issues indefinitely while gaps surface AND
                         # SAFE_TO_AMEND whitelist matches). When non-null, the --auto-amend
                         # cron HALTs auto-issuance once auto_amendment_count reaches this
                         # value; subsequent gaps surface inline as
                         # "amendment budget exhausted — defer to user." Manual amendments
                         # (issued_by: user) do NOT decrement the budget; only
                         # auto-issued:cron-labeled amendments count.

auto_amendment_count: 0   # running counter, incremented by the --auto-amend cron on each
                          # successful auto-issue (v6.10.0+). Read by the budget HALT check
                          # in the cron template. Persists across cron fires; never reset
                          # within a single dispatch. Resets implicitly on a new dispatch
                          # (new dispatch_id = new dispatch file = field initialized to 0).

worker_cron_id: null   # written by the WORKER session (not steering) when it arms its
                       # amendment-pickup cron in response to the --worker-cron setup
                       # paste-block (v6.11.0+). Naming convention:
                       # `falcon-worker-<dispatch-id>`. Sidecar snapshot (worker-side):
                       # `.claude/tmp/falcon-worker-<dispatch-id>-state.json` tracks the
                       # last-processed amendment_id so successive cron fires don't
                       # re-process the same amendment. Steering reads this field via
                       # /falcon status as the source of truth for worker-cron existence
                       # (steering's CronList cannot see worker-session crons). /falcon
                       # release-cron tears down ONLY steering-side crons; worker-cron
                       # teardown requires either the worker session naturally ending
                       # (durable: false → cron dies with session) OR a manual teardown
                       # paste-block into the worker tab.

release_on_merge: false   # set to true by --release-on-merge at dispatch time (v6.12.0+).
                          # When true, Step 4 (Stash for Wrapup + Auto-Release) gains a new
                          # hold-the-lock condition: the lock stays held until the PR for
                          # this branch is merged. The falcon-merge-<dispatch-id> cron (armed
                          # at Step 2) polls `gh pr view --json state` every 15 min and, on
                          # state == "MERGED", sets session_status: complete, which triggers
                          # the normal auto-release path and self-cancellation across all
                          # other crons for this dispatch.

merge_cron_id: null   # CronCreate-returned ID for the merge-poll cron (v6.12.0+).
                      # Naming convention: `falcon-merge-<dispatch-id>`. Sidecar snapshot:
                      # `.claude/tmp/falcon-merge-<dispatch-id>-state.json` tracks the
                      # last-observed PR state so successive cron fires don't re-poll if
                      # state is unchanged. Default cadence 15 minutes (longer than the
                      # write-bearing crons because PR merges are low-frequency state changes
                      # and the cache-miss is amortized over the longer wait). Same
                      # prefix-match teardown via /falcon release-cron.

phase_transitions: []   # v7.1.0 LIVE (fdev-lbq.29 implements fdev-lbq.27 spec).
                        # Forensic record of dispatch lifecycle phase transitions.
                        # Each entry is appended by the Phase Transition Handler
                        # (PROTOCOL.md `### Phase Transition Handler (v7.1)`) when
                        # current_phase (computed from existing fields) changes:
                        #   - from: pre_intent | intent_confirm | implementation |
                        #           verify_amendment | post_validated
                        #   - to: same enum
                        #   - utc: ISO8601 timestamp of transition detection
                        #   - cron_re_arms: list of per-cron actions during this
                        #     transition. Each entry:
                        #       - cron: "watch" | "autoack" | "amend"
                        #       - old_id: <cron-id string> | null
                        #       - new_id: <cron-id string> | null
                        #       - old_cadence_m: integer minutes | null
                        #       - new_cadence_m: integer minutes | null
                        #       - self_cancelled: true | false
                        #       - rearm_failure: null | <error short-code>
                        # current_phase is NOT stored here — computed from
                        # implementation_intent / intent_acknowledged_utc /
                        # implementation_results_hash / session_status. See
                        # PROTOCOL.md `### Mode selection + detection` §"Dispatch
                        # lifecycle phases" for the derivation rule.
                        #
                        # v7.1.0 cron_re_arms[] entry shapes:
                        #   - Re-armed:   { cron, old_id, new_id, old_cadence_m, new_cadence_m }
                        #   - Self-cancel: { cron, self_cancelled: true, old_id, old_cadence_m }
                        #   - No-op:      { cron, no_op: true, old_cadence_m, new_cadence_m }
                        #                 (new == old; handler skipped CronDelete/CronCreate)
                        #   - Skipped:    { cron, skipped: true, reason: "not armed" }
                        #                 (cron_id was null on the dispatch file; nothing to manage)
                        #   - Failed:     { cron, error: "create_failed" | "delete_failed", details }
                        #                 (graceful degrade; <cron>_cron_id unchanged)

cron_telemetry: {}   # v7.1.0 LIVE (fdev-lbq.30 implements fdev-lbq.6 spec).
                     # Each cron template increments its own counters here on fire-entry,
                     # classifying the exit as "silent" (Step 0 early-exit) or "useful" (Step 1+
                     # executed any work). Schema per cron slug:
                     #   cron_telemetry:
                     #     watch:    { fires: N, silent: M, useful: K }
                     #     autoack:  { fires: N, silent: M, useful: K }
                     #     autoamend:{ fires: N, silent: M, useful: K }
                     #     merge:    { fires: N, silent: M, useful: K }
                     #     worker:   { fires: N, silent: M, useful: K } (--via-paste only)
                     # /falcon retro --branch aggregates these per dispatch and emits a "Cron
                     # Telemetry" subsection summarizing fire counts + signal-density ratios.
                     # Useful for empirical autopilot calibration — operators can verify
                     # whether the v7.0.1 adaptive-cadence guards (fdev-lbq.2/.3) + v7.1.0
                     # forecast bucketing (fdev-lbq.28) + per-phase re-arming (fdev-lbq.29)
                     # are landing on signal-density numbers > 30% as expected.
                     # Implementation contract: see REFERENCE.md `### Cron Telemetry
                     # Instrumentation (v7.1.0, fdev-lbq.30)` for slug map + classify rules
                     # + atomic-write discipline + backward-compat notes.

advisor: null   # set to "<agent-name>" (e.g., "quartermaster") by --advisor=<agent> at
                # dispatch time (v6.12.0+). Read by --auto-ack and --auto-amend cron
                # templates to know whether to fork ambiguous decisions to the named agent
                # (per .claude/rules/falcon-autopilot.md § 5 advisor_delegation policy).
                # The advisor's recommendation, if it falls within safe_to_amend_whitelist
                # (or passes safe_to_ack_intent gates), is auto-issued with response_source:
                # /<agent> annotation. Otherwise surfaced inline for user action. null = no
                # advisor configured; ambiguous decisions default to user-relay path.

worker_dispatch_mode: "bg"   # v7.0.0+. Values: "bg" | "via-paste" | "paste". Set by
                             # steering at Step 2 after Mode selection + detection runs.
                             # Default "bg" on new dispatches; auto-downgrades to
                             # "via-paste" when version-gate or disableAgentView check
                             # fails. Autopilot crons consult this field to decide
                             # whether to apply the --bg-aware behavior (skip
                             # worker-cron paste-block; auto-ack-resume guard suffices)
                             # or the legacy --via-paste behavior (emit paste-blocks
                             # as before).

worker_bg_session_id: null   # v7.0.0+. The short session ID returned by
                             # `claude --bg --name "falcon-<dispatch-id>" "<bootstrap>"`
                             # at Step 2 dispatch invocation. Sources of truth: this
                             # field is the CURRENT worker for `claude attach` /
                             # `claude logs` / `claude stop` reference. On respawn-fresh,
                             # the prior value moves to worker_bg_prior_sessions[] and
                             # this field is replaced with the new session ID. null when
                             # worker_dispatch_mode != "bg" (paste-tab dispatches have no
                             # background-session ID to capture).

worker_bg_isolation: null   # v7.0.0+. Values: null (inherit project setting) |
                            # "isolated" (force worktree isolation via --bg-isolated) |
                            # "none" (force no isolation via --bg-no-isolation).
                            # Default null = inherit `worktree.bgIsolation` from
                            # .claude/settings.json; if no setting present, defer to
                            # Claude Code's built-in default (currently isolated). Per-
                            # dispatch override via the two --bg-* flags.

worker_model: "inherit"     # v7.4.0+. Model the worker session runs. Values: "inherit"
                            # (default — omit --model at launch; worker gets the
                            # environment default, identical to pre-v7.4.0 behavior) |
                            # any valid model ID accepted by `claude --model`.
                            # Set by steering at Step 2 from the Step 1 proposal surface
                            # (user can override the proposal). v7.5.0+: the
                            # `/falcon work beads --model <model-id|auto|inherit>` flag
                            # maps 1:1 onto this field, resolved BEFORE this file is
                            # written (orchestrator-owns-model invariant; `auto`
                            # resolves via model_defaults policy then bead-evaluated
                            # fallback — see COMMANDS.md `### --model`). Consumed by the --bg
                            # launch wiring. ENFORCEABLE IN --bg MODE ONLY (same caveat
                            # as worker_thinking_mode below): in via-paste/paste modes
                            # no launch runs, so the field is recorded but advisory —
                            # the worker tab runs whatever model the operator launched.
                            # Readers (crons, /falcon status, /wrapup) get ground truth
                            # only when worker_dispatch_mode == "bg"; otherwise this is
                            # what was REQUESTED, not what runs — cross-check
                            # worker_dispatch_mode before reporting it as fact.
                            # respawn-fresh successors reuse this value; as of v7.5.0
                            # `respawn-fresh --model <id>` rewrites it BEFORE relaunch
                            # (recorded value stays authoritative for later respawns).
                            # Missing field = "inherit" (pre-v7.4.0 dispatch files need
                            # no migration).

worker_model_rationale: null   # v7.5.0+. One-line rationale recorded when worker_model was
                               # resolved via `--model auto`: either "model_defaults: <matched
                               # key>" (policy hit) or the bead-evaluated reasoning (policy
                               # miss). null for inherit and explicit <model-id> dispatches.
                               # Surfaced by /falcon status and the dispatch report so AFK
                               # operators can audit why autopilot picked the model it did.
                               # Missing field = null (pre-v7.5.0 files need no migration).

escalations: []   # v7.5.0+. Intent-gate model escalations, oldest first. Appended by the
                  # `escalate <dispatch-id>` verb (source: operator) or the --auto-ack
                  # cron's escalation path (source: auto-ack-cron) BEFORE the respawn-fresh
                  # relaunch. Each entry:
                  #   - from_model: "<worker_model at escalation time>"
                  #     to_model: "<resolved target model-id>"
                  #     rationale: "<one line — why the intent signalled tier insufficiency>"
                  #     source: "operator | auto-ack-cron"
                  #     escalated_utc: "<ISO8601>"
                  # len(escalations[]) is the consumed escalation count, compared against the
                  # project's escalation_budget (falcon-autopilot.md § 8; default 1). Separate
                  # budget from amendment_budget — neither decrements the other. Shown by
                  # /falcon status + /falcon list-pending; surfaced in the dispatch report's
                  # decisions_for_human[] (see Worker Return Contract). The respawn itself
                  # also appends the normal worker_bg_prior_sessions[] forensic entry (reason
                  # code manual-replace; this list carries the escalation semantics).
                  # Missing field = [] (pre-v7.5.0 files need no migration). See PROTOCOL.md
                  # `### Intent-gate model escalation (v7.5.0)`.

worker_thinking_mode: "inherit"   # v7.4.0+. Extended-thinking budget for the worker.
                                  # Values: "inherit" (default — no env injected) |
                                  # "none" | "think" | "ultrathink". Delivered via
                                  # MAX_THINKING_TOKENS env on the claude --bg launch
                                  # (none=0, think=10000, ultrathink=31999) — session-wide
                                  # for the worker's whole lifecycle. ENFORCEABLE IN --bg
                                  # MODE ONLY: steering owns the spawned process env. In
                                  # via-paste/paste modes the field is recorded but
                                  # advisory (the operator's existing tab env is not
                                  # steering-controlled) — note it in the dispatch prompt
                                  # if it matters. Missing field = "inherit".

worker_bg_prior_sessions: []   # v7.0.0+. Read-only forensic record of replaced workers,
                               # oldest first. Each entry:
                               #   - session_id: "<short-id>"
                               #     spawned_utc: "<ISO8601>"
                               #     replaced_utc: "<ISO8601>"
                               #     reason: "<context-exhausted | safety-tripped |
                               #              stuck-looping | manual-replace | crashed>"
                               # Appended by /falcon respawn-fresh; never re-claimed.
                               # /falcon retro --branch reads this list for respawn-count
                               # audit categorized by reason. /falcon list-pending applies
                               # a respawn-loop heuristic (N >= 2 + still-active + stale
                               # → flag as STALE (respawn-N)).
                               #
                               # safety-tripped advisory (REQUIRED): if any entry has
                               # reason: safety-tripped, the prior session's log may contain
                               # the triggering content. Do NOT read
                               # `claude logs <session_id>` in a new session for forensics
                               # — the log may reproduce the triggering content and
                               # re-trip the safety filter in the reader's session
                               # (development-standards.md §3.15). The forensic record
                               # (timestamp + reason code)
                               # is sufficient for retro analysis without reading logs.

dispatch_continuation: false   # v7.0.0+. Set to true by /falcon respawn-fresh so the
                               # successor worker's bootstrap detects continuation mode
                               # and executes the three-step recovery sequence
                               # (push unpushed commits → close landed-but-bd-open
                               # beads → reconcile in-progress amendments) before
                               # resuming normal lifecycle. See PROTOCOL.md
                               # `### --bg dispatch mode (v7.0.0)` for the bootstrap
                               # continuation branch and `### /falcon respawn-fresh
                               # <dispatch-id>` for the implementation walkthrough.

file_scope:
  directories:
    - "<dir path>"
  files:
    - "<file path>"
  # No glob patterns supported

required_context:        # v7.2.0+: explicit context-file list copied from each bead's
                         # `## Required Context` section (per .claude/docs/work-item-templates.md).
                         # Steering populates at dispatch time via:
                         #   bd show <id> | awk '/^## Required Context/,/^## /' | grep -oE '\.claude/[a-zA-Z_/-]+\.md'
                         # Union across all bead_ids, deduped, preserve source order.
                         # Worker reads each file BEFORE writing implementation_intent
                         # (intent-confirm step), so the intent reflects context-grounded
                         # understanding rather than blind execution.
                         # Empty list is valid for all-cynefin:clear dispatches (atomic beads
                         # need no preemptive context). Under-hydrated cynefin:complicated/complex
                         # beads should NOT reach this stage — they fail the readiness gate
                         # in work-item-templates.md. If they do (e.g., legacy beads), worker
                         # records ad-hoc reads in unlisted_context_reads[] per bead (below).
  - ".claude/security.md"
  - ".claude/data-model.md § User model"

init_prompt: |
  <multi-line string containing the worker's binding spec:
   lifecycle, bead set (pointer or inline per --inline-beads),
   project standards pointer, DAR protocol, return contract YAML.
   Authored per the init_prompt Content Template below.>

implementation_intent: null   # worker writes a string here at intent-confirm step

out_of_spec_approval_requests: []
# Currently stubbed; populated in a future minor version.
# Proposed shape (v6.6.0+):
#   - request_id: "<id>"
#     ask: "<one-sentence>"
#     file_path: "<file outside scope>"
#     rationale: "<why needed>"
#     raised_utc: "<ISO8601>"
#     response: null      # steering OR autopilot writes: "approved" | "denied" | "<custom>"
#     responded_utc: null
#     response_source: null  # "user-relay" | "autonomous" | "/quartermaster"

implementation_results: null   # worker writes the full YAML report content here

implementation_results_hash: null   # sha256(implementation_results_content.encode('utf-8'))
                                     # written by worker in same atomic write as results.
                                     # Steering verifies hash matches before parsing.
                                     # IMPORTANT: sha256 of the raw string as written —
                                     # NOT sha256 of any normalized form. Byte-exact match required.

amendments: []   # steering appends follow-up instructions here AFTER initial completion;
# worker re-reads file on resume prompt, checks session_status, executes pending amendments.
# Append-only: NEVER overwrite an existing amendment entry.
# Shape (active per v6.2+, naming convention per v6.3, satisfied per v6.5.1,
#        response_source per v6.12.0):
#   - amendment_id: "amend-01"     # sequential, zero-padded; initial dispatch has no amendment_id
#     created_utc: "<ISO8601>"
#     issued_by: "user"            # "user" | "steering-cron"
#     label: null                  # "auto-issued:cron" for autopilot-issued amendments
#     response_source: null        # v6.12.0+: who/what produced the decision to issue this
#                                  # amendment. Values:
#                                  #   "autonomous"  — gate match, no advisor consulted
#                                  #   "/<agent>"    — advisor-delegated (e.g., "/quartermaster")
#                                  #                   when --advisor=<agent> was set on dispatch
#                                  #   "user-relay"  — manually issued by user via paste-block
#                                  #   "steering-cron" — default for autopilot writes
#                                  # /falcon retro counts entries by response_source for the
#                                  # autopilot audit summary.
#     request: "<paragraph from steering>"
#     status: "pending" | "in_progress" | "completed" | "satisfied" | "rejected"
#       # Terminal states (eligible for lock release): completed, satisfied, rejected.
#       # Non-terminal (blocks lock release): pending, in_progress.
#       # satisfied = amendment intent met without action from this branch:
#       #          (i) moot trigger (no longer applies) OR
#       #          (ii) work done elsewhere (user pre-edits, sibling work, parent commit covers).
#       #          Worker verifies + records evidence in worker_response.
#     worker_response: null
#     commits: []
#     worker_completed_utc: null
```

---

## Mode-Selection Decision Tree (v7.0.0)

As of v7.0.0, three dispatch modes coexist. This tree documents the choice path + detection sequence + the worktree-isolation interaction. Consumed at PROTOCOL.md Step 2 (Write Dispatch File + Emit Worker Prompt).

```
START: /falcon work beads <spec> [<flags>]
  │
  ▼
  ┌─ Did user explicitly pass --paste? ────────────────────────────────────┐
  │                                                                        │
  │  YES → effective mode = --paste                                        │
  │        (cross-machine; no shared filesystem; full init_prompt inlined) │
  │        → emit DISPATCH PROMPT paste-block per legacy template          │
  │        → write worker_dispatch_mode: "paste"                           │
  │        → done (skip Mode-Selection Decision Tree remainder)            │
  │                                                                        │
  │  NO  → continue ↓                                                      │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ Did user explicitly pass --via-paste? ────────────────────────────────┐
  │                                                                        │
  │  YES → effective mode = --via-paste                                    │
  │        (same-filesystem; paste-to-tab UX; no agent-view)               │
  │        → emit DISPATCH PROMPT paste-block per legacy template          │
  │        → write worker_dispatch_mode: "via-paste"                       │
  │        → done                                                          │
  │                                                                        │
  │  NO  → continue (defaulting to --bg) ↓                                 │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ Version gate: `claude --version` >= 2.1.139? ─────────────────────────┐
  │                                                                        │
  │  NO  → emit: "--bg requires Claude Code >= 2.1.139 (detected: <ver>)." │
  │             " Auto-downgrading to --via-paste."                        │
  │        → effective mode = --via-paste (auto-downgrade)                 │
  │        → emit DISPATCH PROMPT paste-block                              │
  │        → write worker_dispatch_mode: "via-paste"                       │
  │        → done                                                          │
  │                                                                        │
  │  YES → continue ↓                                                      │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ disableAgentView check (v7.0.1): four-file cascade, first non-null    ┐
  │   wins, in precedence order:                                           │
  │     1. <repo>/.claude/settings.local.json                              │
  │     2. <repo>/.claude/settings.json                                    │
  │     3. ~/.claude/settings.local.json                                   │
  │     4. ~/.claude/settings.json                                         │
  │                                                                        │
  │  first non-null == true →                                              │
  │     emit: "agent-view disabled by <source> settings (<file-path>).     │
  │            Auto-downgrading to --via-paste."                           │
  │     (+ advisory note if worker_model/thinking ≠ inherit — v7.4.0)      │
  │              → effective mode = --via-paste (auto-downgrade)           │
  │              → emit DISPATCH PROMPT paste-block                        │
  │              → write worker_dispatch_mode: "via-paste"                 │
  │              → done                                                    │
  │                                                                        │
  │  all null or false → continue ↓                                        │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ effective mode = --bg ────────────────────────────────────────────────┐
  │   → resolve worktree isolation per the sub-tree below                  │
  │   → compute bootstrap from REFERENCE.md template                       │
  │     (substitutes dispatch_id + repo_path)                              │
  │   → Bash: [MAX_THINKING_TOKENS=<n>] claude --bg [--model <id>]         │
  │           --name "<prefix>-falcon-<id>" "<bootstrap>" [<isol-flag>]    │
  │     (bracketed parts from worker_model/worker_thinking_mode; v7.4.0;   │
  │      inherit = omit — launch identical to pre-7.4.0)                   │
  │   → capture returned short session ID                                  │
  │   → write worker_bg_session_id + worker_dispatch_mode: "bg"            │
  │   → emit one-line confirmation:                                        │
  │     "Dispatch mode: --bg (agent-view v<ver> detected; isolated: <y|n>)"│
  │   → emit observation block (Monitor / Peek / Detail / Logs)            │
  │   → done                                                               │
  └────────────────────────────────────────────────────────────────────────┘

Worktree-isolation sub-tree (--bg mode only):
  │
  ▼
  ┌─ Did user explicitly pass --bg-isolated? ──────────────────────────────┐
  │  YES → worker_bg_isolation: "isolated"                                 │
  │        → append Claude-Code-side isolation flag to claude --bg call    │
  │                                                                        │
  │  NO  → continue ↓                                                      │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ Did user explicitly pass --bg-no-isolation? ──────────────────────────┐
  │  YES → worker_bg_isolation: "none"                                     │
  │        → append Claude-Code-side opt-out flag to claude --bg call      │
  │                                                                        │
  │  NO  → continue ↓                                                      │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ Read .claude/settings.json: worktree.bgIsolation ─────────────────────┐
  │  "isolated" → worker_bg_isolation: null (inherit) + apply isolation    │
  │  "none"     → worker_bg_isolation: null (inherit) + apply opt-out      │
  │  "auto"     → worker_bg_isolation: null (inherit) + defer to CC default│
  │  absent     → worker_bg_isolation: null (inherit) + defer to CC default│
  └────────────────────────────────────────────────────────────────────────┘
```

**Mutually exclusive flag combinations (all refused at the entry-validation step before this tree runs):**

- `--bg` + `--paste` → "cannot coexist; --bg is local-only, --paste assumes cross-machine"
- `--via-paste` + `--paste` → same rationale
- `--bg-isolated` + `--bg-no-isolation` → "isolation is binary; pick one"

**Mode override always wins.** If the user explicitly passes `--via-paste` or `--paste`, the version-gate and `disableAgentView` checks are SKIPPED — the user has chosen the mode explicitly. The auto-downgrade path fires only when `--bg` is the requested mode (either default or explicit) and the environment doesn't support it.

**Detection happens eagerly (BEFORE Step 2 dispatch-file write).** If the detection fails at any step, no `.claude/tmp/falcon-dispatch-<id>.yaml` is written; no lock is registered. The user sees the auto-downgrade message and the dispatch proceeds with `--via-paste` (which DOES write a dispatch file + register a lock).

---

## Session JSON Schema Extension

The existing per-session JSON file at `.claude/tmp/<session-id>.json` gains a `falcon_dispatches[]` array:

```json
{
  "schema_version": 1,
  "session_id": "...",
  "tracking_mode": "leroy",
  "started": "...",
  "branch": "...",
  "transcript": "...",
  "worked_beads": [],
  "compactions": [],
  "falcon_dispatches": [
    {
      "dispatch_id": "abc123",
      "started_utc": "2026-05-21T18:20:00Z",
      "bead_ids": ["example-ckl.5"],
      "file_scope": {
        "directories": ["docs/level-designs/samples/replays/"],
        "files": []
      },
      "status": "in_progress",
      "dispatch_file": ".claude/tmp/falcon-dispatch-abc123.yaml"
    }
  ]
}
```

Falcon writes to this array on dispatch creation (Step 1c) and removes entries on Step 4 auto-release or manual `/falcon release`. Cross-session aggregation reads all `.claude/tmp/*.json` files for the lock check.

If the field doesn't exist on a session JSON file (e.g., a session created before the falcon schema extension), treat as empty `[]`.

---

## falcon-queue.yaml Schema (v7.6.0)

Cross-session FIFO of pending dispatches deferred by `/falcon work beads ... --queue` on a Step 1c lock conflict. Lives at `.claude/tmp/falcon-queue.yaml`. Cross-session by design: it complements the cross-session lock registry above — a session-scoped queue would orphan entries when the enqueuing session ends, and the session that releases a lock is often not the session that enqueued.

```yaml
# .claude/tmp/falcon-queue.yaml — a flat YAML list, eldest entry first
- queue_id: "4f9c2a"                  # fresh 6-hex id, distinct from dispatch ids
  spec: "example-qrs.2,example-qrs.3" # original spec string, verbatim
  flags: "--sequential --autopilot"   # invocation flags, verbatim, minus --queue itself
  enqueued_utc: "2026-05-22T09:14:00Z"
  enqueuing_session: "sess-7f"
```

Semantics:

- **Absent file = empty queue.** Readers (the Step 4 / `/falcon release` queue scan, `/falcon list-pending`) treat a missing file as no pending entries; the enqueue path creates it on first use.
- **Atomic read-modify-write.** Every mutation (enqueue, dequeue, manual `/falcon dequeue`) reads the whole file, modifies in memory, and writes back atomically (write temp + rename) — the same discipline as dispatch-file writes. Multiple steering sessions may race on a release; last-write-wins on a flat list is acceptable at this coordination scale, and the post-dequeue Step 1c re-check catches any double-dequeue scope conflict.
- **Only spec + flags are trusted at dequeue.** Bead bodies, derived file scopes, and active locks are re-resolved fresh by the FULL pre-dispatch re-run (PROTOCOL.md Step 4 "Queue scan on release"). `enqueued_utc` orders the FIFO; `enqueuing_session` is an audit field, not a coordination mechanism.
- **No auto-expiry.** Entries older than 24h are flagged STALE by `/falcon list-pending`; removal is manual (`/falcon dequeue <queue-id>`) or via successful dequeue.

---

## init_prompt Content Template (default: thin / pointer-style)

The dispatch file's `init_prompt` field embeds this content. As of v6.7.0, the template is intentionally thin (~60-90 lines per dispatch) and points the worker at the canonical skill files for lifecycle, return contract, and labeled-copy convention. Only per-dispatch content lives inline (branch, bead set, steering notes, optional pre-intent grep). The pointer-style avoids ~150 lines of duplication per dispatch and eliminates the drift risk where old dispatch files carry stale spec.

Fill in `{{ ... }}` from Step 1 resolution.

```
You are a falcon worker for dispatch {{ dispatch_id }} in the repo at {{ repo_path }}.

You own the full lifecycle of the bead set below: claim, implement, test, commit, push, close, flush, return-report.

## Your binding spec — read these BEFORE acting

If you are running in Claude Code with the falcon skill loaded, these files are already in your context — no extra Read calls needed. Otherwise, Read them once before the branch-verify step.

1. **`.claude/skills/falcon/PROTOCOL.md` "## Worker Lifecycle (inside the dispatch)"** — the 13-step lifecycle you execute, including intent-confirm pause, DAR protocol, close-gate discipline, and amendments cycle. For `--sequential` dispatches, also read "### Sequential dispatch lifecycle override (v6.4.0)".
2. **`.claude/skills/falcon/REFERENCE.md` "## Worker Return Contract"** — the YAML schema you write to `implementation_results` at completion.
3. **`.claude/skills/falcon/REFERENCE.md` "## Copy-Paste Emission Convention"** — the labeled-copy fence convention for INTENT, COMPLETION, AMENDMENT COMPLETION, etc.

Project standards in `.claude/rules/*.md` and any root `CLAUDE.md` are binding. Auto-loaded by Claude Code; Read once at session start in any other harness. `.claude/standards-history.md` is NOT auto-loaded — fetch on demand for the "why" behind a specific rule.

If a bead description conflicts with a project standard, the standard wins — flag the conflict in your DAR.

## Per-dispatch context

Dispatch ID: {{ dispatch_id }}
Dispatch file: {{ dispatch_file_path }}
Branch: {{ branch_name }}

### Branch verify (first action)

    git fetch origin
    git checkout {{ branch_name }}
    git rev-parse --abbrev-ref HEAD

The final command MUST return {{ branch_name }}. If `git checkout` fails with "did not match any file(s) known to git", the branch is not on origin yet — STOP and return a partial report with blocker: "branch {{ branch_name }} not found on origin after fetch."

If `git checkout` fails with "already checked out at ..." — EXPECTED under `--bg` worktree isolation, where steering holds {{ branch_name }} in the main checkout — do NOT stop and do NOT invent a branch. Verify by ancestry instead: `git merge-base --is-ancestor origin/{{ branch_name }} HEAD` must succeed (your worktree branch is based at the dispatch branch tip; a FRESH worktree created from a different base may first be re-based with `git reset --hard origin/{{ branch_name }}`). Record the actual branch name you are on for your report. At push time, land commits directly on the branch ref: `git pull --rebase origin {{ branch_name }} && git push origin HEAD:{{ branch_name }}`. See PROTOCOL.md Worker Lifecycle Step 1 (worktree-mode branch verify) and Step 9 (worktree-mode push).

Do NOT `git checkout -b`, do NOT switch branches, do NOT invent a branch name.

### Bead set

**Default (pointer-style):**

| ID | Title |
|----|-------|
| {{ bead_id_1 }} | {{ title_1 }} |
| {{ bead_id_2 }} | {{ title_2 }} |
| ... | ... |

For each bead above: run `bd show <id>` to load the full body. The bead body is the binding spec — read it before claiming.

For each bead not in `triage:ready`, the steering session has marked one of:
- `dispatch_directive: refine_then_claim` — bring it to ready per Lifecycle Step 2, then claim
- `dispatch_directive: claim_with_warning` — proceed as-is; gaps are acknowledged

(With `--inline-beads`, full bead bodies are embedded above instead of this pointer table. With `--paste`, this entire init_prompt is self-contained — see "init_prompt Content Template (`--paste` mode)" in REFERENCE.md.)

### Steering session notes (per-dispatch — bind these alongside the bead body)

{{ steering_session_notes_block }}

### Pre-intent grep verification (per-dispatch, when applicable)

{{ optional_grep_block — present for migration/rename beads per PROTOCOL.md Step 1b; absent otherwise }}

### Project standards especially load-bearing for this bead

{{ per-dispatch list of relevant rule-file sections, e.g. "§3.17, §3.18, §3.9, §3.10" }}

## Reminders (pointers to your binding spec)

- **Intent confirmation:** PROTOCOL.md Worker Lifecycle Step 3. Write to `implementation_intent` in this dispatch file; emit the INTENT block using `dispatch {{ dispatch_id }}` per REFERENCE.md "## Copy-Paste Emission Convention". Wait for `proceed {{ dispatch_id }}` ack before claiming. Skip if `skip_intent: true` directive present.
- **Decisions / DAR:** PROTOCOL.md "### DAR protocol (inside the dispatch)". Low-stakes: proceed, document. High-stakes: STOP, partial report.
- **Verification close gate:** the bead's Testing Strategy + project verification-gate rules. Observable evidence required BEFORE `bd close`, not after. If the bead names out-of-band or encapsulator verification, set `verification.out_of_band_required: true` and leave bead `in_progress`.
- **Return contract:** REFERENCE.md "## Worker Return Contract". Write to `implementation_results` + compute `sha256(implementation_results_content)` into `implementation_results_hash` in the same atomic write. Do NOT paste the YAML inline in chat. Emit the COMPLETION block per the labeled-copy convention.
- **Amendments cycle:** PROTOCOL.md Worker Lifecycle Step 13. Check `session_status` on each resume prompt; execute pending amendments per the spec.
- **Wake-phrase recognition (v7.0.1, fdev-lbq.24):** if a user message in this session matches the case-insensitive regex `^(falcon poll|/falcon-poll)\s*$`, treat it as a wake nudge: (1) Read the dispatch file at the path your bootstrap recorded; (2) process any `amendments[]` entries whose `handled_utc` is null per the Amendments Workflow; (3) emit a single inline `STATE: WAKE-PHRASE-PROCESSED dispatch={{ dispatch_id }} amendments_handled=<n>` line; (4) resume the prior context (waiting for ack, executing, etc.) — do NOT exit the session or claim a new bead. This phrase exists for `--bg` operators to nudge an idle/supervisor-stopped worker back into the autopilot loop via `claude agents` peek-and-reply without having to type a long instruction; in `--via-paste` mode it works identically when typed into the worker tab.

### Worker self-poll at pause points (--bg mode only, v7.1.1)

In `--bg` mode (when `worker_dispatch_mode == "bg"` on this dispatch file), arm a self-poll `CronCreate` at each pause-for-steering point so steering's autopilot ack/amendment writes are observed without an external poke. Two armable points: intent emission (Step 3) and DAR pause-for-response. For the literal `CronCreate` substitution blocks + the role-split contract (cron prompt = wake nudge; worker = `CronDelete(captured_id)` on wake using the ID captured from `CronCreate`'s return value at arm time), see CRONS.md `## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)`. `durable: false` is mandatory. Arm ONLY at the two pause points above — NEVER as an always-on background poller. Do NOT arm in `--via-paste` / `--paste` modes (operator paste / worker-cron handles those modes). See PROTOCOL.md `### Worker self-poll at pause points (v7.1.1)` for full coordination rationale.
```

(End of default init_prompt content template.)

---

## Worker Self-Poll Cron Templates (--bg mode only, v7.1.1)

**Moved in v7.2.0 to [`CRONS.md`](./CRONS.md#worker-self-poll-cron-templates---bg-mode-only-v711).** The two literal `CronCreate` substitution blocks (intent self-poll at `*/2 * * * *`, DAR self-poll at `*/3 * * * *`), the role-split contract (cron prompt = wake nudge; worker = `CronDelete(captured_id)` on wake), and the predicate-simplicity rationale all live in `CRONS.md` now.
---

## Bootstrap Prompt Template (v7.0.0)

The CLI argument passed to `claude --bg --name "<prefix>-falcon-<dispatch-id>" "<bootstrap>"` at PROTOCOL.md Step 2 in `--bg` mode (plus the conditional v7.4.0 `--model` / `MAX_THINKING_TOKENS` injection per Wiring item 2 — neither changes the bootstrap text itself). Intentionally SHORT (~5 lines) — the full multi-line dispatch prompt content stays in the dispatch file's `init_prompt` field (where it already lives for all modes), eliminating shell-quoting concerns for multi-line content with backticks/quotes/etc. The bootstrap is a POINTER, not the spec itself.

**Substitution variables:** `{{ dispatch_id }}` (literal 6hex ID) and `{{ repo_path }}` (absolute path to the main checkout). Substituted by steering at dispatch invocation time. No other variables; no environment-conditional branches.

**Three things the bootstrap MUST include (REQUIRED):**

1. The literal `dispatch_id` — matches the worker's verify-on-load check (mitigates the residual concern that steering code logic could pass a wrong ID; documented in v7.0.0 changelog as the only failure shape `--bg` doesn't structurally eliminate vs the prior wrong-paste failure mode)
2. The absolute `repo_path` — workers may run in a Claude Code worktree (under `<repo_path>/.claude/worktrees/<id>/`) where relative `.claude/tmp/` paths are stale or absent; the worker resolves dispatch-file paths via `<repo_path>/.claude/tmp/...`
3. An instruction to VERIFY the loaded dispatch file's `dispatch_id` matches the bootstrap-provided ID before any state change

### Literal template (substitution at dispatch time)

```
You are a falcon worker for dispatch {{ dispatch_id }}. The repo is at {{ repo_path }}.
cat {{ repo_path }}/.claude/tmp/falcon-dispatch-{{ dispatch_id }}.yaml to load the dispatch file.
Follow the init_prompt section as your binding spec. Verify the dispatch_id field in the
loaded file matches {{ dispatch_id }} before any state change.
If dispatch_continuation: true on the loaded file, execute the three-step recovery
sequence per PROTOCOL.md `### --bg dispatch mode (v7.0.0)` continuation branch before
normal lifecycle.
```

### Example (substituted)

```
You are a falcon worker for dispatch abc123. The repo is at /path/to/repo.
cat /path/to/repo/.claude/tmp/falcon-dispatch-abc123.yaml to load the dispatch file.
Follow the init_prompt section as your binding spec. Verify the dispatch_id field in the
loaded file matches abc123 before any state change.
If dispatch_continuation: true on the loaded file, execute the three-step recovery
sequence per PROTOCOL.md `### --bg dispatch mode (v7.0.0)` continuation branch before
normal lifecycle.
```

### Why `repo_path`-anchored absolute paths

When the worker runs in an isolated Claude Code worktree (under `<repo_path>/.claude/worktrees/<id>/`), the worktree's working directory is the worktree branch — which does NOT contain `.claude/tmp/` (the directory is ephemeral, lives in the main checkout, never committed). A relative `cat .claude/tmp/falcon-dispatch-<id>.yaml` from the worktree's cwd would fail. Anchoring on `repo_path` (the main checkout's absolute path) makes the path resolve correctly regardless of which directory the worker is in.

Same rationale applies to the worker's subsequent reads (project rules files, dispatch file updates, etc.) — when in `--bg` mode with worktree isolation, the worker should resolve all `.claude/`-prefixed paths via `<repo_path>/.claude/...` rather than relative `.claude/...`. The bootstrap doesn't enforce this beyond the dispatch-file path itself; the init_prompt + Worker Lifecycle Step 1 carry the broader convention.

### Continuation-mode branch (when `dispatch_continuation: true`)

The bootstrap template is the same for initial dispatch and respawn-fresh successor dispatch — both substitute the same `{{ dispatch_id }}` + `{{ repo_path }}`. The difference is the dispatch file's `dispatch_continuation` field, which the successor's bootstrap detects on load and uses to route into the three-step recovery sequence (per PROTOCOL.md `### --bg dispatch mode (v7.0.0)` continuation branch) BEFORE entering normal Worker Lifecycle. The bootstrap line about continuation makes the branch explicit — the worker reads "if dispatch_continuation: true ..." and executes the recovery before any other action.

### Thinking-mode delivery — why not a bootstrap keyword (v7.4.0)

`worker_thinking_mode` is delivered via the `MAX_THINKING_TOKENS` env var on the `claude --bg` invocation (PROTOCOL.md `### --bg dispatch mode`, Wiring item 2), NOT by prepending a thinking keyword (`ultrathink`, "think hard") to this bootstrap. Rationale:

1. **Scope.** A prompt keyword influences the turn that carries it; the env var applies to every turn of the worker's session. Workers run dozens of turns — per-turn keyword delivery would silently decay after the first response.
2. **Determinism.** Numeric budgets (`none` → 0, `think` → 10000, `ultrathink` → 31999) are explicit; keyword→budget mapping is a heuristic that can shift between Claude Code versions.
3. **Template stability.** The bootstrap stays a pure pointer (~5 lines, three REQUIRED elements). No conditional branches keyed on dispatch fields — the same template serves initial dispatch and respawn-fresh continuation unchanged.

The bootstrap template above is therefore IDENTICAL whether or not a thinking mode is set. Mode applicability caveat: env delivery only works where steering owns the process spawn (`--bg`); `--via-paste`/`--paste` dispatches record `worker_thinking_mode` as advisory (see the schema field note).

### No `bootstrap_prompt` schema field

The bootstrap template lives in REFERENCE.md (this section), substituted at dispatch time. It does NOT live in the dispatch file's YAML schema as a `bootstrap_prompt` field. Rationale: the bootstrap is a CLI argument shape that depends on the worker spawn mechanism (`claude --bg`); the dispatch file is the worker's binding spec (the `init_prompt` field). Conflating them would couple the dispatch file format to a specific worker spawn pathway and complicate the `--via-paste` / `--paste` modes that don't use a bootstrap at all.

(End of Bootstrap Prompt Template.)

---

## init_prompt Content Template (`--paste` mode: fully inlined)

Paste-mode workers cannot access the filesystem to Read the falcon skill files. The init_prompt MUST be self-contained in this mode. To generate the paste-mode init_prompt, the steering session inlines the three referenced sections directly:

1. The default template above (pointer-style)
2. Plus the verbatim content of `PROTOCOL.md` "## Worker Lifecycle (inside the dispatch)" (including "### Sequential dispatch lifecycle override" and "### DAR protocol")
3. Plus the verbatim content of `REFERENCE.md` "## Worker Return Contract" (the full YAML schema)
4. Plus the verbatim content of `REFERENCE.md` "## Copy-Paste Emission Convention" (the convention + labels table + examples)

This is the only mode where the init_prompt is multi-hundred lines. Use sparingly — paste-mode is a cross-network / cross-machine fallback, not a default.

---

## Worker Return Contract

The worker writes this YAML structure to `implementation_results` in the dispatch file at completion. Compute `sha256(implementation_results_content)` (raw string as written, byte-exact) and write to `implementation_results_hash` in the same atomic write. Do NOT paste the full YAML inline in chat.

```yaml
falcon_report:
  schema_version: 2
  spec: "{{ original spec }}"
  branch: "{{ branch_name }}"
  started: "<UTC ISO8601>"
  completed: "<UTC ISO8601>"
  beads:
    - id: "<id>"
      title: "<title>"
      outcome: "closed | in_progress | blocked | deferred"
      outcome_reason: "<one sentence>"
      commits: ["<sha>", "<sha>"]
      files_changed: ["path/to/file", ...]
      verification:
        method: "<command(s) run + what they exercised>"
        evidence: "<observable outcome: HTTP status, container log line, test pass count, etc.>"
        out_of_band_required: false   # true if bead spec named a human or external tool as verifier
      effort_actual:
        plan_turns: N
        impl_turns: N
        test_turns: N
        total_turns: N
        notes: "<phase variance, if any>"
      ac_status: "all_passed | partial | failed"
      ac_failures: []   # list AC items not satisfied if partial/failed
      unlisted_context_reads:   # v7.2.0+: .claude/*.md files the worker had to read DURING
                                # execution that were NOT named in the bead's `## Required
                                # Context` section (and therefore not in the dispatch's
                                # required_context[]). Each entry is signal that the bead
                                # was under-hydrated — the bead author missed naming a
                                # context dependency the work actually needed. /wrapup
                                # Task 4 absorbs each as a kind:doc_gap entry against the
                                # originating bead so future similar beads get the
                                # Required Context section tightened up.
                                # Empty list is the expected normal — well-hydrated beads
                                # need no ad-hoc reads.
        - path: ".claude/styleguide.md"
          reason: "<one sentence — why this file was needed mid-execution>"

  discovered_beads:
    - id: "<id-or-pending>"
      title: "<title>"
      type: "bug | feature | chore | decision"
      discovered_from: "<originating bead id>"
      created: true   # true if bd create ran, false if just noted
      rationale: "<why this matters>"

  standards_firings:
    - rule: "<rule reference from project standards>"
      context: "<what triggered>"
      action_taken: "<fixed in commit | filed follow-up | other>"

  decisions_for_human:   # DAR entries
    - decision: "<one sentence framing the choice>"
      bead_context: "<bead id this arose from>"
      alternatives:
        - label: "<alternative name>"
          tradeoff: "<one-line>"
      recommendation: "<which alternative + one-sentence why>"
      stakes: "low | high"
      action_taken: "proceeded with recommendation | stopped pending arbitration"
    # Escalation audit entries (v7.5.0): when the dispatch file's escalations[] is
    # non-empty, the reporting worker copies each escalation into this list so the
    # /wrapup + retro surfaces see model-tier decisions alongside DARs. Shape:
    #   - decision: "Escalated dispatch model <from_model> -> <to_model> at intent gate"
    #     bead_context: "<dispatch-id> (pre-claim; applies to the whole bead set)"
    #     recommendation: "<rationale from the escalations[] entry>"
    #     stakes: "low"
    #     action_taken: "escalated by <operator | auto-ack-cron> (<n>/<escalation_budget>)"

  enhancements:
    - kind: "doc_gap | workflow_friction | tooling_pain | standards_candidate"
      summary: "<one sentence>"
      suggested_fix: "<one sentence>"

  blockers_for_steering_session:
    - "<one sentence per blocker>"

  recommended_next_steps:
    - "<priority-ordered, ID-anchored — feeds handoff.yaml next_steps>"

  epic_progress:
    - epic: "<epic-id>"
      delta: "X% -> Y%"
      remaining_children: ["<id>", ...]

  changelog_seed:
    focus: ["feature", "infrastructure", "documentation", ...]
    one_line_summary: "<one line for changelog summary field>"
    area_changes:
      backend: ["added: ...", "fixed: ..."]
      frontend: []
      infra: []
      docs: []

  unresolved_questions: []
  partial_report: false   # true if stopped mid-batch; explains why some beads have outcome=in_progress
```

**Completion summary phrasing convention:** start with `"Work stream completed at <UTC ISO8601>."` (or `"Work stream partial at <UTC ISO8601>."` for `partial_report: true`). The timestamp is the worker's wall-clock emission time generated at emit-time. Avoid bead-type-specific phrasings like `"Spike complete"` in the opening.

Example COMPLETION preamble:

```
## COMPLETION — dispatch abc123 at 2026-05-22T14:32:18Z

═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
~~~
Work stream completed at 2026-05-22T14:32:18Z. Map produced at scripts/qa/wave_pack_similarity_map.json
(101 entries, top-3 cross-match candidates per entry, threshold cos ≥ 0.6).
All 4 in-bead questions ratified per inline recommendations.
Re-read .claude/tmp/falcon-dispatch-abc123.yaml.
~~~
═══ END COPY ═══
```

(End of Worker Return Contract.)

---

## Dispatch Prompt Template

The steering session emits a SHORT prompt (10-20 lines) for the user to paste into the worker session. The worker reads the dispatch file as its first action.

**Advisory model/thinking line (v7.4.0, conditional):** when `worker_dispatch_mode != "bg"` AND either `worker_model` or `worker_thinking_mode` is non-`inherit`, append this line after the `Dispatch ID:` line inside the fence — it is the only delivery surface those fields have outside `--bg`:

    Requested worker model/thinking: {{ worker_model }} / {{ worker_thinking_mode }}
    (ADVISORY — not enforced in this mode. To honor: relaunch this tab as
    `MAX_THINKING_TOKENS=<budget> claude --model <model-id>`, or accept the
    tab's current model and prepend a thinking keyword per-message, which is
    turn-scoped.)

Omit the line entirely when both fields are `inherit` (the overwhelmingly common case — zero added prompt weight).

    ## DISPATCH PROMPT — dispatch {{ dispatch_id }} at {{ created_utc }}

    ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
    ~~~
    You are working autonomously in the repo at {{ repo_path }}.
    This is a falcon dispatch.

    Dispatch file: {{ dispatch_file_path }}
    Branch: {{ branch_name }}
    Dispatch ID: {{ dispatch_id }}

    Steps:
    1. **Identify your session as worker for this dispatch.** Run the
       `/rename falcon-{{ dispatch_id }}` slash command as your first action
       so the session shows up correctly in `claude agents` (when available)
       and on the prompt bar. This is the canonical Claude Code mechanism
       (v7.0.0+) — environment-agnostic, can't be overridden by shell-prompt
       redraw hooks, and always available because the worker IS a Claude Code
       session. (The prior tmux/printf/IDE-escape advice was unreliable across
       most real-world setups — see P5.1 in the falcon v7.0.0 changelog for
       the failure-mode catalog.)
    2. `cat {{ dispatch_file_path }}` to load the dispatch.
    3. Read the `init_prompt` section — it contains the full lifecycle,
       bead set, project standards pointer, and return contract.
    4. Execute the lifecycle in init_prompt EXACTLY as written. Default
       intent-confirm pre-flight applies (unless skip_intent: true in the
       dispatch file).
    5. Write `implementation_intent` to the dispatch file when you reach
       the intent-confirm step. Then STOP and emit BOTH the file-write
       confirmation AND the intent paragraph wrapped in the v6.5.3
       labeled-copy convention, with the v6.12.1 dispatch-identity
       header prepended INSIDE the fence:

           ## INTENT — dispatch {{ dispatch_id }} at <UTC ISO8601>

           ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
           ~~~
           Working dispatch {{ dispatch_id }} on branch {{ branch_name }}
           Beads: [<bead_id_1>: "<title_1>", <bead_id_2>: "<title_2>", ...]

           <intent paragraph(s) as written to the dispatch file>

           Intent above written to {{ dispatch_file_path }}.
           Trigger 'proceed {{ dispatch_id }}' when ready, or paste revisions.
           ~~~
           ═══ END COPY ═══

       The dispatch-identity header (Working dispatch + Beads lines) is
       mandatory as of v6.12.1 — it's the last visual checkpoint where
       a user can spot a wrong-dispatch-paste before authorizing the
       worker to proceed. See PROTOCOL.md "## Worker Lifecycle" Step 3
       for the rationale and example-r3q9 for the broader Safeguard
       A (worker_session_id field + claim mechanic) tracked separately.

    6. Wait for the user to confirm 'proceed {{ dispatch_id }}' (or
       revisions) before continuing to claim/implement.
    7. On completion, write `implementation_results` per the return contract
       in init_prompt, compute sha256(implementation_results_content) and
       write to `implementation_results_hash` in the same atomic write, then emit:

           ## COMPLETION — dispatch {{ dispatch_id }} at <UTC ISO8601>

           ═══ COPY EVERYTHING BETWEEN THE FENCES BELOW ═══
           ~~~
           Work stream completed at <UTC ISO8601>. Re-read {{ dispatch_file_path }}.
           <optional one-paragraph preamble summarizing what's in the report>
           ~~~
           ═══ END COPY ═══

       Do NOT paste the full YAML report inline.
       Do NOT write results_complete: true — the hash IS the completion signal.

    8. For out-of-spec asks: use the existing DAR high-stakes mechanism —
       emit a partial report with the ask details, STOP, await manual resume.

    9. After initial completion, check `session_status` in the dispatch file
       on each resume prompt:
       - `amendments_pending` → find pending amendments in `amendments[]`,
         execute each (no intent-confirm; amendments are directive), write
         worker_response + commits + status: completed back, emit the
         amendment-completion preamble wrapped in v6.5.3, wait for next prompt.
       - `complete` → steering has released the lock; your work is done.

    File-contract: this dispatch is locked to the file_scope declared in the
    dispatch file. Do NOT touch files outside the declared directories/files
    without raising a high-stakes DAR.

    Commit + push protocol: `git pull --rebase origin {{ branch_name }}` before
    each push. Workers do NOT open PRs (steering owns PR opening).
    ~~~
    ═══ END COPY ═══

(End of dispatch prompt template.)

---

## Stash File Format

Stash path is branch-keyed: `.claude/tmp/falcon-reports-<sanitized-branch>.yaml`

Derived via `git rev-parse --abbrev-ref HEAD | tr '/' '-'`. The `tr '/' '-'` is load-bearing — feature-branch names like `feature/work-20260521-foo` would otherwise create a directory hierarchy.

The stash is **append-only across N dispatches** on the same branch. `/wrapup` consumes the entire stash (not just the most recent report). Merging strategy: union of `beads[]`, `discovered_beads[]`, `standards_firings[]`, `decisions_for_human[]`, etc. For `epic_progress`, last delta wins per epic across reports.

---

## falcon-autopilot.md Template

**Moved in v7.2.0 to [`AUTOPILOT-RULES.md`](./AUTOPILOT-RULES.md#falcon-autopilotmd-template).** The 8-section rules-file template (`SAFE_TO_ACK_INTENT` predicate + `SAFE_TO_AMEND` whitelist + denylist + cognitive audit hints + advisor delegation policy + amendment budget defaults + worker model defaults + intent-gate escalation ladder/budget), the 3 profile definitions (`conservative`, `standard`, `aggressive`), and the adopter customization guidance all live in `AUTOPILOT-RULES.md` now.

---

## Autopilot Cron Prompt Templates

**Moved in v7.2.0 to [`CRONS.md`](./CRONS.md#autopilot-cron-prompt-templates).** The 5 cron prompt templates (`--watch`, `--auto-ack`, `--auto-amend`, `--worker-cron`, `--release-on-merge`) with full Step 0-N specs + v7.1.2 condensed `CronCreate` prompts + the shared cron infrastructure subsections (`### Cron Telemetry Instrumentation`, `### Cron Dispatch-Mode Conventions`, `### claude agents CLI surface`) all live in `CRONS.md` now.
