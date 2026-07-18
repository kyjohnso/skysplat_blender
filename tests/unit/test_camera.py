"""Tests for services/camera.py — per-source keyframed camera animations."""
import numpy as np

from services.camera import (
    CameraAnimation, build_camera_animations, parse_frame_number,
)
from services.colmap import ColmapModel
from services.coords import pose_to_blender_matrix
from utils.read_write_model import Camera, Image


def _image(iid, name, camera_id, qvec=(1.0, 0, 0, 0), tvec=(0, 0, 0)):
    return Image(
        id=iid,
        qvec=np.array(qvec, dtype=float),
        tvec=np.array(tvec, dtype=float),
        camera_id=camera_id,
        name=name,
        xys=np.zeros((0, 2)),
        point3D_ids=np.zeros(0, dtype=int),
    )


def _camera(cid, width=1920, height=1080, focal=1000.0):
    return Camera(id=cid, model="SIMPLE_PINHOLE", width=width, height=height,
                  params=[focal, width / 2, height / 2])


class TestParseFrameNumber:
    def test_flat_frame_names(self):
        assert parse_frame_number("frame_0042.png") == 42
        assert parse_frame_number("Frame-007.png") == 7

    def test_subfolder_prefix_is_ignored(self):
        # merged multi-video layout: vid subfolder may itself contain digits
        assert parse_frame_number("vid_0002/frame_0042.png") == 42
        assert parse_frame_number("DJI_0123/frame_0001.png") == 1

    def test_bare_number_fallback(self):
        assert parse_frame_number("IMG_20240101_0042.png") == 42
        assert parse_frame_number("0042.png") == 42

    def test_unparseable_returns_none(self):
        assert parse_frame_number("hero_shot.png") is None


class TestBuildCameraAnimations:
    def _multi_video_model(self):
        cameras = {1: _camera(1, width=1920), 2: _camera(2, width=3840, focal=2000.0)}
        images = {
            1: _image(1, "vid_a/frame_0001.png", 1, tvec=(0, 0, 1)),
            2: _image(2, "vid_a/frame_0006.png", 1, tvec=(0, 0, 2)),
            3: _image(3, "vid_b/frame_0001.png", 2, tvec=(5, 0, 1)),
            4: _image(4, "vid_b/frame_0011.png", 2, tvec=(5, 0, 2)),
        }
        return ColmapModel(cameras=cameras, images=images, points3D={})

    def test_one_animation_per_camera_id(self):
        anims = build_camera_animations(self._multi_video_model())
        assert len(anims) == 2
        assert [a.source_id for a in anims] == ["vid_a", "vid_b"]
        assert all(isinstance(a, CameraAnimation) for a in anims)
        assert [len(a.keys) for a in anims] == [2, 2]

    def test_colliding_frame_numbers_across_videos_are_fine(self):
        # both videos have a frame_0001 — separate cameras, no clash
        anims = build_camera_animations(self._multi_video_model())
        assert anims[0].keys[0].frame == 1
        assert anims[1].keys[0].frame == 1

    def test_intrinsics_per_source(self):
        anims = build_camera_animations(self._multi_video_model())
        a, b = anims
        assert (a.width, a.height) == (1920, 1080)
        assert b.width == 3840
        assert np.isclose(a.focal_mm, 1000.0 * 36.0 / 1920)
        assert np.isclose(b.focal_mm, 2000.0 * 36.0 / 3840)

    def test_poses_match_shared_convention(self):
        model = self._multi_video_model()
        anims = build_camera_animations(model)
        key = anims[0].keys[0]
        expected = pose_to_blender_matrix(
            model.images[1].qvec, model.images[1].tvec)
        assert np.allclose(key.location, tuple(expected.to_translation()), atol=1e-6)
        got_q = np.array(key.quaternion)
        exp_q = np.array(expected.to_quaternion())
        # same rotation regardless of hemisphere
        assert np.isclose(abs(np.dot(got_q, exp_q)), 1.0, atol=1e-6)

    def test_flat_single_video_model(self):
        cameras = {1: _camera(1)}
        images = {
            1: _image(1, "frame_0005.png", 1),
            2: _image(2, "frame_0001.png", 1),
        }
        anims = build_camera_animations(ColmapModel(cameras=cameras, images=images, points3D={}))
        assert len(anims) == 1
        assert anims[0].source_id == "camera_1"
        # keys sorted by parsed frame number, not insertion or name order
        assert [k.frame for k in anims[0].keys] == [1, 5]

    def test_unparseable_names_fall_back_to_name_order(self):
        cameras = {1: _camera(1)}
        images = {
            1: _image(1, "clip/b_shot.png", 1),
            2: _image(2, "clip/a_shot.png", 1),
        }
        anims = build_camera_animations(ColmapModel(cameras=cameras, images=images, points3D={}))
        assert [k.frame for k in anims[0].keys] == [1, 2]

    def test_quaternion_continuity_within_group(self):
        # two nearly-identical rotations expressed in opposite hemispheres
        q = np.array([0.9, 0.1, 0.2, 0.3])
        q /= np.linalg.norm(q)
        cameras = {1: _camera(1)}
        images = {
            1: _image(1, "frame_0001.png", 1, qvec=tuple(q)),
            2: _image(2, "frame_0002.png", 1, qvec=tuple(-q)),
        }
        anims = build_camera_animations(ColmapModel(cameras=cameras, images=images, points3D={}))
        k0, k1 = anims[0].keys
        assert np.dot(k0.quaternion, k1.quaternion) >= 0
