"""Consolidate QC reports, enforcing source hashes and exact artifact identity."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
def sha256(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()
def _load_json(path:Path)->dict[str,Any]:
    data=json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("schema_version")!=1: raise ValueError(f"Unsupported or malformed QC report: {path}")
    return data
def _video_report(path:Path,artifact:Path,artifact_hash:str)->dict[str,Any]:
    data=_load_json(path)
    if Path(str(data.get("file",""))).expanduser().resolve()!=artifact: raise ValueError(f"QC report target path mismatch: {path}")
    if data.get("sha256")!=artifact_hash: raise ValueError(f"QC report hash does not match current video: {path}")
    return data
def _subtitle_report(path:Path)->dict[str,Any]:
    data=_load_json(path); source=Path(str(data.get("file",""))).expanduser().resolve(strict=True)
    if not source.is_file(): raise ValueError("Subtitle source is not a regular file")
    if data.get("sha256")!=sha256(source): raise ValueError("Subtitle QC hash does not match current subtitle file")
    return data
def evaluate(artifact_path:Path,*,technical_report:Path|None,subtitle_report:Path|None=None,subtitle_required:bool=False,perceptual_report:Path|None=None)->dict[str,Any]:
    artifact=artifact_path.expanduser().resolve(strict=True)
    if not artifact.is_file(): raise ValueError("Artifact must be a regular file")
    artifact_hash=sha256(artifact); blocking=[]; review=[]; checks={}
    if technical_report is None: blocking.append("Technical QC report is required")
    else:
        technical=_video_report(technical_report,artifact,artifact_hash)
        checks["technical"]={"passed":technical.get("passed") is True,"problems":technical.get("problems",[])}
        if technical.get("passed") is not True: blocking.append("Technical QC did not pass")
    if subtitle_report is None:
        checks["subtitles"]={"status":"not_provided"}
        if subtitle_required: blocking.append("Subtitle QC report is required but missing")
    else:
        subs=_subtitle_report(subtitle_report)
        checks["subtitles"]={"passed":subs.get("passed") is True,"problems":subs.get("problems",[]),"cue_count":subs.get("cue_count"),"source_sha256":subs["sha256"]}
        if subs.get("passed") is not True:
            if subtitle_required: blocking.append("Subtitle QC did not pass")
            else: review.append("Subtitle QC has findings; review before approval")
    if perceptual_report is None: checks["perceptual"]={"status":"not_provided"}
    else:
        perceptual=_video_report(perceptual_report,artifact,artifact_hash)
        observations=perceptual.get("observations",{})
        if not isinstance(observations,dict): raise ValueError("Perceptual observations must be a JSON object")
        findings={key:value for key,value in observations.items() if value}
        checks["perceptual"]={"observations":findings}
        if findings: review.append("Perceptual observations require human review; they are not automatic defects")
    status="FAILED" if blocking else ("REVIEW_REQUIRED" if review else "READY_FOR_HUMAN_REVIEW")
    return {"schema_version":1,"artifact":str(artifact),"sha256":artifact_hash,"status":status,"blocking":blocking,"review":review,"checks":checks,
      "note":"Reports are hash-bound to their source files. This does not approve, publish, or schedule; human review and rights/platform checks remain mandatory."}
def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--file",type=Path,required=True)
    parser.add_argument("--technical-report",type=Path,required=True); parser.add_argument("--subtitle-report",type=Path)
    parser.add_argument("--subtitle-required",action="store_true"); parser.add_argument("--perceptual-report",type=Path); parser.add_argument("--report",type=Path)
    args=parser.parse_args(argv)
    try: result=evaluate(args.file,technical_report=args.technical_report,subtitle_report=args.subtitle_report,subtitle_required=args.subtitle_required,perceptual_report=args.perceptual_report)
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version":1,"status":"FAILED","blocking":[str(exc)]},indent=2)); return 2
    output=json.dumps(result,ensure_ascii=False,indent=2); print(output)
    if args.report: args.report.expanduser().parent.mkdir(parents=True,exist_ok=True); args.report.expanduser().write_text(output+"\n",encoding="utf-8")
    return 0 if result["status"]=="READY_FOR_HUMAN_REVIEW" else (1 if result["status"]=="REVIEW_REQUIRED" else 2)
if __name__=="__main__": raise SystemExit(main())
