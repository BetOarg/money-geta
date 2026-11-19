"""Money-Geta operational control plane for the local GTA VI video workflow."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.campaign_check import check_file
from scripts.session_paths import create_session_dir

ROOT = Path(__file__).resolve().parents[1]
PATCHES = {
    "live.py": ("scripts/live.py", "c8208b6a0d9d0e4ddc93cfcd1ee123baeb0bb50a",
                ROOT / "patches/gtavi-claudecode/live-session-isolation.patch"),
    "check.py": ("scripts/check.py", "c71ad730e009e4a5b5aea113a34e20dabd37620b",
                 ROOT / "patches/gtavi-claudecode/campaign-check-fail-closed.patch"),
    "secrets_map.py": ("scripts/secrets_map.py", "1d2b50963c3a2f4986911449679809d7390a4c09",
                       ROOT / "patches/gtavi-claudecode/secrets-map-evidence.patch"),
}


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else None


def doctor() -> int:
    git_path = shutil.which("git")
    ffmpeg_path = shutil.which("ffmpeg")
    mpt_dir = env_path("MONEYPRINTERTURBO_DIR")
    if not ffmpeg_path and mpt_dir:
        bundled = mpt_dir / "lib/python/Lib/site-packages/imageio_ffmpeg/binaries"
        candidates = list(bundled.glob("ffmpeg*.exe")) if bundled.is_dir() else []
        ffmpeg_path = str(candidates[0]) if candidates else None

    checks = [
        ("Python", Path(sys.executable).exists(), sys.version.split()[0]),
        ("Git", git_path is not None, git_path or "not found"),
        ("FFmpeg", ffmpeg_path is not None, ffmpeg_path or "not found on PATH or MPT bundled runtime"),
    ]
    for label, ok, detail in checks:
        print(f"{'PASS' if ok else 'PENDING'} {label}: {detail}")

    configured = [
        ("GTA VI ClaudeCode", env_path("GTAVI_CLAUDECODE_DIR"), Path("scripts/live.py")),
        ("MoneyPrinterTurbo", mpt_dir, Path("config.toml")),
    ]
    for label, path, marker in configured:
        ok = bool(path and (path / marker).is_file())
        print(f"{'PASS' if ok else 'PENDING'} {label}: {path or 'environment variable not set'}")
        checks.append((label, ok, str(path or "not configured")))

    print("NOTE API credentials, Codex/Gemini login, image generation, TTS and a full render are not tested by doctor.")
    return 0 if all(item[1] for item in checks) else 2

def verify_patches(upstream: Path, apply: bool = False) -> int:
    git = shutil.which("git")
    if not git:
        print("FAIL Git executable not found")
        return 2
    if not (upstream / ".git").exists():
        print(f"FAIL not a Git checkout: {upstream}")
        return 2

    ready: list[tuple[str, Path]] = []
    failures = 0
    for label, (relative, expected, patch) in PATCHES.items():
        source = upstream / relative
        if not source.is_file() or not patch.is_file():
            print(f"FAIL {label}: source or patch missing")
            failures += 1
            continue
        actual = subprocess.run(
            [git, "hash-object", str(source)], capture_output=True, text=True, check=False
        )
        if actual.returncode or actual.stdout.strip() != expected:
            print(f"BLOCKED {label}: upstream blob differs; expected {expected}, got {actual.stdout.strip() or 'unavailable'}")
            failures += 1
            continue
        checked = subprocess.run(
            [git, "apply", "--check", str(patch)], cwd=upstream,
            capture_output=True, text=True, check=False
        )
        if checked.returncode:
            print(f"FAIL {label}: git apply --check: {(checked.stderr or checked.stdout).strip()}")
            failures += 1
            continue
        ready.append((label, patch))

    if failures:
        print("NO PATCHES APPLIED: resolve every compatibility failure first.")
        return 1
    if apply:
        for label, patch in ready:
            done = subprocess.run(
                [git, "apply", str(patch)], cwd=upstream,
                capture_output=True, text=True, check=False
            )
            if done.returncode:
                print(f"FAIL {label}: apply failed: {(done.stderr or done.stdout).strip()}")
                return 1
            print(f"APPLIED {label}")
    else:
        for label, _ in ready:
            print(f"PASS {label}: exact upstream blob; patch applies cleanly")
    return 0


def run_mpt(args: argparse.Namespace) -> int:
    mpt_dir = args.mpt_dir.expanduser().resolve()
    cli_file = mpt_dir / "cli.py"
    config_file = mpt_dir / "config.toml"
    if not cli_file.is_file() or not config_file.is_file():
        print(f"INCOMPLETE: MoneyPrinterTurbo requires cli.py and config.toml in {mpt_dir}")
        return 2
    if not args.campaign.is_file():
        print(f"INCOMPLETE: campaign file not found: {args.campaign}")
        return 2
    passed, problems = check_file(args.campaign)
    if not passed:
        print("RESULT: INCOMPLETE")
        for problem in problems:
            print(f"- {problem}")
        return 2

    materials = [item.expanduser().resolve() for item in args.materials]
    missing = [str(item) for item in materials if not item.is_file()]
    if missing:
        print("FAIL: local media files not found:")
        for item in missing:
            print(f"- {item}")
        return 2
    if any("," in str(item) for item in materials):
        print("FAIL: material paths cannot contain commas (MoneyPrinterTurbo CLI delimiter).")
        return 2

    command = [
        sys.executable, str(cli_file),
        "--video-subject", args.subject,
        "--video-source", "local",
        "--video-materials", ",".join(str(item) for item in materials),
        "--video-aspect", args.aspect,
        "--video-count", str(args.count),
        "--stop-at", "video",
    ]
    if args.language:
        command += ["--video-language", args.language]
    if args.voice:
        command += ["--voice-name", args.voice]

    print("CAMPAIGN FIELDS: PASS")
    print("HUMAN REVIEW REQUIRED: confirm actual footage rights, creator credits and final export.")
    print("Starting MoneyPrinterTurbo local-media pipeline...")
    completed = subprocess.run(command, cwd=mpt_dir, check=False)
    print(f"MoneyPrinterTurbo exit code: {completed.returncode}")
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="money-geta", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check local tools and configured upstream installations")
    session = sub.add_parser("new-session", help="allocate a unique, non-destructive recording workspace")
    session.add_argument("job_id")
    session.add_argument("--root", type=Path, default=Path(os.environ.get("MONEY_GETA_JOBS_DIR", "jobs")))
    campaign = sub.add_parser("campaign-check", help="validate campaign evidence fields (not legal clearance)")
    campaign.add_argument("--campaign", type=Path, required=True)
    render = sub.add_parser("render", help="run MoneyPrinterTurbo with a gated campaign and local media")
    render.add_argument("--mpt-dir", type=Path, default=env_path("MONEYPRINTERTURBO_DIR"))
    render.add_argument("--campaign", type=Path, required=True)
    render.add_argument("--subject", required=True)
    render.add_argument("--materials", type=Path, nargs="+", required=True)
    render.add_argument("--language", default="en-US")
    render.add_argument("--voice", default=None, help="MPT voice identifier; defaults to installed config")
    render.add_argument("--aspect", choices=["9:16", "16:9", "1:1"], default="9:16")
    render.add_argument("--count", type=int, choices=range(1, 21), default=1)
    upstream = sub.add_parser("upstream-check", help="verify pinned upstream blobs and patch applicability")
    upstream.add_argument("--path", type=Path, default=env_path("GTAVI_CLAUDECODE_DIR"))
    upstream.add_argument("--apply", action="store_true", help="apply patches after all per-file checks; use on a clean clone")
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor()
    if args.command == "new-session":
        path = create_session_dir(args.root, args.job_id)
        print(path)
        return 0
    if args.command == "campaign-check":
        passed, problems = check_file(args.campaign)
        if not passed:
            print("RESULT: INCOMPLETE")
            for item in problems:
                print(f"- {item}")
            return 2
        print("RESULT: CAMPAIGN_FIELDS_COMPLETE")
        print("HUMAN REVIEW REQUIRED: verify rights, credits, platform rules and final media.")
        return 0
    if args.command == "render":
        if args.mpt_dir is None:
            print("INCOMPLETE: set MONEYPRINTERTURBO_DIR or pass --mpt-dir")
            return 2
        return run_mpt(args)
    if args.command == "upstream-check":
        if args.path is None:
            print("INCOMPLETE: set GTAVI_CLAUDECODE_DIR or pass --path")
            return 2
        if args.apply:
            print("WARNING: applying patches changes the selected local upstream checkout.")
        return verify_patches(args.path.expanduser().resolve(), args.apply)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
