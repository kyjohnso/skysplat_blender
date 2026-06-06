# Plan: Bridge the SkySplat node graph → BlendSplat geometry nodes

Status: **deferred / investigation only** (captured 2026-06-06). Not started.

## Goal

Let a trained Brush splat flow out of the SkySplat node graph and into
[BlendSplat](https://codeberg.org/soerensc/BlendSplat-Library) so it renders
natively in the viewport as a Gaussian splat (Geometry Nodes + EEVEE shader
displacement), with no extra manual import steps.

## Why this shape (and not "recast our graph as geo nodes")

Geometry Nodes are evaluated by the depsgraph in C++; there is **no Python hook
to define a geometry node's behavior**, and evaluation must be pure /
side-effect-free. Our pipeline (video → frames → COLMAP → dataset → train) is
long-running, side-effecting subprocess + file IO + async modal jobs — it cannot
live in a `GeometryNodeTree`. So:

- **Producer half** (ours): stays a custom `NodeTree` + modal job runner.
- **Consumer half** (BlendSplat): geometry nodes that read a `.ply` and render
  it. This is the only half that belongs in GN, and BlendSplat already implements it.

The bridge is therefore one-directional: our final node hands BlendSplat a
`.ply` path and builds the GN modifier that drives it.

## BlendSplat contract (verified against the library .blend files, Blender 5.1)

Library: `../blendSplat-library/assets/core/*.blend` (asset library; catalogs:
Geometry/Convert, Create, Display, Info, Process, Shader).

Ingest → render chain, both plain `GeometryNodeTree` groups:

`splat.import` (in `create.blend`)
- IN  `Path`  — **NodeSocketString**  (the `.ply` file path)  ← the hook
- IN  `ply`   — NodeSocketMenu (color space, default `srgb`)
- OUT `Splat` — NodeSocketGeometry

`splat.display` (in `display.blend`)
- IN  `Splat`    — NodeSocketGeometry
- IN  `Material` — NodeSocketMaterial (default `splat.shader`)
- OUT `Splat`    — NodeSocketGeometry

Canonical render setup = a Geometry Nodes modifier whose tree is:
`Group(splat.import, Path=<ply>) → Group(splat.display, Material=splat.shader) → Group Output`.

Other groups available if useful later: `splat.transform`, `splat.filter-size`,
`splat.filter-floater` (process.blend); `splat.to.mesh`, `splat.attr_convert`
(convert.blend); `splat.info` (utils.blend).

## What we already emit (the source side)

`SkysplatBrushTrainNode` output lineage on its `Splat` socket
(`nodes/brush_train_node.py`):

```python
"Splat": {
    "ply_path": str(export_path),     # DIRECTORY: <workspace>/brush_output/
    "training_log": str(log_path),
}
```

Note `ply_path` is the **export directory**, not a single file. Brush writes
`export_{iter}.ply` (see `BrushParams.export_name`). The bridge must resolve the
actual file — pick the highest-iter `export_*.ply` (the final splat).

## Implementation sketch

New terminal node **"BlendSplat Display"** (consumes the existing
`SkysplatSplatSocket`). On Run:

1. **Resolve the `.ply`** — read upstream `Splat` lineage `ply_path` dir, pick
   highest-iter `export_*.ply`. Error if none found.
2. **Ensure BlendSplat datablocks exist** — append (or link) `splat.import`,
   `splat.display`, and the `splat.shader` material from the library `.blend`s.
   Their `_splat.*` helper groups come along automatically (verified). Guard
   against duplicate appends on re-run (reuse by name if already present).
3. **Build the object** — create mesh object `"<node name> Splat"`, add a
   `GEOMETRY_NODES` modifier, author the tiny tree
   `splat.import → splat.display → output`; set `splat.import` `Path` to the
   resolved `.ply` and the `ply` color-space menu.
4. **Orient** — apply the COLMAP→Blender world transform (reuse logic in
   `services/transform`, same as the sidebar applies to its splats) so the
   splat is right-side-up.
5. **Output / cache** — store the created object name in lineage; set node
   status done; log to `run.log` like other nodes. This is fast + main-thread
   (no subprocess) so it does NOT need the worker-thread job path — a plain
   `run()` is fine.

## Decisions to make when we pick this up

1. **Integration surface**: new "BlendSplat Display" node (recommended — fits
   the graph, chainable, own status/log) vs a button on the Brush Train node.
2. **Library discovery**: addon-preference path (default-guess
   `../blendSplat-library`) vs auto-detect from registered Asset Libraries vs
   pref-with-fallback (most robust).
3. **append vs link**: append = self-contained, survives library move; link =
   no duplication, updates with library but breaks if it moves.
4. **Color space**: expose the `ply` menu (`srgb` default) on our node? What
   does Brush actually export?

## Gotchas / risks

- **Coordinate frame** must be verified against a real trained splat; Brush /
  COLMAP axes differ from Blender's. BlendSplat's `splat.import` may handle some
  of this; confirm empirically.
- **Hard dependency on BlendSplat being installed** — degrade gracefully with a
  clear error if the library `.blend`s aren't found.
- **Version coupling**: BlendSplat requires Blender 5.1+. Interface socket names
  above are what we bind to; re-verify if BlendSplat updates.
- **`splat.shader` material**: confirm it's pulled in when appending
  `splat.display` (interface default references it); append the material
  explicitly if not.
- **Re-run idempotency**: appending repeatedly creates `.001` duplicates — reuse
  existing datablocks by name.

## Out of scope

- Rendering correctness tuning (dithered alpha, Cycles limitations) — those are
  BlendSplat's domain, documented in its README limitations.
- Editing splats back out / round-tripping into our graph.
