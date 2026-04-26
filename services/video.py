"""Video sequencer service.

Pure parts: parse_srt_metadata is in services/srt.py.
Scene parts (this module): load_video_into_vse — adopts existing strips
or creates a new one named for skysplat traceability.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


def resolve_target_scene(context):
    """Pick the right scene to host VSE strips on.

    Blender 5.0+ separates `workspace.sequencer_scene` from the active
    3D view scene. The VSE editor shows `workspace.sequencer_scene`
    (auto-created on demand) — adding a strip to context.scene's VSE
    when sequencer_scene is a different scene results in a strip the
    user cannot see.

    Mirrors the logic in `SKY_SPLAT_OT_load_video.execute` (the existing
    sidebar operator) so both UIs converge on the same target scene.

    Returns the scene to use. Side effect: sets workspace.sequencer_scene
    when it was unset and the API supports it.
    """
    if not HAS_BPY:
        raise RuntimeError("resolve_target_scene requires Blender (bpy).")
    workspace = context.workspace
    if hasattr(workspace, "sequencer_scene"):
        if not workspace.sequencer_scene:
            workspace.sequencer_scene = context.scene
        return workspace.sequencer_scene
    return context.scene


def load_video_into_vse(
    scene,
    video_path: Path,
    strip_name: str,
):
    """Load a movie file into the scene's VSE, adopting any existing
    strip pointing at the same file.

    Returns the bpy.types.MovieSequence-equivalent strip object.

    Raises RuntimeError if Blender (bpy) is not available.
    """
    if not HAS_BPY:
        raise RuntimeError("load_video_into_vse requires Blender (bpy).")

    video_path = Path(bpy.path.abspath(str(video_path)))

    if not scene.sequence_editor:
        scene.sequence_editor_create()
    seq_editor = scene.sequence_editor

    # Adopt: look for existing strip with matching filepath.
    for strip in _all_movie_strips(seq_editor):
        if Path(bpy.path.abspath(strip.filepath)) == video_path:
            return strip

    # Create new strip on first free channel.
    next_channel = _next_free_channel(seq_editor)
    sequences_collection = _sequences_collection(seq_editor)
    return sequences_collection.new_movie(
        name=strip_name,
        filepath=str(video_path),
        channel=next_channel,
        frame_start=1,
    )


def _all_movie_strips(seq_editor):
    # Blender 5.0 renamed sequences_all → strips_all. Handle both.
    if hasattr(seq_editor, "strips_all"):
        return [s for s in seq_editor.strips_all if s.type == "MOVIE"]
    return [s for s in seq_editor.sequences_all if s.type == "MOVIE"]


def _sequences_collection(seq_editor):
    if hasattr(seq_editor, "strips"):
        return seq_editor.strips
    return seq_editor.sequences


def _next_free_channel(seq_editor) -> int:
    used = {s.channel for s in _all_movie_strips(seq_editor)}
    for i in range(1, 256):
        if i not in used:
            return i
    return 1
