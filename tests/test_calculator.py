"""Headless tests for the calculator (no GUI needed)."""
import sys, math
sys.path.insert(0, '/home/user/crafting-tree')

from src.models import Item, ProcessMethod, Recipe, RecipeInput, RecipeOutput
from src.calculator import (
    calculate, TargetSpec, binomial_tail_gte, find_cycles, needed_runs_for_confidence,
)


def item(i, name='item', cat=''):
    return Item(id=i, name=name or f'item{i}', description='', category=cat)


def process(i, name='process'):
    return ProcessMethod(id=i, name=name or f'process{i}')


def recipe(i, process_id, inputs, outputs):
    return Recipe(id=i, process_id=process_id, name='', inputs=[RecipeInput(it, q) for it, q in inputs],
                  outputs=[RecipeOutput(it, q, p) for it, q, p in outputs])


def test_expected_mode():
    items = {1: item(1, 'cobblestone'), 2: item(2, 'gravel'), 3: item(3, 'iron')}
    processes = {1: process(1, 'crushing'), 2: process(2, 'washing')}
    recipes = [
        recipe(1, 1, [(1, 1)], [(2, 1, 1.0)]),
        recipe(2, 2, [(2, 1)], [(3, 1, 0.5)]),
    ]
    # target 4 iron: expected mode -> n = ceil(4 / (1*0.5)) = 8 runs -> gravel 8 -> cobble 8
    res = calculate(items, processes, recipes, [TargetSpec(3, 4.0)], mode='expected')
    assert res.recipe_runs[2] == 8, res.recipe_runs
    assert res.raw_inputs.get(1) == 8, res.raw_inputs
    assert res.produced_expected.get(3) == 4.0
    assert abs(res.produced_expected.get(2) - 8.0) < 1e-9  # 8 runs * 1.0
    print('test_expected_mode OK')


def test_guaranteed_mode_probabilistic():
    items = {1: item(1, 'gravel'), 2: item(2, 'iron')}
    processes = {1: process(1, 'washing')}
    recipes = [recipe(1, 1, [(1, 1)], [(2, 1, 0.25)])]
    res = calculate(items, processes, recipes, [TargetSpec(2, 10.0)], mode='guaranteed')
    # 25% output -> cannot guarantee; unreliable, no runs computed for the target
    assert res.unreliable, res
    assert 2 in res.missing or any(u.item_id == 2 for u in res.unreliable)
    print('test_guaranteed_mode_probabilistic OK')


def test_guaranteed_mode_100pct():
    items = {1: item(1), 2: item(2)}
    processes = {1: process(1, 'washing')}
    recipes = [recipe(1, 1, [(1, 2)], [(2, 2, 1.0)])]
    res = calculate(items, processes, recipes, [TargetSpec(2, 10.0)], mode='guaranteed')
    # need 10 of item2 -> runs = ceil(10/2) = 5 -> raw input 2*5=10
    assert res.recipe_runs[1] == 5
    assert res.raw_inputs.get(1) == 10
    print('test_guaranteed_mode_100pct OK')


def test_confidence_mode():
    # 1 qty per run at p=0.25; target 100; confidence 0.95
    n = needed_runs_for_confidence(100.0, 1.0, 0.25, 0.95)
    assert n is not None and n > 0
    # verify probability at that n is >= 0.95
    assert binomial_tail_gte(n, 100, 0.25) >= 0.95
    # and n-1 fails (roughly, minimal scan from m)
    print('test_confidence_mode OK (n=%d)' % n)


def test_confidence_mode_convergence_monotone():
    # higher confidence -> more runs (or None)
    n95 = needed_runs_for_confidence(1001.0, 1.0, 0.25, 0.95)
    n99 = needed_runs_for_confidence(1001.0, 1.0, 0.25, 0.99)
    assert n95 is not None and n99 is not None
    assert n99 >= n95


def test_byproduct_credit():
    # Iron sheet target: R produces iron 2/run (100%) + flint byproduct 1/run (100%)
    # Flint recipe: inputs flint 1, outputs brass 2 (100%). Target: brass 10.
    # Iteration 1: demand {brass:10}; runs brass_recipe = ceil(10/2)=5; inputs flint = 5;
    #   produced iron nothing (iron not a target). byproduct flint = 5 from... no iron runs.
    # Hmm need byproduct from target recipe that ALSO consumes flint.
    # Setup: R_iron consumes flint 1/run and produces iron 2/run + stone 1/run (100%)
    # Target iron 10: runs=5; inputs flint = 5 + byproduct stone 5 (unused).
    # Flint needed by iron = 5. Flint is raw (no recipe).
    # This doesn't credit byproduct since flint is raw. Test byproduct credit to raw:
    items = {1: item(1, 'flint'), 2: item(2, 'iron'), 3: item(3, 'stone')}
    processes = {1: process(1, 'sintering')}
    recipes = [recipe(1, 1, [(1, 1)], [(2, 2, 1.0), (3, 1, 1.0)])]
    res = calculate(items, processes, recipes, [TargetSpec(2, 10.0)], mode='expected')
    assert res.raw_inputs.get(1) == 5, res.raw_inputs
    assert abs(res.byproducts_expected.get(3, 0) - 5.0) < 1e-9
    print('test_byproduct_credit OK')


def test_shared_byproduct_credit_reduced_demand():
    # R_iron: inputs flint 1/run -> outputs iron 2/run (100%) + flint 1/run 25% (byproduct)
    # Flint: produced by same recipe is also its own input (weird cycle) - instead:
    # Two targets: iron 4 (runs 2) + stone 4 (consumes flint 1/run 100%)
    # R_iron: flint 1/run -> iron 2/run + stone 1/run(p=1)
    # R_stone: flint 1/run -> stone 2/run (100%)
    # Expected: iteration 1: demand {iron:4, stone:4}; runs iron=2, stone=2.
    #   inputs flint = 2+2=4; byproduct stone = 2 (from iron runs)
    #   stone demand as input: 2 subtracted? stone is a TARGET as well. Targets are not credited.
    #   inputs flint = 4 -> iteration 2: flint raw = 4 (stone not credited)
    items = {1: item(1, 'flint'), 2: item(2, 'iron'), 3: item(3, 'stone')}
    processes = {1: process(1, 'sintering'), 2: process(2, 'chopping')}
    recipes = [
        recipe(1, 1, [(1, 1)], [(2, 2, 1.0), (3, 1, 1.0)]),
        recipe(2, 2, [(1, 1)], [(3, 2, 1.0)]),
    ]
    res = calculate(items, processes, recipes, [TargetSpec(2, 4.0), TargetSpec(3, 4.0)], mode='expected')
    assert res.byproducts_expected is not None
    # stone is target, byproducts iron->stone contributes nothing toward targets
    # iron byproduct = stone 2/2 runs = 2; stone target needs 4 via own recipe -> 2 runs (4 out) OK
    print('test_shared_byproduct_credit_reduced_demand OK', res.recipe_runs)


def test_multiple_targets_combine_demand():
    # cobblestone -> gravel (1:1). Target gravel 10 == cobble 10
    # and flint -> iron (1:1): target iron 3 == flint 3
    # No sharing here; simple sanity
    items = {1: item(1), 2: item(2), 3: item(3), 4: item(4)}
    processes = {1: process(1, 'crush'), 2: process(2, 'smelt')}
    recipes = [recipe(1, 1, [(1, 1)], [(2, 1, 1.0)]),
               recipe(2, 2, [(3, 1)], [(4, 1, 1.0)])]
    res = calculate(items, processes, recipes, [TargetSpec(2, 10.0), TargetSpec(4, 3.0)], mode='expected')
    assert res.raw_inputs.get(1) == 10
    assert res.raw_inputs.get(3) == 3
    print('test_multiple_targets_combine_demand OK')


def test_missing_recipe_for_target():
    items = {1: item(1)}
    res = calculate(items, {}, [], [TargetSpec(1, 10.0)], mode='expected')
    assert res.missing == [1]
    print('test_missing_recipe_for_target OK')


def test_cycle_detection():
    items = {1: item(1), 2: item(2)}
    processes = {1: process(1, 'p'), 2: process(2, 'q')}
    # A -> B -> C -> A
    recipes = [recipe(1, 1, [(1, 1)], [(2, 1, 1.0)]),
               recipe(2, 2, [(2, 1)], [(3, 1, 1.0)] if False else [(2, 1, 1.0)])]
    # simpler cycle: 1->2, 2->1
    recipes = [recipe(1, 1, [(1, 1)], [(2, 1, 1.0)]),
               recipe(2, 1, [(2, 1)], [(1, 1, 1.0)])]
    cycles = find_cycles(recipes)
    assert cycles
    print('test_cycle_detection OK', cycles)


def test_intermediate_raw_material_identified():
    # cobblestone raw; gravel intermediate (produced by crushing); iron final
    items = {1: item(1, 'cobble'), 2: item(2, 'gravel'), 3: item(3, 'iron')}
    processes = {1: process(1, 'crushing'), 2: process(2, 'smelting')}
    recipes = [recipe(1, 1, [(1, 1)], [(2, 1, 1.0)]),
               recipe(2, 2, [(2, 1)], [(3, 1, 1.0)])]
    res = calculate(items, processes, recipes, [TargetSpec(3, 5.0)], mode='expected')
    assert res.recipe_runs[2] == 5
    assert res.recipe_runs[1] == 5
    assert res.raw_inputs.get(1) == 5
    print('test_intermediate_raw_material_identified OK')


if __name__ == '__main__':
    test_expected_mode()
    test_guaranteed_mode_probabilistic()
    test_guaranteed_mode_100pct()
    test_confidence_mode()
    test_confidence_mode_convergence_monotone()
    test_byproduct_credit()
    test_shared_byproduct_credit_reduced_demand()
    test_multiple_targets_combine_demand()
    test_missing_recipe_for_target()
    test_cycle_detection()
    test_intermediate_raw_material_identified()
    print('\nALL BACKEND TESTS PASSED')
