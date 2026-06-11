# enhancements.yaml — Schema Reference

Schema reference for `.claude/enhancements.yaml` — the typed, status-tracked log of mid-session enhancement ideas, retro reflections, and standards candidates. Replaces the legacy free-form `enhancements.md` (which suffered from category collision: doc-gap items mixed with retro narratives in one untyped append-only file).

**Companion:** [`handoff-schema.md`](./handoff-schema.md), [`changelog-schema.md`](./changelog-schema.md).

**Machine validation:** [`../schemas/enhancements.schema.json`](../schemas/enhancements.schema.json). The YAML file carries a `# yaml-language-server: $schema=...` header for editor live-validation. The schema validates the `kind`/`status` state machine constraints (e.g., `firings` is required for `kind: standards_candidate`).

## Reader / writer roles

| Role | Operation |
|------|-----------|
| `navigator-recon` | Reads `entries[] | select(.status == "open")` via `yq` at /leroy startup; emits §9 Enhancements Alert when any kind exceeds its threshold |
| `/leroy` | Renders §9 alert + 1-line opt-in triage prompt when navigator surfaces accumulation |
| `/wrapup` Task 4 | Appends new entries (synthesis-mode from falcon `enhancements[]`; direct-session from doc-gaps noticed mid-session) |
| `/wrapup` Task 6 | Transitions `status: open → resolved` via `yq -i` when applying a fix to the target doc |
| `/wrapup` Task 9 Self-Reflection | Appends retro/candidate entries; increments `firings` on existing matching candidates; transitions `status: open → promoted` at 3rd firing |

## Universal conventions

- **Newest-first ordering** — `entries[0]` is always the most recent entry.
- **`id` is auto-generated** — pattern `YYYYMMDD-N` where N is the next available integer for that date. Writers MUST query existing entries to compute N.
- **`status` mutations use `yq -i`** — never edit the field by hand-rewriting the file. Stage with `yq -i` and validate with `yq '.' enhancements.yaml > /dev/null` before commit.
- **`thresholds:` block is tunable per project** — defaults below are calibrated to the reference deployment's cadence; slower or faster projects override.

## Entry kinds + state machines

Each `kind` has its own state machine. Adding a new kind requires extending the wrapup spec to handle its transitions.

| Kind | Open → terminal transition | Aging behavior |
|---|---|---|
| `doc_gap` | Task 6 applies fix to `target` doc → `status: resolved`. Or user-decision → `status: deferred` or `retired`. | Unresolved > 60d → §9 alert prompts to retire/defer. |
| `standards_candidate` | 3rd `firings` count promoted to `development-standards.md` → `status: promoted`. Or user-decision → `status: retired`. | 1-firing > 180d → §9 alert prompts to retire. |
| `retro` | Rare — most stay `open` as historical record. User-decision → `status: deferred` to suppress. | `open > 90d` → §9 alert prompts to archive (move to `.archive/enhancements-history.yaml`). |
| `workflow_friction` | Friction addressed in workflow doc → `status: resolved`. | Same as `doc_gap`. |
| `tooling_pain` | Tooling change addresses pain → `status: resolved`. | Same as `doc_gap`. |
| `other` | Catch-all. No state machine — entries age out at 90d via §9 alert. | 90d → prompt to retire. |

Valid `status` values: `open` (default), `resolved`, `promoted`, `deferred`, `retired`. The `deferred` state suppresses §9 alerts but keeps the entry in the file; `retired` removes from active counts but stays for historical reference.

## Schema

```yaml
# Enhancements — typed log of mid-session enhancement ideas, retros, and standards candidates.
# Replaces legacy free-form enhancements.md.
# /wrapup writes; navigator-recon reads via yq queries on open-status entries.

schema_version: 1

# Per-kind alert thresholds. /leroy emits §9 Enhancements Alert when an open-kind count exceeds.
thresholds:
  open_doc_gap_alert: 10
  open_candidate_alert: 20
  open_retro_alert: 60
  workflow_friction_alert: 15
  tooling_pain_alert: 15
  other_alert: 30
  retro_archive_age_days: 90
  candidate_retire_age_days: 180
  doc_gap_retire_age_days: 60

template_entry:
  id: "YYYYMMDD-N"
  date: "YYYY-MM-DD"
  kind: "doc_gap | retro | standards_candidate | workflow_friction | tooling_pain | other"
  status: "open"
  summary: "one-line — used in startup count + grep"
  source: "bead-id | direct | falcon-dispatch-id"
  target: ".claude/backend.md"   # null for kinds without a target doc
  firings: 1                      # only for kind: standards_candidate; increment on re-firing
  body: |
    Multi-line free-form description. Block scalars accept full-paragraph
    prose — use the room. Retro narratives belong here at full fidelity.
  resolution_note: null           # populated when status transitions away from open

entries:
  []
```

## Writer patterns

### Append a new entry (any kind)

```bash
# Compute next id for today
TODAY=$(date +%Y%m%d)
NEXT_N=$(yq "[.entries[] | select(.id | test(\"^${TODAY}-\"))] | length + 1" .claude/enhancements.yaml)
NEW_ID="${TODAY}-${NEXT_N}"

yq -i ".entries = [{
  \"id\": \"${NEW_ID}\",
  \"date\": \"$(date -u +%Y-%m-%d)\",
  \"kind\": \"doc_gap\",
  \"status\": \"open\",
  \"summary\": \"acc-validator.md missing --strict flag docs\",
  \"source\": \"direct\",
  \"target\": \".claude/acc-validator.md\",
  \"body\": \"The --strict flag was needed for X but wasn't documented...\"
}] + .entries" .claude/enhancements.yaml
```

Newest-first ordering: prepend with `[{new}] + .entries`.

### Transition status (Task 6 resolving a doc_gap)

```bash
yq -i "(.entries[] | select(.id == \"${ID}\") | .status) = \"resolved\"" .claude/enhancements.yaml
yq -i "(.entries[] | select(.id == \"${ID}\") | .resolution_note) = \"Applied to .claude/backend.md §3.4 in commit abc1234\"" .claude/enhancements.yaml
```

### Increment firings on a standards_candidate (Task 9)

When a session detects a candidate pattern that already exists in the file, increment its `firings` count rather than appending a duplicate. If `firings >= 3` after the increment, transition to `status: promoted` AND propose the rule body for `development-standards.md`.

```bash
yq -i "(.entries[] | select(.id == \"${EXISTING_ID}\") | .firings) += 1" .claude/enhancements.yaml
# Then check if firings hit 3
FIRINGS=$(yq ".entries[] | select(.id == \"${EXISTING_ID}\") | .firings" .claude/enhancements.yaml)
if [ "$FIRINGS" -ge 3 ]; then
  yq -i "(.entries[] | select(.id == \"${EXISTING_ID}\") | .status) = \"promoted\"" .claude/enhancements.yaml
fi
```

## Reader patterns

### Open count by kind (navigator-recon §9)

```bash
yq '[.entries[] | select(.status == "open")] | group_by(.kind) | map({(.[0].kind): length}) | add' .claude/enhancements.yaml
# → {doc_gap: 3, standards_candidate: 12, retro: 47}
```

### Get thresholds for comparison

```bash
yq '.thresholds' .claude/enhancements.yaml
```

### Get all open entries of a specific kind for triage

```bash
yq '[.entries[] | select(.status == "open" and .kind == "doc_gap")]' .claude/enhancements.yaml
```

### Find aging entries

```bash
# Open standards_candidate older than 180 days
yq "[.entries[] | select(.status == \"open\" and .kind == \"standards_candidate\" and .date < \"$(date -d '180 days ago' +%Y-%m-%d)\")]" .claude/enhancements.yaml
```

## Migration from legacy `enhancements.md`

New projects vendoring the kit get `enhancements.yaml` directly — no migration needed.

Existing projects that had a free-form markdown `enhancements.md` have two paths:

**Option 1 — Start fresh (recommended).** Archive the existing markdown and let the YAML accumulate from this point forward:

```bash
mkdir -p .archive
mv .claude/enhancements.md .archive/enhancements-history-pre-yaml.md
# .claude/enhancements.yaml already exists from the kit upgrade; /wrapup and
# /leroy now use it exclusively.
```

The archived markdown stays grep-able for historical reference; nothing in the active toolchain reads it.

**Option 2 — Hand-port entries.** If the old markdown has entries worth tracking under the new state machine, append them manually to `enhancements.yaml` using the writer pattern in this doc's "Writer patterns" section. Classify each by `kind` (doc_gap / retro / standards_candidate / workflow_friction / tooling_pain / other) and set `status: open`.

There is no automated migration script. The category collision in the legacy file (Task 4 doc-gaps mixed with Task 9 retros mixed with standards candidates) doesn't auto-classify cleanly enough to be worth a script for a rare one-shot case. Manual is faster than tuning regex heuristics.

Post-migration, the kit's `/leroy` and `/wrapup` use only the YAML file.
