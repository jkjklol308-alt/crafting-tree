"""Main application window."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QToolButton, QStatusBar, QMessageBox, QMenu, QFrame, QCheckBox, QLineEdit, QGroupBox,
)

from . import util
from .db import Database
from .models import Item
from .graph import GraphScene, GraphView
from .sidebar import SideBar
from .info_panel import InfoPanel
from .dialogs_items import ItemDialog, ProcessDialog
from .dialogs_recipe import RecipeDialog
from .dialogs_meta import ProjectManagerDialog, ImportExportDialog, SettingsDialog
from .calculator_ui import CalculatorDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Crafting Tree — Create Mod Factory Manager')
        self.setMinimumSize(1150, 720)
        self.resize(1520, 920)

        self.db = Database(util.database_path())
        project_id = self.db.current_project_id()
        if project_id is None:
            project_id = self.db.create_project('My Factory')
            self.db.set_current_project(project_id)
        self.project_id = project_id
        self.selected = None          # (kind, id)
        self._classification = {}

        self._build_ui()
        self._reload_all()
        self.update_window_title()

    # ============================================================ UI
    def _build_ui(self):
        # ---------- top bar ----------
        # Owned by the central layout added at the bottom of _build_ui
        # (a local QWidget would be destroyed as soon as this method returns,
        #  taking every button with it).
        self.topbar = QWidget()
        self.topbar.setObjectName('topbar')
        self.topbar.setStyleSheet('''
            QWidget {{ background: #1d2128; border-bottom: 1px solid #2b313c; }}
        ''')
        top_layout = QHBoxLayout(self.topbar)
        top_layout.setContentsMargins(14, 9, 14, 9)
        top_layout.setSpacing(10)

        logo = QLabel('⛏  Crafting Tree')
        logo.setStyleSheet('font-size: 17px; font-weight: 800; color: #ffb454;')
        top_layout.addWidget(logo)

        top_layout.addWidget(self._separator())

        self.project_button = QPushButton()
        self.project_button.setObjectName('ghostBtn')
        self.project_button.clicked.connect(self._show_project_manager)
        top_layout.addWidget(self.project_button)

        top_layout.addWidget(self._separator())

        self.item_button = QPushButton('+ Item')
        self.item_button.setObjectName('ghostBtn')
        self.item_button.clicked.connect(self._new_item)
        top_layout.addWidget(self.item_button)

        self.recipe_button = QPushButton('+ Recipe')
        self.recipe_button.setObjectName('ghostBtn')
        self.recipe_button.clicked.connect(self._new_recipe)
        top_layout.addWidget(self.recipe_button)

        self.process_button = QPushButton('+ Process')
        self.process_button.setObjectName('ghostBtn')
        self.process_button.clicked.connect(self._new_process)
        top_layout.addWidget(self.process_button)

        self.calculator_button = QPushButton('⚗  Calculator')
        self.calculator_button.setObjectName('primaryBtn')
        self.calculator_button.clicked.connect(self._open_calculator)
        top_layout.addWidget(self.calculator_button)

        top_layout.addStretch()

        self.import_export_button = QPushButton('Import / Export')
        self.import_export_button.setObjectName('ghostBtn')
        self.import_export_button.clicked.connect(self._open_import_export)
        top_layout.addWidget(self.import_export_button)

        self.settings_button = QPushButton('⚙ Settings')
        self.settings_button.setObjectName('ghostBtn')
        self.settings_button.clicked.connect(self._open_settings)
        top_layout.addWidget(self.settings_button)

        # ---------- center panel ----------
        self.graph_scene = GraphScene(self)
        self.graph_view = GraphView(self.graph_scene)
        self.graph_view.setMinimumSize(600, 400)

        self.graph_scene.node_clicked.connect(self._on_graph_node_clicked)
        self.graph_scene.node_double_clicked.connect(self._on_graph_node_dblclicked)
        self.graph_scene.node_moved.connect(self._on_node_moved)

        # filter toolbar
        filter_bar = QWidget()
        filter_bar.setStyleSheet('background: #1b1f26; border-bottom: 1px solid #262b33;')
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 6, 12, 6)
        filter_layout.setSpacing(6)

        filter_label = QLabel('Filter:')
        filter_label.setStyleSheet('color: #7c8594; font-size: 11px; font-weight: 700; letter-spacing: 1px;')
        filter_layout.addWidget(filter_label)

        self.filter_buttons = {}
        for mode, label in (('all', 'All'), ('direct', 'Direct'), ('upstream', 'Upstream'),
                             ('downstream', 'Downstream'), ('chain', 'Chain')):
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setObjectName('filterBtn')
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda checked, m=mode: self._set_filter(m))
            self.filter_buttons[mode] = btn
            filter_layout.addWidget(btn)
        self.filter_buttons['all'].setChecked(True)

        self.byproducts_check = QCheckBox('Byproducts')
        self.byproducts_check.setChecked(True)
        self.byproducts_check.stateChanged.connect(self._byproducts_toggled)
        filter_layout.addSpacing(14)
        filter_layout.addWidget(self.byproducts_check)

        filter_layout.addStretch()

        zoom_in_btn = self._icon_button('＋', 'Zoom in')
        zoom_in_btn.clicked.connect(lambda: self.graph_view.zoom_in())
        zoom_out_btn = self._icon_button('－', 'Zoom out')
        zoom_out_btn.clicked.connect(lambda: self.graph_view.zoom_out())
        reset_btn = self._icon_button('⟲', 'Reset view')
        reset_btn.clicked.connect(lambda: self.graph_view.reset_view())
        fit_btn = self._icon_button('⤢', 'Fit graph to view')
        fit_btn.clicked.connect(lambda: self.graph_view.fit_to_view())
        for b in (zoom_in_btn, zoom_out_btn, reset_btn, fit_btn):
            filter_layout.addWidget(b)

        arrange_btn = QPushButton('Auto-arrange')
        arrange_btn.setObjectName('ghostBtn')
        arrange_btn.clicked.connect(lambda: self.graph_scene.auto_arrange())
        filter_layout.addWidget(arrange_btn)

        # legend bar
        legend = QWidget()
        legend.setStyleSheet('background: #1b1f26; border-top: 1px solid #262b33;')
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(12, 5, 12, 5)
        legend_layout.setSpacing(14)
        legend_layout.addWidget(self._legend_dot('#d98a4b', 'Raw material'))
        legend_layout.addWidget(self._legend_dot('#4ea3c8', 'Intermediate'))
        legend_layout.addWidget(self._legend_dot('#58bd7e', 'Final product'))
        legend_layout.addWidget(self._legend_process('#a06bd8', 'Process'))
        legend_layout.addWidget(QLabel('· dashed edges = probabilistic byproducts'))
        legend_layout.addStretch()

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(filter_bar)
        center_layout.addWidget(self.graph_view, 1)
        center_layout.addWidget(legend)

        # ---------- sidebars ----------
        self.sidebar = SideBar()
        self.sidebar.item_selected.connect(lambda iid: self.select_node(('item', iid), center=True))
        self.sidebar.item_double_clicked.connect(self._edit_item_by_id)
        # Items dragged in from the sidebar are placed in the graph.
        self.graph_view.item_dropped.connect(self._on_item_dropped)

        self.info_panel = InfoPanel()
        self.info_panel.navigate_item.connect(lambda iid: self.select_node(('item', iid), center=True))
        self.info_panel.navigate_process.connect(lambda pid: self.select_node(('process', pid), center=True))
        self.info_panel.edit_item.connect(self._edit_item_by_id)
        self.info_panel.edit_process.connect(self._edit_process_by_id)
        self.info_panel.delete_item.connect(self._delete_item_by_id)
        self.info_panel.delete_process.connect(self._delete_process_by_id)

        # ---------- splitter ----------
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(center_panel)
        splitter.addWidget(self.info_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([270, 900, 340])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(2, True)

        # ---------- central widget ----------
        # A plain topbar followed by a splitter need a container in between;
        # the topbar is otherwise parentless and destroyed on return.
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.topbar)
        central_layout.addWidget(splitter, 1)
        self.central_widget = central
        self.setCentralWidget(central)

        # ---------- status bar ----------
        self.status_bar = QStatusBar()
        self.status_label = QLabel('')
        self.status_bar.addWidget(self.status_label)
        right_label = QLabel('Saved locally in SQLite')
        self.status_bar.addPermanentWidget(right_label)
        self.setStatusBar(self.status_bar)

        self.setGeometry(80, 60, 1520, 920)

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet('color: #2b313c; background: #2b313c; border: 0;')
        return line

    def _icon_button(self, text, tooltip):
        btn = QPushButton(text)
        btn.setObjectName('iconBtn')
        btn.setToolTip(tooltip)
        btn.setFixedSize(38, 34)
        btn.setStyleSheet('''
            QPushButton { font-size: 16px; padding: 0; }
        ''')
        return btn

    def _legend_dot(self, color, text):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(5)
        dot = QLabel()
        dot.setFixedSize(11, 11)
        dot.setStyleSheet(f'background: {color}; border-radius: 5px;')
        t = QLabel(text)
        t.setStyleSheet('color: #7c8594; font-size: 11px;')
        l.addWidget(dot)
        l.addWidget(t)
        return w

    def _legend_process(self, color, text):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(5)
        dot = QLabel('◆')
        dot.setStyleSheet(f'color: {color}; font-size: 11px;')
        t = QLabel(text)
        t.setStyleSheet('color: #7c8594; font-size: 11px;')
        l.addWidget(dot)
        l.addWidget(t)
        return w

    # ============================================================ data
    def _classification_for(self, items, recipes):
        classification = {}
        for item in items:
            upstream = 0
            downstream = 0
            for r in recipes:
                if any(o.item_id == item.id for o in r.outputs):
                    upstream += 1
                if any(i.item_id == item.id for i in r.inputs):
                    downstream += 1
            classification[item.id] = item.classification(downstream, upstream)
        return classification

    def _reload_all(self):
        project = self.db.get_project(self.project_id)
        name = project['name'] if project else '—'
        self.project_button.setText(f'▤  {name}')

        self.items = self.db.list_items(self.project_id)
        self.processes = self.db.list_processes(self.project_id)
        self.recipes = self.db.list_recipes(self.project_id)
        positions = self.db.get_positions(self.project_id)
        self._classification = self._classification_for(self.items, self.recipes)

        # keep focus consistent before rebuilding
        if self.selected:
            self.graph_scene.focus_kind, self.graph_scene.focus_id = self.selected
        else:
            self.graph_scene.focus_kind = None
            self.graph_scene.focus_id = None
        self.sidebar.set_data(self.items, self._classification)
        self.graph_scene.set_model(self.items, self.processes, self.recipes, positions,
                                    self._classification)
        if self.selected:
            self.graph_scene.set_selected(self.selected)
        self._refresh_info()
        self._update_status()
        self.update_window_title()

    def _update_status(self):
        self.status_label.setText(
            f'  {len(self.items)} items    ·    {len(self.processes)} processes    ·    '
            f'{len(self.recipes)} recipes')

    def update_window_title(self):
        self.setWindowTitle('Crafting Tree — Create Mod Factory Manager')

    # ============================================================ selection
    def select_node(self, key, center=False):
        self.selected = key
        self.graph_scene.set_selected(key)
        kind, nid = key
        if kind == 'item':
            self.sidebar.select_item(nid)
        if center:
            self.graph_view.center_on(key)
        # update filter button feedback
        self._refresh_filter_buttons()
        self._refresh_info()

    def _refresh_filter_buttons(self):
        if self.graph_scene.filter_mode == 'all':
            if self.filter_buttons['all'].isChecked():
                return
            self.filter_buttons['all'].setChecked(True)
        else:
            self.filter_buttons['all'].setChecked(False)
            for mode, btn in self.filter_buttons.items():
                if mode != 'all':
                    btn.setChecked(mode == self.graph_scene.filter_mode)
        # disable focused modes when nothing selected
        has_focus = self.selected is not None
        for mode, btn in self.filter_buttons.items():
            if mode != 'all':
                btn.setEnabled(has_focus)

    # ============================================================ info panel
    def _refresh_info(self):
        key = self.selected
        items_by_id = {i.id: i for i in self.items}
        processes_by_id = {p.id: p for p in self.processes}
        if key is None:
            self.info_panel.set_empty()
            return
        kind, nid = key
        if kind == 'item':
            item = items_by_id.get(nid)
            if item is None:
                self.info_panel.set_empty()
                return
            cls = self._classification.get(nid, 'raw')
            produced_by = self.db.recipes_producing_item(self.project_id, nid)
            can_produce = self.db.recipes_consuming_item(self.project_id, nid)
            self.info_panel.show_item(item, items_by_id, processes_by_id, cls, produced_by, can_produce)
        elif kind == 'process':
            proc = processes_by_id.get(nid)
            if proc is None:
                self.info_panel.set_empty()
                return
            recipes = self.db.recipes_using_process(self.project_id, nid)
            self.info_panel.show_process(proc, recipes, items_by_id, processes_by_id)

    # ============================================================ graph events
    def _on_graph_node_clicked(self, key):
        self.select_node(key, center=False)

    def _on_graph_node_dblclicked(self, key):
        kind, nid = key
        if kind == 'item':
            self._edit_item_by_id(nid)
        elif kind == 'process':
            self._edit_process_by_id(nid)

    def _on_node_moved(self, kind, nid, x, y):
        # called while dragging (also from auto-arrange)
        self.db.set_position(self.project_id, kind, nid, x, y)

    def _on_item_dropped(self, ids_text, x, y):
        # Items dropped from the sidebar: persist positions (clustered so
        # several dropped together don't stack) and rebuild the graph.
        ids = util.parse_mime_item_ids(ids_text)
        if not ids:
            return
        # Keep focus consistent with the newly selected item before rebuild.
        self.selected = ('item', ids[-1])
        self.graph_scene.focus_kind, self.graph_scene.focus_id = self.selected
        for i, nid in enumerate(ids):
            self.db.set_position(self.project_id, 'item', nid,
                                 x + (i % 3) * 150, y + (i // 3) * 120)
        self._reload_all()
        self.select_node(('item', ids[-1]), center=False)

    def _set_filter(self, mode):
        self.graph_scene.filter_mode = mode
        if self.selected and mode != 'all':
            self.graph_scene.focus_kind, self.graph_scene.focus_id = self.selected
        else:
            self.graph_scene.focus_kind = None
            self.graph_scene.focus_id = None
        self.graph_scene.rebuild()
        self._refresh_filter_buttons()

    def _byproducts_toggled(self, state):
        self.graph_scene.byproducts = state == Qt.Checked
        self.graph_scene.rebuild()

    # ============================================================ handlers
    def _new_item(self):
        dlg = ItemDialog(self, self.db, self.project_id, None,
                          categories=self.db.categories_for_project(self.project_id), is_edit=False)
        if dlg.exec():
            self._reload_all()
            new_id = getattr(dlg, 'created_id', None)
            if new_id:
                self.select_node(('item', new_id), center=True)

    def _edit_item_by_id(self, item_id):
        item = self.db.get_item(item_id)
        if item is None:
            return
        dlg = ItemDialog(self, self.db, self.project_id, item,
                          categories=self.db.categories_for_project(self.project_id), is_edit=True)
        if dlg.exec():
            self._reload_all()
            if self.selected == ('item', item_id):
                self.select_node(('item', item_id), center=False)

    def _new_process(self):
        dlg = ProcessDialog(self, self.db, self.project_id, None, is_edit=False)
        if dlg.exec():
            self._reload_all()
            new_id = getattr(dlg, 'created_id', None)
            if new_id:
                self.select_node(('process', new_id), center=True)

    def _edit_process_by_id(self, process_id):
        proc = self.db.get_process(process_id)
        if proc is None:
            return
        dlg = ProcessDialog(self, self.db, self.project_id, proc, is_edit=True)
        if dlg.exec():
            self._reload_all()
            if self.selected == ('process', process_id):
                self.select_node(('process', process_id), center=False)

    def _new_recipe(self):
        if not self.processes:
            QMessageBox.information(self, 'Create a processing method first',
                                     'Recipes need a processing method.\n\nCreate one, then create your recipe.')
            return
        dlg = RecipeDialog(self, self.db, self.project_id, None, self.items, self.processes, is_edit=False)
        dlg.new_process_created.connect(lambda pid: self._reload_all())
        if dlg.exec():
            self._reload_all()

    def _edit_recipe_by_id(self, recipe_id):
        recipe = self.db.get_recipe(recipe_id)
        if recipe is None:
            return
        dlg = RecipeDialog(self, self.db, self.project_id, recipe, self.items, self.processes, is_edit=True)
        dlg.new_process_created.connect(lambda pid: self._reload_all())
        if dlg.exec():
            self._reload_all()

    def _edit_recipe_card(self, recipe):
        self._edit_recipe_by_id(recipe.id)

    def _delete_item_by_id(self, item_id):
        item = self.db.get_item(item_id)
        if item is None:
            return
        usage = self.db.count_recipes_using_item(item_id)
        if usage == 0:
            answer = QMessageBox.question(self, 'Delete item',
                                          f'Delete item "{item.name}"?')
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.db.delete_item(item_id)
            if self.selected == ('item', item_id):
                self.selected = None
            self._reload_all()
            return
        # delete with references or block
        answer = QMessageBox.question(
            self, 'Delete item',
            f'"{item.name}" is used in {usage} recipe(s).\n\n'
            'Delete the item AND remove its references (empty recipes will also be deleted)?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_item_with_recipes(self.project_id, item_id)
        if self.selected == ('item', item_id):
            self.selected = None
        self._reload_all()

    def _delete_process_by_id(self, process_id):
        proc = self.db.get_process(process_id)
        if proc is None:
            return
        usage = self.db.count_recipes_using_process(process_id)
        if usage == 0:
            answer = QMessageBox.question(self, 'Delete process',
                                          f'Delete processing method "{proc.name}"?')
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.db.delete_process(process_id)
            if self.selected == ('process', process_id):
                self.selected = None
            self._reload_all()
            return
        answer = QMessageBox.question(
            self, 'Delete process',
            f'"{proc.name}" is used in {usage} recipe(s).\n\n'
            'Delete this process and ALL {usage} recipe(s) using it?'.format(usage=usage),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        # delete dependent recipes first (cascades through recipe_inputs/outputs and graph layout)
        recipes = self.db.recipes_using_process(self.project_id, process_id)
        for r in recipes:
            self.db.delete_recipe(r.id)
        self.db.delete_process(process_id)
        if self.selected == ('process', process_id):
            self.selected = None
        self._reload_all()

    def _open_calculator(self):
        dlg = CalculatorDialog(self, self.project_id, self.items, self.processes, self.recipes)
        dlg.exec()
        # no data changes expected; still reload to be safe
        self._reload_all()

    def _open_import_export(self):
        dlg = ImportExportDialog(self, self.db, self.project_id,
                                 on_imported=self._reload_all)
        dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(self, self.db, self.project_id,
                             on_reset=self._reload_all)
        dlg.exec()

    def _show_project_manager(self):
        dlg = ProjectManagerDialog(self, self.db, self.project_id)
        dlg.project_switched.connect(self._set_project)
        dlg.exec()

    def _set_project(self, pid):
        self.project_id = pid
        self.db.set_current_project(pid)
        self.selected = None
        self.graph_scene.collapsed = set()
        self.graph_scene.focus_kind = None
        self.graph_scene.focus_id = None
        self.graph_scene.filter_mode = 'all'
        self.graph_scene.byproducts = True
        self.byproducts_check.setChecked(True)
        self._reload_all()
        self.graph_view.fit_to_view()
