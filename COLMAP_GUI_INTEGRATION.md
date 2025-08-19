# COLMAP GUI Integration

This document explains how COLMAP has been integrated with GUI support that runs in the background of Blender, similar to the brush app integration.

## Overview

The SkySplat Blender addon now supports three ways to run COLMAP:

1. **CLI Mode** (Original): Blocking command-line execution
2. **GUI Mode** (New): Non-blocking COLMAP GUI that runs alongside Blender
3. **Auto Mode** (New): Non-blocking automatic reconstruction with progress monitoring

## Features

### COLMAP GUI Mode

- **Background Execution**: COLMAP GUI runs as a separate process, allowing full Blender interaction
- **Independent Operation**: GUI window operates independently from Blender
- **Project Integration**: Automatically loads project paths when available
- **Manual Control**: Full access to all COLMAP features through the native GUI

### COLMAP Automatic Mode

- **Background Processing**: Runs automatic reconstruction without blocking Blender
- **Progress Monitoring**: Real-time output monitoring in Blender console
- **Auto Path Updates**: Automatically updates addon paths after successful completion
- **Cancellation Support**: Can be cancelled mid-process if needed

## Implementation Details

### Architecture

The implementation follows the same pattern as the brush app integration:

```python
# Background execution using threading
self._thread = threading.Thread(target=self.launch_colmap_gui, args=(props,))
self._thread.start()

# Non-blocking UI using modal handlers
wm = context.window_manager
self._timer = wm.event_timer_add(0.5, window=context.window)
wm.modal_handler_add(self)

# Independent process management
self._process = subprocess.Popen(command, ...)
```

### Key Components

1. **SKY_SPLAT_OT_run_colmap_gui**: Launches COLMAP GUI in background
2. **SKY_SPLAT_OT_run_colmap_automatic**: Runs automatic reconstruction in background
3. **Modal Operators**: Use Blender's modal system for non-blocking execution
4. **Thread Management**: Proper cleanup and cancellation support

## Usage

### Launching COLMAP GUI

1. Set up your COLMAP executable path in the addon settings
2. Configure input/output folders as needed
3. Click "Launch GUI" button in the COLMAP panel
4. COLMAP GUI opens in a separate window
5. Continue working in Blender while COLMAP GUI runs

### Running Automatic Reconstruction

1. Set input folder (containing images)
2. Set output folder (where results will be saved)
3. Configure camera model and GPU settings
4. Click "Auto Reconstruction" button
5. Monitor progress in Blender console
6. Paths are automatically updated when complete

## Benefits

### For Users

- **Multitasking**: Work in Blender while COLMAP processes images
- **Visual Feedback**: See COLMAP's GUI progress and 3D visualization
- **Flexibility**: Choose between GUI control or automatic processing
- **Integration**: Seamless path synchronization between COLMAP and Blender

### For Developers

- **Consistent Pattern**: Same architecture as brush app integration
- **Maintainable**: Clean separation of concerns
- **Extensible**: Easy to add more COLMAP features
- **Robust**: Proper error handling and cleanup

## Technical Requirements

### COLMAP Build Requirements

COLMAP must be built with GUI support enabled:

```bash
# When building COLMAP, ensure Qt is available and GUI is enabled
cmake .. -DCOLMAP_GUI_ENABLED=ON
```

### System Requirements

- **Qt Framework**: Required for COLMAP GUI
- **Display Server**: X11/Wayland on Linux, native on Windows/macOS
- **OpenGL**: For 3D visualization in COLMAP GUI

## Comparison with Brush App Integration

| Feature | Brush App | COLMAP GUI | COLMAP Auto |
|---------|-----------|------------|-------------|
| Background Execution | ✅ | ✅ | ✅ |
| Non-blocking UI | ✅ | ✅ | ✅ |
| Progress Monitoring | ✅ | ✅ | ✅ |
| Visual Interface | ❌ | ✅ | ❌ |
| Manual Control | ❌ | ✅ | ❌ |
| Auto Path Updates | ✅ | ❌ | ✅ |

## Troubleshooting

### Common Issues

1. **GUI Won't Launch**
   - Check COLMAP executable path
   - Verify COLMAP was built with GUI support
   - Ensure Qt libraries are available

2. **Process Hangs**
   - Check console output for error messages
   - Verify input/output paths exist and are writable
   - Try running COLMAP manually to test

3. **Path Issues**
   - Use absolute paths when possible
   - Check file permissions
   - Verify folder structure matches expectations

### Debug Information

Enable debug output by checking Blender's console:
- Windows: Window > Toggle System Console
- macOS/Linux: Run Blender from terminal

## Future Enhancements

Potential improvements for future versions:

1. **Progress Bars**: Visual progress indicators in Blender UI
2. **Real-time Updates**: Live synchronization of COLMAP results
3. **Preset Management**: Save/load COLMAP configuration presets
4. **Batch Processing**: Process multiple image sets automatically
5. **Cloud Integration**: Support for cloud-based COLMAP processing

## Code Examples

### Basic GUI Launch

```python
# Launch COLMAP GUI with current project
bpy.ops.skysplat.run_colmap_gui()
```

### Automatic Reconstruction

```python
# Run automatic reconstruction
props = bpy.context.scene.skysplat_colmap_props
props.input_folder = "/path/to/images"
props.output_folder = "/path/to/output"
bpy.ops.skysplat.run_colmap_automatic()
```

### Custom Integration

```python
# Access the operators programmatically
from skysplat_blender.operators.run_colmap_gui import (
    SKY_SPLAT_OT_run_colmap_gui,
    SKY_SPLAT_OT_run_colmap_automatic
)
```

This integration provides a seamless workflow for 3D reconstruction within the Blender environment while maintaining the flexibility and power of COLMAP's native tools.