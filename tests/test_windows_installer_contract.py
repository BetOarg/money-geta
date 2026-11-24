from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "install_windows.ps1"


def installer_text() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_installer_checks_ffmpeg_and_ffprobe_before_venv_creation():
    script = installer_text()
    preflight = script.index("# Preflight: fail early")
    venv_creation = script.index("py -3.11 -m venv $VenvDir")
    assert '$MissingMediaTools = @("ffmpeg", "ffprobe")' in script
    assert preflight < venv_creation
    assert "Required media tools missing from PATH" in script


def test_installer_validates_venv_python_311_and_preserves_existing_environment():
    script = installer_text()
    assert "sys.version_info[:2] == (3, 11)" in script
    assert "The installer will not replace it" in script
    assert "Rename it to .venv.backup" in script


def test_installer_reports_install_tests_and_doctor_as_distinct_stages():
    script = installer_text()
    assert 'Write-Stage "Install dependencies"' in script
    assert 'Write-Stage "Run regression tests"' in script
    assert 'Write-Stage "Environment diagnostics"' in script
    assert "INSTALLATION: PASS | REGRESSION TESTS: PASS | ENVIRONMENT DIAGNOSTICS: PENDING/FAIL" in script
    assert "INSTALLATION, REGRESSION TESTS AND ENVIRONMENT DIAGNOSTICS PASSED" in script
