# Override BLENDER on the command line if your install is elsewhere.
BLENDER ?= /Applications/Blender.app/Contents/MacOS/Blender

.PHONY: test test-unit test-integration

test: test-unit test-integration

test-unit:
	pytest -q

test-integration:
	$(BLENDER) --background --python tests/integration/test_video_load.py
