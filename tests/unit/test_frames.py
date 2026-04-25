"""Tests for services/frames.py — frame folder discovery."""
from pathlib import Path

from services.frames import discover_frames


class TestDiscoverFrames:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        assert discover_frames(tmp_path) == []

    def test_returns_image_files_sorted(self, tmp_path):
        for name in ["frame_003.png", "frame_001.png", "frame_002.png"]:
            (tmp_path / name).write_bytes(b"")
        result = discover_frames(tmp_path)
        assert [p.name for p in result] == ["frame_001.png", "frame_002.png", "frame_003.png"]

    def test_filters_non_image_files(self, tmp_path):
        (tmp_path / "frame_001.png").write_bytes(b"")
        (tmp_path / "notes.txt").write_text("hi")
        (tmp_path / "video.mp4").write_bytes(b"")
        result = discover_frames(tmp_path)
        assert [p.name for p in result] == ["frame_001.png"]

    def test_accepts_jpg_jpeg_png(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"")
        (tmp_path / "b.jpeg").write_bytes(b"")
        (tmp_path / "c.PNG").write_bytes(b"")
        result = discover_frames(tmp_path)
        assert {p.name for p in result} == {"a.jpg", "b.jpeg", "c.PNG"}

    def test_missing_dir_raises(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError):
            discover_frames(tmp_path / "nope")
