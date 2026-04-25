"""Minimal bpy stub for running tests outside Blender.

This stub satisfies bare ``import bpy`` calls in the addon's top-level
__init__.py so that pytest can collect tests without a live Blender
process.  Individual service modules that use bpy are expected to gate
their bpy usage so that pure-logic code can be tested in isolation.
"""
from unittest.mock import MagicMock

types = MagicMock()
props = MagicMock()
utils = MagicMock()
context = MagicMock()
data = MagicMock()
ops = MagicMock()
app = MagicMock()

# Property decorators are called at class-definition time; make them
# return a MagicMock so class bodies don't raise AttributeError.
for _prop in (
    "StringProperty",
    "BoolProperty",
    "IntProperty",
    "FloatProperty",
    "EnumProperty",
    "CollectionProperty",
    "PointerProperty",
    "FloatVectorProperty",
    "IntVectorProperty",
):
    setattr(props, _prop, MagicMock(return_value=MagicMock()))
