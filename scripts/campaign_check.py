"""Strict campaign readiness gate. This is not a legal or copyright clearance tool."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_TEXT = ("campaign_name", "platform")
REQUIRED_TRUE = ("permissions_confirmed", "credits_confirmed")


def validate_campaign(data: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["campaign file must contain a JSON object"]

    for field in REQUIRED_TEXT:
        if not isinstance(data.get(field), str) or not data[field].strip():
            problems.append(f"missing or empty: {field}")

    for field in REQUIRED_TRUE:
        if data.get(field) is not True:
            problems.append(f"must be explicitly true: {field}")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources or not all(
        isinstance(item, str) and item.strip() for item in sources
    ):
        problems.append("sources must be a non-empty list of source references")

    disclosures = data.get("required_disclosures")
    if not isinstance(disclosures, list) or not all(
        isinstance(item, str) and item.strip() for item in disclosures
    ):
        problems.append("required_disclosures must be a list (use [] when none apply)")

    if data.get("schema_version") == 1:
        evidence = data.get("source_evidence")
        ledger = data.get("rights_ledger")
        expected_sources = sources if isinstance(sources, list) else []
        if not isinstance(evidence, list) or len(evidence) != len(expected_sources):
            problems.append("source_evidence must contain one record for every source")
        elif any(not isinstance(item, dict) or item.get("source") != source or not item.get("reference") for item, source in zip(evidence, expected_sources)):
            problems.append("source_evidence must identify each source and its evidence reference")
        if not isinstance(ledger, list) or len(ledger) != len(expected_sources):
            problems.append("rights_ledger must contain one record for every source")
        elif any(not isinstance(item, dict) or item.get("source") != source or not item.get("evidence") or item.get("status") != "operator_attested" for item, source in zip(ledger, expected_sources)):
            problems.append("every rights_ledger entry needs matching source, evidence and operator_attested status")
        permission = data.get("permission_attestation")
        if not isinstance(permission, dict) or permission.get("confirmed") is not True or not permission.get("confirmed_at"):
            problems.append("permission_attestation must record an explicit, timestamped operator confirmation")
        credit = data.get("credit_attestation")
        if not isinstance(credit, dict) or credit.get("confirmed") is not True or not credit.get("confirmed_at"):
            problems.append("credit_attestation must record an explicit, timestamped operator confirmation")
        elif not data.get("credit_records") and credit.get("no_credits_required") is not True:
            problems.append("credit_attestation must include credit records or explicitly state none are required")

    return problems



def validate_claim_gate(data: dict[str, Any], campaign_path: Path) -> list[str]:
    """Require reviewed factual claims for flagged campaigns; recorded unresolved claims block."""
    if data.get("schema_version") != 1:
        return []
    required = data.get("factual_claims_required", False)
    if not isinstance(required, bool):
        return ["factual_claims_required must be an explicit boolean"]
    project_id, campaign_id = data.get("project_id"), data.get("campaign_id")
    ledger = campaign_path.parent / "claim_ledger.jsonl"
    if not isinstance(project_id, str) or not project_id or not isinstance(campaign_id, str) or not campaign_id:
        return ["factual claim review requires project_id and campaign_id"] if required else []
    if not ledger.exists():
        return ["factual claims are required but no claim_ledger.jsonl exists"] if required else []
    try:
        from scripts.claim_registry import ClaimRegistryError, list_claims
        claims = list_claims(project_id, campaign_id, root=campaign_path.parents[3])
    except (OSError, ValueError, IndexError) as exc:
        return [f"claim review could not be validated: {exc}"]
    except ClaimRegistryError as exc:
        return [f"claim review ledger is invalid: {exc}"]
    if required and not claims:
        return ["factual claims are required but no claims have been registered"]
    blocked = [
        f"claim {item.get('claim_id', 'unknown')} is {item.get('status', 'unverified')}"
        for item in claims if item.get("status") != "supported"
    ]
    return ["factual claim review incomplete: " + "; ".join(blocked)] if blocked else []


def check_file(path: Path | None) -> tuple[bool, list[str]]:
    if path is None:
        return False, ["campaign file not supplied"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"campaign file not found: {path}"]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, [f"cannot read valid campaign JSON: {exc}"]
    problems = validate_campaign(data)
    if isinstance(data, dict):
        problems.extend(validate_claim_gate(data, path.resolve()))
    return not problems, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, help="Path to campaign JSON")
    args = parser.parse_args(argv)
    passed, problems = check_file(args.campaign)

    if not passed:
        print("RESULT: INCOMPLETE")
        for problem in problems:
            print(f"- {problem}")
        print("Human review is still required before publication.")
        return 2

    print("RESULT: CAMPAIGN_FIELDS_COMPLETE")
    print("This is not legal clearance. A human must verify rights, platform rules and final media.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
