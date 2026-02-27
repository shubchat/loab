#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import litellm

ROOT = Path(__file__).parent.parent
NON_PENALIZED_EXTRA_TOOLS = {"policy_lookup"}


def build_global_system_preamble(agent):
    return f"""You are acting as a Meridian Bank staff member in a multi-agent lending operations benchmark.

Current role: {agent}

Core rules:
- Follow Meridian Bank policy and regulatory obligations as the source of truth.
- The task text describes the scenario only; derive required actions from your role, policy, applicant/account data, and prior handoffs.
- Use tools to verify facts instead of assuming.
- Use exact tool argument formats and correct/retry soft formatting errors when appropriate.
- Stay within your role authority and make the correct handoff when required.
- Return a step decision (`decision_json`) every step.
- The `decision_json.decision` value must be one of the valid decisions defined in your role prompt (do not invent placeholder workflow decisions).
- If your decision requires escalation/handoff, include a structured `handoff_json`; the orchestrator will move the file to the next agent/step using that decision/handoff.
- If your role can conclude the assigned step, return the final step decision for your role in this step (do not stop at a research-only status).
- Handoff naming convention: use snake_case keys. For direct tool outputs, use `<tool_name>_result`. Agent-computed summaries should use clear names like `<topic>_summary`.
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


def format_user_prompt(task_md, objective, applicant_profile, prior_handoffs):
    prompt = []
    prompt.append(f"Current Step Objective: {objective}\n")
    prompt.append("Task Situation:\n" + task_md.strip() + "\n")
    prompt.append("Applicant Profile (JSON):\n" + json.dumps(applicant_profile, indent=2) + "\n")
    if prior_handoffs:
        prompt.append("Prior Handoff Payloads (JSON):\n" + json.dumps(prior_handoffs, indent=2) + "\n")
    else:
        prompt.append("Prior Handoff Payloads (JSON):\n[]\n")

    prompt.append(
        "Provide step decision JSON in a fenced code block labeled decision_json with keys: decision, rationale. "
        "The `decision` must be one of the valid decisions in your role prompt. "
        "If the decision is APPROVE or CONDITIONAL_APPROVE, also include numeric fields `final_interest_rate` "
        "(approved product/customer rate) and `assessment_interest_rate` (serviceability assessment/stress rate used)."
    )
    prompt.append(
        "If your decision requires a handoff/escalation, include a fenced code block labeled handoff_json "
        "with a structured summary of all materially relevant findings, evidence, and calculations for the next agent."
    )
    prompt.append(
        "If your decision does not require a handoff, complete this step with a valid role decision and do not emit placeholder progression decisions."
    )

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


def load_agent_prompt_and_contract(agent):
    prompt_path = ROOT / "loab/agents" / agent / "prompt.md"
    if not prompt_path.exists():
        raise SystemExit(f"Missing prompt for agent {agent}: {prompt_path}")
    agent_prompt = prompt_path.read_text()
    contract = parse_json_block(agent_prompt, "decision_contract")
    if not isinstance(contract, dict) or not isinstance(contract.get("valid_decisions"), dict):
        raise SystemExit(f"Agent prompt missing valid decision_contract block: {prompt_path}")
    return agent_prompt, contract


def extract_allowed_tool_names(agent_prompt):
    """Parse the '## Tools available' section from the agent prompt."""
    m = re.search(r"^## Tools available\s*$([\s\S]*?)(?=^##\s+|\Z)", agent_prompt, re.MULTILINE)
    if not m:
        return set()
    section = m.group(1)
    names = set()
    for tool_sig in re.findall(r"`([^`]+)`", section):
        name = tool_sig.split("(", 1)[0].strip()
        if name:
            names.add(name)
    return names


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


def _decision_rule_for(contract, decision):
    if not isinstance(contract, dict):
        return None
    rules = contract.get("valid_decisions", {})
    if not isinstance(rules, dict):
        return None
    rule = rules.get(decision)
    if not isinstance(rule, dict):
        return None
    out = dict(rule)
    out.setdefault("terminal", False)
    out.setdefault("handoff_required", False)
    out.setdefault("next_agent", None)
    if "advance_workflow" not in out:
        out["advance_workflow"] = (not out["terminal"]) and bool(out.get("next_agent"))
    return out


def _tool_call_matches(expected_call, observed_call):
    if observed_call.get("name") != expected_call.get("tool"):
        return False
    return _match_expected(expected_call.get("arguments", {}), observed_call.get("arguments", {}))


def _step_transcript(step_num, transcript):
    return [s for s in transcript if s.get("step") == step_num]


def _handoff_key_aliases(key):
    """Accept both legacy topic names and generic <tool_name>_result names."""
    aliases = {key}
    alias_map = {
        "greenid_result": "greenid_verify_result",
        "equifax_result": "equifax_pull_result",
        "ato_result": "ato_income_verify_result",
        "asic_result": "asic_lookup_result",
        "corelogic_result": "corelogic_valuation_result",
    }
    reverse = {v: k for k, v in alias_map.items()}
    if key in alias_map:
        aliases.add(alias_map[key])
    if key in reverse:
        aliases.add(reverse[key])
    return aliases


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
            if obs.get("name") in NON_PENALIZED_EXTRA_TOOLS:
                continue
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
            if not any(alias in payload for alias in _handoff_key_aliases(k)):
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
    expected_outcome_fields = rubric.get("expected_outcome_fields", {})
    final_decision_json = None
    observed_decision = None
    if transcript:
        final_step_num = transcript[-1].get("step")
        final_step_entries = _step_transcript(final_step_num, transcript)
        if final_step_entries:
            final_decision_json = final_step_entries[-1].get("decision_json") or {}
            observed_decision = final_decision_json.get("decision")
    outcome_pass = _match_expected(expected_outcome.get("decision"), observed_decision)
    outcome_fields_pass = True
    outcome_fields_missing = []
    if expected_outcome_fields:
        if not isinstance(final_decision_json, dict):
            outcome_fields_pass = False
            outcome_fields_missing.append({"expected": expected_outcome_fields, "observed": None})
        else:
            for k, v in expected_outcome_fields.items():
                if k not in final_decision_json or not _match_expected(v, final_decision_json.get(k)):
                    outcome_fields_pass = False
                    outcome_fields_missing.append({
                        "field": k,
                        "expected": v,
                        "observed": final_decision_json.get(k),
                    })

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
        and outcome_fields_pass
        and not missing_evidence
        and forbidden_pass
    )
    return {
        "task_id": rubric.get("task_id"),
        "passed": passed,
        "tool_calls": {"passed": not missing, "missing": missing, "extra": extra},
        "handoffs": {"passed": not missing_keys, "missing_keys": missing_keys},
        "step_decisions": {"passed": step_decisions_pass, "missing_or_mismatched": missing_step_decisions},
        "outcome": {
            "passed": outcome_pass and outcome_fields_pass,
            "decision_passed": outcome_pass,
            "expected": expected_outcome.get("decision"),
            "observed": observed_decision,
            "expected_fields": expected_outcome_fields,
            "field_mismatches": outcome_fields_missing,
        },
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
    documents_submitted = pending.get("documents_submitted")
    application_documents = pending.get("application_documents")
    if documents_submitted is not None:
        applicant_profile["documents_submitted"] = documents_submitted
    elif isinstance(application_documents, dict):
        applicant_profile["documents_submitted"] = [k for k, v in application_documents.items() if isinstance(v, dict) and v.get("provided") is True]
    if application_documents is not None:
        applicant_profile["application_documents"] = application_documents

    starting_agent = pending.get("starting_agent")
    if not starting_agent:
        raise SystemExit("pendingfiles.json missing starting_agent")
    max_workflow_steps = int(pending.get("max_steps", 8))

    results_dir = ROOT / "loab/results" / args.run_id / args.task
    results_dir.mkdir(parents=True, exist_ok=True)

    mcp = MCPClient()
    mcp.start()
    all_mcp_tools = mcp.tools_list()
    all_tools = mcp_tools_to_openai(all_mcp_tools)

    transcript = []
    handoffs = []
    prior_handoffs = []

    try:
        current_agent = starting_agent
        step_num = 1
        workflow_stop_reason = None
        while current_agent and step_num <= max_workflow_steps:
            agent = current_agent
            objective = f"Execute step {step_num} as {agent}. Make a valid role decision and hand off only if the decision requires it."

            agent_prompt, decision_contract = load_agent_prompt_and_contract(agent)
            allowed_tool_names = extract_allowed_tool_names(agent_prompt)
            if not allowed_tool_names:
                raise SystemExit(f"No tools parsed from agent prompt for {agent}; cannot enforce tool allowlist")
            agent_tools = [t for t in all_tools if t.get("function", {}).get("name") in allowed_tool_names]
            missing_tool_defs = sorted(
                n for n in allowed_tool_names if n not in {t.get('function', {}).get('name') for t in all_tools}
            )
            if missing_tool_defs:
                raise SystemExit(f"Agent {agent} prompt lists unknown tools not provided by MCP: {missing_tool_defs}")
            system_prompt = build_global_system_preamble(agent) + "\n\n" + agent_prompt
            user_prompt = format_user_prompt(
                task_md,
                objective,
                applicant_profile,
                prior_handoffs,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            tool_calls_log = []
            max_iters = 6
            assistant_response = ""
            loop_exhausted = True
            for _ in range(max_iters):
                model = model_assignments.get(agent)
                if not model:
                    raise SystemExit(f"Missing model assignment for {agent}")
                if model.startswith("azure/"):
                    resp = litellm.completion(
                        model=model,
                        messages=messages,
                        tools=agent_tools,
                        tool_choice="auto",
                        api_key=os.getenv("AZURE_API_KEY"),
                        api_base=os.getenv("AZURE_API_BASE"),
                        api_version=os.getenv("AZURE_API_VERSION"),
                    )
                else:
                    resp = litellm.completion(model=model, messages=messages, tools=agent_tools, tool_choice="auto")

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
                    loop_exhausted = False
                    break

            if loop_exhausted and not assistant_response:
                assistant_response = (
                    "Tool-call loop exhausted before final response. "
                    "Return a decision_json and, if handing off, a handoff_json after completing required tool calls."
                )

            handoff_payload = parse_json_block(assistant_response, "handoff_json")
            decision_json = parse_json_block(assistant_response, "decision_json")
            decision_value = (decision_json or {}).get("decision")
            decision_rule = _decision_rule_for(decision_contract, decision_value) if decision_value else None

            protocol_error = None
            if not isinstance(decision_json, dict):
                protocol_error = "missing_or_invalid_decision_json"
            elif decision_rule is None:
                protocol_error = f"invalid_decision_for_agent:{decision_value}"
            elif decision_rule.get("handoff_required") and not isinstance(handoff_payload, dict):
                protocol_error = f"handoff_required_but_missing:{decision_value}"

            transcript.append({
                "step": step_num,
                "agent": agent,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "allowed_tools": sorted(allowed_tool_names),
                "tool_calls": tool_calls_log,
                "tool_loop_exhausted": loop_exhausted,
                "assistant_response": assistant_response,
                "handoff_payload": handoff_payload,
                "decision_json": decision_json,
                "decision_contract_rule": decision_rule,
                "protocol_error": protocol_error,
            })

            next_agent = decision_rule.get("next_agent") if decision_rule else None
            if isinstance(handoff_payload, dict):
                handoff_entry = {
                    "step": step_num,
                    "from_agent": agent,
                    "to_agent": next_agent,
                    "payload": handoff_payload,
                }
                handoffs.append(handoff_entry)
                prior_handoffs.append(handoff_entry)

            if protocol_error:
                workflow_stop_reason = protocol_error
                break

            if decision_rule.get("terminal"):
                workflow_stop_reason = f"terminal_decision:{decision_value}"
                if decision_rule.get("advance_workflow"):
                    current_agent = next_agent
                    step_num += 1
                    continue
                break

            if not decision_rule.get("advance_workflow"):
                workflow_stop_reason = f"non_terminal_no_advance:{decision_value}"
                break
            if not next_agent:
                workflow_stop_reason = f"missing_next_agent:{decision_value}"
                break

            current_agent = next_agent
            step_num += 1

        if step_num > max_workflow_steps and current_agent:
            workflow_stop_reason = f"max_steps_exceeded:{max_workflow_steps}"

        (results_dir / "agent_transcript.json").write_text(json.dumps(transcript, indent=2) + "\n")
        (results_dir / "handoffs.json").write_text(json.dumps(handoffs, indent=2) + "\n")
        (results_dir / "orchestrator.json").write_text(
            json.dumps(
                {
                    "starting_agent": starting_agent,
                    "max_steps": max_workflow_steps,
                    "steps_executed": len(transcript),
                    "stop_reason": workflow_stop_reason,
                },
                indent=2,
            )
            + "\n"
        )

        score = score_run(rubric, transcript, handoffs)
        (results_dir / "score.json").write_text(json.dumps(score, indent=2) + "\n")

    finally:
        mcp.stop()


if __name__ == "__main__":
    main()
