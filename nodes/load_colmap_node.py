"""SkysplatLoadColmapNode — points at an existing COLMAP sparse model on
disk (e.g. sparse/0 from an earlier run or an external tool) and emits a
ColmapModel lineage object, so Transform/Export/Cameras/Brush Dataset can
consume reconstructions that weren't produced by a COLMAP node in this tree.

The pure helpers are at module top-level so pytest can import them
without bpy.
"""
from __future__ import annotations

from pathlib import Path

try:
    import bpy
    from bpy.props import StringProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


# ----- Pure helpers (importable without bpy) -----

_MODEL_STEMS = ("cameras", "images", "points3D")


def find_model_ext(model_dir: Path) -> str | None:
    """Return '.bin' or '.txt' if model_dir holds a complete sparse model
    in that format, else None. Mirrors read_write_model's autodetection
    order (bin first) without paying to parse a large points3D file."""
    model_dir = Path(model_dir)
    for ext in (".bin", ".txt"):
        if all((model_dir / f"{stem}{ext}").exists() for stem in _MODEL_STEMS):
            return ext
    return None


def guess_image_root(model_dir: Path) -> Path | None:
    """Best-effort guess at the images folder for a standard COLMAP layout
    (<workspace>/sparse/0 beside <workspace>/images). Checked at both
    plausible depths since some tools skip the numbered subfolder."""
    model_dir = Path(model_dir)
    for parent in (model_dir.parent.parent, model_dir.parent):
        candidate = parent / "images"
        if candidate.is_dir():
            return candidate
    return None


if HAS_BPY:
    from .base import SkysplatNode
    from .add_menu import register_add_menu_entry

    class SkysplatLoadColmapNode(SkysplatNode):
        bl_idname = "SkysplatLoadColmapNode"
        bl_label = "Load COLMAP"

        model_dir: StringProperty(
            name="Model", default="", subtype="DIR_PATH",
            description="Directory containing a COLMAP sparse model "
                        "(cameras/images/points3D as .bin or .txt), "
                        "typically <workspace>/sparse/0",
        )
        image_root: StringProperty(
            name="Images", default="", subtype="DIR_PATH",
            description="Root folder of the source frames the model was "
                        "reconstructed from. Optional — auto-detected from "
                        "the standard COLMAP layout when left empty; only "
                        "required downstream by Brush Dataset",
        )

        def init(self, context):
            super().init(context)
            self.outputs.new("SkysplatColmapModelSocket", "Model")

        def draw_buttons(self, context, layout):
            self.draw_status(layout)
            layout.prop(self, "model_dir", text="")
            layout.prop(self, "image_root", text="", icon="IMAGE_DATA")
            self.draw_run_row(layout)

        def params_dict(self) -> dict:
            return {
                "model_dir": str(Path(bpy.path.abspath(self.model_dir))) if self.model_dir else "",
                "image_root": str(Path(bpy.path.abspath(self.image_root))) if self.image_root else "",
            }

        def run(self, context):
            if not self.model_dir:
                raise RuntimeError("Load COLMAP node has no model folder set")

            model_dir = Path(bpy.path.abspath(self.model_dir))
            if find_model_ext(model_dir) is None:
                raise RuntimeError(
                    f"No COLMAP model in {model_dir} — expected "
                    "cameras/images/points3D as .bin or .txt")

            if self.image_root:
                image_root = Path(bpy.path.abspath(self.image_root))
                if not image_root.is_dir():
                    raise RuntimeError(f"Images folder doesn't exist: {image_root}")
            else:
                image_root = guess_image_root(model_dir)

            output = {
                "Model": {
                    "model_dir": model_dir,
                    "image_root": image_root,
                    # External models carry no per-video provenance.
                    "source_map": {},
                }
            }
            self.store_output(output, self.params_dict())


    classes = (SkysplatLoadColmapNode,)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        register_add_menu_entry(SkysplatLoadColmapNode.bl_idname, "Load COLMAP")

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
