# Architecture Overview

Purpose: High-level system context for quick orientation. Answers: "What is this? How does it fit together? How do I run it?"

> This is the first file a new session should read. Keep it to one page of essentials. Detailed domain docs (`backend.md`, `frontend.md`, `data-model.md`) go deeper.

> **Theming note:** the `<!-- theme example -->...<!-- /theme example -->` blocks in this file describe THIS repo's current state — the Snake five-phase benchmark artifact at `examples/snake_opus.html` (Phase 1 shipped 2026-06-04; Phases 2–5 stubbed in beads). The blocks were updated in the wrapup pass on commit `40b35ad`'s successor. When adopting falcon for a different project, replace each block with that project's actual values.

---

## What We're Building

<!-- theme example -->
- **Project Name:** Snake — Evolving Five-Phase Field Operation (benchmark artifact for cross-model PRD evaluation; one of several example PRDs in `examples/`)
- **One-Sentence Summary:** A single-file browser Snake game styled as a field-ops patrol that escalates through five gated phases (Night Recon → Dawn Patrol → Ambush → Bunker Run → Sector Transfer), sharing one state machine, one persistent score, and one cohesive field-ops visual language.
- **Programming Languages:**
  - **Frontend (only):** Vanilla JavaScript (ES2020+) inline in HTML
- **Main Frameworks/Tools:**
  - **Rendering:** HTML5 Canvas 2D, flat geometric primitives only
  - **Game loop:** `requestAnimationFrame` + fixed-tick accumulator
  - **Build:** None (single self-contained `.html` file; no transpiler, no bundler, no CDN)
  - **Backend:** None — no server, no database, no network
- **Other example PRDs in the repo:** `examples/asteroids_prd.md` (more complex full-stack worked example used as the worked theme throughout the rest of this distribution's stub blocks below)
<!-- /theme example -->

---

## Product Guidance

### Vision

<!-- theme example -->
A self-contained, single-file browser Snake artifact built per `examples/snake_prd.md` as a benchmark for cross-model PRD-to-code evaluation. The aesthetic is field-ops / camouflage throughout; Phase 1 is grayscale night-recon, Phase 2+ unlocks the camo palette. Five gated phases stack mechanics on a single state machine — no jarring resets, no per-phase rewrites of physics. The benchmark goal: an adopter pastes `examples/snake_prd.md` §15 into N different coding models, names each output `snake_<model>.html`, and diffs the results.
<!-- /theme example -->

### Product Principles

<!-- theme example -->
1. **Single-file by construction** — the entire artifact is one `.html` file, inline HTML/CSS/JS, zero external dependencies. Verifiable by opening in any modern browser via double-click.
2. **Persistence is core** — score, patrol length, direction, reinforcements, upgrades, held bonuses all persist across phase gates. Only the world layer changes; the patrol is one entity through all five phases.
3. **Field-ops aesthetic is non-negotiable** — muted earth-tones (olive drab, coyote brown, tan, dark green, black) throughout. No neon, no saturated arcade hues, ever. Phase 1's grayscale is the only palette swap and it lifts at the Phase 2 gate as "dawn breaks."
<!-- /theme example -->

### Explicit Exclusions

| Excluded Feature | Rationale | Status |
|-----------------|-----------|--------|
<!-- theme example -->
| Backend / leaderboards / multiplayer | Violates single-file no-network constraint | Permanent |
| Audio / image assets | Cannot ship a separate `.wav` / `.mp3` / `.png` under the no-external-deps rule | Permanent |
| Mobile-touch input | Keyboard-first design (Arrows + WASD + P/Esc + R/Space + Shift); touch is a different UX problem | Deferred |
| Save / resume between sessions | Stateless by design; localStorage adds complexity for no benchmark value | Deferred |
| Full list of exclusions | See `examples/snake_prd.md` §17 — 16 explicit exclusions documented | — |
<!-- /theme example -->

### Target Personas

| Persona | Description | Priority |
|---------|-------------|----------|
<!-- theme example -->
| Player (end-user) | Plays the finished HTML file by double-click; wants familiar Snake feel + earned phase progression + no unfair deaths | Primary |
| Implementing Agent (coding model) | Builds from `examples/snake_prd.md` §15; wants enough specificity to build without guessing + enough latitude on visuals/tuning to express judgment | Primary |
| Adopter / Benchmark Operator | Runs the same PRD across multiple models; wants a repeatable prompt (§15) + consistent artifact name (§14) so outputs are diff-able | Secondary |
| Reviewer | Scores each model's artifact; wants AC (§13 and §5.5/§6.6/§7.6/§8.7/§9.9) phrased as checklist items a human tester can verify in one pass | Secondary |
<!-- /theme example -->

---

## Technology Decisions

Before adding a new library, check this table — the problem may already be solved.

| Category | Component | Version | Rationale |
|----------|-----------|---------|-----------|
<!-- theme example -->
| **Language** | JavaScript (ES2020+) | — | Inline in `examples/snake_opus.html`; no transpile step |
| **Rendering** | HTML5 Canvas 2D | (browser) | Flat geometric primitives (rect / line / circle); no sprites, no SVG |
| **Game loop** | `requestAnimationFrame` + fixed-tick accumulator | — | Decouples render rate from game tick; smooth at any monitor refresh |
| **Input** | DOM `keydown` on `window` | — | Arrows + WASD; reversal-protection rejects opposite-of-current heading |
| **HUD** | DOM overlay (`pointer-events: none`) | — | Score/phase/reinforcements/bonus rendered outside the canvas for cheap text updates |
| **Build tooling** | None | — | Single self-contained file by design (per `examples/snake_prd.md` §13.1) |
| **Backend / DB / queue / network** | None | — | All forbidden by single-file constraint |
| **Tooling (meta-repo)** | bd (beads) | 1.0.3 | Issue/work-item tracking; database in `.beads/` |
| **Tooling (meta-repo)** | falcon skill | 7.2.0 | Remote bead dispatch; rules in `.claude/skills/falcon/` + autopilot config at `.claude/rules/falcon-autopilot.md` |
<!-- /theme example -->

> **Update strategy:** Dependencies are updated manually. Before updating a major version, test the application. Run `npm audit` / `pip audit` periodically for security vulnerabilities.

---

## How to Run

### Prerequisites

<!-- theme example -->
- A modern browser (Chrome / Edge / Firefox / Safari) — that's it.
- For working on the beads / falcon tooling itself: `bd` 1.0.3+ on PATH, Node.js (only used opportunistically for `node --check` JS syntax validation of the artifact), Python 3 (for ad-hoc YAML validation).
<!-- /theme example -->

### Local Development

<!-- theme example -->
There is no dev server. To run the artifact:

```bash
# macOS
open examples/snake_opus.html
# Linux
xdg-open examples/snake_opus.html
# Or just double-click it in a file manager.
```

To work on the bead structure / refinement:

```bash
bd ready          # find unblocked work
bd show <id>      # read a bead body
bd update <id> --body-file <body.md>    # apply a refinement
bd close <id> -r "<reason>"             # close when verified
bd export -o .beads/issues.jsonl        # flush to canonical jsonl
```

To validate the artifact statically (no browser surface available):

```bash
# Extract <script> body and node-check it for syntax errors
awk '/<script>/{flag=1;next}/<\/script>/{flag=0}flag' examples/snake_opus.html > /tmp/snake_js.js \
  && node --check /tmp/snake_js.js

# No-external-deps audit
grep -Ein 'src=|href=|@import|<link|cdn|http://|https://' examples/snake_opus.html
# Expected: 0 matches.
```
<!-- /theme example -->

### Environment Health Checks

Used by `/leroy` to verify the dev environment is ready. Update this table when adding new services.

| Service | Check Command | Expected |
|---------|--------------|----------|
<!-- theme example -->
| Artifact file | `test -f examples/snake_opus.html && echo "exists"` | `exists` |
| JS syntax | `awk '/<script>/{f=1;next}/<\/script>/{f=0}f' examples/snake_opus.html > /tmp/_s.js && node --check /tmp/_s.js` | (no error output) |
| No external deps | `grep -cEin 'src=\|href=\|@import\|<link\|cdn\|http://\|https://' examples/snake_opus.html` | `0` |
| bd workspace | `bd where 2>&1 \| head -1` | (path under `.beads/`) |
| bd canonical jsonl | `test -f .beads/issues.jsonl && echo "exists"` | `exists` |
<!-- /theme example -->

---

## System Architecture

<!-- theme example -->
```
┌─────────────────────── examples/snake_opus.html ────────────────────────┐
│                                                                          │
│  ┌─── DOM layer ───────────────────────────────────────────────────┐    │
│  │  #stage > #game (canvas 640×480)  +  #hud-* overlays            │    │
│  │  #overlay-pause  +  #overlay-lost  +  #banner                    │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─── inline <script> (single IIFE) ───────────────────────────────┐    │
│  │  state {phase, score, patrol, supplyCache, runState, paused, …} │    │
│  │  loop(ts)                                                       │    │
│  │   ├── render: ctx clear → grid → cache → patrol                 │    │
│  │   └── advance tick @ 1000/tickRate ms while runState==='playing'│    │
│  │        ├── patrolStep() → checkCollisions() → losePatrol() ?    │    │
│  │        └── pickup check → score++ / grow → checkPhaseGates()    │    │
│  │                                                                  │    │
│  │  Phase-branched helpers (extend each phase):                    │    │
│  │   palette()           — colour set per state.phase               │    │
│  │   recomputeTickRate() — speed ramp formula per state.phase       │    │
│  │   transitionToPhase() — gate handler reused by P1→2, P2→3, …     │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ▲ keydown on window: arrows/WASD → pendingDirection                   │
│                       P/Esc → state.paused                              │
│                       R/Space (only at PATROL LOST) → redeploy()        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
   No backend. No DB. No network. No bundler. No build step. One file.
```

The "subsystems" in this artifact are not directories — they are PRD phases that stack on a shared state machine:

- **Phase 1 — Night Recon (§5):** grayscale palette, score 0→50, supply caches only
- **Phase 2 — Dawn Patrol (§6):** camo palette, field rations, Scavenger Training upgrade, score multiplier — gate at 150
- **Phase 3 — Ambush (§7):** hostile sweep events with telegraph + Cover bonus — gate at 350
- **Phase 4 — Bunker Run (§8):** static bunker obstacles with flood-fill connectivity + sprint boost — gate at 700
- **Phase 5 — Sector Transfer (§9):** open-ended sector progression via wormholes, escalating tempo + bunker density

Phase 1 is implemented as of 2026-06-04 (commit `328d642`). Phases 2–5 are stubbed in beads (SNAKE-8ik.*, -pi2.*, -juy.*, -401.*) — see `bd ready` for next available work.
<!-- /theme example -->

---

## Directory Structure

<!-- theme example -->
```
falcon/
├── examples/
│   ├── snake_prd.md         # canonical Snake PRD (the input to the benchmark)
│   ├── snake_opus.html      # this session's Snake artifact (Phase 1 shipped, Phase 2-5 in beads)
│   └── asteroids_prd.md     # second example PRD (no implementation yet)
├── .beads/                  # bd workspace (Dolt-backed)
│   ├── issues.jsonl         # canonical bead snapshot — committed
│   ├── bodies/*.md          # per-bead template-body sources (FN-01..FN-08, P1-*, P2-*)
│   ├── id_map.txt           # logical-id ↔ bd-id mapping
│   └── _*.sh                # single-use bead-setup scripts (UNTRACKED)
├── .claude/
│   ├── skills/falcon/       # falcon skill source (SKILL.md, COMMANDS.md, PROTOCOL.md, …)
│   ├── rules/               # workflow / planning / execution / autopilot rules
│   ├── docs/                # work-item templates, schemas
│   ├── architecture.md      # this file
│   ├── backend.md, frontend.md, data-model.md, tests.md, security.md, enhancements.md
│   ├── changelog.yaml
│   ├── handoff.yaml
│   └── standards-history.md
├── README.md
├── AGENTS.md                # bd-init-generated; pointer to bd prime
└── CLAUDE.md                # bd-init-generated; project instructions
```
<!-- /theme example -->

---

## Deployment

<!-- theme example -->
- **Hosting:** None — the artifact runs locally by opening the `.html` file in a browser. There is no server, no service, no environment.
- **Distribution:** The artifact + its PRD travel as files in this repo. An adopter copies `examples/snake_prd.md` §15 into a coding model, names the output per §14 (`snake_<model>.html`), and diffs against the canonical `examples/snake_opus.html`.
- **Local-only commit constraint (this branch):** session-scoped — `feature/work-20260603-2200-local-changes` does NOT push to a remote. See `.claude/handoff.yaml` for the durable note.
<!-- /theme example -->

---

## Related Context Files

For deeper detail, see:

- [`backend.md`](backend.md) — API routes, service patterns, backend conventions
- [`frontend.md`](frontend.md) — Pages, components, frontend conventions
- [`data-model.md`](data-model.md) — Database schema, entity relationships, migrations
- [`security.md`](security.md) — Auth, secrets, data sensitivity
- [`tests.md`](tests.md) — Testing strategy and frameworks
