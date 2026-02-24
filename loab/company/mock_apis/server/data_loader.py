import json
import os
from pathlib import Path

def _soft_error(message, available=None):
    payload = {"ok": False, "error": message}
    if available is not None:
        payload["available"] = sorted(available)
    return payload


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def _normalize_key(value):
    if value is None:
        return None
    return str(value).strip().casefold()


class MockApiData:
    def __init__(self, root):
        self.root = Path(root)

    def resolve_applicant_id(self, applicant_id=None, task_id=None):
        if applicant_id:
            return applicant_id
        task_id = task_id or os.environ.get("LOAB_TASK_ID")
        if not task_id:
            return None
        ctx = self.root.parent.parent / "tasks" / task_id / "context" / "applicant.json"
        data = _read_json(ctx)
        if not data:
            return None
        return data.get("applicant_id")

    def load_provider_file(self, provider, applicant_id):
        path = self.root / provider / f"{applicant_id}.json"
        return _read_json(path)

    def load_internal_file(self, applicant_id):
        path = self.root / "internal" / f"{applicant_id}.json"
        return _read_json(path)

    def load_policy(self):
        return _read_json(self.root / "internal" / "policy.json")

    def load_regulatory(self):
        return _read_json(self.root / "internal" / "regulatory.json")

    def available_applicants(self, provider):
        folder = self.root / provider
        if not folder.exists():
            return []
        return [p.stem for p in folder.glob("AP-*.json")]

    def get_response(self, provider, applicant_id, response_key, input_key=None):
        data = self.load_provider_file(provider, applicant_id)
        if not data:
            return _soft_error(
                f"No data for provider {provider} applicant {applicant_id}",
                self.available_applicants(provider),
            )
        responses = data.get("responses", {})
        if response_key not in responses:
            return _soft_error(
                f"No response key {response_key} for provider {provider} applicant {applicant_id}",
                responses.keys(),
            )
        payload = responses[response_key]
        if isinstance(payload, dict) and input_key is not None:
            norm = _normalize_key(input_key)
            if norm in {_normalize_key(k) for k in payload.keys()}:
                for k, v in payload.items():
                    if _normalize_key(k) == norm:
                        return {"ok": True, "data": v}
            return _soft_error(
                f"No data for key {input_key} under {provider}.{response_key}",
                payload.keys(),
            )
        return {"ok": True, "data": payload}

    def get_internal_loan(self, applicant_id, loan_id):
        data = self.load_internal_file(applicant_id)
        if not data:
            return _soft_error(
                f"No internal data for applicant {applicant_id}",
                self.available_applicants("internal"),
            )
        accounts = data.get("loan_accounts", {})
        if loan_id not in accounts:
            return _soft_error(
                f"No loan account {loan_id} for applicant {applicant_id}",
                accounts.keys(),
            )
        return {"ok": True, "data": accounts[loan_id]}

    def get_internal_policy(self, section):
        data = self.load_policy() or {}
        responses = data.get("responses", {})
        if section not in responses:
            return _soft_error(f"No policy section {section}", responses.keys())
        return {"ok": True, "data": responses[section]}

    def get_internal_regulatory(self, act_section):
        data = self.load_regulatory() or {}
        responses = data.get("responses", {})
        if act_section not in responses:
            return _soft_error(f"No regulatory reference {act_section}", responses.keys())
        return {"ok": True, "data": responses[act_section]}
