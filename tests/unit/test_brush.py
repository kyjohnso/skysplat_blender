"""Tests for services/brush.py — Brush dataset preparation."""
from pathlib import Path
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from services.brush import prepare_dataset, run_training
from services.errors import BrushError


def _write_sparse_model(sparse_dir: Path):
    sparse_dir.mkdir(parents=True, exist_ok=True)
    (sparse_dir / "cameras.bin").write_bytes(b"\x00")
    (sparse_dir / "images.bin").write_bytes(b"\x00")
    (sparse_dir / "points3D.bin").write_bytes(b"\x00")


def _write_images(images_dir: Path, count: int = 3):
    images_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (images_dir / f"frame_{i:03d}.png").write_bytes(b"\x89PNG\r\n")
    (images_dir / "notes.txt").write_text("ignored")


class TestPrepareDataset:
    def test_creates_target_layout(self, tmp_path):
        sparse = tmp_path / "in_sparse"
        images = tmp_path / "in_images"
        out = tmp_path / "out"
        _write_sparse_model(sparse)
        _write_images(images)

        result = prepare_dataset(sparse, images, out)

        assert result == out
        assert (out / "sparse" / "0" / "cameras.bin").exists()
        assert (out / "sparse" / "0" / "images.bin").exists()
        assert (out / "sparse" / "0" / "points3D.bin").exists()
        # images directory exists (either symlink or copy)
        assert (out / "images").exists()

    def test_copies_images_when_force_copy(self, tmp_path):
        sparse = tmp_path / "in_sparse"
        images = tmp_path / "in_images"
        out = tmp_path / "out"
        _write_sparse_model(sparse)
        _write_images(images)

        prepare_dataset(sparse, images, out, force_copy=True)

        # All png files copied, txt files filtered
        copied = sorted((out / "images").glob("*.png"))
        assert len(copied) == 3
        assert not (out / "images" / "notes.txt").exists()

    def test_falls_back_to_txt_files_for_sparse(self, tmp_path):
        sparse = tmp_path / "in_sparse"
        sparse.mkdir(parents=True)
        # Only .txt versions present
        (sparse / "cameras.txt").write_text("# comment")
        (sparse / "images.txt").write_text("# comment")
        (sparse / "points3D.txt").write_text("# comment")
        images = tmp_path / "in_images"
        _write_images(images, 1)
        out = tmp_path / "out"

        prepare_dataset(sparse, images, out, force_copy=True)

        assert (out / "sparse" / "0" / "cameras.txt").exists()

    def test_raises_when_sparse_missing(self, tmp_path):
        with pytest.raises(BrushError):
            prepare_dataset(
                tmp_path / "missing", tmp_path / "imgs", tmp_path / "out"
            )

    def test_raises_when_images_missing(self, tmp_path):
        sparse = tmp_path / "sparse"
        _write_sparse_model(sparse)
        with pytest.raises(BrushError):
            prepare_dataset(sparse, tmp_path / "missing", tmp_path / "out")


from services.brush import BrushParams, build_command


class TestBuildCommand:
    def test_includes_executable_and_source(self):
        params = BrushParams(
            executable="/path/brush", source_path="/data/dataset",
            export_path="/data/out",
        )
        cmd = build_command(params)
        assert cmd[0] == "/path/brush"
        assert "/data/dataset" in cmd
        assert "--export-path" in cmd
        assert "/data/out" in cmd

    def test_appends_with_viewer_flag(self):
        params = BrushParams(
            executable="brush", source_path="/d", export_path="/o",
            with_viewer=True,
        )
        cmd = build_command(params)
        assert "--with-viewer" in cmd

    def test_omits_optional_zero_fields(self):
        params = BrushParams(
            executable="brush", source_path="/d", export_path="/o",
            max_frames=0, eval_split_every=0,
        )
        cmd = build_command(params)
        assert "--max-frames" not in cmd
        assert "--eval-split-every" not in cmd

    def test_includes_optional_nonzero_fields(self):
        params = BrushParams(
            executable="brush", source_path="/d", export_path="/o",
            max_frames=100, eval_split_every=10,
        )
        cmd = build_command(params)
        assert "--max-frames" in cmd and "100" in cmd
        assert "--eval-split-every" in cmd and "10" in cmd

    def test_emits_scale_end_as_valid_decay(self):
        # Brush panics if the scale LR schedule increases (end > start), so we
        # must always emit --lr-scale-end and keep it <= --lr-scale.
        params = BrushParams(executable="brush", source_path="/d", export_path="/o")
        cmd = build_command(params)
        assert "--lr-scale" in cmd and "--lr-scale-end" in cmd
        start = float(cmd[cmd.index("--lr-scale") + 1])
        end = float(cmd[cmd.index("--lr-scale-end") + 1])
        assert 0 < end <= start


class TestRunTraining:
    def test_returns_popen_handle(self, tmp_path):
        params = BrushParams(executable="brush", source_path="/d")
        fake_popen = MagicMock(spec=subprocess.Popen)
        with patch("services.brush.subprocess.Popen", return_value=fake_popen) as p:
            result = run_training(params, tmp_path / "log")
        assert result is fake_popen
        # First positional arg of Popen is the command list
        cmd = p.call_args.args[0]
        assert cmd[0] == "brush"
