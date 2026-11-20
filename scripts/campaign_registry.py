"""Campaign registry; new campaigns start incomplete and cannot pass publication gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from scripts.project_registry import default_projects_root, get_project, safe_slug

def create_campaign(project_id: str, name: str, platform: str, *, root: Path | None = None) -> Path:
    clean_name, clean_platform = name.strip(), platform.strip()
    if not clean_name or not clean_platform:
        raise ValueError("Campaign name and platform are required")
    projects_root = (root or default_projects_root()).expanduser().resolve()
    project = get_project(project_id, projects_root)
    campaign_id = safe_slug(clean_name)
    campaign_dir = projects_root / project_id / "campaigns" / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 1, "campaign_id": campaign_id, "project_id": project_id,
        "profile_id": project["profile_id"], "campaign_name": clean_name,
        "platform": clean_platform, "status": "draft", "created_at": now, "updated_at": now,
        "sources": [], "source_evidence": [], "required_disclosures": [],
        "permissions_confirmed": False, "credits_confirmed": False,
        "rights_ledger": [], "credit_records": [],
        "review": {"status": "pending", "approved_artifact_hash": None},
        "distribution": {"mode": "draft_only", "human_approval_required": True},
    }
    target = campaign_dir / "campaign.json"
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        try: campaign_dir.rmdir()
        except OSError: pass
        raise
    return target

def _read_campaign(path: Path) -> dict[str, Any]:
    try: payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read campaign manifest {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError(f"Unsupported or malformed campaign manifest: {path}")
    required = ("campaign_id", "project_id", "profile_id", "campaign_name", "platform")
    if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in required):
        raise ValueError(f"Campaign manifest is missing identity fields: {path}")
    return payload

def get_campaign(project_id: str, campaign_id: str, root: Path | None = None) -> dict[str, Any]:
    if safe_slug(project_id) != project_id or safe_slug(campaign_id) != campaign_id:
        raise ValueError("Project and campaign IDs must be normalized slugs")
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    return _read_campaign(projects_root / project_id / "campaigns" / campaign_id / "campaign.json")

def list_campaigns(project_id: str, root: Path | None = None) -> list[dict[str, Any]]:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    get_project(project_id, projects_root)
    folder = projects_root / project_id / "campaigns"
    if not folder.is_dir(): return []
    return [_read_campaign(path) for path in sorted(folder.glob("*/campaign.json"))]
