"""Mapa logistico en punto fijo de 64 bits, con resiembra HKDF.

Sustituye a src/utils/caos.py. Corrige C2 (bucle infinito por muestreo con
rechazo), C5 (dependencia de la libm en float64, ciclos cortos, sesgo por
r != 4) y la fuga llave<->posiciones: aqui el material que gobierna el
*layout* deriva de k_chaos y nunca se usa como keystream de cifrado.
"""
from __future__ import annotations

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

_MASK64 = (1 << 64) - 1
RESEED_EVERY = 1024
WARMUP = 100


def _hkdf_expand(key: bytes, info: bytes, length: int) -> bytes:
    return HKDFExpand(algorithm=hashes.SHA256(), length=length, info=info).derive(key)


class LogisticFP64:
    """x_{n+1} = 4*x*(1-x) en punto fijo: X' = (X * (2^64 - X)) >> 62.

    r = 4 exacto (no 3.999952): con r < 4 el atractor se trunca y los bits por
    umbral quedan sesgados. En punto fijo de 64 bits no se observan ciclos
    cortos, y el resultado es identico en cualquier plataforma.
    """

    def __init__(self, key: bytes, label: bytes = b"layout"):
        self._key = key
        self._label = label
        self._ctr = 0
        seed = _hkdf_expand(key, label + b"|seed", 8)
        self._x = int.from_bytes(seed, "big") | 1
        self._since_reseed = 0
        for _ in range(WARMUP):
            self._step()

    def _step(self) -> int:
        x = self._x
        x = (x * (_MASK64 + 1 - x)) >> 62
        x &= _MASK64
        if x == 0:  # punto fijo del mapa: resembrar en vez de quedarse pegado
            x = int.from_bytes(_hkdf_expand(self._key, self._label + b"|zero", 8), "big") | 1
        self._x = x
        self._since_reseed += 1
        if self._since_reseed >= RESEED_EVERY:
            self._reseed()
        return x

    def _reseed(self) -> None:
        self._ctr += 1
        inj = int.from_bytes(
            _hkdf_expand(self._key, self._label + b"|reseed" + self._ctr.to_bytes(8, "big"), 8),
            "big",
        )
        self._x = (self._x ^ inj) & _MASK64 or 1
        self._since_reseed = 0

    def u64(self) -> int:
        return self._step()

    def u32_array(self, n: int) -> np.ndarray:
        return np.fromiter((self._step() >> 32 for _ in range(n)), dtype=np.uint32, count=n)

    def unit_array(self, n: int) -> np.ndarray:
        """n valores en [0,1) a partir de los 32 bits altos.

        Nota: no se usa x directamente como uniforme (su densidad invariante es
        arcoseno); se toman bits altos, que si son equidistribuidos.
        """
        return self.u32_array(n).astype(np.float64) / 2.0**32

    def bits(self, n: int) -> np.ndarray:
        return (self.u32_array(n) >> 31).astype(np.uint8)


def chaos_permutation(n: int, rng: LogisticFP64) -> np.ndarray:
    """Fisher-Yates O(n). Reemplaza el muestreo con rechazo que no terminaba
    para n >= 20834 (C2)."""
    perm = np.arange(n, dtype=np.int64)
    if n < 2:
        return perm
    draws = rng.u32_array(n - 1)
    for i in range(n - 1, 0, -1):
        j = int(draws[n - 1 - i]) % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    return perm
