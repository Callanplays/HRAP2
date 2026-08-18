from __future__ import annotations

import numpy as np

from hrap.engine.interp import interp1x, interp2x


def test_interp1x_interior_and_edges():
    X = np.array([0.0, 1.0, 2.0])
    Y = np.array([10.0, 20.0, 40.0])
    assert interp1x(X, Y, -1) == 10.0
    assert interp1x(X, Y, 3) == 40.0
    assert abs(interp1x(X, Y, 0.5) - 15.0) < 1e-12
    assert abs(interp1x(X, Y, 1.5) - 30.0) < 1e-12


def test_interp2x_matches_bilinear_on_pc_of_layout():
    # Z shape (n_Y, n_X) = (n_Pc, n_OF) matching ABS.mat
    OF = np.array([1.0, 2.0, 3.0])
    Pc = np.array([1e6, 2e6])
    Z = np.array(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ]
    )
    assert abs(interp2x(OF, Pc, Z, 1.0, 1e6) - 1.0) < 1e-12
    assert abs(interp2x(OF, Pc, Z, 3.0, 2e6) - 6.0) < 1e-12
    # Mid OF, low Pc
    assert abs(interp2x(OF, Pc, Z, 2.0, 1e6) - 2.0) < 1e-12
    # Mid both: OF=2, Pc=1.5e6 -> col 1 is [2,5], mid = 3.5
    assert abs(interp2x(OF, Pc, Z, 2.0, 1.5e6) - 3.5) < 1e-12
    # Clamp
    assert abs(interp2x(OF, Pc, Z, 0.0, 0.0) - 1.0) < 1e-12
    assert abs(interp2x(OF, Pc, Z, 9.0, 9e6) - 6.0) < 1e-12
