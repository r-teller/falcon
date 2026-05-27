---
name: falcon
description: Falcon — generate a self-contained prompt that ships a bead set to a remote session for autonomous work, returning a structured report this session can feed straight into /wrapup
tier: dispatch
version: 7.1.1
created: 2026-05-21
allowed-tools: Read, Bash, Write
---

## Falcon — Remote Bead Dispatch

> Version history: see [`changelog.md`](./changelog.md)
> CLI surface (commands + flags + examples): see [`COMMANDS.md`](./COMMANDS.md)
> Full lifecycle protocol: see [`PROTOCOL.md`](./PROTOCOL.md)
> Schemas + templates: see [`REFERENCE.md`](./REFERENCE.md)

`/falcon` emits a self-contained prompt for a **different agent session** to work a specified set of beads end-to-end (claim → implement → test → commit → close), then return a structured report this session uses to update `changelog.yaml` + `handoff.yaml` at `/wrapup` time.

**Use this when:**
- You want to maximize context budget by offloading bead execution to a separate session
- The bead set is well-scoped (this session already knows what should happen)
- You plan to invoke falcon multiple times before wrapping up

**Do NOT use when:**
- The work needs your active steering (use `/leroy` or work directly instead)
- The beads are not yet `triage:ready` (refine here first)
- The work crosses major architectural decisions (those should stay in the steering session)

---

## Branch Ownership

The steering session OWNS branch creation. Before emitting the dispatch, this session either:
- Confirms the user is on a feature branch (`git rev-parse --abbrev-ref HEAD` returns non-`main`), pushes upstream if not yet pushed
- Or asks the user for a branch name, creates it (`git checkout -b feature/...`), and pushes upstream (`git push -u origin <branch>`)

The dispatch file embeds the literal branch name and instructs the worker to checkout-and-verify, not invent. This keeps all falcon dispatches against the same branch landing in a coherent commit history.

All workers (including multi-worker parallel dispatches) operate on the same branch. Workers commit + pull-rebase + push individually. The PR is opened by the steering session AFTER all workers complete and steering has validated their reports. Workers never open PRs themselves.

---

## Dispatch Protocol Overview

Falcon writes a per-dispatch YAML file at `.claude/tmp/falcon-dispatch-<6hex>.yaml`. The worker session receives a short "load `<path>` and execute" prompt (or a paste block if `--paste`); reads the dispatch file; runs through the lifecycle; writes intent + results back into the file. Steering reads results from the file at validation time.

Cross-dispatch file-scope locking via the session JSON `falcon_dispatches[]` array (cross-session aggregation) prevents two workers from claiming the same files. HARD reject on file/directory conflict at dispatch time.

**Assumes shared filesystem AND shared branch** between steering and all workers. For workers on a different machine/browser/cross-network, use `--paste` flag.

Lifecycle: **branch verify → bead lookup → intent-confirm → claim → implement → verify → commit + push → close → report.**

For step-by-step detail on each phase: see [`PROTOCOL.md`](./PROTOCOL.md).
For commands and flags: see [`COMMANDS.md`](./COMMANDS.md).
For schemas and templates: see [`REFERENCE.md`](./REFERENCE.md).

---

## What This Session Does Next

After validating and stashing the report:

- Each report contributes to `.claude/tmp/falcon-reports-<sanitized-branch>.yaml`
- High-stakes DARs surface immediately for arbitration
- Out-of-band closures stay open with a documented closure command
- Low-stakes DARs accumulate for retro

At `/wrapup`, this session reads the stashed file (one per branch) and synthesizes:
- **Changelog entry:** union of `changelog_seed.focus`, joined `one_line_summary`s, beads list, merged `area_changes`
- **Handoff entry:** `completed` (closed beads), `discovered` (discovered_beads), `in_progress` (outcome=in_progress beads), `blockers` (blockers_for_steering_session), `next_steps` (union of recommended_next_steps), `commits` (union), `epic_progress` (last delta wins per epic across reports)
- **Enhancements:** append each `enhancements[]` entry with provenance to `.claude/enhancements.md`
- **Standards firings:** append to `.claude/standards-history.md` if any
- **Decisions log:** if the project tracks decisions outside beads, append `decisions_for_human[]` summary

The wrapup skill should check for `.claude/tmp/falcon-reports-<sanitized-branch>.yaml` early in its flow and switch to "synthesis mode" if present, so it draws from the stashed report instead of reconstructing from raw git/bd state.

---

## Protocol Notes (cross-cutting)

- **File scope: files + directories only** — no glob patterns. Two beads touching different files within the same directory cannot run in parallel; must serialize OR consolidate into a single multi-bead dispatch.
- **Inline intent emission at intent-confirm pause** — worker emits the intent paragraph(s) verbatim in chat output (alongside the file write), so the human reads + acks directly in the worker session without bouncing to the orchestrator. Same pattern applies to short completion preambles.
- **Intent-confirm approach sentence** — the intent paragraph includes one sentence on implementation strategy (programmatic vs fan-out, direct-edit vs script-mediated, etc.). Not a plan; just enough to catch strategy surprises before any work starts.
- **Auto-release when safe; manual escape hatch** — Step 4 auto-releases the lock when the safe-to-release predicate holds (validation clean + cognitive audit clean + no unresolved DARs + no amendments queued). The user's natural action — pasting worker completion into steering — triggers it; no separate command required. `/falcon release <id>` remains available as a manual escape hatch.
- **Content hash as completion signal** — `implementation_results_hash: sha256(raw_string_as_written.encode('utf-8'))` replaces the `results_complete: true` boolean sentinel. Hash mismatch = partial write; steering rejects before parsing. Hash must be computed on the raw string as written — NOT any normalized form.
- **Cognitive audit (Step 3b)** — after mechanical validation, steering asks "is there a project-binding concern the AC didn't gate on?" Project-specific per-bead-type validation hints live in the project's rule or doc files (e.g., `.claude/docs/work-item-templates.md` or `.claude/rules/validation-hints.md`), NOT in falcon. Must document "no concerns found" if nothing surfaces.
- **`session_status` field** — dispatch file carries `active | amendments_pending | complete` (set by steering). Worker checks on each resume prompt to know if its session is still live.
- **Amendments dead-worker constraint** — amendments require the worker session to still be alive. If worker closed, re-dispatch as a new bead. Do NOT write amendments expecting a dead session to pick them up.
- **Pre-dispatch grep audit (Step 1b) + worker pre-intent grep verification** are belt-and-suspenders for the file_scope completeness problem. Migration/rename beads should run grep at BOTH dispatch time (steering) AND pre-intent (worker).
- **Project-specific rules** are NOT inlined in the dispatch — the worker reads `.claude/rules/*.md`, any root `CLAUDE.md`, and `.claude/standards-history.md` directly. This keeps falcon project-agnostic.
- **Workers never open PRs.** The steering session owns PR creation after all dispatched workers complete + steering has validated their reports.
- **Background-agent limitation** — the Agent tool surface is NOT available to a background general-purpose agent that itself spawns sub-agents. Workaround: `claude --print` subprocess fan-out.
