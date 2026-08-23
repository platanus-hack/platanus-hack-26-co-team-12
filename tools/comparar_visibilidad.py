#!/usr/bin/env python
"""Compara a ojo cuánto se ve la marca, con tus propias fotos.

El problema que motivó este cambio era visual, así que la prueba también tiene
que serlo: un PSNR no te dice si el cielo se ve moteado. Esto firma la misma
imagen con las configuraciones que interesan y las deja en archivos para que las
abras y las mires.

    python tools/comparar_visibilidad.py foto.jpg
    python tools/comparar_visibilidad.py *.jpg --salida /tmp/comparacion

Qué mirar: las zonas **lisas** —cielo, pared, piel, un fondo plano—, al 100 % de
zoom. Ahí es donde aparecía el moteado y donde tiene que haber desaparecido.
Alterná entre `antes` y `ahora` en el visor; a tamaño reducido no se nota nada
en ninguna de las dos.

Además de las imágenes imprime, por configuración, el error medido separando
zonas planas de texturizadas, que es la medida que sí corresponde con lo que se
percibe.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stego.covers import image_dct_qim as codec  # noqa: E402
from stego.image import loading, masking  # noqa: E402
from stego.keys import derive  # noqa: E402

#: Las cuatro esquinas del compromiso. `antes` y `ahora` son las que importan.
PERFILES = [
    ("antes", 6.0, False, "amp 6.0 sin máscara — lo que producía el moteado"),
    ("solo-amp", 4.0, False, "amp 4.0 sin máscara — solo baja la amplitud"),
    ("solo-mascara", 6.0, True, "amp 6.0 con máscara — solo el enmascaramiento"),
    ("ahora", 4.0, True, "amp 4.0 con máscara — la configuración actual"),
]


def _psnr(a: np.ndarray, b: np.ndarray) -> float:
    e = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return float("inf") if e == 0 else float(10 * np.log10(255.0**2 / e))


def _rms(dif: np.ndarray, sel: np.ndarray | None = None) -> float:
    d = dif[sel] if sel is not None else dif
    return float(np.sqrt((d**2).mean())) if d.size else float("nan")


def comparar(ruta: str, salida: str, passphrase: str, delta: float,
             base_long: int | None) -> None:
    original = loading.open_rgb(ruta)
    km = derive(passphrase)
    ident = secrets.token_bytes(16)
    nombre = os.path.splitext(os.path.basename(ruta))[0]

    # Las zonas planas se derivan de la propia imagen, no se suponen.
    luma = original[..., 0].astype(np.float64)
    plano = masking.local_std(luma, masking.DEFAULTS["radius"]) < 3.0
    frac = float(plano.mean())

    base = os.path.join(salida, f"{nombre}-000-original.png")
    loading.save_rgb(original, base)

    print(f"\n{os.path.basename(ruta)}  ({original.shape[1]}×{original.shape[0]}, "
          f"{frac * 100:.0f}% de zona plana)")
    if frac < 0.02:
        print("  Aviso: casi no tiene zonas planas, que es donde se apreciaba el")
        print("  problema. Probá con una foto que tenga cielo, pared o un fondo liso.")
    print(f"  {'perfil':14} {'PSNR':>8}  {'error zona PLANA':>17}  {'error textura':>14}  recupera")
    print("  " + "-" * 72)

    for etiqueta, amp, mask, _desc in PERFILES:
        marcada = codec.embed(original, ident, km, delta=delta,
                              template_amp=amp, template_mask=mask,
                              base_long=base_long)
        destino = os.path.join(salida, f"{nombre}-{etiqueta}.png")
        loading.save_rgb(marcada, destino)

        dif = marcada.astype(np.float64) - original.astype(np.float64)
        sel = plano[..., None] & np.ones(3, bool) if plano.any() else None
        rms_plano = _rms(dif, np.repeat(plano[..., None], 3, axis=2)) if plano.any() else float("nan")
        rms_tex = _rms(dif, np.repeat(~plano[..., None], 3, axis=2)) if (~plano).any() else float("nan")

        recupera, _diag = codec.extract(marcada, km, delta=delta, template_amp=amp)
        print(f"  {etiqueta:14} {_psnr(original, marcada):7.2f} dB  "
              f"{rms_plano:14.2f} RMS  {rms_tex:11.2f} RMS  "
              f"{'sí' if recupera == ident else 'NO'}")

    print(f"\n  Archivos en {salida}/{nombre}-*.png")
    print("  Abrí 'antes' y 'ahora' al 100 % y mirá una zona lisa.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("imagenes", nargs="+", help="tus fotos (jpg, png, lo que lea Pillow)")
    ap.add_argument("--salida", default="comparacion", help="carpeta donde dejar los PNG")
    ap.add_argument("--passphrase", default="passphrase-de-prueba-larga-2026")
    ap.add_argument("--delta", type=float, default=codec.DEFAULT_DELTA)
    ap.add_argument("--nativo", action="store_true",
                    help="marcar en resolución nativa en vez de normalizar a 1024 px")
    args = ap.parse_args()

    os.makedirs(args.salida, exist_ok=True)
    for ruta in args.imagenes:
        try:
            comparar(ruta, args.salida, args.passphrase, args.delta,
                     None if args.nativo else codec.BASE_LONG)
        except Exception as exc:  # noqa: BLE001
            print(f"\n{ruta}: no pude procesarla ({exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
