"""Tests for services/frames.py — frame folder discovery."""
from pathlib import Path

from services.frames import discover_frames, merge_frame_dirs


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


class TestMergeFrameDirs:
    def _make_video(self, tmp_path, name, n):
        d = tmp_path / name
        d.mkdir()
        for i in range(n):
            (d / f"frame_{i:03d}.png").write_bytes(b"")
        return d

    def test_creates_one_subfolder_per_source(self, tmp_path):
        a = self._make_video(tmp_path, "vid_a", 3)
        b = self._make_video(tmp_path, "vid_b", 4)
        merged = tmp_path / "merged"
        mapping = merge_frame_dirs([("vid_a", a), ("vid_b", b)], merged)

        assert set(mapping.values()) == {"vid_a", "vid_b"}
        assert {d.name for d in merged.iterdir()} == set(mapping.keys())
        for sub in merged.iterdir():
            # Must be a REAL directory (not a dir symlink) — COLMAP won't
            # recurse symlinked dirs correctly.
            assert sub.is_dir() and not sub.is_symlink()
            imgs = discover_frames(sub)
            assert len(imgs) >= 3
            # Files must NOT be symlinks — COLMAP records a symlink's resolved
            # target path (../../…), which breaks per-folder cameras and the
            # undistorter. Hardlinks look like regular files.
            for img in imgs:
                assert not img.is_symlink()

    def test_uniquifies_colliding_source_ids(self, tmp_path):
        a = self._make_video(tmp_path, "first", 3)
        b = self._make_video(tmp_path, "second", 3)
        merged = tmp_path / "merged"
        mapping = merge_frame_dirs([("frames", a), ("frames", b)], merged)
        # two sources with the same id -> two distinct subfolders
        assert len(mapping) == 2
        assert len(set(mapping.keys())) == 2

    def test_wipes_root_on_rerun(self, tmp_path):
        a = self._make_video(tmp_path, "vid_a", 3)
        merged = tmp_path / "merged"
        merge_frame_dirs([("vid_a", a), ("stale", self._make_video(tmp_path, "stale", 3))], merged)
        # re-run with only one source: the stale subfolder must be gone
        mapping = merge_frame_dirs([("vid_a", a)], merged)
        assert set(d.name for d in merged.iterdir()) == set(mapping.keys())
        assert "stale" not in {d.name for d in merged.iterdir()}

    def test_missing_source_raises(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError):
            merge_frame_dirs([("x", tmp_path / "nope")], tmp_path / "merged")
