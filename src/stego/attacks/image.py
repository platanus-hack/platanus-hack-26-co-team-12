"""Ataques de imagen. A diferencia de la bateria de audio original, aqui se
evalua siempre contra el identificador realmente insertado."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image


def jpeg(rgb: np.ndarray, quality: int = 75, subsampling: int = 2) -> np.ndarray:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=quality, subsampling=subsampling)
    buf.seek(0)
    return np.asarray(Image.open(buf).convert("RGB"))


def crop(rgb: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    return rgb[y:y + h, x:x + w]


def rescale(rgb: np.ndarray, long_side: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    m = max(h, w)
    if m <= long_side:
        return rgb
    s = long_side / m
    img = Image.fromarray(rgb).resize((int(round(w * s)), int(round(h * s))), Image.Resampling.LANCZOS)
    return np.asarray(img)


def whatsapp(rgb: np.ndarray, long_side: int = 1600, quality: int = 75) -> np.ndarray:
    """Simulacion del canal: reescalado por encima del umbral + recompresion
    JPEG 4:2:0 + borrado de metadatos. Los parametros reales hay que medirlos."""
    return jpeg(rescale(rgb, long_side), quality=quality, subsampling=2)
