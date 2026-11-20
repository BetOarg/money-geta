# Operational control plane

Money-Geta is the local orchestration layer. MoneyPrinterTurbo remains the rendering engine and GTA VI ClaudeCode remains the research/creator workflow source.

## Install (Windows PowerShell)

From the Money-Geta checkout, run the bootstrap. The pinned GTA VI analysis/cutting source is already included:

```powershell
.\install_windows.ps1
```

The installer creates a local venv only if one does not exist and installs Money-Geta plus the vendored GTA VI dependencies. No external GTA VI checkout is needed for analysis or cutting. An external Git checkout is optional for live recording and patch verification only. To install manually instead:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[capture,media,gtavi,test]"
$env:GTAVI_CLAUDECODE_DIR = "C:\path\to\external-gtavi-checkout"  # optional: live recording only
# Optional only if the GTA VI project uses a separate Python environment:
$env:GTAVI_CLAUDECODE_PYTHON = "C:\path\to\external-gtavi-checkout\.venv\Scripts\python.exe"  # optional
$env:MONEYPRINTERTURBO_DIR = "C:\MoneyPrinterTurbo"
# Optional only if the MPT Python runtime is not auto-detected:
$env:MONEYPRINTERTURBO_PYTHON = "C:\MoneyPrinterTurbo\lib\python\python.exe"
$env:MONEY_GETA_JOBS_DIR = "C:\Money-Geta-Data\jobs"
money-geta doctor
```

Before rendering, ensure MoneyPrinterTurbo's existing `config.toml` has `upload_post_auto_upload = false`; Money-Geta blocks rendering if automatic cross-platform publishing is enabled. Keep `config.toml`, OAuth data, API keys, jobs and exports outside this repository. The tool never copies credentials into Money-Geta. Money-Geta invokes MoneyPrinterTurbo with its own Python environment (auto-detects `.venv`, `venv` or `lib/python`); set `MONEYPRINTERTURBO_PYTHON` if your installation uses another location.

## Projects and campaigns
The Windows desktop app includes a Projects tab for creating projects, selecting one of the four profiles, listing local projects and creating/listing campaign drafts. Its storage defaults to the local Money-Geta application-data folder. The CLI remains the full interface for entering topic and brief metadata.


Projects bind an editorial brief to a reusable content profile. Campaigns inherit that profile and start as incomplete drafts; the existing campaign gate must block them until sources, permissions and credits are supplied and verified.

```powershell
money-geta projects create --name "Noticias de tecnología" --profile news --topic "IA" --brief "Explicar avances verificables"
money-geta projects list
money-geta projects show noticias-de-tecnologia
money-geta campaigns create --project noticias-de-tecnologia --name "Primer video" --platform "YouTube Shorts"
money-geta campaigns list --project noticias-de-tecnologia
money-geta campaigns show --project noticias-de-tecnologia primer-video
money-geta campaigns update --project noticias-de-tecnologia primer-video --source "https://example.org/article" --rights-evidence "Permiso del editor archivado localmente" --confirm-permissions --confirm-credits --no-credits-required
```

Set MONEY_GETA_PROJECTS_DIR to choose the local data directory. New campaigns are draft-only and never publish or schedule content.

## Profiles

The profile registry is declarative and validated at runtime. GTA VI is a specialized subprofile inside Gaming, not a global mode.

```powershell
money-geta profiles list
money-geta profiles show gaming
money-geta profiles show viral
money-geta profiles show news
money-geta profiles show education
```

The registry currently identifies four profiles. Gaming is marked partial because the existing implementation is still GTA VI-centric; Viral, News and Education are planned profiles. Listing a profile does not imply that every listed capability is already implemented.

## Commands

```powershell
money-geta doctor
money-geta status
money-geta new-session gta6-weekly
money-geta record-live --url "https://www.youtube.com/watch?v=..." --minutes 60 --confirm-recording
money-geta process-source --url "URL_DE_UN_VIDEO_AUTORIZADO" --confirm-rights
money-geta analyze-video --source .\media\gameplay.mp4
money-geta cut-video --job-dir "<job path printed by analyze-video>" --pick 1 --layout blur --hook "GTA VI: ..." --credit "@creator"
money-geta campaign-check --campaign .\campaign.json
money-geta upstream-check
money-geta upstream-check --apply
money-geta render --campaign .\campaign.json --subject "GTA VI: ..." --materials .\media\clip1.mp4 .\media\clip2.mp4
```

- `doctor`: checks Python, Git, FFmpeg, FFprobe, the vendored GTA VI analysis dependencies and the MoneyPrinterTurbo CLI contract. It does not test provider credentials or perform a render.
- `status`: lists recent workflow sessions from Money-Geta's local JSON run ledger.
- `new-session`: creates a unique UTC work directory, records it in the ledger and never clears old recordings. Each analysis, clip and render stage updates its session manifest.
- `record-live`: starts a YouTube/Twitch recording only after explicit `--confirm-recording` and after verifying the session-isolation patch is applied.
- `process-source`: downloads a source only after `--confirm-rights`, then analyzes moments using the vendored GTA VI scripts in the same isolated session.
- `analyze-video`: runs the vendored moment-finder on a local video in a fresh isolated job directory; requires the GTA VI Python dependencies, FFmpeg and FFprobe.
- `cut-video`: turns one reviewed candidate into a vertical MP4 using the vendored clip cutter. `--credit` is mandatory; review the output before rendering or publishing.
- `campaign-check`: checks campaign attestations, source references and the factual-claim ledger. `news` and `education` campaigns require at least one claim, and every recorded claim must have latest status `supported` before render. It is not legal clearance or final-media approval.
- `upstream-check`: verifies the exact pinned safety-patch blobs and runs `git apply --check` against an optional external Git checkout. It does not modify the vendored snapshot.
- `render`: requires a complete campaign evidence file and existing local media, then invokes the installed MoneyPrinterTurbo CLI, blocks automatic cross-posting and verifies the final MP4 files exist. It defaults to local media, so it does not call Pexels or paid video-generation providers.

## Campaign file

Start from `config/campaign.example.json`. The permissions and credits booleans are operator attestations. They must be true only after checking the actual rights and attribution for the supplied assets. Inspect every final video before publication.

## Boundaries

Money-Geta does not auto-publish, accept paid provider terms, spend credits, or certify copyright. The integrated production chain is authorized source acquisition → moment analysis → human candidate selection → credited vertical cut → campaign gate → MoneyPrinterTurbo rendering. The other imported skills/scripts are preserved but still require controlled Money-Geta adapters before being exposed as operational commands. Auto-publication remains blocked.


## Final artifact approval

See [FINAL_ARTIFACT_REVIEW.md](FINAL_ARTIFACT_REVIEW.md) for automatic MP4 registration, SHA-256-bound human review, and the non-publishing `publication-check` command. Rendered files remain pending until an operator approves the exact registered hash.
