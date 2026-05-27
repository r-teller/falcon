# Workflow: Execution

Purpose: How to implement work — branching, claiming work items, writing code, committing, and creating pull requests.

> **Terminology for this project:**
> "Work item" / "item" / "issue" throughout this file refers to a **bead** — managed via the beads (`bd`) CLI.

Use this file **during implementation**. It is the primary reference while you
are actively writing code. It covers the claim/execute checklists, branching
conventions, commit standards, and pull request creation. Do not use this file
for scoping or planning work — see `workflow-planning.md` for that.

---

## Confirmation Gates (Publication Intent)

Some actions take work from "private/local" to "the team is being asked to look at this, react to it, or merge it." These are publication events. They ALWAYS require explicit user confirmation before execution, regardless of any standing autonomy instruction. Other shared-state operations (routine pushes, syncs, backups) are NOT gated — they are how work moves through the normal workflow without unnecessary friction.

The test is **publication intent**: does this action signal to the team "review this / approve this / take action on this"? If yes, gate. If it's storage/sync/backup, don't.

### What's gated, what isn't

| Action | Gated? | Why |
|--------|--------|-----|
| Edit / Write / Read files | No | Local |
| `git add`, `git commit` | No | Local |
| Run tests, linters, build | No | Local |
| Update local work-item state | No | Local |
| `git push` to a feature branch (any number of times) | **No** | Storage/sync; the branch is just where the work lives until a PR points at it |
| `git push --force` (any branch) | **Yes** | Destructive; can overwrite others' commits |
| `git push` to `main` / protected branch | **Yes** | Bypasses PR review entirely |
| `bd dolt commit` / `bd dolt push` | No | Routine sync of shared work-tracking DB (note: `bd sync` was removed in bd 1.0) |
| `gh pr create` (including `--draft`) | **Yes** | The publication event |
| `gh pr ready` (lift draft → ready) | **Yes** | Same publication event, different command |
| `gh pr edit` (title or body changes) | **Yes** | Visible change to a public artifact |
| `gh pr comment` / `gh pr review` | **Yes** | Visible action; may notify others |
| `gh pr merge` | **Yes** | Often the user does this via UI; if you do it, ask |
| `gh pr close` / `gh pr reopen` | **Yes** | Visible state change, easy to do by accident |
| `gh issue create` / `gh issue comment` | **Yes** | Same publication intent as PR comments |
| Slack / email / external mutating APIs | **Yes** | Visible to others, often irreversible |
| Deploys, service restarts | **Yes** | External-state side effects |

### Procedure (end-of-request rhythm)

The natural unit for confirmation is the **request**, not the commit or push. Inside one request you may make many local commits and many feature-branch pushes — all proceed under autonomy. The gate fires once, at the end of the request, when you're handing back control:

1. **Finish the requested work.** Local edits, commits, tests, and feature-branch pushes happen freely.
2. **Summarize what was done.** What changed, what was verified, what is on the branch (and on origin if pushed).
3. **Check PR state.**
   - **No PR yet for this branch:** Ask: *"Work for [request] is done. Want me to open the PR?"* Wait for approval before `gh pr create`.
   - **PR already exists for this branch:** Ask: *"Work for [request] is done. N new commits since the PR was opened. Want me to update the PR title/body to reflect the new work?"* Wait for approval before `gh pr edit`.
4. **Wait** for explicit approval before each gated action. Approval for one gated action does NOT carry to the next. If the user approves "open the PR," that does not also approve `gh pr merge`.

### Post-PR updates (full template re-review)

When the user approves a post-PR update, do a **full review of `.claude/docs/PULL_REQUEST_TEMPLATE.md` against cumulative work-since-PR**, not just an append:

1. Re-read the PR template.
2. Re-read the current PR (`gh pr view <num> --json title,body`).
3. Walk every template section. Decide which need updating:
   - **Title**: Keep if work still fits the original framing (e.g., original "ship apples" + new "ship fuji apples" — title still accurate). Update if scope materially shifted (e.g., original "ship apples" + new "ship oranges" — title becomes "ship apples and oranges").
   - **Summary** / **Changes** / **Files Changed table** / **Beads** / **Test Plan**: Update each section that the new commits affect.
4. Present the proposed title + body diff to the user.
5. After approval, run `gh pr edit --title ... --body ...`.

This is a fuller pass than a one-line append because the PR is the team's view of what this work is. Drift between the PR description and the actual diff is misleading — fix it whenever new work lands.

### Autonomy instructions do not authorize gated actions

A standing instruction like "work without stopping for clarifying questions" is **scope authorization** — approval to take judgment calls about approach, file structure, naming, sequencing, and similar local decisions. It is NOT push-to-protected, force-push, PR-create, PR-edit, PR-merge, or external-post authorization. Treat the gate as durable across the whole session unless the user explicitly says "and you can [specific gated action] without asking" — those words must be present.

If the user says "ship it," that is approval for that one gated action in the immediate conversation context. It does not stand for the rest of the session.

### Why this gate exists

Procedural step lists (e.g., the **Pull Requests** section below) describe the eventual flow from local work to merged PR. They do NOT authorize chaining the public steps without a user checkpoint. The default is: pause at the publication boundary every time, even when the workflow file lists the next step.

The most common failure mode is treating "the workflow says to create the PR next" as permission to create the PR next. The workflow describes what eventually happens; the user decides when each publication event happens.

---

## Branching Strategy

All work is done on feature branches that are merged to `main` via pull request.

### Branch Naming Convention

Create branches with a unique work ID and short description:

```
<type>/<work-id>-<short-description>
```

Types: `feature`, `fix`, `chore`, `docs`, `refactor`

Work ID format: `work-YYYYMMDD-HHMM` (timestamp-based, or sequential number)

Examples:
- `feature/work-20260323-canvas-engine`
- `fix/work-20260323-collision-bug`
- `chore/work-20260323-cleanup-imports`

### Starting a Work Session

1. **Create the work branch:**
   ```bash
   # Generate a unique work ID (use timestamp or sequential number)
   WORK_ID="work-$(date +%Y%m%d-%H%M)"
   git checkout -b feature/${WORK_ID}-<description>
   ```

2. **Associate work items with this branch:**
   - Update items to `in_progress` as you work on them
   - Any new issues discovered during work are linked via `bd create ... --deps "discovered-from:<current-id>"`

### During Development

- Make atomic commits as work progresses
- Reference work items in commit messages with `Closes: <id>`
- Create new work items for bugs/gaps discovered during development

---

## Claim and Execute

### Start Checklist — before writing any code:

- [ ] Item is `triage:ready` (if not, enrich first)
- [ ] **If item carries a `pair:<id>` label, apply the Paired-Claim Rule below before claiming.**
- [ ] `bd update <id> -s in_progress` (skip if plan-only refinement — item stays open)
- [ ] Verify Effort Forecast exists on the item (see below)
- [ ] Read item description (`bd show <id>`) and capture: `priority`, `parent_epic`, `bead_created_at`, `discovered_from`
- [ ] Load context files referenced in the item

> **STOP.** Do not open any file for editing until every box above is checked.
> Every item is a command — if you can't copy-paste it, the checklist is broken.

### Paired-Claim Rule (project-defined)

Some projects use a `pair:<id>` label convention to mark beads that must claim and close together (e.g., a feature bead paired with its test bead, a schema migration paired with its rollback, or a recipe paired with its validator). The pair is the unit of work.

When the Start Checklist's item ID has a `pair:<id>` label:

- [ ] Resolve the sibling: `bd list --label pair:<id>` returns both beads
- [ ] Claim BOTH: `bd update <bead-a> -s in_progress` AND `bd update <bead-b> -s in_progress`
- [ ] Use a single feature branch covering both deliverables
- [ ] Author BOTH artifacts before validating either
- [ ] Verify the **pair close gate** defined in your project's `development-standards.md` (or equivalent rule file)
- [ ] Close BOTH: `bd close <bead-a>` AND `bd close <bead-b>` with a shared rationale citing the pair label
- [ ] Single commit covering both deliverables with `Closes: <bead-a>` AND `Closes: <bead-b>` in the message

If only one half of a pair is claimable (e.g., the sibling is `in_progress` by another session), do NOT claim the half — pick a different pair instead. Paired beads must not be split across sessions.

**Falcon integration:** for paired-bead dispatches, use `/falcon work beads <bead-a>,<bead-b> --sequential` — one worker handles both in declared order, inheriting context cleanly. See [falcon `--sequential`](../skills/falcon/COMMANDS.md) for the override semantics.

### Verify Effort Forecast

Before transitioning to implementation, verify the work item has a **per-phase** Effort Forecast. Per-phase estimates that sum to a total give clean apples-to-apples comparison at close time.

1. Read the work item's description (`bd show <id>` for beads) and check for the `Effort Forecast:` section. It must list each expected phase (typical: plan, implement, test) plus a Total line.
2. If missing or single-number-only (e.g. item created before this convention), add a per-phase forecast now:
   ```bash
   bd comments add <id> "Effort Forecast (revised):
   - Plan: ~N turns, ~N tokens (rationale: e.g. reads 2 files for context)
   - Implement: ~N turns, ~N tokens (rationale: type+size historical average)
   - Test: ~N turns, ~N tokens (rationale: e.g. pytest + likely 1-2 fix iterations)
   - Total: ~N turns, ~N tokens
   - Confidence: low/medium/high"
   ```


### End Checklist — after all Acceptance Criteria checklist items pass:

- [ ] Tests written per item's Testing Strategy — diff each listed test case against actual test files before closing
- [ ] Automated verification passes (pytest, linter, type checker)
- [ ] Manual verification of each Acceptance Criteria item confirmed
- [ ] `bd close <id>`
- [ ] Commit includes `Closes: <id>` in message


**When presenting a plan to the user**, include claim as step 0 and
close with effort as the final step. Plans without these steps are
incomplete.

---

## Issue Statuses

| Status | Meaning |
|--------|---------|
| `open` | Ready to start (default) |
| `in_progress` | Currently being worked on |
| `blocked` | Waiting on dependency or external factor |
| `deferred` | Postponed for later |
| `closed` | Completed |

## Execution Order

When implementing features, follow this order to minimize rework:

1. **Schema/data model** — migrations, model definitions
2. **API/service layer** — endpoints, route handlers
3. **Business logic** — service functions, validation
4. **Tests** — unit, integration, E2E
5. **Documentation** — update context files, API docs
6. **Frontend/UI** — consume the API, build the interface

## Handling Blocked Work

If work is blocked by an external factor:

```bash
bd update AES-42 --status blocked
bd comments add AES-42 "Waiting on API team for endpoint spec"
# Issue won't appear in `bd ready` until unblocked
bd update AES-42 --status open  # Unblock when ready
```

## Reopening Closed Issues

```bash
bd reopen AES-42 --reason "Bug reappeared after deploy"
```

## During Execution

- Execute each item in logical order
- Create commits as work progresses (see Commits section below)
- **Verify before closing:** After implementing an item, run the verification steps from its Acceptance Criteria and Testing Strategy sections before marking it done. At minimum:
  1. Run the project's test suite (if tests exist)
  2. Run the type checker / linter (if applicable)
  3. Manually verify each Acceptance Criteria checklist item can be confirmed
  4. If any check fails, fix the issue before closing the item
- Close items only after verification passes
- If blocked, set status to `blocked` and add a comment explaining why

## Work Discovery

When you discover unrelated issues during execution (broken tests, bugs, tech debt), **capture them immediately** rather than ignoring:

```bash
bd create "Fix broken auth tests" --type bug --deps "discovered-from:<current-bead-id>"
bd create "Refactor duplicated validation logic" --type chore --deps "discovered-from:<current-bead-id>"
```

**`--deps "discovered-from:..."` is required for all bugs.** It traces the defect back to the item whose implementation introduced it. For features and chores, `discovered-from` linking is recommended but optional. (In bd 0.5 this was the `--discovered-from <id>` flag; 1.0 folded all dependency creation into the `--deps "type:id"` form.)

**Validate type matches description** before confirming with user:
- `bug`: fixes broken behavior ("Fix X", "X doesn't work", "X times out")
- `feature`: adds new capability ("Add X", "Implement X")
- `chore`: maintenance, no behavior change ("Clean up X", "Rename X", "Upgrade X")
- `decision`: investigates open question ("Investigate X", "Spike: X")
If the user says "create a chore" but it's fixing a failure, classify as `bug` and confirm.


## On Failure

If work fails:
1. Do not close the item
2. Add context via `bd comments add <id> "Error: [description]"`
3. Create follow-up items if needed
4. Seek user guidance before continuing

---

## Commits

When work results in code changes:

### Commit Message Style

Follow Conventional Commits format:

```
feat: add user login button
fix: resolve null pointer in auth handler
docs: update API documentation for auth endpoints
refactor: extract validation logic to shared module
```

### Link to Items

Reference the work item in commits when applicable:

```bash
git commit -m "feat: add login button

Closes: AES-42"
```

### Persist work-tracking state with the commit

`.beads/issues.jsonl` is the on-disk source of truth for beads — bd auto-exports each write to it. Stage the updated jsonl alongside your code so the work-tracking history travels with the change.

**Single write (interactive):**

```bash
bd update <id> --body-file <body.md>
```

In embedded mode (the default), each `bd update` / `bd label add` / `bd close` commits atomically.

**Batching 3+ writes from one process — two patterns, pick by operation type:**

- **Option A (per-call batch, below):** required when any write needs `--body-file`, label operations, `bd set-state`, or `bd comments add`. Each call commits to Dolt independently.
- **Option B (`bd batch` transaction, further below):** atomic and faster (one Dolt commit), but only supports `close`, `update <key>=<value>` (status/priority/title/assignee), `create`, `dep add/remove`.
- **Mixed writes:** use Option A for the body/label/state writes, then optionally Option B for the bulk close at the end.
- Both patterns require a final `bd export -o .beads/issues.jsonl` — neither auto-flushes jsonl after the last write.

**Option A — per-call batch:**

```bash
bd update <id1> --body-file <body1.md>
bd update <id2> --body-file <body2.md>
bd update <id3> --body-file <body3.md>
bd export -o .beads/issues.jsonl
```

Always run `bd export -o .beads/issues.jsonl` after an Option A batch. bd's per-write auto-export does not reliably flush sequential writes to jsonl — without the explicit export, writes stay in Dolt but are missing from the canonical jsonl.

**Option B — `bd batch` transaction:**

```bash
bd batch <<EOF
close bead-1 cleanup pass
close bead-2
update bead-3 status=in_progress priority=1
update bead-4 status=closed
dep add bead-5 bead-6
EOF
bd export -o .beads/issues.jsonl
```

- Use when writes are limited to close + update (status/priority/title/assignee) + dep changes. For body writes, label operations, `bd set-state`, or `bd comments add`, use Option A above (`bd batch` does NOT support those).
- Atomic: all entries commit together or the entire batch rolls back. A single bad ID (stale, already-closed, invalid status) fails the whole batch.
- `bd batch` does NOT auto-flush jsonl — always follow with `bd export -o .beads/issues.jsonl`.

**Concurrent writes (multiple processes, including subagent fan-out):**

Embedded mode is single-writer with file-lock enforcement. Concurrent `bd update` calls serialize behind the lock — they don't corrupt, they queue. After all writers complete, one final flush:

```bash
bd export -o .beads/issues.jsonl
```

This is reliable at small fan-out (3–5 concurrent writers). At larger fan-out (10+), per-write lock-waits effectively serialize the batch anyway — prefer the orchestrator-serializes pattern in `workflow-agents.md`.

**Commit and push:**

```bash
git add <specific-files> .beads/issues.jsonl
git commit -m "feat: [description]"
git push
```

> Always stage specific files. Avoid `git add .` — it can accidentally stage secrets, binaries, or temporary files.

> Pushing to a feature branch is ungated and proceeds under autonomy. `git push --force`, pushing to `main`/protected branches, and any `gh pr ...` operation are gated — see [Confirmation Gates](#confirmation-gates-publication-intent).

**Don't:**

- Write directly to `.beads/issues.jsonl`. Go through `bd update` / `bd label add` / `bd close` so bd validates and maintains its Dolt working set. (Reading a snapshot produced by `bd export` is fine — only writes are forbidden.)
- Use `bd sync`. Removed in bd 1.0; use `bd export -o .beads/issues.jsonl` for jsonl sync and `bd dolt push` for cross-machine sync.

> `bd show --json <id>` returns a list (single-element) in bd 1.0, not an object. Scripts that parse it must handle the list shape (`json.loads(out)[0]` or equivalent).

### Changelog

After completing a set of features, update `changelog.yaml`.

---

## Pull Requests

When the feature branch is ready for merge:

1. **Push the branch** (ungated — proceeds under autonomy):
   ```bash
   git push -u origin <branch-name>
   ```

2. **[GATE] Create PR using the project template:**
   ```bash
   gh pr create --title "<type>: <description>"
   ```
   See [Confirmation Gates](#confirmation-gates-publication-intent). At end-of-request, ask the user before running this command. Read `.github/PULL_REQUEST_TEMPLATE.md` and fill in all sections per `rules/pull-requests.md`. The `gh` CLI auto-populates the body from the template when it exists.

3. **[GATE] Subsequent commits to a branch with an open PR:** Push freely (ungated), but at end-of-request ask the user whether to update the PR title/body to reflect the new work. If approved, do a full template re-review per the [Post-PR updates procedure](#post-pr-updates-full-template-re-review).

4. **[GATE] Request human review:** After creating the PR, always request human review before merging. **NEVER merge PRs to main without explicit human approval.**

5. **[GATE] Merge:** Once approved, squash and merge to keep `main` history clean. Often the user does this via the GitHub UI; if you run `gh pr merge`, ask first.
   - Use `gh pr merge <num> --squash` — do NOT pass `--delete-branch`.
   - The remote feature branch must survive the merge as a permanent artifact of the PR (traceability, link from the merged PR's UI, easier rollback investigation).

6. **Post-merge branch cleanup:** After the merge lands on `main`, delete LOCAL only — keep the remote:
   ```bash
   git checkout main
   git pull origin main
   git branch -d <feature-branch>          # local only; -d (lowercase) refuses if unmerged
   # NEVER: git push origin --delete <feature-branch>
   # NEVER: gh pr merge --delete-branch
   ```
   The local branch is redundant once `main` has the squashed commit. The remote branch is the PR's permanent record — do not delete it.
