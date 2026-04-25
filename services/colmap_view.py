"""Import a COLMAP model into the Blender scene as a viewable point cloud
plus a COLMAP_Root empty.

Phase 1 takes the existing load logic verbatim; phase 2 will tag scene
objects with skysplat_node_uuid for the round-trip pattern. This phase
preserves the existing tagging convention used by sidebar instances.
"""
from __future__ import annotations

import math
from pathlib import Path

try:
    import bpy
    import mathutils
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from .colmap import read_model, ColmapModel


def import_model_to_scene(
    scene,
    model_path: Path,
    instance_name: str,
):
    """Import a COLMAP sparse model into the scene.

    Creates:
      - Collection 'COLMAP_<instance_name>' (or adopts existing)
      - Empty 'COLMAP_Root' parented to a points mesh
      - Point cloud mesh with each 3D point as a vertex

    Returns the COLMAP_Root empty.

    The legacy import logic (which has been in colmap_panel.py for many
    versions) is preserved here verbatim; future phases will refactor.
    """
    if not HAS_BPY:
        raise RuntimeError("import_model_to_scene requires Blender (bpy).")

    model = read_model(Path(model_path))

    # See ui/colmap_panel.py for the original implementation.
    # Phase 1 keeps the operator code as-is; this service is a stub
    # that delegates back to a function on bpy.ops level.
    raise NotImplementedError(
        "import_model_to_scene is a stub for phase 1 — extraction "
        "deferred to phase 1.5 to keep this stage's blast radius small. "
        "See task D3 in the plan."
    )
