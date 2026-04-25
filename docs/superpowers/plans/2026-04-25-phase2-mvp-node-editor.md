# Phase 2 (MVP): Node Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a usable SkySplat Node Editor in Blender — custom NodeTree editor type with 6 node types (Video, Frames Folder, Frame Extract, COLMAP, Brush Dataset, Brush Train) and per-node Run buttons. Demonstrates the linear pipeline as a graph.

**Architecture:** Custom `bpy.types.NodeTree` registered as a new editor type alongside Geometry Nodes/Compositor. Each node is a `bpy.types.Node` subclass with a per-node Run button that calls into the existing `services/` layer (built in phase 1). Sockets carry typed lineage objects via a per-tree evaluation registry. No bake walker, no round-trip nodes, no auto-naming, no live log tail — those are deferred to phase 2.5+.

**Tech Stack:** Blender Python API (bpy), `services/*` from phase 1, pytest for any pure-Python helpers.

**Spec:** `docs/superpowers/specs/2026-04-25-node-graph-editor-design.md`

**Out of scope (deferred to later phases):**
- COLMAP Merge node
- COLMAP in Viewport (round-trip transform)
- Camera Animation node
- Bake-from-output / topological walker
- Auto-derived node names
- 📍 Select / Reveal Node UI
- Live log tail (View Output button gives a path-to-clipboard for now)
- Multi-source COLMAP — `services.colmap.run_reconstruction` already raises ColmapError for multi-source; the COLMAP node enforces single-input until phase 2.5

**Stages:**
- **Stage A — Editor scaffolding** (4 tasks): NodeTree class, base node, sockets, registration, Add menu skeleton.
- **Stage B — Source nodes** (2 tasks): Video, Frames Folder.
- **Stage C — Pipeline nodes** (4 tasks): Frame Extract, COLMAP, Brush Dataset, Brush Train.
- **Stage D — Polish** (2 tasks): View Output button, status row finalization.

---

## File Structure

**New files:**

```
nodes/
  __init__.py             # registers everything from this package
  tree.py                 # SkySplatNodeTree class
  base.py                 # SkysplatNode base + lineage registry + workspace helpers
  sockets.py              # 5 socket classes (Video/Frames/ColmapModel/Dataset/Splat)
  add_menu.py             # NODE_MT_add submenu wiring
  video_node.py           # SkysplatVideoNode
  frames_folder_node.py   # SkysplatFramesFolderNode
  frame_extract_node.py   # SkysplatFrameExtractNode
  colmap_node.py          # SkysplatColmapNode
  brush_dataset_node.py   # SkysplatBrushDatasetNode
  brush_train_node.py     # SkysplatBrushTrainNode

tests/unit/
  test_lineage.py         # lineage object serialization round-trip (pure)
  test_workspace.py       # workspace dir helper logic (pure)
```

**Modified files:**

- `__init__.py` (addon root) — register the `nodes` package alongside `ui`.

---

# Stage A — Editor Scaffolding

## Task A1: NodeTree subclass + minimal registration

**Files:**
- Create: `nodes/__init__.py`
- Create: `nodes/tree.py`
- Modify: `__init__.py` (addon root) — import + register `nodes` package.

#### Step 1: Create `nodes/tree.py`

```python
"""SkySplatNodeTree — registers a new editor type so users can split a
Blender area to "SkySplat Node Editor" and see a node graph there.

The actual nodes live in sibling modules (video_node.py, etc.).
"""
from __future__ import annotations

try:
    import bpy
    from bpy.types import NodeTree
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    NodeTree = object  # for static analysis when bpy is missing


class SkySplatNodeTree(NodeTree if HAS_BPY else object):
    """Top-level container for skysplat pipeline graphs."""
    bl_idname = "SkySplatNodeTree"
    bl_label = "SkySplat"
    bl_icon = "NODETREE"


classes = (SkySplatNodeTree,) if HAS_BPY else ()


def register():
    if not HAS_BPY:
        return
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if not HAS_BPY:
        return
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

#### Step 2: Create `nodes/__init__.py`

```python
"""skysplat node editor — phase 2 MVP.

Registers a new editor type and the node classes that populate it.
Each node calls into services/* for actual pipeline work.
"""
try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from . import tree

_modules = (tree,)


def register():
    if not HAS_BPY:
        return
    for m in _modules:
        m.register()


def unregister():
    if not HAS_BPY:
        return
    for m in reversed(_modules):
        m.unregister()
```

#### Step 3: Wire `nodes` into the addon root `__init__.py`

Currently the addon root has a `register()`/`unregister()` block that registers the panel classes. Modify it to also register the `nodes` package. Inside the `if _BPY_AVAILABLE:` block, after the existing imports and before the existing `register()` function:

```python
    from . import nodes as nodes_pkg
```

Then in `register()`, after `bpy.types.Scene.skysplat_brush_props = ...`:

```python
    nodes_pkg.register()
```

And in `unregister()`, BEFORE `del bpy.types.Scene.skysplat_props`:

```python
    nodes_pkg.unregister()
```

#### Step 4: Manual smoke check

Reload the addon in Blender. Open any area, change Editor Type dropdown — there should now be a "SkySplat" entry alongside the standard editors. Selecting it shows an empty canvas (no add menu yet — that's task A4).

If the editor doesn't appear: check the terminal for registration errors. The most common issue is `bl_idname` collision or missing `bl_label`.

#### Step 5: Commit

```bash
git add nodes/__init__.py nodes/tree.py __init__.py
git commit -m "Register SkySplatNodeTree as a new Blender editor type"
```

---

## Task A2: Custom socket classes

**Files:**
- Create: `nodes/sockets.py`
- Modify: `nodes/__init__.py` — import and register sockets module.

Phase 2 MVP defines 5 sockets. Each carries a small lineage dataclass; the actual data is stored in a per-tree registry (Task A3) — sockets just declare type + draw color.

#### Step 1: Create `nodes/sockets.py`

```python
"""Socket types for the SkySplat node editor.

Each socket type has a fixed color and identifies a kind of data flowing
through the graph. The actual lineage object (paths, source_id, etc.)
isn't stored on the socket itself — Blender's `default_value` doesn't
accommodate arbitrary Python objects cleanly — but in a per-tree
registry keyed by (node.uuid, socket.identifier). See nodes/base.py.
"""
from __future__ import annotations

try:
    import bpy
    from bpy.types import NodeSocket
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    NodeSocket = object


class _SkysplatSocket(NodeSocket if HAS_BPY else object):
    """Base for skysplat sockets. Subclasses set bl_idname, bl_label, and color."""
    color = (0.5, 0.5, 0.5, 1.0)

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return self.color


class VideoSocket(_SkysplatSocket):
    bl_idname = "SkysplatVideoSocket"
    bl_label = "Video"
    color = (0.20, 0.65, 0.27, 1.0)  # green


class FramesSocket(_SkysplatSocket):
    bl_idname = "SkysplatFramesSocket"
    bl_label = "Frames"
    color = (0.85, 0.55, 0.20, 1.0)  # orange


class ColmapModelSocket(_SkysplatSocket):
    bl_idname = "SkysplatColmapModelSocket"
    bl_label = "COLMAP Model"
    color = (0.20, 0.50, 0.78, 1.0)  # blue


class DatasetSocket(_SkysplatSocket):
    bl_idname = "SkysplatDatasetSocket"
    bl_label = "Dataset"
    color = (0.80, 0.78, 0.30, 1.0)  # yellow


class SplatSocket(_SkysplatSocket):
    bl_idname = "SkysplatSplatSocket"
    bl_label = "Splat"
    color = (0.85, 0.32, 0.38, 1.0)  # red


classes = (
    VideoSocket, FramesSocket, ColmapModelSocket, DatasetSocket, SplatSocket,
) if HAS_BPY else ()


def register():
    if not HAS_BPY:
        return
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    if not HAS_BPY:
        return
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

#### Step 2: Update `nodes/__init__.py`

Replace the `_modules = (tree,)` line with:

```python
from . import tree, sockets

_modules = (tree, sockets)
```

Both `register()` and `unregister()` work unchanged because they iterate `_modules`.

#### Step 3: Manual smoke check

Reload addon in Blender. The sockets aren't visible yet (no nodes use them), but the registration shouldn't error. Check the terminal — if there are errors complaining about NodeSocket, it usually means a `bl_idname` collision or a Blender API change.

If you want a quick visual: in Blender's Python console, run:
```python
bpy.types.SkysplatVideoSocket
```
It should print the registered type without error.

#### Step 4: Commit

```bash
git add nodes/sockets.py nodes/__init__.py
git commit -m "Add 5 skysplat socket types with color-coding"
```

---

## Task A3: Base node class + lineage registry + workspace helpers

**Files:**
- Create: `nodes/base.py`
- Create: `tests/unit/test_lineage.py`
- Create: `tests/unit/test_workspace.py`
- Modify: `nodes/__init__.py` — register base module.

The base class manages: stable UUID, status property, parameter hash for staleness, JSON-serialized lineage (`cached_output_json`), and per-tree evaluation registry for Python-object-passing through wires.

#### Step 1: Write the failing tests — `tests/unit/test_lineage.py`

```python
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
```

#### Step 2: Write the failing tests — `tests/unit/test_workspace.py`

```python
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
```

#### Step 3: Run tests to verify failure

```bash
/tmp/skysplat_venv/bin/pytest tests/unit/test_lineage.py tests/unit/test_workspace.py -v
```
Expected: ImportError on `nodes.base`.

#### Step 4: Implement `nodes/base.py`

```python
"""SkysplatNode base class plus pure-Python helpers (lineage JSON,
workspace dir resolution, parameter hashing).

The pure helpers are at module top-level so pytest can import them
without bpy. The SkysplatNode class is gated behind the bpy import.
"""
from __future__ import annotations

import hashlib
import json
import uuid as uuid_module
from pathlib import Path
from typing import Any

try:
    import bpy
    from bpy.types import Node
    from bpy.props import StringProperty, EnumProperty, BoolProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    Node = object


# ----- Pure helpers (importable without bpy) -----

def lineage_to_json(lineage: dict) -> str:
    """Serialize a lineage dict to JSON. Path objects become strings."""
    def encode(obj: Any) -> Any:
        if isinstance(obj, Path):
            return {"__path__": str(obj)}
        if isinstance(obj, dict):
            return {k: encode(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [encode(v) for v in obj]
        return obj
    return json.dumps(encode(lineage))


def lineage_from_json(text: str) -> dict:
    """Deserialize a lineage dict produced by lineage_to_json.

    Returns {} for empty/invalid JSON (defensive — corrupt cache should
    be treated as 'no cache' rather than crash the node graph).
    """
    if not text:
        return {}
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}

    def decode(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "__path__" in obj and len(obj) == 1:
                return Path(obj["__path__"])
            return {k: decode(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [decode(v) for v in obj]
        return obj

    return decode(raw) if isinstance(raw, dict) else {}


def current_param_hash(params: dict, upstream_hashes: list) -> str:
    """Compute a stable hash from this node's parameters and the
    last_run_hash values of all connected upstream nodes.

    Order-insensitive over upstream_hashes (sorted) and dict keys
    (json's sort_keys).
    """
    payload = {
        "params": params,
        "upstream": sorted(upstream_hashes),
    }
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def default_workspace_dir(node_uuid: str, blend_path: str | None) -> Path:
    """Resolve the default workspace dir for a node.

    If the .blend has been saved, anchor under <blend_dir>/skysplat_workspace/<uuid>/.
    Otherwise fall back to ~/skysplat_workspace/<uuid>/.
    """
    if blend_path:
        return Path(blend_path).parent / "skysplat_workspace" / node_uuid
    return Path.home() / "skysplat_workspace" / node_uuid


# ----- SkysplatNode (Blender-only) -----

if HAS_BPY:

    _STATUS_ITEMS = [
        ("clean", "Clean", "Never run"),
        ("dirty", "Dirty", "Inputs or params changed since last run"),
        ("running", "Running", "Currently executing"),
        ("done", "Done", "Last run succeeded"),
        ("errored", "Errored", "Last run raised an error"),
    ]

    class SkysplatNode(Node):
        """Base class for all skysplat nodes."""
        bl_icon = "NODETREE"

        # Identity
        node_uuid: StringProperty(name="UUID", default="")

        # Per-run state — these survive .blend save/load via Blender's
        # standard property persistence.
        status: EnumProperty(name="Status", items=_STATUS_ITEMS, default="clean")
        last_run_hash: StringProperty(name="Last Run Hash", default="")
        last_error: StringProperty(name="Last Error", default="")
        cached_output_json: StringProperty(name="Cached Output", default="")

        # User-overridable workspace; empty means use default.
        workspace_dir_override: StringProperty(name="Workspace Dir", default="", subtype="DIR_PATH")

        @classmethod
        def poll(cls, ntree):
            return ntree.bl_idname == "SkySplatNodeTree"

        def init(self, context):
            """Called once when the node is created."""
            self.node_uuid = uuid_module.uuid4().hex

        def copy(self, original):
            """Shift-D — fresh identity, dirty status, no cached state."""
            self.node_uuid = uuid_module.uuid4().hex
            self.cached_output_json = ""
            self.last_run_hash = ""
            self.last_error = ""
            self.status = "dirty"

        # Subclasses override these.
        def params_dict(self) -> dict:
            """Return the parameter values that affect this node's output."""
            return {}

        def run(self, context):
            """Execute this node's work. Subclasses must override."""
            raise NotImplementedError

        # Common helpers used by subclasses.
        def get_workspace_dir(self) -> Path:
            if self.workspace_dir_override:
                return Path(bpy.path.abspath(self.workspace_dir_override))
            blend_path = bpy.data.filepath or ""
            return default_workspace_dir(self.node_uuid, blend_path)

        def get_log_path(self) -> Path:
            return self.get_workspace_dir() / "run.log"

        def store_output(self, lineage: dict, params: dict):
            self.cached_output_json = lineage_to_json(lineage)
            self.last_run_hash = current_param_hash(params, self._collect_upstream_hashes())
            self.last_error = ""
            self.status = "done"

        def store_error(self, message: str):
            self.last_error = message[:200]  # bpy StringProperty has length limits
            self.status = "errored"

        def get_cached_output(self) -> dict:
            return lineage_from_json(self.cached_output_json)

        def _collect_upstream_hashes(self) -> list:
            hashes = []
            for sock in self.inputs:
                for link in sock.links:
                    upstream = link.from_node
                    if hasattr(upstream, "last_run_hash"):
                        hashes.append(upstream.last_run_hash)
            return hashes

        def get_upstream_lineage(self, socket_name: str) -> dict | None:
            """Return the cached lineage object for a connected input socket,
            or None if disconnected/upstream-unrun."""
            sock = self.inputs.get(socket_name)
            if sock is None or not sock.links:
                return None
            upstream = sock.links[0].from_node
            if not hasattr(upstream, "get_cached_output"):
                return None
            cache = upstream.get_cached_output()
            return cache.get(sock.links[0].from_socket.identifier)


    classes = (SkysplatNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 5: Update `nodes/__init__.py`

Replace the modules tuple:

```python
from . import tree, sockets, base

_modules = (tree, sockets, base)
```

#### Step 6: Run tests

```bash
/tmp/skysplat_venv/bin/pytest tests/unit/test_lineage.py tests/unit/test_workspace.py -v
```
Expected: 7 passed (3 lineage round-trip + 1 invalid + 3 hash + 3 workspace = wait, recount).

Actually counting tests in the spec: 3 in `TestLineageRoundTrip` + 3 in `TestParamHashing` + 3 in `TestDefaultWorkspaceDir` = 9 new tests. Total: 35 + 9 = 44.

#### Step 7: Commit

```bash
git add nodes/base.py nodes/__init__.py tests/unit/test_lineage.py tests/unit/test_workspace.py
git commit -m "Add SkysplatNode base class with lineage, workspace, hashing helpers"
```

---

## Task A4: Add menu integration (no nodes yet — just submenu)

**Files:**
- Create: `nodes/add_menu.py`
- Modify: `nodes/__init__.py`

This adds a "SkySplat" submenu to the Add menu (Shift-A) of the SkySplat editor. The submenu is empty until source/pipeline node tasks add their entries.

#### Step 1: Create `nodes/add_menu.py`

```python
"""SkySplat node add-menu wiring.

Exposes a global registry that node modules append themselves to via
register_add_menu_entry(). The Add menu (Shift-A) reads from this
registry to populate the SkySplat submenu.
"""
from __future__ import annotations

try:
    import bpy
    from bpy.types import Menu
    HAS_BPY = True
except ImportError:
    HAS_BPY = False
    Menu = object


_entries: list[tuple[str, str]] = []  # (bl_idname, label)


def register_add_menu_entry(bl_idname: str, label: str) -> None:
    """Called by node modules at registration time to add themselves
    to the Shift-A menu."""
    _entries.append((bl_idname, label))


def clear_add_menu_entries() -> None:
    _entries.clear()


if HAS_BPY:

    class NODE_MT_skysplat_add(Menu):
        bl_idname = "NODE_MT_skysplat_add"
        bl_label = "SkySplat"

        def draw(self, context):
            layout = self.layout
            for idname, label in _entries:
                op = layout.operator("node.add_node", text=label)
                op.type = idname
                op.use_transform = True


    def _draw_skysplat_submenu(self, context):
        if context.space_data.tree_type == "SkySplatNodeTree":
            self.layout.menu(NODE_MT_skysplat_add.bl_idname, icon="NODETREE")


    classes = (NODE_MT_skysplat_add,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.NODE_MT_add.append(_draw_skysplat_submenu)

    def unregister():
        bpy.types.NODE_MT_add.remove(_draw_skysplat_submenu)
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        clear_add_menu_entries()

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Update `nodes/__init__.py`

```python
from . import tree, sockets, base, add_menu

_modules = (tree, sockets, base, add_menu)
```

#### Step 3: Manual smoke check

In Blender, switch an editor to SkySplat. Press Shift-A — there should be a "SkySplat" submenu with an empty list (no entries yet). The submenu must NOT appear in other node editors (Compositor, Geometry Nodes).

#### Step 4: Commit

```bash
git add nodes/add_menu.py nodes/__init__.py
git commit -m "Add SkySplat submenu to Shift-A in the SkySplat node editor"
```

---

# Stage B — Source Nodes

## Task B1: Video node

**Files:**
- Create: `nodes/video_node.py`
- Modify: `nodes/__init__.py` — register video module.

Single-input UI: file picker + display name. Output: `Video` socket. `run()` calls `services.video.load_video_into_vse` to put a strip in the scene's VSE, plus parses SRT via `services.srt.parse_srt_metadata`.

#### Step 1: Create `nodes/video_node.py`

```python
"""SkysplatVideoNode — points at a video file, loads it into the VSE
when run, and emits a Video lineage object."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import bpy
    from bpy.props import StringProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatVideoNode(SkysplatNode):
        bl_idname = "SkysplatVideoNode"
        bl_label = "Video"

        video_path: StringProperty(
            name="Video", default="", subtype="FILE_PATH",
            description="Path to a video file (mp4, mov, etc.)",
        )

        def init(self, context):
            super().init(context)
            self.outputs.new("SkysplatVideoSocket", "Video")

        def draw_buttons(self, context, layout):
            row = layout.row()
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            row.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.prop(self, "video_path", text="")
            layout.operator("skysplat_node.run", text="Run").node_name = self.name

        def params_dict(self) -> dict:
            return {"video_path": str(Path(bpy.path.abspath(self.video_path))) if self.video_path else ""}

        def run(self, context):
            from ..services.video import load_video_into_vse
            from ..services.srt import parse_srt_metadata

            if not self.video_path:
                raise RuntimeError("Video node has no video_path set")

            video_path = Path(bpy.path.abspath(self.video_path))
            if not video_path.exists():
                raise RuntimeError(f"Video file not found: {video_path}")

            strip_name = os.path.basename(str(video_path))
            strip = load_video_into_vse(context.scene, video_path, strip_name=strip_name)

            # SRT detection (same convention as the sidebar panel)
            srt_meta = None
            for ext in (".SRT", ".srt"):
                cand = video_path.with_suffix(ext)
                if cand.exists():
                    srt_meta = parse_srt_metadata(cand)
                    break

            output = {
                "Video": {
                    "path": video_path,
                    "source_id": video_path.stem,
                    "vse_strip_name": strip.name,
                    "vse_strip_start_frame": int(strip.frame_start),
                    "srt_focal_len_mm": srt_meta.get("focal_len_mm") if srt_meta else None,
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatVideoNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatVideoNode.bl_idname, "Video")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Add per-node Run operator (will be reused by all node types)

In `nodes/base.py`, after the SkysplatNode class definition (still inside `if HAS_BPY:`), append:

```python
    class SKYSPLAT_NODE_OT_run(bpy.types.Operator):
        """Run a single skysplat node by name."""
        bl_idname = "skysplat_node.run"
        bl_label = "Run Node"

        node_name: bpy.props.StringProperty()
        tree_name: bpy.props.StringProperty(default="")  # optional override

        def execute(self, context):
            tree = self._find_tree(context)
            if tree is None:
                self.report({'ERROR'}, "No SkySplatNodeTree active")
                return {'CANCELLED'}
            node = tree.nodes.get(self.node_name)
            if node is None:
                self.report({'ERROR'}, f"Node not found: {self.node_name}")
                return {'CANCELLED'}
            node.status = "running"
            node.last_error = ""
            try:
                node.run(context)
            except Exception as exc:
                node.store_error(str(exc))
                self.report({'ERROR'}, f"{node.bl_label}: {exc}")
                return {'CANCELLED'}
            self.report({'INFO'}, f"{node.bl_label} done")
            return {'FINISHED'}

        def _find_tree(self, context):
            if self.tree_name:
                return bpy.data.node_groups.get(self.tree_name)
            # Fallback: active tree in the editor where the operator was invoked
            space = context.space_data
            if space and getattr(space, "tree_type", "") == "SkySplatNodeTree":
                return space.node_tree
            # Last-resort: first SkySplatNodeTree in scene
            for ng in bpy.data.node_groups:
                if ng.bl_idname == "SkySplatNodeTree":
                    return ng
            return None


    classes = (SkysplatNode, SKYSPLAT_NODE_OT_run)
```

The existing `classes = (SkysplatNode,)` line should be replaced with the tuple shown above (`SkysplatNode, SKYSPLAT_NODE_OT_run`).

#### Step 3: Update `nodes/__init__.py`

```python
from . import tree, sockets, base, add_menu, video_node

_modules = (tree, sockets, base, add_menu, video_node)
```

#### Step 4: Manual smoke check

Reload addon. Open SkySplat editor. Shift-A → SkySplat → Video. A green-headed Video node appears with a file-picker. Pick a video file. Click Run. Status flips to "running" then "done"; the video appears in the VSE.

#### Step 5: Commit

```bash
git add nodes/video_node.py nodes/base.py nodes/__init__.py
git commit -m "Add Video source node and skysplat_node.run operator"
```

---

## Task B2: Frames Folder node

**Files:**
- Create: `nodes/frames_folder_node.py`
- Modify: `nodes/__init__.py`

Frames Folder is a pure source node — points at a directory of images, no scene side effects.

#### Step 1: Create `nodes/frames_folder_node.py`

```python
"""SkysplatFramesFolderNode — points at an existing folder of images
(extracted frames or original stills) and emits a Frames lineage object."""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    from bpy.props import StringProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatFramesFolderNode(SkysplatNode):
        bl_idname = "SkysplatFramesFolderNode"
        bl_label = "Frames Folder"

        folder_path: StringProperty(
            name="Folder", default="", subtype="DIR_PATH",
            description="Directory containing image frames (jpg/jpeg/png)",
        )

        def init(self, context):
            super().init(context)
            self.outputs.new("SkysplatFramesSocket", "Frames")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.prop(self, "folder_path", text="")
            layout.operator("skysplat_node.run", text="Run").node_name = self.name

        def params_dict(self) -> dict:
            return {"folder_path": str(Path(bpy.path.abspath(self.folder_path))) if self.folder_path else ""}

        def run(self, context):
            from ..services.frames import discover_frames

            if not self.folder_path:
                raise RuntimeError("Frames Folder node has no folder_path set")

            folder = Path(bpy.path.abspath(self.folder_path))
            images = discover_frames(folder)
            if len(images) == 0:
                raise RuntimeError(f"No images found in {folder}")

            output = {
                "Frames": {
                    "path": folder,
                    "source_id": folder.name,
                    "image_count": len(images),
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatFramesFolderNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatFramesFolderNode.bl_idname, "Frames Folder")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Update `nodes/__init__.py`

```python
from . import tree, sockets, base, add_menu, video_node, frames_folder_node

_modules = (tree, sockets, base, add_menu, video_node, frames_folder_node)
```

#### Step 3: Manual smoke check

Shift-A → SkySplat → Frames Folder. Pick a folder containing extracted frames. Click Run. Status → done. (No visible side effect since this is a pure source.)

#### Step 4: Commit

```bash
git add nodes/frames_folder_node.py nodes/__init__.py
git commit -m "Add Frames Folder source node"
```

---

# Stage C — Pipeline Nodes

## Task C1: Frame Extract node

**Files:**
- Create: `nodes/frame_extract_node.py`
- Modify: `nodes/__init__.py`

Takes a Video input, calls `services.frames.extract_frames`, emits a Frames lineage. The output frames go into the node's workspace dir.

#### Step 1: Create `nodes/frame_extract_node.py`

```python
"""SkysplatFrameExtractNode — extracts frames from an upstream Video
into the node's workspace dir."""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    from bpy.props import IntProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatFrameExtractNode(SkysplatNode):
        bl_idname = "SkysplatFrameExtractNode"
        bl_label = "Frame Extract"

        frame_start: IntProperty(name="Start", default=1, min=1)
        frame_end: IntProperty(name="End", default=250, min=1)
        frame_step: IntProperty(name="Step", default=5, min=1)

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatVideoSocket", "Video")
            self.outputs.new("SkysplatFramesSocket", "Frames")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            row = layout.row(align=True)
            row.prop(self, "frame_start")
            row.prop(self, "frame_end")
            row.prop(self, "frame_step")
            layout.operator("skysplat_node.run", text="Run").node_name = self.name

        def params_dict(self) -> dict:
            return {
                "frame_start": self.frame_start,
                "frame_end": self.frame_end,
                "frame_step": self.frame_step,
            }

        def run(self, context):
            from ..services.frames import extract_frames

            video_lineage = self.get_upstream_lineage("Video")
            if video_lineage is None:
                raise RuntimeError("Frame Extract requires an upstream Video node that has been Run")

            strip_name = video_lineage.get("vse_strip_name")
            if not strip_name:
                raise RuntimeError("Upstream Video has no VSE strip; Run the Video node first")

            out_dir = self.get_workspace_dir() / "frames"
            out_dir.mkdir(parents=True, exist_ok=True)

            count = extract_frames(
                context.scene,
                video_strip_name=strip_name,
                out_dir=out_dir,
                start=self.frame_start,
                end=self.frame_end,
                step=self.frame_step,
            )
            if count == 0:
                raise RuntimeError("No frames were written; check video strip and frame range")

            output = {
                "Frames": {
                    "path": out_dir,
                    "source_id": video_lineage.get("source_id", "unknown"),
                    "image_count": count,
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatFrameExtractNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatFrameExtractNode.bl_idname, "Frame Extract")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Update `nodes/__init__.py`

```python
from . import (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node,
)

_modules = (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node,
)
```

#### Step 3: Manual smoke check

Build graph: Video → Frame Extract. Run Video first, then run Frame Extract. Frames appear in `<workspace>/frames/`.

#### Step 4: Commit

```bash
git add nodes/frame_extract_node.py nodes/__init__.py
git commit -m "Add Frame Extract pipeline node"
```

---

## Task C2: COLMAP Reconstruct node

**Files:**
- Create: `nodes/colmap_node.py`
- Modify: `nodes/__init__.py`

Takes a single Frames input (multi-input deferred to phase 2.5). Calls `services.colmap.run_reconstruction`. Emits a ColmapModel lineage.

#### Step 1: Create `nodes/colmap_node.py`

```python
"""SkysplatColmapNode — runs COLMAP reconstruction on an upstream Frames
input. Single-source only in phase 2 MVP."""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    from bpy.props import EnumProperty, BoolProperty, StringProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatColmapNode(SkysplatNode):
        bl_idname = "SkysplatColmapNode"
        bl_label = "COLMAP Reconstruct"

        camera_model: EnumProperty(
            name="Camera Model",
            items=[
                ("SIMPLE_PINHOLE", "Simple Pinhole", ""),
                ("PINHOLE", "Pinhole", ""),
                ("OPENCV", "OpenCV", ""),
                ("OPENCV_FISHEYE", "OpenCV Fisheye", ""),
            ],
            default="SIMPLE_PINHOLE",
        )
        matching_type: EnumProperty(
            name="Matching",
            items=[
                ("exhaustive", "Exhaustive", ""),
                ("sequential", "Sequential", ""),
            ],
            default="exhaustive",
        )
        use_gpu: BoolProperty(name="Use GPU", default=True)
        colmap_executable: StringProperty(
            name="COLMAP", default="", subtype="FILE_PATH",
            description="Path to colmap binary (leave empty to use $PATH)",
        )

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatFramesSocket", "Frames")
            self.outputs.new("SkysplatColmapModelSocket", "Model")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.prop(self, "camera_model")
            layout.prop(self, "matching_type")
            layout.prop(self, "use_gpu")
            layout.prop(self, "colmap_executable", text="")
            layout.operator("skysplat_node.run", text="Run").node_name = self.name

        def params_dict(self) -> dict:
            return {
                "camera_model": self.camera_model,
                "matching_type": self.matching_type,
                "use_gpu": self.use_gpu,
                "colmap_executable": self.colmap_executable,
            }

        def run(self, context):
            from ..services.colmap import (
                run_reconstruction, FramesSource, ColmapParams, Manual,
            )

            frames_lineage = self.get_upstream_lineage("Frames")
            if frames_lineage is None:
                raise RuntimeError("COLMAP requires an upstream Frames input that has been Run")

            frames_path = frames_lineage.get("path")
            if not frames_path or not Path(frames_path).exists():
                raise RuntimeError(f"Upstream Frames path missing or doesn't exist: {frames_path}")

            sources = [FramesSource(
                path=Path(frames_path),
                source_id=frames_lineage.get("source_id", self.node_uuid),
                camera_model=Manual(model=self.camera_model, params=[]),
            )]
            params = ColmapParams(
                mode="joint",
                matching=self.matching_type,
                use_gpu=self.use_gpu,
                colmap_executable=self.colmap_executable or "colmap",
            )

            workspace = self.get_workspace_dir()
            workspace.mkdir(parents=True, exist_ok=True)
            log_path = self.get_log_path()

            result = run_reconstruction(sources, workspace, params, log_path=log_path)

            output = {
                "Model": {
                    "model_dir": result.model_dir,
                    "image_root": result.image_root,
                    "source_map": {str(k): v for k, v in result.source_map.items()},
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatColmapNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatColmapNode.bl_idname, "COLMAP Reconstruct")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Update `nodes/__init__.py`

```python
from . import (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, colmap_node,
)

_modules = (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, colmap_node,
)
```

#### Step 3: Manual smoke check

Build graph: Video → Frame Extract → COLMAP. Run each in order. The COLMAP run can take several minutes on a real dataset — Blender's UI will be unresponsive (synchronous). The async-task wrapping is a phase 2.5 task.

#### Step 4: Commit

```bash
git add nodes/colmap_node.py nodes/__init__.py
git commit -m "Add COLMAP Reconstruct pipeline node (single-source)"
```

---

## Task C3: Brush Dataset node

**Files:**
- Create: `nodes/brush_dataset_node.py`
- Modify: `nodes/__init__.py`

Takes a ColmapModel input. Calls `services.brush.prepare_dataset`. Emits a Dataset lineage.

#### Step 1: Create `nodes/brush_dataset_node.py`

```python
"""SkysplatBrushDatasetNode — prepares a Brush-compatible dataset from
an upstream COLMAP Model."""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatBrushDatasetNode(SkysplatNode):
        bl_idname = "SkysplatBrushDatasetNode"
        bl_label = "Brush Dataset"

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatColmapModelSocket", "Model")
            self.outputs.new("SkysplatDatasetSocket", "Dataset")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.operator("skysplat_node.run", text="Run").node_name = self.name

        def params_dict(self) -> dict:
            return {}

        def run(self, context):
            from ..services.brush import prepare_dataset

            model_lineage = self.get_upstream_lineage("Model")
            if model_lineage is None:
                raise RuntimeError("Brush Dataset requires an upstream COLMAP Model input")

            model_dir = model_lineage.get("model_dir")
            image_root = model_lineage.get("image_root")
            if not model_dir or not image_root:
                raise RuntimeError("Upstream COLMAP Model lineage missing model_dir or image_root")

            out_dir = self.get_workspace_dir() / "brush_dataset"
            prepare_dataset(Path(model_dir), Path(image_root), out_dir)

            source_map = model_lineage.get("source_map", {})
            output = {
                "Dataset": {
                    "dir": out_dir,
                    "source_map": source_map,
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatBrushDatasetNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatBrushDatasetNode.bl_idname, "Brush Dataset")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Update `nodes/__init__.py`

```python
from . import (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, colmap_node,
    brush_dataset_node,
)

_modules = (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, colmap_node,
    brush_dataset_node,
)
```

#### Step 3: Manual smoke check

Wire COLMAP → Brush Dataset. Run. `<workspace>/brush_dataset/sparse/0/` and `<workspace>/brush_dataset/images/` populate.

#### Step 4: Commit

```bash
git add nodes/brush_dataset_node.py nodes/__init__.py
git commit -m "Add Brush Dataset pipeline node"
```

---

## Task C4: Brush Train node

**Files:**
- Create: `nodes/brush_train_node.py`
- Modify: `nodes/__init__.py`

Takes a Dataset input. Calls `services.brush.run_training` to launch a Popen. Phase 2 MVP keeps it synchronous-ish — kicks off the subprocess and waits in a non-blocking-ish way (operator returns once the subprocess starts; the user can monitor via the View Output button in Stage D).

For MVP, the simplest behavior: launch subprocess, return immediately, store the Popen handle on the operator instance for the user to monitor. The status flips to "running" and stays there until the user explicitly checks (via a separate "Check Status" button — that's phase 2.5). For now, "Run" launches and returns; the user knows training is in progress.

#### Step 1: Create `nodes/brush_train_node.py`

```python
"""SkysplatBrushTrainNode — kicks off a Brush training subprocess."""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    from bpy.props import StringProperty, IntProperty, BoolProperty, FloatProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatBrushTrainNode(SkysplatNode):
        bl_idname = "SkysplatBrushTrainNode"
        bl_label = "Brush Train"

        brush_executable: StringProperty(
            name="Brush", default="", subtype="FILE_PATH",
            description="Path to brush_app binary",
        )
        total_steps: IntProperty(name="Total Steps", default=30000, min=100)
        max_resolution: IntProperty(name="Max Resolution", default=1920, min=128)
        with_viewer: BoolProperty(name="With Viewer", default=False)

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatDatasetSocket", "Dataset")
            self.outputs.new("SkysplatSplatSocket", "Splat")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.prop(self, "brush_executable", text="")
            layout.prop(self, "total_steps")
            layout.prop(self, "max_resolution")
            layout.prop(self, "with_viewer")
            layout.operator("skysplat_node.run", text="Run").node_name = self.name

        def params_dict(self) -> dict:
            return {
                "brush_executable": self.brush_executable,
                "total_steps": self.total_steps,
                "max_resolution": self.max_resolution,
                "with_viewer": self.with_viewer,
            }

        def run(self, context):
            from ..services.brush import run_training, BrushParams

            dataset_lineage = self.get_upstream_lineage("Dataset")
            if dataset_lineage is None:
                raise RuntimeError("Brush Train requires an upstream Dataset input")

            dataset_dir = dataset_lineage.get("dir")
            if not dataset_dir or not Path(dataset_dir).exists():
                raise RuntimeError(f"Upstream Dataset path missing or doesn't exist: {dataset_dir}")

            if not self.brush_executable:
                raise RuntimeError("Brush Train requires brush_executable to be set")

            export_path = self.get_workspace_dir() / "brush_output"
            export_path.mkdir(parents=True, exist_ok=True)

            params = BrushParams(
                executable=bpy.path.abspath(self.brush_executable),
                source_path=str(Path(dataset_dir)),
                export_path=str(export_path),
                total_steps=self.total_steps,
                max_resolution=self.max_resolution,
                with_viewer=self.with_viewer,
            )

            popen = run_training(params, log_path=self.get_log_path())

            # MVP: synchronous-ish — wait for completion before returning.
            # Phase 2.5 will replace this with modal-timer polling so the
            # UI stays responsive. For long trainings, the user will use
            # `with_viewer=True` to monitor externally.
            popen.wait()
            if popen.returncode != 0:
                raise RuntimeError(f"Brush training failed with code {popen.returncode}; see log: {self.get_log_path()}")

            output = {
                "Splat": {
                    "ply_path": str(export_path),  # path to dir of .ply outputs
                    "training_log": str(self.get_log_path()),
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatBrushTrainNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatBrushTrainNode.bl_idname, "Brush Train")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
```

#### Step 2: Update `nodes/__init__.py`

```python
from . import (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, colmap_node,
    brush_dataset_node, brush_train_node,
)

_modules = (
    tree, sockets, base, add_menu,
    video_node, frames_folder_node, frame_extract_node, colmap_node,
    brush_dataset_node, brush_train_node,
)
```

#### Step 3: Manual smoke check

Wire Brush Dataset → Brush Train. Set brush executable. Lower `total_steps` to ~500 for a fast smoke test. Run. Wait for completion (Blender unresponsive — known MVP limitation). `<workspace>/brush_output/` should contain a .ply.

#### Step 4: Commit

```bash
git add nodes/brush_train_node.py nodes/__init__.py
git commit -m "Add Brush Train pipeline node"
```

---

# Stage D — Polish

## Task D1: View Output button (path-to-clipboard)

**Files:**
- Modify: `nodes/base.py` — add a `skysplat_node.view_output` operator.
- Modify: All 6 node files — add the operator to `draw_buttons`.

Live tail is deferred to phase 2.5. MVP: a button that opens the log file with the OS's default text viewer.

#### Step 1: Add operator to `nodes/base.py`

After the `SKYSPLAT_NODE_OT_run` class (still inside `if HAS_BPY:`), append:

```python
    class SKYSPLAT_NODE_OT_view_output(bpy.types.Operator):
        """Open this node's run.log in the OS file viewer."""
        bl_idname = "skysplat_node.view_output"
        bl_label = "View Output"

        node_name: bpy.props.StringProperty()

        def execute(self, context):
            space = context.space_data
            tree = space.node_tree if space and getattr(space, "tree_type", "") == "SkySplatNodeTree" else None
            if tree is None:
                self.report({'ERROR'}, "Not in a SkySplat node editor")
                return {'CANCELLED'}
            node = tree.nodes.get(self.node_name)
            if node is None:
                self.report({'ERROR'}, f"Node not found: {self.node_name}")
                return {'CANCELLED'}
            log_path = node.get_log_path()
            if not log_path.exists():
                self.report({'WARNING'}, f"No log yet: {log_path}")
                return {'CANCELLED'}
            bpy.ops.wm.path_open(filepath=str(log_path))
            return {'FINISHED'}
```

Update the classes tuple:
```python
    classes = (SkysplatNode, SKYSPLAT_NODE_OT_run, SKYSPLAT_NODE_OT_view_output)
```

#### Step 2: Add View Output button to each node's `draw_buttons`

In each of the 6 node files (`video_node.py`, `frames_folder_node.py`, `frame_extract_node.py`, `colmap_node.py`, `brush_dataset_node.py`, `brush_train_node.py`), find the `Run` button line:

```python
            layout.operator("skysplat_node.run", text="Run").node_name = self.name
```

Replace with:

```python
            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name
```

#### Step 3: Manual smoke check

After running any node, a "T" icon (text editor) appears next to the Run button. Click it. The OS opens the log file.

#### Step 4: Commit

```bash
git add nodes/base.py nodes/video_node.py nodes/frames_folder_node.py nodes/frame_extract_node.py nodes/colmap_node.py nodes/brush_dataset_node.py nodes/brush_train_node.py
git commit -m "Add View Output button to all skysplat nodes"
```

---

## Task D2: Phase 2 wrap-up + smoke checklist

**Files:**
- Modify: `docs/release-checklist.md` — add a phase 2 section.

#### Step 1: Append to `docs/release-checklist.md`

Add this section after the existing Brush panel section:

```markdown
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
```

#### Step 2: Run unit tests

```bash
/tmp/skysplat_venv/bin/pytest -v
```
Expected: 44 passed (35 from phase 1 + 9 new).

#### Step 3: Commit

```bash
git add docs/release-checklist.md
git commit -m "Add phase 2 MVP smoke checklist"
```

---

# Plan Self-Review

**Spec coverage (MVP-scoped):**
- ✅ Custom NodeTree as new editor type — Task A1
- ✅ Custom socket types color-coded — Task A2
- ✅ Node base class with UUID, status, workspace, lineage — Task A3
- ✅ Add menu — Task A4
- ✅ All 6 MVP node types — Tasks B1, B2, C1, C2, C3, C4
- ✅ Per-node Run buttons — Task B1 (operator) reused everywhere
- ✅ View Output button (basic) — Task D1
- ✅ Shift-D fresh-UUID copy — implemented in SkysplatNode.copy() in Task A3
- ✅ NodeTree persistence (free from Blender) + cached_output_json — Task A3
- ❌ DEFERRED: bake walker, round-trip nodes, Camera Animation, COLMAP Merge, auto-naming, live log tail, async/RunningTask, multi-source COLMAP, Reveal Node, multi-input sockets

**Placeholder scan:** None — every step has working code.

**Type consistency:** SkysplatNode + 5 sockets + 6 node bl_idnames defined consistently. The skysplat_node.run and skysplat_node.view_output operators are referenced by name in 6 places — all `node_name` parameter usage matches.

**Imports:** `from ..services.X import Y` pattern (relative — Blender-friendly, learned from phase 1 dual-import bug). No conftest sys.path tricks needed for tests because the new pure helpers in `nodes.base` don't reach into sibling packages.

**Note on testing:** Most node code is bpy-coupled and isn't unit-testable without Blender. The pure helpers (`lineage_to_json`, `lineage_from_json`, `current_param_hash`, `default_workspace_dir`) ARE testable and have 9 tests. Manual smoke checklist in Task D2 covers the rest.

---

**End of phase 2 MVP plan.** When fully executed:
- 12 tasks across 4 stages
- New `nodes/` package with 11 modules
- 9 new pytest tests (44 total)
- 6 new node types + custom NodeTree editor
- Existing sidebar panels untouched
- Full pipeline (Video → Frames → COLMAP → Dataset → Train) wireable as a graph

Phase 2.5 (next plan) tackles: bake walker, round-trip nodes, Camera Animation, COLMAP Merge, async tasks, auto-naming, live log tail, and the multi-source COLMAP plumbing.
