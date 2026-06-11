# Bead Contract Lint Integration

How to wire `.claude/scripts/check-bead-contract.py` into the kit so the tier-contract checks fire automatically. The script validates beads against the contracts in [`work-item-templates.md`](./work-item-templates.md) (Readiness Checklist + tier-specific sections + labels + rules).

## What the script enforces

For every bead in the selected mode, the script verifies:

| Tier | Required labels | Required sections | Other rules |
|---|---|---|---|
| `triage:backlog` | `type:*` (not `task`) | Summary, Persona, Phase, Open Questions, Rough Size Estimate | — |
| `triage:triaged` | + `cynefin:*`, `size:*` | + Acceptance Criteria | `cynefin:disorder` blocked; bug Fix Approach may be TBD |
| `triage:ready` | + `persona:*`, `layer:*` | + Changes Needed, Effort Forecast (per-phase), Required Context (if `cynefin:complicated`/`complex`) | No TBDs; `cynefin:chaotic` blocked |
| No `triage:*` | — | — | **Defect**: must be triaged |

Exit codes: `0` clean / `1` HARD violation / `2` SOFT violation only (when `--strict` is off).

### Severity model (v1.1)

Contract violations are split into HARD and SOFT to keep capture and refinement flows friction-free while still catching broken readiness assertions:

| Rule | Default severity |
|---|---|
| `no_triage_label` (defect) | **HARD** |
| `invalid_type_task` (defect) | **HARD** |
| `cynefin_disorder_blocked` / `cynefin_chaotic_blocked` | **HARD** |
| `tbd_at_ready` | **HARD** |
| `effort_forecast_not_per_phase` (ready) | **HARD** |
| `required_context_invalid:missing` (ready, complicated/complex) | **HARD** |
| `missing_required_label` / `missing_required_section` AT `triage:ready` | **HARD** |
| `missing_required_label` / `missing_required_section` AT `triage:backlog` or `triage:triaged` | SOFT |
| `required_context_invalid:empty` / `:no_refs_no_explicit_none` | SOFT |

Net behavior on a typical pre-push hook (default mode, no `--strict`):

- Pushing a fresh stub bead missing template sections → **warns**, push allowed
- Pushing mid-refinement (`triage:triaged`) work → **warns** about gaps, push allowed
- Pushing a bead asserted as `triage:ready` that's missing Required Context, has a single-number Effort Forecast, or has TBDs → **blocks**, push refused
- Pushing a bead with no `triage:*` label at all → **blocks** (structural defect)

`--strict` promotes every SOFT to HARD — single knob for projects that want maximal enforcement (e.g., CI as a backstop where any drift should fail the PR).

## Mode selection

```bash
# Tactical: explicit bead set
python3 .claude/scripts/check-bead-contract.py --beads foo-42,foo-43

# Tactical: beads touched in the current session
# (derives from .claude/tmp/<session_id>.json `started` timestamp)
python3 .claude/scripts/check-bead-contract.py --session

# Time-bounded
python3 .claude/scripts/check-bead-contract.py --since 2026-05-01

# Status-scoped
python3 .claude/scripts/check-bead-contract.py --in-progress
python3 .claude/scripts/check-bead-contract.py --stale --days 7

# Full audit
python3 .claude/scripts/check-bead-contract.py --all

# CI integration: JSON output + strict mode (warns become fails)
python3 .claude/scripts/check-bead-contract.py --all --strict --json

# Pipe into other commands: --ids emits one bead ID per line, no headers
python3 .claude/scripts/check-bead-contract.py --all --ids               # default = fail IDs
python3 .claude/scripts/check-bead-contract.py --all --ids warn          # warn IDs
python3 .claude/scripts/check-bead-contract.py --all --ids all           # fail + warn IDs
python3 .claude/scripts/check-bead-contract.py --all --ids pass          # passing IDs
```

### Pipe-into-other-command recipes

`--ids` makes it trivial to chain the script into bd or git operations:

```bash
# Show details on every failed bead
python3 .claude/scripts/check-bead-contract.py --all --ids | xargs -I{} bd show {}

# Comment all failed beads with a refinement reminder (e.g., at wrapup time)
python3 .claude/scripts/check-bead-contract.py --session --ids | \
  xargs -I{} bd comments add {} "Contract violations detected — refine before next push"

# Count failures only
python3 .claude/scripts/check-bead-contract.py --all --ids | wc -l

# Diff against last run (track refinement progress over a sprint)
python3 .claude/scripts/check-bead-contract.py --all --ids | sort > .tmp/failed-today.txt
diff .tmp/failed-yesterday.txt .tmp/failed-today.txt   # which beads were fixed today?
```

`--ids` and `--json` are mutually exclusive output modes (the script errors if both are passed).

`--branch` is intentionally absent. Dolt-backed projects shouldn't infer bead state from git diffs — `bd list --updated-after <session-start>` (via `--session`) gives the same precision without depending on `.beads/issues.jsonl` being staged or up-to-date.

## Integration paths

Three paths, pick whichever fits your tooling.

### Path 1 — `.beads/hooks/pre-push` extension (recommended for Dolt-backed projects)

bd ships hooks that fire on git operations to sync Dolt state. Extending `pre-push` is the right integration point because it catches the cumulative state before work leaves the local machine.

Append to `.beads/hooks/pre-push`:

```bash
# Bead contract check (kit-managed, see .claude/docs/lint-integration.md)
if [ -x .claude/scripts/check-bead-contract.py ]; then
  python3 .claude/scripts/check-bead-contract.py --session || {
    echo "Bead contract violations — push blocked."
    echo "Run: python3 .claude/scripts/check-bead-contract.py --session --json | jq ."
    exit 1
  }
fi
```

The `--session` mode is precise (only beads this session touched). If the session-tracker is absent (e.g., direct `git push` without /leroy startup), fall back to `--since "$(git log -1 --format=%aI HEAD~10)"` or similar.

### Path 2 — CI workflow step (GitHub Actions example)

Run `--all --strict` on PRs to catch any open bead that doesn't meet its tier contract. Useful as a periodic backstop even when local hooks miss violations.

```yaml
# .github/workflows/bead-contract.yml
name: Bead Contract Check
on:
  pull_request:
    paths: ['.beads/**']

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install bd
        run: curl -sSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
      - name: Sync Dolt
        run: bd dolt pull
      - name: Check tier contracts
        run: python3 .claude/scripts/check-bead-contract.py --all --strict --json
```

### Path 3 — `/wrapup` Task 9b integration (built-in)

Task 9b (Verification Sweep) in [`wrapup.md`](../commands/wrapup.md) calls `python3 .claude/scripts/check-bead-contract.py --session` by default (see Task 9b's `b. Validate beads touched this session` block). No extra wiring required — the kit's /wrapup honors the contract automatically.

## Output formats

### Human-readable (default)

```
[FAIL] foo-42 (triage:ready, cynefin:complicated)
  - cynefin:complicated requires `## Required Context` section
    [rule: required_context_invalid]
  - Effort Forecast must have plan/implement/test breakdown + Total + Confidence
    [rule: effort_forecast_not_per_phase]

[WARN] foo-43 (triage:ready, cynefin:clear)
  - `## Required Context` section is empty; add 1-3 entries OR write '(none — reason)'
    [rule: required_context_invalid]

Summary: 1 FAIL, 1 WARN, 1 PASS
```

### JSON (`--json` flag)

```json
{
  "contracts_version": "1.1",
  "checked": 3,
  "pass": 1,
  "warn": 1,
  "fail": 1,
  "violations": [
    {
      "bead_id": "foo-42",
      "severity": "fail",
      "tier": "ready",
      "cynefin": "complicated",
      "rule": "required_context_invalid",
      "detail": "cynefin:complicated requires `## Required Context` section"
    }
  ]
}
```

## bd interaction + performance

The script calls bd via subprocess. To stay fast at corpus scale:

- **Single `bd list --json --limit 0` call** populates the audit corpus with full bead bodies (the envelope format includes `description`). The audit loop iterates dicts in memory; no per-bead `bd show` subprocess fan-out.
- **`BD_JSON_ENVELOPE=1` is set automatically** in the bd subprocess env so the script always sees the envelope format (`{data: [...], schema_version: N}`). Forward-compatible with bd v2.0; backward-compatible with bd v1.x. Users don't need to opt in manually.
- **Measured:** ~1 sec for a 160-bead project. Per-bead `bd show` fallback (used only when `--beads` references a closed bead not in the open corpus) is the only remaining N-subprocess path.

If you observe slow runs, check whether bd is itself slow (`time bd list --json --limit 0`). The script's overhead is dominated by that single call.

## Contract versioning

The script's `CONTRACTS_VERSION` constant tracks the contract schema. Bump it when:
- New rules are added to a tier
- Existing rule semantics change
- Labels/sections required by a tier change

Always bump the constant AND the schema-version note in `work-item-templates.md` together. CI consumers can read `contracts_version` from JSON output to detect drift between the lint script and the templates.

Current: **1.1** (severity-by-tier model; matches templates schema 1.0).

## Adding new rules

To extend the lint with a project-specific or kit-managed rule:

1. Add the rule to the appropriate tier in `work-item-templates.md` (the contract source of truth).
2. Implement the check in `audit_bead()` in `check-bead-contract.py`. Each rule appends a violation dict with `severity` / `rule` / `detail` to the returned list.
3. Bump `CONTRACTS_VERSION` (minor for additions; major for breaking changes).
4. Document the change in `work-item-templates.md`'s schema-version log.

If the rule is project-specific (not for upstream), keep the change in the project's vendored copy of the script. If it's a kit-level rule, contribute upstream.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `bd_show_failed` for every bead | bd CLI not on PATH or Dolt not running | Verify `bd list` works manually first |
| `--session` mode errors with "No session trackers found" | `/leroy` startup wasn't run; no tracker file exists | Use `--since` with a recent date instead, OR run `/leroy` once to seed the tracker |
| All beads fail with `effort_forecast_not_per_phase` | Pre-kit-v2 beads with single-number forecasts | Use `--since <date>` to exclude legacy beads from check until refined |
| `--stale` returns nothing on a busy project | All beads recently touched | Pass `--days 30` or higher to widen the window |

## Self-test

Run against the kit's own bd state (if the upstream has beads) to verify the script works:

```bash
python3 .claude/scripts/check-bead-contract.py --all --json | jq '.checked, .pass, .fail'
```

Should return the count of beads + a pass/fail breakdown. Zero violations on a clean project; expected violations on legacy beads.
