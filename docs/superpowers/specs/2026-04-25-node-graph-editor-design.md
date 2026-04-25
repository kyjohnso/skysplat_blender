# SkySplat Node Graph Editor — Design Spec

**Date:** 2026-04-25
**Issue:** [#51 — Multiple Videos Per COLMAP/Splat Model](https://github.com/kyjohnso/skysplat_blender/issues/51)
**Status:** Brainstorming complete, awaiting plan.

## Problem

SkySplat's current workflow is strictly linear: 1 video → 1 frames folder → 1 COLMAP model → 1 splat model. Multi-instance support added in v0.4.0 made N parallel pipelines possible, but provides no way to combine sources — e.g., 2 videos feeding 1 COLMAP reconstruction, or merging two existing reconstructions into one. Users who capture a scene from multiple angles, with multiple drones, or with high-resolution stills as supplements, cannot express that in skysplat today.

## Solution

A new node-based editor for skysplat that lets users wire together videos, frame extraction, COLMAP reconstruction, COLMAP merging, transformation in viewport, camera animation, and Brush training as a graph. The editor coexists with the existing sidebar panels in the short term and will replace them in v1.0.

## Non-goals

- Graph export/import as a standalone JSON file (deferred — graphs travel inside `.blend` files only).
- Smart frame extraction (people removal, change detection, etc.). Mentioned as future work; not in this design.
- Render-pipeline nodes that feed into Blender's compositor.
- Migrating existing sidebar instances into the node graph automatically (a manual import operator may come in v0.7.x).

## Architecture

Three layers:

```
┌──────────────────────────────────────────────────────────────┐
│  Blender UI                                                  │
│  ┌──────────────────┐    ┌─────────────────────────────┐     │
│  │  Sidebar panels  │    │  SkySplat Node Editor       │     │
│  │  (existing,      │    │  (new editor type)          │     │
│  │  thin wrappers)  │    │  custom NodeTree, Nodes,    │     │
│  │                  │    │  Sockets                    │     │
│  └────────┬─────────┘    └───────────────┬─────────────┘     │
└───────────┼──────────────────────────────┼───────────────────┘
            │                              │
            ▼                              ▼
┌──────────────────────────────────────────────────────────────┐
│  services/  (NEW — pure-Python pipeline functions)           │
│    video_service       — load video into VSE, parse SRT      │
│    frames_service      — extract frames (BlenderRenderTask)  │
│    colmap_service      — run colmap, merge models            │
│    transform_service   — apply transform to model            │
│    colmap_view_service — import points + COLMAP_Root empty   │
│    camera_service      — build animated cameras              │
│    brush_service       — prepare dataset, run training       │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
        COLMAP, brush_app, Blender's own render
```

**Layer responsibilities:**

1. **`services/` package** — plain Python modules, each function takes explicit args and returns explicit outputs. The strict rule: services do not read or write `Scene.skysplat_*` properties or any sidebar/node UI state behind the caller's back. Two flavors:
   - **pure** (`frames_service`, `colmap_service`, `transform_service`, parts of `video_service`, parts of `brush_service`) — no `bpy` imports.
   - **scene** (`colmap_view_service`, `camera_service`, parts of `video_service`) — mutate a Blender scene passed in as an explicit argument.

2. **Existing sidebar panels** are refactored into thin wrappers that read sidebar instance data, build the right service inputs, and call the services. No user-visible change for current workflows.

3. **New node editor** lives in a new `nodes/` package. Registers a custom `bpy.types.NodeTree` subclass with `bl_idname = "SkySplatNodeTree"` that appears as a new editor type in Blender's Editor Type dropdown.

## Services API

### `video_service.py` (mixed)

```python
def parse_srt_metadata(srt_path: Path) -> dict | None
def load_video_into_vse(
    scene: bpy.types.Scene,
    video_path: Path,
    srt_meta: dict | None,
    strip_name: str,
) -> bpy.types.MovieSequence
```

`load_video_into_vse` adopts an existing strip if one with the same `filepath` already exists in the scene's sequencer (so re-running a Video node doesn't create duplicate strips).

### `frames_service.py` (pure)

```python
def extract_frames(
    scene: bpy.types.Scene,
    video_strip_name: str,
    out_dir: Path,
    start: int,
    end: int,
    step: int,
    log_path: Path,
) -> RunningTask          # BlenderRenderTask
def discover_frames(image_dir: Path) -> list[Path]
```

`extract_frames` mutes all VSE movie strips except the target, sets render output path/format/resolution from the target strip, and launches `bpy.ops.render.opengl('INVOKE_DEFAULT', animation=True, sequencer=True)`. The returned `RunningTask` restores prior mute states in its `render_complete`/`render_cancel` handlers.

### `colmap_service.py` (pure)

```python
# Camera model is a discriminated union — one per Frames source.
class CameraModelSpec: ...
class Auto(CameraModelSpec):       pass            # COLMAP estimates from EXIF (stills only)
class FromSRT(CameraModelSpec):    srt_path: Path  # parse intrinsics from drone SRT
class Manual(CameraModelSpec):                     # user-specified
    model: str          # COLMAP camera model: SIMPLE_PINHOLE, OPENCV, etc.
    params: list[float]
class Inherit(CameraModelSpec):    pass            # Frame Extract default — ride along with
                                                    # parent Video's FromSRT, else fall back to
                                                    # the source node's Manual setting

@dataclass
class FramesSource:
    path: Path
    source_id: str
    camera_model: CameraModelSpec   # Auto | FromSRT | Manual | Inherit

@dataclass
class ColmapParams:
    mode: Literal["joint", "merge_after"] = "joint"
    matching: Literal["sequential", "exhaustive"] = "exhaustive"
    use_gpu: bool = True

@dataclass
class ColmapResult:
    model_dir: Path                       # path to sparse model
    source_map: dict[Path, str]           # image_path → source_id (lineage)
    image_root: Path                      # base directory all image paths are relative to

def run_reconstruction(
    sources: list[FramesSource],
    workspace_dir: Path,
    params: ColmapParams,
    log_path: Path,
) -> RunningTask                          # SubprocessTask
def merge_models(
    model_a: Path, model_b: Path, output_dir: Path, log_path: Path,
) -> RunningTask
def read_model(model_path: Path) -> ColmapModel
def write_model(model: ColmapModel, output_path: Path) -> None
```

`run_reconstruction` writes images into `workspace_dir` arranged one folder per source (so COLMAP's `--ImageReader.single_camera_per_folder` makes each source's camera model independent). In `joint` mode, COLMAP runs once across all images. In `merge_after` mode, COLMAP runs once per source then `model_merger` fuses results. Both modes return a single `ColmapResult` with `source_map` populated.

The standalone `ColmapMergeNode` (separate node, calls `merge_models`) is **not redundant** with `merge_after` mode: `merge_after` fuses sources that go into a single `ColmapReconstructNode`, while `ColmapMergeNode` fuses two `ColmapModel` lineage values arriving from different graph branches — typical use is combining a freshly-reconstructed model with one loaded from disk via a future "Load Existing Model" source node.

### `transform_service.py` (pure)

```python
def apply_transform(model: ColmapModel, mat4: Matrix) -> ColmapModel
```

Applies a 4×4 transform to all camera poses and points in the model.

### `colmap_view_service.py` (scene)

```python
def import_model_to_scene(
    scene: bpy.types.Scene,
    model: ColmapModel,
    node_uuid: str,
    display_name: str,
) -> bpy.types.Object                     # the COLMAP_Root empty
def read_root_transform(
    scene: bpy.types.Scene, node_uuid: str,
) -> Matrix
```

Creates collection `colmap__<display_name>` under the top-level `skysplat` collection (created if absent) and a `COLMAP_Root_<display_name>` empty parented to all imported points. Both objects carry the `["skysplat_node_uuid"]` custom property as the durable link to the node.

### `camera_service.py` (scene)

```python
def create_animated_cameras(
    scene: bpy.types.Scene,
    model: ColmapModel,
    video_strip_starts: dict[str, int],   # source_id → VSE start frame
    node_uuid: str,
    display_name: str,
) -> list[bpy.types.Object]
```

Groups model images by `source_map[image] → source_id`, parses frame numbers from image filenames, looks up each source's VSE strip start frame, and creates one animated camera per source with keyframes offset to that strip's timeline position. Cameras land in `cameras__<display_name>` collection.

### `brush_service.py` (mixed)

```python
def prepare_dataset(
    model_dir: Path, image_dir: Path, output_dir: Path,
) -> Path                                 # pure
def run_training(
    dataset_dir: Path, output_dir: Path, params: BrushParams, log_path: Path,
) -> RunningTask                          # SubprocessTask
```

## RunningTask abstraction

All long-running operations return a `RunningTask`:

```python
class RunningTask(Protocol):
    def poll(self) -> int | None         # None=running, 0=success, nonzero=error
    def cancel(self) -> None
    def progress(self) -> tuple[float, str]   # (0..1, status text)
    def log_path(self) -> Path
```

Two implementations:

- **`SubprocessTask`** wraps `subprocess.Popen` for COLMAP, Brush, and `colmap model_merger`. Pipes stdout+stderr to `log_path`. Service supplies a regex to extract progress percent from log lines.
- **`BlenderRenderTask`** wraps `bpy.ops.render.opengl('INVOKE_DEFAULT', animation=True, sequencer=True)`. Registers `render_pre`/`render_post`/`render_complete`/`render_cancel` handlers. Each `render_post` writes a synthetic log line ("Rendered frame 142/500") and bumps progress. Cancel triggers Blender's render-cancel.

The bake walker only depends on `RunningTask`; it doesn't know which kind it's polling.

## Node design

### Node base class

```python
class SkysplatNode(bpy.types.Node):
    bl_idname: str                    # set by subclass
    bl_label: str                     # set by subclass

    # Identity & state — bpy.props on the node
    uuid: StringProperty()            # set on init, never changes
    workspace_dir: StringProperty()   # auto-derived; user-overridable
    status: EnumProperty(items=[
        ("clean","Clean",""),("dirty","Dirty",""),
        ("running","Running",""),("done","Done",""),("errored","Errored",""),
    ])
    last_run_hash: StringProperty()
    last_error: StringProperty()
    cached_output_json: StringProperty()  # JSON-serialized lineage objects per output socket
    name_is_user_edited: BoolProperty(default=False)

    # Lifecycle hooks
    def init(self, context): ...              # called once on node creation
    def copy(self, original): ...             # called on Shift-D — fresh UUID, dirty
    def free(self): ...                       # called on delete — preserve workspace? (no, leave on disk)
    def update(self): ...                     # called on wire (dis)connect — recompute auto-name

    # Execution
    def evaluate(self, socket_name) -> Any   # returns lineage object for given output socket
    def run(self) -> RunningTask              # invoked by bake walker
    def is_dirty(self) -> bool                # current_hash != last_run_hash
    def current_hash(self) -> str

    # UI
    def draw_buttons(self, context, layout): ...
```

### Sockets

Five custom socket types, each carrying a typed lineage dataclass:

| Socket | Color | Carries |
|---|---|---|
| `VideoSocket` | green | `Video(path, source_id, srt_meta, vse_strip_name, vse_strip_start_frame)` |
| `FramesSocket` | orange | `Frames(path, source_id, camera_model, image_count)` |
| `ColmapModelSocket` | blue | `ColmapModel(model_dir, source_map, image_root)` |
| `DatasetSocket` | yellow | `Dataset(dir, source_map)` |
| `SplatSocket` | red | `Splat(ply_path, training_log)` |

Lineage objects are not stored on the socket itself — Blender's `default_value` doesn't accommodate arbitrary Python objects cleanly. Instead, an in-memory evaluation registry keyed by `(node.uuid, socket.identifier)` holds the live values, populated from `cached_output_json` on .blend load. Downstream nodes look up upstream values by walking `socket.links[0].from_node.uuid + .from_socket.identifier`.

`ColmapModelSocket` is multi-input on `COLMAP Reconstruct` — Blender 4.x supports this on custom socket types.

### Node types

| Class | Inputs | Outputs | Side effects |
|---|---|---|---|
| `VideoNode` | (none — file picker) | `Video` | Loads/adopts movie strip in VSE |
| `FramesFolderNode` | (none — folder picker) | `Frames` | none |
| `FrameExtractNode` | `Video` | `Frames` | mutes/unmutes VSE strips during render |
| `ColmapReconstructNode` | `Frames` (multi) | `ColmapModel` | none (subprocess only) |
| `ColmapMergeNode` | `ColmapModel`, `ColmapModel` | `ColmapModel` | none |
| `ColmapInViewportNode` | `ColmapModel` | `ColmapModel` (transformed) | imports point cloud + `COLMAP_Root_*` empty into scene |
| `CameraAnimationNode` | `ColmapModel` | (none — pure sink) | creates `AnimatedCamera_*` per source video |
| `BrushDatasetNode` | `ColmapModel` | `Dataset` | none |
| `BrushTrainNode` | `Dataset` | `Splat` | none |

### Round-trip output evaluation

`ColmapInViewportNode.evaluate("transformed_model")` reads the live transform of `COLMAP_Root_<uuid>` on every call and returns `transform_service.apply_transform(cached_input_model, mat)`. Downstream nodes get the current viewport transform every time they re-evaluate, so dragging the empty between bakes propagates automatically.

If the empty is missing (user deleted it from the outliner), `evaluate` raises `NodeEvalError` and the downstream node flips to dirty. Next bake re-creates.

### Naming

| Node | Default name rule |
|---|---|
| `VideoNode` | filename basename (`drone.mp4` → "drone") |
| `FramesFolderNode` | folder basename |
| `FrameExtractNode` | `<video_name>_frames` |
| `ColmapReconstructNode` | 1 source: `colmap_<source_name>`. 2+ sources: `colmap_<n>` counter |
| `ColmapMergeNode` | `merge_<n>` counter |
| `ColmapInViewportNode` | `<colmap_source_name>_view` |
| `CameraAnimationNode` | `cameras_<colmap_source_name>` |
| `BrushDatasetNode` | `dataset_<colmap_source_name>` |
| `BrushTrainNode` | `splat_<colmap_source_name>` |

Auto-derived on wire (dis)connect via `Node.update()`. When the user edits the node header text, `name_is_user_edited` is set and auto-update stops for that node.

### Shift-D duplicate

`Node.copy(self, original)` is called by Blender after the standard property-copy. Override sets:
- fresh UUID via `uuid.uuid4()`
- `cached_output_json = ""`
- `last_run_hash = ""`
- `status = "dirty"`
- recompute default name (with `.001`-style suffix if collision)

Result: duplicate has identical params, fresh identity, must be re-run. No accidental sharing of workspace dirs.

### Mute

Standard Blender M-key mute. For 1-in-1-out nodes (Frame Extract, COLMAP in Viewport, Brush Dataset) muting bypasses the work and passes input lineage straight through to output. For multi-input or pure-source nodes, muting disables `run()` and downstream nodes treat the connection as no-input.

## Execution model

Two entry points share one code path:

1. **Per-node Run button** — calls `bake(target=this_node, force_self=True)`.
2. **Bake from output** — right-click an output socket → "Bake to here". Calls `bake(target=this_node, force_self=False)`.

### Bake walker

A modal `bpy.types.Operator`:

1. Build evaluation order via topological sort of the subgraph upstream of the target.
2. Refuse if a cycle is detected.
3. For each node in order:
   - `if not is_dirty() and not force_self: skip, use cached_output.`
   - else: set `status = "running"`, call `node.run()` to get a `RunningTask`, poll on a 1Hz timer.
4. On task success → `status = "done"`, update `last_run_hash`, write `cached_output_json`.
5. On task error → `status = "errored"`, store exception message in `last_error`, halt walk.
6. On user cancel → `status = "dirty"`, partial output left on disk.

### Staleness

```python
def current_hash(self) -> str:
    upstream_hashes = sorted(
        link.from_node.last_run_hash
        for input_sock in self.inputs for link in input_sock.links
    )
    return sha256(self.params_dict() + upstream_hashes).hexdigest()
```

When a parameter on a Video node changes, its `last_run_hash` doesn't change yet (it only changes on a successful run), but its `current_hash` does. So downstream `is_dirty()` checks return True transitively.

### Concurrency

- One bake walker per NodeTree at a time. Trying to start a second one shows a popup and refuses.
- Addon-wide singleton lock for `BlenderRenderTask` (Frame Extract): even two separate Run-button clicks across different trees can't run renders concurrently, because Blender's render is global per scene.

## Persistence

- **NodeTree** is a Blender datablock; saved/loaded by Blender's standard mechanism.
- **Node properties** (`uuid`, `status`, `last_run_hash`, `cached_output_json`, etc.) are `bpy.props` on the node class, so they persist with the .blend.
- **Workspace directories** at `<.blend dir>/skysplat_workspace/<node_uuid>/`. UUID survives renames so caches stay valid. If `.blend` is unsaved, fall back to `~/skysplat_workspace/<node_uuid>/` and warn that caches will be orphaned across sessions.
- **Log files** at `<workspace>/run.log`. Live-tailed into Blender Text data-blocks named `skysplat_log_<node_uuid>` for the View Output button. Text data-blocks save with the .blend, so logs travel with the project.
- **Cache verification on .blend load:** for every node with `status == "done"`, verify the cached output paths exist on disk. Missing → flip to `"dirty"`.

## Outliner organization

```
Scene
└── skysplat                          ← top-level container, hidden if empty
    ├── colmap__<display_name>        ← per ColmapInViewport node
    │   ├── COLMAP_Root_<display_name>
    │   └── points
    └── cameras__<display_name>       ← per CameraAnimation node
        └── AnimatedCamera_<source_id> [×N for multi-video]
```

Every skysplat-created object/collection carries `["skysplat_node_uuid"] = "<uuid>"` as the durable link.

**Two-way navigation:**
- Each round-trip node has a 📍 Select button that activates the matching collection and selects/frames the empty.
- The SkySplat Node Editor's N-panel shows "Selected scene object → owning node" with a "Reveal Node" button for any selected object that carries `["skysplat_node_uuid"]`.

**Conflict rules:**
- Same display name twice → Blender's `.001`/`.002` de-duplication. Custom property still uniquely identifies.
- User manually renames empty → not fought continuously; on next `run()` it's renamed back.
- User deletes the `skysplat` parent collection → all round-trip nodes flip to `dirty`; next bake re-creates everything.

## Error handling

- Service functions raise typed exceptions: `ColmapError`, `BrushError`, `FrameExtractError`. Each carries a short message + optional log excerpt.
- Bake walker catches these, sets `status = "errored"`, stores message in `last_error`, halts the walk.
- Errors are also tee'd to `run.log` so View Output shows full failure context.
- A non-modal popup at bake completion summarizes: which node errored, short message, "View Log" button.
- `NodeEvalError` (raised from output socket evaluation when scene state is missing) is treated as recoverable — flips to `dirty`, not `errored`. Next bake re-creates.

## Status row UI

Drawn at the top of every node's `draw_buttons`:

```
●  Running   23%   📍 Select   📜 View Output   ↻ Re-run
```

| Element | Behavior |
|---|---|
| Status dot | grey=clean / yellow=dirty / blue spin=running / green=done / red=errored |
| Progress text | derived from `RunningTask.progress()` — frame counter, COLMAP stage, Brush iteration |
| 📍 Select | only on round-trip nodes; activates collection + selects/frames empty |
| 📜 View Output | opens `skysplat_log_<uuid>` Text data-block in a Text Editor area or popup |
| ↻ Re-run | clears `last_run_hash`, marks dirty, immediately bakes |

## Testing

Pytest unit tests for pure services: `frames_service.discover_frames`, `colmap_service.read_model`/`write_model`, `colmap_service.merge_models` (mocked subprocess), `transform_service.apply_transform`, `video_service.parse_srt_metadata`, the staleness hashing logic.

Headless integration scripts run via `blender --background --python tests/integration/<script>.py`. One script per scenario. Each returns nonzero on failure. Driven by a Makefile target. No CI required initially.

Manual smoke checklist in `docs/release-checklist.md` covering UI feel that automation can't catch — viewport drag, mute, Shift-D, missing-workspace-on-load, View Output live tail, cancel mid-bake.

Test fixtures: small (~5MB) mp4 clips and a pre-computed COLMAP model in `tests/fixtures/`.

## Rollout plan

| Phase | Version | Scope |
|---|---|---|
| **1. Services extraction** | v0.5.0 | Refactor existing operators to call into new `services/` package. Sidebar panels keep working unchanged. Pure-service pytest tests added. **No new UI yet.** Released standalone for bisect safety. |
| **2. Node editor MVP** | v0.6.0 | New `nodes/` package, custom NodeTree, all 9 node types, bake walker, View Output button. Side-by-side with sidebar panels. Documented as "experimental — feedback wanted." |
| **3. Polish** | v0.6.x | Multi-video Camera Animation lineage refinement, naming auto-derivation polish, Select / Reveal Node, headless integration tests, README + screenshots. |
| **4. Deprecation path** | v0.7.0+ | Mark sidebar panels as legacy. Add "Migrate sidebar instance → node graph" operator. Sidebar still works but stops getting features. |
| **5. Sidebar removal** | v1.0.0 | Sidebar panels removed. Node editor is the only UI. Migration operator stays for backward compat. |

## Open risks

- **Blender 4.x vs 5.x API differences** for custom NodeTree editor type, multi-input sockets, node draw methods. Min-version verification spike needed early in phase 2. Likely outcome: Blender 4.0+ supported, 5.0+ recommended.
- **`bpy.ops.render.opengl(INVOKE_DEFAULT, animation=True)` async behavior** — this design assumes it runs non-blocking with `render_*` handlers firing per frame. 95% confident based on Blender docs; needs a verification spike in phase 2. Fallback: per-frame `bpy.app.timers` callback driving single-frame renders.
- **Storing complex output lineage on nodes** — `bpy.props` has no Python-object type. Solution: serialize `cached_output` to JSON in a `StringProperty`. Constraints: paths and primitives only; if any future output type can't JSON-serialize, that's a redesign.
- **`source_map` size for very large reconstructions** — 100,000-image reconstructions would produce a large dict. Likely fine for JSON storage but worth measuring during phase 2.
