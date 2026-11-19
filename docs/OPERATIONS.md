# Operational control plane

Money-Geta is the local orchestration layer. MoneyPrinterTurbo remains the rendering engine and GTA VI ClaudeCode remains the research/creator workflow source.

## Install (Windows PowerShell)

From the Money-Geta checkout:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
$env:GTAVI_CLAUDECODE_DIR = "C:\\path\\to\\gtavi-claudecode"
$env:MONEYPRINTERTURBO_DIR = "C:\\MoneyPrinterTurbo"
$env:MONEY_GETA_JOBS_DIR = "C:\\Money-Geta-Data\\jobs"
money-geta doctor
```

Keep MoneyPrinterTurbo's existing `config.toml`, OAuth data, API keys, jobs and exports outside this repository. The tool never copies credentials into Money-Geta.

## Commands

```powershell
money-geta doctor
money-geta new-session gta6-weekly
money-geta campaign-check --campaign .\campaign.json
money-geta upstream-check
money-geta upstream-check --apply
money-geta render --campaign .\campaign.json --subject "GTA VI: ..." --materials .\media\clip1.mp4 .\media\clip2.mp4
```

- `doctor`: checks Python, Git, FFmpeg and configured upstream directories. It does not test provider credentials or perform a render.
- `new-session`: creates a unique UTC work directory and never clears old recordings.
- `campaign-check`: checks that required campaign attestations and source references exist. It is not legal clearance.
- `upstream-check`: verifies the exact pinned source blobs and runs `git apply --check`. `--apply` modifies only the configured local GTA VI ClaudeCode checkout, after all patches pass compatibility checks.
- `render`: requires a complete campaign evidence file and existing local media, then invokes the installed MoneyPrinterTurbo CLI. It defaults to local media, so it does not call Pexels or paid video-generation providers.

## Campaign file

Start from `config/campaign.example.json`. The permissions and credits booleans are operator attestations. They must be true only after checking the actual rights and attribution for the supplied assets. Inspect every final video before publication.

## Boundaries

Money-Geta does not auto-publish, accept paid provider terms, spend credits, or certify copyright. The first integrated render path is local-media only. Trend research, source acquisition, Twitch/YouTube recording and clip extraction remain separate integrations until each has a tested adapter.
