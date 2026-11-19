# Money Geta — GTA 6 Content Studio

Workspace for integrating and validating a local-first GTA 6 content workflow.

## Components

- **MoneyPrinterTurbo**: video scripting, asset assembly and rendering engine.
- **gtavi-claudecode**: research and creator-workflow skills (upstream is not modified).
- **money-geta**: integration contracts, safety patches, validation tools and Windows documentation.

## Principles

1. Keep upstream repositories unchanged; integrate through documented adapters and pinned references.
2. Never delete or overwrite previous recordings or generated assets automatically.
3. Treat missing campaign rules, permissions, credits or source evidence as **INCOMPLETE**, never as a pass.
4. Separate automated technical checks from legal/editorial human review.
5. Do not commit API keys, access tokens, cookies, private footage or other secrets.
6. A technical PASS does not imply copyright clearance or permission to publish.

## Status

Initial repository bootstrap. Implementation and tests are being added on a dedicated working branch.

## Planned structure

- `scripts/`: safe validation utilities.
- `tests/`: regression tests for destructive behavior and fail-open checks.
- `docs/`: integration and Windows setup notes.
- `integrations/`: adapter contracts for upstream projects.
- `.github/workflows/`: continuous integration.

## License

The integration code in this repository will be released under the MIT License. Upstream projects retain their own licenses and notices; see `THIRD_PARTY_NOTICES.md` before redistributing any upstream code.
