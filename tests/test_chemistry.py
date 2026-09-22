"""Equilibrium checks against independent Cantera results and failure cases."""
import json
from pathlib import Path

import numpy as np
import pytest

from hrap.advanced.chem import (
    ChemSolver, EQUILIBRIUM_TOL, FUEL_RECIPES, _thermo_path,
    live_propellant_tables, make_basic_reactant,
)

REFERENCE = json.loads((Path(__file__).parent / 'fixtures/chemistry_cantera.json').read_text())


def fuel_solver(name, product_allow=None):
    solver = ChemSolver(_thermo_path(), product_allow=product_allow)
    recipe = FUEL_RECIPES[name]
    mass = sum(solver.substances[e].M * count for e, count in recipe['composition'].items())
    fuel = make_basic_reactant(recipe['formula'], recipe['composition'], mass, 298.15, recipe['h0'])
    solver.substances[fuel.formula] = fuel
    return solver, fuel


@pytest.mark.parametrize('case', REFERENCE['cases'], ids=lambda c: f"{c['fuel']}-{c['OF']:g}-{c['pressure']:g}")
def test_equilibrium_matches_cantera(case):
    solver, fuel = fuel_solver(case['fuel'])
    of = case['OF']
    result = solver.solve(case['pressure'], {
        'N2O': (of / (1 + of), case['oxidizer_inlet_K']),
        fuel.formula: (1 / (1 + of), case['fuel_inlet_K']),
    })
    assert result.valid, result.reason
    assert max(result.element_error, result.energy_error, result.equilibrium_error) < 2 * EQUILIBRIUM_TOL
    assert result.mass_error < 1e-6
    assert result.T == pytest.approx(case['T'], abs=0.01)
    for field in ['M', 'Cp', 'gamma']:
        assert getattr(result, field) == pytest.approx(case[field], rel=1e-6)
    for name, fraction in result.composition.items():
        assert fraction == pytest.approx(case['mole_fractions'].get(name, 0), abs=1e-7)
    assert sum(result.composition.values()) == pytest.approx(1.0)


@pytest.mark.parametrize('fuel', list(FUEL_RECIPES))
def test_complete_live_tables_converge(fuel):
    table = live_propellant_tables(fuel)
    assert table.T.shape == table.M.shape == table.k.shape == (6, 8)
    assert np.isfinite(table.T).all() and (table.T > 0).all()
    assert np.isfinite(table.M).all() and (table.M > 0).all()
    assert np.isfinite(table.k).all() and (table.k > 1).all()


def test_dependent_element_balances_allow_pure_steam():
    solver = ChemSolver(_thermo_path(), product_allow=['H2O'])
    result = solver.solve(1e5, {'H2O': (1, 1000)})
    assert result.valid, result.reason
    assert result.T == pytest.approx(1000, abs=1e-5)
    assert result.composition['H2O'] == pytest.approx(1)


def test_shortlist_cannot_fake_rich_abs_equilibrium():
    old_products = ['CO2', 'CO', 'H2O', 'H2', 'O2', 'N2', 'OH', 'NO', 'N2O', 'NO2',
                    'H', 'O', 'N', 'C', 'HO2', 'H2O2', 'NH3', 'CH4']
    solver, fuel = fuel_solver('ABS', product_allow=old_products)
    result = solver.solve(5e5, {'N2O': 0.5, fuel.formula: 0.5})
    assert not result.valid
    assert max(result.element_error, result.energy_error, result.equilibrium_error) > EQUILIBRIUM_TOL


def test_iteration_limit_does_not_claim_convergence():
    solver, fuel = fuel_solver('HDPE')
    result = solver.solve(3e6, {'N2O': .87, fuel.formula: .13}, max_iters=1)
    assert not result.valid and result.reason


def test_inconsistent_fuel_mass_is_rejected():
    solver, fuel = fuel_solver('HDPE')
    fuel.M *= 2
    result = solver.solve(3e6, {'N2O': .87, fuel.formula: .13})
    assert not result.valid and result.mass_error > 1e-6


def test_missing_element_products_are_reported():
    solver, fuel = fuel_solver('Asphalt', product_allow=['CO2', 'H2O', 'N2'])
    with pytest.raises(ValueError, match='cannot conserve.*S'):
        solver.solve(5e5, {'N2O': .5, fuel.formula: .5})


def test_charged_products_are_explicitly_unsupported():
    solver = ChemSolver(_thermo_path(), product_allow=['e-', 'H+'])
    with pytest.raises(ValueError, match='not a neutral gas'):
        solver.solve(1e5, {'H2': (1, 1000)})


def test_live_table_preserves_unclipped_solver_properties(monkeypatch):
    monkeypatch.setattr(ChemSolver, 'solve', lambda *args: ChemSolver.Result(
        valid=True, T=5800, M=60, gamma=1.02,
    ))
    table = live_propellant_tables('ABS')
    assert (table.T == 5800).all()
    assert (table.M == 60).all()
    assert (table.k == 1.02).all()


def test_live_chemistry_rejects_oxygen_tank_configuration():
    from hrap.io.config import default_cfg, resolve

    cfg = default_cfg()
    cfg['advanced'] = {'enabled': True, 'live_chem': True, 'ox_fluid': 'Oxygen (CoolProp)'}
    with pytest.raises(ValueError, match='nitrous oxide only'):
        resolve(cfg)
