"""Layout de la tesela, todo derivado de k_chaos.

Indexado por la posicion m dentro de la tesela (identica en todas), de modo que
el extractor lo regenera sin conocer la posicion absoluta. Anade una plantilla
aditiva periodica: es la que permite estimar la escala desconocida que introduce
un canal como WhatsApp al reescalar.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..chaos import LogisticFP64, chaos_permutation

BLOCK = 8
TILE_BLOCKS = 16
TILE_PX = TILE_BLOCKS * BLOCK  # 128
TEMPLATE_BLOCKS = 8
TEMPLATE_PX = TEMPLATE_BLOCKS * BLOCK  # 64
"""La plantilla de sincronia tiene periodo propio, mas corto que la tesela.

Plegar la imagen recibida modulo 64 en vez de 128 cuadruplica el numero de
copias que se suman, que es lo que decide si la correlacion se engancha. Un
recorte de 800x600 de una imagen de 2400 px deja solo 2x2 teselas de 128 px
-- insuficiente en contenido texturizado -- pero 5x4 de 64 px. La ambiguedad
que queda (la fase de tesela modulo 8 bloques) son 4 hipotesis, y se resuelven
con los pilotos, cuyo valor es conocido.
"""
CARRIERS = ((1, 0), (0, 1), (1, 1))  # baja frecuencia: sobreviven al reescalado
K = len(CARRIERS)
PATCH_H, PATCH_W = 2, 4
N_PATCHES = (TILE_BLOCKS // PATCH_H) * (TILE_BLOCKS // PATCH_W)  # 32
N_PILOT_PATCHES = 4  # 12.5%
N_DATA_PATCHES = N_PATCHES - N_PILOT_PATCHES  # 28
DATA_BITS = N_DATA_PATCHES * PATCH_H * PATCH_W * K  # 672
CODEWORD_BYTES = DATA_BITS // 8  # 84


@dataclass(frozen=True)
class Layout:
    dither: np.ndarray      # (T, T, K) float
    bit_index: np.ndarray   # (T, T, K) int64; -1 = piloto
    pilot_bit: np.ndarray   # (T, T, K) uint8
    template: np.ndarray    # (TILE_PX, TILE_PX) float, media cero
    delta: np.ndarray       # (K,) float


def _patch_blocks(p: int) -> tuple[np.ndarray, np.ndarray]:
    per_row = TILE_BLOCKS // PATCH_W
    pi, pj = divmod(p, per_row)
    r = np.repeat(np.arange(PATCH_H) + pi * PATCH_H, PATCH_W)
    c = np.tile(np.arange(PATCH_W) + pj * PATCH_W, PATCH_H)
    return r, c


def _smooth_template(rng: LogisticFP64, amp: float) -> np.ndarray:
    """Ruido pseudoaleatorio a resolucion de bloque, interpolado a pixeles.

    Se genera grueso a proposito: una plantilla de alta frecuencia no
    sobrevivria al JPEG ni al reescalado, que es justo para lo que sirve.
    """
    n = TEMPLATE_BLOCKS
    coarse = rng.unit_array(n * n).reshape(n, n)
    coarse = (coarse - 0.5) * 2.0 * amp
    up = np.repeat(np.repeat(coarse, BLOCK, axis=0), BLOCK, axis=1)
    # suavizado circular separable (media movil de 8 px) para evitar escalones
    k = np.ones(BLOCK) / BLOCK
    for axis in (0, 1):
        up = np.apply_along_axis(
            lambda v: np.real(np.fft.ifft(np.fft.fft(v) * np.fft.fft(k, len(v)))), axis, up
        )
    return up - up.mean()


def build(k_chaos: bytes, delta: float | np.ndarray, template_amp: float = 2.0) -> Layout:
    rng = LogisticFP64(k_chaos, b"layout")
    t = TILE_BLOCKS
    dither_u = rng.unit_array(t * t * K).reshape(t, t, K)
    delta_v = np.broadcast_to(np.asarray(delta, dtype=np.float64), (K,)).copy()
    dither = dither_u * delta_v

    order = chaos_permutation(N_PATCHES, rng)
    pilots, data = order[:N_PILOT_PATCHES], order[N_PILOT_PATCHES:]

    bit_index = np.full((t, t, K), -1, dtype=np.int64)
    pilot_bit = np.zeros((t, t, K), dtype=np.uint8)

    pb = rng.bits(N_PILOT_PATCHES * PATCH_H * PATCH_W * K)
    for n, p in enumerate(pilots):
        r, c = _patch_blocks(int(p))
        chunk = pb[n * PATCH_H * PATCH_W * K:(n + 1) * PATCH_H * PATCH_W * K].reshape(-1, K)
        pilot_bit[r, c, :] = chunk

    slots_per_patch = PATCH_H * PATCH_W * K  # 24 bits = 3 simbolos
    for n, p in enumerate(data):
        r, c = _patch_blocks(int(p))
        idx = np.arange(slots_per_patch) + n * slots_per_patch
        bit_index[r, c, :] = idx.reshape(-1, K)

    return Layout(
        dither=dither,
        bit_index=bit_index,
        pilot_bit=pilot_bit,
        template=_smooth_template(rng, template_amp),
        delta=delta_v,
    )
