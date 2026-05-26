# Workflow: Agents and Testing

Purpose: Multi-agent coordination, Playwright testing conventions, and agent-assisted workflows.

> **Terminology for this project:**
> "Work item" / "item" / "issue" throughout this file refers to a **bead** — managed via the beads (`bd`) CLI.

Use this file when **coordinating multiple agents** on the same project, running
**Playwright tests** for UI verification, or deciding when to suggest agent-
assisted workflows (`/scribe`, `/quartermaster`). This file is not needed for
single-agent sessions doing standard implementation work.

---

## Multi-Agent Coordination (Optional)

When running multiple agents on the same project, use these flags to prevent conflicts and maintain audit trails.

### Actor Tracking

Tag updates with an actor identifier for audit trails:

```bash
bd update AES-42 --status in_progress --actor "claude-session-1"
bd close AES-42 --actor "claude-session-1"
```

This logs who/what made each change, useful for debugging and history.

### Assignee Management

Claim work to prevent other agents from picking it up:

```bash
# Claim atomically (sets assignee + status=in_progress in one shot)
bd update AES-42 --claim --assignee "agent-1"

# See what's assigned to a specific agent
bd list --assignee "agent-1"

# Find unclaimed ready work
bd ready --unassigned
```

### Multi-Agent Workflow

1. On startup, check for unclaimed work: `bd ready --unassigned`
2. Claim atomically: `bd update <id> --claim --assignee "<agent-id>"`
3. Tag all updates with `--actor` for traceability
4. On completion, close with actor: `bd close <id> --actor "<agent-id>"`
5. After a batch of claims/closes, flush jsonl: `bd export -o .beads/issues.jsonl`

### Multi-subagent fan-out

When you fan out work to multiple subagents, split roles along read/write lines. Subagents READ bd state freely (concurrent reads are safe); the orchestrator handles WRITES (concurrent writers work but lock-wait at scale).

**Shared reads at scale (>10 reads):**

Pre-export bd state once, then have subagents read from the snapshot file rather than calling `bd show` per item:

```bash
# Orchestrator, before fan-out:
bd export -o /tmp/beads-snapshot.jsonl

# Subagent prompt:
#   "Parse /tmp/beads-snapshot.jsonl for bead <id>, emit findings to /tmp/work-<id>.json."
```

This avoids per-call bd CLI overhead. The same pattern works for any bulk read of structured project data — snapshot once, parse in-memory, iterate.

**Direct reads at small scale (<10):**

Subagents may call `bd show --json <id>` directly — concurrent reads are safe, no lock contention.

**Writes — orchestrator-serializes (preferred):**

Subagents emit structured artifacts (JSON or YAML files in `/tmp/`); the orchestrator collects them and applies all writes sequentially:

```bash
for f in /tmp/work-*.json; do
  bd update <id> --body-file <body>
done
bd export -o .beads/issues.jsonl
```

One coordinator means one failure surface, easier retry, and the final flush lives in an obvious place.

**Writes — subagents-write (acceptable at 3–5 concurrent):**

If subagents must write themselves, the embedded-mode file lock serializes them — works correctly, but offers no time savings vs. orchestrator-serializes at scale:

```bash
# Each subagent runs bd update / bd label add in parallel
# Orchestrator MUST end with:
bd export -o .beads/issues.jsonl
```

At 10+ concurrent subagent writers, the lock queue eliminates any parallelism benefit; use orchestrator-serializes instead.

> `--actor` is an audit field, not a coordination mechanism. It does NOT lock the row or prevent races. Don't use it as a write barrier.

> Never skip the final `bd export` after any concurrent or batch write. jsonl will reflect only the last write to land, even though Dolt itself is correct.

---

## Playwright Testing

When testing features with Playwright, follow these conventions for traceability:

### Screenshot Naming Convention

Include the work item ID (or short slug) in screenshot filenames to track screenshots back to specific work:

```
<item-id-or-slug>-<description>.png
```

Examples:
- `AES-42-menu-screen.png`
- `AES-43-ship-controls.png`
- `auth-flow-login-success.png` (when no formal ID exists, use a stable slug)

### Testing Workflow

1. **Before testing:** Ensure the dev server is running
2. **Install browser if needed:** Use `browser_install` tool
3. **Navigate to app:** Use `browser_navigate` to load the application
4. **Take baseline screenshot:** Capture initial state with work item ID (or slug) prefix
5. **Test interactions:** Use keyboard/mouse tools to test functionality
6. **Capture results:** Screenshot each significant state change
7. **Close browser:** Clean up with `browser_close` when done

### Screenshot Storage

Screenshots are saved to `.playwright-mcp/` directory. Consider:
- Adding `.playwright-mcp/` to `.gitignore` for temporary test screenshots
- Moving important screenshots to a `docs/` or `tests/screenshots/` folder if they should be preserved

---

## Agent-Assisted Workflows

When working on complex tasks, suggest and use these agent systems to improve planning and execution quality.
All agent workflows track work through beads.

### When to Suggest Scribe (`/scribe`)

Suggest `/scribe` when the user needs to:
- **Set up a new project** → `/scribe setup` (populates templates, initializes beads)
- **Draft requirements** → `/scribe draft PRD for [feature]` (creates PRD + backlog items)
- **Create executive summaries** → `/scribe brief about [topic]` (two-page decision memos)
- **Run a planning session** → `/scribe plan [topic]` (facilitates goals, constraints, next steps — all tracked as beads issues)

### When to Suggest Quartermaster (`/quartermaster`)

Suggest `/quartermaster` when the user needs to:
- **Prioritize work** → `/quartermaster review backlog` (analyzes beads, recommends next items)
- **Integrate a new feature** → `/quartermaster add [feature]` (architectural fit analysis)
- **Assess code health** → `/quartermaster review tech` (gaps, tech debt, security concerns)
- **Approve and execute plans** → `/quartermaster coordinate` (structured handoff to Scribe for beads creation)

### Agent Coordination Flow

1. Quartermaster analyzes and recommends (read-only)
2. When a plan is approved, Quartermaster coordinates with Scribe
3. Scribe executes all beads operations (`bd create`, `bd update`, `bd close`, `bd dep add`)
4. All work items are tracked as beads issues — no planning artifacts exist outside beads

### Recognition Triggers

Proactively suggest agents when you detect:
- New data models or schema changes → `/quartermaster`
- Cross-cutting concerns (auth, logging, caching) → `/quartermaster`
- External API integrations → `/quartermaster`
- Performance-sensitive operations → `/quartermaster`
- New feature requests needing structured PRD → `/scribe`
- Need for stakeholder communication → `/scribe brief`
- Session planning with multiple work items → `/scribe plan`
