# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**LOAB** (Lending Operations Agent Benchmark) evaluates AI agents across the Australian mortgage lifecycle: origination, credit decisioning, servicing, collections, and compliance.

The current benchmark runner (`scripts/run_task.py`) is **multi-agent and decision-driven**:
- orchestration starts from `pendingfiles.json -> starting_agent`
- next step is determined by each agent's `decision_json` plus that agent's machine-readable `decision_contract` in `prompt.md`
- task rubrics are used for scoring, not orchestration flow
- agents call mock APIs via local MCP server with per-agent tool allowlists enforced by the runner
- runtime applicant file is built from customer `profile.json` plus task-level application context from `pendingfiles.json`

Customer simulation prompts exist (`simulation_prompt.md`) but a live customer-simulation orchestration loop is **not** wired into the current runner yet.

## Repository layout

```text
.
├── CLAUDE.md
├── README.md
├── requirements.txt
├── plans/                      ← one markdown file per implementation plan
├── scripts/
│   ├── run_task.py             ← task runner + scorer
│   ├── run_repeats.py          ← repeated-run evaluator (single-task + suite mode)
│   ├── export_benchmark_comparison.py ← suite summary -> comparison CSV
│   └── test_mock_api.py
└── loab/
    ├── .env.example
    ├── agents/                 ← bank role prompts (`prompt.md` per role)
    ├── benchmark/              ← run config + leaderboard + run_configs/ + suites/
    ├── company/
    │   ├── policy/             ← `meridian_bank_credit_policy.md` (source of truth)
    │   ├── rates/
    │   ├── brokers/
    │   ├── lmi_providers/
    │   └── mock_apis/          ← provider data + internal bank tools + MCP server
    ├── customers/
    │   └── AP-00N-name/
    │       ├── profile.json
    │       ├── backstory.md
    │       └── simulation_prompt.md
    ├── tasks/
    │   ├── <taxonomy>/
    │   │   └── task-0N/
    │   │       ├── task.md
    │   │       ├── pendingfiles.json
    │   │       └── rubric.json
    └── results/                ← run outputs (gitignored)
```

## Environment setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp loab/.env.example loab/.env
# Fill in provider keys + model settings
```

`.env` supports multiple providers via LiteLLM (OpenAI, Anthropic, Gemini, Azure OpenAI, MiniMax, etc.). Use `provider/model-id` format in model assignments (for Azure: `azure/<deployment-name>`, for MiniMax: `openai/MiniMax-M2.5`).

`run_task.py` auto-loads `loab/.env` first, then `./.env`. `scripts/run_repeats.py --load-env` does the same.

### Azure OpenAI (LiteLLM)

Set these in `.env`:

```env
AZURE_API_KEY=...
AZURE_API_BASE=https://<resource>.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
```

Example model assignment: `azure/gpt-5.2`

### MiniMax (LiteLLM)

MiniMax provides an OpenAI-compatible API. Set these in `.env`:

```env
MINIMAX_API_KEY=...
MINIMAX_API_BASE=https://api.minimax.io/v1
```

Example model assignment: `openai/MiniMax-M2.5`

Note: MiniMax rejects `temperature=0`. The provided run config uses `temperature=0.01` as a near-deterministic alternative.

## Running the MCP server (manual testing)

```bash
python loab/company/mock_apis/server/mcp_server.py

# Resolve applicant context from task
LOAB_TASK_ID=origination/task-01 python loab/company/mock_apis/server/mcp_server.py

# Enable write-tool audit logging
LOAB_TASK_ID=collections/task-01 LOAB_RUN_ID=run-20250224-001 \
  python loab/company/mock_apis/server/mcp_server.py
```

### MCP env vars

| Variable | Purpose |
|---|---|
| `LOAB_TASK_ID` | Resolve applicant context when `applicant_id` is omitted |
| `LOAB_RUN_ID` | Append write-tool events to `loab/results/<run-id>/events.jsonl` |

Write tools (e.g. `issue_notice`, `arrange_hardship`, `breach_register`, `policy_exception_register`, `submit_sar`) log to `events.jsonl` when `LOAB_RUN_ID` is set.

## Key conventions

### Customer profiles

- Each `loab/customers/AP-00N-name/profile.json` is the stable source of truth for that applicant.
- Customer files are **task-agnostic**.
- Customer profiles do **not** contain `documents_submitted`.
- Expected actions/outcomes/ground truth live in task `rubric.json`, not customer profiles.

### Tasks

Each task folder contains:
- `task.md` — scenario description (`Situation` only; no rubric/checklist leakage)
- `pendingfiles.json` — runtime application context
- `rubric.json` — scoring ground truth

Tasks live under taxonomy folders (for example `loab/tasks/origination/task-01`). Use taxonomy-qualified task ids in the CLI, for example `--task origination/task-01`.

`pendingfiles.json` currently supports:
- `starting_agent`
- `applicants`
- `documents_submitted`
- `application_documents` (nested extracted doc facts)
- optional `max_steps`

At runtime, document fields from `pendingfiles.json` are injected into the applicant file seen by agents.

Benchmark-wide model behavior can also be configured in `loab/benchmark/run_config.json`. If `reasoning_effort` is unset there, the runner uses the provider's default behavior. `LOAB_REASONING_EFFORT` overrides this at runtime.

Provider connectivity is also configured in `loab/benchmark/run_config.json` under `provider_settings`. The runner reads provider-specific env var names from there (for example `azure/...` vs `azure_ai/...`) instead of hardcoding endpoint branches.

Dedicated benchmark variants can be stored in:
- `loab/benchmark/run_configs/*.json` — model-specific run configs
- `loab/benchmark/suites/*.json` — multi-task, multi-model suite definitions
- `loab/benchmark/VERSION` — benchmark semantic version source of truth

Rubrics support:
- step-scoped tool/evidence checks
- forbidden action checks
- alternative acceptable values via `one_of` (e.g. `{"one_of": ["A", "B"]}`)

### Ground truth and scoring

- `rubric.json` is the ground truth for evaluation.
- `rubric.json` does **not** drive orchestration order.
- Policy (`loab/company/policy/meridian_bank_credit_policy.md`) is the business source of truth.
- Agent prompts and rubrics should align to policy (policy wins when they conflict).

### Mock APIs

Provider data lives in `loab/company/mock_apis/<provider>/data.json` and is keyed by realistic query inputs:
- GreenID / Equifax: `full_name` + `dob` + `residential_address`
- ASIC: `abn`
- CoreLogic: `property_address`
- ATO: `tfn`

Internal bank tools/data live under `loab/company/mock_apis/internal/` (policy lookups, regulatory refs, internal loan records, hardship state, etc.).

Notes:
- GreenID includes DVS + watchlist/PEP checks.
- AUSTRAC is treated as reporting (`submit_sar`), not an external lookup provider.
- `loab/company/mock_apis/internal/policy.json` must stay in sync with `loab/company/policy/meridian_bank_credit_policy.md`.

### Plans

Implementation plans are stored in `plans/`, one file per plan (for example `mock_apis.md`, `origination_single_applicant_suite.md`).

### Results

Run outputs are written to `loab/results/<run-id>/`.

Typical files:
- `loab/results/<run-id>/events.jsonl` — MCP write-tool audit trail (run-level)
- `loab/results/<run-id>/<task-id>/agent_transcript.json` — per-step prompts, tool calls/results, responses, extracted handoff/decision JSON
- `loab/results/<run-id>/<task-id>/handoffs.json` — handoff payloads
- `loab/results/<run-id>/<task-id>/orchestrator.json` — dynamic orchestration summary (`starting_agent`, `steps_executed`, `stop_reason`)
- `loab/results/<run-id>/<task-id>/score.json` — scorer output vs rubric
- `loab/results/<batch-id>-summary.json` — repeated-run summary from `scripts/run_repeats.py`
- `loab/results/<suite-id>-suite-summary.json` — multi-task suite summary from `scripts/run_repeats.py --config`
- `loab/results/benchmark-comparison-<timestamp>.csv` — exported comparison artifact from `scripts/export_benchmark_comparison.py`

`scripts/run_task.py` also writes live progress artifacts while a run is executing:
- `progress.json`
- `agent_transcript.partial.json`
- `handoffs.partial.json`

## Orchestration contracts

- Each agent `prompt.md` includes a fenced `decision_contract` JSON block with `valid_decisions`.
- Each decision maps to terminal/handoff behavior and (if non-terminal) exactly one `next_agent`.
- Runner validates agent decisions against this contract.
- Per-agent tool access is enforced by parsing `## Tools available` in prompt files and filtering MCP tools accordingly.

## Current role boundaries (important)

- `processing_officer`: verification + routing only; **no credit decision** and **no formal serviceability calculation**
- `underwriter`: first formal serviceability assessment + credit decision within delegated authority
- `credit_manager`: handles referrals/exceptions within delegated authority, but policy hard limits still apply (for example no exceptions for DTI > 6.0x or Equifax < 580)

## Lender

All policy, rate, and product references use fictional **Meridian Bank**.

## Adding new content

- **New applicant**: add `loab/customers/AP-00N-<surname>/` with `profile.json`, `backstory.md`, `simulation_prompt.md`
- **New task**: add `loab/tasks/<taxonomy>/task-0N/` with `task.md`, `pendingfiles.json`, `rubric.json`; keep numbering sequential within each taxonomy
- **New agent role**: add `loab/agents/<role>/prompt.md`
- **New mock API data**: update `loab/company/mock_apis/<provider>/data.json` using realistic query keys (not applicant IDs)
- **Application document context**: keep document availability/extracted fields in `pendingfiles.json` (`documents_submitted`, `application_documents`), not in customer profile files

## Gitignore notes

Secrets, generated results, and customer document subfolders are gitignored in the repo root `.gitignore`.
