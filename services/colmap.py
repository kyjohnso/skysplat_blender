"""COLMAP service.

Pure parts (this stage): read_model, write_model, ColmapModel dataclass.
Subprocess parts (Stage B): run_reconstruction, merge_models.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Cache for COLMAP options to avoid repeated subprocess calls
_colmap_options_cache: dict = {}

# Dual-import: relative works when loaded as a Blender addon
# (services is a sub-package of skysplat_blender), absolute works when
# pytest puts the addon root on sys.path so `utils` is top-level.
try:
    from ..utils.read_write_model import (
        read_model as _rw_read_model,
        write_model as _rw_write_model,
    )
except ImportError:
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
# GPU flag detection
# ---------------------------------------------------------------------------

def get_colmap_version_and_options(colmap_path: str) -> dict:
    """Detect COLMAP option syntax by parsing help output.

    Uses dynamic detection instead of hard-coded version checks for better
    forward compatibility with future COLMAP versions.

    Returns a dict with keys:
        feature_gpu_option  – e.g. 'FeatureExtraction.use_gpu' or 'SiftExtraction.use_gpu'
        matching_gpu_option – e.g. 'FeatureMatching.use_gpu' or 'SiftMatching.use_gpu'
        version             – version string from colmap help, or 'unknown'
    """
    global _colmap_options_cache

    cache_key = colmap_path or "colmap"
    if cache_key in _colmap_options_cache:
        return _colmap_options_cache[cache_key]

    colmap_command = f'"{colmap_path}"' if colmap_path else "colmap"

    feature_gpu_option = None
    matching_gpu_option = None
    version_string = "unknown"

    def _get_help_output(cmd: str) -> str:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10,
            )
            combined = (result.stdout or "") + (result.stderr or "")
            return combined if result.returncode == 0 else ""
        except Exception as exc:
            logger.debug(f"Command '{cmd}' failed: {exc}")
            return ""

    help_output = _get_help_output(f"{colmap_command} help")
    if help_output:
        m = re.search(r'COLMAP\s+([\d.]+\S*)', help_output)
        if m:
            version_string = m.group(1)

    feature_help = _get_help_output(f"{colmap_command} feature_extractor --help")
    if feature_help:
        if '--FeatureExtraction.use_gpu' in feature_help:
            feature_gpu_option = 'FeatureExtraction.use_gpu'
        elif '--SiftExtraction.use_gpu' in feature_help:
            feature_gpu_option = 'SiftExtraction.use_gpu'

    matcher_help = _get_help_output(f"{colmap_command} sequential_matcher --help")
    if matcher_help:
        if '--FeatureMatching.use_gpu' in matcher_help:
            matching_gpu_option = 'FeatureMatching.use_gpu'
        elif '--SiftMatching.use_gpu' in matcher_help:
            matching_gpu_option = 'SiftMatching.use_gpu'

    if feature_gpu_option is None:
        logger.warning("Could not detect feature GPU option, using 'SiftExtraction.use_gpu' as default")
        feature_gpu_option = 'SiftExtraction.use_gpu'

    if matching_gpu_option is None:
        logger.warning("Could not detect matching GPU option, using 'SiftMatching.use_gpu' as default")
        matching_gpu_option = 'SiftMatching.use_gpu'

    options = {
        'feature_gpu_option': feature_gpu_option,
        'matching_gpu_option': matching_gpu_option,
        'version': version_string,
    }
    logger.info(
        f"Detected COLMAP {version_string}: "
        f"feature GPU option = {feature_gpu_option}, "
        f"matching GPU option = {matching_gpu_option}"
    )
    _colmap_options_cache[cache_key] = options
    return options


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_reconstruction(
    sources: list[FramesSource],
    workspace_dir: Path,
    params: ColmapParams,
    log_path: Path,
    register_proc=None,
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
        # Multiple videos are merged upstream (Merge Frames node) into one
        # source dir with per-video subfolders, so we still receive a single
        # source here. The list form (joint/merge_after over separate sources)
        # is not used by the node graph.
        raise ColmapError(
            "run_reconstruction takes a single source. For multiple videos, "
            "merge their frames into per-video subfolders first."
        )

    source = sources[0]
    image_path = Path(source.path)

    # Heterogeneous capture: if the image dir is organized into image-bearing
    # subfolders (e.g. from a Merge Frames node, one folder per video), give
    # COLMAP one camera per folder so each video solves its own intrinsics.
    # Otherwise the classic flat single-camera layout.
    subdirs = [d for d in sorted(image_path.iterdir()) if d.is_dir() and _images_in(d)]
    per_folder = bool(subdirs)
    if per_folder:
        source_map = {p: d.name for d in subdirs for p in _images_in(d)}
    else:
        source_map = {p: source.source_id for p in _images_in(image_path)}

    if len(source_map) < 3:
        raise ColmapError(f"Need at least 3 images, found {len(source_map)} in {image_path}")

    distorted = workspace_dir / "distorted"
    # Wipe intermediates from any prior run — a stale database.db would
    # accumulate old image entries (e.g. flat names from a previous layout)
    # alongside the new ones and corrupt the reconstruction.
    if distorted.exists():
        shutil.rmtree(distorted)
    # Same for the undistorter outputs: it writes into workspace_dir/images
    # (etc.) without clearing it, so frames from a previous run with a
    # different layout (e.g. flat single-video names) would sit alongside
    # the new per-video subfolders and poison the Brush dataset.
    for stale in ("images", "sparse", "stereo"):
        out = workspace_dir / stale
        if out.exists():
            shutil.rmtree(out)
    sparse = distorted / "sparse"
    sparse.mkdir(parents=True, exist_ok=True)
    db = distorted / "database.db"

    camera_model = _camera_model_arg(source.camera_model)
    use_gpu_val = "1" if params.use_gpu else "0"

    # Detect which GPU flag names this COLMAP build uses.
    colmap_opts = get_colmap_version_and_options(params.colmap_executable)
    feature_gpu_flag = colmap_opts['feature_gpu_option']
    matching_gpu_flag = colmap_opts['matching_gpu_option']

    # Capture all subprocess output to log.
    with open(log_path, "w") as log:
        # 1. Feature extraction. One camera per subfolder for merged
        # multi-video input; a single shared camera for a flat folder.
        single_cam_flag = "single_camera_per_folder" if per_folder else "single_camera"
        _run_colmap_step(
            log, params.colmap_executable, "feature_extractor",
            "--database_path", str(db),
            "--image_path", str(image_path),
            f"--ImageReader.{single_cam_flag}", "1",
            "--ImageReader.camera_model", camera_model,
            f"--{feature_gpu_flag}", use_gpu_val,
            register_proc=register_proc,
        )

        # 2. Matching
        matcher = "exhaustive_matcher" if params.matching == "exhaustive" else "sequential_matcher"
        _run_colmap_step(
            log, params.colmap_executable, matcher,
            "--database_path", str(db),
            f"--{matching_gpu_flag}", use_gpu_val,
            register_proc=register_proc,
        )

        # 3. Bundle adjustment (mapper)
        _run_colmap_step(
            log, params.colmap_executable, "mapper",
            "--database_path", str(db),
            "--image_path", str(image_path),
            "--output_path", str(sparse),
            "--Mapper.ba_global_function_tolerance=0.000001",
            register_proc=register_proc,
        )

        # 4. Image undistorter
        _run_colmap_step(
            log, params.colmap_executable, "image_undistorter",
            "--image_path", str(image_path),
            "--input_path", str(sparse / "0"),
            "--output_path", str(workspace_dir),
            "--output_type", "COLMAP",
            register_proc=register_proc,
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


def merge_models(
    model_a: Path, model_b: Path, output_dir: Path, log_path: Path,
    *, colmap_executable: str = "colmap",
) -> Path:
    """Run `colmap model_merger` to fuse two sparse models."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_path)
    with open(log_path, "w") as log:
        _run_colmap_step(
            log, colmap_executable, "model_merger",
            "--input_path1", str(model_a),
            "--input_path2", str(model_b),
            "--output_path", str(output_dir),
        )
    return output_dir


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _images_in(d: Path) -> list:
    """Image files directly inside d (one level; follows dir symlinks)."""
    return [p for p in Path(d).iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTS]


def _run_colmap_step(log_file, executable: str, subcommand: str, *args: str, register_proc=None):
    cmd = [executable, subcommand, *args]
    log_file.write(f"\n+ {' '.join(cmd)}\n")
    log_file.flush()
    # Popen (not subprocess.run) so the running step can be terminated mid-flight
    # via register_proc — that's what the node's Stop button cancels.
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
    if register_proc is not None:
        register_proc(proc)
    returncode = proc.wait()
    if returncode != 0:
        raise ColmapError(
            f"colmap {subcommand} failed with code {returncode}. "
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
