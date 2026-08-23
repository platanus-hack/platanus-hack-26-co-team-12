"""Enmascaramiento perceptual de la plantilla.

Lo que hay que demostrar son dos cosas a la vez, porque están en tensión:

1. que la marca **se ve menos** justamente donde se veía (zonas planas), y
2. que **se sigue recuperando** el identificador.

Un cambio que consiga solo lo primero no sirve de nada.
"""

import numpy as np
import pytest

from tests.conftest import IDENT, make_image
from stego.covers import image_dct_qim as codec
from stego.image import masking


def _box_mean_bruto(a, r):
    h, w = a.shape
    out = np.empty_like(a, dtype=np.float64)
    for i in range(h):
        for j in range(w):
            i0, i1 = max(i - r, 0), min(i + r, h - 1)
            j0, j1 = max(j - r, 0), min(j + r, w - 1)
            # réplica de bordes: los píxeles fuera repiten el borde
            ii = np.clip(np.arange(i - r, i + r + 1), 0, h - 1)
            jj = np.clip(np.arange(j - r, j + r + 1), 0, w - 1)
            out[i, j] = a[np.ix_(ii, jj)].mean()
    return out


@pytest.mark.parametrize("shape,r", [((7, 5), 1), ((9, 9), 2), ((4, 11), 3)])
def test_box_mean_coincide_con_fuerza_bruta(shape, r):
    """La imagen integral es donde se cuela un off-by-one."""
    a = np.random.default_rng(0).uniform(0, 255, shape)
    assert np.allclose(masking.box_mean(a, r), _box_mean_bruto(a, r), atol=1e-9)


def test_la_ganancia_es_menor_en_lo_liso_que_en_lo_texturizado():
    liso = make_image("liso")[..., 0].astype(np.float64)
    tex = make_image("texturizado")[..., 0].astype(np.float64)
    g_liso = masking.perceptual_gain(liso).mean()
    g_tex = masking.perceptual_gain(tex).mean()
    assert g_liso < g_tex, f"liso {g_liso:.3f} deberia ser menor que texturizado {g_tex:.3f}"


def test_la_ganancia_es_positiva_y_acotada():
    """Nunca cero: anular la plantilla crea escalones duros en los bordes entre
    zonas, que son visibles por sí mismos, y deja al sincronizador sin señal."""
    g = masking.perceptual_gain(make_image("natural")[..., 0].astype(np.float64))
    assert g.min() > 0.0
    assert g.max() <= masking.DEFAULTS["boost_max"] + 1e-9


def test_dentro_de_una_imagen_la_ganancia_sigue_a_la_textura():
    """Mitad plana y mitad con ruido: la ganancia tiene que separarlas."""
    r = np.random.default_rng(3)
    y = np.full((256, 256), 128.0)
    y[:, 128:] += r.normal(0, 30, (256, 128))
    g = masking.perceptual_gain(np.clip(y, 0, 255))
    plana, texturizada = g[:, :100].mean(), g[:, 156:].mean()
    assert texturizada > 1.5 * plana, f"plana {plana:.3f} vs texturizada {texturizada:.3f}"


@pytest.mark.parametrize("kind", ["liso", "natural"])
def test_la_mascara_reduce_la_distorsion_donde_se_veia(km, kind):
    """El síntoma reportado era moteado en cielos y paredes. Aquí se mide."""
    img = make_image(kind)
    con = codec.embed(img, IDENT, km, template_amp=4.0, template_mask=True)
    sin = codec.embed(img, IDENT, km, template_amp=4.0, template_mask=False)

    base = img[..., 0].astype(np.float64)
    plano = masking.local_std(base, masking.DEFAULTS["radius"]) < 4.0
    if plano.sum() < 100:
        pytest.skip("esta imagen no tiene zonas suficientemente planas")

    def mse_en(m):
        d = m[..., 0].astype(np.float64) - base
        return float((d[plano] ** 2).mean())

    assert mse_en(con) < mse_en(sin), (
        f"en zonas planas la mascara deberia reducir el error: "
        f"con {mse_en(con):.2f} vs sin {mse_en(sin):.2f}")


@pytest.mark.parametrize("kind", ["natural", "texturizado", "liso"])
def test_se_sigue_recuperando_con_la_mascara(km, kind):
    """La otra mitad del trato: reducir visibilidad no puede romper la marca."""
    marcada = codec.embed(make_image(kind), IDENT, km, template_amp=4.0, template_mask=True)
    out, _diag = codec.extract(marcada, km)
    assert out == IDENT


def test_la_mascara_no_cambia_el_contrato_de_extraccion(km):
    """El extractor no conoce la máscara y no debe necesitarla: por eso la
    ganancia es positiva y solo repondera la correlación, sin mover el pico."""
    img = make_image("natural")
    marcada = codec.embed(img, IDENT, km, template_amp=4.0, template_mask=True)
    # extract() no recibe ningun parametro de mascara, a proposito
    out, _ = codec.extract(marcada, km)
    assert out == IDENT
