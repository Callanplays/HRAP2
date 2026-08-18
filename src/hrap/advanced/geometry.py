"""Optional non-cylindrical grain helpers (advanced mode)."""
from __future__ import annotations

import math

import numpy as np

from hrap.engine.grain import const_of, shift_of
from hrap.engine.types import Settings, State


def star_vertices(inner_r: float, tip_r: float, n_tips: int) -> np.ndarray:
    r = np.array([inner_r, tip_r] * n_tips)
    t = np.linspace(0.0, 2 * math.pi, 2 * n_tips, endpoint=False)
    return np.stack([r * np.cos(t), r * np.sin(t)], axis=1)


def star_perimeter_and_area(inner_r: float, tip_r: float, n_tips: int) -> tuple[float, float]:
    v = star_vertices(inner_r, tip_r, n_tips)
    v1 = np.roll(v, -1, axis=0)
    perim = float(np.sum(np.hypot(v1[:, 0] - v[:, 0], v1[:, 1] - v[:, 1])))
    area = 0.5 * float(np.abs(np.sum(v[:, 0] * v1[:, 1] - v1[:, 0] * v[:, 1])))
    return perim, area


def make_star_grain_fn(n_tips: int = 6):
    """Regression using star perimeter; chamber still sees an equivalent circular ID."""

    def grain_fn(s: Settings, x: State) -> State:
        if s.regression_model == "Shifting OF":
            x = shift_of(s, x)
        else:
            x = const_of(s, x)
        r_tip = 0.5 * x.grn_ID_old
        r_in = 0.45 * r_tip
        perim, _area = star_perimeter_and_area(r_in, r_tip, n_tips)
        if s.regression_model == "Shifting OF":
            x.mdot_f = s.prop_Rho * x.rdot * perim * s.grn_L
            x.OF = x.mdot_o / x.mdot_f if x.mdot_f else 0.0
            x.m_f = x.m_f + s.prop_Rho * x.rdot * (math.pi * x.grn_ID_old * s.grn_L) * s.dt
            x.m_f = x.m_f - x.mdot_f * s.dt
        return x

    return grain_fn


def make_polygon_grain_fn(vertices: np.ndarray):
    """Regression using an arbitrary closed polygon (advanced, not MATLAB)."""
    verts = np.asarray(vertices, dtype=float)

    def grain_fn(s: Settings, x: State) -> State:
        if s.regression_model != "Shifting OF":
            return const_of(s, x)
        x = shift_of(s, x)
        scale = (0.5 * x.grn_ID_old) / max(float(np.max(np.hypot(verts[:, 0], verts[:, 1]))), 1e-12)
        v = verts * scale
        v1 = np.roll(v, -1, axis=0)
        perim = float(np.sum(np.hypot(v1[:, 0] - v[:, 0], v1[:, 1] - v[:, 1])))
        x.mdot_f = s.prop_Rho * x.rdot * perim * s.grn_L
        x.OF = x.mdot_o / x.mdot_f if x.mdot_f else 0.0
        x.m_f = x.m_f + s.prop_Rho * x.rdot * (math.pi * x.grn_ID_old * s.grn_L) * s.dt
        x.m_f = x.m_f - x.mdot_f * s.dt
        return x

    return grain_fn
