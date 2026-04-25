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
