"""La misma marca, leida por region, detecta y localiza la edicion."""
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from stego.attacks import image as atk
from stego.covers import image_dct_qim as codec
from tests.conftest import IDENT, make_image

DELTA = 42.0


@pytest.fixture(scope="module")
def marcada():
    from stego.keys import derive
    km = derive("passphrase-de-prueba-larga-2026")
    return km, codec.embed(make_image("natural", h=512, w=640), IDENT, km, delta=DELTA)


def _verificar(km, arr, **kw):
    return codec.verify(np.asarray(arr), km, delta=DELTA, **kw)


@pytest.mark.parametrize("nombre,fn", [
    ("sin tocar", lambda a: a),
    ("JPEG Q75", lambda a: atk.jpeg(a, 75)),
    ("JPEG Q30", lambda a: atk.jpeg(a, 30)),
    ("canal WhatsApp", lambda a: atk.whatsapp(a)),
    ("brillo +20%", lambda a: np.asarray(ImageEnhance.Brightness(Image.fromarray(a)).enhance(1.2))),
])
def test_el_canal_no_dispara_falsas_alarmas(marcada, nombre, fn):
    """Un canal degrada la imagen entera de forma leve y uniforme: no es edicion."""
    km, m = marcada
    out, _, rep = _verificar(km, fn(m))
    assert out == IDENT, nombre
    assert rep.ok and not rep.altered, f"{nombre}: {rep.tampered.sum()} celdas marcadas"


def test_pegar_un_objeto_se_detecta_y_se_localiza(marcada):
    km, m = marcada
    p = Image.fromarray(m)
    ImageDraw.Draw(p).rectangle([200, 150, 420, 330], fill=(220, 40, 40))
    out, _, rep = _verificar(km, p)
    assert out == IDENT              # la procedencia sobrevive: para eso es robusta
    assert rep.altered               # pero la integridad la delata
    # las celdas marcadas caen dentro del rectangulo pegado, no repartidas
    ys, xs = np.nonzero(rep.tampered)
    assert 150 // rep.cell_px - 1 <= ys.mean() <= 330 // rep.cell_px + 1
    assert 200 // rep.cell_px - 1 <= xs.mean() <= 420 // rep.cell_px + 1


def test_desenfocar_una_zona_se_detecta(marcada):
    km, m = marcada
    p = Image.fromarray(m)
    z = p.crop((100, 100, 400, 350)).filter(ImageFilter.GaussianBlur(6))
    p.paste(z, (100, 100))
    out, _, rep = _verificar(km, p)
    assert out == IDENT
    assert rep.altered


def test_la_resolucion_de_deteccion_es_la_celda(marcada):
    """Una celda grande promedia mejor pero diluye las ediciones pequenas."""
    km, m = marcada
    p = Image.fromarray(m)
    ImageDraw.Draw(p).text((40, 40), "CONFIDENCIAL", fill=(255, 255, 0))
    _, _, fina = _verificar(km, p, cell_blocks=4)
    _, _, gruesa = _verificar(km, p, cell_blocks=16)
    assert fina.cell_px == 32 and gruesa.cell_px == 128
    assert fina.tampered.sum() >= gruesa.tampered.sum()


def test_sin_marca_no_hay_informe(km, natural):
    out, _, rep = codec.verify(natural, km, delta=DELTA)
    assert out is None and not rep.ok and rep.reason
