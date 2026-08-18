"""Propellant table loader (JSON converted from MATLAB .mat files)."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

import numpy as np

from hrap.engine.types import Propellant

_PKG = "hrap.resources.propellants"


def _read_json(name: str) -> dict:
    try:
        ref = resources.files(_PKG).joinpath(name)
        return json.loads(ref.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        path = Path(__file__).resolve().parents[1] / "resources" / "propellants" / name
        return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def list_propellants() -> list[dict]:
    return _read_json("index.json")


def _to_propellant(data: dict) -> Propellant:
    return Propellant(
        name=data.get("name") or data["id"],
        opt_OF=float(data.get("opt_OF", 0.0)),
        rho=float(data["rho"]),
        reg=np.asarray(data["reg"], dtype=float),
        OF=np.asarray(data["OF"], dtype=float).ravel(),
        Pc=np.asarray(data["Pc"], dtype=float).ravel(),
        k=np.asarray(data["k"], dtype=float),
        M=np.asarray(data["M"], dtype=float),
        T=np.asarray(data["T"], dtype=float),
    )


@lru_cache(maxsize=None)
def load_propellant(ident: str) -> Propellant:
    ident = ident.strip()
    # Try id (filename stem)
    try:
        return _to_propellant(_read_json(f"{ident}.json"))
    except FileNotFoundError:
        pass
    for item in list_propellants():
        if item["id"].lower() == ident.lower() or item["name"].lower() == ident.lower():
            return _to_propellant(_read_json(f"{item['id']}.json"))
    raise FileNotFoundError(f"Unknown propellant {ident!r}")
