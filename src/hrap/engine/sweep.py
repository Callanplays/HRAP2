"""Nozzle throat × injector Cd sweep, for sizing a throat against a chamber pressure limit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Sequence

import numpy as np

from hrap.engine.sim import run
from hrap.engine.summary import summarize
from hrap.io.config import clone_cfg, resolve


@dataclass(frozen=True)
class SweepCase:
    throat: float         # m
    inj_Cd: float
    peak_P_cmbr: float    # Pa, absolute
    avg_inj_dP: float     # Pa, tank minus chamber, averaged over the burn; skips the chamber-filling spike
    total_impulse: float  # N·s
    peak_thrust: float    # N
    burn_time: float      # s
    end_cond: str


def sweep(cfg: dict[str, Any], throats: Sequence[float], cds: Sequence[float]) -> Iterator[SweepCase]:
    """Run ``cfg`` once per throat diameter (m) and injector Cd, keeping every other input.

    A nozzle defined by exit diameter keeps that exit, so its expansion ratio changes with the throat.
    """
    for throat in throats:
        for cd in cds:
            case_cfg = clone_cfg(cfg)
            case_cfg.update(noz_thrt=float(throat), noz_thrt_unit="m", inj_Cd=float(cd))
            s, x = resolve(case_cfg)
            x, o = run(s, x)
            info = summarize(s, x, o)
            burning = o.F_thr > 0
            inj_dP = o.P_tnk[burning] - o.P_cmbr[burning]
            yield SweepCase(
                throat=float(throat),
                inj_Cd=float(cd),
                peak_P_cmbr=float(np.max(o.P_cmbr)),
                avg_inj_dP=float(np.mean(inj_dP)) if inj_dP.size else 0.0,
                total_impulse=info["total_impulse"],
                peak_thrust=info["peak_thrust"],
                burn_time=info["burn_time"],
                end_cond=info["end_cond"],
            )
