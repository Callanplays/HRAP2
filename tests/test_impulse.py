from hrap.engine.impulse import impulse_class


def test_impulse_class_boundaries():
    letter, pct = impulse_class(1.25)
    assert letter == "A"
    assert abs(pct - 100.0) < 1e-9
    letter, pct = impulse_class(2.5)
    assert letter == "B"
    assert abs(pct - 50.0) < 1e-9  # MATLAB denominator 2.5, not 3.75
    letter, pct = impulse_class(160.0)
    assert letter == "G"
    letter, pct = impulse_class(1280.0)
    assert letter == "J"
    letter, pct = impulse_class(2000.0)
    assert letter == "K"
    assert 0.0 <= pct <= 100.0
