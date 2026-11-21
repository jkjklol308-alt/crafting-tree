"""Project manager, import/export, and settings dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QWidget,
    QRadioButton, QCheckBox, QGroupBox, QFrame, QTextEdit, QTabWidget, QInputDialog,
)
from PySide6.QtGui import QColor

from . import util
from .db import Database


def _standard_button(text, name=''):
    btn = QPushButton(text)
    btn.setObjectName(name or 'ghostBtn')
    return btn


class ProjectManagerDialog(QDialog):
    project_switched = Signal(int)

    def __init__(self, parent, db: Database, current_project_id: int):
        super().__init__(parent)
        self.db = db
        self.current_project_id = current_project_id
        self.setWindowTitle('Projects')
        self.setModal(True)
        self.resize(520, 520)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        root.addWidget(QLabel('Projects — each project holds its own items, processes and recipes.'))

        self.project_list = QListWidget()
        self.project_list.doubleClicked.connect(self._switch_to_selection)
        root.addWidget(self.project_list, 1)

        new_row = QHBoxLayout()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText('New project name…')
        new_row.addWidget(self.new_name, 1)
        new_btn = QPushButton('New')
        new_btn.setObjectName('primaryBtn')
        new_btn.clicked.connect(self._new_project)
        new_row.addWidget(new_btn)
        root.addLayout(new_row)

        btn_row = QHBoxLayout()
        self.switch_btn = _standard_button('Switch to')
        self.switch_btn.clicked.connect(self._switch_to_selection)
        self.rename_btn = _standard_button('Rename…')
        self.rename_btn.clicked.connect(self._rename_selection)
        self.delete_btn = _standard_button('Delete…', 'dangerBtn')
        self.delete_btn.clicked.connect(self._delete_selection)
        btn_row.addWidget(self.switch_btn)
        btn_row.addWidget(self.rename_btn)
        btn_row.addWidget(self.delete_btn)
        root.addLayout(btn_row)

        self._refresh()

    def _refresh(self, select_id=None):
        self.project_list.clear()
        for p in self.db.list_projects():
            items_n = len(self.db.list_items(p['id']))
            procs_n = len(self.db.list_processes(p['id']))
            recipes_n = len(self.db.list_recipes(p['id']))
            label = f"{p['name']}   ({items_n} items · {procs_n} processes · {recipes_n} recipes)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, p['id'])
            if p['id'] == self.current_project_id:
                item.setForeground(QColor('#ffd28a'))
            self.project_list.addItem(item)
        for i in range(self.project_list.count()):
            if self.project_list.item(i).data(Qt.UserRole) == self.current_project_id:
                self.project_list.setCurrentRow(i)
                break

    def _selection_id(self):
        it = self.project_list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _new_project(self):
        name = self.new_name.text().strip()
        if not name:
            QMessageBox.warning(self, 'New project', 'Enter a project name.')
            return
        try:
            pid = self.db.create_project(name)
        except Exception as e:
            QMessageBox.warning(self, 'New project', str(e))
            return
        self.new_name.setText('')
        self._refresh()
        self.project_list.setCurrentRow(_find_row(self.project_list, pid))

    def _switch_to_selection(self):
        pid = self._selection_id()
        if pid is None:
            return
        self.db.set_current_project(pid)
        self.project_switched.emit(pid)
        self.accept()

    def _rename_selection(self):
        pid = self._selection_id()
        if pid is None:
            return
        current = self.db.get_project(pid)
        new_name, ok = QInputDialog.getText(self, 'Rename project', 'Name:', text=current['name'] if current else '')
        if not ok or not new_name.strip():
            return
        try:
            self.db.rename_project(pid, new_name.strip())
        except Exception as e:
            QMessageBox.warning(self, 'Rename failed', str(e))
            return
        self._refresh()

    def _delete_selection(self):
        pid = self._selection_id()
        if pid is None:
            return
        projects = self.db.list_projects()
        if len(projects) <= 1:
            QMessageBox.warning(self, 'Delete project', 'The last remaining project cannot be deleted.')
            return
        current = self.db.get_project(pid)
        items_n = len(self.db.list_items(pid))
        recipes_n = len(self.db.list_recipes(pid))
        answer = QMessageBox.question(
            self, 'Confirm delete',
            f'Delete project "{current["name"]}" and all of its data?\n\n'
            f'({items_n} items · {recipes_n} recipes)\nThis cannot be undone.')
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_project(pid)
        # images folder removal
        images = util.data_dir() / 'projects' / str(pid)
        if images.exists():
            import shutil
            shutil.rmtree(images, ignore_errors=True)
        # ensure a current project exists
        projects = self.db.list_projects()
        if projects:
            new_pid = projects[0]['id']
            self.db.set_current_project(new_pid)
            self.project_switched.emit(new_pid)
        self._refresh()


def _find_row(list_widget, pid):
    for i in range(list_widget.count()):
        if list_widget.item(i).data(Qt.UserRole) == pid:
            return i
    return 0


class ImportExportDialog(QDialog):
    def __init__(self, parent, db: Database, project_id: int, on_imported=None):
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.on_imported = on_imported
        self.setWindowTitle('Import / Export')
        self.setModal(True)
        self.resize(640, 480)

        root = QVBoxLayout(self)

        tabs = QTabWidget()
        root.addWidget(tabs)

        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        self.export_path = QLineEdit()
        self.export_path.setPlaceholderText('Choose an export file…')
        browse = QPushButton('Browse…')
        browse.clicked.connect(self._browse_export)
        row = QHBoxLayout()
        row.addWidget(self.export_path, 1)
        row.addWidget(browse)
        export_layout.addLayout(row)
        export_layout.addWidget(QLabel('Full JSON export of the current project (items, processes, recipes, images).'))
        export_layout.addStretch()
        export_btn = QPushButton('Export')
        export_btn.setObjectName('primaryBtn')
        export_btn.clicked.connect(self._do_export)
        export_layout.addWidget(export_btn, alignment=Qt.AlignRight)
        tabs.addTab(export_tab, 'Export')

        import_tab = QWidget()
        import_layout = QVBoxLayout(import_tab)
        self.import_path = QLineEdit()
        self.import_path.setPlaceholderText('Choose a file to import…')
        import_browse = QPushButton('Browse…')
        import_browse.clicked.connect(self._browse_import)
        row2 = QHBoxLayout()
        row2.addWidget(self.import_path, 1)
        row2.addWidget(import_browse)
        import_layout.addLayout(row2)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Import mode:'))
        self.replace_radio = QRadioButton('Replace project data')
        self.replace_radio.setChecked(True)
        self.merge_radio = QRadioButton('Merge (keep existing)')
        mode_row.addWidget(self.replace_radio)
        mode_row.addWidget(self.merge_radio)
        mode_row.addStretch()
        import_layout.addLayout(mode_row)

        import_layout.addWidget(QLabel('Import validates every name, reference, quantity and probability before touching the database.'))
        self.import_log = QTextEdit()
        self.import_log.setReadOnly(True)
        self.import_log.setFixedHeight(140)
        import_layout.addWidget(self.import_log)

        import_btn = QPushButton('Import')
        import_btn.setObjectName('primaryBtn')
        import_btn.clicked.connect(self._do_import)
        import_layout.addWidget(import_btn, alignment=Qt.AlignRight)
        tabs.addTab(import_tab, 'Import')

        backup_tab = QWidget()
        backup_layout = QVBoxLayout(backup_tab)
        self.backup_path = QLineEdit()
        self.backup_path.setPlaceholderText('Choose where to save the backup…')
        backup_browse = QPushButton('Browse…')
        backup_browse.clicked.connect(self._browse_backup)
        row3 = QHBoxLayout()
        row3.addWidget(self.backup_path, 1)
        row3.addWidget(backup_browse)
        backup_layout.addLayout(row3)
        backup_layout.addWidget(QLabel('Backs up the entire database file (all projects) to a chosen location.'))
        backup_layout.addStretch()
        backup_btn = QPushButton('Backup now')
        backup_btn.setObjectName('primaryBtn')
        backup_btn.clicked.connect(self._do_backup)
        backup_layout.addWidget(backup_btn, alignment=Qt.AlignRight)
        tabs.addTab(backup_tab, 'Backup')

        close = _standard_button('Close')
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignRight)

    def _browse_export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export project', '', 'JSON project files (*.json)')
        if path:
            self.export_path.setText(path)

    def _browse_import(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import project', '', 'JSON project files (*.json)')
        if path:
            self.import_path.setText(path)

    def _browse_backup(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Backup database', '', 'Database backups (*.db)')
        if path:
            self.backup_path.setText(path)

    def _do_export(self):
        from .io_manager import export_project
        path = self.export_path.text().strip()
        if not path:
            QMessageBox.warning(self, 'Export', 'Choose an export file first.')
            return
        try:
            counts = export_project(self.db, self.project_id, path)
        except Exception as e:
            QMessageBox.critical(self, 'Export failed', str(e))
            return
        QMessageBox.information(
            self, 'Export complete',
            f'Exported project "{self.db.get_project(self.project_id)["name"]}"\n\n'
            f"{counts['items']} items · {counts['processes']} processes · {counts['recipes']} recipes\n→ {path}")

    def _do_import(self):
        from .io_manager import import_project, ImportError_
        path = self.import_path.text().strip()
        if not path:
            QMessageBox.warning(self, 'Import', 'Choose an import file first.')
            return
        mode = 'replace' if self.replace_radio.isChecked() else 'merge'
        if mode == 'replace':
            items_n = len(self.db.list_items(self.project_id))
            procs_n = len(self.db.list_processes(self.project_id))
            recipes_n = len(self.db.list_recipes(self.project_id))
            answer = QMessageBox.question(
                self, 'Confirm replace',
                f'Replace the project with the imported data?\n\nThis deletes {items_n} items, {procs_n} processes and {recipes_n} recipes.')
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            report = import_project(self.db, self.project_id, path, mode=mode)
        except ImportError_ as e:
            self.import_log.setPlainText(f'Import failed:\n\n{e}')
            return
        except Exception as e:
            self.import_log.setPlainText(f'Import failed:\n\n{e}')
            return
        self.import_log.setPlainText(
            'Import succeeded.\n\n'
            f"Imported {report['items']} items, {report['processes']} processes and {report['recipes']} recipes."
            + (f'\nSkipped {report["skipped"]} duplicate/invalid rows.' if report['skipped'] else ''))
        if self.on_imported:
            self.on_imported()

    def _do_backup(self):
        path = self.backup_path.text().strip()
        if not path:
            QMessageBox.warning(self, 'Backup', 'Choose a backup destination first.')
            return
        try:
            self.db.backup_to(path)
        except Exception as e:
            QMessageBox.critical(self, 'Backup failed', str(e))
            return
        QMessageBox.information(self, 'Backup complete', f'Backup saved to:\n{path}')


class SettingsDialog(QDialog):
    def __init__(self, parent, db: Database, project_id: int, on_reset=None):
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.on_reset = on_reset
        self.setWindowTitle('Settings')
        self.setModal(True)
        self.resize(560, 430)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        root.addWidget(QLabel(f'Data directory: {util.data_dir()}'))
        stats = self.db.stats(self.project_id)
        root.addWidget(QLabel(
            f'Current project: {self.db.get_project(self.project_id)["name"]}\n'
            f'{stats["items"]} items · {stats["processes"]} processes · {stats["recipes"]} recipes · {stats["byproduct_outputs"]} byproduct outputs'))

        root.addWidget(QLabel('Graph layout and window size are saved automatically.'))

        row1 = QHBoxLayout()
        reset_btn = QPushButton('Reset graph layout')
        reset_btn.setObjectName('ghostBtn')
        reset_btn.clicked.connect(self._reset_layout)
        row1.addWidget(reset_btn)
        row1.addStretch()
        root.addLayout(row1)

        row2 = QHBoxLayout()
        clear_btn = QPushButton('Clear project data…')
        clear_btn.setObjectName('dangerBtn')
        clear_btn.clicked.connect(self._clear_project)
        row2.addWidget(clear_btn)
        row2.addStretch()
        root.addLayout(row2)

        close = _standard_button('Close')
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignRight)

    def _reset_layout(self):
        try:
            self.db.clear_positions(self.project_id)
        except Exception as e:
            QMessageBox.warning(self, 'Reset failed', str(e))
            return
        if self.on_reset:
            self.on_reset()
        QMessageBox.information(self, 'Layout reset', 'Node positions were cleared. The graph will re-arrange itself.')

    def _clear_project(self):
        project = self.db.get_project(self.project_id)
        stats = self.db.stats(self.project_id)
        answer = QMessageBox.question(
            self, 'Clear project data',
            f'Delete ALL items, processes and recipes from project "{project["name"]}"?\n\n'
            f'This cannot be undone.\n\n({stats["items"]} items · {stats["recipes"]} recipes)')
        if answer != QMessageBox.StandardButton.Yes:
            return
        with self.db.conn:
            self.db.conn.execute('DELETE FROM recipe_outputs WHERE recipe_id IN (SELECT id FROM recipes WHERE project_id=?)', (self.project_id,))
            self.db.conn.execute('DELETE FROM recipe_inputs WHERE recipe_id IN (SELECT id FROM recipes WHERE project_id=?)', (self.project_id,))
            self.db.conn.execute('DELETE FROM recipes WHERE project_id=?', (self.project_id,))
            self.db.conn.execute('DELETE FROM items WHERE project_id=?', (self.project_id,))
            self.db.conn.execute('DELETE FROM processes WHERE project_id=?', (self.project_id,))
            self.db.conn.execute('DELETE FROM graph_layout WHERE project_id=?', (self.project_id,))
        images = util.data_dir() / 'projects' / str(self.project_id)
        if images.exists():
            import shutil
            shutil.rmtree(images, ignore_errors=True)
        if self.on_reset:
            self.on_reset()
        QMessageBox.information(self, 'Project cleared', 'All items, processes and recipes were deleted.')
