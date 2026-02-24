# Ground Truth Migration + Evidence Checks

## Summary
Moved decision ground truth from applicant profiles into task rubrics, fixed task-03 applicant context, and added strict evidence-based checks so scoring validates that agents used tool outputs (not just called tools).

## What Changed
- Task rubrics are now the single source of truth for expected tool calls, handoffs, outcomes, and evidence.
- Applicant profiles no longer contain `expected_*` fields.
- `task-03-servicing/context/applicant.json` aligned to AP-005 to match `agents.json`.

## Files Updated
- `loab/tasks/task-01-origination/rubric.json`
- `loab/tasks/task-02-decisioning/rubric.json`
- `loab/tasks/task-03-servicing/rubric.json`
- `loab/tasks/task-04-collections/rubric.json`
- `loab/tasks/task-05-compliance/rubric.json`
- `loab/tasks/task-03-servicing/context/applicant.json`
- `loab/customers/AP-001-mitchell/profile.json`
- `loab/customers/AP-002-ferretti/profile.json`
- `loab/customers/AP-003-chen/profile.json`
- `loab/customers/AP-004-nguyen/profile.json`

## Rubric Schema (Key Sections)
- `expected_tool_calls`: strict tool name + argument matching
- `expected_handoffs`: required payload keys per handoff
- `expected_outcome`: decision + rationale + policy refs
- `forbidden_actions`: actions/tools that must not occur
- `expected_evidence`: evidence that tool results were used

## Evidence Generation
Evidence values are derived from mock API JSONs:
- External providers: `loab/company/mock_apis/<provider>/<applicant>.json`
- Internal tools: `loab/company/mock_apis/internal/<applicant>.json`

Each `expected_evidence` entry includes:
- `tool`: tool name
- `must_include`: fields that must appear in the agent’s handoff or decision rationale (scoring rule)

## Decisions / Conventions
- Ground truth is stored in tasks only (not profiles).
- `agents.json` is the canonical task→applicant mapping.
- Strict matching for tool call arguments.
- Evidence-based validation required for correct tool use.
