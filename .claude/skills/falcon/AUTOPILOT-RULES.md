# Falcon — Autopilot Rules File Template

> Template for the `.claude/rules/falcon-autopilot.md` rules file in adopting projects. Split out of `REFERENCE.md` at v7.2.0 when the parent file exceeded the 1500-line tripwire documented in `falcon-dev/.claude/architecture.md` Design Decisions.
>
> **What lives here:**
> - `## falcon-autopilot.md Template` — the 6-section rules-file template (`SAFE_TO_ACK_INTENT` predicate + `SAFE_TO_AMEND` whitelist + `SAFE_TO_AMEND` denylist + cognitive audit hints + advisor delegation policy + amendment budget defaults)
> - 3 profile definitions (`conservative`, `standard`, `aggressive`) consumed by `/falcon enable-autopilot --profile=<name>`
> - "How autopilot reads this file" + "Editing workflow" + "Related files" + adopter customization guidance
>
> **What does NOT live here:**
> - Cron prompt templates → see [`CRONS.md`](./CRONS.md) `## Autopilot Cron Prompt Templates`
> - Dispatch file YAML schema → see [`REFERENCE.md`](./REFERENCE.md#dispatch-file-yaml-schema) `## Dispatch File YAML Schema`
> - Steering-side dispatch protocol + cognitive audit invocation → see [`PROTOCOL.md`](./PROTOCOL.md) §3, §3b
> - Falcon-side `/falcon enable-autopilot` command surface → see [`COMMANDS.md`](./COMMANDS.md)

---

## falcon-autopilot.md Template

Written to `.claude/rules/falcon-autopilot.md` by `/falcon create-rules`. Universal sections are fixed; project-specific sections contain placeholders + auto-seeded examples drawn from the project's `.claude/rules/*.md` files.

```markdown
# Falcon Autopilot Rules ({{ project_name }})

> Consumed by falcon autopilot flags: `--auto-ack`, `--auto-amend`,
> `--advisor`, `--amendment-budget`, and the `--autopilot` bundle.
> See `.claude/skills/falcon/COMMANDS.md` for the consumer flag specs.
>
> **Status:** the autopilot consumer flags are currently `⊘` (proposed) in
> falcon v{{ falcon_version }}. This file is a forward-looking spec; the gates
> below are inert until the consumer lands. Iterate on the gates freely now
> so they're production-ready when the autopilot rollout happens.
>
> **Editing convention:** lines marked `# UNIVERSAL — do not edit` come
> from falcon's defaults. Project-specific gates are added below each
> universal section, marked `# PROJECT —`. Uncomment a gate to activate it;
> leave commented to disable.

---

## 1. SAFE_TO_ACK_INTENT predicate

When the worker emits an intent paragraph, autopilot evaluates these gates.
If ALL pass: auto-ack (writes `intent_acknowledged_utc`, emits `proceed
<dispatch-id>` block). If ANY fail: defer to user.

```yaml
safe_to_ack_intent:
  # UNIVERSAL — do not edit
  gates:
    - no_new_file_scope:
        description: |
          Intent paragraph does not propose touching files outside the
          dispatch's declared file_scope.
        check: |
          Regex intent for absolute paths and known project-root prefixes
          (e.g., docs/, score-tracker/, patches/). Cross-check matches against
          dispatch.file_scope.directories + dispatch.file_scope.files. Any
          match outside scope fails this gate.

    - no_cross_dispatch_conditional:
        description: |
          Intent does not contain phrases implying the bead depends on
          another in-flight dispatch's outcome.
        check: |
          Search intent for: "after X bead closes", "depending on", "if X
          succeeds", "waiting on", "blocked-by" + bead IDs. Any match fails
          this gate.

    - intent_matches_changes_needed:
        description: |
          Intent's "core deliverables" overlap with the bead body's Changes
          Needed file list (substring or keyword match).
        check: |
          Extract file paths + key nouns from bead's Changes Needed section.
          Extract same from intent paragraph. Overlap must be >= 50% of
          Changes Needed items by token count.

    - no_open_dar_arbitration:
        description: |
          No prior dispatch on this branch has an unresolved DAR with
          action_taken: "stopped pending arbitration".
        check: |
          Parse .claude/tmp/falcon-reports-<sanitized-branch>.yaml. Any
          decisions_for_human[] entry with stakes: high and unrecorded
          resolution fails this gate.

  # PROJECT — uncomment to activate
  # project_gates:
  #   - example_project_gate:
  #       description: |
  #         <Replace with a project-specific intent constraint. Example:
  #          intent must not propose extending an externally-versioned
  #          manifest without a corresponding version bump.>
  #       check: |
  #         <Describe how to detect the constraint from the worker's
  #          intent paragraph. Any match fails this gate; defer to human.>
```

---

## 2. SAFE_TO_AMEND whitelist

Autopilot may auto-issue amendments for these categories. Whitelist is
restrictive — anything not listed defers to the user.

```yaml
safe_to_amend_whitelist:
  # UNIVERSAL — do not edit
  - rephrase_existing_test
  - missing_regression_check
  - missing_bd_export
  - missing_wave_pack_pin

  # PROJECT — uncomment to activate (seeded from project's rule files)
  # - missing_wave_pack_version_pin_bump:
  #     trigger: |
  #       Commit touches docs/findings/*.yaml but no score-tracker/waves/*.yaml
  #       in the same commit, OR pin in wave yaml does not match new hash.
  #     rule_ref: development-standards.md §3.17
  #     amendment_text: |
  #       Recompute wave_pack_version (replay-validator side + scorer side),
  #       update every score-tracker/waves/*.yaml pin to the new hash,
  #       commit in same change. Cite both hashes in the close-out message.
  #
  # - missing_bd_export_after_batch:
  #     trigger: |
  #       3+ bd writes (label, comment, status) without a final
  #       bd export -o .beads/issues.jsonl invocation.
  #     rule_ref: workflow-execution.md "Persist work-tracking state with the commit"
  #     amendment_text: |
  #       Run `bd export -o .beads/issues.jsonl` to flush canonical jsonl.
  #       Stage the file in the commit.
  #
  # - missing_closes_footer:
  #     trigger: |
  #       bd close <id> was called in the dispatch BUT the commit message
  #       does not include "Closes: <id>".
  #     rule_ref: workflow-execution.md "Commit Message Style"
  #     amendment_text: |
  #       Amend the commit (or add a new commit if the bead is closed) with
  #       "Closes: <id>" in the message footer.
  #
  # - add_sha_header_to_verify_artifact:
  #     trigger: |
  #       File written under verify/ does not start with a `# captured_at_sha`
  #       header line.
  #     rule_ref: project convention for verification artifacts
  #     amendment_text: |
  #       Prepend git SHA + ISO8601 timestamp header to the artifact file
  #       so a future audit can match the artifact to a specific commit.
  #
  # - stable_identifier_assertion:
  #     trigger: |
  #       New or modified route smell-check test uses substring assertion
  #       like `assert "X" in r.text` on body prose.
  #     rule_ref: rules/standards.md candidate "Route smell-check tests assert on stable identifiers"
  #     amendment_text: |
  #       Replace substring assertion with stable-identifier check
  #       (id="...", data-test="...", or CSS class on a structural element).
```

---

## 3. SAFE_TO_AMEND denylist

Autopilot NEVER auto-issues amendments in these categories. Surface to user.

```yaml
safe_to_amend_denylist:
  # UNIVERSAL — do not edit
  - new_ac_item
  - new_file_outside_scope
  - new_endpoint
  - architectural_change

  # PROJECT — uncomment to activate (seeded from project's rule files)
  # - wave_pack_yaml_mutation:
  #     description: |
  #       Any amendment that proposes mutating docs/findings/*.yaml mid-flight.
  #     reason: |
  #       Wave-pack is contract-bearing (§3.18); mid-flight changes risk
  #       cross-entry reference drift. Wave-pack mutations require dedicated
  #       beads, not amendments.
  #
  # - paired_bead_separation:
  #     description: |
  #       Any amendment that proposes closing only one half of a clj/7hq pair.
  #     reason: |
  #       Paired-claim rule (workflow-execution.md) requires both halves
  #       close in the same commit. Splitting violates §3.22 interop contract.
  #
  # - bypass_manual_close_gate:
  #     description: |
  #       Any amendment that proposes closing a bead based on unit-test-pass
  #       alone when the bead's Testing Strategy names manual verification.
  #     reason: |
  #       §3.10 close-gate is non-negotiable; bypassing it forfeits the
  #       regression-detection guarantee.
  #
  # - wave_yaml_without_recompute:
  #     description: |
  #       Any amendment that proposes editing score-tracker/waves/*.yaml
  #       without an accompanying wave_pack_version recomputation.
  #     reason: |
  #       §3.9 boundary violation; the two services will diverge.
  #
  # - rules_or_architecture_md_rewrite:
  #     description: |
  #       Any amendment that proposes modifying .claude/rules/*.md or
  #       .claude/architecture.md.
  #     reason: |
  #       Standards changes require human acknowledgement; not safe to
  #       auto-amend even if the trigger is mechanical.
```

---

## 4. Bead-type-specific cognitive audit hints

Per PROTOCOL.md §3b, after mechanical validation, steering asks: "any
project-binding concern this bead's AC did NOT gate on?" These are the
project's prompts indexed by bead context.

```yaml
cognitive_audit_hints:
  # PROJECT — uncomment to activate

  # touches_wave_pack_yaml:
  #   trigger: |
  #     Any commit in dispatch touches docs/findings/*.yaml.
  #   prompts:
  #     - "Did wave wave_pack_version pin update in the same commit? (§3.17)"
  #     - "Do replay-validator and score-tracker compute the same new hash? (§3.9)"
  #     - "Did ruamel.yaml round-trip get used (not surgical line edits)? (§3.18)"
  #
  # touches_patch_dir:
  #   trigger: |
  #     Any commit touches patches/vulnerabilities/<id>/.
  #   prompts:
  #     - "Was the sibling clj.* / 7hq.* paired bead updated in the same commit?"
  #     - "Did the patch interact with shared middleware? Full-wave-pack regression sweep required, not single-entry test. (§3.22)"
  #
  # touches_level_designs_tree:
  #   trigger: |
  #     Any commit touches docs/level-designs/.
  #   prompts:
  #     - "Do walkthrough filenames still resolve? (dry-run cross-reference)"
  #     - "Do replay fixtures still load in the scoring suite?"
  #
  # claims_oob_verification:
  #   trigger: |
  #     Bead body Acceptance Criteria or Testing Strategy contains the
  #     phrase "out-of-band" or "Robert verifies" or names an external
  #     persona/tool as verifier.
  #   prompts:
  #     - "Did the agent run the named probe itself? (§3.15 — MUST NOT)"
  #     - "Check bash log: any `curl http://localhost:3000/<probe-path>` invocations should NOT appear."
  #
  # migration_or_rename_bead:
  #   trigger: |
  #     Bead title contains "rename", "migrate", "retire", or the body
  #     names retired identifiers.
  #   prompts:
  #     - "Run post-commit grep for retired identifiers: `grep -rln <old-id>`."
  #     - "Any survivors? Flag as a standards firing (file-contract gap)."
  #
  # schema_bearing_bead:
  #   trigger: |
  #     Bead touches a schema file (*.schema.yaml, _preamble.yaml).
  #   prompts:
  #     - "Does the schema change break any pinned enum value consumers expect?"
  #     - "Did the wave yaml's wave_pack_version need rebumping for the schema diff?"
  #
  # bead_with_sibling_output_dependency:
  #   trigger: |
  #     Bead's Changes Needed produces output consumed by a sibling bead
  #     declared in `discovered_from` or `blocks` deps.
  #   prompts:
  #     - "Does the produced output shape match the sibling bead's AC declared input?"
  #     - "If sibling is in_progress in a concurrent dispatch, is the consumer reading the right hash/path?"

  # touches_prompt_template_or_skill_content (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit touches files in .claude/skills/, .claude/agents/, or
  #     .claude/commands/ — anything that the runtime treats as a prompt.
  #   prompts:
  #     - "Was the prompt change reviewed for prompt-injection or unintended tool-grant patterns?"
  #     - "Did the change preserve the version: frontmatter bump if behavior-altering?"
  #     - "Did the changelog get an entry naming the prompt/skill affected?"
  #     - "If the change touches a worker init_prompt, does it preserve the auto-ack-resume guard semantics?"
  #
  # touches_security_policy_file (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit touches .claude/rules/falcon-autopilot.md, .claude/security.md,
  #     or any file under .github/workflows that gates merges.
  #   prompts:
  #     - "Was the gate change reviewed for refuse-on-MVM preservation?"
  #     - "Did the change loosen any SAFE_TO_ACK_INTENT or SAFE_TO_AMEND predicate without a sibling test?"
  #     - "If the change extends autopilot autonomy, was it accompanied by an amendment-budget reduction or other compensating control?"
  #
  # bumps_dependency_or_runtime_version (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit changes pinned version in package.json, requirements.txt,
  #     pyproject.toml, go.mod, Gemfile.lock, OR the minimum Claude Code version
  #     in SKILL.md frontmatter.
  #   prompts:
  #     - "Did changelog and README minimum-version notes update in lockstep with the bump?"
  #     - "Were breaking changes in the bumped dependency reflected in falcon's own behavior or docs?"
  #     - "If bumping Claude Code minimum: does auto-downgrade still trigger correctly on the prior version?"
  #
  # modifies_cron_schedule_or_template (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit touches REFERENCE.md `## Autopilot Cron Prompt Templates`
  #     OR changes the default --cron-cadence in COMMANDS.md.
  #   prompts:
  #     - "Was the change reviewed against the Cron Dispatch-Mode Conventions for both --bg and --via-paste paths?"
  #     - "Does the offset-staggering still hold after the change?"
  #     - "Were both single-dispatch and parallel-dispatch attribution tests run in the scoring/smoke pass?"
  #
  # introduces_new_dispatch_mode_or_flag (v7.0.1, fdev-lbq.12):
  #   trigger: |
  #     Any commit adds a new --bg-*, --paste-*, --autopilot-* flag OR a new
  #     dispatch-mode value in worker_dispatch_mode.
  #   prompts:
  #     - "Was the new flag added to PROTOCOL.md `### Mode selection + detection`?"
  #     - "Did the cron templates' worker_dispatch_mode branch get extended to cover the new mode?"
  #     - "Does the new flag preserve the refuse-on-MVM precedent if it's write-bearing?"
```

---

## 5. Advisor delegation policy

When a DAR is ambiguous (not clearly auto-approve or clearly reject),
autopilot can fork to a registered advisor before falling back to human.

```yaml
advisor_delegation:
  # PROJECT — uncomment to activate

  # quartermaster:
  #   skill_ref: .claude/skills/quartermaster
  #   delegates:
  #     - dar_in_scope_question:
  #         description: "Is this work in scope of <broader-bead> or this bead?"
  #         rationale: Architectural fit is quartermaster's specialty.
  #     - dar_defer_vs_fix_now:
  #         description: "Should this be deferred or fixed now?"
  #         rationale: Priority/sequencing review is quartermaster's specialty.
  #     - dar_shared_script_extraction:
  #         description: "Should this transformation be extracted to a shared script (§3.21)?"
  #         rationale: Refactor-vs-inline judgment is quartermaster's specialty.
  #
  #   refuses:
  #     # DARs that MUST NOT delegate to quartermaster; human only
  #     - scoring_semantics:
  #         description: "Should this replay score as PASS or FAIL?"
  #         rationale: Pedagogy/intent calls are author-only.

  # herald:
  #   skill_ref: .claude/skills/herald
  #   delegates:
  #     - dar_ux_pattern_choice:
  #         description: "Which UX pattern fits this surface?"
  #         rationale: Design-system fit is herald's specialty.
```

---

## 6. Default amendment budget per bead type

`--amendment-budget` caps how many auto-issued amendments before HALT.

```yaml
amendment_budget_defaults:
  # PROJECT — uncomment to activate

  # chore: 2          # mechanical work; 2 amendments handles most gap-fills
  # bug: 1            # small surface; 1 amendment usually enough
  # feature_small: 2  # single-layer feature; 2 amendments
  # feature_medium: 3 # cross-layer feature; 3 amendments
  # feature_large: 5  # full-stack feature; 5 amendments
  # decision: 0       # spike work — defer all judgment to user
  # spike: 0          # same as decision
  # clj_pair: 1       # paired beads — sibling-bead interaction is brittle, keep tight
  # 7hq_pair: 1       # same as clj_pair
  # epic: 0           # epics don't get amendments; they're parent containers
```

---

## How autopilot reads this file

Per `.claude/skills/falcon/PROTOCOL.md` §3 (Receive and Validate Worker Report) and §3b (Steering-Side Cognitive Audit), the autopilot consumer (when implemented) parses this file at dispatch resume and at completion-signal time.

Order of evaluation:

1. **At intent emission** → `safe_to_ack_intent.gates` (universal) + `safe_to_ack_intent.project_gates` (uncommented only) → all pass = auto-ack
2. **At completion signal** → mechanical validation (steps 1-5 in PROTOCOL.md §3) → cognitive audit (§3b) consulting `cognitive_audit_hints` (uncommented only)
3. **If a gap surfaces** → consult `safe_to_amend_whitelist` (universal + uncommented project) → if matches: auto-issue amendment up to `amendment_budget_defaults` cap
4. **If gap matches `safe_to_amend_denylist`** → never auto-amend; surface to user
5. **If DAR is ambiguous** → consult `advisor_delegation` (uncommented only) → fork or defer

Commented gates are inert. To activate, uncomment + adjust the placeholder text. To deactivate without deleting, re-comment.

---

## Editing workflow

1. **Run `/falcon create-rules`** to populate this file (first time only).
2. **Review project sections** — every `# PROJECT —` block has placeholder gates seeded from your `.claude/rules/*.md` files. Uncomment the ones you want active.
3. **Tune defaults** — adjust amendment-budget numbers and rule references to match your project's standards file naming.
4. **Commit the file** to the repo so other contributors (and other agent sessions) see the same autopilot policy.
5. **Re-run `/falcon create-rules --force`** after major rule-file changes to re-seed defaults; archive the prior version to `.archive/falcon-autopilot-<timestamp>.md`.

---

## Related files

- `.claude/skills/falcon/SKILL.md` — entry point
- `.claude/skills/falcon/COMMANDS.md` — flag specs that consume this file
- `.claude/skills/falcon/PROTOCOL.md` — §3 + §3b (validation + cognitive audit) consume this file
- `.claude/rules/standards.md`, `development-standards.md`, `workflow-execution.md`, `workflow-agents.md` — source of project-specific gate seeds

```

(End of falcon-autopilot.md template.)

### Profile definitions (v6.14.0)

Consumed by `/falcon enable-autopilot --profile=<name>` (see COMMANDS.md and PROTOCOL.md). Defines exactly which `# PROJECT —` items each profile activates, with the detection condition that gates each activation. Items whose detection condition is false stay commented even at aggressive — this prevents activating gates that reference standards the project doesn't have.

Detection condition types:

- `file_exists: <path>` — true if the file exists (path relative to project root)
- `file_grep: <path>, pattern: <regex>` — true if file exists AND pattern matches at least one line
- `directory_has_files: <path>, pattern: <glob>` — true if directory contains at least one file matching glob
- `always` — unconditionally true (used for `safe_to_amend_denylist` items which apply universally)
- `skill_installed: <skill-slug>` — true if `.claude/skills/<slug>/SKILL.md` exists

```yaml
profiles:

  # ---------------------------------------------------------------
  # CONSERVATIVE — minimum-viable autopilot
  # ---------------------------------------------------------------
  conservative:
    description: |
      Minimum-viable autopilot. ALL denylist items active (safety:
      more is better). 1-2 highest-priority intent gates. ZERO
      project whitelist items (universal whitelist only). Tight
      amendment budgets. Use when first activating autopilot on a
      new project.

    items:
      # §1 — intent gates: ONE high-priority gate only
      - section: safe_to_ack_intent.project_gates
        item: example_project_gate
        detection:
          file_exists: .claude/fair-play-policy.md

      # §2 — whitelist: NONE (universal only)

      # §3 — denylist: ALL (always)
      - section: safe_to_amend_denylist
        item: wave_pack_yaml_mutation
        detection: always
      - section: safe_to_amend_denylist
        item: paired_bead_separation
        detection: always
      - section: safe_to_amend_denylist
        item: bypass_manual_close_gate
        detection: always
      - section: safe_to_amend_denylist
        item: wave_yaml_without_recompute
        detection: always
      - section: safe_to_amend_denylist
        item: rules_or_architecture_md_rewrite
        detection: always

      # §4 — cognitive hints: claims_oob_verification only
      - section: cognitive_audit_hints
        item: claims_oob_verification
        detection:
          file_exists: .claude/fair-play-policy.md

      # §5 — advisor: NONE

      # §6 — amendment_budget_defaults: tight
      - section: amendment_budget_defaults
        item: chore
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: bug
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_small
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_medium
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_large
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: decision
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: spike
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: epic
        value: 0
        detection: always

  # ---------------------------------------------------------------
  # STANDARD — recommended for general use
  # ---------------------------------------------------------------
  standard:
    description: |
      Recommended for general use. ALL denylist + project-seeded
      §1, §2, §4 items where detection holds + §5 advisor (if
      quartermaster skill exists) + sensible per-bead-type budgets.

    items:
      # §1 — intent gates: all detected
      - section: safe_to_ack_intent.project_gates
        item: example_project_gate
        detection:
          file_exists: .claude/fair-play-policy.md

      # §2 — whitelist: project items where detection holds
      - section: safe_to_amend_whitelist
        item: missing_wave_pack_version_pin_bump
        detection:
          file_grep:
            path: .claude/rules/development-standards.md
            pattern: '§3\.17|wave_pack_version pin'
      - section: safe_to_amend_whitelist
        item: missing_bd_export_after_batch
        detection:
          file_grep:
            path: .claude/rules/workflow-execution.md
            pattern: 'bd export'
      - section: safe_to_amend_whitelist
        item: missing_closes_footer
        detection:
          file_grep:
            path: .claude/rules/workflow-execution.md
            pattern: 'Closes:|Commit Message Style'
      - section: safe_to_amend_whitelist
        item: stable_identifier_assertion
        detection:
          file_grep:
            path: .claude/rules/standards.md
            pattern: 'stable identifier'

      # §3 — denylist: ALL (always)
      - section: safe_to_amend_denylist
        item: wave_pack_yaml_mutation
        detection: always
      - section: safe_to_amend_denylist
        item: paired_bead_separation
        detection: always
      - section: safe_to_amend_denylist
        item: bypass_manual_close_gate
        detection: always
      - section: safe_to_amend_denylist
        item: wave_yaml_without_recompute
        detection: always
      - section: safe_to_amend_denylist
        item: rules_or_architecture_md_rewrite
        detection: always

      # §4 — cognitive hints: all detected
      - section: cognitive_audit_hints
        item: touches_wave_pack_yaml
        detection:
          directory_has_files:
            path: docs/findings/
            pattern: '*.yaml'
      - section: cognitive_audit_hints
        item: touches_patch_dir
        detection:
          directory_has_files:
            path: patches/vulnerabilities/
            pattern: '*/01-fix.patch'
      - section: cognitive_audit_hints
        item: claims_oob_verification
        detection:
          file_exists: .claude/fair-play-policy.md
      - section: cognitive_audit_hints
        item: migration_or_rename_bead
        detection: always
      - section: cognitive_audit_hints
        item: schema_bearing_bead
        detection: always

      # §5 — advisor: quartermaster if installed
      - section: advisor_delegation
        item: quartermaster
        detection:
          skill_installed: quartermaster

      # §6 — amendment_budget_defaults: template recommended
      - section: amendment_budget_defaults
        item: chore
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: bug
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: feature_small
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: feature_medium
        value: 3
        detection: always
      - section: amendment_budget_defaults
        item: feature_large
        value: 5
        detection: always
      - section: amendment_budget_defaults
        item: decision
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: spike
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: clj_pair
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: 7hq_pair
        value: 1
        detection: always
      - section: amendment_budget_defaults
        item: epic
        value: 0
        detection: always

  # ---------------------------------------------------------------
  # AGGRESSIVE — maximum autopilot autonomy
  # ---------------------------------------------------------------
  aggressive:
    description: |
      Maximum autopilot autonomy. EVERY `# PROJECT —` item where
      detection holds. Generous budgets. Use only after running
      standard for several sprints and confirming the autopilot is
      well-calibrated.

    items:
      # §1, §2, §3, §4, §5 — inherit standard's full set
      - inherit_from: standard

      # §1 additions (none beyond standard for this template)

      # §2 additions: add additional whitelist items as the project
      # grows. For the v6.14.0 template seed, standard already covers
      # the documented whitelist; aggressive matches §2 with standard.

      # §6 — generous budgets
      - section: amendment_budget_defaults
        item: chore
        value: 3
        detection: always
      - section: amendment_budget_defaults
        item: bug
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: feature_small
        value: 3
        detection: always
      - section: amendment_budget_defaults
        item: feature_medium
        value: 5
        detection: always
      - section: amendment_budget_defaults
        item: feature_large
        value: 8
        detection: always
      # decision / spike stay 0 (judgment work — no autopilot ever)
      - section: amendment_budget_defaults
        item: decision
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: spike
        value: 0
        detection: always
      - section: amendment_budget_defaults
        item: clj_pair
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: 7hq_pair
        value: 2
        detection: always
      - section: amendment_budget_defaults
        item: epic
        value: 0
        detection: always
```

### Adapting profiles to a new project

The profile definitions above are seeded from the example project's standards. When falcon ships to a new project, the detection conditions will fail for many items (e.g., `.claude/fair-play-policy.md` doesn't exist; `development-standards.md §3.17` doesn't exist). The command degrades gracefully — items with failed detection stay commented; the user sees the omission in the dry-run preview.

To customize the profiles for a project that has DIFFERENT standards-files / DIFFERENT high-risk patterns, edit this section of REFERENCE.md before running `/falcon enable-autopilot`. Common adaptations:

- Add new project-specific whitelist items with their `rule_ref` and `amendment_text`, then add the `(section, item, detection)` tuple to the appropriate profile.
- Add new denylist items for project-specific catastrophic-amendment patterns; add to ALL three profiles' denylist sections (denylist always defaults to `detection: always`).
- Modify amendment budget defaults to fit the project's tolerance for autopilot scope.
- Re-run `/falcon enable-autopilot --profile=<name> --dry-run` after edits to verify the diff matches intent.

(End of profile definitions.)
