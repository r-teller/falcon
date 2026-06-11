# metrics.jsonl — Schema Reference

Schema reference for `.claude/metrics.jsonl` — the append-only log of forecast-vs-actual token + turn measurements per bead per phase. Closes the calibration loop: bead authors forecast in Effort Forecast → tracker captures actuals → analysis refines future forecasts.

**Machine validation:** [`../schemas/metrics.schema.json`](../schemas/metrics.schema.json). Each line of metrics.jsonl is one JSON object validating against this schema. Each record is one bead-phase-session triple.

**Companion:** [`enhancements-schema.md`](./enhancements-schema.md), [`standards-history-schema.md`](./standards-history-schema.md), [`handoff-schema.md`](./handoff-schema.md), [`changelog-schema.md`](./changelog-schema.md).

## Reader / writer roles

| Role | Operation |
|------|-----------|
| `.claude/scripts/token-tracking.py` | Bookmarks transcript line offsets; computes deltas at stop. Stdlib-only Python 3, no jq required |
| `.claude/scripts/velocity-report.py` | Reads metrics.jsonl; reports forecast accuracy by cynefin / size / phase |
| `/leroy` Step 3d | Starts coordinate-phase tracking for multi-bead claims |
| `/leroy` Step 3e | Starts per-bead per-phase tracking on each claim |
| `/wrapup` Task 3c | Flushes pending segments via `jq -n -c >> metrics.jsonl` |

## Universal conventions

- **Append-only** — never overwrite existing lines. New session segments are appended at the bottom.
- **One bead-phase-session per line** — unique key. Re-running a session under the same key updates the same bead's record set.
- **Schema version on every line** — `schema_version: 1`. Reader filters by this when the schema evolves.
- **JSONL format** — one JSON object per line. Use `jq -c` (compact) for writes; readers use `jq -s '.'` to slurp into an array if needed.

## Phase model (5 work phases + coordinate)

| Phase | Purpose | When applicable |
|---|---|---|
| `coordinate` | Multi-bead batch planning (set internally by `--coordinate` mode) | Multi-bead claims at `/leroy` Step 3d |
| `plan` | Per-bead scoping, context loading, approach confirmation | Every bead at claim time |
| `discover` | Research, spikes, exploration to fill spec gaps | Spike beads + bugs that need diagnosis + any bead with unknown unknowns |
| `implement` | Writing production code + tests + migrations | Every bead (except pure spikes that produce only findings) |
| `test` | Verification, test runs, manual smoke checks | Every bead |
| `fix` | Iteration after tests reveal regressions | Bugs + any bead where the test phase surfaced new failures |

The Effort Forecast contract in [`.claude/docs/work-item-templates.md`](./work-item-templates.md) requires authors to forecast every applicable phase at `triage:ready` time. The tracker accepts all 6 values; analysis joins on phase name.

## Two record shapes (via `record_type` discriminator)

The schema supports two record types:

### `record_type: bead_effort` — per-phase token/turn record (default)

The dominant shape. One per bead per phase per session.

```json
{
  "schema_version": 1,
  "record_type": "bead_effort",
  "bead_id": "asteroid-067",
  "session_id": "40a6bb57-5ef8-419c-ba67-53b9e1d0c857",
  "issue_type": "feature",
  "issue_size": "medium",
  "cynefin_domain": "complicated",
  "phase": "implement",
  "beads_in_scope": [],
  "allocation_method": null,
  "branch": "feature/work-20260525-power-up-shop-rotation",
  "forecast_output_tokens": 5700,
  "forecast_turns": 13,
  "actual_output_tokens": 24404,
  "actual_input_tokens": 12,
  "actual_cache_read_tokens": 2914652,
  "actual_cache_create_tokens": 25786,
  "turns": 12,
  "started": "2026-05-25T17:37:03Z",
  "stopped": "2026-05-25T17:38:34Z",
  "orphaned": false,
  "timestamp": "2026-05-25T17:50:00Z",
  "bead_created_at": "2026-05-20T14:00:00Z",
  "bead_closed": "2026-05-25T17:45:00Z",
  "priority": 1,
  "parent_epic": "shop-economy",
  "discovered_from": null
}
```

### `record_type: session_time` — session-level time analysis

Optional. One per session at `/wrapup`. Captures human-vs-AI time breakdown.

```json
{
  "schema_version": 1,
  "record_type": "session_time",
  "session_id": "40a6bb57-...",
  "ai_active_seconds": 4123,
  "human_review_seconds": 892,
  "human_think_seconds": 245,
  "human_idle_seconds": 102,
  "human_away_seconds": 18000,
  "away_pct": 78.5,
  "flow_efficiency_pct": 67.3,
  "cynefin_domain": "complicated",
  "drift_risk": "low",
  "layers": ["backend"]
}
```

## Writer pattern (the `jq -n -c` template)

`/wrapup` Task 3c appends segments to metrics.jsonl using this template. Pipe through `jq -c` (NOT `jq` without flags) to guarantee one JSON object per line.

```bash
jq -n -c \
  --arg bead_id "$BEAD_ID" \
  --arg session_id "$SESSION_ID" \
  --arg branch "$BRANCH" \
  --arg phase "$PHASE" \
  --arg cynefin "$CYNEFIN_DOMAIN" \
  --arg size "$ISSUE_SIZE" \
  --arg type "$ISSUE_TYPE" \
  --arg started "$STARTED" \
  --arg stopped "$STOPPED" \
  --argjson forecast_output "${FORECAST_OUTPUT_TOKENS:-null}" \
  --argjson forecast_turns "${FORECAST_TURNS:-null}" \
  --argjson actual_output "$ACTUAL_OUTPUT_TOKENS" \
  --argjson actual_input "$ACTUAL_INPUT_TOKENS" \
  --argjson actual_cache_read "$ACTUAL_CACHE_READ" \
  --argjson actual_cache_create "$ACTUAL_CACHE_CREATE" \
  --argjson turns "$TURNS" \
  --argjson beads_in_scope "${BEADS_IN_SCOPE:-[]}" \
  --arg allocation_method "${ALLOCATION_METHOD:-null}" \
  --argjson orphaned "${ORPHANED:-false}" \
  '{
     schema_version: 1,
     record_type: "bead_effort",
     bead_id: $bead_id, session_id: $session_id, branch: $branch,
     phase: $phase, cynefin_domain: $cynefin,
     issue_size: $size, issue_type: $type,
     started: $started, stopped: $stopped,
     forecast_output_tokens: $forecast_output, forecast_turns: $forecast_turns,
     actual_output_tokens: $actual_output, actual_input_tokens: $actual_input,
     actual_cache_read_tokens: $actual_cache_read, actual_cache_create_tokens: $actual_cache_create,
     turns: $turns, beads_in_scope: $beads_in_scope, allocation_method: $allocation_method,
     orphaned: $orphaned,
     timestamp: (now | strftime("%Y-%m-%dT%H:%M:%SZ"))
   }' \
  >> .claude/metrics.jsonl
```

After writing, validate the latest line:

```bash
tail -1 .claude/metrics.jsonl | jq -e '. as $r | if ($r.schema_version == 1) then true else error("schema_version mismatch") end' > /dev/null \
  || echo "ERROR: latest metrics line failed schema check"
```

## Reader patterns

### Forecast accuracy by cynefin domain (last 30 days)

```bash
jq -r 'select(.timestamp >= "2026-05-12" and .record_type == "bead_effort") |
       {cynefin: .cynefin_domain,
        forecast: .forecast_output_tokens,
        actual: .actual_output_tokens,
        ratio: (.actual_output_tokens / (.forecast_output_tokens // 1))}' \
   .claude/metrics.jsonl \
| jq -s 'group_by(.cynefin) | map({cynefin: .[0].cynefin, avg_ratio: ([.[].ratio] | add / length), count: length})'
```

### Per-phase variance (which phase blows out the forecast most?)

```bash
jq -r 'select(.record_type == "bead_effort") |
       {phase, variance: ((.actual_output_tokens - .forecast_output_tokens) / (.forecast_output_tokens // 1))}' \
   .claude/metrics.jsonl \
| jq -s 'group_by(.phase) | map({phase: .[0].phase, avg_variance: ([.[].variance] | add / length)})'
```

### Size-class calibration check (are size:medium beads actually medium?)

```bash
jq -r 'select(.issue_size == "medium" and .record_type == "bead_effort") |
       {turns: .turns, forecast: .forecast_turns,
        ratio: (.turns / (.forecast_turns // 1))}' .claude/metrics.jsonl \
| jq -s 'add | length'
```

### Drift detection (beads where actual > 2x forecast)

```bash
jq 'select(.record_type == "bead_effort" and
           (.actual_output_tokens / (.forecast_output_tokens // 1)) > 2)' \
   .claude/metrics.jsonl
```

### Per-bead history

```bash
jq 'select(.bead_id == "asteroid-067")' .claude/metrics.jsonl
```

### Cross-session resume detection (same bead, same phase, multiple sessions)

```bash
jq -r 'select(.record_type == "bead_effort") |
       "\(.bead_id) | \(.phase) | \(.session_id)"' .claude/metrics.jsonl \
| sort | uniq -c | awk '$1 > 1 {print}'
```

## Schema validation in CI

```yaml
# .github/workflows/metrics-schema.yml
name: Metrics Schema Check
on:
  pull_request:
    paths: ['.claude/metrics.jsonl']

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install ajv-cli
        run: npm install -g ajv-cli
      - name: Validate each metrics line
        run: |
          while IFS= read -r line; do
            echo "$line" | ajv validate -s .claude/schemas/metrics.schema.json -d -
          done < .claude/metrics.jsonl
```

## Lifecycle

| Stage | What happens |
|---|---|
| `/leroy` Step 3d (multi-bead claim) | `token-tracking.py start --coordinate --beads <ids> --session <sid>` — captures planning-phase cost |
| `/leroy` Step 3d.5 (plan confirmed) | `stop --coordinate --session <sid>` — appends coordinate record |
| `/leroy` Step 3e (per-bead claim) | For each bead: `start --bead <id> --phase plan --session <sid>` |
| During work — phase transition | User runs `stop --bead <id>` then `start --bead <id> --phase <next>` |
| Cross-session resume | `start --bead <id> --phase <same> --session <new-sid>` banks tokens; new segment starts |
| `/wrapup` Task 3c | Status check per bead; orphan-detect; flush all pending segments to metrics.jsonl |
| Session end | `.claude/tmp/{session_id}.json` deleted (tracker state) |

## Composition with `--minimal` flags

- **`/leroy --minimal`** (continuation mode): does NOT auto-start tracking. Continuation skips the new-bead claim flow. If the user wants to track work on a resumed bead, run `token-tracking.py start --bead <id> --phase implement --session $SID` manually.
- **`/wrapup --minimal`** (typo fix, checkpoint): Task 3c flush still runs. The data captured by any pending tracker is too useful to skip. Cost is ~50k eff-tokens per bead in `worked_beads`.

## Per-project state

Tracker state files live in `.claude/tmp/.token_tracking/` (gitignored). The metrics.jsonl file itself is per-project; can be committed (team-shared calibration data) or gitignored (private metrics).

## Migration

New projects start with an empty metrics.jsonl. Existing projects that adopted falcon before this schema (no metrics) — just start fresh; no migration script needed.
