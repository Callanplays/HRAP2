from __future__ import annotations

import pytest

from hrap.advanced.geometry import star_vertices
from hrap.io.config import bundled_motor, resolve
from hrap.engine.sim import run


def test_star_vertices_closed():
    v = star_vertices(0.01, 0.02, 6)
    assert v.shape == (12, 2)


def test_star_grain_does_not_crash():
    cfg = bundled_motor("example_98mm")
    cfg.update(reg_model="Shifting OF", prop_a=0.198, prop_n=0.325, prop_m=0.0)
    cfg["advanced"] = {"enabled": True, "ox_fluid": "N2O_legacy", "grain_shape": "star", "star_tips": 6}
    s, x = resolve(cfg)
    assert s.grain_fn is not None
    _x, o = run(s, x)
    assert o.t.size > 10
    assert o.sim_end_cond


@pytest.mark.parametrize("failure", ["invalid", "exception", "nonfinite", "negative"])
def test_live_chemistry_does_not_replace_solver_failure_with_fixed_values(monkeypatch, failure):
    from hrap.advanced.chem import ChemSolver, live_propellant_tables

    def fail(*args):
        if failure == "exception":
            raise RuntimeError("solver failed")
        return ChemSolver.Result(
            valid=failure != "invalid",
            T=float("nan") if failure == "nonfinite" else 2400.0,
            M=-1.0 if failure == "negative" else 25.0,
            gamma=1.2,
        )

    monkeypatch.setattr(ChemSolver, "solve", fail)
    with pytest.raises(ValueError, match="Live chemistry.*ABS.*O/F=.*pressure="):
        live_propellant_tables("ABS")


@pytest.mark.parametrize("ident,formula", [("HTPB_Paraffin", "50P"), ("Metalized_Plastisol", "MPLAST"), (" ABS ", "ABS")])
@pytest.mark.parametrize("as_propellant", [False, True])
def test_live_chemistry_selects_exact_recipe(monkeypatch, ident, formula, as_propellant):
    from hrap.advanced.chem import ChemSolver, live_propellant_tables
    from hrap.io.propellant import load_propellant

    supplies = []

    def solve(self, pressure, supply):
        supplies.append(supply)
        return ChemSolver.Result(valid=True, T=2400.0, gamma=1.2, M=25.0)

    monkeypatch.setattr(ChemSolver, "solve", solve)
    result = live_propellant_tables(load_propellant(ident) if as_propellant else ident)
    assert supplies and all(set(supply) == {"N2O", formula} for supply in supplies)
    assert (result.T == 2400.0).all()


def test_live_chemistry_rejects_unknown_fuel_instead_of_using_abs():
    from dataclasses import replace
    from hrap.advanced.chem import live_propellant_tables
    from hrap.io.propellant import load_propellant

    unknown = replace(load_propellant("ABS"), name="Unspecified fuel")
    with pytest.raises(ValueError, match="No live chemistry recipe"):
        live_propellant_tables(unknown)
