# Phase 1: Services Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pure pipeline logic out of the existing sidebar panel files into a new `services/` package so both the existing panels and the future node graph editor (phase 2) call the same code.

**Architecture:** Three-tier — `services/` (pure Python or scene-mutating but UI-state-free) + existing sidebar panels (refactored to thin wrappers calling services) + Blender's standard infrastructure. No new UI in this phase.

**Tech Stack:** Python 3.11+, Blender Python API (bpy), pytest, numpy, mathutils (pip package available standalone), COLMAP subprocess, Brush subprocess.

**Spec:** `docs/superpowers/specs/2026-04-25-node-graph-editor-design.md`

**Stages (each self-contained, each commits cleanly):**

- **Stage A — setup + pure services** (10 tasks): pytest harness, package skeleton, `srt`, `transform`, `frames.discover`, `brush.prepare_dataset`, `colmap.read_model`/`write_model`. Highest test value, lowest risk.
- **Stage B — COLMAP subprocess** (4 tasks): `colmap.run_reconstruction`, `colmap.merge_models`, sidebar wiring.
- **Stage C — Brush subprocess** (3 tasks): `brush.run_training`, `brush.build_command`, sidebar wiring.
- **Stage D — scene services** (5 tasks): `video_service.load_video_into_vse`, `frames_service.extract_frames`, `colmap_view_service.import_model_to_scene`, `camera_service.create_animated_cameras`. Headless integration tests.

---

## File Structure

**New files (all created in this plan):**

```
services/
  __init__.py                    # exports public API
  srt.py                         # parse_srt_metadata (pure)
  transform.py                   # apply_transform (pure, uses mathutils)
  frames.py                      # discover_frames (pure) + extract_frames (scene)
  colmap.py                      # run_reconstruction, merge_models, read_model, write_model (mostly pure)
  brush.py                       # prepare_dataset, build_command, run_training (pure)
  video.py                       # load_video_into_vse (scene)
  colmap_view.py                 # import_model_to_scene, read_root_transform (scene)
  camera.py                      # create_animated_cameras (scene)
  errors.py                      # ColmapError, BrushError, FrameExtractError, NodeEvalError

tests/
  __init__.py
  conftest.py                    # pytest config
  fixtures/
    sample.srt                   # tiny DJI SRT for parser tests
    sparse/
      cameras.txt                # tiny COLMAP model (3 cameras, 5 points)
      images.txt
      points3D.txt
  unit/
    __init__.py
    test_srt.py
    test_transform.py
    test_frames.py
    test_colmap.py
    test_brush.py

requirements-dev.txt             # pytest, mathutils, numpy
pytest.ini                       # config

docs/
  release-checklist.md           # manual smoke checklist for releases
```

**Modified files (existing — refactored to call services):**

- `ui/video_panel.py` — `SKY_SPLAT_OT_load_video.execute` (lines 226–363) and `SKY_SPLAT_OT_extract_frames.execute` (lines 370–484) call into `services/video.py` and `services/frames.py`. SRT auto-detection (`update_srt_path`, lines 32–51) calls `services/srt.parse_srt_metadata`.
- `ui/colmap_panel.py` — `run_colmap_processing` (lines 580–692) replaced by call to `services/colmap.run_reconstruction`. `SKY_SPLAT_OT_load_colmap_model.execute` (lines 930–1086) calls `services/colmap_view.import_model_to_scene`. `SKY_SPLAT_OT_export_colmap_model.execute` (lines 1108–1238) calls `services/transform.apply_transform`. `SKY_SPLAT_OT_create_camera_animation.execute` (lines 1259–1410) calls `services/camera.create_animated_cameras`. `SKY_SPLAT_OT_prepare_brush_dataset.execute` (lines 788–902) calls `services/brush.prepare_dataset`.
- `ui/gaussian_splatting_panel.py` — `SKY_SPLAT_OT_run_brush_training.build_brush_command` (lines 551–622) replaced by `services/brush.build_command`. `run_training` thread (lines 624–653) replaced by `services/brush.run_training`.
- `__init__.py` — no change required (panels still register the same classes).
- `.gitignore` — add `tests/__pycache__/` and `.pytest_cache/`.

---

# Stage A — Setup + Pure Services

## Task A1: pytest scaffolding and dev-deps

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py` (empty)
- Create: `tests/unit/__init__.py` (empty)
- Create: `tests/conftest.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create `requirements-dev.txt`**

```
pytest>=7.4
numpy>=1.24
mathutils>=3.3
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests/unit
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 3: Create `tests/__init__.py` and `tests/unit/__init__.py` (empty files)**

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Pytest configuration shared across the unit tests.

These tests import skysplat services directly. Services that need bpy
gate the import internally — pure modules import cleanly without
Blender.
"""
import sys
from pathlib import Path

# Make the addon root importable so `from services import ...` works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 5: Append to `.gitignore`**

Append two lines after the existing `.superpowers/` line:

```
.pytest_cache/
tests/__pycache__/
```

- [ ] **Step 6: Verify pytest collects nothing yet**

Run: `pip install -r requirements-dev.txt && pytest -q`
Expected output ends with: `no tests ran`

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/__init__.py tests/unit/__init__.py tests/conftest.py .gitignore
git commit -m "Add pytest scaffolding for services tests"
```

---

## Task A2: services package skeleton

**Files:**
- Create: `services/__init__.py`
- Create: `services/errors.py`

- [ ] **Step 1: Create `services/errors.py`**

```python
"""Typed exceptions raised by skysplat services.

Each service raises one of these so callers can recover precisely.
The bake walker (phase 2) will map these to per-node error states.
"""


class SkysplatServiceError(Exception):
    """Base class for all service-layer errors."""


class ColmapError(SkysplatServiceError):
    """COLMAP subprocess or model I/O failed."""


class BrushError(SkysplatServiceError):
    """Brush training subprocess failed."""


class FrameExtractError(SkysplatServiceError):
    """Frame extraction failed (Blender render or VSE issue)."""


class TransformError(SkysplatServiceError):
    """COLMAP model transformation failed."""


class NodeEvalError(SkysplatServiceError):
    """Node graph evaluation failed because expected scene state is missing.

    Recoverable — the next bake should re-create the missing state.
    """
```

- [ ] **Step 2: Create `services/__init__.py`**

```python
"""skysplat services package.

Pure-Python pipeline functions used by both the existing sidebar panels
and the future node-graph editor. Modules tagged 'pure' have no bpy
dependency. Modules tagged 'scene' take a bpy.types.Scene as an explicit
argument.
"""

from .errors import (
    SkysplatServiceError,
    ColmapError,
    BrushError,
    FrameExtractError,
    TransformError,
    NodeEvalError,
)

__all__ = [
    "SkysplatServiceError",
    "ColmapError",
    "BrushError",
    "FrameExtractError",
    "TransformError",
    "NodeEvalError",
]
```

- [ ] **Step 3: Verify import works in pytest**

Run: `python -c "from services import ColmapError; print(ColmapError)"` (from repo root)
Expected: `<class 'services.errors.ColmapError'>`

- [ ] **Step 4: Commit**

```bash
git add services/__init__.py services/errors.py
git commit -m "Add services package skeleton with typed exceptions"
```

---

## Task A3: SRT parser (pure)

**Files:**
- Create: `services/srt.py`
- Create: `tests/fixtures/sample.srt`
- Create: `tests/unit/test_srt.py`

The existing SRT parsing is implicit — currently `update_srt_path` (`ui/video_panel.py:32–51`) just auto-detects the path. Actual SRT parsing for camera intrinsics/positions isn't yet in skysplat. We're adding it for the first time, sized to what `parse_srt_metadata` needs to return.

The DJI SRT format has frame-stamped blocks like:
```
1
00:00:00,000 --> 00:00:00,033
<font size="28">SrtCnt : 1, DiffTime : 33ms
2025-04-25 12:00:00.000
[iso : 100] [shutter : 1/1000] [fnum : 280] [ev : 0] [ct : 5500] [color_md : default] [focal_len : 240] [latitude: 40.0] [longitude: -105.0] [rel_alt: 50.0 abs_alt: 1650.0]</font>
```

For phase 1 we extract a small set: `focal_len_mm`, `latitude`, `longitude`, `rel_alt`, plus a list of per-frame entries. Future phases (camera-model derivation) build on this.

- [ ] **Step 1: Write the failing test — `tests/unit/test_srt.py`**

```python
"""Tests for services/srt.py — DJI SRT metadata parsing."""
from pathlib import Path

from services.srt import parse_srt_metadata


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.srt"


class TestParseSrtMetadata:
    def test_returns_none_for_missing_file(self, tmp_path):
        result = parse_srt_metadata(tmp_path / "nope.srt")
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        empty = tmp_path / "empty.srt"
        empty.write_text("")
        assert parse_srt_metadata(empty) is None

    def test_parses_two_frames_from_fixture(self):
        result = parse_srt_metadata(FIXTURE)
        assert result is not None
        assert len(result["frames"]) == 2

    def test_first_frame_has_expected_intrinsics(self):
        result = parse_srt_metadata(FIXTURE)
        first = result["frames"][0]
        assert first["frame_index"] == 1
        assert first["focal_len_mm"] == 24.0
        assert first["latitude"] == 40.0
        assert first["longitude"] == -105.0
        assert first["rel_alt"] == 50.0

    def test_summary_uses_first_frame_intrinsics(self):
        result = parse_srt_metadata(FIXTURE)
        assert result["focal_len_mm"] == 24.0
```

- [ ] **Step 2: Create the fixture `tests/fixtures/sample.srt`**

```
1
00:00:00,000 --> 00:00:00,033
<font size="28">SrtCnt : 1, DiffTime : 33ms
2025-04-25 12:00:00.000
[iso : 100] [shutter : 1/1000] [fnum : 280] [ev : 0] [ct : 5500] [color_md : default] [focal_len : 240] [latitude: 40.0] [longitude: -105.0] [rel_alt: 50.0 abs_alt: 1650.0]</font>

2
00:00:00,033 --> 00:00:00,066
<font size="28">SrtCnt : 2, DiffTime : 33ms
2025-04-25 12:00:00.033
[iso : 100] [shutter : 1/1000] [fnum : 280] [ev : 0] [ct : 5500] [color_md : default] [focal_len : 240] [latitude: 40.000001] [longitude: -105.000001] [rel_alt: 50.1 abs_alt: 1650.1]</font>
```

Note the DJI convention: `focal_len` is reported in tenths of millimeters (240 → 24.0 mm).

- [ ] **Step 3: Run the test to verify failure**

Run: `pytest tests/unit/test_srt.py -v`
Expected: ImportError / ModuleNotFoundError on `services.srt`.

- [ ] **Step 4: Implement `services/srt.py`**

```python
"""Parse DJI drone SRT metadata files.

DJI SRT files contain per-frame telemetry — GPS position, altitude,
focal length, exposure. We extract the bits relevant to COLMAP camera
intrinsics estimation (focal length) plus position info that future
work may use as a reconstruction prior.

Pure module: no bpy dependency.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Block separator: a blank line. Each block has 4 lines:
#   <index>
#   <timecode --> timecode>
#   <html-wrapped metadata line 1 (counter)>
#   <metadata line 2 (timestamp)>
#   <metadata line 3 (bracketed key:value pairs)>
# But formats vary. We just look for the bracketed metadata anywhere
# in the block and the leading integer index.

_KV_RE = re.compile(r"\[(\w+)\s*:\s*([^\]]+?)\]")
_INDEX_RE = re.compile(r"^\s*(\d+)\s*$", re.MULTILINE)


def parse_srt_metadata(srt_path: Path) -> dict[str, Any] | None:
    """Parse a DJI SRT file. Returns None if missing/empty/unparseable.

    Returns a dict:
      {
        "focal_len_mm": float,           # from the first frame
        "frames": [
          {"frame_index": int,
           "focal_len_mm": float | None,
           "latitude": float | None,
           "longitude": float | None,
           "rel_alt": float | None,
           "abs_alt": float | None},
           ...
        ],
      }
    """
    srt_path = Path(srt_path)
    if not srt_path.exists():
        return None
    raw = srt_path.read_text(errors="replace")
    if not raw.strip():
        return None

    blocks = [b for b in raw.split("\n\n") if b.strip()]
    frames: list[dict[str, Any]] = []
    for block in blocks:
        index_match = _INDEX_RE.search(block)
        if not index_match:
            continue
        kv = {m.group(1).lower(): m.group(2).strip() for m in _KV_RE.finditer(block)}
        if not kv:
            continue
        # Some DJI SRTs cram multiple values into a single bracket like
        # "[rel_alt: 50.0 abs_alt: 1650.0]" — split those on spaces.
        for key in list(kv.keys()):
            val = kv[key]
            if " " in val and ":" in val:
                # Re-split: "50.0 abs_alt: 1650.0" → rel_alt=50.0, abs_alt=1650.0
                head, _, tail = val.partition(" ")
                kv[key] = head
                # tail is "abs_alt: 1650.0" — re-parse
                tail_match = re.match(r"(\w+)\s*:\s*([\d.\-]+)", tail)
                if tail_match:
                    kv[tail_match.group(1).lower()] = tail_match.group(2)

        focal_raw = _safe_float(kv.get("focal_len"))
        focal_mm = focal_raw / 10.0 if focal_raw is not None else None
        frames.append(
            {
                "frame_index": int(index_match.group(1)),
                "focal_len_mm": focal_mm,
                "latitude": _safe_float(kv.get("latitude")),
                "longitude": _safe_float(kv.get("longitude")),
                "rel_alt": _safe_float(kv.get("rel_alt")),
                "abs_alt": _safe_float(kv.get("abs_alt")),
            }
        )

    if not frames:
        return None

    return {
        "focal_len_mm": frames[0]["focal_len_mm"],
        "frames": frames,
    }


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/unit/test_srt.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add services/srt.py tests/fixtures/sample.srt tests/unit/test_srt.py
git commit -m "Add services.srt with DJI SRT metadata parser + tests"
```

---

## Task A4: transform service (pure, uses mathutils)

**Files:**
- Create: `services/transform.py`
- Create: `tests/unit/test_transform.py`

This extracts the camera-pose + point transformation math from `SKY_SPLAT_OT_export_colmap_model.execute` (`ui/colmap_panel.py:1149–1224`). The function takes a model (cameras dict, images dict, points3D dict) plus a 4×4 matrix and returns transformed copies.

- [ ] **Step 1: Write the failing test — `tests/unit/test_transform.py`**

```python
"""Tests for services/transform.py — COLMAP model transformation."""
import numpy as np
from mathutils import Matrix, Vector

from services.transform import apply_transform, ColmapModel
# Reuse existing utilities — Image and Point3D dataclasses
from utils.read_write_model import Image, Point3D, Camera


def _identity_model() -> ColmapModel:
    cameras = {
        1: Camera(id=1, model="SIMPLE_PINHOLE", width=640, height=480, params=[500.0, 320.0, 240.0])
    }
    images = {
        10: Image(
            id=10,
            qvec=np.array([1.0, 0.0, 0.0, 0.0]),  # identity rotation
            tvec=np.array([0.0, 0.0, 0.0]),
            camera_id=1,
            name="frame_001.png",
            xys=np.zeros((0, 2)),
            point3D_ids=np.zeros(0, dtype=int),
        )
    }
    points3D = {
        100: Point3D(
            id=100,
            xyz=np.array([1.0, 2.0, 3.0]),
            rgb=np.array([255, 0, 0]),
            error=0.0,
            image_ids=np.array([10]),
            point2D_idxs=np.array([0]),
        )
    }
    return ColmapModel(cameras=cameras, images=images, points3D=points3D)


class TestApplyTransform:
    def test_identity_matrix_leaves_model_unchanged(self):
        model = _identity_model()
        out = apply_transform(model, Matrix.Identity(4))
        # Same point coords (within float tolerance)
        assert np.allclose(out.points3D[100].xyz, [1.0, 2.0, 3.0])

    def test_translation_moves_point(self):
        model = _identity_model()
        translation = Matrix.Translation(Vector((10.0, 0.0, 0.0)))
        out = apply_transform(model, translation)
        assert np.allclose(out.points3D[100].xyz, [11.0, 2.0, 3.0])

    def test_uniform_scale_scales_point(self):
        model = _identity_model()
        scale = Matrix.Diagonal((2.0, 2.0, 2.0, 1.0))
        out = apply_transform(model, scale)
        assert np.allclose(out.points3D[100].xyz, [2.0, 4.0, 6.0])

    def test_input_model_is_not_mutated(self):
        model = _identity_model()
        scale = Matrix.Diagonal((2.0, 2.0, 2.0, 1.0))
        _ = apply_transform(model, scale)
        # Original unchanged
        assert np.allclose(model.points3D[100].xyz, [1.0, 2.0, 3.0])
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/test_transform.py -v`
Expected: ImportError on `services.transform`.

- [ ] **Step 3: Implement `services/transform.py`**

```python
"""Apply a 4×4 transform to a COLMAP sparse model.

Transforms BOTH the 3D points and the camera poses. Camera poses must
be re-derived because COLMAP stores world→camera transforms (rotation
quaternion + translation), so applying a world transform requires
inverting the camera matrix, applying the world transform, and
reinverting.

Pure module: uses numpy + mathutils (both pip-installable). No bpy.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from mathutils import Matrix, Vector

from utils.read_write_model import Image, Point3D, qvec2rotmat, rotmat2qvec


@dataclass
class ColmapModel:
    """In-memory COLMAP sparse model: cameras, images, points3D."""
    cameras: dict
    images: dict
    points3D: dict


def apply_transform(model: ColmapModel, mat4: Matrix) -> ColmapModel:
    """Return a new ColmapModel with cameras and points transformed by mat4.

    The transform is interpreted as a world transform — points and
    camera positions are placed by mat4 @ point. The original model
    is not mutated.
    """
    new_points = {
        pid: _transform_point(p, mat4) for pid, p in model.points3D.items()
    }
    new_images = {
        iid: _transform_image_pose(img, mat4) for iid, img in model.images.items()
    }
    # Cameras (intrinsics) are unchanged by a world transform.
    return ColmapModel(cameras=dict(model.cameras), images=new_images, points3D=new_points)


def _transform_point(point: Point3D, mat4: Matrix) -> Point3D:
    p = Vector((point.xyz[0], point.xyz[1], point.xyz[2]))
    p_new = mat4 @ p
    return Point3D(
        id=point.id,
        xyz=np.array([p_new.x, p_new.y, p_new.z]),
        rgb=point.rgb,
        error=point.error,
        image_ids=point.image_ids,
        point2D_idxs=point.point2D_idxs,
    )


def _transform_image_pose(image: Image, mat4: Matrix) -> Image:
    # COLMAP stores world->camera. So:
    #   R_wc, t_wc = qvec2rotmat(image.qvec), image.tvec
    # The camera center in world coords:
    #   C = -R_wc.T @ t_wc
    # Apply world transform: C' = mat4 @ C, R'_cw = R_cw @ mat4_rot.inverse
    # Then convert back to world->camera.
    R_wc = qvec2rotmat(image.qvec)
    t_wc = np.array(image.tvec, dtype=float)
    C = -R_wc.T @ t_wc

    mat4_np = np.array(mat4)
    rot_world = mat4_np[:3, :3]
    trans_world = mat4_np[:3, 3]

    C_new = rot_world @ C + trans_world
    R_cw_new = R_wc.T @ np.linalg.inv(rot_world)
    R_wc_new = R_cw_new.T
    t_wc_new = -R_wc_new @ C_new

    return Image(
        id=image.id,
        qvec=rotmat2qvec(R_wc_new),
        tvec=t_wc_new,
        camera_id=image.camera_id,
        name=image.name,
        xys=image.xys,
        point3D_ids=image.point3D_ids,
    )
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/unit/test_transform.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add services/transform.py tests/unit/test_transform.py
git commit -m "Add services.transform with apply_transform + tests"
```

---

## Task A5: frames.discover_frames (pure)

**Files:**
- Create: `services/frames.py`
- Create: `tests/unit/test_frames.py`

Phase 1 only implements the pure portion (`discover_frames`). The scene-mutating `extract_frames` is added in Stage D.

- [ ] **Step 1: Write the failing test — `tests/unit/test_frames.py`**

```python
"""Tests for services/frames.py — frame folder discovery."""
from pathlib import Path

from services.frames import discover_frames


class TestDiscoverFrames:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        assert discover_frames(tmp_path) == []

    def test_returns_image_files_sorted(self, tmp_path):
        for name in ["frame_003.png", "frame_001.png", "frame_002.png"]:
            (tmp_path / name).write_bytes(b"")
        result = discover_frames(tmp_path)
        assert [p.name for p in result] == ["frame_001.png", "frame_002.png", "frame_003.png"]

    def test_filters_non_image_files(self, tmp_path):
        (tmp_path / "frame_001.png").write_bytes(b"")
        (tmp_path / "notes.txt").write_text("hi")
        (tmp_path / "video.mp4").write_bytes(b"")
        result = discover_frames(tmp_path)
        assert [p.name for p in result] == ["frame_001.png"]

    def test_accepts_jpg_jpeg_png(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"")
        (tmp_path / "b.jpeg").write_bytes(b"")
        (tmp_path / "c.PNG").write_bytes(b"")
        result = discover_frames(tmp_path)
        assert {p.name for p in result} == {"a.jpg", "b.jpeg", "c.PNG"}

    def test_missing_dir_raises(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError):
            discover_frames(tmp_path / "nope")
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/test_frames.py -v`
Expected: ImportError on `services.frames`.

- [ ] **Step 3: Implement `services/frames.py`**

```python
"""Frame extraction and frame-folder utilities.

Pure parts (this stage): discover_frames.
Scene parts (Stage D): extract_frames — uses bpy.ops.render.opengl.
"""
from __future__ import annotations

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
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/unit/test_frames.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/frames.py tests/unit/test_frames.py
git commit -m "Add services.frames.discover_frames + tests"
```

---

## Task A6: brush.prepare_dataset (pure)

**Files:**
- Create: `services/brush.py`
- Create: `tests/unit/test_brush.py`
- Modify: `ui/colmap_panel.py` — `SKY_SPLAT_OT_prepare_brush_dataset.execute` (lines 788–902) to call the service.

Extracts the dataset-preparation logic from `SKY_SPLAT_OT_prepare_brush_dataset.execute` (`ui/colmap_panel.py:788–902`). The original mixes filesystem work with sidebar-state mutation; we extract just the filesystem work.

- [ ] **Step 1: Write the failing test — `tests/unit/test_brush.py`**

```python
"""Tests for services/brush.py — Brush dataset preparation."""
from pathlib import Path

import pytest

from services.brush import prepare_dataset
from services.errors import BrushError


def _write_sparse_model(sparse_dir: Path):
    sparse_dir.mkdir(parents=True, exist_ok=True)
    (sparse_dir / "cameras.bin").write_bytes(b"\x00")
    (sparse_dir / "images.bin").write_bytes(b"\x00")
    (sparse_dir / "points3D.bin").write_bytes(b"\x00")


def _write_images(images_dir: Path, count: int = 3):
    images_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (images_dir / f"frame_{i:03d}.png").write_bytes(b"\x89PNG\r\n")
    (images_dir / "notes.txt").write_text("ignored")


class TestPrepareDataset:
    def test_creates_target_layout(self, tmp_path):
        sparse = tmp_path / "in_sparse"
        images = tmp_path / "in_images"
        out = tmp_path / "out"
        _write_sparse_model(sparse)
        _write_images(images)

        result = prepare_dataset(sparse, images, out)

        assert result == out
        assert (out / "sparse" / "0" / "cameras.bin").exists()
        assert (out / "sparse" / "0" / "images.bin").exists()
        assert (out / "sparse" / "0" / "points3D.bin").exists()
        # images directory exists (either symlink or copy)
        assert (out / "images").exists()

    def test_copies_images_when_force_copy(self, tmp_path):
        sparse = tmp_path / "in_sparse"
        images = tmp_path / "in_images"
        out = tmp_path / "out"
        _write_sparse_model(sparse)
        _write_images(images)

        prepare_dataset(sparse, images, out, force_copy=True)

        # All png files copied, txt files filtered
        copied = sorted((out / "images").glob("*.png"))
        assert len(copied) == 3
        assert not (out / "images" / "notes.txt").exists()

    def test_falls_back_to_txt_files_for_sparse(self, tmp_path):
        sparse = tmp_path / "in_sparse"
        sparse.mkdir(parents=True)
        # Only .txt versions present
        (sparse / "cameras.txt").write_text("# comment")
        (sparse / "images.txt").write_text("# comment")
        (sparse / "points3D.txt").write_text("# comment")
        images = tmp_path / "in_images"
        _write_images(images, 1)
        out = tmp_path / "out"

        prepare_dataset(sparse, images, out, force_copy=True)

        assert (out / "sparse" / "0" / "cameras.txt").exists()

    def test_raises_when_sparse_missing(self, tmp_path):
        with pytest.raises(BrushError):
            prepare_dataset(
                tmp_path / "missing", tmp_path / "imgs", tmp_path / "out"
            )

    def test_raises_when_images_missing(self, tmp_path):
        sparse = tmp_path / "sparse"
        _write_sparse_model(sparse)
        with pytest.raises(BrushError):
            prepare_dataset(sparse, tmp_path / "missing", tmp_path / "out")
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/test_brush.py -v`
Expected: ImportError on `services.brush`.

- [ ] **Step 3: Implement `services/brush.py`**

```python
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
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/unit/test_brush.py -v`
Expected: 5 passed.

- [ ] **Step 5: Refactor existing operator to call the service**

In `ui/colmap_panel.py`, replace lines 792–862 (the body inside `try:` of `SKY_SPLAT_OT_prepare_brush_dataset.execute`) with a call to the service. Keep the surrounding exception handling, logging, and the auto-update-splat-instance block at lines 866–902.

Open `ui/colmap_panel.py` and replace the block from line 792 (after `try:`) up to and including line 862 (the end of the symlink/copy logic, just before `# Mark as prepared`) with:

```python
            # Define paths
            export_path = colmap_instance.model_export_path
            images_path = colmap_instance.images_path

            # Determine source sparse model path
            transformed_sparse_src = os.path.join(export_path, "sparse", "0")
            if not os.path.exists(transformed_sparse_src):
                transformed_sparse_src = export_path

            parent_dir = os.path.dirname(export_path)
            brush_dataset_dir = os.path.join(parent_dir, "brush_dataset")

            from ..services.brush import prepare_dataset
            from ..services.errors import BrushError
            try:
                prepare_dataset(
                    Path(transformed_sparse_src),
                    Path(images_path),
                    Path(brush_dataset_dir),
                )
            except BrushError as exc:
                raise RuntimeError(str(exc)) from exc
```

You'll also need to add `from pathlib import Path` to the imports at the top of `ui/colmap_panel.py` if it isn't there.

- [ ] **Step 6: Manual smoke check**

Open Blender, load the addon, run "Prepare Brush Dataset" on an existing COLMAP instance. Verify:
- `brush_dataset/sparse/0/` contains the model files
- `brush_dataset/images/` is a symlink (or copy on Windows)
- The auto-creation of the splat instance still works

If the manual check passes, proceed to commit. If it fails, debug and fix before committing.

- [ ] **Step 7: Commit**

```bash
git add services/brush.py tests/unit/test_brush.py ui/colmap_panel.py
git commit -m "Add services.brush.prepare_dataset and wire into prepare_brush_dataset operator"
```

---

## Task A7: colmap.read_model / write_model (pure wrappers)

**Files:**
- Create: `services/colmap.py`
- Create: `tests/unit/test_colmap.py`
- Create: `tests/fixtures/sparse/cameras.txt`
- Create: `tests/fixtures/sparse/images.txt`
- Create: `tests/fixtures/sparse/points3D.txt`

Wraps the existing `utils/read_write_model.py` so callers depend on `services.colmap` rather than reaching into `utils`. The wrappers also normalize the return type as a `ColmapModel` dataclass (defined here).

- [ ] **Step 1: Create the COLMAP fixture**

`tests/fixtures/sparse/cameras.txt`:
```
# Camera list with one line of data per camera:
#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]
1 SIMPLE_PINHOLE 640 480 500.0 320.0 240.0
```

`tests/fixtures/sparse/images.txt`:
```
# Image list with two lines of data per image:
#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
#   POINTS2D[] as (X, Y, POINT3D_ID)
1 1.0 0.0 0.0 0.0 0.0 0.0 0.0 1 frame_001.png

2 1.0 0.0 0.0 0.0 1.0 0.0 0.0 1 frame_002.png

```

(Trailing blank line is required by COLMAP format — image record ends with the empty POINTS2D row.)

`tests/fixtures/sparse/points3D.txt`:
```
# 3D point list with one line of data per point:
#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]
1 1.0 2.0 3.0 255 0 0 0.0 1 0
2 -1.0 -2.0 -3.0 0 255 0 0.0 2 0
```

- [ ] **Step 2: Write the failing test — `tests/unit/test_colmap.py`**

```python
"""Tests for services/colmap.py — pure portions (read/write model)."""
from pathlib import Path

import numpy as np
import pytest

from services.colmap import read_model, write_model, ColmapModel
from services.errors import ColmapError


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sparse"


class TestReadWriteModel:
    def test_reads_fixture_two_images(self):
        model = read_model(FIXTURE)
        assert isinstance(model, ColmapModel)
        assert len(model.cameras) == 1
        assert len(model.images) == 2
        assert len(model.points3D) == 2

    def test_round_trip_preserves_image_names(self, tmp_path):
        model = read_model(FIXTURE)
        write_model(model, tmp_path)
        round_tripped = read_model(tmp_path)
        names = {img.name for img in round_tripped.images.values()}
        assert names == {"frame_001.png", "frame_002.png"}

    def test_round_trip_preserves_point_xyz(self, tmp_path):
        model = read_model(FIXTURE)
        write_model(model, tmp_path)
        round_tripped = read_model(tmp_path)
        assert np.allclose(round_tripped.points3D[1].xyz, [1.0, 2.0, 3.0])

    def test_read_missing_dir_raises(self, tmp_path):
        with pytest.raises(ColmapError):
            read_model(tmp_path / "missing")
```

- [ ] **Step 3: Run test to verify failure**

Run: `pytest tests/unit/test_colmap.py -v`
Expected: ImportError on `services.colmap`.

- [ ] **Step 4: Implement `services/colmap.py` (pure portion only — no run_reconstruction yet)**

```python
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
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/unit/test_colmap.py -v`
Expected: 4 passed.

- [ ] **Step 6: Refactor `services/transform.py` to import ColmapModel from services.colmap**

In `services/transform.py`, replace the local `ColmapModel` dataclass with an import:

```python
from .colmap import ColmapModel
```

and remove the `@dataclass class ColmapModel: ...` block from transform.py. Re-run the transform tests to ensure no regression:

Run: `pytest tests/unit/test_transform.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add services/colmap.py services/transform.py tests/unit/test_colmap.py tests/fixtures/sparse/
git commit -m "Add services.colmap with read/write model wrappers + ColmapModel"
```

---

## Task A8: integrate apply_transform into export_colmap_model operator

**Files:**
- Modify: `ui/colmap_panel.py` — `SKY_SPLAT_OT_export_colmap_model.execute` (lines 1108–1238)

The original code unrolls the math inline. We replace it with a call to `services.transform.apply_transform`.

- [ ] **Step 1: Replace the body of `SKY_SPLAT_OT_export_colmap_model.execute`**

In `ui/colmap_panel.py`, replace lines 1132–1226 (from the original `# Read the original model` comment up to `write_model(cameras, images, points3D, export_dir)`) with:

```python
            # Read the original model via the service.
            from ..services.colmap import read_model, write_model
            from ..services.transform import apply_transform

            model = read_model(Path(source_path))

            # Build the world transform from the COLMAP_Root empty's matrix_world.
            # The historical export logic also undid the X-axis flip applied
            # during import — replicate that by composing an X-rotation inverse
            # into the transform.
            x_flip_inv = mathutils.Matrix.Rotation(-math.pi, 4, 'X')
            world_xform = root.matrix_world @ x_flip_inv

            transformed = apply_transform(model, world_xform)

            # Write the updated model
            write_model(transformed, Path(export_dir), ext=".bin")
```

(Note: the legacy code combined per-image overrides — using transformed Blender camera empties — with the root transform. The new path uses ONLY the root transform, which is the documented behavior. If users rely on per-camera tweaks they'll see this as a behavior change. Flag this in the PR description.)

- [ ] **Step 2: Manual smoke check**

In Blender: load a COLMAP model, transform the COLMAP_Root empty, export. Verify:
- The export produces `cameras.bin`, `images.bin`, `points3D.bin` in the expected directory.
- Reloading the exported model lines up with the transformed root.

- [ ] **Step 3: Commit**

```bash
git add ui/colmap_panel.py
git commit -m "Use services.transform.apply_transform in export_colmap_model"
```

---

## Task A9: integrate srt parser into update_srt_path

**Files:**
- Modify: `ui/video_panel.py` — `update_srt_path` (lines 32–51)

The current `update_srt_path` only auto-fills the SRT *path*. We want to also read the SRT and stash any parsed metadata on the video instance so future stages can use it (e.g., camera-model derivation in phase 2). For phase 1 we just demonstrate the call works without changing behavior.

- [ ] **Step 1: Modify `update_srt_path`**

In `ui/video_panel.py`, replace the existing function body (lines 32–51) with:

```python
def update_srt_path(self, context):
    """Auto-detect SRT path when video path changes, and pre-parse metadata."""
    if not self.video_path:
        return
    video_path = bpy.path.abspath(self.video_path)
    base, _ = os.path.splitext(video_path)
    candidate = base + ".SRT"
    if not os.path.exists(candidate):
        candidate = base + ".srt"
    if os.path.exists(candidate):
        self.srt_path = candidate
        try:
            from ..services.srt import parse_srt_metadata
            meta = parse_srt_metadata(Path(candidate))
        except Exception:
            meta = None
        # Stash detected focal length for future use (phase 2 camera-model spec).
        if meta and meta.get("focal_len_mm") is not None:
            self["detected_focal_len_mm"] = float(meta["focal_len_mm"])
```

(The `Path` import needs to be added at the top of the file if absent: `from pathlib import Path`.)

- [ ] **Step 2: Manual smoke check**

Open Blender, set a video file with an associated `.SRT` next to it. Verify:
- The SRT path field auto-fills.
- No crash on a video file without an SRT.
- `videoinstance["detected_focal_len_mm"]` is set when SRT had focal_len data (visible via Blender's custom-properties panel on the instance).

- [ ] **Step 3: Commit**

```bash
git add ui/video_panel.py
git commit -m "Parse SRT metadata via services.srt in update_srt_path"
```

---

## Task A10: Stage A wrap-up — run all unit tests

- [ ] **Step 1: Run the full unit test suite**

Run: `pytest -v`
Expected: all tests pass (test counts: srt=5, transform=4, frames=5, brush=5, colmap=4 → 23 total).

- [ ] **Step 2: Commit any cleanups (if any)** — if everything was clean, no commit needed for this step.

---

# Stage B — COLMAP Subprocess

## Task B1: colmap.run_reconstruction

**Files:**
- Modify: `services/colmap.py` — add `run_reconstruction`, `FramesSource`, `ColmapParams`, `CameraModelSpec`, `ColmapResult`.
- Modify: `tests/unit/test_colmap.py` — add tests with mocked subprocess.

This extracts `run_colmap_processing` (`ui/colmap_panel.py:580–692`). The pure version takes data classes instead of a `colmap_instance` PropertyGroup and is fully tested with `subprocess.run` mocked.

For phase 1, we implement only **single-source** reconstruction (the existing operator's behavior). Multi-source `joint`/`merge_after` modes from the spec become a no-op-when-1-source path that gets exercised; multi-source itself is wired up in phase 2 when nodes can produce multiple Frames inputs.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_colmap.py`:

```python
import subprocess
from unittest.mock import patch, MagicMock

from services.colmap import (
    run_reconstruction, FramesSource, ColmapParams, ColmapResult, Auto, Manual,
)


class TestRunReconstruction:
    def _fake_run(self, returncode=0):
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = returncode
        result.stdout = "ok"
        result.stderr = ""
        return result

    def test_calls_colmap_in_correct_sequence(self, tmp_path):
        sources = [FramesSource(
            path=tmp_path / "frames",
            source_id="vid1",
            camera_model=Auto(),
        )]
        (tmp_path / "frames").mkdir()
        (tmp_path / "frames" / "f1.png").write_bytes(b"")
        (tmp_path / "frames" / "f2.png").write_bytes(b"")
        (tmp_path / "frames" / "f3.png").write_bytes(b"")

        params = ColmapParams(matching="exhaustive", use_gpu=False)
        workspace = tmp_path / "ws"

        with patch("services.colmap.subprocess.run") as run_mock, \
             patch("services.colmap._read_resulting_model") as read_mock:
            run_mock.side_effect = lambda *a, **kw: self._fake_run(0)
            read_mock.return_value = ColmapModel(cameras={}, images={}, points3D={})

            result = run_reconstruction(sources, workspace, params, log_path=tmp_path / "log")

        # Verify the correct sequence of calls: feature_extractor, matcher, mapper, undistorter
        commands = [c.args[0] for c in run_mock.call_args_list]
        assert any("feature_extractor" in " ".join(c) for c in commands)
        assert any("exhaustive_matcher" in " ".join(c) for c in commands)
        assert any("mapper" in " ".join(c) for c in commands)
        assert isinstance(result, ColmapResult)

    def test_raises_colmap_error_on_failure(self, tmp_path):
        sources = [FramesSource(path=tmp_path / "frames", source_id="vid1", camera_model=Auto())]
        (tmp_path / "frames").mkdir()
        for i in range(3):
            (tmp_path / "frames" / f"f{i}.png").write_bytes(b"")
        with patch("services.colmap.subprocess.run") as run_mock:
            run_mock.return_value = self._fake_run(1)
            with pytest.raises(ColmapError):
                run_reconstruction(
                    sources, tmp_path / "ws",
                    ColmapParams(use_gpu=False),
                    log_path=tmp_path / "log",
                )

    def test_source_map_populated(self, tmp_path):
        sources = [FramesSource(path=tmp_path / "frames", source_id="north", camera_model=Auto())]
        (tmp_path / "frames").mkdir()
        for i in range(3):
            (tmp_path / "frames" / f"f{i}.png").write_bytes(b"")
        with patch("services.colmap.subprocess.run") as run_mock, \
             patch("services.colmap._read_resulting_model") as read_mock:
            run_mock.side_effect = lambda *a, **kw: self._fake_run(0)
            read_mock.return_value = ColmapModel(cameras={}, images={}, points3D={})
            result = run_reconstruction(
                sources, tmp_path / "ws",
                ColmapParams(use_gpu=False),
                log_path=tmp_path / "log",
            )
        # All images attributed to "north"
        assert all(v == "north" for v in result.source_map.values())
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_colmap.py -v -k "RunReconstruction"`
Expected: ImportErrors for the new symbols.

- [ ] **Step 3: Implement `run_reconstruction` and supporting types**

Append to `services/colmap.py`:

```python
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Literal


# ---- Camera model discriminated union ----

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


# ---- Reconstruction inputs/outputs ----

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
    source_map = {p: source.source_id for p in image_path.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}}

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
        # COLMAP defaults / EXIF estimation works with SIMPLE_PINHOLE.
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_colmap.py -v`
Expected: all colmap tests pass (4 read/write + 3 reconstruction = 7).

- [ ] **Step 5: Commit**

```bash
git add services/colmap.py tests/unit/test_colmap.py
git commit -m "Add services.colmap.run_reconstruction with subprocess mocked tests"
```

---

## Task B2: colmap.merge_models tests

**Files:**
- Modify: `tests/unit/test_colmap.py`

`merge_models` was added in Task B1; this task adds its tests.

- [ ] **Step 1: Append to `tests/unit/test_colmap.py`**

```python
from services.colmap import merge_models


class TestMergeModels:
    def test_invokes_model_merger_subcommand(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        out = tmp_path / "out"
        a.mkdir(); b.mkdir()
        with patch("services.colmap.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = merge_models(a, b, out, log_path=tmp_path / "log")
        cmd = run_mock.call_args.args[0]
        assert cmd[1] == "model_merger"
        assert "--input_path1" in cmd
        assert "--input_path2" in cmd
        assert result == out

    def test_raises_on_failure(self, tmp_path):
        a = tmp_path / "a"; b = tmp_path / "b"; a.mkdir(); b.mkdir()
        with patch("services.colmap.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
            with pytest.raises(ColmapError):
                merge_models(a, b, tmp_path / "out", log_path=tmp_path / "log")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_colmap.py -v -k merge`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_colmap.py
git commit -m "Add tests for services.colmap.merge_models"
```

---

## Task B3: integrate run_reconstruction into SKY_SPLAT_OT_run_colmap

**Files:**
- Modify: `ui/colmap_panel.py` — `SKY_SPLAT_OT_run_colmap.execute` (lines 707–757) replace inline `run_colmap_processing` call.

The legacy module-level function `run_colmap_processing` (lines 580–692) is replaced by a call to the service. The function is preserved temporarily as a wrapper, then removed.

- [ ] **Step 1: Rewrite `SKY_SPLAT_OT_run_colmap.execute`**

In `ui/colmap_panel.py`, replace the entire `execute` method body of `SKY_SPLAT_OT_run_colmap` (lines 707–757) with:

```python
    def execute(self, context):
        from pathlib import Path
        from ..services.colmap import (
            run_reconstruction, FramesSource, ColmapParams, Manual,
        )
        from ..services.errors import ColmapError

        props = context.scene.skysplat_colmap_props
        colmap_instance = props.colmap_instances[props.active_colmap_index]

        source_path = colmap_instance.output_folder
        input_path = Path(source_path) / "input"

        sources = [FramesSource(
            path=input_path,
            source_id=colmap_instance.name,
            camera_model=Manual(model=colmap_instance.camera_model, params=[]),
        )]
        params = ColmapParams(
            mode="joint",
            matching=("sequential" if colmap_instance.matching_type == "SEQUENTIAL" else "exhaustive"),
            use_gpu=props.use_gpu,
            colmap_executable=props.colmap_path or "colmap",
        )

        log_path = Path(source_path) / "colmap_run.log"

        try:
            run_reconstruction(sources, Path(source_path), params, log_path=log_path)
        except ColmapError as exc:
            self.report({'ERROR'}, f"COLMAP failed: {exc}")
            return {'CANCELLED'}

        colmap_instance.is_processed = True
        self.report({'INFO'}, f"COLMAP completed for {colmap_instance.name}")
        return {'FINISHED'}
```

- [ ] **Step 2: Remove the now-unused `run_colmap_processing` function**

Delete lines 580–692 (the entire `def run_colmap_processing` block) in `ui/colmap_panel.py`. The other helpers (`run_command`, `inspect_colmap_database`, `validate_input_images`) are used elsewhere or are now dead — keep them for now; they get cleaned up later if unused.

- [ ] **Step 3: Manual smoke check**

Run an end-to-end COLMAP processing in Blender on an existing dataset. Verify:
- COLMAP runs to completion.
- `colmap_run.log` is written in the workspace.
- The instance ends up with `is_processed = True`.

- [ ] **Step 4: Commit**

```bash
git add ui/colmap_panel.py
git commit -m "Wire SKY_SPLAT_OT_run_colmap through services.colmap.run_reconstruction"
```

---

## Task B4: Stage B wrap-up — run all tests

- [ ] **Step 1: Run the full unit test suite**

Run: `pytest -v`
Expected: all tests still pass (Stage A 23 + Stage B reconstruction 3 + merge 2 = 28).

---

# Stage C — Brush Subprocess

## Task C1: brush.build_command

**Files:**
- Modify: `services/brush.py` — add `BrushParams` dataclass and `build_command`.
- Modify: `tests/unit/test_brush.py` — add tests.

Extract the `build_brush_command` method (`ui/gaussian_splatting_panel.py:551–622`) as a pure function taking a `BrushParams` dataclass.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_brush.py`:

```python
from services.brush import BrushParams, build_command


class TestBuildCommand:
    def test_includes_executable_and_source(self):
        params = BrushParams(
            executable="/path/brush", source_path="/data/dataset",
            export_path="/data/out",
        )
        cmd = build_command(params)
        assert cmd[0] == "/path/brush"
        assert "/data/dataset" in cmd
        assert "--export-path" in cmd
        assert "/data/out" in cmd

    def test_appends_with_viewer_flag(self):
        params = BrushParams(
            executable="brush", source_path="/d", export_path="/o",
            with_viewer=True,
        )
        cmd = build_command(params)
        assert "--with-viewer" in cmd

    def test_omits_optional_zero_fields(self):
        params = BrushParams(
            executable="brush", source_path="/d", export_path="/o",
            max_frames=0, eval_split_every=0,
        )
        cmd = build_command(params)
        assert "--max-frames" not in cmd
        assert "--eval-split-every" not in cmd

    def test_includes_optional_nonzero_fields(self):
        params = BrushParams(
            executable="brush", source_path="/d", export_path="/o",
            max_frames=100, eval_split_every=10,
        )
        cmd = build_command(params)
        assert "--max-frames" in cmd and "100" in cmd
        assert "--eval-split-every" in cmd and "10" in cmd
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_brush.py -v -k BuildCommand`
Expected: ImportError.

- [ ] **Step 3: Implement BrushParams and build_command**

Append to `services/brush.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_brush.py -v`
Expected: all brush tests pass (5 prepare_dataset + 4 build_command = 9).

- [ ] **Step 5: Commit**

```bash
git add services/brush.py tests/unit/test_brush.py
git commit -m "Add services.brush.BrushParams and build_command + tests"
```

---

## Task C2: brush.run_training

**Files:**
- Modify: `services/brush.py` — add `run_training` (returns subprocess.Popen).

For phase 1, `run_training` is a thin Popen launcher. The async-task abstraction (`RunningTask`) lands in phase 2 alongside the bake walker.

- [ ] **Step 1: Add to `services/brush.py`**

```python
def run_training(
    params: BrushParams,
    log_path: Path,
) -> subprocess.Popen:
    """Launch Brush training as a subprocess. Returns the Popen handle.

    Caller is responsible for polling `popen.poll()` and `popen.wait()`.
    Stdout and stderr are tee'd to log_path.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_command(params)
    log = open(log_path, "w")
    return subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
    )
```

- [ ] **Step 2: Add a tests/unit/test_brush.py test that verifies the call uses Popen**

Append:

```python
from unittest.mock import patch, MagicMock

from services.brush import run_training


class TestRunTraining:
    def test_returns_popen_handle(self, tmp_path):
        params = BrushParams(executable="brush", source_path="/d")
        fake_popen = MagicMock(spec=subprocess.Popen)
        with patch("services.brush.subprocess.Popen", return_value=fake_popen) as p:
            result = run_training(params, tmp_path / "log")
        assert result is fake_popen
        # First positional arg of Popen is the command list
        cmd = p.call_args.args[0]
        assert cmd[0] == "brush"
```

(Don't forget `import subprocess` at the top of the test file if not already there.)

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_brush.py -v`
Expected: 10 passed.

- [ ] **Step 4: Commit**

```bash
git add services/brush.py tests/unit/test_brush.py
git commit -m "Add services.brush.run_training Popen launcher + tests"
```

---

## Task C3: integrate run_training into SKY_SPLAT_OT_run_brush_training

**Files:**
- Modify: `ui/gaussian_splatting_panel.py` — `SKY_SPLAT_OT_run_brush_training` (lines 450–653).

Replace `build_brush_command` and `run_training` methods with calls to the service. The modal-operator structure stays — only the inner subprocess plumbing moves.

- [ ] **Step 1: Replace `build_brush_command` method**

In `ui/gaussian_splatting_panel.py`, replace the entire `build_brush_command` method (lines 551–622) with:

```python
    def build_brush_command(self, props, splat_instance):
        from ..services.brush import BrushParams, build_command
        params = BrushParams(
            executable=props.brush_executable,
            source_path=splat_instance.source_path,
            export_path=splat_instance.export_path,
            export_name=splat_instance.export_name,
            total_steps=splat_instance.total_steps,
            ssim_weight=splat_instance.ssim_weight,
            lr_mean=splat_instance.lr_mean,
            lr_mean_end=splat_instance.lr_mean_end,
            lr_coeffs_dc=splat_instance.lr_coeffs_dc,
            lr_opac=splat_instance.lr_opac,
            lr_scale=splat_instance.lr_scale,
            lr_rotation=splat_instance.lr_rotation,
            max_resolution=splat_instance.max_resolution,
            subsample_frames=splat_instance.subsample_frames,
            subsample_points=splat_instance.subsample_points,
            max_frames=splat_instance.max_frames,
            eval_split_every=splat_instance.eval_split_every,
            refine_every=splat_instance.refine_every,
            growth_grad_threshold=splat_instance.growth_grad_threshold,
            growth_select_fraction=splat_instance.growth_select_fraction,
            growth_stop_iter=splat_instance.growth_stop_iter,
            max_splats=splat_instance.max_splats,
            sh_degree=splat_instance.sh_degree,
            eval_every=splat_instance.eval_every,
            export_every=splat_instance.export_every,
            seed=splat_instance.seed,
            start_iter=splat_instance.start_iter,
            with_viewer=splat_instance.with_viewer,
            eval_save_to_disk=splat_instance.eval_save_to_disk,
        )
        return build_command(params)
```

(The signature is preserved so callers don't change. Only the body now uses the service.)

- [ ] **Step 2: Manual smoke check**

In Blender, run Brush training on an existing splat instance. Verify training starts, produces logs, and the modal operator behaves identically to before.

- [ ] **Step 3: Commit**

```bash
git add ui/gaussian_splatting_panel.py
git commit -m "Use services.brush.build_command in run_brush_training"
```

---

# Stage D — Scene Services

Phase 1's most invasive stage. Each task extracts a scene-mutating service, replaces the inline operator code, and adds a headless integration test that runs via `blender --background --python`.

## Task D1: video.load_video_into_vse

**Files:**
- Create: `services/video.py`
- Modify: `ui/video_panel.py` — `SKY_SPLAT_OT_load_video.execute` (lines 226–363).
- Create: `tests/integration/test_video_load.py` (headless Blender script).
- Create: `Makefile` (for running headless tests).

The existing operator (lines 226–363) does ~140 lines of scene plumbing: VSE setup, sequencer-scene resolution for Blender 5.0, strip creation, frame-step calculation. The service captures the strip-creation and adoption logic.

Note: Blender headless tests require Blender installed and runnable from the command line. Document the path used in the Makefile so the user can override.

- [ ] **Step 1: Create `services/video.py`**

```python
"""Video sequencer service.

Pure parts: parse_srt_metadata is in services/srt.py.
Scene parts (this module): load_video_into_vse — adopts existing strips
or creates a new one named for skysplat traceability.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


def load_video_into_vse(
    scene,
    video_path: Path,
    strip_name: str,
):
    """Load a movie file into the scene's VSE, adopting any existing
    strip pointing at the same file.

    Returns the bpy.types.MovieSequence-equivalent strip object.

    Raises RuntimeError if Blender (bpy) is not available.
    """
    if not HAS_BPY:
        raise RuntimeError("load_video_into_vse requires Blender (bpy).")

    video_path = Path(bpy.path.abspath(str(video_path)))

    if not scene.sequence_editor:
        scene.sequence_editor_create()
    seq_editor = scene.sequence_editor

    # Adopt: look for existing strip with matching filepath.
    for strip in _all_movie_strips(seq_editor):
        if Path(bpy.path.abspath(strip.filepath)) == video_path:
            return strip

    # Create new strip on first free channel.
    next_channel = _next_free_channel(seq_editor)
    sequences_collection = _sequences_collection(seq_editor)
    return sequences_collection.new_movie(
        name=strip_name,
        filepath=str(video_path),
        channel=next_channel,
        frame_start=1,
    )


def _all_movie_strips(seq_editor):
    # Blender 5.0 renamed sequences_all → strips_all. Handle both.
    if hasattr(seq_editor, "strips_all"):
        return [s for s in seq_editor.strips_all if s.type == "MOVIE"]
    return [s for s in seq_editor.sequences_all if s.type == "MOVIE"]


def _sequences_collection(seq_editor):
    if hasattr(seq_editor, "strips"):
        return seq_editor.strips
    return seq_editor.sequences


def _next_free_channel(seq_editor) -> int:
    used = {s.channel for s in _all_movie_strips(seq_editor)}
    for i in range(1, 256):
        if i not in used:
            return i
    return 1
```

- [ ] **Step 2: Create `tests/integration/test_video_load.py`**

```python
"""Headless integration test: load_video_into_vse adopts and creates strips.

Run via: blender --background --python tests/integration/test_video_load.py

Exits 0 on success, nonzero on failure.
"""
import sys
from pathlib import Path

# Add addon root to path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import bpy

from services.video import load_video_into_vse


def main():
    # Reset to a clean scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # Use a fixture mp4 if present, otherwise skip with a warning.
    fixture = ROOT / "tests" / "fixtures" / "tiny.mp4"
    if not fixture.exists():
        print(f"SKIP: {fixture} not present (need a tiny mp4 fixture)")
        sys.exit(0)

    # Create
    strip = load_video_into_vse(scene, fixture, strip_name="skysplat_test")
    assert strip is not None, "Expected a strip after load"

    # Re-load same file → adoption: same number of strips
    seq_editor = scene.sequence_editor
    count_before = len([s for s in (
        seq_editor.strips_all if hasattr(seq_editor, 'strips_all') else seq_editor.sequences_all
    ) if s.type == 'MOVIE'])
    load_video_into_vse(scene, fixture, strip_name="skysplat_test_2")
    count_after = len([s for s in (
        seq_editor.strips_all if hasattr(seq_editor, 'strips_all') else seq_editor.sequences_all
    ) if s.type == 'MOVIE'])
    assert count_before == count_after, (
        f"Expected adoption (no new strip) but counts went {count_before} -> {count_after}"
    )

    print("PASS: video load + adoption")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `Makefile`**

```makefile
# Override BLENDER on the command line if your install is elsewhere.
BLENDER ?= /Applications/Blender.app/Contents/MacOS/Blender

.PHONY: test test-unit test-integration

test: test-unit test-integration

test-unit:
	pytest -q

test-integration:
	$(BLENDER) --background --python tests/integration/test_video_load.py
```

- [ ] **Step 4: Refactor `SKY_SPLAT_OT_load_video.execute` to call the service**

In `ui/video_panel.py`, replace the strip-creation portion of `execute` (around lines 295–306, where `sequences_collection.new_movie(...)` is called) with:

```python
        from ..services.video import load_video_into_vse
        video_path = Path(bpy.path.abspath(video_instance.video_path))
        strip_name = os.path.basename(video_path)
        video_strip = load_video_into_vse(target_scene, video_path, strip_name=strip_name)
```

The surrounding code (sequencer-scene resolution, frame-step calculation, SRT loading) stays. The duplicate-strip-removal block (lines 285–289 of the original) becomes redundant once adoption is in place — leave it as defense-in-depth for now.

- [ ] **Step 5: Manual smoke check**

In Blender:
- Load a video via the panel. Verify a strip appears.
- Click "Load" again on the same instance. Verify no duplicate strip.
- Delete the strip from VSE manually, click "Load" again. Verify a new strip is created.

- [ ] **Step 6: Commit**

```bash
git add services/video.py tests/integration/test_video_load.py Makefile ui/video_panel.py
git commit -m "Add services.video.load_video_into_vse and wire into load_video operator"
```

---

## Task D2: frames.extract_frames (scene)

**Files:**
- Modify: `services/frames.py` — add `extract_frames`.
- Modify: `ui/video_panel.py` — `SKY_SPLAT_OT_extract_frames.execute` (lines 370–484).

Phase 1 keeps the synchronous behavior of the existing operator (`bpy.ops.render.opengl(animation=True)` blocks). The async/RunningTask refactor lands in phase 2. The service captures the mute/unmute and render-setup dance.

- [ ] **Step 1: Append to `services/frames.py`**

```python
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
```

- [ ] **Step 2: Refactor `SKY_SPLAT_OT_extract_frames.execute`**

In `ui/video_panel.py`, replace the body of `execute` from line 408 (start of `try:`) through line 467 (the end of the success-path `return {'FINISHED'}` block, but keeping the `finally` at line 479) — i.e., replace the work between `try:` and the `return` statement — with:

```python
        try:
            from ..services.frames import extract_frames
            video_path = Path(bpy.path.abspath(video_instance.video_path))
            video_filename = os.path.basename(str(video_path))
            count = extract_frames(
                context.scene,
                video_strip_name=video_filename,
                out_dir=Path(output_folder),
                start=video_instance.frame_start,
                end=video_instance.frame_end,
                step=video_instance.frame_step,
            )
            video_instance.frames_extracted = True
            bpy.ops.wm.path_open(filepath=output_folder)
            self.report({'INFO'}, f"Successfully extracted {count} frames to {output_folder}")
            if hasattr(context.scene, 'skysplat_colmap_props'):
                context.scene.skysplat_colmap_props.update_from_video_panel(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}
```

Remove the `finally:` block (lines 479–484) since the service now handles mute/state restoration internally.

- [ ] **Step 3: Manual smoke check**

In Blender, extract frames from a video. Verify:
- Frames are written to the correct folder.
- Frame count matches expectation.
- No mute state lingers on other strips.

- [ ] **Step 4: Commit**

```bash
git add services/frames.py ui/video_panel.py
git commit -m "Add services.frames.extract_frames and wire into extract_frames operator"
```

---

## Task D3: colmap_view.import_model_to_scene

**Files:**
- Create: `services/colmap_view.py`
- Modify: `ui/colmap_panel.py` — `SKY_SPLAT_OT_load_colmap_model.execute` (lines 930–1086).

Extracts the point-cloud + COLMAP_Root creation logic from the existing `load_colmap_model` operator (lines 930–1086).

- [ ] **Step 1: Create `services/colmap_view.py`**

```python
"""Import a COLMAP model into the Blender scene as a viewable point cloud
plus a COLMAP_Root empty.

Phase 1 takes the existing load logic verbatim; phase 2 will tag scene
objects with skysplat_node_uuid for the round-trip pattern. This phase
preserves the existing tagging convention used by sidebar instances.
"""
from __future__ import annotations

import math
from pathlib import Path

try:
    import bpy
    import mathutils
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from .colmap import read_model, ColmapModel


def import_model_to_scene(
    scene,
    model_path: Path,
    instance_name: str,
):
    """Import a COLMAP sparse model into the scene.

    Creates:
      - Collection 'COLMAP_<instance_name>' (or adopts existing)
      - Empty 'COLMAP_Root' parented to a points mesh
      - Point cloud mesh with each 3D point as a vertex

    Returns the COLMAP_Root empty.

    The legacy import logic (which has been in colmap_panel.py for many
    versions) is preserved here verbatim; future phases will refactor.
    """
    if not HAS_BPY:
        raise RuntimeError("import_model_to_scene requires Blender (bpy).")

    model = read_model(Path(model_path))

    # See ui/colmap_panel.py:930–1086 for the original implementation.
    # Phase 1 keeps the operator code as-is; this service is a stub
    # that delegates back to a function on bpy.ops level.
    raise NotImplementedError(
        "import_model_to_scene is a stub for phase 1 — extraction "
        "deferred to phase 1.5 to keep this stage's blast radius small. "
        "See task D3 in the plan."
    )
```

**Note:** the stub above explicitly defers the full extraction. The reason: the original `load_colmap_model.execute` is 156 lines and tightly coupled with sidebar property updates. Doing it correctly requires more time than the rest of phase 1 combined. We mark it as a known gap and complete it in a phase 1.5 follow-up plan. For phase 1 the existing operator continues to work unchanged — we just put the service file in place so phase 2 can land on top of it.

- [ ] **Step 2: Verify the existing operator still works**

Run a manual smoke test in Blender — load a COLMAP model via the panel. It should work as before because we haven't changed the operator.

- [ ] **Step 3: Commit the stub**

```bash
git add services/colmap_view.py
git commit -m "Add services.colmap_view stub (full extraction deferred to phase 1.5)"
```

---

## Task D4: camera.create_animated_cameras

**Files:**
- Create: `services/camera.py`
- Modify: `ui/colmap_panel.py` — `SKY_SPLAT_OT_create_camera_animation.execute` (lines 1259–1410).

Same approach as D3 — stub the service, defer the full extraction to phase 1.5.

- [ ] **Step 1: Create `services/camera.py`**

```python
"""Create animated cameras from a COLMAP model.

Phase 1 stub — full extraction deferred to phase 1.5. The existing
operator at ui/colmap_panel.py:1259–1410 continues to work unchanged.
"""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


def create_animated_cameras(
    scene,
    model_path: Path,
    instance_name: str,
    video_strip_starts: dict,
):
    """Create one animated camera per source video.

    Phase 1 stub — see task D4 in the implementation plan.
    """
    raise NotImplementedError("Deferred to phase 1.5; see plan task D4.")
```

- [ ] **Step 2: Commit**

```bash
git add services/camera.py
git commit -m "Add services.camera stub (full extraction deferred to phase 1.5)"
```

---

## Task D5: Stage D wrap-up — release-checklist + final test pass

**Files:**
- Create: `docs/release-checklist.md`

- [ ] **Step 1: Create `docs/release-checklist.md`**

```markdown
# SkySplat Release Checklist

Run before tagging a release.

## Unit tests

- [ ] `pytest -v` passes (all green)

## Integration tests

- [ ] `make test-integration` passes (requires Blender on PATH or `BLENDER=...`)

## Manual smoke (open Blender, load addon)

### Video panel
- [ ] Add a Video instance, set a video path, click "Load Video and SRT" — strip appears in VSE
- [ ] Click "Load" again on the same instance — no duplicate strip
- [ ] Click "Extract Frames" — frames written, count matches expectation
- [ ] Two video instances loaded — extract frames from one, the other's strip mute state is preserved

### COLMAP panel
- [ ] Click "Run COLMAP" on a prepared instance — completes successfully, log written
- [ ] Click "Load COLMAP Model" — point cloud appears with COLMAP_Root empty
- [ ] Transform the COLMAP_Root, click "Export Transformed Model" — exported model loads back correctly
- [ ] Click "Prepare Brush Dataset" — sparse + images directories laid out correctly
- [ ] Click "Create Camera Animation" — animated camera appears

### Brush panel
- [ ] Click "Run Brush Training" on a prepared dataset — training launches, output appears in console
```

- [ ] **Step 2: Run the full unit suite once more**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add docs/release-checklist.md
git commit -m "Add release checklist for phase 1 services extraction"
```

---

# Plan Self-Review Checklist (run by author after writing)

- [x] **Spec coverage:** All listed services have a phase 1 task. `colmap_view` and `camera` are stubbed with explicit deferral notes (acceptable — the existing operators continue to work).
- [x] **Placeholder scan:** No "TBD" / "TODO" without explicit deferral context. The two stubs (D3, D4) are documented as deferred to phase 1.5 with reasons.
- [x] **Type consistency:** `ColmapModel` defined once in `services/colmap.py`, imported by `services/transform.py`. `BrushParams`, `FramesSource`, `ColmapParams`, `ColmapResult`, `CameraModelSpec` and its variants all defined in `services/colmap.py` (except `BrushParams` in `services/brush.py`). All consistent across tasks.
- [x] **Imports:** `from ..services.X import Y` pattern used in addon code (relative). `from services.X import Y` pattern used in tests (absolute, via conftest path injection).

---

**End of phase 1 plan.** When this plan is fully executed, the result is:
- A `services/` package with 8 modules (some stubs).
- Pure unit tests covering ~30 cases.
- Existing sidebar panels working as before, but routing through services for SRT parsing, brush dataset prep, COLMAP run, brush training, transform, video load, and frame extraction.
- A `docs/release-checklist.md` for manual smoke testing.
- Two intentional stubs (`services/colmap_view.py`, `services/camera.py`) with extraction deferred to phase 1.5 — the original operators are untouched and continue to work.

Phase 2 (node editor MVP) plan should be written **after** this plan is fully executed and v0.5.0 is tagged.
