"""Build keyframed-camera animation specs from a COLMAP model.

Pure module (numpy + mathutils, no bpy): the COLMAP Cameras node and the
sidebar turn the returned specs into actual Blender camera objects and
keyframes. Keeping the math here makes it testable and guarantees the
node and sidebar agree.

Multi-video: with frames staged per-video (Merge Frames node +
--ImageReader.single_camera_per_folder), frame numbers collide across
videos and poses interleave, so a single animated camera is wrong. Images
are grouped by COLMAP camera_id — which per_folder staging makes exactly
one-per-video — yielding one CameraAnimation (one Blender camera) per
source video. A flat single-video model degenerates to one group.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .colmap import ColmapModel
from .coords import continuous_quaternions, focal_px_to_mm, pose_to_blender_matrix


@dataclass
class CameraKey:
    frame: int
    location: tuple  # (x, y, z) Blender world
    quaternion: tuple  # (w, x, y, z), hemisphere-continuous within its animation


@dataclass
class CameraAnimation:
    source_id: str        # subfolder name for merged runs, else a camera label
    camera_id: int
    width: int
    height: int
    focal_mm: float | None
    keys: list  # list[CameraKey], sorted by frame


def parse_frame_number(image_name: str) -> int | None:
    """Frame number from a COLMAP image name, ignoring any subfolder prefix
    ('vid_a/frame_0042.png' -> 42). Falls back to the last >=4 digit run for
    names that don't follow the frame_ pattern."""
    base = PurePosixPath(image_name.replace("\\", "/")).name
    m = re.search(r"frame[_-]?(\d+)", base, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{4,})(?!.*\d{4,})", base)
    if m:
        return int(m.group(1))
    return None


def _source_label(image_name: str, camera_id: int) -> str:
    """Group label: the subfolder for merged multi-video layouts, else a
    camera-derived name for flat layouts."""
    parent = PurePosixPath(image_name.replace("\\", "/")).parent.name
    return parent if parent else f"camera_{camera_id}"


def build_camera_animations(model: ColmapModel) -> list:
    """Group a model's images into per-source camera animations.

    Returns a list[CameraAnimation] sorted by source_id. Keys are sorted by
    frame number (parsed from image names; if any name in a group doesn't
    parse, the whole group falls back to 1-based name-sorted order so frames
    stay consistent) with quaternion continuity applied per group.
    """
    groups: dict[int, list] = {}
    for image in model.images.values():
        groups.setdefault(image.camera_id, []).append(image)

    animations = []
    for camera_id, images in groups.items():
        images = sorted(images, key=lambda im: im.name)
        parsed = [parse_frame_number(im.name) for im in images]
        if any(p is None for p in parsed) or len(set(parsed)) != len(parsed):
            # Unparseable or colliding numbers: keep name order, renumber.
            parsed = list(range(1, len(images) + 1))

        cam = model.cameras.get(camera_id)
        focal_mm = None
        width = height = 0
        if cam is not None:
            width, height = cam.width, cam.height
            if getattr(cam, "params", None) is not None and len(cam.params) > 0:
                focal_mm = focal_px_to_mm(cam.params[0], cam.width)

        pairs = sorted(zip(parsed, images), key=lambda p: p[0])
        mats = [pose_to_blender_matrix(im.qvec, im.tvec) for _, im in pairs]
        locs = [m.to_translation() for m in mats]
        quats = continuous_quaternions([m.to_quaternion() for m in mats])

        keys = [
            CameraKey(frame=f, location=tuple(loc), quaternion=tuple(q))
            for (f, _), loc, q in zip(pairs, locs, quats)
        ]
        animations.append(CameraAnimation(
            source_id=_source_label(images[0].name, camera_id),
            camera_id=camera_id,
            width=width,
            height=height,
            focal_mm=focal_mm,
            keys=keys,
        ))

    animations.sort(key=lambda a: a.source_id)
    return animations
