import os
import sys

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stego.keys import derive  # noqa: E402

PASSPHRASE = "passphrase-de-prueba-larga-2026"
IDENT = bytes.fromhex("0123456789abcdef0123456789abcdef")


@pytest.fixture(scope="session")
def km():
    return derive(PASSPHRASE)


@pytest.fixture(scope="session")
def km_otro():
    return derive("una-passphrase-completamente-distinta")


def make_image(kind="natural", h=384, w=512, seed=0):
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    if kind == "liso":
        y = 128 + 40 * np.sin(xx / 150.0) + gaussian_filter(r.normal(0, 3, (h, w)), 3.0)
    elif kind == "texturizado":
        y = 120 + 35 * np.sin(xx / 30.0) * np.cos(yy / 25.0) + gaussian_filter(r.normal(0, 25, (h, w)), 0.8) * 2
    elif kind == "saturado":
        y = np.where((xx // 60 + yy // 60) % 2 == 0, 252.0, 3.0)
    else:
        y = 130 + 45 * np.sin(xx / 90.0) + 25 * np.cos(yy / 70.0) + gaussian_filter(r.normal(0, 10, (h, w)), 1.5) * 2
    y = np.clip(y, 0, 255)
    return np.stack([y, np.clip(y * 0.96 + 6, 0, 255), np.clip(y * 0.92 + 12, 0, 255)], -1).astype(np.uint8)


@pytest.fixture(scope="session")
def natural():
    return make_image("natural")
