import bpy
import os
import shutil
import subprocess
import tempfile
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SkySplat')

# Panel version constant
PANEL_VERSION = "0.3.0"

class SKY_SPLAT_ColmapProperties(bpy.types.PropertyGroup):
    """Properties for COLMAP processing"""
    
    colmap_path: bpy.props.StringProperty(
        name="COLMAP Executable",
        description="Path to the COLMAP executable",
        subtype='FILE_PATH',
        default=""
    )
    
    magick_path: bpy.props.StringProperty(
        name="ImageMagick Executable",
        description="Path to the ImageMagick executable",
        subtype='FILE_PATH',
        default=""
    )
    
    input_folder: bpy.props.StringProperty(
        name="Input Folder",
        description="Folder containing images to process with COLMAP",
        subtype='DIR_PATH'
    )
    
    output_folder: bpy.props.StringProperty(
        name="Output Folder",
        description="Folder to save COLMAP results",
        subtype='DIR_PATH'
    )
    
    use_gpu: bpy.props.BoolProperty(
        name="Use GPU",
        description="Use GPU acceleration for COLMAP",
        default=True
    )
    
    camera_model: bpy.props.EnumProperty(
        name="Camera Model",
        description="COLMAP camera model to use",
        items=[
            ('SIMPLE_PINHOLE', 'Simple Pinhole', 'Simple pinhole camera model'),
            ('PINHOLE', 'Pinhole', 'Pinhole camera model'),
            ('SIMPLE_RADIAL', 'Simple Radial', 'Simple radial camera model'),
            ('RADIAL', 'Radial', 'Radial camera model'),
            ('OPENCV', 'OpenCV', 'OpenCV camera model'),
            ('FULL_OPENCV', 'Full OpenCV', 'Full OpenCV camera model'),
        ],
        default='OPENCV'
    )
    
    resize_images: bpy.props.BoolProperty(
        name="Create Multi-res Images",
        description="Create multi-resolution images for faster rendering",
        default=True
    )
    
    def update_from_video_panel(self, context):
        """Update COLMAP paths based on the frames extracted in the video panel"""
        video_props = context.scene.skysplat_props
        
        if video_props.video_path:
            # Get video path and name without extension
            video_path = bpy.path.abspath(video_props.video_path)
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            
            # Set default paths based on video name
            frames_folder = os.path.join(video_dir, f"{video_name}_frames")
            colmap_output_folder = os.path.join(video_dir, f"{video_name}_colmap_output")
            
            # Update paths
            self.input_folder = frames_folder
            self.output_folder = colmap_output_folder


def run_command(command, cwd=None):
    """Run a command and log its output"""
    logger.info(f"Running command: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=cwd
        )
        logger.info(f"Command output: {result.stdout}")
        return 0  # Success
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with error: {e}")
        logger.error(f"Error output: {e.stderr}")
        return e.returncode


def run_colmap_processing(props):
    """Run COLMAP processing with the given properties"""
    # Get paths
    source_path = props.output_folder
    input_path = os.path.join(source_path, "input")
    
    # Configure COLMAP command
    colmap_command = f'"{props.colmap_path}"' if props.colmap_path else "colmap"
    magick_command = f'"{props.magick_path}"' if props.magick_path else "magick"
    use_gpu = 1 if props.use_gpu else 0
    
    # Create directories
    os.makedirs(os.path.join(source_path, "distorted/sparse"), exist_ok=True)
    
    # Feature extraction
    feature_cmd = f'{colmap_command} feature_extractor ' \
                 f'--database_path "{source_path}/distorted/database.db" ' \
                 f'--image_path "{input_path}" ' \
                 f'--ImageReader.single_camera 1 ' \
                 f'--ImageReader.camera_model {props.camera_model} ' \
                 f'--SiftExtraction.use_gpu {use_gpu}'
    
    if run_command(feature_cmd) != 0:
        raise RuntimeError("Feature extraction failed")
    
    # Feature matching
    matching_cmd = f'{colmap_command} exhaustive_matcher ' \
                  f'--database_path "{source_path}/distorted/database.db" ' \
                  f'--SiftMatching.use_gpu {use_gpu}'
    
    if run_command(matching_cmd) != 0:
        raise RuntimeError("Feature matching failed")
    
    # Bundle adjustment
    mapper_cmd = f'{colmap_command} mapper ' \
                f'--database_path "{source_path}/distorted/database.db" ' \
                f'--image_path "{input_path}" ' \
                f'--output_path "{source_path}/distorted/sparse" ' \
                f'--Mapper.ba_global_function_tolerance=0.000001'
    
    if run_command(mapper_cmd) != 0:
        raise RuntimeError("Bundle adjustment failed")
    
    # Image undistortion
    undist_cmd = f'{colmap_command} image_undistorter ' \
                f'--image_path "{input_path}" ' \
                f'--input_path "{source_path}/distorted/sparse/0" ' \
                f'--output_path "{source_path}" ' \
                f'--output_type COLMAP'
    
    if run_command(undist_cmd) != 0:
        raise RuntimeError("Image undistortion failed")
    
    # Move files
    files = os.listdir(os.path.join(source_path, "sparse"))
    os.makedirs(os.path.join(source_path, "sparse/0"), exist_ok=True)
    
    for file in files:
        if file == '0':
            continue
        source_file = os.path.join(source_path, "sparse", file)
        destination_file = os.path.join(source_path, "sparse", "0", file)
        shutil.move(source_file, destination_file)
    
    # Create multi-resolution images if requested
    if props.resize_images:
        create_multires_images(source_path, magick_command)
    
    return True


def create_multires_images(source_path, magick_command):
    """Create multi-resolution images for faster rendering"""
    logger.info("Creating multi-resolution images...")
    
    # Create directories
    os.makedirs(os.path.join(source_path, "images_2"), exist_ok=True)
    os.makedirs(os.path.join(source_path, "images_4"), exist_ok=True)
    os.makedirs(os.path.join(source_path, "images_8"), exist_ok=True)
    
    # Get list of images
    image_files = os.listdir(os.path.join(source_path, "images"))
    
    for file in image_files:
        source_file = os.path.join(source_path, "images", file)
        
        # 50% size
        dest_file_2 = os.path.join(source_path, "images_2", file)
        shutil.copy2(source_file, dest_file_2)
        if run_command(f'{magick_command} mogrify -resize 50% "{dest_file_2}"') != 0:
            raise RuntimeError("50% resize failed")
        
        # 25% size
        dest_file_4 = os.path.join(source_path, "images_4", file)
        shutil.copy2(source_file, dest_file_4)
        if run_command(f'{magick_command} mogrify -resize 25% "{dest_file_4}"') != 0:
            raise RuntimeError("25% resize failed")
        
        # 12.5% size
        dest_file_8 = os.path.join(source_path, "images_8", file)
        shutil.copy2(source_file, dest_file_8)
        if run_command(f'{magick_command} mogrify -resize 12.5% "{dest_file_8}"') != 0:
            raise RuntimeError("12.5% resize failed")


class SKY_SPLAT_OT_run_colmap(bpy.types.Operator):
    bl_idname = "skysplat.run_colmap"
    bl_label = "Run COLMAP"
    bl_description = "Run COLMAP on the input images to generate camera poses"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.colmap_props
        return props.input_folder and os.path.exists(props.input_folder) and props.output_folder
    
    def execute(self, context):
        props = context.scene.colmap_props
        
        # Test if input folder contains images
        image_files = [f for f in os.listdir(props.input_folder) 
                      if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        
        if not image_files:
            self.report({'ERROR'}, "No image files found in input folder")
            return {'CANCELLED'}
        
        # Create output folder and input subfolder
        os.makedirs(props.output_folder, exist_ok=True)
        input_path = os.path.join(props.output_folder, "input")
        os.makedirs(input_path, exist_ok=True)
        
        # Copy images to COLMAP input folder
        for img in image_files:
            src = os.path.join(props.input_folder, img)
            dst = os.path.join(input_path, img)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
        
        try:
            # Run COLMAP processing
            run_colmap_processing(props)
            self.report({'INFO'}, f"COLMAP processing completed successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"COLMAP processing failed: {str(e)}")
            return {'CANCELLED'}


class SKY_SPLAT_OT_sync_with_video(bpy.types.Operator):
    bl_idname = "skysplat.sync_with_video"
    bl_label = "Sync with Video Panel"
    bl_description = "Set paths based on video file name"
    
    def execute(self, context):
        props = context.scene.colmap_props
        props.update_from_video_panel(context)
        self.report({'INFO'}, "COLMAP paths synchronized with video")
        return {'FINISHED'}


class SKY_SPLAT_PT_colmap_panel(bpy.types.Panel):
    bl_label = "SkySplat COLMAP"
    bl_idname = "SKY_SPLAT_PT_colmap_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SkySplat"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.colmap_props
        
        # COLMAP executables and options
        box = layout.box()
        box.label(text="COLMAP Settings")
        box.prop(props, "colmap_path")
        box.prop(props, "magick_path")
        box.prop(props, "camera_model")
        
        row = box.row()
        row.prop(props, "use_gpu")
        row.prop(props, "resize_images")
        
        # Input/Output settings
        box = layout.box()
        box.label(text="Input/Output Settings")
        
        row = box.row()
        row.prop(props, "input_folder")
        row.operator("skysplat.sync_with_video", icon='LINKED', text="")
        
        box.prop(props, "output_folder")
        
        # Run COLMAP button
        layout.operator("skysplat.run_colmap", icon='CAMERA_DATA')
        
        # Version indicator at the bottom
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")


# Registration
classes = (
    SKY_SPLAT_ColmapProperties,
    SKY_SPLAT_OT_run_colmap,
    SKY_SPLAT_OT_sync_with_video,
    SKY_SPLAT_PT_colmap_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.colmap_props = bpy.props.PointerProperty(type=SKY_SPLAT_ColmapProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.colmap_props