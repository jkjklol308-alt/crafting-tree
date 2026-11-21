"""Left sidebar: search, categories and the item database list."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QSizePolicy,
)

from .theme import PALETTE
from .models import Item

_STATUS_COLOR = {
    'raw': PALETTE['raw'],
    'intermediate': PALETTE['intermediate'],
    'final': PALETTE['final'],
}


def _dot_icon(color):
    pm = QPixmap(14, 14)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 12, 12)
    p.end()
    return QIcon(pm)


class SideBar(QWidget):
    item_selected = Signal(int)
    item_double_clicked = Signal(int)
    new_item_requested = Signal()
    new_recipe_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._classification = {}
        self._filter_text = ''
        self._category = '__ALL__'

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel('DATABASE'))
        header.addStretch()
        layout.addLayout(header)

        self.search = QLineEdit()
        self.search.setPlaceholderText('Search items, tags, categories…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)

        cat_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.setMinimumHeight(32)
        self.category_combo.currentIndexChanged.connect(self._category_changed)
        cat_row.addWidget(self.category_combo, 1)
        layout.addLayout(cat_row)

        self.list = QListWidget()
        self.list.setVisible(True)
        self.list.itemClicked.connect(self._item_clicked)
        self.list.itemDoubleClicked.connect(self._item_double_clicked)
        layout.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        new_item = QPushButton('+ Item')
        new_item.setObjectName('primaryBtn')
        new_item.clicked.connect(self.new_item_requested.emit)
        new_recipe = QPushButton('+ Recipe')
        new_recipe.setObjectName('ghostBtn')
        new_recipe.clicked.connect(self.new_recipe_requested.emit)
        btn_row.addWidget(new_item)
        btn_row.addWidget(new_recipe)
        layout.addLayout(btn_row)

        self._item_class = {}

    def set_data(self, items, classification):
        self._items = list(items)
        self._classification = dict(classification)
        self._rebuild_categories()
        self._refresh()

    def set_classification(self, ids_to_class):
        self._classification.update(ids_to_class)
        self._refresh()

    def _rebuild_categories(self):
        cats = {}
        for it in self._items:
            cat = it.category or '(no category)'
            cats[cat] = cats.get(cat, 0) + 1
        self.category_combo.blockSignals(True)
        current = self.category_combo.currentText()
        self.category_combo.clear()
        self.category_combo.addItem('All categories', '__ALL__')
        for cat in sorted(cats.keys(), key=str.lower):
            self.category_combo.addItem(f'{cat}  ({cats[cat]})', cat)
        # restore selection
        idx = 0
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == self._category:
                idx = i
                break
        self.category_combo.setCurrentIndex(idx)
        self.category_combo.blockSignals(False)

    def _category_changed(self, idx):
        data = self.category_combo.itemData(idx)
        self._category = data if data else '__ALL__'
        self._refresh()

    def _filtered_items(self):
        text = self._filter_text.strip().lower()

        def matches(it):
            if self._category != '__ALL__' and (it.category or '(no category)') != self._category:
                return False
            if not text:
                return True
            hay = ' '.join([it.name, it.category or '', it.description or ''] + list(it.tags or [])).lower()
            return text in hay

        return [it for it in self._items if matches(it)]

    def _refresh(self):
        text = self.search.text().strip().lower()

        def matches(it):
            if self._category != '__ALL__' and (it.category or '(no category)') != self._category:
                return False
            if not text:
                return True
            hay = ' '.join([it.name, it.category or '', it.description or ''] + list(it.tags or [])).lower()
            return text in hay

        filtered = [it for it in self._items if matches(it)]
        self.list.clear()
        for it in filtered:
            row = QListWidgetItem(it.name)
            row.setData(Qt.UserRole, it.id)
            cls = self._classification.get(it.id, 'raw')
            row.setIcon(_dot_icon(_STATUS_COLOR.get(cls, PALETTE['intermediate'])))
            tooltip = []
            if it.category:
                tooltip.append(f'Category: {it.category}')
            tooltip.append(f'{cls.capitalize()}')
            row.setToolTip('\n'.join(tooltip))
            self.list.addItem(row)

        if not filtered:
            q = QListWidgetItem('No items found' if text or self._category != '__ALL__' else 'No items yet')
            q.setFlags(Qt.NoItemFlags)
            self.list.addItem(q)

    def select_item(self, item_id, scroll=True):
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it and it.data(Qt.UserRole) == item_id:
                self.list.setCurrentRow(i)
                if scroll:
                    self.list.scrollToItem(it)
                return

    def _item_clicked(self, row):
        self.item_selected.emit(row.data(Qt.UserRole))

    def _item_double_clicked(self, row):
        self.item_double_clicked.emit(row.data(Qt.UserRole))
