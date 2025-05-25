import bpy
import os
import subprocess
import threading
import platform
import logging
from bpy.props import StringProperty, IntProperty, BoolProperty

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SkySplat.GaussianSplatting')

PANEL_VERSION = "0.1.0"

class SKY_SPLAT_GaussianSplattingProperties(bpy.types.PropertyGroup):
    """Properties for Gaussian Splatting processing"""
    
    # Path to the gaussian-splatting repository
    gs_repo_path: StringProperty(
        name="3DGS Repository Path",
        description="Path to the gaussian-splatting repository folder",
        subtype='DIR_PATH',
        default=""
    )
    
    # Python environment settings
    use_venv: BoolProperty(
        name="Use Virtual Environment",
        description="Use a Python virtual environment for gaussian-splatting",
        default=True
    )
    
    venv_path: StringProperty(
        name="Virtual Environment Path",
        description="Path to the Python virtual environment (leave empty to use repo's venv)",
        subtype='DIR_PATH',
        default=""
    )
    
    # Training parameters
    source_path: StringProperty(
        name="Source Path (-s)",
        description="Path to COLMAP output folder",
        subtype='DIR_PATH',
        default=""
    )
    
    images_path: StringProperty(
        name="Images Path (-i)",
        description="Path to input images folder",
        subtype='DIR_PATH',
        default=""
    )
    
    model_path: StringProperty(
        name="Model Output Path (-m)",
        description="Path where the trained model will be saved",
        subtype='DIR_PATH',
        default=""
    )
    
    resolution: IntProperty(
        name="Resolution (-r)",
        description="Resolution for training",
        default=3000,
        min=1
    )
    
    test_iterations: IntProperty(
        name="Test Iterations",
        description="Test iterations (-1 for default)",
        default=-1
    )
    
    # Additional options
    additional_args: StringProperty(
        name="Additional Arguments",
        description="Any additional command line arguments",
        default=""
    )
    
    def update_from_colmap_panel(self, context):
        """Update paths based on COLMAP output"""
        if hasattr(context.scene, 'skysplat_colmap_props'):
            colmap_props = context.scene.skysplat_colmap_props
            
            if colmap_props.output_folder:
                # Set source path to COLMAP output
                self.source_path = colmap_props.output_folder
                
                # Set images path to the input subfolder
                self.images_path = os.path.join(colmap_props.output_folder, "input")
                
                # Create gaussian splatting output folder
                video_props = context.scene.skysplat_props
                if video_props.video_path:
                    video_path = bpy.path.abspath(video_props.video_path)
                    video_dir = os.path.dirname(video_path)
                    video_name = os.path.splitext(os.path.basename(video_path))[0]
                    self.model_path = os.path.join(video_dir, f"{video_name}_gaussian_splatting_output")


class SKY_SPLAT_OT_sync_gs_with_colmap(bpy.types.Operator):
    bl_idname = "skysplat.sync_gs_with_colmap"
    bl_label = "Sync with COLMAP"
    bl_description = "Set paths based on COLMAP output"
    
    def execute(self, context):
        props = context.scene.skysplat_gaussian_splatting_props
        props.update_from_colmap_panel(context)
        self.report({'INFO'}, "Paths synchronized with COLMAP output")
        return {'FINISHED'}


class SKY_SPLAT_OT_run_gaussian_splatting(bpy.types.Operator):
    bl_idname = "skysplat.run_gaussian_splatting"
    bl_label = "Train Gaussian Splatting"
    bl_description = "Run gaussian-splatting training on the processed data"
    
    _timer = None
    _thread = None
    _process = None
    _finished = False
    _output_lines = []
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_gaussian_splatting_props
        return (props.gs_repo_path and 
                os.path.exists(props.gs_repo_path) and
                props.source_path and 
                props.images_path and 
                props.model_path)
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            # Check if process is finished
            if self._finished:
                self.report({'INFO'}, "Gaussian Splatting training completed!")
                self.cancel(context)
                return {'FINISHED'}
            
            # Update status in UI if needed
            # You could add a progress property here to show status
            
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process = None
    
    def execute(self, context):
        props = context.scene.skysplat_gaussian_splatting_props
        
        # Create output directory
        os.makedirs(props.model_path, exist_ok=True)
        
        # Build command
        command = self.build_command(props)
        
        # Log the full command
        command_str = ' '.join(command)
        logger.info(f"Running 3DGS command: {command_str}")
        print(f"3DGS Command: {command_str}")  # Also print to console for visibility
        
        # Start training in a separate thread
        self._finished = False
        self._thread = threading.Thread(target=self.run_training, args=(command, props))
        self._thread.start()
        
        # Add timer for modal updates
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, "Started Gaussian Splatting training...")
        return {'RUNNING_MODAL'}
    
    def build_command(self, props):
        """Build the command to run gaussian-splatting"""
        # Get python executable
        if props.use_venv:
            if props.venv_path:
                venv_path = props.venv_path
            else:
                # Try to find venv in the repo
                venv_path = os.path.join(props.gs_repo_path, "venv")
                if not os.path.exists(venv_path):
                    venv_path = os.path.join(props.gs_repo_path, ".venv")
            
            # Get python executable from venv
            if platform.system() == "Windows":
                python_exe = os.path.join(venv_path, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(venv_path, "bin", "python")
        else:
            python_exe = "python"
        
        # Build command
        train_script = os.path.join(props.gs_repo_path, "train.py")
        
        cmd = [
            python_exe,
            train_script,
            "-s", props.source_path,
            "-i", props.images_path,
            "-m", props.model_path,
            "--test_iterations", str(props.test_iterations),
            "-r", str(props.resolution)
        ]
        
        # Add additional arguments if any
        if props.additional_args:
            cmd.extend(props.additional_args.split())
        
        return cmd
    
    def run_training(self, command, props):
        """Run the training process"""
        try:
            # Change to repo directory
            cwd = props.gs_repo_path
            
            # Run the command
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=cwd,
                bufsize=1
            )
            
            # Read output line by line
            for line in self._process.stdout:
                self._output_lines.append(line.strip())
                print(f"3DGS: {line.strip()}")  # Print to console
            
            # Wait for process to complete
            self._process.wait()
            
            if self._process.returncode == 0:
                logger.info("Gaussian Splatting training completed successfully!")
                print("Gaussian Splatting training completed successfully!")
            else:
                logger.error(f"Gaussian Splatting training failed with code: {self._process.returncode}")
                print(f"Gaussian Splatting training failed with code: {self._process.returncode}")
            
        except Exception as e:
            logger.error(f"Error running Gaussian Splatting: {str(e)}")
            print(f"Error running Gaussian Splatting: {str(e)}")
        finally:
            self._finished = True


class SKY_SPLAT_PT_gaussian_splatting_panel(bpy.types.Panel):
    bl_label = "SkySplat 3DGS"
    bl_idname = "SKY_SPLAT_PT_gaussian_splatting_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SkySplat"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.skysplat_gaussian_splatting_props
        
        # Repository settings
        box = layout.box()
        box.label(text="3DGS Repository Settings")
        box.prop(props, "gs_repo_path")
        
        row = box.row()
        row.prop(props, "use_venv")
        if props.use_venv:
            box.prop(props, "venv_path")
        
        # Path settings
        box = layout.box()
        box.label(text="Input/Output Paths")
        
        row = box.row()
        row.prop(props, "source_path")
        row.operator("skysplat.sync_gs_with_colmap", icon='LINKED', text="")
        
        box.prop(props, "images_path")
        box.prop(props, "model_path")
        
        # Training parameters
        box = layout.box()
        box.label(text="Training Parameters")
        box.prop(props, "resolution")
        box.prop(props, "test_iterations")
        box.prop(props, "additional_args")
        
        # Run button
        layout.operator("skysplat.run_gaussian_splatting", icon='PLAY')
        
        # Version indicator
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")


# Register classes
classes = (
    SKY_SPLAT_GaussianSplattingProperties,
    SKY_SPLAT_OT_sync_gs_with_colmap,
    SKY_SPLAT_OT_run_gaussian_splatting,
    SKY_SPLAT_PT_gaussian_splatting_panel,
)