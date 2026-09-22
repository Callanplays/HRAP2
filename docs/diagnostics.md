# Investigation of the editor errors

The September 22, 2026 check found 46 Pyright diagnostics in 11 files in the active `src/hrap` package. This audit covers those diagnostics and the code paths behind them, not every possible defect in HRAP.

## What the diagnostics meant

| Area | Finding and change |
| --- | --- |
| Fuel recipes | Mixed dictionary values hid each field's type from the checker. `FuelRecipe` now declares those fields. |
| CoolProp | The optional package was missing from the development environment. Installed it for verification; explicitly convert its scalar temperature results to floats. |
| Oxidizer properties | `State` allowed missing properties even though `resolve` supplies them and the tank/mass calculations require them. Made this a required field. |
| Simulation output | Mass and CG arrays are always allocated by the simulation, but may be absent in export-only data. The simulation now states that invariant to the checker. |
| Star grain | The regression closure now retains the calculated numeric burnout limit instead of reading a field declared optional. |
| SciPy root solves | The checker inferred a possible tuple return. These calls use the default `full_output=False`, which returns a scalar; their types now state that. Solver arguments and equations are unchanged. |
| GUI | Qt/pyqtgraph exposed broad base types, and the checker could not infer the result/thread lifecycle. Added explicit types at those boundaries and used Qt's dynamic-property API for the saved unit selection. |
| JSON loading | The reader was annotated as always returning a dictionary, although the propellant index is a list. Corrected the annotation. |

No diagnostic rules were disabled. Pyright configuration checks `src/hrap` in standard mode using the repository's `.venv`. It does not check the inherited reference apps.

## Actual behavior bugs found

Live chemistry used to catch solver failures and put fixed values into the resulting table: gamma 1.25, molecular mass 24, temperature 2500 K. A forced failure reproduced this behavior. It now stops with the fuel, mixture ratio and pressure in the error message.

Recipe selection used substring matching, so `HTPB_Paraffin` selected plain HTPB. Passing the display name `Metalized Plastisol` also missed its recipe and fell back to ABS. Matching now accepts exact recipe IDs and names; unsupported fuels raise an error instead of defaulting to ABS.

These bugs concern optional live chemistry, not the default stored MATLAB-derived tables. Regression tests cover invalid results, exceptions, nonfinite results, fuel IDs/display names, and unsupported fuels.

Nonpositive temperature or molecular mass, and gamma at or below one, are also rejected.

## Follow-up chemistry repair

At the time of this diagnostic audit, the solver failed for bundled ABS at O/F 1 and 500000 Pa. The former single-point chemistry test also returned `valid=False` even though its temperature and other values passed broad bounds. That misleading test was replaced by failure-handling and recipe-selection tests.

The subsequent [live-chemistry repair](live-chemistry.md) fixes the equation/species mismatch, replaces the fragile iteration, removes output clipping, and checks results against Cantera. The assumed fuel recipes and gas-only model still limit physical accuracy. A clean type check does not establish agreement with a firing.

## Repeat the checks

After the changes: Pyright reports zero errors and warnings across 35 files; all 100 tests pass, including the saved MATLAB comparisons. Native macOS checks covered a simulation, unit changes, themes, plot hover, RSE export, a live-chemistry error and a successful default run afterward. CoolProp N2O properties and a short simulation were also checked. Windows and fresh MATLAB execution were not tested in this audit.

In the repository's Python environment:

```sh
python -m pip install -e ".[dev,advanced]"
python -m pyright
python -m pytest
```

If using an environment other than `.venv`, pass its Python executable with Pyright's `--pythonpath` option. Prefix unattended commands with `caffeinate -i` on macOS.
