# Script drafts (draft-only)

Money-Geta can generate a structured short-form script from captured source documents and a campaign's claim ledger. It does not auto-approve the script or call the provider unless the operator explicitly runs the command and enables LLM requests.

## Usage

```powershell
python -m scripts.money_geta script-draft --project mi-proyecto --campaign mi-campana --language es-AR --max-tokens 2000
```

## Requirements

- Campaign passes `campaign-check` (rights/credits fields and factual claim gate).
- Original source text is captured in the campaign's `source_ledger.jsonl`.
- Source documents match the campaign's declared source URLs.
- Every existing claim-ledger entry is `supported`; unresolved claims block the draft.
- LLM provider, model and base URL are configured. Requests require `MONEY_GETA_LLM_ALLOW_REQUESTS=true`.

## Output

A JSON draft is stored in the campaign's `drafts/` folder. It includes the title, hook, narration, scenes, CTA, evidence IDs, supported claim IDs, model, timestamp and an input hash. Drafts remain `status: draft` and `approval.status: pending`.

## Validation

The generated JSON is checked for required fields, length limits, 1–8 scenes, citation IDs, and claim references. News and education claims must match a supported claim-ledger entry exactly, including evidence IDs. Other profiles still require source citations; if the model adds a claim-ledger ID, its text and evidence must match that supported record.

These structural checks cannot semantically prove that narration is accurate, complete or appropriately framed. A person must review the script and sources. The model is not the truth adjudicator.

## Cost and security

- No provider call during startup or tests.
- Credentials remain in environment variables and are not written to draft files.
- Non-local LLM gateways require HTTPS; local gateways may use HTTP.
- Source excerpts are treated as untrusted data, not prompt instructions.
- The request may consume quota or incur charges; review provider/model/quota before enabling the opt-in.
- Script generation never renders, approves, publishes or schedules.
