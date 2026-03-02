# LOAB — Lending Operations Agent Benchmark

<p align="center">
  <img src="./assets/loab-overview-flow.svg" alt="LOAB benchmark flow — multi-agent mortgage lifecycle" width="100%"/>
</p>

<p align="center">
  <img src="./assets/loab-overview-scoring.svg" alt="LOAB scoring rubric view" width="100%"/>
</p>

LOAB evaluates tool-using LLM agents across the Australian mortgage lifecycle: origination, credit decisioning, servicing, collections, and compliance.

The benchmark is designed to test more than final answers. Each run measures:
- correct role routing
- correct tool selection and arguments
- policy adherence
- handoff quality
- forbidden action avoidance
- final outcome correctness

The current runner is profile-driven. Applicant data comes from `profile.json`, while application-specific document state comes from task `pendingfiles.json`.

## What This Repository Currently Demonstrates

The current public artifact is an origination proof-of-concept suite:
- `origination/task-01` — clean PAYG approval path
- `origination/task-02` — missing mandatory privacy consent (request more information)
- `origination/task-03` — near-prime + hard DTI decline path

This snapshot was run with:
- `4` simulations per task
- `2` model configurations
- `24` total task runs

Current benchmarked models:
- `gpt-5.2`
- `claude-opus-4-6-2`

The suite configs are ready to add a third model immediately, but the current artifact covers two.

## Benchmark Snapshot

### Suite Definition

- Tasks: `origination/task-01`, `origination/task-02`, `origination/task-03`
- Simulations per task: `4`
- GPT config: `loab/benchmark/run_configs/gpt_5_2_all.json`
- Claude config: `loab/benchmark/run_configs/claude_opus_4_6_all.json`
- Comparison CSV: `loab/results/benchmark-comparison-20260302-151052.csv`

### Full-Rubric Pass Rate

A run only passes if the agent gets both:
- the correct final outcome
- the correct process (tool ordering, policy usage, handoffs, and no forbidden actions)

| Task | Expected Outcome | GPT-5.2 | Claude Opus 4.6 | What This Task Tests |
|---|---|---:|---:|---|
| `origination/task-01` | `APPROVE` | `3/4` (`75%`) | `0/4` (`0%`) | Clean approval path, serviceability discipline, non-overconservative underwriting |
| `origination/task-02` | `REQUEST_FURTHER_INFO` | `0/4` (`0%`) | `1/4` (`25%`) | Mandatory document gating before any external checks |
| `origination/task-03` | `DECLINE` | `0/4` (`0%`) | `4/4` (`100%`) | Hard-policy decline (`DTI > 6.0x`) with no exception pathway |

### Pass-Rate Chart

```text
Full rubric pass rate (4 simulations per task)

origination/task-01  GPT-5.2          [###.]  75%
origination/task-01  Claude Opus 4.6  [....]   0%

origination/task-02  GPT-5.2          [....]   0%
origination/task-02  Claude Opus 4.6  [#...]  25%

origination/task-03  GPT-5.2          [....]   0%
origination/task-03  Claude Opus 4.6  [####] 100%
```

### Outcome-Only Accuracy vs Process Fidelity

This distinction matters. A model can reach the right outcome for the wrong reason and still fail the benchmark.

| Model | Correct Final Outcome | Full Rubric Pass | Interpretation |
|---|---:|---:|---|
| `GPT-5.2` | `8/12` (`66.7%`) | `3/12` (`25.0%`) | More willing to approve; lower process fidelity on hard constraints |
| `Claude Opus 4.6` | `9/12` (`75.0%`) | `5/12` (`41.7%`) | More policy-conservative; stronger hard-limit adherence |

```text
Overall outcome-only accuracy vs full-rubric pass

GPT-5.2          outcome [#######...]  66.7%
GPT-5.2          full    [##........]  25.0%

Claude Opus 4.6 outcome [########..]  75.0%
Claude Opus 4.6 full    [####......]  41.7%
```

### Decision Distribution

| Task | GPT-5.2 Decision Distribution | Claude Opus 4.6 Decision Distribution |
|---|---|---|
| `origination/task-01` | `APPROVE x4` | `CONDITIONAL_APPROVE x3`, `APPROVE x1` |
| `origination/task-02` | `REQUEST_FURTHER_INFO x4` | `REQUEST_FURTHER_INFO x4` |
| `origination/task-03` | `APPROVE x2`, `CONDITIONAL_APPROVE x2` | `DECLINE x4` |

## Key Findings From The Current Suite

### 1. GPT-5.2 is materially stronger on the clean approval path

On `origination/task-01`, GPT passed `75%` of runs.

Observed behavior:
- it reliably reached `APPROVE`
- it generally handled the multi-step PO -> Underwriter flow well
- the remaining failures came from process discipline, not from the high-level credit answer

This suggests GPT is currently better aligned to straightforward prime-file progression.

### 2. Claude Opus 4.6 is materially stronger on hard-policy enforcement

On `origination/task-03`, Claude passed `100%` of runs.

Observed behavior:
- it always routed correctly to `Credit Manager`
- it always issued the correct hard decline
- it consistently respected the `DTI > 6.0x` no-exception rule

This suggests Claude is currently better aligned to strict policy enforcement under hard-limit cases.

### 3. Task 02 separates outcome correctness from process correctness

On `origination/task-02`, both models always reached the correct final outcome:
- `REQUEST_FURTHER_INFO`

But full pass required more than that:
- no external checks before missing `Privacy Consent` is resolved
- correct policy usage
- correct PO-stage stop behavior

What happened:
- GPT failed all `4/4` full-rubric runs because it consistently performed external checks before stopping
- Claude passed `1/4`; the other runs failed for either:
  - missing one required policy lookup, or
  - still performing external checks too early

This is exactly the kind of benchmark pressure LOAB is intended to create.

### 4. The benchmark already exposes meaningful model personality differences

Current model tendencies are not subtle:
- GPT is more approval-forward and more likely to override hard constraints with compensating logic
- Claude is more conservative and more likely to condition or decline where policy boundaries are hard

This is useful operationally because these are the behaviors lenders need to understand before deploying an LLM into a live process.

## Next Steps

The current artifact is intentionally narrow: a `3`-task origination proof of concept. The next expansion steps are:

### 1. Deepen Origination

Add more origination cases so the benchmark tests a wider spread of pre-settlement credit behavior:
- additional PAYG approval variants
- missing-document and stale-document scenarios
- self-employed assessment paths
- thin-file and near-prime edge cases
- fraud-triggered origination holds
- co-borrower files with mixed applicant strength
- borderline serviceability and genuine-savings cases

The goal is to make origination a strong standalone benchmark suite before expanding outward.

### 2. Expand Other Workstreams

Bring the same repeated-run benchmark format to the rest of the mortgage lifecycle:
- `decisioning`
- `servicing`
- `collections`
- `compliance`

Each workstream should have multiple tasks with:
- clear policy-grounded expected outcomes
- explicit process checks
- repeated-run variance measurement

That will turn LOAB from an origination proof of concept into a true lifecycle benchmark.

### 3. Add Cross-Workstream / Intersection Tasks

Some of the hardest real-world cases sit between workstreams rather than inside one department. LOAB should explicitly test those intersections, for example:
- origination -> fraud / compliance handoff
- servicing -> collections transition
- collections -> hardship routing
- hardship -> compliance reporting
- payoff / closure cases with fraud or AML indicators

These cross-workstream tasks are important because they test:
- routing precedence
- handoff quality across teams
- whether agents follow policy when multiple policies apply at once

### 4. Broaden Model Coverage

The current artifact compares:
- `azure/gpt-5.2`
- `azure_ai/claude-opus-4-6-2`

The suite runner is already built to add more models. The next step is to benchmark additional providers and compare:
- full-rubric pass rate
- outcome-only accuracy
- process fidelity
- variance across repeated runs

### 5. Move From Benchmark Snapshot To Benchmark Paper

The current README is the working benchmark artifact. The next publication-grade outputs should be:
- a larger task suite
- stable suite configs
- model comparison CSVs across multiple workstreams
- methodology notes on scoring, variance, and failure taxonomy

That will support a stronger external release and eventual paper.

## How To Run

### 1. Set Up The Environment

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp loab/.env.example loab/.env
```

Fill in `loab/.env` with your provider details.

### 2. Configure Providers

#### Azure OpenAI (GPT)

```env
AZURE_API_KEY=...
AZURE_API_BASE=https://<resource>.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
```

Use model ids like:
- `azure/gpt-5.2`

#### Azure Anthropic / Claude via LiteLLM

```env
AZURE_ANTHROPIC_API_BASE=https://<resource>.openai.azure.com/anthropic
```

Use model ids like:
- `azure_ai/claude-opus-4-6-2`

Provider wiring is controlled by:
- `loab/benchmark/run_config.json`
- `provider_settings`

So `scripts/run_task.py` does not need provider-specific hardcoded branches.

### 3. Run A Single Task

```bash
./.venv/bin/python scripts/run_task.py \
  --task origination/task-01 \
  --run_id run-origination-task01-demo
```

Use a dedicated run config if needed:

```bash
./.venv/bin/python scripts/run_task.py \
  --task origination/task-01 \
  --run_id run-origination-task01-gpt \
  --run-config loab/benchmark/run_configs/gpt_5_2_all.json
```

The runner writes:
- `agent_transcript.json`
- `handoffs.json`
- `orchestrator.json`
- `score.json`

under:
- `loab/results/<run_id>/<task-id>/`

### 4. Run Repeated Simulations For One Task

```bash
./.venv/bin/python -u scripts/run_repeats.py \
  --task origination/task-01 \
  --n 4 \
  --run-config loab/benchmark/run_configs/gpt_5_2_all.json \
  --load-env \
  --python-bin ./.venv/bin/python
```

This writes a task-level batch summary JSON under:
- `loab/results/<batch-id>-summary.json`

### 5. Run The Full 3-Task Origination Suite

#### GPT-only

```bash
./.venv/bin/python -u scripts/run_repeats.py \
  --config loab/benchmark/suites/origination_poc_3x4_gpt.json \
  --load-env \
  --python-bin ./.venv/bin/python
```

#### Claude-only

```bash
./.venv/bin/python -u scripts/run_repeats.py \
  --config loab/benchmark/suites/origination_poc_3x4_claude.json \
  --load-env \
  --python-bin ./.venv/bin/python
```

#### Mixed suite config (multiple model runs in one config)

```bash
./.venv/bin/python -u scripts/run_repeats.py \
  --config loab/benchmark/suites/origination_poc_3x4.json \
  --load-env \
  --python-bin ./.venv/bin/python
```

Suite summaries are written to:
- `loab/results/<suite-id>-suite-summary.json`

### 6. Export A Comparison CSV

```bash
./.venv/bin/python scripts/export_benchmark_comparison.py \
  --suite-summary \
  loab/results/suite-origination-poc-3x4-gpt-20260302-115121-suite-summary.json \
  loab/results/suite-origination-poc-3x4-claude-20260302-115522-suite-summary.json
```

This writes a CSV like:
- `loab/results/benchmark-comparison-<timestamp>.csv`

That CSV is the current outreach artifact for side-by-side model comparison.

## What The CSV Contains

Each row is one:
- `model × task`

Columns include:
- model label
- task id
- pass count
- pass rate
- dominant decision
- decision distribution
- stop-reason distribution
- component pass rates (`tool_calls`, `handoffs`, `step_decisions`, `outcome`, `forbidden_actions`, `evidence`)
- top failure signals

This makes it easy to compare:
- final answer quality
- process fidelity
- failure mode shape

## Repository Structure

```text
loab/
├── .env.example              <- provider configuration template
├── agents/                   <- role prompts and decision contracts
├── benchmark/                <- run config, suite configs, run-config variants
├── company/                  <- Meridian policy and mock APIs
├── customers/                <- stable synthetic applicant profiles
├── results/                  <- run outputs (gitignored)
└── tasks/                    <- taxonomy-organized tasks (`task.md`, `pendingfiles.json`, `rubric.json`)
```

Important paths:
- `loab/tasks/origination/task-01`
- `loab/tasks/origination/task-02`
- `loab/tasks/origination/task-03`
- `loab/benchmark/run_configs/`
- `loab/benchmark/suites/`
- `scripts/run_task.py`
- `scripts/run_repeats.py`
- `scripts/export_benchmark_comparison.py`

## Current Limitations

- The current public artifact covers `3` origination tasks, not the full loan lifecycle suite.
- Customer simulation prompts exist, but the runner is still application/profile-driven rather than live customer-simulated.
- The benchmark is intentionally strict: a correct final decision can still fail if process quality is wrong.
- Task results are sensitive to policy specificity. When policy is underspecified, models may diverge for different reasons.

## Why This Is Useful

LOAB is intended to answer the practical question lenders actually care about:
- not just "Can an LLM produce the right answer?"
- but "Can it follow a controlled lending process, use the right tools, and respect hard policy constraints?"

The current three-task origination suite already shows:
- different models can produce different risk behavior on the same file
- outcome accuracy and process fidelity diverge materially
- repeated-run variance is a real deployment concern

That is already enough to make the benchmark useful as an early evaluation artifact before a full paper.

See `CLAUDE.md` for detailed implementation notes and repository conventions.
