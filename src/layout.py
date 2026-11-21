"""Pure-Python graph layout (no Qt dependency).

Layered layout: raw materials in column 0, final products in the last column.
Processes sit between columns, vertically centered on their inputs/outputs.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import Item, Recipe, ProcessMethod

ITEM_COLUMN_W = 280
ITEM_ROW_H = 150
PROCESS_ROW_H = 150


def items_producing(recipes: List[Recipe], item_id: int) -> List[Recipe]:
    return [r for r in recipes if any(o.item_id == item_id for o in r.outputs)]


def items_consuming(recipes: List[Recipe], item_id: int) -> List[Recipe]:
    return [r for r in recipes if any(i.item_id == item_id for i in r.inputs)]


def input_items_of_recipes(recipes: List[Recipe], recipe_ids):
    return [inp.item_id for r in recipes for inp in r.inputs if r.id in recipe_ids]


def compute_item_depths(items: Dict[int, Item], recipes: List[Recipe]) -> Dict[int, int]:
    """Depth of each item: raw items = 0, others = 1 + max(input depths).

    Cyclic items are assigned a best-effort depth so the layout never hangs.
    """
    producing = {}
    for r in recipes:
        for out in r.outputs:
            producing.setdefault(out.item_id, []).append(r.id)
    depths = {}
    # raw items (no producing recipe)
    for item_id in items:
        if item_id not in producing:
            depths[item_id] = 0

    changed = True
    iterations = 0
    while changed and iterations < 100:
        changed = False
        iterations += 1
        for item_id in items:
            if item_id in depths:
                continue
            rids = producing.get(item_id, [])
            if not rids:
                continue
            inputs = set()
            for rid in rids:
                for r in recipes:
                    if r.id == rid:
                        inputs.update(i.item_id for i in r.inputs)
            if not inputs:
                depths[item_id] = 0
                continue
            if all(i in depths for i in inputs):
                depths[item_id] = 1 + max(depths[i] for i in inputs)
                changed = True
    # remaining (cyclic) items
    for item_id in items:
        if item_id in depths:
            continue
        rids = producing.get(item_id, [])
        known = []
        for rid in rids:
            for r in recipes:
                if r.id == rid:
                    known.extend(depths.get(i.item_id, -1) for i in r.inputs)
        known_vals = [k for k in known if k >= 0]
        depths[item_id] = (1 + max(known_vals)) if known_vals else 0

    return depths


def compute_positions(items: Dict[int, Item],
                     processes: Dict[int, ProcessMethod],
                     recipes: List[Recipe]) -> Dict[tuple, Tuple[float, float]]:
    """Compute (x, y) for every node."""
    depths = compute_item_depths(items, recipes)
    by_depth = {}
    for item_id, d in depths.items():
        by_depth.setdefault(d, []).append(item_id)

    positions = {}
    for d, item_ids in by_depth.items():
        height = len(item_ids) * ITEM_ROW_H
        for idx, item_id in enumerate(sorted(item_ids, key=lambda i: (i))):
            x = d * ITEM_COLUMN_W
            y = idx * ITEM_ROW_H - height / 2 + ITEM_ROW_H / 2
            positions[('item', item_id)] = (x, y)

    # process nodes: x between input depth and output depth; y = mean of inputs/outputs
    proc_depths = {}
    proc_y = {}
    for r in recipes:
        if r.process_id not in processes:
            continue
        proc_depths.setdefault(r.process_id, [])
        in_items = [inp.item_id for inp in r.inputs]
        out_items = [out.item_id for out in r.outputs]
        in_depths = [depths.get(i, 0) for i in in_items]
        out_depths = [depths.get(i, 0) for i in out_items]
        d = (min(in_depths) + 0.5) if in_depths else 0
        if out_depths:
            d = max(d, (min(out_depths) - 0.5))
        proc_depths[r.process_id].append(d)
        y_vals = []
        for i in in_items:
            if ('item', i) in positions:
                y_vals.append(positions[('item', i)][1])
        for i in out_items:
            if ('item', i) in positions:
                y_vals.append(positions[('item', i)][1])
        if y_vals:
            proc_y.setdefault(r.process_id, []).append(sum(y_vals) / len(y_vals))

    for pid in processes:
        d = proc_depths.get(pid)
        if d:
            x = (sum(d) / len(d)) * ITEM_COLUMN_W
        else:
            x = 0
        y_vals = proc_y.get(pid)
        y = sum(y_vals) / len(y_vals) if y_vals else 0
        positions[('process', pid)] = (x, y)

    return positions
