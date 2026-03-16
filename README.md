# LOAB — Lending Operations Agent Benchmark

<p align="center">
  <img src="./assets/loab-overview-flow.svg" alt="LOAB benchmark flow — multi-agent mortgage lifecycle" width="100%"/>
</p>

**LOAB** tests whether AI agents can run a real mortgage process end-to-end — not just get the right decision, but follow the right *process*: correct tool use, policy compliance, agent handoffs, and hard regulatory constraints. Getting the answer right while skipping KYC isn't a pass. The current release covers three origination tasks as a proof-of-concept, with credit decisioning, servicing, collections, and compliance tasks in development. Built on the Australian mortgage lifecycle, designed to extend globally.

**Current benchmark version:** `v0.1.0`  
**Policy baseline:** `MBL-POL-CREDIT-RESI-V3.2` (Effective `1 February 2025`)  
**Change log:** `CHANGELOG.md`

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

> **Run configs now compared:** 4 simulations per task × 6 evaluated settings = 72 total scored runs

### Baseline Comparison

This is the current baseline across the original two models plus GPT-5.4 with no explicit reasoning override.

| Model | Outcome Accuracy | Full-Rubric Pass | Gap |
|---|:---:|:---:|:---:|
| GPT-5.2 | 8/12 (66.7%) | 3/12 (25.0%) | **−41.7pp** |
| GPT-5.4 (default / unset) | 8/12 (66.7%) | 4/12 (33.3%) | **−33.3pp** |
| Claude Opus 4.6 | 9/12 (75.0%) | 5/12 (41.7%) | **−33.3pp** |

GPT-5.4 default improves on GPT-5.2 overall, but it still lags Claude on full-rubric pass rate.

### GPT-5.4 Reasoning Effort Sweep

The same 3-task origination suite was rerun for GPT-5.4 with explicit reasoning-effort settings:

| GPT-5.4 Setting | Outcome Accuracy | Full-Rubric Pass | Gap |
|---|:---:|:---:|:---:|
| Default / unset | 8/12 (66.7%) | 4/12 (33.3%) | **−33.3pp** |
| Low | 9/12 (75.0%) | 8/12 (66.7%) | **−8.3pp** |
| Medium | 9/12 (75.0%) | 8/12 (66.7%) | **−8.3pp** |
| High | 9/12 (75.0%) | 5/12 (41.7%) | **−33.3pp** |

Low and medium are the strongest GPT-5.4 settings tested. High improves outcome accuracy over the default run, but loses much of the process-fidelity benefit.

### Full-Rubric Pass Rate by Task

This is the headline metric. A run only counts as a pass when every rubric component is satisfied:

| Task | Expected | GPT-5.2 | GPT-5.4 Default | GPT-5.4 Low | GPT-5.4 Medium | GPT-5.4 High | Claude Opus 4.6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `task-01` — Clean approve | `APPROVE` | **3/4 (75%)** | **3/4 (75%)** | 1/4 (25%) | 1/4 (25%) | 0/4 (0%) | 0/4 (0%) |
| `task-02` — Missing docs gate | `REQUEST_FURTHER_INFO` | 0/4 (0%) | 0/4 (0%) | **4/4 (100%)** | **4/4 (100%)** | 3/4 (75%) | 1/4 (25%) |
| `task-03` — Hard DTI decline | `DECLINE` | 0/4 (0%) | 1/4 (25%) | 3/4 (75%) | 3/4 (75%) | 2/4 (50%) | **4/4 (100%)** |

### The Key Insight: Outcome ≠ Process

A model can reach the right answer through the wrong process and still fail. This table shows how much they diverge:

| Setting | Outcome Accuracy | Full-Rubric Pass | Gap |
|---|:---:|:---:|:---:|
| GPT-5.2 | 8/12 (66.7%) | 3/12 (25.0%) | **−41.7pp** |
| GPT-5.4 Default | 8/12 (66.7%) | 4/12 (33.3%) | **−33.3pp** |
| GPT-5.4 Low | 9/12 (75.0%) | 8/12 (66.7%) | **−8.3pp** |
| GPT-5.4 Medium | 9/12 (75.0%) | 8/12 (66.7%) | **−8.3pp** |
| GPT-5.4 High | 9/12 (75.0%) | 5/12 (41.7%) | **−33.3pp** |
| Claude Opus 4.6 | 9/12 (75.0%) | 5/12 (41.7%) | **−33.3pp** |

The key result is not just that GPT-5.4 improves with explicit reasoning control — it is that low/medium reasoning reduce the outcome-vs-process gap dramatically.

### GPT-5.4 Decision Distribution by Setting

How GPT-5.4 actually decided across 4 runs per task under each reasoning configuration:

| Task | Default / Unset | Low | Medium | High |
|---|---|---|---|---|
| `task-01` | APPROVE ×3, CONDITIONAL_APPROVE ×1 | APPROVE ×1, DECLINE ×1, CONDITIONAL_APPROVE ×2 | APPROVE ×1, DECLINE ×2, CONDITIONAL_APPROVE ×1 | APPROVE ×1, CONDITIONAL_APPROVE ×3 |
| `task-02` | REQUEST_FURTHER_INFO ×4 | REQUEST_FURTHER_INFO ×4 | REQUEST_FURTHER_INFO ×4 | REQUEST_FURTHER_INFO ×4 |
| `task-03` | CONDITIONAL_APPROVE ×3, DECLINE ×1 | DECLINE ×4 | DECLINE ×4 | DECLINE ×4 |

### Component-Level Pass Rates

Where exactly the main models and GPT-5.4 settings break down:

| Component | GPT-5.2 | GPT-5.4 Default | GPT-5.4 Low | GPT-5.4 Medium | GPT-5.4 High | Claude Opus 4.6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Tool Calls | 100.0% | 75.0% | 100.0% | 100.0% | 100.0% | 83.3% |
| Handoffs | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| Step Decisions | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| Outcome | 66.7% | 66.7% | 75.0% | 75.0% | 75.0% | 75.0% |
| Forbidden Actions | 25.0% | 66.7% | 75.0% | 75.0% | 66.7% | 66.7% |
| Evidence | 100.0% | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% |

---

## Key Findings

### 1. GPT-5.4 low/medium are the current best GPT settings

With explicit reasoning effort set to `low` or `medium`, GPT-5.4 reached **8/12 (66.7%)** full-rubric pass rate, up from **4/12 (33.3%)** at the default setting and **3/12 (25.0%)** for GPT-5.2. The improvement came from much stronger process fidelity on the missing-doc and hard-decline tasks.

### 2. The improvement is driven by task-02 and task-03, not task-01

Default GPT-5.4 was still weak on process gating and hard-limit enforcement:
- `task-02`: **0/4**
- `task-03`: **1/4**

At `low` and `medium`, those same tasks improved to:
- `task-02`: **4/4**
- `task-03`: **3/4**

The tradeoff is that `task-01` regressed from **3/4** at default to **1/4** at both `low` and `medium`.

### 3. High reasoning effort is worse than low/medium

`high` preserved the same 75.0% outcome accuracy as `low` and `medium`, but full-rubric pass rate dropped to **5/12 (41.7%)**. The main regression was clean-approve handling:
- `task-01`: **0/4**
- `task-02`: **3/4**
- `task-03`: **2/4**

### 4. Claude remains the strongest hard-policy model

Claude Opus 4.6 still leads on the strict hard-decline path:
- `task-03`: **4/4**
- overall full-rubric pass: **5/12 (41.7%)**

GPT-5.4 low/medium beat Claude overall, but Claude remains the most reliable model in the suite on the hardest no-exception policy path.

### 5. Run-to-run variance is still a deployment concern

Even at the stronger GPT-5.4 settings, the model still varied materially on `task-01`:
- `low`: APPROVE ×1, DECLINE ×1, CONDITIONAL_APPROVE ×2
- `medium`: APPROVE ×1, DECLINE ×2, CONDITIONAL_APPROVE ×1

So reasoning control improved process compliance overall, but did not eliminate variance on the clean-file approval scenario.

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

# Run a single task with MiniMax-M2.5
python scripts/run_task.py --task origination/task-01 \
  --run-config loab/benchmark/run_configs/minimax_m2_5_all.json --run_id minimax-test-01

# Run a full suite (repeated runs)
python scripts/run_repeats.py --config loab/benchmark/suites/origination_poc_3x4.json --load-env

# Run MiniMax-only suite
python scripts/run_repeats.py --config loab/benchmark/suites/origination_poc_3x4_minimax.json --load-env

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

## Citation

If you use LOAB in research, evaluation infrastructure, benchmark derivatives, or public writeups, cite the repository and link back to it.

```bibtex
@misc{loab2026,
  title        = {LOAB: Lending Operations Agent Benchmark},
  author       = {LOAB contributors},
  year         = {2026},
  howpublished = {GitHub repository},
  note         = {Benchmark for multi-agent, tool-using lending workflows}
}
```

At minimum, include:
- `LOAB — Lending Operations Agent Benchmark`
- the repository link
- the date or commit used for the evaluation

---

## Versioning

LOAB uses semantic versioning for benchmark comparability:
- `MAJOR`: breaking changes to benchmark semantics (scoring/orchestration/policy baseline that invalidate prior comparisons)
- `MINOR`: additive comparable changes (new tasks, suites, models, charts, tooling)
- `PATCH`: bug fixes and documentation updates that do not intentionally change benchmark semantics

Version source of truth:
- `loab/benchmark/VERSION`

Every suite summary and exported comparison CSV includes metadata for:
- benchmark version
- git commit
- policy document and effective date

Tag a release:

```bash
git tag -a v0.1.0 -m "LOAB benchmark v0.1.0"
git push origin v0.1.0
```

---

## License

This repository is released under the MIT License.

You may use, modify, and build on LOAB, including commercial use, provided the license and copyright notice are preserved.
