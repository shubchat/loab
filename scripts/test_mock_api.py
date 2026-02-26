#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys

SERVER_CMD = ["python", "loab/company/mock_apis/server/mcp_server.py"]

def call_tool(tool, arguments):
    payloads = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": arguments}},
    ]
    data = "\n".join(json.dumps(p) for p in payloads) + "\n"
    proc = subprocess.run(SERVER_CMD, input=data, text=True, capture_output=True)
    if proc.returncode != 0:
        print(proc.stderr.strip())
        sys.exit(proc.returncode)
    # print only the tool call response
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) >= 2:
        print(lines[-1])
    elif lines:
        print(lines[0])
    else:
        print("No response")


def main():
    parser = argparse.ArgumentParser(description="Test LOAB mock API tools")
    sub = parser.add_subparsers(dest="tool", required=True)

    p = sub.add_parser("account_status")
    p.add_argument("--loan_id", required=True)
    p.add_argument("--applicant_id", required=True)

    p = sub.add_parser("hardship_queue_check")
    p.add_argument("--loan_id", required=True)
    p.add_argument("--applicant_id", required=True)

    p = sub.add_parser("hardship_application")
    p.add_argument("--loan_id", required=True)
    p.add_argument("--applicant_id", required=True)

    p = sub.add_parser("equifax_pull")
    p.add_argument("--full_name", required=True)
    p.add_argument("--dob", required=True)
    p.add_argument("--residential_address", required=True)

    p = sub.add_parser("greenid_verify")
    p.add_argument("--full_name", required=True)
    p.add_argument("--dob", required=True)
    p.add_argument("--residential_address", required=True)

    p = sub.add_parser("asic_lookup")
    p.add_argument("--abn", required=True)
    p.add_argument("--applicant_id", required=False)

    p = sub.add_parser("corelogic_valuation")
    p.add_argument("--property_address", required=True)
    p.add_argument("--applicant_id", required=False)

    p = sub.add_parser("ato_income_verify")
    p.add_argument("--tfn", required=True)
    p.add_argument("--income_claimed", type=float, required=True)
    p.add_argument("--applicant_id", required=False)

    p = sub.add_parser("submit_sar")
    p.add_argument("--applicant_id", required=True)

    p = sub.add_parser("arrange_hardship")
    p.add_argument("--loan_id", required=True)
    p.add_argument("--arrangement_type", required=True)
    p.add_argument("--duration_months", type=int, required=True)
    p.add_argument("--applicant_id", required=True)

    args = parser.parse_args()
    tool = args.tool
    arguments = {k: v for k, v in vars(args).items() if k not in {"tool"} and v is not None}

    # submit_sar expects a report object; keep simple
    if tool == "submit_sar":
        arguments["report"] = {"summary": "Test SAR"}

    call_tool(tool, arguments)


if __name__ == "__main__":
    main()
