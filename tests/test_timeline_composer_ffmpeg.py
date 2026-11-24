"""Real FFmpeg end-to-end preview render (synthetic fixtures; no external media)."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from scripts.timeline_composer import compose_preview

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="FFmpeg and FFprobe are required")

def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True, timeout=90)

def make_clip(path: Path, color: str) -> None:
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", f"color=c={color}:s=160x90:r=24:d=1.5", "-an", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", str(path)])

def test_real_ffmpeg_preview_transition_and_audio_mix(tmp_path: Path) -> None:
    """Render synthetic clips, dissolve, and soundtrack; probe final streams/duration."""
    first, second, music, output = (tmp_path / "red.mp4", tmp_path / "blue.mp4",
                                   tmp_path / "tone.wav", tmp_path / "rendered-preview.mp4")
    make_clip(first, "red")
    make_clip(second, "blue")
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:sample_rate=48000:duration=3", "-c:a", "pcm_s16le", str(music)])
    draft = {
        "plan_type": "editable_timeline", "render_authorized": False, "publishing_authorized": False,
        "scenes": [
            {"scene_id": "synthetic-1", "duration_seconds": 1.5, "visual_path": str(first),
             "subtitle_text": "", "transition_in": "cut", "transition_duration_seconds": 0},
            {"scene_id": "synthetic-2", "duration_seconds": 1.5, "visual_path": str(second),
             "subtitle_text": "", "transition_in": "dissolve", "transition_duration_seconds": 0.3},
        ],
        "audio_tracks": [{"name": "Synthetic tone", "source_path": str(music), "start_seconds": 0,
                          "duration_seconds": 3, "volume": 0.35, "fade_in_seconds": 0.1,
                          "fade_out_seconds": 0.1}],
    }
    rendered = compose_preview(draft, output, ffmpeg=FFMPEG, width=160, height=90, fps=24, timeout=90)
    assert rendered.is_file() and rendered.stat().st_size > 5_000
    probe = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                 "-show_entries", "stream=codec_type,width,height", "-of", "json", str(output)])
    metadata = json.loads(probe.stdout)
    types = [s["codec_type"] for s in metadata["streams"]]
    assert "video" in types and "audio" in types
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (160, 90)
    assert float(metadata["format"]["duration"]) == pytest.approx(2.7, abs=0.25)
