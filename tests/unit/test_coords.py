"""Tests for services/coords.py — the canonical COLMAP<->Blender convention."""
import math

import numpy as np
import mathutils
from mathutils import Matrix, Quaternion, Vector

from services.coords import (
    COLMAP_CAM_TO_BLENDER_CAM,
    SENSOR_WIDTH_MM,
    pose_to_blender_matrix,
    blender_matrix_to_pose,
    export_world_transform,
    focal_px_to_mm,
    focal_mm_to_px,
    continuous_quaternions,
)
from utils.read_write_model import qvec2rotmat


def _random_pose(seed):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    if q[0] < 0:
        q = -q  # canonical hemisphere (rotmat2qvec returns w >= 0)
    t = rng.normal(size=3)
    return q, t


class TestFlipConstant:
    def test_matches_both_historical_signs(self):
        # The sidebar used Rotation(pi,'X') on load and Rotation(-pi,'X') on
        # export. Both are the same matrix — the single constant serves both.
        # (atol: mathutils is float32, so its sin(pi) is ~9e-8, not 0.)
        pos = mathutils.Matrix.Rotation(math.pi, 4, 'X')
        neg = mathutils.Matrix.Rotation(-math.pi, 4, 'X')
        assert np.allclose(np.array(COLMAP_CAM_TO_BLENDER_CAM), np.array(pos), atol=1e-6)
        assert np.allclose(np.array(COLMAP_CAM_TO_BLENDER_CAM), np.array(neg), atol=1e-6)

    def test_is_its_own_inverse(self):
        double = COLMAP_CAM_TO_BLENDER_CAM @ COLMAP_CAM_TO_BLENDER_CAM
        assert np.allclose(np.array(double), np.eye(4))


class TestPoseToBlenderMatrix:
    def test_matches_sidebar_load_computation(self):
        # Reproduce ui/colmap_panel.py's historical per-camera math verbatim
        # and check the helper agrees.
        q, t = _random_pose(7)
        R = np.array(qvec2rotmat(q))
        cam_center = -R.T @ t
        R_cam_to_world = R.T
        rotation_matrix = mathutils.Matrix((
            (R_cam_to_world[0][0], R_cam_to_world[0][1], R_cam_to_world[0][2]),
            (R_cam_to_world[1][0], R_cam_to_world[1][1], R_cam_to_world[1][2]),
            (R_cam_to_world[2][0], R_cam_to_world[2][1], R_cam_to_world[2][2]),
        )).to_4x4()
        rotation_matrix.translation = Vector(cam_center)
        expected = rotation_matrix @ mathutils.Matrix.Rotation(math.pi, 4, 'X')

        got = pose_to_blender_matrix(q, t)
        assert np.allclose(np.array(got), np.array(expected), atol=1e-9)

    def test_identity_pose_camera_at_origin_looking_down_minus_z_colmap(self):
        # Identity COLMAP pose: camera at origin looking down +Z (COLMAP).
        # In Blender terms the camera's -Z view axis must map onto world +Z.
        m = pose_to_blender_matrix(np.array([1.0, 0, 0, 0]), np.zeros(3))
        view_dir = np.array(m)[:3, :3] @ np.array([0.0, 0.0, -1.0])
        assert np.allclose(view_dir, [0.0, 0.0, 1.0])
        assert np.allclose(np.array(m)[:3, 3], 0.0)

    def test_roundtrip_through_blender_matrix(self):
        for seed in range(5):
            q, t = _random_pose(seed)
            q2, t2 = blender_matrix_to_pose(pose_to_blender_matrix(q, t))
            assert np.allclose(q2, q, atol=1e-6)
            assert np.allclose(t2, t, atol=1e-6)


class TestExportWorldTransform:
    def test_matches_sidebar_export_computation(self):
        root = Matrix.Translation((2.0, -1.0, 0.5)) @ Matrix.Rotation(0.7, 4, 'Z')
        expected = root @ mathutils.Matrix.Rotation(-math.pi, 4, 'X')
        got = export_world_transform(root)
        assert np.allclose(np.array(got), np.array(expected), atol=1e-6)

    def test_identity_root_reduces_to_flip(self):
        got = export_world_transform(Matrix.Identity(4))
        assert np.allclose(np.array(got), np.array(COLMAP_CAM_TO_BLENDER_CAM))


class TestFocalHelpers:
    def test_px_to_mm_matches_sidebar_formula(self):
        # sidebar: focal_mm = params[0] * 36.0 / width
        assert focal_px_to_mm(1000.0, 1920) == 1000.0 * 36.0 / 1920
        assert SENSOR_WIDTH_MM == 36.0

    def test_roundtrip(self):
        assert math.isclose(focal_mm_to_px(focal_px_to_mm(1234.5, 4032), 4032), 1234.5)


class TestContinuousQuaternions:
    def test_flips_hemisphere_jumps(self):
        q = Quaternion((1.0, 0.0, 0.0, 0.0))
        seq = [q, -q, q.copy()]
        out = continuous_quaternions(seq)
        for prev, cur in zip(out, out[1:]):
            assert prev.dot(cur) >= 0

    def test_preserves_rotations(self):
        rng = np.random.default_rng(3)
        seq = []
        for _ in range(10):
            v = rng.normal(size=4)
            v /= np.linalg.norm(v)
            seq.append(Quaternion(v))
        out = continuous_quaternions(seq)
        for a, b in zip(seq, out):
            # same rotation: matrices equal even when sign flipped
            assert np.allclose(np.array(a.to_matrix()), np.array(b.to_matrix()), atol=1e-9)

    def test_does_not_mutate_input(self):
        q = Quaternion((0.5, 0.5, 0.5, 0.5))
        seq = [q, -q]
        continuous_quaternions(seq)
        assert seq[1] == -q
