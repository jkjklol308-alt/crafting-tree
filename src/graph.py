"""Interactive production-chain graph.

Design: items are bubbles (rounded circles), processing methods are hexagons,
connections are directed curves with arrowheads. Supports node dragging,
zooming (cursor-anchored wheel), panning (hand drag), auto-arrangement,
branch collapsing and focused/filtered subgraph views.

Pure layout math lives in layout.py; this module is Qt-only.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPolygonF, QPen, QPixmap, QFont, QRadialGradient
from PySide6.QtWidgets import QGraphicsScene, QGraphicsObject, QGraphicsView, QGraphicsTextItem, QGraphicsItem

from .models import Item, ProcessMethod, Recipe
from .theme import PALETTE
from .layout import compute_positions
from .util import format_qty

ITEM_RADIUS = 34
PROCESS_W, PROCESS_H = 96, 60
MAX_LABEL = 24
LABEL_W = 132

RAW_COLOR = QColor(PALETTE['raw'])
INTERMEDIATE_COLOR = QColor(PALETTE['intermediate'])
FINAL_COLOR = QColor(PALETTE['final'])
PROCESS_COLOR = QColor(PALETTE['process'])
TARGET_COLOR = QColor(PALETTE['accent'])
EDGE_COLOR = QColor(132, 148, 168)
BYPRODUCT_EDGE_COLOR = QColor(189, 130, 198)


def node_color(cls):
    if cls == 'raw':
        return RAW_COLOR
    if cls == 'final':
        return FINAL_COLOR
    return INTERMEDIATE_COLOR


def initials(label):
    parts = label.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return label[:2].upper() if label else '?'


def short_label(label, limit=MAX_LABEL):
    if len(label) <= limit:
        return label
    return label[:limit - 1].rstrip() + '…'


# ---------------------------------------------------------------------------
# text items
# ---------------------------------------------------------------------------

class NodeLabel(QGraphicsTextItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setDefaultTextColor(QColor('#eef1f6'))
        self.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self.setTextWidth(LABEL_W)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(13, 16, 22, 208))
        painter.drawRoundedRect(rect.adjusted(-6, -3, 6, 3), 7, 7)
        super().paint(painter, option, widget)


class QtyBadge(QGraphicsTextItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setDefaultTextColor(QColor('#ffd28a'))
        self.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self.setTextWidth(150)


# ---------------------------------------------------------------------------
# nodes
# ---------------------------------------------------------------------------

class NodeView(QGraphicsObject):
    def __init__(self, kind, node_id, label, icon_path='', target=False):
        super().__init__()
        self.kind = kind
        self.id = int(node_id)
        self.key = (kind, int(node_id))
        self.label = label
        self.target_ring = target
        self.selected = False
        self.highlight = False
        self.classification = 'intermediate'
        self._icon_path = icon_path or ''
        self._pixmap = None
        self._load_icon()

        self._label = NodeLabel()
        self._label.setParentItem(self)
        self._label.setText(short_label(label))
        self._label.setPos(-LABEL_W / 2, ITEM_RADIUS + 8)

        self._qty_badge = None

        self.setItemFlags(QGraphicsObject.ItemIsMovable)

    # -- icon -----------------------------------------------------------
    def _load_icon(self):
        self._pixmap = None
        if not self._icon_path:
            return
        try:
            pm = QPixmap(self._icon_path)
            if not pm.isNull():
                self._pixmap = pm
        except Exception:
            self._pixmap = None

    def set_icon(self, icon_path):
        self._icon_path = icon_path or ''
        self._load_icon()
        self.update()

    # -- labels ----------------------------------------------------------
    def set_qty_text(self, text):
        self._qty = text or ''
        if self._qty:
            if self._qty_badge is None:
                self._qty_badge = QtyBadge()
                self._qty_badge.setParentItem(self)
                self._qty_badge.setPos(-75, ITEM_RADIUS + 27)
            self._qty_badge.setText(self._qty)
        if self._qty_badge is not None and not self._qty:
            self._qty_badge.deleteLater()
            self._qty_badge = None
        self.prepareGeometryChange()
        self.update()

    def set_labels(self, label, qty_text=None):
        self.label = label
        self._label.setText(short_label(label))
        if qty_text is not None:
            self.set_qty_text(qty_text)
        self.prepareGeometryChange()
        self.update()

    def set_classification(self, cls):
        if self.classification != cls:
            self.classification = cls
            self.update()

    def set_selected(self, v):
        if self.selected != v:
            self.selected = v
            self.update()

    def set_highlight(self, v):
        if self.highlight != v:
            self.highlight = v
            self.update()

    # -- paint -----------------------------------------------------------
    def boundingRect(self):
        w = max(PROCESS_W, ITEM_RADIUS * 2)
        h = ITEM_RADIUS * 2 + 34
        return QRectF(-w / 2, -ITEM_RADIUS - 2, w, h + 4)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.kind == 'process':
            self._paint_process(painter)
        else:
            self._paint_item(painter)

        if self.selected:
            painter.setPen(QPen(TARGET_COLOR, 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), ITEM_RADIUS + 6, ITEM_RADIUS + 6)
        elif self.highlight:
            painter.setPen(QPen(QColor(215, 224, 236, 170), 2.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), ITEM_RADIUS + 5, ITEM_RADIUS + 5)

        if self.target_ring:
            painter.setPen(QPen(TARGET_COLOR, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), ITEM_RADIUS + 12, ITEM_RADIUS + 12)

    def _paint_item(self, painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 130))
        painter.drawEllipse(QPointF(2, 5), ITEM_RADIUS + 1, ITEM_RADIUS + 1)

        color = node_color(self.classification)
        grad = QRadialGradient(QPointF(-ITEM_RADIUS * 0.45, -ITEM_RADIUS * 0.55), ITEM_RADIUS * 1.6)
        grad.setColorAt(0.0, color.lighter(135))
        grad.setColorAt(0.65, color)
        grad.setColorAt(1.0, color.darker(128))
        painter.setBrush(grad)
        painter.setPen(QPen(color.darker(165), 1.5))
        painter.drawEllipse(QPointF(0, 0), ITEM_RADIUS, ITEM_RADIUS)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 32))
        painter.drawEllipse(QPointF(-ITEM_RADIUS * 0.42, -ITEM_RADIUS * 0.5), ITEM_RADIUS * 0.44, ITEM_RADIUS * 0.26)

        if self._pixmap is not None:
            size = int(ITEM_RADIUS * 1.15)
            scaled = self._pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(-scaled.width() / 2), int(-scaled.height() / 2), scaled)
        else:
            painter.setPen(QColor('#10131a'))
            painter.setFont(QFont('Segoe UI', 15, QFont.Bold))
            painter.drawText(QRectF(-ITEM_RADIUS, -ITEM_RADIUS, ITEM_RADIUS * 2, ITEM_RADIUS * 2),
                             Qt.AlignCenter, initials(self.label))

    def _paint_process(self, painter):
        w, h = PROCESS_W, PROCESS_H
        pts = []
        for i in range(6):
            ang = (60.0 * i - 30.0) * math.pi / 180.0
            pts.append(QPointF(w / 2 * math.cos(ang), h / 2 * math.sin(ang)))
        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        path.closeSubpath()

        painter.save()
        painter.translate(2, 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawPath(path)
        painter.restore()

        color = PROCESS_COLOR
        grad = QRadialGradient(QPointF(-w * 0.15, -h * 0.35), w * 0.8)
        grad.setColorAt(0.0, color.lighter(130))
        grad.setColorAt(1.0, color.darker(125))
        painter.setPen(QPen(color.darker(170), 1.5))
        painter.setBrush(grad)
        painter.drawPath(path)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 26))
        painter.drawEllipse(QRectF(-w * 0.36, -h * 0.5, w * 0.5, h * 0.2))

        if self._pixmap is not None:
            size = int(min(w, h) * 0.6)
            scaled = self._pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(int(-scaled.width() / 2), int(-scaled.height() / 2), scaled)
        else:
            painter.setPen(QColor('#10131a'))
            painter.setFont(QFont('Segoe UI', 13, QFont.Bold))
            painter.drawText(QRectF(-w / 2, -h / 2, w, h), Qt.AlignCenter, initials(self.label))


# ---------------------------------------------------------------------------
# edges
# ---------------------------------------------------------------------------

class EdgeView(QGraphicsObject):
    def __init__(self, src_key, tgt_key, dash=False, label=''):
        super().__init__()
        self.src_key = src_key
        self.tgt_key = tgt_key
        self.dash = dash
        self.label_text = label
        self._src = QPointF(0, 0)
        self._tgt = QPointF(1, 0)
        self._src_radius = ITEM_RADIUS
        self._tgt_radius = ITEM_RADIUS
        self.setZValue(-1)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)

        self._label = NodeLabel()
        self._label.setParentItem(self)
        self._label.setText(label)
        self._label.setTextWidth(150)
        self._label.setFont(QFont('Segoe UI', 8, QFont.Bold))
        self._label.setDefaultTextColor(QColor('#c9d2df'))

    def update_geometry(self, src_pos, tgt_pos, src_radius=ITEM_RADIUS, tgt_radius=ITEM_RADIUS):
        self._src = QPointF(src_pos.x(), src_pos.y())
        self._tgt = QPointF(tgt_pos.x(), tgt_pos.y())
        self._src_radius = src_radius
        self._tgt_radius = tgt_radius
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        x0, y0 = self._src.x(), self._src.y()
        x1, y1 = self._tgt.x(), self._tgt.y()
        return QRectF(min(x0, x1) - 80, min(y0, y1) - 80, abs(x1 - x0) + 160, abs(y1 - y0) + 160)

    def set_label(self, label):
        self.label_text = label
        self._label.setText(label)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        src, tgt = self._src, self._tgt
        dx = tgt.x() - src.x()
        path = QPainterPath()
        path.moveTo(src)
        path.cubicTo(QPointF(src.x() + dx * 0.45, src.y()),
                     QPointF(tgt.x() - dx * 0.45, tgt.y()),
                     tgt)
        color = BYPRODUCT_EDGE_COLOR if self.dash else EDGE_COLOR
        pen = QPen(color, 2.6, Qt.DashLine if self.dash else Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # arrowhead pulled back to boundary
        cp2 = QPointF(tgt.x() - dx * 0.45, tgt.y())
        tip_dir = QPointF(tgt.x() - cp2.x(), tgt.y() - cp2.y())
        length = tip_dir.length()
        if length > 0:
            tangent = QPointF(tip_dir.x() / length, tip_dir.y() / length)
            tip_in = QPointF(tgt.x() - tangent.x() * self._tgt_radius,
                             tgt.y() - tangent.y() * self._tgt_radius)
            wing = 9
            back = 14
            cp = QPointF(-tangent.y(), tangent.x())
            base_center = QPointF(tip_in.x() - tangent.x() * back, tip_in.y() - tangent.y() * back)
            poly = QPolygonF([tip_in,
                               QPointF(base_center.x() + cp.x() * wing, base_center.y() + cp.y() * wing),
                               QPointF(base_center.x() - cp.x() * wing, base_center.y() - cp.y() * wing)])
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(poly)

        # label at curve midpoint
        mid = QPointF((src.x() + tgt.x()) / 2, (src.y() + tgt.y()) / 2)
        self._label.setPos(mid.x() - 60, mid.y() - 10)


# ---------------------------------------------------------------------------
# scene
# ---------------------------------------------------------------------------

class GraphScene(QGraphicsScene):
    node_clicked = Signal(tuple)       # (kind, id)
    node_moved = Signal(str, int, float, float)
    node_double_clicked = Signal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = {}
        self.processes = {}
        self.recipes = []
        self.positions = {}
        self.classification = {}
        self.target_items = set()

        self.focus_kind = None
        self.focus_id = None
        self.filter_mode = 'all'
        self.byproducts = True
        self.collapsed = set()

        self.node_views = {}
        self.edge_views = []
        self.edges_by_node = {}
        self.empty_text = None
        self._press_pos = QPointF()
        self._layout_cache = None
        self.node_moved.connect(self._sync_positions)

    def _sync_positions(self, kind, nid, x, y):
        self.positions[(kind, nid)] = (x, y)
        self._layout_cache = None

    # ---------------- model ----------------
    def set_model(self, items, processes, recipes, positions=None,
                  classification=None, target_items=None):
        self.items = dict(items)
        self.processes = dict(processes)
        self.recipes = list(recipes)
        self.positions = dict(positions or {})
        self.classification = dict(classification or {})
        self.target_items = set(target_items or set())
        self._layout_cache = None
        self.rebuild()

    def _layout(self):
        if self._layout_cache is None:
            self._layout_cache = compute_positions(self.items, self.processes, self.recipes)
        return self._layout_cache

    def _position_for(self, key):
        if key in self.positions:
            return self.positions[key]
        return self._layout().get(key, (0.0, 0.0))

    def auto_arrange(self):
        self.positions = dict(compute_positions(self.items, self.processes, self.recipes))
        self._layout_cache = None
        self.rebuild()
        for key, (x, y) in self.positions.items():
            kind = 'item' if key[0] == 'item' else 'process'
            self.node_moved.emit(kind, key[1], x, y)

    # ---------------- helpers ----------------
    def focus_key(self):
        return (self.focus_kind, self.focus_id) if self.focus_id is not None else None

    def _recipes_producing(self, item_id):
        return [r for r in self.recipes if any(o.item_id == item_id for o in r.outputs)]

    def _recipes_consuming(self, item_id):
        return [r for r in self.recipes if any(i.item_id == item_id for i in r.inputs)]

    def _all_nodes(self):
        return {('item', i) for i in self.items} | {('process', p) for p in self.processes}

    def _neighbors_of(self, kind, nid):
        """All direct neighbors of a node (both directions)."""
        out = set()
        if kind == 'item':
            for r in self._recipes_producing(nid):
                out.add(('process', r.process_id))
                for inp in r.inputs:
                    out.add(('item', inp.item_id))
            for r in self._recipes_consuming(nid):
                out.add(('process', r.process_id))
                for o in r.outputs:
                    out.add(('item', o.item_id))
        else:
            for r in self.recipes:
                if r.process_id == nid:
                    for inp in r.inputs:
                        out.add(('item', inp.item_id))
                    for o in r.outputs:
                        out.add(('item', o.item_id))
        return out

    def _upstream_of(self, kind, nid):
        out = set()
        if kind == 'item':
            for r in self._recipes_producing(nid):
                out.add(('process', r.process_id))
                for inp in r.inputs:
                    out.add(('item', inp.item_id))
        else:
            for r in self.recipes:
                if r.process_id == nid:
                    for inp in r.inputs:
                        out.add(('item', inp.item_id))
        return out

    def _downstream_of(self, kind, nid):
        out = set()
        if kind == 'item':
            for r in self._recipes_consuming(nid):
                out.add(('process', r.process_id))
                for o in r.outputs:
                    out.add(('item', o.item_id))
        else:
            for r in self.recipes:
                if r.process_id == nid:
                    for o in r.outputs:
                        out.add(('item', o.item_id))
        return out

    def _connected_component(self, fk):
        seen = set()
        stack = [fk]
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            for nxt in self._neighbors_of(*k):
                if nxt not in seen:
                    stack.append(nxt)
        return seen

    def _upstream_set(self, fk):
        seen = set()
        stack = [fk]
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            for nxt in self._upstream_of(*k):
                if nxt not in seen:
                    stack.append(nxt)
        return seen

    def _downstream_set(self, fk):
        seen = set()
        stack = [fk]
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            for nxt in self._downstream_of(*k):
                if nxt not in seen:
                    stack.append(nxt)
        return seen

    def _compute_visible(self):
        all_nodes = self._all_nodes()
        if self.filter_mode == 'all' or self.focus_id is None:
            base = set(all_nodes)
        else:
            fk = self.focus_key()
            if self.filter_mode == 'direct':
                base = set([fk]) | self._neighbors_of(*fk)
            elif self.filter_mode == 'upstream':
                base = self._upstream_set(fk)
            elif self.filter_mode == 'downstream':
                base = self._downstream_set(fk)
            elif self.filter_mode == 'chain':
                base = self._connected_component(fk)
            else:
                base = set(all_nodes)

        # collapse
        if self.collapsed:
            hidden = set()
            for key in self.collapsed:
                stack = [key]
                local = set()
                while stack:
                    k = stack.pop()
                    for nxt in self._downstream_of(*k):
                        if nxt not in local:
                            local.add(nxt)
                            stack.append(nxt)
                hidden |= local
            hidden -= set(self.collapsed)
            base -= hidden

        # byproduct filter
        if not self.byproducts:
            bp = set()
            any_guaranteed = set()
            for r in self.recipes:
                for o in r.outputs:
                    (any_guaranteed.add(o.item_id) if o.probability >= 1.0 else bp.add(o.item_id))
            bp = bp - any_guaranteed
            focus = self.focus_key() if self.filter_mode != 'all' else None
            for (kind, nid) in list(base):
                if kind == 'item' and nid in bp and (focus is None or (kind, nid) != focus):
                    base.discard((kind, nid))

        # keep focus
        if self.focus_id is not None:
            base.add(self.focus_key())
        return base

    # ---------------- build ----------------
    def rebuild(self, keep_focus=False):
        self.clear()
        self.edge_views = []
        self.node_views = {}
        self.edges_by_node = {}
        self.empty_text = None

        visible = self._compute_visible()

        if not any(k[0] == 'item' for k in visible):
            self._add_empty_state()
            self._set_scene_rect(visible)
            return

        # nodes
        for key in list(visible):
            kind, nid = key
            if kind == 'item':
                item = self.items.get(nid)
                if not item:
                    continue
                cls = self.classification.get(nid, item.classification(0, 0))
                view = NodeView('item', nid, item.name,
                                icon_path=self._icon_path(item),
                                target=nid in self.target_items)
                view.set_classification(cls)
                view.setPos(*self._position_for(key))
                qty = self._qty_text_for(item)
                if qty:
                    view.set_qty_text(qty)
                self.node_views[key] = view
                self.addItem(view)
            elif kind == 'process':
                proc = self.processes.get(nid)
                if not proc:
                    continue
                view = NodeView('process', nid, proc.name,
                                icon_path=self._icon_path(proc))
                view.setPos(*self._position_for(key))
                qty = self._process_qty_text_for(proc.id)
                if qty:
                    view.set_qty_text(qty)
                self.node_views[key] = view
                self.addItem(view)

        # neighbors highlight for focus
        if self.focus_id is not None and self.filter_mode != 'all':
            fk = self.focus_key()
            neighbors = self._neighbors_of(fk[0], fk[1])
            for n in neighbors:
                nv = self.node_views.get(n)
                if nv:
                    nv.set_highlight(True)

        # edges
        for r in self.recipes:
            proc_key = ('process', r.process_id)
            if proc_key not in self.node_views:
                continue
            for inp in r.inputs:
                item_key = ('item', inp.item_id)
                if item_key not in self.node_views:
                    continue
                edge = self._make_edge(item_key, proc_key, False,
                                        label=f'×{format_qty(inp.quantity)}')
                if edge:
                    self.addItem(edge)
            for out in r.outputs:
                item_key = ('item', out.item_id)
                if item_key not in self.node_views:
                    continue
                is_byproduct = out.probability < 1.0
                if is_byproduct and not self.byproducts:
                    continue
                label_parts = [f'×{format_qty(out.quantity)}']
                if out.probability < 1.0:
                    label_parts.append(f'{out.probability * 100:.0f}%')
                edge = self._make_edge(proc_key, item_key, is_byproduct,
                                        label=' · '.join(label_parts))
                if edge:
                    self.addItem(edge)

        for edge in self.edge_views:
            self.edges_by_node.setdefault(edge.src_key, []).append(edge)
            self.edges_by_node.setdefault(edge.tgt_key, []).append(edge)

        self._set_scene_rect(visible)

    def _make_edge(self, src_key, tgt_key, dash, label):
        src_item = self.node_views[src_key]
        tgt_item = self.node_views[tgt_key]
        edge = EdgeView(src_key, tgt_key, dash=dash, label=label)
        src_radius = PROCESS_H * 0.58 if src_key[0] == 'process' else ITEM_RADIUS
        tgt_radius = PROCESS_H * 0.58 if tgt_key[0] == 'process' else ITEM_RADIUS
        edge.update_geometry(QPointF(src_item.x(), src_item.y()),
                            QPointF(tgt_item.x(), tgt_item.y()),
                            src_radius, tgt_radius)
        self.edge_views.append(edge)
        return edge

    def _add_empty_state(self):
        t = NodeLabel()
        t.setText('The database is empty.\nCreate your first item, processing method\nand recipe to start building the factory.')
        t.setFont(QFont('Segoe UI', 16, QFont.Normal))
        t.setTextWidth(520)
        t.setDefaultTextColor(QColor('#7c8594'))
        t.setPos(-260, -45)
        self.addItem(t)
        self.empty_text = t

    def _set_scene_rect(self, visible):
        margin = 340
        if not visible:
            self.setSceneRect(QRectF(-600, -300, 1200, 600))
            return
        x0 = y0 = None
        x1 = y1 = None
        for key in visible:
            x, y = self._position_for(key)
            if x0 is None:
                x0 = x1 = x
                y0 = y1 = y
            else:
                x0 = min(x0, x)
                x1 = max(x1, x)
                y0 = min(y0, y)
                y1 = max(y1, y)
        self.setSceneRect(QRectF(x0 - margin, y0 - margin, (x1 - x0) + margin * 2, (y1 - y0) + margin * 2))

    def _icon_path(self, obj):
        path = getattr(obj, 'image_path', '') or getattr(obj, 'icon_path', '')
        if not path:
            return ''
        from . import util
        p = util.data_dir() / path
        return str(p) if p.exists() else path

    def _qty_text_for(self, item):
        return ''

    def _process_qty_text_for(self, process_id):
        return ''

    # ---------------- interaction ----------------
    def mousePressEvent(self, event):
        self._press_pos = event.scenePos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # persist any node whose position changed since last rebuild
        for key, view in list(self.node_views.items()):
            pos = view.pos()
            saved = self.positions.get(key)
            if saved is not None and (abs(saved[0] - pos.x()) > 0.01 or abs(saved[1] - pos.y()) > 0.01):
                kind = 'item' if key[0] == 'item' else 'process'
                self.node_moved.emit(kind, key[1], pos.x(), pos.y())
        # click detection
        moved = (event.scenePos() - self._press_pos).manhattanLength()
        item = self.itemAt(event.scenePos(), Qt.ItemSendsScenePositionToParent)
        node = self._node_for_item(item)
        if moved < 8 and node is not None:
            self.node_clicked.emit(node.key)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        item = self.itemAt(event.scenePos(), Qt.ItemSendsScenePositionToParent)
        node = self._node_for_item(item)
        if node is not None:
            self.node_double_clicked.emit(node.key)

    def _node_for_item(self, item):
        while item is not None:
            if isinstance(item, NodeView):
                return item
            item = item.parentItem()
        return None

    def itemChanged(self, item, change, value):
        super().itemChanged(item, change, value)
        if isinstance(item, NodeView) and change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges_by_node.get(item.key, []):
                self._refresh_edge(edge)

    def _refresh_edge(self, edge):
        src_node = self.node_views.get(edge.src_key)
        tgt_node = self.node_views.get(edge.tgt_key)
        if not src_node or not tgt_node:
            edge.setVisible(False)
            return
        src_radius = PROCESS_H * 0.58 if edge.src_key[0] == 'process' else ITEM_RADIUS
        tgt_radius = PROCESS_H * 0.58 if edge.tgt_key[0] == 'process' else ITEM_RADIUS
        edge.update_geometry(QPointF(src_node.x(), src_node.y()),
                            QPointF(tgt_node.x(), tgt_node.y()),
                            src_radius, tgt_radius)
        edge.setVisible(True)

    def persist_positions(self):
        for key, view in self.node_views.items():
            pos = view.pos()
            kind = 'item' if key[0] == 'item' else 'process'
            self.node_moved.emit(kind, key[1], pos.x(), pos.y())

    def set_selected(self, key):
        for k, nv in self.node_views.items():
            nv.set_selected(k == key)

    def get_node(self, key):
        return self.node_views.get(key)


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------

class GraphView(QGraphicsView):
    min_scale = 0.1
    max_scale = 5.5

    def __init__(self, scene=None, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QColor(PALETTE['background']))
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setRubberBandSelectionVisible(False)
        self._scale = 1.0

    # -- navigation ------------------------------------------------------
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return super().wheelEvent(event)
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self.zoom_at_cursor(factor, event.pos())

    def zoom_at_cursor(self, factor, pos):
        new_scale = max(self.min_scale, min(self.max_scale, self._scale * factor))
        if new_scale == self._scale:
            return
        old_scene_pos = self.mapToScene(pos)
        self.scale(new_scale / self._scale, new_scale / self._scale)
        offset = pos - self.mapFromScene(old_scene_pos)
        if offset.manhattanLength() > 0.01:
            self.translate(offset.x(), offset.y())
        self._scale = new_scale

    def zoom_in(self):
        self.zoom_at_cursor(1.25, self.viewport().rect().center())

    def zoom_out(self):
        self.zoom_at_cursor(1.0 / 1.25, self.viewport().rect().center())

    def reset_view(self):
        self._scale = 1.0
        self.resetTransform()

    def fit_to_view(self):
        if not self.scene():
            return
        rect = self.scene().sceneRect()
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        vp = self.viewport().size()
        sx = vp.width() / rect.width()
        sy = vp.height() / rect.height()
        scale = min(sx, sy)
        scale = max(0.35, min(self.max_scale, scale * 0.96))
        self._scale = scale
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(rect.center())

    def center_on(self, key, zoom_if_small=False):
        node = self.scene().get_node(key)
        if not node:
            return
        self.centerOn(node.pos())
        if zoom_if_small and self._scale < 1.0:
            self.zoom_at_cursor(1.3, self.viewport().rect().center())

    # -- context menu ------------------------------------------------------
    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, Qt.ItemSendsScenePositionToParent)
        node = self.scene()._node_for_item(item) if item else None
        if node is not None:
            key = node.key
            if key in self.scene().collapsed:
                act = menu.addAction('Expand branch')
                act.triggered.connect(lambda: self._toggle_collapse(key))
            else:
                act = menu.addAction('Collapse branch')
                act.triggered.connect(lambda: self._toggle_collapse(key))
            menu.addSeparator()
            for mode, label in (('direct', 'Filter: direct connections'),
                                ('upstream', 'Filter: upstream chain'),
                                ('downstream', 'Filter: downstream chain'),
                                ('chain', 'Filter: full production chain')):
                act = menu.addAction(label)
                act.triggered.connect(lambda checked, m=mode, k=key: self._set_filter(m, k))
            menu.addSeparator()
            act = menu.addAction('Show everything')
            act.triggered.connect(lambda: self._clear_filter())
            menu.exec(event.globalPos())
        else:
            act = menu.addAction('Auto-arrange')
            act.triggered.connect(lambda: self.scene().auto_arrange())
            act = menu.addAction('Reset view')
            act.triggered.connect(lambda: self.reset_view())
            act = menu.addAction('Fit to view')
            act.triggered.connect(lambda: self.fit_to_view())
            menu.exec(event.globalPos())

    def _toggle_collapse(self, key):
        if key in self.scene().collapsed:
            self.scene().collapsed.discard(key)
        else:
            self.scene().collapsed.add(key)
        self.scene().rebuild()

    def _set_filter(self, mode, focus_key):
        self.scene().focus_kind, self.scene().focus_id = focus_key
        self.scene().filter_mode = mode
        self.scene().rebuild()

    def _clear_filter(self):
        self.scene().focus_kind = None
        self.scene().focus_id = None
        self.scene().filter_mode = 'all'
        self.scene().rebuild()


# ---------------------------------------------------------------------------
# calculator graph
# ---------------------------------------------------------------------------

class CalcScene(GraphScene):
    """Scene for the calculator's production plan."""

    def set_calc(self, calc, recipes, items, processes, positions=None):
        self.calc = calc
        self.set_model(items, processes, recipes, positions, target_items=set(calc.targets))

    def _qty_text_for(self, item):
        c = self.calc
        if not c:
            return ''
        parts = []
        if item.id in c.targets:
            parts.append(f'TARGET ×{format_qty(c.targets[item.id])}')
        raw_amt = c.inputs_demand.get(item.id)
        if raw_amt and raw_amt > 0:
            parts.append(f'raw ×{format_qty(raw_amt)}')
        produced = c.produced_expected.get(item.id)
        if produced is not None and produced > 0 and item.id not in c.targets:
            parts.append(f'~{format_qty(produced)}')
        return '  ·  '.join(parts)

    def _process_qty_text_for(self, process_id):
        c = self.calc
        if not c:
            return ''
        runs = c.operation_counts.get(process_id, 0)
        if runs <= 0:
            return ''
        return f'×{runs}'
