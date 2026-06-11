# standards-history.yaml — Schema Reference

Schema reference for `.claude/standards-history.yaml` — the typed audit log of standards rule firings + promotion lifecycle. Replaces the legacy free-form `standards-history.md`.

**Why typed:** the legacy markdown file mixed promoted rules, candidate rules, and per-firing narratives in one prose stream. Queries like "how many times has §3.10 fired this month?" or "which rules haven't fired in 180 days?" required grep gymnastics. The YAML form makes promotion lifecycle and firing audit structured and queryable.

**Companion:** [`enhancements-schema.md`](./enhancements-schema.md), [`handoff-schema.md`](./handoff-schema.md), [`changelog-schema.md`](./changelog-schema.md).

**Machine validation:** [`../schemas/standards-history.schema.json`](../schemas/standards-history.schema.json). The YAML file carries a `# yaml-language-server: $schema=...` header for editor live-validation. The schema enforces slug-key conventions (kebab-case) and validates that every firing's `rule_id` matches the pattern (cross-reference to `rules{}` is by-convention; full referential integrity check belongs in a project-side lint step).

## Reader / writer roles

| Role | Operation |
|------|-----------|
| `/wrapup` Task 8b | Appends `firings[]` entries via `yq -i` (synthesis-mode draws from stashed `standards_firings[]`; direct-session captures inline) |
| `/wrapup` Task 9 Self-Reflection prompt 2 | On promotion (`firings >= 3` on a candidate in enhancements.yaml), adds a new `rules{}` entry here AND ports the rule definition into `rules/development-standards.md` |
| `/wrapup` Task 9 Promotion Review | Queries `rules{}` for deprecation candidates (rules with no firings in N days) |
| Manual `yq` queries | Audit per-rule, per-bead, per-dispatch firing history |

## Universal conventions

- **`rules` is a map keyed by stable slug** — kebab-case identifier auto-generated from rule title at promotion time, manually overridable. Slug is the authoritative reference; section refs (e.g., `§3.10`) are presentational labels that can change.
- **`firings` is a newest-first list** — prepend via `yq -i ".firings = [{new}] + .firings"`.
- **`firing_id` is `YYYYMMDD-N`** — same pattern as enhancements.yaml. N is sequential within a date (1-based); writers query existing entries with `yq "[.firings[] | select(.id | test(\"^${TODAY}-\"))] | length + 1"` to compute next N before writing.

## Slug generation

When a candidate promotes (firings ≥ 3 in `enhancements.yaml`):

1. **Auto-generate from title:** `slugify(rule_title)` → kebab-case, lowercase, ASCII-only. Examples:
   - `"Real-integration verification is a close gate"` → `real-integration-close-gate`
   - `"Cross-service derived values — compute independently"` → `cross-service-derived-values`
2. **Manual override:** if the auto-slug is awkward or collides with an existing one, writer chooses a better one before the rule entry is appended.
3. **Collision:** if the auto-slug already exists in `rules{}`, append `-2`, `-3`, etc. Writer may override.

Slugs never change. If a rule is replaced or split, the old slug stays in `rules{}` with `deprecation_status` set; new rules get new slugs.

## Schema

```yaml
# standards-history.yaml
# Typed audit log of standards rule firings + promotion lifecycle.
# Replaces legacy free-form standards-history.md.
# Schema reference: .claude/docs/standards-history-schema.md
#
# Reader pattern: yq '.firings[] | select(.rule_id == "<slug>")' .claude/standards-history.yaml
# Writer pattern: yq -i '.firings = [{new}] + .firings' .claude/standards-history.yaml

schema_version: 1

# Per-rule metadata, keyed by stable slug. Slug never changes; section_ref can.
rules:
  template_rule:               # example shape; not a real rule
    section_ref: "§X.Y"         # current label in rules/development-standards.md (presentational; may change)
    title: "Human-readable rule title"
    promoted_date: "YYYY-MM-DD"
    promoted_from_bead: "bead-id"            # the bead whose retro triggered promotion
    promoted_from_firings: ["YYYYMMDD-N", ...]  # firing IDs that drove the 3+ firing threshold (optional but recommended provenance)
    deprecation_status: null
      # null = active
      # "deprecated YYYY-MM-DD: <reason>" = no longer applies
      # "split into <slug-a>, <slug-b> (YYYY-MM-DD)" = replaced by N successors
      # "merged into <slug> (YYYY-MM-DD)" = absorbed into another rule

# Time-ordered firings (newest-first). Each firing IS the audit event.
firings:
  - id: "YYYYMMDD-N"                          # firing_id: YYYYMMDD-N, N sequential within date
    date: "YYYY-MM-DD"
    rule_id: "rule-slug-from-rules-keys"      # MUST reference a key in `rules{}` above
    section_ref_at_firing: "§X.Y"             # optional: what the rule was called at firing time (audit trail across renumbers)
    fired_correctly: true                     # false signals deviation/misapplication
    bead_id: "bead-id"                        # which bead this firing occurred on
    dispatch_id: "abc123"                     # null for direct-work; set for falcon dispatches
    commit_sha: "abc1234"                     # optional; the commit where the firing manifested
    action_taken: "followed | deviation | flagged"
    context: |
      Multi-line block scalar — preserve narrative fidelity from prior markdown form.
      Describe what triggered the firing, what evidence supported the rule application,
      and any unusual circumstances. Be specific (cite file paths, line numbers, HTTP
      responses) — generic context entries don't aid future audit.

# Empty file shape (kit ships this):
# rules: {}
# firings: []
```

## Writer patterns

### Append a new firing entry

```bash
# Compute next firing ID for today
TODAY=$(date +%Y%m%d)
NEXT_N=$(yq "[.firings[] | select(.id | test(\"^${TODAY}-\"))] | length + 1" .claude/standards-history.yaml)
NEW_ID="${TODAY}-${NEXT_N}"

yq -i ".firings = [{
  \"id\": \"${NEW_ID}\",
  \"date\": \"$(date -u +%Y-%m-%d)\",
  \"rule_id\": \"real-integration-close-gate\",
  \"section_ref_at_firing\": \"§3.10\",
  \"fired_correctly\": true,
  \"bead_id\": \"foo-42\",
  \"dispatch_id\": \"abc123\",
  \"action_taken\": \"followed\",
  \"context\": \"Close-gate sequence: docker build, curl validation, full sweep — all PASS.\"
}] + .firings" .claude/standards-history.yaml
```

### Add a new promoted rule (during /wrapup Task 9 Self-Reflection)

```bash
# Slug auto-generated from title; writer can override
SLUG="real-integration-close-gate"
SECTION="§3.10"
TITLE="Real-integration verification is a close gate"

yq -i ".rules.\"${SLUG}\" = {
  \"section_ref\": \"${SECTION}\",
  \"title\": \"${TITLE}\",
  \"promoted_date\": \"$(date -u +%Y-%m-%d)\",
  \"promoted_from_bead\": \"foo-42\",
  \"promoted_from_firings\": [\"20260511-1\", \"20260512-1\", \"20260513-1\"],
  \"deprecation_status\": null
}" .claude/standards-history.yaml
```

### Deprecate a rule

```bash
yq -i "(.rules.\"${SLUG}\".deprecation_status) = \"deprecated $(date -u +%Y-%m-%d): superseded by repo-wide CI gate\"" .claude/standards-history.yaml
```

### Section-ref renumber (no schema change to firings)

```bash
# §3.10 → §3.7 after document reorder; only the presentational label changes
yq -i "(.rules.\"real-integration-close-gate\".section_ref) = \"§3.7\"" .claude/standards-history.yaml
# All firings stay pointed at the same slug. section_ref_at_firing fields stay
# at "§3.10" — that's correct; the firing happened when the rule was called §3.10.
```

## Reader patterns

### List all active rules

```bash
yq '.rules | with_entries(select(.value.deprecation_status == null)) | keys' .claude/standards-history.yaml
```

### Firings per rule this month

```bash
yq '[.firings[] | select(.date >= "2026-05-01")] | group_by(.rule_id) | map({rule: .[0].rule_id, count: length})' .claude/standards-history.yaml
```

### Firings of a specific rule

```bash
yq '.firings[] | select(.rule_id == "real-integration-close-gate")' .claude/standards-history.yaml
```

### All firings on a specific bead

```bash
yq '.firings[] | select(.bead_id == "foo-42")' .claude/standards-history.yaml
```

### Per-dispatch firing history

```bash
yq '.firings[] | select(.dispatch_id == "abc123")' .claude/standards-history.yaml
```

### Rules that haven't fired in 90 days (deprecation candidates)

```bash
CUTOFF=$(date -d '90 days ago' +%Y-%m-%d)
FIRED=$(yq "[.firings[] | select(.date >= \"$CUTOFF\")] | map(.rule_id) | unique" .claude/standards-history.yaml)
yq ".rules | keys | map(select(. as \$k | $FIRED | index(\$k) | not))" .claude/standards-history.yaml
```

### Deviation firings (signal of rule misunderstanding)

```bash
yq '.firings[] | select(.fired_correctly == false)' .claude/standards-history.yaml
```

## Lifecycle: candidate → firing → promotion

The full path from "noticed pattern" to "enforced rule":

1. **First observation** — `/wrapup` Task 9 Self-Reflection prompt 2 detects a pattern that "should never happen again." Appends `kind: standards_candidate` to `enhancements.yaml` with `firings: 1`.
2. **Second observation** — same pattern fires again. Task 9 prompt 2 detects the existing match in `enhancements.yaml` and increments `firings` to 2.
3. **Third observation = promotion event** — Task 9 prompt 2 detects match, increments to 3, then:
   - Transitions the enhancements.yaml entry: `status: promoted`
   - Adds a new `rules{slug}` entry to `standards-history.yaml` (this file)
   - Ports the rule definition into `rules/development-standards.md` with the new section ref
   - The promoted_from_firings list captures the candidate's history (3 enhancements.yaml entry IDs, NOT standards-history firing IDs — those start accumulating once the rule is active)
4. **Subsequent firings** — Task 8b appends a firing entry to `standards-history.yaml`'s `firings[]` each time the now-active rule applies during real work. Synthesis-mode draws from stashed `standards_firings[]`; direct-session captures from /wrapup Task 8b's inline review.

## Contract versioning

The schema version (currently **1**) is at the top of the YAML file. CI consumers can check `.schema_version` to detect drift between this doc and the file. Bump on:
- New required fields (minor)
- Field semantic changes (major)
- New top-level sections (minor)

## Migration from legacy `standards-history.md`

New projects vendoring the kit get `standards-history.yaml` directly — no migration needed.

Existing projects with a free-form markdown `standards-history.md` have two paths:

**Option 1 — Start fresh (recommended).** Archive the existing markdown and let the YAML accumulate from this point forward:

```bash
mkdir -p .archive
mv .claude/standards-history.md .archive/standards-history-pre-yaml.md
```

**Option 2 — Hand-port entries.** Walk the markdown rule by rule, append `rules{slug}` entries for promoted rules + `firings[]` entries for each historical firing. Manual is faster than a regex parser for a one-shot.

There is no automated migration script. The legacy markdown's structure (mixed promoted rules + candidates + per-firing narratives, with informal headers) doesn't auto-classify cleanly enough to be worth the script.

Post-migration, the kit's `/wrapup` uses only `standards-history.yaml`.
