#!/usr/bin/env python
"""Clases que landing.css y app.css se disputan.

Existe porque ya pasó: `.marca` estaba definida en app.css como el icono de
estado del rail (1rem x 1rem) y la landing la reusó para el logotipo. El logo
colapsó a 17 px y, peor, las reglas de la landing se aplicaron a los iconos de la
herramienta. Una comprobación de tres líneas encuentra eso; leer dos archivos de
600 líneas a ojo, no.

    .venv/bin/python web/colisiones.py
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CLASE = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

#: Compartidas a propósito. Agregar acá es una decisión que se justifica, no una
#: forma de silenciar el chequeo.
#:
#: - `accion`: la landing reusa el botón de la herramienta para que haya UNA sola
#:   acción primaria en todo el producto; sólo le devuelve el comportamiento de
#:   bloque que un <a> necesita.
#: - `hoja`: la landing la toca en UNA regla y siempre acotada a `.probalo .hoja`,
#:   para restarle el alto de la barra pegajosa. Sigue siendo altura definida
#:   (`calc`), que es la propiedad que no se puede romper.
DELIBERADAS = {"accion", "hoja"}


def clases(ruta: str) -> set[str]:
    with open(ruta, encoding="utf-8") as fh:
        css = fh.read()
    # Fuera los comentarios: un `.marca` en prosa no es un selector.
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    # Sólo los selectores, no los valores de propiedad (donde vive el `.5rem`).
    sel = " ".join(re.split(r"\{[^}]*\}", css))
    return set(CLASE.findall(sel))


def main() -> int:
    app = clases(os.path.join(AQUI, "static", "app.css"))
    land = clases(os.path.join(AQUI, "static", "landing.css"))
    chocan = sorted((app & land) - DELIBERADAS)
    if not chocan:
        print(f"sin colisiones · app.css {len(app)} clases · landing.css {len(land)}"
              f" · compartidas a propósito: {', '.join('.' + c for c in sorted(DELIBERADAS))}")
        return 0
    print("COLISIONAN, y las dos hojas se van a pisar:")
    for c in chocan:
        print(f"  .{c}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
