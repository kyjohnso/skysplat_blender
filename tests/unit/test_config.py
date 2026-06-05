"""Smoke tests for shared default-path detection in config.

These are environment-dependent (they probe the real filesystem/PATH), so
they only assert the contract: a string is returned and never crashes.
"""
from config import get_default_colmap_path, get_default_brush_path


def test_colmap_path_returns_string():
    assert isinstance(get_default_colmap_path(), str)


def test_brush_path_returns_string():
    assert isinstance(get_default_brush_path(), str)
