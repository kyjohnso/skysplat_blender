"""Tests for the pure helpers in nodes/link_drag_search.py (no bpy needed)."""
import pytest

from nodes.link_drag_search import (
    estimate_socket_positions,
    nearest_socket,
    suggestions_for,
)

U = 20.0  # widget_unit at ui_scale 1


class TestEstimateSocketPositions:
    def test_expanded_output_from_top(self):
        # loc.y is the node's top edge; first output sits below the header
        # (1U) + top pad (0.25U), centered in its 1U row.
        ins, outs = estimate_socket_positions(
            loc=(0.0, 0.0), dims=(140.0, 200.0),
            n_inputs=0, n_outputs=1, hidden=False, widget_unit=U)
        assert ins == []
        assert outs == [(140.0, -1.75 * U)]

    def test_expanded_second_output_row_spacing(self):
        _, outs = estimate_socket_positions(
            (0.0, 0.0), (140.0, 200.0), 0, 2, False, U)
        assert outs[1][1] == pytest.approx(outs[0][1] - 1.1 * U)

    def test_expanded_inputs_anchor_to_bottom(self):
        # Inputs are laid out below the (unknown-height) buttons, so we
        # measure from the node bottom: last input at bottom + 0.75U.
        ins, _ = estimate_socket_positions(
            (0.0, -0.0), (140.0, 200.0), 2, 0, False, U)
        bottom = -200.0
        assert ins[-1] == (0.0, bottom + 0.75 * U)
        assert ins[0][1] == pytest.approx(bottom + 0.75 * U + 1.1 * U)

    def test_inputs_on_left_outputs_on_right(self):
        ins, outs = estimate_socket_positions(
            (100.0, 0.0), (140.0, 200.0), 1, 1, False, U)
        assert ins[0][0] == 100.0
        assert outs[0][0] == 240.0

    def test_hidden_single_sockets_centered_on_header(self):
        ins, outs = estimate_socket_positions(
            (0.0, 0.0), (100.0, 30.0), 1, 1, True, U)
        # offset = -0.5U, single socket -> no spread
        assert ins == [(0.0, -0.5 * U)]
        assert outs == [(100.0, -0.5 * U)]

    def test_hidden_multiple_outputs_spread(self):
        _, outs = estimate_socket_positions(
            (0.0, 0.0), (100.0, 40.0), 0, 3, True, U)
        ys = [y for _, y in outs]
        assert ys[0] - ys[1] == pytest.approx(0.5 * U)
        assert sum(ys) / 3 == pytest.approx(-0.5 * U)  # centered on header


class TestNearestSocket:
    POS = [(140.0, -35.0), (140.0, -57.0)]

    def test_direct_hit(self):
        assert nearest_socket((140.0, -35.0), self.POS, U) == 0

    def test_nearest_wins(self):
        assert nearest_socket((139.0, -50.0), self.POS, U) == 1

    def test_outside_tolerance_is_none(self):
        assert nearest_socket((140.0, -100.0), self.POS, U) is None
        assert nearest_socket((100.0, -35.0), self.POS, U) is None

    def test_empty(self):
        assert nearest_socket((0.0, 0.0), [], U) is None


class TestSuggestionsFor:
    SPECS = {
        "SkysplatVideoNode": {
            "label": "Video",
            "inputs": [],
            "outputs": [("Video", "SkysplatVideoSocket")],
        },
        "SkysplatFrameExtractNode": {
            "label": "Frame Extract",
            "inputs": [("Video", "SkysplatVideoSocket")],
            "outputs": [("Frames", "SkysplatFramesSocket")],
        },
        "SkysplatMergeFramesNode": {
            "label": "Merge Frames",
            # dynamic trailing empties -> duplicate names in the probe
            "inputs": [("Frames", "SkysplatFramesSocket"),
                       ("Frames", "SkysplatFramesSocket")],
            "outputs": [("Frames", "SkysplatFramesSocket")],
        },
    }

    def test_drag_from_output_finds_inputs(self):
        got = suggestions_for(self.SPECS, "SkysplatVideoSocket", 'OUT')
        assert got == [("SkysplatFrameExtractNode", "Frame Extract", "Video")]

    def test_drag_from_input_finds_outputs(self):
        got = suggestions_for(self.SPECS, "SkysplatVideoSocket", 'IN')
        assert got == [("SkysplatVideoNode", "Video", "Video")]

    def test_duplicate_socket_names_deduped(self):
        got = suggestions_for(self.SPECS, "SkysplatFramesSocket", 'OUT')
        assert got == [("SkysplatMergeFramesNode", "Merge Frames", "Frames")]

    def test_no_match(self):
        assert suggestions_for(self.SPECS, "SkysplatSplatSocket", 'OUT') == []
