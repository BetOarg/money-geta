"""CLI for creating and explicitly assessing campaign factual claims."""
from __future__ import annotations
import argparse
import json
from scripts.claim_registry import ClaimRegistryError, assess_claim, create_claim, list_claims


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="money-geta-claims")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("--project", required=True)
    add.add_argument("--campaign", required=True)
    add.add_argument("--claim", required=True)
    add.add_argument("--evidence", action="append", required=True)
    assess = sub.add_parser("assess")
    assess.add_argument("--project", required=True)
    assess.add_argument("--campaign", required=True)
    assess.add_argument("--claim-id", required=True)
    assess.add_argument("--status", choices=["supported", "contradicted", "unsupported", "unverified"], required=True)
    assess.add_argument("--rationale", required=True)
    assess.add_argument("--independence-attested", action="store_true")
    assess.add_argument("--contradiction-summary", default="")
    show = sub.add_parser("list")
    show.add_argument("--project", required=True)
    show.add_argument("--campaign", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "add":
            result = create_claim(args.project, args.campaign, args.claim, args.evidence)
        elif args.action == "assess":
            result = assess_claim(args.project, args.campaign, args.claim_id, args.status, args.rationale,
                                  independence_attested=args.independence_attested,
                                  contradiction_summary=args.contradiction_summary)
        else:
            result = list_claims(args.project, args.campaign)
    except (OSError, ValueError, ClaimRegistryError) as exc:
        print(f"FAIL: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
