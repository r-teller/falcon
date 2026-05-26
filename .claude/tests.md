# Testing Strategy

Purpose: This file outlines the strategy for testing the application to ensure it works correctly and prevent future bugs.

> This file explains how we'll test the application to make sure it works correctly and doesn't break when we make changes. A good testing plan gives us confidence to build and release new features.
>
> Example blocks below are themed for the worked Asteroids example — swap each `<!-- theme example -->...<!-- /theme example -->` block with your project's actual testing approach.

---

## 1. Our Testing Philosophy

> What is our main goal for testing? We don't need to test every single line of code. Let's define what's most important.

- **Overall Goal:** [e.g., Ensure the most critical user journeys always work, Achieve 80% code coverage, Prevent regressions]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **Overall Goal:** Guarantee the critical player journey (start → play → submit replay → see score on leaderboard) always works, AND guarantee deterministic physics (the foundation of the anti-cheat system).
  The deterministic-physics guarantee is non-negotiable — a single non-determinism regression invalidates all historical replays. Tests around physics, RNG seeding, and replay re-run get the most scrutiny.
<!-- /theme example -->

---

## 2. Types of Tests We Will Write

> Different kinds of tests check different things. Here's a quick breakdown of what we'll use.

- **Unit Tests:** [Do we write these? What do they test? e.g., Yes, for individual functions and UI components in isolation.]
- **Integration Tests:** [Do we write these? What do they test? e.g., Yes, to check if our UI components correctly fetch data from the backend.]
- **End-to-End (E2E) Tests:** [Do we write these? What do they test? e.g., No, not at this stage. OR Yes, to simulate a full user journey in a real browser.]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **Unit tests:** Yes — individual functions in `physics-engine/`, `score-tracker/`, `replay-validator/`, and React components in isolation.
  **Integration tests:** Yes — leaderboard API + replay-validator pipeline end-to-end, hitting a real Postgres + Redis (no mocks at the service boundary).
  **End-to-end (E2E) tests:** Yes — Playwright tests for the critical journey: log in → play 1 wave → submit replay → poll for validation → confirm leaderboard entry.
  **Determinism tests:** Yes — special category. Same seed + same inputs MUST produce byte-identical outputs across runs. Run on every PR.
<!-- /theme example -->

---

## 3. Testing Frameworks & Tools

> What software will we use to write and run our tests?

- **Main Testing Tool(s):** [e.g., pytest, Jest, React Testing Library, Cypress]
- **How to Run Tests (Command):** [e.g., `pytest`, `npm test`, `npm run cypress:open`]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **Python (backend + workers):** `pytest` + `pytest-asyncio`. Coverage via `coverage.py` (target: 80% for `replay-validator`, 60% elsewhere).
  **TypeScript (frontend):** `vitest` + React Testing Library for unit/component; Playwright for E2E.
  **Determinism harness:** custom — `tests/determinism/run.py` runs each fixture replay 100x and asserts byte-identical outputs.

  **How to run tests:**

  ```bash
  # All backend tests
  cd backend && pytest

  # All frontend tests
  cd frontend && npm test

  # E2E (requires services running)
  cd frontend && npm run e2e

  # Determinism (slow; runs on PR via CI)
  cd backend && python tests/determinism/run.py
  ```
<!-- /theme example -->

---

## 4. Key Test Scenarios

> Let's list the most important user actions that absolutely must work. This helps us prioritize what to test first. Think back to the product goals in `architecture.md` and the acceptance criteria in your beads.

- **Scenario 1:** [e.g., A user should be able to log in with correct credentials.]
- **Scenario 2:** [e.g., A user should see an error if they try to log in with the wrong password.]
- **Scenario 3:** [e.g., A logged-in user should be able to create a new item.]

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  **Scenario 1 — Critical journey:** A player can log in (OAuth), start a game, complete one wave, submit the replay, and see their score land on the leaderboard within 30s.
  **Scenario 2 — Determinism:** Given the same seed + same input sequence, the physics engine produces byte-identical asteroid positions over a 5-minute simulated game.
  **Scenario 3 — Replay validation rejects tampered replays:** A replay with a modified score field fails validation with `FailReason.invalid_signature`.
  **Scenario 4 — Wave-pack version pinning:** A replay submitted against `wave_pack_version: 0.3.0` is rejected for the leaderboard of `0.4.0` (lands on `0.3.0`'s leaderboard instead).
  **Scenario 5 — Shop purchase idempotency:** A duplicate purchase request with the same client-side idempotency key returns the original `Purchase` record, not a new one.
  **Scenario 6 — Soft-delete behavior:** A soft-deleted player's leaderboard entries persist with display name replaced by "Anonymous Player"; their replay artifacts are anonymized but not deleted (deletion would invalidate other players' leaderboard positions that reference the same wave).
<!-- /theme example -->

---

## 5. Test Data

> Where does test data come from? How do we keep it isolated from production?

<!-- theme example -->
- **_Asteroids: Wave Defense:_**
  - **Fixture replays:** `tests/fixtures/replays/*.bin` — committed deterministic replays for regression testing
  - **Wave-pack fixtures:** `tests/fixtures/wave_packs/` — minimal 1-wave packs for fast tests
  - **Database:** Postgres test container via Docker Compose; seeded from `tests/fixtures/seed.sql`
  - **No production data in tests** — ever
<!-- /theme example -->
