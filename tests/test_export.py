import xml.etree.ElementTree as ET

import numpy as np

from hrap.engine.sim import run
from hrap.io.config import default_cfg, resolve
from hrap.io.export import export_rse


def test_rse_delayed_thrust_has_increasing_times_and_valid_metadata(tmp_path):
    cfg = default_cfg()
    cfg["t_max"] = .01
    s, x = resolve(cfg)
    _, output = run(s, x)
    output.t += 2.0
    manufacturer = 'R&D "motor"'
    path = tmp_path / "motor.rse"
    export_rse(path, output, s, mfg=manufacturer)
    engine = ET.parse(path).find(".//engine")
    assert engine.attrib["mfg"] == manufacturer
    times = np.array([float(row.attrib["t"]) for row in engine.findall(".//eng-data")])
    assert np.all(np.diff(times) > 0)
    assert float(engine.findall(".//eng-data")[-1].attrib["f"]) == 0
