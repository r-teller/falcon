# Enhancements

Append-only log of minor enhancement ideas surfaced mid-session — too small to warrant a bead, but worth capturing so they don't get lost. `/wrapup` task 6 reviews open (non-`[RESOLVED]`) entries here and applies them to the target context docs (`.claude/{architecture,backend,...}.md`); after applying, the entry is marked `[RESOLVED]`.

Format per entry:

```
## <YYYY-MM-DD> — <one-line summary>
**Source:** <bead-id | direct | falcon-dispatch-id> · **Target:** <doc to update>
<2-3 sentences describing the enhancement>

[RESOLVED] (added after `/wrapup` applies it)
```

---

## 2026-06-04 — `bd create --deps "blocks:X"` inverts dep direction at creation time
**Source:** direct (Snake Phase 1 session) · **Target:** `.claude/rules/workflow-execution.md` or workflow-planning.md
Using `bd create FOO --deps "blocks:BAR-id"` stores the relationship as `FOO blocks BAR` (the new bead is the blocker), NOT `FOO is blocked-by BAR` (the new bead waits for the listed id). This is the opposite of the intuitive reading and the opposite of every PRD §16-style "Blocked by" column convention. Workaround: use `bd dep add <dependent> <prereq>` after creation. Suggest documenting the gotcha in workflow-execution.md "Dependencies" section, or switching the recommended idiom to per-call `bd dep add` after creation.

## 2026-06-04 — `bd label add` accepts only ONE label per invocation
**Source:** direct (Snake Phase 1 session) · **Target:** `.claude/rules/workflow-planning.md`
`bd label add <id> A B C` treats A as the label and B/C as additional issue IDs, producing "no issue found matching B" errors instead of attaching three labels to one issue. The correct idiom is three sequential invocations: `bd label add <id> A && bd label add <id> B && bd label add <id> C`. Suggest adding a note to workflow-planning.md "Labels" section so future agents don't trip over this when running batch refinements.

## 2026-06-04 — Epic template Success Criteria required by bd lint but not flagged in PRD §16-style breakdown tables
**Source:** SNAKE-egj.5 (Snake Phase 1 session) · **Target:** `.claude/docs/work-item-templates.md`
PRD §16-style "Suggested Bead Breakdown" tables list epics with just an ID + title + child-set. When those epics get created via `bd create --type epic`, bd lint warns "Missing: ## Success Criteria" because the Epic template (work-item-templates.md §"EPIC Template") requires it. Adopters writing PRDs in the §16 style get bitten by this gap. Suggest: either (a) add an "Epic stub vs full" note clarifying that §16 tables are not enough to pass bd lint, or (b) make bd lint auto-skip the warning for epics tagged `seed:prd-table`. Concrete instance tracked as bead SNAKE-zvx.

## 2026-06-04 — `/falcon create-rules` bypassPermissions check doesn't recognize `defaultMode: bypassPermissions`
**Source:** direct (Snake Phase 1 session) · **Target:** `.claude/skills/falcon/COMMANDS.md`
The check in `/falcon create-rules` looks for `bypassPermissions: true` at the top level of `.claude/settings.json` / `~/.claude/settings.json`. This project sets `defaultMode: "bypassPermissions"` instead (Claude Code accepts both forms; the `defaultMode` form is what `/config` writes). The check should also recognize the `defaultMode` form so projects that picked the alternative path don't get a spurious "not configured" warning.

## 2026-06-04 — `bd close` blocks on "blocked by" relationships from later-created beads
**Source:** SNAKE-i0w.1 (Snake Phase 1 session) · **Target:** `.claude/rules/workflow-execution.md` "Close" section
When a prerequisite bead has been created before its dependents, `bd close` refuses to close the prerequisite while ANY dependent is still open ("blocked by open issues..."). This is the inverse-direction failure mode of the deps-syntax gotcha above — but even with correct direction, the same issue surfaces if you try to close prerequisites bottom-up before the dependents are done. Workaround: close in dependency order (closest-to-leaf first) or pass `--force`. Suggest documenting both behaviours: (a) the close-order ordering rule, (b) when `--force` is acceptable (e.g., during incremental landings where the prerequisite is fully implemented but dependents are open follow-ups).
