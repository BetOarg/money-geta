param(
    [string]$GtaviDir = "",

    [string]$MptDir = "C:\MoneyPrinterTurbo",

    [string]$JobsDir = (Join-Path $env:LOCALAPPDATA "Money-Geta\jobs")
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Cli = Join-Path $VenvDir "Scripts\money-geta.exe"

function Write-Stage([string]$Name) {
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
}

# Preflight: fail early before creating or modifying the virtual environment.
Write-Stage "Preflight checks"
$VendoredGtaviDir = Join-Path $RepoRoot "vendor\gtavi-claudecode"
if (-not (Test-Path (Join-Path $VendoredGtaviDir "scripts\moments.py")) -or -not (Test-Path (Join-Path $VendoredGtaviDir "scripts\cut.py"))) {
    throw "Money-Geta vendored GTA VI scripts are missing. Restore vendor\gtavi-claudecode before installing."
}
if ($GtaviDir -and (-not (Test-Path (Join-Path $GtaviDir "scripts\live.py")))) {
    throw "Optional external GTA VI checkout must contain scripts\live.py."
}
if (-not (Test-Path (Join-Path $MptDir "cli.py")) -or -not (Test-Path (Join-Path $MptDir "config.toml"))) {
    throw "MoneyPrinterTurbo directory must contain cli.py and config.toml: $MptDir"
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher (py.exe) not found. Install Python 3.11 and retry."
}
py -3.11 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11 is required. Install it with 'py install 3.11' and retry."
}
$MissingMediaTools = @("ffmpeg", "ffprobe") | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
if ($MissingMediaTools.Count -gt 0) {
    throw "Required media tools missing from PATH: $($MissingMediaTools -join ', '). Install FFmpeg including FFprobe, reopen PowerShell, and retry."
}

# Never replace an existing virtual environment automatically.
if (-not (Test-Path $VenvPython)) {
    if (Test-Path $VenvDir) {
        throw "An incomplete .venv exists (python.exe missing). Rename .venv to .venv.backup manually, then rerun this installer."
    }
    py -3.11 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not create Money-Geta virtual environment." }
}
& $VenvPython -c "import sys; print('Venv Python:', sys.version.split()[0]); sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The existing .venv does not use Python 3.11. The installer will not replace it. Rename it to .venv.backup and rerun."
}

Write-Stage "Install dependencies"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed. Installation is incomplete; fix the pip/network error and rerun." }
& $VenvPython -m pip install --editable "$RepoRoot[capture,media,gtavi,test,gui]"
if ($LASTEXITCODE -ne 0) { throw "Money-Geta installation failed. The virtual environment may be partial; rerun after resolving the pip error." }

Write-Stage "Validate desktop GUI"
& $VenvPython -c "import tkinter; import scripts.money_geta_gui"
if ($LASTEXITCODE -ne 0) { throw "Tkinter is unavailable in this Python installation. Install Python from python.org with Tcl/Tk support." }

Write-Stage "Run regression tests"
& $VenvPython -m pytest
if ($LASTEXITCODE -ne 0) { throw "Money-Geta regression tests failed. Installation is present, but it is NOT validated." }

function Find-ProjectPython([string]$ProjectDir) {
    $Candidates = @(
        (Join-Path $ProjectDir ".venv\Scripts\python.exe"),
        (Join-Path $ProjectDir "venv\Scripts\python.exe"),
        (Join-Path $ProjectDir "lib\python\python.exe")
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) { return (Resolve-Path $Candidate).Path }
    }
    return ""
}

Write-Stage "Configure local project paths"
$GtaviPython = if ($GtaviDir) { Find-ProjectPython $GtaviDir } else { "" }
$MptPython = Find-ProjectPython $MptDir

$Settings = @{
    MONEYPRINTERTURBO_DIR = (Resolve-Path $MptDir).Path
    MONEY_GETA_JOBS_DIR = $JobsDir
}
if ($GtaviDir) { $Settings["GTAVI_CLAUDECODE_DIR"] = (Resolve-Path $GtaviDir).Path }
if ($GtaviPython) { $Settings["GTAVI_CLAUDECODE_PYTHON"] = $GtaviPython }
if ($MptPython) { $Settings["MONEYPRINTERTURBO_PYTHON"] = $MptPython }

foreach ($Name in $Settings.Keys) {
    [Environment]::SetEnvironmentVariable($Name, $Settings[$Name], "User")
    Set-Item -Path "Env:$Name" -Value $Settings[$Name]
}
New-Item -ItemType Directory -Force -Path $JobsDir | Out-Null
Write-Host "Money-Geta dependencies and regression suite installed successfully. Optional external live-recording checkout, credentials and generated media were not modified."

Write-Stage "Create desktop shortcut"
$Pythonw = Join-Path $VenvDir "Scripts\pythonw.exe"
if (-not (Test-Path $Pythonw)) { $Pythonw = $VenvPython }
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Money-Geta.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "-m scripts.money_geta_gui"
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.Description = "Money-Geta - procesamiento local de videos"
$Shortcut.Save()
Write-Host "Desktop shortcut created: $ShortcutPath"

Write-Stage "Environment diagnostics"
Write-Host "Diagnostics are separate from installation/tests: PENDING optional providers or external projects do not mean pip/tests failed."
& $Cli doctor
$DoctorExitCode = $LASTEXITCODE
if ($DoctorExitCode -ne 0) {
    Write-Warning "INSTALLATION: PASS | REGRESSION TESTS: PASS | ENVIRONMENT DIAGNOSTICS: PENDING/FAIL. Resolve doctor items before recording or rendering."
    exit 2
}
Write-Host "VERDE: INSTALLATION, REGRESSION TESTS AND ENVIRONMENT DIAGNOSTICS PASSED." -ForegroundColor Green
