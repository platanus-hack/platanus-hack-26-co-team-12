# Deck de la presentación

**No es parte de la web.** Se proyecta desde la máquina de quien expone, sin
servidor. Por eso el artefacto es un solo archivo:

```
deck/stegora-deck.html      68 KB · doble clic y listo
```

Todo va adentro, incluida la tipografía en base64. Se copia a un USB y funciona
en cualquier máquina, sin internet y sin levantar nada. Desde `file://` una ruta
absoluta a `/static/` no resuelve, y algunos navegadores además bloquean fuentes
por CORS: por eso no puede depender de la web.

## Rehacerlo

```bash
python deck/construir.py
```

Se edita en `deck/fuente/` —`cuerpo.html`, `deck.css`, `deck.js`— y el script
arma la salida.

**Los tokens no se duplican.** El script los lee de `web/static/app.css`, desde
el principio hasta `.hoja {`: eso es `@font-face`, `:root`, el reset, `body`,
selección, scrollbars y foco, que es exactamente lo que el deck usa y nada del
shell de la herramienta. Si mañana se elige un color, se corre esto de nuevo y el
deck cambia con el producto.

El script **falla en vez de emitir un archivo a medias** si el marcador `.hoja {`
desaparece de `app.css`, si la declaración de la fuente cambia, o si queda alguna
referencia externa en la salida.

## Cómo se maneja

| Tecla | Qué hace |
|---|---|
| `→` `↓` `espacio` · clic | avanzar |
| `←` `↑` | retroceder |
| `Inicio` / `Fin` | primera / última |
| `f` | pantalla completa |
| `i` | esconder el cronómetro y la barra — **para grabar** |
| `r` | reiniciar el cronómetro |

`i` esconde el cronómetro y la barra de avance, pero **no la firma**: aquello es
andamiaje del expositor y esto es el nombre del proyecto. Va fija abajo a la
izquierda en todas las láminas —el deck no gasta una lámina en decir cómo se
llama, pero cualquier fotograma que alguien recorte de la grabación tiene que
traer el nombre— y se retira sola en el cierre, donde la marca ya está en grande.

El clic avanza salvo sobre un enlace, para que el botón «Abrir la herramienta» se
pueda abrir sin saltar de lámina. Ese botón apunta a **`https://stegora.xyz`**, o
sea a producción: no hace falta levantar nada en local, pero **sí hace falta que
lo desplegado esté al día**. Comprobalo antes de exponer:

```bash
curl -s https://stegora.xyz/static/app.css | grep -o '\-\-oxido: *#[0-9A-Fa-f]*'
```

Tiene que decir `#FF5C9E`. Si dice otra cosa, producción está atrasada y la demo
mostraría un diseño viejo.

## El cronómetro

La restricción es que la introducción no pase de **un minuto**, y un minuto no se
estima. Arranca en el primer avance, se pone en negativo al pasarse de 60 s, y
deja de avisar después de la lámina de la demo, donde ya no es una restricción.

Eso fijó el diseño: nueve láminas antes de la demo son **~6 segundos cada una**,
y de ahí salió cuánto texto entra en cada una.

## Las doce láminas

```
 1  Mirar la imagen ya no alcanza            el gancho, solo
 2  34 M · + reales · Ago 2026               la escala, con fuente
 3  El problema no es que existan falsas     ┐ el giro,
 4  No podés probar de dónde salió la        ┘ en dos tiempos
    verdadera
 5  Te reclaman por una imagen que subió     donde aterriza en plata
    otra persona
 6  C2PA guarda la procedencia en los        por qué lo de hoy no alcanza
    metadatos
 7  No adivinamos. Anotamos.                 el punchline, solo
 8  el código y lo que resuelve              el mecanismo, en un objeto
 9  Demo                                     el corte
────────────────────────────────────────── de acá manda la herramienta
10  para qué sirve
11  quién lo compra
12  La imagen se acuerda.
```

**Un solo momento animado**, en la lámina 6: los tres renglones —captura de
pantalla, recompresión, reenvío— se tachan uno tras otro mientras el expositor
habla, y ahí cae «y los metadatos ya no están». La lista hace lo que dice en vez
de describirlo.

Ese tachado va atado a `[data-activa]` y no suelto, que es donde estuvo el bug:
las doce láminas existen en el DOM desde que carga la página, sólo que ocultas,
así que una animación sin condición ya había terminado antes de que a esa lámina
le tocara el turno — se veía sin tachar.
