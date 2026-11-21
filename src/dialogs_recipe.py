"""Recipe create / edit dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QPushButton, QLabel, QScrollArea, QWidget, QFrame, QMessageBox,
    QDoubleSpinBox, QCompleter,
)

from . import util
from .models import Item, ProcessMethod, Recipe, RecipeInput, RecipeOutput
from .db import Database


def _item_completer(combo, items):
    names = [it.name for it in items]
    completer = QCompleter(names)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    combo.setCompleter(completer)
    combo.setEditable(True)


def _resolve_item(name, items):
    if not name:
        return None
    key = name.strip().lower()
    for it in items:
        if it.name.lower() == key:
            return it
    return None


class _RecipeRow(QWidget):
    remove_requested = Signal()

    def __init__(self, parent, kind, items, name='', qty=1.0, prob=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.item_combo = QComboBox()
        _item_completer(self.item_combo, items)
        self.item_combo.setMinimumWidth(220)
        layout.addWidget(self.item_combo, 2)

        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 999999)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setValue(qty)
        self.qty_spin.setMinimumWidth(100)
        layout.addWidget(self.qty_spin, 1)

        self.prob_spin = None
        if kind == 'output':
            self.prob_spin = QDoubleSpinBox()
            self.prob_spin.setRange(1, 100)
            self.prob_spin.setSuffix('%')
            self.prob_spin.setValue(int(round((prob if prob is not None else 1.0) * 100)))
            self.prob_spin.setMinimumWidth(80)
            layout.addWidget(self.prob_spin, 1)

        self.remove_btn = QPushButton('✕')
        self.remove_btn.setObjectName('ghostBtn')
        self.remove_btn.setToolTip('Remove row')
        self.remove_btn.setFixedWidth(34)
        self.remove_btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(self.remove_btn)

        if name:
            self.item_combo.setCurrentText(name)

    def data(self):
        return {
            'name': self.item_combo.currentText().strip(),
            'qty': float(self.qty_spin.value()),
            'prob': (float(self.prob_spin.value()) / 100.0) if self.prob_spin else None,
        }


class RecipeDialog(QDialog):
    new_process_created = Signal(int)   # process id

    def __init__(self, parent, db: Database, project_id: int, recipe: Recipe | None = None,
                 items=None, processes=None, is_edit=False):
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.recipe = recipe
        self.is_edit = is_edit
        self._items = items if items else []
        self._processes = processes if processes else []

        self.setWindowTitle('Edit recipe' if is_edit else 'New recipe')
        self.setModal(True)
        self.resize(760, 760)
        self.setMinimumWidth(700)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # header: process + name
        form = QFormLayout()
        form.setSpacing(8)
        form_w = QWidget()
        form_w.setLayout(form)
        form.setFormAlignment(Qt.AlignTop)
        root.addWidget(form_w)

        proc_row = QHBoxLayout()
        self.process_combo = QComboBox()
        self.process_combo.setMinimumWidth(400)
        self._fill_processes()
        proc_row.addWidget(self.process_combo, 2)
        new_proc_btn = QPushButton('+ New process')
        new_proc_btn.setObjectName('ghostBtn')
        new_proc_btn.clicked.connect(self._open_process_dialog)
        proc_row.addWidget(new_proc_btn)
        form.addRow('Processing method *', proc_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Optional recipe name, e.g. "Smelt Iron Ore"')
        form.addRow('Recipe name', self.name_edit)

        # scrollable section
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setSpacing(10)
        content_layout.setAlignment(Qt.AlignTop)

        # inputs group
        content_layout.addWidget(self._group_label('INPUTS'))
        self.inputs_layout = QVBoxLayout()
        self.inputs_layout.setSpacing(6)
        content_layout.addLayout(self.inputs_layout)
        add_inputs = QPushButton('+ Add input')
        add_inputs.setObjectName('ghostBtn')
        add_inputs.clicked.connect(lambda: self._add_row('input'))
        content_layout.addWidget(add_inputs, 0, Qt.AlignLeft)

        content_layout.addWidget(self._group_label('OUTPUTS'))
        self.outputs_layout = QVBoxLayout()
        self.outputs_layout.setSpacing(6)
        content_layout.addLayout(self.outputs_layout)
        add_outputs = QPushButton('+ Add output')
        add_outputs.setObjectName('ghostBtn')
        add_outputs.clicked.connect(lambda: self._add_row('output'))
        content_layout.addWidget(add_outputs, 0, Qt.AlignLeft)

        content_layout.addWidget(self._group_label('NOTES'))
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(70)
        self.notes_edit.setPlaceholderText('Optional notes')
        content_layout.addWidget(self.notes_edit)
        content_layout.addStretch()
        scroll.setWidget(self.content)
        root.addWidget(scroll, 1)

        # buttons
        buttons = QHBoxLayout()
        if self.is_edit:
            delete = QPushButton('Delete recipe')
            delete.setObjectName('dangerBtn')
            delete.clicked.connect(self._delete)
            buttons.addWidget(delete)
        buttons.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        save = QPushButton('Save recipe')
        save.setObjectName('primaryBtn')
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        # populate
        if not self.is_edit:
            self._add_row('input')
            self._add_row('output')
        else:
            self.name_edit.setText(recipe.name or '')
            self.notes_edit.setPlainText(recipe.notes or '')
            proc_name = ''
            for p in self._processes:
                if p.id == recipe.process_id:
                    proc_name = p.name
                    break
            if proc_name:
                self.process_combo.setCurrentText(proc_name)
            for inp in recipe.inputs:
                item = self._item_by_id(inp.item_id)
                self._add_row('input', name=item.name if item else '', qty=inp.quantity)
            for out in recipe.outputs:
                item = self._item_by_id(out.item_id)
                self._add_row('output', name=item.name if item else '', qty=out.quantity, prob=out.probability)

    def _group_label(self, text):
        l = QLabel(text)
        l.setStyleSheet('color: #9aa3b2; font-weight: 700; letter-spacing: 1.4px; font-size: 11px;')
        return l

    def _fill_processes(self):
        self.process_combo.blockSignals(True)
        self.process_combo.clear()
        for p in self._processes:
            self.process_combo.addItem(p.name, p.id)
        self.process_combo.blockSignals(False)

    def _item_by_id(self, item_id):
        for it in self._items:
            if it.id == item_id:
                return it
        return None

    def _add_row(self, kind, name='', qty=1.0, prob=None):
        row = _RecipeRow(self.content, kind, self._items, name=name, qty=qty, prob=prob)
        row.remove_requested.connect(lambda: self._remove_row(row, kind))
        parent_layout = self.inputs_layout if kind == 'input' else self.outputs_layout
        parent_layout.addWidget(row)

    def _remove_row(self, row, kind):
        parent_layout = self.inputs_layout if kind == 'input' else self.outputs_layout
        parent_layout.removeWidget(row)
        row.deleteLater()

    def _open_process_dialog(self):
        from .dialogs_items import ProcessDialog

        dialog = ProcessDialog(self, self.db, self.project_id, None, is_edit=False)
        if dialog.exec() and getattr(dialog, 'created_id', None):
            # refresh process list and select the new process
            self._processes = self.db.list_processes(self.project_id)
            self._fill_processes()
            new_id = dialog.created_id
            new_name = next((p.name for p in self._processes if p.id == new_id), None)
            if new_name:
                self.process_combo.setCurrentText(new_name)
            self.new_process_created.emit(new_id)

    def _save(self):
        proc_name = self.process_combo.currentText().strip()
        proc = None
        for p in self._processes:
            if p.name.lower() == proc_name.lower():
                proc = p
                break
        if proc is None:
            QMessageBox.warning(self, 'Invalid recipe', 'Select a valid processing method (create one first if needed).')
            return

        inputs = []
        outputs = []
        seen_in = set()
        seen_out = set()

        # inputs
        for i in range(self.inputs_layout.count()):
            w = self.inputs_layout.itemAt(i).widget()
            if w is None:
                continue
            data = w.data()
            item = _resolve_item(data['name'], self._items)
            if item is None:
                QMessageBox.warning(self, 'Invalid recipe',
                                    f'Unknown input item: "{data["name"]}". Add it to the database first.'
                                    if data['name'] else 'Every input needs an item.')
                return
            if item.id in seen_in:
                QMessageBox.warning(self, 'Invalid recipe', f'Duplicate input item: "{item.name}". Merge quantities instead.')
                return
            seen_in.add(item.id)
            inputs.append((item.id, data['qty']))

        # outputs
        for i in range(self.outputs_layout.count()):
            w = self.outputs_layout.itemAt(i).widget()
            if w is None:
                continue
            data = w.data()
            item = _resolve_item(data['name'], self._items)
            if item is None:
                QMessageBox.warning(self, 'Invalid recipe',
                                    f'Unknown output item: "{data["name"]}". Add it to the database first.'
                                    if data['name'] else 'Every output needs an item.')
                return
            if item.id in seen_out:
                QMessageBox.warning(self, 'Invalid recipe', f'Duplicate output item: "{item.name}". Merge quantities instead.')
                return
            seen_out.add(item.id)
            outputs.append((item.id, data['qty'], data['prob'] if data['prob'] is not None else 1.0))

        if not inputs:
            QMessageBox.warning(self, 'Invalid recipe', 'A recipe needs at least one input.')
            return
        if not outputs:
            QMessageBox.warning(self, 'Invalid recipe', 'A recipe needs at least one output.')
            return

        name = self.name_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()
        try:
            if self.is_edit:
                self.db.update_recipe(self.recipe.id, name=name, notes=notes,
                                       process_id=proc.id, inputs=inputs, outputs=outputs)
            else:
                self.created_id = self.db.create_recipe(self.project_id, proc.id, name, notes, inputs, outputs)
        except Exception as e:
            QMessageBox.warning(self, 'Save failed', str(e))
            return
        self.accept()

    def _delete(self):
        from PySide6.QtWidgets import QMessageBox
        answer = QMessageBox.question(
            self, 'Delete recipe',
            'Delete this recipe?\n\nThis cannot be undone.')
        if answer != QMessageBox.Yes:
            return
        self.db.delete_recipe(self.recipe.id)
        self.accept()
