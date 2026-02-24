import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from data_loader import MockApiData

LOAB_ROOT = Path(__file__).parent.parent.parent.parent   # loab/
ROOT = LOAB_ROOT / "company" / "mock_apis"
RESULTS_DIR = LOAB_ROOT / "results"

DATA = MockApiData(ROOT)


def _respond(req_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _tool_response(req_id, data):
    """Wrap tool result in MCP-compliant content envelope."""
    _respond(req_id, {
        "content": [{"type": "text", "text": json.dumps(data)}],
        "isError": False,
    })


def _log_event(tool_name, args, result):
    """Append write-tool events to results/<run-id>/events.jsonl if LOAB_RUN_ID is set."""
    run_id = os.environ.get("LOAB_RUN_ID")
    if not run_id:
        return
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "args": args,
        "result": result,
    }
    with open(run_dir / "events.jsonl", "a") as f:
        f.write(json.dumps(event) + "\n")


def _tool_list():
    tools = [
        {"name": "greenid_verify", "description": "Identity DVS result", "inputSchema": {"type": "object", "properties": {"applicant_id": {"type": "string"}}}},
        {"name": "austrac_check", "description": "Watchlist + PEP/sanctions result", "inputSchema": {"type": "object", "properties": {"applicant_id": {"type": "string"}}}},
        {"name": "equifax_pull", "description": "Credit report + score", "inputSchema": {"type": "object", "properties": {"applicant_id": {"type": "string"}}}},
        {"name": "asic_lookup", "description": "Company registration + director details", "inputSchema": {"type": "object", "properties": {"abn": {"type": "string"}}}},
        {"name": "corelogic_valuation", "description": "AVM estimate + confidence", "inputSchema": {"type": "object", "properties": {"property_address": {"type": "string"}}}},
        {"name": "ato_income_verify", "description": "ATO income confirmation", "inputSchema": {"type": "object", "properties": {"tfn_masked": {"type": "string"}, "income_claimed": {"type": "number"}}}},
        {"name": "electoral_roll_check", "description": "Address verification", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "address": {"type": "string"}}}},
        {"name": "submit_sar", "description": "Lodge Suspicious Activity Report", "inputSchema": {"type": "object", "properties": {"applicant_id": {"type": "string"}, "report": {"type": "object"}}}},
        {"name": "account_status", "description": "Loan status + arrears", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "applicant_id": {"type": "string"}}}},
        {"name": "hardship_queue_check", "description": "Pending hardship application", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "applicant_id": {"type": "string"}}}},
        {"name": "issue_notice", "description": "Send arrears/demand notice", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "notice_type": {"type": "string"}}}},
        {"name": "payment_arrangement", "description": "Record repayment arrangement", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "amount": {"type": "number"}, "frequency": {"type": "string"}, "duration": {"type": "string"}}}},
        {"name": "hardship_application", "description": "Hardship application details", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "applicant_id": {"type": "string"}}}},
        {"name": "arrange_hardship", "description": "Record hardship arrangement", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "arrangement_type": {"type": "string"}, "duration_months": {"type": "number"}}}},
        {"name": "policy_lookup", "description": "Credit policy reference", "inputSchema": {"type": "object", "properties": {"section": {"type": "string"}}}},
        {"name": "regulatory_reference", "description": "Regulatory reference", "inputSchema": {"type": "object", "properties": {"act": {"type": "string"}, "section": {"type": "string"}}}},
        {"name": "breach_register", "description": "Log breach finding", "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}, "agent": {"type": "string"}, "breach_type": {"type": "string"}, "severity": {"type": "string"}}}},
        {"name": "policy_exception_register", "description": "Log policy exception", "inputSchema": {"type": "object", "properties": {"loan_id": {"type": "string"}, "exception_type": {"type": "string"}, "justification": {"type": "string"}}}},
    ]
    return {"tools": tools}


def _resolve_applicant(args):
    return DATA.resolve_applicant_id(args.get("applicant_id"), args.get("task_id"))


def _call_tool(name, args):
    args = args or {}

    if name == "greenid_verify":
        applicant_id = _resolve_applicant(args)
        return DATA.get_response("greenid", applicant_id, "dvs_result")

    if name == "austrac_check":
        applicant_id = _resolve_applicant(args)
        return DATA.get_response("austrac", applicant_id, "watchlist")

    if name == "equifax_pull":
        applicant_id = _resolve_applicant(args)
        return DATA.get_response("equifax", applicant_id, "credit_report")

    if name == "asic_lookup":
        applicant_id = _resolve_applicant(args)
        abn = args.get("abn")
        return DATA.get_response("asic", applicant_id, "abn_lookup", abn)

    if name == "corelogic_valuation":
        applicant_id = _resolve_applicant(args)
        address = args.get("property_address")
        return DATA.get_response("corelogic", applicant_id, "property_valuation", address)

    if name == "ato_income_verify":
        applicant_id = _resolve_applicant(args)
        tfn = args.get("tfn_masked")
        return DATA.get_response("ato", applicant_id, "income_verify", tfn)

    if name == "electoral_roll_check":
        applicant_id = _resolve_applicant(args)
        name_key = args.get("name") or ""
        address_key = args.get("address") or ""
        key = f"{name_key}::{address_key}"
        return DATA.get_response("greenid", applicant_id, "electoral_roll", key)

    if name == "submit_sar":
        result = {"ok": True, "data": {"status": "SUBMITTED", "applicant_id": args.get("applicant_id")}}
        _log_event("submit_sar", args, result)
        return result

    if name == "account_status":
        applicant_id = _resolve_applicant(args)
        loan_id = args.get("loan_id")
        internal = DATA.get_internal_loan(applicant_id, loan_id)
        if not internal.get("ok"):
            return internal
        return {"ok": True, "data": internal["data"].get("account_status")}

    if name == "hardship_queue_check":
        applicant_id = _resolve_applicant(args)
        loan_id = args.get("loan_id")
        internal = DATA.get_internal_loan(applicant_id, loan_id)
        if not internal.get("ok"):
            return internal
        hq = internal["data"].get("hardship_queue")
        if hq is None:
            return {"ok": True, "data": {"hardship_application_found": False}}
        return {"ok": True, "data": hq}

    if name == "issue_notice":
        result = {"ok": True, "data": {"status": "ISSUED", "loan_id": args.get("loan_id"), "notice_type": args.get("notice_type")}}
        _log_event("issue_notice", args, result)
        return result

    if name == "payment_arrangement":
        result = {"ok": True, "data": {"status": "RECORDED", **args}}
        _log_event("payment_arrangement", args, result)
        return result

    if name == "hardship_application":
        applicant_id = _resolve_applicant(args)
        loan_id = args.get("loan_id")
        internal = DATA.get_internal_loan(applicant_id, loan_id)
        if not internal.get("ok"):
            return internal
        return {"ok": True, "data": internal["data"].get("hardship_application")}

    if name == "arrange_hardship":
        result = {"ok": True, "data": {"status": "RECORDED", **args}}
        _log_event("arrange_hardship", args, result)
        return result

    if name == "policy_lookup":
        return DATA.get_internal_policy(args.get("section"))

    if name == "regulatory_reference":
        act = args.get("act") or ""
        section = args.get("section") or ""
        key = f"{act} {section}".strip()
        return DATA.get_internal_regulatory(key)

    if name == "breach_register":
        result = {"ok": True, "data": {"status": "LOGGED", **args}}
        _log_event("breach_register", args, result)
        return result

    if name == "policy_exception_register":
        result = {"ok": True, "data": {"status": "LOGGED", **args}}
        _log_event("policy_exception_register", args, result)
        return result

    return {"ok": False, "error": f"Unknown tool {name}"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method")
        req_id = req.get("id")

        # Notifications have no id — skip silently
        if req_id is None:
            continue

        if method == "initialize":
            _respond(req_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "loab-mock-apis", "version": "1.0"},
                "capabilities": {"tools": {}}
            })
        elif method == "tools/list":
            _respond(req_id, _tool_list())
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            result = _call_tool(name, args)
            _tool_response(req_id, result)
        else:
            _respond(req_id, error={"code": -32601, "message": f"Method not found: {method}"})


if __name__ == "__main__":
    main()
