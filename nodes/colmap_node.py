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
            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name

        def params_dict(self) -> dict:
            return {
                "camera_model": self.camera_model,
                "matching_type": self.matching_type,
                "use_gpu": self.use_gpu,
                "colmap_executable": self.colmap_executable,
            }

        def build_job(self, context):
            from ..services.colmap import (
                run_reconstruction, FramesSource, ColmapParams, Manual,
            )
            from .jobs import NodeJob

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

            # Runs on a worker thread — pure subprocess + file IO, no bpy.
            def work(register_proc):
                result = run_reconstruction(sources, workspace, params, log_path=log_path)
                return {
                    "Model": {
                        "model_dir": result.model_dir,
                        "image_root": result.image_root,
                        "source_map": {str(k): v for k, v in result.source_map.items()},
                    }
                }

            return NodeJob(work, self.params_dict())

        def run(self, context):
            job = self.build_job(context)
            output = job.run_blocking()
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
