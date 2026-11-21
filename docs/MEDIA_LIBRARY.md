# Local Media Library

Money-Geta indexes downloaded image assets from each campaign's local `media_assets/` directory and append-only `media_download_ledger.jsonl`. The catalog is read-only: it does not download, copy, delete, rename, modify, render, or publish media.

## CLI

List assets across all campaigns or filter by project/campaign:

```bash
money-geta asset-library list
money-geta asset-library list --project gta-vi --campaign launch
```

Search metadata (all terms must match; case-insensitive):

```bash
money-geta asset-library search --query "city skyline"
money-geta asset-library search --query "creator CC BY" --project gta-vi
```

Verify stored file hashes and current hash-bound rights reviews:

```bash
money-geta asset-library verify
money-geta asset-library verify --project gta-vi --campaign launch
```

## Status fields

- `integrity_status`: verified, hash mismatch, missing/unsafe, or path rejected.
- `rights_status`: current approved/rejected, pending, or stale based on the current review ledger.
- `metadata_current`: candidate metadata hash matches the download record.
- `usable_for_selection`: true only when local file integrity, current candidate metadata, and current approved rights review all pass.

An empty catalog reports `EMPTY` rather than a misleading PASS. A PASS verifies catalog integrity and review-record consistency; it is not a legal opinion, nor does it certify the license or the content. A rights approval is an operator attestation. Review the original source and retain required attribution. The library does not yet feed assets automatically into rendering.
