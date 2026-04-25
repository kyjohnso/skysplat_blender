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

    # Not registered as a standalone class — subclasses register themselves.
    # Blender discovers annotated properties through the MRO when subclasses
    # are registered.
    classes = ()

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
