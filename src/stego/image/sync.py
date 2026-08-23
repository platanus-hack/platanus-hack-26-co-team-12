"""Resincronizacion: escala y posicion desconocidas tras recorte + reescalado.

La plantilla aditiva periodica de layout.build hace de regla de medir: la
autocorrelacion de la imagen blanqueada da el paso de la reticula (y por tanto
la escala) y la correlacion cruzada con la plantilla da la posicion absoluta.
Rotacion y cizalla quedan fuera de alcance y se declaran como tales.

La escala necesita precision: un error relativo e desplaza los bloques del borde
en e*ancho pixeles, y por encima de ~2 px el QIM ya no se lee. De ahi el
refinado fino tras la busqueda gruesa.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import uniform_filter

from .layout import BLOCK, TEMPLATE_PX, TILE_BLOCKS, TILE_PX
from .resample import resize_plane

Z_ACCEPT = 5.0
BP_SMALL, BP_LARGE = 5, 33
FINE_SPAN = 0.02
MAX_DRIFT_PX = 0.35
"""Precision de escala exigida. Un error relativo e desplaza el borde de la
imagen en e*ancho pixeles; por encima de ~1 px el QIM ya no se lee. De ahi que
el refinado sea por biseccion hasta e < MAX_DRIFT_PX/ancho, y no un paso fijo:
con paso fijo del 0.12%, una imagen de 2400 px acumula 3 px de deriva."""
# Acotar el rango evita que una autocorrelacion enganada dispare escalas
# absurdas, que ademas cuestan segundos por el remuestreo. El limite superior
# permite recuperar una imagen que el canal redujo *por debajo* de la resolucion
# de marcado: ahi el verificador si tiene que ampliar.
SCALE_MIN, SCALE_MAX = 0.25, 2.2
# El limite superior permite recuperar una imagen que el canal redujo por debajo
# de la resolucion de marcado: ahi el verificador si tiene que ampliar. Llega a
# x0.5, que es la reduccion tipica de un canal agresivo.
COARSE_STEP = 0.02
MIN_SEPARATION = 0.03


@dataclass(frozen=True)
class Sync:
    scale: float
    tau_i: int
    tau_j: int
    gy: int
    gx: int
    z: float
    dy: int = 0
    dx: int = 0


def whiten(plane: np.ndarray) -> np.ndarray:
    """Paso banda 5-33 px: la plantilla vive ahi (ruido a resolucion de bloque
    suavizado a 8 px), el contenido de la imagen no."""
    return uniform_filter(plane, BP_SMALL, mode="nearest") - uniform_filter(plane, BP_LARGE, mode="nearest")


def _autocorr1d(x: np.ndarray) -> np.ndarray:
    x = x - x.mean()
    n = 1 << int(np.ceil(np.log2(len(x) * 2)))
    f = np.fft.rfft(x, n)
    ac = np.fft.irfft(f * np.conj(f), n)[: len(x)]
    return ac / (ac[0] + 1e-12)


def period_candidates(w: np.ndarray, n: int = 8, pmin: int = 20, pmax: int = 256) -> list[float]:
    """Periodos mas probables por suma armonica de la autocorrelacion proyectada,
    con refinamiento parabolico sub-pixel."""
    h, wd = w.shape
    pmax = int(min(pmax, max(h, wd) // 2))
    if pmax <= pmin + 2:
        return []
    acs = [_autocorr1d(w.sum(axis=1)), _autocorr1d(w.sum(axis=0))]
    ps = np.arange(pmin, pmax + 1)
    score = np.zeros(len(ps), dtype=np.float64)
    for ac in acs:
        for k in (1, 2, 3):
            lag = ps * k
            m = lag < len(ac)
            score[m] += ac[lag[m]] / k
    out: list[float] = []
    order = np.argsort(score)[::-1]
    for i in order:
        p = float(ps[i])
        if any(abs(p - q) < 6 for q in out):
            continue
        if 0 < i < len(ps) - 1:  # refinamiento parabolico
            a, b, c = score[i - 1], score[i], score[i + 1]
            den = a - 2 * b + c
            if den != 0:
                p += 0.5 * (a - c) / den
        out.append(p)
        if len(out) >= n:
            break
    return out


def _fold(w: np.ndarray, period: int) -> np.ndarray:
    h, wd = w.shape
    nh, nw = h // period, wd // period
    if nh < 1 or nw < 1:
        out = np.zeros((period, period))
        out[: min(h, period), : min(wd, period)] = w[:period, :period]
        return out
    return w[: nh * period, : nw * period].reshape(nh, period, nw, period).sum(axis=(0, 2))


def locate(w: np.ndarray, template: np.ndarray) -> tuple[int, int, float]:
    folded = _fold(w, TEMPLATE_PX)
    folded = folded - folded.mean()
    tpl = template - template.mean()
    corr = np.real(np.fft.ifft2(np.fft.fft2(folded) * np.conj(np.fft.fft2(tpl))))
    idx = int(np.argmax(corr))
    dy, dx = divmod(idx, TEMPLATE_PX)
    z = (corr.max() - corr.mean()) / (corr.std() + 1e-12)
    return dy, dx, float(z)


def _evaluate(plane: np.ndarray, template: np.ndarray, scale: float):
    if abs(scale - 1.0) < 1e-9:
        view = plane
    else:
        h, wd = plane.shape
        nh, nw = int(round(h * scale)), int(round(wd * scale))
        if min(nh, nw) < TEMPLATE_PX * 2 or max(nh, nw) > 6000:
            return None
        view = resize_plane(plane, (nw, nh))
    dy, dx, z = locate(whiten(view), template)
    return z, view, dy, dx, scale


def _in_range(s: float) -> bool:
    return SCALE_MIN <= s <= SCALE_MAX


def candidates(plane: np.ndarray, template: np.ndarray, *, search_scale: bool = True,
               top: int = 6) -> list[tuple[np.ndarray, Sync]]:
    """Escalas plausibles ordenadas por correlacion con la plantilla.

    Devuelve varias a proposito: z ordena bien pero no decide bien. Quien decide
    es el BER de pilotos, que mide directamente el desalineo del QIM; z solo
    sirve para no tener que evaluarlo en las ~50 escalas de la rejilla.
    """
    seen: dict[int, tuple] = {}

    def add(scale: float) -> tuple | None:
        key = int(round(scale * 1e6))
        if key in seen:
            return seen[key]
        r = _evaluate(plane, template, scale)
        if r is not None:
            seen[key] = r
        return r

    best = add(1.0)
    if search_scale:
        for c in (TEMPLATE_PX / p for p in period_candidates(whiten(plane))):
            if _in_range(c):
                r = add(c)
                if r is not None and (best is None or r[0] > best[0]):
                    best = r
        if best is None or best[0] < Z_ACCEPT:
            n = int(np.log(SCALE_MAX / SCALE_MIN) / COARSE_STEP) + 1
            for c in SCALE_MIN * np.exp(np.arange(n) * COARSE_STEP):
                r = add(float(c))
                if r is not None and (best is None or r[0] > best[0]):
                    best = r
        if best is not None and abs(best[4] - 1.0) > 1e-9:
            target = MAX_DRIFT_PX / max(best[1].shape)
            step = FINE_SPAN
            while step > target:
                for _ in range(3):
                    moved = False
                    for f in (-2, -1, 1, 2):
                        r = add(best[4] * (1.0 + f * step))
                        if r is not None and r[0] > best[0]:
                            best, moved = r, True
                    if not moved:
                        break
                step /= 2.0

    if not seen:
        return [(plane, Sync(1.0, 0, 0, 0, 0, 0.0))]
    # Diversidad obligatoria: sin ella las `top` candidatas salen casi identicas
    # (todas del mismo pico) y la escala correcta puede no entrar en la lista.
    # Un patron periodico en la propia imagen -- un tablero, una reja, una
    # fachada -- produce un pico espurio que domina a la marca.
    # La escala 1.0 -- que no hubo reescalado -- es la hipotesis a priori mas
    # probable y va siempre, exenta del filtro de diversidad: si no, una
    # candidata espuria a un 2% de distancia con z algo mayor la elimina.
    unity = seen.get(1_000_000)
    ranked: list[tuple] = [unity] if unity is not None else []
    for r in sorted(seen.values(), key=lambda r: -r[0]):
        if unity is not None and r is unity:
            continue
        if any(abs(r[4] / q[4] - 1.0) < MIN_SEPARATION for q in ranked):
            continue
        ranked.append(r)
        if len(ranked) >= top:
            break
    return [(view, from_offset(dy, dx, sc, float(z))) for z, view, dy, dx, sc in ranked]


def resolve(plane: np.ndarray, template: np.ndarray, *, search_scale: bool = True
            ) -> tuple[np.ndarray, Sync]:
    return candidates(plane, template, search_scale=search_scale, top=1)[0]


def from_offset(dy: int, dx: int, scale: float, z: float) -> Sync:
    """Reconstruye la sincronia desde un desplazamiento de plantilla."""
    dy, dx = int(dy) % TEMPLATE_PX, int(dx) % TEMPLATE_PX
    oy, ox = (-dy) % TEMPLATE_PX, (-dx) % TEMPLATE_PX
    gy, gx = dy % BLOCK, dx % BLOCK
    return Sync(scale=scale,
                tau_i=((gy + oy) // BLOCK) % TILE_BLOCKS,
                tau_j=((gx + ox) // BLOCK) % TILE_BLOCKS,
                gy=gy, gx=gx, z=z, dy=dy, dx=dx)
