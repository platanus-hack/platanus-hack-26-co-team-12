"""Mide que le hace realmente un canal (WhatsApp, Telegram, Instagram...) a una
imagen. Los parametros del codec se fijan con estos numeros, no con supuestos.

Uso:
  1. python tools/measure_channel.py --make-probes probes/     # genera sondas
  2. mandar cada sonda por el canal y descargar el resultado
  3. python tools/measure_channel.py --compare probes/ recibidas/
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

STD_LUMA = np.array([
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99])


def estimate_quality(qtable: list[int]) -> int:
    """Invierte la escala de la IJG: q_k = clip((K1_k*S + 50)/100, 1, 255)."""
    best, err = 0, float("inf")
    for q in range(1, 101):
        s = 5000 / q if q < 50 else 200 - 2 * q
        pred = np.clip((STD_LUMA * s + 50) // 100, 1, 255)
        e = float(np.abs(pred - np.array(qtable[:64])).sum())
        if e < err:
            best, err = q, e
    return best


def make_probes(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(11)
    for w, h in [(640, 480), (1024, 768), (1600, 1200), (2400, 1800), (4032, 3024)]:
        yy, xx = np.mgrid[0:h, 0:w]
        base = 128 + 60 * np.sin(xx / 60.0) * np.cos(yy / 55.0) + rng.normal(0, 6, (h, w))
        img = np.clip(base, 0, 255).astype(np.uint8)
        rgb = np.stack([img, img, img], -1)
        # marcas de esquina para detectar recortes del canal
        rgb[:8, :8] = 255; rgb[-8:, -8:] = 0
        Image.fromarray(rgb).save(os.path.join(out_dir, f"probe_{w}x{h}.png"))
    print(f"sondas en {out_dir}: mandalas por el canal y guarda lo que llegue")


def compare(probe_dir: str, recv_dir: str) -> None:
    print(f"{'sonda':<18} {'enviado':>11} {'recibido':>11} {'factor':>7} {'calidad':>8} {'submuestreo':>12}")
    for name in sorted(os.listdir(probe_dir)):
        src = Image.open(os.path.join(probe_dir, name))
        stem = os.path.splitext(name)[0]
        got = [f for f in os.listdir(recv_dir) if f.startswith(stem)]
        if not got:
            print(f"{stem:<18} {src.size[0]}x{src.size[1]:<6} {'(falta)':>11}")
            continue
        dst = Image.open(os.path.join(recv_dir, got[0]))
        factor = max(dst.size) / max(src.size)
        q = qt = "-"
        if hasattr(dst, "quantization") and dst.quantization:
            tbl = list(dst.quantization.get(0, []))
            if len(tbl) >= 64:
                q = estimate_quality(tbl)
            qt = len(dst.quantization)
        sub = "4:2:0" if qt == 2 else ("4:4:4" if qt == 1 else "?")
        print(f"{stem:<18} {src.size[0]}x{src.size[1]:<6} {dst.size[0]}x{dst.size[1]:<6} "
              f"{factor:7.3f} {str(q):>8} {sub:>12}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-probes", metavar="DIR")
    ap.add_argument("--compare", nargs=2, metavar=("SONDAS", "RECIBIDAS"))
    a = ap.parse_args()
    if a.make_probes:
        make_probes(a.make_probes)
    elif a.compare:
        compare(*a.compare)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
