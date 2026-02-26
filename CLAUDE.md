# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**LOAB** (Lending Operations Agent Benchmark) evaluates AI agents across the Australian mortgage lifecycle: origination, credit decisioning, servicing, collections, and compliance.

The current benchmark runner (`scripts/run_task.py`) is **multi-agent and profile-driven**:
- bank-role agents hand off to each other based on task rubrics and policy
- agents call mock APIs via the local MCP server
- applicant data comes from customer `profile.json`

Customer simulation prompts exist (`simulation_prompt.md`) but a live customer-simulation orchestration loop is **not** wired into the current runner yet.

## Repository layout

```text
.
├── CLAUDE.md
├── README.md
├── requirements.txt
├── scripts/
│   └── run_task.py              ← task runner + scorer
└── loab/
    ├── .env.example
    ├── agents/                  ← bank role prompts (`prompt.md` per role)
    ├── benchmark/               ← run config + leaderboard artifacts
    ├── company/
    │   ├── policy/              ← `meridian_bank_credit_policy.md` (source of truth)
    │   ├── rates/
    │   ├── brokers/
    │   ├── lmi_providers/
    │   └── mock_apis/           ← provider data + internal bank tools + MCP server
    ├── customers/
    │   └── AP-00N-name/
    │       ├── profile.json
    │       ├── backstory.md
    │       └── simulation_prompt.md
    ├── tasks/
    │   └── task-0N-<domain>/
    │       ├── task.md
    │       ├── pendingfiles.json
    │       └── rubric.json
    ├── plans/                   ← one markdown file per implementation plan
    └── results/                 ← run outputs (gitignored)
```

## Environment setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp loab/.env.example loab/.env
# Fill in provider keys + DEFAULT_*_MODEL values
```

`.env` supports multiple providers via LiteLLM (OpenAI, Anthropic, Gemini, Azure OpenAI, etc.). Use `provider/model-id` format in model assignments (for Azure: `azure/<deployment-name>`).

### Azure OpenAI (LiteLLM)

Set these in `loab/.env`:

```env
AZURE_API_KEY=...
AZURE_API_BASE=https://<resource>.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
```

Example model assignment: `azure/gpt-5.2`

## Running the MCP server (manual testing)

The mock API server is a stdlib-only Python script.

```bash
python loab/company/mock_apis/server/mcp_server.py

# Resolve applicant context from task
LOAB_TASK_ID=task-01-origination python loab/company/mock_apis/server/mcp_server.py

# Enable write-tool audit logging
LOAB_TASK_ID=task-04-collections LOAB_RUN_ID=run-20250224-001 \
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

- Each `loab/customers/AP-00N-name/profile.json` is the source of truth for that applicant.
- Customer files are **task-agnostic**.
- Expected actions/outcomes/ground truth live in task `rubric.json`, not in customer profiles.

### Tasks

Each task folder contains:
- `task.md` — scenario description (task intent; agent-agnostic)
- `pendingfiles.json` — starting agent + applicant IDs
- `rubric.json` — step-level ground truth (expected tools, handoffs, outcome, forbidden actions, evidence)

Rubrics support:
- step-scoped tool/evidence checks
- forbidden action checks
- alternative acceptable values with explicit matcher syntax (e.g. `{"one_of": ["A", "B"]}`)

### Ground truth and scoring

- `rubric.json` is the ground truth for evaluation.
- Policy (`loab/company/policy/meridian_bank_credit_policy.md`) is the source of truth for business rules.
- Agent prompts and task rubrics should be aligned to policy (policy wins when they conflict).

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

### Plans

Implementation plans are stored in `loab/plans/`, one file per plan (e.g. `mock_apis.md`, `ground_truth.md`).

### Results

Run outputs are written to `loab/results/<run-id>/`.

Typical files:
- `loab/results/<run-id>/events.jsonl` — MCP write-tool audit trail (run-level)
- `loab/results/<run-id>/<task-id>/agent_transcript.json` — per-step prompts, tool calls/results, responses, extracted handoff/decision JSON
- `loab/results/<run-id>/<task-id>/handoffs.json` — handoff payloads
- `loab/results/<run-id>/<task-id>/score.json` — scorer output vs rubric

## Current role boundaries (important)

- `processing_officer`: verification + routing only; **no credit decision** and **no formal serviceability calculation**
- `underwriter`: first formal serviceability assessment + credit decision within delegated authority
- `credit_manager`: handles referrals/exceptions within delegated authority, but policy hard limits still apply (e.g. no exceptions for DTI > 6.0x or Equifax < 580)

## Lender

All policy, rate, and product references use fictional **Meridian Bank**.

## Adding new content

- **New applicant**: add `loab/customers/AP-00N-<surname>/` with `profile.json`, `backstory.md`, `simulation_prompt.md`
- **New task**: add `loab/tasks/task-0N-<domain>/` with `task.md`, `pendingfiles.json`, `rubric.json`
- **New agent role**: add `loab/agents/<role>/prompt.md`
- **New mock API data**: update `loab/company/mock_apis/<provider>/data.json` using realistic query keys (not applicant IDs); add internal records under `loab/company/mock_apis/internal/` as needed

## Gitignore notes

Secrets, generated results, and customer document subfolders are gitignored in the repo root `.gitignore`.
