"""Tests for the pure part of services/colmap_view.py."""
import numpy as np

from services.colmap_view import point_cloud_data
from utils.read_write_model import Point3D


def _point(pid, xyz, rgb):
    return Point3D(
        id=pid,
        xyz=np.array(xyz, dtype=float),
        rgb=np.array(rgb, dtype=int),
        error=0.0,
        image_ids=np.zeros(0, dtype=int),
        point2D_idxs=np.zeros(0, dtype=int),
    )


def test_point_cloud_data_verts_and_colors():
    points = {
        1: _point(1, [1.0, 2.0, 3.0], [255, 0, 0]),
        2: _point(2, [-4.0, 0.5, 0.0], [0, 127, 255]),
    }
    verts, colors = point_cloud_data(points)
    assert verts == [(1.0, 2.0, 3.0), (-4.0, 0.5, 0.0)]
    assert colors[0] == (1.0, 0.0, 0.0, 1.0)
    assert colors[1][2] == 1.0
    assert abs(colors[1][1] - 127 / 255.0) < 1e-9
    assert all(len(c) == 4 and c[3] == 1.0 for c in colors)


def test_point_cloud_data_empty():
    assert point_cloud_data({}) == ([], [])
