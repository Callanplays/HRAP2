# Upstream reference implementations

HCAT's active application is [`src/hrap/`](../src/hrap/). These folders preserve material from the original HRAP project so we can compare calculations and evaluate features without treating three implementations as one app.

| Folder | What it is | Why we keep it |
| --- | --- | --- |
| [`matlab/`](matlab/) | Original MATLAB app, equations, motor/propellant configurations, and documentation | Reference for the standard HCAT engine and generation of MATLAB comparison traces |
| [`python/`](python/) | Upstream's separate Python/JAX implementation | Source to study for features such as arbitrary grain cross-sections; not the engine used by HCAT's app |

The MATLAB comparison generator uses `matlab/core`, `matlab/util`, and the top-level files in `matlab/motor_configs` and `matlab/propellant_configs`. The active app loads its own shipped data from `src/hrap/resources`; neither reference application is imported at runtime.

## Provenance

Source repository: [rnickel1/HRAP_Source](https://github.com/rnickel1/HRAP_Source).

Snapshot: [`d9032d7d947caf7569a46394840feef67759c327`](https://github.com/rnickel1/HRAP_Source/tree/d9032d7d947caf7569a46394840feef67759c327), the upstream state inherited before HCAT's Python app was introduced.

| Original path | Location here |
| --- | --- |
| `HRAP - Matlab/` | `reference/matlab/` |
| `HRAP - Python/` | `reference/python/` |
| Root `propellant_configs/` | Duplicate tables/template consolidated into `reference/matlab/propellant_configs/`; unique `read_me.txt` preserved there |
| Packaged `motor_configs/mtr_cfg.mat` | Preserved in `reference/matlab/motor_configs/packaged/` |

The simulation source is unchanged by this organization change. The inherited READMEs have an added notice identifying them as reference material. Generated MATLAB executables, installers, packaging output/logs, and example output CSVs were removed; they remain available in Git history. The MATLAB compiler project contains historical machine-specific paths and is not HCAT's release build system.

The original theory document is retained in [`matlab/sources/`](matlab/sources/). The project remains subject to the root [GPL license](../LICENSE).

## Study or bring over upstream features

1. Fetch the original project into a separate remote:

   ```sh
   git remote add upstream https://github.com/rnickel1/HRAP_Source.git
   git fetch upstream
   ```

   If `upstream` is already configured for that URL, only run the fetch command.

2. Compare upstream changes against the recorded snapshot:

   ```sh
   git diff d9032d7d947caf7569a46394840feef67759c327 upstream/main -- "HRAP - Python" "HRAP - Matlab" propellant_configs
   ```

3. Understand a selected feature's equations, units, assumptions, and update order. Implement it in the appropriate `src/hrap` module and compare its behavior with a documented case. A newer upstream implementation is not automatically equivalent to MATLAB.
4. If updating the reference snapshot, review the changes, update this provenance record, and explicitly regenerate/review any affected app data or MATLAB traces. Fetching upstream does not update the active app or its reference files.

Use a separate virtual environment when experimenting with `reference/python`: it installs the same `hrap` package and command name as HCAT's app. Its inherited instructions describe the upstream application, not HCAT's setup.
