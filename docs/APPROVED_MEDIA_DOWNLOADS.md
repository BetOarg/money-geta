# Approved image downloads

Downloads require a candidate in the campaign's Openverse ledger and a current hash-bound operator approval.

```powershell
python -m scripts.money_geta media-download --project PROJECT_ID --campaign CAMPAIGN_ID --candidate-id CANDIDATE_ID --allow-network --confirm-download
```

Both flags are mandatory; search, review, render, or GUI actions do not trigger downloads. In the desktop app, select a candidate whose status is `reviewed_approved`, then use **Descargar aprobada** and confirm the network request.

- HTTPS only, standard port, no URL credentials or sensitive query tokens.
- DNS is checked and the HTTPS connection pins to a validated public IP; redirects limited to 3 and each destination revalidated. Proxy environment settings are bypassed.
- Maximum 20 MB, MIME type must match a supported image signature.
- Files stored under campaign `media_assets/`; provenance recorded in `media_download_ledger.jsonl`.
- Repeated downloads reuse a hash-verified file and do not fetch it again. Existing asset files with differing bytes are never overwritten.
- Downloaded content remains untrusted; it is not automatically included in rendering or publishing.
- Rights review is operator attestation, not legal certification.
