---
name: campaign-publication-gate
description: Review a finished clip against explicit campaign rules, source evidence, attribution and publication requirements before a human approves posting.
---

# Campaign publication gate

## Required inputs

- Campaign rules with explicit minimum and maximum duration.
- Platform and required disclosures.
- Source URLs and timestamps for source material.
- Creator identity and attribution text.
- Evidence that recording and reuse are permitted.
- Final clip, caption and generated metadata.

## Decision states

- **FAIL**: a technical check or explicit rule fails.
- **INCOMPLETE**: campaign rules, sources, permissions or credits are missing.
- **HUMAN REVIEW REQUIRED**: final video, factual claims, rights, platform rules and attribution need manual inspection.
- **TECHNICAL PASS**: automated technical checks passed; this is not permission to publish.

Never convert missing rules into default PASS. Never treat a caption keyword scan as audiovisual content moderation or legal review. Never infer copyright permission from a public URL or public stream.

## Workflow

1. Validate campaign rules, source evidence, rights attestations and required disclosures; stop with INCOMPLETE when absent.
2. For `news` and `education` campaigns, require at least one registered factual claim. Every registered claim must have latest human assessment `supported`; `unverified`, `unsupported`, `contradicted`, missing evidence and malformed ledgers block the render gate.
3. Treat two distinct hostnames plus operator-attested independence as a minimum workflow check, not proof of editorial independence or truth.
4. Run technical checks on the exact final clip.
5. Inspect the entire clip and caption manually; factual claim review does not replace audiovisual inspection.
6. Verify source attribution and permission for the intended reuse.
7. Present the clip, caption, credits and unresolved issues to the user.
8. Wait for explicit approval. Do not upload or publish automatically.
