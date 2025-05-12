<img src="images/skysplat_logo1.png" width="300" alt="Description">

# SkySplat: 3DGS Blender Toolkit

SkySplat is a powerful Blender addon that simplifies the workflow for creating 3D Gaussian Splats from drone footage. It provides a comprehensive set of tools to streamline the process from video import to frame extraction and COLMAP integration.

## Features

- **Video Import & Management**
  - Load drone videos directly into Blender
  - Automatic detection and loading of SRT metadata files
  - Smart path management for project organization

- **Intelligent Frame Extraction**
  - Extract frames with customizable parameters (start, end, step)
  - Automatic output folder creation based on video filename
  - Optimized for aerial footage processing

- **COLMAP Integration**
  - Seamless workflow between Blender and COLMAP
  - Path synchronization between video processing and reconstruction
  - Streamlined photogrammetry process

## Installation

1. Download the latest release from code button (see below)

<img src="images/download_zip.png" width="400" alt="Description">

3. Open Blender and navigate to Edit → Preferences → Add-ons
4. Click "Install..." and select the downloaded ZIP file
5. Enable the addon by checking the box next to "3D View: SkySplat: 3DGS Blender Toolkit"

## Requirements

- Blender 4.0.0 or newer
- COLMAP (for reconstruction features)
- [Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting)

## Usage

<img src="images/skysplat_pannel.png" width="400" alt="Description">

1. **Accessing the Toolkit**
   - Open the sidebar in the 3D View (press N)
   - Select the "SkySplat" tab

2. **Loading Drone Footage**
   - Select your video file in the "Video File" field
   - If available, the SRT metadata file will be detected automatically
   - Click "Load Video and SRT" to import into the Video Sequencer

3. **Extracting Frames**
   - Set your desired frame range and step value
   - Confirm or modify the output folder
   - Click "Extract Frames" to process

4. **COLMAP Workflow**
   - Configure COLMAP settings in the dedicated panel
   - Process extracted frames through the integrated COLMAP workflow

## Workflow

SkySplat is designed to simplify the journey from drone video to 3D Gaussian Splats:

1. Import drone footage with GPS data
2. Extract optimal frames for reconstruction
3. Process through COLMAP integration
4. Generate 3D Gaussian Splats
5. Visualize and refine in Blender

## Contributing

Contributions are welcome! If you'd like to improve SkySplat:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License

## Acknowledgments

- [Blender](https://www.blender.org/)
- [COLMAP](https://colmap.github.io/)
- [Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting)
- [RedShot AI Tutorial](https://www.reshot.ai/3d-gaussian-splatting)