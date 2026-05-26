# Standards History

Append-only log of standards firings and rule promotions. Populated by `/wrapup` task 8b when a falcon dispatch's `standards_firings[]` is non-empty.

Format per entry:

```
## §X.Y (<rule-name>) — <YYYY-MM-DD>
**Bead:** <bead-id> · **Branch:** <branch> · **Source:** <falcon | direct>
<one-line context of how the rule applied>
```

Promotion of candidate rules to confirmed: when the same candidate rule text fires 3+ times across recent history, promote it from `candidate:` to a numbered `§X.Y` entry in [`.claude/rules/development-standards.md`](rules/development-standards.md), and reference that promotion here.

---

(No entries yet — `/wrapup` will prepend the first one when a dispatch records a standards firing.)
