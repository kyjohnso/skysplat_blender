"""Socket types for the SkySplat node editor.

Each socket type has a fixed color and identifies a kind of data flowing
through the graph. The actual lineage object (paths, source_id, etc.)
isn't stored on the socket itself — Blender's `default_value` doesn't
accommodate arbitrary Python objects cleanly — but in a per-tree
registry keyed by (node.uuid, socket.identifier). See nodes/base.py.
"""
from __future__ import annotations

try:
    import bpy
    from bpy.types import NodeSocket
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    NodeSocket = object


class _SkysplatSocket(NodeSocket if HAS_BPY else object):
    """Base for skysplat sockets. Subclasses set bl_idname, bl_label, and color."""
    color = (0.5, 0.5, 0.5, 1.0)

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return self.color


class VideoSocket(_SkysplatSocket):
    bl_idname = "SkysplatVideoSocket"
    bl_label = "Video"
    color = (0.20, 0.65, 0.27, 1.0)  # green


class FramesSocket(_SkysplatSocket):
    bl_idname = "SkysplatFramesSocket"
    bl_label = "Frames"
    color = (0.85, 0.55, 0.20, 1.0)  # orange


class ColmapModelSocket(_SkysplatSocket):
    bl_idname = "SkysplatColmapModelSocket"
    bl_label = "COLMAP Model"
    color = (0.20, 0.50, 0.78, 1.0)  # blue


class DatasetSocket(_SkysplatSocket):
    bl_idname = "SkysplatDatasetSocket"
    bl_label = "Dataset"
    color = (0.80, 0.78, 0.30, 1.0)  # yellow


class SplatSocket(_SkysplatSocket):
    bl_idname = "SkysplatSplatSocket"
    bl_label = "Splat"
    color = (0.85, 0.32, 0.38, 1.0)  # red


classes = (
    VideoSocket, FramesSocket, ColmapModelSocket, DatasetSocket, SplatSocket,
) if HAS_BPY else ()


def register():
    if not HAS_BPY:
        return
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if not HAS_BPY:
        return
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
