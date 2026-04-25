"""COLMAP service.

Pure parts (this stage): read_model, write_model, ColmapModel dataclass.
Subprocess parts (Stage B): run_reconstruction, merge_models.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
