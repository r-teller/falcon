#!/usr/bin/env python3
"""
check-bead-contract.py — validate beads against tier-specific contracts.

Enforces the readiness contract defined in .claude/docs/work-item-templates.md
across three triage tiers (backlog / triaged / ready) plus the no-triage defect
case. Designed for Dolt-backed bd setups; queries bd state directly rather
than relying on the transient .beads/issues.jsonl artifact.

Usage:
  Mode selection (mutually exclusive, exactly one required):
    --beads ID[,ID...]      explicit bead set (highest precision)
    --session               beads updated since this session started
                            (reads .claude/tmp/<session_id>.json `started` field)
    --since YYYY-MM-DD      beads updated since a date
    --in-progress           every bead currently triage:in_progress
    --stale [--days N]      bd stale --days N (default 7)
    --all                   every open bead (full audit)

  Output mode (mutually exclusive; default = human-readable text):
    --json                  machine-readable JSON output
    --ids [SEVERITY]        one bead ID per line, no headers
                            SEVERITY: fail (default) | warn | all | pass
                            Useful for piping: `--ids fail | xargs -I{} bd show {}`

  Other:
    --strict                promote SOFT violations to HARD (exit 1 on any)
    --session-id <id>       override session ID for --session mode
                            (default: latest mtime in .claude/tmp/*.json)
    --days N                window for --stale (default 7)

Exit codes:
  0  all checks passed
  1  at least one HARD violation
  2  at least one SOFT violation (only if --strict not set)

bd interaction:
  The script sets BD_JSON_ENVELOPE=1 in the bd subprocess env automatically
  so it always sees the envelope format (`{data: [...], schema_version: N}`).
  Forward-compatible with bd v2.0; backward-compatible with bd v1.x.
  Performance: one `bd list --json --limit 0` call returns the corpus with
  full bead bodies; audit loop iterates dicts in memory. ~1 sec for 160 beads.

Contracts (from .claude/docs/work-item-templates.md, schema v1.0):

  triage:backlog
    labels: type:* (not 'task')
    sections: Summary, Persona, Phase, Open Questions, Rough Size Estimate

  triage:triaged
    labels: +cynefin:*, +size:*
    sections: +Acceptance Criteria
    rules: cynefin:disorder/chaotic cannot reach this tier;
           bug Fix Approach may be TBD

  triage:ready
    labels: +persona:*, +layer:*
    sections: +Changes Needed (table), +Effort Forecast (per-phase),
              +Required Context (if cynefin:complicated/complex)
    rules: no TBDs; Effort Forecast must have plan/implement/test
           phases + Total + Confidence; Required Context section content
           required for complicated/complex (empty allowed only with
           explicit '(none — reason)')

  No triage:* label
    DEFECT: bead exists without classification; must be triaged.

CONTRACTS_VERSION matches the schema version note in
work-item-templates.md. Bump both together on contract changes.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

CONTRACTS_VERSION = "1.2"

# Severity model (v1.1):
#   HARD (severity: fail) — blocks pre-push/wrapup. Reserved for:
#     - no_triage_label                (structural defect)
#     - invalid_type_task              (structural defect)
#     - cynefin_disorder_blocked       (explicit kit invariant)
#     - cynefin_chaotic_blocked        (explicit kit invariant)
#     - tbd_at_ready                   (broken readiness assertion)
#     - effort_forecast_not_per_phase  (broken readiness assertion)
#     - required_context_invalid:missing (broken readiness assertion)
#     - any missing_required_label / missing_required_section AT triage:ready
#   SOFT (severity: warn) — surfaces inline without blocking:
#     - missing_required_label or missing_required_section at backlog / triaged
#     - required_context_invalid:empty | no_refs_no_explicit_none
#   --strict promotes all SOFT to HARD (single knob for projects that want
#   maximal enforcement; default keeps capture + refinement friction-free).

# ---------- Tier contracts ----------

SECTIONS_BY_TIER = {
    "backlog": ["Summary", "Persona", "Phase", "Open Questions", "Rough Size Estimate"],
    "triaged": ["Summary", "Persona", "Phase", "Acceptance Criteria"],
    "ready": ["Summary", "Persona", "Changes Needed", "Acceptance Criteria", "Effort Forecast"],
}

LABELS_BY_TIER = {
    "backlog": ["type:"],
    "triaged": ["type:", "cynefin:", "size:"],
    "ready": ["type:", "cynefin:", "size:", "persona:", "layer:"],
}

# ---------- bd interaction ----------

def run_bd(*args):
    """Run bd with args and return JSON-parsed stdout. Raises on non-zero.

    Forward-compat with bd v2.0: sets BD_JSON_ENVELOPE=1 in subprocess env so
    we always see the envelope format (`{data: [...], meta: {...}}`). Unwraps
    `data` automatically. Bare-format (legacy bd <2.0 without the env var
    honored) is also handled."""
    cmd = ["bd"] + list(args)
    env = os.environ.copy()
    env["BD_JSON_ENVELOPE"] = "1"
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"bd command failed: {' '.join(cmd)}\n{res.stderr}")
    out = res.stdout.strip()
    if not out:
        return None
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        return out  # raw string fallback
    # Unwrap envelope: bd v2.0 envelope is {data: [...], schema_version: N}
    # (bd v1.x with BD_JSON_ENVELOPE=1 honored emits the same shape).
    # Detect by presence of `data` + (schema_version | meta) — robust against
    # bd adding sibling fields, and won't false-positive on bare {data: ...}
    # payloads that happen to use the same key name.
    if isinstance(parsed, dict) and "data" in parsed and (
        "schema_version" in parsed or "meta" in parsed
    ):
        return parsed["data"]
    return parsed

def bd_show(bead_id):
    """Return bd show <id> --json as a dict (bd 1.0 returns list; unwrap).
    Per-bead subprocess call — only used for --beads mode fallback. The main
    audit path uses resolve_beads() which returns full bead dicts from a
    single bd_list call."""
    data = run_bd("show", "--json", bead_id)
    if isinstance(data, list) and data:
        return data[0]
    return data

def bd_list(**filters):
    """Return bd list --json with filters as a list of bead dicts.
    The envelope format includes the full bead body (description) so the
    audit can run from this single call without per-bead bd_show."""
    args = ["list", "--json", "--limit", "0"]
    for k, v in filters.items():
        if v is None:
            continue
        args.extend([f"--{k.replace('_', '-')}", str(v)])
    data = run_bd(*args)
    if data is None:
        return []
    return data if isinstance(data, list) else [data]

# ---------- Mode resolvers ----------

def find_session_tracker(session_id=None, tmp_dir=".claude/tmp"):
    """Find the session tracker JSON. If session_id given, use it; else latest by mtime."""
    p = Path(tmp_dir)
    if not p.is_dir():
        raise FileNotFoundError(f"{tmp_dir} not found — is this a kit project?")
    if session_id:
        f = p / f"{session_id}.json"
        if not f.exists():
            raise FileNotFoundError(f"Session tracker {f} not found")
        return f
    candidates = [f for f in p.glob("*.json") if not f.name.startswith(".")]
    if not candidates:
        raise FileNotFoundError(f"No session trackers found in {tmp_dir}")
    return max(candidates, key=lambda f: f.stat().st_mtime)

def resolve_beads(args):
    """Resolve to a list of bead dicts (NOT just IDs) based on mode flag.

    All modes except --beads already need to call bd_list to find the bead
    set; returning the dicts directly avoids a second corpus fetch in main().
    --beads mode does ONE bd_list to fetch the corpus then filters down."""
    if args.beads:
        ids = {b.strip() for b in args.beads.split(",") if b.strip()}
        # One bd_list with full corpus, then filter. Avoids N bd_show calls.
        return [b for b in bd_list() if b.get("id") in ids]
    if args.session:
        tracker = find_session_tracker(args.session_id)
        data = json.loads(tracker.read_text())
        started = data.get("started")
        if not started:
            raise ValueError(f"Session tracker {tracker} has no 'started' field")
        return bd_list(updated_after=started, status="open")
    if args.since:
        return bd_list(updated_after=args.since, status="open")
    if args.in_progress:
        return bd_list(status="in_progress")
    if args.stale:
        days = args.days or 7
        data = run_bd("stale", "--days", str(days), "--json")
        if isinstance(data, list):
            return data
        return []
    if args.all:
        return bd_list(status="open")
    raise ValueError("No mode specified — pass one of --beads/--session/--since/--in-progress/--stale/--all")

# ---------- Contract checks ----------

def get_labels(bead):
    """Return list of label strings."""
    labels = bead.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    return labels

def get_triage(bead):
    """Return 'backlog' | 'triaged' | 'ready' | None."""
    for lbl in get_labels(bead):
        if lbl.startswith("triage:"):
            return lbl.split(":", 1)[1]
    return None

def get_cynefin(bead):
    for lbl in get_labels(bead):
        if lbl.startswith("cynefin:"):
            return lbl.split(":", 1)[1]
    return None

def label_prefix_present(bead, prefix):
    """True if any label starts with prefix."""
    return any(lbl.startswith(prefix) for lbl in get_labels(bead))

def section_present(body, name):
    """Detect '## <name>' or '### <name>' in body."""
    pat = re.compile(rf"^#{{2,4}}\s+{re.escape(name)}\s*$", re.MULTILINE)
    return bool(pat.search(body))

def section_content(body, name):
    """Extract content under '## <name>' until next ## header."""
    pat = re.compile(rf"^#{{2,4}}\s+{re.escape(name)}\s*$", re.MULTILINE)
    m = pat.search(body)
    if not m:
        return None
    start = m.end()
    next_h = re.search(r"^#{2,4}\s+\S", body[start:], re.MULTILINE)
    end = start + next_h.start() if next_h else len(body)
    return body[start:end].strip()

def has_tbd(body):
    """Detect literal 'TBD' as a non-trivial marker (not e.g., 'TBDsomething')."""
    return bool(re.search(r"\bTBD\b", body))

def effort_forecast_is_per_phase(body):
    """Confirm Effort Forecast has 5-phase breakdown (plan/discover/implement/test/fix) + Total + Confidence.

    Per the work-item-templates.md contract (5-phase model paired with token-tracking.py).
    Authors may write "N/A" or "0 turns" for phases that don't apply to a particular bead's
    work shape (e.g., a cynefin:clear chore won't have meaningful discover or fix phases),
    but the LABEL for each phase must be present so the forecast joins cleanly with the
    tracker's metrics records."""
    content = section_content(body, "Effort Forecast")
    if not content:
        return False
    needed = ["plan", "discover", "implement", "test", "fix", "total", "confidence"]
    lower = content.lower()
    return all(n in lower for n in needed)

def required_context_acceptable(body, cynefin):
    """For complicated/complex: section must exist with non-empty content
    OR explicit '(none — reason)' marker. For clear: any state OK."""
    if cynefin not in ("complicated", "complex"):
        return (True, None)
    if not section_present(body, "Required Context"):
        return (False, "missing")
    content = section_content(body, "Required Context")
    if not content:
        return (False, "empty")
    # Acceptable: at least one .claude/*.md reference OR '(none —' explicit
    if re.search(r"\.claude/[a-zA-Z_/-]+\.md", content):
        return (True, None)
    if re.search(r"\(\s*none\s*[—\-]", content, re.IGNORECASE):
        return (True, None)
    return (False, "no_refs_no_explicit_none")

# ---------- Per-bead audit ----------

def audit_bead(bead_id, bead=None):
    """Return list of violation dicts for one bead.
    If `bead` (dict) is supplied, skip the bd_show subprocess (fast-path used
    by the corpus-prefetch loop in main()). Otherwise fall back to bd_show."""
    violations = []
    if bead is None:
        try:
            bead = bd_show(bead_id)
        except RuntimeError as e:
            violations.append({
                "bead_id": bead_id,
                "severity": "fail",
                "tier": None,
                "rule": "bd_show_failed",
                "detail": str(e),
            })
            return violations
    if bead and bead.get("_fetch_error"):
        violations.append({
            "bead_id": bead_id,
            "severity": "fail",
            "tier": None,
            "rule": "bd_show_failed",
            "detail": bead["_fetch_error"],
        })
        return violations

    body = bead.get("body") or bead.get("description") or ""
    triage = get_triage(bead)
    cynefin = get_cynefin(bead)
    type_lbl = next((lbl.split(":", 1)[1] for lbl in get_labels(bead) if lbl.startswith("type:")), None)

    # No triage label = defect
    if triage is None:
        violations.append({
            "bead_id": bead_id,
            "severity": "fail",
            "tier": None,
            "cynefin": cynefin,
            "rule": "no_triage_label",
            "detail": "Bead exists without triage:* label — run triage classification",
        })
        return violations

    # type:task always invalid at any tier (per kit contract)
    if type_lbl == "task":
        violations.append({
            "bead_id": bead_id,
            "severity": "fail",
            "tier": triage,
            "cynefin": cynefin,
            "rule": "invalid_type_task",
            "detail": "type:task is for quick capture only — reclassify before any triage tier",
        })

    # Cynefin disorder/chaotic constraints
    if triage in ("triaged", "ready") and cynefin == "disorder":
        violations.append({
            "bead_id": bead_id,
            "severity": "fail",
            "tier": triage,
            "cynefin": cynefin,
            "rule": "cynefin_disorder_blocked",
            "detail": f"cynefin:disorder cannot reach triage:{triage} — enrich until classifiable",
        })
    if triage == "ready" and cynefin == "chaotic":
        violations.append({
            "bead_id": bead_id,
            "severity": "fail",
            "tier": triage,
            "cynefin": cynefin,
            "rule": "cynefin_chaotic_blocked",
            "detail": "cynefin:chaotic cannot reach triage:ready — decompose first",
        })

    # Severity-by-tier: ready violations are HARD (asserted readiness must hold),
    # backlog/triaged violations are SOFT (capture + refinement are fluid stages
    # where strict enforcement creates friction for routine work). Structural
    # defects (no triage label, type:task, cynefin:disorder/chaotic) stay HARD
    # regardless of tier.
    tier_sev = "fail" if triage == "ready" else "warn"

    # Required labels by tier
    for prefix in LABELS_BY_TIER.get(triage, []):
        if not label_prefix_present(bead, prefix):
            violations.append({
                "bead_id": bead_id,
                "severity": tier_sev,
                "tier": triage,
                "cynefin": cynefin,
                "rule": "missing_required_label",
                "detail": f"triage:{triage} requires {prefix}* label",
            })

    # Required sections by tier
    for section in SECTIONS_BY_TIER.get(triage, []):
        if not section_present(body, section):
            violations.append({
                "bead_id": bead_id,
                "severity": tier_sev,
                "tier": triage,
                "cynefin": cynefin,
                "rule": "missing_required_section",
                "detail": f"triage:{triage} requires `## {section}` section",
            })

    # Ready-tier specific rules
    if triage == "ready":
        if has_tbd(body):
            violations.append({
                "bead_id": bead_id,
                "severity": "fail",
                "tier": triage,
                "cynefin": cynefin,
                "rule": "tbd_at_ready",
                "detail": "triage:ready must have no TBDs (exception: bug Fix Approach at triage:triaged only)",
            })
        if not effort_forecast_is_per_phase(body):
            violations.append({
                "bead_id": bead_id,
                "severity": "fail",
                "tier": triage,
                "cynefin": cynefin,
                "rule": "effort_forecast_not_per_phase",
                "detail": "Effort Forecast must have plan/implement/test breakdown + Total + Confidence",
            })
        ok, reason = required_context_acceptable(body, cynefin)
        if not ok:
            sev = "fail" if reason == "missing" else "warn"
            detail_map = {
                "missing": f"cynefin:{cynefin} requires `## Required Context` section",
                "empty": "`## Required Context` section is empty; add 1-3 entries OR write '(none — reason)'",
                "no_refs_no_explicit_none": "`## Required Context` content has no .claude/*.md refs and no '(none —' marker",
            }
            violations.append({
                "bead_id": bead_id,
                "severity": sev,
                "tier": triage,
                "cynefin": cynefin,
                "rule": "required_context_invalid",
                "detail": detail_map[reason],
            })

    return violations

# ---------- Output formatting ----------

def format_text(violations, totals):
    lines = []
    by_bead = {}
    for v in violations:
        by_bead.setdefault(v["bead_id"], []).append(v)
    for bead_id, vs in by_bead.items():
        worst = "fail" if any(v["severity"] == "fail" for v in vs) else "warn"
        tag = "[FAIL]" if worst == "fail" else "[WARN]"
        cynefin = vs[0].get("cynefin") or "?"
        tier = vs[0].get("tier") or "(no triage)"
        lines.append(f"{tag} {bead_id} (triage:{tier}, cynefin:{cynefin})")
        for v in vs:
            lines.append(f"  - {v['detail']}")
            lines.append(f"    [rule: {v['rule']}]")
    lines.append("")
    lines.append(f"Summary: {totals['fail']} FAIL, {totals['warn']} WARN, {totals['pass']} PASS")
    return "\n".join(lines)

def format_json(violations, totals, checked):
    return json.dumps({
        "contracts_version": CONTRACTS_VERSION,
        "checked": checked,
        "pass": totals["pass"],
        "warn": totals["warn"],
        "fail": totals["fail"],
        "violations": violations,
    }, indent=2)

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--beads", help="Comma-separated bead IDs")
    grp.add_argument("--session", action="store_true", help="Beads updated since this session started")
    grp.add_argument("--since", help="Beads updated since YYYY-MM-DD")
    grp.add_argument("--in-progress", action="store_true", dest="in_progress", help="All triage:in_progress beads")
    grp.add_argument("--stale", action="store_true", help="bd stale --days N (default 7)")
    grp.add_argument("--all", action="store_true", help="All open beads")
    parser.add_argument("--days", type=int, help="Days for --stale (default 7)")
    parser.add_argument("--session-id", help="Override session ID for --session mode")
    parser.add_argument("--strict", action="store_true", help="Promote WARN to FAIL")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--ids",
        nargs="?",
        const="fail",
        choices=["fail", "warn", "all", "pass"],
        help=(
            "Output one bead ID per line at the given severity; no headers. "
            "Defaults to 'fail' when flag is bare. Useful for piping into "
            "other commands (e.g., `--ids fail | xargs -I{} bd show {}`). "
            "'all' = fail + warn. Mutually exclusive with --json."
        ),
    )
    args = parser.parse_args()
    if args.ids and args.json:
        print("Error: --ids and --json are mutually exclusive output modes.", file=sys.stderr)
        return 1

    try:
        beads = resolve_beads(args)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not beads:
        if args.json:
            print(format_json([], {"pass": 0, "warn": 0, "fail": 0}, 0))
        else:
            print("No beads matched the selected mode.")
        return 0

    # resolve_beads already returned dicts (one bd_list call covers the corpus).
    # No second fetch needed — pass each dict to audit_bead's fast path.
    all_violations = []
    pass_count = 0
    passing_ids = []
    for bead in beads:
        bid = bead.get("id")
        if not bid:
            continue
        vs = audit_bead(bid, bead=bead)
        if not vs:
            pass_count += 1
            passing_ids.append(bid)
        else:
            all_violations.extend(vs)

    if args.strict:
        for v in all_violations:
            if v["severity"] == "warn":
                v["severity"] = "fail"

    totals = {
        "pass": pass_count,
        "warn": sum(1 for v in all_violations if v["severity"] == "warn"),
        "fail": sum(1 for v in all_violations if v["severity"] == "fail"),
    }

    if args.ids:
        # IDs-only output mode — one bead ID per line, no headers/JSON.
        if args.ids == "pass":
            ids_out = passing_ids
        else:
            wanted = {"fail"} if args.ids == "fail" else \
                     {"warn"} if args.ids == "warn" else \
                     {"fail", "warn"}  # all
            # Dedupe while preserving first-seen order
            seen = set()
            ids_out = []
            for v in all_violations:
                if v["severity"] in wanted and v["bead_id"] not in seen:
                    seen.add(v["bead_id"])
                    ids_out.append(v["bead_id"])
        for bid in ids_out:
            print(bid)
    elif args.json:
        print(format_json(all_violations, totals, len(beads)))
    else:
        print(format_text(all_violations, totals))

    if totals["fail"] > 0:
        return 1
    if totals["warn"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
