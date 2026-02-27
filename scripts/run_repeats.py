#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path):
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def run_once(task: str, run_id: str, python_bin: str):
    cmd = [python_bin, str(ROOT / "scripts/run_task.py"), "--task", task, "--run_id", run_id]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result_dir = ROOT / "loab/results" / run_id / task
    score_path = result_dir / "score.json"
    orchestrator_path = result_dir / "orchestrator.json"

    out = {
        "run_id": run_id,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-1200:],
        "stderr_tail": (proc.stderr or "")[-1200:],
        "score": None,
        "orchestrator": None,
    }
    if score_path.exists():
        out["score"] = json.loads(score_path.read_text())
    if orchestrator_path.exists():
        out["orchestrator"] = json.loads(orchestrator_path.read_text())
    return out


def summarize(runs):
    total = len(runs)
    completed = sum(1 for r in runs if r.get("score") is not None)
    passed = sum(1 for r in runs if (r.get("score") or {}).get("passed") is True)

    decisions = Counter()
    stop_reasons = Counter()
    component = Counter()
    component_total = Counter()
    failures = Counter()

    for r in runs:
        score = r.get("score") or {}
        orch = r.get("orchestrator") or {}
        decisions[(score.get("outcome") or {}).get("observed")] += 1
        stop_reasons[orch.get("stop_reason")] += 1

        for key in ["tool_calls", "handoffs", "step_decisions", "outcome", "forbidden_actions", "evidence"]:
            if key in score:
                component_total[key] += 1
                if score[key].get("passed"):
                    component[key] += 1

        if score and not score.get("passed"):
            if not (score.get("outcome") or {}).get("passed"):
                failures[f"outcome:{(score.get('outcome') or {}).get('observed')}"] += 1
            for miss in (score.get("tool_calls") or {}).get("missing", []):
                failures[f"missing_tool:{miss.get('tool')}@step{miss.get('step')}"] += 1
            for miss in (score.get("handoffs") or {}).get("missing_keys", []):
                failures[f"handoff_key:{miss}"] += 1
            for miss in (score.get("evidence") or {}).get("missing", []):
                failures[f"evidence:{miss.get('tool')}@step{miss.get('step')}"] += 1

    return {
        "total_runs": total,
        "completed_runs": completed,
        "passed_runs": passed,
        "pass_rate": (passed / completed) if completed else 0.0,
        "decision_distribution": dict(decisions),
        "stop_reason_distribution": dict(stop_reasons),
        "component_pass_rate": {
            k: {
                "passed": component[k],
                "total": component_total[k],
                "rate": (component[k] / component_total[k]) if component_total[k] else 0.0,
            }
            for k in ["tool_calls", "handoffs", "step_decisions", "outcome", "forbidden_actions", "evidence"]
        },
        "top_failure_signals": failures.most_common(15),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="Task folder name, e.g. task-01-origination")
    parser.add_argument("--n", type=int, default=5, help="Number of repeated runs")
    parser.add_argument("--prefix", default="batch", help="Run id prefix")
    parser.add_argument("--python-bin", default=sys.executable, help="Python binary for run_task.py")
    parser.add_argument("--load-env", action="store_true", help="Load .env into subprocess environment")
    args = parser.parse_args()

    if args.load_env:
        load_dotenv(ROOT / ".env")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_id = f"{args.prefix}-{args.task}-{ts}"
    print(f"Batch: {batch_id}")
    print(f"Task:  {args.task}")
    print(f"Runs:  {args.n}")

    runs = []
    for i in range(1, args.n + 1):
        run_id = f"{batch_id}-r{i:02d}"
        print(f"[{i}/{args.n}] {run_id}")
        res = run_once(args.task, run_id, args.python_bin)
        runs.append(res)
        if res["returncode"] != 0:
            print(f"  failed rc={res['returncode']}")
        else:
            score = res.get("score") or {}
            print(
                f"  done passed={score.get('passed')} "
                f"decision={(score.get('outcome') or {}).get('observed')}"
            )

    summary = summarize(runs)
    out_path = ROOT / "loab/results" / f"{batch_id}-summary.json"
    out_path.write_text(json.dumps({"batch_id": batch_id, "task": args.task, "runs": runs, "summary": summary}, indent=2) + "\n")

    print("\nSummary")
    print(f"- pass_rate: {summary['pass_rate']:.2%} ({summary['passed_runs']}/{summary['completed_runs']})")
    print(f"- decisions: {summary['decision_distribution']}")
    print(f"- stop_reasons: {summary['stop_reason_distribution']}")
    print(f"- summary_file: {out_path}")


if __name__ == "__main__":
    main()
