"""Brush dataset preparation and training subprocess management.

Pure parts (this stage): prepare_dataset, build_command.
Subprocess (Stage C): run_training.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .errors import BrushError

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_SPARSE_BIN_FILES = ("cameras.bin", "images.bin", "points3D.bin")
_SPARSE_TXT_FILES = ("cameras.txt", "images.txt", "points3D.txt")


def prepare_dataset(
    sparse_model_dir: Path,
    image_dir: Path,
    output_dir: Path,
    *,
    force_copy: bool = False,
) -> Path:
    """Build a Brush-compatible dataset directory.

    Layout produced:
      output_dir/
        sparse/0/cameras.bin (or .txt fallback)
        sparse/0/images.bin
        sparse/0/points3D.bin
        images/  (symlink to image_dir on Unix; copy on Windows or force_copy=True)

    Returns output_dir on success. Raises BrushError on missing inputs.
    """
    sparse_model_dir = Path(sparse_model_dir)
    image_dir = Path(image_dir)
    output_dir = Path(output_dir)

    if not sparse_model_dir.exists():
        raise BrushError(f"Sparse model directory does not exist: {sparse_model_dir}")
    if not image_dir.exists():
        raise BrushError(f"Image directory does not exist: {image_dir}")

    target_sparse = output_dir / "sparse" / "0"
    target_sparse.mkdir(parents=True, exist_ok=True)

    # Copy the sparse model — prefer .bin, fall back to .txt for any missing files.
    copied_any = False
    for bin_name, txt_name in zip(_SPARSE_BIN_FILES, _SPARSE_TXT_FILES):
        bin_src = sparse_model_dir / bin_name
        txt_src = sparse_model_dir / txt_name
        if bin_src.exists():
            shutil.copy2(bin_src, target_sparse / bin_name)
            copied_any = True
        elif txt_src.exists():
            shutil.copy2(txt_src, target_sparse / txt_name)
            copied_any = True
    if not copied_any:
        raise BrushError(
            f"No sparse model files found in {sparse_model_dir} "
            f"(expected one of {_SPARSE_BIN_FILES + _SPARSE_TXT_FILES})"
        )

    target_images = output_dir / "images"
    _link_or_copy_images(image_dir, target_images, force_copy=force_copy)

    return output_dir


def _link_or_copy_images(src: Path, dst: Path, *, force_copy: bool):
    use_symlink = platform.system() != "Windows" and not force_copy
    if dst.is_symlink():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)

    if use_symlink:
        try:
            os.symlink(src.resolve(), dst)
            return
        except OSError:
            pass  # fall through to copy

    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.is_file() and entry.suffix.lower() in _IMAGE_EXTENSIONS:
            shutil.copy2(entry, dst / entry.name)
