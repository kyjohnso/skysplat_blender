"""Stub for bpy.props used in tests outside Blender."""
from unittest.mock import MagicMock

def _prop_factory(*args, **kwargs):
    return MagicMock()

StringProperty = _prop_factory
BoolProperty = _prop_factory
IntProperty = _prop_factory
FloatProperty = _prop_factory
EnumProperty = _prop_factory
CollectionProperty = _prop_factory
PointerProperty = _prop_factory
FloatVectorProperty = _prop_factory
IntVectorProperty = _prop_factory
