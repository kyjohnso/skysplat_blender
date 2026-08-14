"""SkysplatNode base class plus pure-Python helpers (lineage JSON,
workspace dir resolution, parameter hashing).

The pure helpers are at module top-level so pytest can import them
without bpy. The SkysplatNode class is gated behind the bpy import.
"""
from __future__ import annotations

import hashlib
import json
import re
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


def sanitize_workspace_name(name: str) -> str:
    """Turn a node name into a filesystem-friendly folder name.

    Blender guarantees node.name is unique within a tree, so the sanitized
    name is a stable, human-readable folder key (e.g. "COLMAP Reconstruct"
    -> "COLMAP_Reconstruct", "Video.001" -> "Video_001"). Runs of any
    non-word characters collapse to a single underscore.
    """
    safe = re.sub(r"[^\w-]+", "_", name.strip()).strip("_")
    return safe or "node"


def default_workspace_dir(step_label: str, node_uuid: str, blend_path: str | None) -> Path:
    """Resolve the default workspace dir for a node.

    If the .blend has been saved, anchor under
    <blend_dir>/skysplat_workspace/, otherwise ~/skysplat_workspace/.

    The folder key is the step type plus a short uuid, e.g.
    brush_train_3f2a9c1d/ — readable (runs of one step sort together)
    while collision-proof. Node NAMES are only unique within one tree,
    so name-keyed folders silently overwrote each other across trees,
    sessions with unsaved .blends (which share ~/skysplat_workspace),
    and delete/recreate cycles. uuids never collide, and Shift-D copies
    get fresh ones.
    """
    step = sanitize_workspace_name(step_label).lower()
    folder = f"{step}_{node_uuid[:8]}" if node_uuid else step
    if blend_path:
        return Path(blend_path).parent / "skysplat_workspace" / folder
    return Path.home() / "skysplat_workspace" / folder


def tail_text(path: Path, max_bytes: int = 256 * 1024) -> str:
    """Read up to the last max_bytes of a text file for log display.

    Returns "" if the file can't be read. When the file is larger than
    max_bytes, the partial leading line is dropped and a marker is
    prepended so the viewer shows a clean tail instead of a mid-line splice.
    """
    path = Path(path)
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                data = f.read()
                truncated = True
            else:
                data = f.read()
                truncated = False
    except OSError:
        return ""
    text = data.decode("utf-8", "replace")
    if truncated:
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
        text = f"…(showing last {max_bytes // 1024} KB)…\n" + text
    return text


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

        def effective_status(self) -> str:
            """Status with a draw-time dirty check: a node that ran but whose
            params (or upstream results) have since changed shows as dirty.

            Cheap enough per redraw — params_dict() is prop reads and the
            hash is over a small dict. This is what makes e.g. dragging the
            Transform node's empty in the viewport read back as "Dirty"
            without any depsgraph handler: the node editor repaints as soon
            as it next gets events.
            """
            if self.status == "done":
                try:
                    now = current_param_hash(self.params_dict(), self._collect_upstream_hashes())
                    if now != self.last_run_hash:
                        return "dirty"
                except Exception:
                    pass
            return self.status

        _STATUS_ICONS = {
            "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
            "done": "CHECKMARK", "errored": "ERROR",
        }

        def draw_status(self, layout):
            """Shared header block: status badge plus last error, if any."""
            status = self.effective_status()
            layout.label(text=status.title(), icon=self._STATUS_ICONS.get(status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")

        def draw_run_row(self, layout):
            """Shared footer row: Run, Stop (while running), log, workspace."""
            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            if self.status == "running":
                row.operator("skysplat_node.stop", text="", icon="CANCEL").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name
            row.operator("skysplat_node.open_workspace", text="", icon="FILE_FOLDER").node_name = self.name

        # Subclasses override these.
        def params_dict(self) -> dict:
            """Return the parameter values that affect this node's output."""
            return {}

        def run(self, context):
            """Execute this node's work synchronously. Subclasses must override."""
            raise NotImplementedError

        def build_job(self, context):
            """Optional: return a NodeJob for off-thread execution, or None.

            Nodes whose heavy work is a subprocess / file IO (COLMAP, Brush
            Train) override this to gather their inputs on the main thread
            and hand back a NodeJob the run operator polls without freezing
            the UI. Returning None means "run me synchronously via run()" —
            the default for bpy-bound nodes (Video, Frame Extract) whose work
            must stay on the main thread.
            """
            return None

        # Common helpers used by subclasses.
        def get_workspace_dir(self) -> Path:
            if self.workspace_dir_override:
                return Path(bpy.path.abspath(self.workspace_dir_override))
            if not self.node_uuid:
                # Nodes from blends predating node_uuid. Only reached from
                # run/operator contexts, where writing ID props is allowed.
                self.node_uuid = uuid_module.uuid4().hex
            blend_path = bpy.data.filepath or ""
            return default_workspace_dir(self.bl_label, self.node_uuid, blend_path)

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

    class SKYSPLAT_NODE_OT_run(bpy.types.Operator):
        """Run a single skysplat node by name.

        Background-capable nodes (those whose build_job() returns a NodeJob)
        run their heavy work on a worker thread while this operator goes
        modal, polling the job from a timer so Blender's UI stays responsive.
        Nodes that return None run synchronously on the main thread — the
        right place for bpy-bound work (VSE load, OpenGL frame render).
        """
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

            # Re-resolve the node by name each modal tick rather than holding
            # a direct reference — undo / node deletion would invalidate it.
            self._tree_name = tree.name
            self._node_name = node.name
            self._job = None
            self._timer = None

            node.status = "running"
            node.last_error = ""

            # Outputs land beside the .blend; warn if it's unsaved so the
            # user isn't surprised to find them in ~/skysplat_workspace.
            if not bpy.data.filepath and not node.workspace_dir_override:
                self.report(
                    {'WARNING'},
                    "Unsaved .blend — outputs go to ~/skysplat_workspace; "
                    "save your file to keep them with the project",
                )

            # Gather inputs on the main thread (this reads bpy). Background
            # nodes hand back a NodeJob; others return None to run inline.
            try:
                job = node.build_job(context)
            except Exception as exc:
                node.store_error(str(exc))
                self._tag_redraw(context)
                self.report({'ERROR'}, f"{node.bl_label}: {exc}")
                return {'CANCELLED'}

            if job is None:
                # Synchronous fallback for bpy-bound / trivial nodes.
                try:
                    node.run(context)
                except Exception as exc:
                    node.store_error(str(exc))
                    self._tag_redraw(context)
                    self.report({'ERROR'}, f"{node.bl_label}: {exc}")
                    return {'CANCELLED'}
                self._tag_redraw(context)
                self.report({'INFO'}, f"{node.bl_label} done")
                return {'FINISHED'}

            # Non-blocking path: run off-thread, poll from a timer.
            from .jobs import register_running
            self._job = job
            job.start()
            register_running(self._tree_name, self._node_name, job)
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.2, window=context.window)
            wm.modal_handler_add(self)
            self._tag_redraw(context)
            self.report({'INFO'}, f"{node.bl_label} started in background…")
            return {'RUNNING_MODAL'}

        def modal(self, context, event):
            if event.type != 'TIMER':
                return {'PASS_THROUGH'}
            if not self._job.finished:
                return {'PASS_THROUGH'}

            from .jobs import unregister_running
            self._remove_timer(context)
            unregister_running(self._tree_name, self._node_name)
            node = self._resolve_node()
            if node is None:
                # Node was deleted mid-run — nothing to write back.
                return {'CANCELLED'}

            if self._job.cancelled:
                node.store_error("Stopped")
                self._tag_redraw(context)
                self.report({'WARNING'}, f"{node.bl_label} stopped")
                return {'CANCELLED'}

            if self._job.error is not None:
                node.store_error(str(self._job.error))
                self._tag_redraw(context)
                self.report({'ERROR'}, f"{node.bl_label}: {self._job.error}")
                return {'CANCELLED'}

            node.store_output(self._job.result, self._job.params)
            self._tag_redraw(context)
            self.report({'INFO'}, f"{node.bl_label} done")
            return {'FINISHED'}

        def cancel(self, context):
            # Blender calls this if the operator is aborted (e.g. window closed).
            from .jobs import unregister_running
            if self._job is not None:
                self._job.cancel()
            self._remove_timer(context)
            unregister_running(self._tree_name, self._node_name)
            node = self._resolve_node()
            if node is not None and node.status == "running":
                node.store_error("Stopped")
                self._tag_redraw(context)

        def _resolve_node(self):
            tree = bpy.data.node_groups.get(self._tree_name)
            if tree is None:
                return None
            return tree.nodes.get(self._node_name)

        def _remove_timer(self, context):
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None

        def _tag_redraw(self, context):
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'NODE_EDITOR':
                        area.tag_redraw()

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

    class SKYSPLAT_NODE_OT_view_output(bpy.types.Operator):
        """Show this node's run.log in a Text editor, auto-scrolled to the
        bottom and live-following new output while the node is running.

        Reuses an existing Text editor if one is open; otherwise opens a
        dedicated window. Falls back to the OS file viewer if no editor can
        be created (e.g. headless).
        """
        bl_idname = "skysplat_node.view_output"
        bl_label = "View Output"

        node_name: bpy.props.StringProperty()
        tree_name: bpy.props.StringProperty(default="")

        def execute(self, context):
            tree = self._find_tree(context)
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

            self._tree_name = tree.name
            self._node_name = node.name
            self._log_path = log_path
            self._text_name = f"SkySplat Log: {node.name}"
            self._stamp = None
            self._settle = 3
            self._timer = None

            text = self._load_text()
            try:
                self._show_in_editor(context, text)
            except Exception as exc:
                self.report({'WARNING'}, f"Couldn't open Text editor ({exc}); opening externally")
                bpy.ops.wm.path_open(filepath=str(log_path))
                return {'FINISHED'}

            wm = context.window_manager
            self._timer = wm.event_timer_add(0.3, window=context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        def modal(self, context, event):
            if event.type != 'TIMER':
                return {'PASS_THROUGH'}

            text = bpy.data.texts.get(self._text_name)
            area = self._find_area_showing(text) if text else None
            if text is None or area is None:
                # User closed or repurposed the log view — stop following.
                self._remove_timer(context)
                return {'FINISHED'}

            changed = self._reload_if_changed(text)
            node = self._resolve_node()
            running = node is not None and node.status == "running"

            # Pin to the bottom while there's new output, and for a few ticks
            # after the area first appears (visible_lines is 0 until drawn).
            # Once the run is done and output settles, stop pinning so the
            # user can scroll freely.
            if changed or running or self._settle > 0:
                self._pin_bottom(area, text)

            if running:
                self._settle = 3
            elif not changed:
                self._settle -= 1
                if self._settle <= 0:
                    self._remove_timer(context)
                    return {'FINISHED'}
            return {'PASS_THROUGH'}

        def cancel(self, context):
            self._remove_timer(context)

        # ----- helpers -----
        def _load_text(self):
            text = bpy.data.texts.get(self._text_name)
            if text is None:
                text = bpy.data.texts.new(self._text_name)
            text.from_string(tail_text(self._log_path))
            self._stamp = self._file_stamp()
            return text

        def _file_stamp(self):
            try:
                st = self._log_path.stat()
                return (st.st_size, st.st_mtime)
            except OSError:
                return None

        def _reload_if_changed(self, text):
            stamp = self._file_stamp()
            if stamp != self._stamp:
                text.from_string(tail_text(self._log_path))
                self._stamp = stamp
                return True
            return False

        def _text_editors(self):
            for win in bpy.context.window_manager.windows:
                for area in win.screen.areas:
                    if area.type == 'TEXT_EDITOR' and area.spaces.active:
                        yield area

        def _find_area_showing(self, text):
            for area in self._text_editors():
                if area.spaces.active.text == text:
                    return area
            return None

        def _show_in_editor(self, context, text):
            area = self._find_area_showing(text)
            if area is None:
                existing = list(self._text_editors())
                if existing:
                    area = existing[0]
                else:
                    bpy.ops.wm.window_new()
                    win = context.window_manager.windows[-1]
                    area = win.screen.areas[0]
                    area.type = 'TEXT_EDITOR'
            space = area.spaces.active
            space.text = text
            space.show_line_numbers = True
            space.show_word_wrap = True
            area.tag_redraw()
            return area

        def _pin_bottom(self, area, text):
            """Scroll the log view to the bottom via the editor's own
            FILE_BOTTOM move. Manual `space.top` math doesn't work here:
            with word wrap on, `top` counts wrapped DISPLAY rows, not
            logical lines, so `top = lines - visible_lines` lands further
            and further above the real bottom as the log grows."""
            space = area.spaces.active
            n = len(text.lines)
            if n == 0:
                return
            win = self._window_of(area)
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            try:
                with bpy.context.temp_override(
                    window=win, area=area, region=region, space_data=space,
                ):
                    bpy.ops.text.move(type='FILE_BOTTOM')
            except Exception:
                # Fallback (exact when word wrap is off).
                vis = space.visible_lines
                space.top = max(0, n - vis) if vis and vis > 0 else max(0, n - 1)
                try:
                    text.cursor_set(n - 1)
                except Exception:
                    pass
            area.tag_redraw()

        def _window_of(self, area):
            for win in bpy.context.window_manager.windows:
                for a in win.screen.areas:
                    if a == area:
                        return win
            return None

        def _resolve_node(self):
            tree = bpy.data.node_groups.get(self._tree_name)
            if tree is None:
                return None
            return tree.nodes.get(self._node_name)

        def _remove_timer(self, context):
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None

        def _find_tree(self, context):
            if self.tree_name:
                return bpy.data.node_groups.get(self.tree_name)
            space = context.space_data
            if space and getattr(space, "tree_type", "") == "SkySplatNodeTree":
                return space.node_tree
            for ng in bpy.data.node_groups:
                if ng.bl_idname == "SkySplatNodeTree":
                    return ng
            return None

    class SKYSPLAT_NODE_OT_stop(bpy.types.Operator):
        """Stop a running node's subprocess (COLMAP / Brush)."""
        bl_idname = "skysplat_node.stop"
        bl_label = "Stop Node"

        node_name: bpy.props.StringProperty()
        tree_name: bpy.props.StringProperty(default="")

        # Reuse the run operator's tree resolution.
        _find_tree = SKYSPLAT_NODE_OT_run._find_tree

        def execute(self, context):
            from .jobs import get_running
            tree = self._find_tree(context)
            tree_name = tree.name if tree is not None else self.tree_name
            job = get_running(tree_name, self.node_name)
            if job is None:
                self.report({'WARNING'}, "Nothing running for this node")
                return {'CANCELLED'}
            job.cancel()
            self.report({'INFO'}, f"Stopping {self.node_name}…")
            return {'FINISHED'}

    class SKYSPLAT_NODE_OT_open_workspace(bpy.types.Operator):
        """Open this node's workspace folder in the system file browser"""
        bl_idname = "skysplat_node.open_workspace"
        bl_label = "Open Workspace Folder"

        node_name: bpy.props.StringProperty()
        tree_name: bpy.props.StringProperty(default="")

        _find_tree = SKYSPLAT_NODE_OT_run._find_tree

        def execute(self, context):
            tree = self._find_tree(context)
            node = tree.nodes.get(self.node_name) if tree else None
            if node is None:
                self.report({'ERROR'}, f"Node not found: {self.node_name}")
                return {'CANCELLED'}
            workspace = node.get_workspace_dir()
            # A node that hasn't run yet has no folder; make it so the
            # browser has something to open.
            workspace.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.path_open(filepath=str(workspace))
            return {'FINISHED'}

    # Not registered as a standalone class — subclasses register themselves.
    # Blender discovers annotated properties through the MRO when subclasses
    # are registered.
    classes = (
        SKYSPLAT_NODE_OT_run,
        SKYSPLAT_NODE_OT_view_output,
        SKYSPLAT_NODE_OT_stop,
        SKYSPLAT_NODE_OT_open_workspace,
    )

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
