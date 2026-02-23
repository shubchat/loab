# LOAB — Lending Operations Agent Benchmark

Evaluates AI agents across the full Australian mortgage lifecycle: origination, credit decisioning, loan servicing, collections, and compliance.

Agents play bank roles (processing officer, underwriter, fraud analyst, etc.) and hand off to each other based on policy rules. A synthetic customer persona is simultaneously active in conversation. Any LLM can be assigned to any role via `.env` or `benchmark/run_config.json`.

## Quick start

```bash
cp .env.example .env
# Fill in at least one provider API key and set DEFAULT_*_MODEL values
```

## Structure

```
loab/
├── .env.example              ← provider keys + default model assignments
├── company/                  ← Meridian Bank artefacts + mock APIs
├── customers/                ← synthetic applicant profiles + simulation prompts
├── agents/                   ← bank role definitions (prompt.md per role)
├── tasks/                    ← task definitions, rubrics, agent handoff sequences
├── results/                  ← run outputs (gitignored)
└── benchmark/                ← run_config.json, scoring rubric, leaderboard
```

See `CLAUDE.md` at the repo root for full architecture detail.
