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

Eso fijó el diseño: **cinco** láminas con reloj antes de la demo son ~12 segundos
cada una,
y de ahí salió cuánto texto entra en cada una. El presupuesto por lámina está
escrito en su `data-tiempo` y suma **60 exactos**: la lámina de los cinco iconos
se lleva **20** —es la que hay que mirar, no leer, y ahora se puede— y se pagó
fusionando y borrando láminas, no estirando el reloj.

## Nada de letra chica

La regla de la sala manda sobre la comodidad de quien maqueta: **si no se lee
desde la última fila, no va**. El deck tiene tres voces y ningún tamaño suelto
—`--voz-nota`, `--voz-rotulo`, `--voz-cuerpo`—, y la más chica de las tres no
baja de ~2.6 % del alto proyectado: 28 px en 1080p, 19 px en 720p. Antes las
fuentes de los datos caían a 15 px y desde la quinta fila no se leían.

Las tres van por el **lado menor** (`min(vw, vh)`), no por el ancho: en un cañón
de 1280×720 el ancho sobra y el alto falta, y dimensionar por `vw` pedía cuerpos
que no cabían de alto. Es la misma regla que ya usaba la web.

## Las ocho láminas

```
 1  ▦                                   el signo solo · sin reloj
 2  La imagen se acuerda.                el problema, con fuente y fecha
    700 M · 62 % · 2 dic 2026
 3  Stegora  +  QR                       el nombre y la invitación
 4  C2PA guarda la procedencia en los    por qué lo de hoy no alcanza
    metadatos
 5  el código y lo que resuelve          el mecanismo, en un objeto
 6  ▣ ⟩ ⧅ ⟩ ✆ ⟩ ✆ ⟩ ▣                    la prueba, dibujada
 7  Demo                                 el corte
──────────────────────────────────── de aquí manda la herramienta
 8  para qué sirve · quién lo firma
```

Eran trece. El giro estaba partido en dos láminas más una escena aparte, «para
qué sirve» y «quién lo compra» iban separadas, y había una lámina sólo para
«No adivinamos. Anotamos.». Cinco láminas que no agregaban una idea, sólo un
clic. La regla que quedó: **lo que se dice en voz alta no necesita una lámina
propia** — y el punchline es justamente lo que mejor se dice en voz alta.

**La lámina 1 no gasta reloj.** Es el signo solo, centrado en los dos ejes, sin
una palabra: no hay nada que leer mientras la sala termina de sentarse. Y no le
quita segundos a nadie, porque el cronómetro **arranca en el primer avance** —
vive con el reloj en 0:00, así que su `data-tiempo` es 0 y el minuto sigue
repartido entre las cinco que vienen detrás.

Lleva `data-marca`, que es lo que retira la firma chica de abajo a la izquierda:
ahí el signo ya está en grande y las dos juntas serían la misma marca dicha dos
veces. Ese atributo sustituyó a la comprobación por clase que hacía `deck.js`:
`lamina--marca` dice **cómo se coloca** una lámina y `data-marca` dice que **ahí
el nombre ya está dicho**, y ahora hay dos láminas que cumplen lo segundo con
maquetación distinta.

**El problema abre el discurso; el nombre entra después.** La lámina de marca estaba
primera y ahora va detrás de los datos: la sala entiende el tamaño del problema y
sólo entonces se le dice quién viene a resolverlo. El QR sigue entrando en el
primer minuto, que era el punto —tiene que estar en pantalla ANTES de que alguien
saque el teléfono, no después—, pero ahora llega cuando ya se sabe por qué habría
que sacarlo.

La frase **«La imagen se acuerda.»** se mudó con el cambio: era el titular de la
lámina de marca y ahora encabeza la de los datos, donde funciona como la
afirmación que los tres números respaldan. La de marca se quedó con el **nombre**
en bloque, que es lo que una portada tiene que decir. Va en `tit--m` sobre los
datos y no en `tit--xl`: ahí los que mandan son los tres números, y un titular
más grande que ellos los convertiría en pie de página.

⚠️ **El deck ya no tiene lámina de cierre**: termina en «para qué sirve». Si en
sala se siente que se corta, la salida barata es duplicar la lámina 1 al final —
la marca y el QR aguantan las dos puntas.

La **lámina 5** no lleva una sola palabra: **cinco iconos en fila** y el jurado
arma la frase solo —la imagen se marca, la destrozan, sale por WhatsApp, llega
por WhatsApp, y la marca sigue ahí—. El primero y el último son **el mismo
dibujo**: ahí está todo el argumento, y por eso no lleva rótulo. El último va
macizo contra los otros cuatro de contorno, así que se lee aunque el proyector se
coma el color; el rosa sólo refuerza algo que ya está dicho en blanco y negro.

**Un solo momento animado**, en la lámina 3: los renglones —recompresión,
reenvío— se tachan uno tras otro mientras el expositor habla, y ahí cae «y los
metadatos ya no están». La lista hace lo que dice en vez de describirlo.

Eran tres: la captura de pantalla salió de la lista porque **tampoco la
sobrevive nuestra marca**. Una lámina que se cuelga de algo que no cumplimos se
cae sola en la primera pregunta del jurado.

Ese tachado va atado a `[data-activa]` y no suelto, que es donde estuvo el bug:
las ocho láminas existen en el DOM desde que carga la página, sólo que ocultas,
así que una animación sin condición ya había terminado antes de que a esa lámina
le tocara el turno — se veía sin tachar.

## Los datos de la lámina 2

Los tres se pueden ir a verificar, y por eso van con fuente y fecha en pantalla:

- **700 M** imágenes en la primera semana de la generación de imágenes de
  ChatGPT (25 mar – 3 abr 2025), 130 M de usuarios — cifra de OpenAI, recogida
  por [TechCrunch](https://techcrunch.com/2025/04/03/chatgpt-users-have-generated-over-700m-images-since-last-week-openai-says/).
  Reemplazó a «34 M por día · Everypixel, ago 2023»: la vieja tenía tres años y
  era una estimación de terceros; ésta es de primera mano y dice más —eso es
  **un solo producto en una semana**—.
- **62 %** de acierto humano distinguiendo imágenes de IA, sobre ~287 000
  juicios de 12 500 participantes — [Microsoft Research, jul 2025](https://arxiv.org/abs/2507.18640).
  Reemplazó a «+ reales que las auténticas», que no se entendía sin explicarla:
  aludía a los estudios de hiperrealismo (PNAS 2022, Psych. Science 2023) pero
  en pantalla no decía nada.
- **2 dic 2026** es el plazo real que le queda a un cliente: el art. 50 del AI
  Act rige desde el 2 ago 2026, pero la prórroga del AI Omnibus (may 2026) da
  hasta el 2 de diciembre a los sistemas que ya estaban en el mercado para
  cumplir el marcado legible por máquina. Es una cuenta atrás, no una fecha
  pasada.

## Lo que ya no está en pantalla

El deck arrancó con trece láminas y quedan siete. Se fueron, por este orden: el
gancho suelto, la escena del reclamo, el punchline «No adivinamos. Anotamos.»,
los dos segundos párrafos, y el giro «el problema no es que existan imágenes
falsas — es que nadie puede probar cuál es la verdadera».

Todas por la misma regla: **lo que se dice en voz alta no necesita una lámina
propia**. Pero eso convierte al expositor en parte del entregable, no en un
adorno del entregable. El giro y el punchline son el argumento del producto; si
no se dicen, el deck pasa de la escala del problema (lámina 2) a la crítica de
C2PA (lámina 3) sin haber enunciado nunca qué se está resolviendo.

Van, literalmente, entre la 2 y la 3:

> El problema no es que existan imágenes falsas. Es que nadie puede probar cuál
> es la verdadera. Y no adivinamos: anotamos.

## Nada de segundos párrafos

Las láminas 3 y 6 llevaban un pie que explicaba lo que el titular ya decía. En
una lámina de una idea, el segundo párrafo sólo le roba escala al primero, y
nadie termina de leerlo en ocho segundos. La 3 se quedó con la frase sola; la 6
con **un** mensaje —«va adentro de los píxeles, no en una etiqueta»—, que es
además el del producto entero. Lo que se cayó lo dice quien expone.

## La medida del titular

`.tit` lleva `max-width: 24ch`. Sin esa medida una frase larga corría hasta el
borde derecho y la siguiente dejaba media lámina vacía: el bloque se leía
torcido **aunque estuviera centrado al píxel**. Medido: las láminas caen a 3–4 px
del centro geométrico de 1080, así que el problema nunca fue el centrado.

Y la tríada alinea por arriba (`align-items: start`) y no por abajo: lo que se
compara de un vistazo son los tres números, y con `end` quedaban a tres alturas
distintas porque debajo cada columna lleva distinta cantidad de renglones.

## El QR de la primera lámina

La **lámina 1** lleva un QR grande a **`https://stegora.xyz/#probalo`**, que cae
directo en la herramienta y no en la portada. Va de entrada y no en la lámina de
la demo: la de la demo se pasa en un segundo, y para cuando alguien saca el
teléfono ya no está. En la primera, el código lleva toda la exposición en
pantalla —o en la foto que alguien le sacó al principio—.

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
