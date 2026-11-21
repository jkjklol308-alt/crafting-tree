"""Production calculator dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QTabWidget, QTextEdit, QWidget, QFrame, QMessageBox, QGroupBox, QTreeWidget,
    QTreeWidgetItem, QRadioButton, QCheckBox, QScrollArea, QGridLayout, QSizePolicy,
    QHeaderView, QGraphicsView,
)

from . import calculator as calc_mod
from .calculator import TargetSpec, calculate
from .models import Item, ProcessMethod, Recipe
from .util import format_qty
from .theme import PALETTE
from .graph import CalcScene, GraphView


class CalculatorDialog(QDialog):
    def __init__(self, parent, project_id, items, processes, recipes, on_recipe_changed=None):
        super().__init__(parent)
        self.project_id = project_id
        self.items = items
        self.processes = processes
        self.recipes = list(recipes)
        self.on_recipe_changed = on_recipe_changed
        self.result = None

        self.setWindowTitle('Production calculator')
        self.setModal(True)
        self.resize(1050, 800)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ---- targets section ------------------------------------------
        targets_group = QGroupBox('Targets')
        t_layout = QVBoxLayout(targets_group)

        self.targets_table = QTableWidget(0, 3)
        self.targets_table.setHorizontalHeaderLabels(['Item', 'Quantity', 'Recipe (auto = smart pick)'])
        header = self.targets_table.horizontalHeader()
        header.setStretchLastSection(True)
        self.targets_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.targets_table.verticalHeader().setVisible(False)
        self.targets_table.setMaximumHeight(200)
        self.targets_table.horizontalHeader().setStretchLastSection(True)
        t_layout.addWidget(self.targets_table)

        target_btn_row = QHBoxLayout()
        add_btn = QPushButton('+ Add target')
        add_btn.setObjectName('primaryBtn')
        add_btn.clicked.connect(self._add_target)
        remove_btn = QPushButton('− Remove selected')
        remove_btn.setObjectName('ghostBtn')
        remove_btn.clicked.connect(self._remove_target)
        target_btn_row.addWidget(add_btn)
        target_btn_row.addWidget(remove_btn)
        target_btn_row.addStretch()
        t_layout.addLayout(target_btn_row)

        root.addWidget(targets_group)

        # ---- mode section ----------------------------------------------
        mode_group = QGroupBox('Calculation mode')
        mode_layout = QHBoxLayout(mode_group)
        self.expected_radio = QRadioButton('Expected output')
        self.expected_radio.setChecked(True)
        self.guaranteed_radio = QRadioButton('Guaranteed output')
        self.confidence_radio = QRadioButton('Custom confidence')
        conf_row = QHBoxLayout()
        conf_row.addWidget(self.confidence_radio)
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(1, 99)
        self.confidence_spin.setValue(95)
        self.confidence_spin.setSuffix('%')
        conf_row.addWidget(self.confidence_spin)
        mode_layout.addWidget(self.expected_radio)
        mode_layout.addWidget(self.guaranteed_radio)
        mode_layout.addLayout(conf_row)
        mode_layout.addStretch()
        root.addWidget(mode_group)

        # ---- calculate button --------------------------------------------
        action_row = QHBoxLayout()
        self.calc_btn = QPushButton('Calculate')
        self.calc_btn.setObjectName('primaryBtn')
        self.calc_btn.setMinimumWidth(140)
        self.calc_btn.setIcon(None)
        self.calc_btn.clicked.connect(self._calculate)
        action_row.addWidget(self.calc_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        # ---- results tabs ------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_summary_tab(), 'Summary')
        self.tabs.addTab(self._build_tree_tab(), 'Chain tree')
        self._graph_tab, self._calc_scene, self._calc_view = self._build_graph_tab()
        self.tabs.addTab(self._graph_tab, 'Production chain')
        self.tabs.setMinimumHeight(0)
        root.addWidget(self.tabs, 1)

    # ---------------- targets table ----------------
    def _add_target(self):
        if not self.items:
            QMessageBox.information(self, 'No items', 'Create items first, then add them as targets.')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Add production target')
        dialog.setModal(True)
        dialog.resize(420, 160)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        label = QLabel('Choose an item to produce:')
        layout.addWidget(label)
        combo = QComboBox()
        combo.setEditable(True)
        for it in self.items:
            combo.addItem(it.name, it.id)
        layout.addWidget(combo)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(dialog.reject)
        add = QPushButton('Add')
        add.setObjectName('primaryBtn')
        btn_row.addWidget(cancel)
        btn_row.addWidget(add)
        layout.addLayout(btn_row)
        add.clicked.connect(lambda: self._confirm_target(dialog, combo))
        if dialog.exec() == QDialog.Accepted:
            selected = getattr(dialog, '_selected_item', None)
            if selected is not None:
                self._add_target_row(selected.id, 1.0)
                self._refresh_targets_table()

    def _confirm_target(self, dialog, combo):
        name = combo.currentText().strip()
        item = next((it for it in self.items if it.name.lower() == name.lower()), None)
        if item is None:
            QMessageBox.warning(self, 'Unknown item', f'No item named "{name}".')
            return
        dialog._selected_item = item
        dialog.accept()

    def _resolve_item_row(self, combo):
        if combo is None:
            return None
        text = combo.currentText().strip()
        if not text:
            return None
        key = text.lower()
        for it in self.items:
            if it.name.lower() == key:
                return it.id
        return None

    def _target_table_rows(self):
        rows = []
        for i in range(self.targets_table.rowCount()):
            combo = self.targets_table.cellWidget(i, 0)
            qty = self.targets_table.cellWidget(i, 1)
            recipe = self.targets_table.cellWidget(i, 2)
            if combo is None or qty is None:
                continue
            item_id = self._resolve_item_row(combo)
            if item_id is None:
                continue
            recipe_id = None if recipe is None or recipe.currentIndex() == 0 else recipe.itemData(recipe.currentIndex())
            rows.append({'item_id': item_id, 'qty': float(qty.value()), 'recipe_id': recipe_id})
        return rows

    def _refresh_targets_table(self):
        existing = self._target_table_rows()
        self.targets_table.blockSignals(True)
        self.targets_table.setRowCount(0)
        for r in existing:
            self._add_target_row(r['item_id'], r['qty'], r['recipe_id'])
        self.targets_table.blockSignals(False)

    def _add_target_row(self, item_id, qty=1.0, recipe_id=None):
        row = self.targets_table.rowCount()
        self.targets_table.insertRow(row)
        self.targets_table.setRowHeight(row, 40)

        # item picker
        combo = QComboBox()
        combo.setEditable(True)
        for it in self.items:
            combo.addItem(it.name, it.id)
        for i in range(combo.count()):
            if combo.itemData(i) == item_id:
                combo.setCurrentIndex(i)
                break
        self.targets_table.setCellWidget(row, 0, combo)

        # qty
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.01, 999999)
        qty_spin.setDecimals(2)
        qty_spin.setValue(qty if qty else 1.0)
        self.targets_table.setCellWidget(row, 1, qty_spin)

        # recipe picker
        recipe_combo = QComboBox()
        candidates = [r for r in self.recipes if any(o.item_id == item_id for o in r.outputs)]
        recipe_combo.addItem('Auto', None)
        for r in candidates:
            proc = next((p for p in self.processes if p.id == r.process_id), None)
            proc_name = proc.name if proc else '?'
            recipe_combo.addItem(r.name or proc_name, r.id)
        for i in range(recipe_combo.count()):
            if recipe_combo.itemData(i) == recipe_id:
                recipe_combo.setCurrentIndex(i)
                break
        self.targets_table.setCellWidget(row, 2, recipe_combo)

        combo.currentIndexChanged.connect(lambda idx, r=row: self._update_recipe_combo(r))

    def _update_recipe_combo(self, row):
        combo = self.targets_table.cellWidget(row, 0)
        if combo is None:
            return
        item_id = self._resolve_item_row(combo)
        current = self.targets_table.cellWidget(row, 2)
        recipe_id = None
        if current is not None and current.currentIndex() > 0:
            recipe_id = current.itemData(current.currentIndex())
        recipe_combo = QComboBox()
        candidates = [r for r in self.recipes if any(o.item_id == item_id for o in r.outputs)]
        recipe_combo.addItem('Auto', None)
        for r in candidates:
            proc = next((p for p in self.processes if p.id == r.process_id), None)
            proc_name = proc.name if proc else '?'
            recipe_combo.addItem(r.name or proc_name, r.id)
        for i in range(recipe_combo.count()):
            if recipe_combo.itemData(i) == recipe_id:
                recipe_combo.setCurrentIndex(i)
                break
        self.targets_table.setCellWidget(row, 2, recipe_combo)

    def _remove_target(self):
        idx = self.targets_table.currentRow()
        if idx >= 0:
            self.targets_table.removeRow(idx)
        elif self.targets_table.rowCount() > 0:
            self.targets_table.removeRow(self.targets_table.rowCount() - 1)

    # ---------------- calculation ----------------
    def _mode(self):
        if self.guaranteed_radio.isChecked():
            return 'guaranteed'
        if self.confidence_radio.isChecked():
            return 'confidence'
        return 'expected'

    def _confidence(self):
        return self.confidence_spin.value() / 100.0

    def _calculate(self):
        rows = self._target_table_rows()
        rows = [r for r in rows if r['item_id'] is not None and r['qty'] > 0]
        if not rows:
            QMessageBox.warning(self, 'No targets', 'Add at least one target with a quantity first.')
            return
        targets = [TargetSpec(item_id=r['item_id'], quantity=r['qty'], recipe_id=r['recipe_id']) for r in rows]
        result = calculate(
            self._items_dict(), self._processes_dict(), self.recipes,
            targets, mode=self._mode(), confidence=self._confidence())
        self.result = result
        self._render_summary()
        self._render_tree()
        self._refresh_graph()

    def _items_dict(self):
        return {it.id: it for it in self.items}

    def _processes_dict(self):
        return {p.id: p for p in self.processes}

    # ---------------- summary tab ----------------
    def _build_summary_tab(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.summary_scroll = scroll
        self.summary_content = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_content)
        self.summary_layout.setContentsMargins(10, 10, 10, 10)
        self.summary_layout.setSpacing(8)
        self.summary_layout.addStretch()
        scroll.setWidget(self.summary_content)
        outer.addWidget(scroll)
        return w

    def _render_summary(self):
        layout = self.summary_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        result = self.result
        if not result:
            layout.insertWidget(0, self._info_label('Enter targets and press Calculate.'))
            return

        items_by_id = self._items_dict()
        processes_by_id = self._processes_dict()

        # targets summary
        targets_box = self._card('TARGETS')
        targets_layout = targets_box[1]
        for item_id, qty in result.targets.items():
            item = items_by_id.get(item_id)
            exp = result.produced_expected.get(item_id, 0.0)
            guar = result.produced_guaranteed.get(item_id, 0.0)
            name = item.name if item else '?'
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(12)
            row_layout.addWidget(QLabel(f'◆ {name}'))
            row_layout.addWidget(QLabel(f'×{format_qty(qty)}'))
            row_layout.addStretch()
            row_layout.addWidget(QLabel(f'expected ~{format_qty(exp)}'))
            row_layout.addWidget(QLabel(f'guaranteed {format_qty(guar)}'))
            targets_layout.addWidget(row)
        self.summary_layout.addWidget(targets_box[0])

        # raw materials
        raw_box = self._card('RAW MATERIALS REQUIRED')
        raw_layout = raw_box[1]
        raw_entries = [(iid, qty) for iid, qty in result.inputs_demand.items() if qty > 0]
        if not raw_entries:
            raw_layout.addWidget(QLabel('No raw materials (network already raw-free).'))
        for iid, qty in raw_entries:
            item = items_by_id.get(iid)
            name = item.name if item else '?'
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 4, 10, 4)
            row_layout.addWidget(QLabel(name))
            row_layout.addStretch()
            row_layout.addWidget(QLabel(f'×{format_qty(qty)}'))
            raw_layout.addWidget(row)
        self.summary_layout.addWidget(raw_box[0])

        # processing operations
        ops_box = self._card('PROCESSING OPERATIONS')
        ops_layout = ops_box[1]
        for pid, runs in result.operation_counts.items():
            proc = processes_by_id.get(pid)
            name = proc.name if proc else '?'
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 4, 10, 4)
            row_layout.addWidget(QLabel(name))
            row_layout.addStretch()
            row_layout.addWidget(QLabel(f'runs needed: {runs}'))
            ops_layout.addWidget(row)
        self.summary_layout.addWidget(ops_box[0])

        # byproducts
        byp_box = self._card('BYPRODUCTS PRODUCED')
        byp_layout = byp_box[1]
        any_byp = False
        for iid, qty in result.byproducts_expected.items():
            if qty <= 0:
                continue
            item = items_by_id.get(iid)
            any_byp = True
            guar = result.byproducts_guaranteed.get(iid, 0.0)
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 4, 10, 4)
            row_layout.addWidget(QLabel(item.name if item else '?'))
            row_layout.addStretch()
            row_layout.addWidget(QLabel(f'~{format_qty(qty)}'))
            row_layout.addWidget(QLabel(f'guaranteed {format_qty(guar)}'))
            byp_layout.addWidget(row)
        if not any_byp:
            byp_layout.addWidget(QLabel('No byproducts produced in this plan.'))
        self.summary_layout.addWidget(byp_box[0])

        # surplus
        surplus_box = self._card('SURPLUS MATERIALS (expected)')
        surplus_layout = surplus_box[1]
        surplus_entries = [(iid, qty) for iid, qty in result.surplus_expected.items() if qty > 0]
        if not surplus_entries:
            surplus_layout.addWidget(QLabel('No surplus materials.'))
        for iid, qty in surplus_entries:
            item = items_by_id.get(iid)
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 4, 10, 4)
            row_layout.addWidget(QLabel(item.name if item else '?'))
            row_layout.addStretch()
            row_layout.addWidget(QLabel(f'~{format_qty(qty)}'))
            surplus_layout.addWidget(row)
        self.summary_layout.addWidget(surplus_box[0])

        # warnings
        warnings_box = self._card('WARNINGS')
        warn_layout = warnings_box[1]
        any_warn = False
        if result.missing:
            names = [items_by_id[i].name for i in result.missing if i in items_by_id]
            warn_layout.addWidget(QLabel('⚠ Missing recipe: ' + ', '.join(names)))
            any_warn = True
        for unr in result.unreliable:
            item = items_by_id.get(unr.item_id)
            name = item.name if item else '?'
            warn_layout.addWidget(QLabel(f'⚠ Cannot guarantee {name}: {unr.reason}'))
            any_warn = True
        if result.cycles:
            names = ' → '.join(str(items_by_id.get(i).name) if items_by_id.get(i) else '?' for i in result.cycles[0].items)
            warn_layout.addWidget(QLabel(f'⚠ Production cycle detected: {names}'))
            any_warn = True
        if not result.converged:
            warn_layout.addWidget(QLabel('⚠ Calculation did not fully converge (a cycle may be involved).'))
            any_warn = True
        if not any_warn:
            warn_layout.addWidget(QLabel('✓ No warnings.'))
        self.summary_layout.addWidget(warnings_box[0])


    def _card(self, title):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(4)
        return box, layout

    def _info_label(self, text):
        label = QLabel(text)
        label.setStyleSheet('color: #8a93a1; font-size: 13px; padding: 10px;')
        return label

    # ---------------- tree tab ----------------
    def _build_tree_tab(self):
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        return self._tree

    def _render_tree(self):
        tree = self._tree
        tree.clear()
        result = self.result
        if not result:
            return
        items_by_id = self._items_dict()
        processes_by_id = self._processes_dict()
        recipes_by_id = {r.id: r for r in self.recipes}

        targets_node = QTreeWidgetItem()
        targets_node.setText(0, 'Target production')
        targets_node.setForeground(0, QColor('#ffd28a'))
        tree.addTopLevelItem(targets_node)
        targets_node.setExpanded(True)

        for item_id, qty in result.targets.items():
            item = items_by_id.get(item_id)
            node = QTreeWidgetItem()
            node.setText(0, f'{item.name if item else "?"}  —  ×{format_qty(qty)}')
            node.setForeground(0, QColor('#eef1f6'))
            targets_node.addChild(node)
            exp = result.produced_expected.get(item_id, 0.0)
            guar = result.produced_guaranteed.get(item_id, 0.0)
            info_node = QTreeWidgetItem()
            info_node.setText(0, f'expected ~{format_qty(exp)}   ·   guaranteed {format_qty(guar)}')
            info_node.setForeground(0, QColor('#8a93a1'))
            node.addChild(info_node)

            if item_id in result.missing:
                missing_node = QTreeWidgetItem()
                missing_node.setText(0, 'NO RECIPE produces this item.')
                missing_node.setForeground(0, QColor('#ff8a7a'))
                node.addChild(missing_node)
                continue

            # find the recipe used for this target
            choices = {}
            r = None
            for rid, runs in result.recipe_runs.items():
                candidate = recipes_by_id.get(rid)
                if candidate and any(o.item_id == item_id for o in candidate.outputs):
                    r = candidate
                    break
            if r is None:
                continue
            proc = processes_by_id.get(r.process_id)
            proc_name = proc.name if proc else '?'
            runs = result.recipe_runs.get(r.id, 0)
            recipe_node = QTreeWidgetItem()
            recipe_node.setText(0, f'{proc_name}  —  {runs} runs')
            recipe_node.setForeground(0, QColor('#d3b3ec'))
            recipe_node.setExpanded(True)
            node.addChild(recipe_node)
            # inputs / outputs
            for inp in r.inputs:
                inp_node = QTreeWidgetItem()
                itm = items_by_id.get(inp.item_id)
                inp_node.setText(0, f'input: {itm.name if itm else "?"}  ×{format_qty(inp.quantity * runs)}')
                inp_node.setForeground(0, QColor('#aab2c2'))
                recipe_node.addChild(inp_node)
            for out in r.outputs:
                if out.item_id == item_id:
                    continue
                out_node = QTreeWidgetItem()
                itm = items_by_id.get(out.item_id)
                exp_qty = out.quantity * out.probability * runs
                out_node.setText(0, f'byproduct: {itm.name if itm else "?"}  ~{format_qty(exp_qty)}' + (f' ({out.probability * 100:.0f}%)' if out.probability < 1 else ''))
                out_node.setForeground(0, QColor('#d3b3ec'))
                recipe_node.addChild(out_node)

        self._tree.expandAll()

    # ---------------- graph tab ----------------
    def _build_graph_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        scene = CalcScene()
        view = GraphView(scene)
        view.setDragMode(QGraphicsView.ScrollHandDrag)
        layout.addWidget(view)
        return tab, scene, view

    def _refresh_graph(self):
        result = self.result
        items = self.items
        procs = self.processes
        recipes = self.recipes
        positions = None
        from .layout import compute_positions
        positions = compute_positions(self._items_dict(), self._processes_dict(), recipes)
        self._calc_scene.set_calc(result, recipes, self._items_dict(), self._processes_dict(), positions)
        self._calc_view.fit_to_view()

    # ---------------- helpers ----------------
    @staticmethod
    def _make_label(text, color='#aab2c2', size=12):
        l = QLabel(text)
        l.setStyleSheet(f'color: {color}; font-size: {size}px;')
        return l


