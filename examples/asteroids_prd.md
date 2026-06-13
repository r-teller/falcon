# Asteroids: Wave Defense — Product Requirements Document

> **Example PRD** — a sample input for the [bootstrap workflow](../BOOTSTRAP.md). In a Claude Code session in this repo, run `Follow @BOOTSTRAP.md with my PRD @examples/asteroids_prd.md` (or paste the prompt block from BOOTSTRAP.md) to see how it hydrates `.claude/{architecture,backend,...}.md` and seeds initial beads. Matches the asteroid theme already threaded through the distribution's example content.

---

## 1. Vision

A modern reimagining of the classic Asteroids arcade game with wave-based progression, between-wave power-up shop economy, online co-op, replay-based leaderboards, and daily-challenge wave packs. The leaderboard is authenticated and replay-validated — every submitted score is re-run server-side against the canonical wave-pack content, so cheating requires breaking deterministic physics, not just spoofing a score.

## 2. Goals

- Single-player core experience parity with arcade Asteroids on day one (controls, feel, lethality curve)
- Authenticated leaderboards with server-validated replays
- Between-wave power-up shop economy (no real-money purchases at MVP)
- Daily-challenge wave packs that rotate without scoreboard-breaking content drift
- Co-op multiplayer prototype as a stretch goal (post-MVP)

## 3. Non-Goals

- Mobile-touch input (UX trade-off; keyboard + gamepad first)
- Pay-to-win cosmetics (damages the fair-play principle)
- User-generated wave packs (out of MVP scope; requires moderation tooling)
- Mod / scripting API (would compromise determinism contract)

## 4. Target Personas

| Persona | Description | Priority |
|---------|-------------|----------|
| Player | Plays for high scores; replays favorite waves; watches top players' replays | Primary |
| Leaderboard integrator | Builds Twitch/Discord bots that read leaderboard state via public API | Secondary |
| Server operator | Runs the leaderboard + replay-validator infrastructure | Secondary |

## 5. Tech Stack

- **Backend:** Python 3.12 — FastAPI 0.115 (leaderboard API) + ARQ workers (replay validation pipeline)
- **Frontend:** TypeScript 5.x — React 19 + Vite + Tailwind 3.4
- **Physics engine:** custom deterministic engine (Python; same engine runs in worker + WebAssembly-compiled in browser)
- **Auth:** Supabase Auth (Apple OAuth, Google OAuth, Steam OpenID)
- **Database:** PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- **Queue/Async:** Redis + ARQ
- **Storage:** S3 (replay artifacts + archived leaderboard snapshots)
- **Hosting:** GCP — Cloud Run (API) + GKE (replay-validator workers) + GCS for static assets

## 6. Major Subsystems

- **`physics-engine/`** — collision detection, velocity integration, broadphase. Deterministic; same seed + inputs = byte-identical outputs.
- **`renderer/`** — vector graphics + HUD + shop panel UI
- **`wave-spawner/`** — procedural wave generation per `wave_pack_version`
- **`score-tracker/`** — wave scoring + leaderboard sync
- **`replay-validator/`** — server-side replay re-run; the anti-cheat backbone
- **`power-up-shop/`** — daily-deal rotation + purchase ledger

## 7. Features (Phased)

### Phase 1 — Core gameplay loop (MVP)

- F1.1 Single-player game canvas with arcade-faithful controls (thrust, rotate, fire, hyperspace)
- F1.2 Wave-spawner: 5-wave demo pack with increasing asteroid density per wave
- F1.3 Score-tracker: in-game score display; persists locally for solo mode
- F1.4 Renderer: vector graphics + HUD (score, lives, current-wave, shield)
- F1.5 Game-over + restart flow

### Phase 2 — Authenticated leaderboards

- F2.1 Supabase Auth integration (Apple/Google/Steam OAuth)
- F2.2 Replay capture (deterministic input log + initial state) on every game session
- F2.3 Leaderboard API endpoints (`POST /replays`, `GET /leaderboard/<wave_pack_version>`)
- F2.4 Replay-validator worker — re-runs submitted replays against canonical wave-pack content; emits PASS/FAIL + canonical score
- F2.5 Leaderboard UI on frontend (top N per wave-pack, click-to-watch replay)

### Phase 3 — Shop economy

- F3.1 Power-up shop UI (modal between waves)
- F3.2 Daily-deal rotation (timezone-aware deterministic UTC-date hash)
- F3.3 Purchase ledger + idempotency
- F3.4 Owned-power-ups inventory (visible in profile page)
- F3.5 Power-up effects integrated into physics-engine (shield extension, multi-shot, etc.)

### Phase 4 — Daily challenge + community (stretch)

- F4.1 Daily wave-pack rotation (fresh wave every UTC day)
- F4.2 Daily-challenge leaderboard (24h window, expires)
- F4.3 Replay sharing (deep link to a specific replay)

### Phase 5 — Co-op multiplayer (post-MVP)

- F5.1 Netcode prototype (rollback or lockstep — see Open Question OQ-2)
- F5.2 2-player local co-op (shared screen)
- F5.3 2-player online co-op

## 8. Security & Anti-Cheat

- **Data sensitivity: PII** — player email (from OAuth), display name, replay artifacts, purchase history. GDPR-aligned handling globally.
- **Anti-cheat = replay validation.** Every leaderboard-bound replay is re-run by the validator against the canonical wave-pack content. Mismatched score = rejection. Tampered replay (bad signature) = rejection before validation starts.
- **Deterministic physics is non-negotiable.** A non-determinism regression invalidates historical replays. Determinism tests run on every PR.
- **No client-side score reporting** — score is computed by the validator during re-run; client only displays.

## 9. Testing Strategy

- **Unit tests** — `pytest` for backend + workers; `vitest` + React Testing Library for frontend
- **Integration tests** — leaderboard API + replay-validator pipeline end-to-end against real Postgres + Redis (no service-boundary mocks)
- **E2E** — Playwright tests for the critical journey: log in → play 1 wave → submit replay → poll for validation → confirm leaderboard entry
- **Determinism harness** — special category; same seed + same input sequence MUST produce byte-identical outputs. Runs 100x per fixture replay on every PR.
- **Coverage targets:** 80% for `replay-validator`, 60% elsewhere

## 10. Open Questions

- **OQ-1: Replay storage retention.** S3 lifecycle policy for replay artifacts — keep forever (cheap, archival) or expire after N days (cheaper)? Affects "watch any historical replay" UX.
- **OQ-2: Netcode strategy for Phase 5 co-op.** Rollback netcode (better feel, harder to implement, requires deterministic physics — which we already have) vs lockstep (simpler, higher latency). Decision spike.
- **OQ-3: Authentication providers.** Apple/Google/Steam at MVP. Should we also support email/password? Trade-off: friction vs. account-recovery complexity.
- **OQ-4: Wave-pack versioning UX.** When `wave_pack_version` bumps, do players' historical leaderboard positions stay or move to an archive? Lean toward archive (one canonical scoreboard per wave-pack-version, immutable post-bump).

## 11. Risks

- **Determinism regressions** — a single floating-point drift breaks all historical replays. Mitigation: determinism harness runs on every PR; pin Python version + math libraries.
- **Replay storage cost** — high-resolution replay artifacts are small (input log + initial state, not video), but scale matters. Mitigation: artifacts are ~20KB each; budget for 10M replays = 200GB ≈ $5/mo on S3.
- **Anti-cheat arms race** — sophisticated attackers might tamper with the deterministic engine in the browser. Mitigation: server-side re-run is the source of truth; browser score is display-only.
- **OAuth provider lock-in** — Supabase Auth bundles all three providers but creates a Supabase dependency. Mitigation: provider abstraction layer at the API boundary so we can swap if needed.

## 12. Roadmap

- **Phase 1 (MVP core):** weeks 1–4
- **Phase 2 (leaderboards):** weeks 5–8
- **Phase 3 (shop economy):** weeks 9–12
- **Phase 4 (daily challenges, stretch):** weeks 13–14
- **Phase 5 (co-op, post-MVP):** weeks 15+ — gated on OQ-2 resolution

## 13. Success Metrics (post-launch)

- **Engagement:** DAU/MAU ratio ≥ 0.25
- **Leaderboard integrity:** < 1% of submitted replays fail validation (anything higher signals either bugs or active attacks worth investigating)
- **Daily challenge participation:** > 30% of DAU play that day's challenge
- **Anti-cheat false-positive rate:** < 0.1% of legitimate replays mis-rejected

---

> When bootstrapping from this PRD, expect Phase 1 to become an epic with ~5 child beads, Phases 2-3 with ~5 each, Phases 4-5 with ~3 each (stretch + post-MVP), plus 4 decision/spike beads for OQ-1 through OQ-4.
