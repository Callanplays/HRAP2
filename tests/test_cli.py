from types import SimpleNamespace

import numpy as np
import pytest

from hrap.cli import compare_main
from hrap.io.config import default_cfg, save_json


@pytest.mark.parametrize("csv, expected", [
    ("t,F_thr\n0,0\n1,2\n", 0),
    ("t,F_thr\n0,0\n", 1),
    ("t,F_thr\n0,0\n1,nan\n", 1),
    ("t,F_thr\n0,0\n1,3\n", 1),
    ("t,unrelated\n0,0\n1,2\n", 1),
    ("t,F_thr\n", 1),
])
def test_compare_rejects_incomplete_or_invalid_reference(tmp_path, monkeypatch, csv, expected):
    output = SimpleNamespace(
        t=np.array([0., 1.]), F_thr=np.array([0., 2.]),
        **{key: np.zeros(2) for key in
           ("P_tnk", "P_cmbr", "mdot_o", "mdot_f", "OF", "grn_ID", "m_o", "m_f")},
        sim_end_cond="Max Simulation Time Reached",
    )
    monkeypatch.setattr("hrap.engine.sim.run", lambda s, x: (x, output))
    motor, reference = tmp_path / "motor.json", tmp_path / "reference.csv"
    save_json(motor, default_cfg())
    reference.write_text(csv)
    assert compare_main([str(motor), str(reference)]) == expected
