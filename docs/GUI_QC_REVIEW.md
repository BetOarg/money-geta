# GUI quality review

The **QC y revisión** desktop tab lists registered final MP4 artifacts from the app's campaign and project roots.

## Review sequence
1. Select a registered artifact. Its ID and SHA-256 are shown with the campaign and latest recorded QC/decision.
2. Run **Ejecutar QC completo**. The workflow records technical QC, runs perceptual observations with FFmpeg, optionally checks a selected SRT/VTT file, consolidates the reports, and records central QC against the same artifact hash.
3. Review the central report. Technical and perceptual checks are automated; perceptual observations are not automatically defects. Subtitle QC checks structure/readability only, not transcription correctness or audio sync.
4. Open and inspect the complete video. Mark the explicit human-review confirmation and use **Aprobar tras revisión** only when the central report is `READY_FOR_HUMAN_REVIEW` and the displayed hash is unchanged.

## Statuses
- `FAILED`: a blocking technical check or QC execution failure; approval blocked.
- `REVIEW_REQUIRED`: perceptual observations or optional subtitle findings require review; the strict publication gate remains blocked.
- `READY_FOR_HUMAN_REVIEW`: QC checks pass without findings; human visual review and approval still required.

Reports are stored in the campaign-local `qc_reports/` directory and the central QC event is append-only in the artifact ledger. This panel does not publish, schedule, or connect to external accounts.
