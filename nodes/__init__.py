"""skysplat node editor — phase 2 MVP.

Registers a new editor type and the node classes that populate it.
Each node calls into services/* for actual pipeline work.
"""
try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from . import tree, sockets

_modules = (tree, sockets)


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
