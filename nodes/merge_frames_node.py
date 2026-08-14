"""SkysplatMergeFramesNode — combine several Frames inputs into one frame set
with per-video subfolders, so a single COLMAP reconstruction can solve all
videos jointly (one camera per video via --single_camera_per_folder).

The node auto-grows its inputs: there's always one empty trailing Frames slot,
and a new one appears as you connect videos (custom sockets can't be true
multi-input, so this is the standard dynamic-socket pattern)."""
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

    class SkysplatMergeFramesNode(SkysplatNode):
        bl_idname = "SkysplatMergeFramesNode"
        bl_label = "Merge Frames"

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatFramesSocket", "Frames")
            self.outputs.new("SkysplatFramesSocket", "Frames")

        def update(self):
            """Keep exactly one empty trailing Frames input as videos connect."""
            try:
                self._sync_inputs()
            except Exception:
                # update() runs in many contexts; never raise out of it.
                pass

        def _sync_inputs(self):
            # Drop redundant trailing empties (keep a single one).
            while len(self.inputs) >= 2 and not self.inputs[-1].is_linked and not self.inputs[-2].is_linked:
                self.inputs.remove(self.inputs[-1])
            # Ensure there is a trailing empty to connect the next video to.
            if len(self.inputs) == 0 or self.inputs[-1].is_linked:
                self.inputs.new("SkysplatFramesSocket", "Frames")

        def draw_buttons(self, context, layout):
            self.draw_status(layout)
            connected = sum(1 for s in self.inputs if s.is_linked)
            layout.label(text=f"{connected} video(s) connected")
            self.draw_run_row(layout)

        def params_dict(self) -> dict:
            return {}

        def _socket_lineage(self, sock):
            """Cached lineage for a specific input socket (inputs share the
            name 'Frames', so we can't look up by name)."""
            if not sock.links:
                return None
            link = sock.links[0]
            upstream = link.from_node
            if not hasattr(upstream, "get_cached_output"):
                return None
            return upstream.get_cached_output().get(link.from_socket.identifier)

        def run(self, context):
            from ..services.frames import merge_frame_dirs, discover_frames

            sources = []
            for sock in self.inputs:
                if not sock.is_linked:
                    continue
                lineage = self._socket_lineage(sock)
                if lineage is None:
                    raise RuntimeError("A connected Frames input hasn't been Run yet")
                path = lineage.get("path")
                if not path or not Path(path).exists():
                    raise RuntimeError(f"Upstream frames path missing or doesn't exist: {path}")
                source_id = lineage.get("source_id") or Path(path).name
                sources.append((source_id, Path(path)))

            if len(sources) < 2:
                raise RuntimeError("Merge Frames needs at least 2 connected Frames inputs")

            merged_root = self.get_workspace_dir() / "merged"
            mapping = merge_frame_dirs(sources, merged_root)
            total = sum(len(discover_frames(src)) for _, src in sources)

            output = {
                "Frames": {
                    "path": merged_root,
                    "source_id": self.node_uuid,
                    "image_count": total,
                    "sources": mapping,  # {subdir_name: original source_id}
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatMergeFramesNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatMergeFramesNode.bl_idname, "Merge Frames")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
