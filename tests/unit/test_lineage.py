"""Tests for nodes/base.py — pure helpers (no bpy)."""
from pathlib import Path

from nodes.base import lineage_to_json, lineage_from_json, current_param_hash


class TestLineageRoundTrip:
    def test_paths_survive_round_trip(self):
        lineage = {"frames": {"path": Path("/tmp/frames"), "source_id": "vid1"}}
        as_json = lineage_to_json(lineage)
        back = lineage_from_json(as_json)
        assert back["frames"]["path"] == Path("/tmp/frames")
        assert back["frames"]["source_id"] == "vid1"

    def test_empty_lineage_round_trips(self):
        assert lineage_from_json(lineage_to_json({})) == {}

    def test_invalid_json_returns_empty(self):
        assert lineage_from_json("not json") == {}
        assert lineage_from_json("") == {}


class TestParamHashing:
    def test_same_params_same_hash(self):
        a = current_param_hash({"x": 1, "y": "abc"}, [])
        b = current_param_hash({"y": "abc", "x": 1}, [])  # order doesn't matter
        assert a == b

    def test_different_params_different_hash(self):
        a = current_param_hash({"x": 1}, [])
        b = current_param_hash({"x": 2}, [])
        assert a != b

    def test_upstream_changes_break_hash(self):
        a = current_param_hash({"x": 1}, ["upstream-A"])
        b = current_param_hash({"x": 1}, ["upstream-B"])
        assert a != b
