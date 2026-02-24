#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import litellm

ROOT = Path(__file__).parent.parent


class MCPClient:
    def __init__(self):
        self.proc = None
        self._next_id = 1

    def start(self):
        cmd = ["python", str(ROOT / "loab/company/mock_apis/server/mcp_server.py")]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # initialize
        self._send({"jsonrpc": "2.0", "id": self._next_id, "method": "initialize", "params": {}})
        self._next_id += 1
        _ = self._read_response()

    def stop(self):
        if not self.proc:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None

    def tools_list(self):
        req_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": {}})
        self._next_id += 1
        resp = self._read_response(req_id)
        return resp.get("result", {}).get("tools", [])

    def tool_call(self, name, arguments):
        req_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        self._next_id += 1
        resp = self._read_response(req_id)
        content = resp.get("result", {}).get("content", [])
        if not content:
            return {"ok": False, "error": "Empty tool response"}
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"ok": False, "error": "Invalid tool response", "raw": text}

    def _send(self, payload):
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("MCP server not running")
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def _read_response(self, req_id=None):
        if not self.proc or not self.proc.stdout:
            raise RuntimeError("MCP server not running")
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return {}
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue
            if req_id is None or resp.get("id") == req_id:
                return resp


def mcp_tools_to_openai(tools):
    """Convert MCP tool schema to OpenAI/LiteLLM tool schema."""
    converted = []
    for tool in tools:
        converted.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        })
    return converted


def load_json(path):
    return json.loads(Path(path).read_text())


def format_user_prompt(task_md, objective, applicant_profile, prior_handoffs, handoff_keys, final_step):
    prompt = []
    prompt.append(f"Task Objective: {objective}\n")
    prompt.append("Task Description:\n" + task_md.strip() + "\n")
    prompt.append("Applicant Profile (JSON):\n" + json.dumps(applicant_profile, indent=2) + "\n")
    if prior_handoffs:
        prompt.append("Prior Handoff Payloads (JSON):\n" + json.dumps(prior_handoffs, indent=2) + "\n")

    if handoff_keys:
        prompt.append("You must produce a handoff payload JSON with these keys:")
        prompt.append(", ".join(handoff_keys))
        prompt.append("Return only a JSON object inside a fenced code block labeled handoff_json.")
    if final_step:
        prompt.append("Provide final decision JSON in a fenced code block labeled decision_json with keys: decision, rationale.")

    return "\n".join(prompt)


def parse_json_block(text, label):
    pattern = rf"```{label}\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def score_run(rubric, transcript, handoffs):
    expected_calls = rubric.get("expected_tool_calls", [])
    observed_calls = []
    for step in transcript:
        for call in step.get("tool_calls", []):
            observed_calls.append(call)

    missing = []
    for exp in expected_calls:
        found = False
        for obs in observed_calls:
            if obs.get("name") == exp.get("tool") and obs.get("arguments") == exp.get("arguments"):
                found = True
                break
        if not found:
            missing.append(exp)

    extra = []
    exp_set = {(e.get("tool"), json.dumps(e.get("arguments", {}), sort_keys=True)) for e in expected_calls}
    for obs in observed_calls:
        key = (obs.get("name"), json.dumps(obs.get("arguments", {}), sort_keys=True))
        if key not in exp_set:
            extra.append(obs)

    # handoffs
    missing_keys = []
    for req in rubric.get("expected_handoffs", []):
        matched = [h for h in handoffs if h.get("from_agent") == req.get("from_agent") and h.get("to_agent") == req.get("to_agent")]
        if not matched:
            missing_keys.extend(req.get("required_payload_keys", []))
            continue
        payload = matched[0].get("payload", {})
        for k in req.get("required_payload_keys", []):
            if k not in payload:
                missing_keys.append(k)

    # outcome
    expected_outcome = rubric.get("expected_outcome", {})
    observed_decision = None
    for step in transcript:
        if step.get("decision_json"):
            observed_decision = step.get("decision_json", {}).get("decision")
    outcome_pass = (expected_outcome.get("decision") == observed_decision)

    # evidence check (basic string containment)
    missing_evidence = []
    for ev in rubric.get("expected_evidence", []):
        must_include = ev.get("must_include", {})
        found = False
        for step in transcript:
            text = step.get("assistant_response", "") + json.dumps(step.get("handoff_payload", {}))
            if all(str(v) in text for v in must_include.values() if v is not None):
                found = True
                break
        if not found:
            missing_evidence.append(ev)

    passed = not missing and not missing_keys and outcome_pass and not missing_evidence
    return {
        "task_id": rubric.get("task_id"),
        "passed": passed,
        "tool_calls": {"passed": not missing, "missing": missing, "extra": extra},
        "handoffs": {"passed": not missing_keys, "missing_keys": missing_keys},
        "outcome": {"passed": outcome_pass, "expected": expected_outcome.get("decision"), "observed": observed_decision},
        "evidence": {"passed": not missing_evidence, "missing": missing_evidence},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run_id", required=True)
    args = parser.parse_args()

    run_config = load_json(ROOT / "loab/benchmark/run_config.json")
    model_assignments = run_config.get("model_assignments", {})

    task_dir = ROOT / "loab/tasks" / args.task
    agents = load_json(task_dir / "agents.json")
    rubric = load_json(task_dir / "rubric.json")
    task_md = (task_dir / "task.md").read_text()

    applicant_dir = agents.get("applicant")
    if not applicant_dir:
        raise SystemExit("agents.json missing applicant")
    applicant_profile = load_json(ROOT / "loab/customers" / applicant_dir / "profile.json")

    results_dir = ROOT / "loab/results" / args.run_id / args.task
    results_dir.mkdir(parents=True, exist_ok=True)

    mcp = MCPClient()
    mcp.start()
    tools = mcp_tools_to_openai(mcp.tools_list())

    transcript = []
    handoffs = []
    prior_handoffs = []

    try:
        for step in agents.get("agent_sequence", []):
            agent = step["agent"]
            objective = step["objective"]
            handoff_keys = step.get("handoff_payload", []) if step.get("handoff_to") else []
            final_step = step.get("handoff_to") is None

            system_prompt = (ROOT / "loab/agents" / agent / "prompt.md").read_text()
            user_prompt = format_user_prompt(task_md, objective, applicant_profile, prior_handoffs, handoff_keys, final_step)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # tool-calling loop
            tool_calls_log = []
            max_iters = 6
            for _ in range(max_iters):
                model = model_assignments.get(agent)
                if not model:
                    raise SystemExit(f"Missing model assignment for {agent}")
                if model.startswith("azure/"):
                    resp = litellm.completion(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto",
                        api_key=os.getenv("AZURE_API_KEY"),
                        api_base=os.getenv("AZURE_API_BASE"),
                        api_version=os.getenv("AZURE_API_VERSION"),
                    )
                else:
                    resp = litellm.completion(model=model, messages=messages, tools=tools, tool_choice="auto")
                msg = resp["choices"][0]["message"]

                if msg.get("tool_calls"):
                    messages.append(msg)
                    for tool_call in msg["tool_calls"]:
                        name = tool_call["function"]["name"]
                        arguments = json.loads(tool_call["function"]["arguments"])
                        result = mcp.tool_call(name, arguments)
                        tool_calls_log.append({"name": name, "arguments": arguments, "result": result})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": name,
                            "content": json.dumps(result),
                        })
                    continue
                else:
                    assistant_response = msg.get("content", "")
                    break
            else:
                assistant_response = ""

            handoff_payload = parse_json_block(assistant_response, "handoff_json") if handoff_keys else None
            decision_json = parse_json_block(assistant_response, "decision_json") if final_step else None

            transcript.append({
                "step": step["step"],
                "agent": agent,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "tool_calls": tool_calls_log,
                "assistant_response": assistant_response,
                "handoff_payload": handoff_payload,
                "decision_json": decision_json,
            })

            if handoff_payload and step.get("handoff_to"):
                handoff_entry = {
                    "from_agent": agent,
                    "to_agent": step.get("handoff_to"),
                    "payload": handoff_payload,
                }
                handoffs.append(handoff_entry)
                prior_handoffs.append(handoff_entry)

        # write outputs
        (results_dir / "agent_transcript.json").write_text(json.dumps(transcript, indent=2) + "\n")
        (results_dir / "handoffs.json").write_text(json.dumps(handoffs, indent=2) + "\n")

        score = score_run(rubric, transcript, handoffs)
        (results_dir / "score.json").write_text(json.dumps(score, indent=2) + "\n")

    finally:
        mcp.stop()


if __name__ == "__main__":
    main()
