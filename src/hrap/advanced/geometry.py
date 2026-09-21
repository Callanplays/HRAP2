"""Optional non-cylindrical grain helpers (advanced mode)."""
from __future__ import annotations

import math

import numpy as np

from shapely.geometry import Polygon
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


def star_area_table(tip_radius: float, outer_radius: float, n_tips: int, inner_ratio: float,
                    samples: int = 513, quad_segs: int = 64) -> tuple[np.ndarray, np.ndarray]:
    """Normal-offset distance and port area (SI), through first wall contact."""
    if not (3 <= n_tips <= 16 and int(n_tips) == n_tips):
        raise ValueError("Star tip count must be an integer from 3 to 16.")
    if not math.isfinite(inner_ratio) or not 0 < inner_ratio < math.cos(math.pi / n_tips):
        raise ValueError("Star valley / tip radius ratio must be positive and below cos(pi / tips).")
    if not (math.isfinite(tip_radius) and math.isfinite(outer_radius) and 0 < tip_radius < outer_radius):
        raise ValueError("Star tip radius must be positive and smaller than grain outer radius.")
    port = Polygon(star_vertices(tip_radius * inner_ratio, tip_radius, n_tips))
    web = np.linspace(0.0, outer_radius - tip_radius, samples)
    areas = np.array([port.buffer(float(w), quad_segs=quad_segs).area for w in web])
    return web, areas


def configure_star(s: Settings, x: State, n_tips: int, inner_ratio: float) -> None:
    """Install normal-offset star regression with consistent mass and volume."""
    if s.regression_model != "Shifting OF":
        raise ValueError("Star grain requires Shifting OF; Constant OF prescribes fuel flow.")
    if not all(math.isfinite(v) and v > 0 for v in (s.grn_L, s.prop_Rho, s.dt)):
        raise ValueError("Star grain length, density and timestep must be positive and finite.")
    if not all(math.isfinite(float(v)) for v in s.prop_Reg) or s.prop_Reg[0] < 0:
        raise ValueError("Regression coefficients must be finite, with nonnegative coefficient a.")
    web, areas = star_area_table(s.grn_ID0 / 2, s.grn_OD / 2, n_tips, inner_ratio)
    outer_area = math.pi / 4 * s.grn_OD**2
    fuel_volume = (outer_area - areas[0]) * s.grn_L
    if not math.isfinite(s.cmbr_V) or s.cmbr_V <= fuel_volume:
        raise ValueError("Chamber volume must leave positive gas volume around the actual star grain.")
    x.m_f = s.prop_Rho * fuel_volume
    x.m_g = 1.225 * (s.cmbr_V - fuel_volume)
    x.grn_ID = x.grn_ID_old = s.grn_ID0 = 2 * math.sqrt(areas[0] / math.pi)
    s.grn_ID_limit = 2 * math.sqrt(areas[-1] / math.pi)

    def regress(s: Settings, x: State) -> State:
        area = math.pi / 4 * x.grn_ID**2
        old_web = float(np.interp(area, areas, web))
        flux = x.mdot_o / area
        a, n, m = s.prop_Reg
        normal_rate = 0.001 * a * flux**n * s.grn_L**m if flux > 0 else 0.0
        if normal_rate == 0:
            x.grn_ID_old = x.grn_ID
            x.mdot_f = x.OF = x.rdot = 0.0
            return x
        new_web = min(old_web + normal_rate * s.dt, web[-1])
        new_area = float(np.interp(new_web, web, areas))
        consumed = s.prop_Rho * s.grn_L * (new_area - area)
        x.grn_ID_old = x.grn_ID
        x.grn_ID = s.grn_ID_limit if new_web >= web[-1] else 2 * math.sqrt(new_area / math.pi)
        x.mdot_f = consumed / s.dt
        x.m_f = s.prop_Rho * (outer_area - new_area) * s.grn_L
        x.OF = x.mdot_o / x.mdot_f if x.mdot_f > 0 else 0.0
        x.rdot = (new_web - old_web) / s.dt
        return x

    s.grain_fn = regress
