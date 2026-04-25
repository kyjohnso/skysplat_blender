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
