"""Conservative capability audit for declared content profiles."""
from __future__ import annotations

from typing import Any

# Evidence-backed implementation inventory. "partial" means the capability exists,
# but it is not yet end-to-end for every profile or production scenario.
CAPABILITY_STATUS: dict[str, str] = {
    "research": "partial",
    "trend-radar": "partial",
    "source-verification": "partial",
    "claim-check": "partial",
    "scriptwriting": "partial",
    "moment-detection": "partial",
    "clip-editing": "partial",
    "subtitles": "partial",
    "render": "partial",
    "quality-control": "partial",
    "rights-check": "partial",
    "outline": "partial",
    "illustration": "planned",
    "translation": "planned",
}

PROFILE_LIMITS = {
    "gaming": {"moment-detection", "clip-editing"},
}


def audit_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return capability support and gaps; never infer a profile is production-ready."""
    report = []
    for profile in profiles:
        profile_id = profile.get("id")
        declared = profile.get("capabilities", [])
        details = []
        unknown = []
        for capability in declared:
            status = CAPABILITY_STATUS.get(capability, "unknown")
            if status == "unknown":
                unknown.append(capability)
            if profile_id in PROFILE_LIMITS and capability in PROFILE_LIMITS[profile_id]:
                status = "partial"
                note = "disponible solo para subperfil GTA VI; no generalizado a todos los juegos"
            else:
                note = ""
            details.append({"capability": capability, "status": status, "note": note})
        unsupported = [item["capability"] for item in details if item["status"] in {"planned", "unknown"}]
        overall = "ready" if profile.get("status") == "ready" and not unsupported and all(
            item["status"] == "available" for item in details
        ) else "partial" if any(item["status"] == "partial" for item in details) else "planned"
        report.append({
            "profile": profile_id,
            "declared_status": profile.get("status"),
            "audit_status": overall,
            "capabilities": details,
            "gaps": unsupported,
            "unknown_capabilities": unknown,
        })
    return report
