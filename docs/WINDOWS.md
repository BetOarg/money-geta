# Windows 11 installation and first test

## Prerequisites

- Windows 11 and Python 3.11 (Python Launcher `py.exe`).
- Git for Windows.
- A local checkout of GTA VI ClaudeCode containing `scripts/moments.py` and `scripts/cut.py`.
- MoneyPrinterTurbo installed locally (default path: `C:\MoneyPrinterTurbo`).
- FFmpeg **and FFprobe** available on PATH. Verify in a new PowerShell window:

```powershell
ffmpeg -version
ffprobe -version
```

The FFmpeg executable bundled inside MoneyPrinterTurbo may be used by the downloader, but it does not guarantee that FFprobe is installed. Install a Windows FFmpeg distribution that includes both executables and add its `bin` folder to PATH if either command is missing.

## Install Money-Geta

From the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1 -GtaviDir "C:\RUTA\A\gtavi-claudecode" -MptDir "C:\MoneyPrinterTurbo"
```

The installer creates an isolated `.venv`, installs Money-Geta with capture, media and test extras, runs the regression suite, and stores the two upstream paths in your user environment. It does not modify either upstream checkout or their credentials.

Open a **new** PowerShell window after installation, then run:

```powershell
money-geta doctor
money-geta status
```

Resolve every `PENDING` item before using the related feature. `doctor` checks local dependencies and configured paths; it does not validate provider API credentials or guarantee a successful render.

## First end-to-end source test

Only use a source that you have permission to download, edit and publish. This command downloads it and analyzes candidate moments in one isolated session:

```powershell
money-geta process-source --url "URL_DE_UN_VIDEO_AUTORIZADO" --confirm-rights
```

The command prints a `WORKFLOW_SESSION` path, candidate job path and a suggested next command. Review the candidate list before cutting anything; no candidate is automatically approved for publication.

Cut one candidate (replace the job path with the exact path printed by the previous command):

```powershell
money-geta cut-video --job-dir "RUTA_EXACTA_DEL_JOB" --pick 1 --layout blur --captions word
```

Available layouts: `fill`, `blur`, `facecam`, `react`. Captions: `word`, `bubble`, `none`. Facecam/react layouts require FFprobe.

## Local media utilities

```powershell
money-geta media inspect --source "C:\Videos\gameplay.mp4"
money-geta media scenes --source "C:\Videos\gameplay.mp4" --output-dir ".\jobs\scenes"
money-geta media transcribe --source "C:\Videos\gameplay.mp4" --output-dir ".\jobs\captions" --language en
money-geta media burn-subtitles --source "C:\Videos\gameplay.mp4" --subtitles ".\jobs\captions\gameplay.srt" --output ".\jobs\gameplay-subtitled.mp4"
```

## MoneyPrinterTurbo render

Rendering requires a completed campaign evidence file and one or more local media files:

```powershell
Copy-Item config/campaign.example.json config/campaign.json
# Edit config/campaign.json and supply truthful source, permission and credit evidence.
money-geta campaign-check --campaign config/campaign.json
money-geta render --campaign config/campaign.json --subject "GTA VI gameplay highlights" --materials "C:\RUTA\AL\CLIP.mp4" --aspect 9:16 --count 1
```

A successful field check is not legal clearance. Review footage rights, creator credits, platform rules, subtitles and final output yourself. Automatic cross-post publishing is blocked.

## Diagnostics and support bundle

```powershell
money-geta doctor
money-geta status
python -m pytest
```

If a command fails, copy its complete console output and the relevant `money-geta.json` manifest. Do not share API keys, cookies, authorization headers, private URLs or URL query tokens.
