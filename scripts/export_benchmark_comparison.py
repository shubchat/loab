#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path):
    return json.loads(path.read_text())


def dominant_key(values: dict):
    if not values:
        return ""
    return max(values.items(), key=lambda kv: (kv[1], str(kv[0])))[0] or ""


def flatten_suite_summary(path: Path):
    data = load_json(path)
    metadata = data.get("metadata") or {}
    rows = []
    for entry in data.get("results", []):
        summary = entry.get("summary") or {}
        component = summary.get("component_pass_rate") or {}
        row = {
            "suite_id": data.get("suite_id", ""),
            "suite_name": data.get("suite_name", ""),
            "suite_summary": str(path),
            "benchmark_version": metadata.get("benchmark_version", ""),
            "git_commit": metadata.get("git_commit", ""),
            "policy_document": metadata.get("policy_document", ""),
            "policy_effective_date": metadata.get("policy_effective_date", ""),
            "policy_next_review": metadata.get("policy_next_review", ""),
            "model_label": entry.get("model_label", ""),
            "task": entry.get("task", ""),
            "run_config": entry.get("run_config", ""),
            "batch_id": entry.get("batch_id", ""),
            "total_runs": summary.get("total_runs", 0),
            "completed_runs": summary.get("completed_runs", 0),
            "passed_runs": summary.get("passed_runs", 0),
            "pass_rate": f"{summary.get('pass_rate', 0.0):.4f}",
            "dominant_decision": dominant_key(summary.get("decision_distribution") or {}),
            "decision_distribution": json.dumps(summary.get("decision_distribution") or {}, ensure_ascii=False, sort_keys=True),
            "stop_reason_distribution": json.dumps(summary.get("stop_reason_distribution") or {}, ensure_ascii=False, sort_keys=True),
            "tool_calls_rate": f"{((component.get('tool_calls') or {}).get('rate', 0.0)):.4f}",
            "handoffs_rate": f"{((component.get('handoffs') or {}).get('rate', 0.0)):.4f}",
            "step_decisions_rate": f"{((component.get('step_decisions') or {}).get('rate', 0.0)):.4f}",
            "outcome_rate": f"{((component.get('outcome') or {}).get('rate', 0.0)):.4f}",
            "forbidden_actions_rate": f"{((component.get('forbidden_actions') or {}).get('rate', 0.0)):.4f}",
            "evidence_rate": f"{((component.get('evidence') or {}).get('rate', 0.0)):.4f}",
            "top_failure_signals": json.dumps(summary.get("top_failure_signals") or [], ensure_ascii=False),
        }
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite-summary",
        nargs="+",
        required=True,
        help="One or more suite summary JSON files produced by scripts/run_repeats.py --config",
    )
    parser.add_argument(
        "--csv",
        help="Output CSV path (defaults to loab/results/benchmark-comparison-<timestamp>.csv)",
    )
    args = parser.parse_args()

    rows = []
    for raw in args.suite_summary:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise SystemExit(f"Suite summary not found: {path}")
        rows.extend(flatten_suite_summary(path))

    if not rows:
        raise SystemExit("No rows found in suite summaries")

    out_path = Path(args.csv) if args.csv else ROOT / "loab/results" / f"benchmark-comparison-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "suite_id",
        "suite_name",
        "suite_summary",
        "benchmark_version",
        "git_commit",
        "policy_document",
        "policy_effective_date",
        "policy_next_review",
        "model_label",
        "task",
        "run_config",
        "batch_id",
        "total_runs",
        "completed_runs",
        "passed_runs",
        "pass_rate",
        "dominant_decision",
        "decision_distribution",
        "stop_reason_distribution",
        "tool_calls_rate",
        "handoffs_rate",
        "step_decisions_rate",
        "outcome_rate",
        "forbidden_actions_rate",
        "evidence_rate",
        "top_failure_signals",
    ]

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(out_path)


if __name__ == "__main__":
    main()
