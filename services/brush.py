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


from dataclasses import dataclass, field


@dataclass
class BrushParams:
    """Parameters for a Brush training run.

    Mirrors the property set on SplatInstance — intentionally one big
    flat dataclass so callers don't have to know which Brush CLI flag
    each property maps to.
    """
    executable: str
    source_path: str
    export_path: str = ""
    export_name: str = "export_{iter}.ply"

    # Training options
    total_steps: int = 30000
    ssim_weight: float = 0.2
    lr_mean: float = 4e-5
    lr_mean_end: float = 4e-7
    lr_coeffs_dc: float = 3e-3
    lr_opac: float = 5e-2
    lr_scale: float = 5e-3
    lr_rotation: float = 1e-3

    # Dataset
    max_resolution: int = 1920
    subsample_frames: int = 1
    subsample_points: int = 1
    max_frames: int = 0           # 0 means omit
    eval_split_every: int = 0      # 0 means omit

    # Refine
    refine_every: int = 100
    growth_grad_threshold: float = 0.00015
    growth_select_fraction: float = 0.1
    growth_stop_iter: int = 12500
    max_splats: int = 10_000_000

    # Model
    sh_degree: int = 3

    # Process
    eval_every: int = 1000
    export_every: int = 5000
    seed: int = 42
    start_iter: int = 0

    # Flags
    with_viewer: bool = False
    eval_save_to_disk: bool = False


def build_command(params: BrushParams) -> list:
    """Build the Brush CLI invocation as an argv list."""
    cmd = [params.executable, params.source_path]
    cmd += [
        "--total-steps", str(params.total_steps),
        "--ssim-weight", str(params.ssim_weight),
        "--lr-mean", str(params.lr_mean),
        "--lr-mean-end", str(params.lr_mean_end),
        "--lr-coeffs-dc", str(params.lr_coeffs_dc),
        "--lr-opac", str(params.lr_opac),
        "--lr-scale", str(params.lr_scale),
        "--lr-rotation", str(params.lr_rotation),
        "--max-resolution", str(params.max_resolution),
        "--subsample-frames", str(params.subsample_frames),
        "--subsample-points", str(params.subsample_points),
        "--refine-every", str(params.refine_every),
        "--growth-grad-threshold", str(params.growth_grad_threshold),
        "--growth-select-fraction", str(params.growth_select_fraction),
        "--growth-stop-iter", str(params.growth_stop_iter),
        "--max-splats", str(params.max_splats),
        "--sh-degree", str(params.sh_degree),
        "--eval-every", str(params.eval_every),
        "--export-every", str(params.export_every),
        "--seed", str(params.seed),
    ]
    if params.max_frames > 0:
        cmd += ["--max-frames", str(params.max_frames)]
    if params.eval_split_every > 0:
        cmd += ["--eval-split-every", str(params.eval_split_every)]
    if params.start_iter > 0:
        cmd += ["--start-iter", str(params.start_iter)]
    if params.with_viewer:
        cmd.append("--with-viewer")
    if params.eval_save_to_disk:
        cmd.append("--eval-save-to-disk")
    if params.export_path:
        cmd += ["--export-path", params.export_path]
    if params.export_name != "export_{iter}.ply":
        cmd += ["--export-name", params.export_name]
    return cmd
