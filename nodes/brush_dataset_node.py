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
