# Deck de la presentación

**No es parte de la web.** Se proyecta desde la máquina de quien expone, sin
servidor. Por eso el artefacto es un solo archivo:

```
deck/stegora-deck.html      78 KB · doble clic y listo
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
lo desplegado esté al día**. Compruébalo antes de exponer:

```bash
curl -s https://stegora.xyz/static/app.css | grep -o '\-\-oxido: *#[0-9A-Fa-f]*'
```

Tiene que decir `#FF5C9E`. Si dice otra cosa, producción está atrasada y la demo
mostraría un diseño viejo.

## El cronómetro

La restricción es que la introducción no pase de **un minuto**, y un minuto no se
estima. Arranca en el primer avance, se pone en negativo al pasarse de 60 s, y
deja de avisar después de la lámina de la demo, donde ya no es una restricción.

Eso fijó el diseño: **siete** láminas antes de la demo son ~8 segundos cada una,
y de ahí salió cuánto texto entra en cada una. El presupuesto por lámina está
escrito en su `data-tiempo` y suma **60 exactos**: la lámina de los cinco iconos
se lleva 14 —es la que hay que mirar, no leer— y se pagó fusionando láminas, no
estirando el reloj.

## Nada de letra chica

La regla de la sala manda sobre la comodidad de quien maqueta: **si no se lee
desde la última fila, no va**. El deck tiene tres voces y ningún tamaño suelto
—`--voz-nota`, `--voz-rotulo`, `--voz-cuerpo`—, y la más chica de las tres no
baja de ~2.6 % del alto proyectado: 28 px en 1080p, 19 px en 720p. Antes las
fuentes de los datos caían a 15 px y desde la quinta fila no se leían.

Las tres van por el **lado menor** (`min(vw, vh)`), no por el ancho: en un cañón
de 1280×720 el ancho sobra y el alto falta, y dimensionar por `vw` pedía cuerpos
que no cabían de alto. Es la misma regla que ya usaba la web.

## Las diez láminas

```
 1  Una imagen ya no prueba nada             el gancho, solo
 2  34 M · + reales · Ago 2026               la escala, con fuente
 3  El problema no es que existan falsas.    el giro, de una sola vez
    Es que nadie puede probar cuál es la
    verdadera
 4  C2PA guarda la procedencia en los        por qué lo de hoy no alcanza
    metadatos
 5  No adivinamos. Anotamos.                 el punchline, solo
 6  el código y lo que resuelve              el mecanismo, en un objeto
 7  ▣ ⟩ ⧅ ⟩ ✆ ⟩ ✆ ⟩ ▣                        la prueba, dibujada
 8  Demo                                     el corte
────────────────────────────────────────── de aquí manda la herramienta
 9  para qué sirve · quién lo firma
10  La imagen se acuerda.  +  QR         para que la sala lo pruebe
```

Eran trece. El giro estaba partido en dos láminas más una escena aparte, y «para
qué sirve» y «quién lo compra» iban separadas: tres láminas que no agregaban una
idea, sólo un clic. Lo que se dice en voz alta no necesita una lámina propia.

La **lámina 7** no lleva una sola palabra: **cinco iconos en fila** y el jurado
arma la frase solo —la imagen se marca, la destrozan, sale por WhatsApp, llega
por WhatsApp, y la marca sigue ahí—. El primero y el último son **el mismo
dibujo**: ahí está todo el argumento, y por eso no lleva rótulo. El último va
macizo contra los otros cuatro de contorno, así que se lee aunque el proyector se
coma el color; el rosa sólo refuerza algo que ya está dicho en blanco y negro.

**Un solo momento animado**, en la lámina 4: los renglones —recompresión,
reenvío— se tachan uno tras otro mientras el expositor habla, y ahí cae «y los
metadatos ya no están». La lista hace lo que dice en vez de describirlo.

Eran tres: la captura de pantalla salió de la lista porque **tampoco la
sobrevive nuestra marca**. Una lámina que se cuelga de algo que no cumplimos se
cae sola en la primera pregunta del jurado.

Ese tachado va atado a `[data-activa]` y no suelto, que es donde estuvo el bug:
las diez láminas existen en el DOM desde que carga la página, sólo que ocultas,
así que una animación sin condición ya había terminado antes de que a esa lámina
le tocara el turno — se veía sin tachar.

## El QR del cierre

La **lámina 10** lleva un QR grande a **`https://stegora.xyz/#probalo`**, que cae
directo en la herramienta y no en la portada. Va ahí y no en la lámina de la
demo porque ésta es la que se queda en pantalla mientras preguntan: nadie saca el
teléfono en el segundo en que se pasa una lámina, lo saca cuando ya no hay prisa.

Es **el único bloque blanco del deck** —la misma cartulina de la herramienta—, y
por eso se ve desde el fondo sin necesidad de una flecha ni de un rótulo grande.
Va con corrección de error **Q (25 %)**: sigue leyéndose con el reflejo del cañón
encima y desde la foto que alguien le saque a la pantalla, de lejos y en ángulo.

El código está **inline como un `<path>` de SVG**, no como imagen: el deck es un
archivo suelto y no puede pedirle nada a la red. Si la URL cambia hay que
regenerarlo —29×29 módulos, nivel Q— y reemplazar ese `d`.

## El español es neutro

Nada de voseo ni de modismos rioplatenses: el jurado no es de una sola ciudad.
«No podés probar» → «nadie puede probar»; «el archivo que ya anda afuera» → «que
ya circula afuera». Si al releer una lámina suena a una ciudad en particular, se
reescribe.
