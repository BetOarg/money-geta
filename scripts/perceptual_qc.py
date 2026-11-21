"""Perceptual media observations via FFmpeg video/audio filters."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from pathlib import Path
BLACK_RE=re.compile(r"black_start:(-?\d+(?:\.\d+)?)\s+black_end:(-?\d+(?:\.\d+)?)\s+black_duration:(-?\d+(?:\.\d+)?)")
FREEZE_RE=re.compile(r"freeze_start:(-?\d+(?:\.\d+)?)\s+freeze_duration:(-?\d+(?:\.\d+)?)\s+freeze_end:(-?\d+(?:\.\d+)?)")
SILENCE_RE=re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
SILENCE_END_RE=re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(-?\d+(?:\.\d+)?)")
def analyze(path:Path,*,black_min:float=1.0,freeze_min:float=2.0,silence_min:float=3.0,timeout:int=120)->dict:
    source=path.expanduser().resolve()
    if not source.is_file(): raise ValueError(f"Input file does not exist: {source}")
    if timeout<1 or black_min<0 or freeze_min<0 or silence_min<0: raise ValueError("Thresholds must be non-negative and timeout positive")
    vf=f"blackdetect=d=0.10:pix_th=0.10:duration={black_min},freezedetect=n=-60dB:d={freeze_min}"
    af=f"silencedetect=n=-50dB:d={silence_min}"
    cmd=["ffmpeg","-hide_banner","-nostats","-i",str(source),"-vf",vf,"-af",af,"-f","null","-"]
    try: proc=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,check=False)
    except FileNotFoundError as exc: raise RuntimeError("FFmpeg executable not found") from exc
    except subprocess.TimeoutExpired as exc: raise RuntimeError(f"FFmpeg timed out after {timeout}s") from exc
    log=(proc.stderr or "")+"\n"+(proc.stdout or "")
    if proc.returncode!=0: raise RuntimeError(f"FFmpeg failed with exit code {proc.returncode}")
    black=[{"start":float(a),"end":float(b),"duration":float(c)} for a,b,c in BLACK_RE.findall(log)]
    freezes=[{"start":float(a),"duration":float(b),"end":float(c)} for a,b,c in FREEZE_RE.findall(log)]
    starts=[float(x) for x in SILENCE_RE.findall(log)]
    ends=[{"end":float(a),"duration":float(b)} for a,b in SILENCE_END_RE.findall(log)]
    digest=hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""): digest.update(chunk)
    return {"schema_version":1,"file":str(source),"sha256":digest.hexdigest(),"mode":"observational",
      "thresholds":{"black_min_seconds":black_min,"freeze_min_seconds":freeze_min,"silence_min_seconds":silence_min,
        "black_luma_threshold":0.10,"freeze_noise_threshold":"-60dB","silence_noise_threshold":"-50dB"},
      "observations":{"black_segments":black,"freeze_segments":freezes,"silence_starts":starts,"silence_segments_ended":ends},
      "note":"Observations are not defects by themselves; intentional black, stills, and silence may be valid."}
def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--file",required=True,type=Path)
    parser.add_argument("--black-min",type=float,default=1.0); parser.add_argument("--freeze-min",type=float,default=2.0)
    parser.add_argument("--silence-min",type=float,default=3.0); parser.add_argument("--timeout",type=int,default=120); parser.add_argument("--report",type=Path)
    args=parser.parse_args(argv)
    try: report=analyze(args.file,black_min=args.black_min,freeze_min=args.freeze_min,silence_min=args.silence_min,timeout=args.timeout)
    except (ValueError,RuntimeError) as exc: print(f"Perceptual QC error: {exc}"); return 2
    output=json.dumps(report,ensure_ascii=False,indent=2); print(output)
    if args.report: args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(output+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
