# Image discovery via Openverse

Money-Geta provides an optional Openverse image discovery adapter. It searches the official Openverse API and stores candidate metadata in the campaign's local `media_candidates.jsonl` ledger. It does not download images or mark rights as verified.

## Enable and run

The Windows desktop GUI also provides an **Imágenes** tab: select project/campaign, enter a query, choose tall/wide/square, confirm the search, select a result and open its source page for manual review. The GUI uses the same opt-in and writes to the same campaign ledger.


Review the API usage limits and the current provider terms first. Enable requests only for the session:

```powershell
$env:MONEY_GETA_IMAGE_SEARCH_ALLOW_REQUESTS="true"
python -m scripts.money_geta image-search --project <project> --campaign <campaign> --query "city skyline at dusk" --aspect tall --limit 12
```

`--aspect`: `tall`, `wide`, or `square`. The query is limited to 200 characters and the result count to 1–20. The API request uses `license_type=commercial`, excludes mature results and filters dead links. Anonymous requests are supported by the provider but subject to rate limits; no key is required by this adapter.

## Candidate record

Each result stores provider, query, title, image URL, source page URL, creator, creator URL, license, license version, license URL, source, category, thumbnail, dimensions, attribution text, retrieval timestamp, and `rights_status=unverified`.

The ledger deduplicates candidate IDs derived from image/source URLs. The adapter never downloads or opens result image URLs.

## Required human review

Open the original source page and independently verify the license, commercial use, modification restrictions, attribution requirements, creator and image. Openverse explicitly cautions that license metadata is not verified and that responsibility lies with the user. A search filter is not permission. Keep verified permissions/attributions in the campaign's rights and credit records before using an asset in a monetized video.

## API documentation

- Openverse image API: https://api.openverse.org/v1/
- Openverse search algorithm: https://docs.openverse.org/api/reference/search_algorithm.html
- Openverse terms: https://docs.openverse.org/terms_of_service/

