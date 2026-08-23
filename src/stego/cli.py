"""CLI: stego embed | extract | measure."""
from __future__ import annotations

import argparse
import os
import secrets
import sys

import numpy as np

from .covers import image_dct_qim as codec
from .image import loading
from .keys import derive


def _read(path: str) -> np.ndarray:
    # loading.open_rgb aplica orientacion EXIF, convierte a sRGB con el perfil
    # incrustado y compone el alfa sobre blanco. convert("RGB") a secas
    # descartaba las tres cosas en silencio.
    return loading.open_rgb(path)


def _passphrase(args) -> str:
    pw = args.passphrase or os.environ.get("STEGO_PASSPHRASE")
    if not pw:
        raise SystemExit("falta --passphrase o STEGO_PASSPHRASE")
    return pw


def cmd_embed(args) -> int:
    km = derive(_passphrase(args), tenant=args.tenant.encode())
    ident = bytes.fromhex(args.id) if args.id else secrets.token_bytes(16)
    if len(ident) != 16:
        raise SystemExit("--id debe ser de 16 bytes (32 hex)")
    # El CLI usaba el default del codec (2.0) mientras la web forzaba 6.0: las
    # dos rutas producian imagenes de calidad y robustez distintas sin decirlo.
    # Ahora la amplitud es un parametro explicito en ambas.
    marked = codec.embed(_read(args.inp), ident, km, delta=args.delta,
                         template_amp=args.template_amp,
                         template_mask=not args.no_mask)
    loading.save_rgb(marked, args.out, jpeg_quality=args.jpeg_quality)
    print(f"id={ident.hex()}")
    print(f"salida={args.out}")
    return 0


def cmd_extract(args) -> int:
    km = derive(_passphrase(args), tenant=args.tenant.encode())
    out, d = codec.extract(_read(args.inp), km, delta=args.delta, deep=args.deep)
    print(f"z={d.z:.2f} escala={d.scale:.4f} pilotBER={d.pilot_ber:.3f} "
          f"borrados={d.erasures} copias={d.tiles_seen:.0f}")
    if out is None:
        # La ausencia de marca NO prueba que el archivo sea ajeno: puede ser
        # propio y degradado. El producto nunca debe afirmar lo contrario.
        print(f"sin marca legible: {d.reason}")
        return 1
    print(f"id={out.hex()}")
    return 0


def cmd_verify(args) -> int:
    km = derive(_passphrase(args), tenant=args.tenant.encode())
    out, d, rep = codec.verify(_read(args.inp), km, delta=args.delta, deep=args.deep,
                               cell_blocks=args.cell_blocks)
    print(f"z={d.z:.2f} escala={d.scale:.4f} ganancia={d.gain:.2f} pilotBER={d.pilot_ber:.3f}")
    if out is None:
        print(f"sin marca legible: {d.reason}")
        return 1
    print(f"id={out.hex()}")
    if not rep.ok:
        print(f"integridad: no evaluable ({rep.reason})")
        return 0
    if rep.altered:
        print(f"INTEGRIDAD: alterada — {rep.tampered.sum()} de {rep.tampered.size} celdas "
              f"de {rep.cell_px} px ({rep.altered_fraction * 100:.1f}% de la imagen)")
        print(rep.ascii_map())
    else:
        print(f"integridad: sin alteracion local detectada "
              f"(celda {rep.cell_px} px, mediana {rep.median_ber:.3f})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stego")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("embed", cmd_embed), ("extract", cmd_extract), ("verify", cmd_verify)):
        p = sub.add_parser(name)
        p.add_argument("--in", dest="inp", required=True)
        p.add_argument("--passphrase")
        p.add_argument("--tenant", default="")
        p.add_argument("--delta", type=float, default=codec.DEFAULT_DELTA)
        p.set_defaults(func=fn)
        if name in ("extract", "verify"):
            p.add_argument("--deep", action="store_true",
                           help="barrido exhaustivo de escalas: ~90 s, solo para imagenes "
                                "con patron periodico fuerte que desvia la sincronia")
        if name == "verify":
            p.add_argument("--cell-blocks", type=int, default=None,
                           help="lado de la celda de analisis en bloques de 8 px "
                                "(por defecto 4 = 32 px)")
        if name == "embed":
            p.add_argument("--out", required=True)
            p.add_argument("--id", help="16 bytes en hex; aleatorio si se omite")
            p.add_argument("--jpeg-quality", type=int, default=95)
            p.add_argument("--template-amp", type=float, default=2.0,
                           help="amplitud de la plantilla de sincronia. Mas alta = "
                                "mejor sincronia en recortes chicos y mas visible")
            p.add_argument("--no-mask", action="store_true",
                           help="desactiva el enmascaramiento perceptual de la "
                                "plantilla (solo para comparar en el banco)")
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
