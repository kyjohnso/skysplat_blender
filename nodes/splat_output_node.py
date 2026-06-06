"""SkysplatSplatOutputNode — terminal node that consumes a Splat input and
lists the generated .ply files on the node, each with a click-to-copy button.

Intended as a hand-off point: copy a splat's absolute path and paste it into
BlendSplat's `splat.import` Path socket (or any other importer)."""
from __future__ import annotations

import re
from pathlib import Path

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


def _iter_key(p: str):
    """Sort key so export_5000.ply < export_30000.ply (numeric, not lexical)."""
    m = re.search(r"(\d+)", Path(p).stem)
    return (int(m.group(1)) if m else -1, Path(p).name)


if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SKYSPLAT_NODE_OT_copy_path(bpy.types.Operator):
        """Copy this splat's absolute path to the clipboard."""
        bl_idname = "skysplat_node.copy_path"
        bl_label = "Copy Path"

        path: bpy.props.StringProperty()

        def execute(self, context):
            if not self.path:
                self.report({'WARNING'}, "No path to copy")
                return {'CANCELLED'}
            context.window_manager.clipboard = self.path
            self.report({'INFO'}, f"Copied: {self.path}")
            return {'FINISHED'}

    class SkysplatSplatOutputNode(SkysplatNode):
        bl_idname = "SkysplatSplatOutputNode"
        bl_label = "Splat Output"

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatSplatSocket", "Splat")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")

            cache = self.get_cached_output()
            files = cache.get("files", []) if cache else []
            if files:
                layout.label(text=f"{len(files)} splat(s) — click to copy path:")
                col = layout.column(align=True)
                for f in files:
                    op = col.operator("skysplat_node.copy_path", text=Path(f).name, icon="COPYDOWN")
                    op.path = f
            elif self.status == "done":
                layout.label(text="No .ply files found", icon="INFO")
            else:
                layout.label(text="Run to list generated splats", icon="INFO")

            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name

        def params_dict(self) -> dict:
            return {}

        def run(self, context):
            lineage = self.get_upstream_lineage("Splat")
            if lineage is None:
                raise RuntimeError("Splat Output requires an upstream Splat input that has been Run")

            ply_path = lineage.get("ply_path")
            if not ply_path:
                raise RuntimeError("Upstream Splat lineage has no ply_path")

            target = Path(ply_path)
            if not target.exists():
                raise RuntimeError(f"Splat path does not exist: {target}")

            if target.is_file() and target.suffix.lower() == ".ply":
                files = [str(target)]
            else:
                files = sorted((str(p) for p in target.glob("*.ply")), key=_iter_key)
            if not files:
                raise RuntimeError(f"No .ply files found in {target}")

            self.store_output({"dir": str(target), "files": files}, self.params_dict())


    classes = (SKYSPLAT_NODE_OT_copy_path, SkysplatSplatOutputNode)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatSplatOutputNode.bl_idname, "Splat Output")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
