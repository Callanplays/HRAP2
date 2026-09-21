"""Experimental fixed-shape helical port; see docs/helical-grain.md."""
from __future__ import annotations

import math

from scipy.special import ellipe

from hrap.engine.types import Settings, State


def area_multiplier(offset: float, pitch: float) -> float:
    """Side area / (2*pi*r*L), for circular ports in axial planes (SI)."""
    if not math.isfinite(offset) or offset < 0:
        raise ValueError("Helix offset must be finite and nonnegative.")
    if not math.isfinite(pitch) or pitch <= 0:
        raise ValueError("Helix pitch must be finite and positive.")
    slope = 2.0 * math.pi * offset / pitch
    factor = float(2.0 / math.pi * ellipe(-slope * slope))
    if not math.isfinite(factor):
        raise ValueError("Helix offset / pitch ratio is too large.")
    return factor


def configure_helical(s: Settings, offset: float, pitch: float, multiplier: float) -> None:
    """Install a volume-conserving, area-averaged Shifting OF grain callback.

    Offset and pitch remain fixed. The local regression law uses axial flux
    and axial grain length. The multiplier is an assumption, not a swirl model.
    Ends and outer surface are inhibited. Stop at first outer-wall contact.
    """
    factor = area_multiplier(offset, pitch)
    if s.regression_model != "Shifting OF":
        raise ValueError("Helical grain requires Shifting OF; Constant OF prescribes fuel flow.")
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("Assumed regression multiplier must be finite and positive.")
    if not all(math.isfinite(v) and v > 0 for v in
               (s.grn_OD, s.grn_ID0, s.grn_L, s.prop_Rho, s.dt)):
        raise ValueError("Helical grain dimensions, density and timestep must be positive and finite.")
    limit = s.grn_OD - 2.0 * offset
    if s.grn_ID0 >= limit:
        raise ValueError("Helix offset + initial port radius must be smaller than grain outer radius.")
    if not all(math.isfinite(float(v)) for v in s.prop_Reg) or s.prop_Reg[0] < 0:
        raise ValueError("Regression coefficients must be finite, with a nonnegative coefficient a.")
    fuel_volume = math.pi / 4.0 * (s.grn_OD**2 - s.grn_ID0**2) * s.grn_L
    if not math.isfinite(s.cmbr_V) or s.cmbr_V <= fuel_volume:
        raise ValueError("Chamber volume must leave positive initial gas volume.")
    s.grn_ID_limit = limit

    def regress(s: Settings, x: State) -> State:
        radius = x.grn_ID / 2.0
        port_area = math.pi * radius**2
        flux = x.mdot_o / port_area
        a, n, m = s.prop_Reg
        normal_rate = (0.001 * a * flux**n * s.grn_L**m * multiplier) if flux > 0 else 0.0
        burn_area = 2.0 * math.pi * radius * s.grn_L * factor
        requested_mass = s.prop_Rho * normal_rate * burn_area * s.dt
        available_mass = s.prop_Rho * math.pi * s.grn_L * ((limit / 2.0)**2 - radius**2)
        consumed = min(requested_mass, max(0.0, available_mass))
        x.grn_ID_old = x.grn_ID
        if requested_mass >= available_mass:
            x.grn_ID = limit
        else:
            x.grn_ID = 2.0 * math.sqrt(radius**2 + consumed / (s.prop_Rho * math.pi * s.grn_L))
        # Use the actual clipped consumption in O/F and the chamber mass balance.
        x.mdot_f = consumed / s.dt
        x.m_f -= consumed
        x.OF = x.mdot_o / x.mdot_f if x.mdot_f > 0 else 0.0
        # Preserve output meaning: effective normal consumption rate, not dr/dt.
        x.rdot = x.mdot_f / (s.prop_Rho * burn_area)
        return x

    s.grain_fn = regress
