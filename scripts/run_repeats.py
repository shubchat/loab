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
DEFAULT_RUN_CONFIG = ROOT / "loab/benchmark/run_config.json"
DEFAULT_VERSION_FILE = ROOT / "loab/benchmark/VERSION"
DEFAULT_POLICY_FILE = ROOT / "loab/company/policy/meridian_bank_credit_policy.md"


def slugify_task(task: str) -> str:
    return task.strip().replace("/", "-")


def slugify_label(label: str) -> str:
    safe = []
    for ch in label.strip().lower():
        if ch.isalnum():
            safe.append(ch)
        elif ch in {"-", "_"}:
            safe.append(ch)
        else:
            safe.append("-")
    return "".join(safe).strip("-") or "run"


def load_json(path: Path):
    return json.loads(path.read_text())


def read_benchmark_version() -> str:
    if DEFAULT_VERSION_FILE.exists():
        return DEFAULT_VERSION_FILE.read_text().strip()
    return "v0.0.0"


def get_git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
            .strip()
        )
    except Exception:
        return ""


def parse_policy_metadata():
    out = {
        "policy_document": "",
        "policy_effective_date": "",
        "policy_next_review": "",
        "policy_source": str(DEFAULT_POLICY_FILE),
    }
    if not DEFAULT_POLICY_FILE.exists():
        return out
    text = DEFAULT_POLICY_FILE.read_text()
    for raw in text.splitlines():
        line = raw.strip().strip("*")
        if "MBL-POL-CREDIT-RESI-" in line and "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if parts:
                out["policy_document"] = parts[0]
            for p in parts:
                if p.lower().startswith("effective "):
                    out["policy_effective_date"] = p.replace("Effective ", "", 1).strip()
        if line.lower().startswith("next review:"):
            out["policy_next_review"] = line.split(":", 1)[1].strip().split(".")[0].strip()
    return out


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


def run_once(task: str, run_id: str, python_bin: str, run_config: str | None = None):
    cmd = [python_bin, str(ROOT / "scripts/run_task.py"), "--task", task, "--run_id", run_id]
    if run_config:
        cmd.extend(["--run-config", run_config])
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
        out["score"] = load_json(score_path)
    if orchestrator_path.exists():
        out["orchestrator"] = load_json(orchestrator_path)
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


def run_single_task_mode(args):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_slug = slugify_task(args.task)
    batch_id = f"{args.prefix}-{task_slug}-{ts}"
    print(f"Batch: {batch_id}", flush=True)
    print(f"Task:  {args.task}", flush=True)
    print(f"Runs:  {args.n}", flush=True)

    runs = []
    for i in range(1, args.n + 1):
        run_id = f"{batch_id}-r{i:02d}"
        print(f"[{i}/{args.n}] {run_id}", flush=True)
        res = run_once(args.task, run_id, args.python_bin, args.run_config)
        runs.append(res)
        if res["returncode"] != 0:
            print(f"  failed rc={res['returncode']}", flush=True)
        else:
            score = res.get("score") or {}
            print(
                f"  done passed={score.get('passed')} "
                f"decision={(score.get('outcome') or {}).get('observed')}",
                flush=True,
            )

    summary = summarize(runs)
    metadata = {
        "benchmark_version": read_benchmark_version(),
        "git_commit": get_git_commit(),
        **parse_policy_metadata(),
    }
    out_path = ROOT / "loab/results" / f"{batch_id}-summary.json"
    out_path.write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "task": args.task,
                "generated_at": ts,
                "metadata": metadata,
                "runs": runs,
                "summary": summary,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    print("\nSummary", flush=True)
    print(f"- pass_rate: {summary['pass_rate']:.2%} ({summary['passed_runs']}/{summary['completed_runs']})", flush=True)
    print(f"- decisions: {summary['decision_distribution']}", flush=True)
    print(f"- stop_reasons: {summary['stop_reason_distribution']}", flush=True)
    print(f"- summary_file: {out_path}", flush=True)


def run_suite_mode(args):
    suite_cfg_path = Path(args.config)
    if not suite_cfg_path.is_absolute():
        suite_cfg_path = ROOT / suite_cfg_path
    suite_cfg = load_json(suite_cfg_path)

    tasks = suite_cfg.get("tasks") or []
    simulations_per_task = int(suite_cfg.get("simulations_per_task", 0))
    model_runs = suite_cfg.get("model_runs") or []
    suite_name = suite_cfg.get("suite_name") or suite_cfg_path.stem
    if not tasks:
        raise SystemExit("Suite config missing tasks")
    if simulations_per_task <= 0:
        raise SystemExit("Suite config simulations_per_task must be > 0")
    if not model_runs:
        raise SystemExit("Suite config missing model_runs")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suite_id = f"{suite_cfg.get('prefix', 'suite')}-{slugify_label(suite_name)}-{ts}"
    metadata = {
        "benchmark_version": suite_cfg.get("benchmark_version") or read_benchmark_version(),
        "git_commit": get_git_commit(),
        **parse_policy_metadata(),
    }
    print(f"Suite: {suite_id}", flush=True)
    print(f"Config: {suite_cfg_path}", flush=True)
    print(f"Tasks: {tasks}", flush=True)
    print(f"Simulations per task: {simulations_per_task}", flush=True)
    print(f"Model runs: {[m.get('label') for m in model_runs]}", flush=True)

    suite_results = []
    total_runs = len(tasks) * simulations_per_task * len(model_runs)
    run_counter = 0

    for model_run in model_runs:
        label = model_run.get("label")
        run_config = model_run.get("run_config")
        if not label or not run_config:
            raise SystemExit("Each model_runs entry must include label and run_config")
        run_cfg_path = Path(run_config)
        if not run_cfg_path.is_absolute():
            run_cfg_path = ROOT / run_cfg_path
        if not run_cfg_path.exists():
            raise SystemExit(f"Run config not found: {run_cfg_path}")

        print(f"\nModel: {label} ({run_cfg_path})", flush=True)
        for task in tasks:
            task_slug = slugify_task(task)
            batch_id = f"{suite_id}-{slugify_label(label)}-{task_slug}"
            print(f"  Task: {task}", flush=True)
            runs = []
            for i in range(1, simulations_per_task + 1):
                run_counter += 1
                run_id = f"{batch_id}-r{i:02d}"
                print(f"    [{run_counter}/{total_runs}] {run_id}", flush=True)
                res = run_once(task, run_id, args.python_bin, str(run_cfg_path))
                runs.append(res)
                if res["returncode"] != 0:
                    print(f"      failed rc={res['returncode']}", flush=True)
                else:
                    score = res.get("score") or {}
                    print(
                        f"      done passed={score.get('passed')} "
                        f"decision={(score.get('outcome') or {}).get('observed')}",
                        flush=True,
                    )
            task_summary = summarize(runs)
            suite_results.append(
                {
                    "model_label": label,
                    "run_config": str(run_cfg_path),
                    "task": task,
                    "batch_id": batch_id,
                    "runs": runs,
                    "summary": task_summary,
                }
            )
            print(
                f"    summary pass_rate={task_summary['pass_rate']:.2%} "
                f"({task_summary['passed_runs']}/{task_summary['completed_runs']})",
                flush=True,
            )

    out_path = ROOT / "loab/results" / f"{suite_id}-suite-summary.json"
    payload = {
        "suite_id": suite_id,
        "suite_name": suite_name,
        "generated_at": ts,
        "metadata": metadata,
        "suite_config": str(suite_cfg_path),
        "tasks": tasks,
        "simulations_per_task": simulations_per_task,
        "model_runs": model_runs,
        "results": suite_results,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print("\nSuite Summary", flush=True)
    print(f"- summary_file: {out_path}", flush=True)
    for entry in suite_results:
        summary = entry["summary"]
        print(
            f"- {entry['model_label']} | {entry['task']}: "
            f"{summary['pass_rate']:.2%} ({summary['passed_runs']}/{summary['completed_runs']})",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", help="Taxonomy-qualified task id, e.g. origination/task-01")
    parser.add_argument("--config", help="Suite config JSON for multi-task, multi-model runs")
    parser.add_argument("--n", type=int, default=5, help="Number of repeated runs (single-task mode)")
    parser.add_argument("--prefix", default="batch", help="Run id prefix (single-task mode)")
    parser.add_argument("--python-bin", default=sys.executable, help="Python binary for run_task.py")
    parser.add_argument("--run-config", default=str(DEFAULT_RUN_CONFIG), help="Run config JSON for single-task mode")
    parser.add_argument("--load-env", action="store_true", help="Load .env into subprocess environment")
    args = parser.parse_args()

    if args.load_env:
        load_dotenv(ROOT / "loab/.env")
        load_dotenv(ROOT / ".env")

    if args.config:
        run_suite_mode(args)
        return
    if not args.task:
        parser.error("--task is required unless --config is provided")
    run_single_task_mode(args)


if __name__ == "__main__":
    main()
