"""Canonical COLMAP <-> Blender coordinate convention.

The whole addon's alignment story hinges on ONE constant: a 180° rotation
about X (diag(1,-1,-1)). COLMAP cameras look down +Z with +Y down; Blender
cameras look down -Z with +Y up. Historically this flip lived in two places
in ui/colmap_panel.py with opposite-signed angles (Rotation(pi,'X') on
camera load, Rotation(-pi,'X') on export) — which LOOK like different
conventions but are numerically the same matrix, since cos(±pi) = -1 and
sin(±pi) = ∓0. Centralizing it here keeps splat, exported model, and
keyframed cameras in one agreed frame; a sign drift between those sites is
the classic "cameras don't line up with the splat" bug.

Pure module: numpy + mathutils (both pip-installable). No bpy.
"""
from __future__ import annotations

import numpy as np
from mathutils import Matrix, Quaternion

# Dual-import: relative works in Blender, absolute works under pytest.
try:
    from ..utils.read_write_model import qvec2rotmat, rotmat2qvec
except ImportError:
    from utils.read_write_model import qvec2rotmat, rotmat2qvec


# 180° about X. Its own inverse. Applied CAMERA-LOCAL (right-multiplied) to
# turn a COLMAP camera-to-world matrix into a Blender camera matrix_world,
# and composed into the world transform on export to undo it.
COLMAP_CAM_TO_BLENDER_CAM = Matrix((
    (1.0,  0.0,  0.0, 0.0),
    (0.0, -1.0,  0.0, 0.0),
    (0.0,  0.0, -1.0, 0.0),
    (0.0,  0.0,  0.0, 1.0),
))

# The sidebar has always assumed a full-frame sensor when converting
# COLMAP's pixel focal lengths to Blender millimeters.
SENSOR_WIDTH_MM = 36.0


def pose_to_blender_matrix(qvec, tvec) -> Matrix:
    """COLMAP image pose (world->camera qvec/tvec) -> Blender matrix_world.

    Inverts the pose to camera-to-world (C = -R^T t, R_c2w = R^T), then
    applies the camera-local axis flip.
    """
    R = np.asarray(qvec2rotmat(qvec), dtype=float)
    t = np.asarray(tvec, dtype=float)
    C = -R.T @ t
    m = Matrix((
        (R[0][0], R[1][0], R[2][0], C[0]),
        (R[0][1], R[1][1], R[2][1], C[1]),
        (R[0][2], R[1][2], R[2][2], C[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return m @ COLMAP_CAM_TO_BLENDER_CAM


def blender_matrix_to_pose(matrix_world: Matrix):
    """Inverse of pose_to_blender_matrix: Blender camera matrix_world ->
    COLMAP world->camera (qvec, tvec) as numpy arrays."""
    m = np.array(matrix_world @ COLMAP_CAM_TO_BLENDER_CAM)
    R_c2w = m[:3, :3]
    C = m[:3, 3]
    R = R_c2w.T
    t = -R @ C
    return rotmat2qvec(R), t


def export_world_transform(root_matrix_world: Matrix) -> Matrix:
    """World transform to bake into a model on export, given the user's
    alignment root empty. Composes the root's matrix with the inverse of
    the camera axis flip applied at load (the flip is its own inverse)."""
    return root_matrix_world @ COLMAP_CAM_TO_BLENDER_CAM


def focal_px_to_mm(focal_px: float, image_width_px: int,
                   sensor_width_mm: float = SENSOR_WIDTH_MM) -> float:
    """COLMAP pixel focal length -> Blender lens millimeters."""
    return focal_px * sensor_width_mm / float(image_width_px)


def focal_mm_to_px(focal_mm: float, image_width_px: int,
                   sensor_width_mm: float = SENSOR_WIDTH_MM) -> float:
    """Blender lens millimeters -> COLMAP pixel focal length."""
    return focal_mm * float(image_width_px) / sensor_width_mm


def continuous_quaternions(quaternions) -> list:
    """Return quaternions flipped into a consistent hemisphere for smooth
    keyframe interpolation: q and -q are the same rotation, so pick the
    sign closest to the previous sample (dot < 0 -> negate)."""
    out: list = []
    for q in quaternions:
        q = Quaternion(q)
        if out and out[-1].dot(q) < 0:
            q = -q
        out.append(q)
    return out
