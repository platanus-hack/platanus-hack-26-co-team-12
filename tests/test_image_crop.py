import pytest

from stego.attacks import image as atk
from stego.covers import image_dct_qim as codec
from tests.conftest import IDENT, make_image


@pytest.mark.parametrize("x,y,w,h", [(13, 37, 384, 288), (71, 53, 320, 256), (0, 0, 256, 256)])
def test_recorte_con_desplazamiento_arbitrario(km, x, y, w, h):
    marked = codec.embed(make_image("natural"), IDENT, km)
    out, d = codec.extract(atk.crop(marked, x, y, w, h), km)
    assert out == IDENT, d


def test_recorte_mas_jpeg(km):
    marked = codec.embed(make_image("natural"), IDENT, km)
    out, d = codec.extract(atk.jpeg(atk.crop(marked, 13, 37, 384, 288), 75), km)
    assert out == IDENT, d


def test_recorte_demasiado_pequeno_no_miente(km):
    """Por debajo del minimo debe decir 'sin marca', nunca inventar un id."""
    marked = codec.embed(make_image("natural"), IDENT, km)
    out, d = codec.extract(atk.crop(marked, 5, 5, 130, 130), km)
    assert out is None or out == IDENT
    if out is None:
        assert d.reason
