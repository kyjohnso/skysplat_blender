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
    from ..config import get_default_brush_path

    class SkysplatBrushTrainNode(SkysplatNode):
        bl_idname = "SkysplatBrushTrainNode"
        bl_label = "Brush Train"

        brush_executable: StringProperty(
            name="Brush", default=get_default_brush_path(), subtype="FILE_PATH",
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
            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name

        def params_dict(self) -> dict:
            return {
                "brush_executable": self.brush_executable,
                "total_steps": self.total_steps,
                "max_resolution": self.max_resolution,
                "with_viewer": self.with_viewer,
            }

        def build_job(self, context):
            from ..services.brush import run_training, BrushParams
            from .jobs import NodeJob

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
            log_path = self.get_log_path()

            # Runs on a worker thread: launch Brush and wait on it there so
            # Blender's main thread stays responsive. register_proc lets the
            # run operator terminate training if the op is cancelled.
            def work(register_proc):
                popen = run_training(params, log_path=log_path)
                register_proc(popen)
                popen.wait()
                if popen.returncode != 0:
                    raise RuntimeError(
                        f"Brush training failed with code {popen.returncode}; see log: {log_path}"
                    )
                return {
                    "Splat": {
                        "ply_path": str(export_path),  # path to dir of .ply outputs
                        "training_log": str(log_path),
                    }
                }

            return NodeJob(work, self.params_dict())

        def run(self, context):
            job = self.build_job(context)
            output = job.run_blocking()
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
