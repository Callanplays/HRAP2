"""Convert upstream MATLAB .mat chemistry tables and motor configs to JSON."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.io

ROOT = Path(__file__).resolve().parents[1]
MAT_PROP = ROOT / "data" / "propellants" / "mat"
MAT_MTR = ROOT / "data" / "motors" / "mat"
OUT_PROP = ROOT / "src" / "hrap" / "resources" / "propellants"
OUT_MTR = ROOT / "src" / "hrap" / "resources" / "motors"


def _arr(x) -> list:
    a = np.asarray(x, dtype=float)
    if a.ndim == 0:
        return [float(a)]
    return a.tolist()


def convert_propellants() -> None:
    OUT_PROP.mkdir(parents=True, exist_ok=True)
    for old in OUT_PROP.glob("*.json"):
        old.unlink()
    index = []
    for path in sorted(MAT_PROP.glob("*.mat")):
        s = scipy.io.loadmat(path, squeeze_me=True, struct_as_record=False)["s"]
        ident = path.stem
        name = str(s.prop_nm)
        payload = {
            "id": ident,
            "name": name,
            "opt_OF": float(getattr(s, "opt_OF", 0.0)),
            "rho": float(s.prop_Rho),
            "reg": [float(v) for v in np.atleast_1d(np.asarray(s.prop_Reg, dtype=float)).ravel()],
            "OF": _arr(s.prop_OF),
            "Pc": _arr(s.prop_Pc),
            "k": np.asarray(s.prop_k, dtype=float).tolist(),
            "M": np.asarray(s.prop_M, dtype=float).tolist(),
            "T": np.asarray(s.prop_T, dtype=float).tolist(),
        }
        out = OUT_PROP / f"{ident}.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        index.append({"id": ident, "name": name})
        print(f"wrote {out}")
    (OUT_PROP / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")


def _jsonify(val):
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, (list, tuple)):
        return [_jsonify(v) for v in val]
    if isinstance(val, dict):
        return {str(k): _jsonify(v) for k, v in val.items()}
    if isinstance(val, np.ndarray):
        if val.dtype.kind in {"U", "S", "O", "V"}:
            if val.size <= 1:
                try:
                    return _jsonify(val.item() if val.ndim == 0 else val.reshape(-1)[0])
                except Exception:
                    return None
            return [_jsonify(v) for v in val.tolist()]
        if val.ndim == 0:
            return _jsonify(val.item())
        return val.tolist()
    if isinstance(val, (np.floating, np.integer, np.bool_)):
        return val.item()
    if isinstance(val, (str, int, float, bool)):
        return val
    name = type(val).__name__
    if name in {"MatlabOpaque", "MatlabFunction", "mat_struct"}:
        return None
    try:
        json.dumps(val)
        return val
    except TypeError:
        return None


def _cfg_to_dict(cfg) -> dict:
    out = {}
    for field in cfg._fieldnames:
        out[field] = _jsonify(getattr(cfg, field))
    if not out.get("prop_file"):
        out["prop_file"] = None
    return out


def convert_motors() -> None:
    OUT_MTR.mkdir(parents=True, exist_ok=True)
    for path in sorted(MAT_MTR.glob("*.mat")):
        cfg = scipy.io.loadmat(path, squeeze_me=True, struct_as_record=False)["cfg"]
        payload = _cfg_to_dict(cfg)
        payload["source"] = "matlab"
        if not payload.get("prop_id"):
            payload["prop_id"] = payload.get("prop_nm") or path.stem
        out = OUT_MTR / f"{path.stem}.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    convert_propellants()
    convert_motors()
