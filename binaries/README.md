# Bundled Binaries Directory

This directory contains pre-compiled Brush app binaries for different platforms, eliminating the need for users to install Rust and compile the code themselves.

## Binary Files

The following files should be placed in this directory:

- `brush_app_windows.exe` - Windows executable
- `brush_app_macos` - macOS executable  
- `brush_app_linux` - Linux executable

## Compiling Binaries

To compile new binaries when updating the Brush version:

### 1. Clone the Brush Repository
```bash
git clone https://github.com/ArthurBrussee/brush.git
cd brush
```

### 2. Compile for Each Platform

**Linux:**
```bash
cargo build --release
cp target/release/brush_app ../skysplat_blender/binaries/brush_app_linux
```

**Windows (cross-compile from Linux):**
```bash
rustup target add x86_64-pc-windows-gnu
cargo build --release --target x86_64-pc-windows-gnu
cp target/x86_64-pc-windows-gnu/release/brush_app.exe ../skysplat_blender/binaries/brush_app_windows.exe
```

**macOS (cross-compile from Linux):**
```bash
rustup target add x86_64-apple-darwin
cargo build --release --target x86_64-apple-darwin
cp target/x86_64-apple-darwin/release/brush_app ../skysplat_blender/binaries/brush_app_macos
```

Note: Cross-compilation may require additional setup. It's recommended to compile on native platforms when possible.

### 3. Version Tracking

When updating binaries, document the Brush version:

1. Check the current Brush version:
   ```bash
   git describe --tags --abbrev=0
   ```

2. Update the version information in `config.py` if needed:
   ```python
   # In config.py, update if there's a version constant
   BRUSH_VERSION = "v1.x.x"  # Update this
   ```

3. Commit the new binaries with a descriptive message:
   ```bash
   git add binaries/
   git commit -m "Update Brush binaries to version v1.x.x"
   ```

## File Permissions

Ensure the executables have proper permissions:
```bash
chmod +x brush_app_linux
chmod +x brush_app_macos
```

## Release Process

After updating binaries:

1. Test the addon with the new binaries on each platform
2. Update the SkySplat version in `config.py` if this is a major update
3. Create a new release tag
4. The GitHub Actions will automatically include the binaries in the release zip

## Testing

After updating binaries, test the addon on each platform to ensure:
1. The bundled binary is detected correctly by the [`get_default_brush_path()`](../ui/gaussian_splatting_panel.py) function
2. The binary runs without errors when executing `brush_app --help`
3. A complete training workflow runs successfully
4. The addon falls back correctly to user-compiled binaries if they exist

## Troubleshooting

**Binary not detected:**
- Check file permissions (executable bit)
- Verify the binary name matches `BUNDLED_BINARY_NAMES` in `config.py`
- Ensure the binary is in the correct directory

**Binary fails to run:**
- Test the binary directly from command line
- Check for missing dependencies (especially on Linux)
- Verify the binary was compiled for the correct architecture

**Path issues:**
- The bundled binary path is: `<addon_dir>/binaries/brush_app_<platform>`
- User-compiled fallback path is: `~/projects/brush/target/release/brush_app[.exe]`