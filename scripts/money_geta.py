"""Money-Geta operational control plane for the local GTA VI video workflow."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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



def write_manifest(session_dir: Path, **fields) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    manifest = session_dir / "money-geta.json"
    current = {}
    if manifest.exists():
        current = json.loads(manifest.read_text(encoding="utf-8"))
    current.update(fields)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    temp = manifest.with_suffix(".json.tmp")
    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(manifest)
    return manifest


def show_status(root: Path, limit: int = 20) -> int:
    root = root.expanduser().resolve()
    if not root.is_dir():
        print(f"INCOMPLETE: jobs directory does not exist: {root}")
        return 2
    manifests = sorted(
        root.rglob("money-geta.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )[:limit]
    if not manifests:
        print(f"No Money-Geta runs recorded in {root}")
        return 0
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print(f"WARNING: unreadable run manifest: {manifest}")
            continue
        label = data.get("subject") or data.get("source") or data.get("source_url") or "untitled"
        print(f"{data.get('updated_at', 'unknown')} | {data.get('stage', 'unknown')} | {label} | {manifest.parent}")
    return 0

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

    if mpt_dir and (mpt_dir / "cli.py").is_file():
        try:
            mpt_python = resolve_mpt_python(mpt_dir, env_path("MONEYPRINTERTURBO_PYTHON"))
            help_result = subprocess.run(
                [str(mpt_python), str(mpt_dir / "cli.py"), "--help"],
                cwd=mpt_dir, capture_output=True, text=True, check=False,
            )
            required = ("--video-subject", "--video-source", "--video-materials", "--video-count", "--stop-at")
            ok = help_result.returncode == 0 and all(flag in help_result.stdout for flag in required)
            detail = str(mpt_python) if ok else (help_result.stderr.strip() or "CLI contract check failed")
        except (OSError, FileNotFoundError) as exc:
            ok, detail = False, str(exc)
        print(f"{'PASS' if ok else 'PENDING'} MoneyPrinterTurbo CLI: {detail}")
        checks.append(("MoneyPrinterTurbo CLI", ok, detail))

    gtavi_dir = env_path("GTAVI_CLAUDECODE_DIR")
    if gtavi_dir and (gtavi_dir / "scripts/moments.py").is_file():
        try:
            gtavi_python = resolve_gtavi_python(gtavi_dir, env_path("GTAVI_CLAUDECODE_PYTHON"))
            dependency = subprocess.run(
                [str(gtavi_python), "-c", "import numpy, faster_whisper"],
                cwd=gtavi_dir, capture_output=True, text=True, check=False,
            )
            ok = dependency.returncode == 0
            detail = str(gtavi_python) if ok else (dependency.stderr.strip() or "numpy/faster-whisper unavailable")
        except (OSError, FileNotFoundError) as exc:
            ok, detail = False, str(exc)
        print(f"{'PASS' if ok else 'PENDING'} GTA VI analysis runtime: {detail}")
        checks.append(("GTA VI analysis runtime", ok, detail))

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



def run_live(args: argparse.Namespace) -> int:
    gtavi_dir = args.gtavi_dir.expanduser().resolve()
    script = gtavi_dir / "scripts/live.py"
    patch = ROOT / "patches/gtavi-claudecode/live-session-isolation.patch"
    if not script.is_file() or not patch.is_file():
        print("INCOMPLETE: live.py or the verified session-isolation patch is missing.")
        return 2
    if not args.confirm_recording:
        print("BLOCKED: recording requires explicit --confirm-recording.")
        return 2
    git = shutil.which("git")
    if not git or not (gtavi_dir / ".git").exists():
        print("INCOMPLETE: use a Git checkout of GTA VI ClaudeCode to verify the safety patch.")
        return 2
    reverse = subprocess.run(
        [git, "apply", "--reverse", "--check", str(patch)],
        cwd=gtavi_dir, capture_output=True, text=True, check=False,
    )
    if reverse.returncode:
        print("BLOCKED: live-session safety patch is not applied. Run money-geta upstream-check --apply first.")
        return 2
    missing_tools = [name for name in ("ffmpeg",) if not shutil.which(name)]
    if missing_tools:
        print("INCOMPLETE: live recording requires on-PATH tools: " + ", ".join(missing_tools))
        return 2
    try:
        python_exe = resolve_gtavi_python(gtavi_dir, args.gtavi_python)
    except FileNotFoundError as exc:
        print(f"INCOMPLETE: {exc}")
        return 2
    session = create_session_dir(args.jobs_root, "live-recording")
    write_manifest(session, stage="recording", source_url=args.url.split("?")[0], requested_minutes=args.minutes)
    env = os.environ.copy()
    env["CLIP_DESK_HOME"] = str(session)
    command = [
        str(python_exe), str(script), args.url,
        "--minutes", str(args.minutes),
        "--before", str(args.before), "--after", str(args.after),
        "--window", str(args.window), "--ratio", str(args.ratio),
        "--min-msgs", str(args.min_msgs), "--lag", str(args.lag),
        "--cooldown", str(args.cooldown),
    ]
    print("RECORDING: explicit operator confirmation received; unique session isolation verified.")
    result = subprocess.run(command, cwd=gtavi_dir, env=env, check=False)
    write_manifest(session, stage="recorded" if result.returncode == 0 else "recording_failed", exit_code=result.returncode)
    print(f"SESSION: {session}")
    return result.returncode

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

    dependency_check = subprocess.run(
        [str(python_exe), "-c", "import numpy, faster_whisper"],
        cwd=gtavi_dir, capture_output=True, text=True, check=False,
    )
    if dependency_check.returncode:
        print("INCOMPLETE: GTA VI Python environment needs numpy and faster-whisper.")
        if dependency_check.stderr:
            print(dependency_check.stderr.strip())
        return 2

    root = args.jobs_root.expanduser().resolve()
    session = create_session_dir(root, f"analysis-{source.stem}")
    write_manifest(session, stage="analyzing", source_path=str(source), requested_top=args.top,
                   min_seconds=args.min_seconds, max_seconds=args.max_seconds)
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
        write_manifest(session, stage="analysis_failed", exit_code=completed.returncode)
        print(f"FAIL: moments analysis exited {completed.returncode}")
        return completed.returncode
    for line in completed.stdout.splitlines():
        if line.startswith("job: "):
            job_path = Path(line[5:]).resolve()
            try:
                candidate_count = len(json.loads((job_path / "candidates.json").read_text(encoding="utf-8")).get("candidates", []))
            except (OSError, json.JSONDecodeError):
                candidate_count = None
            write_manifest(session, stage="analyzed", job_dir=str(job_path), candidate_count=candidate_count)
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
    try:
        candidates = json.loads((job_dir / "candidates.json").read_text(encoding="utf-8")).get("candidates", [])
    except (OSError, json.JSONDecodeError):
        print("FAIL: candidates.json is unreadable.")
        return 2
    if not any(item.get("n") == args.pick for item in candidates):
        print(f"FAIL: candidate {args.pick} does not exist in {job_dir}.")
        return 2
    required_tools = ["ffmpeg"] + (["ffprobe"] if args.layout in {"facecam", "react"} else [])
    missing_tools = [name for name in required_tools if not shutil.which(name)]
    if missing_tools:
        print("INCOMPLETE: clip rendering requires on-PATH tools: " + ", ".join(missing_tools))
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
    session_dir = job_dir.parent.parent
    write_manifest(session_dir, stage="clip_ready", job_dir=str(job_dir), selected_candidate=args.pick,
                   layout=args.layout, clip_path=str(output.resolve()))
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
    try:
        config_text = config_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: cannot read MoneyPrinterTurbo config.toml: {exc}")
        return 2
    if re.search(r"(?im)^\s*upload_post_auto_upload\s*=\s*true\s*(?:#.*)?$", config_text):
        print("BLOCKED: MoneyPrinterTurbo automatic cross-platform publishing is enabled. Set upload_post_auto_upload = false before using Money-Geta render.")
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
    session = create_session_dir(args.jobs_root, f"render-{args.subject[:32]}")
    write_manifest(session, stage="rendering", subject=args.subject, campaign_path=str(args.campaign.resolve()),
                   input_media=[str(item) for item in materials], aspect=args.aspect, count=args.count,
                   engine="MoneyPrinterTurbo")
    print("Starting MoneyPrinterTurbo local-media pipeline...")
    completed = subprocess.run(command, cwd=mpt_dir, capture_output=True, text=True, check=False)
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip())
    if completed.returncode:
        write_manifest(session, stage="render_failed", exit_code=completed.returncode)
        print(f"MoneyPrinterTurbo exit code: {completed.returncode}")
        print(f"SESSION: {session}")
        return completed.returncode
    try:
        payload = json.loads(completed.stdout)
        videos = payload.get("result", {}).get("videos", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        write_manifest(session, stage="render_failed", failure="invalid task JSON")
        print("FAIL: MoneyPrinterTurbo returned no verifiable JSON task result.")
        print(f"SESSION: {session}")
        return 1
    if not videos:
        write_manifest(session, stage="render_failed", failure="no final video paths")
        print("FAIL: MoneyPrinterTurbo reported success without final video paths.")
        print(f"SESSION: {session}")
        return 1
    for item in videos:
        video = Path(item)
        if not video.is_absolute():
            video = mpt_dir / video
        if not video.is_file():
            write_manifest(session, stage="render_failed", failure=f"missing artifact: {video}")
            print(f"FAIL: MoneyPrinterTurbo reported a missing video artifact: {video}")
            print(f"SESSION: {session}")
            return 1
        print(f"VIDEO: {video.resolve()}")
    write_manifest(session, stage="rendered", mpt_task_id=payload.get("task_id"),
                   output_videos=[str((Path(item) if Path(item).is_absolute() else mpt_dir / item).resolve()) for item in videos])
    print(f"VERIFIED: {len(videos)} final video file(s) exist.")
    print(f"SESSION: {session}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="money-geta", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check local tools and configured upstream installations")
    status = sub.add_parser("status", help="list recent Money-Geta workflow sessions")
    status.add_argument("--jobs-root", type=Path, default=Path(os.environ.get("MONEY_GETA_JOBS_DIR", "jobs")))
    status.add_argument("--limit", type=int, choices=range(1, 101), default=20)
    session = sub.add_parser("new-session", help="allocate a unique, non-destructive recording workspace")
    session.add_argument("job_id")
    session.add_argument("--root", type=Path, default=Path(os.environ.get("MONEY_GETA_JOBS_DIR", "jobs")))
    campaign = sub.add_parser("campaign-check", help="validate campaign evidence fields (not legal clearance)")
    campaign.add_argument("--campaign", type=Path, required=True)
    live = sub.add_parser("record-live", help="record a live source after explicit confirmation")
    live.add_argument("--gtavi-dir", type=Path, default=env_path("GTAVI_CLAUDECODE_DIR"))
    live.add_argument("--gtavi-python", type=Path, default=env_path("GTAVI_CLAUDECODE_PYTHON"))
    live.add_argument("--jobs-root", type=Path, default=Path(os.environ.get("MONEY_GETA_JOBS_DIR", "jobs")))
    live.add_argument("--url", required=True)
    live.add_argument("--minutes", type=int, choices=range(1, 721), default=60)
    live.add_argument("--before", type=int, default=15)
    live.add_argument("--after", type=int, default=20)
    live.add_argument("--window", type=int, default=10)
    live.add_argument("--ratio", type=float, default=3)
    live.add_argument("--min-msgs", type=int, default=8)
    live.add_argument("--lag", type=float, default=8)
    live.add_argument("--cooldown", type=float, default=45)
    live.add_argument("--confirm-recording", action="store_true", help="confirm you have permission to record this stream")
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
    render.add_argument("--jobs-root", type=Path, default=Path(os.environ.get("MONEY_GETA_JOBS_DIR", "jobs")))
    media = sub.add_parser("media", help="inspect, detect scenes, transcribe and subtitle local media")
    media.add_argument("media_args", nargs=argparse.REMAINDER)
    upstream = sub.add_parser("upstream-check", help="verify pinned upstream blobs and patch applicability")
    upstream.add_argument("--path", type=Path, default=env_path("GTAVI_CLAUDECODE_DIR"))
    upstream.add_argument("--apply", action="store_true", help="apply patches after all per-file checks; use on a clean clone")
    args = parser.parse_args(argv)

    if args.command == "media":
        from scripts.media_pipeline import main as media_main
        return media_main(args.media_args)
    if args.command == "doctor":
        return doctor()
    if args.command == "status":
        return show_status(args.jobs_root, args.limit)
    if args.command == "new-session":
        path = create_session_dir(args.root, args.job_id)
        write_manifest(path, stage="created", job_id=args.job_id)
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
    if args.command == "record-live":
        if args.gtavi_dir is None:
            print("INCOMPLETE: set GTAVI_CLAUDECODE_DIR or pass --gtavi-dir")
            return 2
        return run_live(args)
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
