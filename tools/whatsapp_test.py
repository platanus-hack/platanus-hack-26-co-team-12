"""Prepara y evalua la prueba de extremo a extremo por un canal real.

    # 1. preparar (marca, recorta y deja el recorte listo para enviar)
    python tools/whatsapp_test.py prepare --in fotos/ --out prueba/ --passphrase X

    # 2. mandar cada prueba/enviar_*.jpg por WhatsApp y guardar lo que llegue
    #    en prueba/recibidas/ con EL MISMO nombre

    # 3. evaluar
    python tools/whatsapp_test.py check --dir prueba/ --passphrase X
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stego.attacks import image as atk  # noqa: E402
from stego.covers import image_dct_qim as codec  # noqa: E402
from stego.keys import derive  # noqa: E402

CROP = (13, 37, 800, 600)  # offset y tamano de la prueba objetivo


def prepare(args) -> int:
    km = derive(args.passphrase)
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(os.path.join(args.out, "recibidas"), exist_ok=True)
    srcs = [os.path.join(args.inp, f) for f in sorted(os.listdir(args.inp))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not srcs:
        raise SystemExit(f"sin imagenes en {args.inp}")
    manifest = {}
    x, y, w, h = CROP
    for i, src in enumerate(srcs):
        img = np.asarray(Image.open(src).convert("RGB"))
        if img.shape[0] < y + h or img.shape[1] < x + w:
            print(f"  saltando {os.path.basename(src)}: menor que el recorte")
            continue
        ident = secrets.token_bytes(16)
        marked = codec.embed(img, ident, km, delta=args.delta)
        crop = atk.crop(marked, x, y, w, h)
        name = f"enviar_{i:02d}.jpg"
        Image.fromarray(crop).save(os.path.join(args.out, name), "JPEG", quality=95, subsampling=0)
        manifest[name] = {"id": ident.hex(), "origen": os.path.basename(src)}
        print(f"  {name}  id={ident.hex()}  origen={os.path.basename(src)}")
    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\n{len(manifest)} pruebas en {args.out}. Mandalas y guarda lo recibido "
          f"en {os.path.join(args.out, 'recibidas')} con el mismo nombre.")
    return 0


def check(args) -> int:
    km = derive(args.passphrase)
    with open(os.path.join(args.dir, "manifest.json")) as fh:
        manifest = json.load(fh)
    recv = os.path.join(args.dir, "recibidas")
    ok = miss = 0
    print(f"{'archivo':<16} {'resultado':<12} {'z':>6} {'escala':>7} {'pilotBER':>9} {'bor':>4}  origen")
    for name, meta in sorted(manifest.items()):
        cands = [f for f in os.listdir(recv) if os.path.splitext(f)[0] == os.path.splitext(name)[0]]
        if not cands:
            miss += 1
            print(f"{name:<16} {'(no llego)':<12}")
            continue
        img = np.asarray(Image.open(os.path.join(recv, cands[0])).convert("RGB"))
        out, d = codec.extract(img, km, delta=args.delta)
        good = out is not None and out.hex() == meta["id"]
        wrong = out is not None and not good
        ok += good
        res = "OK" if good else ("ID INCORRECTO" if wrong else "sin marca")
        print(f"{name:<16} {res:<12} {d.z:6.2f} {d.scale:7.4f} {d.pilot_ber:9.3f} {d.erasures:4d}  {meta['origen']}")
    total = len(manifest) - miss
    print(f"\naciertos: {ok}/{total}" + (f"  ({miss} no llegaron)" if miss else ""))
    print("Un 'ID INCORRECTO' seria un fallo grave: el AEAD deberia hacerlo imposible.")
    return 0 if ok == total and total else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.set_defaults(func=prepare)
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    c = sub.add_parser("check"); c.set_defaults(func=check)
    c.add_argument("--dir", required=True)
    for q in (p, c):
        q.add_argument("--passphrase", required=True)
        q.add_argument("--delta", type=float, default=codec.DEFAULT_DELTA)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
