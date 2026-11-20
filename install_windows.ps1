param(
    [Parameter(Mandatory = $true)]
    [string]$GtaviDir,

    [string]$MptDir = "C:\MoneyPrinterTurbo",

    [string]$JobsDir = (Join-Path $env:LOCALAPPDATA "Money-Geta\jobs")
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Cli = Join-Path $RepoRoot ".venv\Scripts\money-geta.exe"

if (-not (Test-Path (Join-Path $GtaviDir "scripts\moments.py"))) {
    throw "GTA VI ClaudeCode directory is invalid: scripts\moments.py was not found."
}
if (-not (Test-Path (Join-Path $MptDir "cli.py")) -or -not (Test-Path (Join-Path $MptDir "config.toml"))) {
    throw "MoneyPrinterTurbo directory must contain cli.py and config.toml: $MptDir"
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher (py.exe) not found. Install Python 3.11 and retry."
}
py -3.11 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11 is required."
}

if (-not (Test-Path $VenvPython)) {
    if (Test-Path (Join-Path $RepoRoot ".venv")) {
        throw "An incomplete .venv already exists. Rename it manually; installer will not overwrite it."
    }
    py -3.11 -m venv (Join-Path $RepoRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create Money-Geta virtual environment." }
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $VenvPython -m pip install --editable "$RepoRoot[capture,media,test]"
if ($LASTEXITCODE -ne 0) { throw "Money-Geta installation failed." }

Write-Host "Running Money-Geta regression tests..."
& $VenvPython -m pytest
if ($LASTEXITCODE -ne 0) { throw "Money-Geta regression tests failed." }

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

$GtaviPython = Find-ProjectPython $GtaviDir
$MptPython = Find-ProjectPython $MptDir

$Settings = @{
    GTAVI_CLAUDECODE_DIR = (Resolve-Path $GtaviDir).Path
    MONEYPRINTERTURBO_DIR = (Resolve-Path $MptDir).Path
    MONEY_GETA_JOBS_DIR = $JobsDir
}
if ($GtaviPython) { $Settings["GTAVI_CLAUDECODE_PYTHON"] = $GtaviPython }
if ($MptPython) { $Settings["MONEYPRINTERTURBO_PYTHON"] = $MptPython }

foreach ($Name in $Settings.Keys) {
    [Environment]::SetEnvironmentVariable($Name, $Settings[$Name], "User")
    Set-Item -Path "Env:$Name" -Value $Settings[$Name]
}

New-Item -ItemType Directory -Force -Path $JobsDir | Out-Null
Write-Host "Money-Geta installed. Existing upstream folders, credentials and generated media were not modified."
Write-Host "Running environment diagnostics..."
Write-Host "FFmpeg and FFprobe must both be available on PATH. The MPT-bundled FFmpeg can support downloads, but it does not replace FFprobe."
& $Cli doctor
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Installation completed, but diagnostics are incomplete. Resolve PENDING items before recording or rendering."
    exit 2
}
Write-Host "VERDE: Money-Geta CLI and configured project paths are ready."
