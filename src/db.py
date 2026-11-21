"""SQLite persistence layer.

Schema holds projects, items, processes, recipes (inputs/outputs), graph
layout positions and per-project settings (key/value). All mutations commit
immediately so data survives restarts.
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .models import Item, ProcessMethod, RecipeInput, RecipeOutput, Recipe, tags_to_str, tags_from_str, clamp_probability


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',
  image_path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(project_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS processes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  icon_path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(project_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS recipes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  process_id INTEGER NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS recipe_inputs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  quantity REAL NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recipe_outputs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  quantity REAL NOT NULL DEFAULT 1,
  probability REAL NOT NULL DEFAULT 1.0
);
CREATE TABLE IF NOT EXISTS graph_layout(
  project_id INTEGER NOT NULL,
  node_type TEXT NOT NULL,
  node_id INTEGER NOT NULL,
  x REAL NOT NULL,
  y REAL NOT NULL,
  PRIMARY KEY(project_id, node_type, node_id)
);
CREATE TABLE IF NOT EXISTS project_settings(
  project_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY(project_id, key)
);
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

SCHEMA_VERSION = '2'


class DatabaseError(Exception):
    pass


class NameTakenError(DatabaseError):
    def __init__(self, kind: str, name: str):
        super().__init__(f'A {kind} named "{name}" already exists.')
        self.kind = kind
        self.name = name


class ForeignKeyError(DatabaseError):
    pass


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self._init_schema()

    # ---------- schema / lifecycle ----------
    def _init_schema(self):
        with self.conn:
            self.conn.executescript(SCHEMA)
            self.conn.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            row = self.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row is None:
                self.conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
            elif row['value'] != SCHEMA_VERSION:
                # bump marker; no destructive migration needed for young schema
                self.conn.execute("UPDATE meta SET value=? WHERE key='schema_version'", (SCHEMA_VERSION,))

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------- generic meta ----------
    def get_meta(self, key: str, default=None):
        row = self.conn.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default

    def set_meta(self, key: str, value):
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)', (key, str(value)))

    # ---------- projects ----------
    def list_projects(self):
        rows = self.conn.execute('SELECT * FROM projects ORDER BY name COLLATE NOCASE').fetchall()
        return [dict(r) for r in rows]

    def create_project(self, name: str) -> int:
        name = (name or '').strip()
        if not name:
            raise ValueError('Project name cannot be empty.')
        with self.conn:
            try:
                cur = self.conn.execute('INSERT INTO projects(name) VALUES (?)', (name,))
                return cur.lastrowid
            except sqlite3.IntegrityError:
                raise NameTakenError('Project', name)

    def get_project(self, project_id):
        row = self.conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        return dict(row) if row else None

    def rename_project(self, project_id, name: str):
        name = (name or '').strip()
        if not name:
            raise ValueError('Project name cannot be empty.')
        with self.conn:
            try:
                self.conn.execute('UPDATE projects SET name=?, updated_at=? WHERE id=?', (name, _now(), project_id))
                self.conn.execute("UPDATE meta SET value=? WHERE key='current_project_id'", (str(project_id),))
            except sqlite3.IntegrityError:
                raise NameTakenError('Project', name)

    def delete_project(self, project_id):
        with self.conn:
            self.conn.execute('DELETE FROM recipe_outputs WHERE recipe_id IN (SELECT id FROM recipes WHERE project_id=?)', (project_id,))
            self.conn.execute('DELETE FROM recipe_inputs WHERE recipe_id IN (SELECT id FROM recipes WHERE project_id=?)', (project_id,))
            self.conn.execute('DELETE FROM recipes WHERE project_id=?', (project_id,))
            self.conn.execute('DELETE FROM items WHERE project_id=?', (project_id,))
            self.conn.execute('DELETE FROM processes WHERE project_id=?', (project_id,))
            self.conn.execute('DELETE FROM graph_layout WHERE project_id=?', (project_id,))
            self.conn.execute('DELETE FROM project_settings WHERE project_id=?', (project_id,))
            self.conn.execute('DELETE FROM projects WHERE id=?', (project_id,))

    def current_project_id(self):
        val = self.get_meta('current_project_id')
        if val:
            try:
                pid = int(val)
                if self.get_project(pid):
                    return pid
            except (ValueError, TypeError):
                pass
        row = self.conn.execute('SELECT id FROM projects ORDER BY id LIMIT 1').fetchone()
        if row:
            return row['id']
        return None

    def set_current_project(self, project_id):
        self.set_meta('current_project_id', str(project_id))

    # ---------- categories ----------
    def categories_for_project(self, project_id):
        rows = self.conn.execute(
            "SELECT category, COUNT(*) AS n FROM items WHERE project_id=? AND category<>'' GROUP BY category ORDER BY category COLLATE NOCASE",
            (project_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- items ----------
    def list_items(self, project_id=None, category=None, search=None):
        project_id = project_id or self.current_project_id()
        sql = 'SELECT * FROM items WHERE project_id=?'
        params = [project_id]
        if category and category != '__ALL__':
            sql += ' AND category=?'
            params.append(category)
        if search:
            like = f'%{search.strip()}%'
            sql += ' AND (name LIKE ? OR description LIKE ? OR category LIKE ? OR tags LIKE ?)'
            params.extend([like, like, like, like])
        sql += ' ORDER BY name COLLATE NOCASE'
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_item(self, item_id):
        row = self.conn.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def _row_to_item(self, row):
        return Item(
            id=row['id'], name=row['name'], description=row['description'],
            category=row['category'] or '', tags=tags_from_str(row['tags'] or ''),
            image_path=row['image_path'] or '',
            created_at=row['created_at'] or '', updated_at=row['updated_at'] or '')

    def item_name_taken(self, project_id, name, exclude_id=None):
        sql = 'SELECT id FROM items WHERE project_id=? AND name=? COLLATE NOCASE'
        params = [project_id, name.strip()]
        if exclude_id:
            sql += ' AND id!=?'
            params.append(exclude_id)
        row = self.conn.execute(sql, params).fetchone()
        return row is not None

    def create_item(self, project_id, name, description='', category='', tags=None, image_path=''):
        name = (name or '').strip()
        if not name:
            raise ValueError('Item name is required.')
        if self.item_name_taken(project_id, name):
            raise NameTakenError('Item', name)
        with self.conn:
            cur = self.conn.execute(
                'INSERT INTO items(project_id, name, description, category, tags, image_path) VALUES (?,?,?,?,?,?)',
                (project_id, name, (description or '').strip(), (category or '').strip(),
                 tags_to_str(tags or []), image_path or ''))
            return cur.lastrowid

    def update_item(self, item_id, **fields):
        row = self.conn.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
        if not row:
            raise ValueError('Item not found.')
        updates = []
        params = []
        if 'name' in fields:
            name = (fields['name'] or '').strip()
            if not name:
                raise ValueError('Item name is required.')
            if self.item_name_taken(row['project_id'], name, exclude_id=item_id):
                raise NameTakenError('Item', name)
            updates.append('name=?')
            params.append(name)
        for key, col in (('description', 'description'), ('category', 'category'), ('image_path', 'image_path')):
            if key in fields:
                updates.append(f'{col}=?')
                params.append((fields[key] or '').strip() if key != 'image_path' else (fields[key] or ''))
        if 'tags' in fields:
            updates.append('tags=?')
            params.append(tags_to_str(fields['tags'] or []))
        if not updates:
            return item_id
        updates.append('updated_at=?')
        params.append(_now())
        params.append(item_id)
        with self.conn:
            self.conn.execute(f"UPDATE items SET {', '.join(updates)} WHERE id=?", params)
        return item_id

    def delete_item(self, item_id):
        with self.conn:
            self.conn.execute('DELETE FROM items WHERE id=?', (item_id,))

    def count_recipes_using_item(self, item_id):
        row = self.conn.execute(
            'SELECT (SELECT COUNT(DISTINCT recipe_id) FROM recipe_inputs WHERE item_id=?)+(SELECT COUNT(DISTINCT recipe_id) FROM recipe_outputs WHERE item_id=?) AS n FROM items WHERE id=?',
            (item_id, item_id, item_id)).fetchone()
        return int(row['n']) if row else 0

    # ---------- processes ----------
    def list_processes(self, project_id=None):
        project_id = project_id or self.current_project_id()
        rows = self.conn.execute('SELECT * FROM processes WHERE project_id=? ORDER BY name COLLATE NOCASE', (project_id,)).fetchall()
        return [self._row_to_process(r) for r in rows]

    def _row_to_process(self, row):
        return ProcessMethod(id=row['id'], name=row['name'], description=row['description'] or '', icon_path=row['icon_path'] or '')

    def get_process(self, process_id):
        row = self.conn.execute('SELECT * FROM processes WHERE id=?', (process_id,)).fetchone()
        return self._row_to_process(row) if row else None

    def process_name_taken(self, project_id, name, exclude_id=None):
        sql = 'SELECT id FROM processes WHERE project_id=? AND name=? COLLATE NOCASE'
        params = [project_id, name.strip()]
        if exclude_id:
            sql += ' AND id!=?'
            params.append(exclude_id)
        return self.conn.execute(sql, params).fetchone() is not None

    def create_process(self, project_id, name, description='', icon_path=''):
        name = (name or '').strip()
        if not name:
            raise ValueError('Process name is required.')
        if self.process_name_taken(project_id, name):
            raise NameTakenError('Process', name)
        with self.conn:
            cur = self.conn.execute(
                'INSERT INTO processes(project_id, name, description, icon_path) VALUES (?,?,?,?)',
                (project_id, name, (description or '').strip(), icon_path or ''))
            return cur.lastrowid

    def update_process(self, process_id, **fields):
        row = self.conn.execute('SELECT * FROM processes WHERE id=?', (process_id,)).fetchone()
        if not row:
            raise ValueError('Process not found.')
        updates = []
        params = []
        if 'name' in fields:
            name = (fields['name'] or '').strip()
            if not name:
                raise ValueError('Process name is required.')
            if self.process_name_taken(row['project_id'], name, exclude_id=process_id):
                raise NameTakenError('Process', name)
            updates.append('name=?')
            params.append(name)
        if 'description' in fields:
            updates.append('description=?')
            params.append((fields['description'] or '').strip())
        if 'icon_path' in fields:
            updates.append('icon_path=?')
            params.append(fields['icon_path'] or '')
        if not updates:
            return process_id
        updates.append('updated_at=?')
        params.append(_now())
        params.append(process_id)
        with self.conn:
            self.conn.execute(f"UPDATE processes SET {', '.join(updates)} WHERE id=?", params)
        return process_id

    def delete_process(self, process_id):
        with self.conn:
            self.conn.execute('DELETE FROM processes WHERE id=?', (process_id,))

    def count_recipes_using_process(self, process_id):
        row = self.conn.execute('SELECT COUNT(*) AS n FROM recipes WHERE process_id=?', (process_id,)).fetchone()
        return int(row['n']) if row else 0

    # ---------- recipes ----------
    def list_recipes(self, project_id=None):
        project_id = project_id or self.current_project_id()
        rows = self.conn.execute('SELECT * FROM recipes WHERE project_id=? ORDER BY created_at, id', (project_id,)).fetchall()
        recipes = [self._row_to_recipe(r) for r in rows]
        for r in recipes:
            self._load_recipe_parts(r)
        return recipes

    def get_recipe(self, recipe_id):
        row = self.conn.execute('SELECT * FROM recipes WHERE id=?', (recipe_id,)).fetchone()
        if not row:
            return None
        r = self._row_to_recipe(row)
        self._load_recipe_parts(r)
        return r

    def _row_to_recipe(self, row):
        return Recipe(id=row['id'], process_id=row['process_id'], name=row['name'] or '',
                      notes=row['notes'] or '', created_at=row['created_at'] or '', updated_at=row['updated_at'] or '')

    def _load_recipe_parts(self, recipe):
        rows = self.conn.execute('SELECT item_id, quantity FROM recipe_inputs WHERE recipe_id=? ORDER BY id', (recipe.id,)).fetchall()
        recipe.inputs = [RecipeInput(item_id=r['item_id'], quantity=float(r['quantity'])) for r in rows]
        rows = self.conn.execute('SELECT item_id, quantity, probability FROM recipe_outputs WHERE recipe_id=? ORDER BY id', (recipe.id,)).fetchall()
        recipe.outputs = [RecipeOutput(item_id=r['item_id'], quantity=float(r['quantity']), probability=clamp_probability(float(r['probability']))) for r in rows]

    def create_recipe(self, project_id, process_id, name='', notes='', inputs=None, outputs=None):
        self._validate_recipe(process_id, inputs or [], outputs or [])
        if not self.get_process(process_id):
            raise ForeignKeyError('Processing method not found.')
        with self.conn:
            cur = self.conn.execute(
                'INSERT INTO recipes(project_id, process_id, name, notes) VALUES (?,?,?,?)',
                (project_id, process_id, (name or '').strip(), (notes or '').strip()))
            recipe_id = cur.lastrowid
            for item_id, qty in (inputs or []):
                self.conn.execute('INSERT INTO recipe_inputs(recipe_id, item_id, quantity) VALUES (?,?,?)',
                                  (recipe_id, int(item_id), float(qty)))
            for item_id, qty, prob in (outputs or []):
                self.conn.execute('INSERT INTO recipe_outputs(recipe_id, item_id, quantity, probability) VALUES (?,?,?,?)',
                                  (recipe_id, int(item_id), float(qty), clamp_probability(prob)))
            return recipe_id

    def update_recipe(self, recipe_id, name=None, notes=None, process_id=None, inputs=None, outputs=None):
        row = self.conn.execute('SELECT * FROM recipes WHERE id=?', (recipe_id,)).fetchone()
        if not row:
            raise ValueError('Recipe not found.')
        if process_id is None:
            process_id = row['process_id']
        new_inputs = inputs if inputs is not None else [(i.item_id, i.quantity) for i in self._load_current_inputs(recipe_id)]
        new_outputs = outputs if outputs is not None else [(o.item_id, o.quantity, o.probability) for o in self._load_current_outputs(recipe_id)]
        self._validate_recipe(process_id, new_inputs, new_outputs)
        with self.conn:
            self.conn.execute('UPDATE recipes SET process_id=?, name=?, notes=?, updated_at=? WHERE id=?',
                              (process_id, name if name is not None else row['name'],
                               notes if notes is not None else row['notes'], _now(), recipe_id))
            self.conn.execute('DELETE FROM recipe_inputs WHERE recipe_id=?', (recipe_id,))
            self.conn.execute('DELETE FROM recipe_outputs WHERE recipe_id=?', (recipe_id,))
            for item_id, qty in (new_inputs or []):
                self.conn.execute('INSERT INTO recipe_inputs(recipe_id, item_id, quantity) VALUES (?,?,?)',
                                  (recipe_id, int(item_id), float(qty)))
            for item_id, qty, prob in (new_outputs or []):
                self.conn.execute('INSERT INTO recipe_outputs(recipe_id, item_id, quantity, probability) VALUES (?,?,?,?)',
                                  (recipe_id, int(item_id), float(qty), clamp_probability(prob)))
        return recipe_id

    def _load_current_inputs(self, recipe_id):
        rows = self.conn.execute('SELECT item_id, quantity FROM recipe_inputs WHERE recipe_id=? ORDER BY id', (recipe_id,)).fetchall()
        return [(int(r['item_id']), float(r['quantity'])) for r in rows]

    def _load_current_outputs(self, recipe_id):
        rows = self.conn.execute('SELECT item_id, quantity, probability FROM recipe_outputs WHERE recipe_id=? ORDER BY id', (recipe_id,)).fetchall()
        return [(int(r['item_id']), float(r['quantity']), float(r['probability'])) for r in rows]

    def _validate_recipe(self, process_id, inputs, outputs):
        if not process_id:
            raise ValueError('Select a processing method.')
        if not inputs:
            raise ValueError('A recipe needs at least one input.')
        if not outputs:
            raise ValueError('A recipe needs at least one output.')
        seen_in = set()
        for item_id, qty in inputs:
            if int(item_id) in seen_in:
                raise ValueError('Duplicate input item; merge quantities instead.')
            seen_in.add(int(item_id))
            if float(qty) <= 0:
                raise ValueError('Input quantity must be greater than 0.')
        seen_out = set()
        for item_id, qty, prob in outputs:
            if int(item_id) in seen_out:
                raise ValueError('Duplicate output item; merge quantities instead.')
            seen_out.add(int(item_id))
            if float(qty) <= 0:
                raise ValueError('Output quantity must be greater than 0.')
            p = clamp_probability(prob)
            if p <= 0:
                raise ValueError('Output probability must be greater than 0.')

    def delete_recipe(self, recipe_id):
        with self.conn:
            self.conn.execute('DELETE FROM recipes WHERE id=?', (recipe_id,))

    def delete_item_with_recipes(self, project_id, item_id):
        """Delete item and remove all references inside recipes (and their recipe if it becomes empty)."""
        with self.conn:
            recipe_ids = [r['id'] for r in self.conn.execute('SELECT DISTINCT recipe_id FROM recipe_inputs WHERE item_id=? UNION SELECT DISTINCT recipe_id FROM recipe_outputs WHERE item_id=?', (item_id, item_id)).fetchall()]
            self.conn.execute('DELETE FROM recipe_inputs WHERE item_id=?', (item_id,))
            self.conn.execute('DELETE FROM recipe_outputs WHERE item_id=?', (item_id,))
            self.conn.execute('DELETE FROM items WHERE id=?', (item_id,))
            for rid in recipe_ids:
                r = self.conn.execute('SELECT COUNT(*) AS n FROM recipe_inputs WHERE recipe_id=?', (rid,)).fetchone()
                o = self.conn.execute('SELECT COUNT(*) AS n FROM recipe_outputs WHERE recipe_id=?', (rid,)).fetchone()
                if int(r['n']) == 0 or int(o['n']) == 0:
                    self.conn.execute('DELETE FROM recipes WHERE id=?', (rid,))
            return len(recipe_ids)

    def recipes_producing_item(self, project_id, item_id):
        rows = self.conn.execute(
            'SELECT DISTINCT recipe_id FROM recipe_outputs WHERE item_id=? AND recipe_id IN (SELECT id FROM recipes WHERE project_id=?) ORDER BY recipe_id',
            (item_id, project_id)).fetchall()
        return [self.get_recipe(r['recipe_id']) for r in rows]

    def recipes_consuming_item(self, project_id, item_id):
        rows = self.conn.execute(
            'SELECT DISTINCT recipe_id FROM recipe_inputs WHERE item_id=? AND recipe_id IN (SELECT id FROM recipes WHERE project_id=?) ORDER BY recipe_id',
            (item_id, project_id)).fetchall()
        return [self.get_recipe(r['recipe_id']) for r in rows]

    def recipes_using_process(self, project_id, process_id):
        rows = self.conn.execute(
            'SELECT id FROM recipes WHERE project_id=? AND process_id=? ORDER BY id', (project_id, process_id)).fetchall()
        return [self.get_recipe(r['id']) for r in rows]

    def is_raw_material(self, project_id, item_id):
        """Raw material = no recipe produces this item."""
        row = self.conn.execute(
            'SELECT COUNT(*) AS n FROM recipe_outputs WHERE item_id=? AND recipe_id IN (SELECT id FROM recipes WHERE project_id=?)',
            (item_id, project_id)).fetchone()
        return int(row['n']) == 0

    def is_final_product(self, project_id, item_id):
        """Final product = no recipe consumes this item."""
        row = self.conn.execute(
            'SELECT COUNT(*) AS n FROM recipe_inputs WHERE item_id=? AND recipe_id IN (SELECT id FROM recipes WHERE project_id=?)',
            (item_id, project_id)).fetchone()
        return int(row['n']) == 0

    # ---------- graph layout ----------
    def get_positions(self, project_id):
        rows = self.conn.execute('SELECT node_type, node_id, x, y FROM graph_layout WHERE project_id=?', (project_id,)).fetchall()
        return {(r['node_type'], int(r['node_id'])): (float(r['x']), float(r['y'])) for r in rows}

    def set_position(self, project_id, node_type, node_id, x, y):
        with self.conn:
            self.conn.execute(
                'INSERT OR REPLACE INTO graph_layout(project_id, node_type, node_id, x, y) VALUES (?,?,?,?,?)',
                (project_id, node_type, int(node_id), float(x), float(y)))

    def clear_positions(self, project_id):
        with self.conn:
            self.conn.execute('DELETE FROM graph_layout WHERE project_id=?', (project_id,))

    # ---------- project settings ----------
    def get_setting(self, project_id, key, default=None):
        row = self.conn.execute('SELECT value FROM project_settings WHERE project_id=? AND key=?', (project_id, key)).fetchone()
        return row['value'] if row else default

    def set_setting(self, project_id, key, value):
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO project_settings(project_id, key, value) VALUES (?,?,?)',
                              (project_id, key, str(value)))

    # ---------- statistics ----------
    def stats(self, project_id):
        items = self.conn.execute('SELECT COUNT(*) AS n FROM items WHERE project_id=?', (project_id,)).fetchone()['n']
        procs = self.conn.execute('SELECT COUNT(*) AS n FROM processes WHERE project_id=?', (project_id,)).fetchone()['n']
        recs = self.conn.execute('SELECT COUNT(*) AS n FROM recipes WHERE project_id=?', (project_id,)).fetchone()['n']
        byproducts = self.conn.execute(
            'SELECT COUNT(*) AS n FROM recipe_outputs WHERE probability<1.0 AND recipe_id IN (SELECT id FROM recipes WHERE project_id=?)',
            (project_id,)).fetchone()['n']
        return {'items': int(items), 'processes': int(procs), 'recipes': int(recs), 'byproduct_outputs': int(byproducts)}

    def backup_to(self, destination_path):
        import shutil
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, dest)
        return str(dest)
