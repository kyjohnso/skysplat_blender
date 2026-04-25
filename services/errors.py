"""Typed exceptions raised by skysplat services.

Each service raises one of these so callers can recover precisely.
The bake walker (phase 2) will map these to per-node error states.
"""


class SkysplatServiceError(Exception):
    """Base class for all service-layer errors."""


class ColmapError(SkysplatServiceError):
    """COLMAP subprocess or model I/O failed."""


class BrushError(SkysplatServiceError):
    """Brush training subprocess failed."""


class FrameExtractError(SkysplatServiceError):
    """Frame extraction failed (Blender render or VSE issue)."""


class TransformError(SkysplatServiceError):
    """COLMAP model transformation failed."""


class NodeEvalError(SkysplatServiceError):
    """Node graph evaluation failed because expected scene state is missing.

    Recoverable — the next bake should re-create the missing state.
    """
