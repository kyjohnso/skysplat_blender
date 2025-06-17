import bpy
import os
import subprocess
import threading
import platform
from bpy.types import PropertyGroup, Panel, Operator
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, PointerProperty

# Version for UI display
PANEL_VERSION = "0.2.0-brush"

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
    home = os.path.expanduser("~")
    
    if system == "Windows":
        return os.path.join(home, "projects", "brush", "target", "release", "brush_app.exe")
    elif system == "Darwin":  # macOS
        return os.path.join(home, "projects", "brush", "target", "release", "brush_app")
    elif system == "Linux":
        return os.path.join(home, "projects", "brush", "target", "release", "brush_app")
    
    return ""

class SkySplatBrushProperties(PropertyGroup):
    # Brush executable path
    brush_executable: StringProperty(
        name="Brush Executable",
        description="Path to the brush executable",
        subtype='FILE_PATH',
        default=get_default_brush_path()
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
        default=False
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
    
    def update_from_colmap_panel(self, context):
        """Update paths from COLMAP panel settings"""
        if hasattr(context.scene, 'skysplat_colmap_props'):
            colmap_props = context.scene.skysplat_colmap_props
            if colmap_props.output_folder:
                # Prioritize brush_dataset if it exists
                brush_dataset_path = os.path.join(colmap_props.output_folder, "brush_dataset")
                if os.path.exists(brush_dataset_path):
                    self.source_path = brush_dataset_path
                else:
                    # Use transformed model if it exists, otherwise use sparse model
                    transformed_path = os.path.join(colmap_props.output_folder, "transformed")
                    if os.path.exists(transformed_path):
                        self.source_path = transformed_path
                    else:
                        sparse_path = os.path.join(colmap_props.output_folder, "sparse", "0")
                        if os.path.exists(sparse_path):
                            self.source_path = sparse_path
                
                # Set export path with video name prefix
                if not self.export_path:
                    # Extract video name from colmap output folder path
                    # colmap_output_folder typically follows pattern: {video_name}_colmap_output
                    output_folder_name = os.path.basename(colmap_props.output_folder)
                    if output_folder_name.endswith('_colmap_output'):
                        video_name = output_folder_name[:-14]  # Remove '_colmap_output' suffix
                        parent_dir = os.path.dirname(colmap_props.output_folder)
                        self.export_path = os.path.join(parent_dir, f"{video_name}_brush_output")
                    else:
                        # Fallback to generic name if pattern doesn't match
                        self.export_path = os.path.join(colmap_props.output_folder, "brush_output")

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
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_brush_props
        return (props.brush_executable and 
                props.source_path and 
                os.path.exists(props.source_path))
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if self._finished:
                self.cancel(context)
                if self._process and self._process.returncode == 0:
                    self.report({'INFO'}, "Brush training completed successfully!")
                else:
                    self.report({'ERROR'}, "Brush training failed!")
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
        
        # Validate brush executable
        if not props.brush_executable:
            self.report({'ERROR'}, "Brush executable not specified")
            return {'CANCELLED'}
        
        # Validate source path
        if not props.source_path or not os.path.exists(props.source_path):
            self.report({'ERROR'}, "Source path does not exist")
            return {'CANCELLED'}
        
        # Create export directory if specified
        if props.export_path:
            os.makedirs(props.export_path, exist_ok=True)
        
        # Build command
        try:
            command = self.build_brush_command(props)
            print(f"Running Brush command: {' '.join(command)}")
            
            # Reset state
            self._finished = False
            self._output_lines = []
            
            # Start training in a separate thread
            self._thread = threading.Thread(target=self.run_training, args=(command, props))
            self._thread.start()
            
            # Start modal timer
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            
            self.report({'INFO'}, "Started Brush training...")
            return {'RUNNING_MODAL'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start training: {str(e)}")
            return {'CANCELLED'}
    
    def build_brush_command(self, props):
        """Build the complete command to run Brush training"""
        cmd = [props.brush_executable]
        
        # Add source path as positional argument
        if props.source_path:
            cmd.append(props.source_path)
        
        # Training options
        cmd.extend([
            "--total-steps", str(props.total_steps),
            "--ssim-weight", str(props.ssim_weight),
            "--lr-mean", str(props.lr_mean),
            "--lr-mean-end", str(props.lr_mean_end),
            "--lr-coeffs-dc", str(props.lr_coeffs_dc),
            "--lr-opac", str(props.lr_opac),
            "--lr-scale", str(props.lr_scale),
            "--lr-rotation", str(props.lr_rotation)
        ])
        
        # Dataset options
        cmd.extend([
            "--max-resolution", str(props.max_resolution),
            "--subsample-frames", str(props.subsample_frames),
            "--subsample-points", str(props.subsample_points)
        ])
        
        if props.max_frames > 0:
            cmd.extend(["--max-frames", str(props.max_frames)])
        
        if props.eval_split_every > 0:
            cmd.extend(["--eval-split-every", str(props.eval_split_every)])
        
        # Refine options
        cmd.extend([
            "--refine-every", str(props.refine_every),
            "--growth-grad-threshold", str(props.growth_grad_threshold),
            "--growth-select-fraction", str(props.growth_select_fraction),
            "--growth-stop-iter", str(props.growth_stop_iter),
            "--max-splats", str(props.max_splats)
        ])
        
        # Model options
        cmd.extend([
            "--sh-degree", str(props.sh_degree)
        ])
        
        # Process options
        cmd.extend([
            "--eval-every", str(props.eval_every),
            "--export-every", str(props.export_every),
            "--seed", str(props.seed)
        ])
        
        if props.start_iter > 0:
            cmd.extend(["--start-iter", str(props.start_iter)])
        
        # Optional flags
        if props.with_viewer:
            cmd.append("--with-viewer")
        
        if props.eval_save_to_disk:
            cmd.append("--eval-save-to-disk")
        
        # Export settings
        if props.export_path:
            cmd.extend(["--export-path", props.export_path])
        
        if props.export_name != "export_{iter}.ply":
            cmd.extend(["--export-name", props.export_name])
        
        return cmd
    
    def run_training(self, command, props):
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
                print(f"Brush: {line.strip()}")  # Print to console
            
            # Wait for process to complete
            self._process.wait()
            
            if self._process.returncode == 0:
                print("Brush training completed successfully!")
            else:
                print(f"Brush training failed with code: {self._process.returncode}")
            
        except Exception as e:
            print(f"Error running Brush: {str(e)}")
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
        
        # Brush executable
        box = layout.box()
        box.label(text="Brush Settings")
        box.prop(props, "brush_executable")
        
        # Path settings
        box = layout.box()
        box.label(text="Input/Output Paths")
        
        row = box.row()
        row.prop(props, "source_path")
        row.operator("skysplat.sync_brush_with_colmap", icon='LINKED', text="")
        
        box.prop(props, "export_path")
        box.prop(props, "export_name")
        
        # Basic training parameters
        box = layout.box()
        box.label(text="Basic Training Parameters")
        box.prop(props, "total_steps")
        box.prop(props, "max_resolution")
        box.prop(props, "with_viewer")
        
        # Dataset options
        box = layout.box()
        box.label(text="Dataset Options")
        box.prop(props, "max_frames")
        box.prop(props, "subsample_frames")
        box.prop(props, "subsample_points")
        box.prop(props, "eval_split_every")
        
        # Export settings
        box = layout.box()
        box.label(text="Export Settings")
        box.prop(props, "export_every")
        box.prop(props, "eval_every")
        box.prop(props, "eval_save_to_disk")
        box.prop(props, "start_iter")
        
        # Advanced options toggle
        box = layout.box()
        box.prop(props, "show_advanced", icon='TRIA_DOWN' if props.show_advanced else 'TRIA_RIGHT')
        
        if props.show_advanced:
            # Advanced training parameters
            sub_box = box.box()
            sub_box.label(text="Advanced Training")
            sub_box.prop(props, "ssim_weight")
            sub_box.prop(props, "seed")
            sub_box.prop(props, "sh_degree")
            
            # Learning rates toggle
            sub_box.prop(props, "show_learning_rates", icon='TRIA_DOWN' if props.show_learning_rates else 'TRIA_RIGHT')
            if props.show_learning_rates:
                lr_box = sub_box.box()
                lr_box.label(text="Learning Rates")
                lr_box.prop(props, "lr_mean")
                lr_box.prop(props, "lr_mean_end")
                lr_box.prop(props, "lr_coeffs_dc")
                lr_box.prop(props, "lr_opac")
                lr_box.prop(props, "lr_scale")
                lr_box.prop(props, "lr_rotation")
            
            # Refinement parameters
            sub_box = box.box()
            sub_box.label(text="Refinement")
            sub_box.prop(props, "refine_every")
            sub_box.prop(props, "growth_grad_threshold")
            sub_box.prop(props, "growth_select_fraction")
            sub_box.prop(props, "growth_stop_iter")
            sub_box.prop(props, "max_splats")
        
        # Run button
        layout.separator()
        op = layout.operator("skysplat.run_brush_training", icon='PLAY', text="Run Brush Training")
        if not SKY_SPLAT_OT_run_brush_training.poll(context):
            layout.label(text="Configure paths to enable training", icon='ERROR')
        
        # Version indicator
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")

# Registration
classes = (
    SkySplatBrushProperties,
    SKY_SPLAT_OT_sync_brush_with_colmap,
    SKY_SPLAT_OT_run_brush_training,
    SKY_SPLAT_PT_gaussian_splatting_panel,  # Change this line
)
