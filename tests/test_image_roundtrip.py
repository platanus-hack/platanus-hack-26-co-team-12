import numpy as np
import pytest

from stego.covers import image_dct_qim as codec
from tests.conftest import IDENT, make_image


def psnr(a, b):
    mse = ((a.astype(float) - b.astype(float)) ** 2).mean()
    return 10 * np.log10(255.0 ** 2 / mse)


@pytest.mark.parametrize("kind", ["natural", "liso", "texturizado"])
def test_roundtrip_sin_ataque(km, kind):
    img = make_image(kind)
    marked = codec.embed(img, IDENT, km)
    out, d = codec.extract(marked, km)
    assert out == IDENT, d
    assert d.pilot_ber == 0.0


def test_calidad_visual(km, natural):
    marked = codec.embed(natural, IDENT, km)
    assert psnr(natural, marked) > 38.0


def test_dimensiones_impares(km):
    img = make_image("natural", h=381, w=517)
    out, _ = codec.extract(codec.embed(img, IDENT, km), km)
    assert out == IDENT


def test_llave_incorrecta_no_da_falso_positivo(km, km_otro, natural):
    marked = codec.embed(natural, IDENT, km)
    out, d = codec.extract(marked, km_otro)
    assert out is None
    assert not d.ok


def test_imagen_sin_marcar_no_da_falso_positivo(km, natural):
    out, _ = codec.extract(natural, km)
    assert out is None


def test_imagen_menor_que_una_tesela(km):
    with pytest.raises(ValueError):
        codec.embed(make_image("natural", h=100, w=100), IDENT, km)


def test_identificadores_distintos_se_distinguen(km, natural):
    otro = bytes.fromhex("ffeeddccbbaa99887766554433221100")
    assert codec.extract(codec.embed(natural, otro, km), km)[0] == otro


@pytest.mark.parametrize("ident", [
    bytes.fromhex("deadbeefdeadbeefdeadbeefdeadbeef"),  # muy comprimible
    bytes(16),                                          # todo ceros
    b"A" * 16,
    bytes.fromhex("0123456789abcdef0123456789abcdef"),
])
def test_identificadores_comprimibles(km, natural, ident):
    """zlib acorta un identificador repetitivo, y eso cambiaria la longitud de
    la trama que el extractor ciego tiene que asumir."""
    out, d = codec.extract(codec.embed(natural, ident, km), km)
    assert out == ident, d
