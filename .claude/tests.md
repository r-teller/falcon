# Testing Strategy

Purpose: This file outlines the strategy for testing the application to ensure it works correctly and prevent future bugs.

> This file explains how we'll test the application to make sure it works correctly and doesn't break when we make changes. A good testing plan gives us confidence to build and release new features.
>
> The `<!-- theme example -->...<!-- /theme example -->` blocks below describe THIS repo's current testing approach — the Snake five-phase benchmark artifact at `examples/snake_opus.html`. Swap each block with your project's actual testing approach when adopting falcon for a different project.

---

## 1. Our Testing Philosophy

> What is our main goal for testing? We don't need to test every single line of code. Let's define what's most important.

- **Overall Goal:** [e.g., Ensure the most critical user journeys always work, Achieve 80% code coverage, Prevent regressions]

<!-- theme example -->
- **_Snake — Five-Phase Field Operation:_**
  **Overall Goal:** Verify each phase's PRD Acceptance Criteria (§5.5, §6.6, §7.6, §8.7, §9.9) plus the whole-game AC (§13) hold true in a real browser; verify the single-file no-external-deps constraint statically; verify canonical copy strings are exact (not paraphrased) on every commit.
  There are no automated unit / integration / E2E test harnesses — the deliverable is a single 500-line HTML file and PRD §11 explicitly budgets "test" turns as "manual playthrough of each phase, verifying every AC checkbox … not automated tests — this is a single-file artifact with no harness." The most important regression to prevent is silent paraphrasing of the canonical copy strings (PATROL LOST / Press R to redeploy / HOLD POSITION / PHASE N: NAME) and silent introduction of external dependencies (a stray `<script src>` or `<img src>`).
<!-- /theme example -->

---

## 2. Types of Tests We Will Write

> Different kinds of tests check different things. Here's a quick breakdown of what we'll use.

- **Unit Tests:** [Do we write these? What do they test? e.g., Yes, for individual functions and UI components in isolation.]
- **Integration Tests:** [Do we write these? What do they test? e.g., Yes, to check if our UI components correctly fetch data from the backend.]
- **End-to-End (E2E) Tests:** [Do we write these? What do they test? e.g., No, not at this stage. OR Yes, to simulate a full user journey in a real browser.]

<!-- theme example -->
- **_Snake — Five-Phase Field Operation:_**
  **Unit tests:** No — the artifact has no harness, no test runner, and no module boundaries. Per PRD §18 + §11 the verification model is manual playthrough.
  **Integration tests:** No.
  **E2E tests:** Deferred. A future bead could add Playwright coverage for §13 whole-game AC, but it's not in §16 PRD scope. (The wider repo's `mcp__playwright__browser_*` tool surface isn't available in every session, so Playwright coverage stays a nice-to-have rather than a gate.)
  **Static checks (these we DO run):**
   1. JS syntax: extract `<script>` and `node --check` it
   2. No-external-deps audit: `grep -Eni 'src=|href=|@import|<link|cdn|http://|https://' examples/snake_opus.html` returns 0
   3. Canonical copy presence: `grep -n "'PATROL LOST'|'Press R to redeploy'|HOLD POSITION|PHASE 1: NIGHT RECON|PHASE 2: DAWN PATROL"` returns the expected lines
   4. Constants match PRD: `grep -n "GRID_W = 32|GRID_H = 24|CELL = 20|BASE_TICK_RATE = 6|PHASE1_GATE_SCORE = 50"` returns expected
  **Manual playthrough:** per-phase AC verify beads (P1-05, P2-06, P3-08, P4-08, P5-11) own this — each is a chore-type bead that walks the §X.X PRD AC checklist in a real browser and either closes clean or files follow-up bugs via `bd create ... --deps "discovered-from:<verify-bead>"`.
  **bd lint:** runs against the project's bead bodies — required-section enforcement (work-item-templates.md) for any bead promoted to `triage:ready`.
<!-- /theme example -->

---

## 3. Testing Frameworks & Tools

> What software will we use to write and run our tests?

- **Main Testing Tool(s):** [e.g., pytest, Jest, React Testing Library, Cypress]
- **How to Run Tests (Command):** [e.g., `pytest`, `npm test`, `npm run cypress:open`]

<!-- theme example -->
- **_Snake — Five-Phase Field Operation:_**
  **No test framework.** The artifact has no `package.json`, no `pytest`, no test runner.
  **Static-check toolchain (ad-hoc, no harness):**
   - `node --check` (Node.js, any modern version) for JS syntax
   - `grep -Eni` for the no-external-deps audit + canonical-copy presence + constant value checks
   - `bd lint` for bead-body completeness when promoting to `triage:ready`
  **Manual playthrough toolchain:**
   - A modern browser (Chrome / Edge / Firefox / Safari)
   - File-manager double-click on `examples/snake_opus.html` — no dev server, no localhost
  **Bead-lifecycle "tests" (per-phase AC verify beads):**
   - P1-05 / P2-06 / P3-08 / P4-08 / P5-11 — chore beads that own the PRD §5.5 / §6.6 / §7.6 / §8.7 / §9.9 checklist walks

  **How to run static checks:**

  ```bash
  # JS syntax (extracts the inline <script> first)
  awk '/<script>/{f=1;next}/<\/script>/{f=0}f' examples/snake_opus.html > /tmp/_s.js \
    && node --check /tmp/_s.js && echo "JS syntax OK"

  # No-external-deps audit
  grep -cEin 'src=|href=|@import|<link|cdn|http://|https://' examples/snake_opus.html
  # Expected: 0

  # Canonical copy presence
  grep -nE "'PATROL LOST'|'Press R to redeploy'|HOLD POSITION|PHASE 1: NIGHT RECON|PHASE 2: DAWN PATROL" examples/snake_opus.html

  # Bead body / template completeness (run before promoting any bead to triage:ready)
  bd lint
  ```

  **How to "run" the artifact:**

  ```bash
  # macOS:    open examples/snake_opus.html
  # Linux:    xdg-open examples/snake_opus.html
  # Or:       double-click in a file manager
  ```
<!-- /theme example -->

---

## 4. Key Test Scenarios

> Let's list the most important user actions that absolutely must work. This helps us prioritize what to test first. Think back to the product goals in `architecture.md` and the acceptance criteria in your beads.

- **Scenario 1:** [e.g., A user should be able to log in with correct credentials.]
- **Scenario 2:** [e.g., A user should see an error if they try to log in with the wrong password.]
- **Scenario 3:** [e.g., A logged-in user should be able to create a new item.]

<!-- theme example -->
- **_Snake — Five-Phase Field Operation:_**
  **Scenario 1 — File loads cold from disk:** Double-clicking `examples/snake_opus.html` in any modern browser renders a dark-olive page with a 640×480 canvas inside a dark-khaki border, a centered 3-segment grayscale patrol, "SCORE 0" top-left, "PHASE 1: NIGHT RECON" top-center, empty reinforcements row top-right. Browser devtools Network tab shows ZERO external requests. (§13.1)
  **Scenario 2 — First input starts the patrol:** Page sits motionless until the first directional key (Arrow or WASD); thereafter the patrol moves. (§3.39 / §5.5)
  **Scenario 3 — Reversal protection:** With the patrol heading right, pressing Left does not reverse the patrol into itself. (§3.18)
  **Scenario 4 — Score + grow on supply cache:** Driving the head onto the cache cell increments the visible score by 1, grows the patrol by 1 segment, and immediately spawns a new cache on a non-patrol cell. (§3.34 / §5.5)
  **Scenario 5 — Wall + self collision losses:** Driving into any wall OR into the body (after growing to ≥ 5 segments) triggers the PATROL LOST overlay with exact canonical copy. (§4.5 / §13.5)
  **Scenario 6 — Speed ramp 6 → 8 across score 0 → 50:** Subjective playthrough confirms the patrol perceptibly speeds up between score 0 and 50; `state.tickRate` reaches 8 by the gate. (§3.16 / §5.5)
  **Scenario 7 — Phase 1 → 2 gate at score 50:** Collecting the 50-point cache triggers a 2-second "PHASE 2: DAWN PATROL" fade banner; HUD phase text updates; the patrol KEEPS MOVING during the banner (§3.37); score, length, direction all persist (§3.19).
  **Scenario 8 — Pause / resume:** P or Esc shows the HOLD POSITION overlay and halts ticks; pressing again resumes from the exact paused state.
  **Scenario 9 — Mid-game R is ignored, PATROL LOST R redeploys:** Pressing R during play does nothing; pressing R (or Space) from the PATROL LOST overlay starts a fresh Phase 1 run. (§3.23 / §13.5)
  **Scenario 10 — Canonical copy is exact:** A diff that paraphrases "PATROL LOST" → "GAME OVER", or "Press R to redeploy" → "Press R to restart", is a regression even if behaviourally correct. (§3.21 / §13.5)

  Scenarios 1–9 are the §5.5 + §13 AC for Phase 1; they belong to bead SNAKE-egj.5 (P1-05 — currently in_progress pending a browser session). Scenario 10 belongs to every per-phase verify bead, in perpetuity.
<!-- /theme example -->

---

## 5. Test Data

> Where does test data come from? How do we keep it isolated from production?

<!-- theme example -->
- **_Snake — Five-Phase Field Operation:_**
  - **None — the artifact uses `Math.random()` for cache spawn / Ambush trajectory / wormhole placement.** Per PRD §18 there is no determinism/replay requirement, so there are no test fixtures and no seeded RNG.
  - **The PRD itself is the test fixture.** `examples/snake_prd.md` §5.5, §6.6, §7.6, §8.7, §9.9, and §13 are the AC checklists; the per-phase verify beads (P1-05 through P5-11) walk them by hand.
  - **No production / no persistence / no network** — there's nothing to isolate from.
<!-- /theme example -->
