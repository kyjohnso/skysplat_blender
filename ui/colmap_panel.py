import bpy
import os
import shutil
import subprocess
import tempfile
import logging
import platform
import sys
import json

import numpy as np
import mathutils
import math
import sqlite3
import struct
from mathutils import Matrix, Vector

# Use relative import to get functions from utils directory
from ..utils.read_write_model import (
    read_model, write_model, qvec2rotmat, rotmat2qvec,
    Image, Point3D, Camera
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SkySplat')

# Panel version constant
PANEL_VERSION = "0.4.1"

def get_default_colmap_path():
    """Get default COLMAP path based on operating system"""
    system = platform.system()
    
    if system == "Windows":
        # Common installation paths on Windows
        possible_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'COLMAP', 'COLMAP.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'COLMAP', 'COLMAP.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\User\\AppData\\Local'), 'COLMAP', 'COLMAP.exe')
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""
    
    elif system == "Darwin":  # macOS
        # Common installation paths on macOS
        possible_paths = [
            "/Applications/COLMAP.app/Contents/MacOS/colmap",
            "/usr/local/bin/colmap",
            os.path.expanduser("~/Applications/COLMAP.app/Contents/MacOS/colmap")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""
    
    elif system == "Linux":
        # Try to find colmap in PATH on Linux
        try:
            result = subprocess.run(["which", "colmap"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        # Common installation paths on Linux
        possible_paths = [
            "/usr/bin/colmap",
            "/usr/local/bin/colmap"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""
    
    return ""

def get_default_magick_path():
    """Get default ImageMagick path based on operating system"""
    system = platform.system()
    
    if system == "Windows":
        # Common installation paths on Windows
        possible_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'ImageMagick-7.0.10-Q16', 'magick.exe'),
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'ImageMagick', 'magick.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'ImageMagick-7.0.10-Q16', 'magick.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'ImageMagick', 'magick.exe')
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""
    
    elif system == "Darwin" or system == "Linux":
        # Try to find convert/magick in PATH on macOS/Linux
        commands = ["magick", "convert"]  # ImageMagick 7 uses 'magick', older versions use 'convert'
        for cmd in commands:
            try:
                result = subprocess.run(["which", cmd], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass
        
        # Common installation paths
        possible_paths = [
            "/usr/bin/magick",
            "/usr/local/bin/magick",
            "/usr/bin/convert",
            "/usr/local/bin/convert"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""
    
    return ""

class SKY_SPLAT_ColmapProperties(bpy.types.PropertyGroup):
    """Properties for COLMAP processing"""
    
    colmap_path: bpy.props.StringProperty(
        name="COLMAP Executable",
        description="Path to the COLMAP executable",
        subtype='FILE_PATH',
        default=get_default_colmap_path()
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

    matching_type: bpy.props.EnumProperty(
        name="Matching Type",
        description="Choose between sequential or exhaustive matching",
        items=[
            ('SEQUENTIAL', "Sequential", "Use sequential matching - faster but works best for video frames with consecutive overlap"),
            ('EXHAUSTIVE', "Exhaustive", "Use exhaustive matching - slower but more thorough for unordered image collections")
        ],
        default='SEQUENTIAL'
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
    
    # Feature matching - choose method based on matching_type
    if props.matching_type == 'SEQUENTIAL':
        matching_cmd = f'{colmap_command} sequential_matcher ' \
                      f'--database_path "{source_path}/distorted/database.db" ' \
                      f'--SiftMatching.use_gpu {use_gpu}'
    else:  # EXHAUSTIVE
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
    
    return True

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

# Operator to load COLMAP model into Blender with proper camera transformation
class SKY_SPLAT_OT_load_colmap_model(bpy.types.Operator):
    bl_idname = "skysplat.load_colmap_model"
    bl_label = "Load COLMAP Model"
    bl_description = "Load COLMAP model from output folder"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.colmap_props
        return props.output_folder and os.path.exists(props.output_folder)
    
    def execute(self, context):
        props = context.scene.colmap_props
        sparse_dir = os.path.join(props.output_folder, "sparse", "0")
        
        if not os.path.exists(sparse_dir):
            self.report({'ERROR'}, f"Sparse reconstruction not found at {sparse_dir}")
            return {'CANCELLED'}
            
        try:
            # Create a new collection for the COLMAP data
            collection_name = "COLMAP_Model"
            if collection_name in bpy.data.collections:
                collection = bpy.data.collections[collection_name]
                # Clear collection
                for obj in collection.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
            else:
                collection = bpy.data.collections.new(collection_name)
                bpy.context.scene.collection.children.link(collection)
            
            # Read model using read_write_model.py functions
            cameras, images, points3D = read_model(sparse_dir)
            
            # Create a root empty object that will be the parent for all COLMAP objects
            root = bpy.data.objects.new("COLMAP_Root", None)
            root.empty_display_type = 'ARROWS'
            root.empty_display_size = 1.0
            collection.objects.link(root)
            root['colmap_root'] = True
            root['colmap_model_path'] = sparse_dir
            
            # COLMAP to Blender coordinate transformation
            # COLMAP: Y down, Z forward
            # Blender: Y up, -Z forward
            coord_transform = mathutils.Matrix(((1, 0, 0, 0),
                                              (0, -1, 0, 0),
                                              (0, 0, -1, 0),
                                              (0, 0, 0, 1)))
            
            # Create point cloud first
            if points3D:
                mesh = bpy.data.meshes.new("COLMAP_PointCloud")
                obj = bpy.data.objects.new("COLMAP_PointCloud", mesh)
                collection.objects.link(obj)
                
                # Create vertices and colors
                verts = []
                colors = []
                for point_id, point in points3D.items():
                    # Apply coordinate transformation to point
                    point_vec = Vector((point.xyz[0], point.xyz[1], point.xyz[2]))
                    transformed_point = coord_transform @ point_vec
                    verts.append(transformed_point)
                    colors.append([c/255.0 for c in point.rgb])
                
                # Create mesh from vertices
                mesh.from_pydata(verts, [], [])
                mesh.update()
                
                # Add vertex colors
                if len(colors) > 0:
                    color_layer = mesh.vertex_colors.new(name="Col")
                    for i, c in enumerate(color_layer.data):
                        c.color = colors[i % len(colors)] + [1.0]  # RGBA
                
                # Parent to root directly without additional transformation
                obj.parent = root
                
                # Tag point cloud
                obj['colmap_points3D'] = True
            
            # Create camera objects with CORRECTED camera transformation
            for image_id, image in images.items():
                # Create camera object
                cam_data = bpy.data.cameras.new(f"COLMAP_Camera_{image_id}")
                cam_obj = bpy.data.objects.new(f"COLMAP_Camera_{image_id}", cam_data)
                collection.objects.link(cam_obj)
                
                # Set camera parameters based on COLMAP camera model
                camera = cameras[image.camera_id]
                cam_data.lens_unit = 'MILLIMETERS'
                
                # Set focal length if available
                if hasattr(camera, 'params') and len(camera.params) > 0:
                    focal_length_pixels = camera.params[0]
                    sensor_width_mm = 36.0  # Standard full frame width
                    focal_length_mm = (focal_length_pixels * sensor_width_mm) / camera.width
                    cam_data.lens = focal_length_mm
                
                # *** IMPROVED CAMERA TRANSFORMATION ***
                # In COLMAP, camera transform is world-to-camera, but Blender expects camera-to-world
                
                # Get rotation matrix
                R = qvec2rotmat(image.qvec)
                R = np.array(R)
                
                # Compute the inverse (transpose) of rotation
                R_t = R.T
                
                # Get translation vector
                t = np.array(image.tvec)
                
                # Compute camera center in world coordinates
                cam_center = -R_t @ t
                
                # Convert rotation to Blender matrix
                rotation = mathutils.Matrix((
                    (R_t[0][0], R_t[0][1], R_t[0][2]),
                    (R_t[1][0], R_t[1][1], R_t[1][2]),
                    (R_t[2][0], R_t[2][1], R_t[2][2])
                )).to_4x4()
                
                # Create translation matrix with camera center
                translation = mathutils.Matrix.Translation(Vector((cam_center[0], cam_center[1], cam_center[2])))
                
                # Combine to form camera transformation (camera-to-world)
                transform = translation @ rotation
                
                # Apply coordinate system transformation
                transform = coord_transform @ transform @ coord_transform.inverted()
                
                # Set the camera transformation
                cam_obj.matrix_world = transform
                
                # Store COLMAP IDs as custom properties
                cam_obj['colmap_image_id'] = image_id
                cam_obj['colmap_camera_id'] = image.camera_id
                
                # Store original quaternion and tvec for export
                cam_obj['colmap_qvec'] = image.qvec.tolist()
                cam_obj['colmap_tvec'] = image.tvec.tolist()
                
                # Parent to root
                cam_obj.parent = root
            
            # Select the root object so user can transform it
            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            root.select_set(True)
            bpy.context.view_layer.objects.active = root
            
            self.report({'INFO'}, f"COLMAP model loaded with {len(cameras)} cameras, {len(images)} images, and {len(points3D)} points. Use Blender transform tools to adjust the model.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load COLMAP model: {str(e)}")
            logger.error(f"Failed to load COLMAP model: {str(e)}", exc_info=True)
            return {'CANCELLED'}
        
# Operator to export transformed COLMAP model with proper scale handling
class SKY_SPLAT_OT_export_colmap_model(bpy.types.Operator):
    bl_idname = "skysplat.export_colmap_model"
    bl_label = "Export Transformed Model"
    bl_description = "Export the transformed COLMAP model"
    
    @classmethod
    def poll(cls, context):
        # Check if COLMAP root exists in the scene
        for obj in bpy.data.objects:
            if 'colmap_root' in obj and 'colmap_model_path' in obj:
                props = context.scene.colmap_props
                return props.output_folder and os.path.exists(props.output_folder)
        return False
    
    def execute(self, context):
        props = context.scene.colmap_props
        
        try:
            # Find the COLMAP root object
            root = None
            for obj in bpy.data.objects:
                if 'colmap_root' in obj:
                    root = obj
                    break
            
            if not root:
                self.report({'ERROR'}, "COLMAP root object not found")
                return {'CANCELLED'}
            
            # Get the source model path
            source_path = root['colmap_model_path']
            
            # Create transformed_sparse directory
            export_dir = os.path.join(props.output_folder, "transformed_sparse", "0")
            os.makedirs(export_dir, exist_ok=True)
            
            # Read the original model
            cameras, images, points3D = read_model(source_path)
            
            # Coordinate transform matrix (to convert back from Blender to COLMAP)
            coord_transform = mathutils.Matrix(((1, 0, 0, 0),
                                              (0, -1, 0, 0),
                                              (0, 0, -1, 0),
                                              (0, 0, 0, 1)))
            
            # Extract scaling from the root's transformation
            # This is uniform scale - average of X, Y, Z scales
            scale_factor = (root.scale.x + root.scale.y + root.scale.z) / 3.0
            logger.info(f"Detected scale factor: {scale_factor}")
            
            # Create a dictionary of image objects by ID for quick lookup
            image_objects = {}
            for obj in bpy.data.objects:
                if 'colmap_image_id' in obj:
                    image_objects[obj['colmap_image_id']] = obj
            
            # Update camera poses based on the transformed Blender objects
            for image_id, image in images.items():
                if image_id in image_objects:
                    obj = image_objects[image_id]
                    
                    # Get world transformation (includes the root transformation)
                    # This is camera-to-world in Blender
                    world_matrix = obj.matrix_world
                    
                    # Convert from Blender to COLMAP coordinate system
                    colmap_matrix = coord_transform.inverted() @ world_matrix @ coord_transform
                    
                    # Extract rotation and location
                    rot_matrix = colmap_matrix.to_3x3()
                    location = colmap_matrix.translation
                    
                    # Convert from camera-to-world to world-to-camera format for COLMAP
                    R = np.array(rot_matrix)
                    camera_center = np.array([location.x, location.y, location.z])
                    
                    # COLMAP's R is the inverse (transpose) of camera-to-world rotation
                    R_colmap = R.T
                    
                    # COLMAP's t is -R_colmap * camera_center
                    t_colmap = -R_colmap @ camera_center
                    
                    # Convert rotation matrix to quaternion using the COLMAP function
                    qvec = rotmat2qvec(R_colmap)
                    
                    # Create a new Image object with updated transformation
                    images[image_id] = Image(
                        id=image.id,
                        qvec=qvec,
                        tvec=np.array(t_colmap),
                        camera_id=image.camera_id,
                        name=image.name,
                        xys=image.xys,
                        point3D_ids=image.point3D_ids
                    )
            
            # Transform point cloud if needed
            point_cloud = None
            for obj in bpy.data.objects:
                if 'colmap_points3D' in obj:
                    point_cloud = obj
                    break
            
            if point_cloud and points3D:
                # Get global transformation of the point cloud
                pc_matrix = point_cloud.matrix_world
                
                # Convert to COLMAP coordinate system
                pc_colmap_matrix = coord_transform.inverted() @ pc_matrix @ coord_transform
                
                # Create transformed points3D dictionary
                transformed_points3D = {}
                for point_id, point in points3D.items():
                    # Create a vector for the point
                    point_vec = Vector((point.xyz[0], point.xyz[1], point.xyz[2]))
                    
                    # Apply the transformation
                    transformed_point = pc_colmap_matrix @ point_vec
                    
                    # Create a new Point3D object with transformed position
                    transformed_points3D[point_id] = Point3D(
                        id=point.id,
                        xyz=np.array([transformed_point.x, transformed_point.y, transformed_point.z]),
                        rgb=point.rgb,
                        error=point.error,
                        image_ids=point.image_ids,
                        point2D_idxs=point.point2D_idxs
                    )
                
                # Replace the original points with transformed ones
                points3D = transformed_points3D
            
            # Update camera intrinsics to account for scaling
            # This is crucial for COLMAP to properly visualize cameras after scaling
            if scale_factor != 1.0:
                # Create new cameras with scaled intrinsics
                scaled_cameras = {}
                for camera_id, camera in cameras.items():
                    params = list(camera.params)
                    
                    # Scale focal length and principal point parameters
                    # The exact parameters to scale depend on the camera model
                    if camera.model in ['SIMPLE_PINHOLE', 'PINHOLE', 'SIMPLE_RADIAL', 'RADIAL', 'OPENCV', 'FULL_OPENCV']:
                        # For most models, first param is focal length
                        params[0] *= scale_factor  # Scale focal length
                        
                        # If model has separate focal lengths for x and y
                        if camera.model in ['PINHOLE', 'OPENCV', 'FULL_OPENCV'] and len(params) > 1:
                            params[1] *= scale_factor  # Scale second focal length
                        
                        # Scale principal point (cx, cy) if present
                        if camera.model in ['SIMPLE_PINHOLE', 'PINHOLE'] and len(params) > 2:
                            params[2] *= scale_factor  # cx
                            params[3] *= scale_factor  # cy
                        elif camera.model in ['OPENCV', 'FULL_OPENCV'] and len(params) > 3:
                            params[2] *= scale_factor  # cx
                            params[3] *= scale_factor  # cy
                    
                    # Create new camera with scaled parameters
                    scaled_cameras[camera_id] = Camera(
                        id=camera.id,
                        model=camera.model,
                        width=camera.width,
                        height=camera.height,
                        params=np.array(params)
                    )
                
                # Replace original cameras with scaled ones
                cameras = scaled_cameras
            
            # Write the updated model
            write_model(cameras, images, points3D, export_dir)
            
            self.report({'INFO'}, f"Transformed COLMAP model exported to {export_dir}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export COLMAP model: {str(e)}")
            logger.error(f"Failed to export COLMAP model: {str(e)}", exc_info=True)
            return {'CANCELLED'}

# Update the panel to include model import/export UI
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
        box.prop(props, "camera_model")
        box.prop(props, "matching_type")
        
        row = box.row()
        row.prop(props, "use_gpu")
        
        # Input/Output settings
        box = layout.box()
        box.label(text="Input/Output Settings")
        
        row = box.row()
        row.prop(props, "input_folder")
        row.operator("skysplat.sync_with_video", icon='LINKED', text="")
        
        box.prop(props, "output_folder")
        
        # Run COLMAP button
        layout.operator("skysplat.run_colmap", icon='CAMERA_DATA')
        
        # COLMAP model transformation section
        box = layout.box()
        box.label(text="COLMAP Model Transformation")
        
        # Load model button
        box.operator("skysplat.load_colmap_model", icon='IMPORT')
        
        # Check if model is loaded
        has_colmap_root = False
        for obj in bpy.data.objects:
            if 'colmap_root' in obj:
                has_colmap_root = True
                break
                
        if has_colmap_root:
            # Instructions
            box.label(text="Use Blender's transform tools to adjust the model.")
            box.label(text="Select the COLMAP_Root object to transform everything.")
            
            # Export model button
            box.operator("skysplat.export_colmap_model", icon='EXPORT')
        
        # Version indicator at the bottom
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")


# Registration
classes = (
    SKY_SPLAT_ColmapProperties,
    SKY_SPLAT_OT_run_colmap,
    SKY_SPLAT_OT_sync_with_video,
    SKY_SPLAT_OT_load_colmap_model,
    SKY_SPLAT_OT_export_colmap_model,
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