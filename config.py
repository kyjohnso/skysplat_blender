"""
SkySplat Blender Addon Configuration

This module contains configuration constants and settings for the SkySplat addon.
"""

import os

# Addon metadata
ADDON_NAME = "SkySplat: 3DGS Blender Toolkit"
ADDON_VERSION = "0.4.2"
ADDON_AUTHOR = "Kyle Johnson"
ADDON_DESCRIPTION = "Workflow tools for 3D Gaussian Splatting using Blender, COLMAP, and Brush"

# Default paths and settings
DEFAULT_FRAME_STEP = 5
DEFAULT_MAX_RESOLUTION = 1920
DEFAULT_TOTAL_STEPS = 30000

# Camera model options for COLMAP
COLMAP_CAMERA_MODELS = [
    ('SIMPLE_PINHOLE', 'Simple Pinhole', 'Simple pinhole camera model'),
    ('PINHOLE', 'Pinhole', 'Pinhole camera model'),
    ('SIMPLE_RADIAL', 'Simple Radial', 'Simple radial camera model'),
    ('RADIAL', 'Radial', 'Radial camera model'),
    ('OPENCV', 'OpenCV', 'OpenCV camera model'),
    ('FULL_OPENCV', 'Full OpenCV', 'Full OpenCV camera model'),
]

# File extensions
SUPPORTED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v'}
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp'}

# Bundled binary names
BUNDLED_BINARY_NAMES = {
    "Windows": "brush_app_windows.exe",
    "Darwin": "brush_app_mac", 
    "Linux": "brush_app_linux"
}

# Panel versions (for UI display)
PANEL_VERSIONS = {
    "video": "0.4.2",
    "colmap": "0.4.2",
    "gaussian_splatting": "0.4.2"
}

def get_addon_directory():
    """Get the addon installation directory"""
    return os.path.dirname(os.path.abspath(__file__))

def get_bundled_binaries_directory():
    """Get the directory containing bundled binaries"""
    return os.path.join(get_addon_directory(), "binaries")