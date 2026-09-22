# HRAP2 — HCAT's Hybrid Rocket Analysis Program

**The app we develop and run is in [`src/hrap/`](src/hrap/).** It predicts a hybrid motor's burn from tank, injector, fuel-grain, chamber, and nozzle inputs, and displays thrust, pressure, propellant consumption, and mass/center-of-gravity results.

The desktop window is named **HRAP (HCAT Fork) 1.1.0**. Its standard engine translates the original MATLAB HRAP calculation sequence. Advanced fluid, chemistry, and grain options change that model. Agreement with MATLAB is a software check, not a guarantee of agreement with a real firing.

## Run the app

- **Windows:** download the versioned Windows zip from [Releases](https://github.com/sidbanch/HRAP2/releases), unzip it, and run `HRAP.exe`. For a source checkout, double-click `run_hrap.bat`.
- **macOS:** double-click **`run_hrap.command`** in Finder. It uses this checkout's `.venv` and installs missing dependencies. For first-time setup, install Python 3.10+ or `uv`.
- **Other source installations:** use Python 3.10+ in a virtual environment, install this project with `python -m pip install -e .`, then run `python -m hrap`.

Enter the motor settings on the left, press **Run**, and inspect the plots and summary. Save/load motor configurations as JSON, import MATLAB `.mat` motor files, or export results as CSV, RSE (OpenRocket/RockSim), and ENG.

Optional advanced dependencies: `python -m pip install -e ".[advanced]"`.

## Find your way around

| Location | Purpose |
| --- | --- |
| [`src/hrap/gui/`](src/hrap/gui/) | Desktop forms, plots, and motor drawing |
| [`src/hrap/engine/`](src/hrap/engine/) | Standard tank, fuel, combustion, chamber, and nozzle calculations |
| [`src/hrap/io/`](src/hrap/io/) | Configuration loading, unit conversion/initialization, propellant data, and exports |
| [`src/hrap/advanced/`](src/hrap/advanced/) | Additional fluid, chemistry, and grain models |
| [`src/hrap/resources/`](src/hrap/resources/) | Data and example motors shipped with the app |
| [`tests/`](tests/) | Automated checks and saved MATLAB comparison traces |
| [`scripts/`](scripts/) | Maintenance tools for converting reference data and regenerating MATLAB traces |
| [`packaging/`](packaging/) | Build the Windows release |
| [`reference/`](reference/) | Inherited MATLAB and Python implementations, kept for comparison and feature research |

When you press Run, `gui/main.py` collects inputs, `io/config.py` prepares the initial state, and `engine/sim.py` advances it through the burn. The GUI displays the recorded results; `io/export.py` writes them to files.

**The reference folders are not alternative entry points for this app.** Upstream's Python implementation also uses the package and command name `hrap`; do not install it in the same environment. See [the reference guide](reference/README.md) for their origin and how to study upstream changes.

## Develop and verify

Start with [the development guide](docs/development.md) for setup, checks, data regeneration, and releases.

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

For a command-line simulation:

```sh
python -m hrap.cli path/to/motor.json -o HRAP_output.csv
```

## Origin and license

HCAT's app is based on [HRAP](https://github.com/rnickel1/HRAP_Source), originally developed by Robert Nickel for the University of Tennessee Rocket Engineering Team. The repository retains reference code from that project; the active app is maintained here in `src/hrap`.

[GNU GPL v3](LICENSE). This fork remains GPL because it is based on the original HRAP sources.
