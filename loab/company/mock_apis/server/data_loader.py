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
        tasks_root = self.root.parent.parent / "tasks"
        direct = tasks_root / task_id / "pendingfiles.json"
        if direct.exists():
            pending = direct
        else:
            matches = [p / "pendingfiles.json" for p in tasks_root.rglob(task_id) if p.is_dir() and (p / "pendingfiles.json").exists()]
            if len(matches) == 1:
                pending = matches[0]
            else:
                return None
        data = _read_json(pending)
        if not data:
            return None
        applicants = data.get("applicants", [])
        return applicants[0] if applicants else None

    def load_provider_file(self, provider, applicant_id=None):
        # Provider folder data.json
        provider_file = self.root / provider / "data.json"
        if provider_file.exists():
            return _read_json(provider_file)
        # Fallback: provider.json (legacy)
        legacy = self.root / f"{provider}.json"
        if legacy.exists():
            return _read_json(legacy)
        # Fallback: per-applicant file (legacy)
        if applicant_id:
            path = self.root / provider / f"{applicant_id}.json"
            return _read_json(path)
        return None

    def load_internal_file(self, applicant_id):
        path = self.root / "internal" / f"{applicant_id}.json"
        return _read_json(path)

    def load_rates(self):
        return _read_json(self.root.parent / "rates" / "product_rates.json")

    def load_policy(self):
        return _read_json(self.root / "internal" / "policy.json")

    def load_regulatory(self):
        return _read_json(self.root / "internal" / "regulatory.json")

    def available_keys(self, provider, response_key):
        data = self.load_provider_file(provider)
        if not data:
            return []
        responses = data.get("responses", {})
        payload = responses.get(response_key, {})
        if isinstance(payload, dict):
            return list(payload.keys())
        return []

    def get_response(self, provider, response_key, input_key=None, applicant_id=None):
        data = self.load_provider_file(provider, applicant_id)
        if not data:
            return _soft_error(
                f"No data for provider {provider}",
                [],
            )
        responses = data.get("responses", {})
        if response_key not in responses:
            return _soft_error(
                f"No response key {response_key} for provider {provider}",
                responses.keys(),
            )
        payload = responses[response_key]
        if isinstance(payload, dict):
            if input_key is None:
                return _soft_error(
                    f"Missing input key for {provider}.{response_key}",
                    payload.keys(),
                )
            norm = _normalize_key(input_key)
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
                [],
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
        if section is None:
            return _soft_error("Missing policy section", responses.keys())
        if not isinstance(section, str):
            section = str(section)
        if section not in responses:
            # Normalize: accept "6" as "Section 6", "5.5" as "Section 5.5", etc.
            normalized = section.strip()
            if not normalized:
                return _soft_error("Missing policy section", responses.keys())
            if not normalized.lower().startswith("section"):
                normalized = f"Section {normalized}"
            if normalized in responses:
                return {"ok": True, "data": responses[normalized]}
            return _soft_error(f"No policy section {section}", responses.keys())
        return {"ok": True, "data": responses[section]}

    def get_product(self, product_code):
        data = self.load_rates() or {}
        products = data.get("products", {})
        if product_code not in products:
            return _soft_error(
                f"No product found for code {product_code}",
                list(products.keys()),
            )
        return {"ok": True, "data": products[product_code]}

    def get_internal_regulatory(self, act_section):
        data = self.load_regulatory() or {}
        responses = data.get("responses", {})
        if act_section not in responses:
            return _soft_error(f"No regulatory reference {act_section}", responses.keys())
        return {"ok": True, "data": responses[act_section]}
