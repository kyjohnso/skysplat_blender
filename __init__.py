bl_info = {
    "name": "SkySplat: 3DGS Blender Toolkit",
    "author": "Your Name",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > SkySplat",
    "description": "Workflow tools for 3D Gaussian Splatting using Blender and COLMAP",
    "category": "3D View",
}

import bpy

# Import classes from video panel
from .ui.video_panel import (
    SkySplatProperties,
    SKY_SPLAT_PT_video_panel,
    SKY_SPLAT_OT_load_video,
    SKY_SPLAT_OT_extract_frames,
)

classes = (
    SkySplatProperties,
    SKY_SPLAT_PT_video_panel,
    SKY_SPLAT_OT_load_video,
    SKY_SPLAT_OT_extract_frames,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.skysplat_props = bpy.props.PointerProperty(type=SkySplatProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.skysplat_props