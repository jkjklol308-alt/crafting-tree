"""JSON import / export for projects.

Export format:
{
  "format": "crafting-tree-project",
  "version": 1,
  "exported_at": "...",
  "project": "Name",
  "items": [{"name","description","category","tags":[...], "image":"data:image/png;base64,..."}],
  "processes": [{"name","description","icon":"data:image/png;base64,..."}],
  "recipes": [{"process":"Name","name":"","notes":"",
               "inputs":[{"item":"Name","quantity":1}],
               "outputs":[{"item":"Name","quantity":1,"probability":1.0}]}]
}

Validation happens before any changes are applied. Imports that fail validation
must not modify the database.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .db import Database, NameTakenError
from . import models, util

FORMAT_NAME = 'crafting-tree-project'
FORMAT_VERSION = 1


class ImportError_(Exception):
    pass


def _data_url_to_bytes(data_url):
    if not isinstance(data_url, str):
        return None
    m = re.match(r'^data:([^;]+);base64,(.+)$', data_url, re.DOTALL)
    if not m:
        return None
    try:
        return m.group(1), base64.b64decode(m.group(2), validate=True)
    except Exception:
        return None


def _image_to_data_url(stored_path, data_dir):
    if not stored_path:
        return ''
    p = data_dir / stored_path
    if not p.exists():
        return ''
    suffix = p.suffix.lower()
    mime = 'image/png'
    if suffix in ('.jpg', '.jpeg'):
        mime = 'image/jpeg'
    elif suffix == '.webp':
        mime = 'image/webp'
    elif suffix == '.gif':
        mime = 'image/gif'
    elif suffix == '.bmp':
        mime = 'image/bmp'
    try:
        raw = p.read_bytes()
    except OSError:
        return ''
    return f'data:{mime};base64,{base64.b64encode(raw).decode("ascii")}'


def export_project(db: Database, project_id: int, export_path: Path) -> dict:
    """Export a project to JSON. Returns a summary dict."""
    data_dir = util.data_dir()
    project = db.get_project(project_id)
    if not project:
        raise ValueError('Project not found.')

    items_out = []
    for item in db.list_items(project_id):
        items_out.append({
            'name': item.name,
            'description': item.description,
            'category': item.category,
            'tags': list(item.tags),
            'image': _image_to_data_url(item.image_path, data_dir),
        })

    procs_out = []
    for p in db.list_processes(project_id):
        procs_out.append({
            'name': p.name,
            'description': p.description,
            'icon': _image_to_data_url(p.icon_path, data_dir),
        })

    recipes_out = []
    for recipe in db.list_recipes(project_id):
        proc = db.get_process(recipe.process_id)
        process_name = proc.name if proc else ''
        inputs_out = []
        outputs_out = []
        for inp in recipe.inputs:
            it = db.get_item(inp.item_id)
            if it:
                inputs_out.append({'item': it.name, 'quantity': inp.quantity})
        for out in recipe.outputs:
            it = db.get_item(out.item_id)
            if it:
                outputs_out.append({'item': it.name, 'quantity': out.quantity, 'probability': out.probability})
        recipes_out.append({
            'process': process_name,
            'name': recipe.name,
            'notes': recipe.notes,
            'inputs': inputs_out,
            'outputs': outputs_out,
        })

    doc = {
        'format': FORMAT_NAME,
        'version': FORMAT_VERSION,
        'exported_at': datetime.now().isoformat(timespec='seconds'),
        'project': project['name'],
        'counts': {'items': len(items_out), 'processes': len(procs_out), 'recipes': len(recipes_out)},
        'items': items_out,
        'processes': procs_out,
        'recipes': recipes_out,
    }
    export_path = Path(export_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding='utf-8')
    return doc['counts']


def validate_project_import(doc, project_id, db, mode):
    """Validate an import document against the target project (read-only check).

    Returns a list of human-readable errors (empty = valid).
    """
    errors = []
    if not isinstance(doc, dict):
        return ['Document must be a JSON object.']
    if doc.get('format') != FORMAT_NAME:
        errors.append('Unsupported file format: expected "crafting-tree-project".')
    if int(doc.get('version', 0) or 0) > FORMAT_VERSION:
        errors.append('Unsupported project file version.')
    for key in ('items', 'processes', 'recipes'):
        if not isinstance(doc.get(key), list):
            errors.append(f'Missing required list: "{key}".')
    if errors:
        return errors

    file_item_names = {}
    for i, it in enumerate(doc.get('items', [])):
        where = f'items[{i}]'
        if not isinstance(it, dict):
            errors.append(f'{where}: must be an object.')
            continue
        name = str(it.get('name', '') or '').strip()
        if not name:
            errors.append(f'{where}: "name" is required.')
            continue
        key = name.lower()
        if key in file_item_names:
            errors.append(f'{where}: duplicate item name "{name}" in file.')
            continue
        file_item_names[key] = name
        for field in ('description', 'category'):
            if field in it and it[field] is not None and not isinstance(it[field], str):
                errors.append(f'{where}: "{field}" must be a string.')
        if 'tags' in it:
            tags = it['tags']
            if not isinstance(tags, list) or not all(isinstance(t, (str, int, float)) for t in tags):
                errors.append(f'{where}: "tags" must be a list of strings.')
        image = it.get('image')
        if image:
            parsed = _data_url_to_bytes(image)
            if not parsed:
                errors.append(f'{where}: image is not a valid base64 data URL.')
            elif len(parsed[1]) > 20 * 1024 * 1024:
                errors.append(f'{where}: image exceeds the 20 MB limit.')

    file_process_names = {}
    for i, p in enumerate(doc.get('processes', [])):
        where = f'processes[{i}]'
        if not isinstance(p, dict):
            errors.append(f'{where}: must be an object.')
            continue
        name = str(p.get('name', '') or '').strip()
        if not name:
            errors.append(f'{where}: "name" is required.')
            continue
        key = name.lower()
        if key in file_process_names:
            errors.append(f'{where}: duplicate process name "{name}" in file.')
            continue
        file_process_names[key] = name
        if 'description' in p and p['description'] is not None and not isinstance(p['description'], str):
            errors.append(f'{where}: "description" must be a string.')
        icon = p.get('icon')
        if icon:
            parsed = _data_url_to_bytes(icon)
            if not parsed:
                errors.append(f'{where}: icon is not a valid base64 data URL.')
            elif len(parsed[1]) > 20 * 1024 * 1024:
                errors.append(f'{where}: icon exceeds the 20 MB limit.')

    existing_item_names = {it.name.lower() for it in db.list_items(project_id)}
    existing_process_names = {p.name.lower() for p in db.list_processes(project_id)}

    # In replace mode the file must be self-contained; in merge mode names may
    # reference existing items/processes (which are reused, not overwritten).
    for i, r in enumerate(doc.get('recipes', [])):
        where = f'recipes[{i}]'
        if not isinstance(r, dict):
            errors.append(f'{where}: must be an object.')
            continue
        process_name = str(r.get('process', '') or '').strip()
        if not process_name:
            errors.append(f'{where}: "process" is required.')
        else:
            key = process_name.lower()
            if mode == 'replace':
                if key not in file_process_names:
                    errors.append(f'{where}: unknown process "{process_name}" (not in the file).')
            else:
                if key not in file_process_names and key not in existing_process_names:
                    errors.append(f'{where}: unknown process "{process_name}".')
        inputs = r.get('inputs', [])
        outputs = r.get('outputs', [])
        if not isinstance(inputs, list) or not inputs:
            errors.append(f'{where}: must contain at least one input.')
        if not isinstance(outputs, list) or not outputs:
            errors.append(f'{where}: must contain at least one output.')
        if isinstance(inputs, list):
            for j, inp in enumerate(inputs):
                if not isinstance(inp, dict):
                    errors.append(f'{where}.inputs[{j}]: must be an object.')
                    continue
                item_name = str(inp.get('item', '') or '').strip()
                try:
                    qty = float(inp.get('quantity', 0))
                except (TypeError, ValueError):
                    errors.append(f'{where}.inputs[{j}]: quantity must be a number.')
                    continue
                if not item_name:
                    errors.append(f'{where}.inputs[{j}]: "item" is required.')
                elif mode == 'replace':
                    if item_name.lower() not in file_item_names:
                        errors.append(f'{where}.inputs[{j}]: unknown item "{item_name}" (not in the file).')
                else:
                    if item_name.lower() not in file_item_names and item_name.lower() not in existing_item_names:
                        errors.append(f'{where}.inputs[{j}]: unknown item "{item_name}".')
                if qty <= 0:
                    errors.append(f'{where}.inputs[{j}]: quantity must be greater than 0.')
        if isinstance(outputs, list):
            seen_outputs = set()
            for j, out in enumerate(outputs):
                if not isinstance(out, dict):
                    errors.append(f'{where}.outputs[{j}]: must be an object.')
                    continue
                item_name = str(out.get('item', '') or '').strip()
                try:
                    qty = float(out.get('quantity', 0))
                except (TypeError, ValueError):
                    errors.append(f'{where}.outputs[{j}]: quantity must be a number.')
                    continue
                try:
                    prob = float(out.get('probability', 1.0))
                except (TypeError, ValueError):
                    errors.append(f'{where}.outputs[{j}]: probability must be a number.')
                    continue
                if not item_name:
                    errors.append(f'{where}.outputs[{j}]: "item" is required.')
                elif mode == 'replace':
                    if item_name.lower() not in file_item_names:
                        errors.append(f'{where}.outputs[{j}]: unknown item "{item_name}" (not in the file).')
                else:
                    if item_name.lower() not in file_item_names and item_name.lower() not in existing_item_names:
                        errors.append(f'{where}.outputs[{j}]: unknown item "{item_name}".')
                key = item_name.lower()
                if key in seen_outputs:
                    errors.append(f'{where}.outputs[{j}]: duplicate output item "{item_name}".')
                seen_outputs.add(key)
                if qty <= 0:
                    errors.append(f'{where}.outputs[{j}]: quantity must be greater than 0.')
                if prob <= 0 or prob > 1.0:
                    errors.append(f'{where}.outputs[{j}]: probability must be in (0, 1].')
    return errors


def _resolve_images_in_import(dest_dir, url_data, project_id, kind):
    parsed = _data_url_to_bytes(url_data)
    if not parsed:
        return ''
    _, raw = parsed
    stored = util.unique_stored_name(source_path=f'{kind}.png')
    path = dest_dir / stored
    path.write_bytes(raw)
    return path.relative_to(util.data_dir()).as_posix()


def import_project(db: Database, project_id: int, file_path, mode: str = 'merge'):
    """Import a project JSON file into the given project.

    mode: 'replace' (delete current project contents first) or 'merge' (only
    add items/processes that do not exist yet; recipes are always created).
    Returns a summary dict; raises ImportError_ on validation failure.
    """
    file_path = Path(file_path)
    try:
        doc = json.loads(file_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        raise ImportError_(f'Could not read the file: {e}')

    if not isinstance(doc, dict):
        raise ImportError_('The file is not a valid project document.')

    errors = validate_project_import(doc, project_id, db, mode)
    if errors:
        raise ImportError_('\n'.join(errors[:80]))

    data_dir = util.data_dir()
    if mode == 'replace':
        with db.conn:
            db.conn.execute('DELETE FROM recipe_outputs WHERE recipe_id IN (SELECT id FROM recipes WHERE project_id=?)', (project_id,))
            db.conn.execute('DELETE FROM recipe_inputs WHERE recipe_id IN (SELECT id FROM recipes WHERE project_id=?)', (project_id,))
            db.conn.execute('DELETE FROM recipes WHERE project_id=?', (project_id,))
            db.conn.execute('DELETE FROM items WHERE project_id=?', (project_id,))
            db.conn.execute('DELETE FROM processes WHERE project_id=?', (project_id,))
            db.conn.execute('DELETE FROM graph_layout WHERE project_id=?', (project_id,))
        images = data_dir / 'projects' / str(project_id)
        if images.exists():
            shutil.rmtree(images, ignore_errors=True)

    imported = {'items': 0, 'processes': 0, 'recipes': 0, 'skipped': 0}

    # items
    images_dir = util.images_dir(project_id)
    for it in doc.get('items', []):
        name = str(it['name']).strip()
        image_rel = ''
        if it.get('image'):
            image_rel = _resolve_images_in_import(images_dir, it['image'], project_id, 'item')
        try:
            db.create_item(project_id, name, it.get('description', '') or '', it.get('category', '') or '',
                           [str(t) for t in (it.get('tags') or [])], image_rel)
            imported['items'] += 1
        except NameTakenError:
            if mode == 'merge':
                imported['skipped'] += 1
            else:
                raise

    # processes
    for p in doc.get('processes', []):
        name = str(p['name']).strip()
        icon_rel = ''
        if p.get('icon'):
            icon_rel = _resolve_images_in_import(images_dir, p['icon'], project_id, 'process')
        try:
            db.create_process(project_id, name, p.get('description', '') or '', icon_rel)
            imported['processes'] += 1
        except NameTakenError:
            if mode == 'merge':
                imported['skipped'] += 1
            else:
                raise

    # recipes: resolve by name
    items_by_name = {it.name.lower(): it.id for it in db.list_items(project_id)}
    procs_by_name = {p.name.lower(): p.id for p in db.list_processes(project_id)}
    for r in doc.get('recipes', []):
        process_name = str(r.get('process', '') or '').strip()
        process_id = procs_by_name.get(process_name.lower())
        if process_id is None:
            raise ImportError_(f'Process "{process_name}" not found after import.')
        inputs = []
        for inp in r.get('inputs', []):
            item_name = str(inp.get('item', '') or '').strip()
            item_id = items_by_name.get(item_name.lower())
            if item_id is None:
                raise ImportError_(f'Input item "{item_name}" not found after import.')
            inputs.append((item_id, float(inp.get('quantity', 1))))
        outputs = []
        for out in r.get('outputs', []):
            item_name = str(out.get('item', '') or '').strip()
            item_id = items_by_name.get(item_name.lower())
            if item_id is None:
                raise ImportError_(f'Output item "{item_name}" not found after import.')
            outputs.append((item_id, float(out.get('quantity', 1)), models.clamp_probability(out.get('probability', 1.0))))
        try:
            db.create_recipe(project_id, process_id, r.get('name', '') or '', r.get('notes', '') or '', inputs, outputs)
            imported['recipes'] += 1
        except ValueError:
            imported['skipped'] += 1

    return imported
