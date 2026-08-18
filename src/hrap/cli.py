from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def compare_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare an HRAP JSON motor to a MATLAB/CSV golden trace.")
    parser.add_argument("motor", type=Path, help="Motor JSON (or MATLAB .mat)")
    parser.add_argument("csv", type=Path, help="Golden CSV with columns t,F_thr,P_tnk,P_cmbr,...")
    parser.add_argument("--dt-tol", type=float, default=1e-8)
    args = parser.parse_args(argv)

    from hrap.engine.sim import run
    from hrap.io.config import load_json, load_matlab_mat, resolve

    if args.motor.suffix.lower() == ".mat":
        cfg = load_matlab_mat(args.motor)
    else:
        cfg = load_json(args.motor)
    s, x = resolve(cfg)
    _x, o = run(s, x)

    gold = np.genfromtxt(args.csv, delimiter=",", names=True)
    mapping = {
        "t": o.t,
        "F_thr": o.F_thr,
        "P_tnk": o.P_tnk,
        "P_cmbr": o.P_cmbr,
        "mdot_o": o.mdot_o,
        "mdot_f": o.mdot_f,
        "OF": o.OF,
        "grn_ID": o.grn_ID,
        "m_o": o.m_o,
        "m_f": o.m_f,
    }
    n = min(o.t.size, gold.shape[0] if gold.dtype.names is None else gold.size)
    print(f"python n={o.t.size}  golden n={gold.size if gold.dtype.names else gold.shape[0]}  end={o.sim_end_cond}")
    max_rel = 0.0
    for name, arr in mapping.items():
        if gold.dtype.names and name not in gold.dtype.names:
            continue
        g = gold[name][:n] if gold.dtype.names else None
        if g is None:
            continue
        a = arr[:n]
        denom = np.maximum(np.abs(g), 1e-30)
        rel = np.max(np.abs(a - g) / denom)
        abserr = np.max(np.abs(a - g))
        max_rel = max(max_rel, float(rel))
        print(f"  {name:8s}  max_rel={rel:.3e}  max_abs={abserr:.3e}")
    ok = max_rel <= args.dt_tol
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def run_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HRAP from a motor JSON and write CSV.")
    parser.add_argument("motor", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("HRAP_output.csv"))
    args = parser.parse_args(argv)
    from hrap.engine.sim import run
    from hrap.engine.summary import format_summary, summarize
    from hrap.io.config import load_json, load_matlab_mat, resolve
    from hrap.io.export import export_csv

    cfg = load_matlab_mat(args.motor) if args.motor.suffix.lower() == ".mat" else load_json(args.motor)
    s, x = resolve(cfg)
    x, o = run(s, x)
    export_csv(args.output, o, s)
    print(format_summary(summarize(s, x, o)))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(run_main())
