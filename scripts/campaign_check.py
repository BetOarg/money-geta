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
