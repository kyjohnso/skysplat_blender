"""Frame extraction and frame-folder utilities.

Pure parts (this stage): discover_frames.
Scene parts (Stage D): extract_frames — uses bpy.ops.render.opengl.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def discover_frames(image_dir: Path) -> list[Path]:
    """Return a sorted list of image files in image_dir.

    Filters by extension (.jpg, .jpeg, .png — case-insensitive).
    Raises FileNotFoundError if image_dir does not exist.
    """
    image_dir = Path(image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(f"Frames directory does not exist: {image_dir}")
    return sorted(
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )


def _safe_subdir_name(name: str) -> str:
    """Filesystem-friendly subfolder name derived from a source id."""
    safe = re.sub(r"[^\w.-]+", "_", str(name).strip()).strip("_")
    return safe or "src"


def merge_frame_dirs(sources, merged_root: Path, *, force_copy: bool = False) -> dict:
    """Stage several frame folders under one root as per-source subfolders.

    `sources` is an iterable of (source_id, frames_dir). For each, a REAL
    subfolder merged_root/<name>/ is created (name = sanitized, collision-
    uniquified source_id) and the image files are HARDLINKED into it one-by-one
    (copied when force_copy=True or across filesystems).

    Hardlinks, not symlinks: COLMAP canonicalizes symlinks — a directory
    symlink gets flattened to basenames (one camera), and per-file symlinks get
    recorded by their resolved target path (e.g. ../../Frame_Extract/...), which
    breaks --single_camera_per_folder and makes the undistorter write outside
    its output dir. A hardlink is indistinguishable from a regular file (no
    target to resolve) and costs no extra disk on the same filesystem, so COLMAP
    records clean <video>/<frame>.png names and gives one camera per video.

    merged_root is wiped first so re-runs don't accumulate stale entries.
    Returns {subdir_name: original_source_id}.
    """
    merged_root = Path(merged_root)
    if merged_root.exists():
        for entry in merged_root.iterdir():
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            else:
                shutil.rmtree(entry)
    merged_root.mkdir(parents=True, exist_ok=True)

    mapping: dict[str, str] = {}
    used: set[str] = set()

    for source_id, src in sources:
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(f"Frames directory does not exist: {src}")

        name = _safe_subdir_name(source_id)
        base, i = name, 1
        while name in used:
            i += 1
            name = f"{base}_{i}"
        used.add(name)

        dst = merged_root / name
        dst.mkdir(parents=True, exist_ok=True)
        for f in discover_frames(src):
            target = dst / f.name
            placed = False
            if not force_copy:
                try:
                    os.link(f, target)  # hardlink: no extra disk, no symlink to resolve
                    placed = True
                except OSError:
                    placed = False      # cross-filesystem etc. -> copy
            if not placed:
                shutil.copy2(f, target)

        mapping[name] = str(source_id)

    return mapping


try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from contextlib import contextmanager


def extract_frames(
    scene,
    video_strip_name: str,
    out_dir: Path,
    start: int,
    end: int,
    step: int,
) -> int:
    """Extract frames synchronously via Blender's OpenGL render.

    Returns the number of frames written. Raises FrameExtractError if
    the strip is missing or the render fails.

    Phase 1 is synchronous (blocks until done). Phase 2 wraps this in
    a RunningTask via the bake walker.
    """
    if not HAS_BPY:
        raise RuntimeError("extract_frames requires Blender (bpy).")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear stale frames from a previous run. Re-extracting at a different
    # resolution or range otherwise leaves old frames at non-overlapping
    # frame numbers, producing a mixed-resolution folder that COLMAP's
    # --single_camera_per_folder rejects (CAMERA_SINGLE_DIM_ERROR), and an
    # inflated image count.
    for old in out_dir.iterdir():
        if old.is_file() and old.suffix.lower() in _IMAGE_EXTENSIONS:
            old.unlink()

    target = _find_movie_strip(scene, video_strip_name)
    if target is None:
        from .errors import FrameExtractError
        raise FrameExtractError(f"Movie strip '{video_strip_name}' not found in scene")

    with _restore_render_state(scene), _solo_strip(scene, target):
        # Resolution from strip
        scene.render.resolution_x = target.elements[0].orig_width
        scene.render.resolution_y = target.elements[0].orig_height
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.filepath = str(out_dir / "frame_")
        scene.frame_start = start
        scene.frame_end = end
        scene.frame_step = step
        bpy.ops.render.opengl(animation=True, sequencer=True)

    written = sum(1 for f in out_dir.iterdir() if f.suffix.lower() == ".png")
    return written


def _find_movie_strip(scene, name: str):
    seq_editor = scene.sequence_editor
    if not seq_editor:
        return None
    pool = seq_editor.strips_all if hasattr(seq_editor, "strips_all") else seq_editor.sequences_all
    for s in pool:
        if s.type == "MOVIE" and s.name == name:
            return s
    return None


@contextmanager
def _solo_strip(scene, target):
    seq_editor = scene.sequence_editor
    pool = seq_editor.strips_all if hasattr(seq_editor, "strips_all") else seq_editor.sequences_all
    saved = {}
    for s in pool:
        if s.type == "MOVIE":
            saved[s.name] = s.mute
            s.mute = (s != target)
    try:
        yield
    finally:
        for s in pool:
            if s.type == "MOVIE" and s.name in saved:
                s.mute = saved[s.name]


@contextmanager
def _restore_render_state(scene):
    rs = scene.render
    saved = {
        "filepath": rs.filepath,
        "file_format": rs.image_settings.file_format,
        "color_mode": rs.image_settings.color_mode,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "frame_step": scene.frame_step,
        "res_x": rs.resolution_x,
        "res_y": rs.resolution_y,
        "res_pct": rs.resolution_percentage,
    }
    try:
        yield
    finally:
        rs.filepath = saved["filepath"]
        rs.image_settings.file_format = saved["file_format"]
        rs.image_settings.color_mode = saved["color_mode"]
        scene.frame_start = saved["frame_start"]
        scene.frame_end = saved["frame_end"]
        scene.frame_step = saved["frame_step"]
        rs.resolution_x = saved["res_x"]
        rs.resolution_y = saved["res_y"]
        rs.resolution_percentage = saved["res_pct"]
