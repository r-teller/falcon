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

cron_telemetry: {}   # v7.0.1 SPEC (impl deferred to v7.1, fdev-lbq.6).
                     # Each cron template will increment its own counters here on fire-entry,
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
                     # whether the v7.0.1 adaptive-cadence guards (fdev-lbq.2/.3) are landing
                     # on signal-density numbers > 30% as expected. Spec landed in v7.0.1;
                     # implementation requires wiring the counters into every cron template +
                     # extending /falcon retro emitter — both deferred to v7.1.

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
  ┌─ disableAgentView check: read .claude/settings.json (project wins) ────┐
  │   then ~/.claude/settings.json (user-level fallback)                    │
  │                                                                        │
  │  EITHER true → emit: "agent-view disabled by <project|user>            │
  │                       settings.json. Auto-downgrading to --via-paste." │
  │              → effective mode = --via-paste (auto-downgrade)           │
  │              → emit DISPATCH PROMPT paste-block                        │
  │              → write worker_dispatch_mode: "via-paste"                 │
  │              → done                                                    │
  │                                                                        │
  │  BOTH false (or absent) → continue ↓                                   │
  └────────────────────────────────────────────────────────────────────────┘
  │
  ▼
  ┌─ effective mode = --bg ────────────────────────────────────────────────┐
  │   → resolve worktree isolation per the sub-tree below                  │
  │   → compute bootstrap from REFERENCE.md template                       │
  │     (substitutes dispatch_id + repo_path)                              │
  │   → Bash: claude --bg --name "falcon-<id>" "<bootstrap>" [<isol-flag>] │
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
```

(End of default init_prompt content template.)

---

## Bootstrap Prompt Template (v7.0.0)

The CLI argument passed to `claude --bg --name "falcon-<dispatch-id>" "<bootstrap>"` at PROTOCOL.md Step 2 in `--bg` mode. Intentionally SHORT (~5 lines) — the full multi-line dispatch prompt content stays in the dispatch file's `init_prompt` field (where it already lives for all modes), eliminating shell-quoting concerns for multi-line content with backticks/quotes/etc. The bootstrap is a POINTER, not the spec itself.

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

Written to `.claude/rules/falcon-autopilot.md` by `/falcon create-rules`. Universal sections are fixed; project-specific sections contain placeholders + auto-seeded examples drawn from the project's `.claude/rules/*.md` files.

```markdown
# Falcon Autopilot Rules ({{ project_name }})

> Consumed by falcon autopilot flags: `--auto-ack`, `--auto-amend`,
> `--advisor`, `--amendment-budget`, and the `--autopilot` bundle.
> See `.claude/skills/falcon/COMMANDS.md` for the consumer flag specs.
>
> **Status:** the autopilot consumer flags are currently `⊘` (proposed) in
> falcon v{{ falcon_version }}. This file is a forward-looking spec; the gates
> below are inert until the consumer lands. Iterate on the gates freely now
> so they're production-ready when the autopilot rollout happens.
>
> **Editing convention:** lines marked `# UNIVERSAL — do not edit` come
> from falcon's defaults. Project-specific gates are added below each
> universal section, marked `# PROJECT —`. Uncomment a gate to activate it;
> leave commented to disable.

---

## 1. SAFE_TO_ACK_INTENT predicate

When the worker emits an intent paragraph, autopilot evaluates these gates.
If ALL pass: auto-ack (writes `intent_acknowledged_utc`, emits `proceed
<dispatch-id>` block). If ANY fail: defer to user.

```yaml
safe_to_ack_intent:
  # UNIVERSAL — do not edit
  gates:
    - no_new_file_scope:
        description: |
          Intent paragraph does not propose touching files outside the
          dispatch's declared file_scope.
        check: |
          Regex intent for absolute paths and known project-root prefixes
          (e.g., docs/, score-tracker/, patches/). Cross-check matches against
          dispatch.file_scope.directories + dispatch.file_scope.files. Any
          match outside scope fails this gate.

    - no_cross_dispatch_conditional:
        description: |
          Intent does not contain phrases implying the bead depends on
          another in-flight dispatch's outcome.
        check: |
          Search intent for: "after X bead closes", "depending on", "if X
          succeeds", "waiting on", "blocked-by" + bead IDs. Any match fails
          this gate.

    - intent_matches_changes_needed:
        description: |
          Intent's "core deliverables" overlap with the bead body's Changes
          Needed file list (substring or keyword match).
        check: |
          Extract file paths + key nouns from bead's Changes Needed section.
          Extract same from intent paragraph. Overlap must be >= 50% of
          Changes Needed items by token count.

    - no_open_dar_arbitration:
        description: |
          No prior dispatch on this branch has an unresolved DAR with
          action_taken: "stopped pending arbitration".
        check: |
          Parse .claude/tmp/falcon-reports-<sanitized-branch>.yaml. Any
          decisions_for_human[] entry with stakes: high and unrecorded
          resolution fails this gate.

  # PROJECT — uncomment to activate
  # project_gates:
  #   - example_project_gate:
  #       description: |
  #         <Replace with a project-specific intent constraint. Example:
  #          intent must not propose extending an externally-versioned
  #          manifest without a corresponding version bump.>
  #       check: |
  #         <Describe how to detect the constraint from the worker's
  #          intent paragraph. Any match fails this gate; defer to human.>
```

---

## 2. SAFE_TO_AMEND whitelist

Autopilot may auto-issue amendments for these categories. Whitelist is
restrictive — anything not listed defers to the user.

```yaml
safe_to_amend_whitelist:
  # UNIVERSAL — do not edit
  - rephrase_existing_test
  - missing_regression_check
  - missing_bd_export
  - missing_wave_pack_pin

  # PROJECT — uncomment to activate (seeded from project's rule files)
  # - missing_wave_pack_version_pin_bump:
  #     trigger: |
  #       Commit touches docs/findings/*.yaml but no score-tracker/waves/*.yaml
  #       in the same commit, OR pin in wave yaml does not match new hash.
  #     rule_ref: development-standards.md §3.17
  #     amendment_text: |
  #       Recompute wave_pack_version (replay-validator side + scorer side),
  #       update every score-tracker/waves/*.yaml pin to the new hash,
  #       commit in same change. Cite both hashes in the close-out message.
  #
  # - missing_bd_export_after_batch:
  #     trigger: |
  #       3+ bd writes (label, comment, status) without a final
  #       bd export -o .beads/issues.jsonl invocation.
  #     rule_ref: workflow-execution.md "Persist work-tracking state with the commit"
  #     amendment_text: |
  #       Run `bd export -o .beads/issues.jsonl` to flush canonical jsonl.
  #       Stage the file in the commit.
  #
  # - missing_closes_footer:
  #     trigger: |
  #       bd close <id> was called in the dispatch BUT the commit message
  #       does not include "Closes: <id>".
  #     rule_ref: workflow-execution.md "Commit Message Style"
  #     amendment_text: |
  #       Amend the commit (or add a new commit if the bead is closed) with
  #       "Closes: <id>" in the message footer.
  #
  # - add_sha_header_to_verify_artifact:
  #     trigger: |
  #       File written under verify/ does not start with a `# captured_at_sha`
  #       header line.
  #     rule_ref: project convention for verification artifacts
  #     amendment_text: |
  #       Prepend git SHA + ISO8601 timestamp header to the artifact file
  #       so a future audit can match the artifact to a specific commit.
  #
  # - stable_identifier_assertion:
  #     trigger: |
  #       New or modified route smell-check test uses substring assertion
  #       like `assert "X" in r.text` on body prose.
  #     rule_ref: rules/standards.md candidate "Route smell-check tests assert on stable identifiers"
  #     amendment_text: |
  #       Replace substring assertion with stable-identifier check
  #       (id="...", data-test="...", or CSS class on a structural element).
```

---

## 3. SAFE_TO_AMEND denylist

Autopilot NEVER auto-issues amendments in these categories. Surface to user.

```yaml
safe_to_amend_denylist:
  # UNIVERSAL — do not edit
  - new_ac_item
  - new_file_outside_scope
  - new_endpoint
  - architectural_change

  # PROJECT — uncomment to activate (seeded from project's rule files)
  # - wave_pack_yaml_mutation:
  #     description: |
  #       Any amendment that proposes mutating docs/findings/*.yaml mid-flight.
  #     reason: |
  #       Wave-pack is contract-bearing (§3.18); mid-flight changes risk
  #       cross-entry reference drift. Wave-pack mutations require dedicated
  #       beads, not amendments.
  #
  # - paired_bead_separation:
  #     description: |
  #       Any amendment that proposes closing only one half of a clj/7hq pair.
  #     reason: |
  #       Paired-claim rule (workflow-execution.md) requires both halves
  #       close in the same commit. Splitting violates §3.22 interop contract.
  #
  # - bypass_manual_close_gate:
  #     description: |
  #       Any amendment that proposes closing a bead based on unit-test-pass
  #       alone when the bead's Testing Strategy names manual verification.
  #     reason: |
  #       §3.10 close-gate is non-negotiable; bypassing it forfeits the
  #       regression-detection guarantee.
  #
  # - wave_yaml_without_recompute:
  #     description: |
  #       Any amendment that proposes editing score-tracker/waves/*.yaml
  #       without an accompanying wave_pack_version recomputation.
  #     reason: |
  #       §3.9 boundary violation; the two services will diverge.
  #
  # - rules_or_architecture_md_rewrite:
  #     description: |
  #       Any amendment that proposes modifying .claude/rules/*.md or
  #       .claude/architecture.md.
  #     reason: |
  #       Standards changes require human acknowledgement; not safe to
  #       auto-amend even if the trigger is mechanical.
```

---

## 4. Bead-type-specific cognitive audit hints

Per PROTOCOL.md §3b, after mechanical validation, steering asks: "any
project-binding concern this bead's AC did NOT gate on?" These are the
project's prompts indexed by bead context.

```yaml
cognitive_audit_hints:
  # PROJECT — uncomment to activate

  # touches_wave_pack_yaml:
  #   trigger: |
  #     Any commit in dispatch touches docs/findings/*.yaml.
  #   prompts:
  #     - "Did wave wave_pack_version pin update in the same commit? (§3.17)"
  #     - "Do replay-validator and score-tracker compute the same new hash? (§3.9)"
  #     - "Did ruamel.yaml round-trip get used (not surgical line edits)? (§3.18)"
  #
  # touches_patch_dir:
  #   trigger: |
  #     Any commit touches patches/vulnerabilities/<id>/.
  #   prompts:
  #     - "Was the sibling clj.* / 7hq.* paired bead updated in the same commit?"
  #     - "Did the patch interact with shared middleware? Full-wave-pack regression sweep required, not single-entry test. (§3.22)"
  #
  # touches_level_designs_tree:
  #   trigger: |
  #     Any commit touches docs/level-designs/.
  #   prompts:
  #     - "Do walkthrough filenames still resolve? (dry-run cross-reference)"
  #     - "Do replay fixtures still load in the scoring suite?"
  #
  # claims_oob_verification:
  #   trigger: |
  #     Bead body Acceptance Criteria or Testing Strategy contains the
  #     phrase "out-of-band" or "Robert verifies" or names an external
  #     persona/tool as verifier.
  #   prompts:
  #     - "Did the agent run the named probe itself? (§3.15 — MUST NOT)"
  #     - "Check bash log: any `curl http://localhost:3000/<probe-path>` invocations should NOT appear."
  #
  # migration_or_rename_bead:
  #   trigger: |
  #     Bead title contains "rename", "migrate", "retire", or the body
  #     names retired identifiers.
  #   prompts:
  #     - "Run post-commit grep for retired identifiers: `grep -rln <old-id>`."
  #     - "Any survivors? Flag as a standards firing (file-contract gap)."
  #
  # schema_bearing_bead:
  #   trigger: |
  #     Bead touches a schema file (*.schema.yaml, _preamble.yaml).
  #   prompts:
  #     - "Does the schema change break any pinned enum value consumers expect?"
  #     - "Did the wave yaml's wave_pack_version need rebumping for the schema diff?"
  #
  # bead_with_sibling_output_dependency:
  #   trigger: |
  #     Bead's Changes Needed produces output consumed by a sibling bead
  #     declared in `discovered_from` or `blocks` deps.
  #   prompts:
  #     - "Does the produced output shape match the sibling bead's AC declared input?"
  #     - "If sibling is in_progress in a concurrent dispatch, is the consumer reading the right hash/path?"

  # touches_prompt_template_or_skill_content (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit touches files in .claude/skills/, .claude/agents/, or
  #     .claude/commands/ — anything that the runtime treats as a prompt.
  #   prompts:
  #     - "Was the prompt change reviewed for prompt-injection or unintended tool-grant patterns?"
  #     - "Did the change preserve the version: frontmatter bump if behavior-altering?"
  #     - "Did the changelog get an entry naming the prompt/skill affected?"
  #     - "If the change touches a worker init_prompt, does it preserve the auto-ack-resume guard semantics?"
  #
  # touches_security_policy_file (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit touches .claude/rules/falcon-autopilot.md, .claude/security.md,
  #     or any file under .github/workflows that gates merges.
  #   prompts:
  #     - "Was the gate change reviewed for refuse-on-MVM preservation?"
  #     - "Did the change loosen any SAFE_TO_ACK_INTENT or SAFE_TO_AMEND predicate without a sibling test?"
  #     - "If the change extends autopilot autonomy, was it accompanied by an amendment-budget reduction or other compensating control?"
  #
  # bumps_dependency_or_runtime_version (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit changes pinned version in package.json, requirements.txt,
  #     pyproject.toml, go.mod, Gemfile.lock, OR the minimum Claude Code version
  #     in SKILL.md frontmatter.
  #   prompts:
  #     - "Did changelog and README minimum-version notes update in lockstep with the bump?"
  #     - "Were breaking changes in the bumped dependency reflected in falcon's own behavior or docs?"
  #     - "If bumping Claude Code minimum: does auto-downgrade still trigger correctly on the prior version?"
  #
  # modifies_cron_schedule_or_template (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit touches REFERENCE.md `## Autopilot Cron Prompt Templates`
  #     OR changes the default --cron-cadence in COMMANDS.md.
  #   prompts:
  #     - "Was the change reviewed against the Cron Dispatch-Mode Conventions for both --bg and --via-paste paths?"
  #     - "Does the offset-staggering still hold after the change?"
  #     - "Were both single-dispatch and parallel-dispatch attribution tests run in the scoring/smoke pass?"
  #
  # introduces_new_dispatch_mode_or_flag (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit adds a new --bg-*, --paste-*, --autopilot-* flag OR a new
  #     dispatch-mode value in worker_dispatch_mode.
  #   prompts:
  #     - "Was the new flag added to PROTOCOL.md `### Mode selection + detection`?"
  #     - "Did the cron templates' worker_dispatch_mode branch get extended to cover the new mode?"
  #     - "Does the new flag preserve the refuse-on-MVM precedent if it's write-bearing?"
```

---

## 5. Advisor delegation policy

When a DAR is ambiguous (not clearly auto-approve or clearly reject),
autopilot can fork to a registered advisor before falling back to human.

```yaml
advisor_delegation:
  # PROJECT — uncomment to activate

  # quartermaster:
  #   skill_ref: .claude/skills/quartermaster
  #   delegates:
  #     - dar_in_scope_question:
  #         description: "Is this work in scope of <broader-bead> or this bead?"
  #         rationale: Architectural fit is quartermaster's specialty.
  #     - dar_defer_vs_fix_now:
  #         description: "Should this be deferred or fixed now?"
  #         rationale: Priority/sequencing review is quartermaster's specialty.
  #     - dar_shared_script_extraction:
  #         description: "Should this transformation be extracted to a shared script (§3.21)?"
  #         rationale: Refactor-vs-inline judgment is quartermaster's specialty.
  #
  #   refuses:
  #     # DARs that MUST NOT delegate to quartermaster; human only
  #     - scoring_semantics:
  #         description: "Should this replay score as PASS or FAIL?"
  #         rationale: Pedagogy/intent calls are author-only.

  # herald:
  #   skill_ref: .claude/skills/herald
  #   delegates:
  #     - dar_ux_pattern_choice:
  #         description: "Which UX pattern fits this surface?"
  #         rationale: Design-system fit is herald's specialty.
```

---

## 6. Default amendment budget per bead type

`--amendment-budget` caps how many auto-issued amendments before HALT.

```yaml
amendment_budget_defaults:
  # PROJECT — uncomment to activate

  # chore: 2          # mechanical work; 2 amendments handles most gap-fills
  # bug: 1            # small surface; 1 amendment usually enough
  # feature_small: 2  # single-layer feature; 2 amendments
  # feature_medium: 3 # cross-layer feature; 3 amendments
  # feature_large: 5  # full-stack feature; 5 amendments
  # decision: 0       # spike work — defer all judgment to user
  # spike: 0          # same as decision
  # clj_pair: 1       # paired beads — sibling-bead interaction is brittle, keep tight
  # 7hq_pair: 1       # same as clj_pair
  # epic: 0           # epics don't get amendments; they're parent containers
```

---

## How autopilot reads this file

Per `.claude/skills/falcon/PROTOCOL.md` §3 (Receive and Validate Worker Report) and §3b (Steering-Side Cognitive Audit), the autopilot consumer (when implemented) parses this file at dispatch resume and at completion-signal time.

Order of evaluation:

1. **At intent emission** → `safe_to_ack_intent.gates` (universal) + `safe_to_ack_intent.project_gates` (uncommented only) → all pass = auto-ack
2. **At completion signal** → mechanical validation (steps 1-5 in PROTOCOL.md §3) → cognitive audit (§3b) consulting `cognitive_audit_hints` (uncommented only)
3. **If a gap surfaces** → consult `safe_to_amend_whitelist` (universal + uncommented project) → if matches: auto-issue amendment up to `amendment_budget_defaults` cap
4. **If gap matches `safe_to_amend_denylist`** → never auto-amend; surface to user
5. **If DAR is ambiguous** → consult `advisor_delegation` (uncommented only) → fork or defer

Commented gates are inert. To activate, uncomment + adjust the placeholder text. To deactivate without deleting, re-comment.

---

## Editing workflow

1. **Run `/falcon create-rules`** to populate this file (first time only).
2. **Review project sections** — every `# PROJECT —` block has placeholder gates seeded from your `.claude/rules/*.md` files. Uncomment the ones you want active.
3. **Tune defaults** — adjust amendment-budget numbers and rule references to match your project's standards file naming.
4. **Commit the file** to the repo so other contributors (and other agent sessions) see the same autopilot policy.
5. **Re-run `/falcon create-rules --force`** after major rule-file changes to re-seed defaults; archive the prior version to `.archive/falcon-autopilot-<timestamp>.md`.

---

## Related files

- `.claude/skills/falcon/SKILL.md` — entry point
- `.claude/skills/falcon/COMMANDS.md` — flag specs that consume this file
- `.claude/skills/falcon/PROTOCOL.md` — §3 + §3b (validation + cognitive audit) consume this file
- `.claude/rules/standards.md`, `development-standards.md`, `workflow-execution.md`, `workflow-agents.md` — source of project-specific gate seeds

```

(End of falcon-autopilot.md template.)

### Profile definitions (v6.14.0)

Consumed by `/falcon enable-autopilot --profile=<name>` (see COMMANDS.md and PROTOCOL.md). Defines exactly which `# PROJECT —` items each profile activates, with the detection condition that gates each activation. Items whose detection condition is false stay commented even at aggressive — this prevents activating gates that reference standards the project doesn't have.

Detection condition types:

- `file_exists: <path>` — true if the file exists (path relative to project root)
- `file_grep: <path>, pattern: <regex>` — true if file exists AND pattern matches at least one line
- `directory_has_files: <path>, pattern: <glob>` — true if directory contains at least one file matching glob
- `always` — unconditionally true (used for `safe_to_amend_denylist` items which apply universally)
- `skill_installed: <skill-slug>` — true if `.claude/skills/<slug>/SKILL.md` exists

```yaml
profiles:

  # ---------------------------------------------------------------
  # CONSERVATIVE — minimum-viable autopilot
  # ---------------------------------------------------------------
  conservative:
    description: |
      Minimum-viable autopilot. ALL denylist items active (safety:
      more is better). 1-2 highest-priority intent gates. ZERO
      project whitelist items (universal whitelist only). Tight
      amendment budgets. Use when first activating autopilot on a
      new project.

    items:
      # §1 — intent gates: ONE high-priority gate only
      - section: safe_to_ack_intent.project_gates
        item: example_project_gate
        detection:
          file_exists: .claude/fair-play-policy.md

      # §2 — whitelist: NONE (universal only)

      # §3 — denylist: ALL (always)
      - section: safe_to_amend_denylist
        item: wave_pack_yaml_mutation
        detection: always
      - section: safe_to_amend_denylist
        item: paired_bead_separation
        detection: always
      - section: safe_to_amend_denylist
        item: bypass_manual_close_gate
        detection: always
      - section: safe_to_amend_denylist
        item: wave_yaml_without_recompute
        detection: always
      - section: safe_to_amend_denylist
        item: rules_or_architecture_md_rewrite
        detection: always

      # §4 — cognitive hints: claims_oob_verification only
      - section: cognitive_audit_hints
        item: claims_oob_verification
        detection:
          file_exists: .claude/fair-play-policy.md

      # §5 — advisor: NONE

      # §6 — amendment_budget_defaults: tight
      - section: amendment_budget_defaults
        item: chore
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: bug
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_small
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_medium
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_large
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: decision
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: spike
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: epic
        value: 0
        detection: always

  # ---------------------------------------------------------------
  # STANDARD — recommended for general use
  # ---------------------------------------------------------------
  standard:
    description: |
      Recommended for general use. ALL denylist + project-seeded
      §1, §2, §4 items where detection holds + §5 advisor (if
      quartermaster skill exists) + sensible per-bead-type budgets.

    items:
      # §1 — intent gates: all detected
      - section: safe_to_ack_intent.project_gates
        item: example_project_gate
        detection:
          file_exists: .claude/fair-play-policy.md

      # §2 — whitelist: project items where detection holds
      - section: safe_to_amend_whitelist
        item: missing_wave_pack_version_pin_bump
        detection:
          file_grep:
            path: .claude/rules/development-standards.md
            pattern: '§3\.17|wave_pack_version pin'
      - section: safe_to_amend_whitelist
        item: missing_bd_export_after_batch
        detection:
          file_grep:
            path: .claude/rules/workflow-execution.md
            pattern: 'bd export'
      - section: safe_to_amend_whitelist
        item: missing_closes_footer
        detection:
          file_grep:
            path: .claude/rules/workflow-execution.md
            pattern: 'Closes:|Commit Message Style'
      - section: safe_to_amend_whitelist
        item: stable_identifier_assertion
        detection:
          file_grep:
            path: .claude/rules/standards.md
            pattern: 'stable identifier'

      # §3 — denylist: ALL (always)
      - section: safe_to_amend_denylist
        item: wave_pack_yaml_mutation
        detection: always
      - section: safe_to_amend_denylist
        item: paired_bead_separation
        detection: always
      - section: safe_to_amend_denylist
        item: bypass_manual_close_gate
        detection: always
      - section: safe_to_amend_denylist
        item: wave_yaml_without_recompute
        detection: always
      - section: safe_to_amend_denylist
        item: rules_or_architecture_md_rewrite
        detection: always

      # §4 — cognitive hints: all detected
      - section: cognitive_audit_hints
        item: touches_wave_pack_yaml
        detection:
          directory_has_files:
            path: docs/findings/
            pattern: '*.yaml'
      - section: cognitive_audit_hints
        item: touches_patch_dir
        detection:
          directory_has_files:
            path: patches/vulnerabilities/
            pattern: '*/01-fix.patch'
      - section: cognitive_audit_hints
        item: claims_oob_verification
        detection:
          file_exists: .claude/fair-play-policy.md
      - section: cognitive_audit_hints
        item: migration_or_rename_bead
        detection: always
      - section: cognitive_audit_hints
        item: schema_bearing_bead
        detection: always

      # §5 — advisor: quartermaster if installed
      - section: advisor_delegation
        item: quartermaster
        detection:
          skill_installed: quartermaster

      # §6 — amendment_budget_defaults: template recommended
      - section: amendment_budget_defaults
        item: chore
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: bug
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_small
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: feature_medium
        value: 3
        detection: always
      - section: amendment_budget_defaults
        item: feature_large
        value: 5
        detection: always
      - section: amendment_budget_defaults
        item: decision
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: spike
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: clj_pair
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: 7hq_pair
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: epic
        value: 0
        detection: always

  # ---------------------------------------------------------------
  # AGGRESSIVE — maximum autopilot autonomy
  # ---------------------------------------------------------------
  aggressive:
    description: |
      Maximum autopilot autonomy. EVERY `# PROJECT —` item where
      detection holds. Generous budgets. Use only after running
      standard for several sprints and confirming the autopilot is
      well-calibrated.

    items:
      # §1, §2, §3, §4, §5 — inherit standard's full set
      - inherit_from: standard

      # §1 additions (none beyond standard for this template)

      # §2 additions: add additional whitelist items as the project
      # grows. For the v6.14.0 template seed, standard already covers
      # the documented whitelist; aggressive matches §2 with standard.

      # §6 — generous budgets
      - section: amendment_budget_defaults
        item: chore
        value: 3
        detection: always
      - section: amendment_budget_defaults
        item: bug
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: feature_small
        value: 3
        detection: always
      - section: amendment_budget_defaults
        item: feature_medium
        value: 5
        detection: always
      - section: amendment_budget_defaults
        item: feature_large
        value: 8
        detection: always
      # decision / spike stay 0 (judgment work — no autopilot ever)
      - section: amendment_budget_defaults
        item: decision
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: spike
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: clj_pair
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: 7hq_pair
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: epic
        value: 0
        detection: always
```

### Adapting profiles to a new project

The profile definitions above are seeded from the example project's standards. When falcon ships to a new project, the detection conditions will fail for many items (e.g., `.claude/fair-play-policy.md` doesn't exist; `development-standards.md §3.17` doesn't exist). The command degrades gracefully — items with failed detection stay commented; the user sees the omission in the dry-run preview.

To customize the profiles for a project that has DIFFERENT standards-files / DIFFERENT high-risk patterns, edit this section of REFERENCE.md before running `/falcon enable-autopilot`. Common adaptations:

- Add new project-specific whitelist items with their `rule_ref` and `amendment_text`, then add the `(section, item, detection)` tuple to the appropriate profile.
- Add new denylist items for project-specific catastrophic-amendment patterns; add to ALL three profiles' denylist sections (denylist always defaults to `detection: always`).
- Modify amendment budget defaults to fit the project's tolerance for autopilot scope.
- Re-run `/falcon enable-autopilot --profile=<name> --dry-run` after edits to verify the diff matches intent.

(End of profile definitions.)

---

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

### `--watch` cron prompt template (v6.8.0)

Fired by the cron armed at Step 2 of the dispatch protocol when `--watch` is set. Report-only — never writes to the dispatch file, never auto-acks, never auto-amends. The cron self-cancels on terminal `session_status: complete`.

CronCreate call shape (steering side, at Step 2):

```
CronCreate(
  cron: "*/<N> * * * *",                       # N from --cron-cadence; default 10
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

## Phase 2-5 note (forward compatibility)

This template is the foundation for the wider autopilot rollout. Phase 2
(`--auto-ack`) will land a sibling cron template that READS the same dispatch
fields but ALSO writes `intent_acknowledged_utc` when the `SAFE_TO_ACK_INTENT`
predicate in `.claude/rules/falcon-autopilot.md` passes. Phase 3 (`--auto-amend`)
adds an amendment-issuing cron. Phase 4 (`--worker-cron`) adds a worker-side
amendment-pickup cron. Phase 5 (`--advisor`, `--release-on-merge`) extends both
sides. Every future cron template lives in this REFERENCE.md section and follows
the same `falcon-<role>-<dispatch-id>` slug + sidecar-snapshot-file convention.
```

(End of `--watch` cron prompt template.)

### `--auto-ack` cron prompt template (v6.9.0)

Fired by the cron armed at Step 2 of the dispatch protocol when `--auto-ack` is set. Evaluates the `SAFE_TO_ACK_INTENT` 4-gate predicate against the worker's latest intent paragraph; on all-pass, writes `intent_acknowledged_utc` to the dispatch file and emits the `proceed <dispatch-id>` block inline for the user to relay. On any-fail, defers silently (one inline note per fire that gates failed and why, so the user knows manual ack is needed).

CronCreate call shape (steering side, at Step 2):

```
CronCreate(
  cron: "*/<N> * * * *",                       # N from --cron-cadence; default 5
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

## Cross-cron coordination note

When BOTH `--watch` and `--auto-ack` are armed for the same dispatch, two separate
crons run: `falcon-watch-<dispatch-id>` (10m cadence, report-only) and
`falcon-autoack-<dispatch-id>` (5m cadence, write-bearing). They use independent
sidecar snapshots. /falcon release-cron tears down both via the
`falcon-(watch|autoack)-<dispatch-id>` prefix-match.
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
  cron: "*/<N> * * * *",                       # N from --cron-cadence; default 5 (same as --auto-ack)
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

## Multi-cron coordination

When `--watch --auto-ack --auto-amend` are all armed, THREE separate crons run with
independent slugs (`falcon-watch-`, `falcon-autoack-`, `falcon-amend-`) and
independent sidecars. They do not coordinate; each evaluates its own state-change
criteria. /falcon release-cron tears down all three via prefix-match. Cadences
differ: watch defaults to 10m; auto-ack and auto-amend both default to 5m.
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
  cron: "*/<N> * * * *",                       # N from the setup paste-block; default 3
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
  cron: "*/<N> * * * *",                       # N from --cron-cadence; default 15
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

(End of `--release-on-merge` cron prompt template.)
