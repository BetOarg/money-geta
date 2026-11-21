"""Safe resolver for local media previews in the timeline editor."""
from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def resolve_scene_preview_path(raw_path: str) -> tuple[Path | None, str]:
    """Resolve only existing local image/video files; never fetch remote paths."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "Esta escena no tiene recurso asignado."
    path = Path(raw_path).expanduser()
    try:
        if path.is_symlink():
            return None, "No se muestra un recurso que sea enlace simbólico."
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "El recurso local no existe o no se puede acceder."
    if not resolved.is_file():
        return None, "El recurso asignado no es un archivo."
    extension = resolved.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return resolved, "image"
    if extension in VIDEO_EXTENSIONS:
        return resolved, "video"
    return None, "Formato no compatible para preview."
