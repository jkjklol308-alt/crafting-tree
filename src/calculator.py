"""Recursive production-chain calculator.

Trace production backwards from targets to raw materials, accounting for
expected / guaranteed / confidence-based yields, shared byproduct credit and
multiple targets. Pure functions with no Qt dependency so they can be tested
and reused.

Design notes (documented for transparency):
- Guaranteed output = only recipes whose output for that item is 100%.
- Expected mode uses expected quantities (qty * probability).
- Custom confidence mode computes the exact minimum number of runs such that
  P(total output >= required) >= confidence, using an exact binomial tail.
- Byproduct credit is applied toward *input* items only (not target outputs):
  if a recipe produces a byproduct that another recipe in the plan consumes,
  the other recipe's need is reduced. Guaranteed mode credits only
  100%-probability byproducts.
- Convergence is iterative (bounded). Cycles are detected up front and
  reported; the calculation continues but such items are flagged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import Item, ProcessMethod, Recipe, RecipeOutput

MAX_ITERATIONS = 60
MAX_RUNS = 100000
EPS = 1e-9


@dataclass
class TargetSpec:
    item_id: int
    quantity: float
    recipe_id: Optional[int] = None   # None -> auto-pick (least runs)


@dataclass
class UnreliableItem:
    item_id: int
    quantity: float
    reason: str


@dataclass
class CyclePath:
    items: List[int]
    recipes: List[int]


@dataclass
class CalcResult:
    targets: Dict[int, float] = field(default_factory=dict)
    mode: str = 'expected'
    confidence: float = 0.95
    recipe_runs: Dict[int, int] = field(default_factory=dict)          # recipe_id -> runs
    produced_expected: Dict[int, float] = field(default_factory=dict)   # item -> expected total
    produced_guaranteed: Dict[int, float] = field(default_factory=dict) # item -> guaranteed total
    inputs_demand: Dict[int, float] = field(default_factory=dict)       # raw materials demanded
    missing: List[int] = field(default_factory=list)                     # targets with no recipe
    unreliable: List[UnreliableItem] = field(default_factory=list)      # items that cannot be guaranteed
    byproducts_expected: Dict[int, float] = field(default_factory=dict)  # non-target byproduct expected
    byproducts_guaranteed: Dict[int, float] = field(default_factory=dict)
    operation_counts: Dict[int, int] = field(default_factory=dict)      # process_id -> runs
    cycles: List[CyclePath] = field(default_factory=list)
    surplus_expected: Dict[int, float] = field(default_factory=dict)
    converged: bool = True

    def target_expected(self, item_id):
        return self.produced_expected.get(item_id, 0.0)

    def target_guaranteed(self, item_id):
        return self.produced_guaranteed.get(item_id, 0.0)


# ---------------------------------------------------------------- binomial
def binomial_tail_gte(n: int, m: int, p: float) -> float:
    """P(X >= m) for X ~ Binomial(n, p). Exact via log-gamma."""
    if m <= 0:
        return 1.0
    if m > n:
        return 0.0
    if p <= 0.0:
        return 1.0 if m <= 0 else 0.0
    if p >= 1.0:
        return 1.0
    # compute P(X >= m) as sum of pmf(k) for k = m..n
    total = 0.0
    ln_p = math.log(p)
    ln_q = math.log(1.0 - p)
    for k in range(m, n + 1):
        log_pmf = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * ln_p + (n - k) * ln_q
        # guard against overflow
        total += math.exp(log_pmf)
    return min(1.0, max(0.0, total))


def needed_runs_for_confidence(qty: float, qty_per_run: float, prob: float, confidence: float) -> Optional[int]:
    """Minimum number of runs n such that P(total >= qty) >= confidence.
    Per-run output = qty_per_run with probability prob, 0 otherwise.
    Returns None when confidence cannot be reached within sanity bounds.
    """
    if qty <= 0:
        return 0
    m = math.ceil(qty / qty_per_run)
    n = m
    while n <= MAX_RUNS:
        if binomial_tail_gte(n, m, prob) >= confidence:
            return n
        n += 1
    return None


def needed_runs(qty: float, qty_per_run: float, prob: float, mode: str, confidence: float) -> Optional[int]:
    if qty <= 0:
        return 0
    if mode == 'guaranteed':
        if prob >= 1.0:
            return math.ceil(qty / qty_per_run)
        return None  # cannot guarantee
    if mode == 'expected':
        return math.ceil(qty / (qty_per_run * prob))
    # custom confidence
    return needed_runs_for_confidence(qty, qty_per_run, prob, confidence)


# ---------------------------------------------------------------- recipe selection
def recipes_producing_item(recipes: List[Recipe], item_id: int) -> List[Recipe]:
    return [r for r in recipes if any(o.item_id == item_id for o in r.outputs)]


def recipe_output_spec(recipe: Recipe, item_id: int) -> Tuple[float, float]:
    for o in recipe.outputs:
        if o.item_id == item_id:
            return o.quantity, o.probability
    return 0.0, 1.0


def pick_recipe(item_id: int, recipes: List[Recipe], choices: Dict[int, Optional[int]],
                demand_qty: float = 1.0, mode: str = 'expected', confidence: float = 0.95) -> Optional[Recipe]:
    """Pick the recipe to use for item_id.

    Explicit choice for targets wins. Otherwise pick the recipe requiring the
    fewest runs for the requested quantity (least wasteful), ties broken by
    creation order.
    """
    candidates = recipes_producing_item(recipes, item_id)
    if not candidates:
        return None
    chosen_id = choices.get(item_id)
    if chosen_id:
        for r in candidates:
            if r.id == chosen_id:
                return r
    best = None
    best_runs = None
    for r in candidates:
        q, p = recipe_output_spec(r, item_id)
        if q <= 0:
            continue
        n = needed_runs(demand_qty, q, p, mode, confidence)
        if n is not None and (best_runs is None or n < best_runs):
            best_runs = n
            best = r
    return best if best is not None else candidates[0]


# ---------------------------------------------------------------- cycles
def find_cycles(recipes: List[Recipe]) -> List[CyclePath]:
    """Find cycles in the item-dependency graph (production flow).

    A cycle is a sequence of items A -> B -> ... -> A where the edge is justified
    by a recipe consuming A and producing B.
    """
    adj = {}  # item -> [(item, recipe)]
    for r in recipes:
        for inp in r.inputs:
            for out in r.outputs:
                adj.setdefault(inp.item_id, []).append((out.item_id, r.id))

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}
    cycles = []
    seen_cycles = set()

    def dfs(node, path):
        color[node] = GRAY
        path.append(node)
        for nxt, rid in adj.get(node, []):
            if nxt == path[0]:
                # cycle found: path[0:] + [path[0]] -> report item list + recipes
                cycle_items = tuple(path[0:])
                if cycle_items not in seen_cycles:
                    seen_cycles.add(cycle_items)
                    cycles.append(CyclePath(items=list(cycle_items), recipes=[rid]))
            elif color.get(nxt, WHITE) == WHITE:
                dfs(nxt, path)
            # gray nodes already on stack: ignore (handled by the root check)
        path.pop()
        color[node] = BLACK

    for node in list(adj.keys()):
        if color.get(node, WHITE) == WHITE:
            dfs(node, [])

    return cycles


# ---------------------------------------------------------------- main entry
def calculate(items: Dict[int, Item], processes: Dict[int, ProcessMethod],
              recipes: List[Recipe], targets: List[TargetSpec],
              mode: str = 'expected', confidence: float = 0.95) -> CalcResult:
    """Compute a production plan for the given targets.

    items: {id: Item}; processes: {id: ProcessMethod}; recipes: list of Recipe
    targets: list of TargetSpec(item_id, quantity, recipe_id=None)
    mode: 'expected' | 'guaranteed' | 'confidence'
    confidence: required confidence when mode == 'confidence'
    """
    result = CalcResult(mode=mode, confidence=confidence)
    target_map: Dict[int, float] = {}
    for t in targets:
        if t.quantity <= 0:
            continue
        target_map[t.item_id] = target_map.get(t.item_id, 0.0) + t.quantity
    result.targets = dict(target_map)

    if not target_map:
        return result

    choices = {t.item_id: t.recipe_id for t in targets}
    result.cycles = find_cycles(recipes)

    demand = dict(target_map)
    raw_demand: Dict[int, float] = {}
    all_produced_expected: Dict[int, float] = {}
    all_produced_guaranteed: Dict[int, float] = {}
    all_recipe_runs: Dict[int, int] = {}
    all_inputs: Dict[int, float] = {}
    all_byproduct_exp: Dict[int, float] = {}
    all_byproduct_guar: Dict[int, float] = {}

    missing: List[int] = []
    unreliable: List[UnreliableItem] = []

    converged = False
    for iteration in range(MAX_ITERATIONS):
        if not demand:
            converged = True
            break
        runs: Dict[int, int] = {}
        produced_exp: Dict[int, float] = {}
        produced_guar: Dict[int, float] = {}
        new_demand: Dict[int, float] = {}
        byproduct_exp: Dict[int, float] = {}
        byproduct_guar: Dict[int, float] = {}
        iteration_raw: Dict[int, float] = {}
        iteration_missing: List[int] = []
        iteration_unreliable: List[UnreliableItem] = []

        for item_id, qty in list(demand.items()):
            if qty <= EPS:
                continue
            recipe = pick_recipe(item_id, recipes, choices, qty, mode, confidence)
            if recipe is None:
                if item_id in target_map:
                    iteration_missing.append(item_id)
                else:
                    # intermediate with no recipe: it is a raw material
                    iteration_raw[item_id] = iteration_raw.get(item_id, 0.0) + qty
                continue
            out_qty, out_prob = recipe_output_spec(recipe, item_id)
            if out_qty <= 0:
                # recipe exists but no valid output spec: treat as unusable
                if item_id in target_map:
                    iteration_missing.append(item_id)
                else:
                    iteration_raw[item_id] = iteration_raw.get(item_id, 0.0) + qty
                continue
            n = needed_runs(qty, out_qty, out_prob, mode, confidence)
            if n is None:
                if item_id in target_map:
                    iteration_missing.append(item_id)
                iteration_unreliable.append(UnreliableItem(item_id, qty,
                    'Guaranteed mode: this item is only produced with probability < 100%.' if mode == 'guaranteed'
                    else 'Confidence target unreachable within reason.'))
                continue
            runs[recipe.id] = runs.get(recipe.id, 0) + n
            produced_exp[item_id] = produced_exp.get(item_id, 0.0) + out_qty * out_prob * n
            if out_prob >= 1.0:
                produced_guar[item_id] = produced_guar.get(item_id, 0.0) + out_qty * n
            # accumulate inputs and byproducts
            for inp in recipe.inputs:
                new_demand[inp.item_id] = new_demand.get(inp.item_id, 0.0) + inp.quantity * n
            for out in recipe.outputs:
                if out.item_id == item_id:
                    continue
                byproduct_exp[out.item_id] = byproduct_exp.get(out.item_id, 0.0) + out.quantity * out.probability * n
                if out.probability >= 1.0:
                    byproduct_guar[out.item_id] = byproduct_guar.get(out.item_id, 0.0) + out.quantity * n

        # apply byproduct credit toward input demands (not target demands)
        for item_id, credit_exp in list(byproduct_exp.items()):
            credit = credit_exp if mode != 'guaranteed' else byproduct_guar.get(item_id, 0.0)
            if credit <= 0:
                continue
            current = new_demand.get(item_id, 0.0)
            if current > EPS:
                if credit >= current:
                    new_demand.pop(item_id, None)
                else:
                    new_demand[item_id] = current - credit
            # credit beyond demand reduces surplus later

        # apply iteration results; raw materials from input chains are raw only
        # if the item truly has no recipe (checked inside the demand loop)
        for item_id, qty in iteration_raw.items():
            raw_demand[item_id] = raw_demand.get(item_id, 0.0) + qty
        for item_id, qty in produced_exp.items():
            all_produced_expected[item_id] = all_produced_expected.get(item_id, 0.0) + qty
        for item_id, qty in produced_guar.items():
            all_produced_guaranteed[item_id] = all_produced_guaranteed.get(item_id, 0.0) + qty
        for rid, n in runs.items():
            all_recipe_runs[rid] = all_recipe_runs.get(rid, 0) + n
            for inp in pick_recipe_inputs(recipes, rid):
                all_inputs[inp.item_id] = all_inputs.get(inp.item_id, 0.0) + inp.quantity * n
        for item_id, q in byproduct_exp.items():
            all_byproduct_exp[item_id] = all_byproduct_exp.get(item_id, 0.0) + q
        for item_id, q in byproduct_guar.items():
            all_byproduct_guar[item_id] = all_byproduct_guar.get(item_id, 0.0) + q

        missing.extend(iteration_missing)
        unreliable.extend(iteration_unreliable)

        new_demand = {k: v for k, v in new_demand.items() if v > EPS}
        if not new_demand:
            converged = True
            break
        demand = new_demand

    result.converged = converged
    result.recipe_runs = all_recipe_runs
    result.produced_expected = all_produced_expected
    result.produced_guaranteed = all_produced_guaranteed
    result.raw_inputs = raw_demand
    result.inputs_demand = raw_demand  # raw materials required
    result.missing = list(dict.fromkeys(missing))
    result.unreliable = unreliable
    result.byproducts_expected = all_byproduct_exp
    result.byproducts_guaranteed = all_byproduct_guar
    result.operation_counts = {}
    for rid, n in all_recipe_runs.items():
        for r in recipes:
            if r.id == rid:
                result.operation_counts[r.process_id] = result.operation_counts.get(r.process_id, 0) + n
                break
    # surplus: expected production - (demand as inputs + target demands)
    targets_set = set(target_map)
    total_demand_non_target: Dict[int, float] = {}
    for item_id, qty in all_inputs.items():
        total_demand_non_target[item_id] = total_demand_non_target.get(item_id, 0.0) + qty
    for item_id in list(targets_set):
        total_demand_non_target[item_id] = total_demand_non_target.get(item_id, 0.0) + target_map[item_id]
    surplus = {}
    for item_id, exp_total in all_produced_expected.items():
        guar_total = all_produced_guaranteed.get(item_id, 0.0)
        demand_total = total_demand_non_target.get(item_id, 0.0)
        expected_surplus = max(0.0, exp_total - demand_total)
        guar_surplus = max(0.0, guar_total - demand_total)
        if expected_surplus > EPS or guar_surplus > EPS:
            surplus[item_id] = expected_surplus
    result.surplus_expected = surplus

    return result


def pick_recipe_inputs(recipes, rid):
    for r in recipes:
        if r.id == rid:
            return r.inputs
    return []
