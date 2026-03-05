# Changelog

All notable changes to LOAB are documented in this file.

## v0.1.0 - 2026-03-02

Initial public benchmark artifact release.

### Added
- Taxonomy-based task structure under `loab/tasks/<workstream>/task-0N`.
- Dynamic multi-agent orchestration driven by agent `decision_contract` (not rubric step order).
- Per-agent MCP tool allowlist enforcement from agent prompt tool lists.
- Task-level application document context in `pendingfiles.json` via:
  - `documents_submitted`
  - `application_documents`
- Suite-capable benchmark runner:
  - `scripts/run_repeats.py --config <suite.json>`
- Model/provider decoupling via run configs:
  - `loab/benchmark/run_configs/gpt_5_2_all.json`
  - `loab/benchmark/run_configs/claude_opus_4_6_all.json`
- Origination PoC suite configs:
  - `loab/benchmark/suites/origination_poc_3x4*.json`
- Comparison CSV exporter:
  - `scripts/export_benchmark_comparison.py`
- Per-task run-variance chart generator:
  - `scripts/generate_variance_charts.py`
  - outputs in `assets/variance-origination-task-0N.svg`
- MIT license and README citation section.

### Changed
- `scripts/run_task.py` now supports `--run-config`.
- `scripts/run_task.py` auto-loads `loab/.env` then `./.env`.
- Live run instrumentation added in `scripts/run_task.py` with partial artifacts:
  - `progress.json`
  - `agent_transcript.partial.json`
  - `handoffs.partial.json`
- Policy sync workflow aligned to markdown source of truth.
- Task-02 scoring/evidence matching corrected for Unicode-safe substring checks.

### Current Benchmark Snapshot (v0.1.0)
- Scope: `origination/task-01` .. `origination/task-03`
- Simulations: `4` per task
- Compared models:
  - `azure/gpt-5.2`
  - `azure_ai/claude-opus-4-6-2`
- Artifact CSV (latest): `loab/results/benchmark-comparison-20260302-151052.csv`
