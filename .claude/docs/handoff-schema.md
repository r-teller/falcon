# handoff.yaml — Schema Reference

Schema reference for `.claude/handoff.yaml` — the session-state log. Each entry covers one session/branch and captures what's done, in-progress, blocked, and what's next. Newest entry on top.

**Companion:** [`changelog-schema.md`](./changelog-schema.md) — the structured release-log that lives alongside this file.

**Machine validation:** [`../schemas/handoff.schema.json`](../schemas/handoff.schema.json). The YAML file carries a `# yaml-language-server: $schema=...` header that wires VS Code's yaml-language-server (and other editors that honor the directive) to live-validate edits. CI can validate with `ajv-cli` or `yq` + an external validator.

## Reader / writer roles

| Role | Operation |
|------|-----------|
| `/leroy` | Reads `entries[0]` for session orientation |
| `navigator-recon` | Reads `entries[0]` via `yq '.entries[0]' .claude/handoff.yaml` |
| `/wrapup` | Prepends a new entry at session end. Never overwrites historical entries. |

## Universal conventions

- **Newest-first ordering** — `entries[0]` is always the most recent session.
- **Quote commit hashes** — `["abc1234"]` not `[abc1234]`. YAML parses bare 7-char hex as a number when it looks numeric, which silently corrupts the value.
- **Optional `template_entry:` block** at the top of the file — recommended. The schema travels with the file and survives future edits.

## Schema

```yaml
# Handoff — session state log
# Captures where work stands at end of each session.
# /leroy reads entries[0]; /wrapup prepends a new entry.
# IMPORTANT: Always quote commit hashes — e.g. ["abc1234"] not [abc1234].

template_entry:
  date: "YYYY-MM-DD HH:MM UTC"
  branch: "feature/work-YYYYMMDD-HHMM-short-description"
  focus: [feature, bugfix, refactor, infrastructure, documentation, stabilization]
  completed:
    - "bead-id: what was accomplished"
  discovered:
    - "bead-id: new feature/bug filed this session"
  in_progress:
    - "bead-id: current state of partial work"
  blockers:
    - "bead-id: what's stuck and why"
  next_steps:
    - "bead-id: what to do next, in priority order"
  epic_progress: "epic-id XX% → YY%"
  commits: ["abc1234", "def5678"]
  notes:                                  # optional free-form addenda
    - "anything that doesn't fit the structured fields above"

entries:
  - <entry 1: this session>
  - <entry 2: prior session>
  - ...
```

## Field semantics

- **`date`** — wall-clock session-end time, UTC, to the minute.
- **`branch`** — the feature branch the session worked on; falcon's branch-ownership convention applies.
- **`focus`** — one or more category tags. Used by `/leroy` to color the orientation summary.
- **`completed`** — beads closed this session. Each entry: `"<bead-id>: <one-line outcome>"`.
- **`discovered`** — beads filed mid-session. Same format.
- **`in_progress`** — beads claimed but not closed. Include the partial-work state so a future session knows what to resume.
- **`blockers`** — beads stuck on external dependencies, decisions, or merges. Include the reason.
- **`next_steps`** — prose action list. Priority-ordered. Often references beads, sometimes named operations (e.g., "Open PR for branch X").
- **`epic_progress`** — one-line delta per active epic, e.g., `"asteroid-001 35% → 48%"`.
- **`commits`** — list of 7-char commit hashes from the session, in order. Always quoted.
- **`notes`** — optional. Use for context that doesn't fit the structured fields (e.g., "5 falcon dispatches stashed at `.claude/tmp/falcon-reports-<branch>.yaml`").

## Example entry

```yaml
entries:
  - date: "2026-05-25 18:00 UTC"
    branch: "feature/work-20260525-power-up-shop-rotation"
    focus: [feature, infrastructure]
    completed:
      - "asteroid-067: power-up shop daily-deal rotation (timezone-aware, deterministic per UTC date hash)"
      - "asteroid-042: replay-validator 60+ min timestamp-overflow fix (int32 → int64 in replay header)"
    discovered:
      - "asteroid-101: shop rotation needs admin-override knob for live events (P2 chore)"
    in_progress:
      - "asteroid-001.1: boss-wave variant schema draft (3/5 sections done; AC pending)"
    blockers:
      - "asteroid-051: co-op netcode spike blocked on auth-provider decision (asteroid-119)"
    next_steps:
      - "Open PR for this branch — power-up rotation + replay-validator fix"
      - "After PR merge: dispatch asteroid-001.1 (boss-wave schema) with --advisor=quartermaster"
      - "Refine asteroid-119 (auth provider) so asteroid-051 can unblock"
    epic_progress: "asteroid-001 35% → 35% (no movement); shop-economy epic 0% → 22%"
    commits: ["3f8a1c2", "9e02bb4", "11d4470"]
    notes:
      - "1 falcon dispatch stashed at .claude/tmp/falcon-reports-feature-work-20260525-power-up-shop-rotation.yaml"
```

## File location & lifecycle

`.claude/handoff.yaml` (project root, alongside `.claude/changelog.yaml`).

**First session:** the file does not exist yet. Run `/wrapup` at session end — it creates the file on first write. Alternatively, `/scribe init` can stub it with a `template_entry:` block (see [`scribe-init`](../agents/scribe/scribe-init.md)).

**Per session:** `/leroy` reads `entries[0]` for orientation; `/wrapup` prepends a new entry at session end. Falcon dispatch reports contribute via the per-branch stash at `.claude/tmp/falcon-reports-<sanitized-branch>.yaml`, which `/wrapup` consumes to populate `completed`, `discovered`, `commits`, etc.

**Archive:** after PR merge, large historical entries can be moved to `.archive/handoff/<year>.yaml` to keep the live file scannable. This convention is project-defined; falcon and leroy do not enforce or expect archival.
