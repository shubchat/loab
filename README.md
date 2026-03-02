# LOAB — Lending Operations Agent Benchmark

<p align="center">
  <img src="./assets/loab-overview-flow.svg" alt="LOAB benchmark flow — multi-agent mortgage lifecycle" width="100%"/>
</p>

**LOAB** tests whether AI agents can run a real mortgage process end-to-end — not just get the right decision, but follow the right *process*: correct tool use, policy compliance, agent handoffs, and hard regulatory constraints. Getting the answer right while skipping KYC isn't a pass. The current release covers three origination tasks as a proof-of-concept, with credit decisioning, servicing, collections, and compliance tasks in development. Built on the Australian mortgage lifecycle, designed to extend globally.

---

## Why This Exists

Most AI benchmarks ask: *did the model get the right answer?*

In lending, that's not enough. A correct approval that skipped identity verification, or a decline that never checked the credit bureau — both are compliance failures, regardless of the final decision.

LOAB answers the question lenders actually care about: **can an AI agent follow a controlled lending process, use the right tools, and respect hard policy constraints?**

---

## How Scoring Works

<p align="center">
  <img src="./assets/loab-overview-scoring.svg" alt="LOAB scoring rubric" width="100%"/>
</p>

A run only passes if **both the decision and the process are correct**. Each run is evaluated across five rubric components:

| Component | Weight | What It Measures |
|---|:---:|---|
| **Outcome** | 30% | Final decision matches the expected result exactly |
| **Tool Calls** | 25% | All required tools called with correct arguments, in the right step order |
| **Handoffs** | 20% | Correct agent-to-agent routing with all required payload keys |
| **Forbidden Actions** | 15% | No prohibited tools, decisions, or communications were executed |
| **Evidence** | 10% | Tool responses contain the expected data fields in the agent's reasoning |

---

## Current Task Suite

The proof-of-concept covers three origination scenarios, each designed to test a different failure mode:

| Task | Scenario | Expected Outcome | What It Tests |
|---|---|:---:|---|
| `task-01` | Prime PAYG borrower, complete file | `APPROVE` | Can the agent process a clean file without being overconservative? |
| `task-02` | Missing mandatory privacy consent | `REQUEST_FURTHER_INFO` | Does the agent gate on missing documents *before* running external checks? |
| `task-03` | Near-prime borrower, DTI > 6.0× | `DECLINE` | Does the agent enforce a hard policy limit with no exception pathway? |

---

## Benchmark Results — Origination PoC

> **Run config:** 4 simulations per task × 2 models = 24 total runs

### Full-Rubric Pass Rate

This is the headline metric. A run only counts as a pass when every rubric component is satisfied:

| Task | Expected | GPT-5.2 | Claude Opus 4.6 |
|---|:---:|:---:|:---:|
| `task-01` — Clean approve | `APPROVE` | **3/4 (75%)** | 0/4 (0%) |
| `task-02` — Missing docs gate | `REQUEST_FURTHER_INFO` | 0/4 (0%) | **1/4 (25%)** |
| `task-03` — Hard DTI decline | `DECLINE` | 0/4 (0%) | **4/4 (100%)** |

### The Key Insight: Outcome ≠ Process

A model can reach the right answer through the wrong process and still fail. This table shows how much they diverge:

| Model | Outcome Accuracy | Full-Rubric Pass | Gap |
|---|:---:|:---:|:---:|
| GPT-5.2 | 8/12 (66.7%) | 3/12 (25.0%) | **−41.7pp** |
| Claude Opus 4.6 | 9/12 (75.0%) | 5/12 (41.7%) | **−33.3pp** |

Both models lose substantial pass rates when process fidelity is required — this is the core signal LOAB is designed to surface.

### Decision Distribution

How each model actually decided across 4 runs per task:

| Task | GPT-5.2 | Claude Opus 4.6 |
|---|---|---|
| `task-01` | APPROVE ×4 | CONDITIONAL_APPROVE ×3, APPROVE ×1 |
| `task-02` | REQUEST_FURTHER_INFO ×4 | REQUEST_FURTHER_INFO ×4 |
| `task-03` | APPROVE ×2, CONDITIONAL_APPROVE ×2 | DECLINE ×4 |

### Component-Level Pass Rates

Where exactly each model breaks down:

| Component | GPT-5.2 | Claude Opus 4.6 |
|---|:---:|:---:|
| Tool Calls | 100% | 83.3% |
| Handoffs | 100% | 100% |
| Step Decisions | 100% | 100% |
| Outcome | 66.7% | 75.0% |
| Forbidden Actions | 25.0% | 66.7% |
| Evidence | 100% | 100% |

---

## Key Findings

### 1. GPT-5.2 is stronger on clean approval paths

On `task-01`, GPT passed 75% of runs. It reliably reached APPROVE and handled the multi-step Processing Officer → Underwriter flow well. Failures came from process discipline, not from the credit answer itself. This suggests GPT is currently better aligned to straightforward prime-file progression.

### 2. Claude Opus 4.6 is stronger on hard-policy enforcement

On `task-03`, Claude passed 100% of runs. It always routed correctly to Credit Manager, always issued the hard decline, and consistently respected the DTI > 6.0× no-exception rule. This suggests Claude is currently better aligned to strict policy enforcement.

### 3. Task-02 is the process fidelity stress test

Both models always reached the correct outcome (`REQUEST_FURTHER_INFO`). But the full rubric required no external checks before resolving the missing privacy consent. GPT failed all 4 runs by performing external checks too early. Claude passed 1/4, failing the others for missing policy lookups or premature external checks. This is exactly the kind of separation LOAB is designed to create.

### 4. Run-to-run variance is a real deployment concern

GPT-5.2 split 50/50 between APPROVE and CONDITIONAL_APPROVE on `task-03` — a task with a hard decline policy. Claude showed 3:1 CONDITIONAL_APPROVE vs APPROVE variance on `task-01`. Neither model produces deterministic behavior, which is a significant issue for production lending systems.

---

## Roadmap

The full LOAB lifecycle suite is in active development:

| Stage | Status | Example Scenario |
|---|:---:|---|
| **Origination** | ✅ PoC live | Prime approve, missing docs gate, hard decline |
| **Credit Decisioning** | 🔧 In dev | Self-employed DTI breach, sub-prime hard decline |
| **Servicing** | 🔧 In dev | Loan discharge, closure tasks |
| **Collections** | 🔧 In dev | Hardship assessment, collections suspension |
| **Compliance** | 🔧 In dev | Synthetic identity fraud detection, SAR filing |

---

## Repository Structure

```text
loab/
├── agents/           ← Role prompts + decision contracts (per agent)
├── benchmark/        ← Run configs, suite configs, leaderboard
├── company/          ← Meridian Bank policy, product rates, mock APIs
├── customers/        ← Synthetic applicant profiles + backstories
├── tasks/            ← Task definitions, rubrics, pending files
│   └── origination/
│       ├── task-01/  ← Clean PAYG approval
│       ├── task-02/  ← Missing privacy consent
│       └── task-03/  ← Hard DTI decline
└── results/          ← Run outputs (gitignored)
```

---

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp loab/.env.example loab/.env   # Add your provider API keys

# Run a single task
python scripts/run_task.py --task origination/task-01

# Run a full suite (repeated runs)
python scripts/run_repeats.py --config loab/benchmark/suites/origination-poc.json --load-env

# Export comparison CSV
python scripts/export_benchmark_comparison.py \
  --suite-summary results/suite-summary-a.json results/suite-summary-b.json
```

---

## Current Limitations

- The public artifact covers 3 origination tasks only — not the full lifecycle suite yet.
- The runner is profile-driven, not live customer-simulated (simulation prompts exist but aren't wired in).
- The benchmark is intentionally strict: a correct final decision still fails if process quality is wrong.
- Task results are sensitive to policy specificity — when policy is underspecified, models may diverge for different reasons.

---

## License

[Add license info]
