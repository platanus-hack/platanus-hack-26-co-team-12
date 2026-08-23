"""Chequeo de la demo contra el códec real. Sin navegador, sin dependencias extra.

    .venv/bin/python web/check.py                      # contenido sintético
    .venv/bin/python web/check.py fotos/la-que-voy-a-usar.jpg --firmas 3

Corré la segunda forma con la imagen que vayas a proyectar, antes de subir a
tarima. Falla si algún ataque deja de recuperar el identificador exacto en todas
las firmas, o si una passphrase incorrecta devuelve algo.

**Por qué varias firmas**: `payload.pack` usa un nonce nuevo por firma, así que
cada firma produce una imagen marcada distinta. Cerca del margen eso decide entre
recuperar y no, y una sola corrida no distingue «funciona» de «tuve suerte».
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.server import ATAQUES, TEMPLATE_AMP, _normalizar, _psnr, _verificar  # noqa: E402
from stego.covers import image_dct_qim as codec  # noqa: E402
from stego.keys import derive  # noqa: E402

PASS = "passphrase-de-prueba-larga-2026"


def sintetica(h: int = 768, w: int = 1024) -> np.ndarray:
    """Gradientes suaves. Una textura de periodo corto desvía el buscador de escala
    hacia la periodicidad de la propia imagen; está en docs/resultados.md."""
    r = np.random.default_rng(11)
    yy, xx = np.mgrid[0:h, 0:w]
    y = np.clip(128 + 50 * np.sin(xx / 200.0) + 30 * np.cos(yy / 180.0)
                + gaussian_filter(r.normal(0, 4, (h, w)), 3.0), 0, 255)
    return np.stack([y, np.clip(y * .96 + 6, 0, 255), np.clip(y * .92 + 12, 0, 255)], -1).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("imagenes", nargs="*", help="por defecto, una imagen sintética")
    ap.add_argument("--firmas", type=int, default=3)
    ap.add_argument("--delta", type=float, default=codec.DEFAULT_DELTA)
    ap.add_argument("--template-amp", type=float, default=TEMPLATE_AMP)
    args = ap.parse_args()

    imgs = ([(os.path.basename(p), _normalizar(np.asarray(Image.open(p).convert("RGB"))))
             for p in args.imagenes]
            or [("sintética", sintetica())])
    km = derive(PASS)

    print(f"Δ={args.delta:g}  template_amp={args.template_amp:g}  "
          f"{args.firmas} firmas por imagen\n")

    cuenta = {a["clave"]: [0, 0] for a in ATAQUES}
    psnrs = []
    for nombre, img in imgs:
        for _ in range(args.firmas):
            ident = secrets.token_bytes(16)
            m = codec.embed(img, ident, km, delta=args.delta, template_amp=args.template_amp)
            psnrs.append(_psnr(img, m))
            for a in ATAQUES:
                salida, _d, _v = _verificar(a["fn"](m), km, args.delta, args.template_amp)
                cuenta[a["clave"]][0] += salida == ident
                cuenta[a["clave"]][1] += 1
        print(f"  {nombre}  {img.shape[1]}×{img.shape[0]}")

    psnr = float(np.mean(psnrs))
    print(f"\nPSNR medio {psnr:.2f} dB")
    assert psnr > 36, f"marca demasiado visible: {psnr:.2f} dB"

    fallos = []
    for a in ATAQUES:
        ok, n = cuenta[a["clave"]]
        print(f"  {'OK   ' if ok == n else 'FALLA'} {a['titulo']:24} {ok}/{n}")
        if ok != n:
            fallos.append(f"{a['titulo']} ({ok}/{n})")

    # El número que no puede fallar nunca: un identificador inventado sería peor
    # que no encontrar nada.
    malo = derive("passphrase-completamente-distinta")
    ident = secrets.token_bytes(16)
    m = codec.embed(imgs[0][1], ident, km, delta=args.delta, template_amp=args.template_amp)
    for a in ATAQUES[:2]:
        salida, _d, _v = _verificar(a["fn"](m), malo, args.delta, args.template_amp)
        assert salida is None, f"falso positivo en «{a['titulo']}»: {salida.hex()}"
    print("  OK    0 falsos positivos con passphrase incorrecta")

    assert not fallos, "no recuperaron siempre: " + ", ".join(fallos)
    print(f"\n{len(ATAQUES)}/{len(ATAQUES)} ataques recuperan el identificador exacto "
          f"en las {args.firmas * len(imgs)} firmas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
