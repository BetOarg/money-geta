# Local media pipeline

Money-Geta can inspect, scene-detect, transcribe and subtitle-burn local media. Processing
is local; these commands do not upload media or automatically publish results.

## Optional installation

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[media]"
```

The media extra installs faster-whisper and PySceneDetect. FFmpeg and FFprobe must be
installed separately and available on PATH. For NVIDIA acceleration, install a compatible
CUDA/cuDNN runtime and validate it locally before selecting `--device cuda`.

## Commands

```powershell
money-geta media inspect --source "C:\Videos\gameplay.mp4"
money-geta media scenes --source "C:\Videos\gameplay.mp4" --output-dir ".\jobs\scenes"
money-geta media transcribe --source "C:\Videos\gameplay.mp4" --output-dir ".\jobs\captions" --model small
money-geta media burn-subtitles --source "C:\Videos\gameplay.mp4" --subtitles ".\jobs\captions\gameplay.srt" --output ".\jobs\gameplay-captioned.mp4"
```

Transcription creates SRT, VTT and a JSON sidecar. Scene detection produces a CSV. Review
candidate boundaries and subtitle text before publication. Model downloads may require
internet access on first use; inference is local after model availability.

## Deliberate exclusions

This first integration does not automatically download from YouTube/Twitch, record a stream,
infer ownership rights, select a viral moment, crop around a moving subject, or publish.
Those need separate source-specific permission checks, evaluation and human review.
