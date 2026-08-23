#!/usr/bin/env python
"""Arma el deck como UN archivo que se abre con doble clic.

    python deck/construir.py

El deck no es parte de la web: se proyecta desde esta máquina, sin servidor.
Por eso no puede depender de `/static/app.css` ni de una ruta absoluta a la
fuente — desde `file://` eso no carga, y algunos navegadores además bloquean
fuentes por CORS. La salida es un solo HTML con todo adentro, incluida la
tipografía en base64: se copia a un USB y funciona.

**Los tokens NO se duplican.** El script los lee de `web/static/app.css`, desde
el principio hasta `.hoja {` — o sea `@font-face`, `:root`, el reset, `body`,
selección, scrollbars y foco, que es exactamente lo que el deck necesita y nada
del shell de la herramienta. Así, si mañana se elige un color, se vuelve a correr
esto y el deck cambia con el producto.
"""
from __future__ import annotations

import base64
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
FUENTE = os.path.join(AQUI, "fuente")

APP_CSS = os.path.join(RAIZ, "web", "static", "app.css")
WOFF2 = os.path.join(RAIZ, "web", "static", "fonts", "Archivo-var.woff2")
SALIDA = os.path.join(AQUI, "stegora-deck.html")

#: Dónde corta app.css: todo lo anterior es sistema, lo posterior es la
#: herramienta. Si esta regla se renombra, el script falla en vez de emitir un
#: deck a medias.
CORTE = ".hoja {"


def leer(ruta: str) -> str:
    with open(ruta, encoding="utf-8") as fh:
        return fh.read()


def base_del_sistema() -> str:
    css = leer(APP_CSS)
    if CORTE not in css:
        raise SystemExit(
            f"no encuentro `{CORTE}` en app.css: cambió la estructura y este "
            f"script ya no sabe dónde termina el sistema y empieza la herramienta")
    css = css[: css.index(CORTE)]

    # La fuente va adentro: desde file:// una ruta absoluta no resuelve.
    with open(WOFF2, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    css = re.sub(
        r"url\('/static/fonts/Archivo-var\.woff2'\)",
        f"url('data:font/woff2;base64,{b64}')",
        css)
    if "base64" not in css:
        raise SystemExit("no pude empotrar la fuente: cambió su declaración en app.css")
    return css


def main() -> int:
    cuerpo = leer(os.path.join(FUENTE, "cuerpo.html"))
    m = re.search(r"<body[^>]*>(.*)</body>", cuerpo, re.S)
    if not m:
        raise SystemExit("cuerpo.html no tiene <body>")

    # Defensa: cualquier referencia externa que se cuele en el cuerpo rompe el
    # archivo suelto sin decirlo — el navegador falla en silencio y el deck se
    # abre sin estilos o sin teclado. Ya pasó con el <script src>.
    dentro = re.sub(r"<script[^>]*\ssrc=[^>]*></script>\s*", "", m.group(1))
    dentro = re.sub(r"<link[^>]*>\s*", "", dentro)

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stegora · deck</title>
<style>
{base_del_sistema()}
{leer(os.path.join(FUENTE, 'deck.css'))}
</style>
</head>
<body class="deck">
{dentro.strip()}
<script>
{leer(os.path.join(FUENTE, 'deck.js'))}
</script>
</body>
</html>
"""
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(html)

    externas = re.findall(r'(?:src|href)="(?!http|#|data:)([^"]+)"', html)
    if externas:
        raise SystemExit(f"quedaron referencias externas y el archivo no abriría solo: {externas}")

    kb = len(html.encode()) / 1024
    print(f"{os.path.relpath(SALIDA, RAIZ)} · {kb:.0f} KB · un archivo, cero dependencias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
