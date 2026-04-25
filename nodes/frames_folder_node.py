"""SkysplatFramesFolderNode — points at an existing folder of images
(extracted frames or original stills) and emits a Frames lineage object."""
from __future__ import annotations

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

    class SkysplatFramesFolderNode(SkysplatNode):
        bl_idname = "SkysplatFramesFolderNode"
        bl_label = "Frames Folder"

        folder_path: StringProperty(
            name="Folder", default="", subtype="DIR_PATH",
            description="Directory containing image frames (jpg/jpeg/png)",
        )

        def init(self, context):
            super().init(context)
            self.outputs.new("SkysplatFramesSocket", "Frames")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.prop(self, "folder_path", text="")
            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name

        def params_dict(self) -> dict:
            return {"folder_path": str(Path(bpy.path.abspath(self.folder_path))) if self.folder_path else ""}

        def run(self, context):
            from ..services.frames import discover_frames

            if not self.folder_path:
                raise RuntimeError("Frames Folder node has no folder_path set")

            folder = Path(bpy.path.abspath(self.folder_path))
            images = discover_frames(folder)
            if len(images) == 0:
                raise RuntimeError(f"No images found in {folder}")

            output = {
                "Frames": {
                    "path": folder,
                    "source_id": folder.name,
                    "image_count": len(images),
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatFramesFolderNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatFramesFolderNode.bl_idname, "Frames Folder")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
