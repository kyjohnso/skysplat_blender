# SkySplat Release Checklist

Run before tagging a release.

## Unit tests

- [ ] `pytest -v` passes (all green)

## Integration tests

- [ ] `make test-integration` passes (requires Blender on PATH or `BLENDER=...`)
  - Note: requires a `tests/fixtures/tiny.mp4` (~1MB sample video) to actually run; otherwise the test self-skips. Generate one with `ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=30 -c:v libx264 tests/fixtures/tiny.mp4` if missing.

## Manual smoke (open Blender, load addon)

### Video panel
- [ ] Add a Video instance, set a video path, click "Load Video and SRT" — strip appears in VSE
- [ ] Click "Load" again on the same instance — no duplicate strip
- [ ] Click "Extract Frames" — frames written, count matches expectation
- [ ] Two video instances loaded — extract frames from one, the other's strip mute state is preserved

### COLMAP panel
- [ ] Click "Run COLMAP" on a prepared instance — completes successfully, log written
- [ ] Click "Load COLMAP Model" — point cloud appears with COLMAP_Root empty
- [ ] Transform the COLMAP_Root, click "Export Transformed Model" — exported model loads back correctly
- [ ] Click "Prepare Brush Dataset" — sparse + images directories laid out correctly
- [ ] Click "Create Camera Animation" — animated camera appears

### Brush panel
- [ ] Click "Run Brush Training" on a prepared dataset — training launches, output appears in console
