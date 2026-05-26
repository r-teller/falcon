# Development Standards

> **Template stub** — replace the placeholder structure below with your project's actual standards.

This file is project-owned. Falcon does NOT prescribe specific standards; it expects projects to define their own and to cite them by stable section number (`§X.Y`) from dispatch reports, cognitive-audit hints, and the `falcon-autopilot.md` rules file.

## Convention

- **Section numbering** — top-level sections use `§1`, `§2`, ...; sub-sections use `§X.Y` (e.g., `§3.17`). Numbers are stable identifiers — once a section ships, its number does not move. New rules get a new sub-section number; deprecated rules stay numbered (marked `(deprecated)`) so historical references remain valid.
- **Sub-section topic binding** — each `§X.Y` should bind exactly one rule or convention so dispatch reports can cite it unambiguously (e.g., `rule_ref: development-standards.md §3.17`).
- **Cross-references** — falcon's cognitive-audit hint examples in `.claude/skills/falcon/REFERENCE.md` cite `§3.x` numbers as illustrative project values. In your copy of `.claude/rules/falcon-autopilot.md`, replace those with the actual section numbers from this file.

## Where falcon expects this file

`.claude/rules/development-standards.md` (this path). The autopilot template (`.claude/rules/falcon-autopilot.md`) and the cognitive-audit examples reference it by this exact name.

## Template structure

Replace the headers below with your project's categories. The numbering scheme is a suggestion; what matters is that numbers are stable and each `§X.Y` binds one rule.

### §1. <Top-level standards category>

<Short description of what this category covers.>

#### §1.1 <Specific rule>

<One-paragraph rule description, rationale, and how a worker / reviewer applies it.>

#### §1.2 <Another rule>

...

### §2. <Another category>

...

### §3. <Cross-cutting standards>

...
