"""Carga y guardado: lo que se descartaba en silencio.

Estas pruebas cubren los tres cambios que el usuario atribuía a la marca y que la
marca nunca hizo: viraje de color por perder el perfil ICC, rotación por ignorar
la orientación EXIF, y fondos raros por descartar el canal alfa sin componer.

No necesitan el códec: son de entrada/salida pura.
"""

import io

import numpy as np
import pytest
from PIL import Image, ImageCms, ImageOps

from stego.image import loading


def _a_bytes(im, fmt="PNG", **kw):
    buf = io.BytesIO()
    im.save(buf, fmt, **kw)
    buf.seek(0)
    return buf


def test_el_alfa_se_compone_sobre_blanco_y_no_revela_lo_de_debajo():
    """convert("RGB") sobre un RGBA transparente devuelve el color oculto.

    Un logo rojo con alfa 0 salía rojo en vez de blanco: el cambio más brusco de
    todos los que se reportaron.
    """
    rgba = Image.new("RGBA", (8, 8), (255, 0, 0, 0))  # rojo totalmente transparente
    crudo = np.asarray(Image.open(_a_bytes(rgba)).convert("RGB"))
    assert tuple(crudo[0, 0]) == (255, 0, 0), "asi se comportaba antes"

    limpio = loading.open_rgb(_a_bytes(rgba))
    assert tuple(limpio[0, 0]) == loading.ALPHA_BACKGROUND


def test_el_alfa_parcial_se_mezcla_y_no_se_ignora():
    rgba = Image.new("RGBA", (4, 4), (0, 0, 0, 128))  # negro al 50 %
    got = loading.open_rgb(_a_bytes(rgba))[0, 0]
    assert all(100 < c < 155 for c in got), f"deberia quedar a medio camino del blanco, no {got}"


def test_se_aplica_la_orientacion_exif():
    """El navegador rota el original; el servidor no rotaba la marcada, así que
    una foto vertical salía acostada tras firmar."""
    im = Image.new("RGB", (16, 8), (10, 20, 30))
    exif = im.getexif()
    exif[274] = 6  # Orientation: rotar 90 grados
    origen = _a_bytes(im, "JPEG", exif=exif.tobytes())

    sin_corregir = np.asarray(Image.open(origen).convert("RGB"))
    assert sin_corregir.shape[:2] == (8, 16)

    origen.seek(0)
    corregido = loading.open_rgb(origen)
    assert corregido.shape[:2] == (16, 8), "deberia quedar vertical, como lo pinta el navegador"


def test_una_imagen_sin_perfil_no_se_toca():
    im = Image.new("RGB", (4, 4), (17, 99, 200))
    got = loading.open_rgb(_a_bytes(im))
    assert tuple(got[0, 0]) == (17, 99, 200)


def test_un_perfil_incrustado_se_convierte_sin_reventar():
    perfil = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    im = Image.new("RGB", (4, 4), (200, 60, 40))
    got = loading.open_rgb(_a_bytes(im, "JPEG", quality=100, icc_profile=perfil))
    assert got.shape == (4, 4, 3)
    assert got.dtype == np.uint8


def test_un_perfil_corrupto_degrada_en_vez_de_fallar():
    """Perder la gestion de color es preferible a rechazar el archivo."""
    im = Image.new("RGB", (4, 4), (9, 9, 9))
    got = loading.open_rgb(_a_bytes(im, "JPEG", icc_profile=b"esto no es un perfil"))
    assert got.shape == (4, 4, 3)


@pytest.mark.parametrize("modo", ["CMYK", "L", "1", "P"])
def test_otros_modos_de_color_acaban_en_rgb(modo):
    im = Image.new(modo, (4, 4))
    got = loading.open_rgb(_a_bytes(im, "TIFF" if modo == "CMYK" else "PNG"))
    assert got.shape == (4, 4, 3) and got.dtype == np.uint8


def test_lo_guardado_declara_su_espacio_de_color(tmp_path):
    """Sin perfil, un visor con gestion de color vuelve a desplazar los colores:
    justo lo que open_rgb acaba de normalizar."""
    destino = str(tmp_path / "salida.png")
    loading.save_rgb(np.full((4, 4, 3), 123, np.uint8), destino)
    assert Image.open(destino).info.get("icc_profile"), "el PNG deberia llevar perfil sRGB"


def test_el_png_en_memoria_es_sin_perdida():
    rgb = np.random.default_rng(0).integers(0, 256, (16, 16, 3), dtype=np.uint8)
    vuelta = np.asarray(Image.open(io.BytesIO(loading.encode_png(rgb))).convert("RGB"))
    assert np.array_equal(rgb, vuelta), "la lamina no puede anadir su propio dano"
