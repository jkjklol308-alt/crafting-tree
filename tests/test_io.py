"""Headless tests for JSON export/import."""
import sys
sys.path.insert(0, '/home/user/crafting-tree')

import tempfile, json
from pathlib import Path
from src.db import Database
from src import io_manager
from src import util

tmp = Path(tempfile.mkdtemp())
# redirect util.data_dir by patching path? The io code uses util.data_dir() — patch it
orig_data_dir = util.data_dir
util.data_dir = lambda: tmp
try:
    db = Database(tmp / 't.db')
    pid = db.create_project('RoundTrip')
    i1 = db.create_item(pid, 'Cobblestone', 'A rock', 'ore', ['stone'], '')
    i2 = db.create_item(pid, 'Gravel', 'Small stones', 'ore', ['stone'], '')
    p1 = db.create_process(pid, 'Crushing', '', '')
    rid = db.create_recipe(pid, p1, '', '', [(i1, 2)], [(i2, 2, 1.0)])
    out = tmp / 'export.json'
    counts = io_manager.export_project(db, pid, out)
    assert counts['items'] == 2 and counts['processes'] == 1 and counts['recipes'] == 1
    data = json.loads(out.read_text())
    assert data['format'] == 'crafting-tree-project'
    assert data['items'][0]['name'] in ('Cobblestone', 'Gravel')

    # import into a new project with replace mode
    pid2 = db.create_project('ImportTarget')
    report = io_manager.import_project(db, pid2, out, mode='replace')
    assert report['items'] == 2, report
    assert report['recipes'] == 1, report
    items = db.list_items(pid2)
    names = {it.name for it in items}
    assert names == {'Cobblestone', 'Gravel'}, names
    procs = db.list_processes(pid2)
    assert [p.name for p in procs] == ['Crushing']
    recipes = db.list_recipes(pid2)
    assert len(recipes) == 1
    r = recipes[0]
    assert len(r.inputs) == 1 and r.inputs[0].quantity == 2
    assert len(r.outputs) == 1 and r.outputs[0].quantity == 2

    # merge mode into existing project with 1 item
    pid3 = db.create_project('MergeTarget')
    db.create_item(pid3, 'Mystery', '', '', [], '')
    report2 = io_manager.import_project(db, pid3, out, mode='merge')
    assert report2['items'] == 2
    assert len(db.list_items(pid3)) == 3  # Mystery + 2 new

    # reload → no duplicates in merge mode again
    report3 = io_manager.import_project(db, pid3, out, mode='merge')
    assert report3['items'] == 0 and report3['skipped'] >= 2

    # validation failure: recipe with unknown item should be rejected
    bad = {'format': 'crafting-tree-project', 'version': 1, 'project': 'Bad',
           'items': [], 'processes': [],
           'recipes': [{'process': 'Crushing', 'inputs': [{'item': 'Ghost', 'quantity': 1}],
                        'outputs': [{'item': 'Ghost', 'quantity': 1, 'probability': 1.0}]}]}
    bad_path = tmp / 'bad.json'
    bad_path.write_text(json.dumps(bad))
    try:
        io_manager.import_project(db, pid2, bad_path, mode='replace')
        raise SystemExit('ERROR: bad import should have failed')
    except io_manager.ImportError_ as e:
        assert 'unknown process' in str(e).lower()

    print('ALL IO TESTS PASSED')
finally:
    util.data_dir = orig_data_dir
    db.close()
