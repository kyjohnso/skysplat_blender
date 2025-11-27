#!/bin/bash

# Script to build release zip files for skysplat_blender
# Usage: ./build_release_zipfiles.sh <version>

set -e

# Check if version parameter is provided
if [ -z "$1" ]; then
    echo "Error: Version parameter is required"
    echo "Usage: ./build_release_zipfiles.sh <version>"
    echo "Example: ./build_release_zipfiles.sh 0.3.1"
    exit 1
fi

VERSION=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_DIR="${SCRIPT_DIR}/releases"
TEMP_DIR="${RELEASE_DIR}/temp_build"

# Create releases directory if it doesn't exist
mkdir -p "${RELEASE_DIR}"

echo "Building release zip files for version ${VERSION}..."

# Common files to include in all releases (excluding binaries and images)
COMMON_FILES=(
    "__init__.py"
    ".gitattributes"
    ".gitignore"
    "config.py"
    "LICENSE"
    "README.md"
    "requirements.txt"
    ".claude"
    ".github"
    "docs"
    "operators"
    "ui"
    "utils"
    "website"
)

# Function to create base zip without binaries and images
create_base_zip() {
    local zip_name="skysplat_blender_${VERSION}.zip"
    local zip_path="${RELEASE_DIR}/${zip_name}"
    local build_dir="${TEMP_DIR}/skysplat_blender"
    
    echo "Creating ${zip_name}..."
    
    # Remove existing zip and temp directory if they exist
    rm -f "${zip_path}"
    rm -rf "${build_dir}"
    mkdir -p "${build_dir}"
    
    # Copy common files to temp directory
    cd "${SCRIPT_DIR}"
    for item in "${COMMON_FILES[@]}"; do
        if [ -e "${item}" ]; then
            cp -r "${item}" "${build_dir}/"
        fi
    done
    
    # Create zip from temp directory
    cd "${TEMP_DIR}"
    zip -r "${zip_path}" "skysplat_blender" \
        -x "*.pyc" \
        -x "*__pycache__*" \
        -x "*.DS_Store" \
        -x "*/.git/*"
    
    # Clean up temp directory
    rm -rf "${build_dir}"
    
    echo "✓ Created ${zip_name}"
}

# Function to create platform-specific zip
create_platform_zip() {
    local platform=$1
    local binary_file=$2
    local zip_name="skysplat_blender_${platform}_${VERSION}.zip"
    local zip_path="${RELEASE_DIR}/${zip_name}"
    local build_dir="${TEMP_DIR}/skysplat_blender"
    
    echo "Creating ${zip_name}..."
    
    # Remove existing zip and temp directory if they exist
    rm -f "${zip_path}"
    rm -rf "${build_dir}"
    mkdir -p "${build_dir}/binaries"
    
    # Copy common files to temp directory
    cd "${SCRIPT_DIR}"
    for item in "${COMMON_FILES[@]}"; do
        if [ -e "${item}" ]; then
            cp -r "${item}" "${build_dir}/"
        fi
    done
    
    # Copy the platform-specific binary
    if [ -f "binaries/${binary_file}" ]; then
        cp "binaries/${binary_file}" "${build_dir}/binaries/"
        echo "  Added binary: binaries/${binary_file}"
    else
        echo "  Warning: Binary not found: binaries/${binary_file}"
    fi
    
    # Copy binaries README and .gitkeep
    if [ -f "binaries/README.md" ]; then
        cp "binaries/README.md" "${build_dir}/binaries/"
    fi
    if [ -f "binaries/.gitkeep" ]; then
        cp "binaries/.gitkeep" "${build_dir}/binaries/"
    fi
    
    # Create zip from temp directory
    cd "${TEMP_DIR}"
    zip -r "${zip_path}" "skysplat_blender" \
        -x "*.pyc" \
        -x "*__pycache__*" \
        -x "*.DS_Store" \
        -x "*/.git/*"
    
    # Clean up temp directory
    rm -rf "${build_dir}"
    
    echo "✓ Created ${zip_name}"
}

# Create all zip files
create_base_zip
create_platform_zip "win" "brush_app_windows.exe"
create_platform_zip "linux" "brush_app_linux"
create_platform_zip "mac" "brush_app_mac"

# Clean up temp directory
rm -rf "${TEMP_DIR}"

echo ""
echo "All release zip files created successfully in ${RELEASE_DIR}:"
ls -lh "${RELEASE_DIR}"/*_${VERSION}.zip

echo ""
echo "Done!"