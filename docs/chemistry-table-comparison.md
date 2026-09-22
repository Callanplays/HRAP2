# Why live chemistry differs from the MATLAB tables

Investigation on September 22, 2026. The stored tables were copied correctly. The investigation strongly implicates input assumptions and the gamma convention; the exact historical configuration remains unconfirmed. The live calculation's agreement with Cantera establishes numerical agreement for its chosen assumptions, not reproduction of the historical tables.

## What the original tables contain

The bundled *Theory and Application of the Hybrid Rocket Analysis Program*, page 2, says its combustion tables were generated with **RPA 1.2.9**. MATLAB looks up those results; it does not generate them during a simulation.

All eight current JSON tables exactly match the inherited MATLAB pressure coordinates, O/F coordinates, temperatures, molecular masses and gamma arrays. An independent history inspection also found the ABS arrays unchanged from initial commit `70a89da` (MAT header dated May 29, 2022); the 2024 change updated regression coefficients, not combustion properties.

The repository contains the resulting arrays and a template for pasting new arrays. Neither the MAT records nor inspected repository history contains the original RPA input files specifying the fuel formula, formation enthalpy, oxidizer inlet state, or product-phase selection. The vendor's RPA 1.2.9 distribution contains no ABS record or custom `usr_thermo.inp` file. Exact historical inputs therefore remain unconfirmed.

## Gamma is not the same quantity in each calculation

The current live solver returns **frozen Cp/Cv**: it calculates heat capacities while holding the proportions of the product gases fixed. "Frozen" refers to the composition, not a low temperature.

**Equilibrium Cp/Cv** allows molecules to rearrange as temperature changes. Some added energy changes the chemical composition instead of simply raising temperature, so the heat capacities differ. Later upstream Python explicitly calculates equilibrium Cp/Cv. RPA's theory also distinguishes that ratio from a third quantity, the isentropic exponent used for sound speed. These quantities must not be substituted without checking the consuming equations.

For ABS at O/F = 6 and 30 bar, with the current live inputs:

| Calculation | Gamma |
| --- | ---: |
| Stored table | 1.173700 |
| Current live frozen Cp/Cv | 1.251506 |
| Same live equilibrium state, equilibrium Cp/Cv | 1.176077 |

No fuel or temperature was changed for this comparison. Equilibrium heat capacities were computed with Cantera by centered finite differences, re-equilibrating at constant pressure for Cp and constant volume for Cv. Reducing the relative temperature step from `1e-4` to `1e-5` changes the example ratio by less than `4e-8`.

Across the 48 ABS points used by the live table, mean absolute gamma difference from the stored table falls from **5.40% to 1.53%** with equilibrium Cp/Cv. Some rich-mixture points still differ by **7.40%**. This strongly supports a convention difference as a major cause; it does not establish the exact historical RPA output column.

## The inputs differ too

| Input | Current HRAP2 live mode | Later upstream Python GUI |
| --- | --- | --- |
| ABS elemental recipe | C8 H8 N1 | C3.85 H4.85 N0.43 |
| Fuel formation enthalpy | +147 MJ/kmol | −62.63 MJ/kmol |
| Oxidizer energy input | Gaseous N2O at 200 K | Liquid N2O record at 298.15 K |

Formation enthalpy describes chemical energy relative to standard elemental reference states. It is not the same as heat released by burning a kilogram of fuel. Different formulas also represent different amounts of material per mole, so their molar enthalpies cannot be compared as if they were the same recipe.

The upstream Python recipe first appears in commit `4408b52` in August 2025, after the MATLAB tables. It is evidence of a later modeling choice, not proof of the earlier table inputs. Its negative enthalpy also conflicts with the **positive 62.63 kJ/mol** reported for that formula by Whitmore et al. (2013). The code does not identify its intended source, so copying it blindly would not resolve provenance.

Controlled calculations at O/F = 6 and 30 bar, using the same current neutral-gas database:

| Case | Temperature (K) | Molecular mass (g/mol) | Equilibrium Cp/Cv |
| --- | ---: | ---: | ---: |
| Stored table | 3284.622 | 27.0881 | 1.173700* |
| Current live inputs | 3408.858 | 27.4340 | 1.176077 |
| Change only oxidizer to liquid record | 3344.146 | 27.6449 | 1.173472 |
| Change only fuel to later upstream recipe | 3314.576 | 27.0208 | 1.174213 |
| Change both | 3243.796 | 27.2087 | 1.173190 |

*The historical record calls this specific heat ratio; its exact selected RPA output field is unconfirmed.*

The input changes visibly affect the answer but do not exactly reproduce it. Across all eight fuels, the live-mode recipe constants remain assumptions requiring their own source audit.

## A close reconstruction is evidence, not recovered provenance

As an explicitly labeled sensitivity experiment, use the upstream-like ABS elemental composition, set its formation enthalpy to **zero**, and use liquid nitrous at 298.15 K. With the current database this gives 3288.309 K, molecular mass 27.09294, and equilibrium Cp/Cv 1.173697 at the example point.

Using the vendor's **original RPA 1.2.9 thermodynamic database** for that same experiment gives **3285.406 K**, **27.08596 g/mol**, and **1.173713**. The stored values are 3284.622 K, 27.0881 g/mol and 1.1737.

That close result supports investigating those inputs. It does **not** prove the author used zero formation enthalpy, reproduce the whole table, or establish a physically justified ABS recipe. No zero-enthalpy ABS definition was found in the historical inputs. Neither this value nor the later upstream recipe was installed as a new default.

## Reproduce the investigation

The app, solver, default tables and existing reference fixtures are unchanged by this investigation. The diagnostic requires Cantera 3.2.0 separately from the app:

```sh
python scripts/compare_chemistry_tables.py \
  --matlab-dir "HRAP - Matlab/propellant_configs" \
  --output /tmp/chemistry-comparison.json
```

For a reorganized checkout, pass its `reference/matlab/propellant_configs` directory instead. To include the original-database sensitivity experiment, extract `resources/thermo.inp` from the vendor archive and add `--reference-thermo /path/to/thermo.inp`. On macOS, prefix the command with `caffeinate -i`.

[Saved numerical results](chemistry-table-comparison.json) record the Cantera version, database hashes, exact table comparisons, controlled cases and all 48 ABS points. The comparison uses the same gas-only product scope as the repaired solver; it does not resolve effects of condensed products at rich mixtures or for metalized fuels.

The default stored tables remain the source for reproducing MATLAB. A scientifically justified live replacement needs documented input recipes, inlet energy, product phases and a deliberate choice of gas properties for the chamber/nozzle equations. The original RPA project and custom fuel definition, if available from the authors, would settle the historical inputs more directly than tuning to the saved numbers.

## Sources

- Bundled HRAP theory PDF, pp. 2 and 7: RPA version and table-based combustion model.
- `HRAP - Python/hrap/gui/main.py`, ABS and oxidizer definitions; `hrap/chem.py`, equilibrium postprocessing and `Result` fields.
- [RPA 1.2.9 vendor distribution](https://www.rocket-propulsion.com/downloads/1/lite/rpa-1.2.9-lite-win64.zip), original thermodynamic database.
- [RPA theory, equations 32–33](https://www.rocket-propulsion.com/downloads/pub/RPA_LiquidRocketEngineAnalysis_II.pdf), heat-capacity ratio versus isentropic exponent.
- [Whitmore et al., 2013](https://mae-nas.eng.usu.edu/MAE_5540_Web/propulsion_systems/section7/PP_Vol29_No3_May-June_2013.pdf), pp. 584–585 and Table 2: ABS composition and positive formation enthalpy.
- [Cantera sound-speed example](https://cantera.org/stable/examples/python/thermo/sound_speed.html), frozen versus equilibrated response to a thermodynamic perturbation.
