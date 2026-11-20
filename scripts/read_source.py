"""CLI entry point for public-source research capture."""
from __future__ import annotations
import argparse
from scripts.providers.source_reader import SourceReadError, read_source, record_source_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="money-geta-read-source")
    parser.add_argument("--project", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--allow-network", action="store_true",
                        help="explicitly authorize an outbound public web request")
    args = parser.parse_args(argv)
    if not args.allow_network:
        print("BLOCKED: add --allow-network after reviewing the URL and network access.")
        return 2
    try:
        document = read_source(args.url, timeout_seconds=args.timeout)
        ledger = record_source_document(args.project, args.campaign, document)
    except (OSError, ValueError, SourceReadError) as exc:
        print(f"FAIL: {exc}")
        return 2
    print(f"EVIDENCE: {document.evidence_id}")
    print(f"TITLE: {document.title or '(no title)'}")
    print(f"SOURCE: {document.final_url}")
    print(f"CONTENT SHA-256: {document.content_sha256}")
    print(f"LEDGER: {ledger}")
    print("NOTE: extraction does not verify factual claims, rights or publication permission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
