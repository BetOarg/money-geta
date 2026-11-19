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
}


def env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else None


def doctor() -> int:
    git_path = shutil.which("git")
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    mpt_dir = env_path("MONEYPRINTERTURBO_DIR")
    if not ffmpeg_path and mpt_dir:
        bundled = mpt_dir / "lib/python/Lib/site-packages/imageio_ffmpeg/binaries"
        candidates = list(bundled.glob("ffmpeg*.exe")) if bundled.is_dir() else []
        ffmpeg_path = str(candidates[0]) if candidates else None

    checks = [
        ("Python", Path(sys.executable).exists(), sys.version.split()[0]),
        ("Git", git_path is not None, git_path or "not found"),
        ("FFmpeg", ffmpeg_path is not None, ffmpeg_path or "not found on PATH or MPT bundled runtime"),
        ("FFprobe", ffprobe_path is not None, ffprobe_path or "not found on PATH"),
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




def resolve_gtavi_python(gtavi_dir: Path, override: Path | None = None) -> Path:
    if override is not None:
        candidate = override.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"GTA VI ClaudeCode Python runtime not found: {candidate}")
        return candidate
    candidates = [
        gtavi_dir / ".venv/Scripts/python.exe",
        gtavi_dir / "venv/Scripts/python.exe",
        gtavi_dir / "lib/python/python.exe",
        gtavi_dir / ".venv/bin/python",
        gtavi_dir / "venv/bin/python",
        gtavi_dir / "lib/python/bin/python",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return Path(sys.executable).resolve()


def run_moments(args: argparse.Namespace) -> int:
    gtavi_dir = args.gtavi_dir.expanduser().resolve()
    script = gtavi_dir / "scripts/moments.py"
    if not script.is_file():
        print(f"INCOMPLETE: GTA VI ClaudeCode moments.py not found: {script}")
        return 2
    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(f"FAIL: local source video not found: {source}")
        return 2
    missing_tools = [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]
    if missing_tools:
        print("INCOMPLETE: GTA VI clip analysis requires on-PATH tools: " + ", ".join(missing_tools))
        return 2
    try:
        python_exe = resolve_gtavi_python(gtavi_dir, args.gtavi_python)
    except FileNotFoundError as exc:
        print(f"INCOMPLETE: {exc}")
        return 2

    root = args.jobs_root.expanduser().resolve()
    session = create_session_dir(root, f"analysis-{source.stem}")
    env = os.environ.copy()
    env["CLIP_DESK_HOME"] = str(session)
    command = [
        str(python_exe), str(script), str(source),
        "--top", str(args.top), "--min", str(args.min_seconds),
        "--max", str(args.max_seconds),
    ]
    completed = subprocess.run(command, cwd=gtavi_dir, env=env, capture_output=True, text=True, check=False)
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip())
    if completed.returncode:
        print(f"FAIL: moments analysis exited {completed.returncode}")
        return completed.returncode
    for line in completed.stdout.splitlines():
        if line.startswith("job: "):
            print(f"SESSION: {session}")
            print(f'NEXT: money-geta cut-video --job-dir "{line[5:]}" --pick 1')
            return 0
    print("FAIL: moments.py completed without returning a job directory.")
    return 1


def run_cut(args: argparse.Namespace) -> int:
    gtavi_dir = args.gtavi_dir.expanduser().resolve()
    script = gtavi_dir / "scripts/cut.py"
    job_dir = args.job_dir.expanduser().resolve()
    if not script.is_file() or not (job_dir / "candidates.json").is_file() or not (job_dir / "transcript.json").is_file():
        print("INCOMPLETE: cut.py, candidates.json or transcript.json is missing.")
        return 2
    if not shutil.which("ffmpeg"):
        print("INCOMPLETE: ffmpeg must be available on PATH for clip rendering.")
        return 2
    try:
        python_exe = resolve_gtavi_python(gtavi_dir, args.gtavi_python)
    except FileNotFoundError as exc:
        print(f"INCOMPLETE: {exc}")
        return 2
    command = [
        str(python_exe), str(script), str(job_dir),
        "--pick", str(args.pick), "--layout", args.layout,
        "--captions", args.captions,
    ]
    if args.hook:
        command += ["--hook", args.hook]
    completed = subprocess.run(command, cwd=gtavi_dir, capture_output=True, text=True, check=False)
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip())
    if completed.returncode:
        print(f"FAIL: clip cutting exited {completed.returncode}")
        return completed.returncode
    output = next((Path(line.strip()) for line in reversed(completed.stdout.splitlines()) if line.strip().lower().endswith(".mp4")), None)
    if output is None or not output.is_file():
        print("FAIL: cut.py did not produce a verifiable MP4 path.")
        return 1
    print(f"CLIP: {output.resolve()}")
    return 0

def resolve_mpt_python(mpt_dir: Path, override: Path | None = None) -> Path:
    if override is not None:
        candidate = override.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"MoneyPrinterTurbo Python runtime not found: {candidate}")
        return candidate
    candidates = [
        mpt_dir / ".venv/Scripts/python.exe",
        mpt_dir / "venv/Scripts/python.exe",
        mpt_dir / "lib/python/python.exe",
        mpt_dir / ".venv/bin/python",
        mpt_dir / "venv/bin/python",
        mpt_dir / "lib/python/bin/python",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return Path(sys.executable).resolve()


def run_mpt(args: argparse.Namespace) -> int:
    mpt_dir = args.mpt_dir.expanduser().resolve()
    cli_file = mpt_dir / "cli.py"
    config_file = mpt_dir / "config.toml"
    try:
        mpt_python = resolve_mpt_python(mpt_dir, args.mpt_python)
    except FileNotFoundError as exc:
        print(f"INCOMPLETE: {exc}")
        return 2
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

    help_result = subprocess.run(
        [str(mpt_python), str(cli_file), "--help"],
        cwd=mpt_dir, capture_output=True, text=True, check=False,
    )
    if help_result.returncode != 0:
        print("FAIL: MoneyPrinterTurbo CLI help could not be executed.")
        if help_result.stderr:
            print(help_result.stderr.strip())
        return 2
    required_flags = (
        "--video-subject", "--video-source", "--video-materials",
        "--video-aspect", "--video-count", "--stop-at",
    )
    missing_flags = [flag for flag in required_flags if flag not in help_result.stdout]
    if missing_flags:
        print("INCOMPATIBLE: installed MoneyPrinterTurbo CLI is missing required flags: " + ", ".join(missing_flags))
        return 2

    command = [
        str(mpt_python), str(cli_file),
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
    analyze = sub.add_parser("analyze-video", help="find candidate moments in a local VOD/video")
    analyze.add_argument("--gtavi-dir", type=Path, default=env_path("GTAVI_CLAUDECODE_DIR"))
    analyze.add_argument("--gtavi-python", type=Path, default=env_path("GTAVI_CLAUDECODE_PYTHON"))
    analyze.add_argument("--source", type=Path, required=True)
    analyze.add_argument("--jobs-root", type=Path, default=Path(os.environ.get("MONEY_GETA_JOBS_DIR", "jobs")))
    analyze.add_argument("--top", type=int, choices=range(1, 31), default=8)
    analyze.add_argument("--min-seconds", type=float, default=15)
    analyze.add_argument("--max-seconds", type=float, default=40)
    cut = sub.add_parser("cut-video", help="render one analyzed candidate as a vertical clip")
    cut.add_argument("--gtavi-dir", type=Path, default=env_path("GTAVI_CLAUDECODE_DIR"))
    cut.add_argument("--gtavi-python", type=Path, default=env_path("GTAVI_CLAUDECODE_PYTHON"))
    cut.add_argument("--job-dir", type=Path, required=True)
    cut.add_argument("--pick", type=int, default=1)
    cut.add_argument("--layout", choices=["fill", "blur", "facecam", "react"], default="blur")
    cut.add_argument("--captions", choices=["word", "bubble", "none"], default="word")
    cut.add_argument("--hook", default="")
    render = sub.add_parser("render", help="run MoneyPrinterTurbo with a gated campaign and local media")
    render.add_argument("--mpt-dir", type=Path, default=env_path("MONEYPRINTERTURBO_DIR"))
    render.add_argument("--mpt-python", type=Path, default=env_path("MONEYPRINTERTURBO_PYTHON"))
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
    if args.command == "analyze-video":
        if args.gtavi_dir is None:
            print("INCOMPLETE: set GTAVI_CLAUDECODE_DIR or pass --gtavi-dir")
            return 2
        if args.max_seconds <= args.min_seconds or args.min_seconds <= 0:
            print("FAIL: max-seconds must be greater than a positive min-seconds value.")
            return 2
        return run_moments(args)
    if args.command == "cut-video":
        if args.gtavi_dir is None:
            print("INCOMPLETE: set GTAVI_CLAUDECODE_DIR or pass --gtavi-dir")
            return 2
        return run_cut(args)
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
