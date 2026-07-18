"""SkysplatColmapCamerasNode — keyframed Blender cameras from a COLMAP model.

Terminal side-effect node: one animated camera object per source video
(services/camera.py groups images by COLMAP camera_id, which per-folder
staging makes one-per-video). Frame numbers collide across videos, so one
camera each is the only correct shape — a single camera would teleport
between videos every frame.

Idempotent re-runs: cameras are reused by name (SkySplatCam_<source>), and
objects created by a previous run of THIS node that no longer match a
current source are removed instead of piling up.
"""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    from bpy.props import BoolProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatColmapCamerasNode(SkysplatNode):
        bl_idname = "SkysplatColmapCamerasNode"
        bl_label = "COLMAP Cameras"

        apply_scene_settings: BoolProperty(
            name="Set Scene Range/Resolution", default=True,
            description="Set the scene frame range to span the keyframes and "
                        "the render resolution to the first video's camera",
        )

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatColmapModelSocket", "Model")

        def draw_buttons(self, context, layout):
            icon_map = {
                "clean": "DOT", "dirty": "FILE_REFRESH", "running": "PLAY",
                "done": "CHECKMARK", "errored": "ERROR",
            }
            layout.label(text=self.status.title(), icon=icon_map.get(self.status, "DOT"))
            if self.last_error:
                layout.label(text=self.last_error[:80], icon="ERROR")
            layout.prop(self, "apply_scene_settings")

            cache = self.get_cached_output()
            names = cache.get("objects", []) if cache else []
            for n in names:
                layout.label(text=n, icon="CAMERA_DATA")

            row = layout.row(align=True)
            row.operator("skysplat_node.run", text="Run").node_name = self.name
            row.operator("skysplat_node.view_output", text="", icon="TEXT").node_name = self.name

        def params_dict(self) -> dict:
            return {"apply_scene_settings": self.apply_scene_settings}

        def run(self, context):
            from ..services.camera import build_camera_animations
            from ..services.colmap import read_model

            model_lineage = self.get_upstream_lineage("Model")
            if model_lineage is None:
                raise RuntimeError("COLMAP Cameras requires an upstream Model input that has been Run")
            model_dir = model_lineage.get("model_dir")
            if not model_dir or not Path(model_dir).exists():
                raise RuntimeError(f"Upstream model_dir missing or doesn't exist: {model_dir}")

            animations = build_camera_animations(read_model(Path(model_dir)))
            if not animations:
                raise RuntimeError("Model contains no images to animate")

            previous = set(self.get_cached_output().get("objects", []) or [])
            created = []
            for anim in animations:
                created.append(self._build_camera(context, anim))

            # Drop cameras from a previous run whose source disappeared.
            for stale_name in previous - set(created):
                stale = bpy.data.objects.get(stale_name)
                if stale is not None and stale.type == 'CAMERA':
                    data = stale.data
                    bpy.data.objects.remove(stale)
                    if data is not None and data.users == 0:
                        bpy.data.cameras.remove(data)

            if self.apply_scene_settings:
                frames = [k.frame for a in animations for k in a.keys]
                context.scene.frame_start = min(frames)
                context.scene.frame_end = max(frames)
                first = animations[0]
                if first.width and first.height:
                    context.scene.render.resolution_x = first.width
                    context.scene.render.resolution_y = first.height
                cam0 = bpy.data.objects.get(created[0])
                if cam0 is not None:
                    context.scene.camera = cam0

            output = {
                "objects": created,
                "sources": {a.source_id: len(a.keys) for a in animations},
            }
            self.store_output(output, self.params_dict())

        def _build_camera(self, context, anim) -> str:
            from ..services.coords import SENSOR_WIDTH_MM

            name = f"SkySplatCam_{anim.source_id}"
            obj = bpy.data.objects.get(name)
            if obj is None or obj.type != 'CAMERA':
                cam_data = bpy.data.cameras.new(name)
                obj = bpy.data.objects.new(name, cam_data)
                context.scene.collection.objects.link(obj)

            cam_data = obj.data
            cam_data.lens_unit = 'MILLIMETERS'
            cam_data.sensor_fit = 'HORIZONTAL'
            cam_data.sensor_width = SENSOR_WIDTH_MM
            if anim.focal_mm:
                cam_data.lens = anim.focal_mm

            if obj.animation_data:
                obj.animation_data_clear()
            obj.rotation_mode = 'QUATERNION'

            for key in anim.keys:
                obj.location = key.location
                obj.rotation_quaternion = key.quaternion
                obj.keyframe_insert(data_path="location", frame=key.frame)
                obj.keyframe_insert(data_path="rotation_quaternion", frame=key.frame)

            return obj.name


    classes = (SkysplatColmapCamerasNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatColmapCamerasNode.bl_idname, "COLMAP Cameras")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
