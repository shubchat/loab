# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**LOAB** (Lending Operations Agent Benchmark) evaluates AI agents across the full Australian mortgage lifecycle — origination, credit decisioning, loan servicing, collections, and compliance. The benchmark supports multi-agent handoffs and customer simulation: a synthetic customer persona is active in conversation, and bank agents must hand off to each other correctly based on policy rules.

## Repository layout

```
loab/
├── company/            ← Meridian Bank artefacts
│   ├── policy/         ← credit policy PDF/DOCX
│   ├── rates/          ← rate sheets
│   ├── lmi_providers/  ← LMI provider details
│   ├── brokers/        ← accredited broker data
│   └── mock_apis/      ← JSON response stubs (equifax, asic, greenid, austrac, ato, corelogic)
│
├── customers/          ← synthetic applicant profiles
│   └── AP-00N-name/
│       ├── profile.json          ← master financial data (mirrors applicant_profiles.json entry)
│       ├── backstory.md          ← narrative: who this person is, their situation
│       ├── simulation_prompt.md  ← instructions for simulating this customer in conversation
│       ├── identity/
│       ├── income/
│       ├── bank_statements/
│       ├── property/             ← (where applicable)
│       └── correspondence/
│
├── agents/             ← bank role definitions (not AI model names)
│   ├── processing_officer/prompt.md
│   ├── underwriter/prompt.md
│   ├── credit_manager/prompt.md
│   ├── collections_officer/prompt.md
│   ├── hardship_assessor/prompt.md
│   ├── fraud_analyst/prompt.md
│   └── compliance_officer/prompt.md
│
├── tasks/
│   └── task-0N-<domain>/
│       ├── task.md               ← what this task tests + success criteria
│       ├── rubric.json           ← scoring dimensions + ground truth
│       ├── agents.json           ← agent sequence, handoff conditions, handoff payloads
│       └── context/              ← files agents are permitted to access during the run
│
├── results/
│   └── <run-id>/                 ← timestamp or experiment label
│       ├── run_config.json       ← models under test, tasks run, date
│       └── <task-id>/
│           ├── agent_transcript.json  ← full multi-agent + customer conversation log
│           ├── handoffs.json          ← what each agent passed to the next
│           └── score.json             ← scored against rubric.json
│
├── plans/                 ← implementation plans (one file per plan)
│
├── README.md                 ← project overview + quick start (loab root)
└── benchmark/
    ├── run_config.json       ← which models, which tasks, scoring setup for a run
    ├── scoring_rubric.md
    └── leaderboard.json
```

## Environment setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp loab/.env.example loab/.env
# Fill in at least one provider key and set DEFAULT_*_MODEL values
```

`.env` supports all major providers: Anthropic, OpenAI, Google Gemini, Mistral, Cohere, AWS Bedrock, Azure OpenAI, xAI. Each agent role has a `DEFAULT_<ROLE>_MODEL` variable (format: `provider/model-id`, e.g. `anthropic/claude-opus-4-6`). These defaults can be overridden per-run in `benchmark/run_config.json`.

`.env` and all customer document subfolders and `results/` are gitignored.

### Azure OpenAI (LiteLLM)

Set the Azure environment variables in `loab/.env`:

```
AZURE_API_KEY=...
AZURE_API_BASE=https://<resource>.openai.azure.com/
AZURE_API_VERSION=2024-12-01-preview
```

Use the Azure deployment name in model assignments, e.g. `azure/gpt-5.2`.

## Running the MCP server

The mock API server is a stdlib-only Python 3 script — no install required.

```bash
# Basic start (paths resolved from __file__, works from any cwd)
python loab/company/mock_apis/server/mcp_server.py

# With task context (server resolves applicant automatically from task)
LOAB_TASK_ID=task-01-origination python loab/company/mock_apis/server/mcp_server.py

# With run tracking (write-tool events appended to results/<run-id>/events.jsonl)
LOAB_TASK_ID=task-04-collections LOAB_RUN_ID=run-20250224-001 \
  python loab/company/mock_apis/server/mcp_server.py
```

**Environment variables:**
| Variable | Purpose |
|----------|---------|
| `LOAB_TASK_ID` | Resolves applicant context when `applicant_id` is not passed in tool args |
| `LOAB_RUN_ID` | If set, write-tool events (`issue_notice`, `arrange_hardship`, `breach_register`, etc.) are appended to `results/<run-id>/events.jsonl` |

**Tool call resolution order for `applicant_id`:** explicit arg → `LOAB_TASK_ID` context file → soft error.

**Write tools** (`submit_sar`, `issue_notice`, `payment_arrangement`, `arrange_hardship`, `breach_register`, `policy_exception_register`) always return success and additionally persist to `events.jsonl` when `LOAB_RUN_ID` is set. The events log is the audit trail for the scorer.

## Key conventions

### Customer profiles
- Each applicant folder `AP-00N-name/` contains the source-of-truth `profile.json` for that applicant.
- `simulation_prompt.md` defines how to play this customer in a live conversation — their personality, what documents they have ready, and how they respond to pressure.
- `backstory.md` provides human-readable narrative context for scenario design.

### Applicant scenarios
| ID | Name | Scenario | Process Step | Final Decision |
|----|------|----------|--------------|----------------|
| AP-001 | Mitchell | PAYG, clean prime — LVR 80%, score 782, DTI 5.1x | Processing Officer assessment | APPROVE |
| AP-002 | Ferretti | Self-employed — score 634, DTI 7.9x, business overdraft ambiguity | Escalate to Credit Manager | DECLINE (DTI > 6x hard cap) |
| AP-003 | Chen | Synthetic identity — DVS mismatch, thin file, unverifiable employer | Financial Crime referral | FRAUD_REVIEW_HALT |
| AP-004 | Nguyen | Active loan 31 DPD — hardship application pending | Suspend collections | HARDSHIP_ASSESS |
| AP-005 | Whitfield | Closed loan — NDC + lien release outstanding; negative SAR test | Process closure tasks | CLOSE_AND_DISCHARGE |

### Agent roles
Agents are bank roles, not AI model names. The AI model under test is configured at run time in `run_config.json`.

| Agent | Authority | Key escalation trigger |
|-------|-----------|----------------------|
| processing_officer | File prep only — no credit decisions | DVS mismatch → fraud_analyst; near-prime or DTI > 6x → credit_manager |
| underwriter | APPROVE up to delegated limits | Score < 650 or DTI > 6x → credit_manager |
| credit_manager | APPROVE / DECLINE up to $5M | Above $5M → Credit Committee |
| collections_officer | Arrears notices + arrangements | Hardship application found → suspend, refer to hardship_assessor |
| hardship_assessor | Hardship arrangements | Decision required within 21 days of application receipt |
| fraud_analyst | Fraud hold + SAR submission | DVS mismatch = hard stop regardless of applicant explanation |
| compliance_officer | Audit only — no operational authority | Breach findings → breach_register |

### Multi-agent handoffs (`agents.json`)
Each task's `agents.json` defines:
- `agent_sequence` — ordered list of agents, each with `objective`, `handoff_to`, `handoff_condition`, and `handoff_payload`
- `customer_simulation` — whether a customer persona is active in the conversation
- `compliance_trap` / `adversarial_note` — flags deliberate failure modes the benchmark is testing

### Mock APIs (`company/mock_apis/<provider>/data.json`)
Provider data lives in `company/mock_apis/<provider>/data.json`, with responses keyed by the API's natural input (e.g., `full_name` + `dob` + `residential_address` for Equifax/GreenID KYC, `abn` for ASIC, `property_address` for CoreLogic, `tfn` for ATO). Internal bank tools are mocked under `company/mock_apis/internal/`. A stdlib-only MCP server lives at `company/mock_apis/server/`.

### Plans
Implementation plans live in `loab/plans/` — one file per plan, named descriptively (e.g., `mock_apis.md`, `ground_truth.md`). Create or update the relevant plan file before starting any non-trivial implementation.

### Ground truth
Task ground truth (expected tool calls, handoffs, outcomes, evidence) lives in each task's `rubric.json`. Applicant profiles are user data only and do not contain expected outcomes.

### Benchmark config (`benchmark/run_config.json`)
Defines the run before execution: which AI model plays each agent role, which tasks are included, and the customer simulation model. Edit this before each benchmark run.

### Results (`results/<run-id>/`)
- `agent_transcript.json` logs the full conversation including customer turns and agent-to-agent handoffs.
- `handoffs.json` records the payload passed at each handoff step.
- `score.json` records dimension scores against `rubric.json`.

### Lender: Meridian Bank
All policy, rate, and product references use fictional **Meridian Bank**. Credit policy: `company/policy/meridian_bank_credit_policy.md`.

## Adding new content

- **New applicant**: add `AP-00N-<surname>/` under `customers/`, populate `profile.json`, `backstory.md`, `simulation_prompt.md`, and relevant document subfolders.
- **New agent role**: add `agents/<role>/prompt.md` defining responsibilities, tools, authority limits, and escalation rules.
- **New task**: create `tasks/task-0N-<domain>/` with `task.md`, `rubric.json`, and `agents.json`. Mirror under `results/` per run.
- **New mock API response**: add `.json` stub under `company/mock_apis/<provider>/` named by applicant ID or query type.
