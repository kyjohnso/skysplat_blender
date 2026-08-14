"""Link-drag-search for the SkySplat node editor.

Blender's native "drag a link into empty space -> search menu" is disabled
for custom node trees (node_relationships.cc: should_create_drag_link_search_menu
returns false for NTREE_CUSTOM), and Python nodes can't register the
gather_link_search_ops callback it's built from. So we reimplement it:

- SKYSPLAT_OT_link_drag sits on LMB-press in the Node Editor keymap. If the
  press lands on a socket of a SkySplat tree it invokes the native NODE_OT_link
  (so dragging/attaching behaves exactly as stock), then watches for it to
  finish. If the drag ended on empty space without creating a link, it opens
- SKYSPLAT_OT_link_search, a search popup of (node, socket) pairs compatible
  with the dragged socket. Picking one adds the node at the drop point, links
  it, and starts the native translate-attach so it follows the mouse.

Socket screen positions aren't exposed to Python, so the press hit-test
estimates them from the layout math in Blender's node_draw.cc
(node_update_basis_from_socket_lists / node_update_hidden). The estimate only
gates *our* popup: if it misses, native linking still works; if it hits but
the native operator disagrees, we pass the event through untouched.

Pure math/compat helpers live at module top so pytest can import them
without bpy.
"""
from __future__ import annotations

try:
    import bpy
    from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty
    HAS_BPY = True
except ImportError:
    HAS_BPY = False


# ----- Pure helpers (importable without bpy) -----

# Layout constants from node_intern.hh, in units of U = widget_unit
# (20px at ui_scale 1). Sockets are one NODE_DY-tall label row each,
# NODE_ITEM_SPACING_Y (0.1U) apart.
_HEADER = 1.0        # NODE_DY
_TOP_PAD = 0.25      # NODE_DYS / 2
_BOTTOM_PAD = 0.25   # NODE_DYS / 2
_ROW = 1.0           # NODE_DY
_ROW_GAP = 0.1       # NODE_ITEM_SPACING_Y
_SOCK_CENTER = 0.5   # socket sits NODE_DYS below its row top


def estimate_socket_positions(loc, dims, n_inputs, n_outputs, hidden, widget_unit):
    """Estimate socket centers in view pixels for a node drawn at view-space
    top-left `loc` with drawn size `dims` (both view px).

    Returns (inputs, outputs): lists of (x, y) view coords, in socket order.
    Mirrors node_update_basis_from_socket_lists (expanded nodes) and
    node_update_hidden (collapsed nodes) from Blender's node_draw.cc.
    """
    u = widget_unit
    x0, y0 = loc
    w, h = dims

    if hidden:
        # Collapsed: sockets spread along the sides, centered on the header.
        dy = 0.5 * u
        offset = -0.5 * u
        outs = []
        y = y0 + dy * (n_outputs - 1) * 0.5 + offset
        for _ in range(n_outputs):
            outs.append((x0 + w, y))
            y -= dy
        ins = []
        y = y0 + dy * (n_inputs - 1) * 0.5 + offset
        for _ in range(n_inputs):
            ins.append((x0, y))
            y -= dy
        return ins, outs

    # Outputs from the top: header, top padding, then one row per socket.
    outs = []
    y = y0 - (_HEADER + _TOP_PAD + _SOCK_CENTER) * u
    for _ in range(n_outputs):
        outs.append((x0 + w, y))
        y -= (_ROW + _ROW_GAP) * u

    # Inputs from the bottom (buttons of unknown height sit above them):
    # bottom padding, then rows bottom-up in reverse socket order.
    ins = [None] * n_inputs
    y = (y0 - h) + (_BOTTOM_PAD + _SOCK_CENTER) * u
    for i in range(n_inputs - 1, -1, -1):
        ins[i] = (x0, y)
        y += (_ROW + _ROW_GAP) * u
    return ins, outs


def nearest_socket(point, positions, widget_unit):
    """Index of the socket in `positions` nearest to view point, or None if
    none is within tolerance (generous: the native operator is the final
    arbiter of whether a drag actually starts)."""
    px, py = point
    tol_x = 0.9 * widget_unit
    tol_y = 0.6 * widget_unit
    best, best_d = None, None
    for i, (sx, sy) in enumerate(positions):
        dx, dy = abs(px - sx), abs(py - sy)
        if dx > tol_x or dy > tol_y:
            continue
        d = dx * dx + dy * dy
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


def suggestions_for(specs, socket_type, in_out):
    """Compatible (node_idname, node_label, socket_name) triples for a drag
    from a socket of type `socket_type`.

    `in_out` is the side dragged FROM: 'OUT' means we look for inputs on
    other nodes, 'IN' means outputs. `specs` is
    {idname: {"label", "inputs": [(name, type)], "outputs": [(name, type)]}}.
    """
    key = "inputs" if in_out == 'OUT' else "outputs"
    out = []
    for idname, spec in specs.items():
        seen = set()
        for name, stype in spec[key]:
            if stype != socket_type or name in seen:
                continue
            seen.add(name)
            out.append((idname, spec["label"], name))
    return out


# ----- Blender-only part -----

if HAS_BPY:
    from . import add_menu

    _specs_cache: dict | None = None
    # invoke_search_popup enum items must stay referenced (known bpy gotcha).
    _enum_items_ref: list = []

    def _socket_specs() -> dict:
        """Socket declarations per node type, discovered by instantiating
        each registered node once in a throwaway tree (nodes declare their
        sockets imperatively in init(), so there's nothing to introspect
        statically)."""
        global _specs_cache
        if _specs_cache is not None:
            return _specs_cache
        specs = {}
        tmp = bpy.data.node_groups.new("__skysplat_link_search_probe__", "SkySplatNodeTree")
        try:
            for idname, label in add_menu.add_menu_entries():
                try:
                    node = tmp.nodes.new(idname)
                except RuntimeError:
                    continue
                specs[idname] = {
                    "label": label,
                    "inputs": [(s.name, s.bl_idname) for s in node.inputs],
                    "outputs": [(s.name, s.bl_idname) for s in node.outputs],
                }
        finally:
            bpy.data.node_groups.remove(tmp)
        _specs_cache = specs
        return specs

    def clear_specs_cache():
        global _specs_cache
        _specs_cache = None

    def _widget_unit(context) -> float:
        return 20.0 * context.preferences.system.ui_scale

    def _abs_loc(node):
        x, y = node.location
        parent = node.parent
        while parent is not None:
            x += parent.location.x
            y += parent.location.y
            parent = parent.parent
        return x, y

    def _visible(sockets):
        return [s for s in sockets if s.enabled and not s.hide]

    def _find_socket_at(context, tree, view_point):
        """(node, socket, 'IN'|'OUT') under the view-space point, or None."""
        u = _widget_unit(context)
        scale = context.preferences.system.ui_scale
        for node in tree.nodes:
            if node.type == 'FRAME':
                continue
            ax, ay = _abs_loc(node)
            loc = (ax * scale, ay * scale)
            dims = (node.dimensions.x, node.dimensions.y)
            if dims[0] <= 0:
                continue  # not drawn yet
            ins = _visible(node.inputs)
            outs = _visible(node.outputs)
            in_pos, out_pos = estimate_socket_positions(
                loc, dims, len(ins), len(outs), node.hide, u)
            i = nearest_socket(view_point, out_pos, u)
            if i is not None:
                return node, outs[i], 'OUT'
            i = nearest_socket(view_point, in_pos, u)
            if i is not None:
                return node, ins[i], 'IN'
        return None

    def _point_over_node(context, tree, view_point) -> bool:
        px, py = view_point
        scale = context.preferences.system.ui_scale
        u = _widget_unit(context)
        for node in tree.nodes:
            if node.type == 'FRAME':
                continue
            ax, ay = _abs_loc(node)
            x0, y_top = ax * scale, ay * scale
            w, h = node.dimensions.x, node.dimensions.y
            if node.hide:
                # Collapsed nodes are drawn centered on the header line.
                y_max = y_top + 0.5 * h - 0.5 * u
                y_min = y_max - h
            else:
                y_max, y_min = y_top, y_top - h
            if x0 <= px <= x0 + w and y_min <= py <= y_max:
                return True
        return False

    def _links_snapshot(tree) -> frozenset:
        return frozenset(
            (l.from_node.name, l.from_socket.identifier,
             l.to_node.name, l.to_socket.identifier)
            for l in tree.links
        )

    def _active_skysplat_tree(context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return None
        if getattr(space, "tree_type", "") != "SkySplatNodeTree":
            return None
        return space.edit_tree or space.node_tree

    class SKYSPLAT_OT_link_search(bpy.types.Operator):
        """Add a node compatible with the dragged socket and connect it"""
        bl_idname = "skysplat_node.link_search"
        bl_label = "Add Connected Node"
        bl_options = {'INTERNAL', 'UNDO'}
        bl_property = "item"

        from_node: StringProperty()
        from_socket_index: IntProperty()
        in_out: EnumProperty(items=[('IN', "Input", ""), ('OUT', "Output", "")])
        socket_type: StringProperty()
        loc_x: FloatProperty()  # drop point, view coords
        loc_y: FloatProperty()

        def _items(self, context):
            global _enum_items_ref
            items = []
            for idname, label, sock_name in suggestions_for(
                    _socket_specs(), self.socket_type, self.in_out):
                items.append((f"{idname}||{sock_name}",
                              f"{label} ▸ {sock_name}", ""))
            if not items:
                items = [("__none__", "No compatible node", "")]
            _enum_items_ref = items
            return items

        item: EnumProperty(items=_items)

        def invoke(self, context, event):
            context.window_manager.invoke_search_popup(self)
            return {'FINISHED'}

        def execute(self, context):
            if self.item == "__none__":
                return {'CANCELLED'}
            tree = _active_skysplat_tree(context)
            if tree is None:
                return {'CANCELLED'}
            src = tree.nodes.get(self.from_node)
            if src is None:
                return {'CANCELLED'}
            src_sockets = src.outputs if self.in_out == 'OUT' else src.inputs
            if self.from_socket_index >= len(src_sockets):
                return {'CANCELLED'}
            src_sock = src_sockets[self.from_socket_index]

            idname, sock_name = self.item.split("||", 1)
            node = tree.nodes.new(idname)
            scale = context.preferences.system.ui_scale
            x = self.loc_x / scale
            y = self.loc_y / scale
            if self.in_out == 'IN':
                # New node goes upstream: align its right edge to the cursor.
                x -= node.width
            node.location = (x, y)

            if self.in_out == 'OUT':
                dst = next((s for s in node.inputs
                            if s.name == sock_name and not s.is_linked), None)
                if dst is not None:
                    tree.links.new(src_sock, dst)
            else:
                dst = next((s for s in node.outputs if s.name == sock_name), None)
                if dst is not None:
                    tree.links.new(dst, src_sock)

            for n in tree.nodes:
                n.select = False
            node.select = True
            tree.nodes.active = node
            # Native "node follows mouse until click, removed on cancel".
            try:
                bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')
            except RuntimeError:
                pass
            return {'FINISHED'}

    class SKYSPLAT_OT_link_drag(bpy.types.Operator):
        """Drag a link; releasing on empty space opens a node search popup"""
        bl_idname = "skysplat_node.link_drag"
        bl_label = "Link Drag Search"
        bl_options = {'INTERNAL'}

        @classmethod
        def poll(cls, context):
            return _active_skysplat_tree(context) is not None

        def invoke(self, context, event):
            region = context.region
            if region is None or region.type != 'WINDOW':
                return {'PASS_THROUGH'}
            tree = _active_skysplat_tree(context)
            view_point = region.view2d.region_to_view(
                event.mouse_region_x, event.mouse_region_y)
            hit = _find_socket_at(context, tree, view_point)
            if hit is None:
                return {'PASS_THROUGH'}
            node, sock, in_out = hit

            # Dragging an existing link off an input is a detach gesture —
            # native suppresses the search menu there, so do we.
            self._suppress = (in_out == 'IN' and bool(sock.links))
            self._from_node = node.name
            sockets = node.outputs if in_out == 'OUT' else node.inputs
            self._from_socket_index = list(sockets).index(sock)
            self._in_out = in_out
            self._socket_type = sock.bl_idname
            self._links_before = _links_snapshot(tree)
            self._released = None
            self._timer = None

            # Hand the actual drag to the native operator so link drawing,
            # snapping and multi-link behavior stay stock.
            result = bpy.ops.node.link('INVOKE_DEFAULT')
            if 'RUNNING_MODAL' not in result:
                return {'PASS_THROUGH'}
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.05, window=context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        def modal(self, context, event):
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                # Remember where the drag ended; NODE_OT_link (below us on
                # the handler stack) confirms on this same event.
                self._released = (event.mouse_region_x, event.mouse_region_y)
                return {'PASS_THROUGH'}
            if event.type != 'TIMER':
                return {'PASS_THROUGH'}
            if any(op.bl_idname == "NODE_OT_link"
                   for op in context.window.modal_operators):
                return {'PASS_THROUGH'}

            # Native link operator finished.
            self._remove_timer(context)
            tree = _active_skysplat_tree(context)
            if tree is None:
                return {'FINISHED'}
            if self._suppress or self._released is None:  # detach or cancel
                return {'FINISHED'}
            if _links_snapshot(tree) != self._links_before:
                return {'FINISHED'}  # a real link was made (or detached)

            region = context.region
            if region is None:
                return {'FINISHED'}
            view_point = region.view2d.region_to_view(*self._released)
            if _point_over_node(context, tree, view_point):
                return {'FINISHED'}
            if not suggestions_for(_socket_specs(), self._socket_type, self._in_out):
                return {'FINISHED'}

            bpy.ops.skysplat_node.link_search(
                'INVOKE_DEFAULT',
                from_node=self._from_node,
                from_socket_index=self._from_socket_index,
                in_out=self._in_out,
                socket_type=self._socket_type,
                loc_x=view_point[0],
                loc_y=view_point[1],
            )
            return {'FINISHED'}

        def cancel(self, context):
            self._remove_timer(context)

        def _remove_timer(self, context):
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None

    classes = (SKYSPLAT_OT_link_search, SKYSPLAT_OT_link_drag)

    _keymap_items = []

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        kc = bpy.context.window_manager.keyconfigs.addon
        if kc:  # None in background mode
            km = kc.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')
            kmi = km.keymap_items.new(
                SKYSPLAT_OT_link_drag.bl_idname, 'LEFTMOUSE', 'PRESS')
            _keymap_items.append((km, kmi))

    def unregister():
        for km, kmi in _keymap_items:
            km.keymap_items.remove(kmi)
        _keymap_items.clear()
        clear_specs_cache()
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

else:
    def register(): pass
    def unregister(): pass
