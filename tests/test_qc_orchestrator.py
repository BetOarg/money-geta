import hashlib,json
from pathlib import Path
import pytest
from scripts.qc_orchestrator import evaluate
def hash_file(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_video_report(path,target,data):
 data["file"]=str(target.resolve()); data["sha256"]=hash_file(target); path.write_text(json.dumps(data),encoding="utf-8")
def write_sub_report(path,subtitle,data):
 data["file"]=str(subtitle.resolve()); data["sha256"]=hash_file(subtitle); path.write_text(json.dumps(data),encoding="utf-8")
def test_ready_when_technical_passes_optional_absent(tmp_path):
 artifact=tmp_path/"render.mp4"; artifact.write_bytes(b"video")
 technical=tmp_path/"technical.json"; write_video_report(technical,artifact,{"schema_version":1,"passed":True,"problems":[]})
 result=evaluate(artifact,technical_report=technical)
 assert result["status"]=="READY_FOR_HUMAN_REVIEW" and result["sha256"]
def test_failed_technical_blocks(tmp_path):
 artifact=tmp_path/"render.mp4"; artifact.write_bytes(b"video")
 technical=tmp_path/"technical.json"; write_video_report(technical,artifact,{"schema_version":1,"passed":False,"problems":["no audio"]})
 assert evaluate(artifact,technical_report=technical)["status"]=="FAILED"
def test_perceptual_alert_review_not_fail(tmp_path):
 artifact=tmp_path/"render.mp4"; artifact.write_bytes(b"video")
 technical=tmp_path/"technical.json"; perceptual=tmp_path/"perceptual.json"
 write_video_report(technical,artifact,{"schema_version":1,"passed":True,"problems":[]})
 write_video_report(perceptual,artifact,{"schema_version":1,"observations":{"black_segments":[{"duration":2}]}})
 result=evaluate(artifact,technical_report=technical,perceptual_report=perceptual)
 assert result["status"]=="REVIEW_REQUIRED" and result["blocking"]==[]
def test_missing_required_subtitles_blocks(tmp_path):
 artifact=tmp_path/"render.mp4"; artifact.write_bytes(b"video")
 technical=tmp_path/"technical.json"; write_video_report(technical,artifact,{"schema_version":1,"passed":True,"problems":[]})
 assert evaluate(artifact,technical_report=technical,subtitle_required=True)["status"]=="FAILED"
def test_wrong_target_report_rejected(tmp_path):
 artifact=tmp_path/"render.mp4"; other=tmp_path/"other.mp4"; artifact.write_bytes(b"video"); other.write_bytes(b"other")
 technical=tmp_path/"technical.json"; write_video_report(technical,other,{"schema_version":1,"passed":True,"problems":[]})
 with pytest.raises(ValueError,match="target path mismatch"): evaluate(artifact,technical_report=technical)
def test_stale_video_report_hash_rejected(tmp_path):
 artifact=tmp_path/"render.mp4"; artifact.write_bytes(b"video")
 technical=tmp_path/"technical.json"; write_video_report(technical,artifact,{"schema_version":1,"passed":True,"problems":[]})
 artifact.write_bytes(b"changed")
 with pytest.raises(ValueError,match="hash does not match"): evaluate(artifact,technical_report=technical)
def test_subtitle_report_hash_is_verified(tmp_path):
 artifact=tmp_path/"render.mp4"; artifact.write_bytes(b"video")
 subtitle=tmp_path/"subs.srt"; subtitle.write_text("caption")
 technical=tmp_path/"technical.json"; subsreport=tmp_path/"subs.json"
 write_video_report(technical,artifact,{"schema_version":1,"passed":True,"problems":[]})
 write_sub_report(subsreport,subtitle,{"schema_version":1,"passed":True,"cue_count":1,"problems":[]})
 assert evaluate(artifact,technical_report=technical,subtitle_report=subsreport)["status"]=="READY_FOR_HUMAN_REVIEW"
 subtitle.write_text("changed")
 with pytest.raises(ValueError,match="Subtitle QC hash"): evaluate(artifact,technical_report=technical,subtitle_report=subsreport)
