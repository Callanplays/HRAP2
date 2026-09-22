"""Optional live chemistry (advanced mode, not MATLAB-identical).

Neutral ideal-gas equilibrium using element potentials and atom/enthalpy balances.
Default HRAP still uses frozen MATLAB ``.mat`` / JSON tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, TypedDict

import numpy as np
from scipy.optimize import least_squares
from scipy.special import logsumexp

from hrap.engine.types import Propellant
from hrap.io.propellant import load_propellant

Rhat = 8314.0  # J/(K*kmol), same as the JAX ChemSolver
REFERENCE_PRESSURE = 100000.0  # NASA9 standard-state pressure, Pa
EQUILIBRIUM_TOL = 1e-8


class FuelRecipe(TypedDict):
    formula: str
    composition: dict[str, float]
    h0: float


FUEL_RECIPES: dict[str, FuelRecipe] = {
    "ABS": FuelRecipe(formula="ABS", composition={"C": 8.0, "H": 8.0, "N": 1.0}, h0=147.0e6),
    "HDPE": FuelRecipe(formula="HDPE", composition={"C": 2.0, "H": 4.0}, h0=-52.0e6),
    "HTPB": FuelRecipe(formula="HTPB", composition={"C": 7.22, "H": 10.86, "O": 0.17}, h0=-12.0e6),
    "Paraffin": FuelRecipe(formula="PARAFFIN", composition={"C": 32.0, "H": 66.0}, h0=-930.0e6),
    "HTPB_Paraffin": FuelRecipe(formula="50P", composition={"C": 20.0, "H": 38.0, "O": 0.1}, h0=-400.0e6),
    "Asphalt": FuelRecipe(formula="ASPHALT", composition={"C": 10.0, "H": 12.0, "S": 0.2}, h0=50.0e6),
    "Sorbitol": FuelRecipe(formula="SORBITOL", composition={"C": 6.0, "H": 14.0, "O": 6.0}, h0=-1335.0e6),
    "Metalized_Plastisol": FuelRecipe(formula="MPLAST", composition={"C": 4.0, "H": 6.0, "O": 1.0, "AL": 1.0}, h0=-150.0e6),
}


@dataclass
class NASA9:
    T_min: float
    T_max: float
    DeltaHForm: float
    coeffs: np.ndarray

    def get_Cp_D(self, T: float) -> float:
        c = self.coeffs
        return c[0] / (T * T) + c[1] / T + c[2] + c[3] * T + c[4] * T * T + c[5] * T ** 3 + c[6] * T ** 4

    def get_H_D(self, T: float) -> float:
        c = self.coeffs
        return (
            -c[0] / (T * T)
            + c[1] / T * np.log(T)
            + c[2]
            + c[3] * T / 2.0
            + c[4] * T * T / 3.0
            + c[5] * T ** 3 / 4.0
            + c[6] * T ** 4 / 5.0
            + c[7] / T
        )

    def get_S_D(self, T: float) -> float:
        c = self.coeffs
        return (
            -c[0] / (2.0 * T * T)
            - c[1] / T
            + c[2] * np.log(T)
            + c[3] * T
            + c[4] * T * T / 2.0
            + c[5] * T ** 3 / 3.0
            + c[6] * T ** 4 / 4.0
            + c[8]
        )


@dataclass
class ThermoSubstance:
    formula: str
    comment: str
    condensed: bool
    is_product: bool
    composition: Dict[str, float]
    M: float
    providers: list
    T_min: float
    T_max: float

    def get_prov(self, T: float) -> NASA9:
        i = 0
        for j in range(1, len(self.providers)):
            if T > self.providers[j].T_min:
                i = j
        return self.providers[i]

    def get_H_D(self, T: float) -> float:
        return self.get_prov(T).get_H_D(T)


def make_basic_reactant(formula: str, composition: dict, M: float, T0: float, h0: float, condensed=True) -> ThermoSubstance:
    """h0 is J/kmol at T0."""
    coeffs = np.zeros(9)
    coeffs[2] = h0 / Rhat / T0
    return ThermoSubstance(
        formula,
        "",
        condensed,
        False,
        {k.upper(): float(v) for k, v in composition.items()},
        M,
        [NASA9(T0, T0, h0, coeffs)],
        T0,
        T0,
    )


def _thermo_path() -> Path:
    p = Path(__file__).resolve().parents[1] / "resources" / "thermo.dat"
    if p.exists():
        return p
    return Path(__file__).resolve().parents[3] / "HRAP - Python" / "hrap" / "thermo.dat"


def _props_at(T_bounds: np.ndarray, coeffs: np.ndarray, T: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """NASA9 Cp/R, H/RT and S/R, selecting each species' temperature interval."""
    indices = np.maximum(0, np.sum(T > T_bounds, axis=1) - 1)
    c = coeffs[np.arange(coeffs.shape[0]), indices].T
    cp = c[0] / T**2 + c[1] / T + c[2] + c[3]*T + c[4]*T**2 + c[5]*T**3 + c[6]*T**4
    h = (-c[0] / T**2 + c[1]*np.log(T) / T + c[2] + c[3]*T/2
         + c[4]*T**2/3 + c[5]*T**3/4 + c[6]*T**4/5 + c[7]/T)
    entropy = (-c[0] / (2*T**2) - c[1]/T + c[2]*np.log(T) + c[3]*T
               + c[4]*T**2/2 + c[5]*T**3/3 + c[6]*T**4/4 + c[8])
    return cp, h, entropy


class ChemSolver:
    """Constant-enthalpy/pressure equilibrium of neutral ideal gases.

    Condensed products and ionization are not modeled. Optional product_allow
    restricts products explicitly; by default all compatible neutral gases are used.
    """

    def __init__(self, chem_infos, product_allow=None):
        self.substances: Dict[str, ThermoSubstance] = {}
        self.product_allow = frozenset(product_allow) if product_allow is not None else None
        if not isinstance(chem_infos, (list, tuple)):
            chem_infos = [chem_infos]
        for chem_info in chem_infos:
            if isinstance(chem_info, (str, Path)):
                for k, v in self.load_propep(chem_info).items():
                    self.substances.setdefault(k, v)
            elif isinstance(chem_info, ThermoSubstance):
                self.substances.setdefault(chem_info.formula, chem_info)

    def load_propep(self, chem_path) -> dict:
        substances = {}
        path = Path(chem_path)
        with path.open("r", encoding="utf-8", errors="replace") as chem_file:

            def readline():
                line = chem_file.readline().rstrip("\n")
                while line is not None and (len(line.strip(" ")) == 0 or (line and line[0] == "!")):
                    line = chem_file.readline().rstrip("\n")
                    if line == "":
                        return line
                return line

            line = readline()
            in_reactants = False
            while line:
                if line.startswith("thermo"):
                    chem_file.readline()
                elif line.startswith("END PRODUCTS"):
                    in_reactants = True
                elif line.startswith("END REACTANTS"):
                    break
                else:
                    formula = line[0:18].strip(" ")
                    comment = line[18:].strip(" ") if len(line) > 18 else ""
                    line = readline()
                    i = 0
                    fit_pieces = int(line[i : i + 2].strip(" ") or "0")
                    i += 10
                    composition = {}
                    for _ in range(5):
                        symbol = line[i : i + 2].strip(" ").upper()
                        i += 2
                        quantity = float(line[i : i + 6].strip(" ") or "0")
                        i += 6
                        if symbol:
                            composition[symbol] = quantity
                    phase = int(line[i : i + 2].strip(" ") or "0")
                    i += 2
                    condensed = phase != 0
                    M = float(line[i : i + 13].strip(" "))
                    i += 13
                    DeltaHForm = 1e3 * float(line[i : i + 15].strip(" "))
                    line = readline()
                    providers = []
                    if fit_pieces == 0:
                        T = float(line[0:11].strip(" "))
                        providers.append(NASA9(T, T, DeltaHForm, np.array([0.0] * 2 + [DeltaHForm / Rhat / T] + [0.0] * 6)))
                    else:
                        for j in range(fit_pieces):
                            i = 0
                            T_min = float(line[i : i + 11].strip(" "))
                            i += 11
                            T_max = float(line[i : i + 11].strip(" "))
                            i += 11
                            ncoffs = int(line[i : i + 1].strip(" ") or "0")
                            i += 1
                            i += 8 * 5
                            coeffs = np.zeros(9)
                            m = 0
                            line = readline()
                            ii = 0
                            for _ in range(5):
                                coeff = line[ii : ii + 16].strip(" ")
                                ii += 16
                                if coeff:
                                    coeffs[m] = float(coeff.replace("D", "E"))
                                    m += 1
                            line = readline()
                            ii = 0
                            for _ in range(2):
                                coeff = line[ii : ii + 16].strip(" ")
                                ii += 16
                                if coeff:
                                    coeffs[m] = float(coeff.replace("D", "E"))
                                    m += 1
                            ii += 16
                            for k in range(2):
                                coeff = line[ii : ii + 16].strip(" ")
                                ii += 16
                                if coeff:
                                    coeffs[7 + k] = float(coeff.replace("D", "E"))
                            providers.append(NASA9(T_min, T_max, DeltaHForm, coeffs))
                            if j != fit_pieces - 1:
                                line = readline()
                    T_min = min(p.T_min for p in providers)
                    T_max = max(p.T_max for p in providers)
                    substances[formula] = ThermoSubstance(
                        formula, comment, condensed, not in_reactants, composition, M, providers, T_min, T_max
                    )
                line = readline()
        return substances

    @dataclass
    class Result:
        T: float = 0.0
        Cp: float = 0.0
        Cv: float = 0.0
        gamma: float = 1.2
        M: float = 20.0
        R: float = 287.0
        valid: bool = False
        iters: int = 0
        reason: str = ""
        composition: dict[str, float] = field(default_factory=dict)  # mole fractions
        element_error: float = float("inf")
        energy_error: float = float("inf")
        equilibrium_error: float = float("inf")
        mass_error: float = float("inf")

    def solve(self, Pc: float, supply: dict, max_iters: int = 500) -> Result:
        """Solve for gas composition and temperature; accept by balance residuals.

        Supply values are mass amounts, or (mass amount, inlet temperature).
        Scalar amounts retain the inherited inlet convention: each reactant's
        minimum tabulated temperature. Amounts are normalized to a 1 kg feed.
        """
        if not np.isfinite(Pc) or Pc <= 0 or not supply or max_iters < 1:
            raise ValueError("Chemistry needs positive finite pressure, reactants and an iteration budget.")
        feeds = []
        for name, value in supply.items():
            sub = self.substances[name]
            amount, temperature = value if isinstance(value, (tuple, list)) else (value, sub.T_min)
            amount, temperature = float(amount), float(temperature)
            if not np.isfinite([amount, temperature]).all() or amount < 0 or temperature <= 0:
                raise ValueError(f"Invalid mass or inlet temperature for {name}.")
            if sub.composition.get("E", 0):
                raise ValueError("Charged reactants require an ionized equilibrium model.")
            if not sub.T_min <= temperature <= sub.T_max:
                raise ValueError(f"Inlet temperature for {name} is outside its thermodynamic data.")
            if amount > 0:
                feeds.append((sub, amount, temperature))
        total_mass = sum(amount for _, amount, _ in feeds)
        if total_mass <= 0:
            raise ValueError("At least one reactant must have positive mass.")
        elements = sorted({e for sub, _, _ in feeds for e, v in sub.composition.items() if v})
        if self.product_allow is not None:
            for name in self.product_allow:
                sub = self.substances[name]
                if sub.condensed or sub.composition.get("E", 0):
                    raise ValueError(f"Product {name} is not a neutral gas; that phase/charge model is unsupported.")
        gases = [sub for sub in self.substances.values()
                 if sub.is_product and not sub.condensed and not sub.composition.get("E", 0)
                 and (self.product_allow is None or sub.formula in self.product_allow)
                 and all(e in elements for e, v in sub.composition.items() if v)]
        if not gases:
            raise ValueError("No compatible neutral gas products in the thermodynamic data.")
        atoms = np.array([[sub.composition.get(e, 0.0) for e in elements] for sub in gases])
        missing = [e for i, e in enumerate(elements) if not np.any(atoms[:, i])]
        if missing:
            raise ValueError(f"Selected products cannot conserve these elements: {', '.join(missing)}.")
        lower_T = max(sub.T_min for sub in gases)
        upper_T = min(sub.T_max for sub in gases)
        if lower_T >= upper_T:
            raise ValueError("Selected products have no shared thermodynamic temperature range.")
        n_curves = max(len(sub.providers) for sub in gases)
        bounds = np.full((len(gases), n_curves), np.inf)
        coeffs = np.zeros((len(gases), n_curves, 9))
        for i, sub in enumerate(gases):
            for j, curve in enumerate(sub.providers):
                bounds[i, j] = curve.T_min
                coeffs[i, j] = curve.coeffs
        budget = np.zeros(len(elements))
        inlet_h = 0.0
        for sub, amount, temperature in feeds:
            mols = amount / total_mass / sub.M
            budget += mols * np.array([sub.composition.get(e, 0.0) for e in elements])
            inlet_h += mols * sub.get_H_D(temperature) * Rhat * temperature
        atom_total = float(budget.sum())

        def state(z):
            total_mols, temperature = np.exp(z[-2:])
            cp, h, entropy = _props_at(bounds, coeffs, temperature)
            log_y = atoms @ z[:-2] - h + entropy - np.log(Pc / REFERENCE_PRESSURE)
            log_sum = logsumexp(log_y)
            fractions = np.exp(log_y - log_sum)
            return total_mols, temperature, fractions, log_sum, cp, h

        def residual(z):
            total_mols, temperature, fractions, log_sum, _, h = state(z)
            balance = total_mols * (atoms.T @ fractions)
            return np.r_[np.log(balance / budget), log_sum,
                         (total_mols * (fractions @ h) - inlet_h / (Rhat * temperature)) / atom_total]

        # Element potentials make species amounts positive without clipping them.
        T0 = float(np.clip(3000.0, lower_T + 1e-6, upper_T - 1e-6))
        _, h, entropy = _props_at(bounds, coeffs, T0)
        potentials = np.linalg.lstsq(atoms, h - entropy + np.log(Pc / REFERENCE_PRESSURE)
                                    - np.log(len(gases)), rcond=None)[0]
        counts = atoms.sum(axis=1)
        lower_n = atom_total / counts.max() / 2
        upper_n = atom_total / counts.min() * 2
        initial = np.r_[potentials, np.log(np.sqrt(lower_n * upper_n)), np.log(T0)]
        fit = least_squares(
            residual, initial,
            bounds=(np.r_[np.full(len(elements), -np.inf), np.log(lower_n), np.log(lower_T)],
                    np.r_[np.full(len(elements), np.inf), np.log(upper_n), np.log(upper_T)]),
            max_nfev=max_iters, ftol=1e-11, xtol=1e-11, gtol=1e-11,
        )
        # A solver stop flag alone does not establish chemical equilibrium.
        errors = residual(fit.x)
        total_mols, temperature, fractions, _, cp, _ = state(fit.x)
        element_error = float(np.max(np.abs(np.expm1(errors[:-2]))))
        equilibrium_error = float(abs(errors[-2]))
        energy_error = float(abs(errors[-1]))
        molar_mass = float(fractions @ np.array([sub.M for sub in gases]))
        mass_error = float(abs(total_mols * molar_mass - 1.0))
        gas_constant = Rhat / molar_mass
        cp_mass = float(Rhat * (fractions @ cp) / molar_mass)
        cv_mass = cp_mass - gas_constant
        valid = bool(np.isfinite(errors).all() and np.max(np.abs(errors)) <= EQUILIBRIUM_TOL
                     and np.isfinite([temperature, molar_mass, cp_mass, cv_mass]).all()
                     and lower_T <= temperature <= upper_T and molar_mass > 0 and cv_mass > 0
                     and mass_error <= 1e-6)
        return self.Result(
            T=float(temperature), Cp=cp_mass, Cv=cv_mass,
            gamma=cp_mass / cv_mass if cv_mass > 0 else float("nan"),
            M=molar_mass, R=gas_constant, valid=valid, iters=fit.nfev,
            reason="" if valid else (f"Equilibrium residual={np.max(np.abs(errors)):.3g}, "
                                    f"mass error={mass_error:.3g}; {fit.message}"),
            composition={sub.formula: float(y) for sub, y in zip(gases, fractions)},
            element_error=element_error, energy_error=energy_error, equilibrium_error=equilibrium_error,
            mass_error=mass_error,
        )


def blend_tables(ident: str, scale_T: float = 1.0) -> Propellant:
    prop = load_propellant(ident)
    if scale_T != 1.0:
        prop.T = np.asarray(prop.T, dtype=float) * scale_T
    return prop


def build_of_pc_tables(base_ident: str = "ABS") -> Propellant:
    """MATLAB tables remain the high-fidelity default."""
    return load_propellant(base_ident)


def live_propellant_tables(base: str | Propellant, ox_formula: str = "N2O") -> Propellant:
    """Build k, M, T grids from the NumPy Gibbs solver. Not MATLAB-identical."""
    if isinstance(base, str):
        prop = load_propellant(base)
        ident = base
    else:
        prop = base
        ident = prop.name
    normalized = ident.strip().casefold().replace(" ", "_")
    recipe = next((rec for key, rec in FUEL_RECIPES.items()
                   if normalized in (key.casefold(), rec["formula"].casefold())), None)
    if recipe is None:
        raise ValueError(f"No live chemistry recipe for {ident!r}.")
    solver = ChemSolver(_thermo_path())
    # Keep molecular mass consistent with the recipe's atoms, not a separate guess.
    mass = sum(solver.substances[e].M * count for e, count in recipe["composition"].items())
    fuel = make_basic_reactant(recipe["formula"], recipe["composition"], mass, 298.15, recipe["h0"])
    solver.substances[fuel.formula] = fuel
    OF = np.asarray(prop.OF, dtype=float).ravel()
    Pc = np.asarray(prop.Pc, dtype=float).ravel()

    def _thin(arr: np.ndarray, n: int) -> np.ndarray:
        if arr.size <= n:
            return arr
        idx = np.unique(np.round(np.linspace(0, arr.size - 1, n)).astype(int))
        return arr[idx]

    OF = _thin(OF, 8)
    Pc = _thin(Pc, 6)
    k = np.zeros((Pc.size, OF.size))
    M = np.zeros_like(k)
    T = np.zeros_like(k)
    for i, pc in enumerate(Pc):
        for j, of in enumerate(OF):
            m_f = 1.0 / (1.0 + max(of, 1e-6))
            m_o = 1.0 - m_f
            supply = {ox_formula: m_o, fuel.formula: m_f}
            context = f"{ident}, O/F={of:g}, chamber pressure={pc:g} Pa"
            try:
                res = solver.solve(float(pc), supply)
            except Exception as exc:
                raise ValueError(f"Live chemistry failed for {context}: {exc}") from exc
            if (not res.valid or not np.isfinite([res.T, res.gamma, res.M]).all()
                    or res.T <= 0 or res.M <= 0 or res.gamma <= 1):
                raise ValueError(f"Live chemistry did not produce a valid result for {context}: {res.reason}")
            k[i, j] = res.gamma
            M[i, j] = res.M
            T[i, j] = res.T
    return Propellant(
        name=f"{prop.name} (live chem)",
        opt_OF=prop.opt_OF,
        rho=prop.rho,
        reg=prop.reg,
        OF=OF,
        Pc=Pc,
        k=k,
        M=M,
        T=T,
    )
