"""Right sidebar: selected-item information with navigation breadcrumbs."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QGridLayout, QSizePolicy, QSpacerItem, QSplitter,
)

from . import util
from .models import Item, ProcessMethod, Recipe
from .theme import PALETTE


def _chip_button(text, color=None, text_color=None, border=None):
    btn = QPushButton(text)
    btn.setObjectName('chipBtn')
    color = color or '#23272f'
    text_color = text_color or '#c4ccd8'
    btn.setStyleSheet(f'''
        QPushButton {{
            background: {color}; border: 1px solid {border or '#2b313c'};
            border-radius: 8px; color: {text_color}; padding: 4px 11px; font-size: 12px; font-weight: 600;
        }}
        QPushButton:hover {{ border-color: #ffb454; color: #ffd28a; }}
    ''')
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def _badge(text, color):
    btn = QPushButton(text)
    btn.setObjectName('badgeBtn')
    btn.setEnabled(False)
    btn.setStyleSheet(f'''
        QPushButton {{
            background: {color}; color: #10131a; border: 0; border-radius: 8px;
            padding: 3px 10px; font-size: 10px; font-weight: 800; letter-spacing: 0.6px;
        }}
    ''')
    return btn


class _SectionLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet('color: #9aa3b2; font-weight: 700; letter-spacing: 1.3px; font-size: 11px; margin-top: 14px;')


class BreadcrumbBar(QWidget):
    navigate = Signal(int, str)   # (kind, id)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._layout = layout
        empty = QLabel('Nothing inspected yet')
        empty.setStyleSheet('color: #6b7280; font-size: 11px;')
        layout.addWidget(empty)
        layout.addStretch()

    def set_history(self, history, items_by_id, processes_by_id):
        self._clear()
        if not history:
            self._layout.addWidget(self._make_label('Nothing inspected yet'))
            self._layout.addStretch()
            return
        shown = history[-6:]
        for i, (kind, nid) in enumerate(shown):
            label = None
            if kind == 'item':
                it = items_by_id.get(nid)
                label = it.name if it else '?'
            elif kind == 'process':
                pr = processes_by_id.get(nid)
                label = pr.name if pr else '?'
            if label is None:
                continue
            if i > 0:
                arrow = QLabel('→')
                arrow.setStyleSheet('color: #525b69; font-size: 10px;')
                self._layout.addWidget(arrow)
            btn = _chip_button(label, color='#1e222a', text_color='#aab2c2')
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=kind, i=nid: self.navigate.emit(k, i))
            self._layout.addWidget(btn)
        self._layout.addStretch()

    def _make_label(self, text):
        l = QLabel(text)
        l.setStyleSheet('color: #6b7280; font-size: 11px;')
        return l

    def _clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class InfoPanel(QWidget):
    navigate_item = Signal(int)
    navigate_process = Signal(int)
    edit_item = Signal(int)
    edit_process = Signal(int)
    delete_item = Signal(int)
    delete_process = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = []
        self._history_cap = 24

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self.breadcrumbs = BreadcrumbBar()
        self.breadcrumbs.navigate.connect(self._breadcrumb_clicked)
        root.addWidget(self.breadcrumbs)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(self.scroll, 1)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(8)
        self.scroll.setWidget(self.content)

    # ---------------- navigation history -----------------
    def push_history(self, kind, nid):
        if self._history and self._history[-1] == (kind, nid):
            return
        self._history.append((kind, nid))
        del self._history[:-self._history_cap]

    def _breadcrumb_clicked(self, kind, nid):
        # pop history up to the clicked entry
        idx = None
        for i in range(len(self._history) - 1, -1, -1):
            if self._history[i] == (kind, nid):
                idx = i
                break
        if idx is not None:
            del self._history[idx + 1:]
        if kind == 'item':
            self.navigate_item.emit(nid)
        else:
            self.navigate_process.emit(nid)

    # ---------------- rendering ----------------
    def set_empty(self):
        self._clear_content()
        empty = QLabel('Select an item or processing\nmethod to explore the\nproduction network.')
        empty.setStyleSheet('color: #6b7280; font-size: 15px; line-height: 1.5;')
        empty.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(empty, alignment=Qt.AlignCenter)
        self.content_layout.addStretch()
        self.breadcrumbs.set_history(self._history, {}, {})

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_chip_row(self, label, chips):
        """Chips: list of (text, kind, id) or plain strings."""
        if not chips:
            return
        section = _SectionLabel(label)
        self.content_layout.addWidget(section)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        columns = 4
        for i, chip in enumerate(chips):
            r, c = divmod(i, columns)
            if isinstance(chip, tuple):
                text = chip[0]
                kind = chip[1]
                nid = chip[2]
                btn = _chip_button(text)
                btn.clicked.connect(lambda checked, k=kind, n=nid: self._navigate(k, n))
                grid.addWidget(btn, r, c)
            else:
                grid.addWidget(_chip_button(str(chip)), r, c)
        self.content_layout.addLayout(grid)

    def _navigate(self, kind, nid):
        if kind == 'item':
            self.navigate_item.emit(nid)
        else:
            self.navigate_process.emit(nid)

    # ---------------- full update ----------------
    def show_item(self, item, items_by_id, processes_by_id, classification, produced_by, can_produce, parent_recipes_used=None):
        self._clear_content()
        self.push_history('item', item.id)

        # header card
        card = QFrame()
        card.setStyleSheet('QFrame { background: #1f232b; border: 1px solid #2b313c; border-radius: 12px; }')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        row = QHBoxLayout()
        thumb = QLabel()
        thumb.setFixedSize(52, 52)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet('border: 1px solid #2b313c; border-radius: 10px; background: #181b21;')
        pix = QPixmap()
        if item.image_path:
            pix = QPixmap(str(util.data_dir() / item.image_path))
        if not pix.isNull():
            thumb.setPixmap(pix.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            cls_color = {'raw': PALETTE['raw'], 'intermediate': PALETTE['intermediate'], 'final': PALETTE['final']}[classification]
            thumb.setStyleSheet(f'border: 1px solid #2b313c; border-radius: 10px; background: {cls_color}33; color: #eef1f6; font-size: 18px; font-weight: 700;')
            thumb.setText('?')
        row.addWidget(thumb)

        head = QVBoxLayout()
        head.setSpacing(4)
        name_label = QLabel(item.name)
        name_label.setStyleSheet('font-size: 17px; font-weight: 800; color: #eef1f6;')
        head.addWidget(name_label)
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        badge_row.addWidget(_badge(classification.upper(), {'raw': PALETTE['raw'], 'intermediate': PALETTE['intermediate'], 'final': PALETTE['final']}[classification]))
        if item.category:
            badge_row.addWidget(_badge(item.category.upper(), '#2c313b'))
        badge_row.addStretch()
        head.addLayout(badge_row)
        row.addLayout(head, 1)
        card_layout.addLayout(row)

        if item.description:
            desc = QLabel(item.description)
            desc.setStyleSheet('color: #9aa3b2; line-height: 1.4;')
            desc.setWordWrap(True)
            card_layout.addWidget(desc)

        chips = [f'#{t}' for t in (item.tags or [])]
        if chips:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(5)
            for t in chips:
                chip_row.addWidget(_chip_button(t))
            chip_row.addStretch()
            card_layout.addLayout(chip_row)

        buttons = QHBoxLayout()
        edit_btn = QPushButton('Edit')
        edit_btn.clicked.connect(lambda: self.edit_item.emit(item.id))
        delete_btn = QPushButton('Delete')
        delete_btn.setObjectName('dangerBtn')
        delete_btn.clicked.connect(lambda: self.delete_item.emit(item.id))
        buttons.addWidget(edit_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch()
        card_layout.addLayout(buttons)

        self.content_layout.addWidget(card)

        # breadcrumb
        self.breadcrumbs.set_history(self._history, items_by_id, processes_by_id)

        self._add_section('PRODUCED BY', produced_by, items_by_id, processes_by_id,
                          mode='produced_by', self_item=item)
        self._add_section('CAN PRODUCE', can_produce, items_by_id, processes_by_id,
                          mode='can_produce', self_item=item)
        self.content_layout.addStretch()

    def show_process(self, proc, recipes, items_by_id, processes_by_id):
        self._clear_content()
        self.push_history('process', proc.id)

        card = QFrame()
        card.setStyleSheet('QFrame { background: #1f232b; border: 1px solid #2b313c; border-radius: 12px; }')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        row = QHBoxLayout()
        thumb = QLabel()
        thumb.setFixedSize(52, 52)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(f'border: 1px solid #2b313c; border-radius: 10px; background: {PALETTE["process"]}33;')
        pix = QPixmap()
        if proc.icon_path:
            pix = QPixmap(str(util.data_dir() / proc.icon_path))
        if not pix.isNull():
            thumb.setPixmap(pix.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            thumb.setText('⚗')
            thumb.setStyleSheet(f'border: 1px solid #2b313c; border-radius: 10px; background: {PALETTE["process"]}33; color: #eef1f6; font-size: 20px;')
        row.addWidget(thumb)

        head = QVBoxLayout()
        head.setSpacing(4)
        name_label = QLabel(proc.name)
        name_label.setStyleSheet('font-size: 17px; font-weight: 800; color: #eef1f6;')
        head.addWidget(name_label)
        badge_row = QHBoxLayout()
        badge_row.addWidget(_badge('PROCESS', PALETTE['process']))
        badge_row.addStretch()
        head.addLayout(badge_row)
        row.addLayout(head, 1)
        card_layout.addLayout(row)

        if proc.description:
            desc = QLabel(proc.description)
            desc.setWordWrap(True)
            desc.setStyleSheet('color: #9aa3b2; line-height: 1.4;')
            card_layout.addWidget(desc)

        buttons = QHBoxLayout()
        edit_btn = QPushButton('Edit')
        edit_btn.clicked.connect(lambda: self.edit_process.emit(proc.id))
        delete_btn = QPushButton('Delete')
        delete_btn.setObjectName('dangerBtn')
        delete_btn.clicked.connect(lambda: self.delete_process.emit(proc.id))
        buttons.addWidget(edit_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch()
        card_layout.addLayout(buttons)

        self.content_layout.addWidget(card)
        self.breadcrumbs.set_history(self._history, items_by_id, processes_by_id)

        section = _SectionLabel('USED IN')
        self.content_layout.addWidget(section)
        if recipes:
            for r in recipes:
                self._add_recipe_card(r, items_by_id, processes_by_id)
        else:
            self.content_layout.addWidget(QLabel('No recipes use this processing method yet.'))
        self.content_layout.addStretch()

    def _add_recipe_card(self, recipe, items_by_id, processes_by_id):
        card = QFrame()
        card.setStyleSheet('QFrame { background: #21262f; border: 1px solid #2b313c; border-radius: 10px; }')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        proc = processes_by_id.get(recipe.process_id)
        proc_name = proc.name if proc else '?'

        header = QHBoxLayout()
        proc_btn = _chip_button(proc_name, color=f'{PALETTE["process"]}26', text_color='#d3b3ec', border=f'{PALETTE["process"]}55')
        if proc:
            proc_btn.clicked.connect(lambda checked, pid=proc.id: self.navigate_process.emit(pid))
        header.addWidget(proc_btn)
        if recipe.name:
            name_label = QLabel(recipe.name)
            name_label.setStyleSheet('color: #aab2c2; font-size: 12px;')
            header.addWidget(name_label, 1)
        header.addStretch()
        card_layout.addLayout(header)

        # inputs
        if recipe.inputs:
            in_label = QLabel('Inputs')
            in_label.setStyleSheet('color: #7c8594; font-size: 10px; font-weight: 700; letter-spacing: 1px;')
            card_layout.addWidget(in_label)
            row = QHBoxLayout()
            row.setSpacing(5)
            row.setAlignment(Qt.AlignLeft)
            for inp in recipe.inputs:
                itm = items_by_id.get(inp.item_id)
                chip_text = f'×{_fmt(inp.quantity)}  {itm.name if itm else "?"}'
                chip = _chip_button(chip_text)
                if itm:
                    chip.clicked.connect(lambda checked, iid=itm.id: self.navigate_item.emit(iid))
                row.addWidget(chip)
            row.addStretch()
            card_layout.addLayout(row)

        # outputs
        if recipe.outputs:
            out_label = QLabel('Outputs')
            out_label.setStyleSheet('color: #7c8594; font-size: 10px; font-weight: 700; letter-spacing: 1px;')
            card_layout.addWidget(out_label)
            row = QHBoxLayout()
            row.setSpacing(5)
            row.setAlignment(Qt.AlignLeft)
            for out in recipe.outputs:
                itm = items_by_id.get(out.item_id)
                chip_text = f'×{_fmt(out.quantity)}  {itm.name if itm else "?"}'
                if out.probability < 1.0:
                    chip_text += f'  · {out.probability * 100:.0f}%'
                chip = _chip_button(
                    chip_text,
                    color='#2b2133' if out.probability < 1.0 else '#21302a',
                    text_color='#d3b3ec' if out.probability < 1.0 else '#a6d9bc',
                    border='#3d2c4d' if out.probability < 1.0 else '#2d4a37')
                if out.probability < 1.0:
                    chip.setToolTip('Byproduct — produced with reduced probability')
                if itm:
                    chip.clicked.connect(lambda checked, iid=itm.id: self.navigate_item.emit(iid))
                row.addWidget(chip)
            row.addStretch()
            card_layout.addLayout(row)

        self.content_layout.addWidget(card)

    def _add_section(self, title, recipes, items_by_id, processes_by_id, mode, self_item):
        section = _SectionLabel(f'{title}  ({len(recipes)})')
        self.content_layout.addWidget(section)
        if not recipes:
            self.content_layout.addWidget(QLabel('None'))
            return
        for r in recipes:
            self._add_recipe_card(r, items_by_id, processes_by_id)


def _fmt(v):
    return util.format_qty(v)
