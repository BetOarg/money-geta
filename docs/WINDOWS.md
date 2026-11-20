# Windows 11 installation and first test

## Prerequisites

- Windows 11 and Python 3.11 (Python Launcher `py.exe`).
- Git for Windows.
- GTA VI analysis and cutting tools are included in `vendor/gtavi-claudecode/`; no separate checkout is required for those functions.
- An external Git checkout of GTA VI ClaudeCode is optional and is currently required only for live recording / upstream patch verification.
- MoneyPrinterTurbo installed locally (default path: `C:\MoneyPrinterTurbo`).
- FFmpeg **and FFprobe** available on PATH. Verify in a new PowerShell window:

```powershell
ffmpeg -version
ffprobe -version
```

The FFmpeg executable bundled inside MoneyPrinterTurbo may be used by the downloader, but it does not guarantee that FFprobe is installed. Install a Windows FFmpeg distribution that includes both executables and add its `bin` folder to PATH if either command is missing.

## Desktop application

The Windows installer also creates a **Money-Geta** shortcut on the current user's Desktop. Open it to launch the graphical interface (no terminal window when the virtual environment's `pythonw.exe` is available).

On first launch, the app runs `money-geta doctor` automatically. Use the **Configuración** tab to set:
- MoneyPrinterTurbo directory (must contain `cli.py` and `config.toml`).
- GTA VI ClaudeCode directory (defaults to the reviewed copy at `vendor/gtavi-claudecode`).
- Jobs directory (defaults to `%LOCALAPPDATA%\Money-Geta\jobs`).

Settings are stored locally in `%LOCALAPPDATA%\Money-Geta\settings.json`; they do not contain API keys. The **Analizar y cortar** tab accepts a local video or an authorized URL. URL acquisition is blocked until the operator confirms rights. Select a candidate, enter the creator credit, choose a layout/caption style and create the clip. The **Render final · MPT** tab sends one or more local videos to MoneyPrinterTurbo with subject, language, aspect ratio, count and optional voice. It creates a campaign evidence file locally and requires source references plus explicit permission and credit confirmations before invoking the existing fail-closed CLI render workflow. The **Clips y sesiones** tab lists sessions, candidates and generated MP4 files, including MoneyPrinterTurbo outputs; select a file to open it in the Windows default player or send it directly to the MPT render tab.

The GUI does not enable live recording or auto-publishing. MoneyPrinterTurbo's render gate still checks campaign fields, local input files, supported CLI flags and the local config's auto-upload setting. A field check is not legal clearance; a human must review rights, credits, platform rules and final output.

## Install Money-Geta

From the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1 -MptDir "C:\MoneyPrinterTurbo"
```

The installer creates an isolated `.venv`, installs Money-Geta with capture, media, GTA VI and test dependencies, and runs the regression suite. It configures MoneyPrinterTurbo. The vendored GTA VI scripts are used by default; no separate upstream checkout or environment variable is needed for analysis and cutting.

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
money-geta cut-video --job-dir "RUTA_EXACTA_DEL_JOB" --pick 1 --layout blur --captions word --credit "@CREADOR"
```

Available layouts: `fill`, `blur`, `facecam`, `react`. Captions: `word`, `bubble`, `none`. `--credit` is required to attribute the original creator. Facecam/react layouts require FFprobe and may download the YuNet face-detection model on first use. Live recording remains an optional external-checkout feature and is not enabled by the vendored default.

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
