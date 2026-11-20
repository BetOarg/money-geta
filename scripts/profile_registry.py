"""Load and validate Money-Geta's declarative content-profile registry."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "profiles" / "manifest.json"
ALLOWED_STATUS = {"partial", "planned", "ready", "blocked"}

def load_profiles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    registry_path = path or DEFAULT_REGISTRY
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load profile registry {registry_path}: {exc}") from exc
    if payload.get("schema_version") != 1 or not isinstance(payload.get("profiles"), list):
        raise ValueError("Unsupported or malformed profile registry schema")
    profiles: dict[str, dict[str, Any]] = {}
    for item in payload["profiles"]:
        if not isinstance(item, dict):
            raise ValueError("Each profile must be an object")
        profile_id = item.get("id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Every profile requires a non-empty id")
        if profile_id in profiles:
            raise ValueError(f"Duplicate profile id: {profile_id}")
        if item.get("status") not in ALLOWED_STATUS:
            raise ValueError(f"Invalid status for profile {profile_id}")
        for field in ("name", "capabilities", "rules"):
            if field not in item:
                raise ValueError(f"Profile {profile_id} is missing {field}")
        if not isinstance(item["capabilities"], list) or not all(isinstance(v, str) for v in item["capabilities"]):
            raise ValueError(f"Profile {profile_id} capabilities must be a list of strings")
        if not isinstance(item["rules"], list) or not all(isinstance(v, str) for v in item["rules"]):
            raise ValueError(f"Profile {profile_id} rules must be a list of strings")
        profiles[profile_id] = item
    return profiles

def list_profiles(path: Path | None = None) -> list[dict[str, Any]]:
    return list(load_profiles(path).values())

def get_profile(profile_id: str, path: Path | None = None) -> dict[str, Any]:
    profiles = load_profiles(path)
    try:
        return profiles[profile_id]
    except KeyError as exc:
        raise KeyError(f"Unknown profile: {profile_id}") from exc
