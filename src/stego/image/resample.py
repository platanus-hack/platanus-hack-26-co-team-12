"""Remuestreo con Pillow (Lanczos), el mismo tipo de filtro que usan los
canales reales al reescalar."""
from __future__ import annotations

import numpy as np
from PIL import Image


def resize_plane(plane: np.ndarray, size_wh: tuple[int, int]) -> np.ndarray:
    img = Image.fromarray(plane.astype(np.float32), mode="F")
    return np.asarray(img.resize(size_wh, Image.Resampling.LANCZOS), dtype=np.float64)


def base_size(h: int, w: int, long_side: int) -> tuple[int, int]:
    """Tamano (h, w) con el lado largo normalizado. Nunca amplia."""
    m = max(h, w)
    if m <= long_side:
        return h, w
    s = long_side / m
    return max(8, int(round(h * s))), max(8, int(round(w * s)))
