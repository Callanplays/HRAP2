"""Download upstream MATLAB .mlapp, propellant tables, and example motors."""
from __future__ import annotations

import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/rnickel1/HRAP_Source/main"
PROPS = [
    "ABS.mat",
    "Asphalt.mat",
    "HDPE.mat",
    "HTPB.mat",
    "HTPB_Paraffin.mat",
    "Metalized_Plastisol.mat",
    "Paraffin.mat",
    "Sorbitol.mat",
]


def _get(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 100:
        print(f"skip existing {dest}")
        return
    print(f"GET {url}")
    last_err = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HRAP-asset-fetch"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            print(f"  -> {dest} ({dest.stat().st_size} bytes)")
            time.sleep(0.4)
            return
        except Exception as exc:
            last_err = exc
            wait = 2.0 * (attempt + 1)
            print(f"  retry {attempt + 1}/6 after {wait:.0f}s ({exc})")
            time.sleep(wait)
    raise last_err


def main() -> None:
    prop_dir = ROOT / "data" / "propellants" / "mat"
    mtr_dir = ROOT / "data" / "motors" / "mat"
    matlab_dir = ROOT / "HRAP - Matlab"
    gui_dir = ROOT / "data" / "matlab_gui"

    for name in PROPS:
        _get(f"{BASE}/propellant_configs/{name}", prop_dir / name)
        # Also vendor next to the frozen MATLAB tree
        _get(f"{BASE}/propellant_configs/{name}", matlab_dir / "propellant_configs" / name)

    _get(f"{BASE}/HRAP%20-%20Matlab/motor_configs/example_98mm.mat", mtr_dir / "example_98mm.mat")
    _get(f"{BASE}/HRAP%20-%20Matlab/motor_configs/Rattworks_K240.mat", mtr_dir / "Rattworks_K240.mat")
    _get(
        f"{BASE}/HRAP%20-%20Matlab/motor_configs/example_98mm.mat",
        matlab_dir / "motor_configs" / "example_98mm.mat",
    )
    _get(
        f"{BASE}/HRAP%20-%20Matlab/motor_configs/Rattworks_K240.mat",
        matlab_dir / "motor_configs" / "Rattworks_K240.mat",
    )

    mlapp = matlab_dir / "HRAP.mlapp"
    _get(f"{BASE}/HRAP%20-%20Matlab/HRAP.mlapp", mlapp)
    gui_dir.mkdir(parents=True, exist_ok=True)
    (gui_dir / "HRAP.mlapp").write_bytes(mlapp.read_bytes())
    unzip = gui_dir / "unzipped"
    unzip.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(mlapp) as zf:
        zf.extractall(unzip)
    print(f"unzipped {mlapp} -> {unzip}")


if __name__ == "__main__":
    main()
