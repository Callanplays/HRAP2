"""Motor mass and CG. Port of MATLAB util/mass.m."""
from __future__ import annotations

import math

from hrap.engine.types import Settings, State


def mass_properties(s: Settings, x: State) -> tuple[float, float]:
    x.m_t = s.mtr_m + x.m_o + x.m_f
    if x.mLiq_new < 0:
        x.mLiq_new = 0.0

    tA = 0.25 * math.pi * s.tnk_D ** 2

    if x.mLiq_new > 0:
        m_v = x.m_o - x.mLiq_new
        vl = x.mLiq_new / x.ox_props.rho_l
        vv = s.tnk_V - vl
        hl = vl / tA if tA != 0.0 else 0.0
        hv = vv / tA if tA != 0.0 else 0.0
        CoMl = s.tnk_X - hl / 2.0
        CoMv = s.tnk_X - hl - hv / 2.0
        CoMf = s.cmbr_X - s.grn_L / 2.0
        x.cg = (x.mLiq_new * CoMl + m_v * CoMv + x.m_f * CoMf + s.mtr_m * s.mtr_cg) / x.m_t
    else:
        m_v = x.m_o
        vv = s.tnk_V
        hv = vv / tA if tA != 0.0 else 0.0
        CoMv = s.tnk_X - hv / 2.0
        CoMf = s.cmbr_X - s.grn_L / 2.0
        x.cg = (m_v * CoMv + x.m_f * CoMf + s.mtr_m * s.mtr_cg) / x.m_t

    return x.m_t, x.cg
