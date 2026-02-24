# LOAB Plans

This file stores implementation plans so they can be reviewed and edited over time.

## Mock APIs + MCP Server

### Summary
Build a deterministic mock API layer under `loab/company/mock_apis` with per-applicant JSON datasets per provider, and a stdlib-only Python MCP server in `loab/company/mock_apis/server/` that exposes tool names matching agent prompts. Task context files map tasks to applicants.

### Data Layout
- `loab/company/mock_apis/<provider>/AP-00N.json`
- `loab/company/mock_apis/internal/AP-00N.json`
- `loab/company/mock_apis/internal/policy.json`
- `loab/company/mock_apis/internal/regulatory.json`

### MCP Server
- `loab/company/mock_apis/server/mcp_server.py`
- `loab/company/mock_apis/server/data_loader.py`
- `loab/company/mock_apis/server/README.md`

**Path resolution:** `ROOT` and `RESULTS_DIR` are derived from `Path(__file__)` — server works from any working directory, no cwd dependency.

**MCP response format:** `tools/call` responses use the compliant envelope:
```json
{"content": [{"type": "text", "text": "<json string>"}], "isError": false}
```

**Notifications** (no `id` field) are skipped silently.

### Task Context
- `loab/tasks/<task>/context/applicant.json` with `{ "applicant_id": "AP-00N" }`
- Applicant resolution order: explicit arg → `LOAB_TASK_ID` env → soft error

### Write-Tool Persistence
Write tools (`submit_sar`, `issue_notice`, `payment_arrangement`, `arrange_hardship`, `breach_register`, `policy_exception_register`) always return success. When `LOAB_RUN_ID` is set, each call is also appended as a timestamped event to `results/<run-id>/events.jsonl`. This is the audit trail for the scorer.

### Tool Names
Match agent prompts exactly:
- `greenid_verify`, `austrac_check`, `equifax_pull`, `asic_lookup`, `corelogic_valuation`, `ato_income_verify`
- `electoral_roll_check`, `submit_sar`
- `account_status`, `hardship_queue_check`, `issue_notice`, `payment_arrangement`
- `hardship_application`, `arrange_hardship`
- `policy_lookup`, `regulatory_reference`
- `breach_register`, `policy_exception_register`

### Soft Errors
Missing data returns:
```json
{ "ok": false, "error": "...", "available": ["..."] }
```

### Known Data Gaps (by design)
- `asic/AP-003.json` — absent intentionally; a good agent should still identify fraud from other signals
- `greenid/AP-003.json` has no `electoral_roll` key — agent must reason from DVS mismatch + other indicators

### AP-005 Internal Data Shape
`account_status` for AP-005 includes `closure_tasks` and `sar_assessment` inline — agents get all closure context from a single `account_status` call. `hardship_queue` returns `{"hardship_application_found": false}` explicitly.
