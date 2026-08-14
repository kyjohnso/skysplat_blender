"""Tests for workspace dir resolution."""
from pathlib import Path

from nodes.base import default_workspace_dir, sanitize_workspace_name, tail_text


class TestSanitizeWorkspaceName:
    def test_spaces_become_underscores(self):
        assert sanitize_workspace_name("COLMAP Reconstruct") == "COLMAP_Reconstruct"

    def test_dotted_suffix_becomes_underscore(self):
        assert sanitize_workspace_name("Video.001") == "Video_001"

    def test_runs_collapse_and_trim(self):
        assert sanitize_workspace_name("  Frame  Extract  ") == "Frame_Extract"

    def test_empty_falls_back(self):
        assert sanitize_workspace_name("") == "node"
        assert sanitize_workspace_name("***") == "node"


class TestDefaultWorkspaceDir:
    UUID = "3f2a9c1d77aa01c25d12e9f09c01b44e"

    def test_blend_path_anchors_workspace(self, tmp_path):
        blend = tmp_path / "scene.blend"
        result = default_workspace_dir(
            step_label="COLMAP Reconstruct", node_uuid=self.UUID, blend_path=str(blend))
        assert result == tmp_path / "skysplat_workspace" / "colmap_reconstruct_3f2a9c1d"

    def test_unsaved_blend_uses_home(self):
        result = default_workspace_dir(step_label="Video", node_uuid=self.UUID, blend_path="")
        assert result == Path.home() / "skysplat_workspace" / "video_3f2a9c1d"

    def test_unsaved_blend_none_uses_home(self):
        result = default_workspace_dir(step_label="Video", node_uuid=self.UUID, blend_path=None)
        assert result == Path.home() / "skysplat_workspace" / "video_3f2a9c1d"

    def test_same_step_different_nodes_dont_collide(self):
        a = default_workspace_dir("Brush Train", "aaaa1111" + "0" * 24, "")
        b = default_workspace_dir("Brush Train", "bbbb2222" + "0" * 24, "")
        assert a != b
        assert a.name.startswith("brush_train_")

    def test_missing_uuid_falls_back_to_step_only(self):
        result = default_workspace_dir("Brush Train", "", "")
        assert result == Path.home() / "skysplat_workspace" / "brush_train"


class TestTailText:
    def test_missing_file_returns_empty(self, tmp_path):
        assert tail_text(tmp_path / "nope.log") == ""

    def test_small_file_returned_whole(self, tmp_path):
        log = tmp_path / "run.log"
        log.write_text("line1\nline2\nline3\n")
        assert tail_text(log) == "line1\nline2\nline3\n"

    def test_large_file_tailed_with_marker(self, tmp_path):
        log = tmp_path / "run.log"
        body = "".join(f"line {i:06d}\n" for i in range(100000))
        log.write_text(body)
        out = tail_text(log, max_bytes=1024)
        assert out.startswith("…(showing last 1 KB)…\n")
        # last line of the file is present; total payload near the cap
        assert "line 099999" in out
        assert len(out.encode("utf-8")) <= 1024 + 64
        # no spliced partial first content line after the marker
        assert out.splitlines()[1].startswith("line ")
