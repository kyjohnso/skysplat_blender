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

# Import classes from colmap panel
from .ui.colmap_panel import (
    SKY_SPLAT_ColmapProperties,
    SKY_SPLAT_PT_colmap_panel,
    SKY_SPLAT_OT_run_colmap,
    SKY_SPLAT_OT_sync_with_video,
    SKY_SPLAT_OT_load_colmap_model,
    SKY_SPLAT_OT_export_colmap_model,
)

# Import classes from gaussian splatting panel
from .ui.gaussian_splatting_panel import (
    SKY_SPLAT_GaussianSplattingProperties,
    SKY_SPLAT_PT_gaussian_splatting_panel,
    SKY_SPLAT_OT_run_gaussian_splatting,
    SKY_SPLAT_OT_sync_gs_with_colmap,
)

classes = (
    # Video panel
    SkySplatProperties,
    SKY_SPLAT_PT_video_panel,
    SKY_SPLAT_OT_load_video,
    SKY_SPLAT_OT_extract_frames,
    # COLMAP panel
    SKY_SPLAT_ColmapProperties,
    SKY_SPLAT_PT_colmap_panel,
    SKY_SPLAT_OT_run_colmap,
    SKY_SPLAT_OT_sync_with_video,
    SKY_SPLAT_OT_load_colmap_model,
    SKY_SPLAT_OT_export_colmap_model,
    # Gaussian Splatting panel
    SKY_SPLAT_GaussianSplattingProperties,
    SKY_SPLAT_PT_gaussian_splatting_panel,
    SKY_SPLAT_OT_run_gaussian_splatting,
    SKY_SPLAT_OT_sync_gs_with_colmap,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.skysplat_props = bpy.props.PointerProperty(type=SkySplatProperties)
    bpy.types.Scene.skysplat_colmap_props = bpy.props.PointerProperty(type=SKY_SPLAT_ColmapProperties)
    bpy.types.Scene.skysplat_gaussian_splatting_props = bpy.props.PointerProperty(type=SKY_SPLAT_GaussianSplattingProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.skysplat_props
    del bpy.types.Scene.skysplat_colmap_props
    del bpy.types.Scene.skysplat_gaussian_splatting_props