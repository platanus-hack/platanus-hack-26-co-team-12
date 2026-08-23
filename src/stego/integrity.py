"""Verificacion de integridad por region (marca semi-fragil).

La misma marca robusta sirve para las dos cosas segun como se lea:

- **Leida en global**, sobrevive a lo que degrada la imagen entera de forma leve
  y uniforme (recompresion JPEG, reescalado, el paso por WhatsApp). Eso da
  *procedencia*: de que copia salio el archivo.
- **Leida por region**, delata lo que destruye una zona localizada (pegar un
  objeto, poner texto, desenfocar un area). Eso da *integridad*, y ademas
  localiza donde.

La distincion no es un umbral arbitrario: una edicion es local y severa, un
canal es global y suave. Comparar cada tesela contra la mediana de las demas
separa ambos casos sin tener que calibrar nada por adelantado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import ecc, payload
from .image import dct, qim
from .image.layout import CODEWORD_BYTES, K, TILE_BLOCKS, Layout

MAD_FACTOR = 6.0
"""Desviaciones absolutas medianas por encima de la mediana. La MAD es robusta a
que una parte de las celdas este efectivamente rota, que es justo el caso que se
quiere detectar."""

EXTRA_SIGMA = 2.0
"""Margen sobre la cota de comparaciones multiples.

El BER por celda NO es cero ni en una imagen intacta: la extraccion promedia
cada bit sobre todas las copias de tesela, pero aqui se leen bloques sueltos.
Con celdas de 4x4 bloques son 48 bits por celda, asi que la estimacion tiene una
desviacion binomial de ~0.04 y el maximo sobre cientos de celdas se aleja sola
de la mediana. Un umbral absoluto fijo no sirve: hay que acotar el maximo
esperado de N muestras, de ahi el sqrt(2*ln N).
"""

CELL_BLOCKS = 4
"""Lado de la celda de analisis, en bloques de 8 px. Es la resolucion con la que
se localiza una edicion: 4 bloques = 32 px.

Es un compromiso. Una celda grande promedia mejor y da menos falsas alarmas,
pero diluye las ediciones pequenas: con la tesela entera (16 bloques, 128 px)
un texto sobreimpreso de 13x100 px pasa desapercibido. Una celda de 4 bloques
reune 48 bits, suficientes para decidir sin volverse ruidosa."""


@dataclass
class IntegrityReport:
    ok: bool = False
    identifier: bytes | None = None
    cell_px: int = CELL_BLOCKS * 8
    tile_ber: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    tampered: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=bool))
    median_ber: float = 0.0
    threshold: float = 0.0
    reason: str = ""

    @property
    def altered(self) -> bool:
        return bool(self.tampered.any())

    @property
    def altered_fraction(self) -> float:
        return float(self.tampered.mean()) if self.tampered.size else 0.0

    def ascii_map(self) -> str:
        """Mapa de la imagen: '.' intacto, '#' alterado."""
        if not self.tampered.size:
            return "(sin datos)"
        return "\n".join("".join("#" if v else "." for v in row) for row in self.tampered)


def _expected_slot_bits(lay: Layout, frame: bytes) -> np.ndarray:
    bits = ecc.bytes_to_bits(ecc.encode(frame, CODEWORD_BYTES))
    return np.where(lay.bit_index >= 0,
                    bits[np.clip(lay.bit_index, 0, None)],
                    lay.pilot_bit).astype(np.uint8)


def analyse(view: np.ndarray, lay: Layout, s, gain: float, frame: bytes,
            cell_blocks: int = CELL_BLOCKS) -> IntegrityReport:
    """Compara cada tesela del plano contra los bits que deberia llevar."""
    rep = IntegrityReport()
    expected = _expected_slot_bits(lay, frame)

    blocks = dct.to_blocks(view, s.gy, s.gx)
    if blocks.shape[0] < TILE_BLOCKS or blocks.shape[1] < TILE_BLOCKS:
        rep.reason = "imagen menor que una tesela"
        return rep
    coeffs = dct.fdct(blocks)
    nbi, nbj = coeffs.shape[:2]

    carriers = np.stack([coeffs[:, :, ky, kx] for ky, kx in ((1, 0), (0, 1), (1, 1))], axis=-1)
    if gain != 1.0:
        carriers = carriers / gain

    mi = (np.arange(nbi) + s.tau_i) % TILE_BLOCKS
    mj = (np.arange(nbj) + s.tau_j) % TILE_BLOCKS
    dither = lay.dither[mi][:, mj]
    got = qim.hard(carriers, dither, lay.delta)
    wrong = got != expected[mi][:, mj]

    # agregar en celdas espaciales: la resolucion con la que se localiza
    cb = max(1, int(cell_blocks))
    nti, ntj = nbi // cb, nbj // cb
    if nti < 1 or ntj < 1:
        rep.reason = "imagen menor que una celda de analisis"
        return rep
    cut = wrong[: nti * cb, : ntj * cb]
    per_tile = cut.reshape(nti, cb, ntj, cb, K).mean(axis=(1, 3, 4))

    med = float(np.median(per_tile))
    mad = float(np.median(np.abs(per_tile - med)))
    n_cells = max(per_tile.size, 2)
    n_bits = cb * cb * K
    # Suavizado: si la mediana es exactamente 0 la desviacion binomial colapsa
    # y el umbral se va a cero, marcando como alterada cualquier celda con un
    # solo bit erroneo. El piso es el propio grano de la medida, 1/n_bits.
    p_eff = max(med, 1.0 / n_bits)
    sd = float(np.sqrt(p_eff * (1.0 - p_eff) / n_bits))
    z = float(np.sqrt(2.0 * np.log(n_cells))) + EXTRA_SIGMA
    thr = max(med + MAD_FACTOR * mad, med + z * sd)

    rep.cell_px = cb * 8
    rep.tile_ber = per_tile
    rep.median_ber = med
    rep.threshold = thr
    rep.tampered = per_tile > thr
    rep.ok = True
    return rep
