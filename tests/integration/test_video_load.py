"""Headless integration test: load_video_into_vse adopts and creates strips.

Run via: blender --background --python tests/integration/test_video_load.py

Exits 0 on success, nonzero on failure.
"""
import sys
from pathlib import Path

# Add addon root to path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import bpy

from services.video import load_video_into_vse


def main():
    # Reset to a clean scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # Use a fixture mp4 if present, otherwise skip with a warning.
    fixture = ROOT / "tests" / "fixtures" / "tiny.mp4"
    if not fixture.exists():
        print(f"SKIP: {fixture} not present (need a tiny mp4 fixture)")
        sys.exit(0)

    # Create
    strip = load_video_into_vse(scene, fixture, strip_name="skysplat_test")
    assert strip is not None, "Expected a strip after load"

    # Re-load same file → adoption: same number of strips
    seq_editor = scene.sequence_editor
    count_before = len([s for s in (
        seq_editor.strips_all if hasattr(seq_editor, 'strips_all') else seq_editor.sequences_all
    ) if s.type == 'MOVIE'])
    load_video_into_vse(scene, fixture, strip_name="skysplat_test_2")
    count_after = len([s for s in (
        seq_editor.strips_all if hasattr(seq_editor, 'strips_all') else seq_editor.sequences_all
    ) if s.type == 'MOVIE'])
    assert count_before == count_after, (
        f"Expected adoption (no new strip) but counts went {count_before} -> {count_after}"
    )

    print("PASS: video load + adoption")
    sys.exit(0)


if __name__ == "__main__":
    main()
