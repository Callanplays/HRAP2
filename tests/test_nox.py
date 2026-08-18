"""Component tests that encode the MATLAB NOX.m formulas independently."""
from __future__ import annotations

import math

from hrap.engine.nox import nox, vapor_pressure


def test_nox_critical_anchor():
    op = nox(250.0)
    Tr = 250.0 / 309.57
    one_m = 1.0 - Tr
    Pv = 7251000 * math.exp(
        (1 / Tr)
        * (
            -6.71893 * one_m
            + 1.35966 * one_m ** 1.5
            - 1.3779 * one_m ** 2.5
            - 4.051 * one_m ** 5
        )
    )
    assert abs(op.Pv - Pv) < 1e-8
    assert abs(vapor_pressure(250.0) - Pv) < 1e-8
    assert op.rho_l > op.rho_v > 0
    assert 0.2 < op.Z < 1.2


def test_nox_room_temp_ballpark():
    op = nox(293.15)
    # Saturated N2O at ~20 C is roughly 50 bar
    assert 4.5e6 < op.Pv < 6.0e6
    assert 700 < op.rho_l < 900
    assert 100 < op.rho_v < 250
