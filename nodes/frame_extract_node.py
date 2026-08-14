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
            self.draw_status(layout)
            col = layout.column(align=True)
            col.prop(self, "frame_start")
            col.prop(self, "frame_end")
            col.prop(self, "frame_step")
            self.draw_run_row(layout)

        def params_dict(self) -> dict:
            return {
                "frame_start": self.frame_start,
                "frame_end": self.frame_end,
                "frame_step": self.frame_step,
            }

        def run(self, context):
            from ..services.frames import extract_frames
            from ..services.video import resolve_target_scene

            video_lineage = self.get_upstream_lineage("Video")
            if video_lineage is None:
                raise RuntimeError("Frame Extract requires an upstream Video node that has been Run")

            strip_name = video_lineage.get("vse_strip_name")
            if not strip_name:
                raise RuntimeError("Upstream Video has no VSE strip; Run the Video node first")

            # Use the same scene the Video node loaded into. Fall back
            # to live resolution if the lineage predates the fix.
            scene_name = video_lineage.get("vse_scene_name")
            target_scene = bpy.data.scenes.get(scene_name) if scene_name else None
            if target_scene is None:
                target_scene = resolve_target_scene(context)

            out_dir = self.get_workspace_dir() / "frames"
            out_dir.mkdir(parents=True, exist_ok=True)

            count = extract_frames(
                target_scene,
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
