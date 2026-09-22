"""Regenerate neutral-gas equilibrium references with Cantera, not HRAP's solver.

Run from the repo root after installing the optional verification dependency:
    python -m pip install cantera==3.2.0
    python scripts/make_chemistry_reference.py

Both methods use the same bundled NASA9 data, gas species, inlet conditions,
atomic weights, reference pressure and frozen-composition heat capacities.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cantera as ct
import numpy as np
from scipy.optimize import linprog

from hrap.advanced.chem import ChemSolver, FUEL_RECIPES, Rhat, _thermo_path

CASES = [
    ("ABS", 1.0, 5e5), ("HDPE", 1.5, 5e5), ("HTPB", 0.5, 5e5),
    ("Paraffin", 1.0, 5e5), ("HTPB_Paraffin", 1.0, 5e5),
    ("Asphalt", 1.0, 5e5), ("Sorbitol", 1.0, 5e5), ("Metalized_Plastisol", 1.0, 5e5),
    ("ABS", 6.0, 3e6), ("HDPE", 0.87 / 0.13, 3e6),
    ("Paraffin", 10.0, 1e7), ("Asphalt", 6.0, 1e5),
]


def reference(fuel, of, pressure, database):
    recipe = FUEL_RECIPES[fuel]
    oxidizer = database["N2O"]
    elements = sorted(set(recipe["composition"]) | set(oxidizer.composition))
    products = [s for s in database.values() if s.is_product and not s.condensed
                and not s.composition.get("E", 0) and set(s.composition) <= set(elements)]
    mechanism = {
        "elements": [{"symbol": e, "atomic-weight": database[e].M} for e in elements],
        "phases": [{"name": "gas", "thermo": "ideal-gas", "elements": elements, "species": "all"}],
        "species": [{
            "name": s.formula, "composition": s.composition,
            "thermo": {"model": "NASA9", "reference-pressure": 100000.0,
                       "temperature-ranges": [s.T_min, *[p.T_max for p in s.providers]],
                       "data": [p.coeffs.tolist() for p in s.providers]},
        } for s in products],
    }
    gas = ct.Solution(yaml=json.dumps(mechanism))
    fuel_mass = sum(database[e].M * n for e, n in recipe["composition"].items())
    fuel_mols, oxidizer_mols = 1 / (1 + of) / fuel_mass, of / (1 + of) / oxidizer.M
    atoms = np.array([[s.composition.get(e, 0.0) for e in elements] for s in products])
    budget = np.array([fuel_mols * recipe["composition"].get(e, 0.0)
                       + oxidizer_mols * oxidizer.composition.get(e, 0.0) for e in elements])
    # Start independently from a feasible, low-enthalpy mixture, not HRAP's result.
    gas.TP = 1000.0, pressure
    initial = linprog(gas.standard_enthalpies_RT, A_eq=atoms.T, b_eq=budget,
                      bounds=(0, None), method="highs")
    if not initial.success:
        raise RuntimeError(initial.message)
    gas.TPX = 3000.0, pressure, initial.x
    oxidizer_thermo = gas.species("N2O").thermo
    inlet_h = (oxidizer_mols * oxidizer_thermo.h(oxidizer.T_min)
               + fuel_mols * recipe["h0"] * ct.gas_constant / Rhat)
    gas.HP = inlet_h, pressure
    gas.equilibrate("HP", solver="gibbs", rtol=1e-10, max_steps=3000)
    return {
        "fuel": fuel, "OF": of, "pressure": pressure,
        "oxidizer_inlet_K": oxidizer.T_min, "fuel_inlet_K": 298.15,
        "T": gas.T, "M": gas.mean_molecular_weight,
        "Cp": gas.cp_mass * Rhat / ct.gas_constant, "gamma": gas.cp_mass / gas.cv_mass,
        "mole_fractions": {name: float(x) for name, x in zip(gas.species_names, gas.X) if x > 1e-10},
    }


def main():
    database = ChemSolver(_thermo_path()).substances  # parser only; never call solve()
    cases = [reference(*case, database) for case in CASES]
    output = Path(__file__).resolve().parents[1] / "tests/fixtures/chemistry_cantera.json"
    output.write_text(json.dumps({
        "cantera_version": ct.__version__,
        "thermo_sha256": hashlib.sha256(_thermo_path().read_bytes()).hexdigest(),
        "model": "neutral ideal gases, HP equilibrium, frozen Cp/Cv, standard pressure 100000 Pa",
        "gas_constant_J_per_kmol_K": Rhat,
        "cases": cases,
    }, indent=2) + "\n")
    print(f"Wrote {len(cases)} independent Cantera cases to {output}")


if __name__ == "__main__":
    main()
