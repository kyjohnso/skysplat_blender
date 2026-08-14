"""SkySplat node add-menu wiring.

Exposes a global registry that node modules append themselves to via
register_add_menu_entry(). The Add menu (Shift-A) reads from this
registry to populate the SkySplat submenu.
"""
from __future__ import annotations

try:
    import bpy
    from bpy.types import Menu
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    Menu = object


_entries: list[tuple[str, str]] = []  # (bl_idname, label)


def register_add_menu_entry(bl_idname: str, label: str) -> None:
    """Called by node modules at registration time to add themselves
    to the Shift-A menu."""
    _entries.append((bl_idname, label))


def clear_add_menu_entries() -> None:
    _entries.clear()


def add_menu_entries() -> tuple:
    """All registered (bl_idname, label) pairs. Also used by
    link_drag_search to discover node types."""
    return tuple(_entries)


if HAS_BPY:

    class NODE_MT_skysplat_add(Menu):
        bl_idname = "NODE_MT_skysplat_add"
        bl_label = "SkySplat"

        def draw(self, context):
            layout = self.layout
            for idname, label in _entries:
                op = layout.operator("node.add_node", text=label)
                op.type = idname
                op.use_transform = True


    def _draw_skysplat_submenu(self, context):
        if context.space_data.tree_type != "SkySplatNodeTree":
            return
        # Note: this menu can't feed Blender's native link-drag-search —
        # that popup is hard-disabled for custom trees (NTREE_CUSTOM) in
        # node_relationships.cc. See link_drag_search.py for our own.
        self.layout.menu(NODE_MT_skysplat_add.bl_idname, icon="NODETREE")


    classes = (NODE_MT_skysplat_add,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.NODE_MT_add.append(_draw_skysplat_submenu)

    def unregister():
        bpy.types.NODE_MT_add.remove(_draw_skysplat_submenu)
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        clear_add_menu_entries()

else:
    def register(): pass
    def unregister(): pass
