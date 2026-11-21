"""Item and processing-method dialogs (create / edit)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QHBoxLayout, QLabel, QFileDialog, QMessageBox,
)

from . import util
from .models import Item, ProcessMethod, parse_tags
from .db import Database

IMAGE_FILTER = 'Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)'


class ThumbnailLabel(QLabel):
    """Image preview that repaints itself whenever ``set_path`` is called."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignCenter)
        self.set_path('')

    def set_path(self, path):
        pix = QPixmap()
        if path:
            pix = QPixmap(path)
        if not pix.isNull():
            scaled = pix.scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
            self.setText('')
            self.setStyleSheet('border: 1px solid #2b313c; border-radius: 8px; background: #181b21;')
        else:
            self.setPixmap(QPixmap())
            self.setText('?')
            self.setStyleSheet('border: 1px dashed #2b313c; border-radius: 8px; background: #181b21; color: #7c8594; font-size: 22px;')


class _ImagePicker:
    """Mixin (non-QObject) holding the image-upload/thumbnail logic."""

    def _field_row(self, root):
        row = QHBoxLayout()
        self.thumb = ThumbnailLabel(self)
        row.addWidget(self.thumb)
        col = QVBoxLayout()
        col.addStretch()
        up = QPushButton('Upload image…')
        up.clicked.connect(self._upload_image)
        rm = QPushButton('Remove image')
        rm.setObjectName('ghostBtn')
        rm.clicked.connect(self._remove_image)
        col.addWidget(up)
        col.addWidget(rm)
        col.addStretch()
        row.addLayout(col)
        root.addLayout(row)
        return row

    def _upload_image(self):
        src, _ = QFileDialog.getOpenFileName(self, 'Select image', '', IMAGE_FILTER)
        if not src:
            return
        try:
            stored = util.store_image(self.project_id, src, util.unique_stored_name(src))
        except Exception as e:
            QMessageBox.warning(self, 'Upload failed', str(e))
            return
        self._stored_image = stored
        self.thumb.set_path(self._absolute_path())

    def _remove_image(self):
        self._stored_image = ''
        self.thumb.set_path('')

    def _absolute_path(self):
        if not self._stored_image:
            return ''
        p = util.data_dir() / self._stored_image
        return str(p) if p.exists() else ''


class ItemDialog(_ImagePicker, QDialog):
    def __init__(self, parent, db: Database, project_id: int, item: Item | None = None,
                 categories: list | None = None, is_edit=False):
        QDialog.__init__(self, parent)
        self.db = db
        self.project_id = project_id
        self.item = item
        self.is_edit = is_edit
        self._stored_image = item.image_path if item else ''

        self.setWindowTitle('Edit item' if is_edit else 'New item')
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        self._field_row(root)

        form = QFormLayout()
        form.setSpacing(10)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('e.g. Cobblestone')
        form.addRow('Name *', self.name_edit)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(['Ore', 'Mineral', 'Component', 'Building material', 'Byproduct', 'Other'])
        for cat in self._unique_categories(categories):
            self.category_combo.addItem(cat)
        form.addRow('Category', self.category_combo)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText('comma separated, e.g. ore, crushed')
        form.addRow('Tags', self.tags_edit)
        root.addLayout(form)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText('Optional description, recipe notes, source...')
        self.desc_edit.setFixedHeight(90)
        root.addWidget(self.desc_edit)

        self.thumb.set_path(self._absolute_path())

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        save = QPushButton('Save')
        save.setObjectName('primaryBtn')
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        if item:
            self.name_edit.setText(item.name)
            self.category_combo.setCurrentText(item.category or '')
            self.tags_edit.setText(', '.join(item.tags or []))
            self.desc_edit.setPlainText(item.description or '')

    def _unique_categories(self, categories):
        seen = set()
        out = []
        for cat_raw in (categories or []):
            name = cat_raw if isinstance(cat_raw, str) else cat_raw.get('category', '')
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
        return out

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, 'Invalid item', 'Item name is required.')
            self.name_edit.setFocus()
            return
        category = self.category_combo.currentText().strip()
        tags = parse_tags(self.tags_edit.text())
        description = self.desc_edit.toPlainText().strip()
        try:
            if self.is_edit:
                self.db.update_item(self.item.id, name=name, description=description,
                                    category=category, tags=tags, image_path=self._stored_image)
            else:
                self.created_id = self.db.create_item(self.project_id, name, description, category, tags, self._stored_image)
        except Exception as e:
            QMessageBox.warning(self, 'Save failed', str(e))
            return
        self.accept()


class ProcessDialog(_ImagePicker, QDialog):
    def __init__(self, parent, db: Database, project_id: int, process: ProcessMethod | None = None, is_edit=False):
        QDialog.__init__(self, parent)
        self.db = db
        self.project_id = project_id
        self.process = process
        self.is_edit = is_edit
        self._stored_image = process.icon_path if process else ''

        self.setWindowTitle('Edit processing method' if is_edit else 'New processing method')
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        self._field_row(root)

        form = QFormLayout()
        form.setSpacing(10)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('e.g. Crushing')
        form.addRow('Name *', self.name_edit)
        root.addLayout(form)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText('Optional description, e.g. where it is used')
        self.desc_edit.setFixedHeight(90)
        root.addWidget(self.desc_edit)

        self.thumb.set_path(self._absolute_path())

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        save = QPushButton('Save')
        save.setObjectName('primaryBtn')
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        if process:
            self.name_edit.setText(process.name)
            self.desc_edit.setPlainText(process.description or '')

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, 'Invalid process', 'Processing method name is required.')
            self.name_edit.setFocus()
            return
        description = self.desc_edit.toPlainText().strip()
        try:
            if self.is_edit:
                self.db.update_process(self.process.id, name=name, description=description, icon_path=self._stored_image)
            else:
                self.created_id = self.db.create_process(self.project_id, name, description, self._stored_image)
        except Exception as e:
            QMessageBox.warning(self, 'Save failed', str(e))
            return
        self.accept()
