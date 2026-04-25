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

### Node editor (phase 2 MVP)

- [ ] Editor Type dropdown shows "SkySplat" — selecting it opens an empty canvas
- [ ] Shift-A → SkySplat menu has 6 entries: Video, Frames Folder, Frame Extract, COLMAP Reconstruct, Brush Dataset, Brush Train
- [ ] Drop in a Video node — set a video file path — Run — VSE strip appears, status flips to "Done"
- [ ] Wire Video → Frame Extract — Run extract — frames written to node workspace dir
- [ ] Wire Frame Extract → COLMAP Reconstruct — Run COLMAP — sparse model generated
- [ ] Wire COLMAP → Brush Dataset — Run — sparse + images copied/symlinked under workspace
- [ ] Wire Brush Dataset → Brush Train — set brush_executable, low total_steps — Run — .ply appears
- [ ] Click View Output (T icon) on any Done node — log file opens in OS viewer
- [ ] Shift-D duplicate any Done node — duplicate has fresh UUID, status="dirty", empty workspace
- [ ] Save .blend, reopen — node graph persists, Done nodes still show "Done"
