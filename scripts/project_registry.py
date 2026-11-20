"""Persistent local project registry for Money-Geta."""
from __future__ import annotations
import json, os, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from scripts.profile_registry import get_profile

def default_projects_root() -> Path:
    configured = os.environ.get("MONEY_GETA_PROJECTS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Money-Geta" / "projects"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "money-geta" / "projects"

def safe_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not slug:
        raise ValueError("Name must contain at least one letter or number")
    return slug[:64].rstrip("-")

def _read_project(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read project manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"Unsupported or malformed project manifest: {path}")
    if not isinstance(data.get("project_id"), str) or not isinstance(data.get("name"), str):
        raise ValueError(f"Project manifest is missing identity fields: {path}")
    return data

def create_project(name: str, profile_id: str, *, topic: str = "", brief: str = "", root: Path | None = None) -> Path:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Project name cannot be empty")
    profile = get_profile(profile_id)
    project_id = safe_slug(clean_name)
    projects_root = (root or default_projects_root()).expanduser().resolve()
    project_dir = projects_root / project_id
    project_dir.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1, "project_id": project_id, "name": clean_name,
        "profile_id": profile_id, "profile_name": profile["name"],
        "topic": topic.strip(), "brief": brief.strip(), "status": "draft",
        "created_at": now, "updated_at": now, "campaigns": [],
        "workspace": {"preserve_inputs": True, "never_overwrite": True},
    }
    try:
        target = project_dir / "project.json"
        with target.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        try: project_dir.rmdir()
        except OSError: pass
        raise
    return target

def get_project(project_id: str, root: Path | None = None) -> dict[str, Any]:
    normalized = safe_slug(project_id)
    if normalized != project_id:
        raise ValueError("Project ID must be a normalized project slug")
    path = (root or default_projects_root()).expanduser().resolve() / normalized / "project.json"
    return _read_project(path)

def list_projects(root: Path | None = None) -> list[dict[str, Any]]:
    projects_root = (root or default_projects_root()).expanduser().resolve()
    if not projects_root.is_dir(): return []
    return [_read_project(path) for path in sorted(projects_root.glob("*/project.json"))]
