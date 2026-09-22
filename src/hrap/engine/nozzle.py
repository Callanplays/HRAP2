"""Isentropic CD nozzle. Port of MATLAB util/nozzle.m."""
from __future__ import annotations

import math
from typing import cast

from scipy.optimize import brentq

from hrap.engine.types import Settings, State


def nozzle(s: Settings, x: State) -> State:
    if x.P_cmbr > s.Pa:
        k = x.k

        def A_ratio(M: float) -> float:
            return (
                ((k + 1.0) / 2.0) ** (-(k + 1.0) / (2.0 * (k - 1.0)))
                * (1.0 + (k - 1.0) / 2.0 * M ** 2) ** ((k + 1.0) / (2.0 * (k - 1.0)))
                / M
                - s.noz_ER
            )

        # Unique supersonic root (MATLAB fzero from guess 3).
        M = cast(float, brentq(A_ratio, 1.0000001, 80.0, xtol=2.2e-16, maxiter=200))
        Pe = x.P_cmbr * (1.0 + 0.5 * (k - 1.0) * M ** 2) ** (-k / (k - 1.0))
        Ath = 0.25 * math.pi * s.noz_thrt ** 2
        Aex = Ath * s.noz_ER
        Cf = math.sqrt(
            ((2.0 * k ** 2) / (k - 1.0))
            * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0))
            * (1.0 - (Pe / x.P_cmbr) ** ((k - 1.0) / k))
        ) + ((Pe - s.Pa) * Aex) / (x.P_cmbr * Ath)
        x.F_thr = s.noz_eff * Cf * Ath * x.P_cmbr * s.noz_Cd
        if x.F_thr < 0.0:
            x.F_thr = 0.0
    else:
        x.F_thr = 0.0
    return x
