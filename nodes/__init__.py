"""skysplat node editor — phase 2 MVP.

Registers a new editor type and the node classes that populate it.
Each node calls into services/* for actual pipeline work.
"""
try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from . import (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, merge_frames_node,
    colmap_node, transform_colmap_node, export_colmap_node,
    colmap_cameras_node,
    brush_dataset_node, brush_train_node, splat_output_node,
    link_drag_search,
)

_modules = (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, merge_frames_node,
    colmap_node, transform_colmap_node, export_colmap_node,
    colmap_cameras_node,
    brush_dataset_node, brush_train_node, splat_output_node,
    link_drag_search,
)


def register():
    if not HAS_BPY:
        return
    for m in _modules:
        m.register()


def unregister():
    if not HAS_BPY:
        return
    for m in reversed(_modules):
        m.unregister()
