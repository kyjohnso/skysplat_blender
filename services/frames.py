"""Frame extraction and frame-folder utilities.

Pure parts (this stage): discover_frames.
Scene parts (Stage D): extract_frames — uses bpy.ops.render.opengl.
"""
from __future__ import annotations

from pathlib import Path

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def discover_frames(image_dir: Path) -> list[Path]:
    """Return a sorted list of image files in image_dir.

    Filters by extension (.jpg, .jpeg, .png — case-insensitive).
    Raises FileNotFoundError if image_dir does not exist.
    """
    image_dir = Path(image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(f"Frames directory does not exist: {image_dir}")
    return sorted(
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )
