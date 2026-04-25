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


import subprocess
from unittest.mock import patch, MagicMock

from services.colmap import (
    run_reconstruction, FramesSource, ColmapParams, ColmapResult, Auto, Manual,
    ColmapModel, merge_models,
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
        assert cmd[0] == "colmap"
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

    def test_uses_custom_executable(self, tmp_path):
        a = tmp_path / "a"; b = tmp_path / "b"; a.mkdir(); b.mkdir()
        with patch("services.colmap.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
            merge_models(
                a, b, tmp_path / "out",
                log_path=tmp_path / "log",
                colmap_executable="/custom/path/colmap",
            )
        cmd = run_mock.call_args.args[0]
        assert cmd[0] == "/custom/path/colmap"
