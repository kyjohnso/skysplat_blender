"""COLMAP service.

Pure parts (this stage): read_model, write_model, ColmapModel dataclass.
Subprocess parts (Stage B): run_reconstruction, merge_models.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from utils.read_write_model import (
    read_model as _rw_read_model,
    write_model as _rw_write_model,
)

from .errors import ColmapError


@dataclass
class ColmapModel:
    """In-memory COLMAP sparse model."""
    cameras: dict
    images: dict
    points3D: dict


def read_model(model_path: Path) -> ColmapModel:
    """Read a COLMAP sparse model from disk.

    model_path can point to a directory containing cameras.{bin,txt},
    images.{bin,txt}, points3D.{bin,txt}. Format auto-detected.
    """
    model_path = Path(model_path)
    if not model_path.exists():
        raise ColmapError(f"Model path does not exist: {model_path}")
    try:
        cameras, images, points3D = _rw_read_model(str(model_path))
    except Exception as exc:
        raise ColmapError(f"Failed to read model from {model_path}: {exc}") from exc
    return ColmapModel(cameras=cameras, images=images, points3D=points3D)


def write_model(model: ColmapModel, output_path: Path, *, ext: str = ".txt") -> None:
    """Write a ColmapModel to disk.

    ext is '.txt' or '.bin' — determines which format to use.
    output_path will be created if missing.
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    try:
        _rw_write_model(
            model.cameras, model.images, model.points3D,
            str(output_path), ext,
        )
    except Exception as exc:
        raise ColmapError(f"Failed to write model to {output_path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Camera model discriminated union
# ---------------------------------------------------------------------------

@dataclass
class CameraModelSpec:
    pass


@dataclass
class Auto(CameraModelSpec):
    """COLMAP estimates intrinsics from EXIF (stills only)."""


@dataclass
class FromSRT(CameraModelSpec):
    srt_path: Path


@dataclass
class Manual(CameraModelSpec):
    model: str  # "SIMPLE_PINHOLE", "OPENCV", etc.
    params: list


@dataclass
class Inherit(CameraModelSpec):
    """Frame Extract default — inherit from upstream Video's SRT or fall back."""


# ---------------------------------------------------------------------------
# Reconstruction inputs / outputs
# ---------------------------------------------------------------------------

@dataclass
class FramesSource:
    path: Path
    source_id: str
    camera_model: CameraModelSpec


@dataclass
class ColmapParams:
    mode: Literal["joint", "merge_after"] = "joint"
    matching: Literal["sequential", "exhaustive"] = "exhaustive"
    use_gpu: bool = True
    colmap_executable: str = "colmap"


@dataclass
class ColmapResult:
    model_dir: Path
    source_map: dict
    image_root: Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_reconstruction(
    sources: list[FramesSource],
    workspace_dir: Path,
    params: ColmapParams,
    log_path: Path,
) -> ColmapResult:
    """Run COLMAP feature extraction + matching + bundle adjustment.

    Phase 1 supports single-source reconstruction (matches existing
    operator behavior). Multi-source 'joint' and 'merge_after' modes
    are stubs that work only when len(sources) == 1; the multi-source
    paths get fleshed out in phase 2 when node graphs can produce them.
    """
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if len(sources) == 0:
        raise ColmapError("run_reconstruction requires at least one source")

    if len(sources) > 1:
        # Multi-source path is left for phase 2; reject explicitly to avoid
        # silent single-source-only behavior.
        raise ColmapError(
            "Multi-source reconstruction (joint or merge_after) is not yet "
            "implemented in services.colmap. Use a single source for now."
        )

    source = sources[0]
    image_path = source.path
    source_map = {
        p: source.source_id
        for p in Path(image_path).iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    }

    if len(source_map) < 3:
        raise ColmapError(f"Need at least 3 images, found {len(source_map)} in {image_path}")

    distorted = workspace_dir / "distorted"
    sparse = distorted / "sparse"
    sparse.mkdir(parents=True, exist_ok=True)
    db = distorted / "database.db"

    camera_model = _camera_model_arg(source.camera_model)
    use_gpu_val = "1" if params.use_gpu else "0"

    # Capture all subprocess output to log.
    with open(log_path, "w") as log:
        # 1. Feature extraction
        _run_colmap_step(
            log, params.colmap_executable, "feature_extractor",
            "--database_path", str(db),
            "--image_path", str(image_path),
            "--ImageReader.single_camera", "1",
            "--ImageReader.camera_model", camera_model,
            "--SiftExtraction.use_gpu", use_gpu_val,
        )

        # 2. Matching
        matcher = "exhaustive_matcher" if params.matching == "exhaustive" else "sequential_matcher"
        _run_colmap_step(
            log, params.colmap_executable, matcher,
            "--database_path", str(db),
            "--SiftMatching.use_gpu", use_gpu_val,
        )

        # 3. Bundle adjustment (mapper)
        _run_colmap_step(
            log, params.colmap_executable, "mapper",
            "--database_path", str(db),
            "--image_path", str(image_path),
            "--output_path", str(sparse),
            "--Mapper.ba_global_function_tolerance=0.000001",
        )

        # 4. Image undistorter
        _run_colmap_step(
            log, params.colmap_executable, "image_undistorter",
            "--image_path", str(image_path),
            "--input_path", str(sparse / "0"),
            "--output_path", str(workspace_dir),
            "--output_type", "COLMAP",
        )

    # Move undistorter output files into sparse/0 layout.
    _normalize_sparse_layout(workspace_dir)

    final_sparse = workspace_dir / "sparse" / "0"
    _ = _read_resulting_model(final_sparse)

    return ColmapResult(
        model_dir=final_sparse,
        source_map=source_map,
        image_root=image_path,
    )


def merge_models(model_a: Path, model_b: Path, output_dir: Path, log_path: Path) -> Path:
    """Run `colmap model_merger` to fuse two sparse models."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_path)
    with open(log_path, "w") as log:
        _run_colmap_step(
            log, "colmap", "model_merger",
            "--input_path1", str(model_a),
            "--input_path2", str(model_b),
            "--output_path", str(output_dir),
        )
    return output_dir


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _run_colmap_step(log_file, executable: str, subcommand: str, *args: str):
    cmd = [executable, subcommand, *args]
    log_file.write(f"\n+ {' '.join(cmd)}\n")
    log_file.flush()
    result = subprocess.run(
        cmd, stdout=log_file, stderr=subprocess.STDOUT, check=False,
    )
    if result.returncode != 0:
        raise ColmapError(
            f"colmap {subcommand} failed with code {result.returncode}. "
            f"See log: {log_file.name}"
        )


def _camera_model_arg(spec: CameraModelSpec) -> str:
    """Map a CameraModelSpec to a COLMAP camera-model string for feature_extractor."""
    if isinstance(spec, Manual):
        return spec.model
    if isinstance(spec, (Auto, FromSRT, Inherit)):
        return "SIMPLE_PINHOLE"
    return "SIMPLE_PINHOLE"


def _normalize_sparse_layout(workspace_dir: Path):
    """After image_undistorter, files end up in workspace/sparse/ (not /0).
    Move them into workspace/sparse/0/ to match Brush's expectation.
    """
    sparse = workspace_dir / "sparse"
    if not sparse.exists():
        return
    target = sparse / "0"
    target.mkdir(exist_ok=True)
    for entry in sparse.iterdir():
        if entry.is_file():
            shutil.move(str(entry), str(target / entry.name))


def _read_resulting_model(model_dir: Path) -> ColmapModel:
    """Indirection so tests can mock model reading."""
    return read_model(model_dir)
