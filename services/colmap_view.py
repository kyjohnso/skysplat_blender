"""Import a COLMAP model into the Blender scene as a viewable point cloud
under a root empty.

This is the viewport preview for the node graph's Transform COLMAP node:
the point cloud is parented to the root, the node's transform_object points
at the root, and the user aligns with normal viewport tools. Previews are
keyed by the owning node's uuid (custom prop "skysplat_node_uuid") so
re-importing refreshes in place — and deliberately keeps the root's current
transform, so refreshing after an upstream re-run doesn't wreck an
alignment in progress.

Cameras are not imported here: the preview exists to judge alignment and
scale, the point cloud is what you align, and the COLMAP Cameras node
already covers camera visualization without bloating the scene with
hundreds of camera objects.

point_cloud_data() is pure so pytest can cover it without bpy.
"""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    HAS_BPY = True
except ImportError:
    HAS_BPY = False

from .colmap import read_model

NODE_UUID_PROP = "skysplat_node_uuid"


def point_cloud_data(points3D: dict):
    """(verts, colors) lists for a COLMAP points3D dict.

    verts are xyz tuples in COLMAP coordinates (the root empty's transform,
    composed with the shared COLMAP->Blender convention at export time, is
    what maps them into the scene). colors are RGBA in 0..1.
    """
    verts = []
    colors = []
    for point in points3D.values():
        verts.append((float(point.xyz[0]), float(point.xyz[1]), float(point.xyz[2])))
        colors.append((point.rgb[0] / 255.0, point.rgb[1] / 255.0, point.rgb[2] / 255.0, 1.0))
    return verts, colors


if HAS_BPY:

    def find_preview_root(node_uuid: str):
        """The preview root empty owned by a node, or None."""
        for obj in bpy.data.objects:
            if obj.get(NODE_UUID_PROP) == node_uuid and obj.get("colmap_root"):
                return obj
        return None

    def _find_preview_collection(node_uuid: str):
        for coll in bpy.data.collections:
            if coll.get(NODE_UUID_PROP) == node_uuid:
                return coll
        return None

    def _remove_object(obj):
        mesh = obj.data if obj.type == 'MESH' else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    def import_model_preview(scene, model_path: Path, name: str, node_uuid: str):
        """Import (or refresh) a COLMAP model preview for a node.

        Creates collection 'COLMAP_Preview_<name>' with a 'COLMAP_Root_<name>'
        empty parenting a point cloud mesh (one vertex per 3D point, colors
        in a point-domain "Col" attribute — the legacy loop-domain vertex
        colors would be empty on a faceless mesh).

        On refresh, the existing root and its world transform are kept;
        only the point cloud is rebuilt. Returns the root empty.
        """
        model = read_model(Path(model_path))

        coll = _find_preview_collection(node_uuid)
        if coll is None:
            coll = bpy.data.collections.new(f"COLMAP_Preview_{name}")
            coll[NODE_UUID_PROP] = node_uuid
            scene.collection.children.link(coll)

        root = find_preview_root(node_uuid)
        if root is None:
            root = bpy.data.objects.new(f"COLMAP_Root_{name}", None)
            root.empty_display_type = 'ARROWS'
            root.empty_display_size = 1.0
            root["colmap_root"] = True
            root[NODE_UUID_PROP] = node_uuid
            coll.objects.link(root)

        # Rebuild everything under the root (refresh keeps the root itself).
        for obj in list(coll.objects):
            if obj != root:
                _remove_object(obj)

        root["colmap_model_path"] = str(model_path)

        verts, colors = point_cloud_data(model.points3D)
        mesh = bpy.data.meshes.new(f"COLMAP_PointCloud_{name}")
        mesh.from_pydata(verts, [], [])
        mesh.update()
        if colors:
            attr = mesh.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='POINT')
            attr.data.foreach_set("color", [c for rgba in colors for c in rgba])

        obj = bpy.data.objects.new(f"COLMAP_PointCloud_{name}", mesh)
        obj["colmap_points3D"] = True
        obj[NODE_UUID_PROP] = node_uuid
        obj.parent = root
        coll.objects.link(obj)
        return root

    def remove_preview(node_uuid: str) -> bool:
        """Delete a node's preview collection and contents. True if found."""
        coll = _find_preview_collection(node_uuid)
        if coll is None:
            return False
        for obj in list(coll.objects):
            _remove_object(obj)
        bpy.data.collections.remove(coll)
        return True
