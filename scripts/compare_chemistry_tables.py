"""Investigate stored MATLAB tables versus optional live chemistry assumptions.

Requires Cantera 3.2.0 for this diagnostic only. Does not change app inputs.
Example (from the repository root):
    python scripts/compare_chemistry_tables.py --matlab-dir "HRAP - Matlab/propellant_configs" --output /tmp/chemistry-comparison.json

Cantera uses the same NASA9 data, atomic masses, gas products and reference
pressure as the live solver. Equilibrium Cp/Cv is obtained by centered
finite differences, re-equilibrating at constant pressure/volume respectively.
This is not the isentropic exponent, and is not the frozen Cp/Cv used by HRAP2.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cantera as ct
import numpy as np
from scipy.io import loadmat
from scipy.optimize import linprog

from hrap.advanced.chem import FUEL_RECIPES, ChemSolver, Rhat, _thermo_path
from hrap.io.propellant import load_propellant


def build_gas(database, composition):
    elements = sorted(set(composition) | {"N", "O"})
    products = [
        s
        for s in database.values()
        if s.is_product
        and not s.condensed
        and not s.composition.get("E", 0)
        and set(s.composition) <= set(elements)
    ]
    gas = ct.Solution(
        yaml=json.dumps(
            {
                "elements": [
                    {"symbol": e, "atomic-weight": database[e].M} for e in elements
                ],
                "phases": [
                    {
                        "name": "gas",
                        "thermo": "ideal-gas",
                        "elements": elements,
                        "species": "all",
                    }
                ],
                "species": [
                    {
                        "name": s.formula,
                        "composition": s.composition,
                        "thermo": {
                            "model": "NASA9",
                            "reference-pressure": 100000.0,
                            "temperature-ranges": [
                                s.T_min,
                                *[p.T_max for p in s.providers],
                            ],
                            "data": [p.coeffs.tolist() for p in s.providers],
                        },
                    }
                    for s in products
                ],
            }
        )
    )
    return gas, elements, products


def calculate(database, recipe, ox="N2O", of=6, pressure=3e6, eps=1e-4):
    gas, elements, products = build_gas(database, recipe["composition"])
    fuel_M = sum(database[e].M * n for e, n in recipe["composition"].items())
    ox_M = sum(database[e].M * n for e, n in database[ox].composition.items())
    nf = 1 / (1 + of) / fuel_M
    no = of / (1 + of) / ox_M
    budget = np.array(
        [
            nf * recipe["composition"].get(e, 0)
            + no * database[ox].composition.get(e, 0)
            for e in elements
        ]
    )
    atoms = np.array([[s.composition.get(e, 0) for e in elements] for s in products])
    gas.TP = 1000, pressure
    init = linprog(
        gas.standard_enthalpies_RT,
        A_eq=atoms.T,
        b_eq=budget,
        bounds=(0, None),
        method="highs",
    )
    assert init.success
    gas.TPX = 3000, pressure, init.x
    ox_h = database[ox].get_H_D(database[ox].T_min) * Rhat * database[ox].T_min
    h = (nf * recipe["h0"] + no * ox_h) * ct.gas_constant / Rhat
    gas.HP = h, pressure
    gas.equilibrate("HP", solver="gibbs", rtol=1e-11, max_steps=3000)
    T = gas.T
    P = gas.P
    X = gas.X.copy()
    rho = gas.density
    out = {
        "T": T,
        "M": gas.mean_molecular_weight,
        "gamma_frozen": gas.cp_mass / gas.cv_mass,
        "h_feed_J_kg": h * Rhat / ct.gas_constant,
    }
    hs = []
    us = []
    for sign in [-1, 1]:
        gas.TPX = T * (1 + sign * eps), P, X
        gas.equilibrate("TP", solver="gibbs", rtol=1e-11, max_steps=3000)
        hs.append(gas.enthalpy_mass)
        gas.TPX = T, P, X
        gas.TD = T * (1 + sign * eps), rho
        gas.equilibrate("TV", solver="gibbs", rtol=1e-11, max_steps=3000)
        us.append(gas.int_energy_mass)
    out["gamma_equilibrium_cp_cv"] = (hs[1] - hs[0]) / (us[1] - us[0])
    out["Cp_equilibrium"] = (hs[1] - hs[0]) / (2 * eps * T) * Rhat / ct.gas_constant
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matlab-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--reference-thermo",
        type=Path,
        help="Optional original RPA database, for an explicitly inferred reconstruction",
    )
    args = parser.parse_args()
    database = ChemSolver(_thermo_path()).substances
    matches = {}
    for path in sorted(args.matlab_dir.glob("*.mat")):
        source = loadmat(path, squeeze_me=True, struct_as_record=False)["s"]
        stored = load_propellant(path.stem)
        fields = {
            "OF": "prop_OF",
            "Pc": "prop_Pc",
            "k": "prop_k",
            "M": "prop_M",
            "T": "prop_T",
        }
        matches[path.stem] = {
            field: bool(
                np.array_equal(
                    getattr(stored, field),
                    np.asarray(getattr(source, original)).reshape(
                        getattr(stored, field).shape
                    ),
                )
            )
            for field, original in fields.items()
        }
    if not matches:
        raise ValueError("No MATLAB propellant files found")
    assert all(all(fields.values()) for fields in matches.values()), matches
    stored = load_propellant("ABS")
    i = int(np.flatnonzero(stored.Pc == 3e6)[0])
    j = int(np.flatnonzero(stored.OF == 6)[0])
    upstream = {"composition": {"C": 3.85, "H": 4.85, "N": 0.43}, "h0": -6.263e7}
    scenarios = [
        ("Current live assumptions", FUEL_RECIPES["ABS"], "N2O"),
        (
            "Change only oxidizer to liquid N2O at 298.15 K",
            FUEL_RECIPES["ABS"],
            "N2O(L),298.15K",
        ),
        ("Change only fuel to later upstream Python recipe", upstream, "N2O"),
        (
            "Later upstream Python recipe and liquid oxidizer",
            upstream,
            "N2O(L),298.15K",
        ),
        (
            "Inferred reconstruction: upstream composition, ZERO fuel formation enthalpy, liquid oxidizer",
            {**upstream, "h0": 0.0},
            "N2O(L),298.15K",
        ),
    ]
    cases = []
    for label, recipe, oxidizer in scenarios:
        result = calculate(database, recipe, oxidizer)
        cases.append(
            {"label": label, "fuel_recipe": recipe, "oxidizer": oxidizer, **result}
        )
        print(label, result, flush=True)
    rows = []
    for i_pc in np.unique(np.round(np.linspace(0, stored.Pc.size - 1, 6)).astype(int)):
        for j_of in np.unique(
            np.round(np.linspace(0, stored.OF.size - 1, 8)).astype(int)
        ):
            pc, of = float(stored.Pc[i_pc]), float(stored.OF[j_of])
            result = calculate(database, FUEL_RECIPES["ABS"], of=of, pressure=pc)
            rows.append(
                {
                    "OF": of,
                    "Pc": pc,
                    "stored_T": float(stored.T[i_pc, j_of]),
                    "stored_M": float(stored.M[i_pc, j_of]),
                    "stored_gamma": float(stored.k[i_pc, j_of]),
                    **result,
                }
            )
    errors = {}
    for field, original in [
        ("T", "stored_T"),
        ("M", "stored_M"),
        ("gamma_frozen", "stored_gamma"),
        ("gamma_equilibrium_cp_cv", "stored_gamma"),
    ]:
        delta = np.array([100 * (r[field] / r[original] - 1) for r in rows])
        errors[field] = {
            "mean_absolute_percent": float(abs(delta).mean()),
            "min_signed_percent": float(delta.min()),
            "max_signed_percent": float(delta.max()),
        }
    small_step = calculate(database, FUEL_RECIPES["ABS"], eps=1e-5)
    assert (
        abs(small_step["gamma_equilibrium_cp_cv"] - cases[0]["gamma_equilibrium_cp_cv"])
        < 1e-6
    )
    report = {
        "cantera_version": ct.__version__,
        "thermo_sha256": hashlib.sha256(_thermo_path().read_bytes()).hexdigest(),
        "stored_tables_exact_match": matches,
        "example": {
            "fuel": "ABS",
            "OF": 6,
            "Pc": 3e6,
            "stored": {
                "T": float(stored.T[i, j]),
                "M": float(stored.M[i, j]),
                "gamma": float(stored.k[i, j]),
            },
            "scenarios": cases,
        },
        "derivative_step_check": {"relative_temperature_step": 1e-5, **small_step},
        "ABS_48_point_error_percent": errors,
        "ABS_48_points": rows,
        "caveat": "Historical RPA inputs are missing. Inferred reconstruction is a sensitivity experiment, not recovered provenance or a new default.",
    }
    if args.reference_thermo:
        old_database = ChemSolver(args.reference_thermo).substances
        report["inferred_reconstruction_original_database"] = {
            "thermo_sha256": hashlib.sha256(
                args.reference_thermo.read_bytes()
            ).hexdigest(),
            **calculate(old_database, {**upstream, "h0": 0.0}, "N2O(L),298.15K"),
        }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Wrote", args.output)


if __name__ == "__main__":
    main()
