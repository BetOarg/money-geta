# Operational control plane

Money-Geta is the local orchestration layer. MoneyPrinterTurbo remains the rendering engine and GTA VI ClaudeCode remains the research/creator workflow source.

## Install (Windows PowerShell)

From the Money-Geta checkout:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
$env:GTAVI_CLAUDECODE_DIR = "C:\\path\\to\\gtavi-claudecode"
# Optional only if the GTA VI project uses a separate Python environment:
$env:GTAVI_CLAUDECODE_PYTHON = "C:\\path\\to\\gtavi-claudecode\\.venv\\Scripts\\python.exe"
$env:MONEYPRINTERTURBO_DIR = "C:\\MoneyPrinterTurbo"
# Optional only if the MPT Python runtime is not auto-detected:
$env:MONEYPRINTERTURBO_PYTHON = "C:\\MoneyPrinterTurbo\\lib\\python\\python.exe"
$env:MONEY_GETA_JOBS_DIR = "C:\\Money-Geta-Data\\jobs"
money-geta doctor
```

Keep MoneyPrinterTurbo's existing `config.toml`, OAuth data, API keys, jobs and exports outside this repository. The tool never copies credentials into Money-Geta. Money-Geta invokes MoneyPrinterTurbo with its own Python environment (auto-detects `.venv`, `venv` or `lib/python`); set `MONEYPRINTERTURBO_PYTHON` if your installation uses another location.

## Commands

```powershell
money-geta doctor
money-geta new-session gta6-weekly
money-geta analyze-video --source .\\media\\gameplay.mp4
money-geta cut-video --job-dir "<job path printed by analyze-video>" --pick 1 --layout blur --hook "GTA VI: ..." 
money-geta campaign-check --campaign .\campaign.json
money-geta upstream-check
money-geta upstream-check --apply
money-geta render --campaign .\campaign.json --subject "GTA VI: ..." --materials .\media\clip1.mp4 .\media\clip2.mp4
```

- `doctor`: checks Python, Git, FFmpeg and configured upstream directories. It does not test provider credentials or perform a render.
- `new-session`: creates a unique UTC work directory and never clears old recordings.
- `analyze-video`: runs the upstream moment-finder on a local video only, in a fresh isolated job directory; requires the GTA VI Python dependencies, FFmpeg and FFprobe.
- `cut-video`: turns one reviewed candidate into a vertical MP4 using the upstream clip cutter. Review the output before rendering or publishing.
- `campaign-check`: checks that required campaign attestations and source references exist. It is not legal clearance.
- `upstream-check`: verifies the exact pinned source blobs and runs `git apply --check`. `--apply` modifies only the configured local GTA VI ClaudeCode checkout, after all patches pass compatibility checks.
- `render`: requires a complete campaign evidence file and existing local media, then invokes the installed MoneyPrinterTurbo CLI. It defaults to local media, so it does not call Pexels or paid video-generation providers.

## Campaign file

Start from `config/campaign.example.json`. The permissions and credits booleans are operator attestations. They must be true only after checking the actual rights and attribution for the supplied assets. Inspect every final video before publication.

## Boundaries

Money-Geta does not auto-publish, accept paid provider terms, spend credits, or certify copyright. The first integrated production chain is local-VOD analysis → candidate clip cutting → campaign gate → MoneyPrinterTurbo rendering. Trend research, online source acquisition, Twitch/YouTube live recording and auto-publication remain separate integrations until each has a tested adapter.
