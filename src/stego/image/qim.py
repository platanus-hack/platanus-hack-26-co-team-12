"""QIM / dither modulation (Chen-Wornell 2001).

El error de insercion es uniforme en (-D/2, D/2] con media cero e independiente
del contenido; el dither por bloque evita que la red sea visible en el
histograma del coeficiente.
"""
from __future__ import annotations

import numpy as np


def embed(c: np.ndarray, bits: np.ndarray, dither: np.ndarray, delta: np.ndarray) -> np.ndarray:
    off = dither + bits.astype(np.float64) * delta / 2.0
    return delta * np.round((c - off) / delta) + off


def hard(c: np.ndarray, dither: np.ndarray, delta: np.ndarray) -> np.ndarray:
    return (np.round(2.0 * (c - dither) / delta).astype(np.int64) % 2).astype(np.uint8)


def soft(c: np.ndarray, dither: np.ndarray, delta: np.ndarray) -> np.ndarray:
    """cos(2*pi*(c-d)/D): signo = bit (>0 -> 0, <0 -> 1), |valor| = fiabilidad."""
    return np.cos(2.0 * np.pi * (c - dither) / delta)


def phasor(c: np.ndarray, dither: np.ndarray, delta: np.ndarray) -> np.ndarray:
    """exp(i*2*pi*(c-d)/D): base de la correlacion de sincronia."""
    return np.exp(2j * np.pi * (c - dither) / delta)
