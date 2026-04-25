
import bpy
import os
import subprocess
import threading
import platform
from bpy.types import PropertyGroup, Panel, Operator
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, PointerProperty
from ..config import BUNDLED_BINARY_NAMES, get_bundled_binaries_directory

# Version for UI display
PANEL_VERSION = "0.4.1.graph"  # phase-1 services-extraction (issue #51 branch)

def update_export_path_from_source(self, context):
    """Auto-update export path when source path changes"""
    if self.source_path and not self.export_path:
        # Try to extract video name from the source path structure
        # Source path could be something like: /path/to/video_name_colmap_output/transformed
        source_parts = self.source_path.split(os.sep)
        
        # Look for a folder that ends with '_colmap_output'
        video_name = None
        parent_dir = None
        for i, part in enumerate(source_parts):
            if part.endswith('_colmap_output'):
                video_name = part[:-14]  # Remove '_colmap_output' suffix
                parent_dir = os.sep.join(source_parts[:i])
                break
        
        if video_name and parent_dir:
            self.export_path = os.path.join(parent_dir, f"{video_name}_brush_output")
        else:
            # Fallback to a brush_output folder next to the source
            parent_dir = os.path.dirname(os.path.dirname(self.source_path))
            self.export_path = os.path.join(parent_dir, "brush_output")

def get_default_brush_path():
    """Get default brush executable path based on operating system"""
    system = platform.system()
    
    # First priority: Check for bundled binaries
    if system in BUNDLED_BINARY_NAMES:
        bundled_binary_name = BUNDLED_BINARY_NAMES[system]
        bundled_path = os.path.join(get_bundled_binaries_directory(), bundled_binary_name)
        if os.path.exists(bundled_path):
            return bundled_path
    
    # Fallback: Check for user-compiled binaries in default locations
    home = os.path.expanduser("~")
    
    if system == "Windows":
        user_path = os.path.join(home, "projects", "brush", "target", "release", "brush_app.exe")
    elif system == "Darwin":  # macOS
        user_path = os.path.join(home, "projects", "brush", "target", "release", "brush_app")
    elif system == "Linux":
        user_path = os.path.join(home, "projects", "brush", "target", "release", "brush_app")
    else:
        return ""
    
    if os.path.exists(user_path):
        return user_path
    
    # If neither bundled nor user-compiled binary exists, return the bundled path as default
    # This will allow users to see where the bundled binary should be located
    if system in BUNDLED_BINARY_NAMES:
        bundled_binary_name = BUNDLED_BINARY_NAMES[system]
        return os.path.join(get_bundled_binaries_directory(), bundled_binary_name)
    
    return ""

class SplatInstance(PropertyGroup):
    """Individual Gaussian Splatting instance with its own settings"""
    name: StringProperty(
        name="Instance Name",
        description="Name for this splat instance",
        default="Splat"
    )
    
    # Path settings
    source_path: StringProperty(
        name="Source Path",
        description="Path to COLMAP model directory",
        subtype='DIR_PATH',
        update=update_export_path_from_source
    )
    
    export_path: StringProperty(
        name="Export Path",
        description="Location to put exported files",
        subtype='DIR_PATH'
    )
    
    export_name: StringProperty(
        name="Export Name",
        description="Filename pattern for exported ply files",
        default="export_{iter}.ply"
    )
    
    # Training options
    total_steps: IntProperty(
        name="Total Steps",
        description="Total number of steps to train for",
        default=30000,
        min=1000
    )
    
    ssim_weight: FloatProperty(
        name="SSIM Weight",
        description="Weight of SSIM loss (compared to l1 loss)",
        default=0.2,
        min=0.0,
        max=1.0
    )
    
    # Learning rates
    lr_mean: FloatProperty(
        name="LR Mean",
        description="Start learning rate for the mean parameters",
        default=4e-5,
        min=1e-8,
        max=1e-1
    )
    
    lr_mean_end: FloatProperty(
        name="LR Mean End",
        description="End learning rate for the mean parameters",
        default=4e-7,
        min=1e-8,
        max=1e-1
    )
    
    lr_coeffs_dc: FloatProperty(
        name="LR Coeffs DC",
        description="Learning rate for the base SH (RGB) coefficients",
        default=3e-3,
        min=1e-6,
        max=1e-1
    )
    
    lr_opac: FloatProperty(
        name="LR Opacity",
        description="Learning rate for the opacity parameter",
        default=3e-2,
        min=1e-6,
        max=1e-1
    )
    
    lr_scale: FloatProperty(
        name="LR Scale",
        description="Learning rate for the scale parameters",
        default=1e-2,
        min=1e-6,
        max=1e-1
    )
    
    lr_rotation: FloatProperty(
        name="LR Rotation",
        description="Learning rate for the rotation parameters",
        default=1e-3,
        min=1e-6,
        max=1e-1
    )
    
    # Dataset options
    max_frames: IntProperty(
        name="Max Frames",
        description="Max number of frames to load (0 = all)",
        default=0,
        min=0
    )
    
    max_resolution: IntProperty(
        name="Max Resolution",
        description="Max resolution of images to load",
        default=1920,
        min=256
    )
    
    eval_split_every: IntProperty(
        name="Eval Split Every",
        description="Create eval dataset by selecting every nth image (0 = disabled)",
        default=0,
        min=0
    )
    
    subsample_frames: IntProperty(
        name="Subsample Frames",
        description="Load only every nth frame (1 = all frames)",
        default=1,
        min=1
    )
    
    subsample_points: IntProperty(
        name="Subsample Points",
        description="Load only every nth point from initial SfM data (1 = all points)",
        default=1,
        min=1
    )
    
    # Refine options
    refine_every: IntProperty(
        name="Refine Every",
        description="Frequency of refinement (splat replacement/densification)",
        default=150,
        min=10
    )
    
    growth_grad_threshold: FloatProperty(
        name="Growth Gradient Threshold",
        description="Threshold to control splat growth (lower = faster growth)",
        default=0.00085,
        min=0.0001,
        max=0.01
    )
    
    growth_select_fraction: FloatProperty(
        name="Growth Select Fraction",
        description="Fraction of splats that grow (increase for more aggressive growth)",
        default=0.1,
        min=0.01,
        max=1.0
    )
    
    growth_stop_iter: IntProperty(
        name="Growth Stop Iteration",
        description="Period after which splat growth stops",
        default=12500,
        min=1000
    )
    
    max_splats: IntProperty(
        name="Max Splats",
        description="Maximum number of splats",
        default=10000000,
        min=100000
    )
    
    # Model options
    sh_degree: IntProperty(
        name="SH Degree",
        description="SH degree of splats",
        default=3,
        min=0,
        max=4
    )
    
    # Process options
    with_viewer: BoolProperty(
        name="With Viewer",
        description="Spawn a viewer to visualize the training",
        default=True
    )
    
    eval_every: IntProperty(
        name="Eval Every",
        description="Evaluate every this many steps",
        default=1000,
        min=100
    )
    
    export_every: IntProperty(
        name="Export Every",
        description="Export every this many steps",
        default=5000,
        min=100
    )
    
    eval_save_to_disk: BoolProperty(
        name="Save Eval Images",
        description="Save rendered eval images to disk",
        default=False
    )
    
    seed: IntProperty(
        name="Random Seed",
        description="Random seed for reproducibility",
        default=42,
        min=0
    )
    
    start_iter: IntProperty(
        name="Start Iteration",
        description="Iteration to resume from",
        default=0,
        min=0
    )
    
    # Status flags
    is_training: BoolProperty(
        name="Is Training",
        description="Whether this instance is currently training",
        default=False
    )
    
    training_completed: BoolProperty(
        name="Training Completed",
        description="Whether training has completed for this instance",
        default=False
    )

class SkySplatBrushProperties(PropertyGroup):
    """Main property group for Gaussian Splatting management"""
    splat_instances: bpy.props.CollectionProperty(
        type=SplatInstance,
        name="Splat Instances",
        description="Collection of Gaussian Splatting instances"
    )
    
    active_splat_index: IntProperty(
        name="Active Splat Index",
        description="Index of the currently active splat instance",
        default=0,
        min=0
    )
    
    # Brush executable path (shared across all instances)
    brush_executable: StringProperty(
        name="Brush Executable",
        description="Path to the brush executable",
        subtype='FILE_PATH',
        default=get_default_brush_path()
    )
    
    # Advanced options toggle
    show_advanced: BoolProperty(
        name="Show Advanced Options",
        description="Show advanced training parameters",
        default=False
    )
    
    show_learning_rates: BoolProperty(
        name="Show Learning Rates",
        description="Show learning rate parameters",
        default=False
    )
    
    # Legacy properties for backward compatibility
    source_path: StringProperty(
        name="Source Path",
        description="Path to COLMAP model directory (legacy)",
        subtype='DIR_PATH',
        update=update_export_path_from_source
    )
    
    export_path: StringProperty(
        name="Export Path",
        description="Location to put exported files (legacy)",
        subtype='DIR_PATH'
    )
    
    export_name: StringProperty(
        name="Export Name",
        description="Filename pattern for exported ply files (legacy)",
        default="export_{iter}.ply"
    )
    
    total_steps: IntProperty(
        name="Total Steps",
        description="Total number of steps to train for (legacy)",
        default=30000,
        min=1000
    )
    
    def update_from_colmap_panel(self, context):
        """Update paths from COLMAP panel settings"""
        if hasattr(context.scene, 'skysplat_colmap_props'):
            colmap_props = context.scene.skysplat_colmap_props
            
            # Get active COLMAP instance
            if len(colmap_props.colmap_instances) > 0:
                colmap_instance = colmap_props.colmap_instances[colmap_props.active_colmap_index]
                
                if colmap_instance.output_folder:
                    # Get or create matching splat instance
                    if len(self.splat_instances) == 0:
                        splat_instance = self.splat_instances.add()
                        splat_instance.name = f"Splat_{colmap_instance.name}"
                        self.active_splat_index = 0
                    else:
                        splat_instance = self.splat_instances[self.active_splat_index]
                    
                    # Prioritize brush_dataset if it exists
                    brush_dataset_path = os.path.join(os.path.dirname(colmap_instance.output_folder), "brush_dataset")
                    if os.path.exists(brush_dataset_path):
                        splat_instance.source_path = brush_dataset_path
                    else:
                        # Use transformed model if it exists, otherwise use sparse model
                        transformed_path = os.path.join(colmap_instance.output_folder, "transformed")
                        if os.path.exists(transformed_path):
                            splat_instance.source_path = transformed_path
                        else:
                            sparse_path = os.path.join(colmap_instance.output_folder, "sparse", "0")
                            if os.path.exists(sparse_path):
                                splat_instance.source_path = sparse_path
                    
                    # Set export path with video name prefix
                    if not splat_instance.export_path:
                        # Extract video name from colmap output folder path
                        output_folder_name = os.path.basename(colmap_instance.output_folder)
                        if output_folder_name.endswith('_colmap_output'):
                            video_name = output_folder_name[:-14]  # Remove '_colmap_output' suffix
                            parent_dir = os.path.dirname(colmap_instance.output_folder)
                            splat_instance.export_path = os.path.join(parent_dir, f"{video_name}_brush_output")
                        else:
                            # Fallback to generic name if pattern doesn't match
                            splat_instance.export_path = os.path.join(colmap_instance.output_folder, "brush_output")

class SKY_SPLAT_OT_add_splat_instance(Operator):
    bl_idname = "skysplat.add_splat_instance"
    bl_label = "Add Splat Instance"
    bl_description = "Add a new Gaussian Splatting instance"
    
    def execute(self, context):
        props = context.scene.skysplat_brush_props
        new_instance = props.splat_instances.add()
        new_instance.name = f"Splat_{len(props.splat_instances)}"
        props.active_splat_index = len(props.splat_instances) - 1
        self.report({'INFO'}, f"Added splat instance: {new_instance.name}")
        return {'FINISHED'}

class SKY_SPLAT_OT_remove_splat_instance(Operator):
    bl_idname = "skysplat.remove_splat_instance"
    bl_label = "Remove Splat Instance"
    bl_description = "Remove the active splat instance"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_brush_props
        return len(props.splat_instances) > 0
    
    def execute(self, context):
        props = context.scene.skysplat_brush_props
        if len(props.splat_instances) > 0:
            props.splat_instances.remove(props.active_splat_index)
            props.active_splat_index = max(0, props.active_splat_index - 1)
            self.report({'INFO'}, "Removed splat instance")
        return {'FINISHED'}

class SKY_SPLAT_OT_sync_brush_with_colmap(Operator):
    bl_idname = "skysplat.sync_brush_with_colmap"
    bl_label = "Sync with COLMAP"
    bl_description = "Set paths based on COLMAP output"
    
    def execute(self, context):
        props = context.scene.skysplat_brush_props
        props.update_from_colmap_panel(context)
        self.report({'INFO'}, "Paths synchronized with COLMAP output")
        return {'FINISHED'}

class SKY_SPLAT_OT_run_brush_training(Operator):
    bl_idname = "skysplat.run_brush_training"
    bl_label = "Train with Brush"
    bl_description = "Run Brush training on the COLMAP data"
    
    _timer = None
    _thread = None
    _process = None
    _finished = False
    _output_lines = []
    _instance_index = -1
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_brush_props
        if len(props.splat_instances) == 0:
            return False
        splat_instance = props.splat_instances[props.active_splat_index]
        return (props.brush_executable and 
                splat_instance.source_path and 
                os.path.exists(splat_instance.source_path) and
                not splat_instance.is_training)
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if self._finished:
                self.cancel(context)
                props = context.scene.skysplat_brush_props
                if self._instance_index >= 0 and self._instance_index < len(props.splat_instances):
                    splat_instance = props.splat_instances[self._instance_index]
                    splat_instance.is_training = False
                    if self._process and self._process.returncode == 0:
                        splat_instance.training_completed = True
                        self.report({'INFO'}, f"Brush training completed for {splat_instance.name}!")
                    else:
                        self.report({'ERROR'}, f"Brush training failed for {splat_instance.name}!")
                return {'FINISHED'}
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process = None
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None
    
    def execute(self, context):
        props = context.scene.skysplat_brush_props
        splat_instance = props.splat_instances[props.active_splat_index]
        
        # Validate brush executable
        if not props.brush_executable:
            self.report({'ERROR'}, "Brush executable not specified")
            return {'CANCELLED'}
        
        # Validate source path
        if not splat_instance.source_path or not os.path.exists(splat_instance.source_path):
            self.report({'ERROR'}, "Source path does not exist")
            return {'CANCELLED'}
        
        # Create export directory if specified
        if splat_instance.export_path:
            os.makedirs(splat_instance.export_path, exist_ok=True)
        
        # Build command
        try:
            command = self.build_brush_command(props, splat_instance)
            print(f"Running Brush command for {splat_instance.name}: {' '.join(command)}")
            
            # Reset state
            self._finished = False
            self._output_lines = []
            self._instance_index = props.active_splat_index
            
            # Mark as training
            splat_instance.is_training = True
            
            # Start training in a separate thread
            self._thread = threading.Thread(target=self.run_training, args=(command, splat_instance))
            self._thread.start()
            
            # Start modal timer
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            
            self.report({'INFO'}, f"Started Brush training for {splat_instance.name}...")
            return {'RUNNING_MODAL'}
            
        except Exception as e:
            splat_instance.is_training = False
            self.report({'ERROR'}, f"Failed to start training: {str(e)}")
            return {'CANCELLED'}
    
    def build_brush_command(self, props, splat_instance):
        from ..services.brush import BrushParams, build_command
        params = BrushParams(
            executable=props.brush_executable,
            source_path=splat_instance.source_path,
            export_path=splat_instance.export_path,
            export_name=splat_instance.export_name,
            total_steps=splat_instance.total_steps,
            ssim_weight=splat_instance.ssim_weight,
            lr_mean=splat_instance.lr_mean,
            lr_mean_end=splat_instance.lr_mean_end,
            lr_coeffs_dc=splat_instance.lr_coeffs_dc,
            lr_opac=splat_instance.lr_opac,
            lr_scale=splat_instance.lr_scale,
            lr_rotation=splat_instance.lr_rotation,
            max_resolution=splat_instance.max_resolution,
            subsample_frames=splat_instance.subsample_frames,
            subsample_points=splat_instance.subsample_points,
            max_frames=splat_instance.max_frames,
            eval_split_every=splat_instance.eval_split_every,
            refine_every=splat_instance.refine_every,
            growth_grad_threshold=splat_instance.growth_grad_threshold,
            growth_select_fraction=splat_instance.growth_select_fraction,
            growth_stop_iter=splat_instance.growth_stop_iter,
            max_splats=splat_instance.max_splats,
            sh_degree=splat_instance.sh_degree,
            eval_every=splat_instance.eval_every,
            export_every=splat_instance.export_every,
            seed=splat_instance.seed,
            start_iter=splat_instance.start_iter,
            with_viewer=splat_instance.with_viewer,
            eval_save_to_disk=splat_instance.eval_save_to_disk,
        )
        return build_command(params)
    
    def run_training(self, command, splat_instance):
        """Run the training process"""
        try:
            # Run the command
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in self._process.stdout:
                self._output_lines.append(line.strip())
                print(f"Brush ({splat_instance.name}): {line.strip()}")  # Print to console
            
            # Wait for process to complete
            self._process.wait()
            
            if self._process.returncode == 0:
                print(f"Brush training completed successfully for {splat_instance.name}!")
            else:
                print(f"Brush training failed for {splat_instance.name} with code: {self._process.returncode}")
            
        except Exception as e:
            print(f"Error running Brush for {splat_instance.name}: {str(e)}")
        finally:
            self._finished = True

class SKY_SPLAT_PT_gaussian_splatting_panel(Panel):  
    bl_label = "SkySplat - Gaussian Splatting (Brush)"  
    bl_idname = "SKY_SPLAT_PT_gaussian_splatting_panel"  
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SkySplat"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.skysplat_brush_props
        
        # Brush executable (shared)
        box = layout.box()
        box.label(text="Brush Settings")
        box.prop(props, "brush_executable")
        
        # Splat instance management
        box = layout.box()
        box.label(text="Splat Instances", icon='OUTLINER_OB_POINTCLOUD')
        
        row = box.row()
        row.template_list("UI_UL_list", "splat_instances", props, "splat_instances", 
                         props, "active_splat_index", rows=3)
        
        col = row.column(align=True)
        col.operator("skysplat.add_splat_instance", icon='ADD', text="")
        col.operator("skysplat.remove_splat_instance", icon='REMOVE', text="")
        
        # Show active splat instance settings
        if len(props.splat_instances) > 0 and props.active_splat_index < len(props.splat_instances):
            splat_instance = props.splat_instances[props.active_splat_index]
            
            # Instance name
            box.prop(splat_instance, "name")
            
            # Path settings
            box = layout.box()
            box.label(text="Input/Output Paths")
            
            row = box.row()
            row.prop(splat_instance, "source_path")
            row.operator("skysplat.sync_brush_with_colmap", icon='LINKED', text="")
            
            box.prop(splat_instance, "export_path")
            box.prop(splat_instance, "export_name")
            
            # Basic training parameters
            box = layout.box()
            box.label(text="Basic Training Parameters")
            box.prop(splat_instance, "total_steps")
            box.prop(splat_instance, "max_resolution")
            box.prop(splat_instance, "with_viewer")
            
            # Dataset options
            box = layout.box()
            box.label(text="Dataset Options")
            box.prop(splat_instance, "max_frames")
            box.prop(splat_instance, "subsample_frames")
            box.prop(splat_instance, "subsample_points")
            box.prop(splat_instance, "eval_split_every")
            
            # Export settings
            box = layout.box()
            box.label(text="Export Settings")
            box.prop(splat_instance, "export_every")
            box.prop(splat_instance, "eval_every")
            box.prop(splat_instance, "eval_save_to_disk")
            box.prop(splat_instance, "start_iter")
            
            # Advanced options toggle
            box = layout.box()
            box.prop(props, "show_advanced", icon='TRIA_DOWN' if props.show_advanced else 'TRIA_RIGHT')
            
            if props.show_advanced:
                # Advanced training parameters
                sub_box = box.box()
                sub_box.label(text="Advanced Training")
                sub_box.prop(splat_instance, "ssim_weight")
                sub_box.prop(splat_instance, "seed")
                sub_box.prop(splat_instance, "sh_degree")
                
                # Learning rates toggle
                sub_box.prop(props, "show_learning_rates", icon='TRIA_DOWN' if props.show_learning_rates else 'TRIA_RIGHT')
                if props.show_learning_rates:
                    lr_box = sub_box.box()
                    lr_box.label(text="Learning Rates")
                    lr_box.prop(splat_instance, "lr_mean")
                    lr_box.prop(splat_instance, "lr_mean_end")
                    lr_box.prop(splat_instance, "lr_coeffs_dc")
                    lr_box.prop(splat_instance, "lr_opac")
                    lr_box.prop(splat_instance, "lr_scale")
                    lr_box.prop(splat_instance, "lr_rotation")
                
                # Refinement parameters
                sub_box = box.box()
                sub_box.label(text="Refinement")
                sub_box.prop(splat_instance, "refine_every")
                sub_box.prop(splat_instance, "growth_grad_threshold")
                sub_box.prop(splat_instance, "growth_select_fraction")
                sub_box.prop(splat_instance, "growth_stop_iter")
                sub_box.prop(splat_instance, "max_splats")
            
            # Run button
            layout.separator()
            row = layout.row()
            if splat_instance.is_training:
                row.label(text="Training in progress...", icon='TIME')
            else:
                row.operator("skysplat.run_brush_training", icon='PLAY', text="Run Brush Training")
                if splat_instance.training_completed:
                    row.label(text="✓ Completed", icon='CHECKMARK')
            
            if not SKY_SPLAT_OT_run_brush_training.poll(context):
                layout.label(text="Configure paths to enable training", icon='ERROR')
            
            # Info about multiple instances
            box = layout.box()
            box.label(text="💡 Tip: You can train multiple splats", icon='INFO')
            box.label(text="from different COLMAP models simultaneously")
        else:
            box.label(text="Add a splat instance to begin", icon='INFO')
        
        # Version indicator
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")

# Registration
classes = (
    SplatInstance,
    SkySplatBrushProperties,
    SKY_SPLAT_OT_add_splat_instance,
    SKY_SPLAT_OT_remove_splat_instance,
    SKY_SPLAT_OT_sync_brush_with_colmap,
    SKY_SPLAT_OT_run_brush_training,
    SKY_SPLAT_PT_gaussian_splatting_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.skysplat_brush_props = bpy.props.PointerProperty(type=SkySplatBrushProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.skysplat_brush_props

if __name__ == "__main__":
    register()
