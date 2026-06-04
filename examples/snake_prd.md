# PRD: Snake — Evolving Five-Phase Field Operation (Canonical)

> Canonical explicit PRD. Authored from `examples/snake_prd_descriptive.md` via engineering review. Every "designer's call" the descriptive draft left open is resolved below with one sentence of rationale.
>
> Convention: top-level sections are `§1`, `§2`, …; sub-sections `§X.Y` bind exactly one rule or one fact. Numbers are stable identifiers — once shipped they do not move.

---

## §1. Product Summary

### §1.1 One-line summary

A single-file browser Snake game styled as a field-ops patrol that escalates through five gated phases — Night Recon → Dawn Patrol → Ambush → Bunker Run → Sector Transfer — sharing one state machine, one persistent score, and one cohesive field-ops visual language.

### §1.2 Why this PRD exists

This is the canonical benchmark PRD used to compare coding models. An adopter feeds this entire document (or just §15, the Implementation Prompt) to a model and judges the resulting `snake_[model].html` artifact. The PRD must therefore be self-contained: every fact a model needs is in this file, with no external links to resolve.

### §1.3 Aesthetic — field-ops / camouflage (canonical)

The game wears a consistent field-ops / camouflage aesthetic. The canonical visual palette is:

- **olive drab**
- **coyote brown**
- **tan**
- **black**
- **dark green**
- and other muted earth tones

Neon and saturated arcade hues are forbidden in every phase. Within those tones:

- The **patrol (snake)** uses blocky camouflage coloring — each consecutive segment is one solid patch in one of the earth tones (olive / tan / coyote brown / black), alternating segment-by-segment, with the head a distinguishable darker tone bearing a directional notch or eye dot.
- **Supply caches** (regular pickups) read as small crates / ammo boxes — tan / brown fill, dark outline, optional 1-px strap markings.
- **Field rations** (bonus pickups) read as a higher-tier care-package supply drop — coyote brown with a small gold accent.
- **Tactical vocabulary** flows through HUD and phase names ("PATROL", "AMBUSH", "BUNKER", "SECTOR", "WORMHOLE", "PATROL LOST"). See §3.21 for the canonical run-end copy and §3.38 for the canonical tactical callout examples.
- The **canvas** sits inside a thin dark-khaki panel / border frame; the **HUD typography** is stencil / monospace / parchment so the artifact reads as a finished mini-game rather than a bare canvas.
- The **board styling** is earth-tone background with grid or terrain-inspired texture — never a stark black playfield.

Phase 1 projects a **monochrome night-recon / training-exercise** look (low-visibility mode, grayscale only). At Phase 2 **dawn breaks** and the full camo palette emerges; from there through Phase 5 the aesthetic stays consistent — no jarring palette swaps between phases.

The canonical palette is the visual identity. §6.2 specifies a suggested hex palette; implementers may substitute their own colors only if every constraint above remains satisfied.

### §1.4 Scope budget for the implementing agent

A capable front-end coding model should produce a working `snake_[model].html` in **45–75 minutes** of generation time. The descriptive draft's "30 minutes" budget was for the single-phase classic; the five-phase scope warrants a larger budget. See §11 (Effort Forecast) for per-phase breakdown.

---

## §2. Personas

| Persona | Role | Priority | What they need from this PRD |
|---|---|---|---|
| **Player** | End-user, plays the finished HTML file | Primary | Familiar Snake feel; phase escalation that reads as earned progression; no unfair deaths. |
| **Implementing Agent** | Coding model or developer building from this PRD | Primary | Enough specificity to build without guessing; enough latitude on visuals and tuning to express judgment. |
| **Adopter / Benchmark Operator** | Engineer running this PRD across multiple models to compare outputs | Secondary | A repeatable prompt (§15) and a consistent artifact name (§14) so model outputs are diff-able. |
| **Reviewer** | Person who plays each model's artifact and scores it | Secondary | Acceptance Criteria (§13) phrased as checklist items that a human tester can verify in one pass. |

---

## §3. Open Questions Surfaced and Resolved

> This section shows the engineering review's work. Every ambiguity from the descriptive draft (and every additional question surfaced during review) is resolved here with a one-sentence rationale.

### §3.1 Score thresholds

**Q:** What specific score thresholds gate each phase transition?
**A:** **Phase 1→2 = 50, Phase 2→3 = 150, Phase 3→4 = 350, Phase 4→5 = 700.** A roughly 2× curve gives "attainable in a few minutes" at the first gate and "real accomplishment" at the last; the exact numbers are documented in §8 (Functional Gates) so adopters can tune without re-reading prose.

### §3.2 Phase 2 upgrade choice

**Q:** Which of the four candidate upgrades is the canonical pick?
**A:** **Scavenger Training** — a 1.5-cell attraction radius on supply caches and field rations. It is the most visually obvious upgrade (player sees crates pulled toward the patrol), reads as a reward at first contact, and is the easiest of the four to implement without subtle physics edge cases (the others require direction-state changes that interact poorly with the Ambush in Phase 3). "Scavenger Training" is the upgrade's canonical in-game name; the rest of this PRD uses that label.

### §3.3 Phase 4 block density

**Q:** How dense are the static blocks in Phase 4?
**A:** **6% of grid cells** filled with static blocks at Phase 4 start, placed by rejection-sampled flood-fill to guarantee one connected open region covering ≥ 90% of remaining cells; see §6.5. This reads as "obstacles you route around" rather than "maze you solve."

### §3.4 Phase 5 block density curve

**Q:** How does block density scale across Phase 5 levels?
**A:** **density(level) = min(0.06 + 0.015 × (level − 1), 0.18)** — capped at 18% so that even Phase 5 level 9+ remains playable (one connected open region ≥ 70% of remaining cells, enforced by the same flood-fill check). See §7.4.

### §3.5 Ambush frequency

**Q:** How often does the Ambush appear in Phase 3+?
**A:** **One Ambush sweep every 12–20 seconds** (uniform random interval). Frequent enough that the patrol feels contact each minute, rare enough that the Ambush reads as a discrete event rather than ambient hostility. ("Ambush" is the canonical name for the hostile sniper-line / sweeping-fire event introduced in Phase 3; the rest of this PRD uses that label.)

### §3.6 Ambush telegraph duration

**Q:** How long is the warning before the Ambush sweep strikes?
**A:** **1.5 seconds of telegraph**, rendered as a translucent line along the Ambush trajectory with a pulsing animation (the "sight line"). This is enough reaction time for a patrol moving at Phase 3 base speed (8 cells/sec) to reroute by 3–6 cells.

### §3.7 Ambush speed and trajectory

**Q:** How fast does the Ambush cross the board, and what path does it take?
**A:** The Ambush sweep crosses the entire playfield in **0.4 seconds** along a **straight line** from one randomly chosen edge cell to another randomly chosen edge cell on a different side. Straight-line keeps trajectory readable during telegraph; 0.4 s sweep is fast enough to feel like incoming fire, slow enough to dodge if the patrol committed to dodging during telegraph.

### §3.8 Ambush cut rule

**Q:** When the Ambush hits the patrol, where exactly is the cut made?
**A:** **Cut at the strike point.** The patrol retains all segments from head to the first hit segment (exclusive); all segments behind the strike point are removed (the "patrol casualties"). "Halve always" punishes long patrols disproportionately; "cut at strike point" gives the player meaningful agency — being hit near the tail is a small setback (a few casualties), being hit near the head is a large one (most of the patrol lost).

### §3.9 Reinforcement drop rate

**Q:** How often do bonus life (reinforcement) pickups appear?
**A:** **Every 90–150 seconds** of active gameplay (uniform random interval), with a maximum of **5 reinforcements in reserve** at any time (drops above the cap simply do not spawn). Pickup lifetime on the field is 10 seconds. Reinforcements are themed as inbound squad members; mechanically they are the bonus-life reserve.

### §3.10 Phase 5 wormhole countdown duration

**Q:** How long after entering Phase 5 (or completing a Phase 5 sector) until the wormhole pair appears?
**A:** **30 seconds** of open patrol before the wormhole pair spawns, then the wormholes persist until the patrol enters one or is lost. This gives the player meaningful time to bank score before committing to transfer to the next sector. ("Wormhole" is the canonical name for the Phase 5 traversal mechanic — a navigable transition between sectors; "sector transfer" is the canonical name for the level transition itself; the rest of this PRD uses those labels. The wormhole is conceptually a traversal mechanic the patrol drives into — the implementer chooses the in-world rendering within the field-ops aesthetic; specific colors and shapes are NOT prescribed. See §9.5.)

### §3.11 Phase 5 operational tempo per sector

**Q:** How much does the patrol speed up per Phase 5 sector?
**A:** **+8% patrol speed per Phase 5 sector** ("operational tempo increases"), capped at **+80% over base** (i.e., sector 10+ caps tempo). Compounds with the small intra-phase speed bump from §6.1. Without a cap, the game becomes input-lag-bound at high tempo; +80% is the empirical ceiling for "still playable with keyboard."

### §3.12 Phase 5 sector soft cap

**Q:** Do Phase 5 sectors have a visual soft cap, or scale indefinitely?
**A:** **Visual soft cap at sector 10.** Block density, tempo, and the sector counter still progress (counter shows "S11", "S12", …) but the background hue cycles back to a familiar dusk-palette; this signals "long-haul deployment" without adding new mechanics the PRD doesn't specify.

### §3.13 Random bonus appearance rates

**Q:** Which random bonuses appear in which phases and at what cadence?
**A:** See §10 (Random Bonus Appearance Spec) for the full per-phase matrix. Summary: field rations unlock at Phase 2, Cover (Shield) at Phase 3 (the phase where it becomes meaningful), score multiplier at Phase 2, sprint boost at Phase 4. Cadences range from 20 s (field rations) to 90 s (Cover).

### §3.14 Visual language

**Q:** Pixel art, vector / canvas-drawn shapes, or DOM-based grid?
**A:** **HTML5 Canvas with flat geometric primitives** (filled rectangles, lines, simple circles). No pixel art (asset constraints), no DOM grid (poor performance at Phase 5 tempo with bonuses on screen). Canvas + primitives keeps the file size small and the field-ops visual language consistent across phases. Earth-tone palette per §6.2; no neon, no saturated arcade hues.

### §3.15 Grid dimensions

**Q:** How big is the playfield grid?
**A:** **32 cells wide × 24 cells tall** at **20 px per cell** → 640 × 480 px canvas. Standard 4:3 ratio fits most laptop displays without scrolling; 32×24 = 768 cells gives Phase 4 block density math sensible whole numbers (6% → ~46 blocks).

### §3.16 Base snake speed

**Q:** What is the Phase 1 starting tick rate?
**A:** **6 cells/sec** at Phase 1 start, ramping to 8 cells/sec by the Phase 1→2 gate via score-based intra-phase scaling (one cell/sec per 25 score). Phase transitions then re-baseline. Phase 5 level-up bonus stacks on top of the current intra-phase ramp.

### §3.17 Wall behavior

**Q:** Do walls kill the snake, or wrap?
**A:** **Walls kill across all phases.** Wrap-around is a different game; consistency across phases is more valuable than the wrap variant's softer learning curve. The Ambush and bunker obstacles already add forgivable failure modes.

### §3.18 Direction reversal protection

**Q:** What prevents the snake from instantly reversing into itself?
**A:** **Input is debounced to one direction change per tick**, and any input that is the direct opposite of the current heading is rejected (not queued). This handles the "double-tap into yourself" failure mode that plagues naive implementations.

### §3.19 What happens to the patrol on phase transition

**Q:** Does the patrol's position/length reset on phase transition?
**A:** **No — patrol position, length, direction, and accumulated score all persist across phase gates.** Only the world layer changes (background palette, world events, obstacles). This is the core "single state machine" insight from the descriptive draft's implementation notes.

### §3.20 Patrol spawn position on run start

**Q:** Where does the patrol start on a fresh run?
**A:** **Center of the grid, length 3, heading right.** Standard arcade Snake spawn; predictable so the first few seconds of every deployment feel identical.

### §3.21 PATROL LOST screen copy (canonical)

**Q:** What does the run-end screen say?
**A:** **"PATROL LOST"** as the headline — this exact string is canonical, not "GAME OVER" or "YOU DIED". Below it: **"Final Score: N"**, then **"Phase reached: P"** (Phase 5 displays the sector as well, e.g., "Phase 5 — Sector 4"), then **"Press R to redeploy"** at the bottom (Space also restarts; the visible prompt remains "Press R to redeploy"). The field-ops naming carries through to the loss screen so the aesthetic stays cohesive at the run boundary. See §13.5 for the AC binding and §3.24 for the "SECTOR CLEARED" win-screen variant.

### §3.22 Pause behavior

**Q:** Can the player pause?
**A:** **Yes, P or Esc toggles pause.** A paused game shows a "HOLD POSITION" overlay and freezes the tick clock, Ambush timers, wormhole countdowns, and bonus-pickup expirations — pause must not be an exploit for waiting out an Ambush telegraph.

### §3.23 Restart at PATROL LOST vs. mid-game

**Q:** Does restart work mid-game, or only at the PATROL LOST screen?
**A:** **R redeploys only from the "PATROL LOST" screen.** Mid-game R is ignored to prevent rage-quit muscle memory from nuking a Phase 4 run.

### §3.24 What if the patrol fills the board?

**Q:** Phase 5 with a long patrol and dense bunkers — what happens if the patrol covers every reachable cell?
**A:** **The next supply cache spawn fails silently for 1 second, then the game declares "SECTOR CLEARED" as a win state.** Player advances to the next Phase 5 sector (if applicable) or wins the run (if at sector 10+). Vanishingly rare but the failure mode (cache can't spawn → game freezes) must be handled.

### §3.25 Multiple field rations on screen at once

**Q:** Can two field-ration drops be on the board simultaneously?
**A:** **No — at most one field-ration drop at a time.** Multiple drops dilute the "chase or skip" decision the player should be making.

### §3.26 Wormhole entry rules in Phase 5

**Q:** Do both wormholes lead to the same next-sector state? Do their positions matter?
**A:** **Either wormhole advances to the next sector; positions are randomized but always at least 8 cells apart.** Two wormholes exist for patrol routing freedom, not for distinct outcomes.

### §3.27 What happens to in-flight bonuses on phase transition

**Q:** Field rations, active score multiplier, held Cover — do these survive a phase transition?
**A:** **Active timed effects (multiplier, sprint boost) survive transitions; on-board pickups (uncollected field rations) despawn.** Buffs the player "earned" continue; world objects belong to their world layer.

### §3.28 Reinforcement (bonus life) HUD display

**Q:** How are remaining reinforcements shown?
**A:** **A row of small chevron / squad-marker icons in the top HUD, max 5 visible.** Drops above 5 simply do not spawn (§3.9); the HUD therefore never needs to handle overflow. (Implementer may use a heart icon if a chevron / squad marker would be unreadable at the chosen pixel size — the constraint is "5 distinct markers in the top HUD," not the specific glyph.)

### §3.29 Ambush behavior when paused

**Q:** Already answered in §3.22 — Ambush timers freeze on pause.

### §3.30 Multiple Ambushes at once

**Q:** Can two Ambush sweeps be present simultaneously?
**A:** **No — at most one Ambush in flight or in telegraph at any time.** Stacking Ambushes breaks the "readable trajectory" property.

### §3.31 Ambush vs. Cover (Shield) interaction

**Q:** If the player has Cover held, does the Ambush consume the Cover or still cut?
**A:** **Cover consumes the hit; no cut occurs.** Consistent with the Cover's "one-collision forgiveness" specification in the descriptive draft.

### §3.32 Ambush vs. bunkers interaction

**Q:** Does the Ambush sweep pass through Phase 4 bunkers, or does it get stopped?
**A:** **The Ambush passes through bunkers.** The Ambush is an event (incoming fire / sweeping line), not a physical object; bunkers are walls for the patrol only. (An Ambush stopped by a bunker would teach players to hide behind bunkers, which is the opposite of the intended dynamic.)

### §3.33 Wormhole vs. obstacle overlap

**Q:** Can a wormhole spawn on a bunker, on the patrol, or on a supply cache?
**A:** **No to all three.** Wormholes spawn only on empty cells; if no two cells ≥ 8 apart are empty, the countdown extends by 5 seconds and tries again.

### §3.34 Supply cache respawn after pickup

**Q:** Is there a delay between picking up a supply cache and the next one appearing?
**A:** **No delay — a new cache spawns on the same tick the old one is consumed**, except for the "sector cleared" case in §3.24.

### §3.35 Reinforcements at run start

**Q:** How many reinforcements does a fresh run begin with?
**A:** **One life (the patrol itself) plus zero reserve reinforcements.** Reinforcements accumulate via §3.9 drops and Phase 2-onwards bonus pickups (§10).

### §3.36 Death respawn position in Phase 5

**Q:** When the patrol is lost in Phase 5 with a reserve reinforcement, where do they respawn?
**A:** **Center of current Phase 5 sector, length 3, heading right** — same as run start, but the current sector, its bunker layout, and accumulated score are preserved.

### §3.37 Visual readability of phase transition

**Q:** How is the player told a phase changed?
**A:** **A 2-second full-screen banner**: "Phase N: <name>" centered, with a brief fade-in/fade-out. The patrol continues moving during the banner (game does not pause) so banner-spam doesn't break flow.

### §3.38 Tactical callouts (optional flair)

**Q:** Are short on-screen status callouts allowed during gameplay?
**A:** **Yes, optionally.** Implementers may display brief (1–1.5 s) tactical callouts in a low-key HUD corner on certain events: "Supply cache acquired" on regular pickup, "Rations secured" on field-ration pickup, "Contact left/right/front" when an Ambush telegraphs, "Cover holding" on Cover pickup, "Patrol continuing" on a survived Ambush cut, "Sector transfer" on wormhole entry. Callouts are decorative — they may be omitted entirely without affecting Acceptance Criteria. When present they must not occlude the play area and must fade out automatically.

### §3.39 Initial input before player presses a key

**Q:** Does the patrol start moving immediately, or wait for first input?
**A:** **Wait for first input on Phase 1 only; auto-resume movement on respawn and phase transitions.** New players need a beat to read the screen; mid-run pauses don't.

---

## §4. Persistent Mechanics Across All Phases

### §4.1 Score is monotonic and visible

Score increases on supply pickup (supply caches and field rations); never decreases. Score displays in the top-left HUD at all times. Score persists across phase gates, patrol-lost-with-respawn in Phase 5, and sector transfers in Phase 5.

### §4.2 Reinforcements (bonus lives)

Reinforcements display as a row of squad-marker icons in the top HUD (top-right). Maximum 5 in reserve (§3.9, §3.28). A reinforcement is consumed when the patrol is lost; the patrol respawns per §3.20 (run start) or §3.36 (Phase 5 mid-run). Run ends when reserve is empty and the patrol is lost.

### §4.3 Patrol controls

- **Arrow keys and WASD** both supported.
- Direction reversal protection per §3.18.
- **P or Esc** toggles pause / hold position (§3.22).
- **R or Space** redeploys only from the "PATROL LOST" screen (§3.23).

### §4.4 Patrol growth

Growth is +1 segment on a supply cache, +1 segment on field rations, 0 on score multiplier / Cover / sprint boost pickups. The Ambush reduces length per §3.8.

### §4.5 Wall and self-collision

Wall and self-collision lose the patrol across all phases (§3.17). On loss: consume a reserve reinforcement and respawn if available, else "PATROL LOST."

### §4.6 Phase progression is unidirectional within a run

A patrol that has reached Phase 4 does not regress to Phase 3 on respawn; they respawn in Phase 4. Phase 5 losses respawn at the current Phase 5 sector (§3.36).

---

## §5. Phase 1 — Night Recon (Classic)

### §5.1 Cynefin classification

**Clear.** Well-known mechanics, deterministic rules, no novel interactions. Solution is a recipe: implement standard arcade Snake under a night-recon skin.

### §5.2 Visual

Low-visibility night-recon mode — grayscale only. Light gray patrol on near-black background, with subtle dark-gray gridlines (1px, 10% opacity). Supply caches render in a slightly lighter gray than background so they read against terrain. No color, no embellishment. The player sees "this is a training exercise — original Snake under cover of darkness." Phase 1's grayscale is intentional: it sets the field-ops mood without committing to the full camo palette until Phase 2.

### §5.3 Mechanics

- Patrol spawns center, length 3, heading right (§3.20), motionless until first input (§3.39).
- Base speed 6 cells/sec (§3.16), ramping to 8 cells/sec by the gate.
- Supply caches only — no field rations, no bonuses, no random drops in Phase 1.
- Wall and self-collision per §4.5.

### §5.4 Gate

**Score 50 → Phase 2** (§3.1, §8.1).

### §5.5 Acceptance Criteria

- [ ] Patrol spawns at center, length 3, heading right, on game start.
- [ ] Patrol does not move until first directional input.
- [ ] Arrow keys and WASD both control movement.
- [ ] Direction reversal protection blocks instant 180° turns.
- [ ] A supply cache spawns on a random empty cell.
- [ ] Picking up a supply cache increments score by 1 and grows the patrol by 1 segment.
- [ ] Score displays in top-left HUD.
- [ ] Wall collision loses the patrol.
- [ ] Self-collision loses the patrol.
- [ ] Speed ramps from 6 to 8 cells/sec as score climbs from 0 to 50.
- [ ] Phase 1→2 transition banner appears on reaching score 50.
- [ ] Visual palette is grayscale (light-gray patrol on near-black background, no colored elements).

---

## §6. Phase 2 — Dawn Patrol (Color and Upgrade)

### §6.1 Cynefin classification

**Clear.** Adds layered mechanics (full camo palette, field rations, one upgrade) on top of Phase 1 — still recipe-followable, no emergent interactions. Narratively: dawn breaks, the patrol can see its surroundings, and the full field-ops aesthetic emerges.

### §6.2 Visual — camo palette

Full camo palette unlocks. The dominant tones are olive drab, coyote brown, tan, dark green, and black on an earth-tone background. **Implementers must avoid neon, fluorescent, or saturated arcade hues** — the visual identity of the game is muted military-field. Suggested base palette:

| Element | Color | Notes |
|---|---|---|
| Background | #2b2d24 (dark olive / field) | Terrain-inspired; may use a subtle two-tone band or low-contrast grid texture for "terrain" feel |
| Grid lines | #353727 (very subtle) | Almost invisible; reads as terrain texture |
| Patrol body — segment pattern | alternating olive #556b2f / tan #c2b280 / coyote brown #8b6f47 / black #1a1a14 patches, one tone per segment | Blocky-camo per segment; not gradient |
| Patrol head | #3b4a1f (dark olive, distinguishable from body) | Larger eye dot or directional notch for orientation |
| Supply cache (regular pickup) | tan #c2b280 fill with dark brown #4a3823 outline; optional 1-px strap markings | Looks like a small crate / ammo box; not a fruit |
| Field rations (bonus pickup) | coyote brown #8b6f47 fill with dark outline, slight gold accent #b8860b for "higher-tier supply drop" | Distinguishable from supply cache, still earth-toned |
| HUD text | #e5e0c8 (parchment / off-white) | Stencil or monospace feel preferred |
| Panel / border framing | #4a4632 (dark khaki) thin border around canvas | "Finished mini-game" framing, not a bare canvas |

Implementer may substitute their own palette provided: (1) the patrol body uses **at least three** earth-tone patches alternating across segments to read as "camouflage"; (2) supply cache and field rations are visually distinct from patrol and from each other but both read as field-ops supplies (not fruit / candy / gems); (3) the palette stays consistent through Phase 5 — no neon, no saturated arcade hues at any phase; (4) the canvas sits inside a thin panel / border frame rather than floating on a bare page.

### §6.3 Field rations (bonus pickup)

- Appears every **20–35 seconds** (uniform random) starting at Phase 2 entry. Themed as a higher-tier supply drop / care package.
- At most one on-board at a time (§3.25).
- Lifetime on field: **8 seconds**; vanishes (extracted / spoiled) if not collected.
- Worth **5 points** (vs. 1 for a regular supply cache).
- Grows patrol by 1 segment.

### §6.4 Upgrade — Scavenger Training

- Active for the rest of the run. Themed as the patrol learning to pull nearby supplies in (foraging instinct).
- Pulls supply caches and field rations within a **1.5-cell radius** toward the patrol head at 0.5 × patrol speed.
- Pull is paused while the patrol is mid-Ambush-cut animation (§3.8) for visual clarity.
- Scavenger Training does not pull reinforcements, Cover, multipliers, or sprint boosts — only supplies (caches + rations).

### §6.5 Gate

**Score 150 → Phase 3** (§3.1, §8.1).

### §6.6 Acceptance Criteria

- [ ] Camo palette displays (patrol body uses ≥ 3 alternating earth-tone patches; background, supply cache, and field rations all distinct and earth-toned).
- [ ] Patrol head is visually distinguishable from body.
- [ ] Field rations spawn every 20–35 s on a random empty cell.
- [ ] Field rations despawn after 8 s if uncollected.
- [ ] Field rations are worth 5 points; pickup grows the patrol by 1.
- [ ] Phase 1 mechanics (supply cache, wall/self collision, etc.) still work.
- [ ] Scavenger Training upgrade pulls supplies within 1.5 cells of head.
- [ ] A "Phase 2: Dawn Patrol" banner displays on entry.
- [ ] Phase 2→3 transition banner appears on reaching score 150.
- [ ] At most one field-ration drop on screen at a time.

---

## §7. Phase 3 — Ambush

### §7.1 Cynefin classification

**Complicated.** Adds a hostile world event with telegraph timing, dodge windows, and Cover interactions. Implementation requires care (cut location math, telegraph rendering, Cover consume) but no emergent behaviors.

### §7.2 Visual

Same camo palette as Phase 2; the Ambush sweep is rendered as a dark steel / gunmetal elongated rectangle (~5 cells long × 1 cell wide, color #3a3a36) with a subtle motion blur during the strike — read as incoming sweeping fire / a sniper round rather than a chrome blade. Telegraph is a translucent gunmetal "sight line" along the planned trajectory, pulsing at 2 Hz. (No neon red / yellow flash — the threat reads in muted tones, consistent with the field-ops palette.)

### §7.3 Ambush mechanic

- Appears every **12–20 s** (uniform random) — see §3.5.
- **1.5-second telegraph** showing the sight line — see §3.6.
- Sweep crosses the board in **0.4 s** along a straight line — see §3.7.
- On hit: cut at the strike point, head-side segments survive as the remaining patrol, tail-side segments are lost as casualties — see §3.8.
- Cover consumes the hit (§3.31).
- Ambush passes through bunkers (§3.32).
- At most one Ambush in flight or telegraph at a time (§3.30).

### §7.4 Cover bonus (unlocks here)

- Appears every **60–90 s** starting in Phase 3. Themed as a piece of hard cover / sandbag stack the patrol drags along.
- On pickup, patrol holds one Cover; HUD shows a small shield / sandbag icon.
- On the next collision (Ambush, wall, self, or bunker), Cover absorbs the hit and the patrol survives untouched.
- Maximum one Cover held at a time; pickups above the cap do not spawn.

### §7.5 Gate

**Score 350 → Phase 4** (§3.1, §8.1).

### §7.6 Acceptance Criteria

- [ ] Ambush appears every 12–20 s after Phase 3 entry.
- [ ] Ambush telegraph (sight line) displays for 1.5 s before strike.
- [ ] Ambush sweep crosses board in 0.4 s along straight line from one edge to another.
- [ ] Ambush cut removes all patrol segments behind the strike point; head-side segments survive.
- [ ] Patrol survives an Ambush cut (does not lose unless length drops below 1).
- [ ] If patrol length is 1 and Ambush cuts the head, patrol is lost.
- [ ] Cover pickup appears every 60–90 s starting in Phase 3.
- [ ] Cover absorbs the next collision (Ambush, wall, self, or bunker) with no damage.
- [ ] HUD displays Cover-held state when player has Cover.
- [ ] At most one Ambush on screen at a time (in telegraph or sweep).
- [ ] At most one Cover held at a time.
- [ ] A "Phase 3: Ambush" banner displays on entry.
- [ ] Phase 3→4 transition banner appears on reaching score 350.
- [ ] Phase 2 mechanics (camo palette, field rations, Scavenger Training) still work.

---

## §8. Phase 4 — Bunker Run (Obstacles)

### §8.1 Cynefin classification

**Complicated.** Static bunkers require generation, placement validation (flood-fill connectivity check), and interaction with all prior mechanics — but the rules are deterministic and analyzable.

### §8.2 Visual

Bunkers render as sandbag-gray (#6b6453) rounded squares with a 2-px darker border (#3d382a) and an optional 1-px lighter top edge to suggest a 3D bunker / sandbag stack. Visually distinct from patrol, supplies, and background. The single canonical vocabulary across Phase 4 and Phase 5 is **"bunker"** — the rest of this PRD uses that label for every static obstacle (avoiding mixed terms like "barricade" / "rubble" / "abandoned crate" so the AC language stays single-named).

### §8.3 Bunker generation

- **6% density** (§3.3) → ~46 bunkers on a 32×24 grid.
- Placed by uniform random selection followed by flood-fill validation: the largest connected open region must cover ≥ 90% of remaining cells. Discard and retry placements that violate the connectivity rule.
- Bunkers may not spawn on or adjacent (in 4-connectivity) to the patrol's current head position at Phase 4 entry.
- Bunkers are fixed for the duration of Phase 4 (regenerated only on Phase 5 sector transfers).

### §8.4 Bunker interactions

- Patrol-bunker collision loses the patrol (or consumes a Cover).
- Supply caches do not spawn on bunkers.
- Ambush passes through bunkers (§3.32).
- Bonus pickups (Cover, multiplier, sprint boost, reinforcement) do not spawn on bunkers.

### §8.5 Sprint boost bonus (unlocks here)

- Appears every **45–75 s** starting in Phase 4. Themed as a quick adrenaline / sprint reserve.
- On pickup, HUD shows a sprint-boost icon; player presses **Shift** to activate.
- While Shift is held, patrol moves at 1.5× current speed; consumes the sprint boost charge after 3 seconds of continuous use OR when the player releases Shift.
- Max one sprint boost held at a time.

### §8.6 Gate

**Score 700 → Phase 5** (§3.1, §8.1).

### §8.7 Acceptance Criteria

- [ ] ~46 static bunkers spawn on Phase 4 entry (6% of 768 cells).
- [ ] Bunker layout passes connectivity check (≥ 90% of empty cells in one region).
- [ ] Bunkers do not spawn adjacent to patrol head at Phase 4 entry.
- [ ] Patrol is lost on bunker collision (or consumes Cover).
- [ ] Supply caches never spawn on a bunker.
- [ ] Ambush passes through bunkers unchanged.
- [ ] Sprint boost pickup appears every 45–75 s.
- [ ] Shift activates sprint boost (1.5× speed for up to 3 s).
- [ ] HUD displays sprint-boost-held state.
- [ ] A "Phase 4: Bunker Run" banner displays on entry.
- [ ] Phase 4→5 transition banner appears on reaching score 700.
- [ ] Phase 3 mechanics (Ambush, Cover) still work amid bunkers.

---

## §9. Phase 5 — Sector Transfer (Wormholes and Sectors)

> **Wormhole is a traversal mechanic, not a display element.** The patrol navigates into a wormhole to transit between sectors. The PRD specifies WHEN wormholes appear, WHERE they may spawn, and WHAT happens when the patrol enters one — but NOT how the wormhole itself is rendered. The implementer chooses a readable visible transition marker that fits the field-ops aesthetic (avoiding neon and saturated arcade hues per §6.2). Specific colors, shapes, glyphs, animations, and per-wormhole differentiation are explicitly NOT prescribed.

### §9.1 Cynefin classification

**Complicated.** Multiple interlocking systems (wormhole countdown, sector progression, escalating bunker density, tempo cap, respawn-on-current-sector) but no emergent behavior. Edge case load is highest of any phase.

### §9.2 Sector model

- Phase 5 is an open-ended sequence of sectors: Phase 5 Sector 1 (S1), S2, S3, …
- Each sector regenerates bunkers per §9.3, recalculates patrol tempo per §9.4, and spawns a new wormhole pair after the countdown per §9.5.
- Soft visual cap at S10 (§3.12); mechanics still scale (or hit caps).

### §9.3 Bunker density per sector

`density(sector) = min(0.06 + 0.015 × (sector − 1), 0.18)` — see §3.4.

| Sector | Density | Bunkers (32×24) |
|---|---|---|
| S1 | 6.0% | 46 |
| S2 | 7.5% | 58 |
| S3 | 9.0% | 69 |
| S5 | 12.0% | 92 |
| S7 | 15.0% | 115 |
| S9+ | 18.0% (cap) | 138 |

Connectivity check (≥ 70% of empty cells in one region) per §3.4.

### §9.4 Tempo per sector

`tempo_multiplier(sector) = min(1 + 0.08 × (sector − 1), 1.80)` — see §3.11.

Applied as a multiplier on top of the current intra-phase score-driven speed ramp. The cap fires at S11. Operational tempo increases each sector — the phrasing used in HUD callouts.

### §9.5 Wormhole countdown

> **Reminder (per §9 header):** the wormhole is a traversal mechanic the patrol drives into; its on-screen rendering is the implementer's call within the field-ops aesthetic. This sub-section specifies timing, placement constraints, and lifetime — not visual prescription. The only HUD spec is the countdown readout in `Next wormhole: NN s`; whether the wormhole itself is a glow, a marker, a frame, a swirl, an opening in the terrain, or some other readable transition cue is left open.

- On Phase 5 entry and on every Phase 5 sector transfer, a **30-second countdown** runs (§3.10) during which the patrol accumulates score in the current sector.
- HUD displays "Next wormhole: NN s" in the top-center.
- After countdown, two wormholes spawn on empty cells ≥ 8 cells apart (§3.26, §3.33). If placement fails (no valid pair), countdown extends by 5 s and re-tries.
- Wormholes persist until entered or the patrol is lost.

### §9.6 Wormhole entry

- Patrol head entering either wormhole triggers sector transfer.
- Sector transfer: patrol retains length, score, upgrade, held bonuses (Cover, sprint boost), heading, and remaining reinforcements.
- Patrol repositions to center of the new sector, length unchanged (or 3 minimum if the transfer has shortened it for some edge case — never less than 3).
- Bunkers regenerate per §9.3, tempo updates per §9.4, countdown restarts per §9.5.

### §9.7 Patrol loss in Phase 5

- If reinforcements remain: respawn at center of current sector (§3.36), keep score, bunkers unchanged, countdown unchanged, lose held bonuses (Cover, sprint boost) but retain Scavenger Training (upgrade is permanent).
- If reinforcements are 0: PATROL LOST.

### §9.8 Win condition

There is no fixed win. Run ends on loss-with-no-reinforcements. "SECTOR CLEARED" of S10+ (§3.24) ends the run with a celebratory variant of the PATROL LOST screen — same field-ops framing but with the cleared-sector callout in place of the loss copy.

### §9.9 Acceptance Criteria

- [ ] Phase 5 entry shows a 30 s countdown to the first wormhole pair.
- [ ] After countdown, two wormholes spawn on empty cells ≥ 8 cells apart.
- [ ] Entering either wormhole advances to the next Phase 5 sector.
- [ ] Each sector regenerates bunkers at the density specified in §9.3.
- [ ] Each sector increases tempo per §9.4 (capped at +80% by S11).
- [ ] Score, length, upgrade, and reinforcements persist across sector transfers.
- [ ] Held Cover and sprint boost persist across sector transfers.
- [ ] Loss in Phase 5 respawns at current sector center if reinforcements remain.
- [ ] Loss in Phase 5 with no reinforcements ends the run.
- [ ] HUD displays current Phase 5 sector number and "Next wormhole: NN s" countdown.
- [ ] A "Phase 5: Sector Transfer" banner displays on entry.
- [ ] Sector-transfer banner ("S2", "S3", …) displays on wormhole entry.
- [ ] All prior phase mechanics (Ambush, Scavenger Training, camo palette, field rations, bunkers, Cover, sprint boost) still work.

---

## §10. Random Bonus Appearance Spec

> Per-phase matrix of what spawns when. Cadences are uniform-random intervals; the lower bound is the minimum, the upper bound is the maximum.

### §10.1 Appearance matrix

| Bonus | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|---|---|---|---|---|---|
| Supply cache | always present (1 on board) | same | same | same | same |
| Field rations | — | 20–35 s | 20–35 s | 20–35 s | 20–35 s |
| Reinforcement | 90–150 s | 90–150 s | 90–150 s | 90–150 s | 90–150 s |
| Score multiplier (2×, 10 s) | — | 60–90 s | 60–90 s | 60–90 s | 60–90 s |
| Cover (1-hit forgiveness) | — | — | 60–90 s | 60–90 s | 60–90 s |
| Sprint boost (3-s charge) | — | — | — | 45–75 s | 45–75 s |

### §10.2 Spawn rules

- All pickups spawn on empty cells (not on patrol, supply cache, bunkers, wormholes, or other pickups).
- All pickups have a **10-second on-field lifetime** before they despawn uncollected (except field rations, which is 8 s per §6.3).
- Cadence timers begin counting at phase entry and run continuously thereafter, paused during pause and during the PATROL LOST screen.
- Cadence timers are independent — reinforcement can spawn while a multiplier is on the field.

### §10.3 Held vs. instant effects

| Bonus | Type | Held? |
|---|---|---|
| Field rations | Instant (score + grow) | No |
| Reinforcement | Instant (adds to reserve) | No |
| Score multiplier | Timed (10 s of 2×) | No (active immediately) |
| Cover | Held until consumed | Yes (HUD icon, max 1) |
| Sprint boost | Held (Shift to activate) | Yes (HUD icon, max 1) |

---

## §11. Effort Forecast (Per Phase)

> Estimates are for the implementing agent generating the full HTML file. Phase estimates include the cumulative complexity of all prior phases (e.g., Phase 5 "implement" includes wiring Ambush + bunkers + wormholes all together).

### §11.1 Per-phase forecast

| Phase | Plan turns / tokens | Implement turns / tokens | Test turns / tokens | Total | Confidence |
|---|---|---|---|---|---|
| §5 Phase 1 (Night Recon) | 2 / 1.5k | 6 / 4k | 2 / 1.5k | **10 turns / 7k** | high |
| §6 Phase 2 (Dawn Patrol) | 1 / 1k | 4 / 3k | 2 / 1.5k | **7 turns / 5.5k** | high |
| §7 Phase 3 (Ambush) | 2 / 1.5k | 6 / 5k | 3 / 2k | **11 turns / 8.5k** | medium |
| §8 Phase 4 (Bunker Run) | 2 / 1.5k | 5 / 4k | 3 / 2k | **10 turns / 7.5k** | medium |
| §9 Phase 5 (Sector Transfer) | 3 / 2k | 8 / 6k | 4 / 3k | **15 turns / 11k** | medium |
| **Total (cumulative)** | **10 turns / 7.5k** | **29 turns / 22k** | **14 turns / 10k** | **53 turns / ~40k** | medium |

### §11.2 Confidence rationale

- Phase 1 and 2 are recipe-followable (Cynefin: clear) → high confidence.
- Phase 3, 4, 5 involve interacting systems and tuning loops → medium confidence; the agent may need 1–2 extra turns to refine Ambush dodge feel or bunker placement validity.

### §11.3 What "test" turns cover

Manual playthrough of each phase, verifying every Acceptance Criteria checkbox in §5.5, §6.6, §7.6, §8.7, §9.9. Not automated tests — this is a single-file artifact with no harness.

---

## §12. Functional Gate Definition

### §12.1 Gate thresholds and rationale

| Gate | From → To | Threshold | Cumulative score | Rationale |
|---|---|---|---|---|
| G1 | Phase 1 → Phase 2 | 50 | 50 | "A few minutes" of night-recon training — enough to learn rhythm, not enough to bore. |
| G2 | Phase 2 → Phase 3 | 150 (+100) | 150 | Field rations (5 pts each) make 100 points achievable in 3–5 min if the patrol chases rations. |
| G3 | Phase 3 → Phase 4 | 350 (+200) | 350 | Ambush setbacks slow scoring; +200 reflects the friction without becoming punitive. |
| G4 | Phase 4 → Phase 5 | 700 (+350) | 700 | Bunkers + Ambush together; +350 ensures Phase 5 entry feels like a real accomplishment. |

### §12.2 Gate curve shape

Roughly 2× growth (50 → 150 → 350 → 700). This is faster than exponential at the start (encourages Phase 2 entry quickly) and slows toward the end (Phase 5 entry is a milestone). The curve was tuned so a skilled player reaches Phase 5 in ~15 minutes and a casual player clears Phase 2–3 in a sitting.

### §12.3 Gate transition behavior

- On reaching the threshold mid-tick: complete the current tick, then trigger the phase-transition banner (§3.37) and re-baseline speed (§3.16). Score does not reset.
- Patrol position, length, direction, held bonuses, upgrade, and remaining reinforcements all persist.

---

## §13. Acceptance Criteria — Whole-Game Level

> These are the end-to-end criteria across the entire game. Per-phase ACs are in §5.5, §6.6, §7.6, §8.7, §9.9.

### §13.1 Delivery

- [ ] Output is exactly one HTML file.
- [ ] File runs locally by double-clicking in Chrome, Edge, Firefox, or Safari (modern versions).
- [ ] No external dependencies (no `<script src=...>`, no `<link rel="stylesheet" href=...>`, no CDN, no image / audio assets).
- [ ] All HTML, CSS, and JavaScript inline.
- [ ] File name follows the convention in §14.

### §13.2 Cross-phase persistence

- [ ] Score increases monotonically across all phases.
- [ ] Patrol position, length, and direction persist across phase gates.
- [ ] Scavenger Training upgrade persists from Phase 2 entry through PATROL LOST.
- [ ] Held Cover persists across Phase 3, 4, 5 gates.
- [ ] Held sprint boost persists across Phase 4, 5 gates.
- [ ] Reinforcements persist across all gates and Phase 5 sector transfers.

### §13.3 Controls

- [ ] Arrow keys move the patrol.
- [ ] WASD move the patrol.
- [ ] P or Esc hold position / resume.
- [ ] Shift activates a held sprint boost.
- [ ] R or Space redeploy from the PATROL LOST screen.
- [ ] Direction reversal protection rejects opposite-of-current-heading input.

### §13.4 HUD

- [ ] Score visible at top-left.
- [ ] Reinforcements (squad-marker row, max 5) visible at top-right.
- [ ] Current phase name visible somewhere in the HUD.
- [ ] In Phase 5: current sector (S1, S2, …) and "Next wormhole: NN s" countdown visible.
- [ ] Held Cover icon when player has Cover.
- [ ] Held sprint-boost icon when player has a sprint boost.
- [ ] Active multiplier icon and remaining duration when active.

### §13.5 PATROL LOST screen

- [ ] Displays "PATROL LOST" as the headline — this exact copy is canonical (not "GAME OVER", not "YOU DIED").
- [ ] Displays "Final Score: N" below the headline.
- [ ] Displays "Phase reached: P" below that (with sector number for Phase 5, e.g., "Phase 5 — Sector 4").
- [ ] Displays "Press R to redeploy" at the bottom — this exact copy is canonical (Space also accepted as the input).
- [ ] Visually distinct from gameplay (dimmed background or overlay).
- [ ] On "SECTOR CLEARED" (S10+ perfect-clear win, §3.24): same screen layout but headline reads "SECTOR CLEARED" instead of "PATROL LOST".

### §13.6 Fairness invariants

- [ ] Supply caches never spawn on the patrol.
- [ ] Supply caches never spawn on a bunker (Phase 4+).
- [ ] Bonuses never spawn on the patrol, bunkers, supply caches, wormholes, or other bonuses.
- [ ] Bunkers never spawn adjacent to patrol head at Phase 4 entry.
- [ ] Wormholes never spawn on patrol, supply caches, bunkers, or other wormholes; pair distance ≥ 8 cells.
- [ ] Ambush passes through bunkers; Ambush is never blocked.
- [ ] Ambush telegraph is always visible for 1.5 s before strike.

### §13.7 Polish

- [ ] Phase 1 is grayscale (night-recon).
- [ ] Phase 2+ uses the camo palette in §6.2 (or implementer's equivalent earth-tone palette satisfying the §6.2 constraints).
- [ ] No neon or saturated arcade hues appear in any phase.
- [ ] Patrol body uses ≥ 3 alternating earth-tone segment colors so it reads as camouflage at Phase 2+.
- [ ] Supply caches read as crates / ammo boxes (not fruit or candy); field rations read as a higher-tier supply drop.
- [ ] Visual language is consistent from Phase 2 through Phase 5 (no jarring palette swaps; aesthetic remains field-ops throughout).
- [ ] Canvas sits inside a thin panel / border frame; HUD typography reads as stencil / monospace / parchment.
- [ ] Phase transition banners display for 2 seconds with fade-in/fade-out.
- [ ] No commentary text or chrome outside the game canvas + HUD (optional tactical callouts per §3.38 are allowed; they sit inside the HUD area and auto-fade).

---

## §14. File Naming Convention

### §14.1 Convention

The output file is named:

```
snake_[model].html
```

Where `[model]` is the short lowercase identifier of the implementing model (e.g., `opus`, `sonnet`, `haiku`, `gpt5`, `gemini-pro`).

### §14.2 Substitution rule

- Use only ASCII lowercase letters, digits, and hyphens.
- Strip vendor prefixes (`claude-opus-4-7` → `opus-4-7` or just `opus`; `gpt-4o` → `gpt4o`).
- If a version suffix is meaningful, include it with a hyphen (`snake_opus-4-7.html`).

### §14.3 Fallback when the model name is unknown

If the implementing agent cannot determine its own model name (e.g., the runtime does not expose it), name the file **`snake_sonnet.html`** as the canonical fallback and include a short comment at the top of the HTML file with whatever environment hint the agent has access to (e.g., `<!-- generated by Anthropic API, model id unavailable; using sonnet fallback -->`). `snake_sonnet.html` is the canonical default so that `ls snake_*.html` in an adopter's directory always has a stable baseline filename to diff against, even from runtimes that don't surface model IDs.

### §14.4 Why this convention exists

The adopter (benchmark operator) compares model outputs side-by-side. A consistent name + per-model suffix means a single `ls snake_*.html` lists every variant for diff-able comparison.

---

## §15. Implementation Prompt (Verbatim Payload)

> Adopters paste the block below into any coding model. It is the self-contained execution prompt and embeds the essentials from §1–§13. It is intentionally redundant with the rest of this PRD — that is the point: an adopter can use this prompt without shipping the full PRD.

```markdown
You are a senior front-end game developer who ships clean, self-contained
browser games in a single HTML file. Build "Snake — Evolving Five-Phase
Field Operation" as one standalone HTML file with inline HTML, CSS, and
JavaScript. The file must run by double-clicking it in any modern
browser (Chrome, Edge, Firefox, Safari). No external libraries, CDNs,
image / audio assets, or build tools.

# Premise

A browser Snake game styled as a field-ops patrol that escalates through
five gated phases. The patrol starts as a night-recon training exercise
(grayscale Snake) and progresses through a multi-sector deployment.
Each phase introduces a small number of new mechanics. Score, patrol
length, direction, reinforcements (reserve lives), and upgrades persist
across phase gates.

# Aesthetic — non-negotiable

- Field-ops / camouflage visual identity throughout.
- Muted earth-tone palette: olive drab, coyote brown, tan, dark green,
  black. No neon. No saturated arcade hues at any phase.
- Patrol body uses blocky-camo coloring per segment — alternating
  olive / tan / coyote brown / black patches across consecutive
  segments. Head is a distinguishable darker tone with a directional
  notch or eye dot.
- Supply caches (regular pickup) look like small crates / ammo boxes:
  tan fill, dark-brown outline, optional 1-px strap markings.
- Field rations (bonus pickup) look like a higher-tier supply drop —
  coyote-brown fill with a small gold accent. Still earth-toned.
- Background is a dark olive / field tone with very subtle gridlines or
  a low-contrast terrain texture. Canvas sits inside a thin dark-khaki
  border frame so it reads as a finished mini-game.
- HUD typography: stencil or monospace, parchment / off-white color.

# Grid and base rules

- 32 × 24 cell grid at 20 px per cell → 640 × 480 px canvas.
- Patrol starts at center, length 3, heading right. Patrol does not move
  until the player presses a direction key on Phase 1; thereafter it
  auto-resumes on respawn / phase transitions.
- Base speed 6 cells/sec at Phase 1 start, ramping +1 cell/sec per 25
  score within a phase. Phase 5 sectors apply +8 % per sector, capped at
  +80 % ("operational tempo increases").
- Walls lose the patrol. Self-collision loses the patrol.
- Direction reversal protection: reject inputs that are direct opposites
  of current heading. One direction change per tick.
- Controls: Arrow keys + WASD move. P or Esc toggles hold position.
  Shift activates a held sprint boost. R or Space redeploys only on
  PATROL LOST.

# Persistent HUD

- Score (top-left, monotonic, persists across phases).
- Reinforcements row (top-right, squad-marker / chevron icons, max 5;
  implementer may use a heart icon if a chevron is unreadable at chosen
  pixel size).
- Current phase name (Phase 5: also sector "S1" and "Next wormhole:
  NN s" countdown).
- Held bonus icons (Cover, sprint boost, active multiplier).
- Optional short-lived tactical callouts in a quiet HUD corner on
  events: "Supply cache acquired", "Rations secured", "Contact left",
  "Cover holding", "Patrol continuing", "Sector transfer". 1–1.5 s
  fade. Decorative only — never required.

# Phase 1 — Night Recon (Classic)

- Grayscale only — light-gray patrol on near-black background, subtle
  dark-gray gridlines. Night-recon / training-exercise mood.
- Supply caches only; +1 score, +1 segment. No field rations or other
  bonuses spawn in Phase 1.
- Gate: score 50.

# Phase 2 — Dawn Patrol (Color and Upgrade)

- Full camo palette unlocks (per the Aesthetic section above). Patrol
  head visually distinct from body; body alternates ≥ 3 earth-tone
  patches across segments.
- Field rations: every 20–35 s, one on board at a time, 8 s lifetime,
  +5 score, +1 segment.
- Scavenger Training upgrade: pulls supply caches and field rations
  within 1.5-cell radius toward the patrol head at 0.5 × patrol speed.
  Permanent for the run.
- Score multiplier bonus (2× for 10 s): every 60–90 s.
- Gate: score 150.

# Phase 3 — Ambush

- Ambush appears every 12–20 s. Telegraph (translucent gunmetal sight
  line pulsing at 2 Hz) shows for 1.5 s along the sweep path. Sweep
  crosses the board in 0.4 s along a straight line between two random
  edge cells on different sides. Rendered as a dark steel / gunmetal
  elongated rectangle — incoming fire, not a chrome blade.
- On hit: cut at strike point; head-side segments survive as the
  remaining patrol, tail-side segments are lost as casualties. Patrol
  survives unless length drops to 0.
- Ambush passes through bunkers. At most one Ambush in telegraph or
  sweep at a time.
- Cover bonus: every 60–90 s. Themed as hard cover / sandbag stack
  the patrol carries. Held in HUD; absorbs the next collision (Ambush,
  wall, self, bunker) with no damage. Max 1 held.
- Gate: score 350.

# Phase 4 — Bunker Run (Obstacles)

- 6 % of cells (~46 bunkers on 32×24) spawn as sandbag-gray rounded
  squares with a darker border at Phase 4 entry. Bunkers fixed for
  Phase 4. Use the single vocabulary "bunker" — not barricade / rubble
  / abandoned crate.
- Placement validated via flood-fill: largest open connected region ≥
  90 % of remaining cells. Bunkers do not spawn adjacent to patrol head
  at Phase 4 entry. Supply caches and bonuses never spawn on bunkers.
- Sprint boost bonus: every 45–75 s. Held in HUD. Shift activates 1.5×
  speed for up to 3 s of held activation.
- Gate: score 700.

# Phase 5 — Sector Transfer (Wormholes and Sectors)

The wormhole is a TRAVERSAL MECHANIC, not a display element. The patrol
navigates into a wormhole to transit between sectors. The PRD specifies
when wormholes appear, where they may spawn, and what happens on entry —
but the on-screen rendering is your call within the field-ops aesthetic
(no neon, no saturated arcade hues). Pick a readable visible transition
marker that fits.

- Open-ended sectors (S1, S2, ...). Each sector:
  - Bunker density: density(sector) = min(0.06 + 0.015 × (sector − 1),
    0.18). Connectivity check ≥ 70 %.
  - Tempo multiplier: min(1 + 0.08 × (sector − 1), 1.80). Operational
    tempo increases per sector.
  - 30 s countdown ("Next wormhole: NN s" in the HUD), then two
    wormholes spawn on empty cells ≥ 8 cells apart; they persist until
    entered or patrol is lost.
- Either wormhole advances to the next sector. Patrol retains length,
  score, upgrade, held bonuses, reinforcements; repositions to center.
- Loss with reinforcements remaining: respawn at center of current
  sector (length 3, bunkers unchanged); held Cover and sprint boost are
  lost; Scavenger Training retained.
- Visual soft cap at S10 (palette familiarity); mechanics still scale
  or hit caps. "Sector cleared" (patrol covers all reachable cells)
  ends the run as a win — same screen layout as PATROL LOST but the
  headline reads "SECTOR CLEARED".

# Bonus appearance cadence (cumulative across phases)

| Bonus | Cadence | First unlocked |
|---|---|---|
| Field rations | 20–35 s | Phase 2 |
| Reinforcement | 90–150 s | Phase 1 |
| Score multiplier (2×, 10 s) | 60–90 s | Phase 2 |
| Cover (1-hit forgiveness) | 60–90 s | Phase 3 |
| Sprint boost (3-s held, Shift) | 45–75 s | Phase 4 |

All pickups: 10 s on-field lifetime (8 s for field rations), one of each
type on board at a time, never spawn on patrol / supply cache / bunkers
/ wormholes / other pickups, max 5 reinforcements in reserve.

# Pause behavior

P or Esc toggles hold position (overlay "HOLD POSITION"). Pause freezes
the tick clock, Ambush timers, wormhole countdown, and bonus
expirations. Player cannot use pause to wait out an Ambush telegraph.

# Phase transitions

On gate threshold, complete current tick, then show a 2 s banner
"Phase N: <name>" with fade-in/out. Patrol continues moving during the
banner. Phase names: Phase 1 Night Recon, Phase 2 Dawn Patrol, Phase 3
Ambush, Phase 4 Bunker Run, Phase 5 Sector Transfer.

# PATROL LOST screen — canonical copy

Headline reads exactly "PATROL LOST" (this exact string, not "GAME
OVER", not "YOU DIED"). Below it: "Final Score: N", then "Phase
reached: P" (with sector for Phase 5, e.g., "Phase 5 — Sector 4"), then
"Press R to redeploy" at the bottom (also accept Space as the redeploy
input — the visible prompt remains "Press R to redeploy"). Visually
dimmed background. R or Space redeploys to Phase 1. On perfect-clear
win at S10+, swap the headline to "SECTOR CLEARED" but keep the same
layout.

# Visual palette (canonical — implementer may adjust within the Aesthetic constraints)

The canonical palette is olive drab, coyote brown, tan, black, dark
green, and other muted earth tones. Avoid neon and saturated arcade
colors at every phase.

- Background: #2b2d24 (dark olive / field) with subtle gridlines or a
  low-contrast terrain texture suggesting a patrol board
- Panel / border framing: #4a4632 (dark khaki) thin border around the
  canvas so the game reads as a finished mini-game, not a bare canvas
- Patrol body segments alternate in a blocky-camo pattern (one tone per
  segment) among:
  - Olive #556b2f, Tan #c2b280, Coyote brown #8b6f47, Black #1a1a14
- Patrol head: #3b4a1f (dark olive) — visually distinguishable from the
  body via a directional notch or eye dot
- Supply cache: tan #c2b280 fill, dark-brown #4a3823 outline, optional
  1-px strap markings — reads as a small crate / ammo box
- Field rations: coyote brown #8b6f47 fill, dark outline, small gold
  accent #b8860b — reads as a higher-tier care-package supply drop
- Bunkers: sandbag gray #6b6453 fill, #3d382a border
- HUD text: parchment #e5e0c8 (stencil or monospace feel preferred)
- Ambush: gunmetal #3a3a36
- Wormholes: NOT visually prescribed. The wormhole is a traversal
  mechanic the patrol drives into; render it as any readable transition
  marker that fits the field-ops aesthetic (no neon, no saturated
  arcade hues). Color, shape, animation, and per-wormhole
  differentiation are your call.

Phase 1 is grayscale / monochrome night-recon (low-visibility mode);
the camo palette emerges at Phase 2 as dawn breaks. The aesthetic
remains consistent from Phase 2 through Phase 5 — no jarring palette
swaps between phases.

# Output rules

- Provide the complete HTML file in a single fenced code block.
- File name: snake_[model].html where [model] is your short lowercase
  model identifier (e.g., snake_opus.html, snake_sonnet.html,
  snake_haiku.html). If your model identifier is unknown, use
  snake_sonnet.html as the fallback default and include a brief HTML
  comment at the top noting whatever runtime information you do have.
- Return only the code block. No commentary before or after.
```

---

## §16. Suggested Bead Breakdown

> Implementer's reference. The work decomposes into one epic per phase plus cross-cutting beads. Use this as a starting backlog if you are managing the work in `bd`. All beads are sized to the falcon "Effort Forecast" convention per §11.

### §16.1 Epic structure

```
EP-01 Foundation                (§16.2)  parent of FN-* beads
EP-02 Phase 1 Night Recon       (§16.3)  parent of P1-* beads
EP-03 Phase 2 Dawn Patrol       (§16.4)  parent of P2-* beads
EP-04 Phase 3 Ambush            (§16.5)  parent of P3-* beads
EP-05 Phase 4 Bunker Run        (§16.6)  parent of P4-* beads
EP-06 Phase 5 Sector Transfer   (§16.7)  parent of P5-* beads
EP-07 Polish & Ship             (§16.8)  parent of FIN-* beads
```

### §16.2 Foundation beads (EP-01)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| FN-01 | Bootstrap single-file HTML scaffold + canvas + HUD shell (with panel/border frame) | task | — | clear |
| FN-02 | Implement game loop and tick clock (pausable) | task | FN-01 | clear |
| FN-03 | Implement input handler (arrows + WASD + direction reversal protection) | task | FN-02 | clear |
| FN-04 | Implement patrol data model (segments, head, growth, length math) | task | FN-02 | clear |
| FN-05 | Implement supply cache spawn (rejection sampling against patrol) | task | FN-04 | clear |
| FN-06 | Implement HUD renderer (score, reinforcements, phase, held-bonus icons) | task | FN-01 | clear |
| FN-07 | Implement HOLD POSITION overlay + P/Esc toggle | task | FN-02 | clear |
| FN-08 | Implement PATROL LOST screen + R/Space redeploy | task | FN-04 | clear |

### §16.3 Phase 1 beads (EP-02)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| P1-01 | Wire grayscale night-recon palette + Phase 1 visuals | task | FN-01 | clear |
| P1-02 | Implement wall and self-collision loss | feature | FN-04 | clear |
| P1-03 | Implement intra-phase speed ramp (6 → 8 cells/sec by score 50) | task | FN-02 | clear |
| P1-04 | Implement Phase 1→2 gate detection + banner | feature | P1-03, FN-08 | clear |
| P1-05 | Verify §5.5 Acceptance Criteria | task | P1-01–P1-04 | clear |

### §16.4 Phase 2 beads (EP-03)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| P2-01 | Implement Phase 2 camo palette swap on gate (blocky-camo segments, crate-styled supply cache) | task | P1-04 | clear |
| P2-02 | Implement field rations (cadence, lifetime, score, despawn) | feature | FN-05 | clear |
| P2-03 | Implement Scavenger Training upgrade (1.5-cell radius pull on supplies) | feature | P2-02, FN-04 | clear |
| P2-04 | Implement score multiplier bonus (2× for 10 s, cadence 60–90 s) | feature | FN-05 | clear |
| P2-05 | Implement Phase 2→3 gate detection + banner | feature | P1-04 | clear |
| P2-06 | Verify §6.6 Acceptance Criteria | task | P2-01–P2-05 | clear |

### §16.5 Phase 3 beads (EP-04)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| P3-01 | Implement Ambush data model + spawn cadence (12–20 s) | feature | P2-05 | complicated |
| P3-02 | Implement Ambush telegraph render (1.5 s translucent gunmetal sight line) | feature | P3-01 | complicated |
| P3-03 | Implement Ambush sweep animation (0.4 s edge-to-edge) | feature | P3-01 | complicated |
| P3-04 | Implement cut-at-strike-point math (head-side survives, casualties drop) | feature | P3-03, FN-04 | complicated |
| P3-05 | Implement Cover bonus (held, HUD icon, absorb on collision) | feature | FN-05, P3-04 | complicated |
| P3-06 | Wire Ambush ↔ Cover interaction (absorb hit, no cut) | feature | P3-04, P3-05 | complicated |
| P3-07 | Implement Phase 3→4 gate detection + banner | feature | P2-05 | clear |
| P3-08 | Verify §7.6 Acceptance Criteria | task | P3-01–P3-07 | complicated |

### §16.6 Phase 4 beads (EP-05)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| P4-01 | Implement bunker data model + render (sandbag-gray rounded squares) | feature | P3-07 | complicated |
| P4-02 | Implement bunker placement (6 % density, rejection sampling) | feature | P4-01 | complicated |
| P4-03 | Implement flood-fill connectivity validation (≥ 90 %) | feature | P4-02 | complicated |
| P4-04 | Wire bunker ↔ patrol collision (bunker loses patrol, Cover absorbs) | feature | P4-01, P3-05 | complicated |
| P4-05 | Wire supply / bonus spawn rejection against bunkers | feature | P4-01, FN-05 | clear |
| P4-06 | Implement sprint boost bonus (held, Shift to activate, 3 s charge) | feature | FN-05 | complicated |
| P4-07 | Implement Phase 4→5 gate detection + banner | feature | P3-07 | clear |
| P4-08 | Verify §8.7 Acceptance Criteria | task | P4-01–P4-07 | complicated |

### §16.7 Phase 5 beads (EP-06)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| P5-01 | Implement Phase 5 sector model (S1, S2, …) | feature | P4-07 | complicated |
| P5-02 | Implement bunker density formula per sector + cap | feature | P5-01, P4-03 | complicated |
| P5-03 | Implement tempo-multiplier formula per sector + cap | feature | P5-01, P1-03 | complicated |
| P5-04 | Implement wormhole data model + render (implementer chooses readable transition marker within field-ops aesthetic) | feature | P5-01 | complicated |
| P5-05 | Implement 30 s wormhole countdown + "Next wormhole: NN s" HUD display | feature | P5-04, FN-06 | clear |
| P5-06 | Implement wormhole placement (empty cells ≥ 8 apart, retry on failure) | feature | P5-04, P4-03 | complicated |
| P5-07 | Implement wormhole entry → sector transfer (persist score/length/upgrade/held bonuses) | feature | P5-04, P5-02, P5-03 | complicated |
| P5-08 | Implement Phase 5 patrol-loss respawn (current sector, lose held bonuses, keep Scavenger Training) | feature | P5-01, FN-08 | complicated |
| P5-09 | Implement S10 soft cap visual handling | task | P5-01 | clear |
| P5-10 | Implement "SECTOR CLEARED" win condition (patrol covers all reachable cells) | feature | P5-01 | complicated |
| P5-11 | Verify §9.9 Acceptance Criteria | task | P5-01–P5-10 | complicated |

### §16.8 Polish & ship beads (EP-07)

| ID | Title | Type | Blocked by | Cynefin |
|---|---|---|---|---|
| FIN-01 | Implement phase-transition banner (2 s fade-in/out) | feature | P1-04 | clear |
| FIN-02 | Implement reinforcement pickup (cadence 90–150 s, 5-cap, squad-marker HUD row) | feature | FN-06, FN-08 | clear |
| FIN-03 | Implement reinforcement consumed on patrol loss (respawn flow) | feature | FIN-02, P5-08 | clear |
| FIN-04 | Wire pause to freeze Ambush timers, wormhole countdown, bonus expirations | task | P3-01, P5-05, FN-07 | complicated |
| FIN-05 | Final pass: file name (snake_[model].html, sonnet fallback) + no-external-deps audit | task | all phase beads | clear |
| FIN-06 | Final pass: §13 whole-game Acceptance Criteria | task | all phase beads | complicated |

### §16.9 Bead count summary

| Section | Count |
|---|---|
| EP-01 Foundation | 8 |
| EP-02 Phase 1 | 5 |
| EP-03 Phase 2 | 6 |
| EP-04 Phase 3 | 8 |
| EP-05 Phase 4 | 8 |
| EP-06 Phase 5 | 11 |
| EP-07 Polish & Ship | 6 |
| **Total child beads** | **52** |
| **Epics** | **7** |
| **Grand total (epics + children)** | **59** |

### §16.10 Paired beads

Examples of pairs that should claim and close together (using the `pair:<id>` label convention from `workflow-execution.md` §"Paired-Claim Rule"):

- **P3-01 ↔ P3-02** (Ambush data + telegraph) — implementing one without the other leaves the Ambush unreadable. Label both `pair:ambush-spawn`.
- **P4-02 ↔ P4-03** (bunker placement + connectivity check) — placing bunkers without validating connectivity ships a defect. Label both `pair:bunker-validity`.
- **P5-04 ↔ P5-06** (wormhole model + placement) — same reasoning. Label both `pair:wormhole-spawn`.

---

## §17. Explicit Exclusions

| Feature | Rationale | Status |
|---|---|---|
| Persistent leaderboards | Requires backend; violates single-file constraint | Permanent |
| Multiplayer or co-op | Single-player scope by design | Permanent |
| Mobile touch controls | Keyboard-first design; touch is a different UX problem | Deferred |
| User-uploaded skins or themes | Out of MVP; no asset pipeline | Permanent |
| Audio assets / sound files | Single-file no-CDN constraint; cannot ship .wav/.mp3 | Permanent |
| Save / resume between sessions | Stateless by design; localStorage adds complexity for no benchmark value | Deferred |
| Procedurally infinite Phase 5 leaderboards | Implied by no-backend; called out for clarity | Permanent |
| Achievements / progression unlocks | Out of MVP; would require persistence | Deferred |
| Cosmetic skins for the snake | Phase 1 monochrome / Phase 2+ palette is the cosmetic story | Permanent |
| Difficulty modes | Phase progression IS the difficulty curve | Permanent |
| Tutorial overlays | Phase 1 is the tutorial; gates teach the next mechanic | Permanent |
| Online sync of high scores | No backend | Permanent |
| Power-up shop / between-phase economy | Out of scope; reserved for the asteroids example | Permanent |
| Replay system | Out of scope; no persistence layer | Permanent |
| Boss fights | Out of scope; the Ambush is the closest thing to a boss encounter | Deferred |
| Procedural music | Trivially achievable via Web Audio API but out of scope for this PRD | Deferred |

---

## §18. Technology Decisions

| Category | Component | Choice | Rationale |
|---|---|---|---|
| Delivery | HTML file | Single inline document | Benchmark requirement; matches descriptive draft |
| Rendering | HTML5 Canvas 2D | Primary | Best performance for Phase 5 speeds with bonuses on screen |
| Geometry | Flat primitives (rect, line, circle, simple paths) | Only | No image assets; canvas paths are sufficient |
| Game loop | `requestAnimationFrame` with fixed-tick accumulator | Standard | Decouples render rate from game tick; smooth at any monitor refresh |
| Input | `keydown` / `keyup` listeners on `window` | Standard | No focus issues since the page is the game |
| Pause | Tick-clock flag, not loop teardown | Standard | Lets render loop continue showing "PAUSED" overlay |
| RNG | `Math.random()` | Acceptable | No determinism / replay requirement |
| Storage | None | — | No save/resume; no localStorage |
| Network | None | — | No backend |

---

## §19. What "Done" Looks Like

A player opens `snake_[model].html` in a browser. The page presents a dark canvas inside a thin dark-khaki panel frame, a light-gray 3-segment patrol at the center, "PHASE 1: NIGHT RECON" in the HUD, score 0, and 0 reinforcements in reserve. The player presses Right Arrow. The patrol moves. They collect 50 points of supply caches, watch the phase banner, and find themselves in Phase 2 — full camo palette emerging as dawn breaks, with a field-rations countdown ticking and the Scavenger Training upgrade icon visible. They survive an Ambush sweep in Phase 3, navigate around bunkers in Phase 4, and enter Phase 5. They clear two or three sectors of escalating tempo and bunker density before being lost. The PATROL LOST screen shows their final score, the phase reached, the sector reached, and "Press R to redeploy". They press R and the game restarts at Phase 1.

Every transition feels intentional. Every loss feels deserved. Every phase escalates without breaking the core "this is Snake" feeling — and the field-ops aesthetic is unmistakable from first frame to PATROL LOST.
