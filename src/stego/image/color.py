"""RGB <-> YCbCr BT.601 rango completo (JFIF), en float64."""
from __future__ import annotations

import numpy as np

_FWD = np.array([[0.299, 0.587, 0.114],
                 [-0.168736, -0.331264, 0.5],
                 [0.5, -0.418688, -0.081312]])
_INV = np.array([[1.0, 0.0, 1.402],
                 [1.0, -0.344136, -0.714136],
                 [1.0, 1.772, 0.0]])


def rgb_to_ycbcr(rgb: np.ndarray) -> np.ndarray:
    out = rgb.astype(np.float64) @ _FWD.T
    out[..., 1:] += 128.0
    return out


def ycbcr_to_rgb(ycc: np.ndarray) -> np.ndarray:
    tmp = ycc.astype(np.float64).copy()
    tmp[..., 1:] -= 128.0
    return tmp @ _INV.T


def luma(rgb: np.ndarray) -> np.ndarray:
    return rgb.astype(np.float64) @ _FWD[0]
