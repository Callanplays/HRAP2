"""Runtime hook so a frozen HRAP window uses a real desktop Qt plugin."""
import os
import sys

if sys.platform == "win32":
    plat = str(os.environ.get("QT_QPA_PLATFORM", "")).lower()
    if plat in {"offscreen", "minimal", "null"} and not os.environ.get("HRAP_OFFSCREEN"):
        os.environ.pop("QT_QPA_PLATFORM", None)
    windir = os.environ.get("WINDIR", r"C:\Windows")
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(windir, "Fonts"))
