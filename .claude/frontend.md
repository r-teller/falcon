# Frontend Reference

Purpose: Detailed frontend context — pages, components, and conventions. Read [`architecture.md`](architecture.md) first for the high-level overview.

> This file grows as the project evolves. Start with the sections that apply and add detail as patterns emerge. The `<!-- theme example -->...<!-- /theme example -->` blocks below describe the Snake five-phase artifact at `examples/snake_opus.html` (Phase 1 shipped 2026-06-04). When adopting falcon for a different project, swap each block with that project's actual values.

---

## Pages

| Route | Page | Purpose |
|-------|------|---------|
<!-- theme example -->
The Snake artifact has no router and no multi-page concept — the entire UI is one HTML document loaded from disk. All "screens" are DOM overlay layers toggled by `state.runState` and `state.paused`:

| Layer | Element | Shown when |
|-------|---------|------------|
| Playfield | `<canvas id="game">` (640×480) | Always |
| HUD — score | `#hud-score` | Always |
| HUD — phase | `#hud-phase` | Always |
| HUD — reinforcements | `#hud-reinf` | Always (empty when `state.reinforcements === 0`) |
| HUD — bonuses slot | `#hud-bonus` | Always (placeholder until P2-04 / P3-05 / P4-06 populate held-bonus icons) |
| Pause overlay | `#overlay-pause` | `state.paused === true` (P/Esc) |
| Run-end overlay | `#overlay-lost` | `state.runState === 'patrol_lost'` |
| Phase transition banner | `#banner` | 2s after `transitionToPhase(n, name)` fires (CSS opacity transition) |
<!-- /theme example -->

---

## Component Patterns

Describe the standard component patterns. The example below shows a canvas + HUD + modal layout common to game UIs.

<!-- theme example -->
There are no components — the entire artifact is one inline `<script>` IIFE. Patterns to know:

- **Single `state` object** owns everything: phase, score, patrol segments, supply cache, runState, paused, tickRate, scavengerActive (Phase 2+ hook), midAmbushCut (Phase 3+ hook). Every helper reads/writes `state`; no module boundaries.
- **Phase-branched helpers** are the extension seam for Phase 2–5. Three helpers switch on `state.phase`: `palette()`, `recomputeTickRate()`, `checkPhaseGates()`. New phases add a branch; they do NOT rewrite the helper. `transitionToPhase(n, name)` is the generic gate handler reused by every phase transition.
- **Render every frame; tick when playing.** `loop(ts)` always calls `renderFrame()` + `renderHud()`. The tick advance is gated on `state.runState === 'playing'` AND `!state.paused`, so overlays/pauses keep drawing without the patrol moving.
- **DOM overlay over canvas (HUD pattern).** Score / phase / reinforcements / pause / PATROL LOST / phase-transition banner are all DOM divs absolutely-positioned over the canvas with `pointer-events: none`. Cheap to update, easy to style, doesn't interfere with `getContext('2d')` draws.
- **No frameworks, no event bus.** Direct DOM ID lookups (`document.getElementById('hud-score').textContent = …`). At this scale, a framework's overhead is pure cost.
- **Reversal protection: belt-and-braces.** Input handler rejects direct-opposite of `currentDirection` so it never lands in `pendingDirection`; `patrolStep()` also re-checks before committing. Either alone would suffice; both is cheap insurance against future regressions.
<!-- /theme example -->

---

## Conventions

<!-- theme example -->
- **Inline everything.** No `<script src>`, no `<link rel="stylesheet">`, no CDN URL, no image/audio asset reference. Verifiable via `grep -Eni 'src=|href=|@import|cdn|http' examples/snake_opus.html` returning zero matches.
- **Canonical copy strings are exact.** "PATROL LOST", "Press R to redeploy", "PHASE 1: NIGHT RECON", "PHASE 2: DAWN PATROL", "HOLD POSITION" — NOT "GAME OVER", NOT "Press R to restart", NOT "PAUSED". The PRD treats these as contract-bearing (§3.21, §13.5).
- **Phase-branched helpers extend by adding cases, not by rewriting.** A new phase's branch SHOULD NOT mutate other phases' branches. The first commit that violates this becomes a refactor target.
- **`Math.random()` IS allowed** (per PRD §18 — no determinism/replay requirement). This is the explicit opposite of the Asteroids example's deterministic-physics convention.
- **Grid-aligned movement only.** Patrol moves one cell per tick; no fractional positions. Render multiplies grid coords by `CELL` (20) to draw.
- **The "fairness invariants" in PRD §13.6 are non-negotiable.** Supply cache never spawns on patrol or bunkers; bonuses never spawn on bunkers or other bonuses; bunkers never spawn adjacent to patrol head at Phase 4 entry; wormholes are pair-distance ≥ 8 cells. Any code that violates one of these is a regression even if tests pass.
<!-- /theme example -->

---

## Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
<!-- theme example -->
There are no React components — the artifact is a single inline `<script>` IIFE. The closest analogue is the functional decomposition inside that IIFE:

| Function / region | Purpose | Owner bead |
|---|---|---|
| `palette()` | Phase-branched colour set (Phase 1 grayscale; Phase 2+ camo per §6.2 hex table) | P1-01 (extends in P2-01) |
| `recomputeTickRate()` | Score-driven speed ramp (6 → 8 cells/sec across 0..50 in Phase 1) | P1-03 (extends in P5-03) |
| `patrolReset()` / `patrolStep()` / `patrolGrow()` | Patrol data model — head-first segments, growth scheduling | FN-04 |
| `spawnSupplyCache()` / `patrolOccupies()` | Rejection-sampled cache spawn with patrol exclusion | FN-05 (extends in P4-05 for bunker exclusion) |
| `checkCollisions()` | Wall + self collision → returns `'wall'` / `'self'` / `null` | P1-02 |
| `checkPhaseGates()` + `transitionToPhase()` | Score-threshold gate detection + 2s banner + tick-rate re-baseline | P1-04 (extends in P2-05, P3-07, P4-07) |
| `showBanner()` | 2s fade-in/out phase-transition banner (CSS opacity transition) | P1-04 (FIN-01 may generalize) |
| `renderFrame()` | Canvas clear → grid → cache → patrol body → patrol head with directional notch | FN-01 + P1-01 + FN-04 + FN-05 |
| `renderHud()` | DOM updates: score / phase / reinforcements chevrons / overlay visibility toggles | FN-06 |
| `losePatrol()` / `redeploy()` | Run-end overlay (canonical copy strings as constants) + Phase-1 fresh start | FN-08 |
| `loop(ts)` | Main rAF loop with fixed-tick accumulator, dt cap, render-always pattern | FN-02 |
| keydown handler | DIR_KEYS table for Arrows + WASD + isOpposite rejection, P/Esc pause, R/Space gated on `patrol_lost` | FN-03 + FN-07 + FN-08 |
<!-- /theme example -->
