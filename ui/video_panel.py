import bpy
import os

PANEL_VERSION = "1"

def update_srt_path(self, context):
    """Update SRT path when video path changes"""
    if self.video_path:
        # Get the absolute path
        video_path = bpy.path.abspath(self.video_path)
        # Change extension to .srt
        base_path, ext = os.path.splitext(video_path)
        srt_path = base_path + ".SRT"
        
        # Only set if the SRT file exists
        if os.path.exists(srt_path):
            self.srt_path = srt_path
        else:
            # Try lowercase .srt as an alternative
            srt_path_lower = base_path + ".srt"
            if os.path.exists(srt_path_lower):
                self.srt_path = srt_path_lower


class SkySplatProperties(bpy.types.PropertyGroup):
    video_path: bpy.props.StringProperty(
        name="Video File",
        description="Path to the input video",
        subtype='FILE_PATH',
        update=update_srt_path
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
    bl_description = "Load the video and associated SRT file into the Video Sequencer"

    def execute(self, context):
        props = context.scene.skysplat_props
        
        # Validate paths
        if not props.video_path:
            self.report({'ERROR'}, "Please select a video file")
            return {'CANCELLED'}
            
        video_path = bpy.path.abspath(props.video_path)
        if not os.path.exists(video_path):
            self.report({'ERROR'}, f"Video file not found: {props.video_path}")
            return {'CANCELLED'}
        
        # Set up the Video Sequencer
        if not context.scene.sequence_editor:
            context.scene.sequence_editor_create()
        
        seq_editor = context.scene.sequence_editor
        
        # Clear existing strips if any
        for strip in seq_editor.sequences_all:
            seq_editor.sequences.remove(strip)
        
        # Add video strip
        video_strip = seq_editor.sequences.new_movie(
            name=os.path.basename(video_path),
            filepath=video_path,
            channel=1,
            frame_start=1
        )
        
        # Auto-set scene frame range to match video
        context.scene.frame_start = 1
        context.scene.frame_end = video_strip.frame_final_duration
        
        # Set default frame extraction range based on video
        props.frame_start = 1
        props.frame_end = video_strip.frame_final_duration
        
        # Switch to the Video Editing workspace if it exists
        if 'Video Editing' in bpy.data.workspaces:
            bpy.context.window.workspace = bpy.data.workspaces['Video Editing']
        
        # Add SRT file as subtitle if provided
        if props.srt_path and os.path.exists(bpy.path.abspath(props.srt_path)):
            # Note: Blender doesn't directly support SRT files in the sequencer
            # This is a placeholder for future implementation
            self.report({'INFO'}, f"SRT file loaded: {props.srt_path} (metadata only)")
        
        self.report({'INFO'}, f"Loaded video into sequencer: {props.video_path}")
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

        # Version indicator at the bottom
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")