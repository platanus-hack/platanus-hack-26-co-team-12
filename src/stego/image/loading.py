"""Carga y guardado de imágenes sin alterar lo que el usuario no pidió alterar.

Tanto el CLI como la web hacían ``Image.open(path).convert("RGB")``, que descarta
en silencio tres cosas y todas se notan:

**Perfil de color.** ``convert("RGB")`` no hace gestión de color: lee los números
crudos y tira el perfil ICC. Al guardar tampoco se escribía ninguno. Una foto de
iPhone viene en **Display P3**, así que el navegador muestra el original con sus
colores correctos y la marcada —los mismos números, ya sin perfil— interpretados
como sRGB: **sobresaturada**. El usuario ve un viraje de color que el códec nunca
hizo. Aquí se convierte de verdad al espacio sRGB usando el perfil de origen, de
modo que los números que salen significan lo que el visor va a suponer.

**Orientación EXIF.** El servidor no rotaba, pero el navegador sí rota el original
(``image-orientation: from-image`` es el valor por defecto en CSS). Una foto
vertical de celular aparecía acostada después de firmar.

**Canal alfa.** ``convert("RGB")`` sobre una imagen RGBA descarta la
transparencia **sin componer sobre ningún fondo**, dejando a la vista los valores
RGB que había debajo —normalmente negro o basura de color—. Aquí se compone sobre
blanco, que es lo que el visor habría mostrado.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageCms, ImageOps

__all__ = ["open_rgb", "save_rgb", "to_srgb"]

#: Fondo sobre el que se componen las imágenes con transparencia.
ALPHA_BACKGROUND = (255, 255, 255)


def to_srgb(im: Image.Image) -> Image.Image:
    """Convierte al espacio sRGB usando el perfil incrustado, si lo hay.

    Si la imagen no trae perfil se asume que ya es sRGB, que es la convención de
    la web. Si el perfil está corrupto se degrada a esa misma suposición en lugar
    de fallar: perder la gestión de color es preferible a rechazar el archivo.
    """
    icc = im.info.get("icc_profile")
    if not icc:
        return im
    try:
        origen = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        destino = ImageCms.createProfile("sRGB")
        modo = "RGBA" if im.mode in ("RGBA", "LA", "PA") else "RGB"
        return ImageCms.profileToProfile(im, origen, destino, outputMode=modo)
    except Exception:  # noqa: BLE001 - perfil ilegible: seguimos sin gestión
        return im


def open_rgb(source) -> np.ndarray:
    """Abre una imagen y devuelve RGB uint8 ``(H, W, 3)``, ya normalizada.

    Aplica, en este orden: orientación EXIF, conversión a sRGB y composición del
    canal alfa sobre blanco.

    Args:
        source: ruta o descriptor de archivo, lo que acepte ``PIL.Image.open``.
    """
    im = Image.open(source)
    im.load()

    # La orientación va primero: rotar después de recortar o marcar sería peor.
    im = ImageOps.exif_transpose(im) or im

    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    if im.mode in ("CMYK", "YCbCr", "I", "F", "L", "LA", "1"):
        im = im.convert("RGBA" if im.mode == "LA" else "RGB")

    im = to_srgb(im)

    if im.mode == "RGBA":
        fondo = Image.new("RGBA", im.size, (*ALPHA_BACKGROUND, 255))
        im = Image.alpha_composite(fondo, im)

    if im.mode != "RGB":
        im = im.convert("RGB")
    return np.asarray(im, dtype=np.uint8)


def save_rgb(rgb: np.ndarray, path: str, *, jpeg_quality: int = 95) -> None:
    """Guarda RGB uint8 declarando explícitamente que el contenido es sRGB.

    Escribir el perfil importa: sin él, un visor con gestión de color puede
    suponer el espacio del monitor y volver a desplazar los colores, que es
    exactamente el problema que ``open_rgb`` acaba de resolver.
    """
    img = Image.fromarray(np.asarray(rgb, dtype=np.uint8), mode="RGB")
    perfil = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    if path.lower().endswith((".jpg", ".jpeg")):
        img.save(path, "JPEG", quality=jpeg_quality, subsampling=2, icc_profile=perfil)
    else:
        img.save(path, icc_profile=perfil)


def encode_png(rgb: np.ndarray) -> bytes:
    """PNG sin pérdida en memoria, con el perfil sRGB declarado."""
    buf = io.BytesIO()
    perfil = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.fromarray(np.asarray(rgb, dtype=np.uint8), mode="RGB").save(
        buf, "PNG", optimize=False, compress_level=1, icc_profile=perfil)
    return buf.getvalue()
