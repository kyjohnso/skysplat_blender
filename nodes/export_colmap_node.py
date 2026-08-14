"""SkysplatExportColmapNode — write an upstream COLMAP model to a chosen
directory as .bin, in the conventional sparse/0 layout.

Terminal-ish node: put it after Transform COLMAP to persist the aligned
model somewhere outside the node workspace (for other tools, archives,
or a Brush run driven by hand). The written path gets a click-to-copy
button on the node.
"""
from __future__ import annotations

import shutil
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

    class SkysplatExportColmapNode(SkysplatNode):
        bl_idname = "SkysplatExportColmapNode"
        bl_label = "Export COLMAP"

        export_path: StringProperty(
            name="Export Dir", default="", subtype="DIR_PATH",
            description="Directory to write the model into (as sparse/0/*.bin)",
        )

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatColmapModelSocket", "Model")

        def draw_buttons(self, context, layout):
            self.draw_status(layout)
            layout.prop(self, "export_path", text="")

            cache = self.get_cached_output()
            written = cache.get("dir") if cache else None
            if written:
                op = layout.operator("skysplat_node.copy_path", text=str(written), icon="COPYDOWN")
                op.path = str(written)

            self.draw_run_row(layout)

        def params_dict(self) -> dict:
            return {"export_path": self.export_path}

        def run(self, context):
            from ..services.colmap import read_model, write_model

            model_lineage = self.get_upstream_lineage("Model")
            if model_lineage is None:
                raise RuntimeError("Export COLMAP requires an upstream Model input that has been Run")
            model_dir = model_lineage.get("model_dir")
            if not model_dir or not Path(model_dir).exists():
                raise RuntimeError(f"Upstream model_dir missing or doesn't exist: {model_dir}")
            if not self.export_path:
                raise RuntimeError("Set an export directory first")

            export_root = Path(bpy.path.abspath(self.export_path))
            out_dir = export_root / "sparse" / "0"
            if out_dir.exists():
                shutil.rmtree(out_dir)

            # Read + rewrite (rather than raw file copy) so any model format
            # (.txt or .bin) upstream lands as .bin here.
            model = read_model(Path(model_dir))
            write_model(model, out_dir, ext=".bin")

            self.store_output({"dir": str(out_dir)}, self.params_dict())


    classes = (SkysplatExportColmapNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatExportColmapNode.bl_idname, "Export COLMAP")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
