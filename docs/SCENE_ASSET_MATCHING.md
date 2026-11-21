# Scene-to-asset matching (PR #29)

Money-Geta creates a deterministic, suggestions-only plan that links scene visual descriptions to media already present in the local library.

## CLI

```powershell
python -m scripts.money_geta scene-assets --project PROJECT_ID --campaign CAMPAIGN_ID --script-id SCRIPT_ID --sha256 SCRIPT_SHA256 --limit 5
```

The selected script must be registered and currently approved for the exact SHA-256. The matcher reads its scene list and only considers assets marked `usable_for_selection` by the media-library rights/integrity checks.

## Matching behavior
- Normalizes accents and case; removes common Spanish/English stop words.
- Scores overlap with visual-description tokens at double weight and narration context at single weight.
- Returns matched tokens and a short rationale for transparent review.
- Deterministic ordering uses score then candidate ID.
- Maximum 10 suggestions per scene.

## Safeguards
- No network calls.
- No asset copies, edits, downloads, deletions, or media imports.
- Suggestions are not automatically inserted into a render.
- Output explicitly states `suggestions_only`, `human_review_required`, `render_authorized=false`, and `publishing_authorized=false`.
