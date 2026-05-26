# Backend Reference

Purpose: Detailed backend context — API routes, service patterns, and conventions. Read [`architecture.md`](architecture.md) first for the high-level overview.

> This file grows as the project evolves. Start with the sections that apply and add detail as patterns emerge. Example blocks below are themed for the worked Asteroids example — swap each `<!-- theme example -->...<!-- /theme example -->` block with your project's actual values.

---

## API Routes

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
<!-- theme example -->
| GET    | `/health` | Liveness probe | No |
| POST   | `/api/v1/replays` | Submit a replay for validation | Yes |
| GET    | `/api/v1/replays/{id}` | Get replay validation status | Yes |
| GET    | `/api/v1/leaderboard/{wave_pack_version}` | Top N scores for a wave-pack | No |
| GET    | `/api/v1/shop/daily-deal` | Current daily-deal rotation | No |
| POST   | `/api/v1/shop/purchase` | Buy a power-up | Yes |
| GET    | `/api/v1/wave-packs` | List available wave-pack versions | No |
<!-- /theme example -->

---

## Service Pattern

Describe the standard pattern for services in your backend. The example below shows a route/service/worker split that keeps routes thin and business logic testable.

<!-- theme example -->
```
Routes        → orchestration only (validate input, call service, return response)
Services      → business logic + access control + DB operations
Validators    → request schema validation (pydantic)
Workers (ARQ) → async background work (replay validation pipeline)
Models        → SQLAlchemy entities + relationships
```
<!-- /theme example -->

---

## Conventions

<!-- theme example -->
- All routes use Conventional Commits in docstrings
- Services verify access (`current_user`) before any data operation; never trust route-layer checks alone
- Use `def` unless the function body contains `await`
- Pydantic v2 models for request/response; never reuse SQLAlchemy models as response schemas (leaks internal columns)
- Replay-validator workers are idempotent — same replay submitted twice produces the same result
<!-- /theme example -->

---

## Key Modules

| Module | Purpose | Key Files |
|--------|---------|-----------|
<!-- theme example -->
| `app/auth/` | Supabase OAuth verification | `dependencies.py`, `models.py` |
| `app/leaderboard/` | Leaderboard read/write + ranking | `service.py`, `routes.py` |
| `app/replay/` | Replay submission + validation orchestration | `service.py`, `workers.py` |
| `app/shop/` | Daily-deal rotation + purchase ledger | `rotation.py`, `service.py` |
| `app/wave_packs/` | Wave-pack manifest loading + versioning | `loader.py`, `versions.py` |
<!-- /theme example -->
