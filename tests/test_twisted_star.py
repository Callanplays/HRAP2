import math

import numpy as np
import pytest

from hrap.advanced.geometry import star_geometry_table, star_vertices, twisted_perimeter
from hrap.io.config import bundled_motor, resolve


def twisted_cfg():
    cfg = bundled_motor("example_98mm")
    cfg.update(reg_model="Shifting OF", prop_a=.198, prop_n=.325, prop_m=0.)
    cfg["advanced"] = dict(enabled=True, grain_shape="twisted star", star_tips=6,
                           star_inner_ratio=.45, star_twist_pitch=3., star_twist_pitch_unit="in")
    return cfg


def test_twisted_surface_matches_independent_triangle_mesh():
    vertices = star_vertices(.009, .02, 6)
    points = np.concatenate([np.linspace(a, b, 40, endpoint=False)
                             for a, b in zip(vertices, np.roll(vertices, -1, axis=0))])
    z = np.linspace(0, .15, 601)
    k = 2 * math.pi / .075
    c, s = np.cos(k*z)[:, None], np.sin(k*z)[:, None]
    surface = np.stack([c*points[:, 0]-s*points[:, 1], s*points[:, 0]+c*points[:, 1],
                        np.broadcast_to(z[:, None], (len(z), len(points)))], axis=-1)
    a, d = surface[:-1], surface[1:]
    b, c = np.roll(a, -1, axis=1), np.roll(d, -1, axis=1)
    area = .5 * (np.linalg.norm(np.cross(b-a, c-a), axis=-1).sum()
                 + np.linalg.norm(np.cross(c-a, d-a), axis=-1).sum())
    assert twisted_perimeter(vertices, k) * .15 == pytest.approx(area, rel=2e-4)


def test_twisting_a_circle_does_not_add_surface():
    theta = np.linspace(0, 2*math.pi, 4096, endpoint=False)
    vertices = .02 * np.c_[np.cos(theta), np.sin(theta)]
    plain = twisted_perimeter(vertices, 0)
    assert twisted_perimeter(vertices, 2*math.pi/.04) == pytest.approx(plain, rel=2e-6)


def test_twist_does_not_change_initial_area_and_long_pitch_limit():
    web, area, plain = star_geometry_table(.014, .022, 6, .45)
    _, twisted, ratios = star_geometry_table(.014, .022, 6, .45, twist_pitch=.0762)
    _, long, long_ratios = star_geometry_table(.014, .022, 6, .45, twist_pitch=1e8)
    np.testing.assert_array_equal(area, twisted)
    np.testing.assert_array_equal(area, long)
    np.testing.assert_allclose(long_ratios, plain, rtol=1e-12)
    assert np.all(ratios >= 1) and ratios[0] > 1.01
    fine_web, _, fine_ratios = star_geometry_table(.014, .022, 6, .45, samples=1025,
                                                  quad_segs=128, twist_pitch=.0762)
    np.testing.assert_allclose(np.interp(fine_web, web, ratios), fine_ratios, rtol=2e-4)


@pytest.mark.parametrize("dt", [.001, 1000.])
def test_twisted_step_conserves_fuel_and_volume(dt):
    cfg = twisted_cfg()
    cfg["dt"] = dt
    s, x = resolve(cfg)
    mass, area = x.m_f, math.pi/4*x.grn_ID**2
    x.mdot_o = .5
    s.grain_fn(s, x)
    dm = s.prop_Rho*s.grn_L*(math.pi/4*x.grn_ID**2-area)
    assert mass-x.m_f == pytest.approx(dm, rel=1e-10)
    assert x.mdot_f*dt == pytest.approx(dm, rel=1e-10)
    assert x.OF == pytest.approx(x.mdot_o/x.mdot_f)
    if dt == 1000:
        assert x.grn_ID == s.grn_ID_limit and x.m_f > 0


@pytest.mark.parametrize("pitch", [0, -1, float("nan")])
def test_invalid_twist_pitch_rejected(pitch):
    cfg = twisted_cfg()
    cfg["advanced"]["star_twist_pitch"] = pitch
    with pytest.raises(ValueError, match="pitch"):
        resolve(cfg)


def test_gui_twisted_star_roundtrip_and_preview(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from hrap.gui.main import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    cfg = twisted_cfg()
    cfg["advanced"]["star_twist_pitch"] = .0762
    del cfg["advanced"]["star_twist_pitch_unit"]
    try:
        window._cfg_to_form(cfg)
        actual = window._form_to_cfg()
        assert actual["advanced"]["grain_shape"] == "twisted star"
        assert actual["advanced"]["star_twist_pitch"] == pytest.approx(.0762)
        assert actual["advanced"]["star_twist_pitch_unit"] == "m"
        assert not window.star_twist_pitch.isHidden()
        assert window.helix_offset.isHidden()
        s, x = resolve(actual)
        assert window._motor_view().grn_ID == pytest.approx(x.grn_ID)
    finally:
        window.close()
