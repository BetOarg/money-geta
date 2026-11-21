# Rights review of image candidates

Openverse candidates are recorded as `unverified`. Before any monetized use, the operator must open the original source page and confirm the license, commercial-use terms, attribution and any restrictions.

## CLI

Review a candidate after independently inspecting its source page and license:

```powershell
python -m scripts.money_geta media-review --project <project> --campaign <campaign> --candidate-id <sha256> --decision approved --reviewer "Operator" --source-reviewed --rights-evidence "Original source terms URL/page reviewed" --license "CC BY 4.0" --attribution "Creator, source link"
python -m scripts.money_geta media-check --project <project> --campaign <campaign> --candidate-id <sha256>
```

A rejection can be recorded with `--decision rejected` and reviewer/notes. Approval requires `--source-reviewed`, evidence text, a reviewed license string and the provider's license URL.

The append-only `media_review_ledger.jsonl` stores candidate metadata SHA-256, source page, provider license, operator-reviewed license, evidence, attribution, reviewer, decision and time. Any change to candidate metadata makes the prior review stale. Latest rejection blocks approval.

**Important:** the check is an operator attestation, not legal certification. Verify the source and terms yourself; do not rely only on Openverse metadata. Rights evidence remains separate from campaign permission/credit fields and must be carried into the final asset usage record before rendering or publishing.
