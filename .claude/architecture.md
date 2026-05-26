# Architecture Overview

Purpose: High-level system context for quick orientation. Answers: "What is this? How does it fit together? How do I run it?"

> This is the first file a new session should read. Keep it to one page of essentials. Detailed domain docs (`backend.md`, `frontend.md`, `data-model.md`) go deeper.

> **Theming note:** the example blocks in this file are populated for the fictitious "Asteroids: Wave Defense" project used as the worked example throughout this distribution. Replace each `<!-- theme example -->...<!-- /theme example -->` block with your project's actual values when adopting falcon.

---

## What We're Building

<!-- theme example -->
- **Project Name:** Asteroids: Wave Defense
- **One-Sentence Summary:** A modern reimagining of the classic Asteroids arcade game with wave-based progression, between-wave power-up shop economy, online co-op, and replay leaderboards.
- **Programming Languages:**
  - **Backend:** Python 3.12
  - **Frontend:** TypeScript 5.x
- **Main Frameworks/Tools:**
  - **Backend:** FastAPI + SQLAlchemy + Alembic
  - **Frontend:** React 19 + Vite + Tailwind
  - **Auth:** Supabase Auth (Apple/Google/Steam OAuth)
  - **Database:** PostgreSQL 16
  - **Queue/Async:** Redis + ARQ (replay validation pipeline)
  - **Storage:** S3 (replay artifacts + leaderboard archives)
<!-- /theme example -->

---

## Product Guidance

### Vision

<!-- theme example -->
A modern Asteroids that respects the source material while layering a between-wave economy and authenticated leaderboards. Single-player first; co-op as a stretch goal. Wave-pack content is versioned so leaderboards stay fair across content updates.
<!-- /theme example -->

### Product Principles

<!-- theme example -->
1. **Replay-first** — every leaderboard submission is a deterministic replay that re-runs against the canonical `wave_pack_version`. No replay = no score.
2. **Fair-play by construction** — anti-cheat is structural (deterministic physics + server-side replay validation), not behavioral (signal-based detection).
3. **Content versioning is contractual** — `wave_pack_version` bumps are scoreboard-breaking events. Old replays remain valid against old versions; new versions get new leaderboard tracks.
<!-- /theme example -->

### Explicit Exclusions

| Excluded Feature | Rationale | Status |
|-----------------|-----------|--------|
<!-- theme example -->
| Pay-to-win cosmetics | Damages the fair-play principle | Permanent |
| Mobile-touch input | UX trade-off — keyboard/gamepad first | Deferred |
| User-generated wave packs | Out of MVP scope; requires moderation tooling | Deferred |
<!-- /theme example -->

### Target Personas

| Persona | Description | Priority |
|---------|-------------|----------|
<!-- theme example -->
| Player (end-user) | Plays for high scores, replays favorite waves | Primary |
| Leaderboard integrator (api-consumer) | Builds 3rd-party Twitch/Discord bots reading leaderboards | Secondary |
| Server operator (administrator) | Runs the replay-validator + leaderboard service | Secondary |
<!-- /theme example -->

---

## Technology Decisions

Before adding a new library, check this table — the problem may already be solved.

| Category | Component | Version | Rationale |
|----------|-----------|---------|-----------|
<!-- theme example -->
| **Language** | Python | 3.12 | Replay-validator + scoring service |
| **Language** | TypeScript | 5.x | Renderer + HUD + shop UI |
| **Runtime** | Node.js | 22.x | Frontend tooling |
| **Framework** | FastAPI | 0.115 | Leaderboard API |
| **Database** | PostgreSQL | 16 | Leaderboards + user accounts |
| **ORM** | SQLAlchemy | 2.0 | Type-safe queries |
| **UI Library** | React | 19 | HUD + shop panels |
| **Styling** | Tailwind | 3.4 | Quick utility-first styling |
| **Physics** | Custom (deterministic) | — | Required for replay reproducibility |
<!-- /theme example -->

> **Update strategy:** Dependencies are updated manually. Before updating a major version, test the application. Run `npm audit` / `pip audit` periodically for security vulnerabilities.

---

## How to Run

### Prerequisites

<!-- theme example -->
- Docker, Node.js 22+, Python 3.12+
<!-- /theme example -->

### Local Development

<!-- theme example -->
```bash
# Install deps
npm install && cd backend && pip install -r requirements.txt

# Start services
docker-compose up -d  # postgres + redis + minio

# Start backend (leaderboard + replay-validator)
cd backend && uvicorn app.main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev
```

- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
<!-- /theme example -->

### Environment Health Checks

Used by `/leroy` to verify the dev environment is ready. Update this table when adding new services.

| Service | Check Command | Expected |
|---------|--------------|----------|
<!-- theme example -->
| Backend | `curl -s http://localhost:8000/health` | `{"status": "healthy"}` |
| Frontend | `curl -s http://localhost:5173 >/dev/null && echo "running"` | `running` |
| Database | `docker ps --format "{{.Names}} {{.Status}}" \| grep postgres` | `Up ... (healthy)` |
| Redis | `docker ps --format "{{.Names}} {{.Status}}" \| grep redis` | `Up ... (healthy)` |
| .env | `test -f backend/.env && echo "exists"` | `exists` |
<!-- /theme example -->

---

## System Architecture

<!-- theme example -->
```
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│  Renderer    │───▶│  Leaderboard API │───▶│  PostgreSQL  │
│  (TS/React)  │    │  (FastAPI)       │    │              │
└──────────────┘    └────────┬─────────┘    └──────────────┘
                             │
                    ┌────────▼─────────┐    ┌──────────────┐
                    │ Replay Validator │───▶│  S3 (MinIO)  │
                    │ (ARQ workers)    │    │  replay/*    │
                    └──────────────────┘    └──────────────┘
```

Subsystems map to top-level directories:

- `physics-engine/` — deterministic collision + velocity
- `renderer/` — vector graphics, HUD
- `wave-spawner/` — procedural waves per `wave_pack_version`
- `score-tracker/` — wave scoring + leaderboard sync
- `replay-validator/` — replay verification pipeline
- `power-up-shop/` — between-wave shop economy
<!-- /theme example -->

---

## Directory Structure

<!-- theme example -->
```
asteroid-wave-defense/
├── physics-engine/          # collision, velocity, broadphase
├── renderer/                # vector renderer + HUD + shop panel
├── wave-spawner/            # procedural wave generation
├── score-tracker/           # scoring + leaderboard sync
│   └── waves/               # wave-pack YAML manifests
├── replay-validator/        # ARQ workers; replay re-run pipeline
├── power-up-shop/           # daily-deal rotation, purchases
├── docs/
│   └── level-designs/       # wave-pack source + sample replays
└── .claude/                 # this directory
```
<!-- /theme example -->

---

## Deployment

<!-- theme example -->
- **Hosting:** GCP (Cloud Run for API, GKE for replay-validator workers)
- **CI/CD:** GitHub Actions
- **Environments:** local · staging · production
- **Secrets:** GCP Secret Manager (production) · `.env` files (local, gitignored)
<!-- /theme example -->

---

## Related Context Files

For deeper detail, see:

- [`backend.md`](backend.md) — API routes, service patterns, backend conventions
- [`frontend.md`](frontend.md) — Pages, components, frontend conventions
- [`data-model.md`](data-model.md) — Database schema, entity relationships, migrations
- [`security.md`](security.md) — Auth, secrets, data sensitivity
- [`tests.md`](tests.md) — Testing strategy and frameworks
