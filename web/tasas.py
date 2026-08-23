"""Mide la tasa de recuperación de cada ataque y la escribe en `web/tasas.json`.

    .venv/bin/python web/tasas.py fotos/*.jpg --firmas 5

La interfaz lee ese archivo y muestra el porcentaje junto a cada ataque, así un
fallo en tarima es un resultado declarado y no una sorpresa. El número que se ve
en pantalla sale de acá, no de un juicio.

**Por qué hay que medir con varias firmas y no con una**: `payload.pack` genera un
nonce nuevo con `os.urandom` en cada firma, así que cada firma produce una imagen
marcada distinta. Cerca del margen —pocas teselas, plantilla débil frente al
contenido— eso decide entre recuperar y no. Una sola corrida no es una medida, es
una tirada.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.server import ATAQUES, TEMPLATE_AMP, _normalizar, _verificar  # noqa: E402
from stego.covers import image_dct_qim as codec  # noqa: E402
from stego.image import loading  # noqa: E402
from stego.keys import derive  # noqa: E402

SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasas.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("imagenes", nargs="+")
    ap.add_argument("--firmas", type=int, default=5, help="firmas por imagen")
    ap.add_argument("--passphrase", default="passphrase-de-prueba-larga-2026")
    ap.add_argument("--delta", type=float, default=codec.DEFAULT_DELTA)
    # El default tiene que ser el que usa el servidor, no otro: si no, las tasas
    # que la interfaz muestra en pantalla no corresponden al perfil con el que
    # realmente se firma.
    ap.add_argument("--template-amp", type=float, default=TEMPLATE_AMP)
    ap.add_argument("--no-mask", action="store_true",
                    help="mide sin enmascaramiento perceptual, para comparar")
    args = ap.parse_args()

    km = derive(args.passphrase)
    imgs = [(os.path.basename(p), _normalizar(loading.open_rgb(p)))
            for p in args.imagenes]

    cuenta = {a["clave"]: [0, 0] for a in ATAQUES}
    mses = []

    for nombre, img in imgs:
        for i in range(args.firmas):
            ident = secrets.token_bytes(16)   # firma nueva: nonce nuevo, marca distinta
            m = codec.embed(img, ident, km, delta=args.delta,
                            template_amp=args.template_amp,
                            template_mask=not args.no_mask)
            # Se acumula MSE, no dB. Promediar decibelios no es promediar error:
            # la media en dB la domina la peor imagen y da un numero mas bajo que
            # el PSNR del MSE agregado. El PSNR que se mostraba en pantalla estaba
            # sesgado por esto.
            mses.append(float(((img.astype(np.float64) - m.astype(np.float64)) ** 2).mean()))
            for a in ATAQUES:
                salida, _d, _via = _verificar(a["fn"](m), km, args.delta,
                                              template_amp=args.template_amp)
                cuenta[a["clave"]][0] += salida == ident
                cuenta[a["clave"]][1] += 1
        print(f"  {nombre}: {args.firmas} firmas", flush=True)

    datos = {
        "imagenes": [n for n, _ in imgs],
        "firmas_por_imagen": args.firmas,
        "intentos_por_ataque": args.firmas * len(imgs),
        "delta": args.delta,
        "template_amp": args.template_amp,
        "template_mask": not args.no_mask,
        "psnr_medio": round(10 * float(np.log10(255.0 ** 2 / np.mean(mses))), 2),
        "tasas": {k: {"ok": v[0], "n": v[1], "pct": round(100 * v[0] / v[1])}
                  for k, v in cuenta.items()},
    }
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)

    print(f"\nPSNR medio {datos['psnr_medio']} dB · "
          f"{datos['intentos_por_ataque']} intentos por ataque\n")
    for a in ATAQUES:
        t = datos["tasas"][a["clave"]]
        print(f"  {a['titulo']:24} {t['ok']:3}/{t['n']:<3} {t['pct']:3} %  "
              + "#" * round(20 * t["ok"] / t["n"]))
    print(f"\nescrito en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
