
import bpy
import os
import shutil
import subprocess
import tempfile
import logging
import platform
import sys
import json
import time
import re
from pathlib import Path

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
PANEL_VERSION = "0.4.1"  # Updated for multi-instance support

def get_default_colmap_path():
    """Get default COLMAP path based on operating system"""
    system = platform.system()
    
    if system == "Windows":
        # Common installation paths on Windows
        possible_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'COLMAP', 'COLMAP.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'COLMAP', 'COLMAP.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\User\\AppData\\Local'), 'COLMAP', 'COLMAP.exe'),
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'COLMAP', 'bin', 'COLMAP.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'COLMAP', 'bin', 'COLMAP.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\User\\AppData\\Local'), 'COLMAP', 'bin', 'COLMAP.exe'),
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
            "/opt/homebrew/bin/colmap",
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

# Cache for COLMAP options to avoid repeated subprocess calls
_colmap_options_cache = {}

def get_colmap_version_and_options(colmap_path):
    """
    Detect COLMAP option syntax by parsing help output.
    
    Uses dynamic detection instead of hard-coded version checks for better
    forward compatibility with future COLMAP versions.
    """
    global _colmap_options_cache
    
    # Check cache first
    cache_key = colmap_path or "colmap"
    if cache_key in _colmap_options_cache:
        return _colmap_options_cache[cache_key]
    
    colmap_command = f'"{colmap_path}"' if colmap_path else "colmap"
    
    # Default options (will be updated based on detection)
    feature_gpu_option = None
    matching_gpu_option = None
    version_string = "unknown"
    
    # Helper function to get combined stdout+stderr from command
    def get_help_output(cmd):
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            # COLMAP may write help to stdout or stderr, so combine both
            combined_output = (result.stdout or "") + (result.stderr or "")
            return combined_output if result.returncode == 0 else ""
        except Exception as e:
            logger.debug(f"Command '{cmd}' failed: {e}")
            return ""
    
    # Try to get version string (for logging purposes only, not for logic)
    help_output = get_help_output(f'{colmap_command} help')
    if help_output:
        version_match = re.search(r'COLMAP\s+([\d.]+\S*)', help_output)
        if version_match:
            version_string = version_match.group(1)
    
    # Detect feature extraction GPU option by parsing help output
    feature_help = get_help_output(f'{colmap_command} feature_extractor --help')
    if feature_help:
        # Check for each possible option in the help output
        # Order matters: check newer option names first
        if '--FeatureExtraction.use_gpu' in feature_help:
            feature_gpu_option = 'FeatureExtraction.use_gpu'
        elif '--SiftExtraction.use_gpu' in feature_help:
            feature_gpu_option = 'SiftExtraction.use_gpu'
    
    # Detect matching GPU option by parsing sequential_matcher help output
    matcher_help = get_help_output(f'{colmap_command} sequential_matcher --help')
    if matcher_help:
        # Check for each possible option in the help output
        # Order matters: check newer option names first
        if '--FeatureMatching.use_gpu' in matcher_help:
            matching_gpu_option = 'FeatureMatching.use_gpu'
        elif '--SiftMatching.use_gpu' in matcher_help:
            matching_gpu_option = 'SiftMatching.use_gpu'
    
    # Use sensible defaults if detection failed
    if feature_gpu_option is None:
        logger.warning("Could not detect feature GPU option, using 'SiftExtraction.use_gpu' as default")
        feature_gpu_option = 'SiftExtraction.use_gpu'
    
    if matching_gpu_option is None:
        logger.warning("Could not detect matching GPU option, using 'SiftMatching.use_gpu' as default")
        matching_gpu_option = 'SiftMatching.use_gpu'
    
    options = {
        'feature_gpu_option': feature_gpu_option,
        'matching_gpu_option': matching_gpu_option,
        'version': version_string
    }
    
    logger.info(f"Detected COLMAP {version_string}: feature GPU option = {feature_gpu_option}, matching GPU option = {matching_gpu_option}")
    
    # Cache the result
    _colmap_options_cache[cache_key] = options
    
    return options

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

class ColmapInstance(bpy.types.PropertyGroup):
    """Individual COLMAP instance with its own settings"""
    name: bpy.props.StringProperty(
        name="Instance Name",
        description="Name for this COLMAP instance",
        default="COLMAP"
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
    
    model_import_path: bpy.props.StringProperty(
        name="Model Import Path",
        description="Path to sparse model folder (containing cameras.bin, images.bin, points3D.bin)",
        subtype='DIR_PATH'
    )
    
    model_export_path: bpy.props.StringProperty(
        name="Model Export Path", 
        description="Path where transformed model will be saved",
        subtype='DIR_PATH'
    )
    
    images_path: bpy.props.StringProperty(
        name="Images Path",
        description="Path to images folder for brush dataset preparation", 
        subtype='DIR_PATH'
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
    
    is_processed: bpy.props.BoolProperty(
        name="Is Processed",
        description="Whether COLMAP processing has been completed",
        default=False
    )
    
    is_loaded: bpy.props.BoolProperty(
        name="Is Loaded",
        description="Whether the model is loaded in Blender",
        default=False
    )
    
    is_exported: bpy.props.BoolProperty(
        name="Is Exported",
        description="Whether the transformed model has been exported",
        default=False
    )
    
    brush_dataset_prepared: bpy.props.BoolProperty(
        name="Brush Dataset Prepared",
        description="Whether the Brush dataset has been prepared",
        default=False
    )

class SKY_SPLAT_ColmapProperties(bpy.types.PropertyGroup):
    """Properties for COLMAP processing"""
    
    colmap_instances: bpy.props.CollectionProperty(
        type=ColmapInstance,
        name="COLMAP Instances",
        description="Collection of COLMAP instances"
    )
    
    active_colmap_index: bpy.props.IntProperty(
        name="Active COLMAP Index",
        description="Index of the currently active COLMAP instance",
        default=0,
        min=0
    )
    
    colmap_path: bpy.props.StringProperty(
        name="COLMAP Executable",
        description="Path to the COLMAP executable",
        subtype='FILE_PATH',
        default=get_default_colmap_path()
    )
    
    use_gpu: bpy.props.BoolProperty(
        name="Use GPU",
        description="Use GPU acceleration for COLMAP",
        default=True
    )
    
    # Legacy properties for backward compatibility
    input_folder: bpy.props.StringProperty(
        name="Input Folder",
        description="Folder containing images to process with COLMAP (legacy)",
        subtype='DIR_PATH'
    )
    
    output_folder: bpy.props.StringProperty(
        name="Output Folder",
        description="Folder to save COLMAP results (legacy)",
        subtype='DIR_PATH'
    )
    
    model_import_path: bpy.props.StringProperty(
        name="Model Import Path",
        description="Path to sparse model folder (legacy)",
        subtype='DIR_PATH'
    )
    
    model_export_path: bpy.props.StringProperty(
        name="Model Export Path", 
        description="Path where transformed model will be saved (legacy)",
        subtype='DIR_PATH'
    )
    
    images_path: bpy.props.StringProperty(
        name="Images Path",
        description="Path to images folder (legacy)", 
        subtype='DIR_PATH'
    )
    
    camera_model: bpy.props.EnumProperty(
        name="Camera Model",
        description="COLMAP camera model to use (legacy)",
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
        description="Choose between sequential or exhaustive matching (legacy)",
        items=[
            ('SEQUENTIAL', "Sequential", "Use sequential matching"),
            ('EXHAUSTIVE', "Exhaustive", "Use exhaustive matching")
        ],
        default='SEQUENTIAL'
    )
    
    def update_from_video_panel(self, context):
        """Update COLMAP paths based on the frames extracted in the video panel"""
        video_props = context.scene.skysplat_props
        
        # Get active video instance
        if len(video_props.video_instances) > 0:
            video_instance = video_props.video_instances[video_props.active_video_index]
            
            if video_instance.video_path:
                # Get video path and name without extension
                video_path = bpy.path.abspath(video_instance.video_path)
                video_dir = os.path.dirname(video_path)
                video_name = os.path.splitext(os.path.basename(video_path))[0]
                
                # Set default paths based on video name
                frames_folder = os.path.join(video_dir, f"{video_name}_frames")
                colmap_output_folder = os.path.join(video_dir, f"{video_name}_colmap_output")
                
                # Get or create COLMAP instance for this video
                if len(self.colmap_instances) == 0:
                    colmap_instance = self.colmap_instances.add()
                    colmap_instance.name = f"COLMAP_{video_name}"
                else:
                    colmap_instance = self.colmap_instances[self.active_colmap_index]
                
                # Update paths
                colmap_instance.input_folder = frames_folder
                colmap_instance.output_folder = colmap_output_folder
                
                # Set model paths based on COLMAP output structure
                colmap_instance.model_import_path = os.path.join(colmap_output_folder, "sparse", "0")
                colmap_instance.model_export_path = os.path.join(colmap_output_folder, "transformed")
                colmap_instance.images_path = os.path.join(colmap_output_folder, "images")


class SKY_SPLAT_OT_add_colmap_instance(bpy.types.Operator):
    bl_idname = "skysplat.add_colmap_instance"
    bl_label = "Add COLMAP Instance"
    bl_description = "Add a new COLMAP instance"
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        new_instance = props.colmap_instances.add()
        new_instance.name = f"COLMAP_{len(props.colmap_instances)}"
        props.active_colmap_index = len(props.colmap_instances) - 1
        self.report({'INFO'}, f"Added COLMAP instance: {new_instance.name}")
        return {'FINISHED'}

class SKY_SPLAT_OT_remove_colmap_instance(bpy.types.Operator):
    bl_idname = "skysplat.remove_colmap_instance"
    bl_label = "Remove COLMAP Instance"
    bl_description = "Remove the active COLMAP instance"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        return len(props.colmap_instances) > 0
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        if len(props.colmap_instances) > 0:
            props.colmap_instances.remove(props.active_colmap_index)
            props.active_colmap_index = max(0, props.active_colmap_index - 1)
            self.report({'INFO'}, "Removed COLMAP instance")
        return {'FINISHED'}


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
        
        # Log both stdout and stderr - COLMAP often writes important info to stderr
        if result.stdout.strip():
            logger.info(f"Command stdout: {result.stdout.strip()}")
        else:
            logger.info("Command stdout: (empty)")
            
        if result.stderr.strip():
            logger.info(f"Command stderr: {result.stderr.strip()}")
        else:
            logger.info("Command stderr: (empty)")
            
        return 0  # Success
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with return code {e.returncode}: {e}")
        if e.stdout and e.stdout.strip():
            logger.error(f"Failed command stdout: {e.stdout.strip()}")
        if e.stderr and e.stderr.strip():
            logger.error(f"Failed command stderr: {e.stderr.strip()}")
        return e.returncode


def inspect_colmap_database(database_path):
    """Inspect COLMAP database to diagnose feature extraction and matching issues"""
    if not os.path.exists(database_path):
        logger.error(f"Database not found: {database_path}")
        return
    
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        # Check images table
        cursor.execute("SELECT COUNT(*) FROM images")
        image_count = cursor.fetchone()[0]
        logger.info(f"Database contains {image_count} images")
        
        # Check keypoints table
        cursor.execute("SELECT COUNT(*) FROM keypoints")
        keypoint_count = cursor.fetchone()[0]
        logger.info(f"Database contains {keypoint_count} keypoint entries")
        
        # Check matches table
        cursor.execute("SELECT COUNT(*) FROM matches")
        match_count = cursor.fetchone()[0]
        logger.info(f"Database contains {match_count} image pair matches")
        
        # Get detailed keypoint info per image
        cursor.execute("""
            SELECT images.name, keypoints.rows, keypoints.cols
            FROM images
            LEFT JOIN keypoints ON images.image_id = keypoints.image_id
        """)
        keypoint_details = cursor.fetchall()
        
        for name, rows, cols in keypoint_details:
            if rows is not None and cols is not None:
                feature_count = rows
                logger.info(f"Image '{name}': {feature_count} features detected")
            else:
                logger.warning(f"Image '{name}': No features detected!")
        
        # Check for successful matches
        if match_count > 0:
            cursor.execute("SELECT COUNT(*) FROM matches WHERE rows > 0")
            successful_matches = cursor.fetchone()[0]
            logger.info(f"Successful matches: {successful_matches}/{match_count}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Failed to inspect database: {e}")

def validate_input_images(input_path):
    """Validate input images and report potential issues"""
    if not os.path.exists(input_path):
        logger.error(f"Input path does not exist: {input_path}")
        return False
    
    image_files = [f for f in os.listdir(input_path)
                   if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    
    logger.info(f"Found {len(image_files)} images in input directory")
    
    if len(image_files) < 3:
        logger.warning(f"Very few images ({len(image_files)}) - need at least 3 for reconstruction")
        return False
    
    # Check image sizes and report any inconsistencies
    try:
        from PIL import Image
        sizes = []
        for img_file in image_files[:10]:  # Check first 10 images
            img_path = os.path.join(input_path, img_file)
            with Image.open(img_path) as img:
                sizes.append(img.size)
        
        unique_sizes = list(set(sizes))
        if len(unique_sizes) > 1:
            logger.warning(f"Mixed image sizes detected: {unique_sizes}")
        else:
            logger.info(f"All images have consistent size: {unique_sizes[0]}")
            
    except ImportError:
        logger.info("PIL not available - skipping image size validation")
    except Exception as e:
        logger.warning(f"Could not validate image sizes: {e}")
    
    return True

class SKY_SPLAT_OT_run_colmap(bpy.types.Operator):
    bl_idname = "skysplat.run_colmap"
    bl_label = "Run COLMAP"
    bl_description = "Run COLMAP on the input images to generate camera poses"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        if len(props.colmap_instances) == 0:
            return False
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        return colmap_instance.input_folder and os.path.exists(colmap_instance.input_folder) and colmap_instance.output_folder
    
    def execute(self, context):
        from pathlib import Path
        from ..services.colmap import (
            run_reconstruction, FramesSource, ColmapParams, Manual,
        )
        from ..services.errors import ColmapError

        props = context.scene.skysplat_colmap_props
        colmap_instance = props.colmap_instances[props.active_colmap_index]

        source_path = colmap_instance.output_folder
        input_path = Path(source_path) / "input"

        sources = [FramesSource(
            path=input_path,
            source_id=colmap_instance.name,
            camera_model=Manual(model=colmap_instance.camera_model, params=[]),
        )]
        params = ColmapParams(
            mode="joint",
            matching=("sequential" if colmap_instance.matching_type == "SEQUENTIAL" else "exhaustive"),
            use_gpu=props.use_gpu,
            colmap_executable=props.colmap_path or "colmap",
        )

        log_path = Path(source_path) / "colmap_run.log"

        try:
            run_reconstruction(sources, Path(source_path), params, log_path=log_path)
        except ColmapError as exc:
            self.report({'ERROR'}, f"COLMAP failed: {exc}")
            return {'CANCELLED'}

        colmap_instance.is_processed = True
        self.report({'INFO'}, f"COLMAP completed for {colmap_instance.name}")
        return {'FINISHED'}


class SKY_SPLAT_OT_prepare_brush_dataset(bpy.types.Operator):
    bl_idname = "skysplat.prepare_brush_dataset"
    bl_label = "Prepare Brush Dataset"
    bl_description = "Create a properly structured dataset for Brush with transformed model and images"
    
    @classmethod
    def poll(cls, context):
        # Check if transformed model exists and images path is set
        props = context.scene.skysplat_colmap_props
        if len(props.colmap_instances) == 0:
            return False
        
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        if not colmap_instance.model_export_path or not colmap_instance.images_path:
            return False
        
        # Check for exported model (either in sparse/0 subfolder or directly)
        transformed_sparse = os.path.join(colmap_instance.model_export_path, "sparse", "0")
        if not os.path.exists(transformed_sparse):
            # Maybe the model is directly in the export path
            required_files = ['cameras.bin', 'images.bin', 'points3D.bin']
            if not all(os.path.exists(os.path.join(colmap_instance.model_export_path, f)) for f in required_files):
                # Try .txt versions
                txt_files = ['cameras.txt', 'images.txt', 'points3D.txt']
                if not all(os.path.exists(os.path.join(colmap_instance.model_export_path, f)) for f in txt_files):
                    return False
        
        return os.path.exists(colmap_instance.images_path)
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        
        try:
            # Define paths
            export_path = colmap_instance.model_export_path
            images_path = colmap_instance.images_path

            # Determine source sparse model path
            transformed_sparse_src = os.path.join(export_path, "sparse", "0")
            if not os.path.exists(transformed_sparse_src):
                transformed_sparse_src = export_path

            parent_dir = os.path.dirname(export_path)
            brush_dataset_dir = os.path.join(parent_dir, "brush_dataset")

            from ..services.brush import prepare_dataset
            from ..services.errors import BrushError
            try:
                prepare_dataset(
                    Path(transformed_sparse_src),
                    Path(images_path),
                    Path(brush_dataset_dir),
                )
            except BrushError as exc:
                raise RuntimeError(str(exc)) from exc

            # Mark as prepared
            colmap_instance.brush_dataset_prepared = True
            
            self.report({'INFO'}, f"Brush dataset prepared at: {brush_dataset_dir}")
            
            # Auto-update the Gaussian Splatting panel if it exists
            if hasattr(context.scene, 'skysplat_brush_props'):
                brush_props = context.scene.skysplat_brush_props
                # Try to find a matching splat instance by name
                expected_name = f"Splat_{colmap_instance.name}"
                splat_instance = None
                splat_index = -1

                for i, instance in enumerate(brush_props.splat_instances):
                    if instance.name == expected_name:
                        splat_instance = instance
                        splat_index = i
                        break

                # If not found, create a new one
                if splat_instance is None:
                    splat_instance = brush_props.splat_instances.add()
                    splat_instance.name = expected_name
                    splat_index = len(brush_props.splat_instances) - 1
                    self.report({'INFO'}, f"Created new splat instance: {expected_name}")
                else:
                    self.report({'INFO'}, f"Updated existing splat instance: {expected_name}")

                # Set as active and update paths
                brush_props.active_splat_index = splat_index
                splat_instance.source_path = brush_dataset_dir
                if not splat_instance.export_path:
                    splat_instance.export_path = os.path.join(parent_dir, "brush_output")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to prepare Brush dataset: {str(e)}")
            logger.error(f"Failed to prepare Brush dataset: {str(e)}", exc_info=True)
            return {'CANCELLED'}


class SKY_SPLAT_OT_sync_with_video(bpy.types.Operator):
    bl_idname = "skysplat.sync_with_video"
    bl_label = "Sync with Video Panel"
    bl_description = "Set paths based on video file name"
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        props.update_from_video_panel(context)
        self.report({'INFO'}, "COLMAP paths synchronized with video")
        return {'FINISHED'}

# Operator to load COLMAP model into Blender with proper camera transformation
class SKY_SPLAT_OT_load_colmap_model(bpy.types.Operator):
    bl_idname = "skysplat.load_colmap_model"
    bl_label = "Load COLMAP Model"
    bl_description = "Load COLMAP model from specified import path"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        if len(props.colmap_instances) == 0:
            return False
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        return colmap_instance.model_import_path and os.path.exists(colmap_instance.model_import_path)
    
    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        sparse_dir = colmap_instance.model_import_path
        
        # Check if this is a sparse model directory (has the required files)
        required_files = ['cameras.bin', 'images.bin', 'points3D.bin']
        txt_files = ['cameras.txt', 'images.txt', 'points3D.txt'] 
        
        has_bin_files = all(os.path.exists(os.path.join(sparse_dir, f)) for f in required_files)
        has_txt_files = all(os.path.exists(os.path.join(sparse_dir, f)) for f in txt_files)
        
        if not (has_bin_files or has_txt_files):
            self.report({'ERROR'}, f"Sparse reconstruction files not found at {sparse_dir}")
            return {'CANCELLED'}
            
        try:
            # Create a new collection for the COLMAP data with instance name
            collection_name = f"COLMAP_{colmap_instance.name}"
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
            root = bpy.data.objects.new(f"COLMAP_Root_{colmap_instance.name}", None)
            root.empty_display_type = 'ARROWS'
            root.empty_display_size = 1.0
            collection.objects.link(root)
            root['colmap_root'] = True
            root['colmap_model_path'] = sparse_dir
            root['colmap_instance_name'] = colmap_instance.name
            
            # Create point cloud first
            if points3D:
                mesh = bpy.data.meshes.new(f"COLMAP_PointCloud_{colmap_instance.name}")
                obj = bpy.data.objects.new(f"COLMAP_PointCloud_{colmap_instance.name}", mesh)
                collection.objects.link(obj)
                
                # Create vertices and colors
                verts = []
                colors = []
                for point_id, point in points3D.items():
                    # Use COLMAP coordinates directly
                    point_vec = Vector((point.xyz[0], point.xyz[1], point.xyz[2]))
                    verts.append(point_vec)
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
            
            # Create camera objects with original image names
            for image_id, image in images.items():
                # Use the original image filename (without extension) for the camera name
                image_basename = os.path.splitext(image.name)[0]  # Remove file extension
                
                # Create camera object with the original image name
                cam_data = bpy.data.cameras.new(f"Camera_{image_basename}")
                cam_obj = bpy.data.objects.new(f"Camera_{image_basename}", cam_data)
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
                
                # Camera transformation
                # In COLMAP, camera transform is world-to-camera, but Blender expects camera-to-world
                
                # Get rotation matrix from quaternion
                R = qvec2rotmat(image.qvec)
                R = np.array(R)
                
                # Get translation vector
                t = np.array(image.tvec)
                
                # Compute camera center in world coordinates: C = -R^T * t
                cam_center = -R.T @ t
                
                # For Blender, we need the camera-to-world transformation
                # The rotation part is R^T (inverse of world-to-camera rotation)
                R_cam_to_world = R.T
                
                # Convert to Blender matrix format
                rotation_matrix = mathutils.Matrix((
                    (R_cam_to_world[0][0], R_cam_to_world[0][1], R_cam_to_world[0][2]),
                    (R_cam_to_world[1][0], R_cam_to_world[1][1], R_cam_to_world[1][2]),
                    (R_cam_to_world[2][0], R_cam_to_world[2][1], R_cam_to_world[2][2])
                )).to_4x4()
                
                # Set camera location
                rotation_matrix.translation = Vector((cam_center[0], cam_center[1], cam_center[2]))
                
                # Apply coordinate system transformation to fix camera orientation
                # COLMAP uses a different camera coordinate system than Blender
                # We need to rotate 180 degrees around X-axis to flip the camera right-side up
                x_rotation = mathutils.Matrix.Rotation(math.pi, 4, 'X')
                
                # Set the final camera transformation
                cam_obj.matrix_world = rotation_matrix @ x_rotation
                
                # Store COLMAP IDs and original filename information
                cam_obj['colmap_image_id'] = image_id
                cam_obj['colmap_camera_id'] = image.camera_id
                cam_obj['original_filename'] = image.name  # Store the full original filename
                cam_obj['colmap_instance_name'] = colmap_instance.name
                
                # Store original quaternion and tvec for export
                cam_obj['colmap_qvec'] = image.qvec.tolist()
                cam_obj['colmap_tvec'] = image.tvec.tolist()
                
                # Parent to root
                cam_obj.parent = root
            
            # Mark as loaded
            colmap_instance.is_loaded = True
            
            # Select the root object so user can transform it
            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            root.select_set(True)
            bpy.context.view_layer.objects.active = root
            
            self.report({'INFO'}, f"COLMAP model loaded with {len(cameras)} cameras, {len(images)} images, and {len(points3D)} points.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load COLMAP model: {str(e)}")
            logger.error(f"Failed to load COLMAP model: {str(e)}", exc_info=True)
            return {'CANCELLED'}
        
# Operator to export transformed COLMAP model with proper scale handling
class SKY_SPLAT_OT_export_colmap_model(bpy.types.Operator):
    bl_idname = "skysplat.export_colmap_model"
    bl_label = "Export Transformed Model"
    bl_description = "Export the transformed COLMAP model to specified path"
    
    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        if len(props.colmap_instances) == 0:
            return False
        
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        
        # Check if COLMAP root exists in the scene for this instance
        for obj in bpy.data.objects:
            if 'colmap_root' in obj and 'colmap_instance_name' in obj:
                if obj['colmap_instance_name'] == colmap_instance.name:
                    return colmap_instance.model_export_path
        return False
    

    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        colmap_instance = props.colmap_instances[props.active_colmap_index]
        
        try:
            # Find the COLMAP root object for this instance
            root = None
            for obj in bpy.data.objects:
                if 'colmap_root' in obj and 'colmap_instance_name' in obj:
                    if obj['colmap_instance_name'] == colmap_instance.name:
                        root = obj
                        break
            
            if not root:
                self.report({'ERROR'}, f"COLMAP root object not found for instance {colmap_instance.name}")
                return {'CANCELLED'}
            
            # Get the source model path
            source_path = root['colmap_model_path']
            
            # Create export directory
            export_dir = os.path.join(colmap_instance.model_export_path, "sparse", "0")
            os.makedirs(export_dir, exist_ok=True)
            
            # Read the original model via the service.
            from ..services.colmap import read_model, write_model
            from ..services.transform import apply_transform

            model = read_model(Path(source_path))

            # Build the world transform from the COLMAP_Root empty's matrix_world.
            # The historical export logic also undid the X-axis flip applied
            # during import — replicate that by composing an X-rotation inverse
            # into the transform.
            x_flip_inv = mathutils.Matrix.Rotation(-math.pi, 4, 'X')
            world_xform = root.matrix_world @ x_flip_inv

            transformed = apply_transform(model, world_xform)

            # Write the updated model
            write_model(transformed, Path(export_dir), ext=".bin")
            
            # Mark as exported
            colmap_instance.is_exported = True
            
            self.report({'INFO'}, f"Transformed COLMAP model exported to {export_dir}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export COLMAP model: {str(e)}")
            logger.error(f"Failed to export COLMAP model: {str(e)}", exc_info=True)
            return {'CANCELLED'}


class SKY_SPLAT_OT_create_camera_animation(bpy.types.Operator):
    bl_idname = "skysplat.create_camera_animation"
    bl_label = "Create Camera Animation"
    bl_description = "Create or update a camera with keyframes aligned to COLMAP cameras"

    @classmethod
    def poll(cls, context):
        props = context.scene.skysplat_colmap_props
        if len(props.colmap_instances) == 0:
            return False

        colmap_instance = props.colmap_instances[props.active_colmap_index]

        # Check if COLMAP cameras exist in the scene for this instance
        for obj in bpy.data.objects:
            if 'colmap_image_id' in obj and 'colmap_instance_name' in obj:
                if obj['colmap_instance_name'] == colmap_instance.name:
                    return True
        return False

    def execute(self, context):
        props = context.scene.skysplat_colmap_props
        colmap_instance = props.colmap_instances[props.active_colmap_index]

        try:
            # Find all COLMAP cameras for this instance
            colmap_cameras = []
            for obj in bpy.data.objects:
                if 'colmap_image_id' in obj and 'colmap_instance_name' in obj:
                    if obj['colmap_instance_name'] == colmap_instance.name:
                        colmap_cameras.append(obj)

            if not colmap_cameras:
                self.report({'ERROR'}, "No COLMAP cameras found for this instance")
                return {'CANCELLED'}

            # Parse frame numbers from camera names
            frame_camera_map = {}
            for cam_obj in colmap_cameras:
                # Get the camera name (e.g., "Camera_frame_00001" or "Camera_frame_00001.001")
                cam_name = cam_obj.name

                # Extract the frame number
                # Look for pattern like "frame_00001" or just the numeric part
                # Try to find frame_XXXXX pattern first
                match = re.search(r'frame[_-]?(\d+)', cam_name, re.IGNORECASE)
                if match:
                    frame_num = int(match.group(1))
                else:
                    # Try to find just a number sequence
                    match = re.search(r'(\d{4,})', cam_name)
                    if match:
                        frame_num = int(match.group(1))
                    else:
                        logger.warning(f"Could not parse frame number from camera name: {cam_name}")
                        continue

                frame_camera_map[frame_num] = cam_obj

            if not frame_camera_map:
                self.report({'ERROR'}, "Could not parse frame numbers from camera names")
                return {'CANCELLED'}

            # Get or create animated camera
            animated_cam_name = f"AnimatedCamera_{colmap_instance.name}"

            if animated_cam_name in bpy.data.objects:
                animated_cam = bpy.data.objects[animated_cam_name]
            else:
                # Create new camera
                cam_data = bpy.data.cameras.new(animated_cam_name)
                animated_cam = bpy.data.objects.new(animated_cam_name, cam_data)
                context.scene.collection.objects.link(animated_cam)

            # Get camera resolution from COLMAP data
            # All cameras in a COLMAP instance should have the same resolution
            first_colmap_cam = colmap_cameras[0]

            # Get the COLMAP root to access the model
            root = None
            for obj in bpy.data.objects:
                if 'colmap_root' in obj and 'colmap_instance_name' in obj:
                    if obj['colmap_instance_name'] == colmap_instance.name:
                        root = obj
                        break

            if root and 'colmap_model_path' in root:
                # Read camera data from COLMAP model
                cameras, images, points3D = read_model(root['colmap_model_path'])

                # Get camera ID from first COLMAP camera
                if 'colmap_camera_id' in first_colmap_cam:
                    camera_id = first_colmap_cam['colmap_camera_id']
                    colmap_camera = cameras[camera_id]

                    # Set render resolution
                    context.scene.render.resolution_x = colmap_camera.width
                    context.scene.render.resolution_y = colmap_camera.height

                    # Set camera sensor and focal length
                    cam_data = animated_cam.data
                    cam_data.lens_unit = 'MILLIMETERS'

                    if hasattr(colmap_camera, 'params') and len(colmap_camera.params) > 0:
                        focal_length_pixels = colmap_camera.params[0]
                        sensor_width_mm = 36.0  # Standard full frame width
                        focal_length_mm = (focal_length_pixels * sensor_width_mm) / colmap_camera.width
                        cam_data.lens = focal_length_mm

                    logger.info(f"Set camera resolution to {colmap_camera.width}x{colmap_camera.height}")

            # Clear existing animation data
            if animated_cam.animation_data:
                animated_cam.animation_data_clear()

            # Sort frames
            sorted_frames = sorted(frame_camera_map.keys())

            # Set scene frame range
            context.scene.frame_start = min(sorted_frames)
            context.scene.frame_end = max(sorted_frames)

            # Set camera to use quaternion rotation mode to avoid gimbal lock
            animated_cam.rotation_mode = 'QUATERNION'

            # Extract all rotations and locations first
            locations = []
            quaternions = []

            for frame_num in sorted_frames:
                colmap_cam = frame_camera_map[frame_num]

                # Decompose the matrix to get location and rotation
                loc, rot_quat, scale = colmap_cam.matrix_world.decompose()

                locations.append(loc)
                quaternions.append(rot_quat)

            # Ensure quaternion continuity by making sure each quaternion is in the same hemisphere
            # as the previous one (avoiding 180-degree flips)
            for i in range(1, len(quaternions)):
                # Check if we need to flip the quaternion to maintain continuity
                # q and -q represent the same rotation, so we pick the one closer to the previous
                dot_product = quaternions[i].dot(quaternions[i-1])
                if dot_product < 0:
                    # Flip the quaternion to maintain continuity
                    quaternions[i].negate()

            # Create keyframes for each frame
            for i, frame_num in enumerate(sorted_frames):
                # Set the current frame
                context.scene.frame_set(frame_num)

                # Set location and rotation
                animated_cam.location = locations[i]
                animated_cam.rotation_quaternion = quaternions[i]

                # Insert keyframes for location and rotation
                animated_cam.keyframe_insert(data_path="location", frame=frame_num)
                animated_cam.keyframe_insert(data_path="rotation_quaternion", frame=frame_num)

            # Set the animated camera as the active camera
            context.scene.camera = animated_cam

            self.report({'INFO'}, f"Created camera animation with {len(sorted_frames)} keyframes (frames {min(sorted_frames)}-{max(sorted_frames)})")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to create camera animation: {str(e)}")
            logger.error(f"Failed to create camera animation: {str(e)}", exc_info=True)
            return {'CANCELLED'}


# Update the panel to include model import/export UI
class SKY_SPLAT_PT_colmap_panel(bpy.types.Panel):
    bl_label = "SkySplat - Structure from Motion (COLMAP)"
    bl_idname = "SKY_SPLAT_PT_colmap_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SkySplat"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.skysplat_colmap_props
        
        # COLMAP instance management
        box = layout.box()
        box.label(text="COLMAP Instances", icon='CAMERA_DATA')
        
        row = box.row()
        row.template_list("UI_UL_list", "colmap_instances", props, "colmap_instances", 
                         props, "active_colmap_index", rows=3)
        
        col = row.column(align=True)
        col.operator("skysplat.add_colmap_instance", icon='ADD', text="")
        col.operator("skysplat.remove_colmap_instance", icon='REMOVE', text="")
        
        # Show active COLMAP instance settings
        if len(props.colmap_instances) > 0 and props.active_colmap_index < len(props.colmap_instances):
            colmap_instance = props.colmap_instances[props.active_colmap_index]
            
            # Instance name
            box.prop(colmap_instance, "name")
            
            # COLMAP executables and options
            box = layout.box()
            box.label(text="COLMAP Settings")
            box.prop(props, "colmap_path")
            box.prop(colmap_instance, "camera_model")
            box.prop(colmap_instance, "matching_type")
            
            row = box.row()
            row.prop(props, "use_gpu")
            
            # Input/Output settings for COLMAP processing
            box = layout.box()
            box.label(text="COLMAP Processing")
            
            row = box.row()
            row.prop(colmap_instance, "input_folder")
            row.operator("skysplat.sync_with_video", icon='LINKED', text="")
            
            box.prop(colmap_instance, "output_folder")
            
            # Run COLMAP button
            row = box.row()
            row.operator("skysplat.run_colmap", icon='CAMERA_DATA')
            if colmap_instance.is_processed:
                row.label(text="✓ Processed", icon='CHECKMARK')
            
            # COLMAP model transformation section
            box = layout.box()
            box.label(text="COLMAP Model Transformation")
            
            # Model paths
            path_box = box.box()
            path_box.label(text="Model Paths:")
            path_box.prop(colmap_instance, "model_import_path", text="Import From")
            path_box.prop(colmap_instance, "model_export_path", text="Export To")
            path_box.prop(colmap_instance, "images_path", text="Images")
            
            # Load model button
            row = box.row()
            row.operator("skysplat.load_colmap_model", icon='IMPORT')
            if colmap_instance.is_loaded:
                row.label(text="✓ Loaded", icon='CHECKMARK')
            
            # Check if model is loaded
            has_colmap_root = False
            for obj in bpy.data.objects:
                if 'colmap_root' in obj and 'colmap_instance_name' in obj:
                    if obj['colmap_instance_name'] == colmap_instance.name:
                        has_colmap_root = True
                        break
                    
            if has_colmap_root:
                # Instructions
                box.label(text="Use Blender's transform tools to adjust the model.")
                box.label(text=f"Select COLMAP_Root_{colmap_instance.name} to transform.")
                
                # Export model button
                row = box.row()
                row.operator("skysplat.export_colmap_model", icon='EXPORT')
                if colmap_instance.is_exported:
                    row.label(text="✓ Exported", icon='CHECKMARK')

                # Camera Animation section
                box.separator()
                box.label(text="Camera Animation")
                box.operator("skysplat.create_camera_animation", icon='CAMERA_DATA')
                box.label(text="Creates animated camera from COLMAP cameras", icon='INFO')

            # Brush dataset preparation section
            box = layout.box()
            box.label(text="Brush Dataset Preparation")
            
            # Check if we can prepare brush dataset
            can_prepare_brush = False
            if colmap_instance.model_export_path and colmap_instance.images_path:
                # Check for exported model (either in sparse/0 subfolder or directly)
                transformed_sparse = os.path.join(colmap_instance.model_export_path, "sparse", "0")
                if os.path.exists(transformed_sparse) and os.path.exists(colmap_instance.images_path):
                    can_prepare_brush = True
                elif os.path.exists(colmap_instance.model_export_path) and os.path.exists(colmap_instance.images_path):
                    # Check if model files are directly in export path
                    required_files = ['cameras.bin', 'images.bin', 'points3D.bin']
                    txt_files = ['cameras.txt', 'images.txt', 'points3D.txt']
                    has_bin_files = all(os.path.exists(os.path.join(colmap_instance.model_export_path, f)) for f in required_files)
                    has_txt_files = all(os.path.exists(os.path.join(colmap_instance.model_export_path, f)) for f in txt_files)
                    can_prepare_brush = has_bin_files or has_txt_files
            
            if can_prepare_brush:
                row = box.row()
                row.operator("skysplat.prepare_brush_dataset", icon='PACKAGE')
                if colmap_instance.brush_dataset_prepared:
                    row.label(text="✓ Prepared", icon='CHECKMARK')
                parent_dir = os.path.dirname(colmap_instance.model_export_path) if colmap_instance.model_export_path else ""
                box.label(text=f"Creates: {parent_dir}/brush_dataset/", icon='INFO')
            else:
                box.label(text="Export transformed model and set images path first", icon='ERROR')
            
            # Info about shared paths
            box = layout.box()
            box.label(text="💡 Tip: Multiple videos can use the same", icon='INFO')
            box.label(text="input folder for combined COLMAP processing")
        else:
            box.label(text="Add a COLMAP instance to begin", icon='INFO')
        
        # Version indicator at the bottom
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Version: {PANEL_VERSION}")


# Registration
classes = (
    ColmapInstance,
    SKY_SPLAT_ColmapProperties,
    SKY_SPLAT_OT_add_colmap_instance,
    SKY_SPLAT_OT_remove_colmap_instance,
    SKY_SPLAT_OT_run_colmap,
    SKY_SPLAT_OT_sync_with_video,
    SKY_SPLAT_OT_load_colmap_model,
    SKY_SPLAT_OT_export_colmap_model,
    SKY_SPLAT_OT_create_camera_animation,
    SKY_SPLAT_OT_prepare_brush_dataset,
    SKY_SPLAT_PT_colmap_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.skysplat_colmap_props = bpy.props.PointerProperty(type=SKY_SPLAT_ColmapProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.skysplat_colmap_props
    