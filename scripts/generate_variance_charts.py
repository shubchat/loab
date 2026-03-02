#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENT_KEYS = ["tool_calls", "handoffs", "step_decisions", "outcome", "forbidden_actions", "evidence"]
PALETTE = ["#0f766e", "#c2410c", "#2563eb", "#7c3aed"]


def load_json(path: Path):
    return json.loads(path.read_text())


def slugify_task(task: str) -> str:
    return task.replace("/", "-")


def score_percent(score: dict | None) -> float:
    if not score:
        return 0.0
    total = 0
    passed = 0
    for key in COMPONENT_KEYS:
        part = score.get(key)
        if isinstance(part, dict) and "passed" in part:
            total += 1
            if part.get("passed"):
                passed += 1
    if total == 0:
        return 0.0
    return (passed / total) * 100.0


def collect_series(summary_paths):
    by_task = {}
    for raw in summary_paths:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        data = load_json(path)
        for entry in data.get("results", []):
            task = entry.get("task")
            label = entry.get("model_label")
            runs = entry.get("runs", [])
            values = [round(score_percent(run.get("score")), 2) for run in runs]
            by_task.setdefault(task, {})[label] = values
    return by_task


def polyline_points(values, left, top, width, height):
    if not values:
        return ""
    n = len(values)
    pts = []
    for i, val in enumerate(values):
        x = left + (width * i / max(n - 1, 1))
        y = top + height - (height * (val / 100.0))
        pts.append((x, y))
    return pts


def svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def build_chart(task: str, series_map: dict[str, list[float]]) -> str:
    width = 980
    height = 420
    left = 90
    right = 40
    top = 70
    bottom = 70
    plot_w = width - left - right
    plot_h = height - top - bottom

    labels = sorted(series_map)
    max_runs = max((len(v) for v in series_map.values()), default=0)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append('<defs>')
    lines.append('<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">')
    lines.append('<stop offset="0%" stop-color="#f8fafc"/>')
    lines.append('<stop offset="100%" stop-color="#eef2ff"/>')
    lines.append('</linearGradient>')
    lines.append('</defs>')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="url(#bg)" rx="20"/>')
    lines.append('<rect x="24" y="24" width="932" height="372" fill="#ffffff" rx="18" stroke="#dbe4f0"/>')
    lines.append(f'<text x="{left}" y="42" font-family="Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#0f172a">{svg_escape(task)} — Per-run rubric score</text>')
    lines.append(f'<text x="{left}" y="61" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#475569">Score = percentage of rubric components passed (tools, handoffs, step decisions, outcome, forbidden actions, evidence)</text>')

    for pct in [0, 25, 50, 75, 100]:
        y = top + plot_h - (plot_h * (pct / 100.0))
        stroke = '#cbd5e1' if pct in [0, 100] else '#e2e8f0'
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="{stroke}" stroke-width="1"/>')
        lines.append(f'<text x="{left-14}" y="{y+4:.1f}" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#64748b">{pct}</text>')

    for i in range(max_runs):
        x = left + (plot_w * i / max(max_runs - 1, 1))
        lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_h}" stroke="#f1f5f9" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{top+plot_h+24}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#64748b">Run {i+1}</text>')

    lines.append(f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#cbd5e1"/>')

    for idx, label in enumerate(labels):
        color = PALETTE[idx % len(PALETTE)]
        pts = polyline_points(series_map[label], left, top, plot_w, plot_h)
        point_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        lines.append(f'<polyline points="{point_str}" fill="none" stroke="{color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>')
        for run_idx, (x, y) in enumerate(pts):
            val = series_map[label][run_idx]
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#ffffff" stroke="{color}" stroke-width="2.5"/>')
            lines.append(f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="11" fill="{color}">{val:.0f}%</text>')

    legend_x = left
    legend_y = height - 28
    cursor_x = legend_x
    for idx, label in enumerate(labels):
        color = PALETTE[idx % len(PALETTE)]
        lines.append(f'<line x1="{cursor_x}" y1="{legend_y}" x2="{cursor_x+22}" y2="{legend_y}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>')
        lines.append(f'<circle cx="{cursor_x+11}" cy="{legend_y}" r="4" fill="#ffffff" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{cursor_x+30}" y="{legend_y+4}" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#334155">{svg_escape(label)}</text>')
        cursor_x += 220

    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite-summary', nargs='+', required=True, help='Suite summary JSON paths')
    parser.add_argument('--output-dir', default='assets', help='Directory for generated SVG charts')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    by_task = collect_series(args.suite_summary)
    for task, series_map in sorted(by_task.items()):
        out = output_dir / f'variance-{slugify_task(task)}.svg'
        out.write_text(build_chart(task, series_map))
        print(out)


if __name__ == '__main__':
    main()
