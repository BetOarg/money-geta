# Approved image downloads

Downloads require a candidate in the campaign's Openverse ledger and a current hash-bound operator approval.

```powershell
python -m scripts.money_geta media-download --project PROJECT_ID --campaign CAMPAIGN_ID --candidate-id CANDIDATE_ID --allow-network --confirm-download
```

Both flags are mandatory; search, review, render, or GUI actions do not trigger downloads.

- HTTPS only, standard port, no URL credentials or sensitive query tokens.
- DNS checked for public addresses; redirects limited to 3 and each destination revalidated.
- Maximum 20 MB, MIME type must match a supported image signature.
- Files stored under campaign `media_assets/`; provenance recorded in `media_download_ledger.jsonl`.
- Existing asset files with differing bytes are never overwritten.
- Downloaded content remains untrusted; it is not automatically included in rendering or publishing.
- Rights review is operator attestation, not legal certification.
