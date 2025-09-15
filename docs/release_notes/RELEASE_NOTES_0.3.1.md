# SkySplat 0.3.1 Release Notes

**Release Date:** September 14, 2025

## Overview

SkySplat 0.3.1 is a quality-of-life update that focuses on improving user experience, documentation, and operational visibility. This release includes timing information for operations, enhanced documentation, improved camera handling, and new example imagery.

## 🆕 New Features

### Performance Timing
- **Operation Timing**: Added execution time logging for COLMAP processing and frame extraction operations
  - COLMAP operations now display completion time in seconds
  - Frame extraction shows processing duration
  - Timing information is printed to the Blender console for performance monitoring

### Enhanced Documentation
- **Command Line Usage Guide**: Added comprehensive section on running Blender from command line
  - Benefits of CLI usage for monitoring COLMAP output, Brush training, and debug information
  - Platform-specific command examples for macOS, Linux, and Windows
  - Detailed explanation of why CLI usage is recommended for advanced workflows

### New Example Content
- **Sky Islands Gallery**: Added three new high-quality example images showcasing advanced 3D Gaussian Splatting results
- **Point Cloud Visualization**: New portrait-oriented point cloud example image
- **Bridge Example**: Additional small-format bridge rendering example

## 🔧 Improvements

### COLMAP Integration
- **macOS Homebrew Support**: Added `/opt/homebrew/bin/colmap` to default COLMAP path detection for Apple Silicon Macs
- **Camera Orientation Fix**: Improved camera coordinate system transformation
  - Changed from Y-axis to X-axis rotation for better camera orientation
  - Fixes camera right-side-up positioning in Blender viewport
  - More accurate camera-to-world transformation during model export

### User Interface
- **Quality of Life Enhancements**: Various UI improvements for better user experience
- **Version Consistency**: Updated panel version numbers across all UI components

### Documentation Updates
- **Installation Instructions**: Enhanced COLMAP installation section with more explicit platform-specific guidance
- **Brush App Setup**: Improved installation instructions for the bundled Brush application
- **Workflow Clarifications**: Updated various sections for better clarity and accuracy

## 🐛 Bug Fixes

- **Camera Import**: Fixed camera orientation issues when loading COLMAP models into Blender
- **Path Detection**: Improved automatic path detection for COLMAP executable on different platforms
- **Version Numbering**: Corrected inconsistent version numbers across UI panels

## 📁 File Changes

### Modified Files
- [`ui/colmap_panel.py`](ui/colmap_panel.py): Added timing logs, improved camera handling, enhanced COLMAP path detection
- [`ui/video_panel.py`](ui/video_panel.py): Added frame extraction timing, version updates
- [`ui/gaussian_splatting_panel.py`](ui/gaussian_splatting_panel.py): Version consistency updates
- [`config.py`](config.py): Version number updates
- [`__init__.py`](__init__.py): Version bump to 0.3.1
- [`README.md`](README.md): Extensive documentation improvements and new sections
- [`.gitignore`](.gitignore): Added .DS_Store exclusion

### New Files
- [`images/sky_island_1.png`](images/sky_island_1.png): New example rendering (3.96MB)
- [`images/sky_island_2.png`](images/sky_island_2.png): New example rendering (2.28MB)  
- [`images/sky_island_3.png`](images/sky_island_3.png): New example rendering (2.29MB)
- [`images/pointcloud_portrait.png`](images/pointcloud_portrait.png): Point cloud visualization (2.67MB)
- [`images/puente_nuevo_bridge_small.png`](images/puente_nuevo_bridge_small.png): Bridge example (2.97MB)
- Multiple updated workflow images showing improved UI and results

## 🔄 Migration Notes

This is a minor update with no breaking changes. Users can upgrade directly from 0.3.0 without any configuration changes.

### For macOS Users
- If you installed COLMAP via Homebrew on Apple Silicon, the addon will now automatically detect the executable at `/opt/homebrew/bin/colmap`
- No manual configuration required for standard Homebrew installations

### For All Users
- To see the new timing information, run Blender from the command line as described in the updated documentation
- The timing logs will appear in the terminal output during COLMAP and frame extraction operations

## 📋 Technical Details

### Performance Monitoring
The new timing feature helps users understand processing duration for:
- **COLMAP Operations**: Full reconstruction pipeline timing
- **Frame Extraction**: Video processing and frame export timing
- **Debug Information**: Better visibility into operation progress

### Camera System Improvements
- Corrected coordinate system transformation from COLMAP to Blender
- More accurate camera positioning and orientation
- Better compatibility with Blender's camera system conventions

## 🙏 Acknowledgments

This release includes contributions and feedback from the community. Special thanks to users who provided feedback on camera orientation issues and documentation clarity.

## 📞 Support

For issues, feature requests, or contributions:
- **GitHub Issues**: [skysplat_blender/issues](https://github.com/kyjohnso/skysplat_blender/issues)
- **Documentation**: See the updated [README.md](README.md) for comprehensive usage instructions
- **Community**: Share your results and get help from other users

---

**Full Changelog**: [v0.3.0...v0.3.1](https://github.com/kyjohnso/skysplat_blender/compare/v0.3.0...v0.3.1)

Happy Splatting! 🎨