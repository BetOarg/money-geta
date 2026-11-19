"""Safe session directory creation; never cleans or overwrites prior session data."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


def safe_job_id(value: str) -> str:
    """Normalize an external job identifier to a single safe path component."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("job_id must contain at least one safe character")
    return cleaned[:80]


def create_session_dir(root: str | Path, job_id: str) -> Path:
    """Create a unique UTC session folder; fail rather than reuse an existing folder."""
    base = Path(root).expanduser().resolve()
    safe_id = safe_job_id(job_id)
    sessions = base / safe_id / "live"
    sessions.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    # UUID prevents collisions when two sessions start in the same microsecond.
    for _ in range(5):
        candidate = sessions / f"session-{stamp}-{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir(mode=0o700)
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError("Could not allocate a unique session directory")
