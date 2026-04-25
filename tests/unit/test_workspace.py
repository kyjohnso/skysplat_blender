"""Tests for workspace dir resolution."""
from pathlib import Path

from nodes.base import default_workspace_dir


class TestDefaultWorkspaceDir:
    def test_blend_path_anchors_workspace(self, tmp_path):
        blend = tmp_path / "scene.blend"
        result = default_workspace_dir(node_uuid="abc123", blend_path=str(blend))
        assert result == tmp_path / "skysplat_workspace" / "abc123"

    def test_unsaved_blend_uses_home(self):
        result = default_workspace_dir(node_uuid="def456", blend_path="")
        assert result == Path.home() / "skysplat_workspace" / "def456"

    def test_unsaved_blend_none_uses_home(self):
        result = default_workspace_dir(node_uuid="def456", blend_path=None)
        assert result == Path.home() / "skysplat_workspace" / "def456"
