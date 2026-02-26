#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import litellm

ROOT = Path(__file__).parent.parent


def build_global_system_preamble(agent):
    return f"""You are acting as a Meridian Bank staff member in a multi-agent lending operations benchmark.

Current role: {agent}

Core rules:
- Follow Meridian Bank policy and regulatory obligations as the source of truth.
- The task text describes the scenario only; derive required actions from your role, policy, applicant/account data, and prior handoffs.
- Use tools to verify facts instead of assuming.
- Use exact tool argument formats and correct/retry soft formatting errors when appropriate.
- Stay within your role authority and make the correct handoff when required.
- Return a step decision (`decision_json`) every step. If handing off, include a structured `handoff_json` for the next agent.
"""


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


def format_user_prompt(task_md, objective, applicant_profile, prior_handoffs, expects_handoff, final_step):
    prompt = []
    prompt.append(f"Current Step Objective: {objective}\n")
    prompt.append("Task Situation:\n" + task_md.strip() + "\n")
    prompt.append("Applicant Profile (JSON):\n" + json.dumps(applicant_profile, indent=2) + "\n")
    if prior_handoffs:
        prompt.append("Prior Handoff Payloads (JSON):\n" + json.dumps(prior_handoffs, indent=2) + "\n")
    else:
        prompt.append("Prior Handoff Payloads (JSON):\n[]\n")

    prompt.append("Provide step decision JSON in a fenced code block labeled decision_json with keys: decision, rationale.")
    if expects_handoff:
        prompt.append("If you are handing off this step, include a fenced code block labeled handoff_json with a structured summary of all materially relevant findings, evidence, and calculations for the next agent.")
    elif not final_step:
        prompt.append("No handoff is required for this step unless explicitly stated in the task.")

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


def _match_expected(expected, observed):
    """Recursive matcher for rubric values.

    Supports:
    - exact match
    - `{\"one_of\": [...]}` alternatives
    - list-as-one_of (backward-compatible when observed is scalar)
    - dict subset match (ignores `_meta` keys)
    """
    if isinstance(expected, dict):
        if set(expected.keys()) == {"one_of"}:
            return any(_match_expected(opt, observed) for opt in expected.get("one_of", []))
        if not isinstance(observed, dict):
            return False
        for k, v in expected.items():
            if str(k).startswith("_"):
                continue
            if k not in observed:
                return False
            if not _match_expected(v, observed[k]):
                return False
        return True

    if isinstance(expected, list):
        if isinstance(observed, list):
            return expected == observed
        return any(_match_expected(opt, observed) for opt in expected)

    return expected == observed


def _tool_call_matches(expected_call, observed_call):
    if observed_call.get("name") != expected_call.get("tool"):
        return False
    return _match_expected(expected_call.get("arguments", {}), observed_call.get("arguments", {}))


def _step_transcript(step_num, transcript):
    return [s for s in transcript if s.get("step") == step_num]


def _evidence_checks_pass(must_include, text, tool_result_text):
    checks = []
    for k, v in must_include.items():
        if k == "data_contains":
            checks.append(str(v) in tool_result_text or str(v) in text)
        elif v is not None:
            checks.append(str(v) in text or str(v) in tool_result_text)
    return all(checks)


def score_run(rubric, transcript, handoffs):
    expected_calls = rubric.get("expected_tool_calls", [])

    observed_by_step = {}
    for step in transcript:
        observed_by_step.setdefault(step.get("step"), []).extend(step.get("tool_calls", []))

    missing = []
    for exp in expected_calls:
        exp_step = exp.get("step")
        found = False
        for obs in observed_by_step.get(exp_step, []):
            if _tool_call_matches(exp, obs):
                found = True
                break
        if not found:
            missing.append(exp)

    extra = []
    for step_num, obs_calls in observed_by_step.items():
        for obs in obs_calls:
            if not any(e.get("step") == step_num and _tool_call_matches(e, obs) for e in expected_calls):
                extra.append(obs)

    # handoffs
    missing_keys = []
    for req in rubric.get("expected_handoffs", []):
        matched = [h for h in handoffs if h.get("from_agent") == req.get("from_agent") and h.get("to_agent") == req.get("to_agent")]
        if req.get("step") is not None:
            matched = [h for h in matched if h.get("step") == req.get("step")]
        if not matched:
            missing_keys.extend(req.get("required_payload_keys", []))
            continue
        payload = matched[0].get("payload", {})
        for k in req.get("required_payload_keys", []):
            if k not in payload:
                missing_keys.append(k)

    # step decisions (intermediate or explicit per-step decisions)
    missing_step_decisions = []
    for req in rubric.get("expected_step_decisions", []):
        step_num = req.get("step")
        agent = req.get("agent")
        entries = _step_transcript(step_num, transcript) if step_num is not None else transcript
        if agent:
            entries = [e for e in entries if e.get("agent") == agent]
        if not entries:
            missing_step_decisions.append({
                "step": step_num,
                "agent": agent,
                "expected": req.get("decision"),
                "reason": "step_not_found",
            })
            continue
        observed = (entries[0].get("decision_json") or {}).get("decision")
        if not _match_expected(req.get("decision"), observed):
            missing_step_decisions.append({
                "step": step_num,
                "agent": entries[0].get("agent"),
                "expected": req.get("decision"),
                "observed": observed,
            })

    # outcome
    expected_outcome = rubric.get("expected_outcome", {})
    observed_decision = None
    if transcript:
        final_step_num = transcript[-1].get("step")
        final_step_entries = _step_transcript(final_step_num, transcript)
        if final_step_entries:
            observed_decision = (final_step_entries[-1].get("decision_json") or {}).get("decision")
    outcome_pass = _match_expected(expected_outcome.get("decision"), observed_decision)

    # forbidden actions
    forbidden_hits = []
    unsupported_forbidden = []
    for rule in rubric.get("forbidden_actions", []):
        step_num = rule.get("step")
        step_entries = _step_transcript(step_num, transcript) if step_num is not None else transcript
        rtype = rule.get("type")
        if rtype == "tool_call":
            tool = rule.get("tool")
            hit = any(any(tc.get("name") == tool for tc in entry.get("tool_calls", [])) for entry in step_entries)
            if hit:
                forbidden_hits.append(rule)
        elif rtype == "decision":
            disallowed = rule.get("decision")
            hit = False
            for entry in step_entries:
                decision = (entry.get("decision_json") or {}).get("decision")
                if decision is not None and _match_expected(disallowed, decision):
                    hit = True
                    break
            if hit:
                forbidden_hits.append(rule)
        elif rtype == "communication" and rule.get("action") == "credit_decision_to_applicant":
            # Minimal proxy: only treat formal credit decisions as applicant credit decision communication.
            formal_credit_decisions = {"APPROVE", "CONDITIONAL_APPROVE", "DECLINE"}
            hit = any(
                ((entry.get("decision_json") or {}).get("decision") in formal_credit_decisions)
                for entry in step_entries
            )
            if hit:
                forbidden_hits.append(rule)
        else:
            unsupported_forbidden.append(rule)

    # evidence check (step-scoped basic containment)
    missing_evidence = []
    for ev in rubric.get("expected_evidence", []):
        must_include = ev.get("must_include", {})
        ev_step = ev.get("step")
        ev_tool = ev.get("tool")
        found = False
        for step in (_step_transcript(ev_step, transcript) if ev_step is not None else transcript):
            text = step.get("assistant_response", "") + json.dumps(step.get("handoff_payload", {}))
            tool_calls = [tc for tc in step.get("tool_calls", []) if tc.get("name")]

            # If rubric names a tool, evaluate evidence against each matching call result
            # (important when the same tool is called multiple times in one step, e.g. policy_lookup).
            if ev_tool:
                matching_calls = [tc for tc in tool_calls if tc.get("name") == ev_tool]
                for tc in matching_calls:
                    tool_result_text = json.dumps(tc.get("result", {}))
                    if _evidence_checks_pass(must_include, text, tool_result_text):
                        found = True
                        break
                if found:
                    break
                continue

            # Tool-agnostic evidence: search all tool results for the step plus assistant/handoff text.
            tool_result_text = json.dumps([tc.get("result", {}) for tc in tool_calls])
            if _evidence_checks_pass(must_include, text, tool_result_text):
                found = True
                break
        if not found:
            missing_evidence.append(ev)

    forbidden_pass = not forbidden_hits
    step_decisions_pass = not missing_step_decisions
    passed = (
        not missing
        and not missing_keys
        and step_decisions_pass
        and outcome_pass
        and not missing_evidence
        and forbidden_pass
    )
    return {
        "task_id": rubric.get("task_id"),
        "passed": passed,
        "tool_calls": {"passed": not missing, "missing": missing, "extra": extra},
        "handoffs": {"passed": not missing_keys, "missing_keys": missing_keys},
        "step_decisions": {"passed": step_decisions_pass, "missing_or_mismatched": missing_step_decisions},
        "outcome": {"passed": outcome_pass, "expected": expected_outcome.get("decision"), "observed": observed_decision},
        "forbidden_actions": {"passed": forbidden_pass, "hits": forbidden_hits, "unsupported": unsupported_forbidden},
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
    pending = load_json(task_dir / "pendingfiles.json")
    rubric = load_json(task_dir / "rubric.json")
    task_md = (task_dir / "task.md").read_text()

    applicant_id = pending.get("applicants", [None])[0]
    if not applicant_id:
        raise SystemExit("pendingfiles.json missing applicants")
    # find folder by prefix
    cust_dir = next((p for p in (ROOT / "loab/customers").iterdir() if p.name.startswith(applicant_id)), None)
    if not cust_dir:
        raise SystemExit(f"No customer folder for {applicant_id}")
    applicant_profile = load_json(cust_dir / "profile.json")

    steps = rubric.get("steps")
    if not steps:
        steps = [{"step": 1, "agent": pending.get("starting_agent")}]

    results_dir = ROOT / "loab/results" / args.run_id / args.task
    results_dir.mkdir(parents=True, exist_ok=True)

    mcp = MCPClient()
    mcp.start()
    tools = mcp_tools_to_openai(mcp.tools_list())

    transcript = []
    handoffs = []
    prior_handoffs = []

    try:
        for step in steps:
            agent = step["agent"]
            objective = f"Execute step {step['step']} as {agent}."
            # find expected handoff keys for this step
            handoff_keys = []
            for h in rubric.get("expected_handoffs", []):
                if h.get("from_agent") == agent and h.get("step") == step.get("step"):
                    handoff_keys = h.get("required_payload_keys", [])
                    break
            final_step = step.get("step") == steps[-1].get("step")

            agent_prompt = (ROOT / "loab/agents" / agent / "prompt.md").read_text()
            system_prompt = build_global_system_preamble(agent) + "\n\n" + agent_prompt
            user_prompt = format_user_prompt(
                task_md,
                objective,
                applicant_profile,
                prior_handoffs,
                bool(handoff_keys),
                final_step,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            tool_calls_log = []
            max_iters = 6
            assistant_response = ""
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

            handoff_payload = parse_json_block(assistant_response, "handoff_json") if handoff_keys else None
            decision_json = parse_json_block(assistant_response, "decision_json")

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

            if handoff_payload:
                # determine to_agent from rubric expectations
                to_agent = None
                for h in rubric.get("expected_handoffs", []):
                    if h.get("from_agent") == agent and h.get("step") == step.get("step"):
                        to_agent = h.get("to_agent")
                        break
                handoff_entry = {
                    "step": step.get("step"),
                    "from_agent": agent,
                    "to_agent": to_agent,
                    "payload": handoff_payload,
                }
                handoffs.append(handoff_entry)
                prior_handoffs.append(handoff_entry)

        (results_dir / "agent_transcript.json").write_text(json.dumps(transcript, indent=2) + "\n")
        (results_dir / "handoffs.json").write_text(json.dumps(handoffs, indent=2) + "\n")

        score = score_run(rubric, transcript, handoffs)
        (results_dir / "score.json").write_text(json.dumps(score, indent=2) + "\n")

    finally:
        mcp.stop()


if __name__ == "__main__":
    main()
