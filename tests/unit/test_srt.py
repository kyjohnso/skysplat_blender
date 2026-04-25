"""Tests for services/srt.py — DJI SRT metadata parsing."""
from pathlib import Path

from services.srt import parse_srt_metadata


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.srt"


class TestParseSrtMetadata:
    def test_returns_none_for_missing_file(self, tmp_path):
        result = parse_srt_metadata(tmp_path / "nope.srt")
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        empty = tmp_path / "empty.srt"
        empty.write_text("")
        assert parse_srt_metadata(empty) is None

    def test_parses_two_frames_from_fixture(self):
        result = parse_srt_metadata(FIXTURE)
        assert result is not None
        assert len(result["frames"]) == 2

    def test_first_frame_has_expected_intrinsics(self):
        result = parse_srt_metadata(FIXTURE)
        first = result["frames"][0]
        assert first["frame_index"] == 1
        assert first["focal_len_mm"] == 24.0
        assert first["latitude"] == 40.0
        assert first["longitude"] == -105.0
        assert first["rel_alt"] == 50.0

    def test_summary_uses_first_frame_intrinsics(self):
        result = parse_srt_metadata(FIXTURE)
        assert result["focal_len_mm"] == 24.0
