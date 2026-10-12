"""Transcendental functions that give the same answer on every machine.

The platform maths libraries (macOS's, glibc's, and glibc's CPU-specific variants) may round
exp, sin, cos, atan2, and log differently in the last bit. Over thousands of simulation ticks
those bits change decisions: the same seed made a different matchday on a Mac and in the cloud.
These use only +, -, *, /, sqrt, frexp, and ldexp, which IEEE 754 makes exact or correctly
rounded everywhere, so the engine (and the Director, whose cuts the agents' cache is keyed on)
behaves the same on a laptop, in CI, and in production. Accurate to about 1e-16, which is all a
football simulation needs; they are slower than the C versions, which a baked matchday hides.

Range reductions use fdlibm's split constants (Cody and Waite): the high part has trailing zero
bits, so k * HI is exact for the k this code sees.
"""

import math
import random

_LN2_HI = 6.93147180369123816490e-01
_LN2_LO = 1.90821492927058770002e-10
_INV_LN2 = 1.44269504088896338700e00
_PIO2_HI = 1.57079632673412561417e00
_PIO2_LO = 6.07710050650619224932e-11
_TWO_OVER_PI = 6.36619772367581382433e-01
_SQRT3 = math.sqrt(3.0)
_TAN_PI_12 = 2.0 - _SQRT3  # tan(15 degrees)
_SQRT_HALF = math.sqrt(0.5)
_TWO_PI = 2.0 * math.pi


# Taylor coefficients 1/n! (exp), (-1)^k/(2k+1)! (sin), (-1)^k/(2k)! (cos), as fixed literals:
# evaluated by Horner's rule, the same few multiply-adds in the same order everywhere.
_EXP = tuple(1.0 / math.factorial(n) for n in range(15))
_SIN = tuple((-1.0 if k % 2 else 1.0) / math.factorial(2 * k + 1) for k in range(10))
_COS = tuple((-1.0 if k % 2 else 1.0) / math.factorial(2 * k) for k in range(10))


def _horner(coefficients: tuple[float, ...], x: float) -> float:
    total = 0.0
    for c in reversed(coefficients):
        total = total * x + c
    return total


def exp(x: float) -> float:
    if x != x:
        return x
    if x > 709.78:
        return math.inf
    if x < -745.13:
        return 0.0
    k = round(x * _INV_LN2)
    r = (x - k * _LN2_HI) - k * _LN2_LO  # |r| <= ln2 / 2
    return math.ldexp(_horner(_EXP, r), k)


def _sin_cos_reduced(r: float) -> tuple[float, float]:
    """sin and cos for |r| <= pi / 4, by their Taylor series."""
    r2 = r * r
    return r * _horner(_SIN, r2), _horner(_COS, r2)


def _quadrant(x: float) -> tuple[int, float, float]:
    k = round(x * _TWO_OVER_PI)
    r = (x - k * _PIO2_HI) - k * _PIO2_LO
    s, c = _sin_cos_reduced(r)
    return k & 3, s, c


def sin(x: float) -> float:
    q, s, c = _quadrant(x)
    return (s, c, -s, -c)[q]


def cos(x: float) -> float:
    q, s, c = _quadrant(x)
    return (c, -s, -c, s)[q]


def _atan(t: float) -> float:
    if t < 0:
        return -_atan(-t)
    if t > 1.0:
        return math.pi / 2 - _atan(1.0 / t)
    if t > _TAN_PI_12:
        return math.pi / 6 + _atan((t * _SQRT3 - 1.0) / (_SQRT3 + t))
    t2 = t * t
    term = total = t
    for n in range(3, 37, 2):  # |t| <= 0.268: the terms fall below 1e-20
        term *= -t2
        total += term / n
    return total


def atan2(y: float, x: float) -> float:
    if x > 0:
        return _atan(y / x)
    if x < 0:
        return _atan(y / x) + (math.pi if y >= 0 else -math.pi)
    if y > 0:
        return math.pi / 2
    if y < 0:
        return -math.pi / 2
    return 0.0


def log(x: float) -> float:
    """Natural log of a positive number."""
    m, e = math.frexp(x)  # x = m * 2**e, 0.5 <= m < 1
    if m < _SQRT_HALF:
        m *= 2.0
        e -= 1
    s = (m - 1.0) / (m + 1.0)  # |s| <= 0.172
    s2 = s * s
    term = total = s
    for n in range(3, 41, 2):
        term *= s2
        total += term / n
    return e * _LN2_HI + (2.0 * total + e * _LN2_LO)


def gauss(rng: random.Random, mu: float, sigma: float) -> float:
    """random.Random.gauss, step for step (the same draws, and its cached second value), with
    these functions in place of the platform's."""
    z = rng.gauss_next
    rng.gauss_next = None
    if z is None:
        x2pi = rng.random() * _TWO_PI
        g2rad = math.sqrt(-2.0 * log(1.0 - rng.random()))
        z = cos(x2pi) * g2rad
        rng.gauss_next = sin(x2pi) * g2rad
    return mu + z * sigma
