"""
SkySplat Blender Addon Configuration

This module contains configuration constants and settings for the SkySplat addon.
"""

import os
import platform
import subprocess

# Addon metadata
ADDON_NAME = "SkySplat: 3DGS Blender Toolkit"
ADDON_VERSION = "0.4.1"
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
    "video": "0.4.1",
    "colmap": "0.4.1",
    "gaussian_splatting": "0.4.1"
}

def get_addon_directory():
    """Get the addon installation directory"""
    return os.path.dirname(os.path.abspath(__file__))

def get_bundled_binaries_directory():
    """Get the directory containing bundled binaries"""
    return os.path.join(get_addon_directory(), "binaries")


def get_default_colmap_path():
    """Get default COLMAP executable path based on operating system.

    Scans common install locations per platform (and `which colmap` on
    Linux). Returns "" if nothing is found — callers fall back to "colmap"
    on PATH. Shared by the sidebar panel and the COLMAP node.
    """
    system = platform.system()

    if system == "Windows":
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
        possible_paths = [
            "/Applications/COLMAP.app/Contents/MacOS/colmap",
            "/usr/local/bin/colmap",
            "/opt/homebrew/bin/colmap",
            os.path.expanduser("~/Applications/COLMAP.app/Contents/MacOS/colmap"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""

    elif system == "Linux":
        # Try to find colmap in PATH first.
        try:
            result = subprocess.run(["which", "colmap"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        possible_paths = [
            "/usr/bin/colmap",
            "/usr/local/bin/colmap",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""

    return ""


def get_default_brush_path():
    """Get default Brush executable path based on operating system.

    Prefers a bundled binary, then a user-compiled one under
    ~/projects/brush/target/release/, and finally returns the (possibly
    nonexistent) bundled path so the field shows where it should live.
    Shared by the sidebar panel and the Brush Train node.
    """
    system = platform.system()

    # First priority: bundled binaries shipped with the addon.
    if system in BUNDLED_BINARY_NAMES:
        bundled_binary_name = BUNDLED_BINARY_NAMES[system]
        bundled_path = os.path.join(get_bundled_binaries_directory(), bundled_binary_name)
        if os.path.exists(bundled_path):
            return bundled_path

    # Fallback: user-compiled binary in the conventional build location.
    home = os.path.expanduser("~")
    if system == "Windows":
        user_path = os.path.join(home, "projects", "brush", "target", "release", "brush_app.exe")
    elif system in ("Darwin", "Linux"):
        user_path = os.path.join(home, "projects", "brush", "target", "release", "brush_app")
    else:
        return ""

    if os.path.exists(user_path):
        return user_path

    # Neither exists — surface the bundled path so the user sees where it goes.
    if system in BUNDLED_BINARY_NAMES:
        bundled_binary_name = BUNDLED_BINARY_NAMES[system]
        return os.path.join(get_bundled_binaries_directory(), bundled_binary_name)

    return ""