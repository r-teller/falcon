# changelog.yaml — Schema Reference

Schema reference for `.claude/changelog.yaml` — the structured release log. Each entry covers one session/branch and groups changes by area (backend / frontend / infra / docs / tests / standards). Newest entry on top.

**Companion:** [`handoff-schema.md`](./handoff-schema.md) — the session-state log that lives alongside this file.

**Machine validation:** [`../schemas/changelog.schema.json`](../schemas/changelog.schema.json). The YAML file carries a `# yaml-language-server: $schema=...` header for editor live-validation.

## Reader / writer roles

| Role | Operation |
|------|-----------|
| `/leroy` | Reads `entries[0]` for recent context |
| `navigator-recon` | Reads `entries[0]` via `yq '.entries[0]' .claude/changelog.yaml` |
| `/wrapup` | Prepends a new entry at session end. Never overwrites historical entries. |

## Universal conventions

- **Newest-first ordering** — `entries[0]` is always the most recent session.
- **Quote commit hashes** — `["abc1234"]` not `[abc1234]`. YAML parses bare 7-char hex as a number when it looks numeric, which silently corrupts the value.
- **Area-bullet prefix** — every bullet under `backend:`, `frontend:`, `infra:`, `docs:` starts with `added:`, `changed:`, or `fixed:` so the bullets parse cleanly into release notes and PR descriptions.
- **Optional `template_entry:` block** at the top of the file — recommended. The schema travels with the file and survives future edits.

## SemVer convention

- **MAJOR** (`X.0.0`) — incompatible / breaking API changes
- **MINOR** (`0.X.0`) — new features, backwards-compatible
- **PATCH** (`0.0.X`) — bug fixes, minor improvements
- **MVP** — use `0.x.x` while iterating; bump to `1.0.0` when core features are stable

## Schema

```yaml
# Changelog — structured session log
# Each entry is one session/branch. Newest first.
# /leroy reads entries[0]; /wrapup prepends to the top of entries[].
# Each area bullet is prefixed with added:|changed:|fixed: to indicate change type.
# IMPORTANT: Always quote commit hashes — e.g. ["abc1234"] not [abc1234].

template_entry:
  version: "0.X.Y"
  date: "YYYY-MM-DD"
  branch: "feature/work-YYYYMMDD-HHMM-short-description"
  focus: [feature, bugfix, refactor, infrastructure, documentation, stabilization]
  summary: "One-line summary of the session's work"
  beads: [bead-id-1, bead-id-2]
  epic_progress: "epic-id XX% → YY%"
  backend:
    - "added|changed|fixed: <prose>"
  frontend:
    - "added|changed|fixed: <prose>"
  infra:
    - "added|changed|fixed: <prose>"
  docs:
    - "added|changed|fixed: <prose>"
  tests: "N new/updated, M total passing"
  standards:                              # optional
    - "fired: §X.Y (<rule>) — <how it applied>"
    - "candidate: '<new rule text>' — promote after N occurrences"
  commits: ["abc1234", "def5678"]

entries:
  - <entry 1: this session>
  - <entry 2: prior session>
  - ...
```

## Field semantics

- **`version`** — SemVer string. Bumped per `/wrapup` according to the focus tags + scope of the session's beads.
- **`date`** — calendar date (no time component; use `handoff.yaml` for to-the-minute precision).
- **`branch`** — the feature branch the session worked on.
- **`focus`** — same tag vocabulary as `handoff.yaml`.
- **`summary`** — one prose paragraph (1-3 sentences) describing the session in narrative form. Used as the source for release notes and PR descriptions.
- **`beads`** — flat list of bead IDs closed this session. No prose; just IDs.
- **`epic_progress`** — one-line delta per active epic, e.g., `"asteroid-001 35% → 48%"`.
- **Area buckets** (`backend`, `frontend`, `infra`, `docs`, `tests`) — each bullet prefixed with `added:`, `changed:`, or `fixed:`. Omit any bucket that didn't change this session.
- **`tests`** — short string, not a list. Format: `"N new/updated, M total passing"`.
- **`standards`** — optional. Records which numbered standards rules (see [`development-standards.md`](../rules/development-standards.md)) fired this session, and any new candidate rules surfaced. Promote candidates to confirmed after they recur.
- **`commits`** — list of 7-char commit hashes from the session, in order. Always quoted.

## Example entry

```yaml
entries:
  - version: "0.3.0"
    date: "2026-05-25"
    branch: "feature/work-20260525-power-up-shop-rotation"
    focus: [feature, bugfix]
    summary: "Shop-economy daily-deal rotation lands (timezone-aware deterministic UTC-date hash; admin override slot reserved as asteroid-101). Replay-validator unblocked on 60+ min replays via int32→int64 timestamp widening; backfill required for ~12 historical replays flagged in the leaderboard backlog."
    beads: [asteroid-067, asteroid-042]
    epic_progress: "shop-economy 0% → 22%"
    backend:
      - "added: power-up-shop/rotation.py — DailyDealSelector with UTC-date deterministic hash + 7-day no-repeat memory (asteroid-067)"
      - "fixed: replay-validator/header.proto — timestamp field int32 → int64; reader auto-detects legacy headers via wire-format magic byte (asteroid-042)"
    frontend:
      - "added: renderer/shop_panel.tsx — daily-deal banner + 24h countdown timer; reads from /api/shop/daily-deal endpoint (asteroid-067)"
    infra:
      - "added: docs/level-designs/samples/replays/replay-2026-05-19-overflow.bin — fixture for the 60+ min timestamp bug regression test (asteroid-042)"
    docs:
      - "added: docs/shop-rotation-protocol.md — UTC-date hashing scheme + replay-safety guarantees (asteroid-067)"
    tests: "8 new (5 shop-rotation, 3 replay-header), 247 total passing"
    standards:
      - "fired: §3.2 (deterministic algorithms must be timezone-explicit) — applied to UTC-date hash derivation"
    commits: ["3f8a1c2", "9e02bb4", "11d4470"]
```

## File location & lifecycle

`.claude/changelog.yaml` (project root, alongside `.claude/handoff.yaml`).

**First session:** the file does not exist yet. Run `/wrapup` at session end — it creates the file on first write. Alternatively, `/scribe init` can stub it with a `template_entry:` block (see [`scribe-init`](../agents/scribe/scribe-init.md)).

**Per session:** `/leroy` reads `entries[0]` for orientation; `/wrapup` prepends a new entry at session end. Falcon dispatch reports contribute via the per-branch stash at `.claude/tmp/falcon-reports-<sanitized-branch>.yaml`, which `/wrapup` consumes to populate `summary`, `beads`, area-bucket bullets, `commits`, and any `standards` firings flagged by workers.

**Archive:** after PR merge, large historical entries can be moved to `.archive/changelog/<year>.yaml` to keep the live file scannable. This convention is project-defined; falcon and leroy do not enforce or expect archival.
