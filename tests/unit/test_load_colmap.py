"""Tests for the Load COLMAP node's pure helpers."""
from pathlib import Path

from nodes.load_colmap_node import find_model_ext, guess_image_root


def _make_model(model_dir: Path, ext: str) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for stem in ("cameras", "images", "points3D"):
        (model_dir / f"{stem}{ext}").touch()


class TestFindModelExt:
    def test_bin_model(self, tmp_path):
        _make_model(tmp_path, ".bin")
        assert find_model_ext(tmp_path) == ".bin"

    def test_txt_model(self, tmp_path):
        _make_model(tmp_path, ".txt")
        assert find_model_ext(tmp_path) == ".txt"

    def test_bin_wins_when_both_present(self, tmp_path):
        _make_model(tmp_path, ".bin")
        _make_model(tmp_path, ".txt")
        assert find_model_ext(tmp_path) == ".bin"

    def test_incomplete_model(self, tmp_path):
        (tmp_path / "cameras.bin").touch()
        (tmp_path / "images.bin").touch()
        assert find_model_ext(tmp_path) is None

    def test_mixed_formats_are_incomplete(self, tmp_path):
        (tmp_path / "cameras.bin").touch()
        (tmp_path / "images.txt").touch()
        (tmp_path / "points3D.txt").touch()
        assert find_model_ext(tmp_path) is None

    def test_missing_dir(self, tmp_path):
        assert find_model_ext(tmp_path / "nope") is None


class TestGuessImageRoot:
    def test_standard_layout(self, tmp_path):
        # <workspace>/sparse/0 beside <workspace>/images
        model_dir = tmp_path / "sparse" / "0"
        model_dir.mkdir(parents=True)
        images = tmp_path / "images"
        images.mkdir()
        assert guess_image_root(model_dir) == images

    def test_flat_layout(self, tmp_path):
        # <workspace>/sparse beside <workspace>/images (no numbered subfolder)
        model_dir = tmp_path / "sparse"
        model_dir.mkdir()
        images = tmp_path / "images"
        images.mkdir()
        assert guess_image_root(model_dir) == images

    def test_no_images_folder(self, tmp_path):
        model_dir = tmp_path / "sparse" / "0"
        model_dir.mkdir(parents=True)
        assert guess_image_root(model_dir) is None

    def test_images_file_not_dir(self, tmp_path):
        model_dir = tmp_path / "sparse" / "0"
        model_dir.mkdir(parents=True)
        (tmp_path / "images").touch()
        assert guess_image_root(model_dir) is None
