# HRAP (HCAT Fork) 1.1.0

**HRAP (HCAT Fork)** is a desktop Hybrid Rocket Analysis Program. It is a fork of the original MATLAB [HRAP](https://github.com/rnickel1/HRAP_Source) by Robert Nickel (University of Tennessee Rocket Engineering Team).

Version **1.1.0** keeps the MATLAB-parity engine and adds tank / thrust-chamber dry mass, length, and start-station inputs for center-of-mass (used by `.eng` / `.rse` export and the motor schematic). The default ballistics loop is still a line-for-line port of the MATLAB sequential Euler integrator. Optional CoolProp / non-cylindrical grain features are labeled as **not** MATLAB-identical.

## Windows executable

Download the versioned zip from [Releases](https://github.com/sidbanch/HRAP2/releases) (`HRAP-HCAT-Fork-<version>-windows.zip`). Unzip and run `HRAP.exe`. No Python install is required.

Later versions use the same naming: `HRAP-HCAT-Fork-<version>-windows.zip` on the matching GitHub Release.

To cut a new release: bump `__version__` in `src/hrap/__init__.py`, commit, tag `vX.Y.Z`, and push the tag. GitHub Actions builds the Windows zip and attaches it to the release. Local rebuild: `build_exe.bat`.

## Run from source

Requires **Python 3.10+**.

### Windows

Double-click `run_hrap.bat` (or `Run HRAP.bat` in the parent folder). The first launch installs dependencies if needed.

### From a terminal

```
cd HRAP2
python -m pip install -e .
python -m hrap
```

The window title is **HRAP (HCAT Fork) 1.1.0**. Edit the motor on the left, press **Run**, then inspect traces, the scaled motor schematic, and the performance summary on the right.

## Batch / CLI

```
python -m hrap.cli path/to/motor.json -o HRAP_output.csv
hrap-compare path/to/motor.json tests/golden/example_98mm_python.csv
```

Save and load motors as JSON, import original MATLAB `.mat` configs, and export **CSV**, **RSE** (OpenRocket / RockSim), or **ENG**.

## Optional extras

```
python -m pip install -e ".[advanced]"
```

enables CoolProp oxidizers and star-grain geometry. Turning these on in the GUI warns that results will not match original HRAP.

## Tests

```
python -m pip install -e ".[dev]"
python -m pytest
```

Golden traces live in `tests/golden/`. Component tests (NOX, interp2x) and the evaporating-liquid prefix of a full burn match MATLAB to **1e-8**.

To regenerate MATLAB comparison CSVs (R2020b or later; Octave can run the same `.m` core files):

```
cd scripts
python download_assets.py
python convert_assets.py
matlab -batch "make_matlab_golden"
python -m pytest tests -q
```

## Repository layout

| Path | What it is |
| --- | --- |
| `src/hrap/` | Default Python engine + PySide6 GUI |
| `tests/` | Unit tests and golden CSV traces |
| `HRAP - Matlab/` | Frozen original MATLAB sources |
| `HRAP - Python/` | Earlier JAX / Dear PyGui experiment (not the default engine) |

## License

GNU GPL v3. See `LICENSE`. This fork remains GPL because it is based on the original HRAP sources.
