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

1. Validate campaign rules and required evidence; stop with INCOMPLETE when absent.
2. Run technical checks on the exact final clip.
3. Inspect the entire clip and caption manually.
4. Verify source attribution and permission for the intended reuse.
5. Present the clip, caption, credits and unresolved issues to the user.
6. Wait for explicit approval. Do not upload or publish automatically.
