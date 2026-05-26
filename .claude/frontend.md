# Frontend Reference

Purpose: Detailed frontend context — pages, components, and conventions. Read [`architecture.md`](architecture.md) first for the high-level overview.

> This file grows as the project evolves. Start with the sections that apply and add detail as patterns emerge. Example blocks below are themed for the worked Asteroids example — swap each `<!-- theme example -->...<!-- /theme example -->` block with your project's actual values.

---

## Pages

| Route | Page | Purpose |
|-------|------|---------|
<!-- theme example -->
| `/` | Title screen | Start new game, load replay, view leaderboards |
| `/play/:wavePackVersion` | Game canvas | Renderer + HUD + power-up purchases between waves |
| `/leaderboard/:wavePackVersion` | Leaderboard | Top N scores; click a row to play the replay |
| `/replay/:replayId` | Replay viewer | Deterministic re-run of a submitted replay |
| `/shop` | Power-up shop | Daily-deal rotation + purchase history |
| `/profile` | Player profile | Account settings, OAuth links, owned power-ups |
<!-- /theme example -->

---

## Component Patterns

Describe the standard component patterns. The example below shows a canvas + HUD + modal layout common to game UIs.

<!-- theme example -->
- **Game canvas:** single `<GameCanvas>` component owns the renderer + physics-engine; subscribes to deterministic tick events
- **HUD layer:** floats above the canvas as portal-rendered components (radar, score, shield, current-wave indicator)
- **Modal pattern:** `<PowerUpShopModal>` opens between waves; closes on purchase OR skip
- **Form pattern:** Zod schemas for client-side validation, mirrors the backend's pydantic schemas
- **State management:** Zustand for game state (renderer, HUD); React Query for server state (leaderboard, shop)
- **Error handling:** `useToast()` for transient errors; full-page error boundary for renderer crashes
<!-- /theme example -->

---

## Conventions

<!-- theme example -->
- Components handle loading, empty, and error states explicitly — no silent failures
- API calls go through `src/services/api.ts`, never directly in components
- All user-facing text is i18n-ready (using i18n keys even if only English ships at MVP)
- Renderer code is deterministic — no `Math.random()`; use the seeded RNG from `physics-engine`
<!-- /theme example -->

---

## Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
<!-- theme example -->
| `GameCanvas` | Owns the renderer + physics tick loop | `src/components/game/` |
| `HUD` | Radar, score, shield, wave indicator | `src/components/hud/` |
| `PowerUpShopModal` | Between-wave shop UI | `src/components/shop/` |
| `LeaderboardTable` | Sortable + filterable score table | `src/components/leaderboard/` |
| `ReplayViewer` | Replay playback controls + scrubber | `src/components/replay/` |
<!-- /theme example -->
