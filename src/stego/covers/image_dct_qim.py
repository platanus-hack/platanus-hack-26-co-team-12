"""Codec de imagen: QIM sobre DCT 8x8 + plantilla de sincronia + RS + AEAD."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .. import ecc, payload
from ..keys import KeyMaterial
from ..image import color, dct, masking, qim, sync
from ..image.layout import CARRIERS, CODEWORD_BYTES, K, TILE_BLOCKS, Layout, build
from ..image.resample import base_size, resize_plane

DEFAULT_DELTA = 26.0
BASE_LONG = 1024
"""Lado largo al que se normaliza el marcado.

Marcar en resolucion base (y no en la nativa) hace que el verificador solo tenga
que *reducir* la imagen recibida para volver al paso nominal. Interpolar hacia
arriba no recupera lo que el canal descarto al reescalar: con marcado nativo, un
envio por WhatsApp que reduce a 1600 px se pierde aunque la sincronia acierte.
"""


@dataclass
class Diagnostics:
    z: float = 0.0
    scale: float = 1.0
    pilot_ber: float = 1.0
    erasures: int = 0
    gain: float = 1.0
    # estado de la lectura, para el analisis de integridad por region
    frame: bytes | None = None
    view: np.ndarray | None = None
    sync: sync.Sync | None = None
    tiles_seen: float = 0.0
    ok: bool = False
    reason: str = ""


def _tile_map(arr: np.ndarray, nbi: int, nbj: int, tau_i: int = 0, tau_j: int = 0) -> np.ndarray:
    """(T,T,...) -> (nbi,nbj,...) replicando la tesela con desfase (tau_i,tau_j)."""
    ii = (np.arange(nbi) + tau_i) % TILE_BLOCKS
    jj = (np.arange(nbj) + tau_j) % TILE_BLOCKS
    return arr[ii][:, jj]


def _carrier_view(coeffs: np.ndarray) -> np.ndarray:
    return np.stack([coeffs[:, :, ky, kx] for ky, kx in CARRIERS], axis=-1)


def _set_carriers(coeffs: np.ndarray, values: np.ndarray) -> None:
    for n, (ky, kx) in enumerate(CARRIERS):
        coeffs[:, :, ky, kx] = values[:, :, n]


def _mark_plane(y: np.ndarray, lay: Layout, slot_bits: np.ndarray,
                template_mask: bool = True) -> np.ndarray:
    # La plantilla va ANTES del QIM: si se sumara despues, su energia en los
    # portadores desplazaria cada coeficiente de forma sistematica por posicion
    # de tesela, un sesgo que no promedia al acumular copias.
    h, w = y.shape
    tpl = np.tile(lay.template, (h // lay.template.shape[0] + 1, w // lay.template.shape[1] + 1))
    tpl = tpl[:h, :w]

    # Enmascaramiento perceptual. Sin esto la plantilla se suma con amplitud
    # constante a todos los pixeles, y a amp=6.0 eso son +-6.9 niveles de gris de
    # un patron periodico de 64 px: en cielos, paredes y piel se ve como un
    # moteado, que es el sintoma que motivo este cambio. La ganancia baja en las
    # zonas planas y sube donde hay textura que lo tapa.
    #
    # No rompe la extraccion ciega: el sincronizador correlaciona contra el
    # PATRON, y una ganancia local positiva solo repondera los sumandos del
    # plegado. El pico no se mueve y el extractor no necesita conocer la mascara.
    # Lo que si cambia es la altura del pico, o sea la z de sincronia: es el
    # numero a vigilar al tocar los parametros de masking.DEFAULTS.
    if template_mask:
        tpl = tpl * masking.perceptual_gain(y)

    y = y + tpl
    blocks = dct.to_blocks(y)
    nbi, nbj = blocks.shape[:2]
    if nbi < TILE_BLOCKS or nbj < TILE_BLOCKS:
        raise ValueError("imagen menor que una tesela (128 px)")
    coeffs = dct.fdct(blocks)
    _set_carriers(coeffs, qim.embed(_carrier_view(coeffs),
                                    _tile_map(slot_bits, nbi, nbj),
                                    _tile_map(lay.dither, nbi, nbj), lay.delta))
    out = y.copy()
    out[: nbi * dct.BLOCK, : nbj * dct.BLOCK] = dct.from_blocks(dct.idct(coeffs))
    return out


def embed(rgb: np.ndarray, identifier: bytes, km: KeyMaterial, *,
          delta: float = DEFAULT_DELTA, template_amp: float = 2.0,
          base_long: int | None = BASE_LONG,
          template_mask: bool = True) -> np.ndarray:
    lay = build(km.k_chaos, delta, template_amp)
    # Sin compresion, y con la longitud verificada: el extractor es ciego y tiene
    # que asumir el tamano de la trama (OVERHEAD + payload_len) para saber el
    # nsym de Reed-Solomon. Si zlib acortara el cuerpo -- cosa que pasa con un
    # identificador repetitivo, no con uno aleatorio -- la trama saldria mas
    # corta, RS decodificaria con el nsym equivocado y la extraccion fallaria
    # con los pilotos perfectos. Comprimir 16 bytes no aporta nada de todos
    # modos; zlib sigue disponible en payload para quien gestione la longitud.
    frame = payload.pack(km.k_cipher, identifier, compress=False)
    if len(frame) != payload.frame_len(len(identifier)):
        raise ValueError(
            f"trama de {len(frame)} B; el extractor ciego espera "
            f"{payload.frame_len(len(identifier))} B")
    bits = ecc.bytes_to_bits(ecc.encode(frame, CODEWORD_BYTES))
    slot_bits = np.where(lay.bit_index >= 0,
                         bits[np.clip(lay.bit_index, 0, None)],
                         lay.pilot_bit).astype(np.uint8)

    ycc = color.rgb_to_ycbcr(rgb)
    y = ycc[..., 0]
    h, w = y.shape

    if base_long is None or max(h, w) <= base_long:
        marked = _mark_plane(y, lay, slot_bits, template_mask)
    else:
        bh, bw = base_size(h, w, base_long)
        y_base = resize_plane(y, (bw, bh))
        residual = _mark_plane(y_base, lay, slot_bits, template_mask) - y_base
        marked = y + resize_plane(residual, (w, h))

    ycc[..., 0] = np.clip(marked, 0.0, 255.0)
    # np.rint y no astype a secas: astype TRUNCA hacia cero, y como la ida y
    # vuelta de color deja valores del tipo 199.99999998, la mitad de los
    # canales-pixel perdian un nivel. Era un oscurecimiento sistematico del
    # 0.2 % sobre TODA la imagen, croma incluida, que la marca ni siquiera toca.
    return np.rint(np.clip(color.ycbcr_to_rgb(ycc), 0, 255)).astype(np.uint8)


def _accumulate(coeffs: np.ndarray, lay: Layout, s: sync.Sync,
                gain: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    nbi, nbj = coeffs.shape[:2]
    d = _tile_map(lay.dither, nbi, nbj, s.tau_i, s.tau_j)
    view = _carrier_view(coeffs)
    if gain != 1.0:
        view = view / gain
    soft = qim.soft(view, d, lay.delta)

    mi = (np.arange(nbi) + s.tau_i) % TILE_BLOCKS
    mj = (np.arange(nbj) + s.tau_j) % TILE_BLOCKS
    flat = (mi[:, None] * TILE_BLOCKS + mj[None, :]).ravel()
    n = TILE_BLOCKS * TILE_BLOCKS
    acc = np.stack([np.bincount(flat, weights=soft[:, :, k].ravel(), minlength=n) for k in range(K)],
                   axis=-1).reshape(TILE_BLOCKS, TILE_BLOCKS, K)
    cnt = np.repeat(np.bincount(flat, minlength=n)[:, None], K, axis=1).reshape(TILE_BLOCKS, TILE_BLOCKS, K)
    return acc, cnt.astype(np.float64)


MIN_PILOT_RATIO = 0.8


def _better(ber: float, n_seen: int, best) -> bool:
    """Compara candidatas de *escalas distintas*.

    Gana el menor BER de pilotos, pero solo si no pierde cobertura: una escala
    equivocada puede dejar muy pocos pilotos visibles y sacar un BER bajo por
    azar. Exigir BER cero no sirve como criterio, porque una candidata correcta
    puede necesitar el refinado sub-pixel para llegar a cero, y ese refinado
    ocurre despues de elegirla.
    """
    return n_seen >= MIN_PILOT_RATIO * best[4] and ber < best[3]


ALIGN_SPAN = 2
"""La correlacion con la plantilla puede errar 1-2 px porque su autocorrelacion
es ancha (es suave por diseno, para sobrevivir al JPEG). Un solo pixel de
desalineo ya degrada el QIM, asi que se afina con los pilotos, que es
exactamente para lo que sirven: su valor es conocido."""


def _align(y: np.ndarray, lay: Layout, s0: sync.Sync, span: int = ALIGN_SPAN,
           gain: float = 1.0):
    """Afina el desplazamiento y resuelve la fase de tesela.

    La plantilla tiene periodo 64 px y la tesela 128, asi que la sincronia deja
    la fase de tesela determinada solo modulo 8 bloques: quedan 4 hipotesis
    (+0 u +8 en cada eje). Se deciden con los pilotos, igual que el ajuste fino
    de +-2 px, porque su valor es conocido.
    """
    pilots = lay.bit_index < 0
    half = TILE_BLOCKS // 2
    cache: dict[tuple[int, int], np.ndarray] = {}
    best = None
    for ddy in range(-span, span + 1):
        for ddx in range(-span, span + 1):
            base = sync.from_offset(s0.dy + ddy, s0.dx + ddx, s0.scale, s0.z)
            key = (base.gy, base.gx)
            if key not in cache:
                blocks = dct.to_blocks(y, base.gy, base.gx)
                if blocks.shape[0] < 1 or blocks.shape[1] < 1:
                    continue
                cache[key] = dct.fdct(blocks)
            coeffs = cache[key]
            for hi in (0, half):
                for hj in (0, half):
                    s = sync.Sync(base.scale, (base.tau_i + hi) % TILE_BLOCKS,
                                  (base.tau_j + hj) % TILE_BLOCKS,
                                  base.gy, base.gx, base.z, base.dy, base.dx)
                    acc, cnt = _accumulate(coeffs, lay, s, gain)
                    seen = pilots & (cnt > 0)
                    if not seen.any():
                        continue
                    ber = float(((acc[seen] < 0).astype(np.uint8) != lay.pilot_bit[seen]).mean())
                    # dentro de una misma escala, cualquier mejora vale: la
                    # cobertura de pilotos apenas cambia entre desplazamientos
                    if best is None or ber < best[3]:
                        best = (s, acc, cnt, ber, int(seen.sum()), gain)
                    if ber == 0.0:
                        return best
    return best


SCALE_REFINE_SPAN, SCALE_REFINE_STEP = 0.004, 0.0004
SUBPIXEL_STEP = 1.0 / 3.0
HOPELESS_BER = 0.35
"""Por encima de este BER de pilotos no hay marca que recuperar: el valor
esperado sin marca es 0.5.

Ojo con interpretarlo a la ligera: el BER que se compara es el *minimo* sobre
muchos intentos de alineacion, y con 96 pilotos el minimo sobre miles de
intentos aleatorios baja hasta ~0.31 por puro azar. Por eso el corte no basta
por si solo y el barrido exhaustivo es opcional (`deep`)."""

FALLBACK_BER = 0.15
GAIN_COARSE = (0.60, 1.40, 0.05)
GAIN_FINE_SPAN, GAIN_FINE_STEP = 0.05, 0.005


def _refine_gain(view: np.ndarray, lay: Layout, s0: sync.Sync, best):
    """Compensa el escalado de amplitud de los coeficientes portadores.

    El QIM es fragil a la ganancia: si el canal atenua el coeficiente por un
    factor a != 1, la retícula del cuantizador queda desplazada y
    round(2(c-d)/D) mod 2 da mal aunque el coeficiente conserve toda su
    informacion. Medido en el ciclo reducir-recomprimir-ampliar: la ganancia del
    portador cae a ~0.75 con una reduccion a x0.5.

    La ganancia solo afecta a los valores blandos, asi que la DCT se calcula una
    sola vez y el barrido es puro `_accumulate`. Recalcularla por candidata
    costaba dos ordenes de magnitud mas.
    """
    blocks = dct.to_blocks(view, s0.gy, s0.gx)
    if blocks.shape[0] < 1 or blocks.shape[1] < 1:
        return best
    coeffs = dct.fdct(blocks)
    pilots = lay.bit_index < 0
    half = TILE_BLOCKS // 2

    def try_gain(g: float, cur):
        for hi in (0, half):
            for hj in (0, half):
                s = sync.Sync(s0.scale, (s0.tau_i + hi) % TILE_BLOCKS,
                              (s0.tau_j + hj) % TILE_BLOCKS,
                              s0.gy, s0.gx, s0.z, s0.dy, s0.dx)
                acc, cnt = _accumulate(coeffs, lay, s, g)
                seen = pilots & (cnt > 0)
                if not seen.any():
                    continue
                ber = float(((acc[seen] < 0).astype(np.uint8) != lay.pilot_bit[seen]).mean())
                if ber < cur[3]:
                    cur = (s, acc, cnt, ber, int(seen.sum()), g)
        return cur

    lo, hi_, step = GAIN_COARSE
    for g in np.arange(lo, hi_ + 1e-9, step):
        best = try_gain(float(g), best)
        if best[3] == 0.0:
            return best
    g0 = best[5]
    for g in np.arange(g0 - GAIN_FINE_SPAN, g0 + GAIN_FINE_SPAN + 1e-9, GAIN_FINE_STEP):
        best = try_gain(float(g), best)
        if best[3] == 0.0:
            return best
    return best



def _scan_by_pilots(plane: np.ndarray, lay: Layout, best):
    """Ultimo recurso: barrer la rejilla de escalas decidiendo por pilotos.

    Hace falta cuando la propia imagen tiene estructura periodica fuerte -- un
    tablero, una reja, una fachada -- que produce un pico de correlacion mas
    alto que la marca y desvia la busqueda por plantilla.
    """
    n = int(np.log(sync.SCALE_MAX / sync.SCALE_MIN) / sync.COARSE_STEP) + 1
    h, w = plane.shape
    for sc in sync.SCALE_MIN * np.exp(np.arange(n) * sync.COARSE_STEP):
        nh, nw = int(round(h * sc)), int(round(w * sc))
        if min(nh, nw) < 2 * TILE_BLOCKS * dct.BLOCK:
            continue
        view = resize_plane(plane, (nw, nh))
        _, s = sync.resolve(view, lay.template, search_scale=False)
        cand = _align(view, lay,
                      sync.Sync(float(sc), s.tau_i, s.tau_j, s.gy, s.gx, s.z, s.dy, s.dx),
                      span=1)
        if cand is not None and _better(cand[3], cand[4], best):
            best = cand
            if cand[3] == 0.0:
                return best
    return best


def _refine_subpixel(view: np.ndarray, lay: Layout, s0: sync.Sync, best):
    """Corrige el resto fraccionario de la malla.

    Un recorte en pixeles nativos cae en posicion *fraccionaria* a resolucion
    base: recortar en (13,37) de una imagen de 2400 px marcada a 1024 equivale a
    (5.55, 15.79). Medio pixel ya basta para romper el QIM en contenido
    texturizado, y la alineacion entera no puede corregirlo.
    """
    offs = (-SUBPIXEL_STEP, 0.0, SUBPIXEL_STEP)
    for fy in offs:
        for fx in offs:
            if fy == 0.0 and fx == 0.0:
                continue
            shifted = ndimage.shift(view, (fy, fx), order=3, mode="nearest")
            # span=0: el desplazamiento entero ya esta resuelto; aqui solo se
            # prueba el resto fraccionario
            cand = _align(shifted, lay, s0, span=0)
            if cand is not None and _better(cand[3], cand[4], best):
                best = cand
                if cand[3] == 0.0:
                    return best
    return best


def _view_for(plane: np.ndarray, s: sync.Sync) -> np.ndarray:
    if abs(s.scale - 1.0) < 1e-9:
        return plane
    h, w = plane.shape
    return resize_plane(plane, (int(round(w * s.scale)), int(round(h * s.scale))))


def _refine_scale(plane: np.ndarray, lay: Layout, s0: sync.Sync, best):
    h, w = plane.shape
    n = int(SCALE_REFINE_SPAN / SCALE_REFINE_STEP)
    for i in range(-n, n + 1):
        if i == 0:
            continue
        sc = s0.scale * (1.0 + i * SCALE_REFINE_STEP)
        nh, nw = int(round(h * sc)), int(round(w * sc))
        if min(nh, nw) < 128:
            continue
        view = resize_plane(plane, (nw, nh))
        _, s2 = sync.resolve(view, lay.template, search_scale=False)
        cand = _align(view, lay, sync.Sync(sc, s2.tau_i, s2.tau_j, s2.gy, s2.gx, s2.z, s2.dy, s2.dx), span=1)
        if cand is not None and _better(cand[3], cand[4], best):
            best = cand
            if cand[3] == 0.0:
                break
    return best


def extract(rgb: np.ndarray, km: KeyMaterial, *, delta: float = DEFAULT_DELTA,
            template_amp: float = 2.0, payload_len: int = 16,
            search_scale: bool = True, deep: bool = False) -> tuple[bytes | None, Diagnostics]:
    """Recupera el identificador de una imagen marcada.

    `deep` activa el barrido exhaustivo de escalas decidiendo por pilotos. Esta
    desactivado por defecto porque cuesta ~90 s y solo ayuda cuando la propia
    imagen tiene estructura periodica fuerte que desvia la sincronia; sin el, un
    archivo ajeno se descarta en un par de segundos en vez de en minuto y medio.
    """
    lay = build(km.k_chaos, delta, template_amp)
    diag = Diagnostics()

    plane = color.luma(rgb.astype(np.float64))

    # Camino rapido: la mayoria de los archivos llegan a su resolucion de
    # marcado. Probar la escala 1.0 antes de buscar evita la rejilla completa
    # -- que cuesta segundos -- en el caso comun.
    _, s1 = sync.resolve(plane, lay.template, search_scale=False)
    best = _align(plane, lay, s1)

    if best is None or best[3] > 0.0:
        for view, s in sync.candidates(plane, lay.template, search_scale=search_scale):
            cand = _align(view, lay, s)
            if cand is not None and (best is None or _better(cand[3], cand[4], best)):
                best = cand
            if best is not None and best[3] == 0.0:
                break
    if best is not None:
        diag.z, diag.scale = best[0].z, best[0].scale
    if best is None:
        diag.reason = "imagen demasiado pequena"
        return None, diag
    if best[3] > HOPELESS_BER and not deep:
        s, acc, cnt, diag.pilot_ber = best[:4]
        diag.z, diag.scale, diag.gain = s.z, s.scale, best[5]
        diag.reason = f"sin marca (BER de pilotos {best[3]:.2f}, esperado 0.5 sin marca)"
        return None, diag

    # La correlacion con la plantilla no discrimina la escala con suficiente
    # finura en contenido texturizado. El BER de pilotos si: mide directamente
    # el desalineo del QIM, que es lo que importa.
    if best[3] > 0.0 and search_scale and abs(best[0].scale - 1.0) > 1e-9:
        best = _refine_scale(plane, lay, best[0], best)
    if best[3] > 0.0:
        best = _refine_subpixel(_view_for(plane, best[0]), lay, best[0], best)
    if best[3] > 0.0:
        best = _refine_gain(_view_for(plane, best[0]), lay, best[0], best)
    if deep and FALLBACK_BER < best[3] <= HOPELESS_BER and search_scale:
        best = _scan_by_pilots(plane, lay, best)
        if best[3] > 0.0:
            best = _refine_subpixel(_view_for(plane, best[0]), lay, best[0], best)

    s, acc, cnt, diag.pilot_ber = best[:4]
    diag.gain = best[5]
    diag.z, diag.scale = s.z, s.scale
    diag.tiles_seen = float(cnt.max())

    nbits = CODEWORD_BYTES * 8
    bits = np.zeros(nbits, dtype=np.uint8)
    rel = np.zeros(nbits)
    seen = np.zeros(nbits, dtype=bool)
    data = lay.bit_index >= 0
    idx = lay.bit_index[data]
    bits[idx] = (acc[data] < 0).astype(np.uint8)
    rel[idx] = np.abs(acc[data]) / np.maximum(cnt[data], 1)
    seen[idx] = cnt[data] > 0

    codeword = ecc.bits_to_bytes(bits)
    flen = payload.frame_len(payload_len)
    budget = CODEWORD_BYTES - flen

    unseen = {int(i) for i in np.flatnonzero(~seen) // 8}
    diag.erasures = len(unseen)
    if len(unseen) > budget:
        diag.reason = f"demasiados borrados ({len(unseen)})"
        return None, diag

    # Fiabilidad por simbolo: el bit mas debil de sus 8. Marcar los peores como
    # borrados aprovecha que RS corrige s <= n-k borrados frente a 2e <= n-k
    # errores. Probar varios presupuestos es seguro porque el que decide es el
    # tag AEAD (falso positivo 2^-128), no un umbral de correlacion.
    sym_rel = rel.reshape(CODEWORD_BYTES, 8).min(axis=1)
    sym_rel[sorted(unseen)] = -1.0
    order = [int(i) for i in np.argsort(sym_rel)]

    last = ""
    for n_er in (len(unseen), 8, 16, 24, 32, budget):
        n_er = max(n_er, len(unseen))
        if n_er > budget:
            continue
        er = sorted(order[:n_er])
        try:
            frame = ecc.decode(codeword, flen, er)
            out = payload.unpack(km.k_cipher, frame)
        except (ecc.DecodeFailed, payload.BadFrame) as exc:
            last = str(exc)
            continue
        diag.ok, diag.erasures = True, n_er
        # El plano se reconstruye a la escala elegida. Un posible resto
        # sub-pixel sube el BER de todas las teselas por igual, y el criterio de
        # integridad es relativo a la mediana: no lo afecta.
        diag.frame, diag.view, diag.sync = frame, _view_for(plane, s), s
        return out, diag

    diag.reason = last
    return None, diag


def verify(rgb: np.ndarray, km: KeyMaterial, *, cell_blocks: int | None = None, **kw):
    """Lee la marca y ademas analiza su integridad region por region.

    Devuelve (identificador, diagnosticos, informe de integridad). El informe
    dice que teselas no llevan los bits que deberian: ahi es donde la imagen fue
    editada. Un canal como WhatsApp degrada todo por igual y no marca nada; una
    edicion local se delata sola.
    """
    from ..integrity import IntegrityReport, analyse

    out, diag = extract(rgb, km, **kw)
    if out is None or diag.frame is None or diag.view is None:
        return out, diag, IntegrityReport(reason=diag.reason or "sin marca legible")
    lay = build(km.k_chaos, kw.get("delta", DEFAULT_DELTA), kw.get("template_amp", 2.0))
    from ..integrity import CELL_BLOCKS
    rep = analyse(diag.view, lay, diag.sync, diag.gain, diag.frame,
                  cell_blocks=cell_blocks or CELL_BLOCKS)
    rep.identifier = out
    return out, diag, rep
