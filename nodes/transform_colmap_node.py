"""SkysplatTransformColmapNode — bake a world transform into a COLMAP model.

ColmapModel -> ColmapModel pass-through: everything downstream (Brush
Dataset, Export, Cameras) consumes the aligned model in one coordinate
frame. The transform comes from a referenced object (drag an empty around
to align, same muscle memory as the sidebar's COLMAP_Root workflow) or,
with no object set, from explicit loc/rot/scale fields on the node.

The object's matrix is composed with the shared COLMAP->Blender convention
(services/coords.py), so with an identity transform this produces exactly
what the sidebar's "Export Transformed Model" writes for an unmoved root.
"""
from __future__ import annotations

import shutil
from pathlib import Path

try:
    import bpy
    from bpy.props import PointerProperty, FloatVectorProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

if HAS_BPY:
    import math
    from mathutils import Euler, Matrix

    from .base import SkysplatNode, SKYSPLAT_NODE_OT_run, sanitize_workspace_name
    from .add_menu import register_add_menu_entry

    class SkysplatTransformColmapNode(SkysplatNode):
        bl_idname = "SkysplatTransformColmapNode"
        bl_label = "Transform COLMAP"

        transform_object: PointerProperty(
            name="Object",
            type=bpy.types.Object,
            description="Object (usually an empty) whose world matrix is the "
                        "transform to bake in; leave empty to use the fields below",
        )
        # Named transform_* to avoid shadowing bpy.types.Node.location (the
        # node's position in the editor).
        transform_location: FloatVectorProperty(name="Location", size=3, subtype="TRANSLATION")
        transform_rotation: FloatVectorProperty(name="Rotation", size=3, subtype="EULER")
        transform_scale: FloatVectorProperty(name="Scale", size=3, subtype="XYZ", default=(1.0, 1.0, 1.0))

        def init(self, context):
            super().init(context)
            self.inputs.new("SkysplatColmapModelSocket", "Model")
            self.outputs.new("SkysplatColmapModelSocket", "Model")

        def draw_buttons(self, context, layout):
            self.draw_status(layout)
            row = layout.row(align=True)
            op = row.operator("skysplat_node.transform_show_preview",
                              text="Show in Viewport", icon="HIDE_OFF")
            op.node_name = self.name
            op = row.operator("skysplat_node.transform_remove_preview",
                              text="", icon="X")
            op.node_name = self.name
            layout.prop(self, "transform_object")
            if self.transform_object is None:
                col = layout.column(align=True)
                col.prop(self, "transform_location")
                col.prop(self, "transform_rotation")
                col.prop(self, "transform_scale")
            self.draw_run_row(layout)

        def _world_matrix(self) -> Matrix:
            if self.transform_object is not None:
                return self.transform_object.matrix_world.copy()
            return Matrix.LocRotScale(
                self.transform_location,
                Euler(self.transform_rotation, 'XYZ'),
                self.transform_scale,
            )

        def params_dict(self) -> dict:
            # Flatten the effective matrix so moving the empty (or editing the
            # fields) dirties the node. Rounded to keep the hash stable against
            # float noise from the depsgraph.
            mat = self._world_matrix()
            return {
                "matrix": [round(v, 6) for row in mat for v in row],
            }

        def run(self, context):
            from ..services.colmap import read_model, write_model
            from ..services.coords import export_world_transform
            from ..services.transform import apply_transform

            model_lineage = self.get_upstream_lineage("Model")
            if model_lineage is None:
                raise RuntimeError("Transform COLMAP requires an upstream Model input that has been Run")
            model_dir = model_lineage.get("model_dir")
            if not model_dir or not Path(model_dir).exists():
                raise RuntimeError(f"Upstream model_dir missing or doesn't exist: {model_dir}")

            world_xform = export_world_transform(self._world_matrix())

            model = read_model(Path(model_dir))
            transformed = apply_transform(model, world_xform)

            out_dir = self.get_workspace_dir() / "transformed" / "sparse" / "0"
            # Overwrite cleanly — a leftover model in the other format would
            # shadow the fresh one for format-autodetecting readers.
            if out_dir.exists():
                shutil.rmtree(out_dir)
            write_model(transformed, out_dir, ext=".bin")

            output = {
                "Model": {
                    "model_dir": out_dir,
                    # Frames on disk are untouched by a world transform.
                    "image_root": model_lineage.get("image_root"),
                    "source_map": model_lineage.get("source_map", {}),
                }
            }
            self.store_output(output, self.params_dict())


    class SKYSPLAT_NODE_OT_transform_show_preview(bpy.types.Operator):
        """Import the upstream COLMAP model as a point cloud under a root
        empty, and set it as this node's transform object. Align the empty
        in the viewport, then Run to bake. Click again to refresh the
        points after an upstream re-run (the root's transform is kept)."""
        bl_idname = "skysplat_node.transform_show_preview"
        bl_label = "Show COLMAP Preview"
        bl_options = {'UNDO'}

        node_name: bpy.props.StringProperty()
        tree_name: bpy.props.StringProperty(default="")

        _find_tree = SKYSPLAT_NODE_OT_run._find_tree

        def execute(self, context):
            from ..services.colmap_view import import_model_preview

            tree = self._find_tree(context)
            node = tree.nodes.get(self.node_name) if tree else None
            if node is None:
                self.report({'ERROR'}, f"Node not found: {self.node_name}")
                return {'CANCELLED'}
            lineage = node.get_upstream_lineage("Model")
            model_dir = lineage.get("model_dir") if lineage else None
            if not model_dir or not Path(model_dir).exists():
                self.report({'ERROR'}, "No upstream model — Run the connected Model node first")
                return {'CANCELLED'}

            try:
                root = import_model_preview(
                    context.scene, Path(model_dir),
                    sanitize_workspace_name(node.name), node.node_uuid)
            except Exception as exc:
                self.report({'ERROR'}, f"Preview failed: {exc}")
                return {'CANCELLED'}

            node.transform_object = root
            for obj in context.selected_objects:
                obj.select_set(False)
            root.select_set(True)
            context.view_layer.objects.active = root
            self.report({'INFO'}, f"Preview loaded — transform {root.name} to align, then Run")
            return {'FINISHED'}

    class SKYSPLAT_NODE_OT_transform_remove_preview(bpy.types.Operator):
        """Remove this node's viewport preview objects"""
        bl_idname = "skysplat_node.transform_remove_preview"
        bl_label = "Remove COLMAP Preview"
        bl_options = {'UNDO'}

        node_name: bpy.props.StringProperty()
        tree_name: bpy.props.StringProperty(default="")

        _find_tree = SKYSPLAT_NODE_OT_run._find_tree

        def execute(self, context):
            from ..services.colmap_view import remove_preview

            tree = self._find_tree(context)
            node = tree.nodes.get(self.node_name) if tree else None
            if node is None:
                self.report({'ERROR'}, f"Node not found: {self.node_name}")
                return {'CANCELLED'}
            # The PointerProperty goes None on its own when the root is
            # deleted; the baked transform_* fields are untouched.
            if remove_preview(node.node_uuid):
                self.report({'INFO'}, "Preview removed")
            else:
                self.report({'WARNING'}, "No preview to remove")
            return {'FINISHED'}

    classes = (
        SkysplatTransformColmapNode,
        SKYSPLAT_NODE_OT_transform_show_preview,
        SKYSPLAT_NODE_OT_transform_remove_preview,
    )

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatTransformColmapNode.bl_idname, "Transform COLMAP")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
