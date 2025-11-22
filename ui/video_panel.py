import bpy
import os
import time

PANEL_VERSION = "0.4.0"  # Updated version for multi-instance support

def get_all_sequences(seq_editor):
    """Get all sequences from the sequence editor (compatible with Blender 4.5 and 5.0)"""
    # Blender 5.0 changed sequences_all to strips_all
    if hasattr(seq_editor, 'strips_all'):
        return seq_editor.strips_all
    else:
        return seq_editor.sequences_all

def get_sequences_collection(seq_editor):
    """Get the sequences collection for adding new strips (compatible with Blender 4.5 and 5.0)"""
    # Blender 5.0 changed sequences to strips
    if hasattr(seq_editor, 'strips'):
        return seq_editor.strips
    else:
        return seq_editor.sequences

def get_skysplat_props(context):
    """Get skysplat props from the correct scene (compatible with Blender 4.5 and 5.0)"""
    # In Blender 5.0+, the sequencer scene is separate from the window scene
    # We store data in the window scene, not the sequencer scene
    if hasattr(context, 'window') and context.window and hasattr(context.window, 'scene'):
        return context.window.scene.skysplat_props
    else:
        return context.scene.skysplat_props

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

        # Also update the output folder when video path changes
        update_output_folder(self, context)

def update_output_folder(self, context):
    """Set default output folder based on video path"""
    if self.video_path:
        video_path = bpy.path.abspath(self.video_path)
        # Get directory and filename without extension
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        # Create frames folder path
        frames_folder = os.path.join(video_dir, f"{video_name}_frames")
        self.output_folder = frames_folder

class VideoInstance(bpy.types.PropertyGroup):
    """Individual video instance with its own settings"""
    name: bpy.props.StringProperty(
        name="Instance Name",
        description="Name for this video instance",
        default="Video"
    )
    
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
        description="Folder to save extracted frames (can be shared across videos)",
        subtype='DIR_PATH'
    )
    
    is_loaded: bpy.props.BoolProperty(
        name="Is Loaded",
        description="Whether this video is currently loaded in the sequencer",
        default=False
    )
    
    frames_extracted: bpy.props.BoolProperty(
        name="Frames Extracted",
        description="Whether frames have been extracted for this video",
        default=False
    )

class SkySplatProperties(bpy.types.PropertyGroup):
    """Main property group for video management"""
    video_instances: bpy.props.CollectionProperty(
        type=VideoInstance,
        name="Video Instances",
        description="Collection of video instances"
    )
    
    active_video_index: bpy.props.IntProperty(
        name="Active Video Index",
        description="Index of the currently active video instance",
        default=0,
        min=0
    )
    
    # Legacy properties for backward compatibility
    video_path: bpy.props.StringProperty(
        name="Video File",
        description="Path to the input video (legacy)",
        subtype='FILE_PATH',
        update=update_srt_path
    )
    srt_path: bpy.props.StringProperty(
        name="SRT File",
        description="Path to the SRT metadata file (legacy)",
        subtype='FILE_PATH'
    )
    frame_start: bpy.props.IntProperty(
        name="Start Frame",
        description="First frame to extract (legacy)",
        default=0,
        min=0
    )
    frame_end: bpy.props.IntProperty(
        name="End Frame",
        description="Last frame to extract (legacy)",
        default=100,
        min=0
    )
    frame_step: bpy.props.IntProperty(
        name="Frame Step",
        description="Extract every Nth frame (legacy)",
        default=1,
        min=1
    )
    output_folder: bpy.props.StringProperty(
        name="Output Folder",
        description="Folder to save extracted frames (legacy)",
        subtype='DIR_PATH'
    )

class SKY_SPLAT_OT_add_video_instance(bpy.types.Operator):
    bl_idname = "skysplat.add_video_instance"
    bl_label = "Add Video Instance"
    bl_description = "Add a new video instance"

    def execute(self, context):
        # In Blender 5.0+, select the default scene for the video sequencer if not already set
        has_sequencer_scene_support = hasattr(context.workspace, 'sequencer_scene')

        if has_sequencer_scene_support:
            # Check if a sequencer scene is already selected
            if not context.workspace.sequencer_scene:
                # Select the current scene for the video sequencer
                context.workspace.sequencer_scene = context.scene
                self.report({'INFO'}, f"Selected scene '{context.scene.name}' for video sequencer")

            # Ensure the sequencer scene has a sequence editor
            if context.workspace.sequencer_scene and not context.workspace.sequencer_scene.sequence_editor:
                context.workspace.sequencer_scene.sequence_editor_create()

        # Now add the video instance (props will be from window scene)
        props = get_skysplat_props(context)
        new_instance = props.video_instances.add()
        new_instance.name = f"Video_{len(props.video_instances)}"
        props.active_video_index = len(props.video_instances) - 1
        self.report({'INFO'}, f"Added video instance: {new_instance.name}")
        return {'FINISHED'}

class SKY_SPLAT_OT_remove_video_instance(bpy.types.Operator):
    bl_idname = "skysplat.remove_video_instance"
    bl_label = "Remove Video Instance"
    bl_description = "Remove the active video instance"
    
    @classmethod
    def poll(cls, context):
        props = get_skysplat_props(context)
        return len(props.video_instances) > 0

    def execute(self, context):
        props = get_skysplat_props(context)
        if len(props.video_instances) > 0:
            props.video_instances.remove(props.active_video_index)
            props.active_video_index = max(0, props.active_video_index - 1)
            self.report({'INFO'}, "Removed video instance")
        return {'FINISHED'}

class SKY_SPLAT_OT_load_video(bpy.types.Operator):
    bl_idname = "skysplat.load_video"
    bl_label = "Load Video and SRT"
    bl_description = "Load the video and associated SRT file into the Video Sequencer"

    def execute(self, context):
        # Get props from the correct scene (window scene, not sequencer scene)
        props = get_skysplat_props(context)

        # Get active video instance
        if len(props.video_instances) == 0:
            self.report({'ERROR'}, "No video instances. Add a video instance first.")
            return {'CANCELLED'}

        video_instance = props.video_instances[props.active_video_index]

        # Validate paths
        if not video_instance.video_path:
            self.report({'ERROR'}, "Please select a video file")
            return {'CANCELLED'}

        video_path = bpy.path.abspath(video_instance.video_path)
        if not os.path.exists(video_path):
            self.report({'ERROR'}, f"Video file not found: {video_instance.video_path}")
            return {'CANCELLED'}

        # Get the sequencer scene (Blender 5.0 uses workspace.sequencer_scene, fallback to context.scene)
        # Check if we're in Blender 5.0+ with sequencer scene support
        has_sequencer_scene_support = hasattr(context, 'sequencer_scene') or hasattr(context.workspace, 'sequencer_scene')

        if has_sequencer_scene_support:
            # Blender 5.0+ path
            if hasattr(context, 'sequencer_scene') and context.sequencer_scene:
                target_scene = context.sequencer_scene
                self.report({'INFO'}, f"Using context.sequencer_scene: {target_scene.name}")
            elif hasattr(context.workspace, 'sequencer_scene') and context.workspace.sequencer_scene:
                target_scene = context.workspace.sequencer_scene
                self.report({'INFO'}, f"Using workspace.sequencer_scene: {target_scene.name}")
            else:
                # No sequencer scene exists yet, create one
                self.report({'INFO'}, "No sequencer scene found, creating new sequencer scene")
                bpy.ops.scene.new_sequencer_scene(type='NEW')
                # After creating, get the newly created sequencer scene
                if hasattr(context, 'sequencer_scene') and context.sequencer_scene:
                    target_scene = context.sequencer_scene
                    context.workspace.sequencer_scene = context.sequencer_scene
                elif hasattr(context.workspace, 'sequencer_scene') and context.workspace.sequencer_scene:
                    target_scene = context.workspace.sequencer_scene
                else:
                    # Fallback if something went wrong
                    target_scene = context.scene
                self.report({'INFO'}, f"Created and using sequencer scene: {target_scene.name}")
        else:
            # Blender 4.5 and earlier path
            target_scene = context.scene
            self.report({'INFO'}, f"Using context.scene: {target_scene.name}")

        # Set up the Video Sequencer
        if not target_scene.sequence_editor:
            target_scene.sequence_editor_create()

        seq_editor = target_scene.sequence_editor
        
        # Find the next available channel
        # Check all existing strips to find the highest channel in use
        max_channel = 0
        for strip in get_all_sequences(seq_editor):
            if strip.channel > max_channel:
                max_channel = strip.channel
        
        # Use the next channel (or channel 1 if no strips exist)
        next_channel = max_channel + 1 if max_channel > 0 else 1
        
        # Add video strip to the next available channel
        sequences_collection = get_sequences_collection(seq_editor)
        video_strip = sequences_collection.new_movie(
            name=os.path.basename(video_path),
            filepath=video_path,
            channel=next_channel,
            frame_start=1
        )

        self.report({'INFO'}, f"Added strip '{video_strip.name}' to channel {next_channel} in scene '{target_scene.name}'")

        # Store the channel number in the video instance for reference
        video_instance['sequencer_channel'] = next_channel

        # Auto-set scene frame range to match video
        target_scene.frame_start = 1
        target_scene.frame_end = video_strip.frame_final_duration
        
        # Set default frame extraction range based on video
        video_instance.frame_start = 1
        video_instance.frame_end = video_strip.frame_final_duration
        
        # Calculate frame step to get approximately 150 frames
        total_frames = video_strip.frame_final_duration - 1 + 1
        target_frame_count = 150
        calculated_step = max(1, int(total_frames / target_frame_count))
        video_instance.frame_step = calculated_step
        
        # Mark as loaded
        video_instance.is_loaded = True
        
        self.report({'INFO'}, f"Auto-calculated frame step: {calculated_step} (will extract ~{total_frames // calculated_step} frames from {total_frames} total)")
        
        # Switch to the Video Editing workspace if it exists
        if 'Video Editing' in bpy.data.workspaces:
            bpy.context.window.workspace = bpy.data.workspaces['Video Editing']
        
        # Add SRT file as subtitle if provided
        if video_instance.srt_path and os.path.exists(bpy.path.abspath(video_instance.srt_path)):
            self.report({'INFO'}, f"SRT file loaded: {video_instance.srt_path} (metadata only)")
        
        # Auto-create a corresponding COLMAP instance with correct paths
        if hasattr(context.scene, 'skysplat_colmap_props'):
            colmap_props = context.scene.skysplat_colmap_props
            
            # Get video name for naming the COLMAP instance
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            
            # Create new COLMAP instance
            new_colmap = colmap_props.colmap_instances.add()
            new_colmap.name = f"COLMAP_{video_name}"
            
            # Set up paths based on video
            video_dir = os.path.dirname(video_path)
            frames_folder = os.path.join(video_dir, f"{video_name}_frames")
            colmap_output_folder = os.path.join(video_dir, f"{video_name}_colmap_output")
            
            new_colmap.input_folder = frames_folder
            new_colmap.output_folder = colmap_output_folder
            new_colmap.model_import_path = os.path.join(colmap_output_folder, "sparse", "0")
            new_colmap.model_export_path = os.path.join(colmap_output_folder, "transformed")
            new_colmap.images_path = os.path.join(colmap_output_folder, "images")
            
            # Set the new COLMAP instance as active
            colmap_props.active_colmap_index = len(colmap_props.colmap_instances) - 1
            
            self.report({'INFO'}, f"Auto-created COLMAP instance: {new_colmap.name}")
        
        self.report({'INFO'}, f"Loaded video into sequencer: {video_instance.video_path}")
        return {'FINISHED'}

class SKY_SPLAT_OT_extract_frames(bpy.types.Operator):
    bl_idname = "skysplat.extract_frames"
    bl_label = "Extract Frames"
    bl_description = "Extract frames from the loaded video"
    
    def execute(self, context):
        # Start timing
        start_time = time.time()

        props = get_skysplat_props(context)
        
        # Get active video instance
        if len(props.video_instances) == 0:
            self.report({'ERROR'}, "No video instances. Add a video instance first.")
            return {'CANCELLED'}
        
        video_instance = props.video_instances[props.active_video_index]
        
        # Validate required fields
        if not video_instance.video_path:
            self.report({'ERROR'}, "Please load a video first")
            return {'CANCELLED'}
            
        if not video_instance.output_folder:
            self.report({'ERROR'}, "Please specify an output folder")
            return {'CANCELLED'}
            
        output_folder = bpy.path.abspath(video_instance.output_folder)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        
        # Store original render settings to restore later
        original_path = context.scene.render.filepath
        original_file_format = context.scene.render.image_settings.file_format
        original_color_mode = context.scene.render.image_settings.color_mode
        original_frame_start = context.scene.frame_start
        original_frame_end = context.scene.frame_end
        original_frame_step = context.scene.frame_step
        original_res_x = context.scene.render.resolution_x
        original_res_y = context.scene.render.resolution_y
        original_res_pct = context.scene.render.resolution_percentage
        
        try:
            # Store original mute states and find the target video strip
            original_mute_states = {}
            target_strip = None
            video_path = bpy.path.abspath(video_instance.video_path)
            video_filename = os.path.basename(video_path)
            
            if context.scene.sequence_editor:
                # First pass: find the target strip and store all mute states
                for seq in get_all_sequences(context.scene.sequence_editor):
                    if seq.type == 'MOVIE':
                        original_mute_states[seq.name] = seq.mute
                        # Match by filename to find our target strip
                        if seq.name == video_filename or seq.filepath == video_path:
                            target_strip = seq

                # Second pass: mute all video strips except the target
                for seq in get_all_sequences(context.scene.sequence_editor):
                    if seq.type == 'MOVIE':
                        if seq == target_strip:
                            seq.mute = False  # Ensure target is unmuted
                        else:
                            seq.mute = True  # Mute all others
                
                # Set render resolution based on target strip
                if target_strip:
                    context.scene.render.resolution_x = target_strip.elements[0].orig_width
                    context.scene.render.resolution_y = target_strip.elements[0].orig_height
                    context.scene.render.resolution_percentage = 100
                    self.report({'INFO'}, f"Set render resolution to {target_strip.elements[0].orig_width}x{target_strip.elements[0].orig_height}")
                    self.report({'INFO'}, f"Extracting frames from: {target_strip.name}")
            
            # Setup render settings
            context.scene.render.filepath = os.path.join(output_folder, "frame_")
            context.scene.render.image_settings.file_format = 'PNG'
            context.scene.render.image_settings.color_mode = 'RGB'
            
            # Set frame range based on user input
            context.scene.frame_start = video_instance.frame_start
            context.scene.frame_end = video_instance.frame_end
            context.scene.frame_step = video_instance.frame_step
            
            # Render the animation frames
            bpy.ops.render.opengl(animation=True, sequencer=True)
            
            # Count extracted frames
            frame_count = len([f for f in os.listdir(output_folder) if f.endswith('.png')])
            
            # Mark frames as extracted
            video_instance.frames_extracted = True
            
            # Open the output folder
            bpy.ops.wm.path_open(filepath=output_folder)
            
            # Calculate and print timing
            end_time = time.time()
            total_time = end_time - start_time
            print(f"Frame extraction completed in {total_time:.2f} seconds")
            
            self.report({'INFO'}, f"Successfully extracted {frame_count} frames to {output_folder}")
            
            # After successful extraction, update COLMAP paths
            if hasattr(context.scene, 'skysplat_colmap_props'):
                context.scene.skysplat_colmap_props.update_from_video_panel(context)

            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}
            
        finally:
            # Restore original mute states for all video strips
            if context.scene.sequence_editor:
                for seq in get_all_sequences(context.scene.sequence_editor):
                    if seq.type == 'MOVIE' and seq.name in original_mute_states:
                        seq.mute = original_mute_states[seq.name]
            
            # Restore original render settings
            context.scene.render.filepath = original_path
            context.scene.render.image_settings.file_format = original_file_format
            context.scene.render.image_settings.color_mode = original_color_mode
            context.scene.frame_start = original_frame_start
            context.scene.frame_end = original_frame_end
            context.scene.frame_step = original_frame_step
            context.scene.render.resolution_x = original_res_x
            context.scene.render.resolution_y = original_res_y
            context.scene.render.resolution_percentage = original_res_pct
        

class SKY_SPLAT_PT_video_panel(bpy.types.Panel):
    bl_label = "SkySplat Video Loader"
    bl_idname = "SKY_SPLAT_PT_video_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SkySplat"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = get_skysplat_props(context)
        
        # Video instance management
        box = layout.box()
        box.label(text="Video Instances", icon='SEQUENCE')
        
        row = box.row()
        row.template_list("UI_UL_list", "video_instances", props, "video_instances", 
                         props, "active_video_index", rows=3)
        
        col = row.column(align=True)
        col.operator("skysplat.add_video_instance", icon='ADD', text="")
        col.operator("skysplat.remove_video_instance", icon='REMOVE', text="")
        
        # Show active video instance settings
        if len(props.video_instances) > 0 and props.active_video_index < len(props.video_instances):
            video_instance = props.video_instances[props.active_video_index]
            
            # Instance name
            box.prop(video_instance, "name")
            
            # Video loading section
            box = layout.box()
            box.label(text="Video & Metadata Files")
            box.prop(video_instance, "video_path")
            box.prop(video_instance, "srt_path")
            
            row = box.row()
            row.operator("skysplat.load_video", icon='IMPORT')
            if video_instance.is_loaded:
                row.label(text="✓ Loaded", icon='CHECKMARK')
            
            # Frame extraction section
            box = layout.box()
            box.label(text="Frame Extraction")
            
            row = box.row(align=True)
            row.prop(video_instance, "frame_start")
            row.prop(video_instance, "frame_end")
            
            box.prop(video_instance, "frame_step")
            box.prop(video_instance, "output_folder")
            
            row = box.row()
            row.operator("skysplat.extract_frames", icon='RENDER_STILL')
            if video_instance.frames_extracted:
                row.label(text="✓ Extracted", icon='CHECKMARK')
            
            # Info about shared paths
            box = layout.box()
            box.label(text="💡 Tip: Multiple videos can share the same", icon='INFO')
            box.label(text="output folder for combined COLMAP processing")
        else:
            box.label(text="Add a video instance to begin", icon='INFO')

        # Version indicator at the bottom
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")

def register():
    bpy.utils.register_class(VideoInstance)
    bpy.utils.register_class(SkySplatProperties)
    bpy.types.Scene.skysplat_props = bpy.props.PointerProperty(type=SkySplatProperties)
    bpy.utils.register_class(SKY_SPLAT_OT_add_video_instance)
    bpy.utils.register_class(SKY_SPLAT_OT_remove_video_instance)
    bpy.utils.register_class(SKY_SPLAT_OT_load_video)
    bpy.utils.register_class(SKY_SPLAT_OT_extract_frames)
    bpy.utils.register_class(SKY_SPLAT_PT_video_panel)

def unregister():
    bpy.utils.unregister_class(SKY_SPLAT_PT_video_panel)
    bpy.utils.unregister_class(SKY_SPLAT_OT_extract_frames)
    bpy.utils.unregister_class(SKY_SPLAT_OT_load_video)
    bpy.utils.unregister_class(SKY_SPLAT_OT_remove_video_instance)
    bpy.utils.unregister_class(SKY_SPLAT_OT_add_video_instance)
    del bpy.types.Scene.skysplat_props
    bpy.utils.unregister_class(SkySplatProperties)
    bpy.utils.unregister_class(VideoInstance)

if __name__ == "__main__":
    register()