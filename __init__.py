bl_info = {
    "name": "SkySplat Blender: 3DGS Blender Toolkit",
    "author": "kyjohnso",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > SkySplat",
    "description": "Workflow tools for 3D Gaussian Splatting using Blender",
    "category": "3D View",
}

import importlib
import bpy

# Submodules
from . import ui
from .ui import video_panel

# Reload in development
importlib.reload(ui)
importlib.reload(video_panel)

classes = (
    video_panel.SKY_SPLAT_PT_video_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
