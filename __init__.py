bl_info = {
    "name": "SkySplat: 3DGS Blender Toolkit",
    "author": "Kyle Johnson",
    "version": (0, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > SkySplat",
    "description": "Workflow tools for 3D Gaussian Splatting using Blender, COLMAP, and Brush",  # Updated
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
    SKY_SPLAT_OT_prepare_brush_dataset,
)

# Import classes from gaussian splatting panel
from .ui.gaussian_splatting_panel import (
    SkySplatBrushProperties,  # Changed from SKY_SPLAT_GaussianSplattingProperties
    SKY_SPLAT_PT_gaussian_splatting_panel,  # Same name
    SKY_SPLAT_OT_run_brush_training,  # Changed from SKY_SPLAT_OT_run_gaussian_splatting
    SKY_SPLAT_OT_sync_brush_with_colmap,  # Changed from SKY_SPLAT_OT_sync_gs_with_colmap
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
    SKY_SPLAT_OT_prepare_brush_dataset,
    # Gaussian Splatting panel
    SkySplatBrushProperties,  # Changed
    SKY_SPLAT_PT_gaussian_splatting_panel,  # Same name
    SKY_SPLAT_OT_run_brush_training,  # Changed
    SKY_SPLAT_OT_sync_brush_with_colmap,  # Changed
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.skysplat_props = bpy.props.PointerProperty(type=SkySplatProperties)
    bpy.types.Scene.skysplat_colmap_props = bpy.props.PointerProperty(type=SKY_SPLAT_ColmapProperties)
    bpy.types.Scene.skysplat_brush_props = bpy.props.PointerProperty(type=SkySplatBrushProperties)  # Changed property name

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.skysplat_props
    del bpy.types.Scene.skysplat_colmap_props
    del bpy.types.Scene.skysplat_brush_props  # Changed property name