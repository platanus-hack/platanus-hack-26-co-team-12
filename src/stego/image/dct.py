"""DCT-II ortonormal 8x8 por lotes (FDCT de ITU-T T.81)."""
from __future__ import annotations

import numpy as np

BLOCK = 8


def _matrix() -> np.ndarray:
    k = np.arange(BLOCK)[:, None]
    n = np.arange(BLOCK)[None, :]
    d = np.cos((2 * n + 1) * k * np.pi / (2 * BLOCK)) * np.sqrt(2.0 / BLOCK)
    d[0] /= np.sqrt(2.0)
    return d


D = _matrix()


def to_blocks(plane: np.ndarray, gy: int = 0, gx: int = 0) -> np.ndarray:
    """(H,W) -> (nbi, nbj, 8, 8) desde la fase de malla (gy, gx)."""
    h, w = plane.shape
    nbi, nbj = (h - gy) // BLOCK, (w - gx) // BLOCK
    if nbi <= 0 or nbj <= 0:
        return np.zeros((0, 0, BLOCK, BLOCK))
    view = plane[gy:gy + nbi * BLOCK, gx:gx + nbj * BLOCK]
    return view.reshape(nbi, BLOCK, nbj, BLOCK).transpose(0, 2, 1, 3)


def from_blocks(blocks: np.ndarray) -> np.ndarray:
    nbi, nbj = blocks.shape[:2]
    return blocks.transpose(0, 2, 1, 3).reshape(nbi * BLOCK, nbj * BLOCK)


def fdct(blocks: np.ndarray) -> np.ndarray:
    return np.einsum("ij,mnjk,lk->mnil", D, blocks - 128.0, D, optimize=True)


def idct(coeffs: np.ndarray) -> np.ndarray:
    return np.einsum("ji,mnjk,kl->mnil", D, coeffs, D, optimize=True) + 128.0
