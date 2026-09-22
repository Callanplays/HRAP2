"""MATLAB-compatible fzero (scalar start, Brent after bracketing)."""
from __future__ import annotations

from typing import Callable, cast

from scipy.optimize import brentq


def _call(func: Callable[[float], float], x: float) -> float:
    try:
        y = func(float(x))
    except (ValueError, ZeroDivisionError, FloatingPointError, OverflowError, TypeError, ArithmeticError):
        return float("nan")
    if isinstance(y, complex):
        if abs(y.imag) > 1e-12:
            return float("nan")
        y = y.real
    y = float(y)
    if y != y or y in (float("inf"), float("-inf")):
        return float("nan")
    return y


def matlab_fzero(func: Callable[[float], float], x0: float, xtol: float = 2.2e-16) -> float:
    """Approximate MATLAB fzero(fun, x0) for a scalar starting guess.

    MATLAB expands a step around the *original* guess. Walking the center to
    the last probe (an earlier Python draft) overshoots Tc on N2O Pv(T) and
    produces complex residuals.
    """
    x0 = float(x0)
    f0 = _call(func, x0)
    if f0 == 0.0 or (f0 == f0 and abs(f0) < 1e-14):
        return x0

    dx = 0.01 * (1.0 + abs(x0))
    a = b = x0
    fa = fb = f0
    found = False
    for _ in range(200):
        left, right = x0 - dx, x0 + dx
        fl, fr = _call(func, left), _call(func, right)
        for lo, hi, flo, fhi in (
            (left, x0, fl, f0),
            (x0, right, f0, fr),
            (left, right, fl, fr),
        ):
            if flo == flo and fhi == fhi and flo * fhi <= 0.0:
                a, b, fa, fb = lo, hi, flo, fhi
                found = True
                break
        if found:
            break
        dx *= 1.6

    if not found:
        for lo, hi in ((183.15, 309.56), (1.000001, 50.0), (0.5, 20.0), (50.0, 400.0)):
            flo, fhi = _call(func, lo), _call(func, hi)
            if flo == flo and fhi == fhi and flo * fhi <= 0.0:
                a, b, fa, fb = lo, hi, flo, fhi
                found = True
                break
        if not found:
            raise RuntimeError(f"matlab_fzero could not bracket a root near {x0}")

    if a > b:
        a, b = b, a
        fa, fb = fb, fa
    if fa == 0.0:
        return a
    if fb == 0.0:
        return b
    return cast(float, brentq(lambda t: _call(func, t), a, b, xtol=xtol, maxiter=200))
