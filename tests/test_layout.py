from hrap.engine.mass import mass_properties
from hrap.io.config import apply_layout_mass, bundled_motor, default_cfg, resolve, resolve_layout
from hrap.io.export import export_eng
from hrap.layout import FEED_GAP, PLATE_L, infer_component_stations, motor_layout
from hrap.units import to_si


def test_packed_layout_matches_legacy_plate_stack():
    lay = motor_layout(
        tnk_start=0.0,
        tnk_L=0.20,
        cmbr_start=None,
        grn_L=0.40,
        grn_OD=0.08,
        noz_thrt=0.025,
        noz_exit=0.05,
    )
    assert abs(lay.tnk1 - 0.20) < 1e-12
    assert abs(lay.plate0 - 0.20) < 1e-12
    assert abs(lay.plate1 - lay.plate0 - PLATE_L) < 1e-12
    assert lay.grn0 == lay.plate1
    assert lay.x_max >= lay.x_noz


def test_gap_between_tank_and_chamber():
    lay = motor_layout(
        tnk_start=0.10,
        tnk_L=0.20,
        cmbr_start=0.40,
        cmbr_L=0.50,
        tnk_m=4.0,
        cmbr_m=6.0,
        grn_L=0.30,
        grn_OD=0.08,
        noz_thrt=0.025,
        noz_exit=0.05,
    )
    assert abs(lay.cmbr0 - lay.tnk1 - 0.10) < 1e-12
    assert abs(lay.dry_mass - 10.0) < 1e-12
    assert abs(lay.dry_cg - (4.0 * 0.20 + 6.0 * 0.65) / 10.0) < 1e-12
    assert abs(lay.overall_L - (0.90 - 0.10)) < 1e-9


def test_infer_matlab_aft_stations():
    tnk_L = 1.0
    grn_L = 0.4
    tnk_X = 1.2
    cmbr_X = 1.8
    tnk0, cmbr0, cmbr_L = infer_component_stations(
        tnk_start=0.0,
        cmbr_start=0.0,
        cmbr_L=0.0,
        tnk_L=tnk_L,
        grn_L=grn_L,
        tnk_X=tnk_X,
        cmbr_X=cmbr_X,
        auto_cmbr_L=0.55,
    )
    assert abs(tnk0 - (tnk_X - tnk_L)) < 1e-12
    assert abs(cmbr0 - (cmbr_X - grn_L - PLATE_L)) < 1e-12
    assert abs(cmbr_L - 0.55) < 1e-12


def test_new_motor_chamber_follows_tank():
    tnk0, cmbr0, _cmbr_L = infer_component_stations(
        tnk_start=0.0,
        cmbr_start=0.0,
        cmbr_L=0.0,
        tnk_L=0.3,
        grn_L=0.2,
        tnk_X=0.0,
        cmbr_X=0.0,
        auto_cmbr_L=0.4,
    )
    assert tnk0 == 0.0
    assert abs(cmbr0 - (0.3 + FEED_GAP)) < 1e-12


def test_example_98mm_keeps_legacy_empty_mass():
    cfg = bundled_motor("example_98mm")
    s, _x = resolve(cfg)
    assert abs(s.mtr_m - 9.47769) < 1e-6
    assert abs(s.mtr_cg - to_si(52.33018, "in", "length")) < 1e-6
    assert abs(s.tnk_X - to_si(72.54685, "in", "length")) < 5e-3
    assert abs(s.cmbr_X - to_si(91.635, "in", "length")) < 5e-3


def test_component_dry_mass_replaces_legacy_empty():
    cfg = default_cfg()
    cfg["tnk_V_state"] = 1
    cfg["tnk_L"] = 15.0
    cfg["tnk_L_unit"] = "in"
    cfg["tnk_start"] = 0.0
    cfg["tnk_m"] = 4.0
    cfg["cmbr_start"] = 20.0
    cfg["cmbr_start_unit"] = "in"
    cfg["cmbr_L"] = 22.0
    cfg["cmbr_L_unit"] = "in"
    cfg["cmbr_m"] = 6.0
    cfg["mtr_m"] = 99.0
    lay = resolve_layout(cfg)
    mtr_m, mtr_cg, tnk_X, cmbr_X = apply_layout_mass(cfg, lay)
    assert abs(mtr_m - 10.0) < 1e-9
    assert abs(mtr_cg - lay.dry_cg) < 1e-12
    assert tnk_X == lay.tnk_aft
    assert cmbr_X == lay.grain_aft
    s, x = resolve(cfg)
    x.m_o = 2.0
    x.m_f = 1.0
    x.mLiq_new = 1.5
    from hrap.engine.nox import nox

    x.ox_props = nox(293.15)
    m_t, cg = mass_properties(s, x)
    assert abs(m_t - (10.0 + 2.0 + 1.0)) < 1e-9
    assert cg > 0.0


def test_eng_header_uses_layout_length_and_notes_cg(tmp_path):
    cfg = bundled_motor("example_98mm")
    cfg["tnk_m"] = 4.0
    cfg["cmbr_m"] = 6.0
    s, x = resolve(cfg)
    from hrap.engine.sim import run

    _x, o = run(s, x)
    path = tmp_path / "m.eng"
    export_eng(path, o, s, L=0.8)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("; HRAP-HCAT-Fork cg0=")
    header = next(line for line in text.splitlines() if not line.startswith(";"))
    parts = header.split()
    assert abs(float(parts[2]) - 800.0) < 1e-6
    assert float(parts[5]) > 10.0
