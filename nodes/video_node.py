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
            self.draw_status(layout)
            layout.prop(self, "video_path", text="")
            self.draw_run_row(layout)

        def params_dict(self) -> dict:
            return {"video_path": str(Path(bpy.path.abspath(self.video_path))) if self.video_path else ""}

        def run(self, context):
            from ..services.video import load_video_into_vse, resolve_target_scene
            from ..services.srt import parse_srt_metadata

            if not self.video_path:
                raise RuntimeError("Video node has no video_path set")

            video_path = Path(bpy.path.abspath(self.video_path))
            if not video_path.exists():
                raise RuntimeError(f"Video file not found: {video_path}")

            target_scene = resolve_target_scene(context)
            strip_name = os.path.basename(str(video_path))
            strip = load_video_into_vse(target_scene, video_path, strip_name=strip_name)

            total_frames = int(strip.frame_final_duration)

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
                    "vse_strip_total_frames": total_frames,
                    "vse_scene_name": target_scene.name,
                    "srt_focal_len_mm": srt_meta.get("focal_len_mm") if srt_meta else None,
                }
            }
            self.store_output(output, self.params_dict())

            # Push this video's frame range into any connected Frame
            # Extract nodes. Running Video always refreshes them — so a
            # node duplicated from another video (Shift+D) picks up THIS
            # video's numbers, not the copied ones. Tweak the range after
            # running Video if you want a custom window.
            self._push_defaults_downstream(total_frames)

        def _push_defaults_downstream(self, total_frames: int) -> None:
            """Set frame_start=1, frame_end=total_frames, and a frame_step
            targeting ~150 extracted frames on every downstream Frame
            Extract node."""
            target_frame_count = 150
            step = max(1, int(total_frames / target_frame_count))
            for sock in self.outputs:
                for link in sock.links:
                    downstream = link.to_node
                    if downstream.bl_idname != "SkysplatFrameExtractNode":
                        continue
                    downstream.frame_start = 1
                    downstream.frame_end = total_frames
                    downstream.frame_step = step


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
