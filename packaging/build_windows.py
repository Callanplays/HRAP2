"""Build a versioned Windows zip: dist/HRAP-HCAT-Fork-{version}-windows.zip

Bump src/hrap/__init__.py, tag vX.Y.Z, and push the tag. GitHub Actions
runs this script and attaches the zip to the GitHub Release.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hrap import APP_NAME, __version__  # noqa: E402

SPEC = ROOT / "packaging" / "hrap.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "pyinstaller"
APP_DIR = DIST / "HRAP"
ZIP_NAME = f"HRAP-HCAT-Fork-{__version__}-windows.zip"
ZIP_PATH = DIST / ZIP_NAME


def _assert_tag_matches_version() -> None:
    ref = os.environ.get("GITHUB_REF_NAME", "")
    if ref.startswith("v") and ref[1:] != __version__:
        raise SystemExit(f"Git tag {ref} does not match __version__ {__version__}")


def main() -> int:
    _assert_tag_matches_version()
    DIST.mkdir(exist_ok=True)
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--distpath={DIST}",
        f"--workpath={BUILD}",
        str(SPEC),
    ]
    print(" ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)

    if not (APP_DIR / "HRAP.exe").is_file():
        raise SystemExit(f"PyInstaller did not produce {APP_DIR / 'HRAP.exe'}")

    for name in ("LICENSE", "README.md"):
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, APP_DIR / name)
    (APP_DIR / "VERSION.txt").write_text(f"{APP_NAME} {__version__}\n", encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in APP_DIR.rglob("*"):
            if path.is_file():
                zf.write(path, Path("HRAP") / path.relative_to(APP_DIR))

    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1e6:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
