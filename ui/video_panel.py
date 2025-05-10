import bpy
import os

class SkySplatProperties(bpy.types.PropertyGroup):
    video_path: bpy.props.StringProperty(
        name="Video File",
        description="Path to the input video",
        subtype='FILE_PATH'
    )
    srt_path: bpy.props.StringProperty(
        name="SRT File",
        description="Path to the SRT metadata file",
        subtype='FILE_PATH'
    )
    frame_start: bpy.props.IntProperty(
        name="Start Frame",
        description="First frame to extract",
        default=0,
        min=0
    )
    frame_end: bpy.props.IntProperty(
        name="End Frame",
        description="Last frame to extract",
        default=100,
        min=0
    )
    frame_step: bpy.props.IntProperty(
        name="Frame Step",
        description="Extract every Nth frame",
        default=1,
        min=1
    )
    output_folder: bpy.props.StringProperty(
        name="Output Folder",
        description="Folder to save extracted frames",
        subtype='DIR_PATH'
    )

class SKY_SPLAT_OT_load_video(bpy.types.Operator):
    bl_idname = "skysplat.load_video"
    bl_label = "Load Video and SRT"
    bl_description = "Load the video and associated SRT file"

    def execute(self, context):
        props = context.scene.skysplat_props
        self.report({'INFO'}, f"Loaded: {props.video_path}, {props.srt_path}")
        return {'FINISHED'}

class SKY_SPLAT_OT_extract_frames(bpy.types.Operator):
    bl_idname = "skysplat.extract_frames"
    bl_label = "Extract Frames"
    bl_description = "Extract frames from the loaded video"

    def execute(self, context):
        props = context.scene.skysplat_props
        self.report({'INFO'}, f"Extracting frames {props.frame_start}-{props.frame_end} (step {props.frame_step}) to {props.output_folder}")
        return {'FINISHED'}

class SKY_SPLAT_PT_video_panel(bpy.types.Panel):
    bl_label = "SkySplat Video Loader"
    bl_idname = "SKY_SPLAT_PT_video_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SkySplat"

    def draw(self, context):
        layout = self.layout
        props = context.scene.skysplat_props
        
        # Video loading section
        box = layout.box()
        box.label(text="Video & Metadata Files")
        box.prop(props, "video_path")
        box.prop(props, "srt_path")
        box.operator("skysplat.load_video", icon='IMPORT')
        
        # Frame extraction section
        box = layout.box()
        box.label(text="Frame Extraction")
        
        row = box.row(align=True)
        row.prop(props, "frame_start")
        row.prop(props, "frame_end")
        
        box.prop(props, "frame_step")
        box.prop(props, "output_folder")
        box.operator("skysplat.extract_frames", icon='RENDER_STILL')