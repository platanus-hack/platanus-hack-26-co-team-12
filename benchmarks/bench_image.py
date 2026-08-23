"""Banco de robustez de imagen. Evalua SIEMPRE contra el identificador
realmente insertado (el defecto C6 de la bateria de audio original)."""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stego.attacks import image as atk  # noqa: E402
from stego.covers import image_dct_qim as codec  # noqa: E402
from stego.keys import derive  # noqa: E402


def synth(kind: str, h: int, w: int, seed: int) -> np.ndarray:
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    if kind == "liso":
        base = 128 + 50 * np.sin(xx / 200.0) + 30 * np.cos(yy / 180.0)
        noise = gaussian_filter(r.normal(0, 4, (h, w)), 3.0)
    elif kind == "texturizado":
        base = 120 + 40 * np.sin(xx / 40.0) * np.cos(yy / 35.0)
        noise = gaussian_filter(r.normal(0, 30, (h, w)), 0.8) * 2.5
    elif kind == "oscuro":
        base = 40 + 25 * np.sin(xx / 120.0)
        noise = gaussian_filter(r.normal(0, 8, (h, w)), 1.5)
    else:  # contraste
        base = np.where((xx // 120 + yy // 120) % 2 == 0, 205.0, 55.0)
        noise = gaussian_filter(r.normal(0, 10, (h, w)), 1.2)
    y = np.clip(base + noise, 0, 255)
    return np.stack([y, np.clip(y * 0.96 + 6, 0, 255), np.clip(y * 0.92 + 12, 0, 255)], -1).astype(np.uint8)


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def load(paths: list[str]) -> list[tuple[str, np.ndarray]]:
    out = []
    for p in paths:
        img = np.asarray(Image.open(p).convert("RGB"))
        out.append((os.path.basename(p), img))
    return out


CHAIN = {
    "sin ataque": lambda m: m,
    "JPEG Q90": lambda m: atk.jpeg(m, 90),
    "JPEG Q75": lambda m: atk.jpeg(m, 75),
    "JPEG Q50": lambda m: atk.jpeg(m, 50),
    "JPEG Q30": lambda m: atk.jpeg(m, 30),
    "recorte 800x600 @(13,37)": lambda m: atk.crop(m, 13, 37, 800, 600),
    "recorte 800x600 + Q75": lambda m: atk.jpeg(atk.crop(m, 13, 37, 800, 600), 75),
    "recorte 400x300 + Q75": lambda m: atk.jpeg(atk.crop(m, 71, 53, 400, 300), 75),
    "recorte 256x256 + Q75": lambda m: atk.jpeg(atk.crop(m, 91, 17, 256, 256), 75),
    "reescalado x0.75 + Q75": lambda m: atk.jpeg(atk.rescale(m, int(max(m.shape[:2]) * 0.75)), 75),
    "reescalado x0.5 + Q75": lambda m: atk.jpeg(atk.rescale(m, max(m.shape[:2]) // 2), 75),
    "WhatsApp (1600/Q75)": lambda m: atk.whatsapp(m),
    "recorte grande + WhatsApp": lambda m: atk.whatsapp(atk.crop(m, 13, 37,
                                                                 min(2200, m.shape[1] - 13),
                                                                 min(1700, m.shape[0] - 37))),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="*", default=[])
    ap.add_argument("--size", default="2400x1800")
    ap.add_argument("--delta", type=float, default=codec.DEFAULT_DELTA)
    ap.add_argument("--passphrase", default="passphrase-de-prueba-larga-2026")
    # Sin estas dos el banco no podia reproducir el perfil con el que la demo
    # firma de verdad, que es justo lo que un banco tiene que poder hacer.
    ap.add_argument("--template-amp", type=float, default=2.0,
                    help="amplitud de la plantilla de sincronia (la demo web usa 4.0)")
    ap.add_argument("--no-mask", action="store_true",
                    help="sin enmascaramiento perceptual, para comparar")
    args = ap.parse_args()

    h, w = (int(v) for v in args.size.lower().split("x")[::-1])
    imgs = load(args.images) if args.images else [
        (k, synth(k, h, w, i)) for i, k in enumerate(["liso", "texturizado", "oscuro", "contraste"])
    ]
    km = derive(args.passphrase)
    ident = bytes.fromhex("0123456789abcdef0123456789abcdef")

    marked = {}
    print(f"{'imagen':<14} {'tam':>11} {'PSNR(dB)':>9}")
    for name, img in imgs:
        m = codec.embed(img, ident, km, delta=args.delta,
                        template_amp=args.template_amp,
                        template_mask=not args.no_mask)
        marked[name] = m
        print(f"{name:<14} {img.shape[1]}x{img.shape[0]:<6} {psnr(img, m):9.2f}")

    print(f"\n{'ataque':<28} " + " ".join(f"{n[:10]:>11}" for n, _ in imgs) + "   total")
    totals = {}
    for aname, fn in CHAIN.items():
        row, oks = [], 0
        for name, _ in imgs:
            t0 = time.time()
            out, d = codec.extract(fn(marked[name]), km, delta=args.delta,
                                   template_amp=args.template_amp)
            ok = out == ident
            oks += ok
            row.append(f"{'OK' if ok else 'x':>4}/{d.z:5.1f}" + f"{'':2}")
        totals[aname] = oks
        print(f"{aname:<28} " + " ".join(row) + f"   {oks}/{len(imgs)}")

    print("\nfalsos positivos (passphrase incorrecta):")
    bad = derive("passphrase-completamente-distinta")
    fp = 0
    for name, _ in imgs:
        for aname in ("sin ataque", "JPEG Q75"):
            out, _ = codec.extract(CHAIN[aname](marked[name]), bad, delta=args.delta,
                                   template_amp=args.template_amp)
            fp += out is not None
    print(f"  {fp} de {len(imgs) * 2} intentos devolvieron algo (debe ser 0)")
    print(f"\nTOTAL: {sum(totals.values())}/{len(CHAIN) * len(imgs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
