# Data Model Reference

Purpose: Database schema, entity relationships, and migration conventions. Read [`architecture.md`](architecture.md) first for the high-level overview.

> This file grows as the project evolves. Update it when adding models or changing relationships. Example blocks below are themed for the worked Asteroids example — swap each `<!-- theme example -->...<!-- /theme example -->` block with your project's actual schema.

---

## Entity Relationship Overview

<!-- theme example -->
```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Player  │────▶│   Replay     │────▶│  WavePack    │
└──────────┘     └──────┬───────┘     └──────────────┘
      │                 │
      │          ┌──────▼───────┐
      │          │ ReplayResult │
      │          └──────┬───────┘
      │                 │
      │          ┌──────▼───────┐
      └─────────▶│  Leaderboard │
                 │    Entry     │
                 └──────────────┘

┌──────────┐     ┌──────────────┐
│  Player  │────▶│  Purchase    │────▶  PowerUp roster
└──────────┘     └──────────────┘      (in wave-pack manifest)
```
<!-- /theme example -->

---

## Models

| Model | Table | Purpose | Key Relationships |
|-------|-------|---------|-------------------|
<!-- theme example -->
| `Player` | `players` | Authenticated identity (OAuth-linked) | has_many: replays, purchases |
| `Replay` | `replays` | Submitted replay artifact + metadata | belongs_to: player, wave_pack; has_one: replay_result |
| `ReplayResult` | `replay_results` | Validator output (PASS/FAIL + canonical score) | belongs_to: replay |
| `WavePack` | `wave_packs` | Versioned content bundle (waves, asteroids, bosses) | has_many: replays, leaderboard_entries |
| `LeaderboardEntry` | `leaderboard_entries` | Materialized top-N per `wave_pack_version` | belongs_to: player, wave_pack |
| `Purchase` | `purchases` | Power-up purchase ledger | belongs_to: player |
<!-- /theme example -->

---

## Enums

| Enum | Values | Used By |
|------|--------|---------|
<!-- theme example -->
| `ReplayStatus` | `pending`, `validating`, `passed`, `failed`, `expired` | `Replay.status` |
| `FailReason` | `desync`, `version_mismatch`, `invalid_signature`, `timeout` | `ReplayResult.fail_reason` |
| `PurchaseSource` | `daily_deal`, `bundle`, `gift` | `Purchase.source` |
<!-- /theme example -->

---

## Migration Conventions

<!-- theme example -->
- Alembic autogenerate; review the generated SQL before applying
- Every `up` must have a reversible `down`
- Never rename columns — add new, migrate data via separate commit, drop old in a third commit
- Enum additions require a separate commit before any code uses the new value (PostgreSQL limitation)
- Wave-pack schema migrations require a `wave_pack_version` bump (per `development-standards.md` §3.17 if defined)
<!-- /theme example -->

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
<!-- theme example -->
| Soft deletes | `deleted_at` timestamp on `Player` only | Audit trail for player data; replays + scores are append-only |
| UUID primary keys | `uuid4` for all entities | No sequential ID leakage; URL-safe |
| Replay storage | S3 (artifact) + DB (metadata) | Large blobs in object store, fast queries in Postgres |
| Leaderboard materialization | Periodic refresh, not realtime | Decouples scoring throughput from query latency |
| Wave-pack versioning | Content-addressed hash + semver tag | Replays pin to a specific hash; semver is human-facing |
<!-- /theme example -->
