"""Pytest configuration shared across the unit tests.

These tests import skysplat services directly. Services that need bpy
gate the import internally — pure modules import cleanly without
Blender.
"""
import sys
from pathlib import Path

# Make the addon root importable so `from services import ...` works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
