#!/usr/bin/env python3
"""Generate a self-contained velocity report HTML with embedded metrics data.

Usage:
    python3 .claude/scripts/velocity-report.py .claude/metrics.jsonl
    python3 .claude/scripts/velocity-report.py .claude/metrics.jsonl -o velocity-2026-03-30.html
    python3 .claude/scripts/velocity-report.py .claude/metrics.jsonl > report.html

The output is a single HTML file with all chart data embedded inline.
No file picker needed — just open in any browser.
"""
import json
import sys
import os
import argparse
from datetime import datetime


def load_metrics(path):
    """Load metrics.jsonl, skipping malformed lines with a visible count.

    Malformed lines must not be silent: a mostly-corrupt file would otherwise
    be indistinguishable from a healthy small one."""
    records = []
    skipped = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    skipped += 1
    if skipped:
        print(f"Warning: {skipped} malformed line(s) skipped in {path}", file=sys.stderr)
    return records


def load_template():
    """Load velocity.html template from the same directory as this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, 'velocity.html')
    if not os.path.exists(template_path):
        print(f"Error: velocity.html not found at {template_path}", file=sys.stderr)
        sys.exit(1)
    with open(template_path) as f:
        return f.read()


def embed_data(template, records):
    """Embed metrics data into the velocity.html template and arm auto-render.

    Supports two template shapes:
    1. Falcon kit shape (current): pre-processed template with `ALL_DATA = [];  // populated by ...`
       placeholder and dashboard already visible. Most string replacements no-op (their
       targets already in the desired state); the ALL_DATA placeholder line is the
       single injection point.
    2. Legacy mission-control shape: original template with file picker, hidden dashboard,
       and a `file-input` event listener. All replacements active.

    Both shapes converge to the same output: data inlined, file picker hidden, dashboard
    visible, auto-render fires on window load."""
    import re as _re
    data_json = json.dumps(records, separators=(',', ':'))
    count = len(records)
    beads = len(set(r.get('bead_id', '') for r in records if r.get('record_type') != 'session_time'))
    sessions = len(set(r.get('session_id', '') for r in records))
    generated = datetime.now().strftime('%Y-%m-%d %H:%M')

    # ── Primary injection point (works for both shapes) ────────────────────
    # Replace the ALL_DATA placeholder line. Match flexibly: the line may carry
    # a trailing comment ("// populated by ...") or be a bare `ALL_DATA = [];`.
    placeholder_pattern = _re.compile(r'^ALL_DATA\s*=\s*\[\];?(\s*//[^\n]*)?$', _re.MULTILINE)
    if placeholder_pattern.search(template):
        # Replacement MUST be a function: a string repl undergoes re escape
        # processing, so JSON containing \uXXXX (any non-ASCII) crashes with
        # "bad escape" and a literal backslash (\\) collapses to \, silently
        # corrupting the embedded data while exiting 0.
        injected = f'ALL_DATA = {data_json};  // embedded by velocity-report.py ({count} records, {beads} beads, {sessions} sessions, generated {generated})'
        template = placeholder_pattern.sub(lambda m: injected, template, count=1)
    else:
        # Fallback for legacy templates: the data is initialized inside the file-loader.
        # Inject ALL_DATA at the top of the main <script> block.
        first_script_idx = template.find('<script>\n')
        if first_script_idx != -1:
            insert_point = first_script_idx + len('<script>\n')
            template = (
                template[:insert_point]
                + f'ALL_DATA = {data_json};\n// embedded by velocity-report.py ({count} records, {beads} beads)\n'
                + template[insert_point:]
            )

    # ── Hide file picker if present (legacy template shape) ────────────────
    old_load = '''<div id="load-section">
  <p style="color:var(--muted);font-size:16px;margin-bottom:16px">Load metrics data to begin</p>
  <label>Select metrics.jsonl<input type="file" id="file-input" accept=".jsonl"></label>
  <p style="color:var(--muted);font-size:12px;margin-top:12px">File: <code>.claude/metrics.jsonl</code></p>
</div>'''
    template = template.replace(old_load, '<div id="load-section" style="display:none"></div>')

    # ── Make dashboard visible if hidden (legacy template shape) ───────────
    template = template.replace('<div id="dashboard" style="display:none">', '<div id="dashboard">')
    template = template.replace('#dashboard{display:none}', '#dashboard{display:block}')

    # ── Update subtitles for both shapes ───────────────────────────────────
    template = template.replace(
        'Mission Control — Self-reflection dashboard for Agentic Agile development',
        f'Velocity Report — {count} records, {beads} beads, {sessions} sessions · generated {generated}',
    )
    template = template.replace(
        'Velocity Report — load metrics.jsonl to begin',
        f'Velocity Report — {count} records, {beads} beads, {sessions} sessions · generated {generated}',
    )

    # ── Remove the file-loader JS (legacy template shape) ──────────────────
    old_loader = '''document.getElementById('file-input').addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(ev) {
    const lines = ev.target.result.trim().split('\\n');
    ALL_DATA = lines.map(l => { try { return JSON.parse(l); } catch(e) { return null; } }).filter(Boolean);
    buildSprints();
    initSlider();
    render();
    document.getElementById('load-section').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
  };
  reader.readAsText(file);
});'''
    template = template.replace(old_loader, '// File loader removed — data embedded by velocity-report.py')

    # ── Arm auto-render after window load (both shapes) ────────────────────
    last_script_idx = template.rfind('</script>')
    if last_script_idx != -1 and 'Auto-render embedded data' not in template:
        template = (
            template[:last_script_idx]
            + '\n// Auto-render embedded data — fire after window load so layout is computed\n'
            + 'window.addEventListener("load", function() {\n'
            + '  if (typeof buildSprints === "function") buildSprints();\n'
            + '  if (typeof initSlider === "function") initSlider();\n'
            + '  if (typeof render === "function") render();\n'
            + '});\n'
            + template[last_script_idx:]
        )

    return template


def main():
    parser = argparse.ArgumentParser(
        description='Generate self-contained velocity report HTML'
    )
    parser.add_argument('metrics', help='Path to metrics.jsonl')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    args = parser.parse_args()

    if not os.path.exists(args.metrics):
        print(f"Error: {args.metrics} not found", file=sys.stderr)
        sys.exit(1)

    records = load_metrics(args.metrics)
    template = load_template()
    html = embed_data(template, records)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(html)
        beads = len(set(r.get('bead_id', '') for r in records if r.get('record_type') != 'session_time'))
        print(f"Generated {args.output} ({len(records)} records, {beads} beads)", file=sys.stderr)
    else:
        print(html)


if __name__ == '__main__':
    main()
