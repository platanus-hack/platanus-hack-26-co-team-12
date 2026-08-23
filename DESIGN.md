# Design

<!-- impeccable:design-schema 1 -->

Mundo visual de la interfaz web (`web/static/`). Escrito desde lo construido, no
desde la intención.

## El mundo: ficha de catalogación de archivo fotográfico

La marca de 16 bytes **es** un número de registro, así que la pantalla es la
ficha donde una imagen y su identidad quedan atadas: fondo de copia diazo, la
imagen montada como lámina sobre cartulina con esquineros, y el identificador
estampado como sello de caucho.

Rechaza los dos lugares donde este tema siempre aterriza: la consola oscura con
mono neón y badges verde/rojo, y su opuesto previsible, el dashboard blanco con
tarjetas redondeadas y acento azul.

**Destilado a una acción por pantalla.** Tres pestañas —Firmar, Verificar,
Pruebas—, una sola cartulina, un solo botón, y nada más hasta que hay
resultado. Lo que se sacó en el pase de destilado: el reglado del fondo, el
degradado radial, el reporte de diez campos, la barra de atajos, la lámina de
referencia y el pie de límites. Del formulario quedan a la vista el emisor y el
título; los mandos del códec —enlace, Δ, amplitud de plantilla y la casilla de
enmascaramiento— viven detrás de un `<details>`, que es donde tienen que estar:
son para el banco, no para la historia.

La casilla usa `accent-color`, no una marca dibujada. Es la única excepción a la
regla de dibujar los estados, y es deliberada: el navegador ya resuelve el foco,
el estado indeterminado y el alto contraste, y acá sólo hacía falta que tomara el
acento de la casa.

## Color

**Rampa neutra con una sola tinta: rosa `#FF5C9E`.** Todo lo demás es gris, así
que el rosa es lo único que llama — y llama donde uno quiere: la acción, el
sello, el foco, la marca.

El sistema pasó por una etapa enteramente en blanco y negro, y esa etapa dejó lo
más valioso: **el acento se cambia tocando un solo bloque**. Los estados nunca
dependieron de la tinta —cuadro lleno, aspa, cuadro partido, borde discontinuo—,
así que meter un color no obligó a reauditar nada.

**El rosa se eligió con número, no a ojo**, porque tenía que servir para dos
cosas a la vez: ser fondo del botón con texto oscuro encima, y leerse él mismo
sobre el suelo casi negro.

| candidato | texto oscuro encima | sobre el suelo | |
|---|---|---|---|
| `#F72585` | 4.92:1 | 5.21:1 | saturado, vibra sobre el negro |
| **`#FF5C9E`** | **6.44:1** | **6.82:1** | **elegido** |
| `#FF7EB6` | 7.88:1 | 8.35:1 | empieza a leerse pastel |
| `#FFB3D1` | 11.17:1 | 11.83:1 | pastel, pierde carácter |

Sobre cartulina el rosa cae a **2.58:1**, y por eso la regla de siempre se
mantiene: el acento es relleno, filo o sello, **nunca texto de cuerpo**.

| Token | Valor | Rol |
|---|---|---|
| `--indigo` | `#0B0B0B` | el suelo |
| `--indigo-hondo` | `#191919` | superficie **elevada**: campos, banda en reposo, tramos de la landing |
| `--indigo-borde` | `#383838` | divisiones de 1–3 px |
| `--indigo-marca` | `#050505` | el campo de la herramienta: **hundido**, no elevado |
| `--lamina` | `#F2F2F2` | la cartulina |
| `--tinta` | `#131313` | texto sobre cartulina |
| `--tinta-sec` | `#5C5C5C` | rótulos sobre cartulina |
| `--oxido` | `#FF5C9E` | **el acento**, y la única tinta del sistema |
| `--oxido-hondo` | `#E03B7E` | su estado activo |
| `--ledger` | `#E8E8E8` | veredicto positivo: claro, con tinta encima |
| `--adverso` | `#2E2E2E` | veredicto negativo y alterado: oscuro, con texto claro |
| `--sobre` | `#F0F0F0` | texto principal sobre el suelo |
| `--sobre-sec` | `#A0A0A0` | texto secundario |

**El campo de la herramienta se hunde en vez de levantarse.** Es lo que lo separa
del suelo sin inventar un cuarto gris intermedio que competiría con la superficie
elevada.

Tres reglas que quedaron de la etapa monocroma y siguen valiendo:

1. Donde el acento es **fondo** —botón primario, selección de texto— el texto va
   en `--tinta`.
2. El **rayado del cotejo** no usa el acento: trazo en `--tinta` sobre base
   clara. Tiene que leerse sobre cualquier contenido, y para eso existen las dos
   pasadas.
3. Los **tres estados del veredicto** se separan por **valor** —claro el
   positivo, oscuro el adverso— y por la **forma** de la marca. El acento no
   participa: si mañana cambia, los veredictos siguen distinguiéndose.

## El ritmo vertical responde al alto, no al ancho

**Una sección pensada para caber en una pantalla tiene que caber en esa
pantalla.** Medido en siete tamaños, tres cosas la rompían:

1. **`--tramo-y` tenía un mínimo en `rem`.** Era `clamp(4.5rem, 9vh, 8rem)`: en
   una pantalla baja el mínimo ganaba y el relleno quedaba clavado en **153 px
   por sección** pasara lo que pasara. Ahora es `clamp(1.9rem, 5.5vh, 6.5rem)`.
2. **La tipografía escalaba con el ancho.** En un proyector de 1280×720 el ancho
   sobra y el alto falta, pero `6.2vw` pedía 79 px de línea. Los titulares se
   dimensionan por el **lado menor**: `min(6.2vw, 8.6vh)`.
3. **`#probalo` se pasaba por 6 px.** `.hoja` medía `100svh − barra` y la sección
   le sumaba dos bordes de 3 px. Ahora los descuenta.

A eso se sumó una decisión de composición: **los tres usos pasan de apilados a
tres columnas.** Apilados pedían 781 px y no entraban en 720p; en paralelo entran
de sobra, y tres usos del mismo mecanismo se comparan mejor lado a lado que en
fila india. Bajo 940 px vuelven a apilarse.

Queda un `@media (max-height: 700px)` para el último tramo —proyectores viejos,
ventanas a media altura— que aprieta interlineados y esconde la pista de la
cabecera. Va por **alto** y no por ancho, porque el problema es de alto.

Resultado, de 1920×1080 a 1024×640: **todas las secciones caben en su pantalla**.
En teléfono no, y está bien: una portada con cuatro casos no entra en 844 px y
forzarla costaría legibilidad.

## Radio

`--radio: 6px` para controles —botones, campos, el sello, el chip— y
`--radio-caja: 10px` para superficies —la cartulina, el montaje, las fichas—.

La cartulina y el montaje llevan `overflow: hidden`: los esquineros son
triángulos de esquina recta y sin eso sobresalen del papel redondeado.

## Tipografía

**Una sola familia, variable**, autoalojada en `web/static/fonts/`. **Nada
depende de la red**: en tarima no hay internet garantizado.

Eran tres —Archivo Black, Archivo variable y Courier Prime en dos pesos—: cuatro
archivos, 89 KB. El archivo variable declaraba `font-weight: 400 700` cuando su
eje `wght` va de **100 a 900**, así que la voz de bloque nunca necesitó un
archivo aparte: es esta misma familia en 900. Queda **un archivo, 35 KB**.

| Voz | Cómo se hace | Uso |
|---|---|---|
| **Bloque** | `Archivo` **900**, versalitas | pestañas, botones, veredicto, titulares |
| **Corriente** | `Archivo` 400–700 | prosa y encabezados de sección |
| **Tipeada** | `Archivo` **350** + tracking abierto | código, medidas, rótulos, membrete |

Las tres voces se separan por **peso y espaciado**, no por familia. Lo que se
pierde frente a Courier Prime es el ancho fijo: los grupos hexadecimales del
código ya no alinean columna a columna. Los números sí, porque todo lleva
`font-variant-numeric: tabular-nums`.

Raíz `17px`, subiendo a `19px` a partir de 1500 px y `21px` a partir de 1900 px:
la pantalla del proyector es más grande, no más densa.

## Dos superficies, un mundo

El documento tiene **dos superficies** con modos distintos, y el mismo mundo:

- **La landing** (`landing.css`) — modo persuadir. Scroll largo, secciones de una
  medida de 46rem, ritmo de `--tramo-y`.
- **La herramienta** (`app.css`) — modo operar. Vive dentro de
  `<section id="probalo">` y **conserva su shell de `100svh` con
  `overflow:hidden`**, intacto.

Esa conservación no es pereza: `.hoja` ya tenía **altura definida**, y la cadena
`.hoja 100svh → .cuerpo min-height:0 → .vista stretch → .acto height:100% →
.soltar aspect-ratio` es lo que hace que la cartulina se dimensione por alto.
Meterla en un flujo de scroll sin altura definida rompe esa cadena y la lámina se
desborda — es la trampa que ya costó dos rondas, documentada más abajo. Por eso
la herramienta se **envuelve** y no se adapta: `app.css` y `app.js` no se tocaron
ni una línea.

`landing.css` carga después de `app.css` y no redeclara un solo token.

### La landing: una lista de casos

La página **es** la lista, y cada fila es una imagen cuyo origen se puede probar.
La portada parte en dos: nombre, título en bloque y las dos acciones a la
izquierda; cuatro filas separadas por líneas finas a la derecha. El código se
repite idéntico en las cuatro —es la misma imagen en cuatro situaciones— y una
cabecera lo dice, porque sin ella cuatro códigos iguales se leen como relleno
copiado en vez de como el argumento entero.

**Regla de copy: español llano, público general latinoamericano.** La primera
versión se escribió con vocabulario administrativo colombiano —asiento, radicado,
folio, constancia, emisor— y el usuario la rechazó por ilegible. La prueba es
simple: si una palabra no la usaría alguien ajeno al proyecto, no va. «Radicado»
pasó a **código**, también en los rótulos de la herramienta.

**Y sin disculpas.** La página se presenta en auditorio: declarar el alcance es
rigor, pero se escribe con seguridad. Nada de «todavía no sirve» ni de marcadores
de pendiente a la vista. Lo único que se declara siempre es que **las entidades
que aparezcan son ilustrativas**, en una línea discreta: la pantalla emite
certificados a nombre de quien uno escriba, y ahí la claridad protege al proyecto.

**El acento entra como forma, no como texto.** La regla nació de una necesidad:
en la paleta índigo el óxido medía 2.42:1 sobre el fondo y el verde ledger
2.05:1, los dos por debajo de 4.5, así que servían como relleno, filo o sello y
nunca como texto de cuerpo. **Y aun cuando el acento dejó de ser una limitación
—en la etapa monocroma era blanco puro— la regla se conservó.** Eso es lo que
permitió después cambiar a rosa tocando un solo bloque: el rosa llega a 6.8:1
sobre el suelo pero cae a 2.58:1 sobre cartulina, y la regla ya lo cubría.

**Cada estado usa un recurso distinto**, no el mismo filo lateral cuatro veces:
el asiento alterado parte su cuadro en diagonal —la misma gramática que el estado
`alterada` de la banda de veredicto— y suma un sello «EDITADA» sobre cartulina;
las tasas del 97 % llevan una llamada al pie `†`, recurso de ficha impresa; el
dolor de cada aplicación va en voz tipeada, sin recuadro; el equipo pendiente usa
borde discontinuo, como el sello ilegible de la herramienta.

## Composición de la herramienta

Tres filas a `100svh`, sin scroll dentro de su sección en escritorio.

```
membrete        el nombre, tipeado y chico │ las tres pestañas, en bloque
cuerpo          una vista a la vez
veredicto       una línea, fija
```

**Firmar y Verificar** son la misma columna centrada de 46rem: cartulina, línea
de acción, opciones plegadas, sello, y lo que cada una devuelve —la descarga en
Firmar, la constancia en Verificar—. **Pruebas** abre a `[rail 14–17rem]
[ficha 1fr]`.

En Firmar la línea lleva emisor, título y el botón. **En Verificar la línea lleva
solo el botón**, y al lado una frase tipeada que dice por qué: *«Sin contraseña.
La llave del registro no sale del servidor.»* Es la diferencia de producto más
importante de la pantalla y por eso está escrita ahí y no en la documentación.

**La cartulina abraza la lámina**: toma el alto disponible y su ancho sale de
`aspect-ratio: var(--ar)`, que el JS fija con la proporción real de la imagen que
acaba de entrar. Cada recorte cambia la forma del papel, así que el daño se ve en
el objeto y no solo en la foto.

Dos trampas de altura que costaron una ronda cada una, y que son la misma:
**una caja de alto indefinido hace que `max-height: 100%` no resuelva y el hijo
se desborde**. Pasó con una fila de grid `auto` (el contenedor del montaje es
flex, no grid, por eso) y con `place-items: center` en la vista (que dejaba
`.acto` sin alto; ahora es `align-items: stretch` y la cartulina se dimensiona
por alto, no por ancho).

## Componentes

- **Pestañas**: voz de bloque en versalitas, la activa en tinta plena con filo de
  óxido de 3 px abajo. Sin cápsulas, sin fondos.
- **Cartulina** (`.soltar`): es a la vez zona de soltar y montaje. Cuatro
  esquineros SVG, sombra con desplazamiento y desenfoque, y filo de óxido cuando
  hay algo arrastrándose encima.
- **Sello** (`.sello`): caja de 3 px en óxido, girada `-0.5deg` —más giro que eso,
  a ese ancho, se lee como error de layout—. Siempre en una sola línea
  (`white-space: nowrap`) salvo en teléfono, donde nadie lee a cinco metros y
  prefiere partirse antes que desbordar. Cuando no hay marca legible pasa a borde
  discontinuo en `--tinta-sec`, sin giro: la forma cambia, no solo el color.
- **Rail de ataques**: título, **tasa medida** y marca de estado. La tasa sale de
  `web/tasas.json` —que produce `web/tasas.py`— y se muestra siempre, aunque sea
  baja: un fallo en tarima tiene que leerse como resultado declarado y no como
  sorpresa. Si el archivo no está, no se muestra ningún porcentaje; nunca se
  inventa uno. El activo **invierte fondo y tinta por completo** —cartulina sobre
  índigo— para leerse a cinco metros sin depender del color.

  Al pie del rail puede aparecer un **aviso** (`.rail__aviso`) con la misma voz que
  `.nota-cotejo` —tipeada, secundaria, sin recuadro ni filo de color—, separado de
  la lista por una división de 1 px. En esta ficha una salvedad se escribe, no se
  encapsula: encerrarla en un bloque con filo lateral la habría convertido en el
  callout de siempre, y además la haría leerse como un paso más del rail.

  Sale cuando el servidor detecta que las tasas guardadas se midieron con un perfil
  distinto del que firma, y entonces **no muestra ninguna**. Existe porque el
  silencio no alcanzaba: los ocho porcentajes desaparecían y en tarima eso se lee
  como que la pantalla se rompió, no como la decisión deliberada que es. El aviso
  dice qué parámetro no coincide y con qué comando rehacerlo.
- **Constancia** (`.constancia`): rótulo tipeado chico a la izquierda, valor en
  tinta plena a la derecha. Cuatro renglones —emisor y clase, fecha, pieza,
  enlace— y nada más. El radicado **no** se repite acá: el sello ya es el
  radicado, con su momento de estampado.
- **Banda de veredicto**: verde `--ledger` con cuadro lleno para recuperado,
  óxido con aspa dibujada para sin marca legible, índigo hondo con cuadro hueco
  en reposo. Tres estados, tres formas distintas.
- **Cotejo por región** (`.cotejo` + `.nota-cotejo`): la misma marca leída por
  celdas de 32 px, rayada sobre la lámina como el lápiz graso del archivista
  sobre una copia. Ocupa el mismo hueco que la imagen —la caja de contenido de
  la cartulina, de ahí `inset: var(--pad)`—, así que el daño se señala sobre el
  objeto y no en una leyenda aparte.

  El trazo va **a dos tonos y en dos pasadas**: primero todas las bases claras en
  `--lamina`, después todas las de óxido. Sin la base el rayado se camufla cuando
  lo editado es de un color cercano al óxido —probado con un bloque rojo pegado:
  sólo se leía en los bordes—, y en una sola pasada la base de una celda taparía
  el trazo de su vecina. Rayado además de color, otra vez porque a cinco metros y
  con la gama del cañón el color solo no separa un estado de otro.

  Debajo, una línea tipeada que dice cuántas celdas no coinciden **y qué no
  detecta**: «un cambio uniforme sobre toda la imagen no se distingue del canal».
  El límite viaja pegado al resultado, no en la documentación.

- **Marcas de estado**: SVG dibujados, mismo trazo de 2.2, misma caja. Sin glifos
  Unicode ni emoji.

## Movimiento

**Un solo momento autorizado: el sello.** `estampar` va de
`rotate(-6deg) scale(1.3) blur(7px) opacity(0)` a su reposo en 420 ms con
`cubic-bezier(.16,1,.3,1)`. Es lo que hace un sello de caucho al caer sobre la
cartulina, y solo ocurre cuando hay identificador que estampar.

Lo demás son transiciones de estado de 120–220 ms. **La banda de veredicto nunca
se mueve**; solo late su marca mientras el códec trabaja. Bajo
`prefers-reduced-motion` todo cae a 0.01 ms.

## Superficies del navegador

Tematizadas desde la paleta, no heredadas: selección de texto en óxido sobre
cartulina, caret en óxido, scrollbars finas en `--indigo-borde` sobre
transparente, y anillo de foco de 3 px en óxido con 3 px de separación.

## Reglas del producto en la interfaz

1. **El veredicto nunca acusa.** Verificar tiene tres estados —«emitida por X»,
   «marca válida, radicado sin asiento» y «sin marca legible»— y ninguno dice que
   algo sea falso. Cuando no hay marca, el sello dice «no hay marca que leer» y la
   constancia no aparece: no se inventa ni un emisor ni un radicado.
2. **Verificar no pide contraseña.** ChaCha20-Poly1305 es simétrico: quien puede
   verificar puede falsificar. La llave del registro vive en el servidor, así que
   la pantalla de Verificar tiene exactamente un control, el botón.
3. **Nada escrito a mano.** Cada número visible lo devuelve el códec en esa
   llamada, o sale de `web/tasas.json`, que produce un comando del repo.
4. **La degradación se ve.** La lámina viaja en PNG sin pérdida para que el daño
   del ataque sea el del ataque y no el del visor.
5. **La espera se explica.** Decir que no cuesta más que decir que sí: el estado
   ocupado dice «escala nativa primero, después la búsqueda completa», porque los
   nueve segundos de un «sin marca» tienen una razón y conviene que se lea.
6. **Se maneja con teclado, sin chuleta en pantalla.** `1` `2` `3` cambian de
   pestaña; en Pruebas `→` avanza y coteja, `←` retrocede, `Enter` coteja. Están
   en `web/README.md`, no en la interfaz.

## Adaptación

Bajo 940 px la hoja sí scrollea, el rail pasa a tira horizontal, la cartulina
vuelve a dimensionarse por ancho con techo de `46svh`, y la banda de veredicto
queda pegajosa al pie. Bajo 620 px la raíz baja a `15px`, la línea de acción se
apila y el sello puede partirse.

## Contraste medido

Todo en la rampa neutra, y todo muy por encima de 4.5:1.

| Sobre | principal | secundario |
|---|---|---|
| el suelo `#0B0B0B` | **17.3:1** | 7.5:1 |
| el campo de la herramienta `#050505` | **17.9:1** | 7.8:1 |
| la cartulina `#F2F2F2` | 16.6:1 | 6.0:1 |

Botón primario —tinta sobre blanco— **18.6:1**. Veredicto positivo 15.2:1,
adverso 11.9:1.

La rampa neutra subió todos los números: con la paleta índigo el texto principal
estaba entre 10.8 y 11.8:1.

**La regla que sobrevive al cambio de paleta:** el acento nunca es texto de
cuerpo. Con color, óxido y verde ledger no llegaban a 4.5:1 sobre ningún fondo
—3.5:1 y 3.0:1 en el mejor caso— y usarlos como texto fue un error que hubo que
corregir en seis lugares. El rosa de hoy llega a 6.4:1 sobre el suelo y sí
podría ser texto ahí, pero sobre cartulina cae a 2.58:1 — así que la regla se
mantiene, y es lo que permitió cambiar el acento tocando un solo bloque.
