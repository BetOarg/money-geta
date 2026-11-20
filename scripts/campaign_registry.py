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
        "profile_id": project["profile_id"], "factual_claims_required": project["profile_id"] in {"news", "education"}, "campaign_name": clean_name,
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

def update_campaign(project_id: str, campaign_id: str, *, sources: list[str] | None = None,
                    rights_evidence: list[str] | None = None,
                    disclosures: list[str] | None = None, credits: list[str] | None = None,
                    confirm_permissions: bool = False, confirm_credits: bool = False,
                    no_credits_required: bool = False, root: Path | None = None) -> Path:
    """Append operator-supplied evidence and explicit attestations; never approve or publish."""
    from datetime import datetime, timezone
    import os

    payload = get_campaign(project_id, campaign_id, root)
    sources = sources or []
    rights_evidence = rights_evidence or []
    disclosures = disclosures or []
    credits = credits or []
    if len(sources) != len(rights_evidence):
        raise ValueError("Each new source must have exactly one rights-evidence reference")
    if no_credits_required and credits:
        raise ValueError("Cannot declare no credits required while adding credit records")
    now = datetime.now(timezone.utc).isoformat()
    existing_sources = payload.setdefault("sources", [])
    ledger = payload.setdefault("rights_ledger", [])
    evidence_items = payload.setdefault("source_evidence", [])
    for source, evidence in zip(sources, rights_evidence):
        source, evidence = source.strip(), evidence.strip()
        if not source or not evidence:
            raise ValueError("Source and rights-evidence references cannot be empty")
        if source in existing_sources:
            raise ValueError(f"Source already exists: {source}")
        existing_sources.append(source)
        evidence_items.append({"source": source, "reference": source, "recorded_at": now})
        ledger.append({"source": source, "evidence": evidence, "status": "operator_attested", "attested_at": now})
    disclosure_list = payload.setdefault("required_disclosures", [])
    for disclosure in disclosures:
        value = disclosure.strip()
        if value and value not in disclosure_list:
            disclosure_list.append(value)
    credit_list = payload.setdefault("credit_records", [])
    for credit in credits:
        value = credit.strip()
        if value and value not in credit_list:
            credit_list.append(value)
    if confirm_permissions:
        if not existing_sources or len(ledger) != len(existing_sources) or any(
            not isinstance(item, dict) or not item.get("evidence") or item.get("status") != "operator_attested"
            for item in ledger
        ):
            raise ValueError("Cannot confirm permissions: every source needs an operator-supplied rights-evidence reference")
        payload["permissions_confirmed"] = True
        payload["permission_attestation"] = {
            "confirmed": True, "actor": "operator", "confirmed_at": now,
            "source_count": len(existing_sources),
        }
    if confirm_credits:
        if not credit_list and not no_credits_required:
            raise ValueError("Provide --credit or explicitly declare --no-credits-required")
        payload["credits_confirmed"] = True
        payload["credit_attestation"] = {
            "confirmed": True, "actor": "operator", "confirmed_at": now,
            "no_credits_required": no_credits_required, "credit_count": len(credit_list),
        }
    if not (sources or disclosures or credits or confirm_permissions or confirm_credits):
        raise ValueError("No campaign updates supplied")
    payload["updated_at"] = now
    target = (root or default_projects_root()).expanduser().resolve() / project_id / "campaigns" / campaign_id / "campaign.json"
    temp = target.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp, target)
    return target
