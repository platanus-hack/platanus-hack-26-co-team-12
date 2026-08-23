# Arquitectura

Cómo funciona el marcado de imagen de extremo a extremo, y por qué cada decisión
es la que es. Los defectos del sistema anterior que motivan cada cambio están en
[auditoria.md](auditoria.md).

## Visión general

```
IDENTIFICADOR (16 B)
      │
      ├─ payload.pack ──────► zlib · ChaCha20-Poly1305 · cabecera como AAD → trama 44 B
      │
      ├─ ecc.encode ────────► Reed-Solomon(84, 44) → codeword 84 B = 672 bits
      │
      ├─ layout.build ──────► desde k_chaos: dither, roles, pilotos, plantilla
      │
      └─ image_dct_qim ─────► QIM sobre DCT 8×8, tesela de 128 px repetida
                              + plantilla aditiva de periodo 64 px
```

La extracción es **ciega**: nada viaja fuera del archivo. Ni metadatos, ni
sidecar, ni la llave. Solo hace falta la passphrase.

## Capas

### 1. Llaves (`keys.py`)

```
passphrase ──Argon2id(t=3, m=64 MiB, p=1)──► master ──HKDF-SHA256──► k_cipher
                                                                  └► k_chaos
```

`k_cipher` cifra el payload; `k_chaos` gobierna **todo** el layout. Están
separadas a propósito: en el sistema anterior la misma órbita alimentaba el
keystream y las posiciones, y se podían deducir los bits de llave observando
las posiciones.

El salt es constante (`APP_SALT`) por necesidad estructural: el extractor ciego
no puede leer nada del archivo antes de derivar `k_chaos`, así que no hay dónde
guardar un salt por imagen. Eso exige passphrases fuertes.

**`tenant`** deriva solo `k_cipher`, no `k_chaos`. Así varios clientes comparten
el layout —y por tanto una única búsqueda de sincronía— mientras cada uno
conserva su llave de cifrado. Sin esta separación, verificar con N clientes
costaría N sincronías completas más N derivaciones Argon2id de 64 MiB.

### 2. Caos (`chaos.py`)

Mapa logístico en **punto fijo de 64 bits**:

```
X ← (X · (2⁶⁴ − X)) >> 62        equivale a  x ← 4·x·(1−x)
```

Tres decisiones, cada una corrigiendo un defecto medido:

| Decisión | Por qué |
|---|---|
| `r = 4` exacto | Con `r = 3.999952` el atractor se trunca y el test monobit falla con z = +10.5. Con r = 4 los bits por umbral son i.i.d. Bernoulli(½) |
| Punto fijo entero | En float64 el resultado depende de la libm, del orden de operaciones y de si hay FMA. En entero es idéntico en cualquier plataforma |
| Resiembra HKDF cada 1024 iteraciones | El mapa por sí solo es predecible: con 40 bits de keystream se recupera el estado. La resiembra corta esa observabilidad |

La permutación es **Fisher–Yates O(n)**. El muestreo con rechazo anterior no
terminaba nunca para n ≥ 20 834, porque con r < 4 el bin 0 no salía jamás.

El caos **no cifra nada**. Solo decide el layout. El cifrado es AEAD.

### 3. Payload (`payload.py`)

```
cabecera(4 B)          version │ flags │ longitud(2 B)     ← en claro, va como AAD
nonce(8 B)             aleatorio por mensaje
ciphertext + tag       ChaCha20-Poly1305, nonce12 = nonce8 ‖ cabecera
```

28 bytes de sobrecarga. Con un identificador de 16 B la trama son 44 B.

El tag AEAD es **el único criterio de aceptación** del sistema. No hay umbrales
de correlación que decidan si una marca es válida: o el tag cuadra (falso
positivo 2⁻¹²⁸) o no hay marca. Eso elimina de raíz el problema de falsos
positivos que arrastran los esquemas basados en correlación.

`zlib` se aplica solo si acorta. Es sin pérdida y cuesta microsegundos; la
"compresión semántica" por LLM del sistema anterior era con pérdida, no
determinista y consumía el 99.4% del tiempo total.

### 4. Corrección de errores (`ecc.py`)

Reed-Solomon(84, 44) sobre GF(2⁸): **corrige 20 errores o 40 borrados**.

La asimetría importa. Un recorte no produce errores: produce *borrados
conocidos* —el extractor sabe exactamente qué bloques no ve— y RS corrige el
doble de borrados que de errores (`s ≤ n−k` frente a `2e ≤ n−k`).

Además se marcan como borrados los símbolos de **baja fiabilidad**: el
decodificador ordena los símbolos por el valor blando más débil de sus 8 bits y
prueba presupuestos crecientes (0, 8, 16, 24, 32, 40). Probar varios es seguro
porque quien acepta es el tag AEAD, no un umbral.

### 5. Layout de la tesela (`image/layout.py`)

Todo indexado por la posición `m` dentro de la tesela, **idéntica en todas**,
de modo que el extractor la regenera sin conocer la posición absoluta.

| Parámetro | Valor |
|---|---|
| Bloque DCT | 8 × 8 px |
| Tesela | 16 × 16 bloques = 128 px |
| Portadores | (1,0), (0,1), (1,1) — 3 bits por bloque |
| Parche de símbolo | 2 × 4 bloques (24 bits = 3 símbolos) |
| Parches por tesela | 32, de los cuales 4 son piloto (12.5%) |
| Capacidad | 28 × 24 = 672 bits = 84 B por tesela |

El caos decide qué parches son piloto, el dither de cada portador, los bits
piloto y el orden de los parches de datos.

**Cada tesela lleva el payload completo.** Un recorte mayor que la tesela ve
todas las posiciones `m` al menos una vez, y las copias se combinan sumando los
valores blandos: si una copia cae en una zona texturizada y otra en una lisa,
domina la fiable.

Los parches son espacialmente contiguos por una razón concreta: si los 8 bits de
un símbolo estuvieran dispersos, perder una fracción L de los bloques borraría
casi todos los símbolos —P(intacto) = (1−L)⁸, que a L = 0.3 ya es 0.058— en vez
de una fracción L de ellos.

### 6. QIM sobre DCT (`image/qim.py`, `image/dct.py`)

Dither modulation (Chen–Wornell 2001). Para el coeficiente `c`, bit `β` y dither
`d`:

```
inserción:   c' = Δ·round((c − d − β·Δ/2)/Δ) + d + β·Δ/2
extracción:  β̂ = round(2(c−d)/Δ) mod 2
valor blando: s = cos(2π(c−d)/Δ)       signo = bit, |s| = fiabilidad
```

El error de inserción es uniforme en (−Δ/2, Δ/2], con media cero e
**independiente del contenido**. Hay error de lectura si y solo si la
perturbación supera Δ/4.

Para JPEG con la malla alineada el error de cuantización está **acotado**:
`|e| ≤ q_k(Q)/2`. De ahí la cota de diseño:

```
Δ ≥ 2·q_k(Q_min) + 4
```

A Q50 los pasos de los tres portadores son 13–16, luego Δ = 26 cubre Q ≥ 40.
A Q30 suben a 18 y hace falta Δ ≥ 40.

**Los portadores son de baja frecuencia a propósito.** (1,0) es medio ciclo por
bloque, es decir un periodo de 16 px. Al reescalar a la mitad sigue siendo 32 px
de periodo, muy por encima de Nyquist. La banda media clásica —(2,1), (3,0)—
tiene mejor relación capacidad/distorsión pero no sobrevive al reescalado, que
es justo lo que hacen los canales reales.

### 7. Resolución base

El marcado ocurre sobre la luminancia normalizada a **1024 px de lado largo**, y
el residuo se interpola de vuelta al tamaño nativo:

```
y_base    = reducir(Y, 1024)
residuo   = QIM(y_base) − y_base
Y_marcada = Y + ampliar(residuo, tamaño nativo)
```

La razón es asimétrica y decisiva: **interpolar hacia arriba no recupera lo que
el canal descartó**. Marcando en nativo, un envío por WhatsApp que reduce a
1600 px se pierde aunque la sincronía acierte la escala —está medido—. Marcando
en base, el verificador solo tiene que *reducir*, que está bien condicionado.

El coste es que el recorte mínimo en píxeles nativos crece con el tamaño del
original: en una imagen de 2400 px la tesela mide 300 px nativos.

### 8. Sincronía (`image/sync.py`)

El problema: escala y posición desconocidas. La solución es una **plantilla
aditiva periódica** que hace de regla de medir.

La plantilla es ruido pseudoaleatorio a resolución de bloque, suavizado a 8 px.
Es gruesa a propósito: una plantilla de alta frecuencia no sobreviviría al JPEG
ni al reescalado, que es exactamente para lo que sirve.

**Va modulada por enmascaramiento perceptual** (`image/masking.py`). Al principio
se sumaba con amplitud constante a todos los píxeles, y eso ignoraba lo único que
decide si una marca se ve: el mismo error es invisible sobre una textura y
evidente sobre un cielo. A `template_amp = 6.0` inyectaba un RMS de 2.29 niveles
con picos de ±6.9 —contraste Weber del 1.8 %, muy por encima del umbral de
detección— en un patrón periódico exacto, y en cielos, paredes y piel se veía
como un moteado. Reparto de la energía de error a Δ=26: **plantilla 66 %, QIM 34 %**.

La ganancia sale de la desviación típica local y redistribuye: lo que se le quita
al cielo se le devuelve a la textura, que lo esconde. **No rompe la extracción
ciega**, y la razón es la misma por la que la marca sobrevive a cambios de
contraste: el sincronizador correlaciona contra el *patrón*, y una ganancia local
positiva solo repondera los sumandos del plegado sin mover el pico. El extractor
no recibe ningún parámetro de máscara.

Lo que sí cambia es la **altura** del pico, o sea la `z`. Es el número a vigilar
al tocar `masking.DEFAULTS`, y no se puede dar por supuesto que sale gratis: las
zonas planas son justamente donde la plantilla más sobresale del contenido.

De los cuatro parámetros, **`floor` es la palanca útil** y `knee` no lo es. `floor`
es la ganancia mínima —cuánta plantilla queda en lo perfectamente liso—: bajarlo de
0.35 a 0.12 quitó un 22 % de la nube visible sin costar un solo punto de
recuperación, porque la sincronía se sostiene sobre la textura, no sobre el cielo.
`knee` movido de 6.0 a 9.0 mejora la nube parecido pero tumba el recorte de 256 px
de 9/9 a 7/9: desplaza la rodilla hacia arriba y deja sin ganancia a la textura
media, que es la que más superficie ocupa.

La advertencia de que un `floor` bajo crea escalones visibles en el borde
lisa/textura **no se materializa a 0.12**: la ganancia gana rango (salto p99 de
0.15 a 0.23) pero el gradiente de la marca en esos bordes *baja* (0.519 → 0.495),
porque el `boost` renormaliza y en zona plana queda menos amplitud total. El campo
de `local_std` va suavizado en ventana de 17 px, así que no hay discontinuidad
dura que mostrar.

Lo que **no** se puede hacer es aleatorizar el mosaico por posición para romper la
periodicidad visual: la repetición exacta cada 64 px *es* el mecanismo de
sincronía. La periodicidad es carga estructural; la amplitud no.

**Va sumada antes del QIM.** Si se sumara después, su energía en los portadores
desplazaría cada coeficiente de forma sistemática según la posición de tesela —un
sesgo que no promedia al acumular copias—. Este fue un fallo real durante el
desarrollo: 3.7% de bits sistemáticamente invertidos.

**Su periodo es 64 px, no 128.** Plegar la imagen recibida módulo 64 cuadruplica
el número de copias que se suman, que es lo que decide si la correlación se
engancha. Un recorte de 800×600 de una imagen de 2400 px deja solo 2×2 teselas
de 128 px —insuficiente en contenido texturizado— pero 5×4 de 64 px. La
ambigüedad restante (fase de tesela módulo 8 bloques) son 4 hipótesis, resueltas
con los pilotos.

El procedimiento completo:

1. **Blanqueado**: paso banda 5–33 px, donde vive la plantilla y no el contenido.
2. **Candidatas de escala**: la escala 1.0 siempre, más los periodos que sugiere
   la autocorrelación proyectada (con refinamiento parabólico sub-píxel), más
   una rejilla sistemática de respaldo si ninguna alcanza el umbral.
3. **Refinado por bisección** hasta que el error relativo de escala sea menor que
   `MAX_DRIFT_PX / ancho`. La precisión importa mucho: un error relativo `e`
   desplaza el borde de la imagen en `e·ancho` píxeles, y con un paso fijo del
   0.12% una imagen de 2400 px acumula 3 px de deriva.
4. **Localización**: plegado módulo 64 y correlación circular por FFT contra la
   plantilla.
5. **Alineación fina por pilotos** (`_align`): ±2 px y las 4 hipótesis de fase de
   tesela, minimizando el BER de pilotos. La correlación puede errar 1–2 px
   porque la autocorrelación de la plantilla es ancha, y un solo píxel ya degrada
   el QIM.
6. **Refinado sub-píxel**: un recorte en píxeles nativos cae en posición
   *fraccionaria* de la malla base —recortar en (13,37) de una imagen de 2400 px
   marcada a 1024 equivale a (5.55, 15.79)— y medio píxel basta para romper el
   QIM en contenido texturizado.
7. **Respaldo por pilotos**: si nada baja del 15% de BER, se barre la rejilla
   completa decidiendo por pilotos en vez de por correlación. Cuesta segundos,
   pero la verificación es forense y diferida.

El criterio de comparación entre escalas exige no perder cobertura de pilotos:
una escala equivocada puede dejar pocos pilotos visibles y sacar un BER bajo por
azar.

### 9. Integridad por región (`integrity.py`)

La misma marca sirve para dos cosas opuestas según cómo se lea.

Una marca robusta **sobrevive a la edición** — para eso está hecha: si se
rompiera con cualquier cambio no serviría para rastrear nada. La consecuencia es
que prueba **procedencia**, nunca integridad. Si alguien pega un objeto sobre la
imagen, el identificador se sigue leyendo, porque las teselas que no tocó están
intactas.

Pero las teselas bajo el objeto **sí** se rompieron. Esa información ya estaba
ahí; solo había que mirarla por región en vez de en global:

| Lectura | Qué degrada | Qué responde |
|---|---|---|
| Global, acumulando todas las copias | Un canal: leve y uniforme sobre toda la imagen | Procedencia: de qué copia salió |
| Por celda, sin acumular | Una edición: severa y localizada | Integridad, y dónde |

La distinción no necesita calibración previa: **una edición es local y severa, un
canal es global y suave**. Cada celda se compara contra la mediana de las demás.

El procedimiento: se re-codifica el codeword a partir de la trama ya recuperada
—así se conocen los bits que cada bloque *debería* llevar—, se compara con los
leídos y se agrega por celdas de 4×4 bloques (32 px).

Dos detalles que costaron calibrar:

- **El BER por celda no es cero ni en una imagen intacta.** La extracción
  promedia cada bit sobre todas las copias de tesela; aquí se leen bloques
  sueltos. Con 48 bits por celda la estimación tiene una desviación binomial de
  ~0.04, y el máximo sobre cientos de celdas se aleja solo de la mediana. Por eso
  el umbral no es absoluto sino `mediana + z·σ`, con `z = √(2·ln N) + 2` para
  acotar el máximo esperado de N celdas.
- **La mediana puede ser exactamente cero**, y entonces la desviación binomial
  colapsa y el umbral se va a cero, marcando cualquier celda con un solo bit
  erróneo. Se suaviza con un piso de `1/n_bits`, el propio grano de la medida.

La resolución de detección es el tamaño de celda: una edición mucho más pequeña
que 32 px se diluye. Es un compromiso explícito, ajustable con `--cell-blocks`.

## Estructura del código

```
src/stego/
├── keys.py                  Argon2id + HKDF → (k_cipher, k_chaos)
├── chaos.py                 LogisticFP64, chaos_permutation
├── cipher.py                ChaCha20-Poly1305
├── payload.py               cabecera + nonce + AEAD + zlib
├── ecc.py                   Reed-Solomon con borrados
├── integrity.py             verificacion por region (marca semi-fragil)
├── cli.py                   stego embed | extract
├── image/
│   ├── color.py             RGB ↔ YCbCr BT.601
│   ├── dct.py               DCT-II ortonormal 8×8 por lotes
│   ├── qim.py               dither modulation
│   ├── layout.py            tesela: roles, dither, pilotos, plantilla
│   ├── resample.py          remuestreo Lanczos
│   └── sync.py              escala y posición
├── covers/image_dct_qim.py  codec: embed / extract
└── attacks/image.py         jpeg, crop, rescale, whatsapp
```
