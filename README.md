<img src="images/skysplat_logo1.png" width="300" alt="Description">

# SkySplat: 3DGS Blender Toolkit

SkySplat is a Blender addon that simplifies the workflow for creating 3D Gaussian Splats from drone footage. It provides a comprehensive set of tools to streamline the process from video import to frame extraction, and loose integration of Blender with COLMAP and Arthur Brussee's rust based [Brush App](https://github.com/ArthurBrussee/brush) (pre-compiled binaries included).
![pumproom_7000_5](images/pumproom_7000_5.png)

## Features

- **Video Import & Management**
  - Load drone videos directly into Blender
  - Automatic detection and loading of SRT metadata files
  - Smart path management for project organization

  ![video_import](images/silo_video_import.png)

- **Automatic Frame Extraction**
  - Extract frames with customizable parameters (start, end, step)
  - Automatic output folder creation based on video filename
  - Optimized for aerial footage processing

  ![frame_extraction](images/silo_frame_capture.png)

- **COLMAP Integration**
  - A loose integration between COLMAP and Blender, arrange files and launch COLMAP
  - Path synchronization between video processing and reconstruction

  ![colmap_and_blender](images/silo_colmap_and_blender.png)

- **Gaussian Splatting Integration**
  - A loose integration of the [Brush App](https://github.com/ArthurBrussee/brush) for gaussian splatting training.
  - Configuration of gaussian-splatting training from Blender
  - Running of gaussian-splatting in a subprocess

  <!-- ![gaussian_splatting](images/silo_colmap_and_3dgs_6.png) -->
  ![puente_nuevo](images/puente_nuevo_bridge.png)

## Requirements

- Blender 4.0.0 or newer
- COLMAP (for reconstruction features)

**Note**: The [Brush App](https://github.com/ArthurBrussee/brush) for Gaussian Splatting is now bundled with the addon - no separate installation required!

## Installation

### 1. Download and Install SkySplat
1. Download the latest release zip file from [SkySplat Releases](https://github.com/kyjohnso/skysplat_blender/releases/latest)
   
   **OR**
   
   Download the latest development version via the GitHub Download ZIP link under the code button at [skysplat_blender](https://github.com/kyjohnso/skysplat_blender)

   <img src="images/download_zip.png" width="400" alt="Description">

2. Open Blender and navigate to Edit → Preferences → Add-ons
3. Click "Install..." and select the downloaded ZIP file
4. Enable the addon by checking the box next to "3D View: SkySplat: 3DGS Blender Toolkit"

### 2. Install COLMAP

[COLMAP](https://colmap.github.io/) is required for the Structure from Motion reconstruction features. Choose the installation method for your operating system:

#### macOS (Recommended: Homebrew)
```bash
brew install colmap
```
The executable will be installed to `/opt/homebrew/bin/colmap` (Apple Silicon) or `/usr/local/bin/colmap` (Intel).

#### Linux (Package Manager)
**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install colmap
```

**Fedora/RHEL:**
```bash
sudo dnf install colmap
```

**Arch Linux:**
```bash
sudo pacman -S colmap
```

The executable will typically be installed to `/usr/bin/colmap`.

#### Windows (Pre-compiled Binary)
1. Download the latest Windows release from [COLMAP GitHub Releases](https://github.com/colmap/colmap/releases)
2. Extract the ZIP file to a location like `C:\Program Files\COLMAP\`
3. The executable will be at `C:\Program Files\COLMAP\bin\colmap.exe`
4. Optionally, add the `bin` directory to your system PATH for easier access

**Note:** For SkySplat to work properly, you'll need to know the path to the COLMAP executable. The addon will attempt to auto-detect common installation paths, but you can manually specify the path in the COLMAP panel if needed.

### 3. Install Brush app

The brush app from [brush app](https://github.com/ArthurBrussee/brush#) is needed for the 3DGS training of the scene. The brush binaries for all mac/linux/windows are included with this addon, however, when Blender installs an addon via a zip file, it changes the permissions on the extracted files (this is for everyone's benefit), and these cannot be executed by default. 

You have 3 options for running brush from this addon:

#### Option 1: Fix Permissions on Bundled Binaries (Recommended)

After installing the SkySplat addon, you'll need to make the bundled brush binaries executable:

**macOS/Linux:**
1. Open Terminal
2. Navigate to your Blender addons directory:
   - **macOS**: `~/Library/Application Support/Blender/4.0/scripts/addons/skysplat_blender/binaries/`
   - **Linux**: `~/.config/blender/4.0/scripts/addons/skysplat_blender/binaries/`
3. Make the binary executable:
   ```bash
   # For macOS
   chmod +x brush_app_mac
   
   # For Linux
   chmod +x brush_app_linux
   ```

**Windows:**
Windows executables should work without permission changes, but if you encounter issues, right-click on [`brush_app_windows.exe`](binaries/brush_app_windows.exe) → Properties → Security → and ensure your user has "Full control" permissions.

#### Option 2: Download Pre-compiled Binaries

If you prefer to download the binaries separately, you can get them directly from the Brush repository releases:

1. **Windows**: Download [`brush_app_windows.exe`](https://github.com/ArthurBrussee/brush/releases/latest) from Brush Releases
2. **macOS**: Download [`brush_app_macos`](https://github.com/ArthurBrussee/brush/releases/latest) from Brush Releases
3. **Linux**: Download [`brush_app_linux`](https://github.com/ArthurBrussee/brush/releases/latest) from Brush Releases

You can also get the compiled binaries in the skysplat_blender repo
1. **Windows**: [`brush_app_windows.exe`](https://github.com/kyjohnso/skysplat_blender/blob/main/binaries/brush_app_windows.exe)
2. **macOS (Apple silicon)**: [`brush_app_mac`](https://github.com/kyjohnso/skysplat_blender/blob/main/binaries/brush_app_mac)
3. **linux**: [`brush_app_linux`](https://github.com/kyjohnso/skysplat_blender/blob/main/binaries/brush_app_linux)

**Important**: You will need to know the full path to where you downloaded these binaries, as you'll need to specify this path in the SkySplat 3DGS panel's "Brush Executable" field.

#### Option 3: Clone and Build Brush from Source

For the most up-to-date version or if you want to modify the source code:

1. **Install Rust** (if not already installed):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source ~/.cargo/env
   ```

2. **Clone and build Brush**:
   ```bash
   git clone https://github.com/ArthurBrussee/brush.git
   cd brush
   cargo build --release
   ```

3. **Locate the executable**:
   - **Windows**: `target/release/brush_app.exe`
   - **macOS/Linux**: `target/release/brush_app`

**Important**: You will need to know the full path to the compiled executable (e.g., `/home/username/brush/target/release/brush_app`) as you'll need to specify this path in the SkySplat 3DGS panel's "Brush Executable" field.

**Note**: The SkySplat addon will automatically attempt to detect the bundled binaries first, then fall back to common build locations like `~/projects/brush/target/release/brush_app`. If none are found, you can manually specify the path in the 3DGS panel.

---
## Example Workflow Run Through

1. **Accessing the Toolkit**
   - Open the sidebar in the 3D View (press N)
   - Select the "SkySplat" tab

2. **Loading Drone Footage**
   - You can download the example video used in this walkthrough at [windsor_silo](https://skysplat.net/DJI_20250731122012_0009_D_windsor_silo_new_small.mp4) (right click and save as) (This is a new video of the silo that tends to work better in COLMAP)
   - Select your video file in the "Video File" field in the 3D Viewport
   - If available, the SRT metadata file will be detected automatically
   - Click "Load Video and SRT" to import into the Video Sequencer

<img src="images/video_loader_panel.png" width="400" alt="Description">

3. **Extracting Frames**
   - Set your desired frame range and step value, Version 0.3.0 of SkySplat will automatically select the frame step value to get the total number of extracted frames to about 170. Smaller step size means more frames and better reconstruction, but also longer processing times.
   - Confirm or modify the output folder
   - Click "Extract Frames" to process

4. **COLMAP Workflow**
   - Configure COLMAP settings in the SkySplat COLMAP panel
   - COLMAP Executable should auto populate with your systems default path, however you can manually set it if needed (on MacOS this path will be /opt/homebrew/bin/colmap if you used the homebrew as the install method as described above)
   - If the input and output paths for the models aren't loaded, you can click the chain link icon to auto populate them from the video file path and defaults.
   - The defaults for the other settings should be sufficient for your first few runs. 
   - Click "Run COLMAP" to begin processing your video frames into a sparse point cloud (you can monitor the console running blender for detailed colmap output)

<img src="images/colmap_panel.png" width="400" alt="Description">

5. **COLMAP Model Transformation**
   This step was the main reason I came up with this workflow. COLMAP will default the coordinate frame to the frame of the initial camera pose. This means that for many gaussian splatting drone videos, it is slightly tilted down and at the first camera origin, rather than being at a natural center of the scene. The colmap transformation panel lets you load the COLMAP output model, scale, rotate, and translate the parent object in blender to a more natural scale, position, and orientation, and then export the model before gaussian splatting training.

   <img src="images/colmap_transformation_panel.png" width="400" alt="Description">


   - Click "Load COLMAP Model" after running COLMAP and it will load the output COLMAP model into blender. You can also go straight to this step in Blender if you already processed your images outside of SkySplat.

   ![loaded COLMAP model](images/rotate_and_scale_colmap_1.png)

   - If the loaded COLMAP model looks sparse with few points or few cameras, try running frame extraction again with a smaller step size.

   - To transform this model, make sure you transform the parent "COLMAP_Root" empty object, not individual cameras or points. 

   ![rotate and scale colmap 0](images/rotate_and_scale_colmap_0.png)

   - For the example silo video, I rotated it so the natural ground was in the X-Y plane, and the origin was at the base of the silo. You can also use a google maps or OSM image with a scale so that you can right size the COLMAP and hence 3DGS models. I have included a screen shot of a map from this silo video at [silo reference map](https://skysplat.net/google_earth_reference_silo.png)

   ![silo reference map](https://skysplat.net/google_earth_reference_silo.png)

   This is one of the highlights of working with COLMAP and 3DGS in Blender, the ability to include other 3D assets, models, and features in a cohesive 3d environment.

   ![rotate and scale colmap 2](images/rotate_and_scale_colmap_2.png)

   Now I can export the model scaled and rotated into a more natural coordinate system, and the 3DGS code will start with these parameters when it fits the gaussians. 

   <img src="(images/colmap_transformation_panel.png" width="400" alt="Description">

    - Click "Export COLMAP Model" after you have finished transforming and adjusting your model, this will export a new model in the <colmap output directory>/transformed/ directory.

    - Click "Prepare Brush Dataset" to prepare a dataset for training with the Gaussian Splatting Brush. This will arrange your COLMAP model and images into a directory that brush can import.
   

6. **Brush Training (3D Gaussian Splatting)**

<img src="images/3dgs_brush_app_panel.png" width="400" alt="Description">

   - Configure Brush settings in the SkySplat 3DGS panel (as shown in the image below)
   - The Brush Executable path will auto-populate with the bundled binary for your platform (Windows, macOS, or Linux)
   - Use the chain link icon next to the Source Path to automatically sync with your COLMAP output
   - The Source Path should point to your transformed COLMAP model or prepared brush dataset
   - Set your Export Path where the trained .ply files will be saved
   - Configure training parameters:
     - **Total Steps**: Number of training iterations (default: 30000)
     - **Max Resolution**: Maximum image resolution for training (default: 1920)
     - **With Viewer**: Enable this to pop up the interactive viewer application that shows real-time training progress
   - If you want to watch the brush app training live you can click the "viewer" button. This will run brush with the UI and show the 3DGS model as it is trained.
   - Advanced options are available by expanding the "Show Advanced Options" section for fine-tuning learning rates, refinement parameters, and dataset options
   - Click "Run Brush Training" to start the process
   - Unlike the original Gaussian Splatting implementation, Brush runs as a subprocess so it won't block the Blender UI
   - Monitor progress in the Blender console, or if you enabled "With Viewer", watch the training progress in the dedicated viewer window
   - The training process will automatically export .ply files at specified intervals to your Export Path

![brush training 1](images/brush_training_1.png)


7. **3DGS Loading**
   There is already a rich Blender addon ecosystem for loading 3D gaussian splats into Blender. I recommend [KIRI Innovation's 3DGS Render Addon](https://github.com/Kiri-Innovation/3dgs-render-blender-addon) and you can see it in my Blender screen shots above if you look closely. I recommend loading the ply file without transforming from COLMAP to Blender coordinates mainly because we already did a transformation and scaling in the previous step. If everything worked you will now have your transformed COLMAP model, any helper "reference silos" you created in blender, and the 3D Gaussian Splat ready to create whatever awesome render or animation you are working on. 

![silo_colmap_and_3dgs_1](images/3dgs_model_loaded_1.png)
![silo_colmap_and_3dgs_2](images/3dgs_model_loaded_2.png)
![silo_colmap_and_3dgs_3](images/3dgs_model_loaded_3.png)
![silo_colmap_and_3dgs_4](images/3dgs_model_loaded_4.png)
![silo_colmap_and_3dgs_5](images/3dgs_model_loaded_5.png)

## Contributing

The best thing someone can do is try this workflow with their own drone videos and please tell me about your experience. This is the very first iteration of this and I know with an engaged open source community we can create some amazing splats, renders, experiences and art.

![school5.png](images/school5.png)

I did this development on Linux and while I tried (or more acurately Claude tried) to make sure it is platform agnostic, I would love if people wanted to try this out on Windows or MacOS and could provide feedback or contribute to the project. 

I also have many comments above to the effect of *"future versions will include..."*, and *"I still need to work on..."* etc.

If you have any ideas for further features, or bug reports, or want to help work on documentation, please feel free to fork the code and send a pull request or reach out.

## License

SkySplat_blender is licensed under the MIT License. A single file was forked from [COLMAP](https://colmap.github.io/) (utils/read_write_model.py) and it retains the original copyright. 

Brush is built separately and no code is included in SkySplat. Also, it is licensed under Apache v2, and this license should be adhered to.

None of the code from [Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting) is included in this repo, however, if you use it all of its copyright and license conditions should be adhered to.


## Future Work

1. ✅ ~~Package the brush app with the blender addon~~ **COMPLETED!** - Brush binaries are now bundled for all platforms
2. Integration of SRT metadata for improved COLMAP initialization
3. Enhanced UI for batch processing multiple videos
4. Direct integration with more 3D Gaussian Splatting viewers

![pumproom_brush_5000](images/pumproom_brush_50000.png)

## Acknowledgments

Without these open source (or source available in one case) projects, I would have nothing in this project. If you find this workflow useful, please consider giving these projects a star or following them on GitHub to stay updated with their development.


- [Blender](https://www.blender.org/)
- [COLMAP](https://colmap.github.io/)
- [Brush App](https://github.com/ArthurBrussee/brush) - Current preferred implementation for 3dgs
- [Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting) - Original source for performing Gaussian Splatting
- [RedShot AI Tutorial](https://www.reshot.ai/3d-gaussian-splatting) - I used this tutorial extensively as I was working my way through my first gaussian splats
- [KIRI Innovation's 3DGS Render Addon](https://github.com/Kiri-Innovation/3dgs-render-blender-addon)

Happy Splatting!🎨

Kyjohnso

![lighthouse_rendered1.png](images/lighthouse_rendered1.png)

### Legacy - Install GraphDeco-INRIA's [gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) python package

The original SkySplat addon used the GraphDeco-INRIA's gaussian-splatting software. These install instructions are provided for completeness.

   1. clone the repository
   ```
   git clone git@github.com:graphdeco-inria/gaussian-splatting.git --recursive
   cd gaussian-splatting
   ```
   2. Virtual Environment - I highly recommend installing the gaussian-splatting software in a virtual environment to avoid conflicts with other python packages you may have installed. Here is how you would create and activate a virtual environment in bash:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
### 3. Install the python dependencies
   ```
   pip install plyfile tqdm
   ````
   The submodules in the gaussian splatting repository depend on torch. You can install torch a variety of ways, but I find it most continent to install it via pip, just like the other dependencies. We will give pip a index url that is for your specific CUDA version (in this example I am installing 12.6). You can find your specific CUDA version by running;
   ```
   nvcc --version
   ```
   Then install torch via pip;
   ```
   pip install torch --index-url https://download.pytorch.org/whl/cu126
   ```

   At this point, I find it useful to verify that the installed torch version is compatible with your CUDA version and GPU. You can run the following commands in a python interpreter or put them in a file and run it.

   ```
   #!/usr/bin/env python3.11
   verify_cuda_torch.py

   import torch

   if torch.cuda.is_available():
      print("CUDA is available! You have", torch.cuda.device_count(), "GPU(s).")
      print("Device name:", torch.cuda.get_device_name(0))
   else:
      print("CUDA is not available. Check your installation.")
   ```
   
   Note: I have occasionally had problems with creating a venv, activating it, and then the python command pointing to a different version of python. Depending on your version of python and how you setup your environment, you may need to adjust how you call this file that you just created. For instance, I called the above file with the command:
   ```
   python3.11 verify_cuda_torch.py
   ```
   If you encounter issues, try creating a new venv and reinstalling torch there.

   Now you should be able to install the gaussian-splatting dependencies:
   ```
   pip install submodules/diff-gaussian-rasterization
   pip install submodules/simple-knn
   ```
   Make note of where you cloned the code to and where the virtual environment directory is located, these will be needed in blender to call the gaussian-splatting software