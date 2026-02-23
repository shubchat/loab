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
├── README.md                 ← project overview + quick start (loab root)
└── benchmark/
    ├── run_config.json       ← which models, which tasks, scoring setup for a run
    ├── scoring_rubric.md
    └── leaderboard.json
```

## Environment setup

```bash
cp loab/.env.example loab/.env
# Fill in at least one provider key and set DEFAULT_*_MODEL values
```

`.env` supports all major providers: Anthropic, OpenAI, Google Gemini, Mistral, Cohere, AWS Bedrock, Azure OpenAI, xAI. Each agent role has a `DEFAULT_<ROLE>_MODEL` variable (format: `provider/model-id`, e.g. `anthropic/claude-opus-4-6`). These defaults can be overridden per-run in `benchmark/run_config.json`.

`.env` and all customer document subfolders and `results/` are gitignored.

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

### Mock APIs (`company/mock_apis/<provider>/`)
JSON stubs keyed by applicant ID. Agents invoke these as tool calls during a run. Providers: `equifax`, `asic`, `greenid`, `austrac`, `ato`, `corelogic`.

### Benchmark config (`benchmark/run_config.json`)
Defines the run before execution: which AI model plays each agent role, which tasks are included, and the customer simulation model. Edit this before each benchmark run.

### Results (`results/<run-id>/`)
- `agent_transcript.json` logs the full conversation including customer turns and agent-to-agent handoffs.
- `handoffs.json` records the payload passed at each handoff step.
- `score.json` records dimension scores against `rubric.json`.

### Lender: Meridian Bank
All policy, rate, and product references use fictional **Meridian Bank**. Credit policy: `company/policy/meridian_bank_credit_policy.pdf`.

## Adding new content

- **New applicant**: add `AP-00N-<surname>/` under `customers/`, populate `profile.json`, `backstory.md`, `simulation_prompt.md`, and relevant document subfolders.
- **New agent role**: add `agents/<role>/prompt.md` defining responsibilities, tools, authority limits, and escalation rules.
- **New task**: create `tasks/task-0N-<domain>/` with `task.md`, `rubric.json`, and `agents.json`. Mirror under `results/` per run.
- **New mock API response**: add `.json` stub under `company/mock_apis/<provider>/` named by applicant ID or query type.
