"""Enmascaramiento perceptual: modular la marca según lo que el contenido oculta.

El problema que resuelve
------------------------

La plantilla de sincronía se sumaba con **amplitud constante a todos los píxeles**
(`covers/image_dct_qim.py`, `_mark_plane`). Eso ignora el hecho central de la
percepción visual: el mismo error es invisible sobre una textura y evidente sobre
un cielo.

Con el perfil de la demo (``template_amp = 6.0``) la plantilla inyecta un RMS de
2.29 niveles de gris con picos de ±6.9 —un contraste Weber del 1.8 % RMS y 5.4 %
de pico sobre un gris medio, muy por encima del umbral de detección (~1 %) en
zonas planas—. Como además es un mosaico **periódico exacto de 64 px**, el ojo
engancha la regularidad y lo lee como un filtro superpuesto, no como ruido.

Reparto medido de la energía de error a Δ=26 y amp=6.0: la plantilla es el 66 %
y el QIM el 34 %. La plantilla domina 2 a 1, así que es donde hay que actuar.

Cómo funciona
-------------

La ganancia sale de la desviación típica local: cerca de 0 en zonas planas, cerca
de 1 donde hay textura que enmascara. Después se **redistribuye la energía**:
lo que se le quita al cielo se le devuelve a la textura, donde el contenido lo
tapa. Sobre una imagen enteramente lisa no hay dónde redistribuir, así que la
amplitud simplemente baja —y eso es correcto: es justo el caso en que la marca
se vería—.

Por qué esto no rompe la extracción ciega
------------------------------------------

El sincronizador correlaciona la imagen recibida contra el **patrón** de la
plantilla, plegando módulo su periodo. Una ganancia local **positiva** solo
repondera los sumandos de esa correlación: el pico sigue en la misma posición y
el extractor **no necesita conocer la máscara**. Es la misma razón por la que la
marca sobrevive a cambios de contraste.

Lo que sí cambia es la **altura** del pico, y por tanto la ``z`` de sincronía.
Ese es el número que hay que medir al ajustar los parámetros; no se puede dar por
supuesto que sale gratis. Las zonas lisas son precisamente donde la plantilla más
sobresale del contenido, así que quitarle amplitud ahí le cuesta señal al
sincronizador; la redistribución existe para compensarlo subiendo la amplitud en
textura, que es donde hoy el contenido la tapa y por lo que hizo falta llegar a
amp 6.0.

Lo que NO se puede hacer
------------------------

Aleatorizar el mosaico por posición para romper la periodicidad visual. La
repetición exacta cada 64 px **es** el mecanismo de sincronía: ``sync.locate()``
pliega módulo ese periodo para sumar coherentemente todas las copias presentes en
la imagen. Romper la periodicidad rompe la extracción. La periodicidad es carga
estructural; la amplitud no lo es, y por eso es la palanca correcta.
"""

from __future__ import annotations

import numpy as np

__all__ = ["box_mean", "local_std", "perceptual_gain", "DEFAULTS"]

#: Parámetros por defecto, pensados para ser barridos en el banco de pruebas.
DEFAULTS = {
    "radius": 8,       # ventana de 17x17 px: del orden del grano de la plantilla
    "knee": 6.0,       # desviación local (niveles) en que la ganancia llega a la mitad
    "floor": 0.12,     # ganancia mínima: nunca se anula del todo (ver abajo)
    "boost_max": 1.8,  # tope de la redistribución hacia zonas texturizadas
}

# Sobre `floor`: estuvo en 0.35 y se bajó a 0.12 tras barrerlo. Es lo que permitió
# subir `template_amp` a 5.0 en la demo —y recuperar los recortes de 400 y 256 px,
# que a 4.0 caían al 66 %— sin devolverle nada a la nube. Medido sobre 3
# fotografías, error de escala gruesa en zona plana (pasa-bajos σ=3, que es lo que
# el ojo integra), tomando como 100 % el perfil que produjo el moteado:
#
#   amp 6.0 sin máscara ..... 100 %   <- el problema reportado
#   amp 4.0 floor 0.35 ......  49 %   <- el arreglo original
#   amp 5.0 floor 0.35 ......  58 %   <- devolvía ~1/5 del arreglo
#   amp 5.0 floor 0.12 ......  45 %   <- mejor que el arreglo original, y 8/8
#
# El escalón que advierte la nota de abajo NO se materializa a 0.12: la ganancia
# gana rango (salto p99 de 0.15 a 0.23) pero el gradiente de la marca en los
# bordes lisa/textura BAJA (0.519 -> 0.495), porque el boost renormaliza y en
# zona plana queda menos amplitud total. El campo de `local_std` va suavizado en
# ventana de 17 px, así que no hay discontinuidad dura que mostrar.
#
# `knee` en cambio NO se toca: a 9.0 mejora la nube pero el recorte de 256 px cae
# de 9/9 a 7/9. Barrido en el mismo banco.


def box_mean(a: np.ndarray, radius: int) -> np.ndarray:
    """Media en ventana ``(2r+1)x(2r+1)`` mediante imagen integral, O(1) por píxel.

    Los bordes se replican, de modo que la salida tiene el tamaño de la entrada y
    no aparecen artefactos de contorno que serían visibles justo en el marco.
    """
    if radius < 1:
        raise ValueError("radius debe ser >= 1")
    h, w = a.shape
    n = 2 * radius + 1
    padded = np.pad(np.asarray(a, dtype=np.float64), radius, mode="edge")
    cum = np.pad(padded.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    total = (cum[n:n + h, n:n + w] - cum[:h, n:n + w]
             - cum[n:n + h, :w] + cum[:h, :w])
    return total / float(n * n)


def local_std(y: np.ndarray, radius: int) -> np.ndarray:
    """Desviación típica local. Es el estimador de cuánta textura hay para esconder."""
    y = np.asarray(y, dtype=np.float64)
    mu = box_mean(y, radius)
    var = box_mean(y * y, radius) - mu * mu
    return np.sqrt(np.maximum(var, 0.0))


def perceptual_gain(y: np.ndarray, *, radius: int | None = None,
                    knee: float | None = None, floor: float | None = None,
                    boost_max: float | None = None) -> np.ndarray:
    """Ganancia por píxel para modular la plantilla. RMS ≈ 1 cuando hay textura.

    Args:
        y: plano de luminancia sobre el que se va a marcar.
        radius: radio de la ventana de análisis.
        knee: desviación local a la que la ganancia alcanza la mitad de su rango.
        floor: ganancia mínima. **No debe ser 0**: anular la plantilla del todo
            crea escalones duros en los bordes entre zona lisa y texturizada, que
            son en sí mismos visibles, y además deja al sincronizador sin ninguna
            señal en las zonas planas.
        boost_max: tope de la redistribución. Sin tope, una imagen casi lisa
            devolvería toda la amplitud a los pocos píxeles con textura y ahí sí
            se vería.

    Returns:
        Array del tamaño de ``y``, positivo, listo para multiplicar la plantilla.
    """
    radius = DEFAULTS["radius"] if radius is None else radius
    knee = DEFAULTS["knee"] if knee is None else knee
    floor = DEFAULTS["floor"] if floor is None else floor
    boost_max = DEFAULTS["boost_max"] if boost_max is None else boost_max
    if not 0.0 < floor <= 1.0:
        raise ValueError("floor debe estar en (0, 1]")
    if knee <= 0:
        raise ValueError("knee debe ser > 0")

    sigma = local_std(y, radius)
    # Ley saturante: 0 en lo perfectamente liso, ->1 con textura fuerte.
    gain = floor + (1.0 - floor) * (sigma / (sigma + knee))

    # Redistribución: devolver a la textura la energía que se le quitó al cielo.
    # Como gain <= 1, el factor nunca es menor que 1; solo puede subir, y con tope.
    rms = float(np.sqrt(np.mean(gain * gain)))
    boost = min(boost_max, 1.0 / rms) if rms > 1e-9 else 1.0
    return np.clip(gain * boost, 0.0, boost_max)
