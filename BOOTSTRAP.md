# Bootstrap a new project from your PRD

> Part of the falcon distribution — run once per adopted project, after [installation](README.md#installation).
>
> - **Option 1 (copy install):** this file lands in your project alongside `.claude/` — delete BOOTSTRAP.md after the first run if you like.
> - **Option 3 (submodule install):** reference it as `@.claude/falcon-upstream/BOOTSTRAP.md` instead.

Goal: from a PRD to a session where you can run `/leroy`, `bd ready`, and `/falcon work beads <id>` against real work.

**Two ways to use this file:**

1. **Reference it directly** (recommended) — in a fresh Claude Code session in your project:

   ```
   Follow @BOOTSTRAP.md with my PRD @PRD.md
   ```

2. **Copy-paste** — copy the prompt block below into the session, with your PRD attached or its path referenced.

Either way, the prompt walks through 6 steps with confirmation checkpoints.

The `.claude/{architecture,backend,frontend,data-model,security,tests}.md` files (plus `handoff.yaml` and `changelog.yaml`) ship pre-populated with worked examples for a fictitious "Asteroids: Wave Defense" project. Every example block is wrapped in `<!-- theme example -->...<!-- /theme example -->` markers so a hydration pass can find and replace just the example content while preserving the template structure (section headers, instructional prose, table headers, code-block fences).

The prompt:

```
I'm setting up the falcon distribution in a new project. My PRD is @PRD.md
(or paste it inline below). Walk me through the 6 steps below so I can
start using /leroy + /falcon + beads. Pause at the indicated checkpoints.

---

STEP 1 — Read the PRD and summarize.

Read the PRD fully. Extract:
- Project name + one-sentence summary
- Tech stack (backend, frontend, DB, queue, storage, auth)
- Major subsystems / domains
- Initial features (will become first-phase beads)
- Open questions (will become decision/spike beads)
- Security posture (auth, data sensitivity, project-specific concerns)
- Testing strategy (philosophy, frameworks, key scenarios)

Present a one-page summary of what you found. Mark anything ambiguous as
[TODO: fill in]. STOP. Wait for me to confirm or amend before proceeding.

---

STEP 2 — Hydrate context files.

For each file below, locate every <!-- theme example -->...<!-- /theme example -->
block and replace ONLY its contents with PRD-derived values. Keep section
headers, instructional prose, table headers, code-block fences, and the
markers themselves untouched.

- .claude/architecture.md  (12 blocks)
- .claude/backend.md       (4 blocks)
- .claude/frontend.md      (4 blocks; if no UI, add `> **Not applicable** —`
                            at the file top + leave `n/a` placeholder lines
                            inside each block)
- .claude/data-model.md    (5 blocks; same Not Applicable convention if no DB)
- .claude/security.md      (6 blocks)
- .claude/tests.md         (5 blocks)
- .claude/handoff.yaml     (1 commented example entry between template_entry
                            and entries: []; re-theme the commented entry to
                            a plausible first session for my project, OR
                            delete the <!-- theme example --> block entirely)
- .claude/changelog.yaml   (same as handoff.yaml)

Constraints:
1. Preserve every <!-- theme example --> marker — load-bearing for future
   re-hydration passes.
2. Use [TODO: fill in] for granular unknowns inside an otherwise-applicable
   block; use `> **Not applicable** —` for whole sections that don't apply.
3. handoff.yaml + changelog.yaml example entries MUST remain fully commented
   (every line starting with `#`) so they don't parse as live data.
   /wrapup prepends real entries to entries: [] separately.
4. Leave .claude/docs/, .claude/skills/, .claude/agents/, .claude/commands/,
   .claude/rules/, .claude/claude.md, README.md, BOOTSTRAP.md, LICENSE,
   .gitignore alone.
5. After hydration, grep the 8 target files for:
       asteroid | wave[-_]pack | wave[-_]spawner | score-tracker |
       replay-validator | power-up-shop | physics-engine | level-designs
   Any hits are leaks — flag them.

Show a one-line summary per file. STOP. Wait for me to confirm before
proceeding to bead creation.

---

STEP 3 — Initialize beads.

Run `bd --version`. If missing, tell me to install beads
(https://github.com/anthropic-experimental/beads) and stop.

Run `ls .beads/`. If absent, run `bd init` (the non-interactive default —
use this for autonomous/unattended bootstrap runs). Use `bd quickstart`
only if a human is driving onboarding interactively. Otherwise note that
beads is already initialized.

---

STEP 4 — Create initial beads from the PRD.

Group the PRD's features by the phasing the PRD itself declares. If the
PRD doesn't phase work explicitly, group into 2-4 logical phases. Create:

1. Epic per phase:
       bd create "Phase N: <name>" --type epic

2. Child beads per feature in each phase, using the Stub Template from
   .claude/docs/work-item-templates.md (Summary + Persona + Phase + Rough
   Size; leave AC + Effort Forecast for /scribe refine later):
       bd create "<title>" --type feature --parent <epic-id> --add-label triage:backlog

3. Decision beads for each open question. Decision beads need a time-box
   per the Decision (Spike) Template — either add it via --description at
   create time, or expect /scribe refine to surface it as a gap:
       bd create "Decide: <question>" --type decision --add-label triage:triaged \
                 --description "Time Box: <N> turns / <N> days"

4. Promote Phase 1 stubs from triage:backlog → triage:triaged (ready to be
   fully spec'd by /scribe refine). Later phases stay triage:backlog.

5. Dependencies — for any feature the PRD indicates is sequenced after
   another:
       bd dep add <later-id> <earlier-id> -t blocks

Note on labels: beads created here carry only the `triage:*` label.
Size/cynefin/layer/persona labels are added by /scribe refine in Step 5
once each bead has full content (per the Readiness Checklist in
.claude/docs/work-item-templates.md).

Show a summary table: phase, # beads, triage state. STOP. Wait for me
to confirm before refining Phase 1.

---

STEP 5 — Refine Phase 1 beads to triage:ready (recommended).

For each Phase 1 bead created in Step 4, invoke:
      /scribe refine <bead-id>

scribe-refine will:
  - Inline the relevant PRD section into the bead body
  - Apply the appropriate Small/Medium/Large Feature template from
    .claude/docs/work-item-templates.md (sized per the bead's Rough Size)
  - Add Acceptance Criteria (testable checklist with - [ ] items)
  - Add Effort Forecast (per-phase: plan / implement / test / total +
    Confidence)
  - Add Changes Needed (file paths + actions)
  - Validate against the Readiness Checklist in work-item-templates.md
  - Promote triage:triaged → triage:ready

After this step, Phase 1 beads are immediately claimable by /falcon work
beads <id>. Phase 2+ beads STAY at triage:backlog/triaged for just-in-time
refinement when each later phase starts. This matches scribe-refine's
design philosophy ("use just-in-time before claim, not en masse") — Phase
1 qualifies as JIT because it starts now; Phase 2 will not.

If I prefer to refine each Phase 1 bead manually right before claiming
(no bulk refinement), tell me to skip this step and proceed to Step 6.

Show a summary of which Phase 1 beads landed at triage:ready, and flag
any that failed the Readiness Checklist. STOP. Wait for me to confirm
before printing next steps.

---

STEP 6 — Print next steps.

Tell me:

1. Run `/leroy` to start the first real session — it reads the freshly-
   hydrated architecture.md + handoff.yaml for orientation.
2. Run `bd ready` to see Phase 1 work that's claimable (all at
   triage:ready after Step 5).
3. Pick a Phase 1 bead and run `/falcon work beads <bead-id>` to dispatch
   to a remote worker. (Default mode is --bg on Claude Code 2.1.139+;
   auto-downgrades to --via-paste otherwise.)
4. For Phase 2+ work later: when a phase starts, run `/scribe refine
   <bead-id>` per Phase N bead before claiming. (Just-in-time refinement.)
5. Run `/wrapup` at session end to prepend a real entry to handoff.yaml +
   changelog.yaml.

Don't touch git in this bootstrap — the first /wrapup commit captures
everything cleanly.
```

The prompt leaves the falcon skill bundle (`.claude/skills/`, `agents/`, `commands/`, `docs/`, `rules/`, `claude.md`) untouched — those keep their illustrative asteroid references because they're skill-distribution content, not adopted-per-project content.

**If you don't have a PRD yet:** skip this section. Edit the 8 context files directly, or run `/scribe prd` to draft a Product Guidance section into `architecture.md` from a rough idea, then come back here once it's solid enough to seed beads.

**Want to try the workflow first?** Use [`examples/asteroids_prd.md`](examples/asteroids_prd.md) — an asteroid-themed sample PRD that matches the existing example content in this distribution. Paste it as your `@PRD.md` to smoke-test the bootstrap end-to-end before bringing in your real PRD.
