# Crafting Tree — Create Mod Factory Manager

A standalone **desktop application** for documenting, visualising and calculating the Minecraft Create Mod production network: items, processes, recipes and interconnected production chains.

It is **not** a website, does not rely on a browser, and works fully offline. All data is stored locally in a SQLite database.

---

## Features

- **Item database** — create / edit / rename / delete items, with categories, tags, descriptions and optional image icons (e.g. Minecraft item textures). Items are reusable everywhere.
- **Processing methods** — custom processes (Crushing, Washing, Milling, …), created by hand — nothing is generated for you.
- **Recipes** — multiple inputs with per-input quantities, multiple outputs with per-output quantities, adjustable output probabilities (100% = guaranteed, <100% = probabilistic) and byproducts.
- **Interactive bubble-web graph** — every item and process as a draggable node, direction of production on every edge, probabilities and quantities on output edges, branch collapsing, zoom/pan, filters (direct / upstream / downstream / chain), auto-arranging, fit-to-view.
- **Item inspection** — click any node to see *Produced by* and *Can produce* with every input, quantity, probability and process. Every chip is clickable to navigate; the breadcrumb bar keeps your exploration history.
- **Search & filters** — search items by name / category / tag / description, browse by category.
- **Production calculator** — select one or more targets (total quantities), choose recipes, choose a calculation mode:
  - **Expected output** — average quantities using probabilities.
  - **Guaranteed output** — only 100%-probability outputs are counted (never assumes a byproduct is a guaranteed resource).
  - **Custom confidence** — exact binomial-tail math computes the minimum number of runs so the probability of reaching the target quantity reaches your confidence level.
  - Recursive planning back to raw materials, with byproduct credit toward other production chains, cycle detection, missing-recipe reporting and surplus tracking.
  - Results shown as a summary, an expandable chain tree, and an interactive plan graph (quantities, run counts and probabilities).
- **Multiple projects** — separate independent factories, with import/export and backups.
- **JSON import/export** — full project export with images embedded, with strict validation before import (replace or merge mode).
- **Backup** — copy the entire database to a chosen location.
- **Persistence** — SQLite, all changes auto-save, graph positions are saved too.

---

## Requirements

- **Windows** (main target): Python 3.9+ (64-bit)
- **Linux/macOS** work too (Qt offscreen support may vary)
- No internet required once dependencies are installed

## Install & run

The simplest path is the launch script — it installs dependencies on first run:

**Windows**
```bat
launch.bat
```

**Linux / macOS**
```bash
chmod +x launch.sh
./launch.sh
```

Or manually:

```bash
pip install -r requirements.txt
python app.py
```

The first run creates a `.venv` next to `app.py` (if PySide6 is not already installed). Data is stored in the platform data directory:
- **Windows**: `%APPDATA%\CraftingTree\crafting-tree.db`
- **Linux**: `~/.local/share/crafting-tree/crafting-tree.db`
- **macOS**: `~/.local/share/crafting-tree/crafting-tree.db`

## How to use

### 1. Build your database
Start with an empty database (exactly like the real factory):
1. **+ Item** — create items (Cobblestone, Gravel, Iron Nugget, …). Attach an image to give each a Minecraft-texture icon.
2. **+ Process** — create processing methods (Crushing, Washing, …).
3. **+ Recipe** — for each recipe: choose the processing method, add inputs with quantities and outputs with quantities + probabilities (100% guaranteed, less than 100% = probabilistic byproduct).

The graph updates automatically. Drag nodes around, right‑click a node to collapse or filter its branch, scroll to zoom, drag empty space to pan. Double‑click any node to edit it.

### 2. Explore the network
Click any item in the graph or in the left sidebar. The right panel shows:
- **Produced by** — every recipe that makes it, with inputs, quantities and probabilities.
- **Can produce** — every recipe that consumes it.
Everything is clickable to keep exploring. Use the breadcrumb bar to step back through your navigation history.

### 3. Filter the graph
The filter bar above the graph — **All / Direct / Upstream / Downstream / Chain** — focuses the view around the selected item. The **Byproducts** toggle hides probabilistic outputs (the noise).

### 4. Calculate production
Press **⚗ Calculator** (top bar):
1. Add one or more target items with quantities.
2. If more than one recipe produces a target, pick one (or leave **Auto**).
3. Choose a mode — **Expected** (average quantities), **Guaranteed** (100% outputs only) or **Custom confidence** (e.g. 95%).
4. Press **Calculate**.

The calculator traces back recursively to raw materials, counts processing operations, tracks expected and guaranteed byproducts, reports surplus materials, missing recipes and production cycles. The **Production chain** tab renders the plan as a zoomable graph with quantities and probabilities on every node and edge.

*Note on byproduct credit:* byproducts are credited toward other items' needs in the plan, but they do not reduce the already-required runs of the target items themselves. Guaranteed mode only credits 100%-probability byproducts. The calculator never modifies your recipe database.

### 5. Multiple projects
The **Projects** button in the top bar opens the project manager — create / rename / delete / switch independent projects. Each project holds its own items, processes, recipes and graph layout.

### 6. Import / export / backups
**Import / Export** in the top bar:
- **Export** — full JSON file of the current project (items, processes, recipes, embedded images).
- **Import** — load a JSON file into the project in **replace** mode (deletes current content after a confirmation) or **merge** mode (adds only missing items/processes and all recipes). Import is validated before it touches the database.
- **Backup** — copy the entire database to a chosen file.

## File layout

```
app.py                  # entry point
launch.bat              # Windows launcher
launch.sh               # Linux/macOS launcher
requirements.txt        # PySide6
src/
  main_window.py        # main window, layout, wiring
  graph.py               # interactive bubble-web scene & view
  layout.py              # pure layout math
  calculator.py          # recursive production planner
  calculator_ui.py       # calculator dialog (summary / tree / graph)
  db.py                  # SQLite persistence
  io_manager.py          # JSON import/export with validation
  dialogs_items.py       # item / process dialogs
  dialogs_recipe.py      # recipe dialog
  dialogs_meta.py        # projects / import-export / settings
  sidebar.py             # left sidebar (search, categories, item list)
  info_panel.py          # right panel (breadcrumbs, item/process details)
  models.py              # data models
  theme.py               # dark theme
  util.py                # platform/path helpers
tests/                   # headless tests (calculator, IO)
```

## Tests

The calculator and JSON import/export are covered by headless tests:

```bash
python tests/test_calculator.py
python tests/test_io.py
```

## Known limitations

- Byproduct reuse is credited toward downstream/raw demand, not toward the targets themselves (documented in the calculator).
- Guaranteed mode can only guarantee items produced by 100%-probability recipes — probabilistic items are flagged as unreliable instead of being silently padded.
- Graph layout positions are saved per node; moving a node to a previously seen position is not preserved across re-layout.
- No executable packaging is provided — run the Python source directly.
