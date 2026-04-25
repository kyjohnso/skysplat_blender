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
