"""Superellipse geometry helpers.

A superellipse with semi-axes (a, b) and exponent n is the locus
``|x/a|^n + |y/b|^n <= 1``. n=2 is an ellipse; n→∞ approaches a rectangle.
"""

from __future__ import annotations

import math
from collections.abc import Callable


def superellipse_indicator(a_nm: float, b_nm: float, n: float) -> Callable[[tuple[float, float, float]], bool]:
    """Return a `point → inside?` predicate for ubermag's `Region.subregions`.

    Coordinates handed in by ubermag are in metres; we convert to nm
    inside the closure to keep the public surface in nm.
    """
    a = a_nm * 1e-9
    b = b_nm * 1e-9

    def inside(point: tuple[float, float, float]) -> bool:
        x, y, _z = point
        # Centre the shape on (0, 0) — caller is expected to use a mesh
        # with origin at -size/2 so the superellipse sits in the middle.
        return (abs(x) / a) ** n + (abs(y) / b) ** n <= 1.0

    return inside


def superellipse_area_nm2(a_nm: float, b_nm: float, n: float) -> float:
    """Closed-form area of a superellipse: 4ab Γ(1+1/n)² / Γ(1+2/n)."""
    g1 = math.gamma(1.0 + 1.0 / n)
    g2 = math.gamma(1.0 + 2.0 / n)
    return 4.0 * a_nm * b_nm * (g1 * g1) / g2


__all__ = ["superellipse_area_nm2", "superellipse_indicator"]
