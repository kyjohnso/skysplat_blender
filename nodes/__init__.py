"""skysplat node editor — phase 2 MVP.

Registers a new editor type and the node classes that populate it.
Each node calls into services/* for actual pipeline work.
"""
try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from . import tree, sockets, base, add_menu, video_node, frames_folder_node

_modules = (tree, sockets, base, add_menu, video_node, frames_folder_node)


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
