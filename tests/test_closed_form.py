"""Closed-form c* and Cf checks matching MATLAB comb.m / nozzle.m."""
from __future__ import annotations

import math

from hrap.engine.comb import R_UNIV
from hrap.engine.fzero import matlab_fzero


def matlab_cstar(R: float, T: float, k: float, cstar_eff: float = 1.0) -> float:
    return cstar_eff * math.sqrt((R * T) / (k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0))))


def matlab_cf(k: float, Pe_Pc: float, Pa_Pc: float, ER: float) -> float:
    return math.sqrt(
        ((2.0 * k ** 2) / (k - 1.0))
        * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0))
        * (1.0 - Pe_Pc ** ((k - 1.0) / k))
    ) + (Pe_Pc - Pa_Pc) * ER


def test_cstar_formula():
    k, T, M = 1.25, 3200.0, 24.0
    R = R_UNIV / M
    cs = matlab_cstar(R, T, k, 1.0)
    assert 1400.0 < cs < 1800.0
    assert abs(matlab_cstar(R, T, k, 0.9) - 0.9 * cs) < 1e-12


def test_area_mach_and_cf():
    k, ER = 1.25, 5.5

    def A_ratio(M: float) -> float:
        return (
            ((k + 1.0) / 2.0) ** (-(k + 1.0) / (2.0 * (k - 1.0)))
            * (1.0 + (k - 1.0) / 2.0 * M ** 2) ** ((k + 1.0) / (2.0 * (k - 1.0)))
            / M
            - ER
        )

    M = matlab_fzero(A_ratio, 3.0)
    assert 2.5 < M < 4.0
    assert abs(A_ratio(M)) < 1e-10
    Pe_Pc = (1.0 + 0.5 * (k - 1.0) * M ** 2) ** (-k / (k - 1.0))
    Cf = matlab_cf(k, Pe_Pc, 101325.0 / 3e6, ER)
    assert 1.2 < Cf < 1.8
