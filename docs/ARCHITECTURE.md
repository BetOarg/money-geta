# Architecture and integration boundaries

## Roles

- **MoneyPrinterTurbo** remains the rendering/content assembly engine.
- **gtavi-claudecode** remains an independently versioned research/creator skill source.
- **money-geta** owns local adapters, safety checks, regression tests and Windows setup guidance.

Do not copy entire upstream repositories into this repository by default. Prefer pinned references, documented install steps and small adapters. This avoids accidental license mixing and makes upstream updates reviewable.

## Safety fixes represented in this foundation

### Live recording data

The prior static audit found that the upstream live script removes matching files from a shared `jobs/<id>/live/` directory at startup. Do not run that destructive behavior against valuable recordings. The integration utility `scripts/session_paths.py` allocates a unique per-run directory and never deletes previous sessions. Wiring it into an upstream script requires a reviewed adapter/patch and an integration test against that exact upstream revision.

### Campaign checks

The integration gate accepts a JSON campaign file and returns exit code 2 with `INCOMPLETE` if the file is missing, malformed or lacks required evidence fields. A successful result means only that required fields are present; it does not verify actual rights, footage, credits, platform policies or truthfulness.

Example schema:

```json
{
  "campaign_name": "GTA VI explainers",
  "platform": "YouTube",
  "permissions_confirmed": true,
  "credits_confirmed": true,
  "sources": ["https://example.com/source"],
  "required_disclosures": []
}
```

The booleans are attestations supplied by the operator, not independently verified facts. Human review remains mandatory before publication.

## Quality statuses

- **PASS**: automated checks passed for the exact checks run.
- **INCOMPLETE**: required inputs/evidence are missing.
- **HUMAN REVIEW REQUIRED**: rights, credits, claims, platform rules and final media need human inspection.
- **FAIL**: a technical or policy check failed.

Never collapse these into a single publish approval.
