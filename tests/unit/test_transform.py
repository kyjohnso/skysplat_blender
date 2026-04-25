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


import math


class TestApplyTransformRotation:
    def test_rotation_preserves_camera_observation(self):
        """If we transform the world by R, the camera-image relationship
        should be invariant — the same world point should still project
        to the same image pixel through the new camera pose.
        """
        from utils.read_write_model import qvec2rotmat
        # Build a non-identity initial camera pose.
        # Place camera at world (5, 0, 0), looking back at origin → -X direction.
        # Camera-to-world basis: x_axis points up (+Z), y_axis points -Y, z_axis points -X
        # In world frame with camera at (5,0,0) looking toward origin:
        #   R_cw = [[ 0, 0, -1], [-1, 0,  0], [ 0, 1,  0]]
        # ... we can simplify: use a quaternion for 90° rotation about Z and offset translation.
        # For a clean test, just use a quaternion and tvec that work in COLMAP convention.
        s = 1.0 / math.sqrt(2)
        qw, qx, qy, qz = s, 0, s, 0  # 90° about Y
        cameras = {1: Camera(id=1, model="SIMPLE_PINHOLE", width=640, height=480, params=[500.0, 320.0, 240.0])}
        images = {
            10: Image(
                id=10,
                qvec=np.array([qw, qx, qy, qz]),
                tvec=np.array([0.5, 1.0, 2.0]),
                camera_id=1,
                name="frame_001.png",
                xys=np.zeros((0, 2)),
                point3D_ids=np.zeros(0, dtype=int),
            )
        }
        # Pick a world point and verify its image-frame coordinates are
        # unchanged under the world transform.
        P_world = np.array([1.5, -0.5, 0.7])

        # Original camera-frame projection
        R_wc = qvec2rotmat(images[10].qvec)
        P_cam_original = R_wc @ P_world + images[10].tvec

        # Apply a non-trivial world transform: rotate world 60° about Z, translate (2, -1, 0.5)
        rot = Matrix.Rotation(math.pi / 3, 4, 'Z')
        trans = Matrix.Translation((2.0, -1.0, 0.5))
        world_xform = trans @ rot

        model = ColmapModel(cameras=cameras, images=dict(images), points3D={})
        out = apply_transform(model, world_xform)

        # Compute new world position of P_world
        P_world_new = np.array(world_xform) @ np.append(P_world, 1.0)
        P_world_new = P_world_new[:3]

        # New camera-frame projection
        R_wc_new = qvec2rotmat(out.images[10].qvec)
        P_cam_new = R_wc_new @ P_world_new + out.images[10].tvec

        # The same physical observation: P_cam should be invariant.
        assert np.allclose(P_cam_new, P_cam_original, atol=1e-5), (
            f"Camera observation changed under world transform.\n"
            f"  Original P_cam: {P_cam_original}\n"
            f"  New P_cam:      {P_cam_new}"
        )
