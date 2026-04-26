"""SkySplatNodeTree — registers a new editor type so users can split a
Blender area to "SkySplat Node Editor" and see a node graph there.

The actual nodes live in sibling modules (video_node.py, etc.).
"""
from __future__ import annotations

try:
    import bpy
    from bpy.types import NodeTree
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    NodeTree = object  # for static analysis when bpy is missing


class SkySplatNodeTree(NodeTree if HAS_BPY else object):
    """Top-level container for skysplat pipeline graphs."""
    bl_idname = "SkySplatNodeTree"
    bl_label = "SkySplat"
    bl_icon = "NODETREE"

    @classmethod
    def get_from_context(cls, context):
        """Return (tree, owner_id, from_id) for the active SkySplat editor.

        Implementing this helps Blender's link-drag-search and other
        editor-aware operators find our tree.
        """
        if not HAS_BPY:
            return None, None, None
        space = context.space_data
        if space and getattr(space, "tree_type", "") == cls.bl_idname:
            tree = space.node_tree
            return tree, tree, tree
        return None, None, None


classes = (SkySplatNodeTree,) if HAS_BPY else ()


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
