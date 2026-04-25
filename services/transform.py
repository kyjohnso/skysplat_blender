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
