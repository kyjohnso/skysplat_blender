"""Create animated cameras from a COLMAP model.

Phase 1 stub — full extraction deferred to phase 1.5. The existing
operator at ui/colmap_panel.py continues to work unchanged.
"""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


def create_animated_cameras(
    scene,
    model_path: Path,
    instance_name: str,
    video_strip_starts: dict,
):
    """Create one animated camera per source video.

    Phase 1 stub — see task D4 in the implementation plan.
    """
    raise NotImplementedError("Deferred to phase 1.5; see plan task D4.")
