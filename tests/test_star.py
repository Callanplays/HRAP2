import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from hrap.advanced.geometry import star_geometry_table, star_vertices
from hrap.io.config import bundled_motor, resolve


def star_cfg():
    cfg = bundled_motor("example_98mm")
    cfg.update(reg_model="Shifting OF", prop_a=.198, prop_n=.325, prop_m=0.0)
    cfg["advanced"] = dict(enabled=True, grain_shape="star", star_tips=6, star_inner_ratio=.45)
    return cfg


def test_initial_geometry_mass_and_gas_volume():
    cfg = star_cfg()
    s, x = resolve(cfg)
    tip = cfg["grn_ID"] * .0254 / 2
    area = 6 * tip**2 * .45 * math.sin(math.pi / 6)
    assert math.pi / 4 * x.grn_ID**2 == pytest.approx(area)
    assert x.grn_ID_old == x.grn_ID == s.grn_ID0
    fuel_volume = (math.pi / 4 * s.grn_OD**2 - area) * s.grn_L
    assert x.m_f == pytest.approx(s.prop_Rho * fuel_volume)
    assert x.m_g == pytest.approx(1.225 * (s.cmbr_V - fuel_volume))


@pytest.mark.parametrize("overshoot", [False, True])
def test_normal_offset_conserves_mass_and_clips_wall(overshoot):
    cfg = star_cfg()
    if overshoot:
        cfg["dt"] = 1000
    s, x = resolve(cfg)
    mass, area = x.m_f, math.pi / 4 * x.grn_ID**2
    x.mdot_o = .5
    s.grain_fn(s, x)
    delta = s.prop_Rho * s.grn_L * (math.pi / 4 * x.grn_ID**2 - area)
    assert mass - x.m_f == pytest.approx(delta, rel=1e-10)
    assert x.mdot_f * s.dt == pytest.approx(delta, rel=1e-10)
    assert x.OF == pytest.approx(x.mdot_o / x.mdot_f)
    if overshoot:
        assert x.grn_ID == s.grn_ID_limit
        assert x.m_f > 0


def test_geometry_resolution_and_normal_offset_are_not_scaled_star():
    tip, outer = .014, .022
    web, areas, _ = star_geometry_table(tip, outer, 6, .45)
    finer_web, finer, _ = star_geometry_table(tip, outer, 6, .45, samples=2049)
    np.testing.assert_allclose(np.interp(finer_web, web, areas), finer, rtol=2e-5)
    _, finer_arcs, _ = star_geometry_table(tip, outer, 6, .45, quad_segs=128)
    np.testing.assert_allclose(areas, finer_arcs, rtol=1e-4)
    port = Polygon(star_vertices(tip*.45, tip, 6))
    assert areas[0] == pytest.approx(port.area)
    # Initial area derivative equals the original perimeter. Later it is not
    # the homothetically scaled star's perimeter/area relationship.
    assert (areas[1]-areas[0])/(web[1]-web[0]) == pytest.approx(port.length, rel=.003)
    scaled_area = port.area * (outer / tip)**2
    assert abs(areas[-1] - scaled_area) / areas[-1] > .1


def test_no_flow_does_not_change_geometry_or_mass():
    s, x = resolve(star_cfg())
    mass, diameter = x.m_f, x.grn_ID
    s.grain_fn(s, x)
    assert x.m_f == mass and x.grn_ID == diameter
    assert x.mdot_f == x.rdot == 0


@pytest.mark.parametrize("overrides", [{"star_tips": 2}, {"star_tips": 6.2},
                                      {"star_inner_ratio": .99}, {"star_inner_ratio": 0}])
def test_invalid_star_inputs_rejected(overrides):
    cfg = star_cfg()
    cfg["advanced"].update(overrides)
    with pytest.raises(ValueError):
        resolve(cfg)


def test_constant_of_and_insufficient_chamber_volume_rejected():
    cfg = star_cfg()
    cfg["reg_model"] = "Constant OF"
    with pytest.raises(ValueError, match="Shifting OF"):
        resolve(cfg)
    cfg["reg_model"] = "Shifting OF"
    cfg.update(cmbr_V_state=0, cmbr_V=0)
    with pytest.raises(ValueError, match="actual star grain"):
        resolve(cfg)


def test_gui_star_preview_matches_recorded_initial_mass(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from hrap.gui.main import MainWindow
    from hrap.engine.sim import run

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        cfg = star_cfg()
        cfg["t_max"] = .005
        window._cfg_to_form(cfg)
        before = window._motor_view()
        s, x = resolve(cfg)
        assert before.grn_ID == pytest.approx(x.grn_ID)
        _, window._output = run(s, x)
        recorded = window._motor_view(0)
        assert recorded.grn_ID == pytest.approx(before.grn_ID)
        assert recorded.grain_lines[3] == before.grain_lines[3]
        assert recorded.overlay_grain[0] == "100%"
        calls = []
        monkeypatch.setattr(window, "_refresh_viz", lambda: calls.append(True))
        for change in [lambda: window.star_tips.setValue(7),
                       lambda: window.star_inner_ratio.setValue(.5),
                       lambda: window.grain_shape.setCurrentText("cylindrical"),
                       lambda: window.adv_on.setChecked(False)]:
            calls.clear()
            change()
            assert calls
    finally:
        window.close()
