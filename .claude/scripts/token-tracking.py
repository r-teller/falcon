#!/usr/bin/env python3
# =============================================================================
# token-tracking.py — Phase-aware token tracking per work item
# =============================================================================
#
# PURPOSE
#   Measures API token consumption per bead per phase by bookmarking transcript
#   line offsets. Supports individual bead work (--bead) and batch coordination
#   (--coordinate). Tracks across sessions with per-session segment nesting.
#
#   Stdlib only — no jq required. Python port (fdev-6xt) of the original bash
#   implementation; CLI surface and storage schema are unchanged. Behavioral
#   fixes over the bash version:
#     - Unresolvable session exits 1 with no state written (fdev-96q)
#     - Malformed transcript lines are skipped per-line, never abort or zero
#       the sum; a skipped-line warning goes to stderr (fdev-0sr)
#     - Coordinate segments carry a per-segment beads snapshot; empty bead IDs
#       are rejected (fdev-1vs)
#     - Silent-loss cases warn on stderr and mark the segment (fdev-034)
#
# COMMANDS
#   start   --bead <id> --phase <phase> --session <sid>
#   start   --coordinate --beads <id1,id2,...> --session <sid>
#   stop    --bead <id> [--json]
#   stop    --coordinate --session <sid> [--json]
#   status  --bead <id> [--json]
#   status  --coordinate --session <sid> [--json]
#   list
#
# PHASES (--bead mode only)
#   plan, discover, implement, test, fix
#
# RULES
#   - Only one tracking active at a time (single-active enforcement)
#   - Phase transitions require explicit stop + start
#   - Resume: start with same bead + same phase + same session = bank + continue
#   - Orphan: start with same bead + same phase + different session = mark orphaned
#   - --coordinate and --bead are mutually exclusive
#
# STORAGE
#   Per-bead:        .claude/tmp/.token_tracking/<bead-id>.json
#   Per-coordinate:  .claude/tmp/.token_tracking/coordinate.<session-id>.json
# =============================================================================

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

VALID_PHASES = ["plan", "discover", "implement", "test", "fix"]

TRACK_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()) / ".claude" / "tmp" / ".token_tracking"

ZERO_TOKENS = {
    "input_tokens": 0,
    "cache_read_tokens": 0,
    "cache_create_tokens": 0,
    "output_tokens": 0,
    "turns": 0,
}

HELP = """token-tracking.py — Phase-aware token tracking per work item

Commands:
  start   --bead <id> --phase <phase> --session <sid>   Track individual bead
  start   --coordinate --beads <ids> --session <sid>     Track batch coordination
  stop    --bead <id> [--json]                           Finalize active phase
  stop    --coordinate --session <sid> [--json]          Finalize coordination
  status  --bead <id> [--json]                           Check running totals
  status  --coordinate --session <sid> [--json]          Check coordination totals
  list                                                   Show all tracked items

Modes:
  --bead <id>        Individual bead work (requires --phase on start)
  --coordinate       Batch planning (requires --beads on start)

Phases (--bead only):
  plan, discover, implement, test, fix

Rules:
  - Only one tracking active at a time
  - Phase transitions: explicit stop + start
  - Resume: start same bead + same phase + same session
  - --coordinate and --bead are mutually exclusive

Storage:
  Per-bead:       .claude/tmp/.token_tracking/<bead-id>.json
  Coordinate:     .claude/tmp/.token_tracking/coordinate.<session-id>.json"""


def die(msg):
    print(msg)
    sys.exit(1)


def warn(msg):
    print(msg, file=sys.stderr)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -----------------------------------------------------------------------------
# Transcript helpers
# -----------------------------------------------------------------------------
def resolve_transcript(sid):
    matches = sorted(Path.home().glob(f".claude/projects/*/{sid}.jsonl"))
    if not matches:
        # fdev-96q: this is a hard error — exit 1, no state written. The bash
        # version exited only a subshell here and fell through to a corrupt write.
        die(f"Error: No transcript found for session '{sid}'.")
    return str(matches[0])


def get_line_count(path):
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return n


def sum_tokens(path, start_line, end_line):
    """Sum assistant-message usage over transcript lines start_line..end_line (1-based, inclusive).

    fdev-0sr: parses per-line; a malformed line is skipped (counted + warned),
    never aborts the sum or silently zeroes it.
    """
    totals = dict(ZERO_TOKENS)
    skipped = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, start=1):
            if i < start_line:
                continue
            if i > end_line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                skipped += 1
                continue
            if not isinstance(rec, dict) or rec.get("type") != "assistant":
                continue
            message = rec.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            totals["input_tokens"] += usage.get("input_tokens") or 0
            totals["cache_read_tokens"] += usage.get("cache_read_input_tokens") or 0
            totals["cache_create_tokens"] += usage.get("cache_creation_input_tokens") or 0
            totals["output_tokens"] += usage.get("output_tokens") or 0
            totals["turns"] += 1
    if skipped:
        warn(f"Warning: skipped {skipped} malformed transcript line(s) in {path} (lines {start_line}-{end_line}).")
    return totals


# -----------------------------------------------------------------------------
# Track-file helpers
# -----------------------------------------------------------------------------
def load_track(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_track(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    tmp.replace(path)


def active_marker(data):
    """Return a truthy active descriptor for a track file, or None."""
    ap = data.get("active_phase")
    if ap not in (None, "", False, "null"):
        return ap
    if data.get("active") is True:
        # fdev-034: display 'coordinate' rather than the boolean for coordinate files
        return "coordinate" if data.get("type") == "coordinate" else "true"
    return None


def check_single_active(skip_path=None):
    if not TRACK_DIR.is_dir():
        return
    for f in sorted(TRACK_DIR.glob("*.json")):
        if skip_path is not None and f == skip_path:
            continue
        try:
            data = load_track(f)
        except (json.JSONDecodeError, OSError):
            continue
        ap = active_marker(data)
        if ap:
            wid = data.get("work_id") or data.get("type") or f.stem
            die(f"Error: '{wid}' is active (phase: {ap}). Run 'stop' on it first.")


def banked(session, key):
    return session.get(f"banked_{key}") or 0


def clear_banked(session):
    for k in ("banked_input", "banked_cache_read", "banked_cache_create", "banked_output", "banked_turns"):
        session.pop(k, None)


def add_banked(session, seg):
    session["banked_input"] = banked(session, "input") + seg["input_tokens"]
    session["banked_cache_read"] = banked(session, "cache_read") + seg["cache_read_tokens"]
    session["banked_cache_create"] = banked(session, "cache_create") + seg["cache_create_tokens"]
    session["banked_output"] = banked(session, "output") + seg["output_tokens"]
    session["banked_turns"] = banked(session, "turns") + seg["turns"]


def banked_plus(session, seg):
    return {
        "input_tokens": banked(session, "input") + seg["input_tokens"],
        "cache_read_tokens": banked(session, "cache_read") + seg["cache_read_tokens"],
        "cache_create_tokens": banked(session, "cache_create") + seg["cache_create_tokens"],
        "output_tokens": banked(session, "output") + seg["output_tokens"],
        "turns": banked(session, "turns") + seg["turns"],
    }


def totals_of(segments):
    out = dict(ZERO_TOKENS)
    for s in segments:
        for k in out:
            out[k] += s.get(k) or 0
    return out


def all_segments(data):
    segs = []
    for session in data.get("sessions", {}).values():
        segs.extend(session.get("segments", []))
    return segs


def emit_json(obj):
    print(json.dumps(obj, indent=2))


# -----------------------------------------------------------------------------
# start --bead
# -----------------------------------------------------------------------------
def start_bead(bead_id, phase, session_id):
    if not phase:
        die("Error: --phase is required for start --bead.")
    if not session_id:
        die("Error: --session is required for start.")
    if phase not in VALID_PHASES:
        die(f"Error: Invalid phase '{phase}'. Valid: {' '.join(VALID_PHASES)}")

    transcript = resolve_transcript(session_id)
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    track_file = TRACK_DIR / f"{bead_id}.json"
    now = utc_now()
    current_line = get_line_count(transcript)

    if not track_file.exists():
        check_single_active(None)
        save_track(track_file, {
            "work_id": bead_id,
            "active_session": session_id,
            "active_phase": phase,
            "active_started": now,
            "bookmark": current_line,
            "sessions": {
                session_id: {"transcript": transcript, "segments": []}
            },
        })
        print(f"Started tracking {bead_id} phase={phase} session={session_id} at line {current_line}")
        return

    data = load_track(track_file)
    active_phase = data.get("active_phase")
    active_session = data.get("active_session")

    if not active_phase:
        # No active phase — open new segment after previous stop
        check_single_active(track_file)
        data["active_session"] = session_id
        data["active_phase"] = phase
        data["active_started"] = now
        data["bookmark"] = current_line
        data.setdefault("sessions", {}).setdefault(session_id, {"transcript": transcript, "segments": []})
        save_track(track_file, data)
        print(f"Started tracking {bead_id} phase={phase} session={session_id} at line {current_line}")
        return

    if active_phase == phase and active_session == session_id:
        # Resume — same bead, same phase, same session (compaction)
        session = data["sessions"][session_id]
        old_bookmark = data.get("bookmark") or 0
        old_transcript = session.get("transcript")
        if old_transcript and Path(old_transcript).is_file() and old_bookmark < get_line_count(old_transcript):
            seg = sum_tokens(old_transcript, old_bookmark + 1, get_line_count(old_transcript))
            add_banked(session, seg)
        data["bookmark"] = current_line
        session["transcript"] = transcript
        save_track(track_file, data)
        print(f"Resumed tracking {bead_id} phase={phase} session={session_id} at line {current_line}")
        return

    if active_phase == phase and active_session != session_id:
        # Orphan recovery — same phase, different session
        old_session = data["sessions"].setdefault(active_session, {"transcript": "", "segments": []})
        old_bookmark = data.get("bookmark") or 0
        old_transcript = old_session.get("transcript")
        orphan_tokens = dict(ZERO_TOKENS)
        transcript_missing = not (old_transcript and Path(old_transcript).is_file())
        if not transcript_missing:
            old_end = get_line_count(old_transcript)
            if old_bookmark < old_end:
                orphan_tokens = sum_tokens(old_transcript, old_bookmark + 1, old_end)

        orphan_seg = {
            "phase": active_phase,
            "started": data.get("active_started") or "unknown",
            "stopped": utc_now(),
            **banked_plus(old_session, orphan_tokens),
            "orphaned": True,
            "orphan_reason": "session ended without stop",
        }
        if transcript_missing:
            # fdev-034: distinguish "nothing happened" from "transcript gone, tokens unrecoverable"
            orphan_seg["transcript_missing"] = True
        old_session.setdefault("segments", []).append(orphan_seg)
        clear_banked(old_session)
        save_track(track_file, data)
        # fdev-034: warning goes to stderr so programmatic stdout consumers stay clean
        warn(f"Warning: Orphaned segment from session {active_session} (phase={active_phase}). Marked as untrusted.")

        check_single_active(track_file)
        data["active_session"] = session_id
        data["active_phase"] = phase
        data["active_started"] = now
        data["bookmark"] = current_line
        data["sessions"].setdefault(session_id, {"transcript": transcript, "segments": []})
        save_track(track_file, data)
        print(f"Started tracking {bead_id} phase={phase} session={session_id} at line {current_line}")
        return

    die(f"Error: Bead '{bead_id}' is active in phase '{active_phase}'. Run 'stop --bead {bead_id}' first.")


# -----------------------------------------------------------------------------
# stop --bead
# -----------------------------------------------------------------------------
def stop_bead(bead_id, json_output):
    track_file = TRACK_DIR / f"{bead_id}.json"
    if not track_file.is_file():
        die(f"Error: No tracking data for '{bead_id}'.")

    data = load_track(track_file)
    active_phase = data.get("active_phase")
    active_session = data.get("active_session")
    if not active_phase:
        die(f"Error: No active phase for '{bead_id}'. Already stopped.")

    session = data["sessions"].setdefault(active_session, {"transcript": "", "segments": []})
    transcript = session.get("transcript")
    bookmark = data.get("bookmark") or 0

    seg_tokens = dict(ZERO_TOKENS)
    unrecoverable = False
    if transcript and Path(transcript).is_file():
        current_line = get_line_count(transcript)
        if bookmark < current_line:
            seg_tokens = sum_tokens(transcript, bookmark + 1, current_line)
        elif bookmark > current_line:
            # fdev-034: transcript shrank (compaction) with no resume in between —
            # tokens consumed pre-compaction are unrecoverable on a direct stop.
            unrecoverable = True
            warn(f"Warning: bookmark ({bookmark}) exceeds transcript length ({current_line}); "
                 f"tokens consumed pre-compaction are unrecoverable. "
                 f"Use resume (start with same bead/phase/session) before stop to bank across compaction boundaries.")

    segment = {
        "phase": active_phase,
        "started": data.get("active_started") or "unknown",
        "stopped": utc_now(),
        **banked_plus(session, seg_tokens),
    }
    if unrecoverable:
        segment["tokens_unrecoverable"] = True
    session.setdefault("segments", []).append(segment)
    clear_banked(session)
    data["active_phase"] = None
    data["active_session"] = None
    data["active_started"] = None
    data["bookmark"] = None
    save_track(track_file, data)

    if json_output:
        emit_json(bead_report(data))
    else:
        print(f"Stopped tracking {bead_id} phase={active_phase}")


# -----------------------------------------------------------------------------
# status --bead
# -----------------------------------------------------------------------------
def bead_report(data):
    return {
        "work_id": data.get("work_id"),
        "active_phase": data.get("active_phase"),
        "active_session": data.get("active_session"),
        "sessions": {
            sid: {"transcript": s.get("transcript"), "segments": s.get("segments", [])}
            for sid, s in data.get("sessions", {}).items()
        },
        "totals": totals_of(all_segments(data)),
    }


def status_bead(bead_id, json_output):
    track_file = TRACK_DIR / f"{bead_id}.json"
    if not track_file.is_file():
        die(f"Error: No tracking data for '{bead_id}'.")
    data = load_track(track_file)

    if not json_output:
        segs = all_segments(data)
        print(f"=== {bead_id} ===")
        print(f"  active_phase: {data.get('active_phase') or 'none'}")
        print(f"  segments: {len(segs)}")
        return

    active_phase = data.get("active_phase")
    active_session = data.get("active_session")
    if not active_phase:
        emit_json(bead_report(data))
        return

    session = data.get("sessions", {}).get(active_session, {})
    transcript = session.get("transcript")
    bookmark = data.get("bookmark") or 0
    in_progress_raw = dict(ZERO_TOKENS)
    if transcript and Path(transcript).is_file():
        current_line = get_line_count(transcript)
        if bookmark < current_line:
            in_progress_raw = sum_tokens(transcript, bookmark + 1, current_line)
    in_progress = banked_plus(session, in_progress_raw)

    report = bead_report(data)
    report["in_progress"] = {"session": active_session, "phase": active_phase, **in_progress}
    report["totals"] = totals_of(all_segments(data) + [in_progress])
    emit_json(report)


# -----------------------------------------------------------------------------
# coordinate mode
# -----------------------------------------------------------------------------
def parse_beads_list(beads_list):
    beads = [b.strip() for b in beads_list.split(",")]
    beads = [b for b in beads if b]
    # fdev-1vs: comma-only / empty entries must not produce empty-string bead IDs
    if not beads:
        die("Error: --beads must contain at least one non-empty bead ID.")
    return beads


def start_coordinate(beads_list, session_id):
    if not session_id:
        die("Error: --session is required for start.")
    beads = parse_beads_list(beads_list)
    transcript = resolve_transcript(session_id)
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    track_file = TRACK_DIR / f"coordinate.{session_id}.json"
    now = utc_now()
    current_line = get_line_count(transcript)

    if track_file.exists():
        data = load_track(track_file)
        if data.get("active") is True:
            die(f"Error: Coordination already active for session {session_id}. Run 'stop --coordinate --session {session_id}' first.")
        check_single_active(track_file)
        data["active"] = True
        data["beads"] = beads
        data["bookmark"] = current_line
        data["started"] = now
        data["stopped"] = None
        save_track(track_file, data)
    else:
        check_single_active(None)
        save_track(track_file, {
            "type": "coordinate",
            "session_id": session_id,
            "beads": beads,
            "transcript": transcript,
            "bookmark": current_line,
            "active": True,
            "started": now,
            "stopped": None,
            "segments": [],
        })

    print(f"Started coordination tracking for {' '.join(beads)} session={session_id} at line {current_line}")


def coordinate_report(data, extra=None):
    report = {
        "type": data.get("type"),
        "session_id": data.get("session_id"),
        "beads": data.get("beads"),
        "segments": data.get("segments", []),
    }
    segments = list(data.get("segments", []))
    if extra is not None:
        segments.append(extra)
    report["totals"] = totals_of(segments)
    return report


def stop_coordinate(session_id, json_output):
    if not session_id:
        die("Error: --session is required for stop --coordinate.")
    track_file = TRACK_DIR / f"coordinate.{session_id}.json"
    if not track_file.is_file():
        die(f"Error: No coordination tracking for session '{session_id}'.")
    data = load_track(track_file)
    if data.get("active") is not True:
        die(f"Error: No active coordination for session '{session_id}'. Already stopped.")

    transcript = data.get("transcript")
    bookmark = data.get("bookmark") or 0
    now = utc_now()
    seg_tokens = dict(ZERO_TOKENS)
    if transcript and Path(transcript).is_file():
        current_line = get_line_count(transcript)
        if bookmark < current_line:
            seg_tokens = sum_tokens(transcript, bookmark + 1, current_line)

    # fdev-1vs: snapshot the beads this segment tracked — a later re-coordination
    # on the same session file must not rewrite history.
    data.setdefault("segments", []).append({
        "phase": "coordinate",
        "beads": data.get("beads"),
        "started": data.get("started"),
        "stopped": now,
        **seg_tokens,
    })
    data["active"] = False
    data["stopped"] = now
    data["bookmark"] = None
    save_track(track_file, data)

    if json_output:
        emit_json(coordinate_report(data))
    else:
        print(f"Stopped coordination tracking for session {session_id}")


def status_coordinate(session_id, json_output):
    if not session_id:
        die("Error: --session is required for status --coordinate.")
    track_file = TRACK_DIR / f"coordinate.{session_id}.json"
    if not track_file.is_file():
        die(f"Error: No coordination tracking for session '{session_id}'.")
    data = load_track(track_file)

    if not json_output:
        print(f"=== Coordinate: {session_id} ===")
        print(f"  active: {str(data.get('active', False)).lower()}")
        print(f"  beads: {', '.join(data.get('beads') or [])}")
        return

    if data.get("active") is True:
        transcript = data.get("transcript")
        bookmark = data.get("bookmark") or 0
        in_progress = dict(ZERO_TOKENS)
        if transcript and Path(transcript).is_file():
            current_line = get_line_count(transcript)
            if bookmark < current_line:
                in_progress = sum_tokens(transcript, bookmark + 1, current_line)
        report = coordinate_report(data, extra=in_progress)
        report["active"] = True
        report["in_progress"] = {"phase": "coordinate", **in_progress}
        emit_json(report)
    else:
        report = coordinate_report(data)
        report["active"] = data.get("active", False)
        emit_json(report)


# -----------------------------------------------------------------------------
# list
# -----------------------------------------------------------------------------
def do_list():
    print("=== Token Tracking ===")
    found = False
    if TRACK_DIR.is_dir():
        for f in sorted(TRACK_DIR.iterdir()):
            if not f.is_file():
                continue
            if f.suffix == ".json":
                try:
                    data = load_track(f)
                except (json.JSONDecodeError, OSError):
                    print(f"  {f.stem} (unreadable)")
                    found = True
                    continue
                seg_count = len(all_segments(data)) if "sessions" in data else len(data.get("segments", []))
                ap = active_marker(data)
                if ap:
                    print(f"  {f.stem} (active: phase={ap}, segments={seg_count})")
                else:
                    print(f"  {f.stem} (stopped, segments={seg_count})")
                found = True
        # Legacy shell-sourceable files (backward compat)
        for f in sorted(TRACK_DIR.iterdir()):
            if not f.is_file() or f.suffix == ".json":
                continue
            name = f.name
            if name.endswith(".done"):
                print(f"  {name[:-5]} (legacy, completed)")
            else:
                print(f"  {name} (legacy, in progress)")
            found = True
    if not found:
        print("  (none)")


# -----------------------------------------------------------------------------
# Argument parsing + dispatch (hand-rolled for bash-CLI compatibility)
# -----------------------------------------------------------------------------
def main(argv):
    if not argv:
        print(HELP)
        return 1
    action, args = argv[0], argv[1:]

    bead_id = ""
    beads_list = ""
    phase = ""
    session_id = ""
    coordinate = False
    json_output = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--bead":
            bead_id = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        elif a == "--beads":
            beads_list = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        elif a == "--phase":
            phase = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        elif a == "--session":
            session_id = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        elif a == "--coordinate":
            coordinate = True
            i += 1
        elif a == "--json":
            json_output = True
            i += 1
        else:
            die(f"Error: Unknown argument '{a}'")

    def validate_mode():
        if coordinate and bead_id:
            die("Error: --bead and --coordinate are mutually exclusive.")
        if coordinate and not beads_list:
            die("Error: --coordinate requires --beads <id1,id2,...>.")
        if beads_list and not coordinate:
            # fdev-034: one message for this mistake regardless of path
            die("Error: --beads requires --coordinate flag.")
        if not coordinate and not bead_id:
            die("Error: Specify --bead <id> or --coordinate --beads <id1,id2,...>.")
        if bead_id and "," in bead_id:
            die("Error: --bead accepts a single bead ID. For multiple beads use --coordinate --beads <id1,id2,...>.")

    if action == "start":
        if coordinate:
            validate_mode()
            start_coordinate(beads_list, session_id)
        elif bead_id:
            validate_mode()
            start_bead(bead_id, phase, session_id)
        elif beads_list:
            die("Error: --beads requires --coordinate flag.")
        else:
            die("Error: Specify --bead <id> or --coordinate --beads <id1,id2,...>.")
    elif action == "stop":
        if coordinate:
            stop_coordinate(session_id, json_output)
        elif bead_id:
            stop_bead(bead_id, json_output)
        elif beads_list:
            die("Error: --beads requires --coordinate flag.")
        else:
            die("Error: Specify --bead <id> or --coordinate --session <id>.")
    elif action == "status":
        if coordinate:
            status_coordinate(session_id, json_output)
        elif bead_id:
            status_bead(bead_id, json_output)
        elif beads_list:
            die("Error: --beads requires --coordinate flag.")
        else:
            die("Error: Specify --bead <id> or --coordinate --session <id>.")
    elif action == "list":
        do_list()
    else:
        print(HELP)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
