# Multi-Instance Workflow Guide

## Overview

SkySplat Blender Toolkit v0.4.0 introduces **multi-instance support**, allowing you to work with multiple videos, COLMAP models, and Gaussian Splatting training sessions simultaneously within a single Blender project.

## Key Features

### 1. Multiple Video Instances
- Load and process multiple videos independently
- Each video has its own extraction settings (frame range, step, output folder)
- **Shared extraction paths**: Multiple videos can extract to the same folder for combined COLMAP processing

### 2. Multiple COLMAP Instances
- Run COLMAP on different image sets independently
- Each instance maintains its own camera model, matching type, and paths
- Support for both individual and combined reconstructions

### 3. Multiple Splat Instances
- Train multiple Gaussian Splatting models simultaneously
- Each instance has independent training parameters
- Track training status per instance

## Workflow Examples

### Example 1: Single Video, Single COLMAP, Single Splat (Traditional)

This is the simplest workflow, similar to the previous version:

1. **Video Panel**:
   - Click `+` to add a video instance
   - Name it "Video_1"
   - Select your video file
   - Click "Load Video and SRT"
   - Click "Extract Frames"

2. **COLMAP Panel**:
   - Click `+` to add a COLMAP instance
   - Name it "COLMAP_1"
   - Click the sync button (🔗) to auto-populate paths from video
   - Click "Run COLMAP"
   - Click "Load COLMAP Model"
   - Transform the model in Blender
   - Click "Export Transformed Model"
   - Click "Prepare Brush Dataset"

3. **Gaussian Splatting Panel**:
   - Click `+` to add a splat instance
   - Name it "Splat_1"
   - Click the sync button (🔗) to auto-populate paths from COLMAP
   - Adjust training parameters
   - Click "Run Brush Training"

### Example 2: Multiple Videos, Combined COLMAP, Single Splat

Use this when you want to combine multiple videos into a single 3D reconstruction:

1. **Video Panel**:
   - Add first video instance: "Video_Front"
     - Select front-facing video
     - Set output folder to `/path/to/combined_frames`
     - Extract frames
   
   - Add second video instance: "Video_Side"
     - Select side-facing video
     - **Set output folder to the SAME path**: `/path/to/combined_frames`
     - Extract frames
   
   - Add third video instance: "Video_Top"
     - Select top-down video
     - **Set output folder to the SAME path**: `/path/to/combined_frames`
     - Extract frames

2. **COLMAP Panel**:
   - Add COLMAP instance: "COLMAP_Combined"
   - Set input folder to `/path/to/combined_frames`
   - Set output folder to `/path/to/combined_colmap_output`
   - Run COLMAP (will process all frames from all videos together)
   - Load, transform, export, and prepare brush dataset

3. **Gaussian Splatting Panel**:
   - Add splat instance: "Splat_Combined"
   - Sync with COLMAP
   - Run training

### Example 3: Multiple Videos, Multiple COLMAP, Multiple Splats

Use this for completely independent reconstructions:

1. **Video Panel**:
   - Add "Video_Scene1" → extract to `/path/to/scene1_frames`
   - Add "Video_Scene2" → extract to `/path/to/scene2_frames`
   - Add "Video_Scene3" → extract to `/path/to/scene3_frames`

2. **COLMAP Panel**:
   - Add "COLMAP_Scene1" → process scene1_frames
   - Add "COLMAP_Scene2" → process scene2_frames
   - Add "COLMAP_Scene3" → process scene3_frames
   - Process each independently

3. **Gaussian Splatting Panel**:
   - Add "Splat_Scene1" → train from COLMAP_Scene1
   - Add "Splat_Scene2" → train from COLMAP_Scene2
   - Add "Splat_Scene3" → train from COLMAP_Scene3
   - Train simultaneously (each in its own process)

### Example 4: Single Video, Multiple COLMAP Experiments

Use this to test different COLMAP settings on the same video:

1. **Video Panel**:
   - Add "Video_Test" → extract frames once

2. **COLMAP Panel**:
   - Add "COLMAP_Sequential_OpenCV"
     - Input: same frames folder
     - Camera Model: OpenCV
     - Matching: Sequential
     - Output: `/path/to/test_sequential_opencv`
   
   - Add "COLMAP_Exhaustive_OpenCV"
     - Input: same frames folder
     - Camera Model: OpenCV
     - Matching: Exhaustive
     - Output: `/path/to/test_exhaustive_opencv`
   
   - Add "COLMAP_Sequential_Pinhole"
     - Input: same frames folder
     - Camera Model: Pinhole
     - Matching: Sequential
     - Output: `/path/to/test_sequential_pinhole`

3. **Gaussian Splatting Panel**:
   - Create splat instances for each COLMAP result
   - Compare training results

## UI Features

### Instance Management

Each panel has an instance list with `+` and `-` buttons:
- **`+` button**: Add a new instance
- **`-` button**: Remove the selected instance
- **List**: Click to select and view/edit an instance

### Status Indicators

Visual feedback shows the state of each instance:
- **Video Panel**:
  - ✓ Loaded: Video is loaded in sequencer
  - ✓ Extracted: Frames have been extracted

- **COLMAP Panel**:
  - ✓ Processed: COLMAP reconstruction completed
  - ✓ Loaded: Model loaded in Blender
  - ✓ Exported: Transformed model exported
  - ✓ Prepared: Brush dataset prepared

- **Gaussian Splatting Panel**:
  - Training in progress...: Currently training
  - ✓ Completed: Training finished successfully

### Sync Buttons (🔗)

Each panel has a sync button that auto-populates paths:
- **COLMAP Panel**: Syncs with active video instance
- **Gaussian Splatting Panel**: Syncs with active COLMAP instance

## Best Practices

### Naming Conventions

Use descriptive names for instances:
- Videos: `Video_Front`, `Video_Side`, `Video_Aerial`
- COLMAP: `COLMAP_Combined`, `COLMAP_Scene1`, `COLMAP_Test_Sequential`
- Splats: `Splat_Final`, `Splat_LowRes`, `Splat_Experiment1`

### Shared vs. Separate Paths

**Use shared extraction paths when**:
- Combining multiple videos for a single reconstruction
- Videos show the same scene from different angles
- You want COLMAP to find matches across all videos

**Use separate extraction paths when**:
- Videos show completely different scenes
- You want independent reconstructions
- Testing different frame extraction settings

### COLMAP Model Organization

When loading multiple COLMAP models in Blender:
- Each model creates a separate collection: `COLMAP_InstanceName`
- Each has its own root object: `COLMAP_Root_InstanceName`
- Transform each root independently
- Export each model separately

### Training Multiple Splats

- Each splat instance trains in its own process
- You can start multiple training sessions simultaneously
- Monitor console output for each instance
- Each instance has independent export settings

## Tips and Tricks

1. **Incremental Workflow**: Start with one instance of each type, verify it works, then add more

2. **Path Organization**: Use consistent folder structures:
   ```
   project/
   ├── video1_frames/
   ├── video1_colmap_output/
   ├── video1_brush_output/
   ├── video2_frames/
   ├── video2_colmap_output/
   └── video2_brush_output/
   ```

3. **Combined Reconstructions**: When combining videos, ensure:
   - Similar lighting conditions
   - Overlapping coverage
   - Consistent camera settings

4. **Memory Management**: Be mindful when:
   - Loading multiple large COLMAP models
   - Training multiple splats simultaneously
   - Working with high-resolution videos

5. **Backup**: Save your Blender file frequently when working with multiple instances

## Troubleshooting

### "No instances" message
- Click the `+` button to add an instance before proceeding

### Sync button doesn't populate paths
- Ensure the source instance (video or COLMAP) has valid paths set
- Check that the source instance is selected in its panel

### Multiple COLMAP models overlap in viewport
- Select each `COLMAP_Root_*` object and move them apart
- Use collections to organize visibility

### Training fails to start
- Verify the source path exists and contains required files
- Check that the instance is not already training
- Ensure Brush executable path is correct

## Migration from v0.3.x

The plugin maintains backward compatibility:
- Old single-instance workflows still work
- Legacy properties are preserved
- First-time users will see empty instance lists (just click `+` to add)

To migrate existing projects:
1. Open your v0.3.x project in v0.4.0
2. Add one instance in each panel
3. The sync buttons will help populate paths from your existing setup
4. Your existing COLMAP models in the scene will still work

## Advanced: Scripting with Instances

You can access instances via Python:

```python
import bpy

# Access video instances
video_props = bpy.context.scene.skysplat_props
for i, video in enumerate(video_props.video_instances):
    print(f"Video {i}: {video.name} - {video.video_path}")

# Access COLMAP instances
colmap_props = bpy.context.scene.skysplat_colmap_props
for i, colmap in enumerate(colmap_props.colmap_instances):
    print(f"COLMAP {i}: {colmap.name} - {colmap.output_folder}")

# Access splat instances
brush_props = bpy.context.scene.skysplat_brush_props
for i, splat in enumerate(brush_props.splat_instances):
    print(f"Splat {i}: {splat.name} - Training: {splat.is_training}")
```

## Summary

Multi-instance support provides flexibility for:
- ✅ Complex multi-video reconstructions
- ✅ Parallel processing of different scenes
- ✅ Experimentation with different settings
- ✅ Organized project management
- ✅ Simultaneous training of multiple models

The key innovation is the ability to **share extraction paths** while maintaining **independent processing pipelines**, giving you complete control over your 3D reconstruction workflow.