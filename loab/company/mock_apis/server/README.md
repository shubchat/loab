# Mock APIs MCP Server

This server exposes mock APIs as MCP tools over stdio.

## Run

```bash
python loab/company/mock_apis/server/mcp_server.py
```

## Task Context

Set `LOAB_TASK_ID` to resolve applicant context automatically:

```bash
LOAB_TASK_ID=task-01-origination python loab/company/mock_apis/server/mcp_server.py
```

If `applicant_id` is provided in tool arguments, it takes precedence.

## Soft Errors

Missing data returns:

```json
{ "ok": false, "error": "...", "available": ["..."] }
```

## Data Location

All mock responses live under `loab/company/mock_apis/`.
