# Working on HRAP2

Work in `src/hrap` for application changes. Start with `gui/main.py` for the interface, `io/config.py` for input preparation, or `engine/sim.py` for the calculation sequence. Experimental models live in `advanced/`. The inherited implementations under `reference/` are for comparison and research; see [their guide](../reference/README.md).

## Setup and checks

From the repository root, create/activate a Python 3.10+ virtual environment using your platform's usual tools, then:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m hrap
```

The Mac launcher `run_hrap.command` can create `.venv` and install application dependencies. To add the test tools to that environment, use `uv pip install --python .venv/bin/python -e ".[dev]"`, or `.venv/bin/python -m pip install -e ".[dev]"` if that environment has pip. Run its tests with `.venv/bin/python -m pytest`.

On macOS, prefix unattended builds, installs, and full test runs with `caffeinate -i`.

The existing MATLAB tests compare nitrous properties, interpolation, peak thrust, and the early portion of selected burn traces. The strict curve comparisons cover 5 seconds for the 98 mm examples and 3.4 seconds for Rattworks; they do not establish exact full-burn equivalence or physical validation. Missing MATLAB CSV fixtures cause those checks to skip. UI changes also need a native desktop run, and packaging changes need a package/release check.

## Reference data and regeneration

Normal app runs and tests use the checked-in JSON data and CSV fixtures. They do not require a MATLAB installation or downloads.

The source `.mat` files used for regeneration are checked in under `reference/matlab/`. To inspect them or regenerate app JSON, run these commands from the repository root:

```sh
python scripts/inspect_mats.py
python scripts/convert_assets.py
```

Conversion rewrites `src/hrap/resources/propellants` and the example motor JSON files. Review the diff before committing. All propellant inputs are parsed before any existing tables are replaced, so missing or malformed inputs do not erase the current tables. The original network download script has been removed; changing reference inputs is an explicit, reviewed update.

To regenerate the MATLAB reference CSVs with MATLAB R2020b or later, from the repository root:

```sh
matlab -batch "addpath('scripts'); make_matlab_golden"
python -m pytest tests/test_matlab_golden.py
```

`scripts/make_octave_golden.m` is also provided for generating traces with Octave. MATLAB/Octave execution is a separate verification step from comparing against already-saved CSVs. Review regenerated traces and explain differences rather than accepting changed fixtures solely to make a test pass.

## Windows releases

Bump `src/hrap/__init__.py`, tag `vX.Y.Z`, and push the tag. `.github/workflows/release-windows.yml` builds the versioned Windows zip with `packaging/build_windows.py` and attaches it to the release. `build_exe.bat` runs the local Windows build. Historical MATLAB installers are not part of this build pipeline.
