import bpy
import os
import subprocess
import threading
import platform
import time
from bpy.types import Operator

class SKY_SPLAT_OT_run_colmap_gui(Operator):
    bl_idname = "skysplat.run_colmap_gui"
    bl_label = "Run COLMAP GUI"
    bl_description = "Launch COLMAP GUI in background for interactive processing"
    
    # Use class variables to avoid StructRNA reference issues
    _timer = None
    _thread = None
    _process = None
    _finished = False
    _gui_launched = False
    _instance = None
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        return props.colmap_path and os.path.exists(props.colmap_path)
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if SKY_SPLAT_OT_run_colmap_gui._finished:
                self.cancel(context)
                if SKY_SPLAT_OT_run_colmap_gui._gui_launched:
                    self.report({'INFO'}, "COLMAP GUI launched successfully!")
                else:
                    self.report({'ERROR'}, "Failed to launch COLMAP GUI!")
                return {'FINISHED'}
            
            # Check if process is still running
            if SKY_SPLAT_OT_run_colmap_gui._process and SKY_SPLAT_OT_run_colmap_gui._process.poll() is not None:
                SKY_SPLAT_OT_run_colmap_gui._finished = True
                
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        if SKY_SPLAT_OT_run_colmap_gui._timer:
            wm = context.window_manager
            wm.event_timer_remove(SKY_SPLAT_OT_run_colmap_gui._timer)
            SKY_SPLAT_OT_run_colmap_gui._timer = None
        
        # Note: We don't terminate the COLMAP GUI process here
        # as the user should be able to close it manually
        SKY_SPLAT_OT_run_colmap_gui._thread = None
        SKY_SPLAT_OT_run_colmap_gui._instance = None
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        
        # Validate COLMAP executable
        if not props.colmap_path or not os.path.exists(props.colmap_path):
            self.report({'ERROR'}, "COLMAP executable not found")
            return {'CANCELLED'}
        
        try:
            # Reset class state
            SKY_SPLAT_OT_run_colmap_gui._finished = False
            SKY_SPLAT_OT_run_colmap_gui._gui_launched = False
            SKY_SPLAT_OT_run_colmap_gui._instance = self
            
            # Start COLMAP GUI in a separate thread
            SKY_SPLAT_OT_run_colmap_gui._thread = threading.Thread(target=self.launch_colmap_gui, args=(props,))
            SKY_SPLAT_OT_run_colmap_gui._thread.start()
            
            # Start modal timer
            wm = context.window_manager
            SKY_SPLAT_OT_run_colmap_gui._timer = wm.event_timer_add(0.5, window=context.window)
            wm.modal_handler_add(self)
            
            self.report({'INFO'}, "Launching COLMAP GUI...")
            return {'RUNNING_MODAL'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to launch COLMAP GUI: {str(e)}")
            return {'CANCELLED'}
    
    def launch_colmap_gui(self, props):
        """Launch COLMAP GUI with project setup"""
        try:
            # Determine paths for the COLMAP project
            image_path = None
            database_path = None
            project_path = None
            
            # Try to find image path from various sources
            if props.input_folder and os.path.exists(props.input_folder):
                image_path = props.input_folder
            elif props.output_folder and os.path.exists(props.output_folder):
                # Check for images in output folder structure
                images_in_output = os.path.join(props.output_folder, "images")
                if os.path.exists(images_in_output):
                    image_path = images_in_output
                else:
                    # Check for input subfolder
                    input_in_output = os.path.join(props.output_folder, "input")
                    if os.path.exists(input_in_output):
                        image_path = input_in_output
            elif props.images_path and os.path.exists(props.images_path):
                image_path = props.images_path
            
            # If we don't have an image path, we can't create a meaningful project
            if not image_path:
                print("Error: No valid image path found for COLMAP GUI")
                SKY_SPLAT_OT_run_colmap_gui._gui_launched = False
                return
            
            # Set up database path
            if props.output_folder:
                os.makedirs(props.output_folder, exist_ok=True)
                database_path = os.path.join(props.output_folder, "database.db")
                project_path = os.path.join(props.output_folder, "project.ini")
            else:
                # Create output folder based on input folder
                parent_dir = os.path.dirname(image_path)
                output_folder = os.path.join(parent_dir, "colmap_gui_project")
                os.makedirs(output_folder, exist_ok=True)
                database_path = os.path.join(output_folder, "database.db")
                project_path = os.path.join(output_folder, "project.ini")
            
            # Create COLMAP project file
            self.create_colmap_project_file(project_path, database_path, image_path, props)
            
            # Build command to launch COLMAP GUI with project file AND required parameters
            command = [
                props.colmap_path, "gui",
                "--database_path", database_path,
                "--image_path", image_path,
                project_path
            ]
            
            print(f"Launching COLMAP GUI with project: {' '.join(command)}")
            print(f"  Database: {database_path}")
            print(f"  Images: {image_path}")
            print(f"  Project: {project_path}")
            
            # Launch COLMAP GUI as a separate process
            # Use subprocess.Popen to allow the GUI to run independently
            SKY_SPLAT_OT_run_colmap_gui._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Give the GUI a moment to start
            time.sleep(2)
            
            # Check if the process started successfully
            if SKY_SPLAT_OT_run_colmap_gui._process.poll() is None:
                SKY_SPLAT_OT_run_colmap_gui._gui_launched = True
                print("COLMAP GUI launched successfully!")
                
                # The GUI will run independently - we don't wait for it to finish
                # This allows Blender to remain interactive
                
            else:
                print(f"COLMAP GUI failed to start. Return code: {SKY_SPLAT_OT_run_colmap_gui._process.returncode}")
                if SKY_SPLAT_OT_run_colmap_gui._process.stdout:
                    stdout = SKY_SPLAT_OT_run_colmap_gui._process.stdout.read()
                    if stdout:
                        print(f"STDOUT: {stdout}")
                if SKY_SPLAT_OT_run_colmap_gui._process.stderr:
                    stderr = SKY_SPLAT_OT_run_colmap_gui._process.stderr.read()
                    if stderr:
                        print(f"STDERR: {stderr}")
            
        except Exception as e:
            print(f"Error launching COLMAP GUI: {str(e)}")
        finally:
            SKY_SPLAT_OT_run_colmap_gui._finished = True
    
    def create_colmap_project_file(self, project_path, database_path, image_path, props):
        """Create a COLMAP project file with proper settings"""
        try:
            project_content = f"""# COLMAP project file generated by SkySplat Blender Addon

[database]
database_path={database_path}

[image]
image_path={image_path}

[feature_extraction]
ImageReader.camera_model={props.camera_model}
ImageReader.single_camera=1
SiftExtraction.use_gpu={1 if props.use_gpu else 0}

[feature_matching]
SiftMatching.use_gpu={1 if props.use_gpu else 0}
"""
            
            # Add matching type specific settings
            if props.matching_type == 'SEQUENTIAL':
                project_content += """
[sequential_matching]
SequentialMatching.overlap=10
"""
            else:
                project_content += """
[exhaustive_matching]
ExhaustiveMatching.block_size=50
"""
            
            # Add reconstruction settings
            project_content += """
[mapper]
Mapper.ba_global_function_tolerance=0.000001
Mapper.ba_refine_focal_length=1
Mapper.ba_refine_principal_point=0
Mapper.ba_refine_extra_params=1

[bundle_adjustment]
BundleAdjustment.refine_focal_length=1
BundleAdjustment.refine_principal_point=0
BundleAdjustment.refine_extra_params=1
"""
            
            # Write project file
            with open(project_path, 'w') as f:
                f.write(project_content)
            
            print(f"Created COLMAP project file: {project_path}")
            
        except Exception as e:
            print(f"Error creating COLMAP project file: {str(e)}")


class SKY_SPLAT_OT_run_colmap_automatic(Operator):
    bl_idname = "skysplat.run_colmap_automatic"
    bl_label = "Run COLMAP Automatic"
    bl_description = "Run COLMAP automatic reconstruction in background with GUI progress"
    
    # Use class variables to avoid StructRNA reference issues
    _timer = None
    _thread = None
    _process = None
    _finished = False
    _output_lines = []
    _instance = None
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        return (props.colmap_path and 
                props.input_folder and os.path.exists(props.input_folder) and 
                props.output_folder)
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if SKY_SPLAT_OT_run_colmap_automatic._finished:
                self.cancel(context)
                if SKY_SPLAT_OT_run_colmap_automatic._process and SKY_SPLAT_OT_run_colmap_automatic._process.returncode == 0:
                    self.report({'INFO'}, "COLMAP automatic reconstruction completed!")
                    # Auto-update paths after successful completion
                    props = context.scene.skysplat_colmap_props
                    props.model_import_path = os.path.join(props.output_folder, "sparse", "0")
                    props.images_path = os.path.join(props.output_folder, "images")
                else:
                    self.report({'ERROR'}, "COLMAP automatic reconstruction failed!")
                return {'FINISHED'}
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        if SKY_SPLAT_OT_run_colmap_automatic._timer:
            wm = context.window_manager
            wm.event_timer_remove(SKY_SPLAT_OT_run_colmap_automatic._timer)
            SKY_SPLAT_OT_run_colmap_automatic._timer = None
        
        if SKY_SPLAT_OT_run_colmap_automatic._process and SKY_SPLAT_OT_run_colmap_automatic._process.poll() is None:
            SKY_SPLAT_OT_run_colmap_automatic._process.terminate()
            SKY_SPLAT_OT_run_colmap_automatic._process = None
        
        if SKY_SPLAT_OT_run_colmap_automatic._thread and SKY_SPLAT_OT_run_colmap_automatic._thread.is_alive():
            SKY_SPLAT_OT_run_colmap_automatic._thread.join(timeout=1.0)
            SKY_SPLAT_OT_run_colmap_automatic._thread = None
        
        SKY_SPLAT_OT_run_colmap_automatic._instance = None
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        
        # Validate inputs
        if not props.colmap_path or not os.path.exists(props.colmap_path):
            self.report({'ERROR'}, "COLMAP executable not found")
            return {'CANCELLED'}
        
        if not props.input_folder or not os.path.exists(props.input_folder):
            self.report({'ERROR'}, "Input folder does not exist")
            return {'CANCELLED'}
        
        # Create output directory
        os.makedirs(props.output_folder, exist_ok=True)
        
        try:
            # Reset class state
            SKY_SPLAT_OT_run_colmap_automatic._finished = False
            SKY_SPLAT_OT_run_colmap_automatic._output_lines = []
            SKY_SPLAT_OT_run_colmap_automatic._instance = self
            
            # Start automatic reconstruction in background
            SKY_SPLAT_OT_run_colmap_automatic._thread = threading.Thread(target=self.run_automatic_reconstruction, args=(props,))
            SKY_SPLAT_OT_run_colmap_automatic._thread.start()
            
            # Start modal timer
            wm = context.window_manager
            SKY_SPLAT_OT_run_colmap_automatic._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            
            self.report({'INFO'}, "Started COLMAP automatic reconstruction...")
            return {'RUNNING_MODAL'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start automatic reconstruction: {str(e)}")
            return {'CANCELLED'}
    
    def run_automatic_reconstruction(self, props):
        """Run COLMAP automatic reconstruction"""
        try:
            # Build command for automatic reconstruction
            command = [
                props.colmap_path, "automatic_reconstructor",
                "--image_path", props.input_folder,
                "--workspace_path", props.output_folder,
                "--camera_model", props.camera_model
            ]
            
            # Add GPU option if enabled
            if props.use_gpu:
                command.extend(["--SiftExtraction.use_gpu", "1"])
                command.extend(["--SiftMatching.use_gpu", "1"])
            
            print(f"Running COLMAP automatic reconstruction: {' '.join(command)}")
            
            # Run the command
            SKY_SPLAT_OT_run_colmap_automatic._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in SKY_SPLAT_OT_run_colmap_automatic._process.stdout:
                SKY_SPLAT_OT_run_colmap_automatic._output_lines.append(line.strip())
                print(f"COLMAP: {line.strip()}")
            
            # Wait for process to complete
            SKY_SPLAT_OT_run_colmap_automatic._process.wait()
            
            if SKY_SPLAT_OT_run_colmap_automatic._process.returncode == 0:
                print("COLMAP automatic reconstruction completed successfully!")
            else:
                print(f"COLMAP automatic reconstruction failed with code: {SKY_SPLAT_OT_run_colmap_automatic._process.returncode}")
            
        except Exception as e:
            print(f"Error running COLMAP automatic reconstruction: {str(e)}")
        finally:
            SKY_SPLAT_OT_run_colmap_automatic._finished = True


# Registration
classes = (
    SKY_SPLAT_OT_run_colmap_gui,
    SKY_SPLAT_OT_run_colmap_automatic,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)