"""Conservation and geometric limits of the experimental helical closure."""
import math

import numpy as np
import pytest
from scipy.integrate import quad

from hrap.advanced.helical import area_multiplier
from hrap.io.config import bundled_motor, resolve
from hrap.engine.sim import run


def helical_cfg():
    cfg = bundled_motor("example_98mm")
    cfg.update(reg_model="Shifting OF", prop_a=0.198, prop_n=0.325, prop_m=0.0,
               dt=0.001, t_max=0.1)
    cfg["advanced"] = dict(enabled=True, grain_shape="helical", ox_fluid="N2O_legacy",
                           helix_offset=0.1, helix_offset_unit="in",
                           helix_pitch=3.0, helix_pitch_unit="in",
                           helix_regression_multiplier=1.0)
    return cfg


def test_surface_area_and_straight_limits():
    offset, pitch = 0.00635, 0.0381
    slope = 2 * math.pi * offset / pitch
    integral, _ = quad(lambda theta: math.sqrt(1 + (slope * math.sin(theta))**2),
                       0, 2 * math.pi, epsabs=1e-12)
    assert area_multiplier(offset, pitch) == pytest.approx(integral / (2 * math.pi), rel=1e-12)
    assert area_multiplier(0, pitch) == pytest.approx(1.0)
    assert area_multiplier(offset, 1e6) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("cross_wall", [False, True])
def test_step_conserves_fuel_and_chamber_volume(cross_wall):
    cfg = helical_cfg()
    if cross_wall:
        cfg["dt"] = 1000.0  # deliberately cross the wall in a grain-only step
    s, x = resolve(cfg)
    before_mass, before_id = x.m_f, x.grn_ID
    x.mdot_o = 0.5
    s.grain_fn(s, x)
    delta_volume = math.pi / 4 * (x.grn_ID**2 - before_id**2) * s.grn_L
    assert before_mass - x.m_f == pytest.approx(s.prop_Rho * delta_volume, rel=1e-10)
    assert x.mdot_f * s.dt == pytest.approx(s.prop_Rho * delta_volume, rel=1e-10)
    assert x.OF == pytest.approx(x.mdot_o / x.mdot_f)
    assert x.grn_ID <= s.grn_ID_limit
    if cross_wall:
        assert x.grn_ID == s.grn_ID_limit
        expected_remaining = s.prop_Rho * math.pi / 4 * (s.grn_OD**2 - s.grn_ID_limit**2) * s.grn_L
        assert x.m_f == pytest.approx(expected_remaining)
        assert x.m_f > 0


def test_full_run_stops_at_wall_with_fuel_remaining():
    cfg = helical_cfg()
    # Start just inside the wall so the actual tank/grain/chamber loop hits it.
    cfg["advanced"]["helix_offset"] = (cfg["grn_OD"] - cfg["grn_ID"]) / 2 - 0.00001
    s, x = resolve(cfg)
    x, o = run(s, x)
    assert o.sim_end_cond == "Port Reached Outer Wall"
    assert x.m_f > 0
    expected = s.prop_Rho * math.pi / 4 * (s.grn_OD**2 - o.grn_ID**2) * s.grn_L
    np.testing.assert_allclose(o.m_f, expected, rtol=1e-12, atol=1e-12)
    assert np.isfinite(o.P_cmbr).all()


def test_zero_offset_approaches_cylindrical_regression():
    cfg = helical_cfg()
    cfg["dt"] = 1e-7
    cfg["advanced"]["helix_offset"] = 0.0
    s, x = resolve(cfg)
    radius = x.grn_ID / 2
    x.mdot_o = 0.5
    a, n, m = s.prop_Reg
    normal_rate = .001 * a * (x.mdot_o / (math.pi * radius**2))**n * s.grn_L**m
    s.grain_fn(s, x)
    assert x.rdot == pytest.approx(normal_rate, rel=1e-12)
    assert (x.grn_ID - 2 * radius) / (2 * s.dt) == pytest.approx(normal_rate, rel=1e-6)


@pytest.mark.parametrize("overrides", [
    {"helix_pitch": 0}, {"helix_offset": -1}, {"helix_offset": 20},
    {"helix_regression_multiplier": 0}, {"helix_pitch": float("nan")},
])
def test_invalid_helical_inputs_rejected(overrides):
    cfg = helical_cfg()
    cfg["advanced"].update(overrides)
    with pytest.raises(ValueError):
        resolve(cfg)


def test_constant_of_rejected():
    cfg = helical_cfg()
    cfg["reg_model"] = "Constant OF"
    with pytest.raises(ValueError, match="Shifting OF"):
        resolve(cfg)


def test_zero_chamber_volume_rejected():
    cfg = helical_cfg()
    cfg.update(cmbr_V_state=0, cmbr_V=0)
    with pytest.raises(ValueError, match="positive initial gas volume"):
        resolve(cfg)


def test_gui_preserves_unitless_si_geometry(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from hrap.gui.main import MainWindow

    app = QApplication.instance() or QApplication([])
    cfg = helical_cfg()
    cfg["advanced"].update(helix_offset=0.00635, helix_pitch=0.0762)
    del cfg["advanced"]["helix_offset_unit"]
    del cfg["advanced"]["helix_pitch_unit"]
    window = MainWindow()
    try:
        window._cfg_to_form(cfg)
        actual = window._form_to_cfg()
        expected_settings, _ = resolve(cfg)
        actual_settings, _ = resolve(actual)
        assert actual_settings.grn_ID_limit == pytest.approx(expected_settings.grn_ID_limit)
        assert actual["advanced"]["helix_offset_unit"] == "m"
        assert actual["advanced"]["helix_pitch_unit"] == "m"
        assert actual["advanced"]["helix_pitch"] == pytest.approx(0.0762)
    finally:
        window.close()
